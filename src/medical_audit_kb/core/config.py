from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Final, cast

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CONFIG_ENV: Final = "MEDICAL_AUDIT_KB_CONFIG"
DATA_ROOT_ENV: Final = "MEDICAL_AUDIT_KB_DATA_ROOT"
INDEX_ROOT_ENV: Final = "MEDICAL_AUDIT_KB_INDEX_ROOT"
DATABASE_URL_ENV: Final = "MEDICAL_AUDIT_KB_DATABASE_URL"
MODEL_PROVIDER_ENV: Final = "MEDICAL_AUDIT_KB_MODEL_PROVIDER"
ANALYTICS_UPLOAD_ROOT_ENV: Final = "MEDICAL_AUDIT_ANALYTICS_UPLOAD_ROOT"

DEFAULT_CONFIG_PATH: Final = Path("configs/knowledge-query-engine-dev.yaml")
REQUIRED_COLLECTIONS: Final = frozenset(
    {
        "medical-insurance-catalog",
        "supervision-rules-knowledge",
        "risk-negative-list",
        "medical-insurance-laws",
    }
)


class ModelProviderSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str = Field(min_length=1)
    api_key_env: str = Field(min_length=1)
    embedding_model: str = Field(min_length=1)
    rerank_model: str | None = None
    chat_model: str = Field(min_length=1)


class KnowledgeQuerySettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    data_root: Path
    index_root: Path
    analytics_upload_root: Path | None = None
    database_url: str = Field(min_length=1)
    model_provider: ModelProviderSettings
    source_collection_weights: dict[str, float]

    @field_validator("source_collection_weights")
    @classmethod
    def validate_collection_weights(cls, value: dict[str, float]) -> dict[str, float]:
        missing = REQUIRED_COLLECTIONS.difference(value)
        if missing:
            joined = ", ".join(sorted(missing))
            raise ValueError(f"missing source collection weights: {joined}")

        invalid = [key for key, weight in value.items() if weight <= 0]
        if invalid:
            joined = ", ".join(sorted(invalid))
            raise ValueError(f"source collection weights must be positive: {joined}")

        return value

    @model_validator(mode="after")
    def validate_database_url(self) -> KnowledgeQuerySettings:
        if not self.database_url.startswith(("postgresql://", "postgresql+psycopg://")):
            raise ValueError("database_url must use PostgreSQL")
        return self


def load_settings(config_path: Path | str | None = None) -> KnowledgeQuerySettings:
    selected_path = _select_config_path(config_path)
    data = _read_yaml_mapping(selected_path)
    data = _apply_env_overrides(data)
    return KnowledgeQuerySettings.model_validate(data)


def _select_config_path(config_path: Path | str | None) -> Path:
    if config_path is not None:
        return Path(config_path)

    env_path = os.getenv(CONFIG_ENV)
    if env_path:
        return Path(env_path)

    return DEFAULT_CONFIG_PATH


def _read_yaml_mapping(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        raise FileNotFoundError(f"configuration file not found: {config_path}")

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"configuration file must contain a mapping: {config_path}")
    return cast(dict[str, Any], raw)


def _apply_env_overrides(data: dict[str, Any]) -> dict[str, Any]:
    merged = dict(data)

    if data_root := os.getenv(DATA_ROOT_ENV):
        merged["data_root"] = data_root
    if index_root := os.getenv(INDEX_ROOT_ENV):
        merged["index_root"] = index_root
    if analytics_upload_root := os.getenv(ANALYTICS_UPLOAD_ROOT_ENV):
        merged["analytics_upload_root"] = analytics_upload_root
    if database_url := os.getenv(DATABASE_URL_ENV):
        merged["database_url"] = database_url
    if provider := os.getenv(MODEL_PROVIDER_ENV):
        model_provider = dict(cast(dict[str, Any], merged.get("model_provider", {})))
        model_provider["provider"] = provider
        merged["model_provider"] = model_provider

    return merged
