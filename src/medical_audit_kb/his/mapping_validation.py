from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class HisFieldRequirement(BaseModel):
    model_config = ConfigDict(frozen=True)

    target_domain: str
    target_field: str
    reason: str
    requires_deidentification_rule: bool = False


class HisFieldMappingInput(BaseModel):
    model_config = ConfigDict(extra="ignore", from_attributes=True, frozen=True)

    source_field: str = Field(min_length=1)
    target_domain: str = Field(min_length=1)
    target_field: str = Field(min_length=1)
    is_required: bool = True
    nullable: bool = False
    deidentification_rule: str | None = None
    status: str = "active"


class HisMissingRequiredTarget(BaseModel):
    model_config = ConfigDict(frozen=True)

    target_domain: str
    target_field: str
    reason: str


class HisDuplicateTargetMapping(BaseModel):
    model_config = ConfigDict(frozen=True)

    target_domain: str
    target_field: str
    source_fields: tuple[str, ...]


class HisNullableRequiredTarget(BaseModel):
    model_config = ConfigDict(frozen=True)

    target_domain: str
    target_field: str
    source_field: str


class HisMissingDeidentificationRule(BaseModel):
    model_config = ConfigDict(frozen=True)

    target_domain: str
    target_field: str
    source_field: str


class HisDomainCoverage(BaseModel):
    model_config = ConfigDict(frozen=True)

    target_domain: str
    required_count: int
    mapped_required_count: int
    missing_required_fields: tuple[str, ...]


class HisMappingValidationReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Literal["pass", "fail"]
    can_create_snapshot: bool
    mapping_count: int
    active_mapping_count: int
    domain_coverage: tuple[HisDomainCoverage, ...]
    missing_required_targets: tuple[HisMissingRequiredTarget, ...]
    duplicate_target_mappings: tuple[HisDuplicateTargetMapping, ...]
    nullable_required_targets: tuple[HisNullableRequiredTarget, ...]
    missing_deidentification_rules: tuple[HisMissingDeidentificationRule, ...]
    inactive_mapping_count: int


CHARGING_COMPLIANCE_REQUIRED_FIELDS: tuple[HisFieldRequirement, ...] = (
    HisFieldRequirement(
        target_domain="visit",
        target_field="patient_anonymous_id",
        reason="links charge details without exposing patient identity",
        requires_deidentification_rule=True,
    ),
    HisFieldRequirement(
        target_domain="visit",
        target_field="visit_id",
        reason="joins visit, diagnosis, order and charge detail records",
    ),
    HisFieldRequirement(
        target_domain="visit",
        target_field="visit_type",
        reason="separates outpatient and inpatient audit scopes",
    ),
    HisFieldRequirement(
        target_domain="visit",
        target_field="visit_started_at",
        reason="bounds the task time window",
    ),
    HisFieldRequirement(
        target_domain="visit",
        target_field="department_code",
        reason="assigns review and rectification responsibility",
    ),
    HisFieldRequirement(
        target_domain="diagnosis",
        target_field="visit_id",
        reason="joins diagnosis records to the audited visit",
    ),
    HisFieldRequirement(
        target_domain="diagnosis",
        target_field="diagnosis_code",
        reason="supports catalog limitation checks",
    ),
    HisFieldRequirement(
        target_domain="diagnosis",
        target_field="diagnosis_name",
        reason="keeps review evidence human-readable",
    ),
    HisFieldRequirement(
        target_domain="charge_detail",
        target_field="charge_id",
        reason="locates the original charge row",
    ),
    HisFieldRequirement(
        target_domain="charge_detail",
        target_field="visit_id",
        reason="groups charge rows by audited visit",
    ),
    HisFieldRequirement(
        target_domain="charge_detail",
        target_field="hospital_item_code",
        reason="groups duplicate charges by hospital item",
    ),
    HisFieldRequirement(
        target_domain="charge_detail",
        target_field="item_name",
        reason="keeps finding evidence readable",
    ),
    HisFieldRequirement(
        target_domain="charge_detail",
        target_field="quantity",
        reason="distinguishes duplicate rows from legitimate quantity",
    ),
    HisFieldRequirement(
        target_domain="charge_detail",
        target_field="unit_price",
        reason="recalculates suspicious charge amount",
    ),
    HisFieldRequirement(
        target_domain="charge_detail",
        target_field="amount",
        reason="reports the suspicious financial impact",
    ),
    HisFieldRequirement(
        target_domain="charge_detail",
        target_field="charged_at",
        reason="evaluates same-day or same-service-window duplication",
    ),
    HisFieldRequirement(
        target_domain="charge_detail",
        target_field="settlement_status",
        reason="excludes voided or unsettled charge rows when configured",
    ),
    HisFieldRequirement(
        target_domain="order_item",
        target_field="order_id",
        reason="supports explainable exclusion when charges have valid orders",
    ),
    HisFieldRequirement(
        target_domain="order_item",
        target_field="visit_id",
        reason="joins orders to the audited visit",
    ),
    HisFieldRequirement(
        target_domain="order_item",
        target_field="hospital_item_code",
        reason="matches orders and charge details on hospital item",
    ),
    HisFieldRequirement(
        target_domain="order_item",
        target_field="ordered_at",
        reason="checks order timing against charge timing",
    ),
    HisFieldRequirement(
        target_domain="item_catalog",
        target_field="hospital_item_code",
        reason="links charge detail to the local item catalog",
    ),
    HisFieldRequirement(
        target_domain="item_catalog",
        target_field="insurance_item_code",
        reason="links local item to insurance catalog evidence",
    ),
    HisFieldRequirement(
        target_domain="item_catalog",
        target_field="item_name",
        reason="keeps catalog evidence readable",
    ),
    HisFieldRequirement(
        target_domain="item_catalog",
        target_field="unit",
        reason="checks quantity and billing unit consistency",
    ),
    HisFieldRequirement(
        target_domain="item_catalog",
        target_field="price",
        reason="checks charge amount against catalog price",
    ),
    HisFieldRequirement(
        target_domain="item_catalog",
        target_field="effective_from",
        reason="validates catalog version at charge time",
    ),
    HisFieldRequirement(
        target_domain="department_staff",
        target_field="department_code",
        reason="links findings to responsible departments",
    ),
    HisFieldRequirement(
        target_domain="department_staff",
        target_field="department_name",
        reason="keeps rectification handoff readable",
    ),
    HisFieldRequirement(
        target_domain="department_staff",
        target_field="doctor_anonymous_id",
        reason="assigns responsibility without exposing doctor identity",
        requires_deidentification_rule=True,
    ),
)


def validate_charging_compliance_field_mappings(
    mappings: Sequence[HisFieldMappingInput | object],
) -> HisMappingValidationReport:
    normalized_mappings = tuple(_normalize_mapping(mapping) for mapping in mappings)
    active_mappings = tuple(
        mapping for mapping in normalized_mappings if mapping.status == "active"
    )
    mapped_targets = {
        (mapping.target_domain, mapping.target_field)
        for mapping in active_mappings
        if mapping.is_required
    }
    requirements_by_target = {
        (requirement.target_domain, requirement.target_field): requirement
        for requirement in CHARGING_COMPLIANCE_REQUIRED_FIELDS
    }

    missing_required_targets = tuple(
        HisMissingRequiredTarget(
            target_domain=requirement.target_domain,
            target_field=requirement.target_field,
            reason=requirement.reason,
        )
        for requirement in CHARGING_COMPLIANCE_REQUIRED_FIELDS
        if (requirement.target_domain, requirement.target_field) not in mapped_targets
    )
    duplicate_target_mappings = _duplicate_target_mappings(active_mappings)
    nullable_required_targets = tuple(
        HisNullableRequiredTarget(
            target_domain=mapping.target_domain,
            target_field=mapping.target_field,
            source_field=mapping.source_field,
        )
        for mapping in active_mappings
        if mapping.is_required
        and mapping.nullable
        and (mapping.target_domain, mapping.target_field) in requirements_by_target
    )
    missing_deidentification_rules = tuple(
        HisMissingDeidentificationRule(
            target_domain=mapping.target_domain,
            target_field=mapping.target_field,
            source_field=mapping.source_field,
        )
        for mapping in active_mappings
        if _requires_deidentification_rule(mapping, requirements_by_target)
        and _missing_deidentification_rule(mapping.deidentification_rule)
    )
    domain_coverage = _domain_coverage(mapped_targets)
    can_create_snapshot = not (
        missing_required_targets
        or duplicate_target_mappings
        or nullable_required_targets
        or missing_deidentification_rules
    )
    return HisMappingValidationReport(
        status="pass" if can_create_snapshot else "fail",
        can_create_snapshot=can_create_snapshot,
        mapping_count=len(normalized_mappings),
        active_mapping_count=len(active_mappings),
        domain_coverage=domain_coverage,
        missing_required_targets=missing_required_targets,
        duplicate_target_mappings=duplicate_target_mappings,
        nullable_required_targets=nullable_required_targets,
        missing_deidentification_rules=missing_deidentification_rules,
        inactive_mapping_count=len(normalized_mappings) - len(active_mappings),
    )


def _normalize_mapping(mapping: HisFieldMappingInput | object) -> HisFieldMappingInput:
    if isinstance(mapping, HisFieldMappingInput):
        return mapping
    return HisFieldMappingInput.model_validate(mapping)


def _duplicate_target_mappings(
    mappings: Sequence[HisFieldMappingInput],
) -> tuple[HisDuplicateTargetMapping, ...]:
    grouped: dict[tuple[str, str], list[str]] = {}
    for mapping in mappings:
        if not mapping.is_required:
            continue
        grouped.setdefault((mapping.target_domain, mapping.target_field), []).append(
            mapping.source_field
        )
    duplicate_targets = [
        (target, tuple(source_fields))
        for target, source_fields in grouped.items()
        if len(set(source_fields)) > 1
    ]
    return tuple(
        HisDuplicateTargetMapping(
            target_domain=target_domain,
            target_field=target_field,
            source_fields=source_fields,
        )
        for (target_domain, target_field), source_fields in sorted(duplicate_targets)
    )


def _domain_coverage(
    mapped_targets: set[tuple[str, str]],
) -> tuple[HisDomainCoverage, ...]:
    requirement_counter = Counter(
        requirement.target_domain for requirement in CHARGING_COMPLIANCE_REQUIRED_FIELDS
    )
    result: list[HisDomainCoverage] = []
    for target_domain in requirement_counter:
        required_fields = tuple(
            requirement.target_field
            for requirement in CHARGING_COMPLIANCE_REQUIRED_FIELDS
            if requirement.target_domain == target_domain
        )
        missing_fields = tuple(
            target_field
            for target_field in required_fields
            if (target_domain, target_field) not in mapped_targets
        )
        result.append(
            HisDomainCoverage(
                target_domain=target_domain,
                required_count=len(required_fields),
                mapped_required_count=len(required_fields) - len(missing_fields),
                missing_required_fields=missing_fields,
            )
        )
    return tuple(result)


def _requires_deidentification_rule(
    mapping: HisFieldMappingInput,
    requirements_by_target: dict[tuple[str, str], HisFieldRequirement],
) -> bool:
    requirement = requirements_by_target.get((mapping.target_domain, mapping.target_field))
    return bool(requirement and requirement.requires_deidentification_rule)


def _missing_deidentification_rule(rule: str | None) -> bool:
    return rule is None or rule.strip().lower() in {"", "none", "not-applicable", "n/a"}
