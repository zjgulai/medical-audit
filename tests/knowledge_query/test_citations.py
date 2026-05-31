from collections.abc import Sequence
from uuid import uuid4

import pytest

from medical_audit_kb.domain.constants import SourceCollection
from medical_audit_kb.generation.answer_builder import (
    AnswerGenerationProvider,
    ConfidenceCue,
    NoCitedEvidenceError,
    build_citation_backed_answer,
)
from medical_audit_kb.generation.citations import EvidenceType, build_citations, group_citations
from medical_audit_kb.retrieval.hybrid_search import HybridSearchResult, RetrievedChunk


class SuccessfulProvider:
    provider = "fake"
    model_name = "cited-answer"
    provider_version = "v1"

    def generate_answer(self, question: str, citations: Sequence[object]) -> str:
        return f"{question} 的回答必须引用依据 [C1]。"


class FailingProvider:
    provider = "fake"
    model_name = "failing-answer"
    provider_version = "v1"

    def generate_answer(self, question: str, citations: Sequence[object]) -> str:
        raise RuntimeError("model unavailable")


class UncitedProvider:
    provider = "fake"
    model_name = "uncited-answer"
    provider_version = "v1"

    def generate_answer(self, question: str, citations: Sequence[object]) -> str:
        return "这是一个没有引用标记的回答。"


def test_build_citations_preserves_locator_and_versions() -> None:
    result = _result(
        SourceCollection.MEDICAL_INSURANCE_LAWS,
        text="第一条 医疗机构应当保留医保基金审核依据。",
        locator={"type": "law-article", "source_path": "全量法律/law.md", "line_start": 1},
        score=0.8,
    )

    citation = build_citations((result,))[0]

    assert citation.citation_id == "C1"
    assert citation.marker == "[C1]"
    assert citation.evidence_type == EvidenceType.LEGAL_BASIS
    assert citation.chunk_id == result.chunk.chunk_id
    assert citation.locator == result.chunk.locator
    assert citation.index_version_key == "index-v1"
    assert citation.source_package_version_key == "package-v1"
    assert "医保基金审核依据" in citation.snippet


def test_cross_collection_citations_are_grouped_by_basis_type() -> None:
    citations = build_citations(
        (
            _result(SourceCollection.MEDICAL_INSURANCE_LAWS),
            _result(SourceCollection.SUPERVISION_RULES_KNOWLEDGE),
            _result(SourceCollection.MEDICAL_INSURANCE_CATALOG),
            _result(SourceCollection.RISK_NEGATIVE_LIST),
        )
    )

    groups = group_citations(citations)

    assert [group.evidence_type for group in groups] == [
        EvidenceType.LEGAL_BASIS,
        EvidenceType.RULE_BASIS,
        EvidenceType.CATALOG_BASIS,
        EvidenceType.RISK_CASE_BASIS,
    ]
    assert [group.title for group in groups] == ["法规依据", "规则依据", "目录依据", "风险案例依据"]


def test_answer_uses_provider_output_when_it_contains_citation_marker() -> None:
    answer = build_citation_backed_answer(
        "医疗机构如何保留审核依据？",
        (_result(SourceCollection.MEDICAL_INSURANCE_LAWS, score=0.9),),
        generation_provider=SuccessfulProvider(),
    )

    assert answer.answer == "医疗机构如何保留审核依据？ 的回答必须引用依据 [C1]。"
    assert answer.fallback_used is False
    assert answer.generation_error is None
    assert answer.citations[0].marker == "[C1]"
    assert answer.basis_groups[0].items[0].locator["source_path"] == "source.md"
    assert answer.confidence == ConfidenceCue.MEDIUM


def test_answer_falls_back_to_citation_list_when_model_fails() -> None:
    answer = build_citation_backed_answer(
        "超量开药依据是什么？",
        (
            _result(
                SourceCollection.SUPERVISION_RULES_KNOWLEDGE,
                text="规则名称: 超量开药",
                score=0.7,
            ),
            _result(SourceCollection.MEDICAL_INSURANCE_LAWS, text="第一条 医保基金监管", score=0.6),
            _result(SourceCollection.MEDICAL_INSURANCE_CATALOG, text="医保目录编码", score=0.5),
        ),
        generation_provider=FailingProvider(),
    )

    assert answer.fallback_used is True
    assert answer.generation_error == "model unavailable"
    assert "未生成无引用结论" in answer.answer
    assert "[C1]" in answer.answer
    assert "[C2]" in answer.answer
    assert answer.confidence == ConfidenceCue.HIGH


def test_answer_falls_back_when_provider_returns_uncited_answer() -> None:
    answer = build_citation_backed_answer(
        "是否可以直接下结论？",
        (_result(SourceCollection.RISK_NEGATIVE_LIST, text="风险负面清单提示违规收费风险。"),),
        generation_provider=UncitedProvider(),
    )

    assert answer.fallback_used is True
    assert answer.generation_error == "generated answer does not contain citation markers"
    assert "风险负面清单提示违规收费风险" in answer.answer
    assert "[C1]" in answer.answer


def test_answer_without_citations_is_rejected() -> None:
    with pytest.raises(NoCitedEvidenceError, match="cannot build answer without cited"):
        build_citation_backed_answer("没有检索结果时不能回答", ())


def test_provider_protocol_is_structurally_satisfied() -> None:
    provider: AnswerGenerationProvider = SuccessfulProvider()

    assert provider.generate_answer("问题", []) == "问题 的回答必须引用依据 [C1]。"


def _result(
    source_collection: SourceCollection,
    *,
    text: str = "引用片段文本",
    locator: dict[str, object] | None = None,
    score: float = 0.5,
) -> HybridSearchResult:
    return HybridSearchResult(
        chunk=RetrievedChunk(
            chunk_id=uuid4(),
            text=text,
            metadata={"source_collection": source_collection.value},
            locator=locator or {"type": "line", "source_path": "source.md", "line_start": 1},
            index_version_key="index-v1",
            source_package_version_key="package-v1",
        ),
        score=score,
        vector_score=score,
        bm25_score=score,
        rerank_score=None,
        source_weight=1.0,
        matched_by=("vector", "bm25"),
    )
