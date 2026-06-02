from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from medical_audit_kb.domain.constants import SourceCollection
from medical_audit_kb.domain.schemas import DocumentChunkCreate
from medical_audit_kb.ingestion.extractors import (
    ExtractionResult,
    ExtractionStatus,
    TableRow,
    TextSegment,
)

DEFAULT_MAX_CHUNK_CHARS = 1800
DEFAULT_OVERLAP_CHARS = 180

LAW_CHAPTER_PATTERN = re.compile(r"^第[一二三四五六七八九十百千万零〇\d]+章[\s　]*(.+)?$")
LAW_SECTION_PATTERN = re.compile(r"^第[一二三四五六七八九十百千万零〇\d]+节[\s　]*(.+)?$")
LAW_ARTICLE_PATTERN = re.compile(r"^(第[一二三四五六七八九十百千万零〇\d]+条)[\s　]*(.*)$")
MARKDOWN_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


@dataclass(frozen=True, slots=True)
class LocatedLine:
    text: str
    page_number: int | None
    line_number: int | None


@dataclass(frozen=True, slots=True)
class TextBlock:
    text: str
    title_path: tuple[str, ...]
    article_number: str | None
    page_number: int | None
    line_start: int | None
    line_end: int | None
    locator_type: str
    metadata: dict[str, object]


def chunk_extraction_result(
    result: ExtractionResult,
    *,
    source_document_id: UUID,
    source_collection: SourceCollection,
    relative_path: str | None = None,
    max_chunk_chars: int = DEFAULT_MAX_CHUNK_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
) -> list[DocumentChunkCreate]:
    if result.status != ExtractionStatus.EXTRACTED:
        return []

    source_path = relative_path or _safe_relative_path(result.path)
    if result.table_rows:
        return _chunk_table_rows(
            result.table_rows,
            source_document_id=source_document_id,
            source_collection=source_collection,
            source_path=source_path,
        )

    lines = _located_lines(result.text_segments)
    if source_collection == SourceCollection.MEDICAL_INSURANCE_LAWS:
        blocks = _law_blocks(lines)
    else:
        blocks = _ordinary_text_blocks(lines)

    chunks: list[DocumentChunkCreate] = []
    for block in blocks:
        chunks.extend(
            _chunk_text_block(
                block,
                source_document_id=source_document_id,
                source_collection=source_collection,
                source_path=source_path,
                next_chunk_index=len(chunks),
                max_chunk_chars=max_chunk_chars,
                overlap_chars=overlap_chars,
            )
        )
    return chunks


def _chunk_table_rows(
    rows: tuple[TableRow, ...],
    *,
    source_document_id: UUID,
    source_collection: SourceCollection,
    source_path: str,
) -> list[DocumentChunkCreate]:
    chunks: list[DocumentChunkCreate] = []
    for row in rows:
        if _is_header_row(row):
            continue
        text = _table_row_text(row)
        if not text:
            continue
        chunks.append(
            DocumentChunkCreate(
                source_document_id=source_document_id,
                chunk_index=len(chunks),
                text=text,
                title_path=[row.sheet_name],
                sheet_name=row.sheet_name,
                row_number=row.row_number,
                token_count=_rough_token_count(text),
                locator={
                    "type": "xlsx-row",
                    "source_path": source_path,
                    "sheet_name": row.sheet_name,
                    "row_number": row.row_number,
                },
                metadata={
                    "source_collection": source_collection.value,
                    "cells": list(row.cells),
                    "values_by_header": row.values_by_header,
                },
            )
        )
    return chunks


def _is_header_row(row: TableRow) -> bool:
    return row.row_number == 1 and row.values_by_header == {
        cell: cell for cell in row.cells if cell
    }


def _table_row_text(row: TableRow) -> str:
    if row.values_by_header:
        parts = [
            f"{_sanitize_text(key)}: {_sanitize_text(value)}"
            for key, value in row.values_by_header.items()
            if key and value
        ]
        if parts:
            return "\n".join(parts)
    return "\n".join(_sanitize_text(cell) for cell in row.cells if cell)


def _located_lines(segments: tuple[TextSegment, ...]) -> list[LocatedLine]:
    lines: list[LocatedLine] = []
    for segment in segments:
        raw_lines = segment.text.splitlines()
        if not raw_lines and segment.text:
            raw_lines = [segment.text]
        for offset, text in enumerate(raw_lines):
            line_number = segment.line_start + offset if segment.line_start is not None else None
            lines.append(
                LocatedLine(
                    text=_sanitize_text(text).rstrip(),
                    page_number=segment.page_number,
                    line_number=line_number,
                )
            )
    return lines


def _law_blocks(lines: list[LocatedLine]) -> list[TextBlock]:
    blocks: list[TextBlock] = []
    title_path: list[str] = []
    current_article: str | None = None
    current_lines: list[LocatedLine] = []
    preamble_lines: list[LocatedLine] = []

    for line in lines:
        stripped = line.text.strip()
        if not stripped:
            continue

        if LAW_CHAPTER_PATTERN.match(stripped):
            _flush_law_article(blocks, current_lines, title_path, current_article)
            current_lines = []
            current_article = None
            title_path = [stripped]
            continue

        if LAW_SECTION_PATTERN.match(stripped):
            _flush_law_article(blocks, current_lines, title_path, current_article)
            current_lines = []
            current_article = None
            title_path = [title_path[0], stripped] if title_path else [stripped]
            continue

        article_match = LAW_ARTICLE_PATTERN.match(stripped)
        if article_match:
            if current_article is None and preamble_lines:
                blocks.append(_text_block(preamble_lines, tuple(title_path), None, "law-preamble"))
                preamble_lines = []
            _flush_law_article(blocks, current_lines, title_path, current_article)
            current_article = article_match.group(1)
            current_lines = [line]
            continue

        if current_article is None:
            preamble_lines.append(line)
        else:
            current_lines.append(line)

    if current_article is None and preamble_lines:
        blocks.append(_text_block(preamble_lines, tuple(title_path), None, "law-preamble"))
    _flush_law_article(blocks, current_lines, title_path, current_article)
    return blocks


def _flush_law_article(
    blocks: list[TextBlock],
    lines: list[LocatedLine],
    title_path: list[str],
    article_number: str | None,
) -> None:
    if not lines:
        return
    blocks.append(_text_block(lines, tuple(title_path), article_number, "law-article"))


def _ordinary_text_blocks(lines: list[LocatedLine]) -> list[TextBlock]:
    blocks: list[TextBlock] = []
    title_stack: list[str] = []
    paragraph: list[LocatedLine] = []

    for line in lines:
        stripped = line.text.strip()
        heading_match = MARKDOWN_HEADING_PATTERN.match(stripped)
        if heading_match:
            _flush_paragraph(blocks, paragraph, title_stack)
            paragraph = []
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()
            title_stack = title_stack[: level - 1]
            title_stack.append(title)
            continue

        if not stripped:
            _flush_paragraph(blocks, paragraph, title_stack)
            paragraph = []
            continue

        paragraph.append(line)

    _flush_paragraph(blocks, paragraph, title_stack)
    return blocks


def _flush_paragraph(
    blocks: list[TextBlock],
    paragraph: list[LocatedLine],
    title_stack: list[str],
) -> None:
    if not paragraph:
        return
    blocks.append(_text_block(paragraph, tuple(title_stack), None, "paragraph"))


def _text_block(
    lines: list[LocatedLine],
    title_path: tuple[str, ...],
    article_number: str | None,
    locator_type: str,
) -> TextBlock:
    text = "\n".join(line.text.strip() for line in lines if line.text.strip())
    line_numbers = [line.line_number for line in lines if line.line_number is not None]
    page_numbers = [line.page_number for line in lines if line.page_number is not None]
    return TextBlock(
        text=text,
        title_path=title_path,
        article_number=article_number,
        page_number=page_numbers[0] if page_numbers else None,
        line_start=min(line_numbers) if line_numbers else None,
        line_end=max(line_numbers) if line_numbers else None,
        locator_type=locator_type,
        metadata={},
    )


def _chunk_text_block(
    block: TextBlock,
    *,
    source_document_id: UUID,
    source_collection: SourceCollection,
    source_path: str,
    next_chunk_index: int,
    max_chunk_chars: int,
    overlap_chars: int,
) -> list[DocumentChunkCreate]:
    windows = _text_windows(
        block.text,
        max_chunk_chars=max_chunk_chars,
        overlap_chars=overlap_chars,
    )
    chunks: list[DocumentChunkCreate] = []
    for window_index, window_text in enumerate(windows):
        locator = {
            "type": block.locator_type,
            "source_path": source_path,
            "title_path": list(block.title_path),
            "article_number": block.article_number,
            "page_number": block.page_number,
            "line_start": block.line_start,
            "line_end": block.line_end,
        }
        if len(windows) > 1:
            locator.update(
                {
                    "parent_article_number": block.article_number,
                    "window_index": window_index,
                    "window_count": len(windows),
                }
            )

        chunks.append(
            DocumentChunkCreate(
                source_document_id=source_document_id,
                chunk_index=next_chunk_index + window_index,
                text=window_text,
                title_path=list(block.title_path),
                article_number=block.article_number,
                page_number=block.page_number,
                line_start=block.line_start,
                line_end=block.line_end,
                token_count=_rough_token_count(window_text),
                locator=locator,
                metadata={
                    "source_collection": source_collection.value,
                    "is_windowed": len(windows) > 1,
                    **block.metadata,
                },
            )
        )
    return chunks


def _text_windows(text: str, *, max_chunk_chars: int, overlap_chars: int) -> tuple[str, ...]:
    normalized = _sanitize_text(text).strip()
    if not normalized:
        return ()
    if len(normalized) <= max_chunk_chars:
        return (normalized,)

    safe_overlap = min(overlap_chars, max_chunk_chars // 3)
    step = max_chunk_chars - safe_overlap
    windows: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(start + max_chunk_chars, len(normalized))
        windows.append(normalized[start:end].strip())
        if end == len(normalized):
            break
        start += step
    return tuple(window for window in windows if window)


def _rough_token_count(text: str) -> int:
    return max(1, len(text) // 2)


def _safe_relative_path(path: Path) -> str:
    return path.as_posix()


def _sanitize_text(text: str) -> str:
    return text.encode("utf-8", "ignore").decode("utf-8").replace("\x00", "")
