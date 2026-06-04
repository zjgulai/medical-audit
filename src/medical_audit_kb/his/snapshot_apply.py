from __future__ import annotations

import json
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from medical_audit_kb.db.engine import create_schema, create_session_factory
from medical_audit_kb.db.models import AuditDataSnapshot, AuditProject
from medical_audit_kb.db.repositories import AuditWorkflowRepository
from medical_audit_kb.his.snapshot_plan import HisSnapshotPlan


class HisSnapshotApplyResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Literal["pass", "fail"]
    execute_requested: bool
    executed: bool
    dry_run: bool
    snapshot_key: str
    source_batch_key: str
    created_snapshot_id: UUID | None
    row_counts: dict[str, int]
    checksum: str | None
    issues: tuple[str, ...]


async def apply_his_snapshot_plan_to_database(
    plan: HisSnapshotPlan,
    *,
    database_url: str,
    execute: bool = False,
    create_schema_if_missing: bool = False,
) -> HisSnapshotApplyResult:
    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        return await apply_his_snapshot_plan_with_engine(
            plan,
            engine=engine,
            execute=execute,
            create_schema_if_missing=create_schema_if_missing,
        )
    finally:
        await engine.dispose()


async def apply_his_snapshot_plan_with_engine(
    plan: HisSnapshotPlan,
    *,
    engine: AsyncEngine,
    execute: bool = False,
    create_schema_if_missing: bool = False,
) -> HisSnapshotApplyResult:
    if create_schema_if_missing:
        await create_schema(engine)

    session_factory = create_session_factory(engine)
    async with session_factory() as session, session.begin():
        issues = list(_static_plan_issues(plan))
        payload = plan.audit_data_snapshot_payload
        if payload is not None:
            project = await session.get(AuditProject, payload.project_id)
            if project is None:
                issues.append(f"audit project not found: {payload.project_id}")

            existing_result = await session.execute(
                select(AuditDataSnapshot).where(
                    AuditDataSnapshot.snapshot_key == payload.snapshot_key
                )
            )
            if existing_result.scalar_one_or_none() is not None:
                issues.append(f"snapshot_key already exists: {payload.snapshot_key}")

        if issues or payload is None or not execute:
            return _result(
                plan,
                status="fail" if issues or payload is None else "pass",
                execute_requested=execute,
                executed=False,
                issues=tuple(issues),
                created_snapshot_id=None,
            )

        snapshot = await AuditWorkflowRepository(session).create_data_snapshot(payload)
        return _result(
            plan,
            status="pass",
            execute_requested=execute,
            executed=True,
            issues=(),
            created_snapshot_id=snapshot.id,
        )


def load_his_snapshot_plan_json(path: Path) -> HisSnapshotPlan:
    return HisSnapshotPlan.model_validate_json(path.read_text(encoding="utf-8"))


def render_his_snapshot_apply_markdown(result: HisSnapshotApplyResult) -> str:
    lines = [
        "# HIS 数据快照入库报告",
        "",
        f"- 总体状态：`{result.status.upper()}`",
        f"- 请求写入：`{str(result.execute_requested).lower()}`",
        f"- 执行写入：`{str(result.executed).lower()}`",
        f"- dry_run：`{str(result.dry_run).lower()}`",
        f"- snapshot_key：`{result.snapshot_key}`",
        f"- source_batch_key：`{result.source_batch_key}`",
        f"- created_snapshot_id：`{result.created_snapshot_id or '-'}`",
        f"- checksum：`{result.checksum or '-'}`",
    ]
    if result.issues:
        lines.extend(["", "## 阻断问题"])
        lines.extend(f"- {issue}" for issue in result.issues)
    lines.extend(
        [
            "",
            "## 行数摘要",
            "",
            "| 表 | 行数 |",
            "| --- | ---: |",
        ]
    )
    for table_name, row_count in sorted(result.row_counts.items()):
        lines.append(f"| `{table_name}` | {row_count} |")
    return "\n".join(lines) + "\n"


def his_snapshot_apply_result_json(result: HisSnapshotApplyResult) -> str:
    return json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n"


def _static_plan_issues(plan: HisSnapshotPlan) -> tuple[str, ...]:
    issues = list(plan.issues)
    if plan.status != "pass":
        issues.append("snapshot plan status is not PASS")
    if not plan.can_create_snapshot:
        issues.append("snapshot plan cannot create snapshot")
    if plan.audit_data_snapshot_payload is None:
        issues.append("snapshot plan has no audit_data_snapshot_payload")
    return tuple(dict.fromkeys(issues))


def _result(
    plan: HisSnapshotPlan,
    *,
    status: Literal["pass", "fail"],
    execute_requested: bool,
    executed: bool,
    issues: tuple[str, ...],
    created_snapshot_id: UUID | None,
) -> HisSnapshotApplyResult:
    return HisSnapshotApplyResult(
        status=status,
        execute_requested=execute_requested,
        executed=executed,
        dry_run=not execute_requested,
        snapshot_key=plan.snapshot_key,
        source_batch_key=plan.source_batch_key,
        created_snapshot_id=created_snapshot_id,
        row_counts=plan.row_counts,
        checksum=plan.checksum,
        issues=issues,
    )
