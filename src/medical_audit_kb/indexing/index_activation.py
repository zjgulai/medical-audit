from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

SqlParams = tuple[object, ...]


class IndexActivationError(RuntimeError):
    pass


class IndexActivationCursor(Protocol):
    def execute(self, query: str, params: SqlParams | None = None) -> object:
        pass

    def fetchone(self) -> tuple[object, ...] | None:
        pass

    def fetchall(self) -> list[tuple[object, ...]]:
        pass


@dataclass(frozen=True, slots=True)
class IndexActivationResult:
    index_version_key: str
    vector_provider: str | None
    vector_model: str | None
    previous_status: str
    deactivated_index_version_keys: tuple[str, ...]

    @property
    def success(self) -> bool:
        return True

    def to_dict(self) -> dict[str, object]:
        return {
            "success": self.success,
            "index_version_key": self.index_version_key,
            "vector_provider": self.vector_provider,
            "vector_model": self.vector_model,
            "previous_status": self.previous_status,
            "deactivated_index_version_keys": list(self.deactivated_index_version_keys),
        }


@dataclass(frozen=True, slots=True)
class IndexRollbackResult:
    index_version_key: str
    vector_provider: str | None
    vector_model: str | None
    previous_status: str
    deactivated_index_version_keys: tuple[str, ...]

    @property
    def success(self) -> bool:
        return True

    def to_dict(self) -> dict[str, object]:
        return {
            "success": self.success,
            "index_version_key": self.index_version_key,
            "vector_provider": self.vector_provider,
            "vector_model": self.vector_model,
            "previous_status": self.previous_status,
            "deactivated_index_version_keys": list(self.deactivated_index_version_keys),
        }


def activate_index_version(
    *,
    database_url: str,
    index_version_key: str,
) -> IndexActivationResult:
    import psycopg

    with psycopg.connect(_normalize_psycopg_database_url(database_url)) as connection:
        with connection.cursor() as cursor:
            result = activate_index_version_to_cursor(cursor, index_version_key)
        connection.commit()
    return result


def rollback_index_version(
    *,
    database_url: str,
    index_version_key: str,
) -> IndexRollbackResult:
    import psycopg

    with psycopg.connect(_normalize_psycopg_database_url(database_url)) as connection:
        with connection.cursor() as cursor:
            result = rollback_index_version_to_cursor(cursor, index_version_key)
        connection.commit()
    return result


def activate_index_version_to_cursor(
    cursor: IndexActivationCursor,
    index_version_key: str,
) -> IndexActivationResult:
    cursor.execute(SELECT_INDEX_VERSION_FOR_ACTIVATION_SQL, (index_version_key,))
    target = cursor.fetchone()
    if target is None:
        raise IndexActivationError(f"index version not found: {index_version_key}")

    target_id, version_key, vector_provider, vector_model, previous_status = target
    target_uuid = _uuid_value(target_id)
    provider = _optional_str(vector_provider)
    model = _optional_str(vector_model)
    status = str(previous_status)
    if status not in {"candidate", "active"}:
        raise IndexActivationError(
            f"index version must be candidate or active before activation: {status}"
        )

    cursor.execute(
        DEACTIVATE_MATCHING_ACTIVE_INDEX_VERSIONS_SQL,
        (target_uuid, provider, model),
    )
    deactivated = tuple(str(row[0]) for row in cursor.fetchall())
    cursor.execute(ACTIVATE_INDEX_VERSION_SQL, (target_uuid,))
    activated = cursor.fetchone()
    if activated is None:
        raise IndexActivationError(f"index activation failed: {index_version_key}")

    return IndexActivationResult(
        index_version_key=str(version_key),
        vector_provider=provider,
        vector_model=model,
        previous_status=status,
        deactivated_index_version_keys=deactivated,
    )


def rollback_index_version_to_cursor(
    cursor: IndexActivationCursor,
    index_version_key: str,
) -> IndexRollbackResult:
    cursor.execute(SELECT_INDEX_VERSION_FOR_ACTIVATION_SQL, (index_version_key,))
    target = cursor.fetchone()
    if target is None:
        raise IndexActivationError(f"index version not found: {index_version_key}")

    target_id, version_key, vector_provider, vector_model, previous_status = target
    target_uuid = _uuid_value(target_id)
    provider = _optional_str(vector_provider)
    model = _optional_str(vector_model)
    status = str(previous_status)
    if status not in {"inactive", "active"}:
        raise IndexActivationError(
            f"index version must be inactive or active before rollback: {status}"
        )

    cursor.execute(
        DEACTIVATE_MATCHING_ACTIVE_INDEX_VERSIONS_SQL,
        (target_uuid, provider, model),
    )
    deactivated = tuple(str(row[0]) for row in cursor.fetchall())
    cursor.execute(ACTIVATE_INDEX_VERSION_SQL, (target_uuid,))
    activated = cursor.fetchone()
    if activated is None:
        raise IndexActivationError(f"index rollback failed: {index_version_key}")

    return IndexRollbackResult(
        index_version_key=str(version_key),
        vector_provider=provider,
        vector_model=model,
        previous_status=status,
        deactivated_index_version_keys=deactivated,
    )


def render_index_activation_markdown(result: IndexActivationResult) -> str:
    report_date = datetime.now(UTC).date().isoformat()
    lines = [
        "---",
        "title: 知识库索引版本激活报告",
        "doc_type: analysis",
        "module: knowledge-query-engine",
        "topic: index-activation",
        "status: draft",
        f"created: {report_date}",
        f"updated: {report_date}",
        "owner: self",
        "source: ai",
        "---",
        "",
        "# 知识库索引版本激活报告",
        "",
        "总体状态：`PASS`",
        "",
        "## 1. 激活结果",
        "",
        "| 字段 | 值 |",
        "| --- | --- |",
        f"| `index_version_key` | `{result.index_version_key}` |",
        f"| `vector_provider` | `{result.vector_provider or 'unknown'}` |",
        f"| `vector_model` | `{result.vector_model or 'unknown'}` |",
        f"| `previous_status` | `{result.previous_status}` |",
        (
            "| `deactivated_index_version_keys` | "
            f"`{', '.join(result.deactivated_index_version_keys) or 'none'}` |"
        ),
        "",
        "## 2. 下一步",
        "",
        "重新加载 PostgreSQL 检索后端，并运行 UI smoke 与固定评测集。",
    ]
    return "\n".join(lines) + "\n"


def render_index_rollback_markdown(result: IndexRollbackResult) -> str:
    report_date = datetime.now(UTC).date().isoformat()
    lines = [
        "---",
        "title: 知识库索引版本回滚报告",
        "doc_type: analysis",
        "module: knowledge-query-engine",
        "topic: index-rollback",
        "status: draft",
        f"created: {report_date}",
        f"updated: {report_date}",
        "owner: self",
        "source: ai",
        "---",
        "",
        "# 知识库索引版本回滚报告",
        "",
        "总体状态：`PASS`",
        "",
        "## 1. 回滚结果",
        "",
        "| 字段 | 值 |",
        "| --- | --- |",
        f"| `index_version_key` | `{result.index_version_key}` |",
        f"| `vector_provider` | `{result.vector_provider or 'unknown'}` |",
        f"| `vector_model` | `{result.vector_model or 'unknown'}` |",
        f"| `previous_status` | `{result.previous_status}` |",
        (
            "| `deactivated_index_version_keys` | "
            f"`{', '.join(result.deactivated_index_version_keys) or 'none'}` |"
        ),
        "",
        "## 2. 下一步",
        "",
        "重新加载 PostgreSQL 检索后端，并运行 UI smoke 与固定评测集。",
    ]
    return "\n".join(lines) + "\n"


def index_activation_json(result: IndexActivationResult) -> str:
    return json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n"


def index_rollback_json(result: IndexRollbackResult) -> str:
    return json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n"


def _normalize_psycopg_database_url(database_url: str) -> str:
    return database_url.replace("postgresql+psycopg://", "postgresql://", 1)


def _uuid_value(value: object) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


SELECT_INDEX_VERSION_FOR_ACTIVATION_SQL = """
SELECT id, version_key, vector_provider, vector_model, status
FROM index_versions
WHERE version_key = %s
FOR UPDATE
"""

DEACTIVATE_MATCHING_ACTIVE_INDEX_VERSIONS_SQL = """
UPDATE index_versions
SET status = 'inactive'
WHERE status = 'active'
  AND id <> %s
  AND vector_provider IS NOT DISTINCT FROM %s
  AND vector_model IS NOT DISTINCT FROM %s
RETURNING version_key
"""

ACTIVATE_INDEX_VERSION_SQL = """
UPDATE index_versions
SET status = 'active',
    activated_at = now()
WHERE id = %s
RETURNING version_key
"""
