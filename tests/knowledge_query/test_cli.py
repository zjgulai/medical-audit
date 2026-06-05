import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from pytest import MonkeyPatch, raises
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from medical_audit_kb.cli import main
from medical_audit_kb.db.engine import create_schema, create_session_factory
from medical_audit_kb.db.models import AuditDataSnapshot, AuditLogEvent, HisStagingRow
from medical_audit_kb.db.repositories import AuditWorkflowRepository, HisIngestionRepository
from medical_audit_kb.domain.schemas import (
    AuditProjectCreate,
    HisSourceBatchCreate,
    HisTableSchemaCreate,
)
from medical_audit_kb.generation.citations import Citation


def test_acceptance_run_writes_markdown_and_json_outputs(tmp_path: Path) -> None:
    source_root = tmp_path / "医保审核前期资料"
    _write_text(source_root / "医保目录" / "catalog.md", "# 医保目录\n医保目录内容")
    _write_binary(source_root / "风险负面清单" / "scan.png", b"png")
    report_path = tmp_path / "report.md"
    json_path = tmp_path / "report.json"

    exit_code = main(
        [
            "acceptance-run",
            "--source-root",
            str(source_root),
            "--output",
            str(report_path),
            "--json-output",
            str(json_path),
            "--package-version-key",
            "package-test",
        ]
    )

    assert exit_code == 0
    assert "知识库真实资料索引验收报告" in report_path.read_text(encoding="utf-8")
    assert '"source_package_version_key": "package-test"' in json_path.read_text(encoding="utf-8")


def test_acceptance_run_returns_nonzero_when_gate_fails(tmp_path: Path) -> None:
    source_root = tmp_path / "医保审核前期资料"
    _write_text(source_root / "医保目录" / "broken.pdf", "not a pdf")
    report_path = tmp_path / "report.md"

    exit_code = main(
        [
            "acceptance-run",
            "--source-root",
            str(source_root),
            "--output",
            str(report_path),
        ]
    )

    assert exit_code == 2
    assert "总体状态：`FAIL`" in report_path.read_text(encoding="utf-8")


def test_his_ddl_parse_command_writes_markdown_and_json_outputs(tmp_path: Path) -> None:
    ddl_file = tmp_path / "his.sql"
    ddl_file.write_text(
        """
        CREATE TABLE T_CHARGE_DETAIL (
            CHARGE_ID TEXT PRIMARY KEY,
            VISIT_ID TEXT NOT NULL,
            AMOUNT NUMERIC(12, 2) NOT NULL,
            CHARGED_AT TIMESTAMP
        );
        """,
        encoding="utf-8",
    )
    report_path = tmp_path / "his-ddl-report.md"
    json_path = tmp_path / "his-ddl-report.json"

    exit_code = main(
        [
            "his-ddl-parse",
            "--ddl-file",
            str(ddl_file),
            "--output",
            str(report_path),
            "--json-output",
            str(json_path),
        ]
    )

    assert exit_code == 0
    assert "HIS DDL 解析报告" in report_path.read_text(encoding="utf-8")
    assert "## T_CHARGE_DETAIL" in report_path.read_text(encoding="utf-8")
    assert '"business_domain": "charge_detail"' in json_path.read_text(encoding="utf-8")


def test_his_sample_quality_command_writes_markdown_and_json_outputs(tmp_path: Path) -> None:
    ddl_file = tmp_path / "his.sql"
    ddl_file.write_text(
        """
        CREATE TABLE T_CHARGE_DETAIL (
            CHARGE_ID TEXT PRIMARY KEY,
            VISIT_ID TEXT NOT NULL,
            AMOUNT NUMERIC(12, 2) NOT NULL,
            CHARGED_AT TIMESTAMP NOT NULL
        );
        """,
        encoding="utf-8",
    )
    ddl_json_path = tmp_path / "his-ddl-report.json"
    main(
        [
            "his-ddl-parse",
            "--ddl-file",
            str(ddl_file),
            "--output",
            str(tmp_path / "his-ddl-report.md"),
            "--json-output",
            str(ddl_json_path),
        ]
    )
    sample_root = tmp_path / "samples"
    sample_root.mkdir()
    _write_text(
        sample_root / "T_CHARGE_DETAIL.csv",
        "CHARGE_ID,VISIT_ID,AMOUNT,CHARGED_AT\nC001,V001,120.50,2025-01-01 08:00:00\n",
    )
    report_path = tmp_path / "his-sample-quality.md"
    json_path = tmp_path / "his-sample-quality.json"

    exit_code = main(
        [
            "his-sample-quality",
            "--sample-root",
            str(sample_root),
            "--ddl-report-json",
            str(ddl_json_path),
            "--output",
            str(report_path),
            "--json-output",
            str(json_path),
        ]
    )

    assert exit_code == 0
    assert "HIS 脱敏样本数据质量报告" in report_path.read_text(encoding="utf-8")
    assert '"total_row_count": 1' in json_path.read_text(encoding="utf-8")


def test_his_staging_import_command_dry_runs_then_executes(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'his-staging.db'}"
    asyncio.run(_create_his_staging_contract(database_url))
    monkeypatch.setenv("MEDICAL_AUDIT_TEST_DATABASE_URL", database_url)

    ddl_file = tmp_path / "his.sql"
    ddl_file.write_text(
        """
        CREATE TABLE T_CHARGE_DETAIL (
            CHARGE_ID TEXT PRIMARY KEY,
            VISIT_ID TEXT NOT NULL,
            AMOUNT NUMERIC(12, 2) NOT NULL,
            CHARGED_AT TIMESTAMP NOT NULL
        );
        """,
        encoding="utf-8",
    )
    ddl_json_path = tmp_path / "his-ddl-report.json"
    main(
        [
            "his-ddl-parse",
            "--ddl-file",
            str(ddl_file),
            "--output",
            str(tmp_path / "his-ddl-report.md"),
            "--json-output",
            str(ddl_json_path),
        ]
    )
    sample_root = tmp_path / "samples"
    sample_root.mkdir()
    _write_text(
        sample_root / "T_CHARGE_DETAIL.csv",
        "CHARGE_ID,VISIT_ID,AMOUNT,CHARGED_AT\n"
        "C001,V001,120.50,2025-01-01 08:00:00\n"
        "C002,V002,80.00,2025-01-02 08:00:00\n",
    )
    quality_json_path = tmp_path / "his-sample-quality.json"
    main(
        [
            "his-sample-quality",
            "--sample-root",
            str(sample_root),
            "--ddl-report-json",
            str(ddl_json_path),
            "--output",
            str(tmp_path / "his-sample-quality.md"),
            "--json-output",
            str(quality_json_path),
        ]
    )

    dry_run_report_path = tmp_path / "his-staging-import-dry-run.md"
    dry_run_json_path = tmp_path / "his-staging-import-dry-run.json"
    dry_run_exit_code = main(
        [
            "his-staging-import",
            "--quality-report-json",
            str(quality_json_path),
            "--source-batch-key",
            "his-batch-0001",
            "--database-url-env",
            "MEDICAL_AUDIT_TEST_DATABASE_URL",
            "--output",
            str(dry_run_report_path),
            "--json-output",
            str(dry_run_json_path),
        ]
    )
    execute_report_path = tmp_path / "his-staging-import-execute.md"
    execute_json_path = tmp_path / "his-staging-import-execute.json"
    execute_exit_code = main(
        [
            "his-staging-import",
            "--quality-report-json",
            str(quality_json_path),
            "--source-batch-key",
            "his-batch-0001",
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
    assert "HIS 脱敏样本 staging 导入报告" in dry_run_report_path.read_text(encoding="utf-8")
    assert '"execute_requested": false' in dry_run_json_path.read_text(encoding="utf-8")
    execute_json_body = execute_json_path.read_text(encoding="utf-8")
    assert '"execute_requested": true' in execute_json_body
    assert '"inserted_row_count": 2' in execute_json_body
    assert asyncio.run(_his_staging_row_count(database_url)) == 2


def test_his_snapshot_plan_command_writes_payload_outputs(tmp_path: Path) -> None:
    ddl_file = tmp_path / "his.sql"
    ddl_file.write_text(
        """
        CREATE TABLE T_CHARGE_DETAIL (
            CHARGE_ID TEXT PRIMARY KEY,
            VISIT_ID TEXT NOT NULL,
            AMOUNT NUMERIC(12, 2) NOT NULL,
            CHARGED_AT TIMESTAMP NOT NULL
        );
        """,
        encoding="utf-8",
    )
    ddl_json_path = tmp_path / "his-ddl-report.json"
    main(
        [
            "his-ddl-parse",
            "--ddl-file",
            str(ddl_file),
            "--output",
            str(tmp_path / "his-ddl-report.md"),
            "--json-output",
            str(ddl_json_path),
        ]
    )
    sample_root = tmp_path / "samples"
    sample_root.mkdir()
    _write_text(
        sample_root / "T_CHARGE_DETAIL.csv",
        "CHARGE_ID,VISIT_ID,AMOUNT,CHARGED_AT\nC001,V001,120.50,2025-01-01 08:00:00\n",
    )
    quality_json_path = tmp_path / "his-sample-quality.json"
    main(
        [
            "his-sample-quality",
            "--sample-root",
            str(sample_root),
            "--ddl-report-json",
            str(ddl_json_path),
            "--output",
            str(tmp_path / "his-sample-quality.md"),
            "--json-output",
            str(quality_json_path),
        ]
    )
    report_path = tmp_path / "his-snapshot-plan.md"
    json_path = tmp_path / "his-snapshot-plan.json"

    exit_code = main(
        [
            "his-snapshot-plan",
            "--quality-report-json",
            str(quality_json_path),
            "--project-id",
            "11111111-1111-4111-8111-111111111111",
            "--snapshot-key",
            "snapshot-his-0001",
            "--source-batch-key",
            "his-batch-0001",
            "--time-range-json",
            '{"from":"2025-01-01","to":"2025-01-31"}',
            "--output",
            str(report_path),
            "--json-output",
            str(json_path),
        ]
    )

    assert exit_code == 0
    assert "HIS 数据快照计划" in report_path.read_text(encoding="utf-8")
    json_body = json_path.read_text(encoding="utf-8")
    assert '"can_create_snapshot": true' in json_body
    assert '"snapshot_key": "snapshot-his-0001"' in json_body
    assert '"source_batch_key": "his-batch-0001"' in json_body


def test_his_snapshot_apply_command_dry_runs_then_executes(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'audit.db'}"
    project_id = asyncio.run(_create_audit_project(database_url))
    monkeypatch.setenv("MEDICAL_AUDIT_TEST_DATABASE_URL", database_url)

    ddl_file = tmp_path / "his.sql"
    ddl_file.write_text(
        """
        CREATE TABLE T_CHARGE_DETAIL (
            CHARGE_ID TEXT PRIMARY KEY,
            VISIT_ID TEXT NOT NULL,
            AMOUNT NUMERIC(12, 2) NOT NULL,
            CHARGED_AT TIMESTAMP NOT NULL
        );
        """,
        encoding="utf-8",
    )
    ddl_json_path = tmp_path / "his-ddl-report.json"
    main(
        [
            "his-ddl-parse",
            "--ddl-file",
            str(ddl_file),
            "--output",
            str(tmp_path / "his-ddl-report.md"),
            "--json-output",
            str(ddl_json_path),
        ]
    )
    sample_root = tmp_path / "samples"
    sample_root.mkdir()
    _write_text(
        sample_root / "T_CHARGE_DETAIL.csv",
        "CHARGE_ID,VISIT_ID,AMOUNT,CHARGED_AT\nC001,V001,120.50,2025-01-01 08:00:00\n",
    )
    quality_json_path = tmp_path / "his-sample-quality.json"
    main(
        [
            "his-sample-quality",
            "--sample-root",
            str(sample_root),
            "--ddl-report-json",
            str(ddl_json_path),
            "--output",
            str(tmp_path / "his-sample-quality.md"),
            "--json-output",
            str(quality_json_path),
        ]
    )
    snapshot_plan_json_path = tmp_path / "his-snapshot-plan.json"
    main(
        [
            "his-snapshot-plan",
            "--quality-report-json",
            str(quality_json_path),
            "--project-id",
            str(project_id),
            "--snapshot-key",
            "snapshot-his-0001",
            "--source-batch-key",
            "his-batch-0001",
            "--output",
            str(tmp_path / "his-snapshot-plan.md"),
            "--json-output",
            str(snapshot_plan_json_path),
        ]
    )

    dry_run_report_path = tmp_path / "his-snapshot-apply-dry-run.md"
    dry_run_json_path = tmp_path / "his-snapshot-apply-dry-run.json"
    dry_run_exit_code = main(
        [
            "his-snapshot-apply",
            "--snapshot-plan-json",
            str(snapshot_plan_json_path),
            "--database-url-env",
            "MEDICAL_AUDIT_TEST_DATABASE_URL",
            "--output",
            str(dry_run_report_path),
            "--json-output",
            str(dry_run_json_path),
        ]
    )
    execute_report_path = tmp_path / "his-snapshot-apply-execute.md"
    execute_json_path = tmp_path / "his-snapshot-apply-execute.json"
    execute_exit_code = main(
        [
            "his-snapshot-apply",
            "--snapshot-plan-json",
            str(snapshot_plan_json_path),
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
    assert "HIS 数据快照入库报告" in dry_run_report_path.read_text(encoding="utf-8")
    assert '"execute_requested": false' in dry_run_json_path.read_text(encoding="utf-8")
    execute_json_body = execute_json_path.read_text(encoding="utf-8")
    assert '"execute_requested": true' in execute_json_body
    assert '"executed": true' in execute_json_body
    assert asyncio.run(_audit_data_snapshot_count(database_url)) == 1


def test_audit_log_retention_command_dry_runs_without_deleting_events(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'audit-log-retention.db'}"
    old_event_id, _new_event_id = asyncio.run(_seed_audit_log_events(database_url))
    monkeypatch.setenv("MEDICAL_AUDIT_TEST_DATABASE_URL", database_url)
    report_path = tmp_path / "audit-log-retention-dry-run.md"
    json_path = tmp_path / "audit-log-retention-dry-run.json"

    exit_code = main(
        [
            "audit-log-retention",
            "--database-url-env",
            "MEDICAL_AUDIT_TEST_DATABASE_URL",
            "--retention-days",
            "180",
            "--now",
            "2026-06-05T00:00:00Z",
            "--output",
            str(report_path),
            "--json-output",
            str(json_path),
        ]
    )

    result = json.loads(json_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert "审计日志保留归档报告" in report_path.read_text(encoding="utf-8")
    assert result["mode"] == "dry-run"
    assert result["execute_requested"] is False
    assert result["executed"] is False
    assert result["expired_event_count"] == 1
    assert result["archived_event_count"] == 0
    assert result["deleted_event_count"] == 0
    assert result["expired_events"][0]["event_id"] == old_event_id
    assert asyncio.run(_audit_log_event_count(database_url)) == 2


def test_audit_log_retention_command_archives_then_deletes_expired_events(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'audit-log-retention.db'}"
    old_event_id, new_event_id = asyncio.run(_seed_audit_log_events(database_url))
    monkeypatch.setenv("MEDICAL_AUDIT_TEST_DATABASE_URL", database_url)
    report_path = tmp_path / "audit-log-retention-execute.md"
    json_path = tmp_path / "audit-log-retention-execute.json"
    archive_path = tmp_path / "archive" / "audit-log-retention.jsonl"

    exit_code = main(
        [
            "audit-log-retention",
            "--database-url-env",
            "MEDICAL_AUDIT_TEST_DATABASE_URL",
            "--retention-days",
            "180",
            "--now",
            "2026-06-05T00:00:00Z",
            "--archive-output",
            str(archive_path),
            "--output",
            str(report_path),
            "--json-output",
            str(json_path),
            "--execute",
        ]
    )

    result = json.loads(json_path.read_text(encoding="utf-8"))
    archive_rows = [
        json.loads(line) for line in archive_path.read_text(encoding="utf-8").splitlines()
    ]
    remaining_event_ids = asyncio.run(_audit_log_event_ids(database_url))
    assert exit_code == 0
    assert result["mode"] == "execute"
    assert result["execute_requested"] is True
    assert result["executed"] is True
    assert result["expired_event_count"] == 1
    assert result["archived_event_count"] == 1
    assert result["deleted_event_count"] == 1
    assert result["archive_output"] == str(archive_path)
    assert isinstance(result["archive_sha256"], str)
    assert len(result["archive_sha256"]) == 64
    assert archive_rows[0]["event_id"] == old_event_id
    assert archive_rows[0]["payload"]["api_key"] == "raw-secret"
    assert remaining_event_ids == [new_event_id]


def test_audit_log_retention_command_signs_archive_and_detects_tampering(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'audit-log-retention.db'}"
    asyncio.run(_seed_audit_log_events(database_url))
    monkeypatch.setenv("MEDICAL_AUDIT_TEST_DATABASE_URL", database_url)
    monkeypatch.setenv("MEDICAL_AUDIT_ARCHIVE_SIGNING_SECRET", "test-signing-secret")
    report_path = tmp_path / "audit-log-retention-signed.md"
    json_path = tmp_path / "audit-log-retention-signed.json"
    archive_path = tmp_path / "archive" / "audit-log-retention.jsonl"
    signature_path = tmp_path / "archive" / "audit-log-retention.signature.json"

    exit_code = main(
        [
            "audit-log-retention",
            "--database-url-env",
            "MEDICAL_AUDIT_TEST_DATABASE_URL",
            "--retention-days",
            "180",
            "--now",
            "2026-06-05T00:00:00Z",
            "--archive-output",
            str(archive_path),
            "--signature-output",
            str(signature_path),
            "--signing-secret-env",
            "MEDICAL_AUDIT_ARCHIVE_SIGNING_SECRET",
            "--signing-key-id",
            "audit-log-hmac-v1",
            "--signing-subject",
            "it-admin:retention",
            "--previous-signature-sha256",
            "0" * 64,
            "--output",
            str(report_path),
            "--json-output",
            str(json_path),
            "--execute",
        ]
    )

    result = json.loads(json_path.read_text(encoding="utf-8"))
    signature_text = signature_path.read_text(encoding="utf-8")
    signature = json.loads(signature_text)
    verify_path = tmp_path / "audit-log-archive-verify.md"
    verify_json_path = tmp_path / "audit-log-archive-verify.json"
    verify_exit_code = main(
        [
            "audit-log-archive-verify",
            "--archive-output",
            str(archive_path),
            "--signature-manifest",
            str(signature_path),
            "--signing-secret-env",
            "MEDICAL_AUDIT_ARCHIVE_SIGNING_SECRET",
            "--output",
            str(verify_path),
            "--json-output",
            str(verify_json_path),
        ]
    )
    archive_path.write_text(
        archive_path.read_text(encoding="utf-8") + "{}\n",
        encoding="utf-8",
    )
    tamper_json_path = tmp_path / "audit-log-archive-verify-tamper.json"
    tamper_exit_code = main(
        [
            "audit-log-archive-verify",
            "--archive-output",
            str(archive_path),
            "--signature-manifest",
            str(signature_path),
            "--signing-secret-env",
            "MEDICAL_AUDIT_ARCHIVE_SIGNING_SECRET",
            "--output",
            str(tmp_path / "audit-log-archive-verify-tamper.md"),
            "--json-output",
            str(tamper_json_path),
        ]
    )

    verify_result = json.loads(verify_json_path.read_text(encoding="utf-8"))
    tamper_result = json.loads(tamper_json_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert result["signature_manifest_output"] == str(signature_path)
    assert isinstance(result["signature_manifest_sha256"], str)
    assert len(result["signature_manifest_sha256"]) == 64
    assert signature["algorithm"] == "hmac-sha256"
    assert signature["key_id"] == "audit-log-hmac-v1"
    assert signature["signing_subject"] == "it-admin:retention"
    assert signature["previous_signature_sha256"] == "0" * 64
    assert signature["archive_sha256"] == result["archive_sha256"]
    assert "test-signing-secret" not in signature_text
    assert verify_exit_code == 0
    assert verify_result["status"] == "pass"
    assert verify_result["signature_valid"] is True
    assert verify_result["archive_sha256_valid"] is True
    assert tamper_exit_code == 2
    assert tamper_result["status"] == "fail"
    assert tamper_result["archive_sha256_valid"] is False
    assert "archive sha256 mismatch" in tamper_result["issues"]


def test_audit_log_retention_command_derives_controlled_archive_layout(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'audit-log-retention.db'}"
    asyncio.run(_seed_audit_log_events(database_url))
    monkeypatch.setenv("MEDICAL_AUDIT_TEST_DATABASE_URL", database_url)
    monkeypatch.setenv("MEDICAL_AUDIT_ARCHIVE_SIGNING_SECRET", "test-signing-secret")
    archive_root = tmp_path / "controlled-audit-log-archive"
    report_path = tmp_path / "audit-log-retention-root.md"
    json_path = tmp_path / "audit-log-retention-root.json"
    expected_archive_path = (
        archive_root / "audit-log-events" / "2026" / "06" / "05" / "retention-batch-0001.jsonl"
    )
    expected_signature_path = (
        archive_root
        / "audit-log-events"
        / "2026"
        / "06"
        / "05"
        / "retention-batch-0001.signature.json"
    )

    exit_code = main(
        [
            "audit-log-retention",
            "--database-url-env",
            "MEDICAL_AUDIT_TEST_DATABASE_URL",
            "--retention-days",
            "180",
            "--now",
            "2026-06-05T00:00:00Z",
            "--archive-root",
            str(archive_root),
            "--archive-batch-key",
            "retention-batch-0001",
            "--signing-secret-env",
            "MEDICAL_AUDIT_ARCHIVE_SIGNING_SECRET",
            "--signing-key-id",
            "audit-log-hmac-v1",
            "--output",
            str(report_path),
            "--json-output",
            str(json_path),
            "--execute",
        ]
    )

    result = json.loads(json_path.read_text(encoding="utf-8"))
    verify_json_path = tmp_path / "audit-log-root-verify.json"
    verify_exit_code = main(
        [
            "audit-log-archive-verify",
            "--archive-output",
            str(expected_archive_path),
            "--signature-manifest",
            str(expected_signature_path),
            "--signing-secret-env",
            "MEDICAL_AUDIT_ARCHIVE_SIGNING_SECRET",
            "--output",
            str(tmp_path / "audit-log-root-verify.md"),
            "--json-output",
            str(verify_json_path),
        ]
    )
    verify_result = json.loads(verify_json_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert result["archive_root"] == str(archive_root)
    assert result["archive_layout"] == "audit-log-events/YYYY/MM/DD/<batch-key>.jsonl"
    assert result["archive_batch_key"] == "retention-batch-0001"
    assert result["archive_output"] == str(expected_archive_path)
    assert result["signature_manifest_output"] == str(expected_signature_path)
    assert expected_archive_path.exists()
    assert expected_signature_path.exists()
    assert verify_exit_code == 0
    assert verify_result["status"] == "pass"


def test_audit_log_retention_command_rejects_archive_batch_path_escape(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'audit-log-retention.db'}"
    asyncio.run(_seed_audit_log_events(database_url))
    monkeypatch.setenv("MEDICAL_AUDIT_TEST_DATABASE_URL", database_url)

    with raises(SystemExit) as exc_info:
        main(
            [
                "audit-log-retention",
                "--database-url-env",
                "MEDICAL_AUDIT_TEST_DATABASE_URL",
                "--retention-days",
                "180",
                "--now",
                "2026-06-05T00:00:00Z",
                "--archive-root",
                str(tmp_path / "controlled-audit-log-archive"),
                "--archive-batch-key",
                "../escape",
                "--output",
                str(tmp_path / "audit-log-retention-root.md"),
                "--execute",
            ]
        )

    assert "archive_batch_key" in str(exc_info.value)
    assert not (tmp_path / "escape.jsonl").exists()


def test_index_build_and_evaluate_index_commands_write_outputs(tmp_path: Path) -> None:
    source_root = tmp_path / "医保审核前期资料"
    _write_text(
        source_root / "全量法律" / "医保基金监管条例.md",
        "第一条 医疗机构应当保留医保基金审核依据。",
    )
    index_root = tmp_path / "index"
    build_summary = tmp_path / "index-summary.json"
    evaluation_report = tmp_path / "evaluation.md"
    evaluation_json = tmp_path / "evaluation.json"

    build_exit_code = main(
        [
            "index-build",
            "--source-root",
            str(source_root),
            "--index-root",
            str(index_root),
            "--json-output",
            str(build_summary),
            "--package-version-key",
            "package-test",
            "--max-chunks",
            "1",
        ]
    )
    evaluate_exit_code = main(
        [
            "evaluate-index",
            "--source-root",
            str(source_root),
            "--index-root",
            str(index_root),
            "--output",
            str(evaluation_report),
            "--json-output",
            str(evaluation_json),
            "--max-cases",
            "1",
            "--top-k",
            "3",
            "--query-terms",
            "医保",
        ]
    )

    assert build_exit_code == 0
    assert evaluate_exit_code == 0
    assert '"source_package_version_key": "package-test"' in build_summary.read_text(
        encoding="utf-8"
    )
    assert '"persistent_chunk_limit": 1' in build_summary.read_text(encoding="utf-8")
    assert "知识库真实资料检索评测报告" in evaluation_report.read_text(encoding="utf-8")
    assert '"case_count": 1' in evaluation_json.read_text(encoding="utf-8")


def test_evaluate_index_accepts_fixed_cases_file(tmp_path: Path) -> None:
    source_root = tmp_path / "医保审核前期资料"
    _write_text(
        source_root / "全量法律" / "医保基金监管条例.md",
        "第一条 医疗机构应当保留医保基金审核依据。",
    )
    index_root = tmp_path / "index"
    cases_file = tmp_path / "cases.yaml"
    evaluation_report = tmp_path / "evaluation.md"
    evaluation_json = tmp_path / "evaluation.json"

    cases_file.write_text(
        """
cases:
  - case_id: fixed-case-001
    question: 医疗机构需要保留什么审核依据？
    expected_evidence:
      - source_collection: medical-insurance-laws
        source_path: 全量法律/医保基金监管条例.md
        article_or_rule: 第一条
""".strip(),
        encoding="utf-8",
    )

    main(
        [
            "index-build",
            "--source-root",
            str(source_root),
            "--index-root",
            str(index_root),
            "--package-version-key",
            "package-test",
        ]
    )
    evaluate_exit_code = main(
        [
            "evaluate-index",
            "--source-root",
            str(source_root),
            "--index-root",
            str(index_root),
            "--output",
            str(evaluation_report),
            "--json-output",
            str(evaluation_json),
            "--cases-file",
            str(cases_file),
            "--max-cases",
            "1",
        ]
    )

    assert evaluate_exit_code == 0
    assert "fixed-case-001" in evaluation_json.read_text(encoding="utf-8")
    assert '"case_count": 1' in evaluation_json.read_text(encoding="utf-8")


def test_evaluate_postgres_index_command_writes_outputs(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    source_root = tmp_path / "医保审核前期资料"
    _write_text(
        source_root / "全量法律" / "医保基金监管条例.md",
        "第一条 医疗机构应当保留医保基金审核依据。",
    )
    cases_file = tmp_path / "cases.yaml"
    evaluation_report = tmp_path / "postgres-evaluation.md"
    evaluation_json = tmp_path / "postgres-evaluation.json"
    cases_file.write_text(
        """
cases:
  - case_id: postgres-fixed-case-001
    question: 医疗机构需要保留什么审核依据？
    expected_evidence:
      - source_collection: medical-insurance-laws
        source_path: 全量法律/医保基金监管条例.md
        article_or_rule: 第一条
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("TEST_DATABASE_URL", "postgresql://user:pass@localhost/db")
    captured_kwargs: dict[str, object] = {}

    def fake_load_postgres_hybrid_search_engine(**kwargs: object) -> EmptySearchEngine:
        captured_kwargs.update(kwargs)
        return EmptySearchEngine()

    monkeypatch.setattr(
        "medical_audit_kb.cli.load_postgres_hybrid_search_engine",
        fake_load_postgres_hybrid_search_engine,
    )

    exit_code = main(
        [
            "evaluate-postgres-index",
            "--source-root",
            str(source_root),
            "--database-url-env",
            "TEST_DATABASE_URL",
            "--output",
            str(evaluation_report),
            "--json-output",
            str(evaluation_json),
            "--cases-file",
            str(cases_file),
            "--max-cases",
            "1",
            "--index-version-status",
            "candidate",
            "--index-version-key",
            "full-rebuild-next",
        ]
    )

    assert exit_code == 0
    assert "知识库真实资料检索评测报告" in evaluation_report.read_text(encoding="utf-8")
    assert '"case_count": 1' in evaluation_json.read_text(encoding="utf-8")
    assert captured_kwargs["index_version_status"] == "candidate"
    assert captured_kwargs["index_version_key"] == "full-rebuild-next"


def test_evaluate_answers_command_writes_answer_quality_outputs(tmp_path: Path) -> None:
    source_root = tmp_path / "医保审核前期资料"
    _write_text(
        source_root / "全量法律" / "医保基金监管条例.md",
        "第一条 医疗机构应当保留医保基金审核依据。",
    )
    index_root = tmp_path / "index"
    cases_file = tmp_path / "answer-cases.yaml"
    report_path = tmp_path / "answer-evaluation.md"
    json_path = tmp_path / "answer-evaluation.json"

    cases_file.write_text(
        """
cases:
  - case_id: answer-case-001
    question: 医疗机构需要保留什么审核依据？
    expected_behavior: answer
    required_evidence_terms: [第一条]
    required_answer_terms: [审核依据]
    required_citation_terms: [医疗机构]
  - case_id: refusal-case-001
    question: 请给出资料中不存在的处罚金额。
    expected_behavior: refuse
    required_evidence_terms: [不存在的处罚金额]
""".strip(),
        encoding="utf-8",
    )

    main(
        [
            "index-build",
            "--source-root",
            str(source_root),
            "--index-root",
            str(index_root),
            "--package-version-key",
            "package-test",
        ]
    )
    exit_code = main(
        [
            "evaluate-answers",
            "--index-root",
            str(index_root),
            "--cases-file",
            str(cases_file),
            "--output",
            str(report_path),
            "--json-output",
            str(json_path),
            "--max-cases",
            "2",
        ]
    )

    assert exit_code == 0
    assert "知识库答案生成质量评测报告" in report_path.read_text(encoding="utf-8")
    assert '"case_count": 2' in json_path.read_text(encoding="utf-8")
    assert '"pass_rate": 1.0' in json_path.read_text(encoding="utf-8")


def test_answer_provider_smoke_command_writes_preflight_outputs(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    report_path = tmp_path / "answer-provider-smoke.md"
    json_path = tmp_path / "answer-provider-smoke.json"

    monkeypatch.setattr(
        "medical_audit_kb.cli.OpenAICompatibleAnswerGenerationProvider.from_env",
        lambda **kwargs: StaticAnswerSmokeProvider(),
    )

    exit_code = main(
        [
            "answer-provider-smoke",
            "--answer-provider",
            "openai",
            "--output",
            str(report_path),
            "--json-output",
            str(json_path),
        ]
    )

    assert exit_code == 0
    assert "答案生成 Provider 预检报告" in report_path.read_text(encoding="utf-8")
    assert '"success": true' in json_path.read_text(encoding="utf-8")


def test_answer_provider_smoke_command_accepts_anthropic_provider(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    report_path = tmp_path / "answer-provider-smoke.md"

    monkeypatch.setattr(
        "medical_audit_kb.cli.AnthropicAnswerGenerationProvider.from_env",
        lambda **kwargs: StaticAnswerSmokeProvider(),
    )

    exit_code = main(
        [
            "answer-provider-smoke",
            "--answer-provider",
            "anthropic",
            "--answer-model",
            "claude-test",
            "--answer-api-key-env",
            "ANTHROPIC_API_KEY",
            "--output",
            str(report_path),
        ]
    )

    assert exit_code == 0
    assert "总体状态：`PASS`" in report_path.read_text(encoding="utf-8")


def test_pgvector_import_plan_command_writes_outputs(tmp_path: Path) -> None:
    index_root = tmp_path / "index"
    report_path = tmp_path / "pgvector-import-plan.md"
    json_path = tmp_path / "pgvector-import-plan.json"
    _write_text(
        index_root / "summary.json",
        """
{
  "persistent_chunk_count": 1,
  "embedding_count": 1,
  "failed_file_count": 0,
  "pending_file_count": 0,
  "embedding_provider": "openai",
  "embedding_model": "kimi-for-coding",
  "embedding_provider_version": "v1",
  "embedding_dimension": 2
}
""".lstrip(),
    )
    _write_text(
        index_root / "chunks.jsonl",
        '{"chunk_id":"chunk-1","text":"医保审核依据"}\n',
    )
    _write_text(
        index_root / "embeddings.jsonl",
        (
            '{"chunk_id":"chunk-1","text":"医保审核依据","embedding":[1.0,0.0],'
            '"provider":"openai","model_name":"kimi-for-coding",'
            '"provider_version":"v1","dimension":2,"metadata":{}}\n'
        ),
    )
    _write_text(index_root / "failed_files.jsonl", "")
    _write_text(index_root / "pending_files.jsonl", "")

    exit_code = main(
        [
            "pgvector-import-plan",
            "--index-root",
            str(index_root),
            "--output",
            str(report_path),
            "--json-output",
            str(json_path),
            "--schema-dimension",
            "2",
        ]
    )

    assert exit_code == 0
    assert "知识库 pgvector 导入前校验报告" in report_path.read_text(encoding="utf-8")
    assert '"ready_for_import": true' in json_path.read_text(encoding="utf-8")


def test_pgvector_import_command_writes_dry_run_outputs(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    _write_text(source_root / "全量法律" / "医保政策.md", "第一条 医保审核依据。")
    index_root = tmp_path / "index"
    report_path = tmp_path / "pgvector-import.md"
    json_path = tmp_path / "pgvector-import.json"
    _write_text(
        index_root / "summary.json",
        """
{
  "job_type": "full-rebuild",
  "index_version_key": "full-rebuild-test",
  "source_package_version_key": "source-package-test",
  "persistent_chunk_count": 1,
  "embedding_count": 1,
  "failed_file_count": 0,
  "pending_file_count": 0,
  "embedding_provider": "openai",
  "embedding_model": "kimi-for-coding",
  "embedding_provider_version": "v1",
  "embedding_dimension": 2
}
""".lstrip(),
    )
    _write_text(
        index_root / "chunks.jsonl",
        (
            '{"chunk_id":"00000000-0000-0000-0000-000000000001",'
            '"text":"医保审核依据","metadata":{"source_collection":"medical-insurance-laws",'
            '"source_path":"全量法律/医保政策.md"},"locator":{"source_path":"全量法律/医保政策.md"},'
            '"source_path":"全量法律/医保政策.md"}\n'
        ),
    )
    _write_text(
        index_root / "embeddings.jsonl",
        (
            '{"chunk_id":"00000000-0000-0000-0000-000000000001",'
            '"text":"医保审核依据","embedding":[1.0,0.0],'
            '"provider":"openai","model_name":"kimi-for-coding",'
            '"provider_version":"v1","dimension":2,"metadata":{}}\n'
        ),
    )
    _write_text(index_root / "failed_files.jsonl", "")
    _write_text(index_root / "pending_files.jsonl", "")

    exit_code = main(
        [
            "pgvector-import",
            "--index-root",
            str(index_root),
            "--source-root",
            str(source_root),
            "--output",
            str(report_path),
            "--json-output",
            str(json_path),
            "--schema-dimension",
            "2",
        ]
    )

    assert exit_code == 0
    assert "知识库 pgvector 受控导入报告" in report_path.read_text(encoding="utf-8")
    assert '"mode": "dry-run"' in json_path.read_text(encoding="utf-8")
    assert '"ready_for_write": true' in json_path.read_text(encoding="utf-8")


def test_ui_smoke_command_writes_success_report(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    json_path = tmp_path / "ui-smoke.json"
    monkeypatch.setattr(
        "medical_audit_kb.cli._create_api_test_client",
        lambda: FakeUiSmokeClient(backend_status_code=200),
    )

    exit_code = main(["ui-smoke", "--json-output", str(json_path)])

    body = json.loads(json_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert body["success"] is True
    assert body["preview_path"] == "/pages/preview/11111111-1111-4111-8111-111111111111"


def test_ui_smoke_command_fails_when_backend_load_fails(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    json_path = tmp_path / "ui-smoke.json"
    monkeypatch.setattr(
        "medical_audit_kb.cli._create_api_test_client",
        lambda: FakeUiSmokeClient(backend_status_code=409),
    )

    exit_code = main(["ui-smoke", "--json-output", str(json_path)])

    body = json.loads(json_path.read_text(encoding="utf-8"))
    assert exit_code == 2
    assert body["success"] is False
    assert body["backend_load_status_code"] == 409
    assert body["query_page_status_code"] is None


class StaticAnswerSmokeProvider:
    provider = "fake"
    model_name = "static-smoke"
    provider_version = "v1"

    def generate_answer(self, question: str, citations: tuple[Citation, ...]) -> str:
        return "医疗机构应当保留医保基金审核依据 [C1]。"


class EmptySearchEngine:
    def search(self, *args: object, **kwargs: object) -> tuple[object, ...]:
        return ()


class FakeResponse:
    def __init__(
        self,
        *,
        status_code: int,
        text: str = "",
        payload: object | None = None,
    ) -> None:
        self.status_code = status_code
        self.text = text
        self._payload = payload

    def json(self) -> object:
        return self._payload


class FakeUiSmokeClient:
    def __init__(self, *, backend_status_code: int) -> None:
        self._backend_status_code = backend_status_code

    def get(
        self,
        path: str,
        *,
        params: dict[str, object] | None = None,
    ) -> FakeResponse:
        if path == "/index/postgres-status":
            return FakeResponse(
                status_code=200,
                payload={
                    "row_counts": {"document_chunks": 1, "chunk_embeddings": 1},
                    "embedding_sets": [],
                },
            )
        if path == "/pages/query":
            return FakeResponse(
                status_code=200,
                text=(
                    '引用型回答 <a href="/pages/preview/'
                    '11111111-1111-4111-8111-111111111111">原文预览</a>'
                ),
            )
        if path == "/pages/preview/11111111-1111-4111-8111-111111111111":
            return FakeResponse(status_code=200, text="原文证据预览")
        return FakeResponse(status_code=404)

    def post(
        self,
        path: str,
        *,
        headers: dict[str, str],
        json: dict[str, object],
    ) -> FakeResponse:
        if path != "/index/search-backend/postgres":
            return FakeResponse(status_code=404)
        if self._backend_status_code != 200:
            return FakeResponse(
                status_code=self._backend_status_code,
                payload={"detail": "missing embedding api key env: KIMI_API_KEY"},
            )
        return FakeResponse(
            status_code=200,
            payload={
                "backend": "postgres",
                "ready": True,
                "details": {"matching_embedding_count": 1},
            },
        )


async def _create_audit_project(database_url: str) -> UUID:
    engine = create_async_engine(database_url)
    try:
        await create_schema(engine)
        session_factory = create_session_factory(engine)
        async with session_factory() as session, session.begin():
            project = await AuditWorkflowRepository(session).create_project(
                AuditProjectCreate(
                    project_key="audit-project-cli-snapshot-apply",
                    name="CLI snapshot apply fixture",
                    scenario_key="charging-compliance",
                    status="fixture",
                    owner_department="审计科",
                    created_by="unit-test",
                )
            )
            return project.id
    finally:
        await engine.dispose()


async def _create_his_staging_contract(database_url: str) -> None:
    engine = create_async_engine(database_url)
    try:
        await create_schema(engine)
        session_factory = create_session_factory(engine)
        async with session_factory() as session, session.begin():
            audit_repository = AuditWorkflowRepository(session)
            his_repository = HisIngestionRepository(session)
            project = await audit_repository.create_project(
                AuditProjectCreate(
                    project_key="audit-project-cli-his-staging",
                    name="CLI HIS staging fixture",
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
                    schema_key="his-schema-cli-charge-detail",
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
    finally:
        await engine.dispose()


async def _audit_data_snapshot_count(database_url: str) -> int:
    engine = create_async_engine(database_url)
    try:
        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            result = await session.execute(select(AuditDataSnapshot))
            return len(result.scalars().all())
    finally:
        await engine.dispose()


async def _his_staging_row_count(database_url: str) -> int:
    engine = create_async_engine(database_url)
    try:
        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            result = await session.execute(select(HisStagingRow))
            return len(result.scalars().all())
    finally:
        await engine.dispose()


async def _seed_audit_log_events(database_url: str) -> tuple[str, str]:
    engine = create_async_engine(database_url)
    try:
        await create_schema(engine)
        session_factory = create_session_factory(engine)
        async with session_factory() as session, session.begin():
            old_event = AuditLogEvent(
                action="query",
                entity_type="operation",
                entity_id="query",
                user_identifier="auditor-old",
                role="auditor",
                status_code=200,
                endpoint="/query",
                reason=None,
                payload={"question": "医保基金审核依据", "api_key": "raw-secret"},
                extra_metadata={"source": "fixture"},
                created_at=datetime(2025, 11, 30, 12, 0, 0, tzinfo=UTC),
            )
            new_event = AuditLogEvent(
                action="audit-logs-export",
                entity_type="operation",
                entity_id="audit-logs-export",
                user_identifier="admin-new",
                role="it-admin",
                status_code=200,
                endpoint="/audit/logs/export",
                reason=None,
                payload={"limit": 100},
                extra_metadata={"source": "fixture"},
                created_at=datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC),
            )
            session.add_all([old_event, new_event])
            await session.flush()
            return str(old_event.id), str(new_event.id)
    finally:
        await engine.dispose()


async def _audit_log_event_count(database_url: str) -> int:
    engine = create_async_engine(database_url)
    try:
        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            result = await session.execute(select(AuditLogEvent))
            return len(result.scalars().all())
    finally:
        await engine.dispose()


async def _audit_log_event_ids(database_url: str) -> list[str]:
    engine = create_async_engine(database_url)
    try:
        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            result = await session.execute(
                select(AuditLogEvent).order_by(AuditLogEvent.created_at.asc())
            )
            return [str(event.id) for event in result.scalars().all()]
    finally:
        await engine.dispose()


def _write_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _write_binary(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path
