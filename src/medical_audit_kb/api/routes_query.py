from __future__ import annotations

import json
import urllib.parse
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import SQLAlchemyError

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
    require_permission,
    resolve_authenticated_user,
)
from medical_audit_kb.api.document_permissions import (
    allowed_source_collections,
    can_read_all_personal_uploads,
    enforce_source_collection_access,
)
from medical_audit_kb.api.query_history_store import try_add_query_history, try_list_query_history
from medical_audit_kb.domain.constants import SourceCollection
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
    "not-violation": "排除违规",
    "closed": "已关闭",
}


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
    source_collections: list[SourceCollection] = Field(default_factory=list)
    years: list[int] = Field(default_factory=list)
    regions: list[str] = Field(default_factory=list)
    document_types: list[str] = Field(default_factory=list)
    business_topics: list[str] = Field(default_factory=list)
    topic: str | None = Field(default=None, max_length=64)
    title_only: bool = False
    agent: str | None = Field(default=None, max_length=128)


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
    if agent_key is not None:
        _validate_agent_selection(
            state,
            agent_key,
            request_project_name=x_project_name,
            attempted_action="query-agent-select",
        )
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
    )
    results = state.search_engine.search(payload.question, filters=filters, top_k=payload.top_k)
    try:
        answer = build_citation_backed_answer(
            payload.question,
            results,
            generation_provider=state.answer_generation_provider,
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
    )
    retrieved_chunk_ids = [str(citation.chunk_id) for citation in answer.citations]
    agent_invocation_id: str | None = None
    log_entry: dict[str, object] = {
        "user_identifier": user.user_identifier,
        "role": role,
        "effective_role": user.role.value,
        "auth_source": user.auth_source,
        "question": payload.question,
        "agent_id": agent_key,
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
            "filters": filter_payload,
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
            "query_log_id": persisted_log.get("id") if persisted_log else None,
            "query_history_error": query_history_error,
            "filters": filter_payload,
            "personal_upload_match_count": len(personal_upload_matches),
        },
    )

    return {
        "question": answer.question,
        "answer": answer.answer,
        "confidence": answer.confidence.value,
        "fallback_used": answer.fallback_used,
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
) -> dict[str, object]:
    if state.query_history_store is not None:
        history_items, query_history_error = try_list_query_history(
            state.query_history_store,
            limit=limit,
        )
        if query_history_error is not None:
            record_operation(state, "query-history-list-failed", query_history_error)
            return {
                "items": list(reversed(state.query_logs[-limit:])),
                "store": {
                    "ready": False,
                    "backend": state.query_history_store.__class__.__name__,
                    "error": query_history_error,
                },
            }
        assert history_items is not None
        return {
            "items": history_items,
            "store": {"ready": True, "backend": state.query_history_store.__class__.__name__},
        }
    return {
        "items": list(reversed(state.query_logs[-limit:])),
        "store": {"ready": False, "backend": "memory"},
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
    effective_source_collections: tuple[SourceCollection, ...],
) -> dict[str, object]:
    return {
        "top_k": payload.top_k,
        "source_collections": [item.value for item in payload.source_collections],
        "effective_source_collections": [item.value for item in effective_source_collections],
        "years": list(payload.years),
        "regions": list(payload.regions),
        "document_types": list(payload.document_types),
        "business_topics": list(payload.business_topics),
        "topic": payload.topic,
        "title_only": payload.title_only,
        "agent": _normalize_agent_key(payload.agent),
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
    if not normalized_project or str(agent.get("visibility_scope") or "project") != "project":
        return
    agent_project_name = str(agent.get("project_name") or "").strip()
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
) -> dict[str, object]:
    if review_status is not None and review_status not in REVIEW_STATUS_LABELS:
        raise HTTPException(status_code=422, detail=f"unsupported review_status: {review_status}")
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
        limit=limit,
    )
    record_operation(
        state,
        "audit-findings-list",
        {"finding_count": len(findings), "review_status": review_status or "all", "limit": limit},
    )
    return {
        "items": findings,
        "stats": _audit_finding_stats(findings),
        "filters": {"review_status": review_status, "limit": limit},
        "review_status_options": REVIEW_STATUS_LABELS,
        "generation_readiness": state.audit_finding_store.generation_readiness(),
        "store": {"ready": True, "backend": state.audit_finding_store.__class__.__name__},
    }


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
