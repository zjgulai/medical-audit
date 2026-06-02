from uuid import uuid4

import httpx

from medical_audit_kb.indexing.bm25_index import BM25Document, InMemoryBM25Index
from medical_audit_kb.indexing.embeddings import (
    DeterministicFakeEmbeddingProvider,
    EmbeddingMetadata,
    EmbeddingProviderError,
    OpenAICompatibleEmbeddingProvider,
    tokenize_text,
)
from medical_audit_kb.indexing.vector_index import (
    ChunkEmbeddingInput,
    InMemoryVectorIndex,
    build_chunk_embedding_records,
)


def test_fake_embedding_is_deterministic_and_records_provider_metadata() -> None:
    provider = DeterministicFakeEmbeddingProvider(dimension=16)

    first = provider.embed_texts(["医保基金监管"])[0]
    second = provider.embed_texts(["医保基金监管"])[0]
    metadata = EmbeddingMetadata.from_provider(provider)

    assert first == second
    assert len(first) == 16
    assert metadata.provider == "fake"
    assert metadata.model_name == "deterministic-token-hashing"
    assert metadata.provider_version == "v1"
    assert metadata.dimension == 16


def test_tokenize_text_keeps_medical_catalog_codes_as_exact_terms() -> None:
    tokens = tokenize_text("ICD-10医保2.0版中 A00.0 和 C34.9 的诊断名称")

    assert "a00.0" in tokens
    assert "c34.9" in tokens


def test_openai_compatible_embedding_provider_posts_batches_and_validates_dimension() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 0, "embedding": [1.0, 0.0, 0.0]},
                    {"index": 1, "embedding": [0.0, 1.0, 0.0]},
                ]
            },
        )

    provider = OpenAICompatibleEmbeddingProvider(
        api_key="test-key",
        model_name="custom-embedding",
        dimension=3,
        base_url="https://example.test/v1",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    embeddings = provider.embed_texts(["医保审核", "超量开药"])

    assert embeddings == ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0))
    assert requests[0].url == "https://example.test/v1/embeddings"
    assert requests[0].headers["authorization"] == "Bearer test-key"


def test_openai_compatible_embedding_provider_requires_dimension_for_unknown_model() -> None:
    try:
        OpenAICompatibleEmbeddingProvider(api_key="test-key", model_name="custom-embedding")
    except EmbeddingProviderError as exc:
        assert "dimension must be provided" in str(exc)
    else:
        raise AssertionError("expected EmbeddingProviderError")


def test_vector_index_recalls_semantically_matching_fake_embedding() -> None:
    provider = DeterministicFakeEmbeddingProvider(dimension=32)
    target_chunk_id = uuid4()
    records = build_chunk_embedding_records(
        [
            ChunkEmbeddingInput(
                chunk_id=target_chunk_id,
                text="医保基金监管要求医疗机构保留审核依据",
                metadata={"source_collection": "medical-insurance-laws", "year": 2024},
            ),
            ChunkEmbeddingInput(
                chunk_id=uuid4(),
                text="DRG付费分组方案说明",
                metadata={"source_collection": "medical-insurance-catalog", "year": 2024},
            ),
        ],
        provider=provider,
    )
    index = InMemoryVectorIndex(dimension=provider.dimension)
    index.upsert(records)

    query_embedding = provider.embed_texts(["医保基金监管"])[0]
    results = index.search(
        query_embedding,
        top_k=1,
        filters={"source_collection": "medical-insurance-laws"},
    )

    assert len(results) == 1
    assert results[0].record.chunk_id == target_chunk_id
    assert results[0].score > 0


def test_vector_index_uses_numpy_path_without_filters_and_returns_ordered_results() -> None:
    provider = DeterministicFakeEmbeddingProvider(dimension=16)
    target_chunk_id = uuid4()
    records = build_chunk_embedding_records(
        [
            ChunkEmbeddingInput(
                chunk_id=target_chunk_id,
                text="医保基金监管审核依据",
                metadata={"source_collection": "medical-insurance-laws"},
            ),
            ChunkEmbeddingInput(
                chunk_id=uuid4(),
                text="城市绿化管理条例",
                metadata={"source_collection": "medical-insurance-laws"},
            ),
        ],
        provider=provider,
    )
    index = InMemoryVectorIndex(dimension=provider.dimension)
    index.upsert(records)

    query_embedding = provider.embed_texts(["医保基金监管"])[0]
    results = index.search(query_embedding, top_k=2)

    assert len(results) == 2
    assert results[0].record.chunk_id == target_chunk_id
    assert results[0].score >= results[1].score


def test_chunk_embedding_records_can_be_serialized_for_pgvector_rows() -> None:
    provider = DeterministicFakeEmbeddingProvider(dimension=8)
    chunk_id = uuid4()
    record = build_chunk_embedding_records(
        [
            ChunkEmbeddingInput(
                chunk_id=chunk_id,
                text="超量开药风险",
                metadata={"article_number": "第一条"},
            )
        ],
        provider=provider,
    )[0]

    row = record.as_pgvector_row()

    assert row["chunk_id"] == chunk_id
    assert row["provider"] == "fake"
    assert row["model_name"] == "deterministic-token-hashing"
    assert row["provider_version"] == "v1"
    assert row["dimension"] == 8
    assert isinstance(row["embedding"], list)
    assert len(row["embedding"]) == 8
    assert row["metadata"] == {"article_number": "第一条"}


def test_bm25_recalls_by_policy_number_article_number_and_term() -> None:
    policy_chunk_id = uuid4()
    article_chunk_id = uuid4()
    term_chunk_id = uuid4()
    index = InMemoryBM25Index()
    index.upsert(
        [
            BM25Document(
                chunk_id=policy_chunk_id,
                text="国家医保发〔2024〕11号 关于医保支付方式管理的通知",
                metadata={"source_collection": "medical-insurance-laws"},
            ),
            BM25Document(
                chunk_id=article_chunk_id,
                text="医疗机构应当配合监督检查。",
                metadata={
                    "source_collection": "medical-insurance-laws",
                    "article_number": "第二条",
                },
            ),
            BM25Document(
                chunk_id=term_chunk_id,
                text="规则名称: 超量开药\n说明: 超过限定数量",
                metadata={"source_collection": "supervision-rules-knowledge"},
            ),
        ]
    )

    policy_results = index.search("医保发 2024 11号", top_k=1)
    article_results = index.search("第二条", top_k=1)
    term_results = index.search(
        "超量开药",
        top_k=1,
        filters={"source_collection": "supervision-rules-knowledge"},
    )

    assert policy_results[0].document.chunk_id == policy_chunk_id
    assert article_results[0].document.chunk_id == article_chunk_id
    assert term_results[0].document.chunk_id == term_chunk_id


def test_bm25_ranks_exact_medical_catalog_code_above_broad_code_range() -> None:
    target_chunk_id = uuid4()
    broad_range_chunk_id = uuid4()
    index = InMemoryBM25Index()
    index.upsert(
        [
            BM25Document(
                chunk_id=broad_range_chunk_id,
                text="1 A00-B99 某些传染病和寄生虫病 A15-A19 结核病",
                metadata={"source_collection": "medical-insurance-catalog"},
            ),
            BM25Document(
                chunk_id=target_chunk_id,
                text="A00 霍乱 A00.0 霍乱，由于O1群霍乱弧菌，霍乱生物型所致",
                metadata={"source_collection": "medical-insurance-catalog"},
            ),
        ]
    )

    results = index.search("A00.0 对应的诊断名称是什么？", top_k=2)

    assert results[0].document.chunk_id == target_chunk_id


def test_bm25_returns_no_results_for_unmatched_query() -> None:
    index = InMemoryBM25Index()
    index.upsert(
        [
            BM25Document(
                chunk_id=uuid4(),
                text="医保目录内容",
                metadata={"source_collection": "medical-insurance-catalog"},
            )
        ]
    )

    assert index.search("完全无关的罕见词") == ()
