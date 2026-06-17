from datetime import UTC, datetime
from pathlib import Path
from sqlite3 import Connection as SQLiteConnection
from typing import cast

from sqlalchemy import event
from sqlalchemy.engine import Engine

from medical_audit_kb.api.document_upload_governance_store import (
    DOCUMENT_UPLOAD_GOVERNANCE_JOB_ID_PREFIX,
    DocumentObjectStoragePutRequest,
    DocumentStorageObjectCreate,
    DocumentUploadGovernanceJobCreate,
    LocalDocumentObjectStorage,
    SqlAlchemyDocumentUploadGovernanceStore,
    TencentCosDocumentObjectStorage,
)
from medical_audit_kb.api.document_upload_store import (
    SqlAlchemyDocumentUploadStore,
    document_storage_objects_schema_ready,
)


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
        "personal-materials/test/2026/06/17/"
        f"document-upload-cos123/{'b' * 64}.txt"
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
    def __init__(self, *, etag: str, version_id: str) -> None:
        self.etag = etag
        self.version_id = version_id
        self.calls: list[dict[str, object]] = []

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
