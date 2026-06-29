from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.exc import SQLAlchemyError

from medical_audit_kb.api.app import ApiState, get_api_state, record_operation
from medical_audit_kb.api.auth import (
    ROLE_LABELS,
    ROLE_PERMISSIONS,
    HospitalRole,
    Permission,
    normalize_hospital_role,
    require_permission,
    resolve_authenticated_user,
)
from medical_audit_kb.api.auth_user_store import (
    DEFAULT_AUTH_USERS,
    AuthUserStore,
    InMemoryAuthUserStore,
    combined_auth_departments,
    combined_auth_users,
)

router = APIRouter(prefix="/auth")

UserStatus = Literal["active", "disabled", "pending"]
RoleAssignmentStatus = Literal["active", "revoked", "pending"]
RoleScopeType = Literal["global", "project", "department"]


class AuthUserCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_key: str | None = Field(default=None, min_length=1, max_length=128)
    display_name: str = Field(min_length=1, max_length=128)
    department_key: str | None = Field(default=None, max_length=128)
    status: UserStatus = "active"
    metadata: dict[str, object] = Field(default_factory=dict)


class AuthUserUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, min_length=1, max_length=128)
    department_key: str | None = Field(default=None, max_length=128)
    status: UserStatus | None = None
    metadata: dict[str, object] | None = None


class AuthUserRoleAssignmentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str = Field(min_length=1, max_length=48)
    scope_type: RoleScopeType = "global"
    scope_key: str | None = Field(default=None, max_length=128)
    status: RoleAssignmentStatus = "active"
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        return normalize_hospital_role(value).value


class AuthUserRoleAssignmentUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str | None = Field(default=None, min_length=1, max_length=48)
    scope_type: RoleScopeType | None = None
    scope_key: str | None = Field(default=None, max_length=128)
    status: RoleAssignmentStatus | None = None
    metadata: dict[str, object] | None = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_hospital_role(value).value


@router.get("/roles")
def list_auth_roles() -> dict[str, object]:
    return {
        "items": [
            {
                "role": role.value,
                "label": ROLE_LABELS[role],
                "permissions": sorted(permission.value for permission in ROLE_PERMISSIONS[role]),
            }
            for role in HospitalRole
        ],
        "compatibility": {
            "auditor": "member",
            "it-admin": "admin",
            "system-admin": "admin",
            "department-head": "director",
        },
        "mode": "header_transition_layer",
    }


@router.get("/session")
def current_auth_session(
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
    x_project_key: Annotated[str | None, Header(alias="X-Project-Key")] = None,
    x_tenant_id: Annotated[str | None, Header(alias="X-Tenant-Id")] = None,
) -> dict[str, object]:
    user = resolve_authenticated_user(
        state,
        x_user_id=x_user_id,
        x_role=x_role,
        default_role=HospitalRole.MEMBER,
        project_key=x_project_key,
        tenant_id=x_tenant_id,
    )
    profile, store = _load_user_profile(state, user.user_identifier)
    return {
        "user_identifier": user.user_identifier,
        "role": user.role.value,
        "role_label": user.role_label,
        "permissions": sorted(permission.value for permission in ROLE_PERMISSIONS[user.role]),
        "legacy_api_role": user.legacy_api_role,
        "tenant_id": user.tenant_id,
        "auth_source": user.auth_source,
        "profile_status": user.profile_status,
        "auth_scope_type": user.auth_scope_type,
        "auth_scope_key": user.auth_scope_key,
        "auth_mode": "header_transition_layer",
        "profile": profile,
        "store": store,
    }


@router.get("/users")
def list_auth_users(
    state: Annotated[ApiState, Depends(get_api_state)],
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> dict[str, object]:
    actor = require_permission(
        state,
        permission=Permission.MANAGE_PROJECT_MEMBERS,
        x_user_id=x_user_id,
        x_role=x_role,
        attempted_action="auth-users-list",
    )
    try:
        store = _auth_user_store(state)
        users = combined_auth_users(store.list_users(limit=limit))
        departments = combined_auth_departments(store.list_departments())
        store_payload = {"ready": True, "backend": store.__class__.__name__}
    except SQLAlchemyError:
        users = [dict(user) for user in DEFAULT_AUTH_USERS][:limit]
        departments = combined_auth_departments([])
        store_payload = {"ready": False, "backend": "unavailable"}

    record_operation(
        state,
        "auth-users-list",
        {
            "count": len(users),
            "limit": limit,
            "user_identifier": actor.user_identifier,
            "role": actor.role.value,
        },
    )
    return {
        "items": users[:limit],
        "departments": departments,
        "roles": _role_items(),
        "store": store_payload,
        "auth_mode": "header_transition_layer",
    }


@router.post("/users")
def create_auth_user(
    payload: AuthUserCreateRequest,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> dict[str, object]:
    actor = require_permission(
        state,
        permission=Permission.MANAGE_PROJECT_MEMBERS,
        x_user_id=x_user_id,
        x_role=x_role,
        attempted_action="auth-user-create",
    )
    values = payload.model_dump()
    values["created_by"] = actor.user_identifier
    try:
        store = _auth_user_store(state)
        user = store.add_user(values)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=409,
            detail="persistent auth user store is not available",
        ) from exc

    record_operation(
        state,
        "auth-user-create",
        {
            "user_key": user["user_key"],
            "department_key": user.get("department_key"),
            "created_by": actor.user_identifier,
            "role": actor.role.value,
        },
    )
    return {
        "item": user,
        "store": {"ready": True, "backend": store.__class__.__name__},
    }


@router.patch("/users/{user_key}")
def update_auth_user(
    user_key: str,
    payload: AuthUserUpdateRequest,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> dict[str, object]:
    actor = require_permission(
        state,
        permission=Permission.MANAGE_PROJECT_MEMBERS,
        x_user_id=x_user_id,
        x_role=x_role,
        attempted_action="auth-user-update",
    )
    values = payload.model_dump(exclude_unset=True)
    if not values:
        raise HTTPException(status_code=422, detail="at least one user field is required")
    _reject_null_fields(values, fields=("display_name", "status", "metadata"))
    if "status" in values and actor.user_identifier == user_key and values["status"] != "active":
        raise HTTPException(status_code=409, detail="cannot disable the current actor")

    try:
        store = _auth_user_store(state)
        user = store.update_user(user_key, values)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="auth user not found") from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=409,
            detail="persistent auth user store is not available",
        ) from exc

    record_operation(
        state,
        "auth-user-update",
        {
            "user_key": user["user_key"],
            "updated_fields": sorted(values),
            "status": user.get("status"),
            "updated_by": actor.user_identifier,
            "role": actor.role.value,
        },
    )
    return {
        "item": user,
        "store": {"ready": True, "backend": store.__class__.__name__},
    }


@router.post("/users/{user_key}/role-assignments")
def assign_auth_user_role(
    user_key: str,
    payload: AuthUserRoleAssignmentCreateRequest,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> dict[str, object]:
    actor = require_permission(
        state,
        permission=Permission.MANAGE_PROJECT_MEMBERS,
        x_user_id=x_user_id,
        x_role=x_role,
        attempted_action="auth-user-role-assign",
    )
    values = payload.model_dump()
    values["assigned_by"] = actor.user_identifier
    try:
        store = _auth_user_store(state)
        assignment = store.assign_role(user_key, values)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="auth user not found") from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=409,
            detail="persistent auth user store is not available",
        ) from exc

    record_operation(
        state,
        "auth-user-role-assign",
        {
            "user_key": user_key,
            "assignment_key": assignment["assignment_key"],
            "assigned_role": assignment["role"],
            "assigned_by": actor.user_identifier,
            "role": actor.role.value,
        },
    )
    return {
        "item": assignment,
        "store": {"ready": True, "backend": store.__class__.__name__},
    }


@router.patch("/users/{user_key}/role-assignments/{assignment_key}")
def update_auth_user_role_assignment(
    user_key: str,
    assignment_key: str,
    payload: AuthUserRoleAssignmentUpdateRequest,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> dict[str, object]:
    actor = require_permission(
        state,
        permission=Permission.MANAGE_PROJECT_MEMBERS,
        x_user_id=x_user_id,
        x_role=x_role,
        attempted_action="auth-user-role-assignment-update",
    )
    values = payload.model_dump(exclude_unset=True)
    if not values:
        raise HTTPException(
            status_code=422,
            detail="at least one role assignment field is required",
        )
    _reject_null_fields(values, fields=("role", "scope_type", "status", "metadata"))

    try:
        store = _auth_user_store(state)
        assignment = store.update_role_assignment(user_key, assignment_key, values)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="auth role assignment not found") from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=409,
            detail="persistent auth user store is not available",
        ) from exc

    record_operation(
        state,
        "auth-user-role-assignment-update",
        {
            "user_key": user_key,
            "assignment_key": assignment["assignment_key"],
            "updated_fields": sorted(values),
            "status": assignment.get("status"),
            "updated_by": actor.user_identifier,
            "role": actor.role.value,
        },
    )
    return {
        "item": assignment,
        "store": {"ready": True, "backend": store.__class__.__name__},
    }


def _load_user_profile(
    state: ApiState,
    user_identifier: str,
) -> tuple[dict[str, object] | None, dict[str, object]]:
    default_profile = _default_user_profile(user_identifier)
    try:
        store = _auth_user_store(state)
        profile = store.get_user(user_identifier) or default_profile
        return profile, {"ready": True, "backend": store.__class__.__name__}
    except SQLAlchemyError:
        return default_profile, {"ready": False, "backend": "unavailable"}


def _reject_null_fields(values: dict[str, object], *, fields: tuple[str, ...]) -> None:
    null_fields = sorted(field for field in fields if field in values and values[field] is None)
    if null_fields:
        raise HTTPException(
            status_code=422,
            detail=f"{', '.join(null_fields)} cannot be null",
        )


def _default_user_profile(user_key: str) -> dict[str, object] | None:
    return next(
        (dict(user) for user in DEFAULT_AUTH_USERS if str(user["user_key"]) == user_key),
        None,
    )


def _role_items() -> list[dict[str, object]]:
    return [
        {
            "role": role.value,
            "label": ROLE_LABELS[role],
            "permissions": sorted(permission.value for permission in ROLE_PERMISSIONS[role]),
        }
        for role in HospitalRole
    ]


def _auth_user_store(state: ApiState) -> AuthUserStore:
    if state.auth_user_store is None:
        state.auth_user_store = InMemoryAuthUserStore()
    return state.auth_user_store
