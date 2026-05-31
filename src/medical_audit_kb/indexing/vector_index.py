from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from uuid import UUID

from medical_audit_kb.indexing.embeddings import (
    EmbeddingProvider,
    EmbeddingVector,
    cosine_similarity,
)


@dataclass(frozen=True, slots=True)
class ChunkEmbeddingInput:
    chunk_id: UUID
    text: str
    metadata: dict[str, object]


@dataclass(frozen=True, slots=True)
class ChunkEmbeddingRecord:
    chunk_id: UUID
    text: str
    embedding: EmbeddingVector
    provider: str
    model_name: str
    provider_version: str
    dimension: int
    metadata: dict[str, object]

    def as_pgvector_row(self) -> dict[str, object]:
        return {
            "chunk_id": self.chunk_id,
            "provider": self.provider,
            "model_name": self.model_name,
            "provider_version": self.provider_version,
            "dimension": self.dimension,
            "embedding": list(self.embedding),
            "metadata": self.metadata,
        }


@dataclass(frozen=True, slots=True)
class VectorSearchResult:
    record: ChunkEmbeddingRecord
    score: float


class InMemoryVectorIndex:
    def __init__(self, *, dimension: int) -> None:
        if dimension <= 0:
            raise ValueError("dimension must be positive")
        self._dimension = dimension
        self._records_by_chunk_id: dict[UUID, ChunkEmbeddingRecord] = {}

    def upsert(self, records: Sequence[ChunkEmbeddingRecord]) -> None:
        for record in records:
            self._validate_dimension(record.embedding)
            self._records_by_chunk_id[record.chunk_id] = record

    def search(
        self,
        query_embedding: EmbeddingVector,
        *,
        top_k: int = 10,
        filters: Mapping[str, object] | None = None,
    ) -> tuple[VectorSearchResult, ...]:
        self._validate_dimension(query_embedding)
        matched_records = [
            record
            for record in self._records_by_chunk_id.values()
            if _metadata_matches(record.metadata, filters)
        ]
        scored = [
            VectorSearchResult(
                record=record,
                score=cosine_similarity(query_embedding, record.embedding),
            )
            for record in matched_records
        ]
        return tuple(sorted(scored, key=lambda result: result.score, reverse=True)[:top_k])

    @property
    def size(self) -> int:
        return len(self._records_by_chunk_id)

    def _validate_dimension(self, embedding: EmbeddingVector) -> None:
        if len(embedding) != self._dimension:
            raise ValueError(
                f"embedding dimension mismatch: expected {self._dimension}, got {len(embedding)}"
            )


def build_chunk_embedding_records(
    chunks: Sequence[ChunkEmbeddingInput],
    *,
    provider: EmbeddingProvider,
) -> tuple[ChunkEmbeddingRecord, ...]:
    embeddings = provider.embed_texts([chunk.text for chunk in chunks])
    return tuple(
        ChunkEmbeddingRecord(
            chunk_id=chunk.chunk_id,
            text=chunk.text,
            embedding=embedding,
            provider=provider.provider,
            model_name=provider.model_name,
            provider_version=provider.provider_version,
            dimension=provider.dimension,
            metadata=chunk.metadata,
        )
        for chunk, embedding in zip(chunks, embeddings, strict=True)
    )


def _metadata_matches(
    metadata: Mapping[str, object],
    filters: Mapping[str, object] | None,
) -> bool:
    if not filters:
        return True
    return all(metadata.get(key) == value for key, value in filters.items())
