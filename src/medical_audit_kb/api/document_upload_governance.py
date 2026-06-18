from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Literal, Protocol, cast

from medical_audit_kb.core.config import DocumentUploadGovernanceSettings

DocumentUploadGovernanceCheckType = Literal[
    "virus-scan",
    "dlp-review",
    "manual-index-approval",
]
DocumentUploadGovernanceCheckStatus = Literal["passed", "blocked"]
DocumentUploadLocalTestMode = Literal["normal", "false-positive", "false-negative"]
DocumentUploadDlpRiskLevel = Literal["low", "medium", "high"]
DocumentUploadIndexReadinessStatus = Literal["blocked", "ready", "rejected"]
DocumentUploadIndexBlocker = Literal[
    "virus-scan-required",
    "dlp-review-required",
    "manual-index-approval-required",
    "manual-index-approval-rejected",
]
DocumentUploadIndexNextAction = Literal[
    "complete-upload-governance",
    "ingest-personal-upload",
    "review-manual-index-rejection",
]
DocumentUploadManualIndexDecision = Literal["approved", "rejected"]

INDEX_READINESS_BLOCKERS: tuple[DocumentUploadIndexBlocker, ...] = (
    "virus-scan-required",
    "dlp-review-required",
    "manual-index-approval-required",
)
INDEX_READINESS_REJECTED_BLOCKER: DocumentUploadIndexBlocker = "manual-index-approval-rejected"
INDEX_READINESS_NEXT_ACTION: DocumentUploadIndexNextAction = "complete-upload-governance"
INDEX_READINESS_READY_NEXT_ACTION: DocumentUploadIndexNextAction = "ingest-personal-upload"
INDEX_READINESS_REJECTED_NEXT_ACTION: DocumentUploadIndexNextAction = (
    "review-manual-index-rejection"
)
_VALID_CHECK_TYPES = frozenset({"virus-scan", "dlp-review", "manual-index-approval"})
_VALID_CHECK_STATUSES = frozenset({"passed", "blocked"})
_VALID_READINESS_STATUSES = frozenset({"blocked", "ready", "rejected"})
_VALID_NEXT_ACTIONS = frozenset(
    {
        INDEX_READINESS_NEXT_ACTION,
        INDEX_READINESS_READY_NEXT_ACTION,
        INDEX_READINESS_REJECTED_NEXT_ACTION,
    }
)
_VALID_BLOCKERS = frozenset((*INDEX_READINESS_BLOCKERS, INDEX_READINESS_REJECTED_BLOCKER))


@dataclass(frozen=True, slots=True)
class DocumentUploadGovernanceContext:
    file_name: str
    extension: str
    size_bytes: int
    sha256: str
    content: bytes

    @classmethod
    def from_upload(
        cls,
        *,
        file_name: str,
        extension: str,
        content: bytes,
    ) -> DocumentUploadGovernanceContext:
        return cls(
            file_name=file_name,
            extension=extension,
            size_bytes=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
            content=content,
        )


@dataclass(frozen=True, slots=True)
class GovernanceCheckResult:
    check_type: DocumentUploadGovernanceCheckType
    provider: str
    status: DocumentUploadGovernanceCheckStatus
    blocker: DocumentUploadIndexBlocker | None
    detail: str
    job_key: str | None = None
    external_job_id: str | None = None
    risk_level: str | None = None
    result_code: str | None = None
    finished_at: str | None = None
    findings: tuple[dict[str, object], ...] | None = None

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "check_type": self.check_type,
            "provider": self.provider,
            "status": self.status,
            "blocker": self.blocker,
            "detail": self.detail,
        }
        if self.job_key is not None:
            payload["job_key"] = self.job_key
        if self.external_job_id is not None:
            payload["external_job_id"] = self.external_job_id
        if self.risk_level is not None:
            payload["risk_level"] = self.risk_level
        if self.result_code is not None:
            payload["result_code"] = self.result_code
        if self.finished_at is not None:
            payload["finished_at"] = self.finished_at
        if self.findings is not None:
            payload["findings"] = [dict(finding) for finding in self.findings]
        return payload


class DocumentUploadVirusScanner(Protocol):
    @property
    def provider(self) -> str:
        pass

    def scan(self, context: DocumentUploadGovernanceContext) -> GovernanceCheckResult:
        pass


class DocumentUploadDlpReviewer(Protocol):
    @property
    def provider(self) -> str:
        pass

    def review(self, context: DocumentUploadGovernanceContext) -> GovernanceCheckResult:
        pass


@dataclass(frozen=True, slots=True)
class UnconfiguredVirusScanner:
    provider: str = "unconfigured"

    def scan(self, context: DocumentUploadGovernanceContext) -> GovernanceCheckResult:
        return GovernanceCheckResult(
            check_type="virus-scan",
            provider=self.provider,
            status="blocked",
            blocker="virus-scan-required",
            detail=f"virus scan adapter is not configured for {context.extension} upload",
        )


@dataclass(frozen=True, slots=True)
class UnconfiguredDlpReviewer:
    provider: str = "unconfigured"

    def review(self, context: DocumentUploadGovernanceContext) -> GovernanceCheckResult:
        return GovernanceCheckResult(
            check_type="dlp-review",
            provider=self.provider,
            status="blocked",
            blocker="dlp-review-required",
            detail=f"DLP review adapter is not configured for {context.extension} upload",
        )


@dataclass(frozen=True, slots=True)
class LocalTestVirusScanner:
    mode: DocumentUploadLocalTestMode = "normal"
    provider: str = "local-test"

    def scan(self, context: DocumentUploadGovernanceContext) -> GovernanceCheckResult:
        if self.mode == "false-positive":
            return GovernanceCheckResult(
                check_type="virus-scan",
                provider=self.provider,
                status="blocked",
                blocker="virus-scan-required",
                detail="local false-positive virus test blocked upload",
            )
        if self.mode == "false-negative":
            return GovernanceCheckResult(
                check_type="virus-scan",
                provider=self.provider,
                status="passed",
                blocker=None,
                detail="local false-negative virus test passed upload",
            )
        if _context_contains_any(
            context,
            markers=("eicar", "test-malware", "virus-positive"),
        ):
            return GovernanceCheckResult(
                check_type="virus-scan",
                provider=self.provider,
                status="blocked",
                blocker="virus-scan-required",
                detail="local test virus marker detected",
            )
        return GovernanceCheckResult(
            check_type="virus-scan",
            provider=self.provider,
            status="passed",
            blocker=None,
            detail="local test virus scanner found no marker",
        )


@dataclass(frozen=True, slots=True)
class LocalTestDlpReviewer:
    mode: DocumentUploadLocalTestMode = "normal"
    provider: str = "local-test"

    def review(self, context: DocumentUploadGovernanceContext) -> GovernanceCheckResult:
        if self.mode == "false-positive":
            return GovernanceCheckResult(
                check_type="dlp-review",
                provider=self.provider,
                status="blocked",
                blocker="dlp-review-required",
                detail="local false-positive DLP test blocked upload",
            )
        if self.mode == "false-negative":
            return GovernanceCheckResult(
                check_type="dlp-review",
                provider=self.provider,
                status="passed",
                blocker=None,
                detail="local false-negative DLP test passed upload",
            )
        if _context_contains_any(
            context,
            markers=("patient_id", "id_card", "身份证", "手机号", "sensitive-patient"),
        ):
            return GovernanceCheckResult(
                check_type="dlp-review",
                provider=self.provider,
                status="blocked",
                blocker="dlp-review-required",
                detail="local test DLP marker detected",
            )
        return GovernanceCheckResult(
            check_type="dlp-review",
            provider=self.provider,
            status="passed",
            blocker=None,
            detail="local test DLP reviewer found no marker",
        )


@dataclass(frozen=True, slots=True)
class RulesetDlpRule:
    rule_id: str
    category: str
    risk_level: DocumentUploadDlpRiskLevel
    pattern: re.Pattern[str]


@dataclass(frozen=True, slots=True)
class RulesetDlpReviewer:
    provider: str = "ruleset-v1"

    def review(self, context: DocumentUploadGovernanceContext) -> GovernanceCheckResult:
        findings = _ruleset_dlp_findings(context)
        if not findings:
            return GovernanceCheckResult(
                check_type="dlp-review",
                provider=self.provider,
                status="passed",
                blocker=None,
                detail="ruleset-v1 DLP found no configured sensitive markers",
                risk_level="low",
                result_code="no-sensitive-marker",
            )
        risk_level = _max_risk_level(findings)
        return GovernanceCheckResult(
            check_type="dlp-review",
            provider=self.provider,
            status="blocked",
            blocker="dlp-review-required",
            detail=f"ruleset-v1 DLP detected {risk_level}-risk sensitive markers",
            risk_level=risk_level,
            result_code="sensitive-marker-detected",
            findings=tuple(findings),
        )


@dataclass(frozen=True, slots=True)
class ExternalPendingVirusScanner:
    provider: str

    def scan(self, context: DocumentUploadGovernanceContext) -> GovernanceCheckResult:
        return GovernanceCheckResult(
            check_type="virus-scan",
            provider=self.provider,
            status="blocked",
            blocker="virus-scan-required",
            detail=(
                f"{self.provider} scan result is required before indexing "
                f"{context.extension} upload"
            ),
            result_code="pending-external-result",
        )


@dataclass(frozen=True, slots=True)
class ExternalPendingDlpReviewer:
    provider: str

    def review(self, context: DocumentUploadGovernanceContext) -> GovernanceCheckResult:
        return GovernanceCheckResult(
            check_type="dlp-review",
            provider=self.provider,
            status="blocked",
            blocker="dlp-review-required",
            detail=(
                f"{self.provider} review result is required before indexing "
                f"{context.extension} upload"
            ),
            risk_level="unknown",
            result_code="pending-external-result",
        )


@dataclass(frozen=True, slots=True)
class ManualIndexApprovalGate:
    provider: str = "manual"

    def evaluate(self, context: DocumentUploadGovernanceContext) -> GovernanceCheckResult:
        return GovernanceCheckResult(
            check_type="manual-index-approval",
            provider=self.provider,
            status="blocked",
            blocker="manual-index-approval-required",
            detail=f"manual index approval is required before ingesting {context.file_name}",
        )


@dataclass(frozen=True, slots=True)
class DocumentUploadGovernancePolicy:
    virus_scanner: DocumentUploadVirusScanner = field(default_factory=UnconfiguredVirusScanner)
    dlp_reviewer: DocumentUploadDlpReviewer = field(default_factory=UnconfiguredDlpReviewer)
    manual_approval_gate: ManualIndexApprovalGate = field(default_factory=ManualIndexApprovalGate)

    def evaluate(self, context: DocumentUploadGovernanceContext) -> dict[str, object]:
        checks = (
            self.virus_scanner.scan(context),
            self.dlp_reviewer.review(context),
            self.manual_approval_gate.evaluate(context),
        )
        return _readiness_payload(checks=checks)


def document_upload_governance_policy_from_settings(
    settings: DocumentUploadGovernanceSettings,
) -> DocumentUploadGovernancePolicy:
    return DocumentUploadGovernancePolicy(
        virus_scanner=_virus_scanner_from_settings(settings),
        dlp_reviewer=_dlp_reviewer_from_settings(settings),
    )


def default_index_readiness() -> dict[str, object]:
    checks = (
        GovernanceCheckResult(
            check_type="virus-scan",
            provider="unconfigured",
            status="blocked",
            blocker="virus-scan-required",
            detail="virus scan adapter is not configured",
        ),
        GovernanceCheckResult(
            check_type="dlp-review",
            provider="unconfigured",
            status="blocked",
            blocker="dlp-review-required",
            detail="DLP review adapter is not configured",
        ),
        GovernanceCheckResult(
            check_type="manual-index-approval",
            provider="manual",
            status="blocked",
            blocker="manual-index-approval-required",
            detail="manual index approval is required before ingesting personal uploads",
        ),
    )
    return _readiness_payload(checks=checks)


def index_readiness_from_metadata(metadata: dict[str, object]) -> dict[str, object]:
    value = metadata.get("index_readiness")
    if not isinstance(value, dict):
        return default_index_readiness()

    status = value.get("status")
    blockers = value.get("blockers")
    next_action = value.get("next_action")
    checks = value.get("checks")
    if (
        isinstance(status, str)
        and status in _VALID_READINESS_STATUSES
        and isinstance(blockers, list)
        and all(isinstance(blocker, str) and blocker in _VALID_BLOCKERS for blocker in blockers)
        and isinstance(next_action, str)
        and next_action in _VALID_NEXT_ACTIONS
        and isinstance(checks, list)
        and all(_valid_check_payload(check) for check in checks)
    ):
        return {
            "status": status,
            "blockers": list(blockers),
            "next_action": next_action,
            "checks": checks,
        }
    return default_index_readiness()


def apply_manual_index_decision(
    index_readiness: dict[str, object],
    *,
    decision: DocumentUploadManualIndexDecision,
    actor: str,
    note: str,
) -> dict[str, object]:
    current = index_readiness_from_metadata({"index_readiness": index_readiness})
    current_checks = current.get("checks")
    checks: tuple[GovernanceCheckResult, ...] = ()
    if isinstance(current_checks, list):
        checks = tuple(
            _check_result_from_payload(cast(dict[str, object], check))
            for check in current_checks
            if isinstance(check, dict)
        )
    updated_manual_check = _manual_index_decision_check(
        decision=decision,
        actor=actor,
        note=note,
    )
    updated_checks = tuple(
        updated_manual_check if check.check_type == "manual-index-approval" else check
        for check in checks
    )
    if not any(check.check_type == "manual-index-approval" for check in updated_checks):
        updated_checks = (*updated_checks, updated_manual_check)
    return _readiness_payload(checks=updated_checks)


def apply_governance_check_result(
    index_readiness: dict[str, object],
    *,
    check_type: Literal["virus-scan", "dlp-review"],
    provider: str,
    status: DocumentUploadGovernanceCheckStatus,
    detail: str,
    external_job_id: str | None = None,
    risk_level: str | None = None,
    result_code: str | None = None,
    finished_at: str | None = None,
) -> dict[str, object]:
    current = index_readiness_from_metadata({"index_readiness": index_readiness})
    current_checks = current.get("checks")
    checks: tuple[GovernanceCheckResult, ...] = ()
    if isinstance(current_checks, list):
        checks = tuple(
            _check_result_from_payload(cast(dict[str, object], check))
            for check in current_checks
            if isinstance(check, dict)
        )
    updated_check = GovernanceCheckResult(
        check_type=check_type,
        provider=provider,
        status=status,
        blocker=_governance_result_blocker(check_type, status),
        detail=detail,
        external_job_id=external_job_id,
        risk_level=risk_level,
        result_code=result_code,
        finished_at=finished_at,
    )
    updated_checks = tuple(
        updated_check if check.check_type == check_type else check for check in checks
    )
    if not any(check.check_type == check_type for check in updated_checks):
        updated_checks = _insert_governance_result_check(updated_checks, updated_check)
    return _readiness_payload(checks=updated_checks)


def _readiness_payload(
    *,
    checks: tuple[GovernanceCheckResult, ...],
) -> dict[str, object]:
    blockers = [
        check.blocker for check in checks if check.status == "blocked" and check.blocker is not None
    ]
    status, next_action = _readiness_status_and_next_action(blockers)
    return {
        "status": status,
        "blockers": blockers,
        "next_action": next_action,
        "checks": [check.to_payload() for check in checks],
    }


def _valid_check_payload(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    check_type = value.get("check_type")
    provider = value.get("provider")
    status = value.get("status")
    blocker = value.get("blocker")
    detail = value.get("detail")
    optional_text_fields = (
        "job_key",
        "external_job_id",
        "risk_level",
        "result_code",
        "finished_at",
    )
    return (
        isinstance(check_type, str)
        and check_type in _VALID_CHECK_TYPES
        and isinstance(provider, str)
        and bool(provider)
        and isinstance(status, str)
        and status in _VALID_CHECK_STATUSES
        and (blocker is None or (isinstance(blocker, str) and blocker in _VALID_BLOCKERS))
        and isinstance(detail, str)
        and bool(detail)
        and all(
            value.get(field) is None
            or (isinstance(value.get(field), str) and bool(value.get(field)))
            for field in optional_text_fields
        )
        and _valid_findings_payload(value.get("findings"))
    )


def _check_result_from_payload(value: dict[str, object]) -> GovernanceCheckResult:
    if not _valid_check_payload(value):
        raise ValueError("invalid document upload governance check payload")
    return GovernanceCheckResult(
        check_type=cast(DocumentUploadGovernanceCheckType, value["check_type"]),
        provider=str(value["provider"]),
        status=cast(DocumentUploadGovernanceCheckStatus, value["status"]),
        blocker=cast(DocumentUploadIndexBlocker | None, value["blocker"]),
        detail=str(value["detail"]),
        job_key=_optional_text(value.get("job_key")),
        external_job_id=_optional_text(value.get("external_job_id")),
        risk_level=_optional_text(value.get("risk_level")),
        result_code=_optional_text(value.get("result_code")),
        finished_at=_optional_text(value.get("finished_at")),
        findings=_findings_from_payload(value.get("findings")),
    )


def _manual_index_decision_check(
    *,
    decision: DocumentUploadManualIndexDecision,
    actor: str,
    note: str,
) -> GovernanceCheckResult:
    if decision == "approved":
        return GovernanceCheckResult(
            check_type="manual-index-approval",
            provider="manual",
            status="passed",
            blocker=None,
            detail=f"manual index approval approved by {actor}: {note}",
        )
    return GovernanceCheckResult(
        check_type="manual-index-approval",
        provider="manual",
        status="blocked",
        blocker=INDEX_READINESS_REJECTED_BLOCKER,
        detail=f"manual index approval rejected by {actor}: {note}",
    )


def _governance_result_blocker(
    check_type: Literal["virus-scan", "dlp-review"],
    status: DocumentUploadGovernanceCheckStatus,
) -> DocumentUploadIndexBlocker | None:
    if status == "passed":
        return None
    if check_type == "virus-scan":
        return "virus-scan-required"
    return "dlp-review-required"


def _insert_governance_result_check(
    checks: tuple[GovernanceCheckResult, ...],
    updated_check: GovernanceCheckResult,
) -> tuple[GovernanceCheckResult, ...]:
    if updated_check.check_type == "virus-scan":
        return (updated_check, *checks)
    before_manual = tuple(check for check in checks if check.check_type != "manual-index-approval")
    manual_checks = tuple(check for check in checks if check.check_type == "manual-index-approval")
    return (*before_manual, updated_check, *manual_checks)


def _readiness_status_and_next_action(
    blockers: list[DocumentUploadIndexBlocker],
) -> tuple[DocumentUploadIndexReadinessStatus, DocumentUploadIndexNextAction]:
    if INDEX_READINESS_REJECTED_BLOCKER in blockers:
        return "rejected", INDEX_READINESS_REJECTED_NEXT_ACTION
    if blockers:
        return "blocked", INDEX_READINESS_NEXT_ACTION
    return "ready", INDEX_READINESS_READY_NEXT_ACTION


def _virus_scanner_from_settings(
    settings: DocumentUploadGovernanceSettings,
) -> DocumentUploadVirusScanner:
    if settings.virus_scan_provider == "unconfigured":
        return UnconfiguredVirusScanner()
    if settings.virus_scan_provider == "local-test":
        return LocalTestVirusScanner(mode=settings.virus_scan_test_mode)
    return ExternalPendingVirusScanner(provider=settings.virus_scan_provider)


def _dlp_reviewer_from_settings(
    settings: DocumentUploadGovernanceSettings,
) -> DocumentUploadDlpReviewer:
    if settings.dlp_review_provider == "unconfigured":
        return UnconfiguredDlpReviewer()
    if settings.dlp_review_provider == "local-test":
        return LocalTestDlpReviewer(mode=settings.dlp_review_test_mode)
    if settings.dlp_review_provider == "ruleset-v1":
        return RulesetDlpReviewer()
    return ExternalPendingDlpReviewer(provider=settings.dlp_review_provider)


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _context_contains_any(
    context: DocumentUploadGovernanceContext,
    *,
    markers: tuple[str, ...],
) -> bool:
    text = context.content[:4096].decode("utf-8", errors="ignore")
    haystack = f"{context.file_name}\n{context.extension}\n{text}".lower()
    return any(marker.lower() in haystack for marker in markers)


_RULESET_DLP_RULES: tuple[RulesetDlpRule, ...] = (
    RulesetDlpRule(
        rule_id="id-card-number",
        category="identity",
        risk_level="high",
        pattern=re.compile(
            r"(?<!\d)[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])"
            r"(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx](?!\d)"
        ),
    ),
    RulesetDlpRule(
        rule_id="mobile-phone-number",
        category="contact",
        risk_level="high",
        pattern=re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    ),
    RulesetDlpRule(
        rule_id="medical-insurance-id",
        category="medical-insurance",
        risk_level="high",
        pattern=re.compile(r"(?:医保号|医保编号|医保卡号)[:：\s]*[A-Za-z0-9-]{4,32}"),
    ),
    RulesetDlpRule(
        rule_id="inpatient-record-id",
        category="medical-record",
        risk_level="medium",
        pattern=re.compile(r"(?:住院号|病案号)[:：\s]*[A-Za-z0-9-]{3,32}"),
    ),
    RulesetDlpRule(
        rule_id="patient-name",
        category="patient",
        risk_level="medium",
        pattern=re.compile(r"(?:患者姓名|病人姓名|姓名)[:：\s]*[\u4e00-\u9fff]{2,6}"),
    ),
    RulesetDlpRule(
        rule_id="diagnosis-text",
        category="diagnosis",
        risk_level="medium",
        pattern=re.compile(r"(?:诊断|疾病诊断)[:：\s]*[^\n,，;；]{2,40}"),
    ),
    RulesetDlpRule(
        rule_id="address-text",
        category="address",
        risk_level="medium",
        pattern=re.compile(r"(?:住址|地址)[:：\s]*[^\n,，;；]{4,80}"),
    ),
    RulesetDlpRule(
        rule_id="fee-detail-section",
        category="fee-detail",
        risk_level="medium",
        pattern=re.compile(r"(?:费用明细|收费明细|住院费用|门诊费用)"),
    ),
)


def _ruleset_dlp_findings(
    context: DocumentUploadGovernanceContext,
) -> list[dict[str, object]]:
    text = context.content[:65536].decode("utf-8", errors="ignore")
    haystack = f"{context.file_name}\n{context.extension}\n{text}"
    findings: list[dict[str, object]] = []
    for rule in _RULESET_DLP_RULES:
        match_count = len(rule.pattern.findall(haystack))
        if match_count == 0:
            continue
        findings.append(
            {
                "rule_id": rule.rule_id,
                "category": rule.category,
                "risk_level": rule.risk_level,
                "match_count": match_count,
            }
        )
    return findings


def _max_risk_level(findings: tuple[dict[str, object], ...] | list[dict[str, object]]) -> str:
    risk_order = {"low": 0, "medium": 1, "high": 2}
    highest = "low"
    for finding in findings:
        value = finding.get("risk_level")
        if isinstance(value, str) and risk_order.get(value, -1) > risk_order[highest]:
            highest = value
    return highest


def _valid_findings_payload(value: object) -> bool:
    if value is None:
        return True
    if not isinstance(value, list):
        return False
    for finding in value:
        if not isinstance(finding, dict):
            return False
        rule_id = finding.get("rule_id")
        category = finding.get("category")
        risk_level = finding.get("risk_level")
        match_count = finding.get("match_count")
        if not (
            isinstance(rule_id, str)
            and bool(rule_id)
            and isinstance(category, str)
            and bool(category)
            and isinstance(risk_level, str)
            and risk_level in {"low", "medium", "high"}
            and isinstance(match_count, int)
            and match_count > 0
        ):
            return False
    return True


def _findings_from_payload(value: object) -> tuple[dict[str, object], ...] | None:
    if value is None:
        return None
    if not _valid_findings_payload(value):
        raise ValueError("invalid document upload governance findings payload")
    return tuple(dict(cast(dict[str, object], finding)) for finding in cast(list[object], value))
