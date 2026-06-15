from __future__ import annotations

from dataclasses import dataclass, field
from typing import Annotated

from fastapi import Header, Request

LEGACY_AUTH_SOURCE = "legacy-header"
DEFAULT_USER_KEY = "anonymous"
DEFAULT_ROLE_KEY = "auditor"

ROLE_ALIASES = {
    "it-admin": "system-admin",
}

CANONICAL_ROLE_KEYS = frozenset(
    {
        "auditor",
        "department-head",
        "info-staff",
        "business-expert",
        "system-admin",
    }
)

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "auditor": frozenset(
        {
            "agent:create",
            "document-upload:create-personal",
            "document-upload:read-own",
            "knowledge-query:query",
            "project-member:create",
        }
    ),
    "department-head": frozenset(
        {
            "agent:create",
            "agent:manage-all",
            "audit-log:export",
            "audit-log:read",
            "document-upload:create-personal",
            "document-upload:read-all",
            "document-upload:read-own",
            "knowledge-query:query",
            "project-member:create",
        }
    ),
    "info-staff": frozenset(
        {
            "document-upload:create-personal",
            "document-upload:read-own",
            "knowledge-query:query",
        }
    ),
    "business-expert": frozenset(
        {
            "agent:create",
            "document-upload:create-personal",
            "document-upload:read-own",
            "knowledge-query:query",
        }
    ),
    "system-admin": frozenset({"*"}),
}


@dataclass(frozen=True, slots=True)
class CurrentUser:
    user_key: str
    display_name: str
    department_key: str | None
    roles: tuple[str, ...]
    permissions: frozenset[str]
    auth_source: str
    session_id: str | None = None
    legacy_role: str | None = None

    @property
    def primary_role(self) -> str:
        return self.roles[0] if self.roles else DEFAULT_ROLE_KEY

    @property
    def audit_role(self) -> str:
        return self.legacy_role or self.primary_role


@dataclass(frozen=True, slots=True)
class PermissionContext:
    current_user: CurrentUser
    permission: str
    resource_scope: dict[str, object] = field(default_factory=dict)

    def to_audit_payload(self) -> dict[str, object]:
        return auth_audit_payload(
            self.current_user,
            permission=self.permission,
            **self.resource_scope,
        )


def get_current_user(
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> CurrentUser:
    return current_user_from_legacy_headers(user_identifier=x_user_id, role=x_role)


def current_user_from_request(request: Request) -> CurrentUser:
    return current_user_from_legacy_headers(
        user_identifier=request.headers.get("X-User-Id"),
        role=request.headers.get("X-Role"),
    )


def current_user_from_legacy_headers(
    *,
    user_identifier: str | None,
    role: str | None,
) -> CurrentUser:
    user_key = _normalize_user_identifier(user_identifier)
    legacy_role = _normalize_legacy_role(role)
    normalized_role = normalize_role_key(legacy_role, allow_unknown=True)
    permissions = ROLE_PERMISSIONS.get(normalized_role, frozenset())
    return CurrentUser(
        user_key=user_key,
        display_name=user_key,
        department_key=None,
        roles=(normalized_role,),
        permissions=permissions,
        auth_source=LEGACY_AUTH_SOURCE,
        session_id=None,
        legacy_role=legacy_role,
    )


def normalize_role_key(role: str | None, *, allow_unknown: bool = False) -> str:
    normalized = _normalize_legacy_role(role)
    canonical = ROLE_ALIASES.get(normalized, normalized)
    if canonical in CANONICAL_ROLE_KEYS or allow_unknown:
        return canonical
    from fastapi import HTTPException

    raise HTTPException(status_code=403, detail="role is not allowed")


def has_permission(user: CurrentUser, permission: str) -> bool:
    return "*" in user.permissions or permission in user.permissions


def auth_audit_payload(user: CurrentUser, **extra: object) -> dict[str, object]:
    return {
        **extra,
        "user_identifier": user.user_key,
        "role": user.audit_role,
        "normalized_role": user.primary_role,
        "auth_source": user.auth_source,
    }


def _normalize_user_identifier(value: str | None) -> str:
    normalized = (value or DEFAULT_USER_KEY).strip()
    return normalized or DEFAULT_USER_KEY


def _normalize_legacy_role(value: str | None) -> str:
    normalized = (value or DEFAULT_ROLE_KEY).strip()
    return normalized or DEFAULT_ROLE_KEY
