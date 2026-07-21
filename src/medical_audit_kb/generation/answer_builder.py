from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, Protocol, cast
from uuid import UUID

from medical_audit_kb.domain.constants import SourceCollection
from medical_audit_kb.generation.citations import (
    Citation,
    CitationGroup,
    EvidenceType,
    build_citations,
    group_citations,
)
from medical_audit_kb.retrieval.hybrid_search import HybridSearchResult

MAX_FALLBACK_CITATIONS = 3
ANSWER_SNIPPET_CHARS = 96

QUESTION_STOP_TERMS = frozenset(
    {
        "请根据资料回答",
        "根据资料",
        "请",
        "根据",
        "资料",
        "回答",
        "是否",
        "什么",
        "如何",
        "定义",
        "对应",
        "需要",
        "必须",
        "哪条",
        "哪个",
        "中的",
        "中",
        "是",
        "的",
        "了",
    }
)


class ConfidenceCue(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class GenerationStatus(StrEnum):
    NOT_REQUESTED = "not_requested"
    GENERATED = "generated"
    RETRIEVAL_FALLBACK = "retrieval_fallback"


GenerationFailureCode = Literal[
    "provider_configuration",
    "provider_transport",
    "provider_http_status",
    "provider_response_invalid",
    "citation_marker_missing",
    "provider_exception",
]
GENERATION_FAILURE_CODES = frozenset(
    {
        "provider_configuration",
        "provider_transport",
        "provider_http_status",
        "provider_response_invalid",
        "citation_marker_missing",
        "provider_exception",
    }
)
GenerationFailureReason = Literal[
    "response_body_invalid_json",
    "response_root_not_object",
    "response_choices_missing",
    "response_choice_not_object",
    "response_message_missing",
    "response_content_empty",
    "deepseek_content_invalid_json",
    "deepseek_json_root_not_object",
    "deepseek_answer_empty",
    "deepseek_citation_ids_invalid",
    "deepseek_citation_ids_unavailable",
    "deepseek_citation_markers_mismatch",
]
GENERATION_FAILURE_REASONS = frozenset(
    {
        "response_body_invalid_json",
        "response_root_not_object",
        "response_choices_missing",
        "response_choice_not_object",
        "response_message_missing",
        "response_content_empty",
        "deepseek_content_invalid_json",
        "deepseek_json_root_not_object",
        "deepseek_answer_empty",
        "deepseek_citation_ids_invalid",
        "deepseek_citation_ids_unavailable",
        "deepseek_citation_markers_mismatch",
    }
)


class AnswerGenerationError(Exception):
    pass


class NoCitedEvidenceError(ValueError):
    pass


class AnswerGenerationProvider(Protocol):
    @property
    def provider(self) -> str: ...

    @property
    def model_name(self) -> str: ...

    @property
    def provider_version(self) -> str: ...

    def generate_answer(self, question: str, citations: Sequence[Citation]) -> str: ...


@dataclass(frozen=True, slots=True)
class AnswerBasisItem:
    citation_id: str
    chunk_id: UUID
    source_collection: SourceCollection
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
    generation_status: GenerationStatus
    generation_failure_code: GenerationFailureCode | None = None
    generation_failure_reason: GenerationFailureReason | None = None
    generation_http_status: int | None = None
    generation_error: str | None = None


def build_citation_backed_answer(
    question: str,
    results: tuple[HybridSearchResult, ...],
    *,
    generation_provider: AnswerGenerationProvider | None = None,
) -> CitationBackedAnswer:
    focus_terms = _question_focus_terms(question)
    focused_results = _select_focused_results(results, focus_terms)
    citations = build_citations(
        focused_results,
        max_snippet_chars=ANSWER_SNIPPET_CHARS,
        focus_terms=focus_terms,
    )
    if not citations:
        raise NoCitedEvidenceError("cannot build answer without cited retrieval results")

    citation_groups = group_citations(citations)
    basis_groups = _basis_groups(citation_groups)
    fallback_answer = _fallback_answer(question, citation_groups)
    generation_error: str | None = None
    generation_failure_code: GenerationFailureCode | None = None
    generation_failure_reason: GenerationFailureReason | None = None
    generation_http_status: int | None = None
    fallback_used = generation_provider is None
    generation_status = (
        GenerationStatus.NOT_REQUESTED
        if generation_provider is None
        else GenerationStatus.RETRIEVAL_FALLBACK
    )

    answer = fallback_answer
    if generation_provider is not None:
        try:
            candidate_answer = generation_provider.generate_answer(question, citations)
            if not _contains_citation_marker(candidate_answer, citations):
                raise AnswerGenerationError("generated answer does not contain citation markers")
            answer = candidate_answer
            fallback_used = False
            generation_status = GenerationStatus.GENERATED
        except Exception as exc:
            generation_error = str(exc)
            generation_failure_code = _generation_failure_code(exc)
            generation_failure_reason = _generation_failure_reason(exc)
            generation_http_status = _generation_http_status(exc)
            answer = fallback_answer
            fallback_used = True
            generation_status = GenerationStatus.RETRIEVAL_FALLBACK

    return CitationBackedAnswer(
        question=question,
        answer=answer,
        basis_groups=basis_groups,
        citations=citations,
        confidence=_confidence(citations),
        fallback_used=fallback_used,
        generation_status=generation_status,
        generation_failure_code=generation_failure_code,
        generation_failure_reason=generation_failure_reason,
        generation_http_status=generation_http_status,
        generation_error=generation_error,
    )


def _generation_failure_code(exc: Exception) -> GenerationFailureCode:
    if isinstance(exc, AnswerGenerationError):
        return "citation_marker_missing"
    code = getattr(exc, "code", None)
    if isinstance(code, str) and code in GENERATION_FAILURE_CODES:
        return cast(GenerationFailureCode, code)
    return "provider_exception"


def _generation_http_status(exc: Exception) -> int | None:
    value = getattr(exc, "http_status", None)
    return value if isinstance(value, int) and 400 <= value <= 599 else None


def _generation_failure_reason(exc: Exception) -> GenerationFailureReason | None:
    reason = getattr(exc, "reason", None)
    if isinstance(reason, str) and reason in GENERATION_FAILURE_REASONS:
        return cast(GenerationFailureReason, reason)
    return None


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
                        source_collection=citation.source_collection,
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


_CITATION_MARKER_RE = re.compile(
    r"(?<![A-Za-z0-9])[\[【(（]?\s*(C\d+)\s*[\]】)）]?(?![A-Za-z0-9])",
    re.IGNORECASE,
)


def _contains_citation_marker(answer: str, citations: tuple[Citation, ...]) -> bool:
    present = _citation_labels_in_text(answer)
    return any(_marker_label(citation.marker) in present for citation in citations)


def _citation_labels_in_text(text: str) -> set[str]:
    """提取答案中出现的 C<编号> 引用标记，兼容 [C1] 【C1】 (C1) （C1） 及裸 C1 变体。

    要求 C<编号> 不嵌入更大的字母数字串（避免把 VITC1 之类误判为引用）。
    仅放宽标记的“格式”识别，不放宽“必须带引用”的语义。
    """
    return {match.group(1).upper() for match in _CITATION_MARKER_RE.finditer(text)}


def _marker_label(marker: str) -> str:
    match = re.search(r"C\d+", marker, flags=re.IGNORECASE)
    return match.group(0).upper() if match else marker.upper()


def _select_focused_results(
    results: tuple[HybridSearchResult, ...],
    focus_terms: tuple[str, ...],
) -> tuple[HybridSearchResult, ...]:
    if not focus_terms:
        return results[:MAX_FALLBACK_CITATIONS]

    scored_results = tuple(
        (score, result) for result in results if (score := _focus_score(result, focus_terms)) > 0
    )
    if not scored_results:
        return results[:MAX_FALLBACK_CITATIONS]

    best_score = max(score for score, _ in scored_results)
    minimum_score = max(1, int(best_score * 0.6))
    selected = tuple(result for score, result in scored_results if score >= minimum_score)
    return selected[:MAX_FALLBACK_CITATIONS]


def _focus_score(result: HybridSearchResult, focus_terms: tuple[str, ...]) -> int:
    metadata_values = " ".join(str(value) for value in result.chunk.metadata.values())
    locator_values = " ".join(str(value) for value in result.chunk.locator.values())
    haystack = f"{result.chunk.text}\n{metadata_values}\n{locator_values}"
    return sum(len(term) for term in focus_terms if term in haystack)


def _question_focus_terms(question: str) -> tuple[str, ...]:
    terms: list[str] = []
    alpha_numeric_terms = re.findall(r"[A-Za-z0-9]+(?:[._/-][A-Za-z0-9]+)*", question)
    terms.extend(term for term in alpha_numeric_terms if _is_domain_code(term))
    for segment in re.findall(r"[\u4e00-\u9fff]+", question):
        normalized = segment
        for stop_term in sorted(QUESTION_STOP_TERMS, key=len, reverse=True):
            normalized = normalized.replace(stop_term, " ")
        for part in re.findall(r"[\u4e00-\u9fff]+", normalized):
            terms.extend(_chinese_ngrams(part))
    terms.extend(term for term in alpha_numeric_terms if not _is_domain_code(term))
    return _unique_terms(terms)


def _is_domain_code(term: str) -> bool:
    if term.upper().startswith("ICD"):
        return False
    return term.isdigit() or bool(re.fullmatch(r"[A-Za-z]+\d+(?:\.\d+)?", term))


def _chinese_ngrams(text: str) -> tuple[str, ...]:
    max_length = min(8, len(text))
    ngrams: list[str] = []
    for length in range(max_length, 1, -1):
        ngrams.extend(text[start : start + length] for start in range(len(text) - length + 1))
    return tuple(ngrams)


def _unique_terms(terms: Sequence[str]) -> tuple[str, ...]:
    unique_terms: list[str] = []
    seen: set[str] = set()
    for term in terms:
        normalized = term.strip()
        if len(normalized) < 2 or normalized in QUESTION_STOP_TERMS or normalized in seen:
            continue
        unique_terms.append(normalized)
        seen.add(normalized)
    return tuple(unique_terms)


def _confidence(citations: tuple[Citation, ...]) -> ConfidenceCue:
    best_score = max((citation.score for citation in citations), default=0.0)
    if len(citations) >= 3 and best_score >= 0.6:
        return ConfidenceCue.HIGH
    if len(citations) >= 2 or best_score >= 0.35:
        return ConfidenceCue.MEDIUM
    return ConfidenceCue.LOW
