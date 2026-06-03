from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from medical_audit_kb.domain.constants import SourceCollection
from medical_audit_kb.generation.answer_builder import AnswerGenerationProvider
from medical_audit_kb.generation.citations import Citation, EvidenceType

PREFLIGHT_QUESTION = "医疗机构需要保留什么审核依据？"
PREFLIGHT_SNIPPET = "第一条 医疗机构应当保留医保基金审核依据。"
PREFLIGHT_CITATION_ID = "C1"
PREFLIGHT_REQUIRED_TERM = "审核依据"


@dataclass(frozen=True, slots=True)
class AnswerProviderPreflightResult:
    provider: str
    model_name: str
    provider_version: str
    success: bool
    citation_marker_present: bool
    required_term_present: bool
    answer: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "model_name": self.model_name,
            "provider_version": self.provider_version,
            "success": self.success,
            "citation_marker_present": self.citation_marker_present,
            "required_term_present": self.required_term_present,
            "answer": self.answer,
            "error": self.error,
        }


def run_answer_provider_preflight(
    provider: AnswerGenerationProvider,
) -> AnswerProviderPreflightResult:
    try:
        answer = provider.generate_answer(PREFLIGHT_QUESTION, (_preflight_citation(),))
    except Exception as exc:
        return AnswerProviderPreflightResult(
            provider=provider.provider,
            model_name=provider.model_name,
            provider_version=provider.provider_version,
            success=False,
            citation_marker_present=False,
            required_term_present=False,
            error=str(exc),
        )

    citation_marker_present = f"[{PREFLIGHT_CITATION_ID}]" in answer
    required_term_present = PREFLIGHT_REQUIRED_TERM in answer
    return AnswerProviderPreflightResult(
        provider=provider.provider,
        model_name=provider.model_name,
        provider_version=provider.provider_version,
        success=citation_marker_present and required_term_present,
        citation_marker_present=citation_marker_present,
        required_term_present=required_term_present,
        answer=answer,
    )


def render_answer_provider_preflight_markdown(
    result: AnswerProviderPreflightResult,
) -> str:
    status = "PASS" if result.success else "FAIL"
    lines = [
        "---",
        "title: 答案生成 Provider 预检报告",
        "doc_type: analysis",
        "module: knowledge-query-engine",
        "topic: answer-provider-preflight",
        "status: draft",
        "created: 2026-06-01",
        "updated: 2026-06-01",
        "owner: self",
        "source: ai",
        "---",
        "",
        "# 答案生成 Provider 预检报告",
        "",
        f"总体状态：`{status}`",
        "",
        "## 1. 配置",
        "",
        "| 配置 | 值 |",
        "| --- | --- |",
        f"| `provider` | `{result.provider}` |",
        f"| `model_name` | `{result.model_name}` |",
        f"| `provider_version` | `{result.provider_version}` |",
        "",
        "## 2. 门禁",
        "",
        "| 检查项 | 结果 |",
        "| --- | --- |",
        f"| `citation_marker_present` | `{result.citation_marker_present}` |",
        f"| `required_term_present` | `{result.required_term_present}` |",
        "",
        "## 3. 输出",
        "",
        f"- `answer`: {result.answer or '无'}",
        f"- `error`: {result.error or '无'}",
    ]
    return "\n".join(lines) + "\n"


def _preflight_citation() -> Citation:
    return Citation(
        citation_id=PREFLIGHT_CITATION_ID,
        evidence_type=EvidenceType.LEGAL_BASIS,
        source_collection=SourceCollection.MEDICAL_INSURANCE_LAWS,
        chunk_id=uuid4(),
        snippet=PREFLIGHT_SNIPPET,
        locator={"type": "line", "source_path": "preflight.md", "line_start": 1},
        index_version_key="preflight-index",
        source_package_version_key="preflight-source",
        score=1.0,
        metadata={"source_collection": SourceCollection.MEDICAL_INSURANCE_LAWS.value},
    )
