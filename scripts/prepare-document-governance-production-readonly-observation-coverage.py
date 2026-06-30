#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

DEFAULT_JSON_OUTPUT = (
    "tmp/outputs/document-governance-production-readonly-observation-coverage-latest.json"
)
DEFAULT_MARKDOWN_OUTPUT = (
    "tmp/outputs/document-governance-production-readonly-observation-coverage-latest.md"
)

REQUIRED_REPORT_FIELDS = [
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

EXISTING_SAFE_GET_ENDPOINTS = [
    {
        "name": "documents-page-html",
        "method": "GET",
        "path": "/documents",
        "used_by_existing_probe": True,
        "side_effect": "none_expected",
        "covers_fields": ["production_base_url"],
    },
    {
        "name": "documents-permissions",
        "method": "GET",
        "path": "/api/v1/documents/permissions",
        "used_by_existing_probe": True,
        "side_effect": "none_expected",
        "covers_fields": [],
    },
    {
        "name": "backend-health",
        "method": "GET",
        "path": "/api/backend/health",
        "used_by_existing_probe": True,
        "side_effect": "none_expected",
        "covers_fields": [],
    },
    {
        "name": "backend-search-backend",
        "method": "GET",
        "path": "/api/backend/index/search-backend",
        "used_by_existing_probe": True,
        "side_effect": "none_expected",
        "covers_fields": [],
    },
]

SIDE_EFFECT_BLOCKED_ENDPOINTS = [
    {
        "name": "document-upload-list",
        "method": "GET",
        "path": "/api/v1/documents/uploads",
        "blocked_reason": "route records document-upload-list audit operation",
        "would_cover_fields": ["document_upload_list_readonly_status"],
    },
    {
        "name": "document-upload-download",
        "method": "GET",
        "path": "/api/v1/documents/uploads/{upload_id}/download",
        "blocked_reason": "route records download or authorization-denied audit operation",
        "would_cover_fields": ["download_metadata_readonly_status"],
    },
]

WRITE_ENDPOINTS_OUT_OF_SCOPE = [
    {
        "name": "document-governance-result-writeback",
        "method": "POST",
        "path": "/api/v1/documents/uploads/{upload_id}/index-readiness/governance-result",
        "blocked_reason": "write-type governance E2E requires separate L4 authorization",
    },
    {
        "name": "document-upload",
        "method": "POST",
        "path": "/api/v1/documents/uploads",
        "blocked_reason": "object storage and document upload write require separate authorization",
    },
]

FIELD_COVERAGE: dict[str, tuple[str, str, str | None]] = {
    "production_base_url": (
        "observable_by_existing_probe",
        "documents-page-html records the target base URL in the existing report",
        "/documents",
    ),
    "expected_deploy_sha": (
        "not_observable_without_new_readonly_endpoint",
        "documents probe does not read deployment metadata or static manifest",
        None,
    ),
    "document_storage_provider": (
        "not_observable_without_new_readonly_endpoint",
        "no redacted document storage settings GET endpoint exists",
        None,
    ),
    "cos_bucket_status": (
        "not_observable_without_new_readonly_endpoint",
        "COS bucket must be reported as status only by a safe config endpoint",
        None,
    ),
    "cos_region_status": (
        "not_observable_without_new_readonly_endpoint",
        "COS region is not present in existing documents GET responses",
        None,
    ),
    "cos_prefix_status": (
        "not_observable_without_new_readonly_endpoint",
        "COS prefix is not present in existing documents GET responses",
        None,
    ),
    "cos_secret_id_env_name_status": (
        "not_observable_without_new_readonly_endpoint",
        "secret env name status needs a redacted settings endpoint",
        None,
    ),
    "cos_secret_key_env_name_status": (
        "not_observable_without_new_readonly_endpoint",
        "secret env name status needs a redacted settings endpoint",
        None,
    ),
    "cos_sdk_bootstrap_status": (
        "not_observable_without_new_readonly_endpoint",
        "COS SDK bootstrap switch is not exposed by existing GET responses",
        None,
    ),
    "record_storage_objects": (
        "not_observable_without_new_readonly_endpoint",
        "object record switch is not exposed by existing GET responses",
        None,
    ),
    "signed_url_ttl_seconds": (
        "not_observable_without_new_readonly_endpoint",
        "signed URL TTL is not exposed by existing GET responses",
        None,
    ),
    "object_retention_days": (
        "not_observable_without_new_readonly_endpoint",
        "object retention policy is not exposed by existing GET responses",
        None,
    ),
    "local_quarantine_retention_days": (
        "not_observable_without_new_readonly_endpoint",
        "local quarantine retention is not exposed by existing GET responses",
        None,
    ),
    "virus_scan_provider": (
        "not_observable_without_new_readonly_endpoint",
        "virus scan provider is not exposed by existing GET responses",
        None,
    ),
    "virus_scan_job_endpoint_env_status": (
        "not_observable_without_new_readonly_endpoint",
        "external job endpoint env status needs a redacted settings endpoint",
        None,
    ),
    "virus_scan_job_secret_env_status": (
        "not_observable_without_new_readonly_endpoint",
        "external job secret env status needs a redacted settings endpoint",
        None,
    ),
    "dlp_review_provider": (
        "not_observable_without_new_readonly_endpoint",
        "DLP provider is not exposed by existing GET responses",
        None,
    ),
    "dlp_review_job_endpoint_env_status": (
        "not_observable_without_new_readonly_endpoint",
        "external job endpoint env status needs a redacted settings endpoint",
        None,
    ),
    "dlp_review_job_secret_env_status": (
        "not_observable_without_new_readonly_endpoint",
        "external job secret env status needs a redacted settings endpoint",
        None,
    ),
    "redaction_rewrite_enabled": (
        "not_observable_without_new_readonly_endpoint",
        "redaction switch is not exposed by existing GET responses",
        None,
    ),
    "redaction_policy_version_status": (
        "not_observable_without_new_readonly_endpoint",
        "redaction policy version status needs a redacted settings endpoint",
        None,
    ),
    "redaction_manual_review_required": (
        "not_observable_without_new_readonly_endpoint",
        "manual review switch is not exposed by existing GET responses",
        None,
    ),
    "governance_audit_event_required": (
        "not_observable_without_new_readonly_endpoint",
        "audit event contract is not exposed by existing GET responses",
        None,
    ),
    "document_storage_objects_schema_ready": (
        "not_observable_without_schema_readonly_probe",
        "schema readiness needs a read-only schema probe or status endpoint",
        None,
    ),
    "document_upload_list_readonly_status": (
        "blocked_by_audit_log_side_effect",
        "GET /api/v1/documents/uploads records document-upload-list audit operation",
        "/api/v1/documents/uploads",
    ),
    "governance_readonly_endpoint_status": (
        "not_observable_without_new_readonly_endpoint",
        "no GET endpoint reports governance-result readiness without an upload id",
        None,
    ),
    "download_metadata_readonly_status": (
        "blocked_by_audit_log_side_effect",
        "GET download route records download or authorization-denied audit operation",
        "/api/v1/documents/uploads/{upload_id}/download",
    ),
    "audit_log_readonly_status": (
        "not_observable_without_audit_log_readonly_probe",
        "audit log status is outside the existing documents probe",
        None,
    ),
    "production_write": (
        "observable_by_boundary",
        "coverage gate and planned probe keep production_write=false",
        None,
    ),
    "provider_call": (
        "observable_by_boundary",
        "coverage gate and planned probe keep provider_call=false",
        None,
    ),
}


def main() -> int:
    args = _parse_args()
    report = build_coverage_report()
    _write_json(report, Path(args.json_output) if args.json_output else None)
    _write_markdown(report, Path(args.markdown_output) if args.markdown_output else None)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.fail_when_blocked and report["status"] == "blocked_missing_governance_readonly_surface":
        return 2
    return 0


def build_coverage_report() -> dict[str, Any]:
    fields = [_field_coverage(field) for field in REQUIRED_REPORT_FIELDS]
    summary = _coverage_summary(fields)
    blockers = _build_blockers(fields)
    return {
        "task": "document-governance-production-readonly-observation-coverage",
        "status": "blocked_missing_governance_readonly_surface" if blockers else "ready",
        "created_at": _now_iso(),
        "evidence_grade": "L2-fixture-or-dry-run",
        "coverage_summary": summary,
        "required_fields": fields,
        "existing_safe_get_endpoints": EXISTING_SAFE_GET_ENDPOINTS,
        "side_effect_blocked_endpoints": SIDE_EFFECT_BLOCKED_ENDPOINTS,
        "write_endpoints_out_of_scope": WRITE_ENDPOINTS_OUT_OF_SCOPE,
        "blocked_status_values": [
            "not_observable_without_new_readonly_endpoint",
            "not_observable_without_schema_readonly_probe",
            "not_observable_without_audit_log_readonly_probe",
            "blocked_by_audit_log_side_effect",
        ],
        "blockers": blockers,
        "next_contract_todo": [
            (
                "Add or identify a GET-only governance config/status endpoint that returns "
                "redacted statuses for storage, governance providers, redaction and audit "
                "event contract fields."
            ),
            (
                "Replace upload-list and download routes with safe metadata/status probes "
                "that do not record audit-log side effects."
            ),
            (
                "Keep write-type governance result, upload, object storage and provider "
                "checks behind separate authorization."
            ),
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
            "allowed_http_methods_for_future_probe": ["GET"],
            "non_get_http_methods_allowed": False,
        },
        "supported_claims": [
            "The current documents read-only probe coverage has been mapped field by field.",
            "The existing probe is insufficient for full P0-05 governance configuration L3.",
        ],
        "forbidden_claims": [
            "production document governance configuration has been observed",
            "the existing documents smoke fully satisfies the P0-05 required fields",
            "upload list or download metadata may be called as harmless read-only endpoints",
        ],
    }


def _field_coverage(field: str) -> dict[str, str | None]:
    status, rationale, endpoint = FIELD_COVERAGE[field]
    return {
        "field": field,
        "status": status,
        "rationale": rationale,
        "current_endpoint": endpoint,
    }


def _coverage_summary(fields: list[dict[str, str | None]]) -> dict[str, int]:
    summary: dict[str, int] = {"total": len(fields)}
    for item in fields:
        status = str(item["status"])
        summary[status] = summary.get(status, 0) + 1
    return summary


def _build_blockers(fields: list[dict[str, str | None]]) -> list[str]:
    blockers = [
        "governance-config-readonly-endpoint-missing",
        "document-upload-list-get-writes-audit-log",
        "download-metadata-get-writes-audit-log",
    ]
    for item in fields:
        status = str(item["status"])
        if status.startswith("not_observable") or status == "blocked_by_audit_log_side_effect":
            blockers.append(f"required-field-not-observable:{item['field']}")
    return blockers


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
    fields = "\n".join(
        f"- `{item['field']}`: `{item['status']}`"
        for item in report["required_fields"]
    )
    path.write_text(
        "\n".join(
            [
                "# Document Governance Production Readonly Observation Coverage",
                "",
                f"- status: `{report['status']}`",
                f"- evidence_grade: `{report['evidence_grade']}`",
                "- production_readonly_probe: `not_run`",
                "- production_env_write: `false`",
                "- object_storage_write: `false`",
                "- provider_call_status: `not_called`",
                "- external_governance_provider_call: `not_called`",
                "",
                "## Field Coverage",
                "",
                fields,
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
            "Map P0-05 production-readonly governance required fields to the current "
            "GET-only documents probe coverage. This is a local L2 coverage gate: it "
            "does not call production, the network, object storage, providers, or any "
            "non-GET endpoint."
        )
    )
    parser.add_argument("--json-output", default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--markdown-output", default=DEFAULT_MARKDOWN_OUTPUT)
    parser.add_argument("--fail-when-blocked", action="store_true")
    return parser.parse_args()


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


if __name__ == "__main__":
    raise SystemExit(main())
