from __future__ import annotations

import os
import urllib.parse
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, cast
from uuid import UUID

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.responses import Response as StarletteResponse

from medical_audit_kb import __version__
from medical_audit_kb.api.agent_store import AgentStore, SqlAlchemyAgentStore
from medical_audit_kb.api.analytics_upload_store import (
    AnalyticsUploadStore,
    SqlAlchemyAnalyticsUploadStore,
)
from medical_audit_kb.api.audit_finding_store import SqlAlchemyAuditFindingStore
from medical_audit_kb.api.audit_log_store import AuditLogStore, SqlAlchemyAuditLogStore
from medical_audit_kb.api.auth import normalize_tenant_id, resolve_authenticated_user
from medical_audit_kb.api.auth_user_store import AuthUserStore, SqlAlchemyAuthUserStore
from medical_audit_kb.api.document_upload_ingestion import (
    SqlAlchemyDocumentUploadIndexer,
    document_upload_indexer_from_settings,
)
from medical_audit_kb.api.document_upload_store import (
    DocumentUploadStore,
    SqlAlchemyDocumentUploadStore,
    document_object_storage_from_settings,
    document_storage_objects_schema_ready,
    tencent_cos_put_object_client_from_settings,
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
    document_upload_indexer: SqlAlchemyDocumentUploadIndexer | None = None
    query_history_store: QueryHistoryStore | None = None
    auth_user_store: AuthUserStore | None = None
    answer_generation_provider: AnswerGenerationProvider | None = None

    @classmethod
    def from_settings(cls, settings: KnowledgeQuerySettings) -> ApiState:
        document_upload_root = settings.document_upload_root or (
            settings.index_root / "document-uploads"
        )
        tencent_cos_client = tencent_cos_put_object_client_from_settings(
            settings.document_storage
        )
        document_object_storage = document_object_storage_from_settings(
            settings.document_storage,
            upload_root=document_upload_root,
            tencent_cos_client=tencent_cos_client,
        )
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
                upload_root=document_upload_root,
                object_storage=document_object_storage,
                record_storage_objects=document_storage_objects_schema_ready(
                    settings.database_url
                ),
            ),
            document_upload_indexer=document_upload_indexer_from_settings(
                database_url=settings.database_url,
                upload_root=document_upload_root,
                settings=settings.document_upload_indexing,
                object_storage=document_object_storage,
            ),
            query_history_store=SqlAlchemyQueryHistoryStore(settings.database_url),
            auth_user_store=SqlAlchemyAuthUserStore(settings.database_url),
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


DeploymentShaStatus = Literal["set", "missing", "invalid"]
DeploymentShaSource = Literal["env", "env_file", "default_file", "unavailable"]


class DeploymentMetadataBoundaries(BaseModel):
    model_config = ConfigDict(extra="forbid")

    production_write: bool
    production_env_write: bool
    provider_call: bool
    object_storage_write: bool
    secret_values_reported: bool
    allowed_http_methods: list[Literal["GET"]]
    non_get_http_methods_allowed: bool


class DeploymentMetadataResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["deployment_metadata_available"]
    evidence_grade: Literal["L1-public-or-runtime"]
    version: str
    deploy_sha_status: DeploymentShaStatus
    deploy_sha: str | None
    deploy_sha_source: DeploymentShaSource
    required_report_fields: dict[str, str | bool | None]
    boundaries: DeploymentMetadataBoundaries
    supported_claims: list[str]
    forbidden_claims: list[str]


CONTROLLED_API_AUTH_ENV = "MEDICAL_AUDIT_CONTROLLED_API_AUTH"
CONTROLLED_API_TENANT_HEADER = "X-Tenant-Id"
DEPLOY_SHA_ENV = "MEDICAL_AUDIT_DEPLOY_SHA"
DEPLOY_SHA_FILE_ENV = "MEDICAL_AUDIT_DEPLOY_SHA_FILE"
DEPLOY_SHA_FILE_NAME = ".deploy-sha"
WEB_STATIC_ROOT_ENV = "MEDICAL_AUDIT_WEB_STATIC_ROOT"
API_V1_PREFIX = "/api/v1"
API_BACKEND_PREFIX = "/api/backend"
CONTROLLED_API_AUTH_VALUES = frozenset({"1", "true", "yes", "enforce", "required"})
CONTROLLED_API_PUBLIC_EXACT_PATHS = frozenset(
    {
        "/",
        "/health",
        "/favicon.ico",
        "/auth/roles",
        "/index/postgres-status",
    }
)
CONTROLLED_API_PUBLIC_PREFIXES = ("/static/", "/preview/")
CONTROLLED_API_PROTECTED_EXACT_PATHS = frozenset(
    {
        "/auth/session",
        "/deployment/metadata",
        "/query",
        "/projects",
    }
)
CONTROLLED_API_PROTECTED_PREFIXES = (
    "/agents",
    "/analytics",
    "/archive/",
    "/audit/",
    "/audit-findings",
    "/auth/users",
    "/documents",
    "/graph/",
    "/index",
    "/operation/logs",
    "/pages/chat/export",
    "/pages/audit-findings",
    "/pages/review-tasks",
    "/projects/",
    "/query/",
    "/remediation/",
    "/reports/",
    "/review-tasks/",
    "/rules/",
)
STATIC_FALLBACK_RESERVED_PREFIXES = (
    "api/",
    "agents",
    "agents/",
    "analytics",
    "analytics/",
    "archive/",
    "audit/",
    "audit-findings",
    "audit-findings/",
    "auth",
    "auth/",
    "documents/permissions",
    "documents/uploads",
    "graph/",
    "index",
    "index/",
    "operation/",
    "pages/",
    "preview/",
    "projects",
    "projects/",
    "query",
    "query/",
    "remediation/",
    "reports/",
    "review-tasks/",
    "rules/",
    "static/",
)
STATIC_EXPORT_PORTAL_PATHS = (
    "agent-market",
    "agents",
    "analytics",
    "archive",
    "chat",
    "documents",
    "findings",
    "graph",
    "guided-check",
    "knowledge-base",
    "knowledge-query",
    "login",
    "projects",
    "remediation",
    "reports",
    "rules",
    "workspace",
)


def create_app(
    api_state: ApiState | None = None,
    *,
    enforce_controlled_api_auth: bool | None = None,
) -> FastAPI:
    state = api_state or ApiState.from_settings(load_settings())
    app = FastAPI(title="Medical Audit Knowledge Query API", version=__version__)
    app.state.api_state = state

    if _controlled_api_auth_enabled(enforce_controlled_api_auth):

        @app.middleware("http")
        async def controlled_api_auth_middleware(
            request: Request,
            call_next: Callable[[Request], Awaitable[StarletteResponse]],
        ) -> StarletteResponse:
            if _should_authenticate_controlled_api_path(
                request.url.path,
                request.method,
            ):
                tenant_id = normalize_tenant_id(request.headers.get(CONTROLLED_API_TENANT_HEADER))
                if tenant_id is None:
                    record_operation(
                        state,
                        "authorization-denied",
                        {
                            "attempted_action": "controlled-api-auth",
                            "permission": "access_controlled_api",
                            "path": request.url.path,
                            "method": request.method,
                            "user_identifier": request.headers.get("X-User-Id")
                            or "anonymous",
                            "role": request.headers.get("X-Role") or "anonymous",
                            "tenant_id": None,
                            "status_code": 401,
                            "reason": f"{CONTROLLED_API_TENANT_HEADER} header is required",
                        },
                    )
                    return JSONResponse(
                        status_code=401,
                        content={"detail": f"{CONTROLLED_API_TENANT_HEADER} header is required"},
                    )
                try:
                    user = resolve_authenticated_user(
                        state,
                        x_user_id=request.headers.get("X-User-Id"),
                        x_role=request.headers.get("X-Role"),
                        project_key=_project_key_for_auth_middleware(request),
                        tenant_id=tenant_id,
                    )
                except HTTPException as exc:
                    record_operation(
                        state,
                        "authorization-denied",
                        {
                            "attempted_action": "controlled-api-auth",
                            "permission": "access_controlled_api",
                            "path": request.url.path,
                            "method": request.method,
                            "user_identifier": request.headers.get("X-User-Id")
                            or "anonymous",
                            "role": request.headers.get("X-Role") or "anonymous",
                            "tenant_id": tenant_id,
                            "status_code": exc.status_code,
                            "reason": str(exc.detail),
                        },
                    )
                    return JSONResponse(
                        status_code=exc.status_code,
                        content={"detail": exc.detail},
                    )
                request.state.authenticated_user = user
            return await call_next(request)

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

    @app.get(f"{API_V1_PREFIX}/health", response_model=HealthResponse)
    def versioned_health() -> HealthResponse:
        return health()

    @app.get(f"{API_BACKEND_PREFIX}/health", response_model=HealthResponse)
    def backend_proxy_health() -> HealthResponse:
        return health()

    @app.get("/deployment/metadata", response_model=DeploymentMetadataResponse)
    def deployment_metadata() -> DeploymentMetadataResponse:
        return _deployment_metadata_response()

    @app.get(f"{API_V1_PREFIX}/deployment/metadata", response_model=DeploymentMetadataResponse)
    def versioned_deployment_metadata() -> DeploymentMetadataResponse:
        return deployment_metadata()

    @app.get(
        f"{API_BACKEND_PREFIX}/deployment/metadata",
        response_model=DeploymentMetadataResponse,
    )
    def backend_proxy_deployment_metadata() -> DeploymentMetadataResponse:
        return deployment_metadata()

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
    from medical_audit_kb.api.routes_auth import router as auth_router
    from medical_audit_kb.api.routes_documents import router as documents_router
    from medical_audit_kb.api.routes_index import router as index_router
    from medical_audit_kb.api.routes_pages import router as pages_router
    from medical_audit_kb.api.routes_preview import router as preview_router
    from medical_audit_kb.api.routes_projects import router as projects_router
    from medical_audit_kb.api.routes_query import router as query_router
    from medical_audit_kb.api.routes_workbench import router as workbench_router

    web_static_root = _web_static_export_root()
    if web_static_root is not None:
        _register_static_export_root(app, web_static_root)
        _register_static_export_portal_routes(app, web_static_root)

    routers = (
        pages_router,
        query_router,
        workbench_router,
        auth_router,
        agents_router,
        analytics_router,
        documents_router,
        projects_router,
        index_router,
        preview_router,
    )
    for router in routers:
        app.include_router(router)
    for router in routers:
        app.include_router(router, prefix=API_V1_PREFIX)
    for router in routers:
        app.include_router(router, prefix=API_BACKEND_PREFIX)

    if web_static_root is not None:
        _register_static_export_fallback(app, web_static_root)
    return app


def _controlled_api_auth_enabled(enforce_controlled_api_auth: bool | None) -> bool:
    if enforce_controlled_api_auth is not None:
        return enforce_controlled_api_auth
    return os.getenv(CONTROLLED_API_AUTH_ENV, "").strip().lower() in CONTROLLED_API_AUTH_VALUES


def _should_authenticate_controlled_api_path(path: str, method: str) -> bool:
    if method.upper() == "OPTIONS":
        return False
    normalized_path = _controlled_api_match_path(path)
    if normalized_path in CONTROLLED_API_PUBLIC_EXACT_PATHS:
        return False
    if any(normalized_path.startswith(prefix) for prefix in CONTROLLED_API_PUBLIC_PREFIXES):
        return False
    if normalized_path in CONTROLLED_API_PROTECTED_EXACT_PATHS:
        return True
    return any(normalized_path.startswith(prefix) for prefix in CONTROLLED_API_PROTECTED_PREFIXES)


def _project_key_for_auth_middleware(request: Request) -> str | None:
    project_key = request.headers.get("X-Project-Key")
    if project_key:
        return project_key
    parts = [part for part in _controlled_api_match_path(request.url.path).split("/") if part]
    if len(parts) >= 2 and parts[0] == "projects":
        return urllib.parse.unquote(parts[1])
    return None


def _controlled_api_match_path(path: str) -> str:
    if path == API_V1_PREFIX:
        return "/"
    if path.startswith(f"{API_V1_PREFIX}/"):
        return path[len(API_V1_PREFIX) :]
    if path == API_BACKEND_PREFIX:
        return "/"
    if path.startswith(f"{API_BACKEND_PREFIX}/"):
        return path[len(API_BACKEND_PREFIX) :]
    return path


def _web_static_export_root() -> Path | None:
    raw_root = os.getenv(WEB_STATIC_ROOT_ENV, "").strip()
    if not raw_root:
        return None
    return Path(raw_root).expanduser().resolve()


def _deployment_metadata_response() -> DeploymentMetadataResponse:
    deploy_sha_status, deploy_sha, deploy_sha_source = _resolve_deploy_sha()
    return DeploymentMetadataResponse(
        status="deployment_metadata_available",
        evidence_grade="L1-public-or-runtime",
        version=__version__,
        deploy_sha_status=deploy_sha_status,
        deploy_sha=deploy_sha,
        deploy_sha_source=deploy_sha_source,
        required_report_fields={
            "expected_deploy_sha": deploy_sha,
            "current_deploy_sha": deploy_sha,
            "deploy_sha_status": deploy_sha_status,
        },
        boundaries=DeploymentMetadataBoundaries(
            production_write=False,
            production_env_write=False,
            provider_call=False,
            object_storage_write=False,
            secret_values_reported=False,
            allowed_http_methods=["GET"],
            non_get_http_methods_allowed=False,
        ),
        supported_claims=[
            "This endpoint exposes the running application deploy SHA when configured.",
            "This endpoint does not read production env files or write runtime state.",
        ],
        forbidden_claims=[
            (
                "This response proves production was observed unless the endpoint was "
                "called on production."
            ),
            (
                "This endpoint performs deployment, schema migration, or production "
                "configuration writes."
            ),
        ],
    )


def _resolve_deploy_sha() -> tuple[DeploymentShaStatus, str | None, DeploymentShaSource]:
    env_sha = os.getenv(DEPLOY_SHA_ENV, "").strip()
    if env_sha:
        return _normalize_deploy_sha(env_sha, source="env")

    env_file = os.getenv(DEPLOY_SHA_FILE_ENV, "").strip()
    if env_file:
        return _read_deploy_sha_file(Path(env_file).expanduser(), source="env_file")

    for path in _default_deploy_sha_paths():
        status, deploy_sha, source = _read_deploy_sha_file(path, source="default_file")
        if status != "missing":
            return status, deploy_sha, source
    return "missing", None, "unavailable"


def _default_deploy_sha_paths() -> list[Path]:
    repo_root = Path(__file__).resolve().parents[3]
    candidates = [
        Path.cwd() / DEPLOY_SHA_FILE_NAME,
        repo_root / DEPLOY_SHA_FILE_NAME,
    ]
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in candidates:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(resolved)
    return unique


def _read_deploy_sha_file(
    path: Path,
    *,
    source: DeploymentShaSource,
) -> tuple[DeploymentShaStatus, str | None, DeploymentShaSource]:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return "missing", None, "unavailable"
    except OSError:
        return "invalid", None, source
    return _normalize_deploy_sha(raw, source=source)


def _normalize_deploy_sha(
    raw_value: str,
    *,
    source: DeploymentShaSource,
) -> tuple[DeploymentShaStatus, str | None, DeploymentShaSource]:
    first_line = raw_value.splitlines()[0].strip().lower() if raw_value.splitlines() else ""
    if not first_line:
        return "missing", None, "unavailable"
    if not _looks_like_git_sha(first_line):
        return "invalid", None, source
    return "set", first_line, source


def _looks_like_git_sha(value: str) -> bool:
    return 7 <= len(value) <= 64 and all(char in "0123456789abcdef" for char in value)


def _register_static_export_root(app: FastAPI, static_root: Path) -> None:
    @app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
    def static_export_root() -> FileResponse:
        return _static_export_response(static_root, "")


def _register_static_export_portal_routes(app: FastAPI, static_root: Path) -> None:
    for asset_path in STATIC_EXPORT_PORTAL_PATHS:

        def static_export_portal_route(asset_path: str = asset_path) -> FileResponse:
            return _static_export_response(static_root, asset_path)

        app.add_api_route(
            f"/{asset_path}",
            static_export_portal_route,
            methods=["GET", "HEAD"],
            include_in_schema=False,
            name=f"static_export_portal_{asset_path.replace('-', '_')}",
        )


def _register_static_export_fallback(app: FastAPI, static_root: Path) -> None:
    @app.api_route("/{asset_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    def static_export_fallback(asset_path: str) -> FileResponse:
        if _is_backend_reserved_static_fallback_path(asset_path):
            raise HTTPException(status_code=404, detail="backend route not found")
        return _static_export_response(static_root, asset_path)


def _is_backend_reserved_static_fallback_path(asset_path: str) -> bool:
    normalized = asset_path.strip("/")
    if normalized == "":
        return False
    return any(
        _matches_backend_reserved_static_fallback_prefix(normalized, prefix)
        for prefix in STATIC_FALLBACK_RESERVED_PREFIXES
    )


def _matches_backend_reserved_static_fallback_prefix(normalized_path: str, prefix: str) -> bool:
    normalized_prefix = prefix.strip("/")
    if not normalized_prefix:
        return False
    if prefix.endswith("/"):
        return normalized_path.startswith(prefix)
    return normalized_path == normalized_prefix or normalized_path.startswith(
        f"{normalized_prefix}/",
    )


def _static_export_response(static_root: Path, asset_path: str) -> FileResponse:
    if not static_root.is_dir():
        raise HTTPException(status_code=404, detail="web static root not found")
    normalized_path = asset_path.strip("/")
    if normalized_path == "":
        return _static_file_response(static_root, static_root / "index.html")
    candidate = _resolve_static_candidate(static_root, normalized_path)
    if candidate.is_dir():
        return _static_file_response(static_root, candidate / "index.html")
    if candidate.is_file():
        return _static_file_response(static_root, candidate)
    index_candidate = candidate / "index.html"
    if index_candidate.is_file():
        return _static_file_response(static_root, index_candidate)
    html_candidate = candidate.with_suffix(".html")
    if html_candidate.is_file():
        return _static_file_response(static_root, html_candidate)
    if Path(normalized_path).suffix:
        raise HTTPException(status_code=404, detail="static asset not found")
    return _static_file_response(static_root, static_root / "index.html")


def _resolve_static_candidate(static_root: Path, normalized_path: str) -> Path:
    root = static_root.resolve()
    candidate = (root / normalized_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="static asset not found") from exc
    return candidate


def _static_file_response(static_root: Path, path: Path) -> FileResponse:
    candidate = _resolve_static_candidate(static_root, str(path.relative_to(static_root)))
    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="static asset not found")
    return FileResponse(candidate)


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
