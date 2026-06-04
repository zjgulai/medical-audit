from __future__ import annotations

import json
from collections import Counter
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import selectinload

from medical_audit_kb.db.engine import create_session_factory
from medical_audit_kb.db.models import (
    AuditFinding,
    AuditProject,
    AuditRun,
    AuditTask,
    ReviewTask,
)

RESOLVED_REVIEW_STATUSES = (
    "confirmed-violation",
    "not-violation",
    "rule-issue",
    "data-issue",
    "closed",
)
APPROVED_OWNER_SIGNOFF_STATUSES = ("approved", "confirmed", "accepted")
SUCCESSFUL_RUN_STATUSES = ("succeeded", "completed", "accepted")


class CaseReviewReportGateCheck(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    status: Literal["pass", "fail"]
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class CaseReviewReportGateResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Literal["pass", "fail"]
    ready_for_formal_report: bool
    project_key: str
    project_id: UUID | None
    audit_task_key: str
    audit_task_id: UUID | None
    audit_run_key: str
    audit_run_id: UUID | None
    summary: dict[str, Any]
    checks: tuple[CaseReviewReportGateCheck, ...]
    issues: tuple[str, ...]


async def audit_case_review_report_gate_to_database(
    *,
    database_url: str,
    project_key: str,
    audit_task_key: str,
    audit_run_key: str,
    min_findings: int = 0,
    resolved_review_statuses: tuple[str, ...] = RESOLVED_REVIEW_STATUSES,
    require_owner_signoff: bool = True,
    require_workpaper: bool = True,
) -> CaseReviewReportGateResult:
    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        return await audit_case_review_report_gate_with_engine(
            engine=engine,
            project_key=project_key,
            audit_task_key=audit_task_key,
            audit_run_key=audit_run_key,
            min_findings=min_findings,
            resolved_review_statuses=resolved_review_statuses,
            require_owner_signoff=require_owner_signoff,
            require_workpaper=require_workpaper,
        )
    finally:
        await engine.dispose()


async def audit_case_review_report_gate_with_engine(
    *,
    engine: AsyncEngine,
    project_key: str,
    audit_task_key: str,
    audit_run_key: str,
    min_findings: int = 0,
    resolved_review_statuses: tuple[str, ...] = RESOLVED_REVIEW_STATUSES,
    require_owner_signoff: bool = True,
    require_workpaper: bool = True,
) -> CaseReviewReportGateResult:
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        project = await _get_project(session, project_key)
        audit_task = await _get_audit_task(session, audit_task_key)
        audit_run = await _get_audit_run(session, audit_run_key)
        findings = await _list_findings_for_run(session, audit_run)
        review_tasks = await _list_review_tasks(session, findings)
        review_tasks_by_id = {task.id: task for task in review_tasks}
        summary = _build_summary(
            audit_task=audit_task,
            findings=tuple(findings),
            review_tasks=tuple(review_tasks),
            review_tasks_by_id=review_tasks_by_id,
        )
        checks = _build_checks(
            project=project,
            audit_task=audit_task,
            audit_run=audit_run,
            findings=tuple(findings),
            review_tasks_by_id=review_tasks_by_id,
            project_key=project_key,
            audit_task_key=audit_task_key,
            audit_run_key=audit_run_key,
            min_findings=min_findings,
            resolved_review_statuses=resolved_review_statuses,
            require_owner_signoff=require_owner_signoff,
            require_workpaper=require_workpaper,
        )
        issues = tuple(check.message for check in checks if check.status == "fail")
        return CaseReviewReportGateResult(
            status="pass" if not issues else "fail",
            ready_for_formal_report=not issues,
            project_key=project_key,
            project_id=project.id if project is not None else None,
            audit_task_key=audit_task_key,
            audit_task_id=audit_task.id if audit_task is not None else None,
            audit_run_key=audit_run_key,
            audit_run_id=audit_run.id if audit_run is not None else None,
            summary=summary,
            checks=checks,
            issues=issues,
        )


def render_case_review_report_gate_markdown(result: CaseReviewReportGateResult) -> str:
    lines = [
        "# 案件级复核报告门禁",
        "",
        f"- 总体状态：`{result.status.upper()}`",
        f"- ready_for_formal_report：`{str(result.ready_for_formal_report).lower()}`",
        f"- project_key：`{result.project_key}`",
        f"- project_id：`{result.project_id or '-'}`",
        f"- audit_task_key：`{result.audit_task_key}`",
        f"- audit_task_id：`{result.audit_task_id or '-'}`",
        f"- audit_run_key：`{result.audit_run_key}`",
        f"- audit_run_id：`{result.audit_run_id or '-'}`",
    ]
    if result.issues:
        lines.extend(["", "## 阻断问题"])
        lines.extend(f"- {issue}" for issue in result.issues)
    lines.extend(
        [
            "",
            "## 门禁检查",
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


def case_review_report_gate_result_json(result: CaseReviewReportGateResult) -> str:
    return json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n"


async def _get_project(session: AsyncSession, project_key: str) -> AuditProject | None:
    return (
        await session.execute(select(AuditProject).where(AuditProject.project_key == project_key))
    ).scalar_one_or_none()


async def _get_audit_task(session: AsyncSession, audit_task_key: str) -> AuditTask | None:
    return (
        await session.execute(select(AuditTask).where(AuditTask.task_key == audit_task_key))
    ).scalar_one_or_none()


async def _get_audit_run(session: AsyncSession, audit_run_key: str) -> AuditRun | None:
    return (
        await session.execute(select(AuditRun).where(AuditRun.run_key == audit_run_key))
    ).scalar_one_or_none()


async def _list_findings_for_run(
    session: AsyncSession,
    audit_run: AuditRun | None,
) -> list[AuditFinding]:
    if audit_run is None:
        return []
    result = await session.execute(
        select(AuditFinding)
        .options(selectinload(AuditFinding.evidence_items))
        .where(AuditFinding.audit_run_id == audit_run.id)
        .order_by(AuditFinding.created_at.asc())
    )
    return list(result.scalars().all())


async def _list_review_tasks(
    session: AsyncSession,
    findings: list[AuditFinding],
) -> list[ReviewTask]:
    task_ids = sorted({finding.review_task_id for finding in findings if finding.review_task_id})
    if not task_ids:
        return []
    result = await session.execute(select(ReviewTask).where(ReviewTask.id.in_(task_ids)))
    return list(result.scalars().all())


def _build_summary(
    *,
    audit_task: AuditTask | None,
    findings: tuple[AuditFinding, ...],
    review_tasks: tuple[ReviewTask, ...],
    review_tasks_by_id: dict[UUID, ReviewTask],
) -> dict[str, Any]:
    return {
        "finding_count": len(findings),
        "evidence_item_count": sum(len(finding.evidence_items) for finding in findings),
        "findings_with_evidence_count": sum(1 for finding in findings if finding.evidence_items),
        "findings_with_review_task_count": sum(
            1 for finding in findings if finding.review_task_id is not None
        ),
        "review_status_counts": dict(Counter(finding.review_status for finding in findings)),
        "review_task_status_counts": dict(Counter(task.status for task in review_tasks)),
        "confirmed_violation_count": sum(
            1 for finding in findings if finding.review_status == "confirmed-violation"
        ),
        "workpaper_ready_count": sum(
            1 for finding in findings if _finding_has_ready_workpaper(finding, review_tasks_by_id)
        ),
        "owner_signoff": _owner_signoff_summary(audit_task),
    }


def _build_checks(
    *,
    project: AuditProject | None,
    audit_task: AuditTask | None,
    audit_run: AuditRun | None,
    findings: tuple[AuditFinding, ...],
    review_tasks_by_id: dict[UUID, ReviewTask],
    project_key: str,
    audit_task_key: str,
    audit_run_key: str,
    min_findings: int,
    resolved_review_statuses: tuple[str, ...],
    require_owner_signoff: bool,
    require_workpaper: bool,
) -> tuple[CaseReviewReportGateCheck, ...]:
    missing_evidence = [finding.finding_key for finding in findings if not finding.evidence_items]
    unresolved_findings = [
        finding.finding_key
        for finding in findings
        if finding.review_status not in resolved_review_statuses
    ]
    unlinked_findings = [
        finding.finding_key for finding in findings if finding.review_task_id is None
    ]
    missing_review_tasks = [
        finding.finding_key
        for finding in findings
        if finding.review_task_id is not None and finding.review_task_id not in review_tasks_by_id
    ]
    unresolved_review_tasks = [
        task.external_task_id
        for task in review_tasks_by_id.values()
        if task.status not in resolved_review_statuses
    ]
    status_mismatches = [
        finding.finding_key
        for finding in findings
        if finding.review_task_id is not None
        and finding.review_task_id in review_tasks_by_id
        and finding.review_status != review_tasks_by_id[finding.review_task_id].status
    ]
    incomplete_review_notes = [
        task.external_task_id
        for task in review_tasks_by_id.values()
        if not task.reviewer_note.strip() or not task.conclusion.strip()
    ]
    missing_workpapers = [
        finding.finding_key
        for finding in findings
        if finding.review_status == "confirmed-violation"
        and not _finding_has_ready_workpaper(finding, review_tasks_by_id)
    ]
    checks = [
        _check(project is not None, "project", f"audit project not found: {project_key}"),
        _check(
            audit_task is not None,
            "audit-task",
            f"audit task not found: {audit_task_key}",
        ),
        _check(
            audit_task is None or project is None or audit_task.project_id == project.id,
            "audit-task-project",
            "audit task does not belong to the requested project",
        ),
        _check(audit_run is not None, "audit-run", f"audit run not found: {audit_run_key}"),
        _check(
            audit_run is None or audit_task is None or audit_run.audit_task_id == audit_task.id,
            "audit-run-task",
            "audit run is not bound to the requested audit task",
        ),
        _check(
            audit_run is None or audit_run.status in SUCCESSFUL_RUN_STATUSES,
            "audit-run-status",
            "audit run is not in a successful terminal status",
            details={"allowed_statuses": list(SUCCESSFUL_RUN_STATUSES)},
        ),
        _check(
            len(findings) >= min_findings,
            "finding-count",
            f"finding count {len(findings)} below required {min_findings}",
        ),
        _check(
            not missing_evidence,
            "finding-evidence",
            "one or more findings are missing evidence items",
            details={"finding_keys": missing_evidence},
        ),
        _check(
            not unresolved_findings,
            "finding-review-status-resolved",
            "one or more findings still have unresolved review_status",
            details={"finding_keys": unresolved_findings},
        ),
        _check(
            not unlinked_findings,
            "finding-review-task-linked",
            "one or more findings are not linked to review tasks",
            details={"finding_keys": unlinked_findings},
        ),
        _check(
            not missing_review_tasks,
            "linked-review-task-exists",
            "one or more linked review tasks do not exist",
            details={"finding_keys": missing_review_tasks},
        ),
        _check(
            not unresolved_review_tasks,
            "review-task-status-resolved",
            "one or more review tasks are not resolved",
            details={"review_task_ids": unresolved_review_tasks},
        ),
        _check(
            not status_mismatches,
            "review-status-alignment",
            "finding review_status does not match linked review task status",
            details={"finding_keys": status_mismatches},
        ),
        _check(
            not incomplete_review_notes,
            "review-task-conclusion",
            "one or more review tasks are missing reviewer_note or conclusion",
            details={"review_task_ids": incomplete_review_notes},
        ),
    ]
    if require_workpaper:
        checks.append(
            _check(
                not missing_workpapers,
                "confirmed-violation-workpaper",
                "confirmed violation findings are missing ready workpapers",
                details={"finding_keys": missing_workpapers},
            )
        )
    if require_owner_signoff:
        checks.append(_owner_signoff_check(audit_task))
    return tuple(checks)


def _owner_signoff_check(audit_task: AuditTask | None) -> CaseReviewReportGateCheck:
    signoff = _owner_signoff(audit_task)
    condition = (
        signoff.get("status") in APPROVED_OWNER_SIGNOFF_STATUSES
        and bool(str(signoff.get("confirmed_by", "")).strip())
        and bool(str(signoff.get("confirmed_at", "")).strip())
    )
    return _check(
        condition,
        "owner-signoff",
        "department owner signoff is missing or not approved",
        details={"owner_signoff": signoff},
    )


def _finding_has_ready_workpaper(
    finding: AuditFinding,
    review_tasks_by_id: dict[UUID, ReviewTask],
) -> bool:
    finding_workpaper = _dict_value(finding.extra_metadata.get("workpaper"))
    if finding_workpaper.get("status") == "ready":
        return True
    if finding.review_task_id is None:
        return False
    review_task = review_tasks_by_id.get(finding.review_task_id)
    if review_task is None:
        return False
    task_workpaper = _dict_value(review_task.dossier.get("workpaper"))
    return task_workpaper.get("status") == "ready"


def _owner_signoff_summary(audit_task: AuditTask | None) -> dict[str, Any]:
    signoff = _owner_signoff(audit_task)
    return {
        "status": signoff.get("status"),
        "confirmed_by": signoff.get("confirmed_by"),
        "confirmed_at": signoff.get("confirmed_at"),
    }


def _owner_signoff(audit_task: AuditTask | None) -> dict[str, Any]:
    if audit_task is None:
        return {}
    return _dict_value(audit_task.extra_metadata.get("owner_signoff"))


def _dict_value(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _check(
    condition: bool,
    name: str,
    failure_message: str,
    *,
    details: dict[str, Any] | None = None,
) -> CaseReviewReportGateCheck:
    return CaseReviewReportGateCheck(
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
