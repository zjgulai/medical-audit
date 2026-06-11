from __future__ import annotations

import json
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from medical_audit_kb.api.app import ApiState, PreviewReference, get_api_state, record_operation
from medical_audit_kb.api.audit_log_policy import (
    audit_log_policy_payload,
    can_read_audit_logs,
    redact_audit_log_events,
)
from medical_audit_kb.domain.constants import SourceCollection
from medical_audit_kb.generation.answer_builder import (
    NoCitedEvidenceError,
    build_citation_backed_answer,
)
from medical_audit_kb.retrieval.filters import RetrievalFilters

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


@router.post("/query")
def query(
    payload: QueryRequest,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> dict[str, object]:
    if x_role is not None and x_role not in {"auditor", "it-admin", "department-head"}:
        raise HTTPException(status_code=403, detail="role is not allowed to query")
    if state.search_engine is None:
        raise HTTPException(status_code=409, detail="search engine is not initialized")

    filters = RetrievalFilters(
        source_collections=tuple(payload.source_collections),
        years=tuple(payload.years),
        regions=tuple(payload.regions),
        document_types=tuple(payload.document_types),
        business_topics=tuple(payload.business_topics),
    )
    results = state.search_engine.search(payload.question, filters=filters, top_k=payload.top_k)
    try:
        answer = build_citation_backed_answer(payload.question, results)
    except NoCitedEvidenceError as exc:
        raise HTTPException(status_code=404, detail="no cited evidence found") from exc
    for citation in answer.citations:
        state.preview_references[citation.chunk_id] = PreviewReference(
            locator=citation.locator,
            citation_text=citation.snippet,
        )

    log_entry = {
        "user_identifier": x_user_id or "anonymous",
        "role": x_role or "auditor",
        "question": payload.question,
        "retrieved_chunk_ids": [str(citation.chunk_id) for citation in answer.citations],
        "citation_count": len(answer.citations),
    }
    state.query_logs.append(log_entry)
    record_operation(
        state,
        "query",
        {
            "question": payload.question,
            "citation_count": len(answer.citations),
            "user_identifier": x_user_id or "anonymous",
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
                "snippet": citation.snippet,
                "locator": citation.locator,
                "index_version_key": citation.index_version_key,
                "source_package_version_key": citation.source_package_version_key,
            }
            for citation in answer.citations
        ],
        "query_log_index": len(state.query_logs) - 1,
    }


@router.get("/query/logs")
def query_logs(
    state: Annotated[ApiState, Depends(get_api_state)],
) -> dict[str, object]:
    return {"items": state.query_logs}


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
    _require_audit_log_reader(state, role=x_role, user_identifier=x_user_id)
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
    _require_audit_log_reader(state, role=x_role, user_identifier=x_user_id)
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


def _require_audit_log_reader(
    state: ApiState,
    *,
    role: str | None,
    user_identifier: str | None,
) -> None:
    if can_read_audit_logs(role):
        return
    record_operation(
        state,
        "audit-logs-access-denied",
        {
            "user_identifier": user_identifier or "anonymous",
            "role": role or "anonymous",
            "status_code": 403,
            "reason": "audit log access requires governance role",
        },
    )
    raise HTTPException(
        status_code=403,
        detail="audit log access requires it-admin or department-head role",
    )
