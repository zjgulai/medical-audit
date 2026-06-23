from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from typing import cast

from fastapi import HTTPException

from medical_audit_kb.api.auth import Permission, has_permission, normalize_hospital_role
from medical_audit_kb.api.auth_context import normalize_role_key

AUDIT_LOG_READER_ROLES = frozenset({"admin", "director", "it-admin", "department-head"})
LEGACY_AUDIT_LOG_READER_ROLES = frozenset({"department-head", "system-admin"})
AUDIT_LOG_RETENTION_DAYS = 180
REDACTED_VALUE = "[REDACTED]"
SENSITIVE_AUDIT_LOG_KEYS = frozenset(
    {
        "api_key",
        "authorization",
        "credential",
        "password",
        "secret",
        "token",
    }
)


def can_read_audit_logs(role: str | None) -> bool:
    if normalize_role_key(role, allow_unknown=True) in LEGACY_AUDIT_LOG_READER_ROLES:
        return True
    try:
        return has_permission(normalize_hospital_role(role), Permission.READ_AUDIT_LOGS)
    except HTTPException:
        return False


def audit_log_policy_payload() -> dict[str, object]:
    return {
        "reader_roles": sorted(AUDIT_LOG_READER_ROLES),
        "retention_days": AUDIT_LOG_RETENTION_DAYS,
        "redaction": {
            "mode": "response-only",
            "sensitive_keys": sorted(SENSITIVE_AUDIT_LOG_KEYS),
            "redacted_value": REDACTED_VALUE,
        },
    }


def redact_audit_log_event(event: dict[str, object]) -> dict[str, object]:
    redacted = copy.deepcopy(event)
    payload = redacted.get("payload")
    metadata = redacted.get("metadata")
    if isinstance(payload, dict):
        redacted["payload"] = _redact_mapping(payload)
    if isinstance(metadata, dict):
        redacted["metadata"] = _redact_mapping(metadata)
    return redacted


def redact_audit_log_events(events: Sequence[dict[str, object]]) -> list[dict[str, object]]:
    return [redact_audit_log_event(event) for event in events]


def _redact_mapping(values: Mapping[str, object]) -> dict[str, object]:
    return {
        key: REDACTED_VALUE if _is_sensitive_key(key) else _redact_value(value)
        for key, value in values.items()
    }


def _redact_value(value: object) -> object:
    if isinstance(value, Mapping):
        return _redact_mapping(cast(Mapping[str, object], value))
    if isinstance(value, list | tuple):
        return [_redact_value(item) for item in value]
    return value


def _is_sensitive_key(key: str) -> bool:
    normalized_key = key.lower().replace("-", "_")
    return normalized_key in SENSITIVE_AUDIT_LOG_KEYS or any(
        token in normalized_key for token in SENSITIVE_AUDIT_LOG_KEYS
    )
