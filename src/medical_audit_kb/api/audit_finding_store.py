from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, selectinload, sessionmaker

from medical_audit_kb.db.models import (
    AuditDataSnapshot,
    AuditFinding,
    AuditProject,
    AuditRule,
    AuditRun,
    AuditTask,
    Base,
    FindingEvidenceItem,
    HisFieldMapping,
    HisSourceBatch,
    HisStagingRow,
    HisTableSchema,
    ReviewTask,
    RuleVersion,
)


class AuditFindingNotFoundError(KeyError):
    pass


_GENERATION_REQUIRED_TABLES: tuple[tuple[str, str, type[Any]], ...] = (
    ("audit_projects", "审计项目", AuditProject),
    ("his_source_batches", "HIS 数据批次", HisSourceBatch),
    ("his_table_schemas", "HIS 表结构", HisTableSchema),
    ("his_field_mappings", "HIS 字段映射", HisFieldMapping),
    ("his_staging_rows", "HIS staging 行", HisStagingRow),
    ("audit_data_snapshots", "审计数据快照", AuditDataSnapshot),
    ("audit_tasks", "审计任务", AuditTask),
    ("audit_runs", "规则运行批次", AuditRun),
    ("audit_rules", "审计规则", AuditRule),
    ("rule_versions", "规则版本", RuleVersion),
)

_GENERATION_OUTPUT_TABLES: tuple[tuple[str, str, type[Any]], ...] = (
    ("audit_findings", "规则疑点", AuditFinding),
    ("finding_evidence_items", "疑点证据项", FindingEvidenceItem),
)


@dataclass(slots=True)
class SqlAlchemyAuditFindingStore:
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

    def list_findings(
        self,
        *,
        review_status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, object]]:
        with self._session_factory() as session:
            statement = (
                select(AuditFinding)
                .options(
                    selectinload(AuditFinding.audit_run),
                    selectinload(AuditFinding.audit_task),
                    selectinload(AuditFinding.rule_version),
                    selectinload(AuditFinding.evidence_items),
                )
                .order_by(AuditFinding.created_at.desc())
                .limit(limit)
            )
            if review_status is not None:
                statement = statement.where(AuditFinding.review_status == review_status)
            return [_finding_to_payload(session, finding) for finding in session.scalars(statement)]

    def generation_readiness(self) -> dict[str, object]:
        with self._session_factory() as session:
            table_counts = {
                table_key: _count_rows(session, model)
                for table_key, _, model in (
                    *_GENERATION_REQUIRED_TABLES,
                    *_GENERATION_OUTPUT_TABLES,
                )
            }

        prerequisites = [
            {
                "key": table_key,
                "label": label,
                "count": table_counts[table_key],
                "ready": table_counts[table_key] > 0,
                "required": True,
            }
            for table_key, label, _ in _GENERATION_REQUIRED_TABLES
        ]
        missing_prerequisites = [
            item for item in prerequisites if not bool(item["ready"])
        ]
        finding_count = table_counts["audit_findings"]
        if finding_count > 0:
            status = "generated"
            blocking_reasons: list[dict[str, str]] = []
        elif missing_prerequisites:
            status = "blocked"
            blocking_reasons = [
                {
                    "code": f"missing-{item['key']}",
                    "message": f"{item['label']}为空，无法从规则运行生成疑点。",
                }
                for item in missing_prerequisites
            ]
        else:
            status = "ready-to-run"
            blocking_reasons = []

        return {
            "status": status,
            "ready": status != "blocked",
            "has_findings": finding_count > 0,
            "table_counts": table_counts,
            "prerequisites": prerequisites,
            "blocking_reasons": blocking_reasons,
            "next_actions": _generation_next_actions(status),
        }

    def get_finding(self, finding_key: str) -> dict[str, object]:
        with self._session_factory() as session:
            finding = _load_finding(session, finding_key)
            if finding is None:
                raise AuditFindingNotFoundError(finding_key)
            return _finding_to_payload(session, finding)

    def link_review_task(self, finding_key: str, review_task_external_id: str) -> dict[str, object]:
        with self._session_factory.begin() as session:
            finding = _load_finding(session, finding_key)
            if finding is None:
                raise AuditFindingNotFoundError(finding_key)
            review_task = session.scalar(
                select(ReviewTask).where(ReviewTask.external_task_id == review_task_external_id)
            )
            if review_task is None:
                raise ValueError(f"review task does not exist: {review_task_external_id}")
            finding.review_task_id = review_task.id
            finding.review_status = "pending-review"
            finding.updated_at = _utc_now()
            session.flush()
            return _finding_to_payload(session, finding)


def _count_rows(session: Session, model: type[Any]) -> int:
    return int(session.scalar(select(func.count()).select_from(model)) or 0)


def _generation_next_actions(status: str) -> list[str]:
    if status == "generated":
        return ["从疑点清单创建人工复核任务，完成复核后再进入底稿或报告。"]
    if status == "ready-to-run":
        return [
            "先执行 charge-rule-001-staging-run dry-run，确认 planned finding_count。",
            "确认数据库备份和业务窗口后，再追加 --execute 写入 audit_findings。",
        ]
    return [
        "导入脱敏 HIS 样本，生成 his_source_batches、his_table_schemas、"
        "his_field_mappings 和 his_staging_rows。",
        "创建 audit_data_snapshots、audit_tasks、audit_runs，"
        "并激活 CHARGE-RULE-001 的 rule_versions。",
    ]


def _load_finding(session: Session, finding_key: str) -> AuditFinding | None:
    statement = (
        select(AuditFinding)
        .options(
            selectinload(AuditFinding.audit_run),
            selectinload(AuditFinding.audit_task),
            selectinload(AuditFinding.rule_version),
            selectinload(AuditFinding.evidence_items),
        )
        .where(AuditFinding.finding_key == finding_key)
    )
    return session.scalar(statement)


def _finding_to_payload(session: Session, finding: AuditFinding) -> dict[str, object]:
    review_task_external_id = _review_task_external_id(session, finding)
    return {
        "finding_key": finding.finding_key,
        "status": finding.status,
        "finding_type": finding.finding_type,
        "severity": finding.severity,
        "review_status": finding.review_status,
        "review_task_id": review_task_external_id,
        "source_record_locator": copy.deepcopy(finding.source_record_locator),
        "calculation_trace": copy.deepcopy(finding.calculation_trace),
        "metadata": copy.deepcopy(finding.extra_metadata),
        "created_at": _datetime_to_iso(finding.created_at),
        "updated_at": _datetime_to_iso(finding.updated_at),
        "audit_run_key": _audit_run_key(finding.audit_run),
        "audit_task_key": _audit_task_key(finding.audit_task),
        "rule_key": _rule_key(finding.rule_version),
        "rule_version_key": _rule_version_key(finding.rule_version),
        "evidence_items": [
            _evidence_item_to_payload(item) for item in _ordered_evidence_items(finding)
        ],
    }


def _review_task_external_id(session: Session, finding: AuditFinding) -> str | None:
    if finding.review_task_id is None:
        return None
    review_task = session.get(ReviewTask, finding.review_task_id)
    if review_task is None:
        return None
    return review_task.external_task_id


def _evidence_item_to_payload(item: FindingEvidenceItem) -> dict[str, object]:
    return {
        "evidence_type": item.evidence_type,
        "chunk_id": str(item.chunk_id) if item.chunk_id is not None else None,
        "source_package_version_key": item.source_package_version_key,
        "index_version_key": item.index_version_key,
        "citation_id": item.citation_id,
        "locator": copy.deepcopy(item.locator),
        "snippet": item.snippet,
        "metadata": copy.deepcopy(item.extra_metadata),
        "created_at": _datetime_to_iso(item.created_at),
    }


def _ordered_evidence_items(finding: AuditFinding) -> list[FindingEvidenceItem]:
    return sorted(finding.evidence_items, key=lambda item: item.created_at)


def _audit_run_key(audit_run: AuditRun | None) -> str | None:
    return audit_run.run_key if audit_run is not None else None


def _audit_task_key(audit_task: AuditTask | None) -> str | None:
    return audit_task.task_key if audit_task is not None else None


def _rule_key(rule_version: RuleVersion | None) -> str | None:
    return rule_version.rule_key if rule_version is not None else None


def _rule_version_key(rule_version: RuleVersion | None) -> str | None:
    return rule_version.version_key if rule_version is not None else None


def _datetime_to_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _utc_now() -> datetime:
    return datetime.now(UTC)


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
