from __future__ import annotations

import json
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from medical_audit_kb.audit.charge_rule_001 import (
    DEFAULT_RULE_VERSION_KEY,
    RULE_KEY,
    build_audit_finding_payloads,
    evaluate_charge_rule_001,
)
from medical_audit_kb.audit.charge_rule_001_staging import (
    ChargeRule001StagingInputResult,
    build_charge_rule_001_records_from_staging,
)
from medical_audit_kb.db.engine import create_schema, create_session_factory
from medical_audit_kb.db.models import (
    AuditDataSnapshot,
    AuditRun,
    AuditTask,
    HisSourceBatch,
    RuleVersion,
)
from medical_audit_kb.db.repositories import AuditWorkflowRepository, HisIngestionRepository
from medical_audit_kb.domain.schemas import FindingEvidenceItemCreate


class ChargeRule001StagingRunIssue(BaseModel):
    model_config = ConfigDict(frozen=True)

    severity: Literal["warning", "error"]
    issue_type: str
    table_name: str | None
    row_number: int | None
    message: str


class ChargeRule001StagingRunResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Literal["pass", "fail"]
    execute_requested: bool
    executed: bool
    dry_run: bool
    source_batch_key: str
    source_batch_id: UUID | None
    audit_task_key: str
    audit_run_key: str
    snapshot_key: str | None
    rule_version_key: str
    input_summary: dict[str, int]
    rule_summary: dict[str, int]
    finding_keys: tuple[str, ...]
    existing_finding_keys: tuple[str, ...]
    created_finding_count: int
    created_evidence_item_count: int
    issues: tuple[str, ...]
    staging_issues: tuple[ChargeRule001StagingRunIssue, ...]


async def run_charge_rule_001_from_staging_database(
    *,
    database_url: str,
    source_batch_key: str,
    audit_task_key: str,
    audit_run_key: str,
    rule_version_key: str = DEFAULT_RULE_VERSION_KEY,
    execute: bool = False,
    create_schema_if_missing: bool = False,
) -> ChargeRule001StagingRunResult:
    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        return await run_charge_rule_001_from_staging_with_engine(
            engine=engine,
            source_batch_key=source_batch_key,
            audit_task_key=audit_task_key,
            audit_run_key=audit_run_key,
            rule_version_key=rule_version_key,
            execute=execute,
            create_schema_if_missing=create_schema_if_missing,
        )
    finally:
        await engine.dispose()


async def run_charge_rule_001_from_staging_with_engine(
    *,
    engine: AsyncEngine,
    source_batch_key: str,
    audit_task_key: str,
    audit_run_key: str,
    rule_version_key: str = DEFAULT_RULE_VERSION_KEY,
    execute: bool = False,
    create_schema_if_missing: bool = False,
) -> ChargeRule001StagingRunResult:
    if create_schema_if_missing:
        await create_schema(engine)

    session_factory = create_session_factory(engine)
    async with session_factory() as session, session.begin():
        source_batch = (
            await session.execute(
                select(HisSourceBatch).where(HisSourceBatch.batch_key == source_batch_key)
            )
        ).scalar_one_or_none()
        task = (
            await session.execute(select(AuditTask).where(AuditTask.task_key == audit_task_key))
        ).scalar_one_or_none()
        run = (
            await session.execute(select(AuditRun).where(AuditRun.run_key == audit_run_key))
        ).scalar_one_or_none()
        rule_version = (
            await session.execute(
                select(RuleVersion).where(RuleVersion.version_key == rule_version_key)
            )
        ).scalar_one_or_none()
        snapshot = await _load_snapshot(task=task, run=run, engine_session=session)

        his_repository = HisIngestionRepository(session)
        staging_rows = await his_repository.list_staging_rows_for_batch(source_batch_key)
        field_mappings = await his_repository.list_field_mappings_for_batch(source_batch_key)
        input_result = build_charge_rule_001_records_from_staging(
            staging_rows,
            field_mappings,
            source_batch_key=source_batch_key,
        )

        context_issues = _context_issues(
            source_batch=source_batch,
            task=task,
            run=run,
            snapshot=snapshot,
            rule_version=rule_version,
            source_batch_key=source_batch_key,
            rule_version_key=rule_version_key,
        )
        conversion_issues = (
            ("staging input conversion failed",) if input_result.status == "fail" else ()
        )
        issues = (*context_issues, *conversion_issues)
        if (
            issues
            or source_batch is None
            or task is None
            or run is None
            or snapshot is None
            or rule_version is None
        ):
            return _result(
                status="fail",
                execute_requested=execute,
                source_batch_key=source_batch_key,
                source_batch_id=source_batch.id if source_batch is not None else None,
                audit_task_key=audit_task_key,
                audit_run_key=audit_run_key,
                snapshot_key=snapshot.snapshot_key if snapshot is not None else None,
                rule_version_key=rule_version_key,
                input_result=input_result,
                rule_summary={},
                finding_keys=(),
                existing_finding_keys=(),
                created_finding_count=0,
                created_evidence_item_count=0,
                issues=issues,
            )

        rule_result = evaluate_charge_rule_001(
            input_result.records,
            audit_task_key=task.task_key,
            audit_run_key=run.run_key,
            snapshot_key=snapshot.snapshot_key,
            rule_version_key=rule_version.version_key,
            knowledge_index_version_key=run.knowledge_index_version_key,
        )
        payloads = build_audit_finding_payloads(
            rule_result,
            audit_run_id=run.id,
            audit_task_id=task.id,
            rule_version_id=rule_version.id,
            snapshot_id=snapshot.id,
        )

        workflow_repository = AuditWorkflowRepository(session)
        existing_finding_keys = []
        for payload in payloads:
            if await workflow_repository.get_finding_by_key(payload.finding_key) is not None:
                existing_finding_keys.append(payload.finding_key)
        duplicate_issues = tuple(
            f"audit finding already exists: {finding_key}" for finding_key in existing_finding_keys
        )
        if duplicate_issues or not execute:
            return _result(
                status="fail" if duplicate_issues else "pass",
                execute_requested=execute,
                source_batch_key=source_batch_key,
                source_batch_id=source_batch.id,
                audit_task_key=audit_task_key,
                audit_run_key=audit_run_key,
                snapshot_key=snapshot.snapshot_key,
                rule_version_key=rule_version.version_key,
                input_result=input_result,
                rule_summary=dict(rule_result.summary),
                finding_keys=tuple(payload.finding_key for payload in payloads),
                existing_finding_keys=tuple(existing_finding_keys),
                created_finding_count=0,
                created_evidence_item_count=0,
                issues=duplicate_issues,
            )

        created_finding_count = 0
        created_evidence_item_count = 0
        for payload, rule_finding in zip(payloads, rule_result.findings, strict=True):
            finding = await workflow_repository.create_finding(payload)
            created_finding_count += 1
            await workflow_repository.add_finding_evidence_item(
                FindingEvidenceItemCreate(
                    audit_finding_id=finding.id,
                    evidence_type="rule-rationale",
                    source_package_version_key=rule_finding.source_package_version_key,
                    index_version_key=rule_finding.knowledge_index_version_key,
                    citation_id=f"{RULE_KEY}-staging-rationale",
                    locator={
                        "rule_key": RULE_KEY,
                        "rule_version_key": rule_version.version_key,
                        "finding_key": finding.finding_key,
                    },
                    snippet=rule_finding.knowledge_evidence_snippet,
                    metadata={"source": "charge-rule-001-staging-run"},
                )
            )
            created_evidence_item_count += 1

        return _result(
            status="pass",
            execute_requested=execute,
            source_batch_key=source_batch_key,
            source_batch_id=source_batch.id,
            audit_task_key=audit_task_key,
            audit_run_key=audit_run_key,
            snapshot_key=snapshot.snapshot_key,
            rule_version_key=rule_version.version_key,
            input_result=input_result,
            rule_summary=dict(rule_result.summary),
            finding_keys=tuple(payload.finding_key for payload in payloads),
            existing_finding_keys=(),
            created_finding_count=created_finding_count,
            created_evidence_item_count=created_evidence_item_count,
            issues=(),
        )


def render_charge_rule_001_staging_run_markdown(result: ChargeRule001StagingRunResult) -> str:
    lines = [
        "# CHARGE-RULE-001 staging 规则运行报告",
        "",
        f"- 总体状态：`{result.status.upper()}`",
        f"- 请求写入：`{str(result.execute_requested).lower()}`",
        f"- 执行写入：`{str(result.executed).lower()}`",
        f"- dry_run：`{str(result.dry_run).lower()}`",
        f"- source_batch_key：`{result.source_batch_key}`",
        f"- source_batch_id：`{result.source_batch_id or '-'}`",
        f"- audit_task_key：`{result.audit_task_key}`",
        f"- audit_run_key：`{result.audit_run_key}`",
        f"- snapshot_key：`{result.snapshot_key or '-'}`",
        f"- rule_version_key：`{result.rule_version_key}`",
        f"- 计划疑点数：`{len(result.finding_keys)}`",
        f"- 已存在疑点数：`{len(result.existing_finding_keys)}`",
        f"- 写入疑点数：`{result.created_finding_count}`",
        f"- 写入证据项数：`{result.created_evidence_item_count}`",
    ]
    if result.issues:
        lines.extend(["", "## 阻断问题"])
        lines.extend(f"- {issue}" for issue in result.issues)
    lines.extend(["", "## staging 转换摘要", ""])
    lines.extend(_summary_table(result.input_summary))
    lines.extend(["", "## 规则执行摘要", ""])
    lines.extend(_summary_table(result.rule_summary))
    if result.staging_issues:
        lines.extend(
            [
                "",
                "## staging 转换问题",
                "",
                "| 等级 | 类型 | 表 | 行号 | 说明 |",
                "| --- | --- | --- | ---: | --- |",
            ]
        )
        for issue in result.staging_issues:
            lines.append(
                f"| `{issue.severity}` | `{issue.issue_type}` | "
                f"`{issue.table_name or '-'}` | {issue.row_number or 0} | {issue.message} |"
            )
    if result.finding_keys:
        lines.extend(["", "## 疑点键"])
        lines.extend(f"- `{finding_key}`" for finding_key in result.finding_keys)
    return "\n".join(lines) + "\n"


def charge_rule_001_staging_run_result_json(result: ChargeRule001StagingRunResult) -> str:
    return json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n"


async def _load_snapshot(
    *,
    task: AuditTask | None,
    run: AuditRun | None,
    engine_session: AsyncSession,
) -> AuditDataSnapshot | None:
    if task is not None:
        return await engine_session.get(AuditDataSnapshot, task.snapshot_id)
    if run is not None:
        return await engine_session.get(AuditDataSnapshot, run.snapshot_id)
    return None


def _context_issues(
    *,
    source_batch: HisSourceBatch | None,
    task: AuditTask | None,
    run: AuditRun | None,
    snapshot: AuditDataSnapshot | None,
    rule_version: RuleVersion | None,
    source_batch_key: str,
    rule_version_key: str,
) -> tuple[str, ...]:
    issues: list[str] = []
    if source_batch is None:
        issues.append(f"his source batch not found: {source_batch_key}")
    if task is None:
        issues.append("audit task not found")
    if run is None:
        issues.append("audit run not found")
    if snapshot is None:
        issues.append("audit snapshot not found")
    if rule_version is None:
        issues.append(f"rule version not found: {rule_version_key}")
    if rule_version is not None and rule_version.rule_key != RULE_KEY:
        issues.append(
            f"rule version {rule_version.version_key} belongs to {rule_version.rule_key}, "
            f"not {RULE_KEY}"
        )
    if run is not None and run.rule_version_key != rule_version_key:
        issues.append(
            f"audit run rule_version_key mismatch: run={run.rule_version_key}, "
            f"requested={rule_version_key}"
        )
    if task is not None and run is not None and run.audit_task_id != task.id:
        issues.append("audit run is not bound to the requested audit task")
    if task is not None and run is not None and task.snapshot_id != run.snapshot_id:
        issues.append("audit task and audit run snapshots differ")
    if snapshot is not None and snapshot.source_batch_key != source_batch_key:
        issues.append(
            f"snapshot source_batch_key mismatch: snapshot={snapshot.source_batch_key}, "
            f"requested={source_batch_key}"
        )
    if (
        source_batch is not None
        and snapshot is not None
        and source_batch.project_id != snapshot.project_id
    ):
        issues.append("his source batch and audit snapshot belong to different projects")
    return tuple(dict.fromkeys(issues))


def _result(
    *,
    status: Literal["pass", "fail"],
    execute_requested: bool,
    source_batch_key: str,
    source_batch_id: UUID | None,
    audit_task_key: str,
    audit_run_key: str,
    snapshot_key: str | None,
    rule_version_key: str,
    input_result: ChargeRule001StagingInputResult,
    rule_summary: dict[str, int],
    finding_keys: tuple[str, ...],
    existing_finding_keys: tuple[str, ...],
    created_finding_count: int,
    created_evidence_item_count: int,
    issues: tuple[str, ...],
) -> ChargeRule001StagingRunResult:
    return ChargeRule001StagingRunResult(
        status=status,
        execute_requested=execute_requested,
        executed=execute_requested and status == "pass",
        dry_run=not execute_requested,
        source_batch_key=source_batch_key,
        source_batch_id=source_batch_id,
        audit_task_key=audit_task_key,
        audit_run_key=audit_run_key,
        snapshot_key=snapshot_key,
        rule_version_key=rule_version_key,
        input_summary=dict(input_result.summary),
        rule_summary=rule_summary,
        finding_keys=finding_keys,
        existing_finding_keys=existing_finding_keys,
        created_finding_count=created_finding_count,
        created_evidence_item_count=created_evidence_item_count,
        issues=issues,
        staging_issues=tuple(
            ChargeRule001StagingRunIssue(
                severity=issue.severity,
                issue_type=issue.issue_type,
                table_name=issue.table_name,
                row_number=issue.row_number,
                message=issue.message,
            )
            for issue in input_result.issues
        ),
    )


def _summary_table(summary: dict[str, int]) -> list[str]:
    lines = ["| 指标 | 数量 |", "| --- | ---: |"]
    if not summary:
        lines.append("| `-` | 0 |")
        return lines
    for key, value in sorted(summary.items()):
        lines.append(f"| `{key}` | {value} |")
    return lines
