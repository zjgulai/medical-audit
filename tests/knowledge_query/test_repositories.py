import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from medical_audit_kb.db.models import (
    AuditDataSnapshot,
    AuditFinding,
    AuditLogEvent,
    AuditProject,
    AuditRule,
    AuditRun,
    AuditTask,
    Base,
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
)
from medical_audit_kb.db.repositories import (
    AuditLogRepository,
    AuditWorkflowRepository,
    HisIngestionRepository,
    KnowledgeBaseRepository,
    ReviewTaskRepository,
)
from medical_audit_kb.domain.constants import (
    DocumentStatus,
    FileErrorType,
    FileQueueStatus,
    SourceCollection,
)
from medical_audit_kb.domain.schemas import (
    AuditDataSnapshotCreate,
    AuditFindingCreate,
    AuditLogEventCreate,
    AuditProjectCreate,
    AuditRuleCreate,
    AuditRunCreate,
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


def test_repository_creates_package_document_chunks_and_failed_file() -> None:
    asyncio.run(_with_repository(_assert_repository_write_flow))


def test_review_task_repository_creates_task_actions_and_comments() -> None:
    asyncio.run(_with_repository(_assert_review_task_repository_flow))


def test_audit_workflow_repository_creates_traceable_task_run_findings() -> None:
    asyncio.run(_with_repository(_assert_audit_workflow_repository_flow))


def test_his_ingestion_repository_creates_batch_schema_and_field_mappings() -> None:
    asyncio.run(_with_repository(_assert_his_ingestion_repository_flow))


def test_audit_log_repository_creates_and_filters_events() -> None:
    asyncio.run(_with_repository(_assert_audit_log_repository_flow))


async def _with_repository(
    scenario: Callable[[KnowledgeBaseRepository, AsyncSession], Awaitable[None]],
) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        await _create_schema(engine)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session, session.begin():
            await scenario(KnowledgeBaseRepository(session), session)
    finally:
        await engine.dispose()


async def _create_schema(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def _assert_repository_write_flow(
    repository: KnowledgeBaseRepository,
    session: AsyncSession,
) -> None:
    package = await repository.create_source_package_version(
        SourcePackageVersionCreate(
            version_key="20260531-initial",
            source_root_path=Path("data/医保审核前期资料"),
            description="initial audit package",
            metadata={"source": "unit-test"},
        )
    )

    document = await repository.upsert_source_document(
        SourceDocumentUpsert(
            source_package_version_id=package.id,
            source_collection=SourceCollection.MEDICAL_INSURANCE_LAWS,
            relative_path="全量法律/医保政策.md",
            absolute_path="/repo/data/医保审核前期资料/全量法律/医保政策.md",
            file_name="医保政策.md",
            file_ext=".md",
            media_type="text/markdown",
            sha256="a" * 64,
            size_bytes=128,
            status=DocumentStatus.INDEX_CANDIDATE,
            metadata={"title": "医保政策"},
        )
    )

    updated_document = await repository.upsert_source_document(
        SourceDocumentUpsert(
            source_package_version_id=package.id,
            source_collection=SourceCollection.MEDICAL_INSURANCE_LAWS,
            relative_path="全量法律/医保政策.md",
            absolute_path="/repo/data/医保审核前期资料/全量法律/医保政策.md",
            file_name="医保政策.md",
            file_ext=".md",
            media_type="text/markdown",
            sha256="b" * 64,
            size_bytes=256,
            status=DocumentStatus.INDEXED,
            metadata={"title": "医保政策", "updated": True},
        )
    )

    chunks = await repository.add_document_chunks(
        [
            DocumentChunkCreate(
                source_document_id=document.id,
                chunk_index=0,
                text="第一条 医保基金使用应符合规定。",
                title_path=["医保政策"],
                article_number="第一条",
                line_start=1,
                line_end=1,
                token_count=16,
                locator={"type": "line", "line_start": 1, "line_end": 1},
            ),
            DocumentChunkCreate(
                source_document_id=document.id,
                chunk_index=1,
                text="第二条 医疗机构应保留审核依据。",
                title_path=["医保政策"],
                article_number="第二条",
                line_start=2,
                line_end=2,
                token_count=18,
                locator={"type": "line", "line_start": 2, "line_end": 2},
            ),
        ]
    )

    failed_file = await repository.add_failed_file(
        FailedFileCreate(
            source_package_version_id=package.id,
            source_document_id=document.id,
            relative_path="风险负面清单/scan.png",
            error_type=FileErrorType.UNSUPPORTED_TYPE,
            error_summary="PNG enters pending OCR queue in V1.",
            status=FileQueueStatus.OPEN,
        )
    )
    embedding = await repository.upsert_chunk_embedding(
        ChunkEmbeddingCreate(
            chunk_id=chunks[0].id,
            provider="fake",
            model_name="deterministic-token-hashing",
            provider_version="v1",
            dimension=3,
            embedding=[0.1, 0.2, 0.3],
        )
    )
    updated_embedding = await repository.upsert_chunk_embedding(
        ChunkEmbeddingCreate(
            chunk_id=chunks[0].id,
            provider="fake",
            model_name="deterministic-token-hashing",
            provider_version="v1",
            dimension=3,
            embedding=[0.3, 0.2, 0.1],
        )
    )

    assert updated_document.id == document.id
    assert updated_document.sha256 == "b" * 64
    assert len(chunks) == 2
    assert failed_file.retry_count == 0
    assert updated_embedding.id == embedding.id

    stored_document = (
        await session.execute(select(SourceDocument).where(SourceDocument.id == document.id))
    ).scalar_one()
    stored_chunks = (
        (
            await session.execute(
                select(DocumentChunk)
                .where(DocumentChunk.source_document_id == document.id)
                .order_by(DocumentChunk.chunk_index)
            )
        )
        .scalars()
        .all()
    )
    stored_failure = (
        await session.execute(select(FailedFile).where(FailedFile.id == failed_file.id))
    ).scalar_one()
    stored_embedding = (
        await session.execute(select(ChunkEmbedding).where(ChunkEmbedding.id == embedding.id))
    ).scalar_one()

    assert stored_document.source_collection == SourceCollection.MEDICAL_INSURANCE_LAWS.value
    assert stored_document.status == DocumentStatus.INDEXED.value
    assert stored_document.extra_metadata["updated"] is True
    assert [chunk.article_number for chunk in stored_chunks] == ["第一条", "第二条"]
    assert stored_failure.error_type == FileErrorType.UNSUPPORTED_TYPE.value
    assert stored_failure.status == FileQueueStatus.OPEN.value
    assert stored_embedding.provider == "fake"
    assert stored_embedding.model_name == "deterministic-token-hashing"
    assert stored_embedding.provider_version == "v1"
    assert stored_embedding.dimension == 3
    assert stored_embedding.embedding == [0.3, 0.2, 0.1]


async def _assert_his_ingestion_repository_flow(
    _: KnowledgeBaseRepository,
    session: AsyncSession,
) -> None:
    audit_repository = AuditWorkflowRepository(session)
    his_repository = HisIngestionRepository(session)
    project = await audit_repository.create_project(
        AuditProjectCreate(
            project_key="audit-project-his-0001",
            name="收费合规专项审计",
            scenario_key="charging-compliance",
            status="draft",
            owner_department="审计科",
            created_by="unit-test",
        )
    )
    source_batch = await his_repository.create_source_batch(
        HisSourceBatchCreate(
            batch_key="his-batch-0001",
            project_id=project.id,
            hospital_code="hospital-a",
            scenario_key="charging-compliance",
            source_type="offline-export",
            file_manifest={"files": ["charge_detail.csv"]},
            row_counts={"charge_detail": 2},
            checksum="sha256:demo",
            status="received",
        )
    )
    table_schema = await his_repository.create_table_schema(
        HisTableSchemaCreate(
            schema_key="his-schema-charge-detail-0001",
            source_batch_id=source_batch.id,
            table_name="T_HIS_CHARGE_DETAIL",
            business_domain="charge_detail",
            ddl_text="CREATE TABLE T_HIS_CHARGE_DETAIL (CHARGE_ID TEXT NOT NULL);",
            ddl_hash="sha256:charge-detail",
            field_dictionary={"CHARGE_ID": {"description": "charge row id"}},
            primary_key_fields=["CHARGE_ID"],
            time_fields=["CHARGED_AT"],
            row_count=2,
            status="mapped",
        )
    )
    charge_id_mapping = await his_repository.add_field_mapping(
        HisFieldMappingCreate(
            mapping_key="his-map-charge-id-0001",
            table_schema_id=table_schema.id,
            source_field="CHARGE_ID",
            target_domain="charge_detail",
            target_field="charge_id",
            source_data_type="TEXT",
            target_data_type="string",
            status="active",
        )
    )
    amount_mapping = await his_repository.add_field_mapping(
        HisFieldMappingCreate(
            mapping_key="his-map-amount-0001",
            table_schema_id=table_schema.id,
            source_field="AMOUNT",
            target_domain="charge_detail",
            target_field="amount",
            source_data_type="NUMERIC",
            target_data_type="decimal",
            nullable=True,
            status="active",
        )
    )
    staging_rows = await his_repository.add_staging_rows(
        [
            HisStagingRowCreate(
                source_batch_id=source_batch.id,
                table_schema_id=table_schema.id,
                table_name="T_HIS_CHARGE_DETAIL",
                row_number=1,
                row_data={"CHARGE_ID": "C001", "AMOUNT": "100.00"},
                row_hash="sha256:row-1",
                status="staged",
                metadata={"source": "unit-test"},
            ),
            HisStagingRowCreate(
                source_batch_id=source_batch.id,
                table_schema_id=table_schema.id,
                table_name="T_HIS_CHARGE_DETAIL",
                row_number=2,
                row_data={"CHARGE_ID": "C002", "AMOUNT": "120.00"},
                row_hash="sha256:row-2",
                status="staged",
                metadata={"source": "unit-test"},
            ),
        ]
    )

    stored_batch = (
        await session.execute(select(HisSourceBatch).where(HisSourceBatch.id == source_batch.id))
    ).scalar_one()
    stored_schema = (
        await session.execute(select(HisTableSchema).where(HisTableSchema.id == table_schema.id))
    ).scalar_one()
    stored_mappings = await his_repository.list_field_mappings_for_batch("his-batch-0001")
    stored_amount_mapping = (
        await session.execute(
            select(HisFieldMapping).where(HisFieldMapping.id == amount_mapping.id)
        )
    ).scalar_one()
    stored_staging_rows = await his_repository.list_staging_rows_for_batch("his-batch-0001")
    stored_first_staging_row = (
        await session.execute(select(HisStagingRow).where(HisStagingRow.id == staging_rows[0].id))
    ).scalar_one()

    assert stored_batch.project_id == project.id
    assert stored_batch.file_manifest == {"files": ["charge_detail.csv"]}
    assert stored_schema.primary_key_fields == ["CHARGE_ID"]
    assert [mapping.id for mapping in stored_mappings] == [amount_mapping.id, charge_id_mapping.id]
    assert stored_amount_mapping.nullable is True
    assert [row.row_number for row in stored_staging_rows] == [1, 2]
    assert stored_first_staging_row.row_data == {"CHARGE_ID": "C001", "AMOUNT": "100.00"}
    assert stored_first_staging_row.extra_metadata == {"source": "unit-test"}


async def _assert_audit_log_repository_flow(
    _: KnowledgeBaseRepository,
    session: AsyncSession,
) -> None:
    repository = AuditLogRepository(session)
    first_event = await repository.create_event(
        AuditLogEventCreate(
            action="review-task-readonly-write-blocked",
            entity_type="review-task",
            entity_id="review-task-0001",
            user_identifier="auditor-001",
            role="auditor",
            status_code=409,
            endpoint="/pages/review-tasks/review-task-0001/status",
            reason="review task is closed and read-only",
            payload={
                "attempted_action": "review-task-status-update",
                "task_status": "closed",
            },
            metadata={"source": "unit-test"},
        )
    )
    second_event = await repository.create_event(
        AuditLogEventCreate(
            action="review-task-export",
            entity_type="review-task",
            entity_id="review-task-0001",
            user_identifier="auditor-001",
            role="auditor",
            status_code=200,
            endpoint="/review-tasks/review-task-0001/export",
            payload={"format": "json"},
        )
    )
    other_event = await repository.create_event(
        AuditLogEventCreate(
            action="page-query",
            entity_type="query",
            entity_id="query-log-0001",
            user_identifier="auditor-002",
            role="auditor",
            status_code=200,
            endpoint="/pages/query",
            payload={"question": "医保基金审核依据"},
        )
    )

    review_task_events = await repository.list_events(
        entity_type="review-task",
        entity_id="review-task-0001",
    )
    blocked_events = await repository.list_events(
        action="review-task-readonly-write-blocked",
        entity_type="review-task",
        entity_id="review-task-0001",
    )

    assert first_event.action == "review-task-readonly-write-blocked"
    assert first_event.reason == "review task is closed and read-only"
    assert first_event.extra_metadata["source"] == "unit-test"
    assert [event.id for event in review_task_events] == [second_event.id, first_event.id]
    assert [event.id for event in blocked_events] == [first_event.id]
    assert other_event.entity_type == "query"

    stored_event = (
        await session.execute(select(AuditLogEvent).where(AuditLogEvent.id == first_event.id))
    ).scalar_one()
    assert stored_event.payload["attempted_action"] == "review-task-status-update"
    assert stored_event.status_code == 409
    assert stored_event.endpoint == "/pages/review-tasks/review-task-0001/status"


async def _assert_review_task_repository_flow(
    _: KnowledgeBaseRepository,
    session: AsyncSession,
) -> None:
    repository = ReviewTaskRepository(session)
    task = await repository.create_task(
        ReviewTaskCreate(
            external_task_id="review-task-0001",
            question="医保基金审核依据",
            status="pending-review",
            status_label="待复核",
            citation_count=3,
            review_gate="可进入人工复核",
            confidence_label="高",
            fallback_label="检索直出",
            reviewer_note="初始复核意见",
            conclusion="初始复核结论",
            created_by="auditor-001",
            assigned_to="chief-auditor",
            source="chat-dossier",
            dossier={
                "format": "audit-dossier-v1",
                "question": "医保基金审核依据",
                "citations": [{"chunk_id": "11111111-1111-4111-8111-111111111111"}],
            },
        )
    )
    action = await repository.add_action(
        ReviewActionCreate(
            review_task_id=task.id,
            action_type="status-change",
            from_status="pending-review",
            to_status="needs-evidence",
            actor="auditor-001",
            note="引用已覆盖规则依据，仍需补 HIS 原始凭证。",
            metadata={"source": "unit-test"},
        )
    )
    comment = await repository.add_comment(
        ReviewCommentCreate(
            review_task_id=task.id,
            author="chief-auditor",
            body="补充 HIS 原始凭证后再进入正式报告。",
            visibility="internal",
            metadata={"severity": "p1"},
        )
    )

    loaded_task = await repository.get_task(task.id)
    listed_tasks = await repository.list_tasks()

    assert task.external_task_id == "review-task-0001"
    assert task.status == "pending-review"
    assert task.created_by == "auditor-001"
    assert task.reviewer_note == "初始复核意见"
    assert task.conclusion == "初始复核结论"
    assert action.to_status == "needs-evidence"
    assert comment.visibility == "internal"
    assert loaded_task is not None
    assert loaded_task.id == task.id
    assert [item.id for item in listed_tasks] == [task.id]

    stored_task = (
        await session.execute(select(ReviewTask).where(ReviewTask.id == task.id))
    ).scalar_one()
    stored_action = (
        await session.execute(select(ReviewAction).where(ReviewAction.id == action.id))
    ).scalar_one()
    stored_comment = (
        await session.execute(select(ReviewComment).where(ReviewComment.id == comment.id))
    ).scalar_one()

    assert stored_task.dossier["format"] == "audit-dossier-v1"
    assert stored_task.citation_count == 3
    assert stored_task.reviewer_note == "初始复核意见"
    assert stored_task.conclusion == "初始复核结论"
    assert stored_task.source == "chat-dossier"
    assert stored_action.actor == "auditor-001"
    assert stored_action.extra_metadata["source"] == "unit-test"
    assert stored_comment.body == "补充 HIS 原始凭证后再进入正式报告。"
    assert stored_comment.extra_metadata["severity"] == "p1"


async def _assert_audit_workflow_repository_flow(
    _: KnowledgeBaseRepository,
    session: AsyncSession,
) -> None:
    repository = AuditWorkflowRepository(session)

    project = await repository.create_project(
        AuditProjectCreate(
            project_key="audit-project-0001",
            name="收费合规专项",
            scenario_key="charging-compliance",
            status="draft",
            owner_department="审计科",
            created_by="auditor-001",
            description="重复收费与目录限制核验。",
            metadata={"hospital": "fixture-hospital"},
        )
    )
    snapshot = await repository.create_data_snapshot(
        AuditDataSnapshotCreate(
            snapshot_key="snapshot-20260604-001",
            project_id=project.id,
            source_batch_key="his-batch-20260604",
            time_range={"from": "2025-01-01", "to": "2025-12-31"},
            row_counts={"charge_detail": 3},
            checksum="sha256:fixture",
            status="validated",
            metadata={"deidentified": True},
        )
    )
    task = await repository.create_task(
        AuditTaskCreate(
            task_key="audit-task-0001",
            project_id=project.id,
            snapshot_id=snapshot.id,
            topic="重复收费核验",
            department_scope={"department_codes": ["D001"]},
            date_range={"from": "2025-01-01", "to": "2025-01-31"},
            status="ready",
            created_by="auditor-001",
            metadata={"scenario": "charge-duplicate"},
        )
    )
    rule = await repository.create_rule(
        AuditRuleCreate(
            rule_key="charge-rule-001",
            scenario_key="charging-compliance",
            name="同日同项目重复收费",
            status="active",
            owner="audit-rule-team",
            description="同一就诊、同日、同项目重复收费疑点识别。",
            metadata={"risk_domain": "charging"},
        )
    )
    rule_version = await repository.create_rule_version(
        RuleVersionCreate(
            audit_rule_id=rule.id,
            version_key="charge-rule-001@v1",
            rule_key=rule.rule_key,
            status="active",
            logic={
                "type": "group-by",
                "keys": ["visit_id", "charge_item_code", "charge_date"],
                "condition": "count > 1",
            },
            evidence_links={"knowledge_topics": ["重复收费"]},
            created_by="rule-designer-001",
        )
    )
    run = await repository.create_run(
        AuditRunCreate(
            run_key="audit-run-0001",
            audit_task_id=task.id,
            snapshot_id=snapshot.id,
            rule_version_key=rule_version.version_key,
            knowledge_index_version_key="full-rebuild-20260603085815",
            status="succeeded",
            summary={"finding_count": 1},
            metadata={"executor": "unit-test"},
        )
    )
    finding = await repository.create_finding(
        AuditFindingCreate(
            finding_key="finding-0001",
            audit_run_id=run.id,
            audit_task_id=task.id,
            rule_version_id=rule_version.id,
            snapshot_id=snapshot.id,
            status="open",
            finding_type="duplicate-charge",
            severity="medium",
            source_record_locator={"table": "charge_detail", "primary_key": "CD0001"},
            calculation_trace={
                "group_keys": {
                    "visit_id": "V001",
                    "charge_item_code": "P001",
                    "charge_date": "2025-01-03",
                },
                "matched_rows": ["CD0001", "CD0002"],
            },
            review_status="pending-review",
            metadata={"amount": 80.0},
        )
    )
    evidence = await repository.add_finding_evidence_item(
        FindingEvidenceItemCreate(
            audit_finding_id=finding.id,
            evidence_type="knowledge-citation",
            source_package_version_key="20260603-production",
            index_version_key="full-rebuild-20260603085815",
            citation_id="citation-001",
            locator={"article_number": "第十七条"},
            snippet="医疗机构应按照项目内涵和计价单位收费。",
            metadata={"confidence": "high"},
        )
    )

    loaded_finding = await repository.get_finding_by_key("finding-0001")
    run_findings = await repository.list_findings_for_run(run.id)

    assert project.project_key == "audit-project-0001"
    assert snapshot.project_id == project.id
    assert task.snapshot_id == snapshot.id
    assert rule_version.audit_rule_id == rule.id
    assert run.audit_task_id == task.id
    assert run.snapshot_id == snapshot.id
    assert finding.rule_version_id == rule_version.id
    assert evidence.audit_finding_id == finding.id
    assert loaded_finding is not None
    assert loaded_finding.id == finding.id
    assert [item.id for item in run_findings] == [finding.id]

    stored_project = (
        await session.execute(select(AuditProject).where(AuditProject.id == project.id))
    ).scalar_one()
    stored_snapshot = (
        await session.execute(select(AuditDataSnapshot).where(AuditDataSnapshot.id == snapshot.id))
    ).scalar_one()
    stored_task = (
        await session.execute(select(AuditTask).where(AuditTask.id == task.id))
    ).scalar_one()
    stored_run = (await session.execute(select(AuditRun).where(AuditRun.id == run.id))).scalar_one()
    stored_rule = (
        await session.execute(select(AuditRule).where(AuditRule.id == rule.id))
    ).scalar_one()
    stored_rule_version = (
        await session.execute(select(RuleVersion).where(RuleVersion.id == rule_version.id))
    ).scalar_one()
    stored_finding = (
        await session.execute(select(AuditFinding).where(AuditFinding.id == finding.id))
    ).scalar_one()
    stored_evidence = (
        await session.execute(
            select(FindingEvidenceItem).where(FindingEvidenceItem.id == evidence.id)
        )
    ).scalar_one()

    assert stored_project.extra_metadata["hospital"] == "fixture-hospital"
    assert stored_snapshot.row_counts["charge_detail"] == 3
    assert stored_task.department_scope["department_codes"] == ["D001"]
    assert stored_run.rule_version_key == "charge-rule-001@v1"
    assert stored_run.knowledge_index_version_key == "full-rebuild-20260603085815"
    assert stored_rule.scenario_key == "charging-compliance"
    assert stored_rule_version.logic["condition"] == "count > 1"
    assert stored_finding.calculation_trace["matched_rows"] == ["CD0001", "CD0002"]
    assert stored_finding.review_status == "pending-review"
    assert stored_evidence.evidence_type == "knowledge-citation"
    assert stored_evidence.snippet == "医疗机构应按照项目内涵和计价单位收费。"
