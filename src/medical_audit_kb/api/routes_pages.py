from __future__ import annotations

from pathlib import Path
from typing import Annotated
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.templating import Jinja2Templates

from medical_audit_kb.api.app import ApiState, PreviewReference, get_api_state, record_operation
from medical_audit_kb.api.postgres_status import load_postgres_index_status, row_count
from medical_audit_kb.domain.constants import SourceCollection
from medical_audit_kb.generation.answer_builder import (
    NoCitedEvidenceError,
    build_citation_backed_answer,
)
from medical_audit_kb.preview.resolver import PreviewResolutionError
from medical_audit_kb.retrieval.filters import RetrievalFilters

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


@router.get("/")
def root_query_page(
    request: Request,
    state: Annotated[ApiState, Depends(get_api_state)],
) -> object:
    return chat_page(request=request, state=state)


@router.get("/pages/query")
def query_page(
    request: Request,
    state: Annotated[ApiState, Depends(get_api_state)],
    question: Annotated[str | None, Query()] = None,
    source_collection: Annotated[list[SourceCollection] | None, Query()] = None,
) -> object:
    selected_collections = tuple(source_collection or ())
    answer_payload, error_message = _run_page_query(
        state,
        question=question,
        selected_collections=selected_collections,
        operation_name="page-query",
    )

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
            "search_backend": _search_backend_context(state),
        },
    )


@router.get("/pages/chat")
def chat_page(
    request: Request,
    state: Annotated[ApiState, Depends(get_api_state)],
    question: Annotated[str | None, Query()] = None,
    source_collection: Annotated[list[SourceCollection] | None, Query()] = None,
) -> object:
    selected_collections = tuple(source_collection or ())
    answer_payload, error_message = _run_page_query(
        state,
        question=question,
        selected_collections=selected_collections,
        operation_name="page-chat",
    )
    return templates.TemplateResponse(
        request,
        "chat.html",
        {
            "question": question or "",
            "source_collections": list(SourceCollection),
            "selected_collections": {item.value for item in selected_collections},
            "answer": answer_payload,
            "answer_quality": _answer_quality_context(answer_payload),
            "follow_up_questions": _follow_up_questions(question, answer_payload),
            "error_message": error_message,
            "query_logs": state.query_logs[-6:],
            "search_backend": _search_backend_context(state),
        },
    )


@router.get("/pages/preview/{chunk_id}")
def preview_page(
    chunk_id: UUID,
    request: Request,
    state: Annotated[ApiState, Depends(get_api_state)],
) -> object:
    reference = state.preview_references.get(chunk_id)
    if reference is None:
        raise HTTPException(status_code=404, detail="preview reference not found")

    try:
        preview = state.preview_resolver.resolve(
            reference.locator,
            citation_text=reference.citation_text,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PreviewResolutionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    record_operation(
        state,
        "page-preview",
        {
            "chunk_id": str(chunk_id),
            "source_path": str(preview.source_path),
            "media_type": preview.media_type,
        },
    )
    return templates.TemplateResponse(
        request,
        "preview.html",
        {
            "chunk_id": str(chunk_id),
            "source_path": str(preview.source_path),
            "media_type": preview.media_type,
            "preview_text": preview.preview_text,
            "locator": preview.locator,
            "highlights": preview.highlights,
            "page_number": preview.page_number,
            "line_start": preview.line_start,
            "line_end": preview.line_end,
            "sheet_name": preview.sheet_name,
            "row_number": preview.row_number,
            "search_backend": _search_backend_context(state),
        },
    )


@router.get("/pages/index-admin")
def index_admin_page(
    request: Request,
    state: Annotated[ApiState, Depends(get_api_state)],
) -> object:
    postgres_status = _postgres_status_context(state)
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
            "search_backend": _search_backend_context(state),
            "postgres_status": postgres_status,
            "evaluation_status": {
                "status": "not-run",
                "description": "发布后验收将在下一阶段接入。",
            },
        },
    )


def _search_backend_context(state: ApiState) -> dict[str, object]:
    return {
        "backend": state.search_backend,
        "ready": state.search_engine is not None,
        "details": state.search_backend_details,
    }


def _run_page_query(
    state: ApiState,
    *,
    question: str | None,
    selected_collections: tuple[SourceCollection, ...],
    operation_name: str,
) -> tuple[dict[str, object] | None, str | None]:
    if not question:
        return None, None
    if state.search_engine is None:
        return None, "检索引擎尚未初始化。"

    results = state.search_engine.search(
        question,
        filters=RetrievalFilters(source_collections=selected_collections),
        top_k=5,
    )
    try:
        answer = build_citation_backed_answer(question, results)
    except NoCitedEvidenceError:
        return None, "没有找到可引用依据。"

    for citation in answer.citations:
        state.preview_references[citation.chunk_id] = PreviewReference(
            locator=citation.locator,
            citation_text=citation.snippet,
        )
    answer_payload: dict[str, object] = {
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
            "retrieved_chunk_ids": [str(citation.chunk_id) for citation in answer.citations],
            "citation_count": len(answer.citations),
        }
    )
    record_operation(
        state,
        operation_name,
        {"question": question, "citation_count": len(answer.citations)},
    )
    return answer_payload, None


def _answer_quality_context(answer: dict[str, object] | None) -> dict[str, object]:
    if answer is None:
        return {
            "status": "waiting",
            "title": "等待问题",
            "description": "提交问题后展示证据覆盖、引用数量和复核风险。",
            "citation_count": 0,
            "group_count": 0,
            "checks": [],
        }
    citations = answer.get("citations")
    basis_groups = answer.get("basis_groups")
    citation_count = len(citations) if isinstance(citations, tuple) else 0
    group_count = len(basis_groups) if isinstance(basis_groups, tuple) else 0
    confidence = str(answer.get("confidence", "low"))
    fallback_used = bool(answer.get("fallback_used"))
    checks = [
        "已返回可点击原文预览" if citation_count else "未返回可点击原文预览",
        "覆盖多个证据分组" if group_count >= 2 else "当前为单一证据分组",
        "生成模型未介入" if fallback_used else "生成模型回答已通过引用标记检查",
    ]
    if confidence == "high":
        status = "strong"
        title = "证据覆盖强"
        description = "引用数量和检索分数满足高置信复核条件。"
    elif confidence == "medium":
        status = "review"
        title = "需要人工复核"
        description = "证据可追溯，但建议打开原文确认适用条件。"
    else:
        status = "weak"
        title = "证据偏弱"
        description = "仅可作为线索，不应直接形成审核结论。"
    return {
        "status": status,
        "title": title,
        "description": description,
        "citation_count": citation_count,
        "group_count": group_count,
        "checks": checks,
    }


def _follow_up_questions(
    question: str | None,
    answer: dict[str, object] | None,
) -> tuple[str, ...]:
    if answer is None:
        return (
            "门诊超量开药应该核对哪些医保审核依据？",
            "医保基金监管中哪些行为属于重点风险？",
            "诊疗项目收费与目录限制如何交叉审核？",
        )
    subject = question or "这个问题"
    return (
        f"{subject} 的适用条件和例外情况是什么？",
        f"{subject} 需要补充核验哪些原始凭证？",
        "把以上依据整理成审核要点清单。",
    )


def _postgres_status_context(state: ApiState) -> dict[str, object]:
    try:
        status = load_postgres_index_status(state.settings.database_url)
    except psycopg.Error as exc:
        return {
            "available": False,
            "error": str(exc),
            "row_counts": {},
            "embedding_sets": [],
            "index_versions": [],
            "source_packages": [],
            "metrics": {
                "document_chunks": 0,
                "chunk_embeddings": 0,
                "failed_files": 0,
                "pending_files": 0,
            },
        }
    return {
        **status,
        "metrics": {
            "document_chunks": row_count(status, "document_chunks"),
            "chunk_embeddings": row_count(status, "chunk_embeddings"),
            "failed_files": row_count(status, "failed_files"),
            "pending_files": row_count(status, "pending_files"),
        },
    }
