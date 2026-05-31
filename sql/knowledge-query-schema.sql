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
    embedding vector(1536) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_chunk_embeddings_provider UNIQUE (chunk_id, provider, model_name, provider_version),
    CONSTRAINT ck_chunk_embeddings_dimension_positive CHECK (dimension > 0)
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

CREATE INDEX IF NOT EXISTS idx_source_documents_collection ON source_documents (source_collection);
CREATE INDEX IF NOT EXISTS idx_source_documents_package ON source_documents (source_package_version_id);
CREATE INDEX IF NOT EXISTS idx_source_documents_sha256 ON source_documents (sha256);
CREATE INDEX IF NOT EXISTS idx_source_documents_status ON source_documents (status);
CREATE INDEX IF NOT EXISTS idx_document_chunks_document ON document_chunks (source_document_id);
CREATE INDEX IF NOT EXISTS idx_document_chunks_article_number ON document_chunks (article_number);
CREATE INDEX IF NOT EXISTS idx_document_chunks_page_number ON document_chunks (page_number);
CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_chunk ON chunk_embeddings (chunk_id);
CREATE INDEX IF NOT EXISTS idx_index_versions_package ON index_versions (source_package_version_id);
CREATE INDEX IF NOT EXISTS idx_index_versions_status ON index_versions (status);
CREATE INDEX IF NOT EXISTS idx_index_jobs_status ON index_jobs (status);
CREATE INDEX IF NOT EXISTS idx_failed_files_status ON failed_files (status);
CREATE INDEX IF NOT EXISTS idx_pending_files_status ON pending_files (status);
CREATE INDEX IF NOT EXISTS idx_query_logs_created_at ON query_logs (created_at);
