#!/usr/bin/env python3
"""Validate medical_audit documentation contracts without network access."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

from medical_audit_kb.api.app import API_V1_PREFIX, ApiState, create_app

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
OPENAPI_METHODS = frozenset({"delete", "get", "head", "options", "patch", "post", "put"})
API_OPERATION_ROW_RE = re.compile(
    rf"^\|\s*(DELETE|GET|HEAD|OPTIONS|PATCH|POST|PUT)\s*\|\s*`({API_V1_PREFIX}[^`]*)`\s*\|",
    re.MULTILINE,
)
PRODUCTION_EVIDENCE_VALUES = {
    "L3 shell pass",
    "blocked_by_access_mode",
    "not_production_verified",
    "sample_only",
    "not_run",
}
CURRENT_STATE_SECTIONS = (
    ("README.md", "## 当前候选状态", "## 当前材料的权威层级"),
    ("docs/README.md", "# medical_audit 文档入口", "## 历史文档状态"),
    (
        "docs/product/product-development-plan-medical-audit-stable.md",
        "### 1.6 2026-08-14 exact-head CI 外部观察（当前）",
        "### 1.5 2026-08-14 Draft PR 与本地收口基线（历史：push 前）",
    ),
    (
        "docs/workflows/workflow-project-state-and-debt-register-stable.md",
        "### 2.6 2026-08-14 exact-head 交付观察（当前）",
        "### 2.5 2026-08-14 Draft PR 与文档收口快照（历史：push 前）",
    ),
    (
        "docs/architecture/architecture-frontend-boundary-jinja-vs-next-20260623.md",
        "## 5. 当前证据",
        None,
    ),
    (
        "docs/testing/production-feature-acceptance-matrix-stable.md",
        "# medical_audit 本地与生产功能验收矩阵",
        "## 页面与功能",
    ),
    (
        "drafts/analysis/project-reanalysis-and-gap-audit-20260813.md",
        "# medical_audit 全量复盘、差异与清理审计",
        "## 提交前与生产历史事实",
    ),
    (
        ".kiro/plan/task_plan.md",
        "## 2026-08-14 exact-head 交付观察与状态合同修复",
        "## 2026-08-14 PR #275 文档与 P2 收口计划（历史：push 前）",
    ),
    (
        ".kiro/plan/progress.md",
        "## 2026-08-14 exact-head 观察与状态合同修复进展",
        "## 2026-08-14 PR #275 文档与 P2 收口进展（历史：push 前）",
    ),
    (
        ".kiro/plan/findings.md",
        "## 2026-08-14 exact-head 交付审计与状态合同发现",
        "## 2026-08-14 PR #275 交付审计与收口发现（历史：push 前）",
    ),
)
VOLATILE_CURRENT_STATE_PHRASES = (
    "尚未推送",
    "仍未推送",
    "未提交、未推送",
    "local-commit-not-pushed",
    "push=false",
    "pr_mutation=false",
    "与本地 `HEAD` 一致",
    "当前远端 head",
)
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
        _check_openapi_operation_coverage(api_doc, api_text, errors)

    _check_playbook_sections(playbook, errors)
    _check_production_evidence(matrix, errors)
    _check_current_state_evidence(errors)
    _check_dated_current_state_sections(errors)

    for item in warnings:
        print(f"WARN: {item}")
    for item in errors:
        print(f"ERROR: {item}")
    print(
        "documentation contract summary: "
        f"tracked={len(tracked_markdown)} "
        f"api_operations={len(_canonical_openapi_operations())} "
        f"errors={len(errors)} warnings={len(warnings)}"
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
        "repository_observed_at",
        "repository_observed_sha",
        "repository_observed_sha_role",
        "delivery_observed_at",
        "delivery_observed_pr_head",
        "delivery_observed_ci_run",
        "delivery_observed_ci_conclusion",
        "delivery_status_model",
        "production_observed_at",
        "production_git_sha",
        "evidence_grade",
        "production_side_effect",
    ):
        if not fields.get(field):
            errors.append(f"{report.relative_to(REPO_ROOT)}: missing evidence field `{field}`")
    for field in ("repository_observed_sha", "delivery_observed_pr_head", "production_git_sha"):
        if not re.fullmatch(r"[0-9a-f]{40}", fields.get(field, "")):
            errors.append(
                f"{report.relative_to(REPO_ROOT)}: {field} must be a 40-character lowercase SHA"
            )
    if fields.get("repository_observed_sha_role") != "precommit-base":
        errors.append(
            f"{report.relative_to(REPO_ROOT)}: "
            "repository_observed_sha_role must be `precommit-base`"
        )
    if fields.get("delivery_status_model") != "dated-external-observations":
        errors.append(
            f"{report.relative_to(REPO_ROOT)}: "
            "delivery_status_model must be `dated-external-observations`"
        )
    if not re.fullmatch(r"[1-9][0-9]*", fields.get("delivery_observed_ci_run", "")):
        errors.append(
            f"{report.relative_to(REPO_ROOT)}: delivery_observed_ci_run must be numeric"
        )
    if fields.get("delivery_observed_ci_conclusion") not in {
        "cancelled",
        "failure",
        "pending",
        "success",
    }:
        errors.append(
            f"{report.relative_to(REPO_ROOT)}: invalid delivery_observed_ci_conclusion"
        )


def _check_dated_current_state_sections(errors: list[str]) -> None:
    for relative, start_marker, end_marker in CURRENT_STATE_SECTIONS:
        path = REPO_ROOT / relative
        if not path.is_file():
            errors.append(f"missing current-state document: {relative}")
            continue
        text = path.read_text(encoding="utf-8")
        if start_marker not in text:
            errors.append(f"{relative}: missing current-state marker `{start_marker}`")
            continue
        section = text.split(start_marker, 1)[1]
        if end_marker is not None:
            if end_marker not in section:
                errors.append(f"{relative}: missing historical boundary `{end_marker}`")
                continue
            section = section.split(end_marker, 1)[0]
        if "外部观察" not in section:
            errors.append(
                f"{relative}: current-state section must use a dated external observation"
            )
        for phrase in VOLATILE_CURRENT_STATE_PHRASES:
            if phrase in section:
                errors.append(
                    f"{relative}: current-state section contains volatile phrase `{phrase}`"
                )


def _canonical_openapi_operations() -> set[tuple[str, str]]:
    placeholder = cast(Any, object())
    state = ApiState(
        settings=placeholder,
        index_pipeline=placeholder,
        preview_resolver=placeholder,
    )
    schema = create_app(state, api_access_mode="public-shell-readonly").openapi()
    return {
        (method.upper(), path)
        for path, path_item in schema["paths"].items()
        if path.startswith(API_V1_PREFIX)
        for method in path_item
        if method in OPENAPI_METHODS
    }


def _check_openapi_operation_coverage(
    path: Path,
    text: str,
    errors: list[str],
) -> None:
    expected = _canonical_openapi_operations()
    documented = {(method, route) for method, route in API_OPERATION_ROW_RE.findall(text)}
    relative = path.relative_to(REPO_ROOT)
    for method, route in sorted(expected - documented):
        errors.append(f"{relative}: missing OpenAPI operation `{method} {route}`")
    for method, route in sorted(documented - expected):
        errors.append(f"{relative}: stale OpenAPI operation `{method} {route}`")


if __name__ == "__main__":
    sys.exit(main())
