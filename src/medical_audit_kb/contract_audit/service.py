from __future__ import annotations

import hashlib
import html
import io
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5
from zipfile import BadZipFile, ZipFile

import anyio
import pymupdf

from medical_audit_kb.contract_audit.prompt import (
    CONTRACT_AUDIT_AGENT_ID,
    CONTRACT_AUDIT_AGENT_PROMPT,
    CONTRACT_AUDIT_PROMPT_VERSION_KEY,
)
from medical_audit_kb.contract_audit.store import ContractAuditJobStore
from medical_audit_kb.domain.constants import SourceCollection
from medical_audit_kb.generation.answer_builder import (
    AnswerGenerationProvider,
    generate_agent_answer,
)
from medical_audit_kb.generation.answer_providers import AnswerProviderError
from medical_audit_kb.generation.citations import Citation, EvidenceType, citation_labels_in_text
from medical_audit_kb.ocr.unlimited_ocr import UnlimitedOcrClientProtocol, UnlimitedOcrError

MAX_CONTRACT_BYTES = 40 * 1024 * 1024
MAX_DOCX_XML_BYTES = 64 * 1024 * 1024
MAX_PROVIDER_EVIDENCE_PAGES = 80
MAX_PROVIDER_SNIPPET_CHARS = 6000
SUPPORTED_EXTENSIONS = frozenset(
    {"pdf", "txt", "md", "docx", "png", "jpg", "jpeg", "tif", "tiff", "bmp"}
)


class ContractAuditOcrUnavailableError(RuntimeError):
    """Raised before a scanned contract can create an empty audit report."""

    code = "unlimited_ocr_unavailable"

    def __init__(self) -> None:
        super().__init__(
            "该合同为扫描件或图片型 PDF，OCR 运行时尚未启用。"
            "请上传可搜索文字版 PDF/DOCX，或联系管理员启用 OCR 后重新提交。"
        )


async def create_contract_audit_job(
    *,
    store: ContractAuditJobStore,
    file_name: str,
    content: bytes,
    created_by: str,
    project_name: str,
    audit_stage: str,
    perspective: str,
    ocr_client: UnlimitedOcrClientProtocol | None,
    generation_provider: AnswerGenerationProvider | None,
) -> dict[str, object]:
    if not content:
        raise ValueError("contract file is empty")
    if len(content) > MAX_CONTRACT_BYTES:
        raise ValueError("contract file exceeds 40 MiB")
    extension = Path(file_name).suffix.lower().lstrip(".")
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError("unsupported contract file type")

    now = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    job_id = f"contract-audit-{uuid4().hex}"
    source_sha = hashlib.sha256(content).hexdigest()
    pages, extraction = await _extract_pages(
        file_name=file_name,
        extension=extension,
        content=content,
        ocr_client=ocr_client,
    )
    mapping_status = str(extraction["mapping_status"])
    report_status = (
        "extraction_review_required" if mapping_status != "resolved" else "insufficient_evidence"
    )
    analysis_markdown = ""
    model = None
    provider = None
    generation_error: dict[str, object] | None = None
    if mapping_status == "resolved" and generation_provider is not None:
        citations = _page_citations(pages, extraction=extraction)
        if citations:
            question = _audit_question(
                file_name=file_name,
                project_name=project_name,
                audit_stage=audit_stage,
                perspective=perspective,
            )
            model = generation_provider.model_name
            provider = generation_provider.provider
            try:
                analysis_markdown = await anyio.to_thread.run_sync(
                    lambda: generate_agent_answer(
                        generation_provider,
                        question,
                        citations,
                        agent_prompt=CONTRACT_AUDIT_AGENT_PROMPT,
                        prompt_version_key=CONTRACT_AUDIT_PROMPT_VERSION_KEY,
                    )
                )
                cited_labels = citation_labels_in_text(analysis_markdown)
                available_labels = {citation.citation_id for citation in citations}
                if not cited_labels or not cited_labels.issubset(available_labels):
                    raise AnswerProviderError(
                        "contract audit output does not preserve page citations",
                        code="provider_response_invalid",
                        reason="contract_audit_page_citations_invalid",
                    )
                report_status = "completed"
            except AnswerProviderError as exc:
                report_status = "failed"
                generation_error = {
                    "code": exc.code,
                    "http_status": exc.http_status,
                    "reason": exc.reason,
                }

    canonical = _canonical_result(
        job_id=job_id,
        status=report_status,
        pages=pages,
        extraction=extraction,
        analysis_markdown=analysis_markdown,
        source_sha=source_sha,
        file_name=file_name,
        audit_stage=audit_stage,
        perspective=perspective,
        provider=provider,
        model=model,
        generated_at=now,
    )
    report_markdown = _report_markdown(canonical)
    job: dict[str, object] = {
        "contract_version": "contract-audit-job-v2",
        "job_id": job_id,
        "status": report_status,
        "created_at": now,
        "updated_at": now,
        "created_by": created_by,
        "project_name": project_name,
        "source": {
            "file_name": Path(file_name).name,
            "extension": extension,
            "sha256": source_sha,
            "size_bytes": len(content),
        },
        "agent": {
            "id": CONTRACT_AUDIT_AGENT_ID,
            "prompt_version_key": CONTRACT_AUDIT_PROMPT_VERSION_KEY,
            "provider": provider,
            "model": model,
            "generation_error": generation_error,
        },
        "pages": pages,
        "result": canonical,
        "report_markdown": report_markdown,
        "downloads": {
            "json": f"/api/v1/contract-audits/{job_id}/report?format=json",
            "markdown": f"/api/v1/contract-audits/{job_id}/report?format=markdown",
            "docx": f"/api/v1/contract-audits/{job_id}/report?format=docx",
            "pdf": f"/api/v1/contract-audits/{job_id}/report?format=pdf",
        },
    }
    return store.put(job)


async def _extract_pages(
    *,
    file_name: str,
    extension: str,
    content: bytes,
    ocr_client: UnlimitedOcrClientProtocol | None,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    if extension == "pdf":
        native_pages = _pdf_text_pages(content)
        if native_pages and sum(len(str(page["text"]).strip()) for page in native_pages) >= 20:
            return native_pages, _extraction_metadata(native_pages, method="native-pdf")
    elif extension in {"txt", "md"}:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("contract text file must be UTF-8 encoded") from exc
        pages = [_page_payload(1, text, image_sha256=None, mapping_status="resolved")]
        return pages, _extraction_metadata(pages, method="native-text")
    elif extension == "docx":
        text = _docx_text(content)
        pages = [_page_payload(1, text, image_sha256=None, mapping_status="resolved")]
        return pages, _extraction_metadata(pages, method="native-docx-logical-page")

    if ocr_client is None:
        raise ContractAuditOcrUnavailableError
    try:
        result = await ocr_client.extract_text(
            file_name=file_name,
            extension=extension,
            content=content,
        )
    except UnlimitedOcrError as exc:
        raise ValueError(str(exc)) from exc
    pages = [
        {
            "page_number": page.page_number,
            "text": page.text,
            "text_sha256": page.text_sha256,
            "image_sha256": page.image_sha256,
            "mapping_status": page.mapping_status,
        }
        for page in result.pages
    ]
    mapping = (
        "resolved"
        if pages and all(page["mapping_status"] == "resolved" for page in pages)
        else "unresolved"
    )
    issues = [] if mapping == "resolved" else ["OCR page-to-text mapping requires human review."]
    extraction = _extraction_metadata(pages, method=result.method, issues=issues)
    extraction["page_count"] = result.page_count
    extraction["mapping_status"] = mapping
    extraction["ocr"] = {"model": result.model, "source_commit": result.source_commit}
    return pages, extraction


def _pdf_text_pages(content: bytes) -> list[dict[str, object]]:
    try:
        with pymupdf.open(  # type: ignore[no-untyped-call]
            stream=content, filetype="pdf"
        ) as document:
            return [
                _page_payload(
                    index + 1, page.get_text("text"), image_sha256=None, mapping_status="resolved"
                )
                for index, page in enumerate(document)
            ]
    except Exception as exc:
        raise ValueError("contract PDF could not be parsed") from exc


def _docx_text(content: bytes) -> str:
    try:
        with ZipFile(io.BytesIO(content)) as archive:
            document_info = archive.getinfo("word/document.xml")
            if document_info.file_size > MAX_DOCX_XML_BYTES:
                raise ValueError("contract DOCX document.xml exceeds extraction limit")
            with archive.open(document_info) as document_file:
                document_bytes = document_file.read(MAX_DOCX_XML_BYTES + 1)
            if len(document_bytes) > MAX_DOCX_XML_BYTES:
                raise ValueError("contract DOCX document.xml exceeds extraction limit")
            document_xml = document_bytes.decode("utf-8")
    except ValueError:
        raise
    except (BadZipFile, KeyError, UnicodeDecodeError) as exc:
        raise ValueError("contract DOCX could not be parsed") from exc

    text = re.sub(r"</w:p>", "\n", document_xml)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


def _page_payload(
    page_number: int, text: str, *, image_sha256: str | None, mapping_status: str
) -> dict[str, object]:
    normalized = text.strip()
    return {
        "page_number": page_number,
        "text": normalized,
        "text_sha256": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        "image_sha256": image_sha256,
        "mapping_status": mapping_status,
    }


def _extraction_metadata(
    pages: list[dict[str, object]], *, method: str, issues: list[str] | None = None
) -> dict[str, object]:
    covered = [
        page_number
        for page in pages
        if isinstance((page_number := page.get("page_number")), int)
        and str(page.get("text") or "").strip()
    ]
    mapping = (
        "resolved"
        if pages and len(covered) == len(pages)
        else "partial"
        if covered
        else "unresolved"
    )
    return {
        "method": method,
        "page_count": len(pages) or 1,
        "covered_pages": covered,
        "mapping_status": mapping,
        "issues": issues
        or ([] if mapping == "resolved" else ["Some pages contain no extractable text."]),
        "ocr": None,
    }


def _page_citations(
    pages: list[dict[str, object]], *, extraction: dict[str, object]
) -> tuple[Citation, ...]:
    candidate_pages = [page for page in pages if str(page.get("text") or "").strip()]
    selected_pages = candidate_pages[:MAX_PROVIDER_EVIDENCE_PAGES]
    if len(candidate_pages) > len(selected_pages):
        _append_extraction_issue(
            extraction,
            f"Provider evidence omitted {len(candidate_pages) - len(selected_pages)} pages "
            f"after the {MAX_PROVIDER_EVIDENCE_PAGES}-page limit.",
        )
    citations = tuple(
        Citation(
            citation_id=f"C{index}",
            evidence_type=EvidenceType.PERSONAL_MATERIAL_BASIS,
            source_collection=SourceCollection.PERSONAL_MATERIALS,
            chunk_id=uuid5(NAMESPACE_URL, f"contract:{page['text_sha256']}"),
            snippet=str(page["text"])[:MAX_PROVIDER_SNIPPET_CHARS],
            locator={"page_number": page["page_number"], "text_sha256": page["text_sha256"]},
            index_version_key="contract-audit-direct-v2",
            source_package_version_key="uploaded-contract",
            score=1.0,
            metadata={"page_number": page["page_number"], "direct_contract_evidence": True},
        )
        for index, page in enumerate(selected_pages, start=1)
    )
    truncated_page_numbers = [
        page["page_number"]
        for page in selected_pages
        if len(str(page["text"])) > MAX_PROVIDER_SNIPPET_CHARS
    ]
    if truncated_page_numbers:
        _append_extraction_issue(
            extraction,
            "Provider evidence snippets were truncated to "
            f"{MAX_PROVIDER_SNIPPET_CHARS} characters for pages: "
            + ", ".join(str(item) for item in truncated_page_numbers),
        )
    return citations


def _append_extraction_issue(extraction: dict[str, object], issue: str) -> None:
    issues = extraction.get("issues")
    if not isinstance(issues, list):
        issues = []
        extraction["issues"] = issues
    issues.append(issue)


def _audit_question(
    *, file_name: str, project_name: str, audit_stage: str, perspective: str
) -> str:
    return (
        f"请审计上传合同《{Path(file_name).name}》。项目：{project_name}；"
        f"阶段：{audit_stage}；视角：{perspective}。严格按合同审计 v2 工作流输出报告。"
    )


def _canonical_result(
    *,
    job_id: str,
    status: str,
    pages: list[dict[str, object]],
    extraction: dict[str, object],
    analysis_markdown: str,
    source_sha: str,
    file_name: str,
    audit_stage: str,
    perspective: str,
    provider: str | None,
    model: str | None,
    generated_at: str,
) -> dict[str, object]:
    analysis = analysis_markdown
    return {
        "contract_version": "contract-audit-output-v2",
        "job_id": job_id,
        "status": status,
        "contract_summary": {
            "file_name": Path(file_name).name,
            "audit_stage": audit_stage,
            "perspective": perspective,
        },
        "extraction_quality": extraction,
        "findings": [],
        "pending_verifications": (
            []
            if status == "completed"
            else [{"reason": "extraction_or_provider_evidence_incomplete"}]
        ),
        "coverage_matrix": {
            "pages": [page["page_number"] for page in pages],
            "dimensions": ["legal_compliance", "commercial", "finance_tax", "performance"],
        },
        "conclusion": {
            "analysis_markdown": analysis,
            "human_review_required": True,
            "disclaimer": "本报告为 AI 辅助审计参考意见，不构成正式法律意见。",
        },
        "provenance": {
            "source_sha256": source_sha,
            "skill_version": "2.0.0",
            "prompt_version_key": CONTRACT_AUDIT_PROMPT_VERSION_KEY,
            "provider": provider,
            "model": model,
            "generated_at": generated_at,
        },
    }


def _report_markdown(result: dict[str, object]) -> str:
    summary = result["contract_summary"]
    extraction = result["extraction_quality"]
    conclusion = result["conclusion"]
    assert (
        isinstance(summary, dict) and isinstance(extraction, dict) and isinstance(conclusion, dict)
    )
    analysis = str(
        conclusion.get("analysis_markdown") or "证据提取或模型能力尚未就绪，未执行风险定性。"
    )
    provenance = json.dumps(result["provenance"], ensure_ascii=False, indent=2)
    return (
        "# 合同审计报告\n\n"
        f"- 文件：{summary['file_name']}\n"
        f"- 审计阶段：{summary['audit_stage']}\n"
        f"- 审计视角：{summary['perspective']}\n"
        f"- 状态：{result['status']}\n"
        f"- 页数：{extraction['page_count']}\n"
        f"- 页面映射：{extraction['mapping_status']}\n\n"
        "## 审计分析\n\n"
        f"{analysis}\n\n"
        "## 来源与生成信息\n\n"
        f"```json\n{provenance}\n```\n\n"
        "> 本报告为 AI 辅助审计参考意见，不构成正式法律意见；所有结论需由授权审计人员复核。\n"
    )
