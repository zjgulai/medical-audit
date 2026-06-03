from pathlib import Path

from medical_audit_kb.indexing.incremental_plan import (
    ActiveSourceDocument,
    build_incremental_plan,
    render_incremental_plan_markdown,
)


def test_build_incremental_plan_compares_current_sources_with_active_documents(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "医保审核前期资料"
    stable = _write_text(source_root / "医保目录" / "stable.md", "稳定医保目录")
    modified = _write_text(source_root / "医保目录" / "modified.md", "新医保目录")
    _write_text(source_root / "全量法律" / "医保政策.md", "第一条 医保政策内容。")
    _write_binary(source_root / "风险负面清单" / "scan.png", b"png")

    active_documents = (
        ActiveSourceDocument(
            relative_path="医保目录/stable.md",
            sha256=_sha256(stable),
            source_collection="medical-insurance-catalog",
            file_ext=".md",
            size_bytes=stable.stat().st_size,
            chunk_count=3,
        ),
        ActiveSourceDocument(
            relative_path="医保目录/modified.md",
            sha256="0" * 64,
            source_collection="medical-insurance-catalog",
            file_ext=".md",
            size_bytes=modified.stat().st_size,
            chunk_count=4,
        ),
        ActiveSourceDocument(
            relative_path="风险负面清单/deleted.txt",
            sha256="1" * 64,
            source_collection="risk-negative-list",
            file_ext=".txt",
            size_bytes=10,
            chunk_count=2,
        ),
    )

    plan = build_incremental_plan(
        source_root,
        active_documents=active_documents,
        active_index_version_key="full-rebuild-active",
        active_source_package_version_key="source-package-active",
        package_version_key="source-package-next",
    )

    assert plan.active_document_count == 3
    assert plan.index_candidate_file_count == 3
    assert [item.relative_path for item in plan.added_files] == ["全量法律/医保政策.md"]
    assert [item.relative_path for item in plan.modified_files] == ["医保目录/modified.md"]
    assert [item.relative_path for item in plan.deleted_files] == ["风险负面清单/deleted.txt"]
    assert [item.relative_path for item in plan.unchanged_files] == ["医保目录/stable.md"]
    assert [item.relative_path for item in plan.pending_files] == ["风险负面清单/scan.png"]
    assert plan.estimated_reused_embeddings == 3
    assert plan.estimated_new_embeddings == 2
    assert plan.db_rows_to_deactivate == 6
    assert plan.db_rows_to_activate == 5
    assert plan.ready_for_incremental_build is True


def test_render_incremental_plan_markdown_includes_gate_and_counts(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "医保审核前期资料"
    _write_text(source_root / "医保目录" / "catalog.md", "医保目录")
    plan = build_incremental_plan(
        source_root,
        active_documents=(),
        active_index_version_key="full-rebuild-active",
        active_source_package_version_key="source-package-active",
        package_version_key="source-package-next",
    )

    markdown = render_incremental_plan_markdown(plan)

    assert "知识库增量更新计划报告" in markdown
    assert "总体状态：`PASS`" in markdown
    assert "| `added_files` | 1 |" in markdown
    assert "`source-package-next`" in markdown


def _write_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _write_binary(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
