import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from sqlite3 import Connection as SQLiteConnection
from typing import cast

import pytest
from sqlalchemy import event
from sqlalchemy.engine import Engine

from medical_audit_kb.api.document_upload_governance_jobs import (
    LocalRecordingDocumentUploadGovernanceJobSubmitter,
    submit_required_document_upload_governance_jobs,
)
from medical_audit_kb.api.document_upload_governance_store import (
    DOCUMENT_UPLOAD_GOVERNANCE_JOB_ID_PREFIX,
    DocumentObjectStoragePutRequest,
    DocumentStorageObjectCreate,
    DocumentUploadGovernanceJobCreate,
    LocalDocumentObjectStorage,
    SqlAlchemyDocumentUploadGovernanceStore,
    TencentCosDocumentObjectStorage,
    TencentCosSdkPutObjectClient,
)
from medical_audit_kb.api.document_upload_store import (
    SqlAlchemyDocumentUploadStore,
    document_object_storage_from_settings,
    document_storage_objects_schema_ready,
    tencent_cos_bootstrap_preflight_from_settings,
    tencent_cos_put_object_client_from_settings,
)
from medical_audit_kb.core.config import DocumentStorageSettings


def test_local_document_object_storage_keeps_existing_partitioned_path(
    tmp_path: Path,
) -> None:
    storage = LocalDocumentObjectStorage(tmp_path / "document-uploads")
    result = storage.put_object(
        request=DocumentObjectStoragePutRequest(
            upload_key="document-upload-abc123",
            file_name="policy.txt",
            extension="txt",
            content=b"policy evidence",
            sha256="a" * 64,
            created_at=datetime(2026, 6, 16, 12, 0, tzinfo=UTC),
        )
    )

    assert result.provider == "local"
    assert result.object_key == "2026/06/16/document-upload-abc123.txt"
    assert result.storage_status == "local-quarantine"
    assert result.metadata["storage_backend"] == "local-filesystem"
    assert (tmp_path / "document-uploads" / result.object_key).read_bytes() == b"policy evidence"


def test_tencent_cos_storage_uses_injected_client_without_file_name_in_key() -> None:
    client = FakeTencentCosClient(
        etag='"8f7dd3a13bfa8f5b67a6b734f4c1a4d7"',
        version_id="cos-version-1",
    )
    storage = TencentCosDocumentObjectStorage(
        client=client,
        bucket="medical-audit-prod",
        region="ap-guangzhou",
        prefix="personal-materials/test",
        encryption_mode="sse-kms",
        kms_key_id="kms-key-1",
        storage_class="STANDARD_IA",
    )

    result = storage.put_object(
        request=DocumentObjectStoragePutRequest(
            upload_key="document-upload-cos123",
            file_name="patient-report.txt",
            extension="txt",
            content=b"policy evidence",
            sha256="b" * 64,
            created_at=datetime(2026, 6, 17, 10, 11, tzinfo=UTC),
        )
    )

    assert result.provider == "tencent-cos"
    assert result.bucket == "medical-audit-prod"
    assert result.region == "ap-guangzhou"
    assert result.object_key == (
        f"personal-materials/test/2026/06/17/document-upload-cos123/{'b' * 64}.txt"
    )
    assert "patient-report" not in result.object_key
    assert result.etag == '"8f7dd3a13bfa8f5b67a6b734f4c1a4d7"'
    assert result.object_version == "cos-version-1"
    assert result.storage_class == "STANDARD_IA"
    assert result.encryption_mode == "sse-kms"
    assert result.storage_status == "object-stored"
    assert result.metadata == {
        "content_type": "text/plain",
        "storage_backend": "tencent-cos",
    }
    signed_url_result = storage.create_presigned_download_url(
        object_key=result.object_key,
        expires_in_seconds=300,
    )
    assert signed_url_result is not None
    assert signed_url_result.provider == "tencent-cos"
    assert signed_url_result.bucket == "medical-audit-prod"
    assert signed_url_result.region == "ap-guangzhou"
    assert signed_url_result.object_key == result.object_key
    assert signed_url_result.signed_url == "https://cos.example/signed-download"
    assert client.calls == [
        {
            "bucket": "medical-audit-prod",
            "region": "ap-guangzhou",
            "object_key": result.object_key,
            "content": b"policy evidence",
            "content_type": "text/plain",
            "metadata": {
                "sha256": "b" * 64,
                "upload_key": "document-upload-cos123",
            },
            "encryption_mode": "sse-kms",
            "kms_key_id": "kms-key-1",
            "storage_class": "STANDARD_IA",
        }
    ]
    assert client.presign_calls == [
        {
            "bucket": "medical-audit-prod",
            "region": "ap-guangzhou",
            "object_key": result.object_key,
            "expires_in_seconds": 300,
        }
    ]


def test_tencent_cos_sdk_client_translates_contract_to_python_sdk_put_object() -> None:
    sdk_client = FakeTencentCosSdkClient(
        response={
            "ETag": '"8f7dd3a13bfa8f5b67a6b734f4c1a4d7"',
            "VersionId": "cos-version-1",
        }
    )
    client = TencentCosSdkPutObjectClient(sdk_client=sdk_client)

    result = client.put_object(
        bucket="medical-audit-prod",
        region="ap-guangzhou",
        object_key="personal-materials/prod/2026/06/17/object.txt",
        content=b"policy evidence",
        content_type="text/plain",
        metadata={"sha256": "b" * 64, "upload_key": "document-upload-cos123"},
        encryption_mode="sse-cos",
        kms_key_id=None,
        storage_class="STANDARD_IA",
    )

    assert result == {
        "etag": '"8f7dd3a13bfa8f5b67a6b734f4c1a4d7"',
        "version_id": "cos-version-1",
    }
    assert sdk_client.calls == [
        {
            "Bucket": "medical-audit-prod",
            "Key": "personal-materials/prod/2026/06/17/object.txt",
            "Body": b"policy evidence",
            "ContentType": "text/plain",
            "StorageClass": "STANDARD_IA",
            "Metadata": {
                "x-cos-meta-sha256": "b" * 64,
                "x-cos-meta-upload-key": "document-upload-cos123",
            },
            "ServerSideEncryption": "AES256",
        }
    ]


def test_tencent_cos_sdk_client_translates_kms_encryption() -> None:
    sdk_client = FakeTencentCosSdkClient(response={"ETag": '"etag"', "VersionId": None})
    client = TencentCosSdkPutObjectClient(sdk_client=sdk_client)

    result = client.put_object(
        bucket="medical-audit-prod",
        region="ap-guangzhou",
        object_key="personal-materials/prod/object.txt",
        content=b"policy evidence",
        content_type="text/plain",
        metadata={"sha256": "c" * 64},
        encryption_mode="sse-kms",
        kms_key_id="kms-key-1",
        storage_class="STANDARD",
    )

    assert result == {"etag": '"etag"', "version_id": None}
    assert sdk_client.calls[0]["ServerSideEncryption"] == "cos/kms"
    assert sdk_client.calls[0]["SSEKMSKeyId"] == "kms-key-1"


def test_tencent_cos_sdk_client_translates_presigned_download_url() -> None:
    sdk_client = FakeTencentCosSdkClient(response={"ETag": '"etag"', "VersionId": None})
    client = TencentCosSdkPutObjectClient(sdk_client=sdk_client)

    result = client.create_presigned_download_url(
        bucket="medical-audit-prod",
        region="ap-guangzhou",
        object_key="personal-materials/prod/object.txt",
        expires_in_seconds=600,
    )

    assert result == "https://cos.example/sdk-signed-download"
    assert sdk_client.presign_calls == [
        {
            "Bucket": "medical-audit-prod",
            "Key": "personal-materials/prod/object.txt",
            "Expired": 600,
        }
    ]


def test_document_object_storage_factory_builds_local_by_default(tmp_path: Path) -> None:
    storage = document_object_storage_from_settings(
        DocumentStorageSettings(provider="local"),
        upload_root=tmp_path / "document-uploads",
    )

    assert isinstance(storage, LocalDocumentObjectStorage)
    assert storage.upload_root == tmp_path / "document-uploads"


def test_document_object_storage_factory_requires_cos_client() -> None:
    settings = DocumentStorageSettings(
        provider="tencent-cos",
        cos_bucket="medical-audit-prod",
        cos_region="ap-guangzhou",
    )

    with pytest.raises(ValueError, match="tencent-cos client"):
        document_object_storage_from_settings(
            settings,
            upload_root=Path("unused"),
        )


def test_document_object_storage_factory_builds_tencent_cos_with_injected_client() -> None:
    client = FakeTencentCosClient(
        etag='"8f7dd3a13bfa8f5b67a6b734f4c1a4d7"',
        version_id="cos-version-1",
    )
    storage = document_object_storage_from_settings(
        DocumentStorageSettings(
            provider="tencent-cos",
            cos_bucket="medical-audit-prod",
            cos_region="ap-guangzhou",
            cos_prefix="personal-materials/prod",
            cos_encryption="sse-kms",
            cos_kms_key_id="kms-key-1",
            cos_storage_class="STANDARD_IA",
        ),
        upload_root=Path("unused"),
        tencent_cos_client=client,
    )

    assert isinstance(storage, TencentCosDocumentObjectStorage)
    result = storage.put_object(
        request=DocumentObjectStoragePutRequest(
            upload_key="document-upload-cos456",
            file_name="audit-case.xlsx",
            extension="xlsx",
            content=b"spreadsheet bytes",
            sha256="c" * 64,
            created_at=datetime(2026, 6, 17, 10, 30, tzinfo=UTC),
        )
    )

    assert result.bucket == "medical-audit-prod"
    assert result.region == "ap-guangzhou"
    assert result.storage_class == "STANDARD_IA"
    assert result.encryption_mode == "sse-kms"
    assert client.calls[0]["kms_key_id"] == "kms-key-1"
    assert client.calls[0]["storage_class"] == "STANDARD_IA"


def test_tencent_cos_sdk_bootstrap_disabled_by_default() -> None:
    client = tencent_cos_put_object_client_from_settings(
        DocumentStorageSettings(
            provider="tencent-cos",
            cos_bucket="medical-audit-prod",
            cos_region="ap-guangzhou",
        ),
        environ={"COS_SECRET_ID": "sid", "COS_SECRET_KEY": "skey"},
        qcloud_cos_module=FakeTencentCosSdkModule(),
    )

    assert client is None


def test_tencent_cos_sdk_bootstrap_requires_secret_env_names() -> None:
    with pytest.raises(ValueError, match="cos_secret_id_env, cos_secret_key_env"):
        tencent_cos_put_object_client_from_settings(
            DocumentStorageSettings.model_validate(
                {
                    "provider": "tencent-cos",
                    "cos_bucket": "medical-audit-prod",
                    "cos_region": "ap-guangzhou",
                    "cos_sdk_bootstrap_enabled": True,
                }
            ),
            environ={"COS_SECRET_ID": "sid", "COS_SECRET_KEY": "skey"},
            qcloud_cos_module=FakeTencentCosSdkModule(),
        )


def test_tencent_cos_sdk_bootstrap_requires_secret_values() -> None:
    with pytest.raises(ValueError, match="COS_SECRET_KEY"):
        tencent_cos_put_object_client_from_settings(
            DocumentStorageSettings.model_validate(
                {
                    "provider": "tencent-cos",
                    "cos_bucket": "medical-audit-prod",
                    "cos_region": "ap-guangzhou",
                    "cos_secret_id_env": "COS_SECRET_ID",
                    "cos_secret_key_env": "COS_SECRET_KEY",
                    "cos_sdk_bootstrap_enabled": True,
                }
            ),
            environ={"COS_SECRET_ID": "sid"},
            qcloud_cos_module=FakeTencentCosSdkModule(),
        )


def test_tencent_cos_sdk_bootstrap_builds_client_from_fake_module() -> None:
    module = FakeTencentCosSdkModule()

    client = tencent_cos_put_object_client_from_settings(
        DocumentStorageSettings.model_validate(
            {
                "provider": "tencent-cos",
                "cos_bucket": "medical-audit-prod",
                "cos_region": "ap-guangzhou",
                "cos_secret_id_env": "COS_SECRET_ID",
                "cos_secret_key_env": "COS_SECRET_KEY",
                "cos_sdk_bootstrap_enabled": True,
            }
        ),
        environ={"COS_SECRET_ID": "sid", "COS_SECRET_KEY": "skey"},
        qcloud_cos_module=module,
    )

    assert isinstance(client, TencentCosSdkPutObjectClient)
    assert module.config_calls == [
        {
            "Region": "ap-guangzhou",
            "SecretId": "sid",
            "SecretKey": "skey",
            "Token": None,
            "Scheme": "https",
        }
    ]
    assert module.client_configs == [module.configs[0]]


def test_tencent_cos_bootstrap_preflight_reports_blockers_without_secret_leak() -> None:
    report = tencent_cos_bootstrap_preflight_from_settings(
        DocumentStorageSettings.model_validate(
            {
                "provider": "tencent-cos",
                "cos_bucket": "medical-audit-prod",
                "cos_region": "ap-guangzhou",
                "cos_secret_id_env": "COS_SECRET_ID",
                "cos_secret_key_env": "COS_SECRET_KEY",
                "cos_sdk_bootstrap_enabled": True,
            }
        ),
        environ={"COS_SECRET_ID": "sid-secret"},
        qcloud_cos_available=False,
    )

    assert report["status"] == "blocked"
    assert report["provider"] == "tencent-cos"
    assert "cos-secret-key-env-value-missing" in report["issues"]
    assert "qcloud-cos-sdk-not-installed" in report["issues"]
    assert report["secret_env_names"] == {
        "secret_id": "COS_SECRET_ID",
        "secret_key": "COS_SECRET_KEY",
    }
    assert report["checks"]["secret_id_env_value_present"] is True
    assert report["checks"]["secret_key_env_value_present"] is False
    assert report["checks"]["qcloud_cos_available"] is False
    assert "sid-secret" not in json.dumps(report, ensure_ascii=False)


def test_tencent_cos_bootstrap_preflight_passes_when_dependencies_are_ready() -> None:
    report = tencent_cos_bootstrap_preflight_from_settings(
        DocumentStorageSettings.model_validate(
            {
                "provider": "tencent-cos",
                "cos_bucket": "medical-audit-prod",
                "cos_region": "ap-guangzhou",
                "cos_secret_id_env": "COS_SECRET_ID",
                "cos_secret_key_env": "COS_SECRET_KEY",
                "cos_sdk_bootstrap_enabled": True,
            }
        ),
        environ={"COS_SECRET_ID": "sid-secret", "COS_SECRET_KEY": "key-secret"},
        qcloud_cos_available=True,
    )

    assert report["status"] == "pass"
    assert report["issues"] == []
    assert report["checks"] == {
        "provider_is_tencent_cos": True,
        "cos_sdk_bootstrap_enabled": True,
        "cos_bucket_configured": True,
        "cos_region_configured": True,
        "secret_id_env_name_configured": True,
        "secret_key_env_name_configured": True,
        "secret_id_env_value_present": True,
        "secret_key_env_value_present": True,
        "qcloud_cos_available": True,
    }
    assert "sid-secret" not in json.dumps(report, ensure_ascii=False)
    assert "key-secret" not in json.dumps(report, ensure_ascii=False)


def test_tencent_cos_bootstrap_preflight_detects_installed_sdk() -> None:
    report = tencent_cos_bootstrap_preflight_from_settings(
        DocumentStorageSettings.model_validate(
            {
                "provider": "tencent-cos",
                "cos_bucket": "medical-audit-prod",
                "cos_region": "ap-guangzhou",
                "cos_secret_id_env": "COS_SECRET_ID",
                "cos_secret_key_env": "COS_SECRET_KEY",
                "cos_sdk_bootstrap_enabled": True,
            }
        ),
        environ={"COS_SECRET_ID": "sid-secret", "COS_SECRET_KEY": "key-secret"},
    )

    assert report["status"] == "pass"
    assert report["checks"]["qcloud_cos_available"] is True
    assert "sid-secret" not in json.dumps(report, ensure_ascii=False)
    assert "key-secret" not in json.dumps(report, ensure_ascii=False)


def test_document_cos_bootstrap_preflight_script_outputs_json(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "knowledge-query-engine-cos.yaml"
    config_path.write_text(
        """
data_root: data/医保审核前期资料
index_root: tmp/knowledge-query-indexes
database_url: postgresql+psycopg://medical_audit_kb:medical_audit_kb_dev@localhost:5433/medical_audit_kb
model_provider:
  provider: openai
  api_key_env: OPENAI_API_KEY
  embedding_model: text-embedding-3-small
  rerank_model: null
  chat_model: gpt-4.1-mini
document_storage:
  provider: tencent-cos
  cos_bucket: medical-audit-prod
  cos_region: ap-guangzhou
  cos_secret_id_env: COS_SECRET_ID
  cos_secret_key_env: COS_SECRET_KEY
  cos_sdk_bootstrap_enabled: true
source_collection_weights:
  medical-insurance-catalog: 1.25
  supervision-rules-knowledge: 1.35
  risk-negative-list: 1.1
  medical-insurance-laws: 1.0
""".strip(),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run-document-cos-bootstrap-preflight.py",
            "--config",
            str(config_path),
            "--qcloud-cos-availability",
            "available",
        ],
        cwd=Path(__file__).resolve().parents[2],
        env={
            **os.environ,
            "COS_SECRET_ID": "sid-secret",
            "COS_SECRET_KEY": "key-secret",
        },
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    report = json.loads(completed.stdout)
    assert report["status"] == "pass"
    assert report["checks"]["qcloud_cos_available"] is True
    assert "sid-secret" not in completed.stdout
    assert "key-secret" not in completed.stdout


def test_document_upload_store_can_record_local_storage_object(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'document-storage-records.db'}"
    upload_store = SqlAlchemyDocumentUploadStore(
        database_url=database_url,
        upload_root=tmp_path / "document-uploads",
        create_schema=True,
        record_storage_objects=True,
    )
    upload = upload_store.add_upload(
        file_name="policy.txt",
        extension="txt",
        content=b"policy evidence",
        created_by="auditor-1",
    )
    governance_store = SqlAlchemyDocumentUploadGovernanceStore(database_url=database_url)

    storage_object = governance_store.get_storage_object(
        upload_key=str(upload["id"]),
        provider="local",
    )

    assert storage_object is not None
    assert storage_object["upload_key"] == upload["id"]
    assert storage_object["provider"] == "local"
    assert storage_object["object_key"] == upload["storage_path"]
    assert storage_object["sha256"] == upload["sha256"]
    assert storage_object["size_bytes"] == upload["size_bytes"]
    assert storage_object["storage_status"] == "local-quarantine"
    assert storage_object["metadata"] == {
        "storage_backend": "local-filesystem",
        "file_name": "policy.txt",
    }


def test_document_upload_store_records_storage_object_with_foreign_keys_enforced(
    tmp_path: Path,
) -> None:
    event.listen(Engine, "connect", _enable_sqlite_foreign_keys)
    try:
        database_url = f"sqlite:///{tmp_path / 'document-storage-fk-records.db'}"
        upload_store = SqlAlchemyDocumentUploadStore(
            database_url=database_url,
            upload_root=tmp_path / "document-uploads",
            create_schema=True,
            record_storage_objects=True,
        )
        upload = upload_store.add_upload(
            file_name="policy.txt",
            extension="txt",
            content=b"policy evidence",
            created_by="auditor-1",
        )
    finally:
        event.remove(Engine, "connect", _enable_sqlite_foreign_keys)

    governance_store = SqlAlchemyDocumentUploadGovernanceStore(database_url=database_url)
    storage_object = governance_store.get_storage_object(
        upload_key=str(upload["id"]),
        provider="local",
    )

    assert storage_object is not None
    assert storage_object["upload_key"] == upload["id"]


def test_document_storage_objects_schema_ready_detects_created_table(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'document-storage-schema.db'}"

    assert document_storage_objects_schema_ready(database_url) is False

    SqlAlchemyDocumentUploadStore(
        database_url=database_url,
        upload_root=tmp_path / "document-uploads",
        create_schema=True,
    )

    assert document_storage_objects_schema_ready(database_url) is True


def test_document_upload_governance_store_tracks_storage_and_jobs(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'document-governance.db'}"
    upload_store = SqlAlchemyDocumentUploadStore(
        database_url=database_url,
        upload_root=tmp_path / "document-uploads",
        create_schema=True,
    )
    upload = upload_store.add_upload(
        file_name="policy.txt",
        extension="txt",
        content=b"policy evidence",
        created_by="auditor-1",
    )
    store = SqlAlchemyDocumentUploadGovernanceStore(database_url=database_url)

    storage = store.upsert_storage_object(
        DocumentStorageObjectCreate(
            upload_key=str(upload["id"]),
            provider="local",
            object_key=str(upload["storage_path"]),
            sha256=str(upload["sha256"]),
            size_bytes=cast(int, upload["size_bytes"]),
            storage_status="local-quarantine",
            metadata={"source": "unit-test"},
        )
    )
    updated_storage = store.upsert_storage_object(
        DocumentStorageObjectCreate(
            upload_key=str(upload["id"]),
            provider="local",
            object_key=str(upload["storage_path"]),
            sha256=str(upload["sha256"]),
            size_bytes=cast(int, upload["size_bytes"]),
            storage_status="object-stored",
            metadata={"source": "unit-test", "synced": True},
        )
    )

    assert storage["storage_status"] == "local-quarantine"
    assert updated_storage["storage_status"] == "object-stored"
    assert updated_storage["metadata"] == {"source": "unit-test", "synced": True}
    assert store.get_storage_object(upload_key=str(upload["id"]), provider="local") == (
        updated_storage
    )
    assert store.list_storage_objects(str(upload["id"])) == [updated_storage]

    job = store.create_governance_job(
        DocumentUploadGovernanceJobCreate(
            upload_key=str(upload["id"]),
            job_type="virus-scan",
            provider="tencent-ci-virus",
            external_job_id="ci-job-1",
        )
    )
    finished_at = datetime(2026, 6, 16, 12, 0, tzinfo=UTC)
    updated_job = store.update_governance_job_status(
        job_key=str(job["job_key"]),
        status="passed",
        result_payload={"result_code": "normal"},
        finished_at=finished_at,
    )

    assert str(job["job_key"]).startswith(DOCUMENT_UPLOAD_GOVERNANCE_JOB_ID_PREFIX)
    assert job["status"] == "pending"
    assert updated_job is not None
    assert updated_job["status"] == "passed"
    assert updated_job["result_payload"] == {"result_code": "normal"}
    assert updated_job["finished_at"] == "2026-06-16T12:00:00Z"
    assert store.list_governance_jobs(str(upload["id"])) == [updated_job]


def test_local_recording_governance_submitter_records_external_pending_jobs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIRUS_SCAN_JOB_SECRET", "actual-secret-value")
    monkeypatch.setenv("DLP_REVIEW_JOB_SECRET", "actual-secret-value")
    database_url = f"sqlite:///{tmp_path / 'document-governance-submit.db'}"
    upload_store = SqlAlchemyDocumentUploadStore(
        database_url=database_url,
        upload_root=tmp_path / "document-uploads",
        create_schema=True,
        record_storage_objects=True,
    )
    upload = upload_store.add_upload(
        file_name="policy.txt",
        extension="txt",
        content=b"policy evidence",
        created_by="auditor-1",
    )
    governance_store = SqlAlchemyDocumentUploadGovernanceStore(database_url=database_url)
    submitter = LocalRecordingDocumentUploadGovernanceJobSubmitter(
        provider_env_contracts={
            "tencent-ci-virus": {
                "endpoint_env": "VIRUS_SCAN_JOB_ENDPOINT",
                "secret_env": "VIRUS_SCAN_JOB_SECRET",
            },
            "external-dlp": {
                "endpoint_env": "DLP_REVIEW_JOB_ENDPOINT",
                "secret_env": "DLP_REVIEW_JOB_SECRET",
            },
        }
    )
    index_readiness = {
        "checks": [
            {
                "check_type": "virus-scan",
                "provider": "tencent-ci-virus",
                "status": "blocked",
                "blocker": "virus-scan-required",
                "detail": "external result required",
                "result_code": "pending-external-result",
            },
            {
                "check_type": "dlp-review",
                "provider": "external-dlp",
                "status": "blocked",
                "blocker": "dlp-review-required",
                "detail": "external result required",
                "result_code": "pending-external-result",
            },
            {
                "check_type": "manual-index-approval",
                "provider": "manual",
                "status": "blocked",
                "blocker": "manual-index-approval-required",
                "detail": "manual approval required",
            },
        ]
    }

    jobs = submit_required_document_upload_governance_jobs(
        upload=upload,
        index_readiness=index_readiness,
        storage_objects=upload_store.list_storage_objects(str(upload["id"])),
        store=governance_store,
        submitter=submitter,
    )

    assert [job["job_type"] for job in jobs] == ["virus-scan", "dlp-review"]
    assert [job["status"] for job in jobs] == ["pending", "pending"]
    assert jobs[0]["external_job_id"] == f"local-recording-virus-scan-{upload['id']}"
    assert jobs[1]["external_job_id"] == f"local-recording-dlp-review-{upload['id']}"
    assert jobs[0]["result_payload"]["external_provider_call_performed"] is False
    assert jobs[0]["result_payload"]["production_write_performed"] is False
    assert jobs[0]["result_payload"]["provider_env_contract"] == {
        "endpoint_env": "VIRUS_SCAN_JOB_ENDPOINT",
        "secret_env": "VIRUS_SCAN_JOB_SECRET",
    }
    assert jobs[1]["result_payload"]["provider_env_contract"] == {
        "endpoint_env": "DLP_REVIEW_JOB_ENDPOINT",
        "secret_env": "DLP_REVIEW_JOB_SECRET",
    }
    serialized = json.dumps(jobs, ensure_ascii=False)
    assert "actual-secret-value" not in serialized
    assert governance_store.list_governance_jobs(str(upload["id"])) == jobs


def _enable_sqlite_foreign_keys(
    dbapi_connection: object,
    _connection_record: object,
) -> None:
    if not isinstance(dbapi_connection, SQLiteConnection):
        return
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


class FakeTencentCosClient:
    def __init__(
        self,
        *,
        etag: str,
        version_id: str,
        signed_url: str = "https://cos.example/signed-download",
    ) -> None:
        self.etag = etag
        self.version_id = version_id
        self.signed_url = signed_url
        self.calls: list[dict[str, object]] = []
        self.presign_calls: list[dict[str, object]] = []

    def put_object(
        self,
        *,
        bucket: str,
        region: str,
        object_key: str,
        content: bytes,
        content_type: str,
        metadata: dict[str, str],
        encryption_mode: str,
        kms_key_id: str | None,
        storage_class: str,
    ) -> dict[str, str]:
        self.calls.append(
            {
                "bucket": bucket,
                "region": region,
                "object_key": object_key,
                "content": content,
                "content_type": content_type,
                "metadata": metadata,
                "encryption_mode": encryption_mode,
                "kms_key_id": kms_key_id,
                "storage_class": storage_class,
            }
        )
        return {"etag": self.etag, "version_id": self.version_id}

    def create_presigned_download_url(
        self,
        *,
        bucket: str,
        region: str,
        object_key: str,
        expires_in_seconds: int,
    ) -> str:
        self.presign_calls.append(
            {
                "bucket": bucket,
                "region": region,
                "object_key": object_key,
                "expires_in_seconds": expires_in_seconds,
            }
        )
        return self.signed_url


class FakeTencentCosSdkClient:
    def __init__(
        self,
        *,
        response: dict[str, object],
        signed_url: str = "https://cos.example/sdk-signed-download",
    ) -> None:
        self.response = response
        self.signed_url = signed_url
        self.calls: list[dict[str, object]] = []
        self.presign_calls: list[dict[str, object]] = []

    def put_object(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(kwargs)
        return dict(self.response)

    def get_presigned_download_url(self, **kwargs: object) -> str:
        self.presign_calls.append(kwargs)
        return self.signed_url


class FakeTencentCosSdkModule:
    def __init__(self) -> None:
        self.config_calls: list[dict[str, object]] = []
        self.configs: list[dict[str, object]] = []
        self.client_configs: list[dict[str, object]] = []

    def CosConfig(self, **kwargs: object) -> dict[str, object]:  # noqa: N802
        config = dict(kwargs)
        self.config_calls.append(config)
        self.configs.append(config)
        return config

    def CosS3Client(self, config: object) -> FakeTencentCosSdkClient:  # noqa: N802
        assert isinstance(config, dict)
        self.client_configs.append(config)
        return FakeTencentCosSdkClient(response={"ETag": '"etag"', "VersionId": "version-1"})
