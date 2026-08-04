#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse
from uuid import uuid4

import httpx
import pymupdf

PRODUCTION_DOMAIN = "audit.lute-tlz-dddd.top"
PRODUCTION_BASE_URL = f"https://{PRODUCTION_DOMAIN}"


class ProductionContractAuditError(RuntimeError):
    pass


def main() -> int:
    args = _parse_args()
    try:
        if not args.execute or args.confirm_production != PRODUCTION_DOMAIN:
            raise ProductionContractAuditError(
                f"live OCR E2E requires --execute --confirm-production {PRODUCTION_DOMAIN}"
            )
        expected_sha = _validated_sha(args.expected_deploy_sha)
        base_url = _validated_base_url(args.base_url)
        receipt = _run(
            base_url=base_url,
            expected_deploy_sha=expected_sha,
            timeout_seconds=float(args.timeout_seconds),
        )
        output = Path(args.output).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(receipt, ensure_ascii=False, indent=2))
        return 0
    except (ProductionContractAuditError, httpx.HTTPError, ValueError) as exc:
        print(f"production contract-audit OCR E2E failed: {exc}", file=sys.stderr)
        return 2


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one authorized scanned-PDF contract audit and validate PDF export.",
    )
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm-production", default="")
    parser.add_argument("--expected-deploy-sha", required=True)
    parser.add_argument("--base-url", default=PRODUCTION_BASE_URL)
    parser.add_argument("--timeout-seconds", type=float, default=360.0)
    parser.add_argument(
        "--output",
        default="tmp/outputs/production-contract-audit-ocr-e2e-latest.json",
    )
    return parser.parse_args()


def _run(
    *,
    base_url: str,
    expected_deploy_sha: str,
    timeout_seconds: float,
) -> dict[str, object]:
    run_id = f"loop129-contract-ocr-{uuid4().hex}"
    headers = {
        "X-User-Id": run_id,
        "X-Role": "auditor",
        "X-Tenant-Id": "hospital-demo",
    }
    scanned_pdf = _sanitized_scanned_contract_pdf()
    source_sha256 = hashlib.sha256(scanned_pdf).hexdigest()

    with httpx.Client(timeout=timeout_seconds, follow_redirects=False) as client:
        metadata_response = client.get(
            f"{base_url}/api/v1/deployment/metadata",
            headers=headers,
        )
        metadata_response.raise_for_status()
        metadata = metadata_response.json()
        if metadata.get("deploy_sha") != expected_deploy_sha:
            raise ProductionContractAuditError("production deploy SHA does not match E2E target")

        capability_response = client.get(
            f"{base_url}/api/v1/ocr/capabilities",
            headers=headers,
        )
        capability_response.raise_for_status()
        capability = capability_response.json()
        if capability.get("enabled") is not True:
            raise ProductionContractAuditError("production OCR capability is not enabled")
        capability_engine = str(capability.get("engine") or "")
        if "deepseek-v4-pro" not in capability_engine or "tesseract" not in capability_engine:
            raise ProductionContractAuditError("production OCR engine is not DeepSeek-assisted")

        audit_response = client.post(
            f"{base_url}/api/v1/contract-audits",
            headers=headers,
            data={
                "project_name": "脱敏合同审计生产验收",
                "audit_stage": "签约前",
                "perspective": "采购方/医院",
                "model": "deepseek-v4-pro",
            },
            files={"file": ("sanitized-scanned-contract.pdf", scanned_pdf, "application/pdf")},
        )
        if audit_response.status_code != 200:
            raise ProductionContractAuditError(
                f"contract audit returned HTTP {audit_response.status_code}"
            )
        job = audit_response.json()
        if job.get("status") != "completed":
            raise ProductionContractAuditError(
                f"contract audit did not complete: {job.get('status')}"
            )
        result = _mapping(job.get("result"), "result")
        extraction = _mapping(result.get("extraction_quality"), "extraction_quality")
        if extraction.get("method") != "deepseek-assisted-ocr":
            raise ProductionContractAuditError("contract audit did not use DeepSeek-assisted OCR")
        if extraction.get("mapping_status") != "resolved":
            raise ProductionContractAuditError("OCR page mapping is not resolved")
        conclusion = _mapping(result.get("conclusion"), "conclusion")
        analysis = conclusion.get("analysis_markdown")
        if not isinstance(analysis, str) or "[C" not in analysis:
            raise ProductionContractAuditError("contract report does not preserve page citations")

        downloads = _mapping(job.get("downloads"), "downloads")
        pdf_path = str(downloads.get("pdf") or "")
        pdf_url = _same_origin_url(base_url, pdf_path)
        report_response = client.get(pdf_url, headers=headers)
        report_response.raise_for_status()
        if report_response.headers.get("content-type", "").split(";", 1)[0] != "application/pdf":
            raise ProductionContractAuditError("report download is not application/pdf")
        report_bytes = report_response.content
        if not report_bytes.startswith(b"%PDF-"):
            raise ProductionContractAuditError("report download is not a PDF file")
        with pymupdf.open(stream=report_bytes, filetype="pdf") as report_document:
            report_text = "".join(page.get_text() for page in report_document)
            report_page_count = report_document.page_count
        if "合同审计报告" not in report_text or "[C" not in report_text:
            raise ProductionContractAuditError("PDF report is not searchable or lacks citations")

    return {
        "status": "pass",
        "evidence_grade": "L4-authorized-live",
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "run_id": run_id,
        "deploy_sha": expected_deploy_sha,
        "provider_call_status": "called",
        "expected_provider_calls": 2,
        "source_sha256": source_sha256,
        "job_id": job.get("job_id"),
        "job_status": job.get("status"),
        "ocr_engine": capability_engine,
        "ocr_method": extraction.get("method"),
        "ocr_mapping_status": extraction.get("mapping_status"),
        "report_media_type": "application/pdf",
        "report_sha256": hashlib.sha256(report_bytes).hexdigest(),
        "report_size_bytes": len(report_bytes),
        "report_page_count": report_page_count,
        "report_text_sha256": hashlib.sha256(report_text.encode("utf-8")).hexdigest(),
        "report_contains_citations": "[C" in report_text,
        "boundaries": {
            "fixture": "sanitized-generated-image-only-pdf",
            "database_write": "contract-job-and-audit-log-only",
            "source_document_retained_in_receipt": False,
            "provider_response_retained_in_receipt": False,
        },
    }


def _sanitized_scanned_contract_pdf() -> bytes:
    source = pymupdf.open()
    try:
        page = source.new_page(width=620, height=360)
        lines = (
            "MEDICAL AUDIT CONTRACT",
            "Buyer: Example Hospital",
            "Supplier: Example Medical Equipment Co.",
            "Payment: CNY 1000 after acceptance.",
            "Delivery: within 30 days after signing.",
            "Penalty: 0.05 percent per delayed day.",
        )
        for index, line in enumerate(lines):
            page.insert_text((35, 55 + index * 45), line, fontsize=20 if index == 0 else 15)
        image = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False).tobytes("png")
    finally:
        source.close()

    scanned = pymupdf.open()
    try:
        page = scanned.new_page(width=620, height=360)
        page.insert_image(page.rect, stream=image)
        content = scanned.tobytes(garbage=4, deflate=True)
    finally:
        scanned.close()
    with pymupdf.open(stream=content, filetype="pdf") as verification:
        if any(page.get_text().strip() for page in verification):
            raise ProductionContractAuditError("generated fixture is not image-only")
    return content


def _validated_sha(value: str) -> str:
    normalized = value.strip().lower()
    if len(normalized) != 40 or any(
        character not in "0123456789abcdef" for character in normalized
    ):
        raise ProductionContractAuditError("--expected-deploy-sha must be a full SHA-1")
    return normalized


def _validated_base_url(value: str) -> str:
    normalized = value.rstrip("/")
    parsed = urlparse(normalized)
    if parsed.scheme != "https" or parsed.hostname != PRODUCTION_DOMAIN or parsed.path:
        raise ProductionContractAuditError("--base-url must be the exact production HTTPS origin")
    return normalized


def _same_origin_url(base_url: str, path: str) -> str:
    resolved = urljoin(base_url + "/", path)
    if urlparse(resolved).netloc != urlparse(base_url).netloc:
        raise ProductionContractAuditError("report download URL changed origin")
    return resolved


def _mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ProductionContractAuditError(f"{label} is not an object")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
