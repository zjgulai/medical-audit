from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from medical_audit_kb.db.models import RemediationItem

VALID_STATUSES = frozenset({
    "pending-rectification",
    "in-rectification",
    "pending-acceptance",
    "accepted",
    "rejected",
    "closed",
})


def list_remediation_items(
    session: Session,
    *,
    project_key: str | None = None,
    status: str | None = None,
    limit: int = 100,
) -> Sequence[RemediationItem]:
    stmt = select(RemediationItem).order_by(RemediationItem.created_at.desc()).limit(limit)
    if project_key is not None:
        stmt = stmt.where(RemediationItem.project_key == project_key)
    if status is not None:
        stmt = stmt.where(RemediationItem.status == status)
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
    if status == "in-rectification":
        item.rectification_note = note or item.rectification_note
    elif status in {"accepted", "rejected"}:
        item.acceptance_note = note or item.acceptance_note
    elif status == "closed":
        from medical_audit_kb.db.models import utc_now  # noqa: PLC0415
        item.closed_by = closed_by
        item.closed_at = utc_now()
    item.status = status
    session.flush()
    return item
