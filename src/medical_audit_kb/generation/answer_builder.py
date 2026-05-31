from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from medical_audit_kb.generation.citations import (
    Citation,
    CitationGroup,
    EvidenceType,
    build_citations,
    group_citations,
)
from medical_audit_kb.retrieval.hybrid_search import HybridSearchResult


class ConfidenceCue(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class AnswerGenerationError(Exception):
    pass


class NoCitedEvidenceError(ValueError):
    pass


class AnswerGenerationProvider(Protocol):
    provider: str
    model_name: str
    provider_version: str

    def generate_answer(self, question: str, citations: Sequence[Citation]) -> str: ...


@dataclass(frozen=True, slots=True)
class AnswerBasisItem:
    citation_id: str
    chunk_id: UUID
    snippet: str
    locator: dict[str, object]
    index_version_key: str
    source_package_version_key: str


@dataclass(frozen=True, slots=True)
class AnswerBasisGroup:
    evidence_type: EvidenceType
    title: str
    items: tuple[AnswerBasisItem, ...]


@dataclass(frozen=True, slots=True)
class CitationBackedAnswer:
    question: str
    answer: str
    basis_groups: tuple[AnswerBasisGroup, ...]
    citations: tuple[Citation, ...]
    confidence: ConfidenceCue
    fallback_used: bool
    generation_error: str | None = None


def build_citation_backed_answer(
    question: str,
    results: tuple[HybridSearchResult, ...],
    *,
    generation_provider: AnswerGenerationProvider | None = None,
) -> CitationBackedAnswer:
    citations = build_citations(results)
    if not citations:
        raise NoCitedEvidenceError("cannot build answer without cited retrieval results")

    citation_groups = group_citations(citations)
    basis_groups = _basis_groups(citation_groups)
    fallback_answer = _fallback_answer(question, citation_groups)
    generation_error: str | None = None
    fallback_used = generation_provider is None

    answer = fallback_answer
    if generation_provider is not None:
        try:
            candidate_answer = generation_provider.generate_answer(question, citations)
            if not _contains_citation_marker(candidate_answer, citations):
                raise AnswerGenerationError("generated answer does not contain citation markers")
            answer = candidate_answer
            fallback_used = False
        except Exception as exc:
            generation_error = str(exc)
            answer = fallback_answer
            fallback_used = True

    return CitationBackedAnswer(
        question=question,
        answer=answer,
        basis_groups=basis_groups,
        citations=citations,
        confidence=_confidence(citations),
        fallback_used=fallback_used,
        generation_error=generation_error,
    )


def _basis_groups(citation_groups: tuple[CitationGroup, ...]) -> tuple[AnswerBasisGroup, ...]:
    groups: list[AnswerBasisGroup] = []
    for citation_group in citation_groups:
        groups.append(
            AnswerBasisGroup(
                evidence_type=citation_group.evidence_type,
                title=citation_group.title,
                items=tuple(
                    AnswerBasisItem(
                        citation_id=citation.citation_id,
                        chunk_id=citation.chunk_id,
                        snippet=citation.snippet,
                        locator=citation.locator,
                        index_version_key=citation.index_version_key,
                        source_package_version_key=citation.source_package_version_key,
                    )
                    for citation in citation_group.citations
                ),
            )
        )
    return tuple(groups)


def _fallback_answer(question: str, citation_groups: tuple[CitationGroup, ...]) -> str:
    lines = [
        f"问题：{question}",
        "当前回答由检索依据直接组成，未生成无引用结论。",
    ]
    for group in citation_groups:
        lines.append(f"{group.title}：")
        for citation in group.citations:
            lines.append(f"- {citation.snippet} {citation.marker}")
    return "\n".join(lines)


def _contains_citation_marker(answer: str, citations: tuple[Citation, ...]) -> bool:
    return any(citation.marker in answer for citation in citations)


def _confidence(citations: tuple[Citation, ...]) -> ConfidenceCue:
    best_score = max((citation.score for citation in citations), default=0.0)
    if len(citations) >= 3 and best_score >= 0.6:
        return ConfidenceCue.HIGH
    if len(citations) >= 2 or best_score >= 0.35:
        return ConfidenceCue.MEDIUM
    return ConfidenceCue.LOW
