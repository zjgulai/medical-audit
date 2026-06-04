from __future__ import annotations

import json
from collections import Counter
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from medical_audit_kb.audit.charge_rule_001 import DEFAULT_RULE_VERSION_KEY, RULE_KEY
from medical_audit_kb.db.engine import create_session_factory
from medical_audit_kb.db.models import (
    AuditDataSnapshot,
    AuditFinding,
    AuditProject,
    AuditRun,
    AuditTask,
    FindingEvidenceItem,
    HisSourceBatch,
    HisStagingRow,
    HisTableSchema,
    RuleVersion,
)
from medical_audit_kb.db.repositories import HisIngestionRepository
from medical_audit_kb.his.mapping_validation import (
    validate_charging_compliance_field_mappings,
)


class HisStagingAcceptanceCheck(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    status: Literal["pass", "fail"]
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class HisStagingAcceptanceResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Literal["pass", "fail"]
    ready_for_production_staging: bool
    project_key: str
    project_id: UUID | None
    source_batch_key: str
    source_batch_id: UUID | None
    snapshot_key: str
    snapshot_id: UUID | None
    audit_task_key: str
    audit_run_key: str
    rule_version_key: str
    rollback_target_snapshot_key: str | None
    summary: dict[str, Any]
    checks: tuple[HisStagingAcceptanceCheck, ...]
    issues: tuple[str, ...]


async def audit_his_staging_acceptance_to_database(
    *,
    database_url: str,
    project_key: str,
    source_batch_key: str,
    snapshot_key: str,
    audit_task_key: str,
    audit_run_key: str,
    rule_version_key: str = DEFAULT_RULE_VERSION_KEY,
    expected_tables: tuple[str, ...] = (),
    min_staged_rows: int = 1,
    min_findings: int = 0,
    rollback_target_snapshot_key: str | None = None,
) -> HisStagingAcceptanceResult:
    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        return await audit_his_staging_acceptance_with_engine(
            engine=engine,
            project_key=project_key,
            source_batch_key=source_batch_key,
            snapshot_key=snapshot_key,
            audit_task_key=audit_task_key,
            audit_run_key=audit_run_key,
            rule_version_key=rule_version_key,
            expected_tables=expected_tables,
            min_staged_rows=min_staged_rows,
            min_findings=min_findings,
            rollback_target_snapshot_key=rollback_target_snapshot_key,
        )
    finally:
        await engine.dispose()


async def audit_his_staging_acceptance_with_engine(
    *,
    engine: AsyncEngine,
    project_key: str,
    source_batch_key: str,
    snapshot_key: str,
    audit_task_key: str,
    audit_run_key: str,
    rule_version_key: str = DEFAULT_RULE_VERSION_KEY,
    expected_tables: tuple[str, ...] = (),
    min_staged_rows: int = 1,
    min_findings: int = 0,
    rollback_target_snapshot_key: str | None = None,
) -> HisStagingAcceptanceResult:
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        project = await _get_project(session, project_key)
        source_batch = await _get_source_batch(session, source_batch_key)
        snapshot = await _get_snapshot(session, snapshot_key)
        task = await _get_task(session, audit_task_key)
        run = await _get_run(session, audit_run_key)
        rule_version = await _get_rule_version(session, rule_version_key)
        rollback_target = (
            await _get_snapshot(session, rollback_target_snapshot_key)
            if rollback_target_snapshot_key is not None
            else None
        )

        table_schemas = await _table_schemas(session, source_batch)
        staging_rows = await _staging_rows(session, source_batch)
        field_mappings = await HisIngestionRepository(session).list_field_mappings_for_batch(
            source_batch_key
        )
        finding_count = await _finding_count(session, run)
        evidence_item_count = await _evidence_item_count(session, run)
        summary = {
            "table_schema_count": len(table_schemas),
            "staging_row_count": len(staging_rows),
            "staged_row_count": sum(1 for row in staging_rows if row.status == "staged"),
            "active_mapping_count": sum(
                1 for mapping in field_mappings if mapping.status == "active"
            ),
            "finding_count": finding_count,
            "evidence_item_count": evidence_item_count,
            "row_count_by_table": dict(Counter(row.table_name for row in staging_rows)),
            "schema_tables": sorted(schema.table_name for schema in table_schemas),
        }
        checks = _build_checks(
            project=project,
            source_batch=source_batch,
            snapshot=snapshot,
            task=task,
            run=run,
            rule_version=rule_version,
            rollback_target=rollback_target,
            project_key=project_key,
            source_batch_key=source_batch_key,
            snapshot_key=snapshot_key,
            audit_task_key=audit_task_key,
            audit_run_key=audit_run_key,
            rule_version_key=rule_version_key,
            rollback_target_snapshot_key=rollback_target_snapshot_key,
            table_schemas=tuple(table_schemas),
            staging_rows=tuple(staging_rows),
            field_mappings=tuple(field_mappings),
            expected_tables=expected_tables,
            min_staged_rows=min_staged_rows,
            min_findings=min_findings,
            finding_count=finding_count,
            evidence_item_count=evidence_item_count,
        )
        issues = tuple(check.message for check in checks if check.status == "fail")
        return HisStagingAcceptanceResult(
            status="pass" if not issues else "fail",
            ready_for_production_staging=not issues,
            project_key=project_key,
            project_id=project.id if project is not None else None,
            source_batch_key=source_batch_key,
            source_batch_id=source_batch.id if source_batch is not None else None,
            snapshot_key=snapshot_key,
            snapshot_id=snapshot.id if snapshot is not None else None,
            audit_task_key=audit_task_key,
            audit_run_key=audit_run_key,
            rule_version_key=rule_version_key,
            rollback_target_snapshot_key=rollback_target_snapshot_key,
            summary=summary,
            checks=checks,
            issues=issues,
        )


def render_his_staging_acceptance_markdown(result: HisStagingAcceptanceResult) -> str:
    lines = [
        "# HIS 生产 staging 执行验收报告",
        "",
        f"- 总体状态：`{result.status.upper()}`",
        f"- ready_for_production_staging：`{str(result.ready_for_production_staging).lower()}`",
        f"- project_key：`{result.project_key}`",
        f"- project_id：`{result.project_id or '-'}`",
        f"- source_batch_key：`{result.source_batch_key}`",
        f"- source_batch_id：`{result.source_batch_id or '-'}`",
        f"- snapshot_key：`{result.snapshot_key}`",
        f"- snapshot_id：`{result.snapshot_id or '-'}`",
        f"- audit_task_key：`{result.audit_task_key}`",
        f"- audit_run_key：`{result.audit_run_key}`",
        f"- rule_version_key：`{result.rule_version_key}`",
        f"- rollback_target_snapshot_key：`{result.rollback_target_snapshot_key or '-'}`",
    ]
    if result.issues:
        lines.extend(["", "## 阻断问题"])
        lines.extend(f"- {issue}" for issue in result.issues)
    lines.extend(
        [
            "",
            "## 验收检查",
            "",
            "| 检查项 | 状态 | 说明 |",
            "| --- | --- | --- |",
        ]
    )
    for check in result.checks:
        lines.append(f"| `{check.name}` | `{check.status.upper()}` | {check.message} |")
    lines.extend(["", "## 摘要", ""])
    lines.extend(_summary_table(result.summary))
    return "\n".join(lines) + "\n"


def his_staging_acceptance_result_json(result: HisStagingAcceptanceResult) -> str:
    return json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n"


async def _get_project(session: AsyncSession, project_key: str) -> AuditProject | None:
    return (
        await session.execute(select(AuditProject).where(AuditProject.project_key == project_key))
    ).scalar_one_or_none()


async def _get_source_batch(
    session: AsyncSession,
    source_batch_key: str,
) -> HisSourceBatch | None:
    return (
        await session.execute(
            select(HisSourceBatch).where(HisSourceBatch.batch_key == source_batch_key)
        )
    ).scalar_one_or_none()


async def _get_snapshot(
    session: AsyncSession,
    snapshot_key: str | None,
) -> AuditDataSnapshot | None:
    if snapshot_key is None:
        return None
    return (
        await session.execute(
            select(AuditDataSnapshot).where(AuditDataSnapshot.snapshot_key == snapshot_key)
        )
    ).scalar_one_or_none()


async def _get_task(session: AsyncSession, audit_task_key: str) -> AuditTask | None:
    return (
        await session.execute(select(AuditTask).where(AuditTask.task_key == audit_task_key))
    ).scalar_one_or_none()


async def _get_run(session: AsyncSession, audit_run_key: str) -> AuditRun | None:
    return (
        await session.execute(select(AuditRun).where(AuditRun.run_key == audit_run_key))
    ).scalar_one_or_none()


async def _get_rule_version(
    session: AsyncSession,
    rule_version_key: str,
) -> RuleVersion | None:
    return (
        await session.execute(
            select(RuleVersion).where(RuleVersion.version_key == rule_version_key)
        )
    ).scalar_one_or_none()


async def _table_schemas(
    session: AsyncSession,
    source_batch: HisSourceBatch | None,
) -> list[HisTableSchema]:
    if source_batch is None:
        return []
    result = await session.execute(
        select(HisTableSchema)
        .where(HisTableSchema.source_batch_id == source_batch.id)
        .order_by(HisTableSchema.table_name.asc())
    )
    return list(result.scalars().all())


async def _staging_rows(
    session: AsyncSession,
    source_batch: HisSourceBatch | None,
) -> list[HisStagingRow]:
    if source_batch is None:
        return []
    result = await session.execute(
        select(HisStagingRow).where(HisStagingRow.source_batch_id == source_batch.id)
    )
    return list(result.scalars().all())


async def _finding_count(session: AsyncSession, run: AuditRun | None) -> int:
    if run is None:
        return 0
    result = await session.execute(
        select(func.count()).select_from(AuditFinding).where(AuditFinding.audit_run_id == run.id)
    )
    return int(result.scalar_one())


async def _evidence_item_count(session: AsyncSession, run: AuditRun | None) -> int:
    if run is None:
        return 0
    result = await session.execute(
        select(func.count())
        .select_from(FindingEvidenceItem)
        .join(AuditFinding)
        .where(AuditFinding.audit_run_id == run.id)
    )
    return int(result.scalar_one())


def _build_checks(
    *,
    project: AuditProject | None,
    source_batch: HisSourceBatch | None,
    snapshot: AuditDataSnapshot | None,
    task: AuditTask | None,
    run: AuditRun | None,
    rule_version: RuleVersion | None,
    rollback_target: AuditDataSnapshot | None,
    project_key: str,
    source_batch_key: str,
    snapshot_key: str,
    audit_task_key: str,
    audit_run_key: str,
    rule_version_key: str,
    rollback_target_snapshot_key: str | None,
    table_schemas: tuple[HisTableSchema, ...],
    staging_rows: tuple[HisStagingRow, ...],
    field_mappings: tuple[object, ...],
    expected_tables: tuple[str, ...],
    min_staged_rows: int,
    min_findings: int,
    finding_count: int,
    evidence_item_count: int,
) -> tuple[HisStagingAcceptanceCheck, ...]:
    mapping_report = validate_charging_compliance_field_mappings(field_mappings)
    staged_row_count = sum(1 for row in staging_rows if row.status == "staged")
    schema_tables = {schema.table_name for schema in table_schemas}
    row_tables = {row.table_name for row in staging_rows}
    checks = [
        _check(project is not None, "project", f"audit project not found: {project_key}"),
        _check(
            source_batch is not None,
            "source-batch",
            f"his source batch not found: {source_batch_key}",
        ),
        _check(
            source_batch is None or project is None or source_batch.project_id == project.id,
            "source-batch-project",
            "his source batch does not belong to the requested project",
        ),
        _check(bool(table_schemas), "table-schema", "no HIS table schemas found for source batch"),
        _check(
            staged_row_count >= min_staged_rows,
            "staging-rows",
            f"staged row count {staged_row_count} below required {min_staged_rows}",
        ),
        _check(
            set(expected_tables).issubset(schema_tables | row_tables),
            "expected-tables",
            "expected table missing from schemas or staging rows",
            details={"expected_tables": sorted(expected_tables)},
        ),
        _check(
            mapping_report.can_create_snapshot,
            "field-mapping-gate",
            "charging compliance field mapping gate failed",
            details=mapping_report.model_dump(mode="json"),
        ),
        _check(snapshot is not None, "snapshot", f"audit snapshot not found: {snapshot_key}"),
        _check(
            snapshot is None or project is None or snapshot.project_id == project.id,
            "snapshot-project",
            "audit snapshot does not belong to the requested project",
        ),
        _check(
            snapshot is None or snapshot.source_batch_key == source_batch_key,
            "snapshot-source-batch",
            "audit snapshot source_batch_key does not match source batch",
        ),
        _check(task is not None, "audit-task", f"audit task not found: {audit_task_key}"),
        _check(
            task is None or snapshot is None or task.snapshot_id == snapshot.id,
            "audit-task-snapshot",
            "audit task is not bound to the requested snapshot",
        ),
        _check(run is not None, "audit-run", f"audit run not found: {audit_run_key}"),
        _check(
            run is None or task is None or run.audit_task_id == task.id,
            "audit-run-task",
            "audit run is not bound to the requested audit task",
        ),
        _check(
            run is None or snapshot is None or run.snapshot_id == snapshot.id,
            "audit-run-snapshot",
            "audit run is not bound to the requested snapshot",
        ),
        _check(
            rule_version is not None,
            "rule-version",
            f"rule version not found: {rule_version_key}",
        ),
        _check(
            rule_version is None or rule_version.rule_key == RULE_KEY,
            "rule-version-rule-key",
            f"rule version does not belong to {RULE_KEY}",
        ),
        _check(
            run is None or run.rule_version_key == rule_version_key,
            "audit-run-rule-version",
            "audit run rule_version_key does not match requested rule version",
        ),
        _check(
            finding_count >= min_findings,
            "finding-count",
            f"finding count {finding_count} below required {min_findings}",
        ),
        _check(
            evidence_item_count >= finding_count,
            "finding-evidence",
            "finding evidence item count is lower than finding count",
        ),
    ]
    if rollback_target_snapshot_key is not None:
        checks.extend(
            [
                _check(
                    rollback_target is not None,
                    "rollback-target",
                    f"rollback target snapshot not found: {rollback_target_snapshot_key}",
                ),
                _check(
                    rollback_target is None
                    or project is None
                    or rollback_target.project_id == project.id,
                    "rollback-target-project",
                    "rollback target snapshot does not belong to the requested project",
                ),
                _check(
                    rollback_target is None
                    or snapshot is None
                    or rollback_target.id != snapshot.id,
                    "rollback-target-distinct",
                    "rollback target snapshot must differ from accepted snapshot",
                ),
            ]
        )
    return tuple(checks)


def _check(
    condition: bool,
    name: str,
    failure_message: str,
    *,
    details: dict[str, Any] | None = None,
) -> HisStagingAcceptanceCheck:
    return HisStagingAcceptanceCheck(
        name=name,
        status="pass" if condition else "fail",
        message="ok" if condition else failure_message,
        details=details or {},
    )


def _summary_table(summary: dict[str, Any]) -> list[str]:
    lines = ["| 指标 | 值 |", "| --- | --- |"]
    for key, value in sorted(summary.items()):
        rendered = json.dumps(value, ensure_ascii=False, sort_keys=True)
        lines.append(f"| `{key}` | `{rendered}` |")
    return lines
