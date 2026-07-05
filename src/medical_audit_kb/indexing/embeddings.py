from __future__ import annotations

import hashlib
import math
import os
import re
import time
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


class _RetryableEmbeddingProviderError(EmbeddingProviderError):
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
        max_retries: int = 3,
        retry_base_delay_seconds: float = 1.0,
    ) -> None:
        if not api_key:
            raise EmbeddingProviderError("embedding api_key must be non-empty")
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        if retry_base_delay_seconds < 0:
            raise ValueError("retry_base_delay_seconds must be non-negative")
        self.provider = provider
        self.model_name = model_name
        self.provider_version = provider_version
        self.dimension = dimension or _default_openai_embedding_dimension(model_name)
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._batch_size = batch_size
        self._max_retries = max_retries
        self._retry_base_delay_seconds = retry_base_delay_seconds
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
            embeddings.extend(self._embed_batch_with_adaptive_split(batch))
        return tuple(embeddings)

    def _embed_batch_with_adaptive_split(
        self,
        texts: tuple[str, ...],
    ) -> tuple[EmbeddingVector, ...]:
        try:
            return self._embed_batch(texts)
        except _RetryableEmbeddingProviderError:
            if len(texts) <= 1:
                raise
            midpoint = len(texts) // 2
            return self._embed_batch_with_adaptive_split(
                texts[:midpoint]
            ) + self._embed_batch_with_adaptive_split(texts[midpoint:])

    def _embed_batch(self, texts: tuple[str, ...]) -> tuple[EmbeddingVector, ...]:
        for attempt_index in range(self._max_retries + 1):
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
                if attempt_index < self._max_retries and _is_retryable_status(
                    exc.response.status_code
                ):
                    self._sleep_before_retry(attempt_index, exc.response)
                    continue
                if _is_retryable_status(exc.response.status_code):
                    raise _RetryableEmbeddingProviderError(
                        f"embedding request failed: {exc.response.status_code} {exc.response.text}"
                    ) from exc
                raise EmbeddingProviderError(
                    f"embedding request failed: {exc.response.status_code} {exc.response.text}"
                ) from exc

            try:
                payload = response.json()
            except ValueError as exc:
                if attempt_index < self._max_retries:
                    self._sleep_before_retry(attempt_index, response)
                    continue
                raise _RetryableEmbeddingProviderError(
                    f"embedding response invalid json: {_response_text_excerpt(response)}"
                ) from exc

            data = payload.get("data") if isinstance(payload, dict) else None
            if not isinstance(data, list):
                if attempt_index < self._max_retries:
                    self._sleep_before_retry(attempt_index, response)
                    continue
                raise _RetryableEmbeddingProviderError(
                    f"embedding response missing data list: {_response_text_excerpt(response)}"
                )
            sorted_items = sorted(data, key=lambda item: int(item.get("index", 0)))
            vectors = tuple(
                _embedding_vector(item, dimension=self.dimension) for item in sorted_items
            )
            if len(vectors) != len(texts):
                if attempt_index < self._max_retries:
                    self._sleep_before_retry(attempt_index, response)
                    continue
                raise _RetryableEmbeddingProviderError(
                    f"embedding response count mismatch: expected {len(texts)}, got {len(vectors)}"
                )
            return vectors

        raise EmbeddingProviderError("embedding request retry loop exhausted")

    def _sleep_before_retry(self, attempt_index: int, response: httpx.Response) -> None:
        if self._retry_base_delay_seconds == 0:
            return
        retry_after = _retry_after_seconds(response)
        delay = retry_after if retry_after is not None else self._retry_base_delay_seconds * (
            2**attempt_index
        )
        time.sleep(delay)


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


def _is_retryable_status(status_code: int) -> bool:
    return status_code == 429 or 500 <= status_code <= 599


def _retry_after_seconds(response: httpx.Response) -> float | None:
    value = response.headers.get("retry-after")
    if value is None:
        return None
    try:
        seconds = float(value)
    except ValueError:
        return None
    return max(0.0, seconds)


def _response_text_excerpt(response: httpx.Response, *, limit: int = 500) -> str:
    text = response.text.replace("\n", " ")
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


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
