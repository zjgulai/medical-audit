import asyncio
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from medical_audit_kb.db.engine import create_schema, create_session_factory
from medical_audit_kb.db.models import HisStagingRow
from medical_audit_kb.db.repositories import AuditWorkflowRepository, HisIngestionRepository
from medical_audit_kb.domain.schemas import (
    AuditProjectCreate,
    HisSourceBatchCreate,
    HisTableSchemaCreate,
)
from medical_audit_kb.his.ddl_parser import HisDdlParseReport, parse_his_ddl
from medical_audit_kb.his.sample_quality import (
    HisSampleQualityReport,
    build_his_sample_quality_report,
)
from medical_audit_kb.his.staging_import import (
    his_staging_import_result_json,
    import_his_sample_quality_to_staging_with_engine,
    render_his_staging_import_markdown,
)


def test_his_staging_import_dry_run_validates_without_insert(tmp_path: Path) -> None:
    asyncio.run(_assert_his_staging_import_dry_run(tmp_path))


def test_his_staging_import_execute_inserts_raw_rows(tmp_path: Path) -> None:
    asyncio.run(_assert_his_staging_import_execute(tmp_path))


def test_his_staging_import_blocks_duplicate_rows(tmp_path: Path) -> None:
    asyncio.run(_assert_his_staging_import_duplicate_rows(tmp_path))


def test_his_staging_import_blocks_failed_quality_report(tmp_path: Path) -> None:
    asyncio.run(_assert_his_staging_import_blocks_failed_quality_report(tmp_path))


async def _assert_his_staging_import_dry_run(tmp_path: Path) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        await create_schema(engine)
        await _create_his_contract(engine)
        quality_report = _passing_quality_report(tmp_path)

        result = await import_his_sample_quality_to_staging_with_engine(
            quality_report,
            source_batch_key="his-batch-0001",
            engine=engine,
        )

        assert result.status == "pass"
        assert result.execute_requested is False
        assert result.executed is False
        assert result.dry_run is True
        assert result.planned_row_count == 2
        assert result.inserted_row_count == 0
        assert result.issues == ()
        assert "HIS 脱敏样本 staging 导入报告" in render_his_staging_import_markdown(result)
        assert '"execute_requested": false' in his_staging_import_result_json(result)
        assert await _staging_row_count(engine) == 0
    finally:
        await engine.dispose()


async def _assert_his_staging_import_execute(tmp_path: Path) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        await create_schema(engine)
        await _create_his_contract(engine)
        quality_report = _passing_quality_report(tmp_path)

        result = await import_his_sample_quality_to_staging_with_engine(
            quality_report,
            source_batch_key="his-batch-0001",
            engine=engine,
            execute=True,
        )

        assert result.status == "pass"
        assert result.execute_requested is True
        assert result.executed is True
        assert result.dry_run is False
        assert result.planned_row_count == 2
        assert result.inserted_row_count == 2
        assert await _staging_row_count(engine) == 2
        stored_rows = await _staging_rows(engine)
        assert [row.row_number for row in stored_rows] == [1, 2]
        assert stored_rows[0].table_name == "T_CHARGE_DETAIL"
        assert stored_rows[0].row_data["CHARGE_ID"] == "C001"
        assert stored_rows[0].row_hash.startswith("sha256:")
        assert stored_rows[0].extra_metadata["file_sha256"] == quality_report.tables[0].file_sha256
    finally:
        await engine.dispose()


async def _assert_his_staging_import_duplicate_rows(tmp_path: Path) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        await create_schema(engine)
        await _create_his_contract(engine)
        quality_report = _passing_quality_report(tmp_path)
        first_result = await import_his_sample_quality_to_staging_with_engine(
            quality_report,
            source_batch_key="his-batch-0001",
            engine=engine,
            execute=True,
        )

        second_result = await import_his_sample_quality_to_staging_with_engine(
            quality_report,
            source_batch_key="his-batch-0001",
            engine=engine,
            execute=True,
        )

        assert first_result.status == "pass"
        assert second_result.status == "fail"
        assert second_result.execute_requested is True
        assert second_result.executed is False
        assert "staging rows already exist for his-batch-0001/T_CHARGE_DETAIL: 2" in (
            second_result.issues
        )
        assert await _staging_row_count(engine) == 2
    finally:
        await engine.dispose()


async def _assert_his_staging_import_blocks_failed_quality_report(tmp_path: Path) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        await create_schema(engine)
        await _create_his_contract(engine)
        quality_report = _failed_quality_report(tmp_path)

        result = await import_his_sample_quality_to_staging_with_engine(
            quality_report,
            source_batch_key="his-batch-0001",
            engine=engine,
            execute=True,
        )

        assert result.status == "fail"
        assert result.execute_requested is True
        assert result.executed is False
        assert "sample quality report is not PASS" in result.issues
        assert "table quality is not PASS: T_CHARGE_DETAIL" in result.issues
        assert await _staging_row_count(engine) == 0
    finally:
        await engine.dispose()


async def _create_his_contract(engine: AsyncEngine) -> None:
    session_factory = create_session_factory(engine)
    async with session_factory() as session, session.begin():
        audit_repository = AuditWorkflowRepository(session)
        his_repository = HisIngestionRepository(session)
        project = await audit_repository.create_project(
            AuditProjectCreate(
                project_key="audit-project-his-staging",
                name="HIS staging fixture",
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
                row_counts={"T_CHARGE_DETAIL": 2},
                checksum="sha256:batch",
                status="received",
            )
        )
        await his_repository.create_table_schema(
            HisTableSchemaCreate(
                schema_key="his-schema-charge-detail-0001",
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


async def _staging_row_count(engine: AsyncEngine) -> int:
    rows = await _staging_rows(engine)
    return len(rows)


async def _staging_rows(engine: AsyncEngine) -> list[HisStagingRow]:
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        result = await session.execute(
            select(HisStagingRow).order_by(HisStagingRow.table_name.asc(), HisStagingRow.row_number)
        )
        return list(result.scalars().all())


def _passing_quality_report(tmp_path: Path) -> HisSampleQualityReport:
    sample_root = tmp_path / "samples"
    sample_root.mkdir()
    _write_text(
        sample_root / "T_CHARGE_DETAIL.csv",
        "CHARGE_ID,VISIT_ID,AMOUNT,CHARGED_AT\nC001,V001,1,2025-01-01\nC002,V002,2,2025-01-02\n",
    )
    return build_his_sample_quality_report(sample_root, ddl_report=_ddl_report())


def _failed_quality_report(tmp_path: Path) -> HisSampleQualityReport:
    sample_root = tmp_path / "failed-samples"
    sample_root.mkdir()
    _write_text(sample_root / "T_CHARGE_DETAIL.csv", "CHARGE_ID,VISIT_ID,AMOUNT\nC001,,1\n")
    return build_his_sample_quality_report(sample_root, ddl_report=_ddl_report())


def _ddl_report() -> HisDdlParseReport:
    return parse_his_ddl(
        """
        CREATE TABLE T_CHARGE_DETAIL (
            CHARGE_ID TEXT PRIMARY KEY,
            VISIT_ID TEXT NOT NULL,
            AMOUNT NUMERIC(12, 2) NOT NULL,
            CHARGED_AT TIMESTAMP NOT NULL
        );
        """
    )


def _write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
