from pathlib import Path
from uuid import uuid4

from openpyxl import Workbook
from pypdf import PdfWriter

from medical_audit_kb.domain.constants import FileErrorType
from medical_audit_kb.ingestion.extractors import (
    ExtractionStatus,
    extract_file,
    failed_file_payload_from_result,
)


def test_extracts_markdown_and_txt_as_text_segments(tmp_path: Path) -> None:
    markdown = tmp_path / "policy.md"
    txt = tmp_path / "rule.txt"
    markdown.write_text("# 医保政策\n第一条 内容", encoding="utf-8")
    txt.write_text("医保规则\n第二行", encoding="utf-8")

    markdown_result = extract_file(markdown)
    txt_result = extract_file(txt)

    assert markdown_result.status == ExtractionStatus.EXTRACTED
    assert markdown_result.media_type == "text/markdown"
    assert markdown_result.text_segments[0].line_start == 1
    assert markdown_result.text_segments[0].line_end == 2
    assert "第一条" in markdown_result.text
    assert txt_result.status == ExtractionStatus.EXTRACTED
    assert txt_result.media_type == "text/plain"
    assert "第二行" in txt_result.text


def test_extracts_text_pdf(tmp_path: Path) -> None:
    pdf_path = tmp_path / "text.pdf"
    pdf_path.write_bytes(
        _minimal_text_pdf_bytes("medical insurance audit policy keeps citation evidence")
    )

    result = extract_file(pdf_path)

    assert result.status == ExtractionStatus.EXTRACTED
    assert result.media_type == "application/pdf"
    assert result.text_segments[0].page_number == 1
    assert "medical insurance audit policy" in result.text


def test_scanned_or_blank_pdf_enters_pending_queue(tmp_path: Path) -> None:
    pdf_path = tmp_path / "blank.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with pdf_path.open("wb") as file:
        writer.write(file)

    result = extract_file(pdf_path)

    assert result.status == ExtractionStatus.PENDING
    assert result.error_type == FileErrorType.LOW_QUALITY_TEXT
    assert result.error_summary is not None
    assert "too little extractable text" in result.error_summary


def test_extracts_xlsx_rows_with_sheet_and_header_mapping(tmp_path: Path) -> None:
    xlsx_path = tmp_path / "rules.xlsx"
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "规则"
    worksheet.append(["规则编码", "规则名称", "说明"])
    worksheet.append(["R001", "超量开药", "超过限定数量"])
    worksheet.append(["R002", "超期开药", None])
    workbook.save(xlsx_path)

    result = extract_file(xlsx_path)

    assert result.status == ExtractionStatus.EXTRACTED
    assert result.media_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert len(result.table_rows) == 3
    assert result.table_rows[1].sheet_name == "规则"
    assert result.table_rows[1].row_number == 2
    assert result.table_rows[1].cells == ("R001", "超量开药", "超过限定数量")
    assert result.table_rows[1].values_by_header["规则名称"] == "超量开药"
    assert result.table_rows[2].values_by_header["说明"] == ""


def test_unsupported_files_enter_pending_queue(tmp_path: Path) -> None:
    png = tmp_path / "scan.png"
    zip_file = tmp_path / "archive.zip"
    rar = tmp_path / "archive.rar"
    docx = tmp_path / "policy.docx"
    for path in (png, zip_file, rar, docx):
        path.write_bytes(b"not processed in v1")

    results = [extract_file(path) for path in (png, zip_file, rar, docx)]

    assert all(result.status == ExtractionStatus.PENDING for result in results)
    assert all(result.error_type == FileErrorType.UNSUPPORTED_TYPE for result in results)
    assert [result.media_type for result in results] == [
        "image/png",
        "application/zip",
        "application/vnd.rar",
        "application/octet-stream",
    ]


def test_corrupted_file_can_be_converted_to_failed_file_payload(tmp_path: Path) -> None:
    pdf_path = tmp_path / "corrupted.pdf"
    pdf_path.write_text("not a real pdf", encoding="utf-8")

    result = extract_file(pdf_path)
    payload = failed_file_payload_from_result(
        result,
        source_package_version_id=uuid4(),
        relative_path="全量法律/corrupted.pdf",
    )

    assert result.status == ExtractionStatus.FAILED
    assert result.error_type == FileErrorType.EXTRACTION_FAILED
    assert payload.relative_path == "全量法律/corrupted.pdf"
    assert payload.error_type == FileErrorType.EXTRACTION_FAILED
    assert payload.error_summary


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
        b"5 0 obj << /Length " + str(len(stream)).encode("ascii") + b" >> stream\n"
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
