from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid5

from medical_audit_kb.domain.constants import DocumentStatus, FileErrorType, IndexJobType
from medical_audit_kb.domain.schemas import DocumentChunkCreate
from medical_audit_kb.indexing.index_jobs import (
    IndexDiff,
    IndexRunSummary,
    ManifestIndexSnapshot,
    build_index_version_key,
    compare_snapshots,
)
from medical_audit_kb.ingestion.chunkers import chunk_extraction_result
from medical_audit_kb.ingestion.extractors import ExtractionStatus, extract_file
from medical_audit_kb.ingestion.inventory import InventoryFile, build_source_package_manifest

PIPELINE_DOCUMENT_NAMESPACE = UUID("2c6ac9c4-2625-4878-a8e4-1c30a0cb0c6d")


@dataclass(frozen=True, slots=True)
class PipelineFileIssue:
    relative_path: str
    error_type: FileErrorType
    error_summary: str


@dataclass(frozen=True, slots=True)
class PipelineFileResult:
    relative_path: str
    status: ExtractionStatus
    chunk_count: int
    chunks: tuple[DocumentChunkCreate, ...] = ()
    error_type: FileErrorType | None = None
    error_summary: str | None = None


@dataclass(frozen=True, slots=True)
class PipelineRunResult:
    summary: IndexRunSummary
    snapshot: ManifestIndexSnapshot
    file_results: tuple[PipelineFileResult, ...]
    failed_files: tuple[PipelineFileIssue, ...]
    pending_files: tuple[PipelineFileIssue, ...]
    diff: IndexDiff | None = None


class KnowledgeIndexPipeline:
    def __init__(
        self,
        *,
        max_chunk_chars: int = 1800,
        overlap_chars: int = 180,
    ) -> None:
        self._max_chunk_chars = max_chunk_chars
        self._overlap_chars = overlap_chars

    def run_full_rebuild(
        self,
        source_root: Path | str,
        *,
        package_version_key: str | None = None,
        max_chunks: int | None = None,
    ) -> PipelineRunResult:
        if max_chunks is not None and max_chunks <= 0:
            raise ValueError("max_chunks must be positive")
        manifest = build_source_package_manifest(source_root, version_key=package_version_key)
        snapshot = ManifestIndexSnapshot.from_manifest(manifest)
        file_results, failed_files, extraction_pending_files = self._process_files(
            manifest.index_candidates,
            max_chunks=max_chunks,
        )
        pending_files = _manifest_pending_issues(manifest.pending_files) + extraction_pending_files
        summary = IndexRunSummary(
            job_type=IndexJobType.FULL_REBUILD,
            index_version_key=build_index_version_key(IndexJobType.FULL_REBUILD),
            source_package_version_key=manifest.package_version.version_key,
            discovered_file_count=len(manifest.files),
            index_candidate_file_count=len(manifest.index_candidates),
            indexed_file_count=_indexed_count(file_results),
            chunk_count=sum(result.chunk_count for result in file_results),
            failed_file_count=len(failed_files),
            pending_file_count=len(pending_files),
            ignored_file_count=len(manifest.ignored_files),
            added_file_count=len(manifest.index_candidates),
            comparison={
                "before_index_candidate_file_count": 0,
                "after_index_candidate_file_count": len(manifest.index_candidates),
            },
        )
        return PipelineRunResult(
            summary=summary,
            snapshot=snapshot,
            file_results=file_results,
            failed_files=failed_files,
            pending_files=pending_files,
        )

    def run_incremental(
        self,
        source_root: Path | str,
        *,
        previous_snapshot: ManifestIndexSnapshot,
        package_version_key: str | None = None,
    ) -> PipelineRunResult:
        manifest = build_source_package_manifest(source_root, version_key=package_version_key)
        snapshot = ManifestIndexSnapshot.from_manifest(manifest)
        diff = compare_snapshots(previous_snapshot, snapshot)
        candidate_by_path = {file.relative_path: file for file in manifest.index_candidates}
        files_to_process = tuple(
            candidate_by_path[file.relative_path]
            for file in diff.changed
            if file.relative_path in candidate_by_path
        )
        file_results, failed_files, extraction_pending_files = self._process_files(files_to_process)
        pending_files = _manifest_pending_issues(manifest.pending_files) + extraction_pending_files
        comparison = diff.counts_by_type()
        comparison.update(
            {
                "before_index_candidate_file_count": len(
                    previous_snapshot.index_candidates_by_path
                ),
                "after_index_candidate_file_count": len(snapshot.index_candidates_by_path),
            }
        )
        summary = IndexRunSummary(
            job_type=IndexJobType.INCREMENTAL,
            index_version_key=build_index_version_key(IndexJobType.INCREMENTAL),
            source_package_version_key=manifest.package_version.version_key,
            before_package_version_key=previous_snapshot.package_version_key,
            discovered_file_count=len(manifest.files),
            index_candidate_file_count=len(manifest.index_candidates),
            indexed_file_count=_indexed_count(file_results),
            chunk_count=sum(result.chunk_count for result in file_results),
            failed_file_count=len(failed_files),
            pending_file_count=len(pending_files),
            ignored_file_count=len(manifest.ignored_files),
            added_file_count=len(diff.added),
            modified_file_count=len(diff.modified),
            deleted_file_count=len(diff.deleted),
            unchanged_file_count=len(diff.unchanged),
            comparison=comparison,
        )
        return PipelineRunResult(
            summary=summary,
            snapshot=snapshot,
            file_results=file_results,
            failed_files=failed_files,
            pending_files=pending_files,
            diff=diff,
        )

    def retry_file(
        self,
        source_root: Path | str,
        *,
        relative_path: str,
        package_version_key: str | None = None,
    ) -> PipelineRunResult:
        manifest = build_source_package_manifest(source_root, version_key=package_version_key)
        snapshot = ManifestIndexSnapshot.from_manifest(manifest)
        file_by_path = {file.relative_path: file for file in manifest.files}
        selected_file = file_by_path.get(relative_path)
        file_results: tuple[PipelineFileResult, ...] = ()
        failed_files: tuple[PipelineFileIssue, ...] = ()
        extraction_pending_files: tuple[PipelineFileIssue, ...] = ()

        if selected_file is None:
            failed_files = (
                PipelineFileIssue(
                    relative_path=relative_path,
                    error_type=FileErrorType.VALIDATION_FAILED,
                    error_summary="retry target not found in source package",
                ),
            )
        elif selected_file.status != DocumentStatus.INDEX_CANDIDATE:
            extraction_pending_files = (
                PipelineFileIssue(
                    relative_path=relative_path,
                    error_type=FileErrorType.UNSUPPORTED_TYPE,
                    error_summary=selected_file.reason or "retry target is not indexable",
                ),
            )
        else:
            file_results, failed_files, extraction_pending_files = self._process_files(
                (selected_file,)
            )

        pending_files = extraction_pending_files
        summary = IndexRunSummary(
            job_type=IndexJobType.RETRY_FILE,
            index_version_key=build_index_version_key(IndexJobType.RETRY_FILE),
            source_package_version_key=manifest.package_version.version_key,
            discovered_file_count=len(manifest.files),
            index_candidate_file_count=len(manifest.index_candidates),
            indexed_file_count=_indexed_count(file_results),
            chunk_count=sum(result.chunk_count for result in file_results),
            failed_file_count=len(failed_files),
            pending_file_count=len(pending_files),
            ignored_file_count=len(manifest.ignored_files),
            retried_file=relative_path,
            comparison={"retried_file_found": 1 if selected_file is not None else 0},
        )
        return PipelineRunResult(
            summary=summary,
            snapshot=snapshot,
            file_results=file_results,
            failed_files=failed_files,
            pending_files=pending_files,
        )

    def _process_files(
        self,
        files: tuple[InventoryFile, ...],
        *,
        max_chunks: int | None = None,
    ) -> tuple[
        tuple[PipelineFileResult, ...],
        tuple[PipelineFileIssue, ...],
        tuple[PipelineFileIssue, ...],
    ]:
        results: list[PipelineFileResult] = []
        failed_files: list[PipelineFileIssue] = []
        pending_files: list[PipelineFileIssue] = []
        remaining_chunks = max_chunks

        for file in files:
            if remaining_chunks is not None and remaining_chunks <= 0:
                break
            try:
                result = extract_file(file.path)
            except Exception as exc:
                issue = _unexpected_file_issue(file.relative_path, exc)
                failed_files.append(issue)
                results.append(
                    PipelineFileResult(
                        relative_path=file.relative_path,
                        status=ExtractionStatus.FAILED,
                        chunk_count=0,
                        error_type=issue.error_type,
                        error_summary=issue.error_summary,
                    )
                )
                continue

            if result.status == ExtractionStatus.EXTRACTED and file.source_collection is not None:
                try:
                    chunks = chunk_extraction_result(
                        result,
                        source_document_id=_document_uuid(file),
                        source_collection=file.source_collection,
                        domain=file.domain,
                        relative_path=file.relative_path,
                        max_chunk_chars=self._max_chunk_chars,
                        overlap_chars=self._overlap_chars,
                    )
                    selected_chunks = (
                        tuple(chunks[:remaining_chunks])
                        if remaining_chunks is not None
                        else tuple(chunks)
                    )
                except Exception as exc:
                    issue = _unexpected_file_issue(file.relative_path, exc)
                    failed_files.append(issue)
                    results.append(
                        PipelineFileResult(
                            relative_path=file.relative_path,
                            status=ExtractionStatus.FAILED,
                            chunk_count=0,
                            error_type=issue.error_type,
                            error_summary=issue.error_summary,
                        )
                    )
                    continue
                if not selected_chunks:
                    issue = PipelineFileIssue(
                        relative_path=file.relative_path,
                        error_type=FileErrorType.LOW_QUALITY_TEXT,
                        error_summary="extracted content produced no indexable chunks",
                    )
                    pending_files.append(issue)
                    results.append(
                        PipelineFileResult(
                            relative_path=file.relative_path,
                            status=ExtractionStatus.PENDING,
                            chunk_count=0,
                            error_type=issue.error_type,
                            error_summary=issue.error_summary,
                        )
                    )
                    continue
                results.append(
                    PipelineFileResult(
                        relative_path=file.relative_path,
                        status=result.status,
                        chunk_count=len(selected_chunks),
                        chunks=selected_chunks,
                    )
                )
                if remaining_chunks is not None:
                    remaining_chunks -= len(selected_chunks)
                continue

            issue = PipelineFileIssue(
                relative_path=file.relative_path,
                error_type=result.error_type or FileErrorType.EXTRACTION_FAILED,
                error_summary=result.error_summary or "file did not produce extracted content",
            )
            if result.status == ExtractionStatus.PENDING:
                pending_files.append(issue)
            else:
                failed_files.append(issue)
            results.append(
                PipelineFileResult(
                    relative_path=file.relative_path,
                    status=result.status,
                    chunk_count=0,
                    error_type=issue.error_type,
                    error_summary=issue.error_summary,
                )
            )

        return tuple(results), tuple(failed_files), tuple(pending_files)


def _manifest_pending_issues(files: tuple[InventoryFile, ...]) -> tuple[PipelineFileIssue, ...]:
    return tuple(
        PipelineFileIssue(
            relative_path=file.relative_path,
            error_type=FileErrorType.UNSUPPORTED_TYPE,
            error_summary=file.reason or "file is pending",
        )
        for file in files
    )


def _indexed_count(results: tuple[PipelineFileResult, ...]) -> int:
    return len(
        [
            result
            for result in results
            if result.status == ExtractionStatus.EXTRACTED and result.chunk_count > 0
        ]
    )


def _document_uuid(file: InventoryFile) -> UUID:
    return uuid5(PIPELINE_DOCUMENT_NAMESPACE, f"{file.relative_path}:{file.sha256}")


def _unexpected_file_issue(relative_path: str, exc: Exception) -> PipelineFileIssue:
    return PipelineFileIssue(
        relative_path=relative_path,
        error_type=FileErrorType.EXTRACTION_FAILED,
        error_summary=f"pipeline processing failed: {type(exc).__name__}: {exc}",
    )
