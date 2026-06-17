from datetime import UTC, datetime
from pathlib import Path

from medical_audit_kb.api.document_upload_governance_store import (
    DOCUMENT_UPLOAD_GOVERNANCE_JOB_ID_PREFIX,
    DocumentObjectStoragePutRequest,
    DocumentStorageObjectCreate,
    DocumentUploadGovernanceJobCreate,
    LocalDocumentObjectStorage,
    SqlAlchemyDocumentUploadGovernanceStore,
)
from medical_audit_kb.api.document_upload_store import SqlAlchemyDocumentUploadStore


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
            size_bytes=int(upload["size_bytes"]),
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
            size_bytes=int(upload["size_bytes"]),
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

    assert job["job_key"].startswith(DOCUMENT_UPLOAD_GOVERNANCE_JOB_ID_PREFIX)
    assert job["status"] == "pending"
    assert updated_job is not None
    assert updated_job["status"] == "passed"
    assert updated_job["result_payload"] == {"result_code": "normal"}
    assert updated_job["finished_at"] == "2026-06-16T12:00:00Z"
    assert store.list_governance_jobs(str(upload["id"])) == [updated_job]
