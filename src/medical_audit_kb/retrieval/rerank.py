from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, cast
from uuid import UUID

from medical_audit_kb.indexing.embeddings import tokenize_text


@dataclass(frozen=True, slots=True)
class RerankCandidate:
    chunk_id: UUID
    text: str
    metadata: dict[str, object]
    base_score: float


@dataclass(frozen=True, slots=True)
class RerankScore:
    chunk_id: UUID
    score: float


class RerankProvider(Protocol):
    @property
    def provider(self) -> str: ...

    @property
    def model_name(self) -> str: ...

    @property
    def provider_version(self) -> str: ...

    def rerank(
        self,
        query: str,
        candidates: Sequence[RerankCandidate],
    ) -> tuple[RerankScore, ...]: ...


@dataclass(frozen=True, slots=True)
class FakeRerankProvider:
    provider: str = "fake"
    model_name: str = "token-overlap-reranker"
    provider_version: str = "v1"

    def rerank(self, query: str, candidates: Sequence[RerankCandidate]) -> tuple[RerankScore, ...]:
        query_tokens = set(tokenize_text(query))
        scores: list[RerankScore] = []
        for candidate in candidates:
            candidate_tokens = set(tokenize_text(candidate.text))
            overlap = len(query_tokens.intersection(candidate_tokens))
            denominator = max(len(query_tokens), 1)
            overlap_score = overlap / denominator
            scores.append(
                RerankScore(
                    chunk_id=candidate.chunk_id,
                    score=(candidate.base_score * 0.7) + (overlap_score * 0.3),
                )
            )
        return tuple(sorted(scores, key=lambda item: item.score, reverse=True))


_QUERY_TERM_RE = re.compile(r"[A-Za-z0-9]+(?:[._/-][A-Za-z0-9]+)*")
_DOMAIN_CODE_RE = re.compile(r"[A-Za-z]+\d+(?:\.\d+)?")


def _query_domain_codes(query: str) -> frozenset[str]:
    """提取问题中的领域编码（如 ICD ``A00.0``、``I10``、DRG ``0000``）。

    规则与 ``answer_builder._is_domain_code`` 对齐：``ICD-10`` 整体视为版本词而非编码，
    版本号 ``2.0`` 不算编码；保留纯数字码与字母+数字码。
    """
    codes: set[str] = set()
    for token in _QUERY_TERM_RE.findall(query):
        if token.upper().startswith("ICD"):
            continue
        if token.isdigit() or _DOMAIN_CODE_RE.fullmatch(token):
            codes.add(token.upper())
    return frozenset(codes)


@dataclass(frozen=True, slots=True)
class DomainAwareRerankProvider:
    """确定性、零外部依赖的启发式 reranker：在 base_score 上叠加“精确领域编码命中”强信号。

    针对 pgvector 弱召回（正确 chunk 含精确编码但被弱相关 OCR 压低）：含问题精确编码的
    候选获得显著加权而上浮；非编码类问题退化为 base_score + 轻量词覆盖（与 Fake 同量级）。
    仍属 base/词面信号，不是 cross-encoder；作为零依赖的召回排序改进与 A/B 基线。
    """

    provider: str = "heuristic"
    model_name: str = "domain-code-aware-reranker"
    provider_version: str = "v1"
    code_weight: float = 1.0
    term_weight: float = 0.2

    def rerank(self, query: str, candidates: Sequence[RerankCandidate]) -> tuple[RerankScore, ...]:
        codes = _query_domain_codes(query)
        query_tokens = set(tokenize_text(query))
        denominator = max(len(query_tokens), 1)
        scores: list[RerankScore] = []
        for candidate in candidates:
            text_upper = candidate.text.upper()
            code_signal = (
                sum(1 for code in codes if code in text_upper) / len(codes) if codes else 0.0
            )
            candidate_tokens = set(tokenize_text(candidate.text))
            term_coverage = len(query_tokens & candidate_tokens) / denominator
            score = (
                candidate.base_score
                + (self.code_weight * code_signal)
                + (self.term_weight * term_coverage)
            )
            scores.append(RerankScore(chunk_id=candidate.chunk_id, score=score))
        return tuple(sorted(scores, key=lambda item: item.score, reverse=True))


def rerank_provider_from_name(name: str) -> RerankProvider | None:
    """按名称构造 reranker：``fake``（生产现默认）/``domain``（A1 候选）/``none``（禁用）。"""
    normalized = name.strip().lower()
    if normalized in {"none", "off", ""}:
        return None
    if normalized in {"fake", "token-overlap"}:
        return cast(RerankProvider, FakeRerankProvider())
    if normalized in {"domain", "domain-code", "heuristic"}:
        return cast(RerankProvider, DomainAwareRerankProvider())
    raise ValueError(f"unknown rerank provider: {name}")
