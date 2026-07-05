#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

DEFAULT_DATA_ROOT = "data"
DEFAULT_TAXONOMY = "configs/knowledge-base-taxonomy-v1.yaml"
DEFAULT_INCREMENTAL_PLAN = (
    "tmp/outputs/knowledge-query-national-regulation-incremental-plan-20260615.json"
)
DEFAULT_IMPORT_RESULT = (
    "tmp/outputs/knowledge-query-national-regulation-stable-incremental-pgvector-import-execute-20260615.json"
)
DEFAULT_MANIFEST_CSV = "tmp/outputs/knowledge-base-taxonomy-manifest-latest.csv"
DEFAULT_SUMMARY_JSON = "tmp/outputs/knowledge-base-taxonomy-summary-latest.json"
DEFAULT_REPORT = "drafts/analysis/knowledge-base-taxonomy-manifest-report-draft-20260702.md"

HASH_CHUNK_SIZE = 1024 * 1024
TEXT_SAMPLE_LIMIT = 1200
SYSTEM_FILENAMES = {".DS_Store", ".gitkeep"}
UNSUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".rar", ".zip", ".7z"}


@dataclass(frozen=True, slots=True)
class NamespaceRule:
    namespace_key: str
    primary_key: str
    primary_name: str
    secondary_name: str
    description: str
    priority: int
    path_keywords: tuple[str, ...]
    title_keywords: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class IndexedEvidence:
    source_root: str
    indexed_paths: frozenset[str]
    pending_paths: frozenset[str]
    ignored_paths: frozenset[str]
    failed_paths: frozenset[str]
    ignored_reasons: Mapping[str, str]
    pending_reasons: Mapping[str, str]
    indexed_sha256_to_path: Mapping[str, str]
    active_index_version_key: str | None
    source_package_version_key: str | None
    import_success: bool
    imported_index_version_key: str | None


@dataclass(frozen=True, slots=True)
class ManifestRow:
    relative_path: str
    source_root_relative_path: str
    file_name: str
    file_ext: str
    size_bytes: int
    sha256: str
    primary_category: str
    secondary_category: str
    namespace_key: str
    namespace_confidence: str
    matched_terms: str
    extraction_status: str
    already_indexed: bool
    needs_manual_review: bool
    recommended_action: str

    def to_csv_row(self) -> dict[str, object]:
        return {
            "relative_path": self.relative_path,
            "source_root_relative_path": self.source_root_relative_path,
            "file_name": self.file_name,
            "file_ext": self.file_ext,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "primary_category": self.primary_category,
            "secondary_category": self.secondary_category,
            "namespace_key": self.namespace_key,
            "namespace_confidence": self.namespace_confidence,
            "matched_terms": self.matched_terms,
            "extraction_status": self.extraction_status,
            "already_indexed": str(self.already_indexed).lower(),
            "needs_manual_review": str(self.needs_manual_review).lower(),
            "recommended_action": self.recommended_action,
        }


def main() -> int:
    args = _parse_args()
    data_root = Path(args.data_root)
    taxonomy_path = Path(args.taxonomy)
    incremental_plan_path = Path(args.incremental_plan)
    import_result_path = Path(args.import_result)
    manifest_csv = Path(args.manifest_csv)
    summary_json = Path(args.summary_json)
    report_path = Path(args.report)

    taxonomy = _load_taxonomy(taxonomy_path)
    evidence = _load_indexed_evidence(incremental_plan_path, import_result_path)
    rows = _build_manifest_rows(data_root=data_root, taxonomy=taxonomy, evidence=evidence)
    summary = _build_summary(
        rows=rows,
        data_root=data_root,
        taxonomy_path=taxonomy_path,
        incremental_plan_path=incremental_plan_path,
        import_result_path=import_result_path,
        evidence=evidence,
    )

    manifest_csv.parent.mkdir(parents=True, exist_ok=True)
    summary_json.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    _write_manifest_csv(manifest_csv, rows)
    summary_json.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    report_path.write_text(_render_markdown_report(summary), encoding="utf-8")

    print(
        json.dumps(
            _stdout_summary(summary, manifest_csv, summary_json, report_path),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a full data/ manifest with primary/secondary knowledge-base taxonomy.",
    )
    parser.add_argument("--data-root", default=DEFAULT_DATA_ROOT)
    parser.add_argument("--taxonomy", default=DEFAULT_TAXONOMY)
    parser.add_argument("--incremental-plan", default=DEFAULT_INCREMENTAL_PLAN)
    parser.add_argument("--import-result", default=DEFAULT_IMPORT_RESULT)
    parser.add_argument("--manifest-csv", default=DEFAULT_MANIFEST_CSV)
    parser.add_argument("--summary-json", default=DEFAULT_SUMMARY_JSON)
    parser.add_argument("--report", default=DEFAULT_REPORT)
    return parser.parse_args()


def _load_taxonomy(path: Path) -> tuple[NamespaceRule, ...]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("taxonomy config must be a mapping")
    primary_categories = raw.get("primary_categories")
    if not isinstance(primary_categories, dict):
        raise ValueError("taxonomy config missing primary_categories")

    rules: list[NamespaceRule] = []
    for primary_key, primary_payload in primary_categories.items():
        if not isinstance(primary_key, str) or not isinstance(primary_payload, dict):
            raise ValueError("invalid primary category payload")
        primary_name = _required_str(primary_payload, "name")
        secondary_categories = primary_payload.get("secondary_categories")
        if not isinstance(secondary_categories, dict):
            raise ValueError(f"missing secondary_categories for {primary_key}")
        for namespace_key, secondary_payload in secondary_categories.items():
            if not isinstance(namespace_key, str) or not isinstance(secondary_payload, dict):
                raise ValueError(f"invalid secondary category under {primary_key}")
            rules.append(
                NamespaceRule(
                    namespace_key=namespace_key,
                    primary_key=primary_key,
                    primary_name=primary_name,
                    secondary_name=_required_str(secondary_payload, "name"),
                    description=_required_str(secondary_payload, "description"),
                    priority=int(secondary_payload.get("priority", 0)),
                    path_keywords=_str_tuple(secondary_payload.get("path_keywords", [])),
                    title_keywords=_str_tuple(secondary_payload.get("title_keywords", [])),
                )
            )
    return tuple(sorted(rules, key=lambda rule: rule.priority, reverse=True))


def _load_indexed_evidence(plan_path: Path, import_result_path: Path) -> IndexedEvidence:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    import_result = json.loads(import_result_path.read_text(encoding="utf-8"))
    source_root = _required_str(plan, "source_root")

    indexed_paths: set[str] = set()
    pending_paths: set[str] = set()
    ignored_paths: set[str] = set()
    failed_paths: set[str] = set()
    ignored_reasons: dict[str, str] = {}
    pending_reasons: dict[str, str] = {}
    indexed_sha256_to_path: dict[str, str] = {}

    for key in ("added_files", "unchanged_files", "modified_files"):
        for item in _list_of_dicts(plan.get(key, []), key):
            relative_path = _required_str(item, "relative_path")
            indexed_paths.add(relative_path)
            sha256 = _optional_str(item.get("sha256"))
            if sha256:
                indexed_sha256_to_path[sha256] = relative_path
    for item in _list_of_dicts(plan.get("pending_files", []), "pending_files"):
        relative_path = _required_str(item, "relative_path")
        pending_paths.add(relative_path)
        pending_reasons[relative_path] = _optional_str(item.get("error_type")) or "pending"
    for item in _list_of_dicts(plan.get("ignored_files", []), "ignored_files"):
        relative_path = _required_str(item, "relative_path")
        ignored_paths.add(relative_path)
        ignored_reasons[relative_path] = _optional_str(item.get("reason")) or "ignored"
    for item in _list_of_dicts(plan.get("failed_files", []), "failed_files"):
        relative_path = _required_str(item, "relative_path")
        failed_paths.add(relative_path)

    import_manifest = import_result.get("manifest")
    imported_index_version_key = None
    if isinstance(import_manifest, dict):
        plan_payload = import_manifest.get("plan")
        if isinstance(plan_payload, dict):
            summary = plan_payload.get("summary")
            if isinstance(summary, dict):
                imported_index_version_key = _optional_str(summary.get("index_version_key"))

    return IndexedEvidence(
        source_root=source_root,
        indexed_paths=frozenset(indexed_paths),
        pending_paths=frozenset(pending_paths),
        ignored_paths=frozenset(ignored_paths),
        failed_paths=frozenset(failed_paths),
        ignored_reasons=ignored_reasons,
        pending_reasons=pending_reasons,
        indexed_sha256_to_path=indexed_sha256_to_path,
        active_index_version_key=_optional_str(plan.get("active_index_version_key")),
        source_package_version_key=_optional_str(plan.get("source_package_version_key")),
        import_success=bool(import_result.get("success") is True),
        imported_index_version_key=imported_index_version_key,
    )


def _build_manifest_rows(
    *,
    data_root: Path,
    taxonomy: tuple[NamespaceRule, ...],
    evidence: IndexedEvidence,
) -> tuple[ManifestRow, ...]:
    rows: list[ManifestRow] = []
    source_root_prefix = _source_root_prefix(data_root=data_root, source_root=evidence.source_root)
    for path in sorted(file for file in data_root.rglob("*") if file.is_file()):
        data_relative = path.relative_to(data_root).as_posix()
        source_relative = (
            data_relative.removeprefix(source_root_prefix)
            if data_relative.startswith(source_root_prefix)
            else ""
        )
        text = _classification_text(path=path, data_root=data_root, source_relative=source_relative)
        rule, matched_terms = _match_namespace(data_relative, source_relative, text, taxonomy)
        sha256 = _sha256(path)
        extraction_status = _extraction_status(
            data_relative=data_relative,
            source_relative=source_relative,
            sha256=sha256,
            evidence=evidence,
        )
        already_indexed = extraction_status.startswith("extracted_in_stable_incremental_artifact")
        needs_manual_review = _needs_manual_review(
            path=path,
            rule=rule,
            extraction_status=extraction_status,
            matched_terms=matched_terms,
        )
        rows.append(
            ManifestRow(
                relative_path=data_relative,
                source_root_relative_path=source_relative,
                file_name=path.name,
                file_ext=path.suffix.lower() or ".none",
                size_bytes=path.stat().st_size,
                sha256=sha256,
                primary_category=rule.primary_name,
                secondary_category=rule.secondary_name,
                namespace_key=rule.namespace_key,
                namespace_confidence=_confidence(rule=rule, matched_terms=matched_terms),
                matched_terms=";".join(matched_terms),
                extraction_status=extraction_status,
                already_indexed=already_indexed,
                needs_manual_review=needs_manual_review,
                recommended_action=_recommended_action(
                    path=path,
                    namespace_key=rule.namespace_key,
                    extraction_status=extraction_status,
                ),
            )
        )
    return tuple(rows)


def _source_root_prefix(*, data_root: Path, source_root: str) -> str:
    source_root_path = Path(source_root)
    data_root_name = data_root.name
    parts = source_root_path.parts
    relative_parts = parts[1:] if parts and parts[0] == data_root_name else parts
    if not relative_parts:
        return ""
    return f"{Path(*relative_parts).as_posix().rstrip('/')}/"


def _classification_text(*, path: Path, data_root: Path, source_relative: str) -> str:
    data_relative = path.relative_to(data_root).as_posix()
    title = path.stem
    path_without_broad_source = source_relative or data_relative
    return _normalize_text(f"{path_without_broad_source} {title}")


def _match_namespace(
    data_relative: str,
    source_relative: str,
    text: str,
    taxonomy: tuple[NamespaceRule, ...],
) -> tuple[NamespaceRule, tuple[str, ...]]:
    path_text = _normalize_text(f"{data_relative} {source_relative}")
    best_rule: NamespaceRule | None = None
    best_terms: tuple[str, ...] = ()
    best_score = -1
    for rule in taxonomy:
        matched_path_terms = tuple(
            term for term in rule.path_keywords if _contains(path_text, term)
        )
        matched_title_terms = tuple(term for term in rule.title_keywords if _contains(text, term))
        if not matched_path_terms and not matched_title_terms:
            continue
        score = rule.priority + len(matched_path_terms) * 30 + len(matched_title_terms) * 10
        if score > best_score:
            best_rule = rule
            best_terms = matched_path_terms + matched_title_terms
            best_score = score
    if best_rule is not None:
        return best_rule, best_terms
    fallback = next(rule for rule in taxonomy if rule.namespace_key == "other.unclassified")
    return fallback, ()


def _contains(haystack: str, needle: str) -> bool:
    return _normalize_text(needle) in haystack


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).casefold()


def _extraction_status(
    *,
    data_relative: str,
    source_relative: str,
    sha256: str,
    evidence: IndexedEvidence,
) -> str:
    if not source_relative:
        return "outside_current_source_root"
    if source_relative in evidence.indexed_paths:
        return "extracted_in_stable_incremental_artifact"
    moved_from = evidence.indexed_sha256_to_path.get(sha256)
    if moved_from:
        return f"extracted_in_stable_incremental_artifact:path_moved_from={moved_from}"
    if source_relative in evidence.pending_paths:
        return f"pending_conversion:{evidence.pending_reasons.get(source_relative, 'pending')}"
    if source_relative in evidence.failed_paths:
        return "source_extraction_issue"
    if source_relative in evidence.ignored_paths:
        reason = evidence.ignored_reasons.get(source_relative, "ignored")
        return f"excluded_by_current_v1_scope:{reason}"
    if Path(data_relative).name in SYSTEM_FILENAMES:
        return "system_file"
    return "not_seen_in_latest_incremental_plan"


def _needs_manual_review(
    *,
    path: Path,
    rule: NamespaceRule,
    extraction_status: str,
    matched_terms: tuple[str, ...],
) -> bool:
    if rule.namespace_key == "other.unclassified":
        return True
    if path.name in SYSTEM_FILENAMES or path.suffix.lower() in UNSUPPORTED_EXTENSIONS:
        return True
    if not matched_terms:
        return True
    return extraction_status.startswith(("pending_conversion", "source_extraction_issue"))


def _confidence(*, rule: NamespaceRule, matched_terms: tuple[str, ...]) -> str:
    if rule.namespace_key == "other.unclassified":
        return "low"
    if len(matched_terms) >= 2:
        return "high"
    return "medium"


def _recommended_action(*, path: Path, namespace_key: str, extraction_status: str) -> str:
    suffix = path.suffix.lower()
    if extraction_status == "extracted_in_stable_incremental_artifact":
        return "补齐 namespace 元数据；不需要重算 embedding。"
    if extraction_status.startswith("pending_conversion"):
        return "先做格式转换或 OCR，再进入 namespace 入库队列。"
    if extraction_status.startswith("excluded_by_current_v1_scope"):
        return "保留分类结果；按业务优先级决定是否纳入后续补萃取。"
    if extraction_status == "outside_current_source_root":
        return "纳入新的 source package 计划，先按 namespace 做抽样验收。"
    if namespace_key == "other.unclassified":
        return "人工判定分类或标记为低相关归档。"
    if suffix in UNSUPPORTED_EXTENSIONS:
        return "先转换为可抽取文本，再入库。"
    return "进入待萃取队列，按 namespace 优先级处理。"


def _build_summary(
    *,
    rows: tuple[ManifestRow, ...],
    data_root: Path,
    taxonomy_path: Path,
    incremental_plan_path: Path,
    import_result_path: Path,
    evidence: IndexedEvidence,
) -> dict[str, object]:
    generated_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    by_primary = Counter(row.primary_category for row in rows)
    by_namespace = Counter(row.namespace_key for row in rows)
    by_status = Counter(row.extraction_status.split(":", 1)[0] for row in rows)
    by_priority_queue = _priority_queue_counts(rows)
    return {
        "status": "ready",
        "generated_at": generated_at,
        "data_root": str(data_root),
        "taxonomy_path": str(taxonomy_path),
        "incremental_plan_path": str(incremental_plan_path),
        "import_result_path": str(import_result_path),
        "source_root": evidence.source_root,
        "source_package_version_key": evidence.source_package_version_key,
        "active_index_version_key_from_plan": evidence.active_index_version_key,
        "import_success": evidence.import_success,
        "imported_index_version_key": evidence.imported_index_version_key,
        "summary": {
            "total_files": len(rows),
            "already_indexed_files": sum(1 for row in rows if row.already_indexed),
            "needs_manual_review_files": sum(1 for row in rows if row.needs_manual_review),
            "outside_current_source_root_files": sum(
                1 for row in rows if row.extraction_status == "outside_current_source_root"
            ),
            "pending_or_issue_files": sum(
                1
                for row in rows
                if row.extraction_status.startswith(
                    ("pending_conversion", "source_extraction_issue")
                )
            ),
        },
        "counts": {
            "by_primary_category": dict(by_primary.most_common()),
            "by_namespace": dict(by_namespace.most_common()),
            "by_extraction_status": dict(by_status.most_common()),
            "by_priority_queue": by_priority_queue,
        },
        "namespace_details": _namespace_details(rows),
        "recommended_execution_order": _recommended_execution_order(rows),
    }


def _priority_queue_counts(rows: tuple[ManifestRow, ...]) -> dict[str, int]:
    result: dict[str, int] = defaultdict(int)
    for row in rows:
        queue = _queue_name(row)
        result[queue] += 1
    return dict(sorted(result.items()))


def _queue_name(row: ManifestRow) -> str:
    if row.already_indexed:
        return "P0_metadata_backfill_for_indexed"
    if row.namespace_key.startswith("medical."):
        return "P1_medical_unextracted"
    if row.namespace_key in {
        "policy.finance_price_procurement",
        "policy.social_security_livelihood",
        "management.judicial_audit_procedure",
        "management.market_quality",
    }:
        return "P2_audit_adjacent_unextracted"
    if row.namespace_key.startswith(("policy.", "management.")):
        return "P3_general_policy_management_unextracted"
    return "P4_other_or_manual_review"


def _namespace_details(rows: tuple[ManifestRow, ...]) -> list[dict[str, object]]:
    grouped: dict[str, list[ManifestRow]] = defaultdict(list)
    for row in rows:
        grouped[row.namespace_key].append(row)
    details: list[dict[str, object]] = []
    for namespace_key, items in sorted(grouped.items()):
        indexed_count = sum(1 for item in items if item.already_indexed)
        manual_count = sum(1 for item in items if item.needs_manual_review)
        details.append(
            {
                "namespace_key": namespace_key,
                "primary_category": items[0].primary_category,
                "secondary_category": items[0].secondary_category,
                "file_count": len(items),
                "already_indexed_files": indexed_count,
                "unextracted_files": len(items) - indexed_count,
                "needs_manual_review_files": manual_count,
                "sample_paths": [item.relative_path for item in items[:5]],
            }
        )
    return details


def _recommended_execution_order(rows: tuple[ManifestRow, ...]) -> list[dict[str, object]]:
    namespace_to_rows: dict[str, list[ManifestRow]] = defaultdict(list)
    for row in rows:
        namespace_to_rows[row.namespace_key].append(row)
    order_keys = [
        "medical.legal_regulations",
        "medical.supervision_rules",
        "medical.catalog_payment_codes",
        "medical.risk_negative_list",
        "policy.finance_price_procurement",
        "policy.social_security_livelihood",
        "management.judicial_audit_procedure",
        "management.market_quality",
        "policy.general_policy",
        "management.general_admin",
    ]
    result: list[dict[str, object]] = []
    for position, namespace_key in enumerate(order_keys, start=1):
        items = namespace_to_rows.get(namespace_key, [])
        if not items:
            continue
        indexed_count = sum(1 for item in items if item.already_indexed)
        result.append(
            {
                "order": position,
                "namespace_key": namespace_key,
                "primary_category": items[0].primary_category,
                "secondary_category": items[0].secondary_category,
                "file_count": len(items),
                "already_indexed_files": indexed_count,
                "unextracted_files": len(items) - indexed_count,
                "recommended_next_step": _namespace_next_step(
                    namespace_key,
                    indexed_count,
                    len(items),
                ),
            }
        )
    return result


def _namespace_next_step(namespace_key: str, indexed_count: int, total_count: int) -> str:
    if indexed_count:
        return "先补齐已入库文档 namespace 元数据，再增量处理未萃取文件。"
    if namespace_key.startswith("medical."):
        return "优先抽样转换和入库，建立该 namespace 最小评测集。"
    if total_count > 1000:
        return "先做标题去重与低相关过滤，再分批入库。"
    return "进入第二批补萃取候选，先做 5-10 条问题评测。"


def _write_manifest_csv(path: Path, rows: tuple[ManifestRow, ...]) -> None:
    fieldnames = list(rows[0].to_csv_row().keys()) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row.to_csv_row())


def _render_markdown_report(summary: dict[str, object]) -> str:
    summary_payload = _ensure_mapping(summary["summary"])
    counts = _ensure_mapping(summary["counts"])
    lines = [
        "---",
        "title: 知识库二级分类 manifest 执行报告",
        "doc_type: analysis",
        "module: knowledge-base-taxonomy",
        "topic: namespace-manifest",
        "status: draft",
        "created: 2026-07-02",
        "updated: 2026-07-02",
        "owner: self",
        "source: ai",
        "---",
        "",
        "# 知识库二级分类 manifest 执行报告",
        "",
        "## 1. 运行边界",
        "",
        f"- `generated_at`: `{summary['generated_at']}`",
        f"- `data_root`: `{summary['data_root']}`",
        f"- `taxonomy_path`: `{summary['taxonomy_path']}`",
        f"- `source_root`: `{summary['source_root']}`",
        f"- `import_success`: `{summary['import_success']}`",
        f"- `imported_index_version_key`: `{summary['imported_index_version_key']}`",
        "",
        "本报告只生成分类 manifest 和执行队列，不写数据库、不重建向量、不修改生产索引。",
        "",
        "## 2. 总览",
        "",
        f"- `total_files`: `{summary_payload['total_files']}`",
        f"- `already_indexed_files`: `{summary_payload['already_indexed_files']}`",
        "- `outside_current_source_root_files`: "
        f"`{summary_payload['outside_current_source_root_files']}`",
        f"- `pending_or_issue_files`: `{summary_payload['pending_or_issue_files']}`",
        f"- `needs_manual_review_files`: `{summary_payload['needs_manual_review_files']}`",
        "",
        "## 3. 一级分类计数",
        "",
        *_count_lines(_ensure_mapping(counts["by_primary_category"])),
        "",
        "## 4. 入库状态计数",
        "",
        *_count_lines(_ensure_mapping(counts["by_extraction_status"])),
        "",
        "## 5. 执行队列计数",
        "",
        *_count_lines(_ensure_mapping(counts["by_priority_queue"])),
        "",
        "## 6. 推荐执行顺序",
        "",
        "| 顺序 | namespace | 一级 | 二级 | 文件数 | 已入库 | 待处理 | 下一步 |",
        "| ---: | --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for item in _ensure_list(summary["recommended_execution_order"]):
        row = _ensure_mapping(item)
        lines.append(
            "| "
            f"{row['order']} | `{row['namespace_key']}` | {row['primary_category']} | "
            f"{row['secondary_category']} | {row['file_count']} | {row['already_indexed_files']} | "
            f"{row['unextracted_files']} | {row['recommended_next_step']} |"
        )
    lines.extend(["", "## 7. namespace 明细", ""])
    for item in _ensure_list(summary["namespace_details"]):
        row = _ensure_mapping(item)
        lines.extend(
            [
                f"### `{row['namespace_key']}`",
                "",
                f"- 分类：{row['primary_category']} / {row['secondary_category']}",
                f"- 文件数：`{row['file_count']}`",
                f"- 已入库：`{row['already_indexed_files']}`",
                f"- 待处理：`{row['unextracted_files']}`",
                f"- 需人工复核：`{row['needs_manual_review_files']}`",
                "- 样例：",
            ]
        )
        for sample_path in _ensure_list(row["sample_paths"]):
            lines.append(f"  - `{sample_path}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _count_lines(counts: Mapping[str, object]) -> list[str]:
    if not counts:
        return ["- 无"]
    return [f"- `{key}`: `{value}`" for key, value in counts.items()]


def _stdout_summary(
    summary: dict[str, object],
    manifest_csv: Path,
    summary_json: Path,
    report_path: Path,
) -> dict[str, object]:
    return {
        "status": summary["status"],
        "total_files": _ensure_mapping(summary["summary"])["total_files"],
        "already_indexed_files": _ensure_mapping(summary["summary"])["already_indexed_files"],
        "needs_manual_review_files": _ensure_mapping(summary["summary"])[
            "needs_manual_review_files"
        ],
        "manifest_csv": str(manifest_csv),
        "summary_json": str(summary_json),
        "report": str(report_path),
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(HASH_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def _required_str(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"missing required string: {key}")
    return value


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _str_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError("expected list of strings")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError("expected list of strings")
        result.append(item)
    return tuple(result)


def _list_of_dicts(value: object, key: str) -> tuple[dict[str, object], ...]:
    if not isinstance(value, list):
        raise ValueError(f"{key} must be a list")
    result: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError(f"{key} must contain objects")
        result.append(item)
    return tuple(result)


def _ensure_mapping(value: object) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise TypeError("expected mapping")
    return value


def _ensure_list(value: object) -> list[Any]:
    if not isinstance(value, list):
        raise TypeError("expected list")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
