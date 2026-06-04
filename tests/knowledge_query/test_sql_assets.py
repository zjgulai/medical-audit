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


def test_pgvector_schema_includes_review_task_tables() -> None:
    schema = Path("sql/knowledge-query-schema.sql").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS review_tasks" in schema
    assert "external_task_id text NOT NULL UNIQUE" in schema
    assert "dossier jsonb NOT NULL DEFAULT '{}'::jsonb" in schema
    assert "reviewer_note text NOT NULL DEFAULT ''" in schema
    assert "ADD COLUMN IF NOT EXISTS reviewer_note" in schema
    assert "ADD COLUMN IF NOT EXISTS conclusion" in schema
    assert "CREATE TABLE IF NOT EXISTS review_actions" in schema
    assert "review_task_id uuid NOT NULL REFERENCES review_tasks(id) ON DELETE CASCADE" in schema
    assert "CREATE TABLE IF NOT EXISTS review_comments" in schema
    assert "idx_review_tasks_status" in schema
    assert "idx_review_actions_task_created_at" in schema
    assert "idx_review_comments_task_created_at" in schema


def test_pgvector_schema_includes_audit_workflow_tables() -> None:
    schema = Path("sql/knowledge-query-schema.sql").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS audit_projects" in schema
    assert "project_key text NOT NULL UNIQUE" in schema
    assert "CREATE TABLE IF NOT EXISTS audit_data_snapshots" in schema
    assert "project_id uuid NOT NULL REFERENCES audit_projects(id) ON DELETE RESTRICT" in schema
    assert "CREATE TABLE IF NOT EXISTS audit_tasks" in schema
    assert (
        "snapshot_id uuid NOT NULL REFERENCES audit_data_snapshots(id) ON DELETE RESTRICT" in schema
    )
    assert "CREATE TABLE IF NOT EXISTS audit_runs" in schema
    assert "audit_task_id uuid NOT NULL REFERENCES audit_tasks(id) ON DELETE RESTRICT" in schema
    assert "CREATE TABLE IF NOT EXISTS audit_rules" in schema
    assert "CREATE TABLE IF NOT EXISTS rule_versions" in schema
    assert "audit_rule_id uuid NOT NULL REFERENCES audit_rules(id) ON DELETE RESTRICT" in schema
    assert "CREATE TABLE IF NOT EXISTS audit_findings" in schema
    assert "rule_version_id uuid NOT NULL REFERENCES rule_versions(id) ON DELETE RESTRICT" in schema
    assert "CREATE TABLE IF NOT EXISTS finding_evidence_items" in schema
    assert (
        "audit_finding_id uuid NOT NULL REFERENCES audit_findings(id) ON DELETE CASCADE" in schema
    )
    assert "chunk_id uuid REFERENCES document_chunks(id) ON DELETE SET NULL" in schema
    assert "idx_audit_tasks_project" in schema
    assert "idx_audit_runs_task" in schema
    assert "idx_audit_findings_run" in schema
    assert "idx_finding_evidence_items_finding" in schema


def test_pgvector_schema_includes_his_ingestion_contract_tables() -> None:
    schema = Path("sql/knowledge-query-schema.sql").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS his_source_batches" in schema
    assert "batch_key text NOT NULL UNIQUE" in schema
    assert "project_id uuid NOT NULL REFERENCES audit_projects(id) ON DELETE RESTRICT" in schema
    assert "CREATE TABLE IF NOT EXISTS his_table_schemas" in schema
    assert (
        "source_batch_id uuid NOT NULL REFERENCES his_source_batches(id) ON DELETE CASCADE"
        in schema
    )
    assert "CONSTRAINT uq_his_table_schemas_batch_table UNIQUE" in schema
    assert "CREATE TABLE IF NOT EXISTS his_staging_rows" in schema
    assert (
        "source_batch_id uuid NOT NULL REFERENCES his_source_batches(id) ON DELETE CASCADE"
        in schema
    )
    assert "table_schema_id uuid REFERENCES his_table_schemas(id) ON DELETE SET NULL" in schema
    assert "CONSTRAINT uq_his_staging_rows_batch_table_row" in schema
    assert "CONSTRAINT ck_his_staging_rows_row_number_positive" in schema
    assert "CREATE TABLE IF NOT EXISTS his_field_mappings" in schema
    assert (
        "table_schema_id uuid NOT NULL REFERENCES his_table_schemas(id) ON DELETE CASCADE" in schema
    )
    assert "deidentification_rule text" in schema
    assert "idx_his_source_batches_project" in schema
    assert "idx_his_table_schemas_domain" in schema
    assert "idx_his_staging_rows_batch" in schema
    assert "idx_his_staging_rows_hash" in schema
    assert "idx_his_field_mappings_target" in schema
