from __future__ import annotations

import hashlib
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict

from medical_audit_kb.api.app import ApiState, get_api_state, record_operation
from medical_audit_kb.api.auth import Permission, require_permission
from medical_audit_kb.ocr.unlimited_ocr import (
    SUPPORTED_IMAGE_EXTENSIONS,
    UnlimitedOcrError,
)

router = APIRouter()

MAX_OCR_UPLOAD_BYTES = 40 * 1024 * 1024
UPLOAD_READ_CHUNK_BYTES = 1024 * 1024
SUPPORTED_OCR_EXTENSIONS = frozenset({"pdf", *SUPPORTED_IMAGE_EXTENSIONS})


class OcrCapabilityBoundaries(BaseModel):
    model_config = ConfigDict(extra="forbid")

    database_write: Literal[False] = False
    audit_log_write: Literal[False] = False
    source_storage_write: Literal[False] = False
    provider_call: Literal[False] = False


class OcrCapabilityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["unlimited-ocr-capability-v1"]
    enabled: bool
    engine: str
    source_commit: str
    supported_extensions: list[str]
    max_upload_bytes: int
    max_pages: int
    pdf_dpi: int
    boundaries: OcrCapabilityBoundaries


class OcrExtractionPageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_number: int
    text: str
    image_sha256: str
    text_sha256: str
    mapping_status: str


class OcrExtractionBoundaries(BaseModel):
    model_config = ConfigDict(extra="forbid")

    database_write: Literal[False] = False
    audit_log_write: Literal[True] = True
    source_storage_write: Literal[False] = False
    index_write: Literal[False] = False
    provider_call: Literal[True] = True
    ocr_call: Literal[True] = True
    answer_provider_call: Literal[False] = False


class OcrExtractionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["unlimited-ocr-extraction-v1"]
    file_name: str
    extension: str
    source_sha256: str
    size_bytes: int
    text: str
    page_count: int
    engine: str
    source_commit: str
    mapping_status: str
    pages: list[OcrExtractionPageResponse]
    boundaries: OcrExtractionBoundaries


@router.get("/ocr/capabilities", response_model=OcrCapabilityResponse)
def get_ocr_capabilities(
    state: Annotated[ApiState, Depends(get_api_state)],
) -> OcrCapabilityResponse:
    settings = state.settings.unlimited_ocr
    client = state.ocr_client
    return OcrCapabilityResponse(
        contract_version="unlimited-ocr-capability-v1",
        enabled=client is not None,
        engine=str(getattr(client, "engine", settings.model)),
        source_commit=str(getattr(client, "source_version", settings.source_commit)),
        supported_extensions=sorted(SUPPORTED_OCR_EXTENSIONS),
        max_upload_bytes=MAX_OCR_UPLOAD_BYTES,
        max_pages=int(getattr(client, "max_pages", settings.max_pages)),
        pdf_dpi=int(getattr(client, "pdf_dpi", settings.pdf_dpi)),
        boundaries=OcrCapabilityBoundaries(),
    )


@router.post("/ocr/extract", response_model=OcrExtractionResponse)
async def extract_ocr_text(
    state: Annotated[ApiState, Depends(get_api_state)],
    file: Annotated[UploadFile, File(...)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> OcrExtractionResponse:
    user = require_permission(
        state,
        permission=Permission.UPLOAD_PERSONAL_DOCUMENT,
        x_user_id=x_user_id,
        x_role=x_role,
        attempted_action="unlimited-ocr-extract",
    )
    ocr_client = state.ocr_client
    if ocr_client is None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "unlimited_ocr_unavailable",
                "message": "OCR 服务尚未启用，请联系管理员完成运行时配置。",
            },
        )

    file_name = file.filename or "ocr-document"
    extension = _file_extension(file_name)
    if extension not in SUPPORTED_OCR_EXTENSIONS:
        raise HTTPException(status_code=422, detail="文件类型不支持 OCR 识别。")
    content = await _read_upload_bounded(file)
    source_sha256 = hashlib.sha256(content).hexdigest()
    try:
        result = await ocr_client.extract_text(
            file_name=file_name,
            extension=extension,
            content=content,
        )
    except UnlimitedOcrError as exc:
        message = str(exc)
        status_code = 422 if _is_input_ocr_error(message) else 502
        raise HTTPException(status_code=status_code, detail=message) from exc

    mapping_status = (
        "resolved"
        if result.pages and all(page.mapping_status == "resolved" for page in result.pages)
        else "unresolved"
    )
    record_operation(
        state,
        "unlimited-ocr-extract",
        {
            "created_by": user.user_identifier,
            "extension": extension,
            "source_sha256": source_sha256,
            "size_bytes": len(content),
            "page_count": result.page_count,
            "mapping_status": mapping_status,
            "ocr_model": result.model,
            "ocr_source_commit": result.source_commit,
            "provider_call": True,
            "answer_provider_call": False,
        },
    )
    return OcrExtractionResponse(
        contract_version="unlimited-ocr-extraction-v1",
        file_name=file_name,
        extension=extension,
        source_sha256=source_sha256,
        size_bytes=len(content),
        text=result.text,
        page_count=result.page_count,
        engine=result.model,
        source_commit=result.source_commit,
        mapping_status=mapping_status,
        pages=[
            OcrExtractionPageResponse(
                page_number=page.page_number,
                text=page.text,
                image_sha256=page.image_sha256,
                text_sha256=page.text_sha256,
                mapping_status=page.mapping_status,
            )
            for page in result.pages
        ],
        boundaries=OcrExtractionBoundaries(),
    )


async def _read_upload_bounded(file: UploadFile) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(UPLOAD_READ_CHUNK_BYTES)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_OCR_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="OCR 文件超过 40 MiB 限制。")
        chunks.append(chunk)
    if total == 0:
        raise HTTPException(status_code=422, detail="OCR 文件内容为空。")
    return b"".join(chunks)


def _file_extension(file_name: str) -> str:
    return file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""


def _is_input_ocr_error(message: str) -> bool:
    lowered = message.lower()
    return any(
        marker in lowered
        for marker in (
            "exceeds",
            "could not be rendered",
            "file type is not supported",
            "image could not be rendered",
        )
    )
