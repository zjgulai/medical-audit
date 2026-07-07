from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Literal, cast

import psycopg
from fastapi import APIRouter, Depends, Header
from psycopg.rows import dict_row
from pydantic import BaseModel, ConfigDict

from medical_audit_kb.api.app import ApiState, get_api_state
from medical_audit_kb.api.auth import HospitalRole, resolve_authenticated_user
from medical_audit_kb.api.document_permissions import document_permissions_for_role
from medical_audit_kb.api.postgres_status import psycopg_database_url
from medical_audit_kb.domain.constants import SourceCollection
from medical_audit_kb.domain.source_collection_registry import SOURCE_COLLECTION_DEFINITIONS

router = APIRouter(prefix="/knowledge-base")


class KnowledgeBaseCatalogMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_count: int
    chunk_count: int
    embedding_count: int
    active_embedding_count: int
    candidate_chunk_count: int
    character_count: int
    linked_app_count: int


class KnowledgeBaseCatalogIndex(BaseModel):
    model_config = ConfigDict(extra="forbid")

    latest_version_key: str | None
    latest_status: str | None
    search_backend_ready: bool
    queryable: bool


class KnowledgeBaseCatalogItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_collection: SourceCollection
    label: str
    scope: str
    phase: str
    domain: str
    evidence_group: str
    description: str
    audit_hint: str
    access: Literal["read", "explicit-owner-read", "explicit-read-all"]
    product_queryable: bool
    queryable: bool
    metrics: KnowledgeBaseCatalogMetrics
    index: KnowledgeBaseCatalogIndex
    actions: dict[str, str]


class KnowledgeBaseCatalogSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_collection_count: int
    queryable_collection_count: int
    total_document_count: int
    total_chunk_count: int
    total_embedding_count: int
    current_search_embedding_count: int
    candidate_chunk_count: int
    domain_counts: dict[str, int]


class KnowledgeBaseCatalogBoundaries(BaseModel):
    model_config = ConfigDict(extra="forbid")

    production_write: bool
    provider_call: bool
    database_write: bool
    object_storage_write: bool
    query_history_write: bool
    source: Literal["runtime_state_and_postgres_catalog", "runtime_state_and_registry_only"]


class KnowledgeBaseCatalogResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["knowledge-base-catalog-v1"]
    role: str
    summary: KnowledgeBaseCatalogSummary
    items: list[KnowledgeBaseCatalogItem]
    search_backend: dict[str, object]
    store: dict[str, object]
    boundaries: KnowledgeBaseCatalogBoundaries


@router.get("/catalog", response_model=KnowledgeBaseCatalogResponse)
def knowledge_base_catalog(
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> KnowledgeBaseCatalogResponse:
    user = resolve_authenticated_user(
        state,
        x_user_id=x_user_id,
        x_role=x_role,
        default_role=HospitalRole.MEMBER,
    )
    return build_knowledge_base_catalog_response(state=state, role=user.legacy_api_role)


def build_knowledge_base_catalog_response(
    *,
    state: ApiState,
    role: str,
) -> KnowledgeBaseCatalogResponse:
    permissions = {
        permission.source_collection: permission
        for permission in document_permissions_for_role(role)
    }
    metrics_by_collection, totals, latest_by_collection, store_backend = _load_catalog_metrics(
        state
    )

    items: list[KnowledgeBaseCatalogItem] = []
    domain_counts: dict[str, int] = {}
    for definition in SOURCE_COLLECTION_DEFINITIONS:
        permission = permissions.get(definition.collection)
        if permission is None:
            continue
        metrics = metrics_by_collection.get(definition.collection, _empty_metrics())
        latest = latest_by_collection.get(definition.collection, {})
        queryable = definition.product_queryable and state.search_engine is not None
        domain_counts[definition.domain] = domain_counts.get(definition.domain, 0) + 1
        items.append(
            KnowledgeBaseCatalogItem(
                source_collection=definition.collection,
                label=definition.label,
                scope=definition.scope,
                phase=definition.phase,
                domain=definition.domain,
                evidence_group=definition.evidence_group,
                description=definition.description,
                audit_hint=definition.audit_hint,
                access=permission.access,
                product_queryable=definition.product_queryable,
                queryable=queryable,
                metrics=metrics,
                index=KnowledgeBaseCatalogIndex(
                    latest_version_key=_str_or_none(latest.get("latest_index_version_key")),
                    latest_status=_str_or_none(latest.get("latest_index_status")),
                    search_backend_ready=state.search_engine is not None,
                    queryable=queryable,
                ),
                actions={
                    "documents": f"/documents?source_collection={definition.collection.value}",
                    "chat": f"/chat?source_collection={definition.collection.value}",
                    "graph": f"/graph?source_collection={definition.collection.value}",
                },
            )
        )

    total_document_count = _total_or_sum(totals, "source_documents", items, "document_count")
    total_chunk_count = _total_or_sum(totals, "document_chunks", items, "chunk_count")
    total_embedding_count = _total_or_sum(totals, "chunk_embeddings", items, "embedding_count")
    current_search_embedding_count = _int_from_mapping(
        state.search_backend_details,
        "matching_embedding_count",
    )
    candidate_chunk_count = sum(item.metrics.candidate_chunk_count for item in items)

    return KnowledgeBaseCatalogResponse(
        contract_version="knowledge-base-catalog-v1",
        role=role,
        summary=KnowledgeBaseCatalogSummary(
            source_collection_count=len(items),
            queryable_collection_count=sum(1 for item in items if item.queryable),
            total_document_count=total_document_count,
            total_chunk_count=total_chunk_count,
            total_embedding_count=total_embedding_count,
            current_search_embedding_count=current_search_embedding_count,
            candidate_chunk_count=candidate_chunk_count,
            domain_counts=domain_counts,
        ),
        items=items,
        search_backend={
            "ready": state.search_engine is not None,
            "backend": state.search_backend,
            "details": _safe_search_backend_details(state.search_backend_details),
        },
        store={"ready": True, "backend": store_backend},
        boundaries=KnowledgeBaseCatalogBoundaries(
            production_write=False,
            provider_call=False,
            database_write=False,
            object_storage_write=False,
            query_history_write=False,
            source=store_backend,
        ),
    )


def _load_catalog_metrics(
    state: ApiState,
) -> tuple[
    dict[SourceCollection, KnowledgeBaseCatalogMetrics],
    dict[str, int],
    dict[SourceCollection, dict[str, object]],
    Literal["runtime_state_and_postgres_catalog", "runtime_state_and_registry_only"],
]:
    metrics_by_collection, latest_by_collection = _metrics_from_runtime_details(
        state.search_backend_details
    )
    totals = _totals_from_runtime_details(state.search_backend_details)
    if metrics_by_collection or totals:
        return (
            metrics_by_collection,
            totals,
            latest_by_collection,
            "runtime_state_and_postgres_catalog",
        )

    if not state.settings.database_url.startswith(("postgresql://", "postgresql+psycopg://")):
        return ({}, {}, {}, "runtime_state_and_registry_only")

    try:
        return (
            *_metrics_from_postgres(state.settings.database_url),
            "runtime_state_and_postgres_catalog",
        )
    except psycopg.Error:
        return ({}, {}, {}, "runtime_state_and_registry_only")


def _metrics_from_runtime_details(
    details: Mapping[str, object],
) -> tuple[
    dict[SourceCollection, KnowledgeBaseCatalogMetrics],
    dict[SourceCollection, dict[str, object]],
]:
    raw_metrics = details.get("collection_metrics")
    if not isinstance(raw_metrics, Mapping):
        return ({}, {})
    metrics_by_collection: dict[SourceCollection, KnowledgeBaseCatalogMetrics] = {}
    latest_by_collection: dict[SourceCollection, dict[str, object]] = {}
    for raw_collection, raw_value in raw_metrics.items():
        if not isinstance(raw_collection, str) or not isinstance(raw_value, Mapping):
            continue
        try:
            collection = SourceCollection(raw_collection)
        except ValueError:
            continue
        metrics_by_collection[collection] = KnowledgeBaseCatalogMetrics(
            document_count=_int_from_mapping(raw_value, "document_count"),
            chunk_count=_int_from_mapping(raw_value, "chunk_count"),
            embedding_count=_int_from_mapping(raw_value, "embedding_count"),
            active_embedding_count=_int_from_mapping(raw_value, "active_embedding_count"),
            candidate_chunk_count=_int_from_mapping(raw_value, "candidate_chunk_count"),
            character_count=_int_from_mapping(raw_value, "character_count"),
            linked_app_count=_int_from_mapping(raw_value, "linked_app_count") or 1,
        )
        latest_by_collection[collection] = dict(raw_value)
    return metrics_by_collection, latest_by_collection


def _totals_from_runtime_details(details: Mapping[str, object]) -> dict[str, int]:
    raw_totals = details.get("postgres_totals")
    if not isinstance(raw_totals, Mapping):
        return {}
    return {
        key: _int_from_mapping(raw_totals, key)
        for key in ("source_documents", "document_chunks", "chunk_embeddings")
    }


def _metrics_from_postgres(
    database_url: str,
) -> tuple[
    dict[SourceCollection, KnowledgeBaseCatalogMetrics],
    dict[str, int],
    dict[SourceCollection, dict[str, object]],
]:
    metrics_by_collection: dict[SourceCollection, KnowledgeBaseCatalogMetrics] = {}
    latest_by_collection: dict[SourceCollection, dict[str, object]] = {}
    totals: dict[str, int] = {}
    with (
        psycopg.connect(psycopg_database_url(database_url), connect_timeout=2) as connection,
        connection.cursor(row_factory=dict_row) as cursor,
    ):
        cursor.execute(
            """
            SELECT
              sd.source_collection,
              COUNT(DISTINCT sd.id)::bigint AS document_count,
              COUNT(DISTINCT dc.id)::bigint AS chunk_count,
              COUNT(DISTINCT ce.id)::bigint AS embedding_count,
              COUNT(DISTINCT ce.id) FILTER (
                WHERE iv.status = 'active'
              )::bigint AS active_embedding_count,
              COALESCE(SUM(LENGTH(dc.text)), 0)::bigint AS character_count
            FROM source_documents sd
            LEFT JOIN document_chunks dc ON dc.source_document_id = sd.id
            LEFT JOIN chunk_embeddings ce ON ce.chunk_id = dc.id
            LEFT JOIN index_versions iv
              ON iv.source_package_version_id = sd.source_package_version_id
            GROUP BY sd.source_collection
            """
        )
        for row in cursor.fetchall():
            collection = _collection_from_row(row.get("source_collection"))
            if collection is None:
                continue
            metrics_by_collection[collection] = KnowledgeBaseCatalogMetrics(
                document_count=_int_value(row.get("document_count")),
                chunk_count=_int_value(row.get("chunk_count")),
                embedding_count=_int_value(row.get("embedding_count")),
                active_embedding_count=_int_value(row.get("active_embedding_count")),
                candidate_chunk_count=0,
                character_count=_int_value(row.get("character_count")),
                linked_app_count=1,
            )

        cursor.execute(
            """
            SELECT
              sd.source_collection AS collection,
              COUNT(DISTINCT dc.id)::bigint AS candidate_chunk_count
            FROM index_versions iv
            JOIN source_documents sd
              ON sd.source_package_version_id = iv.source_package_version_id
            JOIN document_chunks dc
              ON dc.source_document_id = sd.id
            WHERE iv.status = 'candidate'
            GROUP BY sd.source_collection
            """
        )
        for row in cursor.fetchall():
            collection = _collection_from_row(row.get("collection"))
            if collection is None:
                continue
            current = metrics_by_collection.get(collection, _empty_metrics())
            metrics_by_collection[collection] = current.model_copy(
                update={"candidate_chunk_count": _int_value(row.get("candidate_chunk_count"))}
            )

        cursor.execute(
            """
            SELECT DISTINCT ON (sd.source_collection)
              sd.source_collection,
              iv.version_key AS latest_index_version_key,
              iv.status AS latest_index_status
            FROM source_documents sd
            JOIN index_versions iv ON iv.source_package_version_id = sd.source_package_version_id
            ORDER BY sd.source_collection, iv.created_at DESC, iv.version_key DESC
            """
        )
        for row in cursor.fetchall():
            collection = _collection_from_row(row.get("source_collection"))
            if collection is not None:
                latest_by_collection[collection] = dict(row)

        cursor.execute(
            """
            SELECT
              (SELECT COUNT(*) FROM source_documents)::bigint AS source_documents,
              (SELECT COUNT(*) FROM document_chunks)::bigint AS document_chunks,
              (SELECT COUNT(*) FROM chunk_embeddings)::bigint AS chunk_embeddings
            """
        )
        row = cursor.fetchone()
        if row is not None:
            totals = {
                "source_documents": _int_value(row.get("source_documents")),
                "document_chunks": _int_value(row.get("document_chunks")),
                "chunk_embeddings": _int_value(row.get("chunk_embeddings")),
            }
    return metrics_by_collection, totals, latest_by_collection


def _empty_metrics() -> KnowledgeBaseCatalogMetrics:
    return KnowledgeBaseCatalogMetrics(
        document_count=0,
        chunk_count=0,
        embedding_count=0,
        active_embedding_count=0,
        candidate_chunk_count=0,
        character_count=0,
        linked_app_count=1,
    )


def _collection_from_row(value: object) -> SourceCollection | None:
    if not isinstance(value, str):
        return None
    try:
        return SourceCollection(value)
    except ValueError:
        return None


def _int_from_mapping(mapping: Mapping[str, object], key: str) -> int:
    return _int_value(mapping.get(key))


def _int_value(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    return 0


def _str_or_none(value: object) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def _total_or_sum(
    totals: Mapping[str, int],
    total_key: str,
    items: list[KnowledgeBaseCatalogItem],
    metric_key: Literal["document_count", "chunk_count", "embedding_count"],
) -> int:
    if total_key in totals:
        return totals[total_key]
    return sum(cast(int, getattr(item.metrics, metric_key)) for item in items)


def _safe_search_backend_details(details: Mapping[str, object]) -> dict[str, object]:
    safe: dict[str, object] = {}
    for key, value in details.items():
        lowered = key.lower()
        if "secret" in lowered or "token" in lowered or "password" in lowered or "key" in lowered:
            if key == "provider_version":
                safe[key] = value
            else:
                safe[f"{key}_status"] = "set" if value else "missing"
            continue
        safe[key] = value
    return safe
