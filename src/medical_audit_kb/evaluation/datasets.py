from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from medical_audit_kb.domain.constants import SourceCollection
from medical_audit_kb.retrieval.filters import RetrievalFilters


@dataclass(frozen=True, slots=True)
class ExpectedEvidence:
    source_collection: SourceCollection
    source_path: str
    article_or_rule: str | None = None
    locator: dict[str, object] = field(default_factory=dict)
    required_terms: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AnswerAcceptanceCriteria:
    required_terms: tuple[str, ...] = ()
    min_citations: int = 1
    require_preview: bool = True


@dataclass(frozen=True, slots=True)
class AuditorQuestionImport:
    raw_question: str | None = None
    source_channel: str | None = None
    auditor_question_id: str | None = None
    auditor_role: str | None = None
    asked_at: str | None = None
    reviewer_notes: str | None = None


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    case_id: str
    question: str
    expected_evidence: tuple[ExpectedEvidence, ...]
    acceptance_criteria: AnswerAcceptanceCriteria
    tags: tuple[str, ...] = ()
    filters: RetrievalFilters = field(default_factory=RetrievalFilters)
    auditor_import: AuditorQuestionImport = field(default_factory=AuditorQuestionImport)


@dataclass(frozen=True, slots=True)
class MaterialQuestionSeed:
    source_collection: SourceCollection
    source_path: str
    title: str
    text: str
    locator: dict[str, object] = field(default_factory=dict)
    tags: tuple[str, ...] = ()


def load_evaluation_cases(path: Path | str) -> tuple[EvaluationCase, ...]:
    dataset_path = Path(path)
    payload = _load_payload(dataset_path)
    cases_payload = payload.get("cases")
    if not isinstance(cases_payload, list):
        raise ValueError("evaluation dataset must contain a cases list")
    return tuple(_evaluation_case(item) for item in cases_payload)


def prd_seed_cases() -> tuple[EvaluationCase, ...]:
    return (
        EvaluationCase(
            case_id="prd-prescription-over-quantity-001",
            question="肿瘤门特慢病门诊处方出现超量开药时，应引用哪些规则来源？",
            expected_evidence=(
                ExpectedEvidence(
                    source_collection=SourceCollection.SUPERVISION_RULES_KNOWLEDGE,
                    source_path="智能监管两库规则和知识点/处方规则.xlsx",
                    article_or_rule="超量开药",
                    required_terms=("超量", "处方"),
                ),
            ),
            acceptance_criteria=AnswerAcceptanceCriteria(required_terms=("超量开药", "规则来源")),
            tags=("prd", "prescription-audit", "over-quantity"),
        ),
        EvaluationCase(
            case_id="prd-prescription-over-course-001",
            question="肿瘤门特慢病长处方如何判断是否超疗程？",
            expected_evidence=(
                ExpectedEvidence(
                    source_collection=SourceCollection.SUPERVISION_RULES_KNOWLEDGE,
                    source_path="智能监管两库规则和知识点/处方规则.xlsx",
                    article_or_rule="超疗程开药",
                    required_terms=("超疗程", "长处方"),
                ),
            ),
            acceptance_criteria=AnswerAcceptanceCriteria(required_terms=("超疗程", "长处方")),
            tags=("prd", "prescription-audit", "over-course"),
        ),
        EvaluationCase(
            case_id="prd-rule-version-trace-001",
            question="审计结果中的命中规则需要怎样追溯到规则版本？",
            expected_evidence=(
                ExpectedEvidence(
                    source_collection=SourceCollection.SUPERVISION_RULES_KNOWLEDGE,
                    source_path="智能监管两库规则和知识点/规则版本.xlsx",
                    article_or_rule="规则版本",
                    required_terms=("规则版本", "追溯"),
                ),
            ),
            acceptance_criteria=AnswerAcceptanceCriteria(required_terms=("规则版本", "可追溯")),
            tags=("prd", "rule-governance"),
        ),
    )


def generate_candidate_cases_from_materials(
    materials: Iterable[MaterialQuestionSeed],
    *,
    case_id_prefix: str = "auto-material",
    max_cases: int = 50,
) -> tuple[EvaluationCase, ...]:
    cases: list[EvaluationCase] = []
    for material in materials:
        for question, article_or_rule in _questions_for_material(material):
            if len(cases) >= max_cases:
                return tuple(cases)
            case_number = len(cases) + 1
            cases.append(
                EvaluationCase(
                    case_id=f"{case_id_prefix}-{case_number:04d}",
                    question=question,
                    expected_evidence=(
                        ExpectedEvidence(
                            source_collection=material.source_collection,
                            source_path=material.source_path,
                            article_or_rule=article_or_rule,
                            locator=dict(material.locator),
                            required_terms=tuple(term for term in (article_or_rule,) if term),
                        ),
                    ),
                    acceptance_criteria=AnswerAcceptanceCriteria(
                        required_terms=tuple(term for term in (article_or_rule,) if term)
                    ),
                    tags=("auto-generated", *material.tags),
                    filters=RetrievalFilters(
                        source_collections=(material.source_collection,),
                    ),
                )
            )
    return tuple(cases)


def answer_meets_acceptance(
    answer: str,
    *,
    citation_count: int,
    preview_success: bool,
    criteria: AnswerAcceptanceCriteria,
) -> bool:
    if citation_count < criteria.min_citations:
        return False
    if criteria.require_preview and not preview_success:
        return False
    return all(term in answer for term in criteria.required_terms)


def _load_payload(path: Path) -> Mapping[str, Any]:
    raw_text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        payload = json.loads(raw_text)
    elif path.suffix.lower() in {".yaml", ".yml"}:
        payload = yaml.safe_load(raw_text)
    else:
        raise ValueError(f"unsupported evaluation dataset type: {path.suffix}")
    if not isinstance(payload, Mapping):
        raise ValueError("evaluation dataset root must be an object")
    return payload


def _evaluation_case(payload: object) -> EvaluationCase:
    if not isinstance(payload, Mapping):
        raise ValueError("evaluation case must be an object")
    expected_payload = payload.get("expected_evidence")
    if not isinstance(expected_payload, list) or not expected_payload:
        raise ValueError("evaluation case must contain expected_evidence")
    return EvaluationCase(
        case_id=_required_str(payload, "case_id"),
        question=_required_str(payload, "question"),
        expected_evidence=tuple(_expected_evidence(item) for item in expected_payload),
        acceptance_criteria=_acceptance_criteria(payload.get("acceptance_criteria")),
        tags=_str_tuple(payload.get("tags")),
        filters=_filters(payload.get("filters")),
        auditor_import=_auditor_import(payload.get("auditor_import")),
    )


def _expected_evidence(payload: object) -> ExpectedEvidence:
    if not isinstance(payload, Mapping):
        raise ValueError("expected evidence must be an object")
    locator = payload.get("locator")
    return ExpectedEvidence(
        source_collection=SourceCollection(_required_str(payload, "source_collection")),
        source_path=_required_str(payload, "source_path"),
        article_or_rule=_optional_str(payload.get("article_or_rule")),
        locator=dict(locator) if isinstance(locator, Mapping) else {},
        required_terms=_str_tuple(payload.get("required_terms")),
    )


def _acceptance_criteria(payload: object) -> AnswerAcceptanceCriteria:
    if payload is None:
        return AnswerAcceptanceCriteria()
    if not isinstance(payload, Mapping):
        raise ValueError("acceptance_criteria must be an object")
    return AnswerAcceptanceCriteria(
        required_terms=_str_tuple(payload.get("required_terms")),
        min_citations=_int_value(payload.get("min_citations"), default=1),
        require_preview=_bool_value(payload.get("require_preview"), default=True),
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
        title_only=bool(payload.get("title_only", False)),
        title_query=_optional_str(payload.get("title_query")) or "",
    )


def _auditor_import(payload: object) -> AuditorQuestionImport:
    if payload is None:
        return AuditorQuestionImport()
    if not isinstance(payload, Mapping):
        raise ValueError("auditor_import must be an object")
    return AuditorQuestionImport(
        raw_question=_optional_str(payload.get("raw_question")),
        source_channel=_optional_str(payload.get("source_channel")),
        auditor_question_id=_optional_str(payload.get("auditor_question_id")),
        auditor_role=_optional_str(payload.get("auditor_role")),
        asked_at=_optional_str(payload.get("asked_at")),
        reviewer_notes=_optional_str(payload.get("reviewer_notes")),
    )


def _questions_for_material(material: MaterialQuestionSeed) -> tuple[tuple[str, str | None], ...]:
    article_match = re.search(r"(第[一二三四五六七八九十百千万零〇\d]+条)", material.text)
    if article_match:
        article = article_match.group(1)
        return ((f"{material.title}中{article}的审核要求是什么？", article),)

    rule_name_match = re.search(r"规则名称[:：]\s*([^\n；;]+)", material.text)
    if rule_name_match:
        rule_name = rule_name_match.group(1).strip()
        return ((f"{rule_name}规则的判定依据是什么？", rule_name),)

    return ((f"{material.title}的核心审核依据是什么？", None),)


def _required_str(payload: Mapping[object, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("optional string field must be a string")
    return value


def _str_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list | tuple):
        raise ValueError("string list field must be a list")
    if not all(isinstance(item, str) for item in value):
        raise ValueError("string list field must only contain strings")
    return tuple(value)


def _list_value(value: object) -> tuple[object, ...]:
    if value is None:
        return ()
    if not isinstance(value, list | tuple):
        raise ValueError("list field must be a list")
    return tuple(value)


def _int_value(value: object, *, default: int) -> int:
    if value is None:
        return default
    if not isinstance(value, int):
        raise ValueError("integer field must be an integer")
    return value


def _bool_value(value: object, *, default: bool) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        raise ValueError("boolean field must be a boolean")
    return value
