from __future__ import annotations

from medical_audit_kb.domain.constants import SourceCollection
from medical_audit_kb.ingestion.inventory import (
    DOMAIN_MEDICAL_INSURANCE,
    OTHER_DOMAIN_KEYWORDS,
)
from medical_audit_kb.retrieval.filters import RetrievalFilters
from medical_audit_kb.retrieval.topics import (
    MEDICAL_INSURANCE_FUND_TOPIC,
    get_topic,
)


def test_domain_filter_includes_matching_and_excludes_other() -> None:
    filters = RetrievalFilters(domains=("医保基金", "价格"))
    assert filters.matches({"domain": "医保基金", "source_collection": "medical-insurance-laws"})
    assert filters.matches({"domain": "价格", "source_collection": "medical-insurance-laws"})
    # 不在专题域集 → 排除（养犬等归「其他」）。
    assert not filters.matches({"domain": "其他", "source_collection": "medical-insurance-laws"})
    assert not filters.matches({"domain": "统计", "source_collection": "medical-insurance-laws"})
    assert not filters.is_empty


def test_domain_filter_tolerant_fallback_for_legacy_chunks() -> None:
    # 存量 chunk 无 domain 标签：source_collection 属兜底集 → 纳入；否则排除。
    filters = RetrievalFilters(
        domains=("医保基金",),
        domain_fallback_collections=(
            SourceCollection.MEDICAL_INSURANCE_CATALOG,
            SourceCollection.MEDICAL_INSURANCE_LAWS,
        ),
    )
    # 无 domain，兜底命中医保策展集 → 纳入。
    assert filters.matches({"source_collection": "medical-insurance-catalog"})
    assert filters.matches({"domain": "", "source_collection": "medical-insurance-laws"})
    # 无 domain，兜底未命中 → 排除。
    assert not filters.matches({"source_collection": "personal-materials"})
    # 新 chunk 带 domain="其他" 不走兜底（domain 存在即按 domain 判，排除）。
    assert not filters.matches({"domain": "其他", "source_collection": "medical-insurance-catalog"})


def test_medical_insurance_fund_topic_filters_and_lookup() -> None:
    topic = get_topic("medical-insurance-fund")
    assert topic is MEDICAL_INSURANCE_FUND_TOPIC
    assert get_topic(None) is None
    assert get_topic("unknown") is None

    filters = topic.retrieval_filters()
    assert "医保基金" in filters.domains
    assert SourceCollection.MEDICAL_INSURANCE_CATALOG in filters.domain_fallback_collections
    # 医保策展集合权重高于广义法律集合。
    weights = topic.source_collection_weights
    assert (
        weights[SourceCollection.SUPERVISION_RULES_KNOWLEDGE.value]
        > (weights[SourceCollection.MEDICAL_INSURANCE_LAWS.value])
    )


def test_topic_domains_are_known_vocabulary() -> None:
    # 专题域集必须是分类器已知领域（医保基金 + OTHER_DOMAIN_KEYWORDS 的键），防笔误/漂移。
    known = {DOMAIN_MEDICAL_INSURANCE, *(name for name, _ in OTHER_DOMAIN_KEYWORDS)}
    assert set(MEDICAL_INSURANCE_FUND_TOPIC.domains).issubset(known)
