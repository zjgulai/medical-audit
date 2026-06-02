from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from medical_audit_kb.indexing.embeddings import tokenize_text


@dataclass(frozen=True, slots=True)
class RerankCandidate:
    chunk_id: UUID
    text: str
    metadata: dict[str, object]
    base_score: float


@dataclass(frozen=True, slots=True)
class RerankScore:
    chunk_id: UUID
    score: float


class RerankProvider(Protocol):
    @property
    def provider(self) -> str: ...

    @property
    def model_name(self) -> str: ...

    @property
    def provider_version(self) -> str: ...

    def rerank(
        self,
        query: str,
        candidates: Sequence[RerankCandidate],
    ) -> tuple[RerankScore, ...]: ...


@dataclass(frozen=True, slots=True)
class FakeRerankProvider:
    provider: str = "fake"
    model_name: str = "token-overlap-reranker"
    provider_version: str = "v1"

    def rerank(self, query: str, candidates: Sequence[RerankCandidate]) -> tuple[RerankScore, ...]:
        query_tokens = set(tokenize_text(query))
        scores: list[RerankScore] = []
        for candidate in candidates:
            candidate_tokens = set(tokenize_text(candidate.text))
            overlap = len(query_tokens.intersection(candidate_tokens))
            denominator = max(len(query_tokens), 1)
            overlap_score = overlap / denominator
            scores.append(
                RerankScore(
                    chunk_id=candidate.chunk_id,
                    score=(candidate.base_score * 0.7) + (overlap_score * 0.3),
                )
            )
        return tuple(sorted(scores, key=lambda item: item.score, reverse=True))
