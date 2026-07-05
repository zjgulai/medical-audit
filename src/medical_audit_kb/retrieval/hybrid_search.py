from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from medical_audit_kb.domain.constants import SourceCollection
from medical_audit_kb.indexing.bm25_index import BM25SearchResult, InMemoryBM25Index
from medical_audit_kb.indexing.embeddings import (
    EmbeddingProvider,
    EmbeddingProviderError,
    EmbeddingVector,
)
from medical_audit_kb.indexing.vector_index import InMemoryVectorIndex, VectorSearchResult
from medical_audit_kb.retrieval.filters import RetrievalFilters
from medical_audit_kb.retrieval.rerank import RerankCandidate, RerankProvider

DEFAULT_SOURCE_WEIGHTS: dict[str, float] = {
    SourceCollection.MEDICAL_INSURANCE_CATALOG.value: 1.25,
    SourceCollection.SUPERVISION_RULES_KNOWLEDGE.value: 1.35,
    SourceCollection.RISK_NEGATIVE_LIST.value: 1.1,
    SourceCollection.MEDICAL_INSURANCE_LAWS.value: 1.0,
}


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    chunk_id: UUID
    text: str
    metadata: dict[str, object]
    locator: dict[str, object]
    index_version_key: str
    source_package_version_key: str


@dataclass(frozen=True, slots=True)
class HybridSearchResult:
    chunk: RetrievedChunk
    score: float
    vector_score: float
    bm25_score: float
    rerank_score: float | None
    source_weight: float
    matched_by: tuple[str, ...]


class VectorIndex(Protocol):
    def search(
        self,
        query_embedding: EmbeddingVector,
        *,
        top_k: int = 10,
        filters: Mapping[str, object] | None = None,
    ) -> tuple[VectorSearchResult, ...]: ...


class BM25Index(Protocol):
    def search(
        self,
        query: str,
        *,
        top_k: int = 10,
        filters: Mapping[str, object] | None = None,
    ) -> tuple[BM25SearchResult, ...]: ...


@dataclass(slots=True)
class _MergedCandidate:
    chunk_id: UUID
    text: str
    metadata: dict[str, object]
    vector_score: float = 0.0
    bm25_score: float = 0.0

    @property
    def matched_by(self) -> tuple[str, ...]:
        matches: list[str] = []
        if self.vector_score > 0:
            matches.append("vector")
        if self.bm25_score > 0:
            matches.append("bm25")
        return tuple(matches)


class HybridSearchEngine:
    def __init__(
        self,
        *,
        embedding_provider: EmbeddingProvider,
        vector_index: VectorIndex | InMemoryVectorIndex,
        bm25_index: BM25Index | InMemoryBM25Index,
        rerank_provider: RerankProvider | None = None,
        source_collection_weights: dict[str, float] | None = None,
    ) -> None:
        self._embedding_provider = embedding_provider
        self._vector_index = vector_index
        self._bm25_index = bm25_index
        self._rerank_provider = rerank_provider
        self._source_collection_weights = source_collection_weights or DEFAULT_SOURCE_WEIGHTS

    def search(
        self,
        query: str,
        *,
        filters: RetrievalFilters | None = None,
        top_k: int = 10,
        fetch_k: int = 50,
    ) -> tuple[HybridSearchResult, ...]:
        active_filters = filters or RetrievalFilters()
        try:
            query_embedding = self._embedding_provider.embed_texts([query])[0]
            vector_results = self._vector_index.search(query_embedding, top_k=fetch_k)
        except EmbeddingProviderError:
            vector_results = ()
        bm25_results = self._bm25_index.search(query, top_k=fetch_k)

        candidates = _merge_candidates(vector_results, bm25_results)
        candidates = {
            chunk_id: candidate
            for chunk_id, candidate in candidates.items()
            if active_filters.matches(candidate.metadata)
        }
        if not candidates:
            return ()

        max_bm25_score = max(
            (candidate.bm25_score for candidate in candidates.values()),
            default=0.0,
        )
        scored = [
            _to_search_result(
                candidate,
                base_score=_base_score(candidate, max_bm25_score)
                * _source_weight(candidate.metadata, self._source_collection_weights),
                rerank_score=None,
                source_weight=_source_weight(candidate.metadata, self._source_collection_weights),
            )
            for candidate in candidates.values()
        ]

        if self._rerank_provider is not None:
            scored = _apply_rerank(query, scored, self._rerank_provider)

        return tuple(sorted(scored, key=lambda result: result.score, reverse=True)[:top_k])


def _merge_candidates(
    vector_results: tuple[VectorSearchResult, ...],
    bm25_results: tuple[BM25SearchResult, ...],
) -> dict[UUID, _MergedCandidate]:
    merged: dict[UUID, _MergedCandidate] = {}

    for vector_result in vector_results:
        chunk_id = vector_result.record.chunk_id
        merged[chunk_id] = _MergedCandidate(
            chunk_id=chunk_id,
            text=vector_result.record.text,
            metadata=dict(vector_result.record.metadata),
            vector_score=vector_result.score,
        )

    for bm25_result in bm25_results:
        chunk_id = bm25_result.document.chunk_id
        candidate = merged.get(chunk_id)
        if candidate is None:
            merged[chunk_id] = _MergedCandidate(
                chunk_id=chunk_id,
                text=bm25_result.document.text,
                metadata=dict(bm25_result.document.metadata),
                bm25_score=bm25_result.score,
            )
        else:
            candidate.bm25_score = bm25_result.score

    return merged


def _base_score(candidate: _MergedCandidate, max_bm25_score: float) -> float:
    normalized_bm25 = candidate.bm25_score / max_bm25_score if max_bm25_score > 0 else 0.0
    normalized_vector = max(candidate.vector_score, 0.0)
    if candidate.bm25_score > 0 and candidate.vector_score > 0:
        return (normalized_bm25 * 0.55) + (normalized_vector * 0.45)
    if candidate.bm25_score > 0:
        return normalized_bm25
    return normalized_vector


def _to_search_result(
    candidate: _MergedCandidate,
    *,
    base_score: float,
    rerank_score: float | None,
    source_weight: float,
) -> HybridSearchResult:
    chunk = RetrievedChunk(
        chunk_id=candidate.chunk_id,
        text=candidate.text,
        metadata=candidate.metadata,
        locator=_metadata_dict(candidate.metadata, "locator"),
        index_version_key=str(candidate.metadata.get("index_version_key", "")),
        source_package_version_key=str(candidate.metadata.get("source_package_version_key", "")),
    )
    return HybridSearchResult(
        chunk=chunk,
        score=base_score if rerank_score is None else rerank_score,
        vector_score=candidate.vector_score,
        bm25_score=candidate.bm25_score,
        rerank_score=rerank_score,
        source_weight=source_weight,
        matched_by=candidate.matched_by,
    )


def _apply_rerank(
    query: str,
    results: list[HybridSearchResult],
    rerank_provider: RerankProvider,
) -> list[HybridSearchResult]:
    scores = {
        score.chunk_id: score.score
        for score in rerank_provider.rerank(
            query,
            [
                RerankCandidate(
                    chunk_id=result.chunk.chunk_id,
                    text=result.chunk.text,
                    metadata=result.chunk.metadata,
                    base_score=result.score,
                )
                for result in results
            ],
        )
    }
    return [
        HybridSearchResult(
            chunk=result.chunk,
            score=scores.get(result.chunk.chunk_id, result.score),
            vector_score=result.vector_score,
            bm25_score=result.bm25_score,
            rerank_score=scores.get(result.chunk.chunk_id),
            source_weight=result.source_weight,
            matched_by=result.matched_by,
        )
        for result in results
    ]


def _source_weight(metadata: dict[str, object], weights: dict[str, float]) -> float:
    source_collection = str(metadata.get("source_collection", ""))
    return weights.get(source_collection, 1.0)


def _metadata_dict(metadata: dict[str, object], key: str) -> dict[str, object]:
    value = metadata.get(key)
    if isinstance(value, dict):
        return dict(value)
    return {}
