from types import SimpleNamespace
from typing import cast

import pytest
from fastapi import HTTPException

from medical_audit_kb.api.app import ApiState
from medical_audit_kb.api.audit_log_policy import can_read_audit_logs
from medical_audit_kb.api.role_policy import normalize_audit_role, require_audit_role_for_write


def test_legacy_it_admin_normalizes_to_system_admin() -> None:
    assert normalize_audit_role("it-admin") == "system-admin"


def test_system_admin_is_authorized_for_legacy_write_gate() -> None:
    state = _state()

    role = require_audit_role_for_write(
        state,
        role="system-admin",
        user_identifier="admin-1",
        attempted_action="agent-create",
        denied_action="agent-access-denied",
    )

    assert role == "system-admin"
    assert state.operation_logs == []


def test_denied_legacy_header_write_records_auth_context_fields() -> None:
    state = _state()

    with pytest.raises(HTTPException) as exc_info:
        require_audit_role_for_write(
            state,
            role="guest",
            user_identifier="guest-1",
            attempted_action="agent-create",
            denied_action="agent-access-denied",
        )

    assert exc_info.value.status_code == 403
    assert state.operation_logs[-1] == {
        "action": "agent-access-denied",
        "payload": {
            "attempted_action": "agent-create",
            "user_identifier": "guest-1",
            "role": "guest",
            "normalized_role": "guest",
            "auth_source": "legacy-header",
            "status_code": 403,
            "reason": "role is not allowed",
        },
    }


def test_audit_log_reader_accepts_system_admin_and_legacy_it_admin() -> None:
    assert can_read_audit_logs("system-admin") is True
    assert can_read_audit_logs("it-admin") is True
    assert can_read_audit_logs("auditor") is False


def _state() -> ApiState:
    return cast(
        ApiState,
        SimpleNamespace(operation_logs=[], audit_log_store=None),
    )
