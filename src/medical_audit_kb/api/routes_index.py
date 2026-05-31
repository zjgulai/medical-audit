from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict

from medical_audit_kb.api.app import ApiState, get_api_state, record_index_run, record_operation

router = APIRouter(prefix="/index")


class IndexRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    package_version_key: str | None = None


class RetryFileRequest(IndexRunRequest):
    relative_path: str


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


def _require_index_admin(role: str | None) -> None:
    if role != "it-admin":
        raise HTTPException(status_code=403, detail="index operation requires it-admin role")
