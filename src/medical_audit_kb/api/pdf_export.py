from __future__ import annotations

import re

import pymupdf

PDF_MEDIA_TYPE = "application/pdf"

_A4_WIDTH = 595.0
_A4_HEIGHT = 842.0
_LEFT_MARGIN = 54.0
_RIGHT_MARGIN = 54.0
_TOP_MARGIN = 58.0
_BOTTOM_MARGIN = 54.0
_FONT_NAME = "china-s"


def markdown_to_pdf(markdown: str, *, title: str, subject: str | None = None) -> bytes:
    """Render a compact, searchable CJK-safe audit report PDF."""

    document: pymupdf.Document = pymupdf.open()  # type: ignore[no-untyped-call]
    try:
        document.set_metadata(
            {
                "title": title,
                "subject": subject or "",
                "author": "medical-audit-kb",
                "creator": "medical-audit-kb",
            }
        )
        page = _new_page(document)
        y = _TOP_MARGIN
        for raw_line in markdown.splitlines() or [""]:
            text, font_size, spacing_before, spacing_after = _line_style(raw_line)
            y += spacing_before
            if not text:
                y += max(spacing_after, 7.0)
                continue
            line_height = font_size * 1.55
            for wrapped_line in _wrap_text(
                text,
                max_width=_A4_WIDTH - _LEFT_MARGIN - _RIGHT_MARGIN,
                font_size=font_size,
            ):
                if y + line_height > _A4_HEIGHT - _BOTTOM_MARGIN:
                    page = _new_page(document)
                    y = _TOP_MARGIN
                page.insert_text(
                    (_LEFT_MARGIN, y + font_size),
                    wrapped_line,
                    fontname=_FONT_NAME,
                    fontsize=font_size,
                    color=(0.08, 0.12, 0.18),
                )
                y += line_height
            y += spacing_after

        for page_index in range(document.page_count):
            page_number = page_index + 1
            report_page: pymupdf.Page = document[page_index]
            footer = f"{title}  ·  {page_number}/{document.page_count}"
            report_page.insert_text(
                (_LEFT_MARGIN, _A4_HEIGHT - 25),
                footer,
                fontname=_FONT_NAME,
                fontsize=8.0,
                color=(0.42, 0.46, 0.52),
            )
        content: bytes = document.tobytes(garbage=4, deflate=True)  # type: ignore[no-untyped-call]
        return content
    finally:
        document.close()  # type: ignore[no-untyped-call]


def _new_page(document: pymupdf.Document) -> pymupdf.Page:
    return document.new_page(width=_A4_WIDTH, height=_A4_HEIGHT)


def _line_style(line: str) -> tuple[str, float, float, float]:
    stripped = line.strip()
    if not stripped:
        return "", 11.0, 0.0, 7.0
    if stripped.startswith("### "):
        return _plain_text(stripped[4:]), 13.0, 7.0, 3.0
    if stripped.startswith("## "):
        return _plain_text(stripped[3:]), 15.0, 10.0, 4.0
    if stripped.startswith("# "):
        return _plain_text(stripped[2:]), 19.0, 0.0, 9.0
    if stripped.startswith("> "):
        return f"引用：{_plain_text(stripped[2:])}", 10.5, 3.0, 3.0
    if stripped.startswith("- "):
        return f"• {_plain_text(stripped[2:])}", 10.5, 2.0, 1.0
    return _plain_text(stripped), 10.5, 1.0, 2.0


def _plain_text(value: str) -> str:
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", value)
    text = re.sub(r"__(.*?)__", r"\1", text)
    text = text.replace("`", "")
    return text.strip()


def _wrap_text(text: str, *, max_width: float, font_size: float) -> list[str]:
    if not text:
        return [""]
    lines: list[str] = []
    current = ""
    for character in text:
        candidate = current + character
        width = pymupdf.get_text_length(candidate, fontname=_FONT_NAME, fontsize=font_size)
        if current and width > max_width:
            lines.append(current.rstrip())
            current = character.lstrip()
        else:
            current = candidate
    if current or not lines:
        lines.append(current.rstrip())
    return lines
