#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from medical_audit_kb.core.config import (  # noqa: E402
    DOCUMENT_GOVERNANCE_AUDIT_EVENT_REQUIRED_ENV,
    DOCUMENT_GOVERNANCE_REDACTION_POLICY_VERSION_ENV,
    DOCUMENT_GOVERNANCE_REDACTION_REVIEW_REQUIRED_ENV,
    DOCUMENT_GOVERNANCE_REDACTION_REWRITE_ENABLED_ENV,
    DOCUMENT_LOCAL_QUARANTINE_RETENTION_DAYS_ENV,
    DOCUMENT_OBJECT_RETENTION_DAYS_ENV,
    DOCUMENT_STORAGE_COS_BUCKET_ENV,
    DOCUMENT_STORAGE_COS_PREFIX_ENV,
    DOCUMENT_STORAGE_COS_REGION_ENV,
    DOCUMENT_STORAGE_COS_SDK_BOOTSTRAP_ENV,
    DOCUMENT_STORAGE_COS_SECRET_ID_NAME_ENV,
    DOCUMENT_STORAGE_COS_SECRET_KEY_NAME_ENV,
    DOCUMENT_STORAGE_PROVIDER_ENV,
    DOCUMENT_STORAGE_RECORD_OBJECTS_ENV,
    DOCUMENT_UPLOAD_DLP_REVIEW_JOB_ENDPOINT_NAME_ENV,
    DOCUMENT_UPLOAD_DLP_REVIEW_JOB_SECRET_NAME_ENV,
    DOCUMENT_UPLOAD_GOVERNANCE_JOB_SUBMITTER_PROVIDER_ENV,
    DOCUMENT_UPLOAD_VIRUS_SCAN_JOB_ENDPOINT_NAME_ENV,
    DOCUMENT_UPLOAD_VIRUS_SCAN_JOB_SECRET_NAME_ENV,
)

DEFAULT_JSON_OUTPUT = (
    "tmp/outputs/document-governance-production-readonly-plan-latest.json"
)
DEFAULT_MARKDOWN_OUTPUT = (
    "tmp/outputs/document-governance-production-readonly-plan-latest.md"
)
DEFAULT_READY_PROFILE_REPORT = (
    "tmp/outputs/document-governance-contract-readiness-ready-profile-latest.json"
)
DEFAULT_PRODUCTION_BASE_URL = "https://audit.lute-tlz-dddd.top"
DEFAULT_PROJECT_KEY = "SELF-CHECK-FUND-20260607"
DEFAULT_TENANT_ID = "hospital-demo"


def main() -> int:
    args = _parse_args()
    report = build_plan(
        production_base_url=str(args.production_base_url),
        expected_deploy_sha=str(args.expected_deploy_sha),
        ready_profile_report=str(args.ready_profile_report),
        tenant_id=str(args.tenant_id),
        project_key=str(args.project_key),
    )
    _write_json(report, Path(args.json_output) if args.json_output else None)
    _write_markdown(report, Path(args.markdown_output) if args.markdown_output else None)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def build_plan(
    *,
    production_base_url: str = DEFAULT_PRODUCTION_BASE_URL,
    expected_deploy_sha: str = "manual-input-required",
    ready_profile_report: str = DEFAULT_READY_PROFILE_REPORT,
    tenant_id: str = DEFAULT_TENANT_ID,
    project_key: str = DEFAULT_PROJECT_KEY,
) -> dict[str, Any]:
    readonly_report_path = "tmp/outputs/production-documents-readonly-latest.json"
    return {
        "task": "document-governance-production-readonly-plan",
        "status": "ready_for_production_readonly_plan_review",
        "created_at": _now_iso(),
        "evidence_grade": "L2-fixture-or-dry-run",
        "target": {
            "production_base_url": production_base_url.rstrip("/"),
            "expected_deploy_sha": expected_deploy_sha,
            "tenant_id": tenant_id,
            "project_key": project_key,
        },
        "evidence_layers": [
            {
                "name": "local-ready-profile-dry-run",
                "current_status": "rerunnable",
                "evidence_grade": "L2-fixture-or-dry-run",
                "command": ["pnpm", "document:governance-ready-profile"],
                "report": ready_profile_report,
                "expected_status": "ready_for_readonly_governance_probe",
                "production_state_claim": "not_supported",
            },
            {
                "name": "production-readonly-observation",
                "current_status": "not_run",
                "evidence_grade_after_execution": "L3-production-read-only",
                "command": [
                    "uv",
                    "run",
                    "python",
                    "scripts/run-production-documents-readonly-probe.py",
                    "--base-url",
                    production_base_url.rstrip("/"),
                    "--tenant-id",
                    tenant_id,
                    "--project-key",
                    project_key,
                    "--report",
                    readonly_report_path,
                ],
                "report": readonly_report_path,
                "write_boundary": (
                    "GET-only probe; audit-log-writing upload and download metadata "
                    "endpoints remain skipped"
                ),
            },
            {
                "name": "authorized-write-governance-e2e",
                "current_status": "not_authorized",
                "evidence_grade_after_execution": "L4-authorized-live",
                "requires": [
                    "fresh backup",
                    "explicit production-write confirmation",
                    "rollback point",
                    "post-write production read-only verification",
                ],
                "production_state_claim": "not_supported_until_executed",
            },
        ],
        "production_readonly_observation_spec": {
            "execution_status": "not_run",
            "allowed_http_methods": ["GET"],
            "disallowed_endpoints": [
                "/api/v1/documents/uploads",
                "/api/v1/documents/uploads/{upload_id}/download",
                "/api/v1/documents/uploads/{upload_id}/index-readiness/governance-result",
            ],
            "required_report_fields": _production_readonly_fields(),
            "minimum_pass_criteria": [
                "documents page returns expected product shell",
                "documents permissions endpoint returns auditor scope",
                "search backend is ready with active embeddings",
                "configured storage/governance statuses are reported as names or SET/UNSET only",
                "report boundaries state production_write=false and provider_call=false",
            ],
        },
        "production_configuration_authorization_package": {
            "execution_status": "not_authorized",
            "value_policy": "env names and SET/UNSET status only; never include credential values",
            "required_manual_inputs": _authorization_inputs(),
            "rollback_requirements": [
                "current deployment SHA and package checksum recorded",
                "current production env snapshot recorded with values redacted",
                "object storage bucket/prefix rollback or quarantine decision recorded",
                "database migration and object-record rollback path recorded before write E2E",
            ],
        },
        "next_evidence": [
            {
                "step": "run local ready-profile before production work",
                "raises_to": "L2-fixture-or-dry-run",
                "authorization_required": False,
            },
            {
                "step": "run production documents read-only observation",
                "raises_to": "L3-production-read-only",
                "authorization_required": "read-only production probe approval",
            },
            {
                "step": "prepare production env write request",
                "raises_to": "manual-review-only",
                "authorization_required": "owner approval before any env write",
            },
            {
                "step": "run write-type governance E2E",
                "raises_to": "L4-authorized-live",
                "authorization_required": (
                    "fresh backup, rollback point and explicit production-write "
                    "confirmation"
                ),
            },
        ],
        "blockers": [
            "production-readonly-not-run",
            "production-env-write-not-authorized",
            "authorized-write-e2e-not-authorized",
            "provider-smoke-not-authorized",
        ],
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
            (
                "The next production read-only evidence fields and authorization "
                "boundaries are machine-readable."
            ),
            "The local ready-profile dry-run remains separate from production observation.",
        ],
        "forbidden_claims": [
            "production document governance configuration has been observed in this run",
            "production env has been changed",
            "object storage write or governance-result writeback has been executed",
            "external governance provider or answer provider has been called",
        ],
    }


def _production_readonly_fields() -> list[str]:
    return [
        "production_base_url",
        "expected_deploy_sha",
        "document_storage_provider",
        "cos_bucket_status",
        "cos_region_status",
        "cos_prefix_status",
        "cos_secret_id_env_name_status",
        "cos_secret_key_env_name_status",
        "cos_sdk_bootstrap_status",
        "record_storage_objects",
        "signed_url_ttl_seconds",
        "object_retention_days",
        "local_quarantine_retention_days",
        "virus_scan_provider",
        "virus_scan_job_endpoint_env_status",
        "virus_scan_job_secret_env_status",
        "dlp_review_provider",
        "dlp_review_job_endpoint_env_status",
        "dlp_review_job_secret_env_status",
        "redaction_rewrite_enabled",
        "redaction_policy_version_status",
        "redaction_manual_review_required",
        "governance_audit_event_required",
        "document_storage_objects_schema_ready",
        "document_upload_list_readonly_status",
        "governance_readonly_endpoint_status",
        "download_metadata_readonly_status",
        "audit_log_readonly_status",
        "production_write",
        "provider_call",
    ]


def _authorization_inputs() -> list[dict[str, str]]:
    return [
        _env_input(DOCUMENT_STORAGE_PROVIDER_ENV, "target document storage provider"),
        _env_input(DOCUMENT_STORAGE_COS_BUCKET_ENV, "target Tencent COS bucket"),
        _env_input(DOCUMENT_STORAGE_COS_REGION_ENV, "target Tencent COS region"),
        _env_input(DOCUMENT_STORAGE_COS_PREFIX_ENV, "target Tencent COS prefix"),
        _env_input(DOCUMENT_STORAGE_COS_SECRET_ID_NAME_ENV, "COS secret id env name"),
        _env_input(DOCUMENT_STORAGE_COS_SECRET_KEY_NAME_ENV, "COS secret key env name"),
        _env_input(DOCUMENT_STORAGE_COS_SDK_BOOTSTRAP_ENV, "COS SDK bootstrap switch"),
        _env_input(DOCUMENT_STORAGE_RECORD_OBJECTS_ENV, "storage object record switch"),
        _env_input(DOCUMENT_OBJECT_RETENTION_DAYS_ENV, "object retention days"),
        _env_input(DOCUMENT_LOCAL_QUARANTINE_RETENTION_DAYS_ENV, "local quarantine retention days"),
        _env_input(
            DOCUMENT_UPLOAD_GOVERNANCE_JOB_SUBMITTER_PROVIDER_ENV,
            "governance job submitter provider",
        ),
        _env_input(
            DOCUMENT_UPLOAD_VIRUS_SCAN_JOB_ENDPOINT_NAME_ENV,
            "virus scan endpoint env name",
        ),
        _env_input(
            DOCUMENT_UPLOAD_VIRUS_SCAN_JOB_SECRET_NAME_ENV,
            "virus scan credential env name",
        ),
        _env_input(DOCUMENT_UPLOAD_DLP_REVIEW_JOB_ENDPOINT_NAME_ENV, "DLP endpoint env name"),
        _env_input(DOCUMENT_UPLOAD_DLP_REVIEW_JOB_SECRET_NAME_ENV, "DLP credential env name"),
        _env_input(DOCUMENT_GOVERNANCE_REDACTION_REWRITE_ENABLED_ENV, "redaction rewrite switch"),
        _env_input(DOCUMENT_GOVERNANCE_REDACTION_POLICY_VERSION_ENV, "redaction policy version"),
        _env_input(
            DOCUMENT_GOVERNANCE_REDACTION_REVIEW_REQUIRED_ENV,
            "redaction manual review switch",
        ),
        _env_input(
            DOCUMENT_GOVERNANCE_AUDIT_EVENT_REQUIRED_ENV,
            "governance audit event contract switch",
        ),
    ]


def _env_input(env_name: str, purpose: str) -> dict[str, str]:
    return {
        "env_name": env_name,
        "purpose": purpose,
        "value_status": "manual-confirmation-required",
        "reporting_policy": "report env name and SET/UNSET status only",
    }


def _write_json(report: dict[str, Any], path: Path | None) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_markdown(report: dict[str, Any], path: Path | None) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    blockers = "\n".join(f"- `{item}`" for item in report["blockers"])
    readonly_spec = report["production_readonly_observation_spec"]
    fields = "\n".join(f"- `{field}`" for field in readonly_spec["required_report_fields"])
    path.write_text(
        "\n".join(
            [
                "# Document Governance Production Readonly Plan",
                "",
                f"- status: `{report['status']}`",
                f"- evidence_grade: `{report['evidence_grade']}`",
                "- production_side_effect: `none`",
                "- production_readonly_probe: `not_run`",
                "- production_env_write: `false`",
                "- object_storage_write: `false`",
                "- provider_call_status: `not_called`",
                "- external_governance_provider_call: `not_called`",
                "",
                "## Required Production Readonly Fields",
                "",
                fields,
                "",
                "## Blockers Before Higher Evidence",
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
            "Prepare the P0-05 document-governance production read-only plan. "
            "This script writes local plan files only; it does not read production env, "
            "call the network, write object storage, call providers, or execute a "
            "production read-only probe."
        )
    )
    parser.add_argument("--production-base-url", default=DEFAULT_PRODUCTION_BASE_URL)
    parser.add_argument("--expected-deploy-sha", default="manual-input-required")
    parser.add_argument("--tenant-id", default=DEFAULT_TENANT_ID)
    parser.add_argument("--project-key", default=DEFAULT_PROJECT_KEY)
    parser.add_argument("--ready-profile-report", default=DEFAULT_READY_PROFILE_REPORT)
    parser.add_argument("--json-output", default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--markdown-output", default=DEFAULT_MARKDOWN_OUTPUT)
    return parser.parse_args()


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


if __name__ == "__main__":
    raise SystemExit(main())
