from __future__ import annotations

import urllib.parse
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.exc import SQLAlchemyError

from medical_audit_kb.api.agent_store import (
    AGENT_ALLOWED_ROLES,
    AGENT_CATEGORIES,
    AGENT_FEEDBACK_RATINGS,
    AGENT_PROMPT_REVIEW_STATUSES,
    AgentStore,
    DuplicateMarketAgentInstallError,
    InMemoryAgentStore,
    combined_agent_payloads,
    market_agent_template_id,
    validate_agent_category,
    validate_agent_feedback_rating,
    validate_agent_prompt_review_status,
    validate_agent_status,
    validate_agent_visibility_scope,
)
from medical_audit_kb.api.app import ApiState, get_api_state, record_operation
from medical_audit_kb.api.auth import (
    AuthenticatedUser,
    Permission,
    require_permission,
    resolve_authenticated_user,
)
from medical_audit_kb.catalog.agent_catalog import (
    CATALOG_CONTRACT_VERSION,
    get_agent_template,
    list_public_agent_templates,
)

router = APIRouter()

AGENT_PROMPT_ACTIVATION_ROLES: frozenset[str] = frozenset({"admin", "director"})


class AgentMarketInstallRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_name: str = Field(default="医保基金使用合规专项自查", min_length=1, max_length=256)


@router.get("/agent-market/catalog")
def list_agent_market_catalog(
    state: Annotated[ApiState, Depends(get_api_state)],
) -> dict[str, object]:
    items = list_public_agent_templates()
    record_operation(state, "agent-market-catalog-list", {"item_count": len(items)})
    return {
        "contract_version": CATALOG_CONTRACT_VERSION,
        "items": items,
        "count": len(items),
        "featured_count": sum(1 for item in items if item["featured"]),
        "prompt_materialization": "server-only",
    }


@router.post("/agent-market/templates/{template_id}/install")
def install_agent_market_template(
    template_id: str,
    payload: AgentMarketInstallRequest,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
    x_project_name: Annotated[str | None, Header(alias="X-Project-Name")] = None,
) -> dict[str, object]:
    user = require_permission(
        state,
        permission=Permission.MANAGE_AGENTS,
        x_user_id=x_user_id,
        x_role=x_role,
        attempted_action="agent-market-install",
    )
    template = get_agent_template(template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="agent market template not found")
    project_name = payload.project_name.strip()
    _enforce_create_project_scope(
        state,
        visibility_scope="project",
        project_name=project_name,
        request_project_name=x_project_name,
        attempted_action="agent-market-install",
    )
    values = {
        "name": template["name"],
        "category": template["agent_category"],
        "topic": template["topic"],
        "prompt": template["prompt"],
        "knowledge_base": template["knowledge_base"],
        "project_name": project_name,
        "visibility_scope": "project",
        "allowed_roles": list(AGENT_ALLOWED_ROLES),
        "created_by": user.user_identifier,
        "metadata": {
            "source": "agent-market",
            "template_id": template_id,
            "template_summary": template["summary"],
            "template_category": template["category"],
            "template_prompt_sha256": template["prompt_sha256"],
            "featured": template["featured"],
            "featured_rank": template["featured_rank"],
        },
    }
    try:
        result = _agent_store(state).install_market_agent(values)
    except DuplicateMarketAgentInstallError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=409, detail="persistent agent store is not available"
        ) from exc
    record_operation(
        state,
        "agent-market-install",
        {"template_id": template_id, "agent_id": result.item["id"], "created": result.created},
    )
    return {
        "item": result.item,
        "created": result.created,
        "reactivated": result.reactivated,
        "store": {"ready": True, "backend": _agent_store(state).__class__.__name__},
    }


class AgentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=128)
    category: str = Field(min_length=1, max_length=48)
    topic: str = Field(min_length=1, max_length=256)
    prompt: str = Field(min_length=1, max_length=8000)
    knowledge_base: str = Field(default="项目默认知识库", min_length=1, max_length=256)
    project_name: str = Field(default="医保基金使用合规专项自查", min_length=1, max_length=256)
    visibility_scope: str = Field(default="project", min_length=1, max_length=32)
    allowed_roles: list[str] = Field(default_factory=lambda: list(AGENT_ALLOWED_ROLES))
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str) -> str:
        try:
            return validate_agent_category(value)
        except ValueError as exc:
            raise ValueError("unsupported agent category") from exc

    @field_validator("visibility_scope")
    @classmethod
    def validate_visibility_scope(cls, value: str) -> str:
        try:
            return validate_agent_visibility_scope(value)
        except ValueError as exc:
            raise ValueError("unsupported agent visibility scope") from exc

    @field_validator("allowed_roles")
    @classmethod
    def validate_allowed_roles(cls, value: list[str]) -> list[str]:
        normalized = [item for item in value if item in AGENT_ALLOWED_ROLES]
        if not normalized:
            raise ValueError("allowed_roles must contain at least one supported role")
        return normalized

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, object]) -> dict[str, object]:
        if value.get("source") != "agent-market":
            return value
        template_id = value.get("template_id")
        if not isinstance(template_id, str) or not template_id.strip():
            raise ValueError("agent-market metadata.template_id is required")
        normalized_template_id = template_id.strip()
        if len(normalized_template_id) > 128:
            raise ValueError("agent-market metadata.template_id is too long")
        return {**value, "template_id": normalized_template_id}


class AgentPromptVersionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1, max_length=8000)
    change_summary: str = Field(default="prompt updated", min_length=1, max_length=512)
    review_note: str = Field(default="", max_length=1000)


class AgentPromptVersionReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    review_status: str = Field(min_length=1, max_length=32)
    review_note: str = Field(default="", max_length=1000)

    @field_validator("review_status")
    @classmethod
    def validate_review_status(cls, value: str) -> str:
        try:
            return validate_agent_prompt_review_status(value)
        except ValueError as exc:
            raise ValueError("unsupported agent prompt review status") from exc


class AgentPromptVersionRollbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)


class AgentLifecycleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = Field(min_length=1, max_length=32)
    reason: str = Field(default="", max_length=512)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        try:
            return validate_agent_status(value)
        except ValueError as exc:
            raise ValueError("unsupported agent status") from exc


class AgentInvocationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    invocation_source: str = Field(default="agent-workspace", min_length=1, max_length=64)
    question: str | None = Field(default=None, max_length=2000)
    conversation_ref: str | None = Field(default=None, max_length=256)
    metadata: dict[str, object] = Field(default_factory=dict)


class AgentFeedbackCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    invocation_id: str | None = Field(default=None, max_length=128)
    rating: str = Field(min_length=1, max_length=32)
    comment: str = Field(default="", max_length=1000)
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("rating")
    @classmethod
    def validate_rating(cls, value: str) -> str:
        try:
            return validate_agent_feedback_rating(value)
        except ValueError as exc:
            raise ValueError("unsupported agent feedback rating") from exc


@router.get("/agents")
def list_agents(
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
    x_project_name: Annotated[str | None, Header(alias="X-Project-Name")] = None,
) -> dict[str, object]:
    try:
        agent_store = _agent_store(state)
        custom_agents = agent_store.list_agents()
        all_status_custom_agents = agent_store.list_agents(include_inactive=True)
    except SQLAlchemyError:
        fallback_items = _filter_agents_for_project(
            combined_agent_payloads([]),
            x_project_name,
        )
        return {
            "items": fallback_items,
            "categories": list(AGENT_CATEGORIES),
            "store": {"ready": False, "backend": "unavailable"},
            "market_installations": [],
            "market_installation_issues": [],
        }

    items = combined_agent_payloads(custom_agents)
    items = _filter_agents_for_project(items, x_project_name)
    inventory_items = combined_agent_payloads(all_status_custom_agents)
    inventory_items = _filter_agents_for_project(inventory_items, x_project_name)
    user = (
        resolve_authenticated_user(state, x_user_id=x_user_id, x_role=x_role)
        if x_user_id or x_role
        else None
    )
    if user is not None:
        items = _filter_agents_for_role(items, user.role.value)
        inventory_items = _filter_agents_for_role(inventory_items, user.role.value)
    market_installations, market_installation_issues = _market_installation_inventory(
        inventory_items,
        user_identifier=user.user_identifier if user is not None else None,
    )
    record_operation(
        state,
        "agents-list",
        {
            "agent_count": len(items),
            "role": user.role.value if user is not None else None,
            "project_name": _normalize_project_name(x_project_name),
        },
    )
    return {
        "items": items,
        "categories": list(AGENT_CATEGORIES),
        "store": {"ready": True, "backend": _agent_store(state).__class__.__name__},
        "market_installations": market_installations,
        "market_installation_issues": market_installation_issues,
    }


@router.get("/agents/{agent_key}")
def get_agent(
    agent_key: str,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_project_name: Annotated[str | None, Header(alias="X-Project-Name")] = None,
) -> dict[str, object]:
    try:
        agent = _agent_store(state).get_agent(agent_key)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=409,
            detail="persistent agent store is not available",
        ) from exc
    if agent is None:
        agent = _default_agent(agent_key)
    if agent is None:
        raise HTTPException(status_code=404, detail="agent not found")
    _enforce_agent_project_scope(
        state,
        agent,
        x_project_name,
        attempted_action="agent-detail-view",
    )
    record_operation(
        state,
        "agent-detail-view",
        {
            "agent_id": agent["id"],
            "status": agent["status"],
            "project_name": _normalize_project_name(x_project_name),
        },
    )
    return {
        "item": agent,
        "store": {"ready": True, "backend": _agent_store(state).__class__.__name__},
    }


@router.get("/agents/{agent_key}/prompt-versions")
def list_agent_prompt_versions(
    agent_key: str,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_project_name: Annotated[str | None, Header(alias="X-Project-Name")] = None,
) -> dict[str, object]:
    try:
        agent = _agent_payload_for_key(state, agent_key)
        if agent is None:
            raise KeyError(f"agent not found: {agent_key}")
        _enforce_agent_project_scope(
            state,
            agent,
            x_project_name,
            attempted_action="agent-prompt-versions-view",
        )
        items = _agent_store(state).list_prompt_versions(agent_key)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="agent not found") from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=409,
            detail="persistent agent store is not available",
        ) from exc
    record_operation(
        state,
        "agent-prompt-versions-view",
        {"agent_id": agent_key, "version_count": len(items)},
    )
    return {
        "items": items,
        "store": {"ready": True, "backend": _agent_store(state).__class__.__name__},
    }


@router.post("/agents")
def create_agent(
    payload: AgentCreateRequest,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
    x_project_name: Annotated[str | None, Header(alias="X-Project-Name")] = None,
) -> dict[str, object]:
    user = require_permission(
        state,
        permission=Permission.MANAGE_AGENTS,
        x_user_id=x_user_id,
        x_role=x_role,
        attempted_action="agent-create",
    )
    values = payload.model_dump()
    _enforce_create_project_scope(
        state,
        visibility_scope=str(values["visibility_scope"]),
        project_name=str(values["project_name"]),
        request_project_name=x_project_name,
        attempted_action="agent-create",
    )
    values["created_by"] = user.user_identifier
    try:
        template_id = market_agent_template_id(values)
        if template_id is None:
            agent = _agent_store(state).add_agent(values)
            created = True
            reactivated = False
        else:
            install_result = _agent_store(state).install_market_agent(values)
            agent = install_result.item
            created = install_result.created
            reactivated = install_result.reactivated
    except DuplicateMarketAgentInstallError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=409,
            detail="persistent agent store is not available",
        ) from exc

    record_operation(
        state,
        (
            "agent-create"
            if created
            else "agent-install-reactivated"
            if reactivated
            else "agent-install-reused"
        ),
        {
            "agent_id": agent["id"],
            "category": agent["category"],
            "created_by": user.user_identifier,
            "created": created,
            "market_template_id": template_id,
            "reactivated": reactivated,
            "role": user.role.value,
            "role_label": user.role_label,
        },
    )
    return {
        "item": agent,
        "created": created,
        "reactivated": reactivated,
        "store": {"ready": True, "backend": _agent_store(state).__class__.__name__},
    }


@router.post("/agents/{agent_key}/prompt-versions")
def create_agent_prompt_version(
    agent_key: str,
    payload: AgentPromptVersionCreateRequest,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
    x_project_name: Annotated[str | None, Header(alias="X-Project-Name")] = None,
) -> dict[str, object]:
    user = require_permission(
        state,
        permission=Permission.MANAGE_AGENTS,
        x_user_id=x_user_id,
        x_role=x_role,
        attempted_action="agent-prompt-version-create",
    )
    try:
        existing_agent = _agent_payload_for_key(state, agent_key)
        if existing_agent is None:
            raise KeyError(f"agent not found: {agent_key}")
        _enforce_agent_project_scope(
            state,
            existing_agent,
            x_project_name,
            attempted_action="agent-prompt-version-create",
        )
        agent = _agent_store(state).add_prompt_version(
            agent_key,
            prompt=payload.prompt,
            change_summary=payload.change_summary,
            review_note=payload.review_note or payload.change_summary,
            created_by=user.user_identifier,
        )
        created_prompt_version = _latest_prompt_version_from_payload(agent)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="agent not found") from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=409,
            detail="persistent agent store is not available",
        ) from exc
    record_operation(
        state,
        "agent-prompt-version-create",
        {
            "agent_id": agent["id"],
            "created_prompt_version": created_prompt_version,
            "active_prompt_version": agent["prompt_version"],
            "review_status": "pending-review",
            "activation_status": "pending-review",
            "created_by": user.user_identifier,
            "role": user.role.value,
        },
    )
    return {
        "item": agent,
        "store": {"ready": True, "backend": _agent_store(state).__class__.__name__},
    }


@router.post("/agents/{agent_key}/prompt-versions/review")
def review_agent_prompt_version(
    agent_key: str,
    payload: AgentPromptVersionReviewRequest,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
    x_project_name: Annotated[str | None, Header(alias="X-Project-Name")] = None,
) -> dict[str, object]:
    user = _require_agent_prompt_activator(
        state,
        x_user_id=x_user_id,
        x_role=x_role,
        attempted_action="agent-prompt-version-review",
    )
    try:
        existing_agent = _agent_payload_for_key(state, agent_key)
        if existing_agent is None:
            raise KeyError(f"agent not found: {agent_key}")
        _enforce_agent_project_scope(
            state,
            existing_agent,
            x_project_name,
            attempted_action="agent-prompt-version-review",
        )
        agent = _agent_store(state).update_prompt_version_review(
            agent_key,
            version=payload.version,
            review_status=payload.review_status,
            review_note=payload.review_note,
            reviewed_by=user.user_identifier,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="agent prompt version not found") from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=409,
            detail="persistent agent store is not available",
        ) from exc
    record_operation(
        state,
        "agent-prompt-version-review",
        {
            "agent_id": agent["id"],
            "review_version": payload.version,
            "review_status": payload.review_status,
            "active_prompt_version": agent["prompt_version"],
            "activated": payload.review_status == "approved"
            and agent["prompt_version"] == payload.version,
            "reviewed_by": user.user_identifier,
            "role": user.role.value,
        },
    )
    return {
        "item": agent,
        "review_statuses": list(AGENT_PROMPT_REVIEW_STATUSES),
        "store": {"ready": True, "backend": _agent_store(state).__class__.__name__},
    }


@router.post("/agents/{agent_key}/prompt-versions/rollback")
def rollback_agent_prompt_version(
    agent_key: str,
    payload: AgentPromptVersionRollbackRequest,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
    x_project_name: Annotated[str | None, Header(alias="X-Project-Name")] = None,
) -> dict[str, object]:
    user = _require_agent_prompt_activator(
        state,
        x_user_id=x_user_id,
        x_role=x_role,
        attempted_action="agent-prompt-version-rollback",
    )
    try:
        existing_agent = _agent_payload_for_key(state, agent_key)
        if existing_agent is None:
            raise KeyError(f"agent not found: {agent_key}")
        _enforce_agent_project_scope(
            state,
            existing_agent,
            x_project_name,
            attempted_action="agent-prompt-version-rollback",
        )
        agent = _agent_store(state).rollback_prompt_version(
            agent_key,
            version=payload.version,
            created_by=user.user_identifier,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="agent prompt version not found") from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=409,
            detail="persistent agent store is not available",
        ) from exc
    record_operation(
        state,
        "agent-prompt-version-rollback",
        {
            "agent_id": agent["id"],
            "rollback_to_version": payload.version,
            "prompt_version": agent["prompt_version"],
            "activation_status": "approved-active",
            "created_by": user.user_identifier,
            "role": user.role.value,
        },
    )
    return {
        "item": agent,
        "store": {"ready": True, "backend": _agent_store(state).__class__.__name__},
    }


@router.post("/agents/{agent_key}/lifecycle")
def update_agent_lifecycle(
    agent_key: str,
    payload: AgentLifecycleRequest,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
    x_project_name: Annotated[str | None, Header(alias="X-Project-Name")] = None,
) -> dict[str, object]:
    user = require_permission(
        state,
        permission=Permission.MANAGE_AGENTS,
        x_user_id=x_user_id,
        x_role=x_role,
        attempted_action="agent-lifecycle-update",
    )
    try:
        existing_agent = _agent_payload_for_key(state, agent_key)
        if existing_agent is None:
            raise KeyError(f"agent not found: {agent_key}")
        _enforce_agent_project_scope(
            state,
            existing_agent,
            x_project_name,
            attempted_action="agent-lifecycle-update",
        )
        agent = _agent_store(state).update_agent_lifecycle(
            agent_key,
            status=payload.status,
            reason=payload.reason,
            updated_by=user.user_identifier,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="agent not found") from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=409,
            detail="persistent agent store is not available",
        ) from exc
    record_operation(
        state,
        "agent-lifecycle-update",
        {
            "agent_id": agent["id"],
            "status": agent["status"],
            "updated_by": user.user_identifier,
            "role": user.role.value,
        },
    )
    return {
        "item": agent,
        "store": {"ready": True, "backend": _agent_store(state).__class__.__name__},
    }


@router.get("/agents/{agent_key}/invocations")
def list_agent_invocations(
    agent_key: str,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
    x_project_name: Annotated[str | None, Header(alias="X-Project-Name")] = None,
) -> dict[str, object]:
    user = require_permission(
        state,
        permission=Permission.MANAGE_AGENTS,
        x_user_id=x_user_id,
        x_role=x_role,
        attempted_action="agent-invocations-view",
    )
    try:
        agent = _agent_payload_for_key(state, agent_key)
        if agent is not None:
            _enforce_agent_project_scope(
                state,
                agent,
                x_project_name,
                attempted_action="agent-invocations-view",
            )
        items = _agent_store(state).list_invocations(agent_key)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=409,
            detail="persistent agent store is not available",
        ) from exc
    record_operation(
        state,
        "agent-invocations-view",
        {"agent_id": agent_key, "invocation_count": len(items), "role": user.role.value},
    )
    return {
        "items": items,
        "store": {"ready": True, "backend": _agent_store(state).__class__.__name__},
    }


@router.post("/agents/{agent_key}/invocations")
def create_agent_invocation(
    agent_key: str,
    payload: AgentInvocationCreateRequest,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
    x_project_name: Annotated[str | None, Header(alias="X-Project-Name")] = None,
) -> dict[str, object]:
    user = require_permission(
        state,
        permission=Permission.QUERY_KNOWLEDGE,
        x_user_id=x_user_id,
        x_role=x_role,
        attempted_action="agent-invocation-create",
    )
    try:
        agent = _agent_payload_for_key(state, agent_key)
        if agent is None:
            raise KeyError(f"agent not found: {agent_key}")
        _enforce_agent_project_scope(
            state,
            agent,
            x_project_name,
            attempted_action="agent-invocation-create",
        )
        invocation = _agent_store(state).record_invocation(
            agent_key,
            invocation_source=payload.invocation_source,
            question=payload.question,
            conversation_ref=payload.conversation_ref,
            created_by=user.user_identifier,
            metadata=payload.metadata,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="agent not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=409,
            detail="persistent agent store is not available",
        ) from exc
    record_operation(
        state,
        "agent-invocation-create",
        {
            "agent_id": agent_key,
            "invocation_id": invocation["id"],
            "prompt_version": invocation["prompt_version"],
            "created_by": user.user_identifier,
            "role": user.role.value,
        },
    )
    return {
        "item": invocation,
        "store": {"ready": True, "backend": _agent_store(state).__class__.__name__},
    }


@router.get("/agents/{agent_key}/feedback")
def list_agent_feedback(
    agent_key: str,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
    x_project_name: Annotated[str | None, Header(alias="X-Project-Name")] = None,
) -> dict[str, object]:
    user = require_permission(
        state,
        permission=Permission.MANAGE_AGENTS,
        x_user_id=x_user_id,
        x_role=x_role,
        attempted_action="agent-feedback-view",
    )
    try:
        agent = _agent_payload_for_key(state, agent_key)
        if agent is not None:
            _enforce_agent_project_scope(
                state,
                agent,
                x_project_name,
                attempted_action="agent-feedback-view",
            )
        items = _agent_store(state).list_feedback(agent_key)
        summary = _agent_store(state).feedback_summary(agent_key)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=409,
            detail="persistent agent store is not available",
        ) from exc
    record_operation(
        state,
        "agent-feedback-view",
        {"agent_id": agent_key, "feedback_count": len(items), "role": user.role.value},
    )
    return {
        "items": items,
        "ratings": list(AGENT_FEEDBACK_RATINGS),
        "summary": summary,
        "store": {"ready": True, "backend": _agent_store(state).__class__.__name__},
    }


@router.post("/agents/{agent_key}/feedback")
def create_agent_feedback(
    agent_key: str,
    payload: AgentFeedbackCreateRequest,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
    x_project_name: Annotated[str | None, Header(alias="X-Project-Name")] = None,
) -> dict[str, object]:
    user = require_permission(
        state,
        permission=Permission.QUERY_KNOWLEDGE,
        x_user_id=x_user_id,
        x_role=x_role,
        attempted_action="agent-feedback-create",
    )
    try:
        agent = _agent_payload_for_key(state, agent_key)
        if agent is None:
            raise KeyError(f"agent not found: {agent_key}")
        _enforce_agent_project_scope(
            state,
            agent,
            x_project_name,
            attempted_action="agent-feedback-create",
        )
        feedback = _agent_store(state).record_feedback(
            agent_key,
            invocation_id=payload.invocation_id,
            rating=payload.rating,
            comment=payload.comment,
            created_by=user.user_identifier,
            metadata=payload.metadata,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="agent invocation not found") from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=409,
            detail="persistent agent store is not available",
        ) from exc
    record_operation(
        state,
        "agent-feedback-create",
        {
            "agent_id": agent_key,
            "feedback_id": feedback["id"],
            "rating": feedback["rating"],
            "created_by": user.user_identifier,
            "role": user.role.value,
        },
    )
    return {
        "item": feedback,
        "ratings": list(AGENT_FEEDBACK_RATINGS),
        "summary": _agent_store(state).feedback_summary(agent_key),
        "store": {"ready": True, "backend": _agent_store(state).__class__.__name__},
    }


def _agent_store(state: ApiState) -> AgentStore:
    if state.agent_store is None:
        state.agent_store = InMemoryAgentStore()
    return state.agent_store


def _require_agent_prompt_activator(
    state: ApiState,
    *,
    x_user_id: str | None,
    x_role: str | None,
    attempted_action: str,
) -> AuthenticatedUser:
    user = require_permission(
        state,
        permission=Permission.MANAGE_AGENTS,
        x_user_id=x_user_id,
        x_role=x_role,
        attempted_action=attempted_action,
    )
    if user.role.value in AGENT_PROMPT_ACTIVATION_ROLES:
        return user

    record_operation(
        state,
        "authorization-denied",
        {
            "attempted_action": attempted_action,
            "permission": "review_agent_prompts",
            "user_identifier": user.user_identifier,
            "role": user.raw_role or user.role.value,
            "effective_role": user.role.value,
            "auth_source": user.auth_source,
            "profile_status": user.profile_status,
            "status_code": 403,
            "reason": "agent prompt activation requires admin or director role",
        },
    )
    raise HTTPException(
        status_code=403,
        detail="agent prompt activation requires admin or director role",
    )


def _default_agent(agent_key: str) -> dict[str, object] | None:
    return next(
        (dict(agent) for agent in combined_agent_payloads([]) if agent["id"] == agent_key),
        None,
    )


def _agent_payload_for_key(state: ApiState, agent_key: str) -> dict[str, object] | None:
    agent = _agent_store(state).get_agent(agent_key)
    if agent is not None:
        return agent
    return _default_agent(agent_key)


def _filter_agents_for_role(
    items: list[dict[str, object]],
    role: str,
) -> list[dict[str, object]]:
    filtered: list[dict[str, object]] = []
    for item in items:
        raw_roles = item.get("allowed_roles")
        if not isinstance(raw_roles, list) or role in {str(value) for value in raw_roles}:
            filtered.append(item)
    return filtered


def _market_installation_inventory(
    items: list[dict[str, object]],
    *,
    user_identifier: str | None,
) -> tuple[list[dict[str, str]], list[dict[str, object]]]:
    if not user_identifier:
        return [], []
    installations: list[dict[str, str]] = []
    issues: list[dict[str, object]] = []
    agents_by_template: dict[str, list[tuple[str, str]]] = {}
    for item in items:
        if str(item.get("created_by") or "") != user_identifier:
            continue
        metadata = item.get("metadata")
        if not isinstance(metadata, dict) or metadata.get("source") != "agent-market":
            continue
        template_id = metadata.get("template_id")
        agent_id = item.get("id")
        if (
            not isinstance(template_id, str)
            or not template_id.strip()
            or not isinstance(agent_id, str)
            or not agent_id
        ):
            continue
        agents_by_template.setdefault(template_id, []).append(
            (agent_id, str(item.get("status") or "active"))
        )
    for template_id, agent_records in agents_by_template.items():
        if len(agent_records) == 1:
            agent_id, status = agent_records[0]
            if status == "active":
                installations.append({"template_id": template_id, "agent_id": agent_id})
            continue
        issues.append(
            {
                "code": "ambiguous-market-installations",
                "template_id": template_id,
                "agent_ids": sorted(agent_id for agent_id, _status in agent_records),
            }
        )
    return installations, issues


def _filter_agents_for_project(
    items: list[dict[str, object]],
    project_name: str | None,
) -> list[dict[str, object]]:
    normalized_project = _normalize_project_name(project_name)
    if not normalized_project:
        return [
            item for item in items if str(item.get("visibility_scope") or "project") != "project"
        ]
    return [
        item
        for item in items
        if str(item.get("visibility_scope") or "project") != "project"
        or str(item.get("project_name") or "").strip() == normalized_project
    ]


def _latest_prompt_version_from_payload(agent: dict[str, object]) -> int:
    raw_versions = agent.get("prompt_versions")
    if not isinstance(raw_versions, list):
        return _int_from_payload(agent.get("prompt_version"), default=1)
    version_numbers = [
        _int_from_payload(item.get("version"), default=0)
        for item in raw_versions
        if isinstance(item, dict)
    ]
    return max(version_numbers, default=_int_from_payload(agent.get("prompt_version"), default=1))


def _int_from_payload(value: object, *, default: int) -> int:
    if isinstance(value, int):
        return value
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


def _enforce_create_project_scope(
    state: ApiState,
    *,
    visibility_scope: str,
    project_name: str,
    request_project_name: str | None,
    attempted_action: str,
) -> None:
    normalized_project = _normalize_project_name(request_project_name)
    if visibility_scope != "project":
        return
    if not normalized_project:
        _record_agent_scope_denied(
            state,
            agent_id=None,
            agent_project_name=project_name,
            request_project_name="",
            attempted_action=attempted_action,
        )
        raise HTTPException(
            status_code=403,
            detail="agent project scope requires current project",
        )
    if project_name.strip() == normalized_project:
        return
    _record_agent_scope_denied(
        state,
        agent_id=None,
        agent_project_name=project_name,
        request_project_name=normalized_project,
        attempted_action=attempted_action,
    )
    raise HTTPException(
        status_code=403,
        detail="agent project scope does not match current project",
    )


def _enforce_agent_project_scope(
    state: ApiState,
    agent: dict[str, object],
    project_name: str | None,
    *,
    attempted_action: str,
) -> None:
    normalized_project = _normalize_project_name(project_name)
    if str(agent.get("visibility_scope") or "project") != "project":
        return
    agent_project_name = str(agent.get("project_name") or "").strip()
    if not normalized_project:
        _record_agent_scope_denied(
            state,
            agent_id=str(agent.get("id") or ""),
            agent_project_name=agent_project_name,
            request_project_name="",
            attempted_action=attempted_action,
        )
        raise HTTPException(
            status_code=403,
            detail="agent project scope requires current project",
        )
    if agent_project_name == normalized_project:
        return
    _record_agent_scope_denied(
        state,
        agent_id=str(agent.get("id") or ""),
        agent_project_name=agent_project_name,
        request_project_name=normalized_project,
        attempted_action=attempted_action,
    )
    raise HTTPException(
        status_code=403,
        detail="agent project scope does not match current project",
    )


def _record_agent_scope_denied(
    state: ApiState,
    *,
    agent_id: str | None,
    agent_project_name: str,
    request_project_name: str,
    attempted_action: str,
) -> None:
    record_operation(
        state,
        "agent-project-scope-denied",
        {
            "agent_id": agent_id,
            "agent_project_name": agent_project_name,
            "request_project_name": request_project_name,
            "attempted_action": attempted_action,
        },
    )


def _normalize_project_name(project_name: str | None) -> str | None:
    if project_name is None:
        return None
    normalized = urllib.parse.unquote(project_name.strip())
    return normalized or None
