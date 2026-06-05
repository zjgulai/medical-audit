from __future__ import annotations

import copy
import hashlib
import hmac
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
    signature_manifest_output: str | None
    signature_manifest_sha256: str | None
    signature_algorithm: str | None
    previous_signature_sha256: str | None
    action_counts: dict[str, int] = Field(default_factory=dict)
    entity_type_counts: dict[str, int] = Field(default_factory=dict)
    expired_events: tuple[dict[str, object], ...]
    issues: tuple[str, ...]


class AuditLogArchiveSignatureManifest(BaseModel):
    model_config = ConfigDict(frozen=True)

    manifest_version: int = 1
    algorithm: Literal["hmac-sha256"] = "hmac-sha256"
    archive_path: str
    archive_byte_size: int
    archive_sha256: str
    signed_at: str
    key_id: str
    signing_subject: str | None
    previous_signature_sha256: str | None
    canonical_payload_sha256: str
    signature: str


class AuditLogArchiveSignatureVerifyResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Literal["pass", "fail"]
    archive_output: str
    signature_manifest: str
    algorithm: str
    key_id: str
    archive_sha256: str
    expected_archive_sha256: str
    archive_sha256_valid: bool
    canonical_payload_sha256: str
    expected_canonical_payload_sha256: str
    canonical_payload_sha256_valid: bool
    signature_valid: bool
    previous_signature_sha256: str | None
    issues: tuple[str, ...]


async def run_audit_log_retention_to_database(
    *,
    database_url: str,
    retention_days: int = AUDIT_LOG_RETENTION_DAYS,
    archive_output: Path | None = None,
    signature_output: Path | None = None,
    signing_secret: str | None = None,
    signing_key_id: str | None = None,
    signing_subject: str | None = None,
    previous_signature_sha256: str | None = None,
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
            signature_output=signature_output,
            signing_secret=signing_secret,
            signing_key_id=signing_key_id,
            signing_subject=signing_subject,
            previous_signature_sha256=previous_signature_sha256,
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
    signature_output: Path | None = None,
    signing_secret: str | None = None,
    signing_key_id: str | None = None,
    signing_subject: str | None = None,
    previous_signature_sha256: str | None = None,
    now: datetime | None = None,
    limit: int = 1000,
    execute: bool = False,
    create_schema_if_missing: bool = False,
) -> AuditLogRetentionResult:
    if retention_days <= 0:
        raise ValueError("retention_days must be greater than 0")
    if limit <= 0:
        raise ValueError("limit must be greater than 0")
    signing_requested = signature_output is not None or signing_secret is not None
    if signing_requested and not execute:
        raise ValueError("audit-log-retention archive signing requires --execute")
    if signing_requested and signature_output is None:
        raise ValueError("audit-log-retention archive signing requires --signature-output")
    if signing_requested and not signing_secret:
        raise ValueError("audit-log-retention archive signing requires --signing-secret-env")
    if signing_requested and not signing_key_id:
        raise ValueError("audit-log-retention archive signing requires --signing-key-id")
    previous_signature_sha256 = _validate_optional_sha256(previous_signature_sha256)
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
    signature_manifest_sha256: str | None = None
    archived_event_count = 0
    deleted_event_count = 0
    if execute and expired_events:
        archive_sha256 = _write_jsonl_archive(archive_output, expired_events)
        if signing_requested:
            if archive_output is None or signature_output is None:
                raise ValueError("archive_output and signature_output are required")
            signature_manifest_sha256 = _write_archive_signature_manifest(
                archive_output=archive_output,
                archive_sha256=archive_sha256,
                signature_output=signature_output,
                signing_secret=str(signing_secret),
                signing_key_id=str(signing_key_id),
                signing_subject=signing_subject,
                previous_signature_sha256=previous_signature_sha256,
                signed_at=effective_now,
            )
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
        signature_manifest_output=str(signature_output) if signature_output is not None else None,
        signature_manifest_sha256=signature_manifest_sha256,
        signature_algorithm="hmac-sha256" if signature_manifest_sha256 is not None else None,
        previous_signature_sha256=previous_signature_sha256,
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
        f"- 签名 manifest：`{result.signature_manifest_output or '-'}`",
        f"- 签名 manifest sha256：`{result.signature_manifest_sha256 or '-'}`",
        f"- 签名算法：`{result.signature_algorithm or '-'}`",
        f"- 上一签名 sha256：`{result.previous_signature_sha256 or '-'}`",
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


def verify_audit_log_archive_signature(
    *,
    archive_output: Path,
    signature_manifest: Path,
    signing_secret: str,
) -> AuditLogArchiveSignatureVerifyResult:
    manifest = AuditLogArchiveSignatureManifest.model_validate_json(
        signature_manifest.read_text(encoding="utf-8")
    )
    actual_archive_sha256 = _sha256_file(archive_output)
    archive_sha256_valid = hmac.compare_digest(actual_archive_sha256, manifest.archive_sha256)
    canonical_payload = _signature_payload(manifest)
    canonical_payload_sha256 = _sha256_bytes(canonical_payload)
    canonical_payload_sha256_valid = hmac.compare_digest(
        canonical_payload_sha256,
        manifest.canonical_payload_sha256,
    )
    expected_signature = _hmac_sha256_hex(signing_secret, canonical_payload)
    signature_valid = hmac.compare_digest(expected_signature, manifest.signature)
    issues: list[str] = []
    if not archive_sha256_valid:
        issues.append("archive sha256 mismatch")
    if not canonical_payload_sha256_valid:
        issues.append("signature canonical payload sha256 mismatch")
    if not signature_valid:
        issues.append("signature mismatch")
    return AuditLogArchiveSignatureVerifyResult(
        status="pass" if not issues else "fail",
        archive_output=str(archive_output),
        signature_manifest=str(signature_manifest),
        algorithm=manifest.algorithm,
        key_id=manifest.key_id,
        archive_sha256=actual_archive_sha256,
        expected_archive_sha256=manifest.archive_sha256,
        archive_sha256_valid=archive_sha256_valid,
        canonical_payload_sha256=canonical_payload_sha256,
        expected_canonical_payload_sha256=manifest.canonical_payload_sha256,
        canonical_payload_sha256_valid=canonical_payload_sha256_valid,
        signature_valid=signature_valid,
        previous_signature_sha256=manifest.previous_signature_sha256,
        issues=tuple(issues),
    )


def render_audit_log_archive_signature_verify_markdown(
    result: AuditLogArchiveSignatureVerifyResult,
) -> str:
    lines = [
        "# 审计日志归档验签报告",
        "",
        f"- 总体状态：`{result.status.upper()}`",
        f"- 归档文件：`{result.archive_output}`",
        f"- 签名 manifest：`{result.signature_manifest}`",
        f"- 签名算法：`{result.algorithm}`",
        f"- key_id：`{result.key_id}`",
        f"- archive_sha256_valid：`{str(result.archive_sha256_valid).lower()}`",
        f"- signature_valid：`{str(result.signature_valid).lower()}`",
        f"- 当前 archive sha256：`{result.archive_sha256}`",
        f"- manifest archive sha256：`{result.expected_archive_sha256}`",
        f"- 上一签名 sha256：`{result.previous_signature_sha256 or '-'}`",
    ]
    if result.issues:
        lines.extend(["", "## 阻断问题"])
        lines.extend(f"- {issue}" for issue in result.issues)
    return "\n".join(lines) + "\n"


def audit_log_archive_signature_verify_result_json(
    result: AuditLogArchiveSignatureVerifyResult,
) -> str:
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


def _write_archive_signature_manifest(
    *,
    archive_output: Path,
    archive_sha256: str,
    signature_output: Path,
    signing_secret: str,
    signing_key_id: str,
    signing_subject: str | None,
    previous_signature_sha256: str | None,
    signed_at: datetime,
) -> str:
    manifest_version = 1
    algorithm = "hmac-sha256"
    archive_path = str(archive_output)
    archive_byte_size = archive_output.stat().st_size
    signed_at_iso = _datetime_to_iso(signed_at)
    payload = {
        "manifest_version": manifest_version,
        "algorithm": algorithm,
        "archive_path": archive_path,
        "archive_byte_size": archive_byte_size,
        "archive_sha256": archive_sha256,
        "signed_at": signed_at_iso,
        "key_id": signing_key_id,
        "signing_subject": signing_subject,
        "previous_signature_sha256": previous_signature_sha256,
    }
    canonical_payload = _canonical_json_bytes(payload)
    manifest = AuditLogArchiveSignatureManifest(
        manifest_version=manifest_version,
        algorithm="hmac-sha256",
        archive_path=archive_path,
        archive_byte_size=archive_byte_size,
        archive_sha256=archive_sha256,
        signed_at=signed_at_iso,
        key_id=signing_key_id,
        signing_subject=signing_subject,
        previous_signature_sha256=previous_signature_sha256,
        canonical_payload_sha256=_sha256_bytes(canonical_payload),
        signature=_hmac_sha256_hex(signing_secret, canonical_payload),
    )
    content = (
        json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    )
    signature_output.parent.mkdir(parents=True, exist_ok=True)
    signature_output.write_text(content, encoding="utf-8")
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _signature_payload(manifest: AuditLogArchiveSignatureManifest) -> bytes:
    return _canonical_json_bytes(
        {
            "manifest_version": manifest.manifest_version,
            "algorithm": manifest.algorithm,
            "archive_path": manifest.archive_path,
            "archive_byte_size": manifest.archive_byte_size,
            "archive_sha256": manifest.archive_sha256,
            "signed_at": manifest.signed_at,
            "key_id": manifest.key_id,
            "signing_subject": manifest.signing_subject,
            "previous_signature_sha256": manifest.previous_signature_sha256,
        }
    )


def _canonical_json_bytes(payload: dict[str, object]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _hmac_sha256_hex(signing_secret: str, payload: bytes) -> str:
    return hmac.new(signing_secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


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


def _validate_optional_sha256(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if len(normalized) != 64 or any(
        character not in "0123456789abcdef" for character in normalized
    ):
        raise ValueError("previous_signature_sha256 must be a 64-character hexadecimal string")
    return normalized
