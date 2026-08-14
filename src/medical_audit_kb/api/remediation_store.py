from __future__ import annotations

from collections.abc import Collection, Sequence
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import false, or_, select, update
from sqlalchemy.orm import Session

from medical_audit_kb.db.models import RemediationItem, utc_now

VALID_STATUSES = frozenset({
    "pending-rectification",
    "in-rectification",
    "pending-acceptance",
    "accepted",
    "rejected",
    "closed",
})

REMEDIATION_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "pending-rectification": frozenset({"in-rectification"}),
    "in-rectification": frozenset({"pending-acceptance"}),
    "pending-acceptance": frozenset({"accepted", "rejected"}),
    "accepted": frozenset({"closed"}),
    "rejected": frozenset({"in-rectification"}),
    "closed": frozenset(),
}


class RemediationStatusConflictError(ValueError):
    pass


def list_remediation_items(
    session: Session,
    *,
    project_key: str | None = None,
    status: str | None = None,
    visible_project_keys: Collection[str] | None = None,
    include_legacy_unscoped: bool = False,
    limit: int = 100,
) -> Sequence[RemediationItem]:
    stmt = select(RemediationItem)
    if project_key is not None:
        stmt = stmt.where(RemediationItem.project_key == project_key)
    elif visible_project_keys is not None:
        normalized_project_keys = tuple(sorted(set(visible_project_keys)))
        visibility_filters = []
        if normalized_project_keys:
            visibility_filters.append(RemediationItem.project_key.in_(normalized_project_keys))
        if include_legacy_unscoped:
            visibility_filters.append(RemediationItem.project_key.is_(None))
        stmt = stmt.where(or_(*visibility_filters) if visibility_filters else false())
    if status is not None:
        stmt = stmt.where(RemediationItem.status == status)
    stmt = stmt.order_by(RemediationItem.created_at.desc()).limit(limit)
    return session.scalars(stmt).all()


def get_remediation_item(session: Session, item_id: UUID) -> RemediationItem | None:
    return session.get(RemediationItem, item_id)


def create_remediation_item(
    session: Session,
    *,
    title: str,
    description: str = "",
    project_key: str | None = None,
    audit_finding_id: UUID | None = None,
    responsible_dept: str | None = None,
    responsible_person: str | None = None,
    due_date: datetime | None = None,
    created_by: str | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> RemediationItem:
    item = RemediationItem(
        item_key=f"remediation-{uuid4().hex[:16]}",
        title=title,
        description=description,
        project_key=project_key,
        audit_finding_id=audit_finding_id,
        responsible_dept=responsible_dept,
        responsible_person=responsible_person,
        due_date=due_date,
        created_by=created_by,
        status="pending-rectification",
        extra_metadata=extra_metadata or {},
    )
    session.add(item)
    session.flush()
    return item


def update_remediation_status(
    session: Session,
    item_id: UUID,
    *,
    status: str,
    note: str = "",
    closed_by: str | None = None,
) -> RemediationItem | None:
    item = session.get(RemediationItem, item_id)
    if item is None:
        return None
    if status not in VALID_STATUSES:
        raise ValueError(f"unsupported status: {status}")
    if status not in REMEDIATION_STATUS_TRANSITIONS[item.status]:
        raise ValueError(f"illegal remediation status transition: {item.status} -> {status}")
    previous_status = item.status
    values: dict[str, Any] = {
        "status": status,
        "updated_at": utc_now(),
    }
    if status == "in-rectification":
        if note:
            values["rectification_note"] = note
    elif status in {"accepted", "rejected"}:
        if note:
            values["acceptance_note"] = note
    elif status == "closed":
        values["closed_by"] = closed_by
        values["closed_at"] = utc_now()
    result = session.execute(
        update(RemediationItem)
        .where(
            RemediationItem.id == item_id,
            RemediationItem.status == previous_status,
        )
        .values(**values)
        .execution_options(synchronize_session=False)
    )
    if getattr(result, "rowcount", None) != 1:
        session.expire_all()
        latest = session.get(RemediationItem, item_id)
        latest_status = latest.status if latest is not None else "deleted"
        raise RemediationStatusConflictError(
            "remediation status changed concurrently: "
            f"{previous_status} -> {latest_status}"
        )
    session.expire_all()
    return session.get(RemediationItem, item_id)
