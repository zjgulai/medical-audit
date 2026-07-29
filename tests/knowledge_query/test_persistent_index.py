import json
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from medical_audit_kb.indexing.embeddings import EmbeddingVector
from medical_audit_kb.indexing.persistent_index import (
    BM25_DOCUMENTS_FILE,
    CHUNKS_FILE,
    EMBEDDINGS_FILE,
    SUMMARY_FILE,
    build_persistent_index,
    load_material_question_seeds,
    load_persistent_search_engine,
)


def test_build_persistent_index_writes_artifacts_and_loads_search_engine(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "医保审核前期资料"
    _write_text(
        source_root / "全量法律" / "医保基金监管条例.md",
        "第一条 医疗机构应当保留医保基金审核依据。",
    )
    _write_text(
        source_root / "风险负面清单" / "risk.md",
        "第一条 城市卫生管理要求。",
    )
    _write_text(
        source_root / "智能监管“两库”规则和知识点" / "rules.md",
        "规则编码: R001\n规则名称: 超量开药\n说明: 医保处方超过限定数量。",
    )
    index_root = tmp_path / "index"

    result = build_persistent_index(
        source_root,
        index_root,
        package_version_key="package-test",
    )
    search_engine = load_persistent_search_engine(index_root)
    search_results = search_engine.search("医保基金审核依据", top_k=3)
    seeds = load_material_question_seeds(index_root, max_cases=5, query_terms=("医保",))

    assert result.summary["source_package_version_key"] == "package-test"
    assert result.chunk_count == 3
    assert result.embedding_count == 3
    assert result.bm25_document_count == 3
    assert (index_root / SUMMARY_FILE).exists()
    assert (index_root / CHUNKS_FILE).exists()
    assert (index_root / EMBEDDINGS_FILE).exists()
    assert (index_root / BM25_DOCUMENTS_FILE).exists()
    assert search_results
    assert search_results[0].chunk.metadata["source_package_version_key"] == "package-test"
    assert seeds[0].source_path == "智能监管“两库”规则和知识点/rules.md"
    assert seeds[1].source_path == "全量法律/医保基金监管条例.md"
    assert len(seeds) == 2


def test_build_persistent_index_respects_max_chunks(tmp_path: Path) -> None:
    source_root = tmp_path / "医保审核前期资料"
    _write_text(source_root / "全量法律" / "医保政策A.md", "第一条 医保审核依据。")
    _write_text(source_root / "全量法律" / "医保政策B.md", "第二条 医保审核流程。")
    index_root = tmp_path / "index"

    result = build_persistent_index(
        source_root,
        index_root,
        package_version_key="package-test",
        max_chunks=1,
    )

    assert result.summary["persistent_source_chunk_count"] == 1
    assert result.summary["persistent_chunk_limit"] == 1
    assert result.chunk_count == 1
    assert result.embedding_count == 1
    assert result.bm25_document_count == 1


def test_build_persistent_index_resume_reuses_existing_embeddings(tmp_path: Path) -> None:
    source_root = tmp_path / "医保审核前期资料"
    _write_text(source_root / "全量法律" / "医保政策A.md", "第一条 医保审核依据。")
    _write_text(source_root / "全量法律" / "医保政策B.md", "第二条 医保审核流程。")
    index_root = tmp_path / "index"
    first_provider = CountingEmbeddingProvider()
    second_provider = CountingEmbeddingProvider()

    first_result = build_persistent_index(
        source_root,
        index_root,
        package_version_key="package-test",
        embedding_provider=first_provider,
        max_chunks=1,
    )
    second_result = build_persistent_index(
        source_root,
        index_root,
        package_version_key="package-test",
        embedding_provider=second_provider,
        max_chunks=2,
        resume=True,
    )

    assert first_result.embedding_count == 1
    assert first_provider.embedded_text_count == 1
    assert second_result.embedding_count == 2
    assert second_result.summary["embedding_reused_count"] == 1
    assert second_result.summary["embedding_created_count"] == 1
    assert second_result.summary["embedding_resume_enabled"] is True
    assert second_provider.embedded_text_count == 1


def test_build_persistent_index_resume_repairs_invalid_trailing_embedding_line(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "医保审核前期资料"
    _write_text(source_root / "全量法律" / "医保政策A.md", "第一条 医保审核依据。")
    _write_text(source_root / "全量法律" / "医保政策B.md", "第二条 医保审核流程。")
    index_root = tmp_path / "index"
    first_provider = CountingEmbeddingProvider()
    second_provider = CountingEmbeddingProvider()

    build_persistent_index(
        source_root,
        index_root,
        package_version_key="package-test",
        embedding_provider=first_provider,
        max_chunks=1,
    )
    with (index_root / EMBEDDINGS_FILE).open("a", encoding="utf-8") as file:
        file.write('{"chunk_id": "partial"')

    second_result = build_persistent_index(
        source_root,
        index_root,
        package_version_key="package-test",
        embedding_provider=second_provider,
        max_chunks=2,
        resume=True,
    )
    embedding_rows = _read_jsonl_objects(index_root / EMBEDDINGS_FILE)

    assert second_result.embedding_count == 2
    assert second_result.summary["embedding_reused_count"] == 1
    assert second_result.summary["embedding_created_count"] == 1
    assert second_provider.embedded_text_count == 1
    assert len(embedding_rows) == 2


def test_build_persistent_index_resume_removes_stale_rows_when_current_rows_remain(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "医保审核前期资料"
    _write_text(source_root / "全量法律" / "医保政策A.md", "第一条 医保审核依据。")
    _write_text(source_root / "全量法律" / "医保政策B.md", "第二条 医保审核流程。")
    index_root = tmp_path / "index"
    first_provider = CountingEmbeddingProvider()
    second_provider = CountingEmbeddingProvider()

    build_persistent_index(
        source_root,
        index_root,
        package_version_key="package-test",
        embedding_provider=first_provider,
        max_chunks=2,
    )
    second_result = build_persistent_index(
        source_root,
        index_root,
        package_version_key="package-test",
        embedding_provider=second_provider,
        max_chunks=1,
        resume=True,
    )
    embedding_rows = _read_jsonl_objects(index_root / EMBEDDINGS_FILE)

    assert second_result.embedding_count == 1
    assert second_result.summary["embedding_reused_count"] == 1
    assert second_result.summary["embedding_created_count"] == 0
    assert second_provider.embedded_text_count == 0
    assert len(embedding_rows) == 1


def test_build_persistent_index_resume_rewrites_rows_for_provider_change(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "医保审核前期资料"
    _write_text(source_root / "全量法律" / "医保政策A.md", "第一条 医保审核依据。")
    index_root = tmp_path / "index"
    first_provider = CountingEmbeddingProvider()
    second_provider = AlternateCountingEmbeddingProvider()

    build_persistent_index(
        source_root,
        index_root,
        package_version_key="package-test",
        embedding_provider=first_provider,
    )
    second_result = build_persistent_index(
        source_root,
        index_root,
        package_version_key="package-test",
        embedding_provider=second_provider,
        resume=True,
    )
    embedding_rows = _read_jsonl_objects(index_root / EMBEDDINGS_FILE)

    assert second_result.embedding_count == 1
    assert second_result.summary["embedding_reused_count"] == 0
    assert second_result.summary["embedding_created_count"] == 1
    assert second_provider.embedded_text_count == 1
    assert len(embedding_rows) == 1
    assert embedding_rows[0]["provider_version"] == "v2"


def test_build_persistent_index_uses_package_aware_chunk_ids(tmp_path: Path) -> None:
    source_root = tmp_path / "医保审核前期资料"
    _write_text(source_root / "全量法律" / "医保政策A.md", "第一条 医保审核依据。")
    first_index_root = tmp_path / "index-a"
    second_index_root = tmp_path / "index-b"

    build_persistent_index(
        source_root,
        first_index_root,
        package_version_key="package-a",
        embedding_provider=CountingEmbeddingProvider(),
    )
    build_persistent_index(
        source_root,
        second_index_root,
        package_version_key="package-b",
        embedding_provider=CountingEmbeddingProvider(),
    )

    first_chunk = _read_first_jsonl(first_index_root / CHUNKS_FILE)
    second_chunk = _read_first_jsonl(second_index_root / CHUNKS_FILE)
    first_metadata = cast(dict[str, object], first_chunk["metadata"])
    second_metadata = cast(dict[str, object], second_chunk["metadata"])
    assert first_chunk["chunk_id"] != second_chunk["chunk_id"]
    assert first_metadata["source_package_version_key"] == "package-a"
    assert second_metadata["source_package_version_key"] == "package-b"


def test_build_persistent_index_resume_reuses_vectors_across_package_versions(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "医保审核前期资料"
    _write_text(source_root / "全量法律" / "医保政策A.md", "第一条 医保审核依据。")
    index_root = tmp_path / "index"
    first_provider = CountingEmbeddingProvider()
    second_provider = CountingEmbeddingProvider()

    first_result = build_persistent_index(
        source_root,
        index_root,
        package_version_key="package-a",
        embedding_provider=first_provider,
    )
    first_embedding = _read_first_jsonl(index_root / EMBEDDINGS_FILE)
    second_result = build_persistent_index(
        source_root,
        index_root,
        package_version_key="package-b",
        embedding_provider=second_provider,
        resume=True,
    )
    second_embedding = _read_first_jsonl(index_root / EMBEDDINGS_FILE)

    assert first_result.embedding_count == 1
    assert second_result.embedding_count == 1
    assert second_result.summary["embedding_reused_count"] == 1
    assert second_result.summary["embedding_created_count"] == 0
    assert second_provider.embedded_text_count == 0
    assert first_embedding["chunk_id"] != second_embedding["chunk_id"]
    assert first_embedding["embedding"] == second_embedding["embedding"]
    second_metadata = cast(dict[str, object], second_embedding["metadata"])
    assert second_metadata["source_package_version_key"] == "package-b"


class CountingEmbeddingProvider:
    provider = "test"
    model_name = "counting"
    provider_version = "v1"
    dimension = 2
    batch_size = 1

    def __init__(self) -> None:
        self.embedded_text_count = 0

    def embed_texts(self, texts: Sequence[str]) -> tuple[EmbeddingVector, ...]:
        self.embedded_text_count += len(texts)
        return tuple((float(index + 1), 0.0) for index, _text in enumerate(texts))


class AlternateCountingEmbeddingProvider(CountingEmbeddingProvider):
    provider_version = "v2"


def _write_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _read_first_jsonl(path: Path) -> dict[str, object]:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            payload = json.loads(line)
            assert isinstance(payload, dict)
            return cast(dict[str, object], payload)
    raise AssertionError(f"empty jsonl file: {path}")


def _read_jsonl_objects(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            payload = json.loads(line)
            assert isinstance(payload, dict)
            rows.append(cast(dict[str, object], payload))
    return rows
