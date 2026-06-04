from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from medical_audit_kb.db.models import (
    AuditDataSnapshot,
    AuditFinding,
    AuditProject,
    AuditRule,
    AuditRun,
    AuditSnapshotRollback,
    AuditTask,
    ChunkEmbedding,
    DocumentChunk,
    FailedFile,
    FindingEvidenceItem,
    HisFieldMapping,
    HisSourceBatch,
    HisStagingRow,
    HisTableSchema,
    ReviewAction,
    ReviewComment,
    ReviewTask,
    RuleVersion,
    SourceDocument,
    SourcePackageVersion,
)
from medical_audit_kb.domain.schemas import (
    AuditDataSnapshotCreate,
    AuditFindingCreate,
    AuditProjectCreate,
    AuditRuleCreate,
    AuditRunCreate,
    AuditSnapshotRollbackCreate,
    AuditTaskCreate,
    ChunkEmbeddingCreate,
    DocumentChunkCreate,
    FailedFileCreate,
    FindingEvidenceItemCreate,
    HisFieldMappingCreate,
    HisSourceBatchCreate,
    HisStagingRowCreate,
    HisTableSchemaCreate,
    ReviewActionCreate,
    ReviewCommentCreate,
    ReviewTaskCreate,
    RuleVersionCreate,
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


class AuditWorkflowRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_project(self, payload: AuditProjectCreate) -> AuditProject:
        project = AuditProject(
            project_key=payload.project_key,
            name=payload.name,
            scenario_key=payload.scenario_key,
            status=payload.status,
            owner_department=payload.owner_department,
            created_by=payload.created_by,
            description=payload.description,
            extra_metadata=payload.metadata,
        )
        self._session.add(project)
        await self._session.flush()
        return project

    async def create_data_snapshot(self, payload: AuditDataSnapshotCreate) -> AuditDataSnapshot:
        snapshot = AuditDataSnapshot(
            snapshot_key=payload.snapshot_key,
            project_id=payload.project_id,
            source_batch_key=payload.source_batch_key,
            time_range=payload.time_range,
            row_counts=payload.row_counts,
            checksum=payload.checksum,
            status=payload.status,
            extra_metadata=payload.metadata,
        )
        self._session.add(snapshot)
        await self._session.flush()
        return snapshot

    async def create_snapshot_rollback(
        self, payload: AuditSnapshotRollbackCreate
    ) -> AuditSnapshotRollback:
        rollback = AuditSnapshotRollback(
            rollback_key=payload.rollback_key,
            project_id=payload.project_id,
            from_snapshot_id=payload.from_snapshot_id,
            to_snapshot_id=payload.to_snapshot_id,
            status=payload.status,
            reason=payload.reason,
            requested_by=payload.requested_by,
            impact_summary=payload.impact_summary,
            extra_metadata=payload.metadata,
        )
        self._session.add(rollback)
        await self._session.flush()
        return rollback

    async def get_snapshot_rollback_by_key(self, rollback_key: str) -> AuditSnapshotRollback | None:
        result = await self._session.execute(
            select(AuditSnapshotRollback).where(AuditSnapshotRollback.rollback_key == rollback_key)
        )
        return result.scalar_one_or_none()

    async def create_task(self, payload: AuditTaskCreate) -> AuditTask:
        task = AuditTask(
            task_key=payload.task_key,
            project_id=payload.project_id,
            snapshot_id=payload.snapshot_id,
            topic=payload.topic,
            department_scope=payload.department_scope,
            date_range=payload.date_range,
            status=payload.status,
            created_by=payload.created_by,
            extra_metadata=payload.metadata,
        )
        self._session.add(task)
        await self._session.flush()
        return task

    async def create_rule(self, payload: AuditRuleCreate) -> AuditRule:
        rule = AuditRule(
            rule_key=payload.rule_key,
            scenario_key=payload.scenario_key,
            name=payload.name,
            status=payload.status,
            owner=payload.owner,
            description=payload.description,
            extra_metadata=payload.metadata,
        )
        self._session.add(rule)
        await self._session.flush()
        return rule

    async def create_rule_version(self, payload: RuleVersionCreate) -> RuleVersion:
        rule_version = RuleVersion(
            audit_rule_id=payload.audit_rule_id,
            version_key=payload.version_key,
            rule_key=payload.rule_key,
            status=payload.status,
            logic=payload.logic,
            evidence_links=payload.evidence_links,
            effective_from=payload.effective_from,
            effective_to=payload.effective_to,
            created_by=payload.created_by,
        )
        self._session.add(rule_version)
        await self._session.flush()
        return rule_version

    async def create_run(self, payload: AuditRunCreate) -> AuditRun:
        run = AuditRun(
            run_key=payload.run_key,
            audit_task_id=payload.audit_task_id,
            snapshot_id=payload.snapshot_id,
            rule_version_key=payload.rule_version_key,
            knowledge_index_version_key=payload.knowledge_index_version_key,
            status=payload.status,
            finished_at=payload.finished_at,
            summary=payload.summary,
            extra_metadata=payload.metadata,
        )
        self._session.add(run)
        await self._session.flush()
        return run

    async def create_finding(self, payload: AuditFindingCreate) -> AuditFinding:
        finding = AuditFinding(
            finding_key=payload.finding_key,
            audit_run_id=payload.audit_run_id,
            audit_task_id=payload.audit_task_id,
            rule_version_id=payload.rule_version_id,
            snapshot_id=payload.snapshot_id,
            status=payload.status,
            finding_type=payload.finding_type,
            severity=payload.severity,
            source_record_locator=payload.source_record_locator,
            calculation_trace=payload.calculation_trace,
            review_status=payload.review_status,
            review_task_id=payload.review_task_id,
            extra_metadata=payload.metadata,
        )
        self._session.add(finding)
        await self._session.flush()
        return finding

    async def add_finding_evidence_item(
        self, payload: FindingEvidenceItemCreate
    ) -> FindingEvidenceItem:
        evidence_item = FindingEvidenceItem(
            audit_finding_id=payload.audit_finding_id,
            evidence_type=payload.evidence_type,
            chunk_id=payload.chunk_id,
            source_package_version_key=payload.source_package_version_key,
            index_version_key=payload.index_version_key,
            citation_id=payload.citation_id,
            locator=payload.locator,
            snippet=payload.snippet,
            extra_metadata=payload.metadata,
        )
        self._session.add(evidence_item)
        await self._session.flush()
        return evidence_item

    async def get_finding_by_key(self, finding_key: str) -> AuditFinding | None:
        result = await self._session.execute(
            select(AuditFinding).where(AuditFinding.finding_key == finding_key)
        )
        return result.scalar_one_or_none()

    async def list_findings_for_run(self, audit_run_id: UUID) -> list[AuditFinding]:
        result = await self._session.execute(
            select(AuditFinding)
            .where(AuditFinding.audit_run_id == audit_run_id)
            .order_by(AuditFinding.created_at.asc())
        )
        return list(result.scalars().all())


class HisIngestionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_source_batch(self, payload: HisSourceBatchCreate) -> HisSourceBatch:
        source_batch = HisSourceBatch(
            batch_key=payload.batch_key,
            project_id=payload.project_id,
            hospital_code=payload.hospital_code,
            scenario_key=payload.scenario_key,
            source_type=payload.source_type,
            exported_at=payload.exported_at,
            file_manifest=payload.file_manifest,
            row_counts=payload.row_counts,
            checksum=payload.checksum,
            status=payload.status,
            extra_metadata=payload.metadata,
        )
        self._session.add(source_batch)
        await self._session.flush()
        return source_batch

    async def create_table_schema(self, payload: HisTableSchemaCreate) -> HisTableSchema:
        table_schema = HisTableSchema(
            schema_key=payload.schema_key,
            source_batch_id=payload.source_batch_id,
            table_name=payload.table_name,
            business_domain=payload.business_domain,
            ddl_text=payload.ddl_text,
            ddl_hash=payload.ddl_hash,
            field_dictionary=payload.field_dictionary,
            primary_key_fields=payload.primary_key_fields,
            time_fields=payload.time_fields,
            row_count=payload.row_count,
            status=payload.status,
            extra_metadata=payload.metadata,
        )
        self._session.add(table_schema)
        await self._session.flush()
        return table_schema

    async def add_field_mapping(self, payload: HisFieldMappingCreate) -> HisFieldMapping:
        field_mapping = HisFieldMapping(
            mapping_key=payload.mapping_key,
            table_schema_id=payload.table_schema_id,
            source_field=payload.source_field,
            target_domain=payload.target_domain,
            target_field=payload.target_field,
            source_data_type=payload.source_data_type,
            target_data_type=payload.target_data_type,
            transform_rule=payload.transform_rule,
            is_required=payload.is_required,
            nullable=payload.nullable,
            deidentification_rule=payload.deidentification_rule,
            status=payload.status,
            extra_metadata=payload.metadata,
        )
        self._session.add(field_mapping)
        await self._session.flush()
        return field_mapping

    async def add_staging_rows(
        self,
        payloads: Sequence[HisStagingRowCreate],
    ) -> list[HisStagingRow]:
        staging_rows = [
            HisStagingRow(
                source_batch_id=payload.source_batch_id,
                table_schema_id=payload.table_schema_id,
                table_name=payload.table_name,
                row_number=payload.row_number,
                row_data=payload.row_data,
                row_hash=payload.row_hash,
                status=payload.status,
                validation_errors=payload.validation_errors,
                extra_metadata=payload.metadata,
            )
            for payload in payloads
        ]
        self._session.add_all(staging_rows)
        await self._session.flush()
        return staging_rows

    async def list_staging_rows_for_batch(self, batch_key: str) -> list[HisStagingRow]:
        result = await self._session.execute(
            select(HisStagingRow)
            .join(HisSourceBatch)
            .where(HisSourceBatch.batch_key == batch_key)
            .order_by(HisStagingRow.table_name.asc(), HisStagingRow.row_number.asc())
        )
        return list(result.scalars().all())

    async def list_field_mappings_for_batch(self, batch_key: str) -> list[HisFieldMapping]:
        result = await self._session.execute(
            select(HisFieldMapping)
            .join(HisTableSchema)
            .join(HisSourceBatch)
            .where(HisSourceBatch.batch_key == batch_key)
            .order_by(HisTableSchema.table_name.asc(), HisFieldMapping.target_field.asc())
        )
        return list(result.scalars().all())


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
