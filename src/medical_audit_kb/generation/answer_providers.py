from __future__ import annotations

import os
from collections.abc import Sequence

import httpx

from medical_audit_kb.generation.citations import Citation


class AnswerProviderError(RuntimeError):
    pass


class OpenAICompatibleAnswerGenerationProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model_name: str,
        base_url: str = "https://api.openai.com/v1",
        provider: str = "openai",
        provider_version: str = "v1",
        timeout_seconds: float = 120.0,
        max_output_tokens: int = 600,
        temperature: float = 0.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        if not api_key:
            raise AnswerProviderError("answer generation api_key must be non-empty")
        if max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be positive")
        self.provider = provider
        self.model_name = model_name
        self.provider_version = provider_version
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._max_output_tokens = max_output_tokens
        self._temperature = temperature
        self._http_client = http_client or httpx.Client(timeout=timeout_seconds)

    @classmethod
    def from_env(
        cls,
        *,
        api_key_env: str,
        model_name: str,
        base_url: str = "https://api.openai.com/v1",
        max_output_tokens: int = 600,
        temperature: float = 0.0,
    ) -> OpenAICompatibleAnswerGenerationProvider:
        api_key = os.getenv(api_key_env)
        if not api_key:
            raise AnswerProviderError(f"missing answer generation api key env: {api_key_env}")
        return cls(
            api_key=api_key,
            model_name=model_name,
            base_url=base_url,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
        )

    def generate_answer(self, question: str, citations: Sequence[Citation]) -> str:
        response = self._http_client.post(
            f"{self._base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model_name,
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": _user_prompt(question, citations)},
                ],
                "temperature": self._temperature,
                "max_tokens": self._max_output_tokens,
            },
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise AnswerProviderError(
                f"answer generation request failed: {exc.response.status_code} {exc.response.text}"
            ) from exc

        return _answer_content(response.json())


class AnthropicAnswerGenerationProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model_name: str,
        base_url: str = "https://api.anthropic.com",
        provider: str = "anthropic",
        provider_version: str = "2023-06-01",
        timeout_seconds: float = 120.0,
        max_output_tokens: int = 600,
        temperature: float = 0.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        if not api_key:
            raise AnswerProviderError("answer generation api_key must be non-empty")
        if max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be positive")
        self.provider = provider
        self.model_name = model_name
        self.provider_version = provider_version
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._max_output_tokens = max_output_tokens
        self._temperature = temperature
        self._http_client = http_client or httpx.Client(timeout=timeout_seconds)

    @classmethod
    def from_env(
        cls,
        *,
        api_key_env: str,
        model_name: str,
        base_url: str = "https://api.anthropic.com",
        max_output_tokens: int = 600,
        temperature: float = 0.0,
    ) -> AnthropicAnswerGenerationProvider:
        api_key = os.getenv(api_key_env)
        if not api_key:
            raise AnswerProviderError(f"missing answer generation api key env: {api_key_env}")
        return cls(
            api_key=api_key,
            model_name=model_name,
            base_url=base_url,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
        )

    def generate_answer(self, question: str, citations: Sequence[Citation]) -> str:
        response = self._http_client.post(
            f"{self._base_url}/v1/messages",
            headers={
                "x-api-key": self._api_key,
                "anthropic-version": self.provider_version,
                "content-type": "application/json",
            },
            json={
                "model": self.model_name,
                "system": _SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": _user_prompt(question, citations)}],
                "temperature": self._temperature,
                "max_tokens": self._max_output_tokens,
            },
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise AnswerProviderError(
                f"answer generation request failed: {exc.response.status_code} {exc.response.text}"
            ) from exc

        return _anthropic_answer_content(response.json())


_SYSTEM_PROMPT = """你是医保审计知识库答案生成器。
只能依据用户提供的引用片段回答，不得引入外部知识或自行推断。
每个事实性结论必须带引用标记，例如 [C1]。
如果引用不足以回答问题，必须回答：依据不足，当前知识库未检索到足够可引用依据，拒绝生成结论。
回答保持简洁，优先直接回答问题。"""


def _user_prompt(question: str, citations: Sequence[Citation]) -> str:
    lines = [
        f"问题：{question}",
        "",
        "可用引用：",
    ]
    for citation in citations:
        lines.append(f"{citation.marker} {citation.snippet}")
    lines.extend(
        [
            "",
            "输出要求：",
            "- 只基于可用引用回答。",
            "- 必须在关键结论后使用引用标记。",
            "- 不要输出未被引用支持的判断。",
        ]
    )
    return "\n".join(lines)


def _answer_content(payload: object) -> str:
    if not isinstance(payload, dict):
        raise AnswerProviderError("answer generation response root must be an object")
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise AnswerProviderError("answer generation response missing choices")
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise AnswerProviderError("answer generation choice must be an object")
    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise AnswerProviderError("answer generation choice missing message")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise AnswerProviderError("answer generation message content must be non-empty")
    return content.strip()


def _anthropic_answer_content(payload: object) -> str:
    if not isinstance(payload, dict):
        raise AnswerProviderError("answer generation response root must be an object")
    content_blocks = payload.get("content")
    if not isinstance(content_blocks, list) or not content_blocks:
        raise AnswerProviderError("answer generation response missing content")
    text_parts: list[str] = []
    for block in content_blocks:
        if not isinstance(block, dict):
            raise AnswerProviderError("answer generation content block must be an object")
        if block.get("type") != "text":
            continue
        text = block.get("text")
        if isinstance(text, str) and text.strip():
            text_parts.append(text.strip())
    answer = "\n".join(text_parts).strip()
    if not answer:
        raise AnswerProviderError("answer generation message content must be non-empty")
    return answer
