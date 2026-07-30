from __future__ import annotations

import base64
import os
import re
from dataclasses import dataclass
from typing import Protocol

import httpx
import pymupdf

from medical_audit_kb.core.config import UnlimitedOcrSettings

_IMAGE_EXTENSIONS = {"bmp", "jpeg", "jpg", "png", "tif", "tiff", "webp"}
_REFERENCE_TAG_PATTERN = re.compile(r"<\|/?ref\|>")
_DETECTION_PATTERN = re.compile(r"<\|det\|>.*?<\|/det\|>", flags=re.DOTALL)


class UnlimitedOcrError(RuntimeError):
    """Safe OCR failure that does not include response bodies or credentials."""


@dataclass(frozen=True, slots=True)
class UnlimitedOcrResult:
    text: str
    page_count: int
    model: str
    source_commit: str


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
        prompt = "\n".join([*("<image>" for _ in images), "Multi page parsing."])
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
        return UnlimitedOcrResult(
            text=text,
            page_count=len(images),
            model=self.settings.model,
            source_commit=self.settings.source_commit,
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
            document = pymupdf.open(stream=content, filetype="pdf")
        except Exception as exc:
            raise UnlimitedOcrError("PDF could not be rendered for OCR") from exc
        try:
            if document.page_count > settings.max_pages:
                raise UnlimitedOcrError(
                    f"PDF exceeds the configured OCR page limit ({settings.max_pages})"
                )
            scale = settings.pdf_dpi / 72
            matrix = pymupdf.Matrix(scale, scale)
            images: list[str] = []
            total_pixels = 0
            for page in document:
                pixmap = page.get_pixmap(matrix=matrix, alpha=False)
                total_pixels += pixmap.width * pixmap.height
                if total_pixels > settings.max_total_pixels:
                    raise UnlimitedOcrError("PDF exceeds the configured OCR pixel limit")
                images.append(base64.b64encode(pixmap.tobytes("png")).decode("ascii"))
            if not images:
                raise UnlimitedOcrError("PDF does not contain any pages")
            return images
        finally:
            document.close()
    if normalized_extension not in _IMAGE_EXTENSIONS:
        raise UnlimitedOcrError("file type is not supported by Unlimited-OCR")
    try:
        with pymupdf.open(stream=content, filetype=normalized_extension) as image_document:
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
    return "\n".join(line.rstrip() for line in without_tags.splitlines()).strip()
