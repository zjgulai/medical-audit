from pathlib import Path

import pytest

from medical_audit_kb.core.config import (
    DATABASE_URL_ENV,
    DOCUMENT_DOWNLOAD_SIGNED_URL_TTL_SECONDS_ENV,
    DOCUMENT_GOVERNANCE_AUDIT_EVENT_REQUIRED_ENV,
    DOCUMENT_GOVERNANCE_REDACTION_POLICY_VERSION_ENV,
    DOCUMENT_GOVERNANCE_REDACTION_REVIEW_REQUIRED_ENV,
    DOCUMENT_GOVERNANCE_REDACTION_REWRITE_ENABLED_ENV,
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
    DOCUMENT_UPLOAD_CLAMAV_CHUNK_SIZE_BYTES_ENV,
    DOCUMENT_UPLOAD_CLAMAV_HOST_ENV,
    DOCUMENT_UPLOAD_CLAMAV_PORT_ENV,
    DOCUMENT_UPLOAD_CLAMAV_TIMEOUT_SECONDS_ENV,
    DOCUMENT_UPLOAD_DLP_REVIEW_JOB_ENDPOINT_NAME_ENV,
    DOCUMENT_UPLOAD_DLP_REVIEW_JOB_SECRET_NAME_ENV,
    DOCUMENT_UPLOAD_DLP_REVIEWER_PROVIDER_ENV,
    DOCUMENT_UPLOAD_DLP_TEST_MODE_ENV,
    DOCUMENT_UPLOAD_GOVERNANCE_JOB_SUBMITTER_PROVIDER_ENV,
    DOCUMENT_UPLOAD_INDEXING_EMBEDDING_DIMENSION_ENV,
    DOCUMENT_UPLOAD_INDEXING_ENABLED_ENV,
    DOCUMENT_UPLOAD_INDEXING_INDEX_VERSION_KEY_ENV,
    DOCUMENT_UPLOAD_INDEXING_SOURCE_PACKAGE_KEY_ENV,
    DOCUMENT_UPLOAD_VIRUS_SCAN_JOB_ENDPOINT_NAME_ENV,
    DOCUMENT_UPLOAD_VIRUS_SCAN_JOB_SECRET_NAME_ENV,
    DOCUMENT_UPLOAD_VIRUS_SCANNER_PROVIDER_ENV,
    DOCUMENT_UPLOAD_VIRUS_TEST_MODE_ENV,
    MODEL_PROVIDER_ENV,
    REQUIRED_COLLECTIONS,
    UNLIMITED_OCR_API_KEY_NAME_ENV,
    UNLIMITED_OCR_BASE_URL_ENV,
    UNLIMITED_OCR_ENABLED_ENV,
    UNLIMITED_OCR_MAX_OUTPUT_TOKENS_ENV,
    UNLIMITED_OCR_MAX_PAGES_ENV,
    UNLIMITED_OCR_MODEL_ENV,
    UNLIMITED_OCR_PDF_DPI_ENV,
    UNLIMITED_OCR_TIMEOUT_SECONDS_ENV,
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
    assert settings.document_upload_governance.clamav_host == "127.0.0.1"
    assert settings.document_upload_governance.clamav_port == 3310
    assert settings.document_upload_governance.clamav_timeout_seconds == 3.0
    assert settings.document_upload_governance.clamav_chunk_size_bytes == 131072
    assert settings.document_upload_governance.governance_job_submitter_provider == "disabled"
    assert settings.document_upload_governance.virus_scan_job_endpoint_env is None
    assert settings.document_upload_governance.virus_scan_job_secret_env is None
    assert settings.document_upload_governance.dlp_review_job_endpoint_env is None
    assert settings.document_upload_governance.dlp_review_job_secret_env is None
    assert settings.document_upload_governance.redaction_rewrite_enabled is False
    assert settings.document_upload_governance.redaction_policy_version is None
    assert settings.document_upload_governance.redaction_manual_review_required is False
    assert settings.document_upload_governance.governance_audit_event_required is False
    assert settings.document_storage.provider == "local"
    assert settings.document_storage.cos_bucket is None
    assert settings.document_storage.cos_prefix == "personal-materials/prod"
    assert settings.document_storage.cos_sdk_bootstrap_enabled is False
    assert settings.document_storage.signed_url_ttl_seconds == 120
    assert settings.document_storage.record_storage_objects is False
    assert settings.document_upload_indexing.enabled is False
    assert settings.document_upload_indexing.index_version_status == "candidate"
    assert settings.unlimited_ocr.enabled is False
    assert settings.unlimited_ocr.model == "baidu/Unlimited-OCR"
    default_a4_page_pixels = round(8.27 * settings.unlimited_ocr.pdf_dpi) * round(
        11.69 * settings.unlimited_ocr.pdf_dpi
    )
    assert settings.unlimited_ocr.max_total_pixels >= (
        settings.unlimited_ocr.max_pages * default_a4_page_pixels
    )
    assert settings.unlimited_ocr.source_commit == (
        "d49ff64afffc1f47ab563dc1c589bc2f78808fa4"
    )
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
    monkeypatch.setenv(DOCUMENT_UPLOAD_CLAMAV_HOST_ENV, "clamav")
    monkeypatch.setenv(DOCUMENT_UPLOAD_CLAMAV_PORT_ENV, "3311")
    monkeypatch.setenv(DOCUMENT_UPLOAD_CLAMAV_TIMEOUT_SECONDS_ENV, "5.5")
    monkeypatch.setenv(DOCUMENT_UPLOAD_CLAMAV_CHUNK_SIZE_BYTES_ENV, "65536")
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
    monkeypatch.setenv(DOCUMENT_GOVERNANCE_REDACTION_REWRITE_ENABLED_ENV, "true")
    monkeypatch.setenv(DOCUMENT_GOVERNANCE_REDACTION_POLICY_VERSION_ENV, "redaction-v1")
    monkeypatch.setenv(DOCUMENT_GOVERNANCE_REDACTION_REVIEW_REQUIRED_ENV, "true")
    monkeypatch.setenv(DOCUMENT_GOVERNANCE_AUDIT_EVENT_REQUIRED_ENV, "true")

    settings = load_settings()

    assert settings.document_upload_governance.virus_scan_provider == "local-test"
    assert settings.document_upload_governance.dlp_review_provider == "local-test"
    assert settings.document_upload_governance.virus_scan_test_mode == "false-positive"
    assert settings.document_upload_governance.dlp_review_test_mode == "false-negative"
    assert settings.document_upload_governance.clamav_host == "clamav"
    assert settings.document_upload_governance.clamav_port == 3311
    assert settings.document_upload_governance.clamav_timeout_seconds == 5.5
    assert settings.document_upload_governance.clamav_chunk_size_bytes == 65536
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
    assert settings.document_upload_governance.redaction_rewrite_enabled is True
    assert settings.document_upload_governance.redaction_policy_version == "redaction-v1"
    assert settings.document_upload_governance.redaction_manual_review_required is True
    assert settings.document_upload_governance.governance_audit_event_required is True


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


def test_environment_overrides_document_upload_indexing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(DOCUMENT_UPLOAD_INDEXING_ENABLED_ENV, "true")
    monkeypatch.setenv(DOCUMENT_UPLOAD_INDEXING_EMBEDDING_DIMENSION_ENV, "64")
    monkeypatch.setenv(DOCUMENT_UPLOAD_INDEXING_SOURCE_PACKAGE_KEY_ENV, "personal-package-test")
    monkeypatch.setenv(DOCUMENT_UPLOAD_INDEXING_INDEX_VERSION_KEY_ENV, "personal-index-test")

    settings = load_settings()

    assert settings.document_upload_indexing.enabled is True
    assert settings.document_upload_indexing.embedding_provider == "deterministic-fake"
    assert settings.document_upload_indexing.embedding_dimension == 64
    assert settings.document_upload_indexing.source_package_version_key == (
        "personal-package-test"
    )
    assert settings.document_upload_indexing.index_version_key == "personal-index-test"
    assert settings.document_upload_indexing.index_version_status == "candidate"


def test_environment_overrides_unlimited_ocr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(UNLIMITED_OCR_ENABLED_ENV, "true")
    monkeypatch.setenv(UNLIMITED_OCR_BASE_URL_ENV, "http://ocr.internal:8000/v1")
    monkeypatch.setenv(UNLIMITED_OCR_MODEL_ENV, "baidu/Unlimited-OCR")
    monkeypatch.setenv(UNLIMITED_OCR_API_KEY_NAME_ENV, "UNLIMITED_OCR_TOKEN")
    monkeypatch.setenv(UNLIMITED_OCR_TIMEOUT_SECONDS_ENV, "600")
    monkeypatch.setenv(UNLIMITED_OCR_MAX_PAGES_ENV, "25")
    monkeypatch.setenv(UNLIMITED_OCR_PDF_DPI_ENV, "240")
    monkeypatch.setenv(UNLIMITED_OCR_MAX_OUTPUT_TOKENS_ENV, "16384")

    settings = load_settings()

    assert settings.unlimited_ocr.enabled is True
    assert settings.unlimited_ocr.base_url == "http://ocr.internal:8000/v1"
    assert settings.unlimited_ocr.model == "baidu/Unlimited-OCR"
    assert settings.unlimited_ocr.api_key_env == "UNLIMITED_OCR_TOKEN"
    assert settings.unlimited_ocr.timeout_seconds == 600
    assert settings.unlimited_ocr.max_pages == 25
    assert settings.unlimited_ocr.pdf_dpi == 240
    assert settings.unlimited_ocr.max_output_tokens == 16384


def test_environment_rejects_invalid_document_storage_boolean(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(DOCUMENT_STORAGE_RECORD_OBJECTS_ENV, "maybe")

    with pytest.raises(ValueError, match="MEDICAL_AUDIT_DOCUMENT_STORAGE_RECORD_OBJECTS"):
        load_settings()


def test_environment_rejects_invalid_document_governance_boolean(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(DOCUMENT_GOVERNANCE_AUDIT_EVENT_REQUIRED_ENV, "maybe")

    with pytest.raises(ValueError, match="MEDICAL_AUDIT_DOCUMENT_GOVERNANCE_AUDIT_EVENT_REQUIRED"):
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
