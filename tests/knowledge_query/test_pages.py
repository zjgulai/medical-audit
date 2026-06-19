import hashlib
from pathlib import Path
from typing import cast
from uuid import UUID

from fastapi.testclient import TestClient

from medical_audit_kb.api.app import ApiState, create_app
from medical_audit_kb.api.audit_finding_store import SqlAlchemyAuditFindingStore
from medical_audit_kb.api.audit_log_store import SqlAlchemyAuditLogStore
from medical_audit_kb.api.query_history_store import InMemoryQueryHistoryStore
from medical_audit_kb.api.review_task_store import (
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


def test_query_page_scopes_personal_materials_to_current_user(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    state.search_engine = _search_engine(
        (
            _chunk(
                chunk_id=PERSONAL_OWNER_CHUNK_ID,
                text="个人补充材料 门诊费用审核依据 来自审计员一",
                source_path="personal-materials/auditor-1/note.txt",
                source_collection=SourceCollection.PERSONAL_MATERIALS,
                document_type="personal-upload",
                created_by="auditor-1",
                visibility="private",
            ),
            _chunk(
                chunk_id=PERSONAL_OTHER_CHUNK_ID,
                text="个人补充材料 门诊费用审核依据 来自审计员二",
                source_path="personal-materials/auditor-2/note.txt",
                source_collection=SourceCollection.PERSONAL_MATERIALS,
                document_type="personal-upload",
                created_by="auditor-2",
                visibility="private",
            ),
        )
    )
    client = TestClient(create_app(state))
    params = {
        "question": "个人补充材料 门诊费用审核依据",
        "source_collection": SourceCollection.PERSONAL_MATERIALS.value,
    }

    owner_response = client.get(
        "/pages/query",
        headers={"X-User-Id": "auditor-1", "X-Role": "auditor"},
        params=params,
    )
    other_response = client.get(
        "/pages/query",
        headers={"X-User-Id": "auditor-3", "X-Role": "auditor"},
        params=params,
    )

    assert owner_response.status_code == 200
    assert "来自审计员一" in owner_response.text
    assert "来自审计员二" not in owner_response.text
    assert state.query_logs[-1]["user_identifier"] == "auditor-1"
    assert state.query_logs[-1]["retrieved_chunk_ids"] == [str(PERSONAL_OWNER_CHUNK_ID)]
    assert other_response.status_code == 200
    assert "没有找到可引用依据。" in other_response.text


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
    assert "导出 JSON 记录" in response.text
    assert "复制引用" in response.text
    assert "把以上依据整理成审核要点清单" in response.text
    assert f"/pages/preview/{LAW_CHUNK_ID}" in response.text
    assert "<pre>" not in response.text
    assert state.operation_logs[-1]["action"] == "page-chat"


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
        data={"signed_by": "审计科负责人A"},
        follow_redirects=False,
    )
    assert blocked_signoff_response.status_code == 409

    update_response = client.post(
        "/pages/review-tasks/review-task-0001/status",
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
    assert dossier["owner_signoff"]["confirmed_by"] == "审计科负责人A"
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
    assert "导出报告草稿 Markdown" in updated_page_response.text

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
    assert signed_report["signed_by"] == "审计科负责人A"
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
        headers={"X-User-Id": "auditor-a", "X-Role": "auditor"},
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
        headers={"X-User-Id": "auditor-a", "X-Role": "auditor"},
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
    assert readonly_block_payloads[0]["user_identifier"] == "auditor-a"
    assert readonly_block_payloads[2]["role"] == "department-head"
    assert {payload["auth_source"] for payload in readonly_block_payloads} == {"legacy-header"}
    assert {payload["normalized_role"] for payload in readonly_block_payloads} == {
        "auditor",
        "department-head",
    }


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
    assert rejected_response.json()["detail"] == (
        "audit log access requires it-admin or department-head role"
    )
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
    assert state.operation_logs[-1]["action"] == "audit-logs-access-denied"
    assert state.operation_logs[-1]["payload"]["normalized_role"] == "auditor"
    assert state.operation_logs[-1]["payload"]["auth_source"] == "legacy-header"


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
PERSONAL_OWNER_CHUNK_ID = UUID("33333333-3333-4333-8333-333333333333")
PERSONAL_OTHER_CHUNK_ID = UUID("44444444-4444-4444-8444-444444444444")


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
    created_by: str | None = None,
    visibility: str | None = None,
) -> ChunkEmbeddingInput:
    metadata: dict[str, object] = {
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
    }
    if created_by is not None:
        metadata["created_by"] = created_by
    if visibility is not None:
        metadata["visibility"] = visibility
    return ChunkEmbeddingInput(
        chunk_id=chunk_id,
        text=text,
        metadata=metadata,
    )


def _write_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path
