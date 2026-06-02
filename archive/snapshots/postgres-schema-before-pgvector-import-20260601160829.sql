--
-- PostgreSQL database dump
--

\restrict jFrwP5ZNYrGbhJfrorCtXgaVNdSOcF8GRMTZ7LWC6Iej0j4liP1mOGQ8A7diaxX

-- Dumped from database version 16.14 (Debian 16.14-1.pgdg12+1)
-- Dumped by pg_dump version 16.14 (Debian 16.14-1.pgdg12+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: pgcrypto; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;


--
-- Name: EXTENSION pgcrypto; Type: COMMENT; Schema: -; Owner:
--

COMMENT ON EXTENSION pgcrypto IS 'cryptographic functions';


--
-- Name: vector; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;


--
-- Name: EXTENSION vector; Type: COMMENT; Schema: -; Owner:
--

COMMENT ON EXTENSION vector IS 'vector data type and ivfflat and hnsw access methods';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: chunk_embeddings; Type: TABLE; Schema: public; Owner: medical_audit_kb
--

CREATE TABLE public.chunk_embeddings (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    chunk_id uuid NOT NULL,
    provider text NOT NULL,
    model_name text NOT NULL,
    provider_version text NOT NULL,
    dimension integer NOT NULL,
    embedding public.vector(1024) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_chunk_embeddings_dimension_1024 CHECK ((dimension = 1024))
);


ALTER TABLE public.chunk_embeddings OWNER TO medical_audit_kb;

--
-- Name: document_chunks; Type: TABLE; Schema: public; Owner: medical_audit_kb
--

CREATE TABLE public.document_chunks (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    source_document_id uuid NOT NULL,
    chunk_index integer NOT NULL,
    text text NOT NULL,
    title_path jsonb DEFAULT '[]'::jsonb NOT NULL,
    article_number text,
    page_number integer,
    line_start integer,
    line_end integer,
    sheet_name text,
    row_number integer,
    token_count integer,
    locator jsonb DEFAULT '{}'::jsonb NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_document_chunks_chunk_index_non_negative CHECK ((chunk_index >= 0)),
    CONSTRAINT ck_document_chunks_token_count_non_negative CHECK (((token_count IS NULL) OR (token_count >= 0)))
);


ALTER TABLE public.document_chunks OWNER TO medical_audit_kb;

--
-- Name: failed_files; Type: TABLE; Schema: public; Owner: medical_audit_kb
--

CREATE TABLE public.failed_files (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    source_package_version_id uuid NOT NULL,
    source_document_id uuid,
    relative_path text NOT NULL,
    error_type text NOT NULL,
    error_summary text NOT NULL,
    retry_count integer DEFAULT 0 NOT NULL,
    status text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_failed_files_retry_count_non_negative CHECK ((retry_count >= 0))
);


ALTER TABLE public.failed_files OWNER TO medical_audit_kb;

--
-- Name: index_jobs; Type: TABLE; Schema: public; Owner: medical_audit_kb
--

CREATE TABLE public.index_jobs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    index_version_id uuid,
    job_type text NOT NULL,
    status text NOT NULL,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    finished_at timestamp with time zone,
    summary jsonb DEFAULT '{}'::jsonb NOT NULL,
    error_summary text
);


ALTER TABLE public.index_jobs OWNER TO medical_audit_kb;

--
-- Name: index_versions; Type: TABLE; Schema: public; Owner: medical_audit_kb
--

CREATE TABLE public.index_versions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    source_package_version_id uuid NOT NULL,
    version_key text NOT NULL,
    status text NOT NULL,
    bm25_index_path text,
    vector_provider text,
    vector_model text,
    chunk_count integer DEFAULT 0 NOT NULL,
    document_count integer DEFAULT 0 NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    activated_at timestamp with time zone,
    CONSTRAINT ck_index_versions_chunk_count_non_negative CHECK ((chunk_count >= 0)),
    CONSTRAINT ck_index_versions_document_count_non_negative CHECK ((document_count >= 0))
);


ALTER TABLE public.index_versions OWNER TO medical_audit_kb;

--
-- Name: pending_files; Type: TABLE; Schema: public; Owner: medical_audit_kb
--

CREATE TABLE public.pending_files (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    source_package_version_id uuid NOT NULL,
    relative_path text NOT NULL,
    reason text NOT NULL,
    status text NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.pending_files OWNER TO medical_audit_kb;

--
-- Name: query_logs; Type: TABLE; Schema: public; Owner: medical_audit_kb
--

CREATE TABLE public.query_logs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    index_version_id uuid,
    source_package_version_id uuid,
    user_identifier text,
    question text NOT NULL,
    filters jsonb DEFAULT '{}'::jsonb NOT NULL,
    answer_summary text,
    retrieved_chunk_ids jsonb DEFAULT '[]'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.query_logs OWNER TO medical_audit_kb;

--
-- Name: source_documents; Type: TABLE; Schema: public; Owner: medical_audit_kb
--

CREATE TABLE public.source_documents (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    source_package_version_id uuid NOT NULL,
    source_collection text NOT NULL,
    relative_path text NOT NULL,
    absolute_path text,
    file_name text NOT NULL,
    file_ext text NOT NULL,
    media_type text NOT NULL,
    sha256 character(64) NOT NULL,
    size_bytes bigint NOT NULL,
    status text NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    discovered_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_source_documents_sha256_length CHECK ((length(sha256) = 64)),
    CONSTRAINT ck_source_documents_size_non_negative CHECK ((size_bytes >= 0))
);


ALTER TABLE public.source_documents OWNER TO medical_audit_kb;

--
-- Name: source_package_versions; Type: TABLE; Schema: public; Owner: medical_audit_kb
--

CREATE TABLE public.source_package_versions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    version_key text NOT NULL,
    source_root_path text NOT NULL,
    description text,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.source_package_versions OWNER TO medical_audit_kb;

--
-- Data for Name: chunk_embeddings; Type: TABLE DATA; Schema: public; Owner: medical_audit_kb
--

COPY public.chunk_embeddings (id, chunk_id, provider, model_name, provider_version, dimension, embedding, created_at) FROM stdin;
\.


--
-- Data for Name: document_chunks; Type: TABLE DATA; Schema: public; Owner: medical_audit_kb
--

COPY public.document_chunks (id, source_document_id, chunk_index, text, title_path, article_number, page_number, line_start, line_end, sheet_name, row_number, token_count, locator, metadata, created_at) FROM stdin;
\.


--
-- Data for Name: failed_files; Type: TABLE DATA; Schema: public; Owner: medical_audit_kb
--

COPY public.failed_files (id, source_package_version_id, source_document_id, relative_path, error_type, error_summary, retry_count, status, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: index_jobs; Type: TABLE DATA; Schema: public; Owner: medical_audit_kb
--

COPY public.index_jobs (id, index_version_id, job_type, status, started_at, finished_at, summary, error_summary) FROM stdin;
\.


--
-- Data for Name: index_versions; Type: TABLE DATA; Schema: public; Owner: medical_audit_kb
--

COPY public.index_versions (id, source_package_version_id, version_key, status, bm25_index_path, vector_provider, vector_model, chunk_count, document_count, metadata, created_at, activated_at) FROM stdin;
\.


--
-- Data for Name: pending_files; Type: TABLE DATA; Schema: public; Owner: medical_audit_kb
--

COPY public.pending_files (id, source_package_version_id, relative_path, reason, status, metadata, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: query_logs; Type: TABLE DATA; Schema: public; Owner: medical_audit_kb
--

COPY public.query_logs (id, index_version_id, source_package_version_id, user_identifier, question, filters, answer_summary, retrieved_chunk_ids, created_at) FROM stdin;
\.


--
-- Data for Name: source_documents; Type: TABLE DATA; Schema: public; Owner: medical_audit_kb
--

COPY public.source_documents (id, source_package_version_id, source_collection, relative_path, absolute_path, file_name, file_ext, media_type, sha256, size_bytes, status, metadata, discovered_at, updated_at) FROM stdin;
\.


--
-- Data for Name: source_package_versions; Type: TABLE DATA; Schema: public; Owner: medical_audit_kb
--

COPY public.source_package_versions (id, version_key, source_root_path, description, metadata, created_at) FROM stdin;
\.


--
-- Name: chunk_embeddings chunk_embeddings_pkey; Type: CONSTRAINT; Schema: public; Owner: medical_audit_kb
--

ALTER TABLE ONLY public.chunk_embeddings
    ADD CONSTRAINT chunk_embeddings_pkey PRIMARY KEY (id);


--
-- Name: document_chunks document_chunks_pkey; Type: CONSTRAINT; Schema: public; Owner: medical_audit_kb
--

ALTER TABLE ONLY public.document_chunks
    ADD CONSTRAINT document_chunks_pkey PRIMARY KEY (id);


--
-- Name: failed_files failed_files_pkey; Type: CONSTRAINT; Schema: public; Owner: medical_audit_kb
--

ALTER TABLE ONLY public.failed_files
    ADD CONSTRAINT failed_files_pkey PRIMARY KEY (id);


--
-- Name: index_jobs index_jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: medical_audit_kb
--

ALTER TABLE ONLY public.index_jobs
    ADD CONSTRAINT index_jobs_pkey PRIMARY KEY (id);


--
-- Name: index_versions index_versions_pkey; Type: CONSTRAINT; Schema: public; Owner: medical_audit_kb
--

ALTER TABLE ONLY public.index_versions
    ADD CONSTRAINT index_versions_pkey PRIMARY KEY (id);


--
-- Name: index_versions index_versions_version_key_key; Type: CONSTRAINT; Schema: public; Owner: medical_audit_kb
--

ALTER TABLE ONLY public.index_versions
    ADD CONSTRAINT index_versions_version_key_key UNIQUE (version_key);


--
-- Name: pending_files pending_files_pkey; Type: CONSTRAINT; Schema: public; Owner: medical_audit_kb
--

ALTER TABLE ONLY public.pending_files
    ADD CONSTRAINT pending_files_pkey PRIMARY KEY (id);


--
-- Name: query_logs query_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: medical_audit_kb
--

ALTER TABLE ONLY public.query_logs
    ADD CONSTRAINT query_logs_pkey PRIMARY KEY (id);


--
-- Name: source_documents source_documents_pkey; Type: CONSTRAINT; Schema: public; Owner: medical_audit_kb
--

ALTER TABLE ONLY public.source_documents
    ADD CONSTRAINT source_documents_pkey PRIMARY KEY (id);


--
-- Name: source_package_versions source_package_versions_pkey; Type: CONSTRAINT; Schema: public; Owner: medical_audit_kb
--

ALTER TABLE ONLY public.source_package_versions
    ADD CONSTRAINT source_package_versions_pkey PRIMARY KEY (id);


--
-- Name: source_package_versions source_package_versions_version_key_key; Type: CONSTRAINT; Schema: public; Owner: medical_audit_kb
--

ALTER TABLE ONLY public.source_package_versions
    ADD CONSTRAINT source_package_versions_version_key_key UNIQUE (version_key);


--
-- Name: chunk_embeddings uq_chunk_embeddings_provider; Type: CONSTRAINT; Schema: public; Owner: medical_audit_kb
--

ALTER TABLE ONLY public.chunk_embeddings
    ADD CONSTRAINT uq_chunk_embeddings_provider UNIQUE (chunk_id, provider, model_name, provider_version);


--
-- Name: document_chunks uq_document_chunks_document_index; Type: CONSTRAINT; Schema: public; Owner: medical_audit_kb
--

ALTER TABLE ONLY public.document_chunks
    ADD CONSTRAINT uq_document_chunks_document_index UNIQUE (source_document_id, chunk_index);


--
-- Name: source_documents uq_source_documents_version_path; Type: CONSTRAINT; Schema: public; Owner: medical_audit_kb
--

ALTER TABLE ONLY public.source_documents
    ADD CONSTRAINT uq_source_documents_version_path UNIQUE (source_package_version_id, relative_path);


--
-- Name: idx_chunk_embeddings_chunk; Type: INDEX; Schema: public; Owner: medical_audit_kb
--

CREATE INDEX idx_chunk_embeddings_chunk ON public.chunk_embeddings USING btree (chunk_id);


--
-- Name: idx_chunk_embeddings_kimi_cosine_hnsw; Type: INDEX; Schema: public; Owner: medical_audit_kb
--

CREATE INDEX idx_chunk_embeddings_kimi_cosine_hnsw ON public.chunk_embeddings USING hnsw (embedding public.vector_cosine_ops) WHERE ((provider = 'openai'::text) AND (model_name = 'kimi-for-coding'::text) AND (provider_version = 'v1'::text) AND (dimension = 1024));


--
-- Name: idx_document_chunks_article_number; Type: INDEX; Schema: public; Owner: medical_audit_kb
--

CREATE INDEX idx_document_chunks_article_number ON public.document_chunks USING btree (article_number);


--
-- Name: idx_document_chunks_document; Type: INDEX; Schema: public; Owner: medical_audit_kb
--

CREATE INDEX idx_document_chunks_document ON public.document_chunks USING btree (source_document_id);


--
-- Name: idx_document_chunks_locator_gin; Type: INDEX; Schema: public; Owner: medical_audit_kb
--

CREATE INDEX idx_document_chunks_locator_gin ON public.document_chunks USING gin (locator);


--
-- Name: idx_document_chunks_metadata_gin; Type: INDEX; Schema: public; Owner: medical_audit_kb
--

CREATE INDEX idx_document_chunks_metadata_gin ON public.document_chunks USING gin (metadata);


--
-- Name: idx_document_chunks_page_number; Type: INDEX; Schema: public; Owner: medical_audit_kb
--

CREATE INDEX idx_document_chunks_page_number ON public.document_chunks USING btree (page_number);


--
-- Name: idx_failed_files_status; Type: INDEX; Schema: public; Owner: medical_audit_kb
--

CREATE INDEX idx_failed_files_status ON public.failed_files USING btree (status);


--
-- Name: idx_index_jobs_status; Type: INDEX; Schema: public; Owner: medical_audit_kb
--

CREATE INDEX idx_index_jobs_status ON public.index_jobs USING btree (status);


--
-- Name: idx_index_versions_package; Type: INDEX; Schema: public; Owner: medical_audit_kb
--

CREATE INDEX idx_index_versions_package ON public.index_versions USING btree (source_package_version_id);


--
-- Name: idx_index_versions_status; Type: INDEX; Schema: public; Owner: medical_audit_kb
--

CREATE INDEX idx_index_versions_status ON public.index_versions USING btree (status);


--
-- Name: idx_pending_files_status; Type: INDEX; Schema: public; Owner: medical_audit_kb
--

CREATE INDEX idx_pending_files_status ON public.pending_files USING btree (status);


--
-- Name: idx_query_logs_created_at; Type: INDEX; Schema: public; Owner: medical_audit_kb
--

CREATE INDEX idx_query_logs_created_at ON public.query_logs USING btree (created_at);


--
-- Name: idx_query_logs_filters_gin; Type: INDEX; Schema: public; Owner: medical_audit_kb
--

CREATE INDEX idx_query_logs_filters_gin ON public.query_logs USING gin (filters);


--
-- Name: idx_source_documents_collection; Type: INDEX; Schema: public; Owner: medical_audit_kb
--

CREATE INDEX idx_source_documents_collection ON public.source_documents USING btree (source_collection);


--
-- Name: idx_source_documents_package; Type: INDEX; Schema: public; Owner: medical_audit_kb
--

CREATE INDEX idx_source_documents_package ON public.source_documents USING btree (source_package_version_id);


--
-- Name: idx_source_documents_sha256; Type: INDEX; Schema: public; Owner: medical_audit_kb
--

CREATE INDEX idx_source_documents_sha256 ON public.source_documents USING btree (sha256);


--
-- Name: idx_source_documents_status; Type: INDEX; Schema: public; Owner: medical_audit_kb
--

CREATE INDEX idx_source_documents_status ON public.source_documents USING btree (status);


--
-- Name: chunk_embeddings chunk_embeddings_chunk_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: medical_audit_kb
--

ALTER TABLE ONLY public.chunk_embeddings
    ADD CONSTRAINT chunk_embeddings_chunk_id_fkey FOREIGN KEY (chunk_id) REFERENCES public.document_chunks(id) ON DELETE CASCADE;


--
-- Name: document_chunks document_chunks_source_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: medical_audit_kb
--

ALTER TABLE ONLY public.document_chunks
    ADD CONSTRAINT document_chunks_source_document_id_fkey FOREIGN KEY (source_document_id) REFERENCES public.source_documents(id) ON DELETE CASCADE;


--
-- Name: failed_files failed_files_source_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: medical_audit_kb
--

ALTER TABLE ONLY public.failed_files
    ADD CONSTRAINT failed_files_source_document_id_fkey FOREIGN KEY (source_document_id) REFERENCES public.source_documents(id) ON DELETE SET NULL;


--
-- Name: failed_files failed_files_source_package_version_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: medical_audit_kb
--

ALTER TABLE ONLY public.failed_files
    ADD CONSTRAINT failed_files_source_package_version_id_fkey FOREIGN KEY (source_package_version_id) REFERENCES public.source_package_versions(id) ON DELETE CASCADE;


--
-- Name: index_jobs index_jobs_index_version_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: medical_audit_kb
--

ALTER TABLE ONLY public.index_jobs
    ADD CONSTRAINT index_jobs_index_version_id_fkey FOREIGN KEY (index_version_id) REFERENCES public.index_versions(id) ON DELETE SET NULL;


--
-- Name: index_versions index_versions_source_package_version_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: medical_audit_kb
--

ALTER TABLE ONLY public.index_versions
    ADD CONSTRAINT index_versions_source_package_version_id_fkey FOREIGN KEY (source_package_version_id) REFERENCES public.source_package_versions(id) ON DELETE RESTRICT;


--
-- Name: pending_files pending_files_source_package_version_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: medical_audit_kb
--

ALTER TABLE ONLY public.pending_files
    ADD CONSTRAINT pending_files_source_package_version_id_fkey FOREIGN KEY (source_package_version_id) REFERENCES public.source_package_versions(id) ON DELETE CASCADE;


--
-- Name: query_logs query_logs_index_version_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: medical_audit_kb
--

ALTER TABLE ONLY public.query_logs
    ADD CONSTRAINT query_logs_index_version_id_fkey FOREIGN KEY (index_version_id) REFERENCES public.index_versions(id) ON DELETE SET NULL;


--
-- Name: query_logs query_logs_source_package_version_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: medical_audit_kb
--

ALTER TABLE ONLY public.query_logs
    ADD CONSTRAINT query_logs_source_package_version_id_fkey FOREIGN KEY (source_package_version_id) REFERENCES public.source_package_versions(id) ON DELETE SET NULL;


--
-- Name: source_documents source_documents_source_package_version_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: medical_audit_kb
--

ALTER TABLE ONLY public.source_documents
    ADD CONSTRAINT source_documents_source_package_version_id_fkey FOREIGN KEY (source_package_version_id) REFERENCES public.source_package_versions(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict jFrwP5ZNYrGbhJfrorCtXgaVNdSOcF8GRMTZ7LWC6Iej0j4liP1mOGQ8A7diaxX
