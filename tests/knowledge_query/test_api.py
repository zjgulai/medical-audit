import json
from collections.abc import Sequence
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy.exc import SQLAlchemyError

from medical_audit_kb.api.agent_store import AGENT_ID_PREFIX, SqlAlchemyAgentStore
from medical_audit_kb.api.analytics_upload_store import (
    ANALYTICS_UPLOAD_ID_PREFIX,
    InMemoryAnalyticsUploadStore,
    SqlAlchemyAnalyticsUploadStore,
)
from medical_audit_kb.api.app import ApiState, create_app
from medical_audit_kb.api.auth_user_store import (
    AUTH_ROLE_ASSIGNMENT_ID_PREFIX,
    AUTH_USER_ID_PREFIX,
    SqlAlchemyAuthUserStore,
)
from medical_audit_kb.api.document_upload_store import (
    DOCUMENT_UPLOAD_ID_PREFIX,
    InMemoryDocumentUploadStore,
    SqlAlchemyDocumentUploadStore,
)
from medical_audit_kb.api.project_member_store import (
    PROJECT_MEMBER_ID_PREFIX,
    SqlAlchemyProjectMemberStore,
)
from medical_audit_kb.api.query_history_store import (
    InMemoryQueryHistoryStore,
    SqlAlchemyQueryHistoryStore,
)
from medical_audit_kb.core.config import KnowledgeQuerySettings, ModelProviderSettings
from medical_audit_kb.domain.constants import SourceCollection
from medical_audit_kb.generation.citations import Citation
from medical_audit_kb.indexing.bm25_index import BM25Document, InMemoryBM25Index
from medical_audit_kb.indexing.embeddings import DeterministicFakeEmbeddingProvider
from medical_audit_kb.indexing.index_activation import (
    IndexActivationError,
    IndexActivationResult,
    IndexRollbackResult,
)
from medical_audit_kb.indexing.vector_index import (
    ChunkEmbeddingInput,
    InMemoryVectorIndex,
    build_chunk_embedding_records,
)
from medical_audit_kb.retrieval.hybrid_search import HybridSearchEngine
from medical_audit_kb.retrieval.rerank import FakeRerankProvider

PROJECT_NAME_HEADER = (
    "%E5%8C%BB%E4%BF%9D%E5%9F%BA%E9%87%91"
    "%E4%BD%BF%E7%94%A8%E5%90%88%E8%A7%84"
    "%E4%B8%93%E9%A1%B9%E8%87%AA%E6%9F%A5"
)


def test_health_endpoint_returns_api_status(tmp_path: Path) -> None:
    client = TestClient(create_app(_api_state(tmp_path)))

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["data_root"] == str(tmp_path / "data")


def test_auth_api_lists_roles_and_manages_users(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'auth-users.db'}"
    state = _api_state(tmp_path)
    state.auth_user_store = SqlAlchemyAuthUserStore(database_url, create_schema=True)
    client = TestClient(create_app(state))

    roles_response = client.get("/auth/roles")

    assert roles_response.status_code == 200
    roles_body = roles_response.json()
    assert roles_body["mode"] == "header_transition_layer"
    assert [item["role"] for item in roles_body["items"]] == [
        "admin",
        "technician",
        "director",
        "member",
    ]
    assert roles_body["compatibility"]["it-admin"] == "admin"

    session_response = client.get(
        "/auth/session",
        headers={
            "X-User-Id": "next-admin",
            "X-Role": "admin",
            "X-Tenant-Id": "hospital-demo",
        },
    )
    assert session_response.status_code == 200
    session_body = session_response.json()
    assert session_body["role"] == "admin"
    assert session_body["tenant_id"] == "hospital-demo"
    assert session_body["profile"]["user_key"] == "next-admin"

    create_response = client.post(
        "/auth/users",
        headers={"X-User-Id": "admin-1", "X-Role": "admin"},
        json={
            "display_name": "医保办主任",
            "department_key": "medical-insurance-office",
        },
    )
    assert create_response.status_code == 200
    created = create_response.json()["item"]
    assert created["user_key"].startswith(AUTH_USER_ID_PREFIX)
    assert created["display_name"] == "医保办主任"
    assert created["department_key"] == "medical-insurance-office"
    assert state.operation_logs[-1]["action"] == "auth-user-create"

    assign_response = client.post(
        f"/auth/users/{created['user_key']}/role-assignments",
        headers={"X-User-Id": "admin-1", "X-Role": "admin"},
        json={"role": "director", "scope_type": "project", "scope_key": "CATALOG-LIMIT-202606"},
    )
    assert assign_response.status_code == 200
    assignment = assign_response.json()["item"]
    assert assignment["assignment_key"].startswith(AUTH_ROLE_ASSIGNMENT_ID_PREFIX)
    assert assignment["role"] == "director"
    assert assignment["scope_type"] == "project"
    assert state.operation_logs[-1]["action"] == "auth-user-role-assign"

    users_response = client.get(
        "/auth/users",
        headers={"X-User-Id": "admin-1", "X-Role": "admin"},
    )
    assert users_response.status_code == 200
    users_body = users_response.json()
    assert users_body["store"]["backend"] == "SqlAlchemyAuthUserStore"
    assert users_body["departments"][0]["department_key"]
    assert any(item["user_key"] == created["user_key"] for item in users_body["items"])

    second_state = _api_state(tmp_path / "second")
    second_state.auth_user_store = SqlAlchemyAuthUserStore(database_url)
    second_client = TestClient(create_app(second_state))
    persisted_users = second_client.get(
        "/auth/users",
        headers={"X-User-Id": "admin-1", "X-Role": "admin"},
    ).json()["items"]
    persisted = next(item for item in persisted_users if item["user_key"] == created["user_key"])
    assert persisted["role_assignments"][0]["role"] == "director"


def test_auth_api_rejects_member_user_management(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    state.auth_user_store = SqlAlchemyAuthUserStore(
        f"sqlite:///{tmp_path / 'auth-users.db'}",
        create_schema=True,
    )
    client = TestClient(create_app(state))

    response = client.get(
        "/auth/users",
        headers={"X-User-Id": "member-1", "X-Role": "member"},
    )
    missing_role_response = client.post(
        "/auth/users",
        json={"display_name": "未授权成员"},
    )

    assert response.status_code == 403
    assert missing_role_response.status_code == 401
    assert state.operation_logs[-1]["action"] == "authorization-denied"


def test_controlled_api_auth_middleware_enforces_user_headers_and_status(
    tmp_path: Path,
) -> None:
    state = _api_state(tmp_path)
    state.auth_user_store = SqlAlchemyAuthUserStore(
        f"sqlite:///{tmp_path / 'auth-users.db'}",
        create_schema=True,
    )
    client = TestClient(create_app(state, enforce_controlled_api_auth=True))

    health_response = client.get("/health")
    roles_response = client.get("/auth/roles")
    anonymous_projects_response = client.get("/projects")
    assert health_response.status_code == 200
    assert roles_response.status_code == 200
    assert anonymous_projects_response.status_code == 401
    denied_payload = state.operation_logs[-1]["payload"]
    assert denied_payload["attempted_action"] == "controlled-api-auth"
    assert denied_payload["path"] == "/projects"
    assert denied_payload["permission"] == "access_controlled_api"
    assert denied_payload["tenant_id"] is None
    assert denied_payload["reason"] == "X-Tenant-Id header is required"

    missing_tenant_response = client.get(
        "/projects",
        headers={"X-User-Id": "member-1", "X-Role": "member"},
    )
    missing_tenant_payload = state.operation_logs[-1]["payload"]
    assert missing_tenant_response.status_code == 401
    assert missing_tenant_payload["path"] == "/projects"
    assert missing_tenant_payload["tenant_id"] is None
    assert missing_tenant_payload["reason"] == "X-Tenant-Id header is required"

    member_projects_response = client.get(
        "/projects",
        headers={
            "X-User-Id": "member-1",
            "X-Role": "member",
            "X-Tenant-Id": "hospital-demo",
        },
    )
    create_disabled_response = client.post(
        "/auth/users",
        headers={
            "X-User-Id": "admin-1",
            "X-Role": "admin",
            "X-Tenant-Id": "hospital-demo",
        },
        json={
            "user_key": "disabled-api-user",
            "display_name": "中间件停用用户",
            "department_key": "audit-office",
            "status": "disabled",
        },
    )
    disabled_graph_response = client.get(
        "/graph/workbench",
        headers={
            "X-User-Id": "disabled-api-user",
            "X-Role": "admin",
            "X-Tenant-Id": "hospital-demo",
        },
    )

    assert member_projects_response.status_code == 200
    assert create_disabled_response.status_code == 200
    assert disabled_graph_response.status_code == 403
    disabled_denied_payload = state.operation_logs[-1]["payload"]
    assert disabled_denied_payload["attempted_action"] == "controlled-api-auth"
    assert disabled_denied_payload["path"] == "/graph/workbench"
    assert disabled_denied_payload["tenant_id"] == "hospital-demo"
    assert disabled_denied_payload["reason"] == "auth user status is disabled"


def test_permission_resolver_prefers_persisted_global_role(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    state.auth_user_store = SqlAlchemyAuthUserStore(
        f"sqlite:///{tmp_path / 'auth-users.db'}",
        create_schema=True,
    )
    state.agent_store = SqlAlchemyAgentStore(
        f"sqlite:///{tmp_path / 'agents.db'}",
        create_schema=True,
    )
    client = TestClient(create_app(state))

    create_user_response = client.post(
        "/auth/users",
        headers={"X-User-Id": "admin-1", "X-Role": "admin"},
        json={
            "user_key": "persistent-technician",
            "display_name": "持久化技术人员",
            "department_key": "it-department",
        },
    )
    assert create_user_response.status_code == 200

    assign_response = client.post(
        "/auth/users/persistent-technician/role-assignments",
        headers={"X-User-Id": "admin-1", "X-Role": "admin"},
        json={"role": "technician", "scope_type": "global"},
    )
    assert assign_response.status_code == 200

    session_response = client.get(
        "/auth/session",
        headers={"X-User-Id": "persistent-technician", "X-Role": "member"},
    )
    assert session_response.status_code == 200
    session_body = session_response.json()
    assert session_body["role"] == "technician"
    assert session_body["auth_source"] == "persistent_role"
    assert session_body["profile_status"] == "active"

    agent_response = client.post(
        "/agents",
        headers={"X-User-Id": "persistent-technician", "X-Role": "member"},
        json={
            "name": "持久化权限助手",
            "category": "业务类",
            "topic": "医保基金使用合规",
            "prompt": "仅基于授权角色进行配置。",
        },
    )
    assert agent_response.status_code == 200
    assert state.operation_logs[-1]["action"] == "agent-create"
    assert state.operation_logs[-1]["payload"]["role"] == "technician"

    project_member_response = client.post(
        "/projects/SELF-CHECK-FUND-20260607/members",
        headers={"X-User-Id": "persistent-technician", "X-Role": "admin"},
        json={"name": "持久化越权用户", "role": "审计员", "department": "医保办"},
    )
    assert project_member_response.status_code == 403
    denied_payload = state.operation_logs[-1]["payload"]
    assert state.operation_logs[-1]["action"] == "authorization-denied"
    assert denied_payload["effective_role"] == "technician"
    assert denied_payload["auth_source"] == "persistent_role"
    assert denied_payload["permission"] == "manage_project_members"


def test_permission_resolver_uses_project_scoped_role_for_matching_project(
    tmp_path: Path,
) -> None:
    state = _api_state(tmp_path)
    state.auth_user_store = SqlAlchemyAuthUserStore(
        f"sqlite:///{tmp_path / 'auth-users.db'}",
        create_schema=True,
    )
    state.project_member_store = SqlAlchemyProjectMemberStore(
        f"sqlite:///{tmp_path / 'project-members.db'}",
        create_schema=True,
    )
    client = TestClient(create_app(state))
    admin_headers = {"X-User-Id": "admin-1", "X-Role": "admin"}

    create_user_response = client.post(
        "/auth/users",
        headers=admin_headers,
        json={
            "user_key": "project-director",
            "display_name": "项目主任",
            "department_key": "audit-office",
        },
    )
    assert create_user_response.status_code == 200
    assign_response = client.post(
        "/auth/users/project-director/role-assignments",
        headers=admin_headers,
        json={
            "role": "admin",
            "scope_type": "project",
            "scope_key": "SELF-CHECK-FUND-20260607",
        },
    )
    assert assign_response.status_code == 200

    scoped_session_response = client.get(
        "/auth/session",
        headers={
            "X-User-Id": "project-director",
            "X-Role": "member",
            "X-Project-Key": "SELF-CHECK-FUND-20260607",
        },
    )
    other_project_session_response = client.get(
        "/auth/session",
        headers={
            "X-User-Id": "project-director",
            "X-Role": "admin",
            "X-Project-Key": "CATALOG-LIMIT-202606",
        },
    )
    allowed_member_response = client.post(
        "/projects/SELF-CHECK-FUND-20260607/members",
        headers={"X-User-Id": "project-director", "X-Role": "member"},
        json={"name": "项目授权成员", "role": "审计员", "department": "医保办"},
    )
    blocked_member_response = client.post(
        "/projects/CATALOG-LIMIT-202606/members",
        headers={"X-User-Id": "project-director", "X-Role": "admin"},
        json={"name": "跨项目越权成员", "role": "审计员", "department": "医保办"},
    )

    assert scoped_session_response.status_code == 200
    scoped_session = scoped_session_response.json()
    assert scoped_session["role"] == "admin"
    assert scoped_session["auth_source"] == "persistent_project_role"
    assert scoped_session["auth_scope_type"] == "project"
    assert scoped_session["auth_scope_key"] == "SELF-CHECK-FUND-20260607"
    assert other_project_session_response.status_code == 200
    other_project_session = other_project_session_response.json()
    assert other_project_session["role"] == "member"
    assert other_project_session["auth_source"] == "persistent_profile_without_project_role"
    assert allowed_member_response.status_code == 200
    assert allowed_member_response.json()["item"]["created_by"] == "project-director"
    assert blocked_member_response.status_code == 403
    denied_payload = state.operation_logs[-1]["payload"]
    assert denied_payload["attempted_action"] == "project-member-create"
    assert denied_payload["effective_role"] == "member"
    assert denied_payload["auth_source"] == "persistent_profile_without_project_role"
    assert denied_payload["auth_scope_type"] == "project"
    assert denied_payload["auth_scope_key"] == "CATALOG-LIMIT-202606"


def test_permission_resolver_denies_disabled_persisted_user(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    state.auth_user_store = SqlAlchemyAuthUserStore(
        f"sqlite:///{tmp_path / 'auth-users.db'}",
        create_schema=True,
    )
    client = TestClient(create_app(state))

    create_user_response = client.post(
        "/auth/users",
        headers={"X-User-Id": "admin-1", "X-Role": "admin"},
        json={
            "user_key": "disabled-admin",
            "display_name": "停用管理员",
            "department_key": "it-department",
            "status": "disabled",
        },
    )
    assert create_user_response.status_code == 200

    agent_response = client.post(
        "/agents",
        headers={"X-User-Id": "disabled-admin", "X-Role": "admin"},
        json={
            "name": "停用用户不应保存",
            "category": "业务类",
            "topic": "医保基金使用合规",
            "prompt": "停用用户不能写入。",
        },
    )

    assert agent_response.status_code == 403
    assert state.operation_logs[-1]["action"] == "authorization-denied"
    assert state.operation_logs[-1]["payload"]["user_identifier"] == "disabled-admin"
    assert state.operation_logs[-1]["payload"]["reason"] == "auth user status is disabled"


def test_auth_api_updates_user_status_and_role_assignment(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    state.auth_user_store = SqlAlchemyAuthUserStore(
        f"sqlite:///{tmp_path / 'auth-users.db'}",
        create_schema=True,
    )
    client = TestClient(create_app(state))
    admin_headers = {"X-User-Id": "admin-1", "X-Role": "admin"}

    create_user_response = client.post(
        "/auth/users",
        headers=admin_headers,
        json={
            "user_key": "managed-director",
            "display_name": "待管理主任",
            "department_key": "audit-office",
        },
    )
    assert create_user_response.status_code == 200
    assign_response = client.post(
        "/auth/users/managed-director/role-assignments",
        headers=admin_headers,
        json={"role": "director", "scope_type": "global"},
    )
    assert assign_response.status_code == 200
    assignment_key = assign_response.json()["item"]["assignment_key"]

    disabled_response = client.patch(
        "/auth/users/managed-director",
        headers=admin_headers,
        json={"status": "disabled"},
    )
    assert disabled_response.status_code == 200
    assert disabled_response.json()["item"]["status"] == "disabled"
    assert state.operation_logs[-1]["action"] == "auth-user-update"

    disabled_session_response = client.get(
        "/auth/session",
        headers={"X-User-Id": "managed-director", "X-Role": "director"},
    )
    assert disabled_session_response.status_code == 403
    assert disabled_session_response.json()["detail"] == "auth user status is disabled"

    active_response = client.patch(
        "/auth/users/managed-director",
        headers=admin_headers,
        json={"status": "active", "display_name": "已恢复主任"},
    )
    assert active_response.status_code == 200
    assert active_response.json()["item"]["status"] == "active"
    assert active_response.json()["item"]["display_name"] == "已恢复主任"

    restored_session_response = client.get(
        "/auth/session",
        headers={"X-User-Id": "managed-director", "X-Role": "member"},
    )
    assert restored_session_response.status_code == 200
    assert restored_session_response.json()["role"] == "director"

    revoke_response = client.patch(
        f"/auth/users/managed-director/role-assignments/{assignment_key}",
        headers=admin_headers,
        json={"status": "revoked"},
    )
    assert revoke_response.status_code == 200
    assert revoke_response.json()["item"]["status"] == "revoked"
    assert state.operation_logs[-1]["action"] == "auth-user-role-assignment-update"

    downgraded_session_response = client.get(
        "/auth/session",
        headers={"X-User-Id": "managed-director", "X-Role": "admin"},
    )
    assert downgraded_session_response.status_code == 200
    downgraded_session = downgraded_session_response.json()
    assert downgraded_session["role"] == "member"
    assert downgraded_session["auth_source"] == "persistent_profile_without_global_role"

    restore_assignment_response = client.patch(
        f"/auth/users/managed-director/role-assignments/{assignment_key}",
        headers=admin_headers,
        json={"status": "active"},
    )
    assert restore_assignment_response.status_code == 200
    assert restore_assignment_response.json()["item"]["status"] == "active"
    restored_role_response = client.get(
        "/auth/session",
        headers={"X-User-Id": "managed-director", "X-Role": "member"},
    )
    assert restored_role_response.status_code == 200
    assert restored_role_response.json()["role"] == "director"


def test_agents_api_lists_defaults_and_persists_created_agent(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'agents.db'}"
    state = _api_state(tmp_path)
    state.agent_store = SqlAlchemyAgentStore(database_url, create_schema=True)
    client = TestClient(create_app(state))

    list_response = client.get("/agents")

    assert list_response.status_code == 200
    list_body = list_response.json()
    assert list_body["store"]["backend"] == "SqlAlchemyAgentStore"
    assert list_body["categories"] == ["业务类", "效率类", "研究类"]
    assert [item["id"] for item in list_body["items"][:3]] == [
        "agent-citation-check",
        "agent-duplicate-charge",
        "agent-report-draft",
    ]

    create_response = client.post(
        "/agents",
        headers={"X-User-Id": "director-1", "X-Role": "director"},
        json={
            "name": "目录限制核验助手",
            "category": "业务类",
            "topic": "医保目录限制条件核验",
            "prompt": "仅基于目录限制字段和引用依据输出待补证问题。",
            "knowledge_base": "医保目录库",
            "project_name": "医保目录限制条件核验",
        },
    )

    assert create_response.status_code == 200
    created = create_response.json()["item"]
    assert created["id"].startswith(AGENT_ID_PREFIX)
    assert created["created_by"] == "director-1"
    assert created["source"] == "custom"
    assert created["status"] == "active"
    assert created["prompt_version"] == 1
    assert created["prompt_version_key"] == f"{created['id']}@v1"
    assert created["visibility_scope"] == "project"
    assert created["allowed_roles"] == ["admin", "technician", "director", "member"]
    assert state.operation_logs[-1]["action"] == "agent-create"
    assert state.operation_logs[-1]["payload"]["role"] == "director"

    second_state = _api_state(tmp_path / "second")
    second_state.agent_store = SqlAlchemyAgentStore(database_url)
    second_client = TestClient(create_app(second_state))
    persisted_items = second_client.get("/agents").json()["items"]

    assert persisted_items[0]["id"] == created["id"]
    assert persisted_items[0]["name"] == "目录限制核验助手"
    assert any(item["id"] == "agent-citation-check" for item in persisted_items)


def test_agents_api_fallback_defaults_include_prompt_version_metadata(tmp_path: Path) -> None:
    class UnavailableAgentStore:
        def list_agents(self, *, include_inactive: bool = False) -> list[dict[str, object]]:
            raise SQLAlchemyError("agent store unavailable")

    state = _api_state(tmp_path)
    state.agent_store = UnavailableAgentStore()  # type: ignore[assignment]
    client = TestClient(create_app(state))

    response = client.get("/agents")

    assert response.status_code == 200
    body = response.json()
    assert body["store"] == {"ready": False, "backend": "unavailable"}
    assert body["items"][0]["id"] == "agent-citation-check"
    assert body["items"][0]["prompt_versions"][0]["version"] == 1
    assert body["items"][0]["prompt_versions"][0]["is_active"] is True


def test_agents_api_tracks_prompt_versions_lifecycle_and_history(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'agents-governance.db'}"
    state = _api_state(tmp_path)
    state.agent_store = SqlAlchemyAgentStore(database_url, create_schema=True)
    client = TestClient(create_app(state))
    headers = {"X-User-Id": "director-1", "X-Role": "director"}

    create_response = client.post(
        "/agents",
        headers=headers,
        json={
            "name": "目录限制核验助手",
            "category": "业务类",
            "topic": "医保目录限制条件核验",
            "prompt": "仅基于目录限制字段输出待补证问题。",
            "knowledge_base": "医保目录库",
            "project_name": "医保目录限制条件核验",
            "visibility_scope": "system",
            "allowed_roles": ["director", "member"],
        },
    )
    agent = create_response.json()["item"]
    agent_id = str(agent["id"])

    update_response = client.post(
        f"/agents/{agent_id}/prompt-versions",
        headers=headers,
        json={
            "prompt": "仅基于目录限制字段和原文引用输出待补证问题。",
            "change_summary": "补充原文引用约束。",
            "review_note": "待主任复核原文引用边界。",
        },
    )
    updated = update_response.json()["item"]
    changes_response = client.post(
        f"/agents/{agent_id}/prompt-versions/review",
        headers=headers,
        json={
            "version": 2,
            "review_status": "changes-requested",
            "review_note": "需补充原文引用边界说明。",
        },
    )
    changes_requested = changes_response.json()["item"]
    review_response = client.post(
        f"/agents/{agent_id}/prompt-versions/review",
        headers=headers,
        json={
            "version": 2,
            "review_status": "approved",
            "review_note": "主任已复核提示词引用边界。",
        },
    )
    reviewed = review_response.json()["item"]
    rollback_response = client.post(
        f"/agents/{agent_id}/prompt-versions/rollback",
        headers=headers,
        json={"version": 1},
    )
    rolled_back = rollback_response.json()["item"]
    versions_response = client.get(f"/agents/{agent_id}/prompt-versions")
    invocation_response = client.post(
        f"/agents/{agent_id}/invocations",
        headers={"X-User-Id": "member-1", "X-Role": "member"},
        json={
            "invocation_source": "agent-workspace",
            "question": "目录限制核验试用",
            "conversation_ref": "local-chat-draft",
        },
    )
    invocation = invocation_response.json()["item"]
    feedback_response = client.post(
        f"/agents/{agent_id}/feedback",
        headers={"X-User-Id": "member-1", "X-Role": "member"},
        json={
            "invocation_id": invocation["id"],
            "rating": "effective",
            "comment": "引用约束清晰，可继续使用。",
        },
    )
    invocations_response = client.get(f"/agents/{agent_id}/invocations", headers=headers)
    feedback_list_response = client.get(f"/agents/{agent_id}/feedback", headers=headers)
    inactive_response = client.post(
        f"/agents/{agent_id}/lifecycle",
        headers=headers,
        json={"status": "inactive", "reason": "提示词待复核"},
    )
    archived_response = client.post(
        f"/agents/{agent_id}/lifecycle",
        headers=headers,
        json={"status": "archived", "reason": "软归档，不物理删除"},
    )
    list_response = client.get("/agents")
    detail_response = client.get(f"/agents/{agent_id}")

    assert create_response.status_code == 200
    assert agent["visibility_scope"] == "system"
    assert agent["allowed_roles"] == ["director", "member"]
    assert update_response.status_code == 200
    assert updated["prompt_version"] == 1
    assert updated["prompt"] == "仅基于目录限制字段输出待补证问题。"
    assert updated["prompt_versions"][0]["is_active"] is True
    assert updated["prompt_versions"][1]["review_status"] == "pending-review"
    assert updated["prompt_versions"][1]["is_active"] is False
    assert updated["prompt_versions"][1]["review_note"] == "待主任复核原文引用边界。"
    assert changes_response.status_code == 200
    assert changes_requested["prompt_version"] == 1
    assert changes_requested["prompt"] == "仅基于目录限制字段输出待补证问题。"
    assert changes_requested["prompt_versions"][1]["review_status"] == "changes-requested"
    assert changes_requested["prompt_versions"][1]["is_active"] is False
    assert review_response.status_code == 200
    assert reviewed["prompt_version"] == 2
    assert reviewed["prompt"] == "仅基于目录限制字段和原文引用输出待补证问题。"
    assert reviewed["prompt_versions"][0]["is_active"] is False
    assert reviewed["prompt_versions"][1]["is_active"] is True
    assert reviewed["prompt_versions"][1]["review_status"] == "approved"
    assert reviewed["prompt_versions"][1]["review_note"] == "主任已复核提示词引用边界。"
    assert reviewed["prompt_versions"][1]["reviewed_by"] == "director-1"
    assert "agent-prompt-version-review" in [entry["action"] for entry in state.operation_logs]
    assert rollback_response.status_code == 200
    assert rolled_back["prompt_version"] == 3
    assert rolled_back["prompt"] == "仅基于目录限制字段输出待补证问题。"
    assert rolled_back["prompt_versions"][2]["review_status"] == "approved"
    assert rolled_back["prompt_versions"][2]["is_active"] is True
    assert [item["version"] for item in rolled_back["prompt_versions"]] == [1, 2, 3]
    assert versions_response.status_code == 200
    assert [item["version"] for item in versions_response.json()["items"]] == [1, 2, 3]
    assert versions_response.json()["items"][2]["is_active"] is True
    assert invocation_response.status_code == 200
    assert invocation["agent_key"] == agent_id
    assert invocation["prompt_version"] == 3
    assert invocation["question"] == "目录限制核验试用"
    assert feedback_response.status_code == 200
    assert feedback_response.json()["item"]["invocation_id"] == invocation["id"]
    assert feedback_response.json()["item"]["rating"] == "effective"
    assert feedback_response.json()["summary"]["effective"] == 1
    assert feedback_response.json()["summary"]["latest_rating"] == "effective"
    assert invocations_response.json()["items"][0]["id"] == invocation["id"]
    assert feedback_list_response.json()["items"][0]["comment"] == "引用约束清晰，可继续使用。"
    assert feedback_list_response.json()["summary"] == {
        "total": 1,
        "effective": 1,
        "needs_review": 0,
        "unsafe": 0,
        "latest_rating": "effective",
    }
    assert inactive_response.status_code == 200
    assert inactive_response.json()["item"]["status"] == "inactive"
    assert archived_response.status_code == 200
    assert archived_response.json()["item"]["status"] == "archived"
    assert agent_id not in {item["id"] for item in list_response.json()["items"]}
    assert detail_response.status_code == 200
    assert detail_response.json()["item"]["id"] == agent_id
    assert detail_response.json()["item"]["status"] == "archived"
    assert detail_response.json()["item"]["metadata"]["lifecycle_reason"] == "软归档，不物理删除"
    assert [entry["action"] for entry in state.operation_logs[-9:]] == [
        "agent-prompt-versions-view",
        "agent-invocation-create",
        "agent-feedback-create",
        "agent-invocations-view",
        "agent-feedback-view",
        "agent-lifecycle-update",
        "agent-lifecycle-update",
        "agents-list",
        "agent-detail-view",
    ]


def test_agents_api_restricts_prompt_activation_to_admin_and_director(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'agents-prompt-activation-role.db'}"
    state = _api_state(tmp_path)
    state.agent_store = SqlAlchemyAgentStore(database_url, create_schema=True)
    client = TestClient(create_app(state))
    technician_headers = {"X-User-Id": "technician-1", "X-Role": "technician"}
    director_headers = {"X-User-Id": "director-1", "X-Role": "director"}

    create_response = client.post(
        "/agents",
        headers=technician_headers,
        json={
            "name": "技术配置候选助手",
            "category": "业务类",
            "topic": "医保基金使用合规",
            "prompt": "输出待补证问题。",
            "knowledge_base": "项目默认知识库",
            "project_name": "医保基金使用合规专项自查",
            "visibility_scope": "project",
        },
    )
    agent_id = str(create_response.json()["item"]["id"])
    update_response = client.post(
        f"/agents/{agent_id}/prompt-versions",
        headers=technician_headers,
        json={
            "prompt": "输出待补证问题，并标注引用依据。",
            "change_summary": "技术人员补充引用依据约束。",
            "review_note": "待主任复核。",
        },
    )
    technician_review_response = client.post(
        f"/agents/{agent_id}/prompt-versions/review",
        headers=technician_headers,
        json={
            "version": 2,
            "review_status": "approved",
            "review_note": "技术人员尝试激活。",
        },
    )
    technician_rollback_response = client.post(
        f"/agents/{agent_id}/prompt-versions/rollback",
        headers=technician_headers,
        json={"version": 1},
    )
    director_review_response = client.post(
        f"/agents/{agent_id}/prompt-versions/review",
        headers=director_headers,
        json={
            "version": 2,
            "review_status": "approved",
            "review_note": "主任复核通过。",
        },
    )

    assert create_response.status_code == 200
    assert update_response.status_code == 200
    assert update_response.json()["item"]["prompt_version"] == 1
    assert technician_review_response.status_code == 403
    assert (
        technician_review_response.json()["detail"]
        == "agent prompt activation requires admin or director role"
    )
    assert technician_rollback_response.status_code == 403
    assert director_review_response.status_code == 200
    reviewed = director_review_response.json()["item"]
    assert reviewed["prompt_version"] == 2
    assert reviewed["prompt_versions"][1]["is_active"] is True
    denied_actions = [
        entry["payload"]["attempted_action"]
        for entry in state.operation_logs
        if entry["action"] == "authorization-denied"
    ]
    assert "agent-prompt-version-review" in denied_actions
    assert "agent-prompt-version-rollback" in denied_actions


def test_agents_api_filters_project_scope_and_blocks_cross_project_invocation(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'agents-project-scope.db'}"
    state = _api_state(tmp_path)
    state.agent_store = SqlAlchemyAgentStore(database_url, create_schema=True)
    client = TestClient(create_app(state))
    project_a_headers = {
        "X-User-Id": "admin-1",
        "X-Role": "admin",
        "X-Project-Name": PROJECT_NAME_HEADER,
    }
    project_b_headers = {
        "X-User-Id": "admin-2",
        "X-Role": "admin",
        "X-Project-Name": "other-project",
    }

    create_response = client.post(
        "/agents",
        headers=project_a_headers,
        json={
            "name": "项目内目录限制核验助手",
            "category": "业务类",
            "topic": "医保目录限制条件核验",
            "prompt": "只在当前项目空间内用于目录限制条件核验。",
            "knowledge_base": "项目默认知识库",
            "project_name": "医保基金使用合规专项自查",
            "visibility_scope": "project",
        },
    )
    created = create_response.json()["item"]
    agent_id = str(created["id"])

    project_a_list = client.get("/agents", headers=project_a_headers)
    project_b_list = client.get("/agents", headers=project_b_headers)
    blocked_detail = client.get(f"/agents/{agent_id}", headers=project_b_headers)
    blocked_invocation = client.post(
        f"/agents/{agent_id}/invocations",
        headers={**project_b_headers, "X-User-Id": "member-2", "X-Role": "member"},
        json={"invocation_source": "agent-workspace", "question": "跨项目调用"},
    )
    allowed_invocation = client.post(
        f"/agents/{agent_id}/invocations",
        headers={**project_a_headers, "X-User-Id": "member-1", "X-Role": "member"},
        json={"invocation_source": "agent-workspace", "question": "本项目调用"},
    )

    assert create_response.status_code == 200
    assert agent_id in {item["id"] for item in project_a_list.json()["items"]}
    assert agent_id not in {item["id"] for item in project_b_list.json()["items"]}
    assert "agent-citation-check" in {item["id"] for item in project_b_list.json()["items"]}
    assert blocked_detail.status_code == 403
    assert blocked_detail.json()["detail"] == "agent project scope does not match current project"
    assert blocked_invocation.status_code == 403
    assert allowed_invocation.status_code == 200
    assert allowed_invocation.json()["item"]["question"] == "本项目调用"
    assert any(entry["action"] == "agent-project-scope-denied" for entry in state.operation_logs)


def test_agents_api_rejects_unknown_category(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    state.agent_store = SqlAlchemyAgentStore(
        f"sqlite:///{tmp_path / 'agents.db'}",
        create_schema=True,
    )
    client = TestClient(create_app(state))

    response = client.post(
        "/agents",
        json={
            "name": "未知分类助手",
            "category": "其他",
            "topic": "医保基金使用合规",
            "prompt": "输出审计问题。",
        },
    )

    assert response.status_code == 422


def test_agents_api_enforces_manage_agent_permission(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    state.agent_store = SqlAlchemyAgentStore(
        f"sqlite:///{tmp_path / 'agents.db'}",
        create_schema=True,
    )
    client = TestClient(create_app(state))
    payload = {
        "name": "成员自建系统智能体",
        "category": "业务类",
        "topic": "医保基金使用合规",
        "prompt": "输出审计问题。",
        "visibility_scope": "system",
    }

    unauthenticated_response = client.post("/agents", json=payload)
    member_response = client.post(
        "/agents",
        headers={"X-User-Id": "member-1", "X-Role": "member"},
        json=payload,
    )

    assert unauthenticated_response.status_code == 401
    assert member_response.status_code == 403
    assert state.operation_logs[-1]["action"] == "authorization-denied"
    assert state.operation_logs[-1]["payload"]["attempted_action"] == "agent-create"
    assert state.operation_logs[-1]["payload"]["permission"] == "manage_agents"


def test_projects_api_lists_defaults_and_persists_created_member(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'project-members.db'}"
    state = _api_state(tmp_path)
    state.project_member_store = SqlAlchemyProjectMemberStore(database_url, create_schema=True)
    client = TestClient(create_app(state))

    projects_response = client.get("/projects")

    assert projects_response.status_code == 200
    projects_body = projects_response.json()
    assert projects_body["store"]["backend"] == "SqlAlchemyProjectMemberStore"
    assert projects_body["roles"] == ["项目负责人", "审计员", "业务专家", "信息科", "只读观察员"]
    assert projects_body["items"][0]["id"] == "SELF-CHECK-FUND-20260607"
    assert projects_body["items"][0]["member_count"] == 3

    members_response = client.get("/projects/CATALOG-LIMIT-202606/members")

    assert members_response.status_code == 200
    members_body = members_response.json()
    assert members_body["project_key"] == "CATALOG-LIMIT-202606"
    assert len(members_body["items"]) == 4
    assert members_body["items"][0]["source"] == "system-default"

    create_response = client.post(
        "/projects/CATALOG-LIMIT-202606/members",
        headers={"X-User-Id": "admin-1", "X-Role": "admin"},
        json={
            "name": "赵审计",
            "role": "审计员",
            "department": "医保办",
        },
    )

    assert create_response.status_code == 200
    created = create_response.json()["item"]
    assert created["id"].startswith(PROJECT_MEMBER_ID_PREFIX)
    assert created["project_key"] == "CATALOG-LIMIT-202606"
    assert created["status"] == "待确认"
    assert created["created_by"] == "admin-1"
    assert state.operation_logs[-1]["action"] == "project-member-create"
    assert state.operation_logs[-1]["payload"]["actor_role"] == "admin"

    second_state = _api_state(tmp_path / "second")
    second_state.project_member_store = SqlAlchemyProjectMemberStore(database_url)
    second_client = TestClient(create_app(second_state))
    persisted_members = second_client.get("/projects/CATALOG-LIMIT-202606/members").json()["items"]
    persisted_projects = second_client.get("/projects").json()["items"]
    catalog_project = next(
        item for item in persisted_projects if item["id"] == "CATALOG-LIMIT-202606"
    )

    assert persisted_members[0]["id"] == created["id"]
    assert persisted_members[0]["name"] == "赵审计"
    assert any(item["id"] == "member-catalog-owner" for item in persisted_members)
    assert catalog_project["member_count"] == 5


def test_projects_api_rejects_unknown_project_and_role(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    state.project_member_store = SqlAlchemyProjectMemberStore(
        f"sqlite:///{tmp_path / 'project-members.db'}",
        create_schema=True,
    )
    client = TestClient(create_app(state))

    missing_response = client.get("/projects/UNKNOWN/members")
    invalid_role_response = client.post(
        "/projects/SELF-CHECK-FUND-20260607/members",
        json={
            "name": "未知角色",
            "role": "访客",
            "department": "医保办",
        },
    )

    assert missing_response.status_code == 404
    assert invalid_role_response.status_code == 422


def test_projects_api_enforces_member_management_permission(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    state.project_member_store = SqlAlchemyProjectMemberStore(
        f"sqlite:///{tmp_path / 'project-members.db'}",
        create_schema=True,
    )
    client = TestClient(create_app(state))
    payload = {
        "name": "赵审计",
        "role": "审计员",
        "department": "医保办",
    }

    unauthenticated_response = client.post(
        "/projects/SELF-CHECK-FUND-20260607/members",
        json=payload,
    )
    director_response = client.post(
        "/projects/SELF-CHECK-FUND-20260607/members",
        headers={"X-User-Id": "director-1", "X-Role": "director"},
        json=payload,
    )

    assert unauthenticated_response.status_code == 401
    assert director_response.status_code == 403
    assert state.operation_logs[-1]["action"] == "authorization-denied"
    assert state.operation_logs[-1]["payload"]["attempted_action"] == "project-member-create"
    assert state.operation_logs[-1]["payload"]["permission"] == "manage_project_members"


def test_analytics_table_upload_profiles_csv_file(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'analytics-uploads.db'}"
    state = _api_state(tmp_path)
    state.analytics_upload_store = SqlAlchemyAnalyticsUploadStore(
        database_url=database_url,
        upload_root=tmp_path / "retained-uploads",
        create_schema=True,
    )
    client = TestClient(create_app(state))

    response = client.post(
        "/analytics/table-upload",
        files={
            "file": (
                "charge-sample.csv",
                "\n".join(
                    [
                        "patient_id,visit_date,item_code,charge_amount,insurance_pay",
                        "P001,2026-01-01,A100,120.00,80.00",
                        "P001,2026-01-01,A100,120.00,80.00",
                        "P002,2026-01-02,B200,,50.00",
                    ]
                ),
                "text/csv",
            )
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "charge-sample.csv"
    assert body["upload_id"].startswith(ANALYTICS_UPLOAD_ID_PREFIX)
    assert body["sha256"]
    assert body["retention_status"] == "retained"
    assert body["created_at"]
    assert body["extension"] == "csv"
    assert body["status"] == "parsed"
    assert body["row_count"] == 3
    assert body["duplicate_row_count"] == 1
    assert body["empty_cell_count"] == 1
    assert body["audit_signals"] == [
        "金额/费用字段",
        "患者/就诊字段",
        "日期/时间字段",
        "项目/药品/目录字段",
        "医保支付字段",
    ]
    assert body["columns"][0]["type"] == "标识"
    assert "发现 1 条完全重复行。" in body["quality_findings"]
    assert state.operation_logs[-1]["action"] == "analytics-table-upload"
    assert state.operation_logs[-1]["payload"]["retention_status"] == "retained"

    history_response = client.get("/analytics/table-uploads")
    assert history_response.status_code == 200
    history_body = history_response.json()
    assert history_body["store"]["backend"] == "SqlAlchemyAnalyticsUploadStore"
    assert history_body["items"][0]["id"] == body["upload_id"]
    assert history_body["items"][0]["sha256"] == body["sha256"]
    assert history_body["items"][0]["row_count"] == 3
    assert history_body["items"][0]["column_count"] == 5

    retained_path = tmp_path / "retained-uploads" / history_body["items"][0]["storage_path"]
    assert retained_path.exists()
    assert retained_path.read_text(encoding="utf-8").startswith("patient_id,visit_date")

    second_state = _api_state(tmp_path / "second")
    second_state.analytics_upload_store = SqlAlchemyAnalyticsUploadStore(
        database_url=database_url,
        upload_root=tmp_path / "retained-uploads",
    )
    second_client = TestClient(create_app(second_state))
    persisted_items = second_client.get("/analytics/table-uploads").json()["items"]
    assert persisted_items[0]["id"] == body["upload_id"]


def test_analytics_table_upload_profiles_xlsx_file(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    client = TestClient(create_app(state))
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "收费明细"
    worksheet.append(["患者编号", "结算日期", "项目编码", "收费金额"])
    worksheet.append(["P001", "2026-01-01", "A100", 120])
    worksheet.append(["P002", "2026-01-02", "B200", 80])
    buffer = BytesIO()
    workbook.save(buffer)

    response = client.post(
        "/analytics/table-upload",
        files={
            "file": (
                "charge-workbook.xlsx",
                buffer.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "charge-workbook.xlsx"
    assert body["extension"] == "xlsx"
    assert body["sheet_name"] == "收费明细"
    assert body["row_count"] == 2
    assert body["columns"][3]["name"] == "收费金额"
    assert body["columns"][3]["type"] == "数值"
    assert body["message"] == "后端已完成 XLSX 工作簿（sheet: 收费明细）的字段画像。"


def test_analytics_table_upload_rejects_unsupported_extension(tmp_path: Path) -> None:
    client = TestClient(create_app(_api_state(tmp_path)))

    response = client.post(
        "/analytics/table-upload",
        files={"file": ("charges.txt", "not,a,supported,file", "text/plain")},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "unsupported table file extension"


def test_documents_permissions_and_uploads_are_role_scoped(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'document-uploads.db'}"
    upload_root = tmp_path / "document-uploads"
    state = _api_state(tmp_path)
    state.document_upload_store = SqlAlchemyDocumentUploadStore(
        database_url=database_url,
        upload_root=upload_root,
        create_schema=True,
    )
    client = TestClient(create_app(state))

    permissions_response = client.get("/documents/permissions", headers={"X-Role": "auditor"})

    assert permissions_response.status_code == 200
    permissions_body = permissions_response.json()
    assert permissions_body["role"] == "auditor"
    assert [item["source_collection"] for item in permissions_body["source_collections"]] == [
        "medical-insurance-laws",
        "supervision-rules-knowledge",
        "medical-insurance-catalog",
        "risk-negative-list",
    ]
    assert permissions_body["upload_permissions"] == {
        "can_upload_personal": True,
        "can_read_all_personal_uploads": False,
        "can_govern_personal_uploads": False,
    }

    upload_response = client.post(
        "/documents/uploads",
        headers={"X-User-Id": "auditor-1", "X-Role": "auditor"},
        files={"file": ("policy.pdf", b"%PDF-1.4 policy", "application/pdf")},
    )

    assert upload_response.status_code == 200
    upload_body = upload_response.json()
    uploaded = upload_body["item"]
    assert uploaded["id"].startswith(DOCUMENT_UPLOAD_ID_PREFIX)
    assert uploaded["created_by"] == "auditor-1"
    assert uploaded["extension"] == "pdf"
    assert uploaded["retention_status"] == "retained"
    assert uploaded["index_status"] == "not-indexed"
    assert uploaded["governance_status"] == "pending-review"
    assert uploaded["governance_note"] == ""
    assert uploaded["governed_by"] is None
    assert uploaded["governed_at"] is None
    assert uploaded["security_scan_status"] == "local-policy-passed"
    assert uploaded["security_scan_provider"] == "local-policy"
    assert uploaded["dlp_status"] == "clear"
    assert uploaded["security_findings"] == []
    assert uploaded["download_url"] == f"/api/v1/documents/uploads/{uploaded['id']}/download"
    assert uploaded["sha256"]
    assert upload_body["store"]["backend"] == "SqlAlchemyDocumentUploadStore"
    assert state.operation_logs[-1]["action"] == "document-upload"
    assert state.operation_logs[-1]["payload"]["index_status"] == "not-indexed"

    retained_path = upload_root / uploaded["storage_path"]
    assert retained_path.exists()
    assert retained_path.read_bytes() == b"%PDF-1.4 policy"

    owner_response = client.get(
        "/documents/uploads",
        headers={"X-User-Id": "auditor-1", "X-Role": "auditor"},
    )
    assert owner_response.status_code == 200
    assert owner_response.json()["items"][0]["id"] == uploaded["id"]

    owner_download_response = client.get(
        f"/documents/uploads/{uploaded['id']}/download",
        headers={"X-User-Id": "auditor-1", "X-Role": "auditor"},
    )
    assert owner_download_response.status_code == 200
    assert owner_download_response.content == b"%PDF-1.4 policy"
    assert owner_download_response.headers["x-document-upload-id"] == uploaded["id"]
    assert owner_download_response.headers["x-document-security-scan"] == "local-policy-passed"
    assert state.operation_logs[-1]["action"] == "document-upload-download"

    other_auditor_response = client.get(
        "/documents/uploads",
        headers={"X-User-Id": "auditor-2", "X-Role": "auditor"},
    )
    assert other_auditor_response.status_code == 200
    assert other_auditor_response.json()["items"] == []

    other_download_response = client.get(
        f"/documents/uploads/{uploaded['id']}/download",
        headers={"X-User-Id": "auditor-2", "X-Role": "auditor"},
    )
    assert other_download_response.status_code == 404
    assert state.operation_logs[-1]["action"] == "authorization-denied"
    assert state.operation_logs[-1]["payload"]["attempted_action"] == "document-upload-download"

    admin_response = client.get(
        "/documents/uploads",
        headers={"X-User-Id": "admin-1", "X-Role": "it-admin"},
    )
    assert admin_response.status_code == 200
    admin_body = admin_response.json()
    assert admin_body["permissions"]["can_read_all_personal_uploads"] is True
    assert admin_body["permissions"]["can_govern_personal_uploads"] is True
    assert admin_body["items"][0]["id"] == uploaded["id"]

    admin_download_response = client.get(
        f"/documents/uploads/{uploaded['id']}/download",
        headers={"X-User-Id": "admin-1", "X-Role": "it-admin"},
    )
    assert admin_download_response.status_code == 200
    assert admin_download_response.content == b"%PDF-1.4 policy"

    member_governance_response = client.post(
        f"/documents/uploads/{uploaded['id']}/governance",
        headers={"X-User-Id": "auditor-1", "X-Role": "auditor"},
        json={"governance_status": "approved-for-index", "note": "member should not approve"},
    )
    assert member_governance_response.status_code == 403

    governance_response = client.post(
        f"/documents/uploads/{uploaded['id']}/governance",
        headers={"X-User-Id": "admin-1", "X-Role": "it-admin"},
        json={"governance_status": "approved-for-index", "note": "已完成材料治理。"},
    )
    assert governance_response.status_code == 200
    governed = governance_response.json()["item"]
    assert governed["governance_status"] == "approved-for-index"
    assert governed["governance_note"] == "已完成材料治理。"
    assert governed["governed_by"] == "admin-1"
    assert governed["governed_at"]
    assert governed["index_status"] == "index-ready"
    assert state.operation_logs[-1]["action"] == "document-upload-governance-update"

    governed_admin_items = client.get(
        "/documents/uploads",
        headers={"X-User-Id": "admin-1", "X-Role": "it-admin"},
    ).json()["items"]
    assert governed_admin_items[0]["governance_status"] == "approved-for-index"
    assert governed_admin_items[0]["index_status"] == "index-ready"

    second_state = _api_state(tmp_path / "second")
    second_state.document_upload_store = SqlAlchemyDocumentUploadStore(
        database_url=database_url,
        upload_root=upload_root,
    )
    second_client = TestClient(create_app(second_state))
    persisted_items = second_client.get(
        "/documents/uploads",
        headers={"X-User-Id": "auditor-1", "X-Role": "auditor"},
    ).json()["items"]
    assert persisted_items[0]["id"] == uploaded["id"]
    assert persisted_items[0]["governance_status"] == "approved-for-index"
    assert persisted_items[0]["index_status"] == "index-ready"


def test_documents_permissions_use_persistent_role_and_status_gate(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    state.auth_user_store = SqlAlchemyAuthUserStore(
        f"sqlite:///{tmp_path / 'auth-users.db'}",
        create_schema=True,
    )
    assert state.auth_user_store is not None
    state.auth_user_store.add_user(
        {
            "user_key": "persistent-document-director",
            "display_name": "文档主任",
            "status": "active",
        }
    )
    state.auth_user_store.assign_role(
        "persistent-document-director",
        {"role": "director", "scope_type": "global"},
    )
    client = TestClient(create_app(state))

    permissions_response = client.get(
        "/documents/permissions",
        headers={"X-User-Id": "persistent-document-director", "X-Role": "auditor"},
    )
    disabled_user = state.auth_user_store.update_user(
        "persistent-document-director",
        {"status": "disabled"},
    )
    denied_response = client.get(
        "/documents/permissions",
        headers={"X-User-Id": "persistent-document-director", "X-Role": "director"},
    )

    assert permissions_response.status_code == 200
    permissions_body = permissions_response.json()
    assert permissions_body["role"] == "department-head"
    assert permissions_body["upload_permissions"]["can_read_all_personal_uploads"] is True
    assert permissions_body["upload_permissions"]["can_govern_personal_uploads"] is True
    assert disabled_user["status"] == "disabled"
    assert denied_response.status_code == 403
    assert denied_response.json()["detail"] == "auth user status is disabled"


def test_documents_upload_rejects_unsupported_extension(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    state.document_upload_store = InMemoryDocumentUploadStore(
        upload_root=tmp_path / "document-uploads",
    )
    client = TestClient(create_app(state))

    response = client.post(
        "/documents/uploads",
        files={"file": ("policy.exe", b"binary", "application/octet-stream")},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "unsupported document file extension"


def test_documents_upload_local_policy_blocks_index_approval_until_review(
    tmp_path: Path,
) -> None:
    state = _api_state(tmp_path)
    state.document_upload_store = InMemoryDocumentUploadStore(
        upload_root=tmp_path / "document-uploads",
    )
    client = TestClient(create_app(state))

    upload_response = client.post(
        "/documents/uploads",
        headers={"X-User-Id": "auditor-1", "X-Role": "auditor"},
        files={"file": ("notes.txt", "password=example", "text/plain")},
    )

    assert upload_response.status_code == 200
    uploaded = upload_response.json()["item"]
    assert uploaded["security_scan_status"] == "local-policy-review"
    assert uploaded["dlp_status"] == "needs-review"
    assert uploaded["security_findings"] == ["sensitive-keyword:credential"]

    governance_response = client.post(
        f"/documents/uploads/{uploaded['id']}/governance",
        headers={"X-User-Id": "admin-1", "X-Role": "it-admin"},
        json={"governance_status": "approved-for-index", "note": "review later"},
    )

    assert governance_response.status_code == 409
    assert governance_response.json()["detail"] == (
        "document upload security review is required before index approval"
    )
    assert state.operation_logs[-1]["action"] == "document-upload-governance-blocked"
    assert state.operation_logs[-1]["payload"]["security_finding_count"] == 1


def test_personal_document_index_is_governed_and_query_scoped(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    state.document_upload_store = InMemoryDocumentUploadStore(
        upload_root=tmp_path / "document-uploads",
    )
    client = TestClient(create_app(state))

    upload_response = client.post(
        "/documents/uploads",
        headers={"X-User-Id": "auditor-1", "X-Role": "auditor"},
        files={
            "file": (
                "local-note.txt",
                "院内个人材料提示：医保基金审核依据需核对院内报销清单。",
                "text/plain",
            )
        },
    )

    assert upload_response.status_code == 200
    uploaded = upload_response.json()["item"]
    assert uploaded["personal_index_status"] == "not-indexed"
    assert uploaded["personal_index_chunk_count"] == 0

    unapproved_index_response = client.post(
        f"/documents/uploads/{uploaded['id']}/index",
        headers={"X-User-Id": "auditor-1", "X-Role": "auditor"},
    )
    assert unapproved_index_response.status_code == 409
    assert unapproved_index_response.json()["detail"] == (
        "document upload must be approved before personal index"
    )

    governance_response = client.post(
        f"/documents/uploads/{uploaded['id']}/governance",
        headers={"X-User-Id": "admin-1", "X-Role": "it-admin"},
        json={"governance_status": "approved-for-index", "note": "可进入个人材料索引。"},
    )
    assert governance_response.status_code == 200

    index_response = client.post(
        f"/documents/uploads/{uploaded['id']}/index",
        headers={"X-User-Id": "auditor-1", "X-Role": "auditor"},
    )
    assert index_response.status_code == 200
    indexed = index_response.json()["item"]
    assert indexed["personal_index_status"] == "indexed"
    assert indexed["personal_index_chunk_count"] == 1
    assert indexed["personal_indexed_by"] == "auditor-1"
    assert state.operation_logs[-1]["action"] == "document-upload-index"

    owner_query_response = client.post(
        "/query",
        headers={"X-User-Id": "auditor-1", "X-Role": "auditor"},
        json={"question": "医保基金审核依据", "top_k": 2},
    )
    assert owner_query_response.status_code == 200
    owner_body = owner_query_response.json()
    assert owner_body["personal_upload_matches"][0]["upload_id"] == uploaded["id"]
    assert "院内个人材料提示" in owner_body["personal_upload_matches"][0]["snippet"]
    assert state.query_logs[-1]["personal_upload_match_count"] == 1

    other_query_response = client.post(
        "/query",
        headers={"X-User-Id": "auditor-2", "X-Role": "auditor"},
        json={"question": "医保基金审核依据", "top_k": 2},
    )
    assert other_query_response.status_code == 200
    assert other_query_response.json()["personal_upload_matches"] == []

    admin_query_response = client.post(
        "/query",
        headers={"X-User-Id": "admin-1", "X-Role": "it-admin"},
        json={"question": "医保基金审核依据", "top_k": 2},
    )
    assert admin_query_response.status_code == 200
    assert admin_query_response.json()["personal_upload_matches"][0]["upload_id"] == uploaded["id"]


def test_query_endpoint_returns_citation_answer_and_records_query_log(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    client = TestClient(create_app(state))

    response = client.post(
        "/query",
        headers={"X-User-Id": "auditor-1", "X-Role": "auditor"},
        json={"question": "医保基金审核依据", "top_k": 2},
    )

    assert response.status_code == 200
    body = response.json()
    assert "[C1]" in body["answer"]
    assert body["citations"][0]["source_collection"] == "medical-insurance-laws"
    assert body["citations"][0]["index_version_key"] == "index-v1"
    assert body["citations"][0]["source_package_version_key"] == "package-v1"
    assert body["basis_groups"][0]["title"] == "法规依据"
    assert body["basis_groups"][0]["items"][0]["source_collection"] == "medical-insurance-laws"
    assert body["query_log_index"] == 0

    logs_response = client.get("/query/logs")
    assert logs_response.status_code == 200
    assert logs_response.json()["items"][0]["user_identifier"] == "auditor-1"
    assert logs_response.json()["items"][0]["filters"]["top_k"] == 2


def test_query_endpoint_records_selected_agent_invocation(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    state.agent_store = SqlAlchemyAgentStore(
        f"sqlite:///{tmp_path / 'query-agent-invocations.db'}",
        create_schema=True,
    )
    client = TestClient(create_app(state))

    response = client.post(
        "/query",
        headers={
            "X-User-Id": "auditor-1",
            "X-Role": "auditor",
            "X-Project-Name": PROJECT_NAME_HEADER,
        },
        json={
            "question": "医保基金审核依据",
            "top_k": 2,
            "agent": "agent-citation-check",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["agent_invocation_id"]
    assert state.agent_store is not None
    invocations = state.agent_store.list_invocations("agent-citation-check")
    assert invocations[0]["id"] == body["agent_invocation_id"]
    assert invocations[0]["invocation_source"] == "/query"
    assert invocations[0]["question"] == "医保基金审核依据"
    assert invocations[0]["metadata"]["filters"]["agent"] == "agent-citation-check"
    assert state.operation_logs[-2]["action"] == "agent-invocation-create"
    assert state.operation_logs[-1]["action"] == "query"
    assert state.operation_logs[-1]["payload"]["agent_invocation_id"] == body["agent_invocation_id"]


def test_query_endpoint_supports_title_only_filter(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    client = TestClient(create_app(state))

    response = client.post(
        "/query",
        headers={"X-User-Id": "auditor-1", "X-Role": "auditor"},
        json={"question": "医保基金审核依据", "top_k": 2, "title_only": True},
    )
    unmatched_response = client.post(
        "/query",
        headers={"X-User-Id": "auditor-1", "X-Role": "auditor"},
        json={"question": "不存在的标题", "top_k": 2, "title_only": True},
    )

    assert response.status_code == 200
    assert response.json()["citations"][0]["source_collection"] == "medical-insurance-laws"
    assert state.query_logs[-1]["filters"]["title_only"] is True
    assert state.operation_logs[-1]["payload"]["filters"]["title_only"] is True
    assert unmatched_response.status_code == 404


def test_query_endpoint_uses_persistent_user_status_gate(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    state.auth_user_store = SqlAlchemyAuthUserStore(
        f"sqlite:///{tmp_path / 'auth-users.db'}",
        create_schema=True,
    )
    assert state.auth_user_store is not None
    state.auth_user_store.add_user(
        {
            "user_key": "disabled-query-user",
            "display_name": "停用查询用户",
            "status": "disabled",
        }
    )
    client = TestClient(create_app(state))

    response = client.post(
        "/query",
        headers={"X-User-Id": "disabled-query-user", "X-Role": "it-admin"},
        json={"question": "医保基金审核依据", "top_k": 2},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "auth user status is disabled"


def test_query_endpoint_persists_query_history(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'query-history.db'}"
    state = _api_state(tmp_path)
    state.query_history_store = SqlAlchemyQueryHistoryStore(database_url, create_schema=True)
    client = TestClient(create_app(state))

    response = client.post(
        "/query",
        headers={"X-User-Id": "auditor-1", "X-Role": "auditor"},
        json={
            "question": "医保基金审核依据",
            "top_k": 2,
            "source_collections": ["medical-insurance-laws"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["query_log_id"]

    history_response = client.get("/query/logs?limit=5")
    assert history_response.status_code == 200
    history_body = history_response.json()
    assert history_body["store"]["backend"] == "SqlAlchemyQueryHistoryStore"
    assert history_body["items"][0]["id"] == body["query_log_id"]
    assert history_body["items"][0]["question"] == "医保基金审核依据"
    assert history_body["items"][0]["filters"]["source_collections"] == ["medical-insurance-laws"]
    assert history_body["items"][0]["citation_count"] == 1
    assert history_body["items"][0]["answer_summary"]

    second_state = _api_state(tmp_path / "second")
    second_state.query_history_store = SqlAlchemyQueryHistoryStore(database_url)
    second_client = TestClient(create_app(second_state))
    persisted_items = second_client.get("/query/logs").json()["items"]
    assert persisted_items[0]["id"] == body["query_log_id"]


def test_query_history_store_failure_does_not_block_query(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    state.query_history_store = FailingQueryHistoryStore()
    client = TestClient(create_app(state))

    response = client.post(
        "/query",
        json={"question": "医保基金审核依据", "top_k": 2},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["query_log_id"] is None
    assert state.operation_logs[-1]["payload"]["query_history_error"] == {
        "error_type": "RuntimeError",
        "message": "query history store operation failed",
    }

    logs_response = client.get("/query/logs")
    assert logs_response.status_code == 200
    logs_body = logs_response.json()
    assert logs_body["store"] == {
        "ready": False,
        "backend": "FailingQueryHistoryStore",
        "error": {
            "error_type": "RuntimeError",
            "message": "query history store operation failed",
        },
    }
    assert logs_body["items"][0]["question"] == "医保基金审核依据"


def test_query_endpoint_uses_configured_answer_generation_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "medical_audit_kb.api.app.answer_generation_provider_from_settings",
        lambda _settings: StaticApiAnswerProvider(),
        raising=False,
    )
    state = _api_state(tmp_path)
    client = TestClient(create_app(state))

    response = client.post(
        "/query",
        headers={"X-Role": "auditor"},
        json={"question": "医保基金审核依据", "top_k": 2},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["fallback_used"] is False
    assert body["answer"] == "生成模型回答：应核验医保基金审核依据 [C1]。"


def test_query_endpoint_blocks_unknown_role(tmp_path: Path) -> None:
    client = TestClient(create_app(_api_state(tmp_path)))

    response = client.post(
        "/query",
        headers={"X-Role": "guest"},
        json={"question": "医保基金审核依据"},
    )

    assert response.status_code == 403


def test_preview_endpoint_resolves_chunk_reference_after_query(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    client = TestClient(create_app(state))
    query_response = client.post(
        "/query",
        headers={"X-Role": "auditor"},
        json={"question": "医保基金审核依据"},
    )
    chunk_id = query_response.json()["citations"][0]["chunk_id"]

    preview_response = client.get(f"/preview/{chunk_id}")

    assert preview_response.status_code == 200
    body = preview_response.json()
    assert body["chunk_id"] == chunk_id
    assert "医疗机构应当保留医保基金审核依据" in body["preview_text"]
    assert body["highlights"]
    assert body["line_start"] == 1


def test_index_rebuild_incremental_lists_and_permissions(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    source_root = state.source_root
    _write_text(source_root / "医保目录" / "catalog.md", "# 医保目录\n医保目录内容")
    _write_text(source_root / "风险负面清单" / "risk.png", "pending")
    client = TestClient(create_app(state))

    forbidden_response = client.post(
        "/index/rebuild",
        headers={"X-Role": "auditor"},
        json={"package_version_key": "api-package"},
    )
    assert forbidden_response.status_code == 403

    rebuild_response = client.post(
        "/index/rebuild",
        headers={"X-Role": "it-admin"},
        json={"package_version_key": "api-package"},
    )
    assert rebuild_response.status_code == 200
    rebuild_summary = rebuild_response.json()["summary"]
    assert rebuild_summary["job_type"] == "full-rebuild"
    assert rebuild_summary["index_candidate_file_count"] == 1
    assert rebuild_summary["pending_file_count"] == 1

    incremental_response = client.post(
        "/index/incremental",
        headers={"X-Role": "it-admin"},
        json={"package_version_key": "api-package-next"},
    )
    assert incremental_response.status_code == 200
    assert incremental_response.json()["summary"]["job_type"] == "incremental"

    versions = client.get("/index/versions").json()["items"]
    jobs = client.get("/index/jobs").json()["items"]
    pending = client.get("/index/pending").json()["items"]
    failures = client.get("/index/failures").json()["items"]

    assert len(versions) == 2
    assert len(jobs) == 2
    assert jobs[-1]["status"] == "succeeded"
    assert pending[0]["relative_path"] == "风险负面清单/risk.png"
    assert failures == []


def test_index_rebuild_allows_technician_role(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    _write_text(state.source_root / "医保目录" / "catalog.md", "# 医保目录\n医保目录内容")
    client = TestClient(create_app(state))

    response = client.post(
        "/index/rebuild",
        headers={"X-User-Id": "technician-1", "X-Role": "technician"},
        json={"package_version_key": "technician-package"},
    )

    assert response.status_code == 200
    assert response.json()["summary"]["job_type"] == "full-rebuild"


def test_index_retry_file_reports_missing_target(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    _write_text(state.source_root / "医保目录" / "catalog.md", "# 医保目录\n医保目录内容")
    client = TestClient(create_app(state))

    response = client.post(
        "/index/retry-file",
        headers={"X-Role": "it-admin"},
        json={"package_version_key": "retry-package", "relative_path": "医保目录/missing.md"},
    )

    assert response.status_code == 200
    assert response.json()["summary"]["failed_file_count"] == 1
    assert (
        client.get("/index/failures").json()["items"][0]["relative_path"] == "医保目录/missing.md"
    )


def test_index_postgres_status_reports_database_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _api_state(tmp_path)

    def fake_load_postgres_index_status(database_url: str) -> dict[str, object]:
        return {
            "available": True,
            "row_counts": {
                "source_package_versions": 1,
                "source_documents": 486,
                "document_chunks": 48985,
                "chunk_embeddings": 48985,
                "index_versions": 1,
                "index_jobs": 1,
                "failed_files": 0,
                "pending_files": 13,
            },
            "embedding_sets": [
                {
                    "provider": "openai",
                    "model_name": "kimi-for-coding",
                    "provider_version": "v1",
                    "dimension": 1024,
                    "embedding_count": 48985,
                }
            ],
            "index_versions": [
                {
                    "version_key": "source-package-real-data-kimi-20260531",
                    "status": "active",
                    "vector_provider": "openai",
                    "vector_model": "kimi-for-coding",
                    "chunk_count": 48985,
                    "document_count": 486,
                }
            ],
            "source_packages": [
                {
                    "version_key": "source-package-real-data-kimi-20260531",
                    "source_root_path": "data/医保审核前期资料",
                }
            ],
        }

    monkeypatch.setattr(
        "medical_audit_kb.api.routes_index.load_postgres_index_status",
        fake_load_postgres_index_status,
    )
    client = TestClient(create_app(state))

    response = client.get("/index/postgres-status")

    assert response.status_code == 200
    body = response.json()
    assert body["row_counts"]["document_chunks"] == 48985
    assert body["row_counts"]["pending_files"] == 13
    assert body["embedding_sets"][0]["model_name"] == "kimi-for-coding"
    assert state.operation_logs[-1]["action"] == "postgres-index-status-view"


def test_index_postgres_search_backend_loads_with_admin_role(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _api_state(tmp_path)
    state.search_engine = None
    loaded_engine = _search_engine(_chunk_id(), "全量法律/law.md")
    captured: dict[str, object] = {}

    def fake_load_postgres_hybrid_search_engine(
        *,
        database_url: str,
        embedding_provider: DeterministicFakeEmbeddingProvider,
    ) -> HybridSearchEngine:
        captured["database_url"] = database_url
        captured["embedding_provider"] = embedding_provider
        return loaded_engine

    monkeypatch.setattr(
        "medical_audit_kb.api.routes_index.load_postgres_hybrid_search_engine",
        fake_load_postgres_hybrid_search_engine,
    )
    monkeypatch.setattr(
        "medical_audit_kb.api.routes_index.count_postgres_embeddings",
        lambda database_url, embedding_provider: 48985,
    )
    client = TestClient(create_app(state))

    status_response = client.get("/index/search-backend")
    assert status_response.status_code == 200
    assert status_response.json() == {"backend": "none", "ready": False, "details": {}}

    forbidden_response = client.post(
        "/index/search-backend/postgres",
        headers={"X-Role": "auditor"},
        json={
            "embedding_provider": "fake",
            "embedding_model": "fake",
            "embedding_dimension": 32,
        },
    )
    assert forbidden_response.status_code == 403

    response = client.post(
        "/index/search-backend/postgres",
        headers={"X-Role": "it-admin"},
        json={
            "embedding_provider": "fake",
            "embedding_model": "fake",
            "embedding_dimension": 32,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["backend"] == "postgres"
    assert body["ready"] is True
    assert body["details"]["embedding_provider"] == "fake"
    assert body["details"]["embedding_dimension"] == 32
    assert body["details"]["matching_embedding_count"] == 48985
    assert id(state.search_engine) == id(loaded_engine)
    assert captured["database_url"] == state.settings.database_url


def test_index_postgres_search_backend_rejects_unmatched_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _api_state(tmp_path)
    state.search_engine = None

    def fake_count_postgres_embeddings(
        database_url: str,
        embedding_provider: DeterministicFakeEmbeddingProvider,
    ) -> int:
        raise ValueError("no postgres embeddings match requested provider metadata")

    monkeypatch.setattr(
        "medical_audit_kb.api.routes_index.count_postgres_embeddings",
        fake_count_postgres_embeddings,
    )
    client = TestClient(create_app(state))

    response = client.post(
        "/index/search-backend/postgres",
        headers={"X-Role": "it-admin"},
        json={
            "embedding_provider": "fake",
            "embedding_model": "fake",
            "embedding_dimension": 1536,
        },
    )

    assert response.status_code == 409
    assert "no postgres embeddings match" in response.json()["detail"]
    assert state.search_engine is None
    assert state.search_backend == "none"


def test_index_version_activate_and_rollback_actions_require_admin(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _api_state(tmp_path)
    client = TestClient(create_app(state))

    monkeypatch.setattr(
        "medical_audit_kb.api.routes_index.activate_index_version",
        lambda **kwargs: IndexActivationResult(
            index_version_key=str(kwargs["index_version_key"]),
            vector_provider="openai",
            vector_model="kimi-for-coding",
            previous_status="candidate",
            deactivated_index_version_keys=("active-old",),
        ),
    )
    monkeypatch.setattr(
        "medical_audit_kb.api.routes_index.rollback_index_version",
        lambda **kwargs: IndexRollbackResult(
            index_version_key=str(kwargs["index_version_key"]),
            vector_provider="openai",
            vector_model="kimi-for-coding",
            previous_status="inactive",
            deactivated_index_version_keys=("active-current",),
        ),
    )

    forbidden_response = client.post(
        "/index/versions/activate",
        headers={"X-Role": "auditor"},
        json={"index_version_key": "candidate-next"},
    )
    assert forbidden_response.status_code == 403

    activate_response = client.post(
        "/index/versions/activate",
        headers={"X-Role": "it-admin"},
        json={"index_version_key": "candidate-next"},
    )
    assert activate_response.status_code == 200
    assert activate_response.json()["result"]["index_version_key"] == "candidate-next"
    assert str(state.operation_logs[-1]["action"]) == "index-version-activate"

    rollback_response = client.post(
        "/index/versions/rollback",
        headers={"X-Role": "it-admin"},
        json={"index_version_key": "active-old"},
    )
    assert rollback_response.status_code == 200
    assert rollback_response.json()["result"]["previous_status"] == "inactive"
    assert str(state.operation_logs[-1]["action"]) == "index-version-rollback"


def test_index_version_switch_returns_conflict_for_invalid_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = TestClient(create_app(_api_state(tmp_path)))

    def fake_activate_index_version(**kwargs: object) -> IndexActivationResult:
        raise IndexActivationError("index version must be candidate or active")

    monkeypatch.setattr(
        "medical_audit_kb.api.routes_index.activate_index_version",
        fake_activate_index_version,
    )

    response = client.post(
        "/index/versions/activate",
        headers={"X-Role": "it-admin"},
        json={"index_version_key": "inactive-old"},
    )

    assert response.status_code == 409
    assert "candidate or active" in response.json()["detail"]


def test_index_evaluation_run_scores_runtime_backend_and_records_status(
    tmp_path: Path,
) -> None:
    state = _api_state(tmp_path)
    retrieval_cases = _write_text(
        tmp_path / "retrieval-cases.yaml",
        """
cases:
  - case_id: retrieval-case-001
    question: 医疗机构需要保留什么审核依据？
    expected_evidence:
      - source_collection: medical-insurance-laws
        source_path: 全量法律/law.md
        article_or_rule: 第一条
""".strip(),
    )
    answer_cases = _write_text(
        tmp_path / "answer-cases.yaml",
        """
cases:
  - case_id: answer-case-001
    question: 医疗机构需要保留什么审核依据？
    expected_behavior: answer
    required_evidence_terms: [第一条]
    required_answer_terms: [审核依据]
    required_citation_terms: [医疗机构]
""".strip(),
    )
    client = TestClient(create_app(state))

    forbidden_response = client.post(
        "/index/evaluation/run",
        headers={"X-Role": "auditor"},
        json={},
    )
    assert forbidden_response.status_code == 403

    response = client.post(
        "/index/evaluation/run",
        headers={"X-Role": "it-admin"},
        json={
            "retrieval_cases_file": str(retrieval_cases),
            "answer_cases_file": str(answer_cases),
            "max_retrieval_cases": 1,
            "max_answer_cases": 1,
            "top_k": 2,
            "smoke_question": "医保基金审核依据",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pass"
    assert body["retrieval"]["case_count"] == 1
    assert body["retrieval"]["recall_at_k"] == 1.0
    assert body["answer"]["case_count"] == 1
    assert body["answer"]["pass_rate"] == 1.0
    assert body["ui_smoke"]["success"] is True
    assert state.evaluation_runs[-1]["status"] == "pass"
    assert state.operation_logs[-1]["action"] == "index-evaluation-run"


def test_index_evaluation_run_persists_json_report_and_exports_latest(
    tmp_path: Path,
) -> None:
    state = _api_state(tmp_path)
    retrieval_cases = _write_text(
        tmp_path / "retrieval-cases.yaml",
        """
cases:
  - case_id: retrieval-case-001
    question: 医疗机构需要保留什么审核依据？
    expected_evidence:
      - source_collection: medical-insurance-laws
        source_path: 全量法律/law.md
        article_or_rule: 第一条
""".strip(),
    )
    answer_cases = _write_text(
        tmp_path / "answer-cases.yaml",
        """
cases:
  - case_id: answer-case-001
    question: 医疗机构需要保留什么审核依据？
    expected_behavior: answer
    required_evidence_terms: [第一条]
    required_answer_terms: [审核依据]
    required_citation_terms: [医疗机构]
""".strip(),
    )
    client = TestClient(create_app(state))

    response = client.post(
        "/index/evaluation/run",
        headers={"X-Role": "it-admin"},
        json={
            "retrieval_cases_file": str(retrieval_cases),
            "answer_cases_file": str(answer_cases),
            "max_retrieval_cases": 1,
            "max_answer_cases": 1,
            "top_k": 2,
            "smoke_question": "医保基金审核依据",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["report"]["download_path"] == "/index/evaluation/latest/export"
    report_path = Path(body["report"]["path"])
    assert report_path.is_file()
    assert report_path.parent == state.settings.index_root / "evaluation-runs"
    persisted = json.loads(report_path.read_text(encoding="utf-8"))
    assert persisted["status"] == "pass"
    assert persisted["request"]["max_retrieval_cases"] == 1
    assert persisted["search_backend"]["backend"] == "none"

    export_response = client.get("/index/evaluation/latest/export")

    assert export_response.status_code == 200
    exported = export_response.json()
    assert exported["run_id"] == body["report"]["run_id"]
    assert exported["status"] == "pass"
    assert state.operation_logs[-1]["action"] == "index-evaluation-report-export"


def test_index_evaluation_run_records_postgres_history_when_backend_is_postgres(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _api_state(tmp_path)
    state.search_backend = "postgres"
    state.search_backend_details = {
        "embedding_model": "kimi-for-coding",
        "embedding_dimension": 1024,
        "matching_embedding_count": 48985,
    }
    retrieval_cases = _write_text(
        tmp_path / "retrieval-cases.yaml",
        """
cases:
  - case_id: retrieval-case-001
    question: 医疗机构需要保留什么审核依据？
    expected_evidence:
      - source_collection: medical-insurance-laws
        source_path: 全量法律/law.md
        article_or_rule: 第一条
""".strip(),
    )
    answer_cases = _write_text(
        tmp_path / "answer-cases.yaml",
        """
cases:
  - case_id: answer-case-001
    question: 医疗机构需要保留什么审核依据？
    expected_behavior: answer
    required_evidence_terms: [第一条]
    required_answer_terms: [审核依据]
    required_citation_terms: [医疗机构]
""".strip(),
    )
    captured: dict[str, object] = {}

    def fake_persist_evaluation_history(
        history_state: ApiState,
        report: dict[str, object],
    ) -> dict[str, object]:
        captured["state"] = history_state
        captured["report"] = report
        return {
            "backend": "postgres",
            "persisted": True,
            "table": "index_evaluation_runs",
            "run_id": report["run_id"],
        }

    monkeypatch.setattr(
        "medical_audit_kb.api.evaluation_reports.persist_evaluation_history",
        fake_persist_evaluation_history,
    )
    client = TestClient(create_app(state))

    response = client.post(
        "/index/evaluation/run",
        headers={"X-Role": "it-admin"},
        json={
            "retrieval_cases_file": str(retrieval_cases),
            "answer_cases_file": str(answer_cases),
            "max_retrieval_cases": 1,
            "max_answer_cases": 1,
            "top_k": 2,
            "smoke_question": "医保基金审核依据",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["history"]["persisted"] is True
    assert body["history"]["table"] == "index_evaluation_runs"
    assert body["report"]["history"]["persisted"] is True
    assert captured["state"] is state
    report = captured["report"]
    assert isinstance(report, dict)
    assert report["request"]["top_k"] == 2
    assert report["search_backend"]["backend"] == "postgres"
    assert report["report"]["path"].endswith(".json")


def test_index_evaluation_history_lists_runs_and_records_log(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _api_state(tmp_path)

    def fake_list_evaluation_history(
        history_state: ApiState,
        *,
        limit: int = 20,
    ) -> list[dict[str, object]]:
        assert history_state is state
        assert limit == 20
        return [
            {
                "run_id": "11111111-1111-4111-8111-111111111111",
                "status": "pass",
                "generated_at": "2026-06-02T00:00:00+00:00",
                "retrieval_case_count": 52,
                "answer_case_count": 8,
                "ui_smoke_success": True,
                "report_path": "tmp/knowledge-query-indexes/evaluation-runs/report.json",
                "download_path": "/index/evaluation/latest/export",
                "source": "postgres",
            }
        ]

    monkeypatch.setattr(
        "medical_audit_kb.api.routes_index.list_evaluation_history",
        fake_list_evaluation_history,
    )
    client = TestClient(create_app(state))

    response = client.get("/index/evaluation/history")

    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["run_id"] == "11111111-1111-4111-8111-111111111111"
    assert body["items"][0]["source"] == "postgres"
    assert state.operation_logs[-1]["action"] == "index-evaluation-history-view"


def test_index_evaluation_export_returns_not_found_before_first_report(tmp_path: Path) -> None:
    client = TestClient(create_app(_api_state(tmp_path)))

    response = client.get("/index/evaluation/latest/export")

    assert response.status_code == 404
    assert "evaluation report not found" in response.json()["detail"]


def test_index_evaluation_run_requires_ready_search_backend(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    state.search_engine = None
    client = TestClient(create_app(state))

    response = client.post(
        "/index/evaluation/run",
        headers={"X-Role": "it-admin"},
        json={},
    )

    assert response.status_code == 409
    assert "search backend is not ready" in response.json()["detail"]


def _api_state(tmp_path: Path) -> ApiState:
    source_root = tmp_path / "data"
    source_file = source_root / "全量法律" / "law.md"
    _write_text(
        source_file,
        "\n".join(
            [
                "第一条 医疗机构应当保留医保基金审核依据。",
                "第二条 其他条款。",
            ]
        ),
    )
    settings = KnowledgeQuerySettings(
        data_root=source_root,
        index_root=tmp_path / "index",
        database_url="postgresql+psycopg://user:pass@localhost:5433/db",
        model_provider=ModelProviderSettings(
            provider="fake",
            api_key_env="OPENAI_API_KEY",
            embedding_model="fake",
            chat_model="fake",
        ),
        source_collection_weights={
            "medical-insurance-catalog": 1.25,
            "supervision-rules-knowledge": 1.35,
            "risk-negative-list": 1.1,
            "medical-insurance-laws": 1.0,
        },
    )
    state = ApiState.from_settings(settings)
    state.audit_log_store = None
    state.analytics_upload_store = InMemoryAnalyticsUploadStore(
        upload_root=settings.index_root / "analytics-uploads"
    )
    state.document_upload_store = InMemoryDocumentUploadStore(
        upload_root=settings.index_root / "document-uploads"
    )
    state.query_history_store = InMemoryQueryHistoryStore()
    state.search_engine = _search_engine(
        _chunk_id(),
        source_file.relative_to(source_root).as_posix(),
    )
    return state


def _search_engine(chunk_id: UUID, source_path: str) -> HybridSearchEngine:
    provider = DeterministicFakeEmbeddingProvider(dimension=32)
    chunk = ChunkEmbeddingInput(
        chunk_id=chunk_id,
        text="第一条 医疗机构应当保留医保基金审核依据。",
        metadata={
            "source_collection": SourceCollection.MEDICAL_INSURANCE_LAWS.value,
            "locator": {
                "type": "law-article",
                "source_path": source_path,
                "line_start": 1,
                "line_end": 1,
                "article_number": "第一条",
            },
            "index_version_key": "index-v1",
            "source_package_version_key": "package-v1",
            "title": "医保基金审核依据",
            "source_path": source_path,
            "title_path": ["医保基金审核依据"],
            "year": 2024,
            "region": "国家",
            "document_type": "law",
            "business_topic": "fund-supervision",
        },
    )
    vector_index = InMemoryVectorIndex(dimension=provider.dimension)
    vector_index.upsert(build_chunk_embedding_records([chunk], provider=provider))
    bm25_index = InMemoryBM25Index()
    bm25_index.upsert(
        [
            BM25Document(
                chunk_id=chunk.chunk_id,
                text=chunk.text,
                metadata=chunk.metadata,
            )
        ]
    )
    return HybridSearchEngine(
        embedding_provider=provider,
        vector_index=vector_index,
        bm25_index=bm25_index,
        rerank_provider=FakeRerankProvider(),
    )


def _chunk_id() -> UUID:
    return uuid4()


class StaticApiAnswerProvider:
    provider = "fake"
    model_name = "fake-chat"
    provider_version = "v1"

    def generate_answer(self, question: str, citations: Sequence[Citation]) -> str:
        return f"生成模型回答：应核验医保基金审核依据 {citations[0].marker}。"


class FailingQueryHistoryStore:
    def add_query(self, _values: dict[str, object]) -> dict[str, object]:
        raise RuntimeError("history database unavailable")

    def list_queries(self, *, limit: int = 20) -> list[dict[str, object]]:
        _ = limit
        raise RuntimeError("history database unavailable")


def _write_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path
