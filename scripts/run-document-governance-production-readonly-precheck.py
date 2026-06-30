#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

READY_PROFILE_CONFIG = "configs/knowledge-query-engine-document-governance-ready-profile.yaml"
DEFAULT_JSON_OUTPUT = (
    "tmp/outputs/document-governance-production-readonly-precheck-latest.json"
)
DEFAULT_MARKDOWN_OUTPUT = (
    "tmp/outputs/document-governance-production-readonly-precheck-latest.md"
)
DEFAULT_READY_PROFILE_JSON_OUTPUT = (
    "tmp/outputs/document-governance-production-readonly-precheck-ready-profile-latest.json"
)
DEFAULT_READY_PROFILE_MARKDOWN_OUTPUT = (
    "tmp/outputs/document-governance-production-readonly-precheck-ready-profile-latest.md"
)
DEFAULT_PLAN_JSON_OUTPUT = (
    "tmp/outputs/document-governance-production-readonly-precheck-plan-latest.json"
)
DEFAULT_PLAN_MARKDOWN_OUTPUT = (
    "tmp/outputs/document-governance-production-readonly-precheck-plan-latest.md"
)


@dataclass(frozen=True, slots=True)
class PrecheckConfig:
    json_output: Path | None
    markdown_output: Path | None
    ready_profile_json_output: Path
    ready_profile_markdown_output: Path
    plan_json_output: Path
    plan_markdown_output: Path
    fail_when_blocked: bool


@dataclass(frozen=True, slots=True)
class CommandResult:
    name: str
    command: list[str]
    returncode: int
    stdout: str
    stderr: str


def main() -> int:
    args = _parse_args()
    config = PrecheckConfig(
        json_output=Path(args.json_output) if args.json_output else None,
        markdown_output=Path(args.markdown_output) if args.markdown_output else None,
        ready_profile_json_output=Path(args.ready_profile_json_output),
        ready_profile_markdown_output=Path(args.ready_profile_markdown_output),
        plan_json_output=Path(args.plan_json_output),
        plan_markdown_output=Path(args.plan_markdown_output),
        fail_when_blocked=bool(args.fail_when_blocked),
    )
    report = run_precheck(config)
    _write_json(report, config.json_output)
    _write_markdown(report, config.markdown_output)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if config.fail_when_blocked and report["status"] == "blocked":
        return 2
    return 0


def run_precheck(config: PrecheckConfig) -> dict[str, Any]:
    ready_result = _run_ready_profile(config)
    plan_result = _run_plan(config)
    ready_report = _load_json_file(config.ready_profile_json_output)
    plan_report = _load_json_file(config.plan_json_output)
    artifacts = _artifact_texts(config)
    blockers = _build_blockers(
        ready_result=ready_result,
        plan_result=plan_result,
        ready_report=ready_report,
        plan_report=plan_report,
        artifact_texts=artifacts,
    )
    return {
        "task": "document-governance-production-readonly-precheck",
        "status": "ready_for_manual_authorization_review" if not blockers else "blocked",
        "created_at": _now_iso(),
        "evidence_grade": "L2-fixture-or-dry-run",
        "child_reports": {
            "ready_profile": str(config.ready_profile_json_output),
            "production_readonly_plan": str(config.plan_json_output),
        },
        "checks": [
            _check_result(
                "ready-profile-dry-run",
                ready_result,
                ready_report,
                expected_status="ready_for_readonly_governance_probe",
            ),
            _check_result(
                "production-readonly-plan",
                plan_result,
                plan_report,
                expected_status="ready_for_production_readonly_plan_review",
            ),
            _authorization_package_check(plan_report),
        ],
        "manual_authorization_todo": _manual_authorization_todo(plan_report),
        "next_allowed_step": {
            "step": "request explicit production read-only probe approval",
            "target_evidence_grade": "L3-production-read-only",
            "must_reuse_report_fields": plan_report.get(
                "production_readonly_observation_spec", {}
            ).get("required_report_fields", []),
        },
        "still_forbidden_without_separate_approval": [
            "production env write",
            "object storage write",
            "document governance-result writeback",
            "external governance provider call",
            "answer provider smoke",
            "authorized write-type governance E2E",
        ],
        "blockers": blockers,
        "boundaries": {
            "production_side_effect": "none",
            "production_readonly_probe": "not_run",
            "production_env_write": False,
            "object_storage_write": False,
            "network_call_status": "not_called",
            "provider_call_status": "not_called",
            "external_governance_provider_call": "not_called",
            "authorized_write_e2e": "not_run",
            "secret_values_reported": False,
        },
        "supported_claims": [
            "The local ready-profile and production-readonly plan have been refreshed.",
            "The manual authorization package is ready for human review.",
            "The next evidence step is an explicitly approved production read-only probe.",
        ],
        "forbidden_claims": [
            "production document governance configuration has been observed by this precheck",
            "production env has been changed",
            "production read-only probe has run",
            "object storage write or governance-result writeback has run",
        ],
    }


def _run_ready_profile(config: PrecheckConfig) -> CommandResult:
    command = [
        sys.executable,
        str(REPO_ROOT / "scripts/audit-document-governance-contract-readiness.py"),
        "--config",
        READY_PROFILE_CONFIG,
        "--qcloud-cos-availability",
        "available",
        "--json-output",
        str(config.ready_profile_json_output),
        "--markdown-output",
        str(config.ready_profile_markdown_output),
    ]
    env = {
        **os.environ,
        "MEDICAL_AUDIT_DOCUMENT_READY_PROFILE_COS_SECRET_ID": "-".join(
            ["ready", "profile", "cos", "id", "sentinel"]
        ),
        "MEDICAL_AUDIT_DOCUMENT_READY_PROFILE_COS_SECRET_KEY": "-".join(
            ["ready", "profile", "cos", "key", "sentinel"]
        ),
    }
    return _run_command("ready-profile-dry-run", command, env=env)


def _run_plan(config: PrecheckConfig) -> CommandResult:
    command = [
        sys.executable,
        str(REPO_ROOT / "scripts/prepare-document-governance-production-readonly-plan.py"),
        "--ready-profile-report",
        str(config.ready_profile_json_output),
        "--json-output",
        str(config.plan_json_output),
        "--markdown-output",
        str(config.plan_markdown_output),
    ]
    return _run_command("production-readonly-plan", command)


def _run_command(
    name: str,
    command: list[str],
    *,
    env: dict[str, str] | None = None,
) -> CommandResult:
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    return CommandResult(
        name=name,
        command=command,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _build_blockers(
    *,
    ready_result: CommandResult,
    plan_result: CommandResult,
    ready_report: dict[str, Any],
    plan_report: dict[str, Any],
    artifact_texts: dict[str, str],
) -> list[str]:
    blockers: list[str] = []
    if ready_result.returncode != 0:
        blockers.append("ready-profile-command-failed")
    if plan_result.returncode != 0:
        blockers.append("production-readonly-plan-command-failed")
    if ready_report.get("status") != "ready_for_readonly_governance_probe":
        blockers.append("ready-profile-not-ready")
    if ready_report.get("evidence_grade") != "L2-fixture-or-dry-run":
        blockers.append("ready-profile-evidence-grade-unexpected")
    if plan_report.get("status") != "ready_for_production_readonly_plan_review":
        blockers.append("production-readonly-plan-not-ready")
    if plan_report.get("evidence_grade") != "L2-fixture-or-dry-run":
        blockers.append("production-readonly-plan-evidence-grade-unexpected")
    blockers.extend(_boundary_blockers("ready-profile", ready_report))
    blockers.extend(_boundary_blockers("production-readonly-plan", plan_report))
    blockers.extend(_authorization_blockers(plan_report))
    if _secret_markers_leaked(artifact_texts):
        blockers.append("secret-value-leakage-detected")
    return blockers


def _boundary_blockers(prefix: str, report: dict[str, Any]) -> list[str]:
    boundaries = _dict(report.get("boundaries"))
    expected = {
        "production_side_effect": "none",
        "production_env_write": False,
        "object_storage_write": False,
        "provider_call_status": "not_called",
        "secret_values_reported": False,
    }
    if prefix == "production-readonly-plan":
        expected["production_readonly_probe"] = "not_run"
        expected["network_call_status"] = "not_called"
        expected["external_governance_provider_call"] = "not_called"
        expected["authorized_write_e2e"] = "not_run"
    blockers: list[str] = []
    for key, value in expected.items():
        if boundaries.get(key) != value:
            blockers.append(f"{prefix}-boundary-{key}-unexpected")
    return blockers


def _authorization_blockers(plan_report: dict[str, Any]) -> list[str]:
    package = _dict(plan_report.get("production_configuration_authorization_package"))
    manual_inputs = _list_of_dicts(package.get("required_manual_inputs"))
    env_names = {str(item.get("env_name")) for item in manual_inputs}
    required = {
        "MEDICAL_AUDIT_DOCUMENT_STORAGE_COS_BUCKET",
        "MEDICAL_AUDIT_DOCUMENT_STORAGE_COS_REGION",
        "MEDICAL_AUDIT_DOCUMENT_STORAGE_RECORD_OBJECTS",
        "MEDICAL_AUDIT_DOCUMENT_REDACTION_POLICY_VERSION",
        "MEDICAL_AUDIT_DOCUMENT_GOVERNANCE_AUDIT_EVENT_REQUIRED",
    }
    blockers: list[str] = []
    missing = sorted(required - env_names)
    blockers.extend(f"authorization-env-missing:{env_name}" for env_name in missing)
    for item in manual_inputs:
        if item.get("value_status") != "manual-confirmation-required":
            blockers.append(f"authorization-value-status-unexpected:{item.get('env_name')}")
    if package.get("execution_status") != "not_authorized":
        blockers.append("authorization-package-execution-status-unexpected")
    return blockers


def _authorization_package_check(plan_report: dict[str, Any]) -> dict[str, Any]:
    package = _dict(plan_report.get("production_configuration_authorization_package"))
    manual_inputs = _list_of_dicts(package.get("required_manual_inputs"))
    return {
        "name": "manual-authorization-package",
        "passed": not _authorization_blockers(plan_report),
        "execution_status": package.get("execution_status"),
        "manual_input_count": len(manual_inputs),
        "env_names": [str(item.get("env_name")) for item in manual_inputs],
        "value_policy": package.get("value_policy"),
    }


def _check_result(
    name: str,
    result: CommandResult,
    report: dict[str, Any],
    *,
    expected_status: str,
) -> dict[str, Any]:
    return {
        "name": name,
        "passed": result.returncode == 0 and report.get("status") == expected_status,
        "command_returncode": result.returncode,
        "report_status": report.get("status"),
        "expected_status": expected_status,
        "evidence_grade": report.get("evidence_grade"),
        "stdout_json_parseable": _json_parseable(result.stdout),
        "stderr_empty": result.stderr == "",
    }


def _manual_authorization_todo(plan_report: dict[str, Any]) -> list[str]:
    package = _dict(plan_report.get("production_configuration_authorization_package"))
    rollback = _list_of_strings(package.get("rollback_requirements"))
    return [
        (
            "Review every production env name in the authorization package; record "
            "values elsewhere with redaction."
        ),
        "Confirm target Tencent COS bucket, region, prefix, object recording and retention policy.",
        (
            "Confirm redaction policy version, manual review switch and governance "
            "audit event requirement."
        ),
        "Record current deployment SHA, package checksum and redacted production env snapshot.",
        *rollback,
        "Approve the GET-only production read-only probe as a separate L3 step before execution.",
    ]


def _secret_markers_leaked(artifact_texts: dict[str, str]) -> bool:
    markers = {
        "-".join(["ready", "profile", "cos", "id", "sentinel"]),
        "-".join(["ready", "profile", "cos", "key", "sentinel"]),
    }
    return any(marker in text for marker in markers for text in artifact_texts.values())


def _artifact_texts(config: PrecheckConfig) -> dict[str, str]:
    paths = {
        "ready_profile_json": config.ready_profile_json_output,
        "ready_profile_markdown": config.ready_profile_markdown_output,
        "plan_json": config.plan_json_output,
        "plan_markdown": config.plan_markdown_output,
    }
    return {name: path.read_text(encoding="utf-8") for name, path in paths.items()}


def _load_json_file(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}


def _write_json(report: dict[str, Any], path: Path | None) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_markdown(report: dict[str, Any], path: Path | None) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    blockers = "\n".join(f"- `{item}`" for item in report["blockers"]) or "- none"
    todo = "\n".join(f"- {item}" for item in report["manual_authorization_todo"])
    path.write_text(
        "\n".join(
            [
                "# Document Governance Production Readonly Precheck",
                "",
                f"- status: `{report['status']}`",
                f"- evidence_grade: `{report['evidence_grade']}`",
                "- production_readonly_probe: `not_run`",
                "- production_env_write: `false`",
                "- object_storage_write: `false`",
                "- provider_call_status: `not_called`",
                "- external_governance_provider_call: `not_called`",
                "",
                "## Manual Authorization Todo",
                "",
                todo,
                "",
                "## Blockers",
                "",
                blockers,
                "",
            ]
        ),
        encoding="utf-8",
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Refresh local P0-05 ready-profile and production-readonly plan reports, "
            "then build a local manual-authorization precheck. This script performs no "
            "production read-only probe, production env write, network call, object "
            "storage write, or provider call."
        )
    )
    parser.add_argument("--json-output", default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--markdown-output", default=DEFAULT_MARKDOWN_OUTPUT)
    parser.add_argument(
        "--ready-profile-json-output",
        default=DEFAULT_READY_PROFILE_JSON_OUTPUT,
    )
    parser.add_argument(
        "--ready-profile-markdown-output",
        default=DEFAULT_READY_PROFILE_MARKDOWN_OUTPUT,
    )
    parser.add_argument("--plan-json-output", default=DEFAULT_PLAN_JSON_OUTPUT)
    parser.add_argument("--plan-markdown-output", default=DEFAULT_PLAN_MARKDOWN_OUTPUT)
    parser.add_argument("--fail-when-blocked", action="store_true")
    return parser.parse_args()


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_of_dicts(value: object) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _list_of_strings(value: object) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def _json_parseable(value: str) -> bool:
    try:
        json.loads(value)
    except json.JSONDecodeError:
        return False
    return True


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


if __name__ == "__main__":
    raise SystemExit(main())
