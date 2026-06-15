from __future__ import annotations

from fastapi import HTTPException

from medical_audit_kb.api.app import ApiState, record_operation
from medical_audit_kb.api.auth_context import (
    CANONICAL_ROLE_KEYS,
    CurrentUser,
    auth_audit_payload,
    current_user_from_legacy_headers,
    normalize_role_key,
)

AUDIT_ROLES = CANONICAL_ROLE_KEYS
AUDIT_WRITE_ROLES = frozenset({"auditor", "department-head", "business-expert", "system-admin"})


def normalize_audit_role(role: str | None) -> str:
    return normalize_role_key(role)


def require_audit_role_for_write(
    state: ApiState,
    *,
    role: str | None,
    user_identifier: str | None,
    attempted_action: str,
    denied_action: str,
) -> str:
    current_user = current_user_from_legacy_headers(
        user_identifier=user_identifier,
        role=role,
    )
    return require_audit_user_for_write(
        state,
        current_user=current_user,
        attempted_action=attempted_action,
        denied_action=denied_action,
    ).primary_role


def require_audit_user_for_write(
    state: ApiState,
    *,
    current_user: CurrentUser,
    attempted_action: str,
    denied_action: str,
) -> CurrentUser:
    if current_user.primary_role in AUDIT_WRITE_ROLES:
        return current_user
    record_operation(
        state,
        denied_action,
        auth_audit_payload(
            current_user,
            attempted_action=attempted_action,
            status_code=403,
            reason="role is not allowed",
        ),
    )
    raise HTTPException(status_code=403, detail="role is not allowed")
