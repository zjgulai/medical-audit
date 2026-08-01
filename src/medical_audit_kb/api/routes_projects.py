from __future__ import annotations

from typing import Annotated, cast
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Response, UploadFile
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy.exc import SQLAlchemyError

from medical_audit_kb.api.app import ApiState, get_api_state, record_operation
from medical_audit_kb.api.auth import (
    AuthenticatedUser,
    HospitalRole,
    Permission,
    require_permission,
    resolve_authenticated_user,
    user_has_permission,
)
from medical_audit_kb.api.project_member_store import (
    PROJECT_MEMBER_ROLES,
    PROJECT_MEMBER_STATUSES,
    PROJECT_STATUSES,
    InMemoryProjectMemberStore,
    ProjectIdentityConflictError,
    ProjectMemberIdentityConflictError,
    ProjectMemberStore,
    combined_project_members,
    project_exists,
    project_payloads_with_member_counts,
    supports_persistent_project_writes,
    validate_project_member_role,
    validate_project_member_status,
    visible_project_keys,
)
from medical_audit_kb.api.review_task_store import supports_persistent_review_task_writes

router = APIRouter()

REVIEW_STATUS_LABELS: dict[str, str] = {
    "pending-review": "待复核",
    "needs-evidence": "需补证",
    "confirmed-violation": "确认违规",
    "not-violation": "排除违规",
    "closed": "已关闭",
}
MAX_PROJECT_FILE_BYTES = 20 * 1024 * 1024
SUPPORTED_PROJECT_FILE_EXTENSIONS = {"csv", "md", "pdf", "xlsm", "xlsx", "txt"}
PROJECT_DOCUMENT_TYPES = (
    "审计资料",
    "财务资料",
    "业务资料",
    "制度文件",
    "整改材料",
    "其他",
)
PROJECT_FILE_REVIEW_STATUSES = ("approved", "changes-requested", "withdrawn")


class ProjectMemberCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_identifier: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=128)
    role: str = Field(min_length=1, max_length=48)
    department: str = Field(min_length=1, max_length=128)
    status: str = Field(default="待确认", min_length=1, max_length=48)
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("user_identifier")
    @classmethod
    def normalize_user_identifier(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("user_identifier is required")
        return normalized

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        try:
            return validate_project_member_role(value)
        except ValueError as exc:
            raise ValueError("unsupported project member role") from exc

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        try:
            return validate_project_member_status(value)
        except ValueError as exc:
            raise ValueError("unsupported project member status") from exc


class ProjectCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_key: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
    )
    name: str = Field(min_length=1, max_length=256)
    scenario_key: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
    )
    audit_topic: str = Field(min_length=1, max_length=128)
    organization_name: str = Field(min_length=1, max_length=256)
    owner_department: str | None = Field(default=None, max_length=128)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator(
        "project_key",
        "name",
        "scenario_key",
        "audit_topic",
        "organization_name",
        "owner_department",
        "description",
    )
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized


class ProjectFileReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    note: str = Field(default="", max_length=1000)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in PROJECT_FILE_REVIEW_STATUSES:
            raise ValueError("unsupported project file review status")
        return value

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def require_note_for_non_approval(self) -> ProjectFileReviewRequest:
        if self.status in {"changes-requested", "withdrawn"} and not self.note:
            raise ValueError("note is required for changes-requested or withdrawn")
        return self


@router.post("/projects", status_code=201)
def create_project(
    payload: ProjectCreateRequest,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> dict[str, object]:
    user = require_permission(
        state,
        permission=Permission.CREATE_PROJECT,
        x_user_id=x_user_id,
        x_role=x_role,
        attempted_action="project-create",
    )
    store = _required_project_member_store(state)
    if state.audit_log_store is None:
        state.operation_logs.append(
            {
                "action": "project-create-audit-unavailable",
                "payload": {
                    "project_key": payload.project_key,
                    "user_identifier": user.user_identifier,
                    "role": user.role.value,
                    "endpoint": "/projects",
                    "status_code": 503,
                    "reason": "audit-store-missing",
                },
            }
        )
        raise HTTPException(
            status_code=503,
            detail="project creation audit is not available",
        )
    intent_payload: dict[str, object] = {
        "project_key": payload.project_key,
        "user_identifier": user.user_identifier,
        "role": user.role.value,
        "endpoint": "/projects",
        "scenario_key": payload.scenario_key,
    }
    try:
        record_operation(state, "project-create-intent", intent_payload)
    except SQLAlchemyError as exc:
        state.operation_logs.append(
            {
                "action": "project-create-audit-unavailable",
                "payload": {
                    **intent_payload,
                    "status_code": 503,
                    "reason": "audit-intent-unavailable",
                    "error_type": type(exc).__name__,
                },
            }
        )
        raise HTTPException(
            status_code=503,
            detail="project creation audit is not available",
        ) from exc
    values = payload.model_dump()
    values.update(
        {
            "status": "待开始",
            "created_by": user.user_identifier,
            "creator_display_name": user.user_identifier,
            "metadata": {
                "audit_topic": payload.audit_topic,
                "organization_name": payload.organization_name,
                "project_surface": "collaboration-v1",
            },
        }
    )
    try:
        project, creator_member = store.create_project(values)
    except ProjectIdentityConflictError as exc:
        _record_project_operation_best_effort(
            state,
            "project-create-conflict",
            {
                "project_key": payload.project_key,
                "user_identifier": user.user_identifier,
                "role": user.role.value,
                "endpoint": "/projects",
                "status_code": 409,
                "reason": "project key already exists",
            },
        )
        raise HTTPException(status_code=409, detail="project key already exists") from exc
    except SQLAlchemyError as exc:
        _record_project_operation_best_effort(
            state,
            "project-create-unavailable",
            {
                "project_key": payload.project_key,
                "user_identifier": user.user_identifier,
                "role": user.role.value,
                "endpoint": "/projects",
                "status_code": 503,
                "reason": "persistent project store is not available",
                "error_type": type(exc).__name__,
            },
        )
        raise HTTPException(
            status_code=503,
            detail="persistent project store is not available",
        ) from exc

    audit_recorded = _record_project_operation_best_effort(
        state,
        "project-create",
        {
            "project_key": payload.project_key,
            "user_identifier": user.user_identifier,
            "role": user.role.value,
            "endpoint": "/projects",
            "scenario_key": payload.scenario_key,
            "status": "待开始",
            "status_code": 201,
        },
    )
    return {
        "item": project,
        "creator_member": creator_member,
        "store": {
            "ready": True,
            "backend": store.__class__.__name__,
            "persistent_writes_ready": True,
        },
        "audit": {"status": "recorded" if audit_recorded else "degraded"},
    }


@router.get("/projects")
def list_projects(
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
    configured_store = state.project_member_store
    store = _project_member_store(state)
    if configured_store is None:
        custom_counts = {}
        counts_ready = False
    else:
        try:
            custom_counts = store.member_counts()
            counts_ready = True
        except SQLAlchemyError:
            custom_counts = {}
            counts_ready = False

    visible_keys, visibility_ready = _project_visibility(
        user=user,
        store=store,
    )
    if not visibility_ready:
        custom_counts = {}
        counts_ready = False
    all_items = project_payloads_with_member_counts(
        custom_counts,
        store if visibility_ready else None,
    )
    if not counts_ready:
        all_items = [
            {
                **item,
                "member_count": None,
            }
            for item in all_items
        ]
    items = [item for item in all_items if str(item["id"]) in visible_keys]
    store_ready = counts_ready and visibility_ready
    store_backend = store.__class__.__name__ if store_ready else "unavailable"

    record_operation(
        state,
        "projects-list",
        {
            "actor": user.user_identifier,
            "actor_role": user.role.value,
            "project_count": len(items),
            "visible_project_count": len(items),
            "visibility_ready": visibility_ready,
            "member_counts_ready": counts_ready,
        },
    )
    return {
        "items": items,
        "roles": list(PROJECT_MEMBER_ROLES),
        "statuses": list(PROJECT_MEMBER_STATUSES),
        "project_statuses": list(PROJECT_STATUSES),
        "store": {
            "ready": store_ready,
            "backend": store_backend,
            "persistent_writes_ready": supports_persistent_project_writes(
                configured_store
            ),
            "history_review_task_writes_ready": (
                supports_persistent_project_writes(configured_store)
                and supports_persistent_review_task_writes(state.review_task_store)
            ),
        },
    }


@router.get("/projects/{project_key}/files")
def list_project_files(
    project_key: str,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> dict[str, object]:
    user, _store, _visible_keys, _visibility_ready = _visible_project_user(
        project_key,
        state,
        x_user_id=x_user_id,
        x_role=x_role,
    )
    if state.document_upload_store is None:
        return {
            "contract_version": "project-files-v2",
            "project_key": project_key,
            "items": [],
            "store": {"ready": False, "backend": "none"},
            "permissions": _project_file_permissions(user),
        }
    can_review = user_has_permission(user, Permission.REVIEW_PROJECT_FILE)
    items = [
        _project_file_payload(item, project_key=project_key)
        for item in state.document_upload_store.list_uploads(
            created_by=None if can_review else user.user_identifier,
            include_all=can_review,
            scope="project",
            project_key=project_key,
            limit=100,
        )
    ]
    record_operation(
        state,
        "project-files-list",
        {
            "project_key": project_key,
            "count": len(items),
            "user_identifier": user.user_identifier,
            "role": user.role.value,
        },
    )
    return {
        "contract_version": "project-files-v2",
        "project_key": project_key,
        "items": items,
        "store": {
            "ready": True,
            "backend": state.document_upload_store.__class__.__name__,
        },
        "permissions": _project_file_permissions(user),
    }


@router.post("/projects/{project_key}/files", status_code=201)
async def upload_project_file(
    project_key: str,
    file: Annotated[UploadFile, File()],
    state: Annotated[ApiState, Depends(get_api_state)],
    department: Annotated[str, Form(max_length=128)] = "",
    document_type: Annotated[str, Form(max_length=64)] = "其他",
    description: Annotated[str, Form(max_length=1000)] = "",
    replaces_upload_id: Annotated[str, Form(max_length=128)] = "",
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> dict[str, object]:
    user = require_permission(
        state,
        permission=Permission.UPLOAD_PROJECT_FILE,
        x_user_id=x_user_id,
        x_role=x_role,
        attempted_action="project-file-upload",
        project_key=project_key,
    )
    _visible_user, store, _visible_keys, _visibility_ready = _visible_project_user(
        project_key,
        state,
        x_user_id=x_user_id,
        x_role=x_role,
    )
    if state.document_upload_store is None:
        raise HTTPException(status_code=409, detail="document upload store is not configured")
    project = _project_payload(project_key, store)
    if project.get("status") == "已归档":
        raise HTTPException(status_code=409, detail="archived project does not accept files")
    normalized_document_type = document_type.strip() or "其他"
    if normalized_document_type not in PROJECT_DOCUMENT_TYPES:
        raise HTTPException(status_code=422, detail="unsupported project document type")
    normalized_department = department.strip() or _project_member_department(
        project_key=project_key,
        user_identifier=user.user_identifier,
        store=store,
    )
    normalized_replaces_upload_id = replaces_upload_id.strip()
    if normalized_replaces_upload_id:
        replaced = state.document_upload_store.get_upload(
            upload_id=normalized_replaces_upload_id
        )
        if (
            replaced is None
            or replaced.get("scope") != "project"
            or replaced.get("project_key") != project_key
            or replaced.get("created_by") != user.user_identifier
            or replaced.get("project_review_status") != "changes-requested"
        ):
            raise HTTPException(status_code=409, detail="replacement source is not eligible")
    file_name = file.filename or "project-file"
    extension = _project_file_extension(file_name)
    if extension not in SUPPORTED_PROJECT_FILE_EXTENSIONS:
        raise HTTPException(status_code=422, detail="unsupported project file extension")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=422, detail="project file is empty")
    if len(content) > MAX_PROJECT_FILE_BYTES:
        raise HTTPException(status_code=413, detail="project file is too large")
    stored = state.document_upload_store.add_upload(
        file_name=file_name,
        extension=extension,
        content=content,
        created_by=user.user_identifier,
        metadata={
            "scope": "project",
            "project_key": project_key,
            "project_name": str(project["name"]),
            "department": normalized_department,
            "document_type": normalized_document_type,
            "description": description.strip(),
            "replaces_upload_id": normalized_replaces_upload_id or None,
        },
    )
    item = _project_file_payload(stored, project_key=project_key)
    record_operation(
        state,
        "project-file-upload",
        {
            "project_key": project_key,
            "upload_id": item["id"],
            "extension": extension,
            "size_bytes": len(content),
            "user_identifier": user.user_identifier,
            "role": user.role.value,
            "department": normalized_department,
            "document_type": normalized_document_type,
            "replaces_upload_id": normalized_replaces_upload_id or None,
        },
    )
    return {
        "contract_version": "project-files-v2",
        "project_key": project_key,
        "item": item,
        "store": {
            "ready": True,
            "backend": state.document_upload_store.__class__.__name__,
        },
    }


@router.post("/projects/{project_key}/files/{upload_id}/review")
def review_project_file(
    project_key: str,
    upload_id: str,
    payload: ProjectFileReviewRequest,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> dict[str, object]:
    user, _store, _visible_keys, _visibility_ready = _visible_project_user(
        project_key,
        state,
        x_user_id=x_user_id,
        x_role=x_role,
    )
    if state.document_upload_store is None:
        raise HTTPException(status_code=409, detail="document upload store is not configured")
    item = state.document_upload_store.get_upload(upload_id=upload_id)
    if (
        item is None
        or item.get("scope") != "project"
        or item.get("project_key") != project_key
    ):
        raise HTTPException(status_code=404, detail="project file not found")
    if not _project_file_visible_to_user(item=item, user=user):
        raise HTTPException(status_code=404, detail="project file not found")
    if item.get("project_review_status") != "pending-review":
        raise HTTPException(status_code=409, detail="project file review is already closed")

    if payload.status == "withdrawn":
        if item.get("created_by") != user.user_identifier:
            raise HTTPException(status_code=403, detail="only the uploader can withdraw this file")
    else:
        user = require_permission(
            state,
            permission=Permission.REVIEW_PROJECT_FILE,
            x_user_id=x_user_id,
            x_role=x_role,
            attempted_action="project-file-review",
            project_key=project_key,
        )

    updated = state.document_upload_store.update_project_file_review(
        upload_id=upload_id,
        review_status=payload.status,
        reviewed_by=user.user_identifier,
        review_note=payload.note,
    )
    if updated is None:
        current = state.document_upload_store.get_upload(upload_id=upload_id)
        if (
            current is not None
            and current.get("scope") == "project"
            and current.get("project_key") == project_key
        ):
            raise HTTPException(status_code=409, detail="project file review is already closed")
        raise HTTPException(status_code=404, detail="project file not found")
    result = _project_file_payload(updated, project_key=project_key)
    record_operation(
        state,
        "project-file-review",
        {
            "project_key": project_key,
            "upload_id": upload_id,
            "review_status": payload.status,
            "user_identifier": user.user_identifier,
            "role": user.role.value,
        },
    )
    return {
        "contract_version": "project-files-v2",
        "project_key": project_key,
        "item": result,
    }


@router.get("/projects/{project_key}/files/{upload_id}/preview")
def preview_project_file(
    project_key: str,
    upload_id: str,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> Response:
    return _project_file_response(
        project_key=project_key,
        upload_id=upload_id,
        state=state,
        x_user_id=x_user_id,
        x_role=x_role,
        disposition="inline",
    )


@router.get("/projects/{project_key}/files/{upload_id}/download")
def download_project_file(
    project_key: str,
    upload_id: str,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> Response:
    return _project_file_response(
        project_key=project_key,
        upload_id=upload_id,
        state=state,
        x_user_id=x_user_id,
        x_role=x_role,
        disposition="attachment",
    )


@router.get("/projects/{project_key}")
def get_project(
    project_key: str,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> dict[str, object]:
    user, store, visible_keys, visibility_ready = _visible_project_user(
        project_key,
        state,
        x_user_id=x_user_id,
        x_role=x_role,
    )
    if visibility_ready:
        try:
            project = next(
                item
                for item in project_payloads_with_member_counts(store.member_counts(), store)
                if item["id"] == project_key
            )
            store_ready = True
            store_backend = store.__class__.__name__
        except SQLAlchemyError:
            project = _fallback_project_payload(project_key)
            store_ready = False
            store_backend = "unavailable"
    else:
        project = _fallback_project_payload(project_key)
        store_ready = False
        store_backend = "unavailable"

    record_operation(
        state,
        "project-detail",
        {
            "project_key": project_key,
            "actor": user.user_identifier,
            "actor_role": user.role.value,
            "visible_project_count": len(visible_keys),
            "visibility_ready": visibility_ready,
        },
    )
    return {
        "item": project,
        "store": {"ready": store_ready, "backend": store_backend},
        "production_side_effect": "none",
    }


@router.get("/projects/{project_key}/members")
def list_project_members(
    project_key: str,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> dict[str, object]:
    user, store, visible_keys, visibility_ready = _visible_project_user(
        project_key,
        state,
        x_user_id=x_user_id,
        x_role=x_role,
    )
    if visibility_ready:
        try:
            custom_members = store.list_members(project_key)
            store_ready = True
            store_backend = store.__class__.__name__
        except SQLAlchemyError:
            custom_members = []
            store_ready = False
            store_backend = "unavailable"
    else:
        custom_members = []
        store_ready = False
        store_backend = "unavailable"

    items = combined_project_members(project_key, custom_members)
    record_operation(
        state,
        "project-members-list",
        {
            "project_key": project_key,
            "actor": user.user_identifier,
            "actor_role": user.role.value,
            "visible_project_count": len(visible_keys),
            "visibility_ready": visibility_ready,
            "member_count": len(items),
        },
    )
    return {
        "items": items,
        "project_key": project_key,
        "roles": list(PROJECT_MEMBER_ROLES),
        "statuses": list(PROJECT_MEMBER_STATUSES),
        "store": {"ready": store_ready, "backend": store_backend},
    }


@router.get("/projects/{project_key}/dashboard")
def project_dashboard(
    project_key: str,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> dict[str, object]:
    user, store, visible_keys, visibility_ready = _visible_project_user(
        project_key,
        state,
        x_user_id=x_user_id,
        x_role=x_role,
    )
    if visibility_ready:
        try:
            project = next(
                item for item in project_payloads_with_member_counts(store.member_counts(), store)
                if item["id"] == project_key
            )
            members = combined_project_members(project_key, store.list_members(project_key))
            member_store_ready = True
            member_store_backend = store.__class__.__name__
        except SQLAlchemyError:
            project = _fallback_project_payload(project_key)
            members = combined_project_members(project_key, [])
            member_store_ready = False
            member_store_backend = "unavailable"
    else:
        project = _fallback_project_payload(project_key)
        members = combined_project_members(project_key, [])
        member_store_ready = False
        member_store_backend = "unavailable"

    findings, finding_store_payload = _dashboard_findings(state, project_key)
    stats = _dashboard_finding_stats(findings)
    audit_findings_ready = bool(finding_store_payload["ready"])
    if member_store_ready and audit_findings_ready:
        store_status = "ready"
        evidence_grade = "live-db-connected"
    elif member_store_ready or audit_findings_ready:
        store_status = "partial"
        evidence_grade = "partial-live-db-connected"
    else:
        store_status = "unavailable"
        evidence_grade = "backend-defaults"
    response: dict[str, object] = {
        "format": "project-dashboard-v1",
        "project": project,
        "metrics": _dashboard_metrics(stats, findings, members),
        "queue": _dashboard_queue(findings),
        "activities": _dashboard_activities(stats, findings, member_store_ready),
        "status_distribution": _dashboard_status_distribution(findings),
        "member_workloads": _dashboard_member_workloads(members, findings),
        "evidence_grade": evidence_grade,
        "production_side_effect": "none",
        "store": {
            "ready": member_store_ready and audit_findings_ready,
            "project_members_ready": member_store_ready,
            "audit_findings_ready": audit_findings_ready,
            "status": store_status,
            "backend": {
                "project_members": member_store_backend,
                "audit_findings": finding_store_payload["backend"],
            },
        },
    }
    record_operation(
        state,
        "project-dashboard",
        {
            "project_key": project_key,
            "actor": user.user_identifier,
            "actor_role": user.role.value,
            "visible_project_count": len(visible_keys),
            "visibility_ready": visibility_ready,
            "member_count": len(members),
            "finding_count": stats["total"],
            "member_store_ready": member_store_ready,
            "finding_store_ready": bool(finding_store_payload["ready"]),
        },
    )
    return response


@router.post("/projects/{project_key}/members")
def create_project_member(
    project_key: str,
    payload: ProjectMemberCreateRequest,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> dict[str, object]:
    store = _required_project_member_store(state)
    _require_project(project_key, store)
    user = require_permission(
        state,
        permission=Permission.MANAGE_PROJECT_MEMBERS,
        x_user_id=x_user_id,
        x_role=x_role,
        attempted_action="project-member-create",
        project_key=project_key,
    )
    values = payload.model_dump()
    values["created_by"] = user.user_identifier
    try:
        member = store.add_member(project_key, values)
    except ProjectMemberIdentityConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail="project member identity already exists",
        ) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="persistent project member store is not available",
        ) from exc

    record_operation(
        state,
        "project-member-create",
        {
            "project_key": project_key,
            "member_id": member["id"],
            "role": member["role"],
            "created_by": user.user_identifier,
            "actor_role": user.role.value,
            "actor_role_label": user.role_label,
        },
    )
    return {
        "item": member,
        "store": {"ready": True, "backend": store.__class__.__name__},
    }


def _require_project(project_key: str, store: ProjectMemberStore) -> None:
    try:
        exists = project_exists(project_key, store)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="project store is not available",
        ) from exc
    if not exists:
        raise HTTPException(status_code=404, detail="project not found")


def _fallback_project_payload(project_key: str) -> dict[str, object]:
    project = next(
        (
            item
            for item in project_payloads_with_member_counts({}, None)
            if item["id"] == project_key
        ),
        None,
    )
    if project is None:
        raise HTTPException(status_code=503, detail="project store is not available")
    project["member_count"] = None
    return project


def _record_project_operation_best_effort(
    state: ApiState,
    action: str,
    payload: dict[str, object],
) -> bool:
    try:
        record_operation(state, action, payload)
    except SQLAlchemyError as exc:
        state.operation_logs.append(
            {
                "action": f"{action}-audit-degraded",
                "payload": {**payload, "error_type": type(exc).__name__},
            }
        )
        return False
    return True


def _visible_project_user(
    project_key: str,
    state: ApiState,
    *,
    x_user_id: str | None,
    x_role: str | None,
) -> tuple[AuthenticatedUser, ProjectMemberStore, frozenset[str], bool]:
    store_configured = state.project_member_store is not None
    store = _project_member_store(state)
    _require_project(project_key, store)
    user = resolve_authenticated_user(
        state,
        x_user_id=x_user_id,
        x_role=x_role,
        default_role=HospitalRole.MEMBER,
        project_key=project_key,
    )
    visible_keys, visibility_ready = _project_visibility(
        user=user,
        store=store,
    )
    if project_key not in visible_keys:
        raise HTTPException(status_code=404, detail="project not found")
    return user, store, visible_keys, visibility_ready and store_configured


def _project_visibility(
    *,
    user: AuthenticatedUser,
    store: ProjectMemberStore,
) -> tuple[frozenset[str], bool]:
    try:
        return (
            visible_project_keys(
                user_identifier=user.user_identifier,
                is_admin=user.role is HospitalRole.ADMIN,
                store=store,
            ),
            True,
        )
    except SQLAlchemyError:
        return (
            visible_project_keys(
                user_identifier=user.user_identifier,
                is_admin=user.role is HospitalRole.ADMIN,
                store=InMemoryProjectMemberStore(),
            ),
            False,
        )


def _project_member_store(state: ApiState) -> ProjectMemberStore:
    return state.project_member_store or InMemoryProjectMemberStore()


def _required_project_member_store(state: ApiState) -> ProjectMemberStore:
    if not supports_persistent_project_writes(state.project_member_store):
        raise HTTPException(
            status_code=503,
            detail="persistent project store is not available",
        )
    assert state.project_member_store is not None
    return state.project_member_store


def _project_file_payload(
    item: dict[str, object],
    *,
    project_key: str,
) -> dict[str, object]:
    upload_id = str(item["id"])
    return {
        "id": upload_id,
        "name": str(item["name"]),
        "extension": str(item["extension"]),
        "size_bytes": int(item["size_bytes"]),
        "sha256": str(item["sha256"]),
        "created_by": item.get("created_by"),
        "created_at": str(item["created_at"]),
        "project_name": str(item.get("project_name") or project_key),
        "department": str(item.get("department") or ""),
        "document_type": str(item.get("document_type") or "其他"),
        "description": str(item.get("description") or ""),
        "replaces_upload_id": item.get("replaces_upload_id"),
        "review_status": str(item.get("project_review_status") or "pending-review"),
        "review_note": str(item.get("project_review_note") or ""),
        "reviewed_by": item.get("project_reviewed_by"),
        "reviewed_at": item.get("project_reviewed_at"),
        "review_history": item.get("project_review_history") or [],
        "security_scan_status": str(item["security_scan_status"]),
        "dlp_status": str(item["dlp_status"]),
        "preview_url": (
            f"/api/v1/projects/{project_key}/files/{upload_id}/preview"
        ),
        "download_url": (
            f"/api/v1/projects/{project_key}/files/{upload_id}/download"
        ),
    }


def _project_file_response(
    *,
    project_key: str,
    upload_id: str,
    state: ApiState,
    x_user_id: str | None,
    x_role: str | None,
    disposition: str,
) -> Response:
    user, _store, _visible_keys, _visibility_ready = _visible_project_user(
        project_key,
        state,
        x_user_id=x_user_id,
        x_role=x_role,
    )
    if state.document_upload_store is None:
        raise HTTPException(status_code=409, detail="document upload store is not configured")
    retained = state.document_upload_store.read_upload_content(upload_id=upload_id)
    if retained is None:
        raise HTTPException(status_code=404, detail="project file not found")
    item, content = retained
    if item.get("scope") != "project" or item.get("project_key") != project_key:
        raise HTTPException(status_code=404, detail="project file not found")
    if not _project_file_visible_to_user(item=item, user=user):
        raise HTTPException(status_code=404, detail="project file not found")
    file_name = str(item["name"]).replace("/", "_").replace("\\", "_")
    extension = str(item["extension"])
    record_operation(
        state,
        f"project-file-{disposition}",
        {
            "project_key": project_key,
            "upload_id": upload_id,
            "user_identifier": user.user_identifier,
            "role": user.role.value,
        },
    )
    return Response(
        content=content,
        media_type=_project_file_media_type(extension),
        headers={
            "Content-Disposition": (
                f"{disposition}; filename*=UTF-8''{quote(file_name)}"
            ),
            "X-Project-Key": project_key,
            "X-Document-Upload-Id": upload_id,
        },
    )


def _project_file_extension(file_name: str) -> str:
    if "." not in file_name:
        return ""
    return file_name.rsplit(".", maxsplit=1)[-1].lower()


def _project_file_permissions(user: AuthenticatedUser) -> dict[str, object]:
    return {
        "can_upload": user_has_permission(user, Permission.UPLOAD_PROJECT_FILE),
        "can_review": user_has_permission(user, Permission.REVIEW_PROJECT_FILE),
        "can_withdraw_own": user_has_permission(user, Permission.UPLOAD_PROJECT_FILE),
        "visibility_scope": (
            "project" if user_has_permission(user, Permission.REVIEW_PROJECT_FILE) else "own"
        ),
    }


def _project_file_visible_to_user(
    *,
    item: dict[str, object],
    user: AuthenticatedUser,
) -> bool:
    return user_has_permission(user, Permission.REVIEW_PROJECT_FILE) or (
        item.get("created_by") == user.user_identifier
    )


def _project_payload(
    project_key: str,
    store: ProjectMemberStore,
) -> dict[str, object]:
    try:
        return next(
            item
            for item in project_payloads_with_member_counts(store.member_counts(), store)
            if item["id"] == project_key
        )
    except StopIteration as exc:
        raise HTTPException(status_code=404, detail="project not found") from exc
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="project store is not available") from exc


def _project_member_department(
    *,
    project_key: str,
    user_identifier: str,
    store: ProjectMemberStore,
) -> str:
    try:
        members = combined_project_members(project_key, store.list_members(project_key))
    except SQLAlchemyError:
        return ""
    for member in members:
        if (
            member.get("user_identifier") == user_identifier
            and member.get("status") == "在项目中"
        ):
            return str(member.get("department") or "")
    return ""


def _project_file_media_type(extension: str) -> str:
    return {
        "csv": "text/csv; charset=utf-8",
        "md": "text/markdown; charset=utf-8",
        "pdf": "application/pdf",
        "txt": "text/plain; charset=utf-8",
        "xlsm": "application/vnd.ms-excel.sheet.macroEnabled.12",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }.get(extension, "application/octet-stream")


def _dashboard_findings(
    state: ApiState,
    project_key: str,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    if state.audit_finding_store is None:
        return [], {"ready": False, "backend": "none"}
    try:
        findings = state.audit_finding_store.list_findings(
            project_key=project_key,
            limit=100,
        )
    except SQLAlchemyError:
        return [], {"ready": False, "backend": "unavailable"}
    return findings, {"ready": True, "backend": state.audit_finding_store.__class__.__name__}


def _dashboard_finding_stats(findings: list[dict[str, object]]) -> dict[str, int]:
    return {
        "total": len(findings),
        "open": sum(1 for item in findings if item.get("status") == "open"),
        "status_present": sum(
            1 for item in findings if str(item.get("status") or "").strip()
        ),
        "pending_review": sum(
            1 for item in findings if item.get("review_status") == "pending-review"
        ),
        "needs_evidence": sum(
            1 for item in findings if item.get("review_status") == "needs-evidence"
        ),
        "linked_review_task": sum(1 for item in findings if item.get("review_task_id")),
    }


def _dashboard_metrics(
    stats: dict[str, int],
    findings: list[dict[str, object]],
    members: list[dict[str, object]],
) -> list[dict[str, str]]:
    open_findings = stats["open"] if stats["status_present"] else stats["total"]
    return [
        {
            "key": "open_findings",
            "label": "待处理疑点",
            "value": str(open_findings),
            "helper": "来自审计疑点库，需人工确认后进入底稿",
            "tone": "danger" if open_findings else "neutral",
        },
        {
            "key": "missing_evidence",
            "label": "待补证据",
            "value": str(stats["needs_evidence"]),
            "helper": "需补充结算明细、目录限制或身份字段",
            "tone": "warning" if stats["needs_evidence"] else "neutral",
        },
        {
            "key": "rule_cards",
            "label": "已关联任务",
            "value": str(stats["linked_review_task"]),
            "helper": f"当前专题成员 {len(members)} 人",
            "tone": "info",
        },
        {
            "key": "backend_status",
            "label": "资料可检索",
            "value": "已接入" if findings else "待生成",
            "helper": "读取后端项目成员与疑点 store",
            "tone": "success" if findings else "neutral",
        },
    ]


def _dashboard_queue(findings: list[dict[str, object]]) -> list[dict[str, str]]:
    if not findings:
        return [
            {
                "id": "QUEUE-BACKEND-001",
                "title": "导入或生成首批审计疑点后进入人工复核",
                "owner": "项目负责人",
                "dueLabel": "待启动",
                "status": "open",
                "risk": "medium",
            }
        ]
    return [
        _finding_to_queue_item(index, finding)
        for index, finding in enumerate(findings[:5], start=1)
    ]


def _finding_to_queue_item(index: int, finding: dict[str, object]) -> dict[str, str]:
    severity = str(finding.get("severity") or "").lower()
    review_status = str(finding.get("review_status") or "")
    return {
        "id": str(finding.get("finding_key") or f"QUEUE-{index:03d}"),
        "title": _finding_title(finding, index),
        "owner": _finding_owner(finding),
        "dueLabel": REVIEW_STATUS_LABELS.get(review_status, "待确认"),
        "status": "closed" if review_status in {"closed", "not-violation"} else "open",
        "risk": (
            "high"
            if severity in {"high", "高"}
            else "medium" if severity in {"medium", "中"} else "low"
        ),
    }


def _finding_title(finding: dict[str, object], index: int) -> str:
    metadata = _dict_like(finding.get("metadata"))
    calculation_trace = _dict_like(finding.get("calculation_trace"))
    for key in ("title", "finding_title", "description", "summary"):
        value = metadata.get(key) or calculation_trace.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return f"复核第 {index} 条{finding.get('finding_type') or '审计'}疑点"


def _dashboard_activities(
    stats: dict[str, int],
    findings: list[dict[str, object]],
    member_store_ready: bool,
) -> list[dict[str, str]]:
    if not findings:
        return [
            {
                "id": "ACT-BACKEND-001",
                "title": "项目成员接口已接入",
                "description": "当前驾驶舱读取后端项目成员 store，疑点数据等待生成或导入。",
                "timeLabel": "刚刚",
            }
        ]
    return [
        {
            "id": "ACT-BACKEND-001",
            "title": "审计疑点已同步",
            "description": (
                f"当前读取 {stats['total']} 条疑点，"
                f"其中 {stats['pending_review']} 条待复核。"
            ),
            "timeLabel": "刚刚",
        },
        {
            "id": "ACT-BACKEND-002",
            "title": "项目成员接口已接入" if member_store_ready else "项目成员使用默认清单",
            "description": "驾驶舱会按后端成员和疑点负责人汇总承接情况。",
            "timeLabel": "刚刚",
        },
    ]


def _dashboard_status_distribution(findings: list[dict[str, object]]) -> list[dict[str, object]]:
    counts: dict[str, int] = {}
    for finding in findings:
        status = str(finding.get("review_status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    if not counts:
        return [{"status": "empty", "label": "暂无疑点", "count": 0}]
    return [
        {"status": status, "label": REVIEW_STATUS_LABELS.get(status, status), "count": count}
        for status, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)
    ]


def _dashboard_member_workloads(
    members: list[dict[str, object]],
    findings: list[dict[str, object]],
) -> list[dict[str, object]]:
    workloads: dict[str, dict[str, object]] = {}
    for member in members:
        name = str(member.get("name") or "未命名成员")
        workloads[name] = {
            "name": name,
            "role": str(member.get("role") or "成员"),
            "department": str(member.get("department") or ""),
            "total": 0,
            "pending": 0,
            "closed": 0,
        }
    for finding in findings:
        owner = _finding_owner(finding)
        item = workloads.setdefault(
            owner,
            {
                "name": owner,
                "role": "待分配",
                "department": "",
                "total": 0,
                "pending": 0,
                "closed": 0,
            },
        )
        item["total"] = cast(int, item["total"]) + 1
        review_status = str(finding.get("review_status") or "")
        if review_status in {"pending-review", "needs-evidence"}:
            item["pending"] = cast(int, item["pending"]) + 1
        if review_status in {"closed", "not-violation", "confirmed-violation"}:
            item["closed"] = cast(int, item["closed"]) + 1
    return sorted(
        workloads.values(),
        key=lambda item: (-cast(int, item["total"]), str(item["name"])),
    )[:8]


def _finding_owner(finding: dict[str, object]) -> str:
    for source in (
        _dict_like(finding.get("metadata")),
        _dict_like(finding.get("calculation_trace")),
        _dict_like(finding.get("source_record_locator")),
    ):
        for key in ("owner", "assignee", "auditor", "reviewer", "employee", "handler"):
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return "未分配"


def _dict_like(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}
