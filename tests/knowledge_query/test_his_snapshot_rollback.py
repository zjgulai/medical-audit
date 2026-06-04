import asyncio
from pathlib import Path

from pytest import MonkeyPatch
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from medical_audit_kb.audit.charge_rule_001 import DEFAULT_RULE_VERSION_KEY, RULE_KEY
from medical_audit_kb.cli import main
from medical_audit_kb.db.engine import create_schema, create_session_factory
from medical_audit_kb.db.models import AuditSnapshotRollback
from medical_audit_kb.db.repositories import AuditWorkflowRepository
from medical_audit_kb.domain.schemas import (
    AuditDataSnapshotCreate,
    AuditFindingCreate,
    AuditProjectCreate,
    AuditRuleCreate,
    AuditRunCreate,
    AuditTaskCreate,
    RuleVersionCreate,
)
from medical_audit_kb.his.snapshot_rollback import audit_his_snapshot_rollback_to_database


def test_his_snapshot_rollback_audit_dry_runs_then_executes(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'audit.db'}"
    asyncio.run(_create_snapshot_rollback_contract(database_url))

    dry_run_result = asyncio.run(
        audit_his_snapshot_rollback_to_database(
            database_url=database_url,
            rollback_key="rollback-charge-0001",
            project_key="audit-project-rollback",
            from_snapshot_key="snapshot-current",
            to_snapshot_key="snapshot-previous",
            reason="生产 staging 复核发现当前快照字段映射错误",
            requested_by="unit-test",
        )
    )
    execute_result = asyncio.run(
        audit_his_snapshot_rollback_to_database(
            database_url=database_url,
            rollback_key="rollback-charge-0001",
            project_key="audit-project-rollback",
            from_snapshot_key="snapshot-current",
            to_snapshot_key="snapshot-previous",
            reason="生产 staging 复核发现当前快照字段映射错误",
            requested_by="unit-test",
            execute=True,
        )
    )

    assert dry_run_result.status == "pass"
    assert dry_run_result.executed is False
    assert dry_run_result.impact_summary["affected_task_count"] == 1
    assert dry_run_result.impact_summary["affected_run_count"] == 1
    assert dry_run_result.impact_summary["affected_finding_count"] == 1
    assert execute_result.status == "pass"
    assert execute_result.executed is True
    assert execute_result.created_rollback_id is not None
    assert asyncio.run(_rollback_count(database_url)) == 1


def test_his_snapshot_rollback_audit_blocks_duplicate_key(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'audit.db'}"
    asyncio.run(_create_snapshot_rollback_contract(database_url))
    first_result = asyncio.run(
        audit_his_snapshot_rollback_to_database(
            database_url=database_url,
            rollback_key="rollback-charge-0001",
            project_key="audit-project-rollback",
            from_snapshot_key="snapshot-current",
            to_snapshot_key="snapshot-previous",
            reason="生产 staging 复核发现当前快照字段映射错误",
            execute=True,
        )
    )
    second_result = asyncio.run(
        audit_his_snapshot_rollback_to_database(
            database_url=database_url,
            rollback_key="rollback-charge-0001",
            project_key="audit-project-rollback",
            from_snapshot_key="snapshot-current",
            to_snapshot_key="snapshot-previous",
            reason="重复提交",
            execute=True,
        )
    )

    assert first_result.status == "pass"
    assert second_result.status == "fail"
    assert second_result.executed is False
    assert second_result.issues == ("rollback_key already exists: rollback-charge-0001",)
    assert asyncio.run(_rollback_count(database_url)) == 1


def test_his_snapshot_rollback_audit_blocks_same_snapshot(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'audit.db'}"
    asyncio.run(_create_snapshot_rollback_contract(database_url))

    result = asyncio.run(
        audit_his_snapshot_rollback_to_database(
            database_url=database_url,
            rollback_key="rollback-charge-0002",
            project_key="audit-project-rollback",
            from_snapshot_key="snapshot-current",
            to_snapshot_key="snapshot-current",
            reason="非法回滚目标",
            execute=True,
        )
    )

    assert result.status == "fail"
    assert result.executed is False
    assert "from_snapshot_key and to_snapshot_key must differ" in result.issues
    assert asyncio.run(_rollback_count(database_url)) == 0


def test_his_snapshot_rollback_audit_command_writes_reports(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'audit.db'}"
    asyncio.run(_create_snapshot_rollback_contract(database_url))
    monkeypatch.setenv("MEDICAL_AUDIT_TEST_DATABASE_URL", database_url)
    dry_run_report_path = tmp_path / "snapshot-rollback-dry-run.md"
    dry_run_json_path = tmp_path / "snapshot-rollback-dry-run.json"
    execute_report_path = tmp_path / "snapshot-rollback-execute.md"
    execute_json_path = tmp_path / "snapshot-rollback-execute.json"

    dry_run_exit_code = main(
        [
            "his-snapshot-rollback-audit",
            "--rollback-key",
            "rollback-charge-cli-0001",
            "--project-key",
            "audit-project-rollback",
            "--from-snapshot-key",
            "snapshot-current",
            "--to-snapshot-key",
            "snapshot-previous",
            "--reason",
            "生产 staging 复核发现当前快照字段映射错误",
            "--requested-by",
            "unit-test",
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
            "his-snapshot-rollback-audit",
            "--rollback-key",
            "rollback-charge-cli-0001",
            "--project-key",
            "audit-project-rollback",
            "--from-snapshot-key",
            "snapshot-current",
            "--to-snapshot-key",
            "snapshot-previous",
            "--reason",
            "生产 staging 复核发现当前快照字段映射错误",
            "--requested-by",
            "unit-test",
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
    assert "HIS 数据快照回滚审计报告" in dry_run_report_path.read_text(encoding="utf-8")
    assert '"execute_requested": false' in dry_run_json_path.read_text(encoding="utf-8")
    execute_json_body = execute_json_path.read_text(encoding="utf-8")
    assert '"execute_requested": true' in execute_json_body
    assert '"created_rollback_id":' in execute_json_body
    assert asyncio.run(_rollback_count(database_url)) == 1


async def _create_snapshot_rollback_contract(database_url: str) -> None:
    engine = create_async_engine(database_url)
    try:
        await create_schema(engine)
        session_factory = create_session_factory(engine)
        async with session_factory() as session, session.begin():
            repository = AuditWorkflowRepository(session)
            project = await repository.create_project(
                AuditProjectCreate(
                    project_key="audit-project-rollback",
                    name="收费合规快照回滚专项",
                    scenario_key="charging-compliance",
                    status="fixture",
                    owner_department="审计科",
                    created_by="unit-test",
                )
            )
            previous_snapshot = await repository.create_data_snapshot(
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
            current_snapshot = await repository.create_data_snapshot(
                AuditDataSnapshotCreate(
                    snapshot_key="snapshot-current",
                    project_id=project.id,
                    source_batch_key="his-batch-current",
                    time_range={"from": "2025-01-01", "to": "2025-01-31"},
                    row_counts={"T_CHARGE_DETAIL": 3},
                    checksum="sha256:current",
                    status="validated",
                )
            )
            task = await repository.create_task(
                AuditTaskCreate(
                    task_key="audit-task-current",
                    project_id=project.id,
                    snapshot_id=current_snapshot.id,
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
                    logic={"snapshot": "rollback"},
                    evidence_links={"knowledge_topics": ["重复收费"]},
                    created_by="unit-test",
                )
            )
            run = await repository.create_run(
                AuditRunCreate(
                    run_key="audit-run-current",
                    audit_task_id=task.id,
                    snapshot_id=current_snapshot.id,
                    rule_version_key=rule_version.version_key,
                    status="succeeded",
                )
            )
            await repository.create_finding(
                AuditFindingCreate(
                    finding_key="finding-current-001",
                    audit_run_id=run.id,
                    audit_task_id=task.id,
                    rule_version_id=rule_version.id,
                    snapshot_id=current_snapshot.id,
                    status="open",
                    finding_type="duplicate-charge",
                    severity="medium",
                    source_record_locator={"source_batch_key": "his-batch-current"},
                    calculation_trace={"duplicate_count": 2},
                    review_status="pending-review",
                )
            )
            assert previous_snapshot.id != current_snapshot.id
    finally:
        await engine.dispose()


async def _rollback_count(database_url: str) -> int:
    engine = create_async_engine(database_url)
    try:
        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            result = await session.execute(select(AuditSnapshotRollback))
            return len(result.scalars().all())
    finally:
        await engine.dispose()
