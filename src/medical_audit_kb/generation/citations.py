from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from medical_audit_kb.domain.constants import SourceCollection
from medical_audit_kb.domain.source_collection_registry import source_collection_definition
from medical_audit_kb.retrieval.hybrid_search import HybridSearchResult

DEFAULT_SNIPPET_CHARS = 240
_CITATION_MARKER_RE = re.compile(
    r"(?<![A-Za-z0-9])[\[【(（]?\s*(C\d+)\s*[\]】)）]?(?![A-Za-z0-9])",
    re.IGNORECASE,
)


def citation_labels_in_text(text: str) -> set[str]:
    """Extract citation labels while rejecting labels embedded in alphanumeric text."""
    return {match.group(1).upper() for match in _CITATION_MARKER_RE.finditer(text)}


class EvidenceType(StrEnum):
    LEGAL_BASIS = "legal_basis"
    RULE_BASIS = "rule_basis"
    CATALOG_BASIS = "catalog_basis"
    RISK_CASE_BASIS = "risk_case_basis"
    POLICY_BASIS = "policy_basis"
    MANAGEMENT_BASIS = "management_basis"
    OTHER_PUBLIC_BASIS = "other_public_basis"
    PERSONAL_MATERIAL_BASIS = "personal_material_basis"


EVIDENCE_TITLES: dict[EvidenceType, str] = {
    EvidenceType.LEGAL_BASIS: "法规依据",
    EvidenceType.RULE_BASIS: "规则依据",
    EvidenceType.CATALOG_BASIS: "目录依据",
    EvidenceType.RISK_CASE_BASIS: "风险案例依据",
    EvidenceType.POLICY_BASIS: "政策依据",
    EvidenceType.MANAGEMENT_BASIS: "管理依据",
    EvidenceType.OTHER_PUBLIC_BASIS: "其他公开依据",
    EvidenceType.PERSONAL_MATERIAL_BASIS: "个人材料依据",
}

EVIDENCE_ORDER: tuple[EvidenceType, ...] = (
    EvidenceType.LEGAL_BASIS,
    EvidenceType.RULE_BASIS,
    EvidenceType.CATALOG_BASIS,
    EvidenceType.RISK_CASE_BASIS,
    EvidenceType.POLICY_BASIS,
    EvidenceType.MANAGEMENT_BASIS,
    EvidenceType.OTHER_PUBLIC_BASIS,
    EvidenceType.PERSONAL_MATERIAL_BASIS,
)

EVIDENCE_TYPE_BY_GROUP: dict[str, EvidenceType] = {
    "legal": EvidenceType.LEGAL_BASIS,
    "rule": EvidenceType.RULE_BASIS,
    "catalog": EvidenceType.CATALOG_BASIS,
    "risk": EvidenceType.RISK_CASE_BASIS,
    "policy": EvidenceType.POLICY_BASIS,
    "management": EvidenceType.MANAGEMENT_BASIS,
    "other": EvidenceType.OTHER_PUBLIC_BASIS,
    "personal": EvidenceType.PERSONAL_MATERIAL_BASIS,
}


@dataclass(frozen=True, slots=True)
class Citation:
    citation_id: str
    evidence_type: EvidenceType
    source_collection: SourceCollection
    chunk_id: UUID
    snippet: str
    locator: dict[str, object]
    index_version_key: str
    source_package_version_key: str
    score: float
    metadata: dict[str, object]

    @property
    def marker(self) -> str:
        return f"[{self.citation_id}]"


@dataclass(frozen=True, slots=True)
class CitationGroup:
    evidence_type: EvidenceType
    title: str
    citations: tuple[Citation, ...]


def build_citations(
    results: tuple[HybridSearchResult, ...],
    *,
    max_snippet_chars: int = DEFAULT_SNIPPET_CHARS,
    focus_terms: Sequence[str] = (),
) -> tuple[Citation, ...]:
    citations: list[Citation] = []
    for index, result in enumerate(results, start=1):
        source_collection = _source_collection_from_metadata(result.chunk.metadata)
        citations.append(
            Citation(
                citation_id=f"C{index}",
                evidence_type=evidence_type_for_source_collection(source_collection),
                source_collection=source_collection,
                chunk_id=result.chunk.chunk_id,
                snippet=_snippet(
                    result.chunk.text,
                    max_snippet_chars=max_snippet_chars,
                    focus_terms=focus_terms,
                ),
                locator=result.chunk.locator,
                index_version_key=result.chunk.index_version_key,
                source_package_version_key=result.chunk.source_package_version_key,
                score=result.score,
                metadata=result.chunk.metadata,
            )
        )
    return tuple(citations)


def group_citations(citations: tuple[Citation, ...]) -> tuple[CitationGroup, ...]:
    groups: list[CitationGroup] = []
    for evidence_type in EVIDENCE_ORDER:
        grouped = tuple(
            citation for citation in citations if citation.evidence_type == evidence_type
        )
        if not grouped:
            continue
        groups.append(
            CitationGroup(
                evidence_type=evidence_type,
                title=EVIDENCE_TITLES[evidence_type],
                citations=grouped,
            )
        )
    return tuple(groups)


def evidence_type_for_source_collection(source_collection: SourceCollection) -> EvidenceType:
    definition = source_collection_definition(source_collection)
    return EVIDENCE_TYPE_BY_GROUP[definition.evidence_group]


def _source_collection_from_metadata(metadata: dict[str, object]) -> SourceCollection:
    value = metadata.get("source_collection")
    if not isinstance(value, str):
        raise ValueError("citation metadata must contain source_collection")
    return SourceCollection(value)


def _snippet(
    text: str,
    *,
    max_snippet_chars: int,
    focus_terms: Sequence[str] = (),
) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    if len(normalized) <= max_snippet_chars:
        return normalized
    focus_index = _focus_index(normalized, focus_terms)
    if focus_index is not None:
        return _focused_snippet(normalized, focus_index, max_snippet_chars=max_snippet_chars)
    return f"{normalized[: max_snippet_chars - 1].rstrip()}…"


def _focus_index(text: str, focus_terms: Sequence[str]) -> int | None:
    for term in focus_terms:
        if not term:
            continue
        index = text.find(term)
        if index >= 0:
            return index
    return None


def _focused_snippet(text: str, focus_index: int, *, max_snippet_chars: int) -> str:
    context_before = min(24, max_snippet_chars // 4)
    start = max(0, focus_index - context_before)
    end = min(len(text), start + max_snippet_chars)
    if end - start < max_snippet_chars:
        start = max(0, end - max_snippet_chars)
    snippet = text[start:end].strip()
    if start > 0:
        snippet = f"…{snippet.lstrip()}"
    if end < len(text):
        snippet = f"{snippet.rstrip()}…"
    return snippet
