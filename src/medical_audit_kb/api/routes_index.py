from __future__ import annotations

from typing import Annotated, Literal, cast

import psycopg
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from medical_audit_kb.api.app import ApiState, get_api_state, record_index_run, record_operation
from medical_audit_kb.api.postgres_status import (
    count_postgres_embeddings,
    load_postgres_index_status,
    row_count,
)
from medical_audit_kb.indexing.embeddings import (
    DeterministicFakeEmbeddingProvider,
    EmbeddingProvider,
    EmbeddingProviderError,
    OpenAICompatibleEmbeddingProvider,
)
from medical_audit_kb.indexing.index_activation import (
    IndexActivationError,
    activate_index_version,
    rollback_index_version,
)
from medical_audit_kb.retrieval.postgres_search import load_postgres_hybrid_search_engine

router = APIRouter(prefix="/index")


class IndexRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    package_version_key: str | None = None


class RetryFileRequest(IndexRunRequest):
    relative_path: str


class PostgresSearchBackendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    embedding_provider: Literal["openai", "fake"]
    embedding_model: str = Field(min_length=1)
    embedding_dimension: int = Field(gt=0)
    api_key_env: str | None = Field(default=None, min_length=1)
    embedding_base_url: str = Field(default="https://api.openai.com/v1", min_length=1)
    embedding_batch_size: int = Field(default=128, gt=0)


class IndexVersionSwitchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index_version_key: str = Field(min_length=1)


@router.post("/rebuild")
def rebuild_index(
    payload: IndexRunRequest,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> dict[str, object]:
    _require_index_admin(x_role)
    run_result = state.index_pipeline.run_full_rebuild(
        state.source_root,
        package_version_key=payload.package_version_key,
    )
    record_index_run(state, run_result)
    return {"summary": run_result.summary.to_dict()}


@router.post("/incremental")
def incremental_index(
    payload: IndexRunRequest,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> dict[str, object]:
    _require_index_admin(x_role)
    if state.current_snapshot is None:
        raise HTTPException(status_code=409, detail="no previous snapshot for incremental index")
    run_result = state.index_pipeline.run_incremental(
        state.source_root,
        previous_snapshot=state.current_snapshot,
        package_version_key=payload.package_version_key,
    )
    record_index_run(state, run_result)
    return {"summary": run_result.summary.to_dict()}


@router.post("/retry-file")
def retry_file(
    payload: RetryFileRequest,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> dict[str, object]:
    _require_index_admin(x_role)
    run_result = state.index_pipeline.retry_file(
        state.source_root,
        relative_path=payload.relative_path,
        package_version_key=payload.package_version_key,
    )
    record_index_run(state, run_result)
    return {"summary": run_result.summary.to_dict()}


@router.get("/versions")
def index_versions(state: Annotated[ApiState, Depends(get_api_state)]) -> dict[str, object]:
    record_operation(state, "index-versions-view", {"count": len(state.index_versions)})
    return {"items": state.index_versions}


@router.get("/jobs")
def index_jobs(state: Annotated[ApiState, Depends(get_api_state)]) -> dict[str, object]:
    record_operation(state, "index-jobs-view", {"count": len(state.index_jobs)})
    return {"items": state.index_jobs}


@router.get("/failures")
def index_failures(state: Annotated[ApiState, Depends(get_api_state)]) -> dict[str, object]:
    record_operation(state, "index-failures-view", {"count": len(state.failed_files)})
    return {"items": state.failed_files}


@router.get("/pending")
def index_pending(state: Annotated[ApiState, Depends(get_api_state)]) -> dict[str, object]:
    record_operation(state, "index-pending-view", {"count": len(state.pending_files)})
    return {"items": state.pending_files}


@router.get("/search-backend")
def search_backend_status(state: Annotated[ApiState, Depends(get_api_state)]) -> dict[str, object]:
    response = _search_backend_response(state)
    record_operation(
        state,
        "search-backend-status-view",
        {"backend": response["backend"], "ready": response["ready"]},
    )
    return response


@router.post("/versions/activate")
def activate_postgres_index_version(
    payload: IndexVersionSwitchRequest,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> dict[str, object]:
    _require_index_admin(x_role)
    try:
        result = activate_index_version(
            database_url=state.settings.database_url,
            index_version_key=payload.index_version_key,
        )
    except IndexActivationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except psycopg.Error as exc:
        raise HTTPException(status_code=503, detail=f"index activation failed: {exc}") from exc
    record_operation(
        state,
        "index-version-activate",
        {
            "index_version_key": result.index_version_key,
            "previous_status": result.previous_status,
            "deactivated_index_version_keys": list(result.deactivated_index_version_keys),
        },
    )
    return _index_version_switch_response(result.to_dict())


@router.post("/versions/rollback")
def rollback_postgres_index_version(
    payload: IndexVersionSwitchRequest,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> dict[str, object]:
    _require_index_admin(x_role)
    try:
        result = rollback_index_version(
            database_url=state.settings.database_url,
            index_version_key=payload.index_version_key,
        )
    except IndexActivationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except psycopg.Error as exc:
        raise HTTPException(status_code=503, detail=f"index rollback failed: {exc}") from exc
    record_operation(
        state,
        "index-version-rollback",
        {
            "index_version_key": result.index_version_key,
            "previous_status": result.previous_status,
            "deactivated_index_version_keys": list(result.deactivated_index_version_keys),
        },
    )
    return _index_version_switch_response(result.to_dict())


@router.get("/postgres-status")
def postgres_index_status(state: Annotated[ApiState, Depends(get_api_state)]) -> dict[str, object]:
    try:
        response = load_postgres_index_status(state.settings.database_url)
    except psycopg.Error as exc:
        raise HTTPException(status_code=503, detail=f"postgres status query failed: {exc}") from exc
    record_operation(
        state,
        "postgres-index-status-view",
        {
            "document_chunks": row_count(response, "document_chunks"),
            "chunk_embeddings": row_count(response, "chunk_embeddings"),
        },
    )
    return response


@router.post("/search-backend/postgres")
def load_postgres_search_backend(
    payload: PostgresSearchBackendRequest,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> dict[str, object]:
    _require_index_admin(x_role)
    try:
        embedding_provider = _build_embedding_provider(payload)
        matching_embedding_count = count_postgres_embeddings(
            state.settings.database_url,
            embedding_provider,
        )
        state.search_engine = load_postgres_hybrid_search_engine(
            database_url=state.settings.database_url,
            embedding_provider=embedding_provider,
        )
    except EmbeddingProviderError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except psycopg.Error as exc:
        raise HTTPException(
            status_code=503,
            detail=f"postgres search backend load failed: {exc}",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    state.search_backend = "postgres"
    state.search_backend_details = _search_backend_details(
        payload,
        embedding_provider,
        matching_embedding_count=matching_embedding_count,
    )
    response = _search_backend_response(state)
    record_operation(
        state,
        "search-backend-postgres-load",
        {
            "backend": response["backend"],
            "ready": response["ready"],
            "embedding_provider": embedding_provider.provider,
            "embedding_model": embedding_provider.model_name,
            "embedding_dimension": embedding_provider.dimension,
            "matching_embedding_count": matching_embedding_count,
        },
    )
    return response


def _require_index_admin(role: str | None) -> None:
    if role != "it-admin":
        raise HTTPException(status_code=403, detail="index operation requires it-admin role")


def _build_embedding_provider(payload: PostgresSearchBackendRequest) -> EmbeddingProvider:
    if payload.embedding_provider == "fake":
        return cast(
            EmbeddingProvider,
            DeterministicFakeEmbeddingProvider(dimension=payload.embedding_dimension),
        )

    if payload.api_key_env is None:
        raise HTTPException(
            status_code=422,
            detail="api_key_env is required for openai embedding provider",
        )
    return OpenAICompatibleEmbeddingProvider.from_env(
        api_key_env=payload.api_key_env,
        model_name=payload.embedding_model,
        dimension=payload.embedding_dimension,
        base_url=payload.embedding_base_url,
        batch_size=payload.embedding_batch_size,
    )


def _search_backend_details(
    payload: PostgresSearchBackendRequest,
    embedding_provider: EmbeddingProvider,
    *,
    matching_embedding_count: int,
) -> dict[str, object]:
    details: dict[str, object] = {
        "embedding_provider": embedding_provider.provider,
        "embedding_model": embedding_provider.model_name,
        "provider_version": embedding_provider.provider_version,
        "embedding_dimension": embedding_provider.dimension,
        "matching_embedding_count": matching_embedding_count,
    }
    if payload.embedding_provider == "openai":
        details.update(
            {
                "api_key_env": payload.api_key_env,
                "embedding_base_url": payload.embedding_base_url,
                "embedding_batch_size": payload.embedding_batch_size,
            }
        )
    return details


def _search_backend_response(state: ApiState) -> dict[str, object]:
    return {
        "backend": state.search_backend,
        "ready": state.search_engine is not None,
        "details": state.search_backend_details,
    }


def _index_version_switch_response(result: dict[str, object]) -> dict[str, object]:
    return {
        "result": result,
        "next_steps": [
            "reload-postgres-search-backend",
            "run-ui-smoke",
            "run-fixed-evaluation",
        ],
    }
