import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from medical_audit_kb.api.agent_store import AGENT_ID_PREFIX, SqlAlchemyAgentStore
from medical_audit_kb.api.app import ApiState, create_app
from medical_audit_kb.core.config import KnowledgeQuerySettings, ModelProviderSettings
from medical_audit_kb.domain.constants import SourceCollection
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
        headers={"X-User-Id": "auditor-1"},
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
    assert body["citations"][0]["index_version_key"] == "index-v1"
    assert body["citations"][0]["source_package_version_key"] == "package-v1"
    assert body["basis_groups"][0]["title"] == "法规依据"
    assert body["query_log_index"] == 0

    logs_response = client.get("/query/logs")
    assert logs_response.status_code == 200
    assert logs_response.json()["items"][0]["user_identifier"] == "auditor-1"


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
        headers={"X-Role": "auditor"},
        json={"index_version_key": "candidate-next"},
    )
    assert forbidden_response.status_code == 403

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
        headers={"X-Role": "it-admin"},
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


def _write_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path
