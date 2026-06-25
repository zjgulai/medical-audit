"""专题（topic）配置：从底层分类知识库按 domain 切片出的命名专题。

底层分类库给每篇文档打 `domain` 领域标签（见 ingestion/inventory.classify_domain）。
专题 = 命名的「domain 域集 + 来源加权 + 存量兜底集」，在检索层把全库收窄到该专题：
- domains：纳入专题的领域标签集合；
- fallback_collections：存量无 domain 标签的 chunk 按 source_collection 兜底纳入；
- source_collection_weights：专题内来源加权（A2），让医保策展集合排序更靠前。
新增专题只是多一份配置，不改检索引擎。
"""

from __future__ import annotations

from dataclasses import dataclass

from medical_audit_kb.domain.constants import SourceCollection
from medical_audit_kb.retrieval.filters import RetrievalFilters


@dataclass(frozen=True, slots=True)
class KnowledgeTopic:
    key: str
    label: str
    domains: tuple[str, ...]
    fallback_collections: tuple[SourceCollection, ...]
    source_collection_weights: dict[str, float]

    def retrieval_filters(self) -> RetrievalFilters:
        """构造把检索收窄到本专题的过滤器（domain 命中或存量来源兜底）。"""
        return RetrievalFilters(
            domains=self.domains,
            domain_fallback_collections=self.fallback_collections,
        )


# 医保基金专题：第一个专题。域集涵盖医保及与医保基金审计强相关的旁域（价格/财政/会计审计/
# 国资/采购/税），排除「统计」「其他」（养犬/餐厨垃圾等不进专题）。存量 49051 医保 chunk
# 无 domain 标签，靠四个医保策展集合兜底纳入。
MEDICAL_INSURANCE_FUND_TOPIC = KnowledgeTopic(
    key="medical-insurance-fund",
    label="医保基金专题",
    domains=("医保基金", "价格", "财政", "会计审计", "国资", "采购", "税"),
    fallback_collections=(
        SourceCollection.MEDICAL_INSURANCE_CATALOG,
        SourceCollection.SUPERVISION_RULES_KNOWLEDGE,
        SourceCollection.RISK_NEGATIVE_LIST,
        SourceCollection.MEDICAL_INSURANCE_LAWS,
    ),
    source_collection_weights={
        SourceCollection.SUPERVISION_RULES_KNOWLEDGE.value: 1.4,
        SourceCollection.MEDICAL_INSURANCE_CATALOG.value: 1.3,
        SourceCollection.RISK_NEGATIVE_LIST.value: 1.15,
        SourceCollection.MEDICAL_INSURANCE_LAWS.value: 1.0,
    },
)

TOPICS: dict[str, KnowledgeTopic] = {topic.key: topic for topic in (MEDICAL_INSURANCE_FUND_TOPIC,)}


def get_topic(key: str | None) -> KnowledgeTopic | None:
    """按 key 取专题；key 为空或未知返回 None（= 不收窄，查全库）。"""
    if not key:
        return None
    return TOPICS.get(key)
