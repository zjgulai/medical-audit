from __future__ import annotations

from enum import StrEnum


class SourceCollection(StrEnum):
    MEDICAL_INSURANCE_CATALOG = "medical-insurance-catalog"
    SUPERVISION_RULES_KNOWLEDGE = "supervision-rules-knowledge"
    RISK_NEGATIVE_LIST = "risk-negative-list"
    MEDICAL_INSURANCE_LAWS = "medical-insurance-laws"


class DocumentStatus(StrEnum):
    INDEX_CANDIDATE = "index-candidate"
    INDEXED = "indexed"
    PENDING = "pending"
    FAILED = "failed"
    IGNORED = "ignored"


class IndexVersionStatus(StrEnum):
    BUILDING = "building"
    ACTIVE = "active"
    FAILED = "failed"
    DEPRECATED = "deprecated"


class IndexJobType(StrEnum):
    INCREMENTAL = "incremental"
    FULL_REBUILD = "full-rebuild"
    RETRY_FILE = "retry-file"


class IndexJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class FileQueueStatus(StrEnum):
    OPEN = "open"
    RETRYING = "retrying"
    RESOLVED = "resolved"
    IGNORED = "ignored"


class FileErrorType(StrEnum):
    UNSUPPORTED_TYPE = "unsupported-type"
    EXTRACTION_FAILED = "extraction-failed"
    LOW_QUALITY_TEXT = "low-quality-text"
    VALIDATION_FAILED = "validation-failed"
