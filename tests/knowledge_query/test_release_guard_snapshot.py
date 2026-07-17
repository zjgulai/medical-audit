from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import types
from pathlib import Path

import pytest

SCRIPT_PATH = Path("scripts/audit-production-release-guard-snapshot.py")
SHA_A = "a" * 40
SHA_B = "b" * 40
FINGERPRINT_A = "1" * 64
FINGERPRINT_B = "2" * 64

ALLOWLISTED_TABLES = (
    "query_logs",
    "review_tasks",
    "review_actions",
    "review_comments",
    "audit_projects",
    "audit_project_members",
    "analytics_upload_records",
    "document_upload_records",
    "document_storage_objects",
    "document_upload_governance_jobs",
    "audit_agent_invocations",
    "audit_log_events",
)


def _load_module() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("release_guard_snapshot", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _table_snapshot(index: int, name: str) -> dict[str, object]:
    snapshot: dict[str, object] = {
        "row_count": index,
        "primary_key_fingerprint": f"{index + 10:064x}",
        "row_content_fingerprint": f"{index + 30:064x}",
        "max_timestamp": "none" if index == 0 else "2026-07-16T07:00:00+00:00",
    }
    if name == "audit_log_events":
        row_ids = [f"00000000-0000-0000-0000-{item:012d}" for item in range(index)]
        snapshot["primary_key_fingerprint"] = hashlib.sha256(
            ",".join(row_ids).encode("utf-8")
        ).hexdigest()
        snapshot["row_hashes"] = {
            row_id: hashlib.sha256(f"row:{row_id}".encode()).hexdigest()
            for row_id in row_ids
        }
    return snapshot


def _base_fixture(*, deploy_sha: str = SHA_A) -> dict[str, object]:
    return {
        "format": "medical-audit-production-release-guard-fixture-v1",
        "transaction_read_only": "on",
        "transaction_isolation": "serializable",
        "transaction_deferrable": "on",
        "consistency": {
            "database_snapshot_before": "fixture-snapshot-1",
            "database_snapshot_after": "fixture-snapshot-1",
            "concurrent_activity_detected": False,
        },
        "release_topology": {
            "current": {"kind": "absent"},
            "current_next": {"kind": "absent"},
            "releases_root": {"kind": "absent"},
            "migration_sentinel": {"kind": "absent"},
            "migration_sentinel_next": {"kind": "absent"},
            "incoming_entries": [],
            "legacy_index": {
                "kind": "regular_file",
                "sha256": FINGERPRINT_A,
            },
            "deploy_marker": {"kind": "regular_file", "sha": deploy_sha},
            "deploy_marker_next": {"kind": "absent"},
            "release": {"kind": "absent"},
            "runtime": {
                "app_container": {
                    "status": "running",
                    "health": "healthy",
                    "deploy_sha": deploy_sha,
                },
                "nginx": {
                    "config_test": True,
                    "web_mount_source": "/var/www/audit",
                    "web_mount_read_only": True,
                    "expected_web_root": "/var/www/audit",
                },
            },
        },
        "schema": {
            "algorithm": "sha256",
            "fingerprint": FINGERPRINT_A,
            "tables": list(ALLOWLISTED_TABLES),
            "scope": [
                "columns",
                "constraints",
                "indexes",
                "table-acl",
                "row-level-security-flags",
                "row-level-security-policies",
                "triggers",
                "trigger-functions",
            ],
        },
        "tables": {
            name: _table_snapshot(index, name) for index, name in enumerate(ALLOWLISTED_TABLES)
        },
        "object_storage": {
            "status": "observed",
            "fingerprint": FINGERPRINT_A,
            "object_count": 8,
            "max_timestamp": "2026-07-16T07:00:00+00:00",
            "observation_scope": "database-ledger",
        },
        "release_identity": {
            "expected_deploy_sha": deploy_sha,
            "observed_deploy_sha": deploy_sha,
        },
        "provider": {
            "status": "not_called",
            "evidence_source": "collector-execution-boundary",
            "attempt_count": 0,
            "guard_execution_boundary": {
                "format": "medical-audit-release-guard-execution-boundary-v1",
                "collector_protocol": "fixture-controlled-json-v2",
                "allowed_operations": [
                    "filesystem-read",
                    "docker-exec-psql-readonly",
                    "docker-inspect-readonly",
                    "docker-exec-app-deploy-sha-readonly",
                    "docker-exec-nginx-config-test",
                ],
                "executed_postgresql_readonly_commands": 0,
                "executed_runtime_readonly_commands": 0,
                "rejected_command_count": 0,
                "collector_provider_endpoint_attempt_count": 0,
                "provider_environment_read": False,
                "secret_values_reported": False,
            },
        },
    }


def _versioned_fixture(*, deploy_sha: str = SHA_A) -> dict[str, object]:
    fixture = _base_fixture(deploy_sha=deploy_sha)
    fixture["release_topology"] = {
        "current": {"kind": "symlink", "target": f"releases/{deploy_sha}"},
        "current_next": {"kind": "absent"},
        "releases_root": {"kind": "directory"},
        "migration_sentinel": {"kind": "regular_file", "sha": deploy_sha},
        "migration_sentinel_next": {"kind": "absent"},
        "incoming_entries": [],
        "legacy_index": {"kind": "regular_file", "sha256": FINGERPRINT_A},
        "deploy_marker": {"kind": "regular_file", "sha": deploy_sha},
        "deploy_marker_next": {"kind": "absent"},
        "release": {
            "kind": "directory",
            "sha": deploy_sha,
            "manifest_format": "medical-audit-web-release-manifest-v1",
            "manifest_source_sha": deploy_sha,
            "manifest_sha256": FINGERPRINT_B,
        },
        "runtime": {
            "app_container": {
                "status": "running",
                "health": "healthy",
                "deploy_sha": deploy_sha,
            },
            "nginx": {
                "config_test": True,
                "web_mount_source": "/var/www/audit",
                "web_mount_read_only": True,
                "expected_web_root": "/var/www/audit",
            },
        },
    }
    return fixture


def _live_fixture(*, deploy_sha: str = SHA_A) -> dict[str, object]:
    fixture = _base_fixture(deploy_sha=deploy_sha)
    fixture["observation_target"] = {
        "format": "medical-audit-release-guard-observation-target-v1",
        "kind": "production-ssh",
        "ssh_host": "101.34.52.232",
        "remote_app_dir": "/opt/medical-audit/app",
        "remote_web_dir": "/var/www/audit",
        "postgres_container": "medical_audit_pg",
    }
    provider = fixture["provider"]
    assert isinstance(provider, dict)
    boundary = provider["guard_execution_boundary"]
    assert isinstance(boundary, dict)
    boundary["collector_protocol"] = "ssh-stdin-release-topology-postgresql-readonly-v2"
    boundary["executed_postgresql_readonly_commands"] = 2
    boundary["executed_runtime_readonly_commands"] = 8
    return fixture


def _audit_attribution(run_id: str, event_ids: list[str]) -> dict[str, object]:
    ordered = sorted(event_ids)
    return {
        "acceptance_run_id": run_id,
        "audit_user_identifier": f"frontend-acceptance-{run_id}",
        "attributable_event_count": len(ordered),
        "event_id_fingerprint": hashlib.sha256(",".join(ordered).encode()).hexdigest(),
        "event_ids": ordered,
    }


def _append_audit_rows(fixture: dict[str, object], event_ids: list[str]) -> None:
    tables = fixture["tables"]
    assert isinstance(tables, dict)
    audit = tables["audit_log_events"]
    assert isinstance(audit, dict)
    row_hashes = audit["row_hashes"]
    assert isinstance(row_hashes, dict)
    for event_id in event_ids:
        row_hashes[event_id] = hashlib.sha256(f"row:{event_id}".encode()).hexdigest()
    ordered = sorted(row_hashes)
    audit["row_count"] = len(ordered)
    audit["primary_key_fingerprint"] = hashlib.sha256(",".join(ordered).encode()).hexdigest()
    audit["row_content_fingerprint"] = hashlib.sha256(
        ",".join(str(row_hashes[item]) for item in ordered).encode()
    ).hexdigest()
    audit["max_timestamp"] = "2026-07-16T08:30:00+00:00"


def _capture(
    module: types.ModuleType,
    fixture: dict[str, object],
    *,
    phase: str,
    expected_deploy_sha: str,
) -> dict[str, object]:
    return module._capture_snapshot(
        fixture,
        phase=phase,
        expected_deploy_sha=expected_deploy_sha,
        source="fixture",
    )


def test_capture_legacy_ready_emits_frontend_compatible_contract() -> None:
    module = _load_module()

    report = _capture(module, _base_fixture(), phase="S0", expected_deploy_sha=SHA_A)

    assert report["format"] == "medical-audit-production-release-guard-v1"
    assert report["mode"] == "capture"
    assert report["phase"] == "S0"
    assert report["status"] == "pass"
    assert report["expected_deploy_sha"] == SHA_A
    assert report["observed_deploy_sha"] == SHA_A
    assert report["provider_call_status"] == "not_observed"
    assert report["provider_evidence_source"] == "outside-release-guard-scope"
    assert report["collector_provider_call_status"] == "not_called"
    assert (
        report["collector_execution_boundary"]["collector_provider_endpoint_attempt_count"]
        == 0
    )
    assert report["database_write"] is False
    assert report["transaction_read_only"] is True
    assert report["transaction_read_only_observed"] == "on"
    assert isinstance(report["snapshot_id"], str)
    assert report["release_topology"] == "legacy_ready"
    assert set(report["tables"]) == set(ALLOWLISTED_TABLES)
    assert report["guard_execution_write"] is False
    assert report["capture_side_effect"] == "none"
    assert "production_unchanged" not in report


def test_capture_versioned_ready_requires_runtime_identities_and_valid_lineage_marker() -> None:
    module = _load_module()

    report = _capture(module, _versioned_fixture(), phase="S1", expected_deploy_sha=SHA_A)

    assert report["status"] == "pass"
    assert report["release_topology"] == "versioned_ready"

    lineage = _versioned_fixture(deploy_sha=SHA_B)
    topology = lineage["release_topology"]
    assert isinstance(topology, dict)
    sentinel = topology["migration_sentinel"]
    assert isinstance(sentinel, dict)
    sentinel["sha"] = SHA_A
    lineage_report = _capture(module, lineage, phase="S1", expected_deploy_sha=SHA_B)
    assert lineage_report["status"] == "pass"
    assert lineage_report["release_topology"] == "versioned_ready"

    sentinel["sha"] = "invalid"
    blocked = _capture(module, lineage, phase="S1", expected_deploy_sha=SHA_B)
    assert blocked["status"] == "blocked"
    assert blocked["release_topology"] == "partial_or_unknown"
    assert "release-topology-partial-or-unknown" in blocked["blocking_reasons"]


def test_capture_blocks_partial_migration_and_residue() -> None:
    module = _load_module()
    fixture = _base_fixture()
    topology = fixture["release_topology"]
    assert isinstance(topology, dict)
    topology["migration_sentinel"] = {"kind": "regular_file", "sha": SHA_A}
    topology["incoming_entries"] = [f"releases/{SHA_A}.incoming"]

    report = _capture(module, fixture, phase="S0", expected_deploy_sha=SHA_A)

    assert report["status"] == "blocked"
    assert report["release_topology"] == "partial_or_unknown"


def test_capture_accepts_first_migration_rollback_restored_legacy_shape(
    tmp_path: Path,
) -> None:
    module = _load_module()
    restored = _base_fixture(deploy_sha=SHA_A)
    app_dir = tmp_path / "app"
    web_dir = tmp_path / "web"
    app_dir.mkdir()
    web_dir.mkdir()
    (app_dir / ".deploy-sha").write_text(f"{SHA_A}\n", encoding="ascii")
    (web_dir / "index.html").write_text("legacy", encoding="utf-8")
    topology = module._collect_release_topology(app_dir, web_dir)
    base_topology = restored["release_topology"]
    assert isinstance(base_topology, dict)
    topology["runtime"] = base_topology["runtime"]
    restored["release_topology"] = topology

    report = _capture(module, restored, phase="S1", expected_deploy_sha=SHA_A)

    assert report["status"] == "pass"
    assert report["release_topology"] == "legacy_ready"
    topology = report["release_topology_evidence"]
    assert isinstance(topology, dict)
    assert topology["current"] == {"kind": "absent"}
    assert topology["migration_sentinel"] == {"kind": "absent"}
    assert topology["deploy_marker_next"] == {"kind": "absent"}

    (app_dir / ".deploy-sha.next").write_text(f"{SHA_A}\n", encoding="ascii")
    residue = module._collect_release_topology(app_dir, web_dir)
    residue["runtime"] = base_topology["runtime"]
    restored["release_topology"] = residue
    blocked = _capture(module, restored, phase="S1", expected_deploy_sha=SHA_A)
    assert blocked["status"] == "blocked"
    assert blocked["release_topology"] == "partial_or_unknown"


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        ("read-write", "transaction-read-only-not-on"),
        ("identity-drift", "expected-observed-deploy-sha-mismatch"),
        ("provider-call", "collector-provider-call-status-not-safe"),
        ("provider-boundary", "provider-execution-boundary-invalid"),
        ("concurrent", "capture-concurrent-ambiguity"),
    ],
)
def test_capture_fail_closed_boundaries(mutation: str, reason: str) -> None:
    module = _load_module()
    fixture = _base_fixture()
    if mutation == "read-write":
        fixture["transaction_read_only"] = "off"
    elif mutation == "identity-drift":
        identity = fixture["release_identity"]
        assert isinstance(identity, dict)
        identity["observed_deploy_sha"] = SHA_B
    elif mutation == "provider-call":
        provider = fixture["provider"]
        assert isinstance(provider, dict)
        provider["status"] = "called"
        provider["attempt_count"] = 1
    elif mutation == "provider-boundary":
        provider = fixture["provider"]
        assert isinstance(provider, dict)
        boundary = provider["guard_execution_boundary"]
        assert isinstance(boundary, dict)
        boundary["collector_provider_endpoint_attempt_count"] = 1
    else:
        consistency = fixture["consistency"]
        assert isinstance(consistency, dict)
        consistency["concurrent_activity_detected"] = True

    report = _capture(module, fixture, phase="S0", expected_deploy_sha=SHA_A)

    assert report["status"] == "blocked"
    assert reason in report["blocking_reasons"]


def test_capture_requires_exact_table_allowlist_and_valid_values() -> None:
    module = _load_module()
    missing = _base_fixture()
    tables = missing["tables"]
    assert isinstance(tables, dict)
    tables.pop("review_comments")
    report = _capture(module, missing, phase="S0", expected_deploy_sha=SHA_A)
    assert report["status"] == "blocked"
    assert "business-table-allowlist-mismatch" in report["blocking_reasons"]

    invalid = _base_fixture()
    invalid_tables = invalid["tables"]
    assert isinstance(invalid_tables, dict)
    row = invalid_tables["review_tasks"]
    assert isinstance(row, dict)
    row["max_timestamp"] = "not-a-timestamp"
    invalid_report = _capture(module, invalid, phase="S0", expected_deploy_sha=SHA_A)
    assert invalid_report["status"] == "blocked"
    assert "business-table-snapshot-invalid:review_tasks" in invalid_report["blocking_reasons"]


def test_capture_requires_database_ledger_object_scope() -> None:
    module = _load_module()
    fixture = _base_fixture()
    object_storage = fixture["object_storage"]
    assert isinstance(object_storage, dict)
    object_storage["observation_scope"] = "cos-remote-enumeration"

    report = _capture(module, fixture, phase="S0", expected_deploy_sha=SHA_A)

    assert report["status"] == "blocked"
    assert "object-storage-observation-invalid" in report["blocking_reasons"]


def test_live_capture_requires_configured_production_observation_target() -> None:
    module = _load_module()
    fixture = _live_fixture()
    target = fixture["observation_target"]
    assert isinstance(target, dict)
    target["ssh_host"] = "203.0.113.10"

    report = module._capture_snapshot(
        fixture,
        phase="S0",
        expected_deploy_sha=SHA_A,
        source="ssh-live-readonly",
    )

    assert report["status"] == "blocked"
    assert "production-observation-target-invalid" in report["blocking_reasons"]

    unknown_source = module._capture_snapshot(
        _base_fixture(),
        phase="S0",
        expected_deploy_sha=SHA_A,
        source="manual-report",
    )
    assert unknown_source["status"] == "blocked"
    assert unknown_source["evidence_grade"] == "L2-fixture-or-dry-run"
    assert "capture-source-invalid" in unknown_source["blocking_reasons"]

    shadow_scope = _live_fixture()
    shadow_target = shadow_scope["observation_target"]
    assert isinstance(shadow_target, dict)
    shadow_target["postgres_container"] = "shadow_pg"
    shadow_report = module._capture_snapshot(
        shadow_scope,
        phase="S0",
        expected_deploy_sha=SHA_A,
        source="ssh-live-readonly",
    )
    assert shadow_report["status"] == "blocked"
    assert "production-observation-target-invalid" in shadow_report["blocking_reasons"]


@pytest.mark.parametrize("releases_root_kind", ["symlink", "regular_file", "other"])
def test_legacy_topology_rejects_invalid_releases_root(releases_root_kind: str) -> None:
    module = _load_module()
    fixture = _base_fixture()
    topology = fixture["release_topology"]
    assert isinstance(topology, dict)
    topology["releases_root"] = {"kind": releases_root_kind}

    report = _capture(module, fixture, phase="S0", expected_deploy_sha=SHA_A)

    assert report["status"] == "blocked"
    assert "release-topology-partial-or-unknown" in report["blocking_reasons"]


def test_compare_s0_to_s1_allows_only_release_identity_change() -> None:
    module = _load_module()
    before = _capture(module, _base_fixture(), phase="S0", expected_deploy_sha=SHA_A)
    after = _capture(
        module,
        _versioned_fixture(deploy_sha=SHA_B),
        phase="S1",
        expected_deploy_sha=SHA_B,
    )

    report = module._compare_snapshots(before, after, expected_deploy_sha=SHA_B)

    assert report["status"] == "pass"
    assert report["comparison"] == "S0->S1"
    assert report["database_write"] is False
    assert report["expected_deploy_sha"] == SHA_B


def test_compare_s0_to_s1_requires_operator_expected_deploy_sha() -> None:
    module = _load_module()
    before = _capture(module, _base_fixture(), phase="S0", expected_deploy_sha=SHA_A)
    after = _capture(
        module,
        _versioned_fixture(deploy_sha=SHA_B),
        phase="S1",
        expected_deploy_sha=SHA_B,
    )

    report = module._compare_snapshots(before, after, expected_deploy_sha=SHA_A)

    assert report["status"] == "blocked"
    assert "comparison-expected-deploy-sha-mismatch" in report["blocking_reasons"]


def test_compare_s0_to_s1_rejects_versioned_to_legacy_transition() -> None:
    module = _load_module()
    before = _capture(
        module,
        _versioned_fixture(deploy_sha=SHA_A),
        phase="S0",
        expected_deploy_sha=SHA_A,
    )
    after = _capture(
        module,
        _base_fixture(deploy_sha=SHA_B),
        phase="S1",
        expected_deploy_sha=SHA_B,
    )

    report = module._compare_snapshots(before, after, expected_deploy_sha=SHA_B)

    assert report["status"] == "blocked"
    assert report["comparison_profile"] == "deploy"
    assert "release-topology-transition-invalid" in report["blocking_reasons"]


def test_compare_s0_to_s1_preserves_versioned_migration_lineage() -> None:
    module = _load_module()
    before = _capture(
        module,
        _versioned_fixture(deploy_sha=SHA_A),
        phase="S0",
        expected_deploy_sha=SHA_A,
    )
    rotated_fixture = _versioned_fixture(deploy_sha=SHA_B)
    rotated = _capture(
        module,
        rotated_fixture,
        phase="S1",
        expected_deploy_sha=SHA_B,
    )
    rotated_report = module._compare_snapshots(
        before,
        rotated,
        expected_deploy_sha=SHA_B,
    )
    assert rotated_report["status"] == "blocked"
    assert "migration-sentinel-lineage-delta" in rotated_report["blocking_reasons"]

    stable_fixture = _versioned_fixture(deploy_sha=SHA_B)
    stable_topology = stable_fixture["release_topology"]
    assert isinstance(stable_topology, dict)
    stable_topology["migration_sentinel"] = {"kind": "regular_file", "sha": SHA_A}
    stable = _capture(
        module,
        stable_fixture,
        phase="S1",
        expected_deploy_sha=SHA_B,
    )
    stable_report = module._compare_snapshots(
        before,
        stable,
        expected_deploy_sha=SHA_B,
    )
    assert stable_report["status"] == "pass"


def test_compare_s0_to_s1_detects_balanced_delete_insert_by_pk_fingerprint() -> None:
    module = _load_module()
    before = _capture(module, _base_fixture(), phase="S0", expected_deploy_sha=SHA_A)
    fixture = _base_fixture()
    tables = fixture["tables"]
    assert isinstance(tables, dict)
    row = tables["review_actions"]
    assert isinstance(row, dict)
    row["primary_key_fingerprint"] = FINGERPRINT_B
    after = _capture(module, fixture, phase="S1", expected_deploy_sha=SHA_A)

    report = module._compare_snapshots(before, after, expected_deploy_sha=SHA_A)

    assert report["status"] == "blocked"
    assert "business-table-delta:review_actions" in report["blocking_reasons"]


def test_compare_s0_to_s1_detects_in_place_row_content_change() -> None:
    module = _load_module()
    before = _capture(module, _base_fixture(), phase="S0", expected_deploy_sha=SHA_A)
    changed = _base_fixture()
    tables = changed["tables"]
    assert isinstance(tables, dict)
    row = tables["query_logs"]
    assert isinstance(row, dict)
    row["row_content_fingerprint"] = FINGERPRINT_B
    after = _capture(module, changed, phase="S1", expected_deploy_sha=SHA_A)

    report = module._compare_snapshots(before, after, expected_deploy_sha=SHA_A)

    assert report["status"] == "blocked"
    assert "business-table-delta:query_logs" in report["blocking_reasons"]


def test_compare_revalidates_capture_contract_and_snapshot_id() -> None:
    module = _load_module()
    before = _capture(module, _base_fixture(), phase="S0", expected_deploy_sha=SHA_A)
    after = _capture(module, _base_fixture(), phase="S1", expected_deploy_sha=SHA_A)
    tampered = copy.deepcopy(after)
    tampered["schema_fingerprint"] = None
    tampered["snapshot_id"] = "0" * 64

    report = module._compare_snapshots(before, tampered, expected_deploy_sha=SHA_A)

    assert report["status"] == "blocked"
    assert "after-snapshot-contract-invalid" in report["blocking_reasons"]

    timestamp_tampered = copy.deepcopy(after)
    timestamp_tampered["generated_at"] = "2026-07-16T09:30:00Z"
    assert module._capture_report_is_valid(timestamp_tampered) is False


def test_compare_s1_to_s2_blocks_topology_lineage_drift() -> None:
    module = _load_module()
    run_id = "fa-20260716t153000z-deadbeef"
    before_fixture = _versioned_fixture()
    before_fixture["audit_attribution"] = _audit_attribution(run_id, [])
    before = _capture(module, before_fixture, phase="S1", expected_deploy_sha=SHA_A)
    after_fixture = copy.deepcopy(before_fixture)
    topology = after_fixture["release_topology"]
    assert isinstance(topology, dict)
    sentinel = topology["migration_sentinel"]
    assert isinstance(sentinel, dict)
    sentinel["sha"] = SHA_B
    event_id = "30000000-0000-0000-0000-000000000001"
    _append_audit_rows(after_fixture, [event_id])
    after_fixture["audit_attribution"] = _audit_attribution(run_id, [event_id])
    after = _capture(module, after_fixture, phase="S2", expected_deploy_sha=SHA_A)

    report = module._compare_snapshots(
        before,
        after,
        expected_deploy_sha=SHA_A,
        acceptance_run_id=run_id,
    )

    assert report["status"] == "blocked"
    assert "release-identity-delta:release_topology_evidence" in report["blocking_reasons"]


def test_compare_blocks_schema_object_provider_and_not_observed_ambiguity() -> None:
    module = _load_module()
    before = _capture(module, _base_fixture(), phase="S0", expected_deploy_sha=SHA_A)

    schema_fixture = _base_fixture()
    schema = schema_fixture["schema"]
    assert isinstance(schema, dict)
    schema["fingerprint"] = FINGERPRINT_B
    schema_after = _capture(module, schema_fixture, phase="S1", expected_deploy_sha=SHA_A)
    schema_report = module._compare_snapshots(
        before, schema_after, expected_deploy_sha=SHA_A
    )
    assert "schema-fingerprint-delta" in schema_report["blocking_reasons"]

    object_fixture = _base_fixture()
    object_storage = object_fixture["object_storage"]
    assert isinstance(object_storage, dict)
    object_storage["fingerprint"] = FINGERPRINT_B
    object_after = _capture(module, object_fixture, phase="S1", expected_deploy_sha=SHA_A)
    object_report = module._compare_snapshots(
        before, object_after, expected_deploy_sha=SHA_A
    )
    assert "object-storage-delta" in object_report["blocking_reasons"]

    unobserved_fixture = _base_fixture()
    unobserved_fixture["object_storage"] = {
        "status": "not_observed",
        "reason": "fixture-has-no-object-ledger",
    }
    unobserved_before = _capture(
        module,
        unobserved_fixture,
        phase="S0",
        expected_deploy_sha=SHA_A,
    )
    unobserved_after = _capture(
        module,
        unobserved_fixture,
        phase="S1",
        expected_deploy_sha=SHA_A,
    )
    unobserved_report = module._compare_snapshots(
        unobserved_before, unobserved_after, expected_deploy_sha=SHA_A
    )
    assert unobserved_report["status"] == "blocked"
    assert "object-storage-not-observed" in unobserved_report["blocking_reasons"]


def test_compare_s1_to_s2_allows_only_run_attributable_audit_delta() -> None:
    module = _load_module()
    run_id = "fa-20260716t153000z-deadbeef"
    before_fixture = _versioned_fixture()
    before_fixture["audit_attribution"] = _audit_attribution(run_id, [])
    before = _capture(module, before_fixture, phase="S1", expected_deploy_sha=SHA_A)
    after_fixture = copy.deepcopy(before_fixture)
    event_ids = [
        "10000000-0000-0000-0000-000000000001",
        "10000000-0000-0000-0000-000000000002",
        "10000000-0000-0000-0000-000000000003",
    ]
    _append_audit_rows(after_fixture, event_ids)
    after_fixture["audit_attribution"] = _audit_attribution(run_id, event_ids)
    after = _capture(module, after_fixture, phase="S2", expected_deploy_sha=SHA_A)

    report = module._compare_snapshots(
        before,
        after,
        expected_deploy_sha=SHA_A,
        acceptance_run_id=run_id,
    )

    assert report["status"] == "pass"
    assert report["comparison"] == "S1->S2"
    assert report["database_write"] == "audit-log-only"
    assert report["audit_log_delta"] == 3
    assert report["attributed_acceptance_run_id"] == run_id


@pytest.mark.parametrize(
    "mutation", ["missing", "wrong-run", "unattributed", "concurrent", "reused-run"]
)
def test_compare_s1_to_s2_blocks_ambiguous_audit_delta(mutation: str) -> None:
    module = _load_module()
    run_id = "fa-20260716t153000z-deadbeef"
    before_fixture = _versioned_fixture()
    baseline_run_ids: list[str] = []
    if mutation == "reused-run":
        tables = before_fixture["tables"]
        assert isinstance(tables, dict)
        audit = tables["audit_log_events"]
        assert isinstance(audit, dict)
        row_hashes = audit["row_hashes"]
        assert isinstance(row_hashes, dict)
        baseline_run_ids = [sorted(row_hashes)[0]]
    before_fixture["audit_attribution"] = _audit_attribution(run_id, baseline_run_ids)
    before = _capture(module, before_fixture, phase="S1", expected_deploy_sha=SHA_A)
    after_fixture = copy.deepcopy(before_fixture)
    event_id = "20000000-0000-0000-0000-000000000001"
    _append_audit_rows(after_fixture, [event_id])
    if mutation == "missing":
        after_fixture.pop("audit_attribution")
    else:
        attributed_ids = (
            [] if mutation == "unattributed" else [*baseline_run_ids, event_id]
        )
        attribution_run = (
            "fa-20260716t153001z-feedbeef" if mutation == "wrong-run" else run_id
        )
        after_fixture["audit_attribution"] = _audit_attribution(
            attribution_run, attributed_ids
        )
    if mutation == "concurrent":
        tables = after_fixture["tables"]
        assert isinstance(tables, dict)
        audit = tables["audit_log_events"]
        assert isinstance(audit, dict)
        row_hashes = audit["row_hashes"]
        assert isinstance(row_hashes, dict)
        existing_id = sorted(row_hashes)[0]
        row_hashes[existing_id] = FINGERPRINT_B
        audit["row_content_fingerprint"] = FINGERPRINT_B
    after = _capture(module, after_fixture, phase="S2", expected_deploy_sha=SHA_A)

    report = module._compare_snapshots(
        before,
        after,
        expected_deploy_sha=SHA_A,
        acceptance_run_id=run_id,
    )

    assert report["status"] == "blocked"
    assert "audit-log-delta-not-run-attributable" in report["blocking_reasons"]


def test_compare_s1_to_s2_blocks_any_other_business_table_delta() -> None:
    module = _load_module()
    fixture = _versioned_fixture()
    before = _capture(module, fixture, phase="S1", expected_deploy_sha=SHA_A)
    changed = copy.deepcopy(fixture)
    tables = changed["tables"]
    assert isinstance(tables, dict)
    row = tables["review_tasks"]
    assert isinstance(row, dict)
    row["row_count"] = 99
    row["primary_key_fingerprint"] = FINGERPRINT_B
    after = _capture(module, changed, phase="S2", expected_deploy_sha=SHA_A)

    report = module._compare_snapshots(before, after, expected_deploy_sha=SHA_A)

    assert report["status"] == "blocked"
    assert "business-table-delta:review_tasks" in report["blocking_reasons"]


def test_duplicate_json_keys_fail_closed(tmp_path: Path) -> None:
    module = _load_module()
    path = tmp_path / "duplicate.json"
    path.write_text('{"format":"a","format":"b"}\n', encoding="utf-8")

    with pytest.raises(module.GuardError, match="duplicate JSON key: format"):
        module._load_json_file(path)


def test_ssh_capture_builds_strict_stdin_command_and_remote_readonly_collector() -> None:
    module = _load_module()

    command = module._build_ssh_capture_command(
        ssh_key=Path("/keys/production.pem"),
        ssh_user="ubuntu",
        ssh_host="101.34.52.232",
        remote_script_path="-",
        phase="S0",
        expected_deploy_sha=SHA_A,
    )

    assert command[:2] == ["ssh", "-i"]
    assert "BatchMode=yes" in command
    assert "StrictHostKeyChecking=yes" in command
    assert "IdentitiesOnly=yes" in command
    assert "ubuntu@101.34.52.232" in command
    assert command[-1].startswith("python3 - capture-live")
    assert "--expected-deploy-sha" in command[-1]
    assert "--observation-target-host 101.34.52.232" in command[-1]
    assert "--confirm-production-readonly 101.34.52.232" in command[-1]
    assert "/opt/medical-audit/app/scripts" not in command[-1]
    remote_source = module._remote_capture_source()
    assert 'PGOPTIONS="-c default_transaction_read_only=on"' in remote_source
    assert "psql" in remote_source
    assert "-X" in remote_source
    assert "medical_audit_pg" in remote_source
    assert "BEGIN TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY DEFERRABLE" in remote_source
    assert "audit_agent_invocations" in remote_source


def test_release_guard_fixture_capture_executes_under_python_310(tmp_path: Path) -> None:
    uv = shutil.which("uv")
    assert uv is not None, "uv is required to locate the production-compatible Python 3.10 runtime"
    interpreter_result = subprocess.run(
        [uv, "python", "find", "3.10"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert interpreter_result.returncode == 0, interpreter_result.stderr
    python310 = interpreter_result.stdout.strip()
    assert python310, "uv did not return a Python 3.10 interpreter path"

    fixture = tmp_path / "python310-input.json"
    report_path = tmp_path / "python310-report.json"
    fixture.write_text(json.dumps(_base_fixture()), encoding="utf-8")

    completed = subprocess.run(
        [
            python310,
            str(SCRIPT_PATH),
            "capture",
            "--phase",
            "S0",
            "--expected-deploy-sha",
            SHA_A,
            "--input-json",
            str(fixture),
            "--output",
            str(report_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "pass"
    assert report["phase"] == "S0"
    assert report["generated_at"].endswith("Z")


def test_ssh_capture_streams_local_source_without_using_remote_checkout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    expected_fixture = _live_fixture()
    observed: dict[str, object] = {}

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        observed["command"] = command
        observed["input"] = kwargs.get("input")
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(expected_fixture),
            stderr="",
        )

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    command = module._build_ssh_capture_command(
        ssh_key=Path("/keys/production.pem"),
        ssh_user="ubuntu",
        ssh_host="101.34.52.232",
        remote_script_path="-",
        phase="S0",
        expected_deploy_sha=SHA_A,
    )

    report = module._run_ssh_capture(
        command,
        ssh_host="101.34.52.232",
        ssh_user="ubuntu",
        phase="S0",
        expected_deploy_sha=SHA_A,
    )

    assert report["status"] == "pass"
    assert report["source"] == "ssh-live-readonly"
    assert report["capture_provenance"]["transport"] == "ssh-stdin"
    assert report["capture_provenance"]["ssh_host"] == "101.34.52.232"
    assert isinstance(report["capture_envelope_id"], str)
    assert observed["command"] == command
    assert observed["input"] == module._remote_capture_source()


def test_hidden_capture_live_cannot_write_a_remote_output_file(tmp_path: Path) -> None:
    output = tmp_path / "forbidden-live-output.json"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "capture-live",
            "--phase",
            "S0",
            "--expected-deploy-sha",
            SHA_A,
            "--observation-target-host",
            "101.34.52.232",
            "--confirm-production-readonly",
            "101.34.52.232",
            "--output",
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "unrecognized arguments: --output" in result.stderr
    assert not output.exists()


def test_live_database_output_parser_covers_all_tables_and_attribution() -> None:
    module = _load_module()
    run_id = "fa-20260716t153000z-deadbeef"
    lines = [
        "TX|on|serializable|on",
        "WAL_START|0/ABC",
        f"SCHEMA|{FINGERPRINT_A}",
    ]
    lines.append("SCHEMA_TABLES|" + ",".join(sorted(ALLOWLISTED_TABLES)))
    lines.extend(
        f"TABLE|{name}|{index}|{index + 10:064x}|{index + 30:064x}|"
        "2026-07-16 08:30:00+00"
        for index, name in enumerate(ALLOWLISTED_TABLES)
    )
    audit_ids = [f"00000000-0000-0000-0000-{item:012d}" for item in range(11)]
    audit_rows = {item: FINGERPRINT_A for item in audit_ids}
    lines.append("AUDIT_ROWS|" + json.dumps(audit_rows))
    lines.append(f"OBJECT|8|{FINGERPRINT_B}|2026-07-16 08:30:00+00")
    attribution_ids = [
        "10000000-0000-0000-0000-000000000001",
        "10000000-0000-0000-0000-000000000002",
        "10000000-0000-0000-0000-000000000003",
    ]
    attribution_fingerprint = hashlib.sha256(
        ",".join(attribution_ids).encode()
    ).hexdigest()
    lines.append(
        f"ATTRIBUTION|3|{attribution_fingerprint}|{json.dumps(attribution_ids)}"
    )
    lines.append("WAL_END|0/ABC")

    parsed = module._parse_database_snapshot_output(
        "\n".join(lines),
        acceptance_run_id=run_id,
    )

    assert parsed["transaction_read_only"] == "on"
    assert parsed["transaction_isolation"] == "serializable"
    assert parsed["transaction_deferrable"] == "on"
    assert parsed["database_quiescent"] is True
    assert set(parsed["tables"]) == set(ALLOWLISTED_TABLES)
    assert parsed["object_storage"]["observation_scope"] == "database-ledger"
    assert parsed["audit_attribution"]["attributable_event_count"] == 3


def test_live_database_output_parser_rejects_duplicate_and_unknown_records() -> None:
    module = _load_module()

    with pytest.raises(module.GuardError, match="duplicate PostgreSQL snapshot record: TX"):
        module._parse_database_snapshot_output(
            "TX|on|serializable|on\nTX|on|serializable|on",
            acceptance_run_id=None,
        )
    with pytest.raises(module.GuardError, match="unknown or malformed"):
        module._parse_database_snapshot_output(
            "UNEXPECTED|value",
            acceptance_run_id=None,
        )


def test_live_database_sql_tracks_updated_rows_and_enforces_readonly_transaction() -> None:
    module = _load_module()

    sql = module._database_snapshot_sql(acceptance_run_id=None)

    assert "BEGIN TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY DEFERRABLE" in sql
    assert "pg_current_wal_lsn()" in sql
    assert "pg_get_indexdef" in sql
    assert "pg_policy" in sql
    assert "p.polcmd::text || ':'" in sql
    assert "p.polpermissive::text || ':'" in sql
    assert "pg_get_triggerdef" in sql
    assert "pg_get_functiondef" in sql
    assert "to_jsonb(table_row)" in sql
    for table in (
        "review_tasks",
        "audit_projects",
        "audit_project_members",
        "document_storage_objects",
        "document_upload_governance_jobs",
    ):
        assert (
            "COALESCE(max(GREATEST(created_at, updated_at))::text, 'none') "
            f"FROM public.{table} AS table_row;"
        ) in sql
    assert (
        "COALESCE(max(created_at)::text, 'none') "
        "FROM public.query_logs AS table_row;"
    ) in sql


def test_live_execution_boundary_rejects_non_postgresql_or_non_readonly_commands() -> None:
    module = _load_module()
    boundary = module._LiveExecutionBoundary(postgres_container="medical_audit_pg")

    with pytest.raises(module.GuardError, match="outside the readonly execution boundary"):
        boundary.run_postgresql_readonly(["curl", "https://provider.invalid"])

    assert boundary.rejected_command_count == 1


def test_cli_capture_and_compare_write_fail_closed_reports(tmp_path: Path) -> None:
    before_input = tmp_path / "before-input.json"
    after_input = tmp_path / "after-input.json"
    before_output = tmp_path / "before.json"
    after_output = tmp_path / "after.json"
    compare_output = tmp_path / "compare.json"
    before_input.write_text(json.dumps(_base_fixture()), encoding="utf-8")
    after_input.write_text(json.dumps(_versioned_fixture(deploy_sha=SHA_B)), encoding="utf-8")

    for phase, deploy_sha, source, output in (
        ("S0", SHA_A, before_input, before_output),
        ("S1", SHA_B, after_input, after_output),
    ):
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "capture",
                "--phase",
                phase,
                "--expected-deploy-sha",
                deploy_sha,
                "--input-json",
                str(source),
                "--output",
                str(output),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr

    compared = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "compare",
            "--before",
            str(before_output),
            "--after",
            str(after_output),
            "--expected-deploy-sha",
            SHA_B,
            "--output",
            str(compare_output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert compared.returncode == 0, compared.stderr
    report = json.loads(compare_output.read_text(encoding="utf-8"))
    assert report["status"] == "pass"
    assert report["comparison"] == "S0->S1"
