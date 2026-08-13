#!/usr/bin/env python3
"""Validate medical_audit documentation contracts without network access."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTMATTER_FIELDS = (
    "title",
    "doc_type",
    "module",
    "status",
    "created",
    "updated",
    "owner",
    "source",
)
AUTHORITATIVE_DOCS = (
    "docs/README.md",
    "docs/architecture/architecture-system-overview-stable.md",
    "docs/api/api-medical-audit-platform-v1-stable.md",
    "docs/playbooks/user-playbook-medical-audit-v1-stable.md",
    "docs/playbooks/admin-operations-playbook-stable.md",
    "docs/testing/production-feature-acceptance-matrix-stable.md",
    "docs/style/chinese-technical-writing-style.md",
    "drafts/analysis/project-reanalysis-and-gap-audit-20260813.md",
)
INDEPENDENT_ROUTES = (
    "/",
    "/login",
    "/medical-audit",
    "/fund-compliance",
    "/fund-compliance/review",
    "/chat",
    "/agents",
    "/agent-market",
    "/analytics",
    "/projects",
    "/audit-cockpit",
    "/documents",
    "/ocr",
    "/knowledge-base",
    "/graph",
    "/rules",
    "/reports",
    "/remediation",
    "/archive",
    "/guided-check",
)
ALIAS_ROUTES = ("/workspace", "/findings", "/knowledge-query")
API_FAMILIES = (
    "/health",
    "/deployment/metadata",
    "/auth",
    "/query",
    "/chat",
    "/agents",
    "/agent-market",
    "/analytics",
    "/documents",
    "/ocr",
    "/contract-audits",
    "/knowledge-base",
    "/projects",
    "/audit-findings",
    "/review-tasks",
    "/reports",
    "/remediation",
    "/graph",
    "/rules",
    "/archive",
    "/index",
    "/audit/logs",
    "/operation/logs",
    "/preview",
)
PRODUCTION_EVIDENCE_VALUES = {
    "L3 shell pass",
    "blocked_by_access_mode",
    "not_production_verified",
    "sample_only",
    "not_run",
}
LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
HEADING_RE = re.compile(r"^(#{1,6})\s+\S")


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []
    tracked_markdown = _tracked_markdown()

    for relative in AUTHORITATIVE_DOCS:
        if not (REPO_ROOT / relative).is_file():
            errors.append(f"missing authoritative document: {relative}")

    for path in tracked_markdown:
        relative = path.relative_to(REPO_ROOT).as_posix()
        _check_frontmatter(path, relative, errors)
        _check_links(path, relative, errors)

    for relative in AUTHORITATIVE_DOCS:
        path = REPO_ROOT / relative
        if path.is_file():
            _check_headings(path, relative, errors)

    playbook = REPO_ROOT / "docs/playbooks/user-playbook-medical-audit-v1-stable.md"
    matrix = REPO_ROOT / "docs/testing/production-feature-acceptance-matrix-stable.md"
    for path in (playbook, matrix):
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            for route in (*INDEPENDENT_ROUTES, *ALIAS_ROUTES):
                if f"`{route}`" not in text:
                    errors.append(
                        f"{path.relative_to(REPO_ROOT)}: missing route contract `{route}`"
                    )

    api_doc = REPO_ROOT / "docs/api/api-medical-audit-platform-v1-stable.md"
    if api_doc.is_file():
        api_text = api_doc.read_text(encoding="utf-8")
        for family in API_FAMILIES:
            if family not in api_text:
                errors.append(f"{api_doc.relative_to(REPO_ROOT)}: missing API family `{family}`")

    _check_playbook_sections(playbook, errors)
    _check_production_evidence(matrix, errors)
    _check_current_state_evidence(errors)

    for item in warnings:
        print(f"WARN: {item}")
    for item in errors:
        print(f"ERROR: {item}")
    print(
        "documentation contract summary: "
        f"tracked={len(tracked_markdown)} errors={len(errors)} warnings={len(warnings)}"
    )
    return 2 if errors else 0


def _tracked_markdown() -> list[Path]:
    tracked = subprocess.run(
        ["git", "ls-files", "docs/**/*.md", "drafts/**/*.md"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    untracked = subprocess.run(
        [
            "git",
            "ls-files",
            "--others",
            "--exclude-standard",
            "docs/**/*.md",
            "drafts/**/*.md",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    paths = {*tracked.stdout.splitlines(), *untracked.stdout.splitlines()}
    return [REPO_ROOT / line for line in sorted(paths) if line]


def _frontmatter(path: Path) -> tuple[dict[str, str], int] | None:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    fields: dict[str, str] = {}
    for index, line in enumerate(lines[1:], start=2):
        if line.strip() in {"---", "..."}:
            return fields, index
        match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_-]*):\s*(.*)$", line)
        if match:
            fields[match.group(1)] = match.group(2).strip()
    return None


def _check_frontmatter(path: Path, relative: str, errors: list[str]) -> None:
    parsed = _frontmatter(path)
    if parsed is None:
        errors.append(f"{relative}: missing or invalid frontmatter")
        return
    fields, _ = parsed
    for field in FRONTMATTER_FIELDS:
        if not fields.get(field):
            errors.append(f"{relative}: missing frontmatter field `{field}`")


def _check_headings(path: Path, relative: str, errors: list[str]) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    in_fence = False
    levels: list[int] = []
    for line in lines:
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = HEADING_RE.match(line)
        if match:
            levels.append(len(match.group(1)))
    if levels.count(1) != 1:
        errors.append(f"{relative}: expected exactly one H1, found {levels.count(1)}")
    for previous, current in zip(levels, levels[1:], strict=False):
        if current > previous + 1:
            errors.append(f"{relative}: heading level jumps from H{previous} to H{current}")


def _check_links(path: Path, relative: str, errors: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    for raw_target in LINK_RE.findall(text):
        target = raw_target.strip().strip("<>").split(" ", 1)[0]
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        target_path = target.split("#", 1)[0].split("?", 1)[0]
        if not target_path:
            continue
        resolved = (
            Path(target_path)
            if Path(target_path).is_absolute()
            else (path.parent / target_path).resolve()
        )
        if not resolved.exists():
            errors.append(f"{relative}: broken local link `{target}`")


def _check_playbook_sections(path: Path, errors: list[str]) -> None:
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    required_labels = (
        "适用角色",
        "前置条件",
        "页面与 API",
        "操作步骤",
        "预期结果",
        "副作用",
        "错误码",
        "恢复方法",
        "已知限制",
        "本地证据",
        "生产证据",
    )
    feature_sections = re.split(r"\n## \d+\. ", text)[1:]
    if len(feature_sections) != 22:
        errors.append(f"{path.relative_to(REPO_ROOT)}: expected 22 feature sections")
    for index, section in enumerate(feature_sections, start=1):
        for label in required_labels:
            if f"**{label}**" not in section:
                errors.append(
                    f"{path.relative_to(REPO_ROOT)}: section {index} missing `{label}`"
                )


def _check_production_evidence(path: Path, errors: list[str]) -> None:
    if not path.is_file():
        return
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if "production_evidence=" not in line:
            continue
        value = line.split("production_evidence=", 1)[1].split("`", 1)[0].strip()
        if value not in PRODUCTION_EVIDENCE_VALUES:
            relative = path.relative_to(REPO_ROOT)
            errors.append(
                f"{relative}:{line_number}: invalid production evidence `{value}`"
            )


def _check_current_state_evidence(errors: list[str]) -> None:
    report = REPO_ROOT / "drafts/analysis/project-reanalysis-and-gap-audit-20260813.md"
    if not report.is_file():
        return
    parsed = _frontmatter(report)
    assert parsed is not None
    fields, _ = parsed
    for field in (
        "observed_at",
        "local_git_sha",
        "production_git_sha",
        "evidence_grade",
        "production_side_effect",
    ):
        if not fields.get(field):
            errors.append(f"{report.relative_to(REPO_ROOT)}: missing evidence field `{field}`")


if __name__ == "__main__":
    sys.exit(main())
