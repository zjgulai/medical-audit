from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from medical_audit_kb.evaluation.datasets import EvaluationCase, ExpectedEvidence
from medical_audit_kb.generation.citations import build_citations
from medical_audit_kb.preview.resolver import PreviewResolver
from medical_audit_kb.retrieval.filters import RetrievalFilters
from medical_audit_kb.retrieval.hybrid_search import HybridSearchResult


class SearchEngine(Protocol):
    def search(
        self,
        query: str,
        *,
        filters: RetrievalFilters | None = None,
        top_k: int = 10,
        fetch_k: int = 50,
    ) -> tuple[HybridSearchResult, ...]: ...


@dataclass(frozen=True, slots=True)
class EvaluationCaseResult:
    case_id: str
    question: str
    retrieved_chunk_ids: tuple[str, ...]
    expected_hit_count: int
    expected_count: int
    recall_hit: bool
    citation_hit: bool
    preview_success: bool
    missing_expected_sources: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EvaluationSummary:
    case_count: int
    recall_at_k: float
    citation_hit_rate: float
    preview_location_success_rate: float
    results: tuple[EvaluationCaseResult, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "case_count": self.case_count,
            "recall_at_k": self.recall_at_k,
            "citation_hit_rate": self.citation_hit_rate,
            "preview_location_success_rate": self.preview_location_success_rate,
            "results": [
                {
                    "case_id": result.case_id,
                    "question": result.question,
                    "retrieved_chunk_ids": result.retrieved_chunk_ids,
                    "expected_hit_count": result.expected_hit_count,
                    "expected_count": result.expected_count,
                    "recall_hit": result.recall_hit,
                    "citation_hit": result.citation_hit,
                    "preview_success": result.preview_success,
                    "missing_expected_sources": result.missing_expected_sources,
                }
                for result in self.results
            ],
        }


def evaluate_retrieval(
    cases: tuple[EvaluationCase, ...],
    search_engine: SearchEngine,
    *,
    top_k: int = 5,
    preview_resolver: PreviewResolver | None = None,
) -> EvaluationSummary:
    case_results = tuple(
        _evaluate_case(
            case,
            search_engine.search(case.question, filters=case.filters, top_k=top_k),
            preview_resolver=preview_resolver,
        )
        for case in cases
    )
    case_count = len(case_results)
    return EvaluationSummary(
        case_count=case_count,
        recall_at_k=_rate(result.recall_hit for result in case_results),
        citation_hit_rate=_rate(result.citation_hit for result in case_results),
        preview_location_success_rate=_rate(
            result.preview_success for result in case_results if result.citation_hit
        ),
        results=case_results,
    )


def _evaluate_case(
    case: EvaluationCase,
    results: tuple[HybridSearchResult, ...],
    *,
    preview_resolver: PreviewResolver | None,
) -> EvaluationCaseResult:
    matched_expected = tuple(
        expected
        for expected in case.expected_evidence
        if any(_matches_expected(result, expected) for result in results)
    )
    citations = build_citations(results)
    citation_hit = any(
        _matches_expected(result, expected)
        for expected in case.expected_evidence
        for result in results
        if any(citation.chunk_id == result.chunk.chunk_id for citation in citations)
    )
    preview_success = _preview_success(results, matched_expected, preview_resolver)
    return EvaluationCaseResult(
        case_id=case.case_id,
        question=case.question,
        retrieved_chunk_ids=tuple(str(result.chunk.chunk_id) for result in results),
        expected_hit_count=len(matched_expected),
        expected_count=len(case.expected_evidence),
        recall_hit=bool(matched_expected),
        citation_hit=citation_hit,
        preview_success=preview_success,
        missing_expected_sources=tuple(
            expected.source_path
            for expected in case.expected_evidence
            if expected not in matched_expected
        ),
    )


def _matches_expected(result: HybridSearchResult, expected: ExpectedEvidence) -> bool:
    metadata = result.chunk.metadata
    source_collection = metadata.get("source_collection")
    if source_collection != expected.source_collection.value:
        return False
    if _normalized_source_path(result) != _normalize_source_path(expected.source_path):
        return False
    if expected.article_or_rule is None:
        return True
    return _text_or_metadata_contains(result, expected.article_or_rule)


def _normalized_source_path(result: HybridSearchResult) -> str:
    locator_source_path = result.chunk.locator.get("source_path")
    if isinstance(locator_source_path, str):
        return _normalize_source_path(locator_source_path)
    metadata_source_path = result.chunk.metadata.get("source_path")
    if isinstance(metadata_source_path, str):
        return _normalize_source_path(metadata_source_path)
    return ""


def _text_or_metadata_contains(result: HybridSearchResult, value: str) -> bool:
    metadata_values = tuple(str(item) for item in result.chunk.metadata.values())
    locator_values = tuple(str(item) for item in result.chunk.locator.values())
    haystacks = (result.chunk.text, *metadata_values, *locator_values)
    return any(value in item for item in haystacks)


def _preview_success(
    results: tuple[HybridSearchResult, ...],
    matched_expected: tuple[ExpectedEvidence, ...],
    preview_resolver: PreviewResolver | None,
) -> bool:
    if not matched_expected or preview_resolver is None:
        return False
    for expected in matched_expected:
        for result in results:
            if not _matches_expected(result, expected):
                continue
            try:
                preview_resolver.resolve(result.chunk.locator, citation_text=result.chunk.text)
            except Exception:
                continue
            return True
    return False


def _normalize_source_path(source_path: str) -> str:
    return source_path.strip().replace("\\", "/")


def _rate(values: Iterable[object]) -> float:
    bool_values = tuple(bool(value) for value in values)
    if not bool_values:
        return 0.0
    return sum(1 for value in bool_values if value) / len(bool_values)
