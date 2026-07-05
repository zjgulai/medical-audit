from __future__ import annotations

from enum import StrEnum
from typing import Final


class SourceCollection(StrEnum):
    MEDICAL_INSURANCE_CATALOG = "medical-insurance-catalog"
    SUPERVISION_RULES_KNOWLEDGE = "supervision-rules-knowledge"
    RISK_NEGATIVE_LIST = "risk-negative-list"
    MEDICAL_INSURANCE_LAWS = "medical-insurance-laws"
    POLICY_GENERAL_POLICY = "policy-general-policy"
    POLICY_REFORM_PILOT = "policy-reform-pilot"
    POLICY_FINANCE_PRICE_PROCUREMENT = "policy-finance-price-procurement"
    POLICY_SOCIAL_SECURITY_LIVELIHOOD = "policy-social-security-livelihood"
    POLICY_INDUSTRY_BUSINESS_ENVIRONMENT = "policy-industry-business-environment"
    POLICY_DATA_STATISTICS_DISCLOSURE = "policy-data-statistics-disclosure"
    MANAGEMENT_GENERAL_ADMIN = "management-general-admin"
    MANAGEMENT_LICENSE_ENFORCEMENT = "management-license-enforcement"
    MANAGEMENT_ORG_PERSONNEL_QUALIFICATION = "management-org-personnel-qualification"
    MANAGEMENT_URBAN_MUNICIPAL = "management-urban-municipal"
    MANAGEMENT_ECOLOGY_RESOURCES = "management-ecology-resources"
    MANAGEMENT_SAFETY_EMERGENCY = "management-safety-emergency"
    MANAGEMENT_MARKET_QUALITY = "management-market-quality"
    MANAGEMENT_JUDICIAL_AUDIT_PROCEDURE = "management-judicial-audit-procedure"
    OTHER_EDUCATION_RESEARCH = "other-education-research"
    OTHER_CULTURE_TOURISM_SPORTS = "other-culture-tourism-sports"
    OTHER_AGRICULTURE_WATER = "other-agriculture-water"
    OTHER_TRANSPORT_MARITIME = "other-transport-maritime"
    OTHER_ETHNIC_RELIGIOUS_FOREIGN = "other-ethnic-religious-foreign"
    OTHER_DEFENSE_CONFIDENTIALITY = "other-defense-confidentiality"
    PERSONAL_MATERIALS = "personal-materials"


DEFAULT_QUERY_SOURCE_COLLECTIONS: Final[frozenset[SourceCollection]] = frozenset(
    {
        SourceCollection.MEDICAL_INSURANCE_CATALOG,
        SourceCollection.MEDICAL_INSURANCE_LAWS,
        SourceCollection.RISK_NEGATIVE_LIST,
        SourceCollection.SUPERVISION_RULES_KNOWLEDGE,
    }
)

SYSTEM_SOURCE_COLLECTIONS: Final[frozenset[SourceCollection]] = frozenset(
    collection
    for collection in SourceCollection
    if collection != SourceCollection.PERSONAL_MATERIALS
)


class DocumentStatus(StrEnum):
    INDEX_CANDIDATE = "index-candidate"
    INDEXED = "indexed"
    PENDING = "pending"
    FAILED = "failed"
    IGNORED = "ignored"


class IndexVersionStatus(StrEnum):
    BUILDING = "building"
    ACTIVE = "active"
    FAILED = "failed"
    DEPRECATED = "deprecated"


class IndexJobType(StrEnum):
    INCREMENTAL = "incremental"
    FULL_REBUILD = "full-rebuild"
    RETRY_FILE = "retry-file"


class IndexJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class FileQueueStatus(StrEnum):
    OPEN = "open"
    RETRYING = "retrying"
    RESOLVED = "resolved"
    IGNORED = "ignored"


class FileErrorType(StrEnum):
    UNSUPPORTED_TYPE = "unsupported-type"
    EXTRACTION_FAILED = "extraction-failed"
    LOW_QUALITY_TEXT = "low-quality-text"
    VALIDATION_FAILED = "validation-failed"
