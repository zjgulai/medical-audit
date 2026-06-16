from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from medical_audit_kb.db.models import Base, DocumentUploadRecord, utc_now

DOCUMENT_UPLOAD_ID_PREFIX = "document-upload-"
INDEX_READINESS_BLOCKERS = (
    "virus-scan-required",
    "dlp-review-required",
    "manual-index-approval-required",
)
INDEX_READINESS_NEXT_ACTION = "complete-upload-governance"


class DocumentUploadStore(Protocol):
    def add_upload(
        self,
        *,
        file_name: str,
        extension: str,
        content: bytes,
        created_by: str | None,
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


@dataclass(slots=True)
class SqlAlchemyDocumentUploadStore:
    database_url: str
    upload_root: Path
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

    def add_upload(
        self,
        *,
        file_name: str,
        extension: str,
        content: bytes,
        created_by: str | None,
    ) -> dict[str, object]:
        now = utc_now()
        upload_key = _new_upload_key()
        sha256 = hashlib.sha256(content).hexdigest()
        storage_path = _write_retained_file(
            upload_root=self.upload_root,
            upload_key=upload_key,
            extension=extension,
            content=content,
            created_at=now,
        )
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
                "index_readiness": _default_index_readiness(),
            },
            created_at=now,
        )
        with self._session_factory.begin() as session:
            session.add(record)
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


@dataclass(slots=True)
class InMemoryDocumentUploadStore:
    upload_root: Path
    records: list[dict[str, object]] = field(default_factory=list)

    def add_upload(
        self,
        *,
        file_name: str,
        extension: str,
        content: bytes,
        created_by: str | None,
    ) -> dict[str, object]:
        now = utc_now()
        upload_key = _new_upload_key()
        storage_path = _write_retained_file(
            upload_root=self.upload_root,
            upload_key=upload_key,
            extension=extension,
            content=content,
            created_at=now,
        )
        record = {
            "id": upload_key,
            "name": file_name,
            "extension": extension,
            "size_bytes": len(content),
            "size_kb": _size_kb(len(content)),
            "sha256": hashlib.sha256(content).hexdigest(),
            "storage_path": storage_path,
            "visibility": "private",
            "status": "retained",
            "created_by": created_by,
            "created_at": _datetime_to_iso(now),
            "retention_status": "retained",
            "index_status": "not-indexed",
            "index_readiness": _default_index_readiness(),
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
        "index_readiness": _index_readiness_from_metadata(record.extra_metadata),
    }


def _default_index_readiness() -> dict[str, object]:
    return {
        "status": "blocked",
        "blockers": list(INDEX_READINESS_BLOCKERS),
        "next_action": INDEX_READINESS_NEXT_ACTION,
    }


def _index_readiness_from_metadata(metadata: dict[str, object]) -> dict[str, object]:
    value = metadata.get("index_readiness")
    if not isinstance(value, dict):
        return _default_index_readiness()

    status = value.get("status")
    blockers = value.get("blockers")
    next_action = value.get("next_action")
    if (
        status == "blocked"
        and isinstance(blockers, list)
        and all(isinstance(blocker, str) for blocker in blockers)
        and isinstance(next_action, str)
        and next_action
    ):
        return {
            "status": status,
            "blockers": blockers,
            "next_action": next_action,
        }
    return _default_index_readiness()


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
