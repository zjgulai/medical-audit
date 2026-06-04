from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal
from uuid import UUID

from medical_audit_kb.audit.charge_rule_001 import ChargeDetailRecord
from medical_audit_kb.db.models import HisFieldMapping, HisStagingRow


@dataclass(frozen=True, slots=True)
class ChargeRule001StagingIssue:
    severity: Literal["warning", "error"]
    issue_type: str
    table_name: str | None
    row_number: int | None
    message: str


@dataclass(frozen=True, slots=True)
class ChargeRule001StagingInputResult:
    status: Literal["pass", "fail"]
    source_batch_key: str
    records: tuple[ChargeDetailRecord, ...]
    issues: tuple[ChargeRule001StagingIssue, ...]
    summary: dict[str, int]


TargetField = tuple[str, str]


def build_charge_rule_001_records_from_staging(
    staging_rows: Sequence[HisStagingRow],
    field_mappings: Sequence[HisFieldMapping],
    *,
    source_batch_key: str,
) -> ChargeRule001StagingInputResult:
    mapping_lookup_by_schema, mapping_issues = _mapping_lookup_by_schema(field_mappings)
    records: list[ChargeDetailRecord] = []
    issues = list(mapping_issues)
    candidate_rows = [
        row
        for row in staging_rows
        if row.status == "staged" and _table_has_charge_detail_mapping(row, field_mappings)
    ]

    for row in candidate_rows:
        record, row_issues = _record_from_staging_row(
            row,
            mapping_lookup=mapping_lookup_by_schema.get(row.table_schema_id or UUID(int=0), {}),
            source_batch_key=source_batch_key,
        )
        issues.extend(row_issues)
        if record is not None:
            records.append(record)

    error_count = sum(1 for issue in issues if issue.severity == "error")
    warning_count = sum(1 for issue in issues if issue.severity == "warning")
    return ChargeRule001StagingInputResult(
        status="fail" if error_count else "pass",
        source_batch_key=source_batch_key,
        records=tuple(records),
        issues=tuple(issues),
        summary={
            "staging_row_count": len(staging_rows),
            "candidate_row_count": len(candidate_rows),
            "converted_record_count": len(records),
            "error_count": error_count,
            "warning_count": warning_count,
        },
    )


def _mapping_lookup_by_schema(
    field_mappings: Sequence[HisFieldMapping],
) -> tuple[dict[UUID, dict[TargetField, str]], tuple[ChargeRule001StagingIssue, ...]]:
    active_mappings = [mapping for mapping in field_mappings if mapping.status == "active"]
    mappings_by_schema: dict[UUID, list[HisFieldMapping]] = {}
    for mapping in active_mappings:
        mappings_by_schema.setdefault(mapping.table_schema_id, []).append(mapping)

    issues: list[ChargeRule001StagingIssue] = []
    lookup_by_schema: dict[UUID, dict[TargetField, str]] = {}
    for table_schema_id, mappings in mappings_by_schema.items():
        duplicate_targets = [
            target
            for target, count in Counter(
                (mapping.target_domain, mapping.target_field) for mapping in mappings
            ).items()
            if count > 1
        ]
        issues.extend(
            ChargeRule001StagingIssue(
                severity="error",
                issue_type="duplicate-target-mapping",
                table_name=None,
                row_number=None,
                message=(
                    f"duplicate active mapping for schema {table_schema_id} "
                    f"{target_domain}.{target_field}"
                ),
            )
            for target_domain, target_field in sorted(duplicate_targets)
        )
        lookup_by_schema[table_schema_id] = {
            (mapping.target_domain, mapping.target_field): mapping.source_field
            for mapping in mappings
        }
    if issues:
        return {}, tuple(issues)
    return lookup_by_schema, ()


def _table_has_charge_detail_mapping(
    row: HisStagingRow,
    field_mappings: Sequence[HisFieldMapping],
) -> bool:
    if row.table_schema_id is None:
        return False
    return any(
        mapping.status == "active"
        and mapping.table_schema_id == row.table_schema_id
        and mapping.target_domain == "charge_detail"
        for mapping in field_mappings
    )


def _record_from_staging_row(
    row: HisStagingRow,
    *,
    mapping_lookup: dict[TargetField, str],
    source_batch_key: str,
) -> tuple[ChargeDetailRecord | None, tuple[ChargeRule001StagingIssue, ...]]:
    issues: list[ChargeRule001StagingIssue] = []
    charge_detail_id = _required_text(row, mapping_lookup, ("charge_detail", "charge_id"), issues)
    quantity = _required_decimal(row, mapping_lookup, ("charge_detail", "quantity"), issues)
    unit_price = _required_decimal(row, mapping_lookup, ("charge_detail", "unit_price"), issues)
    if charge_detail_id is None or quantity is None or unit_price is None:
        return None, tuple(issues)

    charge_item_name = _optional_text(
        row,
        mapping_lookup,
        ("charge_detail", "item_name"),
        ("item_catalog", "item_name"),
    )
    if charge_item_name is None:
        charge_item_name = _optional_text(
            row,
            mapping_lookup,
            ("charge_detail", "hospital_item_code"),
        )
        issues.append(
            _issue(
                "warning",
                "missing-readable-item-name",
                row,
                "missing charge_detail.item_name; using item code as display name",
            )
        )

    patient_anonymized_id = _optional_text(
        row,
        mapping_lookup,
        ("visit", "patient_anonymous_id"),
        ("charge_detail", "patient_anonymous_id"),
    )
    if patient_anonymized_id is None:
        patient_anonymized_id = f"UNKNOWN-PATIENT-{charge_detail_id}"
        issues.append(
            _issue(
                "warning",
                "missing-patient-anonymous-id",
                row,
                "missing visit.patient_anonymous_id; using deterministic placeholder",
            )
        )

    department_code = _optional_text(
        row,
        mapping_lookup,
        ("visit", "department_code"),
        ("charge_detail", "department_code"),
    )
    if department_code is None:
        department_code = "UNKNOWN-DEPARTMENT"
        issues.append(
            _issue(
                "warning",
                "missing-department-code",
                row,
                "missing visit.department_code; using UNKNOWN-DEPARTMENT",
            )
        )

    service_date, date_issue = _optional_date(row, mapping_lookup, ("charge_detail", "charged_at"))
    if date_issue is not None:
        issues.append(date_issue)
        return None, tuple(issues)

    return (
        ChargeDetailRecord(
            charge_detail_id=charge_detail_id,
            visit_id=_optional_text(
                row,
                mapping_lookup,
                ("charge_detail", "visit_id"),
                ("visit", "visit_id"),
            ),
            charge_item_code=_optional_text(
                row,
                mapping_lookup,
                ("charge_detail", "hospital_item_code"),
            ),
            charge_item_name=charge_item_name or charge_detail_id,
            service_date=service_date,
            quantity=quantity,
            unit_price=unit_price,
            patient_anonymized_id=patient_anonymized_id,
            department_code=department_code,
            source_batch_key=source_batch_key,
            order_id=_optional_text(row, mapping_lookup, ("order_item", "order_id")),
            execution_record_id=_optional_text(
                row,
                mapping_lookup,
                ("charge_detail", "execution_record_id"),
                ("order_item", "order_id"),
            ),
        ),
        tuple(issues),
    )


def _required_text(
    row: HisStagingRow,
    mapping_lookup: dict[TargetField, str],
    target: TargetField,
    issues: list[ChargeRule001StagingIssue],
) -> str | None:
    value = _optional_text(row, mapping_lookup, target)
    if value is None:
        issues.append(
            _issue("error", "missing-required-field", row, f"missing {target[0]}.{target[1]}")
        )
    return value


def _required_decimal(
    row: HisStagingRow,
    mapping_lookup: dict[TargetField, str],
    target: TargetField,
    issues: list[ChargeRule001StagingIssue],
) -> Decimal | None:
    raw_value = _optional_text(row, mapping_lookup, target)
    if raw_value is None:
        issues.append(
            _issue("error", "missing-required-field", row, f"missing {target[0]}.{target[1]}")
        )
        return None
    try:
        return Decimal(raw_value)
    except InvalidOperation:
        issues.append(
            _issue(
                "error",
                "invalid-decimal",
                row,
                f"invalid decimal for {target[0]}.{target[1]}: {raw_value}",
            )
        )
        return None


def _optional_text(
    row: HisStagingRow,
    mapping_lookup: dict[TargetField, str],
    *targets: TargetField,
) -> str | None:
    for target in targets:
        source_field = mapping_lookup.get(target)
        if source_field is None:
            continue
        value = row.row_data.get(source_field)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _optional_date(
    row: HisStagingRow,
    mapping_lookup: dict[TargetField, str],
    target: TargetField,
) -> tuple[date | None, ChargeRule001StagingIssue | None]:
    raw_value = _optional_text(row, mapping_lookup, target)
    if raw_value is None:
        return None, None
    try:
        return date.fromisoformat(raw_value[:10]), None
    except ValueError:
        try:
            return datetime.fromisoformat(raw_value).date(), None
        except ValueError:
            return None, _issue(
                "error",
                "invalid-date",
                row,
                f"invalid date for {target[0]}.{target[1]}: {raw_value}",
            )


def _issue(
    severity: Literal["warning", "error"],
    issue_type: str,
    row: HisStagingRow,
    message: str,
) -> ChargeRule001StagingIssue:
    return ChargeRule001StagingIssue(
        severity=severity,
        issue_type=issue_type,
        table_name=row.table_name,
        row_number=row.row_number,
        message=message,
    )
