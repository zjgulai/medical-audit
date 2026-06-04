import asyncio
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from medical_audit_kb.audit.charge_rule_001 import (
    DEFAULT_RULE_VERSION_KEY,
    RULE_KEY,
    build_audit_finding_payloads,
    build_charge_rule_001_fixture,
    evaluate_charge_rule_001,
)
from medical_audit_kb.db.models import AuditFinding, Base, FindingEvidenceItem
from medical_audit_kb.db.repositories import AuditWorkflowRepository
from medical_audit_kb.domain.schemas import (
    AuditDataSnapshotCreate,
    AuditProjectCreate,
    AuditRuleCreate,
    AuditRunCreate,
    AuditTaskCreate,
    FindingEvidenceItemCreate,
    RuleVersionCreate,
)


def test_charge_rule_001_fixture_covers_positive_negative_and_needs_evidence_cases() -> None:
    records = build_charge_rule_001_fixture()
    result = evaluate_charge_rule_001(
        records,
        audit_task_key="audit-task-charge-fixture",
        audit_run_key="audit-run-charge-fixture",
        snapshot_key="snapshot-charge-fixture",
        knowledge_index_version_key="full-rebuild-20260603085815",
    )
    repeated = evaluate_charge_rule_001(
        records,
        audit_task_key="audit-task-charge-fixture",
        audit_run_key="audit-run-charge-fixture",
        snapshot_key="snapshot-charge-fixture",
        knowledge_index_version_key="full-rebuild-20260603085815",
    )

    assert result.rule_key == RULE_KEY
    assert result.rule_version_key == DEFAULT_RULE_VERSION_KEY
    assert result.summary["finding_count"] == 3
    assert result.summary["explained_group_count"] == 3
    assert result.summary["needs_evidence_count"] == 2
    assert [finding.finding_key for finding in result.findings] == [
        finding.finding_key for finding in repeated.findings
    ]

    matched_record_ids = {
        record_id
        for finding in result.findings
        for record_id in finding.calculation_trace["matched_charge_detail_ids"]
    }
    assert {"CD0001", "CD0002", "CD0003", "CD0004", "CD0005", "CD0006", "CD0007"} <= (
        matched_record_ids
    )
    assert {"CD0101", "CD0102", "CD0111", "CD0112", "CD0113", "CD0121", "CD0122"}.isdisjoint(
        matched_record_ids
    )
    assert [item.charge_detail_id for item in result.needs_evidence] == ["CD0201", "CD0202"]
    assert result.needs_evidence[0].missing_fields == ("visit_id",)
    assert result.needs_evidence[1].missing_fields == ("service_date",)


def test_charge_rule_001_treats_distinct_execution_records_as_explained() -> None:
    records = build_charge_rule_001_fixture()
    explained_result = evaluate_charge_rule_001(
        [
            record
            for record in records
            if record.visit_id in {"V010", "V011", "V012"}
            and record.service_date == date(2025, 1, 5)
        ],
        audit_task_key="audit-task-negative-fixture",
        audit_run_key="audit-run-negative-fixture",
        snapshot_key="snapshot-charge-fixture",
    )

    assert explained_result.summary["finding_count"] == 0
    assert explained_result.summary["explained_group_count"] == 3
    assert explained_result.findings == ()
    assert explained_result.needs_evidence == ()


def test_charge_rule_001_outputs_repository_compatible_finding_payloads() -> None:
    asyncio.run(_assert_charge_rule_001_repository_flow())


async def _assert_charge_rule_001_repository_flow() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        await _create_schema(engine)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session, session.begin():
            await _assert_charge_rule_001_repository_write(session)
    finally:
        await engine.dispose()


async def _create_schema(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def _assert_charge_rule_001_repository_write(session: AsyncSession) -> None:
    repository = AuditWorkflowRepository(session)
    project = await repository.create_project(
        AuditProjectCreate(
            project_key="audit-project-charge-fixture",
            name="收费合规 fixture 专项",
            scenario_key="charging-compliance",
            status="fixture",
            owner_department="审计科",
            created_by="unit-test",
        )
    )
    snapshot = await repository.create_data_snapshot(
        AuditDataSnapshotCreate(
            snapshot_key="snapshot-charge-fixture",
            project_id=project.id,
            source_batch_key="his-fixture-20260604",
            time_range={"from": "2025-01-01", "to": "2025-01-31"},
            row_counts={"charge_detail": len(build_charge_rule_001_fixture())},
            checksum="sha256:charge-fixture",
            status="validated",
        )
    )
    task = await repository.create_task(
        AuditTaskCreate(
            task_key="audit-task-charge-fixture",
            project_id=project.id,
            snapshot_id=snapshot.id,
            topic="同就诊同项目重复收费",
            department_scope={"department_codes": ["D001"]},
            date_range={"from": "2025-01-01", "to": "2025-01-31"},
            status="ready",
            created_by="unit-test",
        )
    )
    rule = await repository.create_rule(
        AuditRuleCreate(
            rule_key=RULE_KEY,
            scenario_key="charging-compliance",
            name="同就诊同项目重复收费",
            status="active",
            owner="audit-rule-team",
        )
    )
    rule_version = await repository.create_rule_version(
        RuleVersionCreate(
            audit_rule_id=rule.id,
            version_key=DEFAULT_RULE_VERSION_KEY,
            rule_key=RULE_KEY,
            status="active",
            logic={"fixture": "charge-rule-001-v1"},
            evidence_links={"knowledge_topics": ["重复收费", "收费项目内涵"]},
            created_by="unit-test",
        )
    )
    run = await repository.create_run(
        AuditRunCreate(
            run_key="audit-run-charge-fixture",
            audit_task_id=task.id,
            snapshot_id=snapshot.id,
            rule_version_key=rule_version.version_key,
            knowledge_index_version_key="full-rebuild-20260603085815",
            status="succeeded",
        )
    )

    result = evaluate_charge_rule_001(
        build_charge_rule_001_fixture(),
        audit_task_key=task.task_key,
        audit_run_key=run.run_key,
        snapshot_key=snapshot.snapshot_key,
        knowledge_index_version_key=run.knowledge_index_version_key,
    )
    payloads = build_audit_finding_payloads(
        result,
        audit_run_id=run.id,
        audit_task_id=task.id,
        rule_version_id=rule_version.id,
        snapshot_id=snapshot.id,
    )

    findings = [await repository.create_finding(payload) for payload in payloads]
    for finding, rule_finding in zip(findings, result.findings, strict=True):
        await repository.add_finding_evidence_item(
            FindingEvidenceItemCreate(
                audit_finding_id=finding.id,
                evidence_type="rule-rationale",
                source_package_version_key=rule_finding.source_package_version_key,
                index_version_key=rule_finding.knowledge_index_version_key,
                citation_id=f"{RULE_KEY}-fixture-rationale",
                locator={"rule_key": RULE_KEY},
                snippet=rule_finding.knowledge_evidence_snippet,
                metadata={"source": "fixture"},
            )
        )

    stored_findings = (
        (
            await session.execute(
                select(AuditFinding)
                .where(AuditFinding.audit_run_id == run.id)
                .order_by(AuditFinding.finding_key.asc())
            )
        )
        .scalars()
        .all()
    )
    stored_evidence = (
        (
            await session.execute(
                select(FindingEvidenceItem).order_by(FindingEvidenceItem.created_at.asc())
            )
        )
        .scalars()
        .all()
    )

    assert len(payloads) == 3
    assert len(stored_findings) == 3
    assert len(stored_evidence) == 3
    assert {finding.review_status for finding in stored_findings} == {"pending-review"}
    assert {finding.finding_type for finding in stored_findings} == {"duplicate-charge"}
    assert all(item.snippet is not None and "同一就诊" in item.snippet for item in stored_evidence)
