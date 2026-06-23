from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal, cast

import psycopg
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from medical_audit_kb.api.app import (
    ApiState,
    PreviewReference,
    get_api_state,
    record_index_run,
    record_operation,
)
from medical_audit_kb.api.auth import AuthenticatedUser, Permission, require_permission
from medical_audit_kb.api.evaluation_reports import (
    latest_evaluation_report,
    list_evaluation_history,
    persist_evaluation_report,
)
from medical_audit_kb.api.postgres_status import (
    count_postgres_embeddings,
    load_postgres_index_status,
    row_count,
)
from medical_audit_kb.evaluation.answer_datasets import load_answer_evaluation_cases
from medical_audit_kb.evaluation.answer_runner import evaluate_answers
from medical_audit_kb.evaluation.datasets import load_evaluation_cases
from medical_audit_kb.evaluation.runner import evaluate_retrieval
from medical_audit_kb.generation.answer_builder import (
    NoCitedEvidenceError,
    build_citation_backed_answer,
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
from medical_audit_kb.preview.resolver import PreviewResolutionError
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


class EvaluationRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    retrieval_cases_file: str = "configs/evaluation/knowledge-query-human-evaluation-cases-v1.yaml"
    answer_cases_file: str = "configs/evaluation/knowledge-query-answer-evaluation-cases-v1.yaml"
    max_retrieval_cases: int = Field(default=52, gt=0)
    max_answer_cases: int = Field(default=8, gt=0)
    top_k: int = Field(default=5, gt=0)
    smoke_question: str = Field(default="医保基金审核依据", min_length=1)
    min_recall_at_k: float = Field(default=1.0, ge=0.0, le=1.0)
    min_answer_pass_rate: float = Field(default=1.0, ge=0.0, le=1.0)


@router.post("/rebuild")
def rebuild_index(
    payload: IndexRunRequest,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> dict[str, object]:
    _require_index_manager(state, x_user_id=x_user_id, x_role=x_role, action="index-rebuild")
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
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> dict[str, object]:
    _require_index_manager(state, x_user_id=x_user_id, x_role=x_role, action="index-incremental")
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
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> dict[str, object]:
    _require_index_manager(state, x_user_id=x_user_id, x_role=x_role, action="index-retry-file")
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
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> dict[str, object]:
    _require_index_manager(
        state,
        x_user_id=x_user_id,
        x_role=x_role,
        action="index-version-activate",
    )
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
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> dict[str, object]:
    _require_index_manager(
        state,
        x_user_id=x_user_id,
        x_role=x_role,
        action="index-version-rollback",
    )
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


@router.post("/evaluation/run")
def run_post_release_evaluation(
    payload: EvaluationRunRequest,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> dict[str, object]:
    _require_index_manager(
        state,
        x_user_id=x_user_id,
        x_role=x_role,
        action="index-evaluation-run",
    )
    if state.search_engine is None:
        raise HTTPException(status_code=409, detail="search backend is not ready")
    try:
        retrieval_cases = load_evaluation_cases(Path(payload.retrieval_cases_file))[
            : payload.max_retrieval_cases
        ]
        answer_cases = load_answer_evaluation_cases(Path(payload.answer_cases_file))[
            : payload.max_answer_cases
        ]
        retrieval_summary = evaluate_retrieval(
            retrieval_cases,
            state.search_engine,
            top_k=payload.top_k,
            preview_resolver=state.preview_resolver,
        )
        answer_summary = evaluate_answers(
            answer_cases,
            state.search_engine,
            top_k=payload.top_k,
        )
        ui_smoke = _run_ui_smoke_check(
            state,
            question=payload.smoke_question,
            top_k=payload.top_k,
        )
    except (FileNotFoundError, ValueError, NoCitedEvidenceError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    status = (
        "pass"
        if retrieval_summary.recall_at_k >= payload.min_recall_at_k
        and answer_summary.pass_rate >= payload.min_answer_pass_rate
        and bool(ui_smoke["success"])
        else "fail"
    )
    response: dict[str, object] = {
        "status": status,
        "retrieval": retrieval_summary.to_dict(),
        "answer": answer_summary.to_dict(),
        "ui_smoke": ui_smoke,
        "thresholds": {
            "min_recall_at_k": payload.min_recall_at_k,
            "min_answer_pass_rate": payload.min_answer_pass_rate,
        },
    }
    report_metadata = persist_evaluation_report(
        state,
        payload=payload,
        result=response,
        search_backend=_search_backend_response(state),
    )
    response["report"] = report_metadata
    response["history"] = report_metadata.get("history", {})
    state.evaluation_runs.append(response)
    record_operation(
        state,
        "index-evaluation-run",
        {
            "status": status,
            "retrieval_case_count": retrieval_summary.case_count,
            "answer_case_count": answer_summary.case_count,
            "ui_smoke_success": bool(ui_smoke["success"]),
        },
    )
    return response


@router.get("/evaluation/latest/export")
def export_latest_evaluation_report(
    state: Annotated[ApiState, Depends(get_api_state)],
) -> dict[str, object]:
    report = latest_evaluation_report(state)
    if report is None:
        raise HTTPException(status_code=404, detail="evaluation report not found")
    record_operation(
        state,
        "index-evaluation-report-export",
        {"run_id": str(report.get("run_id", "unknown"))},
    )
    return report


@router.get("/evaluation/history")
def evaluation_history(state: Annotated[ApiState, Depends(get_api_state)]) -> dict[str, object]:
    items = list_evaluation_history(state, limit=20)
    record_operation(
        state,
        "index-evaluation-history-view",
        {"count": len(items)},
    )
    return {"items": items}


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
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> dict[str, object]:
    user = _require_index_manager(
        state,
        x_user_id=x_user_id,
        x_role=x_role,
        action="search-backend-postgres-load",
    )
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
            "user_identifier": user.user_identifier,
            "role": user.role.value,
        },
    )
    return response


def _require_index_manager(
    state: ApiState,
    *,
    x_user_id: str | None,
    x_role: str | None,
    action: str,
) -> AuthenticatedUser:
    return require_permission(
        state,
        permission=Permission.MANAGE_INDEX,
        x_user_id=x_user_id,
        x_role=x_role,
        attempted_action=action,
    )


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


def _run_ui_smoke_check(
    state: ApiState,
    *,
    question: str,
    top_k: int,
) -> dict[str, object]:
    if state.search_engine is None:
        return {"success": False, "question": question, "error": "search backend is not ready"}

    try:
        results = state.search_engine.search(question, top_k=top_k)
        answer = build_citation_backed_answer(
            question,
            results,
            generation_provider=state.answer_generation_provider,
        )
    except NoCitedEvidenceError as exc:
        return {"success": False, "question": question, "error": str(exc)}

    preview_path: str | None = None
    preview_success = False
    first_citation = answer.citations[0] if answer.citations else None
    if first_citation is not None:
        state.preview_references[first_citation.chunk_id] = PreviewReference(
            locator=first_citation.locator,
            citation_text=first_citation.snippet,
        )
        preview_path = f"/pages/preview/{first_citation.chunk_id}"
        try:
            state.preview_resolver.resolve(
                first_citation.locator,
                citation_text=first_citation.snippet,
            )
            preview_success = True
        except PreviewResolutionError as exc:
            return {
                "success": False,
                "question": question,
                "citation_count": len(answer.citations),
                "preview_path": preview_path,
                "error": str(exc),
            }

    return {
        "success": bool(answer.citations) and preview_success,
        "question": question,
        "citation_count": len(answer.citations),
        "preview_path": preview_path,
        "confidence": answer.confidence.value,
    }
