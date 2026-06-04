import asyncio
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from medical_audit_kb.db.engine import create_schema, create_session_factory
from medical_audit_kb.db.models import AuditDataSnapshot
from medical_audit_kb.db.repositories import AuditWorkflowRepository
from medical_audit_kb.domain.schemas import AuditProjectCreate
from medical_audit_kb.his.ddl_parser import HisDdlParseReport, parse_his_ddl
from medical_audit_kb.his.sample_quality import (
    HisSampleQualityReport,
    build_his_sample_quality_report,
)
from medical_audit_kb.his.snapshot_apply import (
    apply_his_snapshot_plan_with_engine,
    his_snapshot_apply_result_json,
    render_his_snapshot_apply_markdown,
)
from medical_audit_kb.his.snapshot_plan import HisSnapshotPlan, build_his_snapshot_plan


def test_his_snapshot_apply_dry_run_validates_without_insert(tmp_path: Path) -> None:
    asyncio.run(_assert_his_snapshot_apply_dry_run(tmp_path))


def test_his_snapshot_apply_execute_inserts_audit_data_snapshot(tmp_path: Path) -> None:
    asyncio.run(_assert_his_snapshot_apply_execute(tmp_path))


def test_his_snapshot_apply_blocks_duplicate_snapshot_key(tmp_path: Path) -> None:
    asyncio.run(_assert_his_snapshot_apply_duplicate_snapshot_key(tmp_path))


def test_his_snapshot_apply_blocks_failed_snapshot_plan(tmp_path: Path) -> None:
    asyncio.run(_assert_his_snapshot_apply_blocks_failed_plan(tmp_path))


async def _assert_his_snapshot_apply_dry_run(tmp_path: Path) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        await create_schema(engine)
        project_id = await _create_project(engine)
        plan = _passing_plan(tmp_path, project_id)

        result = await apply_his_snapshot_plan_with_engine(plan, engine=engine)

        assert result.status == "pass"
        assert result.execute_requested is False
        assert result.executed is False
        assert result.dry_run is True
        assert result.created_snapshot_id is None
        assert result.issues == ()
        assert "HIS 数据快照入库报告" in render_his_snapshot_apply_markdown(result)
        assert '"execute_requested": false' in his_snapshot_apply_result_json(result)
        assert await _snapshot_count(engine) == 0
    finally:
        await engine.dispose()


async def _assert_his_snapshot_apply_execute(tmp_path: Path) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        await create_schema(engine)
        project_id = await _create_project(engine)
        plan = _passing_plan(tmp_path, project_id)

        result = await apply_his_snapshot_plan_with_engine(plan, engine=engine, execute=True)

        assert result.status == "pass"
        assert result.execute_requested is True
        assert result.executed is True
        assert result.dry_run is False
        assert result.created_snapshot_id is not None
        assert await _snapshot_count(engine) == 1
        snapshot = await _get_snapshot(engine, result.created_snapshot_id)
        assert snapshot is not None
        assert snapshot.snapshot_key == "snapshot-his-0001"
        assert snapshot.row_counts == {"T_CHARGE_DETAIL": 1}
    finally:
        await engine.dispose()


async def _assert_his_snapshot_apply_duplicate_snapshot_key(tmp_path: Path) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        await create_schema(engine)
        project_id = await _create_project(engine)
        plan = _passing_plan(tmp_path, project_id)
        first_result = await apply_his_snapshot_plan_with_engine(
            plan,
            engine=engine,
            execute=True,
        )

        second_result = await apply_his_snapshot_plan_with_engine(
            plan,
            engine=engine,
            execute=True,
        )

        assert first_result.status == "pass"
        assert second_result.status == "fail"
        assert second_result.execute_requested is True
        assert second_result.executed is False
        assert second_result.dry_run is False
        assert "snapshot_key already exists: snapshot-his-0001" in second_result.issues
        assert await _snapshot_count(engine) == 1
    finally:
        await engine.dispose()


async def _assert_his_snapshot_apply_blocks_failed_plan(tmp_path: Path) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        await create_schema(engine)
        project_id = await _create_project(engine)
        plan = _failed_plan(tmp_path, project_id)

        result = await apply_his_snapshot_plan_with_engine(plan, engine=engine, execute=True)

        assert result.status == "fail"
        assert result.execute_requested is True
        assert result.executed is False
        assert result.dry_run is False
        assert "snapshot plan status is not PASS" in result.issues
        assert "snapshot plan has no audit_data_snapshot_payload" in result.issues
        assert await _snapshot_count(engine) == 0
    finally:
        await engine.dispose()


async def _create_project(engine: AsyncEngine) -> UUID:
    session_factory = create_session_factory(engine)
    async with session_factory() as session, session.begin():
        project = await AuditWorkflowRepository(session).create_project(
            AuditProjectCreate(
                project_key="audit-project-his-snapshot-apply",
                name="HIS snapshot apply fixture",
                scenario_key="charging-compliance",
                status="fixture",
                owner_department="审计科",
                created_by="unit-test",
            )
        )
        return project.id


async def _snapshot_count(engine: AsyncEngine) -> int:
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        result = await session.execute(select(AuditDataSnapshot))
        return len(result.scalars().all())


async def _get_snapshot(engine: AsyncEngine, snapshot_id: UUID) -> AuditDataSnapshot | None:
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        return await session.get(AuditDataSnapshot, snapshot_id)


def _passing_plan(tmp_path: Path, project_id: UUID) -> HisSnapshotPlan:
    return build_his_snapshot_plan(
        _passing_quality_report(tmp_path),
        project_id=project_id,
        snapshot_key="snapshot-his-0001",
        source_batch_key="his-batch-0001",
        time_range={"from": "2025-01-01", "to": "2025-01-31"},
    )


def _failed_plan(tmp_path: Path, project_id: UUID) -> HisSnapshotPlan:
    sample_root = tmp_path / "failed-samples"
    sample_root.mkdir()
    _write_text(sample_root / "T_CHARGE_DETAIL.csv", "CHARGE_ID,VISIT_ID,AMOUNT\nC001,,1\n")
    return build_his_snapshot_plan(
        build_his_sample_quality_report(sample_root, ddl_report=_ddl_report()),
        project_id=project_id,
        snapshot_key="snapshot-his-failed",
        source_batch_key="his-batch-failed",
    )


def _passing_quality_report(tmp_path: Path) -> HisSampleQualityReport:
    sample_root = tmp_path / "samples"
    sample_root.mkdir()
    _write_text(
        sample_root / "T_CHARGE_DETAIL.csv",
        "CHARGE_ID,VISIT_ID,AMOUNT,CHARGED_AT\nC001,V001,1,2025-01-01\n",
    )
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
