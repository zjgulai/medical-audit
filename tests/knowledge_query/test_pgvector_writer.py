from __future__ import annotations

import json
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from medical_audit_kb.indexing.pgvector_writer import (
    build_pgvector_import_manifest,
    run_pgvector_import,
    write_pgvector_import_to_cursor,
)


def test_build_pgvector_import_manifest_prepares_source_metadata(
    tmp_path: Path,
) -> None:
    index_root, source_root = _write_index_and_source_artifacts(tmp_path)

    manifest = build_pgvector_import_manifest(
        index_root,
        source_root,
        schema_dimension=2,
    )

    assert manifest.ready_for_write is True
    assert manifest.source_document_count == 1
    assert manifest.document_chunk_count == 2
    assert manifest.chunk_embedding_count == 2
    assert manifest.pending_file_count == 1
    assert manifest.source_file_missing_count == 0
    assert manifest.invalid_source_metadata_count == 0


def test_build_pgvector_import_manifest_blocks_missing_source_file(
    tmp_path: Path,
) -> None:
    index_root, source_root = _write_index_and_source_artifacts(tmp_path)
    (source_root / "全量法律" / "医保政策.md").unlink()

    manifest = build_pgvector_import_manifest(
        index_root,
        source_root,
        schema_dimension=2,
    )

    assert manifest.ready_for_write is False
    assert manifest.source_file_missing_count == 1
    assert "source file not found" in "\n".join(manifest.issue_samples)


def test_run_pgvector_import_dry_run_does_not_execute_database_write(
    tmp_path: Path,
) -> None:
    index_root, source_root = _write_index_and_source_artifacts(tmp_path)

    result = run_pgvector_import(
        index_root,
        source_root,
        execute=False,
        schema_dimension=2,
    )

    assert result.mode == "dry-run"
    assert result.executed is False
    assert result.success is True
    assert result.manifest.ready_for_write is True


def test_write_pgvector_import_to_cursor_writes_expected_batches(
    tmp_path: Path,
) -> None:
    index_root, source_root = _write_index_and_source_artifacts(tmp_path)
    manifest = build_pgvector_import_manifest(
        index_root,
        source_root,
        schema_dimension=2,
    )
    cursor = RecordingCursor()

    write_pgvector_import_to_cursor(cursor, manifest, batch_size=1)

    assert cursor.execute_count == 3
    assert cursor.executemany_row_counts["source_documents"] == 1
    assert cursor.executemany_row_counts["document_chunks"] == 2
    assert cursor.executemany_row_counts["chunk_embeddings"] == 2
    assert cursor.executemany_row_counts["pending_files"] == 1
    assert cursor.execute_params_by_table["index_versions"][0][3] == "candidate"


class RecordingCursor:
    def __init__(self) -> None:
        self.execute_count = 0
        self.executemany_row_counts: Counter[str] = Counter()
        self.execute_params_by_table: dict[str, list[tuple[object, ...]]] = {}

    def execute(self, query: str, params: tuple[object, ...] | None = None) -> object:
        self.execute_count += 1
        table_name = _insert_table_name(query)
        self.execute_params_by_table.setdefault(table_name, []).append(params or ())
        return None

    def executemany(
        self,
        query: str,
        params_seq: Sequence[tuple[object, ...]],
    ) -> object:
        table_name = _insert_table_name(query)
        self.executemany_row_counts[table_name] += len(params_seq)
        return None


def _write_index_and_source_artifacts(tmp_path: Path) -> tuple[Path, Path]:
    source_root = tmp_path / "source"
    _write_text(source_root / "全量法律" / "医保政策.md", "第一条 医保审核依据。")
    index_root = tmp_path / "index"
    index_root.mkdir()
    _write_json(
        index_root / "summary.json",
        {
            "job_type": "full-rebuild",
            "index_version_key": "full-rebuild-test",
            "source_package_version_key": "source-package-test",
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
            _chunk_row("chunk-00000000-0000-0000-0000-000000000001", "第一条"),
            _chunk_row("chunk-00000000-0000-0000-0000-000000000002", "第二条"),
        ],
    )
    _write_jsonl(
        index_root / "embeddings.jsonl",
        [
            _embedding_row("00000000-0000-0000-0000-000000000001", [1.0, 0.0]),
            _embedding_row("00000000-0000-0000-0000-000000000002", [0.0, 1.0]),
        ],
    )
    _write_jsonl(index_root / "failed_files.jsonl", [])
    _write_jsonl(
        index_root / "pending_files.jsonl",
        [{"relative_path": "扫描件.pdf", "error_type": "unsupported-type"}],
    )
    return index_root, source_root


def _chunk_row(chunk_id: str, text: str) -> dict[str, object]:
    return {
        "chunk_id": chunk_id.replace("chunk-", ""),
        "text": text,
        "metadata": {
            "source_collection": "medical-insurance-laws",
            "source_path": "全量法律/医保政策.md",
            "title_path": ["总则"],
            "line_start": 1,
            "line_end": 1,
        },
        "locator": {"type": "markdown", "source_path": "全量法律/医保政策.md"},
        "source_path": "全量法律/医保政策.md",
    }


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


def _insert_table_name(query: str) -> str:
    normalized = " ".join(query.split())
    return normalized.split("INSERT INTO ", maxsplit=1)[1].split(" ", maxsplit=1)[0]


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
