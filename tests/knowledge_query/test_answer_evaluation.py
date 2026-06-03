import json
from collections.abc import Sequence
from pathlib import Path
from uuid import uuid4

from medical_audit_kb.domain.constants import SourceCollection
from medical_audit_kb.evaluation.answer_datasets import (
    ExpectedAnswerBehavior,
    load_answer_evaluation_cases,
)
from medical_audit_kb.evaluation.answer_runner import evaluate_answers
from medical_audit_kb.generation.citations import Citation
from medical_audit_kb.retrieval.filters import RetrievalFilters
from medical_audit_kb.retrieval.hybrid_search import HybridSearchResult, RetrievedChunk


def test_load_answer_evaluation_cases_keeps_filters_and_terms(tmp_path: Path) -> None:
    cases_path = tmp_path / "answer-cases.yaml"
    cases_path.write_text(
        """
cases:
  - case_id: answer-case-001
    question: 医疗机构需要保留什么？
    expected_behavior: answer
    required_evidence_terms: [第一条]
    required_answer_terms: [审核依据]
    required_citation_terms: [医疗机构]
    forbidden_answer_terms: [自行推断]
    tags: [answerable]
    filters:
      source_collections: [medical-insurance-laws]
""".strip(),
        encoding="utf-8",
    )

    cases = load_answer_evaluation_cases(cases_path)

    assert len(cases) == 1
    assert cases[0].expected_behavior == ExpectedAnswerBehavior.ANSWER
    assert cases[0].required_evidence_terms == ("第一条",)
    assert cases[0].filters.source_collections == (SourceCollection.MEDICAL_INSURANCE_LAWS,)


def test_evaluate_answers_scores_answer_and_refusal_cases(tmp_path: Path) -> None:
    cases = load_answer_evaluation_cases(
        _write_dataset(
            tmp_path / "answer-cases.json",
            [
                {
                    "case_id": "answer-case-001",
                    "question": "医疗机构需要保留什么？",
                    "expected_behavior": "answer",
                    "required_evidence_terms": ["第一条"],
                    "required_answer_terms": ["审核依据"],
                    "required_citation_terms": ["医疗机构"],
                    "forbidden_answer_terms": ["自行推断"],
                },
                {
                    "case_id": "refusal-case-001",
                    "question": "请给出资料中不存在的处罚金额。",
                    "expected_behavior": "refuse",
                    "required_evidence_terms": ["不存在的处罚金额"],
                    "forbidden_answer_terms": ["处罚金额为"],
                },
            ],
        )
    )
    engine = StaticSearchEngine(
        (
            _result(
                SourceCollection.MEDICAL_INSURANCE_LAWS,
                text="第一条 医疗机构应当保留医保基金审核依据。",
            ),
        )
    )

    summary = evaluate_answers(cases, engine, top_k=3)

    assert summary.case_count == 2
    assert summary.pass_rate == 1.0
    assert summary.citation_marker_rate == 1.0
    assert summary.answer_term_coverage_rate == 1.0
    assert summary.refusal_accuracy_rate == 1.0
    assert summary.generation_success_rate == 0.0
    assert summary.fallback_rate == 1.0
    assert summary.results[1].generated_refusal
    assert summary.to_dict()["case_count"] == 2


def test_evaluate_answers_uses_generation_provider_when_available(tmp_path: Path) -> None:
    cases = load_answer_evaluation_cases(
        _write_dataset(
            tmp_path / "answer-cases.json",
            [
                {
                    "case_id": "answer-case-001",
                    "question": "医疗机构需要保留什么？",
                    "expected_behavior": "answer",
                    "required_evidence_terms": ["第一条"],
                    "required_answer_terms": ["审核依据"],
                    "required_citation_terms": ["医疗机构"],
                }
            ],
        )
    )
    engine = StaticSearchEngine(
        (
            _result(
                SourceCollection.MEDICAL_INSURANCE_LAWS,
                text="第一条 医疗机构应当保留医保基金审核依据。",
            ),
        )
    )

    summary = evaluate_answers(
        cases,
        engine,
        generation_provider=StaticAnswerProvider(),
    )

    assert summary.pass_rate == 1.0
    assert summary.results[0].answer == "医疗机构应当保留医保基金审核依据 [C1]。"
    assert summary.results[0].fallback_used is False
    assert summary.generation_success_rate == 1.0
    assert summary.fallback_rate == 0.0


def test_evaluate_answers_can_require_generation_success(tmp_path: Path) -> None:
    cases = load_answer_evaluation_cases(
        _write_dataset(
            tmp_path / "answer-cases.json",
            [
                {
                    "case_id": "answer-case-001",
                    "question": "医疗机构需要保留什么？",
                    "expected_behavior": "answer",
                    "required_evidence_terms": ["第一条"],
                    "required_answer_terms": ["审核依据"],
                    "required_citation_terms": ["医疗机构"],
                }
            ],
        )
    )
    engine = StaticSearchEngine(
        (
            _result(
                SourceCollection.MEDICAL_INSURANCE_LAWS,
                text="第一条 医疗机构应当保留医保基金审核依据。",
            ),
        )
    )

    summary = evaluate_answers(
        cases,
        engine,
        generation_provider=UncitedAnswerProvider(),
        require_generation_success=True,
    )

    assert summary.pass_rate == 0.0
    assert summary.fallback_rate == 1.0
    assert summary.results[0].failure_reasons == ("generation_provider_failed",)


class StaticSearchEngine:
    def __init__(self, results: tuple[HybridSearchResult, ...]) -> None:
        self._results = results

    def search(
        self,
        query: str,
        *,
        filters: RetrievalFilters | None = None,
        top_k: int = 10,
        fetch_k: int = 50,
    ) -> tuple[HybridSearchResult, ...]:
        return self._results[:top_k]


class StaticAnswerProvider:
    provider = "fake"
    model_name = "static-answer"
    provider_version = "v1"

    def generate_answer(self, question: str, citations: Sequence[Citation]) -> str:
        return "医疗机构应当保留医保基金审核依据 [C1]。"


class UncitedAnswerProvider:
    provider = "fake"
    model_name = "uncited-answer"
    provider_version = "v1"

    def generate_answer(self, question: str, citations: Sequence[Citation]) -> str:
        return "医疗机构应当保留医保基金审核依据。"


def _result(
    source_collection: SourceCollection,
    *,
    text: str,
) -> HybridSearchResult:
    return HybridSearchResult(
        chunk=RetrievedChunk(
            chunk_id=uuid4(),
            text=text,
            metadata={"source_collection": source_collection.value},
            locator={"type": "line", "source_path": "source.md", "line_start": 1},
            index_version_key="index-v1",
            source_package_version_key="package-v1",
        ),
        score=0.7,
        vector_score=0.7,
        bm25_score=0.7,
        rerank_score=None,
        source_weight=1.0,
        matched_by=("vector", "bm25"),
    )


def _write_dataset(path: Path, cases: list[dict[str, object]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"cases": cases}, ensure_ascii=False), encoding="utf-8")
    return path
