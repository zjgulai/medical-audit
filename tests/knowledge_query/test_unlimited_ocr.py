from __future__ import annotations

import asyncio
from io import BytesIO
from typing import Any

import pytest
from pypdf import PdfWriter

from medical_audit_kb.api.routes_chat import (
    OCR_IMAGE_EXTENSIONS,
    SUPPORTED_DOCUMENT_EXTENSIONS,
)
from medical_audit_kb.core.config import UnlimitedOcrSettings
from medical_audit_kb.ocr.unlimited_ocr import (
    SUPPORTED_IMAGE_EXTENSIONS,
    UnlimitedOcrClient,
    UnlimitedOcrError,
    _render_images,
)


def test_unlimited_ocr_uses_pinned_vllm_contract_without_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                "<|ref|>医保基金审计<|/ref|>"
                                "<|det|>[[1,2,3,4]]<|/det|>\n应复核异常结算。"
                            )
                        }
                    }
                ]
            }

    class FakeAsyncClient:
        def __init__(self, *, timeout: float) -> None:
            assert timeout == 60

        async def __aenter__(self) -> FakeAsyncClient:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(
            self,
            endpoint: str,
            *,
            headers: dict[str, str],
            json: dict[str, object],
        ) -> FakeResponse:
            calls.append({"endpoint": endpoint, "headers": headers, "json": json})
            return FakeResponse()

    monkeypatch.setattr(
        "medical_audit_kb.ocr.unlimited_ocr.httpx.AsyncClient",
        FakeAsyncClient,
    )
    pdf_bytes = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.write(pdf_bytes)
    client = UnlimitedOcrClient(
        settings=UnlimitedOcrSettings(
            enabled=True,
            timeout_seconds=60,
            pdf_dpi=72,
            max_output_tokens=900,
        )
    )

    result = asyncio.run(
        client.extract_text(
            file_name="scan.pdf",
            extension="pdf",
            content=pdf_bytes.getvalue(),
        )
    )

    assert result.text == "医保基金审计\n应复核异常结算。"
    assert result.page_count == 1
    assert result.model == "baidu/Unlimited-OCR"
    assert len(calls) == 1
    request = calls[0]
    assert request["endpoint"] == "http://127.0.0.1:8000/v1/chat/completions"
    payload = request["json"]
    assert payload["model"] == "baidu/Unlimited-OCR"
    assert payload["max_tokens"] == 900
    assert payload["skip_special_tokens"] is False
    assert payload["vllm_xargs"] == {"ngram_size": 35, "window_size": 128}
    messages = payload["messages"]
    assert isinstance(messages, list)
    content = messages[0]["content"]
    assert content[0] == {"type": "text", "text": "<image>\nMulti page parsing."}
    assert str(content[1]["image_url"]["url"]).startswith("data:image/png;base64,")


def test_unlimited_ocr_does_not_advertise_or_render_webp() -> None:
    assert (
        SUPPORTED_DOCUMENT_EXTENSIONS.intersection(SUPPORTED_IMAGE_EXTENSIONS)
        == OCR_IMAGE_EXTENSIONS
    )
    assert "webp" not in OCR_IMAGE_EXTENSIONS

    with pytest.raises(
        UnlimitedOcrError,
        match="file type is not supported by Unlimited-OCR",
    ):
        _render_images(
            extension="webp",
            content=b"not-a-supported-image",
            settings=UnlimitedOcrSettings(),
        )
