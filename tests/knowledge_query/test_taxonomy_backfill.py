from __future__ import annotations

import csv
import json
from pathlib import Path

from medical_audit_kb.cli import main
from medical_audit_kb.indexing.taxonomy_backfill import (
    build_taxonomy_backfill_plan,
    render_taxonomy_backfill_markdown,
    run_taxonomy_backfill,
    write_taxonomy_backfill_to_cursor,
)


def test_build_taxonomy_backfill_plan_selects_indexed_rows(tmp_path: Path) -> None:
    manifest_csv = _write_manifest_csv(tmp_path)

    plan = build_taxonomy_backfill_plan(manifest_csv)

    assert plan.planned_document_count == 2
    assert plan.skipped_row_count == 1
    assert plan.counts_by_namespace == {
        "medical.legal_regulations": 1,
        "medical.supervision_rules": 1,
    }
    moved_item = next(
        item for item in plan.items if item.namespace_key == "medical.supervision_rules"
    )
    assert moved_item.database_relative_path == "智能监管/旧规则.xlsx"
    assert moved_item.metadata_patch["knowledge_base_namespace"] == "medical.supervision_rules"


def test_run_taxonomy_backfill_dry_run_does_not_write_database(tmp_path: Path) -> None:
    manifest_csv = _write_manifest_csv(tmp_path)

    result = run_taxonomy_backfill(manifest_csv, execute=False)

    assert result.mode == "dry-run"
    assert result.executed is False
    assert result.success is True
    assert result.plan.planned_document_count == 2
    assert result.updated_document_count == 0
    assert "database_write` | `False" in render_taxonomy_backfill_markdown(result)


def test_write_taxonomy_backfill_to_cursor_updates_documents_and_chunks(
    tmp_path: Path,
) -> None:
    manifest_csv = _write_manifest_csv(tmp_path)
    plan = build_taxonomy_backfill_plan(manifest_csv)
    cursor = RecordingCursor()

    counts = write_taxonomy_backfill_to_cursor(
        cursor,
        plan,
        index_version_status="active",
        index_version_key="stable-incremental-20260615",
    )

    assert counts.matched_document_count == 2
    assert counts.updated_document_count == 2
    assert counts.updated_chunk_count == 4
    assert not counts.unmatched_items
    assert cursor.execute_kinds == ["document", "chunks", "document", "chunks"]
    assert cursor.params[0][4] == "全量法律/医保政策.md"
    assert cursor.params[2][4] == "智能监管/旧规则.xlsx"


def test_taxonomy_backfill_cli_writes_dry_run_outputs(tmp_path: Path) -> None:
    manifest_csv = _write_manifest_csv(tmp_path)
    report_path = tmp_path / "taxonomy-backfill.md"
    json_path = tmp_path / "taxonomy-backfill.json"

    exit_code = main(
        [
            "taxonomy-backfill",
            "--manifest-csv",
            str(manifest_csv),
            "--output",
            str(report_path),
            "--json-output",
            str(json_path),
        ]
    )

    assert exit_code == 0
    assert "知识库二级分类元数据回填报告" in report_path.read_text(encoding="utf-8")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["mode"] == "dry-run"
    assert payload["plan"]["planned_document_count"] == 2


class RecordingCursor:
    def __init__(self) -> None:
        self.execute_kinds: list[str] = []
        self.params: list[tuple[object, ...]] = []
        self._next_rows: list[tuple[object, ...]] = []

    def execute(self, query: str, params: tuple[object, ...] | None = None) -> object:
        self.params.append(params or ())
        if "UPDATE source_documents" in query:
            self.execute_kinds.append("document")
            self._next_rows = [("document-id",)]
        elif "UPDATE document_chunks" in query:
            self.execute_kinds.append("chunks")
            self._next_rows = [("chunk-1",), ("chunk-2",)]
        else:
            raise AssertionError(f"unexpected query: {query}")
        return None

    def fetchall(self) -> list[tuple[object, ...]]:
        return list(self._next_rows)


def _write_manifest_csv(tmp_path: Path) -> Path:
    path = tmp_path / "manifest.csv"
    rows = [
        {
            "relative_path": "医保审核前期资料/全量法律/医保政策.md",
            "source_root_relative_path": "全量法律/医保政策.md",
            "file_name": "医保政策.md",
            "file_ext": ".md",
            "size_bytes": "128",
            "sha256": "a" * 64,
            "primary_category": "医疗类",
            "secondary_category": "法律法规",
            "namespace_key": "medical.legal_regulations",
            "namespace_confidence": "high",
            "matched_terms": "医保;医疗",
            "extraction_status": "extracted_in_stable_incremental_artifact",
            "already_indexed": "true",
            "needs_manual_review": "false",
            "recommended_action": "补齐 namespace 元数据；不需要重算 embedding。",
        },
        {
            "relative_path": "医保审核前期资料/智能监管/新规则.xlsx",
            "source_root_relative_path": "智能监管/新规则.xlsx",
            "file_name": "新规则.xlsx",
            "file_ext": ".xlsx",
            "size_bytes": "256",
            "sha256": "b" * 64,
            "primary_category": "医疗类",
            "secondary_category": "监管两库",
            "namespace_key": "medical.supervision_rules",
            "namespace_confidence": "high",
            "matched_terms": "监管;两库",
            "extraction_status": (
                "extracted_in_stable_incremental_artifact:path_moved_from=智能监管/旧规则.xlsx"
            ),
            "already_indexed": "true",
            "needs_manual_review": "false",
            "recommended_action": "补齐 namespace 元数据；不需要重算 embedding。",
        },
        {
            "relative_path": "医保审核前期资料/全量法律/未入库.md",
            "source_root_relative_path": "全量法律/未入库.md",
            "file_name": "未入库.md",
            "file_ext": ".md",
            "size_bytes": "64",
            "sha256": "c" * 64,
            "primary_category": "医疗类",
            "secondary_category": "法律法规",
            "namespace_key": "medical.legal_regulations",
            "namespace_confidence": "medium",
            "matched_terms": "医疗",
            "extraction_status": "not_seen_in_latest_incremental_plan",
            "already_indexed": "false",
            "needs_manual_review": "false",
            "recommended_action": "进入待萃取队列，按 namespace 优先级处理。",
        },
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path
