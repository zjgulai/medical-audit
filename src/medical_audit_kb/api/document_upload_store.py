from __future__ import annotations

import copy
import hashlib
import importlib
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from importlib import util as importlib_util
from pathlib import Path
from typing import Literal, Protocol, TypedDict, cast
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
    DocumentObjectStorageSignedUrlResult,
    LocalDocumentObjectStorage,
    TencentCosDocumentObjectStorage,
    TencentCosPutObjectClient,
    TencentCosSdkClient,
    TencentCosSdkPutObjectClient,
)
from medical_audit_kb.core.config import DocumentStorageSettings
from medical_audit_kb.db.models import Base, DocumentStorageObject, DocumentUploadRecord, utc_now

DOCUMENT_UPLOAD_ID_PREFIX = "document-upload-"
DOCUMENT_STORAGE_OBJECTS_TABLE = "document_storage_objects"
DEFAULT_DOCUMENT_UPLOAD_METADATA: dict[str, object] = {
    "index_status": "not-indexed",
    "governance_status": "pending-review",
    "governance_note": "",
    "governed_by": None,
    "governed_at": None,
    "security_scan_status": "local-policy-passed",
    "security_scan_provider": "local-policy",
    "dlp_status": "clear",
    "security_findings": [],
    "personal_index_status": "not-indexed",
    "personal_indexed_at": None,
    "personal_indexed_by": None,
    "personal_index_chunk_count": 0,
    "personal_index_error": "",
}


class TencentCosSdkModule(Protocol):
    def CosConfig(self, **kwargs: object) -> object:  # noqa: N802
        pass

    def CosS3Client(self, config: object) -> TencentCosSdkClient:  # noqa: N802
        pass


class TencentCosBootstrapPreflightChecks(TypedDict):
    provider_is_tencent_cos: bool
    cos_sdk_bootstrap_enabled: bool
    cos_bucket_configured: bool
    cos_region_configured: bool
    secret_id_env_name_configured: bool
    secret_key_env_name_configured: bool
    secret_id_env_value_present: bool
    secret_key_env_value_present: bool
    qcloud_cos_available: bool


class TencentCosBootstrapSecretEnvNames(TypedDict):
    secret_id: str | None
    secret_key: str | None


class TencentCosBootstrapPreflightReport(TypedDict):
    status: Literal["pass", "blocked"]
    provider: str
    cos_bucket: str | None
    cos_region: str | None
    cos_prefix: str
    cos_sdk_bootstrap_enabled: bool
    secret_env_names: TencentCosBootstrapSecretEnvNames
    checks: TencentCosBootstrapPreflightChecks
    issues: list[str]


def tencent_cos_bootstrap_preflight_from_settings(
    settings: DocumentStorageSettings,
    *,
    environ: Mapping[str, str] | None = None,
    qcloud_cos_available: bool | None = None,
) -> TencentCosBootstrapPreflightReport:
    selected_environ = os.environ if environ is None else environ
    secret_id_env = settings.cos_secret_id_env
    secret_key_env = settings.cos_secret_key_env
    sdk_available = (
        _qcloud_cos_sdk_available() if qcloud_cos_available is None else qcloud_cos_available
    )
    checks: TencentCosBootstrapPreflightChecks = {
        "provider_is_tencent_cos": settings.provider == "tencent-cos",
        "cos_sdk_bootstrap_enabled": settings.cos_sdk_bootstrap_enabled,
        "cos_bucket_configured": bool(settings.cos_bucket),
        "cos_region_configured": bool(settings.cos_region),
        "secret_id_env_name_configured": bool(secret_id_env),
        "secret_key_env_name_configured": bool(secret_key_env),
        "secret_id_env_value_present": _env_value_present(selected_environ, secret_id_env),
        "secret_key_env_value_present": _env_value_present(selected_environ, secret_key_env),
        "qcloud_cos_available": sdk_available,
    }
    issues: list[str] = []
    if not checks["provider_is_tencent_cos"]:
        issues.append("document-storage-provider-not-tencent-cos")
    if not checks["cos_sdk_bootstrap_enabled"]:
        issues.append("cos-sdk-bootstrap-disabled")
    if not checks["cos_bucket_configured"]:
        issues.append("cos-bucket-missing")
    if not checks["cos_region_configured"]:
        issues.append("cos-region-missing")
    if not checks["secret_id_env_name_configured"]:
        issues.append("cos-secret-id-env-name-missing")
    if not checks["secret_key_env_name_configured"]:
        issues.append("cos-secret-key-env-name-missing")
    if not checks["secret_id_env_value_present"]:
        issues.append("cos-secret-id-env-value-missing")
    if not checks["secret_key_env_value_present"]:
        issues.append("cos-secret-key-env-value-missing")
    if not checks["qcloud_cos_available"]:
        issues.append("qcloud-cos-sdk-not-installed")

    return {
        "status": "pass" if not issues else "blocked",
        "provider": settings.provider,
        "cos_bucket": settings.cos_bucket,
        "cos_region": settings.cos_region,
        "cos_prefix": settings.cos_prefix,
        "cos_sdk_bootstrap_enabled": settings.cos_sdk_bootstrap_enabled,
        "secret_env_names": {
            "secret_id": secret_id_env,
            "secret_key": secret_key_env,
        },
        "checks": checks,
        "issues": issues,
    }


def tencent_cos_put_object_client_from_settings(
    settings: DocumentStorageSettings,
    *,
    environ: Mapping[str, str] | None = None,
    qcloud_cos_module: TencentCosSdkModule | None = None,
) -> TencentCosPutObjectClient | None:
    if not settings.cos_sdk_bootstrap_enabled:
        return None
    if settings.provider != "tencent-cos":
        raise ValueError("Tencent COS SDK bootstrap requires tencent-cos document storage")
    if not settings.cos_secret_id_env or not settings.cos_secret_key_env:
        raise ValueError(
            "cos_secret_id_env, cos_secret_key_env are required for Tencent COS SDK bootstrap"
        )
    if not settings.cos_region:
        raise ValueError("cos_region is required for Tencent COS SDK bootstrap")

    selected_environ = os.environ if environ is None else environ
    secret_id = selected_environ.get(settings.cos_secret_id_env, "").strip()
    secret_key = selected_environ.get(settings.cos_secret_key_env, "").strip()
    missing: list[str] = []
    if not secret_id:
        missing.append(settings.cos_secret_id_env)
    if not secret_key:
        missing.append(settings.cos_secret_key_env)
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"missing Tencent COS secret environment variables: {joined}")

    module = qcloud_cos_module or _import_qcloud_cos_module()
    config = module.CosConfig(
        Region=settings.cos_region,
        SecretId=secret_id,
        SecretKey=secret_key,
        Token=None,
        Scheme="https",
    )
    return TencentCosSdkPutObjectClient(sdk_client=module.CosS3Client(config))


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


def _import_qcloud_cos_module() -> TencentCosSdkModule:
    try:
        module = importlib.import_module("qcloud_cos")
    except ImportError as exc:
        raise RuntimeError(
            "qcloud_cos is required when Tencent COS SDK bootstrap is enabled"
        ) from exc
    return cast(TencentCosSdkModule, module)


def _qcloud_cos_sdk_available() -> bool:
    return importlib_util.find_spec("qcloud_cos") is not None


def _env_value_present(environ: Mapping[str, str], env_name: str | None) -> bool:
    if not env_name:
        return False
    return bool(environ.get(env_name, "").strip())


class DocumentUploadStore(Protocol):
    def add_upload(
        self,
        *,
        file_name: str,
        extension: str,
        content: bytes,
        created_by: str | None,
        index_readiness: dict[str, object] | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        pass

    def list_uploads(
        self,
        *,
        created_by: str | None,
        include_all: bool = False,
        scope: str | None = None,
        project_key: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, object]]:
        pass

    def get_upload(self, *, upload_id: str) -> dict[str, object] | None:
        pass

    def list_storage_objects(self, upload_key: str) -> list[dict[str, object]]:
        pass

    def create_presigned_download_url(
        self,
        *,
        storage_object: Mapping[str, object],
        expires_in_seconds: int,
    ) -> DocumentObjectStorageSignedUrlResult | None:
        pass

    def read_upload_content(self, *, upload_id: str) -> tuple[dict[str, object], bytes] | None:
        pass

    def update_governance(
        self,
        *,
        upload_id: str,
        governance_status: str,
        index_status: str,
        governed_by: str | None,
        governance_note: str,
    ) -> dict[str, object] | None:
        pass

    def update_index_readiness(
        self,
        *,
        upload_id: str,
        index_readiness: dict[str, object],
    ) -> dict[str, object] | None:
        pass

    def update_project_file_review(
        self,
        *,
        upload_id: str,
        review_status: str,
        reviewed_by: str,
        review_note: str,
    ) -> dict[str, object] | None:
        pass

    def index_upload(
        self,
        *,
        upload_id: str,
        indexed_by: str | None,
    ) -> dict[str, object] | None:
        pass

    def search_personal_index(
        self,
        *,
        query: str,
        created_by: str | None,
        include_all: bool = False,
        limit: int = 5,
    ) -> list[dict[str, object]]:
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
        metadata: Mapping[str, object] | None = None,
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
        record = DocumentUploadRecord(
            upload_key=upload_key,
            file_name=file_name,
            extension=extension,
            size_bytes=len(content),
            sha256=sha256,
            storage_path=storage_result.object_key,
            visibility="private",
            status="retained",
            created_by=created_by,
            extra_metadata={
                **DEFAULT_DOCUMENT_UPLOAD_METADATA,
                "index_readiness": readiness,
                **_local_security_metadata(extension=extension, content=content),
                **_document_scope_metadata(metadata),
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

    def index_upload(
        self,
        *,
        upload_id: str,
        indexed_by: str | None,
    ) -> dict[str, object] | None:
        with self._session_factory.begin() as session:
            record = session.scalar(
                select(DocumentUploadRecord).where(DocumentUploadRecord.upload_key == upload_id)
            )
            if record is None:
                return None
            content = _read_retained_file(
                upload_root=self.upload_root,
                storage_path=record.storage_path,
            )
            chunks, error = _extract_personal_index_chunks(
                extension=record.extension,
                content=content,
            )
            record.extra_metadata = _personal_index_metadata(
                metadata=record.extra_metadata,
                indexed_by=indexed_by,
                chunks=chunks,
                error=error,
            )
            session.add(record)
            session.flush()
            return _record_to_payload(record)

    def search_personal_index(
        self,
        *,
        query: str,
        created_by: str | None,
        include_all: bool = False,
        limit: int = 5,
    ) -> list[dict[str, object]]:
        if limit <= 0:
            return []
        matches: list[dict[str, object]] = []
        with self._session_factory() as session:
            statement = select(DocumentUploadRecord).order_by(
                DocumentUploadRecord.created_at.desc()
            )
            if not include_all:
                statement = statement.where(DocumentUploadRecord.created_by == created_by)
            statement = statement.limit(max(50, limit * 20))
            records = session.scalars(statement).all()

            for record in records:
                payload = _record_to_payload(record)
                if payload["personal_index_status"] != "indexed":
                    continue
                content = _read_retained_file(
                    upload_root=self.upload_root,
                    storage_path=record.storage_path,
                )
                chunks, _error = _extract_personal_index_chunks(
                    extension=record.extension,
                    content=content,
                )
                matches.extend(
                    _personal_index_matches(
                        query=query,
                        payload=payload,
                        chunks=chunks,
                    )
                )
        return _rank_personal_index_matches(matches, limit=limit)

    def list_uploads(
        self,
        *,
        created_by: str | None,
        include_all: bool = False,
        scope: str | None = None,
        project_key: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, object]]:
        with self._session_factory() as session:
            statement = select(DocumentUploadRecord).order_by(
                DocumentUploadRecord.created_at.desc()
            )
            if not include_all:
                statement = statement.where(DocumentUploadRecord.created_by == created_by)
            if scope is not None:
                statement = statement.where(
                    DocumentUploadRecord.extra_metadata["scope"].as_string() == scope
                )
            if project_key is not None:
                statement = statement.where(
                    DocumentUploadRecord.extra_metadata["project_key"].as_string() == project_key
                )
            statement = statement.limit(limit)
            return [_record_to_payload(record) for record in session.scalars(statement).all()]

    def get_upload(self, *, upload_id: str) -> dict[str, object] | None:
        with self._session_factory() as session:
            record = session.scalar(
                select(DocumentUploadRecord).where(DocumentUploadRecord.upload_key == upload_id)
            )
            if record is None:
                return None
            return _record_to_payload(record)

    def list_storage_objects(self, upload_key: str) -> list[dict[str, object]]:
        with self._session_factory() as session:
            if not inspect(session.connection()).has_table(DOCUMENT_STORAGE_OBJECTS_TABLE):
                return []
            records = session.scalars(
                select(DocumentStorageObject)
                .where(DocumentStorageObject.upload_key == upload_key)
                .order_by(DocumentStorageObject.created_at.asc())
            ).all()
            return [_storage_object_to_payload(record) for record in records]

    def create_presigned_download_url(
        self,
        *,
        storage_object: Mapping[str, object],
        expires_in_seconds: int,
    ) -> DocumentObjectStorageSignedUrlResult | None:
        object_storage = self.object_storage or LocalDocumentObjectStorage(self.upload_root)
        if not _storage_object_is_signable(storage_object, provider=object_storage.provider):
            return None
        object_key = str(storage_object.get("object_key") or "")
        return object_storage.create_presigned_download_url(
            object_key=object_key,
            expires_in_seconds=expires_in_seconds,
        )

    def read_upload_content(self, *, upload_id: str) -> tuple[dict[str, object], bytes] | None:
        payload = self.get_upload(upload_id=upload_id)
        if payload is None:
            return None
        content = _read_retained_file(
            upload_root=self.upload_root,
            storage_path=payload["storage_path"],
        )
        if content is None:
            return None
        return payload, content

    def update_governance(
        self,
        *,
        upload_id: str,
        governance_status: str,
        index_status: str,
        governed_by: str | None,
        governance_note: str,
    ) -> dict[str, object] | None:
        with self._session_factory.begin() as session:
            record = session.scalar(
                select(DocumentUploadRecord).where(DocumentUploadRecord.upload_key == upload_id)
            )
            if record is None:
                return None
            record.extra_metadata = {
                **DEFAULT_DOCUMENT_UPLOAD_METADATA,
                **dict(record.extra_metadata or {}),
                "governance_status": governance_status,
                "index_status": index_status,
                "governed_by": governed_by,
                "governance_note": governance_note,
                "governed_at": _datetime_to_iso(utc_now()),
            }
            session.add(record)
            session.flush()
            return _record_to_payload(record)

    def update_index_readiness(
        self,
        *,
        upload_id: str,
        index_readiness: dict[str, object],
    ) -> dict[str, object] | None:
        readiness = _copy_index_readiness(index_readiness)
        with self._session_factory.begin() as session:
            record = session.scalar(
                select(DocumentUploadRecord).where(DocumentUploadRecord.upload_key == upload_id)
            )
            if record is None:
                return None
            record.extra_metadata = {
                **DEFAULT_DOCUMENT_UPLOAD_METADATA,
                **dict(record.extra_metadata or {}),
                "index_readiness": readiness,
            }
            session.add(record)
            session.flush()
            return _record_to_payload(record)

    def update_project_file_review(
        self,
        *,
        upload_id: str,
        review_status: str,
        reviewed_by: str,
        review_note: str,
    ) -> dict[str, object] | None:
        with self._session_factory.begin() as session:
            record = session.scalar(
                select(DocumentUploadRecord).where(DocumentUploadRecord.upload_key == upload_id)
            )
            if record is None:
                return None
            metadata = dict(record.extra_metadata or {})
            if metadata.get("scope") != "project":
                return None
            record.extra_metadata = {
                **DEFAULT_DOCUMENT_UPLOAD_METADATA,
                **metadata,
                **_project_review_metadata(
                    metadata=metadata,
                    review_status=review_status,
                    reviewed_by=reviewed_by,
                    review_note=review_note,
                ),
            }
            session.add(record)
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
        metadata: Mapping[str, object] | None = None,
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
            **DEFAULT_DOCUMENT_UPLOAD_METADATA,
            "index_readiness": readiness,
            **_local_security_metadata(extension=extension, content=content),
            **_document_scope_metadata(metadata),
            "download_url": _download_url(upload_key),
        }
        self.records.insert(0, copy.deepcopy(record))
        return copy.deepcopy(record)

    def list_uploads(
        self,
        *,
        created_by: str | None,
        include_all: bool = False,
        scope: str | None = None,
        project_key: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, object]]:
        records = self.records
        if not include_all:
            records = [record for record in records if record.get("created_by") == created_by]
        if scope is not None:
            records = [record for record in records if record.get("scope") == scope]
        if project_key is not None:
            records = [
                record for record in records if record.get("project_key") == project_key
            ]
        return [copy.deepcopy(record) for record in records[:limit]]

    def get_upload(self, *, upload_id: str) -> dict[str, object] | None:
        for record in self.records:
            if record.get("id") == upload_id:
                return copy.deepcopy(record)
        return None

    def list_storage_objects(self, upload_key: str) -> list[dict[str, object]]:
        _ = upload_key
        return []

    def create_presigned_download_url(
        self,
        *,
        storage_object: Mapping[str, object],
        expires_in_seconds: int,
    ) -> DocumentObjectStorageSignedUrlResult | None:
        object_storage = self.object_storage or LocalDocumentObjectStorage(self.upload_root)
        if not _storage_object_is_signable(storage_object, provider=object_storage.provider):
            return None
        object_key = str(storage_object.get("object_key") or "")
        return object_storage.create_presigned_download_url(
            object_key=object_key,
            expires_in_seconds=expires_in_seconds,
        )

    def read_upload_content(self, *, upload_id: str) -> tuple[dict[str, object], bytes] | None:
        payload = self.get_upload(upload_id=upload_id)
        if payload is None:
            return None
        content = _read_retained_file(
            upload_root=self.upload_root,
            storage_path=payload["storage_path"],
        )
        if content is None:
            return None
        return payload, content

    def update_governance(
        self,
        *,
        upload_id: str,
        governance_status: str,
        index_status: str,
        governed_by: str | None,
        governance_note: str,
    ) -> dict[str, object] | None:
        for index, record in enumerate(self.records):
            if record.get("id") != upload_id:
                continue
            updated = {
                **DEFAULT_DOCUMENT_UPLOAD_METADATA,
                **record,
                "governance_status": governance_status,
                "index_status": index_status,
                "governed_by": governed_by,
                "governance_note": governance_note,
                "governed_at": _datetime_to_iso(utc_now()),
            }
            self.records[index] = copy.deepcopy(updated)
            return copy.deepcopy(updated)
        return None

    def update_index_readiness(
        self,
        *,
        upload_id: str,
        index_readiness: dict[str, object],
    ) -> dict[str, object] | None:
        readiness = _copy_index_readiness(index_readiness)
        for index, record in enumerate(self.records):
            if record.get("id") != upload_id:
                continue
            updated = {
                **DEFAULT_DOCUMENT_UPLOAD_METADATA,
                **record,
                "index_readiness": readiness,
            }
            self.records[index] = copy.deepcopy(updated)
            return copy.deepcopy(updated)
        return None

    def update_project_file_review(
        self,
        *,
        upload_id: str,
        review_status: str,
        reviewed_by: str,
        review_note: str,
    ) -> dict[str, object] | None:
        for index, record in enumerate(self.records):
            if record.get("id") != upload_id or record.get("scope") != "project":
                continue
            updated = {
                **DEFAULT_DOCUMENT_UPLOAD_METADATA,
                **record,
                **_project_review_metadata(
                    metadata=record,
                    review_status=review_status,
                    reviewed_by=reviewed_by,
                    review_note=review_note,
                ),
            }
            self.records[index] = copy.deepcopy(updated)
            return copy.deepcopy(updated)
        return None

    def index_upload(
        self,
        *,
        upload_id: str,
        indexed_by: str | None,
    ) -> dict[str, object] | None:
        for index, record in enumerate(self.records):
            if record.get("id") != upload_id:
                continue
            content = _read_retained_file(
                upload_root=self.upload_root,
                storage_path=record.get("storage_path"),
            )
            chunks, error = _extract_personal_index_chunks(
                extension=str(record.get("extension") or ""),
                content=content,
            )
            updated = {
                **DEFAULT_DOCUMENT_UPLOAD_METADATA,
                **record,
                **_personal_index_metadata(
                    metadata=record,
                    indexed_by=indexed_by,
                    chunks=chunks,
                    error=error,
                ),
            }
            self.records[index] = copy.deepcopy(updated)
            return copy.deepcopy(updated)
        return None

    def search_personal_index(
        self,
        *,
        query: str,
        created_by: str | None,
        include_all: bool = False,
        limit: int = 5,
    ) -> list[dict[str, object]]:
        if limit <= 0:
            return []
        matches: list[dict[str, object]] = []
        visible_records = (
            self.records
            if include_all
            else [record for record in self.records if record.get("created_by") == created_by]
        )
        for record in visible_records[: max(50, limit * 20)]:
            if record.get("personal_index_status") != "indexed":
                continue
            content = _read_retained_file(
                upload_root=self.upload_root,
                storage_path=record.get("storage_path"),
            )
            chunks, _error = _extract_personal_index_chunks(
                extension=str(record.get("extension") or ""),
                content=content,
            )
            matches.extend(
                _personal_index_matches(
                    query=query,
                    payload=record,
                    chunks=chunks,
                )
            )
        return _rank_personal_index_matches(matches, limit=limit)


def _write_retained_file(
    *,
    upload_root: Path,
    upload_key: str,
    extension: str,
    content: bytes,
    created_at: datetime,
) -> str:
    partition = created_at.astimezone(UTC).strftime("%Y/%m/%d")
    relative_path = Path(partition) / f"{upload_key}.{extension}"
    final_path = upload_root / relative_path
    final_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = final_path.with_suffix(f"{final_path.suffix}.tmp")
    temp_path.write_bytes(content)
    temp_path.replace(final_path)
    return relative_path.as_posix()


def _read_retained_file(*, upload_root: Path, storage_path: object) -> bytes | None:
    if not isinstance(storage_path, str) or not storage_path:
        return None
    root = upload_root.resolve()
    path = (root / storage_path).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        return None
    return path.read_bytes()


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
    metadata = {**DEFAULT_DOCUMENT_UPLOAD_METADATA, **dict(record.extra_metadata or {})}
    governed_by = metadata.get("governed_by")
    governed_at = metadata.get("governed_at")
    security_findings = metadata.get("security_findings")
    personal_indexed_at = metadata.get("personal_indexed_at")
    personal_indexed_by = metadata.get("personal_indexed_by")
    payload: dict[str, object] = {
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
        "index_status": str(metadata["index_status"]),
        "index_readiness": index_readiness_from_metadata(metadata),
        "governance_status": str(metadata["governance_status"]),
        "governance_note": str(metadata["governance_note"] or ""),
        "governed_by": governed_by if isinstance(governed_by, str) else None,
        "governed_at": governed_at if isinstance(governed_at, str) else None,
        "security_scan_status": str(metadata["security_scan_status"]),
        "security_scan_provider": str(metadata["security_scan_provider"]),
        "dlp_status": str(metadata["dlp_status"]),
        "security_findings": _string_list(security_findings),
        "personal_index_status": str(metadata["personal_index_status"]),
        "personal_indexed_at": (
            personal_indexed_at if isinstance(personal_indexed_at, str) else None
        ),
        "personal_indexed_by": (
            personal_indexed_by if isinstance(personal_indexed_by, str) else None
        ),
        "personal_index_chunk_count": _int_value(metadata.get("personal_index_chunk_count")),
        "personal_index_error": str(metadata.get("personal_index_error") or ""),
        "scope": str(metadata.get("scope") or "personal"),
        "project_key": (
            str(metadata["project_key"])
            if isinstance(metadata.get("project_key"), str)
            else None
        ),
        "project_name": (
            str(metadata["project_name"])
            if isinstance(metadata.get("project_name"), str)
            else None
        ),
        "download_url": _download_url(record.upload_key),
    }
    if metadata.get("scope") == "project":
        payload.update(
            {
                "department": str(metadata.get("department") or ""),
                "document_type": str(metadata.get("document_type") or "其他"),
                "description": str(metadata.get("description") or ""),
                "replaces_upload_id": (
                    str(metadata["replaces_upload_id"])
                    if isinstance(metadata.get("replaces_upload_id"), str)
                    else None
                ),
                "project_review_status": str(
                    metadata.get("project_review_status") or "pending-review"
                ),
                "project_review_note": str(metadata.get("project_review_note") or ""),
                "project_reviewed_by": (
                    str(metadata["project_reviewed_by"])
                    if isinstance(metadata.get("project_reviewed_by"), str)
                    else None
                ),
                "project_reviewed_at": (
                    str(metadata["project_reviewed_at"])
                    if isinstance(metadata.get("project_reviewed_at"), str)
                    else None
                ),
                "project_review_history": _project_review_history(
                    metadata.get("project_review_history")
                ),
            }
        )
    return payload


def _document_scope_metadata(
    metadata: Mapping[str, object] | None,
) -> dict[str, object]:
    if metadata is None:
        return {"scope": "personal", "project_key": None, "project_name": None}
    scope = metadata.get("scope")
    project_key = metadata.get("project_key")
    project_name = metadata.get("project_name")
    if scope == "project" and isinstance(project_key, str) and project_key.strip():
        return {
            "scope": "project",
            "project_key": project_key.strip(),
            "project_name": project_name.strip()
            if isinstance(project_name, str) and project_name.strip()
            else None,
            "department": _bounded_metadata_text(metadata.get("department"), limit=128),
            "document_type": _bounded_metadata_text(
                metadata.get("document_type"), limit=64, fallback="其他"
            ),
            "description": _bounded_metadata_text(metadata.get("description"), limit=1000),
            "replaces_upload_id": _bounded_metadata_text(
                metadata.get("replaces_upload_id"), limit=128
            ) or None,
            "project_review_status": "pending-review",
            "project_review_note": "",
            "project_reviewed_by": None,
            "project_reviewed_at": None,
            "project_review_history": [],
        }
    return {"scope": "personal", "project_key": None, "project_name": None}


def _bounded_metadata_text(
    value: object,
    *,
    limit: int,
    fallback: str = "",
) -> str:
    if not isinstance(value, str):
        return fallback
    normalized = value.strip()
    return normalized[:limit] if normalized else fallback


def _project_review_history(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    history: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        status = item.get("status")
        reviewer = item.get("reviewed_by")
        reviewed_at = item.get("reviewed_at")
        if not all(isinstance(field, str) and field for field in (status, reviewer, reviewed_at)):
            continue
        history.append(
            {
                "status": status,
                "note": str(item.get("note") or ""),
                "reviewed_by": reviewer,
                "reviewed_at": reviewed_at,
            }
        )
    return history


def _project_review_metadata(
    *,
    metadata: Mapping[str, object],
    review_status: str,
    reviewed_by: str,
    review_note: str,
) -> dict[str, object]:
    reviewed_at = _datetime_to_iso(utc_now())
    history = _project_review_history(metadata.get("project_review_history"))
    history.append(
        {
            "status": review_status,
            "note": review_note,
            "reviewed_by": reviewed_by,
            "reviewed_at": reviewed_at,
        }
    )
    return {
        "project_review_status": review_status,
        "project_review_note": review_note,
        "project_reviewed_by": reviewed_by,
        "project_reviewed_at": reviewed_at,
        "project_review_history": history,
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
        "created_at": _datetime_to_iso(record.created_at),
        "updated_at": _datetime_to_iso(record.updated_at),
        "metadata": copy.deepcopy(record.extra_metadata),
    }


def _storage_object_is_signable(
    storage_object: Mapping[str, object],
    *,
    provider: str,
) -> bool:
    return (
        storage_object.get("provider") == provider
        and storage_object.get("storage_status") == "object-stored"
        and bool(str(storage_object.get("object_key") or "").strip())
    )


def _copy_index_readiness(value: dict[str, object] | None) -> dict[str, object]:
    if value is None:
        return default_index_readiness()
    return copy.deepcopy(value)


def _local_security_metadata(*, extension: str, content: bytes) -> dict[str, object]:
    findings: list[str] = []
    if extension in {"txt", "md", "csv", "pdf"}:
        findings.extend(_text_security_findings(content))
    elif extension in {"xlsx", "xlsm"}:
        findings.append("binary-office-content-requires-review")
    else:
        findings.append("unsupported-local-policy-extension")
    return {
        "security_scan_status": ("local-policy-review" if findings else "local-policy-passed"),
        "security_scan_provider": "local-policy",
        "dlp_status": "needs-review" if findings else "clear",
        "security_findings": findings,
    }


def _text_security_findings(content: bytes) -> list[str]:
    text = content.decode("utf-8", errors="ignore").lower()
    checks = {
        "sensitive-keyword:credential": (
            "password",
            "passwd",
            "token",
            "secret",
            "api_key",
            "密码",
            "口令",
        ),
        "sensitive-keyword:identity": ("身份证", "idcard", "identity card"),
        "sensitive-keyword:phone": ("手机号", "phone", "mobile"),
    }
    return [
        finding for finding, keywords in checks.items() if any(item in text for item in keywords)
    ]


def _download_url(upload_key: str) -> str:
    return f"/api/v1/documents/uploads/{upload_key}/download"


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str)]


def _int_value(value: object) -> int:
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return 0


def _personal_index_metadata(
    *,
    metadata: dict[str, object] | None,
    indexed_by: str | None,
    chunks: list[str],
    error: str,
) -> dict[str, object]:
    return {
        **DEFAULT_DOCUMENT_UPLOAD_METADATA,
        **dict(metadata or {}),
        "personal_index_status": "indexed" if chunks else "failed",
        "personal_indexed_at": _datetime_to_iso(utc_now()),
        "personal_indexed_by": indexed_by,
        "personal_index_chunk_count": len(chunks),
        "personal_index_error": error,
    }


def _extract_personal_index_chunks(
    *,
    extension: str,
    content: bytes | None,
) -> tuple[list[str], str]:
    if content is None:
        return [], "retained file is unavailable"
    if extension not in {"txt", "md", "csv", "pdf"}:
        return [], f"local personal index does not support .{extension}"
    text = _normalize_extracted_text(content.decode("utf-8", errors="ignore"))
    if not text:
        return [], "no readable text extracted by local personal indexer"
    return _chunk_text(text), ""


def _normalize_extracted_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\x00", " ")).strip()


def _chunk_text(text: str, *, max_chars: int = 1200, overlap: int = 120) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    chunks: list[str] = []
    cursor = 0
    while cursor < len(text):
        chunk = text[cursor : cursor + max_chars].strip()
        if chunk:
            chunks.append(chunk)
        if cursor + max_chars >= len(text):
            break
        cursor += max_chars - overlap
    return chunks


def _personal_index_matches(
    *,
    query: str,
    payload: dict[str, object],
    chunks: list[str],
) -> list[dict[str, object]]:
    normalized_query = _normalize_for_match(query)
    terms = _query_terms(query)
    if not normalized_query and not terms:
        return []

    matches: list[dict[str, object]] = []
    for chunk_index, chunk in enumerate(chunks):
        normalized_chunk = _normalize_for_match(chunk)
        score = 0
        if normalized_query and normalized_query in normalized_chunk:
            score += 5
        score += sum(1 for term in terms if term in normalized_chunk)
        if score <= 0:
            continue
        upload_id = str(payload.get("id") or "")
        matches.append(
            {
                "id": f"{upload_id}#chunk-{chunk_index + 1}",
                "upload_id": upload_id,
                "name": str(payload.get("name") or ""),
                "extension": str(payload.get("extension") or ""),
                "created_by": payload.get("created_by")
                if isinstance(payload.get("created_by"), str)
                else None,
                "indexed_at": payload.get("personal_indexed_at")
                if isinstance(payload.get("personal_indexed_at"), str)
                else None,
                "chunk_index": chunk_index,
                "snippet": _snippet_for_match(chunk, query=query, terms=terms),
                "score": score,
                "locator": {
                    "type": "personal-upload",
                    "upload_id": upload_id,
                    "file_name": str(payload.get("name") or ""),
                    "storage_path": str(payload.get("storage_path") or ""),
                    "chunk_index": chunk_index,
                },
            }
        )
    return matches


def _rank_personal_index_matches(
    matches: list[dict[str, object]],
    *,
    limit: int,
) -> list[dict[str, object]]:
    return sorted(
        matches,
        key=lambda item: (
            _match_score(item.get("score")),
            str(item.get("indexed_at") or ""),
        ),
        reverse=True,
    )[:limit]


def _match_score(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return 0


def _query_terms(query: str) -> list[str]:
    terms = [_normalize_for_match(item) for item in re.findall(r"[\w\u4e00-\u9fff]+", query)]
    return [item for item in terms if item]


def _normalize_for_match(value: str) -> str:
    return re.sub(r"\s+", "", value).lower()


def _snippet_for_match(chunk: str, *, query: str, terms: list[str]) -> str:
    normalized_chunk = _normalize_for_match(chunk)
    candidates = [_normalize_for_match(query), *terms]
    offsets = [
        normalized_chunk.find(candidate)
        for candidate in candidates
        if candidate and normalized_chunk.find(candidate) >= 0
    ]
    if not offsets:
        return chunk[:280]
    # Normalized offsets can drift from the original string when whitespace exists.
    # Keeping the window broad still preserves a useful human-verifiable snippet.
    start = max(0, min(offsets) - 80)
    return chunk[start : start + 280]


def _new_upload_key() -> str:
    return f"{DOCUMENT_UPLOAD_ID_PREFIX}{uuid4().hex[:12]}"


def _size_kb(size_bytes: int) -> int:
    return max(1, round(size_bytes / 1024))


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
