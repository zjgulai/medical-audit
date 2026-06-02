from pathlib import Path

import pytest
from openpyxl import Workbook
from pypdf import PdfWriter

from medical_audit_kb.preview.resolver import PreviewResolutionError, PreviewResolver


def test_resolves_markdown_by_line_range_and_highlights_text(tmp_path: Path) -> None:
    source_root = tmp_path / "data"
    markdown = source_root / "全量法律" / "law.md"
    _write_text(
        markdown,
        "\n".join(
            [
                "标题",
                "第一条 医保基金监管要求。",
                "医疗机构应保留审核依据。",
                "第二条 其他内容。",
            ]
        ),
    )

    preview = PreviewResolver(source_root=source_root).resolve(
        {
            "type": "law-article",
            "source_path": "全量法律/law.md",
            "line_start": 2,
            "line_end": 3,
        },
        citation_text="医疗机构应保留审核依据",
    )

    assert preview.source_path == markdown
    assert preview.media_type == "text/markdown"
    assert preview.line_start == 1
    assert preview.line_end == 4
    assert "第一条 医保基金监管要求。" in preview.preview_text
    assert preview.highlights[0].text == "医疗机构应保留审核依据"


def test_resolves_text_article_when_line_range_is_absent(tmp_path: Path) -> None:
    source_root = tmp_path / "data"
    text_file = source_root / "policy.txt"
    _write_text(
        text_file,
        "\n".join(
            [
                "总则",
                "第一条 第一条内容。",
                "第一条续行。",
                "第二条 第二条内容。",
            ]
        ),
    )

    preview = PreviewResolver(source_root=source_root).resolve(
        {
            "type": "law-article",
            "source_path": "policy.txt",
            "article_number": "第一条",
        },
        citation_text="第一条续行",
    )

    assert preview.media_type == "text/plain"
    assert "第一条 第一条内容。" in preview.preview_text
    assert "第一条续行。" in preview.preview_text
    assert "第二条 第二条内容。" in preview.preview_text
    assert preview.highlights[0].text == "第一条续行"


def test_resolves_pdf_page_and_highlight_ranges(tmp_path: Path) -> None:
    source_root = tmp_path / "data"
    pdf_path = source_root / "医保目录" / "catalog.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(_minimal_text_pdf_bytes("medical insurance catalog page text"))

    preview = PreviewResolver(source_root=source_root).resolve(
        {
            "type": "pdf-page",
            "source_path": "医保目录/catalog.pdf",
            "page_number": 1,
        },
        citation_text="insurance catalog",
    )

    assert preview.source_path == pdf_path
    assert preview.media_type == "application/pdf"
    assert preview.page_number == 1
    assert "medical insurance catalog page text" in preview.preview_text
    assert [highlight.text for highlight in preview.highlights] == ["insurance catalog"]


def test_resolves_xlsx_sheet_row_and_highlights_cell_text(tmp_path: Path) -> None:
    source_root = tmp_path / "data"
    xlsx_path = source_root / "智能监管“两库”规则和知识点" / "rules.xlsx"
    _write_xlsx(xlsx_path)

    preview = PreviewResolver(source_root=source_root).resolve(
        {
            "type": "xlsx-row",
            "source_path": "智能监管“两库”规则和知识点/rules.xlsx",
            "sheet_name": "规则",
            "row_number": 2,
        },
        citation_text="超量开药",
    )

    assert preview.source_path == xlsx_path
    assert preview.media_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert preview.sheet_name == "规则"
    assert preview.row_number == 2
    assert "1: R001" in preview.preview_text
    assert "2: 超量开药" in preview.preview_text
    assert preview.highlights[0].text == "超量开药"


def test_resolver_keeps_absolute_source_path(tmp_path: Path) -> None:
    source_root = tmp_path / "data"
    markdown = source_root / "source.md"
    _write_text(markdown, "医保内容")

    preview = PreviewResolver(source_root=source_root).resolve(
        {"type": "line", "source_path": str(markdown), "line_start": 1}
    )

    assert preview.source_path == markdown
    assert preview.preview_text == "医保内容"


def test_resolver_rejects_missing_pdf_page(tmp_path: Path) -> None:
    source_root = tmp_path / "data"
    pdf_path = source_root / "blank.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with pdf_path.open("wb") as file:
        writer.write(file)

    with pytest.raises(PreviewResolutionError, match="pdf locator must contain page_number"):
        PreviewResolver(source_root=source_root).resolve(
            {"type": "pdf-page", "source_path": "blank.pdf"}
        )


def _write_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _write_xlsx(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    worksheet = workbook.active
    assert worksheet is not None
    worksheet.title = "规则"
    worksheet.append(["规则编码", "规则名称"])
    worksheet.append(["R001", "超量开药"])
    workbook.save(path)
    return path


def _minimal_text_pdf_bytes(text: str) -> bytes:
    escaped_text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 50 750 Td ({escaped_text}) Tj ET".encode("ascii")
    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
        (
            b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n"
        ),
        b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
        b"5 0 obj << /Length "
        + str(len(stream)).encode("ascii")
        + b" >> stream\n"
        + stream
        + b"\nendstream endobj\n",
    ]
    content = b"%PDF-1.4\n"
    offsets = [0]
    for pdf_object in objects:
        offsets.append(len(content))
        content += pdf_object
    xref_offset = len(content)
    content += f"xref\n0 {len(objects) + 1}\n".encode("ascii")
    content += b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        content += f"{offset:010d} 00000 n \n".encode("ascii")
    content += (
        b"trailer << /Size "
        + str(len(objects) + 1).encode("ascii")
        + b" /Root 1 0 R >>\nstartxref\n"
        + str(xref_offset).encode("ascii")
        + b"\n%%EOF\n"
    )
    return content
