from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

type EmbeddingVector = tuple[float, ...]

TOKEN_PATTERN = re.compile(r"[a-z0-9]+|[\u4e00-\u9fff]")


class EmbeddingProvider(Protocol):
    provider: str
    model_name: str
    provider_version: str
    dimension: int

    def embed_texts(self, texts: Sequence[str]) -> tuple[EmbeddingVector, ...]: ...


@dataclass(frozen=True, slots=True)
class EmbeddingMetadata:
    provider: str
    model_name: str
    provider_version: str
    dimension: int

    @classmethod
    def from_provider(cls, provider: EmbeddingProvider) -> EmbeddingMetadata:
        return cls(
            provider=provider.provider,
            model_name=provider.model_name,
            provider_version=provider.provider_version,
            dimension=provider.dimension,
        )


@dataclass(frozen=True, slots=True)
class DeterministicFakeEmbeddingProvider:
    dimension: int = 32
    provider: str = "fake"
    model_name: str = "deterministic-token-hashing"
    provider_version: str = "v1"

    def embed_texts(self, texts: Sequence[str]) -> tuple[EmbeddingVector, ...]:
        return tuple(self._embed_text(text) for text in texts)

    def _embed_text(self, text: str) -> EmbeddingVector:
        if self.dimension <= 0:
            raise ValueError("embedding dimension must be positive")

        vector = [0.0 for _ in range(self.dimension)]
        tokens = tokenize_text(text)
        if not tokens:
            return tuple(vector)

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = digest[0] % self.dimension
            sign = 1.0 if digest[1] % 2 == 0 else -1.0
            vector[index] += sign

        return normalize_vector(tuple(vector))


def tokenize_text(text: str) -> tuple[str, ...]:
    normalized = text.lower()
    base_tokens = [match.group(0) for match in TOKEN_PATTERN.finditer(normalized)]
    cjk_text = "".join(token for token in base_tokens if _is_cjk_token(token))
    cjk_bigrams = [cjk_text[index : index + 2] for index in range(max(0, len(cjk_text) - 1))]
    return tuple(base_tokens + cjk_bigrams)


def cosine_similarity(left: EmbeddingVector, right: EmbeddingVector) -> float:
    if len(left) != len(right):
        raise ValueError("vectors must have the same dimension")
    left_norm = vector_norm(left)
    right_norm = vector_norm(right)
    if left_norm == 0 or right_norm == 0:
        return 0.0
    dot = sum(left_value * right_value for left_value, right_value in zip(left, right, strict=True))
    return dot / (left_norm * right_norm)


def normalize_vector(vector: EmbeddingVector) -> EmbeddingVector:
    norm = vector_norm(vector)
    if norm == 0:
        return vector
    return tuple(value / norm for value in vector)


def vector_norm(vector: EmbeddingVector) -> float:
    return math.sqrt(sum(value * value for value in vector))


def _is_cjk_token(token: str) -> bool:
    return len(token) == 1 and "\u4e00" <= token <= "\u9fff"
