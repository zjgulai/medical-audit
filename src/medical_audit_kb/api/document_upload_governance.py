from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Literal, Protocol

from medical_audit_kb.core.config import DocumentUploadGovernanceSettings

DocumentUploadGovernanceCheckType = Literal[
    "virus-scan",
    "dlp-review",
    "manual-index-approval",
]
DocumentUploadGovernanceCheckStatus = Literal["passed", "blocked"]
DocumentUploadLocalTestMode = Literal["normal", "false-positive", "false-negative"]
DocumentUploadIndexBlocker = Literal[
    "virus-scan-required",
    "dlp-review-required",
    "manual-index-approval-required",
]

INDEX_READINESS_BLOCKERS: tuple[DocumentUploadIndexBlocker, ...] = (
    "virus-scan-required",
    "dlp-review-required",
    "manual-index-approval-required",
)
INDEX_READINESS_NEXT_ACTION = "complete-upload-governance"
_VALID_CHECK_TYPES = frozenset({"virus-scan", "dlp-review", "manual-index-approval"})
_VALID_CHECK_STATUSES = frozenset({"passed", "blocked"})
_VALID_BLOCKERS = frozenset(INDEX_READINESS_BLOCKERS)


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

    def to_payload(self) -> dict[str, object]:
        return {
            "check_type": self.check_type,
            "provider": self.provider,
            "status": self.status,
            "blocker": self.blocker,
            "detail": self.detail,
        }


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
    virus_scanner: DocumentUploadVirusScanner = field(
        default_factory=UnconfiguredVirusScanner
    )
    dlp_reviewer: DocumentUploadDlpReviewer = field(default_factory=UnconfiguredDlpReviewer)
    manual_approval_gate: ManualIndexApprovalGate = field(
        default_factory=ManualIndexApprovalGate
    )

    def evaluate(self, context: DocumentUploadGovernanceContext) -> dict[str, object]:
        checks = (
            self.virus_scanner.scan(context),
            self.dlp_reviewer.review(context),
            self.manual_approval_gate.evaluate(context),
        )
        blockers = [
            check.blocker
            for check in checks
            if check.status == "blocked" and check.blocker is not None
        ]
        return _readiness_payload(checks=checks, blockers=blockers)


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
    return _readiness_payload(checks=checks, blockers=list(INDEX_READINESS_BLOCKERS))


def index_readiness_from_metadata(metadata: dict[str, object]) -> dict[str, object]:
    value = metadata.get("index_readiness")
    if not isinstance(value, dict):
        return default_index_readiness()

    status = value.get("status")
    blockers = value.get("blockers")
    next_action = value.get("next_action")
    checks = value.get("checks")
    if (
        status == "blocked"
        and isinstance(blockers, list)
        and all(isinstance(blocker, str) and blocker in _VALID_BLOCKERS for blocker in blockers)
        and next_action == INDEX_READINESS_NEXT_ACTION
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


def _readiness_payload(
    *,
    checks: tuple[GovernanceCheckResult, ...],
    blockers: list[DocumentUploadIndexBlocker],
) -> dict[str, object]:
    return {
        "status": "blocked",
        "blockers": blockers,
        "next_action": INDEX_READINESS_NEXT_ACTION,
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
    )


def _virus_scanner_from_settings(
    settings: DocumentUploadGovernanceSettings,
) -> DocumentUploadVirusScanner:
    if settings.virus_scan_provider == "unconfigured":
        return UnconfiguredVirusScanner()
    if settings.virus_scan_provider == "local-test":
        return LocalTestVirusScanner(mode=settings.virus_scan_test_mode)
    raise ValueError(f"unsupported document upload virus scanner: {settings.virus_scan_provider}")


def _dlp_reviewer_from_settings(
    settings: DocumentUploadGovernanceSettings,
) -> DocumentUploadDlpReviewer:
    if settings.dlp_review_provider == "unconfigured":
        return UnconfiguredDlpReviewer()
    if settings.dlp_review_provider == "local-test":
        return LocalTestDlpReviewer(mode=settings.dlp_review_test_mode)
    raise ValueError(f"unsupported document upload DLP reviewer: {settings.dlp_review_provider}")


def _context_contains_any(
    context: DocumentUploadGovernanceContext,
    *,
    markers: tuple[str, ...],
) -> bool:
    text = context.content[:4096].decode("utf-8", errors="ignore")
    haystack = f"{context.file_name}\n{context.extension}\n{text}".lower()
    return any(marker.lower() in haystack for marker in markers)
