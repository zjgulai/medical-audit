from __future__ import annotations

from typing import Literal, TypedDict

from medical_audit_kb.core.config import DocumentUploadGovernanceSettings

DocumentUploadGovernanceProviderStage = Literal[
    "inactive",
    "local-test",
    "local-ruleset",
    "local-sidecar",
    "external-pending",
]
DocumentUploadGovernanceProviderCheckType = Literal["virus-scan", "dlp-review"]

_EXTERNAL_VIRUS_SCAN_PROVIDERS = frozenset({"tencent-ci-virus"})
_EXTERNAL_DLP_REVIEW_PROVIDERS = frozenset({"external-dlp"})
_LOCAL_RULESET_PROVIDERS = frozenset({"ruleset-v1"})
_LOCAL_SIDECAR_VIRUS_SCAN_PROVIDERS = frozenset({"clamav-sidecar"})


class DocumentUploadGovernanceProviderPreflightCheck(TypedDict):
    check_type: DocumentUploadGovernanceProviderCheckType
    provider: str
    stage: DocumentUploadGovernanceProviderStage
    external_provider_requested: bool
    local_validation_only: bool
    external_provider_call_implemented: bool
    result_writeback_supported: bool
    issues: list[str]


class DocumentUploadGovernanceProviderPreflightReport(TypedDict):
    status: Literal["pass", "blocked"]
    external_provider_requested: bool
    external_provider_call_performed: bool
    production_write_performed: bool
    result_writeback_supported: bool
    manual_index_approval_required: bool
    checks: list[DocumentUploadGovernanceProviderPreflightCheck]
    issues: list[str]


def document_upload_governance_provider_preflight_from_settings(
    settings: DocumentUploadGovernanceSettings,
    *,
    require_external_provider: bool = False,
) -> DocumentUploadGovernanceProviderPreflightReport:
    """Inspect governance-provider activation readiness without calling providers."""
    checks = [
        _provider_check(
            check_type="virus-scan",
            provider=settings.virus_scan_provider,
            external_providers=_EXTERNAL_VIRUS_SCAN_PROVIDERS,
            local_sidecar_providers=_LOCAL_SIDECAR_VIRUS_SCAN_PROVIDERS,
        ),
        _provider_check(
            check_type="dlp-review",
            provider=settings.dlp_review_provider,
            external_providers=_EXTERNAL_DLP_REVIEW_PROVIDERS,
            local_ruleset_providers=_LOCAL_RULESET_PROVIDERS,
        ),
    ]
    external_provider_requested = any(check["external_provider_requested"] for check in checks)
    issues = [issue for check in checks for issue in check["issues"]]
    if require_external_provider and not external_provider_requested:
        issues.append("external-governance-provider-not-configured")

    return {
        "status": "pass" if not issues else "blocked",
        "external_provider_requested": external_provider_requested,
        "external_provider_call_performed": False,
        "production_write_performed": False,
        "result_writeback_supported": True,
        "manual_index_approval_required": True,
        "checks": checks,
        "issues": issues,
    }


def _provider_check(
    *,
    check_type: DocumentUploadGovernanceProviderCheckType,
    provider: str,
    external_providers: frozenset[str],
    local_ruleset_providers: frozenset[str] = frozenset(),
    local_sidecar_providers: frozenset[str] = frozenset(),
) -> DocumentUploadGovernanceProviderPreflightCheck:
    if provider == "unconfigured":
        return {
            "check_type": check_type,
            "provider": provider,
            "stage": "inactive",
            "external_provider_requested": False,
            "local_validation_only": False,
            "external_provider_call_implemented": False,
            "result_writeback_supported": True,
            "issues": [],
        }
    if provider == "local-test":
        return {
            "check_type": check_type,
            "provider": provider,
            "stage": "local-test",
            "external_provider_requested": False,
            "local_validation_only": True,
            "external_provider_call_implemented": False,
            "result_writeback_supported": True,
            "issues": [],
        }
    if provider in local_ruleset_providers:
        return {
            "check_type": check_type,
            "provider": provider,
            "stage": "local-ruleset",
            "external_provider_requested": False,
            "local_validation_only": True,
            "external_provider_call_implemented": False,
            "result_writeback_supported": True,
            "issues": [],
        }
    if provider in local_sidecar_providers:
        return {
            "check_type": check_type,
            "provider": provider,
            "stage": "local-sidecar",
            "external_provider_requested": False,
            "local_validation_only": False,
            "external_provider_call_implemented": True,
            "result_writeback_supported": True,
            "issues": [],
        }
    if provider in external_providers:
        return {
            "check_type": check_type,
            "provider": provider,
            "stage": "external-pending",
            "external_provider_requested": True,
            "local_validation_only": False,
            "external_provider_call_implemented": False,
            "result_writeback_supported": True,
            "issues": [f"{check_type}-external-provider-call-not-implemented"],
        }
    return {
        "check_type": check_type,
        "provider": provider,
        "stage": "external-pending",
        "external_provider_requested": True,
        "local_validation_only": False,
        "external_provider_call_implemented": False,
        "result_writeback_supported": True,
        "issues": [f"{check_type}-provider-unsupported"],
    }
