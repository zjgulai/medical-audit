from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.exc import SQLAlchemyError

from medical_audit_kb.api.app import ApiState, get_api_state, record_operation
from medical_audit_kb.api.project_member_store import (
    DEFAULT_PROJECT_PAYLOADS,
    PROJECT_MEMBER_ROLES,
    PROJECT_MEMBER_STATUSES,
    InMemoryProjectMemberStore,
    ProjectMemberStore,
    combined_project_members,
    project_exists,
    project_payloads_with_member_counts,
    validate_project_member_role,
    validate_project_member_status,
)
from medical_audit_kb.api.role_policy import require_audit_role_for_write

router = APIRouter()


class ProjectMemberCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=128)
    role: str = Field(min_length=1, max_length=48)
    department: str = Field(min_length=1, max_length=128)
    status: str = Field(default="待确认", min_length=1, max_length=48)
    metadata: dict[str, object] = Field(default_factory=dict)

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


@router.get("/projects")
def list_projects(
    state: Annotated[ApiState, Depends(get_api_state)],
) -> dict[str, object]:
    try:
        items = project_payloads_with_member_counts(_project_member_store(state).member_counts())
    except SQLAlchemyError:
        return {
            "items": [dict(project) for project in DEFAULT_PROJECT_PAYLOADS],
            "roles": list(PROJECT_MEMBER_ROLES),
            "statuses": list(PROJECT_MEMBER_STATUSES),
            "store": {"ready": False, "backend": "unavailable"},
        }

    record_operation(state, "projects-list", {"project_count": len(items)})
    return {
        "items": items,
        "roles": list(PROJECT_MEMBER_ROLES),
        "statuses": list(PROJECT_MEMBER_STATUSES),
        "store": {"ready": True, "backend": _project_member_store(state).__class__.__name__},
    }


@router.get("/projects/{project_key}/members")
def list_project_members(
    project_key: str,
    state: Annotated[ApiState, Depends(get_api_state)],
) -> dict[str, object]:
    _require_project(project_key)
    try:
        custom_members = _project_member_store(state).list_members(project_key)
    except SQLAlchemyError:
        return {
            "items": combined_project_members(project_key, []),
            "project_key": project_key,
            "roles": list(PROJECT_MEMBER_ROLES),
            "statuses": list(PROJECT_MEMBER_STATUSES),
            "store": {"ready": False, "backend": "unavailable"},
        }

    items = combined_project_members(project_key, custom_members)
    record_operation(
        state,
        "project-members-list",
        {"project_key": project_key, "member_count": len(items)},
    )
    return {
        "items": items,
        "project_key": project_key,
        "roles": list(PROJECT_MEMBER_ROLES),
        "statuses": list(PROJECT_MEMBER_STATUSES),
        "store": {"ready": True, "backend": _project_member_store(state).__class__.__name__},
    }


@router.post("/projects/{project_key}/members")
def create_project_member(
    project_key: str,
    payload: ProjectMemberCreateRequest,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> dict[str, object]:
    _require_project(project_key)
    actor_role = require_audit_role_for_write(
        state,
        role=x_role,
        user_identifier=x_user_id,
        attempted_action="project-member-create",
        denied_action="project-member-access-denied",
    )
    values = payload.model_dump()
    values["created_by"] = x_user_id or "anonymous"
    try:
        member = _project_member_store(state).add_member(project_key, values)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=409,
            detail="persistent project member store is not available",
        ) from exc

    record_operation(
        state,
        "project-member-create",
        {
            "project_key": project_key,
            "member_id": member["id"],
            "role": member["role"],
            "actor_role": actor_role,
            "created_by": x_user_id or "anonymous",
        },
    )
    return {
        "item": member,
        "store": {"ready": True, "backend": _project_member_store(state).__class__.__name__},
    }


def _require_project(project_key: str) -> None:
    if not project_exists(project_key):
        raise HTTPException(status_code=404, detail="project not found")


def _project_member_store(state: ApiState) -> ProjectMemberStore:
    if state.project_member_store is None:
        state.project_member_store = InMemoryProjectMemberStore()
    return state.project_member_store
