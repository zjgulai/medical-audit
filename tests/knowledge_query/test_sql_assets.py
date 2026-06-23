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


def test_pgvector_schema_includes_audit_agent_table() -> None:
    schema = Path("sql/knowledge-query-schema.sql").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS audit_agents" in schema
    assert "CREATE TABLE IF NOT EXISTS audit_agent_prompt_versions" in schema
    assert "CREATE TABLE IF NOT EXISTS audit_agent_invocations" in schema
    assert "CREATE TABLE IF NOT EXISTS audit_agent_feedback" in schema
    assert "agent_key text NOT NULL UNIQUE" in schema
    assert "prompt text NOT NULL" in schema
    assert "knowledge_base text NOT NULL" in schema
    assert "project_name text NOT NULL" in schema
    assert "agent_id uuid NOT NULL REFERENCES audit_agents(id) ON DELETE CASCADE" in schema
    assert "agent_id uuid REFERENCES audit_agents(id) ON DELETE SET NULL" in schema
    assert "invocation_id uuid REFERENCES audit_agent_invocations(id) ON DELETE SET NULL" in schema
    assert "CONSTRAINT uq_audit_agent_prompt_versions_agent_version" in schema
    assert "CONSTRAINT ck_audit_agent_feedback_rating" in schema
    assert "CONSTRAINT ck_audit_agents_category" in schema
    assert "idx_audit_agents_category" in schema
    assert "idx_audit_agents_status" in schema
    assert "idx_audit_agents_updated_at" in schema
    assert "idx_audit_agent_prompt_versions_agent" in schema
    assert "idx_audit_agent_invocations_agent_key" in schema
    assert "idx_audit_agent_feedback_agent_key" in schema
    assert "idx_audit_agent_feedback_invocation" in schema


def test_pgvector_schema_includes_project_member_table() -> None:
    schema = Path("sql/knowledge-query-schema.sql").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS audit_project_members" in schema
    assert "member_key text NOT NULL UNIQUE" in schema
    assert "project_key text NOT NULL" in schema
    assert "department text NOT NULL" in schema
    assert "CONSTRAINT ck_audit_project_members_role" in schema
    assert "CONSTRAINT ck_audit_project_members_status" in schema
    assert "idx_audit_project_members_project" in schema
    assert "idx_audit_project_members_role" in schema
    assert "idx_audit_project_members_status" in schema


def test_pgvector_schema_includes_auth_user_tables() -> None:
    schema = Path("sql/knowledge-query-schema.sql").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS auth_departments" in schema
    assert "department_key text NOT NULL UNIQUE" in schema
    assert "CREATE TABLE IF NOT EXISTS auth_users" in schema
    assert "user_key text NOT NULL UNIQUE" in schema
    assert (
        "department_key text REFERENCES auth_departments(department_key) ON DELETE SET NULL"
        in schema
    )
    assert "CREATE TABLE IF NOT EXISTS auth_user_role_assignments" in schema
    assert "user_key text NOT NULL REFERENCES auth_users(user_key) ON DELETE CASCADE" in schema
    assert "CONSTRAINT ck_auth_user_role_assignments_role" in schema
    assert "CHECK (role IN ('admin', 'technician', 'director', 'member'))" in schema
    assert "idx_auth_users_department" in schema
    assert "idx_auth_user_role_assignments_user" in schema
    assert "idx_auth_user_role_assignments_role" in schema


def test_pgvector_schema_includes_analytics_upload_records_table() -> None:
    schema = Path("sql/knowledge-query-schema.sql").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS analytics_upload_records" in schema
    assert "upload_key text NOT NULL UNIQUE" in schema
    assert "sha256 text NOT NULL" in schema
    assert "storage_path text NOT NULL" in schema
    assert "analysis_summary jsonb NOT NULL DEFAULT '{}'::jsonb" in schema
    assert "CONSTRAINT ck_analytics_upload_records_extension" in schema
    assert "idx_analytics_upload_records_created_at" in schema
    assert "idx_analytics_upload_records_sha256" in schema


def test_pgvector_schema_includes_document_upload_records_table() -> None:
    schema = Path("sql/knowledge-query-schema.sql").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS document_upload_records" in schema
    assert "upload_key text NOT NULL UNIQUE" in schema
    assert "file_name text NOT NULL" in schema
    assert "storage_path text NOT NULL" in schema
    assert "visibility text NOT NULL DEFAULT 'private'" in schema
    assert "status text NOT NULL DEFAULT 'retained'" in schema
    assert "metadata jsonb NOT NULL DEFAULT '{}'::jsonb" in schema
    assert "CONSTRAINT ck_document_upload_records_extension" in schema
    assert "CONSTRAINT ck_document_upload_records_visibility" in schema
    assert "CONSTRAINT ck_document_upload_records_status" in schema
    assert "idx_document_upload_records_created_by" in schema
    assert "idx_document_upload_records_sha256" in schema
    assert "idx_document_upload_records_status" in schema


def test_pgvector_schema_includes_audit_workflow_tables() -> None:
    schema = Path("sql/knowledge-query-schema.sql").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS audit_projects" in schema
    assert "project_key text NOT NULL UNIQUE" in schema
    assert "CREATE TABLE IF NOT EXISTS audit_data_snapshots" in schema
    assert "project_id uuid NOT NULL REFERENCES audit_projects(id) ON DELETE RESTRICT" in schema
    assert "CREATE TABLE IF NOT EXISTS audit_snapshot_rollbacks" in schema
    assert (
        "from_snapshot_id uuid NOT NULL REFERENCES audit_data_snapshots(id) ON DELETE RESTRICT"
        in schema
    )
    assert (
        "to_snapshot_id uuid NOT NULL REFERENCES audit_data_snapshots(id) ON DELETE RESTRICT"
        in schema
    )
    assert "ck_audit_snapshot_rollbacks_distinct_snapshots" in schema
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
    assert "idx_audit_snapshot_rollbacks_project" in schema
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
