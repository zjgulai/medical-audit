from __future__ import annotations

import json
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import Response

from medical_audit_kb.api.app import ApiState, get_api_state, record_operation
from medical_audit_kb.api.auth import (
    HospitalRole,
    Permission,
    require_permission,
    resolve_authenticated_user,
)
from medical_audit_kb.api.chat_models import (
    ChatModelAlias,
    ChatModelUnavailableError,
    contract_audit_generation_provider_for_alias,
)
from medical_audit_kb.api.docx_export import DOCX_MEDIA_TYPE, markdown_to_docx
from medical_audit_kb.contract_audit.service import (
    MAX_CONTRACT_BYTES,
    ContractAuditOcrUnavailableError,
    create_contract_audit_job,
)
from medical_audit_kb.contract_audit.store import ContractAuditJobStore, FileContractAuditJobStore

router = APIRouter()
UPLOAD_READ_CHUNK_BYTES = 1024 * 1024


@router.post("/contract-audits")
async def create_contract_audit(
    state: Annotated[ApiState, Depends(get_api_state)],
    file: Annotated[UploadFile, File(...)],
    project_name: Annotated[str, Form(min_length=1, max_length=256)] = "全院审计项目",
    audit_stage: Annotated[str, Form(max_length=64)] = "签约前",
    perspective: Annotated[str, Form(max_length=128)] = "采购方/医院",
    model: Annotated[ChatModelAlias | None, Form()] = None,
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> dict[str, object]:
    user = require_permission(
        state,
        permission=Permission.UPLOAD_PERSONAL_DOCUMENT,
        x_user_id=x_user_id,
        x_role=x_role,
        attempted_action="contract-audit-create",
    )
    generation_provider = state.answer_generation_provider
    if model is not None:
        try:
            generation_provider = contract_audit_generation_provider_for_alias(model)
        except ChatModelUnavailableError as exc:
            raise HTTPException(
                status_code=409,
                detail={"code": "chat_model_unavailable", "model": exc.alias.value},
            ) from exc
    try:
        job = await create_contract_audit_job(
            store=_job_store(state),
            file_name=file.filename or "contract.bin",
            content=await _read_upload_bounded(file),
            created_by=user.user_identifier,
            project_name=project_name.strip(),
            audit_stage=audit_stage.strip() or "签约前",
            perspective=perspective.strip() or "采购方/医院",
            ocr_client=state.ocr_client,
            generation_provider=generation_provider,
        )
    except ContractAuditOcrUnavailableError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    record_operation(
        state,
        "contract-audit-create",
        {
            "job_id": job["job_id"],
            "status": job["status"],
            "created_by": user.user_identifier,
            "source_sha256": _source_sha(job),
        },
    )
    return _job_response(job)


@router.get("/contract-audits/{job_id}")
def get_contract_audit(
    job_id: str,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> dict[str, object]:
    user = resolve_authenticated_user(
        state,
        x_user_id=x_user_id,
        x_role=x_role,
        default_role=HospitalRole.MEMBER,
    )
    job = _owned_job(state, job_id, user_identifier=user.user_identifier, role=user.role)
    return _job_response(job)


@router.get("/contract-audits/{job_id}/report")
def download_contract_audit_report(
    job_id: str,
    state: Annotated[ApiState, Depends(get_api_state)],
    report_format: Annotated[
        Literal["json", "markdown", "docx"], Query(alias="format")
    ] = "docx",
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> Response:
    user = resolve_authenticated_user(
        state,
        x_user_id=x_user_id,
        x_role=x_role,
        default_role=HospitalRole.MEMBER,
    )
    job = _owned_job(state, job_id, user_identifier=user.user_identifier, role=user.role)
    markdown = str(job.get("report_markdown") or "")
    if report_format == "json":
        content = json.dumps(job["result"], ensure_ascii=False, indent=2).encode("utf-8")
        media_type = "application/json"
        suffix = "json"
    elif report_format == "markdown":
        content = markdown.encode("utf-8")
        media_type = "text/markdown; charset=utf-8"
        suffix = "md"
    else:
        content = markdown_to_docx(markdown, title="合同审计报告", subject=job_id)
        media_type = DOCX_MEDIA_TYPE
        suffix = "docx"
    record_operation(
        state,
        "contract-audit-report-download",
        {"job_id": job_id, "format": report_format, "created_by": user.user_identifier},
    )
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{job_id}.{suffix}"'},
    )


def _job_store(state: ApiState) -> ContractAuditJobStore:
    if state.contract_audit_job_store is None:
        state.contract_audit_job_store = FileContractAuditJobStore(
            state.settings.index_root / "contract-audit-jobs"
        )
    return state.contract_audit_job_store


def _owned_job(
    state: ApiState,
    job_id: str,
    *,
    user_identifier: str,
    role: HospitalRole,
) -> dict[str, object]:
    try:
        job = _job_store(state).get(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="contract audit job not found") from exc
    if job is None:
        raise HTTPException(status_code=404, detail="contract audit job not found")
    if (
        role not in {HospitalRole.ADMIN, HospitalRole.DIRECTOR}
        and job.get("created_by") != user_identifier
    ):
        raise HTTPException(
            status_code=403, detail="contract audit job is not visible to current user"
        )
    return job


def _job_response(job: dict[str, object]) -> dict[str, object]:
    return {
        key: value
        for key, value in job.items()
        if key not in {"pages", "report_markdown"}
    }


async def _read_upload_bounded(file: UploadFile) -> bytes:
    chunks: list[bytes] = []
    size_bytes = 0
    while True:
        chunk = await file.read(UPLOAD_READ_CHUNK_BYTES)
        if not chunk:
            break
        size_bytes += len(chunk)
        if size_bytes > MAX_CONTRACT_BYTES:
            raise ValueError("contract file exceeds 40 MiB")
        chunks.append(chunk)
    return b"".join(chunks)


def _source_sha(job: dict[str, object]) -> str | None:
    source = job.get("source")
    return str(source.get("sha256")) if isinstance(source, dict) and source.get("sha256") else None
