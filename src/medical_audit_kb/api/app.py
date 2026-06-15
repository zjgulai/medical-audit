from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast
from uuid import UUID

from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from medical_audit_kb import __version__
from medical_audit_kb.api.agent_store import AgentStore, SqlAlchemyAgentStore
from medical_audit_kb.api.analytics_upload_store import (
    AnalyticsUploadStore,
    SqlAlchemyAnalyticsUploadStore,
)
from medical_audit_kb.api.audit_finding_store import SqlAlchemyAuditFindingStore
from medical_audit_kb.api.audit_log_store import AuditLogStore, SqlAlchemyAuditLogStore
from medical_audit_kb.api.document_upload_store import (
    DocumentUploadStore,
    SqlAlchemyDocumentUploadStore,
)
from medical_audit_kb.api.project_member_store import (
    ProjectMemberStore,
    SqlAlchemyProjectMemberStore,
)
from medical_audit_kb.api.query_history_store import QueryHistoryStore, SqlAlchemyQueryHistoryStore
from medical_audit_kb.api.review_task_store import ReviewTaskStore, SqlAlchemyReviewTaskStore
from medical_audit_kb.core.config import KnowledgeQuerySettings, load_settings
from medical_audit_kb.generation.answer_builder import AnswerGenerationProvider
from medical_audit_kb.generation.answer_providers import (
    AnthropicAnswerGenerationProvider,
    OpenAICompatibleAnswerGenerationProvider,
)
from medical_audit_kb.indexing.index_jobs import ManifestIndexSnapshot
from medical_audit_kb.ingestion.pipeline import KnowledgeIndexPipeline, PipelineRunResult
from medical_audit_kb.preview.resolver import PreviewResolver
from medical_audit_kb.retrieval.hybrid_search import HybridSearchEngine


@dataclass(frozen=True, slots=True)
class PreviewReference:
    locator: dict[str, object]
    citation_text: str | None = None


@dataclass(slots=True)
class ApiState:
    settings: KnowledgeQuerySettings
    index_pipeline: KnowledgeIndexPipeline
    preview_resolver: PreviewResolver
    search_engine: HybridSearchEngine | None = None
    search_backend: str = "none"
    search_backend_details: dict[str, object] = field(default_factory=dict)
    current_snapshot: ManifestIndexSnapshot | None = None
    index_versions: list[dict[str, object]] = field(default_factory=list)
    index_jobs: list[dict[str, object]] = field(default_factory=list)
    failed_files: list[dict[str, object]] = field(default_factory=list)
    pending_files: list[dict[str, object]] = field(default_factory=list)
    evaluation_runs: list[dict[str, object]] = field(default_factory=list)
    query_logs: list[dict[str, object]] = field(default_factory=list)
    operation_logs: list[dict[str, object]] = field(default_factory=list)
    preview_references: dict[UUID, PreviewReference] = field(default_factory=dict)
    review_task_store: ReviewTaskStore | None = None
    audit_finding_store: SqlAlchemyAuditFindingStore | None = None
    audit_log_store: AuditLogStore | None = None
    agent_store: AgentStore | None = None
    project_member_store: ProjectMemberStore | None = None
    analytics_upload_store: AnalyticsUploadStore | None = None
    document_upload_store: DocumentUploadStore | None = None
    query_history_store: QueryHistoryStore | None = None
    answer_generation_provider: AnswerGenerationProvider | None = None

    @classmethod
    def from_settings(cls, settings: KnowledgeQuerySettings) -> ApiState:
        return cls(
            settings=settings,
            index_pipeline=KnowledgeIndexPipeline(),
            preview_resolver=PreviewResolver(source_root=settings.data_root),
            review_task_store=SqlAlchemyReviewTaskStore(settings.database_url),
            audit_finding_store=SqlAlchemyAuditFindingStore(settings.database_url),
            audit_log_store=SqlAlchemyAuditLogStore(settings.database_url),
            agent_store=SqlAlchemyAgentStore(settings.database_url),
            project_member_store=SqlAlchemyProjectMemberStore(settings.database_url),
            analytics_upload_store=SqlAlchemyAnalyticsUploadStore(
                settings.database_url,
                upload_root=settings.analytics_upload_root
                or settings.index_root / "analytics-uploads",
            ),
            document_upload_store=SqlAlchemyDocumentUploadStore(
                settings.database_url,
                upload_root=settings.document_upload_root
                or settings.index_root / "document-uploads",
            ),
            query_history_store=SqlAlchemyQueryHistoryStore(settings.database_url),
            answer_generation_provider=answer_generation_provider_from_settings(settings),
        )

    @property
    def source_root(self) -> Path:
        return self.settings.data_root


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    version: str
    data_root: str


def create_app(api_state: ApiState | None = None) -> FastAPI:
    state = api_state or ApiState.from_settings(load_settings())
    app = FastAPI(title="Medical Audit Knowledge Query API", version=__version__)
    app.state.api_state = state
    app.mount(
        "/static",
        StaticFiles(directory=Path(__file__).parent / "static"),
        name="static",
    )

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            version=__version__,
            data_root=str(state.source_root),
        )

    @app.api_route("/favicon.ico", methods=["GET", "HEAD"], include_in_schema=False)
    def favicon() -> Response:
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
            '<rect width="64" height="64" rx="16" fill="#0B1F33"/>'
            '<path d="M18 17h28v6H18zM18 29h28v6H18zM18 41h18v6H18z" fill="#F5F7FA"/>'
            '<path d="M42 39l4 4 8-11" fill="none" stroke="#0A84FF" stroke-width="5"'
            ' stroke-linecap="round" stroke-linejoin="round"/>'
            "</svg>"
        )
        return Response(content=svg, media_type="image/svg+xml")

    from medical_audit_kb.api.routes_agents import router as agents_router
    from medical_audit_kb.api.routes_analytics import router as analytics_router
    from medical_audit_kb.api.routes_documents import router as documents_router
    from medical_audit_kb.api.routes_index import router as index_router
    from medical_audit_kb.api.routes_pages import router as pages_router
    from medical_audit_kb.api.routes_preview import router as preview_router
    from medical_audit_kb.api.routes_projects import router as projects_router
    from medical_audit_kb.api.routes_query import router as query_router

    app.include_router(pages_router)
    app.include_router(query_router)
    app.include_router(agents_router)
    app.include_router(analytics_router)
    app.include_router(documents_router)
    app.include_router(projects_router)
    app.include_router(index_router)
    app.include_router(preview_router)
    return app


def answer_generation_provider_from_settings(
    settings: KnowledgeQuerySettings,
) -> AnswerGenerationProvider | None:
    provider = os.getenv("MEDICAL_AUDIT_KB_ANSWER_PROVIDER", "fallback").strip().lower()
    if provider in {"", "fallback", "none"}:
        return None

    api_key_env = os.getenv(
        "MEDICAL_AUDIT_KB_ANSWER_API_KEY_ENV",
        settings.model_provider.api_key_env,
    ).strip()
    model_name = os.getenv(
        "MEDICAL_AUDIT_KB_ANSWER_MODEL",
        settings.model_provider.chat_model,
    ).strip()
    max_output_tokens = int(os.getenv("MEDICAL_AUDIT_KB_ANSWER_MAX_OUTPUT_TOKENS", "600"))
    temperature = float(os.getenv("MEDICAL_AUDIT_KB_ANSWER_TEMPERATURE", "0"))

    if provider == "anthropic":
        return AnthropicAnswerGenerationProvider.from_env(
            api_key_env=api_key_env,
            model_name=model_name,
            base_url=os.getenv("MEDICAL_AUDIT_KB_ANSWER_BASE_URL", "https://api.anthropic.com"),
            max_output_tokens=max_output_tokens,
            temperature=temperature,
        )
    if provider == "openai":
        return OpenAICompatibleAnswerGenerationProvider.from_env(
            api_key_env=api_key_env,
            model_name=model_name,
            base_url=os.getenv("MEDICAL_AUDIT_KB_ANSWER_BASE_URL", "https://api.openai.com/v1"),
            max_output_tokens=max_output_tokens,
            temperature=temperature,
        )

    raise ValueError(f"unsupported answer provider: {provider}")


def get_api_state(request: Request) -> ApiState:
    return cast(ApiState, request.app.state.api_state)


def record_index_run(state: ApiState, run_result: PipelineRunResult) -> None:
    summary = run_result.summary.to_dict()
    state.current_snapshot = run_result.snapshot
    state.index_versions.append(
        {
            "index_version_key": run_result.summary.index_version_key,
            "source_package_version_key": run_result.summary.source_package_version_key,
            "status": "active",
            "chunk_count": run_result.summary.chunk_count,
            "document_count": run_result.summary.indexed_file_count,
        }
    )
    state.index_jobs.append(
        {
            "job_id": run_result.summary.index_version_key,
            "job_type": run_result.summary.job_type.value,
            "status": "succeeded",
            "summary": summary,
        }
    )
    state.failed_files = [
        {
            "relative_path": item.relative_path,
            "error_type": item.error_type.value,
            "error_summary": item.error_summary,
        }
        for item in run_result.failed_files
    ]
    state.pending_files = [
        {
            "relative_path": item.relative_path,
            "error_type": item.error_type.value,
            "error_summary": item.error_summary,
        }
        for item in run_result.pending_files
    ]
    record_operation(
        state,
        "index",
        {
            "job_type": run_result.summary.job_type.value,
            "index_version_key": run_result.summary.index_version_key,
            "status": "succeeded",
        },
    )


def record_operation(
    state: ApiState,
    action: str,
    payload: dict[str, object],
) -> None:
    state.operation_logs.append({"action": action, "payload": payload})
    if state.audit_log_store is not None:
        state.audit_log_store.add_event(action, payload)


class PermissionHeaders(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_identifier: str = Field(default="anonymous")
    role: str = Field(default="auditor")
