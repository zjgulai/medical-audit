from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from medical_audit_kb.api.app import ApiState, get_api_state, record_operation
from medical_audit_kb.preview.resolver import PreviewResolutionError

router = APIRouter(prefix="/preview")


@router.get("/{chunk_id}")
def preview_chunk(
    chunk_id: UUID,
    state: Annotated[ApiState, Depends(get_api_state)],
) -> dict[str, object]:
    reference = state.preview_references.get(chunk_id)
    if reference is None:
        raise HTTPException(status_code=404, detail="preview reference not found")

    try:
        preview = state.preview_resolver.resolve(
            reference.locator,
            citation_text=reference.citation_text,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PreviewResolutionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    record_operation(
        state,
        "preview",
        {
            "chunk_id": str(chunk_id),
            "source_path": str(preview.source_path),
            "media_type": preview.media_type,
        },
    )

    return {
        "chunk_id": str(chunk_id),
        "source_path": str(preview.source_path),
        "media_type": preview.media_type,
        "preview_text": preview.preview_text,
        "locator": preview.locator,
        "highlights": [
            {"start": item.start, "end": item.end, "text": item.text}
            for item in preview.highlights
        ],
        "page_number": preview.page_number,
        "line_start": preview.line_start,
        "line_end": preview.line_end,
        "sheet_name": preview.sheet_name,
        "row_number": preview.row_number,
    }
