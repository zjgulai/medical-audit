from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from fastapi.testclient import TestClient

from medical_audit_kb.api.agent_store import InMemoryAgentStore
from medical_audit_kb.api.analytics_upload_store import InMemoryAnalyticsUploadStore
from medical_audit_kb.api.app import create_app
from medical_audit_kb.api.auth_user_store import InMemoryAuthUserStore
from medical_audit_kb.api.document_upload_store import InMemoryDocumentUploadStore
from medical_audit_kb.api.local_acceptance import create_local_acceptance_state
from medical_audit_kb.api.project_member_store import InMemoryProjectMemberStore
from medical_audit_kb.api.query_history_store import InMemoryQueryHistoryStore
from medical_audit_kb.api.review_task_store import InMemoryReviewTaskStore

PAGE_BACKEND_CONTRACT_PATH = Path("docs/api/frontend-backend-page-contract.json")
EXPECTED_WORKSPACE_ROUTES = {
    "/workspace",
    "/chat",
    "/knowledge-query",
    "/agents",
    "/agent-market",
    "/knowledge-base",
    "/documents",
    "/analytics",
    "/graph",
    "/rules",
    "/reports",
    "/projects",
    "/findings",
    "/remediation",
    "/archive",
    "/fund-compliance",
    "/fund-compliance/review",
    "/guided-check",
}
LOCAL_ACCEPTANCE_HEADERS = {
    "X-User-Id": "next-admin",
    "X-Role": "admin",
    "X-Tenant-Id": "hospital-demo",
    "X-Project-Key": "SELF-CHECK-FUND-20260607",
    "X-Project-Name": "%E5%8C%BB%E4%BF%9D%E5%9F%BA%E9%87%91%E4%BD%BF%E7%94%A8"
    "%E5%90%88%E8%A7%84%E4%B8%93%E9%A1%B9%E8%87%AA%E6%9F%A5",
}


def test_local_acceptance_state_uses_local_only_stores(tmp_path: Path) -> None:
    state = create_local_acceptance_state(tmp_path)

    assert state.search_backend == "local-acceptance"
    assert state.search_backend_details["provider_call"] is False
    assert state.search_backend_details["database_write"] is False
    assert state.audit_log_store is None
    assert state.audit_finding_store is None
    assert state.document_upload_indexer is None
    assert isinstance(state.agent_store, InMemoryAgentStore)
    assert isinstance(state.project_member_store, InMemoryProjectMemberStore)
    assert isinstance(state.review_task_store, InMemoryReviewTaskStore)
    assert isinstance(state.document_upload_store, InMemoryDocumentUploadStore)
    assert isinstance(state.analytics_upload_store, InMemoryAnalyticsUploadStore)
    assert isinstance(state.auth_user_store, InMemoryAuthUserStore)
    assert isinstance(state.query_history_store, InMemoryQueryHistoryStore)
    assert state.answer_generation_provider is not None


def test_local_acceptance_api_serves_rebuilt_frontend_routes(tmp_path: Path) -> None:
    state = create_local_acceptance_state(tmp_path)
    client = TestClient(create_app(state))

    route_checks = [
        ("GET", "/health", None),
        ("GET", "/agents", None),
        ("GET", "/documents/source-collections", None),
        ("GET", "/documents/permissions", None),
        ("GET", "/projects", None),
        ("GET", "/projects/SELF-CHECK-FUND-20260607/members", None),
        ("GET", "/audit-findings", None),
        ("GET", "/query/logs?limit=8", None),
    ]

    for method, path, payload in route_checks:
        response = client.request(
            method,
            path,
            headers=LOCAL_ACCEPTANCE_HEADERS,
            json=payload,
        )
        assert response.status_code == 200, f"{method} {path}: {response.text}"


def test_local_acceptance_query_records_agent_invocation(tmp_path: Path) -> None:
    state = create_local_acceptance_state(tmp_path)
    client = TestClient(create_app(state))

    response = client.post(
        "/query",
        json={
            "question": "医保基金审核依据是什么？",
            "top_k": 2,
            "source_collections": ["medical-insurance-laws"],
            "topic": "medical-insurance-fund",
            "agent": "agent-citation-check",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["agent_invocation_id"]
    assert payload["effective_source_collections"] == ["medical-insurance-laws"]

    assert state.query_logs[0]["agent_id"] == "agent-citation-check"
    filters = state.query_logs[0]["filters"]
    assert filters["topic"] == "medical-insurance-fund"
    assert filters["source_collections"] == ["medical-insurance-laws"]

    assert isinstance(state.agent_store, InMemoryAgentStore)
    invocations = state.agent_store.list_invocations("agent-citation-check")
    assert invocations[0]["id"] == payload["agent_invocation_id"]
    assert invocations[0]["metadata"]["filters"] == filters


def test_local_acceptance_document_source_collection_catalog_is_readonly(tmp_path: Path) -> None:
    state = create_local_acceptance_state(tmp_path)
    client = TestClient(create_app(state))

    response = client.get("/documents/source-collections", headers=LOCAL_ACCEPTANCE_HEADERS)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["contract_version"] == "document-source-collections-v1"
    assert payload["role"] == "it-admin"
    assert payload["search_backend"]["backend"] == "local-acceptance"
    assert payload["search_backend"]["ready"] is True
    assert payload["search_backend"]["details"]["provider_call"] is False
    assert payload["search_backend"]["details"]["database_write"] is False
    assert payload["boundaries"] == {
        "production_write": False,
        "provider_call": False,
        "database_write": False,
        "object_storage_write": False,
        "source": "runtime_state_and_registry_only",
    }

    items = {
        item["source_collection"]: item
        for item in payload["items"]
    }
    assert "medical-insurance-laws" in items
    assert "personal-materials" in items
    assert items["medical-insurance-laws"]["label"] == "法规政策"
    assert items["medical-insurance-laws"]["queryable"] is True
    assert items["personal-materials"]["access"] == "explicit-read-all"


def test_frontend_backend_page_contract_covers_workspace_routes() -> None:
    contract = _load_page_backend_contract()

    assert contract["contract_version"] == "frontend-backend-page-contract-v1"
    assert contract["boundaries"] == {
        "ui_style_change": False,
        "production_write": False,
        "provider_call": False,
        "database_write": False,
        "scope": "local_acceptance_and_frontend_contract_only",
    }

    routes = {str(page["route"]) for page in contract["pages"]}
    assert routes >= EXPECTED_WORKSPACE_ROUTES

    for page in contract["pages"]:
        assert page["connection_status"] in {
            "connected_first_batch",
            "static_shell_first_batch",
        }
        for endpoint in page["endpoints"]:
            path = str(endpoint["path"])
            assert path.startswith("/api/")
            assert not path.startswith(("http://", "https://"))
            assert endpoint["method"] in {"GET", "POST"}
            if endpoint["method"] == "POST":
                assert isinstance(endpoint.get("sample_body"), dict)


def test_local_acceptance_api_satisfies_frontend_backend_page_contract(tmp_path: Path) -> None:
    contract = _load_page_backend_contract()
    state = create_local_acceptance_state(tmp_path)
    client = TestClient(create_app(state))
    placeholders = {
        key: str(value)
        for key, value in contract["placeholders"].items()
    }

    checked_paths: list[str] = []
    for page in contract["pages"]:
        for endpoint in page["endpoints"]:
            path = _resolve_contract_path(str(endpoint["path"]), placeholders)
            method = str(endpoint["method"])
            if method == "GET":
                response = client.get(path, headers=LOCAL_ACCEPTANCE_HEADERS)
            elif endpoint.get("sample_body", {}).get("multipart") is True:
                sample_body = endpoint["sample_body"]
                response = client.post(
                    path,
                    headers=LOCAL_ACCEPTANCE_HEADERS,
                    data={
                        "model": str(sample_body["model"]),
                        "mode": str(sample_body.get("mode", "auto")),
                    },
                    files={
                        "file": (
                            str(sample_body.get("file", "sample.csv")),
                            "patient_id,charge_amount\nP001,120\nP002,80\n",
                            "text/csv",
                        )
                    },
                )
            else:
                response = client.post(
                    path,
                    headers=LOCAL_ACCEPTANCE_HEADERS,
                    json=endpoint.get("sample_body", {}),
                )
            checked_paths.append(f"{method} {path}")
            assert 200 <= response.status_code < 300, (
                f"{page['route']} {method} {path}: {response.status_code} {response.text}"
            )

    assert "GET /api/v1/projects/SELF-CHECK-FUND-20260607/members" in checked_paths
    assert "POST /api/v1/query" in checked_paths
    assert "GET /api/v1/documents/source-collections" in checked_paths
    assert "GET /api/v1/graph/workbench" in checked_paths


def _load_page_backend_contract() -> dict[str, object]:
    return json.loads(PAGE_BACKEND_CONTRACT_PATH.read_text(encoding="utf-8"))


def _resolve_contract_path(path: str, placeholders: Mapping[str, str]) -> str:
    resolved = path
    for key, value in placeholders.items():
        resolved = resolved.replace(f"{{{key}}}", value)
    return resolved
