from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def markdown_to_docx(markdown: str, *, title: str, subject: str | None = None) -> bytes:
    generated_at = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    document_xml = _document_xml(markdown)
    buffer = BytesIO()
    with ZipFile(buffer, mode="w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _content_types_xml())
        archive.writestr("_rels/.rels", _package_relationships_xml())
        archive.writestr("docProps/app.xml", _app_properties_xml())
        archive.writestr(
            "docProps/core.xml",
            _core_properties_xml(title=title, subject=subject, generated_at=generated_at),
        )
        archive.writestr("word/document.xml", document_xml)
        archive.writestr("word/styles.xml", _styles_xml())
    return buffer.getvalue()


def _document_xml(markdown: str) -> str:
    paragraphs = [_markdown_line_to_paragraph(line) for line in markdown.splitlines()]
    if not paragraphs:
        paragraphs = [_paragraph_xml("")]
    body = "".join(paragraphs)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}"
        "<w:sectPr>"
        '<w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" '
        'w:header="720" w:footer="720" w:gutter="0"/>'
        "</w:sectPr>"
        "</w:body></w:document>"
    )


def _markdown_line_to_paragraph(line: str) -> str:
    stripped = line.strip()
    if not stripped:
        return _paragraph_xml("")
    if stripped.startswith("### "):
        return _paragraph_xml(stripped.removeprefix("### "), style="Heading3", bold=True)
    if stripped.startswith("## "):
        return _paragraph_xml(stripped.removeprefix("## "), style="Heading2", bold=True)
    if stripped.startswith("# "):
        return _paragraph_xml(stripped.removeprefix("# "), style="Heading1", bold=True)
    if stripped.startswith("> "):
        return _paragraph_xml(stripped.removeprefix("> "), style="Quote", italic=True)
    if stripped.startswith("- ["):
        return _paragraph_xml(stripped.removeprefix("- "), style="ListParagraph")
    if stripped.startswith("- "):
        return _paragraph_xml(f"\u2022 {stripped.removeprefix('- ')}", style="ListParagraph")
    return _paragraph_xml(stripped)


def _paragraph_xml(
    text: str,
    *,
    style: str | None = None,
    bold: bool = False,
    italic: bool = False,
) -> str:
    paragraph_properties = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    run_properties = _run_properties_xml(bold=bold, italic=italic)
    return (
        f"<w:p>{paragraph_properties}<w:r>{run_properties}"
        f'<w:t xml:space="preserve">{_xml_text(text)}</w:t>'
        "</w:r></w:p>"
    )


def _run_properties_xml(*, bold: bool, italic: bool) -> str:
    values: list[str] = []
    if bold:
        values.append("<w:b/>")
    if italic:
        values.append("<w:i/>")
    if not values:
        return ""
    return f"<w:rPr>{''.join(values)}</w:rPr>"


def _xml_text(value: str) -> str:
    cleaned = "".join(
        character
        for character in value
        if character in "\t\n\r" or ord(character) >= 32
    )
    return escape(cleaned)


def _content_types_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" '
        'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '<Override PartName="/word/styles.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
        '<Override PartName="/docProps/core.xml" '
        'ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        '<Override PartName="/docProps/app.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
        "</Types>"
    )


def _package_relationships_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/>'
        '<Relationship Id="rId2" '
        'Type="http://schemas.openxmlformats.org/package/2006/relationships/'
        'metadata/core-properties" '
        'Target="docProps/core.xml"/>'
        '<Relationship Id="rId3" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
        'extended-properties" '
        'Target="docProps/app.xml"/>'
        "</Relationships>"
    )


def _core_properties_xml(*, title: str, subject: str | None, generated_at: str) -> str:
    subject_xml = f"<dc:subject>{_xml_text(subject)}</dc:subject>" if subject else ""
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/'
        'metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:dcmitype="http://purl.org/dc/dcmitype/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        f"<dc:title>{_xml_text(title)}</dc:title>"
        f"{subject_xml}"
        "<dc:creator>medical-audit-kb</dc:creator>"
        f'<dcterms:created xsi:type="dcterms:W3CDTF">{generated_at}</dcterms:created>'
        f'<dcterms:modified xsi:type="dcterms:W3CDTF">{generated_at}</dcterms:modified>'
        "</cp:coreProperties>"
    )


def _app_properties_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/'
        'extended-properties" '
        'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
        "<Application>medical-audit-kb</Application>"
        "</Properties>"
    )


def _styles_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:style w:type="paragraph" w:default="1" w:styleId="Normal">'
        '<w:name w:val="Normal"/></w:style>'
        '<w:style w:type="paragraph" w:styleId="Heading1">'
        '<w:name w:val="heading 1"/><w:basedOn w:val="Normal"/>'
        '<w:pPr><w:spacing w:before="240" w:after="120"/></w:pPr>'
        '<w:rPr><w:b/><w:sz w:val="32"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Heading2">'
        '<w:name w:val="heading 2"/><w:basedOn w:val="Normal"/>'
        '<w:pPr><w:spacing w:before="200" w:after="100"/></w:pPr>'
        '<w:rPr><w:b/><w:sz w:val="26"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Heading3">'
        '<w:name w:val="heading 3"/><w:basedOn w:val="Normal"/>'
        '<w:rPr><w:b/><w:sz w:val="22"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="ListParagraph">'
        '<w:name w:val="List Paragraph"/><w:basedOn w:val="Normal"/>'
        '<w:pPr><w:ind w:left="360"/></w:pPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Quote">'
        '<w:name w:val="Quote"/><w:basedOn w:val="Normal"/>'
        '<w:pPr><w:ind w:left="360"/><w:spacing w:before="120" w:after="120"/></w:pPr>'
        '<w:rPr><w:i/></w:rPr></w:style>'
        "</w:styles>"
    )
