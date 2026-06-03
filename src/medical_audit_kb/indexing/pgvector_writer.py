from __future__ import annotations

import hashlib
import json
import mimetypes
import os
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from uuid import UUID, uuid5

from psycopg.types.json import Jsonb

from medical_audit_kb.indexing.persistent_index import (
    CHUNKS_FILE,
    EMBEDDINGS_FILE,
    FAILED_FILES_FILE,
    PENDING_FILES_FILE,
)
from medical_audit_kb.indexing.pgvector_import import (
    DEFAULT_SCHEMA_DIMENSION,
    PgvectorImportPlan,
    build_pgvector_import_plan,
)

SOURCE_PACKAGE_NAMESPACE = UUID("2fd47077-7bb1-4c22-a6e2-c5e34136e213")
SOURCE_DOCUMENT_NAMESPACE = UUID("df83805c-e7df-432d-9f2a-a11b42d6141c")
INDEX_VERSION_NAMESPACE = UUID("86ac5b05-8e07-43b5-9991-c98f2fc33e5c")
INDEX_JOB_NAMESPACE = UUID("a44d5c5e-3b71-4a88-a3f6-d538fdfb19aa")
QUEUE_FILE_NAMESPACE = UUID("489b1e69-5132-43bf-9837-b780ee5de7f7")
DEFAULT_BATCH_SIZE = 500
DEFAULT_MAX_ISSUE_SAMPLES = 20
ALLOWED_INDEX_VERSION_WRITE_STATUSES = frozenset({"candidate", "active"})

SqlParams = tuple[object, ...]


class PgvectorImportCursor(Protocol):
    def execute(self, query: str, params: SqlParams | None = None) -> object:
        pass

    def executemany(self, query: str, params_seq: Sequence[SqlParams]) -> object:
        pass


@dataclass(frozen=True, slots=True)
class SourceDocumentImportRow:
    id: UUID
    source_collection: str
    relative_path: str
    absolute_path: str
    file_name: str
    file_ext: str
    media_type: str
    sha256: str
    size_bytes: int
    metadata: dict[str, object]


@dataclass(frozen=True, slots=True)
class PgvectorImportManifest:
    index_root: Path
    source_root: Path
    plan: PgvectorImportPlan
    source_package_id: UUID | None
    index_version_id: UUID | None
    source_document_count: int
    document_chunk_count: int
    chunk_embedding_count: int
    failed_file_count: int
    pending_file_count: int
    source_file_missing_count: int
    invalid_source_metadata_count: int
    issue_samples: tuple[str, ...]

    @property
    def ready_for_write(self) -> bool:
        return (
            self.plan.ready_for_import
            and self.source_package_id is not None
            and self.index_version_id is not None
            and self.source_file_missing_count == 0
            and self.invalid_source_metadata_count == 0
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "index_root": str(self.index_root),
            "source_root": str(self.source_root),
            "source_package_id": str(self.source_package_id) if self.source_package_id else None,
            "index_version_id": str(self.index_version_id) if self.index_version_id else None,
            "source_document_count": self.source_document_count,
            "document_chunk_count": self.document_chunk_count,
            "chunk_embedding_count": self.chunk_embedding_count,
            "failed_file_count": self.failed_file_count,
            "pending_file_count": self.pending_file_count,
            "source_file_missing_count": self.source_file_missing_count,
            "invalid_source_metadata_count": self.invalid_source_metadata_count,
            "ready_for_write": self.ready_for_write,
            "issue_samples": list(self.issue_samples),
            "plan": self.plan.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class PgvectorImportExecutionResult:
    manifest: PgvectorImportManifest
    mode: str
    executed: bool
    success: bool
    batch_size: int
    database_url_env: str | None
    index_version_status: str

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "executed": self.executed,
            "success": self.success,
            "batch_size": self.batch_size,
            "database_url_env": self.database_url_env,
            "index_version_status": self.index_version_status,
            "manifest": self.manifest.to_dict(),
        }


def build_pgvector_import_manifest(
    index_root: Path | str,
    source_root: Path | str,
    *,
    schema_dimension: int = DEFAULT_SCHEMA_DIMENSION,
    max_issue_samples: int = DEFAULT_MAX_ISSUE_SAMPLES,
) -> PgvectorImportManifest:
    root = Path(index_root)
    source = Path(source_root)
    plan = build_pgvector_import_plan(root, schema_dimension=schema_dimension)
    summary = plan.summary
    source_package_version_key = _summary_str(summary, "source_package_version_key")
    index_version_key = _summary_str(summary, "index_version_key")
    source_package_id = (
        uuid5(SOURCE_PACKAGE_NAMESPACE, source_package_version_key)
        if source_package_version_key
        else None
    )
    index_version_id = (
        uuid5(INDEX_VERSION_NAMESPACE, index_version_key) if index_version_key else None
    )
    issue_samples: list[str] = []
    if source_package_version_key is None:
        issue_samples.append("summary.source_package_version_key is missing")
    if index_version_key is None:
        issue_samples.append("summary.index_version_key is missing")
    if not source.exists():
        issue_samples.append(f"source root not found: {source}")

    source_documents = _prepare_source_document_rows(
        root / CHUNKS_FILE,
        source_root=source,
        source_package_version_key=source_package_version_key,
        issue_samples=issue_samples,
        max_issue_samples=max_issue_samples,
    )
    return PgvectorImportManifest(
        index_root=root,
        source_root=source,
        plan=plan,
        source_package_id=source_package_id,
        index_version_id=index_version_id,
        source_document_count=len(source_documents.rows),
        document_chunk_count=plan.chunk_row_count or 0,
        chunk_embedding_count=plan.embedding_row_count or 0,
        failed_file_count=plan.failed_file_row_count or 0,
        pending_file_count=plan.pending_file_row_count or 0,
        source_file_missing_count=source_documents.missing_file_count,
        invalid_source_metadata_count=source_documents.invalid_metadata_count,
        issue_samples=tuple(issue_samples[:max_issue_samples]),
    )


def run_pgvector_import(
    index_root: Path | str,
    source_root: Path | str,
    *,
    execute: bool,
    database_url: str | None = None,
    database_url_env: str | None = None,
    schema_dimension: int = DEFAULT_SCHEMA_DIMENSION,
    batch_size: int = DEFAULT_BATCH_SIZE,
    index_version_status: str = "candidate",
) -> PgvectorImportExecutionResult:
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    _validate_index_version_status(index_version_status)
    manifest = build_pgvector_import_manifest(
        index_root,
        source_root,
        schema_dimension=schema_dimension,
    )
    if not execute:
        return PgvectorImportExecutionResult(
            manifest=manifest,
            mode="dry-run",
            executed=False,
            success=manifest.ready_for_write,
            batch_size=batch_size,
            database_url_env=database_url_env,
            index_version_status=index_version_status,
        )
    if not manifest.ready_for_write:
        return PgvectorImportExecutionResult(
            manifest=manifest,
            mode="execute",
            executed=False,
            success=False,
            batch_size=batch_size,
            database_url_env=database_url_env,
            index_version_status=index_version_status,
        )
    resolved_database_url = database_url or _database_url_from_env(database_url_env)
    if resolved_database_url is None:
        raise ValueError("database_url is required when execute is true")
    _write_with_psycopg(
        manifest,
        database_url=_normalize_psycopg_database_url(resolved_database_url),
        batch_size=batch_size,
        index_version_status=index_version_status,
    )
    return PgvectorImportExecutionResult(
        manifest=manifest,
        mode="execute",
        executed=True,
        success=True,
        batch_size=batch_size,
        database_url_env=database_url_env,
        index_version_status=index_version_status,
    )


def write_pgvector_import_to_cursor(
    cursor: PgvectorImportCursor,
    manifest: PgvectorImportManifest,
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
    index_version_status: str = "candidate",
) -> None:
    _validate_index_version_status(index_version_status)
    if not manifest.ready_for_write:
        raise ValueError("pgvector import manifest is not ready for write")
    if manifest.source_package_id is None or manifest.index_version_id is None:
        raise ValueError("manifest identifiers are missing")
    summary = manifest.plan.summary
    source_package_version_key = _required_summary_str(summary, "source_package_version_key")
    index_version_key = _required_summary_str(summary, "index_version_key")
    cursor.execute(
        SOURCE_PACKAGE_UPSERT_SQL,
        (
            manifest.source_package_id,
            source_package_version_key,
            str(manifest.source_root),
            "Imported from persistent JSONL artifact.",
            Jsonb(summary),
        ),
    )
    _write_source_documents(cursor, manifest, batch_size=batch_size)
    _write_document_chunks(cursor, manifest, batch_size=batch_size)
    _write_chunk_embeddings(cursor, manifest, batch_size=batch_size)
    cursor.execute(
        INDEX_VERSION_UPSERT_SQL,
        (
            manifest.index_version_id,
            manifest.source_package_id,
            index_version_key,
            index_version_status,
            str(manifest.index_root / "bm25_documents.jsonl"),
            manifest.plan.expected_embedding_provider,
            manifest.plan.expected_embedding_model,
            manifest.document_chunk_count,
            manifest.source_document_count,
            Jsonb(summary),
            _activated_at_for_status(index_version_status),
        ),
    )
    cursor.execute(
        INDEX_JOB_UPSERT_SQL,
        (
            uuid5(INDEX_JOB_NAMESPACE, f"{index_version_key}:pgvector-import"),
            manifest.index_version_id,
            str(summary.get("job_type") or "full-rebuild"),
            "succeeded",
            Jsonb({"import": manifest.to_dict()}),
        ),
    )
    _write_failed_files(cursor, manifest, batch_size=batch_size)
    _write_pending_files(cursor, manifest, batch_size=batch_size)


def render_pgvector_import_execution_markdown(
    result: PgvectorImportExecutionResult,
) -> str:
    report_date = datetime.now(UTC).date().isoformat()
    status = "PASS" if result.success else "FAIL"
    manifest = result.manifest
    lines = [
        "---",
        "title: 知识库 pgvector 受控导入报告",
        "doc_type: analysis",
        "module: knowledge-query-engine",
        "topic: pgvector-import",
        "status: draft",
        f"created: {report_date}",
        f"updated: {report_date}",
        "owner: self",
        "source: ai",
        "---",
        "",
        "# 知识库 pgvector 受控导入报告",
        "",
        f"总体状态：`{status}`",
        "",
        "## 1. 运行配置",
        "",
        "| 配置 | 值 |",
        "| --- | --- |",
        f"| `mode` | `{result.mode}` |",
        f"| `executed` | `{result.executed}` |",
        f"| `index_root` | `{manifest.index_root}` |",
        f"| `source_root` | `{manifest.source_root}` |",
        f"| `batch_size` | `{result.batch_size}` |",
        f"| `index_version_status` | `{result.index_version_status}` |",
        "",
        "## 2. 写入准备指标",
        "",
        "| 指标 | 数值 |",
        "| --- | ---: |",
        f"| `ready_for_import` | `{manifest.plan.ready_for_import}` |",
        f"| `ready_for_write` | `{manifest.ready_for_write}` |",
        f"| `source_document_count` | {manifest.source_document_count} |",
        f"| `document_chunk_count` | {manifest.document_chunk_count} |",
        f"| `chunk_embedding_count` | {manifest.chunk_embedding_count} |",
        f"| `failed_file_count` | {manifest.failed_file_count} |",
        f"| `pending_file_count` | {manifest.pending_file_count} |",
        f"| `source_file_missing_count` | {manifest.source_file_missing_count} |",
        f"| `invalid_source_metadata_count` | {manifest.invalid_source_metadata_count} |",
        "",
        "## 3. 问题样例",
        "",
    ]
    if not manifest.issue_samples:
        lines.append("- 无")
    else:
        lines.extend(f"- {sample}" for sample in manifest.issue_samples)
    lines.extend(["", "## 4. 下一步", "", _next_step_line(result)])
    return "\n".join(lines) + "\n"


@dataclass(frozen=True, slots=True)
class _SourceDocumentRows:
    rows: tuple[SourceDocumentImportRow, ...]
    missing_file_count: int
    invalid_metadata_count: int


def _write_with_psycopg(
    manifest: PgvectorImportManifest,
    *,
    database_url: str,
    batch_size: int,
    index_version_status: str,
) -> None:
    import psycopg

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            write_pgvector_import_to_cursor(
                cursor,
                manifest,
                batch_size=batch_size,
                index_version_status=index_version_status,
            )
        connection.commit()


def _write_source_documents(
    cursor: PgvectorImportCursor,
    manifest: PgvectorImportManifest,
    *,
    batch_size: int,
) -> None:
    rows = _prepare_source_document_rows(
        manifest.index_root / CHUNKS_FILE,
        source_root=manifest.source_root,
        source_package_version_key=_required_summary_str(
            manifest.plan.summary,
            "source_package_version_key",
        ),
        issue_samples=[],
        max_issue_samples=0,
    ).rows
    for batch in _batches(rows, batch_size):
        cursor.executemany(
            SOURCE_DOCUMENT_UPSERT_SQL,
            tuple(
                (
                    row.id,
                    manifest.source_package_id,
                    row.source_collection,
                    row.relative_path,
                    row.absolute_path,
                    row.file_name,
                    row.file_ext,
                    row.media_type,
                    row.sha256,
                    row.size_bytes,
                    "indexed",
                    Jsonb(row.metadata),
                )
                for row in batch
            ),
        )


def _write_document_chunks(
    cursor: PgvectorImportCursor,
    manifest: PgvectorImportManifest,
    *,
    batch_size: int,
) -> None:
    source_package_version_key = _required_summary_str(
        manifest.plan.summary,
        "source_package_version_key",
    )
    rows: list[SqlParams] = []
    source_path_indexes: dict[str, int] = {}
    for row in _read_jsonl(manifest.index_root / CHUNKS_FILE):
        source_path = _source_path_from_chunk(row)
        chunk_index = source_path_indexes.get(source_path, 0)
        source_path_indexes[source_path] = chunk_index + 1
        metadata = _object_dict(row.get("metadata"))
        locator = _object_dict(row.get("locator")) or _object_dict(metadata.get("locator"))
        rows.append(
            (
                UUID(str(row["chunk_id"])),
                _source_document_id(source_package_version_key, source_path),
                chunk_index,
                str(row["text"]),
                Jsonb(_string_list(metadata.get("title_path"))),
                _optional_str(metadata.get("article_number")),
                _optional_int(metadata.get("page_number")),
                _optional_int(metadata.get("line_start")),
                _optional_int(metadata.get("line_end")),
                _optional_str(metadata.get("sheet_name")),
                _optional_int(metadata.get("row_number")),
                None,
                Jsonb(locator),
                Jsonb(metadata),
            )
        )
        if len(rows) >= batch_size:
            cursor.executemany(DOCUMENT_CHUNK_UPSERT_SQL, tuple(rows))
            rows.clear()
    if rows:
        cursor.executemany(DOCUMENT_CHUNK_UPSERT_SQL, tuple(rows))


def _write_chunk_embeddings(
    cursor: PgvectorImportCursor,
    manifest: PgvectorImportManifest,
    *,
    batch_size: int,
) -> None:
    rows: list[SqlParams] = []
    for row in _read_jsonl(manifest.index_root / EMBEDDINGS_FILE):
        rows.append(
            (
                UUID(str(row["chunk_id"])),
                str(row["provider"]),
                str(row["model_name"]),
                str(row["provider_version"]),
                _required_int(row, "dimension"),
                _vector_literal(row["embedding"]),
            )
        )
        if len(rows) >= batch_size:
            cursor.executemany(CHUNK_EMBEDDING_UPSERT_SQL, tuple(rows))
            rows.clear()
    if rows:
        cursor.executemany(CHUNK_EMBEDDING_UPSERT_SQL, tuple(rows))


def _write_failed_files(
    cursor: PgvectorImportCursor,
    manifest: PgvectorImportManifest,
    *,
    batch_size: int,
) -> None:
    rows: list[SqlParams] = []
    package_key = _required_summary_str(manifest.plan.summary, "source_package_version_key")
    for row in _read_jsonl(manifest.index_root / FAILED_FILES_FILE):
        relative_path = str(row["relative_path"])
        rows.append(
            (
                uuid5(QUEUE_FILE_NAMESPACE, f"{package_key}:failed:{relative_path}"),
                manifest.source_package_id,
                None,
                relative_path,
                str(row.get("error_type") or "validation-failed"),
                str(row.get("error_summary") or "unknown"),
                0,
                "open",
            )
        )
        if len(rows) >= batch_size:
            cursor.executemany(FAILED_FILE_UPSERT_SQL, tuple(rows))
            rows.clear()
    if rows:
        cursor.executemany(FAILED_FILE_UPSERT_SQL, tuple(rows))


def _write_pending_files(
    cursor: PgvectorImportCursor,
    manifest: PgvectorImportManifest,
    *,
    batch_size: int,
) -> None:
    rows: list[SqlParams] = []
    package_key = _required_summary_str(manifest.plan.summary, "source_package_version_key")
    for row in _read_jsonl(manifest.index_root / PENDING_FILES_FILE):
        relative_path = str(row["relative_path"])
        rows.append(
            (
                uuid5(QUEUE_FILE_NAMESPACE, f"{package_key}:pending:{relative_path}"),
                manifest.source_package_id,
                relative_path,
                str(row.get("error_summary") or row.get("error_type") or "pending"),
                "open",
                Jsonb(row),
            )
        )
        if len(rows) >= batch_size:
            cursor.executemany(PENDING_FILE_UPSERT_SQL, tuple(rows))
            rows.clear()
    if rows:
        cursor.executemany(PENDING_FILE_UPSERT_SQL, tuple(rows))


def _prepare_source_document_rows(
    chunks_path: Path,
    *,
    source_root: Path,
    source_package_version_key: str | None,
    issue_samples: list[str],
    max_issue_samples: int,
) -> _SourceDocumentRows:
    rows: dict[str, SourceDocumentImportRow] = {}
    missing_source_paths: set[str] = set()
    invalid_metadata_paths: set[str] = set()
    for row in _read_jsonl(chunks_path):
        source_path = _source_path_from_chunk(row)
        if (
            source_path in rows
            or source_path in missing_source_paths
            or source_path in invalid_metadata_paths
        ):
            continue
        metadata = _object_dict(row.get("metadata"))
        source_collection = _optional_str(metadata.get("source_collection"))
        if source_collection is None:
            invalid_metadata_paths.add(source_path)
            _append_issue(
                issue_samples,
                max_issue_samples,
                f"missing source_collection: {source_path}",
            )
            continue
        source_file = source_root / source_path
        if not source_file.exists() or not source_file.is_file():
            missing_source_paths.add(source_path)
            _append_issue(issue_samples, max_issue_samples, f"source file not found: {source_file}")
            continue
        if source_package_version_key is None:
            invalid_metadata_paths.add(source_path)
            continue
        rows[source_path] = SourceDocumentImportRow(
            id=_source_document_id(source_package_version_key, source_path),
            source_collection=source_collection,
            relative_path=source_path,
            absolute_path=str(source_file),
            file_name=source_file.name,
            file_ext=source_file.suffix.lower() or ".unknown",
            media_type=_media_type_for(source_file),
            sha256=_sha256_file(source_file),
            size_bytes=source_file.stat().st_size,
            metadata={
                "import_source": "persistent-jsonl",
                "index_root": str(chunks_path.parent),
            },
        )
    return _SourceDocumentRows(
        rows=tuple(rows[path] for path in sorted(rows)),
        missing_file_count=len(missing_source_paths),
        invalid_metadata_count=len(invalid_metadata_paths),
    )


def _source_document_id(source_package_version_key: str, relative_path: str) -> UUID:
    return uuid5(SOURCE_DOCUMENT_NAMESPACE, f"{source_package_version_key}:{relative_path}")


def _source_path_from_chunk(row: dict[str, object]) -> str:
    metadata = _object_dict(row.get("metadata"))
    locator = _object_dict(row.get("locator")) or _object_dict(metadata.get("locator"))
    source_path = (
        row.get("source_path") or metadata.get("source_path") or locator.get("source_path")
    )
    if not isinstance(source_path, str) or not source_path:
        raise ValueError("chunk row missing source_path")
    return source_path


def _read_jsonl(path: Path) -> Iterator[dict[str, object]]:
    with path.open(encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"jsonl row must be object: {path}")
            yield dict(payload)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _media_type_for(path: Path) -> str:
    guessed_type, _encoding = mimetypes.guess_type(path.name)
    if guessed_type:
        return guessed_type
    if path.suffix.lower() in {".md", ".txt"}:
        return "text/plain"
    return "application/octet-stream"


def _database_url_from_env(database_url_env: str | None) -> str | None:
    if database_url_env is None:
        return None
    value = os.getenv(database_url_env)
    return value if value else None


def _normalize_psycopg_database_url(database_url: str) -> str:
    return database_url.replace("postgresql+psycopg://", "postgresql://", 1)


def _summary_str(summary: dict[str, object], key: str) -> str | None:
    value = summary.get(key)
    return value if isinstance(value, str) and value else None


def _required_summary_str(summary: dict[str, object], key: str) -> str:
    value = _summary_str(summary, key)
    if value is None:
        raise ValueError(f"summary.{key} is required")
    return value


def _required_int(row: dict[str, object], key: str) -> int:
    value = row.get(key)
    if not isinstance(value, int):
        raise ValueError(f"{key} must be an integer")
    return value


def _object_dict(value: object) -> dict[str, object]:
    return dict(value) if isinstance(value, dict) else {}


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _vector_literal(value: object) -> str:
    if not isinstance(value, list):
        raise ValueError("embedding must be a list")
    return "[" + ",".join(format(float(item), ".9g") for item in value) + "]"


def _append_issue(samples: list[str], max_issue_samples: int, issue: str) -> None:
    if len(samples) < max_issue_samples:
        samples.append(issue)


def _batches(
    rows: Sequence[SourceDocumentImportRow],
    batch_size: int,
) -> Iterator[tuple[SourceDocumentImportRow, ...]]:
    for index in range(0, len(rows), batch_size):
        yield tuple(rows[index : index + batch_size])


def _next_step_line(result: PgvectorImportExecutionResult) -> str:
    if result.executed and result.success:
        if result.index_version_status == "candidate":
            return "结论：candidate 版本已写入。下一步运行评测，通过后执行 `index-activate`。"
        return "结论：active 版本已写入。下一步重新加载检索后端并运行 UI smoke。"
    if result.success:
        return "结论：dry-run 已通过。下一步在确认数据库连接和备份后添加 `--execute` 执行写入。"
    return "结论：写入前检查未通过。先修复问题样例和失败门禁，不允许添加 `--execute`。"


def _validate_index_version_status(status: str) -> None:
    if status not in ALLOWED_INDEX_VERSION_WRITE_STATUSES:
        allowed = ", ".join(sorted(ALLOWED_INDEX_VERSION_WRITE_STATUSES))
        raise ValueError(f"index_version_status must be one of: {allowed}")


def _activated_at_for_status(status: str) -> datetime | None:
    if status == "active":
        return datetime.now(UTC)
    return None


SOURCE_PACKAGE_UPSERT_SQL = """
INSERT INTO source_package_versions (id, version_key, source_root_path, description, metadata)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (version_key) DO UPDATE SET
    source_root_path = EXCLUDED.source_root_path,
    description = EXCLUDED.description,
    metadata = EXCLUDED.metadata
"""

SOURCE_DOCUMENT_UPSERT_SQL = """
INSERT INTO source_documents (
    id,
    source_package_version_id,
    source_collection,
    relative_path,
    absolute_path,
    file_name,
    file_ext,
    media_type,
    sha256,
    size_bytes,
    status,
    metadata
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (source_package_version_id, relative_path) DO UPDATE SET
    source_collection = EXCLUDED.source_collection,
    absolute_path = EXCLUDED.absolute_path,
    file_name = EXCLUDED.file_name,
    file_ext = EXCLUDED.file_ext,
    media_type = EXCLUDED.media_type,
    sha256 = EXCLUDED.sha256,
    size_bytes = EXCLUDED.size_bytes,
    status = EXCLUDED.status,
    metadata = EXCLUDED.metadata,
    updated_at = now()
"""

DOCUMENT_CHUNK_UPSERT_SQL = """
INSERT INTO document_chunks (
    id,
    source_document_id,
    chunk_index,
    text,
    title_path,
    article_number,
    page_number,
    line_start,
    line_end,
    sheet_name,
    row_number,
    token_count,
    locator,
    metadata
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (id) DO UPDATE SET
    source_document_id = EXCLUDED.source_document_id,
    chunk_index = EXCLUDED.chunk_index,
    text = EXCLUDED.text,
    title_path = EXCLUDED.title_path,
    article_number = EXCLUDED.article_number,
    page_number = EXCLUDED.page_number,
    line_start = EXCLUDED.line_start,
    line_end = EXCLUDED.line_end,
    sheet_name = EXCLUDED.sheet_name,
    row_number = EXCLUDED.row_number,
    token_count = EXCLUDED.token_count,
    locator = EXCLUDED.locator,
    metadata = EXCLUDED.metadata
"""

CHUNK_EMBEDDING_UPSERT_SQL = """
INSERT INTO chunk_embeddings (
    chunk_id,
    provider,
    model_name,
    provider_version,
    dimension,
    embedding
)
VALUES (%s, %s, %s, %s, %s, %s::vector)
ON CONFLICT (chunk_id, provider, model_name, provider_version) DO UPDATE SET
    dimension = EXCLUDED.dimension,
    embedding = EXCLUDED.embedding
"""

INDEX_VERSION_UPSERT_SQL = """
INSERT INTO index_versions (
    id,
    source_package_version_id,
    version_key,
    status,
    bm25_index_path,
    vector_provider,
    vector_model,
    chunk_count,
    document_count,
    metadata,
    activated_at
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (version_key) DO UPDATE SET
    source_package_version_id = EXCLUDED.source_package_version_id,
    status = EXCLUDED.status,
    bm25_index_path = EXCLUDED.bm25_index_path,
    vector_provider = EXCLUDED.vector_provider,
    vector_model = EXCLUDED.vector_model,
    chunk_count = EXCLUDED.chunk_count,
    document_count = EXCLUDED.document_count,
    metadata = EXCLUDED.metadata,
    activated_at = EXCLUDED.activated_at
"""

INDEX_JOB_UPSERT_SQL = """
INSERT INTO index_jobs (id, index_version_id, job_type, status, finished_at, summary)
VALUES (%s, %s, %s, %s, now(), %s)
ON CONFLICT (id) DO UPDATE SET
    index_version_id = EXCLUDED.index_version_id,
    job_type = EXCLUDED.job_type,
    status = EXCLUDED.status,
    finished_at = EXCLUDED.finished_at,
    summary = EXCLUDED.summary
"""

FAILED_FILE_UPSERT_SQL = """
INSERT INTO failed_files (
    id,
    source_package_version_id,
    source_document_id,
    relative_path,
    error_type,
    error_summary,
    retry_count,
    status
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (id) DO UPDATE SET
    error_type = EXCLUDED.error_type,
    error_summary = EXCLUDED.error_summary,
    retry_count = EXCLUDED.retry_count,
    status = EXCLUDED.status,
    updated_at = now()
"""

PENDING_FILE_UPSERT_SQL = """
INSERT INTO pending_files (
    id,
    source_package_version_id,
    relative_path,
    reason,
    status,
    metadata
)
VALUES (%s, %s, %s, %s, %s, %s)
ON CONFLICT (id) DO UPDATE SET
    reason = EXCLUDED.reason,
    status = EXCLUDED.status,
    metadata = EXCLUDED.metadata,
    updated_at = now()
"""
