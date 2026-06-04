from medical_audit_kb.his.mapping_validation import (
    CHARGING_COMPLIANCE_REQUIRED_FIELDS,
    HisFieldMappingInput,
    validate_charging_compliance_field_mappings,
)


def test_charging_compliance_mapping_validation_accepts_complete_contract() -> None:
    report = validate_charging_compliance_field_mappings(_complete_mappings())

    assert report.status == "pass"
    assert report.can_create_snapshot is True
    assert report.mapping_count == len(CHARGING_COMPLIANCE_REQUIRED_FIELDS)
    assert report.missing_required_targets == ()
    assert report.duplicate_target_mappings == ()
    assert report.nullable_required_targets == ()
    assert report.missing_deidentification_rules == ()


def test_charging_compliance_mapping_validation_blocks_incomplete_delivery() -> None:
    mappings = [
        mapping
        for mapping in _complete_mappings()
        if not (
            mapping.target_domain == "charge_detail"
            and mapping.target_field in {"amount", "settlement_status"}
        )
    ]
    mappings.append(
        HisFieldMappingInput(
            source_field="charge_item_code_backup",
            target_domain="charge_detail",
            target_field="hospital_item_code",
        )
    )
    mappings.append(
        HisFieldMappingInput(
            source_field="amount_inactive",
            target_domain="charge_detail",
            target_field="amount",
            status="inactive",
        )
    )
    mappings = [
        mapping.model_copy(update={"nullable": True})
        if mapping.target_domain == "charge_detail" and mapping.target_field == "charged_at"
        else mapping
        for mapping in mappings
    ]
    mappings = [
        mapping.model_copy(update={"deidentification_rule": "none"})
        if mapping.target_domain == "visit" and mapping.target_field == "patient_anonymous_id"
        else mapping
        for mapping in mappings
    ]

    report = validate_charging_compliance_field_mappings(mappings)

    assert report.status == "fail"
    assert report.can_create_snapshot is False
    assert report.inactive_mapping_count == 1
    assert {
        (item.target_domain, item.target_field) for item in report.missing_required_targets
    } == {("charge_detail", "amount"), ("charge_detail", "settlement_status")}
    assert [
        (item.target_domain, item.target_field) for item in report.duplicate_target_mappings
    ] == [("charge_detail", "hospital_item_code")]
    assert [
        (item.target_domain, item.target_field) for item in report.nullable_required_targets
    ] == [("charge_detail", "charged_at")]
    assert [
        (item.target_domain, item.target_field) for item in report.missing_deidentification_rules
    ] == [("visit", "patient_anonymous_id")]


def _complete_mappings() -> list[HisFieldMappingInput]:
    return [
        HisFieldMappingInput(
            source_field=f"{requirement.target_domain}_{requirement.target_field}",
            target_domain=requirement.target_domain,
            target_field=requirement.target_field,
            deidentification_rule=(
                "sha256_with_hospital_salt" if requirement.requires_deidentification_rule else None
            ),
        )
        for requirement in CHARGING_COMPLIANCE_REQUIRED_FIELDS
    ]
