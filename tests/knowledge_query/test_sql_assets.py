from pathlib import Path


def test_pgvector_schema_matches_current_kimi_embedding_dimension() -> None:
    schema = Path("sql/knowledge-query-schema.sql").read_text(encoding="utf-8")

    assert "CREATE EXTENSION IF NOT EXISTS vector;" in schema
    assert "embedding vector(1024) NOT NULL" in schema
    assert "embedding vector(1536) NOT NULL" not in schema
    assert "ck_chunk_embeddings_dimension_1024 CHECK (dimension = 1024)" in schema
    assert "USING hnsw (embedding vector_cosine_ops)" in schema
    assert "model_name = 'kimi-for-coding'" in schema


def test_pgvector_schema_keeps_metadata_indexes_for_filtered_retrieval() -> None:
    schema = Path("sql/knowledge-query-schema.sql").read_text(encoding="utf-8")

    assert "idx_document_chunks_metadata_gin" in schema
    assert "idx_document_chunks_locator_gin" in schema
    assert "idx_query_logs_filters_gin" in schema


def test_pgvector_schema_includes_evaluation_run_history_table() -> None:
    schema = Path("sql/knowledge-query-schema.sql").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS index_evaluation_runs" in schema
    assert "run_id uuid NOT NULL UNIQUE" in schema
    assert "report_path text NOT NULL" in schema
    assert "request jsonb NOT NULL DEFAULT '{}'::jsonb" in schema
    assert "report jsonb NOT NULL DEFAULT '{}'::jsonb" in schema
    assert "idx_index_evaluation_runs_created_at" in schema
    assert "idx_index_evaluation_runs_status" in schema
