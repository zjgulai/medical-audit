from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from medical_audit_kb.api.app import ApiState, create_app
from medical_audit_kb.api.project_member_store import SqlAlchemyProjectMemberStore
from medical_audit_kb.api.query_history_store import (
    InMemoryQueryHistoryStore,
    SqlAlchemyQueryHistoryStore,
)
from medical_audit_kb.api.review_task_store import (
    InMemoryReviewTaskStore,
    JsonFileReviewTaskStore,
    SqlAlchemyReviewTaskStore,
)
from medical_audit_kb.core.config import (
    REQUIRED_COLLECTIONS,
    KnowledgeQuerySettings,
    ModelProviderSettings,
)

PROJECT_KEY = "SELF-CHECK-FUND-20260607"
MEMBER_HEADERS = {
    "X-User-Id": "next-member",
    "X-Role": "member",
    "X-Project-Key": PROJECT_KEY,
}


def test_query_history_list_is_owner_scoped_on_both_routes(tmp_path: Path) -> None:
    state = _state(tmp_path)
    history_store = _history_store(state)
    own = _add_history(history_store, user_identifier="next-member", question="本人查询")
    _add_history(history_store, user_identifier="another-member", question="他人查询")
    client = TestClient(create_app(state))

    for path in ("/query/logs?limit=20", "/api/v1/query/logs?limit=20"):
        response = client.get(path, headers=MEMBER_HEADERS)

        assert response.status_code == 200
        assert [item["id"] for item in response.json()["items"]] == [own["id"]]
        assert response.json()["store"]["ready"] is True

        anonymous = client.get(path)
        assert anonymous.status_code == 401
        assert anonymous.json()["detail"] == "X-User-Id header is required"


def test_owned_history_creates_project_scoped_review_task_with_safe_audit(
    tmp_path: Path,
) -> None:
    state = _state(tmp_path)
    sensitive_question = "SENTINEL-QUESTION-DO-NOT-AUDIT"
    sensitive_note = "SENTINEL-NOTE-DO-NOT-AUDIT"
    history = _add_history(
        _history_store(state),
        user_identifier="next-member",
        question=sensitive_question,
        answer_summary="A" * 700,
    )
    client = TestClient(create_app(state))

    response = client.post(
        f"/api/v1/query/logs/{history['id']}/review-task",
        headers=MEMBER_HEADERS,
        json={"project_key": PROJECT_KEY, "note": sensitive_note},
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "format": "query-history-review-task-v1",
        "query_log_id": history["id"],
        "task_id": body["task_id"],
        "project_key": PROJECT_KEY,
        "status": "pending-review",
        "created": True,
        "review_queue_href": "/reports",
        "provider_call": False,
        "audit": {
            "status": "ready",
            "intent_recorded": True,
            "completion_recorded": True,
        },
    }
    assert body["task_id"].startswith("history-task-")
    assert len(body["task_id"]) <= 64

    tasks = _review_store(state).list_tasks()
    assert len(tasks) == 1
    task = tasks[0]
    assert task["source"] == "query-history-manual"
    assert task["status"] == "pending-review"
    assert task["created_by"] == "next-member"
    assert task["assigned_to"] == "next-member"
    assert task["reviewer_note"] == sensitive_note
    assert task["citation_count"] == 2
    dossier = task["dossier"]
    assert dossier["project_key"] == PROJECT_KEY
    assert dossier["query_history_snapshot"]["query_log_id"] == history["id"]
    assert dossier["query_history_snapshot"]["question"] == sensitive_question
    assert dossier["query_history_snapshot"]["answer_summary"] == "A" * 500
    assert dossier["query_history_snapshot"]["retrieved_chunk_ids"] == [
        "chunk-001",
        "chunk-002",
    ]

    audit_actions = [event["action"] for event in _audit_store(state).events]
    assert audit_actions[-2:] == [
        "query-history-review-task-create-intent",
        "query-history-review-task-create-completed",
    ]
    serialized_audit = json.dumps(_audit_store(state).events, ensure_ascii=False)
    assert sensitive_question not in serialized_audit
    assert sensitive_note not in serialized_audit


def test_history_review_task_exports_json_markdown_and_docx(tmp_path: Path) -> None:
    state = _state(tmp_path)
    history = _add_history(
        _history_store(state),
        user_identifier="next-member",
        question="医保基金审核依据",
        answer_summary="应核对法规依据并由人工复核。",
    )
    client = TestClient(create_app(state), raise_server_exceptions=False)
    created = client.post(
        f"/api/v1/query/logs/{history['id']}/review-task",
        headers=MEMBER_HEADERS,
        json={"project_key": PROJECT_KEY, "note": "导出前复核"},
    )
    task_id = created.json()["task_id"]

    json_response = client.get(f"/review-tasks/{task_id}/export", headers=MEMBER_HEADERS)
    markdown_response = client.get(
        f"/review-tasks/{task_id}/export",
        headers=MEMBER_HEADERS,
        params={"format": "markdown"},
    )
    docx_response = client.get(
        f"/review-tasks/{task_id}/export",
        headers=MEMBER_HEADERS,
        params={"format": "docx"},
    )

    assert created.status_code == 200
    assert json_response.status_code == 200
    assert json_response.json()["dossier"]["format"] == (
        "query-history-review-task-dossier-v1"
    )
    assert markdown_response.status_code == 200
    assert "AuditScope 历史对话人工复核底稿" in markdown_response.text
    assert "医保基金审核依据" in markdown_response.text
    assert "应核对法规依据并由人工复核。" in markdown_response.text
    assert docx_response.status_code == 200
    with ZipFile(BytesIO(docx_response.content)) as archive:
        document_xml = archive.read("word/document.xml").decode("utf-8")
    assert "AuditScope 历史对话人工复核底稿" in document_xml


def test_history_review_task_id_uses_canonical_sql_query_id(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'history-idempotency.db'}"
    state = _state(tmp_path)
    state.query_history_store = SqlAlchemyQueryHistoryStore(database_url, create_schema=True)
    state.review_task_store = SqlAlchemyReviewTaskStore(database_url)
    history = state.query_history_store.add_query(
        {
            "user_identifier": "next-member",
            "question": "规范化 UUID 幂等性",
            "filters": {"generation_status": "not_requested"},
            "answer_summary": "待人工复核。",
            "retrieved_chunk_ids": [],
        }
    )
    canonical_id = str(history["id"])
    variants = (canonical_id, canonical_id.upper(), canonical_id.replace("-", ""))
    client = TestClient(create_app(state))

    responses = [
        client.post(
            f"/api/v1/query/logs/{query_id}/review-task",
            headers=MEMBER_HEADERS,
            json={"project_key": PROJECT_KEY},
        )
        for query_id in variants
    ]

    assert [response.status_code for response in responses] == [200, 200, 200]
    assert [response.json()["query_log_id"] for response in responses] == [
        canonical_id,
        canonical_id,
        canonical_id,
    ]
    assert len({response.json()["task_id"] for response in responses}) == 1
    assert [response.json()["created"] for response in responses] == [True, False, False]
    assert len(state.review_task_store.list_tasks()) == 1


def test_history_to_task_is_deterministic_and_rejects_project_conflict(
    tmp_path: Path,
) -> None:
    state = _state(tmp_path)
    history = _add_history(
        _history_store(state),
        user_identifier="next-member",
        question="需要人工复核的查询",
    )
    client = TestClient(create_app(state))
    path = f"/api/v1/query/logs/{history['id']}/review-task"

    first = client.post(
        path,
        headers=MEMBER_HEADERS,
        json={"project_key": PROJECT_KEY},
    )
    task_id = first.json()["task_id"]
    _review_store(state).update_task(
        task_id,
        {"status": "needs-evidence", "status_label": "需补证"},
    )
    repeated = client.post(
        path,
        headers=MEMBER_HEADERS,
        json={"project_key": PROJECT_KEY},
    )
    conflict = client.post(
        path,
        headers={**MEMBER_HEADERS, "X-Role": "admin", "X-User-Id": "next-member"},
        json={"project_key": "CATALOG-LIMIT-202606"},
    )

    assert first.status_code == 200
    assert repeated.status_code == 200
    assert first.json()["task_id"] == task_id == repeated.json()["task_id"]
    assert first.json()["created"] is True
    assert repeated.json()["created"] is False
    assert repeated.json()["status"] == "needs-evidence"
    assert len(_review_store(state).list_tasks()) == 1
    assert conflict.status_code == 409
    assert conflict.json()["detail"] == "query history review task project scope conflicts"
    assert len(_review_store(state).list_tasks()) == 1


def test_history_to_task_hides_foreign_history_and_project_visibility(
    tmp_path: Path,
) -> None:
    state = _state(tmp_path)
    foreign = _add_history(
        _history_store(state),
        user_identifier="another-member",
        question="他人的历史",
    )
    own = _add_history(
        _history_store(state),
        user_identifier="next-member",
        question="本人的历史",
    )
    client = TestClient(create_app(state))

    foreign_response = client.post(
        f"/api/v1/query/logs/{foreign['id']}/review-task",
        headers=MEMBER_HEADERS,
        json={"project_key": PROJECT_KEY},
    )
    invisible_project = client.post(
        f"/api/v1/query/logs/{own['id']}/review-task",
        headers=MEMBER_HEADERS,
        json={"project_key": "CATALOG-LIMIT-202606"},
    )

    assert foreign_response.status_code == 404
    assert foreign_response.json()["detail"] == "query history not found"
    assert invisible_project.status_code == 404
    assert invisible_project.json()["detail"] == "project not found"
    assert _review_store(state).list_tasks() == []


def test_history_to_task_accepts_visible_dynamic_project(tmp_path: Path) -> None:
    state = _state(tmp_path)
    store = state.project_member_store
    assert isinstance(store, SqlAlchemyProjectMemberStore)
    dynamic_project_key = "DYNAMIC-AUDIT-20260715"
    store.create_project(
        {
            "project_key": dynamic_project_key,
            "name": "动态审计项目",
            "scenario_key": "medical-insurance",
            "status": "进行中",
            "owner_department": "内审部",
            "created_by": "next-member",
            "creator_display_name": "审计员",
            "metadata": {
                "audit_topic": "医保基金使用合规",
                "organization_name": "内审部",
            },
        }
    )
    history = _add_history(
        _history_store(state),
        user_identifier="next-member",
        question="动态项目历史",
    )
    client = TestClient(create_app(state))

    response = client.post(
        f"/api/v1/query/logs/{history['id']}/review-task",
        headers={**MEMBER_HEADERS, "X-Project-Key": dynamic_project_key},
        json={"project_key": dynamic_project_key},
    )

    assert response.status_code == 200
    assert response.json()["project_key"] == dynamic_project_key
    assert _review_store(state).list_tasks()[0]["dossier"]["project_key"] == dynamic_project_key


def test_history_to_task_rejects_visible_user_without_create_permission(
    tmp_path: Path,
) -> None:
    state = _state(tmp_path)
    store = state.project_member_store
    assert isinstance(store, SqlAlchemyProjectMemberStore)
    store.add_member(
        PROJECT_KEY,
        {
            "user_identifier": "visible-technician",
            "name": "技术人员",
            "role": "信息科",
            "department": "信息科",
            "status": "在项目中",
            "created_by": "next-director",
        },
    )
    history = _add_history(
        _history_store(state),
        user_identifier="visible-technician",
        question="技术人员历史",
    )
    client = TestClient(create_app(state))

    response = client.post(
        f"/api/v1/query/logs/{history['id']}/review-task",
        headers={
            "X-User-Id": "visible-technician",
            "X-Role": "technician",
            "X-Project-Key": PROJECT_KEY,
        },
        json={"project_key": PROJECT_KEY},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "create_review_task is not allowed"
    assert _review_store(state).list_tasks() == []


def test_history_to_task_fails_closed_when_membership_store_is_unavailable(
    tmp_path: Path,
) -> None:
    state = _state(tmp_path)
    state.project_member_store = _UnavailableProjectMemberStore()
    history = _add_history(
        _history_store(state),
        user_identifier="next-member",
        question="成员存储不可用",
    )
    client = TestClient(create_app(state))

    response = client.post(
        f"/api/v1/query/logs/{history['id']}/review-task",
        headers=MEMBER_HEADERS,
        json={"project_key": PROJECT_KEY},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "project membership store is unavailable"
    assert _review_store(state).list_tasks() == []


def test_project_read_fallback_does_not_enable_history_task_creation(
    tmp_path: Path,
) -> None:
    state = _state(tmp_path)
    state.project_member_store = None
    history = _add_history(
        _history_store(state),
        user_identifier="next-member",
        question="只读回退后仍应拒绝业务写入",
    )
    client = TestClient(create_app(state))

    read_response = client.get(
        "/projects",
        headers={"X-User-Id": "next-member", "X-Role": "member"},
    )
    task_response = client.post(
        f"/api/v1/query/logs/{history['id']}/review-task",
        headers=MEMBER_HEADERS,
        json={"project_key": PROJECT_KEY},
    )

    assert read_response.status_code == 200
    assert read_response.json()["store"] == {
        "ready": False,
        "backend": "unavailable",
        "persistent_writes_ready": False,
        "history_review_task_writes_ready": False,
    }
    assert state.project_member_store is None
    assert task_response.status_code == 503
    assert task_response.json()["detail"] == "project membership store is unavailable"
    assert _review_store(state).list_tasks() == []


def test_history_to_task_rejects_in_memory_review_task_store(tmp_path: Path) -> None:
    state = _state(tmp_path)
    state.review_task_store = InMemoryReviewTaskStore()
    history = _add_history(
        _history_store(state),
        user_identifier="next-member",
        question="任务必须持久化",
    )

    client = TestClient(create_app(state))
    projects_response = client.get("/projects", headers=MEMBER_HEADERS)
    response = client.post(
        f"/api/v1/query/logs/{history['id']}/review-task",
        headers=MEMBER_HEADERS,
        json={"project_key": PROJECT_KEY},
    )

    assert projects_response.status_code == 200
    assert projects_response.json()["store"]["persistent_writes_ready"] is True
    assert projects_response.json()["store"]["history_review_task_writes_ready"] is False
    assert response.status_code == 503
    assert response.json()["detail"] == "review task store is unavailable"
    assert state.review_task_store.tasks == []


def test_history_to_task_records_terminal_failure_after_audit_intent(
    tmp_path: Path,
) -> None:
    state = _state(tmp_path)
    history = _add_history(
        _history_store(state),
        user_identifier="next-member",
        question="任务存储故障",
    )

    class FailingReviewTaskStore:
        supports_persistent_writes = True

        def get_task(self, task_id: str) -> dict[str, object]:
            raise SQLAlchemyError(task_id)

    state.review_task_store = FailingReviewTaskStore()  # type: ignore[assignment]
    response = TestClient(create_app(state)).post(
        f"/api/v1/query/logs/{history['id']}/review-task",
        headers=MEMBER_HEADERS,
        json={"project_key": PROJECT_KEY},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "review task store is unavailable"
    assert [event["action"] for event in _audit_store(state).events[-2:]] == [
        "query-history-review-task-create-intent",
        "query-history-review-task-create-failed",
    ]
    failure_payload = _audit_store(state).events[-1]["payload"]
    assert failure_payload["status_code"] == 503
    assert failure_payload["reason"] == "review-task-store-unavailable"


def test_history_to_task_fails_closed_for_corrupt_json_review_task_store(
    tmp_path: Path,
) -> None:
    state = _state(tmp_path)
    history = _add_history(
        _history_store(state),
        user_identifier="next-member",
        question="损坏任务文件",
    )
    store_path = tmp_path / "corrupt-review-tasks.json"
    store_path.write_text("{not-json", encoding="utf-8")
    state.review_task_store = JsonFileReviewTaskStore(store_path)

    response = TestClient(create_app(state)).post(
        f"/api/v1/query/logs/{history['id']}/review-task",
        headers=MEMBER_HEADERS,
        json={"project_key": PROJECT_KEY},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "review task store is unavailable"
    assert [event["action"] for event in _audit_store(state).events[-2:]] == [
        "query-history-review-task-create-intent",
        "query-history-review-task-create-failed",
    ]


def test_history_to_task_fails_closed_for_non_utf8_json_review_task_store(
    tmp_path: Path,
) -> None:
    state = _state(tmp_path)
    history = _add_history(
        _history_store(state),
        user_identifier="next-member",
        question="非法编码任务文件",
    )
    store_path = tmp_path / "non-utf8-review-tasks.json"
    store_path.write_bytes(b"\xff")
    state.review_task_store = JsonFileReviewTaskStore(store_path)

    response = TestClient(create_app(state)).post(
        f"/api/v1/query/logs/{history['id']}/review-task",
        headers=MEMBER_HEADERS,
        json={"project_key": PROJECT_KEY},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "review task store is unavailable"
    assert [event["action"] for event in _audit_store(state).events[-2:]] == [
        "query-history-review-task-create-intent",
        "query-history-review-task-create-failed",
    ]


def test_history_to_task_rejects_non_object_json_review_task_entries(
    tmp_path: Path,
) -> None:
    state = _state(tmp_path)
    history = _add_history(
        _history_store(state),
        user_identifier="next-member",
        question="非法任务条目",
    )
    store_path = tmp_path / "invalid-entry-review-tasks.json"
    original_payload = json.dumps(
        {"format": "review-task-store-v1", "tasks": ["invalid-entry"]},
        ensure_ascii=False,
    )
    store_path.write_text(original_payload, encoding="utf-8")
    state.review_task_store = JsonFileReviewTaskStore(store_path)

    response = TestClient(create_app(state)).post(
        f"/api/v1/query/logs/{history['id']}/review-task",
        headers=MEMBER_HEADERS,
        json={"project_key": PROJECT_KEY},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "review task store is unavailable"
    assert store_path.read_text(encoding="utf-8") == original_payload
    assert [event["action"] for event in _audit_store(state).events[-2:]] == [
        "query-history-review-task-create-intent",
        "query-history-review-task-create-failed",
    ]


def test_history_to_task_fails_closed_for_unwritable_json_review_task_store(
    tmp_path: Path,
) -> None:
    state = _state(tmp_path)
    history = _add_history(
        _history_store(state),
        user_identifier="next-member",
        question="不可写任务文件",
    )
    blocked_parent = tmp_path / "blocked-review-task-parent"
    blocked_parent.write_text("not-a-directory", encoding="utf-8")
    state.review_task_store = JsonFileReviewTaskStore(
        blocked_parent / "review-tasks.json"
    )

    response = TestClient(create_app(state)).post(
        f"/api/v1/query/logs/{history['id']}/review-task",
        headers=MEMBER_HEADERS,
        json={"project_key": PROJECT_KEY},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "review task store is unavailable"
    assert [event["action"] for event in _audit_store(state).events[-2:]] == [
        "query-history-review-task-create-intent",
        "query-history-review-task-create-failed",
    ]


class _RecordingAuditLogStore:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    def add_event(self, action: str, payload: dict[str, object]) -> dict[str, object]:
        event = {
            "event_id": f"event-{len(self.events) + 1:03d}",
            "action": action,
            "payload": dict(payload),
        }
        self.events.append(event)
        return event

    def list_events(self, **_: object) -> list[dict[str, object]]:
        return list(self.events)


class _UnavailableProjectMemberStore:
    def list_members(self, project_key: str) -> list[dict[str, object]]:
        _ = project_key
        raise SQLAlchemyError("membership unavailable")

    def add_member(
        self,
        project_key: str,
        values: dict[str, object],
    ) -> dict[str, object]:
        _ = project_key, values
        raise SQLAlchemyError("membership unavailable")

    def member_counts(self) -> dict[str, int]:
        raise SQLAlchemyError("membership unavailable")


def _state(tmp_path: Path) -> ApiState:
    settings = KnowledgeQuerySettings(
        data_root=tmp_path / "data",
        index_root=tmp_path / "index",
        database_url="postgresql+psycopg://audit:audit@127.0.0.1:1/audit",
        model_provider=ModelProviderSettings(
            provider="fake",
            api_key_env="OPENAI_API_KEY",
            embedding_model="fake",
            chat_model="fake",
        ),
        source_collection_weights={key: 1.0 for key in REQUIRED_COLLECTIONS},
    )
    state = ApiState.from_settings(settings)
    state.auth_user_store = None
    state.query_history_store = InMemoryQueryHistoryStore()
    state.review_task_store = SqlAlchemyReviewTaskStore(
        f"sqlite:///{tmp_path / 'review-tasks.db'}",
        create_schema=True,
    )
    state.project_member_store = SqlAlchemyProjectMemberStore(
        f"sqlite:///{tmp_path / 'project-members.db'}",
        create_schema=True,
    )
    state.audit_log_store = _RecordingAuditLogStore()  # type: ignore[assignment]
    return state


def _add_history(
    store: InMemoryQueryHistoryStore,
    *,
    user_identifier: str,
    question: str,
    answer_summary: str = "应当核对引用依据并由人工复核。",
) -> dict[str, object]:
    return store.add_query(
        {
            "user_identifier": user_identifier,
            "question": question,
            "filters": {
                "source_collections": ["medical-insurance-laws"],
                "effective_source_collections": ["medical-insurance-laws"],
                "generation_status": "not_requested",
            },
            "answer_summary": answer_summary,
            "retrieved_chunk_ids": ["chunk-001", "chunk-002"],
        }
    )


def _history_store(state: ApiState) -> InMemoryQueryHistoryStore:
    assert isinstance(state.query_history_store, InMemoryQueryHistoryStore)
    return state.query_history_store


def _review_store(state: ApiState) -> SqlAlchemyReviewTaskStore:
    assert isinstance(state.review_task_store, SqlAlchemyReviewTaskStore)
    return state.review_task_store


def _audit_store(state: ApiState) -> _RecordingAuditLogStore:
    assert isinstance(state.audit_log_store, _RecordingAuditLogStore)
    return state.audit_log_store
