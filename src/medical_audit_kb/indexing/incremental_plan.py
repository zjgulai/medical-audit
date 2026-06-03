from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from medical_audit_kb.domain.constants import DocumentStatus, SourceCollection
from medical_audit_kb.indexing.index_jobs import FileIndexState, ManifestIndexSnapshot
from medical_audit_kb.ingestion.pipeline import KnowledgeIndexPipeline, PipelineFileIssue

DEFAULT_MAX_SAMPLE_ITEMS = 20

SqlParams = tuple[object, ...]


class IncrementalPlanError(RuntimeError):
    pass


class IncrementalPlanCursor(Protocol):
    def execute(self, query: str, params: SqlParams | None = None) -> object:
        pass

    def fetchall(self) -> list[tuple[object, ...]]:
        pass


@dataclass(frozen=True, slots=True)
class ActiveSourceDocument:
    relative_path: str
    sha256: str
    source_collection: str
    file_ext: str
    size_bytes: int
    chunk_count: int


@dataclass(frozen=True, slots=True)
class IncrementalPlanFile:
    relative_path: str
    sha256: str
    source_collection: str | None
    file_ext: str
    size_bytes: int
    reason: str | None = None
    chunk_count: int | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "relative_path": self.relative_path,
            "sha256": self.sha256,
            "source_collection": self.source_collection,
            "file_ext": self.file_ext,
            "size_bytes": self.size_bytes,
            "reason": self.reason,
            "chunk_count": self.chunk_count,
        }


@dataclass(frozen=True, slots=True)
class IncrementalPlanIssue:
    relative_path: str
    error_type: str
    error_summary: str

    def to_dict(self) -> dict[str, object]:
        return {
            "relative_path": self.relative_path,
            "error_type": self.error_type,
            "error_summary": self.error_summary,
        }


@dataclass(frozen=True, slots=True)
class IncrementalPlan:
    source_root: Path
    source_package_version_key: str
    active_index_version_key: str
    active_source_package_version_key: str
    discovered_file_count: int
    active_document_count: int
    index_candidate_file_count: int
    added_files: tuple[IncrementalPlanFile, ...]
    modified_files: tuple[IncrementalPlanFile, ...]
    deleted_files: tuple[IncrementalPlanFile, ...]
    unchanged_files: tuple[IncrementalPlanFile, ...]
    pending_files: tuple[IncrementalPlanIssue, ...]
    ignored_files: tuple[IncrementalPlanFile, ...]
    failed_files: tuple[IncrementalPlanIssue, ...]
    estimated_new_chunks: int
    estimated_reused_embeddings: int
    estimated_new_embeddings: int
    db_rows_to_activate: int
    db_rows_to_deactivate: int

    @property
    def ready_for_incremental_build(self) -> bool:
        return not self.failed_files

    @property
    def counts(self) -> dict[str, int]:
        return {
            "discovered_files": self.discovered_file_count,
            "active_documents": self.active_document_count,
            "index_candidate_files": self.index_candidate_file_count,
            "added_files": len(self.added_files),
            "modified_files": len(self.modified_files),
            "deleted_files": len(self.deleted_files),
            "unchanged_files": len(self.unchanged_files),
            "pending_files": len(self.pending_files),
            "ignored_files": len(self.ignored_files),
            "failed_files": len(self.failed_files),
            "estimated_new_chunks": self.estimated_new_chunks,
            "estimated_reused_embeddings": self.estimated_reused_embeddings,
            "estimated_new_embeddings": self.estimated_new_embeddings,
            "db_rows_to_activate": self.db_rows_to_activate,
            "db_rows_to_deactivate": self.db_rows_to_deactivate,
        }

    def to_dict(self) -> dict[str, object]:
        return {
            "source_root": str(self.source_root),
            "source_package_version_key": self.source_package_version_key,
            "active_index_version_key": self.active_index_version_key,
            "active_source_package_version_key": self.active_source_package_version_key,
            "ready_for_incremental_build": self.ready_for_incremental_build,
            "counts": self.counts,
            "added_files": [item.to_dict() for item in self.added_files],
            "modified_files": [item.to_dict() for item in self.modified_files],
            "deleted_files": [item.to_dict() for item in self.deleted_files],
            "unchanged_files": [item.to_dict() for item in self.unchanged_files],
            "pending_files": [item.to_dict() for item in self.pending_files],
            "ignored_files": [item.to_dict() for item in self.ignored_files],
            "failed_files": [item.to_dict() for item in self.failed_files],
        }


def build_incremental_plan(
    source_root: Path | str,
    *,
    active_documents: tuple[ActiveSourceDocument, ...],
    active_index_version_key: str,
    active_source_package_version_key: str,
    package_version_key: str | None = None,
) -> IncrementalPlan:
    previous_snapshot = ManifestIndexSnapshot(
        package_version_key=active_source_package_version_key,
        files_by_path={
            document.relative_path: _file_index_state(document) for document in active_documents
        },
    )
    run_result = KnowledgeIndexPipeline().run_incremental(
        source_root,
        previous_snapshot=previous_snapshot,
        package_version_key=package_version_key,
    )
    if run_result.diff is None:
        raise IncrementalPlanError("incremental pipeline did not return a diff")

    active_by_path = {document.relative_path: document for document in active_documents}
    modified_paths = {file.relative_path for file in run_result.diff.modified}
    deleted_paths = {file.relative_path for file in run_result.diff.deleted}
    reused_embeddings = sum(
        active_by_path[file.relative_path].chunk_count
        for file in run_result.diff.unchanged
        if file.relative_path in active_by_path
    )
    rows_to_deactivate = sum(
        active_by_path[path].chunk_count
        for path in modified_paths | deleted_paths
        if path in active_by_path
    )
    new_chunks = run_result.summary.chunk_count
    return IncrementalPlan(
        source_root=Path(source_root),
        source_package_version_key=run_result.summary.source_package_version_key,
        active_index_version_key=active_index_version_key,
        active_source_package_version_key=active_source_package_version_key,
        discovered_file_count=run_result.summary.discovered_file_count,
        active_document_count=len(active_documents),
        index_candidate_file_count=run_result.summary.index_candidate_file_count,
        added_files=tuple(_current_file(file) for file in run_result.diff.added),
        modified_files=tuple(_current_file(file) for file in run_result.diff.modified),
        deleted_files=tuple(
            _active_file(active_by_path[file.relative_path]) for file in run_result.diff.deleted
        ),
        unchanged_files=tuple(
            _active_file(active_by_path[file.relative_path])
            for file in run_result.diff.unchanged
            if file.relative_path in active_by_path
        ),
        pending_files=tuple(_issue(issue) for issue in run_result.pending_files),
        ignored_files=tuple(
            _current_file(file)
            for file in run_result.snapshot.files_by_path.values()
            if file.status == DocumentStatus.IGNORED
        ),
        failed_files=tuple(_issue(issue) for issue in run_result.failed_files),
        estimated_new_chunks=new_chunks,
        estimated_reused_embeddings=reused_embeddings,
        estimated_new_embeddings=new_chunks,
        db_rows_to_activate=reused_embeddings + new_chunks,
        db_rows_to_deactivate=rows_to_deactivate,
    )


def build_incremental_plan_from_database(
    *,
    source_root: Path | str,
    database_url: str,
    package_version_key: str | None = None,
) -> IncrementalPlan:
    active = load_active_source_documents(database_url)
    return build_incremental_plan(
        source_root,
        active_documents=active.documents,
        active_index_version_key=active.index_version_key,
        active_source_package_version_key=active.source_package_version_key,
        package_version_key=package_version_key,
    )


def render_incremental_plan_markdown(plan: IncrementalPlan) -> str:
    report_date = datetime.now(UTC).date().isoformat()
    status = "PASS" if plan.ready_for_incremental_build else "FAIL"
    lines = [
        "---",
        "title: 知识库增量更新计划报告",
        "doc_type: analysis",
        "module: knowledge-query-engine",
        "topic: incremental-plan",
        "status: draft",
        f"created: {report_date}",
        f"updated: {report_date}",
        "owner: self",
        "source: ai",
        "---",
        "",
        "# 知识库增量更新计划报告",
        "",
        f"总体状态：`{status}`",
        "",
        "## 1. 版本信息",
        "",
        "| 字段 | 值 |",
        "| --- | --- |",
        f"| `source_root` | `{plan.source_root}` |",
        f"| `source_package_version_key` | `{plan.source_package_version_key}` |",
        f"| `active_index_version_key` | `{plan.active_index_version_key}` |",
        f"| `active_source_package_version_key` | `{plan.active_source_package_version_key}` |",
        "",
        "## 2. 影响计数",
        "",
        "| 指标 | 数值 |",
        "| --- | ---: |",
    ]
    for key, value in plan.counts.items():
        lines.append(f"| `{key}` | {value} |")

    lines.extend(
        [
            "",
            "## 3. 文件样例",
            "",
            "### 新增文件",
            *_file_lines(plan.added_files),
            "",
            "### 修改文件",
            *_file_lines(plan.modified_files),
            "",
            "### 删除文件",
            *_file_lines(plan.deleted_files),
            "",
            "### 待处理文件",
            *_issue_lines(plan.pending_files),
            "",
            "### 失败文件",
            *_issue_lines(plan.failed_files),
            "",
            "## 4. 下一步",
            "",
            _next_step_line(plan),
        ]
    )
    return "\n".join(lines) + "\n"


@dataclass(frozen=True, slots=True)
class _ActiveIndexDocuments:
    index_version_key: str
    source_package_version_key: str
    documents: tuple[ActiveSourceDocument, ...]


def load_active_source_documents(database_url: str) -> _ActiveIndexDocuments:
    import psycopg

    with (
        psycopg.connect(_normalize_psycopg_database_url(database_url)) as connection,
        connection.cursor() as cursor,
    ):
        cursor.execute(ACTIVE_INDEX_QUERY)
        active_rows = cursor.fetchall()
        if not active_rows:
            raise IncrementalPlanError("no active index version found in database")
        if len(active_rows) > 1:
            raise IncrementalPlanError(f"multiple active index versions found: {len(active_rows)}")
        index_version_key, source_package_version_key, source_package_id = active_rows[0]
        cursor.execute(ACTIVE_DOCUMENTS_QUERY, (source_package_id,))
        documents = tuple(_active_document(row) for row in cursor.fetchall())
    return _ActiveIndexDocuments(
        index_version_key=str(index_version_key),
        source_package_version_key=str(source_package_version_key),
        documents=documents,
    )


def _file_index_state(document: ActiveSourceDocument) -> FileIndexState:
    source_collection = _source_collection_or_none(document.source_collection)
    return FileIndexState(
        relative_path=document.relative_path,
        sha256=document.sha256,
        status=DocumentStatus.INDEX_CANDIDATE,
        source_collection=source_collection,
        file_ext=document.file_ext,
        size_bytes=document.size_bytes,
    )


def _active_document(row: tuple[object, ...]) -> ActiveSourceDocument:
    relative_path, sha256, source_collection, file_ext, size_bytes, chunk_count = row
    return ActiveSourceDocument(
        relative_path=str(relative_path),
        sha256=str(sha256),
        source_collection=str(source_collection),
        file_ext=str(file_ext),
        size_bytes=_int_value(size_bytes),
        chunk_count=_int_value(chunk_count),
    )


def _active_file(document: ActiveSourceDocument) -> IncrementalPlanFile:
    return IncrementalPlanFile(
        relative_path=document.relative_path,
        sha256=document.sha256,
        source_collection=document.source_collection,
        file_ext=document.file_ext,
        size_bytes=document.size_bytes,
        chunk_count=document.chunk_count,
    )


def _current_file(file: FileIndexState) -> IncrementalPlanFile:
    return IncrementalPlanFile(
        relative_path=file.relative_path,
        sha256=file.sha256,
        source_collection=file.source_collection.value if file.source_collection else None,
        file_ext=file.file_ext,
        size_bytes=file.size_bytes,
        reason=file.reason,
    )


def _issue(issue: PipelineFileIssue) -> IncrementalPlanIssue:
    return IncrementalPlanIssue(
        relative_path=issue.relative_path,
        error_type=issue.error_type.value,
        error_summary=issue.error_summary,
    )


def _source_collection_or_none(value: str) -> SourceCollection | None:
    try:
        return SourceCollection(value)
    except ValueError:
        return None


def _file_lines(files: tuple[IncrementalPlanFile, ...]) -> list[str]:
    if not files:
        return ["- 无"]
    return [
        (
            f"- `{item.relative_path}`"
            f" (`{item.source_collection or 'unknown'}`, `{item.file_ext}`"
            f"{', chunks=' + str(item.chunk_count) if item.chunk_count is not None else ''})"
        )
        for item in files[:DEFAULT_MAX_SAMPLE_ITEMS]
    ]


def _issue_lines(issues: tuple[IncrementalPlanIssue, ...]) -> list[str]:
    if not issues:
        return ["- 无"]
    return [
        f"- `{item.relative_path}` (`{item.error_type}`): {item.error_summary}"
        for item in issues[:DEFAULT_MAX_SAMPLE_ITEMS]
    ]


def _next_step_line(plan: IncrementalPlan) -> str:
    if not plan.ready_for_incremental_build:
        return "结论：增量计划存在失败文件。先修复失败项，不允许进入增量构建。"
    if plan.added_files or plan.modified_files or plan.deleted_files:
        return (
            "结论：增量计划可执行。下一步构建 candidate index version，并在通过评测后切换 active。"
        )
    return "结论：未发现索引候选文件变化。无需执行增量构建。"


def _int_value(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    raise IncrementalPlanError(f"expected integer value, got {value!r}")


def _normalize_psycopg_database_url(database_url: str) -> str:
    return database_url.replace("postgresql+psycopg://", "postgresql://", 1)


def incremental_plan_json(plan: IncrementalPlan) -> str:
    return json.dumps(plan.to_dict(), ensure_ascii=False, indent=2) + "\n"


ACTIVE_INDEX_QUERY = """
SELECT iv.version_key, spv.version_key, spv.id
FROM index_versions iv
JOIN source_package_versions spv ON spv.id = iv.source_package_version_id
WHERE iv.status = 'active'
ORDER BY iv.activated_at DESC NULLS LAST, iv.created_at DESC
"""

ACTIVE_DOCUMENTS_QUERY = """
SELECT
    sd.relative_path,
    sd.sha256,
    sd.source_collection,
    sd.file_ext,
    sd.size_bytes,
    COUNT(dc.id)::int AS chunk_count
FROM source_documents sd
LEFT JOIN document_chunks dc ON dc.source_document_id = sd.id
WHERE sd.source_package_version_id = %s
  AND sd.status = 'indexed'
GROUP BY
    sd.relative_path,
    sd.sha256,
    sd.source_collection,
    sd.file_ext,
    sd.size_bytes
ORDER BY sd.relative_path
"""
