from __future__ import annotations

import json
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from medical_audit_kb.db.engine import create_schema, create_session_factory
from medical_audit_kb.db.models import (
    AuditDataSnapshot,
    AuditFinding,
    AuditProject,
    AuditRun,
    AuditTask,
)
from medical_audit_kb.db.repositories import AuditWorkflowRepository
from medical_audit_kb.domain.schemas import AuditSnapshotRollbackCreate


class HisSnapshotRollbackAuditResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Literal["pass", "fail"]
    execute_requested: bool
    executed: bool
    dry_run: bool
    rollback_key: str
    project_key: str
    project_id: UUID | None
    from_snapshot_key: str
    from_snapshot_id: UUID | None
    to_snapshot_key: str
    to_snapshot_id: UUID | None
    reason: str
    requested_by: str | None
    created_rollback_id: UUID | None
    impact_summary: dict[str, Any]
    issues: tuple[str, ...]


async def audit_his_snapshot_rollback_to_database(
    *,
    database_url: str,
    rollback_key: str,
    project_key: str,
    from_snapshot_key: str,
    to_snapshot_key: str,
    reason: str,
    requested_by: str | None = None,
    execute: bool = False,
    create_schema_if_missing: bool = False,
) -> HisSnapshotRollbackAuditResult:
    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        return await audit_his_snapshot_rollback_with_engine(
            engine=engine,
            rollback_key=rollback_key,
            project_key=project_key,
            from_snapshot_key=from_snapshot_key,
            to_snapshot_key=to_snapshot_key,
            reason=reason,
            requested_by=requested_by,
            execute=execute,
            create_schema_if_missing=create_schema_if_missing,
        )
    finally:
        await engine.dispose()


async def audit_his_snapshot_rollback_with_engine(
    *,
    engine: AsyncEngine,
    rollback_key: str,
    project_key: str,
    from_snapshot_key: str,
    to_snapshot_key: str,
    reason: str,
    requested_by: str | None = None,
    execute: bool = False,
    create_schema_if_missing: bool = False,
) -> HisSnapshotRollbackAuditResult:
    if create_schema_if_missing:
        await create_schema(engine)

    session_factory = create_session_factory(engine)
    async with session_factory() as session, session.begin():
        project = await _get_project_by_key(session, project_key)
        from_snapshot = await _get_snapshot_by_key(session, from_snapshot_key)
        to_snapshot = await _get_snapshot_by_key(session, to_snapshot_key)
        repository = AuditWorkflowRepository(session)
        existing_rollback = await repository.get_snapshot_rollback_by_key(rollback_key)
        impact_summary = await _build_impact_summary(session, from_snapshot, to_snapshot)
        issues = _context_issues(
            project=project,
            from_snapshot=from_snapshot,
            to_snapshot=to_snapshot,
            existing_rollback_exists=existing_rollback is not None,
            rollback_key=rollback_key,
            project_key=project_key,
            from_snapshot_key=from_snapshot_key,
            to_snapshot_key=to_snapshot_key,
        )

        if issues or not execute:
            return _result(
                status="fail" if issues else "pass",
                execute_requested=execute,
                rollback_key=rollback_key,
                project_key=project_key,
                project_id=project.id if project is not None else None,
                from_snapshot_key=from_snapshot_key,
                from_snapshot_id=from_snapshot.id if from_snapshot is not None else None,
                to_snapshot_key=to_snapshot_key,
                to_snapshot_id=to_snapshot.id if to_snapshot is not None else None,
                reason=reason,
                requested_by=requested_by,
                created_rollback_id=None,
                impact_summary=impact_summary,
                issues=issues,
            )

        assert project is not None
        assert from_snapshot is not None
        assert to_snapshot is not None
        rollback = await repository.create_snapshot_rollback(
            AuditSnapshotRollbackCreate(
                rollback_key=rollback_key,
                project_id=project.id,
                from_snapshot_id=from_snapshot.id,
                to_snapshot_id=to_snapshot.id,
                status="recorded",
                reason=reason,
                requested_by=requested_by,
                impact_summary=impact_summary,
                metadata={"source": "his-snapshot-rollback-audit"},
            )
        )
        return _result(
            status="pass",
            execute_requested=execute,
            rollback_key=rollback_key,
            project_key=project_key,
            project_id=project.id,
            from_snapshot_key=from_snapshot_key,
            from_snapshot_id=from_snapshot.id,
            to_snapshot_key=to_snapshot_key,
            to_snapshot_id=to_snapshot.id,
            reason=reason,
            requested_by=requested_by,
            created_rollback_id=rollback.id,
            impact_summary=impact_summary,
            issues=(),
        )


def render_his_snapshot_rollback_audit_markdown(
    result: HisSnapshotRollbackAuditResult,
) -> str:
    lines = [
        "# HIS 数据快照回滚审计报告",
        "",
        f"- 总体状态：`{result.status.upper()}`",
        f"- 请求写入：`{str(result.execute_requested).lower()}`",
        f"- 执行写入：`{str(result.executed).lower()}`",
        f"- dry_run：`{str(result.dry_run).lower()}`",
        f"- rollback_key：`{result.rollback_key}`",
        f"- project_key：`{result.project_key}`",
        f"- project_id：`{result.project_id or '-'}`",
        f"- from_snapshot_key：`{result.from_snapshot_key}`",
        f"- from_snapshot_id：`{result.from_snapshot_id or '-'}`",
        f"- to_snapshot_key：`{result.to_snapshot_key}`",
        f"- to_snapshot_id：`{result.to_snapshot_id or '-'}`",
        f"- requested_by：`{result.requested_by or '-'}`",
        f"- created_rollback_id：`{result.created_rollback_id or '-'}`",
        f"- reason：{result.reason}",
    ]
    if result.issues:
        lines.extend(["", "## 阻断问题"])
        lines.extend(f"- {issue}" for issue in result.issues)
    lines.extend(["", "## 影响面摘要", ""])
    lines.extend(_summary_table(result.impact_summary))
    lines.extend(
        [
            "",
            "## 执行边界",
            "",
            "- 该命令只记录回滚审计事件，不删除历史快照、审计任务、运行批次或疑点。",
            "- 正式切换案件使用的快照前，必须先复核 dry-run 报告和影响面。",
        ]
    )
    return "\n".join(lines) + "\n"


def his_snapshot_rollback_audit_result_json(result: HisSnapshotRollbackAuditResult) -> str:
    return json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n"


async def _get_project_by_key(session: AsyncSession, project_key: str) -> AuditProject | None:
    return (
        await session.execute(select(AuditProject).where(AuditProject.project_key == project_key))
    ).scalar_one_or_none()


async def _get_snapshot_by_key(
    session: AsyncSession,
    snapshot_key: str,
) -> AuditDataSnapshot | None:
    return (
        await session.execute(
            select(AuditDataSnapshot).where(AuditDataSnapshot.snapshot_key == snapshot_key)
        )
    ).scalar_one_or_none()


async def _build_impact_summary(
    session: AsyncSession,
    from_snapshot: AuditDataSnapshot | None,
    to_snapshot: AuditDataSnapshot | None,
) -> dict[str, Any]:
    if from_snapshot is None:
        return {
            "affected_task_count": 0,
            "affected_run_count": 0,
            "affected_finding_count": 0,
        }
    return {
        "from_snapshot_status": from_snapshot.status,
        "from_source_batch_key": from_snapshot.source_batch_key,
        "from_row_counts": from_snapshot.row_counts,
        "to_snapshot_status": to_snapshot.status if to_snapshot is not None else None,
        "to_source_batch_key": to_snapshot.source_batch_key if to_snapshot is not None else None,
        "to_row_counts": to_snapshot.row_counts if to_snapshot is not None else {},
        "affected_task_count": await _count_by_snapshot(session, AuditTask, from_snapshot.id),
        "affected_run_count": await _count_by_snapshot(session, AuditRun, from_snapshot.id),
        "affected_finding_count": await _count_by_snapshot(session, AuditFinding, from_snapshot.id),
    }


async def _count_by_snapshot(
    session: AsyncSession,
    model: type[AuditTask] | type[AuditRun] | type[AuditFinding],
    snapshot_id: UUID,
) -> int:
    result = await session.execute(
        select(func.count()).select_from(model).where(model.snapshot_id == snapshot_id)
    )
    return int(result.scalar_one())


def _context_issues(
    *,
    project: AuditProject | None,
    from_snapshot: AuditDataSnapshot | None,
    to_snapshot: AuditDataSnapshot | None,
    existing_rollback_exists: bool,
    rollback_key: str,
    project_key: str,
    from_snapshot_key: str,
    to_snapshot_key: str,
) -> tuple[str, ...]:
    issues: list[str] = []
    if existing_rollback_exists:
        issues.append(f"rollback_key already exists: {rollback_key}")
    if project is None:
        issues.append(f"audit project not found: {project_key}")
    if from_snapshot is None:
        issues.append(f"from snapshot not found: {from_snapshot_key}")
    if to_snapshot is None:
        issues.append(f"to snapshot not found: {to_snapshot_key}")
    if from_snapshot_key == to_snapshot_key:
        issues.append("from_snapshot_key and to_snapshot_key must differ")
    if project is not None and from_snapshot is not None and project.id != from_snapshot.project_id:
        issues.append("from snapshot does not belong to the requested project")
    if project is not None and to_snapshot is not None and project.id != to_snapshot.project_id:
        issues.append("to snapshot does not belong to the requested project")
    if (
        from_snapshot is not None
        and to_snapshot is not None
        and from_snapshot.project_id != to_snapshot.project_id
    ):
        issues.append("from snapshot and to snapshot belong to different projects")
    return tuple(dict.fromkeys(issues))


def _result(
    *,
    status: Literal["pass", "fail"],
    execute_requested: bool,
    rollback_key: str,
    project_key: str,
    project_id: UUID | None,
    from_snapshot_key: str,
    from_snapshot_id: UUID | None,
    to_snapshot_key: str,
    to_snapshot_id: UUID | None,
    reason: str,
    requested_by: str | None,
    created_rollback_id: UUID | None,
    impact_summary: dict[str, Any],
    issues: tuple[str, ...],
) -> HisSnapshotRollbackAuditResult:
    return HisSnapshotRollbackAuditResult(
        status=status,
        execute_requested=execute_requested,
        executed=execute_requested and status == "pass",
        dry_run=not execute_requested,
        rollback_key=rollback_key,
        project_key=project_key,
        project_id=project_id,
        from_snapshot_key=from_snapshot_key,
        from_snapshot_id=from_snapshot_id,
        to_snapshot_key=to_snapshot_key,
        to_snapshot_id=to_snapshot_id,
        reason=reason,
        requested_by=requested_by,
        created_rollback_id=created_rollback_id,
        impact_summary=impact_summary,
        issues=issues,
    )


def _summary_table(summary: dict[str, Any]) -> list[str]:
    lines = ["| 指标 | 值 |", "| --- | --- |"]
    if not summary:
        lines.append("| `-` | `-` |")
        return lines
    for key, value in sorted(summary.items()):
        rendered = json.dumps(value, ensure_ascii=False, sort_keys=True)
        lines.append(f"| `{key}` | `{rendered}` |")
    return lines
