from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from medical_audit_kb.domain.constants import DocumentStatus, SourceCollection
from medical_audit_kb.domain.schemas import SourcePackageVersionCreate
from medical_audit_kb.domain.source_collection_registry import source_collection_definition

SOURCE_COLLECTION_BY_TOP_LEVEL: Final = {
    "医保目录": SourceCollection.MEDICAL_INSURANCE_CATALOG,
    "智能监管“两库”规则和知识点": SourceCollection.SUPERVISION_RULES_KNOWLEDGE,
    "风险负面清单": SourceCollection.RISK_NEGATIVE_LIST,
    "全量法律": SourceCollection.MEDICAL_INSURANCE_LAWS,
}

LAW_KEYWORDS: Final = (
    "医保",
    "医疗保障",
    "基本医疗保险",
    "医疗保障基金",
    "医疗机构",
    "医疗保险",
    "药品",
    "处方",
    "门诊",
    "住院",
    "诊疗",
    "卫生",
    "生育保险",
    "工伤保险",
    "DRG",
    "DIP",
)

# 领域分类（底层分类库）：每篇文档除来源 source_collection 外，再打一个 domain 领域标签。
# 医保策展三集合（医保目录/两库/风险）按来源直接判「医保基金」；广义法律/规章语料按文件名
# 关键词分类；命中医保关键词（LAW_KEYWORDS）也判「医保基金」；都不命中 → 「其他」。
# 「其他」仍入底层分类库，只是不进医保基金专题（专题切片在检索层按 domain 过滤）。关键词可逐步增减。
DOMAIN_MEDICAL_INSURANCE: Final = "医保基金"
DOMAIN_OTHER: Final = "其他"

OTHER_DOMAIN_KEYWORDS: Final[tuple[tuple[str, tuple[str, ...]], ...]] = (
    ("价格", ("价格", "收费", "计价", "成本监审", "行政事业性收费")),
    ("财政", ("财政", "预算", "决算", "国库", "专项资金", "政府投资", "财务")),
    ("会计审计", ("会计", "审计", "资产评估", "内部控制")),
    ("国资", ("国有资产", "国有股权", "国资", "产权登记")),
    ("采购", ("政府采购", "招标投标", "招标", "投标")),
    ("税", ("税收", "税务", "资源税", "契税", "印花税", "增值税", "发票", "票据")),
    ("统计", ("统计法", "统计调查")),
)

# 来源即「医保基金」域的策展集合（医保法律集合不在内：广义法律语料按文件名再分类）。
_CURATED_MEDICAL_COLLECTIONS: Final = frozenset(
    {
        SourceCollection.MEDICAL_INSURANCE_CATALOG,
        SourceCollection.SUPERVISION_RULES_KNOWLEDGE,
        SourceCollection.RISK_NEGATIVE_LIST,
    }
)

SUPPORTED_MEDIA_TYPES: Final = {
    ".md": "text/markdown",
    ".txt": "text/plain",
    ".pdf": "application/pdf",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

PENDING_MEDIA_TYPES: Final = {
    ".png": "image/png",
    ".zip": "application/zip",
    ".rar": "application/vnd.rar",
}

SYSTEM_FILE_NAMES: Final = frozenset({".DS_Store"})
HASH_BLOCK_SIZE: Final = 1024 * 1024


@dataclass(frozen=True, slots=True)
class InventoryFile:
    path: Path
    relative_path: str
    file_name: str
    file_ext: str
    media_type: str
    size_bytes: int
    sha256: str
    source_collection: SourceCollection | None
    domain: str
    status: DocumentStatus
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class SourcePackageManifest:
    package_version: SourcePackageVersionCreate
    files: tuple[InventoryFile, ...]
    duplicate_groups: dict[str, tuple[InventoryFile, ...]]

    @property
    def index_candidates(self) -> tuple[InventoryFile, ...]:
        return tuple(file for file in self.files if file.status == DocumentStatus.INDEX_CANDIDATE)

    @property
    def pending_files(self) -> tuple[InventoryFile, ...]:
        return tuple(file for file in self.files if file.status == DocumentStatus.PENDING)

    @property
    def ignored_files(self) -> tuple[InventoryFile, ...]:
        return tuple(file for file in self.files if file.status == DocumentStatus.IGNORED)


def build_source_package_manifest(
    source_root: Path | str,
    *,
    version_key: str | None = None,
) -> SourcePackageManifest:
    root = Path(source_root)
    if not root.exists():
        raise FileNotFoundError(f"source root not found: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"source root must be a directory: {root}")

    files = tuple(_scan_files(root))
    duplicate_groups = _find_duplicate_groups(files)
    package_version = SourcePackageVersionCreate(
        version_key=version_key or _default_version_key(root),
        source_root_path=root,
        description="knowledge query source package inventory",
        metadata={
            "total_files": len(files),
            "index_candidate_count": len(
                [file for file in files if file.status == DocumentStatus.INDEX_CANDIDATE]
            ),
            "pending_count": len([file for file in files if file.status == DocumentStatus.PENDING]),
            "ignored_count": len([file for file in files if file.status == DocumentStatus.IGNORED]),
            "duplicate_group_count": len(duplicate_groups),
            "domain_counts": _domain_counts(files),
        },
    )
    return SourcePackageManifest(
        package_version=package_version,
        files=files,
        duplicate_groups=duplicate_groups,
    )


def classify_source_collection(relative_path: Path) -> SourceCollection | None:
    if not relative_path.parts:
        return None

    top_level = relative_path.parts[0]
    if top_level in SourceCollection._value2member_map_:
        return SourceCollection(top_level)

    if top_level in SOURCE_COLLECTION_BY_TOP_LEVEL:
        # 全量入库：全量法律目录下所有文档都归入法律集合（不再用 is_medical_insurance_law 丢弃），
        # 医保 vs 非医保的区分交给 domain 领域标签（见 classify_domain）。
        return SOURCE_COLLECTION_BY_TOP_LEVEL[top_level]

    if is_medical_insurance_law(relative_path.name):
        return SourceCollection.MEDICAL_INSURANCE_LAWS

    return None


def classify_domain(file_name: str, source_collection: SourceCollection | None = None) -> str:
    """给每篇文档打领域标签（底层分类库）。

    医保策展三集合（目录/两库/风险）按来源直接判「医保基金」；其余（含广义法律语料）先按
    医保关键词判，再按 OTHER_DOMAIN_KEYWORDS 关键词判；都不命中 → 「其他」。
    """
    if source_collection in _CURATED_MEDICAL_COLLECTIONS:
        return DOMAIN_MEDICAL_INSURANCE
    if (
        source_collection is not None
        and source_collection != SourceCollection.MEDICAL_INSURANCE_LAWS
    ):
        return source_collection_definition(source_collection).label
    if is_medical_insurance_law(file_name):
        return DOMAIN_MEDICAL_INSURANCE
    normalized = file_name.upper()
    for domain, keywords in OTHER_DOMAIN_KEYWORDS:
        if any(keyword.upper() in normalized for keyword in keywords):
            return domain
    return DOMAIN_OTHER


def is_medical_insurance_law(file_name: str) -> bool:
    normalized = file_name.upper()
    return any(keyword.upper() in normalized for keyword in LAW_KEYWORDS)


def calculate_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(HASH_BLOCK_SIZE), b""):
            digest.update(block)
    return digest.hexdigest()


def _scan_files(root: Path) -> list[InventoryFile]:
    files: list[InventoryFile] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        files.append(_build_inventory_file(root, path))
    return files


def _build_inventory_file(root: Path, path: Path) -> InventoryFile:
    relative_path = path.relative_to(root)
    file_name = path.name
    file_ext = path.suffix.lower()
    size_bytes = path.stat().st_size
    sha256 = calculate_sha256(path)
    media_type = _media_type_for_ext(file_ext)
    source_collection = classify_source_collection(relative_path)
    domain = classify_domain(file_name, source_collection)
    status, reason = _classify_status(file_name, file_ext, source_collection)

    return InventoryFile(
        path=path,
        relative_path=relative_path.as_posix(),
        file_name=file_name,
        file_ext=file_ext,
        media_type=media_type,
        size_bytes=size_bytes,
        sha256=sha256,
        source_collection=source_collection,
        domain=domain,
        status=status,
        reason=reason,
    )


def _media_type_for_ext(file_ext: str) -> str:
    if file_ext in SUPPORTED_MEDIA_TYPES:
        return SUPPORTED_MEDIA_TYPES[file_ext]
    if file_ext in PENDING_MEDIA_TYPES:
        return PENDING_MEDIA_TYPES[file_ext]
    return "application/octet-stream"


def _classify_status(
    file_name: str,
    file_ext: str,
    source_collection: SourceCollection | None,
) -> tuple[DocumentStatus, str | None]:
    # 全量入库：策展四集合下的可解析文档都进 INDEX_CANDIDATE（含全量法律里的非医保文档，
    # 其领域差异由 domain 标签承载，不再 IGNORE）。仅系统文件、不支持的格式、未知来源被排除。
    if file_name in SYSTEM_FILE_NAMES:
        return DocumentStatus.IGNORED, "system-file"

    if file_ext not in SUPPORTED_MEDIA_TYPES:
        return DocumentStatus.PENDING, "unsupported-file-type"

    if source_collection is None:
        return DocumentStatus.PENDING, "unknown-source-collection"

    return DocumentStatus.INDEX_CANDIDATE, None


def _domain_counts(files: tuple[InventoryFile, ...]) -> dict[str, int]:
    counts: defaultdict[str, int] = defaultdict(int)
    for file in files:
        if file.status == DocumentStatus.INDEX_CANDIDATE:
            counts[file.domain] += 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _find_duplicate_groups(
    files: tuple[InventoryFile, ...],
) -> dict[str, tuple[InventoryFile, ...]]:
    grouped: defaultdict[str, list[InventoryFile]] = defaultdict(list)
    for file in files:
        if file.status == DocumentStatus.IGNORED:
            continue
        grouped[file.sha256].append(file)

    return {digest: tuple(items) for digest, items in grouped.items() if len(items) > 1}


def _default_version_key(root: Path) -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    return f"{root.name}-{timestamp}"
