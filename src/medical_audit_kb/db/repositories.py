from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from medical_audit_kb.db.models import (
    ChunkEmbedding,
    DocumentChunk,
    FailedFile,
    ReviewAction,
    ReviewComment,
    ReviewTask,
    SourceDocument,
    SourcePackageVersion,
)
from medical_audit_kb.domain.schemas import (
    ChunkEmbeddingCreate,
    DocumentChunkCreate,
    FailedFileCreate,
    ReviewActionCreate,
    ReviewCommentCreate,
    ReviewTaskCreate,
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


class ReviewTaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_task(self, payload: ReviewTaskCreate) -> ReviewTask:
        task = ReviewTask(
            external_task_id=payload.external_task_id,
            question=payload.question,
            status=payload.status,
            status_label=payload.status_label,
            citation_count=payload.citation_count,
            review_gate=payload.review_gate,
            confidence_label=payload.confidence_label,
            fallback_label=payload.fallback_label,
            reviewer_note=payload.reviewer_note,
            conclusion=payload.conclusion,
            created_by=payload.created_by,
            assigned_to=payload.assigned_to,
            source=payload.source,
            dossier=payload.dossier,
        )
        self._session.add(task)
        await self._session.flush()
        return task

    async def get_task(self, task_id: UUID) -> ReviewTask | None:
        result = await self._session.execute(select(ReviewTask).where(ReviewTask.id == task_id))
        return result.scalar_one_or_none()

    async def list_tasks(self, *, limit: int | None = None) -> list[ReviewTask]:
        statement = select(ReviewTask).order_by(ReviewTask.created_at.desc())
        if limit is not None:
            statement = statement.limit(limit)
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def add_action(self, payload: ReviewActionCreate) -> ReviewAction:
        action = ReviewAction(
            review_task_id=payload.review_task_id,
            action_type=payload.action_type,
            from_status=payload.from_status,
            to_status=payload.to_status,
            actor=payload.actor,
            note=payload.note,
            extra_metadata=payload.metadata,
        )
        self._session.add(action)
        await self._session.flush()
        return action

    async def add_comment(self, payload: ReviewCommentCreate) -> ReviewComment:
        comment = ReviewComment(
            review_task_id=payload.review_task_id,
            author=payload.author,
            body=payload.body,
            visibility=payload.visibility,
            extra_metadata=payload.metadata,
        )
        self._session.add(comment)
        await self._session.flush()
        return comment


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
