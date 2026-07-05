from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException

from medical_audit_kb.api.auth import (
    HospitalRole,
    Permission,
    has_permission,
    normalize_hospital_role,
)
from medical_audit_kb.domain.constants import (
    DEFAULT_QUERY_SOURCE_COLLECTIONS,
    SourceCollection,
)

DOCUMENT_SOURCE_COLLECTION_LABELS: dict[SourceCollection, tuple[str, str]] = {
    SourceCollection.MEDICAL_INSURANCE_LAWS: ("法规政策", "公开知识库"),
    SourceCollection.SUPERVISION_RULES_KNOWLEDGE: ("监管两库", "系统知识库"),
    SourceCollection.MEDICAL_INSURANCE_CATALOG: ("医保目录", "系统知识库"),
    SourceCollection.RISK_NEGATIVE_LIST: ("风险清单", "系统知识库"),
    SourceCollection.POLICY_GENERAL_POLICY: ("综合政策与规范性文件", "政策类知识库"),
    SourceCollection.POLICY_REFORM_PILOT: ("规划改革与试点方案", "政策类知识库"),
    SourceCollection.POLICY_FINANCE_PRICE_PROCUREMENT: ("财政价格与采购政策", "政策类知识库"),
    SourceCollection.POLICY_SOCIAL_SECURITY_LIVELIHOOD: ("社会保障与民生政策", "政策类知识库"),
    SourceCollection.POLICY_INDUSTRY_BUSINESS_ENVIRONMENT: ("产业发展与营商环境", "政策类知识库"),
    SourceCollection.POLICY_DATA_STATISTICS_DISCLOSURE: ("数据统计与政务公开", "政策类知识库"),
    SourceCollection.MANAGEMENT_GENERAL_ADMIN: ("综合行政管理", "管理类知识库"),
    SourceCollection.MANAGEMENT_LICENSE_ENFORCEMENT: ("行政许可与监督执法", "管理类知识库"),
    SourceCollection.MANAGEMENT_ORG_PERSONNEL_QUALIFICATION: ("机构人员与资质管理", "管理类知识库"),
    SourceCollection.MANAGEMENT_URBAN_MUNICIPAL: ("城乡建设与市政治理", "管理类知识库"),
    SourceCollection.MANAGEMENT_ECOLOGY_RESOURCES: ("生态环境与资源管理", "管理类知识库"),
    SourceCollection.MANAGEMENT_SAFETY_EMERGENCY: ("安全生产与应急管理", "管理类知识库"),
    SourceCollection.MANAGEMENT_MARKET_QUALITY: ("市场监管与质量管理", "管理类知识库"),
    SourceCollection.MANAGEMENT_JUDICIAL_AUDIT_PROCEDURE: ("司法审计与程序管理", "管理类知识库"),
    SourceCollection.OTHER_EDUCATION_RESEARCH: ("教育科研", "其他类知识库"),
    SourceCollection.OTHER_CULTURE_TOURISM_SPORTS: ("文化旅游体育", "其他类知识库"),
    SourceCollection.OTHER_AGRICULTURE_WATER: ("农业农村与水利", "其他类知识库"),
    SourceCollection.OTHER_TRANSPORT_MARITIME: ("交通运输与海事", "其他类知识库"),
    SourceCollection.OTHER_ETHNIC_RELIGIOUS_FOREIGN: ("民族宗教外事", "其他类知识库"),
    SourceCollection.OTHER_DEFENSE_CONFIDENTIALITY: ("国防保密与征兵", "其他类知识库"),
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


def default_source_collections(role: str) -> frozenset[SourceCollection]:
    return DEFAULT_QUERY_SOURCE_COLLECTIONS


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
