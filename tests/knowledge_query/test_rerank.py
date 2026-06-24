from __future__ import annotations

from uuid import UUID

import pytest

from medical_audit_kb.retrieval.rerank import (
    DomainAwareRerankProvider,
    RerankCandidate,
    rerank_provider_from_name,
)


def _chunk_id(value: int) -> UUID:
    return UUID(int=value)


def test_domain_reranker_lifts_exact_code_chunk_above_higher_base_noise() -> None:
    provider = DomainAwareRerankProvider()
    correct = RerankCandidate(
        chunk_id=_chunk_id(1),
        text="A00.0 霍乱，由于O1群霍乱弧菌所致",
        metadata={},
        base_score=0.40,
    )
    noise = RerankCandidate(
        chunk_id=_chunk_id(2),
        text="ICD-9-CM3 手术操作编码 86.22 创面清创术 无关内容",
        metadata={},
        base_score=0.90,
    )

    ranked = provider.rerank("ICD-10医保2.0版中 A00.0 对应什么诊断？", (noise, correct))

    # 含精确编码 A00.0 的正确 chunk 应上浮到首位，尽管其 base_score 更低。
    assert ranked[0].chunk_id == _chunk_id(1)
    assert ranked[0].score > ranked[1].score


def test_domain_reranker_keeps_base_ranking_when_query_has_no_codes() -> None:
    provider = DomainAwareRerankProvider()
    high_base = RerankCandidate(
        chunk_id=_chunk_id(2),
        text="负面清单：超量开药 指超过规定剂量开具药品",
        metadata={},
        base_score=0.80,
    )
    low_base = RerankCandidate(
        chunk_id=_chunk_id(1),
        text="完全无关的条目",
        metadata={},
        base_score=0.20,
    )

    ranked = provider.rerank("医保负面清单中超量开药是如何定义的？", (low_base, high_base))

    # 无领域编码时按 base + 词覆盖排序，高 base 的相关候选保持在前，不被错误压制。
    assert ranked[0].chunk_id == _chunk_id(2)
    assert {score.chunk_id for score in ranked} == {_chunk_id(1), _chunk_id(2)}


def test_domain_reranker_preserves_all_candidates() -> None:
    provider = DomainAwareRerankProvider()
    candidates = tuple(
        RerankCandidate(
            chunk_id=_chunk_id(index),
            text=f"chunk {index}",
            metadata={},
            base_score=0.1 * index,
        )
        for index in range(1, 5)
    )

    ranked = provider.rerank("任意问题", candidates)

    assert len(ranked) == len(candidates)
    assert {score.chunk_id for score in ranked} == {c.chunk_id for c in candidates}


def test_rerank_provider_factory_selects_implementation() -> None:
    assert rerank_provider_from_name("none") is None

    fake = rerank_provider_from_name("fake")
    assert fake is not None and fake.model_name == "token-overlap-reranker"

    domain = rerank_provider_from_name("domain")
    assert domain is not None and domain.model_name == "domain-code-aware-reranker"

    with pytest.raises(ValueError, match="unknown rerank provider"):
        rerank_provider_from_name("bogus")
