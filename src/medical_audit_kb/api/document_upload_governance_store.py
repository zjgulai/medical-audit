from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal, Protocol
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from medical_audit_kb.db.models import (
    Base,
    DocumentStorageObject,
    DocumentUploadGovernanceJob,
)

DocumentStorageProvider = Literal["local", "tencent-cos"]
DocumentStorageStatus = Literal["local-quarantine", "object-stored", "object-missing"]
DocumentUploadGovernanceJobType = Literal["virus-scan", "dlp-review", "object-sync"]
DocumentUploadGovernanceJobStatus = Literal[
    "pending",
    "running",
    "passed",
    "blocked",
    "failed",
    "timeout",
]

DOCUMENT_UPLOAD_GOVERNANCE_JOB_ID_PREFIX = "document-governance-job-"


@dataclass(frozen=True, slots=True)
class DocumentObjectStoragePutRequest:
    upload_key: str
    file_name: str
    extension: str
    content: bytes
    sha256: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class DocumentObjectStoragePutResult:
    upload_key: str
    provider: DocumentStorageProvider
    object_key: str
    sha256: str
    size_bytes: int
    storage_status: DocumentStorageStatus
    bucket: str | None = None
    region: str | None = None
    object_version: str | None = None
    etag: str | None = None
    storage_class: str | None = None
    encryption_mode: str | None = None
    retention_until: datetime | None = None
    metadata: dict[str, object] = field(default_factory=dict)


class DocumentObjectStorage(Protocol):
    @property
    def provider(self) -> DocumentStorageProvider:
        pass

    def put_object(
        self,
        request: DocumentObjectStoragePutRequest,
    ) -> DocumentObjectStoragePutResult:
        pass


@dataclass(frozen=True, slots=True)
class DocumentUploadGovernanceJobRequest:
    upload_key: str
    job_type: DocumentUploadGovernanceJobType
    provider: str
    object_key: str
    sha256: str
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DocumentUploadGovernanceJobSubmission:
    provider: str
    status: DocumentUploadGovernanceJobStatus = "pending"
    external_job_id: str | None = None
    result_payload: dict[str, object] = field(default_factory=dict)
    error_message: str | None = None


class DocumentVirusScanJobProvider(Protocol):
    @property
    def provider(self) -> str:
        pass

    def submit(
        self,
        request: DocumentUploadGovernanceJobRequest,
    ) -> DocumentUploadGovernanceJobSubmission:
        pass


class DocumentDlpJobProvider(Protocol):
    @property
    def provider(self) -> str:
        pass

    def submit(
        self,
        request: DocumentUploadGovernanceJobRequest,
    ) -> DocumentUploadGovernanceJobSubmission:
        pass


@dataclass(frozen=True, slots=True)
class DocumentStorageObjectCreate:
    upload_key: str
    provider: DocumentStorageProvider
    object_key: str
    sha256: str
    size_bytes: int
    storage_status: DocumentStorageStatus
    bucket: str | None = None
    region: str | None = None
    object_version: str | None = None
    etag: str | None = None
    storage_class: str | None = None
    encryption_mode: str | None = None
    retention_until: datetime | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DocumentUploadGovernanceJobCreate:
    upload_key: str
    job_type: DocumentUploadGovernanceJobType
    provider: str
    status: DocumentUploadGovernanceJobStatus = "pending"
    external_job_id: str | None = None
    result_payload: dict[str, object] = field(default_factory=dict)
    error_message: str | None = None
    attempt_count: int = 0
    next_retry_at: datetime | None = None
    finished_at: datetime | None = None


class DocumentUploadGovernanceStore(Protocol):
    def upsert_storage_object(
        self,
        payload: DocumentStorageObjectCreate,
    ) -> dict[str, object]:
        pass

    def get_storage_object(
        self,
        *,
        upload_key: str,
        provider: DocumentStorageProvider,
    ) -> dict[str, object] | None:
        pass

    def list_storage_objects(self, upload_key: str) -> list[dict[str, object]]:
        pass

    def create_governance_job(
        self,
        payload: DocumentUploadGovernanceJobCreate,
    ) -> dict[str, object]:
        pass

    def list_governance_jobs(self, upload_key: str) -> list[dict[str, object]]:
        pass

    def update_governance_job_status(
        self,
        *,
        job_key: str,
        status: DocumentUploadGovernanceJobStatus,
        result_payload: dict[str, object] | None = None,
        external_job_id: str | None = None,
        error_message: str | None = None,
        next_retry_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> dict[str, object] | None:
        pass


@dataclass(slots=True)
class SqlAlchemyDocumentUploadGovernanceStore:
    database_url: str
    create_schema: bool = False
    _engine: Engine = field(init=False, repr=False)
    _session_factory: sessionmaker[Session] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._engine = create_engine(
            _sync_database_url(self.database_url),
            connect_args=_connect_args(self.database_url),
            pool_pre_ping=True,
        )
        if self.create_schema:
            Base.metadata.create_all(self._engine)
        self._session_factory = sessionmaker(self._engine, expire_on_commit=False)

    def upsert_storage_object(
        self,
        payload: DocumentStorageObjectCreate,
    ) -> dict[str, object]:
        values = _storage_object_values(payload)
        with self._session_factory.begin() as session:
            record = session.scalars(
                select(DocumentStorageObject).where(
                    DocumentStorageObject.upload_key == payload.upload_key,
                    DocumentStorageObject.provider == payload.provider,
                )
            ).one_or_none()
            if record is None:
                record = DocumentStorageObject(**values)
                session.add(record)
            else:
                for key, value in values.items():
                    setattr(record, key, value)
            session.flush()
            return _storage_object_to_payload(record)

    def get_storage_object(
        self,
        *,
        upload_key: str,
        provider: DocumentStorageProvider,
    ) -> dict[str, object] | None:
        with self._session_factory() as session:
            record = session.scalars(
                select(DocumentStorageObject).where(
                    DocumentStorageObject.upload_key == upload_key,
                    DocumentStorageObject.provider == provider,
                )
            ).one_or_none()
            if record is None:
                return None
            return _storage_object_to_payload(record)

    def list_storage_objects(self, upload_key: str) -> list[dict[str, object]]:
        with self._session_factory() as session:
            records = session.scalars(
                select(DocumentStorageObject)
                .where(DocumentStorageObject.upload_key == upload_key)
                .order_by(DocumentStorageObject.created_at.asc())
            ).all()
            return [_storage_object_to_payload(record) for record in records]

    def create_governance_job(
        self,
        payload: DocumentUploadGovernanceJobCreate,
    ) -> dict[str, object]:
        record = DocumentUploadGovernanceJob(
            job_key=_new_governance_job_key(),
            upload_key=payload.upload_key,
            job_type=payload.job_type,
            provider=payload.provider,
            external_job_id=payload.external_job_id,
            status=payload.status,
            result_payload=copy.deepcopy(payload.result_payload),
            error_message=payload.error_message,
            attempt_count=payload.attempt_count,
            next_retry_at=payload.next_retry_at,
            finished_at=payload.finished_at,
        )
        with self._session_factory.begin() as session:
            session.add(record)
            session.flush()
            return _governance_job_to_payload(record)

    def list_governance_jobs(self, upload_key: str) -> list[dict[str, object]]:
        with self._session_factory() as session:
            records = session.scalars(
                select(DocumentUploadGovernanceJob)
                .where(DocumentUploadGovernanceJob.upload_key == upload_key)
                .order_by(DocumentUploadGovernanceJob.created_at.asc())
            ).all()
            return [_governance_job_to_payload(record) for record in records]

    def update_governance_job_status(
        self,
        *,
        job_key: str,
        status: DocumentUploadGovernanceJobStatus,
        result_payload: dict[str, object] | None = None,
        external_job_id: str | None = None,
        error_message: str | None = None,
        next_retry_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> dict[str, object] | None:
        with self._session_factory.begin() as session:
            record = session.scalars(
                select(DocumentUploadGovernanceJob).where(
                    DocumentUploadGovernanceJob.job_key == job_key
                )
            ).one_or_none()
            if record is None:
                return None
            record.status = status
            if result_payload is not None:
                record.result_payload = copy.deepcopy(result_payload)
            if external_job_id is not None:
                record.external_job_id = external_job_id
            record.error_message = error_message
            record.next_retry_at = next_retry_at
            record.finished_at = finished_at
            session.flush()
            return _governance_job_to_payload(record)


def _storage_object_values(payload: DocumentStorageObjectCreate) -> dict[str, object]:
    return {
        "upload_key": payload.upload_key,
        "provider": payload.provider,
        "bucket": payload.bucket,
        "region": payload.region,
        "object_key": payload.object_key,
        "object_version": payload.object_version,
        "etag": payload.etag,
        "sha256": payload.sha256,
        "size_bytes": payload.size_bytes,
        "storage_class": payload.storage_class,
        "encryption_mode": payload.encryption_mode,
        "storage_status": payload.storage_status,
        "retention_until": payload.retention_until,
        "extra_metadata": copy.deepcopy(payload.metadata),
    }


def _storage_object_to_payload(record: DocumentStorageObject) -> dict[str, object]:
    return {
        "upload_key": record.upload_key,
        "provider": record.provider,
        "bucket": record.bucket,
        "region": record.region,
        "object_key": record.object_key,
        "object_version": record.object_version,
        "etag": record.etag,
        "sha256": record.sha256,
        "size_bytes": record.size_bytes,
        "storage_class": record.storage_class,
        "encryption_mode": record.encryption_mode,
        "storage_status": record.storage_status,
        "retention_until": _datetime_to_iso(record.retention_until),
        "metadata": copy.deepcopy(record.extra_metadata),
        "created_at": _datetime_to_iso(record.created_at),
        "updated_at": _datetime_to_iso(record.updated_at),
    }


def _governance_job_to_payload(record: DocumentUploadGovernanceJob) -> dict[str, object]:
    return {
        "job_key": record.job_key,
        "upload_key": record.upload_key,
        "job_type": record.job_type,
        "provider": record.provider,
        "external_job_id": record.external_job_id,
        "status": record.status,
        "result_payload": copy.deepcopy(record.result_payload),
        "error_message": record.error_message,
        "attempt_count": record.attempt_count,
        "next_retry_at": _datetime_to_iso(record.next_retry_at),
        "created_at": _datetime_to_iso(record.created_at),
        "updated_at": _datetime_to_iso(record.updated_at),
        "finished_at": _datetime_to_iso(record.finished_at),
    }


def _new_governance_job_key() -> str:
    return f"{DOCUMENT_UPLOAD_GOVERNANCE_JOB_ID_PREFIX}{uuid4().hex[:12]}"


def _datetime_to_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _sync_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


def _connect_args(database_url: str) -> dict[str, object]:
    if database_url.startswith("sqlite:"):
        return {"check_same_thread": False}
    return {}
