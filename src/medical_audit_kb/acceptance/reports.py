from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from medical_audit_kb.ingestion.pipeline import PipelineFileIssue, PipelineRunResult

INDEX_SUCCESS_THRESHOLD = 0.95
QUEUE_EXPLAIN_THRESHOLD = 1.0
DEFAULT_SAMPLE_SIZE = 20


@dataclass(frozen=True, slots=True)
class AcceptanceGateResult:
    name: str
    passed: bool
    actual: float | bool
    expected: float | bool
    description: str

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "passed": self.passed,
            "actual": self.actual,
            "expected": self.expected,
            "description": self.description,
        }


@dataclass(frozen=True, slots=True)
class AcceptanceReport:
    summary: dict[str, object]
    index_success_rate: float
    queue_explain_rate: float
    no_silent_loss: bool
    accounted_file_count: int
    lost_file_count: int
    gates: tuple[AcceptanceGateResult, ...]
    failed_reason_counts: dict[str, int]
    pending_reason_counts: dict[str, int]
    failed_samples: tuple[dict[str, str], ...]
    pending_samples: tuple[dict[str, str], ...]

    @property
    def passed(self) -> bool:
        return all(gate.passed for gate in self.gates)

    def to_dict(self) -> dict[str, object]:
        return {
            "summary": self.summary,
            "index_success_rate": self.index_success_rate,
            "queue_explain_rate": self.queue_explain_rate,
            "no_silent_loss": self.no_silent_loss,
            "accounted_file_count": self.accounted_file_count,
            "lost_file_count": self.lost_file_count,
            "passed": self.passed,
            "gates": [gate.to_dict() for gate in self.gates],
            "failed_reason_counts": self.failed_reason_counts,
            "pending_reason_counts": self.pending_reason_counts,
            "failed_samples": list(self.failed_samples),
            "pending_samples": list(self.pending_samples),
        }


def build_acceptance_report(
    run_result: PipelineRunResult,
    *,
    sample_size: int = DEFAULT_SAMPLE_SIZE,
) -> AcceptanceReport:
    summary = run_result.summary.to_dict()
    index_success_rate = _index_success_rate(run_result)
    queue_explain_rate = _queue_explain_rate(run_result)
    accounted_file_count = _accounted_file_count(run_result)
    discovered_file_count = run_result.summary.discovered_file_count
    lost_file_count = max(0, discovered_file_count - accounted_file_count)
    no_silent_loss = lost_file_count == 0 and accounted_file_count == discovered_file_count
    gates = (
        AcceptanceGateResult(
            name="index-success-rate",
            passed=index_success_rate >= INDEX_SUCCESS_THRESHOLD,
            actual=index_success_rate,
            expected=INDEX_SUCCESS_THRESHOLD,
            description="可索引文件成功抽取并切分比例不低于 95%",
        ),
        AcceptanceGateResult(
            name="queue-explain-rate",
            passed=queue_explain_rate >= QUEUE_EXPLAIN_THRESHOLD,
            actual=queue_explain_rate,
            expected=QUEUE_EXPLAIN_THRESHOLD,
            description="失败队列和待处理队列必须 100% 具备可解释原因",
        ),
        AcceptanceGateResult(
            name="no-silent-loss",
            passed=no_silent_loss,
            actual=no_silent_loss,
            expected=True,
            description="发现文件必须全部进入 indexed、failed、pending 或 ignored 之一",
        ),
    )
    return AcceptanceReport(
        summary=summary,
        index_success_rate=index_success_rate,
        queue_explain_rate=queue_explain_rate,
        no_silent_loss=no_silent_loss,
        accounted_file_count=accounted_file_count,
        lost_file_count=lost_file_count,
        gates=gates,
        failed_reason_counts=_reason_counts(run_result.failed_files),
        pending_reason_counts=_reason_counts(run_result.pending_files),
        failed_samples=_issue_samples(run_result.failed_files, sample_size=sample_size),
        pending_samples=_issue_samples(run_result.pending_files, sample_size=sample_size),
    )


def render_acceptance_report_markdown(report: AcceptanceReport) -> str:
    status = "PASS" if report.passed else "FAIL"
    lines = [
        "---",
        "title: 知识库真实资料索引验收报告",
        "doc_type: analysis",
        "module: knowledge-query-engine",
        "topic: real-data-index-acceptance",
        "status: draft",
        "created: 2026-05-31",
        "updated: 2026-05-31",
        "owner: self",
        "source: ai",
        "---",
        "",
        "# 知识库真实资料索引验收报告",
        "",
        f"总体状态：`{status}`",
        "",
        "## 1. 摘要",
        "",
        "| 指标 | 数值 |",
        "| --- | ---: |",
    ]
    for key, value in report.summary.items():
        lines.append(f"| `{key}` | {value} |")

    lines.extend(
        [
            f"| `index_success_rate` | {_format_rate(report.index_success_rate)} |",
            f"| `queue_explain_rate` | {_format_rate(report.queue_explain_rate)} |",
            f"| `accounted_file_count` | {report.accounted_file_count} |",
            f"| `lost_file_count` | {report.lost_file_count} |",
            "",
            "## 2. 验收门禁",
            "",
            "| 门禁 | 状态 | 实际 | 预期 | 说明 |",
            "| --- | --- | ---: | ---: | --- |",
        ]
    )
    for gate in report.gates:
        gate_status = "PASS" if gate.passed else "FAIL"
        lines.append(
            "| "
            f"`{gate.name}` | `{gate_status}` | "
            f"{_format_gate_value(gate.actual)} | {_format_gate_value(gate.expected)} | "
            f"{gate.description} |"
        )

    lines.extend(
        [
            "",
            "## 3. 失败原因分布",
            "",
            *_render_counts(report.failed_reason_counts),
            "",
            "## 4. 待处理原因分布",
            "",
            *_render_counts(report.pending_reason_counts),
            "",
            "## 5. 失败样例",
            "",
            *_render_samples(report.failed_samples),
            "",
            "## 6. 待处理样例",
            "",
            *_render_samples(report.pending_samples),
            "",
            "## 7. 下一步判断",
            "",
            _next_step_line(report),
        ]
    )
    return "\n".join(lines) + "\n"


def _index_success_rate(run_result: PipelineRunResult) -> float:
    candidate_count = run_result.summary.index_candidate_file_count
    if candidate_count == 0:
        return 0.0
    return run_result.summary.indexed_file_count / candidate_count


def _queue_explain_rate(run_result: PipelineRunResult) -> float:
    issues = run_result.failed_files + run_result.pending_files
    if not issues:
        return 1.0
    explained_count = len(
        [issue for issue in issues if issue.error_type.value and issue.error_summary.strip()]
    )
    return explained_count / len(issues)


def _accounted_file_count(run_result: PipelineRunResult) -> int:
    return (
        run_result.summary.indexed_file_count
        + run_result.summary.failed_file_count
        + run_result.summary.pending_file_count
        + run_result.summary.ignored_file_count
    )


def _reason_counts(issues: tuple[PipelineFileIssue, ...]) -> dict[str, int]:
    counts = Counter(issue.error_type.value for issue in issues)
    return dict(sorted(counts.items()))


def _issue_samples(
    issues: tuple[PipelineFileIssue, ...],
    *,
    sample_size: int,
) -> tuple[dict[str, str], ...]:
    return tuple(
        {
            "relative_path": issue.relative_path,
            "error_type": issue.error_type.value,
            "error_summary": issue.error_summary,
        }
        for issue in issues[:sample_size]
    )


def _format_rate(value: float) -> str:
    return f"{value:.2%}"


def _format_gate_value(value: float | bool) -> str:
    if isinstance(value, bool):
        return str(value)
    return _format_rate(value)


def _render_counts(counts: dict[str, int]) -> list[str]:
    if not counts:
        return ["无。"]
    lines = ["| 原因 | 数量 |", "| --- | ---: |"]
    for reason, count in counts.items():
        lines.append(f"| `{reason}` | {count} |")
    return lines


def _render_samples(samples: tuple[dict[str, str], ...]) -> list[str]:
    if not samples:
        return ["无。"]
    lines = ["| 文件 | 类型 | 摘要 |", "| --- | --- | --- |"]
    for sample in samples:
        lines.append(
            "| "
            f"`{sample['relative_path']}` | "
            f"`{sample['error_type']}` | "
            f"{sample['error_summary']} |"
        )
    return lines


def _next_step_line(report: AcceptanceReport) -> str:
    if report.passed:
        return "当前资料抽取与切分验收通过，下一步进入持久化向量/BM25 索引和真实检索评测。"
    return "当前资料抽取与切分验收未通过，下一步优先处理失败队列和待处理队列。"
