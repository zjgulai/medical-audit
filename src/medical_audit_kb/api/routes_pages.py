from __future__ import annotations

import hashlib
import json
import urllib.parse
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

import psycopg
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from medical_audit_kb.api.app import ApiState, PreviewReference, get_api_state, record_operation
from medical_audit_kb.api.audit_finding_store import (
    AuditFindingNotFoundError,
    SqlAlchemyAuditFindingStore,
)
from medical_audit_kb.api.evaluation_reports import (
    latest_evaluation_report,
    list_evaluation_history,
    list_evaluation_report_files,
)
from medical_audit_kb.api.postgres_status import load_postgres_index_status, row_count
from medical_audit_kb.api.review_task_store import (
    InMemoryReviewTaskStore,
    ReviewTaskNotFoundError,
    ReviewTaskStore,
)
from medical_audit_kb.domain.constants import SourceCollection
from medical_audit_kb.generation.answer_builder import (
    AnswerBasisGroup,
    AnswerBasisItem,
    NoCitedEvidenceError,
    build_citation_backed_answer,
)
from medical_audit_kb.generation.citations import Citation
from medical_audit_kb.preview.resolver import PreviewResolutionError
from medical_audit_kb.retrieval.filters import RetrievalFilters

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

DOSSIER_REVIEW_CHECKLIST = (
    "核对引用片段是否完整覆盖问题。",
    "打开原文确认条款上下文。",
    "检查目录、规则、法规版本是否适用。",
    "确认是否还需 HIS 原始凭证补证。",
)

REVIEW_TASK_STATUS_LABELS: dict[str, str] = {
    "pending-review": "待复核",
    "confirmed-violation": "确认违规",
    "rule-issue": "规则问题",
    "data-issue": "数据问题",
    "needs-evidence": "待补证据",
    "not-violation": "未发现违规",
    "closed": "已关闭",
}
RESOLVED_REVIEW_TASK_STATUSES = {
    "confirmed-violation",
    "rule-issue",
    "data-issue",
    "not-violation",
    "closed",
}
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
REVIEW_TASK_ATTACHMENT_DIR = "review-task-attachments"
REVIEW_TASK_ATTACHMENT_MAX_BYTES = 20 * 1024 * 1024

SOURCE_COLLECTION_UI: dict[SourceCollection, dict[str, str]] = {
    SourceCollection.MEDICAL_INSURANCE_LAWS: {
        "title": "法规政策",
        "description": "医保、医疗、药品、基金监管相关法律政策。",
        "audit_hint": "用于判断制度依据和监管边界。",
    },
    SourceCollection.SUPERVISION_RULES_KNOWLEDGE: {
        "title": "监管两库",
        "description": "智能监管规则库、知识库和知识点明细。",
        "audit_hint": "用于定位规则口径和疑点类型。",
    },
    SourceCollection.MEDICAL_INSURANCE_CATALOG: {
        "title": "医保目录",
        "description": "药品、诊疗项目、编码、支付范围和限制条件。",
        "audit_hint": "用于核验目录编码、剂型、支付限制。",
    },
    SourceCollection.RISK_NEGATIVE_LIST: {
        "title": "风险清单",
        "description": "高风险负面清单、案例和风险线索。",
        "audit_hint": "用于辅助排查异常模式。",
    },
}


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
            "source_collection_cards": _source_collection_cards(selected_collections),
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
            "source_collection_cards": _source_collection_cards(selected_collections),
            "selected_collections": {item.value for item in selected_collections},
            "answer": answer_payload,
            "answer_quality": _answer_quality_context(answer_payload),
            "follow_up_questions": _follow_up_questions(question, answer_payload),
            "error_message": error_message,
            "query_logs": state.query_logs[-6:],
            "search_backend": _search_backend_context(state),
        },
    )


@router.get("/pages/chat/export")
def chat_dossier_export(
    request: Request,
    state: Annotated[ApiState, Depends(get_api_state)],
    question: Annotated[str, Query(min_length=1)],
    source_collection: Annotated[list[SourceCollection] | None, Query()] = None,
    format: Annotated[str, Query(pattern="^(json|markdown)$")] = "json",
) -> Response:
    selected_collections = tuple(source_collection or ())
    answer_payload, error_message = _run_page_query(
        state,
        question=question,
        selected_collections=selected_collections,
        operation_name="page-chat-export-query",
    )
    if error_message is not None or answer_payload is None:
        status_code = 409 if state.search_engine is None else 404
        raise HTTPException(status_code=status_code, detail=error_message or "无法生成审计底稿。")

    dossier = _audit_dossier_payload(
        question=question,
        answer=answer_payload,
        selected_collections=selected_collections,
        request=request,
    )
    record_operation(
        state,
        "chat-dossier-export",
        {
            "question": question,
            "format": format,
            "citation_count": dossier["citation_count"],
        },
    )
    if format == "markdown":
        return Response(
            content=_render_audit_dossier_markdown(dossier),
            media_type="text/markdown; charset=utf-8",
            headers=_download_headers("auditscope-dossier.md"),
        )
    return Response(
        content=json.dumps(dossier, ensure_ascii=False, indent=2) + "\n",
        media_type="application/json",
        headers=_download_headers("auditscope-dossier.json"),
    )


@router.get("/pages/review-tasks")
def review_tasks_page(
    request: Request,
    state: Annotated[ApiState, Depends(get_api_state)],
) -> object:
    review_tasks = _review_tasks(state)
    record_operation(
        state,
        "page-review-tasks-view",
        {"task_count": len(review_tasks)},
    )
    return templates.TemplateResponse(
        request,
        "review_tasks.html",
        {
            "review_tasks": tuple(_review_task_page_item(task) for task in reversed(review_tasks)),
            "review_task_stats": _review_task_stats(review_tasks),
            "review_status_options": REVIEW_TASK_STATUS_LABELS,
            "workpaper_status_options": WORKPAPER_STATUS_LABELS,
            "owner_signoff_status_options": OWNER_SIGNOFF_STATUS_LABELS,
            "search_backend": _search_backend_context(state),
        },
    )


@router.get("/pages/audit-findings")
def audit_findings_page(
    request: Request,
    state: Annotated[ApiState, Depends(get_api_state)],
    review_status: Annotated[str | None, Query()] = None,
) -> object:
    if review_status is not None and review_status not in REVIEW_TASK_STATUS_LABELS:
        raise HTTPException(status_code=422, detail=f"unsupported review_status: {review_status}")
    findings = _audit_findings(state, review_status=review_status)
    record_operation(
        state,
        "page-audit-findings-view",
        {"finding_count": len(findings), "review_status": review_status or "all"},
    )
    return templates.TemplateResponse(
        request,
        "audit_findings.html",
        {
            "audit_findings": findings,
            "audit_finding_stats": _audit_finding_stats(findings),
            "review_status_options": REVIEW_TASK_STATUS_LABELS,
            "selected_review_status": review_status or "",
            "search_backend": _search_backend_context(state),
        },
    )


@router.get("/audit-findings/{finding_key}/export")
def audit_finding_export(
    finding_key: str,
    state: Annotated[ApiState, Depends(get_api_state)],
) -> Response:
    finding = _audit_finding_by_key(state, finding_key)
    payload = _audit_finding_export_payload(finding)
    record_operation(
        state,
        "audit-finding-export",
        {"finding_key": finding_key},
    )
    return Response(
        content=json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        media_type="application/json",
        headers=_download_headers(f"{finding_key}.json"),
    )


@router.post("/pages/audit-findings/{finding_key}/review-task")
def create_audit_finding_review_task_page(
    finding_key: str,
    request: Request,
    state: Annotated[ApiState, Depends(get_api_state)],
) -> RedirectResponse:
    finding = _audit_finding_by_key(state, finding_key)
    task = _create_review_task_from_finding(
        state=state,
        request=request,
        finding=finding,
    )
    try:
        _audit_finding_store(state).link_review_task(finding_key, str(task["task_id"]))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    record_operation(
        state,
        "audit-finding-review-task-create",
        {"finding_key": finding_key, "task_id": str(task["task_id"])},
    )
    return RedirectResponse("/pages/review-tasks", status_code=303)


@router.post("/pages/review-tasks/create")
async def create_review_task_page(
    request: Request,
    state: Annotated[ApiState, Depends(get_api_state)],
) -> RedirectResponse:
    form = await _urlencoded_form(request)
    question = _form_required_str(form, "question")
    selected_collections = _source_collections_from_form(form)
    answer_payload, error_message = _run_page_query(
        state,
        question=question,
        selected_collections=selected_collections,
        operation_name="review-task-create-query",
    )
    if error_message is not None or answer_payload is None:
        status_code = 409 if state.search_engine is None else 404
        raise HTTPException(status_code=status_code, detail=error_message or "无法创建复核任务。")

    task = _create_review_task(
        state=state,
        request=request,
        question=question,
        selected_collections=selected_collections,
        answer=answer_payload,
    )
    record_operation(
        state,
        "review-task-create",
        {
            "task_id": task["task_id"],
            "question": question,
            "citation_count": task["citation_count"],
        },
    )
    return RedirectResponse("/pages/review-tasks", status_code=303)


@router.post("/pages/review-tasks/{task_id}/status")
async def update_review_task_status_page(
    task_id: str,
    request: Request,
    state: Annotated[ApiState, Depends(get_api_state)],
) -> RedirectResponse:
    form = await _urlencoded_form(request)
    existing_task = _review_task_by_id(state, task_id)
    status = _form_required_str(form, "status")
    if status not in REVIEW_TASK_STATUS_LABELS:
        raise HTTPException(status_code=422, detail=f"unsupported review task status: {status}")

    _update_review_task(
        state,
        task_id,
        {
            "status": status,
            "status_label": REVIEW_TASK_STATUS_LABELS[status],
            "assigned_to": _form_optional_str(form, "assigned_to"),
            "reviewer_note": _form_optional_str(form, "reviewer_note"),
            "conclusion": _form_optional_str(form, "conclusion"),
            "dossier": _review_task_dossier_from_form(existing_task, form),
            "updated_at": _utc_now_iso(),
        },
    )
    record_operation(
        state,
        "review-task-status-update",
        {"task_id": task_id, "status": status},
    )
    return RedirectResponse("/pages/review-tasks", status_code=303)


@router.post("/pages/review-tasks/{task_id}/attachments")
async def upload_review_task_attachment_page(
    task_id: str,
    state: Annotated[ApiState, Depends(get_api_state)],
    attachment_file: Annotated[UploadFile, File()],
    attachment_title: Annotated[str | None, Form()] = None,
    attachment_note: Annotated[str | None, Form()] = None,
) -> RedirectResponse:
    task = _review_task_by_id(state, task_id)
    dossier = _with_review_task_governance_defaults(_dict_value(task.get("dossier")))
    attachment = await _archive_review_task_attachment(
        state=state,
        task_id=task_id,
        upload=attachment_file,
        title=attachment_title,
        note=attachment_note,
    )
    dossier["attachments"] = [*_attachment_items(dossier), attachment]
    _update_review_task(
        state,
        task_id,
        {
            "dossier": dossier,
            "updated_at": _utc_now_iso(),
        },
    )
    record_operation(
        state,
        "review-task-attachment-upload",
        {
            "task_id": task_id,
            "attachment_id": attachment["attachment_id"],
            "byte_size": attachment["byte_size"],
            "sha256": attachment["sha256"],
        },
    )
    return RedirectResponse("/pages/review-tasks", status_code=303)


@router.get("/review-tasks/{task_id}/attachments/{attachment_id}/download")
def download_review_task_attachment(
    task_id: str,
    attachment_id: str,
    state: Annotated[ApiState, Depends(get_api_state)],
) -> FileResponse:
    task = _review_task_by_id(state, task_id)
    dossier = _with_review_task_governance_defaults(_dict_value(task.get("dossier")))
    attachment = _review_task_attachment_by_id(dossier, attachment_id)
    if attachment is None:
        raise HTTPException(status_code=404, detail="review task attachment not found")
    storage_path = str(attachment.get("storage_path", "")).strip()
    if not storage_path:
        raise HTTPException(status_code=404, detail="review task attachment file not archived")
    file_path = _resolve_review_task_attachment_path(state, storage_path)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="review task attachment file not found")
    record_operation(
        state,
        "review-task-attachment-download",
        {"task_id": task_id, "attachment_id": attachment_id},
    )
    return FileResponse(
        path=file_path,
        media_type=str(attachment.get("media_type") or "application/octet-stream"),
        filename=str(
            attachment.get("original_filename") or attachment.get("title") or file_path.name
        ),
    )


@router.get("/review-tasks/{task_id}/export")
def review_task_export(
    task_id: str,
    state: Annotated[ApiState, Depends(get_api_state)],
    format: Annotated[str, Query(pattern="^(json|markdown)$")] = "json",
) -> Response:
    task = _review_task_by_id(state, task_id)
    payload = _review_task_export_payload(task)
    record_operation(
        state,
        "review-task-export",
        {"task_id": task_id, "format": format},
    )
    if format == "markdown":
        return Response(
            content=_render_review_task_markdown(payload),
            media_type="text/markdown; charset=utf-8",
            headers=_download_headers(f"{task_id}.md"),
        )
    return Response(
        content=json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        media_type="application/json",
        headers=_download_headers(f"{task_id}.json"),
    )


@router.get("/review-tasks/{task_id}/report-draft")
def review_task_report_draft_export(
    task_id: str,
    state: Annotated[ApiState, Depends(get_api_state)],
    format: Annotated[str, Query(pattern="^(json|markdown)$")] = "markdown",
) -> Response:
    task = _review_task_by_id(state, task_id)
    payload = _review_task_report_draft_payload(task)
    record_operation(
        state,
        "review-task-report-draft-export",
        {"task_id": task_id, "format": format},
    )
    if format == "json":
        return Response(
            content=json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            media_type="application/json",
            headers=_download_headers(f"{task_id}-report-draft.json"),
        )
    return Response(
        content=_render_review_task_report_draft_markdown(payload),
        media_type="text/markdown; charset=utf-8",
        headers=_download_headers(f"{task_id}-report-draft.md"),
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
            "evaluation_status": _evaluation_status_context(state),
            "evaluation_history": _evaluation_history_context(state, postgres_status),
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


def _audit_dossier_payload(
    *,
    question: str,
    answer: dict[str, object],
    selected_collections: tuple[SourceCollection, ...],
    request: Request,
) -> dict[str, object]:
    quality = _answer_quality_context(answer)
    citations = _answer_citations(answer)
    basis_groups = _answer_basis_groups(answer)
    return {
        "format": "audit-dossier-v1",
        "generated_at": _utc_now_iso(),
        "question": question,
        "answer": str(answer.get("answer", "")),
        "confidence": str(answer.get("confidence", "low")),
        "confidence_label": str(quality["confidence_label"]),
        "fallback_used": bool(answer.get("fallback_used")),
        "fallback_label": str(quality["fallback_label"]),
        "review_gate": str(quality["review_gate"]),
        "review_notice": "该导出为审计线索和人工复核底稿，不替代正式审计结论。",
        "review_checklist": list(DOSSIER_REVIEW_CHECKLIST),
        "source_collections": [collection.value for collection in selected_collections],
        "citation_count": len(citations),
        "basis_group_count": len(basis_groups),
        "basis_groups": [
            _basis_group_export_payload(group, request=request) for group in basis_groups
        ],
        "citations": [
            _citation_export_payload(citation, request=request) for citation in citations
        ],
    }


def _answer_citations(answer: dict[str, object]) -> tuple[Citation, ...]:
    value = answer.get("citations")
    if isinstance(value, tuple):
        return tuple(item for item in value if isinstance(item, Citation))
    return ()


def _answer_basis_groups(answer: dict[str, object]) -> tuple[AnswerBasisGroup, ...]:
    value = answer.get("basis_groups")
    if isinstance(value, tuple):
        return tuple(item for item in value if isinstance(item, AnswerBasisGroup))
    return ()


def _basis_group_export_payload(
    group: AnswerBasisGroup,
    *,
    request: Request,
) -> dict[str, object]:
    return {
        "evidence_type": str(group.evidence_type),
        "title": group.title,
        "items": [_basis_item_export_payload(item, request=request) for item in group.items],
    }


def _basis_item_export_payload(
    item: AnswerBasisItem,
    *,
    request: Request,
) -> dict[str, object]:
    return {
        "citation_id": item.citation_id,
        "chunk_id": str(item.chunk_id),
        "snippet": item.snippet,
        "preview_url": str(request.url_for("preview_page", chunk_id=item.chunk_id)),
        "locator": _json_safe(item.locator),
        "index_version_key": item.index_version_key,
        "source_package_version_key": item.source_package_version_key,
    }


def _citation_export_payload(
    citation: Citation,
    *,
    request: Request,
) -> dict[str, object]:
    return {
        "citation_id": citation.citation_id,
        "marker": citation.marker,
        "evidence_type": str(citation.evidence_type),
        "source_collection": str(citation.source_collection),
        "chunk_id": str(citation.chunk_id),
        "snippet": citation.snippet,
        "preview_url": str(request.url_for("preview_page", chunk_id=citation.chunk_id)),
        "locator": _json_safe(citation.locator),
        "index_version_key": citation.index_version_key,
        "source_package_version_key": citation.source_package_version_key,
        "score": citation.score,
        "metadata": _json_safe(citation.metadata),
    }


def _render_audit_dossier_markdown(dossier: dict[str, object]) -> str:
    lines = [
        "# AuditScope 审计底稿导出",
        "",
        f"- 生成时间：{dossier['generated_at']}",
        f"- 问题：{dossier['question']}",
        f"- 置信度：{dossier['confidence_label']} ({dossier['confidence']})",
        f"- 生成方式：{dossier['fallback_label']}",
        f"- 复核门禁：{dossier['review_gate']}",
        f"- 引用数量：{dossier['citation_count']}",
        "",
        f"> {dossier['review_notice']}",
        "",
        "## 人工复核清单",
        "",
    ]
    lines.extend(f"- {item}" for item in _string_list(dossier["review_checklist"]))
    lines.extend(["", "## 可追溯回答", ""])
    lines.extend(str(dossier["answer"]).splitlines())
    lines.extend(["", "## 证据分组", ""])
    for group in _dict_list(dossier["basis_groups"]):
        lines.extend([f"### {group['title']}", ""])
        for item in _dict_list(group["items"]):
            lines.extend(
                [
                    f"- [{item['citation_id']}] {item['snippet']}",
                    f"  - chunk: `{item['chunk_id']}`",
                    f"  - index: `{item['index_version_key']}`",
                    f"  - package: `{item['source_package_version_key']}`",
                    f"  - 原文链接: {item['preview_url']}",
                ]
            )
        lines.append("")
    lines.extend(["## 完整引用", ""])
    for citation in _dict_list(dossier["citations"]):
        lines.extend(
            [
                f"### {citation['marker']}",
                "",
                f"- 来源：{citation['source_collection']} / {citation['evidence_type']}",
                f"- chunk: `{citation['chunk_id']}`",
                f"- index: `{citation['index_version_key']}`",
                f"- package: `{citation['source_package_version_key']}`",
                f"- score: `{citation['score']}`",
                f"- 原文链接: {citation['preview_url']}",
                "",
                str(citation["snippet"]),
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _string_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value)


def _dict_list(value: object) -> tuple[dict[str, object], ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, dict))


def _dict_value(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return dict(value)
    return {}


def _json_safe(value: object) -> object:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str):
        return [_json_safe(item) for item in value]
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return str(value)


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _download_headers(filename: str) -> dict[str, str]:
    return {"Content-Disposition": f'attachment; filename="{filename}"'}


def _create_review_task(
    *,
    state: ApiState,
    request: Request,
    question: str,
    selected_collections: tuple[SourceCollection, ...],
    answer: dict[str, object],
) -> dict[str, object]:
    now = _utc_now_iso()
    dossier = _audit_dossier_payload(
        question=question,
        answer=answer,
        selected_collections=selected_collections,
        request=request,
    )
    task = {
        "task_id": _review_task_store(state).next_task_id(),
        "created_at": now,
        "updated_at": now,
        "status": "pending-review",
        "status_label": REVIEW_TASK_STATUS_LABELS["pending-review"],
        "question": question,
        "citation_count": dossier["citation_count"],
        "review_gate": dossier["review_gate"],
        "confidence_label": dossier["confidence_label"],
        "fallback_label": dossier["fallback_label"],
        "source": "chat-dossier",
        "assigned_to": "",
        "reviewer_note": "",
        "conclusion": "",
        "dossier": _with_review_task_governance_defaults(dossier),
    }
    return _review_task_store(state).add_task(task)


def _create_review_task_from_finding(
    *,
    state: ApiState,
    request: Request,
    finding: dict[str, object],
) -> dict[str, object]:
    now = _utc_now_iso()
    dossier = _audit_finding_dossier_payload(finding=finding, request=request)
    task = {
        "task_id": _review_task_store(state).next_task_id(),
        "created_at": now,
        "updated_at": now,
        "status": "pending-review",
        "status_label": REVIEW_TASK_STATUS_LABELS["pending-review"],
        "question": f"复核疑点 {finding['finding_key']}：{finding['finding_type']}",
        "citation_count": len(_dict_list(finding.get("evidence_items", []))),
        "review_gate": "疑点已绑定规则版本和计算过程，进入人工复核。",
        "confidence_label": "中",
        "fallback_label": "规则命中",
        "source": "audit-finding",
        "assigned_to": "",
        "reviewer_note": "",
        "conclusion": "",
        "dossier": _with_review_task_governance_defaults(dossier),
    }
    return _review_task_store(state).add_task(task)


def _review_task_by_id(state: ApiState, task_id: str) -> dict[str, object]:
    try:
        return _review_task_store(state).get_task(task_id)
    except ReviewTaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail="review task not found") from exc


def _review_tasks(state: ApiState) -> list[dict[str, object]]:
    return _review_task_store(state).list_tasks()


def _update_review_task(
    state: ApiState,
    task_id: str,
    values: dict[str, object],
) -> dict[str, object]:
    try:
        return _review_task_store(state).update_task(task_id, values)
    except ReviewTaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail="review task not found") from exc


def _review_task_store(state: ApiState) -> ReviewTaskStore:
    if state.review_task_store is None:
        state.review_task_store = InMemoryReviewTaskStore()
    return state.review_task_store


def _audit_findings(
    state: ApiState,
    *,
    review_status: str | None = None,
) -> list[dict[str, object]]:
    return _audit_finding_store(state).list_findings(review_status=review_status)


def _audit_finding_by_key(state: ApiState, finding_key: str) -> dict[str, object]:
    try:
        return _audit_finding_store(state).get_finding(finding_key)
    except AuditFindingNotFoundError as exc:
        raise HTTPException(status_code=404, detail="audit finding not found") from exc


def _audit_finding_store(state: ApiState) -> SqlAlchemyAuditFindingStore:
    if state.audit_finding_store is None:
        state.audit_finding_store = SqlAlchemyAuditFindingStore(state.settings.database_url)
    return state.audit_finding_store


def _review_task_stats(tasks: list[dict[str, object]]) -> dict[str, object]:
    status_counts = {status: 0 for status in REVIEW_TASK_STATUS_LABELS}
    for task in tasks:
        status = str(task.get("status", "pending-review"))
        if status in status_counts:
            status_counts[status] += 1
    open_count = sum(
        count
        for status, count in status_counts.items()
        if status not in {"closed", "confirmed-violation", "not-violation"}
    )
    return {
        "total": len(tasks),
        "open": open_count,
        "closed": status_counts["closed"],
        "confirmed_violation": status_counts["confirmed-violation"],
        "needs_evidence": status_counts["needs-evidence"],
        "report_ready": sum(
            1 for task in tasks if _review_task_report_gate_context(task)["ready_for_report"]
        ),
        "status_counts": status_counts,
    }


def _review_task_export_payload(task: dict[str, object]) -> dict[str, object]:
    return {
        "format": "review-task-v1",
        "task_id": task["task_id"],
        "created_at": task["created_at"],
        "updated_at": task["updated_at"],
        "status": task["status"],
        "status_label": task["status_label"],
        "question": task["question"],
        "citation_count": task["citation_count"],
        "review_gate": task["review_gate"],
        "confidence_label": task["confidence_label"],
        "fallback_label": task["fallback_label"],
        "assigned_to": task.get("assigned_to"),
        "reviewer_note": task["reviewer_note"],
        "conclusion": task["conclusion"],
        "source": task.get("source", "chat-dossier"),
        "report_gate": _review_task_report_gate_context(task),
        "dossier": task["dossier"],
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


def _audit_finding_export_payload(finding: dict[str, object]) -> dict[str, object]:
    return {
        "format": "audit-finding-v1",
        "exported_at": _utc_now_iso(),
        **finding,
    }


def _audit_finding_dossier_payload(
    *,
    finding: dict[str, object],
    request: Request,
) -> dict[str, object]:
    return {
        "format": "audit-finding-dossier-v1",
        "generated_at": _utc_now_iso(),
        "finding_key": finding["finding_key"],
        "finding_type": finding["finding_type"],
        "severity": finding["severity"],
        "status": finding["status"],
        "review_status": finding["review_status"],
        "audit_task_key": finding.get("audit_task_key"),
        "audit_run_key": finding.get("audit_run_key"),
        "rule_key": finding.get("rule_key"),
        "rule_version_key": finding.get("rule_version_key"),
        "source_record_locator": finding["source_record_locator"],
        "calculation_trace": finding["calculation_trace"],
        "evidence_items": finding.get("evidence_items", []),
        "finding_export_url": str(
            request.url_for("audit_finding_export", finding_key=str(finding["finding_key"]))
        ),
        "review_notice": "该任务来源于结构化规则疑点，进入报告前必须完成人工复核。",
    }


def _render_review_task_markdown(payload: dict[str, object]) -> str:
    dossier = payload.get("dossier")
    if not isinstance(dossier, dict):
        dossier = {}
    report_gate = _dict_value(payload.get("report_gate"))
    report_ready_label = (
        "可进入报告草稿" if report_gate.get("ready_for_report") else "不得进入报告草稿"
    )
    workpaper = _dict_value(dossier.get("workpaper"))
    owner_signoff = _dict_value(dossier.get("owner_signoff"))
    report_draft = _report_draft_context(dossier, payload)
    attachments = _attachment_items(dossier)
    lines = [
        "# AuditScope 复核任务记录",
        "",
        f"- 任务编号：{payload['task_id']}",
        f"- 创建时间：{payload['created_at']}",
        f"- 更新时间：{payload['updated_at']}",
        f"- 状态：{payload['status_label']} ({payload['status']})",
        f"- 承办人：{payload.get('assigned_to') or '未指定'}",
        f"- 问题：{payload['question']}",
        f"- 引用数量：{payload['citation_count']}",
        f"- 复核门禁：{payload['review_gate']}",
        f"- 报告准备度：{report_ready_label}",
        f"- 复核意见：{payload['reviewer_note'] or '未填写'}",
        f"- 复核结论：{payload['conclusion'] or '未填写'}",
        f"- 底稿状态：{workpaper.get('status_label', '未建底稿')}",
        f"- 底稿编号：{workpaper.get('workpaper_id') or '未填写'}",
        f"- 负责人确认：{owner_signoff.get('status_label', '未提交确认')}",
        f"- 确认人：{owner_signoff.get('confirmed_by') or '未填写'}",
        f"- 附件数量：{len(attachments)}",
        f"- 报告标题：{report_draft['title']}",
        "",
        "## 报告门禁检查",
        "",
    ]
    for check in _dict_list(report_gate.get("checks")):
        lines.append(
            f"- [{'x' if check.get('pass') else ' '}] {check.get('label')}: {check.get('message')}"
        )
    lines.extend(
        [
            "",
            "## 附件清单",
            "",
        ]
    )
    if attachments:
        for attachment in attachments:
            lines.append(
                f"- {attachment['title']} | {attachment.get('locator') or '未填写位置'}"
                f" | {attachment.get('note') or '无说明'}"
            )
    else:
        lines.append("- 未登记附件。")
    lines.extend(
        [
            "",
            "## 报告草稿字段",
            "",
            f"- 报告标题：{report_draft['title']}",
            f"- 摘要：{report_draft['summary']}",
            f"- 整改建议：{report_draft['rectification_request']}",
            "",
            "## 底稿",
            "",
            _render_audit_dossier_markdown(dossier),
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _review_task_page_item(task: dict[str, object]) -> dict[str, object]:
    dossier = _with_review_task_governance_defaults(_dict_value(task.get("dossier")))
    return {
        **task,
        "assigned_to": str(task.get("assigned_to") or ""),
        "dossier": dossier,
        "workpaper": _workpaper_context(dossier),
        "owner_signoff": _owner_signoff_context(dossier),
        "attachments": _attachment_items_for_page(str(task.get("task_id", "")), dossier),
        "attachment_manifest": _attachment_manifest_text(dossier),
        "report_draft": _report_draft_context(dossier, task),
        "report_gate": _review_task_report_gate_context({**task, "dossier": dossier}),
    }


def _review_task_report_gate_context(task: dict[str, object]) -> dict[str, object]:
    status = str(task.get("status", "pending-review"))
    dossier = _with_review_task_governance_defaults(_dict_value(task.get("dossier")))
    workpaper = _workpaper_context(dossier)
    owner_signoff = _owner_signoff_context(dossier)
    attachment_count = len(_attachment_items(dossier))
    reviewer_note = str(task.get("reviewer_note", "")).strip()
    conclusion = str(task.get("conclusion", "")).strip()
    requires_workpaper = status == "confirmed-violation"
    checks = [
        {
            "key": "review-status",
            "label": "复核状态闭合",
            "pass": status in RESOLVED_REVIEW_TASK_STATUSES,
            "message": REVIEW_TASK_STATUS_LABELS.get(status, status),
        },
        {
            "key": "review-note",
            "label": "复核意见完整",
            "pass": bool(reviewer_note),
            "message": "已填写复核意见" if reviewer_note else "缺少复核意见",
        },
        {
            "key": "review-conclusion",
            "label": "复核结论完整",
            "pass": bool(conclusion),
            "message": "已填写复核结论" if conclusion else "缺少复核结论",
        },
        {
            "key": "workpaper",
            "label": "确认违规底稿",
            "pass": (not requires_workpaper) or workpaper["status"] == "ready",
            "message": str(workpaper["status_label"]),
        },
        {
            "key": "owner-signoff",
            "label": "负责人确认",
            "pass": bool(owner_signoff["approved"]),
            "message": str(owner_signoff["status_label"]),
        },
        {
            "key": "attachments",
            "label": "附件登记",
            "pass": (not requires_workpaper) or attachment_count > 0,
            "message": f"已登记 {attachment_count} 条附件" if attachment_count else "未登记附件",
        },
    ]
    return {
        "ready_for_report": all(bool(check["pass"]) for check in checks),
        "status_label": "可进入报告草稿"
        if all(bool(check["pass"]) for check in checks)
        else "不得进入报告草稿",
        "checks": checks,
    }


def _review_task_dossier_from_form(
    task: dict[str, object],
    form: Mapping[str, Sequence[str]],
) -> dict[str, object]:
    dossier = _with_review_task_governance_defaults(_dict_value(task.get("dossier")))
    workpaper_status = _form_optional_str(form, "workpaper_status") or str(
        _dict_value(dossier.get("workpaper")).get("status", "missing")
    )
    owner_status = _form_optional_str(form, "owner_signoff_status") or str(
        _dict_value(dossier.get("owner_signoff")).get("status", "not-requested")
    )
    if workpaper_status not in WORKPAPER_STATUS_LABELS:
        raise HTTPException(
            status_code=422, detail=f"unsupported workpaper_status: {workpaper_status}"
        )
    if owner_status not in OWNER_SIGNOFF_STATUS_LABELS:
        raise HTTPException(
            status_code=422,
            detail=f"unsupported owner_signoff_status: {owner_status}",
        )
    dossier["workpaper"] = {
        "status": workpaper_status,
        "status_label": WORKPAPER_STATUS_LABELS[workpaper_status],
        "workpaper_id": _form_optional_str(form, "workpaper_id"),
        "note": _form_optional_str(form, "workpaper_note"),
    }
    dossier["owner_signoff"] = {
        "status": owner_status,
        "status_label": OWNER_SIGNOFF_STATUS_LABELS[owner_status],
        "confirmed_by": _form_optional_str(form, "owner_confirmed_by"),
        "confirmed_at": _form_optional_str(form, "owner_confirmed_at"),
    }
    dossier["attachments"] = [
        *_parse_attachment_manifest(_form_optional_str(form, "attachment_manifest")),
        *_uploaded_attachment_items(dossier),
    ]
    dossier["report_draft"] = {
        "title": _form_optional_str(form, "report_title"),
        "summary": _form_optional_str(form, "report_summary"),
        "rectification_request": _form_optional_str(form, "rectification_request"),
        "updated_at": _utc_now_iso(),
    }
    dossier["report_gate"] = {
        "source": "review-task-page",
        "updated_at": _utc_now_iso(),
    }
    return dossier


def _with_review_task_governance_defaults(dossier: dict[str, object]) -> dict[str, object]:
    normalized = dict(dossier)
    workpaper = _dict_value(normalized.get("workpaper"))
    workpaper_status = str(workpaper.get("status", "missing"))
    if workpaper_status not in WORKPAPER_STATUS_LABELS:
        workpaper_status = "missing"
    normalized["workpaper"] = {
        "status": workpaper_status,
        "status_label": WORKPAPER_STATUS_LABELS[workpaper_status],
        "workpaper_id": str(workpaper.get("workpaper_id", "")),
        "note": str(workpaper.get("note", "")),
    }
    owner_signoff = _dict_value(normalized.get("owner_signoff"))
    owner_status = str(owner_signoff.get("status", "not-requested"))
    if owner_status not in OWNER_SIGNOFF_STATUS_LABELS:
        owner_status = "not-requested"
    normalized["owner_signoff"] = {
        "status": owner_status,
        "status_label": OWNER_SIGNOFF_STATUS_LABELS[owner_status],
        "confirmed_by": str(owner_signoff.get("confirmed_by", "")),
        "confirmed_at": str(owner_signoff.get("confirmed_at", "")),
    }
    normalized["attachments"] = list(_attachment_items(normalized))
    report_draft = _dict_value(normalized.get("report_draft"))
    normalized["report_draft"] = {
        "title": str(report_draft.get("title", "")).strip(),
        "summary": str(report_draft.get("summary", "")).strip(),
        "rectification_request": str(report_draft.get("rectification_request", "")).strip(),
        "updated_at": str(report_draft.get("updated_at", "")).strip(),
    }
    normalized.setdefault("report_gate", {"source": "review-task-page"})
    return normalized


def _workpaper_context(dossier: dict[str, object]) -> dict[str, object]:
    workpaper = _dict_value(dossier.get("workpaper"))
    status = str(workpaper.get("status", "missing"))
    if status not in WORKPAPER_STATUS_LABELS:
        status = "missing"
    return {
        "status": status,
        "status_label": WORKPAPER_STATUS_LABELS[status],
        "workpaper_id": str(workpaper.get("workpaper_id", "")),
        "note": str(workpaper.get("note", "")),
    }


def _owner_signoff_context(dossier: dict[str, object]) -> dict[str, object]:
    owner_signoff = _dict_value(dossier.get("owner_signoff"))
    status = str(owner_signoff.get("status", "not-requested"))
    if status not in OWNER_SIGNOFF_STATUS_LABELS:
        status = "not-requested"
    confirmed_by = str(owner_signoff.get("confirmed_by", "")).strip()
    confirmed_at = str(owner_signoff.get("confirmed_at", "")).strip()
    return {
        "status": status,
        "status_label": OWNER_SIGNOFF_STATUS_LABELS[status],
        "confirmed_by": confirmed_by,
        "confirmed_at": confirmed_at,
        "approved": status == "approved" and bool(confirmed_by) and bool(confirmed_at),
    }


def _attachment_items(dossier: dict[str, object]) -> tuple[dict[str, object], ...]:
    attachments: list[dict[str, object]] = []
    for index, item in enumerate(_dict_list(dossier.get("attachments")), start=1):
        title = str(item.get("title", "")).strip()
        if not title:
            continue
        attachment: dict[str, object] = {
            "attachment_id": str(item.get("attachment_id") or f"attachment-{index:03d}"),
            "title": title,
            "locator": str(item.get("locator", "")).strip(),
            "note": str(item.get("note", "")).strip(),
            "status": str(item.get("status", "registered") or "registered"),
        }
        for key in (
            "original_filename",
            "media_type",
            "sha256",
            "storage_path",
            "uploaded_at",
        ):
            value = str(item.get(key, "")).strip()
            if value:
                attachment[key] = value
        byte_size = item.get("byte_size")
        if isinstance(byte_size, int) and byte_size >= 0:
            attachment["byte_size"] = byte_size
        attachments.append(attachment)
    return tuple(attachments)


def _uploaded_attachment_items(dossier: dict[str, object]) -> tuple[dict[str, object], ...]:
    return tuple(
        item for item in _attachment_items(dossier) if str(item.get("storage_path", "")).strip()
    )


def _attachment_items_for_page(
    task_id: str,
    dossier: dict[str, object],
) -> tuple[dict[str, object], ...]:
    attachments: list[dict[str, object]] = []
    for item in _attachment_items(dossier):
        attachment = dict(item)
        if str(attachment.get("storage_path", "")).strip():
            attachment["download_url"] = (
                f"/review-tasks/{urllib.parse.quote(task_id)}/attachments/"
                f"{urllib.parse.quote(str(attachment['attachment_id']))}/download"
            )
        attachments.append(attachment)
    return tuple(attachments)


def _attachment_manifest_text(dossier: dict[str, object]) -> str:
    lines = []
    for item in _attachment_items(dossier):
        if str(item.get("storage_path", "")).strip():
            continue
        lines.append(f"{item['title']} | {item['locator']} | {item['note']}".rstrip(" |"))
    return "\n".join(lines)


def _parse_attachment_manifest(raw_manifest: str) -> list[dict[str, object]]:
    attachments: list[dict[str, object]] = []
    for index, line in enumerate(raw_manifest.splitlines(), start=1):
        normalized = line.strip()
        if not normalized:
            continue
        parts = [part.strip() for part in normalized.split("|")]
        if not parts[0]:
            continue
        attachments.append(
            {
                "attachment_id": f"attachment-{index:03d}",
                "title": parts[0],
                "locator": parts[1] if len(parts) >= 2 else "",
                "note": parts[2] if len(parts) >= 3 else "",
                "status": "registered",
            }
        )
    return attachments


async def _archive_review_task_attachment(
    *,
    state: ApiState,
    task_id: str,
    upload: UploadFile,
    title: str | None,
    note: str | None,
) -> dict[str, object]:
    content = await upload.read()
    if not content:
        raise HTTPException(status_code=422, detail="attachment file is empty")
    if len(content) > REVIEW_TASK_ATTACHMENT_MAX_BYTES:
        raise HTTPException(status_code=413, detail="attachment file is too large")

    digest = hashlib.sha256(content).hexdigest()
    original_filename = Path(upload.filename or "attachment").name
    attachment_id = f"attachment-{uuid4().hex[:12]}"
    storage_root = _review_task_attachment_root(state, task_id)
    storage_root.mkdir(parents=True, exist_ok=True)
    storage_filename = f"{attachment_id}{_safe_attachment_suffix(original_filename)}"
    file_path = storage_root / storage_filename
    file_path.write_bytes(content)
    storage_path = file_path.relative_to(state.settings.index_root).as_posix()
    display_title = (title or "").strip() or original_filename or attachment_id
    return {
        "attachment_id": attachment_id,
        "title": display_title,
        "locator": f"uploaded://{task_id}/{attachment_id}",
        "note": (note or "").strip(),
        "status": "uploaded",
        "original_filename": original_filename,
        "media_type": upload.content_type or "application/octet-stream",
        "byte_size": len(content),
        "sha256": digest,
        "storage_path": storage_path,
        "uploaded_at": _utc_now_iso(),
    }


def _review_task_attachment_root(state: ApiState, task_id: str) -> Path:
    return state.settings.index_root / REVIEW_TASK_ATTACHMENT_DIR / _safe_path_segment(task_id)


def _resolve_review_task_attachment_path(state: ApiState, storage_path: str) -> Path:
    archive_root = (state.settings.index_root / REVIEW_TASK_ATTACHMENT_DIR).resolve()
    file_path = (state.settings.index_root / storage_path).resolve()
    try:
        file_path.relative_to(archive_root)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="review task attachment path invalid") from exc
    return file_path


def _review_task_attachment_by_id(
    dossier: dict[str, object],
    attachment_id: str,
) -> dict[str, object] | None:
    for attachment in _attachment_items(dossier):
        if attachment.get("attachment_id") == attachment_id:
            return attachment
    return None


def _safe_attachment_suffix(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if not suffix or len(suffix) > 16:
        return ""
    if all(char.isalnum() or char == "." for char in suffix):
        return suffix
    return ""


def _safe_path_segment(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value)


def _report_draft_context(
    dossier: dict[str, object],
    task: dict[str, object],
) -> dict[str, object]:
    report_draft = _dict_value(dossier.get("report_draft"))
    title = str(report_draft.get("title", "")).strip() or (
        f"{task.get('task_id', '复核任务')} 报告草稿"
    )
    summary = str(report_draft.get("summary", "")).strip() or str(
        task.get("conclusion", "未填写复核结论。")
    )
    rectification_request = str(report_draft.get("rectification_request", "")).strip() or (
        "请按复核结论完成整改责任确认，并补齐正式附件归档。"
    )
    return {
        "title": title,
        "summary": summary,
        "rectification_request": rectification_request,
        "updated_at": str(report_draft.get("updated_at", "")),
    }


def _review_task_report_draft_payload(task: dict[str, object]) -> dict[str, object]:
    task_payload = _review_task_export_payload(task)
    report_gate = _dict_value(task_payload.get("report_gate"))
    if not report_gate.get("ready_for_report"):
        raise HTTPException(
            status_code=409,
            detail="review task is not ready for report draft",
        )
    dossier = _with_review_task_governance_defaults(_dict_value(task_payload.get("dossier")))
    return {
        "format": "review-task-report-draft-v1",
        "generated_at": _utc_now_iso(),
        "task_id": task_payload["task_id"],
        "status": task_payload["status"],
        "status_label": task_payload["status_label"],
        "question": task_payload["question"],
        "assigned_to": task_payload.get("assigned_to"),
        "reviewer_note": task_payload["reviewer_note"],
        "conclusion": task_payload["conclusion"],
        "report_gate": report_gate,
        "report_draft": _report_draft_context(dossier, task_payload),
        "workpaper": _workpaper_context(dossier),
        "owner_signoff": _owner_signoff_context(dossier),
        "attachments": list(_attachment_items(dossier)),
        "source_task": task_payload,
    }


def _render_review_task_report_draft_markdown(payload: dict[str, object]) -> str:
    report_draft = _dict_value(payload.get("report_draft"))
    workpaper = _dict_value(payload.get("workpaper"))
    owner_signoff = _dict_value(payload.get("owner_signoff"))
    attachments = _dict_list(payload.get("attachments"))
    lines = [
        "# AuditScope 审计报告草稿",
        "",
        f"- 生成时间：{payload['generated_at']}",
        f"- 任务编号：{payload['task_id']}",
        f"- 承办人：{payload.get('assigned_to') or '未指定'}",
        f"- 报告标题：{report_draft.get('title')}",
        f"- 复核状态：{payload['status_label']} ({payload['status']})",
        f"- 底稿编号：{workpaper.get('workpaper_id') or '未填写'}",
        f"- 负责人确认：{owner_signoff.get('status_label') or '未提交确认'}",
        f"- 确认人：{owner_signoff.get('confirmed_by') or '未填写'}",
        "",
        "## 一、审计事项",
        "",
        str(payload["question"]),
        "",
        "## 二、复核摘要",
        "",
        str(report_draft.get("summary", "")),
        "",
        "## 三、复核意见与结论",
        "",
        f"- 复核意见：{payload.get('reviewer_note') or '未填写'}",
        f"- 复核结论：{payload.get('conclusion') or '未填写'}",
        "",
        "## 四、整改建议",
        "",
        str(report_draft.get("rectification_request", "")),
        "",
        "## 五、附件清单",
        "",
    ]
    if attachments:
        for item in attachments:
            lines.append(
                f"- {item.get('title')} | {item.get('locator') or '未填写位置'}"
                f" | {item.get('note') or '无说明'}"
            )
    else:
        lines.append("- 未登记附件。")
    lines.extend(
        [
            "",
            "> 本文件为系统生成的报告草稿，不替代正式审计报告签发流程。",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


async def _urlencoded_form(request: Request) -> dict[str, tuple[str, ...]]:
    body = await request.body()
    parsed = urllib.parse.parse_qs(body.decode("utf-8"), keep_blank_values=True)
    return {key: tuple(values) for key, values in parsed.items()}


def _form_required_str(form: Mapping[str, Sequence[str]], key: str) -> str:
    values = form.get(key, ())
    value = values[0] if values else ""
    normalized = str(value).strip()
    if not normalized:
        raise HTTPException(status_code=422, detail=f"missing required form field: {key}")
    return normalized


def _form_optional_str(form: Mapping[str, Sequence[str]], key: str) -> str:
    values = form.get(key, ())
    value = values[0] if values else ""
    return str(value).strip()


def _source_collections_from_form(
    form: Mapping[str, Sequence[str]],
) -> tuple[SourceCollection, ...]:
    collections: list[SourceCollection] = []
    for value in form.get("source_collection", ()):
        try:
            collections.append(SourceCollection(str(value)))
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail=f"unsupported source_collection: {value}",
            ) from exc
    return tuple(collections)


def _answer_quality_context(answer: dict[str, object] | None) -> dict[str, object]:
    if answer is None:
        return {
            "status": "waiting",
            "status_label": "待提问",
            "title": "等待问题",
            "description": "提交问题后展示证据覆盖、引用数量和复核风险。",
            "citation_count": 0,
            "group_count": 0,
            "confidence_label": "未形成",
            "fallback_label": "未运行",
            "review_gate": "不可进入报告",
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
        status_label = "证据较强"
        title = "证据覆盖强"
        description = "引用数量和检索分数满足高置信复核条件。"
    elif confidence == "medium":
        status = "review"
        status_label = "需复核"
        title = "需要人工复核"
        description = "证据可追溯，但建议打开原文确认适用条件。"
    else:
        status = "weak"
        status_label = "证据偏弱"
        title = "证据偏弱"
        description = "仅可作为线索，不应直接形成审核结论。"
    return {
        "status": status,
        "status_label": status_label,
        "title": title,
        "description": description,
        "citation_count": citation_count,
        "group_count": group_count,
        "confidence_label": {"high": "高", "medium": "中", "low": "低"}.get(
            confidence,
            "低",
        ),
        "fallback_label": "检索直出" if fallback_used else "模型生成",
        "review_gate": "可进入人工复核" if citation_count else "不可进入报告",
        "checks": checks,
    }


def _source_collection_cards(
    selected_collections: tuple[SourceCollection, ...],
) -> tuple[dict[str, object], ...]:
    selected_values = {item.value for item in selected_collections}
    return tuple(
        {
            "value": collection.value,
            "title": SOURCE_COLLECTION_UI[collection]["title"],
            "description": SOURCE_COLLECTION_UI[collection]["description"],
            "audit_hint": SOURCE_COLLECTION_UI[collection]["audit_hint"],
            "selected": collection.value in selected_values,
        }
        for collection in SourceCollection
    )


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


def _evaluation_status_context(state: ApiState) -> dict[str, object]:
    if not state.evaluation_runs:
        latest_report = latest_evaluation_report(state)
        if latest_report is not None:
            return _evaluation_status_from_result(latest_report)
        return {
            "status": "not-run",
            "description": "尚未运行发布后固定验收。",
            "latest": None,
            "report": None,
        }
    return _evaluation_status_from_result(state.evaluation_runs[-1])


def _evaluation_status_from_result(latest: dict[str, object]) -> dict[str, object]:
    retrieval = latest.get("retrieval")
    answer = latest.get("answer")
    ui_smoke = latest.get("ui_smoke")
    retrieval_cases = retrieval.get("case_count") if isinstance(retrieval, dict) else "unknown"
    answer_cases = answer.get("case_count") if isinstance(answer, dict) else "unknown"
    smoke_success = ui_smoke.get("success") if isinstance(ui_smoke, dict) else False
    return {
        "status": latest.get("status", "unknown"),
        "description": (
            f"retrieval cases: {retrieval_cases} · "
            f"answer cases: {answer_cases} · "
            f"smoke: {'pass' if smoke_success else 'fail'}"
        ),
        "latest": latest,
        "report": latest.get("report"),
    }


def _evaluation_history_context(
    state: ApiState,
    postgres_status: dict[str, object],
) -> list[dict[str, object]]:
    if postgres_status.get("available") is True:
        return list_evaluation_history(state, limit=8)
    return list_evaluation_report_files(state, limit=8)
