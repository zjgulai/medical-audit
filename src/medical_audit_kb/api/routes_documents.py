from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, UploadFile
from pydantic import BaseModel, ConfigDict

from medical_audit_kb.api.app import ApiState, get_api_state, record_operation
from medical_audit_kb.api.document_permissions import (
    can_read_all_personal_uploads,
    document_permissions_for_role,
    normalize_role,
)
from medical_audit_kb.domain.constants import SourceCollection

router = APIRouter(prefix="/documents")

MAX_DOCUMENT_UPLOAD_BYTES = 20 * 1024 * 1024
SUPPORTED_DOCUMENT_EXTENSIONS = {"pdf", "md", "txt", "csv", "xlsx", "xlsm"}


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


@router.get("/permissions", response_model=DocumentPermissionsResponse)
def document_permissions(
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> DocumentPermissionsResponse:
    role = normalize_role(x_role)
    return _permissions_response(role)


@router.get("/uploads", response_model=DocumentUploadListResponse)
def list_document_uploads(
    state: Annotated[ApiState, Depends(get_api_state)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> DocumentUploadListResponse:
    role = normalize_role(x_role)
    permissions = _upload_permissions(role)
    if state.document_upload_store is None:
        return DocumentUploadListResponse(
            items=[],
            store={"ready": False, "backend": "none"},
            permissions=permissions,
        )

    user_identifier = _user_identifier(x_user_id)
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
        {
            "count": len(items),
            "limit": limit,
            "user_identifier": user_identifier,
            "role": role,
            "include_all": permissions.can_read_all_personal_uploads,
        },
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
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> DocumentUploadResponse:
    role = normalize_role(x_role)
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

    user_identifier = _user_identifier(x_user_id)
    item = DocumentUploadItem.model_validate(
        state.document_upload_store.add_upload(
            file_name=file_name,
            extension=extension,
            content=content,
            created_by=user_identifier,
        )
    )
    record_operation(
        state,
        "document-upload",
        {
            "upload_id": item.id,
            "file_name": item.name,
            "extension": item.extension,
            "size_bytes": item.size_bytes,
            "retention_status": item.retention_status,
            "index_status": item.index_status,
            "user_identifier": user_identifier,
            "role": role,
        },
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


def _file_extension(file_name: str) -> str:
    if "." not in file_name:
        return ""
    return file_name.rsplit(".", maxsplit=1)[-1].lower()


def _user_identifier(value: str | None) -> str:
    normalized = (value or "anonymous").strip()
    return normalized or "anonymous"
