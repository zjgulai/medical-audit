from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from medical_audit_kb.db.models import AuditProjectMember, Base, utc_now

PROJECT_MEMBER_ROLES = ("项目负责人", "审计员", "业务专家", "信息科", "只读观察员")
PROJECT_MEMBER_STATUSES = ("在项目中", "待确认")
PROJECT_MEMBER_ID_PREFIX = "member-custom-"

DEFAULT_PROJECT_PAYLOADS: tuple[dict[str, object], ...] = (
    {
        "id": "SELF-CHECK-FUND-20260607",
        "name": "医保基金使用合规专项自查",
        "audit_topic": "医保基金使用合规",
        "organization_name": "单院医保内审试运行",
        "member_count": 3,
        "creator": "项目负责人",
        "created_at": "2026-06-07",
        "status": "进行中",
        "operation_label": "进入项目",
        "source": "system-default",
    },
    {
        "id": "CATALOG-LIMIT-202606",
        "name": "医保目录限制条件核验",
        "audit_topic": "目录限制",
        "organization_name": "单院医保内审试运行",
        "member_count": 4,
        "creator": "业务专家",
        "created_at": "2026-06-09",
        "status": "待启动",
        "operation_label": "查看成员",
        "source": "system-default",
    },
    {
        "id": "OUTPATIENT-DOSE-202606",
        "name": "门诊超量开药专项复核",
        "audit_topic": "门诊处方合规",
        "organization_name": "单院医保内审试运行",
        "member_count": 5,
        "creator": "审计员",
        "created_at": "2026-06-10",
        "status": "进行中",
        "operation_label": "进入项目",
        "source": "system-default",
    },
    {
        "id": "KB-GOVERNANCE-202606",
        "name": "审计知识库治理项目",
        "audit_topic": "知识库治理",
        "organization_name": "内审部",
        "member_count": 2,
        "creator": "信息科接口人",
        "created_at": "2026-06-11",
        "status": "已归档",
        "operation_label": "查看归档",
        "source": "system-default",
    },
)

DEFAULT_PROJECT_MEMBERS_BY_PROJECT: dict[str, tuple[dict[str, object], ...]] = {
    "SELF-CHECK-FUND-20260607": (
        {
            "id": "member-auditor",
            "name": "审计员",
            "role": "审计员",
            "department": "内审部",
            "status": "在项目中",
        },
        {
            "id": "member-owner",
            "name": "项目负责人",
            "role": "项目负责人",
            "department": "内审部",
            "status": "在项目中",
        },
        {
            "id": "member-it",
            "name": "信息科接口人",
            "role": "信息科",
            "department": "信息科",
            "status": "待确认",
        },
    ),
    "CATALOG-LIMIT-202606": (
        {
            "id": "member-catalog-owner",
            "name": "业务专家",
            "role": "业务专家",
            "department": "医保办",
            "status": "在项目中",
        },
        {
            "id": "member-catalog-auditor",
            "name": "目录审计员",
            "role": "审计员",
            "department": "内审部",
            "status": "在项目中",
        },
        {
            "id": "member-catalog-it",
            "name": "信息科接口人",
            "role": "信息科",
            "department": "信息科",
            "status": "待确认",
        },
        {
            "id": "member-catalog-observer",
            "name": "只读观察员",
            "role": "只读观察员",
            "department": "财务科",
            "status": "待确认",
        },
    ),
    "OUTPATIENT-DOSE-202606": (
        {
            "id": "member-dose-auditor",
            "name": "审计员",
            "role": "审计员",
            "department": "内审部",
            "status": "在项目中",
        },
        {
            "id": "member-dose-owner",
            "name": "项目负责人",
            "role": "项目负责人",
            "department": "内审部",
            "status": "在项目中",
        },
        {
            "id": "member-dose-expert",
            "name": "药剂科专家",
            "role": "业务专家",
            "department": "药剂科",
            "status": "在项目中",
        },
        {
            "id": "member-dose-it",
            "name": "信息科接口人",
            "role": "信息科",
            "department": "信息科",
            "status": "待确认",
        },
        {
            "id": "member-dose-observer",
            "name": "只读观察员",
            "role": "只读观察员",
            "department": "门诊办",
            "status": "待确认",
        },
    ),
    "KB-GOVERNANCE-202606": (
        {
            "id": "member-kb-it",
            "name": "信息科接口人",
            "role": "信息科",
            "department": "信息科",
            "status": "在项目中",
        },
        {
            "id": "member-kb-owner",
            "name": "项目负责人",
            "role": "项目负责人",
            "department": "内审部",
            "status": "在项目中",
        },
    ),
}

_PROJECT_KEYS = frozenset(str(project["id"]) for project in DEFAULT_PROJECT_PAYLOADS)


class ProjectMemberStore(Protocol):
    def list_members(self, project_key: str) -> list[dict[str, object]]:
        pass

    def add_member(self, project_key: str, values: dict[str, object]) -> dict[str, object]:
        pass

    def member_counts(self) -> dict[str, int]:
        pass


@dataclass(slots=True)
class SqlAlchemyProjectMemberStore:
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

    def list_members(self, project_key: str) -> list[dict[str, object]]:
        with self._session_factory() as session:
            statement = (
                select(AuditProjectMember)
                .where(AuditProjectMember.project_key == project_key)
                .order_by(
                    AuditProjectMember.updated_at.desc(),
                    AuditProjectMember.created_at.desc(),
                )
            )
            return [_member_to_payload(member) for member in session.scalars(statement).all()]

    def add_member(self, project_key: str, values: dict[str, object]) -> dict[str, object]:
        now = utc_now()
        member = AuditProjectMember(
            member_key=_new_member_key(),
            project_key=project_key,
            name=str(values["name"]),
            role=str(values["role"]),
            department=str(values["department"]),
            status=str(values.get("status", "待确认")),
            created_by=_optional_str(values.get("created_by")),
            extra_metadata=_dict_value(values.get("metadata")),
            created_at=now,
            updated_at=now,
        )
        with self._session_factory.begin() as session:
            session.add(member)
            session.flush()
            return _member_to_payload(member)

    def member_counts(self) -> dict[str, int]:
        with self._session_factory() as session:
            rows = session.execute(
                select(AuditProjectMember.project_key, func.count(AuditProjectMember.id)).group_by(
                    AuditProjectMember.project_key
                )
            )
            return {str(project_key): int(count) for project_key, count in rows.all()}


@dataclass(slots=True)
class InMemoryProjectMemberStore:
    members: dict[str, list[dict[str, object]]] = field(default_factory=dict)

    def list_members(self, project_key: str) -> list[dict[str, object]]:
        return [copy.deepcopy(member) for member in self.members.get(project_key, [])]

    def add_member(self, project_key: str, values: dict[str, object]) -> dict[str, object]:
        now = _datetime_to_iso(utc_now())
        member: dict[str, object] = {
            "id": _new_member_key(),
            "project_key": project_key,
            "name": str(values["name"]),
            "role": str(values["role"]),
            "department": str(values["department"]),
            "status": str(values.get("status", "待确认")),
            "created_by": _optional_str(values.get("created_by")),
            "created_at": now,
            "updated_at": now,
            "source": "custom",
            "metadata": _dict_value(values.get("metadata")),
        }
        self.members.setdefault(project_key, []).insert(0, member)
        return copy.deepcopy(member)

    def member_counts(self) -> dict[str, int]:
        return {project_key: len(members) for project_key, members in self.members.items()}


def project_exists(project_key: str) -> bool:
    return project_key in _PROJECT_KEYS


def project_payloads_with_member_counts(custom_counts: dict[str, int]) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for project in DEFAULT_PROJECT_PAYLOADS:
        project_key = str(project["id"])
        item = copy.deepcopy(project)
        item["member_count"] = (
            _default_member_count(project_key) + custom_counts.get(project_key, 0)
        )
        items.append(item)
    return items


def combined_project_members(
    project_key: str,
    custom_members: list[dict[str, object]],
) -> list[dict[str, object]]:
    seen_ids = {str(member.get("id")) for member in custom_members}
    defaults = [
        _default_member_payload(project_key, member)
        for member in DEFAULT_PROJECT_MEMBERS_BY_PROJECT.get(project_key, ())
        if str(member["id"]) not in seen_ids
    ]
    return [*custom_members, *defaults]


def validate_project_member_role(role: str) -> str:
    if role not in PROJECT_MEMBER_ROLES:
        raise ValueError(f"unsupported project member role: {role}")
    return role


def validate_project_member_status(status: str) -> str:
    if status not in PROJECT_MEMBER_STATUSES:
        raise ValueError(f"unsupported project member status: {status}")
    return status


def _default_member_count(project_key: str) -> int:
    return len(DEFAULT_PROJECT_MEMBERS_BY_PROJECT.get(project_key, ()))


def _default_member_payload(
    project_key: str,
    member: dict[str, object],
) -> dict[str, object]:
    payload = copy.deepcopy(member)
    payload["project_key"] = project_key
    payload["source"] = "system-default"
    payload["created_by"] = "system"
    payload["metadata"] = {}
    return payload


def _member_to_payload(member: AuditProjectMember) -> dict[str, object]:
    return {
        "id": member.member_key,
        "project_key": member.project_key,
        "name": member.name,
        "role": member.role,
        "department": member.department,
        "status": member.status,
        "created_by": member.created_by,
        "created_at": _datetime_to_iso(member.created_at),
        "updated_at": _datetime_to_iso(member.updated_at),
        "source": "custom",
        "metadata": copy.deepcopy(member.extra_metadata),
    }


def _new_member_key() -> str:
    return f"{PROJECT_MEMBER_ID_PREFIX}{uuid4().hex[:12]}"


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
