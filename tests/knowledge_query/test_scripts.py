import json
import os
import subprocess
import sys
import threading
import types
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import util as importlib_util
from pathlib import Path
from typing import ClassVar

import pytest
from pytest import MonkeyPatch


def test_serve_chat_workbench_script_is_valid_and_does_not_store_secret() -> None:
    script_path = Path("scripts/serve-chat-workbench.sh")

    result = subprocess.run(
        ["bash", "-n", str(script_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    script_text = script_path.read_text(encoding="utf-8")
    assert "KIMI_API_KEY" in script_text
    assert "sk-" not in script_text


def test_capture_chat_workbench_visual_baseline_script_is_valid() -> None:
    script_path = Path("scripts/capture-chat-workbench-visual-baseline.py")

    result = subprocess.run(
        ["python3", "-m", "py_compile", str(script_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    script_text = script_path.read_text(encoding="utf-8")
    assert "sk-" not in script_text
    assert "tmp/screenshots" in script_text
    assert "tmp/outputs/knowledge-query-chat-visual-baseline-latest.json" in script_text
    assert "desktop" in script_text
    assert "mobile" in script_text
    assert "可追溯回答" in script_text
    assert "证据卷宗" in script_text
    assert "人工复核清单" in script_text
    assert "创建复核任务" in script_text
    assert "导出 Markdown 底稿" in script_text
    assert "导出 JSON 记录" in script_text


def test_serve_chat_workbench_container_script_is_valid_and_does_not_store_secret() -> None:
    script_path = Path("scripts/serve-chat-workbench-container.py")

    result = subprocess.run(
        ["python3", "-m", "py_compile", str(script_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    script_text = script_path.read_text(encoding="utf-8")
    assert "KIMI_API_KEY" in script_text
    assert "sk-" not in script_text
    assert "urllib.request" in script_text


def test_run_production_e2e_smoke_script_is_valid_and_does_not_store_secret() -> None:
    script_path = Path("scripts/run-production-e2e-smoke.py")

    result = subprocess.run(
        ["python3", "-m", "py_compile", str(script_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    script_text = script_path.read_text(encoding="utf-8")
    assert "sk-" not in script_text
    assert "tmp/outputs/production-e2e-smoke-latest.json" in script_text
    assert "tls-certificate-san" in script_text
    assert "query-api-with-citations" in script_text
    assert "citation-preview" in script_text
    assert "review-flow-create-update-export" in script_text
    assert "--include-review-write" in script_text
    assert "--require-generated-answer" in script_text
    assert "Default is read-only production smoke" in script_text
    assert "edge-regression" in script_text


def test_run_production_e2e_smoke_selects_latest_review_task_id() -> None:
    module = _load_script_module(
        "run_production_e2e_smoke",
        Path("scripts/run-production-e2e-smoke.py"),
    )
    html = """
    <a href="/review-tasks/review-task-0001/export?format=json">old</a>
    <a href="/review-tasks/review-task-0003/export?format=json">new</a>
    <a href="/review-tasks/review-task-0002/export?format=json">middle</a>
    """

    assert module._first_review_task_id(html) == "review-task-0003"


def test_run_production_e2e_smoke_auth_uses_admin_secret_for_admin_requests() -> None:
    module = _load_script_module(
        "run_production_e2e_smoke",
        Path("scripts/run-production-e2e-smoke.py"),
    )
    auth = module.SmokeAuth(
        api_key="auditor-secret",
        admin_api_key="admin-secret",
        api_key_env="AUDITOR_SECRET",
        admin_api_key_env="ADMIN_SECRET",
    )

    assert auth.headers() == {"X-API-Key": "auditor-secret"}
    assert auth.headers(admin=True) == {
        "X-API-Key": "admin-secret",
        "X-Role": "it-admin",
    }


def test_run_production_e2e_smoke_auth_falls_back_to_admin_secret() -> None:
    module = _load_script_module(
        "run_production_e2e_smoke",
        Path("scripts/run-production-e2e-smoke.py"),
    )
    auth = module.SmokeAuth(
        api_key=None,
        admin_api_key="admin-secret",
        api_key_env=None,
        admin_api_key_env="ADMIN_SECRET",
    )

    assert auth.headers() == {"X-API-Key": "admin-secret"}


def test_run_production_e2e_smoke_can_require_generated_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script_module(
        "run_production_e2e_smoke_generated_answer",
        Path("scripts/run-production-e2e-smoke.py"),
    )
    auth = module.SmokeAuth(
        api_key=None,
        admin_api_key=None,
        api_key_env=None,
        admin_api_key_env=None,
    )

    monkeypatch.setattr(
        module,
        "_request_json",
        lambda *args, **kwargs: {
            "confidence": "high",
            "fallback_used": True,
            "citations": [{"chunk_id": "chunk-1"}],
            "basis_groups": [{"title": "法规依据"}],
        },
    )

    with pytest.raises(module.SmokeError, match="fallback answer"):
        module._check_query_api(
            "https://audit.lute-tlz-dddd.top",
            auth=auth,
            question="医保基金审核依据",
            require_generated_answer=True,
            timeout_seconds=1,
        )


def test_audit_tencent_cloud_deployment_state_script_is_valid_and_secret_safe() -> None:
    script_path = Path("scripts/audit-tencent-cloud-deployment-state.py")

    result = subprocess.run(
        ["python3", "-m", "py_compile", str(script_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    script_text = script_path.read_text(encoding="utf-8")
    assert "sk-" not in script_text
    assert "<remote-audit>" in script_text
    assert "tmp/outputs/tencent-cloud-deployment-state-latest.json" in script_text
    assert "medical-audit.env" not in script_text


def test_audit_tencent_cloud_deployment_state_builds_pass_report(tmp_path: Path) -> None:
    module = _load_script_module(
        "audit_tencent_cloud_deployment_state",
        Path("scripts/audit-tencent-cloud-deployment-state.py"),
    )
    stamp = "20260611T180655+0800"
    smoke_report = tmp_path / "production-e2e-smoke-after-pr48-deploy-20260611.json"
    smoke_report.write_text(
        json.dumps(
            {
                "status": "pass",
                "base_url": "https://audit.lute-tlz-dddd.top",
                "started_at": "2026-06-11T10:10:24Z",
                "finished_at": "2026-06-11T10:10:34Z",
                "steps": [{"name": "health"}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    report = module._build_report(
        remote_report=_deployment_state_fixture(stamp=stamp),
        local_smoke_reports=module._summarize_local_smoke_reports(tmp_path, limit=3),
        expected_deploy_sha="cf6c1479de0b109d5abc9ee92ac8267e549ec2f6",
        required_backup_stamp=stamp,
        min_matching_embeddings=48985,
    )

    assert report["status"] == "pass"
    assert report["issues"] == []
    assert report["summary"]["deploy_sha"] == "cf6c1479de0b109d5abc9ee92ac8267e549ec2f6"
    assert report["summary"]["audit_mount_present"] is True
    assert report["summary"]["matching_embedding_count"] == 48985
    assert report["summary"]["latest_local_smoke_status"] == "pass"


def test_audit_tencent_cloud_deployment_state_accepts_embedding_count_above_minimum() -> None:
    module = _load_script_module(
        "audit_tencent_cloud_deployment_state_embedding_minimum",
        Path("scripts/audit-tencent-cloud-deployment-state.py"),
    )
    stamp = "20260611T180655+0800"
    remote_report = json.loads(json.dumps(_deployment_state_fixture(stamp=stamp)))
    remote_report["local_backend"]["search_backend"]["payload"]["details"][
        "matching_embedding_count"
    ] = 49051

    report = module._build_report(
        remote_report=remote_report,
        local_smoke_reports=[],
        expected_deploy_sha="cf6c1479de0b109d5abc9ee92ac8267e549ec2f6",
        required_backup_stamp=stamp,
        min_matching_embeddings=48985,
    )

    assert report["status"] == "pass"
    assert report["summary"]["matching_embedding_count"] == 49051
    assert report["minimum_matching_embeddings"] == 48985


def test_audit_tencent_cloud_deployment_state_blocks_missing_backup_stamp() -> None:
    module = _load_script_module(
        "audit_tencent_cloud_deployment_state_missing_backup",
        Path("scripts/audit-tencent-cloud-deployment-state.py"),
    )

    report = module._build_report(
        remote_report=_deployment_state_fixture(stamp="other-stamp"),
        local_smoke_reports=[],
        expected_deploy_sha="cf6c1479de0b109d5abc9ee92ac8267e549ec2f6",
        required_backup_stamp="20260611T180655+0800",
        min_matching_embeddings=48985,
    )

    assert report["status"] == "fail"
    assert report["issues"] == ["missing-required-backup-stamp:app,env,db,nginx,web"]


def test_deploy_tencent_cloud_defaults_smoke_report_path() -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_production",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    args = types.SimpleNamespace(
        execute=False,
        confirm_production="",
        ssh_key="ai_video.pem",
        ssh_user=module.DEFAULT_USER,
        ssh_host=module.DEFAULT_HOST,
        remote_app_dir=module.DEFAULT_REMOTE_APP_DIR,
        remote_web_dir=module.DEFAULT_REMOTE_WEB_DIR,
        base_url=module.DEFAULT_BASE_URL,
        stamp="20260611T184000+0800",
        allow_dirty=False,
        skip_web_build=False,
        skip_app_rebuild=False,
        apply_schema=False,
        skip_smoke=False,
        include_review_write=False,
        report="",
    )

    config = module._config_from_args(args)

    assert config.report_path == Path(
        "tmp/outputs/production-e2e-smoke-after-deploy-20260611T184000+0800.json",
    ).resolve()


def test_deploy_tencent_cloud_ssh_script_calls_detach_stdin() -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_production_ssh_args",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    config = types.SimpleNamespace(
        ssh_key=Path("ai_video.pem"),
        ssh_target="ubuntu@101.34.52.232",
    )

    ssh_args = module._ssh_args(config, "echo ok")
    ssh_transport = module._ssh_transport(config)

    assert ssh_args[:2] == ["ssh", "-n"]
    assert "-n" not in ssh_transport.split()


def test_deploy_tencent_cloud_cleans_only_remote_source_sync_artifacts(
    monkeypatch: MonkeyPatch,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_production_cleanup",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    assert ".git" in module.APP_RSYNC_EXCLUDES
    assert ".git/" in module.APP_RSYNC_EXCLUDES
    captured_scripts: list[str] = []

    def fake_ssh(config: object, script: str) -> None:
        captured_scripts.append(script)

    monkeypatch.setattr(module, "_ssh", fake_ssh)
    config = types.SimpleNamespace(remote_app_dir="/opt/medical-audit/app")

    module._cleanup_remote_sync_artifacts(config)

    assert len(captured_scripts) == 1
    script = captured_scripts[0]
    assert "git_file=/opt/medical-audit/app/.git" in script
    assert 'if [ -f "$git_file" ]; then' in script
    assert 'rm -f "$git_file"' in script
    assert "src_dir=/opt/medical-audit/app/src" in script
    assert "test -d \"$src_dir\"" in script
    assert "-name '*.pyc'" in script
    assert "-name '*.pyo'" in script
    assert "-name '*.uploading.cfg'" in script
    assert "-name __pycache__ -empty" in script
    assert "--delete-excluded" not in script
    assert "/data" not in script
    assert "medical-audit.env" not in script
    assert "rm -rf" not in script


def test_deploy_tencent_cloud_runs_cleanup_after_backups_before_rsync() -> None:
    script_text = Path("scripts/deploy-tencent-cloud-production.py").read_text(
        encoding="utf-8",
    )

    backup_call = script_text.index("_create_remote_backups(config)")
    cleanup_call = script_text.index("_cleanup_remote_sync_artifacts(config)")
    sync_call = script_text.index("_sync_application(config)")

    assert backup_call < cleanup_call < sync_call
    assert "--delete-excluded" not in script_text
    assert "docker exec medical_audit_pg sh -lc 'pg_dump" in script_text
    assert "docker exec -i medical_audit_pg sh -lc 'pg_dump" not in script_text
    assert "docker exec -t medical_audit_pg sh -lc 'pg_dump" not in script_text


def test_run_audit_log_archive_audit_script_is_valid_and_does_not_store_secret() -> None:
    script_path = Path("scripts/run-audit-log-archive-audit.py")

    result = subprocess.run(
        ["python3", "-m", "py_compile", str(script_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    script_text = script_path.read_text(encoding="utf-8")
    assert "sk-" not in script_text
    assert "audit-log-archive-audit" in script_text
    assert "MEDICAL_AUDIT_AUDIT_LOG_SIGNING_SECRET" in script_text
    assert "MEDICAL_AUDIT_AUDIT_LOG_ARCHIVE_ROOT" in script_text
    assert "MEDICAL_AUDIT_AUDIT_LOG_ARCHIVE_REPORT_DIR" in script_text
    assert "MEDICAL_AUDIT_AUDIT_LOG_ALERT_WEBHOOK_URL" in script_text
    assert "MEDICAL_AUDIT_AUDIT_LOG_ALERT_TIMEOUT_SECONDS" in script_text
    assert "latest_json_report" in script_text


def test_run_audit_log_archive_audit_script_sends_failure_webhook(
    tmp_path: Path,
) -> None:
    script_path = Path("scripts/run-audit-log-archive-audit.py")
    archive_root = tmp_path / "archive"
    report_dir = tmp_path / "reports"
    archive_root.mkdir()
    _WebhookCaptureHandler.payloads = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _WebhookCaptureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    webhook_url = f"http://127.0.0.1:{server.server_port}/archive-alert"
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"
    env["MEDICAL_AUDIT_AUDIT_LOG_SIGNING_SECRET"] = "test-signing-secret"
    env["MEDICAL_AUDIT_AUDIT_LOG_ALERT_WEBHOOK_URL"] = webhook_url

    try:
        result = subprocess.run(
            [
                sys.executable,
                str(script_path),
                "--archive-root",
                str(archive_root),
                "--report-dir",
                str(report_dir),
                "--min-manifest-count",
                "1",
                "--run-id",
                "webhook-failure",
            ],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    latest_payload = json.loads(
        (report_dir / "audit-log-archive-audit-latest.json").read_text(encoding="utf-8")
    )
    stdout_payload = json.loads(result.stdout)
    assert result.returncode == 2
    assert webhook_url not in result.stdout
    assert webhook_url not in result.stderr
    assert latest_payload["status"] == "fail"
    assert latest_payload["manifest_count"] == 0
    assert latest_payload["issues"] == ["manifest count below minimum"]
    stdout_alert = stdout_payload["alert"]
    assert isinstance(stdout_alert, dict)
    assert stdout_alert["sent"] is True
    assert _WebhookCaptureHandler.payloads
    alert_payload = _WebhookCaptureHandler.payloads[0]
    summary = alert_payload["summary"]
    assert isinstance(summary, dict)
    assert alert_payload["event_type"] == "medical_audit.audit_log_archive_audit"
    assert alert_payload["severity"] == "critical"
    assert alert_payload["status"] == "fail"
    assert alert_payload["exit_code"] == 2
    assert summary["manifest_count"] == 0
    assert summary["failed_count"] == 0
    assert summary["issues"] == ["manifest count below minimum"]


def test_run_audit_log_archive_audit_script_fails_success_alert_validation_without_webhook(
    tmp_path: Path,
) -> None:
    script_path = Path("scripts/run-audit-log-archive-audit.py")
    archive_root = tmp_path / "archive"
    report_dir = tmp_path / "reports"
    archive_root.mkdir()
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"
    env["MEDICAL_AUDIT_AUDIT_LOG_SIGNING_SECRET"] = "test-signing-secret"
    env.pop("MEDICAL_AUDIT_AUDIT_LOG_ALERT_WEBHOOK_URL", None)

    result = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--archive-root",
            str(archive_root),
            "--report-dir",
            str(report_dir),
            "--min-manifest-count",
            "0",
            "--run-id",
            "success-alert-not-configured",
            "--send-success-alert",
            "--fail-on-alert-error",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    stdout_payload = json.loads(result.stdout)
    assert result.returncode == 2
    assert stdout_payload["audit_exit_code"] == 0
    assert stdout_payload["alert"]["status"] == "not-configured"
    assert stdout_payload["alert"]["reason"] == "webhook-not-configured"


def test_classify_knowledge_pending_files_script_writes_reports(tmp_path: Path) -> None:
    script_path = Path("scripts/classify-knowledge-pending-files.py")
    source_root = tmp_path / "source"
    pending_file = tmp_path / "pending_files.jsonl"
    output = tmp_path / "pending-report.md"
    json_output = tmp_path / "pending-report.json"
    _write_bytes(source_root / "风险负面清单" / "scan.png", b"png")
    _write_bytes(source_root / "全量法律.zip", b"zip")
    pending_file.write_text(
        "\n".join(
            (
                json.dumps(
                    {
                        "relative_path": "风险负面清单/scan.png",
                        "error_type": "unsupported-type",
                        "error_summary": "unsupported-file-type",
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "relative_path": "全量法律.zip",
                        "error_type": "unsupported-type",
                        "error_summary": "unsupported-file-type",
                    },
                    ensure_ascii=False,
                ),
            )
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            "python3",
            str(script_path),
            "--pending-file",
            str(pending_file),
            "--source-root",
            str(source_root),
            "--output",
            str(output),
            "--json-output",
            str(json_output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    body = json.loads(json_output.read_text(encoding="utf-8"))
    report_text = output.read_text(encoding="utf-8")
    assert result.returncode == 0, result.stderr
    assert body["summary"]["total_pending_files"] == 2
    assert body["summary"]["source_missing_count"] == 0
    assert body["counts"]["by_category"] == {
        "archive-unpack-required": 1,
        "ocr-required-image": 1,
    }
    assert body["counts"]["by_source_collection"] == {
        "root": 1,
        "风险负面清单": 1,
    }
    assert "知识库 pending 文件分类报告" in report_text
    assert "scan.png" in report_text
    assert "全量法律.zip" in report_text


def test_audit_index_rollback_readiness_allows_inactive_target(tmp_path: Path) -> None:
    script_path = Path("scripts/audit-index-rollback-readiness.py")
    versions_file = tmp_path / "versions.json"
    output = tmp_path / "rollback-readiness.md"
    json_output = tmp_path / "rollback-readiness.json"
    versions_file.write_text(
        json.dumps(
            [
                {
                    "version_key": "full-rebuild-current",
                    "status": "active",
                    "vector_provider": "openai",
                    "vector_model": "kimi-for-coding",
                    "document_count": 486,
                    "chunk_count": 48985,
                },
                {
                    "version_key": "full-rebuild-previous",
                    "status": "inactive",
                    "vector_provider": "openai",
                    "vector_model": "kimi-for-coding",
                    "document_count": 480,
                    "chunk_count": 48000,
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            "python3",
            str(script_path),
            "--versions-file",
            str(versions_file),
            "--output",
            str(output),
            "--json-output",
            str(json_output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    body = json.loads(json_output.read_text(encoding="utf-8"))
    assert result.returncode == 0, result.stderr
    assert body["status"] == "pass"
    assert body["safe_to_execute_rollback_rehearsal"] is True
    assert body["summary"]["rollback_target_count"] == 1
    assert "知识库索引回滚就绪审计报告" in output.read_text(encoding="utf-8")


def test_audit_index_rollback_readiness_blocks_without_inactive_target(
    tmp_path: Path,
) -> None:
    script_path = Path("scripts/audit-index-rollback-readiness.py")
    versions_file = tmp_path / "versions.json"
    output = tmp_path / "rollback-readiness.md"
    json_output = tmp_path / "rollback-readiness.json"
    versions_file.write_text(
        json.dumps(
            [
                {
                    "version_key": "full-rebuild-current",
                    "status": "active",
                    "vector_provider": "openai",
                    "vector_model": "kimi-for-coding",
                    "document_count": 486,
                    "chunk_count": 48985,
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            "python3",
            str(script_path),
            "--versions-file",
            str(versions_file),
            "--expected-active-key",
            "full-rebuild-current",
            "--output",
            str(output),
            "--json-output",
            str(json_output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    body = json.loads(json_output.read_text(encoding="utf-8"))
    assert result.returncode == 2
    assert body["status"] == "blocked"
    assert body["safe_to_execute_rollback_rehearsal"] is False
    assert body["blocking_reasons"] == ["no-inactive-rollback-target-for-active-provider-model"]
    assert body["summary"]["rollback_target_count"] == 0


def test_audit_index_candidate_release_readiness_allows_new_candidate_key(
    tmp_path: Path,
) -> None:
    script_path = Path("scripts/audit-index-candidate-release-readiness.py")
    import_result_file = tmp_path / "pgvector-import-dry-run.json"
    versions_file = tmp_path / "versions.json"
    output = tmp_path / "candidate-release-readiness.md"
    json_output = tmp_path / "candidate-release-readiness.json"
    import_result_file.write_text(
        json.dumps(_candidate_import_result("full-rebuild-next"), ensure_ascii=False),
        encoding="utf-8",
    )
    versions_file.write_text(
        json.dumps(
            [
                {
                    "version_key": "full-rebuild-current",
                    "status": "active",
                    "vector_provider": "openai",
                    "vector_model": "kimi-for-coding",
                    "document_count": 486,
                    "chunk_count": 48985,
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            "python3",
            str(script_path),
            "--import-result-json",
            str(import_result_file),
            "--versions-file",
            str(versions_file),
            "--expected-active-key",
            "full-rebuild-current",
            "--output",
            str(output),
            "--json-output",
            str(json_output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    body = json.loads(json_output.read_text(encoding="utf-8"))
    assert result.returncode == 0, result.stderr
    assert body["status"] == "pass"
    assert body["safe_to_execute_candidate_write"] is True
    assert body["candidate"]["candidate_index_version_key"] == "full-rebuild-next"
    assert body["evidence_grade"] == "L2-fixture-or-dry-run"
    assert "知识库 candidate 发布就绪审计报告" in output.read_text(encoding="utf-8")


def test_audit_index_candidate_release_readiness_blocks_existing_candidate_key(
    tmp_path: Path,
) -> None:
    script_path = Path("scripts/audit-index-candidate-release-readiness.py")
    import_result_file = tmp_path / "pgvector-import-dry-run.json"
    versions_file = tmp_path / "versions.json"
    output = tmp_path / "candidate-release-readiness.md"
    json_output = tmp_path / "candidate-release-readiness.json"
    import_result_file.write_text(
        json.dumps(_candidate_import_result("full-rebuild-current"), ensure_ascii=False),
        encoding="utf-8",
    )
    versions_file.write_text(
        json.dumps(
            [
                {
                    "version_key": "full-rebuild-current",
                    "status": "active",
                    "vector_provider": "openai",
                    "vector_model": "kimi-for-coding",
                    "document_count": 486,
                    "chunk_count": 48985,
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            "python3",
            str(script_path),
            "--import-result-json",
            str(import_result_file),
            "--versions-file",
            str(versions_file),
            "--output",
            str(output),
            "--json-output",
            str(json_output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    body = json.loads(json_output.read_text(encoding="utf-8"))
    assert result.returncode == 2
    assert body["status"] == "blocked"
    assert body["safe_to_execute_candidate_write"] is False
    assert "candidate-index-version-key-already-exists" in body["blocking_reasons"]
    assert "candidate-index-version-key-matches-active" in body["blocking_reasons"]


def test_audit_index_candidate_release_readiness_blocks_chunk_id_collision(
    tmp_path: Path,
) -> None:
    script_path = Path("scripts/audit-index-candidate-release-readiness.py")
    import_result_file = tmp_path / "pgvector-import-dry-run.json"
    versions_file = tmp_path / "versions.json"
    candidate_chunks_file = tmp_path / "candidate-chunks.jsonl"
    active_chunks_file = tmp_path / "active-chunks.jsonl"
    output = tmp_path / "candidate-release-readiness.md"
    json_output = tmp_path / "candidate-release-readiness.json"
    import_result_file.write_text(
        json.dumps(_candidate_import_result("full-rebuild-next"), ensure_ascii=False),
        encoding="utf-8",
    )
    versions_file.write_text(
        json.dumps(
            [
                {
                    "version_key": "full-rebuild-current",
                    "status": "active",
                    "source_package_version_key": "source-package-current",
                    "vector_provider": "openai",
                    "vector_model": "kimi-for-coding",
                    "document_count": 486,
                    "chunk_count": 48985,
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    _write_jsonl(candidate_chunks_file, [{"chunk_id": "chunk-shared"}])
    _write_jsonl(active_chunks_file, [{"chunk_id": "chunk-shared"}])

    result = subprocess.run(
        [
            "python3",
            str(script_path),
            "--import-result-json",
            str(import_result_file),
            "--versions-file",
            str(versions_file),
            "--candidate-chunks-file",
            str(candidate_chunks_file),
            "--active-chunks-file",
            str(active_chunks_file),
            "--output",
            str(output),
            "--json-output",
            str(json_output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    body = json.loads(json_output.read_text(encoding="utf-8"))
    assert result.returncode == 2
    assert body["status"] == "blocked"
    assert "candidate-chunk-id-collides-with-active-package" in body["blocking_reasons"]
    assert body["chunk_collision_check"]["collision_count"] == 1
    assert body["chunk_collision_check"]["collision_samples"] == ["chunk-shared"]


def _candidate_import_result(index_version_key: str) -> dict[str, object]:
    return {
        "mode": "dry-run",
        "executed": False,
        "success": True,
        "index_version_status": "candidate",
        "manifest": {
            "ready_for_write": True,
            "source_document_count": 486,
            "document_chunk_count": 48985,
            "chunk_embedding_count": 48985,
            "failed_file_count": 0,
            "pending_file_count": 13,
            "source_file_missing_count": 0,
            "invalid_source_metadata_count": 0,
            "plan": {
                "expected_embedding_provider": "openai",
                "expected_embedding_model": "kimi-for-coding",
                "summary": {
                    "index_version_key": index_version_key,
                    "source_package_version_key": "source-package-next",
                    "embedding_provider": "openai",
                    "embedding_model": "kimi-for-coding",
                },
            },
        },
    }


def _deployment_state_fixture(stamp: str) -> dict[str, object]:
    return {
        "deploy_sha": "cf6c1479de0b109d5abc9ee92ac8267e549ec2f6",
        "containers": {
            "medical_audit_app": {
                "status": "running",
                "running": True,
                "health": "healthy",
                "compose_project": "medical-audit",
                "compose_service": "app",
            },
            "medical_audit_pg": {
                "status": "running",
                "running": True,
                "health": "healthy",
                "compose_project": "medical-audit",
                "compose_service": "postgres",
            },
            "ai_video_nginx": {
                "status": "running",
                "running": True,
                "compose_project": "lighthouse",
                "compose_service": "nginx",
            },
        },
        "nginx": {
            "config_test": {"passed": True},
            "mounts": {
                "audit_mount": {
                    "source": "/var/www/audit",
                    "destination": "/var/www/audit",
                    "mode": "ro",
                    "rw": False,
                }
            },
        },
        "local_backend": {
            "search_backend": {
                "ok": True,
                "payload": {
                    "backend": "postgres",
                    "ready": True,
                    "details": {"matching_embedding_count": 48985},
                },
            }
        },
        "backups": {
            "app": [{"path": f"/opt/medical-audit/backups/app/pre-deploy-{stamp}.tar.gz"}],
            "env": [
                {"path": f"/opt/medical-audit/backups/env/medical-audit.env.pre-deploy-{stamp}"}
            ],
            "db": [{"path": f"/opt/medical-audit/backups/db/pre-deploy-{stamp}.sql.gz"}],
            "nginx": [{"path": f"/opt/medical-audit/backups/nginx/nginx.conf.pre-deploy-{stamp}"}],
            "web": [
                {"path": f"/opt/medical-audit/backups/web/audit-web-pre-deploy-{stamp}.tar.gz"}
            ],
        },
    }


def _write_bytes(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _load_script_module(name: str, path: Path) -> types.ModuleType:
    spec = importlib_util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib_util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class _WebhookCaptureHandler(BaseHTTPRequestHandler):
    payloads: ClassVar[list[dict[str, object]]] = []

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        payload = json.loads(body.decode("utf-8"))
        if isinstance(payload, dict):
            self.payloads.append(payload)
        self.send_response(204)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return None


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    return path
