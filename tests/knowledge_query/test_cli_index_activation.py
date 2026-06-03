import json
from pathlib import Path

from pytest import MonkeyPatch

from medical_audit_kb.cli import main
from medical_audit_kb.indexing.index_activation import (
    IndexActivationResult,
    IndexRollbackResult,
)


def test_index_activate_command_writes_outputs(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    report_path = tmp_path / "activate.md"
    json_path = tmp_path / "activate.json"
    monkeypatch.setenv("TEST_DATABASE_URL", "postgresql://user:pass@localhost/db")

    monkeypatch.setattr(
        "medical_audit_kb.cli.activate_index_version",
        lambda **kwargs: IndexActivationResult(
            index_version_key=str(kwargs["index_version_key"]),
            vector_provider="openai",
            vector_model="kimi-for-coding",
            previous_status="candidate",
            deactivated_index_version_keys=("active-old",),
        ),
    )

    exit_code = main(
        [
            "index-activate",
            "--index-version-key",
            "candidate-next",
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
    assert "知识库索引版本激活报告" in report_path.read_text(encoding="utf-8")
    assert body["index_version_key"] == "candidate-next"
    assert body["deactivated_index_version_keys"] == ["active-old"]


def test_index_rollback_command_writes_outputs(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    report_path = tmp_path / "rollback.md"
    json_path = tmp_path / "rollback.json"
    monkeypatch.setenv("TEST_DATABASE_URL", "postgresql://user:pass@localhost/db")

    monkeypatch.setattr(
        "medical_audit_kb.cli.rollback_index_version",
        lambda **kwargs: IndexRollbackResult(
            index_version_key=str(kwargs["index_version_key"]),
            vector_provider="openai",
            vector_model="kimi-for-coding",
            previous_status="inactive",
            deactivated_index_version_keys=("active-current",),
        ),
    )

    exit_code = main(
        [
            "index-rollback",
            "--index-version-key",
            "active-previous",
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
    assert "知识库索引版本回滚报告" in report_path.read_text(encoding="utf-8")
    assert body["index_version_key"] == "active-previous"
    assert body["deactivated_index_version_keys"] == ["active-current"]
