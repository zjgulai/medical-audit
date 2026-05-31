from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Final

from medical_audit_kb.domain.constants import DocumentStatus, IndexJobType, SourceCollection
from medical_audit_kb.ingestion.inventory import InventoryFile, SourcePackageManifest

INDEX_VERSION_TIME_FORMAT: Final = "%Y%m%d%H%M%S"


class FileChangeType(StrEnum):
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    UNCHANGED = "unchanged"


@dataclass(frozen=True, slots=True)
class FileIndexState:
    relative_path: str
    sha256: str
    status: DocumentStatus
    source_collection: SourceCollection | None
    file_ext: str
    size_bytes: int
    reason: str | None = None

    @classmethod
    def from_inventory_file(cls, file: InventoryFile) -> FileIndexState:
        return cls(
            relative_path=file.relative_path,
            sha256=file.sha256,
            status=file.status,
            source_collection=file.source_collection,
            file_ext=file.file_ext,
            size_bytes=file.size_bytes,
            reason=file.reason,
        )


@dataclass(frozen=True, slots=True)
class ManifestIndexSnapshot:
    package_version_key: str
    files_by_path: dict[str, FileIndexState]

    @classmethod
    def from_manifest(cls, manifest: SourcePackageManifest) -> ManifestIndexSnapshot:
        return cls(
            package_version_key=manifest.package_version.version_key,
            files_by_path={
                file.relative_path: FileIndexState.from_inventory_file(file)
                for file in manifest.files
            },
        )

    @property
    def index_candidates_by_path(self) -> dict[str, FileIndexState]:
        return {
            path: file
            for path, file in self.files_by_path.items()
            if file.status == DocumentStatus.INDEX_CANDIDATE
        }


@dataclass(frozen=True, slots=True)
class IndexDiff:
    added: tuple[FileIndexState, ...]
    modified: tuple[FileIndexState, ...]
    deleted: tuple[FileIndexState, ...]
    unchanged: tuple[FileIndexState, ...]

    @property
    def changed(self) -> tuple[FileIndexState, ...]:
        return self.added + self.modified

    def counts_by_type(self) -> dict[str, int]:
        return {
            FileChangeType.ADDED.value: len(self.added),
            FileChangeType.MODIFIED.value: len(self.modified),
            FileChangeType.DELETED.value: len(self.deleted),
            FileChangeType.UNCHANGED.value: len(self.unchanged),
        }


@dataclass(frozen=True, slots=True)
class IndexRunSummary:
    job_type: IndexJobType
    index_version_key: str
    source_package_version_key: str
    discovered_file_count: int
    index_candidate_file_count: int
    indexed_file_count: int
    chunk_count: int
    failed_file_count: int
    pending_file_count: int
    ignored_file_count: int
    added_file_count: int = 0
    modified_file_count: int = 0
    deleted_file_count: int = 0
    unchanged_file_count: int = 0
    retried_file: str | None = None
    before_package_version_key: str | None = None
    comparison: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "job_type": self.job_type.value,
            "index_version_key": self.index_version_key,
            "source_package_version_key": self.source_package_version_key,
            "before_package_version_key": self.before_package_version_key,
            "discovered_file_count": self.discovered_file_count,
            "index_candidate_file_count": self.index_candidate_file_count,
            "indexed_file_count": self.indexed_file_count,
            "chunk_count": self.chunk_count,
            "failed_file_count": self.failed_file_count,
            "pending_file_count": self.pending_file_count,
            "ignored_file_count": self.ignored_file_count,
            "added_file_count": self.added_file_count,
            "modified_file_count": self.modified_file_count,
            "deleted_file_count": self.deleted_file_count,
            "unchanged_file_count": self.unchanged_file_count,
            "retried_file": self.retried_file,
            "comparison": self.comparison,
        }


def compare_snapshots(
    previous: ManifestIndexSnapshot,
    current: ManifestIndexSnapshot,
) -> IndexDiff:
    previous_candidates = previous.index_candidates_by_path
    current_candidates = current.index_candidates_by_path

    added: list[FileIndexState] = []
    modified: list[FileIndexState] = []
    deleted: list[FileIndexState] = []
    unchanged: list[FileIndexState] = []

    for path, current_file in sorted(current_candidates.items()):
        previous_file = previous_candidates.get(path)
        if previous_file is None:
            added.append(current_file)
        elif previous_file.sha256 != current_file.sha256:
            modified.append(current_file)
        else:
            unchanged.append(current_file)

    for path, previous_file in sorted(previous_candidates.items()):
        if path not in current_candidates:
            deleted.append(previous_file)

    return IndexDiff(
        added=tuple(added),
        modified=tuple(modified),
        deleted=tuple(deleted),
        unchanged=tuple(unchanged),
    )


def build_index_version_key(job_type: IndexJobType, *, now: datetime | None = None) -> str:
    timestamp = (now or datetime.now(UTC)).strftime(INDEX_VERSION_TIME_FORMAT)
    return f"{job_type.value}-{timestamp}"


def summarize_manifest_counts(manifest: SourcePackageManifest) -> dict[str, int]:
    return {
        "discovered_file_count": len(manifest.files),
        "index_candidate_file_count": len(manifest.index_candidates),
        "pending_file_count": len(manifest.pending_files),
        "ignored_file_count": len(manifest.ignored_files),
    }
