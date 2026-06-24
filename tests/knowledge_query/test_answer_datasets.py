from __future__ import annotations

from pathlib import Path

from medical_audit_kb.evaluation.answer_datasets import (
    AnswerEvaluationCase,
    ExpectedAnswerBehavior,
    load_answer_evaluation_cases,
)

_DATASET_PATH = (
    Path(__file__).resolve().parents[2]
    / "configs/evaluation/knowledge-query-answer-evaluation-cases-v1.yaml"
)


def _cases() -> tuple[AnswerEvaluationCase, ...]:
    return load_answer_evaluation_cases(_DATASET_PATH)


def test_answer_evaluation_dataset_loads_and_is_well_formed() -> None:
    cases = _cases()
    assert len(cases) >= 10
    case_ids = [case.case_id for case in cases]
    assert len(case_ids) == len(set(case_ids)), "case_id 必须唯一"
    for case in cases:
        assert isinstance(case.expected_behavior, ExpectedAnswerBehavior)
        if case.expected_behavior is ExpectedAnswerBehavior.ANSWER:
            assert case.required_answer_terms, (
                f"{case.case_id}: answer 用例必须有 required_answer_terms"
            )
        else:
            assert not case.required_answer_terms, (
                f"{case.case_id}: refuse 用例不应有 required_answer_terms"
            )


def test_weak_recall_subset_is_present_and_answerable() -> None:
    weak_recall_cases = [case for case in _cases() if "weak-recall" in case.tags]
    assert weak_recall_cases, "应存在 weak-recall 标签子集以度量 generate-or-safe-fallback"
    assert all(
        case.expected_behavior is ExpectedAnswerBehavior.ANSWER for case in weak_recall_cases
    )
    assert any("icd" in case.case_id for case in weak_recall_cases), "应包含 ICD-10 弱召回基准用例"


def test_needs_corpus_verification_cases_are_answer_typed() -> None:
    pending = [case for case in _cases() if "needs-corpus-verification" in case.tags]
    # 新增的标准 ICD 用例：required 术语需人工对照真实语料确认后再移除该标签。
    assert all(case.expected_behavior is ExpectedAnswerBehavior.ANSWER for case in pending)
