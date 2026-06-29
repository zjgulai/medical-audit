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
    assert "Default is read-only production smoke" in script_text
    assert "edge-regression" in script_text


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
    assert report["blockers"] == ["no-provider-api-key-env-set"]
    assert scope["answer_runtime"]["status"] == "fallback_or_unset"
    assert scope["ready_provider_candidates"] == []
    assert report["boundaries"]["production_env_write"] is False


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
        if url.endswith("/documents"):
            return module.HttpResponse(
                status=200,
                url=url,
                content="AI智能审计管理系统 材料与知识库统一检索 个人材料".encode(),
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
    assert report["summary"]["backend_health"] == "ok"
    assert "documents_role" not in report["summary"]
    permission_step = next(
        step for step in report["steps"] if step["name"] == "documents-permissions"
    )
    assert permission_step["passed"] is False
    assert permission_step["details"]["error"] == "role mismatch: None"
    assert report["boundaries"]["production_write"] is False
    assert report["boundaries"]["document_upload_list_api_called"] is False


def test_run_production_documents_readonly_probe_reports_search_backend_failure() -> None:
    module = _load_script_module(
        "run_production_documents_readonly_probe_search_failure",
        Path("scripts/run-production-documents-readonly-probe.py"),
    )

    def fake_http_get(url: str, headers: dict[str, str], timeout_seconds: float) -> object:
        del headers, timeout_seconds
        if url.endswith("/documents"):
            return module.HttpResponse(
                status=200,
                url=url,
                content="AI智能审计管理系统 材料与知识库统一检索 个人材料".encode(),
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
    assert "provider_call_status" in script_text
    assert "X-Tenant-Id" in script_text


def test_run_controlled_api_readonly_permission_smoke_builds_get_probes() -> None:
    module = _load_script_module(
        "run_controlled_api_readonly_permission_smoke_builds_get_probes",
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
    )

    probes = module._build_probes(config)

    assert {probe.method for probe in probes} == {"GET"}
    assert [probe.kind for probe in probes] == [
        "public",
        "public",
        "protected-anonymous",
        "protected-missing-tenant",
        "protected-admin",
    ]
    admin_probe = next(probe for probe in probes if probe.kind == "protected-admin")
    missing_tenant_probe = next(
        probe for probe in probes if probe.kind == "protected-missing-tenant"
    )
    assert admin_probe.headers["X-Tenant-Id"] == "hospital-demo"
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
    )

    def fake_requester(probe: object, timeout_seconds: float) -> object:
        del timeout_seconds
        return module.HttpResponse(status=200, url=probe.url, text="{}")

    report = module.run_readonly_permission_smoke(config, requester=fake_requester)

    assert report["status"] == "observed"
    assert report["issues"] == []
    assert report["summary"]["observation_count"] == 2
    assert report["production_side_effect"] == "none"
    assert report["http_methods"] == ["GET"]


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
        expected_embeddings=48985,
    )

    assert report["status"] == "pass"
    assert report["issues"] == []
    assert report["summary"]["deploy_sha"] == "cf6c1479de0b109d5abc9ee92ac8267e549ec2f6"
    assert report["summary"]["audit_mount_present"] is True
    assert report["summary"]["latest_local_smoke_status"] == "pass"


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


def test_audit_tencent_cloud_deployment_state_authenticates_documents_frontdoor() -> None:
    script_text = Path("scripts/audit-tencent-cloud-deployment-state.py").read_text(
        encoding="utf-8",
    )

    assert "def http_status(url, expected_texts=None, headers=None):" in script_text
    assert "request_headers.update(headers)" in script_text
    assert "headers=AUDIT_HEADERS" in script_text


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
        include_review_write=False,
        report="",
    )

    config = module._config_from_args(args)

    assert config.report_path == Path(
        "tmp/outputs/production-e2e-smoke-after-deploy-20260611T184000+0800.json",
    ).resolve()


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
    assert "/var/www/audit -> /var/www/audit" not in script


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
                    "backend": "postgres",
                    "ready": True,
                    "details": {"matching_embedding_count": 48985},
                },
            }
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
