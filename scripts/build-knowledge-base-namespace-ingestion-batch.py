#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

DEFAULT_MANIFEST_CSV = "tmp/outputs/knowledge-base-taxonomy-manifest-latest.csv"
DEFAULT_NAMESPACE_KEY = "medical.legal_regulations"
DEFAULT_OUTPUT_CSV = (
    "tmp/outputs/knowledge-base-ingestion-batch-medical-legal-regulations-latest.csv"
)
DEFAULT_OUTPUT_JSON = (
    "tmp/outputs/knowledge-base-ingestion-batch-medical-legal-regulations-latest.json"
)
DEFAULT_REPORT = (
    "drafts/analysis/knowledge-base-ingestion-batch-medical-legal-regulations-draft-20260703.md"
)

SUPPORTED_TEXT_EXTENSIONS = {".md", ".txt", ".pdf", ".xlsx"}
CONVERSION_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".rar", ".zip", ".7z"}
SYSTEM_FILENAMES = {".DS_Store", ".gitkeep"}


@dataclass(frozen=True, slots=True)
class BatchRow:
    priority_rank: int
    batch_group: str
    relative_path: str
    source_root_relative_path: str
    file_name: str
    file_ext: str
    size_bytes: int
    sha256: str
    primary_category: str
    secondary_category: str
    namespace_key: str
    namespace_confidence: str
    matched_terms: str
    extraction_status: str
    needs_manual_review: bool
    recommended_action: str

    def to_csv_row(self) -> dict[str, object]:
        return {
            "priority_rank": self.priority_rank,
            "batch_group": self.batch_group,
            "relative_path": self.relative_path,
            "source_root_relative_path": self.source_root_relative_path,
            "file_name": self.file_name,
            "file_ext": self.file_ext,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "primary_category": self.primary_category,
            "secondary_category": self.secondary_category,
            "namespace_key": self.namespace_key,
            "namespace_confidence": self.namespace_confidence,
            "matched_terms": self.matched_terms,
            "extraction_status": self.extraction_status,
            "needs_manual_review": str(self.needs_manual_review).lower(),
            "recommended_action": self.recommended_action,
        }


def main() -> int:
    args = _parse_args()
    manifest_csv = Path(args.manifest_csv)
    output_csv = Path(args.output_csv)
    output_json = Path(args.output_json)
    report = Path(args.report)

    rows = _build_batch_rows(manifest_csv, namespace_key=args.namespace_key)
    summary = _build_summary(
        rows=rows,
        manifest_csv=manifest_csv,
        namespace_key=args.namespace_key,
    )

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    _write_batch_csv(output_csv, rows)
    output_json.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    report.write_text(_render_report(summary), encoding="utf-8")

    print(
        json.dumps(
            {
                "status": "ready",
                "namespace_key": args.namespace_key,
                "batch_file_count": len(rows),
                "output_csv": str(output_csv),
                "output_json": str(output_json),
                "report": str(report),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a namespace-scoped ingestion batch from taxonomy manifest.",
    )
    parser.add_argument("--manifest-csv", default=DEFAULT_MANIFEST_CSV)
    parser.add_argument("--namespace-key", default=DEFAULT_NAMESPACE_KEY)
    parser.add_argument("--output-csv", default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--report", default=DEFAULT_REPORT)
    return parser.parse_args()


def _build_batch_rows(manifest_csv: Path, *, namespace_key: str) -> tuple[BatchRow, ...]:
    raw_rows = _read_manifest_rows(manifest_csv)
    selected = [
        row
        for row in raw_rows
        if row.get("namespace_key") == namespace_key and not _truthy(row.get("already_indexed"))
    ]
    batch_rows: list[BatchRow] = []
    for row in selected:
        batch_rows.append(
            BatchRow(
                priority_rank=0,
                batch_group=_batch_group(row),
                relative_path=_required(row, "relative_path"),
                source_root_relative_path=row.get("source_root_relative_path", ""),
                file_name=_required(row, "file_name"),
                file_ext=_required(row, "file_ext"),
                size_bytes=int(_required(row, "size_bytes")),
                sha256=_required(row, "sha256"),
                primary_category=_required(row, "primary_category"),
                secondary_category=_required(row, "secondary_category"),
                namespace_key=_required(row, "namespace_key"),
                namespace_confidence=_required(row, "namespace_confidence"),
                matched_terms=row.get("matched_terms", ""),
                extraction_status=_required(row, "extraction_status"),
                needs_manual_review=_truthy(row.get("needs_manual_review")),
                recommended_action=_required(row, "recommended_action"),
            )
        )
    sorted_rows = sorted(
        batch_rows,
        key=lambda item: (
            _batch_group_rank(item.batch_group),
            item.namespace_confidence != "high",
            item.size_bytes,
            item.relative_path,
        ),
    )
    return tuple(
        BatchRow(
            priority_rank=index,
            batch_group=row.batch_group,
            relative_path=row.relative_path,
            source_root_relative_path=row.source_root_relative_path,
            file_name=row.file_name,
            file_ext=row.file_ext,
            size_bytes=row.size_bytes,
            sha256=row.sha256,
            primary_category=row.primary_category,
            secondary_category=row.secondary_category,
            namespace_key=row.namespace_key,
            namespace_confidence=row.namespace_confidence,
            matched_terms=row.matched_terms,
            extraction_status=row.extraction_status,
            needs_manual_review=row.needs_manual_review,
            recommended_action=row.recommended_action,
        )
        for index, row in enumerate(sorted_rows, start=1)
    )


def _batch_group(row: dict[str, str]) -> str:
    file_name = row.get("file_name", "")
    file_ext = row.get("file_ext", "")
    extraction_status = row.get("extraction_status", "")
    needs_manual_review = _truthy(row.get("needs_manual_review"))

    if file_name in SYSTEM_FILENAMES or extraction_status == "system_file":
        return "exclude_system_file"
    if extraction_status.startswith(("pending_conversion", "source_extraction_issue")):
        return "requires_conversion_or_ocr"
    if file_ext in CONVERSION_EXTENSIONS:
        return "requires_conversion_or_ocr"
    if needs_manual_review or row.get("namespace_confidence") == "low":
        return "manual_review_before_ingestion"
    if file_ext in SUPPORTED_TEXT_EXTENSIONS:
        return "ready_for_text_extraction"
    return "manual_review_before_ingestion"


def _batch_group_rank(group: str) -> int:
    return {
        "ready_for_text_extraction": 1,
        "manual_review_before_ingestion": 2,
        "requires_conversion_or_ocr": 3,
        "exclude_system_file": 4,
    }.get(group, 99)


def _build_summary(
    *,
    rows: tuple[BatchRow, ...],
    manifest_csv: Path,
    namespace_key: str,
) -> dict[str, object]:
    by_group = Counter(row.batch_group for row in rows)
    by_ext = Counter(row.file_ext for row in rows)
    by_status = Counter(row.extraction_status.split(":", maxsplit=1)[0] for row in rows)
    ready_rows = [row for row in rows if row.batch_group == "ready_for_text_extraction"]
    return {
        "status": "ready",
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S%z"),
        "manifest_csv": str(manifest_csv),
        "namespace_key": namespace_key,
        "summary": {
            "batch_file_count": len(rows),
            "ready_for_text_extraction_count": len(ready_rows),
            "manual_review_before_ingestion_count": by_group.get(
                "manual_review_before_ingestion",
                0,
            ),
            "requires_conversion_or_ocr_count": by_group.get("requires_conversion_or_ocr", 0),
            "exclude_system_file_count": by_group.get("exclude_system_file", 0),
            "total_size_bytes": sum(row.size_bytes for row in rows),
        },
        "counts": {
            "by_batch_group": dict(by_group.most_common()),
            "by_file_ext": dict(by_ext.most_common()),
            "by_extraction_status": dict(by_status.most_common()),
        },
        "first_ready_batch": [row.to_csv_row() for row in ready_rows[:30]],
        "sample_manual_review": [
            row.to_csv_row()
            for row in rows
            if row.batch_group == "manual_review_before_ingestion"
        ][:20],
        "sample_conversion_or_ocr": [
            row.to_csv_row()
            for row in rows
            if row.batch_group == "requires_conversion_or_ocr"
        ][:20],
        "boundaries": {
            "database_write": False,
            "embedding_rebuild": False,
            "provider_call": False,
            "file_move": False,
        },
    }


def _write_batch_csv(path: Path, rows: tuple[BatchRow, ...]) -> None:
    fieldnames = list(rows[0].to_csv_row()) if rows else []
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row.to_csv_row())


def _render_report(summary: dict[str, object]) -> str:
    payload = _mapping(summary["summary"])
    counts = _mapping(summary["counts"])
    by_group = _mapping(counts["by_batch_group"])
    lines = [
        "---",
        "title: 知识库 namespace 入库批次计划",
        "doc_type: analysis",
        "module: knowledge-base-taxonomy",
        "topic: namespace-ingestion-batch",
        "status: draft",
        "created: 2026-07-03",
        "updated: 2026-07-03",
        "owner: self",
        "source: ai",
        "---",
        "",
        "# 知识库 namespace 入库批次计划",
        "",
        "## 1. 运行边界",
        "",
        f"- `namespace_key`: `{summary['namespace_key']}`",
        f"- `manifest_csv`: `{summary['manifest_csv']}`",
        "- `database_write`: `False`",
        "- `embedding_rebuild`: `False`",
        "- `provider_call`: `False`",
        "- `file_move`: `False`",
        "",
        "## 2. 批次总览",
        "",
        f"- `batch_file_count`: `{payload['batch_file_count']}`",
        f"- `ready_for_text_extraction_count`: `{payload['ready_for_text_extraction_count']}`",
        "- `manual_review_before_ingestion_count`: "
        f"`{payload['manual_review_before_ingestion_count']}`",
        f"- `requires_conversion_or_ocr_count`: `{payload['requires_conversion_or_ocr_count']}`",
        f"- `exclude_system_file_count`: `{payload['exclude_system_file_count']}`",
        f"- `total_size_bytes`: `{payload['total_size_bytes']}`",
        "",
        "## 3. 分组计数",
        "",
        "| batch_group | count |",
        "| --- | ---: |",
    ]
    for key, value in by_group.items():
        lines.append(f"| `{key}` | {value} |")
    lines.extend(
        [
            "",
            "## 4. 第一批建议",
            "",
            "先处理 `ready_for_text_extraction` 的前 30 个小文件，建立抽取、chunk、评测、"
            "导入的最小闭环；再扩大到该 namespace 全量。",
        ]
    )
    return "\n".join(lines) + "\n"


def _read_manifest_rows(path: Path) -> tuple[dict[str, str], ...]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        return tuple(dict(row) for row in csv.DictReader(file))


def _required(row: dict[str, str], key: str) -> str:
    value = row.get(key)
    if value is None or value == "":
        raise ValueError(f"manifest row missing {key}")
    return value


def _truthy(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError("expected mapping")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
