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
    Base,
    ChunkEmbedding,
    DocumentChunk,
    FailedFile,
    ReviewAction,
    ReviewComment,
    ReviewTask,
    SourceDocument,
)
from medical_audit_kb.db.repositories import KnowledgeBaseRepository, ReviewTaskRepository
from medical_audit_kb.domain.constants import (
    DocumentStatus,
    FileErrorType,
    FileQueueStatus,
    SourceCollection,
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


def test_repository_creates_package_document_chunks_and_failed_file() -> None:
    asyncio.run(_with_repository(_assert_repository_write_flow))


def test_review_task_repository_creates_task_actions_and_comments() -> None:
    asyncio.run(_with_repository(_assert_review_task_repository_flow))


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
