from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from medical_audit_kb.indexing.persistent_index import (
    CHUNKS_FILE,
    EMBEDDINGS_FILE,
    FAILED_FILES_FILE,
    PENDING_FILES_FILE,
    SUMMARY_FILE,
)

DEFAULT_SCHEMA_DIMENSION = 1024
DEFAULT_MAX_ISSUE_SAMPLES = 20


@dataclass(frozen=True, slots=True)
class PgvectorImportGate:
    name: str
    passed: bool
    actual: object
    expected: object
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
class PgvectorImportPlan:
    index_root: Path
    summary: dict[str, object]
    expected_chunk_count: int | None
    expected_embedding_count: int | None
    expected_failed_file_count: int | None
    expected_pending_file_count: int | None
    expected_embedding_provider: str | None
    expected_embedding_model: str | None
    expected_embedding_provider_version: str | None
    expected_embedding_dimension: int | None
    schema_dimension: int
    chunk_row_count: int | None
    embedding_row_count: int | None
    failed_file_row_count: int | None
    pending_file_row_count: int | None
    duplicate_chunk_id_count: int
    duplicate_embedding_chunk_id_count: int
    missing_embedding_count: int
    orphan_embedding_count: int
    invalid_embedding_metadata_count: int
    invalid_embedding_dimension_count: int
    issue_samples: tuple[str, ...]
    gates: tuple[PgvectorImportGate, ...]

    @property
    def ready_for_import(self) -> bool:
        return all(gate.passed for gate in self.gates)

    def to_dict(self) -> dict[str, object]:
        return {
            "index_root": str(self.index_root),
            "summary": self.summary,
            "expected_chunk_count": self.expected_chunk_count,
            "expected_embedding_count": self.expected_embedding_count,
            "expected_failed_file_count": self.expected_failed_file_count,
            "expected_pending_file_count": self.expected_pending_file_count,
            "expected_embedding_provider": self.expected_embedding_provider,
            "expected_embedding_model": self.expected_embedding_model,
            "expected_embedding_provider_version": self.expected_embedding_provider_version,
            "expected_embedding_dimension": self.expected_embedding_dimension,
            "schema_dimension": self.schema_dimension,
            "chunk_row_count": self.chunk_row_count,
            "embedding_row_count": self.embedding_row_count,
            "failed_file_row_count": self.failed_file_row_count,
            "pending_file_row_count": self.pending_file_row_count,
            "duplicate_chunk_id_count": self.duplicate_chunk_id_count,
            "duplicate_embedding_chunk_id_count": self.duplicate_embedding_chunk_id_count,
            "missing_embedding_count": self.missing_embedding_count,
            "orphan_embedding_count": self.orphan_embedding_count,
            "invalid_embedding_metadata_count": self.invalid_embedding_metadata_count,
            "invalid_embedding_dimension_count": self.invalid_embedding_dimension_count,
            "ready_for_import": self.ready_for_import,
            "gates": [gate.to_dict() for gate in self.gates],
            "issue_samples": list(self.issue_samples),
        }


def build_pgvector_import_plan(
    index_root: Path | str,
    *,
    schema_dimension: int = DEFAULT_SCHEMA_DIMENSION,
    max_issue_samples: int = DEFAULT_MAX_ISSUE_SAMPLES,
) -> PgvectorImportPlan:
    root = Path(index_root)
    required_paths = {
        SUMMARY_FILE: root / SUMMARY_FILE,
        CHUNKS_FILE: root / CHUNKS_FILE,
        EMBEDDINGS_FILE: root / EMBEDDINGS_FILE,
        FAILED_FILES_FILE: root / FAILED_FILES_FILE,
        PENDING_FILES_FILE: root / PENDING_FILES_FILE,
    }
    missing_files = tuple(name for name, path in required_paths.items() if not path.exists())
    issue_samples: list[str] = [f"missing file: {name}" for name in missing_files]
    summary = _read_summary(required_paths[SUMMARY_FILE], issue_samples, max_issue_samples)
    expected_chunk_count = _summary_int(summary, "persistent_chunk_count") or _summary_int(
        summary,
        "chunk_count",
    )
    expected_embedding_count = _summary_int(summary, "embedding_count")
    expected_failed_file_count = _summary_int(summary, "failed_file_count")
    expected_pending_file_count = _summary_int(summary, "pending_file_count")
    expected_embedding_provider = _summary_str(summary, "embedding_provider")
    expected_embedding_model = _summary_str(summary, "embedding_model")
    expected_embedding_provider_version = _summary_str(summary, "embedding_provider_version")
    expected_embedding_dimension = _summary_int(summary, "embedding_dimension")

    chunk_stats = _scan_chunks(
        required_paths[CHUNKS_FILE],
        issue_samples=issue_samples,
        max_issue_samples=max_issue_samples,
    )
    embedding_stats = _scan_embeddings(
        required_paths[EMBEDDINGS_FILE],
        chunk_ids=chunk_stats.ids,
        expected_provider=expected_embedding_provider,
        expected_model=expected_embedding_model,
        expected_provider_version=expected_embedding_provider_version,
        expected_dimension=expected_embedding_dimension,
        issue_samples=issue_samples,
        max_issue_samples=max_issue_samples,
    )
    failed_file_row_count = _count_jsonl_rows(
        required_paths[FAILED_FILES_FILE],
        issue_samples=issue_samples,
        max_issue_samples=max_issue_samples,
    )
    pending_file_row_count = _count_jsonl_rows(
        required_paths[PENDING_FILES_FILE],
        issue_samples=issue_samples,
        max_issue_samples=max_issue_samples,
    )
    missing_embedding_count = len(chunk_stats.ids - embedding_stats.ids)
    if missing_embedding_count and len(issue_samples) < max_issue_samples:
        missing_sample = next(iter(chunk_stats.ids - embedding_stats.ids))
        issue_samples.append(f"chunk has no embedding: {missing_sample}")

    gates = _build_gates(
        missing_files=missing_files,
        expected_chunk_count=expected_chunk_count,
        expected_embedding_count=expected_embedding_count,
        expected_failed_file_count=expected_failed_file_count,
        expected_pending_file_count=expected_pending_file_count,
        expected_embedding_dimension=expected_embedding_dimension,
        schema_dimension=schema_dimension,
        chunk_row_count=chunk_stats.row_count,
        embedding_row_count=embedding_stats.row_count,
        failed_file_row_count=failed_file_row_count,
        pending_file_row_count=pending_file_row_count,
        duplicate_chunk_id_count=chunk_stats.duplicate_id_count,
        duplicate_embedding_chunk_id_count=embedding_stats.duplicate_id_count,
        missing_embedding_count=missing_embedding_count,
        orphan_embedding_count=embedding_stats.orphan_id_count,
        invalid_embedding_metadata_count=embedding_stats.invalid_metadata_count,
        invalid_embedding_dimension_count=embedding_stats.invalid_dimension_count,
    )
    return PgvectorImportPlan(
        index_root=root,
        summary=summary,
        expected_chunk_count=expected_chunk_count,
        expected_embedding_count=expected_embedding_count,
        expected_failed_file_count=expected_failed_file_count,
        expected_pending_file_count=expected_pending_file_count,
        expected_embedding_provider=expected_embedding_provider,
        expected_embedding_model=expected_embedding_model,
        expected_embedding_provider_version=expected_embedding_provider_version,
        expected_embedding_dimension=expected_embedding_dimension,
        schema_dimension=schema_dimension,
        chunk_row_count=chunk_stats.row_count,
        embedding_row_count=embedding_stats.row_count,
        failed_file_row_count=failed_file_row_count,
        pending_file_row_count=pending_file_row_count,
        duplicate_chunk_id_count=chunk_stats.duplicate_id_count,
        duplicate_embedding_chunk_id_count=embedding_stats.duplicate_id_count,
        missing_embedding_count=missing_embedding_count,
        orphan_embedding_count=embedding_stats.orphan_id_count,
        invalid_embedding_metadata_count=embedding_stats.invalid_metadata_count,
        invalid_embedding_dimension_count=embedding_stats.invalid_dimension_count,
        issue_samples=tuple(issue_samples[:max_issue_samples]),
        gates=gates,
    )


def render_pgvector_import_plan_markdown(plan: PgvectorImportPlan) -> str:
    report_date = datetime.now(UTC).date().isoformat()
    status = "PASS" if plan.ready_for_import else "FAIL"
    lines = [
        "---",
        "title: 知识库 pgvector 导入前校验报告",
        "doc_type: analysis",
        "module: knowledge-query-engine",
        "topic: pgvector-import-plan",
        "status: draft",
        f"created: {report_date}",
        f"updated: {report_date}",
        "owner: self",
        "source: ai",
        "---",
        "",
        "# 知识库 pgvector 导入前校验报告",
        "",
        f"总体状态：`{status}`",
        "",
        "## 1. 运行配置",
        "",
        "| 配置 | 值 |",
        "| --- | --- |",
        f"| `index_root` | `{plan.index_root}` |",
        f"| `schema_dimension` | `{plan.schema_dimension}` |",
        f"| `embedding_provider` | `{plan.expected_embedding_provider or 'unknown'}` |",
        f"| `embedding_model` | `{plan.expected_embedding_model or 'unknown'}` |",
        (
            "| `embedding_provider_version` | "
            f"`{plan.expected_embedding_provider_version or 'unknown'}` |"
        ),
        f"| `embedding_dimension` | `{plan.expected_embedding_dimension or 'unknown'}` |",
        "",
        "## 2. 行数校验",
        "",
        "| 资产 | 实际 | 预期 |",
        "| --- | ---: | ---: |",
        _metric_line("chunks.jsonl", plan.chunk_row_count, plan.expected_chunk_count),
        _metric_line("embeddings.jsonl", plan.embedding_row_count, plan.expected_embedding_count),
        _metric_line(
            "failed_files.jsonl",
            plan.failed_file_row_count,
            plan.expected_failed_file_count,
        ),
        _metric_line(
            "pending_files.jsonl",
            plan.pending_file_row_count,
            plan.expected_pending_file_count,
        ),
        "",
        "## 3. 一致性指标",
        "",
        "| 指标 | 数值 |",
        "| --- | ---: |",
        f"| `duplicate_chunk_id_count` | {plan.duplicate_chunk_id_count} |",
        f"| `duplicate_embedding_chunk_id_count` | {plan.duplicate_embedding_chunk_id_count} |",
        f"| `missing_embedding_count` | {plan.missing_embedding_count} |",
        f"| `orphan_embedding_count` | {plan.orphan_embedding_count} |",
        f"| `invalid_embedding_metadata_count` | {plan.invalid_embedding_metadata_count} |",
        f"| `invalid_embedding_dimension_count` | {plan.invalid_embedding_dimension_count} |",
        "",
        "## 4. 门禁",
        "",
        "| 门禁 | 状态 | 实际 | 预期 | 说明 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for gate in plan.gates:
        gate_status = "PASS" if gate.passed else "FAIL"
        lines.append(
            "| "
            f"`{gate.name}` | `{gate_status}` | "
            f"`{_json_cell(gate.actual)}` | `{_json_cell(gate.expected)}` | "
            f"{gate.description} |"
        )

    lines.extend(["", "## 5. 问题样例", ""])
    if not plan.issue_samples:
        lines.append("- 无")
    else:
        lines.extend(f"- {sample}" for sample in plan.issue_samples)
    lines.extend(["", "## 6. 下一步", "", _next_step_line(plan)])
    return "\n".join(lines) + "\n"


@dataclass(frozen=True, slots=True)
class _JsonlIdStats:
    row_count: int | None
    ids: set[str]
    duplicate_id_count: int


@dataclass(frozen=True, slots=True)
class _EmbeddingStats:
    row_count: int | None
    ids: set[str]
    duplicate_id_count: int
    orphan_id_count: int
    invalid_metadata_count: int
    invalid_dimension_count: int


def _build_gates(
    *,
    missing_files: tuple[str, ...],
    expected_chunk_count: int | None,
    expected_embedding_count: int | None,
    expected_failed_file_count: int | None,
    expected_pending_file_count: int | None,
    expected_embedding_dimension: int | None,
    schema_dimension: int,
    chunk_row_count: int | None,
    embedding_row_count: int | None,
    failed_file_row_count: int | None,
    pending_file_row_count: int | None,
    duplicate_chunk_id_count: int,
    duplicate_embedding_chunk_id_count: int,
    missing_embedding_count: int,
    orphan_embedding_count: int,
    invalid_embedding_metadata_count: int,
    invalid_embedding_dimension_count: int,
) -> tuple[PgvectorImportGate, ...]:
    return (
        PgvectorImportGate(
            name="required-files-present",
            passed=not missing_files,
            actual=list(missing_files),
            expected=[],
            description="导入所需 JSONL artifact 必须全部存在",
        ),
        PgvectorImportGate(
            name="schema-dimension-compatible",
            passed=expected_embedding_dimension == schema_dimension,
            actual=expected_embedding_dimension,
            expected=schema_dimension,
            description="summary.embedding_dimension 必须匹配 pgvector schema 维度",
        ),
        PgvectorImportGate(
            name="chunk-row-count",
            passed=chunk_row_count == expected_chunk_count,
            actual=chunk_row_count,
            expected=expected_chunk_count,
            description="chunks.jsonl 行数必须匹配 summary.persistent_chunk_count",
        ),
        PgvectorImportGate(
            name="embedding-row-count",
            passed=embedding_row_count == expected_embedding_count,
            actual=embedding_row_count,
            expected=expected_embedding_count,
            description="embeddings.jsonl 行数必须匹配 summary.embedding_count",
        ),
        PgvectorImportGate(
            name="failed-file-row-count",
            passed=failed_file_row_count == expected_failed_file_count,
            actual=failed_file_row_count,
            expected=expected_failed_file_count,
            description="failed_files.jsonl 行数必须匹配 summary.failed_file_count",
        ),
        PgvectorImportGate(
            name="pending-file-row-count",
            passed=pending_file_row_count == expected_pending_file_count,
            actual=pending_file_row_count,
            expected=expected_pending_file_count,
            description="pending_files.jsonl 行数必须匹配 summary.pending_file_count",
        ),
        PgvectorImportGate(
            name="unique-chunk-ids",
            passed=duplicate_chunk_id_count == 0,
            actual=duplicate_chunk_id_count,
            expected=0,
            description="chunks.jsonl 中 chunk_id 不允许重复",
        ),
        PgvectorImportGate(
            name="unique-embedding-chunk-ids",
            passed=duplicate_embedding_chunk_id_count == 0,
            actual=duplicate_embedding_chunk_id_count,
            expected=0,
            description="embeddings.jsonl 中 chunk_id 不允许重复",
        ),
        PgvectorImportGate(
            name="embedding-chunk-alignment",
            passed=missing_embedding_count == 0 and orphan_embedding_count == 0,
            actual={
                "missing_embedding_count": missing_embedding_count,
                "orphan_embedding_count": orphan_embedding_count,
            },
            expected={"missing_embedding_count": 0, "orphan_embedding_count": 0},
            description="每个 chunk 必须存在且仅存在一条对应 embedding",
        ),
        PgvectorImportGate(
            name="embedding-provider-metadata",
            passed=invalid_embedding_metadata_count == 0,
            actual=invalid_embedding_metadata_count,
            expected=0,
            description=(
                "embedding provider、model、provider_version、dimension 必须与 summary 一致"
            ),
        ),
        PgvectorImportGate(
            name="embedding-vector-dimension",
            passed=invalid_embedding_dimension_count == 0,
            actual=invalid_embedding_dimension_count,
            expected=0,
            description="每条 embedding 向量长度必须等于 summary.embedding_dimension",
        ),
    )


def _scan_chunks(
    path: Path,
    *,
    issue_samples: list[str],
    max_issue_samples: int,
) -> _JsonlIdStats:
    if not path.exists():
        return _JsonlIdStats(row_count=None, ids=set(), duplicate_id_count=0)
    ids: set[str] = set()
    duplicate_id_count = 0
    row_count = 0
    for row_number, row in _read_jsonl(path, issue_samples, max_issue_samples):
        row_count += 1
        chunk_id = _string_value(row.get("chunk_id"))
        if chunk_id is None:
            _append_issue(
                issue_samples,
                max_issue_samples,
                f"{path.name}:{row_number} missing chunk_id",
            )
            continue
        if chunk_id in ids:
            duplicate_id_count += 1
            _append_issue(
                issue_samples,
                max_issue_samples,
                f"{path.name}:{row_number} duplicate chunk_id {chunk_id}",
            )
        ids.add(chunk_id)
    return _JsonlIdStats(
        row_count=row_count,
        ids=ids,
        duplicate_id_count=duplicate_id_count,
    )


def _scan_embeddings(
    path: Path,
    *,
    chunk_ids: set[str],
    expected_provider: str | None,
    expected_model: str | None,
    expected_provider_version: str | None,
    expected_dimension: int | None,
    issue_samples: list[str],
    max_issue_samples: int,
) -> _EmbeddingStats:
    if not path.exists():
        return _EmbeddingStats(
            row_count=None,
            ids=set(),
            duplicate_id_count=0,
            orphan_id_count=0,
            invalid_metadata_count=0,
            invalid_dimension_count=0,
        )
    ids: set[str] = set()
    duplicate_id_count = 0
    orphan_id_count = 0
    invalid_metadata_count = 0
    invalid_dimension_count = 0
    row_count = 0
    for row_number, row in _read_jsonl(path, issue_samples, max_issue_samples):
        row_count += 1
        chunk_id = _string_value(row.get("chunk_id"))
        if chunk_id is None:
            _append_issue(
                issue_samples,
                max_issue_samples,
                f"{path.name}:{row_number} missing chunk_id",
            )
            invalid_metadata_count += 1
        elif chunk_id in ids:
            duplicate_id_count += 1
            _append_issue(
                issue_samples,
                max_issue_samples,
                f"{path.name}:{row_number} duplicate chunk_id {chunk_id}",
            )
        elif chunk_id not in chunk_ids:
            orphan_id_count += 1
            _append_issue(
                issue_samples,
                max_issue_samples,
                f"{path.name}:{row_number} embedding chunk_id not found in chunks {chunk_id}",
            )
        if chunk_id is not None:
            ids.add(chunk_id)

        if not _embedding_metadata_matches(
            row,
            expected_provider=expected_provider,
            expected_model=expected_model,
            expected_provider_version=expected_provider_version,
            expected_dimension=expected_dimension,
        ):
            invalid_metadata_count += 1
            _append_issue(
                issue_samples,
                max_issue_samples,
                f"{path.name}:{row_number} embedding metadata mismatch",
            )

        embedding = row.get("embedding")
        if not isinstance(embedding, list) or len(embedding) != expected_dimension:
            invalid_dimension_count += 1
            _append_issue(
                issue_samples,
                max_issue_samples,
                f"{path.name}:{row_number} embedding vector dimension mismatch",
            )
    return _EmbeddingStats(
        row_count=row_count,
        ids=ids,
        duplicate_id_count=duplicate_id_count,
        orphan_id_count=orphan_id_count,
        invalid_metadata_count=invalid_metadata_count,
        invalid_dimension_count=invalid_dimension_count,
    )


def _count_jsonl_rows(
    path: Path,
    *,
    issue_samples: list[str],
    max_issue_samples: int,
) -> int | None:
    if not path.exists():
        return None
    return sum(1 for _row_number, _row in _read_jsonl(path, issue_samples, max_issue_samples))


def _read_summary(
    path: Path,
    issue_samples: list[str],
    max_issue_samples: int,
) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        _append_issue(issue_samples, max_issue_samples, f"{path.name} invalid JSON: {exc}")
        return {}
    if not isinstance(payload, dict):
        _append_issue(issue_samples, max_issue_samples, f"{path.name} root must be object")
        return {}
    return dict(payload)


def _read_jsonl(
    path: Path,
    issue_samples: list[str],
    max_issue_samples: int,
) -> Iterator[tuple[int, dict[str, object]]]:
    with path.open(encoding="utf-8") as file:
        for row_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                _append_issue(
                    issue_samples,
                    max_issue_samples,
                    f"{path.name}:{row_number} invalid JSON: {exc}",
                )
                continue
            if not isinstance(payload, dict):
                _append_issue(
                    issue_samples,
                    max_issue_samples,
                    f"{path.name}:{row_number} row must be object",
                )
                continue
            yield row_number, payload


def _embedding_metadata_matches(
    row: dict[str, object],
    *,
    expected_provider: str | None,
    expected_model: str | None,
    expected_provider_version: str | None,
    expected_dimension: int | None,
) -> bool:
    if expected_provider is None or expected_model is None or expected_provider_version is None:
        return False
    return (
        row.get("provider") == expected_provider
        and row.get("model_name") == expected_model
        and row.get("provider_version") == expected_provider_version
        and row.get("dimension") == expected_dimension
    )


def _summary_int(summary: dict[str, object], key: str) -> int | None:
    value = summary.get(key)
    return value if isinstance(value, int) else None


def _summary_str(summary: dict[str, object], key: str) -> str | None:
    value = summary.get(key)
    return value if isinstance(value, str) and value else None


def _string_value(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _append_issue(samples: list[str], max_issue_samples: int, issue: str) -> None:
    if len(samples) < max_issue_samples:
        samples.append(issue)


def _metric_line(label: str, actual: int | None, expected: int | None) -> str:
    return f"| `{label}` | {_format_optional_int(actual)} | {_format_optional_int(expected)} |"


def _format_optional_int(value: int | None) -> str:
    return "unknown" if value is None else str(value)


def _json_cell(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _next_step_line(plan: PgvectorImportPlan) -> str:
    if plan.ready_for_import:
        return "结论：导入前校验通过，可以进入 PostgreSQL 写入脚本或受控导入执行。"
    return "结论：导入前校验未通过，先修复失败门禁，不允许写入 PostgreSQL。"
