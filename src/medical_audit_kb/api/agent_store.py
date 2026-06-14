from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from medical_audit_kb.db.models import AuditAgent, Base, utc_now

AGENT_CATEGORIES = ("业务类", "效率类", "研究类")
AGENT_ID_PREFIX = "agent-custom-"

DEFAULT_AGENT_PAYLOADS: tuple[dict[str, object], ...] = (
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
        "metadata": {},
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
        "metadata": {},
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
        "metadata": {},
    },
)


class AgentStore(Protocol):
    def list_agents(self) -> list[dict[str, object]]:
        pass

    def add_agent(self, values: dict[str, object]) -> dict[str, object]:
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

    def list_agents(self) -> list[dict[str, object]]:
        with self._session_factory() as session:
            statement = (
                select(AuditAgent)
                .where(AuditAgent.status == "active")
                .order_by(AuditAgent.updated_at.desc(), AuditAgent.created_at.desc())
            )
            return [_agent_to_payload(agent) for agent in session.scalars(statement).all()]

    def add_agent(self, values: dict[str, object]) -> dict[str, object]:
        now = utc_now()
        agent = AuditAgent(
            agent_key=_new_agent_key(),
            name=str(values["name"]),
            category=str(values["category"]),
            topic=str(values["topic"]),
            prompt=str(values["prompt"]),
            knowledge_base=str(values["knowledge_base"]),
            project_name=str(values["project_name"]),
            status="active",
            created_by=_optional_str(values.get("created_by")),
            extra_metadata=_dict_value(values.get("metadata")),
            created_at=now,
            updated_at=now,
        )
        with self._session_factory.begin() as session:
            session.add(agent)
            session.flush()
            return _agent_to_payload(agent)


@dataclass(slots=True)
class InMemoryAgentStore:
    agents: list[dict[str, object]] = field(default_factory=list)

    def list_agents(self) -> list[dict[str, object]]:
        return [copy.deepcopy(agent) for agent in self.agents]

    def add_agent(self, values: dict[str, object]) -> dict[str, object]:
        now = _datetime_to_iso(utc_now())
        agent: dict[str, object] = {
            "id": _new_agent_key(),
            "name": str(values["name"]),
            "category": str(values["category"]),
            "topic": str(values["topic"]),
            "prompt": str(values["prompt"]),
            "knowledge_base": str(values["knowledge_base"]),
            "project_name": str(values["project_name"]),
            "status": "active",
            "created_by": _optional_str(values.get("created_by")),
            "created_at": now,
            "updated_at": now,
            "source": "custom",
            "metadata": _dict_value(values.get("metadata")),
        }
        self.agents.insert(0, agent)
        return copy.deepcopy(agent)


def combined_agent_payloads(custom_agents: list[dict[str, object]]) -> list[dict[str, object]]:
    seen_ids = {str(agent.get("id")) for agent in custom_agents}
    defaults = [
        copy.deepcopy(agent)
        for agent in DEFAULT_AGENT_PAYLOADS
        if str(agent["id"]) not in seen_ids
    ]
    return [*custom_agents, *defaults]


def validate_agent_category(category: str) -> str:
    if category not in AGENT_CATEGORIES:
        raise ValueError(f"unsupported agent category: {category}")
    return category


def _agent_to_payload(agent: AuditAgent) -> dict[str, object]:
    return {
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
    }


def _new_agent_key() -> str:
    return f"{AGENT_ID_PREFIX}{uuid4().hex[:12]}"


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
