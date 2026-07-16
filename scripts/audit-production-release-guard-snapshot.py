#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import stat
import subprocess
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

FORMAT = "medical-audit-production-release-guard-v1"
FIXTURE_FORMAT = "medical-audit-production-release-guard-fixture-v1"
WEB_MANIFEST_FORMAT = "medical-audit-web-release-manifest-v1"
EXECUTION_BOUNDARY_FORMAT = "medical-audit-release-guard-execution-boundary-v1"
OBSERVATION_TARGET_FORMAT = "medical-audit-release-guard-observation-target-v1"
CAPTURE_PROVENANCE_FORMAT = "medical-audit-release-guard-capture-provenance-v1"
PHASES = ("S0", "S1", "S2")
SHA40_PATTERN = re.compile(r"[0-9a-f]{40}\Z")
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
CURRENT_TARGET_PATTERN = re.compile(r"releases/([0-9a-f]{40})\Z")
ACCEPTANCE_RUN_ID_PATTERN = re.compile(r"fa-[0-9]{8}t[0-9]{6}z-[0-9a-f]{8,32}\Z")

DEFAULT_SSH_USER = "ubuntu"
DEFAULT_SSH_HOST = "101.34.52.232"
DEFAULT_REMOTE_APP_DIR = "/opt/medical-audit/app"
DEFAULT_REMOTE_WEB_DIR = "/var/www/audit"
DEFAULT_POSTGRES_CONTAINER = "medical_audit_pg"

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
UPDATED_AT_TABLES = frozenset(
    {
        "review_tasks",
        "audit_projects",
        "audit_project_members",
        "document_storage_objects",
        "document_upload_governance_jobs",
    }
)
LIVE_COLLECTOR_PROTOCOL = "ssh-stdin-release-topology-postgresql-readonly-v2"
SCHEMA_FINGERPRINT_SCOPE = (
    "columns",
    "constraints",
    "indexes",
    "table-acl",
    "row-level-security-flags",
    "row-level-security-policies",
    "triggers",
    "trigger-functions",
)
LIVE_ALLOWED_OPERATIONS = (
    "filesystem-read",
    "docker-exec-psql-readonly",
    "docker-inspect-readonly",
    "docker-exec-app-deploy-sha-readonly",
    "docker-exec-nginx-config-test",
)
APP_CONTAINER = "medical_audit_app"
NGINX_CONTAINER = "ai_video_nginx"
NGINX_WEB_MOUNT = "/var/www/audit"


class GuardError(RuntimeError):
    pass


class _LiveExecutionBoundary:
    def __init__(self, *, postgres_container: str) -> None:
        self.postgres_container = postgres_container
        self.postgresql_readonly_command_count = 0
        self.runtime_readonly_command_count = 0
        self.rejected_command_count = 0

    def run_postgresql_readonly(self, command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        expected_prefix = ("docker", "exec", self.postgres_container, "sh", "-c")
        shell_contract = command[5] if len(command) > 5 else ""
        if (
            tuple(command[:5]) != expected_prefix
            or 'PGOPTIONS="-c default_transaction_read_only=on"' not in shell_contract
            or "psql -X" not in shell_contract
            or "ON_ERROR_STOP=1" not in shell_contract
            or "--env-file" in shell_contract
        ):
            self.rejected_command_count += 1
            raise GuardError("live collector command is outside the readonly execution boundary")
        self.postgresql_readonly_command_count += 1
        return subprocess.run(list(command), check=False, capture_output=True, text=True)

    def run_runtime_readonly(self, command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        allowed_commands = {
            (
                "docker",
                "inspect",
                APP_CONTAINER,
                "--format",
                "{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{end}}",
            ),
            (
                "docker",
                "exec",
                APP_CONTAINER,
                "sh",
                "-c",
                'printf "%s" "${MEDICAL_AUDIT_DEPLOY_SHA:-}"',
            ),
            (
                "docker",
                "inspect",
                NGINX_CONTAINER,
                "--format",
                (
                    '{{range .Mounts}}{{if eq .Destination "/var/www/audit"}}'
                    "{{.Source}}|{{.RW}}{{end}}{{end}}"
                ),
            ),
            ("docker", "exec", NGINX_CONTAINER, "nginx", "-t"),
        }
        normalized = tuple(command)
        if normalized not in allowed_commands:
            self.rejected_command_count += 1
            raise GuardError("live collector command is outside the readonly execution boundary")
        self.runtime_readonly_command_count += 1
        return subprocess.run(list(command), check=False, capture_output=True, text=True)

    def report(self) -> dict[str, object]:
        if (
            self.postgresql_readonly_command_count != 2
            or self.runtime_readonly_command_count != 8
            or self.rejected_command_count != 0
        ):
            raise GuardError("live collector execution boundary is incomplete")
        return {
            "format": EXECUTION_BOUNDARY_FORMAT,
            "collector_protocol": LIVE_COLLECTOR_PROTOCOL,
            "allowed_operations": list(LIVE_ALLOWED_OPERATIONS),
            "executed_postgresql_readonly_commands": self.postgresql_readonly_command_count,
            "executed_runtime_readonly_commands": self.runtime_readonly_command_count,
            "rejected_command_count": self.rejected_command_count,
            "collector_provider_endpoint_attempt_count": 0,
            "provider_environment_read": False,
            "secret_values_reported": False,
        }


def main() -> int:
    args = _parse_args()
    try:
        if args.command == "capture":
            report = _capture_from_args(args)
        elif args.command == "capture-live":
            report = _capture_live_from_args(args)
        elif args.command == "compare":
            report = _compare_from_args(args)
        else:
            raise GuardError("missing command")
    except GuardError as exc:
        print(f"release guard failed: {exc}", file=sys.stderr)
        return 2

    output = getattr(args, "output", "-")
    _emit_report(report, output=str(output))
    if args.command == "capture-live":
        return 0
    return 0 if report.get("status") == "pass" else 2


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Capture and compare fail-closed production release guard snapshots. "
            "Fixture capture is L2. SSH capture is explicit L3 production read-only work."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    capture = subparsers.add_parser("capture", help="Capture from fixture JSON or explicit SSH")
    _add_capture_contract_args(capture)
    capture.add_argument("--input-json", help="Controlled fixture JSON input")
    capture.add_argument("--ssh-key", help="SSH key for an explicitly authorized live capture")
    capture.add_argument("--ssh-user", default=DEFAULT_SSH_USER)
    capture.add_argument("--ssh-host", default=DEFAULT_SSH_HOST)
    capture.add_argument("--remote-app-dir", default=DEFAULT_REMOTE_APP_DIR)
    capture.add_argument("--remote-web-dir", default=DEFAULT_REMOTE_WEB_DIR)
    capture.add_argument("--postgres-container", default=DEFAULT_POSTGRES_CONTAINER)
    capture.add_argument(
        "--confirm-production-readonly",
        default="",
        help="Required for SSH capture and must exactly equal --ssh-host.",
    )
    capture.add_argument(
        "--ssh-command-only",
        action="store_true",
        help="Emit a blocked command plan without opening an SSH connection.",
    )

    capture_live = subparsers.add_parser(
        "capture-live",
        help=argparse.SUPPRESS,
    )
    _add_capture_contract_args(capture_live, include_output=False)
    capture_live.add_argument("--remote-app-dir", default=DEFAULT_REMOTE_APP_DIR)
    capture_live.add_argument("--remote-web-dir", default=DEFAULT_REMOTE_WEB_DIR)
    capture_live.add_argument("--postgres-container", default=DEFAULT_POSTGRES_CONTAINER)
    capture_live.add_argument("--observation-target-host", required=True)
    capture_live.add_argument("--confirm-production-readonly", required=True)

    compare = subparsers.add_parser("compare", help="Compare S0->S1 or S1->S2")
    compare.add_argument("--before", required=True)
    compare.add_argument("--after", required=True)
    compare.add_argument("--expected-deploy-sha", required=True)
    compare.add_argument("--acceptance-run-id", default="")
    compare.add_argument("--output", default="-")
    return parser.parse_args()


def _add_capture_contract_args(
    parser: argparse.ArgumentParser,
    *,
    include_output: bool = True,
) -> None:
    parser.add_argument("--phase", choices=PHASES, required=True)
    parser.add_argument("--expected-deploy-sha", required=True)
    parser.add_argument("--acceptance-run-id", default="")
    if include_output:
        parser.add_argument("--output", default="-")


def _capture_from_args(args: argparse.Namespace) -> dict[str, object]:
    expected_sha = str(args.expected_deploy_sha)
    phase = str(args.phase)
    acceptance_run_id = _optional_text(args.acceptance_run_id)
    input_json = _optional_text(args.input_json)
    ssh_key_value = _optional_text(args.ssh_key)
    if (input_json is None) == (ssh_key_value is None):
        raise GuardError("capture requires exactly one of --input-json or --ssh-key")

    if input_json is not None:
        if bool(args.ssh_command_only):
            raise GuardError("--ssh-command-only cannot be used with --input-json")
        payload = _load_json_file(Path(input_json))
        return _capture_snapshot(
            payload,
            phase=phase,
            expected_deploy_sha=expected_sha,
            source="fixture",
        )

    assert ssh_key_value is not None
    ssh_key = Path(ssh_key_value).expanduser()
    command = _build_ssh_capture_command(
        ssh_key=ssh_key,
        ssh_user=str(args.ssh_user),
        ssh_host=str(args.ssh_host),
        remote_script_path="-",
        phase=phase,
        expected_deploy_sha=expected_sha,
        remote_app_dir=str(args.remote_app_dir),
        remote_web_dir=str(args.remote_web_dir),
        postgres_container=str(args.postgres_container),
        acceptance_run_id=acceptance_run_id,
    )
    if bool(args.ssh_command_only):
        return _ssh_command_plan(
            command,
            phase=phase,
            expected_deploy_sha=expected_sha,
        )
    if str(args.confirm_production_readonly) != str(args.ssh_host):
        raise GuardError("SSH capture requires --confirm-production-readonly to equal --ssh-host")
    if str(args.ssh_host) != DEFAULT_SSH_HOST:
        raise GuardError(
            f"SSH capture target must be the configured production host {DEFAULT_SSH_HOST}"
        )
    if str(args.ssh_user) != DEFAULT_SSH_USER:
        raise GuardError(
            f"SSH capture user must be the configured production user {DEFAULT_SSH_USER}"
        )
    if (
        str(args.remote_app_dir) != DEFAULT_REMOTE_APP_DIR
        or str(args.remote_web_dir) != DEFAULT_REMOTE_WEB_DIR
        or str(args.postgres_container) != DEFAULT_POSTGRES_CONTAINER
    ):
        raise GuardError(
            "SSH capture scope must match the configured production directories/database"
        )
    if not ssh_key.is_file():
        raise GuardError(f"SSH key not found: {ssh_key}")
    return _run_ssh_capture(
        command,
        ssh_host=str(args.ssh_host),
        ssh_user=str(args.ssh_user),
        phase=phase,
        expected_deploy_sha=expected_sha,
    )


def _capture_live_from_args(args: argparse.Namespace) -> dict[str, object]:
    observation_target_host = str(args.observation_target_host)
    if (
        observation_target_host != DEFAULT_SSH_HOST
        or str(args.confirm_production_readonly) != observation_target_host
    ):
        raise GuardError(
            "capture-live requires the configured production observation target and confirmation"
        )
    fixture = _collect_live_fixture_local(
        expected_deploy_sha=str(args.expected_deploy_sha),
        remote_app_dir=Path(str(args.remote_app_dir)),
        remote_web_dir=Path(str(args.remote_web_dir)),
        postgres_container=str(args.postgres_container),
        acceptance_run_id=_optional_text(args.acceptance_run_id),
        observation_target_host=observation_target_host,
    )
    return fixture


def _compare_from_args(args: argparse.Namespace) -> dict[str, object]:
    before = _load_json_file(Path(str(args.before)))
    after = _load_json_file(Path(str(args.after)))
    return _compare_snapshots(
        before,
        after,
        expected_deploy_sha=str(args.expected_deploy_sha),
        acceptance_run_id=_optional_text(args.acceptance_run_id),
    )


def _capture_snapshot(
    payload: Mapping[str, object],
    *,
    phase: str,
    expected_deploy_sha: str,
    source: str,
    generated_at: str | None = None,
) -> dict[str, object]:
    blocking: list[str] = []
    if payload.get("format") != FIXTURE_FORMAT:
        blocking.append("fixture-format-invalid")
    if phase not in PHASES:
        blocking.append("phase-invalid")
    if not _is_sha40(expected_deploy_sha):
        blocking.append("expected-deploy-sha-invalid")
    if source not in {"fixture", "ssh-live-readonly"}:
        blocking.append("capture-source-invalid")
    generated_at_value = generated_at or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    if (
        re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z",
            generated_at_value,
        )
        is None
    ):
        blocking.append("generated-at-invalid")

    observation_target = _normalize_observation_target(
        payload.get("observation_target"),
        source=source,
        blocking=blocking,
    )

    transaction_observed = payload.get("transaction_read_only")
    transaction_isolation_observed = payload.get("transaction_isolation")
    transaction_deferrable_observed = payload.get("transaction_deferrable")
    transaction_read_only = transaction_observed == "on"
    if not transaction_read_only:
        blocking.append("transaction-read-only-not-on")
    if transaction_isolation_observed != "serializable":
        blocking.append("transaction-isolation-not-serializable")
    if transaction_deferrable_observed != "on":
        blocking.append("transaction-deferrable-not-on")

    consistency = _normalize_consistency(payload.get("consistency"), blocking)
    topology_name, topology_evidence = _classify_release_topology(payload.get("release_topology"))
    if topology_name == "partial_or_unknown":
        blocking.append("release-topology-partial-or-unknown")

    release_identity = _mapping_or_empty(payload.get("release_identity"))
    fixture_expected_sha = _optional_text(release_identity.get("expected_deploy_sha"))
    observed_sha = _optional_text(release_identity.get("observed_deploy_sha"))
    if fixture_expected_sha != expected_deploy_sha:
        blocking.append("fixture-expected-deploy-sha-mismatch")
    if not _is_sha40(observed_sha):
        blocking.append("observed-deploy-sha-invalid")
    if observed_sha != expected_deploy_sha:
        blocking.append("expected-observed-deploy-sha-mismatch")

    topology_marker = _mapping_or_empty(topology_evidence.get("deploy_marker"))
    if _optional_text(topology_marker.get("sha")) != observed_sha:
        blocking.append("deploy-marker-observed-sha-mismatch")

    schema_fingerprint, schema_tables, schema_scope = _normalize_schema(
        payload.get("schema"), blocking
    )
    tables = _normalize_tables(payload.get("tables"), blocking)
    object_storage = _normalize_object_storage(payload.get("object_storage"), blocking)
    provider = _normalize_provider(payload.get("provider"), blocking, source=source)
    attribution = _normalize_attribution(payload.get("audit_attribution"), blocking)

    current_target, manifest_source_sha, manifest_sha256 = _release_identity_fields(
        topology_name,
        topology_evidence,
    )
    if topology_name == "versioned_ready":
        if current_target != f"releases/{observed_sha}":
            blocking.append("current-release-target-observed-sha-mismatch")
        if manifest_source_sha != observed_sha:
            blocking.append("manifest-source-sha-observed-sha-mismatch")

    normalized_core: dict[str, object] = {
        "phase": phase,
        "generated_at": generated_at_value,
        "observation_target": observation_target,
        "expected_deploy_sha": expected_deploy_sha,
        "observed_deploy_sha": observed_sha,
        "transaction_read_only": transaction_read_only,
        "transaction_read_only_observed": transaction_observed,
        "transaction_isolation_observed": transaction_isolation_observed,
        "transaction_deferrable_observed": transaction_deferrable_observed,
        "release_topology": topology_name,
        "release_topology_evidence": topology_evidence,
        "current_release_target": current_target,
        "manifest_source_sha": manifest_source_sha,
        "manifest_sha256": manifest_sha256,
        "schema_fingerprint": schema_fingerprint,
        "schema_tables": schema_tables,
        "schema_fingerprint_scope": schema_scope,
        "tables": tables,
        "object_storage": object_storage,
        "provider_call_status": "not_observed",
        "provider_evidence_source": "outside-release-guard-scope",
        "collector_provider_call_status": provider["status"],
        "collector_provider_attempt_count": provider["attempt_count"],
        "collector_execution_boundary": provider["execution_boundary"],
        "capture_consistency": consistency,
        "audit_attribution": attribution,
    }
    snapshot_id = hashlib.sha256(_canonical_json(normalized_core).encode("utf-8")).hexdigest()
    reasons = _deduplicate(blocking)
    return {
        "format": FORMAT,
        "mode": "capture",
        "phase": phase,
        "status": "pass" if not reasons else "blocked",
        "evidence_grade": (
            "L3-production-read-only"
            if source == "ssh-live-readonly"
            else "L2-fixture-or-dry-run"
        ),
        "source": source,
        "observation_target": observation_target,
        "generated_at": generated_at_value,
        "expected_deploy_sha": expected_deploy_sha,
        "observed_deploy_sha": observed_sha,
        "provider_call_status": "not_observed",
        "provider_evidence_source": "outside-release-guard-scope",
        "collector_provider_call_status": provider["status"],
        "collector_provider_attempt_count": provider["attempt_count"],
        "collector_execution_boundary": provider["execution_boundary"],
        "database_write": False,
        "transaction_read_only": transaction_read_only,
        "transaction_read_only_observed": transaction_observed,
        "transaction_isolation_observed": transaction_isolation_observed,
        "transaction_deferrable_observed": transaction_deferrable_observed,
        "snapshot_id": snapshot_id,
        "release_topology": topology_name,
        "release_topology_evidence": topology_evidence,
        "current_release_target": current_target,
        "manifest_source_sha": manifest_source_sha,
        "manifest_sha256": manifest_sha256,
        "schema_fingerprint": schema_fingerprint,
        "schema_tables": schema_tables,
        "schema_fingerprint_scope": schema_scope,
        "tables": tables,
        "object_storage": object_storage,
        "capture_consistency": consistency,
        "audit_attribution": attribution,
        "blocking_reasons": reasons,
        "guard_execution_write": False,
        "capture_side_effect": "none",
    }


CAPTURE_INTEGRITY_FIELDS = (
    "format",
    "mode",
    "phase",
    "status",
    "evidence_grade",
    "source",
    "generated_at",
    "observation_target",
    "expected_deploy_sha",
    "observed_deploy_sha",
    "provider_call_status",
    "provider_evidence_source",
    "collector_provider_call_status",
    "collector_provider_attempt_count",
    "collector_execution_boundary",
    "database_write",
    "transaction_read_only",
    "transaction_read_only_observed",
    "transaction_isolation_observed",
    "transaction_deferrable_observed",
    "snapshot_id",
    "release_topology",
    "release_topology_evidence",
    "current_release_target",
    "manifest_source_sha",
    "manifest_sha256",
    "schema_fingerprint",
    "schema_tables",
    "schema_fingerprint_scope",
    "tables",
    "object_storage",
    "capture_consistency",
    "audit_attribution",
    "blocking_reasons",
    "guard_execution_write",
    "capture_side_effect",
)


def _capture_fixture_from_report(snapshot: Mapping[str, object]) -> dict[str, object]:
    return {
        "format": FIXTURE_FORMAT,
        "observation_target": snapshot.get("observation_target"),
        "transaction_read_only": snapshot.get("transaction_read_only_observed"),
        "transaction_isolation": snapshot.get("transaction_isolation_observed"),
        "transaction_deferrable": snapshot.get("transaction_deferrable_observed"),
        "consistency": snapshot.get("capture_consistency"),
        "release_topology": snapshot.get("release_topology_evidence"),
        "schema": {
            "algorithm": "sha256",
            "fingerprint": snapshot.get("schema_fingerprint"),
            "tables": snapshot.get("schema_tables"),
            "scope": snapshot.get("schema_fingerprint_scope"),
        },
        "tables": snapshot.get("tables"),
        "object_storage": snapshot.get("object_storage"),
        "release_identity": {
            "expected_deploy_sha": snapshot.get("expected_deploy_sha"),
            "observed_deploy_sha": snapshot.get("observed_deploy_sha"),
        },
        "provider": {
            "status": snapshot.get("collector_provider_call_status"),
            "evidence_source": "collector-execution-boundary",
            "attempt_count": snapshot.get("collector_provider_attempt_count"),
            "guard_execution_boundary": snapshot.get("collector_execution_boundary"),
        },
        "audit_attribution": snapshot.get("audit_attribution"),
    }


def _capture_report_is_valid(snapshot: Mapping[str, object]) -> bool:
    if any(field not in snapshot for field in CAPTURE_INTEGRITY_FIELDS):
        return False
    source = _optional_text(snapshot.get("source"))
    phase = _optional_text(snapshot.get("phase"))
    expected_deploy_sha = _optional_text(snapshot.get("expected_deploy_sha"))
    generated_at = _optional_text(snapshot.get("generated_at"))
    if (
        source not in {"fixture", "ssh-live-readonly"}
        or phase not in PHASES
        or expected_deploy_sha is None
        or generated_at is None
        or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", generated_at)
        is None
    ):
        return False
    rebuilt = _capture_snapshot(
        _capture_fixture_from_report(snapshot),
        phase=phase,
        expected_deploy_sha=expected_deploy_sha,
        source=source,
        generated_at=generated_at,
    )
    return (
        rebuilt.get("status") == "pass"
        and all(snapshot.get(field) == rebuilt.get(field) for field in CAPTURE_INTEGRITY_FIELDS)
        and _capture_provenance_is_valid(snapshot)
    )


def _capture_provenance_is_valid(snapshot: Mapping[str, object]) -> bool:
    source = _optional_text(snapshot.get("source"))
    provenance = snapshot.get("capture_provenance")
    envelope_id = _optional_text(snapshot.get("capture_envelope_id"))
    if source == "fixture":
        return provenance is None and envelope_id is None
    if source != "ssh-live-readonly":
        return False
    value = _mapping_or_empty(provenance)
    expected_source_sha256 = hashlib.sha256(
        _remote_capture_source().encode("utf-8")
    ).hexdigest()
    if (
        value.get("format") != CAPTURE_PROVENANCE_FORMAT
        or value.get("transport") != "ssh-stdin"
        or value.get("ssh_host") != DEFAULT_SSH_HOST
        or value.get("ssh_user") != DEFAULT_SSH_USER
        or value.get("batch_mode") is not True
        or value.get("strict_host_key_checking") is not True
        or value.get("identities_only") is not True
        or value.get("ssh_exit_code") != 0
        or value.get("remote_app_dir") != DEFAULT_REMOTE_APP_DIR
        or value.get("remote_web_dir") != DEFAULT_REMOTE_WEB_DIR
        or value.get("postgres_container") != DEFAULT_POSTGRES_CONTAINER
        or value.get("collector_source_sha256") != expected_source_sha256
    ):
        return False
    expected_envelope_id = hashlib.sha256(
        _canonical_json(
            {
                "snapshot_id": snapshot.get("snapshot_id"),
                "capture_provenance": value,
            }
        ).encode("utf-8")
    ).hexdigest()
    return envelope_id == expected_envelope_id


def _compare_snapshots(
    before: Mapping[str, object],
    after: Mapping[str, object],
    *,
    expected_deploy_sha: str | None = None,
    acceptance_run_id: str | None = None,
) -> dict[str, object]:
    blocking: list[str] = []
    before_phase = _optional_text(before.get("phase"))
    after_phase = _optional_text(after.get("phase"))
    comparison = f"{before_phase or 'unknown'}->{after_phase or 'unknown'}"
    if (before_phase, after_phase) not in {("S0", "S1"), ("S1", "S2")}:
        blocking.append("comparison-phase-transition-invalid")
    if (
        not _is_sha40(expected_deploy_sha)
        or after.get("expected_deploy_sha") != expected_deploy_sha
        or after.get("observed_deploy_sha") != expected_deploy_sha
    ):
        blocking.append("comparison-expected-deploy-sha-mismatch")

    for label, snapshot in (("before", before), ("after", after)):
        if not _capture_report_is_valid(snapshot):
            blocking.append(f"{label}-snapshot-contract-invalid")

    if before.get("source") != after.get("source"):
        blocking.append("capture-source-mismatch")

    before_topology = before.get("release_topology")
    after_topology = after.get("release_topology")
    comparison_profile: str | None = None
    if comparison == "S0->S1":
        comparison_profile = "deploy"
        if before_topology not in {"legacy_ready", "versioned_ready"} or after_topology != (
            "versioned_ready"
        ):
            blocking.append("release-topology-transition-invalid")
        before_topology_evidence = _mapping_or_empty(before.get("release_topology_evidence"))
        after_topology_evidence = _mapping_or_empty(after.get("release_topology_evidence"))
        before_sentinel = _mapping_or_empty(
            before_topology_evidence.get("migration_sentinel")
        )
        after_sentinel = _mapping_or_empty(
            after_topology_evidence.get("migration_sentinel")
        )
        if before_topology == "legacy_ready":
            if after_sentinel.get("sha") != after.get("expected_deploy_sha"):
                blocking.append("migration-sentinel-lineage-invalid")
        elif before_topology == "versioned_ready" and before_sentinel != after_sentinel:
            blocking.append("migration-sentinel-lineage-delta")
    elif comparison == "S1->S2":
        comparison_profile = "acceptance"
        if before_topology != "versioned_ready" or after_topology != "versioned_ready":
            blocking.append("release-topology-transition-invalid")

    if before.get("schema_fingerprint") != after.get("schema_fingerprint"):
        blocking.append("schema-fingerprint-delta")
    if before.get("schema_fingerprint_scope") != after.get("schema_fingerprint_scope"):
        blocking.append("schema-fingerprint-scope-delta")
    before_tables = _mapping_or_empty(before.get("tables"))
    after_tables = _mapping_or_empty(after.get("tables"))
    if set(before_tables) != set(ALLOWLISTED_TABLES) or set(after_tables) != set(
        ALLOWLISTED_TABLES
    ):
        blocking.append("business-table-allowlist-mismatch")

    excluded = {"audit_log_events"} if comparison == "S1->S2" else set()
    for table in ALLOWLISTED_TABLES:
        if table in excluded:
            continue
        if before_tables.get(table) != after_tables.get(table):
            blocking.append(f"business-table-delta:{table}")

    before_object = _mapping_or_empty(before.get("object_storage"))
    after_object = _mapping_or_empty(after.get("object_storage"))
    if before_object.get("status") != "observed" or after_object.get("status") != "observed":
        blocking.append("object-storage-not-observed")
    elif before_object != after_object:
        blocking.append("object-storage-delta")

    audit_delta = 0
    attributed_run: str | None = None
    database_write: object = False
    if comparison == "S1->S2":
        if not _is_acceptance_run_id(acceptance_run_id):
            blocking.append("acceptance-run-id-required")
        for field in (
            "expected_deploy_sha",
            "observed_deploy_sha",
            "release_topology",
            "release_topology_evidence",
            "current_release_target",
            "manifest_source_sha",
            "manifest_sha256",
        ):
            if before.get(field) != after.get(field):
                blocking.append(f"release-identity-delta:{field}")
        audit_delta, attribution_ok, attributed_run = _audit_delta_is_attributable(
            before_tables.get("audit_log_events"),
            after_tables.get("audit_log_events"),
            before.get("audit_attribution"),
            after.get("audit_attribution"),
            expected_run_id=acceptance_run_id,
        )
        if not attribution_ok:
            blocking.append("audit-log-delta-not-run-attributable")
        elif audit_delta > 0:
            database_write = "audit-log-only"
    elif comparison == "S0->S1":
        if before_tables.get("audit_log_events") != after_tables.get("audit_log_events"):
            blocking.append("business-table-delta:audit_log_events")

    reasons = _deduplicate(blocking)
    return {
        "format": FORMAT,
        "mode": "compare",
        "phase": after_phase,
        "comparison": comparison,
        "comparison_profile": comparison_profile,
        "status": "pass" if not reasons else "blocked",
        "evidence_grade": _lower_evidence_grade(before, after),
        "expected_deploy_sha": after.get("expected_deploy_sha"),
        "observed_deploy_sha": after.get("observed_deploy_sha"),
        "provider_call_status": after.get("provider_call_status", "unknown"),
        "provider_evidence_source": after.get("provider_evidence_source"),
        "collector_provider_call_status": after.get("collector_provider_call_status"),
        "collector_provider_attempt_count": after.get("collector_provider_attempt_count"),
        "collector_execution_boundary": after.get("collector_execution_boundary"),
        "database_write": database_write,
        "transaction_read_only": (
            before.get("transaction_read_only") is True
            and after.get("transaction_read_only") is True
        ),
        "snapshot_id": after.get("snapshot_id"),
        "before_snapshot_id": before.get("snapshot_id"),
        "current_release_target": after.get("current_release_target"),
        "manifest_source_sha": after.get("manifest_source_sha"),
        "manifest_sha256": after.get("manifest_sha256"),
        "schema_fingerprint": after.get("schema_fingerprint"),
        "audit_log_delta": audit_delta,
        "attributed_acceptance_run_id": attributed_run,
        "blocking_reasons": reasons,
        "guard_execution_write": False,
        "capture_side_effect": "none",
    }


def _audit_delta_is_attributable(
    before_value: object,
    after_value: object,
    before_attribution_value: object,
    after_attribution_value: object,
    *,
    expected_run_id: str | None,
) -> tuple[int, bool, str | None]:
    before = _mapping_or_empty(before_value)
    after = _mapping_or_empty(after_value)
    before_count = _strict_nonnegative_int(before.get("row_count"))
    after_count = _strict_nonnegative_int(after.get("row_count"))
    before_rows = _mapping_or_empty(before.get("row_hashes"))
    after_rows = _mapping_or_empty(after.get("row_hashes"))
    if (
        before_count is None
        or after_count is None
        or after_count < before_count
        or len(before_rows) != before_count
        or len(after_rows) != after_count
        or not _is_acceptance_run_id(expected_run_id)
    ):
        return 0, False, None
    delta = after_count - before_count
    before_attribution = _mapping_or_empty(before_attribution_value)
    after_attribution = _mapping_or_empty(after_attribution_value)
    before_run_id = _optional_text(before_attribution.get("acceptance_run_id"))
    after_run_id = _optional_text(after_attribution.get("acceptance_run_id"))
    before_run_ids = set(_string_list(before_attribution.get("event_ids")))
    after_run_ids = set(_string_list(after_attribution.get("event_ids")))
    before_run_count = _strict_nonnegative_int(
        before_attribution.get("attributable_event_count")
    )
    after_run_count = _strict_nonnegative_int(after_attribution.get("attributable_event_count"))
    if (
        before_run_id != expected_run_id
        or after_run_id != expected_run_id
        or before_attribution.get("audit_user_identifier")
        != f"frontend-acceptance-{expected_run_id}"
        or after_attribution.get("audit_user_identifier")
        != f"frontend-acceptance-{expected_run_id}"
        or before_run_count != 0
        or before_run_ids
        or before_run_count != len(before_run_ids)
        or after_run_count != len(after_run_ids)
    ):
        return delta, False, after_run_id

    before_ids = set(before_rows)
    after_ids = set(after_rows)
    global_new_ids = after_ids - before_ids
    global_deleted_ids = before_ids - after_ids
    run_new_ids = after_run_ids - before_run_ids
    run_deleted_ids = before_run_ids - after_run_ids
    existing_rows_unchanged = all(
        after_rows.get(key) == value for key, value in before_rows.items()
    )
    attributable = (
        delta > 0
        and not global_deleted_ids
        and not run_deleted_ids
        and len(global_new_ids) == delta
        and len(run_new_ids) == after_run_count - before_run_count
        and global_new_ids == run_new_ids
        and existing_rows_unchanged
    )
    return delta, attributable, after_run_id


def _normalize_consistency(value: object, blocking: list[str]) -> dict[str, object]:
    mapping = _mapping_or_empty(value)
    before = _optional_text(mapping.get("database_snapshot_before"))
    after = _optional_text(mapping.get("database_snapshot_after"))
    concurrent = mapping.get("concurrent_activity_detected")
    if before is None or after is None or before != after or concurrent is not False:
        blocking.append("capture-concurrent-ambiguity")
    return {
        "database_snapshot_before": before,
        "database_snapshot_after": after,
        "concurrent_activity_detected": concurrent,
    }


def _classify_release_topology(value: object) -> tuple[str, dict[str, object]]:
    topology = _mapping_or_empty(value)
    evidence: dict[str, object] = {
        "current": _mapping_or_empty(topology.get("current")),
        "current_next": _mapping_or_empty(topology.get("current_next")),
        "releases_root": _mapping_or_empty(topology.get("releases_root")),
        "migration_sentinel": _mapping_or_empty(topology.get("migration_sentinel")),
        "migration_sentinel_next": _mapping_or_empty(topology.get("migration_sentinel_next")),
        "incoming_entries": _string_list(topology.get("incoming_entries")),
        "legacy_index": _mapping_or_empty(topology.get("legacy_index")),
        "deploy_marker": _mapping_or_empty(topology.get("deploy_marker")),
        "deploy_marker_next": _mapping_or_empty(topology.get("deploy_marker_next")),
        "release": _mapping_or_empty(topology.get("release")),
        "runtime": _mapping_or_empty(topology.get("runtime")),
    }
    current = cast(dict[str, object], evidence["current"])
    current_next = cast(dict[str, object], evidence["current_next"])
    releases_root = cast(dict[str, object], evidence["releases_root"])
    sentinel = cast(dict[str, object], evidence["migration_sentinel"])
    sentinel_next = cast(dict[str, object], evidence["migration_sentinel_next"])
    incoming = cast(list[str], evidence["incoming_entries"])
    legacy_index = cast(dict[str, object], evidence["legacy_index"])
    marker = cast(dict[str, object], evidence["deploy_marker"])
    marker_next = cast(dict[str, object], evidence["deploy_marker_next"])
    release = cast(dict[str, object], evidence["release"])
    runtime = cast(dict[str, object], evidence["runtime"])
    app_runtime = _mapping_or_empty(runtime.get("app_container"))
    nginx_runtime = _mapping_or_empty(runtime.get("nginx"))

    residue_free = (
        current_next.get("kind") == "absent"
        and sentinel_next.get("kind") == "absent"
        and marker_next.get("kind") == "absent"
        and incoming == []
    )
    marker_valid = marker.get("kind") == "regular_file" and _is_sha40(marker.get("sha"))
    runtime_ready = (
        app_runtime.get("status") == "running"
        and app_runtime.get("health") == "healthy"
        and app_runtime.get("deploy_sha") == marker.get("sha")
        and nginx_runtime.get("config_test") is True
        and nginx_runtime.get("web_mount_read_only") is True
        and _optional_text(nginx_runtime.get("web_mount_source"))
        == _optional_text(nginx_runtime.get("expected_web_root"))
    )
    legacy_ready = (
        current.get("kind") == "absent"
        and releases_root.get("kind") in {"absent", "directory"}
        and sentinel.get("kind") == "absent"
        and residue_free
        and legacy_index.get("kind") == "regular_file"
        and _is_sha256(legacy_index.get("sha256"))
        and marker_valid
        and runtime_ready
    )
    if legacy_ready:
        return "legacy_ready", evidence

    current_target = _optional_text(current.get("target"))
    current_match = CURRENT_TARGET_PATTERN.fullmatch(current_target or "")
    current_sha = current_match.group(1) if current_match else None
    sentinel_valid = sentinel.get("kind") == "regular_file" and _is_sha40(sentinel.get("sha"))
    versioned_ready = (
        current.get("kind") == "symlink"
        and current_sha is not None
        and releases_root.get("kind") == "directory"
        and residue_free
        and sentinel_valid
        and marker_valid
        and marker.get("sha") == current_sha
        and runtime_ready
        and release.get("kind") == "directory"
        and release.get("sha") == current_sha
        and release.get("manifest_format") == WEB_MANIFEST_FORMAT
        and release.get("manifest_source_sha") == current_sha
        and _is_sha256(release.get("manifest_sha256"))
    )
    if versioned_ready:
        return "versioned_ready", evidence
    return "partial_or_unknown", evidence


def _release_identity_fields(
    topology_name: str,
    evidence: Mapping[str, object],
) -> tuple[str | None, str | None, str | None]:
    if topology_name != "versioned_ready":
        return None, None, None
    current = _mapping_or_empty(evidence.get("current"))
    release = _mapping_or_empty(evidence.get("release"))
    return (
        _optional_text(current.get("target")),
        _optional_text(release.get("manifest_source_sha")),
        _optional_text(release.get("manifest_sha256")),
    )


def _normalize_schema(
    value: object,
    blocking: list[str],
) -> tuple[str | None, list[str], list[str]]:
    schema = _mapping_or_empty(value)
    fingerprint = _optional_text(schema.get("fingerprint"))
    tables = _string_list(schema.get("tables"))
    scope = _string_list(schema.get("scope"))
    if schema.get("algorithm") != "sha256" or not _is_sha256(fingerprint):
        blocking.append("schema-fingerprint-invalid")
    if set(tables) != set(ALLOWLISTED_TABLES) or len(tables) != len(ALLOWLISTED_TABLES):
        blocking.append("schema-table-allowlist-mismatch")
    if scope != list(SCHEMA_FINGERPRINT_SCOPE):
        blocking.append("schema-fingerprint-scope-invalid")
    return fingerprint, sorted(tables), scope


def _normalize_tables(value: object, blocking: list[str]) -> dict[str, object]:
    tables = _mapping_or_empty(value)
    if set(tables) != set(ALLOWLISTED_TABLES):
        blocking.append("business-table-allowlist-mismatch")
    normalized: dict[str, object] = {}
    for name in ALLOWLISTED_TABLES:
        row = _mapping_or_empty(tables.get(name))
        row_count = _strict_nonnegative_int(row.get("row_count"))
        fingerprint = _optional_text(row.get("primary_key_fingerprint"))
        row_content_fingerprint = _optional_text(row.get("row_content_fingerprint"))
        max_timestamp = _optional_text(row.get("max_timestamp"))
        valid = (
            row_count is not None
            and _is_sha256(fingerprint)
            and _is_sha256(row_content_fingerprint)
            and _is_timestamp_or_none(max_timestamp)
        )
        row_hashes: dict[str, object] | None = None
        if name == "audit_log_events":
            row_hashes = _mapping_or_empty(row.get("row_hashes"))
            row_ids = sorted(row_hashes)
            valid = (
                valid
                and row_count == len(row_hashes)
                and all(_optional_text(row_id) is not None for row_id in row_ids)
                and all(_is_sha256(row_hash) for row_hash in row_hashes.values())
                and fingerprint
                == hashlib.sha256(",".join(row_ids).encode("utf-8")).hexdigest()
            )
        if not valid:
            blocking.append(f"business-table-snapshot-invalid:{name}")
        normalized_row: dict[str, object] = {
            "row_count": row_count,
            "primary_key_fingerprint": fingerprint,
            "row_content_fingerprint": row_content_fingerprint,
            "max_timestamp": max_timestamp,
        }
        if row_hashes is not None:
            normalized_row["row_hashes"] = dict(sorted(row_hashes.items()))
        normalized[name] = normalized_row
    return normalized


def _normalize_observation_target(
    value: object,
    *,
    source: str,
    blocking: list[str],
) -> dict[str, object]:
    if source == "fixture":
        expected: dict[str, object] = {
            "format": OBSERVATION_TARGET_FORMAT,
            "kind": "fixture",
            "ssh_host": None,
        }
        if value is not None and _mapping_or_empty(value) != expected:
            blocking.append("fixture-observation-target-invalid")
        return expected
    observed = _mapping_or_empty(value)
    normalized: dict[str, object] = {
        "format": observed.get("format"),
        "kind": observed.get("kind"),
        "ssh_host": observed.get("ssh_host"),
        "remote_app_dir": observed.get("remote_app_dir"),
        "remote_web_dir": observed.get("remote_web_dir"),
        "postgres_container": observed.get("postgres_container"),
    }
    if normalized != {
        "format": OBSERVATION_TARGET_FORMAT,
        "kind": "production-ssh",
        "ssh_host": DEFAULT_SSH_HOST,
        "remote_app_dir": DEFAULT_REMOTE_APP_DIR,
        "remote_web_dir": DEFAULT_REMOTE_WEB_DIR,
        "postgres_container": DEFAULT_POSTGRES_CONTAINER,
    }:
        blocking.append("production-observation-target-invalid")
    return normalized


def _normalize_object_storage(value: object, blocking: list[str]) -> dict[str, object]:
    observed = _mapping_or_empty(value)
    status_value = _optional_text(observed.get("status"))
    if status_value == "not_observed":
        reason = _optional_text(observed.get("reason"))
        if reason is None:
            blocking.append("object-storage-not-observed-reason-missing")
        return {"status": "not_observed", "reason": reason}
    if status_value != "observed":
        blocking.append("object-storage-observation-invalid")
        return {"status": status_value or "unknown"}
    fingerprint = _optional_text(observed.get("fingerprint"))
    count = _strict_nonnegative_int(observed.get("object_count"))
    max_timestamp = _optional_text(observed.get("max_timestamp"))
    scope = _optional_text(observed.get("observation_scope"))
    if (
        count is None
        or not _is_sha256(fingerprint)
        or not _is_timestamp_or_none(max_timestamp)
        or scope != "database-ledger"
    ):
        blocking.append("object-storage-observation-invalid")
    result: dict[str, object] = {
        "status": "observed",
        "fingerprint": fingerprint,
        "object_count": count,
        "max_timestamp": max_timestamp,
        "observation_scope": scope,
    }
    return result


def _normalize_provider(
    value: object,
    blocking: list[str],
    *,
    source: str,
) -> dict[str, object]:
    provider = _mapping_or_empty(value)
    status_value = _optional_text(provider.get("status")) or "unknown"
    evidence_source = _optional_text(provider.get("evidence_source"))
    attempt_count = _strict_nonnegative_int(provider.get("attempt_count"))
    boundary = _mapping_or_empty(provider.get("guard_execution_boundary"))
    if status_value != "not_called" or attempt_count != 0:
        blocking.append("collector-provider-call-status-not-safe")
    if evidence_source != "collector-execution-boundary":
        blocking.append("provider-evidence-not-collector-derived")
    expected_protocol = (
        "fixture-controlled-json-v2"
        if source == "fixture"
        else LIVE_COLLECTOR_PROTOCOL
    )
    expected_command_count = 0 if source == "fixture" else 2
    expected_runtime_command_count = 0 if source == "fixture" else 8
    boundary_valid = (
        boundary.get("format") == EXECUTION_BOUNDARY_FORMAT
        and boundary.get("collector_protocol") == expected_protocol
        and boundary.get("allowed_operations") == list(LIVE_ALLOWED_OPERATIONS)
        and boundary.get("executed_postgresql_readonly_commands") == expected_command_count
        and boundary.get("executed_runtime_readonly_commands")
        == expected_runtime_command_count
        and boundary.get("rejected_command_count") == 0
        and boundary.get("collector_provider_endpoint_attempt_count") == 0
        and boundary.get("provider_environment_read") is False
        and boundary.get("secret_values_reported") is False
        and attempt_count == boundary.get("collector_provider_endpoint_attempt_count")
    )
    if not boundary_valid:
        blocking.append("provider-execution-boundary-invalid")
    return {
        "status": status_value,
        "evidence_source": evidence_source,
        "attempt_count": attempt_count,
        "execution_boundary": boundary,
    }


def _normalize_attribution(value: object, blocking: list[str]) -> dict[str, object] | None:
    if value is None:
        return None
    attribution = _mapping_or_empty(value)
    run_id = _optional_text(attribution.get("acceptance_run_id"))
    audit_user = _optional_text(attribution.get("audit_user_identifier"))
    count = _strict_nonnegative_int(attribution.get("attributable_event_count"))
    fingerprint = _optional_text(attribution.get("event_id_fingerprint"))
    event_ids = _string_list(attribution.get("event_ids"))
    unique_event_ids = sorted(set(event_ids))
    if (
        not _is_acceptance_run_id(run_id)
        or audit_user != f"frontend-acceptance-{run_id}"
        or count != len(event_ids)
        or len(unique_event_ids) != len(event_ids)
        or fingerprint
        != hashlib.sha256(",".join(unique_event_ids).encode("utf-8")).hexdigest()
    ):
        blocking.append("audit-attribution-invalid")
    return {
        "acceptance_run_id": run_id,
        "audit_user_identifier": audit_user,
        "attributable_event_count": count,
        "event_id_fingerprint": fingerprint,
        "event_ids": unique_event_ids,
    }


def _collect_live_fixture_local(
    *,
    expected_deploy_sha: str,
    remote_app_dir: Path,
    remote_web_dir: Path,
    postgres_container: str,
    acceptance_run_id: str | None,
    observation_target_host: str,
) -> dict[str, object]:
    if not _is_sha40(expected_deploy_sha):
        raise GuardError("expected deploy SHA must be 40 lowercase hex characters")
    if acceptance_run_id is not None and not _is_acceptance_run_id(acceptance_run_id):
        raise GuardError("acceptance run id is invalid")
    if observation_target_host != DEFAULT_SSH_HOST:
        raise GuardError("live collector production observation target is invalid")
    if (
        remote_app_dir != Path(DEFAULT_REMOTE_APP_DIR)
        or remote_web_dir != Path(DEFAULT_REMOTE_WEB_DIR)
        or postgres_container != DEFAULT_POSTGRES_CONTAINER
    ):
        raise GuardError("live collector scope is not the configured production scope")

    execution_boundary = _LiveExecutionBoundary(postgres_container=postgres_container)
    topology_before = _collect_release_topology(remote_app_dir, remote_web_dir)
    topology_before["runtime"] = _collect_runtime_topology(
        remote_web_dir=remote_web_dir,
        execution_boundary=execution_boundary,
    )
    database_before = _collect_database_snapshot(
        postgres_container=postgres_container,
        acceptance_run_id=acceptance_run_id,
        execution_boundary=execution_boundary,
    )
    topology_after = _collect_release_topology(remote_app_dir, remote_web_dir)
    topology_after["runtime"] = _collect_runtime_topology(
        remote_web_dir=remote_web_dir,
        execution_boundary=execution_boundary,
    )
    database_after = _collect_database_snapshot(
        postgres_container=postgres_container,
        acceptance_run_id=acceptance_run_id,
        execution_boundary=execution_boundary,
    )
    before_token = hashlib.sha256(
        _canonical_json({"topology": topology_before, "database": database_before}).encode("utf-8")
    ).hexdigest()
    after_token = hashlib.sha256(
        _canonical_json({"topology": topology_after, "database": database_after}).encode("utf-8")
    ).hexdigest()
    marker = _mapping_or_empty(topology_after.get("deploy_marker"))
    fixture: dict[str, object] = {
        "format": FIXTURE_FORMAT,
        "observation_target": {
            "format": OBSERVATION_TARGET_FORMAT,
            "kind": "production-ssh",
            "ssh_host": observation_target_host,
            "remote_app_dir": str(remote_app_dir),
            "remote_web_dir": str(remote_web_dir),
            "postgres_container": postgres_container,
        },
        "transaction_read_only": database_after.get("transaction_read_only"),
        "transaction_isolation": database_after.get("transaction_isolation"),
        "transaction_deferrable": database_after.get("transaction_deferrable"),
        "consistency": {
            "database_snapshot_before": before_token,
            "database_snapshot_after": after_token,
            "concurrent_activity_detected": (
                before_token != after_token
                or database_before.get("database_quiescent") is not True
                or database_after.get("database_quiescent") is not True
            ),
        },
        "release_topology": topology_after,
        "schema": database_after.get("schema"),
        "tables": database_after.get("tables"),
        "object_storage": database_after.get("object_storage"),
        "release_identity": {
            "expected_deploy_sha": expected_deploy_sha,
            "observed_deploy_sha": marker.get("sha"),
        },
        "provider": {
            "status": "not_called",
            "evidence_source": "collector-execution-boundary",
            "attempt_count": 0,
            "guard_execution_boundary": execution_boundary.report(),
        },
    }
    if database_after.get("audit_attribution") is not None:
        fixture["audit_attribution"] = database_after["audit_attribution"]
    return fixture


def _collect_release_topology(app_dir: Path, web_dir: Path) -> dict[str, object]:
    current = _path_state(web_dir / "current", symlink_target=True)
    current_next = _path_state(web_dir / "current.next", symlink_target=True)
    sentinel = _sha_marker_state(web_dir / ".versioned-release-migration-complete")
    sentinel_next = _sha_marker_state(web_dir / ".versioned-release-migration-complete.next")
    deploy_marker = _sha_marker_state(app_dir / ".deploy-sha")
    deploy_marker_next = _sha_marker_state(app_dir / ".deploy-sha.next")
    legacy_index = _hashed_regular_file_state(web_dir / "index.html")
    incoming: list[str] = []
    releases = web_dir / "releases"
    releases_root = _path_state(releases)
    if _is_regular_directory(releases):
        for child in releases.iterdir():
            if child.name.endswith((".incoming", ".incoming.owner", ".next")):
                incoming.append(f"releases/{child.name}")

    release: dict[str, object] = {"kind": "absent"}
    current_target = _optional_text(current.get("target"))
    match = CURRENT_TARGET_PATTERN.fullmatch(current_target or "")
    if match:
        sha = match.group(1)
        release_dir = releases / sha
        if _is_regular_directory(release_dir):
            manifest_path = release_dir / "release-manifest.json"
            manifest_state = _read_release_manifest(manifest_path)
            release = {
                "kind": "directory",
                "sha": sha,
                **manifest_state,
            }
        else:
            release = {"kind": "invalid", "sha": sha}
    return {
        "current": current,
        "current_next": current_next,
        "releases_root": releases_root,
        "migration_sentinel": sentinel,
        "migration_sentinel_next": sentinel_next,
        "incoming_entries": sorted(incoming),
        "legacy_index": legacy_index,
        "deploy_marker": deploy_marker,
        "deploy_marker_next": deploy_marker_next,
        "release": release,
    }


def _collect_runtime_topology(
    *,
    remote_web_dir: Path,
    execution_boundary: _LiveExecutionBoundary,
) -> dict[str, object]:
    app_state_command = [
        "docker",
        "inspect",
        APP_CONTAINER,
        "--format",
        "{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{end}}",
    ]
    app_state = execution_boundary.run_runtime_readonly(app_state_command)
    if app_state.returncode != 0:
        raise GuardError("application container readonly inspection failed")
    state_fields = app_state.stdout.strip().split("|")
    if len(state_fields) != 2:
        raise GuardError("application container readonly inspection is malformed")

    deploy_sha_command = [
        "docker",
        "exec",
        APP_CONTAINER,
        "sh",
        "-c",
        'printf "%s" "${MEDICAL_AUDIT_DEPLOY_SHA:-}"',
    ]
    deploy_sha = execution_boundary.run_runtime_readonly(deploy_sha_command)
    if deploy_sha.returncode != 0:
        raise GuardError("application deploy SHA readonly inspection failed")

    mount_command = [
        "docker",
        "inspect",
        NGINX_CONTAINER,
        "--format",
        (
            '{{range .Mounts}}{{if eq .Destination "/var/www/audit"}}'
            "{{.Source}}|{{.RW}}{{end}}{{end}}"
        ),
    ]
    mount = execution_boundary.run_runtime_readonly(mount_command)
    if mount.returncode != 0:
        raise GuardError("Nginx web mount readonly inspection failed")
    mount_fields = mount.stdout.strip().split("|")
    if len(mount_fields) != 2:
        raise GuardError("Nginx web mount readonly inspection is malformed")

    nginx_test = execution_boundary.run_runtime_readonly(
        ["docker", "exec", NGINX_CONTAINER, "nginx", "-t"]
    )
    return {
        "app_container": {
            "status": state_fields[0],
            "health": state_fields[1],
            "deploy_sha": deploy_sha.stdout.strip(),
        },
        "nginx": {
            "config_test": nginx_test.returncode == 0,
            "web_mount_source": mount_fields[0],
            "web_mount_read_only": mount_fields[1].lower() == "false",
            "expected_web_root": str(remote_web_dir),
        },
    }


def _collect_database_snapshot(
    *,
    postgres_container: str,
    acceptance_run_id: str | None,
    execution_boundary: _LiveExecutionBoundary,
) -> dict[str, object]:
    sql = _database_snapshot_sql(acceptance_run_id=acceptance_run_id)
    command = [
        "docker",
        "exec",
        postgres_container,
        "sh",
        "-c",
        'PGOPTIONS="-c default_transaction_read_only=on" '
        'psql -X -q -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" "$POSTGRES_DB" '
        "-At -F '|' -c \"$1\"",
        "medical-audit-release-guard",
        sql,
    ]
    completed = execution_boundary.run_postgresql_readonly(command)
    if completed.returncode != 0:
        raise GuardError(completed.stderr.strip() or "PostgreSQL readonly snapshot failed")
    return _parse_database_snapshot_output(
        completed.stdout,
        acceptance_run_id=acceptance_run_id,
    )


def _database_snapshot_sql(*, acceptance_run_id: str | None) -> str:
    quoted_tables = ", ".join(f"'{table}'" for table in ALLOWLISTED_TABLES)
    table_queries = "\n".join(
        (
            "SELECT 'TABLE', "
            f"'{table}', count(*)::text, "
            "encode(sha256(convert_to(COALESCE(string_agg(id::text, ',' ORDER BY id::text), "
            "''), 'UTF8')), 'hex'), "
            "encode(sha256(convert_to(COALESCE(string_agg("
            "encode(sha256(convert_to(to_jsonb(table_row)::text, 'UTF8')), 'hex'), "
            "',' ORDER BY id::text), ''), 'UTF8')), 'hex'), "
            f"COALESCE(max({_table_timestamp_expression(table)})::text, 'none') "
            f"FROM public.{table} AS table_row;"
        )
        for table in ALLOWLISTED_TABLES
    )
    attribution_query = ""
    if acceptance_run_id is not None:
        audit_user = f"frontend-acceptance-{acceptance_run_id}".replace("'", "''")
        attribution_query = (
            "SELECT 'ATTRIBUTION', count(*)::text, "
            "encode(sha256(convert_to(COALESCE(string_agg(id::text, ',' ORDER BY id::text), "
            "''), 'UTF8')), 'hex'), "
            "COALESCE(jsonb_agg(id::text ORDER BY id::text), '[]'::jsonb)::text "
            "FROM public.audit_log_events "
            f"WHERE user_identifier = '{audit_user}';"
        )
    return f"""
BEGIN TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY DEFERRABLE;
SELECT 'TX', current_setting('transaction_read_only'),
       current_setting('transaction_isolation'), current_setting('transaction_deferrable');
SELECT 'WAL_START', pg_current_wal_lsn()::text;
SELECT 'SCHEMA',
       encode(sha256(convert_to(
         COALESCE(string_agg(item, E'\\n' ORDER BY item), ''), 'UTF8'
       )), 'hex')
FROM (
  SELECT 'column:' || table_schema || '.' || table_name || '.' || column_name || ':' ||
         ordinal_position::text || ':' || data_type || ':' || is_nullable || ':' ||
         COALESCE(column_default, '') AS item
  FROM information_schema.columns
  WHERE table_schema = 'public' AND table_name IN ({quoted_tables})
  UNION ALL
  SELECT 'constraint:' || n.nspname || '.' || c.relname || '.' || con.conname || ':' ||
         pg_get_constraintdef(con.oid, true) AS item
  FROM pg_constraint con
  JOIN pg_class c ON c.oid = con.conrelid
  JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE n.nspname = 'public' AND c.relname IN ({quoted_tables})
  UNION ALL
  SELECT 'index:' || n.nspname || '.' || t.relname || '.' || i.relname || ':' ||
         pg_get_indexdef(i.oid)
  FROM pg_index ix
  JOIN pg_class t ON t.oid = ix.indrelid
  JOIN pg_class i ON i.oid = ix.indexrelid
  JOIN pg_namespace n ON n.oid = t.relnamespace
  WHERE n.nspname = 'public' AND t.relname IN ({quoted_tables})
  UNION ALL
  SELECT 'table-acl:' || n.nspname || '.' || c.relname || ':' || COALESCE(c.relacl::text, '')
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE n.nspname = 'public' AND c.relname IN ({quoted_tables})
  UNION ALL
  SELECT 'rls:' || n.nspname || '.' || c.relname || ':' ||
         c.relrowsecurity::text || ':' || c.relforcerowsecurity::text
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE n.nspname = 'public' AND c.relname IN ({quoted_tables})
  UNION ALL
  SELECT 'policy:' || n.nspname || '.' || c.relname || '.' || p.polname || ':' ||
         p.polcmd || ':' || p.polpermissive::text || ':' ||
         COALESCE((SELECT string_agg(
           CASE WHEN role_oid = 0 THEN 'PUBLIC' ELSE pg_get_userbyid(role_oid) END,
           ',' ORDER BY role_oid
         ) FROM unnest(p.polroles) AS role_ids(role_oid)), '') || ':' ||
         COALESCE(pg_get_expr(p.polqual, p.polrelid, true), '') || ':' ||
         COALESCE(pg_get_expr(p.polwithcheck, p.polrelid, true), '')
  FROM pg_policy p
  JOIN pg_class c ON c.oid = p.polrelid
  JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE n.nspname = 'public' AND c.relname IN ({quoted_tables})
  UNION ALL
  SELECT 'trigger:' || n.nspname || '.' || c.relname || '.' || tg.tgname || ':' ||
         pg_get_triggerdef(tg.oid, true)
  FROM pg_trigger tg
  JOIN pg_class c ON c.oid = tg.tgrelid
  JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE n.nspname = 'public' AND c.relname IN ({quoted_tables}) AND NOT tg.tgisinternal
  UNION ALL
  SELECT 'trigger-function:' || n.nspname || '.' || c.relname || '.' || tg.tgname || ':' ||
         pn.nspname || '.' || pr.proname || ':' || pg_get_functiondef(pr.oid)
  FROM pg_trigger tg
  JOIN pg_class c ON c.oid = tg.tgrelid
  JOIN pg_namespace n ON n.oid = c.relnamespace
  JOIN pg_proc pr ON pr.oid = tg.tgfoid
  JOIN pg_namespace pn ON pn.oid = pr.pronamespace
  WHERE n.nspname = 'public' AND c.relname IN ({quoted_tables}) AND NOT tg.tgisinternal
) AS schema_items;
SELECT 'SCHEMA_TABLES', COALESCE(string_agg(table_name, ',' ORDER BY table_name), '')
FROM information_schema.tables
WHERE table_schema = 'public' AND table_name IN ({quoted_tables});
{table_queries}
SELECT 'AUDIT_ROWS', COALESCE(jsonb_object_agg(
         id::text,
         encode(sha256(convert_to(to_jsonb(audit_row)::text, 'UTF8')), 'hex')
         ORDER BY id::text
       ), '{{}}'::jsonb)::text
FROM public.audit_log_events AS audit_row;
SELECT 'OBJECT', count(*)::text,
       encode(sha256(convert_to(COALESCE(string_agg(to_jsonb(object_row)::text, E'\\n'
         ORDER BY id::text), ''), 'UTF8')), 'hex'),
       COALESCE(max(updated_at)::text, 'none')
FROM public.document_storage_objects AS object_row;
{attribution_query}
SELECT 'WAL_END', pg_current_wal_lsn()::text;
COMMIT;
""".strip()


def _table_timestamp_expression(table: str) -> str:
    if table in UPDATED_AT_TABLES:
        return "GREATEST(created_at, updated_at)"
    return "created_at"


def _parse_database_snapshot_output(
    output: str,
    *,
    acceptance_run_id: str | None,
) -> dict[str, object]:
    transaction_read_only: str | None = None
    transaction_isolation: str | None = None
    transaction_deferrable: str | None = None
    wal_start: str | None = None
    wal_end: str | None = None
    schema_fingerprint: str | None = None
    schema_tables: list[str] = []
    tables: dict[str, object] = {}
    audit_row_hashes: dict[str, object] | None = None
    object_storage: dict[str, object] | None = None
    attribution_count: int | None = None
    attribution_fingerprint: str | None = None
    attribution_ids: list[str] | None = None
    singleton_tags: set[str] = set()
    for line in output.splitlines():
        fields = line.strip().split("|")
        if not fields or not fields[0]:
            continue
        tag = fields[0]
        if tag != "TABLE":
            if tag in singleton_tags:
                raise GuardError(f"duplicate PostgreSQL snapshot record: {tag}")
            singleton_tags.add(tag)
        if tag == "TX" and len(fields) == 4:
            transaction_read_only = fields[1]
            transaction_isolation = fields[2]
            transaction_deferrable = fields[3]
        elif tag == "WAL_START" and len(fields) == 2:
            wal_start = fields[1]
        elif tag == "WAL_END" and len(fields) == 2:
            wal_end = fields[1]
        elif tag == "SCHEMA" and len(fields) == 2:
            schema_fingerprint = fields[1]
        elif tag == "SCHEMA_TABLES" and len(fields) == 2:
            schema_tables = [item for item in fields[1].split(",") if item]
        elif tag == "TABLE" and len(fields) == 6:
            if fields[1] in tables:
                raise GuardError(f"duplicate PostgreSQL table snapshot: {fields[1]}")
            tables[fields[1]] = {
                "row_count": _parse_nonnegative_int(fields[2], label=f"{fields[1]} count"),
                "primary_key_fingerprint": fields[3],
                "row_content_fingerprint": fields[4],
                "max_timestamp": fields[5] if fields[5] else "none",
            }
        elif tag == "AUDIT_ROWS" and len(fields) == 2:
            audit_row_hashes = _load_json_text(
                fields[1], source="PostgreSQL audit row hash snapshot"
            )
        elif tag == "OBJECT" and len(fields) == 4:
            object_storage = {
                "status": "observed",
                "fingerprint": fields[2],
                "object_count": _parse_nonnegative_int(fields[1], label="object count"),
                "max_timestamp": fields[3] if fields[3] else "none",
                "observation_scope": "database-ledger",
            }
        elif tag == "ATTRIBUTION" and len(fields) == 4:
            attribution_count = _parse_nonnegative_int(fields[1], label="attribution count")
            attribution_fingerprint = fields[2]
            try:
                attribution_value = json.loads(fields[3])
            except json.JSONDecodeError as exc:
                raise GuardError("PostgreSQL audit attribution IDs are invalid JSON") from exc
            if not isinstance(attribution_value, list) or any(
                not isinstance(item, str) for item in attribution_value
            ):
                raise GuardError("PostgreSQL audit attribution IDs are invalid")
            attribution_ids = list(attribution_value)
        else:
            raise GuardError(f"unknown or malformed PostgreSQL snapshot record: {tag}")

    expected_singletons = {
        "TX",
        "WAL_START",
        "WAL_END",
        "SCHEMA",
        "SCHEMA_TABLES",
        "AUDIT_ROWS",
        "OBJECT",
    }
    if acceptance_run_id is not None:
        expected_singletons.add("ATTRIBUTION")
    if (
        singleton_tags != expected_singletons
        or transaction_read_only is None
        or transaction_isolation is None
        or transaction_deferrable is None
        or wal_start is None
        or wal_end is None
        or re.fullmatch(r"[0-9A-F]+/[0-9A-F]+", wal_start) is None
        or re.fullmatch(r"[0-9A-F]+/[0-9A-F]+", wal_end) is None
        or schema_fingerprint is None
        or set(tables) != set(ALLOWLISTED_TABLES)
        or audit_row_hashes is None
        or object_storage is None
    ):
        raise GuardError("PostgreSQL readonly snapshot output is incomplete")
    audit_row = _mapping_or_empty(tables.get("audit_log_events"))
    audit_row["row_hashes"] = audit_row_hashes
    tables["audit_log_events"] = audit_row
    result: dict[str, object] = {
        "transaction_read_only": transaction_read_only,
        "transaction_isolation": transaction_isolation,
        "transaction_deferrable": transaction_deferrable,
        "wal_lsn_start": wal_start,
        "wal_lsn_end": wal_end,
        "database_quiescent": wal_start == wal_end,
        "schema": {
            "algorithm": "sha256",
            "fingerprint": schema_fingerprint,
            "tables": schema_tables,
            "scope": list(SCHEMA_FINGERPRINT_SCOPE),
        },
        "tables": tables,
        "object_storage": object_storage,
        "audit_attribution": None,
    }
    if acceptance_run_id is not None:
        if (
            attribution_count is None
            or attribution_fingerprint is None
            or attribution_ids is None
        ):
            raise GuardError("PostgreSQL audit attribution output is incomplete")
        result["audit_attribution"] = {
            "acceptance_run_id": acceptance_run_id,
            "audit_user_identifier": f"frontend-acceptance-{acceptance_run_id}",
            "attributable_event_count": attribution_count,
            "event_id_fingerprint": attribution_fingerprint,
            "event_ids": attribution_ids,
        }
    return result


def _build_ssh_capture_command(
    *,
    ssh_key: Path,
    ssh_user: str,
    ssh_host: str,
    remote_script_path: str,
    phase: str,
    expected_deploy_sha: str,
    remote_app_dir: str = DEFAULT_REMOTE_APP_DIR,
    remote_web_dir: str = DEFAULT_REMOTE_WEB_DIR,
    postgres_container: str = DEFAULT_POSTGRES_CONTAINER,
    acceptance_run_id: str | None = None,
) -> list[str]:
    remote_args = [
        "python3",
        remote_script_path,
        "capture-live",
        "--phase",
        phase,
        "--expected-deploy-sha",
        expected_deploy_sha,
        "--remote-app-dir",
        remote_app_dir,
        "--remote-web-dir",
        remote_web_dir,
        "--postgres-container",
        postgres_container,
        "--observation-target-host",
        ssh_host,
        "--confirm-production-readonly",
        ssh_host,
    ]
    if acceptance_run_id is not None:
        remote_args.extend(("--acceptance-run-id", acceptance_run_id))
    return [
        "ssh",
        "-i",
        str(ssh_key),
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        "IdentitiesOnly=yes",
        f"{ssh_user}@{ssh_host}",
        shlex.join(remote_args),
    ]


def _run_ssh_capture(
    command: Sequence[str],
    *,
    ssh_host: str,
    ssh_user: str,
    phase: str,
    expected_deploy_sha: str,
) -> dict[str, object]:
    if ssh_host != DEFAULT_SSH_HOST or ssh_user != DEFAULT_SSH_USER:
        raise GuardError("SSH capture provenance target is not the configured production host")
    collector_source = _remote_capture_source()
    completed = subprocess.run(
        list(command),
        input=collector_source,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise GuardError(completed.stderr.strip() or "SSH release guard capture failed")
    fixture = _load_json_text(completed.stdout, source="SSH release guard output")
    payload = _capture_snapshot(
        fixture,
        phase=phase,
        expected_deploy_sha=expected_deploy_sha,
        source="ssh-live-readonly",
    )
    provenance: dict[str, object] = {
        "format": CAPTURE_PROVENANCE_FORMAT,
        "transport": "ssh-stdin",
        "ssh_host": ssh_host,
        "ssh_user": ssh_user,
        "batch_mode": True,
        "strict_host_key_checking": True,
        "identities_only": True,
        "ssh_exit_code": completed.returncode,
        "remote_app_dir": DEFAULT_REMOTE_APP_DIR,
        "remote_web_dir": DEFAULT_REMOTE_WEB_DIR,
        "postgres_container": DEFAULT_POSTGRES_CONTAINER,
        "collector_source_sha256": hashlib.sha256(
            collector_source.encode("utf-8")
        ).hexdigest(),
    }
    payload["capture_provenance"] = provenance
    payload["capture_envelope_id"] = hashlib.sha256(
        _canonical_json(
            {
                "snapshot_id": payload.get("snapshot_id"),
                "capture_provenance": provenance,
            }
        ).encode("utf-8")
    ).hexdigest()
    if not _capture_report_is_valid(payload):
        raise GuardError("SSH release guard returned an invalid snapshot contract")
    return payload


def _remote_capture_source() -> str:
    source_path = Path(__file__).resolve()
    if not source_path.is_file():
        raise GuardError("release guard source is unavailable for SSH capture")
    return source_path.read_text(encoding="utf-8")


def _ssh_command_plan(
    command: Sequence[str],
    *,
    phase: str,
    expected_deploy_sha: str,
) -> dict[str, object]:
    return {
        "format": FORMAT,
        "mode": "capture-command-only",
        "phase": phase,
        "status": "blocked",
        "expected_deploy_sha": expected_deploy_sha,
        "observed_deploy_sha": None,
        "provider_call_status": "not_observed",
        "provider_evidence_source": "outside-release-guard-scope",
        "collector_provider_call_status": "not_executed",
        "collector_provider_attempt_count": None,
        "database_write": False,
        "transaction_read_only": False,
        "snapshot_id": None,
        "execution": False,
        "command": shlex.join(command),
        "blocking_reasons": ["ssh-capture-not-executed"],
        "guard_execution_write": False,
        "capture_side_effect": "none",
    }


def _path_state(path: Path, *, symlink_target: bool = False) -> dict[str, object]:
    try:
        observed = path.lstat()
    except FileNotFoundError:
        return {"kind": "absent"}
    if stat.S_ISLNK(observed.st_mode):
        result: dict[str, object] = {"kind": "symlink"}
        if symlink_target:
            result["target"] = os.readlink(path)
        return result
    if stat.S_ISREG(observed.st_mode):
        return {"kind": "regular_file"}
    if stat.S_ISDIR(observed.st_mode):
        return {"kind": "directory"}
    return {"kind": "other"}


def _sha_marker_state(path: Path) -> dict[str, object]:
    state = _path_state(path)
    if state.get("kind") != "regular_file":
        return state
    try:
        content = _read_small_regular_file(path, maximum_bytes=128).decode("ascii").strip()
    except (GuardError, UnicodeDecodeError):
        return {"kind": "invalid"}
    return {"kind": "regular_file", "sha": content}


def _hashed_regular_file_state(path: Path) -> dict[str, object]:
    state = _path_state(path)
    if state.get("kind") != "regular_file":
        return state
    try:
        content = _read_small_regular_file(path, maximum_bytes=16 * 1024 * 1024)
    except GuardError:
        return {"kind": "invalid"}
    return {"kind": "regular_file", "sha256": hashlib.sha256(content).hexdigest()}


def _read_release_manifest(path: Path) -> dict[str, object]:
    try:
        content = _read_small_regular_file(path, maximum_bytes=16 * 1024 * 1024)
        payload = _load_json_text(content.decode("utf-8"), source=str(path))
    except (GuardError, UnicodeDecodeError):
        return {
            "manifest_format": None,
            "manifest_source_sha": None,
            "manifest_sha256": None,
        }
    return {
        "manifest_format": payload.get("format"),
        "manifest_source_sha": payload.get("source_sha"),
        "manifest_sha256": hashlib.sha256(content).hexdigest(),
    }


def _read_small_regular_file(path: Path, *, maximum_bytes: int) -> bytes:
    before = path.lstat()
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
        raise GuardError(f"not a regular file: {path}")
    if before.st_size > maximum_bytes:
        raise GuardError(f"file exceeds safe read limit: {path}")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        opened = os.fstat(descriptor)
        if opened.st_dev != before.st_dev or opened.st_ino != before.st_ino:
            raise GuardError(f"file changed before read: {path}")
        chunks: list[bytes] = []
        remaining = maximum_bytes + 1
        while remaining > 0:
            chunk = os.read(descriptor, min(1024 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        content = b"".join(chunks)
        after_open = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    after = path.lstat()
    if (
        len(content) > maximum_bytes
        or after_open.st_dev != after.st_dev
        or after_open.st_ino != after.st_ino
        or after_open.st_mtime_ns != after.st_mtime_ns
        or after_open.st_size != after.st_size
    ):
        raise GuardError(f"file changed during read: {path}")
    return content


def _is_regular_directory(path: Path) -> bool:
    try:
        observed = path.lstat()
    except FileNotFoundError:
        return False
    return stat.S_ISDIR(observed.st_mode) and not stat.S_ISLNK(observed.st_mode)


def _load_json_file(path: Path) -> dict[str, object]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise GuardError(f"cannot read JSON file: {path}") from exc
    return _load_json_text(text, source=str(path))


def _load_json_text(text: str, *, source: str) -> dict[str, object]:
    def object_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise GuardError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    try:
        payload = json.loads(text, object_pairs_hook=object_pairs)
    except json.JSONDecodeError as exc:
        raise GuardError(f"invalid JSON: {source}") from exc
    if not isinstance(payload, dict):
        raise GuardError(f"JSON root must be an object: {source}")
    return cast(dict[str, object], payload)


def _emit_report(report: Mapping[str, object], *, output: str) -> None:
    encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if output == "-":
        sys.stdout.write(encoded)
        return
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    next_path = path.with_name(f"{path.name}.{os.getpid()}.next")
    try:
        next_path.write_text(encoded, encoding="utf-8")
        os.replace(next_path, path)
    finally:
        next_path.unlink(missing_ok=True)
    print(json.dumps(_stdout_summary(report), ensure_ascii=False, sort_keys=True))


def _stdout_summary(report: Mapping[str, object]) -> dict[str, object]:
    return {
        "format": report.get("format"),
        "mode": report.get("mode"),
        "phase": report.get("phase"),
        "status": report.get("status"),
        "snapshot_id": report.get("snapshot_id"),
        "blocking_reasons": report.get("blocking_reasons"),
    }


def _mapping_or_empty(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items()}


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        return []
    return list(value)


def _optional_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _strict_nonnegative_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _parse_nonnegative_int(value: str, *, label: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise GuardError(f"invalid {label}") from exc
    if parsed < 0:
        raise GuardError(f"invalid {label}")
    return parsed


def _is_sha40(value: object) -> bool:
    return isinstance(value, str) and SHA40_PATTERN.fullmatch(value) is not None


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and SHA256_PATTERN.fullmatch(value) is not None


def _is_acceptance_run_id(value: object) -> bool:
    return isinstance(value, str) and ACCEPTANCE_RUN_ID_PATTERN.fullmatch(value) is not None


def _is_timestamp_or_none(value: str | None) -> bool:
    if value == "none":
        return True
    if value is None:
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _deduplicate(values: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _lower_evidence_grade(
    before: Mapping[str, object],
    after: Mapping[str, object],
) -> str:
    if (
        before.get("evidence_grade") == "L3-production-read-only"
        and after.get("evidence_grade") == "L3-production-read-only"
    ):
        return "L3-production-read-only"
    return "L2-fixture-or-dry-run"


if __name__ == "__main__":
    raise SystemExit(main())
