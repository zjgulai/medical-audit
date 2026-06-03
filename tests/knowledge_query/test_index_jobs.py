from pathlib import Path

from openpyxl import Workbook
from pytest import MonkeyPatch

from medical_audit_kb.domain.constants import IndexJobType
from medical_audit_kb.indexing.index_jobs import (
    ManifestIndexSnapshot,
    compare_snapshots,
)
from medical_audit_kb.ingestion.inventory import build_source_package_manifest
from medical_audit_kb.ingestion.pipeline import KnowledgeIndexPipeline


def test_full_rebuild_outputs_version_and_file_statistics(tmp_path: Path) -> None:
    source_root = tmp_path / "医保审核前期资料"
    _write_text(source_root / "医保目录" / "catalog.md", "# 目录\n医保目录内容")
    _write_xlsx(source_root / "智能监管“两库”规则和知识点" / "rules.xlsx")
    _write_binary(source_root / "风险负面清单" / "scan.png", b"png")

    result = KnowledgeIndexPipeline().run_full_rebuild(
        source_root,
        package_version_key="full-package",
    )

    assert result.summary.job_type == IndexJobType.FULL_REBUILD
    assert result.summary.index_version_key.startswith("full-rebuild-")
    assert result.summary.source_package_version_key == "full-package"
    assert result.summary.discovered_file_count == 3
    assert result.summary.index_candidate_file_count == 2
    assert result.summary.indexed_file_count == 2
    assert result.summary.chunk_count == 2
    assert result.summary.pending_file_count == 1
    assert result.summary.failed_file_count == 0
    assert result.summary.added_file_count == 2
    assert result.summary.comparison == {
        "before_index_candidate_file_count": 0,
        "after_index_candidate_file_count": 2,
    }


def test_incremental_index_detects_added_modified_deleted_and_unchanged_files(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "医保审核前期资料"
    catalog = _write_text(source_root / "医保目录" / "catalog.md", "# 目录\n旧内容")
    deleted = _write_text(source_root / "风险负面清单" / "risk.txt", "风险清单")
    _write_text(source_root / "医保目录" / "stable.md", "# 稳定\n内容")
    previous_manifest = build_source_package_manifest(source_root, version_key="before")
    previous_snapshot = ManifestIndexSnapshot.from_manifest(previous_manifest)

    catalog.write_text("# 目录\n新内容", encoding="utf-8")
    deleted.unlink()
    _write_text(source_root / "全量法律" / "医保政策.md", "第一条 医保政策内容。")

    result = KnowledgeIndexPipeline().run_incremental(
        source_root,
        previous_snapshot=previous_snapshot,
        package_version_key="after",
    )

    assert result.summary.job_type == IndexJobType.INCREMENTAL
    assert result.summary.before_package_version_key == "before"
    assert result.summary.source_package_version_key == "after"
    assert result.summary.added_file_count == 1
    assert result.summary.modified_file_count == 1
    assert result.summary.deleted_file_count == 1
    assert result.summary.unchanged_file_count == 1
    assert result.summary.indexed_file_count == 2
    assert result.summary.chunk_count == 2
    assert result.diff is not None
    assert [file.relative_path for file in result.diff.added] == ["全量法律/医保政策.md"]
    assert [file.relative_path for file in result.diff.modified] == ["医保目录/catalog.md"]
    assert [file.relative_path for file in result.diff.deleted] == ["风险负面清单/risk.txt"]
    assert [file.relative_path for file in result.diff.unchanged] == ["医保目录/stable.md"]


def test_compare_snapshots_uses_only_index_candidates(tmp_path: Path) -> None:
    source_root = tmp_path / "医保审核前期资料"
    _write_text(source_root / "全量法律" / "医保政策.md", "医保政策")
    _write_text(source_root / "全量法律" / "行政复议法.md", "非范围")
    previous = ManifestIndexSnapshot.from_manifest(
        build_source_package_manifest(source_root, version_key="before")
    )

    _write_text(source_root / "全量法律" / "行政复议法.md", "非范围修改后")
    current = ManifestIndexSnapshot.from_manifest(
        build_source_package_manifest(source_root, version_key="after")
    )

    diff = compare_snapshots(previous, current)

    assert diff.counts_by_type() == {
        "added": 0,
        "modified": 0,
        "deleted": 0,
        "unchanged": 1,
    }


def test_retry_file_indexes_single_repaired_file(tmp_path: Path) -> None:
    source_root = tmp_path / "医保审核前期资料"
    _write_text(source_root / "医保目录" / "repaired.md", "# 修复\n医保目录内容")
    _write_text(source_root / "医保目录" / "other.md", "# 其他\n不应重试")

    result = KnowledgeIndexPipeline().retry_file(
        source_root,
        relative_path="医保目录/repaired.md",
        package_version_key="retry-package",
    )

    assert result.summary.job_type == IndexJobType.RETRY_FILE
    assert result.summary.retried_file == "医保目录/repaired.md"
    assert result.summary.indexed_file_count == 1
    assert result.summary.chunk_count == 1
    assert [file.relative_path for file in result.file_results] == ["医保目录/repaired.md"]
    assert result.summary.comparison == {"retried_file_found": 1}


def test_retry_file_reports_missing_target_as_failure(tmp_path: Path) -> None:
    source_root = tmp_path / "医保审核前期资料"
    _write_text(source_root / "医保目录" / "other.md", "# 其他\n内容")

    result = KnowledgeIndexPipeline().retry_file(
        source_root,
        relative_path="医保目录/missing.md",
        package_version_key="retry-missing",
    )

    assert result.summary.failed_file_count == 1
    assert result.summary.indexed_file_count == 0
    assert result.failed_files[0].relative_path == "医保目录/missing.md"
    assert result.summary.comparison == {"retried_file_found": 0}


def test_pipeline_counts_failed_and_pending_files(tmp_path: Path) -> None:
    source_root = tmp_path / "医保审核前期资料"
    _write_text(source_root / "医保目录" / "corrupted.pdf", "not a real pdf")
    _write_binary(source_root / "风险负面清单" / "scan.png", b"png")

    result = KnowledgeIndexPipeline().run_full_rebuild(
        source_root,
        package_version_key="failure-package",
    )

    assert result.summary.discovered_file_count == 2
    assert result.summary.index_candidate_file_count == 1
    assert result.summary.indexed_file_count == 0
    assert result.summary.failed_file_count == 1
    assert result.summary.pending_file_count == 1
    assert result.failed_files[0].relative_path == "医保目录/corrupted.pdf"
    assert result.pending_files[0].relative_path == "风险负面清单/scan.png"


def test_pipeline_isolates_unexpected_chunking_failure(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    source_root = tmp_path / "医保审核前期资料"
    _write_text(source_root / "医保目录" / "catalog.md", "# 目录\n医保目录内容")

    def fail_chunking(*_args: object, **_kwargs: object) -> None:
        raise ValueError("bad chunk")

    monkeypatch.setattr(
        "medical_audit_kb.ingestion.pipeline.chunk_extraction_result",
        fail_chunking,
    )

    result = KnowledgeIndexPipeline().run_full_rebuild(
        source_root,
        package_version_key="failure-package",
    )

    assert result.summary.discovered_file_count == 1
    assert result.summary.index_candidate_file_count == 1
    assert result.summary.indexed_file_count == 0
    assert result.summary.failed_file_count == 1
    assert result.failed_files[0].relative_path == "医保目录/catalog.md"
    assert "bad chunk" in result.failed_files[0].error_summary


def _write_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _write_binary(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
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
