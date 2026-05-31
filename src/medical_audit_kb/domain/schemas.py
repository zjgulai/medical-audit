from __future__ import annotations

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
