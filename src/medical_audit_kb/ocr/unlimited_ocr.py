from __future__ import annotations

import base64
import hashlib
import os
import re
from dataclasses import dataclass
from typing import Protocol

import httpx
import pymupdf

from medical_audit_kb.core.config import UnlimitedOcrSettings

SUPPORTED_IMAGE_EXTENSIONS: frozenset[str] = frozenset({"bmp", "jpeg", "jpg", "png", "tif", "tiff"})
_REFERENCE_TAG_PATTERN = re.compile(r"<\|/?ref\|>")
_DETECTION_PATTERN = re.compile(r"<\|det\|>.*?<\|/det\|>", flags=re.DOTALL)
_PAGE_BLOCK_PATTERN = re.compile(
    r"<page\s+(?:number=)?[\"']?(\d+)[\"']?>\s*(.*?)\s*</page>",
    flags=re.DOTALL | re.IGNORECASE,
)
_PAGE_TAG_PATTERN = re.compile(r"</?page(?:\s+[^>]*)?>", flags=re.IGNORECASE)


class UnlimitedOcrError(RuntimeError):
    """Safe OCR failure that does not include response bodies or credentials."""


@dataclass(frozen=True, slots=True)
class UnlimitedOcrPage:
    page_number: int
    text: str
    image_sha256: str
    text_sha256: str
    mapping_status: str


@dataclass(frozen=True, slots=True)
class UnlimitedOcrResult:
    text: str
    page_count: int
    model: str
    source_commit: str
    pages: tuple[UnlimitedOcrPage, ...] = ()


class UnlimitedOcrClientProtocol(Protocol):
    async def extract_text(
        self,
        *,
        file_name: str,
        extension: str,
        content: bytes,
    ) -> UnlimitedOcrResult: ...


@dataclass(frozen=True, slots=True)
class UnlimitedOcrClient:
    settings: UnlimitedOcrSettings

    async def extract_text(
        self,
        *,
        file_name: str,
        extension: str,
        content: bytes,
    ) -> UnlimitedOcrResult:
        del file_name
        images = _render_images(
            extension=extension,
            content=content,
            settings=self.settings,
        )
        prompt = "\n".join(
            [
                *("<image>" for _ in images),
                "Multi page parsing. Return each page exactly once as "
                '<page number="N">recognized text</page> in source order.',
            ]
        )
        message_content: list[dict[str, object]] = [{"type": "text", "text": prompt}]
        message_content.extend(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{encoded}"},
            }
            for encoded in images
        )
        headers = {"Content-Type": "application/json"}
        if self.settings.api_key_env:
            api_key = os.getenv(self.settings.api_key_env)
            if not api_key:
                raise UnlimitedOcrError("Unlimited-OCR API key is not configured")
            headers["Authorization"] = f"Bearer {api_key}"
        payload = {
            "model": self.settings.model,
            "messages": [{"role": "user", "content": message_content}],
            "temperature": 0,
            "max_tokens": self.settings.max_output_tokens,
            "skip_special_tokens": False,
            "vllm_xargs": {
                "ngram_size": 35,
                "window_size": 1024 if len(images) > 1 else 128,
            },
        }
        endpoint = f"{self.settings.base_url.rstrip('/')}/chat/completions"
        try:
            async with httpx.AsyncClient(timeout=self.settings.timeout_seconds) as client:
                response = await client.post(endpoint, headers=headers, json=payload)
                response.raise_for_status()
                body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise UnlimitedOcrError("Unlimited-OCR request failed") from exc
        try:
            raw_text = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise UnlimitedOcrError("Unlimited-OCR returned an invalid response") from exc
        if not isinstance(raw_text, str):
            raise UnlimitedOcrError("Unlimited-OCR returned an invalid response")
        text = _clean_ocr_text(raw_text)
        if not text:
            raise UnlimitedOcrError("Unlimited-OCR returned no readable text")
        pages = _page_results(raw_text, images)
        return UnlimitedOcrResult(
            text=text,
            page_count=len(images),
            model=self.settings.model,
            source_commit=self.settings.source_commit,
            pages=pages,
        )


def unlimited_ocr_client_from_settings(
    settings: UnlimitedOcrSettings,
) -> UnlimitedOcrClient | None:
    if not settings.enabled:
        return None
    return UnlimitedOcrClient(settings=settings)


def _render_images(
    *,
    extension: str,
    content: bytes,
    settings: UnlimitedOcrSettings,
) -> list[str]:
    normalized_extension = extension.lower()
    if normalized_extension == "pdf":
        try:
            document = pymupdf.open(  # type: ignore[no-untyped-call]
                stream=content, filetype="pdf"
            )
        except Exception as exc:
            raise UnlimitedOcrError("PDF could not be rendered for OCR") from exc
        try:
            if document.page_count > settings.max_pages:
                raise UnlimitedOcrError(
                    f"PDF exceeds the configured OCR page limit ({settings.max_pages})"
                )
            scale = settings.pdf_dpi / 72
            matrix = pymupdf.Matrix(scale, scale)  # type: ignore[no-untyped-call]
            images: list[str] = []
            total_pixels = 0
            for page in document:  # type: ignore[attr-defined]
                pixmap = page.get_pixmap(matrix=matrix, alpha=False)
                total_pixels += pixmap.width * pixmap.height
                if total_pixels > settings.max_total_pixels:
                    raise UnlimitedOcrError("PDF exceeds the configured OCR pixel limit")
                images.append(base64.b64encode(pixmap.tobytes("png")).decode("ascii"))
            if not images:
                raise UnlimitedOcrError("PDF does not contain any pages")
            return images
        finally:
            document.close()  # type: ignore[no-untyped-call]
    if normalized_extension not in SUPPORTED_IMAGE_EXTENSIONS:
        raise UnlimitedOcrError("file type is not supported by Unlimited-OCR")
    try:
        with pymupdf.open(  # type: ignore[no-untyped-call]
            stream=content, filetype=normalized_extension
        ) as image_document:
            page = image_document[0]
            pixmap = page.get_pixmap(alpha=False)
            if pixmap.width * pixmap.height > settings.max_total_pixels:
                raise UnlimitedOcrError("image exceeds the configured OCR pixel limit")
            return [base64.b64encode(pixmap.tobytes("png")).decode("ascii")]
    except UnlimitedOcrError:
        raise
    except Exception as exc:
        raise UnlimitedOcrError("image could not be rendered for OCR") from exc


def _clean_ocr_text(value: str) -> str:
    without_detections = _DETECTION_PATTERN.sub("", value)
    without_tags = _REFERENCE_TAG_PATTERN.sub("", without_detections)
    without_tags = _PAGE_TAG_PATTERN.sub("\n", without_tags)
    without_tags = re.sub(r"\n(?:[ \t]*\n)+", "\n", without_tags)
    return "\n".join(line.rstrip() for line in without_tags.splitlines()).strip()


def _page_results(raw_text: str, images: list[str]) -> tuple[UnlimitedOcrPage, ...]:
    image_hashes = tuple(
        hashlib.sha256(base64.b64decode(encoded)).hexdigest() for encoded in images
    )
    if len(images) == 1:
        text = _clean_ocr_text(raw_text)
        return (
            UnlimitedOcrPage(
                page_number=1,
                text=text,
                image_sha256=image_hashes[0],
                text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                mapping_status="resolved",
            ),
        )

    block_items = [
        (int(page_number), _clean_ocr_text(text))
        for page_number, text in _PAGE_BLOCK_PATTERN.findall(raw_text)
    ]
    blocks = dict(block_items)
    expected_page_numbers = list(range(1, len(images) + 1))
    actual_page_numbers = [page_number for page_number, _ in block_items]
    mapping_resolved = actual_page_numbers == expected_page_numbers and all(
        blocks.get(index) for index in expected_page_numbers
    )
    return tuple(
        UnlimitedOcrPage(
            page_number=index,
            text=blocks.get(index, ""),
            image_sha256=image_hashes[index - 1],
            text_sha256=hashlib.sha256(blocks.get(index, "").encode("utf-8")).hexdigest(),
            mapping_status="resolved" if mapping_resolved else "unresolved",
        )
        for index in range(1, len(images) + 1)
    )
