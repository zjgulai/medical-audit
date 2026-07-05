from pathlib import Path
from uuid import uuid4

from medical_audit_kb.domain.constants import SourceCollection
from medical_audit_kb.ingestion.chunkers import chunk_extraction_result
from medical_audit_kb.ingestion.extractors import (
    ExtractionResult,
    ExtractionStatus,
    TableRow,
    TextSegment,
)


def test_chunks_law_text_by_chapter_section_and_article() -> None:
    source_document_id = uuid4()
    result = ExtractionResult(
        path=Path("医疗保障基金使用监督管理条例.md"),
        status=ExtractionStatus.EXTRACTED,
        media_type="text/markdown",
        text_segments=(
            TextSegment(
                text=(
                    "第一章 总则\n"
                    "第一节 基本要求\n"
                    "第一条 医疗保障基金使用应当合法合规。\n"
                    "经办机构应当保留审核依据。\n"
                    "第二条 医疗机构应当配合监督检查。"
                ),
                line_start=1,
                line_end=5,
            ),
        ),
    )

    chunks = chunk_extraction_result(
        result,
        source_document_id=source_document_id,
        source_collection=SourceCollection.MEDICAL_INSURANCE_LAWS,
        domain="医保基金",
        relative_path="全量法律/医疗保障基金使用监督管理条例.md",
    )

    assert [chunk.article_number for chunk in chunks] == ["第一条", "第二条"]
    assert chunks[0].source_document_id == source_document_id
    assert chunks[0].title_path == ["第一章 总则", "第一节 基本要求"]
    assert chunks[0].line_start == 3
    assert chunks[0].line_end == 4
    assert chunks[0].locator["source_path"] == "全量法律/医疗保障基金使用监督管理条例.md"
    assert chunks[0].locator["type"] == "law-article"
    assert chunks[0].metadata["source_collection"] == "medical-insurance-laws"
    # domain 进 chunk 元数据 → 专题检索可按 domain 过滤（默认不传时为 ""）。
    assert chunks[0].metadata["domain"] == "医保基金"
    assert "审核依据" in chunks[0].text


def test_law_preamble_can_be_excluded_from_chunks() -> None:
    result = ExtractionResult(
        path=Path("护士条例.md"),
        status=ExtractionStatus.EXTRACTED,
        media_type="text/markdown",
        text_segments=(
            TextSegment(
                text=(
                    "---\n"
                    'title: "护士条例"\n'
                    "---\n"
                    "护士条例\n"
                    "第一章 总则\n"
                    "第一条 为了维护护士的合法权益，制定本条例。\n"
                    "第二条 本条例所称护士，是指取得护士执业证书的人员。"
                ),
                line_start=1,
                line_end=7,
            ),
        ),
    )

    chunks = chunk_extraction_result(
        result,
        source_document_id=uuid4(),
        source_collection=SourceCollection.MEDICAL_INSURANCE_LAWS,
        relative_path="全量法律/护士条例.md",
        include_law_preamble=False,
    )

    assert [chunk.locator["type"] for chunk in chunks] == ["law-article", "law-article"]
    assert [chunk.article_number for chunk in chunks] == ["第一条", "第二条"]
    assert all("title:" not in chunk.text for chunk in chunks)


def test_law_text_without_article_falls_back_to_paragraph_chunks() -> None:
    result = ExtractionResult(
        path=Path("legal-decision.md"),
        status=ExtractionStatus.EXTRACTED,
        media_type="text/markdown",
        text_segments=(
            TextSegment(
                text=(
                    "# 医疗保障决定\n"
                    "本决定用于规范医疗保障基金监督管理。\n"
                    "一、加强审核。\n"
                    "二、完善整改。"
                ),
                line_start=1,
                line_end=4,
            ),
        ),
    )

    chunks = chunk_extraction_result(
        result,
        source_document_id=uuid4(),
        source_collection=SourceCollection.MEDICAL_INSURANCE_LAWS,
        relative_path="全量法律/legal-decision.md",
        include_law_preamble=False,
    )

    assert len(chunks) == 1
    assert chunks[0].locator["type"] == "paragraph"
    assert chunks[0].article_number is None
    assert chunks[0].title_path == ["医疗保障决定"]
    assert "加强审核" in chunks[0].text


def test_chunks_ordinary_markdown_by_headings_and_paragraphs() -> None:
    result = ExtractionResult(
        path=Path("普通文档.md"),
        status=ExtractionStatus.EXTRACTED,
        media_type="text/markdown",
        text_segments=(
            TextSegment(
                text=(
                    "# 审核说明\n第一段说明。\n\n第二段说明。\n继续第二段。\n## 细则\n细则段落。"
                ),
                line_start=1,
                line_end=7,
            ),
        ),
    )

    chunks = chunk_extraction_result(
        result,
        source_document_id=uuid4(),
        source_collection=SourceCollection.SUPERVISION_RULES_KNOWLEDGE,
        relative_path="智能监管“两库”规则和知识点/普通文档.md",
    )

    assert [chunk.text for chunk in chunks] == [
        "第一段说明。",
        "第二段说明。\n继续第二段。",
        "细则段落。",
    ]
    assert chunks[0].title_path == ["审核说明"]
    assert chunks[1].line_start == 4
    assert chunks[1].line_end == 5
    assert chunks[2].title_path == ["审核说明", "细则"]
    assert chunks[2].locator["type"] == "paragraph"


def test_chunks_xlsx_rows_with_sheet_and_row_locator() -> None:
    result = ExtractionResult(
        path=Path("rules.xlsx"),
        status=ExtractionStatus.EXTRACTED,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        table_rows=(
            TableRow(
                sheet_name="规则",
                row_number=1,
                cells=("规则编码", "规则名称"),
                values_by_header={"规则编码": "规则编码", "规则名称": "规则名称"},
            ),
            TableRow(
                sheet_name="规则",
                row_number=2,
                cells=("R001", "超量开药"),
                values_by_header={"规则编码": "R001", "规则名称": "超量开药"},
            ),
        ),
    )

    chunks = chunk_extraction_result(
        result,
        source_document_id=uuid4(),
        source_collection=SourceCollection.SUPERVISION_RULES_KNOWLEDGE,
        relative_path="智能监管“两库”规则和知识点/rules.xlsx",
    )

    assert len(chunks) == 1
    assert chunks[0].sheet_name == "规则"
    assert chunks[0].row_number == 2
    assert chunks[0].title_path == ["规则"]
    assert "规则编码: R001" in chunks[0].text
    assert "规则名称: 超量开药" in chunks[0].text
    assert chunks[0].locator == {
        "type": "xlsx-row",
        "source_path": "智能监管“两库”规则和知识点/rules.xlsx",
        "sheet_name": "规则",
        "row_number": 2,
    }
    assert chunks[0].metadata["values_by_header"]["规则名称"] == "超量开药"


def test_splits_long_article_into_windows_with_parent_locator() -> None:
    long_body = "医保基金监管要求。" * 30
    result = ExtractionResult(
        path=Path("long-law.md"),
        status=ExtractionStatus.EXTRACTED,
        media_type="text/markdown",
        text_segments=(
            TextSegment(
                text=f"第一章 总则\n第一条 {long_body}",
                line_start=1,
                line_end=2,
            ),
        ),
    )

    chunks = chunk_extraction_result(
        result,
        source_document_id=uuid4(),
        source_collection=SourceCollection.MEDICAL_INSURANCE_LAWS,
        relative_path="全量法律/long-law.md",
        max_chunk_chars=80,
        overlap_chars=10,
    )

    assert len(chunks) > 1
    assert {chunk.article_number for chunk in chunks} == {"第一条"}
    assert all(chunk.locator["parent_article_number"] == "第一条" for chunk in chunks)
    assert all(chunk.locator["window_count"] == len(chunks) for chunk in chunks)
    assert [chunk.locator["window_index"] for chunk in chunks] == list(range(len(chunks)))
    assert all(chunk.metadata["is_windowed"] is True for chunk in chunks)


def test_non_extracted_result_returns_no_chunks() -> None:
    result = ExtractionResult(
        path=Path("scan.png"),
        status=ExtractionStatus.PENDING,
        media_type="image/png",
    )

    chunks = chunk_extraction_result(
        result,
        source_document_id=uuid4(),
        source_collection=SourceCollection.RISK_NEGATIVE_LIST,
        relative_path="风险负面清单/scan.png",
    )

    assert chunks == []


def test_chunker_sanitizes_invalid_unicode_surrogates() -> None:
    result = ExtractionResult(
        path=Path("bad-unicode.md"),
        status=ExtractionStatus.EXTRACTED,
        media_type="text/markdown",
        text_segments=(
            TextSegment(
                text="医保\udce2审核依据",
                line_start=1,
                line_end=1,
            ),
        ),
    )

    chunks = chunk_extraction_result(
        result,
        source_document_id=uuid4(),
        source_collection=SourceCollection.SUPERVISION_RULES_KNOWLEDGE,
        relative_path="智能监管“两库”规则和知识点/bad-unicode.md",
    )

    assert chunks[0].text == "医保审核依据"
