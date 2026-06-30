#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from medical_audit_kb.api.document_upload_governance_preflight import (  # noqa: E402
    document_upload_governance_provider_preflight_from_settings,
)
from medical_audit_kb.api.document_upload_store import (  # noqa: E402
    tencent_cos_bootstrap_preflight_from_settings,
)
from medical_audit_kb.core.config import (  # noqa: E402
    DocumentStorageSettings,
    DocumentUploadGovernanceSettings,
    load_settings,
)

JsonObject = dict[str, object]

DEFAULT_JSON_OUTPUT = "tmp/outputs/document-governance-contract-readiness-latest.json"
DEFAULT_MARKDOWN_OUTPUT = "tmp/outputs/document-governance-contract-readiness-latest.md"

REDACTION_REWRITE_ENABLED_ENV = "MEDICAL_AUDIT_DOCUMENT_REDACTION_REWRITE_ENABLED"
REDACTION_POLICY_VERSION_ENV = "MEDICAL_AUDIT_DOCUMENT_REDACTION_POLICY_VERSION"
REDACTION_REVIEW_REQUIRED_ENV = "MEDICAL_AUDIT_DOCUMENT_REDACTION_REVIEW_REQUIRED"
GOVERNANCE_AUDIT_EVENT_REQUIRED_ENV = (
    "MEDICAL_AUDIT_DOCUMENT_GOVERNANCE_AUDIT_EVENT_REQUIRED"
)


@dataclass(frozen=True, slots=True)
class ReadinessConfig:
    config_path: Path | None
    qcloud_cos_available: bool | None
    require_external_dlp_provider: bool
    json_output: Path | None
    markdown_output: Path | None
    fail_when_blocked: bool


def main() -> int:
    args = _parse_args()
    config = ReadinessConfig(
        config_path=Path(args.config) if args.config else None,
        qcloud_cos_available=_sdk_availability_override(str(args.qcloud_cos_availability)),
        require_external_dlp_provider=bool(args.require_external_dlp_provider),
        json_output=Path(args.json_output) if args.json_output else None,
        markdown_output=Path(args.markdown_output) if args.markdown_output else None,
        fail_when_blocked=bool(args.fail_when_blocked),
    )
    settings = load_settings(config.config_path)
    report = build_readiness_report_from_settings(
        config,
        document_storage=settings.document_storage,
        document_governance=settings.document_upload_governance,
        environ=os.environ,
    )
    _write_json(report, config.json_output)
    _write_markdown(report, config.markdown_output)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if config.fail_when_blocked and report["status"] == "blocked":
        return 2
    return 0


def build_readiness_report_from_settings(
    config: ReadinessConfig,
    *,
    document_storage: DocumentStorageSettings,
    document_governance: DocumentUploadGovernanceSettings,
    environ: Mapping[str, str],
) -> JsonObject:
    cos_report = tencent_cos_bootstrap_preflight_from_settings(
        document_storage,
        environ=environ,
        qcloud_cos_available=config.qcloud_cos_available,
    )
    governance_report = document_upload_governance_provider_preflight_from_settings(
        document_governance,
        require_external_provider=False,
    )
    safe_env = _safe_contract_env(environ, document_storage)
    blockers = _build_blockers(
        document_storage=document_storage,
        cos_report=cos_report,
        governance_report=governance_report,
        environ=environ,
        require_external_dlp_provider=config.require_external_dlp_provider,
    )
    return {
        "task": "document-governance-contract-readiness",
        "status": "ready_for_readonly_governance_probe" if not blockers else "blocked",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "evidence_grade": "L2-fixture-or-dry-run",
        "cos_bootstrap_preflight": cos_report,
        "governance_provider_preflight": governance_report,
        "safe_env": safe_env,
        "blockers": blockers,
        "contract": {
            "object_storage": [
                "provider=tencent-cos",
                "COS bucket and region configured",
                "COS credentials referenced by env name only",
                "storage object records enabled",
                "short signed URL TTL",
                "object retention at least 180 days",
            ],
            "governance": [
                "virus scan provider is clamav-sidecar or approved external scanner",
                "DLP provider is ruleset-v1 or approved external DLP",
                "governance result writeback is supported",
                "manual index approval remains required",
            ],
            "redaction": [
                "redaction rewrite enabled",
                "versioned redaction policy configured",
                "manual review remains required after rewrite",
            ],
            "audit_events": [
                (
                    "governance updates, blockers, result writeback, downloads and "
                    "indexing actions are auditable"
                ),
            ],
        },
        "boundaries": {
            "production_side_effect": "none",
            "production_env_write": False,
            "network_call_status": "not_called",
            "external_governance_provider_call": "not_called",
            "object_storage_write": False,
            "provider_call_status": "not_called",
            "secret_values_reported": False,
            "authorized_write_e2e": "not_run",
        },
        "supported_claims": [
            "The document-governance contract is machine-readable and fail-closed.",
            "The report only inspects local config, env names and SET/UNSET status.",
        ],
        "forbidden_claims": [
            "enterprise object storage is active in production",
            "external DLP or virus provider has been called",
            "redaction rewrite is complete",
            "production write-type governance E2E has been authorized",
        ],
    }


def _build_blockers(
    *,
    document_storage: DocumentStorageSettings,
    cos_report: JsonObject,
    governance_report: JsonObject,
    environ: Mapping[str, str],
    require_external_dlp_provider: bool,
) -> list[str]:
    blockers: list[str] = []
    blockers.extend(f"cos:{issue}" for issue in _list_of_strings(cos_report.get("issues")))
    if not document_storage.record_storage_objects:
        blockers.append("document-storage-object-recording-disabled")
    if document_storage.signed_url_ttl_seconds > 300:
        blockers.append("document-signed-url-ttl-too-long")
    if document_storage.object_retention_days < 180:
        blockers.append("document-object-retention-too-short")
    if document_storage.local_quarantine_retention_days > 30:
        blockers.append("local-quarantine-retention-too-long")

    checks = _list_of_dicts(governance_report.get("checks"))
    virus_check = _check_by_type(checks, "virus-scan")
    dlp_check = _check_by_type(checks, "dlp-review")
    blockers.extend(
        f"governance:{issue}" for issue in _list_of_strings(governance_report.get("issues"))
    )
    if _provider_stage(virus_check) in {"inactive", "local-test"}:
        blockers.append("enterprise-virus-scan-provider-not-configured")
    if _provider_stage(dlp_check) in {"inactive", "local-test"}:
        blockers.append("enterprise-dlp-provider-not-configured")
    if require_external_dlp_provider and not bool(dlp_check.get("external_provider_requested")):
        blockers.append("external-dlp-provider-not-configured")
    if not bool(governance_report.get("result_writeback_supported")):
        blockers.append("governance-result-writeback-not-supported")
    if not bool(governance_report.get("manual_index_approval_required")):
        blockers.append("manual-index-approval-not-required")

    if not _truthy(_contract_env_value(environ, REDACTION_REWRITE_ENABLED_ENV)):
        blockers.append("redaction-rewrite-not-enabled")
    if not _contract_env_value(environ, REDACTION_POLICY_VERSION_ENV):
        blockers.append("redaction-policy-version-missing")
    if not _truthy(_contract_env_value(environ, REDACTION_REVIEW_REQUIRED_ENV)):
        blockers.append("redaction-manual-review-not-required")
    if not _truthy(_contract_env_value(environ, GOVERNANCE_AUDIT_EVENT_REQUIRED_ENV)):
        blockers.append("document-governance-audit-event-contract-missing")
    return blockers


def _safe_contract_env(
    environ: Mapping[str, str],
    document_storage: DocumentStorageSettings,
) -> JsonObject:
    env_names = (
        REDACTION_REWRITE_ENABLED_ENV,
        REDACTION_POLICY_VERSION_ENV,
        REDACTION_REVIEW_REQUIRED_ENV,
        GOVERNANCE_AUDIT_EVENT_REQUIRED_ENV,
    )
    safe: JsonObject = {
        name: _safe_env_item(environ, name) for name in env_names
    }
    referenced_secret_status: dict[str, str] = {}
    for name in (
        document_storage.cos_secret_id_env,
        document_storage.cos_secret_key_env,
    ):
        if name:
            referenced_secret_status[name] = "SET" if environ.get(name, "").strip() else "UNSET"
    safe["referenced_secret_status"] = referenced_secret_status
    return safe


def _safe_env_item(environ: Mapping[str, str], name: str) -> JsonObject:
    value = environ.get(name, "").strip()
    return {
        "status": "SET" if value else "UNSET",
    }


def _contract_env_value(environ: Mapping[str, str], name: str) -> str:
    return environ.get(name, "").strip()


def _provider_stage(check: JsonObject) -> str:
    return str(check.get("stage") or "inactive")


def _check_by_type(checks: list[JsonObject], check_type: str) -> JsonObject:
    for check in checks:
        if check.get("check_type") == check_type:
            return check
    return {}


def _list_of_dicts(value: object) -> list[JsonObject]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _list_of_strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _write_json(report: JsonObject, path: Path | None) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_markdown(report: JsonObject, path: Path | None) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    blockers = "\n".join(f"- `{item}`" for item in report["blockers"]) or "- none"
    path.write_text(
        "\n".join(
            [
                "# Document Governance Contract Readiness",
                "",
                f"- status: `{report['status']}`",
                f"- evidence_grade: `{report['evidence_grade']}`",
                "- production_side_effect: `none`",
                "- external_governance_provider_call: `not_called`",
                "- object_storage_write: `false`",
                "- secret_values_reported: `false`",
                "",
                "## Blockers",
                "",
                blockers,
                "",
            ]
        ),
        encoding="utf-8",
    )


def _sdk_availability_override(value: str) -> bool | None:
    if value == "available":
        return True
    if value == "missing":
        return False
    return None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fail-closed readiness audit for the P0-05 document-governance contract. "
            "The script reads local config and env names only; it performs no network "
            "call, object-storage write, external governance provider call, provider call, "
            "production write, or env write."
        )
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to a knowledge-query-engine YAML config. Defaults to configured app behavior.",
    )
    parser.add_argument(
        "--qcloud-cos-availability",
        choices=("auto", "available", "missing"),
        default="auto",
    )
    parser.add_argument(
        "--require-external-dlp-provider",
        action="store_true",
        help="Block unless the DLP provider is configured as an external DLP provider.",
    )
    parser.add_argument("--json-output", default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--markdown-output", default=DEFAULT_MARKDOWN_OUTPUT)
    parser.add_argument("--fail-when-blocked", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    sys.exit(main())
