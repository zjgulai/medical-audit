from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from medical_audit_kb.db.models import AuditProjectMember, Base, utc_now

PROJECT_MEMBER_ROLES = ("项目负责人", "审计员", "业务专家", "信息科", "只读观察员")
PROJECT_MEMBER_STATUSES = ("在项目中", "待确认")
PROJECT_STATUSES = ("待开始", "进行中", "已完成", "已归档")
PROJECT_MEMBER_ID_PREFIX = "member-custom-"


class ProjectMemberIdentityConflictError(ValueError):
    pass

DEFAULT_PROJECT_PAYLOADS: tuple[dict[str, object], ...] = (
    {
        "id": "SELF-CHECK-FUND-20260607",
        "name": "医保基金使用合规专项自查",
        "audit_topic": "医保基金使用合规",
        "organization_name": "单院医保内审试运行",
        "member_count": 3,
        "creator": "项目负责人",
        "creator_user_identifier": "next-director",
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
        "creator_user_identifier": "expert-catalog",
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
        "creator_user_identifier": "auditor-outpatient-dose",
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
        "creator_user_identifier": "it-kb-governance",
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
            "user_identifier": "next-member",
            "name": "审计员",
            "role": "审计员",
            "department": "内审部",
            "status": "在项目中",
        },
        {
            "id": "member-owner",
            "user_identifier": "next-director",
            "name": "项目负责人",
            "role": "项目负责人",
            "department": "内审部",
            "status": "在项目中",
        },
        {
            "id": "member-it",
            "user_identifier": "next-technician",
            "name": "信息科接口人",
            "role": "信息科",
            "department": "信息科",
            "status": "待确认",
        },
    ),
    "CATALOG-LIMIT-202606": (
        {
            "id": "member-catalog-owner",
            "user_identifier": "expert-catalog",
            "name": "业务专家",
            "role": "业务专家",
            "department": "医保办",
            "status": "在项目中",
        },
        {
            "id": "member-catalog-auditor",
            "user_identifier": "auditor-catalog",
            "name": "目录审计员",
            "role": "审计员",
            "department": "内审部",
            "status": "在项目中",
        },
        {
            "id": "member-catalog-it",
            "user_identifier": "it-catalog",
            "name": "信息科接口人",
            "role": "信息科",
            "department": "信息科",
            "status": "待确认",
        },
        {
            "id": "member-catalog-observer",
            "user_identifier": "observer-catalog",
            "name": "只读观察员",
            "role": "只读观察员",
            "department": "财务科",
            "status": "待确认",
        },
    ),
    "OUTPATIENT-DOSE-202606": (
        {
            "id": "member-dose-auditor",
            "user_identifier": "auditor-outpatient-dose",
            "name": "审计员",
            "role": "审计员",
            "department": "内审部",
            "status": "在项目中",
        },
        {
            "id": "member-dose-owner",
            "user_identifier": "owner-outpatient-dose",
            "name": "项目负责人",
            "role": "项目负责人",
            "department": "内审部",
            "status": "在项目中",
        },
        {
            "id": "member-dose-expert",
            "user_identifier": "expert-outpatient-dose",
            "name": "药剂科专家",
            "role": "业务专家",
            "department": "药剂科",
            "status": "在项目中",
        },
        {
            "id": "member-dose-it",
            "user_identifier": "it-outpatient-dose",
            "name": "信息科接口人",
            "role": "信息科",
            "department": "信息科",
            "status": "待确认",
        },
        {
            "id": "member-dose-observer",
            "user_identifier": "observer-outpatient-dose",
            "name": "只读观察员",
            "role": "只读观察员",
            "department": "门诊办",
            "status": "待确认",
        },
    ),
    "KB-GOVERNANCE-202606": (
        {
            "id": "member-kb-it",
            "user_identifier": "it-kb-governance",
            "name": "信息科接口人",
            "role": "信息科",
            "department": "信息科",
            "status": "在项目中",
        },
        {
            "id": "member-kb-owner",
            "user_identifier": "owner-kb-governance",
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
                    AuditProjectMember.member_key.desc(),
                )
            )
            return [_member_to_payload(member) for member in session.scalars(statement).all()]

    def add_member(self, project_key: str, values: dict[str, object]) -> dict[str, object]:
        now = utc_now()
        metadata = _member_metadata(values)
        with self._session_factory.begin() as session:
            existing_members = [
                _member_to_payload(member)
                for member in session.scalars(
                    select(AuditProjectMember)
                    .where(AuditProjectMember.project_key == project_key)
                    .order_by(
                        AuditProjectMember.updated_at.desc(),
                        AuditProjectMember.created_at.desc(),
                        AuditProjectMember.member_key.desc(),
                    )
                ).all()
            ]
            # Application-level gate only; this batch adds no database uniqueness constraint.
            _ensure_project_member_identity_available(
                project_key,
                str(metadata["user_identifier"]),
                existing_members,
            )
            member = AuditProjectMember(
                member_key=_new_member_key(),
                project_key=project_key,
                name=str(values["name"]),
                role=str(values["role"]),
                department=str(values["department"]),
                status=str(values.get("status", "待确认")),
                created_by=_optional_str(values.get("created_by")),
                extra_metadata=metadata,
                created_at=now,
                updated_at=now,
            )
            session.add(member)
            session.flush()
            return _member_to_payload(member)

    def member_counts(self) -> dict[str, int]:
        with self._session_factory() as session:
            members_by_project: dict[str, list[dict[str, object]]] = {}
            for member in session.scalars(
                select(AuditProjectMember).order_by(
                    AuditProjectMember.project_key.asc(),
                    AuditProjectMember.updated_at.desc(),
                    AuditProjectMember.created_at.desc(),
                    AuditProjectMember.member_key.desc(),
                )
            ):
                members_by_project.setdefault(member.project_key, []).append(
                    _member_to_payload(member)
                )
            return {
                project_key: len(_effective_custom_project_members(project_key, members))
                for project_key, members in members_by_project.items()
            }


@dataclass(slots=True)
class InMemoryProjectMemberStore:
    members: dict[str, list[dict[str, object]]] = field(default_factory=dict)

    def list_members(self, project_key: str) -> list[dict[str, object]]:
        return [copy.deepcopy(member) for member in self.members.get(project_key, [])]

    def add_member(self, project_key: str, values: dict[str, object]) -> dict[str, object]:
        now = _datetime_to_iso(utc_now())
        metadata = _member_metadata(values)
        _ensure_project_member_identity_available(
            project_key,
            str(metadata["user_identifier"]),
            self.members.get(project_key, []),
        )
        member: dict[str, object] = {
            "id": _new_member_key(),
            "project_key": project_key,
            "name": str(values["name"]),
            "role": str(values["role"]),
            "department": str(values["department"]),
            "status": str(values.get("status", "待确认")),
            "user_identifier": metadata["user_identifier"],
            "created_by": _optional_str(values.get("created_by")),
            "created_at": now,
            "updated_at": now,
            "source": "custom",
            "metadata": metadata,
        }
        self.members.setdefault(project_key, []).insert(0, member)
        return copy.deepcopy(member)

    def member_counts(self) -> dict[str, int]:
        return {
            project_key: len(_effective_custom_project_members(project_key, members))
            for project_key, members in self.members.items()
        }


def project_exists(project_key: str) -> bool:
    return project_key in _PROJECT_KEYS


def project_payloads_with_member_counts(custom_counts: dict[str, int]) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for project in DEFAULT_PROJECT_PAYLOADS:
        project_key = str(project["id"])
        item = copy.deepcopy(project)
        item["status"] = normalize_project_status(str(item["status"]))
        item["member_count"] = (
            _default_member_count(project_key) + custom_counts.get(project_key, 0)
        )
        items.append(item)
    return items


def visible_project_keys(
    *,
    user_identifier: str,
    is_admin: bool,
    store: ProjectMemberStore,
) -> frozenset[str]:
    normalized_user_identifier = _optional_str(user_identifier)
    if normalized_user_identifier in {None, "anonymous"}:
        return frozenset()
    if is_admin:
        return _PROJECT_KEYS

    default_visible = {
        str(project["id"])
        for project in DEFAULT_PROJECT_PAYLOADS
        if project.get("creator_user_identifier") == normalized_user_identifier
    }
    for project_key, default_members in DEFAULT_PROJECT_MEMBERS_BY_PROJECT.items():
        if any(
            member.get("status") == "在项目中"
            and member.get("user_identifier") == normalized_user_identifier
            for member in default_members
        ):
            default_visible.add(project_key)

    custom_visible: set[str] = set()
    for project_key in _PROJECT_KEYS:
        custom_members = _effective_custom_project_members(
            project_key,
            store.list_members(project_key),
        )
        if any(
            member.get("status") == "在项目中"
            and _member_user_identifier(member) == normalized_user_identifier
            for member in custom_members
        ):
            custom_visible.add(project_key)
    return frozenset(default_visible | custom_visible)


def normalize_project_status(status: str) -> str:
    return "待开始" if status == "待启动" else status


def combined_project_members(
    project_key: str,
    custom_members: list[dict[str, object]],
) -> list[dict[str, object]]:
    effective_custom_members = _effective_custom_project_members(
        project_key,
        custom_members,
    )
    defaults = [
        _default_member_payload(project_key, member)
        for member in DEFAULT_PROJECT_MEMBERS_BY_PROJECT.get(project_key, ())
    ]
    return [*effective_custom_members, *defaults]


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


def _effective_custom_project_members(
    project_key: str,
    custom_members: list[dict[str, object]],
) -> list[dict[str, object]]:
    default_members = DEFAULT_PROJECT_MEMBERS_BY_PROJECT.get(project_key, ())
    seen_identifiers = {
        user_identifier
        for member in default_members
        if (user_identifier := _member_user_identifier(member)) is not None
    }
    seen_record_ids = {
        record_id
        for member in default_members
        if (record_id := _optional_str(member.get("id"))) is not None
    }
    effective_members: list[dict[str, object]] = []
    for member in custom_members:
        user_identifier = _member_user_identifier(member)
        record_id = _optional_str(member.get("id"))
        if user_identifier is not None and user_identifier in seen_identifiers:
            continue
        if record_id is not None and record_id in seen_record_ids:
            continue
        if user_identifier is not None:
            seen_identifiers.add(user_identifier)
        if record_id is not None:
            seen_record_ids.add(record_id)
        effective_members.append(member)
    return effective_members


def _ensure_project_member_identity_available(
    project_key: str,
    user_identifier: str,
    custom_members: list[dict[str, object]],
) -> None:
    default_members = DEFAULT_PROJECT_MEMBERS_BY_PROJECT.get(project_key, ())
    if any(
        _member_user_identifier(member) == user_identifier
        for member in (*default_members, *custom_members)
    ):
        raise ProjectMemberIdentityConflictError(user_identifier)


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
    metadata = copy.deepcopy(member.extra_metadata)
    return {
        "id": member.member_key,
        "project_key": member.project_key,
        "name": member.name,
        "role": member.role,
        "department": member.department,
        "status": member.status,
        "user_identifier": _member_user_identifier({"metadata": metadata}),
        "created_by": member.created_by,
        "created_at": _datetime_to_iso(member.created_at),
        "updated_at": _datetime_to_iso(member.updated_at),
        "source": "custom",
        "metadata": metadata,
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


def _member_metadata(values: dict[str, object]) -> dict[str, object]:
    metadata = _dict_value(values.get("metadata"))
    user_identifier = _optional_str(values.get("user_identifier"))
    if user_identifier is None:
        raise ValueError("user_identifier is required")
    metadata["user_identifier"] = user_identifier
    return metadata


def _member_user_identifier(member: dict[str, object]) -> str | None:
    direct_value = _optional_str(member.get("user_identifier"))
    if direct_value is not None:
        return direct_value
    metadata = _dict_value(member.get("metadata"))
    return _optional_str(metadata.get("user_identifier"))


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
