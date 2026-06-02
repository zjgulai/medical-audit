from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient

from medical_audit_kb.api.app import ApiState, create_app
from medical_audit_kb.core.config import KnowledgeQuerySettings, ModelProviderSettings
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
    assert 'aria-current="page">查询工作台' in response.text
    assert 'aria-describedby="question-help"' in response.text
    assert "required" in response.text
    assert SourceCollection.MEDICAL_INSURANCE_LAWS.value in response.text


def test_root_path_renders_chat_workbench(tmp_path: Path) -> None:
    client = TestClient(create_app(_api_state(tmp_path)))

    response = client.get("/")

    assert response.status_code == 200
    assert "医保审核对话审证台" in response.text
    assert 'aria-current="page">对话审证' in response.text


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
    assert state.operation_logs[-1]["action"] == "page-query"
    assert state.query_logs[-1]["question"] == "医保基金审核依据"


def test_chat_page_renders_conversation_evidence_and_followups(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    client = TestClient(create_app(state))

    response = client.get("/pages/chat", params={"question": "医保基金审核依据"})

    assert response.status_code == 200
    assert "医保审核对话审证台" in response.text
    assert "AuditScope" in response.text
    assert "Evidence Command Center" in response.text
    assert "审证流程 · Case Review" in response.text
    assert "审计问题输入" in response.text
    assert "Evidence Dossier" in response.text
    assert "证据卷宗" in response.text
    assert "可追溯回答" in response.text
    assert "把以上依据整理成审核要点清单" in response.text
    assert f"/pages/preview/{LAW_CHUNK_ID}" in response.text
    assert "<pre>" not in response.text
    assert state.operation_logs[-1]["action"] == "page-chat"


def test_preview_page_renders_source_context_after_query(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    client = TestClient(create_app(state))
    client.get("/pages/query", params={"question": "医保基金审核依据"})

    response = client.get(f"/pages/preview/{LAW_CHUNK_ID}")

    assert response.status_code == 200
    assert "原文证据预览" in response.text
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
    assert 'aria-current="page">索引管理' in response.text
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


def test_operation_logs_export_records_export_operation(tmp_path: Path) -> None:
    state = _api_state(tmp_path)
    client = TestClient(create_app(state))
    client.get("/pages/index-admin")

    response = client.get("/operation/logs/export")

    assert response.status_code == 200
    body = response.json()
    assert body["format"] == "json"
    assert body["items"][-1]["action"] == "operation-logs-export"


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
