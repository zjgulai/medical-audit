import json
from pathlib import Path

from pytest import MonkeyPatch

from medical_audit_kb.cli import main
from medical_audit_kb.indexing.incremental_plan import (
    ActiveSourceDocument,
    build_incremental_plan,
)


def test_index_incremental_plan_command_writes_outputs(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    source_root = tmp_path / "医保审核前期资料"
    _write_text(source_root / "医保目录" / "catalog.md", "医保目录")
    report_path = tmp_path / "incremental-plan.md"
    json_path = tmp_path / "incremental-plan.json"
    monkeypatch.setenv("TEST_DATABASE_URL", "postgresql://user:pass@localhost/db")

    def fake_build_from_database(**kwargs: object) -> object:
        source_root_arg = kwargs["source_root"]
        package_version_key_arg = kwargs["package_version_key"]
        active_source_package_version_key_arg = kwargs["active_source_package_version_key"]
        assert isinstance(source_root_arg, (str, Path))
        assert isinstance(package_version_key_arg, str)
        assert active_source_package_version_key_arg == "source-package-active"
        return build_incremental_plan(
            source_root_arg,
            active_documents=(
                ActiveSourceDocument(
                    relative_path="医保目录/old.md",
                    sha256="1" * 64,
                    source_collection="medical-insurance-catalog",
                    file_ext=".md",
                    size_bytes=8,
                    chunk_count=2,
                ),
            ),
            active_index_version_key="full-rebuild-active",
            active_source_package_version_key="source-package-active",
            package_version_key=package_version_key_arg,
        )

    monkeypatch.setattr(
        "medical_audit_kb.cli.build_incremental_plan_from_database",
        fake_build_from_database,
    )

    exit_code = main(
        [
            "index-incremental-plan",
            "--source-root",
            str(source_root),
            "--package-version-key",
            "source-package-next",
            "--active-source-package-version-key",
            "source-package-active",
            "--database-url-env",
            "TEST_DATABASE_URL",
            "--output",
            str(report_path),
            "--json-output",
            str(json_path),
        ]
    )

    body = json.loads(json_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert "知识库增量更新计划报告" in report_path.read_text(encoding="utf-8")
    assert body["active_index_version_key"] == "full-rebuild-active"
    assert body["source_package_version_key"] == "source-package-next"
    assert body["counts"]["added_files"] == 1
    assert body["counts"]["deleted_files"] == 1


def _write_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path
