from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import types
from pathlib import Path

import pytest

SCRIPT_PATH = Path("scripts/audit-agent-market-duplicate-cleanup.py")


def _load_module() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("agent_market_duplicate_cleanup", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _agent(
    suffix: str,
    *,
    status: str = "active",
    invocation_count: int = 0,
    updated_at: str = "2026-07-16T08:00:00+00:00",
    created_by: str = "director-1",
    project_name: str = "医保基金专项",
    template_id: str = "agent-medical-fund",
) -> dict[str, object]:
    return {
        "agent_id": f"00000000-0000-0000-0000-{int(suffix):012d}",
        "agent_key": f"agent-market-{suffix}",
        "created_by": created_by,
        "project_name": project_name,
        "status": status,
        "metadata": {"source": "agent-market", "template_id": template_id},
        "created_at": "2026-07-15T08:00:00+00:00",
        "updated_at": updated_at,
        "invocation_count": invocation_count,
    }


def _inventory(agents: list[dict[str, object]]) -> dict[str, object]:
    return {
        "format": "medical-audit-agent-market-inventory-v1",
        "source": "fixture",
        "transaction_read_only": "on",
        "agents": agents,
    }


def test_duplicate_manifest_prefers_active_then_most_invoked_and_preserves_history() -> None:
    module = _load_module()
    report = module._analyze_inventory(
        _inventory(
            [
                _agent("1", status="archived", invocation_count=500),
                _agent("2", invocation_count=20),
                _agent("3", invocation_count=40),
            ]
        )
    )

    assert report["status"] == "pass"
    assert report["decision"] == "dry-run-only"
    assert report["database_write"] is False
    assert report["sql_write_statements_emitted"] is False
    assert report["summary"] == {
        "market_row_count": 3,
        "active_market_row_count": 2,
        "identity_group_count": 1,
        "ambiguous_identity_group_count": 1,
        "active_duplicate_group_count": 1,
        "excess_row_count": 2,
    }
    group = report["duplicate_groups"][0]
    assert group["survivor"]["agent_key"] == "agent-market-3"
    assert [item["action"] for item in group["proposed_actions"]].count(
        "detach-market-identity-and-archive"
    ) == 2
    assert all(item["preserve_invocation_history"] for item in group["proposed_actions"])
    assert "director-1" not in json.dumps(report)
    assert "医保基金专项" not in json.dumps(report, ensure_ascii=False)


def test_archived_duplicate_is_included_in_all_status_identity_ambiguity() -> None:
    module = _load_module()
    report = module._analyze_inventory(
        _inventory([_agent("1"), _agent("2", status="archived")])
    )

    assert report["summary"]["ambiguous_identity_group_count"] == 1
    assert report["summary"]["active_duplicate_group_count"] == 0
    assert report["duplicate_groups"][0]["survivor"]["agent_key"] == "agent-market-1"


def test_all_dormant_duplicate_group_preserves_survivor_status() -> None:
    module = _load_module()
    report = module._analyze_inventory(
        _inventory(
            [
                _agent("1", status="archived", invocation_count=5),
                _agent("2", status="inactive", invocation_count=10),
            ]
        )
    )

    group = report["duplicate_groups"][0]
    assert group["survivor"]["agent_key"] == "agent-market-2"
    survivor_action = next(
        item
        for item in group["proposed_actions"]
        if item["agent_key"] == "agent-market-2"
    )
    assert survivor_action["action"] == "keep-market-identity"
    assert all(
        item["action"] != "reactivate-survivor-before-detach"
        for item in group["proposed_actions"]
    )


def test_unique_market_inventory_requires_no_cleanup_authorization() -> None:
    module = _load_module()
    report = module._analyze_inventory(
        _inventory(
            [
                _agent("1"),
                _agent("2", created_by="director-2"),
            ]
        )
    )

    assert report["cleanup_write_authorization_required"] is False
    assert report["duplicate_groups"] == []
    assert report["summary"]["identity_group_count"] == 2


def test_inventory_must_be_read_only_and_market_scoped() -> None:
    module = _load_module()
    payload = _inventory([_agent("1")])
    payload["transaction_read_only"] = "off"
    with pytest.raises(module.InventoryError, match="transaction_read_only must be on"):
        module._analyze_inventory(payload)

    outside_scope = _inventory([_agent("1")])
    outside_scope["agents"][0]["metadata"]["source"] = "manual"
    with pytest.raises(module.InventoryError, match="outside the agent-market inventory scope"):
        module._analyze_inventory(outside_scope)


def test_emitted_inventory_sql_is_strict_read_only() -> None:
    module = _load_module()
    sql = module._inventory_sql()
    upper = sql.upper()

    assert "BEGIN TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY DEFERRABLE" in upper
    assert "CURRENT_SETTING('TRANSACTION_READ_ONLY')" in upper
    assert "PUBLIC.AUDIT_AGENTS" in upper
    assert "PUBLIC.AUDIT_AGENT_INVOCATIONS" in upper
    assert "COMMIT" in upper
    for forbidden in ("UPDATE ", "DELETE ", "INSERT ", "ALTER ", "DROP ", "TRUNCATE "):
        assert forbidden not in upper


def test_cli_writes_deterministic_dry_run_report(tmp_path: Path) -> None:
    input_path = tmp_path / "inventory.json"
    output_path = tmp_path / "report.json"
    input_path.write_text(json.dumps(_inventory([_agent("1"), _agent("2")])), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "analyze",
            "--input-json",
            str(input_path),
            "--output",
            str(output_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["format"] == "medical-audit-agent-market-duplicate-cleanup-dry-run-v1"
    assert report["summary"]["excess_row_count"] == 1
