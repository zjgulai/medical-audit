from pathlib import Path

from medical_audit_kb.ingestion.canonical_source_root import (
    build_canonical_source_root,
    canonical_document_key_and_version,
)


def test_canonical_document_key_and_version_strips_prefix_and_trailing_date() -> None:
    assert canonical_document_key_and_version("01074_中华人民共和国药品管理法2019-08-26.md") == (
        "中华人民共和国药品管理法",
        "2019-08-26",
    )
    assert canonical_document_key_and_version("护士条例_20200327.md") == (
        "护士条例",
        "2020-03-27",
    )
    assert canonical_document_key_and_version("安徽省实施《中华人民共和国献血法》办法_.md") == (
        "安徽省实施《中华人民共和国献血法》办法",
        "",
    )


def test_build_canonical_source_root_selects_latest_then_converted_source(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "normalized"
    output_root = tmp_path / "canonical"
    _write_text(source_root / "全量法律" / "护士条例_20200327.md", "raw nurse")
    _write_text(
        source_root
        / "全量法律"
        / "docx-converted"
        / "审计通用法律法规"
        / "01935_护士条例2020-03-27.md",
        "converted nurse",
    )
    _write_text(
        source_root
        / "全量法律"
        / "docx-converted"
        / "审计通用法律法规"
        / "01074_中华人民共和国药品管理法2015-04-24.md",
        "old drug law",
    )
    _write_text(
        source_root
        / "全量法律"
        / "docx-converted"
        / "审计通用法律法规"
        / "01074_中华人民共和国药品管理法2019-08-26.md",
        "new drug law",
    )
    _write_text(source_root / "全量法律" / "医疗器械监督管理条例_20241206.md", "raw device")
    _write_text(
        source_root
        / "全量法律"
        / "docx-converted"
        / "国家规章平台文档"
        / "医疗器械监督管理条例2021-02-09.md",
        "converted device",
    )

    result = build_canonical_source_root(source_root, output_root, execute=True)
    selected = {item.canonical_document_key: item for item in result.items if item.selected}
    suppressed = [item for item in result.items if not item.selected]

    assert result.discovered_file_count == 6
    assert result.selected_file_count == 3
    assert result.suppressed_file_count == 3
    assert result.duplicate_group_count == 3
    assert result.linked_file_count == 3
    assert (
        selected["护士条例"].relative_path
        == "全量法律/docx-converted/审计通用法律法规/01935_护士条例2020-03-27.md"
    )
    assert (
        selected["中华人民共和国药品管理法"].relative_path
        == "全量法律/docx-converted/审计通用法律法规/01074_中华人民共和国药品管理法2019-08-26.md"
    )
    assert (
        selected["医疗器械监督管理条例"].relative_path
        == "全量法律/医疗器械监督管理条例_20241206.md"
    )
    assert all(item.suppression_reason == "duplicate_or_superseded" for item in suppressed)
    assert (
        output_root
        / "全量法律"
        / "docx-converted"
        / "审计通用法律法规"
        / "01935_护士条例2020-03-27.md"
    ).is_symlink()
    assert not (output_root / "全量法律" / "护士条例_20200327.md").exists()


def test_build_canonical_source_root_dry_run_does_not_write_output_root(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "normalized"
    output_root = tmp_path / "canonical"
    _write_text(source_root / "全量法律" / "医保政策.md", "第一条 内容。")

    result = build_canonical_source_root(source_root, output_root, execute=False)

    assert result.selected_file_count == 1
    assert result.linked_file_count == 0
    assert not output_root.exists()


def _write_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path
