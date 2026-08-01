from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
from threading import Lock
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from medical_audit_kb.contract_audit.prompt import (
    CONTRACT_AUDIT_AGENT_ID,
    CONTRACT_AUDIT_AGENT_PROMPT,
    CONTRACT_AUDIT_PROMPT_VERSION_KEY,
)
from medical_audit_kb.db.models import (
    AuditAgent,
    AuditAgentFeedback,
    AuditAgentInvocation,
    AuditAgentPromptVersion,
    Base,
    utc_now,
)

AGENT_CATEGORIES = ("业务类", "效率类", "研究类")
AGENT_ID_PREFIX = "agent-custom-"
AGENT_STATUSES = ("active", "inactive", "archived")
AGENT_VISIBILITY_SCOPES = ("project", "system")
AGENT_ALLOWED_ROLES = ("admin", "technician", "director", "member")
AGENT_FEEDBACK_RATINGS = ("effective", "needs_review", "unsafe")
AGENT_PROMPT_REVIEW_STATUSES = ("pending-review", "approved", "changes-requested")

DEFAULT_AGENT_PAYLOADS: tuple[dict[str, object], ...] = (
    {
        "id": CONTRACT_AUDIT_AGENT_ID,
        "name": "合同审计智能体",
        "category": "业务类",
        "topic": "合同审计与风险复核",
        "prompt": CONTRACT_AUDIT_AGENT_PROMPT,
        "knowledge_base": "合同审计知识与项目材料",
        "project_name": "全院审计项目",
        "status": "active",
        "created_by": "system",
        "updated_at": "2026-08-01",
        "source": "system-default",
        "prompt_version": 2,
        "prompt_version_key": CONTRACT_AUDIT_PROMPT_VERSION_KEY,
        "visibility_scope": "system",
        "allowed_roles": list(AGENT_ALLOWED_ROLES),
        "metadata": {
            "summary": "上传合同后执行页面证据约束审计并生成可下载报告。",
            "featured": True,
            "featured_rank": 1,
            "workflow": "contract-audit-v2",
            "prompt_version": 2,
            "prompt_version_key": CONTRACT_AUDIT_PROMPT_VERSION_KEY,
            "visibility_scope": "system",
            "allowed_roles": list(AGENT_ALLOWED_ROLES),
        },
    },
    {
        "id": "agent-citation-check",
        "name": "引用依据核验助手",
        "category": "业务类",
        "topic": "医保基金使用合规",
        "prompt": "只基于命中的法规、目录、规则和风险清单回答；没有引用时输出待补证据。",
        "knowledge_base": "系统医保审计知识库",
        "project_name": "医保基金使用合规专项自查",
        "status": "active",
        "created_by": "system",
        "updated_at": "2026-06-12",
        "source": "system-default",
        "prompt_version": 1,
        "prompt_version_key": "agent-citation-check@v1",
        "visibility_scope": "system",
        "allowed_roles": list(AGENT_ALLOWED_ROLES),
        "metadata": {
            "prompt_version": 1,
            "prompt_version_key": "agent-citation-check@v1",
            "visibility_scope": "system",
            "allowed_roles": list(AGENT_ALLOWED_ROLES),
        },
    },
    {
        "id": "agent-duplicate-charge",
        "name": "重复收费复核助手",
        "category": "业务类",
        "topic": "收费明细复核",
        "prompt": (
            "围绕同就诊、同项目、同日期的重复收费线索，"
            "列出应核验的执行记录、数量和例外情形。"
        ),
        "knowledge_base": "规则库与风险清单",
        "project_name": "医保基金使用合规专项自查",
        "status": "active",
        "created_by": "system",
        "updated_at": "2026-06-11",
        "source": "system-default",
        "prompt_version": 1,
        "prompt_version_key": "agent-duplicate-charge@v1",
        "visibility_scope": "system",
        "allowed_roles": list(AGENT_ALLOWED_ROLES),
        "metadata": {
            "prompt_version": 1,
            "prompt_version_key": "agent-duplicate-charge@v1",
            "visibility_scope": "system",
            "allowed_roles": list(AGENT_ALLOWED_ROLES),
        },
    },
    {
        "id": "agent-report-draft",
        "name": "底稿摘要助手",
        "category": "效率类",
        "topic": "审计底稿",
        "prompt": "把已复核的引用、疑点和附件清单整理为底稿摘要，保留待人工确认标记。",
        "knowledge_base": "项目复核资料",
        "project_name": "医保基金使用合规专项自查",
        "status": "active",
        "created_by": "system",
        "updated_at": "2026-06-10",
        "source": "system-default",
        "prompt_version": 1,
        "prompt_version_key": "agent-report-draft@v1",
        "visibility_scope": "system",
        "allowed_roles": list(AGENT_ALLOWED_ROLES),
        "metadata": {
            "prompt_version": 1,
            "prompt_version_key": "agent-report-draft@v1",
            "visibility_scope": "system",
            "allowed_roles": list(AGENT_ALLOWED_ROLES),
        },
    },
)


@dataclass(frozen=True, slots=True)
class AgentInstallResult:
    item: dict[str, object]
    created: bool
    reactivated: bool = False


class DuplicateMarketAgentInstallError(RuntimeError):
    pass


class AgentStore(Protocol):
    def list_agents(self, *, include_inactive: bool = False) -> list[dict[str, object]]:
        pass

    def get_agent(self, agent_key: str) -> dict[str, object] | None:
        pass

    def list_prompt_versions(self, agent_key: str) -> list[dict[str, object]]:
        pass

    def add_agent(self, values: dict[str, object]) -> dict[str, object]:
        pass

    def install_market_agent(self, values: dict[str, object]) -> AgentInstallResult:
        pass

    def add_prompt_version(
        self,
        agent_key: str,
        *,
        prompt: str,
        change_summary: str,
        review_note: str | None,
        created_by: str | None,
    ) -> dict[str, object]:
        pass

    def update_prompt_version_review(
        self,
        agent_key: str,
        *,
        version: int,
        review_status: str,
        review_note: str,
        reviewed_by: str | None,
    ) -> dict[str, object]:
        pass

    def rollback_prompt_version(
        self,
        agent_key: str,
        *,
        version: int,
        created_by: str | None,
    ) -> dict[str, object]:
        pass

    def update_agent_lifecycle(
        self,
        agent_key: str,
        *,
        status: str,
        reason: str,
        updated_by: str | None,
    ) -> dict[str, object]:
        pass

    def record_invocation(
        self,
        agent_key: str,
        *,
        invocation_source: str,
        question: str | None,
        conversation_ref: str | None,
        created_by: str | None,
        metadata: dict[str, object],
    ) -> dict[str, object]:
        pass

    def list_invocations(self, agent_key: str, *, limit: int = 20) -> list[dict[str, object]]:
        pass

    def record_feedback(
        self,
        agent_key: str,
        *,
        invocation_id: str | None,
        rating: str,
        comment: str,
        created_by: str | None,
        metadata: dict[str, object],
    ) -> dict[str, object]:
        pass

    def list_feedback(self, agent_key: str, *, limit: int = 20) -> list[dict[str, object]]:
        pass

    def feedback_summary(self, agent_key: str) -> dict[str, object]:
        pass


@dataclass(slots=True)
class SqlAlchemyAgentStore:
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

    def list_agents(self, *, include_inactive: bool = False) -> list[dict[str, object]]:
        with self._session_factory() as session:
            statement = select(AuditAgent).order_by(
                AuditAgent.updated_at.desc(),
                AuditAgent.created_at.desc(),
            )
            if not include_inactive:
                statement = statement.where(AuditAgent.status == "active")
            return [_agent_to_payload(agent) for agent in session.scalars(statement).all()]

    def get_agent(self, agent_key: str) -> dict[str, object] | None:
        with self._session_factory() as session:
            agent = session.scalar(select(AuditAgent).where(AuditAgent.agent_key == agent_key))
            return _agent_to_payload(agent) if agent is not None else None

    def list_prompt_versions(self, agent_key: str) -> list[dict[str, object]]:
        with self._session_factory() as session:
            agent = session.scalar(select(AuditAgent).where(AuditAgent.agent_key == agent_key))
            if agent is None:
                default_agent = _default_agent_payload(agent_key)
                if default_agent is None:
                    raise KeyError(f"agent not found: {agent_key}")
                return _payload_prompt_versions(default_agent)
            return _agent_prompt_versions_payload(agent)

    def add_agent(self, values: dict[str, object]) -> dict[str, object]:
        return self._insert_agent(values, agent_key=_new_agent_key())

    def install_market_agent(self, values: dict[str, object]) -> AgentInstallResult:
        agent_key = _market_agent_key(values)
        with self._session_factory.begin() as session:
            existing = _find_market_agent_install(session, values)
            if existing is not None:
                reactivated = existing.status != "active"
                if reactivated:
                    existing.status = "active"
                    existing.updated_at = utc_now()
                    metadata = _dict_value(existing.extra_metadata)
                    metadata["lifecycle_reason"] = "market reinstall"
                    metadata["lifecycle_updated_by"] = _optional_str(
                        values.get("created_by")
                    )
                    metadata["lifecycle_updated_at"] = _datetime_to_iso(
                        existing.updated_at
                    )
                    existing.extra_metadata = metadata
                    session.flush()
                return AgentInstallResult(
                    item=_agent_to_payload(existing),
                    created=False,
                    reactivated=reactivated,
                )

        try:
            return AgentInstallResult(
                item=self._insert_agent(values, agent_key=agent_key),
                created=True,
            )
        except IntegrityError:
            with self._session_factory() as session:
                existing = session.scalar(
                    select(AuditAgent).where(AuditAgent.agent_key == agent_key)
                )
                if existing is None or not _agent_matches_market_install(existing, values):
                    raise
                return AgentInstallResult(item=_agent_to_payload(existing), created=False)

    def _insert_agent(
        self,
        values: dict[str, object],
        *,
        agent_key: str,
    ) -> dict[str, object]:
        now = utc_now()
        metadata = _governance_metadata(values, agent_key=agent_key, version=1)
        project_name = str(values["project_name"])
        if market_agent_template_id(values) is not None:
            project_name = project_name.strip()
        agent = AuditAgent(
            agent_key=agent_key,
            name=str(values["name"]),
            category=str(values["category"]),
            topic=str(values["topic"]),
            prompt=str(values["prompt"]),
            knowledge_base=str(values["knowledge_base"]),
            project_name=project_name,
            status="active",
            created_by=_optional_str(values.get("created_by")),
            extra_metadata=metadata,
            created_at=now,
            updated_at=now,
        )
        with self._session_factory.begin() as session:
            session.add(agent)
            session.flush()
            prompt_version = AuditAgentPromptVersion(
                agent_id=agent.id,
                version=1,
                prompt=agent.prompt,
                change_summary="initial prompt",
                created_by=agent.created_by,
                created_at=now,
            )
            session.add(prompt_version)
            session.flush()
            return _agent_to_payload(agent, prompt_version=1, prompt_versions=[prompt_version])

    def add_prompt_version(
        self,
        agent_key: str,
        *,
        prompt: str,
        change_summary: str,
        review_note: str | None,
        created_by: str | None,
    ) -> dict[str, object]:
        with self._session_factory.begin() as session:
            agent = _load_agent_for_update(session, agent_key)
            existing_versions = list(agent.prompt_versions)
            next_version = _latest_prompt_version(agent) + 1
            now = utc_now()
            prompt_version = AuditAgentPromptVersion(
                agent_id=agent.id,
                version=next_version,
                prompt=prompt,
                change_summary=change_summary,
                created_by=created_by,
                created_at=now,
            )
            session.add(prompt_version)
            agent.updated_at = now
            _set_agent_prompt_review_metadata(
                agent,
                version=next_version,
                status="pending-review",
                note=review_note or change_summary,
                requested_by=created_by,
                reviewed_by=None,
                reviewed_at=None,
                updated_at=now,
            )
            session.flush()
            return _agent_to_payload(
                agent,
                prompt_versions=[*existing_versions, prompt_version],
            )

    def update_prompt_version_review(
        self,
        agent_key: str,
        *,
        version: int,
        review_status: str,
        review_note: str,
        reviewed_by: str | None,
    ) -> dict[str, object]:
        validate_agent_prompt_review_status(review_status)
        with self._session_factory.begin() as session:
            agent = _load_agent_for_update(session, agent_key)
            existing_versions = list(agent.prompt_versions)
            if not any(item.version == version for item in existing_versions):
                raise KeyError(f"agent prompt version not found: {agent_key}@v{version}")
            target = next(item for item in existing_versions if item.version == version)
            now = utc_now()
            if review_status == "approved":
                agent.prompt = target.prompt
                _set_agent_version_metadata(agent, version=version)
            agent.updated_at = now
            _set_agent_prompt_review_metadata(
                agent,
                version=version,
                status=review_status,
                note=review_note,
                requested_by=None,
                reviewed_by=reviewed_by,
                reviewed_at=now,
                updated_at=now,
            )
            session.flush()
            return _agent_to_payload(agent, prompt_versions=existing_versions)

    def rollback_prompt_version(
        self,
        agent_key: str,
        *,
        version: int,
        created_by: str | None,
    ) -> dict[str, object]:
        with self._session_factory.begin() as session:
            agent = _load_agent_for_update(session, agent_key)
            existing_versions = list(agent.prompt_versions)
            target = next((item for item in existing_versions if item.version == version), None)
            if target is None:
                raise KeyError(f"agent prompt version not found: {agent_key}@v{version}")
            next_version = _latest_prompt_version(agent) + 1
            now = utc_now()
            prompt_version = AuditAgentPromptVersion(
                agent_id=agent.id,
                version=next_version,
                prompt=target.prompt,
                change_summary=f"rollback to v{version}",
                created_by=created_by,
                created_at=now,
            )
            session.add(prompt_version)
            agent.prompt = target.prompt
            agent.updated_at = now
            _set_agent_version_metadata(agent, version=next_version)
            _set_agent_prompt_review_metadata(
                agent,
                version=next_version,
                status="approved",
                note=f"rollback to v{version}",
                requested_by=created_by,
                reviewed_by=created_by,
                reviewed_at=now,
                updated_at=now,
            )
            session.flush()
            return _agent_to_payload(
                agent,
                prompt_version=next_version,
                prompt_versions=[*existing_versions, prompt_version],
            )

    def update_agent_lifecycle(
        self,
        agent_key: str,
        *,
        status: str,
        reason: str,
        updated_by: str | None,
    ) -> dict[str, object]:
        validate_agent_status(status)
        with self._session_factory.begin() as session:
            agent = _load_agent_for_update(session, agent_key)
            agent.status = status
            agent.updated_at = utc_now()
            metadata = _dict_value(agent.extra_metadata)
            metadata["lifecycle_reason"] = reason
            metadata["lifecycle_updated_by"] = updated_by
            metadata["lifecycle_updated_at"] = _datetime_to_iso(agent.updated_at)
            agent.extra_metadata = metadata
            session.flush()
            return _agent_to_payload(agent)

    def record_invocation(
        self,
        agent_key: str,
        *,
        invocation_source: str,
        question: str | None,
        conversation_ref: str | None,
        created_by: str | None,
        metadata: dict[str, object],
    ) -> dict[str, object]:
        with self._session_factory.begin() as session:
            agent = session.scalar(select(AuditAgent).where(AuditAgent.agent_key == agent_key))
            agent_payload = (
                _agent_to_payload(agent) if agent is not None else _default_agent_payload(agent_key)
            )
            if agent_payload is None:
                raise KeyError(f"agent not found: {agent_key}")
            if str(agent_payload.get("status") or "active") != "active":
                raise ValueError(f"agent is not active: {agent_key}")
            invocation = AuditAgentInvocation(
                agent_id=agent.id if agent is not None else None,
                agent_key=agent_key,
                prompt_version=_int_value(agent_payload.get("prompt_version"), default=1),
                prompt_version_key=str(
                    agent_payload.get("prompt_version_key") or f"{agent_key}@v1"
                ),
                invocation_source=invocation_source,
                question=question,
                conversation_ref=conversation_ref,
                created_by=created_by,
                extra_metadata=copy.deepcopy(metadata),
                created_at=utc_now(),
            )
            session.add(invocation)
            session.flush()
            return _invocation_to_payload(invocation)

    def list_invocations(self, agent_key: str, *, limit: int = 20) -> list[dict[str, object]]:
        with self._session_factory() as session:
            statement = (
                select(AuditAgentInvocation)
                .where(AuditAgentInvocation.agent_key == agent_key)
                .order_by(AuditAgentInvocation.created_at.desc())
                .limit(limit)
            )
            return [_invocation_to_payload(item) for item in session.scalars(statement).all()]

    def record_feedback(
        self,
        agent_key: str,
        *,
        invocation_id: str | None,
        rating: str,
        comment: str,
        created_by: str | None,
        metadata: dict[str, object],
    ) -> dict[str, object]:
        validate_agent_feedback_rating(rating)
        with self._session_factory.begin() as session:
            agent = session.scalar(select(AuditAgent).where(AuditAgent.agent_key == agent_key))
            agent_payload = (
                _agent_to_payload(agent) if agent is not None else _default_agent_payload(agent_key)
            )
            if agent_payload is None:
                raise KeyError(f"agent not found: {agent_key}")
            invocation = _load_invocation(session, invocation_id) if invocation_id else None
            if invocation is not None and invocation.agent_key != agent_key:
                raise KeyError(f"agent invocation does not belong to agent: {invocation_id}")
            prompt_version = (
                invocation.prompt_version
                if invocation is not None
                else _int_value(agent_payload.get("prompt_version"), default=1)
            )
            feedback = AuditAgentFeedback(
                agent_id=agent.id if agent is not None else None,
                invocation_id=invocation.id if invocation is not None else None,
                agent_key=agent_key,
                prompt_version=prompt_version,
                rating=rating,
                comment=comment,
                created_by=created_by,
                extra_metadata=copy.deepcopy(metadata),
                created_at=utc_now(),
            )
            session.add(feedback)
            session.flush()
            return _feedback_to_payload(feedback)

    def list_feedback(self, agent_key: str, *, limit: int = 20) -> list[dict[str, object]]:
        with self._session_factory() as session:
            statement = (
                select(AuditAgentFeedback)
                .where(AuditAgentFeedback.agent_key == agent_key)
                .order_by(AuditAgentFeedback.created_at.desc())
                .limit(limit)
            )
            return [_feedback_to_payload(item) for item in session.scalars(statement).all()]

    def feedback_summary(self, agent_key: str) -> dict[str, object]:
        with self._session_factory() as session:
            rows = session.execute(
                select(AuditAgentFeedback.rating, func.count(AuditAgentFeedback.id))
                .where(AuditAgentFeedback.agent_key == agent_key)
                .group_by(AuditAgentFeedback.rating)
            ).all()
            latest = session.scalar(
                select(AuditAgentFeedback)
                .where(AuditAgentFeedback.agent_key == agent_key)
                .order_by(AuditAgentFeedback.created_at.desc())
                .limit(1)
            )
        return _feedback_summary_payload(
            {str(rating): int(count) for rating, count in rows},
            latest_rating=latest.rating if latest is not None else None,
        )


@dataclass(slots=True)
class InMemoryAgentStore:
    agents: list[dict[str, object]] = field(default_factory=list)
    invocations: list[dict[str, object]] = field(default_factory=list)
    feedback_entries: list[dict[str, object]] = field(default_factory=list)
    _install_lock: Lock = field(default_factory=Lock, init=False, repr=False)

    def list_agents(self, *, include_inactive: bool = False) -> list[dict[str, object]]:
        return [
            _enrich_agent_payload(copy.deepcopy(agent))
            for agent in self.agents
            if include_inactive or agent.get("status") == "active"
        ]

    def get_agent(self, agent_key: str) -> dict[str, object] | None:
        agent = next((item for item in self.agents if item.get("id") == agent_key), None)
        return _enrich_agent_payload(copy.deepcopy(agent)) if agent is not None else None

    def list_prompt_versions(self, agent_key: str) -> list[dict[str, object]]:
        agent = self.get_agent(agent_key) or _default_agent_payload(agent_key)
        if agent is None:
            raise KeyError(f"agent not found: {agent_key}")
        return _payload_prompt_versions(agent)

    def add_agent(self, values: dict[str, object]) -> dict[str, object]:
        return self._add_agent_with_key(values, agent_key=_new_agent_key())

    def install_market_agent(self, values: dict[str, object]) -> AgentInstallResult:
        with self._install_lock:
            matches = [
                agent
                for agent in self.agents
                if _payload_matches_market_install(agent, values)
            ]
            if len(matches) > 1:
                raise DuplicateMarketAgentInstallError(
                    "multiple market agent installations already exist"
                )
            existing = matches[0] if matches else None
            if existing is not None:
                reactivated = str(existing.get("status") or "active") != "active"
                if reactivated:
                    existing["status"] = "active"
                    existing["updated_at"] = _datetime_to_iso(utc_now())
                    metadata = _dict_value(existing.get("metadata"))
                    metadata["lifecycle_reason"] = "market reinstall"
                    metadata["lifecycle_updated_by"] = _optional_str(
                        values.get("created_by")
                    )
                    metadata["lifecycle_updated_at"] = existing["updated_at"]
                    existing["metadata"] = metadata
                return AgentInstallResult(
                    item=_enrich_agent_payload(copy.deepcopy(existing)),
                    created=False,
                    reactivated=reactivated,
                )
            return AgentInstallResult(
                item=self._add_agent_with_key(
                    values,
                    agent_key=_market_agent_key(values),
                ),
                created=True,
            )

    def _add_agent_with_key(
        self,
        values: dict[str, object],
        *,
        agent_key: str,
    ) -> dict[str, object]:
        now = _datetime_to_iso(utc_now())
        metadata = _governance_metadata(values, agent_key=agent_key, version=1)
        project_name = str(values["project_name"])
        if market_agent_template_id(values) is not None:
            project_name = project_name.strip()
        agent: dict[str, object] = {
            "id": agent_key,
            "name": str(values["name"]),
            "category": str(values["category"]),
            "topic": str(values["topic"]),
            "prompt": str(values["prompt"]),
            "knowledge_base": str(values["knowledge_base"]),
            "project_name": project_name,
            "status": "active",
            "created_by": _optional_str(values.get("created_by")),
            "created_at": now,
            "updated_at": now,
            "source": "custom",
            "metadata": metadata,
        }
        agent["prompt_versions"] = [
            {
                "version": 1,
                "prompt": agent["prompt"],
                "change_summary": "initial prompt",
                "created_by": agent["created_by"],
                "created_at": now,
            }
        ]
        _set_payload_version_fields(agent, version=1)
        self.agents.insert(0, agent)
        return _enrich_agent_payload(copy.deepcopy(agent))

    def add_prompt_version(
        self,
        agent_key: str,
        *,
        prompt: str,
        change_summary: str,
        review_note: str | None,
        created_by: str | None,
    ) -> dict[str, object]:
        agent = self._agent_for_update(agent_key)
        prompt_versions = _payload_prompt_versions(agent)
        next_version = _latest_payload_prompt_version(agent) + 1
        now = _datetime_to_iso(utc_now())
        prompt_versions.append(
            {
                "version": next_version,
                "prompt": prompt,
                "change_summary": change_summary,
                "created_by": created_by,
                "created_at": now,
            }
        )
        agent["updated_at"] = now
        agent["prompt_versions"] = prompt_versions
        _set_payload_prompt_review_metadata(
            agent,
            version=next_version,
            status="pending-review",
            note=review_note or change_summary,
            requested_by=created_by,
            reviewed_by=None,
            reviewed_at=None,
            updated_at=now,
        )
        return _enrich_agent_payload(copy.deepcopy(agent))

    def update_prompt_version_review(
        self,
        agent_key: str,
        *,
        version: int,
        review_status: str,
        review_note: str,
        reviewed_by: str | None,
    ) -> dict[str, object]:
        validate_agent_prompt_review_status(review_status)
        agent = self._agent_for_update(agent_key)
        prompt_versions = _payload_prompt_versions(agent)
        if not any(
            _int_value(item.get("version"), default=0) == version for item in prompt_versions
        ):
            raise KeyError(f"agent prompt version not found: {agent_key}@v{version}")
        target = next(
            item
            for item in prompt_versions
            if _int_value(item.get("version"), default=0) == version
        )
        now = _datetime_to_iso(utc_now())
        if review_status == "approved":
            agent["prompt"] = str(target["prompt"])
            _set_payload_version_fields(agent, version=version)
        agent["updated_at"] = now
        _set_payload_prompt_review_metadata(
            agent,
            version=version,
            status=review_status,
            note=review_note,
            requested_by=None,
            reviewed_by=reviewed_by,
            reviewed_at=now,
            updated_at=now,
        )
        return _enrich_agent_payload(copy.deepcopy(agent))

    def rollback_prompt_version(
        self,
        agent_key: str,
        *,
        version: int,
        created_by: str | None,
    ) -> dict[str, object]:
        agent = self._agent_for_update(agent_key)
        prompt_versions = _payload_prompt_versions(agent)
        target = next(
            (
                item
                for item in prompt_versions
                if _int_value(item.get("version"), default=0) == version
            ),
            None,
        )
        if target is None:
            raise KeyError(f"agent prompt version not found: {agent_key}@v{version}")
        next_version = _latest_payload_prompt_version(agent) + 1
        now = _datetime_to_iso(utc_now())
        prompt_versions.append(
            {
                "version": next_version,
                "prompt": str(target["prompt"]),
                "change_summary": f"rollback to v{version}",
                "created_by": created_by,
                "created_at": now,
            }
        )
        agent["prompt"] = str(target["prompt"])
        agent["updated_at"] = now
        agent["prompt_versions"] = prompt_versions
        _set_payload_version_fields(agent, version=next_version)
        _set_payload_prompt_review_metadata(
            agent,
            version=next_version,
            status="approved",
            note=f"rollback to v{version}",
            requested_by=created_by,
            reviewed_by=created_by,
            reviewed_at=now,
            updated_at=now,
        )
        return _enrich_agent_payload(copy.deepcopy(agent))

    def update_agent_lifecycle(
        self,
        agent_key: str,
        *,
        status: str,
        reason: str,
        updated_by: str | None,
    ) -> dict[str, object]:
        validate_agent_status(status)
        agent = self._agent_for_update(agent_key)
        agent["status"] = status
        agent["updated_at"] = _datetime_to_iso(utc_now())
        metadata = _dict_value(agent.get("metadata"))
        metadata["lifecycle_reason"] = reason
        metadata["lifecycle_updated_by"] = updated_by
        metadata["lifecycle_updated_at"] = agent["updated_at"]
        agent["metadata"] = metadata
        return _enrich_agent_payload(copy.deepcopy(agent))

    def record_invocation(
        self,
        agent_key: str,
        *,
        invocation_source: str,
        question: str | None,
        conversation_ref: str | None,
        created_by: str | None,
        metadata: dict[str, object],
    ) -> dict[str, object]:
        agent = self.get_agent(agent_key) or _default_agent_payload(agent_key)
        if agent is None:
            raise KeyError(f"agent not found: {agent_key}")
        if str(agent.get("status") or "active") != "active":
            raise ValueError(f"agent is not active: {agent_key}")
        invocation = {
            "id": str(uuid4()),
            "agent_key": agent_key,
            "prompt_version": _int_value(agent.get("prompt_version"), default=1),
            "prompt_version_key": str(agent.get("prompt_version_key") or f"{agent_key}@v1"),
            "invocation_source": invocation_source,
            "question": question,
            "conversation_ref": conversation_ref,
            "created_by": created_by,
            "created_at": _datetime_to_iso(utc_now()),
            "metadata": copy.deepcopy(metadata),
        }
        self.invocations.insert(0, invocation)
        return copy.deepcopy(invocation)

    def list_invocations(self, agent_key: str, *, limit: int = 20) -> list[dict[str, object]]:
        return [
            copy.deepcopy(item)
            for item in self.invocations
            if item.get("agent_key") == agent_key
        ][:limit]

    def record_feedback(
        self,
        agent_key: str,
        *,
        invocation_id: str | None,
        rating: str,
        comment: str,
        created_by: str | None,
        metadata: dict[str, object],
    ) -> dict[str, object]:
        validate_agent_feedback_rating(rating)
        agent = self.get_agent(agent_key) or _default_agent_payload(agent_key)
        if agent is None:
            raise KeyError(f"agent not found: {agent_key}")
        invocation = (
            next((item for item in self.invocations if item.get("id") == invocation_id), None)
            if invocation_id
            else None
        )
        if invocation_id and invocation is None:
            raise KeyError(f"agent invocation not found: {invocation_id}")
        if invocation is not None and invocation.get("agent_key") != agent_key:
            raise KeyError(f"agent invocation does not belong to agent: {invocation_id}")
        feedback: dict[str, object] = {
            "id": str(uuid4()),
            "agent_key": agent_key,
            "invocation_id": invocation_id,
            "prompt_version": _int_value(
                invocation.get("prompt_version") if invocation else agent.get("prompt_version"),
                default=1,
            ),
            "rating": rating,
            "comment": comment,
            "created_by": created_by,
            "created_at": _datetime_to_iso(utc_now()),
            "metadata": copy.deepcopy(metadata),
        }
        self.feedback_entries.insert(0, feedback)
        return copy.deepcopy(feedback)

    def list_feedback(self, agent_key: str, *, limit: int = 20) -> list[dict[str, object]]:
        return [
            copy.deepcopy(item)
            for item in self.feedback_entries
            if item.get("agent_key") == agent_key
        ][:limit]

    def feedback_summary(self, agent_key: str) -> dict[str, object]:
        entries = [item for item in self.feedback_entries if item.get("agent_key") == agent_key]
        counts = {
            rating: sum(1 for item in entries if item.get("rating") == rating)
            for rating in AGENT_FEEDBACK_RATINGS
        }
        latest_rating = str(entries[0]["rating"]) if entries else None
        return _feedback_summary_payload(counts, latest_rating=latest_rating)

    def _agent_for_update(self, agent_key: str) -> dict[str, object]:
        agent = next((item for item in self.agents if item.get("id") == agent_key), None)
        if agent is None:
            raise KeyError(f"agent not found: {agent_key}")
        return agent


def combined_agent_payloads(custom_agents: list[dict[str, object]]) -> list[dict[str, object]]:
    seen_ids = {str(agent.get("id")) for agent in custom_agents}
    defaults = [
        _enrich_agent_payload(copy.deepcopy(agent))
        for agent in DEFAULT_AGENT_PAYLOADS
        if str(agent["id"]) not in seen_ids
    ]
    return [*[_enrich_agent_payload(agent) for agent in custom_agents], *defaults]


def validate_agent_category(category: str) -> str:
    if category not in AGENT_CATEGORIES:
        raise ValueError(f"unsupported agent category: {category}")
    return category


def validate_agent_status(status: str) -> str:
    if status not in AGENT_STATUSES:
        raise ValueError(f"unsupported agent status: {status}")
    return status


def validate_agent_visibility_scope(scope: str) -> str:
    if scope not in AGENT_VISIBILITY_SCOPES:
        raise ValueError(f"unsupported agent visibility scope: {scope}")
    return scope


def validate_agent_feedback_rating(rating: str) -> str:
    if rating not in AGENT_FEEDBACK_RATINGS:
        raise ValueError(f"unsupported agent feedback rating: {rating}")
    return rating


def validate_agent_prompt_review_status(status: str) -> str:
    if status not in AGENT_PROMPT_REVIEW_STATUSES:
        raise ValueError(f"unsupported agent prompt review status: {status}")
    return status


def _feedback_summary_payload(
    counts: dict[str, int],
    *,
    latest_rating: str | None,
) -> dict[str, object]:
    normalized_counts = {rating: int(counts.get(rating, 0)) for rating in AGENT_FEEDBACK_RATINGS}
    return {
        "total": sum(normalized_counts.values()),
        "effective": normalized_counts["effective"],
        "needs_review": normalized_counts["needs_review"],
        "unsafe": normalized_counts["unsafe"],
        "latest_rating": latest_rating,
    }


def _agent_to_payload(
    agent: AuditAgent,
    *,
    prompt_version: int | None = None,
    prompt_versions: list[AuditAgentPromptVersion] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": agent.agent_key,
        "name": agent.name,
        "category": agent.category,
        "topic": agent.topic,
        "prompt": agent.prompt,
        "knowledge_base": agent.knowledge_base,
        "project_name": agent.project_name,
        "status": agent.status,
        "created_by": agent.created_by,
        "created_at": _datetime_to_iso(agent.created_at),
        "updated_at": _datetime_to_iso(agent.updated_at),
        "source": "custom",
        "metadata": copy.deepcopy(agent.extra_metadata),
        "prompt_versions": [
            _prompt_version_to_payload(item)
            for item in sorted(
                prompt_versions if prompt_versions is not None else agent.prompt_versions,
                key=lambda item: item.version,
            )
        ],
    }
    _set_payload_version_fields(payload, version=prompt_version or _active_prompt_version(agent))
    return _enrich_agent_payload(payload)


def _load_agent_for_update(session: Session, agent_key: str) -> AuditAgent:
    agent = session.scalar(select(AuditAgent).where(AuditAgent.agent_key == agent_key))
    if agent is None:
        raise KeyError(f"agent not found: {agent_key}")
    return agent


def _load_invocation(session: Session, invocation_id: str) -> AuditAgentInvocation:
    try:
        parsed_id = UUID(invocation_id)
    except ValueError as exc:
        raise KeyError(f"agent invocation not found: {invocation_id}") from exc
    invocation = session.get(AuditAgentInvocation, parsed_id)
    if invocation is None:
        raise KeyError(f"agent invocation not found: {invocation_id}")
    return invocation


def _latest_prompt_version(agent: AuditAgent) -> int:
    return max((item.version for item in agent.prompt_versions), default=1)


def _active_prompt_version(agent: AuditAgent) -> int:
    metadata = _dict_value(agent.extra_metadata)
    return _int_value(metadata.get("prompt_version"), default=_latest_prompt_version(agent))


def _set_agent_version_metadata(agent: AuditAgent, *, version: int) -> None:
    metadata = _dict_value(agent.extra_metadata)
    metadata["prompt_version"] = version
    metadata["prompt_version_key"] = f"{agent.agent_key}@v{version}"
    agent.extra_metadata = metadata


def _set_agent_prompt_review_metadata(
    agent: AuditAgent,
    *,
    version: int,
    status: str,
    note: str,
    requested_by: str | None,
    reviewed_by: str | None,
    reviewed_at: datetime | None,
    updated_at: datetime,
) -> None:
    metadata = _dict_value(agent.extra_metadata)
    _set_prompt_review_entry(
        metadata,
        version=version,
        status=status,
        note=note,
        requested_by=requested_by,
        reviewed_by=reviewed_by,
        reviewed_at=_datetime_to_iso(reviewed_at) if reviewed_at is not None else None,
        updated_at=_datetime_to_iso(updated_at),
    )
    agent.extra_metadata = metadata


def _set_payload_version_fields(payload: dict[str, object], *, version: int) -> None:
    agent_key = str(payload["id"])
    metadata = _dict_value(payload.get("metadata"))
    metadata["prompt_version"] = version
    metadata["prompt_version_key"] = f"{agent_key}@v{version}"
    payload["metadata"] = metadata
    payload["prompt_version"] = version
    payload["prompt_version_key"] = f"{agent_key}@v{version}"


def _set_payload_prompt_review_metadata(
    payload: dict[str, object],
    *,
    version: int,
    status: str,
    note: str,
    requested_by: str | None,
    reviewed_by: str | None,
    reviewed_at: str | None,
    updated_at: str,
) -> None:
    metadata = _dict_value(payload.get("metadata"))
    _set_prompt_review_entry(
        metadata,
        version=version,
        status=status,
        note=note,
        requested_by=requested_by,
        reviewed_by=reviewed_by,
        reviewed_at=reviewed_at,
        updated_at=updated_at,
    )
    payload["metadata"] = metadata


def _set_prompt_review_entry(
    metadata: dict[str, object],
    *,
    version: int,
    status: str,
    note: str,
    requested_by: str | None,
    reviewed_by: str | None,
    reviewed_at: str | None,
    updated_at: str,
) -> None:
    validate_agent_prompt_review_status(status)
    reviews = _prompt_version_reviews(metadata)
    previous = reviews.get(str(version))
    previous_entry = previous if isinstance(previous, dict) else {}
    requested_by_value = requested_by
    if requested_by_value is None and isinstance(previous_entry.get("requested_by"), str):
        requested_by_value = str(previous_entry["requested_by"])
    reviews[str(version)] = {
        "status": status,
        "note": note,
        "requested_by": requested_by_value,
        "reviewed_by": reviewed_by,
        "reviewed_at": reviewed_at,
        "updated_at": updated_at,
    }
    metadata["prompt_version_reviews"] = reviews


def _enrich_agent_payload(payload: dict[str, object]) -> dict[str, object]:
    metadata = _dict_value(payload.get("metadata"))
    agent_key = str(payload["id"])
    version = _int_value(metadata.get("prompt_version"), default=1)
    prompt_version_key = str(metadata.get("prompt_version_key") or f"{agent_key}@v{version}")
    visibility_scope = validate_agent_visibility_scope(
        str(metadata.get("visibility_scope") or payload.get("visibility_scope") or "project")
    )
    allowed_roles = _string_list_value(
        metadata.get("allowed_roles") or payload.get("allowed_roles"),
        default=list(AGENT_ALLOWED_ROLES),
    )
    metadata["prompt_version"] = version
    metadata["prompt_version_key"] = prompt_version_key
    metadata["visibility_scope"] = visibility_scope
    metadata["allowed_roles"] = allowed_roles
    payload["metadata"] = metadata
    payload["prompt_version"] = version
    payload["prompt_version_key"] = prompt_version_key
    payload["visibility_scope"] = visibility_scope
    payload["allowed_roles"] = allowed_roles
    payload["prompt_versions"] = _payload_prompt_versions(payload)
    return payload


def _governance_metadata(
    values: dict[str, object],
    *,
    agent_key: str,
    version: int,
) -> dict[str, object]:
    metadata = _dict_value(values.get("metadata"))
    visibility_scope = validate_agent_visibility_scope(
        str(values.get("visibility_scope") or "project")
    )
    allowed_roles = _string_list_value(
        values.get("allowed_roles"),
        default=list(AGENT_ALLOWED_ROLES),
    )
    metadata["prompt_version"] = version
    metadata["prompt_version_key"] = f"{agent_key}@v{version}"
    metadata["visibility_scope"] = visibility_scope
    metadata["allowed_roles"] = allowed_roles
    _set_prompt_review_entry(
        metadata,
        version=version,
        status="approved",
        note="initial prompt",
        requested_by=_optional_str(values.get("created_by")),
        reviewed_by=_optional_str(values.get("created_by")),
        reviewed_at=None,
        updated_at="",
    )
    return metadata


def _payload_prompt_versions(agent: dict[str, object]) -> list[dict[str, object]]:
    metadata = _dict_value(agent.get("metadata"))
    raw_versions = agent.get("prompt_versions")
    if isinstance(raw_versions, list):
        versions = [dict(item) for item in raw_versions if isinstance(item, dict)]
    else:
        versions = [
            {
                "version": 1,
                "prompt": str(agent["prompt"]),
                "change_summary": "initial prompt",
                "created_by": agent.get("created_by"),
                "created_at": str(agent.get("created_at") or agent.get("updated_at") or ""),
            }
        ]
    return [_enrich_prompt_version_review_payload(item, metadata) for item in versions]


def _agent_prompt_versions_payload(agent: AuditAgent) -> list[dict[str, object]]:
    metadata = _dict_value(agent.extra_metadata)
    versions = [
        _prompt_version_to_payload(item)
        for item in sorted(agent.prompt_versions, key=lambda version: version.version)
    ]
    return [_enrich_prompt_version_review_payload(item, metadata) for item in versions]


def _prompt_version_to_payload(version: AuditAgentPromptVersion) -> dict[str, object]:
    return {
        "version": version.version,
        "prompt": version.prompt,
        "change_summary": version.change_summary,
        "created_by": version.created_by,
        "created_at": _datetime_to_iso(version.created_at),
    }


def _enrich_prompt_version_review_payload(
    version: dict[str, object],
    metadata: dict[str, object],
) -> dict[str, object]:
    version_number = _int_value(version.get("version"), default=1)
    reviews = _prompt_version_reviews(metadata)
    raw_review = reviews.get(str(version_number))
    review = raw_review if isinstance(raw_review, dict) else {}
    status = validate_agent_prompt_review_status(str(review.get("status") or "approved"))
    active_version = _int_value(metadata.get("prompt_version"), default=1)
    version["review_status"] = status
    version["review_note"] = str(review.get("note") or "")
    version["requested_by"] = _optional_str(review.get("requested_by"))
    version["reviewed_by"] = _optional_str(review.get("reviewed_by"))
    version["reviewed_at"] = _optional_str(review.get("reviewed_at"))
    version["review_updated_at"] = _optional_str(review.get("updated_at"))
    version["is_active"] = version_number == active_version
    return version


def _prompt_version_reviews(metadata: dict[str, object]) -> dict[str, object]:
    raw_reviews = metadata.get("prompt_version_reviews")
    if isinstance(raw_reviews, dict):
        return dict(raw_reviews)
    return {}


def _invocation_to_payload(invocation: AuditAgentInvocation) -> dict[str, object]:
    return {
        "id": str(invocation.id),
        "agent_key": invocation.agent_key,
        "prompt_version": invocation.prompt_version,
        "prompt_version_key": invocation.prompt_version_key,
        "invocation_source": invocation.invocation_source,
        "question": invocation.question,
        "conversation_ref": invocation.conversation_ref,
        "created_by": invocation.created_by,
        "created_at": _datetime_to_iso(invocation.created_at),
        "metadata": copy.deepcopy(invocation.extra_metadata),
    }


def _feedback_to_payload(feedback: AuditAgentFeedback) -> dict[str, object]:
    return {
        "id": str(feedback.id),
        "agent_key": feedback.agent_key,
        "invocation_id": str(feedback.invocation_id) if feedback.invocation_id else None,
        "prompt_version": feedback.prompt_version,
        "rating": feedback.rating,
        "comment": feedback.comment,
        "created_by": feedback.created_by,
        "created_at": _datetime_to_iso(feedback.created_at),
        "metadata": copy.deepcopy(feedback.extra_metadata),
    }


def _latest_payload_prompt_version(agent: dict[str, object]) -> int:
    return max(
        (_int_value(item.get("version"), default=1) for item in _payload_prompt_versions(agent)),
        default=1,
    )


def _new_agent_key() -> str:
    return f"{AGENT_ID_PREFIX}{uuid4().hex[:12]}"


def market_agent_template_id(values: dict[str, object]) -> str | None:
    metadata = _dict_value(values.get("metadata"))
    if _optional_str(metadata.get("source")) != "agent-market":
        return None
    template_id = _optional_str(metadata.get("template_id"))
    if template_id is None or len(template_id) > 128:
        raise ValueError("agent-market metadata.template_id must be 1..128 characters")
    return template_id


def _market_agent_key(values: dict[str, object]) -> str:
    template_id = market_agent_template_id(values)
    created_by = _optional_str(values.get("created_by"))
    project_name = _optional_str(values.get("project_name"))
    if template_id is None or created_by is None or project_name is None:
        raise ValueError("agent-market install identity is incomplete")
    digest = sha256(
        "\0".join((created_by, project_name, template_id)).encode("utf-8")
    ).hexdigest()[:32]
    return f"{AGENT_ID_PREFIX}market-{digest}"


def _find_market_agent_install(
    session: Session,
    values: dict[str, object],
) -> AuditAgent | None:
    created_by = _optional_str(values.get("created_by"))
    project_name = _optional_str(values.get("project_name"))
    if created_by is None or project_name is None:
        raise ValueError("agent-market install identity is incomplete")
    candidates = session.scalars(
        select(AuditAgent)
        .where(
            AuditAgent.created_by == created_by,
            func.trim(AuditAgent.project_name) == project_name,
        )
        .order_by(AuditAgent.updated_at.desc(), AuditAgent.created_at.desc())
    ).all()
    matches = [
        agent for agent in candidates if _agent_matches_market_install(agent, values)
    ]
    if len(matches) > 1:
        raise DuplicateMarketAgentInstallError(
            "multiple market agent installations already exist"
        )
    return matches[0] if matches else None


def _agent_matches_market_install(
    agent: AuditAgent,
    values: dict[str, object],
) -> bool:
    metadata = _dict_value(agent.extra_metadata)
    return (
        agent.created_by == _optional_str(values.get("created_by"))
        and _optional_str(agent.project_name)
        == _optional_str(values.get("project_name"))
        and _optional_str(metadata.get("source")) == "agent-market"
        and _optional_str(metadata.get("template_id"))
        == market_agent_template_id(values)
    )


def _payload_matches_market_install(
    agent: dict[str, object],
    values: dict[str, object],
) -> bool:
    metadata = _dict_value(agent.get("metadata"))
    return (
        _optional_str(agent.get("created_by")) == _optional_str(values.get("created_by"))
        and _optional_str(agent.get("project_name"))
        == _optional_str(values.get("project_name"))
        and _optional_str(metadata.get("source")) == "agent-market"
        and _optional_str(metadata.get("template_id"))
        == market_agent_template_id(values)
    )


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


def _int_value(value: object, *, default: int) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def _default_agent_payload(agent_key: str) -> dict[str, object] | None:
    agent = next(
        (dict(agent) for agent in DEFAULT_AGENT_PAYLOADS if agent["id"] == agent_key),
        None,
    )
    return _enrich_agent_payload(agent) if agent is not None else None


def _string_list_value(value: object, *, default: list[str]) -> list[str]:
    if isinstance(value, list):
        normalized = [str(item) for item in value if str(item) in AGENT_ALLOWED_ROLES]
        return normalized or default
    return default


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
