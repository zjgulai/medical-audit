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

from medical_audit_kb.db.models import AnalyticsUploadRecord, Base, utc_now

ANALYTICS_UPLOAD_ID_PREFIX = "analytics-upload-"


class AnalyticsUploadStore(Protocol):
    def add_upload(
        self,
        *,
        file_name: str,
        extension: str,
        content: bytes,
        analysis_summary: dict[str, object],
        created_by: str | None,
    ) -> dict[str, object]:
        pass

    def list_uploads(
        self,
        *,
        limit: int = 20,
        created_by: str | None = None,
    ) -> list[dict[str, object]]:
        pass


@dataclass(slots=True)
class SqlAlchemyAnalyticsUploadStore:
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
        analysis_summary: dict[str, object],
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
        record = AnalyticsUploadRecord(
            upload_key=upload_key,
            file_name=file_name,
            extension=extension,
            size_bytes=len(content),
            sha256=sha256,
            storage_path=storage_path,
            sheet_name=_optional_str(analysis_summary.get("sheet_name")),
            row_count=_int_value(analysis_summary.get("row_count")),
            column_count=_int_value(analysis_summary.get("column_count")),
            empty_cell_count=_int_value(analysis_summary.get("empty_cell_count")),
            duplicate_row_count=_int_value(analysis_summary.get("duplicate_row_count")),
            status=str(analysis_summary.get("status") or "parsed"),
            created_by=created_by,
            analysis_summary=copy.deepcopy(analysis_summary),
            created_at=now,
        )
        try:
            with self._session_factory.begin() as session:
                session.add(record)
                session.flush()
                return _record_to_payload(record)
        except Exception:
            _remove_retained_file(upload_root=self.upload_root, storage_path=storage_path)
            raise

    def list_uploads(
        self,
        *,
        limit: int = 20,
        created_by: str | None = None,
    ) -> list[dict[str, object]]:
        with self._session_factory() as session:
            statement = select(AnalyticsUploadRecord)
            if created_by is not None:
                statement = statement.where(AnalyticsUploadRecord.created_by == created_by)
            statement = statement.order_by(AnalyticsUploadRecord.created_at.desc()).limit(limit)
            return [_record_to_payload(record) for record in session.scalars(statement).all()]


@dataclass(slots=True)
class InMemoryAnalyticsUploadStore:
    upload_root: Path
    records: list[dict[str, object]] = field(default_factory=list)

    def add_upload(
        self,
        *,
        file_name: str,
        extension: str,
        content: bytes,
        analysis_summary: dict[str, object],
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
            "sheet_name": _optional_str(analysis_summary.get("sheet_name")),
            "row_count": _int_value(analysis_summary.get("row_count")),
            "column_count": _int_value(analysis_summary.get("column_count")),
            "empty_cell_count": _int_value(analysis_summary.get("empty_cell_count")),
            "duplicate_row_count": _int_value(analysis_summary.get("duplicate_row_count")),
            "status": str(analysis_summary.get("status") or "parsed"),
            "created_by": created_by,
            "created_at": _datetime_to_iso(now),
            "retention_status": "retained",
            "audit_signals": _str_list(analysis_summary.get("audit_signals")),
        }
        self.records.insert(0, copy.deepcopy(record))
        return copy.deepcopy(record)

    def list_uploads(
        self,
        *,
        limit: int = 20,
        created_by: str | None = None,
    ) -> list[dict[str, object]]:
        records = self.records
        if created_by is not None:
            records = [record for record in records if record.get("created_by") == created_by]
        return [copy.deepcopy(record) for record in records[:limit]]


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


def _remove_retained_file(*, upload_root: Path, storage_path: str) -> None:
    root = upload_root.resolve()
    retained_path = (root / storage_path).resolve()
    if not retained_path.is_relative_to(root):
        raise ValueError("analytics upload path escapes upload root")
    retained_path.unlink(missing_ok=True)


def _record_to_payload(record: AnalyticsUploadRecord) -> dict[str, object]:
    return {
        "id": record.upload_key,
        "name": record.file_name,
        "extension": record.extension,
        "size_bytes": record.size_bytes,
        "size_kb": _size_kb(record.size_bytes),
        "sha256": record.sha256,
        "storage_path": record.storage_path,
        "sheet_name": record.sheet_name,
        "row_count": record.row_count,
        "column_count": record.column_count,
        "empty_cell_count": record.empty_cell_count,
        "duplicate_row_count": record.duplicate_row_count,
        "status": record.status,
        "created_by": record.created_by,
        "created_at": _datetime_to_iso(record.created_at),
        "retention_status": "retained",
        "audit_signals": _str_list(record.analysis_summary.get("audit_signals")),
    }


def _new_upload_key() -> str:
    return f"{ANALYTICS_UPLOAD_ID_PREFIX}{uuid4().hex[:12]}"


def _size_kb(size_bytes: int) -> int:
    return max(1, round(size_bytes / 1024))


def _int_value(value: object) -> int:
    if isinstance(value, int):
        return value
    return int(value) if isinstance(value, str) and value.isdigit() else 0


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


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
