import asyncio

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from medical_audit_kb.audit.charge_rule_001 import evaluate_charge_rule_001
from medical_audit_kb.audit.charge_rule_001_staging import (
    build_charge_rule_001_records_from_staging,
)
from medical_audit_kb.db.models import Base
from medical_audit_kb.db.repositories import AuditWorkflowRepository, HisIngestionRepository
from medical_audit_kb.domain.schemas import (
    AuditProjectCreate,
    HisFieldMappingCreate,
    HisSourceBatchCreate,
    HisStagingRowCreate,
    HisTableSchemaCreate,
)


def test_charge_rule_001_staging_records_drive_existing_rule() -> None:
    asyncio.run(_assert_charge_rule_001_staging_records_drive_existing_rule())


def test_charge_rule_001_staging_blocks_invalid_decimal() -> None:
    asyncio.run(_assert_charge_rule_001_staging_blocks_invalid_decimal())


async def _assert_charge_rule_001_staging_records_drive_existing_rule() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        await _create_schema(engine)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session, session.begin():
            his_repository = await _create_charge_detail_staging_contract(session)
            staging_rows = await his_repository.list_staging_rows_for_batch("his-batch-0001")
            field_mappings = await his_repository.list_field_mappings_for_batch("his-batch-0001")

        input_result = build_charge_rule_001_records_from_staging(
            staging_rows,
            field_mappings,
            source_batch_key="his-batch-0001",
        )
        rule_result = evaluate_charge_rule_001(
            input_result.records,
            audit_task_key="audit-task-staging",
            audit_run_key="audit-run-staging",
            snapshot_key="snapshot-staging",
        )

        assert input_result.status == "pass"
        assert input_result.summary["converted_record_count"] == 3
        assert input_result.summary["error_count"] == 0
        assert rule_result.summary["finding_count"] == 1
        assert rule_result.summary["needs_evidence_count"] == 1
        assert rule_result.findings[0].calculation_trace["matched_charge_detail_ids"] == [
            "C001",
            "C002",
        ]
        assert rule_result.needs_evidence[0].charge_detail_id == "C003"
        assert rule_result.needs_evidence[0].missing_fields == ("visit_id",)
    finally:
        await engine.dispose()


async def _assert_charge_rule_001_staging_blocks_invalid_decimal() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        await _create_schema(engine)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session, session.begin():
            his_repository = await _create_charge_detail_staging_contract(
                session,
                unit_price_for_second_row="not-a-decimal",
            )
            staging_rows = await his_repository.list_staging_rows_for_batch("his-batch-0001")
            field_mappings = await his_repository.list_field_mappings_for_batch("his-batch-0001")

        input_result = build_charge_rule_001_records_from_staging(
            staging_rows,
            field_mappings,
            source_batch_key="his-batch-0001",
        )

        assert input_result.status == "fail"
        assert input_result.summary["converted_record_count"] == 2
        assert input_result.summary["error_count"] == 1
        assert input_result.issues[0].issue_type == "invalid-decimal"
        assert input_result.issues[0].row_number == 2
    finally:
        await engine.dispose()


async def _create_schema(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def _create_charge_detail_staging_contract(
    session: AsyncSession,
    *,
    unit_price_for_second_row: str = "40.00",
) -> HisIngestionRepository:
    audit_repository = AuditWorkflowRepository(session)
    his_repository = HisIngestionRepository(session)
    project = await audit_repository.create_project(
        AuditProjectCreate(
            project_key="audit-project-charge-staging",
            name="收费合规 staging 专项",
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
            schema_key="his-schema-charge-detail-staging",
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
                mapping_key=f"map-{source_field.lower()}",
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
                row_data=_row("C001", "V001", "P001", "静脉输液", "40.00"),
                row_hash="sha256:row-1",
                status="staged",
            ),
            HisStagingRowCreate(
                source_batch_id=source_batch.id,
                table_schema_id=table_schema.id,
                table_name="T_CHARGE_DETAIL",
                row_number=2,
                row_data=_row("C002", "V001", "P001", "静脉输液", unit_price_for_second_row),
                row_hash="sha256:row-2",
                status="staged",
            ),
            HisStagingRowCreate(
                source_batch_id=source_batch.id,
                table_schema_id=table_schema.id,
                table_name="T_CHARGE_DETAIL",
                row_number=3,
                row_data=_row("C003", "", "P002", "床位费", "60.00"),
                row_hash="sha256:row-3",
                status="staged",
            ),
        ]
    )
    return his_repository


def _row(
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
