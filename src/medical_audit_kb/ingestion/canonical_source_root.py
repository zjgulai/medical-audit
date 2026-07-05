from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

SYSTEM_FILENAMES = {".DS_Store", ".gitkeep"}
TRAILING_SEPARATOR_CHARS = " _-—－.．()（）[]【】"
NUMERIC_PREFIX_PATTERN = re.compile(r"^\d+[_\-\s]+")
VERSION_DATE_PATTERN = re.compile(
    r"(?P<year>19\d{2}|20\d{2})"
    r"(?:[-_.年]?)"
    r"(?P<month>0[1-9]|1[0-2])"
    r"(?:[-_.月]?)"
    r"(?P<day>0[1-9]|[12]\d|3[01])"
    r"日?"
)


@dataclass(frozen=True, slots=True)
class CanonicalSourceItem:
    relative_path: str
    resolved_source_path: str
    file_name: str
    file_ext: str
    size_bytes: int
    sha256: str
    canonical_document_key: str
    canonical_version_date: str
    source_priority: int
    source_priority_reason: str
    selected: bool
    selection_rank: int
    selected_relative_path: str
    suppression_reason: str

    def to_manifest_row(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class CanonicalSourceRootResult:
    source_root: str
    output_root: str
    execute: bool
    generated_at: str
    discovered_file_count: int
    selected_file_count: int
    suppressed_file_count: int
    canonical_document_count: int
    duplicate_group_count: int
    versioned_file_count: int
    linked_file_count: int
    items: tuple[CanonicalSourceItem, ...]

    def summary(self) -> dict[str, object]:
        return {
            "source_root": self.source_root,
            "output_root": self.output_root,
            "execute": self.execute,
            "generated_at": self.generated_at,
            "discovered_file_count": self.discovered_file_count,
            "selected_file_count": self.selected_file_count,
            "suppressed_file_count": self.suppressed_file_count,
            "canonical_document_count": self.canonical_document_count,
            "duplicate_group_count": self.duplicate_group_count,
            "versioned_file_count": self.versioned_file_count,
            "linked_file_count": self.linked_file_count,
        }

    def to_manifest(self) -> dict[str, object]:
        return {
            "status": "materialized" if self.execute else "planned",
            "summary": self.summary(),
            "selected": [
                item.to_manifest_row()
                for item in self.items
                if item.selected
            ],
            "suppressed": [
                item.to_manifest_row()
                for item in self.items
                if not item.selected
            ],
            "boundaries": {
                "source_root_write": False,
                "database_write": False,
                "embedding_rebuild": False,
                "provider_call": False,
                "production_write": False,
            },
        }


def build_canonical_source_root(
    source_root: Path | str,
    output_root: Path | str,
    *,
    execute: bool = False,
) -> CanonicalSourceRootResult:
    source_root_path = Path(source_root).resolve()
    output_root_path = Path(output_root).resolve()
    _validate_roots(source_root_path, output_root_path, execute=execute)

    discovered = _discover_items(source_root_path)
    ranked = _rank_items(discovered)
    linked_file_count = 0
    if execute:
        linked_file_count = _materialize_selected_items(ranked, output_root_path)

    group_sizes = Counter(item.canonical_document_key for item in ranked)
    return CanonicalSourceRootResult(
        source_root=str(source_root_path),
        output_root=str(output_root_path),
        execute=execute,
        generated_at=datetime.now().strftime("%Y-%m-%dT%H:%M:%S%z"),
        discovered_file_count=len(ranked),
        selected_file_count=sum(1 for item in ranked if item.selected),
        suppressed_file_count=sum(1 for item in ranked if not item.selected),
        canonical_document_count=len(group_sizes),
        duplicate_group_count=sum(1 for count in group_sizes.values() if count > 1),
        versioned_file_count=sum(1 for item in ranked if item.canonical_version_date),
        linked_file_count=linked_file_count,
        items=ranked,
    )


def write_canonical_manifest_json(
    path: Path | str,
    result: CanonicalSourceRootResult,
) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result.to_manifest(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_canonical_manifest_csv(
    path: Path | str,
    result: CanonicalSourceRootResult,
) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(CanonicalSourceItem.__dataclass_fields__.keys())
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in result.items:
            writer.writerow(item.to_manifest_row())


def write_canonical_report(
    path: Path | str,
    result: CanonicalSourceRootResult,
) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_canonical_report(result), encoding="utf-8")


def render_canonical_report(result: CanonicalSourceRootResult) -> str:
    selected_samples = [
        item for item in result.items if item.selected and _is_representative(item)
    ][:12]
    suppressed_samples = [item for item in result.items if not item.selected][:12]
    lines = [
        "---",
        'title: "医疗法律法规 canonical source root 构建报告"',
        f'created_at: "{result.generated_at}"',
        'status: "draft"',
        'scope: "local_knowledge_base_canonical_source_root"',
        "---",
        "",
        "# 医疗法律法规 canonical source root 构建报告",
        "",
        "## 事实",
        "",
        f"- `source_root`: `{result.source_root}`",
        f"- `output_root`: `{result.output_root}`",
        f"- `execute`: `{str(result.execute).lower()}`",
        f"- `discovered_file_count`: `{result.discovered_file_count}`",
        f"- `selected_file_count`: `{result.selected_file_count}`",
        f"- `suppressed_file_count`: `{result.suppressed_file_count}`",
        f"- `canonical_document_count`: `{result.canonical_document_count}`",
        f"- `duplicate_group_count`: `{result.duplicate_group_count}`",
        f"- `versioned_file_count`: `{result.versioned_file_count}`",
        f"- `linked_file_count`: `{result.linked_file_count}`",
        "",
        "## 规则",
        "",
        "- 按清洗后的法规标题聚合为 `canonical_document_key`。",
        "- 同一标题优先选择最新 `canonical_version_date`。",
        "- 版本日期相同或缺失时，优先选择 converted 文档，其次选择 raw 文档。",
        "- 本步骤只生成新的本地 canonical source root，不修改原始 source root，"
        "不写数据库，不重建向量，不调用 provider。",
        "",
        "## 代表性保留样本",
        "",
    ]
    lines.extend(_markdown_table(selected_samples))
    lines.extend(
        [
            "",
            "## 代表性抑制样本",
            "",
        ]
    )
    lines.extend(_markdown_table(suppressed_samples))
    lines.extend(
        [
            "",
            "## 边界",
            "",
            "- `source_root_write=false`",
            "- `database_write=false`",
            "- `embedding_rebuild=false`",
            "- `provider_call=false`",
            "- `production_write=false`",
            "",
        ]
    )
    return "\n".join(lines)


def canonical_document_key_and_version(file_name: str) -> tuple[str, str]:
    stem = unicodedata.normalize("NFKC", Path(file_name).stem)
    stem = NUMERIC_PREFIX_PATTERN.sub("", stem).strip(TRAILING_SEPARATOR_CHARS)
    version_date = ""
    matches = list(VERSION_DATE_PATTERN.finditer(stem))
    for match in reversed(matches):
        tail = stem[match.end() :]
        if tail.strip(TRAILING_SEPARATOR_CHARS) == "":
            version_date = _date_from_match(match)
            stem = stem[: match.start()] + tail
            break
    key = re.sub(r"\s+", "", stem).strip(TRAILING_SEPARATOR_CHARS)
    return key or Path(file_name).stem, version_date


def _discover_items(source_root: Path) -> tuple[CanonicalSourceItem, ...]:
    items: list[CanonicalSourceItem] = []
    for path in _iter_files(source_root):
        relative_path = path.relative_to(source_root).as_posix()
        resolved_path = path.resolve()
        stat = resolved_path.stat()
        canonical_key, version_date = canonical_document_key_and_version(path.name)
        priority, priority_reason = _source_priority(relative_path)
        items.append(
            CanonicalSourceItem(
                relative_path=relative_path,
                resolved_source_path=str(resolved_path),
                file_name=path.name,
                file_ext=path.suffix.lower(),
                size_bytes=stat.st_size,
                sha256=_sha256_file(resolved_path),
                canonical_document_key=canonical_key,
                canonical_version_date=version_date,
                source_priority=priority,
                source_priority_reason=priority_reason,
                selected=False,
                selection_rank=0,
                selected_relative_path="",
                suppression_reason="",
            )
        )
    return tuple(sorted(items, key=lambda item: item.relative_path))


def _rank_items(items: tuple[CanonicalSourceItem, ...]) -> tuple[CanonicalSourceItem, ...]:
    grouped: dict[str, list[CanonicalSourceItem]] = defaultdict(list)
    for item in items:
        grouped[item.canonical_document_key].append(item)

    ranked_items: list[CanonicalSourceItem] = []
    for group in grouped.values():
        ranked_group = sorted(
            group,
            key=lambda item: (
                _negative_date_sort_key(item.canonical_version_date),
                item.source_priority,
                item.relative_path,
            ),
        )
        selected = ranked_group[0]
        for rank, item in enumerate(ranked_group, start=1):
            ranked_items.append(
                CanonicalSourceItem(
                    relative_path=item.relative_path,
                    resolved_source_path=item.resolved_source_path,
                    file_name=item.file_name,
                    file_ext=item.file_ext,
                    size_bytes=item.size_bytes,
                    sha256=item.sha256,
                    canonical_document_key=item.canonical_document_key,
                    canonical_version_date=item.canonical_version_date,
                    source_priority=item.source_priority,
                    source_priority_reason=item.source_priority_reason,
                    selected=item.relative_path == selected.relative_path,
                    selection_rank=rank,
                    selected_relative_path=selected.relative_path,
                    suppression_reason=""
                    if item.relative_path == selected.relative_path
                    else "duplicate_or_superseded",
                )
            )
    return tuple(sorted(ranked_items, key=lambda item: item.relative_path))


def _materialize_selected_items(items: tuple[CanonicalSourceItem, ...], output_root: Path) -> int:
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"output root is not empty: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    linked_count = 0
    for item in items:
        if not item.selected:
            continue
        destination = output_root / item.relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(item.resolved_source_path, destination)
        linked_count += 1
    return linked_count


def _validate_roots(source_root: Path, output_root: Path, *, execute: bool) -> None:
    if not source_root.exists() or not source_root.is_dir():
        raise FileNotFoundError(f"source root not found: {source_root}")
    if output_root == source_root:
        raise ValueError("output root must be different from source root")
    if _is_relative_to(output_root, source_root):
        raise ValueError("output root must not be inside source root")
    if execute:
        if output_root.exists() and any(output_root.iterdir()):
            raise FileExistsError(f"output root is not empty: {output_root}")
    elif output_root.exists() and not output_root.is_dir():
        raise NotADirectoryError(f"output root exists and is not a directory: {output_root}")


def _iter_files(source_root: Path) -> tuple[Path, ...]:
    files: list[Path] = []
    for root, dirnames, filenames in os.walk(source_root, followlinks=True):
        dirnames[:] = [name for name in dirnames if not name.startswith(".")]
        root_path = Path(root)
        for file_name in filenames:
            if file_name in SYSTEM_FILENAMES:
                continue
            path = root_path / file_name
            if path.is_file():
                files.append(path)
    return tuple(sorted(files, key=lambda path: path.relative_to(source_root).as_posix()))


def _source_priority(relative_path: str) -> tuple[int, str]:
    normalized = relative_path.replace("\\", "/")
    if "/docx-converted/审计通用法律法规/" in normalized:
        return 0, "converted_audit_general_laws"
    if "/docx-converted/国家规章平台文档/" in normalized:
        return 1, "converted_state_rules_platform"
    if "/docx-converted/" in normalized:
        return 2, "converted_other"
    return 3, "raw_or_other"


def _negative_date_sort_key(value: str) -> tuple[int, int, int]:
    if not value:
        return (0, 0, 0)
    year, month, day = value.split("-")
    return (-int(year), -int(month), -int(day))


def _date_from_match(match: re.Match[str]) -> str:
    return f"{match.group('year')}-{match.group('month')}-{match.group('day')}"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _markdown_table(items: list[CanonicalSourceItem]) -> list[str]:
    if not items:
        return ["未命中样本。"]
    lines = [
        "| canonical_document_key | selected | version | priority | relative_path |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in items:
        lines.append(
            "| "
            + " | ".join(
                [
                    item.canonical_document_key,
                    str(item.selected).lower(),
                    item.canonical_version_date or "",
                    str(item.source_priority),
                    item.relative_path,
                ]
            )
            + " |"
        )
    return lines


def _is_representative(item: CanonicalSourceItem) -> bool:
    terms = ("护士条例", "中华人民共和国药品管理法", "医疗器械监督管理条例")
    return any(term in item.canonical_document_key for term in terms)
