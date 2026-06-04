from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, selectinload, sessionmaker

from medical_audit_kb.db.models import (
    AuditFinding,
    AuditRun,
    AuditTask,
    Base,
    FindingEvidenceItem,
    ReviewTask,
    RuleVersion,
)


class AuditFindingNotFoundError(KeyError):
    pass


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
