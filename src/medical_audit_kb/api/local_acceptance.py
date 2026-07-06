from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import FastAPI

from medical_audit_kb.api.agent_store import InMemoryAgentStore
from medical_audit_kb.api.analytics_upload_store import InMemoryAnalyticsUploadStore
from medical_audit_kb.api.app import ApiState, create_app
from medical_audit_kb.api.auth_user_store import InMemoryAuthUserStore
from medical_audit_kb.api.document_upload_store import InMemoryDocumentUploadStore
from medical_audit_kb.api.project_member_store import InMemoryProjectMemberStore
from medical_audit_kb.api.query_history_store import InMemoryQueryHistoryStore
from medical_audit_kb.api.review_task_store import InMemoryReviewTaskStore
from medical_audit_kb.core.config import KnowledgeQuerySettings, ModelProviderSettings
from medical_audit_kb.domain.constants import SourceCollection
from medical_audit_kb.generation.citations import Citation
from medical_audit_kb.indexing.bm25_index import BM25Document, InMemoryBM25Index
from medical_audit_kb.indexing.embeddings import DeterministicFakeEmbeddingProvider
from medical_audit_kb.indexing.vector_index import (
    ChunkEmbeddingInput,
    InMemoryVectorIndex,
    build_chunk_embedding_records,
)
from medical_audit_kb.ingestion.pipeline import KnowledgeIndexPipeline
from medical_audit_kb.preview.resolver import PreviewResolver
from medical_audit_kb.retrieval.hybrid_search import HybridSearchEngine
from medical_audit_kb.retrieval.rerank import FakeRerankProvider

DEFAULT_LOCAL_ACCEPTANCE_ROOT = Path("tmp/local-acceptance-api")
LOCAL_ACCEPTANCE_DATABASE_URL = (
    "postgresql+psycopg://local:local@127.0.0.1:5433/local_acceptance"
)
LOCAL_ACCEPTANCE_CHAT_MODEL_ENV: dict[str, str] = {
    "MEDICAL_AUDIT_KB_ALLOW_FAKE_CHAT_MODELS": "1",
    "MEDICAL_AUDIT_LOCAL_ACCEPTANCE_FAKE_KEY": "local-acceptance-placeholder",
    "MEDICAL_AUDIT_KB_CHAT_MODEL_KIMI_2_7_API_KEY_ENV": (
        "MEDICAL_AUDIT_LOCAL_ACCEPTANCE_FAKE_KEY"
    ),
    "MEDICAL_AUDIT_KB_CHAT_MODEL_KIMI_2_7_PROVIDER": "fake",
    "MEDICAL_AUDIT_KB_CHAT_MODEL_KIMI_2_7_MODEL": "local-acceptance-kimi",
    "MEDICAL_AUDIT_KB_CHAT_MODEL_DEEPSEEK_V4_PRO_API_KEY_ENV": (
        "MEDICAL_AUDIT_LOCAL_ACCEPTANCE_FAKE_KEY"
    ),
    "MEDICAL_AUDIT_KB_CHAT_MODEL_DEEPSEEK_V4_PRO_PROVIDER": "fake",
    "MEDICAL_AUDIT_KB_CHAT_MODEL_DEEPSEEK_V4_PRO_MODEL": "local-acceptance-deepseek",
}


class LocalAcceptanceAnswerProvider:
    provider = "fake"
    model_name = "local-acceptance-chat"
    provider_version = "v1"

    def generate_answer(self, question: str, citations: Sequence[Citation]) -> str:
        if not citations:
            return f"本地验收回答：{question} 暂无可引用依据。"
        return f"本地验收回答：应核验医保基金审核依据 {citations[0].marker}。"


def create_local_acceptance_app(state_root: Path | str | None = None) -> FastAPI:
    """Create the local fullstack acceptance API.

    This profile is intentionally local-only: no provider calls, no production
    probes, and no PostgreSQL store use. It exists so the rebuilt frontend can
    exercise real HTTP routes during smoke checks.
    """

    return create_app(create_local_acceptance_state(state_root))


def create_local_acceptance_state(state_root: Path | str | None = None) -> ApiState:
    configure_local_acceptance_chat_models()
    root = Path(state_root or DEFAULT_LOCAL_ACCEPTANCE_ROOT)
    source_root = root / "data"
    index_root = root / "index"
    source_path = _write_local_acceptance_source(source_root)
    settings = KnowledgeQuerySettings(
        data_root=source_root,
        index_root=index_root,
        database_url=LOCAL_ACCEPTANCE_DATABASE_URL,
        model_provider=ModelProviderSettings(
            provider="fake",
            api_key_env="MEDICAL_AUDIT_LOCAL_ACCEPTANCE_FAKE_KEY",
            embedding_model="local-acceptance-embedding",
            chat_model="local-acceptance-chat",
        ),
        source_collection_weights={
            SourceCollection.MEDICAL_INSURANCE_CATALOG.value: 1.25,
            SourceCollection.SUPERVISION_RULES_KNOWLEDGE.value: 1.35,
            SourceCollection.RISK_NEGATIVE_LIST.value: 1.1,
            SourceCollection.MEDICAL_INSURANCE_LAWS.value: 1.0,
        },
    )
    index_root.mkdir(parents=True, exist_ok=True)
    return ApiState(
        settings=settings,
        index_pipeline=KnowledgeIndexPipeline(),
        preview_resolver=PreviewResolver(source_root=source_root),
        search_engine=_local_acceptance_search_engine(
            chunk_id=_local_acceptance_chunk_id(source_path),
            source_path=source_path.relative_to(source_root).as_posix(),
        ),
        search_backend="local-acceptance",
        search_backend_details={
            "provider_call": False,
            "database_write": False,
            "postgres_store": False,
            "source_collection": SourceCollection.MEDICAL_INSURANCE_LAWS.value,
        },
        review_task_store=InMemoryReviewTaskStore(),
        audit_finding_store=None,
        audit_log_store=None,
        agent_store=InMemoryAgentStore(),
        project_member_store=InMemoryProjectMemberStore(),
        analytics_upload_store=InMemoryAnalyticsUploadStore(
            upload_root=index_root / "analytics-uploads",
        ),
        document_upload_store=InMemoryDocumentUploadStore(
            upload_root=index_root / "document-uploads",
        ),
        document_upload_indexer=None,
        query_history_store=InMemoryQueryHistoryStore(),
        auth_user_store=InMemoryAuthUserStore(),
        answer_generation_provider=LocalAcceptanceAnswerProvider(),
    )


def configure_local_acceptance_chat_models() -> None:
    for name, value in LOCAL_ACCEPTANCE_CHAT_MODEL_ENV.items():
        os.environ.setdefault(name, value)


def _write_local_acceptance_source(source_root: Path) -> Path:
    source_path = source_root / "全量法律" / "law.md"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text(
        "\n".join(
            [
                "第一条 医疗机构应当保留医保基金审核依据。",
                "第二条 审计人员应结合病历、费用明细和政策目录进行复核。",
            ]
        ),
        encoding="utf-8",
    )
    return source_path


def _local_acceptance_search_engine(
    *,
    chunk_id: UUID,
    source_path: str,
) -> HybridSearchEngine:
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
            "index_version_key": "local-acceptance-index-v1",
            "source_package_version_key": "local-acceptance-package-v1",
            "title": "医保基金审核依据",
            "source_path": source_path,
            "title_path": ["医保基金审核依据"],
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
        source_collection_weights={
            SourceCollection.MEDICAL_INSURANCE_CATALOG.value: 1.25,
            SourceCollection.SUPERVISION_RULES_KNOWLEDGE.value: 1.35,
            SourceCollection.RISK_NEGATIVE_LIST.value: 1.1,
            SourceCollection.MEDICAL_INSURANCE_LAWS.value: 1.0,
        },
    )


def _local_acceptance_chunk_id(source_path: Path) -> UUID:
    return uuid5(NAMESPACE_URL, source_path.as_posix())
