from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from sqlalchemy import create_engine, inspect, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from medical_audit_kb.api.document_upload_governance import (
    default_index_readiness,
    index_readiness_from_metadata,
)
from medical_audit_kb.api.document_upload_governance_store import (
    DocumentObjectStorage,
    DocumentObjectStoragePutRequest,
    DocumentObjectStoragePutResult,
    LocalDocumentObjectStorage,
    TencentCosDocumentObjectStorage,
    TencentCosPutObjectClient,
)
from medical_audit_kb.core.config import DocumentStorageSettings
from medical_audit_kb.db.models import Base, DocumentStorageObject, DocumentUploadRecord, utc_now

DOCUMENT_UPLOAD_ID_PREFIX = "document-upload-"
DOCUMENT_STORAGE_OBJECTS_TABLE = "document_storage_objects"


def document_object_storage_from_settings(
    settings: DocumentStorageSettings,
    *,
    upload_root: Path,
    tencent_cos_client: TencentCosPutObjectClient | None = None,
) -> DocumentObjectStorage:
    if settings.provider == "local":
        return LocalDocumentObjectStorage(upload_root)

    if settings.provider == "tencent-cos":
        if tencent_cos_client is None:
            raise ValueError("tencent-cos client is required for document object storage")
        bucket = settings.cos_bucket
        region = settings.cos_region
        if not bucket or not region:
            missing = []
            if not bucket:
                missing.append("cos_bucket")
            if not region:
                missing.append("cos_region")
            joined = ", ".join(missing)
            raise ValueError(f"missing tencent-cos document storage settings: {joined}")
        return TencentCosDocumentObjectStorage(
            client=tencent_cos_client,
            bucket=bucket,
            region=region,
            prefix=settings.cos_prefix,
            encryption_mode=settings.cos_encryption,
            kms_key_id=settings.cos_kms_key_id,
            storage_class=settings.cos_storage_class,
        )

    raise ValueError(f"unsupported document storage provider: {settings.provider}")


class DocumentUploadStore(Protocol):
    def add_upload(
        self,
        *,
        file_name: str,
        extension: str,
        content: bytes,
        created_by: str | None,
        index_readiness: dict[str, object] | None = None,
    ) -> dict[str, object]:
        pass

    def list_uploads(
        self,
        *,
        created_by: str | None,
        include_all: bool = False,
        limit: int = 20,
    ) -> list[dict[str, object]]:
        pass

    def get_upload(self, upload_key: str) -> dict[str, object] | None:
        pass

    def update_index_readiness(
        self,
        *,
        upload_key: str,
        index_readiness: dict[str, object],
    ) -> dict[str, object] | None:
        pass


@dataclass(slots=True)
class SqlAlchemyDocumentUploadStore:
    database_url: str
    upload_root: Path
    create_schema: bool = False
    object_storage: DocumentObjectStorage | None = None
    record_storage_objects: bool = False
    _engine: Engine = field(init=False, repr=False)
    _session_factory: sessionmaker[Session] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.object_storage is None:
            self.object_storage = LocalDocumentObjectStorage(self.upload_root)
        self._engine = create_engine(
            _sync_database_url(self.database_url),
            connect_args=_connect_args(self.database_url),
            pool_pre_ping=True,
        )
        if self.create_schema:
            Base.metadata.create_all(self._engine)
        self._session_factory = sessionmaker(self._engine, expire_on_commit=False)

    def add_upload(
        self,
        *,
        file_name: str,
        extension: str,
        content: bytes,
        created_by: str | None,
        index_readiness: dict[str, object] | None = None,
    ) -> dict[str, object]:
        now = utc_now()
        upload_key = _new_upload_key()
        sha256 = hashlib.sha256(content).hexdigest()
        readiness = _copy_index_readiness(index_readiness)
        object_storage = self.object_storage or LocalDocumentObjectStorage(self.upload_root)
        storage_result = object_storage.put_object(
            DocumentObjectStoragePutRequest(
                upload_key=upload_key,
                file_name=file_name,
                extension=extension,
                content=content,
                sha256=sha256,
                created_at=now,
            )
        )
        storage_path = storage_result.object_key
        record = DocumentUploadRecord(
            upload_key=upload_key,
            file_name=file_name,
            extension=extension,
            size_bytes=len(content),
            sha256=sha256,
            storage_path=storage_path,
            visibility="private",
            status="retained",
            created_by=created_by,
            extra_metadata={
                "index_status": "not-indexed",
                "index_readiness": readiness,
            },
            created_at=now,
        )
        with self._session_factory.begin() as session:
            session.add(record)
            session.flush()
            if self.record_storage_objects:
                session.add(_storage_object_record_from_result(storage_result))
            session.flush()
            return _record_to_payload(record)

    def list_uploads(
        self,
        *,
        created_by: str | None,
        include_all: bool = False,
        limit: int = 20,
    ) -> list[dict[str, object]]:
        with self._session_factory() as session:
            statement = select(DocumentUploadRecord).order_by(
                DocumentUploadRecord.created_at.desc()
            )
            if not include_all:
                statement = statement.where(DocumentUploadRecord.created_by == created_by)
            statement = statement.limit(limit)
            return [_record_to_payload(record) for record in session.scalars(statement).all()]

    def get_upload(self, upload_key: str) -> dict[str, object] | None:
        with self._session_factory() as session:
            record = session.scalars(
                select(DocumentUploadRecord).where(DocumentUploadRecord.upload_key == upload_key)
            ).one_or_none()
            if record is None:
                return None
            return _record_to_payload(record)

    def update_index_readiness(
        self,
        *,
        upload_key: str,
        index_readiness: dict[str, object],
    ) -> dict[str, object] | None:
        readiness = _copy_index_readiness(index_readiness)
        with self._session_factory.begin() as session:
            record = session.scalars(
                select(DocumentUploadRecord).where(DocumentUploadRecord.upload_key == upload_key)
            ).one_or_none()
            if record is None:
                return None
            metadata = dict(record.extra_metadata)
            metadata["index_status"] = str(metadata.get("index_status") or "not-indexed")
            metadata["index_readiness"] = readiness
            record.extra_metadata = metadata
            session.flush()
            return _record_to_payload(record)


@dataclass(slots=True)
class InMemoryDocumentUploadStore:
    upload_root: Path
    object_storage: DocumentObjectStorage | None = None
    records: list[dict[str, object]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.object_storage is None:
            self.object_storage = LocalDocumentObjectStorage(self.upload_root)

    def add_upload(
        self,
        *,
        file_name: str,
        extension: str,
        content: bytes,
        created_by: str | None,
        index_readiness: dict[str, object] | None = None,
    ) -> dict[str, object]:
        now = utc_now()
        upload_key = _new_upload_key()
        sha256 = hashlib.sha256(content).hexdigest()
        readiness = _copy_index_readiness(index_readiness)
        object_storage = self.object_storage or LocalDocumentObjectStorage(self.upload_root)
        storage_result = object_storage.put_object(
            DocumentObjectStoragePutRequest(
                upload_key=upload_key,
                file_name=file_name,
                extension=extension,
                content=content,
                sha256=sha256,
                created_at=now,
            )
        )
        record = {
            "id": upload_key,
            "name": file_name,
            "extension": extension,
            "size_bytes": len(content),
            "size_kb": _size_kb(len(content)),
            "sha256": sha256,
            "storage_path": storage_result.object_key,
            "visibility": "private",
            "status": "retained",
            "created_by": created_by,
            "created_at": _datetime_to_iso(now),
            "retention_status": "retained",
            "index_status": "not-indexed",
            "index_readiness": readiness,
        }
        self.records.insert(0, copy.deepcopy(record))
        return copy.deepcopy(record)

    def list_uploads(
        self,
        *,
        created_by: str | None,
        include_all: bool = False,
        limit: int = 20,
    ) -> list[dict[str, object]]:
        if include_all:
            return [copy.deepcopy(record) for record in self.records[:limit]]
        owned = [record for record in self.records if record.get("created_by") == created_by]
        return [copy.deepcopy(record) for record in owned[:limit]]

    def get_upload(self, upload_key: str) -> dict[str, object] | None:
        for record in self.records:
            if record.get("id") == upload_key:
                return copy.deepcopy(record)
        return None

    def update_index_readiness(
        self,
        *,
        upload_key: str,
        index_readiness: dict[str, object],
    ) -> dict[str, object] | None:
        readiness = _copy_index_readiness(index_readiness)
        for record in self.records:
            if record.get("id") == upload_key:
                record["index_readiness"] = readiness
                return copy.deepcopy(record)
        return None


def _storage_object_record_from_result(
    result: DocumentObjectStoragePutResult,
) -> DocumentStorageObject:
    return DocumentStorageObject(
        upload_key=result.upload_key,
        provider=result.provider,
        bucket=result.bucket,
        region=result.region,
        object_key=result.object_key,
        object_version=result.object_version,
        etag=result.etag,
        sha256=result.sha256,
        size_bytes=result.size_bytes,
        storage_class=result.storage_class,
        encryption_mode=result.encryption_mode,
        storage_status=result.storage_status,
        retention_until=result.retention_until,
        extra_metadata=copy.deepcopy(result.metadata),
    )


def _record_to_payload(record: DocumentUploadRecord) -> dict[str, object]:
    return {
        "id": record.upload_key,
        "name": record.file_name,
        "extension": record.extension,
        "size_bytes": record.size_bytes,
        "size_kb": _size_kb(record.size_bytes),
        "sha256": record.sha256,
        "storage_path": record.storage_path,
        "visibility": record.visibility,
        "status": record.status,
        "created_by": record.created_by,
        "created_at": _datetime_to_iso(record.created_at),
        "retention_status": "retained",
        "index_status": str(record.extra_metadata.get("index_status") or "not-indexed"),
        "index_readiness": index_readiness_from_metadata(record.extra_metadata),
    }


def _copy_index_readiness(value: dict[str, object] | None) -> dict[str, object]:
    if value is None:
        return default_index_readiness()
    return copy.deepcopy(value)


def _new_upload_key() -> str:
    return f"{DOCUMENT_UPLOAD_ID_PREFIX}{uuid4().hex[:12]}"


def _size_kb(size_bytes: int) -> int:
    return max(1, round(size_bytes / 1024))


def _datetime_to_iso(value: datetime) -> str:
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


def document_storage_objects_schema_ready(database_url: str) -> bool:
    engine = create_engine(
        _sync_database_url(database_url),
        connect_args=_connect_args(database_url),
        pool_pre_ping=True,
    )
    try:
        with engine.connect() as connection:
            return bool(inspect(connection).has_table(DOCUMENT_STORAGE_OBJECTS_TABLE))
    except SQLAlchemyError:
        return False
    finally:
        engine.dispose()
