from __future__ import annotations

import hashlib
import json
import os
import urllib.parse
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

import psycopg
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.exc import SQLAlchemyError

from medical_audit_kb.api.agent_store import AgentStore, InMemoryAgentStore, combined_agent_payloads
from medical_audit_kb.api.app import ApiState, PreviewReference, get_api_state, record_operation
from medical_audit_kb.api.audit_finding_store import (
    AuditFindingNotFoundError,
    SqlAlchemyAuditFindingStore,
)
from medical_audit_kb.api.audit_log_policy import (
    audit_log_policy_payload,
    redact_audit_log_events,
)
from medical_audit_kb.api.auth import (
    AuthenticatedUser,
    HospitalRole,
    Permission,
    record_authorization_denied,
    resolve_authenticated_user,
    user_has_permission,
)
from medical_audit_kb.api.docx_export import DOCX_MEDIA_TYPE, markdown_to_docx
from medical_audit_kb.api.evaluation_reports import (
    latest_evaluation_report,
    list_evaluation_history,
    list_evaluation_report_files,
)
from medical_audit_kb.api.postgres_status import load_postgres_index_status, row_count
from medical_audit_kb.api.project_member_store import (
    ProjectMemberStore,
    project_exists,
    visible_project_keys,
)
from medical_audit_kb.api.query_history_store import try_add_query_history
from medical_audit_kb.api.review_task_store import (
    ReviewTaskNotFoundError,
    ReviewTaskProjectScopeConflictError,
    ReviewTaskStore,
    review_task_project_key,
)
from medical_audit_kb.domain.constants import SourceCollection
from medical_audit_kb.domain.source_collection_registry import (
    SOURCE_COLLECTION_DEFINITIONS,
)
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

LEGACY_PAGE_RETIRE_ENV = "MEDICAL_AUDIT_RETIRE_LEGACY_PAGES"
LEGACY_PAGE_REDIRECTS = {
    "/pages/chat": "/chat",
    "/pages/query": "/documents",
    "/pages/review-tasks": "/reports",
    "/pages/audit-logs": "/archive",
    "/pages/audit-findings": "/findings",
    "/pages/index-admin": "/knowledge-base",
}
LEGACY_PAGE_RETIRE_ENABLED_VALUES = {"1", "true", "yes", "on"}


def _retired_legacy_page_redirect(path: str) -> RedirectResponse | None:
    enabled = os.getenv(LEGACY_PAGE_RETIRE_ENV, "").strip().lower()
    if enabled not in LEGACY_PAGE_RETIRE_ENABLED_VALUES:
        return None
    return RedirectResponse(LEGACY_PAGE_REDIRECTS[path], status_code=302)


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
RECTIFICATION_STATUS_LABELS: dict[str, str] = {
    "not-created": "未生成",
    "pending-rectification": "待整改",
    "in-progress": "整改中",
    "submitted": "已提交",
    "accepted": "已验收",
    "returned": "退回整改",
}
RECTIFICATION_FORM_STATUS_LABELS: dict[str, str] = {
    key: label for key, label in RECTIFICATION_STATUS_LABELS.items() if key != "not-created"
}
REVIEW_TASK_ATTACHMENT_DIR = "review-task-attachments"
REVIEW_TASK_ATTACHMENT_MAX_BYTES = 20 * 1024 * 1024

SOURCE_COLLECTION_UI: dict[SourceCollection, dict[str, str]] = {
    definition.collection: {
        "title": definition.label,
        "description": definition.description,
        "audit_hint": definition.audit_hint,
    }
    for definition in SOURCE_COLLECTION_DEFINITIONS
}

REPORT_TEMPLATE_CATEGORIES: tuple[dict[str, str], ...] = (
    {"id": "plan", "label": "计划类", "availability": "awaiting-business-template"},
    {"id": "workpaper", "label": "底稿类", "availability": "active"},
    {
        "id": "evidence",
        "label": "取证类",
        "availability": "awaiting-business-template",
    },
    {
        "id": "confirmation",
        "label": "函证类",
        "availability": "awaiting-business-template",
    },
    {
        "id": "report",
        "label": "报告类",
        "availability": "awaiting-business-template",
    },
    {
        "id": "remediation",
        "label": "整改类",
        "availability": "awaiting-business-template",
    },
)


class ReportTemplateDraftCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_id: str = Field(min_length=1, max_length=128)
    project_key: str = Field(min_length=1, max_length=128)
    field_values: dict[str, str] = Field(max_length=32)

    @field_validator("template_id", "project_key")
    @classmethod
    def normalize_identifier(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("identifier is required")
        return normalized

    @field_validator("field_values")
    @classmethod
    def normalize_field_values(cls, values: dict[str, str]) -> dict[str, str]:
        normalized: dict[str, str] = {}
        for key, value in values.items():
            normalized_key = key.strip()
            if not normalized_key:
                raise ValueError("field_values keys must not be blank")
            if len(normalized_key) > 128:
                raise ValueError("field_values keys must not exceed 128 characters")
            if normalized_key in normalized:
                raise ValueError("field_values keys must be unique after normalization")
            normalized_value = value.strip()
            if len(normalized_value) > 4000:
                raise ValueError("field_values values must not exceed 4000 characters")
            normalized[normalized_key] = normalized_value
        return normalized

WORKPAPER_TEMPLATE_REGISTRY: tuple[dict[str, object], ...] = (
    {
        "id": "workpaper-summary-risk",
        "category_id": "workpaper",
        "name": "费用汇总风险底稿",
        "source_template_id": "medical-expense-summary",
        "source_table": "表1 医保费用汇总表",
        "source_file_name": "表1_医保费用汇总表（空白）.xlsx",
        "sheet_name": "汇总表",
        "output_type": "底稿草稿",
        "registry_status": "active",
        "expected_columns": (
            "费用分类",
            "人次",
            "人数",
            "有效人次",
            "有效人数",
            "平均费",
            "医疗总费用",
            "现金支付",
            "账户支付",
            "统筹支付",
            "大额记账",
            "公务员补助",
            "企业补充",
            "医疗救",
            "伤残补",
            "产前检查费",
            "其他",
            "记账合计",
        ),
        "key_checks": (
            "医疗总费用与支付分项是否存在口径不一致",
            "统筹支付、账户支付、现金支付是否能回溯到明细",
            "重点费用分类是否存在异常占比或环比突增",
        ),
        "evidence_bindings": (
            "费用分类汇总",
            "支付分项合计",
            "异常占比说明",
            "人工复核意见",
        ),
        "prompt": (
            "基于已上传的医保费用汇总表和已核验引用依据，生成费用分类风险底稿草稿；"
            "只写已确认数据事实、待补证项和人工复核意见。"
        ),
        "chat_href": (
            "/chat?agent=agent-report-draft&question="
            "%E5%9F%BA%E4%BA%8E%E5%8C%BB%E4%BF%9D%E8%B4%B9%E7%94%A8"
            "%E6%B1%87%E6%80%BB%E8%A1%A8%E7%94%9F%E6%88%90%E5%BA%95"
            "%E7%A8%BF%E8%8D%89%E7%A8%BF"
        ),
    },
    {
        "id": "workpaper-category-review",
        "category_id": "workpaper",
        "name": "分类费用复核清单",
        "source_template_id": "medical-expense-category-summary",
        "source_table": "表2 医保费用分类汇总表",
        "source_file_name": "表2_医保费用分类汇总表（空白）.xlsx",
        "sheet_name": "汇总表",
        "output_type": "问题清单",
        "registry_status": "active",
        "expected_columns": (
            "费用分类",
            "人次",
            "人数",
            "有效人次",
            "有效人数",
            "平均费用",
            "医疗总费用",
            "现金支付",
            "账户支付",
            "统筹支付",
            "大额记账",
            "公务员补助",
            "企业补充",
            "医疗救",
            "伤残补",
            "产前检查费",
            "其他",
            "记账合计",
        ),
        "key_checks": (
            "平均费用是否存在明显偏离",
            "基金支付与现金支付结构是否符合费用类别预期",
            "分类口径是否能与就诊明细表闭环",
        ),
        "evidence_bindings": (
            "平均费用偏离",
            "基金支付结构",
            "分类口径说明",
            "需下钻明细",
        ),
        "prompt": (
            "基于医保费用分类汇总表，列出平均费用、基金支付结构和分类口径需要复核的"
            "问题清单；不能直接形成结论的内容标为待人工确认。"
        ),
        "chat_href": (
            "/chat?agent=agent-citation-check&question="
            "%E5%8C%BB%E4%BF%9D%E8%B4%B9%E7%94%A8%E5%88%86%E7%B1%BB"
            "%E6%B1%87%E6%80%BB%E8%A1%A8%E5%BA%94%E5%BD%A2%E6%88%90"
            "%E5%93%AA%E4%BA%9B%E5%A4%8D%E6%A0%B8%E6%B8%85%E5%8D%95"
        ),
    },
    {
        "id": "workpaper-visit-detail",
        "category_id": "workpaper",
        "name": "就诊明细疑点摘要",
        "source_template_id": "visit-expense-detail",
        "source_table": "表3 就诊费用明细表",
        "source_file_name": "表3_就诊费用明细表（空白）.xlsx",
        "sheet_name": "明细表",
        "output_type": "复核摘要",
        "registry_status": "active",
        "expected_columns": (
            "序号",
            "职工类型",
            "就诊记录号",
            "姓名",
            "身份证号码",
            "入院诊断",
            "医疗费用总额",
            "自费金额",
            "统筹支付",
            "公务员补助",
            "大额支付",
            "账户支付",
        ),
        "key_checks": (
            "同一就诊记录是否存在重复收费或异常支付",
            "自费金额与统筹支付是否出现不合理组合",
            "身份证号、就诊记录号等直接身份字段需按权限处理",
        ),
        "evidence_bindings": (
            "就诊记录号",
            "诊断与费用",
            "自费和基金支付",
            "隐私字段处理记录",
        ),
        "prompt": (
            "基于就诊费用明细表，按就诊记录输出疑点摘要、证据字段和隐私字段处理提醒；"
            "只把已人工确认的疑点纳入底稿草稿。"
        ),
        "chat_href": (
            "/chat?agent=agent-report-draft&question="
            "%E5%9F%BA%E4%BA%8E%E5%B0%B1%E8%AF%8A%E8%B4%B9%E7%94%A8"
            "%E6%98%8E%E7%BB%86%E8%A1%A8%E6%95%B4%E7%90%86%E7%96%91"
            "%E7%82%B9%E6%91%98%E8%A6%81"
        ),
    },
)


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
    if redirect_response := _retired_legacy_page_redirect("/pages/query"):
        return redirect_response

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
    agent: Annotated[str | None, Query(max_length=128)] = None,
    project_name: Annotated[str | None, Query(max_length=256)] = None,
) -> object:
    if redirect_response := _retired_legacy_page_redirect("/pages/chat"):
        return redirect_response

    selected_collections = tuple(source_collection or ())
    answer_payload, error_message = _run_page_query(
        state,
        question=question,
        selected_collections=selected_collections,
        operation_name="page-chat",
        agent_key=agent,
        request_project_name=project_name,
        record_agent_invocation=True,
    )
    return templates.TemplateResponse(
        request,
        "chat.html",
        {
            "question": question or "",
            "source_collections": list(SourceCollection),
            "source_collection_cards": _source_collection_cards(selected_collections),
            "selected_collections": {item.value for item in selected_collections},
            "selected_agent": agent or "",
            "selected_project_name": project_name or "",
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
    agent: Annotated[str | None, Query(max_length=128)] = None,
    project_name: Annotated[str | None, Query(max_length=256)] = None,
    format: Annotated[str, Query(pattern="^(json|markdown|docx)$")] = "json",
) -> Response:
    _ = (agent, project_name)
    selected_collections = tuple(source_collection or ())
    answer_payload, error_message = _run_page_query(
        state,
        question=question,
        selected_collections=selected_collections,
        operation_name="page-chat-export-query",
        agent_key=None,
        request_project_name=None,
        record_agent_invocation=False,
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
    if format == "docx":
        return _docx_download_response(
            _render_audit_dossier_markdown(dossier),
            filename="auditscope-dossier.docx",
            title="AuditScope 审计底稿导出",
            subject=str(dossier["question"]),
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
    if redirect_response := _retired_legacy_page_redirect("/pages/review-tasks"):
        return redirect_response

    review_tasks = _visible_review_tasks(
        state,
        request=request,
        attempted_action="review-task-page-list",
    )
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
            "rectification_status_options": RECTIFICATION_FORM_STATUS_LABELS,
            "search_backend": _search_backend_context(state),
        },
    )


@router.get("/reports/workpaper-templates")
def report_workpaper_templates(
    state: Annotated[ApiState, Depends(get_api_state)],
) -> dict[str, object]:
    templates_payload = tuple(
        _workpaper_template_registry_item(item) for item in WORKPAPER_TEMPLATE_REGISTRY
    )
    record_operation(
        state,
        "report-workpaper-template-registry-view",
        {"template_count": len(templates_payload), "registry_status": "active"},
    )
    return {
        "format": "workpaper-template-registry-v1",
        "generated_at": _utc_now_iso(),
        "registry_status": "active",
        "template_categories": REPORT_TEMPLATE_CATEGORIES,
        "items": templates_payload,
        "count": len(templates_payload),
        "store": {"ready": True, "backend": "static-template-registry"},
    }


@router.post("/reports/drafts")
def create_report_template_draft(
    payload: ReportTemplateDraftCreateRequest,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> dict[str, object]:
    user = _report_draft_authorized_user(
        state,
        project_key=payload.project_key,
        x_user_id=x_user_id,
        x_role=x_role,
    )
    template = _report_template_by_id(payload.template_id)
    allowed_fields = frozenset(_string_sequence(template.get("evidence_bindings")))
    unsupported_fields = sorted(set(payload.field_values) - allowed_fields)
    if unsupported_fields:
        raise HTTPException(
            status_code=422,
            detail=(
                "field_values contains unsupported evidence binding: "
                f"{unsupported_fields[0]}"
            ),
        )
    now = _utc_now_iso()
    template_name = str(template["name"])
    category_id = str(template["category_id"])
    task_id = f"report-draft-{uuid4().hex}"
    safe_audit_payload: dict[str, object] = {
        "task_id": task_id,
        "template_id": payload.template_id,
        "category_id": category_id,
        "project_key": payload.project_key,
        "created_by": user.user_identifier,
        "actor_role": user.role.value,
        "field_count": len(payload.field_values),
        "status": "pending-review",
        "formal_report_created": False,
        "provider_call": False,
    }
    try:
        record_operation(
            state,
            "report-template-draft-create-intent",
            safe_audit_payload,
        )
    except SQLAlchemyError as exc:
        _record_local_operation(
            state,
            "report-template-draft-create-unavailable",
            {
                **safe_audit_payload,
                "status_code": 503,
                "reason": "audit-intent-unavailable",
                "error_type": type(exc).__name__,
            },
        )
        raise HTTPException(status_code=503, detail="report draft audit is unavailable") from exc

    task = {
        "task_id": task_id,
        "created_at": now,
        "updated_at": now,
        "status": "pending-review",
        "status_label": REVIEW_TASK_STATUS_LABELS["pending-review"],
        "question": f"{template_name}：{payload.project_key}",
        "citation_count": 0,
        "review_gate": "模板字段已受控校验，待人工复核。",
        "confidence_label": "待复核",
        "fallback_label": "模板草稿",
        "source": "report-template-draft",
        "created_by": user.user_identifier,
        "assigned_to": "",
        "reviewer_note": "",
        "conclusion": "",
        "dossier": _with_review_task_governance_defaults(
            {
                "format": "report-template-draft-dossier-v1",
                "report_template_draft": {
                    "status": "draft",
                    "template_id": payload.template_id,
                    "template_name": template_name,
                    "category_id": category_id,
                    "project_key": payload.project_key,
                    "created_by": user.user_identifier,
                    "user_identifier": user.user_identifier,
                    "field_values": dict(payload.field_values),
                }
            }
        ),
    }
    created_task = _review_task_store(state).add_task(task)
    task_id = str(created_task["task_id"])
    audit_payload = (
        {
            "status": "ready",
            "durability": "durable",
            "local_only": False,
            "intent_recorded": True,
            "completion_recorded": True,
        }
        if state.audit_log_store is not None
        else {
            "status": "local-only",
            "durability": "local-only",
            "local_only": True,
            "intent_recorded": True,
            "completion_recorded": True,
        }
    )
    try:
        record_operation(
            state,
            "report-template-draft-create-completed",
            safe_audit_payload,
        )
    except SQLAlchemyError as exc:
        audit_payload = {
            "status": "degraded",
            "durability": "intent-only",
            "local_only": False,
            "intent_recorded": True,
            "completion_recorded": False,
        }
        _record_local_operation(
            state,
            "report-template-draft-create-audit-degraded",
            {
                **safe_audit_payload,
                "status_code": 200,
                "reason": "audit-completion-unavailable",
                "error_type": type(exc).__name__,
            },
        )
    return {
        "format": "report-template-draft-v1",
        "task_id": task_id,
        "template_id": payload.template_id,
        "category_id": category_id,
        "project_key": payload.project_key,
        "project_href": (
            "/projects?project="
            f"{urllib.parse.quote(payload.project_key, safe='')}"
        ),
        "status": "pending-review",
        "store": {
            "ready": True,
            "backend": _review_task_store(state).__class__.__name__,
        },
        "formal_report_created": False,
        "provider_call": False,
        "audit": audit_payload,
    }


class ReportSignoffRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    signoff_note: str = Field(default="", max_length=2000)


@router.post("/reports/drafts/{task_id}/signoff")
def sign_report_draft(
    task_id: str,
    payload: ReportSignoffRequest,
    request: Request,
    state: Annotated[ApiState, Depends(get_api_state)],
) -> dict[str, object]:
    task, user = _visible_review_task_for_formal_action(
        state,
        task_id,
        request=request,
        attempted_action="report-draft-signoff",
    )
    signed_report = _sign_review_task_report_atomically(
        state,
        task_id,
        task=task,
        actor=user,
        request=request,
        attempted_action="report-draft-signoff",
        endpoint=f"/reports/drafts/{task_id}/signoff",
        signoff_note=payload.signoff_note,
    )
    record_operation(
        state,
        "report-draft-signoff",
        {
            "task_id": task_id,
            "report_id": signed_report["report_id"],
            "signed_by": user.user_identifier,
            "actor_role": user.role.value,
        },
    )
    return {
        "format": "report-signoff-v1",
        "task_id": task_id,
        "report_id": str(signed_report["report_id"]),
        "signed_by": str(signed_report["signed_by"]),
        "signed_at": str(signed_report["signed_at"]),
        "signoff_note": str(signed_report["signoff_note"]),
        "status": "signed",
    }


@router.get("/reports/workbench")
def reports_workbench(
    request: Request,
    state: Annotated[ApiState, Depends(get_api_state)],
) -> dict[str, object]:
    review_tasks = tuple(
        reversed(
            _visible_review_tasks(
                state,
                request=request,
                attempted_action="report-workbench-list",
            )
        )
    )
    signoff_actors: dict[str | None, AuthenticatedUser | None] = {}
    report_entries = tuple(
        _review_task_report_entry(
            task,
            signoff_capability=_review_task_signoff_capability(
                state,
                task,
                request=request,
                actor_cache=signoff_actors,
            ),
        )
        for task in review_tasks
    )
    report_evidence_sources = tuple(
        _review_task_report_evidence_source(task) for task in review_tasks
    )
    templates_payload = tuple(
        _workpaper_template_registry_item(item) for item in WORKPAPER_TEMPLATE_REGISTRY
    )
    metrics = _report_workbench_metrics(report_entries)
    record_operation(
        state,
        "report-workbench-view",
        {
            "template_count": len(templates_payload),
            "report_count": len(report_entries),
            "signed_report_count": metrics["signed_report_count"],
            "docx_download_count": metrics["docx_download_count"],
        },
    )
    return {
        "format": "report-workbench-v1",
        "generated_at": _utc_now_iso(),
        "template_registry_status": "active",
        "template_categories": REPORT_TEMPLATE_CATEGORIES,
        "workpaper_templates": templates_payload,
        "report_entries": report_entries,
        "report_evidence_sources": report_evidence_sources,
        "metrics": metrics,
        "store": {"ready": True, "backend": _review_task_store(state).__class__.__name__},
    }


@router.get("/pages/audit-logs")
def audit_logs_page(
    request: Request,
    state: Annotated[ApiState, Depends(get_api_state)],
    action: Annotated[str | None, Query(max_length=96)] = None,
    entity_type: Annotated[str | None, Query(max_length=64)] = None,
    entity_id: Annotated[str | None, Query(max_length=128)] = None,
    user_identifier: Annotated[str | None, Query(max_length=128)] = None,
    created_from: Annotated[datetime | None, Query()] = None,
    created_to: Annotated[datetime | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> object:
    if redirect_response := _retired_legacy_page_redirect("/pages/audit-logs"):
        return redirect_response

    filters = _audit_log_filter_context(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        user_identifier=user_identifier,
        created_from=created_from,
        created_to=created_to,
        limit=limit,
    )
    user_role = request.headers.get("X-Role")
    user_identifier_header = request.headers.get("X-User-Id")
    user_identifier_for_log = user_identifier_header or "anonymous"
    effective_role_for_log = "anonymous"
    auth_source_for_log = "header"
    try:
        user = resolve_authenticated_user(
            state,
            x_user_id=user_identifier_header,
            x_role=user_role,
        )
        user_identifier_for_log = user.user_identifier
        effective_role_for_log = user.role.value
        auth_source_for_log = user.auth_source
        can_access_audit_logs = user_has_permission(user, Permission.READ_AUDIT_LOGS)
    except HTTPException as exc:
        can_access_audit_logs = False
        auth_source_for_log = "denied"
        effective_role_for_log = user_role or "anonymous"
        denied_status_code = exc.status_code
    else:
        denied_status_code = 403
    record_operation(
        state,
        "page-audit-logs-view" if can_access_audit_logs else "audit-logs-access-denied",
        {
            "filters": filters,
            "user_identifier": user_identifier_for_log,
            "role": user_role or "anonymous",
            "effective_role": effective_role_for_log,
            "auth_source": auth_source_for_log,
            "status_code": 200 if can_access_audit_logs else 403,
            "auth_status_code": 200 if can_access_audit_logs else denied_status_code,
        },
    )
    audit_log_events = []
    if can_access_audit_logs and state.audit_log_store is not None:
        audit_log_events = redact_audit_log_events(
            state.audit_log_store.list_events(
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                user_identifier=user_identifier,
                created_from=created_from,
                created_to=created_to,
                limit=limit,
            )
        )
    return templates.TemplateResponse(
        request,
        "audit_logs.html",
        {
            "audit_log_events": tuple(_audit_log_page_item(event) for event in audit_log_events),
            "audit_log_summary": _audit_log_summary(audit_log_events),
            "audit_log_filters": filters,
            "audit_log_access_allowed": can_access_audit_logs,
            "audit_log_store_ready": state.audit_log_store is not None,
            "audit_log_store_backend": (
                "none"
                if state.audit_log_store is None
                else state.audit_log_store.__class__.__name__
            ),
            "audit_log_export_query": _audit_log_export_query(filters),
            "audit_log_policy": audit_log_policy_payload(),
            "search_backend": _search_backend_context(state),
        },
    )


@router.get("/pages/audit-findings")
def audit_findings_page(
    request: Request,
    state: Annotated[ApiState, Depends(get_api_state)],
    review_status: Annotated[str | None, Query()] = None,
) -> object:
    if redirect_response := _retired_legacy_page_redirect("/pages/audit-findings"):
        return redirect_response

    if review_status is not None and review_status not in REVIEW_TASK_STATUS_LABELS:
        raise HTTPException(status_code=422, detail=f"unsupported review_status: {review_status}")
    user = _audit_finding_authorized_user(
        state,
        request=request,
        attempted_action="page-audit-findings-view",
    )
    findings = _audit_findings(
        state,
        review_status=review_status,
        project_keys=_audit_finding_visible_project_keys(
            state,
            user=user,
            attempted_action="page-audit-findings-view",
        ),
    )
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
    request: Request,
    state: Annotated[ApiState, Depends(get_api_state)],
) -> Response:
    finding = _visible_audit_finding_by_key(
        state,
        finding_key,
        request=request,
        attempted_action="audit-finding-export",
    )
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
    finding = _visible_audit_finding_by_key(
        state,
        finding_key,
        request=request,
        attempted_action="audit-finding-review-task-create",
    )
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
    status = _form_required_str(form, "status")
    if status not in REVIEW_TASK_STATUS_LABELS:
        raise HTTPException(status_code=422, detail=f"unsupported review task status: {status}")
    owner_signoff_status = _form_optional_str(form, "owner_signoff_status")
    owner_confirmed_by = _form_optional_str(form, "owner_confirmed_by")
    owner_confirmed_at = _form_optional_str(form, "owner_confirmed_at")
    is_formal_action = (
        status == "closed"
        or owner_signoff_status in {"approved", "rejected"}
        or bool(owner_confirmed_by)
        or bool(owner_confirmed_at)
    )
    formal_actor: AuthenticatedUser | None
    if is_formal_action:
        existing_task, formal_actor = _visible_review_task_for_formal_action(
            state,
            task_id,
            request=request,
            attempted_action="review-task-status-update",
        )
        if (
            owner_signoff_status in {"approved", "rejected"}
            or owner_confirmed_by
            or owner_confirmed_at
        ):
            form = {**form, "owner_confirmed_by": (formal_actor.user_identifier,)}
    else:
        existing_task = _visible_review_task_by_id(
            state,
            task_id,
            request=request,
            attempted_action="review-task-status-update",
        )
        formal_actor = None
    _ensure_review_task_writable(
        state,
        existing_task,
        request=request,
        attempted_action="review-task-status-update",
        endpoint=f"/pages/review-tasks/{task_id}/status",
    )
    if status == "closed":
        _ensure_review_task_can_close(existing_task)

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
    synced_findings = _sync_audit_finding_review_status(
        state,
        task_id,
        status,
        project_key=_review_task_project_key(existing_task),
    )
    record_operation(
        state,
        "review-task-status-update",
        {
            "task_id": task_id,
            "status": status,
            "synced_audit_finding_count": len(synced_findings),
            "actor": formal_actor.user_identifier if formal_actor is not None else None,
            "actor_role": formal_actor.role.value if formal_actor is not None else None,
        },
    )
    return RedirectResponse("/pages/review-tasks", status_code=303)


@router.post("/pages/review-tasks/{task_id}/attachments")
async def upload_review_task_attachment_page(
    task_id: str,
    request: Request,
    state: Annotated[ApiState, Depends(get_api_state)],
    attachment_file: Annotated[UploadFile, File()],
    attachment_title: Annotated[str | None, Form()] = None,
    attachment_note: Annotated[str | None, Form()] = None,
) -> RedirectResponse:
    task = _visible_review_task_by_id(
        state,
        task_id,
        request=request,
        attempted_action="review-task-attachment-upload",
    )
    _ensure_review_task_writable(
        state,
        task,
        request=request,
        attempted_action="review-task-attachment-upload",
        endpoint=f"/pages/review-tasks/{task_id}/attachments",
    )
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
    request: Request,
    state: Annotated[ApiState, Depends(get_api_state)],
) -> FileResponse:
    task = _visible_review_task_by_id(
        state,
        task_id,
        request=request,
        attempted_action="review-task-attachment-download",
    )
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
    request: Request,
    state: Annotated[ApiState, Depends(get_api_state)],
    format: Annotated[str, Query(pattern="^(json|markdown|docx)$")] = "json",
) -> Response:
    task = _visible_review_task_by_id(
        state,
        task_id,
        request=request,
        attempted_action="review-task-export",
    )
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
    if format == "docx":
        return _docx_download_response(
            _render_review_task_markdown(payload),
            filename=f"{task_id}.docx",
            title="AuditScope 复核任务记录",
            subject=str(payload["question"]),
        )
    return Response(
        content=json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        media_type="application/json",
        headers=_download_headers(f"{task_id}.json"),
    )


@router.get("/review-tasks/{task_id}/report-draft")
def review_task_report_draft_export(
    task_id: str,
    request: Request,
    state: Annotated[ApiState, Depends(get_api_state)],
    format: Annotated[str, Query(pattern="^(json|markdown|docx)$")] = "markdown",
) -> Response:
    task = _visible_review_task_by_id(
        state,
        task_id,
        request=request,
        attempted_action="review-task-report-draft-export",
    )
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
    markdown = _render_review_task_report_draft_markdown(payload)
    if format == "docx":
        report_draft = _dict_value(payload.get("report_draft"))
        return _docx_download_response(
            markdown,
            filename=f"{task_id}-report-draft.docx",
            title=str(report_draft.get("title") or "AuditScope 审计报告草稿"),
            subject=str(payload["question"]),
        )
    return Response(
        content=markdown,
        media_type="text/markdown; charset=utf-8",
        headers=_download_headers(f"{task_id}-report-draft.md"),
    )


@router.post("/pages/review-tasks/{task_id}/report-signoff")
async def sign_review_task_report_page(
    task_id: str,
    request: Request,
    state: Annotated[ApiState, Depends(get_api_state)],
) -> RedirectResponse:
    task, actor = _visible_review_task_for_formal_action(
        state,
        task_id,
        request=request,
        attempted_action="review-task-report-signoff",
    )
    form = await _urlencoded_form(request)
    signoff_note = _form_optional_str(form, "signoff_note")
    signed_report = _sign_review_task_report_atomically(
        state,
        task_id,
        task=task,
        actor=actor,
        request=request,
        attempted_action="review-task-report-signoff",
        endpoint=f"/pages/review-tasks/{task_id}/report-signoff",
        signoff_note=signoff_note,
    )
    record_operation(
        state,
        "review-task-report-signoff",
        {
            "task_id": task_id,
            "report_id": signed_report["report_id"],
            "signed_by": actor.user_identifier,
            "actor_role": actor.role.value,
            "content_sha256": signed_report["content_sha256"],
        },
    )
    return RedirectResponse("/pages/review-tasks", status_code=303)


@router.get("/review-tasks/{task_id}/signed-report")
def review_task_signed_report_export(
    task_id: str,
    request: Request,
    state: Annotated[ApiState, Depends(get_api_state)],
    format: Annotated[str, Query(pattern="^(json|markdown|docx)$")] = "markdown",
) -> Response:
    task = _visible_review_task_by_id(
        state,
        task_id,
        request=request,
        attempted_action="review-task-signed-report-export",
    )
    payload = _review_task_signed_report_payload(task)
    record_operation(
        state,
        "review-task-signed-report-export",
        {"task_id": task_id, "format": format},
    )
    if format == "json":
        return Response(
            content=json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            media_type="application/json",
            headers=_download_headers(f"{task_id}-signed-report.json"),
        )
    signed_report = _dict_value(payload.get("signed_report"))
    markdown = str(signed_report.get("content", ""))
    if format == "docx":
        return _docx_download_response(
            markdown,
            filename=f"{task_id}-signed-report.docx",
            title=str(signed_report.get("report_id") or "AuditScope 正式报告"),
            subject=str(payload["question"]),
        )
    return Response(
        content=markdown,
        media_type="text/markdown; charset=utf-8",
        headers=_download_headers(f"{task_id}-signed-report.md"),
    )


@router.post("/pages/review-tasks/{task_id}/rectification")
async def update_review_task_rectification_page(
    task_id: str,
    request: Request,
    state: Annotated[ApiState, Depends(get_api_state)],
) -> RedirectResponse:
    form = await _urlencoded_form(request)
    rectification_status = _form_required_str(form, "rectification_status")
    if rectification_status not in RECTIFICATION_FORM_STATUS_LABELS:
        raise HTTPException(
            status_code=422,
            detail=f"unsupported rectification_status: {rectification_status}",
        )
    formal_actor: AuthenticatedUser | None = None
    if rectification_status in {"accepted", "returned"}:
        task, formal_actor = _visible_review_task_for_formal_action(
            state,
            task_id,
            request=request,
            attempted_action="review-task-rectification-update",
        )
    else:
        task = _visible_review_task_by_id(
            state,
            task_id,
            request=request,
            attempted_action="review-task-rectification-update",
        )
    _ensure_review_task_writable(
        state,
        task,
        request=request,
        attempted_action="review-task-rectification-update",
        endpoint=f"/pages/review-tasks/{task_id}/rectification",
    )
    dossier = _with_review_task_governance_defaults(_dict_value(task.get("dossier")))
    if not _signed_report_context(dossier)["signed"]:
        raise HTTPException(
            status_code=409,
            detail="review task report must be signed before rectification tracking",
        )
    rectification = _build_review_task_rectification(
        task={**task, "dossier": dossier},
        form=form,
        rectification_status=rectification_status,
        actor_identifier=formal_actor.user_identifier
        if formal_actor is not None
        else "page-user",
    )
    dossier["rectification"] = rectification
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
        "review-task-rectification-update",
        {
            "task_id": task_id,
            "rectification_id": rectification["rectification_id"],
            "rectification_status": rectification["status"],
            "event_count": rectification["event_count"],
            "actor": formal_actor.user_identifier if formal_actor is not None else None,
            "actor_role": formal_actor.role.value if formal_actor is not None else None,
        },
    )
    return RedirectResponse("/pages/review-tasks", status_code=303)


@router.get("/review-tasks/{task_id}/rectification/export")
def review_task_rectification_export(
    task_id: str,
    request: Request,
    state: Annotated[ApiState, Depends(get_api_state)],
    format: Annotated[str, Query(pattern="^(json|markdown)$")] = "json",
) -> Response:
    task = _visible_review_task_by_id(
        state,
        task_id,
        request=request,
        attempted_action="review-task-rectification-export",
    )
    payload = _review_task_rectification_payload(task)
    record_operation(
        state,
        "review-task-rectification-export",
        {"task_id": task_id, "format": format},
    )
    if format == "markdown":
        return Response(
            content=_render_review_task_rectification_markdown(payload),
            media_type="text/markdown; charset=utf-8",
            headers=_download_headers(f"{task_id}-rectification.md"),
        )
    return Response(
        content=json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        media_type="application/json",
        headers=_download_headers(f"{task_id}-rectification.json"),
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
    if redirect_response := _retired_legacy_page_redirect("/pages/index-admin"):
        return redirect_response

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


def _audit_log_filter_context(
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
        "action": action or "",
        "entity_type": entity_type or "",
        "entity_id": entity_id or "",
        "user_identifier": user_identifier or "",
        "created_from": created_from.isoformat() if created_from is not None else "",
        "created_to": created_to.isoformat() if created_to is not None else "",
        "limit": limit,
    }


def _audit_log_page_item(event: dict[str, object]) -> dict[str, object]:
    payload = event.get("payload")
    metadata = event.get("metadata")
    return {
        "event_id": event.get("event_id", ""),
        "action": event.get("action", ""),
        "entity_type": event.get("entity_type", ""),
        "entity_id": event.get("entity_id", ""),
        "user_identifier": event.get("user_identifier") or "anonymous",
        "role": event.get("role") or "unknown",
        "status_code": event.get("status_code") or "",
        "endpoint": event.get("endpoint") or "",
        "reason": event.get("reason") or "",
        "payload": payload if isinstance(payload, dict) else {},
        "metadata": metadata if isinstance(metadata, dict) else {},
        "created_at": event.get("created_at", ""),
        "severity": _audit_log_severity(event),
    }


def _audit_log_summary(events: list[dict[str, object]]) -> dict[str, object]:
    user_identifiers = {
        str(event["user_identifier"])
        for event in events
        if event.get("user_identifier") not in {None, ""}
    }
    entity_keys = {
        (str(event.get("entity_type")), str(event.get("entity_id")))
        for event in events
        if event.get("entity_type") not in {None, ""} and event.get("entity_id") not in {None, ""}
    }
    blocked_count = sum(1 for event in events if _audit_log_severity(event) == "blocked")
    return {
        "total": len(events),
        "blocked": blocked_count,
        "users": len(user_identifiers),
        "entities": len(entity_keys),
    }


def _audit_log_export_query(filters: dict[str, object]) -> str:
    query_items = [
        (key, value)
        for key in (
            "action",
            "entity_type",
            "entity_id",
            "user_identifier",
            "created_from",
            "created_to",
        )
        if (value := filters.get(key)) not in {None, ""}
    ]
    return urllib.parse.urlencode(query_items)


def _audit_log_severity(event: dict[str, object]) -> str:
    action = str(event.get("action") or "")
    status_code = event.get("status_code")
    if "blocked" in action or (isinstance(status_code, int) and status_code >= 400):
        return "blocked"
    if action.endswith("export"):
        return "export"
    return "normal"


def _run_page_query(
    state: ApiState,
    *,
    question: str | None,
    selected_collections: tuple[SourceCollection, ...],
    operation_name: str,
    agent_key: str | None = None,
    request_project_name: str | None = None,
    record_agent_invocation: bool = False,
) -> tuple[dict[str, object] | None, str | None]:
    if not question:
        return None, None
    if state.search_engine is None:
        return None, "检索引擎尚未初始化。"
    normalized_agent_key = _normalize_agent_key(agent_key)
    selected_agent: dict[str, object] | None = None
    if normalized_agent_key is not None:
        selected_agent, agent_error = _validate_page_agent_selection(
            state,
            normalized_agent_key,
            request_project_name=request_project_name,
            attempted_action=operation_name,
        )
        if agent_error is not None:
            return None, agent_error

    results = state.search_engine.search(
        question,
        filters=RetrievalFilters(source_collections=selected_collections),
        top_k=5,
    )
    try:
        answer = build_citation_backed_answer(
            question,
            results,
            generation_provider=state.answer_generation_provider,
            agent_prompt=str(selected_agent.get("prompt") or "") if selected_agent else None,
            agent_prompt_version_key=(
                str(selected_agent.get("prompt_version_key") or "") if selected_agent else None
            ),
        )
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
        "agent_id": normalized_agent_key,
        "agent_name": str(selected_agent.get("name")) if selected_agent is not None else None,
        "agent_invocation_id": None,
    }
    retrieved_chunk_ids = [str(citation.chunk_id) for citation in answer.citations]
    filter_payload = {
        "top_k": 5,
        "source_collections": [item.value for item in selected_collections],
        "agent": normalized_agent_key,
    }
    state.query_logs.append(
        {
            "user_identifier": "page-user",
            "role": "auditor",
            "question": question,
            "agent_id": normalized_agent_key,
            "filters": filter_payload,
            "retrieved_chunk_ids": retrieved_chunk_ids,
            "citation_count": len(answer.citations),
        }
    )
    persisted_log, query_history_error = try_add_query_history(
        state.query_history_store,
        {
            "user_identifier": "page-user",
            "question": question,
            "filters": filter_payload,
            "answer_summary": answer.answer[:500],
            "retrieved_chunk_ids": retrieved_chunk_ids,
        },
    )
    if record_agent_invocation and normalized_agent_key is not None:
        invocation, invocation_error = _record_page_agent_invocation(
            state,
            agent_key=normalized_agent_key,
            question=question,
            selected_collections=selected_collections,
            query_log_id=str(persisted_log.get("id")) if persisted_log else None,
            query_log_index=len(state.query_logs) - 1,
            citation_count=len(answer.citations),
            request_project_name=request_project_name,
        )
        if invocation_error is not None:
            return None, invocation_error
        assert invocation is not None
        answer_payload["agent_invocation_id"] = str(invocation["id"])
    record_operation(
        state,
        operation_name,
        {
            "question": question,
            "citation_count": len(answer.citations),
            "agent_id": normalized_agent_key,
            "agent_invocation_id": answer_payload["agent_invocation_id"],
            "query_log_id": persisted_log.get("id") if persisted_log else None,
            "query_history_error": query_history_error,
        },
    )
    return answer_payload, None


def _record_page_agent_invocation(
    state: ApiState,
    *,
    agent_key: str,
    question: str,
    selected_collections: tuple[SourceCollection, ...],
    query_log_id: str | None,
    query_log_index: int,
    citation_count: int,
    request_project_name: str | None,
) -> tuple[dict[str, object] | None, str | None]:
    metadata: dict[str, object] = {
        "filters": {
            "top_k": 5,
            "source_collections": [item.value for item in selected_collections],
            "agent": agent_key,
        },
        "query_log_id": query_log_id,
        "query_log_index": query_log_index,
        "citation_count": citation_count,
        "project_name": _normalize_project_name(request_project_name),
    }
    try:
        invocation = _agent_store(state).record_invocation(
            agent_key,
            invocation_source="/pages/chat",
            question=question,
            conversation_ref=query_log_id or f"page-query-log-index:{query_log_index}",
            created_by="page-user",
            metadata=metadata,
        )
    except KeyError:
        return None, "选择的智能体不存在。"
    except ValueError:
        return None, "选择的智能体已下架，不能用于新的对话。"
    except SQLAlchemyError:
        return None, "智能体调用记录存储不可用。"
    record_operation(
        state,
        "agent-invocation-create",
        {
            "agent_id": agent_key,
            "invocation_id": invocation["id"],
            "prompt_version": invocation["prompt_version"],
            "created_by": "page-user",
            "invocation_source": "/pages/chat",
        },
    )
    return invocation, None


def _validate_page_agent_selection(
    state: ApiState,
    agent_key: str,
    *,
    request_project_name: str | None,
    attempted_action: str,
) -> tuple[dict[str, object] | None, str | None]:
    try:
        agent = _agent_payload_for_key(state, agent_key)
    except SQLAlchemyError:
        return None, "智能体存储不可用。"
    if agent is None:
        return None, "选择的智能体不存在。"
    if str(agent.get("status") or "active") != "active":
        return None, "选择的智能体已下架，不能用于新的对话。"
    if not str(agent.get("prompt") or "").strip():
        return None, "选择的智能体提示词不可用。"
    scope_error = _agent_project_scope_error(
        state,
        agent,
        request_project_name=request_project_name,
        attempted_action=attempted_action,
    )
    if scope_error is not None:
        return None, scope_error
    return agent, None


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


def _agent_project_scope_error(
    state: ApiState,
    agent: dict[str, object],
    *,
    request_project_name: str | None,
    attempted_action: str,
) -> str | None:
    normalized_project = _normalize_project_name(request_project_name)
    if str(agent.get("visibility_scope") or "project") != "project":
        return None
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
        return "选择项目级智能体时必须提供当前项目空间。"
    if agent_project_name == normalized_project:
        return None
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
    return "选择的智能体不属于当前项目空间。"


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


def _string_sequence(value: object) -> tuple[str, ...]:
    if isinstance(value, Sequence) and not isinstance(value, str):
        return tuple(str(item) for item in value)
    return ()


def _dict_list(value: object) -> tuple[dict[str, object], ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, dict))


def _dict_value(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return dict(value)
    return {}


def _non_negative_int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int) and value >= 0:
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return 0


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


def _docx_download_response(
    markdown: str,
    *,
    filename: str,
    title: str,
    subject: str | None = None,
) -> Response:
    return Response(
        content=markdown_to_docx(markdown, title=title, subject=subject),
        media_type=DOCX_MEDIA_TYPE,
        headers=_download_headers(filename),
    )


def _workpaper_template_registry_item(template: Mapping[str, object]) -> dict[str, object]:
    return {
        "id": str(template["id"]),
        "category_id": str(template["category_id"]),
        "name": str(template["name"]),
        "source_template_id": str(template["source_template_id"]),
        "source_table": str(template["source_table"]),
        "source_file_name": str(template["source_file_name"]),
        "sheet_name": str(template["sheet_name"]),
        "output_type": str(template["output_type"]),
        "registry_status": str(template["registry_status"]),
        "expected_columns": _string_sequence(template.get("expected_columns")),
        "key_checks": _string_sequence(template.get("key_checks")),
        "evidence_bindings": _string_sequence(template.get("evidence_bindings")),
        "prompt": str(template["prompt"]),
        "chat_href": str(template["chat_href"]),
    }


def _report_template_by_id(template_id: str) -> Mapping[str, object]:
    for template in WORKPAPER_TEMPLATE_REGISTRY:
        if template["id"] == template_id:
            return template
    raise HTTPException(status_code=404, detail="report template not found")


def _report_draft_authorized_user(
    state: ApiState,
    *,
    project_key: str,
    x_user_id: str | None,
    x_role: str | None,
) -> AuthenticatedUser:
    attempted_action = "report-template-draft-create"
    permission = Permission.CREATE_REPORT_DRAFT
    normalized_user_identifier = (x_user_id or "").strip()
    if not normalized_user_identifier or normalized_user_identifier == "anonymous":
        record_authorization_denied(
            state,
            attempted_action=attempted_action,
            permission=permission,
            user_identifier="anonymous",
            raw_role=x_role,
            status_code=401,
            reason="X-User-Id header is required",
            auth_scope_type="project",
            auth_scope_key=project_key,
        )
        raise HTTPException(status_code=401, detail="X-User-Id header is required")

    try:
        user = resolve_authenticated_user(
            state,
            x_user_id=normalized_user_identifier,
            x_role=x_role,
            project_key=project_key,
        )
    except HTTPException as exc:
        record_authorization_denied(
            state,
            attempted_action=attempted_action,
            permission=permission,
            user_identifier=normalized_user_identifier,
            raw_role=x_role,
            status_code=exc.status_code,
            reason=str(exc.detail),
            auth_scope_type="project",
            auth_scope_key=project_key,
        )
        raise

    store = _report_project_member_store(state)
    try:
        exists = project_exists(project_key, store)
    except SQLAlchemyError as exc:
        _record_operation_best_effort(
            state,
            "report-template-draft-create-unavailable",
            {
                "attempted_action": attempted_action,
                "permission": permission.value,
                "user_identifier": user.user_identifier,
                "status_code": 503,
                "reason": "project-store-unavailable",
                "error_type": type(exc).__name__,
            },
        )
        raise HTTPException(status_code=503, detail="project store is unavailable") from exc
    if not exists:
        _record_report_draft_denial(
            state,
            user=user,
            project_key=project_key,
            status_code=404,
            reason="project not found",
        )
        raise HTTPException(status_code=404, detail="project not found")

    try:
        visible_keys = visible_project_keys(
            user_identifier=user.user_identifier,
            is_admin=user.role is HospitalRole.ADMIN,
            store=store,
        )
    except SQLAlchemyError as exc:
        _record_operation_best_effort(
            state,
            "report-template-draft-create-unavailable",
            {
                "attempted_action": attempted_action,
                "permission": permission.value,
                "user_identifier": user.user_identifier,
                "role": user.raw_role or user.role.value,
                "effective_role": user.role.value,
                "auth_scope_type": "project",
                "auth_scope_key": project_key,
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
        _record_report_draft_denial(
            state,
            user=user,
            project_key=project_key,
            status_code=404,
            reason="project not found",
        )
        raise HTTPException(status_code=404, detail="project not found")

    if not user_has_permission(user, permission):
        _record_report_draft_denial(
            state,
            user=user,
            project_key=project_key,
            status_code=403,
            reason=f"{permission.value} requires a higher hospital role",
        )
        raise HTTPException(status_code=403, detail=f"{permission.value} is not allowed")
    return user


def _record_report_draft_denial(
    state: ApiState,
    *,
    user: AuthenticatedUser,
    project_key: str,
    status_code: int,
    reason: str,
) -> None:
    record_authorization_denied(
        state,
        attempted_action="report-template-draft-create",
        permission=Permission.CREATE_REPORT_DRAFT,
        user_identifier=user.user_identifier,
        raw_role=user.raw_role,
        effective_role=user.role.value,
        auth_source=user.auth_source,
        profile_status=user.profile_status,
        auth_scope_type="project",
        auth_scope_key=project_key,
        status_code=status_code,
        reason=reason,
    )


def _report_project_member_store(state: ApiState) -> ProjectMemberStore:
    if state.project_member_store is None:
        raise HTTPException(
            status_code=503,
            detail="project membership store is not configured",
        )
    return state.project_member_store


def _record_local_operation(
    state: ApiState,
    action: str,
    payload: dict[str, object],
) -> None:
    state.operation_logs.append({"action": action, "payload": payload})


def _review_task_report_entry(
    task: dict[str, object],
    *,
    signoff_capability: dict[str, bool] | None = None,
) -> dict[str, object]:
    payload = _review_task_export_payload(task)
    dossier = _with_review_task_governance_defaults(_dict_value(payload.get("dossier")))
    report_gate = _dict_value(payload.get("report_gate"))
    signed_report = _signed_report_context(dossier)
    workpaper = _workpaper_context(dossier)
    attachments = _attachment_items(dossier)
    report_draft = _report_draft_context(dossier, payload)
    task_id = str(payload["task_id"])
    encoded_task_id = urllib.parse.quote(task_id)
    report_download_prefix = _report_download_prefix(
        encoded_task_id=encoded_task_id,
        ready_for_report=bool(report_gate.get("ready_for_report")),
        signed=bool(signed_report["signed"]),
    )
    report_status = _report_entry_status(
        ready_for_report=bool(report_gate.get("ready_for_report")),
        signed=bool(signed_report["signed"]),
    )
    report_docx_href = (
        f"{report_download_prefix}?format=docx" if report_download_prefix is not None else None
    )
    return {
        "id": task_id,
        "title": str(report_draft.get("title") or payload["question"]),
        "status": report_status,
        "report_no": _report_entry_no(
            task_id=task_id,
            signed_report=signed_report,
            workpaper=workpaper,
        ),
        "owner": str(payload.get("assigned_to") or "未指定"),
        "source": str(payload.get("source", "review-task")),
        "included_finding_count": 1 if report_status != "门禁阻断" else 0,
        "appendix_count": len(attachments),
        "gate_summary": str(report_gate.get("status_label") or "未执行报告门禁"),
        "updated_at": str(payload["updated_at"]),
        "href": "/pages/review-tasks",
        "signoff": {
            "signed": bool(signed_report.get("signed")),
            "signed_by": str(signed_report.get("signed_by") or ""),
            "signed_at": str(signed_report.get("signed_at") or ""),
            "signoff_note": str(signed_report.get("signoff_note") or ""),
            "report_id": str(signed_report.get("report_id") or ""),
            **(
                signoff_capability
                or {
                    "can_sign": False,
                    "gate_ready": bool(report_gate.get("ready_for_report")),
                    "writes_allowed": str(payload.get("status") or "") != "closed",
                }
            ),
        },
        "download_links": {
            "page": "/pages/review-tasks",
            "task_docx": f"/review-tasks/{encoded_task_id}/export?format=docx",
            "report_docx": report_docx_href,
            "report_markdown": (
                f"{report_download_prefix}?format=markdown"
                if report_download_prefix is not None
                else None
            ),
            "report_json": (
                f"{report_download_prefix}?format=json"
                if report_download_prefix is not None
                else None
            ),
        },
    }


def _review_task_signoff_capability(
    state: ApiState,
    task: dict[str, object],
    *,
    request: Request,
    actor_cache: dict[str | None, AuthenticatedUser | None],
) -> dict[str, bool]:
    dossier = _with_review_task_governance_defaults(_dict_value(task.get("dossier")))
    gate_ready = bool(_review_task_report_gate_context(task).get("ready_for_report"))
    writes_allowed = (
        str(task.get("status") or "").strip() != "closed"
        and not bool(_signed_report_context(dossier)["signed"])
    )
    project_key = _review_task_project_key(task)
    if project_key in actor_cache:
        actor = actor_cache[project_key]
    elif project_key is None:
        actor = _global_legacy_formal_actor(state, request=request)
        actor_cache[project_key] = actor
    else:
        try:
            actor = resolve_authenticated_user(
                state,
                x_user_id=request.headers.get("X-User-Id"),
                x_role=request.headers.get("X-Role"),
                project_key=project_key,
            )
        except HTTPException:
            actor = None
        actor_cache[project_key] = actor
    has_sign_permission = bool(
        actor is not None and user_has_permission(actor, Permission.SIGN_REPORTS)
    )
    return {
        "can_sign": gate_ready and writes_allowed and has_sign_permission,
        "gate_ready": gate_ready,
        "writes_allowed": writes_allowed,
    }


def _review_task_report_evidence_source(task: dict[str, object]) -> dict[str, object]:
    payload = _review_task_export_payload(task)
    dossier = _with_review_task_governance_defaults(_dict_value(payload.get("dossier")))
    report_gate = _dict_value(payload.get("report_gate"))
    workpaper = _workpaper_context(dossier)
    attachments = _attachment_items(dossier)
    task_id = str(payload["task_id"])
    workpaper_id = str(workpaper.get("workpaper_id") or "").strip()
    return {
        "id": f"evidence-{task_id}",
        "title": workpaper_id or task_id,
        "kind": "底稿",
        "reference": f"{task_id} · 附件 {len(attachments)} 条",
        "status": "已纳入" if report_gate.get("ready_for_report") else "待补证",
        "href": "/pages/review-tasks",
    }


def _report_workbench_metrics(report_entries: Sequence[dict[str, object]]) -> dict[str, int]:
    return {
        "report_count": len(report_entries),
        "signed_report_count": sum(
            1 for entry in report_entries if entry.get("status") == "已签发"
        ),
        "blocked_report_count": sum(
            1 for entry in report_entries if entry.get("status") == "门禁阻断"
        ),
        "included_finding_count": sum(
            _non_negative_int(entry.get("included_finding_count")) for entry in report_entries
        ),
        "docx_download_count": sum(
            1
            for entry in report_entries
            if _dict_value(entry.get("download_links")).get("report_docx")
        ),
    }


def _report_entry_status(*, ready_for_report: bool, signed: bool) -> str:
    if signed:
        return "已签发"
    if ready_for_report:
        return "草稿"
    return "门禁阻断"


def _report_download_prefix(
    *,
    encoded_task_id: str,
    ready_for_report: bool,
    signed: bool,
) -> str | None:
    if signed:
        return f"/review-tasks/{encoded_task_id}/signed-report"
    if ready_for_report:
        return f"/review-tasks/{encoded_task_id}/report-draft"
    return None


def _report_entry_no(
    *,
    task_id: str,
    signed_report: dict[str, object],
    workpaper: dict[str, object],
) -> str:
    report_id = str(signed_report.get("report_id") or "").strip()
    if report_id:
        return report_id
    workpaper_id = str(workpaper.get("workpaper_id") or "").strip()
    if workpaper_id:
        return workpaper_id
    return f"DRAFT-{task_id}"


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
        "created_by": request.headers.get("X-User-Id") or "page-user",
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
        "created_by": request.headers.get("X-User-Id") or "page-user",
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


def _visible_review_task_by_id(
    state: ApiState,
    task_id: str,
    *,
    request: Request,
    attempted_action: str,
) -> dict[str, object]:
    task = _review_task_by_id(state, task_id)
    _review_task_visible_to_request(
        state,
        task,
        request=request,
        attempted_action=attempted_action,
        raise_on_denied=True,
        context=None,
    )
    return task


def _visible_review_task_for_formal_action(
    state: ApiState,
    task_id: str,
    *,
    request: Request,
    attempted_action: str,
) -> tuple[dict[str, object], AuthenticatedUser]:
    task = _review_task_by_id(state, task_id)
    if _review_task_project_key(task) is None:
        global_actor = _global_legacy_formal_actor(state, request=request)
        if global_actor is not None:
            return task, global_actor
    _review_task_visible_to_request(
        state,
        task,
        request=request,
        attempted_action=attempted_action,
        raise_on_denied=True,
        context=None,
    )
    return task, _require_review_task_permission(
        state,
        task,
        request=request,
        permission=Permission.SIGN_REPORTS,
        attempted_action=attempted_action,
    )


def _visible_review_tasks(
    state: ApiState,
    *,
    request: Request,
    attempted_action: str,
) -> list[dict[str, object]]:
    context = _ReviewTaskVisibilityContext()
    visible: list[dict[str, object]] = []
    hidden_count = 0
    for task in _review_tasks(state):
        if _review_task_visible_to_request(
            state,
            task,
            request=request,
            attempted_action=attempted_action,
            raise_on_denied=False,
            context=context,
        ):
            visible.append(task)
        else:
            hidden_count += 1
    if hidden_count:
        _record_operation_best_effort(
            state,
            "review-task-list-filtered",
            {
                "attempted_action": attempted_action,
                "hidden_count": hidden_count,
                "user_identifier": request.headers.get("X-User-Id") or "anonymous",
                "role": request.headers.get("X-Role") or "anonymous",
                "status_code": 200,
                "reason": "review-task-visibility-filtered",
            },
        )
    return visible


class _ReviewTaskVisibilityContext:
    def __init__(self) -> None:
        self.users_by_project: dict[str, AuthenticatedUser | None] = {}
        self.non_admin_visible_keys: frozenset[str] | None = None
        self.membership_evaluated = False


def _review_task_visible_to_request(
    state: ApiState,
    task: dict[str, object],
    *,
    request: Request,
    attempted_action: str,
    raise_on_denied: bool,
    context: _ReviewTaskVisibilityContext | None,
) -> bool:
    project_key = _review_task_project_key(task)
    if project_key is None:
        controlled_user = getattr(request.state, "authenticated_user", None)
        if not isinstance(controlled_user, AuthenticatedUser):
            return True
        created_by = str(task.get("created_by") or "").strip()
        if _can_access_global_legacy_as_admin(controlled_user) or (
            created_by and created_by == controlled_user.user_identifier
        ):
            return True
        return _review_task_access_denied(
            state,
            task=task,
            attempted_action=attempted_action,
            project_key=None,
            x_user_id=controlled_user.user_identifier,
            x_role=controlled_user.raw_role,
            user=controlled_user,
            raise_on_denied=raise_on_denied,
            record_denial=context is None,
        )

    x_user_id = (request.headers.get("X-User-Id") or "").strip()
    x_role = request.headers.get("X-Role")
    if not x_user_id or x_user_id == "anonymous":
        return _review_task_access_denied(
            state,
            task=task,
            attempted_action=attempted_action,
            project_key=project_key,
            x_user_id="anonymous",
            x_role=x_role,
            user=None,
            raise_on_denied=raise_on_denied,
            record_denial=context is None,
        )
    user: AuthenticatedUser | None
    if context is not None and project_key in context.users_by_project:
        user = context.users_by_project[project_key]
    else:
        try:
            user = resolve_authenticated_user(
                state,
                x_user_id=x_user_id,
                x_role=x_role,
                project_key=project_key,
            )
        except HTTPException:
            user = None
        if context is not None:
            context.users_by_project[project_key] = user
    if user is None:
        return _review_task_access_denied(
            state,
            task=task,
            attempted_action=attempted_action,
            project_key=project_key,
            x_user_id=x_user_id,
            x_role=x_role,
            user=None,
            raise_on_denied=raise_on_denied,
            record_denial=context is None,
        )

    project_member_store = _report_project_member_store(state)
    try:
        exists = project_exists(project_key, project_member_store)
    except SQLAlchemyError as exc:
        _record_operation_best_effort(
            state,
            "review-task-project-visibility-unavailable",
            {
                "attempted_action": attempted_action,
                "task_id": str(task.get("task_id") or ""),
                "user_identifier": user.user_identifier,
                "status_code": 503,
                "reason": "project-store-unavailable",
                "error_type": type(exc).__name__,
            },
        )
        if raise_on_denied:
            raise HTTPException(status_code=503, detail="project store is unavailable") from exc
        return False
    if not exists:
        return _review_task_access_denied(
            state,
            task=task,
            attempted_action=attempted_action,
            project_key=project_key,
            x_user_id=x_user_id,
            x_role=x_role,
            user=user,
            raise_on_denied=raise_on_denied,
            record_denial=context is None,
        )
    if user.role is HospitalRole.ADMIN:
        return True
    try:
        if context is not None and context.membership_evaluated:
            visible_keys = context.non_admin_visible_keys or frozenset()
        else:
            visible_keys = visible_project_keys(
                user_identifier=user.user_identifier,
                is_admin=False,
                store=project_member_store,
            )
            if context is not None:
                context.non_admin_visible_keys = visible_keys
                context.membership_evaluated = True
    except SQLAlchemyError as exc:
        _record_operation_best_effort(
            state,
            "review-task-project-visibility-unavailable",
            {
                "attempted_action": attempted_action,
                "task_id": str(task.get("task_id") or ""),
                "user_identifier": user.user_identifier,
                "role": user.raw_role or user.role.value,
                "effective_role": user.role.value,
                "auth_scope_type": "project",
                "auth_scope_key": project_key,
                "status_code": 503,
                "reason": "project-membership-store-unavailable",
                "error_type": type(exc).__name__,
            },
        )
        raise HTTPException(
            status_code=503,
            detail="project membership store is unavailable",
        ) from exc
    if project_key in visible_keys:
        return True
    return _review_task_access_denied(
        state,
        task=task,
        attempted_action=attempted_action,
        project_key=project_key,
        x_user_id=x_user_id,
        x_role=x_role,
        user=user,
        raise_on_denied=raise_on_denied,
        record_denial=context is None,
    )


def _review_task_access_denied(
    state: ApiState,
    *,
    task: dict[str, object],
    attempted_action: str,
    project_key: str | None,
    x_user_id: str,
    x_role: str | None,
    user: AuthenticatedUser | None,
    raise_on_denied: bool,
    record_denial: bool,
) -> bool:
    if record_denial:
        record_authorization_denied(
            state,
            attempted_action=attempted_action,
            permission="access_project_review_task" if project_key else "access_review_task",
            user_identifier=user.user_identifier if user is not None else x_user_id,
            raw_role=user.raw_role if user is not None else x_role,
            effective_role=user.role.value if user is not None else None,
            auth_source=user.auth_source if user is not None else None,
            profile_status=user.profile_status if user is not None else None,
            auth_scope_type="project" if project_key else "review-task",
            auth_scope_key=project_key or str(task.get("task_id") or ""),
            status_code=404,
            reason="review task not found",
        )
    if raise_on_denied:
        raise HTTPException(status_code=404, detail="review task not found")
    return False


def _can_access_global_legacy_as_admin(user: AuthenticatedUser) -> bool:
    if user.role is not HospitalRole.ADMIN:
        return False
    if user.auth_source == "header":
        return user.auth_scope_type is None and user.auth_scope_key is None
    return (
        user.auth_source == "persistent_role"
        and user.auth_scope_type == "global"
        and user.auth_scope_key is None
    )


def _global_legacy_formal_actor(
    state: ApiState,
    *,
    request: Request,
) -> AuthenticatedUser | None:
    controlled_user = getattr(request.state, "authenticated_user", None)
    user = controlled_user if isinstance(controlled_user, AuthenticatedUser) else None
    if user is None:
        x_user_id = (request.headers.get("X-User-Id") or "").strip()
        if not x_user_id or x_user_id == "anonymous":
            return None
        try:
            user = resolve_authenticated_user(
                state,
                x_user_id=x_user_id,
                x_role=request.headers.get("X-Role"),
                project_key=None,
            )
        except HTTPException:
            return None
    if not user_has_permission(user, Permission.SIGN_REPORTS):
        return None
    if user.auth_source == "header":
        return (
            user
            if user.auth_scope_type is None and user.auth_scope_key is None
            else None
        )
    if (
        user.auth_source == "persistent_role"
        and user.auth_scope_type == "global"
        and user.auth_scope_key is None
    ):
        return user
    return None


def _review_task_project_key(task: dict[str, object]) -> str | None:
    try:
        return review_task_project_key(task)
    except ReviewTaskProjectScopeConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail="review task project scope is inconsistent",
        ) from exc


def _require_review_task_permission(
    state: ApiState,
    task: dict[str, object],
    *,
    request: Request,
    permission: Permission,
    attempted_action: str,
) -> AuthenticatedUser:
    project_key = _review_task_project_key(task)
    x_user_id = (request.headers.get("X-User-Id") or "").strip()
    x_role = request.headers.get("X-Role")
    user: AuthenticatedUser | None = None
    if x_user_id and x_user_id != "anonymous":
        try:
            user = resolve_authenticated_user(
                state,
                x_user_id=x_user_id,
                x_role=x_role,
                project_key=project_key,
            )
        except HTTPException:
            user = None
    if user is None or not user_has_permission(user, permission):
        record_authorization_denied(
            state,
            attempted_action=attempted_action,
            permission=permission,
            user_identifier=user.user_identifier if user is not None else x_user_id or "anonymous",
            raw_role=user.raw_role if user is not None else x_role,
            effective_role=user.role.value if user is not None else None,
            auth_source=user.auth_source if user is not None else None,
            profile_status=user.profile_status if user is not None else None,
            auth_scope_type="project" if project_key else "review-task",
            auth_scope_key=project_key or str(task.get("task_id") or ""),
            status_code=403,
            reason=f"{permission.value} is not allowed",
        )
        raise HTTPException(status_code=403, detail=f"{permission.value} is not allowed")
    return user


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


def _mutate_review_task(
    state: ApiState,
    task_id: str,
    mutator: Callable[[dict[str, object]], dict[str, object]],
) -> dict[str, object]:
    try:
        return _review_task_store(state).mutate_task(task_id, mutator)
    except ReviewTaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail="review task not found") from exc


def _sign_review_task_report_atomically(
    state: ApiState,
    task_id: str,
    *,
    task: dict[str, object],
    actor: AuthenticatedUser,
    request: Request,
    attempted_action: str,
    endpoint: str,
    signoff_note: str,
) -> dict[str, object]:
    expected_project_key = _review_task_project_key(task)

    def mutate(current: dict[str, object]) -> dict[str, object]:
        if _review_task_project_key(current) != expected_project_key:
            raise HTTPException(
                status_code=409,
                detail="review task project scope changed during signoff",
            )
        _ensure_review_task_writable(
            state,
            current,
            request=request,
            attempted_action=attempted_action,
            endpoint=endpoint,
        )
        dossier = _with_review_task_governance_defaults(
            _dict_value(current.get("dossier"))
        )
        signed_report = _build_review_task_signed_report(
            task=current,
            signed_by=actor.user_identifier,
            signoff_note=signoff_note,
        )
        dossier["signed_report"] = signed_report
        return {
            "dossier": dossier,
            "updated_at": _utc_now_iso(),
        }

    updated_task = _mutate_review_task(state, task_id, mutate)
    updated_dossier = _with_review_task_governance_defaults(
        _dict_value(updated_task.get("dossier"))
    )
    return _dict_value(updated_dossier.get("signed_report"))


def _review_task_store(state: ApiState) -> ReviewTaskStore:
    if state.review_task_store is None:
        raise HTTPException(status_code=503, detail="review task store is not configured")
    return state.review_task_store


def _record_operation_best_effort(
    state: ApiState,
    action: str,
    payload: dict[str, object],
) -> None:
    try:
        record_operation(state, action, payload)
    except SQLAlchemyError as exc:
        _record_local_operation(
            state,
            f"{action}-audit-degraded",
            {**payload, "error_type": type(exc).__name__},
        )


def _audit_findings(
    state: ApiState,
    *,
    review_status: str | None = None,
    project_keys: frozenset[str] | None = None,
) -> list[dict[str, object]]:
    return _audit_finding_store(state).list_findings(
        review_status=review_status,
        project_keys=project_keys,
    )


def _audit_finding_by_key(state: ApiState, finding_key: str) -> dict[str, object]:
    try:
        return _audit_finding_store(state).get_finding(finding_key)
    except AuditFindingNotFoundError as exc:
        raise HTTPException(status_code=404, detail="audit finding not found") from exc


def _visible_audit_finding_by_key(
    state: ApiState,
    finding_key: str,
    *,
    request: Request,
    attempted_action: str,
) -> dict[str, object]:
    user = _audit_finding_authorized_user(
        state,
        request=request,
        attempted_action=attempted_action,
    )
    finding = _audit_finding_by_key(state, finding_key)
    visible_keys = _audit_finding_visible_project_keys(
        state,
        user=user,
        attempted_action=attempted_action,
    )
    project_key = str(finding.get("project_key") or "").strip()
    if not project_key or project_key not in visible_keys:
        raise HTTPException(status_code=404, detail="audit finding not found")
    return finding


def _audit_finding_authorized_user(
    state: ApiState,
    *,
    request: Request,
    attempted_action: str,
) -> AuthenticatedUser:
    permission = Permission.ANALYZE_DATA
    x_user_id = (request.headers.get("X-User-Id") or "").strip()
    x_role = request.headers.get("X-Role")
    if not x_user_id or x_user_id == "anonymous":
        record_authorization_denied(
            state,
            attempted_action=attempted_action,
            permission=permission,
            user_identifier="anonymous",
            raw_role=x_role,
            status_code=401,
            reason="X-User-Id header is required",
        )
        raise HTTPException(status_code=401, detail="X-User-Id header is required")
    try:
        user = resolve_authenticated_user(
            state,
            x_user_id=x_user_id,
            x_role=x_role,
        )
    except HTTPException as exc:
        record_authorization_denied(
            state,
            attempted_action=attempted_action,
            permission=permission,
            user_identifier=x_user_id,
            raw_role=x_role,
            status_code=exc.status_code,
            reason=str(exc.detail),
        )
        raise
    if user_has_permission(user, permission):
        return user
    record_authorization_denied(
        state,
        attempted_action=attempted_action,
        permission=permission,
        user_identifier=user.user_identifier,
        raw_role=user.raw_role,
        effective_role=user.role.value,
        auth_source=user.auth_source,
        profile_status=user.profile_status,
        auth_scope_type=user.auth_scope_type,
        auth_scope_key=user.auth_scope_key,
        status_code=403,
        reason=f"{permission.value} requires a higher hospital role",
    )
    raise HTTPException(status_code=403, detail=f"{permission.value} is not allowed")


def _audit_finding_visible_project_keys(
    state: ApiState,
    *,
    user: AuthenticatedUser,
    attempted_action: str,
) -> frozenset[str]:
    try:
        return visible_project_keys(
            user_identifier=user.user_identifier,
            is_admin=user.role is HospitalRole.ADMIN,
            store=_report_project_member_store(state),
        )
    except SQLAlchemyError as exc:
        _record_operation_best_effort(
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


def _sync_audit_finding_review_status(
    state: ApiState,
    review_task_id: str,
    review_status: str,
    *,
    project_key: str | None,
) -> list[dict[str, object]]:
    if state.audit_finding_store is None or project_key is None:
        return []
    try:
        return state.audit_finding_store.sync_review_task_status(
            review_task_id,
            review_status,
            project_keys=frozenset({project_key}),
        )
    except (SQLAlchemyError, ValueError):
        return []


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
        "rectification_open": sum(
            1
            for task in tasks
            if _rectification_context(_dict_value(task.get("dossier")))["status"]
            in {"pending-rectification", "in-progress", "submitted", "returned"}
        ),
        "rectification_accepted": sum(
            1
            for task in tasks
            if _rectification_context(_dict_value(task.get("dossier")))["status"] == "accepted"
        ),
        "status_counts": status_counts,
    }


def _review_task_export_payload(task: dict[str, object]) -> dict[str, object]:
    dossier = _with_review_task_governance_defaults(_dict_value(task.get("dossier")))
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
        "created_by": task.get("created_by"),
        "reviewer_note": task["reviewer_note"],
        "conclusion": task["conclusion"],
        "source": task.get("source", "chat-dossier"),
        "report_gate": _review_task_report_gate_context({**task, "dossier": dossier}),
        "close_gate": _review_task_close_gate_context({**task, "dossier": dossier}),
        "rectification": _rectification_context(dossier),
        "dossier": dossier,
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
        "project_key": finding.get("project_key"),
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
    close_gate = _dict_value(payload.get("close_gate"))
    report_ready_label = (
        "可进入报告草稿" if report_gate.get("ready_for_report") else "不得进入报告草稿"
    )
    workpaper = _dict_value(dossier.get("workpaper"))
    owner_signoff = _dict_value(dossier.get("owner_signoff"))
    report_draft = _report_draft_context(dossier, payload)
    attachments = _attachment_items(dossier)
    rectification = _rectification_context(dossier)
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
            "## 整改跟踪",
            "",
        ]
    )
    if rectification["created"]:
        lines.extend(
            [
                f"- 整改编号：{rectification['rectification_id']}",
                f"- 整改状态：{rectification['status_label']}",
                f"- 责任科室：{rectification['responsible_department'] or '未填写'}",
                f"- 责任人：{rectification['responsible_owner'] or '未填写'}",
                f"- 完成期限：{rectification['due_date'] or '未填写'}",
                f"- 整改要求：{rectification['action_request'] or '未填写'}",
                f"- 最新进展：{rectification['progress_note'] or '未填写'}",
                f"- 关联正式报告：{rectification['source_report_id'] or '未签发'}",
                f"- 正文 SHA256：{rectification['source_report_sha256'] or '未记录'}",
                f"- 事件数量：{rectification['event_count']}",
            ]
        )
    else:
        lines.append("- 未生成整改事项。")
    lines.extend(
        [
            "",
            "## 结案门禁",
            "",
            f"- 结案状态：{close_gate.get('status_label') or '不得结案'}",
        ]
    )
    for check in _dict_list(close_gate.get("checks")):
        lines.append(
            f"- [{'x' if check.get('pass') else ' '}] {check.get('label')}: {check.get('message')}"
        )
    lines.extend(
        [
            "",
            "## 底稿",
            "",
            _render_review_task_dossier_markdown(dossier),
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _render_review_task_dossier_markdown(dossier: dict[str, object]) -> str:
    if dossier.get("format") == "audit-finding-dossier-v1":
        return _render_audit_finding_dossier_markdown(dossier)
    if dossier.get("format") == "query-history-review-task-dossier-v1":
        return _render_query_history_review_task_dossier_markdown(dossier)
    if dossier.get("format") == "report-template-draft-dossier-v1":
        return _render_report_template_draft_dossier_markdown(dossier)
    return _render_audit_dossier_markdown(dossier)


def _render_query_history_review_task_dossier_markdown(
    dossier: dict[str, object],
) -> str:
    snapshot = _dict_value(dossier.get("query_history_snapshot"))
    filters = _dict_value(snapshot.get("filters"))
    retrieved_chunk_ids = _string_list(snapshot.get("retrieved_chunk_ids"))
    workpaper = _dict_value(dossier.get("workpaper"))
    owner_signoff = _dict_value(dossier.get("owner_signoff"))
    answer_summary = str(snapshot.get("answer_summary") or "未保存回答摘要。")
    lines = [
        "# AuditScope 历史对话人工复核底稿",
        "",
        f"- 历史记录 ID：{snapshot.get('query_log_id') or '未记录'}",
        f"- 项目：{dossier.get('project_key') or '未记录'}",
        f"- 创建人：{dossier.get('created_by') or '未记录'}",
        f"- 原始查询时间：{snapshot.get('created_at') or '未记录'}",
        f"- 引用数量：{snapshot.get('citation_count') or 0}",
        f"- 底稿状态：{workpaper.get('status_label') or '未建底稿'}",
        f"- 负责人确认：{owner_signoff.get('status_label') or '未提交确认'}",
        "",
        "> 历史对话快照仅作为人工复核输入，不构成审计疑点或结论。",
        "",
        "## 原始问题",
        "",
        str(snapshot.get("question") or "未记录问题。"),
        "",
        "## 回答摘要",
        "",
        answer_summary,
        "",
        "## 检索条件",
        "",
        "```json",
        json.dumps(filters, ensure_ascii=False, indent=2),
        "```",
        "",
        "## 引用片段标识",
        "",
    ]
    if retrieved_chunk_ids:
        lines.extend(f"- `{chunk_id}`" for chunk_id in retrieved_chunk_ids)
    else:
        lines.append("- 未记录引用片段。")
    return "\n".join(lines).rstrip() + "\n"


def _render_report_template_draft_dossier_markdown(dossier: dict[str, object]) -> str:
    draft = _dict_value(dossier.get("report_template_draft"))
    field_values = _dict_value(draft.get("field_values"))
    lines = [
        "# AuditScope 模板底稿草稿",
        "",
        f"- 模板：{draft.get('template_name') or '未记录'}",
        f"- 模板 ID：{draft.get('template_id') or '未记录'}",
        f"- 分类：{draft.get('category_id') or '未记录'}",
        f"- 项目：{draft.get('project_key') or '未记录'}",
        f"- 创建人：{draft.get('created_by') or '未记录'}",
        f"- 草稿状态：{draft.get('status') or 'draft'}",
        "",
        "## 受控模板字段",
        "",
    ]
    if field_values:
        for key, value in field_values.items():
            lines.append(f"- {key}：")
            value_lines = str(value).splitlines() or [""]
            lines.extend(f"DATA | {line}" for line in value_lines)
    else:
        lines.append("- 未填写模板字段。")
    lines.extend(
        [
            "",
            "> 本文件为受控模板草稿，不是正式审计报告，未调用外部 provider。",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _render_audit_finding_dossier_markdown(dossier: dict[str, object]) -> str:
    evidence_items = _dict_list(dossier.get("evidence_items"))
    lines = [
        "# AuditScope 规则疑点底稿导出",
        "",
        f"- 生成时间：{dossier.get('generated_at') or '未记录'}",
        f"- 疑点编号：{dossier.get('finding_key') or '未记录'}",
        f"- 疑点类型：{dossier.get('finding_type') or '未记录'}",
        f"- 严重程度：{dossier.get('severity') or '未记录'}",
        f"- 疑点状态：{dossier.get('status') or '未记录'}",
        f"- 复核状态：{dossier.get('review_status') or '未记录'}",
        f"- 审计任务：{dossier.get('audit_task_key') or '未记录'}",
        f"- 规则运行：{dossier.get('audit_run_key') or '未记录'}",
        f"- 规则：{dossier.get('rule_key') or '未记录'}",
        f"- 规则版本：{dossier.get('rule_version_key') or '未记录'}",
        f"- 证据项数量：{len(evidence_items)}",
        "",
        f"> {dossier.get('review_notice') or '该疑点需要人工复核。'}",
        "",
        "## 源记录定位",
        "",
        "```json",
        json.dumps(dossier.get("source_record_locator", {}), ensure_ascii=False, indent=2),
        "```",
        "",
        "## 计算过程",
        "",
        "```json",
        json.dumps(dossier.get("calculation_trace", {}), ensure_ascii=False, indent=2),
        "```",
        "",
        "## 证据项",
        "",
    ]
    if evidence_items:
        for item in evidence_items:
            lines.extend(
                [
                    f"### {item.get('citation_id') or item.get('evidence_type') or '证据项'}",
                    "",
                    f"- 类型：{item.get('evidence_type') or '未记录'}",
                    f"- chunk: `{item.get('chunk_id') or 'n/a'}`",
                    f"- index: `{item.get('index_version_key') or 'n/a'}`",
                    f"- package: `{item.get('source_package_version_key') or 'n/a'}`",
                    "",
                    str(item.get("snippet") or "未记录证据片段。"),
                    "",
                ]
            )
    else:
        lines.append("- 未绑定证据项。")
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
        "signed_report": _signed_report_context(dossier),
        "rectification": _rectification_context(dossier),
        "report_gate": _review_task_report_gate_context({**task, "dossier": dossier}),
        "close_gate": _review_task_close_gate_context({**task, "dossier": dossier}),
        "readonly": str(task.get("status", "")) == "closed",
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


def _review_task_close_gate_context(task: dict[str, object]) -> dict[str, object]:
    status = str(task.get("status", "pending-review"))
    dossier = _with_review_task_governance_defaults(_dict_value(task.get("dossier")))
    signed_report = _signed_report_context(dossier)
    rectification = _rectification_context(dossier)
    requires_rectification = (
        status == "confirmed-violation"
        or bool(signed_report["signed"])
        or bool(rectification["created"])
    )
    if requires_rectification:
        checks = [
            {
                "key": "signed-report",
                "label": "正式报告签发",
                "pass": bool(signed_report["signed"]),
                "message": "正式报告已签发" if signed_report["signed"] else "正式报告未签发",
            },
            {
                "key": "rectification-created",
                "label": "整改事项生成",
                "pass": bool(rectification["created"]),
                "message": "整改事项已生成" if rectification["created"] else "未生成整改事项",
            },
            {
                "key": "rectification-accepted",
                "label": "整改验收",
                "pass": rectification["status"] == "accepted",
                "message": "整改已验收" if rectification["status"] == "accepted" else "整改未验收",
            },
        ]
    else:
        checks = [
            {
                "key": "rectification-not-required",
                "label": "整改要求",
                "pass": True,
                "message": "当前任务无需整改验收",
            }
        ]
    ready_to_close = all(bool(check["pass"]) for check in checks)
    return {
        "ready_to_close": ready_to_close,
        "status_label": "允许结案" if ready_to_close else "不得结案",
        "requires_rectification": requires_rectification,
        "checks": checks,
    }


def _ensure_review_task_can_close(task: dict[str, object]) -> None:
    close_gate = _review_task_close_gate_context(task)
    if not close_gate["ready_to_close"]:
        raise HTTPException(
            status_code=409,
            detail="review task rectification must be accepted before closing",
        )


def _ensure_review_task_writable(
    state: ApiState,
    task: dict[str, object],
    *,
    request: Request,
    attempted_action: str,
    endpoint: str,
) -> None:
    if str(task.get("status", "")).strip() == "closed":
        detail = "review task is closed and read-only"
        record_operation(
            state,
            "review-task-readonly-write-blocked",
            {
                "task_id": str(task.get("task_id", "")),
                "task_status": "closed",
                "attempted_action": attempted_action,
                "endpoint": endpoint,
                "status_code": 409,
                "reason": detail,
                "user_identifier": request.headers.get("X-User-Id") or "anonymous",
                "role": request.headers.get("X-Role") or "auditor",
            },
        )
        raise HTTPException(status_code=409, detail=detail)


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
    normalized["signed_report"] = _signed_report_context(normalized)
    normalized["rectification"] = _rectification_context(normalized)
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


def _signed_report_context(dossier: dict[str, object]) -> dict[str, object]:
    signed_report = _dict_value(dossier.get("signed_report"))
    content = str(signed_report.get("content", ""))
    content_sha256 = str(signed_report.get("content_sha256", "")).strip()
    status = str(signed_report.get("status", "")).strip()
    signed = status == "signed" and bool(content_sha256) and bool(content)
    result: dict[str, object] = {
        "signed": signed,
        "status": "signed" if signed else "unsigned",
        "status_label": "正式报告已签发" if signed else "正式报告未签发",
        "report_id": str(signed_report.get("report_id", "")).strip(),
        "signed_by": str(signed_report.get("signed_by", "")).strip(),
        "signed_at": str(signed_report.get("signed_at", "")).strip(),
        "signoff_note": str(signed_report.get("signoff_note", "")).strip(),
        "content_sha256": content_sha256,
        "content_byte_size": _non_negative_int(signed_report.get("content_byte_size")),
        "attachment_count": _non_negative_int(signed_report.get("attachment_count")),
        "source_format": str(signed_report.get("source_format", "")).strip(),
        "source_generated_at": str(signed_report.get("source_generated_at", "")).strip(),
        "content": content,
    }
    return result


def _build_review_task_signed_report(
    *,
    task: dict[str, object],
    signed_by: str,
    signoff_note: str,
) -> dict[str, object]:
    dossier = _with_review_task_governance_defaults(_dict_value(task.get("dossier")))
    if _signed_report_context(dossier)["signed"]:
        raise HTTPException(status_code=409, detail="review task report is already signed")
    draft_payload = _review_task_report_draft_payload(task)
    content = _render_review_task_report_draft_markdown(draft_payload)
    content_bytes = content.encode("utf-8")
    signed_at = _utc_now_iso()
    report_id = f"signed-report-{uuid4().hex[:12]}"
    return {
        "format": "review-task-signed-report-v1",
        "status": "signed",
        "report_id": report_id,
        "signed_by": signed_by,
        "signed_at": signed_at,
        "signoff_note": signoff_note,
        "content_sha256": hashlib.sha256(content_bytes).hexdigest(),
        "content_byte_size": len(content_bytes),
        "content_media_type": "text/markdown; charset=utf-8",
        "attachment_count": len(_dict_list(draft_payload.get("attachments"))),
        "source_format": str(draft_payload.get("format", "")),
        "source_generated_at": str(draft_payload.get("generated_at", "")),
        "content": content,
    }


def _review_task_signed_report_payload(task: dict[str, object]) -> dict[str, object]:
    task_payload = _review_task_export_payload(task)
    dossier = _with_review_task_governance_defaults(_dict_value(task_payload.get("dossier")))
    signed_report = _signed_report_context(dossier)
    if not signed_report["signed"]:
        raise HTTPException(status_code=409, detail="review task report is not signed")
    return {
        "format": "review-task-signed-report-v1",
        "generated_at": _utc_now_iso(),
        "task_id": task_payload["task_id"],
        "status": task_payload["status"],
        "status_label": task_payload["status_label"],
        "question": task_payload["question"],
        "report_gate": task_payload["report_gate"],
        "signed_report": signed_report,
        "source_task": task_payload,
    }


def _rectification_context(dossier: dict[str, object]) -> dict[str, object]:
    rectification = _dict_value(dossier.get("rectification"))
    rectification_id = str(rectification.get("rectification_id", "")).strip()
    status = str(rectification.get("status", "not-created")).strip()
    if status not in RECTIFICATION_STATUS_LABELS:
        status = "not-created"
    created = bool(rectification_id) and status != "not-created"
    if not created:
        status = "not-created"
    events = _rectification_events(rectification)
    return {
        "created": created,
        "rectification_id": rectification_id if created else "",
        "status": status,
        "status_label": RECTIFICATION_STATUS_LABELS[status],
        "responsible_department": str(rectification.get("responsible_department", "")).strip(),
        "responsible_owner": str(rectification.get("responsible_owner", "")).strip(),
        "due_date": str(rectification.get("due_date", "")).strip(),
        "action_request": str(rectification.get("action_request", "")).strip(),
        "progress_note": str(rectification.get("progress_note", "")).strip(),
        "source_report_id": str(rectification.get("source_report_id", "")).strip(),
        "source_report_sha256": str(rectification.get("source_report_sha256", "")).strip(),
        "created_at": str(rectification.get("created_at", "")).strip(),
        "updated_at": str(rectification.get("updated_at", "")).strip(),
        "event_count": len(events),
        "events": events,
    }


def _rectification_events(rectification: dict[str, object]) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for item in _dict_list(rectification.get("events")):
        from_status = str(item.get("from_status", "not-created")).strip()
        to_status = str(item.get("to_status", "not-created")).strip()
        if from_status not in RECTIFICATION_STATUS_LABELS:
            from_status = "not-created"
        if to_status not in RECTIFICATION_STATUS_LABELS:
            to_status = "not-created"
        events.append(
            {
                "event_id": str(item.get("event_id", "")).strip(),
                "recorded_at": str(item.get("recorded_at", "")).strip(),
                "from_status": from_status,
                "from_status_label": RECTIFICATION_STATUS_LABELS[from_status],
                "to_status": to_status,
                "to_status_label": RECTIFICATION_STATUS_LABELS[to_status],
                "actor": str(item.get("actor", "")).strip(),
                "note": str(item.get("note", "")).strip(),
            }
        )
    return events


def _build_review_task_rectification(
    *,
    task: dict[str, object],
    form: Mapping[str, Sequence[str]],
    rectification_status: str,
    actor_identifier: str,
) -> dict[str, object]:
    dossier = _with_review_task_governance_defaults(_dict_value(task.get("dossier")))
    signed_report = _signed_report_context(dossier)
    if not signed_report["signed"]:
        raise HTTPException(
            status_code=409,
            detail="review task report must be signed before rectification tracking",
        )
    existing = _rectification_context(dossier)
    now = _utc_now_iso()
    report_draft = _report_draft_context(dossier, task)
    rectification_id = str(existing["rectification_id"] or f"rectification-{uuid4().hex[:12]}")
    previous_status = str(existing["status"] if existing["created"] else "not-created")
    events = list(_dict_list(existing.get("events")))
    progress_note = _form_optional_str(form, "progress_note")
    events.append(
        {
            "event_id": f"rectification-event-{uuid4().hex[:12]}",
            "recorded_at": now,
            "from_status": previous_status,
            "from_status_label": RECTIFICATION_STATUS_LABELS[previous_status],
            "to_status": rectification_status,
            "to_status_label": RECTIFICATION_STATUS_LABELS[rectification_status],
            "actor": actor_identifier,
            "note": progress_note,
        }
    )
    action_request = _form_optional_str(form, "action_request") or str(
        existing.get("action_request") or report_draft["rectification_request"]
    )
    return {
        "format": "review-task-rectification-v1",
        "rectification_id": rectification_id,
        "status": rectification_status,
        "status_label": RECTIFICATION_STATUS_LABELS[rectification_status],
        "responsible_department": _form_optional_str(form, "responsible_department"),
        "responsible_owner": _form_optional_str(form, "responsible_owner"),
        "due_date": _form_optional_str(form, "due_date"),
        "action_request": action_request,
        "progress_note": progress_note,
        "source_report_id": signed_report["report_id"],
        "source_report_sha256": signed_report["content_sha256"],
        "created_at": str(existing.get("created_at") or now),
        "updated_at": now,
        "event_count": len(events),
        "events": events,
    }


def _review_task_rectification_payload(task: dict[str, object]) -> dict[str, object]:
    task_payload = _review_task_export_payload(task)
    dossier = _with_review_task_governance_defaults(_dict_value(task_payload.get("dossier")))
    rectification = _rectification_context(dossier)
    if not rectification["created"]:
        raise HTTPException(status_code=409, detail="review task rectification is not created")
    signed_report = _signed_report_context(dossier)
    return {
        "format": "review-task-rectification-v1",
        "generated_at": _utc_now_iso(),
        "task_id": task_payload["task_id"],
        "status": task_payload["status"],
        "status_label": task_payload["status_label"],
        "question": task_payload["question"],
        "rectification": rectification,
        "signed_report": signed_report,
        "source_task": task_payload,
    }


def _render_review_task_rectification_markdown(payload: dict[str, object]) -> str:
    rectification = _dict_value(payload.get("rectification"))
    events = _dict_list(rectification.get("events"))
    lines = [
        "# AuditScope 整改跟踪记录",
        "",
        f"- 生成时间：{payload['generated_at']}",
        f"- 任务编号：{payload['task_id']}",
        f"- 整改编号：{rectification.get('rectification_id')}",
        f"- 整改状态：{rectification.get('status_label')} ({rectification.get('status')})",
        f"- 责任科室：{rectification.get('responsible_department') or '未填写'}",
        f"- 责任人：{rectification.get('responsible_owner') or '未填写'}",
        f"- 完成期限：{rectification.get('due_date') or '未填写'}",
        f"- 关联正式报告：{rectification.get('source_report_id') or '未签发'}",
        f"- 正文 SHA256：{rectification.get('source_report_sha256') or '未记录'}",
        "",
        "## 整改要求",
        "",
        str(rectification.get("action_request") or "未填写"),
        "",
        "## 最新进展",
        "",
        str(rectification.get("progress_note") or "未填写"),
        "",
        "## 状态事件",
        "",
    ]
    if events:
        for event in events:
            lines.append(
                f"- {event.get('recorded_at') or '未记录时间'} | "
                f"{event.get('from_status_label')} -> {event.get('to_status_label')} | "
                f"{event.get('note') or '无说明'}"
            )
    else:
        lines.append("- 未记录事件。")
    return "\n".join(lines).rstrip() + "\n"


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
            "title": SOURCE_COLLECTION_UI.get(collection, {}).get("title", collection.value),
            "description": SOURCE_COLLECTION_UI.get(collection, {}).get(
                "description",
                "二级分类知识库，完成入库后可用于限定检索范围。",
            ),
            "audit_hint": SOURCE_COLLECTION_UI.get(collection, {}).get(
                "audit_hint",
                "用于补充背景资料和分类检索。",
            ),
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
