from uuid import uuid4

from medical_audit_kb.indexing.bm25_index import BM25Document, InMemoryBM25Index
from medical_audit_kb.indexing.embeddings import (
    DeterministicFakeEmbeddingProvider,
    EmbeddingMetadata,
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
