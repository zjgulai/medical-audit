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
        min_matching_embeddings=49000,
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


def test_run_production_documents_readonly_probe_reports_search_backend_failure() -> None:
    module = _load_script_module(
        "run_production_documents_readonly_probe_search_failure",
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
        if url.endswith("/api/backend/index/search-backend"):
            return module.HttpResponse(
                status=200,
                url=url,
                content=b'{"backend":"postgres","ready":false,"details":{"matching_embedding_count":0,"embedding_provider":"openai"}}',
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
        min_matching_embeddings=49000,
        http_get=fake_http_get,
    )

    assert report["status"] == "fail"
    assert report["summary"]["deploy_sha_status"] == "set"
    assert report["summary"]["backend_health"] == "ok"
    assert "search_backend_ready" not in report["summary"]
    search_step = next(
        step for step in report["steps"] if step["name"] == "backend-search-backend"
    )
    assert search_step["passed"] is False
    assert search_step["details"]["error"] == "search backend should be ready"


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
        base_url="http://127.0.0.1:8021",
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
        base_url="http://127.0.0.1:8021",
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


def test_production_frontend_acceptance_gate_rejects_inconsistent_report() -> None:
    gate_path = Path("scripts/run-production-frontend-acceptance-gate.mjs").resolve()
    runner_path = Path("scripts/run-production-frontend-acceptance.mjs").resolve()
    api_check = {
        "execution_status": "executed",
        "anonymous_check": "executed",
        "missing_tenant_check": "executed",
        "allowed_check": "executed",
        "anonymous_status": 403,
        "missing_tenant_status": 401,
        "allowed_status": 200,
    }
    report = {
        "status": "pass",
        "contract_profile": "hardened",
        "side_effect_mode": "audit-log-write-enabled",
        "production_side_effect": "audit-log-only",
        "database_write": "audit-log-only",
        "audit_log_write_expected": True,
        "summary": {
            "route_count": 0,
            "check_count": 0,
            "viewports": [],
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
    }
    node_program = (
        f"import {{ assertGate }} from {json.dumps(gate_path.as_uri())}; "
        f"import {{ routeCheckProfiles, viewports }} from {json.dumps(runner_path.as_uri())}; "
        "const report = JSON.parse(process.env.REPORT); "
        "const routes = routeCheckProfiles[report.contract_profile].map((item) => item.route); "
        "const viewportNames = viewports.map((item) => item.name); "
        "report.summary.route_count = routes.length; "
        "report.summary.viewports = viewportNames; "
        "report.checks = routes.flatMap((route) => "
        "viewportNames.map((viewport) => ({ route, viewport, status: 200, "
        "navigationError: false, headingCount: 1, bodyTextLength: 100, "
        "fileInputCount: 0, scrollWidth: 100, clientWidth: 100, "
        "horizontalOverflow: false, overflowOffenders: [], consoleErrorCount: 0, "
        "failedRequestCount: 0, failedRequests: [], interactionErrorCount: 0, "
        "issues: [] }))); "
        "report.summary.check_count = report.checks.length; "
        "if (process.env.MUTATE_ROUTE === '1') report.checks[0].route = '/fake-route'; "
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
    assert "frontend acceptance route coverage is incomplete" in (
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
    remote_report["public_frontdoor"] = {
        "health": {"ok": True, "status_code": 200},
        "documents": {"ok": True, "status_code": 200},
        "next_static": {"ok": False, "status_code": 404},
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
        report="",
    )

    config = module._config_from_args(args)

    assert config.report_path == Path(
        "tmp/outputs/production-e2e-smoke-after-deploy-20260611T184000+0800.json",
    ).resolve()


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
    assert "docker exec ai_video_nginx nginx -t" in script
    assert "WARNING shared-nginx-test-failed" not in script
    assert "/knowledge-base/catalog" in script
    assert "/index/search-backend" not in script
    assert "/tmp/medical-audit-nginx-test.log" not in script
    assert "/var/www/audit -> /var/www/audit" not in script


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
    assert "docker exec ai_video_nginx nginx -t" in script
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
        expected_current_sha="a" * 40,
        restore_sha="b" * 40,
    )

    module._run_remote_rollback(config)

    assert len(captured_scripts) == 1
    script = captured_scripts[0]
    assert "pre-deploy-approved-stamp.tar.gz" in script
    assert "audit-web-pre-deploy-approved-stamp.tar.gz" in script
    assert "expected_current_sha=" in script
    assert "restore_sha=" in script
    assert 'test "$(cat "$remote_app_dir/.deploy-sha")" = "$expected_current_sha"' in script
    assert "rsync -a --delete" in script
    assert "--exclude '.deploy-sha'" in script
    assert "up -d --no-deps app" in script
    assert "docker exec ai_video_nginx nginx -t" in script
    marker_write = 'printf \'%s\\n\' "$restore_sha" > "$remote_app_dir/.deploy-sha"'
    assert script.index("up -d --no-deps app") < script.index(marker_write)
    assert script.index("docker exec ai_video_nginx nginx -t") < script.index(marker_write)
    syntax_check = subprocess.run(
        ["bash", "-n"],
        input=script,
        check=False,
        capture_output=True,
        text=True,
    )
    assert syntax_check.returncode == 0, syntax_check.stderr


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
    monkeypatch.setattr(module, "_current_deploy_sha", lambda _config: "deploy-sha")
    config = types.SimpleNamespace(
        skip_app_rebuild=False,
        remote_app_dir="/opt/medical-audit/app",
    )

    module._rebuild_application(config)

    assert len(captured_scripts) == 1
    script = captured_scripts[0]
    assert "build app" in script
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
            returncode=255,
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
    assert not poll_results


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

    module._create_remote_backups(config)

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
    assert "pg_dump" in script
    assert "pre-deploy-${stamp}.sql.gz" in script
    assert "medical-audit-deploy-backups-unit-stamp.complete" in completion_script
    assert "test -s /opt/medical-audit/backups/db/pre-deploy-unit-stamp.sql.gz" in (
        completion_script
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
    assert "COPY web/out ./web/out" in dockerfile_text
    assert "MEDICAL_AUDIT_WEB_STATIC_ROOT: /app/web/out" in compose_text


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

    module._cleanup_remote_sync_artifacts(config)

    assert len(captured_scripts) == 1
    script = captured_scripts[0]
    assert "web_parent_dir=/opt/medical-audit/app/web" in script
    assert "web_out_dir=/opt/medical-audit/app/web/out" in script
    assert "rm -rf \"$web_out_dir\"" in script
    assert "sudo -n rm -rf \"$web_out_dir\"" in script
    assert "sudo -n install -d -o \"$(id -u)\" -g \"$(id -g)\" \"$web_out_dir\"" in script
    assert "sudo -n chown -R \"$(id -u):$(id -g)\" \"$web_out_dir\"" in script
    assert "src_dir=/opt/medical-audit/app/src" in script
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

    backup_call = script_text.index("_create_remote_backups(config)")
    cleanup_call = script_text.index("_cleanup_remote_sync_artifacts(config)")
    sync_call = script_text.index("_sync_application(config)")

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
            "documents": {"ok": True, "status_code": 200},
            "next_static": {"ok": True, "status_code": 200},
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
