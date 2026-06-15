from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException

from medical_audit_kb.domain.constants import SourceCollection

DOCUMENT_SOURCE_COLLECTION_LABELS: dict[SourceCollection, tuple[str, str]] = {
    SourceCollection.MEDICAL_INSURANCE_LAWS: ("法规政策", "公开知识库"),
    SourceCollection.SUPERVISION_RULES_KNOWLEDGE: ("监管两库", "系统知识库"),
    SourceCollection.MEDICAL_INSURANCE_CATALOG: ("医保目录", "系统知识库"),
    SourceCollection.RISK_NEGATIVE_LIST: ("风险清单", "系统知识库"),
}

READ_ALL_PERSONAL_UPLOAD_ROLES = frozenset({"it-admin", "department-head"})
QUERY_ROLES = frozenset({"auditor", "it-admin", "department-head"})


@dataclass(frozen=True, slots=True)
class DocumentPermission:
    source_collection: SourceCollection
    label: str
    scope: str
    access: str

    def to_payload(self) -> dict[str, object]:
        return {
            "source_collection": self.source_collection.value,
            "label": self.label,
            "scope": self.scope,
            "access": self.access,
        }


def normalize_role(role: str | None) -> str:
    normalized = (role or "auditor").strip() or "auditor"
    if normalized not in QUERY_ROLES:
        raise HTTPException(status_code=403, detail="role is not allowed to query")
    return normalized


def can_read_all_personal_uploads(role: str) -> bool:
    return role in READ_ALL_PERSONAL_UPLOAD_ROLES


def document_permissions_for_role(role: str) -> tuple[DocumentPermission, ...]:
    # Current system collections are readable by all authenticated audit roles.
    return tuple(
        DocumentPermission(
            source_collection=collection,
            label=label,
            scope=scope,
            access="read",
        )
        for collection, (label, scope) in DOCUMENT_SOURCE_COLLECTION_LABELS.items()
    )


def allowed_source_collections(role: str) -> frozenset[SourceCollection]:
    return frozenset(item.source_collection for item in document_permissions_for_role(role))


def enforce_source_collection_access(
    *,
    role: str,
    source_collections: tuple[SourceCollection, ...],
) -> None:
    denied = sorted(
        collection.value
        for collection in source_collections
        if collection not in allowed_source_collections(role)
    )
    if denied:
        raise HTTPException(
            status_code=403,
            detail={
                "message": "document source collection access denied",
                "denied_source_collections": denied,
            },
        )
