from __future__ import annotations

import json
import os
from collections.abc import Sequence
from typing import Literal

import httpx

from medical_audit_kb.generation.citations import Citation, citation_labels_in_text


class AnswerProviderError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: str = "provider_exception",
        http_status: int | None = None,
        reason: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.http_status = (
            http_status
            if isinstance(http_status, int) and 400 <= http_status <= 599
            else None
        )
        self.reason = reason if isinstance(reason, str) else None


ThinkingMode = Literal["enabled", "disabled"]

DEFAULT_THINKING_MODE_BY_PROVIDER: dict[str, ThinkingMode] = {
    "kimi": "enabled",
    "deepseek": "disabled",
}


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
        thinking_mode: ThinkingMode | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        if not api_key:
            raise AnswerProviderError(
                "answer generation api_key must be non-empty",
                code="provider_configuration",
            )
        if max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be positive")
        self.provider = provider
        self.model_name = model_name
        self.provider_version = provider_version
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._max_output_tokens = max_output_tokens
        self._temperature = temperature
        self._thinking_mode = thinking_mode or DEFAULT_THINKING_MODE_BY_PROVIDER.get(provider)
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
        thinking_mode: ThinkingMode | None = None,
    ) -> OpenAICompatibleAnswerGenerationProvider:
        api_key = os.getenv(api_key_env)
        if not api_key:
            raise AnswerProviderError(
                f"missing answer generation api key env: {api_key_env}",
                code="provider_configuration",
            )
        return cls(
            api_key=api_key,
            model_name=model_name,
            base_url=base_url,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
            thinking_mode=thinking_mode,
        )

    def generate_answer(self, question: str, citations: Sequence[Citation]) -> str:
        user_prompt = (
            _deepseek_user_prompt(question, citations)
            if self.provider == "deepseek"
            else _user_prompt(question, citations)
        )
        payload: dict[str, object] = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self._temperature,
        }
        token_field = "max_completion_tokens" if self.provider == "kimi" else "max_tokens"
        payload[token_field] = self._max_output_tokens
        if self._thinking_mode is not None:
            payload["thinking"] = {"type": self._thinking_mode}
        if self.provider == "deepseek":
            payload["response_format"] = {"type": "json_object"}
        try:
            response = self._http_client.post(
                f"{self._base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        except httpx.HTTPError as exc:
            raise AnswerProviderError(
                f"answer generation transport failed: {exc.__class__.__name__}",
                code="provider_transport",
            ) from exc
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise AnswerProviderError(
                f"answer generation request failed: HTTP {exc.response.status_code}",
                code="provider_http_status",
                http_status=exc.response.status_code,
            ) from exc

        response_payload = _response_json(response)
        if self.provider == "deepseek":
            return _deepseek_answer_content(response_payload, citations)
        return _answer_content(response_payload)


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
            raise AnswerProviderError(
                "answer generation api_key must be non-empty",
                code="provider_configuration",
            )
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
            raise AnswerProviderError(
                f"missing answer generation api key env: {api_key_env}",
                code="provider_configuration",
            )
        return cls(
            api_key=api_key,
            model_name=model_name,
            base_url=base_url,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
        )

    def generate_answer(self, question: str, citations: Sequence[Citation]) -> str:
        try:
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
                    "messages": [
                        {"role": "user", "content": _user_prompt(question, citations)}
                    ],
                    "temperature": self._temperature,
                    "max_tokens": self._max_output_tokens,
                },
            )
        except httpx.HTTPError as exc:
            raise AnswerProviderError(
                f"answer generation transport failed: {exc.__class__.__name__}",
                code="provider_transport",
            ) from exc
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise AnswerProviderError(
                f"answer generation request failed: HTTP {exc.response.status_code}",
                code="provider_http_status",
                http_status=exc.response.status_code,
            ) from exc

        return _anthropic_answer_content(_response_json(response))


_SYSTEM_PROMPT = """你是医保审计知识库答案生成器。
只能依据用户提供的引用片段回答，不得引入外部知识或自行推断。
每个事实性结论必须带引用标记，例如 [C1]。
最终答案至少包含一个来自可用引用列表的原样标记，不得只在推理内容中引用。
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
            "- 最终答案至少包含一个来自可用引用列表的原样标记。",
            "- 不得只在推理内容中引用，最终答案正文必须保留引用标记。",
            "- 不要输出未被引用支持的判断。",
        ]
    )
    return "\n".join(lines)


def _deepseek_user_prompt(question: str, citations: Sequence[Citation]) -> str:
    return "\n".join(
        [
            _user_prompt(question, citations),
            "",
            "请仅输出一个合法 json 对象，不要输出 Markdown 代码块或额外文字。",
            'json 结构必须为：{"answer":"带原样引用标记的最终答案 [C1]",'
            '"citation_ids":["C1"]}',
            "citation_ids 必须完整列出 answer 正文中出现的引用 ID，且只能使用可用引用。",
        ]
    )


def _answer_content(payload: object) -> str:
    if not isinstance(payload, dict):
        raise AnswerProviderError(
            "answer generation response root must be an object",
            code="provider_response_invalid",
            reason="response_root_not_object",
        )
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise AnswerProviderError(
            "answer generation response missing choices",
            code="provider_response_invalid",
            reason="response_choices_missing",
        )
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise AnswerProviderError(
            "answer generation choice must be an object",
            code="provider_response_invalid",
            reason="response_choice_not_object",
        )
    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise AnswerProviderError(
            "answer generation choice missing message",
            code="provider_response_invalid",
            reason="response_message_missing",
        )
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise AnswerProviderError(
            "answer generation message content must be non-empty",
            code="provider_response_invalid",
            reason="response_content_empty",
        )
    return content.strip()


def _response_json(response: httpx.Response) -> object:
    try:
        return response.json()
    except ValueError as exc:
        raise AnswerProviderError(
            "answer generation response body must be valid json",
            code="provider_response_invalid",
            reason="response_body_invalid_json",
        ) from exc


def _deepseek_answer_content(payload: object, citations: Sequence[Citation]) -> str:
    content = _answer_content(payload)
    try:
        structured = json.loads(content)
    except json.JSONDecodeError as exc:
        raise AnswerProviderError(
            "deepseek answer generation content must be valid json",
            code="provider_response_invalid",
            reason="deepseek_content_invalid_json",
        ) from exc
    if not isinstance(structured, dict):
        raise AnswerProviderError(
            "deepseek answer generation json root must be an object",
            code="provider_response_invalid",
            reason="deepseek_json_root_not_object",
        )

    answer = structured.get("answer")
    citation_ids = structured.get("citation_ids")
    if not isinstance(answer, str) or not answer.strip():
        raise AnswerProviderError(
            "deepseek answer generation json answer must be non-empty",
            code="provider_response_invalid",
            reason="deepseek_answer_empty",
        )
    if citation_ids not in (None, []) and (
        not isinstance(citation_ids, list)
        or not all(isinstance(citation_id, str) and citation_id for citation_id in citation_ids)
    ):
        raise AnswerProviderError(
            "deepseek answer generation json citation_ids must be strings",
            code="provider_response_invalid",
            reason="deepseek_citation_ids_invalid",
        )

    normalized_answer = answer.strip()
    available_ids = {citation.citation_id.upper() for citation in citations}
    visible_ids = citation_labels_in_text(normalized_answer)
    claimed_ids = (
        {citation_id.upper() for citation_id in citation_ids}
        if isinstance(citation_ids, list) and citation_ids
        else set()
    )
    if not visible_ids.issubset(available_ids) or not claimed_ids.issubset(available_ids):
        raise AnswerProviderError(
            "deepseek answer generation json contains unavailable citation ids",
            code="provider_response_invalid",
            reason="deepseek_citation_ids_unavailable",
        )
    if not visible_ids:
        raise AnswerProviderError(
            "deepseek answer generation json answer must contain citation markers",
            code="provider_response_invalid",
            reason="deepseek_citation_markers_mismatch",
        )
    return normalized_answer


def _anthropic_answer_content(payload: object) -> str:
    if not isinstance(payload, dict):
        raise AnswerProviderError(
            "answer generation response root must be an object",
            code="provider_response_invalid",
            reason="response_root_not_object",
        )
    content_blocks = payload.get("content")
    if not isinstance(content_blocks, list) or not content_blocks:
        raise AnswerProviderError(
            "answer generation response missing content",
            code="provider_response_invalid",
            reason="anthropic_content_missing",
        )
    text_parts: list[str] = []
    for block in content_blocks:
        if not isinstance(block, dict):
            raise AnswerProviderError(
                "answer generation content block must be an object",
                code="provider_response_invalid",
                reason="anthropic_content_block_not_object",
            )
        if block.get("type") != "text":
            continue
        text = block.get("text")
        if isinstance(text, str) and text.strip():
            text_parts.append(text.strip())
    answer = "\n".join(text_parts).strip()
    if not answer:
        raise AnswerProviderError(
            "answer generation message content must be non-empty",
            code="provider_response_invalid",
            reason="response_content_empty",
        )
    return answer
