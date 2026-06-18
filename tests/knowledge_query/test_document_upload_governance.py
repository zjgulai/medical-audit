from medical_audit_kb.api.document_upload_governance import (
    DocumentUploadGovernanceContext,
    apply_manual_index_decision,
    document_upload_governance_policy_from_settings,
    index_readiness_from_metadata,
)
from medical_audit_kb.core.config import DocumentUploadGovernanceSettings


def test_index_readiness_preserves_async_job_fields() -> None:
    readiness = {
        "status": "blocked",
        "blockers": ["manual-index-approval-required"],
        "next_action": "complete-upload-governance",
        "checks": [
            {
                "check_type": "virus-scan",
                "provider": "tencent-ci-virus",
                "status": "passed",
                "blocker": None,
                "detail": "cloud virus scan accepted the object",
                "job_key": "document-governance-job-virus",
                "external_job_id": "ci-job-1",
                "result_code": "normal",
                "finished_at": "2026-06-16T12:00:00Z",
            },
            {
                "check_type": "dlp-review",
                "provider": "ruleset-v1",
                "status": "passed",
                "blocker": None,
                "detail": "ruleset found no high-risk finding",
                "job_key": "document-governance-job-dlp",
                "risk_level": "low",
                "result_code": "no-sensitive-marker",
                "finished_at": "2026-06-16T12:01:00Z",
            },
            {
                "check_type": "manual-index-approval",
                "provider": "manual",
                "status": "blocked",
                "blocker": "manual-index-approval-required",
                "detail": "manual approval is pending",
            },
        ],
    }

    normalized = index_readiness_from_metadata({"index_readiness": readiness})
    approved = apply_manual_index_decision(
        normalized,
        decision="approved",
        actor="head-1",
        note="准许进入后续入索引队列。",
    )

    assert normalized["checks"] == readiness["checks"]
    assert approved["status"] == "ready"
    assert approved["checks"][0]["job_key"] == "document-governance-job-virus"
    assert approved["checks"][0]["external_job_id"] == "ci-job-1"
    assert approved["checks"][1]["job_key"] == "document-governance-job-dlp"
    assert approved["checks"][1]["risk_level"] == "low"


def test_future_governance_providers_do_not_clear_blockers_in_phase_a() -> None:
    policy = document_upload_governance_policy_from_settings(
        DocumentUploadGovernanceSettings(
            virus_scan_provider="tencent-ci-virus",
            dlp_review_provider="ruleset-v1",
        )
    )
    readiness = policy.evaluate(
        DocumentUploadGovernanceContext.from_upload(
            file_name="policy.txt",
            extension="txt",
            content=b"policy evidence",
        )
    )

    assert readiness["status"] == "blocked"
    assert readiness["blockers"] == [
        "virus-scan-required",
        "dlp-review-required",
        "manual-index-approval-required",
    ]
    assert readiness["checks"][0]["provider"] == "tencent-ci-virus"
    assert readiness["checks"][0]["status"] == "blocked"
    assert readiness["checks"][1]["provider"] == "ruleset-v1"
    assert readiness["checks"][1]["status"] == "blocked"


def test_external_governance_providers_surface_pending_result_boundary() -> None:
    policy = document_upload_governance_policy_from_settings(
        DocumentUploadGovernanceSettings(
            virus_scan_provider="tencent-ci-virus",
            dlp_review_provider="external-dlp",
        )
    )
    readiness = policy.evaluate(
        DocumentUploadGovernanceContext.from_upload(
            file_name="patient-ledger.csv",
            extension="csv",
            content=b"patient_id,amount\np1,120.00\n",
        )
    )

    virus_check = readiness["checks"][0]
    dlp_check = readiness["checks"][1]
    assert readiness["status"] == "blocked"
    assert virus_check["provider"] == "tencent-ci-virus"
    assert virus_check["status"] == "blocked"
    assert virus_check["blocker"] == "virus-scan-required"
    assert virus_check["result_code"] == "pending-external-result"
    assert "not configured" not in virus_check["detail"]
    assert dlp_check["provider"] == "external-dlp"
    assert dlp_check["status"] == "blocked"
    assert dlp_check["blocker"] == "dlp-review-required"
    assert dlp_check["risk_level"] == "unknown"
    assert dlp_check["result_code"] == "pending-external-result"
    assert "not configured" not in dlp_check["detail"]
