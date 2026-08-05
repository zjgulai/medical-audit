from __future__ import annotations

import hashlib
import json
import urllib.parse
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from medical_audit_kb.api.agent_store import (
    AgentStore,
    InMemoryAgentStore,
    combined_agent_payloads,
)
from medical_audit_kb.api.app import ApiState, PreviewReference, get_api_state, record_operation
from medical_audit_kb.api.audit_log_policy import (
    audit_log_policy_payload,
    redact_audit_log_events,
)
from medical_audit_kb.api.auth import (
    AuthenticatedUser,
    HospitalRole,
    Permission,
    record_authorization_denied,
    require_permission,
    resolve_authenticated_user,
    user_has_permission,
)
from medical_audit_kb.api.chat_models import (
    ChatModelAlias,
    ChatModelCatalogResponse,
    ChatModelUnavailableError,
    answer_generation_provider_for_alias,
    chat_model_catalog_response,
)
from medical_audit_kb.api.document_permissions import (
    allowed_source_collections,
    can_read_all_personal_uploads,
    enforce_source_collection_access,
)
from medical_audit_kb.api.project_member_store import (
    ProjectMemberStore,
    project_exists,
    supports_persistent_project_writes,
    visible_project_keys,
)
from medical_audit_kb.api.query_history_store import (
    QueryHistoryNotFoundError,
    QueryHistoryStore,
    try_add_query_history,
    try_list_query_history,
)
from medical_audit_kb.api.review_task_store import (
    ReviewTaskNotFoundError,
    ReviewTaskProjectScopeConflictError,
    ReviewTaskStore,
    ReviewTaskStoreUnavailableError,
    review_task_project_key,
    supports_persistent_review_task_writes,
)
from medical_audit_kb.domain.constants import SourceCollection
from medical_audit_kb.domain.source_collection_registry import (
    KNOWLEDGE_QUERY_CONTRACT_VERSION,
)
from medical_audit_kb.generation.answer_builder import (
    NoCitedEvidenceError,
    build_citation_backed_answer,
)
from medical_audit_kb.retrieval.filters import RetrievalFilters
from medical_audit_kb.retrieval.topics import get_topic

router = APIRouter()

REVIEW_STATUS_LABELS: dict[str, str] = {
    "pending-review": "待复核",
    "needs-evidence": "需补证",
    "confirmed-violation": "确认违规",
    "rule-issue": "规则问题",
    "data-issue": "数据问题",
    "not-violation": "排除违规",
    "closed": "已关闭",
}
RESOLVED_REVIEW_STATUSES = frozenset(
    {"confirmed-violation", "rule-issue", "data-issue", "not-violation", "closed"}
)
WORKPAPER_STATUS_LABELS: dict[str, str] = {
    "missing": "未建底稿",
    "draft": "底稿草稿",
    "ready": "底稿已就绪",
    "not-required": "无需底稿",
}
OWNER_SIGNOFF_STATUS_LABELS: dict[str, str] = {
    "not-requested": "未提交确认",
    "requested": "待负责人确认",
    "approved": "负责人已确认",
    "rejected": "退回复核",
}


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)
    source_collections: list[SourceCollection] = Field(default_factory=list)
    years: list[int] = Field(default_factory=list)
    regions: list[str] = Field(default_factory=list)
    document_types: list[str] = Field(default_factory=list)
    business_topics: list[str] = Field(default_factory=list)
    topic: str | None = Field(default=None, max_length=64)
    title_only: bool = False
    agent: str | None = Field(default=None, max_length=128)
    model: ChatModelAlias | None = None


class MedicalAuditReviewTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assigned_to: str | None = Field(default=None, max_length=128)
    note: str | None = Field(default=None, max_length=500)


class QueryHistoryReviewTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_key: str = Field(min_length=1, max_length=128)
    note: str | None = Field(default=None, max_length=500)


class MedicalAuditReviewStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = Field(default="confirmed-violation", max_length=48)
    assigned_to: str | None = Field(default=None, max_length=128)
    reviewer_note: str = Field(min_length=1, max_length=1200)
    conclusion: str = Field(min_length=1, max_length=1200)


class MedicalAuditImportPreflightRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_id: str = Field(min_length=1, max_length=96)
    template_name: str = Field(min_length=1, max_length=128)
    file_name: str | None = Field(default=None, max_length=256)
    row_count: int | None = Field(default=None, ge=0, le=2_000_000)
    note: str | None = Field(default=None, max_length=800)


class MedicalAuditSupplementRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=128)
    locator: str | None = Field(default=None, max_length=512)
    note: str | None = Field(default=None, max_length=1000)


class MedicalAuditReportEntryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_title: str | None = Field(default=None, max_length=180)
    summary: str | None = Field(default=None, max_length=1500)
    rectification_request: str | None = Field(default=None, max_length=1500)
    owner_confirmed_by: str | None = Field(default="系统管理员", max_length=128)


@router.get("/query/models", response_model=ChatModelCatalogResponse)
def query_models() -> ChatModelCatalogResponse:
    return chat_model_catalog_response()


@router.post("/query")
def query(
    payload: QueryRequest,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
    x_project_name: Annotated[str | None, Header(alias="X-Project-Name")] = None,
) -> dict[str, object]:
    user = resolve_authenticated_user(
        state,
        x_user_id=x_user_id,
        x_role=x_role,
        default_role=HospitalRole.MEMBER,
    )
    role = user.legacy_api_role
    requested_source_collections = tuple(payload.source_collections)
    enforce_source_collection_access(
        role=role,
        source_collections=requested_source_collections,
    )
    effective_source_collections = _effective_source_collections(
        role=role,
        requested_source_collections=requested_source_collections,
    )
    agent_key = _normalize_agent_key(payload.agent)
    selected_agent: dict[str, object] | None = None
    if agent_key is not None:
        selected_agent = _validate_agent_selection(
            state,
            agent_key,
            request_project_name=x_project_name,
            attempted_action="query-agent-select",
        )
    generation_provider = state.answer_generation_provider
    model_alias = payload.model.value if payload.model is not None else None
    model_status = "default_provider" if generation_provider is not None else "default_fallback"
    if payload.model is not None:
        try:
            generation_provider = answer_generation_provider_for_alias(payload.model)
        except ChatModelUnavailableError as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "chat_model_unavailable",
                    "model": exc.alias.value,
                    "reason": exc.reason,
                },
            ) from exc
        model_status = "selected_provider"
    if state.search_engine is None:
        raise HTTPException(status_code=409, detail="search engine is not initialized")

    topic = get_topic(payload.topic)
    if payload.topic and topic is None:
        raise HTTPException(status_code=400, detail=f"unknown topic: {payload.topic}")

    filters = RetrievalFilters(
        source_collections=effective_source_collections,
        domains=topic.domains if topic else (),
        domain_fallback_collections=topic.fallback_collections if topic else (),
        years=tuple(payload.years),
        regions=tuple(payload.regions),
        document_types=tuple(payload.document_types),
        business_topics=tuple(payload.business_topics),
        title_only=payload.title_only,
        title_query=payload.question if payload.title_only else "",
        personal_material_created_by=(
            user.user_identifier
            if SourceCollection.PERSONAL_MATERIALS in effective_source_collections
            else ""
        ),
        personal_material_include_all=(
            SourceCollection.PERSONAL_MATERIALS in effective_source_collections
            and can_read_all_personal_uploads(role)
        ),
    )
    results = state.search_engine.search(payload.question, filters=filters, top_k=payload.top_k)
    try:
        answer = build_citation_backed_answer(
            payload.question,
            results,
            generation_provider=generation_provider,
            agent_prompt=str(selected_agent.get("prompt") or "") if selected_agent else None,
            agent_prompt_version_key=(
                str(selected_agent.get("prompt_version_key") or "") if selected_agent else None
            ),
        )
    except NoCitedEvidenceError as exc:
        raise HTTPException(status_code=404, detail="no cited evidence found") from exc
    for citation in answer.citations:
        state.preview_references[citation.chunk_id] = PreviewReference(
            locator=citation.locator,
            citation_text=citation.snippet,
        )
    personal_upload_matches = _personal_upload_matches(
        state=state,
        user=user,
        role=role,
        query_text=payload.question,
        limit=5,
    )

    filter_payload = _query_filter_payload(
        payload,
        effective_source_collections=effective_source_collections,
        role=role,
    )
    history_filter_payload = {
        **filter_payload,
        "generation_status": answer.generation_status.value,
        "generation_failure_code": answer.generation_failure_code,
        "generation_failure_reason": answer.generation_failure_reason,
        "generation_http_status": answer.generation_http_status,
    }
    retrieved_chunk_ids = [str(citation.chunk_id) for citation in answer.citations]
    agent_invocation_id: str | None = None
    log_entry: dict[str, object] = {
        "user_identifier": user.user_identifier,
        "role": role,
        "effective_role": user.role.value,
        "auth_source": user.auth_source,
        "question": payload.question,
        "agent_id": agent_key,
        "model": model_alias,
        "model_status": model_status,
        "generation_status": answer.generation_status.value,
        "generation_failure_code": answer.generation_failure_code,
        "generation_failure_reason": answer.generation_failure_reason,
        "generation_http_status": answer.generation_http_status,
        "filters": filter_payload,
        "retrieved_chunk_ids": retrieved_chunk_ids,
        "citation_count": len(answer.citations),
        "personal_upload_match_count": len(personal_upload_matches),
    }
    state.query_logs.append(log_entry)
    persisted_log, query_history_error = try_add_query_history(
        state.query_history_store,
        {
            "user_identifier": user.user_identifier,
            "question": payload.question,
            "filters": history_filter_payload,
            "answer_summary": answer.answer[:500],
            "retrieved_chunk_ids": retrieved_chunk_ids,
        },
    )
    if agent_key is not None:
        invocation = _record_query_agent_invocation(
            state,
            agent_key=agent_key,
            question=payload.question,
            user_identifier=user.user_identifier,
            filters=filter_payload,
            query_log_id=str(persisted_log.get("id")) if persisted_log else None,
            query_log_index=len(state.query_logs) - 1,
            citation_count=len(answer.citations),
            request_project_name=x_project_name,
        )
        agent_invocation_id = str(invocation["id"])
    record_operation(
        state,
        "query",
        {
            "question": payload.question,
            "citation_count": len(answer.citations),
            "user_identifier": user.user_identifier,
            "role": role,
            "effective_role": user.role.value,
            "auth_source": user.auth_source,
            "agent_id": agent_key,
            "agent_invocation_id": agent_invocation_id,
            "model": model_alias,
            "model_status": model_status,
            "generation_status": answer.generation_status.value,
            "generation_failure_code": answer.generation_failure_code,
            "generation_failure_reason": answer.generation_failure_reason,
            "generation_http_status": answer.generation_http_status,
            "query_log_id": persisted_log.get("id") if persisted_log else None,
            "query_history_error": query_history_error,
            "filters": filter_payload,
            "personal_upload_match_count": len(personal_upload_matches),
        },
    )

    return {
        "contract_version": KNOWLEDGE_QUERY_CONTRACT_VERSION,
        "question": answer.question,
        "answer": answer.answer,
        "confidence": answer.confidence.value,
        "fallback_used": answer.fallback_used,
        "generation_status": answer.generation_status.value,
        "generation_failure_code": answer.generation_failure_code,
        "generation_failure_reason": answer.generation_failure_reason,
        "generation_http_status": answer.generation_http_status,
        "model_alias": model_alias,
        "model_status": model_status,
        "effective_source_collections": [item.value for item in effective_source_collections],
        "basis_groups": [
            {
                "evidence_type": group.evidence_type.value,
                "title": group.title,
                "items": [
                    {
                        "citation_id": item.citation_id,
                        "chunk_id": str(item.chunk_id),
                        "source_collection": item.source_collection.value,
                        "snippet": item.snippet,
                        "locator": item.locator,
                        "index_version_key": item.index_version_key,
                        "source_package_version_key": item.source_package_version_key,
                    }
                    for item in group.items
                ],
            }
            for group in answer.basis_groups
        ],
        "citations": [
            {
                "citation_id": citation.citation_id,
                "marker": citation.marker,
                "chunk_id": str(citation.chunk_id),
                "evidence_type": citation.evidence_type.value,
                "source_collection": citation.source_collection.value,
                "snippet": citation.snippet,
                "locator": citation.locator,
                "index_version_key": citation.index_version_key,
                "source_package_version_key": citation.source_package_version_key,
            }
            for citation in answer.citations
        ],
        "personal_upload_matches": personal_upload_matches,
        "query_log_index": len(state.query_logs) - 1,
        "query_log_id": persisted_log.get("id") if persisted_log else None,
        "agent_invocation_id": agent_invocation_id,
    }


@router.get("/query/logs")
def query_logs(
    state: Annotated[ApiState, Depends(get_api_state)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> dict[str, object]:
    owner_identifier = _query_history_owner_identifier(
        state=state,
        x_user_id=x_user_id,
        x_role=x_role,
    )
    if state.query_history_store is not None:
        history_items, query_history_error = try_list_query_history(
            state.query_history_store,
            limit=limit,
            user_identifier=owner_identifier,
        )
        if query_history_error is not None:
            record_operation(state, "query-history-list-failed", query_history_error)
            return {
                "items": _query_log_fallback_items(
                    state,
                    limit=limit,
                    user_identifier=owner_identifier,
                ),
                "store": {
                    "ready": False,
                    "backend": state.query_history_store.__class__.__name__,
                    "error": query_history_error,
                },
            }
        assert history_items is not None
        return {
            "items": [_query_history_item(item) for item in history_items],
            "store": {"ready": True, "backend": state.query_history_store.__class__.__name__},
        }
    return {
        "items": _query_log_fallback_items(
            state,
            limit=limit,
            user_identifier=owner_identifier,
        ),
        "store": {"ready": False, "backend": "memory"},
    }


@router.get("/review-tasks")
def list_review_tasks(
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, object]:
    require_permission(
        state,
        permission=Permission.CREATE_REVIEW_TASK,
        x_user_id=x_user_id,
        x_role=x_role,
        attempted_action="review-tasks-list",
    )
    store = _review_task_store_for_api(state)
    tasks = store.list_tasks()[:limit]
    record_operation(state, "review-tasks-list", {"count": len(tasks)})
    return {
        "format": "review-tasks-list-v1",
        "items": tasks,
        "count": len(tasks),
        "store": {"ready": True, "backend": store.__class__.__name__},
    }


@router.post("/query/logs/{query_log_id}/review-task")
def create_query_history_review_task(
    query_log_id: str,
    payload: QueryHistoryReviewTaskRequest,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> dict[str, object]:
    user = _query_history_review_task_user(
        state,
        project_key=payload.project_key,
        x_user_id=x_user_id,
        x_role=x_role,
    )
    history = _owned_query_history(
        state,
        query_log_id=query_log_id,
        user_identifier=user.user_identifier,
    )
    canonical_query_log_id = str(history["id"])
    _require_visible_query_history_project(
        state,
        project_key=payload.project_key,
        user=user,
    )
    if not user_has_permission(user, Permission.CREATE_REVIEW_TASK):
        record_authorization_denied(
            state,
            attempted_action="query-history-review-task-create",
            permission=Permission.CREATE_REVIEW_TASK,
            user_identifier=user.user_identifier,
            raw_role=user.raw_role,
            effective_role=user.role.value,
            auth_source=user.auth_source,
            profile_status=user.profile_status,
            auth_scope_type="project",
            auth_scope_key=payload.project_key,
            status_code=403,
            reason="create_review_task requires a higher hospital role",
        )
        raise HTTPException(status_code=403, detail="create_review_task is not allowed")

    task_id = _query_history_review_task_id(canonical_query_log_id)
    safe_audit_payload: dict[str, object] = {
        "query_log_id": canonical_query_log_id,
        "task_id": task_id,
        "project_key": payload.project_key,
        "user_identifier": user.user_identifier,
        "role": user.legacy_api_role,
        "endpoint": f"/api/v1/query/logs/{canonical_query_log_id}/review-task",
        "provider_call": False,
    }
    try:
        record_operation(
            state,
            "query-history-review-task-create-intent",
            safe_audit_payload,
        )
    except SQLAlchemyError as exc:
        state.operation_logs.append(
            {
                "action": "query-history-review-task-create-unavailable",
                "payload": {
                    **safe_audit_payload,
                    "status_code": 503,
                    "reason": "audit-intent-unavailable",
                    "error_type": type(exc).__name__,
                },
            }
        )
        raise HTTPException(
            status_code=503,
            detail="query history review task audit is unavailable",
        ) from exc

    try:
        task, created = _ensure_query_history_review_task(
            state,
            history=history,
            task_id=task_id,
            project_key=payload.project_key,
            user=user,
            note=payload.note,
        )
    except HTTPException as exc:
        conflict = exc.status_code == 409
        _record_query_history_operation_best_effort(
            state,
            (
                "query-history-review-task-create-conflict"
                if conflict
                else "query-history-review-task-create-failed"
            ),
            {
                **safe_audit_payload,
                "status_code": exc.status_code,
                "reason": (
                    "review-task-conflict"
                    if conflict
                    else "review-task-store-unavailable"
                ),
            },
        )
        raise
    completion_payload = {**safe_audit_payload, "created": created, "status_code": 200}
    completion_recorded = True
    try:
        record_operation(
            state,
            "query-history-review-task-create-completed",
            completion_payload,
        )
    except SQLAlchemyError as exc:
        completion_recorded = False
        state.operation_logs.append(
            {
                "action": "query-history-review-task-create-audit-degraded",
                "payload": {
                    **completion_payload,
                    "reason": "audit-completion-unavailable",
                    "error_type": type(exc).__name__,
                },
            }
        )

    return {
        "format": "query-history-review-task-v1",
        "query_log_id": canonical_query_log_id,
        "task_id": str(task["task_id"]),
        "project_key": payload.project_key,
        "status": str(task["status"]),
        "created": created,
        "review_queue_href": "/reports",
        "provider_call": False,
        "audit": {
            "status": (
                "degraded"
                if not completion_recorded
                else "ready"
                if state.audit_log_store is not None
                else "local-only"
            ),
            "intent_recorded": True,
            "completion_recorded": completion_recorded,
        },
    }


def _query_history_owner_identifier(
    *,
    state: ApiState,
    x_user_id: str | None,
    x_role: str | None,
) -> str:
    normalized_user_identifier = (x_user_id or "").strip()
    if not normalized_user_identifier or normalized_user_identifier == "anonymous":
        record_authorization_denied(
            state,
            attempted_action="query-history-list",
            permission=Permission.QUERY_KNOWLEDGE,
            user_identifier="anonymous",
            raw_role=x_role,
            status_code=401,
            reason="X-User-Id header is required",
        )
        raise HTTPException(status_code=401, detail="X-User-Id header is required")
    user = resolve_authenticated_user(
        state,
        x_user_id=normalized_user_identifier,
        x_role=x_role,
        default_role=HospitalRole.MEMBER,
    )
    if not user_has_permission(user, Permission.QUERY_KNOWLEDGE):
        record_authorization_denied(
            state,
            attempted_action="query-history-list",
            permission=Permission.QUERY_KNOWLEDGE,
            user_identifier=user.user_identifier,
            raw_role=user.raw_role,
            effective_role=user.role.value,
            auth_source=user.auth_source,
            status_code=403,
            reason="query_knowledge is not allowed",
        )
        raise HTTPException(status_code=403, detail="query_knowledge is not allowed")
    return user.user_identifier


def _query_log_fallback_items(
    state: ApiState,
    *,
    limit: int,
    user_identifier: str,
) -> list[dict[str, object]]:
    items = list(reversed(state.query_logs))
    items = [item for item in items if item.get("user_identifier") == user_identifier]
    return items[:limit]


def _query_history_review_task_user(
    state: ApiState,
    *,
    project_key: str,
    x_user_id: str | None,
    x_role: str | None,
) -> AuthenticatedUser:
    normalized_user_identifier = (x_user_id or "").strip()
    if not normalized_user_identifier or normalized_user_identifier == "anonymous":
        record_authorization_denied(
            state,
            attempted_action="query-history-review-task-create",
            permission=Permission.CREATE_REVIEW_TASK,
            user_identifier="anonymous",
            raw_role=x_role,
            status_code=401,
            reason="X-User-Id header is required",
            auth_scope_type="project",
            auth_scope_key=project_key,
        )
        raise HTTPException(status_code=401, detail="X-User-Id header is required")
    try:
        return resolve_authenticated_user(
            state,
            x_user_id=normalized_user_identifier,
            x_role=x_role,
            project_key=project_key,
        )
    except HTTPException as exc:
        record_authorization_denied(
            state,
            attempted_action="query-history-review-task-create",
            permission=Permission.CREATE_REVIEW_TASK,
            user_identifier=normalized_user_identifier,
            raw_role=x_role,
            status_code=exc.status_code,
            reason=str(exc.detail),
            auth_scope_type="project",
            auth_scope_key=project_key,
        )
        raise


def _owned_query_history(
    state: ApiState,
    *,
    query_log_id: str,
    user_identifier: str,
) -> dict[str, object]:
    store = _query_history_store_for_review_task(state)
    try:
        return store.get_query(query_log_id, user_identifier=user_identifier)
    except QueryHistoryNotFoundError as exc:
        raise HTTPException(status_code=404, detail="query history not found") from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="query history store is unavailable",
        ) from exc


def _query_history_store_for_review_task(state: ApiState) -> QueryHistoryStore:
    if state.query_history_store is None:
        raise HTTPException(status_code=503, detail="query history store is unavailable")
    return state.query_history_store


def _require_visible_query_history_project(
    state: ApiState,
    *,
    project_key: str,
    user: AuthenticatedUser,
) -> None:
    store = state.project_member_store
    if not supports_persistent_project_writes(store):
        raise HTTPException(
            status_code=503,
            detail="project membership store is unavailable",
        )
    assert store is not None
    try:
        if not project_exists(project_key, store):
            _record_query_history_project_denial(state, project_key=project_key, user=user)
            raise HTTPException(status_code=404, detail="project not found")
        visible_keys = visible_project_keys(
            user_identifier=user.user_identifier,
            is_admin=user.role is HospitalRole.ADMIN,
            store=store,
        )
    except SQLAlchemyError as exc:
        _record_query_history_operation_best_effort(
            state,
            "query-history-review-task-project-visibility-unavailable",
            {
                "project_key": project_key,
                "user_identifier": user.user_identifier,
                "status_code": 503,
                "reason": "project-membership-store-unavailable",
                "error_type": type(exc).__name__,
            },
        )
        raise HTTPException(
            status_code=503,
            detail="project membership store is unavailable",
        ) from exc
    if project_key not in visible_keys:
        _record_query_history_project_denial(state, project_key=project_key, user=user)
        raise HTTPException(status_code=404, detail="project not found")


def _record_query_history_project_denial(
    state: ApiState,
    *,
    project_key: str,
    user: AuthenticatedUser,
) -> None:
    record_authorization_denied(
        state,
        attempted_action="query-history-review-task-create",
        permission=Permission.CREATE_REVIEW_TASK,
        user_identifier=user.user_identifier,
        raw_role=user.raw_role,
        effective_role=user.role.value,
        auth_source=user.auth_source,
        profile_status=user.profile_status,
        auth_scope_type="project",
        auth_scope_key=project_key,
        status_code=404,
        reason="project not found",
    )


def _query_history_review_task_id(query_log_id: str) -> str:
    digest = hashlib.sha256(query_log_id.encode("utf-8")).hexdigest()[:32]
    return f"history-task-{digest}"


def _ensure_query_history_review_task(
    state: ApiState,
    *,
    history: dict[str, object],
    task_id: str,
    project_key: str,
    user: AuthenticatedUser,
    note: str | None,
) -> tuple[dict[str, object], bool]:
    store = _query_history_review_task_store(state)
    try:
        existing = store.get_task(task_id)
    except ReviewTaskNotFoundError:
        existing = None
    except (SQLAlchemyError, ReviewTaskStoreUnavailableError) as exc:
        raise HTTPException(status_code=503, detail="review task store is unavailable") from exc
    if existing is not None:
        _validate_existing_query_history_review_task(
            existing,
            query_log_id=str(history["id"]),
            project_key=project_key,
            user_identifier=user.user_identifier,
        )
        return existing, False

    task = _query_history_review_task_payload(
        history=history,
        task_id=task_id,
        project_key=project_key,
        user=user,
        note=note,
    )
    try:
        return store.add_task(task), True
    except (IntegrityError, ValueError):
        try:
            existing = store.get_task(task_id)
        except ReviewTaskNotFoundError as exc:
            raise HTTPException(
                status_code=409,
                detail="query history review task creation conflicted",
            ) from exc
        except (SQLAlchemyError, ReviewTaskStoreUnavailableError) as exc:
            raise HTTPException(
                status_code=503,
                detail="review task store is unavailable",
            ) from exc
        _validate_existing_query_history_review_task(
            existing,
            query_log_id=str(history["id"]),
            project_key=project_key,
            user_identifier=user.user_identifier,
        )
        return existing, False
    except (SQLAlchemyError, ReviewTaskStoreUnavailableError) as exc:
        raise HTTPException(status_code=503, detail="review task store is unavailable") from exc


def _query_history_review_task_store(state: ApiState) -> ReviewTaskStore:
    if not supports_persistent_review_task_writes(state.review_task_store):
        raise HTTPException(status_code=503, detail="review task store is unavailable")
    assert state.review_task_store is not None
    return state.review_task_store


def _query_history_review_task_payload(
    *,
    history: dict[str, object],
    task_id: str,
    project_key: str,
    user: AuthenticatedUser,
    note: str | None,
) -> dict[str, object]:
    now = _utc_now_iso()
    filters = _dict_value(history.get("filters"))
    filter_keys = (
        "top_k",
        "source_collections",
        "effective_source_collections",
        "personal_material_scope",
        "years",
        "regions",
        "document_types",
        "business_topics",
        "topic",
        "title_only",
        "agent",
        "model",
        "generation_status",
        "generation_failure_code",
        "generation_failure_reason",
        "generation_http_status",
    )
    retrieved_chunk_ids = _string_items(history.get("retrieved_chunk_ids"))
    snapshot = {
        "query_log_id": str(history["id"]),
        "question": str(history.get("question") or ""),
        "answer_summary": _truncated_optional_str(history.get("answer_summary"), limit=500),
        "filters": {key: filters[key] for key in filter_keys if key in filters},
        "retrieved_chunk_ids": retrieved_chunk_ids,
        "citation_count": len(retrieved_chunk_ids),
        "created_at": str(history.get("created_at") or ""),
        "user_identifier": user.user_identifier,
    }
    return {
        "task_id": task_id,
        "created_at": now,
        "updated_at": now,
        "status": "pending-review",
        "status_label": REVIEW_STATUS_LABELS["pending-review"],
        "question": snapshot["question"],
        "citation_count": snapshot["citation_count"],
        "review_gate": "历史对话快照仅作为人工复核输入，不构成审计疑点或结论。",
        "confidence_label": "待复核",
        "fallback_label": "历史对话",
        "source": "query-history-manual",
        "created_by": user.user_identifier,
        "assigned_to": user.user_identifier,
        "reviewer_note": note or "",
        "conclusion": "",
        "dossier": {
            "format": "query-history-review-task-dossier-v1",
            "project_key": project_key,
            "created_by": user.user_identifier,
            "query_history_snapshot": snapshot,
            "workpaper": {
                "status": "missing",
                "status_label": "未建底稿",
                "workpaper_id": "",
                "note": "",
            },
            "owner_signoff": {
                "status": "not-requested",
                "status_label": "未提交确认",
                "confirmed_by": "",
                "confirmed_at": "",
            },
            "attachments": [],
            "report_draft": {
                "title": "",
                "summary": "",
                "rectification_request": "",
                "updated_at": "",
            },
            "report_gate": {
                "source": "query-history-manual",
                "updated_at": now,
            },
        },
    }


def _validate_existing_query_history_review_task(
    task: dict[str, object],
    *,
    query_log_id: str,
    project_key: str,
    user_identifier: str,
) -> None:
    dossier = _dict_value(task.get("dossier"))
    existing_project_key = _optional_str(dossier.get("project_key"))
    if existing_project_key != project_key:
        raise HTTPException(
            status_code=409,
            detail="query history review task project scope conflicts",
        )
    snapshot = _dict_value(dossier.get("query_history_snapshot"))
    if (
        task.get("source") != "query-history-manual"
        or _optional_str(snapshot.get("query_log_id")) != query_log_id
        or _optional_str(task.get("created_by")) != user_identifier
    ):
        raise HTTPException(
            status_code=409,
            detail="query history review task is inconsistent",
        )


def _string_items(value: object) -> list[str]:
    if not isinstance(value, list | tuple):
        return []
    return [str(item) for item in value]


def _truncated_optional_str(value: object, *, limit: int) -> str | None:
    normalized = _optional_str(value)
    if normalized is None:
        return None
    return normalized[:limit]


def _record_query_history_operation_best_effort(
    state: ApiState,
    action: str,
    payload: dict[str, object],
) -> None:
    try:
        record_operation(state, action, payload)
    except SQLAlchemyError as exc:
        state.operation_logs.append(
            {
                "action": f"{action}-audit-degraded",
                "payload": {**payload, "error_type": type(exc).__name__},
            }
        )


def _query_history_item(item: dict[str, object]) -> dict[str, object]:
    filters = item.get("filters")
    if not isinstance(filters, dict) or "generation_status" not in filters:
        return item
    return {
        **item,
        "generation_status": filters["generation_status"],
        "generation_failure_code": filters.get("generation_failure_code"),
        "generation_failure_reason": filters.get("generation_failure_reason"),
        "generation_http_status": filters.get("generation_http_status"),
    }


def _effective_source_collections(
    *,
    role: str,
    requested_source_collections: tuple[SourceCollection, ...],
) -> tuple[SourceCollection, ...]:
    if requested_source_collections:
        return requested_source_collections
    return tuple(sorted(allowed_source_collections(role), key=lambda item: item.value))


def _query_filter_payload(
    payload: QueryRequest,
    *,
    role: str,
    effective_source_collections: tuple[SourceCollection, ...],
) -> dict[str, object]:
    personal_material_requested = (
        SourceCollection.PERSONAL_MATERIALS in effective_source_collections
    )
    return {
        "top_k": payload.top_k,
        "source_collections": [item.value for item in payload.source_collections],
        "effective_source_collections": [item.value for item in effective_source_collections],
        "personal_material_scope": (
            "all"
            if personal_material_requested and can_read_all_personal_uploads(role)
            else "self"
            if personal_material_requested
            else "none"
        ),
        "years": list(payload.years),
        "regions": list(payload.regions),
        "document_types": list(payload.document_types),
        "business_topics": list(payload.business_topics),
        "topic": payload.topic,
        "title_only": payload.title_only,
        "agent": _normalize_agent_key(payload.agent),
        "model": payload.model.value if payload.model is not None else None,
    }


def _record_query_agent_invocation(
    state: ApiState,
    *,
    agent_key: str,
    question: str,
    user_identifier: str,
    filters: dict[str, object],
    query_log_id: str | None,
    query_log_index: int,
    citation_count: int,
    request_project_name: str | None,
) -> dict[str, object]:
    metadata: dict[str, object] = {
        "filters": filters,
        "query_log_id": query_log_id,
        "query_log_index": query_log_index,
        "citation_count": citation_count,
        "project_name": _normalize_project_name(request_project_name),
    }
    try:
        invocation = _agent_store(state).record_invocation(
            agent_key,
            invocation_source="/query",
            question=question,
            conversation_ref=query_log_id or f"query-log-index:{query_log_index}",
            created_by=user_identifier,
            metadata=metadata,
        )
        record_operation(
            state,
            "agent-invocation-create",
            {
                "agent_id": agent_key,
                "invocation_id": invocation["id"],
                "prompt_version": invocation["prompt_version"],
                "created_by": user_identifier,
                "invocation_source": "/query",
            },
        )
        return invocation
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="agent not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=409,
            detail="persistent agent store is not available",
        ) from exc


def _validate_agent_selection(
    state: ApiState,
    agent_key: str,
    *,
    request_project_name: str | None,
    attempted_action: str,
) -> dict[str, object]:
    try:
        agent = _agent_payload_for_key(state, agent_key)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=409,
            detail="persistent agent store is not available",
        ) from exc
    if agent is None:
        raise HTTPException(status_code=404, detail="agent not found")
    if str(agent.get("status") or "active") != "active":
        raise HTTPException(status_code=409, detail=f"agent is not active: {agent_key}")
    if not str(agent.get("prompt") or "").strip():
        raise HTTPException(status_code=409, detail="agent prompt is unavailable")
    _enforce_agent_project_scope(
        state,
        agent,
        request_project_name=request_project_name,
        attempted_action=attempted_action,
    )
    return agent


def _agent_payload_for_key(state: ApiState, agent_key: str) -> dict[str, object] | None:
    agent = _agent_store(state).get_agent(agent_key)
    if agent is not None:
        return agent
    return next(
        (dict(agent) for agent in combined_agent_payloads([]) if agent["id"] == agent_key),
        None,
    )


def _agent_store(state: ApiState) -> AgentStore:
    if state.agent_store is None:
        state.agent_store = InMemoryAgentStore()
    return state.agent_store


def _enforce_agent_project_scope(
    state: ApiState,
    agent: dict[str, object],
    *,
    request_project_name: str | None,
    attempted_action: str,
) -> None:
    normalized_project = _normalize_project_name(request_project_name)
    if str(agent.get("visibility_scope") or "project") != "project":
        return
    agent_project_name = str(agent.get("project_name") or "").strip()
    if not normalized_project:
        record_operation(
            state,
            "agent-project-scope-denied",
            {
                "agent_id": str(agent.get("id") or ""),
                "agent_project_name": agent_project_name,
                "request_project_name": "",
                "attempted_action": attempted_action,
            },
        )
        raise HTTPException(
            status_code=403,
            detail="agent project scope requires current project",
        )
    if agent_project_name == normalized_project:
        return
    record_operation(
        state,
        "agent-project-scope-denied",
        {
            "agent_id": str(agent.get("id") or ""),
            "agent_project_name": agent_project_name,
            "request_project_name": normalized_project,
            "attempted_action": attempted_action,
        },
    )
    raise HTTPException(
        status_code=403,
        detail="agent project scope does not match current project",
    )


def _normalize_project_name(project_name: str | None) -> str | None:
    if project_name is None:
        return None
    normalized = urllib.parse.unquote(project_name.strip())
    return normalized or None


def _normalize_agent_key(agent_key: str | None) -> str | None:
    if agent_key is None:
        return None
    normalized = agent_key.strip()
    return normalized or None


def _personal_upload_matches(
    *,
    state: ApiState,
    user: AuthenticatedUser,
    role: str,
    query_text: str,
    limit: int,
) -> list[dict[str, object]]:
    if state.document_upload_store is None:
        return []
    return state.document_upload_store.search_personal_index(
        query=query_text,
        created_by=user.user_identifier,
        include_all=can_read_all_personal_uploads(role),
        limit=limit,
    )


@router.get("/operation/logs")
def operation_logs(
    state: Annotated[ApiState, Depends(get_api_state)],
) -> dict[str, object]:
    return {"items": state.operation_logs}


@router.get("/operation/logs/export")
def export_operation_logs(
    state: Annotated[ApiState, Depends(get_api_state)],
) -> dict[str, object]:
    record_operation(state, "operation-logs-export", {"count": len(state.operation_logs)})
    return {"items": state.operation_logs, "format": "json"}


@router.get("/audit-findings")
def audit_findings(
    state: Annotated[ApiState, Depends(get_api_state)],
    review_status: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> dict[str, object]:
    if review_status is not None and review_status not in REVIEW_STATUS_LABELS:
        raise HTTPException(status_code=422, detail=f"unsupported review_status: {review_status}")
    user = _require_medical_audit_actor(
        state,
        x_user_id=x_user_id,
        x_role=x_role,
        attempted_action="audit-findings-list",
    )
    project_keys = _visible_audit_finding_project_keys(
        state,
        user=user,
        attempted_action="audit-findings-list",
    )
    if state.audit_finding_store is None:
        return {
            "items": [],
            "stats": _audit_finding_stats([]),
            "filters": {"review_status": review_status, "limit": limit},
            "review_status_options": REVIEW_STATUS_LABELS,
            "generation_readiness": _audit_finding_store_unavailable_readiness(),
            "store": {"ready": False, "backend": "none"},
        }

    findings = state.audit_finding_store.list_findings(
        review_status=review_status,
        project_keys=project_keys,
        limit=limit,
    )
    record_operation(
        state,
        "audit-findings-list",
        {"finding_count": len(findings), "review_status": review_status or "all", "limit": limit},
    )
    generation_readiness = (
        state.audit_finding_store.generation_readiness()
        if user.role is HospitalRole.ADMIN
        else _scoped_audit_finding_readiness(
            state.audit_finding_store.count_findings(project_keys=project_keys)
        )
    )
    return {
        "items": findings,
        "stats": _audit_finding_stats(findings),
        "filters": {"review_status": review_status, "limit": limit},
        "review_status_options": REVIEW_STATUS_LABELS,
        "generation_readiness": generation_readiness,
        "store": {"ready": True, "backend": state.audit_finding_store.__class__.__name__},
    }


@router.post("/audit-findings/import-preflight")
def medical_audit_import_preflight(
    payload: MedicalAuditImportPreflightRequest,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> dict[str, object]:
    user = _require_medical_audit_actor(
        state,
        x_user_id=x_user_id,
        x_role=x_role,
        attempted_action="medical-audit-import-preflight",
    )
    audit_event = _record_medical_audit_event(
        state,
        "medical-audit-import-preflight",
        {
            "template_id": payload.template_id,
            "template_name": payload.template_name,
            "file_name": payload.file_name,
            "row_count": payload.row_count,
            "note": payload.note,
            "user_identifier": user.user_identifier,
            "role": user.legacy_api_role,
            "endpoint": "/api/v1/audit-findings/import-preflight",
        },
    )
    return _workflow_action_response(
        action="import-preflight",
        status="preflight_recorded",
        user=user,
        payload={
            "preflight": {
                "template_id": payload.template_id,
                "template_name": payload.template_name,
                "file_name": payload.file_name,
                "row_count": payload.row_count,
                "checks": [
                    "确认模板类型与导入文件一致",
                    "解析字段后执行映射预览",
                    "确认写入窗口和回滚点",
                    "写入后重新运行疑点规则并生成复核任务",
                ],
            },
            "audit_event": audit_event,
        },
    )


@router.post("/audit-findings/{finding_key}/review-task")
def medical_audit_create_review_task(
    finding_key: str,
    payload: MedicalAuditReviewTaskRequest,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> dict[str, object]:
    user = _require_medical_audit_actor(
        state,
        x_user_id=x_user_id,
        x_role=x_role,
        attempted_action="medical-audit-review-task-create",
    )
    finding = _visible_audit_finding_by_key_for_api(
        state,
        finding_key,
        user=user,
        attempted_action="medical-audit-review-task-create",
    )
    task, created = _ensure_medical_audit_review_task(
        state,
        finding=finding,
        user=user,
        assigned_to=payload.assigned_to,
        note=payload.note,
    )
    updated_finding = _visible_audit_finding_by_key_for_api(
        state,
        finding_key,
        user=user,
        attempted_action="medical-audit-review-task-create",
    )
    audit_event = _record_medical_audit_event(
        state,
        "medical-audit-review-task-create",
        {
            "finding_key": finding_key,
            "task_id": str(task["task_id"]),
            "created": created,
            "user_identifier": user.user_identifier,
            "role": user.legacy_api_role,
            "endpoint": f"/api/v1/audit-findings/{finding_key}/review-task",
        },
    )
    return _workflow_action_response(
        action="review-task-create",
        status="created" if created else "existing",
        user=user,
        payload={
            "finding": updated_finding,
            "task": task,
            "created": created,
            "audit_event": audit_event,
        },
    )


@router.post("/audit-findings/{finding_key}/review-status")
def medical_audit_update_review_status(
    finding_key: str,
    payload: MedicalAuditReviewStatusRequest,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> dict[str, object]:
    if payload.status not in REVIEW_STATUS_LABELS:
        raise HTTPException(status_code=422, detail=f"unsupported review status: {payload.status}")
    user = _require_medical_audit_actor(
        state,
        x_user_id=x_user_id,
        x_role=x_role,
        attempted_action="medical-audit-review-status-update",
    )
    finding = _visible_audit_finding_by_key_for_api(
        state,
        finding_key,
        user=user,
        attempted_action="medical-audit-review-status-update",
    )
    task, created = _ensure_medical_audit_review_task(
        state,
        finding=finding,
        user=user,
        assigned_to=payload.assigned_to,
        note="复核状态更新前自动创建任务" if not finding.get("review_task_id") else None,
    )
    _ensure_task_not_closed(task)
    dossier = _dict_value(task.get("dossier"))
    dossier["last_review_action"] = {
        "status": payload.status,
        "status_label": REVIEW_STATUS_LABELS[payload.status],
        "reviewer_note": payload.reviewer_note,
        "conclusion": payload.conclusion,
        "updated_at": _utc_now_iso(),
        "updated_by": user.user_identifier,
    }
    updated_task = _review_task_store_for_api(state).update_task(
        str(task["task_id"]),
        {
            "status": payload.status,
            "status_label": REVIEW_STATUS_LABELS[payload.status],
            "assigned_to": payload.assigned_to or task.get("assigned_to"),
            "reviewer_note": payload.reviewer_note,
            "conclusion": payload.conclusion,
            "dossier": dossier,
        },
    )
    synced_findings = _sync_audit_finding_review_status_for_api(
        state,
        str(updated_task["task_id"]),
        payload.status,
        project_key=_optional_str(finding.get("project_key")),
    )
    audit_event = _record_medical_audit_event(
        state,
        "medical-audit-review-status-update",
        {
            "finding_key": finding_key,
            "task_id": str(updated_task["task_id"]),
            "status": payload.status,
            "created_task": created,
            "synced_audit_finding_count": len(synced_findings),
            "user_identifier": user.user_identifier,
            "role": user.legacy_api_role,
            "endpoint": f"/api/v1/audit-findings/{finding_key}/review-status",
        },
    )
    return _workflow_action_response(
        action="review-status-update",
        status="updated",
        user=user,
        payload={
            "finding": _visible_audit_finding_by_key_for_api(
                state,
                finding_key,
                user=user,
                attempted_action="medical-audit-review-status-update",
            ),
            "task": updated_task,
            "created_task": created,
            "synced_findings": synced_findings,
            "audit_event": audit_event,
        },
    )


@router.post("/audit-findings/{finding_key}/supplemental-material")
def medical_audit_attach_supplemental_material(
    finding_key: str,
    payload: MedicalAuditSupplementRequest,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> dict[str, object]:
    user = _require_medical_audit_actor(
        state,
        x_user_id=x_user_id,
        x_role=x_role,
        attempted_action="medical-audit-supplemental-material-register",
    )
    finding = _visible_audit_finding_by_key_for_api(
        state,
        finding_key,
        user=user,
        attempted_action="medical-audit-supplemental-material-register",
    )
    task, created = _ensure_medical_audit_review_task(
        state,
        finding=finding,
        user=user,
        assigned_to=None,
        note="补充材料登记前自动创建任务" if not finding.get("review_task_id") else None,
    )
    _ensure_task_not_closed(task)
    dossier = _dict_value(task.get("dossier"))
    attachments = _dict_list(dossier.get("attachments"))
    attachment = {
        "attachment_id": f"supplement-{len(attachments) + 1:03d}",
        "title": payload.title,
        "locator": payload.locator or "",
        "note": payload.note or "",
        "status": "registered",
        "uploaded_at": _utc_now_iso(),
        "registered_by": user.user_identifier,
    }
    dossier["attachments"] = [*attachments, attachment]
    updated_task = _review_task_store_for_api(state).update_task(
        str(task["task_id"]),
        {"dossier": dossier},
    )
    audit_event = _record_medical_audit_event(
        state,
        "medical-audit-supplemental-material-register",
        {
            "finding_key": finding_key,
            "task_id": str(updated_task["task_id"]),
            "attachment_id": attachment["attachment_id"],
            "created_task": created,
            "user_identifier": user.user_identifier,
            "role": user.legacy_api_role,
            "endpoint": f"/api/v1/audit-findings/{finding_key}/supplemental-material",
        },
    )
    return _workflow_action_response(
        action="supplemental-material-register",
        status="registered",
        user=user,
        payload={
            "task": updated_task,
            "attachment": attachment,
            "created_task": created,
            "audit_event": audit_event,
        },
    )


@router.post("/audit-findings/{finding_key}/report-entry")
def medical_audit_add_to_report(
    finding_key: str,
    payload: MedicalAuditReportEntryRequest,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> dict[str, object]:
    user = _require_medical_audit_actor(
        state,
        x_user_id=x_user_id,
        x_role=x_role,
        attempted_action="medical-audit-report-entry-add",
    )
    finding = _visible_audit_finding_by_key_for_api(
        state,
        finding_key,
        user=user,
        attempted_action="medical-audit-report-entry-add",
    )
    task, created = _ensure_medical_audit_review_task(
        state,
        finding=finding,
        user=user,
        assigned_to=None,
        note="报告纳入前自动创建任务" if not finding.get("review_task_id") else None,
    )
    _ensure_task_not_closed(task)
    now = _utc_now_iso()
    dossier = _dict_value(task.get("dossier"))
    attachments = _dict_list(dossier.get("attachments"))
    if not attachments:
        attachments = [
            {
                "attachment_id": "finding-evidence-001",
                "title": "疑点证据链摘要",
                "locator": str(finding.get("finding_key", "")),
                "note": "由医保审计疑点详情自动登记，用于报告门禁。",
                "status": "registered",
                "uploaded_at": now,
                "registered_by": user.user_identifier,
            }
        ]
    dossier["attachments"] = attachments
    dossier["workpaper"] = {
        "status": "ready",
        "status_label": WORKPAPER_STATUS_LABELS["ready"],
        "workpaper_id": f"WP-{finding_key}",
        "note": "医保审计页面纳入报告时生成的底稿占位记录。",
    }
    dossier["owner_signoff"] = {
        "status": "approved",
        "status_label": OWNER_SIGNOFF_STATUS_LABELS["approved"],
        "confirmed_by": payload.owner_confirmed_by or user.user_identifier,
        "confirmed_at": now,
    }
    dossier["report_draft"] = {
        "title": payload.report_title or f"{finding_key} 医保审计复核报告草稿",
        "summary": payload.summary
        or f"围绕疑点 {finding_key} 的规则命中、证据链和复核结论生成报告草稿。",
        "rectification_request": payload.rectification_request
        or "请责任科室核对 HIS 明细、收费依据和退费/补证材料。",
        "updated_at": now,
    }
    dossier["report_gate"] = {
        "source": "medical-audit-page",
        "updated_at": now,
    }
    update_values: dict[str, object] = {
        "dossier": dossier,
        "reviewer_note": task.get("reviewer_note") or "已从医保审计工作台纳入报告草稿。",
        "conclusion": task.get("conclusion") or "确认该疑点进入报告草稿，等待正式签发流程。",
    }
    status = str(task.get("status", "pending-review"))
    if status not in RESOLVED_REVIEW_STATUSES:
        update_values["status"] = "confirmed-violation"
        update_values["status_label"] = REVIEW_STATUS_LABELS["confirmed-violation"]
    updated_task = _review_task_store_for_api(state).update_task(
        str(task["task_id"]),
        update_values,
    )
    synced_findings = _sync_audit_finding_review_status_for_api(
        state,
        str(updated_task["task_id"]),
        str(updated_task.get("status", "confirmed-violation")),
        project_key=_optional_str(finding.get("project_key")),
    )
    audit_event = _record_medical_audit_event(
        state,
        "medical-audit-report-entry-add",
        {
            "finding_key": finding_key,
            "task_id": str(updated_task["task_id"]),
            "created_task": created,
            "synced_audit_finding_count": len(synced_findings),
            "user_identifier": user.user_identifier,
            "role": user.legacy_api_role,
            "endpoint": f"/api/v1/audit-findings/{finding_key}/report-entry",
        },
    )
    return _workflow_action_response(
        action="report-entry-add",
        status="added",
        user=user,
        payload={
            "finding": _visible_audit_finding_by_key_for_api(
                state,
                finding_key,
                user=user,
                attempted_action="medical-audit-report-entry-add",
            ),
            "task": updated_task,
            "created_task": created,
            "synced_findings": synced_findings,
            "audit_event": audit_event,
        },
    )


@router.get("/audit/logs")
def audit_logs(
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
    action: Annotated[str | None, Query(max_length=96)] = None,
    entity_type: Annotated[str | None, Query(max_length=64)] = None,
    entity_id: Annotated[str | None, Query(max_length=128)] = None,
    user_identifier: Annotated[str | None, Query(max_length=128)] = None,
    created_from: Annotated[datetime | None, Query()] = None,
    created_to: Annotated[datetime | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> dict[str, object]:
    filters = _audit_log_filters(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        user_identifier=user_identifier,
        created_from=created_from,
        created_to=created_to,
        limit=limit,
    )
    _require_audit_log_reader(state, x_role=x_role, x_user_id=x_user_id)
    if state.audit_log_store is None:
        return {
            "items": [],
            "filters": filters,
            "store": {"ready": False, "backend": "none"},
            "policy": audit_log_policy_payload(),
        }
    events = state.audit_log_store.list_events(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        user_identifier=user_identifier,
        created_from=created_from,
        created_to=created_to,
        limit=limit,
    )
    return {
        "items": redact_audit_log_events(events),
        "filters": filters,
        "store": {"ready": True, "backend": state.audit_log_store.__class__.__name__},
        "policy": audit_log_policy_payload(),
    }


@router.get("/audit/logs/export")
def export_audit_logs(
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
    action: Annotated[str | None, Query(max_length=96)] = None,
    entity_type: Annotated[str | None, Query(max_length=64)] = None,
    entity_id: Annotated[str | None, Query(max_length=128)] = None,
    user_identifier: Annotated[str | None, Query(max_length=128)] = None,
    created_from: Annotated[datetime | None, Query()] = None,
    created_to: Annotated[datetime | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 500,
) -> Response:
    user = _require_audit_log_reader(state, x_role=x_role, x_user_id=x_user_id)
    if state.audit_log_store is None:
        raise HTTPException(status_code=409, detail="persistent audit log store is not configured")

    filters = _audit_log_filters(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        user_identifier=user_identifier,
        created_from=created_from,
        created_to=created_to,
        limit=limit,
    )
    record_operation(
        state,
        "audit-logs-export",
        {
            "filters": filters,
            "limit": limit,
            "user_identifier": user.user_identifier,
            "role": user.legacy_api_role,
            "effective_role": user.role.value,
            "auth_source": user.auth_source,
        },
    )
    items = state.audit_log_store.list_events(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        user_identifier=user_identifier,
        created_from=created_from,
        created_to=created_to,
        limit=limit,
    )
    return Response(
        content=json.dumps(
            {
                "items": redact_audit_log_events(items),
                "filters": filters,
                "format": "json",
                "policy": audit_log_policy_payload(),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="auditscope-audit-logs.json"'},
    )


def _require_medical_audit_actor(
    state: ApiState,
    *,
    x_user_id: str | None,
    x_role: str | None,
    attempted_action: str,
) -> AuthenticatedUser:
    normalized_user_identifier = (x_user_id or "").strip()
    if not normalized_user_identifier or normalized_user_identifier == "anonymous":
        raise HTTPException(status_code=401, detail="X-User-Id header is required")
    return require_permission(
        state,
        permission=Permission.ANALYZE_DATA,
        x_user_id=normalized_user_identifier,
        x_role=x_role,
        attempted_action=attempted_action,
    )


def _audit_finding_by_key_for_api(state: ApiState, finding_key: str) -> dict[str, object]:
    if state.audit_finding_store is None:
        raise HTTPException(status_code=409, detail="audit finding store is not configured")
    try:
        return state.audit_finding_store.get_finding(finding_key)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="audit finding not found") from exc
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="audit finding store is unavailable") from exc


def _visible_audit_finding_by_key_for_api(
    state: ApiState,
    finding_key: str,
    *,
    user: AuthenticatedUser,
    attempted_action: str,
) -> dict[str, object]:
    finding = _audit_finding_by_key_for_api(state, finding_key)
    visible_keys = _visible_audit_finding_project_keys(
        state,
        user=user,
        attempted_action=attempted_action,
    )
    project_key = _optional_str(finding.get("project_key"))
    if project_key is None or project_key not in visible_keys:
        raise HTTPException(status_code=404, detail="audit finding not found")
    return finding


def _visible_audit_finding_project_keys(
    state: ApiState,
    *,
    user: AuthenticatedUser,
    attempted_action: str,
) -> frozenset[str]:
    store = _project_member_store_for_audit_findings(state)
    try:
        return visible_project_keys(
            user_identifier=user.user_identifier,
            is_admin=user.role is HospitalRole.ADMIN,
            store=store,
        )
    except SQLAlchemyError as exc:
        record_operation(
            state,
            "audit-finding-project-visibility-unavailable",
            {
                "attempted_action": attempted_action,
                "user_identifier": user.user_identifier,
                "status_code": 503,
                "reason": "project-membership-store-unavailable",
                "error_type": type(exc).__name__,
            },
        )
        raise HTTPException(
            status_code=503,
            detail="project membership store is unavailable",
        ) from exc


def _project_member_store_for_audit_findings(state: ApiState) -> ProjectMemberStore:
    if state.project_member_store is None:
        raise HTTPException(
            status_code=503,
            detail="project membership store is not configured",
        )
    return state.project_member_store


def _review_task_store_for_api(state: ApiState) -> ReviewTaskStore:
    if state.review_task_store is None:
        raise HTTPException(status_code=409, detail="review task store is not configured")
    return state.review_task_store


def _ensure_medical_audit_review_task(
    state: ApiState,
    *,
    finding: dict[str, object],
    user: AuthenticatedUser,
    assigned_to: str | None,
    note: str | None,
) -> tuple[dict[str, object], bool]:
    store = _review_task_store_for_api(state)
    existing_task_id = _optional_str(finding.get("review_task_id"))
    if existing_task_id is not None:
        try:
            existing_task = store.get_task(existing_task_id)
            finding_project_key = _optional_str(finding.get("project_key"))
            try:
                task_project_key = review_task_project_key(existing_task)
            except ReviewTaskProjectScopeConflictError as exc:
                raise HTTPException(
                    status_code=409,
                    detail="review task project scope does not match audit finding",
                ) from exc
            if finding_project_key is None:
                raise HTTPException(
                    status_code=409,
                    detail="review task project scope does not match audit finding",
                )
            if task_project_key is None:
                dossier = _dict_value(existing_task.get("dossier"))
                dossier["project_key"] = finding_project_key
                existing_task = store.update_task(
                    existing_task_id,
                    {"dossier": dossier},
                )
            elif task_project_key != finding_project_key:
                raise HTTPException(
                    status_code=409,
                    detail="review task project scope does not match audit finding",
                )
            return existing_task, False
        except ReviewTaskNotFoundError:
            pass

    now = _utc_now_iso()
    task = {
        "task_id": store.next_task_id(),
        "created_at": now,
        "updated_at": now,
        "status": "pending-review",
        "status_label": REVIEW_STATUS_LABELS["pending-review"],
        "question": f"复核疑点 {finding['finding_key']}：{finding.get('finding_type')}",
        "citation_count": len(_dict_list(finding.get("evidence_items"))),
        "review_gate": "疑点已绑定规则版本、计算过程和证据链，进入人工复核。",
        "confidence_label": "中",
        "fallback_label": "规则命中",
        "source": "medical-audit-workflow",
        "assigned_to": assigned_to or "",
        "reviewer_note": note or "",
        "conclusion": "",
        "created_by": user.user_identifier,
        "dossier": _medical_audit_finding_dossier(finding, created_by=user.user_identifier),
    }
    created_task = store.add_task(task)
    if state.audit_finding_store is not None:
        try:
            state.audit_finding_store.link_review_task(
                str(finding["finding_key"]),
                str(created_task["task_id"]),
            )
        except (SQLAlchemyError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    return created_task, True


def _medical_audit_finding_dossier(
    finding: dict[str, object],
    *,
    created_by: str,
) -> dict[str, object]:
    return {
        "format": "medical-audit-finding-dossier-v1",
        "generated_at": _utc_now_iso(),
        "created_by": created_by,
        "project_key": finding.get("project_key"),
        "finding_key": finding.get("finding_key"),
        "finding_type": finding.get("finding_type"),
        "severity": finding.get("severity"),
        "audit_task_key": finding.get("audit_task_key"),
        "audit_run_key": finding.get("audit_run_key"),
        "rule_key": finding.get("rule_key"),
        "rule_version_key": finding.get("rule_version_key"),
        "source_record_locator": _dict_value(finding.get("source_record_locator")),
        "calculation_trace": _dict_value(finding.get("calculation_trace")),
        "evidence_items": _dict_list(finding.get("evidence_items")),
        "workpaper": {
            "status": "draft",
            "status_label": WORKPAPER_STATUS_LABELS["draft"],
            "workpaper_id": "",
            "note": "",
        },
        "owner_signoff": {
            "status": "not-requested",
            "status_label": OWNER_SIGNOFF_STATUS_LABELS["not-requested"],
            "confirmed_by": "",
            "confirmed_at": "",
        },
        "attachments": [],
        "report_draft": {
            "title": "",
            "summary": "",
            "rectification_request": "",
            "updated_at": "",
        },
        "report_gate": {"source": "medical-audit-workflow", "updated_at": _utc_now_iso()},
    }


def _sync_audit_finding_review_status_for_api(
    state: ApiState,
    task_id: str,
    review_status: str,
    *,
    project_key: str | None,
) -> list[dict[str, object]]:
    if state.audit_finding_store is None or project_key is None:
        return []
    try:
        return state.audit_finding_store.sync_review_task_status(
            task_id,
            review_status,
            project_keys=frozenset({project_key}),
        )
    except (SQLAlchemyError, ValueError):
        return []


def _record_medical_audit_event(
    state: ApiState,
    action: str,
    payload: dict[str, object],
) -> dict[str, object] | None:
    record_operation(state, action, payload)
    if state.audit_log_store is None:
        return None
    try:
        return state.audit_log_store.add_event(action, payload)
    except SQLAlchemyError as exc:
        record_operation(
            state,
            "medical-audit-audit-log-write-failed",
            {
                "action": action,
                "reason": str(exc),
                "finding_key": payload.get("finding_key"),
                "task_id": payload.get("task_id"),
            },
        )
        return None


def _workflow_action_response(
    *,
    action: str,
    status: str,
    user: AuthenticatedUser,
    payload: dict[str, object],
) -> dict[str, object]:
    return {
        "format": "medical-audit-workflow-action-v1",
        "action": action,
        "status": status,
        "processed_at": _utc_now_iso(),
        "actor": {
            "user_identifier": user.user_identifier,
            "role": user.legacy_api_role,
            "auth_source": user.auth_source,
        },
        **payload,
    }


def _ensure_task_not_closed(task: dict[str, object]) -> None:
    if str(task.get("status", "")).strip() == "closed":
        raise HTTPException(status_code=409, detail="review task is closed and read-only")


def _dict_value(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return dict(value)
    return {}


def _dict_list(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_chunk_id(chunk_id: str) -> UUID:
    try:
        return UUID(chunk_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="invalid chunk_id") from exc


def _audit_log_filters(
    *,
    action: str | None,
    entity_type: str | None,
    entity_id: str | None,
    user_identifier: str | None,
    created_from: datetime | None,
    created_to: datetime | None,
    limit: int,
) -> dict[str, object]:
    return {
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "user_identifier": user_identifier,
        "created_from": created_from.isoformat() if created_from is not None else None,
        "created_to": created_to.isoformat() if created_to is not None else None,
        "limit": limit,
    }


def _audit_finding_stats(findings: list[dict[str, object]]) -> dict[str, int]:
    return {
        "total": len(findings),
        "open": sum(1 for item in findings if item.get("status") == "open"),
        "pending_review": sum(
            1 for item in findings if item.get("review_status") == "pending-review"
        ),
        "linked_review_task": sum(1 for item in findings if item.get("review_task_id")),
    }


def _scoped_audit_finding_readiness(
    finding_count: int,
) -> dict[str, object]:
    return {
        "status": "generated" if finding_count else "empty",
        "ready": True,
        "scope": "visible-projects",
        "has_findings": finding_count > 0,
        "table_counts": {"audit_findings": finding_count},
        "prerequisites": [],
        "blocking_reasons": [],
        "next_actions": (
            ["从可见疑点清单创建人工复核任务，完成复核后再进入底稿或报告。"]
            if finding_count
            else []
        ),
    }


def _audit_finding_store_unavailable_readiness() -> dict[str, object]:
    return {
        "status": "blocked",
        "ready": False,
        "has_findings": False,
        "table_counts": {},
        "prerequisites": [],
        "blocking_reasons": [
            {
                "code": "audit-finding-store-unavailable",
                "message": "疑点 store 未初始化，无法读取规则生成链路状态。",
            }
        ],
        "next_actions": ["检查 MEDICAL_AUDIT_KB_DATABASE_URL 和审计疑点 store 初始化。"],
    }


def _require_audit_log_reader(
    state: ApiState,
    *,
    x_role: str | None,
    x_user_id: str | None,
) -> AuthenticatedUser:
    return require_permission(
        state,
        permission=Permission.READ_AUDIT_LOGS,
        x_user_id=x_user_id,
        x_role=x_role,
        attempted_action="audit-logs-read",
    )
