from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
from uuid import UUID

from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from medical_audit_kb.api.document_upload_governance_store import DocumentObjectStorage
from medical_audit_kb.api.document_upload_store import _connect_args, _sync_database_url
from medical_audit_kb.core.config import DocumentUploadIndexingSettings
from medical_audit_kb.db.models import (
    ChunkEmbedding,
    DocumentChunk,
    DocumentStorageObject,
    DocumentUploadRecord,
    IndexVersion,
    SourceDocument,
    SourcePackageVersion,
)
from medical_audit_kb.domain.constants import DocumentStatus, SourceCollection
from medical_audit_kb.domain.schemas import DocumentChunkCreate
from medical_audit_kb.indexing.embeddings import DeterministicFakeEmbeddingProvider
from medical_audit_kb.ingestion.chunkers import chunk_extraction_result
from medical_audit_kb.ingestion.extractors import ExtractionStatus, extract_file

DocumentUploadIngestionStatus = Literal["staged-for-index", "already-staged"]


@dataclass(frozen=True, slots=True)
class DocumentUploadIngestionResult:
    status: DocumentUploadIngestionStatus
    upload_key: str
    source_collection: str
    source_package_version_key: str
    index_version_key: str
    index_version_status: str
    source_document_id: str
    chunk_count: int
    embedding_count: int
    embedding_provider: str
    embedding_model: str
    embedding_dimension: int
    external_provider_call_performed: bool = False
    live_retrieval_activated: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "upload_key": self.upload_key,
            "source_collection": self.source_collection,
            "source_package_version_key": self.source_package_version_key,
            "index_version_key": self.index_version_key,
            "index_version_status": self.index_version_status,
            "source_document_id": self.source_document_id,
            "chunk_count": self.chunk_count,
            "embedding_count": self.embedding_count,
            "embedding_provider": self.embedding_provider,
            "embedding_model": self.embedding_model,
            "embedding_dimension": self.embedding_dimension,
            "external_provider_call_performed": self.external_provider_call_performed,
            "live_retrieval_activated": self.live_retrieval_activated,
        }


class DocumentUploadIngestionError(RuntimeError):
    def __init__(
        self,
        reason: str,
        detail: str,
        *,
        status_code: int = 409,
        payload: dict[str, object] | None = None,
    ) -> None:
        super().__init__(detail)
        self.reason = reason
        self.detail = detail
        self.status_code = status_code
        self.payload = payload or {}


@dataclass(frozen=True, slots=True)
class ResolvedUploadSource:
    path: Path
    ingestion_source: str
    storage_provider: str | None = None
    object_key: str | None = None


@dataclass(slots=True)
class SqlAlchemyDocumentUploadIndexer:
    database_url: str
    upload_root: Path
    settings: DocumentUploadIndexingSettings
    object_storage: DocumentObjectStorage | None = None
    _engine: Engine = field(init=False, repr=False)
    _session_factory: sessionmaker[Session] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._engine = create_engine(
            _sync_database_url(self.database_url),
            connect_args=_connect_args(self.database_url),
            pool_pre_ping=True,
        )
        self._session_factory = sessionmaker(self._engine, expire_on_commit=False)

    def ingest_upload(self, upload_key: str, *, actor: str | None) -> DocumentUploadIngestionResult:
        if not self.settings.enabled:
            raise DocumentUploadIngestionError(
                "document-upload-indexing-disabled",
                "document upload indexing is not enabled",
            )
        provider = DeterministicFakeEmbeddingProvider(
            dimension=self.settings.embedding_dimension,
        )
        with self._session_factory.begin() as session:
            upload = _get_upload_record(session, upload_key)
            if upload is None:
                raise DocumentUploadIngestionError(
                    "document-upload-not-found",
                    "document upload not found",
                    status_code=404,
                )
            metadata = dict(upload.extra_metadata)
            if metadata.get("index_status") == "staged-for-index":
                return _already_staged_result(upload, metadata, provider=provider)
            _validate_upload_ready(upload, metadata)
            source = _resolve_upload_source(
                session,
                self.upload_root,
                upload=upload,
                object_storage=self.object_storage,
            )
            extraction = extract_file(source.path)
            if extraction.status != ExtractionStatus.EXTRACTED:
                raise DocumentUploadIngestionError(
                    "document-upload-extraction-not-ready",
                    extraction.error_summary or "document upload text extraction is not ready",
                    payload={
                        "extraction_status": extraction.status.value,
                        "error_type": extraction.error_type.value
                        if extraction.error_type is not None
                        else None,
                    },
                )

            package = _upsert_source_package(
                session,
                version_key=self.settings.source_package_version_key,
                upload_root=self.upload_root,
            )
            document = _upsert_source_document(
                session,
                package=package,
                upload=upload,
                source=source,
                media_type=extraction.media_type,
            )
            session.flush()
            _clear_existing_chunks(session, document.id)
            chunks = chunk_extraction_result(
                extraction,
                source_document_id=document.id,
                source_collection=SourceCollection.PERSONAL_MATERIALS,
                relative_path=document.relative_path,
            )
            chunk_records = [
                _chunk_record(
                    chunk,
                    upload=upload,
                    source_package_version_key=package.version_key,
                    index_version_key=self.settings.index_version_key,
                )
                for chunk in chunks
            ]
            if not chunk_records:
                raise DocumentUploadIngestionError(
                    "document-upload-no-indexable-chunks",
                    "document upload produced no indexable chunks",
                )
            session.add_all(chunk_records)
            session.flush()
            embeddings = provider.embed_texts([chunk.text for chunk in chunk_records])
            session.add_all(
                ChunkEmbedding(
                    chunk_id=chunk.id,
                    provider=provider.provider,
                    model_name=provider.model_name,
                    provider_version=provider.provider_version,
                    dimension=provider.dimension,
                    embedding=list(embedding),
                )
                for chunk, embedding in zip(chunk_records, embeddings, strict=True)
            )
            _upsert_index_version(
                session,
                package=package,
                settings=self.settings,
                provider=provider,
            )
            result = DocumentUploadIngestionResult(
                status="staged-for-index",
                upload_key=upload.upload_key,
                source_collection=SourceCollection.PERSONAL_MATERIALS.value,
                source_package_version_key=package.version_key,
                index_version_key=self.settings.index_version_key,
                index_version_status=self.settings.index_version_status,
                source_document_id=str(document.id),
                chunk_count=len(chunk_records),
                embedding_count=len(chunk_records),
                embedding_provider=provider.provider,
                embedding_model=provider.model_name,
                embedding_dimension=provider.dimension,
            )
            upload.extra_metadata = _indexed_upload_metadata(
                metadata,
                actor=actor,
                result=result,
            )
            session.flush()
            return result


def document_upload_indexer_from_settings(
    *,
    database_url: str,
    upload_root: Path,
    settings: DocumentUploadIndexingSettings,
    object_storage: DocumentObjectStorage | None = None,
) -> SqlAlchemyDocumentUploadIndexer | None:
    if not settings.enabled:
        return None
    return SqlAlchemyDocumentUploadIndexer(
        database_url=database_url,
        upload_root=upload_root,
        settings=settings,
        object_storage=object_storage,
    )


def _get_upload_record(session: Session, upload_key: str) -> DocumentUploadRecord | None:
    return session.scalars(
        select(DocumentUploadRecord).where(DocumentUploadRecord.upload_key == upload_key)
    ).one_or_none()


def _validate_upload_ready(upload: DocumentUploadRecord, metadata: dict[str, object]) -> None:
    readiness = metadata.get("index_readiness")
    if not isinstance(readiness, dict) or readiness.get("status") != "ready":
        raise DocumentUploadIngestionError(
            "document-upload-not-ready-for-indexing",
            "document upload is not ready for indexing",
            payload={"index_readiness": copy.deepcopy(readiness)},
        )
    if metadata.get("index_status", "not-indexed") != "not-indexed":
        raise DocumentUploadIngestionError(
            "document-upload-index-status-not-ingestable",
            f"document upload index_status is not ingestible: {metadata.get('index_status')}",
            payload={"index_status": str(metadata.get("index_status"))},
        )
    if upload.visibility != "private" or upload.status != "retained":
        raise DocumentUploadIngestionError(
            "document-upload-state-not-ingestable",
            "document upload must be private and retained before indexing",
            payload={"visibility": upload.visibility, "status": upload.status},
        )


def _resolve_upload_source(
    session: Session,
    upload_root: Path,
    *,
    upload: DocumentUploadRecord,
    object_storage: DocumentObjectStorage | None,
) -> ResolvedUploadSource:
    local_path = _resolve_local_upload_path(
        upload_root,
        storage_path=upload.storage_path,
        raise_when_missing=False,
    )
    if local_path is not None:
        return ResolvedUploadSource(path=local_path, ingestion_source="local-quarantine")
    if object_storage is None:
        raise DocumentUploadIngestionError(
            "document-upload-local-file-unavailable",
            "document upload local quarantine file is unavailable for indexing",
            payload={"storage_path": upload.storage_path},
        )
    storage_object = _get_ingestable_storage_object(
        session,
        upload_key=upload.upload_key,
        provider=object_storage.provider,
    )
    if storage_object is None:
        raise DocumentUploadIngestionError(
            "document-upload-storage-object-unavailable",
            "document upload storage object is unavailable for indexing",
            payload={
                "upload_key": upload.upload_key,
                "storage_provider": object_storage.provider,
            },
        )
    read_result = object_storage.read_object(object_key=storage_object.object_key)
    actual_sha256 = hashlib.sha256(read_result.content).hexdigest()
    if actual_sha256 != upload.sha256:
        raise DocumentUploadIngestionError(
            "document-upload-object-sha256-mismatch",
            "document upload object sha256 does not match the retained upload record",
            payload={
                "upload_key": upload.upload_key,
                "expected_sha256": upload.sha256,
                "actual_sha256": actual_sha256,
            },
        )
    staged_path = _write_staged_upload_source(
        upload_root,
        upload=upload,
        content=read_result.content,
    )
    return ResolvedUploadSource(
        path=staged_path,
        ingestion_source="object-storage-staging",
        storage_provider=storage_object.provider,
        object_key=storage_object.object_key,
    )


def _resolve_local_upload_path(
    upload_root: Path,
    *,
    storage_path: str,
    raise_when_missing: bool = True,
) -> Path | None:
    relative_path = Path(storage_path)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise DocumentUploadIngestionError(
            "document-upload-storage-path-invalid",
            "document upload storage path is invalid",
        )
    source_path = upload_root / relative_path
    if not source_path.exists() or not source_path.is_file():
        if not raise_when_missing:
            return None
        raise DocumentUploadIngestionError(
            "document-upload-local-file-unavailable",
            "document upload local quarantine file is unavailable for indexing",
            payload={"storage_path": storage_path},
        )
    return source_path


def _get_ingestable_storage_object(
    session: Session,
    *,
    upload_key: str,
    provider: str,
) -> DocumentStorageObject | None:
    return session.scalars(
        select(DocumentStorageObject)
        .where(
            DocumentStorageObject.upload_key == upload_key,
            DocumentStorageObject.provider == provider,
            DocumentStorageObject.storage_status.in_(("object-stored", "local-quarantine")),
        )
        .order_by(DocumentStorageObject.created_at.desc())
    ).first()


def _write_staged_upload_source(
    upload_root: Path,
    *,
    upload: DocumentUploadRecord,
    content: bytes,
) -> Path:
    staged_path = upload_root / ".index-staging" / upload.upload_key / _safe_file_name(
        upload.file_name
    )
    staged_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = staged_path.with_suffix(f"{staged_path.suffix}.tmp")
    temp_path.write_bytes(content)
    temp_path.replace(staged_path)
    return staged_path


def _upsert_source_package(
    session: Session,
    *,
    version_key: str,
    upload_root: Path,
) -> SourcePackageVersion:
    package = session.scalars(
        select(SourcePackageVersion).where(SourcePackageVersion.version_key == version_key)
    ).one_or_none()
    metadata = {
        "source": "document-upload-indexing",
        "live_retrieval_activated": False,
    }
    if package is None:
        package = SourcePackageVersion(
            version_key=version_key,
            source_root_path=str(upload_root),
            description="Personal document uploads staged as candidate index material.",
            extra_metadata=metadata,
        )
        session.add(package)
        session.flush()
        return package
    if package.extra_metadata.get("source") != "document-upload-indexing":
        raise DocumentUploadIngestionError(
            "document-upload-source-package-key-collision",
            "document upload source package key already belongs to another index source",
            payload={"source_package_version_key": version_key},
        )
    package.source_root_path = str(upload_root)
    package.extra_metadata = metadata
    return package


def _upsert_source_document(
    session: Session,
    *,
    package: SourcePackageVersion,
    upload: DocumentUploadRecord,
    source: ResolvedUploadSource,
    media_type: str,
) -> SourceDocument:
    relative_path = _source_relative_path(upload)
    source_metadata: dict[str, object] = {
        "source": "document-upload",
        "upload_key": upload.upload_key,
        "created_by": upload.created_by,
        "visibility": upload.visibility,
        "storage_path": upload.storage_path,
        "ingestion_source": source.ingestion_source,
    }
    if source.storage_provider:
        source_metadata["storage_provider"] = source.storage_provider
    if source.object_key:
        source_metadata["object_key"] = source.object_key
    document = session.scalars(
        select(SourceDocument).where(
            SourceDocument.source_package_version_id == package.id,
            SourceDocument.relative_path == relative_path,
        )
    ).one_or_none()
    values = {
        "source_package_version_id": package.id,
        "source_collection": SourceCollection.PERSONAL_MATERIALS.value,
        "relative_path": relative_path,
        "absolute_path": str(source.path),
        "file_name": _safe_file_name(upload.file_name),
        "file_ext": f".{upload.extension.lower()}",
        "media_type": media_type,
        "sha256": upload.sha256,
        "size_bytes": upload.size_bytes,
        "status": DocumentStatus.INDEXED.value,
        "extra_metadata": source_metadata,
    }
    if document is None:
        document = SourceDocument(**values)
        session.add(document)
        return document
    for key, value in values.items():
        setattr(document, key, value)
    return document


def _clear_existing_chunks(session: Session, source_document_id: UUID) -> None:
    for chunk in session.scalars(
        select(DocumentChunk).where(DocumentChunk.source_document_id == source_document_id)
    ).all():
        session.delete(chunk)
    session.flush()


def _chunk_record(
    chunk: DocumentChunkCreate,
    *,
    upload: DocumentUploadRecord,
    source_package_version_key: str,
    index_version_key: str,
) -> DocumentChunk:
    metadata = dict(chunk.metadata)
    locator = dict(chunk.locator)
    locator["upload_key"] = upload.upload_key
    metadata.update(
        {
            "source_collection": SourceCollection.PERSONAL_MATERIALS.value,
            "source_package_version_key": source_package_version_key,
            "index_version_key": index_version_key,
            "upload_key": upload.upload_key,
            "created_by": upload.created_by,
            "visibility": upload.visibility,
            "live_retrieval_activated": False,
            "locator": locator,
        }
    )
    return DocumentChunk(
        source_document_id=chunk.source_document_id,
        chunk_index=chunk.chunk_index,
        text=chunk.text,
        title_path=list(chunk.title_path),
        article_number=chunk.article_number,
        page_number=chunk.page_number,
        line_start=chunk.line_start,
        line_end=chunk.line_end,
        sheet_name=chunk.sheet_name,
        row_number=chunk.row_number,
        token_count=chunk.token_count,
        locator=locator,
        extra_metadata=metadata,
    )


def _upsert_index_version(
    session: Session,
    *,
    package: SourcePackageVersion,
    settings: DocumentUploadIndexingSettings,
    provider: DeterministicFakeEmbeddingProvider,
) -> IndexVersion:
    index_version = session.scalars(
        select(IndexVersion).where(IndexVersion.version_key == settings.index_version_key)
    ).one_or_none()
    if index_version is not None and (
        index_version.source_package_version_id != package.id
        or index_version.status != settings.index_version_status
        or index_version.extra_metadata.get("source") != "document-upload-indexing"
    ):
        raise DocumentUploadIngestionError(
            "document-upload-index-version-key-collision",
            "document upload index version key already belongs to another index source",
            payload={"index_version_key": settings.index_version_key},
        )
    chunk_count = _chunk_count(session, package.id)
    document_count = _document_count(session, package.id)
    values = {
        "source_package_version_id": package.id,
        "version_key": settings.index_version_key,
        "status": settings.index_version_status,
        "bm25_index_path": None,
        "vector_provider": provider.provider,
        "vector_model": provider.model_name,
        "chunk_count": chunk_count,
        "document_count": document_count,
        "extra_metadata": {
            "source": "document-upload-indexing",
            "source_collection": SourceCollection.PERSONAL_MATERIALS.value,
            "embedding_dimension": provider.dimension,
            "external_provider_call_performed": False,
            "live_retrieval_activated": False,
        },
        "activated_at": None,
    }
    if index_version is None:
        index_version = IndexVersion(**values)
        session.add(index_version)
        return index_version
    for key, value in values.items():
        setattr(index_version, key, value)
    return index_version


def _indexed_upload_metadata(
    metadata: dict[str, object],
    *,
    actor: str | None,
    result: DocumentUploadIngestionResult,
) -> dict[str, object]:
    updated = dict(metadata)
    updated["index_status"] = "staged-for-index"
    ingestion = result.to_dict()
    ingestion["actor"] = actor
    updated["index_ingestion"] = ingestion
    return updated


def _already_staged_result(
    upload: DocumentUploadRecord,
    metadata: dict[str, object],
    *,
    provider: DeterministicFakeEmbeddingProvider,
) -> DocumentUploadIngestionResult:
    ingestion = metadata.get("index_ingestion")
    if not isinstance(ingestion, dict):
        raise DocumentUploadIngestionError(
            "document-upload-index-ingestion-metadata-missing",
            "document upload index ingestion metadata is missing",
        )
    return DocumentUploadIngestionResult(
        status="already-staged",
        upload_key=upload.upload_key,
        source_collection=str(
            ingestion.get("source_collection") or SourceCollection.PERSONAL_MATERIALS.value
        ),
        source_package_version_key=str(ingestion.get("source_package_version_key") or ""),
        index_version_key=str(ingestion.get("index_version_key") or ""),
        index_version_status=str(ingestion.get("index_version_status") or "candidate"),
        source_document_id=str(ingestion.get("source_document_id") or ""),
        chunk_count=int(ingestion.get("chunk_count") or 0),
        embedding_count=int(ingestion.get("embedding_count") or 0),
        embedding_provider=str(ingestion.get("embedding_provider") or provider.provider),
        embedding_model=str(ingestion.get("embedding_model") or provider.model_name),
        embedding_dimension=int(ingestion.get("embedding_dimension") or provider.dimension),
    )


def _document_count(session: Session, package_id: UUID) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(SourceDocument)
            .where(SourceDocument.source_package_version_id == package_id)
        )
        or 0
    )


def _chunk_count(session: Session, package_id: UUID) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(DocumentChunk)
            .join(SourceDocument, SourceDocument.id == DocumentChunk.source_document_id)
            .where(SourceDocument.source_package_version_id == package_id)
        )
        or 0
    )


def _source_relative_path(upload: DocumentUploadRecord) -> str:
    return f"personal-materials/{upload.upload_key}/{_safe_file_name(upload.file_name)}"


def _safe_file_name(file_name: str) -> str:
    name = Path(file_name).name.strip()
    return name or "uploaded-document"
