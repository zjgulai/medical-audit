from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict

from medical_audit_kb.generation.answer_builder import AnswerGenerationProvider
from medical_audit_kb.generation.answer_providers import (
    OpenAICompatibleAnswerGenerationProvider,
    ThinkingMode,
)
from medical_audit_kb.generation.citations import Citation


class ChatModelAlias(StrEnum):
    KIMI_2_7 = "kimi-2.7"
    DEEPSEEK_V4_PRO = "deepseek-v4-pro"


DEFAULT_CHAT_MODEL_ALIAS = ChatModelAlias.KIMI_2_7
ALLOW_FAKE_CHAT_MODELS_ENV = "MEDICAL_AUDIT_KB_ALLOW_FAKE_CHAT_MODELS"
CHAT_MODEL_ALIASES: tuple[ChatModelAlias, ...] = (
    ChatModelAlias.KIMI_2_7,
    ChatModelAlias.DEEPSEEK_V4_PRO,
)


DEFAULT_BASE_URL_BY_ALIAS: dict[ChatModelAlias, str] = {
    ChatModelAlias.KIMI_2_7: "https://api.moonshot.cn/v1",
    ChatModelAlias.DEEPSEEK_V4_PRO: "https://api.deepseek.com",
}

DEFAULT_MODEL_BY_ALIAS: dict[ChatModelAlias, str] = {
    ChatModelAlias.KIMI_2_7: "kimi-k2.6",
    ChatModelAlias.DEEPSEEK_V4_PRO: "deepseek-v4-pro",
}

DEFAULT_TEMPERATURE_BY_ALIAS: dict[ChatModelAlias, float] = {
    ChatModelAlias.KIMI_2_7: 1.0,
    ChatModelAlias.DEEPSEEK_V4_PRO: 0.0,
}

DEFAULT_MAX_OUTPUT_TOKENS_BY_ALIAS: dict[ChatModelAlias, int] = {
    ChatModelAlias.KIMI_2_7: 4096,
    ChatModelAlias.DEEPSEEK_V4_PRO: 900,
}

MIN_OUTPUT_TOKENS_BY_ALIAS: dict[ChatModelAlias, int] = {
    ChatModelAlias.KIMI_2_7: 4096,
}

DEFAULT_THINKING_MODE_BY_ALIAS: dict[ChatModelAlias, ThinkingMode] = {
    ChatModelAlias.KIMI_2_7: "enabled",
    ChatModelAlias.DEEPSEEK_V4_PRO: "disabled",
}

REQUIRED_THINKING_MODE_BY_ALIAS: dict[ChatModelAlias, ThinkingMode] = {
    ChatModelAlias.KIMI_2_7: "enabled",
    ChatModelAlias.DEEPSEEK_V4_PRO: "disabled",
}

DEFAULT_PROVIDER_BY_ALIAS: dict[ChatModelAlias, str] = {
    ChatModelAlias.KIMI_2_7: "kimi",
    ChatModelAlias.DEEPSEEK_V4_PRO: "deepseek",
}

MODEL_LABEL_BY_ALIAS: dict[ChatModelAlias, str] = {
    ChatModelAlias.KIMI_2_7: "Kimi K2.6（兼容别名）",
    ChatModelAlias.DEEPSEEK_V4_PRO: "DeepSeek V4 Pro",
}


class ChatModelUnavailableError(RuntimeError):
    def __init__(self, alias: ChatModelAlias, reason: str) -> None:
        super().__init__(f"chat model {alias.value} is unavailable: {reason}")
        self.alias = alias
        self.reason = reason


class ChatModelCatalogItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alias: ChatModelAlias
    label: str
    provider: str | None
    available: bool
    default: bool
    unavailable_reason: str | None = None


class ChatModelCatalogResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["chat-model-catalog-v1"] = "chat-model-catalog-v1"
    default_model: ChatModelAlias
    items: list[ChatModelCatalogItem]
    boundaries: dict[str, bool | str]


@dataclass(frozen=True, slots=True)
class ChatModelConfig:
    alias: ChatModelAlias
    provider: str
    api_key_env: str
    model_name: str
    base_url: str
    max_output_tokens: int
    temperature: float
    thinking_mode: ThinkingMode


def chat_model_catalog_response() -> ChatModelCatalogResponse:
    return ChatModelCatalogResponse(
        default_model=DEFAULT_CHAT_MODEL_ALIAS,
        items=[_catalog_item(alias) for alias in CHAT_MODEL_ALIASES],
        boundaries={
            "production_write": False,
            "provider_call": False,
            "secret_values_reported": False,
            "source": "environment_capability_probe_only",
        },
    )


def answer_generation_provider_for_alias(alias: ChatModelAlias) -> AnswerGenerationProvider:
    config, reason = chat_model_config_from_env(alias)
    if config is None:
        raise ChatModelUnavailableError(alias, reason or "invalid_configuration")
    if config.provider == "fake":
        return _FakeChatModelAnswerProvider(alias)
    api_key = os.getenv(config.api_key_env, "")
    if not api_key:
        raise ChatModelUnavailableError(alias, "missing_api_key")
    return OpenAICompatibleAnswerGenerationProvider(
        api_key=api_key,
        model_name=config.model_name,
        base_url=config.base_url,
        provider=config.provider,
        max_output_tokens=config.max_output_tokens,
        temperature=config.temperature,
        thinking_mode=config.thinking_mode,
    )


def chat_model_config_from_env(alias: ChatModelAlias) -> tuple[ChatModelConfig | None, str | None]:
    prefix = _env_prefix(alias)
    api_key_env = os.getenv(f"{prefix}_API_KEY_ENV", "").strip()
    if not api_key_env:
        return None, "missing_api_key_env"
    if not os.getenv(api_key_env):
        return None, "missing_api_key"

    provider = os.getenv(f"{prefix}_PROVIDER", _default_provider(alias)).strip().lower()
    model_name = os.getenv(f"{prefix}_MODEL", DEFAULT_MODEL_BY_ALIAS[alias]).strip()
    base_url = os.getenv(f"{prefix}_BASE_URL", DEFAULT_BASE_URL_BY_ALIAS[alias]).strip()
    if not provider:
        return None, "missing_provider"
    if provider == "fake" and os.getenv(ALLOW_FAKE_CHAT_MODELS_ENV) != "1":
        return None, "fake_provider_not_allowed"
    if not model_name:
        return None, "missing_model_name"
    if not base_url:
        return None, "missing_base_url"
    thinking_mode_value = os.getenv(
        f"{prefix}_THINKING_MODE",
        DEFAULT_THINKING_MODE_BY_ALIAS[alias],
    ).strip().lower()
    if thinking_mode_value not in {"enabled", "disabled"}:
        return None, "invalid_thinking_mode"
    if thinking_mode_value != REQUIRED_THINKING_MODE_BY_ALIAS[alias]:
        return None, "unsupported_thinking_mode"
    thinking_mode: ThinkingMode = "enabled" if thinking_mode_value == "enabled" else "disabled"
    max_output_tokens = _int_env(
        f"{prefix}_MAX_OUTPUT_TOKENS",
        DEFAULT_MAX_OUTPUT_TOKENS_BY_ALIAS[alias],
    )
    minimum_output_tokens = MIN_OUTPUT_TOKENS_BY_ALIAS.get(alias)
    if minimum_output_tokens is not None and max_output_tokens < minimum_output_tokens:
        return None, "insufficient_output_budget"

    return (
        ChatModelConfig(
            alias=alias,
            provider=provider,
            api_key_env=api_key_env,
            model_name=model_name,
            base_url=base_url,
            max_output_tokens=max_output_tokens,
            temperature=_float_env(
                f"{prefix}_TEMPERATURE",
                DEFAULT_TEMPERATURE_BY_ALIAS[alias],
            ),
            thinking_mode=thinking_mode,
        ),
        None,
    )


def _catalog_item(alias: ChatModelAlias) -> ChatModelCatalogItem:
    config, reason = chat_model_config_from_env(alias)
    return ChatModelCatalogItem(
        alias=alias,
        label=_model_label(alias),
        provider=config.provider if config else None,
        available=config is not None,
        default=alias == DEFAULT_CHAT_MODEL_ALIAS,
        unavailable_reason=reason,
    )


def _env_prefix(alias: ChatModelAlias) -> str:
    slug = alias.value.upper().replace("-", "_").replace(".", "_")
    return f"MEDICAL_AUDIT_KB_CHAT_MODEL_{slug}"


def _model_label(alias: ChatModelAlias) -> str:
    return MODEL_LABEL_BY_ALIAS[alias]


def _default_provider(alias: ChatModelAlias) -> str:
    return DEFAULT_PROVIDER_BY_ALIAS[alias]


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if parsed <= 0:
        raise ValueError(f"{name} must be positive")
    return parsed


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc


class _FakeChatModelAnswerProvider:
    provider = "fake"
    provider_version = "local-acceptance-v1"

    def __init__(self, alias: ChatModelAlias) -> None:
        self.model_name = alias.value

    def generate_answer(self, question: str, citations: Sequence[Citation]) -> str:
        if not citations:
            return f"本地验收模型回答：{question} 暂无可引用依据。"
        return f"本地验收模型回答：应核验医保基金审核依据 {citations[0].marker}。"
