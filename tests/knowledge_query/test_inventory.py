from pathlib import Path

from medical_audit_kb.domain.constants import DocumentStatus, SourceCollection
from medical_audit_kb.ingestion.inventory import (
    build_source_package_manifest,
    calculate_sha256,
    classify_domain,
    classify_source_collection,
    is_medical_insurance_law,
)


def test_inventory_builds_manifest_and_classifies_files(tmp_path: Path) -> None:
    source_root = tmp_path / "医保审核前期资料"
    _write_text(source_root / "医保目录" / "ICD-10医保2.0版.md", "医保目录")
    _write_text(source_root / "智能监管“两库”规则和知识点" / "第一批" / "规则.xlsx", "fake")
    _write_text(source_root / "风险负面清单" / "医保负面清单.txt", "风险")
    _write_text(source_root / "全量法律" / "医疗保障基金使用监督管理条例.md", "条例")
    _write_text(source_root / "全量法律" / "人民检察院刑事诉讼规则.md", "非医保")
    _write_text(source_root / "全量法律" / "价格违法行为行政处罚规定.md", "价格")
    _write_text(source_root / "未知来源" / "unknown.md", "未知")
    _write_text(source_root / ".DS_Store", "system")

    manifest = build_source_package_manifest(source_root, version_key="unit-test-package")
    by_relative_path = {file.relative_path: file for file in manifest.files}

    assert manifest.package_version.version_key == "unit-test-package"
    assert manifest.package_version.metadata["total_files"] == 8
    catalog_file = by_relative_path["医保目录/ICD-10医保2.0版.md"]
    assert catalog_file.source_collection == SourceCollection.MEDICAL_INSURANCE_CATALOG
    assert catalog_file.domain == "医保基金"
    assert (
        by_relative_path["智能监管“两库”规则和知识点/第一批/规则.xlsx"].source_collection
        == SourceCollection.SUPERVISION_RULES_KNOWLEDGE
    )
    assert (
        by_relative_path["风险负面清单/医保负面清单.txt"].source_collection
        == SourceCollection.RISK_NEGATIVE_LIST
    )
    mi_law = by_relative_path["全量法律/医疗保障基金使用监督管理条例.md"]
    assert mi_law.source_collection == SourceCollection.MEDICAL_INSURANCE_LAWS
    assert mi_law.domain == "医保基金"
    # 全量入库：非医保法律不再被丢弃，进 INDEX_CANDIDATE 并按领域打标签。
    non_mi_law = by_relative_path["全量法律/人民检察院刑事诉讼规则.md"]
    assert non_mi_law.source_collection == SourceCollection.MEDICAL_INSURANCE_LAWS
    assert non_mi_law.status == DocumentStatus.INDEX_CANDIDATE
    assert non_mi_law.domain == "其他"
    price_law = by_relative_path["全量法律/价格违法行为行政处罚规定.md"]
    assert price_law.status == DocumentStatus.INDEX_CANDIDATE
    assert price_law.domain == "价格"
    assert by_relative_path["未知来源/unknown.md"].status == DocumentStatus.PENDING
    assert by_relative_path["未知来源/unknown.md"].reason == "unknown-source-collection"
    assert by_relative_path[".DS_Store"].status == DocumentStatus.IGNORED
    assert len(manifest.index_candidates) == 6
    assert len(manifest.pending_files) == 1
    assert len(manifest.ignored_files) == 1
    assert manifest.package_version.metadata["domain_counts"]["医保基金"] == 4


def test_inventory_calculates_stable_hashes_and_detects_duplicates(tmp_path: Path) -> None:
    source_root = tmp_path / "医保审核前期资料"
    content = "同一份医保政策"
    first = _write_text(source_root / "全量法律" / "医保政策A.md", content)
    second = _write_text(source_root / "全量法律" / "医保政策B.md", content)

    assert calculate_sha256(first) == calculate_sha256(second)

    manifest = build_source_package_manifest(source_root, version_key="duplicate-test")

    assert len(manifest.duplicate_groups) == 1
    duplicate_group = next(iter(manifest.duplicate_groups.values()))
    assert {file.relative_path for file in duplicate_group} == {
        "全量法律/医保政策A.md",
        "全量法律/医保政策B.md",
    }


def test_inventory_puts_unsupported_known_files_into_pending_queue(tmp_path: Path) -> None:
    source_root = tmp_path / "医保审核前期资料"
    _write_binary(source_root / "风险负面清单" / "医保负面清单.png", b"\x89PNG\r\n")
    _write_binary(source_root / "全量法律.zip", b"zip")
    _write_binary(source_root / "医保目录" / "catalog.docx", b"docx")

    manifest = build_source_package_manifest(source_root, version_key="pending-test")

    pending_by_path = {file.relative_path: file for file in manifest.pending_files}
    assert pending_by_path["风险负面清单/医保负面清单.png"].reason == "unsupported-file-type"
    assert pending_by_path["全量法律.zip"].reason == "unsupported-file-type"
    assert pending_by_path["医保目录/catalog.docx"].media_type == "application/octet-stream"
    assert pending_by_path["医保目录/catalog.docx"].reason == "unsupported-file-type"


def test_collection_mapping_and_medical_law_keyword_filter() -> None:
    assert classify_source_collection(Path("医保目录/catalog.pdf")) == (
        SourceCollection.MEDICAL_INSURANCE_CATALOG
    )
    assert classify_source_collection(Path("全量法律/医疗机构管理条例.md")) == (
        SourceCollection.MEDICAL_INSURANCE_LAWS
    )
    # 全量入库：全量法律下的非医保文档也归入法律集合（不再返回 None 被丢弃）。
    assert classify_source_collection(Path("全量法律/人民检察院刑事诉讼规则.md")) == (
        SourceCollection.MEDICAL_INSURANCE_LAWS
    )
    assert is_medical_insurance_law("DRG付费分组方案.md")
    assert not is_medical_insurance_law("行政复议法.md")
    assert classify_source_collection(Path("policy-general-policy/通知.md")) == (
        SourceCollection.POLICY_GENERAL_POLICY
    )
    assert classify_source_collection(Path("management-general-admin/管理办法.md")) == (
        SourceCollection.MANAGEMENT_GENERAL_ADMIN
    )
    assert classify_source_collection(Path("other-education-research/教育条例.md")) == (
        SourceCollection.OTHER_EDUCATION_RESEARCH
    )


def test_classify_domain_taxonomy() -> None:
    # 策展三集合按来源即「医保基金」域。
    assert classify_domain("任意.md", SourceCollection.MEDICAL_INSURANCE_CATALOG) == "医保基金"
    assert classify_domain("任意.xlsx", SourceCollection.RISK_NEGATIVE_LIST) == "医保基金"
    # 广义法律语料按文件名分类（医保关键词→医保基金；否则按领域词；都不命中→其他）。
    laws = SourceCollection.MEDICAL_INSURANCE_LAWS
    assert classify_domain("医疗保障基金使用监督管理条例.md", laws) == "医保基金"
    assert classify_domain("价格违法行为行政处罚规定.md", laws) == "价格"
    assert classify_domain("财政违法行为处罚处分条例.md", laws) == "财政"
    assert classify_domain("政府采购法实施条例.md", laws) == "采购"
    assert classify_domain("中华人民共和国统计法.md", laws) == "统计"
    assert classify_domain("养犬管理条例.md", laws) == "其他"
    assert classify_domain("餐厨垃圾管理办法.md", laws) == "其他"
    assert classify_domain("通知.md", SourceCollection.POLICY_GENERAL_POLICY) == (
        "综合政策与规范性文件"
    )
    assert classify_domain("管理办法.md", SourceCollection.MANAGEMENT_GENERAL_ADMIN) == (
        "综合行政管理"
    )


def _write_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _write_binary(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path
