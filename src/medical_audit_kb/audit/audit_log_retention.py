from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from medical_audit_kb.api.audit_log_policy import AUDIT_LOG_RETENTION_DAYS
from medical_audit_kb.db.engine import create_schema, create_session_factory
from medical_audit_kb.db.models import AuditLogEvent


class AuditLogRetentionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Literal["pass", "fail"]
    mode: Literal["dry-run", "execute"]
    execute_requested: bool
    executed: bool
    retention_days: int
    now: datetime
    cutoff: datetime
    limit: int
    limit_reached: bool
    expired_event_count: int
    archived_event_count: int
    deleted_event_count: int
    archive_output: str | None
    archive_sha256: str | None
    action_counts: dict[str, int] = Field(default_factory=dict)
    entity_type_counts: dict[str, int] = Field(default_factory=dict)
    expired_events: tuple[dict[str, object], ...]
    issues: tuple[str, ...]


async def run_audit_log_retention_to_database(
    *,
    database_url: str,
    retention_days: int = AUDIT_LOG_RETENTION_DAYS,
    archive_output: Path | None = None,
    now: datetime | None = None,
    limit: int = 1000,
    execute: bool = False,
    create_schema_if_missing: bool = False,
) -> AuditLogRetentionResult:
    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        return await run_audit_log_retention_with_engine(
            engine=engine,
            retention_days=retention_days,
            archive_output=archive_output,
            now=now,
            limit=limit,
            execute=execute,
            create_schema_if_missing=create_schema_if_missing,
        )
    finally:
        await engine.dispose()


async def run_audit_log_retention_with_engine(
    *,
    engine: AsyncEngine,
    retention_days: int = AUDIT_LOG_RETENTION_DAYS,
    archive_output: Path | None = None,
    now: datetime | None = None,
    limit: int = 1000,
    execute: bool = False,
    create_schema_if_missing: bool = False,
) -> AuditLogRetentionResult:
    if retention_days <= 0:
        raise ValueError("retention_days must be greater than 0")
    if limit <= 0:
        raise ValueError("limit must be greater than 0")
    effective_now = _normalize_datetime(now or datetime.now(UTC))
    cutoff = effective_now - timedelta(days=retention_days)
    if create_schema_if_missing:
        await create_schema(engine)

    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        result = await session.execute(
            select(AuditLogEvent)
            .where(AuditLogEvent.created_at < cutoff)
            .order_by(AuditLogEvent.created_at.asc(), AuditLogEvent.id.asc())
            .limit(limit)
        )
        events = list(result.scalars().all())

    expired_events = tuple(_event_to_payload(event) for event in events)
    if execute and expired_events and archive_output is None:
        raise ValueError("audit-log-retention --execute requires --archive-output")

    archive_sha256: str | None = None
    archived_event_count = 0
    deleted_event_count = 0
    if execute and expired_events:
        archive_sha256 = _write_jsonl_archive(archive_output, expired_events)
        archived_event_count = len(expired_events)
        event_ids = tuple(event.id for event in events)
        async with session_factory() as session, session.begin():
            await session.execute(delete(AuditLogEvent).where(AuditLogEvent.id.in_(event_ids)))
        deleted_event_count = len(event_ids)

    return AuditLogRetentionResult(
        status="pass",
        mode="execute" if execute else "dry-run",
        execute_requested=execute,
        executed=execute and (not expired_events or deleted_event_count == len(expired_events)),
        retention_days=retention_days,
        now=effective_now,
        cutoff=cutoff,
        limit=limit,
        limit_reached=len(expired_events) == limit,
        expired_event_count=len(expired_events),
        archived_event_count=archived_event_count,
        deleted_event_count=deleted_event_count,
        archive_output=str(archive_output) if archive_output is not None else None,
        archive_sha256=archive_sha256,
        action_counts=dict(Counter(str(event["action"]) for event in expired_events)),
        entity_type_counts=dict(Counter(str(event["entity_type"]) for event in expired_events)),
        expired_events=expired_events,
        issues=(),
    )


def render_audit_log_retention_markdown(result: AuditLogRetentionResult) -> str:
    lines = [
        "# 审计日志保留归档报告",
        "",
        f"- 总体状态：`{result.status.upper()}`",
        f"- 模式：`{result.mode}`",
        f"- 请求执行：`{str(result.execute_requested).lower()}`",
        f"- 已执行：`{str(result.executed).lower()}`",
        f"- 保留天数：`{result.retention_days}`",
        f"- 当前时间：`{_datetime_to_iso(result.now)}`",
        f"- 过期 cutoff：`{_datetime_to_iso(result.cutoff)}`",
        f"- 批次上限：`{result.limit}`",
        f"- 命中上限：`{str(result.limit_reached).lower()}`",
        f"- 过期事件数：`{result.expired_event_count}`",
        f"- 已归档事件数：`{result.archived_event_count}`",
        f"- 已删除事件数：`{result.deleted_event_count}`",
        f"- 归档文件：`{result.archive_output or '-'}`",
        f"- 归档 sha256：`{result.archive_sha256 or '-'}`",
    ]
    if result.issues:
        lines.extend(["", "## 阻断问题"])
        lines.extend(f"- {issue}" for issue in result.issues)
    lines.extend(["", "## 动作分布", "", "| action | 过期事件数 |", "| --- | ---: |"])
    if result.action_counts:
        for action, count in sorted(result.action_counts.items()):
            lines.append(f"| `{action}` | {count} |")
    else:
        lines.append("| - | 0 |")
    lines.extend(["", "## 实体类型分布", "", "| entity_type | 过期事件数 |", "| --- | ---: |"])
    if result.entity_type_counts:
        for entity_type, count in sorted(result.entity_type_counts.items()):
            lines.append(f"| `{entity_type}` | {count} |")
    else:
        lines.append("| - | 0 |")
    lines.extend(
        [
            "",
            "## 过期事件清单",
            "",
            "| event_id | created_at | action | entity_type | entity_id | user_identifier |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    if result.expired_events:
        for event in result.expired_events:
            lines.append(
                "| "
                f"`{event['event_id']}` | "
                f"`{event['created_at']}` | "
                f"`{event['action']}` | "
                f"`{event['entity_type']}` | "
                f"`{event['entity_id']}` | "
                f"`{event.get('user_identifier') or '-'}` |"
            )
    else:
        lines.append("| - | - | - | - | - | - |")
    return "\n".join(lines) + "\n"


def audit_log_retention_result_json(result: AuditLogRetentionResult) -> str:
    return json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n"


def _write_jsonl_archive(
    archive_output: Path | None,
    events: tuple[dict[str, object], ...],
) -> str:
    if archive_output is None:
        raise ValueError("archive_output is required")
    content = "".join(
        json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n" for event in events
    )
    archive_output.parent.mkdir(parents=True, exist_ok=True)
    archive_output.write_text(content, encoding="utf-8")
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


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
        "payload": _json_safe(event.payload),
        "metadata": _json_safe(event.extra_metadata),
        "created_at": _datetime_to_iso(event.created_at),
    }


def _json_safe(value: object) -> object:
    return cast(
        object,
        json.loads(json.dumps(copy.deepcopy(value), ensure_ascii=False, default=str)),
    )


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _datetime_to_iso(value: datetime) -> str:
    return _normalize_datetime(value).isoformat(timespec="seconds").replace("+00:00", "Z")
