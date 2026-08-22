from __future__ import annotations

import copy
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import ClassVar, Protocol

from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from medical_audit_kb.db.models import Base, ReviewAction, ReviewTask, utc_now

REVIEW_TASK_ID_PREFIX = "review-task-"


class ReviewTaskNotFoundError(KeyError):
    pass


class ReviewTaskProjectScopeConflictError(ValueError):
    pass


class ReviewTaskStoreUnavailableError(RuntimeError):
    pass


def review_task_project_key(task: dict[str, object]) -> str | None:
    dossier = _dict_value(task.get("dossier"))
    draft = _dict_value(dossier.get("report_template_draft"))
    top_level_project_key = _optional_str(dossier.get("project_key"))
    draft_project_key = _optional_str(draft.get("project_key"))
    if (
        top_level_project_key is not None
        and draft_project_key is not None
        and top_level_project_key != draft_project_key
    ):
        raise ReviewTaskProjectScopeConflictError(
            "review task project scope fields are inconsistent"
        )
    return top_level_project_key or draft_project_key


class ReviewTaskStore(Protocol):
    def list_tasks(self) -> list[dict[str, object]]:
        pass

    def next_task_id(self) -> str:
        pass

    def add_task(self, task: dict[str, object]) -> dict[str, object]:
        pass

    def get_task(self, task_id: str) -> dict[str, object]:
        pass

    def update_task(self, task_id: str, values: dict[str, object]) -> dict[str, object]:
        pass

    def mutate_task(
        self,
        task_id: str,
        mutator: Callable[[dict[str, object]], dict[str, object]],
    ) -> dict[str, object]:
        pass


@dataclass(slots=True)
class SqlAlchemyReviewTaskStore:
    supports_persistent_writes: ClassVar[bool] = True
    database_url: str
    create_schema: bool = False
    _engine: Engine = field(init=False, repr=False)
    _session_factory: sessionmaker[Session] = field(init=False, repr=False)
    _lock: RLock = field(default_factory=RLock, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        self._engine = create_engine(
            _sync_database_url(self.database_url),
            connect_args=_connect_args(self.database_url),
            pool_pre_ping=True,
        )
        if self.create_schema:
            Base.metadata.create_all(self._engine)
        self._session_factory = sessionmaker(self._engine, expire_on_commit=False)

    def list_tasks(self) -> list[dict[str, object]]:
        with self._session_factory() as session:
            statement = select(ReviewTask).order_by(ReviewTask.created_at.desc())
            return [_task_to_payload(task) for task in session.scalars(statement).all()]

    def next_task_id(self) -> str:
        highest = 0
        with self._session_factory() as session:
            for task_id in session.scalars(select(ReviewTask.external_task_id)):
                if not task_id.startswith(REVIEW_TASK_ID_PREFIX):
                    continue
                suffix = task_id.removeprefix(REVIEW_TASK_ID_PREFIX)
                if suffix.isdigit():
                    highest = max(highest, int(suffix))
        return f"{REVIEW_TASK_ID_PREFIX}{highest + 1:04d}"

    def add_task(self, task: dict[str, object]) -> dict[str, object]:
        with self._session_factory.begin() as session:
            task_id = str(task.get("task_id", ""))
            if _load_task(session, task_id) is not None:
                raise ValueError(f"review task already exists: {task_id}")
            review_task = ReviewTask(
                external_task_id=task_id,
                question=str(task.get("question", "")),
                status=str(task.get("status", "pending-review")),
                status_label=str(task.get("status_label", "")),
                citation_count=_int_value(task.get("citation_count")),
                review_gate=str(task.get("review_gate", "")),
                confidence_label=str(task.get("confidence_label", "")),
                fallback_label=str(task.get("fallback_label", "")),
                reviewer_note=str(task.get("reviewer_note", "")),
                conclusion=str(task.get("conclusion", "")),
                created_by=str(task.get("created_by", "page-user")),
                assigned_to=_optional_str(task.get("assigned_to")),
                source=str(task.get("source", "chat-dossier")),
                dossier=_dict_value(task.get("dossier")),
            )
            session.add(review_task)
            session.flush()
            return _task_to_payload(review_task)

    def get_task(self, task_id: str) -> dict[str, object]:
        with self._session_factory() as session:
            task = _load_task(session, task_id)
            if task is None:
                raise ReviewTaskNotFoundError(task_id)
            return _task_to_payload(task)

    def update_task(self, task_id: str, values: dict[str, object]) -> dict[str, object]:
        return self.mutate_task(task_id, lambda _task: values)

    def mutate_task(
        self,
        task_id: str,
        mutator: Callable[[dict[str, object]], dict[str, object]],
    ) -> dict[str, object]:
        with self._lock, self._session_factory.begin() as session:
            task = _load_task(session, task_id, for_update=True)
            if task is None:
                raise ReviewTaskNotFoundError(task_id)
            values = mutator(_task_to_payload(task))
            previous_status = task.status
            if "status" in values:
                task.status = str(values["status"])
            if "status_label" in values:
                task.status_label = str(values["status_label"])
            if "reviewer_note" in values:
                task.reviewer_note = str(values["reviewer_note"])
            if "conclusion" in values:
                task.conclusion = str(values["conclusion"])
            if "assigned_to" in values:
                task.assigned_to = _optional_str(values["assigned_to"])
            if "dossier" in values:
                task.dossier = _dict_value(values["dossier"])
            task.updated_at = utc_now()
            session.add(
                ReviewAction(
                    review_task_id=task.id,
                    action_type="status-update",
                    from_status=previous_status,
                    to_status=task.status,
                    actor="page-user",
                    note=task.reviewer_note,
                    extra_metadata={"conclusion": task.conclusion},
                )
            )
            session.flush()
            return _task_to_payload(task)


@dataclass(slots=True)
class JsonFileReviewTaskStore:
    supports_persistent_writes: ClassVar[bool] = True
    path: Path
    _lock: RLock = field(default_factory=RLock, init=False, repr=False, compare=False)

    def list_tasks(self) -> list[dict[str, object]]:
        with self._lock:
            return _copy_tasks(self._read_tasks())

    def next_task_id(self) -> str:
        with self._lock:
            highest = 0
            for task in self._read_tasks():
                task_id = str(task.get("task_id", ""))
                if not task_id.startswith(REVIEW_TASK_ID_PREFIX):
                    continue
                suffix = task_id.removeprefix(REVIEW_TASK_ID_PREFIX)
                if suffix.isdigit():
                    highest = max(highest, int(suffix))
            return f"{REVIEW_TASK_ID_PREFIX}{highest + 1:04d}"

    def add_task(self, task: dict[str, object]) -> dict[str, object]:
        with self._lock:
            tasks = self._read_tasks()
            task_id = str(task.get("task_id", ""))
            if any(existing.get("task_id") == task_id for existing in tasks):
                raise ValueError(f"review task already exists: {task_id}")
            tasks.append(copy.deepcopy(task))
            self._write_tasks(tasks)
            return copy.deepcopy(task)

    def get_task(self, task_id: str) -> dict[str, object]:
        with self._lock:
            for task in self._read_tasks():
                if task.get("task_id") == task_id:
                    return copy.deepcopy(task)
        raise ReviewTaskNotFoundError(task_id)

    def update_task(self, task_id: str, values: dict[str, object]) -> dict[str, object]:
        return self.mutate_task(task_id, lambda _task: values)

    def mutate_task(
        self,
        task_id: str,
        mutator: Callable[[dict[str, object]], dict[str, object]],
    ) -> dict[str, object]:
        with self._lock:
            tasks = self._read_tasks()
            for index, task in enumerate(tasks):
                if task.get("task_id") != task_id:
                    continue
                values = mutator(copy.deepcopy(task))
                updated = {**task, **copy.deepcopy(values)}
                tasks[index] = updated
                self._write_tasks(tasks)
                return copy.deepcopy(updated)
        raise ReviewTaskNotFoundError(task_id)

    def _read_tasks(self) -> list[dict[str, object]]:
        try:
            if not self.path.exists():
                return []
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ReviewTaskStoreUnavailableError(
                "review task store could not be read"
            ) from exc
        if not isinstance(raw, dict):
            raise ReviewTaskStoreUnavailableError(
                "review task store must contain an object"
            )
        tasks = raw.get("tasks")
        if not isinstance(tasks, list):
            raise ReviewTaskStoreUnavailableError(
                "review task store must contain a tasks list"
            )
        if any(not isinstance(task, dict) for task in tasks):
            raise ReviewTaskStoreUnavailableError(
                "review task store tasks must contain only objects"
            )
        return tasks

    def _write_tasks(self, tasks: list[dict[str, object]]) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "format": "review-task-store-v1",
                "tasks": tasks,
            }
            tmp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
            tmp_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            tmp_path.replace(self.path)
        except (OSError, UnicodeError) as exc:
            raise ReviewTaskStoreUnavailableError(
                "review task store could not be written"
            ) from exc


@dataclass(slots=True)
class InMemoryReviewTaskStore:
    supports_persistent_writes: ClassVar[bool] = False
    tasks: list[dict[str, object]] = field(default_factory=list)
    _lock: RLock = field(default_factory=RLock, init=False, repr=False, compare=False)

    def list_tasks(self) -> list[dict[str, object]]:
        with self._lock:
            return _copy_tasks(self.tasks)

    def next_task_id(self) -> str:
        with self._lock:
            return f"{REVIEW_TASK_ID_PREFIX}{len(self.tasks) + 1:04d}"

    def add_task(self, task: dict[str, object]) -> dict[str, object]:
        with self._lock:
            task_id = str(task.get("task_id", ""))
            if any(existing.get("task_id") == task_id for existing in self.tasks):
                raise ValueError(f"review task already exists: {task_id}")
            self.tasks.append(copy.deepcopy(task))
            return copy.deepcopy(task)

    def get_task(self, task_id: str) -> dict[str, object]:
        with self._lock:
            for task in self.tasks:
                if task.get("task_id") == task_id:
                    return copy.deepcopy(task)
        raise ReviewTaskNotFoundError(task_id)

    def update_task(self, task_id: str, values: dict[str, object]) -> dict[str, object]:
        return self.mutate_task(task_id, lambda _task: values)

    def mutate_task(
        self,
        task_id: str,
        mutator: Callable[[dict[str, object]], dict[str, object]],
    ) -> dict[str, object]:
        with self._lock:
            for index, task in enumerate(self.tasks):
                if task.get("task_id") != task_id:
                    continue
                values = mutator(copy.deepcopy(task))
                updated = {**task, **copy.deepcopy(values)}
                self.tasks[index] = updated
                return copy.deepcopy(updated)
        raise ReviewTaskNotFoundError(task_id)


def _copy_tasks(tasks: list[dict[str, object]]) -> list[dict[str, object]]:
    return [copy.deepcopy(task) for task in tasks]


def supports_persistent_review_task_writes(store: ReviewTaskStore | None) -> bool:
    return bool(store is not None and getattr(store, "supports_persistent_writes", False))


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


def _load_task(
    session: Session,
    task_id: str,
    *,
    for_update: bool = False,
) -> ReviewTask | None:
    statement = select(ReviewTask).where(ReviewTask.external_task_id == task_id)
    if for_update:
        statement = statement.with_for_update()
    return session.scalar(statement)


def _task_to_payload(task: ReviewTask) -> dict[str, object]:
    return {
        "task_id": task.external_task_id,
        "created_at": _datetime_to_iso(task.created_at),
        "updated_at": _datetime_to_iso(task.updated_at),
        "status": task.status,
        "status_label": task.status_label,
        "question": task.question,
        "citation_count": task.citation_count,
        "review_gate": task.review_gate,
        "confidence_label": task.confidence_label,
        "fallback_label": task.fallback_label,
        "reviewer_note": task.reviewer_note,
        "conclusion": task.conclusion,
        "assigned_to": task.assigned_to,
        "created_by": task.created_by,
        "source": task.source,
        "dossier": copy.deepcopy(task.dossier),
    }


def _datetime_to_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _int_value(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return 0


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _dict_value(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return copy.deepcopy(value)
    return {}
