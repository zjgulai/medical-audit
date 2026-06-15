from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from medical_audit_kb.db.models import Base, QueryLog, utc_now


class QueryHistoryStore(Protocol):
    def add_query(self, values: dict[str, object]) -> dict[str, object]:
        pass

    def list_queries(self, *, limit: int = 20) -> list[dict[str, object]]:
        pass


def try_add_query_history(
    store: QueryHistoryStore | None,
    values: dict[str, object],
) -> tuple[dict[str, object] | None, dict[str, object] | None]:
    if store is None:
        return None, None
    try:
        return store.add_query(values), None
    except Exception as exc:
        return None, _store_error_payload(exc)


def try_list_query_history(
    store: QueryHistoryStore | None,
    *,
    limit: int = 20,
) -> tuple[list[dict[str, object]] | None, dict[str, object] | None]:
    if store is None:
        return None, None
    try:
        return store.list_queries(limit=limit), None
    except Exception as exc:
        return None, _store_error_payload(exc)


@dataclass(slots=True)
class SqlAlchemyQueryHistoryStore:
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

    def add_query(self, values: dict[str, object]) -> dict[str, object]:
        log = QueryLog(
            user_identifier=_optional_str(values.get("user_identifier")),
            question=str(values["question"]),
            filters=_dict_value(values.get("filters")),
            answer_summary=_optional_str(values.get("answer_summary")),
            retrieved_chunk_ids=_string_list(values.get("retrieved_chunk_ids")),
            created_at=utc_now(),
        )
        with self._session_factory.begin() as session:
            session.add(log)
            session.flush()
            return _query_log_to_payload(log)

    def list_queries(self, *, limit: int = 20) -> list[dict[str, object]]:
        normalized_limit = max(1, min(limit, 100))
        with self._session_factory() as session:
            statement = (
                select(QueryLog)
                .order_by(QueryLog.created_at.desc())
                .limit(normalized_limit)
            )
            return [_query_log_to_payload(log) for log in session.scalars(statement).all()]


@dataclass(slots=True)
class InMemoryQueryHistoryStore:
    items: list[dict[str, object]] = field(default_factory=list)

    def add_query(self, values: dict[str, object]) -> dict[str, object]:
        now = _datetime_to_iso(utc_now())
        item: dict[str, object] = {
            "id": f"in-memory-query-{len(self.items) + 1}",
            "user_identifier": _optional_str(values.get("user_identifier")),
            "question": str(values["question"]),
            "filters": _dict_value(values.get("filters")),
            "answer_summary": _optional_str(values.get("answer_summary")),
            "retrieved_chunk_ids": _string_list(values.get("retrieved_chunk_ids")),
            "citation_count": len(_string_list(values.get("retrieved_chunk_ids"))),
            "created_at": now,
        }
        self.items.insert(0, item)
        return copy.deepcopy(item)

    def list_queries(self, *, limit: int = 20) -> list[dict[str, object]]:
        normalized_limit = max(1, min(limit, 100))
        return [copy.deepcopy(item) for item in self.items[:normalized_limit]]


def _query_log_to_payload(log: QueryLog) -> dict[str, object]:
    retrieved_chunk_ids = [str(item) for item in log.retrieved_chunk_ids]
    return {
        "id": str(log.id),
        "user_identifier": log.user_identifier,
        "question": log.question,
        "filters": copy.deepcopy(log.filters),
        "answer_summary": log.answer_summary,
        "retrieved_chunk_ids": retrieved_chunk_ids,
        "citation_count": len(retrieved_chunk_ids),
        "created_at": _datetime_to_iso(log.created_at),
    }


def _datetime_to_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _dict_value(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return copy.deepcopy(value)
    return {}


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list | tuple):
        return []
    return [str(item) for item in value]


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


def _store_error_payload(exc: Exception) -> dict[str, object]:
    return {
        "error_type": exc.__class__.__name__,
        "message": "query history store operation failed",
    }
