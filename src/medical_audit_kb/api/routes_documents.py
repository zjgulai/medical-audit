from __future__ import annotations

from typing import Annotated, Literal, cast

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from medical_audit_kb.api.app import ApiState, get_api_state, record_operation
from medical_audit_kb.api.auth_context import CurrentUser, auth_audit_payload, get_current_user
from medical_audit_kb.api.document_permissions import (
    can_read_all_personal_uploads,
    document_permissions_for_role,
    normalize_role,
)
from medical_audit_kb.api.document_upload_governance import (
    DocumentUploadGovernanceContext,
    apply_manual_index_decision,
)
from medical_audit_kb.domain.constants import SourceCollection

router = APIRouter(prefix="/documents")

MAX_DOCUMENT_UPLOAD_BYTES = 20 * 1024 * 1024
SUPPORTED_DOCUMENT_EXTENSIONS = {"pdf", "md", "txt", "csv", "xlsx", "xlsm"}
MANUAL_INDEX_APPROVAL_ROLES = frozenset({"system-admin", "department-head"})
MANUAL_INDEX_APPROVAL_DENIED_REASON = (
    "document upload index approval requires department-head or system-admin role"
)


class DocumentSourcePermissionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_collection: SourceCollection
    label: str
    scope: str
    access: Literal["read"]


class DocumentUploadPermissions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    can_upload_personal: bool
    can_read_all_personal_uploads: bool


class DocumentIndexReadinessCheck(BaseModel):
    model_config = ConfigDict(extra="allow")

    check_type: Literal["virus-scan", "dlp-review", "manual-index-approval"]
    provider: str
    status: Literal["passed", "blocked"]
    blocker: (
        Literal[
            "virus-scan-required",
            "dlp-review-required",
            "manual-index-approval-required",
            "manual-index-approval-rejected",
        ]
        | None
    )
    detail: str


class DocumentIndexReadiness(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["blocked", "ready", "rejected"]
    blockers: list[
        Literal[
            "virus-scan-required",
            "dlp-review-required",
            "manual-index-approval-required",
            "manual-index-approval-rejected",
        ]
    ]
    next_action: Literal[
        "complete-upload-governance",
        "ingest-personal-upload",
        "review-manual-index-rejection",
    ]
    checks: list[DocumentIndexReadinessCheck]


class DocumentPermissionsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str
    source_collections: list[DocumentSourcePermissionItem]
    upload_permissions: DocumentUploadPermissions


class DocumentUploadItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    extension: str
    size_bytes: int
    size_kb: int
    sha256: str
    storage_path: str
    visibility: Literal["private"]
    status: Literal["retained"]
    created_by: str | None
    created_at: str
    retention_status: Literal["retained"]
    index_status: Literal["not-indexed"]
    index_readiness: DocumentIndexReadiness


class DocumentStorageObjectItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    upload_key: str
    provider: Literal["local", "tencent-cos"]
    bucket: str | None
    region: str | None
    object_key: str
    object_version: str | None
    etag: str | None
    sha256: str
    size_bytes: int
    storage_class: str | None
    encryption_mode: str | None
    storage_status: Literal["local-quarantine", "object-stored", "object-missing"]
    retention_until: str | None
    created_at: str
    updated_at: str


class DocumentUploadDownloadAccess(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["metadata-only"]
    access_scope: Literal["owner", "read-all"]
    delivery: Literal["not-issued"]
    reason: Literal["signed-download-not-configured"]
    signed_url: str | None
    expires_at: str | None
    storage_path: str
    storage_objects: list[DocumentStorageObjectItem]


class DocumentUploadListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[DocumentUploadItem]
    store: dict[str, object]
    permissions: DocumentUploadPermissions


class DocumentUploadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item: DocumentUploadItem
    store: dict[str, object]
    permissions: DocumentUploadPermissions


class DocumentUploadDownloadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item: DocumentUploadItem
    download: DocumentUploadDownloadAccess
    permissions: DocumentUploadPermissions


class ManualIndexApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["approved", "rejected"]
    note: str = Field(min_length=1, max_length=1000)


@router.get("/permissions", response_model=DocumentPermissionsResponse)
def document_permissions(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> DocumentPermissionsResponse:
    role = normalize_role(current_user.primary_role)
    return _permissions_response(role)


@router.get("/uploads", response_model=DocumentUploadListResponse)
def list_document_uploads(
    state: Annotated[ApiState, Depends(get_api_state)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> DocumentUploadListResponse:
    role = normalize_role(current_user.primary_role)
    permissions = _upload_permissions(role)
    if state.document_upload_store is None:
        return DocumentUploadListResponse(
            items=[],
            store={"ready": False, "backend": "none"},
            permissions=permissions,
        )

    user_identifier = current_user.user_key
    items = [
        DocumentUploadItem.model_validate(item)
        for item in state.document_upload_store.list_uploads(
            created_by=user_identifier,
            include_all=permissions.can_read_all_personal_uploads,
            limit=limit,
        )
    ]
    record_operation(
        state,
        "document-upload-list",
        auth_audit_payload(
            current_user,
            count=len(items),
            limit=limit,
            include_all=permissions.can_read_all_personal_uploads,
        ),
    )
    return DocumentUploadListResponse(
        items=items,
        store={"ready": True, "backend": state.document_upload_store.__class__.__name__},
        permissions=permissions,
    )


@router.post("/uploads", response_model=DocumentUploadResponse)
async def upload_document(
    file: Annotated[UploadFile, File()],
    state: Annotated[ApiState, Depends(get_api_state)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> DocumentUploadResponse:
    role = normalize_role(current_user.primary_role)
    permissions = _upload_permissions(role)
    if state.document_upload_store is None:
        raise HTTPException(status_code=409, detail="document upload store is not configured")

    file_name = file.filename or "uploaded-document"
    extension = _file_extension(file_name)
    if extension not in SUPPORTED_DOCUMENT_EXTENSIONS:
        raise HTTPException(status_code=422, detail="unsupported document file extension")

    content = await file.read()
    if len(content) > MAX_DOCUMENT_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="uploaded document file is too large")
    if not content:
        raise HTTPException(status_code=422, detail="uploaded document file is empty")

    user_identifier = current_user.user_key
    governance_context = DocumentUploadGovernanceContext.from_upload(
        file_name=file_name,
        extension=extension,
        content=content,
    )
    index_readiness = state.document_upload_governance.evaluate(governance_context)
    item = DocumentUploadItem.model_validate(
        state.document_upload_store.add_upload(
            file_name=file_name,
            extension=extension,
            content=content,
            created_by=user_identifier,
            index_readiness=index_readiness,
        )
    )
    record_operation(
        state,
        "document-upload",
        auth_audit_payload(
            current_user,
            upload_id=item.id,
            file_name=item.name,
            extension=item.extension,
            size_bytes=item.size_bytes,
            retention_status=item.retention_status,
            index_status=item.index_status,
            index_readiness_status=item.index_readiness.status,
            index_readiness_blockers=item.index_readiness.blockers,
            index_readiness_checks=[check.model_dump() for check in item.index_readiness.checks],
        ),
    )
    return DocumentUploadResponse(
        item=item,
        store={"ready": True, "backend": state.document_upload_store.__class__.__name__},
        permissions=permissions,
    )


@router.get("/uploads/{upload_id}/download", response_model=DocumentUploadDownloadResponse)
def get_document_upload_download_metadata(
    upload_id: str,
    state: Annotated[ApiState, Depends(get_api_state)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> DocumentUploadDownloadResponse:
    role = normalize_role(current_user.primary_role)
    permissions = _upload_permissions(role)
    if state.document_upload_store is None:
        raise HTTPException(status_code=409, detail="document upload store is not configured")

    upload = state.document_upload_store.get_upload(upload_id)
    if upload is None:
        raise HTTPException(status_code=404, detail="document upload not found")

    access_scope = _document_upload_access_scope(
        upload=upload,
        current_user=current_user,
        permissions=permissions,
    )
    if access_scope is None:
        record_operation(
            state,
            "document-upload-download-access-denied",
            auth_audit_payload(
                current_user,
                attempted_action="document-upload-download-metadata",
                upload_id=upload_id,
                status_code=404,
                reason="document upload not found",
            ),
        )
        raise HTTPException(status_code=404, detail="document upload not found")

    item = DocumentUploadItem.model_validate(upload)
    storage_objects = [
        DocumentStorageObjectItem.model_validate(storage_object)
        for storage_object in state.document_upload_store.list_storage_objects(upload_id)
    ]
    record_operation(
        state,
        "document-upload-download-metadata",
        auth_audit_payload(
            current_user,
            upload_id=item.id,
            access_scope=access_scope,
            storage_object_count=len(storage_objects),
            signed_url_issued=False,
        ),
    )
    return DocumentUploadDownloadResponse(
        item=item,
        download=DocumentUploadDownloadAccess(
            status="metadata-only",
            access_scope=access_scope,
            delivery="not-issued",
            reason="signed-download-not-configured",
            signed_url=None,
            expires_at=None,
            storage_path=item.storage_path,
            storage_objects=storage_objects,
        ),
        permissions=permissions,
    )


@router.post(
    "/uploads/{upload_id}/index-readiness/manual-approval",
    response_model=DocumentUploadResponse,
)
def decide_manual_index_approval(
    upload_id: str,
    request: ManualIndexApprovalRequest,
    state: Annotated[ApiState, Depends(get_api_state)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> DocumentUploadResponse:
    role = normalize_role(current_user.primary_role)
    permissions = _upload_permissions(role)
    if state.document_upload_store is None:
        raise HTTPException(status_code=409, detail="document upload store is not configured")
    if role not in MANUAL_INDEX_APPROVAL_ROLES:
        record_operation(
            state,
            "document-upload-index-approval-access-denied",
            auth_audit_payload(
                current_user,
                attempted_action="document-upload-index-readiness-update",
                upload_id=upload_id,
                status_code=403,
                reason=MANUAL_INDEX_APPROVAL_DENIED_REASON,
            ),
        )
        raise HTTPException(status_code=403, detail=MANUAL_INDEX_APPROVAL_DENIED_REASON)

    current_upload = state.document_upload_store.get_upload(upload_id)
    if current_upload is None:
        raise HTTPException(status_code=404, detail="document upload not found")

    index_readiness = apply_manual_index_decision(
        cast(dict[str, object], current_upload["index_readiness"]),
        decision=request.decision,
        actor=current_user.user_key,
        note=request.note,
    )
    updated = state.document_upload_store.update_index_readiness(
        upload_key=upload_id,
        index_readiness=index_readiness,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="document upload not found")

    item = DocumentUploadItem.model_validate(updated)
    record_operation(
        state,
        "document-upload-index-readiness-update",
        auth_audit_payload(
            current_user,
            upload_id=item.id,
            decision=request.decision,
            index_status=item.index_status,
            index_readiness_status=item.index_readiness.status,
            index_readiness_blockers=item.index_readiness.blockers,
            index_readiness_checks=[check.model_dump() for check in item.index_readiness.checks],
        ),
    )
    return DocumentUploadResponse(
        item=item,
        store={"ready": True, "backend": state.document_upload_store.__class__.__name__},
        permissions=permissions,
    )


def _permissions_response(role: str) -> DocumentPermissionsResponse:
    return DocumentPermissionsResponse(
        role=role,
        source_collections=[
            DocumentSourcePermissionItem.model_validate(permission.to_payload())
            for permission in document_permissions_for_role(role)
        ],
        upload_permissions=_upload_permissions(role),
    )


def _upload_permissions(role: str) -> DocumentUploadPermissions:
    return DocumentUploadPermissions(
        can_upload_personal=True,
        can_read_all_personal_uploads=can_read_all_personal_uploads(role),
    )


def _document_upload_access_scope(
    *,
    upload: dict[str, object],
    current_user: CurrentUser,
    permissions: DocumentUploadPermissions,
) -> Literal["owner", "read-all"] | None:
    if upload.get("created_by") == current_user.user_key:
        return "owner"
    if permissions.can_read_all_personal_uploads:
        return "read-all"
    return None


def _file_extension(file_name: str) -> str:
    if "." not in file_name:
        return ""
    return file_name.rsplit(".", maxsplit=1)[-1].lower()
