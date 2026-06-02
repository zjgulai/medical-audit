from __future__ import annotations

import json
from pathlib import Path

from medical_audit_kb.indexing.pgvector_import import (
    PgvectorImportPlan,
    build_pgvector_import_plan,
)


def test_build_pgvector_import_plan_passes_matching_artifacts(tmp_path: Path) -> None:
    index_root = _write_index_artifacts(tmp_path)

    plan = build_pgvector_import_plan(index_root, schema_dimension=2)

    assert plan.ready_for_import is True
    assert plan.chunk_row_count == 2
    assert plan.embedding_row_count == 2
    assert plan.failed_file_row_count == 0
    assert plan.pending_file_row_count == 1
    assert plan.missing_embedding_count == 0
    assert plan.orphan_embedding_count == 0
    assert plan.invalid_embedding_dimension_count == 0


def test_build_pgvector_import_plan_fails_on_schema_dimension_mismatch(
    tmp_path: Path,
) -> None:
    index_root = _write_index_artifacts(tmp_path)

    plan = build_pgvector_import_plan(index_root, schema_dimension=1024)

    assert plan.ready_for_import is False
    assert _gate_status(plan, "schema-dimension-compatible") is False
    assert plan.expected_embedding_dimension == 2
    assert plan.schema_dimension == 1024


def test_build_pgvector_import_plan_fails_on_embedding_alignment_error(
    tmp_path: Path,
) -> None:
    index_root = _write_index_artifacts(
        tmp_path,
        embeddings=[
            _embedding_row("chunk-1", [1.0, 0.0]),
            _embedding_row("orphan-chunk", [0.0, 1.0]),
        ],
    )

    plan = build_pgvector_import_plan(index_root, schema_dimension=2)

    assert plan.ready_for_import is False
    assert _gate_status(plan, "embedding-chunk-alignment") is False
    assert plan.missing_embedding_count == 1
    assert plan.orphan_embedding_count == 1
    assert "orphan-chunk" in "\n".join(plan.issue_samples)


def test_build_pgvector_import_plan_fails_on_vector_dimension_error(
    tmp_path: Path,
) -> None:
    index_root = _write_index_artifacts(
        tmp_path,
        embeddings=[
            _embedding_row("chunk-1", [1.0, 0.0]),
            _embedding_row("chunk-2", [0.0, 1.0, 0.0]),
        ],
    )

    plan = build_pgvector_import_plan(index_root, schema_dimension=2)

    assert plan.ready_for_import is False
    assert _gate_status(plan, "embedding-vector-dimension") is False
    assert plan.invalid_embedding_dimension_count == 1


def _write_index_artifacts(
    tmp_path: Path,
    *,
    embeddings: list[dict[str, object]] | None = None,
) -> Path:
    index_root = tmp_path / "index"
    index_root.mkdir()
    _write_json(
        index_root / "summary.json",
        {
            "persistent_chunk_count": 2,
            "embedding_count": 2,
            "failed_file_count": 0,
            "pending_file_count": 1,
            "embedding_provider": "openai",
            "embedding_model": "kimi-for-coding",
            "embedding_provider_version": "v1",
            "embedding_dimension": 2,
        },
    )
    _write_jsonl(
        index_root / "chunks.jsonl",
        [
            {"chunk_id": "chunk-1", "text": "第一条 医保审核依据。"},
            {"chunk_id": "chunk-2", "text": "第二条 医保审核流程。"},
        ],
    )
    _write_jsonl(
        index_root / "embeddings.jsonl",
        embeddings
        or [
            _embedding_row("chunk-1", [1.0, 0.0]),
            _embedding_row("chunk-2", [0.0, 1.0]),
        ],
    )
    _write_jsonl(index_root / "failed_files.jsonl", [])
    _write_jsonl(
        index_root / "pending_files.jsonl",
        [{"relative_path": "扫描件.pdf", "error_type": "unsupported_media"}],
    )
    return index_root


def _embedding_row(chunk_id: str, embedding: list[float]) -> dict[str, object]:
    return {
        "chunk_id": chunk_id,
        "text": "医保审核依据",
        "embedding": embedding,
        "provider": "openai",
        "model_name": "kimi-for-coding",
        "provider_version": "v1",
        "dimension": 2,
        "metadata": {},
    }


def _gate_status(plan: PgvectorImportPlan, name: str) -> bool:
    return next(gate.passed for gate in plan.gates if gate.name == name)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")
