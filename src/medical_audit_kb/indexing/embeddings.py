from __future__ import annotations

import hashlib
import math
import os
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

import httpx

type EmbeddingVector = tuple[float, ...]

TOKEN_PATTERN = re.compile(r"[a-z]\d{2}(?:\.\d+[a-z0-9+*]*)?|[a-z0-9]+|[\u4e00-\u9fff]")


class EmbeddingProvider(Protocol):
    @property
    def provider(self) -> str: ...

    @property
    def model_name(self) -> str: ...

    @property
    def provider_version(self) -> str: ...

    @property
    def dimension(self) -> int: ...

    def embed_texts(self, texts: Sequence[str]) -> tuple[EmbeddingVector, ...]: ...


class EmbeddingProviderError(RuntimeError):
    pass


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


class OpenAICompatibleEmbeddingProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model_name: str,
        dimension: int | None = None,
        base_url: str = "https://api.openai.com/v1",
        provider: str = "openai",
        provider_version: str = "v1",
        batch_size: int = 128,
        timeout_seconds: float = 60.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        if not api_key:
            raise EmbeddingProviderError("embedding api_key must be non-empty")
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        self.provider = provider
        self.model_name = model_name
        self.provider_version = provider_version
        self.dimension = dimension or _default_openai_embedding_dimension(model_name)
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._batch_size = batch_size
        self._http_client = http_client or httpx.Client(timeout=timeout_seconds)

    @property
    def batch_size(self) -> int:
        return self._batch_size

    @classmethod
    def from_env(
        cls,
        *,
        api_key_env: str,
        model_name: str,
        dimension: int | None = None,
        base_url: str = "https://api.openai.com/v1",
        batch_size: int = 128,
    ) -> OpenAICompatibleEmbeddingProvider:
        api_key = os.getenv(api_key_env)
        if not api_key:
            raise EmbeddingProviderError(f"missing embedding api key env: {api_key_env}")
        return cls(
            api_key=api_key,
            model_name=model_name,
            dimension=dimension,
            base_url=base_url,
            batch_size=batch_size,
        )

    def embed_texts(self, texts: Sequence[str]) -> tuple[EmbeddingVector, ...]:
        embeddings: list[EmbeddingVector] = []
        for batch in _batches(tuple(texts), self._batch_size):
            embeddings.extend(self._embed_batch(batch))
        return tuple(embeddings)

    def _embed_batch(self, texts: tuple[str, ...]) -> tuple[EmbeddingVector, ...]:
        response = self._http_client.post(
            f"{self._base_url}/embeddings",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json={"model": self.model_name, "input": list(texts)},
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise EmbeddingProviderError(
                f"embedding request failed: {exc.response.status_code} {exc.response.text}"
            ) from exc

        payload = response.json()
        data = payload.get("data")
        if not isinstance(data, list):
            raise EmbeddingProviderError("embedding response missing data list")
        sorted_items = sorted(data, key=lambda item: int(item.get("index", 0)))
        vectors = tuple(_embedding_vector(item, dimension=self.dimension) for item in sorted_items)
        if len(vectors) != len(texts):
            raise EmbeddingProviderError(
                f"embedding response count mismatch: expected {len(texts)}, got {len(vectors)}"
            )
        return vectors


def tokenize_text(text: str) -> tuple[str, ...]:
    normalized = text.lower()
    base_tokens = [match.group(0) for match in TOKEN_PATTERN.finditer(normalized)]
    cjk_text = "".join(token for token in base_tokens if _is_cjk_token(token))
    cjk_bigrams = [cjk_text[index : index + 2] for index in range(max(0, len(cjk_text) - 1))]
    return tuple(base_tokens + cjk_bigrams)


def _batches(items: tuple[str, ...], batch_size: int) -> tuple[tuple[str, ...], ...]:
    return tuple(items[index : index + batch_size] for index in range(0, len(items), batch_size))


def _embedding_vector(item: object, *, dimension: int) -> EmbeddingVector:
    if not isinstance(item, dict):
        raise EmbeddingProviderError("embedding data item must be an object")
    raw_embedding = item.get("embedding")
    if not isinstance(raw_embedding, list):
        raise EmbeddingProviderError("embedding data item missing embedding list")
    vector = tuple(float(value) for value in raw_embedding)
    if len(vector) != dimension:
        raise EmbeddingProviderError(
            f"embedding dimension mismatch: expected {dimension}, got {len(vector)}"
        )
    return vector


def _default_openai_embedding_dimension(model_name: str) -> int:
    if model_name == "text-embedding-3-small":
        return 1536
    if model_name == "text-embedding-3-large":
        return 3072
    raise EmbeddingProviderError(f"embedding dimension must be provided for model: {model_name}")


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
