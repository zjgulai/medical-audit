from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from medical_audit_kb.db.models import (
    ChunkEmbedding,
    DocumentChunk,
    FailedFile,
    SourceDocument,
    SourcePackageVersion,
)
from medical_audit_kb.domain.schemas import (
    ChunkEmbeddingCreate,
    DocumentChunkCreate,
    FailedFileCreate,
    SourceDocumentUpsert,
    SourcePackageVersionCreate,
)


class KnowledgeBaseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_source_package_version(
        self, payload: SourcePackageVersionCreate
    ) -> SourcePackageVersion:
        package = SourcePackageVersion(
            version_key=payload.version_key,
            source_root_path=str(payload.source_root_path),
            description=payload.description,
            extra_metadata=payload.metadata,
        )
        self._session.add(package)
        await self._session.flush()
        return package

    async def upsert_source_document(self, payload: SourceDocumentUpsert) -> SourceDocument:
        result = await self._session.execute(
            select(SourceDocument).where(
                SourceDocument.source_package_version_id == payload.source_package_version_id,
                SourceDocument.relative_path == payload.relative_path,
            )
        )
        existing = result.scalar_one_or_none()

        values = _source_document_values(payload)
        if existing is None:
            document = SourceDocument(**values)
            self._session.add(document)
            await self._session.flush()
            return document

        for key, value in values.items():
            setattr(existing, key, value)
        await self._session.flush()
        return existing

    async def add_document_chunks(
        self, payloads: Sequence[DocumentChunkCreate]
    ) -> list[DocumentChunk]:
        chunks = [
            DocumentChunk(
                source_document_id=payload.source_document_id,
                chunk_index=payload.chunk_index,
                text=payload.text,
                title_path=payload.title_path,
                article_number=payload.article_number,
                page_number=payload.page_number,
                line_start=payload.line_start,
                line_end=payload.line_end,
                sheet_name=payload.sheet_name,
                row_number=payload.row_number,
                token_count=payload.token_count,
                locator=payload.locator,
                extra_metadata=payload.metadata,
            )
            for payload in payloads
        ]
        self._session.add_all(chunks)
        await self._session.flush()
        return chunks

    async def upsert_chunk_embedding(self, payload: ChunkEmbeddingCreate) -> ChunkEmbedding:
        result = await self._session.execute(
            select(ChunkEmbedding).where(
                ChunkEmbedding.chunk_id == payload.chunk_id,
                ChunkEmbedding.provider == payload.provider,
                ChunkEmbedding.model_name == payload.model_name,
                ChunkEmbedding.provider_version == payload.provider_version,
            )
        )
        existing = result.scalar_one_or_none()
        values = {
            "chunk_id": payload.chunk_id,
            "provider": payload.provider,
            "model_name": payload.model_name,
            "provider_version": payload.provider_version,
            "dimension": payload.dimension,
            "embedding": payload.embedding,
        }
        if existing is None:
            embedding = ChunkEmbedding(**values)
            self._session.add(embedding)
            await self._session.flush()
            return embedding

        for key, value in values.items():
            setattr(existing, key, value)
        await self._session.flush()
        return existing

    async def add_failed_file(self, payload: FailedFileCreate) -> FailedFile:
        failed_file = FailedFile(
            source_package_version_id=payload.source_package_version_id,
            source_document_id=payload.source_document_id,
            relative_path=payload.relative_path,
            error_type=payload.error_type.value,
            error_summary=payload.error_summary,
            retry_count=payload.retry_count,
            status=payload.status.value,
        )
        self._session.add(failed_file)
        await self._session.flush()
        return failed_file


def _source_document_values(payload: SourceDocumentUpsert) -> dict[str, Any]:
    return {
        "source_package_version_id": payload.source_package_version_id,
        "source_collection": payload.source_collection.value,
        "relative_path": payload.relative_path,
        "absolute_path": payload.absolute_path,
        "file_name": payload.file_name,
        "file_ext": payload.file_ext,
        "media_type": payload.media_type,
        "sha256": payload.sha256,
        "size_bytes": payload.size_bytes,
        "status": payload.status.value,
        "extra_metadata": payload.metadata,
    }
