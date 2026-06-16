from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol, cast

from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from medical_audit_kb.db.models import AuditLogEvent, Base


class AuditLogStore(Protocol):
    def add_event(self, action: str, payload: dict[str, object]) -> dict[str, object]:
        pass

    def list_events(
        self,
        *,
        action: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        user_identifier: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        limit: int = 100,
    ) -> list[dict[str, object]]:
        pass


@dataclass(slots=True)
class SqlAlchemyAuditLogStore:
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

    def add_event(self, action: str, payload: dict[str, object]) -> dict[str, object]:
        normalized_payload = _json_safe_dict(payload)
        entity_type, entity_id = _entity_from_payload(action, normalized_payload)
        with self._session_factory.begin() as session:
            event = AuditLogEvent(
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                user_identifier=_optional_str(normalized_payload.get("user_identifier")),
                role=_optional_str(normalized_payload.get("role")),
                status_code=_optional_int(normalized_payload.get("status_code")),
                endpoint=_optional_str(normalized_payload.get("endpoint")),
                reason=_optional_str(normalized_payload.get("reason")),
                payload=normalized_payload,
                extra_metadata={},
            )
            session.add(event)
            session.flush()
            return _event_to_payload(event)

    def list_events(
        self,
        *,
        action: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        user_identifier: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        limit: int = 100,
    ) -> list[dict[str, object]]:
        with self._session_factory() as session:
            statement = select(AuditLogEvent).order_by(AuditLogEvent.created_at.desc())
            if action is not None:
                statement = statement.where(AuditLogEvent.action == action)
            if entity_type is not None:
                statement = statement.where(AuditLogEvent.entity_type == entity_type)
            if entity_id is not None:
                statement = statement.where(AuditLogEvent.entity_id == entity_id)
            if user_identifier is not None:
                statement = statement.where(AuditLogEvent.user_identifier == user_identifier)
            if created_from is not None:
                statement = statement.where(AuditLogEvent.created_at >= created_from)
            if created_to is not None:
                statement = statement.where(AuditLogEvent.created_at <= created_to)
            events = session.scalars(statement.limit(limit)).all()
            return [_event_to_payload(event) for event in events]


def _entity_from_payload(action: str, payload: dict[str, object]) -> tuple[str, str]:
    task_id = _optional_str(payload.get("task_id"))
    if task_id is not None:
        return "review-task", task_id
    finding_key = _optional_str(payload.get("finding_key"))
    if finding_key is not None:
        return "audit-finding", finding_key
    chunk_id = _optional_str(payload.get("chunk_id"))
    if chunk_id is not None:
        return "document-chunk", chunk_id
    upload_id = _optional_str(payload.get("upload_id"))
    if upload_id is not None:
        return "document-upload", upload_id
    index_version_key = _optional_str(payload.get("index_version_key"))
    if index_version_key is not None:
        return "index-version", index_version_key
    return "operation", action


def _event_to_payload(event: AuditLogEvent) -> dict[str, object]:
    return {
        "event_id": str(event.id),
        "action": event.action,
        "entity_type": event.entity_type,
        "entity_id": event.entity_id,
        "user_identifier": event.user_identifier,
        "role": event.role,
        "status_code": event.status_code,
        "endpoint": event.endpoint,
        "reason": event.reason,
        "payload": copy.deepcopy(event.payload),
        "metadata": copy.deepcopy(event.extra_metadata),
        "created_at": _datetime_to_iso(event.created_at),
    }


def _json_safe_dict(payload: dict[str, object]) -> dict[str, object]:
    return cast(dict[str, object], json.loads(json.dumps(payload, ensure_ascii=False, default=str)))


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _optional_int(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


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
