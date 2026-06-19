from __future__ import annotations

import copy
import io
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
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


@dataclass(frozen=True, slots=True)
class DocumentObjectStorageSignedUrlResult:
    provider: DocumentStorageProvider
    object_key: str
    signed_url: str
    expires_at: datetime
    bucket: str | None = None
    region: str | None = None


@dataclass(frozen=True, slots=True)
class DocumentObjectStorageReadResult:
    provider: DocumentStorageProvider
    object_key: str
    content: bytes
    bucket: str | None = None
    region: str | None = None


class DocumentObjectStorage(Protocol):
    @property
    def provider(self) -> DocumentStorageProvider:
        pass

    def put_object(
        self,
        request: DocumentObjectStoragePutRequest,
    ) -> DocumentObjectStoragePutResult:
        pass

    def create_presigned_download_url(
        self,
        *,
        object_key: str,
        expires_in_seconds: int,
    ) -> DocumentObjectStorageSignedUrlResult | None:
        pass

    def read_object(
        self,
        *,
        object_key: str,
    ) -> DocumentObjectStorageReadResult:
        pass


class TencentCosPutObjectClient(Protocol):
    def put_object(
        self,
        *,
        bucket: str,
        region: str,
        object_key: str,
        content: bytes,
        content_type: str,
        metadata: dict[str, str],
        encryption_mode: str,
        kms_key_id: str | None,
        storage_class: str,
    ) -> Mapping[str, str | None]:
        pass

    def create_presigned_download_url(
        self,
        *,
        bucket: str,
        region: str,
        object_key: str,
        expires_in_seconds: int,
    ) -> str:
        pass

    def get_object(
        self,
        *,
        bucket: str,
        region: str,
        object_key: str,
    ) -> bytes:
        pass


class TencentCosSdkClient(Protocol):
    def put_object(self, **kwargs: object) -> Mapping[str, object]:
        pass

    def get_presigned_download_url(self, **kwargs: object) -> str:
        pass

    def get_object(self, **kwargs: object) -> Mapping[str, object]:
        pass


@dataclass(frozen=True, slots=True)
class TencentCosSdkPutObjectClient:
    sdk_client: TencentCosSdkClient

    def put_object(
        self,
        *,
        bucket: str,
        region: str,
        object_key: str,
        content: bytes,
        content_type: str,
        metadata: dict[str, str],
        encryption_mode: str,
        kms_key_id: str | None,
        storage_class: str,
    ) -> Mapping[str, str | None]:
        # qcloud_cos binds Region in CosConfig; its put_object call does not take Region.
        _ = region
        put_kwargs = {
            "Bucket": bucket,
            "Key": object_key,
            "Body": content,
            "ContentType": content_type,
            "StorageClass": storage_class,
            "Metadata": _cos_sdk_metadata(metadata),
        }
        put_kwargs.update(
            _cos_sdk_encryption_args(
                encryption_mode=encryption_mode,
                kms_key_id=kms_key_id,
            )
        )
        response = self.sdk_client.put_object(**put_kwargs)
        return {
            "etag": _string_mapping_value(response, "ETag"),
            "version_id": _string_mapping_value(response, "VersionId"),
        }

    def create_presigned_download_url(
        self,
        *,
        bucket: str,
        region: str,
        object_key: str,
        expires_in_seconds: int,
    ) -> str:
        # qcloud_cos binds Region in CosConfig; its presign call does not take Region.
        _ = region
        return self.sdk_client.get_presigned_download_url(
            Bucket=bucket,
            Key=object_key,
            Expired=expires_in_seconds,
        )

    def get_object(
        self,
        *,
        bucket: str,
        region: str,
        object_key: str,
    ) -> bytes:
        _ = region
        response = self.sdk_client.get_object(
            Bucket=bucket,
            Key=object_key,
        )
        return _read_cos_object_body(response)


@dataclass(frozen=True, slots=True)
class LocalDocumentObjectStorage:
    upload_root: Path
    provider: DocumentStorageProvider = "local"

    def put_object(
        self,
        request: DocumentObjectStoragePutRequest,
    ) -> DocumentObjectStoragePutResult:
        object_key = _local_object_key(
            created_at=request.created_at,
            upload_key=request.upload_key,
            extension=request.extension,
        )
        final_path = self.upload_root / object_key
        final_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = final_path.with_suffix(f"{final_path.suffix}.tmp")
        temp_path.write_bytes(request.content)
        temp_path.replace(final_path)
        return DocumentObjectStoragePutResult(
            upload_key=request.upload_key,
            provider=self.provider,
            object_key=object_key,
            sha256=request.sha256,
            size_bytes=len(request.content),
            storage_status="local-quarantine",
            metadata={
                "storage_backend": "local-filesystem",
                "file_name": request.file_name,
            },
        )

    def create_presigned_download_url(
        self,
        *,
        object_key: str,
        expires_in_seconds: int,
    ) -> DocumentObjectStorageSignedUrlResult | None:
        _ = object_key, expires_in_seconds
        return None

    def read_object(
        self,
        *,
        object_key: str,
    ) -> DocumentObjectStorageReadResult:
        relative_path = Path(object_key)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise ValueError("local object key is invalid")
        content = (self.upload_root / relative_path).read_bytes()
        return DocumentObjectStorageReadResult(
            provider=self.provider,
            object_key=object_key,
            content=content,
        )


@dataclass(frozen=True, slots=True)
class TencentCosDocumentObjectStorage:
    client: TencentCosPutObjectClient
    bucket: str
    region: str
    prefix: str
    encryption_mode: str = "sse-cos"
    kms_key_id: str | None = None
    storage_class: str = "STANDARD"
    provider: DocumentStorageProvider = "tencent-cos"

    def put_object(
        self,
        request: DocumentObjectStoragePutRequest,
    ) -> DocumentObjectStoragePutResult:
        object_key = _cos_object_key(
            prefix=self.prefix,
            created_at=request.created_at,
            upload_key=request.upload_key,
            sha256=request.sha256,
            extension=request.extension,
        )
        content_type = _content_type_for_extension(request.extension)
        response = self.client.put_object(
            bucket=self.bucket,
            region=self.region,
            object_key=object_key,
            content=request.content,
            content_type=content_type,
            metadata={
                "sha256": request.sha256,
                "upload_key": request.upload_key,
            },
            encryption_mode=self.encryption_mode,
            kms_key_id=self.kms_key_id,
            storage_class=self.storage_class,
        )
        return DocumentObjectStoragePutResult(
            upload_key=request.upload_key,
            provider=self.provider,
            bucket=self.bucket,
            region=self.region,
            object_key=object_key,
            object_version=response.get("version_id"),
            etag=response.get("etag"),
            sha256=request.sha256,
            size_bytes=len(request.content),
            storage_class=self.storage_class,
            encryption_mode=self.encryption_mode,
            storage_status="object-stored",
            metadata={
                "content_type": content_type,
                "storage_backend": "tencent-cos",
            },
        )

    def create_presigned_download_url(
        self,
        *,
        object_key: str,
        expires_in_seconds: int,
    ) -> DocumentObjectStorageSignedUrlResult | None:
        signed_url = self.client.create_presigned_download_url(
            bucket=self.bucket,
            region=self.region,
            object_key=object_key,
            expires_in_seconds=expires_in_seconds,
        )
        return DocumentObjectStorageSignedUrlResult(
            provider=self.provider,
            bucket=self.bucket,
            region=self.region,
            object_key=object_key,
            signed_url=signed_url,
            expires_at=datetime.now(UTC) + timedelta(seconds=expires_in_seconds),
        )

    def read_object(
        self,
        *,
        object_key: str,
    ) -> DocumentObjectStorageReadResult:
        content = self.client.get_object(
            bucket=self.bucket,
            region=self.region,
            object_key=object_key,
        )
        return DocumentObjectStorageReadResult(
            provider=self.provider,
            bucket=self.bucket,
            region=self.region,
            object_key=object_key,
            content=content,
        )


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


class DocumentUploadGovernanceJobSubmitter(Protocol):
    def submit(
        self,
        request: DocumentUploadGovernanceJobRequest,
    ) -> DocumentUploadGovernanceJobSubmission:
        pass


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


def _local_object_key(
    *,
    created_at: datetime,
    upload_key: str,
    extension: str,
) -> str:
    partition = created_at.astimezone(UTC).strftime("%Y/%m/%d")
    return (Path(partition) / f"{upload_key}.{extension}").as_posix()


def _cos_object_key(
    *,
    prefix: str,
    created_at: datetime,
    upload_key: str,
    sha256: str,
    extension: str,
) -> str:
    partition = created_at.astimezone(UTC).strftime("%Y/%m/%d")
    suffix = f"{sha256}.{extension.lower()}" if extension else sha256
    path = (Path(partition) / upload_key / suffix).as_posix()
    normalized_prefix = prefix.strip("/")
    if not normalized_prefix:
        return path
    return f"{normalized_prefix}/{path}"


def _content_type_for_extension(extension: str) -> str:
    return {
        "csv": "text/csv",
        "md": "text/markdown",
        "pdf": "application/pdf",
        "txt": "text/plain",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "xlsm": "application/vnd.ms-excel.sheet.macroEnabled.12",
    }.get(extension.lower(), "application/octet-stream")


def _cos_sdk_metadata(metadata: dict[str, str]) -> dict[str, str]:
    return {f"x-cos-meta-{key.replace('_', '-')}": value for key, value in metadata.items()}


def _cos_sdk_encryption_args(
    *,
    encryption_mode: str,
    kms_key_id: str | None,
) -> dict[str, str]:
    if encryption_mode == "sse-cos":
        return {"ServerSideEncryption": "AES256"}
    if encryption_mode == "sse-kms":
        args = {"ServerSideEncryption": "cos/kms"}
        if kms_key_id:
            args["SSEKMSKeyId"] = kms_key_id
        return args
    raise ValueError(f"unsupported Tencent COS encryption mode: {encryption_mode}")


def _string_mapping_value(mapping: Mapping[str, object], key: str) -> str | None:
    value = mapping.get(key)
    if isinstance(value, str):
        return value
    return None


def _read_cos_object_body(response: Mapping[str, object]) -> bytes:
    body = response.get("Body")
    if isinstance(body, bytes):
        return body
    if isinstance(body, str):
        return body.encode()
    if isinstance(body, io.BytesIO):
        return body.getvalue()
    if body is not None:
        read = getattr(body, "read", None)
        if callable(read):
            value = read()
            if isinstance(value, bytes):
                return value
            if isinstance(value, str):
                return value.encode()
        get_raw_stream = getattr(body, "get_raw_stream", None)
        if callable(get_raw_stream):
            stream = get_raw_stream()
            stream_read = getattr(stream, "read", None)
            if callable(stream_read):
                value = stream_read()
                if isinstance(value, bytes):
                    return value
                if isinstance(value, str):
                    return value.encode()
    raise RuntimeError("Tencent COS get_object response does not contain a readable body")


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
