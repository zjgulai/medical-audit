from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast
from uuid import UUID, uuid5

from medical_audit_kb.domain.constants import SourceCollection
from medical_audit_kb.domain.schemas import DocumentChunkCreate
from medical_audit_kb.evaluation.datasets import MaterialQuestionSeed
from medical_audit_kb.indexing.bm25_index import BM25Document, InMemoryBM25Index
from medical_audit_kb.indexing.embeddings import (
    DeterministicFakeEmbeddingProvider,
    EmbeddingProvider,
    EmbeddingVector,
)
from medical_audit_kb.indexing.vector_index import (
    ChunkEmbeddingInput,
    ChunkEmbeddingRecord,
    InMemoryVectorIndex,
)
from medical_audit_kb.ingestion.pipeline import KnowledgeIndexPipeline, PipelineFileIssue
from medical_audit_kb.retrieval.hybrid_search import HybridSearchEngine
from medical_audit_kb.retrieval.rerank import FakeRerankProvider, RerankProvider

PERSISTENT_CHUNK_NAMESPACE = UUID("7e3c76e3-10a8-4a48-bfbc-7c7f5f9e9a31")
SUMMARY_FILE = "summary.json"
CHUNKS_FILE = "chunks.jsonl"
EMBEDDINGS_FILE = "embeddings.jsonl"
BM25_DOCUMENTS_FILE = "bm25_documents.jsonl"
FAILED_FILES_FILE = "failed_files.jsonl"
PENDING_FILES_FILE = "pending_files.jsonl"
SOURCE_COLLECTION_SEED_PRIORITY: dict[SourceCollection, int] = {
    SourceCollection.SUPERVISION_RULES_KNOWLEDGE: 0,
    SourceCollection.MEDICAL_INSURANCE_CATALOG: 1,
    SourceCollection.RISK_NEGATIVE_LIST: 2,
    SourceCollection.MEDICAL_INSURANCE_LAWS: 3,
}


@dataclass(frozen=True, slots=True)
class PersistentIndexBuildResult:
    index_root: Path
    summary: dict[str, object]
    chunk_count: int
    embedding_count: int
    bm25_document_count: int


@dataclass(frozen=True, slots=True)
class PersistentEmbeddingWriteResult:
    embedding_count: int
    reused_count: int
    created_count: int


def build_persistent_index(
    source_root: Path | str,
    index_root: Path | str,
    *,
    package_version_key: str | None = None,
    embedding_provider: EmbeddingProvider | None = None,
    max_chunks: int | None = None,
    resume: bool = False,
) -> PersistentIndexBuildResult:
    if max_chunks is not None and max_chunks <= 0:
        raise ValueError("max_chunks must be positive")
    provider = embedding_provider or cast(EmbeddingProvider, DeterministicFakeEmbeddingProvider())
    destination = Path(index_root)
    destination.mkdir(parents=True, exist_ok=True)
    run_result = KnowledgeIndexPipeline().run_full_rebuild(
        source_root,
        package_version_key=package_version_key,
        max_chunks=max_chunks,
    )
    all_chunk_inputs = tuple(
        _chunk_embedding_input(chunk, run_result.summary.to_dict())
        for file_result in run_result.file_results
        for chunk in file_result.chunks
    )
    chunk_inputs = all_chunk_inputs[:max_chunks] if max_chunks is not None else all_chunk_inputs
    bm25_documents = tuple(
        BM25Document(
            chunk_id=chunk.chunk_id,
            text=chunk.text,
            metadata=chunk.metadata,
        )
        for chunk in chunk_inputs
    )
    _write_jsonl(
        destination / CHUNKS_FILE,
        (_chunk_record_payload(chunk) for chunk in chunk_inputs),
    )
    _write_jsonl(
        destination / BM25_DOCUMENTS_FILE,
        (_bm25_document_payload(document) for document in bm25_documents),
    )
    _write_jsonl(
        destination / FAILED_FILES_FILE,
        (_issue_payload(issue) for issue in run_result.failed_files),
    )
    _write_jsonl(
        destination / PENDING_FILES_FILE,
        (_issue_payload(issue) for issue in run_result.pending_files),
    )
    embedding_result = _write_embedding_records(
        destination / EMBEDDINGS_FILE,
        chunk_inputs,
        provider=provider,
        resume=resume,
    )
    summary = {
        **run_result.summary.to_dict(),
        "persistent_source_chunk_count": len(all_chunk_inputs),
        "persistent_chunk_count": len(chunk_inputs),
        "persistent_chunk_limit": max_chunks,
        "embedding_count": embedding_result.embedding_count,
        "embedding_reused_count": embedding_result.reused_count,
        "embedding_created_count": embedding_result.created_count,
        "embedding_resume_enabled": resume,
        "bm25_document_count": len(bm25_documents),
        "embedding_provider": provider.provider,
        "embedding_model": provider.model_name,
        "embedding_provider_version": provider.provider_version,
        "embedding_dimension": provider.dimension,
    }
    _write_json(destination / SUMMARY_FILE, summary)
    return PersistentIndexBuildResult(
        index_root=destination,
        summary=summary,
        chunk_count=len(chunk_inputs),
        embedding_count=embedding_result.embedding_count,
        bm25_document_count=len(bm25_documents),
    )


def load_persistent_search_engine(
    index_root: Path | str,
    *,
    embedding_provider: EmbeddingProvider | None = None,
) -> HybridSearchEngine:
    root = Path(index_root)
    summary = _read_json(root / SUMMARY_FILE)
    provider = embedding_provider or cast(
        EmbeddingProvider,
        DeterministicFakeEmbeddingProvider(
            dimension=_int_from_summary(summary, "embedding_dimension"),
        ),
    )
    vector_index = InMemoryVectorIndex(dimension=provider.dimension)
    vector_index.upsert(
        tuple(_embedding_record(row) for row in _read_jsonl(root / EMBEDDINGS_FILE))
    )
    bm25_index = InMemoryBM25Index()
    bm25_index.upsert(tuple(_bm25_document(row) for row in _read_jsonl(root / BM25_DOCUMENTS_FILE)))
    return HybridSearchEngine(
        embedding_provider=provider,
        vector_index=vector_index,
        bm25_index=bm25_index,
        rerank_provider=cast(RerankProvider, FakeRerankProvider()),
    )


def load_material_question_seeds(
    index_root: Path | str,
    *,
    max_cases: int,
    query_terms: tuple[str, ...] = (),
) -> tuple[MaterialQuestionSeed, ...]:
    root = Path(index_root)
    rows = tuple(
        row for row in _read_jsonl(root / CHUNKS_FILE) if _matches_query_terms(row, query_terms)
    )
    prioritized = sorted(
        rows,
        key=lambda row: (
            _source_priority(row),
            -_query_term_match_count(row, query_terms),
            0 if _article_or_rule_hint(row) else 1,
            str(row.get("source_path", "")),
        ),
    )
    seeds: list[MaterialQuestionSeed] = []
    for row in prioritized:
        if len(seeds) >= max_cases:
            break
        source_collection = _source_collection(row)
        source_path = str(row.get("source_path", ""))
        if source_collection is None or not source_path:
            continue
        seeds.append(
            MaterialQuestionSeed(
                source_collection=source_collection,
                source_path=source_path,
                title=Path(source_path).stem,
                text=str(row.get("text", "")),
                locator=_object_dict(row.get("locator")),
                tags=("persistent-index",),
            )
        )
    return tuple(seeds)


def _chunk_embedding_input(
    chunk: DocumentChunkCreate,
    summary: dict[str, object],
) -> ChunkEmbeddingInput:
    source_package_version_key = str(summary["source_package_version_key"])
    chunk_id = _chunk_id(chunk, source_package_version_key=source_package_version_key)
    metadata = {
        **chunk.metadata,
        "locator": chunk.locator,
        "source_path": str(chunk.locator.get("source_path", "")),
        "index_version_key": str(summary["index_version_key"]),
        "source_package_version_key": source_package_version_key,
        "title_path": chunk.title_path,
        "article_number": chunk.article_number,
        "page_number": chunk.page_number,
        "line_start": chunk.line_start,
        "line_end": chunk.line_end,
        "sheet_name": chunk.sheet_name,
        "row_number": chunk.row_number,
    }
    return ChunkEmbeddingInput(
        chunk_id=chunk_id,
        text=chunk.text,
        metadata=metadata,
    )


def _chunk_id(chunk: DocumentChunkCreate, *, source_package_version_key: str) -> UUID:
    return uuid5(
        PERSISTENT_CHUNK_NAMESPACE,
        f"{source_package_version_key}:{chunk.source_document_id}:{chunk.chunk_index}:{chunk.locator}",
    )


def _chunk_record_payload(chunk: ChunkEmbeddingInput) -> dict[str, object]:
    return {
        "chunk_id": str(chunk.chunk_id),
        "text": chunk.text,
        "metadata": chunk.metadata,
        "locator": chunk.metadata.get("locator", {}),
        "source_path": chunk.metadata.get("source_path", ""),
    }


def _embedding_record_payload(record: ChunkEmbeddingRecord) -> dict[str, object]:
    return {
        "chunk_id": str(record.chunk_id),
        "text": record.text,
        "embedding": list(record.embedding),
        "provider": record.provider,
        "model_name": record.model_name,
        "provider_version": record.provider_version,
        "dimension": record.dimension,
        "metadata": record.metadata,
    }


def _bm25_document_payload(document: BM25Document) -> dict[str, object]:
    return {
        "chunk_id": str(document.chunk_id),
        "text": document.text,
        "metadata": document.metadata,
    }


def _issue_payload(issue: PipelineFileIssue) -> dict[str, object]:
    return {
        "relative_path": issue.relative_path,
        "error_type": issue.error_type.value,
        "error_summary": issue.error_summary,
    }


def _write_embedding_records(
    path: Path,
    chunks: Sequence[ChunkEmbeddingInput],
    *,
    provider: EmbeddingProvider,
    resume: bool,
) -> PersistentEmbeddingWriteResult:
    reusable_vectors = _read_reusable_embedding_vectors(path, provider=provider) if resume else {}
    path.write_text("", encoding="utf-8")

    missing_chunks: list[ChunkEmbeddingInput] = []
    reused_count = 0
    created_count = 0
    with path.open("a", encoding="utf-8") as file:
        for chunk in chunks:
            reusable_vector = reusable_vectors.get(chunk.text)
            if reusable_vector is None:
                missing_chunks.append(chunk)
                continue
            file.write(
                json.dumps(
                    _embedding_record_payload(
                        ChunkEmbeddingRecord(
                            chunk_id=chunk.chunk_id,
                            text=chunk.text,
                            embedding=reusable_vector,
                            provider=provider.provider,
                            model_name=provider.model_name,
                            provider_version=provider.provider_version,
                            dimension=provider.dimension,
                            metadata=chunk.metadata,
                        )
                    ),
                    ensure_ascii=False,
                )
                + "\n"
            )
            reused_count += 1
        for batch in _chunk_batches(missing_chunks, _provider_batch_size_hint(provider)):
            records = _embedding_records_for_chunks(batch, provider=provider)
            for record in records:
                file.write(json.dumps(_embedding_record_payload(record), ensure_ascii=False) + "\n")
            created_count += len(records)

    return PersistentEmbeddingWriteResult(
        embedding_count=reused_count + created_count,
        reused_count=reused_count,
        created_count=created_count,
    )


def _read_reusable_embedding_vectors(
    path: Path,
    *,
    provider: EmbeddingProvider,
) -> dict[str, EmbeddingVector]:
    if not path.exists():
        return {}

    reusable_vectors: dict[str, EmbeddingVector] = {}
    for row in _read_jsonl(path):
        if not _embedding_row_matches_provider(row, provider):
            continue
        text = row.get("text")
        embedding = row.get("embedding")
        if not isinstance(text, str) or not isinstance(embedding, list):
            continue
        reusable_vectors.setdefault(text, tuple(float(value) for value in embedding))
    return reusable_vectors


def _embedding_row_matches_provider(
    row: dict[str, object],
    provider: EmbeddingProvider,
) -> bool:
    return (
        row.get("provider") == provider.provider
        and row.get("model_name") == provider.model_name
        and row.get("provider_version") == provider.provider_version
        and row.get("dimension") == provider.dimension
    )


def _embedding_records_for_chunks(
    chunks: Sequence[ChunkEmbeddingInput],
    *,
    provider: EmbeddingProvider,
) -> tuple[ChunkEmbeddingRecord, ...]:
    embeddings = provider.embed_texts([chunk.text for chunk in chunks])
    return tuple(
        ChunkEmbeddingRecord(
            chunk_id=chunk.chunk_id,
            text=chunk.text,
            embedding=embedding,
            provider=provider.provider,
            model_name=provider.model_name,
            provider_version=provider.provider_version,
            dimension=provider.dimension,
            metadata=chunk.metadata,
        )
        for chunk, embedding in zip(chunks, embeddings, strict=True)
    )


def _chunk_batches(
    chunks: Sequence[ChunkEmbeddingInput],
    batch_size: int,
) -> tuple[tuple[ChunkEmbeddingInput, ...], ...]:
    return tuple(
        tuple(chunks[index : index + batch_size]) for index in range(0, len(chunks), batch_size)
    )


def _provider_batch_size_hint(provider: EmbeddingProvider) -> int:
    raw_value = getattr(provider, "batch_size", None)
    return raw_value if isinstance(raw_value, int) and raw_value > 0 else 128


def _embedding_record(row: dict[str, object]) -> ChunkEmbeddingRecord:
    embedding = row.get("embedding")
    if not isinstance(embedding, list):
        raise ValueError("embedding row must contain embedding list")
    dimension = row.get("dimension")
    if not isinstance(dimension, int):
        raise ValueError("embedding row must contain integer dimension")
    return ChunkEmbeddingRecord(
        chunk_id=UUID(str(row["chunk_id"])),
        text=str(row["text"]),
        embedding=tuple(float(value) for value in embedding),
        provider=str(row["provider"]),
        model_name=str(row["model_name"]),
        provider_version=str(row["provider_version"]),
        dimension=dimension,
        metadata=_object_dict(row.get("metadata")),
    )


def _bm25_document(row: dict[str, object]) -> BM25Document:
    return BM25Document(
        chunk_id=UUID(str(row["chunk_id"])),
        text=str(row["text"]),
        metadata=_object_dict(row.get("metadata")),
    )


def _source_collection(row: dict[str, object]) -> SourceCollection | None:
    metadata = _object_dict(row.get("metadata"))
    value = metadata.get("source_collection")
    if not isinstance(value, str):
        return None
    try:
        return SourceCollection(value)
    except ValueError:
        return None


def _article_or_rule_hint(row: dict[str, object]) -> str | None:
    metadata = _object_dict(row.get("metadata"))
    article_number = metadata.get("article_number")
    if isinstance(article_number, str) and article_number:
        return article_number
    text = str(row.get("text", ""))
    if "规则名称" in text:
        return "规则名称"
    return None


def _query_haystack(row: dict[str, object]) -> str:
    text = str(row.get("text", ""))
    source_path = str(row.get("source_path", ""))
    # domain 是领域分类标签（供检索过滤），非内容；排除出 seed 相关性匹配，避免
    # 「医保基金」之类标签把非医保内容的文档误配到「医保」查询上。
    metadata = {
        key: value
        for key, value in _object_dict(row.get("metadata")).items()
        if key != "domain"
    }
    return "\n".join((text, source_path, json.dumps(metadata, ensure_ascii=False)))


def _matches_query_terms(row: dict[str, object], query_terms: tuple[str, ...]) -> bool:
    if not query_terms:
        return True
    haystack = _query_haystack(row)
    return any(term in haystack for term in query_terms)


def _query_term_match_count(row: dict[str, object], query_terms: tuple[str, ...]) -> int:
    if not query_terms:
        return 0
    haystack = _query_haystack(row)
    return len([term for term in query_terms if term in haystack])


def _source_priority(row: dict[str, object]) -> int:
    source_collection = _source_collection(row)
    if source_collection is None:
        return 99
    return SOURCE_COLLECTION_SEED_PRIORITY[source_collection]


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"json root must be object: {path}")
    return payload


def _write_jsonl(path: Path, rows: Iterable[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def _read_jsonl(path: Path) -> Iterable[dict[str, object]]:
    with path.open(encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"jsonl row must be object: {path}")
            yield payload


def _object_dict(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return dict(value)
    return {}


def _int_from_summary(summary: dict[str, object], key: str) -> int:
    value = summary.get(key)
    if not isinstance(value, int):
        raise ValueError(f"summary.{key} must be an integer")
    return value
