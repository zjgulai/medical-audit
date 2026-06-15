from __future__ import annotations

from fastapi import HTTPException

from medical_audit_kb.api.app import ApiState, record_operation

AUDIT_ROLES = frozenset({"auditor", "it-admin", "department-head"})


def normalize_audit_role(role: str | None) -> str:
    normalized = (role or "auditor").strip() or "auditor"
    if normalized not in AUDIT_ROLES:
        raise HTTPException(status_code=403, detail="role is not allowed")
    return normalized


def require_audit_role_for_write(
    state: ApiState,
    *,
    role: str | None,
    user_identifier: str | None,
    attempted_action: str,
    denied_action: str,
) -> str:
    normalized = (role or "auditor").strip() or "auditor"
    if normalized in AUDIT_ROLES:
        return normalized
    record_operation(
        state,
        denied_action,
        {
            "attempted_action": attempted_action,
            "user_identifier": user_identifier or "anonymous",
            "role": normalized,
            "status_code": 403,
            "reason": "role is not allowed",
        },
    )
    raise HTTPException(status_code=403, detail="role is not allowed")
