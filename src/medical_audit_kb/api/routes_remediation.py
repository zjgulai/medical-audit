from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from medical_audit_kb.api.app import ApiState, get_api_state, record_operation
from medical_audit_kb.api.auth import (
    AuthenticatedUser,
    HospitalRole,
    Permission,
    require_permission,
    user_has_permission,
)
from medical_audit_kb.api.project_member_store import project_exists, visible_project_keys
from medical_audit_kb.api.remediation_store import (
    REMEDIATION_STATUS_TRANSITIONS,
    VALID_STATUSES,
    create_remediation_item,
    get_remediation_item,
    list_remediation_items,
    update_remediation_status,
)

router = APIRouter()

REMEDIATION_STATUS_LABELS: dict[str, str] = {
    "pending-rectification": "待整改",
    "in-rectification": "整改中",
    "pending-acceptance": "待验收",
    "accepted": "验收通过",
    "rejected": "验收退回",
    "closed": "已关闭",
}


@contextmanager
def _db_session(state: ApiState) -> Iterator[Session]:
    store = state.review_task_store
    if store is None or not hasattr(store, "_session_factory"):
        raise HTTPException(status_code=409, detail="database not available")
    with store._session_factory() as session:  # noqa: SLF001
        yield session


class RemediationItemCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    description: str = Field(default="", max_length=4096)
    project_key: str = Field(min_length=1, max_length=128)
    audit_finding_id: UUID | None = None
    responsible_dept: str | None = Field(default=None, max_length=256)
    responsible_person: str | None = Field(default=None, max_length=128)
    due_date: str | None = None


class RemediationStatusUpdateRequest(BaseModel):
    status: str = Field(min_length=1, max_length=48)
    note: str = Field(default="", max_length=2048)


def _item_payload(item: object, *, user: AuthenticatedUser) -> dict[str, object]:
    from medical_audit_kb.db.models import RemediationItem as M

    assert isinstance(item, M)
    legacy_unscoped = not bool(item.project_key)
    allowed_transitions = remediation_allowed_transitions(
        item.status,
        user=user,
        writable=not legacy_unscoped,
    )
    return {
        "id": str(item.id),
        "item_key": item.item_key,
        "title": item.title,
        "description": item.description,
        "status": item.status,
        "status_label": REMEDIATION_STATUS_LABELS.get(item.status, item.status),
        "project_key": item.project_key,
        "audit_finding_id": str(item.audit_finding_id) if item.audit_finding_id else None,
        "responsible_dept": item.responsible_dept,
        "responsible_person": item.responsible_person,
        "due_date": item.due_date.isoformat() if item.due_date else None,
        "rectification_note": item.rectification_note,
        "acceptance_note": item.acceptance_note,
        "attachment_count": item.attachment_count,
        "created_by": item.created_by,
        "closed_by": item.closed_by,
        "closed_at": item.closed_at.isoformat() if item.closed_at else None,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
        "legacy_unscoped": legacy_unscoped,
        "allowed_transitions": allowed_transitions,
        "can_upload_attachment": item.status != "closed"
        and not legacy_unscoped
        and user_has_permission(user, Permission.CREATE_REVIEW_TASK),
    }


def remediation_allowed_transitions(
    status: str,
    *,
    user: AuthenticatedUser,
    writable: bool,
) -> list[dict[str, str]]:
    if not writable:
        return []
    allowed: list[dict[str, str]] = []
    for target in sorted(REMEDIATION_STATUS_TRANSITIONS.get(status, frozenset())):
        permission = (
            Permission.SIGN_REPORTS
            if target in {"accepted", "rejected", "closed"}
            else Permission.CREATE_REVIEW_TASK
        )
        if user_has_permission(user, permission):
            allowed.append({"status": target, "label": REMEDIATION_STATUS_LABELS[target]})
    return allowed


def _visible_keys_for_user(state: ApiState, user: AuthenticatedUser) -> frozenset[str]:
    store = state.project_member_store
    if store is None:
        raise HTTPException(status_code=503, detail="project membership store unavailable")
    try:
        return visible_project_keys(
            user_identifier=user.user_identifier,
            is_admin=user.role is HospitalRole.ADMIN,
            store=store,
        )
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="project membership store unavailable") from exc


def _require_visible_project(
    state: ApiState,
    user: AuthenticatedUser,
    project_key: str | None,
) -> None:
    if not project_key:
        if user.role is HospitalRole.ADMIN:
            return
        raise HTTPException(status_code=404, detail="remediation item not found")
    store = state.project_member_store
    if store is None:
        raise HTTPException(status_code=503, detail="project membership store unavailable")
    try:
        exists = project_exists(project_key, store)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="project membership store unavailable") from exc
    if not exists or project_key not in _visible_keys_for_user(state, user):
        raise HTTPException(status_code=404, detail="remediation item not found")


@router.get("/remediation/items")
def list_items(
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
    project_key: Annotated[str | None, Query(max_length=128)] = None,
    status: Annotated[str | None, Query(max_length=48)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, object]:
    user = require_permission(
        state, permission=Permission.CREATE_REVIEW_TASK,
        x_user_id=x_user_id, x_role=x_role,
        attempted_action="remediation-list",
    )
    visible_keys = _visible_keys_for_user(state, user)
    if project_key is not None and project_key not in visible_keys:
        raise HTTPException(status_code=404, detail="remediation item not found")
    try:
        with _db_session(state) as session:
            items = list_remediation_items(
                session, project_key=project_key, status=status, limit=limit
            )
            payload = [
                _item_payload(item, user=user)
                for item in items
                if item.project_key in visible_keys
                or (item.project_key is None and user.role is HospitalRole.ADMIN)
            ]
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="remediation store unavailable") from exc
    record_operation(state, "remediation-list", {"count": len(payload), "project_key": project_key})
    return {
        "format": "remediation-items-v1",
        "items": payload,
        "count": len(payload),
        "status_options": REMEDIATION_STATUS_LABELS,
        "store": {"ready": True, "backend": "SqlAlchemyRemediationStore"},
    }


@router.post("/remediation/items")
def create_item(
    payload: RemediationItemCreateRequest,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> dict[str, object]:
    user = require_permission(
        state, permission=Permission.CREATE_REVIEW_TASK,
        x_user_id=x_user_id, x_role=x_role,
        attempted_action="remediation-create", project_key=payload.project_key,
    )
    _require_visible_project(state, user, payload.project_key)
    due_date = None
    if payload.due_date:
        from datetime import datetime  # noqa: PLC0415
        try:
            due_date = datetime.fromisoformat(payload.due_date)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="invalid due_date format") from exc
    try:
        with _db_session(state) as session:
            item = create_remediation_item(
                session,
                title=payload.title,
                description=payload.description,
                project_key=payload.project_key,
                audit_finding_id=payload.audit_finding_id,
                responsible_dept=payload.responsible_dept,
                responsible_person=payload.responsible_person,
                due_date=due_date,
                created_by=user.user_identifier,
            )
            session.commit()
            result = _item_payload(item, user=user)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="remediation store unavailable") from exc
    record_operation(state, "remediation-create", {
        "item_key": result["item_key"], "project_key": payload.project_key,
        "created_by": user.user_identifier,
    })
    return {"format": "remediation-item-v1", "item": result}


@router.get("/remediation/items/{item_id}")
def get_item(
    item_id: UUID,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> dict[str, object]:
    user = require_permission(
        state, permission=Permission.CREATE_REVIEW_TASK,
        x_user_id=x_user_id, x_role=x_role,
        attempted_action="remediation-get",
    )
    try:
        with _db_session(state) as session:
            item = get_remediation_item(session, item_id)
            if item is not None:
                _require_visible_project(state, user, item.project_key)
            result = _item_payload(item, user=user) if item is not None else None
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="remediation store unavailable") from exc
    if result is None:
        raise HTTPException(status_code=404, detail="remediation item not found")
    return {"format": "remediation-item-v1", "item": result}


@router.post("/remediation/items/{item_id}/status")
def update_status(
    item_id: UUID,
    payload: RemediationStatusUpdateRequest,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> dict[str, object]:
    user = require_permission(
        state, permission=Permission.CREATE_REVIEW_TASK,
        x_user_id=x_user_id, x_role=x_role,
        attempted_action="remediation-status-update",
    )
    if payload.status not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail=f"unsupported status: {payload.status}")
    try:
        with _db_session(state) as session:
            existing = get_remediation_item(session, item_id)
            if existing is None:
                raise HTTPException(status_code=404, detail="remediation item not found")
            _require_visible_project(state, user, existing.project_key)
            if not existing.project_key:
                raise HTTPException(
                    status_code=409,
                    detail="legacy unscoped remediation is read-only",
                )
            required_permission = (
                Permission.SIGN_REPORTS
                if payload.status in {"accepted", "rejected", "closed"}
                else Permission.CREATE_REVIEW_TASK
            )
            if not user_has_permission(user, required_permission):
                raise HTTPException(
                    status_code=403,
                    detail=f"{required_permission.value} is not allowed",
                )
            item = update_remediation_status(
                session, item_id,
                status=payload.status, note=payload.note,
                closed_by=user.user_identifier,
            )
            if item is None:
                raise HTTPException(status_code=404, detail="remediation item not found")
            session.commit()
            result = _item_payload(item, user=user)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="remediation store unavailable") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    record_operation(state, "remediation-status-update", {
        "item_key": result["item_key"], "status": payload.status,
        "updated_by": user.user_identifier,
    })
    return {"format": "remediation-item-v1", "item": result}


MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024
ALLOWED_ATTACHMENT_EXTENSIONS = frozenset({
    "pdf", "png", "jpg", "jpeg", "gif", "webp",
    "xlsx", "xls", "csv", "docx", "doc", "txt", "zip",
})


@router.post("/remediation/items/{item_id}/attachments")
async def upload_attachment(
    item_id: UUID,
    state: Annotated[ApiState, Depends(get_api_state)],
    file: Annotated[UploadFile, File(...)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> dict[str, object]:
    user = require_permission(
        state, permission=Permission.CREATE_REVIEW_TASK,
        x_user_id=x_user_id, x_role=x_role,
        attempted_action="remediation-attachment-upload",
    )
    try:
        with _db_session(state) as session:
            item = get_remediation_item(session, item_id)
            if item is None:
                raise HTTPException(status_code=404, detail="remediation item not found")
            _require_visible_project(state, user, item.project_key)
            if not item.project_key:
                raise HTTPException(
                    status_code=409,
                    detail="legacy unscoped remediation is read-only",
                )
            if item.status == "closed":
                raise HTTPException(
                    status_code=409,
                    detail="closed remediation is read-only",
                )
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="remediation store unavailable") from exc

    upload_store = state.document_upload_store
    if upload_store is None:
        raise HTTPException(status_code=409, detail="附件存储未启用，请联系管理员配置。")

    file_name = file.filename or "attachment"
    ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    if ext not in ALLOWED_ATTACHMENT_EXTENSIONS:
        raise HTTPException(status_code=422, detail=f"不支持的附件格式：{ext}")

    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(65536)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_ATTACHMENT_BYTES:
            raise HTTPException(status_code=413, detail="附件超过 20 MiB 限制。")
        chunks.append(chunk)
    if total == 0:
        raise HTTPException(status_code=422, detail="附件内容为空。")
    content = b"".join(chunks)

    try:
        with _db_session(state) as session:
            item = get_remediation_item(session, item_id)
            if item is None:
                raise HTTPException(status_code=404, detail="remediation item not found")
            _require_visible_project(state, user, item.project_key)
            if not item.project_key:
                raise HTTPException(
                    status_code=409,
                    detail="legacy unscoped remediation is read-only",
                )
            if item.status == "closed":
                raise HTTPException(
                    status_code=409,
                    detail="closed remediation is read-only",
                )
            upload = upload_store.add_upload(
                file_name=file_name,
                extension=ext,
                content=content,
                created_by=user.user_identifier,
                metadata={
                    "scope": "project",
                    "project_key": f"remediation:{item_id}",
                    "parent_project_key": item.project_key,
                    "document_type": "整改附件",
                    "description": f"整改事项附件：{item.item_key}",
                },
            )
            item.attachment_count = (item.attachment_count or 0) + 1
            session.commit()
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="remediation store unavailable") from exc

    record_operation(state, "remediation-attachment-upload", {
        "item_id": str(item_id), "file_name": file_name,
        "size_bytes": total, "uploaded_by": user.user_identifier,
    })
    return {
        "format": "remediation-attachment-v1",
        "upload_id": upload.get("id") or upload.get("upload_id"),
        "file_name": file_name,
        "size_bytes": total,
        "item_id": str(item_id),
    }


@router.get("/remediation/items/{item_id}/attachments")
def list_attachments(
    item_id: UUID,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> dict[str, object]:
    user = require_permission(
        state, permission=Permission.CREATE_REVIEW_TASK,
        x_user_id=x_user_id, x_role=x_role,
        attempted_action="remediation-attachment-list",
    )
    try:
        with _db_session(state) as session:
            item = get_remediation_item(session, item_id)
            if item is None:
                raise HTTPException(status_code=404, detail="remediation item not found")
            _require_visible_project(state, user, item.project_key)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="remediation store unavailable") from exc

    upload_store = state.document_upload_store
    if upload_store is None:
        return {"format": "remediation-attachments-v1", "item_id": str(item_id), "items": []}

    uploads = upload_store.list_uploads(
        created_by=None,
        include_all=True,
        project_key=f"remediation:{item_id}",
        limit=200,
    )
    return {
        "format": "remediation-attachments-v1",
        "item_id": str(item_id),
        "items": uploads,
        "count": len(uploads),
    }
