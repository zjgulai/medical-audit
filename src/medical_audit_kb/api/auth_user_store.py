from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from medical_audit_kb.db.models import (
    AuthDepartment,
    AuthUser,
    AuthUserRoleAssignment,
    Base,
    utc_now,
)

AUTH_USER_ID_PREFIX = "auth-user-"
AUTH_ROLE_ASSIGNMENT_ID_PREFIX = "auth-role-assignment-"

DEFAULT_AUTH_DEPARTMENTS: tuple[dict[str, object], ...] = (
    {
        "department_key": "audit-office",
        "name": "内审部",
        "parent_department_key": None,
        "status": "active",
        "metadata": {},
        "source": "system-default",
    },
    {
        "department_key": "it-department",
        "name": "信息科",
        "parent_department_key": None,
        "status": "active",
        "metadata": {},
        "source": "system-default",
    },
    {
        "department_key": "medical-insurance-office",
        "name": "医保办",
        "parent_department_key": None,
        "status": "active",
        "metadata": {},
        "source": "system-default",
    },
)

DEFAULT_AUTH_USERS: tuple[dict[str, object], ...] = (
    {
        "user_key": "next-admin",
        "display_name": "系统管理员",
        "department_key": "it-department",
        "department_name": "信息科",
        "status": "active",
        "created_by": "system",
        "metadata": {},
        "role_assignments": [
            {
                "assignment_key": "auth-role-default-admin",
                "role": "admin",
                "scope_type": "global",
                "scope_key": None,
                "status": "active",
                "assigned_by": "system",
                "metadata": {},
                "source": "system-default",
            }
        ],
        "source": "system-default",
    },
    {
        "user_key": "next-technician",
        "display_name": "信息科技术人员",
        "department_key": "it-department",
        "department_name": "信息科",
        "status": "active",
        "created_by": "system",
        "metadata": {},
        "role_assignments": [
            {
                "assignment_key": "auth-role-default-technician",
                "role": "technician",
                "scope_type": "global",
                "scope_key": None,
                "status": "active",
                "assigned_by": "system",
                "metadata": {},
                "source": "system-default",
            }
        ],
        "source": "system-default",
    },
    {
        "user_key": "next-director",
        "display_name": "审计主任",
        "department_key": "audit-office",
        "department_name": "内审部",
        "status": "active",
        "created_by": "system",
        "metadata": {},
        "role_assignments": [
            {
                "assignment_key": "auth-role-default-director",
                "role": "director",
                "scope_type": "global",
                "scope_key": None,
                "status": "active",
                "assigned_by": "system",
                "metadata": {},
                "source": "system-default",
            }
        ],
        "source": "system-default",
    },
    {
        "user_key": "next-member",
        "display_name": "普通审计成员",
        "department_key": "audit-office",
        "department_name": "内审部",
        "status": "active",
        "created_by": "system",
        "metadata": {},
        "role_assignments": [
            {
                "assignment_key": "auth-role-default-member",
                "role": "member",
                "scope_type": "global",
                "scope_key": None,
                "status": "active",
                "assigned_by": "system",
                "metadata": {},
                "source": "system-default",
            }
        ],
        "source": "system-default",
    },
)


class AuthUserStore(Protocol):
    def list_departments(self) -> list[dict[str, object]]:
        pass

    def list_users(self, *, limit: int = 100) -> list[dict[str, object]]:
        pass

    def get_user(self, user_key: str) -> dict[str, object] | None:
        pass

    def add_user(self, values: dict[str, object]) -> dict[str, object]:
        pass

    def update_user(self, user_key: str, values: dict[str, object]) -> dict[str, object]:
        pass

    def assign_role(self, user_key: str, values: dict[str, object]) -> dict[str, object]:
        pass

    def update_role_assignment(
        self,
        user_key: str,
        assignment_key: str,
        values: dict[str, object],
    ) -> dict[str, object]:
        pass


@dataclass(slots=True)
class SqlAlchemyAuthUserStore:
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

    def list_departments(self) -> list[dict[str, object]]:
        with self._session_factory() as session:
            departments = session.scalars(
                select(AuthDepartment).order_by(AuthDepartment.name.asc())
            ).all()
            return [_department_to_payload(department) for department in departments]

    def list_users(self, *, limit: int = 100) -> list[dict[str, object]]:
        with self._session_factory() as session:
            users = session.scalars(
                select(AuthUser).order_by(AuthUser.updated_at.desc()).limit(limit)
            ).all()
            return [_user_to_payload(session, user) for user in users]

    def get_user(self, user_key: str) -> dict[str, object] | None:
        with self._session_factory() as session:
            user = session.scalar(select(AuthUser).where(AuthUser.user_key == user_key))
            if user is None:
                return None
            return _user_to_payload(session, user)

    def add_user(self, values: dict[str, object]) -> dict[str, object]:
        now = utc_now()
        user = AuthUser(
            user_key=str(values.get("user_key") or _new_user_key()),
            display_name=str(values["display_name"]),
            department_key=_optional_str(values.get("department_key")),
            status=str(values.get("status", "active")),
            created_by=_optional_str(values.get("created_by")),
            extra_metadata=_dict_value(values.get("metadata")),
            created_at=now,
            updated_at=now,
        )
        with self._session_factory.begin() as session:
            _ensure_department(session, user.department_key)
            session.add(user)
            session.flush()
            return _user_to_payload(session, user)

    def assign_role(self, user_key: str, values: dict[str, object]) -> dict[str, object]:
        now = utc_now()
        assignment = AuthUserRoleAssignment(
            assignment_key=_new_role_assignment_key(),
            user_key=user_key,
            role=str(values["role"]),
            scope_type=str(values.get("scope_type", "global")),
            scope_key=_optional_str(values.get("scope_key")),
            status=str(values.get("status", "active")),
            assigned_by=_optional_str(values.get("assigned_by")),
            extra_metadata=_dict_value(values.get("metadata")),
            created_at=now,
            updated_at=now,
        )
        with self._session_factory.begin() as session:
            user = session.scalar(select(AuthUser).where(AuthUser.user_key == user_key))
            if user is None:
                raise ValueError(f"auth user not found: {user_key}")
            session.add(assignment)
            session.flush()
            return _role_assignment_to_payload(assignment)

    def update_user(self, user_key: str, values: dict[str, object]) -> dict[str, object]:
        with self._session_factory.begin() as session:
            user = session.scalar(select(AuthUser).where(AuthUser.user_key == user_key))
            if user is None:
                raise ValueError(f"auth user not found: {user_key}")
            if "department_key" in values:
                department_key = _optional_str(values.get("department_key"))
                _ensure_department(session, department_key)
                user.department_key = department_key
            if "display_name" in values:
                user.display_name = str(values["display_name"])
            if "status" in values:
                user.status = str(values["status"])
            if "metadata" in values:
                user.extra_metadata = _dict_value(values.get("metadata"))
            user.updated_at = utc_now()
            session.flush()
            return _user_to_payload(session, user)

    def update_role_assignment(
        self,
        user_key: str,
        assignment_key: str,
        values: dict[str, object],
    ) -> dict[str, object]:
        with self._session_factory.begin() as session:
            assignment = session.scalar(
                select(AuthUserRoleAssignment).where(
                    AuthUserRoleAssignment.user_key == user_key,
                    AuthUserRoleAssignment.assignment_key == assignment_key,
                )
            )
            if assignment is None:
                raise ValueError(f"auth role assignment not found: {assignment_key}")
            if "role" in values:
                assignment.role = str(values["role"])
            if "scope_type" in values:
                assignment.scope_type = str(values["scope_type"])
            if "scope_key" in values:
                assignment.scope_key = _optional_str(values.get("scope_key"))
            if "status" in values:
                assignment.status = str(values["status"])
            if "metadata" in values:
                assignment.extra_metadata = _dict_value(values.get("metadata"))
            assignment.updated_at = utc_now()
            session.flush()
            return _role_assignment_to_payload(assignment)


@dataclass(slots=True)
class InMemoryAuthUserStore:
    users: list[dict[str, object]] = field(default_factory=list)
    departments: list[dict[str, object]] = field(default_factory=list)

    def _ensure_mutable_users(self) -> None:
        if not self.users:
            self.users = [copy.deepcopy(user) for user in DEFAULT_AUTH_USERS]

    def list_departments(self) -> list[dict[str, object]]:
        if not self.departments:
            return [copy.deepcopy(department) for department in DEFAULT_AUTH_DEPARTMENTS]
        return [copy.deepcopy(department) for department in self.departments]

    def list_users(self, *, limit: int = 100) -> list[dict[str, object]]:
        self._ensure_mutable_users()
        users = [copy.deepcopy(user) for user in self.users]
        return users[:limit]

    def get_user(self, user_key: str) -> dict[str, object] | None:
        for user in self.list_users(limit=500):
            if user.get("user_key") == user_key:
                return copy.deepcopy(user)
        return None

    def add_user(self, values: dict[str, object]) -> dict[str, object]:
        self._ensure_mutable_users()
        now = _datetime_to_iso(utc_now())
        user: dict[str, object] = {
            "user_key": str(values.get("user_key") or _new_user_key()),
            "display_name": str(values["display_name"]),
            "department_key": _optional_str(values.get("department_key")),
            "department_name": _department_name(_optional_str(values.get("department_key"))),
            "status": str(values.get("status", "active")),
            "created_by": _optional_str(values.get("created_by")),
            "metadata": _dict_value(values.get("metadata")),
            "role_assignments": [],
            "created_at": now,
            "updated_at": now,
            "source": "custom",
        }
        self.users.insert(0, user)
        return copy.deepcopy(user)

    def update_user(self, user_key: str, values: dict[str, object]) -> dict[str, object]:
        self._ensure_mutable_users()
        for stored_user in self.users:
            if stored_user.get("user_key") != user_key:
                continue
            if "department_key" in values:
                department_key = _optional_str(values.get("department_key"))
                stored_user["department_key"] = department_key
                stored_user["department_name"] = _department_name(department_key)
            if "display_name" in values:
                stored_user["display_name"] = str(values["display_name"])
            if "status" in values:
                stored_user["status"] = str(values["status"])
            if "metadata" in values:
                stored_user["metadata"] = _dict_value(values.get("metadata"))
            stored_user["updated_at"] = _datetime_to_iso(utc_now())
            return copy.deepcopy(stored_user)
        raise ValueError(f"auth user not found: {user_key}")

    def assign_role(self, user_key: str, values: dict[str, object]) -> dict[str, object]:
        self._ensure_mutable_users()
        user = self.get_user(user_key)
        if user is None:
            raise ValueError(f"auth user not found: {user_key}")
        now = _datetime_to_iso(utc_now())
        assignment: dict[str, object] = {
            "assignment_key": _new_role_assignment_key(),
            "role": str(values["role"]),
            "scope_type": str(values.get("scope_type", "global")),
            "scope_key": _optional_str(values.get("scope_key")),
            "status": str(values.get("status", "active")),
            "assigned_by": _optional_str(values.get("assigned_by")),
            "metadata": _dict_value(values.get("metadata")),
            "created_at": now,
            "updated_at": now,
            "source": "custom",
        }
        for stored_user in self.users:
            if stored_user.get("user_key") == user_key:
                roles = stored_user.setdefault("role_assignments", [])
                if isinstance(roles, list):
                    roles.insert(0, assignment)
                break
        return copy.deepcopy(assignment)

    def update_role_assignment(
        self,
        user_key: str,
        assignment_key: str,
        values: dict[str, object],
    ) -> dict[str, object]:
        self._ensure_mutable_users()
        for stored_user in self.users:
            if stored_user.get("user_key") != user_key:
                continue
            roles = stored_user.get("role_assignments")
            if not isinstance(roles, list):
                break
            for role_assignment in roles:
                if not isinstance(role_assignment, dict):
                    continue
                if role_assignment.get("assignment_key") != assignment_key:
                    continue
                if "role" in values:
                    role_assignment["role"] = str(values["role"])
                if "scope_type" in values:
                    role_assignment["scope_type"] = str(values["scope_type"])
                if "scope_key" in values:
                    role_assignment["scope_key"] = _optional_str(values.get("scope_key"))
                if "status" in values:
                    role_assignment["status"] = str(values["status"])
                if "metadata" in values:
                    role_assignment["metadata"] = _dict_value(values.get("metadata"))
                role_assignment["updated_at"] = _datetime_to_iso(utc_now())
                return copy.deepcopy(role_assignment)
            break
        raise ValueError(f"auth role assignment not found: {assignment_key}")


def combined_auth_users(custom_users: list[dict[str, object]]) -> list[dict[str, object]]:
    seen_keys = {str(user.get("user_key")) for user in custom_users}
    defaults = [
        copy.deepcopy(user) for user in DEFAULT_AUTH_USERS if str(user["user_key"]) not in seen_keys
    ]
    return [*custom_users, *defaults]


def combined_auth_departments(
    custom_departments: list[dict[str, object]],
) -> list[dict[str, object]]:
    seen_keys = {str(department.get("department_key")) for department in custom_departments}
    defaults = [
        copy.deepcopy(department)
        for department in DEFAULT_AUTH_DEPARTMENTS
        if str(department["department_key"]) not in seen_keys
    ]
    return [*custom_departments, *defaults]


def _ensure_department(session: Session, department_key: str | None) -> None:
    if department_key is None:
        return
    existing = session.scalar(
        select(AuthDepartment).where(AuthDepartment.department_key == department_key)
    )
    if existing is not None:
        return
    department = next(
        (
            item
            for item in DEFAULT_AUTH_DEPARTMENTS
            if str(item["department_key"]) == department_key
        ),
        None,
    )
    if department is None:
        return
    session.add(
        AuthDepartment(
            department_key=str(department["department_key"]),
            name=str(department["name"]),
            parent_department_key=_optional_str(department.get("parent_department_key")),
            status=str(department["status"]),
            extra_metadata=_dict_value(department.get("metadata")),
        )
    )


def _department_to_payload(department: AuthDepartment) -> dict[str, object]:
    return {
        "department_key": department.department_key,
        "name": department.name,
        "parent_department_key": department.parent_department_key,
        "status": department.status,
        "metadata": copy.deepcopy(department.extra_metadata),
        "created_at": _datetime_to_iso(department.created_at),
        "updated_at": _datetime_to_iso(department.updated_at),
        "source": "custom",
    }


def _user_to_payload(session: Session, user: AuthUser) -> dict[str, object]:
    assignments = session.scalars(
        select(AuthUserRoleAssignment)
        .where(AuthUserRoleAssignment.user_key == user.user_key)
        .order_by(
            AuthUserRoleAssignment.updated_at.desc(),
            AuthUserRoleAssignment.created_at.desc(),
        )
    ).all()
    department_name = None
    if user.department_key is not None:
        department = session.scalar(
            select(AuthDepartment).where(AuthDepartment.department_key == user.department_key)
        )
        department_name = department.name if department is not None else None
    return {
        "user_key": user.user_key,
        "display_name": user.display_name,
        "department_key": user.department_key,
        "department_name": department_name,
        "status": user.status,
        "created_by": user.created_by,
        "metadata": copy.deepcopy(user.extra_metadata),
        "role_assignments": [
            _role_assignment_to_payload(assignment) for assignment in assignments
        ],
        "created_at": _datetime_to_iso(user.created_at),
        "updated_at": _datetime_to_iso(user.updated_at),
        "source": "custom",
    }


def _role_assignment_to_payload(assignment: AuthUserRoleAssignment) -> dict[str, object]:
    return {
        "assignment_key": assignment.assignment_key,
        "role": assignment.role,
        "scope_type": assignment.scope_type,
        "scope_key": assignment.scope_key,
        "status": assignment.status,
        "assigned_by": assignment.assigned_by,
        "metadata": copy.deepcopy(assignment.extra_metadata),
        "created_at": _datetime_to_iso(assignment.created_at),
        "updated_at": _datetime_to_iso(assignment.updated_at),
        "source": "custom",
    }


def _new_user_key() -> str:
    return f"{AUTH_USER_ID_PREFIX}{uuid4().hex[:12]}"


def _new_role_assignment_key() -> str:
    return f"{AUTH_ROLE_ASSIGNMENT_ID_PREFIX}{uuid4().hex[:12]}"


def _department_name(department_key: str | None) -> str | None:
    if department_key is None:
        return None
    department = next(
        (
            item
            for item in DEFAULT_AUTH_DEPARTMENTS
            if str(item["department_key"]) == department_key
        ),
        None,
    )
    if department is None:
        return None
    return str(department["name"])


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
