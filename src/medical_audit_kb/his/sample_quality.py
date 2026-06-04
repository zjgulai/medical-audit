from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from medical_audit_kb.his.ddl_parser import HisDdlParseReport, HisDdlTable


class HisSampleColumnProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    column_name: str
    non_empty_count: int
    empty_count: int


class HisSampleTableQuality(BaseModel):
    model_config = ConfigDict(frozen=True)

    table_name: str
    file_path: str
    file_sha256: str
    file_format: Literal["csv", "jsonl"]
    status: Literal["pass", "fail"]
    row_count: int
    column_count: int
    columns: tuple[str, ...]
    expected_columns: tuple[str, ...]
    missing_expected_columns: tuple[str, ...]
    extra_columns: tuple[str, ...]
    primary_key_fields: tuple[str, ...]
    duplicate_primary_key_count: int
    required_empty_counts: dict[str, int]
    column_profiles: tuple[HisSampleColumnProfile, ...]
    issues: tuple[str, ...]


class HisSampleQualityReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Literal["pass", "fail"]
    sample_root: str
    table_count: int
    total_row_count: int
    tables: tuple[HisSampleTableQuality, ...]
    issues: tuple[str, ...]


SUPPORTED_SAMPLE_SUFFIXES = {".csv", ".jsonl"}


def build_his_sample_quality_report(
    sample_root: Path,
    *,
    ddl_report: HisDdlParseReport | None = None,
) -> HisSampleQualityReport:
    table_lookup = _table_lookup(ddl_report)
    sample_files = tuple(_sample_files(sample_root))
    issues: list[str] = []
    table_reports: list[HisSampleTableQuality] = []

    if not sample_root.exists():
        issues.append(f"sample root not found: {sample_root}")
    if sample_root.exists() and not sample_files:
        issues.append(f"sample root has no supported sample files: {sample_root}")

    for sample_file in sample_files:
        try:
            rows = tuple(load_his_sample_rows(sample_file))
        except ValueError as exc:
            issues.append(str(exc))
            continue
        expected_table = _match_expected_table(sample_file, table_lookup)
        table_reports.append(_table_quality(sample_file, rows, expected_table))

    status: Literal["pass", "fail"] = (
        "fail" if issues or any(table.status == "fail" for table in table_reports) else "pass"
    )
    return HisSampleQualityReport(
        status=status,
        sample_root=str(sample_root),
        table_count=len(table_reports),
        total_row_count=sum(table.row_count for table in table_reports),
        tables=tuple(table_reports),
        issues=tuple(issues),
    )


def load_his_ddl_parse_report_json(path: Path) -> HisDdlParseReport:
    return HisDdlParseReport.model_validate_json(path.read_text(encoding="utf-8"))


def render_his_sample_quality_report_markdown(report: HisSampleQualityReport) -> str:
    lines = [
        "# HIS 脱敏样本数据质量报告",
        "",
        f"- 总体状态：`{report.status.upper()}`",
        f"- 样本目录：`{report.sample_root}`",
        f"- 表数量：`{report.table_count}`",
        f"- 总行数：`{report.total_row_count}`",
    ]
    if report.issues:
        lines.extend(["", "## 全局问题"])
        lines.extend(f"- {issue}" for issue in report.issues)

    for table in report.tables:
        lines.extend(
            [
                "",
                f"## {table.table_name}",
                "",
                f"- 状态：`{table.status.upper()}`",
                f"- 文件：`{table.file_path}`",
                f"- 格式：`{table.file_format}`",
                f"- 行数：`{table.row_count}`",
                f"- 字段数：`{table.column_count}`",
                f"- 主键字段：`{', '.join(table.primary_key_fields) or '-'}`",
                f"- 重复主键数：`{table.duplicate_primary_key_count}`",
                f"- 缺失预期字段：`{', '.join(table.missing_expected_columns) or '-'}`",
                f"- 额外字段：`{', '.join(table.extra_columns) or '-'}`",
            ]
        )
        if table.required_empty_counts:
            lines.append(
                "- 必填字段空值：`"
                + ", ".join(
                    f"{field}={count}" for field, count in table.required_empty_counts.items()
                )
                + "`"
            )
        if table.issues:
            lines.append("")
            lines.append("### 问题")
            lines.extend(f"- {issue}" for issue in table.issues)
        lines.extend(
            [
                "",
                "| 字段 | 非空行数 | 空值行数 |",
                "| --- | ---: | ---: |",
            ]
        )
        for profile in table.column_profiles:
            lines.append(
                f"| `{profile.column_name}` | {profile.non_empty_count} | {profile.empty_count} |"
            )
    return "\n".join(lines) + "\n"


def his_sample_quality_report_json(report: HisSampleQualityReport) -> str:
    return json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n"


def _sample_files(sample_root: Path) -> Iterable[Path]:
    if not sample_root.exists():
        return ()
    return sorted(
        path
        for path in sample_root.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_SAMPLE_SUFFIXES
    )


def load_his_sample_rows(path: Path) -> list[dict[str, str]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _read_csv_rows(path)
    if suffix == ".jsonl":
        return _read_jsonl_rows(path)
    raise ValueError(f"unsupported sample file: {path}")


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise ValueError(f"CSV sample has no header: {path}")
            return [
                {str(key): "" if value is None else str(value) for key, value in row.items()}
                for row in reader
            ]
    except UnicodeDecodeError as exc:
        raise ValueError(f"CSV sample is not UTF-8 compatible: {path}") from exc


def _read_jsonl_rows(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"JSONL sample invalid JSON at {path}:{row_number}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"JSONL sample row must be object at {path}:{row_number}")
        rows.append({str(key): "" if item is None else str(item) for key, item in value.items()})
    return rows


def _table_quality(
    sample_file: Path,
    rows: tuple[dict[str, str], ...],
    expected_table: HisDdlTable | None,
) -> HisSampleTableQuality:
    columns = _columns(rows)
    expected_columns = (
        tuple(column.name for column in expected_table.columns) if expected_table else ()
    )
    primary_key_fields = expected_table.primary_key_fields if expected_table else ()
    required_fields = (
        tuple(column.name for column in expected_table.columns if not column.nullable)
        if expected_table is not None
        else ()
    )
    missing_expected_columns = tuple(column for column in expected_columns if column not in columns)
    extra_columns = tuple(
        column for column in columns if expected_columns and column not in expected_columns
    )
    required_empty_counts = _required_empty_counts(rows, required_fields)
    duplicate_primary_key_count = _duplicate_primary_key_count(rows, primary_key_fields)
    issues = _table_issues(
        row_count=len(rows),
        missing_expected_columns=missing_expected_columns,
        required_empty_counts=required_empty_counts,
        primary_key_fields=primary_key_fields,
        duplicate_primary_key_count=duplicate_primary_key_count,
        columns=columns,
        expected_table=expected_table,
    )
    status: Literal["pass", "fail"] = "fail" if issues else "pass"
    return HisSampleTableQuality(
        table_name=expected_table.table_name if expected_table is not None else sample_file.stem,
        file_path=str(sample_file),
        file_sha256=_file_sha256(sample_file),
        file_format="jsonl" if sample_file.suffix.lower() == ".jsonl" else "csv",
        status=status,
        row_count=len(rows),
        column_count=len(columns),
        columns=columns,
        expected_columns=expected_columns,
        missing_expected_columns=missing_expected_columns,
        extra_columns=extra_columns,
        primary_key_fields=primary_key_fields,
        duplicate_primary_key_count=duplicate_primary_key_count,
        required_empty_counts=required_empty_counts,
        column_profiles=_column_profiles(rows, columns),
        issues=issues,
    )


def _columns(rows: tuple[dict[str, str], ...]) -> tuple[str, ...]:
    columns: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                columns.append(key)
                seen.add(key)
    return tuple(columns)


def _required_empty_counts(
    rows: tuple[dict[str, str], ...],
    required_fields: tuple[str, ...],
) -> dict[str, int]:
    return {
        field: empty_count
        for field in required_fields
        if (empty_count := sum(1 for row in rows if _is_empty(row.get(field)))) > 0
    }


def _duplicate_primary_key_count(
    rows: tuple[dict[str, str], ...],
    primary_key_fields: tuple[str, ...],
) -> int:
    if not primary_key_fields:
        return 0
    keys = [
        tuple((row.get(field) or "").strip() for field in primary_key_fields)
        for row in rows
        if all(not _is_empty(row.get(field)) for field in primary_key_fields)
    ]
    counts = Counter(keys)
    return sum(count - 1 for count in counts.values() if count > 1)


def _column_profiles(
    rows: tuple[dict[str, str], ...],
    columns: tuple[str, ...],
) -> tuple[HisSampleColumnProfile, ...]:
    return tuple(
        HisSampleColumnProfile(
            column_name=column,
            non_empty_count=sum(1 for row in rows if not _is_empty(row.get(column))),
            empty_count=sum(1 for row in rows if _is_empty(row.get(column))),
        )
        for column in columns
    )


def _table_issues(
    *,
    row_count: int,
    missing_expected_columns: tuple[str, ...],
    required_empty_counts: dict[str, int],
    primary_key_fields: tuple[str, ...],
    duplicate_primary_key_count: int,
    columns: tuple[str, ...],
    expected_table: HisDdlTable | None,
) -> tuple[str, ...]:
    issues: list[str] = []
    if expected_table is None:
        issues.append("sample file has no matching DDL table")
    if row_count == 0:
        issues.append("sample file has no rows")
    if missing_expected_columns:
        issues.append(f"missing expected columns: {', '.join(missing_expected_columns)}")
    if required_empty_counts:
        issues.append(
            "required columns contain empty values: "
            + ", ".join(f"{field}={count}" for field, count in required_empty_counts.items())
        )
    if primary_key_fields and any(field not in columns for field in primary_key_fields):
        issues.append(f"primary key columns are absent: {', '.join(primary_key_fields)}")
    if duplicate_primary_key_count > 0:
        issues.append(f"duplicate primary keys: {duplicate_primary_key_count}")
    return tuple(issues)


def _table_lookup(ddl_report: HisDdlParseReport | None) -> dict[str, HisDdlTable]:
    if ddl_report is None:
        return {}
    lookup: dict[str, HisDdlTable] = {}
    for table in ddl_report.tables:
        for key in _table_match_keys(table):
            lookup[key] = table
    return lookup


def _match_expected_table(
    sample_file: Path,
    table_lookup: dict[str, HisDdlTable],
) -> HisDdlTable | None:
    return table_lookup.get(_normalize_table_key(sample_file.stem))


def _table_match_keys(table: HisDdlTable) -> tuple[str, ...]:
    table_name = table.table_name
    unqualified_name = table_name.split(".")[-1]
    return tuple(
        key
        for key in {
            _normalize_table_key(table_name),
            _normalize_table_key(unqualified_name),
            _normalize_table_key(table.business_domain),
        }
        if key
    )


def _normalize_table_key(value: str) -> str:
    return "".join(char for char in value.lower() if char.isalnum())


def _is_empty(value: str | None) -> bool:
    return value is None or value.strip() == ""


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
