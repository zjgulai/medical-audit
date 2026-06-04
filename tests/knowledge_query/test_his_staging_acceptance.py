import asyncio
from pathlib import Path

from pytest import MonkeyPatch
from sqlalchemy.ext.asyncio import create_async_engine

from medical_audit_kb.audit.charge_rule_001 import DEFAULT_RULE_VERSION_KEY, RULE_KEY
from medical_audit_kb.cli import main
from medical_audit_kb.db.engine import create_schema, create_session_factory
from medical_audit_kb.db.repositories import AuditWorkflowRepository, HisIngestionRepository
from medical_audit_kb.domain.schemas import (
    AuditDataSnapshotCreate,
    AuditFindingCreate,
    AuditProjectCreate,
    AuditRuleCreate,
    AuditRunCreate,
    AuditTaskCreate,
    FindingEvidenceItemCreate,
    HisFieldMappingCreate,
    HisSourceBatchCreate,
    HisStagingRowCreate,
    HisTableSchemaCreate,
    RuleVersionCreate,
)
from medical_audit_kb.his.mapping_validation import CHARGING_COMPLIANCE_REQUIRED_FIELDS
from medical_audit_kb.his.staging_acceptance import audit_his_staging_acceptance_to_database


def test_his_staging_acceptance_passes_complete_production_contract(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'audit.db'}"
    asyncio.run(_create_staging_acceptance_contract(database_url))

    result = asyncio.run(
        audit_his_staging_acceptance_to_database(
            database_url=database_url,
            project_key="audit-project-acceptance",
            source_batch_key="his-batch-acceptance",
            snapshot_key="snapshot-current",
            audit_task_key="audit-task-acceptance",
            audit_run_key="audit-run-acceptance",
            expected_tables=("T_CHARGE_DETAIL",),
            min_staged_rows=2,
            min_findings=1,
            rollback_target_snapshot_key="snapshot-previous",
        )
    )

    assert result.status == "pass"
    assert result.ready_for_production_staging is True
    assert result.summary["staged_row_count"] == 2
    assert result.summary["active_mapping_count"] == len(CHARGING_COMPLIANCE_REQUIRED_FIELDS)
    assert result.summary["finding_count"] == 1
    assert result.summary["evidence_item_count"] == 1
    assert result.issues == ()


def test_his_staging_acceptance_blocks_incomplete_mapping(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'audit.db'}"
    asyncio.run(_create_staging_acceptance_contract(database_url, omit_last_mapping=True))

    result = asyncio.run(
        audit_his_staging_acceptance_to_database(
            database_url=database_url,
            project_key="audit-project-acceptance",
            source_batch_key="his-batch-acceptance",
            snapshot_key="snapshot-current",
            audit_task_key="audit-task-acceptance",
            audit_run_key="audit-run-acceptance",
            expected_tables=("T_CHARGE_DETAIL",),
            min_staged_rows=2,
            min_findings=1,
        )
    )

    assert result.status == "fail"
    assert result.ready_for_production_staging is False
    assert "charging compliance field mapping gate failed" in result.issues
    failed_checks = {check.name for check in result.checks if check.status == "fail"}
    assert failed_checks == {"field-mapping-gate"}


def test_his_staging_acceptance_command_writes_reports(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'audit.db'}"
    asyncio.run(_create_staging_acceptance_contract(database_url))
    monkeypatch.setenv("MEDICAL_AUDIT_TEST_DATABASE_URL", database_url)
    report_path = tmp_path / "his-staging-acceptance.md"
    json_path = tmp_path / "his-staging-acceptance.json"

    exit_code = main(
        [
            "his-staging-acceptance",
            "--project-key",
            "audit-project-acceptance",
            "--source-batch-key",
            "his-batch-acceptance",
            "--snapshot-key",
            "snapshot-current",
            "--audit-task-key",
            "audit-task-acceptance",
            "--audit-run-key",
            "audit-run-acceptance",
            "--expected-table",
            "T_CHARGE_DETAIL",
            "--min-staged-rows",
            "2",
            "--min-findings",
            "1",
            "--rollback-target-snapshot-key",
            "snapshot-previous",
            "--database-url-env",
            "MEDICAL_AUDIT_TEST_DATABASE_URL",
            "--output",
            str(report_path),
            "--json-output",
            str(json_path),
        ]
    )

    assert exit_code == 0
    assert "HIS 生产 staging 执行验收报告" in report_path.read_text(encoding="utf-8")
    json_body = json_path.read_text(encoding="utf-8")
    assert '"ready_for_production_staging": true' in json_body
    assert '"field-mapping-gate"' in json_body


async def _create_staging_acceptance_contract(
    database_url: str,
    *,
    omit_last_mapping: bool = False,
) -> None:
    engine = create_async_engine(database_url)
    try:
        await create_schema(engine)
        session_factory = create_session_factory(engine)
        async with session_factory() as session, session.begin():
            audit_repository = AuditWorkflowRepository(session)
            his_repository = HisIngestionRepository(session)
            project = await audit_repository.create_project(
                AuditProjectCreate(
                    project_key="audit-project-acceptance",
                    name="收费合规生产 staging 验收",
                    scenario_key="charging-compliance",
                    status="fixture",
                    owner_department="审计科",
                    created_by="unit-test",
                )
            )
            source_batch = await his_repository.create_source_batch(
                HisSourceBatchCreate(
                    batch_key="his-batch-acceptance",
                    project_id=project.id,
                    hospital_code="hospital-a",
                    scenario_key="charging-compliance",
                    source_type="offline-export",
                    file_manifest={"files": ["T_CHARGE_DETAIL.csv"]},
                    row_counts={"T_CHARGE_DETAIL": 2},
                    checksum="sha256:batch",
                    status="received",
                )
            )
            table_schema = await his_repository.create_table_schema(
                HisTableSchemaCreate(
                    schema_key="his-schema-acceptance-charge-detail",
                    source_batch_id=source_batch.id,
                    table_name="T_CHARGE_DETAIL",
                    business_domain="charge_detail",
                    ddl_text="CREATE TABLE T_CHARGE_DETAIL (CHARGE_ID TEXT NOT NULL);",
                    ddl_hash="sha256:ddl",
                    field_dictionary={"CHARGE_ID": {"description": "charge row id"}},
                    primary_key_fields=["CHARGE_ID"],
                    time_fields=["CHARGED_AT"],
                    row_count=2,
                    status="mapped",
                )
            )
            requirements = CHARGING_COMPLIANCE_REQUIRED_FIELDS
            if omit_last_mapping:
                requirements = requirements[:-1]
            for requirement in requirements:
                source_field = f"{requirement.target_domain}_{requirement.target_field}".upper()
                await his_repository.add_field_mapping(
                    HisFieldMappingCreate(
                        mapping_key=f"map-acceptance-{requirement.target_domain}-{requirement.target_field}",
                        table_schema_id=table_schema.id,
                        source_field=source_field,
                        target_domain=requirement.target_domain,
                        target_field=requirement.target_field,
                        deidentification_rule=(
                            "sha256-with-salt"
                            if requirement.requires_deidentification_rule
                            else None
                        ),
                        status="active",
                    )
                )
            await his_repository.add_staging_rows(
                [
                    HisStagingRowCreate(
                        source_batch_id=source_batch.id,
                        table_schema_id=table_schema.id,
                        table_name="T_CHARGE_DETAIL",
                        row_number=1,
                        row_data={"CHARGE_ID": "C001"},
                        row_hash="sha256:row-1",
                        status="staged",
                    ),
                    HisStagingRowCreate(
                        source_batch_id=source_batch.id,
                        table_schema_id=table_schema.id,
                        table_name="T_CHARGE_DETAIL",
                        row_number=2,
                        row_data={"CHARGE_ID": "C002"},
                        row_hash="sha256:row-2",
                        status="staged",
                    ),
                ]
            )
            await audit_repository.create_data_snapshot(
                AuditDataSnapshotCreate(
                    snapshot_key="snapshot-previous",
                    project_id=project.id,
                    source_batch_key="his-batch-previous",
                    time_range={"from": "2025-01-01", "to": "2025-01-31"},
                    row_counts={"T_CHARGE_DETAIL": 2},
                    checksum="sha256:previous",
                    status="validated",
                )
            )
            snapshot = await audit_repository.create_data_snapshot(
                AuditDataSnapshotCreate(
                    snapshot_key="snapshot-current",
                    project_id=project.id,
                    source_batch_key=source_batch.batch_key,
                    time_range={"from": "2025-01-01", "to": "2025-01-31"},
                    row_counts={"T_CHARGE_DETAIL": 2},
                    checksum="sha256:current",
                    status="validated",
                )
            )
            task = await audit_repository.create_task(
                AuditTaskCreate(
                    task_key="audit-task-acceptance",
                    project_id=project.id,
                    snapshot_id=snapshot.id,
                    topic="同就诊同项目重复收费",
                    department_scope={"department_codes": ["D001"]},
                    date_range={"from": "2025-01-01", "to": "2025-01-31"},
                    status="ready",
                    created_by="unit-test",
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
                    logic={"acceptance": "charge-rule-001-v1"},
                    evidence_links={"knowledge_topics": ["重复收费"]},
                    created_by="unit-test",
                )
            )
            run = await audit_repository.create_run(
                AuditRunCreate(
                    run_key="audit-run-acceptance",
                    audit_task_id=task.id,
                    snapshot_id=snapshot.id,
                    rule_version_key=rule_version.version_key,
                    knowledge_index_version_key="full-rebuild-20260603085815",
                    status="succeeded",
                )
            )
            finding = await audit_repository.create_finding(
                AuditFindingCreate(
                    finding_key="finding-acceptance-001",
                    audit_run_id=run.id,
                    audit_task_id=task.id,
                    rule_version_id=rule_version.id,
                    snapshot_id=snapshot.id,
                    status="open",
                    finding_type="duplicate-charge",
                    severity="medium",
                    source_record_locator={"source_batch_key": source_batch.batch_key},
                    calculation_trace={"duplicate_count": 2},
                    review_status="pending-review",
                )
            )
            await audit_repository.add_finding_evidence_item(
                FindingEvidenceItemCreate(
                    audit_finding_id=finding.id,
                    evidence_type="rule-rationale",
                    citation_id="CHARGE-RULE-001-acceptance",
                    locator={"rule_key": RULE_KEY},
                    snippet="同一就诊同一收费项目重复收费进入人工复核。",
                    metadata={"source": "unit-test"},
                )
            )
    finally:
        await engine.dispose()
