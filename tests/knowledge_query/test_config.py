from pathlib import Path

import pytest

from medical_audit_kb.core.config import (
    DATABASE_URL_ENV,
    MODEL_PROVIDER_ENV,
    REQUIRED_COLLECTIONS,
    KnowledgeQuerySettings,
    load_settings,
)


def test_default_config_loads() -> None:
    settings = load_settings()

    assert settings.data_root == Path("data/医保审核前期资料")
    assert settings.index_root == Path("tmp/knowledge-query-indexes")
    assert settings.model_provider.provider == "openai"
    assert REQUIRED_COLLECTIONS.issubset(settings.source_collection_weights)


def test_config_rejects_missing_required_collection_weight() -> None:
    with pytest.raises(ValueError, match="missing source collection weights"):
        KnowledgeQuerySettings.model_validate(
            {
                "data_root": "data/医保审核前期资料",
                "index_root": "tmp/knowledge-query-indexes",
                "database_url": "postgresql+psycopg://user:pass@localhost:5433/db",
                "model_provider": {
                    "provider": "openai",
                    "api_key_env": "OPENAI_API_KEY",
                    "embedding_model": "text-embedding-3-small",
                    "chat_model": "gpt-4.1-mini",
                },
                "source_collection_weights": {
                    "medical-insurance-catalog": 1.0,
                },
            }
        )


def test_config_rejects_non_postgresql_database_url() -> None:
    with pytest.raises(ValueError, match="database_url must use PostgreSQL"):
        KnowledgeQuerySettings.model_validate(
            {
                "data_root": "data/医保审核前期资料",
                "index_root": "tmp/knowledge-query-indexes",
                "database_url": "sqlite:///tmp.db",
                "model_provider": {
                    "provider": "openai",
                    "api_key_env": "OPENAI_API_KEY",
                    "embedding_model": "text-embedding-3-small",
                    "chat_model": "gpt-4.1-mini",
                },
                "source_collection_weights": {
                    "medical-insurance-catalog": 1.0,
                    "supervision-rules-knowledge": 1.0,
                    "risk-negative-list": 1.0,
                    "medical-insurance-laws": 1.0,
                },
            }
        )


def test_environment_overrides_database_and_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        DATABASE_URL_ENV,
        "postgresql+psycopg://override:override@localhost:5433/override",
    )
    monkeypatch.setenv(MODEL_PROVIDER_ENV, "local")

    settings = load_settings()

    assert settings.database_url == "postgresql+psycopg://override:override@localhost:5433/override"
    assert settings.model_provider.provider == "local"
