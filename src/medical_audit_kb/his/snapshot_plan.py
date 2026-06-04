from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from medical_audit_kb.domain.schemas import AuditDataSnapshotCreate
from medical_audit_kb.his.sample_quality import HisSampleQualityReport, HisSampleTableQuality


class HisSnapshotTablePlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    table_name: str
    file_path: str
    file_sha256: str
    row_count: int
    column_count: int


class HisSnapshotPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Literal["pass", "fail"]
    can_create_snapshot: bool
    snapshot_key: str
    source_batch_key: str
    checksum: str | None
    row_counts: dict[str, int]
    table_plans: tuple[HisSnapshotTablePlan, ...]
    audit_data_snapshot_payload: AuditDataSnapshotCreate | None
    issues: tuple[str, ...]


def build_his_snapshot_plan(
    quality_report: HisSampleQualityReport,
    *,
    project_id: UUID,
    snapshot_key: str,
    source_batch_key: str,
    time_range: dict[str, Any] | None = None,
    status: str = "validated",
) -> HisSnapshotPlan:
    table_plans = tuple(_table_plan(table) for table in quality_report.tables)
    row_counts = {table.table_name: table.row_count for table in table_plans}
    issues = _snapshot_issues(quality_report)
    can_create_snapshot = not issues
    checksum = _snapshot_checksum(table_plans) if can_create_snapshot else None
    payload = (
        AuditDataSnapshotCreate(
            snapshot_key=snapshot_key,
            project_id=project_id,
            source_batch_key=source_batch_key,
            time_range=time_range or {},
            row_counts=row_counts,
            checksum=f"sha256:{checksum}",
            status=status,
            metadata={
                "source": "his-snapshot-plan",
                "sample_quality_status": quality_report.status,
                "sample_root": quality_report.sample_root,
            },
        )
        if can_create_snapshot and checksum is not None
        else None
    )
    return HisSnapshotPlan(
        status="pass" if can_create_snapshot else "fail",
        can_create_snapshot=can_create_snapshot,
        snapshot_key=snapshot_key,
        source_batch_key=source_batch_key,
        checksum=f"sha256:{checksum}" if checksum is not None else None,
        row_counts=row_counts,
        table_plans=table_plans,
        audit_data_snapshot_payload=payload,
        issues=issues,
    )


def load_his_sample_quality_report_json(path: Path) -> HisSampleQualityReport:
    return HisSampleQualityReport.model_validate_json(path.read_text(encoding="utf-8"))


def render_his_snapshot_plan_markdown(plan: HisSnapshotPlan) -> str:
    lines = [
        "# HIS 数据快照计划",
        "",
        f"- 总体状态：`{plan.status.upper()}`",
        f"- 可创建快照：`{str(plan.can_create_snapshot).lower()}`",
        f"- snapshot_key：`{plan.snapshot_key}`",
        f"- source_batch_key：`{plan.source_batch_key}`",
        f"- checksum：`{plan.checksum or '-'}`",
    ]
    if plan.issues:
        lines.extend(["", "## 阻断问题"])
        lines.extend(f"- {issue}" for issue in plan.issues)
    lines.extend(
        [
            "",
            "## 表清单",
            "",
            "| 表 | 行数 | 字段数 | 文件 hash |",
            "| --- | ---: | ---: | --- |",
        ]
    )
    for table in plan.table_plans:
        lines.append(
            f"| `{table.table_name}` | {table.row_count} | {table.column_count} | "
            f"`sha256:{table.file_sha256}` |"
        )
    return "\n".join(lines) + "\n"


def his_snapshot_plan_json(plan: HisSnapshotPlan) -> str:
    return json.dumps(plan.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n"


def _table_plan(table: HisSampleTableQuality) -> HisSnapshotTablePlan:
    return HisSnapshotTablePlan(
        table_name=table.table_name,
        file_path=table.file_path,
        file_sha256=table.file_sha256,
        row_count=table.row_count,
        column_count=table.column_count,
    )


def _snapshot_issues(quality_report: HisSampleQualityReport) -> tuple[str, ...]:
    issues: list[str] = []
    if quality_report.status != "pass":
        issues.append("sample quality report is not PASS")
    if not quality_report.tables:
        issues.append("sample quality report has no tables")
    for table in quality_report.tables:
        if table.status != "pass":
            issues.append(f"table quality is not PASS: {table.table_name}")
    return tuple(issues)


def _snapshot_checksum(table_plans: tuple[HisSnapshotTablePlan, ...]) -> str:
    digest = hashlib.sha256()
    for table in sorted(table_plans, key=lambda item: item.table_name):
        digest.update(table.table_name.encode("utf-8"))
        digest.update(str(table.row_count).encode("utf-8"))
        digest.update(str(table.column_count).encode("utf-8"))
        digest.update(table.file_sha256.encode("utf-8"))
    return digest.hexdigest()
