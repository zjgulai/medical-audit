from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

REVIEW_TASK_ID_PREFIX = "review-task-"


class ReviewTaskNotFoundError(KeyError):
    pass


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


@dataclass(slots=True)
class JsonFileReviewTaskStore:
    path: Path

    def list_tasks(self) -> list[dict[str, object]]:
        return _copy_tasks(self._read_tasks())

    def next_task_id(self) -> str:
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
        tasks = self._read_tasks()
        task_id = str(task.get("task_id", ""))
        if any(existing.get("task_id") == task_id for existing in tasks):
            raise ValueError(f"review task already exists: {task_id}")
        tasks.append(copy.deepcopy(task))
        self._write_tasks(tasks)
        return copy.deepcopy(task)

    def get_task(self, task_id: str) -> dict[str, object]:
        for task in self._read_tasks():
            if task.get("task_id") == task_id:
                return copy.deepcopy(task)
        raise ReviewTaskNotFoundError(task_id)

    def update_task(self, task_id: str, values: dict[str, object]) -> dict[str, object]:
        tasks = self._read_tasks()
        for index, task in enumerate(tasks):
            if task.get("task_id") != task_id:
                continue
            updated = {**task, **copy.deepcopy(values)}
            tasks[index] = updated
            self._write_tasks(tasks)
            return copy.deepcopy(updated)
        raise ReviewTaskNotFoundError(task_id)

    def _read_tasks(self) -> list[dict[str, object]]:
        if not self.path.exists():
            return []
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"review task store must contain an object: {self.path}")
        tasks = raw.get("tasks")
        if not isinstance(tasks, list):
            raise ValueError(f"review task store must contain a tasks list: {self.path}")
        return [task for task in tasks if isinstance(task, dict)]

    def _write_tasks(self, tasks: list[dict[str, object]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "format": "review-task-store-v1",
            "tasks": tasks,
        }
        tmp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        tmp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        tmp_path.replace(self.path)


@dataclass(slots=True)
class InMemoryReviewTaskStore:
    tasks: list[dict[str, object]] = field(default_factory=list)

    def list_tasks(self) -> list[dict[str, object]]:
        return _copy_tasks(self.tasks)

    def next_task_id(self) -> str:
        return f"{REVIEW_TASK_ID_PREFIX}{len(self.tasks) + 1:04d}"

    def add_task(self, task: dict[str, object]) -> dict[str, object]:
        self.tasks.append(copy.deepcopy(task))
        return copy.deepcopy(task)

    def get_task(self, task_id: str) -> dict[str, object]:
        for task in self.tasks:
            if task.get("task_id") == task_id:
                return copy.deepcopy(task)
        raise ReviewTaskNotFoundError(task_id)

    def update_task(self, task_id: str, values: dict[str, object]) -> dict[str, object]:
        for index, task in enumerate(self.tasks):
            if task.get("task_id") != task_id:
                continue
            updated = {**task, **copy.deepcopy(values)}
            self.tasks[index] = updated
            return copy.deepcopy(updated)
        raise ReviewTaskNotFoundError(task_id)


def _copy_tasks(tasks: list[dict[str, object]]) -> list[dict[str, object]]:
    return [copy.deepcopy(task) for task in tasks]
