import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from threading import Barrier
from time import sleep
from typing import cast
from uuid import UUID
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from medical_audit_kb.api.agent_store import SqlAlchemyAgentStore
from medical_audit_kb.api.app import ApiState, create_app
from medical_audit_kb.api.audit_finding_store import SqlAlchemyAuditFindingStore
from medical_audit_kb.api.audit_log_store import SqlAlchemyAuditLogStore
from medical_audit_kb.api.auth_user_store import SqlAlchemyAuthUserStore
from medical_audit_kb.api.project_member_store import InMemoryProjectMemberStore
from medical_audit_kb.api.query_history_store import InMemoryQueryHistoryStore
from medical_audit_kb.api.review_task_store import (
    InMemoryReviewTaskStore,
    JsonFileReviewTaskStore,
    SqlAlchemyReviewTaskStore,
)
from medical_audit_kb.audit.charge_rule_001 import (
    DEFAULT_RULE_VERSION_KEY,
    RULE_KEY,
    build_audit_finding_payloads,
    build_charge_rule_001_fixture,
    evaluate_charge_rule_001,
)
from medical_audit_kb.core.config import KnowledgeQuerySettings, ModelProviderSettings
from medical_audit_kb.db.models import (
    AuditDataSnapshot,
    AuditFinding,
    AuditProject,
    AuditRule,
    AuditRun,
    AuditTask,
    FindingEvidenceItem,
    RuleVersion,
)
from medical_audit_kb.domain.constants import SourceCollection
from medical_audit_kb.indexing.bm25_index import BM25Document, InMemoryBM25Index
from medical_audit_kb.indexing.embeddings import DeterministicFakeEmbeddingProvider
from medical_audit_kb.indexing.vector_index import (
    ChunkEmbeddingInput,
    InMemoryVectorIndex,
    build_chunk_embedding_records,
)
from medical_audit_kb.retrieval.hybrid_search import HybridSearchEngine
from medical_audit_kb.retrieval.rerank import FakeRerankProvider


def test_query_page_renders_form_and_source_filters(tmp_path: Path) -> None:
    client = TestClient(create_app(_api_state(tmp_path)))

    response = client.get("/pages/query")

    assert response.status_code == 200
    assert "引用优先的医保审核知识查询" in response.text
    assert "检索已就绪" in response.text
    assert "来源过滤" in response.text
    assert 'href="#main-content"' in response.text
    assert 'aria-current="page">文档检索' in response.text
    assert 'aria-describedby="question-help"' in response.text
    assert "required" in response.text
    assert SourceCollection.MEDICAL_INSURANCE_LAWS.value in response.text


def test_root_path_renders_chat_workbench(tmp_path: Path) -> None:
    client = TestClient(create_app(_api_state(tmp_path)))

    response = client.get("/")

    assert response.status_code == 200
    assert "AI智能审计管理系统 · AI 对话" in response.text
    assert 'aria-current="page">AI 对话' in response.text


def test_legacy_visible_pages_redirect_when_retired(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MEDICAL_AUDIT_RETIRE_LEGACY_PAGES", "1")
    client = TestClient(create_app(_api_state(tmp_path)))

    cases = {
        "/": "/chat",
        "/pages/chat": "/chat",
        "/pages/query": "/documents",
        "/pages/review-tasks": "/reports",
        "/pages/audit-logs": "/archive",
        "/pages/audit-findings": "/findings",
        "/pages/index-admin": "/knowledge-base",
    }

    for path, expected_location in cases.items():
        response = client.get(
            path,
            headers={"X-Role": "it-admin"},
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert response.headers["location"] == expected_location


def test_graph_workbench_api_returns_readonly_topology(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    client = TestClient(create_app(state))

    response = client.get("/graph/workbench")

    assert response.status_code == 200
    body = response.json()
    assert body["format"] == "graph-workbench-v1"
    assert body["graph_id"] == "SELF-CHECK-FUND-20260607"
    assert body["metrics"]["node_count"] >= 26
    assert body["metrics"]["relation_count"] >= 25
    assert body["metrics"]["node_kind_counts"]["知识库"] >= 25
    assert body["production_side_effect"] == "none"
    assert body["store"] == {"ready": True, "backend": "KnowledgeCatalogGraphBuilder"}
    assert body["nodes"][0]["kind"] == "项目"
    assert body["relations"][0]["sourceId"] == "graph-node-project"
    assert state.operation_logs[-1]["action"] == "graph-workbench-view"


def test_rules_workbench_api_returns_readonly_rule_status(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    client = TestClient(create_app(state))

    response = client.get("/rules/workbench")

    assert response.status_code == 200
    body = response.json()
    assert body["format"] == "rules-workbench-v1"
    assert body["ruleset_id"] == "FUND-USAGE-COMPLIANCE-RULES"
    assert body["metrics"]["rule_count"] == 4
    assert body["metrics"]["enabled_rule_count"] == 1
    assert body["metrics"]["pending_rule_count"] == 3
    assert body["metrics"]["total_finding_count"] == 3
    assert body["metrics"]["blocked_gate_count"] == 1
    assert body["production_side_effect"] == "none"
    assert body["store"] == {"ready": True, "backend": "ReadonlyRulesWorkbenchSeed"}
    assert body["rule_library_items"][0]["code"] == "CHARGE-RULE-001"
    assert body["source_coverages"][0]["sourceCollection"] == "supervision-rules-knowledge"
    assert body["control_gates"][1]["status"] == "阻断"
    assert state.operation_logs[-1]["action"] == "rules-workbench-view"


def test_remediation_workbench_api_returns_readonly_gate_status(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    client = TestClient(create_app(state))

    response = client.get("/remediation/workbench")

    assert response.status_code == 200
    body = response.json()
    assert body["format"] == "remediation-workbench-v1"
    assert body["workbench_id"] == "FUND-USAGE-REMEDIATION"
    assert body["metrics"]["case_count"] == 4
    assert body["metrics"]["active_case_count"] == 3
    assert body["metrics"]["closed_case_count"] == 1
    assert body["metrics"]["pending_evidence_count"] == 3
    assert body["metrics"]["blocked_gate_count"] == 1
    assert body["metrics"]["average_progress"] == 66
    assert body["production_side_effect"] == "none"
    assert body["store"] == {"ready": True, "backend": "ReadonlyRemediationWorkbenchSeed"}
    assert body["remediation_cases"][0]["sourceFinding"] == "FINDING-F044EBD309B659DC"
    assert body["evidence_requests"][1]["status"] == "待上传"
    assert body["closure_gates"][0]["status"] == "阻断"
    assert state.operation_logs[-1]["action"] == "remediation-workbench-view"


def test_archive_workbench_api_returns_readonly_archive_status(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    client = TestClient(create_app(state))

    response = client.get("/archive/workbench")

    assert response.status_code == 200
    body = response.json()
    assert body["format"] == "archive-workbench-v1"
    assert body["archive_id"] == "FUND-USAGE-ARCHIVE"
    assert body["metrics"]["package_count"] == 4
    assert body["metrics"]["archived_package_count"] == 1
    assert body["metrics"]["pending_package_count"] == 3
    assert body["metrics"]["blocked_package_count"] == 1
    assert body["metrics"]["audit_run_count"] == 3
    assert body["metrics"]["signature_count"] == 3
    assert body["metrics"]["policy_count"] == 4
    assert body["metrics"]["latest_archive_run_status"] == "通过"
    assert body["production_side_effect"] == "none"
    assert body["store"] == {"ready": True, "backend": "ReadonlyArchiveWorkbenchSeed"}
    assert body["archive_packages"][0]["archiveNo"] == "ARCHIVE-SELF-CHECK-FUND-202606"
    assert body["audit_runs"][0]["title"] == "archive root 巡检"
    assert body["signature_items"][0]["label"] == "retention-batch-0001.jsonl"
    assert body["policy_items"][1]["value"] == "180 days"
    assert state.operation_logs[-1]["action"] == "archive-workbench-view"


def test_backend_pages_share_product_navigation(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'product-nav.db'}"
    state = _api_state(tmp_path)
    state.audit_finding_store = SqlAlchemyAuditFindingStore(database_url, create_schema=True)
    state.review_task_store = SqlAlchemyReviewTaskStore(database_url)
    client = TestClient(create_app(state))
    client.get("/pages/query", params={"question": "医保基金审核依据"})
    expected_links = (
        ('href="/chat"', "AI 对话"),
        ('href="/agents"', "我的智能体"),
        ('href="/agent-market"', "智能体广场"),
        ('href="/knowledge-base"', "知识库"),
        ('href="/documents"', "文档检索"),
        ('href="/analytics"', "AI 数据分析"),
        ('href="/graph"', "知识图谱"),
        ('href="/reports"', "审计底稿/报告"),
        ('href="/projects"', "项目管理"),
    )
    pages = (
        ("/pages/chat", "AI 对话"),
        ("/pages/query", "文档检索"),
        ("/pages/audit-findings", None),
        ("/pages/review-tasks", "审计底稿/报告"),
        ("/pages/audit-logs", None),
        ("/pages/index-admin", None),
        (f"/pages/preview/{LAW_CHUNK_ID}", None),
    )

    for path, current_label in pages:
        response = client.get(path, headers={"X-Role": "it-admin"})

        assert response.status_code == 200
        assert 'aria-label="AI智能审计管理系统门户导航"' in response.text
        assert 'aria-label="AI智能审计管理系统门户首页"' in response.text
        for href, label in expected_links:
            assert href in response.text
            assert label in response.text
        if current_label is not None:
            assert f'aria-current="page">{current_label}</a>' in response.text


def test_query_page_returns_answer_citations_preview_links_and_log(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    client = TestClient(create_app(state))

    response = client.get(
        "/pages/query",
        params={
            "question": "医保基金审核依据",
            "source_collection": SourceCollection.MEDICAL_INSURANCE_LAWS.value,
        },
    )

    assert response.status_code == 200
    assert "引用型回答" in response.text
    assert "法规依据" in response.text
    assert f"/pages/preview/{LAW_CHUNK_ID}" in response.text
    assert "查询结果摘要" in response.text
    assert "核验原文" in response.text
    assert "chunk" in response.text
    assert "package" in response.text
    assert "复制引用" in response.text
    assert "证据使用边界" in response.text
    assert "人工复核清单" in response.text
    assert "转入对话审证" in response.text
    assert "创建复核任务" in response.text
    assert state.operation_logs[-1]["action"] == "page-query"
    assert state.query_logs[-1]["question"] == "医保基金审核依据"


def test_chat_page_renders_conversation_evidence_and_followups(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    client = TestClient(create_app(state))

    response = client.get("/pages/chat", params={"question": "医保基金审核依据"})

    assert response.status_code == 200
    assert "AI智能审计管理系统 · AI 对话" in response.text
    assert "AI智能审计管理系统" in response.text
    assert "Evidence Command Center" in response.text
    assert "本地证据优先" in response.text
    assert "人工复核门禁" in response.text
    assert "审证流程 · Case Review" in response.text
    assert "审计问题输入" in response.text
    assert "Evidence Dossier" in response.text
    assert "证据卷宗" in response.text
    assert "证据使用边界" in response.text
    assert "复核门禁" in response.text
    assert "人工复核清单" in response.text
    assert "可追溯回答" in response.text
    assert "回答进入底稿或报告前" in response.text
    assert "创建复核任务" in response.text
    assert "导出 Markdown 底稿" in response.text
    assert "导出 Word 底稿" in response.text
    assert "导出 JSON 记录" in response.text
    assert "复制引用" in response.text
    assert "把以上依据整理成审核要点清单" in response.text
    assert f"/pages/preview/{LAW_CHUNK_ID}" in response.text
    assert "<pre>" not in response.text
    assert state.operation_logs[-1]["action"] == "page-chat"


def test_chat_page_records_selected_agent_invocation_without_export_duplication(
    tmp_path: Path,
) -> None:
    state = _api_state(tmp_path)
    state.agent_store = SqlAlchemyAgentStore(
        f"sqlite:///{tmp_path / 'page-agent-invocations.db'}",
        create_schema=True,
    )
    client = TestClient(create_app(state))

    response = client.get(
        "/pages/chat",
        params={
            "question": "医保基金审核依据",
            "agent": "agent-citation-check",
            "project_name": "医保基金使用合规专项自查",
        },
    )
    assert response.status_code == 200
    assert 'name="agent" value="agent-citation-check"' in response.text
    assert 'name="project_name" value="医保基金使用合规专项自查"' in response.text
    assert state.agent_store is not None
    invocations = state.agent_store.list_invocations("agent-citation-check")
    assert len(invocations) == 1
    assert invocations[0]["invocation_source"] == "/pages/chat"
    assert invocations[0]["question"] == "医保基金审核依据"
    assert invocations[0]["metadata"]["project_name"] == "医保基金使用合规专项自查"
    assert state.operation_logs[-2]["action"] == "agent-invocation-create"
    assert state.operation_logs[-1]["action"] == "page-chat"

    export_response = client.get(
        "/pages/chat/export",
        params={
            "question": "医保基金审核依据",
            "agent": "agent-citation-check",
            "project_name": "医保基金使用合规专项自查",
            "format": "json",
        },
    )

    assert export_response.status_code == 200
    assert len(state.agent_store.list_invocations("agent-citation-check")) == 1
    assert state.operation_logs[-1]["action"] == "chat-dossier-export"


def test_chat_dossier_export_returns_json_download_and_records_log(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    client = TestClient(create_app(state))

    response = client.get(
        "/pages/chat/export",
        params={
            "question": "医保基金审核依据",
            "source_collection": SourceCollection.MEDICAL_INSURANCE_LAWS.value,
        },
    )

    assert response.status_code == 200
    assert response.headers["content-disposition"] == (
        'attachment; filename="auditscope-dossier.json"'
    )
    body = response.json()
    assert body["format"] == "audit-dossier-v1"
    assert body["question"] == "医保基金审核依据"
    assert body["review_gate"] == "可进入人工复核"
    assert body["review_notice"] == "该导出为审计线索和人工复核底稿，不替代正式审计结论。"
    assert body["review_checklist"] == [
        "核对引用片段是否完整覆盖问题。",
        "打开原文确认条款上下文。",
        "检查目录、规则、法规版本是否适用。",
        "确认是否还需 HIS 原始凭证补证。",
    ]
    assert body["citation_count"] >= 1
    assert body["citations"][0]["chunk_id"] == str(LAW_CHUNK_ID)
    assert body["citations"][0]["index_version_key"] == "index-v1"
    assert body["citations"][0]["source_package_version_key"] == "package-v1"
    assert body["citations"][0]["preview_url"].endswith(f"/pages/preview/{LAW_CHUNK_ID}")
    assert state.operation_logs[-1]["action"] == "chat-dossier-export"


def test_chat_dossier_export_returns_markdown_download(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    client = TestClient(create_app(state))

    response = client.get(
        "/pages/chat/export",
        params={"question": "医保基金审核依据", "format": "markdown"},
    )

    assert response.status_code == 200
    assert response.headers["content-disposition"] == (
        'attachment; filename="auditscope-dossier.md"'
    )
    assert "# AuditScope 审计底稿导出" in response.text
    assert "## 人工复核清单" in response.text
    assert "## 可追溯回答" in response.text
    assert f"chunk: `{LAW_CHUNK_ID}`" in response.text
    assert "package: `package-v1`" in response.text
    assert "原文链接: http://testserver/pages/preview/" in response.text


def test_chat_dossier_export_returns_docx_download(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    client = TestClient(create_app(state))

    response = client.get(
        "/pages/chat/export",
        params={"question": "医保基金审核依据", "format": "docx"},
    )

    assert response.status_code == 200
    assert response.headers["content-disposition"] == (
        'attachment; filename="auditscope-dossier.docx"'
    )
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    document_xml = _docx_document_xml(response.content)
    assert "AuditScope 审计底稿导出" in document_xml
    assert "医保基金审核依据" in document_xml
    assert str(LAW_CHUNK_ID) in document_xml


def test_report_workpaper_template_registry_returns_docx_metadata(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    client = TestClient(create_app(state))

    response = client.get("/reports/workpaper-templates")

    assert response.status_code == 200
    body = response.json()
    assert body["format"] == "workpaper-template-registry-v1"
    assert body["registry_status"] == "active"
    assert body["count"] == 3
    assert [item["label"] for item in body["template_categories"]] == [
        "计划类",
        "底稿类",
        "取证类",
        "函证类",
        "报告类",
        "整改类",
    ]
    assert [item["availability"] for item in body["template_categories"]] == [
        "awaiting-business-template",
        "active",
        "awaiting-business-template",
        "awaiting-business-template",
        "awaiting-business-template",
        "awaiting-business-template",
    ]
    template_names = {item["name"] for item in body["items"]}
    assert template_names == {
        "费用汇总风险底稿",
        "分类费用复核清单",
        "就诊明细疑点摘要",
    }
    visit_detail = next(item for item in body["items"] if item["id"] == "workpaper-visit-detail")
    assert visit_detail["source_file_name"] == "表3_就诊费用明细表（空白）.xlsx"
    assert "身份证号码" in visit_detail["expected_columns"]
    assert "隐私字段处理记录" in visit_detail["evidence_bindings"]
    assert {item["category_id"] for item in body["items"]} == {"workpaper"}
    assert state.operation_logs[-1]["action"] == "report-workpaper-template-registry-view"


def test_report_workbench_returns_six_categories_and_only_workpaper_templates(
    tmp_path: Path,
) -> None:
    state = _api_state(tmp_path)
    client = TestClient(create_app(state))

    response = client.get("/reports/workbench")

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body["template_categories"]] == [
        "plan",
        "workpaper",
        "evidence",
        "confirmation",
        "report",
        "remediation",
    ]
    assert [item["label"] for item in body["template_categories"]] == [
        "计划类",
        "底稿类",
        "取证类",
        "函证类",
        "报告类",
        "整改类",
    ]
    assert {item["id"] for item in body["workpaper_templates"]} == {
        "workpaper-summary-risk",
        "workpaper-category-review",
        "workpaper-visit-detail",
    }
    assert {item["category_id"] for item in body["workpaper_templates"]} == {
        "workpaper"
    }


@pytest.mark.parametrize(
    ("role", "user_identifier"),
    (
        ("admin", "next-admin"),
        ("director", "next-director"),
        ("member", "next-member"),
    ),
)
def test_report_template_draft_persists_controlled_review_task_for_allowed_roles(
    tmp_path: Path,
    role: str,
    user_identifier: str,
) -> None:
    state = _api_state(tmp_path)
    state.project_member_store = InMemoryProjectMemberStore()
    client = TestClient(create_app(state))
    sensitive_value = "SENTINEL-FIELD-VALUE-MUST-NOT-ENTER-AUDIT-LOG"

    response = client.post(
        "/reports/drafts",
        headers={"X-User-Id": user_identifier, "X-Role": role},
        json={
            "template_id": "workpaper-summary-risk",
            "project_key": "SELF-CHECK-FUND-20260607",
            "field_values": {"人工复核意见": sensitive_value},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["format"] == "report-template-draft-v1"
    assert body["task_id"].startswith("report-draft-")
    assert len(body["task_id"]) <= 64
    assert body["template_id"] == "workpaper-summary-risk"
    assert body["category_id"] == "workpaper"
    assert body["project_key"] == "SELF-CHECK-FUND-20260607"
    assert body["project_href"] == "/projects?project=SELF-CHECK-FUND-20260607"
    assert body["status"] == "pending-review"
    assert body["store"] == {"ready": True, "backend": "JsonFileReviewTaskStore"}
    assert body["formal_report_created"] is False
    assert body["provider_call"] is False
    assert body["audit"] == {
        "status": "local-only",
        "durability": "local-only",
        "local_only": True,
        "intent_recorded": True,
        "completion_recorded": True,
    }
    task = _review_tasks(state)[0]
    assert task["source"] == "report-template-draft"
    assert task["status"] == "pending-review"
    assert task["created_by"] == user_identifier
    dossier = task["dossier"]
    assert isinstance(dossier, dict)
    draft = dossier["report_template_draft"]
    assert draft == {
        "status": "draft",
        "template_id": "workpaper-summary-risk",
        "template_name": "费用汇总风险底稿",
        "category_id": "workpaper",
        "project_key": "SELF-CHECK-FUND-20260607",
        "created_by": user_identifier,
        "user_identifier": user_identifier,
        "field_values": {"人工复核意见": sensitive_value},
    }
    assert [log["action"] for log in state.operation_logs[-2:]] == [
        "report-template-draft-create-intent",
        "report-template-draft-create-completed",
    ]
    assert state.operation_logs[-1]["payload"]["field_count"] == 1
    serialized_operation = json.dumps(state.operation_logs[-1], ensure_ascii=False)
    assert sensitive_value not in serialized_operation
    assert "field_values" not in serialized_operation


def test_report_template_draft_rejects_unknown_template_and_field_without_task(
    tmp_path: Path,
) -> None:
    state = _api_state(tmp_path)
    state.project_member_store = InMemoryProjectMemberStore()
    client = TestClient(create_app(state))
    headers = {"X-User-Id": "next-admin", "X-Role": "admin"}

    unknown_template = client.post(
        "/reports/drafts",
        headers=headers,
        json={
            "template_id": "not-a-template",
            "project_key": "SELF-CHECK-FUND-20260607",
            "field_values": {},
        },
    )
    unknown_field = client.post(
        "/reports/drafts",
        headers=headers,
        json={
            "template_id": "workpaper-summary-risk",
            "project_key": "SELF-CHECK-FUND-20260607",
            "field_values": {"not-an-evidence-binding": "value"},
        },
    )
    nested_field_value = client.post(
        "/reports/drafts",
        headers=headers,
        json={
            "template_id": "workpaper-summary-risk",
            "project_key": "SELF-CHECK-FUND-20260607",
            "field_values": {"人工复核意见": {"nested": "not allowed"}},
        },
    )
    normalized_key_collision = client.post(
        "/reports/drafts",
        headers=headers,
        json={
            "template_id": "workpaper-summary-risk",
            "project_key": "SELF-CHECK-FUND-20260607",
            "field_values": {
                "人工复核意见": "first",
                " 人工复核意见 ": "second",
            },
        },
    )
    too_many_fields = client.post(
        "/reports/drafts",
        headers=headers,
        json={
            "template_id": "workpaper-summary-risk",
            "project_key": "SELF-CHECK-FUND-20260607",
            "field_values": {f"field-{index}": "value" for index in range(33)},
        },
    )

    assert unknown_template.status_code == 404
    assert unknown_template.json()["detail"] == "report template not found"
    assert unknown_field.status_code == 422
    assert unknown_field.json()["detail"] == (
        "field_values contains unsupported evidence binding: not-an-evidence-binding"
    )
    assert nested_field_value.status_code == 422
    assert normalized_key_collision.status_code == 422
    assert too_many_fields.status_code == 422
    assert too_many_fields.json()["detail"][0]["type"] == "too_long"
    assert _review_tasks(state) == []
    assert all(log["action"] != "authorization-denied" for log in state.operation_logs)


@pytest.mark.parametrize(
    ("headers", "expected_status", "expected_reason"),
    (
        (
            {"X-Role": "member"},
            401,
            "X-User-Id header is required",
        ),
        (
            {"X-User-Id": "anonymous", "X-Role": "member"},
            401,
            "X-User-Id header is required",
        ),
        (
            {"X-User-Id": "unrelated-member", "X-Role": "member"},
            404,
            "project not found",
        ),
    ),
)
def test_report_template_draft_hides_project_and_safely_audits_denials(
    tmp_path: Path,
    headers: dict[str, str],
    expected_status: int,
    expected_reason: str,
) -> None:
    state = _api_state(tmp_path)
    state.project_member_store = InMemoryProjectMemberStore()
    client = TestClient(create_app(state))
    sensitive_value = "SENTINEL-DENIED-FIELD-VALUE"

    response = client.post(
        "/reports/drafts",
        headers=headers,
        json={
            "template_id": "workpaper-summary-risk",
            "project_key": "SELF-CHECK-FUND-20260607",
            "field_values": {"人工复核意见": sensitive_value},
        },
    )

    assert response.status_code == expected_status
    assert response.json()["detail"] == expected_reason
    assert _review_tasks(state) == []
    denial = state.operation_logs[-1]
    assert denial["action"] == "authorization-denied"
    assert denial["payload"]["attempted_action"] == "report-template-draft-create"
    assert denial["payload"]["permission"] == "create_report_draft"
    assert denial["payload"]["status_code"] == expected_status
    assert denial["payload"]["auth_scope_type"] == "project"
    assert denial["payload"]["auth_scope_key"] == "SELF-CHECK-FUND-20260607"
    serialized_denial = json.dumps(denial, ensure_ascii=False)
    assert sensitive_value not in serialized_denial
    assert "field_values" not in serialized_denial


def test_report_template_draft_checks_identity_before_template_lookup(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    state.project_member_store = InMemoryProjectMemberStore()
    client = TestClient(create_app(state))

    response = client.post(
        "/reports/drafts",
        headers={"X-Role": "member"},
        json={
            "template_id": "not-a-template",
            "project_key": "SELF-CHECK-FUND-20260607",
            "field_values": {},
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "X-User-Id header is required"
    assert _review_tasks(state) == []
    assert state.operation_logs[-1]["action"] == "authorization-denied"


def test_report_template_draft_hides_unknown_project_and_safely_audits(
    tmp_path: Path,
) -> None:
    state = _api_state(tmp_path)
    state.project_member_store = InMemoryProjectMemberStore()
    client = TestClient(create_app(state))
    sensitive_value = "SENTINEL-UNKNOWN-PROJECT-FIELD-VALUE"

    response = client.post(
        "/reports/drafts",
        headers={"X-User-Id": "next-admin", "X-Role": "admin"},
        json={
            "template_id": "workpaper-summary-risk",
            "project_key": "UNKNOWN-PROJECT",
            "field_values": {"人工复核意见": sensitive_value},
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "project not found"
    assert _review_tasks(state) == []
    denial = state.operation_logs[-1]
    assert denial["action"] == "authorization-denied"
    assert denial["payload"]["auth_scope_key"] == "UNKNOWN-PROJECT"
    serialized_denial = json.dumps(denial, ensure_ascii=False)
    assert sensitive_value not in serialized_denial
    assert "field_values" not in serialized_denial


def test_report_template_draft_rejects_visible_technician_and_safely_audits(
    tmp_path: Path,
) -> None:
    state = _api_state(tmp_path)
    store = InMemoryProjectMemberStore()
    store.add_member(
        "SELF-CHECK-FUND-20260607",
        {
            "user_identifier": "active-technician",
            "name": "可见技术人员",
            "role": "信息科",
            "department": "信息科",
            "status": "在项目中",
        },
    )
    state.project_member_store = store
    client = TestClient(create_app(state))
    sensitive_value = "SENTINEL-TECHNICIAN-FIELD-VALUE"

    response = client.post(
        "/reports/drafts",
        headers={"X-User-Id": "active-technician", "X-Role": "technician"},
        json={
            "template_id": "workpaper-summary-risk",
            "project_key": "SELF-CHECK-FUND-20260607",
            "field_values": {"人工复核意见": sensitive_value},
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "create_report_draft is not allowed"
    assert _review_tasks(state) == []
    denial = state.operation_logs[-1]
    assert denial["action"] == "authorization-denied"
    assert denial["payload"]["effective_role"] == "technician"
    assert denial["payload"]["status_code"] == 403
    serialized_denial = json.dumps(denial, ensure_ascii=False)
    assert sensitive_value not in serialized_denial
    assert "field_values" not in serialized_denial


def test_report_template_draft_does_not_invert_missing_assignment_technician(
    tmp_path: Path,
) -> None:
    state = _api_state(tmp_path)
    state.auth_user_store = SqlAlchemyAuthUserStore(
        f"sqlite:///{tmp_path / 'auth-users.db'}",
        create_schema=True,
    )
    state.auth_user_store.add_user(
        {
            "user_key": "profile-without-assignment",
            "display_name": "无角色分配技术人员",
            "status": "active",
        }
    )
    member_store = InMemoryProjectMemberStore()
    member_store.add_member(
        "SELF-CHECK-FUND-20260607",
        {
            "user_identifier": "profile-without-assignment",
            "name": "无角色分配技术人员",
            "role": "信息科",
            "department": "信息科",
            "status": "在项目中",
        },
    )
    state.project_member_store = member_store
    client = TestClient(create_app(state))
    headers = {
        "X-User-Id": "profile-without-assignment",
        "X-Role": "technician",
        "X-Project-Key": "SELF-CHECK-FUND-20260607",
    }

    session_response = client.get("/auth/session", headers=headers)
    create_response = client.post(
        "/reports/drafts",
        headers=headers,
        json={
            "template_id": "workpaper-summary-risk",
            "project_key": "SELF-CHECK-FUND-20260607",
            "field_values": {"人工复核意见": "不得越权"},
        },
    )

    assert session_response.status_code == 200
    assert session_response.json()["role"] == "member"
    assert session_response.json()["auth_source"] == (
        "persistent_profile_without_project_role"
    )
    assert "create_report_draft" not in session_response.json()["permissions"]
    assert create_response.status_code == 403
    assert _review_tasks(state) == []


@pytest.mark.parametrize(
    ("assigned_role", "expected_status"),
    (("technician", 403), ("member", 200), ("director", 200)),
)
def test_report_template_draft_uses_explicit_project_assignment_permissions(
    tmp_path: Path,
    assigned_role: str,
    expected_status: int,
) -> None:
    user_identifier = f"assigned-{assigned_role}"
    state = _api_state(tmp_path)
    state.auth_user_store = SqlAlchemyAuthUserStore(
        f"sqlite:///{tmp_path / 'auth-users.db'}",
        create_schema=True,
    )
    state.auth_user_store.add_user(
        {"user_key": user_identifier, "display_name": user_identifier, "status": "active"}
    )
    state.auth_user_store.assign_role(
        user_identifier,
        {
            "role": assigned_role,
            "scope_type": "project",
            "scope_key": "SELF-CHECK-FUND-20260607",
        },
    )
    member_store = InMemoryProjectMemberStore()
    member_store.add_member(
        "SELF-CHECK-FUND-20260607",
        {
            "user_identifier": user_identifier,
            "name": user_identifier,
            "role": "审计员",
            "department": "内审部",
            "status": "在项目中",
        },
    )
    state.project_member_store = member_store
    client = TestClient(create_app(state))

    response = client.post(
        "/reports/drafts",
        headers={"X-User-Id": user_identifier, "X-Role": "technician"},
        json={
            "template_id": "workpaper-summary-risk",
            "project_key": "SELF-CHECK-FUND-20260607",
            "field_values": {"人工复核意见": assigned_role},
        },
    )

    assert response.status_code == expected_status
    assert len(_review_tasks(state)) == (1 if expected_status == 200 else 0)


def test_project_report_draft_enforces_formal_action_permissions_and_actor_binding(
    tmp_path: Path,
) -> None:
    state = _api_state(tmp_path)
    state.project_member_store = InMemoryProjectMemberStore()
    client = TestClient(create_app(state))
    member_headers = {"X-User-Id": "next-member", "X-Role": "member"}
    director_headers = {"X-User-Id": "next-director", "X-Role": "director"}
    create_response = client.post(
        "/reports/drafts",
        headers=member_headers,
        json={
            "template_id": "workpaper-summary-risk",
            "project_key": "SELF-CHECK-FUND-20260607",
            "field_values": {"人工复核意见": "待复核"},
        },
    )
    task_id = create_response.json()["task_id"]

    ordinary_update = client.post(
        f"/pages/review-tasks/{task_id}/status",
        headers=member_headers,
        data={
            "status": "needs-evidence",
            "reviewer_note": "普通成员补充复核意见。",
            "conclusion": "需要继续补证。",
            "workpaper_status": "draft",
            "report_title": "普通成员底稿草稿",
            "report_summary": "仅为复核草稿。",
        },
        follow_redirects=False,
    )
    assert ordinary_update.status_code == 303

    member_owner_approval = client.post(
        f"/pages/review-tasks/{task_id}/status",
        headers=member_headers,
        data={
            "status": "not-violation",
            "owner_signoff_status": "approved",
            "owner_confirmed_by": "spoofed-owner",
            "owner_confirmed_at": "2026-07-12T12:00:00Z",
        },
        follow_redirects=False,
    )
    member_close = client.post(
        f"/pages/review-tasks/{task_id}/status",
        headers=member_headers,
        data={"status": "closed"},
        follow_redirects=False,
    )
    member_signoff = client.post(
        f"/pages/review-tasks/{task_id}/report-signoff",
        headers=member_headers,
        data={"signed_by": "spoofed-director"},
        follow_redirects=False,
    )
    member_accepted = client.post(
        f"/pages/review-tasks/{task_id}/rectification",
        headers=member_headers,
        data={"rectification_status": "accepted"},
        follow_redirects=False,
    )
    member_returned = client.post(
        f"/pages/review-tasks/{task_id}/rectification",
        headers=member_headers,
        data={"rectification_status": "returned"},
        follow_redirects=False,
    )
    for response in (
        member_owner_approval,
        member_close,
        member_signoff,
        member_accepted,
        member_returned,
    ):
        assert response.status_code == 403
        assert response.json()["detail"] == "sign_reports is not allowed"

    director_approval = client.post(
        f"/pages/review-tasks/{task_id}/status",
        headers=director_headers,
        data={
            "status": "not-violation",
            "reviewer_note": "主任完成复核。",
            "conclusion": "未发现违规。",
            "owner_signoff_status": "approved",
            "owner_confirmed_by": "spoofed-owner",
            "owner_confirmed_at": "2026-07-12T12:00:00Z",
            "report_title": "未发现违规报告草稿",
            "report_summary": "证据已复核。",
        },
        follow_redirects=False,
    )
    assert director_approval.status_code == 303
    approved_dossier = _review_tasks(state)[0]["dossier"]
    assert isinstance(approved_dossier, dict)
    assert approved_dossier["owner_signoff"]["confirmed_by"] == "next-director"

    director_signoff = client.post(
        f"/pages/review-tasks/{task_id}/report-signoff",
        headers=director_headers,
        data={"signed_by": "spoofed-director", "signoff_note": "主任签发。"},
        follow_redirects=False,
    )
    assert director_signoff.status_code == 303
    signed_dossier = _review_tasks(state)[0]["dossier"]
    assert isinstance(signed_dossier, dict)
    assert signed_dossier["signed_report"]["signed_by"] == "next-director"
    assert state.operation_logs[-1]["payload"]["signed_by"] == "next-director"

    member_pending_rectification = client.post(
        f"/pages/review-tasks/{task_id}/rectification",
        headers=member_headers,
        data={
            "rectification_status": "pending-rectification",
            "progress_note": "普通成员发起整改。",
        },
        follow_redirects=False,
    )
    assert member_pending_rectification.status_code == 303

    member_returned_after_signoff = client.post(
        f"/pages/review-tasks/{task_id}/rectification",
        headers=member_headers,
        data={"rectification_status": "returned"},
        follow_redirects=False,
    )
    assert member_returned_after_signoff.status_code == 403
    director_returned = client.post(
        f"/pages/review-tasks/{task_id}/rectification",
        headers=director_headers,
        data={"rectification_status": "returned", "progress_note": "主任退回。"},
        follow_redirects=False,
    )
    assert director_returned.status_code == 303
    member_accepted_after_signoff = client.post(
        f"/pages/review-tasks/{task_id}/rectification",
        headers=member_headers,
        data={"rectification_status": "accepted"},
        follow_redirects=False,
    )
    assert member_accepted_after_signoff.status_code == 403
    director_accepted = client.post(
        f"/pages/review-tasks/{task_id}/rectification",
        headers=director_headers,
        data={"rectification_status": "accepted", "progress_note": "主任验收。"},
        follow_redirects=False,
    )
    assert director_accepted.status_code == 303
    member_close_after_acceptance = client.post(
        f"/pages/review-tasks/{task_id}/status",
        headers=member_headers,
        data={"status": "closed"},
        follow_redirects=False,
    )
    assert member_close_after_acceptance.status_code == 403
    director_close = client.post(
        f"/pages/review-tasks/{task_id}/status",
        headers=director_headers,
        data={"status": "closed"},
        follow_redirects=False,
    )
    assert director_close.status_code == 303
    assert _review_tasks(state)[0]["status"] == "closed"

    denials = [log for log in state.operation_logs if log["action"] == "authorization-denied"]
    assert denials
    assert {log["payload"]["permission"] for log in denials} == {"sign_reports"}
    serialized_denials = json.dumps(denials, ensure_ascii=False)
    assert "field_values" not in serialized_denials
    assert "普通成员补充复核意见" not in serialized_denials


def test_report_template_draft_fails_closed_when_project_member_store_fails(
    tmp_path: Path,
) -> None:
    class FailingProjectMemberStore:
        def list_members(self, project_key: str) -> list[dict[str, object]]:
            raise SQLAlchemyError("project member store unavailable")

        def add_member(
            self,
            project_key: str,
            values: dict[str, object],
        ) -> dict[str, object]:
            raise SQLAlchemyError("project member store unavailable")

        def member_counts(self) -> dict[str, int]:
            raise SQLAlchemyError("project member store unavailable")

    state = _api_state(tmp_path)
    state.project_member_store = FailingProjectMemberStore()
    client = TestClient(create_app(state))

    response = client.post(
        "/reports/drafts",
        headers={"X-User-Id": "next-member", "X-Role": "member"},
        json={
            "template_id": "workpaper-category-review",
            "project_key": "SELF-CHECK-FUND-20260607",
            "field_values": {"需下钻明细": "待复核"},
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "project membership store is unavailable"
    assert _review_tasks(state) == []
    assert state.operation_logs[-1]["action"] == "report-template-draft-create-unavailable"
    assert "field_values" not in json.dumps(state.operation_logs[-1], ensure_ascii=False)


def test_report_template_draft_admin_does_not_require_member_store_read(tmp_path: Path) -> None:
    class FailingProjectMemberStore:
        def list_members(self, project_key: str) -> list[dict[str, object]]:
            raise SQLAlchemyError("project member store unavailable")

        def add_member(
            self,
            project_key: str,
            values: dict[str, object],
        ) -> dict[str, object]:
            raise SQLAlchemyError("project member store unavailable")

        def member_counts(self) -> dict[str, int]:
            raise SQLAlchemyError("project member store unavailable")

    state = _api_state(tmp_path)
    state.project_member_store = FailingProjectMemberStore()
    client = TestClient(create_app(state))

    response = client.post(
        "/reports/drafts",
        headers={"X-User-Id": "next-admin", "X-Role": "admin"},
        json={
            "template_id": "workpaper-category-review",
            "project_key": "SELF-CHECK-FUND-20260607",
            "field_values": {"需下钻明细": "待复核"},
        },
    )

    assert response.status_code == 200
    assert len(_review_tasks(state)) == 1


def test_project_report_draft_guard_filters_lists_and_hides_all_task_resources(
    tmp_path: Path,
) -> None:
    state = _api_state(tmp_path)
    state.project_member_store = InMemoryProjectMemberStore()
    client = TestClient(create_app(state))
    sentinel = "SENTINEL-PROJECT-DRAFT-MUST-NOT-LEAK"
    create_response = client.post(
        "/reports/drafts",
        headers={"X-User-Id": "next-member", "X-Role": "member"},
        json={
            "template_id": "workpaper-summary-risk",
            "project_key": "SELF-CHECK-FUND-20260607",
            "field_values": {"人工复核意见": sentinel},
        },
    )
    assert create_response.status_code == 200
    task_id = create_response.json()["task_id"]
    unrelated_headers = {"X-User-Id": "unrelated-member", "X-Role": "member"}

    page_response = client.get("/pages/review-tasks", headers=unrelated_headers)
    workbench_response = client.get("/reports/workbench", headers=unrelated_headers)

    assert page_response.status_code == 200
    assert task_id not in page_response.text
    assert "费用汇总风险底稿" not in page_response.text
    assert sentinel not in page_response.text
    assert workbench_response.status_code == 200
    workbench_serialized = json.dumps(workbench_response.json(), ensure_ascii=False)
    assert task_id not in workbench_serialized
    assert "SELF-CHECK-FUND-20260607" not in workbench_serialized
    assert sentinel not in workbench_serialized

    direct_responses = (
        client.get(f"/review-tasks/{task_id}/export", headers=unrelated_headers),
        client.get(f"/review-tasks/{task_id}/report-draft", headers=unrelated_headers),
        client.get(f"/review-tasks/{task_id}/signed-report", headers=unrelated_headers),
        client.get(
            f"/review-tasks/{task_id}/rectification/export",
            headers=unrelated_headers,
        ),
        client.get(
            f"/review-tasks/{task_id}/attachments/attachment-hidden/download",
            headers=unrelated_headers,
        ),
        client.get(f"/review-tasks/{task_id}/export"),
    )
    write_responses = (
        client.post(
            f"/pages/review-tasks/{task_id}/status",
            headers=unrelated_headers,
            data={"status": "closed"},
            follow_redirects=False,
        ),
        client.post(
            f"/pages/review-tasks/{task_id}/attachments",
            headers=unrelated_headers,
            files={"attachment_file": ("hidden.txt", b"hidden", "text/plain")},
            follow_redirects=False,
        ),
        client.post(
            f"/pages/review-tasks/{task_id}/report-signoff",
            headers=unrelated_headers,
            data={"signed_by": "unrelated"},
            follow_redirects=False,
        ),
        client.post(
            f"/pages/review-tasks/{task_id}/rectification",
            headers=unrelated_headers,
            data={"rectification_status": "pending-rectification"},
            follow_redirects=False,
        ),
    )
    for response in (*direct_responses, *write_responses):
        assert response.status_code == 404
        assert response.json()["detail"] == "review task not found"

    assert len(_review_tasks(state)) == 1
    denial_logs = [
        log for log in state.operation_logs if log["action"] == "authorization-denied"
    ]
    assert len(denial_logs) >= 10
    serialized_denials = json.dumps(denial_logs, ensure_ascii=False)
    assert sentinel not in serialized_denials
    assert "field_values" not in serialized_denials


def test_project_report_draft_resource_guard_fails_closed_on_member_store_error(
    tmp_path: Path,
) -> None:
    class FailingProjectMemberStore:
        def list_members(self, project_key: str) -> list[dict[str, object]]:
            raise SQLAlchemyError("project member store unavailable")

        def add_member(
            self,
            project_key: str,
            values: dict[str, object],
        ) -> dict[str, object]:
            raise SQLAlchemyError("project member store unavailable")

        def member_counts(self) -> dict[str, int]:
            raise SQLAlchemyError("project member store unavailable")

    state = _api_state(tmp_path)
    state.project_member_store = InMemoryProjectMemberStore()
    client = TestClient(create_app(state))
    create_response = client.post(
        "/reports/drafts",
        headers={"X-User-Id": "next-admin", "X-Role": "admin"},
        json={
            "template_id": "workpaper-summary-risk",
            "project_key": "SELF-CHECK-FUND-20260607",
            "field_values": {"人工复核意见": "受控草稿"},
        },
    )
    task_id = create_response.json()["task_id"]
    state.project_member_store = FailingProjectMemberStore()

    member_response = client.get(
        f"/review-tasks/{task_id}/export",
        headers={"X-User-Id": "next-member", "X-Role": "member"},
    )
    member_list_response = client.get(
        "/pages/review-tasks",
        headers={"X-User-Id": "next-member", "X-Role": "member"},
    )
    admin_response = client.get(
        f"/review-tasks/{task_id}/export",
        headers={"X-User-Id": "next-admin", "X-Role": "admin"},
    )

    assert member_response.status_code == 503
    assert member_response.json()["detail"] == "project membership store is unavailable"
    assert member_list_response.status_code == 503
    assert admin_response.status_code == 200
    availability_logs = [
        log
        for log in state.operation_logs
        if log["action"] == "review-task-project-visibility-unavailable"
    ]
    assert len(availability_logs) == 2
    assert "field_values" not in json.dumps(availability_logs, ensure_ascii=False)


def test_controlled_auth_legacy_review_task_is_admin_or_creator_only(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    state.review_task_store = InMemoryReviewTaskStore(
        tasks=[
            {
                "task_id": "legacy-controlled-task",
                "created_at": "2026-07-12T00:00:00Z",
                "updated_at": "2026-07-12T00:00:00Z",
                "status": "pending-review",
                "status_label": "待复核",
                "question": "受控 legacy task",
                "citation_count": 0,
                "review_gate": "待人工复核",
                "confidence_label": "待复核",
                "fallback_label": "legacy",
                "created_by": "legacy-creator",
                "assigned_to": "",
                "reviewer_note": "",
                "conclusion": "",
                "source": "legacy-test",
                "dossier": {"format": "audit-finding-dossier-v1"},
            }
        ]
    )
    client = TestClient(create_app(state, enforce_controlled_api_auth=True))

    def headers(user_identifier: str, role: str) -> dict[str, str]:
        return {
            "X-User-Id": user_identifier,
            "X-Role": role,
            "X-Tenant-Id": "hospital-demo",
        }

    creator_response = client.get(
        "/review-tasks/legacy-controlled-task/export",
        headers=headers("legacy-creator", "member"),
    )
    admin_response = client.get(
        "/review-tasks/legacy-controlled-task/export",
        headers=headers("next-admin", "admin"),
    )
    unrelated_response = client.get(
        "/review-tasks/legacy-controlled-task/export",
        headers=headers("unrelated-member", "member"),
    )
    unrelated_page = client.get(
        "/pages/review-tasks",
        headers=headers("unrelated-member", "member"),
    )
    unrelated_workbench = client.get(
        "/reports/workbench",
        headers=headers("unrelated-member", "member"),
    )

    assert creator_response.status_code == 200
    assert admin_response.status_code == 200
    assert unrelated_response.status_code == 404
    assert "legacy-controlled-task" not in unrelated_page.text
    assert unrelated_workbench.json()["report_entries"] == []


def test_legacy_formal_actions_require_authenticated_sign_report_actor(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    state.review_task_store = InMemoryReviewTaskStore(
        tasks=[
            {
                "task_id": "legacy-formal-task",
                "created_at": "2026-07-12T00:00:00Z",
                "updated_at": "2026-07-12T00:00:00Z",
                "status": "not-violation",
                "status_label": "未发现违规",
                "question": "legacy formal task",
                "citation_count": 0,
                "review_gate": "待人工复核",
                "confidence_label": "待复核",
                "fallback_label": "legacy",
                "created_by": "legacy-creator",
                "assigned_to": "",
                "reviewer_note": "已复核",
                "conclusion": "未发现违规",
                "source": "legacy-test",
                "dossier": {"format": "audit-finding-dossier-v1"},
            }
        ]
    )
    client = TestClient(create_app(state))

    approval = client.post(
        "/pages/review-tasks/legacy-formal-task/status",
        data={"status": "not-violation", "owner_signoff_status": "approved"},
        follow_redirects=False,
    )
    signoff = client.post(
        "/pages/review-tasks/legacy-formal-task/report-signoff",
        data={"signed_by": "anonymous-spoof"},
        follow_redirects=False,
    )
    close = client.post(
        "/pages/review-tasks/legacy-formal-task/status",
        data={"status": "closed"},
        follow_redirects=False,
    )

    assert [approval.status_code, signoff.status_code, close.status_code] == [403, 403, 403]
    assert all(response.json()["detail"] == "sign_reports is not allowed" for response in (
        approval,
        signoff,
        close,
    ))


@pytest.mark.parametrize("scope_type", ("project", "department"))
def test_scoped_admin_cannot_bypass_controlled_legacy_task_scope(
    tmp_path: Path,
    scope_type: str,
) -> None:
    state = _api_state(tmp_path)
    state.review_task_store = InMemoryReviewTaskStore(
        tasks=[
            {
                "task_id": "legacy-global-task",
                "created_at": "2026-07-12T00:00:00Z",
                "updated_at": "2026-07-12T00:00:00Z",
                "status": "pending-review",
                "status_label": "待复核",
                "question": "global legacy task",
                "citation_count": 0,
                "review_gate": "待人工复核",
                "confidence_label": "待复核",
                "fallback_label": "legacy",
                "created_by": "legacy-creator",
                "assigned_to": "",
                "reviewer_note": "",
                "conclusion": "",
                "source": "legacy-test",
                "dossier": {"format": "audit-finding-dossier-v1"},
            }
        ]
    )
    state.auth_user_store = SqlAlchemyAuthUserStore(
        f"sqlite:///{tmp_path / 'auth-users.db'}",
        create_schema=True,
    )
    user_identifier = f"{scope_type}-admin"
    state.auth_user_store.add_user(
        {"user_key": user_identifier, "display_name": user_identifier, "status": "active"}
    )
    assignment: dict[str, object] = {"role": "admin", "scope_type": scope_type}
    if scope_type == "project":
        assignment["scope_key"] = "SELF-CHECK-FUND-20260607"
    else:
        assignment["scope_key"] = "audit-office"
    state.auth_user_store.assign_role(user_identifier, assignment)
    client = TestClient(create_app(state, enforce_controlled_api_auth=True))
    headers = {
        "X-User-Id": user_identifier,
        "X-Role": "admin",
        "X-Tenant-Id": "hospital-demo",
        "X-Project-Key": "SELF-CHECK-FUND-20260607",
    }

    direct = client.get("/review-tasks/legacy-global-task/export", headers=headers)
    listing = client.get("/reports/workbench", headers=headers)
    write = client.post(
        "/pages/review-tasks/legacy-global-task/status",
        headers=headers,
        data={"status": "needs-evidence"},
        follow_redirects=False,
    )

    assert direct.status_code == 404
    assert listing.json()["report_entries"] == []
    assert write.status_code == 404


def test_review_task_list_visibility_caches_membership_and_aggregates_hidden_audit(
    tmp_path: Path,
) -> None:
    class CountingProjectMemberStore(InMemoryProjectMemberStore):
        def __init__(self) -> None:
            super().__init__()
            self.list_calls = 0

        def list_members(self, project_key: str) -> list[dict[str, object]]:
            self.list_calls += 1
            return super().list_members(project_key)

    tasks = []
    for index in range(20):
        tasks.append(
            {
                "task_id": f"project-cache-task-{index}",
                "created_at": "2026-07-12T00:00:00Z",
                "updated_at": "2026-07-12T00:00:00Z",
                "status": "pending-review",
                "status_label": "待复核",
                "question": f"project task {index}",
                "citation_count": 0,
                "review_gate": "待人工复核",
                "confidence_label": "待复核",
                "fallback_label": "template",
                "created_by": "next-member",
                "assigned_to": "",
                "reviewer_note": "",
                "conclusion": "",
                "source": "report-template-draft",
                "dossier": {
                    "format": "report-template-draft-dossier-v1",
                    "report_template_draft": {
                        "project_key": "SELF-CHECK-FUND-20260607"
                    },
                },
            }
        )
    state = _api_state(tmp_path)
    state.review_task_store = InMemoryReviewTaskStore(tasks=tasks)
    counting_store = CountingProjectMemberStore()
    state.project_member_store = counting_store
    client = TestClient(create_app(state))

    visible = client.get(
        "/reports/workbench",
        headers={"X-User-Id": "next-member", "X-Role": "member"},
    )
    assert visible.status_code == 200
    assert len(visible.json()["report_entries"]) == 20
    assert counting_store.list_calls <= 4

    counting_store.list_calls = 0
    state.operation_logs.clear()
    hidden = client.get(
        "/reports/workbench",
        headers={"X-User-Id": "unrelated-member", "X-Role": "member"},
    )
    assert hidden.status_code == 200
    assert hidden.json()["report_entries"] == []
    assert counting_store.list_calls <= 4
    filtered_events = [
        log for log in state.operation_logs if log["action"] == "review-task-list-filtered"
    ]
    assert len(filtered_events) == 1
    assert filtered_events[0]["payload"]["hidden_count"] == 20
    assert all(log["action"] != "authorization-denied" for log in state.operation_logs)


def test_report_template_draft_owner_can_export_json_markdown_and_docx(
    tmp_path: Path,
) -> None:
    state = _api_state(tmp_path)
    state.project_member_store = InMemoryProjectMemberStore()
    client = TestClient(create_app(state), raise_server_exceptions=False)
    headers = {"X-User-Id": "next-member", "X-Role": "member"}
    create_response = client.post(
        "/reports/drafts",
        headers=headers,
        json={
            "template_id": "workpaper-summary-risk",
            "project_key": "SELF-CHECK-FUND-20260607",
            "field_values": {
                "费用分类汇总": "住院费用汇总",
                "人工复核意见": "待核验基金支付结构",
            },
        },
    )
    assert create_response.status_code == 200
    task_id = create_response.json()["task_id"]

    json_response = client.get(f"/review-tasks/{task_id}/export", headers=headers)
    markdown_response = client.get(
        f"/review-tasks/{task_id}/export",
        headers=headers,
        params={"format": "markdown"},
    )
    docx_response = client.get(
        f"/review-tasks/{task_id}/export",
        headers=headers,
        params={"format": "docx"},
    )
    page_response = client.get("/pages/review-tasks", headers=headers)
    workbench_response = client.get("/reports/workbench", headers=headers)

    assert json_response.status_code == 200
    json_body = json_response.json()
    assert json_body["dossier"]["format"] == "report-template-draft-dossier-v1"
    assert json_body["dossier"]["report_template_draft"]["template_id"] == (
        "workpaper-summary-risk"
    )
    assert markdown_response.status_code == 200
    assert "# AuditScope 模板底稿草稿" in markdown_response.text
    assert "费用汇总风险底稿" in markdown_response.text
    assert "住院费用汇总" in markdown_response.text
    assert docx_response.status_code == 200
    assert "AuditScope 模板底稿草稿" in _docx_document_xml(docx_response.content)
    assert task_id in page_response.text
    task_docx_href = workbench_response.json()["report_entries"][0]["download_links"][
        "task_docx"
    ]
    task_docx_response = client.get(task_docx_href, headers=headers)
    assert task_docx_response.status_code == 200


def test_report_template_draft_intent_audit_failure_creates_no_task(tmp_path: Path) -> None:
    class FailingAuditLogStore:
        def add_event(self, action: str, payload: dict[str, object]) -> dict[str, object]:
            raise SQLAlchemyError("audit store unavailable")

    state = _api_state(tmp_path)
    state.project_member_store = InMemoryProjectMemberStore()
    state.audit_log_store = FailingAuditLogStore()
    client = TestClient(create_app(state), raise_server_exceptions=False)
    sentinel = "SENTINEL-INTENT-AUDIT-FAILURE"

    response = client.post(
        "/reports/drafts",
        headers={"X-User-Id": "next-member", "X-Role": "member"},
        json={
            "template_id": "workpaper-summary-risk",
            "project_key": "SELF-CHECK-FUND-20260607",
            "field_values": {"人工复核意见": sentinel},
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "report draft audit is unavailable"
    assert _review_tasks(state) == []
    assert state.operation_logs[-1]["action"] == "report-template-draft-create-unavailable"
    serialized_logs = json.dumps(state.operation_logs, ensure_ascii=False)
    assert sentinel not in serialized_logs
    assert "field_values" not in serialized_logs


def test_report_template_draft_completion_audit_failure_returns_degraded_success(
    tmp_path: Path,
) -> None:
    class CompletionFailingAuditLogStore:
        def __init__(self) -> None:
            self.calls = 0

        def add_event(self, action: str, payload: dict[str, object]) -> dict[str, object]:
            self.calls += 1
            if self.calls == 1:
                return {"action": action, "payload": dict(payload)}
            raise SQLAlchemyError("completion audit unavailable")

    state = _api_state(tmp_path)
    state.project_member_store = InMemoryProjectMemberStore()
    state.audit_log_store = CompletionFailingAuditLogStore()
    client = TestClient(create_app(state), raise_server_exceptions=False)
    sentinel = "SENTINEL-COMPLETION-AUDIT-FAILURE"

    response = client.post(
        "/reports/drafts",
        headers={"X-User-Id": "next-member", "X-Role": "member"},
        json={
            "template_id": "workpaper-summary-risk",
            "project_key": "SELF-CHECK-FUND-20260607",
            "field_values": {"人工复核意见": sentinel},
        },
    )

    assert response.status_code == 200
    assert response.json()["audit"] == {
        "status": "degraded",
        "durability": "intent-only",
        "local_only": False,
        "intent_recorded": True,
        "completion_recorded": False,
    }
    assert response.json()["formal_report_created"] is False
    assert response.json()["provider_call"] is False
    assert len(_review_tasks(state)) == 1
    assert state.operation_logs[-1]["action"] == (
        "report-template-draft-create-audit-degraded"
    )
    serialized_logs = json.dumps(state.operation_logs, ensure_ascii=False)
    assert sentinel not in serialized_logs
    assert "field_values" not in serialized_logs


def test_report_template_draft_persistent_audit_reports_durable_ready(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    state.project_member_store = InMemoryProjectMemberStore()
    state.audit_log_store = SqlAlchemyAuditLogStore(
        f"sqlite:///{tmp_path / 'audit-events.db'}",
        create_schema=True,
    )
    client = TestClient(create_app(state))

    response = client.post(
        "/reports/drafts",
        headers={"X-User-Id": "next-member", "X-Role": "member"},
        json={
            "template_id": "workpaper-summary-risk",
            "project_key": "SELF-CHECK-FUND-20260607",
            "field_values": {"人工复核意见": "持久审计"},
        },
    )

    assert response.status_code == 200
    assert response.json()["audit"] == {
        "status": "ready",
        "durability": "durable",
        "local_only": False,
        "intent_recorded": True,
        "completion_recorded": True,
    }
    events = state.audit_log_store.list_events(limit=10)
    assert {event["action"] for event in events} >= {
        "report-template-draft-create-intent",
        "report-template-draft-create-completed",
    }


@pytest.mark.parametrize(
    "case",
    ("intent", "authorization-denial", "best-effort-availability"),
)
def test_non_sql_audit_programmer_errors_are_not_disguised_as_degraded(
    tmp_path: Path,
    case: str,
) -> None:
    class ProgrammerErrorAuditStore:
        def add_event(self, action: str, payload: dict[str, object]) -> dict[str, object]:
            raise RuntimeError("programmer error")

    class FailingProjectMemberStore:
        def list_members(self, project_key: str) -> list[dict[str, object]]:
            raise SQLAlchemyError("project member store unavailable")

        def add_member(
            self,
            project_key: str,
            values: dict[str, object],
        ) -> dict[str, object]:
            raise SQLAlchemyError("project member store unavailable")

        def member_counts(self) -> dict[str, int]:
            raise SQLAlchemyError("project member store unavailable")

    state = _api_state(tmp_path)
    state.review_task_store = JsonFileReviewTaskStore(
        tmp_path / f"{case}-review-tasks.json"
    )
    state.project_member_store = (
        FailingProjectMemberStore()
        if case == "best-effort-availability"
        else InMemoryProjectMemberStore()
    )
    state.audit_log_store = ProgrammerErrorAuditStore()
    client = TestClient(create_app(state), raise_server_exceptions=False)
    headers = {"X-User-Id": "next-member", "X-Role": "member"}
    if case == "authorization-denial":
        headers = {"X-Role": "member"}

    response = client.post(
        "/reports/drafts",
        headers=headers,
        json={
            "template_id": "workpaper-summary-risk",
            "project_key": "SELF-CHECK-FUND-20260607",
            "field_values": {"人工复核意见": "programmer error must surface"},
        },
    )

    assert response.status_code == 500
    assert _review_tasks(state) == []
    assert all("degraded" not in str(log["action"]) for log in state.operation_logs)


def test_report_and_project_task_paths_require_configured_stores(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    state.project_member_store = InMemoryProjectMemberStore()
    state.review_task_store = None
    client = TestClient(create_app(state))
    payload = {
        "template_id": "workpaper-summary-risk",
        "project_key": "SELF-CHECK-FUND-20260607",
        "field_values": {"人工复核意见": "no implicit store"},
    }

    no_review_store_create = client.post(
        "/reports/drafts",
        headers={"X-User-Id": "next-member", "X-Role": "member"},
        json=payload,
    )
    state.review_task_store = InMemoryReviewTaskStore()
    state.project_member_store = None
    no_member_store_create = client.post(
        "/reports/drafts",
        headers={"X-User-Id": "next-member", "X-Role": "member"},
        json=payload,
    )
    state.review_task_store = None
    no_review_store_workbench = client.get(
        "/reports/workbench",
        headers={"X-User-Id": "next-admin", "X-Role": "admin"},
    )

    assert no_review_store_create.status_code == 503
    assert no_member_store_create.status_code == 503
    assert no_review_store_workbench.status_code == 503
    assert state.review_task_store is None


def test_template_renderer_contains_untrusted_multiline_values_as_structure_safe_block(
    tmp_path: Path,
) -> None:
    state = _api_state(tmp_path)
    state.project_member_store = InMemoryProjectMemberStore()
    client = TestClient(create_app(state), raise_server_exceptions=False)
    headers = {"X-User-Id": "next-member", "X-Role": "member"}
    untrusted = "line one\n# Injected Heading\n```\nmalicious fence\n```"
    create_response = client.post(
        "/reports/drafts",
        headers=headers,
        json={
            "template_id": "workpaper-summary-risk",
            "project_key": "SELF-CHECK-FUND-20260607",
            "field_values": {"人工复核意见": untrusted},
        },
    )
    task_id = create_response.json()["task_id"]

    markdown = client.get(
        f"/review-tasks/{task_id}/export",
        headers=headers,
        params={"format": "markdown"},
    )
    docx = client.get(
        f"/review-tasks/{task_id}/export",
        headers=headers,
        params={"format": "docx"},
    )

    assert markdown.status_code == 200
    assert "\n# Injected Heading\n" not in markdown.text
    assert "\n```\n" not in markdown.text
    assert "    # Injected Heading" in markdown.text
    assert "    ```" in markdown.text
    assert docx.status_code == 200
    document_xml = _docx_document_xml(docx.content)
    assert "Injected Heading" in document_xml
    assert "malicious fence" in document_xml


def test_report_template_draft_concurrent_requests_use_distinct_ids_and_persist_both(
    tmp_path: Path,
) -> None:
    class InterleavingReviewTaskStore:
        def __init__(self) -> None:
            self.delegate = InMemoryReviewTaskStore()
            self.barrier = Barrier(2)

        def list_tasks(self) -> list[dict[str, object]]:
            return self.delegate.list_tasks()

        def next_task_id(self) -> str:
            return self.delegate.next_task_id()

        def add_task(self, task: dict[str, object]) -> dict[str, object]:
            self.barrier.wait(timeout=5)
            return self.delegate.add_task(task)

        def get_task(self, task_id: str) -> dict[str, object]:
            return self.delegate.get_task(task_id)

        def update_task(
            self,
            task_id: str,
            values: dict[str, object],
        ) -> dict[str, object]:
            return self.delegate.update_task(task_id, values)

    state = _api_state(tmp_path)
    state.project_member_store = InMemoryProjectMemberStore()
    state.review_task_store = InterleavingReviewTaskStore()
    app = create_app(state)

    def create(index: int) -> object:
        with TestClient(app) as client:
            return client.post(
                "/reports/drafts",
                headers={"X-User-Id": "next-member", "X-Role": "member"},
                json={
                    "template_id": "workpaper-summary-risk",
                    "project_key": "SELF-CHECK-FUND-20260607",
                    "field_values": {"人工复核意见": f"draft-{index}"},
                },
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(create, (1, 2)))

    assert [response.status_code for response in responses] == [200, 200]
    task_ids = [response.json()["task_id"] for response in responses]
    assert len(set(task_ids)) == 2
    assert all(task_id.startswith("report-draft-") for task_id in task_ids)
    assert {str(task["task_id"]) for task in _review_tasks(state)} == set(task_ids)


def test_review_task_stores_serialize_same_instance_concurrent_writes(tmp_path: Path) -> None:
    class SlowJsonFileReviewTaskStore(JsonFileReviewTaskStore):
        def _write_tasks(self, tasks: list[dict[str, object]]) -> None:
            sleep(0.05)
            super()._write_tasks(tasks)

    json_store = SlowJsonFileReviewTaskStore(tmp_path / "concurrent-review-tasks.json")
    json_barrier = Barrier(2)

    def add_json(index: int) -> None:
        json_barrier.wait(timeout=5)
        json_store.add_task({"task_id": f"concurrent-json-{index}"})

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(add_json, (1, 2)))

    assert {task["task_id"] for task in json_store.list_tasks()} == {
        "concurrent-json-1",
        "concurrent-json-2",
    }

    memory_store = InMemoryReviewTaskStore()
    memory_barrier = Barrier(2)

    def add_duplicate_memory(_: int) -> str:
        memory_barrier.wait(timeout=5)
        try:
            memory_store.add_task({"task_id": "same-memory-id"})
        except ValueError:
            return "duplicate"
        return "created"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(add_duplicate_memory, (1, 2)))

    assert sorted(outcomes) == ["created", "duplicate"]
    assert len(memory_store.list_tasks()) == 1


def test_chat_dossier_export_fails_when_backend_is_not_ready(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    state.search_engine = None
    client = TestClient(create_app(state))

    response = client.get("/pages/chat/export", params={"question": "医保基金审核依据"})

    assert response.status_code == 409
    assert response.json()["detail"] == "检索引擎尚未初始化。"


def test_review_tasks_page_renders_empty_state(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    client = TestClient(create_app(state))

    response = client.get("/pages/review-tasks")

    assert response.status_code == 200
    assert "AI智能审计管理系统 · 审计底稿/报告" in response.text
    assert "门户化复核工作区" in response.text
    assert "暂无复核任务" in response.text
    assert "从对话审证创建复核任务" in response.text
    assert 'aria-current="page">审计底稿/报告' in response.text
    assert state.operation_logs[-1]["action"] == "page-review-tasks-view"


def test_review_task_create_update_and_export_flow(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    client = TestClient(create_app(state))
    director_headers = {"X-User-Id": "next-director", "X-Role": "director"}

    create_response = client.post(
        "/pages/review-tasks/create",
        data={
            "question": "医保基金审核依据",
            "source_collection": SourceCollection.MEDICAL_INSURANCE_LAWS.value,
        },
        follow_redirects=False,
    )

    assert create_response.status_code == 303
    assert create_response.headers["location"] == "/pages/review-tasks"
    assert len(_review_tasks(state)) == 1
    task = _review_tasks(state)[0]
    assert task["task_id"] == "review-task-0001"
    assert task["status"] == "pending-review"
    assert task["status_label"] == "待复核"
    assert task["question"] == "医保基金审核依据"
    citation_count = task["citation_count"]
    assert isinstance(citation_count, int)
    assert citation_count >= 1
    assert str(state.operation_logs[-1]["action"]) == "review-task-create"

    page_response = client.get("/pages/review-tasks")
    assert page_response.status_code == 200
    assert "review-task-0001" in page_response.text
    assert "医保基金审核依据" in page_response.text
    assert "待复核" in page_response.text
    assert "导出任务 Markdown" in page_response.text
    assert "导出任务 JSON" in page_response.text
    assert "报告门禁预检" in page_response.text
    assert "底稿与负责人确认" in page_response.text
    assert "附件登记与报告草稿" in page_response.text
    assert "报告草稿需先通过门禁" in page_response.text

    blocked_report_response = client.get("/review-tasks/review-task-0001/report-draft")
    assert blocked_report_response.status_code == 409
    assert blocked_report_response.json()["detail"] == ("review task is not ready for report draft")
    blocked_signoff_response = client.post(
        "/pages/review-tasks/review-task-0001/report-signoff",
        headers=director_headers,
        data={"signed_by": "审计科负责人A"},
        follow_redirects=False,
    )
    assert blocked_signoff_response.status_code == 409

    update_response = client.post(
        "/pages/review-tasks/review-task-0001/status",
        headers=director_headers,
        data={
            "status": "confirmed-violation",
            "assigned_to": "审计员A",
            "reviewer_note": "引用已覆盖规则依据，需补 HIS 原始凭证。",
            "conclusion": "疑似违规线索成立，进入人工复核。",
            "workpaper_status": "ready",
            "workpaper_id": "workpaper-20260604-001",
            "workpaper_note": "底稿已核对引用、原文和 HIS 凭证位置。",
            "owner_signoff_status": "approved",
            "owner_confirmed_by": "审计科负责人A",
            "owner_confirmed_at": "2026-06-04T12:00:00Z",
            "attachment_manifest": (
                "HIS收费明细导出 | /evidence/his-charge-detail.csv | 已脱敏\n"
                "复核签字单 | /evidence/signoff.pdf | 负责人确认"
            ),
            "report_title": "同就诊同项目重复收费复核报告草稿",
            "report_summary": "本任务确认重复收费线索成立，证据链已闭合。",
            "rectification_request": "请责任科室核对收费明细并提交整改说明。",
        },
        follow_redirects=False,
    )

    assert update_response.status_code == 303
    updated_task = _review_tasks(state)[0]
    assert updated_task["status"] == "confirmed-violation"
    assert updated_task["status_label"] == "确认违规"
    assert updated_task["assigned_to"] == "审计员A"
    assert updated_task["reviewer_note"] == "引用已覆盖规则依据，需补 HIS 原始凭证。"
    assert updated_task["conclusion"] == "疑似违规线索成立，进入人工复核。"
    dossier = updated_task["dossier"]
    assert isinstance(dossier, dict)
    assert dossier["workpaper"]["status"] == "ready"
    assert dossier["workpaper"]["workpaper_id"] == "workpaper-20260604-001"
    assert dossier["owner_signoff"]["status"] == "approved"
    assert dossier["owner_signoff"]["confirmed_by"] == "next-director"
    assert dossier["attachments"][0]["title"] == "HIS收费明细导出"
    assert dossier["attachments"][1]["title"] == "复核签字单"
    assert dossier["report_draft"]["title"] == "同就诊同项目重复收费复核报告草稿"
    assert str(state.operation_logs[-1]["action"]) == "review-task-status-update"

    upload_content = b"charge_id,amount\nCD0001,100\n"
    upload_response = client.post(
        "/pages/review-tasks/review-task-0001/attachments",
        data={
            "attachment_title": "HIS收费明细上传归档",
            "attachment_note": "测试上传归档文件",
        },
        files={
            "attachment_file": (
                "his-charge-detail.csv",
                upload_content,
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    assert upload_response.status_code == 303
    uploaded_task = _review_tasks(state)[0]
    uploaded_dossier = uploaded_task["dossier"]
    assert isinstance(uploaded_dossier, dict)
    uploaded_attachments = uploaded_dossier["attachments"]
    assert isinstance(uploaded_attachments, list)
    uploaded_attachment = uploaded_attachments[-1]
    assert uploaded_attachment["status"] == "uploaded"
    assert uploaded_attachment["title"] == "HIS收费明细上传归档"
    assert uploaded_attachment["original_filename"] == "his-charge-detail.csv"
    assert uploaded_attachment["byte_size"] == len(upload_content)
    assert uploaded_attachment["sha256"] == hashlib.sha256(upload_content).hexdigest()
    assert str(uploaded_attachment["storage_path"]).startswith(
        "review-task-attachments/review-task-0001/"
    )
    archived_path = state.settings.index_root / str(uploaded_attachment["storage_path"])
    assert archived_path.read_bytes() == upload_content
    assert str(state.operation_logs[-1]["action"]) == "review-task-attachment-upload"

    download_response = client.get(
        f"/review-tasks/review-task-0001/attachments/"
        f"{uploaded_attachment['attachment_id']}/download"
    )
    assert download_response.status_code == 200
    assert download_response.content == upload_content
    assert download_response.headers["content-type"].startswith("text/csv")
    assert str(state.operation_logs[-1]["action"]) == "review-task-attachment-download"

    preserve_upload_response = client.post(
        "/pages/review-tasks/review-task-0001/status",
        headers=director_headers,
        data={
            "status": "confirmed-violation",
            "assigned_to": "审计员A",
            "reviewer_note": "引用已覆盖规则依据，需补 HIS 原始凭证。",
            "conclusion": "疑似违规线索成立，进入人工复核。",
            "workpaper_status": "ready",
            "workpaper_id": "workpaper-20260604-001",
            "workpaper_note": "底稿已核对引用、原文和 HIS 凭证位置。",
            "owner_signoff_status": "approved",
            "owner_confirmed_by": "审计科负责人A",
            "owner_confirmed_at": "2026-06-04T12:00:00Z",
            "attachment_manifest": (
                "HIS收费明细导出 | /evidence/his-charge-detail.csv | 已脱敏\n"
                "复核签字单 | /evidence/signoff.pdf | 负责人确认"
            ),
            "report_title": "同就诊同项目重复收费复核报告草稿",
            "report_summary": "本任务确认重复收费线索成立，证据链已闭合。",
            "rectification_request": "请责任科室核对收费明细并提交整改说明。",
        },
        follow_redirects=False,
    )
    assert preserve_upload_response.status_code == 303
    preserved_dossier = _review_tasks(state)[0]["dossier"]
    assert isinstance(preserved_dossier, dict)
    preserved_attachments = preserved_dossier["attachments"]
    assert isinstance(preserved_attachments, list)
    assert preserved_attachments[-1]["status"] == "uploaded"
    assert preserved_attachments[-1]["storage_path"] == uploaded_attachment["storage_path"]

    updated_page_response = client.get("/pages/review-tasks")
    assert updated_page_response.status_code == 200
    assert "可进入报告草稿" in updated_page_response.text
    assert "审计员A" in updated_page_response.text
    assert "HIS收费明细导出" in updated_page_response.text
    assert "HIS收费明细上传归档" in updated_page_response.text
    assert "下载归档文件" in updated_page_response.text
    assert "导出任务 Word" in updated_page_response.text
    assert "导出报告草稿 Markdown" in updated_page_response.text
    assert "导出报告草稿 Word" in updated_page_response.text

    json_response = client.get("/review-tasks/review-task-0001/export")
    assert json_response.status_code == 200
    assert json_response.headers["content-disposition"] == (
        'attachment; filename="review-task-0001.json"'
    )
    body = json_response.json()
    assert body["format"] == "review-task-v1"
    assert body["status"] == "confirmed-violation"
    assert body["assigned_to"] == "审计员A"
    assert body["report_gate"]["ready_for_report"] is True
    assert body["reviewer_note"] == "引用已覆盖规则依据，需补 HIS 原始凭证。"
    assert body["conclusion"] == "疑似违规线索成立，进入人工复核。"
    assert body["dossier"]["workpaper"]["status"] == "ready"
    assert body["dossier"]["owner_signoff"]["status"] == "approved"
    assert body["dossier"]["attachments"][0]["title"] == "HIS收费明细导出"
    assert body["dossier"]["attachments"][2]["status"] == "uploaded"
    assert body["dossier"]["report_draft"]["title"] == ("同就诊同项目重复收费复核报告草稿")
    assert body["dossier"]["format"] == "audit-dossier-v1"
    assert body["dossier"]["citations"][0]["chunk_id"] == str(LAW_CHUNK_ID)
    assert body["dossier"]["citations"][0]["index_version_key"] == "index-v1"
    assert str(state.operation_logs[-1]["action"]) == "review-task-export"

    markdown_response = client.get(
        "/review-tasks/review-task-0001/export",
        params={"format": "markdown"},
    )
    assert markdown_response.status_code == 200
    assert markdown_response.headers["content-disposition"] == (
        'attachment; filename="review-task-0001.md"'
    )
    assert "# AuditScope 复核任务记录" in markdown_response.text
    assert "## 底稿" in markdown_response.text
    assert "确认违规 (confirmed-violation)" in markdown_response.text
    assert "报告准备度：可进入报告草稿" in markdown_response.text
    assert "底稿编号：workpaper-20260604-001" in markdown_response.text
    assert "负责人确认：负责人已确认" in markdown_response.text
    assert "附件数量：3" in markdown_response.text
    assert "报告标题：同就诊同项目重复收费复核报告草稿" in markdown_response.text
    assert "HIS收费明细导出" in markdown_response.text
    assert "HIS收费明细上传归档" in markdown_response.text
    assert "疑似违规线索成立，进入人工复核。" in markdown_response.text
    assert f"chunk: `{LAW_CHUNK_ID}`" in markdown_response.text

    task_docx_response = client.get(
        "/review-tasks/review-task-0001/export",
        params={"format": "docx"},
    )
    assert task_docx_response.status_code == 200
    assert task_docx_response.headers["content-disposition"] == (
        'attachment; filename="review-task-0001.docx"'
    )
    task_document_xml = _docx_document_xml(task_docx_response.content)
    assert "AuditScope 复核任务记录" in task_document_xml
    assert "workpaper-20260604-001" in task_document_xml

    report_markdown_response = client.get("/review-tasks/review-task-0001/report-draft")
    assert report_markdown_response.status_code == 200
    assert report_markdown_response.headers["content-disposition"] == (
        'attachment; filename="review-task-0001-report-draft.md"'
    )
    assert "# AuditScope 审计报告草稿" in report_markdown_response.text
    assert "同就诊同项目重复收费复核报告草稿" in report_markdown_response.text
    assert "HIS收费明细导出" in report_markdown_response.text
    assert "请责任科室核对收费明细并提交整改说明。" in report_markdown_response.text

    report_json_response = client.get(
        "/review-tasks/review-task-0001/report-draft",
        params={"format": "json"},
    )
    assert report_json_response.status_code == 200
    assert report_json_response.headers["content-disposition"] == (
        'attachment; filename="review-task-0001-report-draft.json"'
    )
    report_body = report_json_response.json()
    assert report_body["format"] == "review-task-report-draft-v1"
    assert report_body["report_gate"]["ready_for_report"] is True
    assert report_body["attachments"][0]["title"] == "HIS收费明细导出"
    assert report_body["attachments"][2]["status"] == "uploaded"
    assert report_body["report_draft"]["title"] == ("同就诊同项目重复收费复核报告草稿")

    report_docx_response = client.get(
        "/review-tasks/review-task-0001/report-draft",
        params={"format": "docx"},
    )
    assert report_docx_response.status_code == 200
    assert report_docx_response.headers["content-disposition"] == (
        'attachment; filename="review-task-0001-report-draft.docx"'
    )
    report_document_xml = _docx_document_xml(report_docx_response.content)
    assert "AuditScope 审计报告草稿" in report_document_xml
    assert "同就诊同项目重复收费复核报告草稿" in report_document_xml

    unsigned_report_response = client.get("/review-tasks/review-task-0001/signed-report")
    assert unsigned_report_response.status_code == 409
    assert unsigned_report_response.json()["detail"] == "review task report is not signed"

    blocked_rectification_response = client.post(
        "/pages/review-tasks/review-task-0001/rectification",
        data={
            "rectification_status": "pending-rectification",
            "responsible_department": "收费管理科",
            "responsible_owner": "科主任B",
            "due_date": "2026-06-30",
            "action_request": "核对重复收费并提交退费说明。",
            "progress_note": "待正式报告签发后发起整改。",
        },
        follow_redirects=False,
    )
    assert blocked_rectification_response.status_code == 409
    assert blocked_rectification_response.json()["detail"] == (
        "review task report must be signed before rectification tracking"
    )

    signoff_response = client.post(
        "/pages/review-tasks/review-task-0001/report-signoff",
        headers=director_headers,
        data={
            "signed_by": "审计科负责人A",
            "signoff_note": "报告正文、附件和负责人确认已核验。",
        },
        follow_redirects=False,
    )
    assert signoff_response.status_code == 303
    signed_task = _review_tasks(state)[0]
    signed_dossier = signed_task["dossier"]
    assert isinstance(signed_dossier, dict)
    signed_report = signed_dossier["signed_report"]
    assert isinstance(signed_report, dict)
    assert signed_report["status"] == "signed"
    assert str(signed_report["report_id"]).startswith("signed-report-")
    assert signed_report["signed_by"] == "next-director"
    assert signed_report["signoff_note"] == "报告正文、附件和负责人确认已核验。"
    signed_content = str(signed_report["content"])
    assert "# AuditScope 审计报告草稿" in signed_content
    assert "同就诊同项目重复收费复核报告草稿" in signed_content
    assert (
        signed_report["content_sha256"]
        == hashlib.sha256(signed_content.encode("utf-8")).hexdigest()
    )
    assert signed_report["attachment_count"] == 3
    assert str(state.operation_logs[-1]["action"]) == "review-task-report-signoff"

    signed_page_response = client.get("/pages/review-tasks")
    assert signed_page_response.status_code == 200
    assert "正式报告已签发" in signed_page_response.text
    assert "下载正式报告 Markdown" in signed_page_response.text
    assert "下载正式报告 Word" in signed_page_response.text
    assert str(signed_report["content_sha256"]) in signed_page_response.text

    signed_markdown_response = client.get("/review-tasks/review-task-0001/signed-report")
    assert signed_markdown_response.status_code == 200
    assert signed_markdown_response.headers["content-disposition"] == (
        'attachment; filename="review-task-0001-signed-report.md"'
    )
    assert signed_markdown_response.text == signed_content

    signed_json_response = client.get(
        "/review-tasks/review-task-0001/signed-report",
        params={"format": "json"},
    )
    assert signed_json_response.status_code == 200
    assert signed_json_response.headers["content-disposition"] == (
        'attachment; filename="review-task-0001-signed-report.json"'
    )
    signed_body = signed_json_response.json()
    assert signed_body["format"] == "review-task-signed-report-v1"
    assert signed_body["signed_report"]["content_sha256"] == signed_report["content_sha256"]
    assert signed_body["signed_report"]["content"] == signed_content

    signed_docx_response = client.get(
        "/review-tasks/review-task-0001/signed-report",
        params={"format": "docx"},
    )
    assert signed_docx_response.status_code == 200
    assert signed_docx_response.headers["content-disposition"] == (
        'attachment; filename="review-task-0001-signed-report.docx"'
    )
    signed_document_xml = _docx_document_xml(signed_docx_response.content)
    assert "AuditScope 审计报告草稿" in signed_document_xml
    assert "同就诊同项目重复收费复核报告草稿" in signed_document_xml

    reports_workbench_response = client.get("/reports/workbench")
    assert reports_workbench_response.status_code == 200
    reports_body = reports_workbench_response.json()
    assert reports_body["format"] == "report-workbench-v1"
    assert reports_body["template_registry_status"] == "active"
    assert reports_body["metrics"]["signed_report_count"] == 1
    assert reports_body["metrics"]["docx_download_count"] == 1
    assert len(reports_body["workpaper_templates"]) == 3
    report_entry = reports_body["report_entries"][0]
    assert report_entry["id"] == "review-task-0001"
    assert report_entry["status"] == "已签发"
    assert report_entry["download_links"]["task_docx"] == (
        "/review-tasks/review-task-0001/export?format=docx"
    )
    assert report_entry["download_links"]["report_docx"] == (
        "/review-tasks/review-task-0001/signed-report?format=docx"
    )
    assert reports_body["report_evidence_sources"][0]["title"] == "workpaper-20260604-001"

    rectification_response = client.post(
        "/pages/review-tasks/review-task-0001/rectification",
        data={
            "rectification_status": "pending-rectification",
            "responsible_department": "收费管理科",
            "responsible_owner": "科主任B",
            "due_date": "2026-06-30",
            "action_request": "核对重复收费并提交退费说明。",
            "progress_note": "已向责任科室发起整改通知。",
        },
        follow_redirects=False,
    )
    assert rectification_response.status_code == 303
    rectification_task = _review_tasks(state)[0]
    rectification_dossier = rectification_task["dossier"]
    assert isinstance(rectification_dossier, dict)
    rectification = rectification_dossier["rectification"]
    assert isinstance(rectification, dict)
    assert str(rectification["rectification_id"]).startswith("rectification-")
    assert rectification["status"] == "pending-rectification"
    assert rectification["status_label"] == "待整改"
    assert rectification["responsible_department"] == "收费管理科"
    assert rectification["responsible_owner"] == "科主任B"
    assert rectification["due_date"] == "2026-06-30"
    assert rectification["action_request"] == "核对重复收费并提交退费说明。"
    assert rectification["progress_note"] == "已向责任科室发起整改通知。"
    assert rectification["source_report_id"] == signed_report["report_id"]
    assert rectification["source_report_sha256"] == signed_report["content_sha256"]
    assert rectification["event_count"] == 1
    events = rectification["events"]
    assert isinstance(events, list)
    assert events[0]["from_status"] == "not-created"
    assert events[0]["to_status"] == "pending-rectification"
    assert events[0]["note"] == "已向责任科室发起整改通知。"
    assert str(state.operation_logs[-1]["action"]) == "review-task-rectification-update"

    rectification_page_response = client.get("/pages/review-tasks")
    assert rectification_page_response.status_code == 200
    assert "整改跟踪" in rectification_page_response.text
    assert "收费管理科" in rectification_page_response.text
    assert "待整改" in rectification_page_response.text
    assert "导出整改 JSON" in rectification_page_response.text

    rectification_json_response = client.get("/review-tasks/review-task-0001/rectification/export")
    assert rectification_json_response.status_code == 200
    assert rectification_json_response.headers["content-disposition"] == (
        'attachment; filename="review-task-0001-rectification.json"'
    )
    rectification_body = rectification_json_response.json()
    assert rectification_body["format"] == "review-task-rectification-v1"
    assert rectification_body["rectification"]["status"] == "pending-rectification"
    assert (
        rectification_body["rectification"]["source_report_sha256"]
        == signed_report["content_sha256"]
    )

    rectification_markdown_response = client.get(
        "/review-tasks/review-task-0001/rectification/export",
        params={"format": "markdown"},
    )
    assert rectification_markdown_response.status_code == 200
    assert rectification_markdown_response.headers["content-disposition"] == (
        'attachment; filename="review-task-0001-rectification.md"'
    )
    assert "# AuditScope 整改跟踪记录" in rectification_markdown_response.text
    assert "收费管理科" in rectification_markdown_response.text
    assert str(signed_report["content_sha256"]) in rectification_markdown_response.text

    task_export_after_rectification = client.get("/review-tasks/review-task-0001/export")
    assert task_export_after_rectification.status_code == 200
    assert task_export_after_rectification.json()["rectification"]["status"] == (
        "pending-rectification"
    )
    task_markdown_after_rectification = client.get(
        "/review-tasks/review-task-0001/export",
        params={"format": "markdown"},
    )
    assert "## 整改跟踪" in task_markdown_after_rectification.text
    assert "整改状态：待整改" in task_markdown_after_rectification.text

    blocked_close_response = client.post(
        "/pages/review-tasks/review-task-0001/status",
        headers=director_headers,
        data={
            "status": "closed",
            "assigned_to": "审计员A",
            "reviewer_note": "整改未验收前尝试结案。",
            "conclusion": "疑似违规线索成立，进入人工复核。",
            "workpaper_status": "ready",
            "workpaper_id": "workpaper-20260604-001",
            "workpaper_note": "底稿已核对引用、原文和 HIS 凭证位置。",
            "owner_signoff_status": "approved",
            "owner_confirmed_by": "审计科负责人A",
            "owner_confirmed_at": "2026-06-04T12:00:00Z",
            "attachment_manifest": (
                "HIS收费明细导出 | /evidence/his-charge-detail.csv | 已脱敏\n"
                "复核签字单 | /evidence/signoff.pdf | 负责人确认"
            ),
            "report_title": "同就诊同项目重复收费复核报告草稿",
            "report_summary": "本任务确认重复收费线索成立，证据链已闭合。",
            "rectification_request": "请责任科室核对收费明细并提交整改说明。",
        },
        follow_redirects=False,
    )
    assert blocked_close_response.status_code == 409
    assert blocked_close_response.json()["detail"] == (
        "review task rectification must be accepted before closing"
    )
    assert _review_tasks(state)[0]["status"] == "confirmed-violation"
    blocked_close_page_response = client.get("/pages/review-tasks")
    assert blocked_close_page_response.status_code == 200
    assert "结案门禁" in blocked_close_page_response.text
    assert "整改未验收" in blocked_close_page_response.text

    accepted_rectification_response = client.post(
        "/pages/review-tasks/review-task-0001/rectification",
        headers=director_headers,
        data={
            "rectification_status": "accepted",
            "responsible_department": "收费管理科",
            "responsible_owner": "科主任B",
            "due_date": "2026-06-30",
            "action_request": "核对重复收费并提交退费说明。",
            "progress_note": "已核验退费说明和制度修订记录。",
        },
        follow_redirects=False,
    )
    assert accepted_rectification_response.status_code == 303
    accepted_task = _review_tasks(state)[0]
    accepted_dossier = accepted_task["dossier"]
    assert isinstance(accepted_dossier, dict)
    accepted_rectification = accepted_dossier["rectification"]
    assert isinstance(accepted_rectification, dict)
    assert accepted_rectification["rectification_id"] == rectification["rectification_id"]
    assert accepted_rectification["status"] == "accepted"
    assert accepted_rectification["status_label"] == "已验收"
    assert accepted_rectification["event_count"] == 2
    accepted_events = accepted_rectification["events"]
    assert isinstance(accepted_events, list)
    assert accepted_events[-1]["from_status"] == "pending-rectification"
    assert accepted_events[-1]["to_status"] == "accepted"

    close_response = client.post(
        "/pages/review-tasks/review-task-0001/status",
        headers=director_headers,
        data={
            "status": "closed",
            "assigned_to": "审计员A",
            "reviewer_note": "整改已验收，允许结案。",
            "conclusion": "疑似违规线索成立，整改已验收。",
            "workpaper_status": "ready",
            "workpaper_id": "workpaper-20260604-001",
            "workpaper_note": "底稿已核对引用、原文和 HIS 凭证位置。",
            "owner_signoff_status": "approved",
            "owner_confirmed_by": "审计科负责人A",
            "owner_confirmed_at": "2026-06-04T12:00:00Z",
            "attachment_manifest": (
                "HIS收费明细导出 | /evidence/his-charge-detail.csv | 已脱敏\n"
                "复核签字单 | /evidence/signoff.pdf | 负责人确认"
            ),
            "report_title": "同就诊同项目重复收费复核报告草稿",
            "report_summary": "本任务确认重复收费线索成立，证据链已闭合。",
            "rectification_request": "请责任科室核对收费明细并提交整改说明。",
        },
        follow_redirects=False,
    )
    assert close_response.status_code == 303
    closed_task = _review_tasks(state)[0]
    assert closed_task["status"] == "closed"
    assert closed_task["status_label"] == "已关闭"
    assert str(state.operation_logs[-1]["action"]) == "review-task-status-update"

    closed_page_response = client.get("/pages/review-tasks")
    assert closed_page_response.status_code == 200
    assert "允许结案" in closed_page_response.text
    assert "已关闭" in closed_page_response.text
    assert "该任务已结案，只读锁定。" in closed_page_response.text

    closed_export_response = client.get("/review-tasks/review-task-0001/export")
    assert closed_export_response.status_code == 200
    closed_body = closed_export_response.json()
    assert closed_body["status"] == "closed"
    assert closed_body["close_gate"]["ready_to_close"] is True
    assert closed_body["close_gate"]["status_label"] == "允许结案"
    closed_markdown_response = client.get(
        "/review-tasks/review-task-0001/export",
        params={"format": "markdown"},
    )
    assert "## 结案门禁" in closed_markdown_response.text
    assert "结案状态：允许结案" in closed_markdown_response.text

    locked_signoff_response = client.post(
        "/pages/review-tasks/review-task-0001/report-signoff",
        headers=director_headers,
        data={"signed_by": "审计科负责人A"},
        follow_redirects=False,
    )
    assert locked_signoff_response.status_code == 409
    assert locked_signoff_response.json()["detail"] == "review task is closed and read-only"

    locked_attachment_response = client.post(
        "/pages/review-tasks/review-task-0001/attachments",
        headers={"X-User-Id": "auditor-a", "X-Role": "auditor"},
        data={
            "attachment_title": "结案后不应归档",
            "attachment_note": "closed task must be read-only",
        },
        files={
            "attachment_file": (
                "closed-after.csv",
                b"charge_id,amount\nCD0002,200\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    assert locked_attachment_response.status_code == 409
    assert locked_attachment_response.json()["detail"] == "review task is closed and read-only"

    locked_rectification_response = client.post(
        "/pages/review-tasks/review-task-0001/rectification",
        headers={"X-User-Id": "department-head-a", "X-Role": "department-head"},
        data={
            "rectification_status": "returned",
            "responsible_department": "收费管理科",
            "responsible_owner": "科主任B",
            "due_date": "2026-06-30",
            "action_request": "结案后不应修改整改。",
            "progress_note": "closed task must be read-only",
        },
        follow_redirects=False,
    )
    assert locked_rectification_response.status_code == 409
    assert locked_rectification_response.json()["detail"] == "review task is closed and read-only"

    edit_after_close_response = client.post(
        "/pages/review-tasks/review-task-0001/status",
        headers=director_headers,
        data={
            "status": "confirmed-violation",
            "assigned_to": "审计员A",
            "reviewer_note": "结案后补充编辑应被阻断。",
            "conclusion": "疑似违规线索成立，进入人工复核。",
            "workpaper_status": "ready",
            "workpaper_id": "workpaper-20260604-001",
            "workpaper_note": "底稿已核对引用、原文和 HIS 凭证位置。",
            "owner_signoff_status": "approved",
            "owner_confirmed_by": "审计科负责人A",
            "owner_confirmed_at": "2026-06-04T12:00:00Z",
            "attachment_manifest": (
                "HIS收费明细导出 | /evidence/his-charge-detail.csv | 已脱敏\n"
                "复核签字单 | /evidence/signoff.pdf | 负责人确认"
            ),
            "report_title": "后续编辑不应改写已签发报告",
            "report_summary": "后续编辑不应影响签发正文。",
            "rectification_request": "后续编辑不应影响签发正文。",
        },
        follow_redirects=False,
    )
    assert edit_after_close_response.status_code == 409
    assert edit_after_close_response.json()["detail"] == "review task is closed and read-only"
    locked_task = _review_tasks(state)[0]
    assert locked_task["status"] == "closed"
    locked_dossier = locked_task["dossier"]
    assert isinstance(locked_dossier, dict)
    assert len(locked_dossier["attachments"]) == 3
    assert locked_dossier["rectification"]["status"] == "accepted"
    frozen_markdown_response = client.get("/review-tasks/review-task-0001/signed-report")
    assert frozen_markdown_response.status_code == 200
    assert frozen_markdown_response.text == signed_content
    readonly_block_events = [
        item
        for item in state.operation_logs
        if item["action"] == "review-task-readonly-write-blocked"
    ]
    readonly_block_payloads = [
        cast(dict[str, object], event["payload"]) for event in readonly_block_events
    ]
    assert [payload["attempted_action"] for payload in readonly_block_payloads] == [
        "review-task-report-signoff",
        "review-task-attachment-upload",
        "review-task-rectification-update",
        "review-task-status-update",
    ]
    assert {payload["task_id"] for payload in readonly_block_payloads} == {"review-task-0001"}
    assert {payload["task_status"] for payload in readonly_block_payloads} == {"closed"}
    assert {payload["status_code"] for payload in readonly_block_payloads} == {409}
    assert {payload["reason"] for payload in readonly_block_payloads} == {
        "review task is closed and read-only"
    }
    assert readonly_block_payloads[0]["endpoint"] == (
        "/pages/review-tasks/review-task-0001/report-signoff"
    )
    assert readonly_block_payloads[0]["user_identifier"] == "next-director"
    assert readonly_block_payloads[2]["role"] == "department-head"


def test_review_tasks_persist_across_api_state_rebuilds(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    client = TestClient(create_app(state))

    create_response = client.post(
        "/pages/review-tasks/create",
        data={"question": "医保基金审核依据"},
        follow_redirects=False,
    )

    assert create_response.status_code == 303
    assert _review_tasks(state)[0]["task_id"] == "review-task-0001"

    rebuilt_state = _api_state(tmp_path)
    rebuilt_client = TestClient(create_app(rebuilt_state))
    page_response = rebuilt_client.get("/pages/review-tasks")

    assert page_response.status_code == 200
    assert "review-task-0001" in page_response.text
    assert "医保基金审核依据" in page_response.text

    update_response = rebuilt_client.post(
        "/pages/review-tasks/review-task-0001/status",
        data={
            "status": "needs-evidence",
            "reviewer_note": "服务重启后继续复核。",
            "conclusion": "需要补充 HIS 原始凭证。",
        },
        follow_redirects=False,
    )
    assert update_response.status_code == 303

    second_rebuilt_state = _api_state(tmp_path)
    second_rebuilt_client = TestClient(create_app(second_rebuilt_state))
    export_response = second_rebuilt_client.get("/review-tasks/review-task-0001/export")

    assert export_response.status_code == 200
    body = export_response.json()
    assert body["status"] == "needs-evidence"
    assert body["reviewer_note"] == "服务重启后继续复核。"
    assert body["conclusion"] == "需要补充 HIS 原始凭证。"


def test_review_tasks_sqlalchemy_store_persists_review_state_across_rebuilds(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'review-tasks.db'}"
    state = _api_state(tmp_path)
    state.review_task_store = SqlAlchemyReviewTaskStore(database_url, create_schema=True)
    client = TestClient(create_app(state))

    create_response = client.post(
        "/pages/review-tasks/create",
        data={"question": "医保基金审核依据"},
        follow_redirects=False,
    )

    assert create_response.status_code == 303
    assert _review_tasks(state)[0]["task_id"] == "review-task-0001"

    rebuilt_state = _api_state(tmp_path)
    rebuilt_state.review_task_store = SqlAlchemyReviewTaskStore(database_url)
    rebuilt_client = TestClient(create_app(rebuilt_state))
    update_response = rebuilt_client.post(
        "/pages/review-tasks/review-task-0001/status",
        data={
            "status": "needs-evidence",
            "reviewer_note": "数据库重建后继续复核。",
            "conclusion": "需要补充 HIS 原始凭证。",
        },
        follow_redirects=False,
    )

    assert update_response.status_code == 303

    second_rebuilt_state = _api_state(tmp_path)
    second_rebuilt_state.review_task_store = SqlAlchemyReviewTaskStore(database_url)
    second_rebuilt_client = TestClient(create_app(second_rebuilt_state))
    export_response = second_rebuilt_client.get("/review-tasks/review-task-0001/export")

    assert export_response.status_code == 200
    body = export_response.json()
    assert body["status"] == "needs-evidence"
    assert body["reviewer_note"] == "数据库重建后继续复核。"
    assert body["conclusion"] == "需要补充 HIS 原始凭证。"


def test_review_task_create_fails_when_backend_is_not_ready(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    state.search_engine = None
    client = TestClient(create_app(state))

    response = client.post(
        "/pages/review-tasks/create",
        data={"question": "医保基金审核依据"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "检索引擎尚未初始化。"
    assert _review_tasks(state) == []


def test_audit_findings_page_export_and_review_task_flow(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'audit-findings.db'}"
    state = _api_state(tmp_path)
    state.audit_finding_store = SqlAlchemyAuditFindingStore(database_url, create_schema=True)
    state.review_task_store = SqlAlchemyReviewTaskStore(database_url)
    _seed_charge_rule_001_findings(database_url)
    client = TestClient(create_app(state))

    page_response = client.get("/pages/audit-findings")

    assert page_response.status_code == 200
    assert "疑点清单" in page_response.text
    assert "Findings Workbench" in page_response.text
    assert "CHARGE-RULE-001" in page_response.text
    assert "duplicate-charge" in page_response.text
    assert "pending-review" in page_response.text
    assert "matched_charge_detail_ids" in page_response.text
    assert "创建复核任务" in page_response.text
    assert 'role="tab" aria-selected="true" href="/findings">疑点清单' in page_response.text
    assert str(state.operation_logs[-1]["action"]) == "page-audit-findings-view"

    api_response = client.get("/audit-findings")

    assert api_response.status_code == 200
    api_body = api_response.json()
    assert api_body["stats"]["total"] == 3
    assert api_body["stats"]["pending_review"] == 3
    assert api_body["stats"]["linked_review_task"] == 0
    assert api_body["review_status_options"]["pending-review"] == "待复核"
    assert api_body["store"]["ready"] is True
    assert api_body["generation_readiness"]["status"] == "generated"
    assert api_body["generation_readiness"]["ready"] is True
    assert api_body["generation_readiness"]["has_findings"] is True
    assert api_body["generation_readiness"]["table_counts"]["audit_findings"] == 3
    assert api_body["items"][0]["finding_type"] == "duplicate-charge"
    assert api_body["items"][0]["evidence_items"][0]["evidence_type"] == "rule-rationale"
    assert str(state.operation_logs[-1]["action"]) == "audit-findings-list"

    filtered_response = client.get("/audit-findings", params={"review_status": "closed"})
    assert filtered_response.status_code == 200
    assert filtered_response.json()["items"] == []

    invalid_filter_response = client.get(
        "/audit-findings",
        params={"review_status": "unsupported"},
    )
    assert invalid_filter_response.status_code == 422

    export_response = client.get("/audit-findings/finding-fdc6a665ec5fcbf8/export")

    assert export_response.status_code == 200
    assert export_response.headers["content-disposition"] == (
        'attachment; filename="finding-fdc6a665ec5fcbf8.json"'
    )
    body = export_response.json()
    assert isinstance(body, dict)
    assert body["format"] == "audit-finding-v1"
    assert body["finding_key"] == "finding-fdc6a665ec5fcbf8"
    assert body["rule_key"] == RULE_KEY
    assert body["rule_version_key"] == DEFAULT_RULE_VERSION_KEY
    assert body["source_record_locator"]["source_table"] == "charge_detail"
    assert body["calculation_trace"]["matched_charge_detail_ids"] == ["CD0001", "CD0002"]
    assert body["evidence_items"][0]["evidence_type"] == "rule-rationale"
    assert str(state.operation_logs[-1]["action"]) == "audit-finding-export"

    create_response = client.post(
        "/pages/audit-findings/finding-fdc6a665ec5fcbf8/review-task",
        follow_redirects=False,
    )

    assert create_response.status_code == 303
    assert create_response.headers["location"] == "/pages/review-tasks"
    tasks = _review_tasks(state)
    assert len(tasks) == 1
    assert tasks[0]["source"] == "audit-finding"
    dossier = tasks[0]["dossier"]
    assert isinstance(dossier, dict)
    assert dossier["format"] == "audit-finding-dossier-v1"
    assert dossier["finding_key"] == "finding-fdc6a665ec5fcbf8"
    calculation_trace = dossier["calculation_trace"]
    assert isinstance(calculation_trace, dict)
    assert calculation_trace["matched_charge_detail_ids"] == [
        "CD0001",
        "CD0002",
    ]

    task_markdown_response = client.get(
        "/review-tasks/review-task-0001/export",
        params={"format": "markdown"},
    )
    assert task_markdown_response.status_code == 200
    assert "AuditScope 规则疑点底稿导出" in task_markdown_response.text
    assert "finding-fdc6a665ec5fcbf8" in task_markdown_response.text
    assert "matched_charge_detail_ids" in task_markdown_response.text

    update_response = client.post(
        "/pages/review-tasks/review-task-0001/status",
        data={
            "status": "confirmed-violation",
            "assigned_to": "fixture-auditor",
            "reviewer_note": "规则疑点复核状态同步测试。",
            "conclusion": "确认规则命中。",
        },
        follow_redirects=False,
    )
    assert update_response.status_code == 303
    assert state.operation_logs[-1]["payload"]["synced_audit_finding_count"] == 1

    synced_response = client.get(
        "/audit-findings",
        params={"review_status": "confirmed-violation"},
    )
    assert synced_response.status_code == 200
    synced_items = synced_response.json()["items"]
    assert [item["finding_key"] for item in synced_items] == ["finding-fdc6a665ec5fcbf8"]
    assert synced_items[0]["review_status"] == "confirmed-violation"

    linked_page_response = client.get("/pages/audit-findings")
    assert linked_page_response.status_code == 200
    assert "review-task-0001" in linked_page_response.text
    assert "confirmed-violation" in linked_page_response.text
    assert "已创建复核任务" in linked_page_response.text


def test_audit_findings_api_reports_blocked_generation_readiness(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'empty-audit-findings.db'}"
    state = _api_state(tmp_path)
    state.audit_finding_store = SqlAlchemyAuditFindingStore(database_url, create_schema=True)
    client = TestClient(create_app(state))

    response = client.get("/audit-findings")

    assert response.status_code == 200
    body = response.json()
    readiness = body["generation_readiness"]
    assert body["items"] == []
    assert readiness["status"] == "blocked"
    assert readiness["ready"] is False
    assert readiness["has_findings"] is False
    assert readiness["table_counts"]["audit_projects"] == 0
    assert readiness["table_counts"]["his_staging_rows"] == 0
    assert readiness["table_counts"]["audit_findings"] == 0
    blocking_codes = {item["code"] for item in readiness["blocking_reasons"]}
    assert "missing-audit_projects" in blocking_codes
    assert "missing-his_staging_rows" in blocking_codes


def test_preview_page_renders_source_context_after_query(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    client = TestClient(create_app(state))
    client.get("/pages/query", params={"question": "医保基金审核依据"})

    response = client.get(f"/pages/preview/{LAW_CHUNK_ID}")

    assert response.status_code == 200
    assert "原文证据预览" in response.text
    assert "原文复核优先级" in response.text
    assert "证据链" in response.text
    assert "复核要点" in response.text
    assert "第一条 医疗机构应当保留医保基金审核依据。" in response.text
    assert "全量法律/law.md" in response.text
    assert state.operation_logs[-1]["action"] == "page-preview"


def test_index_admin_page_renders_operational_status_and_records_log(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    state.index_versions.append(
        {
            "index_version_key": "index-v1",
            "source_package_version_key": "package-v1",
            "status": "active",
            "chunk_count": 2,
            "document_count": 2,
        }
    )
    state.index_jobs.append(
        {
            "job_id": "index-v1",
            "job_type": "full-rebuild",
            "status": "succeeded",
            "summary": {},
        }
    )
    state.failed_files.append(
        {
            "relative_path": "全量法律/broken.pdf",
            "error_type": "parse-failed",
            "error_summary": "cannot parse",
        }
    )
    state.pending_files.append(
        {
            "relative_path": "风险负面清单/case.png",
            "error_type": "unsupported-media",
            "error_summary": "needs OCR",
        }
    )
    client = TestClient(create_app(state))

    response = client.get("/pages/index-admin")

    assert response.status_code == 200
    assert "知识库索引管理" in response.text
    assert "数据库 chunks" in response.text
    assert "检索已就绪" in response.text
    assert 'href="#main-content"' in response.text
    assert 'role="tab" aria-selected="true" href="/pages/index-admin">索引管理' in response.text
    assert "index-v1" in response.text
    assert "全量法律/broken.pdf" in response.text
    assert "风险负面清单/case.png" in response.text
    assert "not-run" in response.text
    assert "导出操作日志 JSON" in response.text
    assert "Release Console" in response.text
    assert "发布 candidate" in response.text
    assert "回滚到历史版本" in response.text
    assert 'data-endpoint="/index/versions/activate"' in response.text
    assert 'data-endpoint="/index/versions/rollback"' in response.text
    assert 'data-endpoint="/index/search-backend/postgres"' in response.text
    assert "Smoke Question" in response.text
    assert "Acceptance Panel" in response.text
    assert "运行发布后验收" in response.text
    assert "下载最新验收报告 JSON" in response.text
    assert "验收历史" in response.text
    assert "历史报告列表" in response.text
    assert 'href="/index/evaluation/history"' in response.text
    assert 'data-endpoint="/index/evaluation/run"' in response.text
    assert 'href="/index/evaluation/latest/export"' in response.text
    assert state.operation_logs[-1]["action"] == "page-index-admin-view"


def test_query_page_exposes_alert_when_backend_is_not_ready(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    state.search_engine = None
    client = TestClient(create_app(state))

    response = client.get("/pages/query", params={"question": "医保基金审核依据"})

    assert response.status_code == 200
    assert 'role="alert"' in response.text
    assert "检索引擎尚未初始化" in response.text


def test_static_css_includes_keyboard_focus_styles(tmp_path: Path) -> None:
    client = TestClient(create_app(_api_state(tmp_path)))

    response = client.get("/static/app.css")

    assert response.status_code == 200
    assert ":focus-visible" in response.text
    assert "@media print" in response.text
    assert ".copy-citation-button" in response.text
    assert ".review-attachment-archive" in response.text
    assert ".review-report-signoff" in response.text
    assert ".review-rectification-tracking" in response.text
    assert ".review-close-gate" in response.text
    assert ".review-readonly-lock" in response.text
    assert ".audit-log-timeline" in response.text
    assert ".audit-log-filter-form" in response.text


def test_operation_logs_export_records_export_operation(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    client = TestClient(create_app(state))
    client.get("/pages/index-admin")

    response = client.get("/operation/logs/export")

    assert response.status_code == 200
    body = response.json()
    assert body["format"] == "json"
    assert body["items"][-1]["action"] == "operation-logs-export"


def test_operation_logs_persist_when_audit_log_store_is_configured(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'audit-log.db'}"
    state = _api_state(tmp_path)
    state.audit_log_store = SqlAlchemyAuditLogStore(database_url, create_schema=True)
    client = TestClient(create_app(state))

    client.get("/pages/index-admin")
    response = client.get("/operation/logs/export")

    assert response.status_code == 200
    rebuilt_store = SqlAlchemyAuditLogStore(database_url)
    persisted_events = rebuilt_store.list_events()
    assert [event["action"] for event in persisted_events[:2]] == [
        "operation-logs-export",
        "page-index-admin-view",
    ]
    assert persisted_events[0]["entity_type"] == "operation"
    assert persisted_events[0]["entity_id"] == "operation-logs-export"
    persisted_export_payload = cast(dict[str, object], persisted_events[0]["payload"])
    assert persisted_export_payload["count"] == 1


def test_persistent_audit_logs_api_filters_and_exports_events(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    state.audit_log_store = SqlAlchemyAuditLogStore(
        f"sqlite:///{tmp_path / 'audit-log-api.db'}",
        create_schema=True,
    )
    state.audit_log_store.add_event(
        "review-task-readonly-write-blocked",
        {
            "task_id": "review-task-0001",
            "task_status": "closed",
            "user_identifier": "auditor-001",
            "role": "auditor",
            "status_code": 409,
            "endpoint": "/pages/review-tasks/review-task-0001/status",
            "reason": "review task is closed and read-only",
        },
    )
    state.audit_log_store.add_event(
        "query",
        {
            "question": "医保基金审核依据",
            "user_identifier": "auditor-002",
            "role": "auditor",
            "status_code": 200,
            "endpoint": "/query",
        },
    )
    client = TestClient(create_app(state))

    response = client.get(
        "/audit/logs",
        params={
            "entity_type": "review-task",
            "entity_id": "review-task-0001",
            "user_identifier": "auditor-001",
        },
        headers={"X-Role": "department-head"},
    )
    export_response = client.get("/audit/logs/export", headers={"X-Role": "department-head"})

    assert response.status_code == 200
    body = response.json()
    assert body["store"]["ready"] is True
    assert body["filters"]["entity_id"] == "review-task-0001"
    assert body["items"][0]["action"] == "review-task-readonly-write-blocked"
    assert body["items"][0]["user_identifier"] == "auditor-001"
    assert export_response.status_code == 200
    assert export_response.headers["content-disposition"] == (
        'attachment; filename="auditscope-audit-logs.json"'
    )
    export_body = export_response.json()
    assert export_body["items"][0]["action"] == "audit-logs-export"
    assert any(item["entity_type"] == "review-task" for item in export_body["items"])


def test_audit_logs_api_and_page_use_persistent_role(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    state.audit_log_store = SqlAlchemyAuditLogStore(
        f"sqlite:///{tmp_path / 'audit-log-persistent-role.db'}",
        create_schema=True,
    )
    state.auth_user_store = SqlAlchemyAuthUserStore(
        f"sqlite:///{tmp_path / 'auth-users.db'}",
        create_schema=True,
    )
    assert state.auth_user_store is not None
    state.auth_user_store.add_user(
        {
            "user_key": "persistent-audit-director",
            "display_name": "审计主任",
            "status": "active",
        }
    )
    state.auth_user_store.assign_role(
        "persistent-audit-director",
        {"role": "director", "scope_type": "global"},
    )
    assert state.audit_log_store is not None
    state.audit_log_store.add_event(
        "review-task-readonly-write-blocked",
        {
            "task_id": "review-task-0001",
            "user_identifier": "auditor-001",
            "role": "auditor",
            "status_code": 409,
            "endpoint": "/pages/review-tasks/review-task-0001/status",
        },
    )
    client = TestClient(create_app(state))
    headers = {"X-User-Id": "persistent-audit-director", "X-Role": "auditor"}

    api_response = client.get("/audit/logs", headers=headers)
    page_response = client.get("/pages/audit-logs", headers=headers)

    assert api_response.status_code == 200
    assert any(
        item["action"] == "review-task-readonly-write-blocked"
        for item in api_response.json()["items"]
    )
    assert page_response.status_code == 200
    assert "review-task-readonly-write-blocked" in page_response.text


def test_persistent_audit_logs_require_governance_role_and_redact_sensitive_payload(
    tmp_path: Path,
) -> None:
    state = _api_state(tmp_path)
    state.audit_log_store = SqlAlchemyAuditLogStore(
        f"sqlite:///{tmp_path / 'audit-log-governance.db'}",
        create_schema=True,
    )
    state.audit_log_store.add_event(
        "query",
        {
            "question": "医保基金审核依据",
            "user_identifier": "auditor-sensitive",
            "role": "auditor",
            "status_code": 200,
            "endpoint": "/query",
            "api_key": "secret-key",
            "nested": {
                "authorization": "Bearer raw-token",
                "safe_note": "keep this note",
            },
        },
    )
    client = TestClient(create_app(state))

    rejected_response = client.get("/audit/logs", headers={"X-Role": "auditor"})
    accepted_response = client.get("/audit/logs", headers={"X-Role": "department-head"})
    export_rejected_response = client.get("/audit/logs/export", headers={"X-Role": "auditor"})

    assert rejected_response.status_code == 403
    assert rejected_response.json()["detail"] == "read_audit_logs is not allowed"
    assert export_rejected_response.status_code == 403
    assert accepted_response.status_code == 200
    body = accepted_response.json()
    assert body["policy"]["retention_days"] == 180
    query_event = next(item for item in body["items"] if item["action"] == "query")
    payload = cast(dict[str, object], query_event["payload"])
    nested_payload = cast(dict[str, object], payload["nested"])
    assert payload["api_key"] == "[REDACTED]"
    assert nested_payload["authorization"] == "[REDACTED]"
    assert nested_payload["safe_note"] == "keep this note"


def test_audit_logs_page_renders_persistent_events_and_filters(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    state.audit_log_store = SqlAlchemyAuditLogStore(
        f"sqlite:///{tmp_path / 'audit-log-page.db'}",
        create_schema=True,
    )
    state.audit_log_store.add_event(
        "review-task-readonly-write-blocked",
        {
            "task_id": "review-task-0001",
            "task_status": "closed",
            "user_identifier": "auditor-001",
            "role": "auditor",
            "status_code": 409,
            "endpoint": "/pages/review-tasks/review-task-0001/status",
            "reason": "review task is closed and read-only",
        },
    )
    client = TestClient(create_app(state))

    response = client.get(
        "/pages/audit-logs",
        params={"entity_type": "review-task", "entity_id": "review-task-0001"},
        headers={"X-Role": "department-head"},
    )

    assert response.status_code == 200
    assert "审计日志台" in response.text
    assert "review-task-readonly-write-blocked" in response.text
    assert "auditor-001" in response.text
    assert "409" in response.text
    assert (
        "/audit/logs/export?entity_type=review-task&amp;entity_id=review-task-0001" in response.text
    )


def test_audit_logs_page_hides_events_without_governance_role(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    state.audit_log_store = SqlAlchemyAuditLogStore(
        f"sqlite:///{tmp_path / 'audit-log-page-denied.db'}",
        create_schema=True,
    )
    state.audit_log_store.add_event(
        "review-task-readonly-write-blocked",
        {
            "task_id": "review-task-0001",
            "user_identifier": "auditor-denied",
            "status_code": 409,
        },
    )
    client = TestClient(create_app(state))

    response = client.get("/pages/audit-logs", headers={"X-Role": "auditor"})

    assert response.status_code == 200
    assert "需要审计日志权限" in response.text
    assert "review-task-readonly-write-blocked" not in response.text
    assert "auditor-denied" not in response.text


def test_favicon_route_avoids_browser_404_noise(tmp_path: Path) -> None:
    client = TestClient(create_app(_api_state(tmp_path)))

    response = client.get("/favicon.ico")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/svg+xml"
    assert "<svg" in response.text

    head_response = client.head("/favicon.ico")
    assert head_response.status_code == 200
    assert head_response.headers["content-type"] == "image/svg+xml"


LAW_CHUNK_ID = UUID("11111111-1111-4111-8111-111111111111")
RULE_CHUNK_ID = UUID("22222222-2222-4222-8222-222222222222")


def _api_state(tmp_path: Path) -> ApiState:
    source_root = tmp_path / "data"
    law_file = source_root / "全量法律" / "law.md"
    rule_file = source_root / "三大目录知识库" / "rule.md"
    _write_text(
        law_file,
        "\n".join(
            [
                "第一条 医疗机构应当保留医保基金审核依据。",
                "第二条 审核记录应可追溯。",
            ]
        ),
    )
    _write_text(rule_file, "规则一 医保基金审核需要核验诊疗记录。")
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
    state.query_history_store = InMemoryQueryHistoryStore()
    state.review_task_store = JsonFileReviewTaskStore(
        settings.index_root / "review-tasks" / "review-tasks.json"
    )
    state.search_engine = _search_engine(
        (
            _chunk(
                chunk_id=LAW_CHUNK_ID,
                text="第一条 医疗机构应当保留医保基金审核依据。",
                source_path=law_file.relative_to(source_root).as_posix(),
                source_collection=SourceCollection.MEDICAL_INSURANCE_LAWS,
                document_type="law",
            ),
            _chunk(
                chunk_id=RULE_CHUNK_ID,
                text="规则一 医保基金审核需要核验诊疗记录。",
                source_path=rule_file.relative_to(source_root).as_posix(),
                source_collection=SourceCollection.SUPERVISION_RULES_KNOWLEDGE,
                document_type="rule",
            ),
        )
    )
    return state


def _review_tasks(state: ApiState) -> list[dict[str, object]]:
    assert state.review_task_store is not None
    return state.review_task_store.list_tasks()


def _docx_document_xml(content: bytes) -> str:
    with ZipFile(BytesIO(content)) as archive:
        names = set(archive.namelist())
        assert "[Content_Types].xml" in names
        assert "word/document.xml" in names
        return archive.read("word/document.xml").decode("utf-8")


def _seed_charge_rule_001_findings(database_url: str) -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from medical_audit_kb.db.models import Base

    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        project = AuditProject(
            project_key="audit-project-charge-fixture",
            name="收费合规 fixture 专项",
            scenario_key="charging-compliance",
            status="fixture",
            owner_department="审计科",
            created_by="unit-test",
        )
        session.add(project)
        session.flush()
        snapshot = AuditDataSnapshot(
            snapshot_key="snapshot-charge-fixture",
            project_id=project.id,
            source_batch_key="his-fixture-20260604",
            time_range={"from": "2025-01-01", "to": "2025-01-31"},
            row_counts={"charge_detail": len(build_charge_rule_001_fixture())},
            checksum="sha256:charge-fixture",
            status="validated",
        )
        session.add(snapshot)
        session.flush()
        task = AuditTask(
            task_key="audit-task-charge-fixture",
            project_id=project.id,
            snapshot_id=snapshot.id,
            topic="同就诊同项目重复收费",
            department_scope={"department_codes": ["D001"]},
            date_range={"from": "2025-01-01", "to": "2025-01-31"},
            status="ready",
            created_by="unit-test",
        )
        rule = AuditRule(
            rule_key=RULE_KEY,
            scenario_key="charging-compliance",
            name="同就诊同项目重复收费",
            status="active",
            owner="audit-rule-team",
        )
        session.add_all([task, rule])
        session.flush()
        rule_version = RuleVersion(
            audit_rule_id=rule.id,
            version_key=DEFAULT_RULE_VERSION_KEY,
            rule_key=RULE_KEY,
            status="active",
            logic={"fixture": "charge-rule-001-v1"},
            evidence_links={"knowledge_topics": ["重复收费", "收费项目内涵"]},
            created_by="unit-test",
        )
        session.add(rule_version)
        session.flush()
        run = AuditRun(
            run_key="audit-run-charge-fixture",
            audit_task_id=task.id,
            snapshot_id=snapshot.id,
            rule_version_key=rule_version.version_key,
            knowledge_index_version_key="full-rebuild-20260603085815",
            status="succeeded",
            summary={"fixture": True},
        )
        session.add(run)
        session.flush()
        result = evaluate_charge_rule_001(
            build_charge_rule_001_fixture(),
            audit_task_key=task.task_key,
            audit_run_key=run.run_key,
            snapshot_key=snapshot.snapshot_key,
            knowledge_index_version_key=run.knowledge_index_version_key,
        )
        payloads = build_audit_finding_payloads(
            result,
            audit_run_id=run.id,
            audit_task_id=task.id,
            rule_version_id=rule_version.id,
            snapshot_id=snapshot.id,
        )
        for payload, rule_finding in zip(payloads, result.findings, strict=True):
            finding_model = AuditFinding(
                finding_key=payload.finding_key,
                audit_run_id=payload.audit_run_id,
                audit_task_id=payload.audit_task_id,
                rule_version_id=payload.rule_version_id,
                snapshot_id=payload.snapshot_id,
                status=payload.status,
                finding_type=payload.finding_type,
                severity=payload.severity,
                source_record_locator=payload.source_record_locator,
                calculation_trace=payload.calculation_trace,
                review_status=payload.review_status,
                extra_metadata=payload.metadata,
            )
            session.add(finding_model)
            session.flush()
            session.add(
                FindingEvidenceItem(
                    audit_finding_id=finding_model.id,
                    evidence_type="rule-rationale",
                    source_package_version_key=rule_finding.source_package_version_key,
                    index_version_key=rule_finding.knowledge_index_version_key,
                    citation_id=f"{RULE_KEY}-fixture-rationale",
                    locator={"rule_key": RULE_KEY},
                    snippet=rule_finding.knowledge_evidence_snippet,
                    extra_metadata={"source": "fixture"},
                )
            )
        session.commit()


def _search_engine(chunks: tuple[ChunkEmbeddingInput, ...]) -> HybridSearchEngine:
    provider = DeterministicFakeEmbeddingProvider(dimension=32)
    vector_index = InMemoryVectorIndex(dimension=provider.dimension)
    vector_index.upsert(build_chunk_embedding_records(chunks, provider=provider))
    bm25_index = InMemoryBM25Index()
    bm25_index.upsert(
        [
            BM25Document(
                chunk_id=chunk.chunk_id,
                text=chunk.text,
                metadata=chunk.metadata,
            )
            for chunk in chunks
        ]
    )
    return HybridSearchEngine(
        embedding_provider=provider,
        vector_index=vector_index,
        bm25_index=bm25_index,
        rerank_provider=FakeRerankProvider(),
    )


def _chunk(
    *,
    chunk_id: UUID,
    text: str,
    source_path: str,
    source_collection: SourceCollection,
    document_type: str,
) -> ChunkEmbeddingInput:
    return ChunkEmbeddingInput(
        chunk_id=chunk_id,
        text=text,
        metadata={
            "source_collection": source_collection.value,
            "locator": {
                "type": "markdown-section",
                "source_path": source_path,
                "line_start": 1,
                "line_end": 1,
            },
            "index_version_key": "index-v1",
            "source_package_version_key": "package-v1",
            "year": 2024,
            "region": "国家",
            "document_type": document_type,
            "business_topic": "fund-supervision",
        },
    )


def _write_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path
