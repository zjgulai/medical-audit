from __future__ import annotations

import copy
import json
from importlib import util as importlib_util
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT_PATH = Path("scripts/check-mypy-non-regression.py")


def _load_module() -> ModuleType:
    spec = importlib_util.spec_from_file_location("check_mypy_non_regression", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib_util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _row(
    *,
    file: str = "scripts/legacy.py",
    line: int = 7,
    message: str = "Legacy typing debt",
) -> dict[str, object]:
    return {
        "file": file,
        "line": line,
        "column": 4,
        "end_line": line,
        "end_column": 12,
        "message": message,
        "hint": None,
        "code": "assignment",
        "severity": "error",
    }


def _baseline(module: ModuleType, rows: list[dict[str, object]]) -> dict[str, object]:
    summary = module.summarize_diagnostics(rows)
    files = copy.deepcopy(summary["files"])
    for evidence in files.values():
        evidence["source_sha256"] = "a" * 64
    return {
        "schema_version": 1,
        "policy": "exact-diagnostic-non-regression",
        "approved_base_sha": "1" * 40,
        "mypy_version": "mypy 2.1.0 (compiled: yes)",
        "command": list(module.LOGICAL_MYPY_COMMAND),
        "expected_exit_code": 1,
        "diagnostic_count": summary["diagnostic_count"],
        "diagnostics_sha256": summary["diagnostics_sha256"],
        "files": files,
    }


def _observation(module: ModuleType, rows: list[dict[str, object]]) -> dict[str, object]:
    summary = module.summarize_diagnostics(rows)
    return {
        "mypy_version": "mypy 2.1.0 (compiled: yes)",
        "mypy_exit_code": 1,
        "mypy_stderr": "",
        "diagnostic_count": summary["diagnostic_count"],
        "diagnostics_sha256": summary["diagnostics_sha256"],
        "files": summary["files"],
        "changed_paths": [],
        "current_source_sha256": {"scripts/legacy.py": "a" * 64},
        "base_source_sha256": {"scripts/legacy.py": "a" * 64},
        "base_is_ancestor": True,
    }


def test_exact_inherited_diagnostic_set_passes_only_as_labeled_exception() -> None:
    module = _load_module()
    rows = [_row()]

    report = module.evaluate_policy(_baseline(module, rows), _observation(module, rows))

    assert report["status"] == "pass"
    assert report["decision"] == "allowed-with-label"
    assert report["evidence_grade"] == "L2-fixture-or-dry-run"
    assert report["mypy_full_pass"] is False
    assert report["issues"] == []
    assert "mypy src scripts PASS" in report["forbidden_claims"]


def test_same_count_diagnostic_exchange_fails_closed() -> None:
    module = _load_module()
    baseline_rows = [_row(message="Known debt")]
    current_rows = [_row(message="New regression")]

    report = module.evaluate_policy(
        _baseline(module, baseline_rows),
        _observation(module, current_rows),
    )

    assert report["status"] == "fail"
    assert any("diagnostics_sha256" in issue for issue in report["issues"])


def test_missing_historical_diagnostic_requires_explicit_baseline_refresh() -> None:
    module = _load_module()
    baseline_rows = [_row(), _row(line=8, message="Second debt")]

    report = module.evaluate_policy(
        _baseline(module, baseline_rows),
        _observation(module, baseline_rows[:1]),
    )

    assert report["status"] == "fail"
    assert any("diagnostic_count" in issue for issue in report["issues"])


def test_changed_historical_debt_file_fails_closed() -> None:
    module = _load_module()
    rows = [_row()]
    observation = _observation(module, rows)
    observation["changed_paths"] = ["scripts/legacy.py"]

    report = module.evaluate_policy(_baseline(module, rows), observation)

    assert report["status"] == "fail"
    assert any("candidate-touched" in issue for issue in report["issues"])


@pytest.mark.parametrize(
    ("field", "value", "expected_fragment"),
    [
        ("mypy_version", "mypy 2.2.0 (compiled: yes)", "mypy_version"),
        ("mypy_exit_code", 2, "mypy_exit_code"),
        ("mypy_stderr", "configuration failed", "mypy_stderr"),
        ("base_is_ancestor", False, "base_is_ancestor"),
    ],
)
def test_tool_or_git_contract_drift_fails_closed(
    field: str,
    value: object,
    expected_fragment: str,
) -> None:
    module = _load_module()
    rows = [_row()]
    observation = _observation(module, rows)
    observation[field] = value

    report = module.evaluate_policy(_baseline(module, rows), observation)

    assert report["status"] == "fail"
    assert any(expected_fragment in issue for issue in report["issues"])


def test_source_hash_drift_in_current_or_base_fails_closed() -> None:
    module = _load_module()
    rows = [_row()]
    observation = _observation(module, rows)
    observation["base_source_sha256"] = {"scripts/legacy.py": "b" * 64}

    report = module.evaluate_policy(_baseline(module, rows), observation)

    assert report["status"] == "fail"
    assert any("base source hash" in issue for issue in report["issues"])


def test_parse_mypy_json_rejects_non_json_and_non_error_rows() -> None:
    module = _load_module()

    with pytest.raises(module.GateError, match="invalid JSON"):
        module.parse_mypy_json("not-json\n")

    note = _row()
    note["severity"] = "note"
    with pytest.raises(module.GateError, match="severity"):
        module.parse_mypy_json(json.dumps(note) + "\n")


def test_validate_baseline_rejects_unsafe_path_and_count_mismatch() -> None:
    module = _load_module()
    baseline = _baseline(module, [_row()])
    files = baseline["files"]
    files["../outside.py"] = files.pop("scripts/legacy.py")
    baseline["diagnostic_count"] = 2

    issues = module.validate_baseline(baseline)

    assert any("unsafe" in issue for issue in issues)
    assert any("sum" in issue for issue in issues)
