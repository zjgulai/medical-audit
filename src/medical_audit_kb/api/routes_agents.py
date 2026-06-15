from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.exc import SQLAlchemyError

from medical_audit_kb.api.agent_store import (
    AGENT_CATEGORIES,
    DEFAULT_AGENT_PAYLOADS,
    AgentStore,
    InMemoryAgentStore,
    combined_agent_payloads,
    validate_agent_category,
)
from medical_audit_kb.api.app import ApiState, get_api_state, record_operation
from medical_audit_kb.api.role_policy import require_audit_role_for_write

router = APIRouter()


class AgentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=128)
    category: str = Field(min_length=1, max_length=48)
    topic: str = Field(min_length=1, max_length=256)
    prompt: str = Field(min_length=1, max_length=8000)
    knowledge_base: str = Field(default="项目默认知识库", min_length=1, max_length=256)
    project_name: str = Field(default="医保基金使用合规专项自查", min_length=1, max_length=256)
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str) -> str:
        try:
            return validate_agent_category(value)
        except ValueError as exc:
            raise ValueError("unsupported agent category") from exc


@router.get("/agents")
def list_agents(
    state: Annotated[ApiState, Depends(get_api_state)],
) -> dict[str, object]:
    try:
        custom_agents = _agent_store(state).list_agents()
    except SQLAlchemyError:
        return {
            "items": [dict(agent) for agent in DEFAULT_AGENT_PAYLOADS],
            "categories": list(AGENT_CATEGORIES),
            "store": {"ready": False, "backend": "unavailable"},
        }

    items = combined_agent_payloads(custom_agents)
    record_operation(state, "agents-list", {"agent_count": len(items)})
    return {
        "items": items,
        "categories": list(AGENT_CATEGORIES),
        "store": {"ready": True, "backend": _agent_store(state).__class__.__name__},
    }


@router.post("/agents")
def create_agent(
    payload: AgentCreateRequest,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> dict[str, object]:
    role = require_audit_role_for_write(
        state,
        role=x_role,
        user_identifier=x_user_id,
        attempted_action="agent-create",
        denied_action="agent-access-denied",
    )
    values = payload.model_dump()
    values["created_by"] = x_user_id or "anonymous"
    try:
        agent = _agent_store(state).add_agent(values)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=409,
            detail="persistent agent store is not available",
        ) from exc

    record_operation(
        state,
        "agent-create",
        {
            "agent_id": agent["id"],
            "category": agent["category"],
            "created_by": x_user_id or "anonymous",
            "role": role,
        },
    )
    return {
        "item": agent,
        "store": {"ready": True, "backend": _agent_store(state).__class__.__name__},
    }


def _agent_store(state: ApiState) -> AgentStore:
    if state.agent_store is None:
        state.agent_store = InMemoryAgentStore()
    return state.agent_store
