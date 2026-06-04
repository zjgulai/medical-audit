import asyncio
from pathlib import Path

from pytest import MonkeyPatch
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from medical_audit_kb.audit.charge_rule_001 import DEFAULT_RULE_VERSION_KEY, RULE_KEY
from medical_audit_kb.audit.charge_rule_001_staging_runner import (
    run_charge_rule_001_from_staging_database,
)
from medical_audit_kb.cli import main
from medical_audit_kb.db.engine import create_schema, create_session_factory
from medical_audit_kb.db.models import AuditFinding, FindingEvidenceItem
from medical_audit_kb.db.repositories import AuditWorkflowRepository, HisIngestionRepository
from medical_audit_kb.domain.schemas import (
    AuditDataSnapshotCreate,
    AuditProjectCreate,
    AuditRuleCreate,
    AuditRunCreate,
    AuditTaskCreate,
    HisFieldMappingCreate,
    HisSourceBatchCreate,
    HisStagingRowCreate,
    HisTableSchemaCreate,
    RuleVersionCreate,
)


def test_charge_rule_001_staging_runner_dry_runs_then_executes(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'audit.db'}"
    asyncio.run(_create_charge_rule_001_staging_run_contract(database_url))

    dry_run_result = asyncio.run(
        run_charge_rule_001_from_staging_database(
            database_url=database_url,
            source_batch_key="his-batch-0001",
            audit_task_key="audit-task-staging-run",
            audit_run_key="audit-run-staging-run",
        )
    )
    execute_result = asyncio.run(
        run_charge_rule_001_from_staging_database(
            database_url=database_url,
            source_batch_key="his-batch-0001",
            audit_task_key="audit-task-staging-run",
            audit_run_key="audit-run-staging-run",
            execute=True,
        )
    )

    assert dry_run_result.status == "pass"
    assert dry_run_result.executed is False
    assert dry_run_result.rule_summary["finding_count"] == 1
    assert dry_run_result.rule_summary["needs_evidence_count"] == 1
    assert dry_run_result.created_finding_count == 0
    assert execute_result.status == "pass"
    assert execute_result.executed is True
    assert execute_result.created_finding_count == 1
    assert execute_result.created_evidence_item_count == 1
    assert asyncio.run(_finding_counts(database_url)) == (1, 1)


def test_charge_rule_001_staging_runner_blocks_duplicate_execution(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'audit.db'}"
    asyncio.run(_create_charge_rule_001_staging_run_contract(database_url))

    first_result = asyncio.run(
        run_charge_rule_001_from_staging_database(
            database_url=database_url,
            source_batch_key="his-batch-0001",
            audit_task_key="audit-task-staging-run",
            audit_run_key="audit-run-staging-run",
            execute=True,
        )
    )
    second_result = asyncio.run(
        run_charge_rule_001_from_staging_database(
            database_url=database_url,
            source_batch_key="his-batch-0001",
            audit_task_key="audit-task-staging-run",
            audit_run_key="audit-run-staging-run",
            execute=True,
        )
    )

    assert first_result.status == "pass"
    assert second_result.status == "fail"
    assert second_result.executed is False
    assert second_result.existing_finding_keys == first_result.finding_keys
    assert "audit finding already exists" in second_result.issues[0]
    assert asyncio.run(_finding_counts(database_url)) == (1, 1)


def test_charge_rule_001_staging_runner_blocks_conversion_errors(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'audit.db'}"
    asyncio.run(
        _create_charge_rule_001_staging_run_contract(
            database_url,
            unit_price_for_second_row="not-a-decimal",
        )
    )

    result = asyncio.run(
        run_charge_rule_001_from_staging_database(
            database_url=database_url,
            source_batch_key="his-batch-0001",
            audit_task_key="audit-task-staging-run",
            audit_run_key="audit-run-staging-run",
            execute=True,
        )
    )

    assert result.status == "fail"
    assert result.executed is False
    assert result.input_summary["error_count"] == 1
    assert result.staging_issues[0].issue_type == "invalid-decimal"
    assert result.staging_issues[0].row_number == 2
    assert asyncio.run(_finding_counts(database_url)) == (0, 0)


def test_charge_rule_001_staging_run_command_writes_reports(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'audit.db'}"
    asyncio.run(_create_charge_rule_001_staging_run_contract(database_url))
    monkeypatch.setenv("MEDICAL_AUDIT_TEST_DATABASE_URL", database_url)
    dry_run_report_path = tmp_path / "charge-rule-001-staging-run-dry-run.md"
    dry_run_json_path = tmp_path / "charge-rule-001-staging-run-dry-run.json"
    execute_report_path = tmp_path / "charge-rule-001-staging-run-execute.md"
    execute_json_path = tmp_path / "charge-rule-001-staging-run-execute.json"

    dry_run_exit_code = main(
        [
            "charge-rule-001-staging-run",
            "--source-batch-key",
            "his-batch-0001",
            "--audit-task-key",
            "audit-task-staging-run",
            "--audit-run-key",
            "audit-run-staging-run",
            "--database-url-env",
            "MEDICAL_AUDIT_TEST_DATABASE_URL",
            "--output",
            str(dry_run_report_path),
            "--json-output",
            str(dry_run_json_path),
        ]
    )
    execute_exit_code = main(
        [
            "charge-rule-001-staging-run",
            "--source-batch-key",
            "his-batch-0001",
            "--audit-task-key",
            "audit-task-staging-run",
            "--audit-run-key",
            "audit-run-staging-run",
            "--database-url-env",
            "MEDICAL_AUDIT_TEST_DATABASE_URL",
            "--output",
            str(execute_report_path),
            "--json-output",
            str(execute_json_path),
            "--execute",
        ]
    )

    assert dry_run_exit_code == 0
    assert execute_exit_code == 0
    assert "CHARGE-RULE-001 staging 规则运行报告" in dry_run_report_path.read_text(encoding="utf-8")
    assert '"execute_requested": false' in dry_run_json_path.read_text(encoding="utf-8")
    execute_json_body = execute_json_path.read_text(encoding="utf-8")
    assert '"execute_requested": true' in execute_json_body
    assert '"created_finding_count": 1' in execute_json_body
    assert asyncio.run(_finding_counts(database_url)) == (1, 1)


async def _create_charge_rule_001_staging_run_contract(
    database_url: str,
    *,
    unit_price_for_second_row: str = "40.00",
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
                    project_key="audit-project-charge-staging-run",
                    name="收费合规 staging 运行专项",
                    scenario_key="charging-compliance",
                    status="fixture",
                    owner_department="审计科",
                    created_by="unit-test",
                )
            )
            source_batch = await his_repository.create_source_batch(
                HisSourceBatchCreate(
                    batch_key="his-batch-0001",
                    project_id=project.id,
                    hospital_code="hospital-a",
                    scenario_key="charging-compliance",
                    source_type="offline-export",
                    file_manifest={"files": ["T_CHARGE_DETAIL.csv"]},
                    row_counts={"T_CHARGE_DETAIL": 3},
                    checksum="sha256:batch",
                    status="received",
                )
            )
            table_schema = await his_repository.create_table_schema(
                HisTableSchemaCreate(
                    schema_key="his-schema-charge-detail-staging-run",
                    source_batch_id=source_batch.id,
                    table_name="T_CHARGE_DETAIL",
                    business_domain="charge_detail",
                    ddl_text="CREATE TABLE T_CHARGE_DETAIL (CHARGE_ID TEXT NOT NULL);",
                    ddl_hash="sha256:ddl",
                    field_dictionary={"CHARGE_ID": {"description": "charge row id"}},
                    primary_key_fields=["CHARGE_ID"],
                    time_fields=["CHARGED_AT"],
                    row_count=3,
                    status="mapped",
                )
            )
            for source_field, target_domain, target_field in (
                ("CHARGE_ID", "charge_detail", "charge_id"),
                ("VISIT_ID", "charge_detail", "visit_id"),
                ("ITEM_CODE", "charge_detail", "hospital_item_code"),
                ("ITEM_NAME", "charge_detail", "item_name"),
                ("CHARGED_AT", "charge_detail", "charged_at"),
                ("QUANTITY", "charge_detail", "quantity"),
                ("UNIT_PRICE", "charge_detail", "unit_price"),
                ("PATIENT_ID", "visit", "patient_anonymous_id"),
                ("DEPARTMENT_CODE", "visit", "department_code"),
            ):
                await his_repository.add_field_mapping(
                    HisFieldMappingCreate(
                        mapping_key=f"map-run-{source_field.lower()}",
                        table_schema_id=table_schema.id,
                        source_field=source_field,
                        target_domain=target_domain,
                        target_field=target_field,
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
                        row_data=_charge_row("C001", "V001", "ITEM-A", "静脉输液", "40.00"),
                        row_hash="sha256:row-1",
                        status="staged",
                    ),
                    HisStagingRowCreate(
                        source_batch_id=source_batch.id,
                        table_schema_id=table_schema.id,
                        table_name="T_CHARGE_DETAIL",
                        row_number=2,
                        row_data=_charge_row(
                            "C002",
                            "V001",
                            "ITEM-A",
                            "静脉输液",
                            unit_price_for_second_row,
                        ),
                        row_hash="sha256:row-2",
                        status="staged",
                    ),
                    HisStagingRowCreate(
                        source_batch_id=source_batch.id,
                        table_schema_id=table_schema.id,
                        table_name="T_CHARGE_DETAIL",
                        row_number=3,
                        row_data=_charge_row("C003", "", "ITEM-B", "床位费", "60.00"),
                        row_hash="sha256:row-3",
                        status="staged",
                    ),
                ]
            )
            snapshot = await audit_repository.create_data_snapshot(
                AuditDataSnapshotCreate(
                    snapshot_key="snapshot-staging-run",
                    project_id=project.id,
                    source_batch_key=source_batch.batch_key,
                    time_range={"from": "2025-01-01", "to": "2025-01-31"},
                    row_counts={"T_CHARGE_DETAIL": 3},
                    checksum="sha256:snapshot",
                    status="validated",
                )
            )
            task = await audit_repository.create_task(
                AuditTaskCreate(
                    task_key="audit-task-staging-run",
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
            await audit_repository.create_rule_version(
                RuleVersionCreate(
                    audit_rule_id=rule.id,
                    version_key=DEFAULT_RULE_VERSION_KEY,
                    rule_key=RULE_KEY,
                    status="active",
                    logic={"staging": "charge-rule-001-v1"},
                    evidence_links={"knowledge_topics": ["重复收费", "收费项目内涵"]},
                    created_by="unit-test",
                )
            )
            await audit_repository.create_run(
                AuditRunCreate(
                    run_key="audit-run-staging-run",
                    audit_task_id=task.id,
                    snapshot_id=snapshot.id,
                    rule_version_key=DEFAULT_RULE_VERSION_KEY,
                    knowledge_index_version_key="full-rebuild-20260603085815",
                    status="ready",
                )
            )
    finally:
        await engine.dispose()


async def _finding_counts(database_url: str) -> tuple[int, int]:
    engine = create_async_engine(database_url)
    try:
        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            finding_result = await session.execute(select(AuditFinding))
            evidence_result = await session.execute(select(FindingEvidenceItem))
            return len(finding_result.scalars().all()), len(evidence_result.scalars().all())
    finally:
        await engine.dispose()


def _charge_row(
    charge_id: str,
    visit_id: str,
    item_code: str,
    item_name: str,
    unit_price: str,
) -> dict[str, str]:
    return {
        "CHARGE_ID": charge_id,
        "VISIT_ID": visit_id,
        "ITEM_CODE": item_code,
        "ITEM_NAME": item_name,
        "CHARGED_AT": "2025-01-03 08:00:00",
        "QUANTITY": "1",
        "UNIT_PRICE": unit_price,
        "PATIENT_ID": f"PAT-{charge_id}",
        "DEPARTMENT_CODE": "D001",
    }
