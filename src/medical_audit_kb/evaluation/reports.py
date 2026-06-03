from __future__ import annotations

import json
from datetime import UTC, datetime

from medical_audit_kb.evaluation.runner import EvaluationSummary


def render_evaluation_summary_markdown(
    summary: EvaluationSummary,
    *,
    embedding_provider: str | None = None,
    embedding_model: str | None = None,
    embedding_dimension: int | None = None,
    index_root: str | None = None,
) -> str:
    report_date = datetime.now(UTC).date().isoformat()
    lines = [
        "---",
        "title: 知识库真实资料检索评测报告",
        "doc_type: analysis",
        "module: knowledge-query-engine",
        "topic: real-data-retrieval-evaluation",
        "status: draft",
        f"created: {report_date}",
        f"updated: {report_date}",
        "owner: self",
        "source: ai",
        "---",
        "",
        "# 知识库真实资料检索评测报告",
        "",
        (
            "说明：当前评测使用真实资料索引产物和 CLI 指定的 embedding provider。"
            "评测 provider 必须与索引构建 provider 保持一致。"
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
        "",
        "## 2. 指标",
        "",
        "| 指标 | 数值 |",
        "| --- | ---: |",
        f"| `case_count` | {summary.case_count} |",
        f"| `recall_at_k` | {_format_rate(summary.recall_at_k)} |",
        f"| `citation_hit_rate` | {_format_rate(summary.citation_hit_rate)} |",
        (
            "| `preview_location_success_rate` | "
            f"{_format_rate(summary.preview_location_success_rate)} |"
        ),
        "",
        "## 3. 未命中样例",
        "",
        "| case_id | question | missing_expected_sources |",
        "| --- | --- | --- |",
    ]
    missed = [result for result in summary.results if not result.recall_hit]
    if not missed:
        lines.append("| 无 | 无 | 无 |")
    else:
        for result in missed[:20]:
            lines.append(
                "| "
                f"`{result.case_id}` | "
                f"{result.question} | "
                f"`{json.dumps(result.missing_expected_sources, ensure_ascii=False)}` |"
            )
    return "\n".join(lines) + "\n"


def _format_rate(value: float) -> str:
    return f"{value:.2%}"
