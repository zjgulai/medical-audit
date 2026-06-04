import asyncio
from pathlib import Path

from pytest import MonkeyPatch
from sqlalchemy.ext.asyncio import create_async_engine

from medical_audit_kb.audit.case_review_report_gate import (
    audit_case_review_report_gate_to_database,
)
from medical_audit_kb.audit.charge_rule_001 import DEFAULT_RULE_VERSION_KEY, RULE_KEY
from medical_audit_kb.cli import main
from medical_audit_kb.db.engine import create_schema, create_session_factory
from medical_audit_kb.db.repositories import AuditWorkflowRepository, ReviewTaskRepository
from medical_audit_kb.domain.schemas import (
    AuditDataSnapshotCreate,
    AuditFindingCreate,
    AuditProjectCreate,
    AuditRuleCreate,
    AuditRunCreate,
    AuditTaskCreate,
    FindingEvidenceItemCreate,
    ReviewTaskCreate,
    RuleVersionCreate,
)


def test_case_review_report_gate_passes_complete_case_review(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'audit.db'}"
    asyncio.run(_create_case_review_contract(database_url))

    result = asyncio.run(
        audit_case_review_report_gate_to_database(
            database_url=database_url,
            project_key="audit-project-report-gate",
            audit_task_key="audit-task-report-gate",
            audit_run_key="audit-run-report-gate",
            min_findings=2,
        )
    )

    assert result.status == "pass"
    assert result.ready_for_formal_report is True
    assert result.summary["finding_count"] == 2
    assert result.summary["confirmed_violation_count"] == 1
    assert result.summary["workpaper_ready_count"] == 1
    assert result.issues == ()


def test_case_review_report_gate_blocks_unresolved_review_and_missing_workpaper(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'audit.db'}"
    asyncio.run(
        _create_case_review_contract(
            database_url,
            first_review_status="confirmed-violation",
            first_task_status="confirmed-violation",
            first_task_conclusion="",
            first_task_reviewer_note="",
            include_workpaper=False,
            include_owner_signoff=False,
        )
    )

    result = asyncio.run(
        audit_case_review_report_gate_to_database(
            database_url=database_url,
            project_key="audit-project-report-gate",
            audit_task_key="audit-task-report-gate",
            audit_run_key="audit-run-report-gate",
            min_findings=2,
        )
    )

    assert result.status == "fail"
    assert result.ready_for_formal_report is False
    failed_checks = {check.name for check in result.checks if check.status == "fail"}
    assert {
        "review-task-conclusion",
        "confirmed-violation-workpaper",
        "owner-signoff",
    }.issubset(failed_checks)


def test_case_review_report_gate_command_writes_reports(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'audit.db'}"
    asyncio.run(_create_case_review_contract(database_url))
    monkeypatch.setenv("MEDICAL_AUDIT_TEST_DATABASE_URL", database_url)
    report_path = tmp_path / "case-review-report-gate.md"
    json_path = tmp_path / "case-review-report-gate.json"

    exit_code = main(
        [
            "case-review-report-gate",
            "--project-key",
            "audit-project-report-gate",
            "--audit-task-key",
            "audit-task-report-gate",
            "--audit-run-key",
            "audit-run-report-gate",
            "--min-findings",
            "2",
            "--database-url-env",
            "MEDICAL_AUDIT_TEST_DATABASE_URL",
            "--output",
            str(report_path),
            "--json-output",
            str(json_path),
        ]
    )

    assert exit_code == 0
    assert "案件级复核报告门禁" in report_path.read_text(encoding="utf-8")
    json_body = json_path.read_text(encoding="utf-8")
    assert '"ready_for_formal_report": true' in json_body
    assert '"owner-signoff"' in json_body


async def _create_case_review_contract(
    database_url: str,
    *,
    first_review_status: str = "confirmed-violation",
    first_task_status: str = "confirmed-violation",
    first_task_reviewer_note: str = "已复核 HIS 明细、规则依据和重复收费计算过程。",
    first_task_conclusion: str = "确认同就诊同项目重复收费成立，进入正式底稿。",
    include_workpaper: bool = True,
    include_owner_signoff: bool = True,
) -> None:
    engine = create_async_engine(database_url)
    try:
        await create_schema(engine)
        session_factory = create_session_factory(engine)
        async with session_factory() as session, session.begin():
            audit_repository = AuditWorkflowRepository(session)
            review_repository = ReviewTaskRepository(session)
            project = await audit_repository.create_project(
                AuditProjectCreate(
                    project_key="audit-project-report-gate",
                    name="收费合规正式报告门禁",
                    scenario_key="charging-compliance",
                    status="fixture",
                    owner_department="审计科",
                    created_by="unit-test",
                )
            )
            snapshot = await audit_repository.create_data_snapshot(
                AuditDataSnapshotCreate(
                    snapshot_key="snapshot-report-gate",
                    project_id=project.id,
                    source_batch_key="his-batch-report-gate",
                    time_range={"from": "2025-01-01", "to": "2025-01-31"},
                    row_counts={"T_CHARGE_DETAIL": 2},
                    checksum="sha256:snapshot",
                    status="validated",
                )
            )
            task_metadata = {}
            if include_owner_signoff:
                task_metadata["owner_signoff"] = {
                    "status": "approved",
                    "confirmed_by": "审计科负责人A",
                    "confirmed_at": "2026-06-04T12:00:00Z",
                }
            task = await audit_repository.create_task(
                AuditTaskCreate(
                    task_key="audit-task-report-gate",
                    project_id=project.id,
                    snapshot_id=snapshot.id,
                    topic="同就诊同项目重复收费",
                    department_scope={"department_codes": ["D001"]},
                    date_range={"from": "2025-01-01", "to": "2025-01-31"},
                    status="ready",
                    created_by="unit-test",
                    metadata=task_metadata,
                )
            )
            rule = await audit_repository.create_rule(
                AuditRuleCreate(
                    rule_key=RULE_KEY,
                    scenario_key="charging-compliance",
                    name="同就诊同项目重复收费",
                    status="active",
                    owner="audit-rule-team",
                )
            )
            rule_version = await audit_repository.create_rule_version(
                RuleVersionCreate(
                    audit_rule_id=rule.id,
                    version_key=DEFAULT_RULE_VERSION_KEY,
                    rule_key=RULE_KEY,
                    status="active",
                    logic={"gate": "case-review-report-gate"},
                    evidence_links={"knowledge_topics": ["重复收费"]},
                    created_by="unit-test",
                )
            )
            run = await audit_repository.create_run(
                AuditRunCreate(
                    run_key="audit-run-report-gate",
                    audit_task_id=task.id,
                    snapshot_id=snapshot.id,
                    rule_version_key=rule_version.version_key,
                    knowledge_index_version_key="full-rebuild-20260603085815",
                    status="succeeded",
                )
            )
            first_review_task = await review_repository.create_task(
                ReviewTaskCreate(
                    external_task_id="review-task-report-0001",
                    question="复核 finding-report-001",
                    status=first_task_status,
                    status_label="确认违规",
                    citation_count=1,
                    review_gate="人工复核后方可进入正式报告",
                    confidence_label="high",
                    fallback_label="none",
                    reviewer_note=first_task_reviewer_note,
                    conclusion=first_task_conclusion,
                    created_by="unit-test",
                    assigned_to="auditor-a",
                    source="audit-finding",
                    dossier=(
                        {
                            "workpaper": {
                                "status": "ready",
                                "workpaper_id": "workpaper-report-001",
                                "prepared_by": "auditor-a",
                            }
                        }
                        if include_workpaper
                        else {}
                    ),
                )
            )
            second_review_task = await review_repository.create_task(
                ReviewTaskCreate(
                    external_task_id="review-task-report-0002",
                    question="复核 finding-report-002",
                    status="not-violation",
                    status_label="非违规",
                    citation_count=1,
                    review_gate="人工复核后方可进入正式报告",
                    confidence_label="medium",
                    fallback_label="none",
                    reviewer_note="已复核医嘱解释，重复计费不成立。",
                    conclusion="不构成违规，不进入正式底稿。",
                    created_by="unit-test",
                    assigned_to="auditor-a",
                    source="audit-finding",
                    dossier={},
                )
            )
            first_finding = await audit_repository.create_finding(
                AuditFindingCreate(
                    finding_key="finding-report-001",
                    audit_run_id=run.id,
                    audit_task_id=task.id,
                    rule_version_id=rule_version.id,
                    snapshot_id=snapshot.id,
                    status="open",
                    finding_type="duplicate-charge",
                    severity="medium",
                    source_record_locator={"source_batch_key": "his-batch-report-gate"},
                    calculation_trace={"duplicate_count": 2},
                    review_status=first_review_status,
                    review_task_id=first_review_task.id,
                )
            )
            second_finding = await audit_repository.create_finding(
                AuditFindingCreate(
                    finding_key="finding-report-002",
                    audit_run_id=run.id,
                    audit_task_id=task.id,
                    rule_version_id=rule_version.id,
                    snapshot_id=snapshot.id,
                    status="closed",
                    finding_type="duplicate-charge",
                    severity="low",
                    source_record_locator={"source_batch_key": "his-batch-report-gate"},
                    calculation_trace={"duplicate_count": 1},
                    review_status="not-violation",
                    review_task_id=second_review_task.id,
                )
            )
            for finding in (first_finding, second_finding):
                await audit_repository.add_finding_evidence_item(
                    FindingEvidenceItemCreate(
                        audit_finding_id=finding.id,
                        evidence_type="rule-rationale",
                        citation_id=f"{finding.finding_key}-evidence",
                        locator={"rule_key": RULE_KEY},
                        snippet="同一就诊同一收费项目重复收费进入人工复核。",
                        metadata={"source": "unit-test"},
                    )
                )
    finally:
        await engine.dispose()
