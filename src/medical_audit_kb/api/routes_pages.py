from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.templating import Jinja2Templates

from medical_audit_kb.api.app import ApiState, PreviewReference, get_api_state, record_operation
from medical_audit_kb.domain.constants import SourceCollection
from medical_audit_kb.generation.answer_builder import (
    NoCitedEvidenceError,
    build_citation_backed_answer,
)
from medical_audit_kb.retrieval.filters import RetrievalFilters

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


@router.get("/")
def root_query_page(
    request: Request,
    state: Annotated[ApiState, Depends(get_api_state)],
) -> object:
    return query_page(request=request, state=state)


@router.get("/pages/query")
def query_page(
    request: Request,
    state: Annotated[ApiState, Depends(get_api_state)],
    question: Annotated[str | None, Query()] = None,
    source_collection: Annotated[list[SourceCollection] | None, Query()] = None,
) -> object:
    answer_payload: dict[str, object] | None = None
    error_message: str | None = None
    selected_collections = tuple(source_collection or ())

    if question:
        if state.search_engine is None:
            error_message = "检索引擎尚未初始化。"
        else:
            results = state.search_engine.search(
                question,
                filters=RetrievalFilters(source_collections=selected_collections),
                top_k=5,
            )
            try:
                answer = build_citation_backed_answer(question, results)
                for citation in answer.citations:
                    state.preview_references[citation.chunk_id] = PreviewReference(
                        locator=citation.locator,
                        citation_text=citation.snippet,
                    )
                answer_payload = {
                    "answer": answer.answer,
                    "confidence": answer.confidence.value,
                    "fallback_used": answer.fallback_used,
                    "basis_groups": answer.basis_groups,
                    "citations": answer.citations,
                }
                state.query_logs.append(
                    {
                        "user_identifier": "page-user",
                        "role": "auditor",
                        "question": question,
                        "retrieved_chunk_ids": [
                            str(citation.chunk_id) for citation in answer.citations
                        ],
                        "citation_count": len(answer.citations),
                    }
                )
                record_operation(
                    state,
                    "page-query",
                    {"question": question, "citation_count": len(answer.citations)},
                )
            except NoCitedEvidenceError:
                error_message = "没有找到可引用依据。"

    return templates.TemplateResponse(
        request,
        "query.html",
        {
            "question": question or "",
            "source_collections": list(SourceCollection),
            "selected_collections": {item.value for item in selected_collections},
            "answer": answer_payload,
            "error_message": error_message,
            "query_logs": state.query_logs[-5:],
        },
    )


@router.get("/pages/index-admin")
def index_admin_page(
    request: Request,
    state: Annotated[ApiState, Depends(get_api_state)],
) -> object:
    record_operation(
        state,
        "page-index-admin-view",
        {
            "version_count": len(state.index_versions),
            "job_count": len(state.index_jobs),
        },
    )
    return templates.TemplateResponse(
        request,
        "index_admin.html",
        {
            "data_root": str(state.source_root),
            "index_root": str(state.settings.index_root),
            "index_versions": state.index_versions,
            "index_jobs": state.index_jobs,
            "failed_files": state.failed_files,
            "pending_files": state.pending_files,
            "operation_logs": state.operation_logs[-10:],
            "evaluation_status": {
                "status": "not-run",
                "description": "评测集将在 Task 13 接入。",
            },
        },
    )
