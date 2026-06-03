from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

from medical_audit_kb.domain.constants import SourceCollection
from medical_audit_kb.retrieval.filters import RetrievalFilters


class ExpectedAnswerBehavior(StrEnum):
    ANSWER = "answer"
    REFUSE = "refuse"


@dataclass(frozen=True, slots=True)
class AnswerEvaluationCase:
    case_id: str
    question: str
    expected_behavior: ExpectedAnswerBehavior
    required_evidence_terms: tuple[str, ...] = ()
    required_answer_terms: tuple[str, ...] = ()
    required_citation_terms: tuple[str, ...] = ()
    forbidden_answer_terms: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    filters: RetrievalFilters = field(default_factory=RetrievalFilters)


def load_answer_evaluation_cases(path: Path | str) -> tuple[AnswerEvaluationCase, ...]:
    dataset_path = Path(path)
    payload = _load_payload(dataset_path)
    cases_payload = payload.get("cases")
    if not isinstance(cases_payload, list):
        raise ValueError("answer evaluation dataset must contain a cases list")
    return tuple(_answer_evaluation_case(item) for item in cases_payload)


def _load_payload(path: Path) -> Mapping[str, Any]:
    raw_text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        payload = json.loads(raw_text)
    elif path.suffix.lower() in {".yaml", ".yml"}:
        payload = yaml.safe_load(raw_text)
    else:
        raise ValueError(f"unsupported answer evaluation dataset type: {path.suffix}")
    if not isinstance(payload, Mapping):
        raise ValueError("answer evaluation dataset root must be an object")
    return payload


def _answer_evaluation_case(payload: object) -> AnswerEvaluationCase:
    if not isinstance(payload, Mapping):
        raise ValueError("answer evaluation case must be an object")
    return AnswerEvaluationCase(
        case_id=_required_str(payload, "case_id"),
        question=_required_str(payload, "question"),
        expected_behavior=ExpectedAnswerBehavior(_required_str(payload, "expected_behavior")),
        required_evidence_terms=_str_tuple(payload.get("required_evidence_terms")),
        required_answer_terms=_str_tuple(payload.get("required_answer_terms")),
        required_citation_terms=_str_tuple(payload.get("required_citation_terms")),
        forbidden_answer_terms=_str_tuple(payload.get("forbidden_answer_terms")),
        tags=_str_tuple(payload.get("tags")),
        filters=_filters(payload.get("filters")),
    )


def _filters(payload: object) -> RetrievalFilters:
    if payload is None:
        return RetrievalFilters()
    if not isinstance(payload, Mapping):
        raise ValueError("filters must be an object")
    return RetrievalFilters(
        source_collections=tuple(
            SourceCollection(item) for item in _str_tuple(payload.get("source_collections"))
        ),
        years=tuple(_int_value(item, default=0) for item in _list_value(payload.get("years"))),
        regions=_str_tuple(payload.get("regions")),
        document_types=_str_tuple(payload.get("document_types")),
        business_topics=_str_tuple(payload.get("business_topics")),
    )


def _required_str(payload: Mapping[object, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"answer evaluation case must contain {key}")
    return value


def _str_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if not isinstance(value, list):
        raise ValueError("string list field must be a list or string")
    if not all(isinstance(item, str) for item in value):
        raise ValueError("string list field must only contain strings")
    return tuple(value)


def _list_value(value: object) -> tuple[object, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError("list field must be a list")
    return tuple(value)


def _int_value(value: object, *, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("integer field must be an integer")
    return value
