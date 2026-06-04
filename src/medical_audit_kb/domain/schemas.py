from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from medical_audit_kb.domain.constants import (
    DocumentStatus,
    FileErrorType,
    FileQueueStatus,
    SourceCollection,
)


class SourcePackageVersionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version_key: str = Field(min_length=1, max_length=128)
    source_root_path: Path
    description: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SourceDocumentUpsert(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_package_version_id: UUID
    source_collection: SourceCollection
    relative_path: str = Field(min_length=1)
    absolute_path: str | None = None
    file_name: str = Field(min_length=1)
    file_ext: str = Field(min_length=1)
    media_type: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    size_bytes: int = Field(ge=0)
    status: DocumentStatus = DocumentStatus.INDEX_CANDIDATE
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        if any(char not in "0123456789abcdef" for char in value.lower()):
            raise ValueError("sha256 must be a hexadecimal string")
        return value.lower()


class DocumentChunkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_document_id: UUID
    chunk_index: int = Field(ge=0)
    text: str = Field(min_length=1)
    title_path: list[str] = Field(default_factory=list)
    article_number: str | None = None
    page_number: int | None = Field(default=None, ge=1)
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)
    sheet_name: str | None = None
    row_number: int | None = Field(default=None, ge=1)
    token_count: int | None = Field(default=None, ge=0)
    locator: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChunkEmbeddingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk_id: UUID
    provider: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    provider_version: str = Field(min_length=1)
    dimension: int = Field(gt=0)
    embedding: list[float] = Field(min_length=1)


class FailedFileCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_package_version_id: UUID
    source_document_id: UUID | None = None
    relative_path: str = Field(min_length=1)
    error_type: FileErrorType
    error_summary: str = Field(min_length=1)
    retry_count: int = Field(default=0, ge=0)
    status: FileQueueStatus = FileQueueStatus.OPEN


class ReviewTaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    external_task_id: str = Field(min_length=1, max_length=64)
    question: str = Field(min_length=1)
    status: str = Field(min_length=1, max_length=48)
    status_label: str = Field(min_length=1, max_length=64)
    citation_count: int = Field(default=0, ge=0)
    review_gate: str = Field(min_length=1)
    confidence_label: str = Field(min_length=1, max_length=32)
    fallback_label: str = Field(min_length=1, max_length=64)
    reviewer_note: str = ""
    conclusion: str = ""
    created_by: str | None = None
    assigned_to: str | None = None
    source: str = Field(min_length=1, max_length=64)
    dossier: dict[str, Any] = Field(default_factory=dict)


class ReviewActionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    review_task_id: UUID
    action_type: str = Field(min_length=1, max_length=64)
    from_status: str | None = Field(default=None, max_length=48)
    to_status: str | None = Field(default=None, max_length=48)
    actor: str | None = None
    note: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReviewCommentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    review_task_id: UUID
    author: str = Field(min_length=1)
    body: str = Field(min_length=1)
    visibility: str = Field(default="internal", min_length=1, max_length=32)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AuditProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    project_key: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1)
    scenario_key: str = Field(min_length=1, max_length=128)
    status: str = Field(min_length=1, max_length=48)
    owner_department: str | None = None
    created_by: str | None = None
    description: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AuditDataSnapshotCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    snapshot_key: str = Field(min_length=1, max_length=128)
    project_id: UUID
    source_batch_key: str = Field(min_length=1, max_length=128)
    time_range: dict[str, Any] = Field(default_factory=dict)
    row_counts: dict[str, Any] = Field(default_factory=dict)
    checksum: str | None = None
    status: str = Field(min_length=1, max_length=48)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AuditSnapshotRollbackCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    rollback_key: str = Field(min_length=1, max_length=128)
    project_id: UUID
    from_snapshot_id: UUID
    to_snapshot_id: UUID
    status: str = Field(min_length=1, max_length=48)
    reason: str = Field(min_length=1)
    requested_by: str | None = None
    impact_summary: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class HisSourceBatchCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    batch_key: str = Field(min_length=1, max_length=128)
    project_id: UUID
    hospital_code: str = Field(min_length=1, max_length=128)
    scenario_key: str = Field(min_length=1, max_length=128)
    source_type: str = Field(min_length=1, max_length=64)
    exported_at: datetime | None = None
    file_manifest: dict[str, Any] = Field(default_factory=dict)
    row_counts: dict[str, Any] = Field(default_factory=dict)
    checksum: str | None = None
    status: str = Field(min_length=1, max_length=48)
    metadata: dict[str, Any] = Field(default_factory=dict)


class HisTableSchemaCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_key: str = Field(min_length=1, max_length=128)
    source_batch_id: UUID
    table_name: str = Field(min_length=1, max_length=128)
    business_domain: str = Field(min_length=1, max_length=128)
    ddl_text: str = Field(min_length=1)
    ddl_hash: str = Field(min_length=1, max_length=128)
    field_dictionary: dict[str, Any] = Field(default_factory=dict)
    primary_key_fields: list[str] = Field(default_factory=list)
    time_fields: list[str] = Field(default_factory=list)
    row_count: int | None = Field(default=None, ge=0)
    status: str = Field(min_length=1, max_length=48)
    metadata: dict[str, Any] = Field(default_factory=dict)


class HisStagingRowCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_batch_id: UUID
    table_schema_id: UUID | None = None
    table_name: str = Field(min_length=1, max_length=128)
    row_number: int = Field(ge=1)
    row_data: dict[str, Any] = Field(default_factory=dict)
    row_hash: str = Field(min_length=1, max_length=128)
    status: str = Field(min_length=1, max_length=48)
    validation_errors: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class HisFieldMappingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mapping_key: str = Field(min_length=1, max_length=128)
    table_schema_id: UUID
    source_field: str = Field(min_length=1, max_length=128)
    target_domain: str = Field(min_length=1, max_length=128)
    target_field: str = Field(min_length=1, max_length=128)
    source_data_type: str | None = Field(default=None, max_length=128)
    target_data_type: str | None = Field(default=None, max_length=128)
    transform_rule: str | None = None
    is_required: bool = True
    nullable: bool = False
    deidentification_rule: str | None = None
    status: str = Field(min_length=1, max_length=48)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AuditTaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    task_key: str = Field(min_length=1, max_length=128)
    project_id: UUID
    snapshot_id: UUID
    topic: str = Field(min_length=1)
    department_scope: dict[str, Any] = Field(default_factory=dict)
    date_range: dict[str, Any] = Field(default_factory=dict)
    status: str = Field(min_length=1, max_length=48)
    created_by: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AuditRunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_key: str = Field(min_length=1, max_length=128)
    audit_task_id: UUID
    snapshot_id: UUID
    rule_version_key: str = Field(min_length=1, max_length=128)
    knowledge_index_version_key: str | None = Field(default=None, max_length=128)
    status: str = Field(min_length=1, max_length=48)
    finished_at: datetime | None = None
    summary: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AuditRuleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_key: str = Field(min_length=1, max_length=128)
    scenario_key: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1)
    status: str = Field(min_length=1, max_length=48)
    owner: str | None = None
    description: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RuleVersionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    audit_rule_id: UUID
    version_key: str = Field(min_length=1, max_length=128)
    rule_key: str = Field(min_length=1, max_length=128)
    status: str = Field(min_length=1, max_length=48)
    logic: dict[str, Any] = Field(default_factory=dict)
    evidence_links: dict[str, Any] = Field(default_factory=dict)
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    created_by: str | None = None


class AuditFindingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    finding_key: str = Field(min_length=1, max_length=128)
    audit_run_id: UUID
    audit_task_id: UUID
    rule_version_id: UUID
    snapshot_id: UUID
    status: str = Field(min_length=1, max_length=48)
    finding_type: str = Field(min_length=1, max_length=128)
    severity: str = Field(min_length=1, max_length=48)
    source_record_locator: dict[str, Any] = Field(default_factory=dict)
    calculation_trace: dict[str, Any] = Field(default_factory=dict)
    review_status: str = Field(min_length=1, max_length=48)
    review_task_id: UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class FindingEvidenceItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    audit_finding_id: UUID
    evidence_type: str = Field(min_length=1, max_length=64)
    chunk_id: UUID | None = None
    source_package_version_key: str | None = Field(default=None, max_length=128)
    index_version_key: str | None = Field(default=None, max_length=128)
    citation_id: str | None = Field(default=None, max_length=128)
    locator: dict[str, Any] = Field(default_factory=dict)
    snippet: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
