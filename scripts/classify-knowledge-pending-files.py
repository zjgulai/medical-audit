#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_PENDING_FILE = "tmp/knowledge-query-indexes/real-data-kimi-20260531/pending_files.jsonl"
DEFAULT_SOURCE_ROOT = "data/医保审核前期资料"
DEFAULT_OUTPUT = "tmp/outputs/knowledge-query-pending-files-classification-latest.md"
DEFAULT_JSON_OUTPUT = "tmp/outputs/knowledge-query-pending-files-classification-latest.json"

ARCHIVE_EXTENSIONS = {".zip", ".rar", ".7z"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}
OFFICE_EXTENSIONS = {".doc", ".docx", ".ppt", ".pptx", ".csv"}


@dataclass(frozen=True, slots=True)
class PendingItem:
    relative_path: str
    error_type: str
    error_summary: str
    file_ext: str
    source_collection: str
    category: str
    recommended_action: str
    source_exists: bool
    size_bytes: int | None

    def to_dict(self) -> dict[str, object]:
        return {
            "relative_path": self.relative_path,
            "error_type": self.error_type,
            "error_summary": self.error_summary,
            "file_ext": self.file_ext,
            "source_collection": self.source_collection,
            "category": self.category,
            "recommended_action": self.recommended_action,
            "source_exists": self.source_exists,
            "size_bytes": self.size_bytes,
        }


def main() -> int:
    args = _parse_args()
    pending_file = Path(args.pending_file)
    source_root = Path(args.source_root)
    output = Path(args.output)
    json_output = Path(args.json_output)

    rows = _load_pending_rows(pending_file)
    items = tuple(_classify_row(row, source_root=source_root) for row in rows)
    report = _build_report(
        items,
        pending_file=pending_file,
        source_root=source_root,
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    json_output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(_render_markdown(report), encoding="utf-8")
    json_output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(_summary_for_stdout(report), ensure_ascii=False, indent=2))
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Classify knowledge-query pending files and recommend resolution actions.",
    )
    parser.add_argument("--pending-file", default=DEFAULT_PENDING_FILE)
    parser.add_argument("--source-root", default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--json-output", default=DEFAULT_JSON_OUTPUT)
    return parser.parse_args()


def _load_pending_rows(path: Path) -> tuple[dict[str, object], ...]:
    if not path.exists():
        raise FileNotFoundError(f"pending file not found: {path}")
    rows: list[dict[str, object]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"pending row {line_number} is not an object")
        rows.append(payload)
    return tuple(rows)


def _classify_row(row: dict[str, object], *, source_root: Path) -> PendingItem:
    relative_path = _required_str(row, "relative_path")
    error_type = _optional_str(row.get("error_type")) or "unknown"
    error_summary = _optional_str(row.get("error_summary")) or "unknown"
    file_ext = Path(relative_path).suffix.lower() or ".unknown"
    source_collection = _source_collection(relative_path)
    category, action = _category_and_action(file_ext=file_ext, source_collection=source_collection)
    source_file = source_root / relative_path
    source_exists = source_file.exists() and source_file.is_file()
    size_bytes = source_file.stat().st_size if source_exists else None
    return PendingItem(
        relative_path=relative_path,
        error_type=error_type,
        error_summary=error_summary,
        file_ext=file_ext,
        source_collection=source_collection,
        category=category,
        recommended_action=action,
        source_exists=source_exists,
        size_bytes=size_bytes,
    )


def _source_collection(relative_path: str) -> str:
    path = Path(relative_path)
    if len(path.parts) <= 1:
        return "root"
    return path.parts[0]


def _category_and_action(*, file_ext: str, source_collection: str) -> tuple[str, str]:
    if file_ext in IMAGE_EXTENSIONS:
        return (
            "ocr-required-image",
            "执行 OCR 或寻找同批次可索引文本/xlsx 原件，转换后进入下一版资料包。",
        )
    if file_ext in ARCHIVE_EXTENSIONS:
        return (
            "archive-unpack-required",
            "先解包到草稿区，逐文件分类、去重、确认 V1 范围后再进入正式资料包。",
        )
    if file_ext in OFFICE_EXTENSIONS:
        return (
            "converter-required",
            "补充可靠转换器或人工转为 markdown/xlsx 后再索引。",
        )
    if source_collection == "unknown":
        return (
            "source-collection-required",
            "补充分组目录或 metadata，明确资料来源集合后再索引。",
        )
    return (
        "manual-triage-required",
        "人工判断文件类型、来源范围和转换策略后再进入下一版资料包。",
    )


def _build_report(
    items: tuple[PendingItem, ...],
    *,
    pending_file: Path,
    source_root: Path,
) -> dict[str, object]:
    generated_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "status": "pass",
        "generated_at": generated_at,
        "pending_file": str(pending_file),
        "source_root": str(source_root),
        "summary": {
            "total_pending_files": len(items),
            "source_missing_count": sum(1 for item in items if not item.source_exists),
            "blocking_current_active_index": False,
            "requires_resolution_before_full_source_completeness": bool(items),
        },
        "counts": {
            "by_category": _counter_dict(item.category for item in items),
            "by_file_ext": _counter_dict(item.file_ext for item in items),
            "by_error_type": _counter_dict(item.error_type for item in items),
            "by_source_collection": _counter_dict(item.source_collection for item in items),
        },
        "items": [item.to_dict() for item in items],
    }


def _render_markdown(report: dict[str, object]) -> str:
    summary = _ensure_dict(report["summary"])
    counts = _ensure_dict(report["counts"])
    items = _ensure_list(report["items"])
    lines = [
        "# 知识库 pending 文件分类报告",
        "",
        f"- `generated_at`: `{report['generated_at']}`",
        f"- `pending_file`: `{report['pending_file']}`",
        f"- `source_root`: `{report['source_root']}`",
        f"- `total_pending_files`: `{summary['total_pending_files']}`",
        f"- `source_missing_count`: `{summary['source_missing_count']}`",
        f"- `blocking_current_active_index`: `{summary['blocking_current_active_index']}`",
        "",
        "## 分类计数",
        "",
        "### 按处理类别",
        "",
        *_count_lines(_ensure_dict(counts["by_category"])),
        "",
        "### 按文件类型",
        "",
        *_count_lines(_ensure_dict(counts["by_file_ext"])),
        "",
        "### 按来源目录",
        "",
        *_count_lines(_ensure_dict(counts["by_source_collection"])),
        "",
        "## 明细",
        "",
        "| 文件 | 类型 | 来源目录 | 分类 | 建议动作 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in items:
        row = _ensure_dict(item)
        lines.append(
            "| "
            f"`{row['relative_path']}` | "
            f"`{row['file_ext']}` | "
            f"`{row['source_collection']}` | "
            f"`{row['category']}` | "
            f"{row['recommended_action']} |"
        )
    lines.append("")
    return "\n".join(lines)


def _summary_for_stdout(report: dict[str, object]) -> dict[str, object]:
    summary = _ensure_dict(report["summary"])
    counts = _ensure_dict(report["counts"])
    return {
        "status": report["status"],
        "total_pending_files": summary["total_pending_files"],
        "source_missing_count": summary["source_missing_count"],
        "by_category": counts["by_category"],
        "by_file_ext": counts["by_file_ext"],
    }


def _count_lines(counts: dict[str, object]) -> list[str]:
    if not counts:
        return ["- 无"]
    return [f"- `{key}`: `{value}`" for key, value in sorted(counts.items())]


def _counter_dict(values: Iterable[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


def _required_str(row: dict[str, object], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"missing required string: {key}")
    return value


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _ensure_dict(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError(f"expected dict, got {type(value).__name__}")
    return value


def _ensure_list(value: object) -> list[object]:
    if not isinstance(value, list):
        raise TypeError(f"expected list, got {type(value).__name__}")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
