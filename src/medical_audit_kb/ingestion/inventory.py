from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from medical_audit_kb.domain.constants import DocumentStatus, SourceCollection
from medical_audit_kb.domain.schemas import SourcePackageVersionCreate

SOURCE_COLLECTION_BY_TOP_LEVEL: Final = {
    "医保目录": SourceCollection.MEDICAL_INSURANCE_CATALOG,
    "智能监管“两库”规则和知识点": SourceCollection.SUPERVISION_RULES_KNOWLEDGE,
    "风险负面清单": SourceCollection.RISK_NEGATIVE_LIST,
    "全量法律": SourceCollection.MEDICAL_INSURANCE_LAWS,
}

LAW_KEYWORDS: Final = (
    "医保",
    "医疗保障",
    "基本医疗保险",
    "医疗保障基金",
    "医疗机构",
    "医疗保险",
    "药品",
    "处方",
    "门诊",
    "住院",
    "诊疗",
    "卫生",
    "生育保险",
    "工伤保险",
    "DRG",
    "DIP",
)

SUPPORTED_MEDIA_TYPES: Final = {
    ".md": "text/markdown",
    ".txt": "text/plain",
    ".pdf": "application/pdf",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

PENDING_MEDIA_TYPES: Final = {
    ".png": "image/png",
    ".zip": "application/zip",
    ".rar": "application/vnd.rar",
}

SYSTEM_FILE_NAMES: Final = frozenset({".DS_Store"})
HASH_BLOCK_SIZE: Final = 1024 * 1024


@dataclass(frozen=True, slots=True)
class InventoryFile:
    path: Path
    relative_path: str
    file_name: str
    file_ext: str
    media_type: str
    size_bytes: int
    sha256: str
    source_collection: SourceCollection | None
    status: DocumentStatus
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class SourcePackageManifest:
    package_version: SourcePackageVersionCreate
    files: tuple[InventoryFile, ...]
    duplicate_groups: dict[str, tuple[InventoryFile, ...]]

    @property
    def index_candidates(self) -> tuple[InventoryFile, ...]:
        return tuple(file for file in self.files if file.status == DocumentStatus.INDEX_CANDIDATE)

    @property
    def pending_files(self) -> tuple[InventoryFile, ...]:
        return tuple(file for file in self.files if file.status == DocumentStatus.PENDING)

    @property
    def ignored_files(self) -> tuple[InventoryFile, ...]:
        return tuple(file for file in self.files if file.status == DocumentStatus.IGNORED)


def build_source_package_manifest(
    source_root: Path | str,
    *,
    version_key: str | None = None,
) -> SourcePackageManifest:
    root = Path(source_root)
    if not root.exists():
        raise FileNotFoundError(f"source root not found: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"source root must be a directory: {root}")

    files = tuple(_scan_files(root))
    duplicate_groups = _find_duplicate_groups(files)
    package_version = SourcePackageVersionCreate(
        version_key=version_key or _default_version_key(root),
        source_root_path=root,
        description="knowledge query source package inventory",
        metadata={
            "total_files": len(files),
            "index_candidate_count": len(
                [file for file in files if file.status == DocumentStatus.INDEX_CANDIDATE]
            ),
            "pending_count": len([file for file in files if file.status == DocumentStatus.PENDING]),
            "ignored_count": len([file for file in files if file.status == DocumentStatus.IGNORED]),
            "duplicate_group_count": len(duplicate_groups),
        },
    )
    return SourcePackageManifest(
        package_version=package_version,
        files=files,
        duplicate_groups=duplicate_groups,
    )


def classify_source_collection(relative_path: Path) -> SourceCollection | None:
    if not relative_path.parts:
        return None

    top_level = relative_path.parts[0]
    if top_level in SOURCE_COLLECTION_BY_TOP_LEVEL:
        collection = SOURCE_COLLECTION_BY_TOP_LEVEL[top_level]
        if collection == SourceCollection.MEDICAL_INSURANCE_LAWS:
            return collection if is_medical_insurance_law(relative_path.name) else None
        return collection

    if is_medical_insurance_law(relative_path.name):
        return SourceCollection.MEDICAL_INSURANCE_LAWS

    return None


def is_medical_insurance_law(file_name: str) -> bool:
    normalized = file_name.upper()
    return any(keyword.upper() in normalized for keyword in LAW_KEYWORDS)


def calculate_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(HASH_BLOCK_SIZE), b""):
            digest.update(block)
    return digest.hexdigest()


def _scan_files(root: Path) -> list[InventoryFile]:
    files: list[InventoryFile] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        files.append(_build_inventory_file(root, path))
    return files


def _build_inventory_file(root: Path, path: Path) -> InventoryFile:
    relative_path = path.relative_to(root)
    file_name = path.name
    file_ext = path.suffix.lower()
    size_bytes = path.stat().st_size
    sha256 = calculate_sha256(path)
    media_type = _media_type_for_ext(file_ext)
    source_collection = classify_source_collection(relative_path)
    status, reason = _classify_status(file_name, file_ext, source_collection, relative_path)

    return InventoryFile(
        path=path,
        relative_path=relative_path.as_posix(),
        file_name=file_name,
        file_ext=file_ext,
        media_type=media_type,
        size_bytes=size_bytes,
        sha256=sha256,
        source_collection=source_collection,
        status=status,
        reason=reason,
    )


def _media_type_for_ext(file_ext: str) -> str:
    if file_ext in SUPPORTED_MEDIA_TYPES:
        return SUPPORTED_MEDIA_TYPES[file_ext]
    if file_ext in PENDING_MEDIA_TYPES:
        return PENDING_MEDIA_TYPES[file_ext]
    return "application/octet-stream"


def _classify_status(
    file_name: str,
    file_ext: str,
    source_collection: SourceCollection | None,
    relative_path: Path,
) -> tuple[DocumentStatus, str | None]:
    if file_name in SYSTEM_FILE_NAMES:
        return DocumentStatus.IGNORED, "system-file"

    if source_collection is None and relative_path.parts[:1] == ("全量法律",):
        return DocumentStatus.IGNORED, "outside-v1-law-scope"

    if file_ext not in SUPPORTED_MEDIA_TYPES:
        return DocumentStatus.PENDING, "unsupported-file-type"

    if source_collection is None:
        return DocumentStatus.PENDING, "unknown-source-collection"

    return DocumentStatus.INDEX_CANDIDATE, None


def _find_duplicate_groups(
    files: tuple[InventoryFile, ...],
) -> dict[str, tuple[InventoryFile, ...]]:
    grouped: defaultdict[str, list[InventoryFile]] = defaultdict(list)
    for file in files:
        if file.status == DocumentStatus.IGNORED:
            continue
        grouped[file.sha256].append(file)

    return {
        digest: tuple(items)
        for digest, items in grouped.items()
        if len(items) > 1
    }


def _default_version_key(root: Path) -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    return f"{root.name}-{timestamp}"
