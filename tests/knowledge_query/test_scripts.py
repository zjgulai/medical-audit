import binascii
import hashlib
import json
import os
import shutil
import stat
import struct
import subprocess
import sys
import threading
import types
import zlib
from contextlib import nullcontext
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import util as importlib_util
from pathlib import Path
from typing import ClassVar

import pytest
from pytest import MonkeyPatch


def _rgba_png_bytes(width: int, height: int) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        checksum = binascii.crc32(kind + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    scanline = b"\x00" + (b"\x00" * width * 4)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(scanline * height))
        + chunk(b"IEND", b"")
    )


def _frontend_live_release_guard(
    expected_sha: str,
    run_id: str = "fa-20260716t153000z-deadbeef",
) -> dict[str, object]:
    report: dict[str, object] = {
        "format": "medical-audit-production-release-guard-v1",
        "mode": "capture",
        "phase": "S1",
        "status": "pass",
        "evidence_grade": "L3-production-read-only",
        "source": "ssh-live-readonly",
        "generated_at": "2026-07-16T08:30:00Z",
        "observation_target": {
            "format": "medical-audit-release-guard-observation-target-v1",
            "kind": "production-ssh",
            "ssh_host": "101.34.52.232",
            "remote_app_dir": "/opt/medical-audit/app",
            "remote_web_dir": "/var/www/audit",
            "postgres_container": "medical_audit_pg",
        },
        "expected_deploy_sha": expected_sha,
        "observed_deploy_sha": expected_sha,
        "provider_call_status": "not_observed",
        "provider_evidence_source": "outside-release-guard-scope",
        "collector_provider_call_status": "not_called",
        "collector_provider_attempt_count": 0,
        "collector_execution_boundary": {
            "format": "medical-audit-release-guard-execution-boundary-v1",
            "collector_protocol": "ssh-stdin-release-topology-postgresql-readonly-v2",
            "allowed_operations": [
                "filesystem-read",
                "docker-exec-psql-readonly",
                "docker-inspect-readonly",
                "docker-exec-app-deploy-sha-readonly",
                "docker-exec-nginx-config-test",
            ],
            "executed_postgresql_readonly_commands": 2,
            "executed_runtime_readonly_commands": 8,
            "rejected_command_count": 0,
            "collector_provider_endpoint_attempt_count": 0,
            "provider_environment_read": False,
            "secret_values_reported": False,
        },
        "database_write": False,
        "transaction_read_only": True,
        "transaction_read_only_observed": "on",
        "transaction_isolation_observed": "serializable",
        "transaction_deferrable_observed": "on",
        "release_topology": "versioned_ready",
        "release_topology_evidence": {
            "releases_root": {"kind": "directory"},
            "current": {"kind": "symlink", "target": f"releases/{expected_sha}"},
            "current_next": {"kind": "absent"},
            "migration_sentinel": {"kind": "regular_file", "sha": expected_sha},
            "migration_sentinel_next": {"kind": "absent"},
            "incoming_entries": [],
            "legacy_index": {"kind": "regular_file", "sha256": "9" * 64},
            "deploy_marker": {"kind": "regular_file", "sha": expected_sha},
            "deploy_marker_next": {"kind": "absent"},
            "release": {
                "kind": "directory",
                "sha": expected_sha,
                "manifest_format": "medical-audit-web-release-manifest-v1",
                "manifest_source_sha": expected_sha,
                "manifest_sha256": "a" * 64,
            },
            "runtime": {
                "app_container": {
                    "status": "running",
                    "health": "healthy",
                    "deploy_sha": expected_sha,
                },
                "nginx": {
                    "config_test": True,
                    "web_mount_source": "/var/www/audit",
                    "web_mount_read_only": True,
                    "expected_web_root": "/var/www/audit",
                },
            },
        },
        "current_release_target": f"releases/{expected_sha}",
        "manifest_source_sha": expected_sha,
        "manifest_sha256": "a" * 64,
        "schema_fingerprint": "b" * 64,
        "schema_tables": [],
        "schema_fingerprint_scope": [],
        "tables": {},
        "object_storage": {
            "status": "observed",
            "fingerprint": "c" * 64,
            "object_count": 8,
            "max_timestamp": "2026-07-16T07:00:00+00:00",
            "observation_scope": "database-ledger",
        },
        "capture_consistency": {
            "database_snapshot_before": "d" * 64,
            "database_snapshot_after": "d" * 64,
            "concurrent_activity_detected": False,
        },
        "audit_attribution": {
            "acceptance_run_id": run_id,
            "audit_user_identifier": f"frontend-acceptance-{run_id}",
            "attributable_event_count": 0,
            "event_id_fingerprint": hashlib.sha256(b"").hexdigest(),
            "event_ids": [],
        },
        "blocking_reasons": [],
        "guard_execution_write": False,
        "capture_side_effect": "none",
    }
    snapshot_core_fields = (
        "phase",
        "generated_at",
        "observation_target",
        "expected_deploy_sha",
        "observed_deploy_sha",
        "transaction_read_only",
        "transaction_read_only_observed",
        "transaction_isolation_observed",
        "transaction_deferrable_observed",
        "release_topology",
        "release_topology_evidence",
        "current_release_target",
        "manifest_source_sha",
        "manifest_sha256",
        "schema_fingerprint",
        "schema_tables",
        "schema_fingerprint_scope",
        "tables",
        "object_storage",
        "provider_call_status",
        "provider_evidence_source",
        "collector_provider_call_status",
        "collector_provider_attempt_count",
        "collector_execution_boundary",
        "capture_consistency",
        "audit_attribution",
    )
    core = {field: report[field] for field in snapshot_core_fields}
    report["snapshot_id"] = hashlib.sha256(
        json.dumps(
            core,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    provenance = {
        "format": "medical-audit-release-guard-capture-provenance-v1",
        "transport": "ssh-stdin",
        "ssh_host": "101.34.52.232",
        "ssh_user": "ubuntu",
        "batch_mode": True,
        "strict_host_key_checking": True,
        "identities_only": True,
        "ssh_exit_code": 0,
        "remote_app_dir": "/opt/medical-audit/app",
        "remote_web_dir": "/var/www/audit",
        "postgres_container": "medical_audit_pg",
        "collector_source_sha256": hashlib.sha256(
            Path("scripts/audit-production-release-guard-snapshot.py").read_bytes()
        ).hexdigest(),
    }
    report["capture_provenance"] = provenance
    report["capture_envelope_id"] = hashlib.sha256(
        json.dumps(
            {
                "snapshot_id": report["snapshot_id"],
                "capture_provenance": provenance,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return report


def _documents_governance_status_payload() -> dict[str, object]:
    fields: dict[str, object] = {
        "document_storage_provider": "tencent-cos",
        "cos_bucket_status": "set",
        "cos_region_status": "set",
        "cos_prefix_status": "set",
        "cos_secret_id_env_name_status": "set",
        "cos_secret_key_env_name_status": "set",
        "cos_sdk_bootstrap_status": "enabled",
        "record_storage_objects": True,
        "signed_url_ttl_seconds": 180,
        "object_retention_days": 365,
        "local_quarantine_retention_days": 14,
        "virus_scan_provider": "clamav-sidecar",
        "virus_scan_job_endpoint_env_status": "not_required",
        "virus_scan_job_secret_env_status": "not_required",
        "dlp_review_provider": "ruleset-v1",
        "dlp_review_job_endpoint_env_status": "not_required",
        "dlp_review_job_secret_env_status": "not_required",
        "redaction_rewrite_enabled": True,
        "redaction_policy_version_status": "set",
        "redaction_manual_review_required": True,
        "governance_audit_event_required": True,
        "document_storage_objects_schema_ready": True,
        "document_upload_list_readonly_status": "blocked_by_audit_log_side_effect",
        "governance_readonly_endpoint_status": "available",
        "download_metadata_readonly_status": "blocked_by_audit_log_side_effect",
        "audit_log_readonly_status": "available_no_event_written",
    }
    return {
        "status": "readonly_status_available",
        "evidence_grade": "L1-public-or-runtime",
        "required_report_fields": fields,
        "boundaries": {
            "production_write": False,
            "document_upload_write": False,
            "document_upload_list_api_called": False,
            "download_metadata_api_called": False,
            "audit_log_write_expected": False,
            "provider_call": False,
            "object_storage_write": False,
            "secret_values_reported": False,
            "allowed_http_methods": ["GET"],
            "non_get_http_methods_allowed": False,
        },
    }


def _deployment_metadata_payload() -> dict[str, object]:
    deploy_sha = "5e603f85aa11bb22cc33dd44ee55ff6677889900"
    return {
        "status": "deployment_metadata_available",
        "evidence_grade": "L1-public-or-runtime",
        "version": "0.1.0",
        "deploy_sha_status": "set",
        "deploy_sha": deploy_sha,
        "deploy_sha_source": "default_file",
        "required_report_fields": {
            "expected_deploy_sha": deploy_sha,
            "current_deploy_sha": deploy_sha,
            "deploy_sha_status": "set",
        },
        "boundaries": {
            "production_write": False,
            "production_env_write": False,
            "provider_call": False,
            "object_storage_write": False,
            "secret_values_reported": False,
            "allowed_http_methods": ["GET"],
            "non_get_http_methods_allowed": False,
        },
    }


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
    assert "X-Tenant-Id" in script_text
    assert "X-Project-Key" in script_text


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
    assert "X-Tenant-Id" in script_text
    assert "X-Project-Key" in script_text


def test_serve_local_acceptance_api_script_is_valid_and_does_not_store_secret() -> None:
    script_path = Path("scripts/serve-local-acceptance-api.py")

    result = subprocess.run(
        ["python3", "-m", "py_compile", str(script_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    script_text = script_path.read_text(encoding="utf-8")
    assert "create_local_acceptance_app" in script_text
    assert "--state-root" in script_text
    assert "8021" in script_text
    assert "sk-" not in script_text


def test_serve_chat_workbench_container_internal_auth_headers(
    monkeypatch: MonkeyPatch,
) -> None:
    module = _load_script_module(
        "serve_chat_workbench_container_internal_auth_headers",
        Path("scripts/serve-chat-workbench-container.py"),
    )

    monkeypatch.setenv("MEDICAL_AUDIT_INTERNAL_USER_ID", "bootstrap-user")
    monkeypatch.setenv("MEDICAL_AUDIT_INTERNAL_ROLE", "it-admin")
    monkeypatch.setenv("MEDICAL_AUDIT_INTERNAL_PROJECT_KEY", "project-a")
    monkeypatch.setenv("MEDICAL_AUDIT_INTERNAL_TENANT_ID", "tenant-a")

    assert module._internal_auth_headers() == {
        "X-User-Id": "bootstrap-user",
        "X-Role": "it-admin",
        "X-Project-Key": "project-a",
        "X-Tenant-Id": "tenant-a",
    }


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
    assert "L3-production-read-only" in script_text
    assert "--include-query-provider-smoke" in script_text
    assert "--confirm-production-write" in script_text
    assert "edge-regression" in script_text
    assert "--include-shared-edge-regression" in script_text
    assert "shared-edge-regression-is-opt-in" in script_text


def test_run_production_e2e_smoke_excludes_shared_edge_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script_module(
        "run_production_e2e_smoke_no_shared_edge",
        Path("scripts/run-production-e2e-smoke.py"),
    )
    monkeypatch.setattr(sys, "argv", ["run-production-e2e-smoke.py"])

    args = module._parse_args()

    assert module._selected_regression_urls(args) == ()


def test_run_production_e2e_smoke_shared_edge_is_explicit_opt_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script_module(
        "run_production_e2e_smoke_shared_edge",
        Path("scripts/run-production-e2e-smoke.py"),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run-production-e2e-smoke.py",
            "--include-shared-edge-regression",
            "--regression-url",
            "https://status.example.test/",
        ],
    )

    args = module._parse_args()

    assert module._selected_regression_urls(args) == (
        *module.SHARED_EDGE_REGRESSION_URLS,
        "https://status.example.test/",
    )


def test_run_production_e2e_smoke_defaults_to_get_only(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_script_module(
        "run_production_e2e_smoke_get_only",
        Path("scripts/run-production-e2e-smoke.py"),
    )
    report_path = tmp_path / "readonly-smoke.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run-production-e2e-smoke.py",
            "--report",
            str(report_path),
        ],
    )
    monkeypatch.setattr(module, "_check_certificate_san", lambda **_kwargs: {"ok": True})
    monkeypatch.setattr(module, "_check_health", lambda *_args, **_kwargs: {"ok": True})
    monkeypatch.setattr(
        module,
        "_check_search_backend",
        lambda *_args, **_kwargs: {"ok": True},
    )
    monkeypatch.setattr(module, "_check_pages", lambda *_args, **_kwargs: {"ok": True})
    monkeypatch.setattr(
        module,
        "_check_query_api",
        lambda *_args, **_kwargs: pytest.fail("default smoke must not call POST /query"),
    )
    monkeypatch.setattr(
        module,
        "_check_chat_export",
        lambda *_args, **_kwargs: pytest.fail("default smoke must not run chat export"),
    )

    assert module.main() == 0

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["evidence_grade"] == "L3-production-read-only"
    assert report["production_side_effect"] == "none"
    assert report["database_write"] is False
    assert report["provider_call"] == "not_called"
    assert report["http_methods"] == ["GET"]
    not_run_steps = {
        item["name"]: item["details"]["reason"]
        for item in report["steps"]
        if item.get("details", {}).get("status") == "not_run"
    }
    assert not_run_steps["query-api-with-citations"] == (
        "requires-explicit-production-write-authorization"
    )
    assert not_run_steps["chat-dossier-export"] == (
        "requires-explicit-production-write-authorization"
    )


def test_run_production_e2e_smoke_requires_confirmation_for_live_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script_module(
        "run_production_e2e_smoke_live_confirmation",
        Path("scripts/run-production-e2e-smoke.py"),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["run-production-e2e-smoke.py", "--include-query-provider-smoke"],
    )

    args = module._parse_args()

    with pytest.raises(module.SmokeError, match="confirm-production-write"):
        module._validate_side_effect_authorization(args)


def test_run_production_e2e_smoke_allows_confirmed_live_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script_module(
        "run_production_e2e_smoke_live_confirmed",
        Path("scripts/run-production-e2e-smoke.py"),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run-production-e2e-smoke.py",
            "--include-query-provider-smoke",
            "--confirm-production-write",
            "audit.lute-tlz-dddd.top",
        ],
    )

    args = module._parse_args()

    module._validate_side_effect_authorization(args)


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_run_production_e2e_smoke_rejects_cross_origin_redirects_without_forwarding_auth(
    method: str,
) -> None:
    module = _load_script_module(
        f"run_production_e2e_smoke_cross_origin_redirect_{method.lower()}",
        Path("scripts/run-production-e2e-smoke.py"),
    )
    target_hits: list[dict[str, str]] = []

    class TargetHandler(BaseHTTPRequestHandler):
        def _capture(self) -> None:
            target_hits.append({key.lower(): value for key, value in self.headers.items()})
            self.send_response(200)
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802
            self._capture()

        def do_POST(self) -> None:  # noqa: N802
            self._capture()

        def log_message(self, format: str, *args: object) -> None:
            del format, args

    target_server = ThreadingHTTPServer(("127.0.0.1", 0), TargetHandler)
    target_thread = threading.Thread(target=target_server.serve_forever, daemon=True)
    target_thread.start()

    class RedirectHandler(BaseHTTPRequestHandler):
        def _redirect(self) -> None:
            self.send_response(307)
            self.send_header(
                "Location",
                f"http://127.0.0.1:{target_server.server_port}/target",
            )
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802
            self._redirect()

        def do_POST(self) -> None:  # noqa: N802
            self._redirect()

        def log_message(self, format: str, *args: object) -> None:
            del format, args

    redirect_server = ThreadingHTTPServer(("127.0.0.1", 0), RedirectHandler)
    redirect_thread = threading.Thread(
        target=redirect_server.serve_forever,
        daemon=True,
    )
    redirect_thread.start()
    sensitive_headers = {
        "X-API-Key": "secret-api-key",
        "X-Role": "admin",
        "X-User-Id": "deploy-user",
        "X-Project-Key": "project-a",
        "X-Tenant-Id": "tenant-a",
    }

    try:
        with pytest.raises(module.SmokeError, match="cross-origin redirect"):
            module._request(
                f"http://127.0.0.1:{redirect_server.server_port}/redirect",
                method=method,
                body=b"payload" if method == "POST" else None,
                headers=sensitive_headers,
                timeout_seconds=1,
            )
    finally:
        redirect_server.shutdown()
        target_server.shutdown()
        redirect_thread.join(timeout=2)
        target_thread.join(timeout=2)
        redirect_server.server_close()
        target_server.server_close()

    assert target_hits == []


def test_run_production_e2e_smoke_reads_search_status_from_no_write_catalog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script_module(
        "run_production_e2e_smoke_readonly_search_catalog",
        Path("scripts/run-production-e2e-smoke.py"),
    )
    requested_urls: list[str] = []

    def fake_get_json(url: str, **_kwargs: object) -> dict[str, object]:
        requested_urls.append(url)
        return {
            "summary": {"current_search_embedding_count": 49051},
            "search_backend": {
                "backend": "postgres",
                "ready": True,
                "details": {"embedding_model": "text-embedding-v4"},
            },
            "boundaries": {
                "database_write": False,
                "provider_call": False,
                "query_history_write": False,
            },
        }

    monkeypatch.setattr(module, "_get_json", fake_get_json)
    auth = module.SmokeAuth(
        api_key=None,
        admin_api_key=None,
        api_key_env=None,
        admin_api_key_env=None,
    )

    details = module._check_search_backend(
        "https://audit.lute-tlz-dddd.top",
        auth=auth,
        expected_matching_embeddings=48985,
        timeout_seconds=1,
    )

    assert requested_urls == [
        "https://audit.lute-tlz-dddd.top/api/v1/knowledge-base/catalog",
    ]
    assert details["matching_embedding_count"] == 49051


def test_audit_answer_provider_gate_readiness_script_is_valid_and_sanitized() -> None:
    script_path = Path("scripts/audit-answer-provider-gate-readiness.py")

    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(script_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    script_text = script_path.read_text(encoding="utf-8")
    assert "sk-" not in script_text
    assert "secret_values_reported" in script_text
    assert "provider_call_status" in script_text
    assert "production_side_effect" in script_text
    assert "fail-when-not-ready" in script_text


def test_audit_answer_provider_gate_readiness_never_reports_secret_values() -> None:
    module = _load_script_module(
        "audit_answer_provider_gate_readiness_secret_values",
        Path("scripts/audit-answer-provider-gate-readiness.py"),
    )
    snapshot = module._sanitize_env_mapping(
        {
            "MEDICAL_AUDIT_KB_ANSWER_PROVIDER": "openai",
            "MEDICAL_AUDIT_KB_ANSWER_API_KEY_ENV": "DEEPSEEK_API_KEY",
            "MEDICAL_AUDIT_KB_ANSWER_MODEL": "deepseek-chat",
            "MEDICAL_AUDIT_KB_ANSWER_BASE_URL": "https://api.deepseek.com/v1",
            "DEEPSEEK_API_KEY": "do-not-print-this-secret",
            "KIMI_API_KEY": "also-secret",
        }
    )

    scope = module._build_scope_report("local-shell", snapshot)
    report = module._build_report([scope])
    serialized = json.dumps(report, ensure_ascii=False)

    assert report["status"] == "ready_for_smoke"
    assert scope["answer_runtime"]["status"] == "configured_with_key"
    assert scope["answer_runtime"]["api_key_status"] == "SET"
    assert scope["ready_provider_candidates"] == ["deepseek"]
    assert "do-not-print-this-secret" not in serialized
    assert "also-secret" not in serialized
    assert report["boundaries"]["secret_values_reported"] is False
    assert report["boundaries"]["provider_call_status"] == "not_called"


def test_audit_answer_provider_gate_readiness_reports_chat_model_alias_without_secret() -> None:
    module = _load_script_module(
        "audit_answer_provider_gate_readiness_chat_model_values",
        Path("scripts/audit-answer-provider-gate-readiness.py"),
    )
    snapshot = module._sanitize_env_mapping(
        {
            "MEDICAL_AUDIT_KB_CHAT_MODEL_KIMI_2_7_API_KEY_ENV": "MOONSHOT_API_KEY",
            "MEDICAL_AUDIT_KB_CHAT_MODEL_KIMI_2_7_PROVIDER": "kimi",
            "MEDICAL_AUDIT_KB_CHAT_MODEL_KIMI_2_7_MAX_OUTPUT_TOKENS": "4096",
            "MEDICAL_AUDIT_KB_CHAT_MODEL_KIMI_2_7_THINKING_MODE": "enabled",
            "MOONSHOT_API_KEY": "do-not-print-this-moonshot-secret",
        }
    )

    scope = module._build_scope_report("local-shell", snapshot)
    report = module._build_report([scope])
    serialized = json.dumps(report, ensure_ascii=False)

    assert report["status"] == "ready_for_smoke"
    assert scope["ready_chat_model_aliases"] == ["kimi-2.7"]
    kimi_runtime = next(
        item for item in scope["chat_model_runtime"] if item["alias"] == "kimi-2.7"
    )
    assert kimi_runtime["status"] == "configured_with_key"
    assert kimi_runtime["api_key_env"] == "MOONSHOT_API_KEY"
    assert kimi_runtime["api_key_status"] == "SET"
    assert kimi_runtime["model"] == "kimi-k2.6"
    assert kimi_runtime["base_url"] == "https://api.moonshot.cn/v1"
    assert kimi_runtime["max_output_tokens"] == "4096"
    assert kimi_runtime["temperature"] == "1.0"
    assert kimi_runtime["thinking_mode"] == "enabled"
    assert "do-not-print-this-moonshot-secret" not in serialized
    assert report["boundaries"]["secret_values_reported"] is False
    assert report["boundaries"]["provider_call_status"] == "not_called"


@pytest.mark.parametrize(
    ("max_output_tokens", "thinking_mode", "expected_status"),
    (
        ("900", "enabled", "insufficient_output_budget"),
        ("4096", "disabled", "unsupported_thinking_mode"),
    ),
)
def test_audit_answer_provider_gate_readiness_rejects_invalid_kimi_runtime(
    max_output_tokens: str,
    thinking_mode: str,
    expected_status: str,
) -> None:
    module = _load_script_module(
        f"audit_answer_provider_gate_readiness_kimi_{expected_status}",
        Path("scripts/audit-answer-provider-gate-readiness.py"),
    )
    snapshot = module._sanitize_env_mapping(
        {
            "MEDICAL_AUDIT_KB_CHAT_MODEL_KIMI_2_7_API_KEY_ENV": "MOONSHOT_API_KEY",
            "MEDICAL_AUDIT_KB_CHAT_MODEL_KIMI_2_7_MAX_OUTPUT_TOKENS": max_output_tokens,
            "MEDICAL_AUDIT_KB_CHAT_MODEL_KIMI_2_7_THINKING_MODE": thinking_mode,
            "MOONSHOT_API_KEY": "do-not-print-this-moonshot-secret",
        }
    )

    scope = module._build_scope_report("local-shell", snapshot)
    kimi_runtime = next(
        item for item in scope["chat_model_runtime"] if item["alias"] == "kimi-2.7"
    )

    assert kimi_runtime["status"] == expected_status
    assert scope["ready_chat_model_aliases"] == []


def test_audit_answer_provider_gate_readiness_blocks_without_candidate_key() -> None:
    module = _load_script_module(
        "audit_answer_provider_gate_readiness_blocks",
        Path("scripts/audit-answer-provider-gate-readiness.py"),
    )
    snapshot = module._sanitize_env_mapping(
        {
            "MEDICAL_AUDIT_KB_ANSWER_PROVIDER": "fallback",
            "KIMI_EMBEDDING_PROVIDER": "openai",
            "KIMI_EMBEDDING_MODEL": "kimi-for-coding",
        }
    )

    scope = module._build_scope_report("local-shell", snapshot)
    report = module._build_report([scope])

    assert report["status"] == "blocked"
    assert report["blockers"] == ["no-provider-or-chat-model-api-key-env-set"]
    assert scope["answer_runtime"]["status"] == "fallback_or_unset"
    assert scope["ready_chat_model_aliases"] == []
    assert scope["ready_provider_candidates"] == []
    assert report["boundaries"]["production_env_write"] is False


def test_run_production_chat_model_catalog_readonly_probe_script_is_valid() -> None:
    script_path = Path("scripts/run-production-chat-model-catalog-readonly-probe.py")

    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(script_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    script_text = script_path.read_text(encoding="utf-8")
    assert "sk-" not in script_text
    assert "provider_call" in script_text
    assert "production_env_write" in script_text
    assert "secret_values_reported" in script_text
    assert "require-ready-model" in script_text


def test_run_production_chat_model_catalog_readonly_probe_allows_catalog_only() -> None:
    module = _load_script_module(
        "run_production_chat_model_catalog_readonly_catalog_only",
        Path("scripts/run-production-chat-model-catalog-readonly-probe.py"),
    )

    def fake_http_get(
        url: str,
        _headers: dict[str, str],
        _timeout_seconds: float,
    ) -> object:
        if url.endswith("/api/v1/deployment/metadata"):
            return module.HttpResponse(
                status=200,
                url=url,
                content=json.dumps(_deployment_metadata_payload()).encode(),
                headers={"content-type": "application/json"},
            )
        if url.endswith("/api/v1/query/models"):
            return module.HttpResponse(
                status=200,
                url=url,
                content=json.dumps(
                    {
                        "contract_version": "chat-model-catalog-v1",
                        "default_model": "kimi-2.7",
                        "items": [
                            {
                                "alias": "kimi-2.7",
                                "label": "Kimi K2.6（兼容别名）",
                                "provider": None,
                                "available": False,
                                "default": True,
                                "unavailable_reason": "missing_api_key_env",
                            },
                            {
                                "alias": "deepseek-v4-pro",
                                "label": "DeepSeek V4 Pro",
                                "provider": None,
                                "available": False,
                                "default": False,
                                "unavailable_reason": "missing_api_key_env",
                            },
                        ],
                        "boundaries": {
                            "production_write": False,
                            "provider_call": False,
                            "secret_values_reported": False,
                            "source": "environment_capability_probe_only",
                        },
                    }
                ).encode(),
                headers={"content-type": "application/json"},
            )
        raise AssertionError(url)

    report = module._run_probe(
        base_url="https://audit.lute-tlz-dddd.top",
        timeout_seconds=1,
        user_id="readonly-probe",
        role="auditor",
        tenant_id="hospital-demo",
        project_key="SELF-CHECK-FUND-20260607",
        require_ready_model=False,
        http_get=fake_http_get,
    )

    assert report["status"] == "pass"
    assert report["summary"]["ready_model_count"] == 0
    assert report["summary"]["available_model_aliases"] == []
    assert report["boundaries"]["provider_call"] is False
    assert report["boundaries"]["production_env_write"] is False
    assert report["boundaries"]["secret_values_reported"] is False


def test_run_production_chat_model_catalog_readonly_probe_can_require_ready_model() -> None:
    module = _load_script_module(
        "run_production_chat_model_catalog_readonly_require_ready",
        Path("scripts/run-production-chat-model-catalog-readonly-probe.py"),
    )

    def fake_http_get(
        url: str,
        _headers: dict[str, str],
        _timeout_seconds: float,
    ) -> object:
        if url.endswith("/api/v1/deployment/metadata"):
            return module.HttpResponse(
                status=200,
                url=url,
                content=json.dumps(_deployment_metadata_payload()).encode(),
                headers={"content-type": "application/json"},
            )
        if url.endswith("/api/v1/query/models"):
            return module.HttpResponse(
                status=200,
                url=url,
                content=json.dumps(
                    {
                        "contract_version": "chat-model-catalog-v1",
                        "default_model": "kimi-2.7",
                        "items": [
                            {
                                "alias": "kimi-2.7",
                                "label": "Kimi K2.6（兼容别名）",
                                "provider": None,
                                "available": False,
                                "default": True,
                                "unavailable_reason": "missing_api_key_env",
                            },
                            {
                                "alias": "deepseek-v4-pro",
                                "label": "DeepSeek V4 Pro",
                                "provider": None,
                                "available": False,
                                "default": False,
                                "unavailable_reason": "missing_api_key_env",
                            },
                        ],
                        "boundaries": {
                            "production_write": False,
                            "provider_call": False,
                            "secret_values_reported": False,
                            "source": "environment_capability_probe_only",
                        },
                    }
                ).encode(),
                headers={"content-type": "application/json"},
            )
        raise AssertionError(url)

    report = module._run_probe(
        base_url="https://audit.lute-tlz-dddd.top",
        timeout_seconds=1,
        user_id="readonly-probe",
        role="auditor",
        tenant_id="hospital-demo",
        project_key="SELF-CHECK-FUND-20260607",
        require_ready_model=True,
        http_get=fake_http_get,
    )

    assert report["status"] == "fail"
    query_models_step = next(
        step for step in report["steps"] if step["name"] == "query-models-catalog"
    )
    assert query_models_step["details"]["error"] == "no chat model alias is available"


@pytest.mark.parametrize(
    ("module_name", "script_path"),
    (
        (
            "run_production_documents_readonly_probe_exact_origin",
            Path("scripts/run-production-documents-readonly-probe.py"),
        ),
        (
            "run_production_chat_model_catalog_readonly_probe_exact_origin",
            Path("scripts/run-production-chat-model-catalog-readonly-probe.py"),
        ),
    ),
)
def test_production_readonly_probes_bind_the_exact_production_origin(
    module_name: str,
    script_path: Path,
) -> None:
    module = _load_script_module(module_name, script_path)

    assert module._normalize_production_base_url(module.DEFAULT_BASE_URL) == (
        module.DEFAULT_BASE_URL
    )
    assert module._normalize_production_base_url(f"{module.DEFAULT_BASE_URL}:443/") == (
        module.DEFAULT_BASE_URL
    )
    for invalid_base_url in (
        "http://audit.lute-tlz-dddd.top",
        "https://audit.lute-tlz-dddd.top:444",
        "https://audit.lute-tlz-dddd.top/probe",
        "https://audit.lute-tlz-dddd.top?target=probe",
        "https://probe@audit.lute-tlz-dddd.top",
        "https://audit.example.test",
    ):
        with pytest.raises(module.ReadOnlyProbeError, match="exact production origin"):
            module._normalize_production_base_url(invalid_base_url)


@pytest.mark.parametrize(
    ("module_name", "script_path"),
    (
        (
            "run_production_documents_readonly_probe_no_redirect",
            Path("scripts/run-production-documents-readonly-probe.py"),
        ),
        (
            "run_production_chat_model_catalog_readonly_probe_no_redirect",
            Path("scripts/run-production-chat-model-catalog-readonly-probe.py"),
        ),
    ),
)
def test_production_readonly_probes_do_not_follow_redirects(
    module_name: str,
    script_path: Path,
) -> None:
    module = _load_script_module(module_name, script_path)
    target_hits: list[dict[str, str]] = []

    class TargetHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            target_hits.append(
                {key.lower(): value for key, value in self.headers.items()}
            )
            self.send_response(200)
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:
            del format, args

    target_server = ThreadingHTTPServer(("127.0.0.1", 0), TargetHandler)
    target_thread = threading.Thread(target=target_server.serve_forever, daemon=True)
    target_thread.start()

    class RedirectHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            self.send_response(302)
            self.send_header(
                "Location",
                f"http://127.0.0.1:{target_server.server_port}/target",
            )
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:
            del format, args

    redirect_server = ThreadingHTTPServer(("127.0.0.1", 0), RedirectHandler)
    redirect_thread = threading.Thread(
        target=redirect_server.serve_forever,
        daemon=True,
    )
    redirect_thread.start()

    try:
        response = module._http_get(
            f"http://127.0.0.1:{redirect_server.server_port}/redirect",
            {"X-API-Key": "secret-api-key"},
            1,
        )
    finally:
        redirect_server.shutdown()
        target_server.shutdown()
        redirect_thread.join(timeout=2)
        target_thread.join(timeout=2)
        redirect_server.server_close()
        target_server.server_close()

    assert response.status == 302
    assert target_hits == []


def test_audit_auth_sso_contract_readiness_script_is_valid_and_sanitized() -> None:
    script_path = Path("scripts/audit-auth-sso-contract-readiness.py")

    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(script_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    script_text = script_path.read_text(encoding="utf-8")
    assert "sk-" not in script_text
    assert "production_side_effect" in script_text
    assert "provider_call_status" in script_text
    assert "secret_values_reported" in script_text
    assert "X-Medical-Audit-Claims-Signature" in script_text
    assert "X-Tenant-Id" in script_text


def test_audit_auth_sso_contract_readiness_blocks_default_transition_layer() -> None:
    module = _load_script_module(
        "audit_auth_sso_contract_readiness_blocks_default",
        Path("scripts/audit-auth-sso-contract-readiness.py"),
    )
    report = module.build_readiness_report(
        module.ReadinessConfig(
            target_mode="trusted-sso-proxy",
            json_output=None,
            markdown_output=None,
            fail_when_blocked=False,
        ),
        {},
    )

    assert report["status"] == "blocked"
    assert report["evidence_grade"] == "L2-fixture-or-dry-run"
    assert "auth-mode-not-trusted-sso-proxy" in report["blockers"]
    assert "trusted-proxy-signature-key-env-missing" in report["blockers"]
    assert "legacy-header-auth-still-enabled" in report["blockers"]
    assert report["boundaries"]["production_side_effect"] == "none"
    assert report["boundaries"]["provider_call_status"] == "not_called"
    assert report["boundaries"]["secret_values_reported"] is False


def test_audit_auth_sso_contract_readiness_accepts_trusted_proxy_config() -> None:
    module = _load_script_module(
        "audit_auth_sso_contract_readiness_ready_proxy",
        Path("scripts/audit-auth-sso-contract-readiness.py"),
    )
    env = {
        "MEDICAL_AUDIT_AUTH_MODE": "trusted-sso-proxy",
        "MEDICAL_AUDIT_TRUSTED_PROXY_ENABLED": "true",
        "MEDICAL_AUDIT_TRUSTED_PROXY_SIGNATURE_KEY_ENV": "SSO_PROXY_SIGNATURE_KEY",
        "MEDICAL_AUDIT_TRUSTED_PROXY_ALLOWED_SOURCE_CIDRS": "10.0.0.0/8",
        "MEDICAL_AUDIT_DISABLE_LEGACY_HEADER_AUTH": "true",
        "SSO_PROXY_SIGNATURE_KEY": "redacted-sentinel-value",
    }

    report = module.build_readiness_report(
        module.ReadinessConfig(
            target_mode="trusted-sso-proxy",
            json_output=None,
            markdown_output=None,
            fail_when_blocked=False,
        ),
        env,
    )
    serialized = json.dumps(report, ensure_ascii=False)

    assert report["status"] == "ready_for_readonly_gateway_probe"
    assert report["blockers"] == []
    assert "redacted-sentinel-value" not in serialized
    assert report["safe_env"]["referenced_secret_status"] == {
        "SSO_PROXY_SIGNATURE_KEY": "SET"
    }
    assert report["mode_readiness"]["status"] == "ready"


def test_audit_document_governance_contract_readiness_script_is_valid_and_sanitized() -> None:
    script_path = Path("scripts/audit-document-governance-contract-readiness.py")

    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(script_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    script_text = script_path.read_text(encoding="utf-8")
    assert "sk-" not in script_text
    assert "production_side_effect" in script_text
    assert "external_governance_provider_call" in script_text
    assert "object_storage_write" in script_text
    assert "DOCUMENT_GOVERNANCE_REDACTION_REWRITE_ENABLED_ENV" in script_text
    assert "DOCUMENT_GOVERNANCE_AUDIT_EVENT_REQUIRED_ENV" in script_text


def test_audit_document_governance_contract_readiness_blocks_default_config() -> None:
    module = _load_script_module(
        "audit_document_governance_contract_readiness_blocks_default",
        Path("scripts/audit-document-governance-contract-readiness.py"),
    )
    report = module.build_readiness_report_from_settings(
        module.ReadinessConfig(
            config_path=None,
            qcloud_cos_available=False,
            require_external_dlp_provider=False,
            json_output=None,
            markdown_output=None,
            fail_when_blocked=False,
        ),
        document_storage=module.DocumentStorageSettings(),
        document_governance=module.DocumentUploadGovernanceSettings(),
        environ={},
    )

    assert report["status"] == "blocked"
    assert report["evidence_grade"] == "L2-fixture-or-dry-run"
    assert "cos:document-storage-provider-not-tencent-cos" in report["blockers"]
    assert "enterprise-virus-scan-provider-not-configured" in report["blockers"]
    assert "enterprise-dlp-provider-not-configured" in report["blockers"]
    assert "redaction-rewrite-not-enabled" in report["blockers"]
    assert "document-governance-audit-event-contract-missing" in report["blockers"]
    assert report["boundaries"]["production_side_effect"] == "none"
    assert report["boundaries"]["external_governance_provider_call"] == "not_called"
    assert report["boundaries"]["object_storage_write"] is False


def test_audit_document_governance_contract_readiness_accepts_enterprise_config() -> None:
    module = _load_script_module(
        "audit_document_governance_contract_readiness_ready",
        Path("scripts/audit-document-governance-contract-readiness.py"),
    )
    env = {
        "COS_SECRET_ID": "sentinel-cos-id-value",
        "COS_SECRET_KEY": "sentinel-cos-key-value",
    }

    report = module.build_readiness_report_from_settings(
        module.ReadinessConfig(
            config_path=None,
            qcloud_cos_available=True,
            require_external_dlp_provider=False,
            json_output=None,
            markdown_output=None,
            fail_when_blocked=False,
        ),
        document_storage=module.DocumentStorageSettings(
            provider="tencent-cos",
            cos_bucket="medical-audit-documents",
            cos_region="ap-guangzhou",
            cos_prefix="personal-materials/prod",
            cos_secret_id_env="COS_SECRET_ID",
            cos_secret_key_env="COS_SECRET_KEY",
            cos_sdk_bootstrap_enabled=True,
            signed_url_ttl_seconds=120,
            local_quarantine_retention_days=7,
            object_retention_days=365,
            record_storage_objects=True,
        ),
        document_governance=module.DocumentUploadGovernanceSettings(
            virus_scan_provider="clamav-sidecar",
            dlp_review_provider="ruleset-v1",
            redaction_rewrite_enabled=True,
            redaction_policy_version="redaction-v1",
            redaction_manual_review_required=True,
            governance_audit_event_required=True,
        ),
        environ=env,
    )
    serialized = json.dumps(report, ensure_ascii=False)

    assert report["status"] == "ready_for_readonly_governance_probe"
    assert report["blockers"] == []
    assert "sentinel-cos-id-value" not in serialized
    assert "sentinel-cos-key-value" not in serialized
    assert "redaction-v1" not in serialized
    assert report["safe_env"]["referenced_secret_status"] == {
        "COS_SECRET_ID": "SET",
        "COS_SECRET_KEY": "SET",
    }


def test_audit_frontend_backend_api_contract_schema_script_is_valid() -> None:
    script_path = Path("scripts/audit-frontend-backend-api-contract-schema.py")

    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(script_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    script_text = script_path.read_text(encoding="utf-8")
    assert "sk-" not in script_text
    assert "production_side_effect" in script_text
    assert "provider_call_status" in script_text
    assert "secret_values_reported" in script_text


def test_audit_frontend_backend_api_contract_schema_marks_schema_gaps() -> None:
    module = _load_script_module(
        "audit_frontend_backend_api_contract_schema",
        Path("scripts/audit-frontend-backend-api-contract-schema.py"),
    )
    schema = module._load_openapi_schema()
    api_types_text = Path("web/src/lib/api-types.ts").read_text(encoding="utf-8")

    report = module.build_contract_report(schema=schema, api_types_text=api_types_text)
    items = {item["surface"]: item for item in report["items"]}

    assert report["evidence_grade"] == "L2-fixture-or-dry-run"
    assert report["boundaries"]["production_side_effect"] == "none"
    assert report["boundaries"]["provider_call_status"] == "not_called"
    assert report["summary"]["contract_count"] >= 30
    assert items["document-uploads"]["response"]["status"] == "aligned"
    assert items["knowledge-query"]["response"]["status"] == "missing_response_schema"
    assert items["agents-list"]["response"]["status"] == "missing_response_schema"


def test_audit_document_governance_ready_profile_outputs_ready_without_secret_leak(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "document-governance-ready-profile.json"
    markdown_path = tmp_path / "document-governance-ready-profile.md"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/audit-document-governance-contract-readiness.py",
            "--config",
            "configs/knowledge-query-engine-document-governance-ready-profile.yaml",
            "--qcloud-cos-availability",
            "available",
            "--json-output",
            str(report_path),
            "--markdown-output",
            str(markdown_path),
        ],
        cwd=Path(__file__).resolve().parents[2],
        env={
            **os.environ,
            "MEDICAL_AUDIT_DOCUMENT_READY_PROFILE_COS_SECRET_ID": (
                "ready-profile-cos-id-sentinel"
            ),
            "MEDICAL_AUDIT_DOCUMENT_READY_PROFILE_COS_SECRET_KEY": (
                "ready-profile-cos-key-sentinel"
            ),
        },
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    serialized_file = report_path.read_text(encoding="utf-8")
    markdown = markdown_path.read_text(encoding="utf-8")

    assert report["status"] == "ready_for_readonly_governance_probe"
    assert report["blockers"] == []
    assert report["evidence_grade"] == "L2-fixture-or-dry-run"
    assert report["boundaries"]["production_side_effect"] == "none"
    assert report["boundaries"]["object_storage_write"] is False
    assert report["boundaries"]["external_governance_provider_call"] == "not_called"
    assert report["safe_env"]["referenced_secret_status"] == {
        "MEDICAL_AUDIT_DOCUMENT_READY_PROFILE_COS_SECRET_ID": "SET",
        "MEDICAL_AUDIT_DOCUMENT_READY_PROFILE_COS_SECRET_KEY": "SET",
    }
    for output in (completed.stdout, serialized_file, markdown):
        assert "ready-profile-cos-id-sentinel" not in output
        assert "ready-profile-cos-key-sentinel" not in output
        assert "local-ready-profile-v1" not in output


def test_run_document_governance_ready_profile_outputs_ready_without_secret_leak() -> None:
    script_path = Path("scripts/run-document-governance-ready-profile.py")
    compile_result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(script_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert compile_result.returncode == 0, compile_result.stderr

    completed = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    assert report["status"] == "ready_for_readonly_governance_probe"
    assert report["blockers"] == []
    assert "ready-profile-cos-id-sentinel" not in completed.stdout
    assert "ready-profile-cos-key-sentinel" not in completed.stdout


def test_prepare_document_governance_production_readonly_plan_script_is_scoped() -> None:
    script_path = Path("scripts/prepare-document-governance-production-readonly-plan.py")

    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(script_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    script_text = script_path.read_text(encoding="utf-8")
    assert "sk-" not in script_text
    assert "production_side_effect" in script_text
    assert "production_readonly_probe" in script_text
    assert "production_env_write" in script_text
    assert "object_storage_write" in script_text
    assert "network_call_status" in script_text
    assert "not_called" in script_text


def test_prepare_document_governance_production_readonly_plan_reports_layers(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "document-governance-production-readonly-plan.json"
    markdown_path = tmp_path / "document-governance-production-readonly-plan.md"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/prepare-document-governance-production-readonly-plan.py",
            "--json-output",
            str(report_path),
            "--markdown-output",
            str(markdown_path),
        ],
        cwd=Path(__file__).resolve().parents[2],
        env={
            **os.environ,
            "COS_SECRET_ID": "do-not-print-cos-id",
            "COS_SECRET_KEY": "do-not-print-cos-key",
        },
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    serialized_file = report_path.read_text(encoding="utf-8")
    markdown = markdown_path.read_text(encoding="utf-8")
    layer_names = {layer["name"] for layer in report["evidence_layers"]}
    readonly_fields = set(
        report["production_readonly_observation_spec"]["required_report_fields"]
    )
    authorization_envs = {
        item["env_name"]
        for item in report["production_configuration_authorization_package"][
            "required_manual_inputs"
        ]
    }

    assert report["status"] == "ready_for_production_readonly_plan_review"
    assert report["evidence_grade"] == "L2-fixture-or-dry-run"
    assert layer_names == {
        "local-ready-profile-dry-run",
        "production-readonly-observation",
        "authorized-write-governance-e2e",
    }
    assert report["evidence_layers"][1]["current_status"] == "not_run"
    assert report["evidence_layers"][2]["current_status"] == "not_authorized"
    assert report["boundaries"]["production_side_effect"] == "none"
    assert report["boundaries"]["production_readonly_probe"] == "not_run"
    assert report["boundaries"]["production_env_write"] is False
    assert report["boundaries"]["object_storage_write"] is False
    assert report["boundaries"]["network_call_status"] == "not_called"
    assert report["boundaries"]["provider_call_status"] == "not_called"
    assert report["boundaries"]["external_governance_provider_call"] == "not_called"
    assert report["boundaries"]["authorized_write_e2e"] == "not_run"
    assert report["boundaries"]["secret_values_reported"] is False
    assert "production-readonly-not-run" in report["blockers"]
    assert "production-env-write-not-authorized" in report["blockers"]
    assert "authorized-write-e2e-not-authorized" in report["blockers"]
    assert "document_storage_provider" in readonly_fields
    assert "redaction_policy_version_status" in readonly_fields
    assert "audit_log_readonly_status" in readonly_fields
    assert "MEDICAL_AUDIT_DOCUMENT_STORAGE_COS_BUCKET" in authorization_envs
    assert "MEDICAL_AUDIT_DOCUMENT_STORAGE_RECORD_OBJECTS" in authorization_envs
    assert "MEDICAL_AUDIT_DOCUMENT_GOVERNANCE_AUDIT_EVENT_REQUIRED" in authorization_envs
    for output in (completed.stdout, serialized_file, markdown):
        assert "do-not-print-cos-id" not in output
        assert "do-not-print-cos-key" not in output


def test_run_document_governance_production_readonly_precheck_script_is_scoped() -> None:
    script_path = Path("scripts/run-document-governance-production-readonly-precheck.py")

    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(script_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    script_text = script_path.read_text(encoding="utf-8")
    assert "sk-" not in script_text
    assert "production_readonly_probe" in script_text
    assert "production_env_write" in script_text
    assert "object_storage_write" in script_text
    assert "network_call_status" in script_text
    assert "authorized_write_e2e" in script_text
    assert "not_called" in script_text


def test_run_document_governance_production_readonly_precheck_reports_manual_review(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "document-governance-production-readonly-precheck.json"
    markdown_path = tmp_path / "document-governance-production-readonly-precheck.md"
    ready_json = tmp_path / "ready-profile.json"
    ready_markdown = tmp_path / "ready-profile.md"
    plan_json = tmp_path / "production-readonly-plan.json"
    plan_markdown = tmp_path / "production-readonly-plan.md"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run-document-governance-production-readonly-precheck.py",
            "--json-output",
            str(report_path),
            "--markdown-output",
            str(markdown_path),
            "--ready-profile-json-output",
            str(ready_json),
            "--ready-profile-markdown-output",
            str(ready_markdown),
            "--plan-json-output",
            str(plan_json),
            "--plan-markdown-output",
            str(plan_markdown),
        ],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    serialized_file = report_path.read_text(encoding="utf-8")
    markdown = markdown_path.read_text(encoding="utf-8")
    ready_report = json.loads(ready_json.read_text(encoding="utf-8"))
    plan_report = json.loads(plan_json.read_text(encoding="utf-8"))
    check_names = {check["name"] for check in report["checks"]}

    assert report["status"] == "ready_for_manual_authorization_review"
    assert report["evidence_grade"] == "L2-fixture-or-dry-run"
    assert report["blockers"] == []
    assert check_names == {
        "ready-profile-dry-run",
        "production-readonly-plan",
        "manual-authorization-package",
    }
    assert ready_report["status"] == "ready_for_readonly_governance_probe"
    assert plan_report["status"] == "ready_for_production_readonly_plan_review"
    assert report["boundaries"]["production_side_effect"] == "none"
    assert report["boundaries"]["production_readonly_probe"] == "not_run"
    assert report["boundaries"]["production_env_write"] is False
    assert report["boundaries"]["object_storage_write"] is False
    assert report["boundaries"]["network_call_status"] == "not_called"
    assert report["boundaries"]["provider_call_status"] == "not_called"
    assert report["boundaries"]["external_governance_provider_call"] == "not_called"
    assert report["boundaries"]["authorized_write_e2e"] == "not_run"
    assert report["boundaries"]["secret_values_reported"] is False
    assert report["next_allowed_step"]["step"] == (
        "request explicit production read-only probe approval"
    )
    assert "production env write" in report["still_forbidden_without_separate_approval"]
    assert any(
        "redaction policy version" in item
        for item in report["manual_authorization_todo"]
    )
    for output in (
        completed.stdout,
        serialized_file,
        markdown,
        ready_json.read_text(encoding="utf-8"),
        ready_markdown.read_text(encoding="utf-8"),
        plan_json.read_text(encoding="utf-8"),
        plan_markdown.read_text(encoding="utf-8"),
    ):
        assert "ready-profile-cos-id-sentinel" not in output
        assert "ready-profile-cos-key-sentinel" not in output


def test_prepare_document_governance_production_readonly_coverage_script_is_scoped() -> None:
    script_path = Path(
        "scripts/prepare-document-governance-production-readonly-observation-coverage.py"
    )

    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(script_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    script_text = script_path.read_text(encoding="utf-8")
    assert "sk-" not in script_text
    assert "production_readonly_probe" in script_text
    assert "observable_by_new_governance_status_endpoint" in script_text
    assert "observable_by_deployment_metadata_endpoint" in script_text
    assert "blocked_by_audit_log_side_effect" in script_text
    assert "non_get_http_methods_allowed" in script_text
    assert "secret_values_reported" in script_text


def test_prepare_document_governance_production_readonly_coverage_reports_gaps(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "document-governance-production-readonly-coverage.json"
    markdown_path = tmp_path / "document-governance-production-readonly-coverage.md"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/prepare-document-governance-production-readonly-observation-coverage.py",
            "--json-output",
            str(report_path),
            "--markdown-output",
            str(markdown_path),
        ],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    serialized_file = report_path.read_text(encoding="utf-8")
    markdown = markdown_path.read_text(encoding="utf-8")
    fields = {item["field"]: item for item in report["required_fields"]}
    blocked_paths = {
        item["path"] for item in report["side_effect_blocked_endpoints"]
    }
    write_methods = {item["method"] for item in report["write_endpoints_out_of_scope"]}

    assert report["status"] == "ready"
    assert report["evidence_grade"] == "L2-fixture-or-dry-run"
    assert report["coverage_summary"]["total"] == 30
    assert report["coverage_summary"]["observable_by_existing_probe"] == 1
    assert report["coverage_summary"]["observable_by_new_governance_status_endpoint"] == 26
    assert report["coverage_summary"]["observable_by_deployment_metadata_endpoint"] == 1
    assert report["coverage_summary"]["observable_by_boundary"] == 2
    assert fields["expected_deploy_sha"]["status"] == (
        "observable_by_deployment_metadata_endpoint"
    )
    assert fields["expected_deploy_sha"]["current_endpoint"] == (
        "/api/v1/deployment/metadata"
    )
    assert fields["document_storage_provider"]["status"] == (
        "observable_by_new_governance_status_endpoint"
    )
    assert fields["redaction_policy_version_status"]["status"] == (
        "observable_by_new_governance_status_endpoint"
    )
    assert fields["document_upload_list_readonly_status"]["status"] == (
        "observable_by_new_governance_status_endpoint"
    )
    assert fields["download_metadata_readonly_status"]["status"] == (
        "observable_by_new_governance_status_endpoint"
    )
    assert "/api/v1/documents/uploads" in blocked_paths
    assert "/api/v1/documents/uploads/{upload_id}/download" in blocked_paths
    assert "/api/backend/index/search-backend" in blocked_paths
    assert "POST" in write_methods
    assert report["boundaries"]["production_side_effect"] == "none"
    assert report["boundaries"]["production_readonly_probe"] == "not_run"
    assert report["boundaries"]["production_env_write"] is False
    assert report["boundaries"]["object_storage_write"] is False
    assert report["boundaries"]["network_call_status"] == "not_called"
    assert report["boundaries"]["provider_call_status"] == "not_called"
    assert report["boundaries"]["external_governance_provider_call"] == "not_called"
    assert report["boundaries"]["authorized_write_e2e"] == "not_run"
    assert report["boundaries"]["allowed_http_methods_for_future_probe"] == ["GET"]
    assert report["boundaries"]["non_get_http_methods_allowed"] is False
    assert "governance-config-readonly-endpoint-missing" not in report["blockers"]
    assert "deploy-metadata-readonly-endpoint-missing" not in report["blockers"]
    assert report["blockers"] == []
    for output in (completed.stdout, serialized_file, markdown):
        assert "ready-profile-cos-id-sentinel" not in output
        assert "ready-profile-cos-key-sentinel" not in output


def test_run_production_documents_governance_result_e2e_script_is_scoped() -> None:
    script_path = Path("scripts/run-production-documents-governance-result-e2e.py")

    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(script_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    script_text = script_path.read_text(encoding="utf-8")
    assert "sk-" not in script_text
    assert "--confirm-production-write" in script_text
    assert "X-Tenant-Id" in script_text
    assert "X-Project-Key" in script_text
    assert "external_governance_provider_call" in script_text
    assert "indexing_triggered" in script_text


def test_run_production_documents_governance_actor_headers_include_scope() -> None:
    module = _load_script_module(
        "run_production_documents_governance_actor_headers_include_scope",
        Path("scripts/run-production-documents-governance-result-e2e.py"),
    )

    assert module._actor_headers(
        user_id="owner-a",
        role="auditor",
        tenant_id="tenant-a",
        project_key="project-a",
    ) == {
        "X-User-Id": "owner-a",
        "X-Role": "auditor",
        "X-Project-Key": "project-a",
        "X-Tenant-Id": "tenant-a",
    }


def test_run_production_documents_governance_confirmation_blocks_production() -> None:
    module = _load_script_module(
        "run_production_documents_governance_confirmation_blocks_production",
        Path("scripts/run-production-documents-governance-result-e2e.py"),
    )

    with pytest.raises(module.E2EError, match="confirm-production-write"):
        module._require_production_write_confirmation(
            base_url="https://audit.lute-tlz-dddd.top",
            confirm_production_write="",
        )

    module._require_production_write_confirmation(
        base_url="https://audit.lute-tlz-dddd.top",
        confirm_production_write="audit.lute-tlz-dddd.top",
    )
    module._require_production_write_confirmation(
        base_url="http://127.0.0.1:8000",
        confirm_production_write="",
    )


def test_run_production_documents_readonly_probe_reports_permission_shape_failure() -> None:
    module = _load_script_module(
        "run_production_documents_readonly_probe_shape_failure",
        Path("scripts/run-production-documents-readonly-probe.py"),
    )

    def fake_http_get(url: str, headers: dict[str, str], timeout_seconds: float) -> object:
        del headers, timeout_seconds
        if url.endswith("/api/v1/deployment/metadata"):
            return module.HttpResponse(
                status=200,
                url=url,
                content=json.dumps(_deployment_metadata_payload()).encode(),
                headers={"content-type": "application/json"},
            )
        if url.endswith("/documents"):
            return module.HttpResponse(
                status=200,
                url=url,
                content=(
                    "AI审计一体化协作平台 /_next/static/ "
                    "app/(workspace)/documents/page-abc123.js"
                ).encode(),
                headers={"content-type": "text/html"},
            )
        if url.endswith("/api/v1/documents/permissions"):
            return module.HttpResponse(
                status=200,
                url=url,
                content=json.dumps(
                    {
                        "source_collections": [{"source_collection": "medical-insurance-laws"}],
                        "upload_permissions": {
                            "can_upload_personal": True,
                            "can_read_all_personal_uploads": False,
                        },
                    },
                    ensure_ascii=False,
                ).encode(),
                headers={"content-type": "application/json"},
            )
        if url.endswith("/api/v1/documents/governance/status"):
            return module.HttpResponse(
                status=200,
                url=url,
                content=json.dumps(_documents_governance_status_payload()).encode(),
                headers={"content-type": "application/json"},
            )
        if url.endswith("/api/backend/health"):
            return module.HttpResponse(
                status=200,
                url=url,
                content=b'{"status":"ok","version":"0.1.0"}',
                headers={"content-type": "application/json"},
            )
        if url.endswith("/api/backend/index/search-backend"):
            return module.HttpResponse(
                status=200,
                url=url,
                content=b'{"backend":"postgres","ready":true,"details":{"matching_embedding_count":49051,"embedding_provider":"openai"}}',
                headers={"content-type": "application/json"},
            )
        raise AssertionError(url)

    report = module._run_probe(
        base_url="https://audit.lute-tlz-dddd.top",
        timeout_seconds=1,
        user_id="readonly-probe",
        role="auditor",
        tenant_id="hospital-demo",
        project_key="SELF-CHECK-FUND-20260607",
        api_key_env=None,
        http_get=fake_http_get,
    )

    assert report["status"] == "fail"
    assert report["summary"]["deploy_sha_status"] == "set"
    assert report["summary"]["deploy_sha_matches_expected"] is None
    assert report["summary"]["backend_health"] == "ok"
    assert "documents_role" not in report["summary"]
    permission_step = next(
        step for step in report["steps"] if step["name"] == "documents-permissions"
    )
    assert permission_step["passed"] is False
    assert permission_step["details"]["error"] == "role mismatch: None"
    assert report["boundaries"]["production_write"] is False
    assert report["boundaries"]["deployment_metadata_api_called"] is True
    assert report["boundaries"]["document_upload_list_api_called"] is False
    assert report["boundaries"]["document_governance_status_api_called"] is True


def test_run_production_documents_readonly_probe_uses_pr232_page_contract() -> None:
    module = _load_script_module(
        "run_production_documents_readonly_probe_pr232_contract",
        Path("scripts/run-production-documents-readonly-probe.py"),
    )
    expected_text = (
        "AI审计一体化协作平台",
        "/_next/static/",
        "app/(workspace)/documents/page-",
    )

    assert expected_text == module.EXPECTED_DOCUMENTS_TEXT

    details = module._check_documents_page(
        "https://audit.lute-tlz-dddd.top",
        timeout_seconds=1,
        http_get=lambda url, headers, timeout_seconds: module.HttpResponse(
            status=200,
            url=url,
            content=(
                "AI审计一体化协作平台 /_next/static/ "
                "app/(workspace)/documents/page-abc123.js"
            ).encode(),
            headers={"content-type": "text/html"},
        ),
    )

    assert details["status_code"] == 200
    assert all(details["expected_utf8_text"].values())


def test_run_production_documents_readonly_probe_skips_search_backend_audit_log_endpoint() -> None:
    module = _load_script_module(
        "run_production_documents_readonly_probe_skips_search_backend_audit_log_endpoint",
        Path("scripts/run-production-documents-readonly-probe.py"),
    )

    def fake_http_get(url: str, headers: dict[str, str], timeout_seconds: float) -> object:
        del headers, timeout_seconds
        if url.endswith("/api/v1/deployment/metadata"):
            return module.HttpResponse(
                status=200,
                url=url,
                content=json.dumps(_deployment_metadata_payload()).encode(),
                headers={"content-type": "application/json"},
            )
        if url.endswith("/documents"):
            return module.HttpResponse(
                status=200,
                url=url,
                content=(
                    "AI审计一体化协作平台 /_next/static/ "
                    "app/(workspace)/documents/page-abc123.js"
                ).encode(),
                headers={"content-type": "text/html"},
            )
        if url.endswith("/api/v1/documents/permissions"):
            return module.HttpResponse(
                status=200,
                url=url,
                content=json.dumps(
                    {
                        "role": "auditor",
                        "source_collections": [{"source_collection": "medical-insurance-laws"}],
                        "upload_permissions": {
                            "can_upload_personal": True,
                            "can_read_all_personal_uploads": False,
                        },
                    },
                    ensure_ascii=False,
                ).encode(),
                headers={"content-type": "application/json"},
            )
        if url.endswith("/api/v1/documents/governance/status"):
            return module.HttpResponse(
                status=200,
                url=url,
                content=json.dumps(_documents_governance_status_payload()).encode(),
                headers={"content-type": "application/json"},
            )
        if url.endswith("/api/backend/health"):
            return module.HttpResponse(
                status=200,
                url=url,
                content=b'{"status":"ok","version":"0.1.0"}',
                headers={"content-type": "application/json"},
            )
        raise AssertionError(url)

    report = module._run_probe(
        base_url="https://audit.lute-tlz-dddd.top",
        timeout_seconds=1,
        user_id="readonly-probe",
        role="auditor",
        tenant_id="hospital-demo",
        project_key="SELF-CHECK-FUND-20260607",
        api_key_env=None,
        http_get=fake_http_get,
    )

    assert report["status"] == "pass"
    assert report["summary"]["deploy_sha_status"] == "set"
    assert report["summary"]["backend_health"] == "ok"
    assert "search_backend_ready" not in report["summary"]
    assert all(step["name"] != "backend-search-backend" for step in report["steps"])
    assert "/api/backend/index/search-backend" in report["boundaries"][
        "skipped_audit_log_writing_endpoints"
    ]


def test_run_production_documents_readonly_probe_auth_headers_include_context() -> None:
    module = _load_script_module(
        "run_production_documents_readonly_probe_auth_headers",
        Path("scripts/run-production-documents-readonly-probe.py"),
    )

    assert module._auth_headers(
        user_id="readonly-probe",
        role="auditor",
        tenant_id="hospital-demo",
        project_key="SELF-CHECK-FUND-20260607",
        api_key=None,
    ) == {
        "X-User-Id": "readonly-probe",
        "X-Role": "auditor",
        "X-Project-Key": "SELF-CHECK-FUND-20260607",
        "X-Tenant-Id": "hospital-demo",
    }
    assert module._auth_headers(
        user_id="readonly-probe",
        role="auditor",
        tenant_id="hospital-demo",
        project_key="SELF-CHECK-FUND-20260607",
        api_key="secret-value",
    )["X-API-Key"] == "secret-value"


def test_run_production_documents_readonly_probe_deployment_metadata_expected_sha() -> None:
    module = _load_script_module(
        "run_production_documents_readonly_probe_deploy_sha",
        Path("scripts/run-production-documents-readonly-probe.py"),
    )
    payload = _deployment_metadata_payload()
    deploy_sha = str(payload["deploy_sha"])

    def fake_http_get(url: str, headers: dict[str, str], timeout_seconds: float) -> object:
        del headers, timeout_seconds
        assert url.endswith("/api/v1/deployment/metadata")
        return module.HttpResponse(
            status=200,
            url=url,
            content=json.dumps(payload).encode(),
            headers={"content-type": "application/json"},
        )

    details = module._check_deployment_metadata(
        "https://audit.lute-tlz-dddd.top",
        timeout_seconds=1,
        auth_headers={},
        expected_deploy_sha=deploy_sha.upper(),
        http_get=fake_http_get,
    )

    assert details["deploy_sha_matches_expected"] is True
    with pytest.raises(module.ReadOnlyProbeError, match="deploy_sha mismatch"):
        module._check_deployment_metadata(
            "https://audit.lute-tlz-dddd.top",
            timeout_seconds=1,
            auth_headers={},
            expected_deploy_sha="deadbeef",
            http_get=fake_http_get,
        )


def test_run_controlled_api_readonly_permission_smoke_script_is_valid_and_readonly() -> None:
    script_path = Path("scripts/run-controlled-api-readonly-permission-smoke.py")

    result = subprocess.run(
        ["python3", "-m", "py_compile", str(script_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    script_text = script_path.read_text(encoding="utf-8")
    assert "sk-" not in script_text
    assert '"GET"' in script_text
    assert '"POST"' not in script_text
    assert "production_side_effect" in script_text
    assert "database_write" in script_text
    assert "audit_log_write_expected" in script_text
    assert "provider_call_status" in script_text
    assert "X-Tenant-Id" in script_text
    assert "--allow-audit-log-writes" in script_text
    assert "--confirm-production-write" in script_text
    assert "body_preview" not in script_text
    assert "body_length" in script_text


def test_run_controlled_api_readonly_permission_smoke_builds_get_probes() -> None:
    module = _load_script_module(
        "run_controlled_api_readonly_permission_smoke_builds_get_probes",
        Path("scripts/run-controlled-api-readonly-permission-smoke.py"),
    )
    config = module.SmokeConfig(
        base_url="http://127.0.0.1:8021",
        api_prefix="",
        mode="enforce",
        protected_paths=("/auth/session", "/projects"),
        tenant_id="hospital-demo",
        project_key="SELF-CHECK-FUND-20260607",
        admin_role="admin",
        admin_user_id="permission-smoke-admin",
        api_key=None,
        api_key_env=None,
        timeout_seconds=1,
        json_output=None,
    )

    probes = module._build_probes(config)

    assert {probe.method for probe in probes} == {"GET"}
    assert [probe.kind for probe in probes] == [
        "public",
        "public",
    ]
    skipped = module._build_skipped_probes(config)
    assert len(skipped) == 6
    assert sum(
        item["reason"] == "audit-log-writes-not-authorized" for item in skipped
    ) == 4
    assert sum(item["reason"] == "endpoint-may-write-audit-log" for item in skipped) == 2


def test_run_controlled_api_readonly_permission_smoke_write_mode_builds_full_matrix() -> None:
    module = _load_script_module(
        "run_controlled_api_readonly_permission_smoke_write_mode_builds_full_matrix",
        Path("scripts/run-controlled-api-readonly-permission-smoke.py"),
    )
    config = module.SmokeConfig(
        base_url=module.PRODUCTION_BASE_URL,
        api_prefix="",
        mode="enforce",
        protected_paths=("/projects",),
        tenant_id="hospital-demo",
        project_key="SELF-CHECK-FUND-20260607",
        admin_role="admin",
        admin_user_id="permission-smoke-admin",
        api_key=None,
        api_key_env=None,
        timeout_seconds=1,
        json_output=None,
        allow_audit_log_writes=True,
        confirm_production_write="audit.lute-tlz-dddd.top",
    )

    probes = module._build_probes(config)

    assert [probe.kind for probe in probes] == [
        "public",
        "public",
        "protected-anonymous",
        "protected-missing-tenant",
        "protected-admin",
    ]
    assert module._build_skipped_probes(config) == []
    missing_tenant_probe = next(
        probe for probe in probes if probe.kind == "protected-missing-tenant"
    )
    assert "X-Tenant-Id" not in missing_tenant_probe.headers


def test_run_controlled_api_readonly_permission_smoke_enforce_fails_mismatch() -> None:
    module = _load_script_module(
        "run_controlled_api_readonly_permission_smoke_enforce_fails_mismatch",
        Path("scripts/run-controlled-api-readonly-permission-smoke.py"),
    )
    config = module.SmokeConfig(
        base_url=module.PRODUCTION_BASE_URL,
        api_prefix="",
        mode="enforce",
        protected_paths=("/projects",),
        tenant_id="hospital-demo",
        project_key="SELF-CHECK-FUND-20260607",
        admin_role="admin",
        admin_user_id="permission-smoke-admin",
        api_key=None,
        api_key_env=None,
        timeout_seconds=1,
        json_output=None,
        allow_audit_log_writes=True,
        confirm_production_write="audit.lute-tlz-dddd.top",
    )

    def fake_requester(probe: object, timeout_seconds: float) -> object:
        del timeout_seconds
        return module.HttpResponse(status=200, url=probe.url, text="{}")

    report = module.run_readonly_permission_smoke(config, requester=fake_requester)

    assert report["status"] == "fail"
    assert report["summary"]["issue_count"] == 2
    assert any("protected-anonymous:/projects" in item for item in report["issues"])
    assert any("protected-missing-tenant:/projects" in item for item in report["issues"])


def test_run_controlled_api_readonly_permission_smoke_observe_records_observations() -> None:
    module = _load_script_module(
        "run_controlled_api_readonly_permission_smoke_observe_records_observations",
        Path("scripts/run-controlled-api-readonly-permission-smoke.py"),
    )
    config = module.SmokeConfig(
        base_url="https://audit.lute-tlz-dddd.top",
        api_prefix="/api/v1",
        mode="observe",
        protected_paths=("/projects",),
        tenant_id="hospital-demo",
        project_key="SELF-CHECK-FUND-20260607",
        admin_role="admin",
        admin_user_id="permission-smoke-admin",
        api_key=None,
        api_key_env=None,
        timeout_seconds=1,
        json_output=None,
        allow_audit_log_writes=True,
        confirm_production_write="audit.lute-tlz-dddd.top",
    )

    def fake_requester(probe: object, timeout_seconds: float) -> object:
        del timeout_seconds
        return module.HttpResponse(status=200, url=probe.url, text="{}")

    report = module.run_readonly_permission_smoke(config, requester=fake_requester)

    assert report["status"] == "observed"
    assert report["issues"] == []
    assert report["summary"]["observation_count"] == 2
    assert report["side_effect_mode"] == "audit-log-write-enabled"
    assert report["production_side_effect"] == "audit-log-only"
    assert report["database_write"] == "audit-log-only"
    assert report["audit_log_write_expected"] is True
    assert report["http_methods"] == ["GET"]


def test_run_controlled_api_readonly_permission_smoke_default_reports_limited_readonly() -> None:
    module = _load_script_module(
        "run_controlled_api_readonly_permission_smoke_default_reports_limited_readonly",
        Path("scripts/run-controlled-api-readonly-permission-smoke.py"),
    )
    config = module.SmokeConfig(
        base_url="https://audit.lute-tlz-dddd.top",
        api_prefix="/api/v1",
        mode="observe",
        protected_paths=module.DEFAULT_PROTECTED_PATHS,
        tenant_id="hospital-demo",
        project_key="SELF-CHECK-FUND-20260607",
        admin_role="admin",
        admin_user_id="permission-smoke-admin",
        api_key=None,
        api_key_env=None,
        timeout_seconds=1,
        json_output=None,
    )

    def fake_requester(probe: object, timeout_seconds: float) -> object:
        del timeout_seconds
        return module.HttpResponse(status=200, url=probe.url, text="{}")

    report = module.run_readonly_permission_smoke(config, requester=fake_requester)

    assert report["side_effect_mode"] == "readonly"
    assert report["production_side_effect"] == "none"
    assert report["database_write"] is False
    assert report["audit_log_write_expected"] is False
    assert report["summary"] == {
        "probe_count": 2,
        "executed_probe_count": 2,
        "skipped_probe_count": 33,
        "total_probe_count": 35,
        "issue_count": 0,
        "observation_count": 0,
    }
    assert len(report["executed_probes"]) == 2
    assert len(report["skipped_probes"]) == 33


@pytest.mark.parametrize(
    "base_url",
    (
        "http://127.0.0.1:8021",
        "https://audit.lute-tlz-dddd.top",
        "http://101.34.52.232:18080",
    ),
)
def test_run_controlled_api_readonly_permission_smoke_rejects_unconfirmed_write(
    base_url: str,
) -> None:
    module = _load_script_module(
        "run_controlled_api_readonly_permission_smoke_rejects_unconfirmed_production_write",
        Path("scripts/run-controlled-api-readonly-permission-smoke.py"),
    )
    config = module.SmokeConfig(
        base_url=base_url,
        api_prefix="/api/v1",
        mode="observe",
        protected_paths=("/projects",),
        tenant_id="hospital-demo",
        project_key="SELF-CHECK-FUND-20260607",
        admin_role="admin",
        admin_user_id="permission-smoke-admin",
        api_key=None,
        api_key_env=None,
        timeout_seconds=1,
        json_output=None,
        allow_audit_log_writes=True,
    )
    request_count = 0

    def fake_requester(probe: object, timeout_seconds: float) -> object:
        nonlocal request_count
        del probe, timeout_seconds
        request_count += 1
        raise AssertionError("requester must not run")

    with pytest.raises(module.PermissionSmokeConfigError, match="confirm-production-write"):
        module.run_readonly_permission_smoke(config, requester=fake_requester)

    assert request_count == 0


@pytest.mark.parametrize(
    "base_url",
    (
        "http://127.0.0.1:8021",
        "http://audit.lute-tlz-dddd.top",
        "https://audit.lute-tlz-dddd.top:444",
        "https://audit.lute-tlz-dddd.top/probe",
        "https://audit.lute-tlz-dddd.top?target=probe",
        "https://probe@audit.lute-tlz-dddd.top",
    ),
)
def test_run_controlled_api_readonly_permission_smoke_write_mode_requires_exact_origin(
    base_url: str,
) -> None:
    module = _load_script_module(
        "run_controlled_api_readonly_permission_smoke_write_mode_exact_origin",
        Path("scripts/run-controlled-api-readonly-permission-smoke.py"),
    )
    config = module.SmokeConfig(
        base_url=base_url,
        api_prefix="/api/v1",
        mode="observe",
        protected_paths=("/projects",),
        tenant_id="hospital-demo",
        project_key="SELF-CHECK-FUND-20260607",
        admin_role="admin",
        admin_user_id="permission-smoke-admin",
        api_key=None,
        api_key_env=None,
        timeout_seconds=1,
        json_output=None,
        allow_audit_log_writes=True,
        confirm_production_write=module.PRODUCTION_HOST,
    )

    with pytest.raises(module.PermissionSmokeConfigError, match="--base-url"):
        module.run_readonly_permission_smoke(config)


def test_run_controlled_api_readonly_permission_smoke_does_not_follow_redirects() -> None:
    module = _load_script_module(
        "run_controlled_api_readonly_permission_smoke_does_not_follow_redirects",
        Path("scripts/run-controlled-api-readonly-permission-smoke.py"),
    )
    target_hits = 0

    class TargetHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            nonlocal target_hits
            target_hits += 1
            self.send_response(200)
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:
            del format, args

    target_server = ThreadingHTTPServer(("127.0.0.1", 0), TargetHandler)
    target_thread = threading.Thread(target=target_server.serve_forever, daemon=True)
    target_thread.start()

    class RedirectHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            self.send_response(302)
            self.send_header(
                "Location",
                f"http://127.0.0.1:{target_server.server_port}/target",
            )
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:
            del format, args

    redirect_server = ThreadingHTTPServer(("127.0.0.1", 0), RedirectHandler)
    redirect_thread = threading.Thread(
        target=redirect_server.serve_forever,
        daemon=True,
    )
    redirect_thread.start()

    try:
        response = module._request_probe(
            module.Probe(
                name="redirect",
                path="/redirect",
                url=f"http://127.0.0.1:{redirect_server.server_port}/redirect",
                method="GET",
                headers={},
                expected_statuses=(302,),
                kind="public",
            ),
            1,
        )
    finally:
        redirect_server.shutdown()
        target_server.shutdown()
        redirect_thread.join(timeout=2)
        target_thread.join(timeout=2)
        redirect_server.server_close()
        target_server.server_close()

    assert response.status == 302
    assert target_hits == 0


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


def test_production_frontend_acceptance_rejects_unexpected_final_path() -> None:
    runner_path = Path("scripts/run-production-frontend-acceptance.mjs").resolve()
    program = (
        "import { classify } from " + json.dumps(runner_path.as_uri()) + "; "
        "const issues = classify("
        "{ status: 200, error: null, consoleErrors: [], failedRequests: [], "
        "interactionErrors: [], finalUrl: 'https://audit.example.test/medical-audit' }, "
        "{ route: '/remediation', expectedPath: '/remediation' }, "
        "{ bodyText: 'x'.repeat(120), headings: ['整改台账'], controlText: [], "
        "fileInputCount: 0, horizontalOverflow: false, scrollWidth: 100, "
        "clientWidth: 100, overflowOffenders: [] }); "
        "console.log(JSON.stringify(issues));"
    )
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", program],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert '"type":"unexpected-final-path"' in result.stdout


def test_production_frontend_acceptance_rejects_clipped_controls_and_occluding_floats() -> None:
    runner_path = Path("scripts/run-production-frontend-acceptance.mjs").resolve()
    program = (
        "import { classify } from " + json.dumps(runner_path.as_uri()) + "; "
        "const issues = classify("
        "{ status: 200, error: null, consoleErrors: [], failedRequests: [], "
        "interactionErrors: [], finalUrl: 'https://audit.example.test/medical-audit' }, "
        "{ route: '/medical-audit', expectedPath: '/medical-audit' }, "
        "{ bodyText: 'x'.repeat(120), headings: ['医保审计'], controlText: [], "
        "fileInputCount: 0, horizontalOverflow: false, scrollWidth: 390, "
        "clientWidth: 390, overflowOffenders: [], "
        "interactiveOverflowOffenders: [{ tag: 'button', "
        "rect: { left: 586, right: 682, width: 96 } }], "
        "floatingControlOcclusions: [{ floating: { tag: 'button' }, covered: { tag: 'a' } }] }); "
        "console.log(JSON.stringify(issues.map((item) => item.type).sort()));"
    )
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", program],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == [
        "floating-control-occlusion",
        "interactive-control-overflow",
    ]


def test_production_frontend_acceptance_only_audits_positioned_floating_markers() -> None:
    runner_path = Path("scripts/run-production-frontend-acceptance.mjs").resolve()
    program = (
        "import { isFloatingLayoutPosition } from "
        + json.dumps(runner_path.as_uri())
        + "; console.log(JSON.stringify(['static', 'relative', 'absolute', 'fixed', 'sticky']"
        ".map((value) => isFloatingLayoutPosition(value))));"
    )
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", program],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == [False, False, True, True, True]


def test_production_frontend_acceptance_rejects_unexpected_final_search() -> None:
    runner_path = Path("scripts/run-production-frontend-acceptance.mjs").resolve()
    program = (
        "import { classify } from " + json.dumps(runner_path.as_uri()) + "; "
        "const routeCheck = { route: '/knowledge-query', expectedPath: '/documents', "
        "expectedSearch: '?query=%E5%8C%BB%E4%BF%9D&source_collection=regulations"
        "&source_collection=personal-materials' }; "
        "const data = { bodyText: 'x'.repeat(120), headings: ['文档检索'], "
        "controlText: [], fileInputCount: 0, horizontalOverflow: false, "
        "scrollWidth: 100, clientWidth: 100, overflowOffenders: [] }; "
        "const hasSearchIssue = (finalUrl) => classify("
        "{ status: 200, error: null, consoleErrors: [], failedRequests: [], "
        "interactionErrors: [], finalUrl }, routeCheck, data)"
        ".some((item) => item.type === 'unexpected-final-search'); "
        "console.log(JSON.stringify({ "
        "good: hasSearchIssue('https://audit.example.test/documents"
        "?query=%E5%8C%BB%E4%BF%9D&source_collection=regulations"
        "&source_collection=personal-materials'), "
        "unknown: hasSearchIssue('https://audit.example.test/documents"
        "?query=%E5%8C%BB%E4%BF%9D&source_collection=regulations"
        "&source_collection=personal-materials&unknown=forwarded'), "
        "missingRepeated: hasSearchIssue('https://audit.example.test/documents"
        "?query=%E5%8C%BB%E4%BF%9D&source_collection=regulations') }));"
    )
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", program],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "good": False,
        "unknown": True,
        "missingRepeated": True,
    }


def test_production_frontend_acceptance_rejects_unexpected_chrome_title() -> None:
    runner_path = Path("scripts/run-production-frontend-acceptance.mjs").resolve()
    program = (
        "import { classify } from " + json.dumps(runner_path.as_uri()) + "; "
        "const routeCheck = { route: '/rules', expectedPath: '/rules', "
        "expectedChromeTitle: '规则运行工作台' }; "
        "const baseData = { bodyText: 'x'.repeat(120), headings: ['规则运行工作台'], "
        "controlText: [], fileInputCount: 0, horizontalOverflow: false, "
        "scrollWidth: 100, clientWidth: 100, overflowOffenders: [] }; "
        "const hasChromeIssue = (chromeTitle) => classify("
        "{ status: 200, error: null, consoleErrors: [], failedRequests: [], "
        "interactionErrors: [], finalUrl: 'https://audit.example.test/rules' }, "
        "routeCheck, { ...baseData, chromeTitle })"
        ".some((item) => item.type === 'unexpected-chrome-title'); "
        "console.log(JSON.stringify({ good: hasChromeIssue('规则运行工作台'), "
        "wrong: hasChromeIssue('AI 对话'), missing: hasChromeIssue(null) }));"
    )
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", program],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "good": False,
        "wrong": True,
        "missing": True,
    }


def test_production_frontend_acceptance_recognizes_current_login_gate() -> None:
    runner_path = Path("scripts/run-production-frontend-acceptance.mjs").resolve()
    program = (
        "import { isLoginGateSnapshot } from "
        + json.dumps(runner_path.as_uri())
        + "; "
        "console.log(JSON.stringify({ "
        "current: isLoginGateSnapshot({ headings: ['登录工作台'], submitControls: ['登录'] }), "
        "legacy: isLoginGateSnapshot({ headings: ['登录工作台'], submitControls: ['进入系统'] }), "
        "partial: isLoginGateSnapshot({ headings: ['登录工作台'], submitControls: [] }) }));"
    )
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", program],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "current": True,
        "legacy": False,
        "partial": False,
    }


def test_production_frontend_acceptance_binds_run_guard_and_release_identity(
    tmp_path: Path,
) -> None:
    runner_path = Path("scripts/run-production-frontend-acceptance.mjs").resolve()
    expected_sha = "a" * 40
    run_id = "fa-20260716t153000z-deadbeef"
    guard_path = tmp_path / "release-guard-s1.json"
    guard_path.write_text(
        json.dumps(_frontend_live_release_guard(expected_sha)),
        encoding="utf-8",
    )
    observation = {
        "public_manifest": {
            "http_status": 200,
            "content_type": "application/json",
            "format": "medical-audit-web-release-manifest-v1",
            "source_sha": expected_sha,
            "body_sha256": "b" * 64,
        },
        "deployment_metadata": {
            "http_status": 200,
            "content_type": "application/json",
            "status": "deployment_metadata_available",
            "deploy_sha_status": "set",
            "observed_deploy_sha": expected_sha,
            "deploy_sha_source": "default_file",
            "body_sha256": "c" * 64,
        },
    }
    program = (
        "import { deriveAcceptanceUserId, loadReleaseGuardEvidence, "
        "validateReleaseIdentityPair } from "
        + json.dumps(runner_path.as_uri())
        + "; "
        "const expectedSha = process.env.EXPECTED_SHA; "
        "const guard = loadReleaseGuardEvidence("
        "process.env.GUARD_PATH, expectedSha, process.env.RUN_ID); "
        "const observation = JSON.parse(process.env.OBSERVATION); "
        "const identity = validateReleaseIdentityPair("
        "observation, observation, expectedSha, `releases/${expectedSha}`); "
        "console.log(JSON.stringify({ userId: deriveAcceptanceUserId(process.env.RUN_ID), "
        "guard, identity }));"
    )
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", program],
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "EXPECTED_SHA": expected_sha,
            "RUN_ID": run_id,
            "GUARD_PATH": str(guard_path),
            "OBSERVATION": json.dumps(observation),
        },
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["userId"] == f"frontend-acceptance-{run_id}"
    assert payload["guard"]["report_path"] == str(guard_path)
    assert payload["guard"]["report_sha256"] == hashlib.sha256(
        guard_path.read_bytes()
    ).hexdigest()
    assert payload["guard"]["evidence_source"] == "release-guard-report:S1"
    assert (
        payload["guard"]["snapshot_id"]
        == _frontend_live_release_guard(expected_sha)["snapshot_id"]
    )
    assert payload["identity"]["stable"] is True
    assert payload["identity"]["current_release_target"] == f"releases/{expected_sha}"
    assert payload["guard"]["audit_attribution"] == {
        "acceptance_run_id": run_id,
        "audit_user_identifier": f"frontend-acceptance-{run_id}",
        "attributable_event_count": 0,
        "event_id_fingerprint": hashlib.sha256(b"").hexdigest(),
        "event_ids": [],
    }
    assert payload["identity"]["public_manifest"]["source_sha"] == expected_sha
    assert (
        payload["identity"]["deployment_metadata"]["observed_deploy_sha"]
        == expected_sha
    )
    assert (
        payload["identity"]["deployment_metadata"]["current_release_target_status"]
        == "not_exposed_by_endpoint"
    )

    tampered_guard = _frontend_live_release_guard(expected_sha)
    tampered_guard["schema_fingerprint"] = "f" * 64
    guard_path.write_text(json.dumps(tampered_guard), encoding="utf-8")
    tampered_result = subprocess.run(
        ["node", "--input-type=module", "--eval", program],
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "EXPECTED_SHA": expected_sha,
            "RUN_ID": run_id,
            "GUARD_PATH": str(guard_path),
            "OBSERVATION": json.dumps(observation),
        },
    )
    assert tampered_result.returncode != 0
    assert "complete L3 ssh-live-readonly S1 capture" in tampered_result.stderr

    wrong_run_guard = _frontend_live_release_guard(
        expected_sha,
        "fa-20260716t153001z-feedbeef",
    )
    guard_path.write_text(json.dumps(wrong_run_guard), encoding="utf-8")
    wrong_run_result = subprocess.run(
        ["node", "--input-type=module", "--eval", program],
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "EXPECTED_SHA": expected_sha,
            "RUN_ID": run_id,
            "GUARD_PATH": str(guard_path),
            "OBSERVATION": json.dumps(observation),
        },
    )
    assert wrong_run_result.returncode != 0
    assert "complete L3 ssh-live-readonly S1 capture" in wrong_run_result.stderr

    invalid_guard = _frontend_live_release_guard(expected_sha)
    invalid_guard.pop("current_release_target")
    guard_path.write_text(json.dumps(invalid_guard), encoding="utf-8")
    invalid_result = subprocess.run(
        ["node", "--input-type=module", "--eval", program],
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "EXPECTED_SHA": expected_sha,
            "RUN_ID": run_id,
            "GUARD_PATH": str(guard_path),
            "OBSERVATION": json.dumps(observation),
        },
    )
    assert invalid_result.returncode != 0
    assert "complete L3 ssh-live-readonly S1 capture" in invalid_result.stderr

    fixture_guard = _frontend_live_release_guard(expected_sha)
    fixture_guard["evidence_grade"] = "L2-fixture-or-dry-run"
    fixture_guard["source"] = "fixture"
    guard_path.write_text(json.dumps(fixture_guard), encoding="utf-8")
    fixture_result = subprocess.run(
        ["node", "--input-type=module", "--eval", program],
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "EXPECTED_SHA": expected_sha,
            "RUN_ID": run_id,
            "GUARD_PATH": str(guard_path),
            "OBSERVATION": json.dumps(observation),
        },
    )
    assert fixture_result.returncode != 0
    assert "complete L3 ssh-live-readonly S1 capture" in fixture_result.stderr


def test_production_frontend_acceptance_permission_probes_keep_run_attribution() -> None:
    runner_path = Path("scripts/run-production-frontend-acceptance.mjs").resolve()
    run_id = "fa-20260716t153000z-deadbeef"
    user_id = f"frontend-acceptance-{run_id}"
    program = (
        "import { buildAuditPermissionProbeHeaders } from "
        + json.dumps(runner_path.as_uri())
        + "; "
        "console.log(JSON.stringify(buildAuditPermissionProbeHeaders({ "
        f"adminRole: 'it-admin', adminApiKey: null, adminUserId: {json.dumps(user_id)} "
        "})));"
    )
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", program],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    headers = json.loads(result.stdout)
    assert headers["anonymous"] == {
        "Accept": "application/json",
        "X-User-Id": user_id,
    }
    assert "X-Role" not in headers["anonymous"]
    assert headers["missingTenant"]["X-User-Id"] == user_id
    assert "X-Tenant-Id" not in headers["missingTenant"]
    assert headers["allowed"]["X-User-Id"] == user_id
    assert headers["allowed"]["X-Tenant-Id"] == "hospital-demo"


def test_production_frontend_acceptance_separates_independent_pages_and_aliases() -> None:
    runner_path = Path("scripts/run-production-frontend-acceptance.mjs").resolve()
    program = (
        "import { aliasRouteChecks, routeCheckProfiles } from "
        + json.dumps(runner_path.as_uri())
        + "; "
        "const project = (item) => ({ route: item.route, "
        "inputSearch: item.inputSearch ?? '', expectedPath: item.expectedPath, "
        "expectedSearch: item.expectedSearch ?? '', session: item.session }); "
        "console.log(JSON.stringify({ independent: routeCheckProfiles.hardened.map(project), "
        "aliases: aliasRouteChecks.map(project), "
        "loginRequiredText: routeCheckProfiles.hardened[0].requiredText.map(String), "
        "loginRequiredControlText: "
        "routeCheckProfiles.hardened[0].requiredControlText.map(String), "
        "chromeTitles: Object.fromEntries(routeCheckProfiles.hardened"
        ".filter((item) => item.expectedChromeTitle)"
        ".map((item) => [item.route, item.expectedChromeTitle])) }));"
    )
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", program],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert [item["route"] for item in payload["independent"]] == [
        "/login",
        "/medical-audit",
        "/fund-compliance",
        "/fund-compliance/review",
        "/chat",
        "/agents",
        "/agent-market",
        "/analytics",
        "/projects",
        "/documents",
        "/knowledge-base",
        "/graph",
        "/rules",
        "/reports",
        "/remediation",
        "/archive",
        "/guided-check",
    ]
    assert [item["expectedPath"] for item in payload["independent"]] == [
        item["route"] for item in payload["independent"]
    ]
    assert payload["independent"][0]["session"] == "anonymous"
    assert all(
        item["session"] == "workspace" for item in payload["independent"][1:]
    )
    assert payload["loginRequiredText"] == ["/登录工作台/"]
    assert payload["loginRequiredControlText"] == ["/(^|\\s)登录($|\\s)/"]
    assert payload["chromeTitles"] == {
        "/fund-compliance": "医保基金使用合规",
        "/fund-compliance/review": "医保基金复核表单",
        "/rules": "规则运行工作台",
        "/remediation": "整改工作台",
        "/archive": "归档工作台",
        "/guided-check": "引导式核查",
    }
    assert payload["aliases"] == [
        {
            "route": "/workspace",
            "inputSearch": "",
            "expectedPath": "/chat",
            "expectedSearch": "",
            "session": "workspace",
        },
        {
            "route": "/findings",
            "inputSearch": "",
            "expectedPath": "/medical-audit",
            "expectedSearch": "",
            "session": "workspace",
        },
        {
            "route": "/knowledge-query",
            "inputSearch": (
                "?q=%E5%8C%BB%E4%BF%9D%E6%94%AF%E4%BB%98"
                "&source_collection=medical-insurance-laws&unknown=discard"
                "&source_collection=personal-materials"
            ),
            "expectedPath": "/documents",
            "expectedSearch": (
                "?query=%E5%8C%BB%E4%BF%9D%E6%94%AF%E4%BB%98"
                "&source_collection=medical-insurance-laws"
                "&source_collection=personal-materials"
            ),
            "session": "workspace",
        },
    ]


def test_production_frontend_acceptance_anonymous_context_omits_acceptance_headers() -> None:
    runner_path = Path("scripts/run-production-frontend-acceptance.mjs").resolve()
    program = (
        "import { buildBrowserContextOptions } from "
        + json.dumps(runner_path.as_uri())
        + "; "
        "const viewport = { width: 390, height: 900 }; "
        "const headers = { 'X-Role': 'it-admin', 'X-Tenant-Id': 'hospital-demo' }; "
        "console.log(JSON.stringify({ "
        "anonymous: buildBrowserContextOptions(viewport, 'anonymous', headers), "
        "workspace: buildBrowserContextOptions(viewport, 'workspace', headers) }));"
    )
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", program],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["anonymous"] == {"viewport": {"width": 390, "height": 900}}
    assert payload["workspace"] == {
        "viewport": {"width": 390, "height": 900},
        "extraHTTPHeaders": {
            "X-Role": "it-admin",
            "X-Tenant-Id": "hospital-demo",
        },
    }


@pytest.mark.parametrize(
    "script_name",
    ("run-production-frontend-acceptance.mjs",),
)
def test_production_frontend_acceptance_rejects_invalid_screenshot_policy_before_browser(
    script_name: str,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "acceptance.json"
    screenshot_dir = tmp_path / "screenshots"
    result = subprocess.run(
        [
            "node",
            f"scripts/{script_name}",
            "--allow-audit-log-writes",
            "--confirm-production-write",
            "audit.lute-tlz-dddd.top",
            "--base-url",
            "https://audit.lute-tlz-dddd.top",
            "--output",
            str(output_path),
            "--screenshot-dir",
            str(screenshot_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "MEDICAL_AUDIT_FRONTEND_ACCEPTANCE_SCREENSHOTS": "1",
            "MEDICAL_AUDIT_FRONTEND_ACCEPTANCE_SCREENSHOT_POLICY": "sometimes",
        },
    )

    assert result.returncode == 2
    assert "SCREENSHOT_POLICY must be one of: all, issues" in result.stderr
    assert not output_path.exists()
    assert not screenshot_dir.exists()


def test_production_frontend_acceptance_contract_tracks_live_workbenches() -> None:
    script_text = Path("scripts/run-production-frontend-acceptance.mjs").read_text(
        encoding="utf-8"
    )
    gate_text = Path("scripts/run-production-frontend-acceptance-gate.mjs").read_text(
        encoding="utf-8"
    )

    assert script_text.count("/表格分析工作台/") == 2
    assert script_text.count("/上传表格|分析历史/") == 2
    assert script_text.count("/审计底稿与报告台账/") == 2
    assert script_text.count("/六类模板目录/") == 2
    assert "/项目协作工作台/" in script_text
    assert "/可见项目/" in script_text
    assert "/内测中|待开通/" not in script_text
    for contract_text in (script_text, gate_text):
        assert "--allow-audit-log-writes" in contract_text
        assert "--confirm-production-write" in contract_text
        assert "audit-log-write-enabled" in contract_text
        assert "audit-log-only" in contract_text
    assert "anonymous_body_length" in script_text
    assert "missing_tenant_body_length" in script_text
    assert "allowed_body_length" in script_text
    assert 'screenshotPolicy === "all"' in script_text
    assert 'MEDICAL_AUDIT_FRONTEND_ACCEPTANCE_SCREENSHOTS: "1"' in gate_text
    assert 'MEDICAL_AUDIT_FRONTEND_ACCEPTANCE_SCREENSHOT_POLICY: "all"' in gate_text
    assert "frontend-acceptance-admin" not in script_text
    for report_field in (
        "independent_page_count",
        "alias_check_count",
        "alias_execution_check_count",
        "total_execution_check_count",
        "alias_checks",
        "inputSearch",
        "expectedPath",
        "finalPath",
        "expectedSearch",
        "finalSearch",
    ):
        assert report_field in script_text
        assert report_field in gate_text


@pytest.mark.parametrize(
    "script_name",
    (
        "run-production-frontend-acceptance.mjs",
        "run-production-frontend-acceptance-gate.mjs",
    ),
)
def test_production_frontend_acceptance_fails_closed_before_local_side_effects(
    script_name: str,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "acceptance.json"
    screenshot_dir = tmp_path / "screenshots"

    result = subprocess.run(
        [
            "node",
            f"scripts/{script_name}",
            "--base-url",
            "http://127.0.0.1:9",
            "--output",
            str(output_path),
            "--screenshot-dir",
            str(screenshot_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "fails closed by default" in result.stderr
    assert not output_path.exists()
    assert not screenshot_dir.exists()


@pytest.mark.parametrize(
    "script_name",
    (
        "run-production-frontend-acceptance.mjs",
        "run-production-frontend-acceptance-gate.mjs",
    ),
)
@pytest.mark.parametrize(
    "base_url",
    (
        "http://127.0.0.1:8021",
        "https://audit.lute-tlz-dddd.top",
        "http://101.34.52.232:18080",
    ),
)
def test_production_frontend_acceptance_requires_exact_write_confirmation(
    script_name: str,
    base_url: str,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "acceptance.json"
    screenshot_dir = tmp_path / "screenshots"

    result = subprocess.run(
        [
            "node",
            f"scripts/{script_name}",
            "--allow-audit-log-writes",
            "--base-url",
            base_url,
            "--output",
            str(output_path),
            "--screenshot-dir",
            str(screenshot_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "Audit-log writes require" in result.stderr
    assert not output_path.exists()
    assert not screenshot_dir.exists()


@pytest.mark.parametrize(
    "script_name",
    (
        "run-production-frontend-acceptance.mjs",
        "run-production-frontend-acceptance-gate.mjs",
    ),
)
def test_production_frontend_acceptance_binds_exact_production_origin(
    script_name: str,
) -> None:
    script_path = Path(f"scripts/{script_name}").resolve()
    candidates = [
        "https://audit.lute-tlz-dddd.top",
        "https://audit.lute-tlz-dddd.top:443",
        "http://audit.lute-tlz-dddd.top",
        "https://staging.example.test",
        "https://audit.lute-tlz-dddd.top:444",
        "https://user@audit.lute-tlz-dddd.top",
        "https://audit.lute-tlz-dddd.top/path",
        "https://audit.lute-tlz-dddd.top?query=1",
        "https://audit.lute-tlz-dddd.top#fragment",
    ]
    program = (
        "import { validateSideEffectAuthorization } from "
        + json.dumps(script_path.as_uri())
        + "; const values = JSON.parse(process.env.CANDIDATES); "
        "const results = values.map((baseUrl) => { try { return { baseUrl, accepted: true, "
        "normalized: validateSideEffectAuthorization({ baseUrl, allowAuditLogWrites: true, "
        "confirmProductionWrite: 'audit.lute-tlz-dddd.top' }) }; } catch (error) { "
        "return { baseUrl, accepted: false, error: String(error.message ?? error) }; } }); "
        "console.log(JSON.stringify(results));"
    )
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", program],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "CANDIDATES": json.dumps(candidates)},
    )

    assert result.returncode == 0, result.stderr
    observed = {item["baseUrl"]: item for item in json.loads(result.stdout)}
    for value in candidates[:2]:
        assert observed[value] == {
            "baseUrl": value,
            "accepted": True,
            "normalized": "https://audit.lute-tlz-dddd.top",
        }
    for value in candidates[2:]:
        assert observed[value]["accepted"] is False
        assert "exact production origin" in observed[value]["error"]


def test_production_frontend_acceptance_gate_rejects_inconsistent_report(
    tmp_path: Path,
) -> None:
    gate_path = Path("scripts/run-production-frontend-acceptance-gate.mjs").resolve()
    runner_path = Path("scripts/run-production-frontend-acceptance.mjs").resolve()
    expected_sha = "a" * 40
    run_id = "fa-20260716t153000z-deadbeef"
    desktop_png_path = tmp_path / "desktop-template.png"
    mobile_png_path = tmp_path / "mobile-template.png"
    screenshot_dir = tmp_path / "screenshots"
    screenshot_dir.mkdir()
    desktop_png_path.write_bytes(_rgba_png_bytes(1440, 1100))
    mobile_png_path.write_bytes(_rgba_png_bytes(390, 900))
    api_check = {
        "execution_status": "executed",
        "anonymous_check": "executed",
        "missing_tenant_check": "executed",
        "allowed_check": "executed",
        "anonymous_attribution_user_id": f"frontend-acceptance-{run_id}",
        "anonymous_status": 403,
        "missing_tenant_status": 401,
        "allowed_status": 200,
    }
    report = {
        "status": "pass",
        "base_url": "https://audit.lute-tlz-dddd.top/",
        "contract_profile": "hardened",
        "side_effect_mode": "audit-log-write-enabled",
        "production_side_effect": "audit-log-only",
        "database_write": "audit-log-only",
        "audit_log_write_expected": True,
        "provider_call_status": "not_observed",
        "provider_evidence_source": "outside-frontend-acceptance-scope",
        "collector_provider_call_status": "not_called",
        "expected_deploy_sha": expected_sha,
        "acceptance_run_id": run_id,
        "acceptance_user_id": f"frontend-acceptance-{run_id}",
        "release_guard": {
            **_frontend_live_release_guard(expected_sha),
            "report_path": str(tmp_path / "release-guard-s1.json"),
            "report_sha256": "d" * 64,
            "evidence_source": "release-guard-report:S1",
        },
        "release_identity": {
            "stable": True,
            "expected_deploy_sha": expected_sha,
            "current_release_target": f"releases/{expected_sha}",
            "current_release_target_source": "release-guard-report:S1",
            "public_manifest": {
                "path": "/release-manifest.json",
                "format": "medical-audit-web-release-manifest-v1",
                "source_sha": expected_sha,
                "body_sha256": "b" * 64,
                "initial_body_sha256": "b" * 64,
                "final_body_sha256": "b" * 64,
            },
            "deployment_metadata": {
                "path": "/api/v1/deployment/metadata",
                "status": "deployment_metadata_available",
                "deploy_sha_status": "set",
                "observed_deploy_sha": expected_sha,
                "deploy_sha_source": "default_file",
                "initial_body_sha256": "c" * 64,
                "final_body_sha256": "c" * 64,
                "current_release_target": None,
                "current_release_target_status": "not_exposed_by_endpoint",
            },
        },
        "summary": {
            "route_count": 0,
            "independent_page_count": 0,
            "alias_check_count": 0,
            "check_count": 0,
            "alias_execution_check_count": 0,
            "total_execution_check_count": 0,
            "viewports": [],
            "screenshot_capture": True,
            "screenshot_policy": "all",
            "p0": [],
            "p1": [],
            "api_checks": {
                "/audit/logs": dict(api_check),
                "/audit/logs/export": dict(api_check),
            },
            "executed_api_probes": [
                "/audit/logs:anonymous",
                "/audit/logs:missing-tenant",
                "/audit/logs:allowed",
                "/audit/logs/export:anonymous",
                "/audit/logs/export:missing-tenant",
                "/audit/logs/export:allowed",
            ],
            "executed_api_probe_count": 6,
            "skipped_api_probes": [],
            "skipped_api_probe_count": 0,
            "skipped_routes": [],
            "skipped_route_count": 0,
        },
        "checks": [],
        "alias_checks": [],
    }
    node_program = (
        f"import {{ assertGate }} from {json.dumps(gate_path.as_uri())}; "
        "import fs from 'node:fs'; import path from 'node:path'; "
        "import { aliasRouteChecks, readPngEvidence, routeCheckProfiles, "
        "screenshotFileName, viewports } from "
        f"{json.dumps(runner_path.as_uri())}; "
        "const report = JSON.parse(process.env.REPORT); "
        "const routes = routeCheckProfiles[report.contract_profile]; "
        "const aliases = report.contract_profile === 'hardened' ? aliasRouteChecks : []; "
        "const viewportNames = viewports.map((item) => item.name); "
        "report.summary.route_count = routes.length; "
        "report.summary.independent_page_count = routes.length; "
        "report.summary.alias_check_count = aliases.length; "
        "report.summary.viewports = viewportNames; "
        "const makeCheck = (contract, viewport, contractKind) => { "
        f"const screenshot = path.join({json.dumps(str(screenshot_dir))}, screenshotFileName({{ "
        "acceptanceRunId: report.acceptance_run_id, contractKind, viewport, "
        "route: contract.route, inputSearch: contract.inputSearch ?? '' })); "
        f"fs.copyFileSync(viewport === 'desktop' ? {json.dumps(str(desktop_png_path))} : "
        f"{json.dumps(str(mobile_png_path))}, screenshot); "
        "return ({ route: contract.route, viewport, "
        "inputSearch: contract.inputSearch ?? '', "
        "expectedPath: contract.expectedPath, finalPath: contract.expectedPath, "
        "expectedSearch: contract.expectedSearch ?? '', "
        "finalSearch: contract.expectedSearch ?? '', "
        "expectedChromeTitle: contract.expectedChromeTitle ?? null, "
        "chromeTitle: contract.expectedChromeTitle ?? null, "
        "finalUrl: `https://audit.example.test${contract.expectedPath}`, status: 200, "
        "navigationError: false, headingCount: 1, bodyTextLength: 100, "
        "fileInputCount: 0, scrollWidth: 100, clientWidth: 100, "
        "horizontalOverflow: false, overflowOffenders: [], consoleErrorCount: 0, "
        "failedRequestCount: 0, failedRequests: [], interactionErrorCount: 0, "
        "screenshot, screenshot_evidence: readPngEvidence(screenshot), "
        "issues: [] }); }; "
        "report.checks = routes.flatMap((contract) => "
        "viewportNames.map((viewport) => makeCheck(contract, viewport, 'independent'))); "
        "report.alias_checks = aliases.flatMap((contract) => "
        "viewportNames.map((viewport) => makeCheck(contract, viewport, 'alias'))); "
        "report.summary.check_count = report.checks.length; "
        "report.summary.alias_execution_check_count = report.alias_checks.length; "
        "report.summary.total_execution_check_count = "
        "report.checks.length + report.alias_checks.length; "
        "if (process.env.MUTATE_ROUTE === '1') report.checks[0].route = '/fake-route'; "
        "if (process.env.MUTATE_FINAL_PATH === '1') report.checks[0].finalPath = '/wrong'; "
        "if (process.env.MUTATE_FINAL_URL === '1') "
        "report.checks[0].finalUrl = 'https://audit.example.test/wrong'; "
        "if (process.env.MUTATE_CHROME_TITLE === '1') "
        "report.checks.find((check) => check.expectedChromeTitle).chromeTitle = 'AI 对话'; "
        "if (process.env.MUTATE_ALIAS_FINAL_URL === '1') "
        "report.alias_checks[0].finalUrl = 'not-a-valid-url'; "
        "if (process.env.MUTATE_ALIAS_FINAL_SEARCH === '1') "
        "report.alias_checks.find((check) => check.route === '/knowledge-query').finalSearch = "
        "'?query=%E5%8C%BB%E4%BF%9D%E6%94%AF%E4%BB%98&unknown=forwarded'; "
        "if (process.env.DROP_REPEATED_ALIAS_SEARCH === '1') "
        "report.alias_checks.find((check) => check.route === '/knowledge-query').finalSearch = "
        "'?query=%E5%8C%BB%E4%BF%9D%E6%94%AF%E4%BB%98"
        "&source_collection=medical-insurance-laws'; "
        "if (process.env.DROP_ALIAS === '1') report.alias_checks.pop(); "
        "if (process.env.DROP_SCREENSHOT === '1') delete report.checks[0].screenshot; "
        "if (process.env.SCREENSHOT_PATH) { "
        "report.checks.forEach((check) => { check.screenshot = process.env.SCREENSHOT_PATH; "
        "check.screenshot_evidence = readPngEvidence(process.env.SCREENSHOT_PATH); }); } "
        "if (process.env.MUTATE_GUARD_TRANSACTION === '1') "
        "report.release_guard.transaction_read_only = false; "
        "if (process.env.MUTATE_GUARD_EVIDENCE_GRADE === '1') "
        "report.release_guard.evidence_grade = 'L2-fixture-or-dry-run'; "
        "if (process.env.MUTATE_GUARD_PROVIDER_BOUNDARY === '1') "
        "delete report.release_guard.collector_execution_boundary; "
        "if (process.env.MUTATE_ACCEPTANCE_USER === '1') "
        "report.acceptance_user_id = 'frontend-acceptance-wrong'; "
        "if (process.env.REUSE_SCREENSHOTS === '1') { "
        "const first = report.checks[0]; "
        "[...report.checks, ...report.alias_checks].forEach((check) => { "
        "check.screenshot = first.screenshot; "
        "check.screenshot_evidence = first.screenshot_evidence; "
        "}); } "
        "if (process.env.MUTATE_MANIFEST_SHA === '1') "
        "report.release_identity.public_manifest.source_sha = 'f'.repeat(40); "
        "if (process.env.DROP_RESULTS === '1') { "
        "delete report.checks[0].status; delete report.checks[0].issues; } "
        "assertGate(report);"
    )

    valid_result = subprocess.run(
        ["node", "--input-type=module", "--eval", node_program],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "REPORT": json.dumps(report)},
    )
    assert valid_result.returncode == 0, valid_result.stderr

    report["database_write"] = False
    invalid_result = subprocess.run(
        ["node", "--input-type=module", "--eval", node_program],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "REPORT": json.dumps(report)},
    )
    assert invalid_result.returncode == 2
    assert "frontend acceptance side-effect contract is inconsistent" in invalid_result.stderr

    report["database_write"] = "audit-log-only"
    invalid_guard_result = subprocess.run(
        ["node", "--input-type=module", "--eval", node_program],
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "REPORT": json.dumps(report),
            "MUTATE_GUARD_TRANSACTION": "1",
        },
    )
    assert invalid_guard_result.returncode == 2
    assert "frontend acceptance release guard evidence is inconsistent" in (
        invalid_guard_result.stderr
    )

    for mutation in ("MUTATE_GUARD_EVIDENCE_GRADE", "MUTATE_GUARD_PROVIDER_BOUNDARY"):
        invalid_guard_contract = subprocess.run(
            ["node", "--input-type=module", "--eval", node_program],
            check=False,
            capture_output=True,
            text=True,
            env={**os.environ, "REPORT": json.dumps(report), mutation: "1"},
        )
        assert invalid_guard_contract.returncode == 2
        assert "frontend acceptance release guard evidence is inconsistent" in (
            invalid_guard_contract.stderr
        )

    invalid_user_result = subprocess.run(
        ["node", "--input-type=module", "--eval", node_program],
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "REPORT": json.dumps(report),
            "MUTATE_ACCEPTANCE_USER": "1",
        },
    )
    assert invalid_user_result.returncode == 2
    assert "frontend acceptance run identity is inconsistent" in invalid_user_result.stderr

    reused_screenshot_result = subprocess.run(
        ["node", "--input-type=module", "--eval", node_program],
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "REPORT": json.dumps(report),
            "REUSE_SCREENSHOTS": "1",
        },
    )
    assert reused_screenshot_result.returncode == 2
    assert "frontend acceptance route check evidence is incomplete" in (
        reused_screenshot_result.stderr
    )

    invalid_manifest_result = subprocess.run(
        ["node", "--input-type=module", "--eval", node_program],
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "REPORT": json.dumps(report),
            "MUTATE_MANIFEST_SHA": "1",
        },
    )
    assert invalid_manifest_result.returncode == 2
    assert "frontend acceptance release identity evidence is inconsistent" in (
        invalid_manifest_result.stderr
    )

    route_invalid_result = subprocess.run(
        ["node", "--input-type=module", "--eval", node_program],
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "REPORT": json.dumps(report),
            "MUTATE_ROUTE": "1",
        },
    )
    assert route_invalid_result.returncode == 2
    assert "frontend acceptance route check evidence is incomplete" in (
        route_invalid_result.stderr
    )

    incomplete_result = subprocess.run(
        ["node", "--input-type=module", "--eval", node_program],
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "REPORT": json.dumps(report),
            "DROP_RESULTS": "1",
        },
    )
    assert incomplete_result.returncode == 2
    assert "frontend acceptance route check evidence is incomplete" in (
        incomplete_result.stderr
    )

    wrong_path_result = subprocess.run(
        ["node", "--input-type=module", "--eval", node_program],
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "REPORT": json.dumps(report),
            "MUTATE_FINAL_PATH": "1",
        },
    )
    assert wrong_path_result.returncode == 2
    assert "frontend acceptance route check evidence is incomplete" in (
        wrong_path_result.stderr
    )

    wrong_url_result = subprocess.run(
        ["node", "--input-type=module", "--eval", node_program],
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "REPORT": json.dumps(report),
            "MUTATE_FINAL_URL": "1",
        },
    )
    assert wrong_url_result.returncode == 2
    assert "frontend acceptance route check evidence is incomplete" in (
        wrong_url_result.stderr
    )

    wrong_chrome_title_result = subprocess.run(
        ["node", "--input-type=module", "--eval", node_program],
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "REPORT": json.dumps(report),
            "MUTATE_CHROME_TITLE": "1",
        },
    )
    assert wrong_chrome_title_result.returncode == 2
    assert "frontend acceptance route check evidence is incomplete" in (
        wrong_chrome_title_result.stderr
    )

    wrong_alias_url_result = subprocess.run(
        ["node", "--input-type=module", "--eval", node_program],
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "REPORT": json.dumps(report),
            "MUTATE_ALIAS_FINAL_URL": "1",
        },
    )
    assert wrong_alias_url_result.returncode == 2
    assert "frontend acceptance alias check evidence is incomplete" in (
        wrong_alias_url_result.stderr
    )

    wrong_alias_search_result = subprocess.run(
        ["node", "--input-type=module", "--eval", node_program],
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "REPORT": json.dumps(report),
            "MUTATE_ALIAS_FINAL_SEARCH": "1",
        },
    )
    assert wrong_alias_search_result.returncode == 2
    assert "frontend acceptance alias check evidence is incomplete" in (
        wrong_alias_search_result.stderr
    )

    missing_repeated_alias_search_result = subprocess.run(
        ["node", "--input-type=module", "--eval", node_program],
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "REPORT": json.dumps(report),
            "DROP_REPEATED_ALIAS_SEARCH": "1",
        },
    )
    assert missing_repeated_alias_search_result.returncode == 2
    assert "frontend acceptance alias check evidence is incomplete" in (
        missing_repeated_alias_search_result.stderr
    )

    missing_alias_result = subprocess.run(
        ["node", "--input-type=module", "--eval", node_program],
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "REPORT": json.dumps(report),
            "DROP_ALIAS": "1",
        },
    )
    assert missing_alias_result.returncode == 2
    assert "frontend acceptance alias coverage is incomplete" in (
        missing_alias_result.stderr
    )

    missing_screenshot_result = subprocess.run(
        ["node", "--input-type=module", "--eval", node_program],
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "REPORT": json.dumps(report),
            "DROP_SCREENSHOT": "1",
        },
    )
    assert missing_screenshot_result.returncode == 2
    assert "frontend acceptance route check evidence is incomplete" in (
        missing_screenshot_result.stderr
    )

    nonexistent_screenshot_result = subprocess.run(
        ["node", "--input-type=module", "--eval", node_program],
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "REPORT": json.dumps(report),
            "SCREENSHOT_PATH": str(tmp_path / "missing.png"),
        },
    )
    assert nonexistent_screenshot_result.returncode == 2
    assert "frontend acceptance route check evidence is incomplete" in (
        nonexistent_screenshot_result.stderr
    )

    non_png_path = tmp_path / "not-a-png.png"
    non_png_path.write_bytes(b"not a png")
    non_png_screenshot_result = subprocess.run(
        ["node", "--input-type=module", "--eval", node_program],
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "REPORT": json.dumps(report),
            "SCREENSHOT_PATH": str(non_png_path),
        },
    )
    assert non_png_screenshot_result.returncode == 2
    assert "frontend acceptance route check evidence is incomplete" in (
        non_png_screenshot_result.stderr
    )

    truncated_png_path = tmp_path / "truncated.png"
    truncated_png_path.write_bytes(bytes.fromhex("89504e470d0a1a0a"))
    truncated_png_screenshot_result = subprocess.run(
        ["node", "--input-type=module", "--eval", node_program],
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "REPORT": json.dumps(report),
            "SCREENSHOT_PATH": str(truncated_png_path),
        },
    )
    assert truncated_png_screenshot_result.returncode == 2
    assert "frontend acceptance route check evidence is incomplete" in (
        truncated_png_screenshot_result.stderr
    )

    valid_screenshot_result = subprocess.run(
        ["node", "--input-type=module", "--eval", node_program],
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "REPORT": json.dumps(report),
        },
    )
    assert valid_screenshot_result.returncode == 0, valid_screenshot_result.stderr


def test_production_frontend_acceptance_report_sanitizers_remove_sensitive_text() -> None:
    runner_path = Path("scripts/run-production-frontend-acceptance.mjs").resolve()
    sentinel = "patient-li-ACCESS_TOKEN_123"
    node_program = (
        "import { classify, sanitizeFailedRequest, sanitizeUrl } from "
        f"{json.dumps(runner_path.as_uri())}; "
        f"const sentinel = {json.dumps(sentinel)}; "
        "const failed = { "
        "url: `https://audit.example.test/api/items?token=${sentinel}#record`, "
        "error: sentinel }; "
        "const issues = classify("
        "{ status: 200, error: null, consoleErrors: [sentinel], "
        "failedRequests: [failed], interactionErrors: [sentinel] }, "
        "{}, "
        "{ bodyText: 'x'.repeat(100), headings: ['heading'], controlText: [], fileInputCount: 0, "
        "horizontalOverflow: false, scrollWidth: 100, clientWidth: 100, overflowOffenders: [] }"
        "); "
        "console.log(JSON.stringify({ url: sanitizeUrl(failed.url), "
        "failed: sanitizeFailedRequest(failed), issues }));"
    )

    result = subprocess.run(
        ["node", "--input-type=module", "--eval", node_program],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert sentinel not in result.stdout
    payload = json.loads(result.stdout)
    assert payload["url"] == "https://audit.example.test/api/items"
    assert payload["failed"] == {
        "url": "https://audit.example.test/api/items",
        "error": "request-failed",
    }
    script_text = Path("scripts/run-production-frontend-acceptance.mjs").read_text(
        encoding="utf-8"
    )
    assert "bodySample" not in script_text
    assert "headings: data.headings" not in script_text
    assert 'route.request().method() !== "GET"' in script_text
    assert 'redirect: "manual"' in script_text


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
    assert "/knowledge-base/catalog" in script_text
    assert "/index/search-backend" not in script_text
    assert "default_transaction_read_only=on" in script_text
    assert "audit_log_events" in script_text
    assert "deployment-state-auditor-" in script_text


def test_audit_tencent_cloud_deployment_state_remote_code_is_valid_and_blocks_redirects() -> None:
    module = _load_script_module(
        "audit_tencent_cloud_deployment_state_remote_code",
        Path("scripts/audit-tencent-cloud-deployment-state.py"),
    )

    remote_code = module._remote_audit_code(
        remote_app_dir="/opt/medical-audit/app",
        remote_web_dir="/var/www/audit",
        remote_backup_root="/opt/medical-audit/backups",
        base_url="https://audit.example.test",
        backup_limit=1,
    )

    compile(remote_code, "<remote-audit>", "exec")
    assert "class NoRedirectHandler" in remote_code
    assert "build_opener(NoRedirectHandler())" in remote_code
    assert "urllib.request.urlopen(" not in remote_code
    assert "psql -X -v ON_ERROR_STOP=1" in remote_code
    assert "event_id_fingerprint" in remote_code
    assert "auditor_event_count" in remote_code
    assert "GOVERNANCE_ENV_KEYS" in remote_code
    assert "ENV_FILE_NAME" not in remote_code
    assert "env_path.read_text" not in remote_code
    assert '"--env-file"' not in remote_code
    assert '"medical_audit_app",\n            "python3",' in remote_code


def test_audit_tencent_cloud_deployment_state_remote_release_state_validates_exact_set(
    tmp_path: Path,
) -> None:
    fixture = _write_versioned_audit_release_fixture(tmp_path)
    web_root = fixture["web_root"]
    assert isinstance(web_root, Path)
    namespace = _audit_remote_namespace(remote_web_dir=web_root)
    release_state = namespace.get("release_state")

    assert callable(release_state)
    state = release_state()
    assert state == {
        "ok": True,
        "error": None,
        "current_release_target": f"releases/{fixture['release_sha']}",
        "release_sha": fixture["release_sha"],
        "manifest_source_sha": fixture["release_sha"],
        "remote_manifest_sha256": fixture["manifest_sha256"],
        "manifest_file_count": 2,
        "manifest_mismatch_count": 0,
        "selected_html_path": fixture["html_path"],
        "selected_html_sha256": fixture["html_sha256"],
        "selected_static_path": fixture["static_path"],
        "selected_static_sha256": fixture["static_sha256"],
    }


@pytest.mark.parametrize(
    "mutation",
    ["missing", "extra", "size", "hash", "symlink", "special"],
)
def test_audit_tencent_cloud_deployment_state_rejects_exact_manifest_mutations(
    tmp_path: Path,
    mutation: str,
) -> None:
    fixture = _write_versioned_audit_release_fixture(tmp_path)
    release_root = fixture["release_root"]
    assert isinstance(release_root, Path)
    static_path = fixture["static_path"]
    assert isinstance(static_path, str)
    static_file = release_root / static_path
    if mutation == "missing":
        static_file.unlink()
    elif mutation == "extra":
        _write_bytes(release_root / "extra.txt", b"not in the manifest")
    elif mutation == "size":
        static_file.write_bytes(static_file.read_bytes() + b"size drift")
    elif mutation == "hash":
        static_file.write_bytes(b"x" * static_file.stat().st_size)
    elif mutation == "symlink":
        (release_root / "escape.txt").symlink_to(release_root / "index.html")
    else:
        os.mkfifo(release_root / "named-pipe")

    web_root = fixture["web_root"]
    assert isinstance(web_root, Path)
    release_state = _audit_remote_namespace(remote_web_dir=web_root).get("release_state")
    assert callable(release_state)
    state = release_state()

    assert state["ok"] is False
    assert state["manifest_mismatch_count"] >= 1


@pytest.mark.parametrize(
    "current_target",
    [None, "/var/www/audit/releases/" + "a" * 40, "releases/" + "b" * 40],
    ids=["legacy-no-current", "absolute-target", "wrong-release"],
)
def test_audit_tencent_cloud_deployment_state_rejects_legacy_or_drifted_current(
    tmp_path: Path,
    current_target: str | None,
) -> None:
    fixture = _write_versioned_audit_release_fixture(tmp_path)
    web_root = fixture["web_root"]
    assert isinstance(web_root, Path)
    current = web_root / "current"
    current.unlink()
    if current_target is None:
        _write_bytes(web_root / "_next/static/legacy.js", b"legacy flat root")
    else:
        current.symlink_to(current_target, target_is_directory=True)
    release_state = _audit_remote_namespace(remote_web_dir=web_root).get("release_state")

    assert callable(release_state)
    state = release_state()
    assert state["ok"] is False


def test_audit_tencent_cloud_deployment_state_rejects_manifest_source_drift(
    tmp_path: Path,
) -> None:
    fixture = _write_versioned_audit_release_fixture(
        tmp_path,
        manifest_source_sha="b" * 40,
    )
    web_root = fixture["web_root"]
    assert isinstance(web_root, Path)
    release_state = _audit_remote_namespace(remote_web_dir=web_root).get("release_state")

    assert callable(release_state)
    state = release_state()
    assert state["ok"] is False
    assert state["manifest_source_sha"] == "b" * 40


def test_audit_tencent_cloud_deployment_state_hashes_the_manifest_bytes_it_parses(
    tmp_path: Path,
) -> None:
    fixture = _write_versioned_audit_release_fixture(tmp_path)
    web_root = fixture["web_root"]
    release_root = fixture["release_root"]
    assert isinstance(web_root, Path)
    assert isinstance(release_root, Path)
    manifest_path = release_root / "release-manifest.json"
    replacement = json.loads(manifest_path.read_text(encoding="utf-8"))
    replacement["node_version"] = "v23.99.0"
    replacement_bytes = (
        json.dumps(replacement, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")
    namespace = _audit_remote_namespace(remote_web_dir=web_root)
    original_reader = namespace.get("read_regular_file_at")
    release_state = namespace.get("release_state")
    assert callable(original_reader)
    assert callable(release_state)
    swapped = False

    def swap_after_read(
        parent_fd: int,
        name: str,
        expected_stat: object | None = None,
        collect_bytes: bool = False,
    ) -> tuple[str, int, bytes | None]:
        nonlocal swapped
        result = original_reader(
            parent_fd,
            name,
            expected_stat=expected_stat,
            collect_bytes=collect_bytes,
        )
        if name == "release-manifest.json" and collect_bytes and not swapped:
            manifest_path.write_bytes(replacement_bytes)
            swapped = True
        return result

    namespace["read_regular_file_at"] = swap_after_read
    state = release_state()

    assert swapped is True
    assert state["ok"] is False
    assert state["error"] == "release-manifest-changed-during-audit"
    assert state["remote_manifest_sha256"] == fixture["manifest_sha256"]


def test_audit_tencent_cloud_deployment_state_does_not_follow_directory_swap(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    fixture = _write_versioned_audit_release_fixture(tmp_path)
    web_root = fixture["web_root"]
    release_root = fixture["release_root"]
    assert isinstance(web_root, Path)
    assert isinstance(release_root, Path)
    safe_content = b"expected nested release bytes"
    nested = release_root / "nested"
    _write_bytes(nested / "safe.txt", safe_content)
    manifest_path = release_root / "release-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"].append(
        {
            "path": "nested/safe.txt",
            "size_bytes": len(safe_content),
            "sha256": hashlib.sha256(safe_content).hexdigest(),
        }
    )
    manifest["files"].sort(key=lambda item: item["path"].encode("utf-8"))
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n",
        encoding="utf-8",
    )
    outside = tmp_path / "outside"
    _write_bytes(outside / "safe.txt", safe_content)
    displaced = tmp_path / "displaced-nested"
    namespace = _audit_remote_namespace(remote_web_dir=web_root)
    release_state = namespace.get("release_state")
    remote_os = namespace.get("os")
    assert callable(release_state)
    assert remote_os is os
    original_open = os.open
    original_scandir = os.scandir
    swapped = False

    def swap_directory() -> None:
        nonlocal swapped
        if swapped:
            return
        nested.rename(displaced)
        nested.symlink_to(outside, target_is_directory=True)
        swapped = True

    def racing_open(
        path: str | bytes | int,
        flags: int,
        *args: object,
        **kwargs: object,
    ) -> int:
        if path == "nested" and kwargs.get("dir_fd") is not None:
            swap_directory()
        return original_open(path, flags, *args, **kwargs)

    def racing_scandir(path: str | bytes | int | os.PathLike[str]) -> object:
        if not isinstance(path, int) and Path(path) == nested:
            swap_directory()
        return original_scandir(path)

    monkeypatch.setattr(os, "open", racing_open)
    monkeypatch.setattr(os, "scandir", racing_scandir)

    state = release_state()

    assert swapped is True
    assert state["ok"] is False


def test_audit_tencent_cloud_deployment_state_rejects_symlink_deploy_marker(
    tmp_path: Path,
) -> None:
    deploy_sha = "cf6c1479de0b109d5abc9ee92ac8267e549ec2f6"
    app_root = tmp_path / "app"
    app_root.mkdir()
    outside_marker = _write_bytes(tmp_path / "outside-deploy-sha", f"{deploy_sha}\n".encode())
    (app_root / ".deploy-sha").symlink_to(outside_marker)
    namespace = _audit_remote_namespace(
        remote_app_dir=app_root,
        remote_web_dir=tmp_path / "web",
    )
    deploy_marker_state = namespace.get("deploy_marker_state")

    assert callable(deploy_marker_state)
    marker_state = deploy_marker_state()

    assert marker_state["ok"] is False
    assert marker_state["sha"] is None

    module = _load_script_module(
        "audit_tencent_cloud_deployment_state_symlink_marker",
        Path("scripts/audit-tencent-cloud-deployment-state.py"),
    )
    remote_report = _deployment_state_fixture(stamp="20260611T180655+0800")
    remote_report["deploy_sha"] = None
    release_observation = remote_report["release_observation"]
    assert isinstance(release_observation, dict)
    release_observation["initial_deploy_sha"] = None
    release_observation["final_deploy_sha"] = None
    release_observation["initial_deploy_marker_state"] = marker_state
    release_observation["final_deploy_marker_state"] = marker_state
    report = module._build_report(
        remote_report=remote_report,
        local_smoke_reports=[],
        expected_deploy_sha=deploy_sha,
        required_backup_stamp=None,
        expected_embeddings=48985,
    )

    assert report["status"] == "fail"
    assert "deploy-marker-invalid" in report["issues"]
    assert report["summary"]["release_commit_state"] == "unproven"


def test_audit_tencent_cloud_deployment_state_rejects_same_content_marker_replacement(
    tmp_path: Path,
) -> None:
    deploy_sha = "cf6c1479de0b109d5abc9ee92ac8267e549ec2f6"
    app_root = tmp_path / "app"
    marker = _write_bytes(app_root / ".deploy-sha", f"{deploy_sha}\n".encode())
    namespace = _audit_remote_namespace(
        remote_app_dir=app_root,
        remote_web_dir=tmp_path / "web",
    )
    deploy_marker_state = namespace.get("deploy_marker_state")
    assert callable(deploy_marker_state)
    initial_marker = deploy_marker_state()
    replacement = _write_bytes(
        app_root / ".deploy-sha.next",
        f"{deploy_sha}\n".encode(),
    )
    os.replace(replacement, marker)
    final_marker = deploy_marker_state()

    assert initial_marker["ok"] is True
    assert final_marker["ok"] is True
    assert initial_marker["sha"] == final_marker["sha"] == deploy_sha
    assert initial_marker["snapshot"] != final_marker["snapshot"]

    module = _load_script_module(
        "audit_tencent_cloud_deployment_state_marker_replacement",
        Path("scripts/audit-tencent-cloud-deployment-state.py"),
    )
    remote_report = _deployment_state_fixture(stamp="20260611T180655+0800")
    release_observation = remote_report["release_observation"]
    assert isinstance(release_observation, dict)
    release_observation["initial_deploy_marker_state"] = initial_marker
    release_observation["final_deploy_marker_state"] = final_marker

    report = module._build_report(
        remote_report=remote_report,
        local_smoke_reports=[],
        expected_deploy_sha=deploy_sha,
        required_backup_stamp=None,
        expected_embeddings=48985,
    )

    assert report["status"] == "fail"
    assert "release-observation-drift" in report["issues"]
    assert report["summary"]["release_commit_state"] == "unproven"


def test_audit_tencent_cloud_deployment_state_http_evidence_hashes_cache_and_blocks_cross_origin(
    tmp_path: Path,
) -> None:
    body = b"immutable audit release bytes"
    target_hits: list[str] = []

    class TargetHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            target_hits.append(self.path)
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "public, max-age=31536000")
            self.send_header("Cache-Control", "Immutable")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format: str, *_args: object) -> None:
            return

    target_server = ThreadingHTTPServer(("127.0.0.1", 0), TargetHandler)
    target_thread = threading.Thread(target=target_server.serve_forever, daemon=True)
    target_thread.start()

    class RedirectHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(302)
            self.send_header(
                "Location",
                f"http://127.0.0.1:{target_server.server_port}/asset.js",
            )
            self.end_headers()

        def log_message(self, _format: str, *_args: object) -> None:
            return

    redirect_server = ThreadingHTTPServer(("127.0.0.1", 0), RedirectHandler)
    redirect_thread = threading.Thread(
        target=redirect_server.serve_forever,
        daemon=True,
    )
    redirect_thread.start()
    try:
        namespace = _audit_remote_namespace(remote_web_dir=tmp_path)
        http_status = namespace.get("http_status")
        assert callable(http_status)
        target_url = f"http://127.0.0.1:{target_server.server_port}/asset.js"
        direct = http_status(target_url)
        assert direct.get("body_sha256") == hashlib.sha256(body).hexdigest()
        assert direct.get("cache_control") == (
            "public, max-age=31536000, immutable"
        )
        assert direct.get("final_url") == target_url
        assert direct.get("same_origin") is True

        redirect_url = f"http://127.0.0.1:{redirect_server.server_port}/redirect"
        redirected = http_status(redirect_url)
        assert redirected.get("ok") is False
        assert redirected.get("status_code") == 302
        assert redirected.get("same_origin") is False
        assert target_hits == ["/asset.js"]
    finally:
        redirect_server.shutdown()
        redirect_server.server_close()
        redirect_thread.join(timeout=2)
        target_server.shutdown()
        target_server.server_close()
        target_thread.join(timeout=2)


def test_audit_tencent_cloud_deployment_state_requires_known_host(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_script_module(
        "audit_tencent_cloud_deployment_state_strict_ssh",
        Path("scripts/audit-tencent-cloud-deployment-state.py"),
    )
    ssh_key = tmp_path / "deploy.pem"
    ssh_key.write_text("test-key-placeholder", encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0, stdout="{}", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    module._collect_remote_report(
        ssh_key=ssh_key,
        ssh_user="ubuntu",
        ssh_host="example.test",
        remote_app_dir="/opt/medical-audit/app",
        remote_web_dir="/var/www/audit",
        remote_backup_root="/opt/medical-audit/backups",
        base_url="https://audit.example.test",
        backup_limit=1,
    )

    command = captured["command"]
    assert isinstance(command, list)
    assert "BatchMode=yes" in command
    assert "StrictHostKeyChecking=yes" in command
    assert "StrictHostKeyChecking=no" not in command
    assert "IdentitiesOnly=yes" in command


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
        expected_embeddings=48985,
    )

    assert report["status"] == "pass"
    assert report["issues"] == []
    assert report["evidence_grade"] == "L3-production-read-only"
    assert report["production_side_effect"] == "none"
    assert report["database_write"] is False
    assert report["provider_call_status"] == "not_called"
    assert report["http_methods"] == ["GET"]
    assert report["summary"]["deploy_sha"] == "cf6c1479de0b109d5abc9ee92ac8267e549ec2f6"
    assert report["summary"]["audit_mount_present"] is True
    assert report["summary"]["audit_log_event_delta"] == 0
    assert report["summary"]["latest_local_smoke_status"] == "pass"
    assert report["summary"] | {
        "remote_manifest_sha256": "b" * 64,
        "public_manifest_sha256": "b" * 64,
        "manifest_file_count": 2,
        "manifest_mismatch_count": 0,
        "html_cache_control": "no-store, no-cache, must-revalidate",
        "static_cache_control": "public, max-age=31536000, immutable",
        "current_release_target": (
            "releases/cf6c1479de0b109d5abc9ee92ac8267e549ec2f6"
        ),
        "deploy_sha": "cf6c1479de0b109d5abc9ee92ac8267e549ec2f6",
    } == report["summary"]
    assert report["summary"]["release_commit_state"] == "committed_by_marker"
    assert report["summary"]["deploy_marker_valid"] is True
    assert report["summary"]["deploy_marker_observation_stable"] is True
    assert report["summary"]["release_observation_stable"] is True
    assert report["summary"]["manifest_html_sha256"] == "d" * 64
    assert report["summary"]["public_html_sha256"] == "d" * 64


@pytest.mark.parametrize(
    ("mutation", "expected_issue"),
    [
        ("deploy-sha", "deploy-sha-mismatch"),
        ("current", "current-release-target-mismatch"),
        ("source", "remote-manifest-source-sha-mismatch"),
        ("post-current", "release-observation-drift"),
        ("post-manifest", "release-observation-drift"),
        ("post-deploy", "release-observation-drift"),
        ("manifest-hash", "public-manifest-sha-mismatch"),
        ("html-hash", "public-html-sha-mismatch"),
        ("static-hash", "public-static-sha-mismatch"),
        ("file-mismatch", "remote-release-integrity-failed"),
        ("html-cache", "html-cache-control-invalid"),
        ("valued-html-cache", "html-cache-control-invalid"),
        ("static-cache", "static-cache-control-invalid"),
        ("valued-static-cache", "static-cache-control-invalid"),
        ("short-static-cache", "static-cache-control-invalid"),
        ("nginx", "nginx-config-test-failed"),
        ("legacy", "remote-release-integrity-failed"),
    ],
)
def test_audit_tencent_cloud_deployment_state_rejects_release_gate_mutation(
    mutation: str,
    expected_issue: str,
) -> None:
    module = _load_script_module(
        f"audit_tencent_cloud_deployment_state_release_gate_{mutation}",
        Path("scripts/audit-tencent-cloud-deployment-state.py"),
    )
    remote_report = _deployment_state_fixture(stamp="20260611T180655+0800")
    release_state = remote_report["release_state"]
    release_observation = remote_report["release_observation"]
    frontdoor = remote_report["public_frontdoor"]
    nginx = remote_report["nginx"]
    assert isinstance(release_state, dict)
    assert isinstance(release_observation, dict)
    assert isinstance(frontdoor, dict)
    assert isinstance(nginx, dict)
    if mutation == "deploy-sha":
        remote_report["deploy_sha"] = "f" * 40
        release_observation["initial_deploy_sha"] = "f" * 40
        release_observation["final_deploy_sha"] = "f" * 40
    elif mutation == "current":
        release_state["current_release_target"] = "releases/" + "f" * 40
        final_release = release_observation["final_release_state"]
        assert isinstance(final_release, dict)
        final_release["current_release_target"] = "releases/" + "f" * 40
    elif mutation == "source":
        release_state["manifest_source_sha"] = "f" * 40
        final_release = release_observation["final_release_state"]
        assert isinstance(final_release, dict)
        final_release["manifest_source_sha"] = "f" * 40
    elif mutation in {"post-current", "post-manifest"}:
        final_release = release_observation["final_release_state"]
        assert isinstance(final_release, dict)
        field = (
            "current_release_target"
            if mutation == "post-current"
            else "remote_manifest_sha256"
        )
        final_release[field] = (
            "releases/" + "f" * 40 if field.startswith("current") else "f" * 64
        )
    elif mutation == "post-deploy":
        release_observation["final_deploy_sha"] = "f" * 40
    elif mutation == "manifest-hash":
        manifest = frontdoor["manifest"]
        assert isinstance(manifest, dict)
        manifest["body_sha256"] = "f" * 64
    elif mutation == "html-hash":
        documents = frontdoor["documents"]
        assert isinstance(documents, dict)
        documents["body_sha256"] = "f" * 64
    elif mutation == "static-hash":
        static = frontdoor["next_static"]
        assert isinstance(static, dict)
        static["body_sha256"] = "f" * 64
    elif mutation == "file-mismatch":
        release_state["ok"] = False
        release_state["manifest_mismatch_count"] = 1
        final_release = release_observation["final_release_state"]
        assert isinstance(final_release, dict)
        final_release["ok"] = False
        final_release["manifest_mismatch_count"] = 1
    elif mutation == "html-cache":
        documents = frontdoor["documents"]
        assert isinstance(documents, dict)
        documents["cache_control"] = "private, no-cache-disabled"
    elif mutation == "valued-html-cache":
        documents = frontdoor["documents"]
        assert isinstance(documents, dict)
        documents["cache_control"] = "private, no-cache=disabled"
    elif mutation == "static-cache":
        static = frontdoor["next_static"]
        assert isinstance(static, dict)
        static["cache_control"] = "public, max-age=31536000, not-immutable"
    elif mutation == "valued-static-cache":
        static = frontdoor["next_static"]
        assert isinstance(static, dict)
        static["cache_control"] = (
            "public, max-age=31536000, immutable=disabled"
        )
    elif mutation == "short-static-cache":
        static = frontdoor["next_static"]
        assert isinstance(static, dict)
        static["cache_control"] = "public, max-age=60, immutable"
    elif mutation == "nginx":
        nginx["config_test"] = {"passed": False}
    else:
        release_state.clear()
        release_state.update(
            {
                "ok": False,
                "error": "current-release-missing",
                "current_release_target": None,
                "manifest_file_count": 0,
                "manifest_mismatch_count": 1,
            }
        )
        release_observation["final_release_state"] = dict(release_state)

    report = module._build_report(
        remote_report=remote_report,
        local_smoke_reports=[],
        expected_deploy_sha="cf6c1479de0b109d5abc9ee92ac8267e549ec2f6",
        required_backup_stamp=None,
        expected_embeddings=48985,
    )

    assert report["status"] == "fail"
    assert expected_issue in report["issues"]
    if mutation in {
        "deploy-sha",
        "current",
        "source",
        "post-current",
        "post-manifest",
        "post-deploy",
        "legacy",
    }:
        assert report["summary"]["release_commit_state"] != "committed_by_marker"
    else:
        assert report["summary"]["release_commit_state"] == "committed_by_marker"


def test_audit_tencent_cloud_deployment_state_outputs_release_fields_compatibly(
    tmp_path: Path,
) -> None:
    module = _load_script_module(
        "audit_tencent_cloud_deployment_state_output_compatibility",
        Path("scripts/audit-tencent-cloud-deployment-state.py"),
    )
    report = module._build_report(
        remote_report=_deployment_state_fixture(stamp="20260611T180655+0800"),
        local_smoke_reports=[],
        expected_deploy_sha="cf6c1479de0b109d5abc9ee92ac8267e549ec2f6",
        required_backup_stamp=None,
        expected_embeddings=48985,
    )
    json_output = tmp_path / "state.json"
    markdown_output = tmp_path / "state.md"
    module._write_json(json_output, report)
    module._write_markdown(markdown_output, report)

    serialized = json.loads(json_output.read_text(encoding="utf-8"))
    assert serialized["summary"]["app_health"] == "healthy"
    assert serialized["summary"]["remote_manifest_sha256"] == "b" * 64
    assert serialized["warnings"] == []
    markdown = markdown_output.read_text(encoding="utf-8")
    for field in (
        "deploy_sha",
        "app_health",
        "remote_manifest_sha256",
        "public_manifest_sha256",
        "manifest_file_count",
        "manifest_mismatch_count",
        "html_cache_control",
        "static_cache_control",
        "current_release_target",
    ):
        assert f"`{field}`" in markdown


def test_audit_tencent_cloud_deployment_state_fails_closed_on_audit_log_delta() -> None:
    module = _load_script_module(
        "audit_tencent_cloud_deployment_state_audit_delta",
        Path("scripts/audit-tencent-cloud-deployment-state.py"),
    )
    remote_report = _deployment_state_fixture(stamp="20260611T180655+0800")
    side_effects = remote_report["side_effect_observation"]
    assert isinstance(side_effects, dict)
    after = side_effects["audit_log_after"]
    assert isinstance(after, dict)
    after["count"] = 101

    report = module._build_report(
        remote_report=remote_report,
        local_smoke_reports=[],
        expected_deploy_sha="cf6c1479de0b109d5abc9ee92ac8267e549ec2f6",
        required_backup_stamp=None,
        expected_embeddings=48985,
    )

    assert report["status"] == "fail"
    assert report["issues"] == ["audit-log-delta-nonzero"]
    assert report["evidence_grade"] == "L1-public-or-runtime"
    assert report["production_side_effect"] == "unknown"
    assert report["database_write"] == "unknown"
    assert report["provider_call_status"] == "not_called"
    assert report["summary"]["audit_log_event_delta"] == 1


def test_audit_tencent_cloud_deployment_state_rejects_balanced_audit_log_mutation() -> None:
    module = _load_script_module(
        "audit_tencent_cloud_deployment_state_balanced_audit_mutation",
        Path("scripts/audit-tencent-cloud-deployment-state.py"),
    )
    remote_report = _deployment_state_fixture(stamp="20260611T180655+0800")
    side_effects = remote_report["side_effect_observation"]
    assert isinstance(side_effects, dict)
    after = side_effects["audit_log_after"]
    assert isinstance(after, dict)
    after["event_id_fingerprint"] = "f" * 32
    after["latest_created_at"] = "2026-07-15 01:00:01+00"

    report = module._build_report(
        remote_report=remote_report,
        local_smoke_reports=[],
        expected_deploy_sha="cf6c1479de0b109d5abc9ee92ac8267e549ec2f6",
        required_backup_stamp=None,
        expected_embeddings=48985,
    )

    assert report["status"] == "fail"
    assert "audit-log-snapshot-mutated" in report["issues"]
    assert report["evidence_grade"] == "L1-public-or-runtime"
    assert report["production_side_effect"] == "unknown"
    assert report["database_write"] == "unknown"
    assert report["summary"]["audit_log_event_delta"] == 0
    assert report["summary"]["audit_log_snapshot_unchanged"] is False


def test_audit_tencent_cloud_deployment_state_rejects_auditor_attributed_event() -> None:
    module = _load_script_module(
        "audit_tencent_cloud_deployment_state_auditor_event",
        Path("scripts/audit-tencent-cloud-deployment-state.py"),
    )
    remote_report = _deployment_state_fixture(stamp="20260611T180655+0800")
    side_effects = remote_report["side_effect_observation"]
    assert isinstance(side_effects, dict)
    after = side_effects["audit_log_after"]
    assert isinstance(after, dict)
    after["auditor_event_count"] = 1
    after["event_id_fingerprint"] = "f" * 32
    after["latest_created_at"] = "2026-07-15 01:00:01+00"

    report = module._build_report(
        remote_report=remote_report,
        local_smoke_reports=[],
        expected_deploy_sha="cf6c1479de0b109d5abc9ee92ac8267e549ec2f6",
        required_backup_stamp=None,
        expected_embeddings=48985,
    )

    assert report["status"] == "fail"
    assert "audit-log-auditor-events-detected" in report["issues"]
    assert report["evidence_grade"] == "L1-public-or-runtime"
    assert report["production_side_effect"] == "audit-log-only"
    assert report["database_write"] == "audit-log-only"
    assert report["summary"]["audit_log_auditor_event_delta"] == 1
    assert report["summary"]["audit_log_auditor_write_attributed"] is True


def test_audit_tencent_cloud_deployment_state_unknown_database_write_without_boundaries(
) -> None:
    module = _load_script_module(
        "audit_tencent_cloud_deployment_state_missing_boundaries",
        Path("scripts/audit-tencent-cloud-deployment-state.py"),
    )
    remote_report = _deployment_state_fixture(stamp="20260611T180655+0800")
    local_backend = remote_report["local_backend"]
    assert isinstance(local_backend, dict)
    search_backend = local_backend["search_backend"]
    assert isinstance(search_backend, dict)
    payload = search_backend["payload"]
    assert isinstance(payload, dict)
    payload.pop("boundaries")

    report = module._build_report(
        remote_report=remote_report,
        local_smoke_reports=[],
        expected_deploy_sha="cf6c1479de0b109d5abc9ee92ac8267e549ec2f6",
        required_backup_stamp=None,
        expected_embeddings=48985,
    )

    assert report["status"] == "fail"
    assert "search-backend-side-effect-boundary-unsafe" in report["issues"]
    assert report["evidence_grade"] == "L1-public-or-runtime"
    assert report["production_side_effect"] == "unknown"
    assert report["database_write"] == "unknown"
    assert report["provider_call_status"] == "unknown"

    side_effects = remote_report["side_effect_observation"]
    assert isinstance(side_effects, dict)
    after = side_effects["audit_log_after"]
    assert isinstance(after, dict)
    after["count"] = 101
    after["auditor_event_count"] = 1
    after["event_id_fingerprint"] = "f" * 32
    after["latest_created_at"] = "2026-07-15 01:00:01+00"
    report_with_observed_audit_write = module._build_report(
        remote_report=remote_report,
        local_smoke_reports=[],
        expected_deploy_sha="cf6c1479de0b109d5abc9ee92ac8267e549ec2f6",
        required_backup_stamp=None,
        expected_embeddings=48985,
    )
    assert report_with_observed_audit_write["database_write"] == "unknown"
    assert report_with_observed_audit_write["production_side_effect"] == "unknown"


@pytest.mark.parametrize(
    ("after_count", "expected_issue"),
    [
        (99, "audit-log-delta-nonzero"),
        (None, "audit-log-delta-unavailable"),
    ],
)
def test_audit_tencent_cloud_deployment_state_rejects_unprovable_l3_delta(
    after_count: int | None,
    expected_issue: str,
) -> None:
    module = _load_script_module(
        f"audit_tencent_cloud_deployment_state_unprovable_{after_count}",
        Path("scripts/audit-tencent-cloud-deployment-state.py"),
    )
    remote_report = _deployment_state_fixture(stamp="20260611T180655+0800")
    side_effects = remote_report["side_effect_observation"]
    assert isinstance(side_effects, dict)
    after = side_effects["audit_log_after"]
    assert isinstance(after, dict)
    if after_count is None:
        after.pop("count")
    else:
        after["count"] = after_count

    report = module._build_report(
        remote_report=remote_report,
        local_smoke_reports=[],
        expected_deploy_sha="cf6c1479de0b109d5abc9ee92ac8267e549ec2f6",
        required_backup_stamp=None,
        expected_embeddings=48985,
    )

    assert report["status"] == "fail"
    assert expected_issue in report["issues"]
    assert report["evidence_grade"] == "L1-public-or-runtime"
    assert report["production_side_effect"] == "unknown"
    assert report["database_write"] == "unknown"


def test_audit_tencent_cloud_deployment_state_rejects_proxy_frontdoor_without_mount() -> None:
    module = _load_script_module(
        "audit_tencent_cloud_deployment_state_proxy_frontdoor",
        Path("scripts/audit-tencent-cloud-deployment-state.py"),
    )
    remote_report = _deployment_state_fixture(stamp="20260611T180655+0800")
    remote_report["nginx"] = {
        "config_test": {"passed": True},
        "mounts": {"audit_mount": None, "mount_count": 18},
    }
    frontdoor = remote_report["public_frontdoor"]
    assert isinstance(frontdoor, dict)
    frontdoor["next_static"] = {
        "ok": False,
        "status_code": 404,
        "same_origin": True,
        "cache_control": "public, max-age=31536000, immutable",
    }

    report = module._build_report(
        remote_report=remote_report,
        local_smoke_reports=[],
        expected_deploy_sha="cf6c1479de0b109d5abc9ee92ac8267e549ec2f6",
        required_backup_stamp=None,
        expected_embeddings=48985,
    )

    assert report["status"] == "fail"
    assert report["issues"] == [
        "audit-static-bind-mount-missing",
        "audit-next-static-not-ready",
    ]
    assert report["summary"]["audit_mount_present"] is False
    assert report["summary"]["audit_frontdoor_healthy"] is True
    assert report["summary"]["audit_next_static_healthy"] is False


def test_audit_tencent_cloud_deployment_state_fails_when_frontdoor_is_unhealthy() -> None:
    module = _load_script_module(
        "audit_tencent_cloud_deployment_state_frontdoor_unhealthy",
        Path("scripts/audit-tencent-cloud-deployment-state.py"),
    )
    remote_report = _deployment_state_fixture(stamp="20260611T180655+0800")
    frontdoor = remote_report["public_frontdoor"]
    assert isinstance(frontdoor, dict)
    frontdoor["health"] = {"ok": False, "status_code": 503}

    report = module._build_report(
        remote_report=remote_report,
        local_smoke_reports=[],
        expected_deploy_sha="cf6c1479de0b109d5abc9ee92ac8267e549ec2f6",
        required_backup_stamp=None,
        expected_embeddings=48985,
    )

    assert report["status"] == "fail"
    assert "audit-frontdoor-not-ready" in report["issues"]
    assert report["summary"]["audit_frontdoor_healthy"] is False


def test_audit_tencent_cloud_deployment_state_authenticates_documents_frontdoor() -> None:
    script_text = Path("scripts/audit-tencent-cloud-deployment-state.py").read_text(
        encoding="utf-8",
    )

    assert "def http_status(url, expected_texts=None, headers=None):" in script_text
    assert "request_headers.update(headers)" in script_text
    assert "headers=AUDIT_HEADERS" in script_text
    assert '["登录工作台", "AI审计一体化协作平台"]' in script_text
    assert "文档依据检索" not in script_text


def test_local_fullstack_e2e_runs_playwright_serially_for_stable_route_compilation() -> None:
    script_text = Path("scripts/run-local-fullstack-e2e.py").read_text(encoding="utf-8")

    assert 'command = [pnpm, "--dir", "web", "e2e", "--workers=1"]' in script_text


def test_local_fullstack_e2e_configures_in_memory_report_store(tmp_path: Path) -> None:
    module = _load_script_module(
        "run_local_fullstack_e2e_report_store",
        Path("scripts/run-local-fullstack-e2e.py"),
    )

    state = module._api_state(tmp_path)

    assert state.review_task_store is not None
    assert state.review_task_store.__class__.__name__ == "InMemoryReviewTaskStore"
    assert state.audit_finding_store is None
    assert state.audit_log_store is None


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
        expected_embeddings=48985,
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
        include_query_provider_smoke=False,
        include_review_write=False,
        confirm_production_write="",
        approved_sha="",
        rollback=False,
        expected_current_sha="",
        restore_sha="",
        allow_first_legacy_migration=False,
        report="",
    )

    config = module._config_from_args(args)

    assert config.report_path == Path(
        "tmp/outputs/production-e2e-smoke-after-deploy-20260611T184000+0800.json",
    ).resolve()


def _patch_deploy_execute_snapshot(
    monkeypatch: MonkeyPatch,
    module: types.ModuleType,
    config: types.SimpleNamespace,
) -> None:
    if not hasattr(config, "repo_root"):
        config.repo_root = Path(".").resolve()
    if not hasattr(config, "skip_web_build"):
        config.skip_web_build = False
    monkeypatch.setattr(
        module,
        "_approved_release_snapshot",
        lambda _config: nullcontext(config.repo_root),
    )
    monkeypatch.setattr(
        module,
        "replace",
        lambda value, **changes: types.SimpleNamespace(**(vars(value) | changes)),
    )


def _patch_deploy_locked_path(
    monkeypatch: MonkeyPatch,
    module: types.ModuleType,
    config: types.SimpleNamespace,
    events: list[str],
) -> None:
    _patch_deploy_execute_snapshot(monkeypatch, module, config)
    evidence = module.ReleaseEvidence("b" * 64, 2, "_next/static/app.js", "c" * 64)
    monkeypatch.setattr(module, "_parse_args", lambda: object())
    monkeypatch.setattr(module, "_config_from_args", lambda _args: config)
    monkeypatch.setattr(module, "_print_plan", lambda _config: None)
    monkeypatch.setattr(module, "_validate_local_state", lambda _config: None)
    monkeypatch.setattr(module, "_validate_locked_python_dependencies", lambda _config: None)
    monkeypatch.setattr(module, "_build_static_frontend", lambda _config: None)
    monkeypatch.setattr(module, "_validate_web_release", lambda _config: evidence)
    monkeypatch.setattr(module, "_run_remote_preflight", lambda _config: None)
    monkeypatch.setattr(
        module,
        "_acquire_remote_deploy_lock",
        lambda _config: events.append("lock") or "token",
    )
    monkeypatch.setattr(
        module,
        "_release_remote_deploy_lock",
        lambda *_args: events.append("unlock"),
    )
    for name in (
        "_create_remote_backups",
        "_cleanup_remote_sync_artifacts",
        "_sync_application",
        "_prepare_remote_release_incoming",
        "_sync_static_frontend",
        "_verify_and_promote_remote_release",
        "_rebuild_application",
        "_activate_remote_release",
        "_run_remote_post_checks",
        "_verify_remote_release_commit_point",
        "_run_production_smoke",
        "_write_remote_deploy_sha",
    ):
        monkeypatch.setattr(module, name, lambda *_args: None)


def test_deploy_tencent_cloud_execute_requires_clean_approved_main(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_release_source_gate",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    approved_sha = "a" * 40
    fetch_calls: list[list[str]] = []
    outputs = {
        ("git", "symbolic-ref", "--quiet", "--short", "HEAD"): "main\n",
        ("git", "rev-parse", "HEAD"): f"{approved_sha}\n",
        ("git", "rev-parse", "origin/main"): f"{approved_sha}\n",
    }
    monkeypatch.setattr(
        module,
        "_run",
        lambda args, *, cwd: fetch_calls.append(list(args)),
    )
    monkeypatch.setattr(
        module,
        "_run_capture",
        lambda args, *, cwd: outputs[tuple(args)],
    )
    config = types.SimpleNamespace(repo_root=tmp_path, approved_sha=approved_sha)

    module._validate_release_source(config)

    assert fetch_calls == [
        [
            "git",
            "fetch",
            "--quiet",
            "origin",
            "+refs/heads/main:refs/remotes/origin/main",
        ],
    ]


def test_deploy_tencent_cloud_snapshot_is_pinned_to_approved_commit(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_approved_snapshot",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    snapshotter = getattr(module, "_approved_release_snapshot", None)
    assert snapshotter is not None
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "codex@example.test"],
        cwd=repo,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Codex Test"],
        cwd=repo,
        check=True,
    )
    (repo / "approved.txt").write_text("approved\n", encoding="utf-8")
    subprocess.run(["git", "add", "approved.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "approved"], cwd=repo, check=True)
    approved_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    config = types.SimpleNamespace(
        repo_root=repo,
        approved_sha=approved_sha,
        skip_web_build=False,
    )
    commands: list[tuple[list[str], Path]] = []
    monkeypatch.setattr(
        module,
        "_run",
        lambda args, *, cwd, **_kwargs: commands.append((list(args), cwd)),
    )

    with snapshotter(config) as snapshot_root:
        snapshot_root = Path(snapshot_root)
        assert snapshot_root != repo
        assert (snapshot_root / "approved.txt").read_text(encoding="utf-8") == "approved\n"
        subprocess.run(["git", "switch", "-c", "drift"], cwd=repo, check=True)
        (repo / "approved.txt").write_text("live-drift\n", encoding="utf-8")
        web_out = snapshot_root / "web" / "out"
        web_out.mkdir(parents=True)
        deploy_config = types.SimpleNamespace(
            repo_root=snapshot_root,
            ssh_target="ubuntu@example.test",
            ssh_key=tmp_path / "deploy.pem",
            remote_app_dir="/opt/medical-audit/app",
            remote_web_dir="/var/www/audit",
            approved_sha=approved_sha,
        )
        module._sync_application(deploy_config, "owner-token")
        module._sync_static_frontend(deploy_config, "owner-token")
        assert (snapshot_root / "approved.txt").read_text(encoding="utf-8") == "approved\n"
        assert commands[0][0][-2] == f"{snapshot_root}/"
        assert commands[1][0][-2] == f"{snapshot_root}/web/out/"
    assert not snapshot_root.exists()


def test_deploy_tencent_cloud_wrong_release_sha_fails_before_first_ssh(
    monkeypatch: MonkeyPatch,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_wrong_release_sha_before_ssh",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    config = types.SimpleNamespace(execute=True, rollback=False, apply_schema=False)
    _patch_deploy_execute_snapshot(monkeypatch, module, config)
    events: list[str] = []

    monkeypatch.setattr(module, "_parse_args", lambda: object())
    monkeypatch.setattr(module, "_config_from_args", lambda _args: config)
    monkeypatch.setattr(module, "_print_plan", lambda _config: None)
    monkeypatch.setattr(module, "_validate_local_state", lambda _config: None)
    monkeypatch.setattr(
        module,
        "_validate_locked_python_dependencies",
        lambda _config: None,
    )
    monkeypatch.setattr(
        module,
        "_build_static_frontend",
        lambda _config: events.append("build"),
    )

    def reject_manifest(_config: object) -> None:
        events.append("validate")
        raise module.DeployError(
            "web release manifest source SHA does not match approved SHA",
        )

    monkeypatch.setattr(module, "_validate_web_release", reject_manifest, raising=False)
    monkeypatch.setattr(
        module,
        "_run_remote_preflight",
        lambda _config: events.append("ssh"),
    )
    monkeypatch.setattr(module, "_create_remote_backups", lambda _config: None)
    monkeypatch.setattr(module, "_cleanup_remote_sync_artifacts", lambda _config: None)
    monkeypatch.setattr(module, "_sync_application", lambda _config: None)
    monkeypatch.setattr(module, "_sync_static_frontend", lambda _config: None)
    monkeypatch.setattr(module, "_rebuild_application", lambda _config: None)
    monkeypatch.setattr(module, "_run_remote_post_checks", lambda _config: None)
    monkeypatch.setattr(module, "_write_remote_deploy_sha", lambda _config: None)
    monkeypatch.setattr(module, "_run_production_smoke", lambda _config: None)

    assert module.main() == 2
    assert events == ["build", "validate"]


def _deploy_release_fixture(
    tmp_path: Path,
    *,
    source_sha: str = "a" * 40,
) -> tuple[types.SimpleNamespace, dict[str, object], Path]:
    repo_root = tmp_path / "repo"
    web_out = repo_root / "web" / "out"
    static_asset = _write_bytes(
        web_out / "_next" / "static" / "app.js",
        b"console.log('release');\n",
    )
    index = _write_bytes(web_out / "index.html", b"<h1>release</h1>\n")
    lockfile = _write_bytes(repo_root / "pnpm-lock.yaml", b"lockfileVersion: '9.0'\n")
    files = []
    for relative_path, path in (
        ("_next/static/app.js", static_asset),
        ("index.html", index),
    ):
        content = path.read_bytes()
        files.append(
            {
                "path": relative_path,
                "size_bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )
    payload: dict[str, object] = {
        "files": files,
        "format": "medical-audit-web-release-manifest-v1",
        "lockfile_sha256": hashlib.sha256(lockfile.read_bytes()).hexdigest(),
        "node_version": "v22.22.0",
        "pnpm_version": "9.15.0",
        "public_build_variables": {
            "NEXT_PUBLIC_AUDIT_ORG_LOGO": None,
            "NEXT_PUBLIC_AUDIT_ORG_NAME": "测试医院",
            "NEXT_PUBLIC_MEDICAL_AUDIT_AGENT_EXTENSION_PACK": None,
            "NEXT_PUBLIC_MEDICAL_AUDIT_REPLICA_API_READS": "1",
        },
        "source_sha": source_sha,
    }
    manifest_path = web_out / "release-manifest.json"
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n",
        encoding="utf-8",
    )
    return (
        types.SimpleNamespace(repo_root=repo_root, approved_sha="a" * 40),
        payload,
        manifest_path,
    )


def _rewrite_deploy_release_manifest(
    manifest_path: Path,
    payload: dict[str, object],
) -> None:
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n",
        encoding="utf-8",
    )


def test_deploy_tencent_cloud_valid_release_manifest_returns_stable_evidence(
    tmp_path: Path,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_valid_release_manifest",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    config, payload, manifest_path = _deploy_release_fixture(tmp_path)

    evidence = module._validate_web_release(config)

    assert evidence.manifest_sha256 == hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    assert evidence.manifest_file_count == len(payload["files"])
    assert evidence.static_asset_path == "_next/static/app.js"
    assert evidence.static_asset_sha256 == hashlib.sha256(
        (config.repo_root / "web/out/_next/static/app.js").read_bytes(),
    ).hexdigest()


@pytest.mark.parametrize(
    "case",
    ["empty", "missing", "extra", "invalid-value"],
)
def test_deploy_tencent_cloud_release_manifest_requires_exact_public_build_variables(
    tmp_path: Path,
    case: str,
) -> None:
    module = _load_script_module(
        f"deploy_tencent_cloud_release_public_build_variables_{case}",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    config, payload, manifest_path = _deploy_release_fixture(tmp_path)
    variables = payload["public_build_variables"]
    assert isinstance(variables, dict)
    if case == "empty":
        variables.clear()
    elif case == "missing":
        variables.pop("NEXT_PUBLIC_AUDIT_ORG_LOGO")
    elif case == "extra":
        variables["NEXT_PUBLIC_UNREVIEWED_FLAG"] = "enabled"
    elif case == "invalid-value":
        variables["NEXT_PUBLIC_AUDIT_ORG_LOGO"] = 1
    else:
        raise AssertionError(f"unhandled case: {case}")
    _rewrite_deploy_release_manifest(manifest_path, payload)

    with pytest.raises(module.DeployError, match="public_build_variables"):
        module._validate_web_release(config)


def test_deploy_tencent_cloud_open_release_root_closes_fd_when_fstat_fails(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_release_root_fstat_failure",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    web_out = tmp_path / "web" / "out"
    web_out.mkdir(parents=True)
    closed: list[int] = []
    monkeypatch.setattr(module.os, "open", lambda *_args, **_kwargs: 73)
    monkeypatch.setattr(
        module.os,
        "fstat",
        lambda _fd: (_ for _ in ()).throw(OSError("injected fstat failure")),
    )
    monkeypatch.setattr(module.os, "close", lambda fd: closed.append(fd))

    with pytest.raises(module.DeployError, match="web/out"):
        module._open_release_root(web_out)

    assert closed == [73]


def test_deploy_tencent_cloud_open_release_root_closes_non_directory_fd(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_release_root_wrong_type",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    web_out = tmp_path / "web" / "out"
    web_out.mkdir(parents=True)
    closed: list[int] = []
    regular_file_stat = os.stat_result(
        (stat.S_IFREG | 0o644, 0, 0, 1, 1, 0, 0, 0, 0, 0),
    )
    monkeypatch.setattr(module.os, "open", lambda *_args, **_kwargs: 74)
    monkeypatch.setattr(module.os, "fstat", lambda _fd: regular_file_stat)
    monkeypatch.setattr(module.os, "close", lambda fd: closed.append(fd))

    with pytest.raises(module.DeployError, match="web/out"):
        module._open_release_root(web_out)

    assert closed == [74]


def test_deploy_tencent_cloud_open_release_root_closes_malformed_fstat_result(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_release_root_malformed_fstat",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    web_out = tmp_path / "web" / "out"
    web_out.mkdir(parents=True)
    closed: list[int] = []
    monkeypatch.setattr(module.os, "open", lambda *_args, **_kwargs: 75)
    monkeypatch.setattr(
        module.os,
        "fstat",
        lambda _fd: types.SimpleNamespace(st_mode="not-an-integer-mode"),
    )
    monkeypatch.setattr(module.os, "close", lambda fd: closed.append(fd))

    with pytest.raises(module.DeployError, match="web/out"):
        module._open_release_root(web_out)

    assert closed == [75]


def test_deploy_tencent_cloud_release_gate_fails_closed_on_parent_directory_swap(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_release_parent_directory_swap",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    config, _payload, _manifest_path = _deploy_release_fixture(tmp_path)
    static_directory = config.repo_root / "web/out/_next/static"
    safe_directory = config.repo_root / "web/out/_next/static.safe"
    outside_directory = tmp_path / "outside-static"
    outside_directory.mkdir()
    _write_bytes(outside_directory / "app.js", b"malicious outside content\n")
    original_open = module.os.open
    swapped = False

    def swap_parent_before_asset_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal swapped
        if not swapped and Path(os.fsdecode(path)).name == "app.js":
            static_directory.rename(safe_directory)
            static_directory.symlink_to(outside_directory, target_is_directory=True)
            swapped = True
        if dir_fd is None:
            return original_open(path, flags, mode)
        return original_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(module.os, "open", swap_parent_before_asset_open)

    with pytest.raises(module.DeployError, match="symlink"):
        module._validate_web_release(config)

    assert swapped is True


def test_deploy_tencent_cloud_release_gate_rejects_special_file(
    tmp_path: Path,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_release_special_file",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    config, _payload, _manifest_path = _deploy_release_fixture(tmp_path)
    os.mkfifo(config.repo_root / "web/out/named-pipe")

    with pytest.raises(module.DeployError, match="non-regular file"):
        module._validate_web_release(config)


def test_deploy_tencent_cloud_release_gate_rejects_replaced_root_path(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_release_replaced_root_path",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    config, _payload, _manifest_path = _deploy_release_fixture(tmp_path)
    web_out = config.repo_root / "web/out"
    preserved = config.repo_root / "web/out.preserved"
    replacement = tmp_path / "replacement-out"
    replacement.mkdir()
    original_collect = module._collect_release_files
    swapped = False

    def collect_then_replace(root_fd: int) -> object:
        nonlocal swapped
        result = original_collect(root_fd)
        if not swapped:
            web_out.rename(preserved)
            web_out.symlink_to(replacement, target_is_directory=True)
            swapped = True
        return result

    monkeypatch.setattr(module, "_collect_release_files", collect_then_replace)

    with pytest.raises(module.DeployError, match="web/out changed"):
        module._validate_web_release(config)

    assert swapped is True


def test_deploy_tencent_cloud_release_gate_rejects_change_between_stability_scans(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_release_stability_scan_change",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    config, _payload, _manifest_path = _deploy_release_fixture(tmp_path)
    asset = config.repo_root / "web/out/_next/static/app.js"
    original_collect = module._collect_release_files
    collect_count = 0

    def collect_then_mutate(root_fd: int) -> object:
        nonlocal collect_count
        result = original_collect(root_fd)
        collect_count += 1
        if collect_count == 1:
            asset.write_bytes(b"changed between stability scans\n")
        return result

    monkeypatch.setattr(module, "_collect_release_files", collect_then_mutate)

    with pytest.raises(module.DeployError, match="changed during release validation"):
        module._validate_web_release(config)

    assert collect_count == 2


def test_deploy_tencent_cloud_release_manifest_has_bounded_read(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_release_manifest_bounded_read",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    config, _payload, manifest_path = _deploy_release_fixture(tmp_path)
    monkeypatch.setattr(module, "MAX_RELEASE_MANIFEST_BYTES", 32)
    assert manifest_path.stat().st_size > 32

    with pytest.raises(module.DeployError, match="maximum allowed size"):
        module._validate_web_release(config)


@pytest.mark.parametrize(
    ("case", "error_match"),
    [
        ("missing", "file set"),
        ("extra", "file set"),
        ("hash", "SHA-256"),
        ("size", "size"),
        ("symlink", "symlink"),
        ("manifest-symlink", "manifest.*regular"),
        ("path-escape", "canonical relative POSIX"),
        ("invalid-format", "format"),
        ("lockfile", "lockfile"),
        ("duplicate", "duplicate"),
        ("sha-type", "sha256"),
        ("size-type", "size_bytes"),
        ("files-type", "files"),
        ("no-static-asset", "_next/static"),
    ],
)
def test_deploy_tencent_cloud_release_manifest_fails_closed(
    tmp_path: Path,
    case: str,
    error_match: str,
) -> None:
    module = _load_script_module(
        f"deploy_tencent_cloud_invalid_release_manifest_{case}",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    config, payload, manifest_path = _deploy_release_fixture(tmp_path)
    files = payload["files"]
    assert isinstance(files, list)
    first = files[0]
    assert isinstance(first, dict)

    if case == "missing":
        (config.repo_root / "web/out/index.html").unlink()
    elif case == "extra":
        _write_bytes(config.repo_root / "web/out/unexpected.txt", b"unexpected")
    elif case == "hash":
        first["sha256"] = "b" * 64
    elif case == "size":
        first["size_bytes"] = int(first["size_bytes"]) + 1
    elif case == "symlink":
        asset = config.repo_root / "web/out/_next/static/app.js"
        outside = _write_bytes(tmp_path / "outside.js", b"outside")
        asset.unlink()
        asset.symlink_to(outside)
    elif case == "manifest-symlink":
        outside_manifest = _write_bytes(tmp_path / "manifest.json", manifest_path.read_bytes())
        manifest_path.unlink()
        manifest_path.symlink_to(outside_manifest)
    elif case == "path-escape":
        first["path"] = "../escape.js"
    elif case == "invalid-format":
        payload["format"] = "medical-audit-web-release-manifest-v0"
    elif case == "lockfile":
        payload["lockfile_sha256"] = "b" * 64
    elif case == "duplicate":
        files.append(dict(first))
    elif case == "sha-type":
        first["sha256"] = True
    elif case == "size-type":
        first["size_bytes"] = True
    elif case == "files-type":
        payload["files"] = {"not": "a list"}
    elif case == "no-static-asset":
        first["path"] = "app.js"
        (config.repo_root / "web/out/app.js").parent.mkdir(parents=True, exist_ok=True)
        (config.repo_root / "web/out/_next/static/app.js").rename(
            config.repo_root / "web/out/app.js",
        )
    else:
        raise AssertionError(f"unhandled case: {case}")
    if case != "manifest-symlink":
        _rewrite_deploy_release_manifest(manifest_path, payload)

    with pytest.raises(module.DeployError, match=error_match):
        module._validate_web_release(config)


def test_deploy_tencent_cloud_wrong_release_source_sha_has_exact_error(
    tmp_path: Path,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_wrong_release_source_sha",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    config, _payload, _manifest_path = _deploy_release_fixture(
        tmp_path,
        source_sha="b" * 40,
    )

    with pytest.raises(module.DeployError) as exc_info:
        module._validate_web_release(config)

    assert str(exc_info.value) == (
        "web release manifest source SHA does not match approved SHA"
    )


def test_deploy_tencent_cloud_execute_forbids_skip_web_build(
    monkeypatch: MonkeyPatch,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_skip_web_build_denied",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "deploy-tencent-cloud-production.py",
            "--execute",
            "--confirm-production",
            module.DEFAULT_DOMAIN,
            "--approved-sha",
            "a" * 40,
            "--skip-web-build",
        ],
    )

    with pytest.raises(module.DeployError, match="forbids --skip-web-build"):
        module._config_from_args(module._parse_args())

    monkeypatch.setattr(
        sys,
        "argv",
        ["deploy-tencent-cloud-production.py", "--skip-web-build"],
    )
    assert module._config_from_args(module._parse_args()).skip_web_build is True


def test_deploy_tencent_cloud_execute_forbids_skip_app_rebuild(
    monkeypatch: MonkeyPatch,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_skip_app_rebuild_denied",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "deploy-tencent-cloud-production.py",
            "--execute",
            "--confirm-production",
            module.DEFAULT_DOMAIN,
            "--approved-sha",
            "a" * 40,
            "--skip-app-rebuild",
        ],
    )

    with pytest.raises(module.DeployError, match="forbids --skip-app-rebuild"):
        module._config_from_args(module._parse_args())

    monkeypatch.setattr(
        sys,
        "argv",
        ["deploy-tencent-cloud-production.py", "--skip-app-rebuild"],
    )
    assert module._config_from_args(module._parse_args()).skip_app_rebuild is True


def test_deploy_tencent_cloud_readonly_preflight_does_not_require_manifest(
    monkeypatch: MonkeyPatch,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_readonly_without_manifest",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    config = types.SimpleNamespace(execute=False, rollback=False)
    events: list[str] = []
    monkeypatch.setattr(module, "_parse_args", lambda: object())
    monkeypatch.setattr(module, "_config_from_args", lambda _args: config)
    monkeypatch.setattr(module, "_print_plan", lambda _config: None)
    monkeypatch.setattr(module, "_validate_local_state", lambda _config: None)
    monkeypatch.setattr(
        module,
        "_validate_locked_python_dependencies",
        lambda _config: None,
    )
    monkeypatch.setattr(
        module,
        "_build_static_frontend",
        lambda _config: pytest.fail("readonly preflight must not build"),
    )
    monkeypatch.setattr(
        module,
        "_validate_web_release",
        lambda _config: pytest.fail("readonly preflight must not require manifest"),
        raising=False,
    )
    monkeypatch.setattr(
        module,
        "_run_remote_preflight",
        lambda _config: events.append("ssh"),
    )

    assert module.main() == 0
    assert events == ["ssh"]


def test_deploy_tencent_cloud_execute_requires_explicit_approved_sha(
    monkeypatch: MonkeyPatch,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_approved_sha_required",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "deploy-tencent-cloud-production.py",
            "--execute",
            "--confirm-production",
            module.DEFAULT_DOMAIN,
        ],
    )

    with pytest.raises(module.DeployError, match="approved-sha"):
        module._config_from_args(module._parse_args())


def test_deploy_tencent_cloud_rollback_requires_both_sha_guards(
    monkeypatch: MonkeyPatch,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_rollback_sha_guards",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "deploy-tencent-cloud-production.py",
            "--rollback",
            "--confirm-production",
            module.DEFAULT_DOMAIN,
            "--expected-current-sha",
            "a" * 40,
        ],
    )

    with pytest.raises(module.DeployError, match="restore-sha"):
        module._config_from_args(module._parse_args())


@pytest.mark.parametrize(
    "bad_base_url",
    [
        "http://audit.lute-tlz-dddd.top",
        "https://user@audit.lute-tlz-dddd.top",
        "https://audit.lute-tlz-dddd.top.evil.example",
        "https://audit.lute-tlz-dddd.top:444",
        "https://audit.lute-tlz-dddd.top?probe=1",
        "https://audit.lute-tlz-dddd.top#fragment",
    ],
)
def test_deploy_tencent_cloud_live_modes_reject_untrusted_base_url(
    monkeypatch: MonkeyPatch,
    bad_base_url: str,
) -> None:
    module = _load_script_module(
        f"deploy_tencent_cloud_bad_base_url_{hashlib.sha256(bad_base_url.encode()).hexdigest()[:8]}",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "deploy-tencent-cloud-production.py",
            "--execute",
            "--confirm-production",
            module.DEFAULT_DOMAIN,
            "--approved-sha",
            "a" * 40,
            "--base-url",
            bad_base_url,
        ],
    )

    with pytest.raises(module.DeployError, match="base-url"):
        module._config_from_args(module._parse_args())


def test_deploy_tencent_cloud_live_base_url_allows_explicit_default_https_port(
    monkeypatch: MonkeyPatch,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_explicit_https_port",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "deploy-tencent-cloud-production.py",
            "--execute",
            "--confirm-production",
            module.DEFAULT_DOMAIN,
            "--approved-sha",
            "a" * 40,
            "--base-url",
            f"https://{module.DEFAULT_DOMAIN}:443/",
        ],
    )

    config = module._config_from_args(module._parse_args())

    assert config.base_url == module.DEFAULT_BASE_URL


def test_deploy_tencent_cloud_execute_forbids_skip_smoke(
    monkeypatch: MonkeyPatch,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_skip_smoke_denied",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "deploy-tencent-cloud-production.py",
            "--execute",
            "--confirm-production",
            module.DEFAULT_DOMAIN,
            "--approved-sha",
            "a" * 40,
            "--skip-smoke",
        ],
    )

    with pytest.raises(module.DeployError, match="forbids --skip-smoke"):
        module._config_from_args(module._parse_args())


def test_deploy_tencent_cloud_first_legacy_migration_requires_explicit_flag(
    monkeypatch: MonkeyPatch,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_legacy_migration_flag",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "deploy-tencent-cloud-production.py",
            "--execute",
            "--confirm-production",
            module.DEFAULT_DOMAIN,
            "--approved-sha",
            "a" * 40,
            "--allow-first-legacy-migration",
        ],
    )

    config = module._config_from_args(module._parse_args())

    assert config.allow_first_legacy_migration is True


def test_deploy_tencent_cloud_execute_rejects_release_branch(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_release_branch_denied",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    monkeypatch.setattr(module, "_run", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        module,
        "_run_capture",
        lambda args, *, cwd: "codex/release-candidate\n",
    )
    config = types.SimpleNamespace(repo_root=tmp_path, approved_sha="a" * 40)

    with pytest.raises(module.DeployError, match="main branch"):
        module._validate_release_source(config)


def test_deploy_tencent_cloud_execute_rejects_unapproved_sha(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_unapproved_sha_denied",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    outputs = {
        ("git", "symbolic-ref", "--quiet", "--short", "HEAD"): "main\n",
        ("git", "rev-parse", "HEAD"): f"{'b' * 40}\n",
        ("git", "rev-parse", "origin/main"): f"{'b' * 40}\n",
    }
    monkeypatch.setattr(module, "_run", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        module,
        "_run_capture",
        lambda args, *, cwd: outputs[tuple(args)],
    )
    config = types.SimpleNamespace(repo_root=tmp_path, approved_sha="a" * 40)

    with pytest.raises(module.DeployError, match="approved SHA"):
        module._validate_release_source(config)


def test_deploy_tencent_cloud_preflight_uses_app_proxy_topology(
    monkeypatch: MonkeyPatch,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_preflight_proxy_topology",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    captured_scripts: list[str] = []

    def fake_ssh(config: object, script: str) -> None:
        del config
        captured_scripts.append(script)

    monkeypatch.setattr(module, "_ssh", fake_ssh)
    config = types.SimpleNamespace(
        remote_app_dir="/opt/medical-audit/app",
        remote_web_dir="/var/www/audit",
    )

    module._run_remote_preflight(config)

    assert len(captured_scripts) == 1
    script = captured_scripts[0]
    assert "docker inspect medical_audit_app" in script
    assert "curl -fsS http://127.0.0.1:18080/health" in script
    assert "docker exec ai_video_nginx nginx -t >/dev/null 2>&1" in script
    assert "production nginx configuration test failed" in script
    assert "sudo -n -- true" in script
    assert "WARNING shared-nginx-test-failed" not in script
    assert "/knowledge-base/catalog" not in script
    assert "X-User-Id" not in script
    for forbidden in (
        "/documents",
        "auth_headers",
        "X-Role",
        "X-Project-Key",
        "X-Tenant-Id",
    ):
        assert forbidden not in script
    assert "/index/search-backend" not in script
    assert "/tmp/medical-audit-nginx-test.log" not in script
    assert "/var/www/audit -> /var/www/audit" not in script


def test_deploy_tencent_cloud_static_sync_targets_owned_incoming_without_delete(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_versioned_static_sync",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    run_command = module._run
    commands: list[tuple[list[str], dict[str, object]]] = []
    monkeypatch.setattr(
        module,
        "_run",
        lambda args, *, cwd, **kwargs: commands.append((list(args), kwargs)),
    )
    web_out = tmp_path / "web" / "out"
    web_out.mkdir(parents=True)
    approved_sha = "a" * 40
    config = types.SimpleNamespace(
        repo_root=tmp_path,
        ssh_target="ubuntu@example.test",
        ssh_key=tmp_path / "deploy.pem",
        remote_web_dir="/var/www/audit",
        remote_app_dir="/opt/medical-audit/app",
        approved_sha=approved_sha,
    )

    module._sync_application(config, "owner-token")
    module._sync_static_frontend(config, "owner-token")

    assert len(commands) == 2
    app_command, app_kwargs = commands[0]
    static_command, static_kwargs = commands[1]
    assert "--delete" in app_command
    assert "--delete" not in static_command
    assert static_command[-1] == (
        "ubuntu@example.test:/var/www/audit/releases/"
        f"{approved_sha}.incoming/"
    )
    for command, kwargs in commands:
        assert "--timeout" in command
        assert int(command[command.index("--timeout") + 1]) > 0
        transport = command[command.index("-e") + 1]
        assert "ConnectTimeout=" in transport
        assert "ServerAliveInterval=" in transport
        assert "ServerAliveCountMax=" in transport
        assert "owner-token" in command[command.index("--rsync-path") + 1]
        assert kwargs["remote_outcome_unknown"] is True
        assert int(kwargs["timeout_seconds"]) > 0
    assert app_kwargs == static_kwargs

    def fail_partial_rsync(*_args: object, **_kwargs: object) -> None:
        raise subprocess.CalledProcessError(23, ["rsync"])

    monkeypatch.setattr(module.subprocess, "run", fail_partial_rsync)
    with pytest.raises(module.RemoteOutcomeUnknownError):
        run_command(
            ["rsync", "source", "target"],
            cwd=tmp_path,
            remote_outcome_unknown=True,
        )


def test_deploy_tencent_cloud_remote_lock_is_owner_checked_and_fail_closed(
    tmp_path: Path,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_remote_lock_behavior",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    lock_dir = tmp_path / "production.deploy.lock"
    acquire_builder = getattr(
        module,
        "_remote_lock_acquire_script",
        lambda _lock_dir, _token: "true",
    )
    release_builder = getattr(
        module,
        "_remote_lock_release_script",
        lambda _lock_dir, _token: "true",
    )

    first = subprocess.run(
        ["bash", "-lc", acquire_builder(str(lock_dir), "owner-a")],
        check=False,
        capture_output=True,
        text=True,
    )
    assert first.returncode == 0
    assert (lock_dir / "owner").is_file()
    assert (lock_dir / "owner").read_text(encoding="utf-8").strip() == "owner-a"

    contender = subprocess.run(
        ["bash", "-lc", acquire_builder(str(lock_dir), "owner-b")],
        check=False,
        capture_output=True,
        text=True,
    )
    assert contender.returncode != 0
    assert (lock_dir / "owner").read_text(encoding="utf-8").strip() == "owner-a"

    wrong_release = subprocess.run(
        ["bash", "-lc", release_builder(str(lock_dir), "owner-b")],
        check=False,
        capture_output=True,
        text=True,
    )
    assert wrong_release.returncode != 0
    assert lock_dir.is_dir()

    owner_release = subprocess.run(
        ["bash", "-lc", release_builder(str(lock_dir), "owner-a")],
        check=False,
        capture_output=True,
        text=True,
    )
    assert owner_release.returncode == 0
    assert not lock_dir.exists()


def test_deploy_tencent_cloud_remote_release_verifier_recomputes_file_hashes(
    tmp_path: Path,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_remote_release_verifier",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    source_sha = "a" * 40
    release = tmp_path / source_sha
    static_asset = release / "_next" / "static" / "app.js"
    static_asset.parent.mkdir(parents=True)
    static_asset.write_bytes(b"static-v1")
    (release / "index.html").write_bytes(b"<html>release</html>")
    files = []
    for relative_path in ("_next/static/app.js", "index.html"):
        content = (release / relative_path).read_bytes()
        files.append(
            {
                "path": relative_path,
                "sha256": hashlib.sha256(content).hexdigest(),
                "size_bytes": len(content),
            },
        )
    manifest = {
        "files": files,
        "format": "medical-audit-web-release-manifest-v1",
        "lockfile_sha256": "b" * 64,
        "node_version": "v22.0.0",
        "pnpm_version": "9.0.0",
        "public_build_variables": {
            "NEXT_PUBLIC_AUDIT_ORG_LOGO": None,
            "NEXT_PUBLIC_AUDIT_ORG_NAME": None,
            "NEXT_PUBLIC_MEDICAL_AUDIT_AGENT_EXTENSION_PACK": None,
            "NEXT_PUBLIC_MEDICAL_AUDIT_REPLICA_API_READS": None,
        },
        "source_sha": source_sha,
    }
    manifest_bytes = (
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")
    (release / "release-manifest.json").write_bytes(manifest_bytes)
    verifier = getattr(module, "_remote_release_verifier_code", lambda: "pass")()
    compile(verifier, "<remote-release-verifier>", "exec")
    command = [
        sys.executable,
        "-c",
        verifier,
        str(release),
        source_sha,
        hashlib.sha256(manifest_bytes).hexdigest(),
        "2",
        "_next/static/app.js",
        hashlib.sha256(b"static-v1").hexdigest(),
    ]

    valid = subprocess.run(command, check=False, capture_output=True, text=True)
    assert valid.returncode == 0, valid.stderr

    static_asset.write_bytes(b"tampered")
    tampered = subprocess.run(command, check=False, capture_output=True, text=True)
    assert tampered.returncode != 0


def test_deploy_tencent_cloud_incoming_creation_never_removes_existing_owner(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_incoming_owner",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    prepare = getattr(module, "_prepare_remote_release_incoming", None)
    assert prepare is not None
    approved_sha = "a" * 40
    remote_app_dir = tmp_path / "app"
    remote_web_dir = tmp_path / "web"
    remote_app_dir.mkdir()
    remote_web_dir.mkdir()
    lock_dir = Path(f"{remote_app_dir}.deploy.lock")
    lock_dir.mkdir()
    (lock_dir / "owner").write_text("owner-token\n", encoding="utf-8")
    scripts: list[str] = []
    monkeypatch.setattr(module, "_ssh", lambda _config, script: scripts.append(script))
    config = types.SimpleNamespace(
        remote_app_dir=str(remote_app_dir),
        remote_web_dir=str(remote_web_dir),
        approved_sha=approved_sha,
    )

    prepare(config, "owner-token")
    assert len(scripts) == 1
    syntax = subprocess.run(
        ["bash", "-n"],
        input=scripts[0],
        check=False,
        capture_output=True,
        text=True,
    )
    assert syntax.returncode == 0, syntax.stderr
    first = subprocess.run(
        ["bash", "-c", scripts[0]],
        check=False,
        capture_output=True,
        text=True,
    )
    assert first.returncode == 0, first.stderr
    incoming = remote_web_dir / "releases" / f"{approved_sha}.incoming"
    owner = Path(f"{incoming}.owner")
    sentinel = incoming / "foreign-sentinel"
    sentinel.write_text("preserve-me", encoding="utf-8")
    owner.write_text("foreign-owner\n", encoding="utf-8")

    contender = subprocess.run(
        ["bash", "-c", scripts[0]],
        check=False,
        capture_output=True,
        text=True,
    )
    assert contender.returncode != 0
    assert sentinel.read_text(encoding="utf-8") == "preserve-me"
    assert owner.read_text(encoding="utf-8").strip() == "foreign-owner"


def test_deploy_tencent_cloud_promotion_reuses_only_identical_immutable_release(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_immutable_promotion",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    promote = getattr(module, "_verify_and_promote_remote_release", None)
    assert promote is not None
    approved_sha = "a" * 40
    remote_app_dir = tmp_path / "app"
    remote_web_dir = tmp_path / "web"
    remote_app_dir.mkdir()
    (remote_web_dir / "releases").mkdir(parents=True)
    lock_dir = Path(f"{remote_app_dir}.deploy.lock")
    lock_dir.mkdir()
    (lock_dir / "owner").write_text("owner-token\n", encoding="utf-8")
    incoming = remote_web_dir / "releases" / f"{approved_sha}.incoming"
    immutable = remote_web_dir / "releases" / approved_sha

    def write_release(root: Path) -> tuple[str, str]:
        static = root / "_next" / "static" / "app.js"
        static.parent.mkdir(parents=True)
        static.write_bytes(b"static-v1")
        (root / "index.html").write_bytes(b"<html>release</html>")
        files = []
        for path in ("_next/static/app.js", "index.html"):
            content = (root / path).read_bytes()
            files.append(
                {
                    "path": path,
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "size_bytes": len(content),
                },
            )
        payload = {
            "files": files,
            "format": "medical-audit-web-release-manifest-v1",
            "lockfile_sha256": "b" * 64,
            "node_version": "v22.0.0",
            "pnpm_version": "9.0.0",
            "public_build_variables": {
                "NEXT_PUBLIC_AUDIT_ORG_LOGO": None,
                "NEXT_PUBLIC_AUDIT_ORG_NAME": None,
                "NEXT_PUBLIC_MEDICAL_AUDIT_AGENT_EXTENSION_PACK": None,
                "NEXT_PUBLIC_MEDICAL_AUDIT_REPLICA_API_READS": None,
            },
            "source_sha": approved_sha,
        }
        manifest = (
            json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode()
        (root / "release-manifest.json").write_bytes(manifest)
        return (
            hashlib.sha256(manifest).hexdigest(),
            hashlib.sha256(b"static-v1").hexdigest(),
        )

    manifest_sha, static_sha = write_release(incoming)
    Path(f"{incoming}.owner").write_text("owner-token\n", encoding="utf-8")
    evidence = module.ReleaseEvidence(
        manifest_sha256=manifest_sha,
        manifest_file_count=2,
        static_asset_path="_next/static/app.js",
        static_asset_sha256=static_sha,
    )
    scripts: list[str] = []
    monkeypatch.setattr(module, "_ssh", lambda _config, script: scripts.append(script))
    config = types.SimpleNamespace(
        remote_app_dir=str(remote_app_dir),
        remote_web_dir=str(remote_web_dir),
        approved_sha=approved_sha,
    )
    promote(config, "owner-token", evidence)
    assert len(scripts) == 1
    syntax = subprocess.run(
        ["bash", "-n"],
        input=scripts[0],
        check=False,
        capture_output=True,
        text=True,
    )
    assert syntax.returncode == 0, syntax.stderr
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_mv = fake_bin / "mv"
    fake_mv.write_text(
        "#!/bin/sh\n"
        "[ \"$1\" = '-T' ] && shift\n"
        "[ \"$1\" = '--' ] && shift\n"
        "exec /bin/mv \"$@\"\n",
        encoding="utf-8",
    )
    fake_mv.chmod(0o755)
    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}:{environment['PATH']}"

    first = subprocess.run(
        ["bash", "-c", scripts[0]],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    assert first.returncode == 0, first.stderr
    assert immutable.is_dir()
    immutable_inode = immutable.stat().st_ino

    shutil.copytree(immutable, incoming)
    Path(f"{incoming}.owner").write_text("owner-token\n", encoding="utf-8")
    identical = subprocess.run(
        ["bash", "-c", scripts[0]],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    assert identical.returncode == 0, identical.stderr
    assert immutable.stat().st_ino == immutable_inode

    shutil.copytree(immutable, incoming)
    Path(f"{incoming}.owner").write_text("owner-token\n", encoding="utf-8")
    (immutable / "index.html").write_bytes(b"tampered-immutable")
    rejected = subprocess.run(
        ["bash", "-c", scripts[0]],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    assert rejected.returncode != 0
    assert (immutable / "index.html").read_bytes() == b"tampered-immutable"


def test_deploy_tencent_cloud_execute_acquires_lock_and_writes_marker_after_smoke(
    monkeypatch: MonkeyPatch,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_atomic_order",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    config = types.SimpleNamespace(
        execute=True,
        rollback=False,
        apply_schema=False,
        approved_sha="a" * 40,
        skip_app_rebuild=False,
    )
    _patch_deploy_execute_snapshot(monkeypatch, module, config)
    evidence = module.ReleaseEvidence(
        manifest_sha256="b" * 64,
        manifest_file_count=2,
        static_asset_path="_next/static/chunks/app.js",
        static_asset_sha256="c" * 64,
    )
    events: list[str] = []
    monkeypatch.setattr(module, "_parse_args", lambda: object())
    monkeypatch.setattr(module, "_config_from_args", lambda _args: config)
    monkeypatch.setattr(module, "_print_plan", lambda _config: None)
    monkeypatch.setattr(module, "_validate_local_state", lambda _config: None)
    monkeypatch.setattr(module, "_validate_locked_python_dependencies", lambda _config: None)
    monkeypatch.setattr(module, "_build_static_frontend", lambda _config: events.append("build"))
    monkeypatch.setattr(module, "_validate_web_release", lambda _config: evidence)
    monkeypatch.setattr(module, "_run_remote_preflight", lambda _config: events.append("preflight"))
    monkeypatch.setattr(
        module,
        "_acquire_remote_deploy_lock",
        lambda _config: events.append("lock") or "owner-token",
        raising=False,
    )
    monkeypatch.setattr(
        module,
        "_release_remote_deploy_lock",
        lambda _config, _token: events.append("unlock"),
        raising=False,
    )
    for name in (
        "_create_remote_backups",
        "_cleanup_remote_sync_artifacts",
        "_sync_application",
        "_prepare_remote_release_incoming",
        "_sync_static_frontend",
        "_verify_and_promote_remote_release",
        "_rebuild_application",
        "_activate_remote_release",
        "_run_remote_post_checks",
        "_verify_remote_release_commit_point",
    ):
        monkeypatch.setattr(
            module,
            name,
            lambda *_args, _name=name, **_kwargs: events.append(_name),
            raising=False,
        )
    monkeypatch.setattr(
        module,
        "_run_production_smoke",
        lambda _config: events.append("smoke"),
    )
    monkeypatch.setattr(
        module,
        "_write_remote_deploy_sha",
        lambda *_args: events.append("marker"),
    )

    assert module.main() == 0
    assert "lock" in events
    assert events.index("lock") < events.index("_create_remote_backups")
    assert events.index("smoke") < events.index("marker")
    assert events[-1] == "unlock"


def test_deploy_tencent_cloud_precommit_failure_restores_activation_and_keeps_marker(
    monkeypatch: MonkeyPatch,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_precommit_restore",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    config = types.SimpleNamespace(
        execute=True,
        rollback=False,
        apply_schema=False,
        approved_sha="a" * 40,
        skip_app_rebuild=False,
    )
    _patch_deploy_execute_snapshot(monkeypatch, module, config)
    evidence = module.ReleaseEvidence("b" * 64, 2, "_next/static/app.js", "c" * 64)
    events: list[str] = []
    monkeypatch.setattr(module, "_parse_args", lambda: object())
    monkeypatch.setattr(module, "_config_from_args", lambda _args: config)
    monkeypatch.setattr(module, "_print_plan", lambda _config: None)
    monkeypatch.setattr(module, "_validate_local_state", lambda _config: None)
    monkeypatch.setattr(module, "_validate_locked_python_dependencies", lambda _config: None)
    monkeypatch.setattr(module, "_build_static_frontend", lambda _config: None)
    monkeypatch.setattr(module, "_validate_web_release", lambda _config: evidence)
    monkeypatch.setattr(module, "_run_remote_preflight", lambda _config: None)
    monkeypatch.setattr(module, "_acquire_remote_deploy_lock", lambda _config: "token")
    monkeypatch.setattr(
        module,
        "_release_remote_deploy_lock",
        lambda _config, _token: events.append("unlock"),
    )
    for name in (
        "_create_remote_backups",
        "_cleanup_remote_sync_artifacts",
        "_sync_application",
        "_prepare_remote_release_incoming",
        "_sync_static_frontend",
        "_verify_and_promote_remote_release",
        "_rebuild_application",
        "_run_remote_post_checks",
    ):
        monkeypatch.setattr(module, name, lambda *_args: None)
    monkeypatch.setattr(
        module,
        "_activate_remote_release",
        lambda *_args: events.append("activate"),
    )
    monkeypatch.setattr(
        module,
        "_verify_remote_release_commit_point",
        lambda *_args: (_ for _ in ()).throw(module.DeployError("public hash failed")),
        raising=False,
    )
    monkeypatch.setattr(
        module,
        "_restore_remote_activation",
        lambda *_args: events.append("restore"),
        raising=False,
    )
    monkeypatch.setattr(
        module,
        "_write_remote_deploy_sha",
        lambda *_args: events.append("marker"),
    )
    monkeypatch.setattr(module, "_run_production_smoke", lambda _config: None)

    assert module.main() == 2
    assert events == ["activate", "restore"]


def test_deploy_tencent_cloud_marker_commit_error_retains_lock_without_restore(
    monkeypatch: MonkeyPatch,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_marker_commit_uncertain",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    config = types.SimpleNamespace(
        execute=True,
        rollback=False,
        apply_schema=False,
        approved_sha="a" * 40,
        skip_app_rebuild=False,
    )
    _patch_deploy_execute_snapshot(monkeypatch, module, config)
    evidence = module.ReleaseEvidence("b" * 64, 2, "_next/static/app.js", "c" * 64)
    events: list[str] = []
    monkeypatch.setattr(module, "_parse_args", lambda: object())
    monkeypatch.setattr(module, "_config_from_args", lambda _args: config)
    monkeypatch.setattr(module, "_print_plan", lambda _config: None)
    monkeypatch.setattr(module, "_validate_local_state", lambda _config: None)
    monkeypatch.setattr(module, "_validate_locked_python_dependencies", lambda _config: None)
    monkeypatch.setattr(module, "_build_static_frontend", lambda _config: None)
    monkeypatch.setattr(module, "_validate_web_release", lambda _config: evidence)
    monkeypatch.setattr(module, "_run_remote_preflight", lambda _config: None)
    monkeypatch.setattr(module, "_acquire_remote_deploy_lock", lambda _config: "token")
    monkeypatch.setattr(
        module,
        "_release_remote_deploy_lock",
        lambda *_args: events.append("unlock"),
    )
    for name in (
        "_create_remote_backups",
        "_cleanup_remote_sync_artifacts",
        "_sync_application",
        "_prepare_remote_release_incoming",
        "_sync_static_frontend",
        "_verify_and_promote_remote_release",
        "_rebuild_application",
        "_run_remote_post_checks",
        "_verify_remote_release_commit_point",
    ):
        monkeypatch.setattr(module, name, lambda *_args: None)
    monkeypatch.setattr(
        module,
        "_activate_remote_release",
        lambda *_args: events.append("activate"),
    )
    monkeypatch.setattr(
        module,
        "_restore_remote_activation",
        lambda *_args: events.append("restore"),
    )
    monkeypatch.setattr(module, "_run_production_smoke", lambda _config: None)
    monkeypatch.setattr(
        module,
        "_write_remote_deploy_sha",
        lambda *_args: (
            events.append("marker")
            or (_ for _ in ()).throw(module.DeployError("marker outcome unknown"))
        ),
    )

    assert module.main() == 2
    assert events == ["activate", "marker"]


def test_deploy_tencent_cloud_rsync_timeout_retains_remote_lock(
    monkeypatch: MonkeyPatch,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_rsync_timeout_lock",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    outcome_error = getattr(module, "RemoteOutcomeUnknownError", None)
    assert outcome_error is not None
    config = types.SimpleNamespace(
        execute=True,
        rollback=False,
        apply_schema=False,
        approved_sha="a" * 40,
        skip_app_rebuild=False,
        skip_web_build=False,
    )
    _patch_deploy_execute_snapshot(monkeypatch, module, config)
    evidence = module.ReleaseEvidence("b" * 64, 2, "_next/static/app.js", "c" * 64)
    events: list[str] = []
    monkeypatch.setattr(module, "_parse_args", lambda: object())
    monkeypatch.setattr(module, "_config_from_args", lambda _args: config)
    monkeypatch.setattr(module, "_print_plan", lambda _config: None)
    monkeypatch.setattr(module, "_validate_local_state", lambda _config: None)
    monkeypatch.setattr(module, "_validate_locked_python_dependencies", lambda _config: None)
    monkeypatch.setattr(module, "_build_static_frontend", lambda _config: None)
    monkeypatch.setattr(module, "_validate_web_release", lambda _config: evidence)
    monkeypatch.setattr(module, "_run_remote_preflight", lambda _config: None)
    monkeypatch.setattr(
        module,
        "_acquire_remote_deploy_lock",
        lambda _config: events.append("lock") or "token",
    )
    monkeypatch.setattr(
        module,
        "_release_remote_deploy_lock",
        lambda *_args: events.append("unlock"),
    )
    monkeypatch.setattr(module, "_create_remote_backups", lambda *_args: None)
    monkeypatch.setattr(module, "_cleanup_remote_sync_artifacts", lambda *_args: None)
    monkeypatch.setattr(
        module,
        "_sync_application",
        lambda *_args: (_ for _ in ()).throw(outcome_error("rsync timed out")),
    )

    assert module.main() == 2
    assert events == ["lock"]


def test_deploy_tencent_cloud_activation_unknown_retains_lock_without_reconcile(
    monkeypatch: MonkeyPatch,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_activation_unknown_lock",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    outcome_error = getattr(module, "RemoteOutcomeUnknownError", None)
    assert outcome_error is not None
    config = types.SimpleNamespace(
        execute=True,
        rollback=False,
        apply_schema=False,
        approved_sha="a" * 40,
        skip_app_rebuild=False,
        skip_web_build=False,
    )
    _patch_deploy_execute_snapshot(monkeypatch, module, config)
    evidence = module.ReleaseEvidence("b" * 64, 2, "_next/static/app.js", "c" * 64)
    events: list[str] = []
    monkeypatch.setattr(module, "_parse_args", lambda: object())
    monkeypatch.setattr(module, "_config_from_args", lambda _args: config)
    monkeypatch.setattr(module, "_print_plan", lambda _config: None)
    monkeypatch.setattr(module, "_validate_local_state", lambda _config: None)
    monkeypatch.setattr(module, "_validate_locked_python_dependencies", lambda _config: None)
    monkeypatch.setattr(module, "_build_static_frontend", lambda _config: None)
    monkeypatch.setattr(module, "_validate_web_release", lambda _config: evidence)
    monkeypatch.setattr(module, "_run_remote_preflight", lambda _config: None)
    monkeypatch.setattr(
        module,
        "_acquire_remote_deploy_lock",
        lambda _config: events.append("lock") or "token",
    )
    monkeypatch.setattr(
        module,
        "_release_remote_deploy_lock",
        lambda *_args: events.append("unlock"),
    )
    for name in (
        "_create_remote_backups",
        "_cleanup_remote_sync_artifacts",
        "_sync_application",
        "_prepare_remote_release_incoming",
        "_sync_static_frontend",
        "_verify_and_promote_remote_release",
        "_rebuild_application",
    ):
        monkeypatch.setattr(module, name, lambda *_args: None)
    monkeypatch.setattr(
        module,
        "_activate_remote_release",
        lambda *_args: (
            events.append("activate")
            or (_ for _ in ()).throw(outcome_error("activation restore outcome unknown"))
        ),
    )
    monkeypatch.setattr(
        module,
        "_restore_remote_activation",
        lambda *_args: events.append("reconcile"),
    )

    assert module.main() == 2
    assert events == ["lock", "activate"]


def test_deploy_tencent_cloud_activation_precondition_failure_does_not_restore_old_transaction(
    monkeypatch: MonkeyPatch,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_activation_precondition_failure",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    config = types.SimpleNamespace(
        execute=True,
        rollback=False,
        apply_schema=False,
        approved_sha="a" * 40,
        skip_app_rebuild=False,
        skip_web_build=False,
    )
    _patch_deploy_execute_snapshot(monkeypatch, module, config)
    evidence = module.ReleaseEvidence("b" * 64, 2, "_next/static/app.js", "c" * 64)
    events: list[str] = []
    monkeypatch.setattr(module, "_parse_args", lambda: object())
    monkeypatch.setattr(module, "_config_from_args", lambda _args: config)
    monkeypatch.setattr(module, "_print_plan", lambda _config: None)
    monkeypatch.setattr(module, "_validate_local_state", lambda _config: None)
    monkeypatch.setattr(module, "_validate_locked_python_dependencies", lambda _config: None)
    monkeypatch.setattr(module, "_build_static_frontend", lambda _config: None)
    monkeypatch.setattr(module, "_validate_web_release", lambda _config: evidence)
    monkeypatch.setattr(module, "_run_remote_preflight", lambda _config: None)
    monkeypatch.setattr(
        module,
        "_acquire_remote_deploy_lock",
        lambda _config: events.append("lock") or "token",
    )
    monkeypatch.setattr(
        module,
        "_release_remote_deploy_lock",
        lambda *_args: events.append("unlock"),
    )
    for name in (
        "_create_remote_backups",
        "_cleanup_remote_sync_artifacts",
        "_sync_application",
        "_prepare_remote_release_incoming",
        "_sync_static_frontend",
        "_verify_and_promote_remote_release",
    ):
        monkeypatch.setattr(module, name, lambda *_args: None)
    monkeypatch.setattr(
        module,
        "_rebuild_application",
        lambda *_args: events.append("rebuild"),
    )
    monkeypatch.setattr(
        module,
        "_activate_remote_release",
        lambda *_args: (
            events.append("activate")
            or (_ for _ in ()).throw(subprocess.CalledProcessError(77, ["ssh"]))
        ),
    )
    monkeypatch.setattr(
        module,
        "_restore_remote_activation",
        lambda *_args: events.append("restore"),
    )

    assert module.main() == 77
    assert events == ["lock", "rebuild", "activate"]


def test_deploy_tencent_cloud_rebuild_failure_retains_lock(
    monkeypatch: MonkeyPatch,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_rebuild_failure_lock",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    config = types.SimpleNamespace(
        execute=True,
        rollback=False,
        apply_schema=False,
        approved_sha="a" * 40,
        skip_app_rebuild=False,
        skip_web_build=False,
    )
    events: list[str] = []
    _patch_deploy_locked_path(monkeypatch, module, config, events)
    monkeypatch.setattr(
        module,
        "_rebuild_application",
        lambda *_args: (
            events.append("rebuild")
            or (_ for _ in ()).throw(module.DeployError("rebuild failed"))
        ),
    )
    monkeypatch.setattr(
        module,
        "_restore_remote_activation",
        lambda *_args: events.append("restore"),
    )

    assert module.main() == 2
    assert events == ["lock", "rebuild"]


def test_deploy_tencent_cloud_schema_side_effect_retains_lock_on_later_failure(
    monkeypatch: MonkeyPatch,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_schema_side_effect_lock",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    config = types.SimpleNamespace(
        execute=True,
        rollback=False,
        apply_schema=True,
        approved_sha="a" * 40,
        skip_app_rebuild=True,
        skip_web_build=False,
    )
    events: list[str] = []
    _patch_deploy_locked_path(monkeypatch, module, config, events)
    monkeypatch.setattr(
        module,
        "_apply_schema",
        lambda *_args: events.append("schema"),
    )
    monkeypatch.setattr(
        module,
        "_activate_remote_release",
        lambda *_args: (
            events.append("activate")
            or (_ for _ in ()).throw(module.DeployError("activation precondition failed"))
        ),
    )
    monkeypatch.setattr(
        module,
        "_restore_remote_activation",
        lambda *_args: events.append("restore"),
    )

    assert module.main() == 2
    assert events == ["lock", "schema", "activate"]


def test_deploy_tencent_cloud_partial_schema_failure_retains_lock(
    monkeypatch: MonkeyPatch,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_partial_schema_failure_lock",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    config = types.SimpleNamespace(
        execute=True,
        rollback=False,
        apply_schema=True,
        approved_sha="a" * 40,
        skip_app_rebuild=True,
        skip_web_build=False,
    )
    events: list[str] = []
    _patch_deploy_locked_path(monkeypatch, module, config, events)
    monkeypatch.setattr(
        module,
        "_apply_schema",
        lambda *_args: (
            events.append("schema-partial-side-effect")
            or (_ for _ in ()).throw(module.DeployError("schema failed after DDL"))
        ),
    )

    assert module.main() == 2
    assert events == ["lock", "schema-partial-side-effect"]


def test_deploy_tencent_cloud_activation_only_failure_restores_and_retains_lock(
    monkeypatch: MonkeyPatch,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_activation_only_failure_lock",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    config = types.SimpleNamespace(
        execute=True,
        rollback=False,
        apply_schema=False,
        approved_sha="a" * 40,
        skip_app_rebuild=True,
        skip_web_build=False,
    )
    events: list[str] = []
    _patch_deploy_locked_path(monkeypatch, module, config, events)
    monkeypatch.setattr(
        module,
        "_activate_remote_release",
        lambda *_args: events.append("activate"),
    )
    monkeypatch.setattr(
        module,
        "_run_remote_post_checks",
        lambda *_args: (
            events.append("postcheck-failure")
            or (_ for _ in ()).throw(module.DeployError("postcheck failed"))
        ),
    )
    monkeypatch.setattr(
        module,
        "_restore_remote_activation",
        lambda *_args: events.append("restore"),
    )

    assert module.main() == 2
    assert events == ["lock", "activate", "postcheck-failure", "restore"]


def test_deploy_tencent_cloud_early_determinate_failure_still_unlocks(
    monkeypatch: MonkeyPatch,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_early_failure_unlock",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    config = types.SimpleNamespace(
        execute=True,
        rollback=False,
        apply_schema=False,
        approved_sha="a" * 40,
        skip_app_rebuild=True,
        skip_web_build=False,
    )
    events: list[str] = []
    _patch_deploy_locked_path(monkeypatch, module, config, events)
    monkeypatch.setattr(
        module,
        "_create_remote_backups",
        lambda *_args: (
            events.append("early-failure")
            or (_ for _ in ()).throw(module.DeployError("backup precondition failed"))
        ),
    )

    assert module.main() == 2
    assert events == ["lock", "early-failure", "unlock"]


@pytest.mark.parametrize(
    "interrupt",
    [KeyboardInterrupt(), SystemExit(9)],
    ids=["keyboard-interrupt", "system-exit"],
)
def test_deploy_tencent_cloud_base_exception_retains_lock_without_restore(
    monkeypatch: MonkeyPatch,
    interrupt: BaseException,
) -> None:
    module = _load_script_module(
        f"deploy_tencent_cloud_{type(interrupt).__name__.lower()}_lock",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    config = types.SimpleNamespace(
        execute=True,
        rollback=False,
        apply_schema=False,
        approved_sha="a" * 40,
        skip_app_rebuild=False,
        skip_web_build=False,
    )
    _patch_deploy_execute_snapshot(monkeypatch, module, config)
    evidence = module.ReleaseEvidence("b" * 64, 2, "_next/static/app.js", "c" * 64)
    events: list[str] = []
    monkeypatch.setattr(module, "_parse_args", lambda: object())
    monkeypatch.setattr(module, "_config_from_args", lambda _args: config)
    monkeypatch.setattr(module, "_print_plan", lambda _config: None)
    monkeypatch.setattr(module, "_validate_local_state", lambda _config: None)
    monkeypatch.setattr(module, "_validate_locked_python_dependencies", lambda _config: None)
    monkeypatch.setattr(module, "_build_static_frontend", lambda _config: None)
    monkeypatch.setattr(module, "_validate_web_release", lambda _config: evidence)
    monkeypatch.setattr(module, "_run_remote_preflight", lambda _config: None)
    monkeypatch.setattr(
        module,
        "_acquire_remote_deploy_lock",
        lambda _config: events.append("lock") or "token",
    )
    monkeypatch.setattr(
        module,
        "_release_remote_deploy_lock",
        lambda *_args: events.append("unlock"),
    )
    for name in (
        "_create_remote_backups",
        "_cleanup_remote_sync_artifacts",
        "_sync_application",
        "_prepare_remote_release_incoming",
        "_sync_static_frontend",
        "_verify_and_promote_remote_release",
        "_rebuild_application",
    ):
        monkeypatch.setattr(module, name, lambda *_args: None)
    monkeypatch.setattr(
        module,
        "_activate_remote_release",
        lambda *_args: events.append("activate"),
    )
    monkeypatch.setattr(
        module,
        "_run_remote_post_checks",
        lambda *_args: (_ for _ in ()).throw(interrupt),
    )
    monkeypatch.setattr(
        module,
        "_restore_remote_activation",
        lambda *_args: events.append("restore"),
    )

    with pytest.raises(type(interrupt)):
        module.main()
    assert events == ["lock", "activate"]


def test_nginx_audit_fragment_uses_versioned_current_roots_and_cache_contract() -> None:
    fragment = Path("configs/deploy/tencent-cloud/nginx-audit-server.conf").read_text(
        encoding="utf-8",
    )

    assert "client_max_body_size 21m;" in fragment
    assert "client_max_body_size 20m;" not in fragment
    assert fragment.count("root /var/www/audit/current;") == 3
    assert "root /var/www/audit;" not in fragment
    assert 'Cache-Control "public, max-age=31536000, immutable"' in fragment
    assert 'Cache-Control "no-store, no-cache, must-revalidate"' in fragment


def test_deploy_tencent_cloud_nginx_patch_is_secret_safe_exact_and_idempotent(
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_nginx_patch",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    patcher = getattr(module, "_patch_nginx_audit_locations", None)
    assert patcher is not None
    secret = "SECRET-SENTINEL-never-log"
    other_server = b"""server {
    server_name other.example.test;
    location / { root /srv/other; }
}
"""
    http_audit_server = b"""server {
    listen 80 default_server;
    server_name audit.lute-tlz-dddd.top;
    location / { return 301 https://audit.lute-tlz-dddd.top$request_uri; }
}
"""
    audit_server = f"""server {{
    listen 443 ssl;
    server_name audit.lute-tlz-dddd.top;
    ssl_certificate /etc/nginx/audit.crt;
    ssl_certificate_key /etc/nginx/audit.key;
    set $quoted "brace-{{-inside-string";
    # comment with }} brace
    location / {{ root /var/www/audit; }}
    location /api/ {{
        proxy_set_header X-API-Key "{secret}";
        proxy_pass http://medical_audit_app;
    }}
}}
""".encode()
    source = (
        b"events {}\nhttp {\n"
        + other_server
        + http_audit_server
        + audit_server
        + b"}\n"
    )
    fragment = Path("configs/deploy/tencent-cloud/nginx-audit-server.conf").read_bytes()

    patched = patcher(source, fragment)

    assert secret.encode() in patched
    assert other_server in patched
    assert http_audit_server in patched
    assert patched.count(b"root /var/www/audit/current;") == 3
    assert patcher(patched, fragment) == patched
    captured = capsys.readouterr()
    assert secret not in captured.out
    assert secret not in captured.err

    duplicate = source + audit_server
    with pytest.raises(module.DeployError, match="server cardinality") as exc_info:
        patcher(duplicate, fragment)
    assert secret not in str(exc_info.value)

    duplicate_root = source.replace(
        b"    location / { root /var/www/audit; }\n    location /api/ {",
        b"    location / { root /var/www/audit; }\n"
        b"    location / { root /var/www/audit-duplicate; }\n"
        b"    location /api/ {",
    )
    with pytest.raises(module.DeployError, match="location cardinality"):
        patcher(duplicate_root, fragment)


def test_deploy_tencent_cloud_nginx_host_update_preserves_bind_mount_inode(
    tmp_path: Path,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_nginx_inode",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    overwrite = getattr(module, "_overwrite_regular_file_in_place", None)
    assert overwrite is not None
    host_config = tmp_path / "nginx.conf"
    candidate = tmp_path / "candidate.conf"
    host_config.write_bytes(b"old-config")
    candidate.write_bytes(b"new-config")
    original = host_config.stat()

    overwrite(host_config, candidate)

    updated = host_config.stat()
    assert (updated.st_dev, updated.st_ino) == (original.st_dev, original.st_ino)
    assert host_config.read_bytes() == b"new-config"

    linked = tmp_path / "linked.conf"
    linked.symlink_to(host_config)
    with pytest.raises(module.DeployError, match="regular file"):
        overwrite(linked, candidate)


def test_deploy_tencent_cloud_nginx_inode_race_does_not_truncate_replacement(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_nginx_inode_race",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    host_config = tmp_path / "nginx.conf"
    replacement = tmp_path / "replacement.conf"
    candidate = tmp_path / "candidate.conf"
    host_config.write_bytes(b"old-config")
    replacement_bytes = b"replacement-must-remain-unchanged"
    replacement.write_bytes(replacement_bytes)
    candidate.write_bytes(b"new-config")
    real_open = module.os.open
    raced = False

    def racing_open(path: object, flags: int, *args: object, **kwargs: object) -> int:
        nonlocal raced
        if Path(path) == host_config and flags & module.os.O_WRONLY and not raced:
            raced = True
            module.os.replace(replacement, host_config)
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(module.os, "open", racing_open)

    with pytest.raises(module.DeployError, match="changed before in-place update"):
        module._overwrite_regular_file_in_place(host_config, candidate)

    assert raced is True
    assert host_config.read_bytes() == replacement_bytes


def test_deploy_tencent_cloud_activation_failure_restores_current_and_nginx_inode(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_activation_transaction",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    activate = getattr(module, "_activate_remote_release", None)
    assert activate is not None
    old_sha = "1" * 40
    new_sha = "2" * 40
    remote_app_dir = tmp_path / "app"
    remote_web_dir = tmp_path / "web"
    transaction_root = tmp_path / "transactions"
    host_config = tmp_path / "nginx.conf"
    (remote_app_dir / "scripts").mkdir(parents=True)
    (remote_app_dir / "configs" / "deploy" / "tencent-cloud").mkdir(parents=True)
    shutil.copyfile(
        "scripts/deploy-tencent-cloud-production.py",
        remote_app_dir / "scripts" / "deploy-tencent-cloud-production.py",
    )
    shutil.copyfile(
        "configs/deploy/tencent-cloud/nginx-audit-server.conf",
        remote_app_dir / "configs" / "deploy" / "tencent-cloud" / "nginx-audit-server.conf",
    )
    (remote_web_dir / "releases" / old_sha).mkdir(parents=True)
    (remote_web_dir / "releases" / new_sha).mkdir(parents=True)
    (remote_web_dir / "current").symlink_to(f"releases/{old_sha}")
    (remote_web_dir / ".versioned-release-migration-complete").write_text(
        old_sha + "\n",
        encoding="utf-8",
    )
    remote_app_dir.mkdir(exist_ok=True)
    lock_dir = Path(f"{remote_app_dir}.deploy.lock")
    lock_dir.mkdir()
    (lock_dir / "owner").write_text("owner-token\n", encoding="utf-8")
    secret = "SECRET-SENTINEL-activation"
    original_config = f"""events {{}}
http {{
server {{
  listen 443 ssl;
  server_name audit.lute-tlz-dddd.top;
  ssl_certificate /etc/nginx/audit.crt;
  ssl_certificate_key /etc/nginx/audit.key;
  location /_next/static/ {{ root /var/www/audit; }}
  location /brand/ {{ root /var/www/audit; }}
  location / {{ root /var/www/audit; }}
  location /api/ {{ proxy_set_header X-API-Key \"{secret}\"; }}
}}
}}
""".encode()
    host_config.write_bytes(original_config)
    original_inode = host_config.stat().st_ino
    monkeypatch.setattr(module, "REMOTE_NGINX_CONFIG", str(host_config), raising=False)
    monkeypatch.setattr(
        module,
        "REMOTE_TRANSACTION_ROOT",
        str(transaction_root),
        raising=False,
    )
    scripts: list[str] = []
    monkeypatch.setattr(module, "_ssh", lambda _config, script: scripts.append(script))
    stamp = f"activation-failure-{tmp_path.name}"
    host_candidate = Path(f"/tmp/medical-audit-nginx-{stamp}.candidate")
    assert not host_candidate.exists()
    config = types.SimpleNamespace(
        remote_app_dir=str(remote_app_dir),
        remote_web_dir=str(remote_web_dir),
        approved_sha=new_sha,
        stamp=stamp,
        allow_first_legacy_migration=False,
    )

    activate(config, "owner-token")

    assert len(scripts) == 1
    syntax = subprocess.run(
        ["bash", "-n"],
        input=scripts[0],
        check=False,
        capture_output=True,
        text=True,
    )
    assert syntax.returncode == 0, syntax.stderr
    assert scripts[0].index("nginx -t -c") < scripts[0].index(
        'ln -s "releases/$approved_sha"',
    )
    assert scripts[0].index("trap cleanup_sensitive_candidates") < scripts[0].index(
        "MEDICAL_AUDIT_NGINX_PATCH",
    )
    assert 'rm -f "$container_candidate" >/dev/null 2>&1 || true' not in scripts[0]
    assert "mv -Tf" in scripts[0]
    assert "sudo -n -- python3 - \\" in scripts[0]
    assert '"$destination" "$source_file" "$deploy_script"' in scripts[0]
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "python3").symlink_to(sys.executable)
    fake_sudo = fake_bin / "sudo"
    fake_sudo.write_text(
        "#!/bin/sh\n"
        '[ "$1" = "-n" ] && shift\n'
        '[ "$1" = "--" ] && shift\n'
        'exec "$@"\n',
        encoding="utf-8",
    )
    fake_sudo.chmod(0o755)
    fake_mv = fake_bin / "mv"
    fake_mv.write_text(
        "#!/bin/sh\n"
        "case \"$1\" in -Tf|-fT|-T) shift;; esac\n"
        "[ \"$1\" = '--' ] && shift\n"
        "source=$1; target=$2\n"
        "/bin/rm -f \"$target\"\n"
        "set -- \"$source\" \"$target\"\n"
        "exec /bin/mv \"$@\"\n",
        encoding="utf-8",
    )
    fake_mv.chmod(0o755)
    fake_docker = fake_bin / "docker"
    docker_log = tmp_path / "docker.log"
    fake_docker.write_text(
        "#!/bin/sh\n"
        "printf '%s\\n' \"$*\" >> \"$DOCKER_LOG\"\n"
        "case \"$*\" in\n"
        "  *'nginx -t -c'*) exit 0;;\n"
        "  *'nginx -t'*) exit 1;;\n"
        "  *) exit 0;;\n"
        "esac\n",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)
    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
    environment["DOCKER_LOG"] = str(docker_log)

    failed = subprocess.run(
        ["bash", "-c", scripts[0]],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert failed.returncode != 0
    assert secret not in failed.stdout
    assert secret not in failed.stderr
    assert os.readlink(remote_web_dir / "current") == f"releases/{old_sha}"
    assert host_config.read_bytes() == original_config
    assert host_config.stat().st_ino == original_inode
    assert not host_candidate.exists()
    assert f"exec ai_video_nginx rm -f {host_candidate}" in docker_log.read_text(
        encoding="utf-8",
    )


def test_deploy_tencent_cloud_activation_cleanup_only_exits_for_failure(
    monkeypatch: MonkeyPatch,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_activation_cleanup_exit",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    scripts: list[str] = []
    monkeypatch.setattr(module, "_ssh", lambda _config, script: scripts.append(script))
    config = types.SimpleNamespace(
        stamp="activation-cleanup-exit",
        remote_app_dir="/opt/medical-audit/app",
        remote_web_dir="/var/www/audit",
        approved_sha="a" * 40,
        allow_first_legacy_migration=False,
    )

    module._activate_remote_release(config, "owner-token")

    cleanup_handler = scripts[0].split(
        "cleanup_sensitive_candidates_on_exit() {\n",
        1,
    )[1].split("\n}\ntrap cleanup_sensitive_candidates_on_exit EXIT", 1)[0]
    assert 'if [ "$original_status" -ne 0 ]; then' in cleanup_handler
    assert cleanup_handler.count('exit "$original_status"') == 1


def test_deploy_tencent_cloud_activation_rc79_is_outcome_unknown(
    monkeypatch: MonkeyPatch,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_activation_rc79",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    outcome_error = getattr(module, "RemoteOutcomeUnknownError", None)
    assert outcome_error is not None
    monkeypatch.setattr(
        module,
        "_ssh",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            subprocess.CalledProcessError(79, ["ssh"]),
        ),
    )
    config = types.SimpleNamespace(
        stamp="activation-rc79",
        remote_app_dir="/opt/medical-audit/app",
        remote_web_dir="/var/www/audit",
        approved_sha="a" * 40,
        allow_first_legacy_migration=False,
    )

    with pytest.raises(outcome_error, match="restore outcome"):
        module._activate_remote_release(config, "owner-token")


def test_deploy_tencent_cloud_missing_current_requires_legacy_authorization(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_legacy_activation_denied",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    remote_app_dir = tmp_path / "app"
    remote_web_dir = tmp_path / "web"
    transaction_root = tmp_path / "transactions"
    approved_sha = "a" * 40
    old_sha = "b" * 40
    (remote_web_dir / "releases" / approved_sha).mkdir(parents=True)
    (remote_web_dir / "index.html").write_text("legacy", encoding="utf-8")
    remote_app_dir.mkdir()
    (remote_app_dir / ".deploy-sha").write_text(old_sha + "\n", encoding="utf-8")
    lock_dir = Path(f"{remote_app_dir}.deploy.lock")
    lock_dir.mkdir()
    (lock_dir / "owner").write_text("owner-token\n", encoding="utf-8")
    nginx_config = tmp_path / "nginx.conf"
    nginx_config.write_text("events {}\n", encoding="utf-8")
    monkeypatch.setattr(module, "REMOTE_NGINX_CONFIG", str(nginx_config), raising=False)
    monkeypatch.setattr(
        module,
        "REMOTE_TRANSACTION_ROOT",
        str(transaction_root),
        raising=False,
    )
    scripts: list[str] = []
    monkeypatch.setattr(module, "_ssh", lambda _config, script: scripts.append(script))
    config = types.SimpleNamespace(
        stamp="legacy-denied",
        remote_app_dir=str(remote_app_dir),
        remote_web_dir=str(remote_web_dir),
        approved_sha=approved_sha,
        allow_first_legacy_migration=False,
    )

    module._activate_remote_release(config, "owner-token")

    denied = subprocess.run(
        ["bash", "-c", scripts[0]],
        check=False,
        capture_output=True,
        text=True,
    )
    assert denied.returncode != 0
    assert "legacy migration authorization required" in denied.stderr
    assert not transaction_root.exists()
    assert not (remote_web_dir / ".versioned-release-migration-complete").exists()
    assert 'rm -f -- "$migration_sentinel"' in scripts[0]
    sentinel_commit = 'mv -Tf -- "$next_migration_sentinel" "$migration_sentinel"'
    assert scripts[0].index(sentinel_commit) < scripts[0].index(
        "printf 'active",
    )
    for marker in (
        "MEDICAL_AUDIT_MIGRATION_FSYNC",
        "MEDICAL_AUDIT_MIGRATION_DIR_FSYNC",
    ):
        embedded = scripts[0].split(f"<<'{marker}'\n", 1)[1].split(
            f"\n{marker}",
            1,
        )[0]
        compile(embedded, f"<{marker.lower()}>", "exec")


def test_deploy_tencent_cloud_post_activation_restore_uses_recorded_transaction(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_post_activation_restore",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    restore = getattr(module, "_restore_remote_activation", None)
    assert restore is not None
    old_sha = "3" * 40
    new_sha = "4" * 40
    remote_app_dir = tmp_path / "app"
    remote_web_dir = tmp_path / "web"
    transaction_root = tmp_path / "transactions"
    transaction = transaction_root / "post-activation-test"
    host_config = tmp_path / "nginx.conf"
    (remote_app_dir / "scripts").mkdir(parents=True)
    shutil.copyfile(
        "scripts/deploy-tencent-cloud-production.py",
        remote_app_dir / "scripts" / "deploy-tencent-cloud-production.py",
    )
    (remote_web_dir / "releases" / old_sha).mkdir(parents=True)
    (remote_web_dir / "releases" / new_sha).mkdir(parents=True)
    (remote_web_dir / "current").symlink_to(f"releases/{new_sha}")
    (remote_web_dir / "current.next").symlink_to(f"releases/{new_sha}")
    (remote_web_dir / ".versioned-release-migration-complete").write_text(
        old_sha + "\n",
        encoding="utf-8",
    )
    lock_dir = Path(f"{remote_app_dir}.deploy.lock")
    lock_dir.mkdir()
    (lock_dir / "owner").write_text("owner-token\n", encoding="utf-8")
    transaction.mkdir(parents=True)
    (transaction / "approved-sha").write_text(new_sha + "\n", encoding="utf-8")
    (transaction / "previous-current").write_text(
        f"releases/{old_sha}\n",
        encoding="utf-8",
    )
    (transaction / "status").write_text("prepared\n", encoding="utf-8")
    secret = b"SECRET-SENTINEL-post-activation"
    original = b"events {}\n# " + secret + b"\n"
    patched = b"events {}\n# patched\n"
    host_config.write_bytes(patched)
    original_inode = host_config.stat().st_ino
    (transaction / "nginx.conf.before").write_bytes(original)
    monkeypatch.setattr(module, "REMOTE_NGINX_CONFIG", str(host_config), raising=False)
    monkeypatch.setattr(
        module,
        "REMOTE_TRANSACTION_ROOT",
        str(transaction_root),
        raising=False,
    )
    scripts: list[str] = []
    monkeypatch.setattr(module, "_ssh", lambda _config, script: scripts.append(script))
    config = types.SimpleNamespace(
        remote_app_dir=str(remote_app_dir),
        remote_web_dir=str(remote_web_dir),
        approved_sha=new_sha,
        stamp="post-activation-test",
    )

    restore(config, "owner-token")

    assert len(scripts) == 1
    syntax = subprocess.run(
        ["bash", "-n"],
        input=scripts[0],
        check=False,
        capture_output=True,
        text=True,
    )
    assert syntax.returncode == 0, syntax.stderr
    assert "sudo -n -- python3 - \\" in scripts[0]
    assert '"$nginx_config" "$nginx_backup" "$deploy_script"' in scripts[0]
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "python3").symlink_to(sys.executable)
    fake_sudo = fake_bin / "sudo"
    fake_sudo.write_text(
        "#!/bin/sh\n"
        '[ "$1" = "-n" ] && shift\n'
        '[ "$1" = "--" ] && shift\n'
        'exec "$@"\n',
        encoding="utf-8",
    )
    fake_sudo.chmod(0o755)
    fake_mv = fake_bin / "mv"
    fake_mv.write_text(
        "#!/bin/sh\n"
        "case \"$1\" in -Tf|-fT|-T) shift;; esac\n"
        "[ \"$1\" = '--' ] && shift\n"
        "source=$1; target=$2\n"
        "/bin/rm -f \"$target\"\n"
        "set -- \"$source\" \"$target\"\n"
        "exec /bin/mv \"$@\"\n",
        encoding="utf-8",
    )
    fake_mv.chmod(0o755)
    fake_docker = fake_bin / "docker"
    fake_docker.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_docker.chmod(0o755)
    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
    completed = subprocess.run(
        ["bash", "-c", scripts[0]],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert completed.returncode == 0, completed.stderr
    assert secret.decode() not in completed.stdout
    assert secret.decode() not in completed.stderr
    assert os.readlink(remote_web_dir / "current") == f"releases/{old_sha}"
    assert not (remote_web_dir / "current.next").exists()
    assert host_config.read_bytes() == original
    assert host_config.stat().st_ino == original_inode
    assert (transaction / "status").read_text(encoding="utf-8").strip() == "restored"


def test_deploy_tencent_cloud_public_release_verifier_rejects_cache_and_hash_drift() -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_public_release_verifier",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    verifier_builder = getattr(module, "_public_release_verifier_code", None)
    assert verifier_builder is not None
    manifest = b'{"release":"verified"}\n'
    static = b"static-release-bytes"

    class Handler(BaseHTTPRequestHandler):
        static_cache = "public, max-age=31536000, immutable"
        static_body = static
        html_cache = "no-store, no-cache, must-revalidate"
        redirect_manifest = False
        server_port = 0

        def do_GET(self) -> None:
            if self.path == "/release-manifest.json":
                if type(self).redirect_manifest:
                    self.send_response(302)
                    self.send_header(
                        "Location",
                        f"http://localhost:{type(self).server_port}/redirected-manifest.json",
                    )
                    self.end_headers()
                    return
                body = manifest
                cache = "no-store"
            elif self.path == "/redirected-manifest.json":
                body = manifest
                cache = "no-store"
            elif self.path == "/_next/static/app.js":
                body = type(self).static_body
                cache = type(self).static_cache
            else:
                body = b"<html>release</html>"
                cache = type(self).html_cache
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", cache)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format: str, *_args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        Handler.server_port = server.server_port
        base_url = f"http://127.0.0.1:{server.server_port}"
        command = [
            sys.executable,
            "-c",
            verifier_builder(),
            base_url,
            "_next/static/app.js",
            hashlib.sha256(manifest).hexdigest(),
            hashlib.sha256(static).hexdigest(),
        ]
        valid = subprocess.run(command, check=False, capture_output=True, text=True)
        assert valid.returncode == 0, valid.stderr

        Handler.html_cache = "private, no-cache, must-revalidate"
        bare_no_cache = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
        assert bare_no_cache.returncode == 0, bare_no_cache.stderr

        Handler.html_cache = "no-store, must-revalidate"
        bare_no_store = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
        assert bare_no_store.returncode == 0, bare_no_store.stderr

        Handler.static_cache = "public, max-age=60"
        bad_cache = subprocess.run(command, check=False, capture_output=True, text=True)
        assert bad_cache.returncode != 0

        Handler.static_cache = "public, max-age=31536000, immutable"
        Handler.static_body = b"tampered-static"
        bad_hash = subprocess.run(command, check=False, capture_output=True, text=True)
        assert bad_hash.returncode != 0

        Handler.static_body = static
        Handler.static_cache = "public, max-age=60, not-immutable"
        substring_static = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
        assert substring_static.returncode != 0

        Handler.static_cache = "public, max-age=31536000, immutable"
        Handler.html_cache = "private, no-cache-disabled"
        substring_html = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
        assert substring_html.returncode != 0

        Handler.html_cache = "no-store"
        Handler.redirect_manifest = True
        cross_origin_redirect = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
        assert cross_origin_redirect.returncode != 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.parametrize(
    ("html_cache", "static_cache"),
    [
        (
            "private, no-cache=disabled",
            "public, max-age=31536000, immutable",
        ),
        (
            "private, no-store=disabled",
            "public, max-age=31536000, immutable",
        ),
        (
            "no-store, must-revalidate",
            "public, max-age=31536000, immutable=disabled",
        ),
        (
            "no-store, must-revalidate",
            "public, immutable",
        ),
        (
            "no-store, must-revalidate",
            "public, max-age=invalid, immutable",
        ),
        (
            "no-store, must-revalidate",
            "public, max-age=60, immutable",
        ),
    ],
    ids=(
        "valued-no-cache",
        "valued-no-store",
        "valued-immutable",
        "missing-max-age",
        "invalid-max-age",
        "short-max-age",
    ),
)
def test_deploy_tencent_cloud_public_release_verifier_rejects_cache_directive_mutations(
    html_cache: str,
    static_cache: str,
) -> None:
    module = _load_script_module(
        f"deploy_tencent_cloud_public_cache_mutation_{hash((html_cache, static_cache))}",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    verifier_builder = getattr(module, "_public_release_verifier_code", None)
    assert verifier_builder is not None
    manifest = b'{"release":"verified"}\n'
    static = b"static-release-bytes"

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/release-manifest.json":
                body = manifest
                cache = "no-store"
            elif self.path == "/_next/static/app.js":
                body = static
                cache = static_cache
            else:
                body = b"<html>release</html>"
                cache = html_cache
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", cache)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format: str, *_args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        command = [
            sys.executable,
            "-c",
            verifier_builder(),
            f"http://127.0.0.1:{server.server_port}",
            "_next/static/app.js",
            hashlib.sha256(manifest).hexdigest(),
            hashlib.sha256(static).hexdigest(),
        ]
        result = subprocess.run(command, check=False, capture_output=True, text=True)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert result.returncode != 0, (
        f"cache mutation unexpectedly passed: html={html_cache!r}, "
        f"static={static_cache!r}"
    )


def test_deploy_tencent_cloud_deploy_marker_is_atomic_and_uses_approved_sha(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_atomic_marker",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    approved_sha = "a" * 40
    remote_app_dir = tmp_path / "app"
    remote_web_dir = tmp_path / "web"
    transaction_root = tmp_path / "transactions"
    transaction = transaction_root / "atomic-marker"
    remote_app_dir.mkdir()
    remote_web_dir.mkdir()
    transaction.mkdir(parents=True)
    (remote_app_dir / ".deploy-sha").write_text("b" * 40 + "\n", encoding="utf-8")
    (transaction / "approved-sha").write_text(approved_sha + "\n", encoding="utf-8")
    (transaction / "previous-current").write_text("LEGACY_NONE\n", encoding="utf-8")
    migration_sentinel = remote_web_dir / ".versioned-release-migration-complete"
    migration_sentinel.write_text(approved_sha + "\n", encoding="utf-8")
    lock_dir = Path(f"{remote_app_dir}.deploy.lock")
    lock_dir.mkdir()
    (lock_dir / "owner").write_text("owner-token\n", encoding="utf-8")
    ssh_calls: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        module,
        "_ssh",
        lambda _config, script, **kwargs: ssh_calls.append((script, kwargs)),
    )
    monkeypatch.setattr(
        module,
        "REMOTE_TRANSACTION_ROOT",
        str(transaction_root),
        raising=False,
    )
    config = types.SimpleNamespace(
        remote_app_dir=str(remote_app_dir),
        remote_web_dir=str(remote_web_dir),
        approved_sha=approved_sha,
        stamp="atomic-marker",
    )

    module._write_remote_deploy_sha(config, "owner-token")

    assert len(ssh_calls) == 1
    script, ssh_kwargs = ssh_calls[0]
    assert ssh_kwargs == {}
    assert ".deploy-sha.next" in script
    assert "mv -Tf" in script
    assert "next_migration_sentinel" not in script
    syntax = subprocess.run(
        ["bash", "-n"],
        input=script,
        check=False,
        capture_output=True,
        text=True,
    )
    assert syntax.returncode == 0, syntax.stderr
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_mv = fake_bin / "mv"
    fake_mv.write_text(
        "#!/bin/sh\n"
        "case \"$1\" in -Tf|-fT|-T) shift;; esac\n"
        "[ \"$1\" = '--' ] && shift\n"
        "exec /bin/mv \"$@\"\n",
        encoding="utf-8",
    )
    fake_mv.chmod(0o755)
    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
    completed = subprocess.run(
        ["bash", "-c", script],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    assert completed.returncode == 0, completed.stderr
    assert (remote_app_dir / ".deploy-sha").read_text(encoding="utf-8").strip() == approved_sha
    assert not (remote_app_dir / ".deploy-sha.next").exists()
    assert migration_sentinel.read_text(encoding="utf-8").strip() == approved_sha


def test_deploy_tencent_cloud_ssh_transport_requires_known_host(tmp_path: Path) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_strict_ssh_transport",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    config = types.SimpleNamespace(
        repo_root=tmp_path,
        ssh_key=tmp_path / "deploy.pem",
        ssh_target="ubuntu@example.test",
    )

    args = module._ssh_args(config, "true")
    transport = module._ssh_transport(config)

    assert "BatchMode=yes" in args
    assert "StrictHostKeyChecking=yes" in args
    assert "StrictHostKeyChecking=no" not in args
    assert "-o BatchMode=yes" in transport
    assert "-o StrictHostKeyChecking=yes" in transport
    assert "StrictHostKeyChecking=no" not in transport


def test_deploy_tencent_cloud_post_checks_auth_protected_documents(
    monkeypatch: MonkeyPatch,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_post_checks_auth_documents",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    captured_scripts: list[str] = []

    def fake_ssh(config: object, script: str) -> None:
        del config
        captured_scripts.append(script)

    monkeypatch.setattr(module, "_ssh", fake_ssh)
    config = types.SimpleNamespace(
        remote_app_dir="/opt/medical-audit/app",
        base_url="https://audit.example.test",
    )

    module._run_remote_post_checks(config)

    assert len(captured_scripts) == 1
    script = captured_scripts[0]
    assert "auth_headers=(" in script
    assert "curl -fsS https://audit.example.test/api/v1/health >/dev/null" in script
    assert (
        'curl -fsS "${auth_headers[@]}" '
        "https://audit.example.test/documents >/dev/null"
    ) in script
    assert "curl -fsS https://audit.example.test/documents >/dev/null" not in script
    assert "docker exec ai_video_nginx nginx -t >/dev/null 2>&1" in script
    assert "production nginx configuration test failed" in script
    assert "WARNING shared-nginx-test-failed" not in script
    assert "/api/v1/knowledge-base/catalog" in script
    assert "/index/search-backend" not in script


def test_deploy_tencent_cloud_default_smoke_stays_get_only(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_get_only_smoke",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    commands: list[list[str]] = []
    monkeypatch.setattr(
        module,
        "_run",
        lambda args, *, cwd: commands.append(list(args)),
    )
    config = types.SimpleNamespace(
        skip_smoke=False,
        report_path=tmp_path / "smoke.json",
        repo_root=tmp_path,
        base_url="https://audit.example.test",
        include_query_provider_smoke=False,
        include_review_write=False,
        confirm_production_write="",
    )

    module._run_production_smoke(config)

    assert len(commands) == 1
    assert "--include-query-provider-smoke" not in commands[0]
    assert "--include-review-write" not in commands[0]
    assert "--confirm-production-write" not in commands[0]


def test_deploy_tencent_cloud_rollback_is_executable_and_stamp_scoped(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_rollback_script",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    captured_scripts: list[str] = []
    monkeypatch.setattr(
        module,
        "_ssh",
        lambda config, script: captured_scripts.append(script),
    )
    config = types.SimpleNamespace(
        stamp="approved-stamp",
        remote_app_dir="/opt/medical-audit/app",
        remote_web_dir="/var/www/audit",
        base_url="https://audit.example.test",
        expected_current_sha="a" * 40,
        restore_sha="b" * 40,
    )

    module._run_remote_rollback(config, "owner-token")

    assert len(captured_scripts) == 1
    script = captured_scripts[0]
    assert "pre-deploy-approved-stamp.tar.gz" in script
    assert "audit-web-pre-deploy-approved-stamp.tar.gz" in script
    assert "expected_current_sha=" in script
    assert "owner-token" in script
    assert "restore_sha=" in script
    assert 'test "$(cat "$remote_app_dir/.deploy-sha")" = "$expected_current_sha"' in script
    assert 'release="$remote_web_dir/releases/$restore_sha"' in script
    assert 'incoming="$remote_web_dir/releases/$restore_sha.incoming"' in script
    assert '"$restore_root/app/web/out/" "$incoming/"' in script
    assert "release-manifest.json" in script
    assert 'ln -s "releases/$restore_sha" "$current_next"' in script
    assert 'mv -Tf -- "$current_next" "$current"' in script
    assert 'rsync -a --delete "$restore_root/audit/" "$remote_web_dir/"' not in script
    assert 'previous-current' in script
    assert 'LEGACY_NONE' in script
    assert "--exclude '.deploy-sha'" in script
    assert "up -d --no-deps app" in script
    assert "docker exec ai_video_nginx nginx -t" in script
    assert 'sudo -n -- python3 - "$destination" "$source_file"' in script
    assert 'next_marker="$remote_app_dir/.deploy-sha.next"' in script
    assert "marker_commit_started=0" in script
    assert 'if [ "$marker_commit_started" -eq 1 ]; then' in script
    marker_commit = 'mv -Tf -- "$next_marker" "$marker"'
    sentinel_remove = 'rm -f -- "$migration_sentinel"'
    assert script.index(sentinel_remove) < script.index(marker_commit)
    assert script.index("marker_commit_started=1") < script.index(marker_commit)
    assert script.index("up -d --no-deps app") < script.index(marker_commit)
    assert script.index("docker exec ai_video_nginx nginx -t") < script.index(marker_commit)
    assert script.index("/api/v1/health") < script.index(marker_commit)
    syntax_check = subprocess.run(
        ["bash", "-n"],
        input=script,
        check=False,
        capture_output=True,
        text=True,
    )
    assert syntax_check.returncode == 0, syntax_check.stderr
    heredoc_start = "<<'MEDICAL_AUDIT_NGINX_OVERWRITE'\n"
    inline_overwrite = script.split(heredoc_start, 1)[1].split(
        "\nMEDICAL_AUDIT_NGINX_OVERWRITE",
        1,
    )[0]
    compile(inline_overwrite, "<rollback-nginx-overwrite>", "exec")
    assert "os.O_TRUNC" not in inline_overwrite
    destination = tmp_path / "nginx.conf"
    source = tmp_path / "nginx.before"
    destination.write_bytes(b"patched\n")
    source.write_bytes(b"original\n")
    destination_inode = destination.stat().st_ino
    overwritten = subprocess.run(
        [sys.executable, "-c", inline_overwrite, str(destination), str(source)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert overwritten.returncode == 0, overwritten.stderr
    assert destination.read_bytes() == b"original\n"
    assert destination.stat().st_ino == destination_inode


def test_deploy_tencent_cloud_failed_rollback_retains_remote_lock(
    monkeypatch: MonkeyPatch,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_failed_rollback_lock",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    config = types.SimpleNamespace(rollback=True)
    events: list[str] = []
    monkeypatch.setattr(module, "_parse_args", lambda: object())
    monkeypatch.setattr(module, "_config_from_args", lambda _args: config)
    monkeypatch.setattr(module, "_print_plan", lambda _config: None)
    monkeypatch.setattr(module, "_validate_local_state", lambda _config: None)
    monkeypatch.setattr(
        module,
        "_acquire_remote_deploy_lock",
        lambda _config: events.append("lock") or "owner-token",
    )
    monkeypatch.setattr(
        module,
        "_run_remote_rollback",
        lambda *_args: (_ for _ in ()).throw(module.DeployError("rollback failed")),
    )
    monkeypatch.setattr(
        module,
        "_release_remote_deploy_lock",
        lambda *_args: events.append("unlock"),
    )

    assert module.main() == 2
    assert events == ["lock"]


def test_deploy_tencent_cloud_rebuilds_only_app_without_dependencies(
    monkeypatch: MonkeyPatch,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_rebuild_app_without_dependencies",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    captured_scripts: list[str] = []

    def fake_ssh(config: object, script: str) -> None:
        del config
        captured_scripts.append(script)

    monkeypatch.setattr(module, "_ssh", fake_ssh)
    approved_sha = "d" * 40
    config = types.SimpleNamespace(
        skip_app_rebuild=False,
        remote_app_dir="/opt/medical-audit/app",
        approved_sha=approved_sha,
    )

    module._rebuild_application(config, "owner-token")

    assert len(captured_scripts) == 1
    script = captured_scripts[0]
    assert "build app" in script
    assert "owner-token" in script
    assert f"export MEDICAL_AUDIT_DEPLOY_SHA={approved_sha}" in script
    assert not hasattr(module, "_current_deploy_sha")
    assert "up -d --no-deps app" in script
    assert "up -d clamav" not in script
    assert "up -d postgres" not in script
    assert 'postgres_id_before="$(docker inspect medical_audit_pg' in script
    assert 'clamav_id_before="$(docker inspect medical_audit_clamav' in script
    assert 'test "$(docker inspect medical_audit_pg' in script
    assert 'test "$(docker inspect medical_audit_clamav' in script
    syntax_check = subprocess.run(
        ["bash", "-n"],
        input=script,
        check=False,
        capture_output=True,
        text=True,
    )
    assert syntax_check.returncode == 0, syntax_check.stderr


def test_deploy_tencent_cloud_background_completion_polls_until_marker(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_background_completion",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    config = types.SimpleNamespace(
        repo_root=tmp_path,
        ssh_key=tmp_path / "deploy.pem",
        ssh_target="ubuntu@example.test",
    )
    calls: list[dict[str, object]] = []
    poll_results = [
        subprocess.CompletedProcess(
            args=["ssh"],
            returncode=0,
            stdout="MEDICAL_AUDIT_REMOTE_JOB_STATUS=running\n",
            stderr="",
        ),
        subprocess.CompletedProcess(
            args=["ssh"],
            returncode=0,
            stdout="MEDICAL_AUDIT_REMOTE_JOB_STATUS=complete\n",
            stderr="",
        ),
    ]

    def fake_run(
        args: list[str],
        *,
        cwd: Path,
        check: bool,
        text: bool,
        timeout: int,
        capture_output: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        calls.append(
            {
                "args": args,
                "cwd": cwd,
                "check": check,
                "text": text,
                "timeout": timeout,
                "capture_output": capture_output,
            },
        )
        if capture_output:
            return poll_results.pop(0)
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)

    module._ssh_background_with_completion(
        config,
        "printf 'complete\\n' > /tmp/marker",
        "test -s /tmp/marker",
        timeout_seconds=5,
        timeout_description="remote backups",
        job_name="deploy-backups-test",
    )

    assert len(calls) == 3
    starter_script = calls[0]["args"][-1]
    assert isinstance(starter_script, str)
    assert "deploy-backups-test.sh" in starter_script
    assert "nohup bash" in starter_script
    assert "deploy-backups-test.pid" in starter_script
    assert calls[0]["check"] is True
    assert calls[1]["capture_output"] is True
    assert calls[1]["check"] is False
    assert calls[2]["capture_output"] is True
    assert calls[2]["check"] is False
    poll_script = calls[1]["args"][-1]
    assert isinstance(poll_script, str)
    assert "exit 0" not in poll_script
    assert not poll_results


@pytest.mark.parametrize("failure_mode", ["timeout", "returncode"])
def test_deploy_tencent_cloud_background_completion_retries_transient_poll_failure(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    failure_mode: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_script_module(
        f"deploy_tencent_cloud_background_transient_{failure_mode}",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    config = types.SimpleNamespace(
        repo_root=tmp_path,
        ssh_key=tmp_path / "deploy.pem",
        ssh_target="ubuntu@example.test",
    )
    poll_calls = 0

    def fake_run(
        args: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        nonlocal poll_calls
        if not bool(kwargs.get("capture_output")):
            return subprocess.CompletedProcess(args=args, returncode=0)
        poll_calls += 1
        if poll_calls <= 4:
            if failure_mode == "timeout":
                raise subprocess.TimeoutExpired(
                    args,
                    timeout=60,
                    output="poll stdout",
                    stderr="poll stderr",
                )
            return subprocess.CompletedProcess(
                args=args,
                returncode=255,
                stdout="",
                stderr="",
            )
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout="MEDICAL_AUDIT_REMOTE_JOB_STATUS=complete\n",
            stderr="",
        )

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)

    module._ssh_background_with_completion(
        config,
        "printf 'complete\\n' > /tmp/marker",
        "test -s /tmp/marker",
        timeout_seconds=5,
        timeout_description="remote backups",
        job_name="deploy-backups-test",
    )

    assert poll_calls == 5
    if failure_mode == "timeout":
        output = capsys.readouterr().out
        assert "poll stdout" in output
        assert "poll stderr" in output


@pytest.mark.parametrize("failure_phase", ["command", "completion-check"])
def test_deploy_tencent_cloud_ssh_signal_termination_is_outcome_unknown(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    failure_phase: str,
) -> None:
    module = _load_script_module(
        f"deploy_tencent_cloud_ssh_signal_{failure_phase}",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    config = types.SimpleNamespace(
        repo_root=tmp_path,
        ssh_key=tmp_path / "deploy.pem",
        ssh_target="ubuntu@example.test",
    )
    calls = 0

    def fake_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        nonlocal calls
        calls += 1
        if failure_phase == "command" or calls == 2:
            raise subprocess.CalledProcessError(-9, ["ssh"])
        return subprocess.CompletedProcess(args=["ssh"], returncode=0)

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    with pytest.raises(module.RemoteOutcomeUnknownError, match="outcome is unknown"):
        module._ssh(
            config,
            "true",
            completion_check_script=(
                "test -f /tmp/complete" if failure_phase == "completion-check" else None
            ),
            timeout_description="test remote write",
        )


@pytest.mark.parametrize(
    ("failure_case", "poll_returncode", "poll_stdout", "poll_stderr"),
    [
        ("starter-rc1", None, "", ""),
        ("poll-rc1", 1, "", "ssh poll failed"),
        ("poll-signal", -9, "", "ssh process terminated"),
        ("poll-garbage", 0, "not-a-status\n", ""),
    ],
)
def test_deploy_tencent_cloud_background_indeterminate_results_are_outcome_unknown(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    failure_case: str,
    poll_returncode: int | None,
    poll_stdout: str,
    poll_stderr: str,
) -> None:
    module = _load_script_module(
        f"deploy_tencent_cloud_background_{failure_case}",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    config = types.SimpleNamespace(
        repo_root=tmp_path,
        ssh_key=tmp_path / "deploy.pem",
        ssh_target="ubuntu@example.test",
    )

    def fake_run(
        args: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        if not bool(kwargs.get("capture_output")):
            if failure_case == "starter-rc1":
                raise subprocess.CalledProcessError(1, args)
            return subprocess.CompletedProcess(args=args, returncode=0)
        assert poll_returncode is not None
        return subprocess.CompletedProcess(
            args=args,
            returncode=poll_returncode,
            stdout=poll_stdout,
            stderr=poll_stderr,
        )

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)

    with pytest.raises(
        module.RemoteOutcomeUnknownError,
        match="outcome is unknown",
    ) as exc_info:
        module._ssh_background_with_completion(
            config,
            "true",
            "test -f /tmp/complete",
            timeout_seconds=0,
            timeout_description="test remote job",
            job_name="deploy-test-job",
        )
    if poll_stderr:
        assert poll_stderr in str(exc_info.value)


def test_deploy_tencent_cloud_background_completion_reports_failed_status(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_background_completion_failed_status",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    config = types.SimpleNamespace(
        repo_root=tmp_path,
        ssh_key=tmp_path / "deploy.pem",
        ssh_target="ubuntu@example.test",
    )
    poll_results = [
        subprocess.CompletedProcess(
            args=["ssh"],
            returncode=0,
            stdout=(
                "MEDICAL_AUDIT_REMOTE_JOB_STATUS=failed\n"
                "remote job exited before completion marker\n"
            ),
            stderr="",
        ),
    ]

    def fake_run(
        args: list[str],
        *,
        cwd: Path,
        check: bool,
        text: bool,
        timeout: int,
        capture_output: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        del cwd, check, text, timeout
        if capture_output:
            return poll_results.pop(0)
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    with pytest.raises(module.DeployError, match="failed before completion marker"):
        module._ssh_background_with_completion(
            config,
            "exit 1",
            "test -s /tmp/marker",
            timeout_seconds=5,
            timeout_description="remote backups",
            job_name="deploy-backups-test",
        )

    assert not poll_results


def test_deploy_tencent_cloud_remote_backups_use_background_completion(
    monkeypatch: MonkeyPatch,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_remote_backups_background",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    captured: dict[str, object] = {}
    captured_cleanup: list[str] = []
    events: list[str] = []

    def fake_ssh(config: object, script: str) -> None:
        del config
        events.append("cleanup")
        captured_cleanup.append(script)

    def fake_background_completion(
        config: object,
        script: str,
        completion_check_script: str,
        *,
        timeout_seconds: int,
        timeout_description: str,
        job_name: str,
    ) -> None:
        events.append("background")
        captured.update(
            {
                "config": config,
                "script": script,
                "completion_check_script": completion_check_script,
                "timeout_seconds": timeout_seconds,
                "timeout_description": timeout_description,
                "job_name": job_name,
            },
        )

    monkeypatch.setattr(module, "_ssh", fake_ssh)
    monkeypatch.setattr(
        module,
        "_ssh_background_with_completion",
        fake_background_completion,
    )
    config = types.SimpleNamespace(
        stamp="unit-stamp",
        remote_app_dir="/opt/medical-audit/app",
    )

    module._create_remote_backups(config, "owner-token")

    assert events == ["cleanup", "background"]
    assert len(captured_cleanup) == 1
    cleanup_script = captured_cleanup[0]
    assert "rm -f" in cleanup_script
    assert "/tmp/medical-audit-deploy-backups-unit-stamp.complete" in cleanup_script
    assert "/opt/medical-audit/backups/app/pre-deploy-unit-stamp.tar.gz" in (
        cleanup_script
    )
    assert "/opt/medical-audit/backups/env/medical-audit.env.pre-deploy-unit-stamp" in (
        cleanup_script
    )
    assert "/opt/medical-audit/backups/db/pre-deploy-unit-stamp.sql.gz" in (
        cleanup_script
    )
    assert "/opt/medical-audit/backups/nginx/nginx.conf.pre-deploy-unit-stamp" in (
        cleanup_script
    )
    assert (
        "/opt/medical-audit/backups/web/audit-web-pre-deploy-unit-stamp.tar.gz"
        in cleanup_script
    )
    assert captured["config"] is config
    assert captured["timeout_seconds"] == module.REMOTE_BACKUP_TIMEOUT_SECONDS
    assert captured["timeout_description"] == "remote backups"
    assert captured["job_name"] == "medical-audit-deploy-backups-unit-stamp"
    script = captured["script"]
    completion_script = captured["completion_check_script"]
    assert isinstance(script, str)
    assert isinstance(completion_script, str)
    for generated_script in (cleanup_script, script, completion_script):
        syntax = subprocess.run(
            ["bash", "-n"],
            input=generated_script,
            check=False,
            capture_output=True,
            text=True,
        )
        assert syntax.returncode == 0, syntax.stderr
    assert "pg_dump" in script
    assert "owner-token" in script
    assert script.index("umask 077") < script.index('worker_pid="$lock_dir/worker.pid"')
    assert "install -m 600" in script
    assert "medical-audit.env.pre-deploy-${stamp}" in script
    assert "nginx.conf.pre-deploy-${stamp}" in script
    assert 'worker_pid="$lock_dir/worker.pid"' in script
    assert 'printf \'%s\\n\' "$BASHPID" > "$worker_pid_next"' in script
    assert 'test "$(cat "$worker_pid" 2>/dev/null || true)" = "$BASHPID"' in script
    assert 'rm -f -- "$worker_pid"' in script
    assert "--exclude='audit/releases'" in script
    assert "--exclude='audit/current'" in script
    assert "pre-deploy-${stamp}.sql.gz" in script
    assert "medical-audit-deploy-backups-unit-stamp.complete" in completion_script
    assert 'test ! -e "$lock_dir/worker.pid"' in completion_script
    assert "test ! -L" in completion_script
    assert 'test "$(stat -c \'%a\' "$path")" = 600' in completion_script
    assert (
        "verify_backup_file "
        "/opt/medical-audit/backups/db/pre-deploy-unit-stamp.sql.gz"
        in completion_script
    )


def test_deploy_tencent_cloud_package_carries_static_export() -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_package_static_export",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    dockerfile_text = Path("configs/deploy/tencent-cloud/Dockerfile").read_text(
        encoding="utf-8",
    )
    compose_text = Path("configs/deploy/tencent-cloud/docker-compose.prod.yaml").read_text(
        encoding="utf-8",
    )

    assert "web/out/" not in module.APP_RSYNC_EXCLUDES
    assert "/archive/" in module.APP_RSYNC_EXCLUDES
    assert "archive/" not in module.APP_RSYNC_EXCLUDES
    assert "COPY web/out ./web/out" in dockerfile_text
    assert "MEDICAL_AUDIT_WEB_STATIC_ROOT: /app/web/out" in compose_text


def test_deploy_tencent_cloud_uses_locked_dependency_inputs(
    monkeypatch: MonkeyPatch,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_locked_dependencies",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    dockerfile_text = Path("configs/deploy/tencent-cloud/Dockerfile").read_text(
        encoding="utf-8",
    )
    calls: list[tuple[list[str], Path, dict[str, str] | None]] = []

    def fake_run(
        args: list[str],
        *,
        cwd: Path,
        env: dict[str, str] | None = None,
    ) -> None:
        calls.append((args, cwd, env))

    monkeypatch.setattr(module, "_run", fake_run)
    repo_root = Path("/tmp/medical-audit-release")
    config = types.SimpleNamespace(
        skip_web_build=False,
        repo_root=repo_root,
        approved_sha="a" * 40,
    )
    original_environment = os.environ.copy()

    module._validate_locked_python_dependencies(config)
    module._build_static_frontend(config)

    assert "COPY pyproject.toml uv.lock README.md ./" in dockerfile_text
    assert "uv sync --frozen --no-dev --no-editable" in dockerfile_text
    assert "UV_HTTP_TIMEOUT=120" in dockerfile_text
    assert "uv pip install" not in dockerfile_text
    assert calls == [
        (
            [
                "uv",
                "lock",
                "--check",
                "--default-index",
                "https://pypi.org/simple",
            ],
            repo_root,
            None,
        ),
        (
            ["corepack", "pnpm", "install", "--frozen-lockfile"],
            repo_root,
            None,
        ),
        (
            ["corepack", "pnpm", "web:build:release"],
            repo_root,
            {**original_environment, "MEDICAL_AUDIT_DEPLOY_SHA": "a" * 40},
        ),
    ]
    assert os.environ == original_environment
    script_text = Path("scripts/deploy-tencent-cloud-production.py").read_text(
        encoding="utf-8",
    )
    assert script_text.index("_validate_locked_python_dependencies(config)") < (
        script_text.index("_run_remote_preflight(config)")
    )

    calls.clear()
    module._build_static_frontend(
        types.SimpleNamespace(
            skip_web_build=True,
            repo_root=repo_root,
            approved_sha="a" * 40,
        ),
    )
    assert calls == []


def test_deploy_tencent_cloud_excludes_local_tooling_and_evidence_artifacts() -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_local_artifact_excludes",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    gitignore_lines = Path(".gitignore").read_text(encoding="utf-8").splitlines()
    dockerignore_lines = Path(".dockerignore").read_text(encoding="utf-8").splitlines()

    assert ".gitnexus/" in module.APP_RSYNC_EXCLUDES
    assert "output/" in module.APP_RSYNC_EXCLUDES
    assert ".gitnexus/" in gitignore_lines
    assert ".gitnexus" in dockerignore_lines
    assert "output" in dockerignore_lines


def test_deploy_tencent_cloud_cleans_only_regenerable_remote_sync_artifacts(
    monkeypatch: MonkeyPatch,
) -> None:
    module = _load_script_module(
        "deploy_tencent_cloud_production_cleanup",
        Path("scripts/deploy-tencent-cloud-production.py"),
    )
    captured_scripts: list[str] = []

    def fake_ssh(config: object, script: str) -> None:
        captured_scripts.append(script)

    monkeypatch.setattr(module, "_ssh", fake_ssh)
    config = types.SimpleNamespace(remote_app_dir="/opt/medical-audit/app")

    module._cleanup_remote_sync_artifacts(config, "owner-token")

    assert len(captured_scripts) == 1
    script = captured_scripts[0]
    assert "web_parent_dir=/opt/medical-audit/app/web" in script
    assert "web_out_dir=/opt/medical-audit/app/web/out" in script
    assert "rm -rf \"$web_out_dir\"" in script
    assert "sudo -n rm -rf \"$web_out_dir\"" in script
    assert "sudo -n install -d -o \"$(id -u)\" -g \"$(id -g)\" \"$web_out_dir\"" in script
    assert "sudo -n chown -R \"$(id -u):$(id -g)\" \"$web_out_dir\"" in script
    assert "src_dir=/opt/medical-audit/app/src" in script
    assert "owner-token" in script
    assert "test -d \"$src_dir\"" in script
    assert "-name '*.pyc'" in script
    assert "-name '*.pyo'" in script
    assert "-name '*.uploading.cfg'" in script
    assert "-name __pycache__ -empty" in script
    assert "--delete-excluded" not in script
    assert "/data" not in script
    assert "medical-audit.env" not in script


def test_deploy_tencent_cloud_runs_cleanup_after_backups_before_rsync() -> None:
    script_text = Path("scripts/deploy-tencent-cloud-production.py").read_text(
        encoding="utf-8",
    )

    backup_call = script_text.index("_create_remote_backups(config, owner_token)")
    cleanup_call = script_text.index("_cleanup_remote_sync_artifacts(config, owner_token)")
    sync_call = script_text.index("_sync_application(config, owner_token)")

    assert backup_call < cleanup_call < sync_call
    assert "--delete-excluded" not in script_text


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
    deploy_sha = "cf6c1479de0b109d5abc9ee92ac8267e549ec2f6"
    remote_manifest_sha256 = "b" * 64
    static_sha256 = "c" * 64
    release_state: dict[str, object] = {
        "ok": True,
        "error": None,
        "current_release_target": f"releases/{deploy_sha}",
        "release_sha": deploy_sha,
        "manifest_source_sha": deploy_sha,
        "remote_manifest_sha256": remote_manifest_sha256,
        "manifest_file_count": 2,
        "manifest_mismatch_count": 0,
        "selected_html_path": "documents.html",
        "selected_html_sha256": "d" * 64,
        "selected_static_path": "_next/static/chunks/app-audit.js",
        "selected_static_sha256": static_sha256,
    }

    def deploy_marker_state() -> dict[str, object]:
        return {
            "ok": True,
            "error": None,
            "sha": deploy_sha,
            "snapshot": {
                "device": 1,
                "inode": 2,
                "file_type": "regular",
                "mode": stat.S_IFREG | 0o644,
                "size_bytes": 41,
                "mtime_ns": 3,
                "ctime_ns": 4,
            },
        }

    return {
        "deploy_sha": deploy_sha,
        "release_state": release_state,
        "release_observation": {
            "initial_deploy_sha": deploy_sha,
            "final_deploy_sha": deploy_sha,
            "initial_deploy_marker_state": deploy_marker_state(),
            "final_deploy_marker_state": deploy_marker_state(),
            "final_release_state": dict(release_state),
        },
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
                    "contract_version": "knowledge-base-catalog-v1",
                    "backend": "postgres",
                    "ready": True,
                    "details": {"matching_embedding_count": 48985},
                    "boundaries": {
                        "production_write": False,
                        "provider_call": False,
                        "database_write": False,
                        "object_storage_write": False,
                        "query_history_write": False,
                    },
                },
            }
        },
        "side_effect_observation": {
            "audit_log_before": {
                "ok": True,
                "transaction_read_only": "on",
                "count": 100,
                "latest_created_at": "2026-07-15 01:00:00+00",
                "event_id_fingerprint": "a" * 32,
                "auditor_user_identifier": "deployment-state-auditor-123",
                "auditor_event_count": 0,
            },
            "audit_log_after": {
                "ok": True,
                "transaction_read_only": "on",
                "count": 100,
                "latest_created_at": "2026-07-15 01:00:00+00",
                "event_id_fingerprint": "a" * 32,
                "auditor_user_identifier": "deployment-state-auditor-123",
                "auditor_event_count": 0,
            },
        },
        "public_frontdoor": {
            "health": {"ok": True, "status_code": 200},
            "documents": {
                "ok": True,
                "status_code": 200,
                "body_sha256": "d" * 64,
                "cache_control": "no-store, no-cache, must-revalidate",
                "same_origin": True,
            },
            "manifest": {
                "ok": True,
                "status_code": 200,
                "body_sha256": remote_manifest_sha256,
                "cache_control": "no-store, no-cache, must-revalidate",
                "same_origin": True,
            },
            "next_static": {
                "ok": True,
                "status_code": 200,
                "body_sha256": static_sha256,
                "cache_control": "public, max-age=31536000, immutable",
                "same_origin": True,
                "path": "/_next/static/chunks/app-audit.js",
            },
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


def _write_versioned_audit_release_fixture(
    root: Path,
    *,
    release_sha: str = "a" * 40,
    manifest_source_sha: str | None = None,
) -> dict[str, object]:
    web_root = root / "web"
    release_root = web_root / "releases" / release_sha
    files = {
        "_next/static/chunks/app-audit.js": b"console.log('audit release');\n",
        "documents.html": b"<html>audit release</html>\n",
    }
    entries: list[dict[str, object]] = []
    for relative_path, content in files.items():
        path = _write_bytes(release_root / relative_path, content)
        entries.append(
            {
                "path": relative_path,
                "size_bytes": path.stat().st_size,
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )
    entries.sort(key=lambda item: str(item["path"]).encode("utf-8"))
    payload = {
        "files": entries,
        "format": "medical-audit-web-release-manifest-v1",
        "lockfile_sha256": "e" * 64,
        "node_version": "v22.99.0",
        "pnpm_version": "9.99.0",
        "public_build_variables": {},
        "source_sha": manifest_source_sha or release_sha,
    }
    manifest_bytes = (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")
    _write_bytes(release_root / "release-manifest.json", manifest_bytes)
    web_root.mkdir(parents=True, exist_ok=True)
    (web_root / "current").symlink_to(
        f"releases/{release_sha}",
        target_is_directory=True,
    )
    static_entry = entries[0]
    return {
        "web_root": web_root,
        "release_root": release_root,
        "release_sha": release_sha,
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "static_path": static_entry["path"],
        "static_sha256": static_entry["sha256"],
        "html_path": "documents.html",
        "html_sha256": hashlib.sha256(files["documents.html"]).hexdigest(),
    }


def _audit_remote_namespace(
    *,
    remote_web_dir: Path,
    remote_app_dir: Path | None = None,
) -> dict[str, object]:
    module = _load_script_module(
        f"audit_tencent_cloud_remote_{hash(remote_web_dir)}",
        Path("scripts/audit-tencent-cloud-deployment-state.py"),
    )
    remote_code = module._remote_audit_code(
        remote_app_dir=str(remote_app_dir or "/opt/medical-audit/app"),
        remote_web_dir=str(remote_web_dir),
        remote_backup_root="/opt/medical-audit/backups",
        base_url="http://127.0.0.1:1",
        backup_limit=1,
    )
    prelude, separator, _main = remote_code.partition(
        "\nactive_release = release_state()\n"
    )
    assert separator
    namespace: dict[str, object] = {}
    exec(compile(prelude, "<remote-audit-prelude>", "exec"), namespace)
    return namespace


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


def test_audit_production_personal_material_indexing_readiness_script_is_readonly() -> None:
    script_path = Path("scripts/audit-production-personal-material-indexing-readiness.py")

    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(script_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    script_text = script_path.read_text(encoding="utf-8")
    assert "sk-" not in script_text
    assert "COS_SECRET" not in script_text
    assert "tmp/outputs/production-personal-material-indexing-readiness-latest.json" in script_text
    assert "production_write" in script_text
    assert "api_write" in script_text
    assert "audit_log_write_expected" in script_text
    assert "external_provider_call" in script_text
    assert "index_ingestion_triggered" in script_text
    assert "active_retrieval_activated" in script_text
    assert "/index-ingestion" not in script_text
    assert '"POST"' not in script_text
    assert "method='POST'" not in script_text
    assert 'method="POST"' not in script_text


def test_audit_production_personal_material_indexing_readiness_builds_blocked_report() -> None:
    module = _load_script_module(
        "audit_production_personal_material_indexing_readiness",
        Path("scripts/audit-production-personal-material-indexing-readiness.py"),
    )
    remote_report = {
        "deploy_sha": "c21d985e6853ffcbd4cb06cdf27deb03ab2861bc",
        "document_upload_indexing": {
            "env_ok": True,
            "env": {
                "MEDICAL_AUDIT_DOCUMENT_UPLOAD_INDEXING_ENABLED": "",
                "MEDICAL_AUDIT_DOCUMENT_UPLOAD_INDEXING_INDEX_VERSION_KEY": "",
                "MEDICAL_AUDIT_DOCUMENT_UPLOAD_INDEXING_SOURCE_PACKAGE_KEY": "",
            },
            "db_ok": True,
            "db": {
                "total_uploads": 12,
                "ready_not_indexed_uploads": 2,
                "staged_uploads": 0,
                "personal_material_candidate_versions": 0,
                "personal_material_active_versions": 0,
                "personal_material_chunks": 0,
                "personal_material_active_chunks": 0,
                "ready_not_indexed_samples": [
                    {
                        "upload_key": "document-upload-ready-cos",
                        "storage_path": "personal-materials/prod/object.txt",
                        "storage_provider": "tencent-cos",
                        "local_file_exists": False,
                    }
                ],
            },
        },
        "containers": {
            "medical_audit_app": {"health": "healthy"},
            "medical_audit_pg": {"health": "healthy"},
        },
    }

    report = module._build_report(
        remote_report=remote_report,
        expected_deploy_sha="c21d985e6853ffcbd4cb06cdf27deb03ab2861bc",
        require_indexing_enabled=True,
        require_ready_upload=True,
        require_local_file_available=True,
        require_no_active_personal_materials=True,
    )

    assert report["status"] == "blocked"
    assert report["issues"] == [
        "document-upload-indexing-disabled",
        "ready-upload-local-file-unavailable",
    ]
    assert report["summary"]["ready_not_indexed_uploads"] == 2
    assert report["summary"]["active_retrieval_activated"] is False
    assert report["boundaries"]["production_write"] is False
    assert report["boundaries"]["api_write"] is False
    assert report["boundaries"]["audit_log_write_expected"] is False
    assert report["boundaries"]["index_ingestion_triggered"] is False
    assert report["boundaries"]["active_retrieval_activated"] is False


def test_audit_production_personal_material_indexing_readiness_passes_completed_staging() -> None:
    module = _load_script_module(
        "audit_production_personal_material_indexing_readiness",
        Path("scripts/audit-production-personal-material-indexing-readiness.py"),
    )
    remote_report = {
        "deploy_sha": "550a445012267ba1211f5881b1d441264f3a3056",
        "document_upload_indexing": {
            "env_ok": True,
            "env": {
                "MEDICAL_AUDIT_DOCUMENT_UPLOAD_INDEXING_ENABLED": "true",
                "MEDICAL_AUDIT_DOCUMENT_UPLOAD_INDEXING_INDEX_VERSION_KEY": (
                    "personal-materials-cos-staging-pr152-20260619"
                ),
                "MEDICAL_AUDIT_DOCUMENT_UPLOAD_INDEXING_SOURCE_PACKAGE_KEY": (
                    "personal-materials-cos-staging-pr152-20260619"
                ),
            },
            "db_ok": True,
            "db": {
                "total_uploads": 18,
                "ready_not_indexed_uploads": 0,
                "ready_not_indexed_local_file_available_count": 0,
                "staged_uploads": 2,
                "personal_material_candidate_versions": 1,
                "personal_material_active_versions": 0,
                "personal_material_chunks": 2,
                "personal_material_active_chunks": 0,
                "ready_not_indexed_samples": [],
            },
        },
        "containers": {
            "medical_audit_app": {"health": "healthy"},
            "medical_audit_pg": {"health": "healthy"},
        },
    }

    report = module._build_report(
        remote_report=remote_report,
        expected_deploy_sha="550a445012267ba1211f5881b1d441264f3a3056",
        require_indexing_enabled=True,
        require_ready_upload=True,
        require_local_file_available=True,
        require_no_active_personal_materials=True,
    )

    assert report["status"] == "pass"
    assert report["issues"] == []
    assert report["summary"]["ready_not_indexed_uploads"] == 0
    assert report["summary"]["staged_uploads"] == 2
    assert report["summary"]["personal_material_chunks"] == 2
    assert report["summary"]["personal_material_active_chunks"] == 0
    assert report["boundaries"]["active_retrieval_activated"] is False


def test_audit_production_personal_material_active_gate_script_is_readonly() -> None:
    script_path = Path("scripts/audit-production-personal-material-active-gate.py")

    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(script_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    script_text = script_path.read_text(encoding="utf-8")
    assert "sk-" not in script_text
    assert "COS_SECRET" not in script_text
    assert "active gate" in script_text
    assert "production_write" in script_text
    assert "db_write" in script_text
    assert "external_provider_call" in script_text
    assert "index_activate_executed" in script_text
    assert "search_backend_reload_executed" in script_text
    assert "medical-audit-kb index-activate" not in script_text
    assert "activate_index_version(" not in script_text
    assert '"POST"' not in script_text
    assert "method='POST'" not in script_text
    assert 'method="POST"' not in script_text
    assert "UPDATE index_versions" not in script_text


def test_audit_production_personal_material_active_gate_blocks_inactive_live_retrieval() -> None:
    module = _load_script_module(
        "audit_production_personal_material_active_gate",
        Path("scripts/audit-production-personal-material-active-gate.py"),
    )
    remote_report = _personal_material_active_gate_remote_report(
        metadata={
            "source_collection": "personal-materials",
            "live_retrieval_activated": False,
        },
        runtime_guard=True,
    )

    report = module._build_report(
        remote_report=remote_report,
        expected_deploy_sha="0984aad93505cb8eedb36aa8379031c4396b1939",
        require_live_retrieval_activated=True,
        require_runtime_activation_guard=True,
    )

    assert report["status"] == "blocked"
    assert report["issues"] == ["live-retrieval-not-activated"]
    assert report["summary"]["target_index_version_key"] == (
        "personal-materials-cos-staging-pr152-20260619"
    )
    assert report["summary"]["target_status"] == "candidate"
    assert report["summary"]["target_live_retrieval_activated"] is False
    assert report["summary"]["runtime_activation_guard_enforced"] is True
    assert report["summary"]["personal_material_default_query_isolated"] is True
    assert report["summary"]["safe_to_execute_index_activate"] is False
    assert report["boundaries"]["production_read_only"] is True
    assert report["boundaries"]["production_write"] is False
    assert report["boundaries"]["db_write"] is False
    assert report["boundaries"]["index_activate_executed"] is False
    assert report["boundaries"]["search_backend_reload_executed"] is False


def test_audit_production_personal_material_active_gate_passes_explicit_live_activation() -> None:
    module = _load_script_module(
        "audit_production_personal_material_active_gate",
        Path("scripts/audit-production-personal-material-active-gate.py"),
    )
    remote_report = _personal_material_active_gate_remote_report(
        metadata={
            "source_collection": "personal-materials",
            "live_retrieval_activated": True,
        },
        runtime_guard=True,
    )

    report = module._build_report(
        remote_report=remote_report,
        expected_deploy_sha="0984aad93505cb8eedb36aa8379031c4396b1939",
        require_live_retrieval_activated=True,
        require_runtime_activation_guard=True,
    )

    assert report["status"] == "pass"
    assert report["issues"] == []
    assert report["summary"]["target_live_retrieval_activated"] is True
    assert report["summary"]["personal_material_default_query_isolated"] is True
    assert report["summary"]["safe_to_execute_index_activate"] is True
    assert "单独授权执行 index-activate" in report["recommended_next_step"]


def test_audit_production_personal_material_active_gate_blocks_default_query_leak() -> None:
    module = _load_script_module(
        "audit_production_personal_material_active_gate",
        Path("scripts/audit-production-personal-material-active-gate.py"),
    )
    remote_report = _personal_material_active_gate_remote_report(
        metadata={
            "source_collection": "personal-materials",
            "live_retrieval_activated": True,
        },
        runtime_guard=True,
    )
    remote_report["runtime_checks"] = {
        **remote_report["runtime_checks"],
        "personal_material_default_query_excludes_personal_materials": False,
        "personal_material_default_query_allowed_roles": ["auditor"],
    }

    report = module._build_report(
        remote_report=remote_report,
        expected_deploy_sha="0984aad93505cb8eedb36aa8379031c4396b1939",
        require_live_retrieval_activated=True,
        require_runtime_activation_guard=True,
    )

    assert report["status"] == "blocked"
    assert report["issues"] == ["personal-material-default-query-not-isolated"]
    assert report["summary"]["personal_material_default_query_isolated"] is False
    assert report["summary"]["safe_to_execute_index_activate"] is False


def test_run_production_personal_material_live_retrieval_gate_has_write_gate() -> None:
    script_path = Path("scripts/run-production-personal-material-live-retrieval-gate.py")

    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(script_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    script_text = script_path.read_text(encoding="utf-8")
    assert "--confirm-production-write" in script_text
    assert "--execute" in script_text
    assert "audit.lute-tlz-dddd.top" in script_text
    assert "UPDATE index_versions" in script_text
    assert "live_retrieval_activated" in script_text
    assert "index_activate_executed" in script_text
    assert "search_backend_reload_executed" in script_text
    assert "metadata->'index_readiness'" in script_text
    assert "extra_metadata->'index_readiness'" not in script_text
    assert "medical-audit-kb index-activate" not in script_text
    assert "activate_index_version(" not in script_text


def test_run_production_personal_material_live_retrieval_gate_requires_confirmation() -> None:
    module = _load_script_module(
        "run_production_personal_material_live_retrieval_gate",
        Path("scripts/run-production-personal-material-live-retrieval-gate.py"),
    )

    with pytest.raises(module.LiveRetrievalGateError, match="confirm-production-write"):
        module._require_production_write_confirmation("")
    module._require_production_write_confirmation("audit.lute-tlz-dddd.top")


def test_run_production_personal_material_live_retrieval_gate_reports_ready_for_write() -> None:
    module = _load_script_module(
        "run_production_personal_material_live_retrieval_gate",
        Path("scripts/run-production-personal-material-live-retrieval-gate.py"),
    )
    remote_report = _personal_material_active_gate_remote_report(
        metadata={
            "source_collection": "personal-materials",
            "live_retrieval_activated": False,
        },
        runtime_guard=True,
    )

    report = module._build_report(
        remote_report=remote_report,
        expected_deploy_sha="0984aad93505cb8eedb36aa8379031c4396b1939",
        execute=False,
        actor="tester",
        run_id="run-1",
    )

    assert report["status"] == "ready_for_write"
    assert report["issues"] == []
    assert report["summary"]["target_live_retrieval_activated"] is False
    assert report["summary"]["personal_material_default_query_isolated"] is True
    assert report["boundaries"]["production_write"] is False
    assert report["boundaries"]["index_activate_executed"] is False


def test_run_production_personal_material_live_retrieval_gate_blocks_default_query_leak() -> None:
    module = _load_script_module(
        "run_production_personal_material_live_retrieval_gate",
        Path("scripts/run-production-personal-material-live-retrieval-gate.py"),
    )
    remote_report = _personal_material_active_gate_remote_report(
        metadata={
            "source_collection": "personal-materials",
            "live_retrieval_activated": False,
        },
        runtime_guard=True,
    )
    remote_report["runtime_checks"] = {
        **remote_report["runtime_checks"],
        "personal_material_default_query_excludes_personal_materials": False,
        "personal_material_default_query_allowed_roles": ["auditor"],
    }

    report = module._build_report(
        remote_report=remote_report,
        expected_deploy_sha="0984aad93505cb8eedb36aa8379031c4396b1939",
        execute=False,
        actor="tester",
        run_id="run-1",
    )

    assert report["status"] == "blocked"
    assert report["issues"] == ["personal-material-default-query-not-isolated"]


def _personal_material_active_gate_remote_report(
    *,
    metadata: dict[str, object],
    runtime_guard: bool,
) -> dict[str, object]:
    return {
        "deploy_sha": "0984aad93505cb8eedb36aa8379031c4396b1939",
        "containers": {
            "medical_audit_app": {"health": "healthy"},
            "medical_audit_pg": {"health": "healthy"},
        },
        "document_upload_indexing_env": {
            "MEDICAL_AUDIT_DOCUMENT_UPLOAD_INDEXING_ENABLED": "true",
            "MEDICAL_AUDIT_DOCUMENT_UPLOAD_INDEXING_INDEX_VERSION_KEY": (
                "personal-materials-cos-staging-pr152-20260619"
            ),
            "MEDICAL_AUDIT_DOCUMENT_UPLOAD_INDEXING_SOURCE_PACKAGE_KEY": (
                "personal-materials-cos-staging-pr152-20260619"
            ),
        },
        "env_ok": True,
        "runtime_checks": {
            "activation_guard_blocks_inactive_live_retrieval": runtime_guard,
            "personal_material_explicit_query_allowed_roles": [],
            "personal_material_default_query_allowed_roles": [],
            "personal_material_default_query_excludes_personal_materials": True,
            "error": "",
        },
        "runtime_ok": True,
        "db_state": {
            "target_index_version_key": "personal-materials-cos-staging-pr152-20260619",
            "target_version": {
                "version_key": "personal-materials-cos-staging-pr152-20260619",
                "status": "candidate",
                "source_package_version_key": "personal-materials-cos-staging-pr152-20260619",
                "vector_provider": "fake",
                "vector_model": "deterministic-token-hashing",
                "document_count": 2,
                "chunk_count": 2,
                "metadata": metadata,
            },
            "personal_material_stats": {
                "candidate_versions": 1,
                "active_versions": 0,
                "documents": 2,
                "chunks": 2,
                "active_chunks": 0,
            },
        },
        "db_ok": True,
    }


def test_run_production_personal_material_index_staging_script_has_write_gate() -> None:
    script_path = Path("scripts/run-production-personal-material-index-staging-e2e.py")

    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(script_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    script_text = script_path.read_text(encoding="utf-8")
    assert "--confirm-production-write" in script_text
    assert "audit.lute-tlz-dddd.top" in script_text
    assert "X-Tenant-Id" in script_text
    assert "X-Project-Key" in script_text
    assert "/index-ingestion" in script_text
    assert "external_provider_call" in script_text
    assert "index_activate_executed" in script_text
    assert "search_backend_reload_executed" in script_text
    assert "active_retrieval_activated" in script_text


def test_run_production_personal_material_index_staging_requires_confirmation() -> None:
    module = _load_script_module(
        "run_production_personal_material_index_staging_e2e",
        Path("scripts/run-production-personal-material-index-staging-e2e.py"),
    )

    with pytest.raises(module.StagingE2EError, match="confirm-production-write"):
        module._require_production_write_confirmation(
            base_url="https://audit.lute-tlz-dddd.top",
            confirm_production_write="",
        )
    module._require_production_write_confirmation(
        base_url="https://audit.lute-tlz-dddd.top",
        confirm_production_write="audit.lute-tlz-dddd.top",
    )


def test_run_production_personal_material_index_staging_selects_readiness_samples(
    tmp_path: Path,
) -> None:
    module = _load_script_module(
        "run_production_personal_material_index_staging_e2e",
        Path("scripts/run-production-personal-material-index-staging-e2e.py"),
    )
    readiness_report = tmp_path / "readiness.json"
    readiness_report.write_text(
        json.dumps(
            {
                "remote": {
                    "document_upload_indexing": {
                        "db": {
                            "ready_not_indexed_samples": [
                                {"upload_key": "document-upload-one"},
                                {"upload_key": "document-upload-two"},
                            ]
                        }
                    }
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    assert module._selected_upload_ids(
        readiness_report=readiness_report,
        explicit_upload_ids=(),
        max_uploads=1,
    ) == ["document-upload-one"]
    assert module._selected_upload_ids(
        readiness_report=readiness_report,
        explicit_upload_ids=("document-upload-explicit",),
        max_uploads=10,
    ) == ["document-upload-explicit"]


def _release_manifest_env(tmp_path: Path) -> dict[str, str]:
    tool_bin = tmp_path / "tool-bin"
    tool_bin.mkdir()
    node = _write_bytes(tool_bin / "node", b"#!/bin/sh\nprintf 'v22.99.0\\n'\n")
    pnpm = _write_bytes(tool_bin / "pnpm", b"#!/bin/sh\nprintf '9.99.0\\n'\n")
    node.chmod(0o755)
    pnpm.chmod(0o755)
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("NEXT_PUBLIC_")
    }
    env["PATH"] = f"{tool_bin}{os.pathsep}{env['PATH']}"
    return env


def _run_release_manifest(
    *,
    web_out: Path,
    output: Path,
    env: dict[str, str],
    source_sha: str = "a" * 40,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "scripts/build-web-release-manifest.py",
            "--web-out",
            str(web_out),
            "--source-sha",
            source_sha,
            "--output",
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def test_web_release_manifest_is_deterministic_complete_and_secret_safe(
    tmp_path: Path,
) -> None:
    web_out = tmp_path / "out"
    shutil.copytree(Path("tests/fixtures/web-release-manifest"), web_out)
    output = web_out / "release-manifest.json"
    output.write_text("stale manifest", encoding="utf-8")
    env = _release_manifest_env(tmp_path)
    env.update(
        {
            "MEDICAL_AUDIT_SECRET_SENTINEL": "must-never-be-serialized",
            "NEXT_PUBLIC_AUDIT_ORG_NAME": "测试医院",
            "NEXT_PUBLIC_MEDICAL_AUDIT_REPLICA_API_READS": "",
        }
    )

    first = _run_release_manifest(web_out=web_out, output=output, env=env)
    assert first.returncode == 0, first.stderr
    first_bytes = output.read_bytes()
    second = _run_release_manifest(web_out=web_out, output=output, env=env)

    assert second.returncode == 0, second.stderr
    assert output.read_bytes() == first_bytes
    payload = json.loads(first_bytes)
    assert first_bytes == (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()
    assert payload == {
        "files": [
            {
                "path": "_next/static/app.js",
                "sha256": "3385455a7d81f78e18978e877f84012edbf2471b613620c8dff01f154e5ec7d4",
                "size_bytes": 24,
            },
            {
                "path": "index.html",
                "sha256": "335fca8574f060eea24ebcdae6b78f32414f5de03da1084fd0e73d710768e3a9",
                "size_bytes": 16,
            },
        ],
        "format": "medical-audit-web-release-manifest-v1",
        "lockfile_sha256": hashlib.sha256(Path("pnpm-lock.yaml").read_bytes()).hexdigest(),
        "node_version": "v22.99.0",
        "pnpm_version": "9.99.0",
        "public_build_variables": {
            "NEXT_PUBLIC_AUDIT_ORG_LOGO": None,
            "NEXT_PUBLIC_AUDIT_ORG_NAME": "测试医院",
            "NEXT_PUBLIC_MEDICAL_AUDIT_AGENT_EXTENSION_PACK": None,
            "NEXT_PUBLIC_MEDICAL_AUDIT_REPLICA_API_READS": "",
        },
        "source_sha": "a" * 40,
    }
    serialized = first_bytes.decode("utf-8")
    assert "release-manifest.json" not in serialized
    assert "must-never-be-serialized" not in serialized
    assert str(tmp_path) not in serialized
    assert "timestamp" not in serialized
    assert "mtime" not in serialized


@pytest.mark.parametrize("source_sha", ["a" * 39, "A" * 40, "g" * 40])
def test_web_release_manifest_rejects_invalid_source_sha(
    tmp_path: Path,
    source_sha: str,
) -> None:
    web_out = tmp_path / "out"
    shutil.copytree(Path("tests/fixtures/web-release-manifest"), web_out)
    output = web_out / "release-manifest.json"

    result = _run_release_manifest(
        web_out=web_out,
        output=output,
        env=_release_manifest_env(tmp_path),
        source_sha=source_sha,
    )

    assert result.returncode != 0
    assert "source SHA" in result.stderr
    assert not output.exists()


def test_web_release_manifest_requires_named_source_sha_environment_variable(
    tmp_path: Path,
) -> None:
    web_out = tmp_path / "out"
    shutil.copytree(Path("tests/fixtures/web-release-manifest"), web_out)
    output = web_out / "release-manifest.json"
    env = _release_manifest_env(tmp_path)
    env.pop("MISSING_DEPLOY_SHA", None)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/build-web-release-manifest.py",
            "--web-out",
            str(web_out),
            "--source-sha-env",
            "MISSING_DEPLOY_SHA",
            "--output",
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode != 0
    assert "MISSING_DEPLOY_SHA" in result.stderr
    assert not output.exists()


def test_web_release_manifest_rejects_unknown_public_build_variable(
    tmp_path: Path,
) -> None:
    web_out = tmp_path / "out"
    shutil.copytree(Path("tests/fixtures/web-release-manifest"), web_out)
    output = web_out / "release-manifest.json"
    env = _release_manifest_env(tmp_path)
    env["NEXT_PUBLIC_UNREVIEWED_FLAG"] = "enabled"

    result = _run_release_manifest(web_out=web_out, output=output, env=env)

    assert result.returncode != 0
    assert "NEXT_PUBLIC_UNREVIEWED_FLAG" in result.stderr
    assert not output.exists()


def test_web_release_manifest_rejects_symlinks_and_special_files(tmp_path: Path) -> None:
    env = _release_manifest_env(tmp_path)
    fixture = Path("tests/fixtures/web-release-manifest")

    symlink_out = tmp_path / "symlink-out"
    shutil.copytree(fixture, symlink_out)
    outside = _write_bytes(tmp_path / "outside.txt", b"outside")
    (symlink_out / "escape.txt").symlink_to(outside)
    symlink_output = symlink_out / "release-manifest.json"
    symlink_result = _run_release_manifest(
        web_out=symlink_out,
        output=symlink_output,
        env=env,
    )
    assert symlink_result.returncode != 0
    assert "symlink" in symlink_result.stderr.lower()
    assert not symlink_output.exists()

    special_out = tmp_path / "special-out"
    shutil.copytree(fixture, special_out)
    special = special_out / "named-pipe"
    os.mkfifo(special)
    special_output = special_out / "release-manifest.json"
    special_result = _run_release_manifest(
        web_out=special_out,
        output=special_output,
        env=env,
    )
    assert special_result.returncode != 0
    assert "regular file" in special_result.stderr.lower()
    assert not special_output.exists()


def test_web_release_manifest_rejects_output_escape_and_output_symlink(
    tmp_path: Path,
) -> None:
    env = _release_manifest_env(tmp_path)
    fixture = Path("tests/fixtures/web-release-manifest")
    web_out = tmp_path / "out"
    shutil.copytree(fixture, web_out)
    escaped_output = tmp_path / "escaped-manifest.json"

    escape_result = _run_release_manifest(
        web_out=web_out,
        output=escaped_output,
        env=env,
    )
    assert escape_result.returncode != 0
    assert "inside --web-out" in escape_result.stderr
    assert not escaped_output.exists()

    outside = _write_bytes(tmp_path / "outside-manifest.json", b"outside remains")
    linked_output = web_out / "release-manifest.json"
    linked_output.symlink_to(outside)
    link_result = _run_release_manifest(web_out=web_out, output=linked_output, env=env)
    assert link_result.returncode != 0
    assert "symlink" in link_result.stderr.lower()
    assert outside.read_bytes() == b"outside remains"


def test_web_release_manifest_atomic_failure_preserves_previous_output(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_script_module(
        "build_web_release_manifest_atomic_failure",
        Path("scripts/build-web-release-manifest.py"),
    )
    web_out = tmp_path / "out"
    shutil.copytree(Path("tests/fixtures/web-release-manifest"), web_out)
    output = web_out / "release-manifest.json"
    output.write_bytes(b"previous manifest\n")
    env = _release_manifest_env(tmp_path)
    for key in tuple(os.environ):
        if key.startswith("NEXT_PUBLIC_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("PATH", env["PATH"])
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build-web-release-manifest.py",
            "--web-out",
            str(web_out),
            "--source-sha",
            "a" * 40,
            "--output",
            str(output),
        ],
    )

    def fail_replace(_source: Path, _destination: Path) -> None:
        raise OSError("injected replace failure")

    monkeypatch.setattr(module.os, "replace", fail_replace)

    assert module.main() == 2
    assert output.read_bytes() == b"previous manifest\n"
    assert sorted(path.name for path in web_out.iterdir()) == [
        "_next",
        "index.html",
        "release-manifest.json",
    ]


def test_web_release_manifest_package_script_is_frozen() -> None:
    package = json.loads(Path("package.json").read_text(encoding="utf-8"))

    assert package["scripts"]["web:build:release"] == (
        "pnpm web:build:static && uv run python scripts/build-web-release-manifest.py "
        "--web-out web/out --source-sha-env MEDICAL_AUDIT_DEPLOY_SHA "
        "--output web/out/release-manifest.json"
    )


def test_web_release_manifest_is_world_readable_after_atomic_publish(
    tmp_path: Path,
) -> None:
    web_out = tmp_path / "out"
    shutil.copytree(Path("tests/fixtures/web-release-manifest"), web_out)
    output = web_out / "release-manifest.json"

    result = _run_release_manifest(
        web_out=web_out,
        output=output,
        env=_release_manifest_env(tmp_path),
    )

    assert result.returncode == 0, result.stderr
    assert stat.S_IMODE(output.stat().st_mode) == 0o644


def test_web_release_manifest_hashes_from_open_parent_directory_during_swap(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_script_module(
        "build_web_release_manifest_parent_directory_swap",
        Path("scripts/build-web-release-manifest.py"),
    )
    web_out = tmp_path / "out"
    nested = web_out / "nested"
    outside = tmp_path / "outside"
    nested.mkdir(parents=True)
    outside.mkdir()
    safe_content = b"safe release content\n"
    outside_content = b"outside attacker content\n"
    _write_bytes(nested / "probe.txt", safe_content)
    _write_bytes(outside / "probe.txt", outside_content)
    output = web_out / "release-manifest.json"
    env = _release_manifest_env(tmp_path)
    for key in tuple(os.environ):
        if key.startswith("NEXT_PUBLIC_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("PATH", env["PATH"])
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build-web-release-manifest.py",
            "--web-out",
            str(web_out),
            "--source-sha",
            "a" * 40,
            "--output",
            str(output),
        ],
    )
    original_open = module.os.open
    swapped = False

    def swap_parent_before_probe_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal swapped
        if not swapped and Path(os.fsdecode(path)).name == "probe.txt":
            nested.rename(web_out / "nested.safe")
            nested.symlink_to(outside, target_is_directory=True)
            swapped = True
        if dir_fd is None:
            return original_open(path, flags, mode)
        return original_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(module.os, "open", swap_parent_before_probe_open)

    assert module.main() == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert swapped is True
    assert payload["files"] == [
        {
            "path": "nested/probe.txt",
            "sha256": hashlib.sha256(safe_content).hexdigest(),
            "size_bytes": len(safe_content),
        }
    ]
    assert hashlib.sha256(outside_content).hexdigest() not in output.read_text(
        encoding="utf-8"
    )
