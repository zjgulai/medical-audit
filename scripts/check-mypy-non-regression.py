#!/usr/bin/env python3
"""Verify an exact, explicitly labeled Mypy historical-debt exception."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import cast

SCHEMA_VERSION = 1
POLICY = "exact-diagnostic-non-regression"
EVIDENCE_GRADE = "L2-fixture-or-dry-run"
LOGICAL_MYPY_COMMAND = (
    "mypy",
    "src",
    "scripts",
    "--output=json",
    "--no-error-summary",
)
DEFAULT_BASELINE = Path("configs/mypy-non-regression-baseline-v1.json")
BASELINE_KEYS = {
    "schema_version",
    "policy",
    "approved_base_sha",
    "mypy_version",
    "command",
    "expected_exit_code",
    "diagnostic_count",
    "diagnostics_sha256",
    "files",
}
FILE_EVIDENCE_KEYS = {
    "diagnostic_count",
    "diagnostics_sha256",
    "source_sha256",
}
DIAGNOSTIC_KEYS = {
    "file",
    "line",
    "column",
    "end_line",
    "end_column",
    "message",
    "hint",
    "code",
    "severity",
}


class GateError(RuntimeError):
    """Raised when evidence cannot be collected or parsed safely."""


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_sha(value: object, length: int) -> bool:
    return isinstance(value, str) and re.fullmatch(rf"[0-9a-f]{{{length}}}", value) is not None


def _safe_relative_path(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise GateError("path must be a non-empty string")
    if "\\" in value:
        raise GateError(f"unsafe path uses a backslash: {value!r}")
    path = PurePosixPath(value)
    unsafe_part = any(part in {"", ".", ".."} for part in path.parts)
    if path.is_absolute() or value != path.as_posix() or unsafe_part:
        raise GateError(f"unsafe relative path: {value!r}")
    return value


def _normalize_diagnostic(value: object, line_number: int) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise GateError(f"mypy JSON line {line_number} is not an object with string keys")
    row = cast(dict[str, object], value)
    if set(row) != DIAGNOSTIC_KEYS:
        raise GateError(
            f"mypy JSON line {line_number} has unexpected fields: "
            f"expected={sorted(DIAGNOSTIC_KEYS)!r} actual={sorted(row)!r}"
        )
    file_name = _safe_relative_path(row["file"])
    for key in ("line", "column", "end_line", "end_column"):
        if not _is_int(row[key]):
            raise GateError(f"mypy JSON line {line_number} field {key!r} is not an integer")
    for key in ("message", "code", "severity"):
        if not isinstance(row[key], str) or not row[key]:
            raise GateError(f"mypy JSON line {line_number} field {key!r} is invalid")
    if row["hint"] is not None and not isinstance(row["hint"], str):
        raise GateError(f"mypy JSON line {line_number} field 'hint' is invalid")
    if row["severity"] != "error":
        raise GateError(
            f"mypy JSON line {line_number} severity must be 'error', got {row['severity']!r}"
        )
    return {
        "file": file_name,
        "line": row["line"],
        "column": row["column"],
        "end_line": row["end_line"],
        "end_column": row["end_column"],
        "message": row["message"],
        "hint": row["hint"],
        "code": row["code"],
        "severity": row["severity"],
    }


def parse_mypy_json(stdout: str) -> list[dict[str, object]]:
    """Parse Mypy's JSON-lines output and reject contract drift."""
    rows: list[dict[str, object]] = []
    for line_number, line in enumerate(stdout.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value: object = json.loads(line)
        except json.JSONDecodeError as exc:
            raise GateError(f"mypy output line {line_number} is invalid JSON") from exc
        rows.append(_normalize_diagnostic(value, line_number))
    return rows


def _diagnostic_sort_key(row: dict[str, object]) -> tuple[object, ...]:
    return (
        row["file"],
        row["line"],
        row["column"],
        row["end_line"],
        row["end_column"],
        row["code"],
        row["message"],
        row["hint"] or "",
        row["severity"],
    )


def _canonical_diagnostics(rows: list[dict[str, object]]) -> str:
    return "\n".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        for row in sorted(rows, key=_diagnostic_sort_key)
    )


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def summarize_diagnostics(rows: list[dict[str, object]]) -> dict[str, object]:
    """Return deterministic global and per-file diagnostic fingerprints."""
    grouped: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        file_name = cast(str, row["file"])
        grouped.setdefault(file_name, []).append(row)
    files: dict[str, dict[str, object]] = {}
    for file_name, file_rows in sorted(grouped.items()):
        files[file_name] = {
            "diagnostic_count": len(file_rows),
            "diagnostics_sha256": _sha256_text(_canonical_diagnostics(file_rows)),
        }
    return {
        "diagnostic_count": len(rows),
        "diagnostics_sha256": _sha256_text(_canonical_diagnostics(rows)),
        "files": files,
    }


def _string_map(value: object) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    result: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, str):
            return None
        result[key] = item
    return result


def _object_map(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        return None
    return cast(dict[str, object], value)


def validate_baseline(baseline: dict[str, object]) -> list[str]:
    """Validate baseline shape without trusting it as executable configuration."""
    issues: list[str] = []
    if set(baseline) != BASELINE_KEYS:
        issues.append(
            f"baseline keys mismatch: expected={sorted(BASELINE_KEYS)!r} "
            f"actual={sorted(baseline)!r}"
        )
    if baseline.get("schema_version") != SCHEMA_VERSION:
        issues.append(f"schema_version must equal {SCHEMA_VERSION}")
    if baseline.get("policy") != POLICY:
        issues.append(f"policy must equal {POLICY!r}")
    if not _is_sha(baseline.get("approved_base_sha"), 40):
        issues.append("approved_base_sha must be a lowercase 40-character commit SHA")
    if not isinstance(baseline.get("mypy_version"), str) or not baseline.get("mypy_version"):
        issues.append("mypy_version must be a non-empty string")
    if baseline.get("command") != list(LOGICAL_MYPY_COMMAND):
        issues.append(f"command must equal {list(LOGICAL_MYPY_COMMAND)!r}")
    if baseline.get("expected_exit_code") != 1:
        issues.append("expected_exit_code must equal 1 for an explicit failing-command exception")
    if not _is_int(baseline.get("diagnostic_count")) or cast(
        int, baseline.get("diagnostic_count", 0)
    ) <= 0:
        issues.append("diagnostic_count must be a positive integer")
    if not _is_sha(baseline.get("diagnostics_sha256"), 64):
        issues.append("diagnostics_sha256 must be a lowercase SHA-256")

    files = _object_map(baseline.get("files"))
    if files is None or not files:
        issues.append("files must be a non-empty object")
        return issues

    total = 0
    for raw_path, raw_evidence in sorted(files.items()):
        try:
            path = _safe_relative_path(raw_path)
        except GateError as exc:
            issues.append(str(exc))
            path = raw_path
        evidence = _object_map(raw_evidence)
        if evidence is None:
            issues.append(f"file evidence for {path!r} must be an object")
            continue
        if set(evidence) != FILE_EVIDENCE_KEYS:
            issues.append(f"file evidence keys mismatch for {path!r}")
        count = evidence.get("diagnostic_count")
        if not _is_int(count) or cast(int, count) <= 0:
            issues.append(f"diagnostic_count for {path!r} must be positive")
        else:
            total += cast(int, count)
        if not _is_sha(evidence.get("diagnostics_sha256"), 64):
            issues.append(f"diagnostics_sha256 for {path!r} is invalid")
        if not _is_sha(evidence.get("source_sha256"), 64):
            issues.append(f"source_sha256 for {path!r} is invalid")
    if _is_int(baseline.get("diagnostic_count")) and total != baseline["diagnostic_count"]:
        issues.append(
            f"per-file diagnostic_count sum {total} does not equal "
            f"diagnostic_count {baseline['diagnostic_count']}"
        )
    return issues


def _expected_file_fingerprints(baseline: dict[str, object]) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    files = _object_map(baseline.get("files")) or {}
    for path, raw_evidence in files.items():
        evidence = _object_map(raw_evidence)
        if evidence is None:
            continue
        result[path] = {
            "diagnostic_count": evidence.get("diagnostic_count"),
            "diagnostics_sha256": evidence.get("diagnostics_sha256"),
        }
    return result


def evaluate_policy(
    baseline: dict[str, object], observation: dict[str, object]
) -> dict[str, object]:
    """Evaluate evidence without promoting the failing full command to PASS."""
    issues = [f"baseline: {issue}" for issue in validate_baseline(baseline)]

    comparisons = (
        ("mypy_version", observation.get("mypy_version"), baseline.get("mypy_version")),
        ("mypy_exit_code", observation.get("mypy_exit_code"), baseline.get("expected_exit_code")),
        ("diagnostic_count", observation.get("diagnostic_count"), baseline.get("diagnostic_count")),
        (
            "diagnostics_sha256",
            observation.get("diagnostics_sha256"),
            baseline.get("diagnostics_sha256"),
        ),
    )
    for field, actual, expected in comparisons:
        if actual != expected:
            issues.append(f"{field} mismatch: expected={expected!r} actual={actual!r}")

    if observation.get("mypy_stderr") != "":
        issues.append("mypy_stderr must be empty")
    if observation.get("base_is_ancestor") is not True:
        issues.append("base_is_ancestor must be true")
    if observation.get("targeted_mypy_exit_code", 0) != 0:
        issues.append(
            f"targeted_mypy_exit_code must be 0, got "
            f"{observation.get('targeted_mypy_exit_code')!r}"
        )
    if observation.get("targeted_mypy_stderr", "") != "":
        issues.append("targeted_mypy_stderr must be empty")

    expected_files = _expected_file_fingerprints(baseline)
    observed_files = _object_map(observation.get("files"))
    if observed_files != expected_files:
        issues.append("per-file diagnostic fingerprints mismatch")

    changed_paths_raw = observation.get("changed_paths")
    changed_paths = (
        {item for item in changed_paths_raw if isinstance(item, str)}
        if isinstance(changed_paths_raw, list)
        else set()
    )
    touched_debt = sorted(set(expected_files) & changed_paths)
    if touched_debt:
        issues.append(f"historical debt files are candidate-touched: {touched_debt!r}")

    current_hashes = _string_map(observation.get("current_source_sha256")) or {}
    base_hashes = _string_map(observation.get("base_source_sha256")) or {}
    baseline_files = _object_map(baseline.get("files")) or {}
    for path, raw_evidence in sorted(baseline_files.items()):
        evidence = _object_map(raw_evidence) or {}
        expected_hash = evidence.get("source_sha256")
        if current_hashes.get(path) != expected_hash:
            issues.append(f"current source hash mismatch for {path!r}")
        if base_hashes.get(path) != expected_hash:
            issues.append(f"base source hash mismatch for {path!r}")

    passed = not issues
    return {
        "status": "pass" if passed else "fail",
        "decision": "allowed-with-label" if passed else "blocked",
        "evidence_grade": EVIDENCE_GRADE,
        "policy": POLICY,
        "approved_base_sha": baseline.get("approved_base_sha"),
        "mypy_full_pass": False,
        "mypy_exit_code": observation.get("mypy_exit_code"),
        "diagnostic_count": observation.get("diagnostic_count"),
        "diagnostics_sha256": observation.get("diagnostics_sha256"),
        "diagnostic_files": sorted(expected_files),
        "changed_python_scripts": observation.get("changed_python_scripts", []),
        "targeted_mypy_exit_code": observation.get("targeted_mypy_exit_code", 0),
        "supported_claims": [
            "the exact approved historical diagnostic set is unchanged",
            "candidate-changed Python scripts pass targeted Mypy",
        ],
        "forbidden_claims": [
            "mypy src scripts PASS",
            "repository-wide Mypy clean",
        ],
        "issues": issues,
        "production_side_effect": "none",
        "provider_attempt_made": False,
        "database_write": False,
    }


def _run_text(command: list[str], repo_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )


def _git_changed_paths(repo_root: Path, base_sha: str) -> list[str]:
    tracked = _run_text(
        ["git", "diff", "--name-only", "--diff-filter=ACDMRTUXB", base_sha, "--"],
        repo_root,
    )
    if tracked.returncode != 0:
        raise GateError(f"git diff failed: {tracked.stderr.strip()}")
    untracked = _run_text(["git", "ls-files", "--others", "--exclude-standard"], repo_root)
    if untracked.returncode != 0:
        raise GateError(f"git ls-files failed: {untracked.stderr.strip()}")
    paths: set[str] = set()
    for line in [*tracked.stdout.splitlines(), *untracked.stdout.splitlines()]:
        if line.strip():
            paths.add(_safe_relative_path(line.strip()))
    return sorted(paths)


def _sha256_file(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise GateError(f"source path must be a regular non-symlink file: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_git_blob(repo_root: Path, base_sha: str, path: str) -> str:
    completed = subprocess.run(
        ["git", "show", f"{base_sha}:{path}"],
        cwd=repo_root,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        raise GateError(f"cannot read base blob for {path!r}: {stderr}")
    return hashlib.sha256(completed.stdout).hexdigest()


def collect_observation(
    baseline: dict[str, object], repo_root: Path
) -> dict[str, object]:
    """Collect current Git, Mypy and source-identity evidence."""
    base_sha = baseline.get("approved_base_sha")
    if not isinstance(base_sha, str):
        raise GateError("approved_base_sha is unavailable")

    top = _run_text(["git", "rev-parse", "--show-toplevel"], repo_root)
    if top.returncode != 0:
        raise GateError(f"git rev-parse failed: {top.stderr.strip()}")
    if Path(top.stdout.strip()).resolve() != repo_root.resolve():
        raise GateError("repo_root does not match git rev-parse --show-toplevel")

    ancestor = _run_text(["git", "merge-base", "--is-ancestor", base_sha, "HEAD"], repo_root)
    if ancestor.returncode not in {0, 1}:
        raise GateError(f"git merge-base failed: {ancestor.stderr.strip()}")

    changed_paths = _git_changed_paths(repo_root, base_sha)
    changed_scripts = sorted(
        path for path in changed_paths if path.startswith("scripts/") and path.endswith(".py")
    )

    version = _run_text([sys.executable, "-m", "mypy", "--version"], repo_root)
    if version.returncode != 0:
        raise GateError(f"mypy --version failed: {version.stderr.strip()}")
    mypy = _run_text(
        [sys.executable, "-m", "mypy", *LOGICAL_MYPY_COMMAND[1:]],
        repo_root,
    )
    rows = parse_mypy_json(mypy.stdout)
    summary = summarize_diagnostics(rows)

    if changed_scripts:
        targeted = _run_text([sys.executable, "-m", "mypy", *changed_scripts], repo_root)
        targeted_exit_code = targeted.returncode
        targeted_stdout = targeted.stdout.strip()
        targeted_stderr = targeted.stderr.strip()
    else:
        targeted_exit_code = 0
        targeted_stdout = "no changed Python scripts"
        targeted_stderr = ""

    files = _object_map(baseline.get("files")) or {}
    current_hashes: dict[str, str] = {}
    base_hashes: dict[str, str] = {}
    for path in files:
        safe_path = _safe_relative_path(path)
        current_hashes[safe_path] = _sha256_file(repo_root / safe_path)
        base_hashes[safe_path] = _sha256_git_blob(repo_root, base_sha, safe_path)

    return {
        "mypy_version": version.stdout.strip(),
        "mypy_exit_code": mypy.returncode,
        "mypy_stderr": mypy.stderr.strip(),
        **summary,
        "changed_paths": changed_paths,
        "changed_python_scripts": changed_scripts,
        "targeted_mypy_exit_code": targeted_exit_code,
        "targeted_mypy_stdout": targeted_stdout,
        "targeted_mypy_stderr": targeted_stderr,
        "current_source_sha256": current_hashes,
        "base_source_sha256": base_hashes,
        "base_is_ancestor": ancestor.returncode == 0,
    }


def _load_json_object(path: Path) -> dict[str, object]:
    try:
        value: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GateError(f"cannot read JSON object {path}: {exc}") from exc
    result = _object_map(value)
    if result is None:
        raise GateError(f"JSON root must be an object: {path}")
    return result


def _write_report(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify an exact, labeled Mypy historical-debt non-regression exception."
    )
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    repo_root = args.repo_root.resolve()
    baseline_path = (
        args.baseline if args.baseline.is_absolute() else repo_root / args.baseline
    )
    try:
        baseline = _load_json_object(baseline_path)
        baseline_issues = validate_baseline(baseline)
        if baseline_issues:
            raise GateError("; ".join(baseline_issues))
        observation = collect_observation(baseline, repo_root)
        report = evaluate_policy(baseline, observation)
    except GateError as exc:
        report = {
            "status": "fail",
            "decision": "blocked",
            "evidence_grade": EVIDENCE_GRADE,
            "policy": POLICY,
            "mypy_full_pass": False,
            "supported_claims": [],
            "forbidden_claims": [
                "mypy src scripts PASS",
                "repository-wide Mypy clean",
            ],
            "issues": [str(exc)],
            "production_side_effect": "none",
            "provider_attempt_made": False,
            "database_write": False,
        }
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    print(rendered)
    if args.output is not None:
        output_path = args.output if args.output.is_absolute() else repo_root / args.output
        _write_report(output_path, report)
    return 0 if report.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
