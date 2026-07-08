from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from medical_audit_kb.api.app import ApiState, create_app
from medical_audit_kb.api.review_task_store import InMemoryReviewTaskStore
from medical_audit_kb.core.config import (
    REQUIRED_COLLECTIONS,
    KnowledgeQuerySettings,
    ModelProviderSettings,
)

AUTH_HEADERS = {
    "X-User-Id": "auditor-1",
    "X-Role": "member",
    "X-Tenant-Id": "hospital-demo",
}


def test_medical_audit_review_task_create_and_status_update(tmp_path: Path) -> None:
    state = _workflow_state(tmp_path)
    client = TestClient(create_app(state))

    create_response = client.post(
        "/api/v1/audit-findings/finding-001/review-task",
        json={"assigned_to": "审计员A", "note": "从页面创建"},
        headers=AUTH_HEADERS,
    )

    assert create_response.status_code == 200
    create_body = create_response.json()
    assert create_body["status"] == "created"
    assert create_body["task"]["task_id"] == "review-task-0001"
    assert create_body["finding"]["review_task_id"] == "review-task-0001"
    assert state.operation_logs[-1]["action"] == "medical-audit-review-task-create"

    update_response = client.post(
        "/api/v1/audit-findings/finding-001/review-status",
        json={
            "status": "confirmed-violation",
            "assigned_to": "审计员A",
            "reviewer_note": "已核对明细与规则依据。",
            "conclusion": "确认违规，进入报告草稿。",
        },
        headers=AUTH_HEADERS,
    )

    assert update_response.status_code == 200
    update_body = update_response.json()
    assert update_body["status"] == "updated"
    assert update_body["task"]["status"] == "confirmed-violation"
    assert update_body["finding"]["review_status"] == "confirmed-violation"
    assert update_body["synced_findings"][0]["finding_key"] == "finding-001"


def test_medical_audit_import_supplement_and_report_entry(tmp_path: Path) -> None:
    state = _workflow_state(tmp_path)
    client = TestClient(create_app(state))

    preflight_response = client.post(
        "/api/v1/audit-findings/import-preflight",
        json={
            "template_id": "table1",
            "template_name": "医保费用汇总表",
            "file_name": "表1.xlsx",
            "row_count": 12,
        },
        headers=AUTH_HEADERS,
    )

    assert preflight_response.status_code == 200
    assert preflight_response.json()["status"] == "preflight_recorded"

    supplement_response = client.post(
        "/api/v1/audit-findings/finding-001/supplemental-material",
        json={
            "title": "HIS 明细截图",
            "locator": "charge_detail:C001",
            "note": "等待正式文件上传。",
        },
        headers=AUTH_HEADERS,
    )

    assert supplement_response.status_code == 200
    supplement_body = supplement_response.json()
    assert supplement_body["status"] == "registered"
    assert supplement_body["attachment"]["title"] == "HIS 明细截图"

    report_response = client.post(
        "/api/v1/audit-findings/finding-001/report-entry",
        json={
            "report_title": "finding-001 医保审计报告草稿",
            "summary": "纳入报告草稿。",
            "rectification_request": "请责任科室补充收费依据。",
            "owner_confirmed_by": "审计科负责人",
        },
        headers=AUTH_HEADERS,
    )

    assert report_response.status_code == 200
    report_body = report_response.json()
    assert report_body["status"] == "added"
    assert report_body["task"]["status"] == "confirmed-violation"
    assert report_body["task"]["dossier"]["workpaper"]["status"] == "ready"
    assert report_body["task"]["dossier"]["owner_signoff"]["status"] == "approved"
    assert report_body["finding"]["review_status"] == "confirmed-violation"


class FakeAuditFindingStore:
    def __init__(self) -> None:
        self.items: dict[str, dict[str, object]] = {
            "finding-001": {
                "finding_key": "finding-001",
                "status": "open",
                "finding_type": "charge-rule",
                "severity": "medium",
                "review_status": "pending-review",
                "review_task_id": None,
                "source_record_locator": {"source_table": "charge_detail", "id": "C001"},
                "calculation_trace": {"total_amount": "80.00"},
                "metadata": {"department": "骨科"},
                "created_at": "2026-07-08T01:00:00Z",
                "updated_at": "2026-07-08T01:00:00Z",
                "audit_run_key": "audit-run-001",
                "audit_task_key": "audit-task-001",
                "rule_key": "CHARGE-RULE-001",
                "rule_version_key": "CHARGE-RULE-001@v1",
                "evidence_items": [
                    {
                        "evidence_type": "rule-hit",
                        "chunk_id": None,
                        "source_package_version_key": None,
                        "index_version_key": None,
                        "citation_id": "E-001",
                        "locator": {"source": "charge_detail"},
                        "snippet": "同一就诊同一项目重复收费。",
                        "metadata": {},
                        "created_at": "2026-07-08T01:00:00Z",
                    }
                ],
            }
        }

    def list_findings(
        self,
        *,
        review_status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, object]]:
        findings = list(self.items.values())
        if review_status is not None:
            findings = [item for item in findings if item.get("review_status") == review_status]
        return [dict(item) for item in findings[:limit]]

    def generation_readiness(self) -> dict[str, object]:
        return {
            "status": "generated",
            "ready": True,
            "has_findings": True,
            "table_counts": {"audit_findings": len(self.items)},
            "prerequisites": [],
            "blocking_reasons": [],
            "next_actions": [],
        }

    def get_finding(self, finding_key: str) -> dict[str, object]:
        if finding_key not in self.items:
            raise KeyError(finding_key)
        return dict(self.items[finding_key])

    def link_review_task(self, finding_key: str, review_task_external_id: str) -> dict[str, object]:
        finding = self.items[finding_key]
        finding["review_task_id"] = review_task_external_id
        finding["review_status"] = "pending-review"
        return dict(finding)

    def sync_review_task_status(
        self,
        review_task_external_id: str,
        review_status: str,
    ) -> list[dict[str, object]]:
        updated: list[dict[str, object]] = []
        for finding in self.items.values():
            if finding.get("review_task_id") == review_task_external_id:
                finding["review_status"] = review_status
                updated.append(dict(finding))
        return updated


class FakeAuditLogStore:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    def add_event(self, action: str, payload: dict[str, object]) -> dict[str, object]:
        event = {
            "event_id": f"event-{len(self.events) + 1:03d}",
            "action": action,
            "payload": dict(payload),
        }
        self.events.append(event)
        return event

    def list_events(self, **_: object) -> list[dict[str, object]]:
        return list(self.events)


def _workflow_state(tmp_path: Path) -> ApiState:
    settings = KnowledgeQuerySettings(
        data_root=tmp_path / "data",
        index_root=tmp_path / "index",
        database_url="postgresql+psycopg://audit:audit@127.0.0.1:1/audit",
        model_provider=ModelProviderSettings(
            provider="fake",
            api_key_env="OPENAI_API_KEY",
            embedding_model="fake",
            chat_model="fake",
        ),
        source_collection_weights={key: 1.0 for key in REQUIRED_COLLECTIONS},
    )
    state = ApiState.from_settings(settings)
    state.audit_finding_store = FakeAuditFindingStore()  # type: ignore[assignment]
    state.audit_log_store = FakeAuditLogStore()  # type: ignore[assignment]
    state.review_task_store = InMemoryReviewTaskStore()
    return state
