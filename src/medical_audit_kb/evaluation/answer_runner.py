from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from medical_audit_kb.evaluation.answer_datasets import (
    AnswerEvaluationCase,
    ExpectedAnswerBehavior,
)
from medical_audit_kb.evaluation.runner import SearchEngine
from medical_audit_kb.generation.answer_builder import (
    AnswerGenerationProvider,
    NoCitedEvidenceError,
    build_citation_backed_answer,
)
from medical_audit_kb.retrieval.hybrid_search import HybridSearchResult

REFUSAL_ANSWER = "依据不足，当前知识库未检索到足够可引用依据，拒绝生成结论。"


@dataclass(frozen=True, slots=True)
class AnswerEvaluationCaseResult:
    case_id: str
    question: str
    expected_behavior: str
    answer: str
    generated_refusal: bool
    citation_count: int
    citation_markers_present: bool
    answer_terms_hit: bool
    citation_terms_hit: bool
    unsupported_claim_free: bool
    fallback_used: bool
    generation_error: str | None
    passed: bool
    failure_reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AnswerEvaluationSummary:
    case_count: int
    pass_rate: float
    citation_marker_rate: float
    answer_term_coverage_rate: float
    citation_term_coverage_rate: float
    refusal_accuracy_rate: float
    unsupported_claim_free_rate: float
    generation_success_rate: float
    fallback_rate: float
    results: tuple[AnswerEvaluationCaseResult, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "case_count": self.case_count,
            "pass_rate": self.pass_rate,
            "citation_marker_rate": self.citation_marker_rate,
            "answer_term_coverage_rate": self.answer_term_coverage_rate,
            "citation_term_coverage_rate": self.citation_term_coverage_rate,
            "refusal_accuracy_rate": self.refusal_accuracy_rate,
            "unsupported_claim_free_rate": self.unsupported_claim_free_rate,
            "generation_success_rate": self.generation_success_rate,
            "fallback_rate": self.fallback_rate,
            "results": [
                {
                    "case_id": result.case_id,
                    "question": result.question,
                    "expected_behavior": result.expected_behavior,
                    "answer": result.answer,
                    "generated_refusal": result.generated_refusal,
                    "citation_count": result.citation_count,
                    "citation_markers_present": result.citation_markers_present,
                    "answer_terms_hit": result.answer_terms_hit,
                    "citation_terms_hit": result.citation_terms_hit,
                    "unsupported_claim_free": result.unsupported_claim_free,
                    "fallback_used": result.fallback_used,
                    "generation_error": result.generation_error,
                    "passed": result.passed,
                    "failure_reasons": result.failure_reasons,
                }
                for result in self.results
            ],
        }


def evaluate_answers(
    cases: tuple[AnswerEvaluationCase, ...],
    search_engine: SearchEngine,
    *,
    top_k: int = 5,
    generation_provider: AnswerGenerationProvider | None = None,
    require_generation_success: bool = False,
) -> AnswerEvaluationSummary:
    case_results = tuple(
        _evaluate_answer_case(
            case,
            search_engine.search(case.question, filters=case.filters, top_k=top_k),
            generation_provider=generation_provider,
            require_generation_success=require_generation_success,
        )
        for case in cases
    )
    answer_results = tuple(
        result
        for result in case_results
        if result.expected_behavior == ExpectedAnswerBehavior.ANSWER.value
    )
    refusal_results = tuple(
        result
        for result in case_results
        if result.expected_behavior == ExpectedAnswerBehavior.REFUSE.value
    )
    return AnswerEvaluationSummary(
        case_count=len(case_results),
        pass_rate=_rate(result.passed for result in case_results),
        citation_marker_rate=_rate(result.citation_markers_present for result in answer_results),
        answer_term_coverage_rate=_rate(result.answer_terms_hit for result in answer_results),
        citation_term_coverage_rate=_rate(result.citation_terms_hit for result in answer_results),
        refusal_accuracy_rate=_rate(result.generated_refusal for result in refusal_results),
        unsupported_claim_free_rate=_rate(result.unsupported_claim_free for result in case_results),
        generation_success_rate=_rate(
            (
                not result.fallback_used
                and result.generation_error is None
                and not result.generated_refusal
            )
            for result in answer_results
        ),
        fallback_rate=_rate(result.fallback_used for result in answer_results),
        results=case_results,
    )


def _evaluate_answer_case(
    case: AnswerEvaluationCase,
    results: tuple[HybridSearchResult, ...],
    *,
    generation_provider: AnswerGenerationProvider | None = None,
    require_generation_success: bool = False,
) -> AnswerEvaluationCaseResult:
    evidence_terms_hit = _terms_present_in_results(case.required_evidence_terms, results)
    should_refuse = bool(case.required_evidence_terms) and not evidence_terms_hit
    generated_refusal = should_refuse
    answer = REFUSAL_ANSWER
    citation_count = 0
    citation_markers_present = False
    fallback_used = False
    generation_error: str | None = None

    if not should_refuse:
        try:
            citation_backed_answer = build_citation_backed_answer(
                case.question,
                results,
                generation_provider=generation_provider,
            )
            answer = citation_backed_answer.answer
            citation_count = len(citation_backed_answer.citations)
            citation_markers_present = any(
                citation.marker in answer for citation in citation_backed_answer.citations
            )
            fallback_used = citation_backed_answer.fallback_used
            generation_error = citation_backed_answer.generation_error
        except NoCitedEvidenceError:
            generated_refusal = True

    answer_terms_hit = _terms_present(case.required_answer_terms, answer)
    citation_terms_hit = _terms_present_in_results(case.required_citation_terms, results)
    unsupported_claim_free = not case.forbidden_answer_terms or not _terms_present(
        case.forbidden_answer_terms,
        answer,
    )
    failure_reasons = _failure_reasons(
        case,
        generated_refusal=generated_refusal,
        citation_markers_present=citation_markers_present,
        answer_terms_hit=answer_terms_hit,
        citation_terms_hit=citation_terms_hit,
        unsupported_claim_free=unsupported_claim_free,
        fallback_used=fallback_used,
        generation_error=generation_error,
        require_generation_success=require_generation_success,
    )
    return AnswerEvaluationCaseResult(
        case_id=case.case_id,
        question=case.question,
        expected_behavior=case.expected_behavior.value,
        answer=answer,
        generated_refusal=generated_refusal,
        citation_count=citation_count,
        citation_markers_present=citation_markers_present,
        answer_terms_hit=answer_terms_hit,
        citation_terms_hit=citation_terms_hit,
        unsupported_claim_free=unsupported_claim_free,
        fallback_used=fallback_used,
        generation_error=generation_error,
        passed=not failure_reasons,
        failure_reasons=failure_reasons,
    )


def _failure_reasons(
    case: AnswerEvaluationCase,
    *,
    generated_refusal: bool,
    citation_markers_present: bool,
    answer_terms_hit: bool,
    citation_terms_hit: bool,
    unsupported_claim_free: bool,
    fallback_used: bool,
    generation_error: str | None,
    require_generation_success: bool,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if case.expected_behavior == ExpectedAnswerBehavior.ANSWER:
        if generated_refusal:
            reasons.append("unexpected_refusal")
        if not citation_markers_present:
            reasons.append("missing_citation_marker")
        if not answer_terms_hit:
            reasons.append("missing_required_answer_terms")
        if not citation_terms_hit:
            reasons.append("missing_required_citation_terms")
        if require_generation_success and generation_error is not None:
            reasons.append("generation_provider_failed")
        elif require_generation_success and fallback_used:
            reasons.append("generation_fallback_used")
    else:
        if not generated_refusal:
            reasons.append("expected_refusal_not_triggered")
    if not unsupported_claim_free:
        reasons.append("forbidden_answer_terms_present")
    return tuple(reasons)


def _terms_present_in_results(
    terms: tuple[str, ...],
    results: tuple[HybridSearchResult, ...],
) -> bool:
    if not terms:
        return True
    parts: list[str] = []
    for result in results:
        parts.append(result.chunk.text)
        parts.append(" ".join(str(value) for value in result.chunk.metadata.values()))
        parts.append(" ".join(str(value) for value in result.chunk.locator.values()))
    haystack = "\n".join(parts)
    return _terms_present(terms, haystack)


def _terms_present(terms: tuple[str, ...], text: str) -> bool:
    return all(term in text for term in terms)


def _rate(values: Iterable[object]) -> float:
    bool_values = tuple(bool(value) for value in values)
    if not bool_values:
        return 0.0
    return sum(1 for value in bool_values if value) / len(bool_values)
