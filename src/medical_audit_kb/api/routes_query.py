from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from medical_audit_kb.api.app import ApiState, PreviewReference, get_api_state, record_operation
from medical_audit_kb.domain.constants import SourceCollection
from medical_audit_kb.generation.answer_builder import (
    NoCitedEvidenceError,
    build_citation_backed_answer,
)
from medical_audit_kb.retrieval.filters import RetrievalFilters

router = APIRouter()


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


def parse_chunk_id(chunk_id: str) -> UUID:
    try:
        return UUID(chunk_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="invalid chunk_id") from exc
