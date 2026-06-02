from __future__ import annotations

import json
from datetime import UTC, datetime

from medical_audit_kb.evaluation.answer_runner import AnswerEvaluationSummary


def render_answer_evaluation_summary_markdown(
    summary: AnswerEvaluationSummary,
    *,
    embedding_provider: str | None = None,
    embedding_model: str | None = None,
    embedding_dimension: int | None = None,
    answer_provider: str | None = None,
    answer_model: str | None = None,
    index_root: str | None = None,
) -> str:
    report_date = datetime.now(UTC).date().isoformat()
    lines = [
        "---",
        "title: 知识库答案生成质量评测报告",
        "doc_type: analysis",
        "module: knowledge-query-engine",
        "topic: answer-quality-evaluation",
        "status: draft",
        f"created: {report_date}",
        f"updated: {report_date}",
        "owner: self",
        "source: ai",
        "---",
        "",
        "# 知识库答案生成质量评测报告",
        "",
        (
            "说明：当前评测验证 citation-backed answer 的引用约束、"
            "拒答门控和关键术语覆盖，不替代专家人工审核。"
        ),
        "",
        "## 1. 运行配置",
        "",
        "| 配置 | 值 |",
        "| --- | --- |",
        f"| `index_root` | `{index_root or 'unknown'}` |",
        f"| `embedding_provider` | `{embedding_provider or 'unknown'}` |",
        f"| `embedding_model` | `{embedding_model or 'unknown'}` |",
        f"| `embedding_dimension` | `{embedding_dimension or 'unknown'}` |",
        f"| `answer_provider` | `{answer_provider or 'fallback'}` |",
        f"| `answer_model` | `{answer_model or 'citation-backed-fallback'}` |",
        "",
        "## 2. 指标",
        "",
        "| 指标 | 数值 |",
        "| --- | ---: |",
        f"| `case_count` | {summary.case_count} |",
        f"| `pass_rate` | {_format_rate(summary.pass_rate)} |",
        f"| `citation_marker_rate` | {_format_rate(summary.citation_marker_rate)} |",
        f"| `answer_term_coverage_rate` | {_format_rate(summary.answer_term_coverage_rate)} |",
        f"| `citation_term_coverage_rate` | {_format_rate(summary.citation_term_coverage_rate)} |",
        f"| `refusal_accuracy_rate` | {_format_rate(summary.refusal_accuracy_rate)} |",
        (
            "| `unsupported_claim_free_rate` | "
            f"{_format_rate(summary.unsupported_claim_free_rate)} |"
        ),
        f"| `generation_success_rate` | {_format_rate(summary.generation_success_rate)} |",
        f"| `fallback_rate` | {_format_rate(summary.fallback_rate)} |",
        "",
        "## 3. 未通过样例",
        "",
        "| case_id | expected_behavior | failure_reasons |",
        "| --- | --- | --- |",
    ]
    failed = [result for result in summary.results if not result.passed]
    if not failed:
        lines.append("| 无 | 无 | 无 |")
    else:
        for result in failed[:20]:
            lines.append(
                "| "
                f"`{result.case_id}` | "
                f"`{result.expected_behavior}` | "
                f"`{json.dumps(result.failure_reasons, ensure_ascii=False)}` |"
            )
    return "\n".join(lines) + "\n"


def _format_rate(value: float) -> str:
    return f"{value:.2%}"
