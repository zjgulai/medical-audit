from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from hashlib import sha1
from typing import Any
from uuid import UUID

from medical_audit_kb.domain.schemas import AuditFindingCreate

RULE_KEY = "CHARGE-RULE-001"
DEFAULT_RULE_VERSION_KEY = "CHARGE-RULE-001@v1"
FINDING_TYPE = "duplicate-charge"
KNOWLEDGE_EVIDENCE_SNIPPET = (
    "同一就诊、同一收费项目、同一服务日期下出现多条收费时，必须能够由数量、"
    "频次或执行记录解释；无法解释的记录进入人工复核。"
)


@dataclass(frozen=True, slots=True)
class ChargeDetailRecord:
    charge_detail_id: str
    visit_id: str | None
    charge_item_code: str | None
    charge_item_name: str
    service_date: date | None
    quantity: Decimal
    unit_price: Decimal
    patient_anonymized_id: str
    department_code: str
    source_batch_key: str
    order_id: str | None = None
    execution_record_id: str | None = None

    @property
    def amount(self) -> Decimal:
        return self.quantity * self.unit_price


@dataclass(frozen=True, slots=True)
class ChargeRule001Finding:
    finding_key: str
    audit_task_key: str
    audit_run_key: str
    snapshot_key: str
    rule_key: str
    rule_version_key: str
    status: str
    finding_type: str
    severity: str
    source_record_locator: dict[str, Any]
    calculation_trace: dict[str, Any]
    review_status: str
    source_package_version_key: str | None
    knowledge_index_version_key: str | None
    knowledge_evidence_snippet: str


@dataclass(frozen=True, slots=True)
class ChargeRule001NeedsEvidence:
    charge_detail_id: str
    missing_fields: tuple[str, ...]
    source_record_locator: dict[str, Any]
    reason: str


@dataclass(frozen=True, slots=True)
class ChargeRule001Result:
    rule_key: str
    rule_version_key: str
    audit_task_key: str
    audit_run_key: str
    snapshot_key: str
    findings: tuple[ChargeRule001Finding, ...]
    needs_evidence: tuple[ChargeRule001NeedsEvidence, ...]
    summary: dict[str, int]


def build_charge_rule_001_fixture() -> tuple[ChargeDetailRecord, ...]:
    return (
        _record("CD0001", "V001", "P001", "静脉输液", "2025-01-03", "1", "40", None),
        _record("CD0002", "V001", "P001", "静脉输液", "2025-01-03", "1", "40", None),
        _record("CD0003", "V002", "P002", "床位费", "2025-01-04", "1", "60", "EX200"),
        _record("CD0004", "V002", "P002", "床位费", "2025-01-04", "1", "60", "EX200"),
        _record("CD0005", "V003", "P003", "护理费", "2025-01-05", "1", "25", "EX300"),
        _record("CD0006", "V003", "P003", "护理费", "2025-01-05", "1", "25", None),
        _record("CD0007", "V003", "P003", "护理费", "2025-01-05", "1", "25", None),
        _record("CD0101", "V010", "P010", "换药费", "2025-01-05", "1", "20", "EX101"),
        _record("CD0102", "V010", "P010", "换药费", "2025-01-05", "1", "20", "EX102"),
        _record("CD0111", "V011", "P011", "雾化吸入", "2025-01-05", "1", "15", "EX111"),
        _record("CD0112", "V011", "P011", "雾化吸入", "2025-01-05", "1", "15", "EX112"),
        _record("CD0113", "V011", "P011", "雾化吸入", "2025-01-05", "1", "15", "EX113"),
        _record("CD0121", "V012", "P012", "血糖测定", "2025-01-05", "1", "8", "EX121"),
        _record("CD0122", "V012", "P012", "血糖测定", "2025-01-05", "1", "8", "EX122"),
        _record("CD0201", None, "P020", "诊查费", "2025-01-06", "1", "10", "EX201"),
        _record("CD0202", "V020", "P021", "治疗费", None, "1", "30", "EX202"),
    )


def evaluate_charge_rule_001(
    records: Sequence[ChargeDetailRecord],
    *,
    audit_task_key: str,
    audit_run_key: str,
    snapshot_key: str,
    rule_version_key: str = DEFAULT_RULE_VERSION_KEY,
    knowledge_index_version_key: str | None = None,
    source_package_version_key: str | None = None,
) -> ChargeRule001Result:
    valid_records: list[ChargeDetailRecord] = []
    needs_evidence: list[ChargeRule001NeedsEvidence] = []
    for record in records:
        missing_fields = _missing_group_fields(record)
        if missing_fields:
            needs_evidence.append(_needs_evidence(record, missing_fields))
            continue
        valid_records.append(record)

    grouped_records = _group_records(valid_records)
    findings: list[ChargeRule001Finding] = []
    explained_group_count = 0
    for group_key in sorted(grouped_records):
        group = tuple(sorted(grouped_records[group_key], key=lambda item: item.charge_detail_id))
        if len(group) < 2:
            continue
        if _is_explained_by_execution_records(group):
            explained_group_count += 1
            continue
        findings.append(
            _finding(
                group,
                audit_task_key=audit_task_key,
                audit_run_key=audit_run_key,
                snapshot_key=snapshot_key,
                rule_version_key=rule_version_key,
                knowledge_index_version_key=knowledge_index_version_key,
                source_package_version_key=source_package_version_key,
            )
        )

    return ChargeRule001Result(
        rule_key=RULE_KEY,
        rule_version_key=rule_version_key,
        audit_task_key=audit_task_key,
        audit_run_key=audit_run_key,
        snapshot_key=snapshot_key,
        findings=tuple(findings),
        needs_evidence=tuple(needs_evidence),
        summary={
            "input_record_count": len(records),
            "valid_record_count": len(valid_records),
            "finding_count": len(findings),
            "explained_group_count": explained_group_count,
            "needs_evidence_count": len(needs_evidence),
        },
    )


def build_audit_finding_payloads(
    result: ChargeRule001Result,
    *,
    audit_run_id: UUID,
    audit_task_id: UUID,
    rule_version_id: UUID,
    snapshot_id: UUID,
) -> tuple[AuditFindingCreate, ...]:
    return tuple(
        AuditFindingCreate(
            finding_key=finding.finding_key,
            audit_run_id=audit_run_id,
            audit_task_id=audit_task_id,
            rule_version_id=rule_version_id,
            snapshot_id=snapshot_id,
            status=finding.status,
            finding_type=finding.finding_type,
            severity=finding.severity,
            source_record_locator=finding.source_record_locator,
            calculation_trace=finding.calculation_trace,
            review_status=finding.review_status,
            metadata={
                "audit_task_key": finding.audit_task_key,
                "audit_run_key": finding.audit_run_key,
                "snapshot_key": finding.snapshot_key,
                "rule_key": finding.rule_key,
                "rule_version_key": finding.rule_version_key,
            },
        )
        for finding in result.findings
    )


def _record(
    charge_detail_id: str,
    visit_id: str | None,
    charge_item_code: str | None,
    charge_item_name: str,
    service_date_value: str | None,
    quantity: str,
    unit_price: str,
    execution_record_id: str | None,
) -> ChargeDetailRecord:
    return ChargeDetailRecord(
        charge_detail_id=charge_detail_id,
        visit_id=visit_id,
        charge_item_code=charge_item_code,
        charge_item_name=charge_item_name,
        service_date=date.fromisoformat(service_date_value) if service_date_value else None,
        quantity=Decimal(quantity),
        unit_price=Decimal(unit_price),
        patient_anonymized_id=f"PAT-{charge_detail_id[2:]}",
        department_code="D001",
        source_batch_key="his-fixture-20260604",
        execution_record_id=execution_record_id,
    )


def _missing_group_fields(record: ChargeDetailRecord) -> tuple[str, ...]:
    missing_fields: list[str] = []
    if not record.visit_id:
        missing_fields.append("visit_id")
    if not record.charge_item_code:
        missing_fields.append("charge_item_code")
    if record.service_date is None:
        missing_fields.append("service_date")
    return tuple(missing_fields)


def _needs_evidence(
    record: ChargeDetailRecord,
    missing_fields: tuple[str, ...],
) -> ChargeRule001NeedsEvidence:
    return ChargeRule001NeedsEvidence(
        charge_detail_id=record.charge_detail_id,
        missing_fields=missing_fields,
        source_record_locator={
            "source_table": "charge_detail",
            "primary_key": record.charge_detail_id,
            "source_batch_key": record.source_batch_key,
        },
        reason="缺少重复收费分组必需字段，不能静默判定为合规或违规。",
    )


def _group_records(
    records: Iterable[ChargeDetailRecord],
) -> dict[tuple[str, str, str], list[ChargeDetailRecord]]:
    grouped_records: dict[tuple[str, str, str], list[ChargeDetailRecord]] = defaultdict(list)
    for record in records:
        if (
            record.visit_id is None
            or record.charge_item_code is None
            or record.service_date is None
        ):
            continue
        grouped_records[
            (record.visit_id, record.charge_item_code, record.service_date.isoformat())
        ].append(record)
    return grouped_records


def _is_explained_by_execution_records(records: Sequence[ChargeDetailRecord]) -> bool:
    execution_record_ids = [record.execution_record_id for record in records]
    if any(execution_record_id is None for execution_record_id in execution_record_ids):
        return False
    return len(set(execution_record_ids)) == len(execution_record_ids)


def _finding(
    records: Sequence[ChargeDetailRecord],
    *,
    audit_task_key: str,
    audit_run_key: str,
    snapshot_key: str,
    rule_version_key: str,
    knowledge_index_version_key: str | None,
    source_package_version_key: str | None,
) -> ChargeRule001Finding:
    first_record = records[0]
    record_ids = [record.charge_detail_id for record in records]
    finding_key = f"finding-{_stable_digest(audit_run_key, record_ids)}"
    total_quantity = sum((record.quantity for record in records), Decimal("0"))
    total_amount = sum((record.amount for record in records), Decimal("0"))
    execution_record_ids = [record.execution_record_id for record in records]

    return ChargeRule001Finding(
        finding_key=finding_key,
        audit_task_key=audit_task_key,
        audit_run_key=audit_run_key,
        snapshot_key=snapshot_key,
        rule_key=RULE_KEY,
        rule_version_key=rule_version_key,
        status="open",
        finding_type=FINDING_TYPE,
        severity="medium",
        source_record_locator={
            "source_table": "charge_detail",
            "primary_keys": record_ids,
            "source_batch_key": first_record.source_batch_key,
            "record_count": len(records),
        },
        calculation_trace={
            "rule_key": RULE_KEY,
            "rule_version_key": rule_version_key,
            "group_key": {
                "visit_id": first_record.visit_id,
                "charge_item_code": first_record.charge_item_code,
                "service_date": first_record.service_date.isoformat()
                if first_record.service_date
                else None,
            },
            "matched_charge_detail_ids": record_ids,
            "duplicate_count": len(records),
            "total_quantity": str(total_quantity),
            "total_amount": str(total_amount),
            "execution_record_ids": execution_record_ids,
            "explanation_check": {
                "all_records_have_execution_record_id": all(
                    execution_record_id is not None for execution_record_id in execution_record_ids
                ),
                "distinct_execution_record_count": len(
                    {item for item in execution_record_ids if item is not None}
                ),
                "explained_by_distinct_execution_records": False,
            },
        },
        review_status="pending-review",
        source_package_version_key=source_package_version_key,
        knowledge_index_version_key=knowledge_index_version_key,
        knowledge_evidence_snippet=KNOWLEDGE_EVIDENCE_SNIPPET,
    )


def _stable_digest(audit_run_key: str, record_ids: Sequence[str]) -> str:
    digest_source = "|".join([audit_run_key, *record_ids])
    return sha1(digest_source.encode("utf-8")).hexdigest()[:16]
