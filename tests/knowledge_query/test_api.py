import json
from collections.abc import Sequence
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook

from medical_audit_kb.api.agent_store import AGENT_ID_PREFIX, SqlAlchemyAgentStore
from medical_audit_kb.api.analytics_upload_store import (
    ANALYTICS_UPLOAD_ID_PREFIX,
    InMemoryAnalyticsUploadStore,
    SqlAlchemyAnalyticsUploadStore,
)
from medical_audit_kb.api.app import ApiState, create_app
from medical_audit_kb.api.document_upload_governance import (
    DocumentUploadGovernanceContext,
    DocumentUploadGovernancePolicy,
    GovernanceCheckResult,
    document_upload_governance_policy_from_settings,
)
from medical_audit_kb.api.document_upload_store import (
    DOCUMENT_UPLOAD_ID_PREFIX,
    InMemoryDocumentUploadStore,
    SqlAlchemyDocumentUploadStore,
)
from medical_audit_kb.api.project_member_store import (
    PROJECT_MEMBER_ID_PREFIX,
    SqlAlchemyProjectMemberStore,
)
from medical_audit_kb.api.query_history_store import (
    InMemoryQueryHistoryStore,
    SqlAlchemyQueryHistoryStore,
)
from medical_audit_kb.core.config import (
    DocumentUploadGovernanceSettings,
    KnowledgeQuerySettings,
    ModelProviderSettings,
)
from medical_audit_kb.domain.constants import SourceCollection
from medical_audit_kb.generation.citations import Citation
from medical_audit_kb.indexing.bm25_index import BM25Document, InMemoryBM25Index
from medical_audit_kb.indexing.embeddings import DeterministicFakeEmbeddingProvider
from medical_audit_kb.indexing.index_activation import (
    IndexActivationError,
    IndexActivationResult,
    IndexRollbackResult,
)
from medical_audit_kb.indexing.vector_index import (
    ChunkEmbeddingInput,
    InMemoryVectorIndex,
    build_chunk_embedding_records,
)
from medical_audit_kb.retrieval.hybrid_search import HybridSearchEngine
from medical_audit_kb.retrieval.rerank import FakeRerankProvider


def test_health_endpoint_returns_api_status(tmp_path: Path) -> None:
    client = TestClient(create_app(_api_state(tmp_path)))

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["data_root"] == str(tmp_path / "data")


def test_agents_api_lists_defaults_and_persists_created_agent(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'agents.db'}"
    state = _api_state(tmp_path)
    state.agent_store = SqlAlchemyAgentStore(database_url, create_schema=True)
    client = TestClient(create_app(state))

    list_response = client.get("/agents")

    assert list_response.status_code == 200
    list_body = list_response.json()
    assert list_body["store"]["backend"] == "SqlAlchemyAgentStore"
    assert list_body["categories"] == ["业务类", "效率类", "研究类"]
    assert [item["id"] for item in list_body["items"][:3]] == [
        "agent-citation-check",
        "agent-duplicate-charge",
        "agent-report-draft",
    ]

    create_response = client.post(
        "/agents",
        headers={"X-User-Id": "auditor-1", "X-Role": "auditor"},
        json={
            "name": "目录限制核验助手",
            "category": "业务类",
            "topic": "医保目录限制条件核验",
            "prompt": "仅基于目录限制字段和引用依据输出待补证问题。",
            "knowledge_base": "医保目录库",
            "project_name": "医保目录限制条件核验",
        },
    )

    assert create_response.status_code == 200
    created = create_response.json()["item"]
    assert created["id"].startswith(AGENT_ID_PREFIX)
    assert created["created_by"] == "auditor-1"
    assert created["source"] == "custom"
    assert state.operation_logs[-1]["action"] == "agent-create"
    assert state.operation_logs[-1]["payload"]["role"] == "auditor"
    assert state.operation_logs[-1]["payload"]["normalized_role"] == "auditor"
    assert state.operation_logs[-1]["payload"]["auth_source"] == "legacy-header"

    second_state = _api_state(tmp_path / "second")
    second_state.agent_store = SqlAlchemyAgentStore(database_url)
    second_client = TestClient(create_app(second_state))
    persisted_items = second_client.get("/agents").json()["items"]

    assert persisted_items[0]["id"] == created["id"]
    assert persisted_items[0]["name"] == "目录限制核验助手"
    assert any(item["id"] == "agent-citation-check" for item in persisted_items)


def test_agents_api_rejects_unknown_category(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    state.agent_store = SqlAlchemyAgentStore(
        f"sqlite:///{tmp_path / 'agents.db'}",
        create_schema=True,
    )
    client = TestClient(create_app(state))

    response = client.post(
        "/agents",
        json={
            "name": "未知分类助手",
            "category": "其他",
            "topic": "医保基金使用合规",
            "prompt": "输出审计问题。",
        },
    )

    assert response.status_code == 422


def test_agents_api_records_denied_write_for_unknown_role(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    state.agent_store = SqlAlchemyAgentStore(
        f"sqlite:///{tmp_path / 'agents.db'}",
        create_schema=True,
    )
    client = TestClient(create_app(state))

    response = client.post(
        "/agents",
        headers={"X-User-Id": "guest-1", "X-Role": "guest"},
        json={
            "name": "访客助手",
            "category": "业务类",
            "topic": "医保基金使用合规",
            "prompt": "输出审计问题。",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "role is not allowed"
    assert state.operation_logs[-1] == {
        "action": "agent-access-denied",
        "payload": {
            "attempted_action": "agent-create",
            "user_identifier": "guest-1",
            "role": "guest",
            "normalized_role": "guest",
            "auth_source": "legacy-header",
            "status_code": 403,
            "reason": "role is not allowed",
        },
    }


def test_projects_api_lists_defaults_and_persists_created_member(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'project-members.db'}"
    state = _api_state(tmp_path)
    state.project_member_store = SqlAlchemyProjectMemberStore(database_url, create_schema=True)
    client = TestClient(create_app(state))

    projects_response = client.get("/projects")

    assert projects_response.status_code == 200
    projects_body = projects_response.json()
    assert projects_body["store"]["backend"] == "SqlAlchemyProjectMemberStore"
    assert projects_body["roles"] == ["项目负责人", "审计员", "业务专家", "信息科", "只读观察员"]
    assert projects_body["items"][0]["id"] == "SELF-CHECK-FUND-20260607"
    assert projects_body["items"][0]["member_count"] == 3

    members_response = client.get("/projects/CATALOG-LIMIT-202606/members")

    assert members_response.status_code == 200
    members_body = members_response.json()
    assert members_body["project_key"] == "CATALOG-LIMIT-202606"
    assert len(members_body["items"]) == 4
    assert members_body["items"][0]["source"] == "system-default"

    create_response = client.post(
        "/projects/CATALOG-LIMIT-202606/members",
        headers={"X-User-Id": "auditor-1", "X-Role": "auditor"},
        json={
            "name": "赵审计",
            "role": "审计员",
            "department": "医保办",
        },
    )

    assert create_response.status_code == 200
    created = create_response.json()["item"]
    assert created["id"].startswith(PROJECT_MEMBER_ID_PREFIX)
    assert created["project_key"] == "CATALOG-LIMIT-202606"
    assert created["status"] == "待确认"
    assert created["created_by"] == "auditor-1"
    assert state.operation_logs[-1]["action"] == "project-member-create"
    assert state.operation_logs[-1]["payload"]["actor_role"] == "auditor"
    assert state.operation_logs[-1]["payload"]["normalized_role"] == "auditor"
    assert state.operation_logs[-1]["payload"]["auth_source"] == "legacy-header"

    second_state = _api_state(tmp_path / "second")
    second_state.project_member_store = SqlAlchemyProjectMemberStore(database_url)
    second_client = TestClient(create_app(second_state))
    persisted_members = second_client.get("/projects/CATALOG-LIMIT-202606/members").json()[
        "items"
    ]
    persisted_projects = second_client.get("/projects").json()["items"]
    catalog_project = next(
        item for item in persisted_projects if item["id"] == "CATALOG-LIMIT-202606"
    )

    assert persisted_members[0]["id"] == created["id"]
    assert persisted_members[0]["name"] == "赵审计"
    assert any(item["id"] == "member-catalog-owner" for item in persisted_members)
    assert catalog_project["member_count"] == 5


def test_projects_api_rejects_unknown_project_and_role(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    state.project_member_store = SqlAlchemyProjectMemberStore(
        f"sqlite:///{tmp_path / 'project-members.db'}",
        create_schema=True,
    )
    client = TestClient(create_app(state))

    missing_response = client.get("/projects/UNKNOWN/members")
    invalid_role_response = client.post(
        "/projects/SELF-CHECK-FUND-20260607/members",
        json={
            "name": "未知角色",
            "role": "访客",
            "department": "医保办",
        },
    )
    forbidden_actor_response = client.post(
        "/projects/SELF-CHECK-FUND-20260607/members",
        headers={"X-User-Id": "guest-1", "X-Role": "guest"},
        json={
            "name": "访客成员",
            "role": "审计员",
            "department": "医保办",
        },
    )

    assert missing_response.status_code == 404
    assert invalid_role_response.status_code == 422
    assert forbidden_actor_response.status_code == 403
    assert forbidden_actor_response.json()["detail"] == "role is not allowed"
    assert state.operation_logs[-1] == {
        "action": "project-member-access-denied",
        "payload": {
            "attempted_action": "project-member-create",
            "user_identifier": "guest-1",
            "role": "guest",
            "normalized_role": "guest",
            "auth_source": "legacy-header",
            "status_code": 403,
            "reason": "role is not allowed",
        },
    }


def test_analytics_table_upload_profiles_csv_file(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'analytics-uploads.db'}"
    state = _api_state(tmp_path)
    state.analytics_upload_store = SqlAlchemyAnalyticsUploadStore(
        database_url=database_url,
        upload_root=tmp_path / "retained-uploads",
        create_schema=True,
    )
    client = TestClient(create_app(state))

    response = client.post(
        "/analytics/table-upload",
        files={
            "file": (
                "charge-sample.csv",
                "\n".join(
                    [
                        "patient_id,visit_date,item_code,charge_amount,insurance_pay",
                        "P001,2026-01-01,A100,120.00,80.00",
                        "P001,2026-01-01,A100,120.00,80.00",
                        "P002,2026-01-02,B200,,50.00",
                    ]
                ),
                "text/csv",
            )
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "charge-sample.csv"
    assert body["upload_id"].startswith(ANALYTICS_UPLOAD_ID_PREFIX)
    assert body["sha256"]
    assert body["retention_status"] == "retained"
    assert body["created_at"]
    assert body["extension"] == "csv"
    assert body["status"] == "parsed"
    assert body["row_count"] == 3
    assert body["duplicate_row_count"] == 1
    assert body["empty_cell_count"] == 1
    assert body["audit_signals"] == [
        "金额/费用字段",
        "患者/就诊字段",
        "日期/时间字段",
        "项目/药品/目录字段",
        "医保支付字段",
    ]
    assert body["columns"][0]["type"] == "标识"
    assert "发现 1 条完全重复行。" in body["quality_findings"]
    assert state.operation_logs[-1]["action"] == "analytics-table-upload"
    assert state.operation_logs[-1]["payload"]["retention_status"] == "retained"

    history_response = client.get("/analytics/table-uploads")
    assert history_response.status_code == 200
    history_body = history_response.json()
    assert history_body["store"]["backend"] == "SqlAlchemyAnalyticsUploadStore"
    assert history_body["items"][0]["id"] == body["upload_id"]
    assert history_body["items"][0]["sha256"] == body["sha256"]
    assert history_body["items"][0]["row_count"] == 3
    assert history_body["items"][0]["column_count"] == 5

    retained_path = tmp_path / "retained-uploads" / history_body["items"][0]["storage_path"]
    assert retained_path.exists()
    assert retained_path.read_text(encoding="utf-8").startswith("patient_id,visit_date")

    second_state = _api_state(tmp_path / "second")
    second_state.analytics_upload_store = SqlAlchemyAnalyticsUploadStore(
        database_url=database_url,
        upload_root=tmp_path / "retained-uploads",
    )
    second_client = TestClient(create_app(second_state))
    persisted_items = second_client.get("/analytics/table-uploads").json()["items"]
    assert persisted_items[0]["id"] == body["upload_id"]


def test_analytics_table_upload_profiles_xlsx_file(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    client = TestClient(create_app(state))
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "收费明细"
    worksheet.append(["患者编号", "结算日期", "项目编码", "收费金额"])
    worksheet.append(["P001", "2026-01-01", "A100", 120])
    worksheet.append(["P002", "2026-01-02", "B200", 80])
    buffer = BytesIO()
    workbook.save(buffer)

    response = client.post(
        "/analytics/table-upload",
        files={
            "file": (
                "charge-workbook.xlsx",
                buffer.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "charge-workbook.xlsx"
    assert body["extension"] == "xlsx"
    assert body["sheet_name"] == "收费明细"
    assert body["row_count"] == 2
    assert body["columns"][3]["name"] == "收费金额"
    assert body["columns"][3]["type"] == "数值"
    assert body["message"] == "后端已完成 XLSX 工作簿（sheet: 收费明细）的字段画像。"


def test_analytics_table_upload_rejects_unsupported_extension(tmp_path: Path) -> None:
    client = TestClient(create_app(_api_state(tmp_path)))

    response = client.post(
        "/analytics/table-upload",
        files={"file": ("charges.txt", "not,a,supported,file", "text/plain")},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "unsupported table file extension"


def test_documents_permissions_and_uploads_are_role_scoped(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'document-uploads.db'}"
    upload_root = tmp_path / "document-uploads"
    state = _api_state(tmp_path)
    state.document_upload_store = SqlAlchemyDocumentUploadStore(
        database_url=database_url,
        upload_root=upload_root,
        create_schema=True,
    )
    client = TestClient(create_app(state))

    permissions_response = client.get("/documents/permissions", headers={"X-Role": "auditor"})

    assert permissions_response.status_code == 200
    permissions_body = permissions_response.json()
    assert permissions_body["role"] == "auditor"
    assert [item["source_collection"] for item in permissions_body["source_collections"]] == [
        "medical-insurance-laws",
        "supervision-rules-knowledge",
        "medical-insurance-catalog",
        "risk-negative-list",
    ]
    assert permissions_body["upload_permissions"] == {
        "can_upload_personal": True,
        "can_read_all_personal_uploads": False,
    }

    upload_response = client.post(
        "/documents/uploads",
        headers={"X-User-Id": "auditor-1", "X-Role": "auditor"},
        files={"file": ("policy.pdf", b"%PDF-1.4 policy", "application/pdf")},
    )

    assert upload_response.status_code == 200
    upload_body = upload_response.json()
    uploaded = upload_body["item"]
    assert uploaded["id"].startswith(DOCUMENT_UPLOAD_ID_PREFIX)
    assert uploaded["created_by"] == "auditor-1"
    assert uploaded["extension"] == "pdf"
    assert uploaded["retention_status"] == "retained"
    assert uploaded["index_status"] == "not-indexed"
    assert uploaded["index_readiness"] == {
        "status": "blocked",
        "blockers": [
            "virus-scan-required",
            "dlp-review-required",
            "manual-index-approval-required",
        ],
        "next_action": "complete-upload-governance",
        "checks": [
            {
                "check_type": "virus-scan",
                "provider": "unconfigured",
                "status": "blocked",
                "blocker": "virus-scan-required",
                "detail": "virus scan adapter is not configured for pdf upload",
            },
            {
                "check_type": "dlp-review",
                "provider": "unconfigured",
                "status": "blocked",
                "blocker": "dlp-review-required",
                "detail": "DLP review adapter is not configured for pdf upload",
            },
            {
                "check_type": "manual-index-approval",
                "provider": "manual",
                "status": "blocked",
                "blocker": "manual-index-approval-required",
                "detail": "manual index approval is required before ingesting policy.pdf",
            },
        ],
    }
    assert uploaded["sha256"]
    assert upload_body["store"]["backend"] == "SqlAlchemyDocumentUploadStore"
    assert state.operation_logs[-1]["action"] == "document-upload"
    assert state.operation_logs[-1]["payload"]["index_status"] == "not-indexed"
    assert state.operation_logs[-1]["payload"]["index_readiness_status"] == "blocked"
    assert state.operation_logs[-1]["payload"]["index_readiness_blockers"] == [
        "virus-scan-required",
        "dlp-review-required",
        "manual-index-approval-required",
    ]
    assert state.operation_logs[-1]["payload"]["index_readiness_checks"] == uploaded[
        "index_readiness"
    ]["checks"]
    assert state.operation_logs[-1]["payload"]["normalized_role"] == "auditor"
    assert state.operation_logs[-1]["payload"]["auth_source"] == "legacy-header"

    retained_path = upload_root / uploaded["storage_path"]
    assert retained_path.exists()
    assert retained_path.read_bytes() == b"%PDF-1.4 policy"

    owner_response = client.get(
        "/documents/uploads",
        headers={"X-User-Id": "auditor-1", "X-Role": "auditor"},
    )
    assert owner_response.status_code == 200
    assert owner_response.json()["items"][0]["id"] == uploaded["id"]

    other_auditor_response = client.get(
        "/documents/uploads",
        headers={"X-User-Id": "auditor-2", "X-Role": "auditor"},
    )
    assert other_auditor_response.status_code == 200
    assert other_auditor_response.json()["items"] == []

    admin_response = client.get(
        "/documents/uploads",
        headers={"X-User-Id": "admin-1", "X-Role": "it-admin"},
    )
    assert admin_response.status_code == 200
    admin_body = admin_response.json()
    assert admin_body["permissions"]["can_read_all_personal_uploads"] is True
    assert admin_body["items"][0]["id"] == uploaded["id"]

    second_state = _api_state(tmp_path / "second")
    second_state.document_upload_store = SqlAlchemyDocumentUploadStore(
        database_url=database_url,
        upload_root=upload_root,
    )
    second_client = TestClient(create_app(second_state))
    persisted_items = second_client.get(
        "/documents/uploads",
        headers={"X-User-Id": "auditor-1", "X-Role": "auditor"},
    ).json()["items"]
    assert persisted_items[0]["id"] == uploaded["id"]


def test_documents_upload_governance_adapters_clear_scan_and_dlp_blockers(
    tmp_path: Path,
) -> None:
    class PassingVirusScanner:
        provider = "local-test-virus"

        def scan(self, context: DocumentUploadGovernanceContext) -> GovernanceCheckResult:
            return GovernanceCheckResult(
                check_type="virus-scan",
                provider=self.provider,
                status="passed",
                blocker=None,
                detail=f"sha256 {context.sha256} accepted",
            )

    class PassingDlpReviewer:
        provider = "local-test-dlp"

        def review(self, context: DocumentUploadGovernanceContext) -> GovernanceCheckResult:
            return GovernanceCheckResult(
                check_type="dlp-review",
                provider=self.provider,
                status="passed",
                blocker=None,
                detail=f"{context.file_name} contains no test DLP findings",
            )

    state = _api_state(tmp_path)
    state.document_upload_store = InMemoryDocumentUploadStore(
        upload_root=tmp_path / "document-uploads",
    )
    state.document_upload_governance = DocumentUploadGovernancePolicy(
        virus_scanner=PassingVirusScanner(),
        dlp_reviewer=PassingDlpReviewer(),
    )
    client = TestClient(create_app(state))

    response = client.post(
        "/documents/uploads",
        headers={"X-User-Id": "auditor-1", "X-Role": "auditor"},
        files={"file": ("policy.txt", b"policy evidence", "text/plain")},
    )

    assert response.status_code == 200
    readiness = response.json()["item"]["index_readiness"]
    assert readiness["status"] == "blocked"
    assert readiness["blockers"] == ["manual-index-approval-required"]
    assert readiness["checks"] == [
        {
            "check_type": "virus-scan",
            "provider": "local-test-virus",
            "status": "passed",
            "blocker": None,
            "detail": f"sha256 {response.json()['item']['sha256']} accepted",
        },
        {
            "check_type": "dlp-review",
            "provider": "local-test-dlp",
            "status": "passed",
            "blocker": None,
            "detail": "policy.txt contains no test DLP findings",
        },
        {
            "check_type": "manual-index-approval",
            "provider": "manual",
            "status": "blocked",
            "blocker": "manual-index-approval-required",
            "detail": "manual index approval is required before ingesting policy.txt",
        },
    ]


def test_documents_upload_manual_index_approval_marks_ready_and_persists(
    tmp_path: Path,
) -> None:
    class PassingVirusScanner:
        provider = "local-test-virus"

        def scan(self, context: DocumentUploadGovernanceContext) -> GovernanceCheckResult:
            return GovernanceCheckResult(
                check_type="virus-scan",
                provider=self.provider,
                status="passed",
                blocker=None,
                detail=f"sha256 {context.sha256} accepted",
            )

    class PassingDlpReviewer:
        provider = "local-test-dlp"

        def review(self, context: DocumentUploadGovernanceContext) -> GovernanceCheckResult:
            return GovernanceCheckResult(
                check_type="dlp-review",
                provider=self.provider,
                status="passed",
                blocker=None,
                detail=f"{context.file_name} contains no test DLP findings",
            )

    database_url = f"sqlite:///{tmp_path / 'document-index-readiness.db'}"
    state = _api_state(tmp_path)
    state.document_upload_store = SqlAlchemyDocumentUploadStore(
        database_url=database_url,
        upload_root=tmp_path / "document-uploads",
        create_schema=True,
    )
    state.document_upload_governance = DocumentUploadGovernancePolicy(
        virus_scanner=PassingVirusScanner(),
        dlp_reviewer=PassingDlpReviewer(),
    )
    client = TestClient(create_app(state))

    upload_response = client.post(
        "/documents/uploads",
        headers={"X-User-Id": "auditor-1", "X-Role": "auditor"},
        files={"file": ("policy.txt", b"policy evidence", "text/plain")},
    )
    upload_id = upload_response.json()["item"]["id"]

    approval_response = client.post(
        f"/documents/uploads/{upload_id}/index-readiness/manual-approval",
        headers={"X-User-Id": "head-1", "X-Role": "department-head"},
        json={"decision": "approved", "note": "审查通过，准许进入后续入索引队列。"},
    )

    assert approval_response.status_code == 200
    item = approval_response.json()["item"]
    assert item["id"] == upload_id
    assert item["index_status"] == "not-indexed"
    assert item["index_readiness"] == {
        "status": "ready",
        "blockers": [],
        "next_action": "ingest-personal-upload",
        "checks": [
            {
                "check_type": "virus-scan",
                "provider": "local-test-virus",
                "status": "passed",
                "blocker": None,
                "detail": f"sha256 {item['sha256']} accepted",
            },
            {
                "check_type": "dlp-review",
                "provider": "local-test-dlp",
                "status": "passed",
                "blocker": None,
                "detail": "policy.txt contains no test DLP findings",
            },
            {
                "check_type": "manual-index-approval",
                "provider": "manual",
                "status": "passed",
                "blocker": None,
                "detail": (
                    "manual index approval approved by head-1: "
                    "审查通过，准许进入后续入索引队列。"
                ),
            },
        ],
    }
    assert state.operation_logs[-1]["action"] == "document-upload-index-readiness-update"
    assert state.operation_logs[-1]["payload"]["upload_id"] == upload_id
    assert state.operation_logs[-1]["payload"]["decision"] == "approved"
    assert state.operation_logs[-1]["payload"]["index_readiness_status"] == "ready"
    assert state.operation_logs[-1]["payload"]["normalized_role"] == "department-head"

    second_state = _api_state(tmp_path / "second")
    second_state.document_upload_store = SqlAlchemyDocumentUploadStore(
        database_url=database_url,
        upload_root=tmp_path / "document-uploads",
    )
    second_client = TestClient(create_app(second_state))
    persisted = second_client.get(
        "/documents/uploads",
        headers={"X-User-Id": "auditor-1", "X-Role": "auditor"},
    ).json()["items"][0]
    assert persisted["id"] == upload_id
    assert persisted["index_readiness"]["status"] == "ready"


def test_documents_upload_manual_index_rejection_marks_rejected(
    tmp_path: Path,
) -> None:
    state = _api_state(tmp_path)
    client = TestClient(create_app(state))
    upload_response = client.post(
        "/documents/uploads",
        headers={"X-User-Id": "auditor-1", "X-Role": "auditor"},
        files={"file": ("policy.txt", b"policy evidence", "text/plain")},
    )
    upload_id = upload_response.json()["item"]["id"]

    rejection_response = client.post(
        f"/documents/uploads/{upload_id}/index-readiness/manual-approval",
        headers={"X-User-Id": "admin-1", "X-Role": "it-admin"},
        json={"decision": "rejected", "note": "材料来源不足，退回补证。"},
    )

    assert rejection_response.status_code == 200
    readiness = rejection_response.json()["item"]["index_readiness"]
    assert readiness["status"] == "rejected"
    assert readiness["blockers"] == [
        "virus-scan-required",
        "dlp-review-required",
        "manual-index-approval-rejected",
    ]
    assert readiness["next_action"] == "review-manual-index-rejection"
    assert readiness["checks"][-1] == {
        "check_type": "manual-index-approval",
        "provider": "manual",
        "status": "blocked",
        "blocker": "manual-index-approval-rejected",
        "detail": "manual index approval rejected by admin-1: 材料来源不足，退回补证。",
    }


def test_documents_upload_manual_index_approval_rejects_auditor(
    tmp_path: Path,
) -> None:
    denied_reason = "document upload index approval requires department-head or system-admin role"
    state = _api_state(tmp_path)
    client = TestClient(create_app(state))
    upload_response = client.post(
        "/documents/uploads",
        headers={"X-User-Id": "auditor-1", "X-Role": "auditor"},
        files={"file": ("policy.txt", b"policy evidence", "text/plain")},
    )
    upload_id = upload_response.json()["item"]["id"]

    response = client.post(
        f"/documents/uploads/{upload_id}/index-readiness/manual-approval",
        headers={"X-User-Id": "auditor-1", "X-Role": "auditor"},
        json={"decision": "approved", "note": "普通审计员尝试批准。"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == denied_reason
    assert state.operation_logs[-1] == {
        "action": "document-upload-index-approval-access-denied",
        "payload": {
            "attempted_action": "document-upload-index-readiness-update",
            "upload_id": upload_id,
            "user_identifier": "auditor-1",
            "role": "auditor",
            "normalized_role": "auditor",
            "auth_source": "legacy-header",
            "status_code": 403,
            "reason": denied_reason,
        },
    }


def test_documents_upload_local_test_governance_detects_markers(
    tmp_path: Path,
) -> None:
    state = _api_state(tmp_path)
    state.document_upload_store = InMemoryDocumentUploadStore(
        upload_root=tmp_path / "document-uploads",
    )
    state.document_upload_governance = document_upload_governance_policy_from_settings(
        DocumentUploadGovernanceSettings(
            virus_scan_provider="local-test",
            dlp_review_provider="local-test",
        )
    )
    client = TestClient(create_app(state))

    response = client.post(
        "/documents/uploads",
        headers={"X-User-Id": "auditor-1", "X-Role": "auditor"},
        files={"file": ("policy.txt", b"EICAR patient_id=123", "text/plain")},
    )

    assert response.status_code == 200
    readiness = response.json()["item"]["index_readiness"]
    assert readiness["blockers"] == [
        "virus-scan-required",
        "dlp-review-required",
        "manual-index-approval-required",
    ]
    assert readiness["checks"] == [
        {
            "check_type": "virus-scan",
            "provider": "local-test",
            "status": "blocked",
            "blocker": "virus-scan-required",
            "detail": "local test virus marker detected",
        },
        {
            "check_type": "dlp-review",
            "provider": "local-test",
            "status": "blocked",
            "blocker": "dlp-review-required",
            "detail": "local test DLP marker detected",
        },
        {
            "check_type": "manual-index-approval",
            "provider": "manual",
            "status": "blocked",
            "blocker": "manual-index-approval-required",
            "detail": "manual index approval is required before ingesting policy.txt",
        },
    ]


def test_documents_upload_local_test_governance_supports_false_positive_and_negative(
    tmp_path: Path,
) -> None:
    state = _api_state(tmp_path)
    state.document_upload_store = InMemoryDocumentUploadStore(
        upload_root=tmp_path / "document-uploads",
    )
    state.document_upload_governance = document_upload_governance_policy_from_settings(
        DocumentUploadGovernanceSettings(
            virus_scan_provider="local-test",
            dlp_review_provider="local-test",
            virus_scan_test_mode="false-positive",
            dlp_review_test_mode="false-negative",
        )
    )
    client = TestClient(create_app(state))

    response = client.post(
        "/documents/uploads",
        headers={"X-User-Id": "auditor-1", "X-Role": "auditor"},
        files={"file": ("policy.txt", b"patient_id=123", "text/plain")},
    )

    assert response.status_code == 200
    readiness = response.json()["item"]["index_readiness"]
    assert readiness["blockers"] == [
        "virus-scan-required",
        "manual-index-approval-required",
    ]
    assert readiness["checks"] == [
        {
            "check_type": "virus-scan",
            "provider": "local-test",
            "status": "blocked",
            "blocker": "virus-scan-required",
            "detail": "local false-positive virus test blocked upload",
        },
        {
            "check_type": "dlp-review",
            "provider": "local-test",
            "status": "passed",
            "blocker": None,
            "detail": "local false-negative DLP test passed upload",
        },
        {
            "check_type": "manual-index-approval",
            "provider": "manual",
            "status": "blocked",
            "blocker": "manual-index-approval-required",
            "detail": "manual index approval is required before ingesting policy.txt",
        },
    ]


def test_documents_upload_rejects_unsupported_extension(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    state.document_upload_store = InMemoryDocumentUploadStore(
        upload_root=tmp_path / "document-uploads",
    )
    client = TestClient(create_app(state))

    response = client.post(
        "/documents/uploads",
        files={"file": ("policy.exe", b"binary", "application/octet-stream")},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "unsupported document file extension"


def test_query_endpoint_returns_citation_answer_and_records_query_log(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    client = TestClient(create_app(state))

    response = client.post(
        "/query",
        headers={"X-User-Id": "auditor-1", "X-Role": "auditor"},
        json={"question": "医保基金审核依据", "top_k": 2},
    )

    assert response.status_code == 200
    body = response.json()
    assert "[C1]" in body["answer"]
    assert body["citations"][0]["source_collection"] == "medical-insurance-laws"
    assert body["citations"][0]["index_version_key"] == "index-v1"
    assert body["citations"][0]["source_package_version_key"] == "package-v1"
    assert body["basis_groups"][0]["title"] == "法规依据"
    assert body["basis_groups"][0]["items"][0]["source_collection"] == "medical-insurance-laws"
    assert body["query_log_index"] == 0

    logs_response = client.get("/query/logs")
    assert logs_response.status_code == 200
    assert logs_response.json()["items"][0]["user_identifier"] == "auditor-1"
    assert logs_response.json()["items"][0]["filters"]["top_k"] == 2
    assert state.operation_logs[-1]["action"] == "query"
    assert state.operation_logs[-1]["payload"]["normalized_role"] == "auditor"
    assert state.operation_logs[-1]["payload"]["auth_source"] == "legacy-header"


def test_query_endpoint_persists_query_history(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'query-history.db'}"
    state = _api_state(tmp_path)
    state.query_history_store = SqlAlchemyQueryHistoryStore(database_url, create_schema=True)
    client = TestClient(create_app(state))

    response = client.post(
        "/query",
        headers={"X-User-Id": "auditor-1", "X-Role": "auditor"},
        json={
            "question": "医保基金审核依据",
            "top_k": 2,
            "source_collections": ["medical-insurance-laws"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["query_log_id"]

    history_response = client.get("/query/logs?limit=5")
    assert history_response.status_code == 200
    history_body = history_response.json()
    assert history_body["store"]["backend"] == "SqlAlchemyQueryHistoryStore"
    assert history_body["items"][0]["id"] == body["query_log_id"]
    assert history_body["items"][0]["question"] == "医保基金审核依据"
    assert history_body["items"][0]["filters"]["source_collections"] == ["medical-insurance-laws"]
    assert history_body["items"][0]["citation_count"] == 1
    assert history_body["items"][0]["answer_summary"]

    second_state = _api_state(tmp_path / "second")
    second_state.query_history_store = SqlAlchemyQueryHistoryStore(database_url)
    second_client = TestClient(create_app(second_state))
    persisted_items = second_client.get("/query/logs").json()["items"]
    assert persisted_items[0]["id"] == body["query_log_id"]


def test_query_history_store_failure_does_not_block_query(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    state.query_history_store = FailingQueryHistoryStore()
    client = TestClient(create_app(state))

    response = client.post(
        "/query",
        json={"question": "医保基金审核依据", "top_k": 2},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["query_log_id"] is None
    assert state.operation_logs[-1]["payload"]["query_history_error"] == {
        "error_type": "RuntimeError",
        "message": "query history store operation failed",
    }

    logs_response = client.get("/query/logs")
    assert logs_response.status_code == 200
    logs_body = logs_response.json()
    assert logs_body["store"] == {
        "ready": False,
        "backend": "FailingQueryHistoryStore",
        "error": {
            "error_type": "RuntimeError",
            "message": "query history store operation failed",
        },
    }
    assert logs_body["items"][0]["question"] == "医保基金审核依据"


def test_query_endpoint_uses_configured_answer_generation_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "medical_audit_kb.api.app.answer_generation_provider_from_settings",
        lambda _settings: StaticApiAnswerProvider(),
        raising=False,
    )
    state = _api_state(tmp_path)
    client = TestClient(create_app(state))

    response = client.post(
        "/query",
        headers={"X-Role": "auditor"},
        json={"question": "医保基金审核依据", "top_k": 2},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["fallback_used"] is False
    assert body["answer"] == "生成模型回答：应核验医保基金审核依据 [C1]。"


def test_query_endpoint_blocks_unknown_role(tmp_path: Path) -> None:
    client = TestClient(create_app(_api_state(tmp_path)))

    response = client.post(
        "/query",
        headers={"X-Role": "guest"},
        json={"question": "医保基金审核依据"},
    )

    assert response.status_code == 403


def test_preview_endpoint_resolves_chunk_reference_after_query(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    client = TestClient(create_app(state))
    query_response = client.post(
        "/query",
        headers={"X-Role": "auditor"},
        json={"question": "医保基金审核依据"},
    )
    chunk_id = query_response.json()["citations"][0]["chunk_id"]

    preview_response = client.get(f"/preview/{chunk_id}")

    assert preview_response.status_code == 200
    body = preview_response.json()
    assert body["chunk_id"] == chunk_id
    assert "医疗机构应当保留医保基金审核依据" in body["preview_text"]
    assert body["highlights"]
    assert body["line_start"] == 1


def test_index_rebuild_incremental_lists_and_permissions(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    source_root = state.source_root
    _write_text(source_root / "医保目录" / "catalog.md", "# 医保目录\n医保目录内容")
    _write_text(source_root / "风险负面清单" / "risk.png", "pending")
    client = TestClient(create_app(state))

    forbidden_response = client.post(
        "/index/rebuild",
        headers={"X-Role": "auditor"},
        json={"package_version_key": "api-package"},
    )
    assert forbidden_response.status_code == 403

    rebuild_response = client.post(
        "/index/rebuild",
        headers={"X-Role": "it-admin"},
        json={"package_version_key": "api-package"},
    )
    assert rebuild_response.status_code == 200
    rebuild_summary = rebuild_response.json()["summary"]
    assert rebuild_summary["job_type"] == "full-rebuild"
    assert rebuild_summary["index_candidate_file_count"] == 1
    assert rebuild_summary["pending_file_count"] == 1

    incremental_response = client.post(
        "/index/incremental",
        headers={"X-Role": "it-admin"},
        json={"package_version_key": "api-package-next"},
    )
    assert incremental_response.status_code == 200
    assert incremental_response.json()["summary"]["job_type"] == "incremental"

    versions = client.get("/index/versions").json()["items"]
    jobs = client.get("/index/jobs").json()["items"]
    pending = client.get("/index/pending").json()["items"]
    failures = client.get("/index/failures").json()["items"]

    assert len(versions) == 2
    assert len(jobs) == 2
    assert jobs[-1]["status"] == "succeeded"
    assert pending[0]["relative_path"] == "风险负面清单/risk.png"
    assert failures == []


def test_index_retry_file_reports_missing_target(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    _write_text(state.source_root / "医保目录" / "catalog.md", "# 医保目录\n医保目录内容")
    client = TestClient(create_app(state))

    response = client.post(
        "/index/retry-file",
        headers={"X-Role": "it-admin"},
        json={"package_version_key": "retry-package", "relative_path": "医保目录/missing.md"},
    )

    assert response.status_code == 200
    assert response.json()["summary"]["failed_file_count"] == 1
    assert (
        client.get("/index/failures").json()["items"][0]["relative_path"] == "医保目录/missing.md"
    )


def test_index_postgres_status_reports_database_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _api_state(tmp_path)

    def fake_load_postgres_index_status(database_url: str) -> dict[str, object]:
        return {
            "available": True,
            "row_counts": {
                "source_package_versions": 1,
                "source_documents": 486,
                "document_chunks": 48985,
                "chunk_embeddings": 48985,
                "index_versions": 1,
                "index_jobs": 1,
                "failed_files": 0,
                "pending_files": 13,
            },
            "embedding_sets": [
                {
                    "provider": "openai",
                    "model_name": "kimi-for-coding",
                    "provider_version": "v1",
                    "dimension": 1024,
                    "embedding_count": 48985,
                }
            ],
            "index_versions": [
                {
                    "version_key": "source-package-real-data-kimi-20260531",
                    "status": "active",
                    "vector_provider": "openai",
                    "vector_model": "kimi-for-coding",
                    "chunk_count": 48985,
                    "document_count": 486,
                }
            ],
            "source_packages": [
                {
                    "version_key": "source-package-real-data-kimi-20260531",
                    "source_root_path": "data/医保审核前期资料",
                }
            ],
        }

    monkeypatch.setattr(
        "medical_audit_kb.api.routes_index.load_postgres_index_status",
        fake_load_postgres_index_status,
    )
    client = TestClient(create_app(state))

    response = client.get("/index/postgres-status")

    assert response.status_code == 200
    body = response.json()
    assert body["row_counts"]["document_chunks"] == 48985
    assert body["row_counts"]["pending_files"] == 13
    assert body["embedding_sets"][0]["model_name"] == "kimi-for-coding"
    assert state.operation_logs[-1]["action"] == "postgres-index-status-view"


def test_index_postgres_search_backend_loads_with_admin_role(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _api_state(tmp_path)
    state.search_engine = None
    loaded_engine = _search_engine(_chunk_id(), "全量法律/law.md")
    captured: dict[str, object] = {}

    def fake_load_postgres_hybrid_search_engine(
        *,
        database_url: str,
        embedding_provider: DeterministicFakeEmbeddingProvider,
    ) -> HybridSearchEngine:
        captured["database_url"] = database_url
        captured["embedding_provider"] = embedding_provider
        return loaded_engine

    monkeypatch.setattr(
        "medical_audit_kb.api.routes_index.load_postgres_hybrid_search_engine",
        fake_load_postgres_hybrid_search_engine,
    )
    monkeypatch.setattr(
        "medical_audit_kb.api.routes_index.count_postgres_embeddings",
        lambda database_url, embedding_provider: 48985,
    )
    client = TestClient(create_app(state))

    status_response = client.get("/index/search-backend")
    assert status_response.status_code == 200
    assert status_response.json() == {"backend": "none", "ready": False, "details": {}}

    forbidden_response = client.post(
        "/index/search-backend/postgres",
        headers={"X-Role": "auditor"},
        json={
            "embedding_provider": "fake",
            "embedding_model": "fake",
            "embedding_dimension": 32,
        },
    )
    assert forbidden_response.status_code == 403

    response = client.post(
        "/index/search-backend/postgres",
        headers={"X-Role": "it-admin"},
        json={
            "embedding_provider": "fake",
            "embedding_model": "fake",
            "embedding_dimension": 32,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["backend"] == "postgres"
    assert body["ready"] is True
    assert body["details"]["embedding_provider"] == "fake"
    assert body["details"]["embedding_dimension"] == 32
    assert body["details"]["matching_embedding_count"] == 48985
    assert id(state.search_engine) == id(loaded_engine)
    assert captured["database_url"] == state.settings.database_url


def test_index_postgres_search_backend_rejects_unmatched_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _api_state(tmp_path)
    state.search_engine = None

    def fake_count_postgres_embeddings(
        database_url: str,
        embedding_provider: DeterministicFakeEmbeddingProvider,
    ) -> int:
        raise ValueError("no postgres embeddings match requested provider metadata")

    monkeypatch.setattr(
        "medical_audit_kb.api.routes_index.count_postgres_embeddings",
        fake_count_postgres_embeddings,
    )
    client = TestClient(create_app(state))

    response = client.post(
        "/index/search-backend/postgres",
        headers={"X-Role": "it-admin"},
        json={
            "embedding_provider": "fake",
            "embedding_model": "fake",
            "embedding_dimension": 1536,
        },
    )

    assert response.status_code == 409
    assert "no postgres embeddings match" in response.json()["detail"]
    assert state.search_engine is None
    assert state.search_backend == "none"


def test_index_version_activate_and_rollback_actions_require_admin(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _api_state(tmp_path)
    client = TestClient(create_app(state))

    monkeypatch.setattr(
        "medical_audit_kb.api.routes_index.activate_index_version",
        lambda **kwargs: IndexActivationResult(
            index_version_key=str(kwargs["index_version_key"]),
            vector_provider="openai",
            vector_model="kimi-for-coding",
            previous_status="candidate",
            deactivated_index_version_keys=("active-old",),
        ),
    )
    monkeypatch.setattr(
        "medical_audit_kb.api.routes_index.rollback_index_version",
        lambda **kwargs: IndexRollbackResult(
            index_version_key=str(kwargs["index_version_key"]),
            vector_provider="openai",
            vector_model="kimi-for-coding",
            previous_status="inactive",
            deactivated_index_version_keys=("active-current",),
        ),
    )

    forbidden_response = client.post(
        "/index/versions/activate",
        headers={"X-User-Id": "auditor-1", "X-Role": "auditor"},
        json={"index_version_key": "candidate-next"},
    )
    assert forbidden_response.status_code == 403
    denied_log = state.operation_logs[-1]
    assert denied_log["action"] == "index-admin-access-denied"
    assert denied_log["payload"] == {
        "attempted_action": "index-version-activate",
        "user_identifier": "auditor-1",
        "role": "auditor",
        "normalized_role": "auditor",
        "auth_source": "legacy-header",
        "status_code": 403,
        "reason": "index operation requires it-admin role",
    }

    activate_response = client.post(
        "/index/versions/activate",
        headers={"X-Role": "it-admin"},
        json={"index_version_key": "candidate-next"},
    )
    assert activate_response.status_code == 200
    assert activate_response.json()["result"]["index_version_key"] == "candidate-next"
    assert str(state.operation_logs[-1]["action"]) == "index-version-activate"

    rollback_response = client.post(
        "/index/versions/rollback",
        headers={"X-Role": "system-admin"},
        json={"index_version_key": "active-old"},
    )
    assert rollback_response.status_code == 200
    assert rollback_response.json()["result"]["previous_status"] == "inactive"
    assert str(state.operation_logs[-1]["action"]) == "index-version-rollback"


def test_index_version_switch_returns_conflict_for_invalid_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = TestClient(create_app(_api_state(tmp_path)))

    def fake_activate_index_version(**kwargs: object) -> IndexActivationResult:
        raise IndexActivationError("index version must be candidate or active")

    monkeypatch.setattr(
        "medical_audit_kb.api.routes_index.activate_index_version",
        fake_activate_index_version,
    )

    response = client.post(
        "/index/versions/activate",
        headers={"X-Role": "it-admin"},
        json={"index_version_key": "inactive-old"},
    )

    assert response.status_code == 409
    assert "candidate or active" in response.json()["detail"]


def test_index_evaluation_run_scores_runtime_backend_and_records_status(
    tmp_path: Path,
) -> None:
    state = _api_state(tmp_path)
    retrieval_cases = _write_text(
        tmp_path / "retrieval-cases.yaml",
        """
cases:
  - case_id: retrieval-case-001
    question: 医疗机构需要保留什么审核依据？
    expected_evidence:
      - source_collection: medical-insurance-laws
        source_path: 全量法律/law.md
        article_or_rule: 第一条
""".strip(),
    )
    answer_cases = _write_text(
        tmp_path / "answer-cases.yaml",
        """
cases:
  - case_id: answer-case-001
    question: 医疗机构需要保留什么审核依据？
    expected_behavior: answer
    required_evidence_terms: [第一条]
    required_answer_terms: [审核依据]
    required_citation_terms: [医疗机构]
""".strip(),
    )
    client = TestClient(create_app(state))

    forbidden_response = client.post(
        "/index/evaluation/run",
        headers={"X-Role": "auditor"},
        json={},
    )
    assert forbidden_response.status_code == 403

    response = client.post(
        "/index/evaluation/run",
        headers={"X-Role": "it-admin"},
        json={
            "retrieval_cases_file": str(retrieval_cases),
            "answer_cases_file": str(answer_cases),
            "max_retrieval_cases": 1,
            "max_answer_cases": 1,
            "top_k": 2,
            "smoke_question": "医保基金审核依据",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pass"
    assert body["retrieval"]["case_count"] == 1
    assert body["retrieval"]["recall_at_k"] == 1.0
    assert body["answer"]["case_count"] == 1
    assert body["answer"]["pass_rate"] == 1.0
    assert body["ui_smoke"]["success"] is True
    assert state.evaluation_runs[-1]["status"] == "pass"
    assert state.operation_logs[-1]["action"] == "index-evaluation-run"


def test_index_evaluation_run_persists_json_report_and_exports_latest(
    tmp_path: Path,
) -> None:
    state = _api_state(tmp_path)
    retrieval_cases = _write_text(
        tmp_path / "retrieval-cases.yaml",
        """
cases:
  - case_id: retrieval-case-001
    question: 医疗机构需要保留什么审核依据？
    expected_evidence:
      - source_collection: medical-insurance-laws
        source_path: 全量法律/law.md
        article_or_rule: 第一条
""".strip(),
    )
    answer_cases = _write_text(
        tmp_path / "answer-cases.yaml",
        """
cases:
  - case_id: answer-case-001
    question: 医疗机构需要保留什么审核依据？
    expected_behavior: answer
    required_evidence_terms: [第一条]
    required_answer_terms: [审核依据]
    required_citation_terms: [医疗机构]
""".strip(),
    )
    client = TestClient(create_app(state))

    response = client.post(
        "/index/evaluation/run",
        headers={"X-Role": "it-admin"},
        json={
            "retrieval_cases_file": str(retrieval_cases),
            "answer_cases_file": str(answer_cases),
            "max_retrieval_cases": 1,
            "max_answer_cases": 1,
            "top_k": 2,
            "smoke_question": "医保基金审核依据",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["report"]["download_path"] == "/index/evaluation/latest/export"
    report_path = Path(body["report"]["path"])
    assert report_path.is_file()
    assert report_path.parent == state.settings.index_root / "evaluation-runs"
    persisted = json.loads(report_path.read_text(encoding="utf-8"))
    assert persisted["status"] == "pass"
    assert persisted["request"]["max_retrieval_cases"] == 1
    assert persisted["search_backend"]["backend"] == "none"

    export_response = client.get("/index/evaluation/latest/export")

    assert export_response.status_code == 200
    exported = export_response.json()
    assert exported["run_id"] == body["report"]["run_id"]
    assert exported["status"] == "pass"
    assert state.operation_logs[-1]["action"] == "index-evaluation-report-export"


def test_index_evaluation_run_records_postgres_history_when_backend_is_postgres(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _api_state(tmp_path)
    state.search_backend = "postgres"
    state.search_backend_details = {
        "embedding_model": "kimi-for-coding",
        "embedding_dimension": 1024,
        "matching_embedding_count": 48985,
    }
    retrieval_cases = _write_text(
        tmp_path / "retrieval-cases.yaml",
        """
cases:
  - case_id: retrieval-case-001
    question: 医疗机构需要保留什么审核依据？
    expected_evidence:
      - source_collection: medical-insurance-laws
        source_path: 全量法律/law.md
        article_or_rule: 第一条
""".strip(),
    )
    answer_cases = _write_text(
        tmp_path / "answer-cases.yaml",
        """
cases:
  - case_id: answer-case-001
    question: 医疗机构需要保留什么审核依据？
    expected_behavior: answer
    required_evidence_terms: [第一条]
    required_answer_terms: [审核依据]
    required_citation_terms: [医疗机构]
""".strip(),
    )
    captured: dict[str, object] = {}

    def fake_persist_evaluation_history(
        history_state: ApiState,
        report: dict[str, object],
    ) -> dict[str, object]:
        captured["state"] = history_state
        captured["report"] = report
        return {
            "backend": "postgres",
            "persisted": True,
            "table": "index_evaluation_runs",
            "run_id": report["run_id"],
        }

    monkeypatch.setattr(
        "medical_audit_kb.api.evaluation_reports.persist_evaluation_history",
        fake_persist_evaluation_history,
    )
    client = TestClient(create_app(state))

    response = client.post(
        "/index/evaluation/run",
        headers={"X-Role": "it-admin"},
        json={
            "retrieval_cases_file": str(retrieval_cases),
            "answer_cases_file": str(answer_cases),
            "max_retrieval_cases": 1,
            "max_answer_cases": 1,
            "top_k": 2,
            "smoke_question": "医保基金审核依据",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["history"]["persisted"] is True
    assert body["history"]["table"] == "index_evaluation_runs"
    assert body["report"]["history"]["persisted"] is True
    assert captured["state"] is state
    report = captured["report"]
    assert isinstance(report, dict)
    assert report["request"]["top_k"] == 2
    assert report["search_backend"]["backend"] == "postgres"
    assert report["report"]["path"].endswith(".json")


def test_index_evaluation_history_lists_runs_and_records_log(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _api_state(tmp_path)

    def fake_list_evaluation_history(
        history_state: ApiState,
        *,
        limit: int = 20,
    ) -> list[dict[str, object]]:
        assert history_state is state
        assert limit == 20
        return [
            {
                "run_id": "11111111-1111-4111-8111-111111111111",
                "status": "pass",
                "generated_at": "2026-06-02T00:00:00+00:00",
                "retrieval_case_count": 52,
                "answer_case_count": 8,
                "ui_smoke_success": True,
                "report_path": "tmp/knowledge-query-indexes/evaluation-runs/report.json",
                "download_path": "/index/evaluation/latest/export",
                "source": "postgres",
            }
        ]

    monkeypatch.setattr(
        "medical_audit_kb.api.routes_index.list_evaluation_history",
        fake_list_evaluation_history,
    )
    client = TestClient(create_app(state))

    response = client.get("/index/evaluation/history")

    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["run_id"] == "11111111-1111-4111-8111-111111111111"
    assert body["items"][0]["source"] == "postgres"
    assert state.operation_logs[-1]["action"] == "index-evaluation-history-view"


def test_index_evaluation_export_returns_not_found_before_first_report(tmp_path: Path) -> None:
    client = TestClient(create_app(_api_state(tmp_path)))

    response = client.get("/index/evaluation/latest/export")

    assert response.status_code == 404
    assert "evaluation report not found" in response.json()["detail"]


def test_index_evaluation_run_requires_ready_search_backend(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    state.search_engine = None
    client = TestClient(create_app(state))

    response = client.post(
        "/index/evaluation/run",
        headers={"X-Role": "it-admin"},
        json={},
    )

    assert response.status_code == 409
    assert "search backend is not ready" in response.json()["detail"]


def _api_state(tmp_path: Path) -> ApiState:
    source_root = tmp_path / "data"
    source_file = source_root / "全量法律" / "law.md"
    _write_text(
        source_file,
        "\n".join(
            [
                "第一条 医疗机构应当保留医保基金审核依据。",
                "第二条 其他条款。",
            ]
        ),
    )
    settings = KnowledgeQuerySettings(
        data_root=source_root,
        index_root=tmp_path / "index",
        database_url="postgresql+psycopg://user:pass@localhost:5433/db",
        model_provider=ModelProviderSettings(
            provider="fake",
            api_key_env="OPENAI_API_KEY",
            embedding_model="fake",
            chat_model="fake",
        ),
        source_collection_weights={
            "medical-insurance-catalog": 1.25,
            "supervision-rules-knowledge": 1.35,
            "risk-negative-list": 1.1,
            "medical-insurance-laws": 1.0,
        },
    )
    state = ApiState.from_settings(settings)
    state.audit_log_store = None
    state.analytics_upload_store = InMemoryAnalyticsUploadStore(
        upload_root=settings.index_root / "analytics-uploads"
    )
    state.document_upload_store = InMemoryDocumentUploadStore(
        upload_root=settings.index_root / "document-uploads"
    )
    state.query_history_store = InMemoryQueryHistoryStore()
    state.search_engine = _search_engine(
        _chunk_id(),
        source_file.relative_to(source_root).as_posix(),
    )
    return state


def _search_engine(chunk_id: UUID, source_path: str) -> HybridSearchEngine:
    provider = DeterministicFakeEmbeddingProvider(dimension=32)
    chunk = ChunkEmbeddingInput(
        chunk_id=chunk_id,
        text="第一条 医疗机构应当保留医保基金审核依据。",
        metadata={
            "source_collection": SourceCollection.MEDICAL_INSURANCE_LAWS.value,
            "locator": {
                "type": "law-article",
                "source_path": source_path,
                "line_start": 1,
                "line_end": 1,
                "article_number": "第一条",
            },
            "index_version_key": "index-v1",
            "source_package_version_key": "package-v1",
            "year": 2024,
            "region": "国家",
            "document_type": "law",
            "business_topic": "fund-supervision",
        },
    )
    vector_index = InMemoryVectorIndex(dimension=provider.dimension)
    vector_index.upsert(build_chunk_embedding_records([chunk], provider=provider))
    bm25_index = InMemoryBM25Index()
    bm25_index.upsert(
        [
            BM25Document(
                chunk_id=chunk.chunk_id,
                text=chunk.text,
                metadata=chunk.metadata,
            )
        ]
    )
    return HybridSearchEngine(
        embedding_provider=provider,
        vector_index=vector_index,
        bm25_index=bm25_index,
        rerank_provider=FakeRerankProvider(),
    )


def _chunk_id() -> UUID:
    return uuid4()


class StaticApiAnswerProvider:
    provider = "fake"
    model_name = "fake-chat"
    provider_version = "v1"

    def generate_answer(self, question: str, citations: Sequence[Citation]) -> str:
        return f"生成模型回答：应核验医保基金审核依据 {citations[0].marker}。"


class FailingQueryHistoryStore:
    def add_query(self, _values: dict[str, object]) -> dict[str, object]:
        raise RuntimeError("history database unavailable")

    def list_queries(self, *, limit: int = 20) -> list[dict[str, object]]:
        _ = limit
        raise RuntimeError("history database unavailable")


def _write_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path
