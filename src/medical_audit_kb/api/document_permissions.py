from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException

from medical_audit_kb.api.auth import (
    HospitalRole,
    Permission,
    has_permission,
    normalize_hospital_role,
)
from medical_audit_kb.domain.constants import SourceCollection

DOCUMENT_SOURCE_COLLECTION_LABELS: dict[SourceCollection, tuple[str, str]] = {
    SourceCollection.MEDICAL_INSURANCE_LAWS: ("法规政策", "公开知识库"),
    SourceCollection.SUPERVISION_RULES_KNOWLEDGE: ("监管两库", "系统知识库"),
    SourceCollection.MEDICAL_INSURANCE_CATALOG: ("医保目录", "系统知识库"),
    SourceCollection.RISK_NEGATIVE_LIST: ("风险清单", "系统知识库"),
}
PERSONAL_MATERIAL_PERMISSION_LABEL = ("个人材料", "个人上传材料")

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
    try:
        normalized = normalize_hospital_role(role, default=HospitalRole.MEMBER)
    except HTTPException as exc:
        if exc.status_code == 403:
            raise HTTPException(status_code=403, detail="role is not allowed to query") from exc
        raise
    if not has_permission(normalized, Permission.QUERY_KNOWLEDGE):
        raise HTTPException(status_code=403, detail="role is not allowed to query")
    return _legacy_api_role(normalized)


def can_read_all_personal_uploads(role: str) -> bool:
    normalized = normalize_hospital_role(role, default=HospitalRole.MEMBER)
    return has_permission(normalized, Permission.READ_ALL_PERSONAL_UPLOADS)


def can_query_personal_materials(role: str) -> bool:
    normalized = normalize_hospital_role(role, default=HospitalRole.MEMBER)
    return has_permission(normalized, Permission.QUERY_KNOWLEDGE)


def document_permissions_for_role(role: str) -> tuple[DocumentPermission, ...]:
    # Current system collections are readable by all authenticated audit roles.
    permissions = tuple(
        DocumentPermission(
            source_collection=collection,
            label=label,
            scope=scope,
            access="read",
        )
        for collection, (label, scope) in DOCUMENT_SOURCE_COLLECTION_LABELS.items()
    )
    if not can_query_personal_materials(role):
        return permissions
    personal_label, personal_scope = PERSONAL_MATERIAL_PERMISSION_LABEL
    personal_access = (
        "explicit-read-all" if can_read_all_personal_uploads(role) else "explicit-owner-read"
    )
    return (
        *permissions,
        DocumentPermission(
            source_collection=SourceCollection.PERSONAL_MATERIALS,
            label=personal_label,
            scope=personal_scope,
            access=personal_access,
        ),
    )


def allowed_source_collections(role: str) -> frozenset[SourceCollection]:
    return frozenset(DOCUMENT_SOURCE_COLLECTION_LABELS)


def allowed_explicit_source_collections(role: str) -> frozenset[SourceCollection]:
    return frozenset(item.source_collection for item in document_permissions_for_role(role))


def enforce_source_collection_access(
    *,
    role: str,
    source_collections: tuple[SourceCollection, ...],
) -> None:
    denied = sorted(
        collection.value
        for collection in source_collections
        if collection not in allowed_explicit_source_collections(role)
    )
    if denied:
        raise HTTPException(
            status_code=403,
            detail={
                "message": "document source collection access denied",
                "denied_source_collections": denied,
            },
        )


def _legacy_api_role(role: HospitalRole) -> str:
    if role == HospitalRole.ADMIN:
        return "it-admin"
    if role == HospitalRole.TECHNICIAN:
        return "technician"
    if role == HospitalRole.DIRECTOR:
        return "department-head"
    return "auditor"
