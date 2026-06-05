CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS source_package_versions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    version_key text NOT NULL UNIQUE,
    source_root_path text NOT NULL,
    description text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS source_documents (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_package_version_id uuid NOT NULL REFERENCES source_package_versions(id) ON DELETE CASCADE,
    source_collection text NOT NULL,
    relative_path text NOT NULL,
    absolute_path text,
    file_name text NOT NULL,
    file_ext text NOT NULL,
    media_type text NOT NULL,
    sha256 char(64) NOT NULL,
    size_bytes bigint NOT NULL,
    status text NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    discovered_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_source_documents_version_path UNIQUE (source_package_version_id, relative_path),
    CONSTRAINT ck_source_documents_size_non_negative CHECK (size_bytes >= 0),
    CONSTRAINT ck_source_documents_sha256_length CHECK (length(sha256) = 64)
);

CREATE TABLE IF NOT EXISTS document_chunks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_document_id uuid NOT NULL REFERENCES source_documents(id) ON DELETE CASCADE,
    chunk_index integer NOT NULL,
    text text NOT NULL,
    title_path jsonb NOT NULL DEFAULT '[]'::jsonb,
    article_number text,
    page_number integer,
    line_start integer,
    line_end integer,
    sheet_name text,
    row_number integer,
    token_count integer,
    locator jsonb NOT NULL DEFAULT '{}'::jsonb,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_document_chunks_document_index UNIQUE (source_document_id, chunk_index),
    CONSTRAINT ck_document_chunks_chunk_index_non_negative CHECK (chunk_index >= 0),
    CONSTRAINT ck_document_chunks_token_count_non_negative CHECK (token_count IS NULL OR token_count >= 0)
);

CREATE TABLE IF NOT EXISTS chunk_embeddings (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    chunk_id uuid NOT NULL REFERENCES document_chunks(id) ON DELETE CASCADE,
    provider text NOT NULL,
    model_name text NOT NULL,
    provider_version text NOT NULL,
    dimension integer NOT NULL,
    embedding vector(1024) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_chunk_embeddings_provider UNIQUE (chunk_id, provider, model_name, provider_version),
    CONSTRAINT ck_chunk_embeddings_dimension_1024 CHECK (dimension = 1024)
);

CREATE TABLE IF NOT EXISTS index_versions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_package_version_id uuid NOT NULL REFERENCES source_package_versions(id) ON DELETE RESTRICT,
    version_key text NOT NULL UNIQUE,
    status text NOT NULL,
    bm25_index_path text,
    vector_provider text,
    vector_model text,
    chunk_count integer NOT NULL DEFAULT 0,
    document_count integer NOT NULL DEFAULT 0,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    activated_at timestamptz,
    CONSTRAINT ck_index_versions_chunk_count_non_negative CHECK (chunk_count >= 0),
    CONSTRAINT ck_index_versions_document_count_non_negative CHECK (document_count >= 0)
);

CREATE TABLE IF NOT EXISTS index_jobs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    index_version_id uuid REFERENCES index_versions(id) ON DELETE SET NULL,
    job_type text NOT NULL,
    status text NOT NULL,
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    summary jsonb NOT NULL DEFAULT '{}'::jsonb,
    error_summary text
);

CREATE TABLE IF NOT EXISTS failed_files (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_package_version_id uuid NOT NULL REFERENCES source_package_versions(id) ON DELETE CASCADE,
    source_document_id uuid REFERENCES source_documents(id) ON DELETE SET NULL,
    relative_path text NOT NULL,
    error_type text NOT NULL,
    error_summary text NOT NULL,
    retry_count integer NOT NULL DEFAULT 0,
    status text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_failed_files_retry_count_non_negative CHECK (retry_count >= 0)
);

CREATE TABLE IF NOT EXISTS pending_files (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_package_version_id uuid NOT NULL REFERENCES source_package_versions(id) ON DELETE CASCADE,
    relative_path text NOT NULL,
    reason text NOT NULL,
    status text NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS query_logs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    index_version_id uuid REFERENCES index_versions(id) ON DELETE SET NULL,
    source_package_version_id uuid REFERENCES source_package_versions(id) ON DELETE SET NULL,
    user_identifier text,
    question text NOT NULL,
    filters jsonb NOT NULL DEFAULT '{}'::jsonb,
    answer_summary text,
    retrieved_chunk_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_log_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    action text NOT NULL,
    entity_type text NOT NULL,
    entity_id text NOT NULL,
    user_identifier text,
    role text,
    status_code integer,
    endpoint text,
    reason text,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_audit_log_events_status_code
        CHECK (status_code IS NULL OR (status_code >= 100 AND status_code <= 599))
);

CREATE TABLE IF NOT EXISTS index_evaluation_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id uuid NOT NULL UNIQUE,
    status text NOT NULL,
    report_path text NOT NULL,
    retrieval_case_count integer NOT NULL DEFAULT 0,
    answer_case_count integer NOT NULL DEFAULT 0,
    ui_smoke_success boolean NOT NULL DEFAULT false,
    search_backend text NOT NULL,
    search_backend_details jsonb NOT NULL DEFAULT '{}'::jsonb,
    request jsonb NOT NULL DEFAULT '{}'::jsonb,
    report jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_index_evaluation_runs_retrieval_case_count_non_negative CHECK (retrieval_case_count >= 0),
    CONSTRAINT ck_index_evaluation_runs_answer_case_count_non_negative CHECK (answer_case_count >= 0)
);

CREATE TABLE IF NOT EXISTS review_tasks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    external_task_id text NOT NULL UNIQUE,
    question text NOT NULL,
    status text NOT NULL,
    status_label text NOT NULL,
    citation_count integer NOT NULL DEFAULT 0,
    review_gate text NOT NULL,
    confidence_label text NOT NULL,
    fallback_label text NOT NULL,
    reviewer_note text NOT NULL DEFAULT '',
    conclusion text NOT NULL DEFAULT '',
    created_by text,
    assigned_to text,
    source text NOT NULL,
    dossier jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_review_tasks_citation_count_non_negative CHECK (citation_count >= 0)
);

ALTER TABLE IF EXISTS review_tasks
    ADD COLUMN IF NOT EXISTS reviewer_note text NOT NULL DEFAULT '';

ALTER TABLE IF EXISTS review_tasks
    ADD COLUMN IF NOT EXISTS conclusion text NOT NULL DEFAULT '';

CREATE TABLE IF NOT EXISTS review_actions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    review_task_id uuid NOT NULL REFERENCES review_tasks(id) ON DELETE CASCADE,
    action_type text NOT NULL,
    from_status text,
    to_status text,
    actor text,
    note text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS review_comments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    review_task_id uuid NOT NULL REFERENCES review_tasks(id) ON DELETE CASCADE,
    author text NOT NULL,
    body text NOT NULL,
    visibility text NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_projects (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_key text NOT NULL UNIQUE,
    name text NOT NULL,
    scenario_key text NOT NULL,
    status text NOT NULL,
    owner_department text,
    created_by text,
    description text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS his_source_batches (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_key text NOT NULL UNIQUE,
    project_id uuid NOT NULL REFERENCES audit_projects(id) ON DELETE RESTRICT,
    hospital_code text NOT NULL,
    scenario_key text NOT NULL,
    source_type text NOT NULL,
    exported_at timestamptz,
    file_manifest jsonb NOT NULL DEFAULT '{}'::jsonb,
    row_counts jsonb NOT NULL DEFAULT '{}'::jsonb,
    checksum text,
    status text NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS his_table_schemas (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    schema_key text NOT NULL UNIQUE,
    source_batch_id uuid NOT NULL REFERENCES his_source_batches(id) ON DELETE CASCADE,
    table_name text NOT NULL,
    business_domain text NOT NULL,
    ddl_text text NOT NULL,
    ddl_hash text NOT NULL,
    field_dictionary jsonb NOT NULL DEFAULT '{}'::jsonb,
    primary_key_fields jsonb NOT NULL DEFAULT '[]'::jsonb,
    time_fields jsonb NOT NULL DEFAULT '[]'::jsonb,
    row_count integer,
    status text NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_his_table_schemas_batch_table UNIQUE (source_batch_id, table_name),
    CONSTRAINT ck_his_table_schemas_row_count_non_negative CHECK (row_count IS NULL OR row_count >= 0)
);

CREATE TABLE IF NOT EXISTS his_staging_rows (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_batch_id uuid NOT NULL REFERENCES his_source_batches(id) ON DELETE CASCADE,
    table_schema_id uuid REFERENCES his_table_schemas(id) ON DELETE SET NULL,
    table_name text NOT NULL,
    row_number integer NOT NULL,
    row_data jsonb NOT NULL DEFAULT '{}'::jsonb,
    row_hash text NOT NULL,
    status text NOT NULL,
    validation_errors jsonb NOT NULL DEFAULT '[]'::jsonb,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_his_staging_rows_batch_table_row
        UNIQUE (source_batch_id, table_name, row_number),
    CONSTRAINT ck_his_staging_rows_row_number_positive CHECK (row_number >= 1)
);

CREATE TABLE IF NOT EXISTS his_field_mappings (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    mapping_key text NOT NULL UNIQUE,
    table_schema_id uuid NOT NULL REFERENCES his_table_schemas(id) ON DELETE CASCADE,
    source_field text NOT NULL,
    target_domain text NOT NULL,
    target_field text NOT NULL,
    source_data_type text,
    target_data_type text,
    transform_rule text,
    is_required boolean NOT NULL DEFAULT true,
    nullable boolean NOT NULL DEFAULT false,
    deidentification_rule text,
    status text NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_data_snapshots (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_key text NOT NULL UNIQUE,
    project_id uuid NOT NULL REFERENCES audit_projects(id) ON DELETE RESTRICT,
    source_batch_key text NOT NULL,
    time_range jsonb NOT NULL DEFAULT '{}'::jsonb,
    row_counts jsonb NOT NULL DEFAULT '{}'::jsonb,
    checksum text,
    status text NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_snapshot_rollbacks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    rollback_key text NOT NULL UNIQUE,
    project_id uuid NOT NULL REFERENCES audit_projects(id) ON DELETE RESTRICT,
    from_snapshot_id uuid NOT NULL REFERENCES audit_data_snapshots(id) ON DELETE RESTRICT,
    to_snapshot_id uuid NOT NULL REFERENCES audit_data_snapshots(id) ON DELETE RESTRICT,
    status text NOT NULL,
    reason text NOT NULL,
    requested_by text,
    impact_summary jsonb NOT NULL DEFAULT '{}'::jsonb,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_audit_snapshot_rollbacks_distinct_snapshots
        CHECK (from_snapshot_id <> to_snapshot_id)
);

CREATE TABLE IF NOT EXISTS audit_tasks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    task_key text NOT NULL UNIQUE,
    project_id uuid NOT NULL REFERENCES audit_projects(id) ON DELETE RESTRICT,
    snapshot_id uuid NOT NULL REFERENCES audit_data_snapshots(id) ON DELETE RESTRICT,
    topic text NOT NULL,
    department_scope jsonb NOT NULL DEFAULT '{}'::jsonb,
    date_range jsonb NOT NULL DEFAULT '{}'::jsonb,
    status text NOT NULL,
    created_by text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_key text NOT NULL UNIQUE,
    audit_task_id uuid NOT NULL REFERENCES audit_tasks(id) ON DELETE RESTRICT,
    snapshot_id uuid NOT NULL REFERENCES audit_data_snapshots(id) ON DELETE RESTRICT,
    rule_version_key text NOT NULL,
    knowledge_index_version_key text,
    status text NOT NULL,
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    summary jsonb NOT NULL DEFAULT '{}'::jsonb,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS audit_rules (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_key text NOT NULL UNIQUE,
    scenario_key text NOT NULL,
    name text NOT NULL,
    status text NOT NULL,
    owner text,
    description text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rule_versions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    audit_rule_id uuid NOT NULL REFERENCES audit_rules(id) ON DELETE RESTRICT,
    version_key text NOT NULL UNIQUE,
    rule_key text NOT NULL,
    status text NOT NULL,
    logic jsonb NOT NULL DEFAULT '{}'::jsonb,
    evidence_links jsonb NOT NULL DEFAULT '{}'::jsonb,
    effective_from timestamptz,
    effective_to timestamptz,
    created_by text,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_rule_versions_rule_version UNIQUE (audit_rule_id, version_key)
);

CREATE TABLE IF NOT EXISTS audit_findings (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    finding_key text NOT NULL UNIQUE,
    audit_run_id uuid NOT NULL REFERENCES audit_runs(id) ON DELETE RESTRICT,
    audit_task_id uuid NOT NULL REFERENCES audit_tasks(id) ON DELETE RESTRICT,
    rule_version_id uuid NOT NULL REFERENCES rule_versions(id) ON DELETE RESTRICT,
    snapshot_id uuid NOT NULL REFERENCES audit_data_snapshots(id) ON DELETE RESTRICT,
    status text NOT NULL,
    finding_type text NOT NULL,
    severity text NOT NULL,
    source_record_locator jsonb NOT NULL DEFAULT '{}'::jsonb,
    calculation_trace jsonb NOT NULL DEFAULT '{}'::jsonb,
    review_status text NOT NULL,
    review_task_id uuid REFERENCES review_tasks(id) ON DELETE SET NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS finding_evidence_items (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    audit_finding_id uuid NOT NULL REFERENCES audit_findings(id) ON DELETE CASCADE,
    evidence_type text NOT NULL,
    chunk_id uuid REFERENCES document_chunks(id) ON DELETE SET NULL,
    source_package_version_key text,
    index_version_key text,
    citation_id text,
    locator jsonb NOT NULL DEFAULT '{}'::jsonb,
    snippet text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_source_documents_collection ON source_documents (source_collection);
CREATE INDEX IF NOT EXISTS idx_source_documents_package ON source_documents (source_package_version_id);
CREATE INDEX IF NOT EXISTS idx_source_documents_sha256 ON source_documents (sha256);
CREATE INDEX IF NOT EXISTS idx_source_documents_status ON source_documents (status);
CREATE INDEX IF NOT EXISTS idx_document_chunks_document ON document_chunks (source_document_id);
CREATE INDEX IF NOT EXISTS idx_document_chunks_article_number ON document_chunks (article_number);
CREATE INDEX IF NOT EXISTS idx_document_chunks_page_number ON document_chunks (page_number);
CREATE INDEX IF NOT EXISTS idx_document_chunks_metadata_gin ON document_chunks USING gin (metadata);
CREATE INDEX IF NOT EXISTS idx_document_chunks_locator_gin ON document_chunks USING gin (locator);
CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_chunk ON chunk_embeddings (chunk_id);
CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_kimi_cosine_hnsw
    ON chunk_embeddings
    USING hnsw (embedding vector_cosine_ops)
    WHERE provider = 'openai'
      AND model_name = 'kimi-for-coding'
      AND provider_version = 'v1'
      AND dimension = 1024;
CREATE INDEX IF NOT EXISTS idx_index_versions_package ON index_versions (source_package_version_id);
CREATE INDEX IF NOT EXISTS idx_index_versions_status ON index_versions (status);
CREATE INDEX IF NOT EXISTS idx_index_jobs_status ON index_jobs (status);
CREATE INDEX IF NOT EXISTS idx_failed_files_status ON failed_files (status);
CREATE INDEX IF NOT EXISTS idx_pending_files_status ON pending_files (status);
CREATE INDEX IF NOT EXISTS idx_query_logs_created_at ON query_logs (created_at);
CREATE INDEX IF NOT EXISTS idx_query_logs_filters_gin ON query_logs USING gin (filters);
CREATE INDEX IF NOT EXISTS idx_audit_log_events_action ON audit_log_events (action);
CREATE INDEX IF NOT EXISTS idx_audit_log_events_entity
    ON audit_log_events (entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_events_user ON audit_log_events (user_identifier);
CREATE INDEX IF NOT EXISTS idx_audit_log_events_created_at
    ON audit_log_events (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_events_payload_gin
    ON audit_log_events USING gin (payload);
CREATE INDEX IF NOT EXISTS idx_index_evaluation_runs_created_at ON index_evaluation_runs (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_index_evaluation_runs_status ON index_evaluation_runs (status);
CREATE INDEX IF NOT EXISTS idx_review_tasks_status ON review_tasks (status);
CREATE INDEX IF NOT EXISTS idx_review_tasks_created_at ON review_tasks (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_review_tasks_created_by ON review_tasks (created_by);
CREATE INDEX IF NOT EXISTS idx_review_actions_task ON review_actions (review_task_id);
CREATE INDEX IF NOT EXISTS idx_review_actions_task_created_at
    ON review_actions (review_task_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_review_actions_type ON review_actions (action_type);
CREATE INDEX IF NOT EXISTS idx_review_comments_task ON review_comments (review_task_id);
CREATE INDEX IF NOT EXISTS idx_review_comments_task_created_at
    ON review_comments (review_task_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_review_comments_visibility ON review_comments (visibility);
CREATE INDEX IF NOT EXISTS idx_audit_projects_status ON audit_projects (status);
CREATE INDEX IF NOT EXISTS idx_audit_projects_scenario ON audit_projects (scenario_key);
CREATE INDEX IF NOT EXISTS idx_his_source_batches_project ON his_source_batches (project_id);
CREATE INDEX IF NOT EXISTS idx_his_source_batches_hospital ON his_source_batches (hospital_code);
CREATE INDEX IF NOT EXISTS idx_his_source_batches_status ON his_source_batches (status);
CREATE INDEX IF NOT EXISTS idx_his_table_schemas_batch ON his_table_schemas (source_batch_id);
CREATE INDEX IF NOT EXISTS idx_his_table_schemas_domain ON his_table_schemas (business_domain);
CREATE INDEX IF NOT EXISTS idx_his_table_schemas_status ON his_table_schemas (status);
CREATE INDEX IF NOT EXISTS idx_his_staging_rows_batch ON his_staging_rows (source_batch_id);
CREATE INDEX IF NOT EXISTS idx_his_staging_rows_schema ON his_staging_rows (table_schema_id);
CREATE INDEX IF NOT EXISTS idx_his_staging_rows_table ON his_staging_rows (table_name);
CREATE INDEX IF NOT EXISTS idx_his_staging_rows_status ON his_staging_rows (status);
CREATE INDEX IF NOT EXISTS idx_his_staging_rows_hash ON his_staging_rows (row_hash);
CREATE INDEX IF NOT EXISTS idx_his_field_mappings_schema ON his_field_mappings (table_schema_id);
CREATE INDEX IF NOT EXISTS idx_his_field_mappings_target
    ON his_field_mappings (target_domain, target_field);
CREATE INDEX IF NOT EXISTS idx_his_field_mappings_status ON his_field_mappings (status);
CREATE INDEX IF NOT EXISTS idx_audit_data_snapshots_project ON audit_data_snapshots (project_id);
CREATE INDEX IF NOT EXISTS idx_audit_data_snapshots_status ON audit_data_snapshots (status);
CREATE INDEX IF NOT EXISTS idx_audit_snapshot_rollbacks_project
    ON audit_snapshot_rollbacks (project_id);
CREATE INDEX IF NOT EXISTS idx_audit_snapshot_rollbacks_from_snapshot
    ON audit_snapshot_rollbacks (from_snapshot_id);
CREATE INDEX IF NOT EXISTS idx_audit_snapshot_rollbacks_to_snapshot
    ON audit_snapshot_rollbacks (to_snapshot_id);
CREATE INDEX IF NOT EXISTS idx_audit_snapshot_rollbacks_status
    ON audit_snapshot_rollbacks (status);
CREATE INDEX IF NOT EXISTS idx_audit_tasks_project ON audit_tasks (project_id);
CREATE INDEX IF NOT EXISTS idx_audit_tasks_snapshot ON audit_tasks (snapshot_id);
CREATE INDEX IF NOT EXISTS idx_audit_tasks_status ON audit_tasks (status);
CREATE INDEX IF NOT EXISTS idx_audit_runs_task ON audit_runs (audit_task_id);
CREATE INDEX IF NOT EXISTS idx_audit_runs_snapshot ON audit_runs (snapshot_id);
CREATE INDEX IF NOT EXISTS idx_audit_runs_status ON audit_runs (status);
CREATE INDEX IF NOT EXISTS idx_audit_rules_scenario ON audit_rules (scenario_key);
CREATE INDEX IF NOT EXISTS idx_audit_rules_status ON audit_rules (status);
CREATE INDEX IF NOT EXISTS idx_rule_versions_rule ON rule_versions (audit_rule_id);
CREATE INDEX IF NOT EXISTS idx_rule_versions_status ON rule_versions (status);
CREATE INDEX IF NOT EXISTS idx_audit_findings_run ON audit_findings (audit_run_id);
CREATE INDEX IF NOT EXISTS idx_audit_findings_task ON audit_findings (audit_task_id);
CREATE INDEX IF NOT EXISTS idx_audit_findings_rule_version ON audit_findings (rule_version_id);
CREATE INDEX IF NOT EXISTS idx_audit_findings_review_status ON audit_findings (review_status);
CREATE INDEX IF NOT EXISTS idx_audit_findings_status ON audit_findings (status);
CREATE INDEX IF NOT EXISTS idx_finding_evidence_items_finding
    ON finding_evidence_items (audit_finding_id);
CREATE INDEX IF NOT EXISTS idx_finding_evidence_items_chunk ON finding_evidence_items (chunk_id);
CREATE INDEX IF NOT EXISTS idx_finding_evidence_items_type ON finding_evidence_items (evidence_type);
