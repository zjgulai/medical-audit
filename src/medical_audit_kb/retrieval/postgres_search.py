from __future__ import annotations

from collections.abc import Mapping
from typing import cast
from uuid import UUID

import psycopg

from medical_audit_kb.indexing.bm25_index import BM25Document, InMemoryBM25Index
from medical_audit_kb.indexing.embeddings import EmbeddingProvider, EmbeddingVector
from medical_audit_kb.indexing.vector_index import ChunkEmbeddingRecord, VectorSearchResult
from medical_audit_kb.retrieval.hybrid_search import HybridSearchEngine
from medical_audit_kb.retrieval.rerank import FakeRerankProvider, RerankProvider

DEFAULT_FETCH_MULTIPLIER = 3


class PostgresVectorIndex:
    def __init__(
        self,
        *,
        database_url: str,
        provider: str,
        model_name: str,
        provider_version: str,
        dimension: int,
    ) -> None:
        if dimension <= 0:
            raise ValueError("dimension must be positive")
        self._database_url = _normalize_psycopg_database_url(database_url)
        self._provider = provider
        self._model_name = model_name
        self._provider_version = provider_version
        self._dimension = dimension

    def search(
        self,
        query_embedding: EmbeddingVector,
        *,
        top_k: int = 10,
        filters: Mapping[str, object] | None = None,
    ) -> tuple[VectorSearchResult, ...]:
        if len(query_embedding) != self._dimension:
            raise ValueError(
                "embedding dimension mismatch: "
                f"expected {self._dimension}, got {len(query_embedding)}"
            )
        if top_k <= 0:
            return ()
        vector_literal = _vector_literal(query_embedding)
        rows = _query_vector_rows(
            self._database_url,
            vector_literal=vector_literal,
            provider=self._provider,
            model_name=self._model_name,
            provider_version=self._provider_version,
            dimension=self._dimension,
            fetch_k=_fetch_k_for_filters(top_k, filters),
        )
        results = tuple(_vector_search_result(row) for row in rows)
        if filters:
            results = tuple(
                result for result in results if _metadata_matches(result.record.metadata, filters)
            )
        return results[:top_k]


def load_postgres_hybrid_search_engine(
    *,
    database_url: str,
    embedding_provider: EmbeddingProvider,
    rerank_provider: RerankProvider | None = None,
) -> HybridSearchEngine:
    bm25_index = load_postgres_bm25_index(database_url)
    vector_index = PostgresVectorIndex(
        database_url=database_url,
        provider=embedding_provider.provider,
        model_name=embedding_provider.model_name,
        provider_version=embedding_provider.provider_version,
        dimension=embedding_provider.dimension,
    )
    return HybridSearchEngine(
        embedding_provider=embedding_provider,
        vector_index=vector_index,
        bm25_index=bm25_index,
        rerank_provider=rerank_provider or cast(RerankProvider, FakeRerankProvider()),
    )


def load_postgres_bm25_index(database_url: str) -> InMemoryBM25Index:
    index = InMemoryBM25Index()
    with (
        psycopg.connect(_normalize_psycopg_database_url(database_url)) as connection,
        connection.cursor() as cursor,
    ):
        cursor.execute(
            """
            SELECT dc.id, dc.text, dc.metadata
            FROM document_chunks dc
            JOIN source_documents sd ON sd.id = dc.source_document_id
            JOIN index_versions iv ON iv.source_package_version_id = sd.source_package_version_id
            WHERE iv.status = 'active'
              AND sd.status = 'indexed'
            ORDER BY dc.id
            """
        )
        index.upsert(
            tuple(
                BM25Document(
                    chunk_id=chunk_id,
                    text=text,
                    metadata=_object_dict(metadata),
                )
                for chunk_id, text, metadata in cursor.fetchall()
            )
        )
    return index


def _query_vector_rows(
    database_url: str,
    *,
    vector_literal: str,
    provider: str,
    model_name: str,
    provider_version: str,
    dimension: int,
    fetch_k: int,
) -> tuple[tuple[object, ...], ...]:
    with psycopg.connect(database_url) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                ce.chunk_id,
                dc.text,
                dc.metadata,
                ce.provider,
                ce.model_name,
                ce.provider_version,
                ce.dimension,
                1 - (ce.embedding <=> %s::vector) AS score
            FROM chunk_embeddings ce
            JOIN document_chunks dc ON dc.id = ce.chunk_id
            JOIN source_documents sd ON sd.id = dc.source_document_id
            JOIN index_versions iv ON iv.source_package_version_id = sd.source_package_version_id
            WHERE ce.provider = %s
              AND ce.model_name = %s
              AND ce.provider_version = %s
              AND ce.dimension = %s
              AND iv.status = 'active'
              AND sd.status = 'indexed'
            ORDER BY ce.embedding <=> %s::vector
            LIMIT %s
            """,
            (
                vector_literal,
                provider,
                model_name,
                provider_version,
                dimension,
                vector_literal,
                fetch_k,
            ),
        )
        return tuple(cursor.fetchall())


def _vector_search_result(row: tuple[object, ...]) -> VectorSearchResult:
    (
        chunk_id,
        text,
        metadata,
        provider,
        model_name,
        provider_version,
        dimension,
        score,
    ) = row
    return VectorSearchResult(
        record=ChunkEmbeddingRecord(
            chunk_id=_uuid_value(chunk_id),
            text=str(text),
            embedding=(),
            provider=str(provider),
            model_name=str(model_name),
            provider_version=str(provider_version),
            dimension=_int_value(dimension),
            metadata=_object_dict(metadata),
        ),
        score=_float_value(score),
    )


def _fetch_k_for_filters(
    top_k: int,
    filters: Mapping[str, object] | None,
) -> int:
    if not filters:
        return top_k
    return max(top_k * DEFAULT_FETCH_MULTIPLIER, top_k)


def _metadata_matches(
    metadata: Mapping[str, object],
    filters: Mapping[str, object],
) -> bool:
    return all(metadata.get(key) == value for key, value in filters.items())


def _normalize_psycopg_database_url(database_url: str) -> str:
    return database_url.replace("postgresql+psycopg://", "postgresql://", 1)


def _vector_literal(value: EmbeddingVector) -> str:
    return "[" + ",".join(format(float(item), ".9g") for item in value) + "]"


def _object_dict(value: object) -> dict[str, object]:
    return dict(value) if isinstance(value, dict) else {}


def _uuid_value(value: object) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


def _int_value(value: object) -> int:
    if not isinstance(value, int):
        raise ValueError("dimension must be an integer")
    return value


def _float_value(value: object) -> float:
    if isinstance(value, int | float):
        return float(value)
    raise ValueError("score must be numeric")
