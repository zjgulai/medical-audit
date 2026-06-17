from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Final, Literal, cast

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CONFIG_ENV: Final = "MEDICAL_AUDIT_KB_CONFIG"
DATA_ROOT_ENV: Final = "MEDICAL_AUDIT_KB_DATA_ROOT"
INDEX_ROOT_ENV: Final = "MEDICAL_AUDIT_KB_INDEX_ROOT"
DATABASE_URL_ENV: Final = "MEDICAL_AUDIT_KB_DATABASE_URL"
MODEL_PROVIDER_ENV: Final = "MEDICAL_AUDIT_KB_MODEL_PROVIDER"
ANALYTICS_UPLOAD_ROOT_ENV: Final = "MEDICAL_AUDIT_ANALYTICS_UPLOAD_ROOT"
DOCUMENT_UPLOAD_ROOT_ENV: Final = "MEDICAL_AUDIT_DOCUMENT_UPLOAD_ROOT"
DOCUMENT_UPLOAD_VIRUS_SCANNER_PROVIDER_ENV: Final = (
    "MEDICAL_AUDIT_DOCUMENT_UPLOAD_VIRUS_SCANNER_PROVIDER"
)
DOCUMENT_UPLOAD_DLP_REVIEWER_PROVIDER_ENV: Final = (
    "MEDICAL_AUDIT_DOCUMENT_UPLOAD_DLP_REVIEWER_PROVIDER"
)
DOCUMENT_UPLOAD_VIRUS_TEST_MODE_ENV: Final = "MEDICAL_AUDIT_DOCUMENT_UPLOAD_VIRUS_TEST_MODE"
DOCUMENT_UPLOAD_DLP_TEST_MODE_ENV: Final = "MEDICAL_AUDIT_DOCUMENT_UPLOAD_DLP_TEST_MODE"
DOCUMENT_STORAGE_PROVIDER_ENV: Final = "MEDICAL_AUDIT_DOCUMENT_STORAGE_PROVIDER"
DOCUMENT_STORAGE_COS_BUCKET_ENV: Final = "MEDICAL_AUDIT_DOCUMENT_STORAGE_COS_BUCKET"
DOCUMENT_STORAGE_COS_REGION_ENV: Final = "MEDICAL_AUDIT_DOCUMENT_STORAGE_COS_REGION"
DOCUMENT_STORAGE_COS_PREFIX_ENV: Final = "MEDICAL_AUDIT_DOCUMENT_STORAGE_COS_PREFIX"
DOCUMENT_STORAGE_COS_SECRET_ID_NAME_ENV: Final = "MEDICAL_AUDIT_DOCUMENT_STORAGE_COS_SECRET_ID_ENV"
DOCUMENT_STORAGE_COS_SECRET_KEY_NAME_ENV: Final = (
    "MEDICAL_AUDIT_DOCUMENT_STORAGE_COS_SECRET_KEY_ENV"
)
DOCUMENT_STORAGE_COS_ENCRYPTION_ENV: Final = "MEDICAL_AUDIT_DOCUMENT_STORAGE_COS_ENCRYPTION"
DOCUMENT_STORAGE_COS_KMS_KEY_ID_ENV: Final = "MEDICAL_AUDIT_DOCUMENT_STORAGE_COS_KMS_KEY_ID"
DOCUMENT_STORAGE_COS_STORAGE_CLASS_ENV: Final = (
    "MEDICAL_AUDIT_DOCUMENT_STORAGE_COS_STORAGE_CLASS"
)
DOCUMENT_DOWNLOAD_SIGNED_URL_TTL_SECONDS_ENV: Final = (
    "MEDICAL_AUDIT_DOCUMENT_DOWNLOAD_SIGNED_URL_TTL_SECONDS"
)
DOCUMENT_LOCAL_QUARANTINE_RETENTION_DAYS_ENV: Final = (
    "MEDICAL_AUDIT_DOCUMENT_LOCAL_QUARANTINE_RETENTION_DAYS"
)
DOCUMENT_OBJECT_RETENTION_DAYS_ENV: Final = "MEDICAL_AUDIT_DOCUMENT_OBJECT_RETENTION_DAYS"
DOCUMENT_STORAGE_RECORD_OBJECTS_ENV: Final = "MEDICAL_AUDIT_DOCUMENT_STORAGE_RECORD_OBJECTS"

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


class DocumentUploadGovernanceSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    virus_scan_provider: Literal[
        "unconfigured",
        "local-test",
        "tencent-ci-virus",
        "clamav-sidecar",
    ] = "unconfigured"
    dlp_review_provider: Literal[
        "unconfigured",
        "local-test",
        "ruleset-v1",
        "external-dlp",
    ] = "unconfigured"
    virus_scan_test_mode: Literal["normal", "false-positive", "false-negative"] = "normal"
    dlp_review_test_mode: Literal["normal", "false-positive", "false-negative"] = "normal"


class DocumentStorageSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: Literal["local", "tencent-cos"] = "local"
    cos_bucket: str | None = None
    cos_region: str | None = None
    cos_prefix: str = "personal-materials/prod"
    cos_secret_id_env: str | None = None
    cos_secret_key_env: str | None = None
    cos_encryption: Literal["sse-cos", "sse-kms"] = "sse-cos"
    cos_kms_key_id: str | None = None
    cos_storage_class: str = Field(default="STANDARD", min_length=1)
    signed_url_ttl_seconds: int = Field(default=120, ge=1)
    local_quarantine_retention_days: int = Field(default=7, ge=0)
    object_retention_days: int = Field(default=180, ge=1)
    record_storage_objects: bool = False


class KnowledgeQuerySettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    data_root: Path
    index_root: Path
    analytics_upload_root: Path | None = None
    document_upload_root: Path | None = None
    database_url: str = Field(min_length=1)
    model_provider: ModelProviderSettings
    document_upload_governance: DocumentUploadGovernanceSettings = Field(
        default_factory=DocumentUploadGovernanceSettings
    )
    document_storage: DocumentStorageSettings = Field(default_factory=DocumentStorageSettings)
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
    if document_upload_root := os.getenv(DOCUMENT_UPLOAD_ROOT_ENV):
        merged["document_upload_root"] = document_upload_root
    if database_url := os.getenv(DATABASE_URL_ENV):
        merged["database_url"] = database_url
    if provider := os.getenv(MODEL_PROVIDER_ENV):
        model_provider = dict(cast(dict[str, Any], merged.get("model_provider", {})))
        model_provider["provider"] = provider
        merged["model_provider"] = model_provider
    if document_upload_governance := _document_upload_governance_env_overrides(merged):
        merged["document_upload_governance"] = document_upload_governance
    if document_storage := _document_storage_env_overrides(merged):
        merged["document_storage"] = document_storage

    return merged


def _document_upload_governance_env_overrides(
    data: dict[str, Any],
) -> dict[str, Any] | None:
    governance = dict(cast(dict[str, Any], data.get("document_upload_governance", {})))
    changed = False
    if provider := os.getenv(DOCUMENT_UPLOAD_VIRUS_SCANNER_PROVIDER_ENV):
        governance["virus_scan_provider"] = provider
        changed = True
    if provider := os.getenv(DOCUMENT_UPLOAD_DLP_REVIEWER_PROVIDER_ENV):
        governance["dlp_review_provider"] = provider
        changed = True
    if mode := os.getenv(DOCUMENT_UPLOAD_VIRUS_TEST_MODE_ENV):
        governance["virus_scan_test_mode"] = mode
        changed = True
    if mode := os.getenv(DOCUMENT_UPLOAD_DLP_TEST_MODE_ENV):
        governance["dlp_review_test_mode"] = mode
        changed = True
    if not changed:
        return None
    return governance


def _document_storage_env_overrides(data: dict[str, Any]) -> dict[str, Any] | None:
    storage = dict(cast(dict[str, Any], data.get("document_storage", {})))
    changed = False
    if provider := os.getenv(DOCUMENT_STORAGE_PROVIDER_ENV):
        storage["provider"] = provider
        changed = True
    if bucket := os.getenv(DOCUMENT_STORAGE_COS_BUCKET_ENV):
        storage["cos_bucket"] = bucket
        changed = True
    if region := os.getenv(DOCUMENT_STORAGE_COS_REGION_ENV):
        storage["cos_region"] = region
        changed = True
    if prefix := os.getenv(DOCUMENT_STORAGE_COS_PREFIX_ENV):
        storage["cos_prefix"] = prefix
        changed = True
    if secret_id_env := os.getenv(DOCUMENT_STORAGE_COS_SECRET_ID_NAME_ENV):
        storage["cos_secret_id_env"] = secret_id_env
        changed = True
    if secret_key_env := os.getenv(DOCUMENT_STORAGE_COS_SECRET_KEY_NAME_ENV):
        storage["cos_secret_key_env"] = secret_key_env
        changed = True
    if encryption := os.getenv(DOCUMENT_STORAGE_COS_ENCRYPTION_ENV):
        storage["cos_encryption"] = encryption
        changed = True
    if kms_key_id := os.getenv(DOCUMENT_STORAGE_COS_KMS_KEY_ID_ENV):
        storage["cos_kms_key_id"] = kms_key_id
        changed = True
    if storage_class := os.getenv(DOCUMENT_STORAGE_COS_STORAGE_CLASS_ENV):
        storage["cos_storage_class"] = storage_class
        changed = True
    if ttl := os.getenv(DOCUMENT_DOWNLOAD_SIGNED_URL_TTL_SECONDS_ENV):
        storage["signed_url_ttl_seconds"] = int(ttl)
        changed = True
    if retention_days := os.getenv(DOCUMENT_LOCAL_QUARANTINE_RETENTION_DAYS_ENV):
        storage["local_quarantine_retention_days"] = int(retention_days)
        changed = True
    if retention_days := os.getenv(DOCUMENT_OBJECT_RETENTION_DAYS_ENV):
        storage["object_retention_days"] = int(retention_days)
        changed = True
    if record_objects := os.getenv(DOCUMENT_STORAGE_RECORD_OBJECTS_ENV):
        storage["record_storage_objects"] = _parse_bool_env(
            record_objects,
            DOCUMENT_STORAGE_RECORD_OBJECTS_ENV,
        )
        changed = True
    if not changed:
        return None
    return storage


def _parse_bool_env(value: str, env_name: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{env_name} must be a boolean value")
