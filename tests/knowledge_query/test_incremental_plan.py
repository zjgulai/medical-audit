import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

from medical_audit_kb.indexing.incremental_plan import (
    ActiveSourceDocument,
    IncrementalPlanError,
    build_incremental_plan,
    build_incremental_plan_from_database,
    load_active_source_documents,
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


def test_load_active_source_documents_filters_by_source_package_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package_id = UUID("00000000-0000-0000-0000-000000000001")
    cursor = RecordingCursor(
        fetchall_results=[
            [("active-index", "target-package", package_id)],
            [
                (
                    "docs/policy.md",
                    "a" * 64,
                    "management-general-admin",
                    ".md",
                    12,
                    3,
                )
            ],
        ]
    )
    monkeypatch.setitem(
        sys.modules,
        "psycopg",
        SimpleNamespace(connect=lambda _database_url: RecordingConnection(cursor)),
    )

    active = load_active_source_documents(
        "postgresql://user:pass@localhost/db",
        source_package_version_key="target-package",
    )

    assert active.index_version_key == "active-index"
    assert active.source_package_version_key == "target-package"
    assert active.documents[0].relative_path == "docs/policy.md"
    assert "spv.version_key = %s" in cursor.executed[0][0]
    assert cursor.executed[0][1] == ("target-package",)
    assert cursor.executed[1][1] == (package_id,)


def test_load_active_source_documents_requires_package_key_when_multiple_active(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cursor = RecordingCursor(
        fetchall_results=[
            [
                ("active-a", "package-a", UUID("00000000-0000-0000-0000-000000000001")),
                ("active-b", "package-b", UUID("00000000-0000-0000-0000-000000000002")),
            ],
        ]
    )
    monkeypatch.setitem(
        sys.modules,
        "psycopg",
        SimpleNamespace(connect=lambda _database_url: RecordingConnection(cursor)),
    )

    with pytest.raises(
        IncrementalPlanError,
        match="pass --active-source-package-version-key",
    ):
        load_active_source_documents("postgresql://user:pass@localhost/db")


def test_build_incremental_plan_from_database_keeps_active_and_target_keys_distinct(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_root = tmp_path / "医保审核前期资料"
    _write_text(source_root / "医保目录" / "catalog.md", "医保目录")

    def fake_load(
        database_url: str,
        *,
        source_package_version_key: str | None = None,
    ) -> object:
        assert database_url == "postgresql://user:pass@localhost/db"
        assert source_package_version_key == "source-package-active"
        return SimpleNamespace(
            index_version_key="full-rebuild-active",
            source_package_version_key="source-package-active",
            documents=(),
        )

    monkeypatch.setattr(
        "medical_audit_kb.indexing.incremental_plan.load_active_source_documents",
        fake_load,
    )

    plan = build_incremental_plan_from_database(
        source_root=source_root,
        database_url="postgresql://user:pass@localhost/db",
        package_version_key="source-package-next",
        active_source_package_version_key="source-package-active",
    )

    assert plan.active_source_package_version_key == "source-package-active"
    assert plan.source_package_version_key == "source-package-next"


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


class RecordingConnection:
    def __init__(self, cursor: "RecordingCursor") -> None:
        self._cursor = cursor

    def __enter__(self) -> "RecordingConnection":
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def cursor(self) -> "RecordingCursor":
        return self._cursor


class RecordingCursor:
    def __init__(self, *, fetchall_results: list[list[tuple[object, ...]]]) -> None:
        self._fetchall_results = list(fetchall_results)
        self.executed: list[tuple[str, tuple[object, ...] | None]] = []

    def __enter__(self) -> "RecordingCursor":
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def execute(self, query: str, params: tuple[object, ...] | None = None) -> object:
        self.executed.append((query, params))
        return None

    def fetchall(self) -> list[tuple[object, ...]]:
        return self._fetchall_results.pop(0)
