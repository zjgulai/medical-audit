from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from medical_audit_kb.api.app import ApiState, create_app
from medical_audit_kb.api.audit_log_store import SqlAlchemyAuditLogStore
from medical_audit_kb.api.auth_user_store import SqlAlchemyAuthUserStore
from medical_audit_kb.api.document_upload_store import (
    InMemoryDocumentUploadStore,
    SqlAlchemyDocumentUploadStore,
)
from medical_audit_kb.api.project_member_store import (
    InMemoryProjectMemberStore,
    ProjectIdentityConflictError,
    SqlAlchemyProjectMemberStore,
)
from medical_audit_kb.core.config import KnowledgeQuerySettings, ModelProviderSettings
from medical_audit_kb.db.models import AuditProject, AuditProjectMember

ADMIN_HEADERS = {"X-User-Id": "project-admin", "X-Role": "admin"}
PROJECT_PAYLOAD = {
    "project_key": "FUND-CHECK-202607",
    "name": "医保基金专项检查",
    "scenario_key": "charging-compliance",
    "audit_topic": "医保基金使用合规",
    "organization_name": "测试医院",
    "owner_department": "内审部",
    "description": "本地项目创建合同测试",
}


def test_create_project_persists_creator_membership_and_visibility(tmp_path: Path) -> None:
    state, database_url = _project_state(tmp_path)
    client = TestClient(create_app(state))

    response = client.post("/projects", headers=ADMIN_HEADERS, json=PROJECT_PAYLOAD)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["item"] == {
        "id": "FUND-CHECK-202607",
        "name": "医保基金专项检查",
        "audit_topic": "医保基金使用合规",
        "organization_name": "测试医院",
        "member_count": 1,
        "creator": "project-admin",
        "creator_user_identifier": "project-admin",
        "created_at": body["item"]["created_at"],
        "status": "待开始",
        "operation_label": "进入项目",
        "source": "collaboration-v1",
    }
    assert body["creator_member"]["user_identifier"] == "project-admin"
    assert body["creator_member"]["role"] == "项目负责人"
    assert body["creator_member"]["status"] == "在项目中"
    assert body["audit"] == {"status": "recorded"}
    assert state.operation_logs[-1]["action"] == "project-create"
    assert state.audit_log_store is not None
    audit_events = state.audit_log_store.list_events(user_identifier="project-admin")
    project_audit_events = [
        event
        for event in audit_events
        if event["action"] in {"project-create", "project-create-intent"}
    ]
    assert {event["action"] for event in project_audit_events} == {
        "project-create",
        "project-create-intent",
    }
    assert all(event["role"] == "admin" for event in project_audit_events)
    assert all(event["entity_type"] == "audit-project" for event in project_audit_events)
    assert all(event["entity_id"] == "FUND-CHECK-202607" for event in project_audit_events)

    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    with Session(engine) as session:
        project = session.scalar(
            select(AuditProject).where(AuditProject.project_key == "FUND-CHECK-202607")
        )
        member = session.scalar(
            select(AuditProjectMember).where(
                AuditProjectMember.project_key == "FUND-CHECK-202607"
            )
        )
        assert project is not None
        assert project.created_by == "project-admin"
        assert project.status == "待开始"
        assert project.extra_metadata["project_surface"] == "collaboration-v1"
        assert member is not None
        assert member.extra_metadata["user_identifier"] == "project-admin"

    creator_headers = {"X-User-Id": "project-admin", "X-Role": "member"}
    unrelated_headers = {"X-User-Id": "unrelated-member", "X-Role": "member"}
    assert [
        item["id"] for item in client.get("/projects", headers=creator_headers).json()["items"]
    ] == ["FUND-CHECK-202607"]
    assert client.get(
        "/projects/FUND-CHECK-202607", headers=creator_headers
    ).status_code == 200
    assert client.get("/projects", headers=unrelated_headers).json()["items"] == []
    assert client.get(
        "/projects/FUND-CHECK-202607", headers=unrelated_headers
    ).status_code == 404

    restarted_state, _ = _project_state(tmp_path, create_schema=False)
    restarted_client = TestClient(create_app(restarted_state))
    restarted_items = restarted_client.get(
        "/projects", headers=creator_headers
    ).json()["items"]
    assert [item["id"] for item in restarted_items] == ["FUND-CHECK-202607"]


def test_create_project_requires_permission_and_rejects_conflicts(tmp_path: Path) -> None:
    state, _ = _project_state(tmp_path)
    client = TestClient(create_app(state))

    anonymous = client.post("/projects", json=PROJECT_PAYLOAD)
    member = client.post(
        "/projects",
        headers={"X-User-Id": "ordinary-member", "X-Role": "member"},
        json=PROJECT_PAYLOAD,
    )
    default_conflict = client.post(
        "/projects",
        headers=ADMIN_HEADERS,
        json={**PROJECT_PAYLOAD, "project_key": "SELF-CHECK-FUND-20260607"},
    )
    created = client.post("/projects", headers=ADMIN_HEADERS, json=PROJECT_PAYLOAD)
    persisted_conflict = client.post("/projects", headers=ADMIN_HEADERS, json=PROJECT_PAYLOAD)

    assert anonymous.status_code == 401
    assert member.status_code == 403
    assert default_conflict.status_code == 409
    assert created.status_code == 201
    assert persisted_conflict.status_code == 409
    assert any(
        event["action"] == "authorization-denied"
        and event["payload"]["permission"] == "create_project"
        for event in state.operation_logs
    )


def test_admin_uploads_and_project_members_read_project_files(tmp_path: Path) -> None:
    state, _ = _project_state(tmp_path)
    state.document_upload_store = InMemoryDocumentUploadStore(
        upload_root=tmp_path / "project-files"
    )
    client = TestClient(create_app(state))
    assert client.post("/projects", headers=ADMIN_HEADERS, json=PROJECT_PAYLOAD).status_code == 201

    upload_response = client.post(
        "/projects/FUND-CHECK-202607/files",
        headers=ADMIN_HEADERS,
        files={"file": ("audit-note.md", b"# audit evidence", "text/markdown")},
    )

    assert upload_response.status_code == 201, upload_response.text
    uploaded = upload_response.json()["item"]
    assert uploaded["name"] == "audit-note.md"
    assert uploaded["preview_url"].endswith(f"/{uploaded['id']}/preview")
    assert uploaded["download_url"].endswith(f"/{uploaded['id']}/download")

    member_headers = {"X-User-Id": "project-admin", "X-Role": "member"}
    list_response = client.get(
        "/projects/FUND-CHECK-202607/files",
        headers=member_headers,
    )
    assert list_response.status_code == 200
    assert list_response.json()["items"] == [uploaded]
    assert list_response.json()["permissions"] == {"can_upload": False}

    preview_response = client.get(uploaded["preview_url"], headers=member_headers)
    download_response = client.get(uploaded["download_url"], headers=member_headers)
    assert preview_response.status_code == 200
    assert preview_response.content == b"# audit evidence"
    assert preview_response.headers["content-disposition"].startswith("inline;")
    assert download_response.status_code == 200
    assert download_response.headers["content-disposition"].startswith("attachment;")

    denied_upload = client.post(
        "/projects/FUND-CHECK-202607/files",
        headers=member_headers,
        files={"file": ("denied.md", b"no", "text/markdown")},
    )
    assert denied_upload.status_code == 403


def test_project_file_listing_filters_scope_before_limit(tmp_path: Path) -> None:
    state, _ = _project_state(tmp_path)
    store = InMemoryDocumentUploadStore(upload_root=tmp_path / "project-files")
    state.document_upload_store = store
    client = TestClient(create_app(state))
    assert client.post("/projects", headers=ADMIN_HEADERS, json=PROJECT_PAYLOAD).status_code == 201
    expected = store.add_upload(
        file_name="target.md",
        extension="md",
        content=b"target project evidence",
        created_by="project-admin",
        metadata={"scope": "project", "project_key": "FUND-CHECK-202607"},
    )
    for index in range(100):
        store.add_upload(
            file_name=f"other-{index}.md",
            extension="md",
            content=b"other project evidence",
            created_by="project-admin",
            metadata={"scope": "project", "project_key": f"OTHER-{index}"},
        )

    response = client.get(
        "/projects/FUND-CHECK-202607/files",
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [expected["id"]]


def test_sql_upload_listing_filters_scope_before_limit(tmp_path: Path) -> None:
    store = SqlAlchemyDocumentUploadStore(
        database_url=f"sqlite:///{tmp_path / 'project-files.db'}",
        upload_root=tmp_path / "project-files",
        create_schema=True,
    )
    expected = store.add_upload(
        file_name="target.md",
        extension="md",
        content=b"target project evidence",
        created_by="project-admin",
        metadata={"scope": "project", "project_key": "FUND-CHECK-202607"},
    )
    for index in range(100):
        store.add_upload(
            file_name=f"other-{index}.md",
            extension="md",
            content=b"other project evidence",
            created_by="project-admin",
            metadata={"scope": "project", "project_key": f"OTHER-{index}"},
        )

    items = store.list_uploads(
        created_by=None,
        include_all=True,
        scope="project",
        project_key="FUND-CHECK-202607",
        limit=1,
    )

    assert [item["id"] for item in items] == [expected["id"]]


def test_project_scoped_admin_can_upload_project_file(tmp_path: Path) -> None:
    state, _ = _project_state(tmp_path)
    state.document_upload_store = InMemoryDocumentUploadStore(
        upload_root=tmp_path / "project-files"
    )
    state.auth_user_store = SqlAlchemyAuthUserStore(
        f"sqlite:///{tmp_path / 'auth-users.db'}",
        create_schema=True,
    )
    client = TestClient(create_app(state))
    assert client.post("/projects", headers=ADMIN_HEADERS, json=PROJECT_PAYLOAD).status_code == 201
    assert client.post(
        "/auth/users",
        headers=ADMIN_HEADERS,
        json={
            "user_key": "scoped-project-admin",
            "display_name": "项目级管理员",
            "department_key": "audit-office",
        },
    ).status_code == 200
    assert client.post(
        "/auth/users/scoped-project-admin/role-assignments",
        headers=ADMIN_HEADERS,
        json={
            "role": "admin",
            "scope_type": "project",
            "scope_key": "FUND-CHECK-202607",
        },
    ).status_code == 200

    response = client.post(
        "/projects/FUND-CHECK-202607/files",
        headers={"X-User-Id": "scoped-project-admin", "X-Role": "member"},
        files={"file": ("scoped.md", b"project-scoped evidence", "text/markdown")},
    )

    assert response.status_code == 201, response.text
    assert response.json()["item"]["name"] == "scoped.md"
    assert state.operation_logs[-1]["payload"]["user_identifier"] == "scoped-project-admin"
    assert state.operation_logs[-1]["payload"]["role"] == "admin"


def test_create_project_rolls_back_when_creator_member_insert_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state, database_url = _project_state(tmp_path)
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    with Session(engine) as session:
        session.add(
            AuditProjectMember(
                member_key="member-forced-conflict",
                project_key="SELF-CHECK-FUND-20260607",
                name="既有成员",
                role="审计员",
                department="内审部",
                status="在项目中",
                created_by="fixture",
                extra_metadata={"user_identifier": "existing-member"},
            )
        )
        session.commit()
    monkeypatch.setattr(
        "medical_audit_kb.api.project_member_store._new_member_key",
        lambda: "member-forced-conflict",
    )
    client = TestClient(create_app(state))

    response = client.post("/projects", headers=ADMIN_HEADERS, json=PROJECT_PAYLOAD)

    assert response.status_code == 503
    with Session(engine) as session:
        assert session.scalar(
            select(AuditProject).where(AuditProject.project_key == "FUND-CHECK-202607")
        ) is None
        assert session.scalar(
            select(AuditProjectMember).where(
                AuditProjectMember.project_key == "FUND-CHECK-202607"
            )
        ) is None
    assert not any(event["action"] == "project-create" for event in state.operation_logs)


def test_create_project_store_failure_is_503_and_internal_projects_stay_hidden(
    tmp_path: Path,
) -> None:
    state, database_url = _project_state(tmp_path)
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    with Session(engine) as session:
        session.add(
            AuditProject(
                project_key="INTERNAL-FIXTURE",
                name="内部工作流项目",
                scenario_key="charging-compliance",
                status="fixture",
                owner_department="内审部",
                created_by="unit-test",
                description=None,
                extra_metadata={},
            )
        )
        session.commit()

    admin_items = TestClient(create_app(state)).get(
        "/projects", headers=ADMIN_HEADERS
    ).json()["items"]
    assert "INTERNAL-FIXTURE" not in {item["id"] for item in admin_items}

    class FailingCreateStore:
        supports_persistent_writes = True

        def create_project(self, values: dict[str, object]) -> object:
            raise SQLAlchemyError("project store unavailable")

    state.project_member_store = FailingCreateStore()  # type: ignore[assignment]
    response = TestClient(create_app(state)).post(
        "/projects", headers=ADMIN_HEADERS, json=PROJECT_PAYLOAD
    )
    assert response.status_code == 503
    assert state.operation_logs[-1]["action"] == "project-create-unavailable"


def test_create_project_requires_persistent_project_and_audit_stores(tmp_path: Path) -> None:
    missing_project_state, database_url = _project_state(tmp_path / "missing-project")
    missing_project_state.project_member_store = None
    missing_project_response = TestClient(create_app(missing_project_state)).post(
        "/projects", headers=ADMIN_HEADERS, json=PROJECT_PAYLOAD
    )

    assert missing_project_response.status_code == 503
    assert missing_project_response.json()["detail"] == (
        "persistent project store is not available"
    )
    with Session(create_engine(database_url, connect_args={"check_same_thread": False})) as session:
        assert session.scalar(
            select(AuditProject).where(AuditProject.project_key == "FUND-CHECK-202607")
        ) is None


def test_project_read_fallback_does_not_enable_volatile_mutations(tmp_path: Path) -> None:
    state, _ = _project_state(tmp_path)
    state.project_member_store = None
    client = TestClient(create_app(state))

    read_response = client.get("/projects", headers=ADMIN_HEADERS)
    project_response = client.post(
        "/projects",
        headers=ADMIN_HEADERS,
        json=PROJECT_PAYLOAD,
    )
    member_response = client.post(
        "/projects/SELF-CHECK-FUND-20260607/members",
        headers=ADMIN_HEADERS,
        json={
            "user_identifier": "volatile-member",
            "name": "易失成员",
            "role": "审计员",
            "department": "内审部",
            "status": "在项目中",
        },
    )

    assert read_response.status_code == 200
    assert read_response.json()["store"] == {
        "ready": False,
        "backend": "unavailable",
        "persistent_writes_ready": False,
        "history_review_task_writes_ready": False,
    }
    assert state.project_member_store is None
    assert project_response.status_code == 503
    assert member_response.status_code == 503


def test_project_creation_rejects_explicit_in_memory_store(tmp_path: Path) -> None:
    state, _ = _project_state(tmp_path)
    state.project_member_store = InMemoryProjectMemberStore()

    response = TestClient(create_app(state)).post(
        "/projects",
        headers=ADMIN_HEADERS,
        json=PROJECT_PAYLOAD,
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "persistent project store is not available"
    assert state.project_member_store.projects == {}


def test_project_member_store_failure_is_service_unavailable(tmp_path: Path) -> None:
    state, _ = _project_state(tmp_path)

    class FailingPersistentMemberStore:
        supports_persistent_writes = True

        def add_member(
            self,
            project_key: str,
            values: dict[str, object],
        ) -> dict[str, object]:
            raise SQLAlchemyError(f"{project_key}:{values['user_identifier']}")

    state.project_member_store = FailingPersistentMemberStore()  # type: ignore[assignment]
    response = TestClient(create_app(state)).post(
        "/projects/SELF-CHECK-FUND-20260607/members",
        headers=ADMIN_HEADERS,
        json={
            "user_identifier": "member-store-failure",
            "name": "存储故障成员",
            "role": "审计员",
            "department": "内审部",
            "status": "在项目中",
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "persistent project member store is not available"
    )

    missing_audit_state, missing_audit_database_url = _project_state(
        tmp_path / "missing-audit"
    )
    missing_audit_state.audit_log_store = None
    missing_audit_response = TestClient(create_app(missing_audit_state)).post(
        "/projects", headers=ADMIN_HEADERS, json=PROJECT_PAYLOAD
    )

    assert missing_audit_response.status_code == 503
    assert missing_audit_response.json()["detail"] == (
        "project creation audit is not available"
    )
    with Session(
        create_engine(
            missing_audit_database_url,
            connect_args={"check_same_thread": False},
        )
    ) as session:
        assert session.scalar(
            select(AuditProject).where(AuditProject.project_key == "FUND-CHECK-202607")
        ) is None


def test_project_reads_fall_back_without_rereading_a_failed_dynamic_store(
    tmp_path: Path,
) -> None:
    state, _ = _project_state(tmp_path)

    class FailingReadStore:
        def list_projects(self) -> list[dict[str, object]]:
            raise SQLAlchemyError("project reads unavailable")

        def list_members(self, project_key: str) -> list[dict[str, object]]:
            raise SQLAlchemyError(project_key)

        def member_counts(self) -> dict[str, int]:
            raise SQLAlchemyError("member counts unavailable")

    state.project_member_store = FailingReadStore()  # type: ignore[assignment]
    client = TestClient(create_app(state))
    creator_headers = {"X-User-Id": "expert-catalog", "X-Role": "member"}

    projects = client.get("/projects", headers=creator_headers)
    detail = client.get("/projects/CATALOG-LIMIT-202606", headers=creator_headers)
    dashboard = client.get(
        "/projects/CATALOG-LIMIT-202606/dashboard",
        headers=creator_headers,
    )

    assert projects.status_code == 200
    assert [item["id"] for item in projects.json()["items"]] == ["CATALOG-LIMIT-202606"]
    assert projects.json()["store"] == {
        "ready": False,
        "backend": "unavailable",
        "persistent_writes_ready": False,
        "history_review_task_writes_ready": False,
    }
    assert detail.status_code == 200
    assert detail.json()["store"] == {"ready": False, "backend": "unavailable"}
    assert dashboard.status_code == 200
    assert dashboard.json()["store"]["project_members_ready"] is False


def test_project_list_keeps_failed_dynamic_member_count_unknown(tmp_path: Path) -> None:
    state, _ = _project_state(tmp_path)
    assert state.project_member_store is not None
    state.project_member_store.create_project(
        {
            **PROJECT_PAYLOAD,
            "status": "待开始",
            "created_by": "project-admin",
            "creator_display_name": "project-admin",
            "metadata": {
                "audit_topic": "医保基金使用合规",
                "organization_name": "测试医院",
                "project_surface": "collaboration-v1",
            },
        }
    )
    durable_store = state.project_member_store

    class FailingCountStore:
        def list_projects(self) -> list[dict[str, object]]:
            return durable_store.list_projects()

        def list_members(self, project_key: str) -> list[dict[str, object]]:
            return durable_store.list_members(project_key)

        def member_counts(self) -> dict[str, int]:
            raise SQLAlchemyError("member counts unavailable")

    state.project_member_store = FailingCountStore()  # type: ignore[assignment]

    response = TestClient(create_app(state)).get("/projects", headers=ADMIN_HEADERS)

    assert response.status_code == 200
    assert response.json()["store"] == {
        "ready": False,
        "backend": "unavailable",
        "persistent_writes_ready": False,
        "history_review_task_writes_ready": False,
    }
    dynamic = next(
        item for item in response.json()["items"] if item["id"] == "FUND-CHECK-202607"
    )
    assert dynamic["member_count"] is None
    default = next(
        item for item in response.json()["items"] if item["id"] == "CATALOG-LIMIT-202606"
    )
    assert default["member_count"] is None


def test_project_creation_audit_intent_is_fail_closed_and_completion_can_degrade(
    tmp_path: Path,
) -> None:
    intent_state, intent_database_url = _project_state(tmp_path / "intent")

    class IntentFailingAuditStore:
        def add_event(self, action: str, payload: dict[str, object]) -> dict[str, object]:
            raise SQLAlchemyError(f"{action}:{payload['project_key']}")

    intent_state.audit_log_store = IntentFailingAuditStore()  # type: ignore[assignment]
    intent_response = TestClient(create_app(intent_state)).post(
        "/projects",
        headers=ADMIN_HEADERS,
        json=PROJECT_PAYLOAD,
    )

    assert intent_response.status_code == 503
    intent_engine = create_engine(
        intent_database_url,
        connect_args={"check_same_thread": False},
    )
    with Session(intent_engine) as session:
        assert session.scalar(select(AuditProject)) is None

    completion_state, completion_database_url = _project_state(tmp_path / "completion")

    class CompletionFailingAuditStore:
        def add_event(self, action: str, payload: dict[str, object]) -> dict[str, object]:
            if action == "project-create":
                raise SQLAlchemyError("completion audit unavailable")
            return {"action": action, "payload": payload}

    completion_state.audit_log_store = CompletionFailingAuditStore()  # type: ignore[assignment]
    completion_response = TestClient(create_app(completion_state)).post(
        "/projects",
        headers=ADMIN_HEADERS,
        json=PROJECT_PAYLOAD,
    )

    assert completion_response.status_code == 201
    assert completion_response.json()["audit"] == {"status": "degraded"}
    completion_engine = create_engine(
        completion_database_url,
        connect_args={"check_same_thread": False},
    )
    with Session(completion_engine) as session:
        assert session.scalar(
            select(AuditProject).where(AuditProject.project_key == "FUND-CHECK-202607")
        ) is not None
    assert completion_state.operation_logs[-1]["action"] == "project-create-audit-degraded"


def test_concurrent_project_key_integrity_conflict_maps_to_project_conflict(
    tmp_path: Path,
) -> None:
    store = SqlAlchemyProjectMemberStore(
        f"sqlite:///{tmp_path / 'integrity-translation.db'}",
        create_schema=True,
    )

    class Context:
        def __init__(self, session: object) -> None:
            self.session = session

        def __enter__(self) -> object:
            return self.session

        def __exit__(self, *_args: object) -> None:
            return None

    class WriteSession:
        def scalar(self, _statement: object) -> None:
            return None

        def add(self, _value: object) -> None:
            return None

        def flush(self) -> None:
            raise IntegrityError("insert audit_projects", {}, RuntimeError("duplicate"))

    class ReadSession:
        def scalar(self, _statement: object) -> object:
            return object()

    class ConcurrentSessionFactory:
        def begin(self) -> Context:
            return Context(WriteSession())

        def __call__(self) -> Context:
            return Context(ReadSession())

    store._session_factory = ConcurrentSessionFactory()  # type: ignore[assignment]
    values: dict[str, Any] = {
        **PROJECT_PAYLOAD,
        "status": "待开始",
        "created_by": "project-admin",
        "metadata": {
            "audit_topic": "医保基金使用合规",
            "organization_name": "测试医院",
        },
    }

    with pytest.raises(ProjectIdentityConflictError):
        store.create_project(values)


def _project_state(
    tmp_path: Path,
    *,
    create_schema: bool = True,
) -> tuple[ApiState, str]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    database_url = f"sqlite:///{tmp_path / 'project-creation.db'}"
    settings = KnowledgeQuerySettings(
        data_root=tmp_path / "data",
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
    state.project_member_store = SqlAlchemyProjectMemberStore(
        database_url,
        create_schema=create_schema,
    )
    state.audit_log_store = SqlAlchemyAuditLogStore(database_url)
    return state, database_url
