from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _enable_explicit_local_header_transition_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep repository tests on the explicit local identity simulator."""

    monkeypatch.setenv("MEDICAL_AUDIT_KB_DEV_MODE", "1")
