from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path
from typing import Annotated, Literal
from uuid import NAMESPACE_URL, uuid5

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict

from medical_audit_kb.api.app import ApiState, get_api_state, record_operation
from medical_audit_kb.api.chat_models import (
    ChatModelAlias,
    ChatModelUnavailableError,
    answer_generation_provider_for_alias,
)
from medical_audit_kb.api.routes_analytics import (
    MAX_UPLOAD_BYTES as MAX_TABLE_UPLOAD_BYTES,
)
from medical_audit_kb.api.routes_analytics import (
    SUPPORTED_EXTENSIONS as SUPPORTED_TABLE_EXTENSIONS,
)
from medical_audit_kb.api.routes_analytics import (
    _build_response as _build_table_response,
)
from medical_audit_kb.api.routes_analytics import (
    _read_csv_rows,
    _read_workbook_rows,
)
from medical_audit_kb.domain.constants import FileErrorType, SourceCollection
from medical_audit_kb.generation.citations import Citation, EvidenceType
from medical_audit_kb.ingestion.extractors import ExtractionStatus, extract_file
from medical_audit_kb.ocr.unlimited_ocr import (
    UnlimitedOcrClientProtocol,
    UnlimitedOcrError,
    UnlimitedOcrResult,
)

router = APIRouter(prefix="/chat")

SUPPORTED_DOCUMENT_EXTENSIONS = {
    "bmp",
    "jpeg",
    "jpg",
    "md",
    "pdf",
    "png",
    "tif",
    "tiff",
    "txt",
    "webp",
}
OCR_IMAGE_EXTENSIONS = SUPPORTED_DOCUMENT_EXTENSIONS.difference({"md", "pdf", "txt", "webp"})
MAX_CONTEXT_CHARS = 6_000
MAX_SNIPPET_CHARS = 1_200


class ChatAttachmentAnalysisResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["chat-attachment-analysis-v1"] = "chat-attachment-analysis-v1"
    file_name: str
    extension: str
    mode: Literal["table-analysis", "document-summary"]
    model_alias: ChatModelAlias | None
    model_status: Literal["selected_provider", "default_fallback"]
    answer: str
    extracted_preview: str
    summary_items: list[str]
    boundaries: dict[str, bool | str]


@router.post("/attachments/analyze", response_model=ChatAttachmentAnalysisResponse)
async def analyze_chat_attachment(
    file: Annotated[UploadFile, File()],
    state: Annotated[ApiState, Depends(get_api_state)],
    model: Annotated[ChatModelAlias | None, Form()] = None,
    mode: Annotated[Literal["auto", "table-analysis", "document-summary"], Form()] = "auto",
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
) -> ChatAttachmentAnalysisResponse:
    file_name = file.filename or "chat-attachment"
    extension = _file_extension(file_name)
    resolved_mode = _resolve_mode(extension, mode)
    content = await file.read()
    if not content:
        raise HTTPException(status_code=422, detail="附件内容为空，请重新选择文件。")
    if len(content) > MAX_TABLE_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="附件超过大小限制，请压缩或拆分后重试。")

    if resolved_mode == "table-analysis":
        context, summary_items = _table_context(
            file_name=file_name,
            extension=extension,
            content=content,
        )
    else:
        context, summary_items, ocr_result = await _document_context(
            file_name=file_name,
            extension=extension,
            content=content,
            ocr_client=state.ocr_client,
        )
    if resolved_mode == "table-analysis":
        ocr_result = None
    provider = None
    if model is not None:
        try:
            provider = answer_generation_provider_for_alias(model)
        except ChatModelUnavailableError as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "chat_model_unavailable",
                    "model": exc.alias.value,
                    "reason": exc.reason,
                },
            ) from exc
    citation = _attachment_citation(
        file_name=file_name,
        extension=extension,
        content=content,
        context=context,
    )
    prompt = _attachment_prompt(mode=resolved_mode, file_name=file_name)
    if provider is None:
        answer = _fallback_attachment_answer(
            mode=resolved_mode,
            file_name=file_name,
            summary_items=summary_items,
            context=context,
        )
        model_status: Literal["selected_provider", "default_fallback"] = "default_fallback"
    else:
        try:
            answer = provider.generate_answer(prompt, [citation])
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail="chat attachment model call failed",
            ) from exc
        model_status = "selected_provider"

    record_operation(
        state,
        "chat-attachment-analyze",
        {
            "file_name": file_name,
            "extension": extension,
            "mode": resolved_mode,
            "model": model.value if model is not None else None,
            "model_status": model_status,
            "created_by": x_user_id,
            "size_bytes": len(content),
            "provider_call": provider is not None or ocr_result is not None,
            "answer_provider_call": provider is not None,
            "ocr_call": ocr_result is not None,
            "ocr_model": ocr_result.model if ocr_result is not None else None,
            "ocr_source_commit": (
                ocr_result.source_commit if ocr_result is not None else None
            ),
        },
    )
    return ChatAttachmentAnalysisResponse(
        file_name=file_name,
        extension=extension,
        mode=resolved_mode,
        model_alias=model,
        model_status=model_status,
        answer=answer,
        extracted_preview=_truncate(context, 800),
        summary_items=summary_items,
        boundaries={
            "database_write": False,
            "object_storage_write": False,
            "index_write": False,
            "provider_call": provider is not None or ocr_result is not None,
            "answer_provider_call": provider is not None,
            "ocr_call": ocr_result is not None,
            "ocr_engine": ocr_result.model if ocr_result is not None else "not-used",
        },
    )


def _resolve_mode(
    extension: str,
    requested_mode: Literal["auto", "table-analysis", "document-summary"],
) -> Literal["table-analysis", "document-summary"]:
    if requested_mode != "auto":
        if requested_mode == "table-analysis" and extension not in SUPPORTED_TABLE_EXTENSIONS:
            raise HTTPException(status_code=422, detail="file is not a supported table format")
        if requested_mode == "document-summary" and extension not in SUPPORTED_DOCUMENT_EXTENSIONS:
            raise HTTPException(status_code=422, detail="file is not a supported document format")
        return requested_mode
    if extension in SUPPORTED_TABLE_EXTENSIONS:
        return "table-analysis"
    if extension in SUPPORTED_DOCUMENT_EXTENSIONS:
        return "document-summary"
    raise HTTPException(status_code=422, detail="unsupported chat attachment extension")


def _table_context(*, file_name: str, extension: str, content: bytes) -> tuple[str, list[str]]:
    try:
        if extension == "csv":
            sheet_name = None
            rows = _read_csv_rows(content)
        else:
            sheet_name, rows = _read_workbook_rows(content)
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=422,
            detail="table file text encoding is not supported",
        ) from exc
    if not rows:
        raise HTTPException(status_code=422, detail="table file does not contain tabular rows")

    response = _build_table_response(
        file_name=file_name,
        size_bytes=len(content),
        extension=extension,
        rows=rows,
        sheet_name=sheet_name,
    )
    summary_items = [
        f"行数：{response.row_count}",
        f"字段数：{len(response.columns)}",
        f"空单元格：{response.empty_cell_count}",
        f"重复行：{response.duplicate_row_count}",
    ]
    column_lines = [
        (
            f"- {column.name}：{column.type}，"
            f"空值 {column.empty_count}，样例 {', '.join(column.sample_values[:3])}"
        )
        for column in response.columns[:16]
    ]
    context = "\n".join(
        [
            f"文件：{file_name}",
            f"工作表：{response.sheet_name or '默认'}",
            *summary_items,
            "字段画像：",
            *column_lines,
            "质量提示：",
            *response.quality_findings,
            "审计信号：",
            *response.audit_signals,
            "建议：",
            *response.recommendations,
        ]
    )
    return _truncate(context, MAX_CONTEXT_CHARS), summary_items


async def _document_context(
    *,
    file_name: str,
    extension: str,
    content: bytes,
    ocr_client: UnlimitedOcrClientProtocol | None,
) -> tuple[str, list[str], UnlimitedOcrResult | None]:
    result = None
    if extension not in OCR_IMAGE_EXTENSIONS:
        with tempfile.TemporaryDirectory(prefix="medical-audit-chat-upload-") as tmp_dir:
            path = Path(tmp_dir) / f"upload.{extension}"
            path.write_bytes(content)
            result = extract_file(path)
    ocr_result: UnlimitedOcrResult | None = None
    should_ocr = extension in OCR_IMAGE_EXTENSIONS or (
        result is not None
        and (
            result.status != ExtractionStatus.EXTRACTED
            or not result.text.strip()
        )
    )
    if should_ocr:
        if ocr_client is None:
            raise HTTPException(
                status_code=422,
                detail=_document_extraction_error_detail(
                    extension=extension,
                    error_type=result.error_type if result is not None else None,
                ),
            )
        try:
            ocr_result = await ocr_client.extract_text(
                file_name=file_name,
                extension=extension,
                content=content,
            )
        except UnlimitedOcrError as exc:
            raise HTTPException(
                status_code=502,
                detail="OCR 识别服务未完成处理，请检查服务状态后重试。",
            ) from exc
        text = ocr_result.text.strip()
    else:
        assert result is not None
        text = result.text.strip()
    if not text:
        raise HTTPException(
            status_code=422,
            detail="文档未检测到可读取文字，请确认内容后重新上传。",
        )
    lines = text.splitlines()
    summary_items = [
        (
            f"OCR 页数：{ocr_result.page_count}"
            if ocr_result is not None
            else f"文本段落：{len(result.text_segments) if result is not None else 0}"
        ),
        f"可读行数：{len(lines)}",
        f"字符数：{len(text)}",
    ]
    if ocr_result is not None:
        summary_items.append(f"OCR 引擎：{ocr_result.model}")
    context = "\n".join([f"文件：{file_name}", *summary_items, "正文摘录：", text])
    return _truncate(context, MAX_CONTEXT_CHARS), summary_items, ocr_result


def _document_extraction_error_detail(
    *,
    extension: str,
    error_type: FileErrorType | None,
) -> str:
    if error_type == FileErrorType.LOW_QUALITY_TEXT:
        if extension == "pdf":
            return (
                "PDF 未检测到可读取文字，可能是扫描件或图片型 PDF。"
                "请先进行 OCR 识别，或上传可搜索文字版 PDF。"
            )
        return "文档未检测到可读取文字，请确认内容后重新上传。"
    if extension in OCR_IMAGE_EXTENSIONS:
        return "图片 OCR 服务尚未启用，请联系管理员完成 Unlimited-OCR 服务配置。"
    if extension == "pdf":
        return "PDF 解析失败，文件可能损坏、加密或格式不完整。请重新导出后再上传。"
    return "文档解析失败，请确认文件完整且格式正确后重试。"


def _attachment_prompt(
    *,
    mode: Literal["table-analysis", "document-summary"],
    file_name: str,
) -> str:
    if mode == "table-analysis":
        return (
            f"请对用户上传的表格《{file_name}》做审计数据分析。"
            "输出字段质量、异常线索、下一步核验建议，并在关键判断后保留引用标记 [C1]。"
        )
    return (
        f"请对用户上传的文档《{file_name}》做审计口径总结。"
        "输出核心内容、可引用事项、疑点线索和下一步核验建议，并在关键判断后保留引用标记 [C1]。"
    )


def _fallback_attachment_answer(
    *,
    mode: Literal["table-analysis", "document-summary"],
    file_name: str,
    summary_items: list[str],
    context: str,
) -> str:
    headline = "数据分析" if mode == "table-analysis" else "文档总结"
    summary = "；".join(summary_items[:4])
    preview = _truncate(context, 360)
    return (
        f"{headline}已基于后端解析器完成，当前未调用外部模型。"
        f"文件《{file_name}》的结构摘要：{summary}。\n\n"
        f"可先参考以下摘录继续追问：\n{preview}"
    )


def _attachment_citation(
    *,
    file_name: str,
    extension: str,
    content: bytes,
    context: str,
) -> Citation:
    digest = hashlib.sha256(content).hexdigest()
    return Citation(
        citation_id="C1",
        evidence_type=EvidenceType.PERSONAL_MATERIAL_BASIS,
        source_collection=SourceCollection.PERSONAL_MATERIALS,
        chunk_id=uuid5(NAMESPACE_URL, f"chat-attachment:{digest}"),
        snippet=_truncate(context, MAX_SNIPPET_CHARS),
        locator={
            "type": "chat-attachment",
            "file_name": file_name,
            "extension": extension,
            "sha256": digest,
        },
        index_version_key="chat-attachment-session",
        source_package_version_key="chat-upload",
        score=1.0,
        metadata={"file_name": file_name, "extension": extension},
    )


def _file_extension(file_name: str) -> str:
    if "." not in file_name:
        return ""
    return file_name.rsplit(".", maxsplit=1)[-1].lower()


def _truncate(value: str, max_chars: int) -> str:
    normalized = value.strip()
    if len(normalized) <= max_chars:
        return normalized
    return f"{normalized[: max_chars - 3]}..."
