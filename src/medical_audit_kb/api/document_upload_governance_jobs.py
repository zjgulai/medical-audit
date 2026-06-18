from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal, cast

from medical_audit_kb.api.document_upload_governance_store import (
    DocumentUploadGovernanceJobCreate,
    DocumentUploadGovernanceJobRequest,
    DocumentUploadGovernanceJobSubmission,
    DocumentUploadGovernanceJobSubmitter,
    DocumentUploadGovernanceJobType,
    DocumentUploadGovernanceStore,
)
from medical_audit_kb.core.config import DocumentUploadGovernanceSettings

DocumentUploadGovernanceJobSubmitterProvider = Literal["disabled", "local-recording"]


@dataclass(frozen=True, slots=True)
class LocalRecordingDocumentUploadGovernanceJobSubmitter:
    provider_env_contracts: dict[str, dict[str, str | None]] = field(default_factory=dict)
    mode: Literal["local-recording"] = "local-recording"

    def submit(
        self,
        request: DocumentUploadGovernanceJobRequest,
    ) -> DocumentUploadGovernanceJobSubmission:
        return DocumentUploadGovernanceJobSubmission(
            provider=request.provider,
            status="pending",
            external_job_id=f"local-recording-{request.job_type}-{request.upload_key}",
            result_payload={
                "submission_mode": self.mode,
                "external_provider_call_performed": False,
                "production_write_performed": False,
                "provider_env_contract": self.provider_env_contracts.get(
                    request.provider,
                    {},
                ),
            },
        )


def document_upload_governance_job_submitter_from_settings(
    settings: DocumentUploadGovernanceSettings,
) -> DocumentUploadGovernanceJobSubmitter | None:
    if settings.governance_job_submitter_provider == "disabled":
        return None
    return LocalRecordingDocumentUploadGovernanceJobSubmitter(
        provider_env_contracts=_provider_env_contracts(settings)
    )


def submit_required_document_upload_governance_jobs(
    *,
    upload: Mapping[str, object],
    index_readiness: Mapping[str, object],
    storage_objects: Sequence[Mapping[str, object]],
    store: DocumentUploadGovernanceStore,
    submitter: DocumentUploadGovernanceJobSubmitter,
) -> list[dict[str, object]]:
    upload_key = str(upload["id"])
    sha256 = str(upload["sha256"])
    object_key = _object_key_for_job(upload=upload, storage_objects=storage_objects)
    jobs: list[dict[str, object]] = []
    for check in _external_pending_checks(index_readiness):
        job_type = cast(DocumentUploadGovernanceJobType, check["check_type"])
        request = DocumentUploadGovernanceJobRequest(
            upload_key=upload_key,
            job_type=job_type,
            provider=str(check["provider"]),
            object_key=object_key,
            sha256=sha256,
            metadata={
                "source": "document-upload",
                "external_provider_call_performed": False,
                "production_write_performed": False,
            },
        )
        submission = submitter.submit(request)
        jobs.append(
            store.create_governance_job(
                DocumentUploadGovernanceJobCreate(
                    upload_key=upload_key,
                    job_type=job_type,
                    provider=submission.provider,
                    status=submission.status,
                    external_job_id=submission.external_job_id,
                    result_payload={
                        **submission.result_payload,
                        "request_metadata": request.metadata,
                    },
                    error_message=submission.error_message,
                )
            )
        )
    return jobs


def _external_pending_checks(
    index_readiness: Mapping[str, object],
) -> list[Mapping[str, object]]:
    checks = index_readiness.get("checks")
    if not isinstance(checks, list):
        return []
    return [
        check
        for check in checks
        if isinstance(check, dict)
        and check.get("check_type") in {"virus-scan", "dlp-review"}
        and check.get("result_code") == "pending-external-result"
    ]


def _object_key_for_job(
    *,
    upload: Mapping[str, object],
    storage_objects: Sequence[Mapping[str, object]],
) -> str:
    for storage_object in storage_objects:
        object_key = storage_object.get("object_key")
        if isinstance(object_key, str) and object_key:
            return object_key
    return str(upload["storage_path"])


def _provider_env_contracts(
    settings: DocumentUploadGovernanceSettings,
) -> dict[str, dict[str, str | None]]:
    contracts: dict[str, dict[str, str | None]] = {}
    if settings.virus_scan_provider not in {"unconfigured", "local-test"}:
        contracts[settings.virus_scan_provider] = {
            "endpoint_env": settings.virus_scan_job_endpoint_env,
            "secret_env": settings.virus_scan_job_secret_env,
        }
    if settings.dlp_review_provider not in {"unconfigured", "local-test", "ruleset-v1"}:
        contracts[settings.dlp_review_provider] = {
            "endpoint_env": settings.dlp_review_job_endpoint_env,
            "secret_env": settings.dlp_review_job_secret_env,
        }
    return contracts
