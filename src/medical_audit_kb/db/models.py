from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class SourcePackageVersion(Base):
    __tablename__ = "source_package_versions"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    version_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    source_root_path: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    documents: Mapped[list[SourceDocument]] = relationship(
        back_populates="source_package_version",
        cascade="all, delete-orphan",
    )


class SourceDocument(Base):
    __tablename__ = "source_documents"
    __table_args__ = (
        UniqueConstraint(
            "source_package_version_id",
            "relative_path",
            name="uq_source_documents_version_path",
        ),
        Index("idx_source_documents_collection", "source_collection"),
        Index("idx_source_documents_package", "source_package_version_id"),
        Index("idx_source_documents_sha256", "sha256"),
        Index("idx_source_documents_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    source_package_version_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("source_package_versions.id"), nullable=False
    )
    source_collection: Mapped[str] = mapped_column(String(96), nullable=False)
    relative_path: Mapped[str] = mapped_column(Text, nullable=False)
    absolute_path: Mapped[str | None] = mapped_column(Text)
    file_name: Mapped[str] = mapped_column(Text, nullable=False)
    file_ext: Mapped[str] = mapped_column(String(32), nullable=False)
    media_type: Mapped[str] = mapped_column(String(128), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(48), nullable=False)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, nullable=False, default=dict
    )
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    source_package_version: Mapped[SourcePackageVersion] = relationship(back_populates="documents")
    chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="source_document",
        cascade="all, delete-orphan",
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint(
            "source_document_id",
            "chunk_index",
            name="uq_document_chunks_document_index",
        ),
        Index("idx_document_chunks_document", "source_document_id"),
        Index("idx_document_chunks_article_number", "article_number"),
        Index("idx_document_chunks_page_number", "page_number"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    source_document_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("source_documents.id"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    title_path: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    article_number: Mapped[str | None] = mapped_column(Text)
    page_number: Mapped[int | None] = mapped_column(Integer)
    line_start: Mapped[int | None] = mapped_column(Integer)
    line_end: Mapped[int | None] = mapped_column(Integer)
    sheet_name: Mapped[str | None] = mapped_column(Text)
    row_number: Mapped[int | None] = mapped_column(Integer)
    token_count: Mapped[int | None] = mapped_column(Integer)
    locator: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    source_document: Mapped[SourceDocument] = relationship(back_populates="chunks")
    embeddings: Mapped[list[ChunkEmbedding]] = relationship(
        back_populates="chunk",
        cascade="all, delete-orphan",
    )


class ChunkEmbedding(Base):
    __tablename__ = "chunk_embeddings"
    __table_args__ = (
        UniqueConstraint(
            "chunk_id",
            "provider",
            "model_name",
            "provider_version",
            name="uq_chunk_embeddings_provider",
        ),
        Index("idx_chunk_embeddings_chunk", "chunk_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    chunk_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("document_chunks.id"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_version: Mapped[str] = mapped_column(String(128), nullable=False)
    dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    chunk: Mapped[DocumentChunk] = relationship(back_populates="embeddings")


class IndexVersion(Base):
    __tablename__ = "index_versions"
    __table_args__ = (
        Index("idx_index_versions_package", "source_package_version_id"),
        Index("idx_index_versions_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    source_package_version_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("source_package_versions.id"), nullable=False
    )
    version_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(48), nullable=False)
    bm25_index_path: Mapped[str | None] = mapped_column(Text)
    vector_provider: Mapped[str | None] = mapped_column(String(64))
    vector_model: Mapped[str | None] = mapped_column(String(128))
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    document_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class IndexJob(Base):
    __tablename__ = "index_jobs"
    __table_args__ = (Index("idx_index_jobs_status", "status"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    index_version_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("index_versions.id")
    )
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(48), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    error_summary: Mapped[str | None] = mapped_column(Text)


class FailedFile(Base):
    __tablename__ = "failed_files"
    __table_args__ = (Index("idx_failed_files_status", "status"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    source_package_version_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("source_package_versions.id"), nullable=False
    )
    source_document_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("source_documents.id")
    )
    relative_path: Mapped[str] = mapped_column(Text, nullable=False)
    error_type: Mapped[str] = mapped_column(String(64), nullable=False)
    error_summary: Mapped[str] = mapped_column(Text, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(48), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class PendingFile(Base):
    __tablename__ = "pending_files"
    __table_args__ = (Index("idx_pending_files_status", "status"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    source_package_version_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("source_package_versions.id"), nullable=False
    )
    relative_path: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(48), nullable=False)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class QueryLog(Base):
    __tablename__ = "query_logs"
    __table_args__ = (Index("idx_query_logs_created_at", "created_at"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    index_version_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("index_versions.id")
    )
    source_package_version_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("source_package_versions.id")
    )
    user_identifier: Mapped[str | None] = mapped_column(Text)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    filters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    answer_summary: Mapped[str | None] = mapped_column(Text)
    retrieved_chunk_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class IndexEvaluationRun(Base):
    __tablename__ = "index_evaluation_runs"
    __table_args__ = (
        Index("idx_index_evaluation_runs_created_at", "created_at"),
        Index("idx_index_evaluation_runs_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(48), nullable=False)
    report_path: Mapped[str] = mapped_column(Text, nullable=False)
    retrieval_case_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    answer_case_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ui_smoke_success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    search_backend: Mapped[str] = mapped_column(String(48), nullable=False)
    search_backend_details: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    request: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    report: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class ReviewTask(Base):
    __tablename__ = "review_tasks"
    __table_args__ = (
        Index("idx_review_tasks_status", "status"),
        Index("idx_review_tasks_created_at", "created_at"),
        Index("idx_review_tasks_created_by", "created_by"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    external_task_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(48), nullable=False)
    status_label: Mapped[str] = mapped_column(String(64), nullable=False)
    citation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    review_gate: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_label: Mapped[str] = mapped_column(String(32), nullable=False)
    fallback_label: Mapped[str] = mapped_column(String(64), nullable=False)
    reviewer_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    conclusion: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by: Mapped[str | None] = mapped_column(Text)
    assigned_to: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    dossier: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    actions: Mapped[list[ReviewAction]] = relationship(
        back_populates="review_task",
        cascade="all, delete-orphan",
    )
    comments: Mapped[list[ReviewComment]] = relationship(
        back_populates="review_task",
        cascade="all, delete-orphan",
    )


class ReviewAction(Base):
    __tablename__ = "review_actions"
    __table_args__ = (
        Index("idx_review_actions_task", "review_task_id"),
        Index("idx_review_actions_task_created_at", "review_task_id", "created_at"),
        Index("idx_review_actions_type", "action_type"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    review_task_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("review_tasks.id"), nullable=False
    )
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(48))
    to_status: Mapped[str | None] = mapped_column(String(48))
    actor: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    review_task: Mapped[ReviewTask] = relationship(back_populates="actions")


class ReviewComment(Base):
    __tablename__ = "review_comments"
    __table_args__ = (
        Index("idx_review_comments_task", "review_task_id"),
        Index("idx_review_comments_task_created_at", "review_task_id", "created_at"),
        Index("idx_review_comments_visibility", "visibility"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    review_task_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("review_tasks.id"), nullable=False
    )
    author: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    visibility: Mapped[str] = mapped_column(String(32), nullable=False)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    review_task: Mapped[ReviewTask] = relationship(back_populates="comments")


class AuditProject(Base):
    __tablename__ = "audit_projects"
    __table_args__ = (
        Index("idx_audit_projects_status", "status"),
        Index("idx_audit_projects_scenario", "scenario_key"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    project_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    scenario_key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(48), nullable=False)
    owner_department: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    data_snapshots: Mapped[list[AuditDataSnapshot]] = relationship(back_populates="project")
    audit_tasks: Mapped[list[AuditTask]] = relationship(back_populates="project")
    his_source_batches: Mapped[list[HisSourceBatch]] = relationship(back_populates="project")


class HisSourceBatch(Base):
    __tablename__ = "his_source_batches"
    __table_args__ = (
        Index("idx_his_source_batches_project", "project_id"),
        Index("idx_his_source_batches_hospital", "hospital_code"),
        Index("idx_his_source_batches_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    batch_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("audit_projects.id", ondelete="RESTRICT"), nullable=False
    )
    hospital_code: Mapped[str] = mapped_column(String(128), nullable=False)
    scenario_key: Mapped[str] = mapped_column(String(128), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    exported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    file_manifest: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    row_counts: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    checksum: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(48), nullable=False)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    project: Mapped[AuditProject] = relationship(back_populates="his_source_batches")
    table_schemas: Mapped[list[HisTableSchema]] = relationship(
        back_populates="source_batch",
        cascade="all, delete-orphan",
    )


class HisTableSchema(Base):
    __tablename__ = "his_table_schemas"
    __table_args__ = (
        UniqueConstraint(
            "source_batch_id",
            "table_name",
            name="uq_his_table_schemas_batch_table",
        ),
        Index("idx_his_table_schemas_batch", "source_batch_id"),
        Index("idx_his_table_schemas_domain", "business_domain"),
        Index("idx_his_table_schemas_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    schema_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    source_batch_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("his_source_batches.id", ondelete="CASCADE"), nullable=False
    )
    table_name: Mapped[str] = mapped_column(String(128), nullable=False)
    business_domain: Mapped[str] = mapped_column(String(128), nullable=False)
    ddl_text: Mapped[str] = mapped_column(Text, nullable=False)
    ddl_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    field_dictionary: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    primary_key_fields: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    time_fields: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    row_count: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(48), nullable=False)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    source_batch: Mapped[HisSourceBatch] = relationship(back_populates="table_schemas")
    field_mappings: Mapped[list[HisFieldMapping]] = relationship(
        back_populates="table_schema",
        cascade="all, delete-orphan",
    )


class HisFieldMapping(Base):
    __tablename__ = "his_field_mappings"
    __table_args__ = (
        Index("idx_his_field_mappings_schema", "table_schema_id"),
        Index("idx_his_field_mappings_target", "target_domain", "target_field"),
        Index("idx_his_field_mappings_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    mapping_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    table_schema_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("his_table_schemas.id", ondelete="CASCADE"), nullable=False
    )
    source_field: Mapped[str] = mapped_column(String(128), nullable=False)
    target_domain: Mapped[str] = mapped_column(String(128), nullable=False)
    target_field: Mapped[str] = mapped_column(String(128), nullable=False)
    source_data_type: Mapped[str | None] = mapped_column(String(128))
    target_data_type: Mapped[str | None] = mapped_column(String(128))
    transform_rule: Mapped[str | None] = mapped_column(Text)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    nullable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    deidentification_rule: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(48), nullable=False)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    table_schema: Mapped[HisTableSchema] = relationship(back_populates="field_mappings")


class AuditDataSnapshot(Base):
    __tablename__ = "audit_data_snapshots"
    __table_args__ = (
        Index("idx_audit_data_snapshots_project", "project_id"),
        Index("idx_audit_data_snapshots_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    snapshot_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("audit_projects.id", ondelete="RESTRICT"), nullable=False
    )
    source_batch_key: Mapped[str] = mapped_column(String(128), nullable=False)
    time_range: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    row_counts: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    checksum: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(48), nullable=False)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    project: Mapped[AuditProject] = relationship(back_populates="data_snapshots")
    audit_tasks: Mapped[list[AuditTask]] = relationship(back_populates="snapshot")
    audit_runs: Mapped[list[AuditRun]] = relationship(back_populates="snapshot")
    findings: Mapped[list[AuditFinding]] = relationship(back_populates="snapshot")


class AuditTask(Base):
    __tablename__ = "audit_tasks"
    __table_args__ = (
        Index("idx_audit_tasks_project", "project_id"),
        Index("idx_audit_tasks_snapshot", "snapshot_id"),
        Index("idx_audit_tasks_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    task_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("audit_projects.id", ondelete="RESTRICT"), nullable=False
    )
    snapshot_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("audit_data_snapshots.id", ondelete="RESTRICT"),
        nullable=False,
    )
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    department_scope: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    date_range: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(48), nullable=False)
    created_by: Mapped[str | None] = mapped_column(Text)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    project: Mapped[AuditProject] = relationship(back_populates="audit_tasks")
    snapshot: Mapped[AuditDataSnapshot] = relationship(back_populates="audit_tasks")
    audit_runs: Mapped[list[AuditRun]] = relationship(back_populates="audit_task")
    findings: Mapped[list[AuditFinding]] = relationship(back_populates="audit_task")


class AuditRun(Base):
    __tablename__ = "audit_runs"
    __table_args__ = (
        Index("idx_audit_runs_task", "audit_task_id"),
        Index("idx_audit_runs_snapshot", "snapshot_id"),
        Index("idx_audit_runs_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    run_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    audit_task_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("audit_tasks.id", ondelete="RESTRICT"), nullable=False
    )
    snapshot_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("audit_data_snapshots.id", ondelete="RESTRICT"),
        nullable=False,
    )
    rule_version_key: Mapped[str] = mapped_column(String(128), nullable=False)
    knowledge_index_version_key: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(48), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, nullable=False, default=dict
    )

    audit_task: Mapped[AuditTask] = relationship(back_populates="audit_runs")
    snapshot: Mapped[AuditDataSnapshot] = relationship(back_populates="audit_runs")
    findings: Mapped[list[AuditFinding]] = relationship(back_populates="audit_run")


class AuditRule(Base):
    __tablename__ = "audit_rules"
    __table_args__ = (
        Index("idx_audit_rules_scenario", "scenario_key"),
        Index("idx_audit_rules_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    rule_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    scenario_key: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(48), nullable=False)
    owner: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    versions: Mapped[list[RuleVersion]] = relationship(back_populates="audit_rule")


class RuleVersion(Base):
    __tablename__ = "rule_versions"
    __table_args__ = (
        UniqueConstraint("audit_rule_id", "version_key", name="uq_rule_versions_rule_version"),
        Index("idx_rule_versions_rule", "audit_rule_id"),
        Index("idx_rule_versions_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    audit_rule_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("audit_rules.id", ondelete="RESTRICT"), nullable=False
    )
    version_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    rule_key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(48), nullable=False)
    logic: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    evidence_links: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    audit_rule: Mapped[AuditRule] = relationship(back_populates="versions")
    findings: Mapped[list[AuditFinding]] = relationship(back_populates="rule_version")


class AuditFinding(Base):
    __tablename__ = "audit_findings"
    __table_args__ = (
        Index("idx_audit_findings_run", "audit_run_id"),
        Index("idx_audit_findings_task", "audit_task_id"),
        Index("idx_audit_findings_rule_version", "rule_version_id"),
        Index("idx_audit_findings_review_status", "review_status"),
        Index("idx_audit_findings_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    finding_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    audit_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("audit_runs.id", ondelete="RESTRICT"), nullable=False
    )
    audit_task_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("audit_tasks.id", ondelete="RESTRICT"), nullable=False
    )
    rule_version_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("rule_versions.id", ondelete="RESTRICT"), nullable=False
    )
    snapshot_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("audit_data_snapshots.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(48), nullable=False)
    finding_type: Mapped[str] = mapped_column(String(128), nullable=False)
    severity: Mapped[str] = mapped_column(String(48), nullable=False)
    source_record_locator: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    calculation_trace: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    review_status: Mapped[str] = mapped_column(String(48), nullable=False)
    review_task_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("review_tasks.id", ondelete="SET NULL")
    )
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    audit_run: Mapped[AuditRun] = relationship(back_populates="findings")
    audit_task: Mapped[AuditTask] = relationship(back_populates="findings")
    rule_version: Mapped[RuleVersion] = relationship(back_populates="findings")
    snapshot: Mapped[AuditDataSnapshot] = relationship(back_populates="findings")
    evidence_items: Mapped[list[FindingEvidenceItem]] = relationship(
        back_populates="audit_finding",
        cascade="all, delete-orphan",
    )


class FindingEvidenceItem(Base):
    __tablename__ = "finding_evidence_items"
    __table_args__ = (
        Index("idx_finding_evidence_items_finding", "audit_finding_id"),
        Index("idx_finding_evidence_items_chunk", "chunk_id"),
        Index("idx_finding_evidence_items_type", "evidence_type"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    audit_finding_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("audit_findings.id", ondelete="CASCADE"), nullable=False
    )
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False)
    chunk_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("document_chunks.id", ondelete="SET NULL")
    )
    source_package_version_key: Mapped[str | None] = mapped_column(String(128))
    index_version_key: Mapped[str | None] = mapped_column(String(128))
    citation_id: Mapped[str | None] = mapped_column(String(128))
    locator: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    snippet: Mapped[str | None] = mapped_column(Text)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    audit_finding: Mapped[AuditFinding] = relationship(back_populates="evidence_items")
