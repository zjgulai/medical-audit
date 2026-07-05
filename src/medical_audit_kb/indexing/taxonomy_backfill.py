from __future__ import annotations

import csv
import os
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Protocol

from psycopg.types.json import Jsonb

DEFAULT_MANIFEST_CSV = "tmp/outputs/knowledge-base-taxonomy-manifest-latest.csv"
DEFAULT_TAXONOMY_VERSION = "knowledge-base-taxonomy-v1"

SqlParams = tuple[object, ...]


class TaxonomyBackfillCursor(Protocol):
    def execute(self, query: str, params: SqlParams | None = None) -> object:
        pass

    def fetchall(self) -> list[tuple[object, ...]]:
        pass


@dataclass(frozen=True, slots=True)
class TaxonomyBackfillItem:
    relative_path: str
    source_root_relative_path: str
    database_relative_path: str
    sha256: str
    primary_category: str
    secondary_category: str
    namespace_key: str
    namespace_confidence: str
    matched_terms: tuple[str, ...]
    extraction_status: str
    metadata_patch: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return {
            "relative_path": self.relative_path,
            "source_root_relative_path": self.source_root_relative_path,
            "database_relative_path": self.database_relative_path,
            "sha256": self.sha256,
            "primary_category": self.primary_category,
            "secondary_category": self.secondary_category,
            "namespace_key": self.namespace_key,
            "namespace_confidence": self.namespace_confidence,
            "matched_terms": list(self.matched_terms),
            "extraction_status": self.extraction_status,
            "metadata_patch": self.metadata_patch,
        }


@dataclass(frozen=True, slots=True)
class TaxonomyBackfillPlan:
    manifest_csv: Path
    taxonomy_version: str
    items: tuple[TaxonomyBackfillItem, ...]
    skipped_row_count: int

    @property
    def planned_document_count(self) -> int:
        return len(self.items)

    @property
    def counts_by_namespace(self) -> dict[str, int]:
        return dict(Counter(item.namespace_key for item in self.items).most_common())

    @property
    def ready_for_execute(self) -> bool:
        return self.planned_document_count > 0

    def to_dict(self) -> dict[str, object]:
        return {
            "manifest_csv": str(self.manifest_csv),
            "taxonomy_version": self.taxonomy_version,
            "planned_document_count": self.planned_document_count,
            "skipped_row_count": self.skipped_row_count,
            "ready_for_execute": self.ready_for_execute,
            "counts_by_namespace": self.counts_by_namespace,
            "items": [item.to_dict() for item in self.items],
        }


@dataclass(frozen=True, slots=True)
class TaxonomyBackfillExecutionResult:
    plan: TaxonomyBackfillPlan
    mode: str
    executed: bool
    success: bool
    database_url_env: str | None
    index_version_status: str
    index_version_key: str | None
    matched_document_count: int
    updated_document_count: int
    updated_chunk_count: int
    unmatched_items: tuple[TaxonomyBackfillItem, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "executed": self.executed,
            "success": self.success,
            "database_url_env": self.database_url_env,
            "index_version_status": self.index_version_status,
            "index_version_key": self.index_version_key,
            "matched_document_count": self.matched_document_count,
            "updated_document_count": self.updated_document_count,
            "updated_chunk_count": self.updated_chunk_count,
            "unmatched_document_count": len(self.unmatched_items),
            "unmatched_items": [item.to_dict() for item in self.unmatched_items],
            "plan": self.plan.to_dict(),
            "boundaries": {
                "database_write": self.executed,
                "embedding_rebuild": False,
                "provider_call": False,
                "index_activation": False,
            },
        }


def build_taxonomy_backfill_plan(
    manifest_csv: Path | str = DEFAULT_MANIFEST_CSV,
    *,
    taxonomy_version: str = DEFAULT_TAXONOMY_VERSION,
) -> TaxonomyBackfillPlan:
    manifest_path = Path(manifest_csv)
    rows = _read_manifest_rows(manifest_path)
    items: list[TaxonomyBackfillItem] = []
    skipped_count = 0
    for row in rows:
        if not _truthy(row.get("already_indexed")):
            skipped_count += 1
            continue
        source_root_relative_path = _required(row, "source_root_relative_path")
        extraction_status = _required(row, "extraction_status")
        database_relative_path = _database_relative_path(
            source_root_relative_path=source_root_relative_path,
            extraction_status=extraction_status,
        )
        item = TaxonomyBackfillItem(
            relative_path=_required(row, "relative_path"),
            source_root_relative_path=source_root_relative_path,
            database_relative_path=database_relative_path,
            sha256=_required(row, "sha256"),
            primary_category=_required(row, "primary_category"),
            secondary_category=_required(row, "secondary_category"),
            namespace_key=_required(row, "namespace_key"),
            namespace_confidence=_required(row, "namespace_confidence"),
            matched_terms=_terms(row.get("matched_terms", "")),
            extraction_status=extraction_status,
            metadata_patch={},
        )
        items.append(
            replace(
                item,
                metadata_patch=_metadata_patch(item, taxonomy_version=taxonomy_version),
            )
        )
    return TaxonomyBackfillPlan(
        manifest_csv=manifest_path,
        taxonomy_version=taxonomy_version,
        items=tuple(items),
        skipped_row_count=skipped_count,
    )


def run_taxonomy_backfill(
    manifest_csv: Path | str = DEFAULT_MANIFEST_CSV,
    *,
    execute: bool,
    database_url: str | None = None,
    database_url_env: str | None = None,
    taxonomy_version: str = DEFAULT_TAXONOMY_VERSION,
    index_version_status: str = "active",
    index_version_key: str | None = None,
) -> TaxonomyBackfillExecutionResult:
    _validate_index_version_status(index_version_status)
    plan = build_taxonomy_backfill_plan(manifest_csv, taxonomy_version=taxonomy_version)
    if not execute:
        return TaxonomyBackfillExecutionResult(
            plan=plan,
            mode="dry-run",
            executed=False,
            success=plan.ready_for_execute,
            database_url_env=database_url_env,
            index_version_status=index_version_status,
            index_version_key=index_version_key,
            matched_document_count=0,
            updated_document_count=0,
            updated_chunk_count=0,
            unmatched_items=(),
        )
    if not plan.ready_for_execute:
        return TaxonomyBackfillExecutionResult(
            plan=plan,
            mode="execute",
            executed=False,
            success=False,
            database_url_env=database_url_env,
            index_version_status=index_version_status,
            index_version_key=index_version_key,
            matched_document_count=0,
            updated_document_count=0,
            updated_chunk_count=0,
            unmatched_items=(),
        )
    resolved_database_url = database_url or _database_url_from_env(database_url_env)
    if resolved_database_url is None:
        raise ValueError("database_url is required when execute is true")
    counts = _write_with_psycopg(
        plan,
        database_url=_normalize_psycopg_database_url(resolved_database_url),
        index_version_status=index_version_status,
        index_version_key=index_version_key,
    )
    success = (
        counts.matched_document_count == plan.planned_document_count
        and counts.updated_document_count == plan.planned_document_count
        and not counts.unmatched_items
    )
    return TaxonomyBackfillExecutionResult(
        plan=plan,
        mode="execute",
        executed=True,
        success=success,
        database_url_env=database_url_env,
        index_version_status=index_version_status,
        index_version_key=index_version_key,
        matched_document_count=counts.matched_document_count,
        updated_document_count=counts.updated_document_count,
        updated_chunk_count=counts.updated_chunk_count,
        unmatched_items=counts.unmatched_items,
    )


def write_taxonomy_backfill_to_cursor(
    cursor: TaxonomyBackfillCursor,
    plan: TaxonomyBackfillPlan,
    *,
    index_version_status: str = "active",
    index_version_key: str | None = None,
) -> _BackfillWriteCounts:
    _validate_index_version_status(index_version_status)
    matched_document_count = 0
    updated_document_count = 0
    updated_chunk_count = 0
    unmatched_items: list[TaxonomyBackfillItem] = []
    for item in plan.items:
        document_ids = _update_source_document(
            cursor,
            item,
            index_version_status=index_version_status,
            index_version_key=index_version_key,
        )
        if not document_ids:
            unmatched_items.append(item)
            continue
        matched_document_count += 1
        updated_document_count += len(document_ids)
        updated_chunk_count += len(
            _update_document_chunks(
                cursor,
                item,
                index_version_status=index_version_status,
                index_version_key=index_version_key,
            )
        )
    return _BackfillWriteCounts(
        matched_document_count=matched_document_count,
        updated_document_count=updated_document_count,
        updated_chunk_count=updated_chunk_count,
        unmatched_items=tuple(unmatched_items),
    )


def render_taxonomy_backfill_markdown(result: TaxonomyBackfillExecutionResult) -> str:
    report_date = datetime.now().date().isoformat()
    status = "PASS" if result.success else "FAIL"
    plan = result.plan
    lines = [
        "---",
        "title: 知识库二级分类元数据回填报告",
        "doc_type: analysis",
        "module: knowledge-base-taxonomy",
        "topic: taxonomy-metadata-backfill",
        "status: draft",
        f"created: {report_date}",
        f"updated: {report_date}",
        "owner: self",
        "source: ai",
        "---",
        "",
        "# 知识库二级分类元数据回填报告",
        "",
        f"总体状态：`{status}`",
        "",
        "## 1. 运行边界",
        "",
        "| 字段 | 值 |",
        "| --- | --- |",
        f"| `mode` | `{result.mode}` |",
        f"| `executed` | `{result.executed}` |",
        f"| `database_write` | `{result.executed}` |",
        "| `embedding_rebuild` | `False` |",
        "| `provider_call` | `False` |",
        "| `index_activation` | `False` |",
        f"| `manifest_csv` | `{plan.manifest_csv}` |",
        f"| `taxonomy_version` | `{plan.taxonomy_version}` |",
        f"| `index_version_status` | `{result.index_version_status}` |",
        f"| `index_version_key` | `{result.index_version_key or ''}` |",
        "",
        "## 2. 影响计数",
        "",
        "| 指标 | 数值 |",
        "| --- | ---: |",
        f"| `planned_document_count` | {plan.planned_document_count} |",
        f"| `skipped_row_count` | {plan.skipped_row_count} |",
        f"| `matched_document_count` | {result.matched_document_count} |",
        f"| `updated_document_count` | {result.updated_document_count} |",
        f"| `updated_chunk_count` | {result.updated_chunk_count} |",
        f"| `unmatched_document_count` | {len(result.unmatched_items)} |",
        "",
        "## 3. Namespace 分布",
        "",
        "| namespace | 文档数 |",
        "| --- | ---: |",
    ]
    for namespace_key, count in plan.counts_by_namespace.items():
        lines.append(f"| `{namespace_key}` | {count} |")
    lines.extend(["", "## 4. 未匹配样例", ""])
    if not result.unmatched_items:
        lines.append("- 无")
    else:
        for item in result.unmatched_items[:20]:
            lines.append(f"- `{item.database_relative_path}` / `{item.sha256}`")
    lines.extend(["", "## 5. 下一步", "", _next_step_line(result)])
    return "\n".join(lines) + "\n"


@dataclass(frozen=True, slots=True)
class _BackfillWriteCounts:
    matched_document_count: int
    updated_document_count: int
    updated_chunk_count: int
    unmatched_items: tuple[TaxonomyBackfillItem, ...]


def _write_with_psycopg(
    plan: TaxonomyBackfillPlan,
    *,
    database_url: str,
    index_version_status: str,
    index_version_key: str | None,
) -> _BackfillWriteCounts:
    import psycopg

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            counts = write_taxonomy_backfill_to_cursor(
                cursor,
                plan,
                index_version_status=index_version_status,
                index_version_key=index_version_key,
            )
        connection.commit()
    return counts


def _update_source_document(
    cursor: TaxonomyBackfillCursor,
    item: TaxonomyBackfillItem,
    *,
    index_version_status: str,
    index_version_key: str | None,
) -> tuple[object, ...]:
    cursor.execute(
        SOURCE_DOCUMENT_TAXONOMY_UPDATE_SQL,
        (
            Jsonb(item.metadata_patch),
            index_version_status,
            index_version_key,
            index_version_key,
            item.database_relative_path,
            item.sha256,
        ),
    )
    return tuple(row[0] for row in cursor.fetchall())


def _update_document_chunks(
    cursor: TaxonomyBackfillCursor,
    item: TaxonomyBackfillItem,
    *,
    index_version_status: str,
    index_version_key: str | None,
) -> tuple[object, ...]:
    cursor.execute(
        DOCUMENT_CHUNK_TAXONOMY_UPDATE_SQL,
        (
            Jsonb(item.metadata_patch),
            index_version_status,
            index_version_key,
            index_version_key,
            item.database_relative_path,
            item.sha256,
        ),
    )
    return tuple(row[0] for row in cursor.fetchall())


def _read_manifest_rows(path: Path) -> tuple[dict[str, str], ...]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        return tuple(dict(row) for row in csv.DictReader(file))


def _metadata_patch(
    item: TaxonomyBackfillItem,
    *,
    taxonomy_version: str,
) -> dict[str, object]:
    knowledge_base = {
        "taxonomy_version": taxonomy_version,
        "namespace_key": item.namespace_key,
        "primary_category": item.primary_category,
        "secondary_category": item.secondary_category,
        "confidence": item.namespace_confidence,
        "matched_terms": list(item.matched_terms),
        "manifest_relative_path": item.relative_path,
        "source_root_relative_path": item.source_root_relative_path,
        "database_relative_path": item.database_relative_path,
        "file_sha256": item.sha256,
    }
    return {
        "knowledge_base": knowledge_base,
        "knowledge_base_namespace": item.namespace_key,
        "knowledge_base_primary_category": item.primary_category,
        "knowledge_base_secondary_category": item.secondary_category,
    }


def _database_relative_path(*, source_root_relative_path: str, extraction_status: str) -> str:
    marker = "path_moved_from="
    if marker in extraction_status:
        return extraction_status.split(marker, maxsplit=1)[1]
    return source_root_relative_path


def _terms(value: str) -> tuple[str, ...]:
    return tuple(term for term in value.split(";") if term)


def _truthy(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _required(row: Mapping[str, str], key: str) -> str:
    value = row.get(key)
    if value is None or value == "":
        raise ValueError(f"manifest row missing {key}")
    return value


def _database_url_from_env(database_url_env: str | None) -> str | None:
    if database_url_env is None:
        return None
    value = os.getenv(database_url_env)
    return value if value else None


def _normalize_psycopg_database_url(database_url: str) -> str:
    return database_url.replace("postgresql+psycopg://", "postgresql://", 1)


def _validate_index_version_status(status: str) -> None:
    if status not in {"active", "candidate", "inactive"}:
        raise ValueError("index_version_status must be active, candidate, or inactive")


def _next_step_line(result: TaxonomyBackfillExecutionResult) -> str:
    if result.executed and result.success:
        return "结论：P0 已入库文档的二级分类元数据已回填。下一步处理 P1 医疗类未萃取文件。"
    if result.executed:
        return "结论：存在未匹配文档。先核对 index_version/status、文件移动记录和 SHA 后再补跑。"
    if result.success:
        return (
            "结论：dry-run 已生成 P0 回填清单。连接目标数据库并确认备份后，"
            "可用同一命令追加 `--execute`。"
        )
    return "结论：没有可回填的已入库文档；先重新生成 taxonomy manifest。"


SOURCE_DOCUMENT_TAXONOMY_UPDATE_SQL = """
UPDATE source_documents sd
SET
    metadata = COALESCE(sd.metadata, '{}'::jsonb) || %s::jsonb,
    updated_at = now()
FROM index_versions iv
WHERE iv.source_package_version_id = sd.source_package_version_id
  AND iv.status = %s
  AND (%s::text IS NULL OR iv.version_key = %s::text)
  AND sd.status = 'indexed'
  AND sd.relative_path = %s
  AND sd.sha256 = %s
RETURNING sd.id
"""

DOCUMENT_CHUNK_TAXONOMY_UPDATE_SQL = """
UPDATE document_chunks dc
SET metadata = COALESCE(dc.metadata, '{}'::jsonb) || %s::jsonb
FROM source_documents sd
JOIN index_versions iv ON iv.source_package_version_id = sd.source_package_version_id
WHERE dc.source_document_id = sd.id
  AND iv.status = %s
  AND (%s::text IS NULL OR iv.version_key = %s::text)
  AND sd.status = 'indexed'
  AND sd.relative_path = %s
  AND sd.sha256 = %s
RETURNING dc.id
"""
