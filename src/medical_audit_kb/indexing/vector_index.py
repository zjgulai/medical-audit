from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from heapq import nlargest
from typing import cast
from uuid import UUID

import numpy as np
import numpy.typing as npt

from medical_audit_kb.indexing.embeddings import (
    EmbeddingProvider,
    EmbeddingVector,
    vector_norm,
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


@dataclass(frozen=True, slots=True)
class _IndexedVectorRecord:
    record: ChunkEmbeddingRecord
    norm: float


class InMemoryVectorIndex:
    def __init__(self, *, dimension: int) -> None:
        if dimension <= 0:
            raise ValueError("dimension must be positive")
        self._dimension = dimension
        self._records_by_chunk_id: dict[UUID, _IndexedVectorRecord] = {}
        self._matrix_records: tuple[_IndexedVectorRecord, ...] = ()
        self._normalized_matrix: npt.NDArray[np.float32] | None = None

    def upsert(self, records: Sequence[ChunkEmbeddingRecord]) -> None:
        for record in records:
            self._validate_dimension(record.embedding)
            self._records_by_chunk_id[record.chunk_id] = _IndexedVectorRecord(
                record=record,
                norm=vector_norm(record.embedding),
            )
        self._matrix_records = ()
        self._normalized_matrix = None

    def search(
        self,
        query_embedding: EmbeddingVector,
        *,
        top_k: int = 10,
        filters: Mapping[str, object] | None = None,
    ) -> tuple[VectorSearchResult, ...]:
        self._validate_dimension(query_embedding)
        if top_k <= 0:
            return ()
        if not filters:
            return self._search_with_numpy(query_embedding, top_k=top_k)
        query_norm = vector_norm(query_embedding)
        scored = (
            VectorSearchResult(
                record=indexed.record,
                score=_cosine_similarity_with_norm(
                    query_embedding,
                    query_norm=query_norm,
                    indexed=indexed,
                ),
            )
            for indexed in self._records_by_chunk_id.values()
            if _metadata_matches(indexed.record.metadata, filters)
        )
        return tuple(nlargest(top_k, scored, key=lambda result: result.score))

    @property
    def size(self) -> int:
        return len(self._records_by_chunk_id)

    def _validate_dimension(self, embedding: EmbeddingVector) -> None:
        if len(embedding) != self._dimension:
            raise ValueError(
                f"embedding dimension mismatch: expected {self._dimension}, got {len(embedding)}"
            )

    def _search_with_numpy(
        self,
        query_embedding: EmbeddingVector,
        *,
        top_k: int,
    ) -> tuple[VectorSearchResult, ...]:
        if not self._records_by_chunk_id:
            return ()
        matrix = self._ensure_normalized_matrix()
        query = _normalized_query_vector(query_embedding)
        scores = matrix @ query
        result_count = min(top_k, int(scores.size))
        if result_count <= 0:
            return ()
        top_indices = _top_score_indices(scores, result_count)
        return tuple(
            VectorSearchResult(
                record=self._matrix_records[index].record,
                score=float(scores[index]),
            )
            for index in top_indices
        )

    def _ensure_normalized_matrix(self) -> npt.NDArray[np.float32]:
        if self._normalized_matrix is not None:
            return self._normalized_matrix

        records = tuple(self._records_by_chunk_id.values())
        matrix = np.asarray(
            [indexed.record.embedding for indexed in records],
            dtype=np.float32,
        )
        norms = np.asarray(
            [indexed.norm for indexed in records],
            dtype=np.float32,
        )
        safe_norms = np.where(norms == 0.0, 1.0, norms).astype(np.float32)
        normalized = matrix / safe_norms[:, np.newaxis]

        self._matrix_records = records
        self._normalized_matrix = cast(npt.NDArray[np.float32], normalized)
        return self._normalized_matrix


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


def _cosine_similarity_with_norm(
    query_embedding: EmbeddingVector,
    *,
    query_norm: float,
    indexed: _IndexedVectorRecord,
) -> float:
    if query_norm == 0 or indexed.norm == 0:
        return 0.0
    dot = sum(
        query_value * record_value
        for query_value, record_value in zip(
            query_embedding,
            indexed.record.embedding,
            strict=True,
        )
    )
    return dot / (query_norm * indexed.norm)


def _normalized_query_vector(query_embedding: EmbeddingVector) -> npt.NDArray[np.float32]:
    query = np.asarray(query_embedding, dtype=np.float32)
    norm = np.linalg.norm(query)
    if norm == 0.0:
        return query
    return cast(npt.NDArray[np.float32], query / norm)


def _top_score_indices(
    scores: npt.NDArray[np.float32],
    result_count: int,
) -> tuple[int, ...]:
    if result_count == int(scores.size):
        ordered = np.argsort(scores)[::-1]
    else:
        partition = np.argpartition(scores, -result_count)[-result_count:]
        ordered = partition[np.argsort(scores[partition])[::-1]]
    return tuple(int(index) for index in ordered[:result_count])
