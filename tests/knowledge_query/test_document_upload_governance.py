import json
import os
import subprocess
import sys
from pathlib import Path

from medical_audit_kb.api.document_upload_governance import (
    DocumentUploadGovernanceContext,
    apply_manual_index_decision,
    document_upload_governance_policy_from_settings,
    index_readiness_from_metadata,
)
from medical_audit_kb.api.document_upload_governance_preflight import (
    document_upload_governance_provider_preflight_from_settings,
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


def test_document_governance_provider_preflight_passes_for_default_inactive_state() -> None:
    report = document_upload_governance_provider_preflight_from_settings(
        DocumentUploadGovernanceSettings()
    )

    assert report["status"] == "pass"
    assert report["external_provider_requested"] is False
    assert report["external_provider_call_performed"] is False
    assert report["production_write_performed"] is False
    assert report["issues"] == []
    assert report["checks"][0]["stage"] == "inactive"
    assert report["checks"][1]["stage"] == "inactive"


def test_document_governance_provider_preflight_blocks_pending_external_calls() -> None:
    report = document_upload_governance_provider_preflight_from_settings(
        DocumentUploadGovernanceSettings(
            virus_scan_provider="tencent-ci-virus",
            dlp_review_provider="external-dlp",
        )
    )

    assert report["status"] == "blocked"
    assert report["external_provider_requested"] is True
    assert report["external_provider_call_performed"] is False
    assert report["production_write_performed"] is False
    assert report["result_writeback_supported"] is True
    assert report["manual_index_approval_required"] is True
    assert report["checks"][0]["stage"] == "external-pending"
    assert report["checks"][0]["external_provider_call_implemented"] is False
    assert report["checks"][1]["stage"] == "external-pending"
    assert report["checks"][1]["external_provider_call_implemented"] is False
    assert report["issues"] == [
        "virus-scan-external-provider-call-not-implemented",
        "dlp-review-external-provider-call-not-implemented",
    ]


def test_document_governance_provider_preflight_can_require_external_provider() -> None:
    report = document_upload_governance_provider_preflight_from_settings(
        DocumentUploadGovernanceSettings(),
        require_external_provider=True,
    )

    assert report["status"] == "blocked"
    assert report["external_provider_requested"] is False
    assert report["external_provider_call_performed"] is False
    assert report["production_write_performed"] is False
    assert report["issues"] == ["external-governance-provider-not-configured"]


def test_document_governance_provider_preflight_script_outputs_json(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "knowledge-query-engine-governance-provider.yaml"
    config_path.write_text(
        """
data_root: data/医保审核前期资料
index_root: tmp/knowledge-query-indexes
database_url: postgresql+psycopg://medical_audit_kb:medical_audit_kb_dev@localhost:5433/medical_audit_kb
model_provider:
  provider: openai
  api_key_env: OPENAI_API_KEY
  embedding_model: text-embedding-3-small
  rerank_model: null
  chat_model: gpt-4.1-mini
document_upload_governance:
  virus_scan_provider: tencent-ci-virus
  dlp_review_provider: external-dlp
source_collection_weights:
  medical-insurance-catalog: 1.25
  supervision-rules-knowledge: 1.35
  risk-negative-list: 1.1
  medical-insurance-laws: 1.0
""".strip(),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run-document-governance-provider-preflight.py",
            "--config",
            str(config_path),
        ],
        cwd=Path(__file__).resolve().parents[2],
        env=os.environ.copy(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 2
    report = json.loads(completed.stdout)
    assert report["status"] == "blocked"
    assert report["external_provider_requested"] is True
    assert report["external_provider_call_performed"] is False
    assert report["production_write_performed"] is False
    assert report["issues"] == [
        "virus-scan-external-provider-call-not-implemented",
        "dlp-review-external-provider-call-not-implemented",
    ]
