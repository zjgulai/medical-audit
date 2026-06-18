from pathlib import Path

import pytest

from medical_audit_kb.core.config import (
    DATABASE_URL_ENV,
    DOCUMENT_DOWNLOAD_SIGNED_URL_TTL_SECONDS_ENV,
    DOCUMENT_OBJECT_RETENTION_DAYS_ENV,
    DOCUMENT_STORAGE_COS_BUCKET_ENV,
    DOCUMENT_STORAGE_COS_ENCRYPTION_ENV,
    DOCUMENT_STORAGE_COS_PREFIX_ENV,
    DOCUMENT_STORAGE_COS_REGION_ENV,
    DOCUMENT_STORAGE_COS_SDK_BOOTSTRAP_ENV,
    DOCUMENT_STORAGE_COS_SECRET_ID_NAME_ENV,
    DOCUMENT_STORAGE_COS_SECRET_KEY_NAME_ENV,
    DOCUMENT_STORAGE_COS_STORAGE_CLASS_ENV,
    DOCUMENT_STORAGE_PROVIDER_ENV,
    DOCUMENT_STORAGE_RECORD_OBJECTS_ENV,
    DOCUMENT_UPLOAD_DLP_REVIEW_JOB_ENDPOINT_NAME_ENV,
    DOCUMENT_UPLOAD_DLP_REVIEW_JOB_SECRET_NAME_ENV,
    DOCUMENT_UPLOAD_DLP_REVIEWER_PROVIDER_ENV,
    DOCUMENT_UPLOAD_DLP_TEST_MODE_ENV,
    DOCUMENT_UPLOAD_GOVERNANCE_JOB_SUBMITTER_PROVIDER_ENV,
    DOCUMENT_UPLOAD_VIRUS_SCAN_JOB_ENDPOINT_NAME_ENV,
    DOCUMENT_UPLOAD_VIRUS_SCAN_JOB_SECRET_NAME_ENV,
    DOCUMENT_UPLOAD_VIRUS_SCANNER_PROVIDER_ENV,
    DOCUMENT_UPLOAD_VIRUS_TEST_MODE_ENV,
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
    assert settings.document_upload_governance.virus_scan_provider == "unconfigured"
    assert settings.document_upload_governance.dlp_review_provider == "unconfigured"
    assert settings.document_upload_governance.virus_scan_test_mode == "normal"
    assert settings.document_upload_governance.dlp_review_test_mode == "normal"
    assert settings.document_upload_governance.governance_job_submitter_provider == "disabled"
    assert settings.document_upload_governance.virus_scan_job_endpoint_env is None
    assert settings.document_upload_governance.virus_scan_job_secret_env is None
    assert settings.document_upload_governance.dlp_review_job_endpoint_env is None
    assert settings.document_upload_governance.dlp_review_job_secret_env is None
    assert settings.document_storage.provider == "local"
    assert settings.document_storage.cos_bucket is None
    assert settings.document_storage.cos_prefix == "personal-materials/prod"
    assert settings.document_storage.cos_sdk_bootstrap_enabled is False
    assert settings.document_storage.signed_url_ttl_seconds == 120
    assert settings.document_storage.record_storage_objects is False
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


def test_environment_overrides_document_upload_governance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(DOCUMENT_UPLOAD_VIRUS_SCANNER_PROVIDER_ENV, "local-test")
    monkeypatch.setenv(DOCUMENT_UPLOAD_DLP_REVIEWER_PROVIDER_ENV, "local-test")
    monkeypatch.setenv(DOCUMENT_UPLOAD_VIRUS_TEST_MODE_ENV, "false-positive")
    monkeypatch.setenv(DOCUMENT_UPLOAD_DLP_TEST_MODE_ENV, "false-negative")
    monkeypatch.setenv(DOCUMENT_UPLOAD_GOVERNANCE_JOB_SUBMITTER_PROVIDER_ENV, "local-recording")
    monkeypatch.setenv(
        DOCUMENT_UPLOAD_VIRUS_SCAN_JOB_ENDPOINT_NAME_ENV,
        "VIRUS_SCAN_JOB_ENDPOINT",
    )
    monkeypatch.setenv(DOCUMENT_UPLOAD_VIRUS_SCAN_JOB_SECRET_NAME_ENV, "VIRUS_SCAN_JOB_SECRET")
    monkeypatch.setenv(
        DOCUMENT_UPLOAD_DLP_REVIEW_JOB_ENDPOINT_NAME_ENV,
        "DLP_REVIEW_JOB_ENDPOINT",
    )
    monkeypatch.setenv(DOCUMENT_UPLOAD_DLP_REVIEW_JOB_SECRET_NAME_ENV, "DLP_REVIEW_JOB_SECRET")

    settings = load_settings()

    assert settings.document_upload_governance.virus_scan_provider == "local-test"
    assert settings.document_upload_governance.dlp_review_provider == "local-test"
    assert settings.document_upload_governance.virus_scan_test_mode == "false-positive"
    assert settings.document_upload_governance.dlp_review_test_mode == "false-negative"
    assert settings.document_upload_governance.governance_job_submitter_provider == (
        "local-recording"
    )
    assert settings.document_upload_governance.virus_scan_job_endpoint_env == (
        "VIRUS_SCAN_JOB_ENDPOINT"
    )
    assert settings.document_upload_governance.virus_scan_job_secret_env == (
        "VIRUS_SCAN_JOB_SECRET"
    )
    assert settings.document_upload_governance.dlp_review_job_endpoint_env == (
        "DLP_REVIEW_JOB_ENDPOINT"
    )
    assert settings.document_upload_governance.dlp_review_job_secret_env == (
        "DLP_REVIEW_JOB_SECRET"
    )


def test_environment_overrides_document_storage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(DOCUMENT_STORAGE_PROVIDER_ENV, "tencent-cos")
    monkeypatch.setenv(DOCUMENT_STORAGE_COS_BUCKET_ENV, "medical-audit-prod")
    monkeypatch.setenv(DOCUMENT_STORAGE_COS_REGION_ENV, "ap-guangzhou")
    monkeypatch.setenv(DOCUMENT_STORAGE_COS_PREFIX_ENV, "personal-materials/prod")
    monkeypatch.setenv(DOCUMENT_STORAGE_COS_SECRET_ID_NAME_ENV, "COS_SECRET_ID")
    monkeypatch.setenv(DOCUMENT_STORAGE_COS_SECRET_KEY_NAME_ENV, "COS_SECRET_KEY")
    monkeypatch.setenv(DOCUMENT_STORAGE_COS_ENCRYPTION_ENV, "sse-kms")
    monkeypatch.setenv(DOCUMENT_STORAGE_COS_STORAGE_CLASS_ENV, "STANDARD_IA")
    monkeypatch.setenv(DOCUMENT_STORAGE_COS_SDK_BOOTSTRAP_ENV, "true")
    monkeypatch.setenv(DOCUMENT_DOWNLOAD_SIGNED_URL_TTL_SECONDS_ENV, "180")
    monkeypatch.setenv(DOCUMENT_OBJECT_RETENTION_DAYS_ENV, "365")
    monkeypatch.setenv(DOCUMENT_STORAGE_RECORD_OBJECTS_ENV, "true")

    settings = load_settings()

    assert settings.document_storage.provider == "tencent-cos"
    assert settings.document_storage.cos_bucket == "medical-audit-prod"
    assert settings.document_storage.cos_region == "ap-guangzhou"
    assert settings.document_storage.cos_prefix == "personal-materials/prod"
    assert settings.document_storage.cos_secret_id_env == "COS_SECRET_ID"
    assert settings.document_storage.cos_secret_key_env == "COS_SECRET_KEY"
    assert settings.document_storage.cos_encryption == "sse-kms"
    assert settings.document_storage.cos_storage_class == "STANDARD_IA"
    assert settings.document_storage.cos_sdk_bootstrap_enabled is True
    assert settings.document_storage.signed_url_ttl_seconds == 180
    assert settings.document_storage.object_retention_days == 365
    assert settings.document_storage.record_storage_objects is True


def test_environment_rejects_invalid_document_storage_boolean(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(DOCUMENT_STORAGE_RECORD_OBJECTS_ENV, "maybe")

    with pytest.raises(ValueError, match="MEDICAL_AUDIT_DOCUMENT_STORAGE_RECORD_OBJECTS"):
        load_settings()


def test_config_rejects_invalid_document_upload_governance_provider() -> None:
    with pytest.raises(ValueError):
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
                "document_upload_governance": {
                    "virus_scan_provider": "prod-scanner",
                },
                "source_collection_weights": {
                    "medical-insurance-catalog": 1.0,
                    "supervision-rules-knowledge": 1.0,
                    "risk-negative-list": 1.0,
                    "medical-insurance-laws": 1.0,
                },
            }
        )
