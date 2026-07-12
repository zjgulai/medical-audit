from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.exc import SQLAlchemyError

from medical_audit_kb.api.app import ApiState, get_api_state, record_operation
from medical_audit_kb.api.auth import (
    AuthenticatedUser,
    HospitalRole,
    Permission,
    require_permission,
    resolve_authenticated_user,
)
from medical_audit_kb.api.project_member_store import (
    PROJECT_MEMBER_ROLES,
    PROJECT_MEMBER_STATUSES,
    PROJECT_STATUSES,
    InMemoryProjectMemberStore,
    ProjectMemberStore,
    combined_project_members,
    project_exists,
    project_payloads_with_member_counts,
    validate_project_member_role,
    validate_project_member_status,
    visible_project_keys,
)

router = APIRouter()

REVIEW_STATUS_LABELS: dict[str, str] = {
    "pending-review": "待复核",
    "needs-evidence": "需补证",
    "confirmed-violation": "确认违规",
    "not-violation": "排除违规",
    "closed": "已关闭",
}


class ProjectMemberCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_identifier: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=128)
    role: str = Field(min_length=1, max_length=48)
    department: str = Field(min_length=1, max_length=128)
    status: str = Field(default="待确认", min_length=1, max_length=48)
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("user_identifier")
    @classmethod
    def normalize_user_identifier(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("user_identifier is required")
        return normalized

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        try:
            return validate_project_member_role(value)
        except ValueError as exc:
            raise ValueError("unsupported project member role") from exc

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        try:
            return validate_project_member_status(value)
        except ValueError as exc:
            raise ValueError("unsupported project member status") from exc


@router.get("/projects")
def list_projects(
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> dict[str, object]:
    user = resolve_authenticated_user(
        state,
        x_user_id=x_user_id,
        x_role=x_role,
        default_role=HospitalRole.MEMBER,
    )
    store = _project_member_store(state)
    try:
        all_items = project_payloads_with_member_counts(store.member_counts())
        store_ready = True
        store_backend = store.__class__.__name__
    except SQLAlchemyError:
        all_items = project_payloads_with_member_counts({})
        store_ready = False
        store_backend = "unavailable"

    visible_keys = visible_project_keys(
        user_identifier=user.user_identifier,
        is_admin=user.role is HospitalRole.ADMIN,
        store=store,
    )
    items = [item for item in all_items if str(item["id"]) in visible_keys]

    record_operation(
        state,
        "projects-list",
        {
            "actor": user.user_identifier,
            "actor_role": user.role.value,
            "project_count": len(items),
            "visible_project_count": len(items),
        },
    )
    return {
        "items": items,
        "roles": list(PROJECT_MEMBER_ROLES),
        "statuses": list(PROJECT_MEMBER_STATUSES),
        "project_statuses": list(PROJECT_STATUSES),
        "store": {"ready": store_ready, "backend": store_backend},
    }


@router.get("/projects/{project_key}")
def get_project(
    project_key: str,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> dict[str, object]:
    user, store, visible_keys = _visible_project_user(
        project_key,
        state,
        x_user_id=x_user_id,
        x_role=x_role,
    )
    try:
        project = next(
            item
            for item in project_payloads_with_member_counts(store.member_counts())
            if item["id"] == project_key
        )
        store_ready = True
        store_backend = store.__class__.__name__
    except SQLAlchemyError:
        project = next(
            item
            for item in project_payloads_with_member_counts({})
            if item["id"] == project_key
        )
        store_ready = False
        store_backend = "unavailable"

    record_operation(
        state,
        "project-detail",
        {
            "project_key": project_key,
            "actor": user.user_identifier,
            "actor_role": user.role.value,
            "visible_project_count": len(visible_keys),
        },
    )
    return {
        "item": project,
        "store": {"ready": store_ready, "backend": store_backend},
        "production_side_effect": "none",
    }


@router.get("/projects/{project_key}/members")
def list_project_members(
    project_key: str,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> dict[str, object]:
    user, store, visible_keys = _visible_project_user(
        project_key,
        state,
        x_user_id=x_user_id,
        x_role=x_role,
    )
    try:
        custom_members = store.list_members(project_key)
    except SQLAlchemyError:
        items = combined_project_members(project_key, [])
        record_operation(
            state,
            "project-members-list",
            {
                "project_key": project_key,
                "actor": user.user_identifier,
                "actor_role": user.role.value,
                "visible_project_count": len(visible_keys),
                "member_count": len(items),
            },
        )
        return {
            "items": items,
            "project_key": project_key,
            "roles": list(PROJECT_MEMBER_ROLES),
            "statuses": list(PROJECT_MEMBER_STATUSES),
            "store": {"ready": False, "backend": "unavailable"},
        }

    items = combined_project_members(project_key, custom_members)
    record_operation(
        state,
        "project-members-list",
        {
            "project_key": project_key,
            "actor": user.user_identifier,
            "actor_role": user.role.value,
            "visible_project_count": len(visible_keys),
            "member_count": len(items),
        },
    )
    return {
        "items": items,
        "project_key": project_key,
        "roles": list(PROJECT_MEMBER_ROLES),
        "statuses": list(PROJECT_MEMBER_STATUSES),
        "store": {"ready": True, "backend": store.__class__.__name__},
    }


@router.get("/projects/{project_key}/dashboard")
def project_dashboard(
    project_key: str,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> dict[str, object]:
    user, store, visible_keys = _visible_project_user(
        project_key,
        state,
        x_user_id=x_user_id,
        x_role=x_role,
    )
    try:
        project = next(
            item for item in project_payloads_with_member_counts(store.member_counts())
            if item["id"] == project_key
        )
        members = combined_project_members(project_key, store.list_members(project_key))
        member_store_ready = True
        member_store_backend = store.__class__.__name__
    except SQLAlchemyError:
        project = next(
            item
            for item in project_payloads_with_member_counts({})
            if item["id"] == project_key
        )
        members = combined_project_members(project_key, [])
        member_store_ready = False
        member_store_backend = "unavailable"

    findings, finding_store_payload = _dashboard_findings(state)
    stats = _dashboard_finding_stats(findings)
    response: dict[str, object] = {
        "format": "project-dashboard-v1",
        "project": project,
        "metrics": _dashboard_metrics(stats, findings, members),
        "queue": _dashboard_queue(findings),
        "activities": _dashboard_activities(stats, findings, member_store_ready),
        "status_distribution": _dashboard_status_distribution(findings),
        "member_workloads": _dashboard_member_workloads(members, findings),
        "evidence_grade": (
            "live-db-connected"
            if bool(finding_store_payload["ready"]) or member_store_ready
            else "backend-defaults"
        ),
        "production_side_effect": "none",
        "store": {
            "ready": member_store_ready or bool(finding_store_payload["ready"]),
            "backend": {
                "project_members": member_store_backend,
                "audit_findings": finding_store_payload["backend"],
            },
        },
    }
    record_operation(
        state,
        "project-dashboard",
        {
            "project_key": project_key,
            "actor": user.user_identifier,
            "actor_role": user.role.value,
            "visible_project_count": len(visible_keys),
            "member_count": len(members),
            "finding_count": stats["total"],
            "member_store_ready": member_store_ready,
            "finding_store_ready": bool(finding_store_payload["ready"]),
        },
    )
    return response


@router.post("/projects/{project_key}/members")
def create_project_member(
    project_key: str,
    payload: ProjectMemberCreateRequest,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> dict[str, object]:
    _require_project(project_key)
    user = require_permission(
        state,
        permission=Permission.MANAGE_PROJECT_MEMBERS,
        x_user_id=x_user_id,
        x_role=x_role,
        attempted_action="project-member-create",
        project_key=project_key,
    )
    values = payload.model_dump()
    values["created_by"] = user.user_identifier
    try:
        member = _project_member_store(state).add_member(project_key, values)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=409,
            detail="persistent project member store is not available",
        ) from exc

    record_operation(
        state,
        "project-member-create",
        {
            "project_key": project_key,
            "member_id": member["id"],
            "role": member["role"],
            "created_by": user.user_identifier,
            "actor_role": user.role.value,
            "actor_role_label": user.role_label,
        },
    )
    return {
        "item": member,
        "store": {"ready": True, "backend": _project_member_store(state).__class__.__name__},
    }


def _require_project(project_key: str) -> None:
    if not project_exists(project_key):
        raise HTTPException(status_code=404, detail="project not found")


def _visible_project_user(
    project_key: str,
    state: ApiState,
    *,
    x_user_id: str | None,
    x_role: str | None,
) -> tuple[AuthenticatedUser, ProjectMemberStore, frozenset[str]]:
    _require_project(project_key)
    user = resolve_authenticated_user(
        state,
        x_user_id=x_user_id,
        x_role=x_role,
        default_role=HospitalRole.MEMBER,
        project_key=project_key,
    )
    store = _project_member_store(state)
    visible_keys = visible_project_keys(
        user_identifier=user.user_identifier,
        is_admin=user.role is HospitalRole.ADMIN,
        store=store,
    )
    if project_key not in visible_keys:
        raise HTTPException(status_code=404, detail="project not found")
    return user, store, visible_keys


def _project_member_store(state: ApiState) -> ProjectMemberStore:
    if state.project_member_store is None:
        state.project_member_store = InMemoryProjectMemberStore()
    return state.project_member_store


def _dashboard_findings(state: ApiState) -> tuple[list[dict[str, object]], dict[str, object]]:
    if state.audit_finding_store is None:
        return [], {"ready": False, "backend": "none"}
    try:
        findings = state.audit_finding_store.list_findings(limit=100)
    except SQLAlchemyError:
        return [], {"ready": False, "backend": "unavailable"}
    return findings, {"ready": True, "backend": state.audit_finding_store.__class__.__name__}


def _dashboard_finding_stats(findings: list[dict[str, object]]) -> dict[str, int]:
    return {
        "total": len(findings),
        "open": sum(1 for item in findings if item.get("status") == "open"),
        "pending_review": sum(
            1 for item in findings if item.get("review_status") == "pending-review"
        ),
        "needs_evidence": sum(
            1 for item in findings if item.get("review_status") == "needs-evidence"
        ),
        "linked_review_task": sum(1 for item in findings if item.get("review_task_id")),
    }


def _dashboard_metrics(
    stats: dict[str, int],
    findings: list[dict[str, object]],
    members: list[dict[str, object]],
) -> list[dict[str, str]]:
    return [
        {
            "key": "open_findings",
            "label": "待处理疑点",
            "value": str(stats["open"] or stats["total"]),
            "helper": "来自审计疑点库，需人工确认后进入底稿",
            "tone": "danger" if stats["open"] else "neutral",
        },
        {
            "key": "missing_evidence",
            "label": "待补证据",
            "value": str(stats["needs_evidence"]),
            "helper": "需补充结算明细、目录限制或身份字段",
            "tone": "warning" if stats["needs_evidence"] else "neutral",
        },
        {
            "key": "rule_cards",
            "label": "已关联任务",
            "value": str(stats["linked_review_task"]),
            "helper": f"当前专题成员 {len(members)} 人",
            "tone": "info",
        },
        {
            "key": "backend_status",
            "label": "资料可检索",
            "value": "已接入" if findings else "待生成",
            "helper": "读取后端项目成员与疑点 store",
            "tone": "success" if findings else "neutral",
        },
    ]


def _dashboard_queue(findings: list[dict[str, object]]) -> list[dict[str, str]]:
    if not findings:
        return [
            {
                "id": "QUEUE-BACKEND-001",
                "title": "导入或生成首批审计疑点后进入人工复核",
                "owner": "项目负责人",
                "dueLabel": "待启动",
                "status": "open",
                "risk": "medium",
            }
        ]
    return [
        _finding_to_queue_item(index, finding)
        for index, finding in enumerate(findings[:5], start=1)
    ]


def _finding_to_queue_item(index: int, finding: dict[str, object]) -> dict[str, str]:
    severity = str(finding.get("severity") or "").lower()
    review_status = str(finding.get("review_status") or "")
    return {
        "id": str(finding.get("finding_key") or f"QUEUE-{index:03d}"),
        "title": _finding_title(finding, index),
        "owner": _finding_owner(finding),
        "dueLabel": REVIEW_STATUS_LABELS.get(review_status, "待确认"),
        "status": "closed" if review_status in {"closed", "not-violation"} else "open",
        "risk": (
            "high"
            if severity in {"high", "高"}
            else "medium" if severity in {"medium", "中"} else "low"
        ),
    }


def _finding_title(finding: dict[str, object], index: int) -> str:
    metadata = _dict_like(finding.get("metadata"))
    calculation_trace = _dict_like(finding.get("calculation_trace"))
    for key in ("title", "finding_title", "description", "summary"):
        value = metadata.get(key) or calculation_trace.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return f"复核第 {index} 条{finding.get('finding_type') or '审计'}疑点"


def _dashboard_activities(
    stats: dict[str, int],
    findings: list[dict[str, object]],
    member_store_ready: bool,
) -> list[dict[str, str]]:
    if not findings:
        return [
            {
                "id": "ACT-BACKEND-001",
                "title": "项目成员接口已接入",
                "description": "当前驾驶舱读取后端项目成员 store，疑点数据等待生成或导入。",
                "timeLabel": "刚刚",
            }
        ]
    return [
        {
            "id": "ACT-BACKEND-001",
            "title": "审计疑点已同步",
            "description": (
                f"当前读取 {stats['total']} 条疑点，"
                f"其中 {stats['pending_review']} 条待复核。"
            ),
            "timeLabel": "刚刚",
        },
        {
            "id": "ACT-BACKEND-002",
            "title": "项目成员接口已接入" if member_store_ready else "项目成员使用默认清单",
            "description": "驾驶舱会按后端成员和疑点负责人汇总承接情况。",
            "timeLabel": "刚刚",
        },
    ]


def _dashboard_status_distribution(findings: list[dict[str, object]]) -> list[dict[str, object]]:
    counts: dict[str, int] = {}
    for finding in findings:
        status = str(finding.get("review_status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    if not counts:
        return [{"status": "empty", "label": "暂无疑点", "count": 0}]
    return [
        {"status": status, "label": REVIEW_STATUS_LABELS.get(status, status), "count": count}
        for status, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)
    ]


def _dashboard_member_workloads(
    members: list[dict[str, object]],
    findings: list[dict[str, object]],
) -> list[dict[str, object]]:
    workloads: dict[str, dict[str, object]] = {}
    for member in members:
        name = str(member.get("name") or "未命名成员")
        workloads[name] = {
            "name": name,
            "role": str(member.get("role") or "成员"),
            "department": str(member.get("department") or ""),
            "total": 0,
            "pending": 0,
            "closed": 0,
        }
    for finding in findings:
        owner = _finding_owner(finding)
        item = workloads.setdefault(
            owner,
            {
                "name": owner,
                "role": "待分配",
                "department": "",
                "total": 0,
                "pending": 0,
                "closed": 0,
            },
        )
        item["total"] = int(item["total"]) + 1
        review_status = str(finding.get("review_status") or "")
        if review_status in {"pending-review", "needs-evidence"}:
            item["pending"] = int(item["pending"]) + 1
        if review_status in {"closed", "not-violation", "confirmed-violation"}:
            item["closed"] = int(item["closed"]) + 1
    return sorted(
        workloads.values(),
        key=lambda item: (-int(item["total"]), str(item["name"])),
    )[:8]


def _finding_owner(finding: dict[str, object]) -> str:
    for source in (
        _dict_like(finding.get("metadata")),
        _dict_like(finding.get("calculation_trace")),
        _dict_like(finding.get("source_record_locator")),
    ):
        for key in ("owner", "assignee", "auditor", "reviewer", "employee", "handler"):
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return "未分配"


def _dict_like(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}
