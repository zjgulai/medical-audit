from collections.abc import Mapping
from uuid import UUID, uuid4

from medical_audit_kb.domain.constants import SourceCollection
from medical_audit_kb.indexing.bm25_index import BM25Document, BM25SearchResult, InMemoryBM25Index
from medical_audit_kb.indexing.embeddings import (
    DeterministicFakeEmbeddingProvider,
    EmbeddingProviderError,
)
from medical_audit_kb.indexing.vector_index import (
    ChunkEmbeddingInput,
    ChunkEmbeddingRecord,
    InMemoryVectorIndex,
    VectorSearchResult,
    build_chunk_embedding_records,
)
from medical_audit_kb.retrieval.filters import RetrievalFilters
from medical_audit_kb.retrieval.hybrid_search import HybridSearchEngine
from medical_audit_kb.retrieval.rerank import FakeRerankProvider


def test_hybrid_search_recalls_exact_term_and_keeps_locator_versions() -> None:
    engine, ids = _build_engine()

    results = engine.search("超量开药", top_k=3)

    assert results[0].chunk.chunk_id == ids["rule"]
    assert "bm25" in results[0].matched_by
    assert results[0].rerank_score is not None
    assert results[0].chunk.locator == {
        "type": "xlsx-row",
        "source_path": "智能监管“两库”规则和知识点/rules.xlsx",
        "sheet_name": "规则",
        "row_number": 2,
    }
    assert results[0].chunk.index_version_key == "index-v1"
    assert results[0].chunk.source_package_version_key == "package-v1"


def test_hybrid_search_handles_natural_language_question() -> None:
    engine, ids = _build_engine()

    results = engine.search("医疗机构如何保留医保基金审核依据", top_k=2)

    assert results
    assert results[0].chunk.chunk_id == ids["law"]
    assert results[0].chunk.metadata["article_number"] == "第一条"
    assert results[0].score > 0


def test_hybrid_search_filters_by_source_year_region_document_type_and_topic() -> None:
    engine, ids = _build_engine()

    results = engine.search(
        "医保基金监管",
        filters=RetrievalFilters(
            source_collections=(SourceCollection.MEDICAL_INSURANCE_LAWS,),
            years=(2024,),
            regions=("国家",),
            document_types=("law",),
            business_topics=("fund-supervision",),
        ),
        top_k=5,
    )

    assert [result.chunk.chunk_id for result in results] == [ids["law"]]


def test_hybrid_search_pushes_single_source_collection_into_candidate_recall() -> None:
    provider = DeterministicFakeEmbeddingProvider(dimension=32)
    target_id = uuid4()
    metadata = {
        "source_collection": SourceCollection.RISK_NEGATIVE_LIST.value,
        "locator": {"type": "pdf-page", "source_path": "风险负面清单/risk.pdf"},
        "index_version_key": "index-v1",
        "source_package_version_key": "package-v1",
    }
    vector_index = _FilterRequiredVectorIndex(target_id, metadata)
    bm25_index = _FilterRequiredBM25Index(target_id, metadata)
    engine = HybridSearchEngine(
        embedding_provider=provider,
        vector_index=vector_index,
        bm25_index=bm25_index,
        rerank_provider=None,
    )

    results = engine.search(
        "超量开药",
        filters=RetrievalFilters(source_collections=(SourceCollection.RISK_NEGATIVE_LIST,)),
        top_k=1,
        fetch_k=1,
    )

    expected_filter = {"source_collection": SourceCollection.RISK_NEGATIVE_LIST.value}
    assert vector_index.received_filters == expected_filter
    assert bm25_index.received_filters == expected_filter
    assert [result.chunk.chunk_id for result in results] == [target_id]


def test_hybrid_search_recalls_negative_list_term_before_global_candidate_truncation() -> None:
    target_id = uuid4()
    bm25_index = InMemoryBM25Index()
    documents = [
        BM25Document(
            chunk_id=uuid4(),
            text="超量开药 超量开药 超量开药",
            metadata={"source_collection": SourceCollection.SUPERVISION_RULES_KNOWLEDGE.value},
        )
        for _ in range(3)
    ]
    documents.append(
        BM25Document(
            chunk_id=target_id,
            text="超量开药是指超过规定剂量开具药品。",
            metadata={
                "source_collection": SourceCollection.RISK_NEGATIVE_LIST.value,
                "locator": {"type": "pdf-page", "source_path": "风险负面清单/risk.pdf"},
                "index_version_key": "index-v1",
                "source_package_version_key": "package-v1",
            },
        )
    )
    bm25_index.upsert(documents)
    engine = HybridSearchEngine(
        embedding_provider=_FailingEmbeddingProvider(),
        vector_index=InMemoryVectorIndex(dimension=32),
        bm25_index=bm25_index,
        rerank_provider=None,
    )

    results = engine.search(
        "超量开药",
        filters=RetrievalFilters(source_collections=(SourceCollection.RISK_NEGATIVE_LIST,)),
        top_k=1,
        fetch_k=1,
    )

    assert [result.chunk.chunk_id for result in results] == [target_id]
    assert "超过规定剂量" in results[0].chunk.text


def test_hybrid_search_title_only_matches_title_metadata_not_body_text() -> None:
    engine, ids = _build_engine()

    title_results = engine.search(
        "医保基金监管条例",
        filters=RetrievalFilters(title_only=True, title_query="医保基金监管条例"),
        top_k=5,
    )
    body_results = engine.search(
        "保留医保基金审核依据",
        filters=RetrievalFilters(title_only=True, title_query="保留医保基金审核依据"),
        top_k=5,
    )

    assert [result.chunk.chunk_id for result in title_results] == [ids["law"]]
    assert body_results == ()


def test_hybrid_search_source_weight_prioritizes_rule_basis_when_scores_tie() -> None:
    provider = DeterministicFakeEmbeddingProvider(dimension=32)
    shared_text = "医保基金监管共同依据"
    rule_id = uuid4()
    law_id = uuid4()
    chunks = [
        _chunk_input(
            rule_id,
            shared_text,
            source_collection=SourceCollection.SUPERVISION_RULES_KNOWLEDGE,
            locator={"type": "xlsx-row"},
        ),
        _chunk_input(
            law_id,
            shared_text,
            source_collection=SourceCollection.MEDICAL_INSURANCE_LAWS,
            locator={"type": "law-article"},
        ),
    ]
    engine = _engine_from_chunks(provider, chunks, rerank=False)

    results = engine.search("医保基金监管共同依据", top_k=2)

    assert [result.chunk.chunk_id for result in results] == [rule_id, law_id]
    assert results[0].source_weight > results[1].source_weight


def test_hybrid_search_accepts_custom_source_collection_weights() -> None:
    provider = DeterministicFakeEmbeddingProvider(dimension=32)
    shared_text = "医保基金监管共同依据"
    rule_id = uuid4()
    law_id = uuid4()
    chunks = [
        _chunk_input(
            rule_id,
            shared_text,
            source_collection=SourceCollection.SUPERVISION_RULES_KNOWLEDGE,
            locator={"type": "xlsx-row"},
        ),
        _chunk_input(
            law_id,
            shared_text,
            source_collection=SourceCollection.MEDICAL_INSURANCE_LAWS,
            locator={"type": "law-article"},
        ),
    ]

    # 默认权重：规则(1.35) 排在法规(1.0) 之前。
    default_results = _engine_from_chunks(provider, chunks, rerank=False).search(
        shared_text, top_k=2
    )
    assert [result.chunk.chunk_id for result in default_results] == [rule_id, law_id]

    # 注入候选权重把法规抬到最高 → 跨来源排序翻转，证明 A2 来源加权杠杆生效。
    custom_results = _engine_from_chunks(
        provider,
        chunks,
        rerank=False,
        source_collection_weights={
            SourceCollection.MEDICAL_INSURANCE_LAWS.value: 5.0,
            SourceCollection.SUPERVISION_RULES_KNOWLEDGE.value: 1.0,
        },
    ).search(shared_text, top_k=2)
    assert [result.chunk.chunk_id for result in custom_results] == [law_id, rule_id]


def test_hybrid_search_returns_cross_source_recall() -> None:
    engine, ids = _build_engine()

    results = engine.search("医保基金 超量开药 DRG目录", top_k=5)
    result_ids = {result.chunk.chunk_id for result in results}

    assert {ids["law"], ids["rule"], ids["catalog"]}.issubset(result_ids)


def test_retrieval_filters_accept_multiple_metadata_values() -> None:
    filters = RetrievalFilters(regions=("国家",), business_topics=("fund-supervision",))

    assert filters.matches(
        {
            "region": ["国家", "海南"],
            "business_topic": ["fund-supervision", "prescription-audit"],
        }
    )
    assert not filters.matches({"region": ["海南"], "business_topic": "fund-supervision"})


def test_hybrid_search_falls_back_to_bm25_when_embedding_provider_is_unavailable() -> None:
    chunk_id = uuid4()
    metadata = {
        "source_collection": SourceCollection.MEDICAL_INSURANCE_LAWS.value,
        "locator": {"type": "law-article"},
        "index_version_key": "index-v1",
        "source_package_version_key": "package-v1",
    }
    bm25_index = InMemoryBM25Index()
    bm25_index.upsert(
        [
            BM25Document(
                chunk_id=chunk_id,
                text="医疗机构发现异常收费时，应优先核验证据链、项目编码和收费依据。",
                metadata=metadata,
            )
        ]
    )
    engine = HybridSearchEngine(
        embedding_provider=_FailingEmbeddingProvider(),
        vector_index=InMemoryVectorIndex(dimension=32),
        bm25_index=bm25_index,
        rerank_provider=None,
    )

    results = engine.search("异常收费 证据链", top_k=1)

    assert results[0].chunk.chunk_id == chunk_id
    assert results[0].matched_by == ("bm25",)
    assert results[0].vector_score == 0


def _build_engine() -> tuple[HybridSearchEngine, dict[str, UUID]]:
    provider = DeterministicFakeEmbeddingProvider(dimension=32)
    ids = {
        "law": uuid4(),
        "rule": uuid4(),
        "catalog": uuid4(),
        "risk": uuid4(),
    }
    chunks = [
        _chunk_input(
            ids["law"],
            "第一条 医疗机构应当保留医保基金审核依据并配合监督检查。",
            source_collection=SourceCollection.MEDICAL_INSURANCE_LAWS,
            locator={
                "type": "law-article",
                "source_path": "全量法律/医保基金监管条例.md",
                "article_number": "第一条",
                "line_start": 1,
                "line_end": 2,
            },
            article_number="第一条",
            year=2024,
            region="国家",
            document_type="law",
            business_topic="fund-supervision",
            title="医保基金监管条例",
        ),
        _chunk_input(
            ids["rule"],
            "规则编码: R001\n规则名称: 超量开药\n说明: 超过限定数量。",
            source_collection=SourceCollection.SUPERVISION_RULES_KNOWLEDGE,
            locator={
                "type": "xlsx-row",
                "source_path": "智能监管“两库”规则和知识点/rules.xlsx",
                "sheet_name": "规则",
                "row_number": 2,
            },
            year=2025,
            region="国家",
            document_type="rule",
            business_topic="prescription-audit",
        ),
        _chunk_input(
            ids["catalog"],
            "DRG目录包含按病组付费分组方案和医保目录编码。",
            source_collection=SourceCollection.MEDICAL_INSURANCE_CATALOG,
            locator={"type": "pdf-page", "source_path": "医保目录/DRG.pdf", "page_number": 1},
            year=2024,
            region="国家",
            document_type="catalog",
            business_topic="catalog-query",
        ),
        _chunk_input(
            ids["risk"],
            "风险负面清单提示重复收费和违规收费风险。",
            source_collection=SourceCollection.RISK_NEGATIVE_LIST,
            locator={"type": "pdf-page", "source_path": "风险负面清单/risk.pdf", "page_number": 1},
            year=2024,
            region="国家",
            document_type="risk-list",
            business_topic="risk-warning",
        ),
    ]
    return _engine_from_chunks(provider, chunks, rerank=True), ids


def _engine_from_chunks(
    provider: DeterministicFakeEmbeddingProvider,
    chunks: list[ChunkEmbeddingInput],
    *,
    rerank: bool,
    source_collection_weights: dict[str, float] | None = None,
) -> HybridSearchEngine:
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
        rerank_provider=FakeRerankProvider() if rerank else None,
        source_collection_weights=source_collection_weights,
    )


class _FailingEmbeddingProvider:
    provider = "openai"
    model_name = "kimi-for-coding"
    provider_version = "v1"
    dimension = 32

    def embed_texts(self, texts: list[str]) -> tuple[tuple[float, ...], ...]:
        raise EmbeddingProviderError("embedding provider quota exhausted")


class _FilterRequiredVectorIndex:
    def __init__(self, chunk_id: UUID, metadata: dict[str, object]) -> None:
        self.received_filters: dict[str, object] | None = None
        self._result = VectorSearchResult(
            record=ChunkEmbeddingRecord(
                chunk_id=chunk_id,
                text="超量开药是指超过规定剂量开具药品。",
                embedding=tuple(0.0 for _ in range(32)),
                provider="fake",
                model_name="fake-embedding",
                provider_version="v1",
                dimension=32,
                metadata=metadata,
            ),
            score=0.8,
        )

    def search(
        self,
        query_embedding: tuple[float, ...],
        *,
        top_k: int = 10,
        filters: Mapping[str, object] | None = None,
    ) -> tuple[VectorSearchResult, ...]:
        _ = query_embedding, top_k
        self.received_filters = dict(filters) if filters else None
        return (self._result,) if self.received_filters else ()


class _FilterRequiredBM25Index:
    def __init__(self, chunk_id: UUID, metadata: dict[str, object]) -> None:
        self.received_filters: dict[str, object] | None = None
        self._result = BM25SearchResult(
            document=BM25Document(
                chunk_id=chunk_id,
                text="超量开药是指超过规定剂量开具药品。",
                metadata=metadata,
            ),
            score=1.0,
        )

    def search(
        self,
        query: str,
        *,
        top_k: int = 10,
        filters: Mapping[str, object] | None = None,
    ) -> tuple[BM25SearchResult, ...]:
        _ = query, top_k
        self.received_filters = dict(filters) if filters else None
        return (self._result,) if self.received_filters else ()


def _chunk_input(
    chunk_id: UUID,
    text: str,
    *,
    source_collection: SourceCollection,
    locator: dict[str, object],
    article_number: str | None = None,
    year: int = 2024,
    region: str = "国家",
    document_type: str = "law",
    business_topic: str = "fund-supervision",
    title: str | None = None,
) -> ChunkEmbeddingInput:
    return ChunkEmbeddingInput(
        chunk_id=chunk_id,
        text=text,
        metadata={
            "source_collection": source_collection.value,
            "locator": locator,
            "index_version_key": "index-v1",
            "source_package_version_key": "package-v1",
            "article_number": article_number,
            "year": year,
            "region": region,
            "document_type": document_type,
            "business_topic": business_topic,
            **({"title": title, "title_path": [title]} if title else {}),
        },
    )
