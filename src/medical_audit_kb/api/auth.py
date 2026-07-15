from __future__ import annotations

import urllib.parse
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError

if TYPE_CHECKING:
    from medical_audit_kb.api.app import ApiState


class HospitalRole(StrEnum):
    ADMIN = "admin"
    TECHNICIAN = "technician"
    DIRECTOR = "director"
    MEMBER = "member"


class Permission(StrEnum):
    QUERY_KNOWLEDGE = "query_knowledge"
    UPLOAD_PERSONAL_DOCUMENT = "upload_personal_document"
    READ_ALL_PERSONAL_UPLOADS = "read_all_personal_uploads"
    ANALYZE_DATA = "analyze_data"
    MANAGE_AGENTS = "manage_agents"
    MANAGE_PROJECT_MEMBERS = "manage_project_members"
    MANAGE_INDEX = "manage_index"
    READ_AUDIT_LOGS = "read_audit_logs"
    READ_ALL_ANALYTICS_UPLOADS = "read_all_analytics_uploads"
    SIGN_REPORTS = "sign_reports"
    CREATE_REPORT_DRAFT = "create_report_draft"
    CREATE_REVIEW_TASK = "create_review_task"
    CREATE_PROJECT = "create_project"


ROLE_LABELS: dict[HospitalRole, str] = {
    HospitalRole.ADMIN: "管理员",
    HospitalRole.TECHNICIAN: "技术人员",
    HospitalRole.DIRECTOR: "主任",
    HospitalRole.MEMBER: "普通成员",
}

LEGACY_API_ROLES: dict[HospitalRole, str] = {
    HospitalRole.ADMIN: "it-admin",
    HospitalRole.TECHNICIAN: "technician",
    HospitalRole.DIRECTOR: "department-head",
    HospitalRole.MEMBER: "auditor",
}

ROLE_ALIASES: dict[str, HospitalRole] = {
    "admin": HospitalRole.ADMIN,
    "hospital-admin": HospitalRole.ADMIN,
    "it-admin": HospitalRole.ADMIN,
    "system-admin": HospitalRole.ADMIN,
    "administrator": HospitalRole.ADMIN,
    "管理员": HospitalRole.ADMIN,
    "technician": HospitalRole.TECHNICIAN,
    "technical": HospitalRole.TECHNICIAN,
    "tech": HospitalRole.TECHNICIAN,
    "index-admin": HospitalRole.TECHNICIAN,
    "data-admin": HospitalRole.TECHNICIAN,
    "技术人员": HospitalRole.TECHNICIAN,
    "director": HospitalRole.DIRECTOR,
    "department-head": HospitalRole.DIRECTOR,
    "chief": HospitalRole.DIRECTOR,
    "主任": HospitalRole.DIRECTOR,
    "member": HospitalRole.MEMBER,
    "auditor": HospitalRole.MEMBER,
    "普通成员": HospitalRole.MEMBER,
}

ROLE_PERMISSIONS: dict[HospitalRole, frozenset[Permission]] = {
    HospitalRole.ADMIN: frozenset(
        {
            Permission.QUERY_KNOWLEDGE,
            Permission.UPLOAD_PERSONAL_DOCUMENT,
            Permission.READ_ALL_PERSONAL_UPLOADS,
            Permission.ANALYZE_DATA,
            Permission.MANAGE_AGENTS,
            Permission.MANAGE_PROJECT_MEMBERS,
            Permission.MANAGE_INDEX,
            Permission.READ_AUDIT_LOGS,
            Permission.READ_ALL_ANALYTICS_UPLOADS,
            Permission.CREATE_REPORT_DRAFT,
            Permission.CREATE_REVIEW_TASK,
            Permission.CREATE_PROJECT,
        }
    ),
    HospitalRole.TECHNICIAN: frozenset(
        {
            Permission.QUERY_KNOWLEDGE,
            Permission.UPLOAD_PERSONAL_DOCUMENT,
            Permission.ANALYZE_DATA,
            Permission.MANAGE_AGENTS,
            Permission.MANAGE_INDEX,
        }
    ),
    HospitalRole.DIRECTOR: frozenset(
        {
            Permission.QUERY_KNOWLEDGE,
            Permission.UPLOAD_PERSONAL_DOCUMENT,
            Permission.READ_ALL_PERSONAL_UPLOADS,
            Permission.ANALYZE_DATA,
            Permission.MANAGE_AGENTS,
            Permission.READ_AUDIT_LOGS,
            Permission.SIGN_REPORTS,
            Permission.CREATE_REPORT_DRAFT,
            Permission.CREATE_REVIEW_TASK,
        }
    ),
    HospitalRole.MEMBER: frozenset(
        {
            Permission.QUERY_KNOWLEDGE,
            Permission.UPLOAD_PERSONAL_DOCUMENT,
            Permission.ANALYZE_DATA,
            Permission.CREATE_REPORT_DRAFT,
            Permission.CREATE_REVIEW_TASK,
        }
    ),
}


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    user_identifier: str
    role: HospitalRole
    role_label: str
    legacy_api_role: str
    raw_role: str | None
    tenant_id: str | None = None
    auth_source: str = "header"
    profile_status: str | None = None
    auth_scope_type: str | None = None
    auth_scope_key: str | None = None


def normalize_hospital_role(
    role: str | None,
    *,
    default: HospitalRole | None = None,
) -> HospitalRole:
    normalized = (role or "").strip()
    if not normalized:
        if default is not None:
            return default
        raise HTTPException(status_code=401, detail="X-Role header is required")
    resolved = ROLE_ALIASES.get(normalized) or ROLE_ALIASES.get(normalized.lower())
    if resolved is None:
        raise HTTPException(status_code=403, detail="role is not allowed")
    return resolved


def current_user_from_headers(
    *,
    x_user_id: str | None,
    x_role: str | None,
    tenant_id: str | None = None,
    default_role: HospitalRole | None = None,
) -> AuthenticatedUser:
    role = normalize_hospital_role(x_role, default=default_role)
    user_identifier = (x_user_id or "anonymous").strip() or "anonymous"
    return AuthenticatedUser(
        user_identifier=user_identifier,
        role=role,
        role_label=ROLE_LABELS[role],
        legacy_api_role=LEGACY_API_ROLES[role],
        raw_role=x_role,
        tenant_id=normalize_tenant_id(tenant_id),
    )


def resolve_authenticated_user(
    state: ApiState,
    *,
    x_user_id: str | None,
    x_role: str | None,
    default_role: HospitalRole | None = None,
    project_key: str | None = None,
    tenant_id: str | None = None,
) -> AuthenticatedUser:
    user_identifier = (x_user_id or "anonymous").strip() or "anonymous"
    normalized_tenant_id = normalize_tenant_id(tenant_id)
    header_user: AuthenticatedUser | None = None
    header_error: HTTPException | None = None
    try:
        header_user = current_user_from_headers(
            x_user_id=x_user_id,
            x_role=x_role,
            tenant_id=normalized_tenant_id,
            default_role=default_role,
        )
    except HTTPException as exc:
        header_error = exc

    profile = _load_persistent_profile(state, user_identifier)
    if profile is not None:
        status = str(profile.get("status") or "active")
        if status != "active":
            raise HTTPException(
                status_code=403,
                detail=f"auth user status is {status}",
            )
        scoped_role = _active_persistent_role(profile, project_key=project_key)
        if scoped_role is not None:
            role, scope_type, scope_key = scoped_role
            return AuthenticatedUser(
                user_identifier=user_identifier,
                role=role,
                role_label=ROLE_LABELS[role],
                legacy_api_role=LEGACY_API_ROLES[role],
                raw_role=x_role,
                tenant_id=normalized_tenant_id,
                auth_source="persistent_project_role"
                if scope_type == "project"
                else "persistent_role",
                profile_status=status,
                auth_scope_type=scope_type,
                auth_scope_key=scope_key,
            )
        if header_user is not None:
            scope_source = (
                "persistent_profile_without_project_role"
                if _normalize_scope_key(project_key)
                else "persistent_profile_without_global_role"
            )
            return AuthenticatedUser(
                user_identifier=user_identifier,
                role=HospitalRole.MEMBER,
                role_label=ROLE_LABELS[HospitalRole.MEMBER],
                legacy_api_role=LEGACY_API_ROLES[HospitalRole.MEMBER],
                raw_role=x_role,
                tenant_id=normalized_tenant_id,
                auth_source=scope_source,
                profile_status=status,
                auth_scope_type="project" if _normalize_scope_key(project_key) else "global",
                auth_scope_key=_normalize_scope_key(project_key),
            )

    if header_user is not None:
        return header_user
    if header_error is not None:
        raise header_error
    raise HTTPException(status_code=401, detail="X-Role header is required")


def has_permission(role: HospitalRole, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS[role]


def permissions_for_user(user: AuthenticatedUser) -> frozenset[Permission]:
    permissions = ROLE_PERMISSIONS[user.role]
    if not user.auth_source.startswith("persistent_profile_without_"):
        return permissions
    try:
        raw_role = normalize_hospital_role(user.raw_role)
    except HTTPException:
        return frozenset()
    return permissions & ROLE_PERMISSIONS[raw_role]


def user_has_permission(user: AuthenticatedUser, permission: Permission) -> bool:
    return permission in permissions_for_user(user)


def require_permission(
    state: ApiState,
    *,
    permission: Permission,
    x_user_id: str | None,
    x_role: str | None,
    attempted_action: str,
    project_key: str | None = None,
) -> AuthenticatedUser:
    try:
        user = resolve_authenticated_user(
            state,
            x_user_id=x_user_id,
            x_role=x_role,
            project_key=project_key,
        )
    except HTTPException as exc:
        record_authorization_denied(
            state,
            attempted_action=attempted_action,
            permission=permission,
            user_identifier=x_user_id or "anonymous",
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


def record_authorization_denied(
    state: ApiState,
    *,
    attempted_action: str,
    permission: Permission | str,
    user_identifier: str,
    raw_role: str | None,
    status_code: int,
    reason: str,
    effective_role: str | None = None,
    auth_source: str | None = None,
    profile_status: str | None = None,
    auth_scope_type: str | None = None,
    auth_scope_key: str | None = None,
) -> None:
    from medical_audit_kb.api.app import record_operation

    payload: dict[str, object] = {
        "attempted_action": attempted_action,
        "permission": permission.value if isinstance(permission, Permission) else permission,
        "user_identifier": user_identifier,
        "role": raw_role or "anonymous",
        "effective_role": effective_role,
        "auth_source": auth_source,
        "profile_status": profile_status,
        "auth_scope_type": auth_scope_type,
        "auth_scope_key": auth_scope_key,
        "status_code": status_code,
        "reason": reason,
    }
    try:
        record_operation(state, "authorization-denied", payload)
    except SQLAlchemyError as exc:
        state.operation_logs.append(
            {
                "action": "authorization-denied-audit-degraded",
                "payload": {
                    **payload,
                    "error_type": type(exc).__name__,
                },
            }
        )


def _load_persistent_profile(
    state: ApiState,
    user_identifier: str,
) -> dict[str, object] | None:
    if user_identifier == "anonymous" or state.auth_user_store is None:
        return None
    try:
        return state.auth_user_store.get_user(user_identifier)
    except SQLAlchemyError:
        return None


def _active_persistent_role(
    profile: dict[str, object],
    *,
    project_key: str | None,
) -> tuple[HospitalRole, str, str | None] | None:
    project_role = _active_scoped_role(profile, scope_type="project", scope_key=project_key)
    if project_role is not None:
        return project_role
    return _active_scoped_role(profile, scope_type="global", scope_key=None)


def _active_scoped_role(
    profile: dict[str, object],
    *,
    scope_type: str,
    scope_key: str | None,
) -> tuple[HospitalRole, str, str | None] | None:
    normalized_scope_key = _normalize_scope_key(scope_key)
    if scope_type != "global" and not normalized_scope_key:
        return None
    assignments = profile.get("role_assignments")
    if not isinstance(assignments, list):
        return None
    for assignment in assignments:
        if not isinstance(assignment, dict):
            continue
        if str(assignment.get("status") or "active") != "active":
            continue
        assignment_scope_type = str(assignment.get("scope_type") or "global")
        if assignment_scope_type != scope_type:
            continue
        assignment_scope_key = _normalize_scope_key(
            str(assignment.get("scope_key") or "") or None
        )
        if scope_type != "global" and assignment_scope_key != normalized_scope_key:
            continue
        try:
            return (
                normalize_hospital_role(str(assignment.get("role") or "")),
                assignment_scope_type,
                assignment_scope_key,
            )
        except HTTPException:
            continue
    return None


def _normalize_scope_key(scope_key: str | None) -> str | None:
    if scope_key is None:
        return None
    normalized = urllib.parse.unquote(str(scope_key).strip())
    return normalized or None


def normalize_tenant_id(tenant_id: str | None) -> str | None:
    if tenant_id is None:
        return None
    normalized = urllib.parse.unquote(str(tenant_id).strip())
    return normalized or None
