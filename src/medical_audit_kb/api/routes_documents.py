from __future__ import annotations

import os
from typing import Annotated, Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from medical_audit_kb.api.app import ApiState, PreviewReference, get_api_state, record_operation
from medical_audit_kb.api.auth import (
    HospitalRole,
    Permission,
    normalize_hospital_role,
    resolve_authenticated_user,
    user_has_permission,
)
from medical_audit_kb.api.document_permissions import (
    can_read_all_personal_uploads,
    document_permissions_for_role,
)
from medical_audit_kb.api.document_upload_governance import (
    apply_governance_check_result,
    apply_manual_index_decision,
)
from medical_audit_kb.api.document_upload_ingestion import (
    DocumentUploadIngestionError,
)
from medical_audit_kb.api.document_upload_store import document_storage_objects_schema_ready
from medical_audit_kb.api.search_backend_details import safe_search_backend_details
from medical_audit_kb.domain.constants import SourceCollection
from medical_audit_kb.domain.source_collection_registry import SOURCE_COLLECTION_DEFINITIONS
from medical_audit_kb.retrieval.filters import RetrievalFilters
from medical_audit_kb.retrieval.hybrid_search import HybridSearchResult

router = APIRouter(prefix="/documents")

MAX_DOCUMENT_UPLOAD_BYTES = 20 * 1024 * 1024
SUPPORTED_DOCUMENT_EXTENSIONS = {"pdf", "md", "txt", "csv", "xlsx", "xlsm"}
DocumentIndexStatus = Literal["not-indexed", "index-ready", "staged-for-index", "blocked"]
DocumentGovernanceStatus = Literal["pending-review", "approved-for-index", "blocked"]
DocumentSecurityScanStatus = Literal["local-policy-passed", "local-policy-review"]
DocumentDlpStatus = Literal["clear", "needs-review"]
PersonalDocumentIndexStatus = Literal["not-indexed", "indexed", "failed"]
RedactedConfigStatus = Literal["set", "missing", "not_required"]
ReadonlyFeatureStatus = Literal["enabled", "disabled", "not_required"]
ReadonlyEndpointStatus = Literal[
    "available",
    "available_no_event_written",
    "blocked_by_audit_log_side_effect",
]
RequiredReportFieldValue = str | bool | int


class DocumentSourcePermissionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_collection: SourceCollection
    label: str
    scope: str
    access: Literal["read", "explicit-owner-read", "explicit-read-all"]


class DocumentUploadPermissions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    can_upload_personal: bool
    can_read_all_personal_uploads: bool
    can_govern_personal_uploads: bool


class DocumentIndexReadinessCheck(BaseModel):
    model_config = ConfigDict(extra="allow")

    check_type: Literal["virus-scan", "dlp-review", "manual-index-approval"]
    provider: str
    status: Literal["passed", "blocked"]
    blocker: (
        Literal[
            "virus-scan-required",
            "dlp-review-required",
            "manual-index-approval-required",
            "manual-index-approval-rejected",
        ]
        | None
    )
    detail: str


class DocumentIndexReadiness(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["blocked", "ready", "rejected"]
    blockers: list[
        Literal[
            "virus-scan-required",
            "dlp-review-required",
            "manual-index-approval-required",
            "manual-index-approval-rejected",
        ]
    ]
    next_action: Literal[
        "complete-upload-governance",
        "ingest-personal-upload",
        "review-manual-index-rejection",
    ]
    checks: list[DocumentIndexReadinessCheck]


class DocumentPermissionsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str
    source_collections: list[DocumentSourcePermissionItem]
    upload_permissions: DocumentUploadPermissions


class DocumentSourceCollectionMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_count: int | None = None
    chunk_count: int | None = None
    character_count: int | None = None
    linked_app_count: int | None = None


class DocumentSourceCollectionCatalogItem(BaseModel):
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
    metrics: DocumentSourceCollectionMetrics


class DocumentSourceCollectionSearchBackend(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ready: bool
    backend: str
    details: dict[str, object]


class DocumentSourceCollectionCatalogBoundaries(BaseModel):
    model_config = ConfigDict(extra="forbid")

    production_write: bool
    provider_call: bool
    database_write: bool
    object_storage_write: bool
    source: Literal["runtime_state_and_registry_only"]


class DocumentSourceCollectionCatalogResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["document-source-collections-v1"]
    role: str
    items: list[DocumentSourceCollectionCatalogItem]
    search_backend: DocumentSourceCollectionSearchBackend
    upload_permissions: DocumentUploadPermissions
    boundaries: DocumentSourceCollectionCatalogBoundaries


class DocumentSearchItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    chunk_id: str
    title: str
    source_collection: SourceCollection
    source_label: str
    snippet: str
    locator: dict[str, object]
    score: float
    matched_by: list[str]
    index_version_key: str
    source_package_version_key: str
    preview_url: str


class DocumentSearchBoundaries(BaseModel):
    model_config = ConfigDict(extra="forbid")

    production_write: bool
    provider_call: bool
    database_write: bool
    object_storage_write: bool
    query_history_write: bool


class DocumentSearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["document-search-v1"]
    query: str
    effective_source_collections: list[SourceCollection]
    items: list[DocumentSearchItem]
    store: dict[str, object]
    boundaries: DocumentSearchBoundaries


class DocumentUploadItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    extension: str
    size_bytes: int
    size_kb: int
    sha256: str
    storage_path: str
    visibility: Literal["private"]
    status: Literal["retained"]
    created_by: str | None
    created_at: str
    retention_status: Literal["retained"]
    index_status: DocumentIndexStatus
    index_readiness: DocumentIndexReadiness
    governance_status: DocumentGovernanceStatus
    governance_note: str
    governed_by: str | None
    governed_at: str | None
    security_scan_status: DocumentSecurityScanStatus
    security_scan_provider: Literal["local-policy"]
    dlp_status: DocumentDlpStatus
    security_findings: list[str]
    personal_index_status: PersonalDocumentIndexStatus
    personal_indexed_at: str | None
    personal_indexed_by: str | None
    personal_index_chunk_count: int
    personal_index_error: str
    download_url: str


class DocumentUploadListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[DocumentUploadItem]
    store: dict[str, object]
    permissions: DocumentUploadPermissions


class DocumentUploadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item: DocumentUploadItem
    store: dict[str, object]
    permissions: DocumentUploadPermissions


class DocumentUploadIndexIngestionDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["staged-for-index", "already-staged"]
    upload_key: str
    source_collection: str
    source_package_version_key: str
    index_version_key: str
    index_version_status: str
    source_document_id: str
    chunk_count: int
    embedding_count: int
    embedding_provider: str
    embedding_model: str
    embedding_dimension: int
    external_provider_call_performed: bool
    live_retrieval_activated: bool


class DocumentUploadIndexIngestionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item: DocumentUploadItem
    ingestion: DocumentUploadIndexIngestionDetails
    store: dict[str, object]
    permissions: DocumentUploadPermissions


class DocumentUploadGovernanceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    governance_status: DocumentGovernanceStatus
    note: str = Field(default="", max_length=500)


class DocumentGovernanceResultRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_type: Literal["virus-scan", "dlp-review"]
    provider: str = Field(min_length=1, max_length=100)
    status: Literal["passed", "blocked"]
    detail: str = Field(min_length=1, max_length=1000)
    external_job_id: str | None = Field(default=None, max_length=200)
    risk_level: str | None = Field(default=None, max_length=100)
    result_code: str | None = Field(default=None, max_length=100)
    finished_at: str | None = Field(default=None, max_length=100)


class DocumentManualApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["approved", "rejected"]
    note: str = Field(min_length=1, max_length=1000)


class DocumentGovernanceSecretStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    env_name_status: RedactedConfigStatus
    referenced_secret_status: RedactedConfigStatus


class DocumentGovernanceStorageReadonlyStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    cos_bucket_status: RedactedConfigStatus
    cos_region_status: RedactedConfigStatus
    cos_prefix_status: RedactedConfigStatus
    cos_secret_id: DocumentGovernanceSecretStatus
    cos_secret_key: DocumentGovernanceSecretStatus
    cos_sdk_bootstrap_status: ReadonlyFeatureStatus
    record_storage_objects: bool
    signed_url_ttl_seconds: int
    object_retention_days: int
    local_quarantine_retention_days: int


class DocumentGovernanceProviderReadonlyStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    job_endpoint_env_status: RedactedConfigStatus
    job_secret: DocumentGovernanceSecretStatus


class DocumentGovernancePolicyReadonlyStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    virus_scan: DocumentGovernanceProviderReadonlyStatus
    dlp_review: DocumentGovernanceProviderReadonlyStatus
    redaction_rewrite_enabled: bool
    redaction_policy_version_status: RedactedConfigStatus
    redaction_manual_review_required: bool
    governance_audit_event_required: bool


class DocumentGovernanceEndpointReadonlyStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    governance_readonly_endpoint_status: ReadonlyEndpointStatus
    document_storage_objects_schema_ready: bool
    document_upload_list_readonly_status: ReadonlyEndpointStatus
    download_metadata_readonly_status: ReadonlyEndpointStatus
    audit_log_readonly_status: ReadonlyEndpointStatus
    audit_log_store_configured: bool


class DocumentGovernanceReadonlyBoundaries(BaseModel):
    model_config = ConfigDict(extra="forbid")

    production_write: bool
    document_upload_write: bool
    document_upload_list_api_called: bool
    download_metadata_api_called: bool
    audit_log_write_expected: bool
    provider_call: bool
    object_storage_write: bool
    secret_values_reported: bool
    allowed_http_methods: list[Literal["GET"]]
    non_get_http_methods_allowed: bool


class DocumentGovernanceReadonlyStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["readonly_status_available"]
    evidence_grade: Literal["L1-public-or-runtime"]
    storage: DocumentGovernanceStorageReadonlyStatus
    governance: DocumentGovernancePolicyReadonlyStatus
    endpoints: DocumentGovernanceEndpointReadonlyStatus
    required_report_fields: dict[str, RequiredReportFieldValue]
    boundaries: DocumentGovernanceReadonlyBoundaries
    supported_claims: list[str]
    forbidden_claims: list[str]


@router.get("/permissions", response_model=DocumentPermissionsResponse)
def document_permissions(
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> DocumentPermissionsResponse:
    user = resolve_authenticated_user(
        state,
        x_user_id=x_user_id,
        x_role=x_role,
        default_role=HospitalRole.MEMBER,
    )
    role = user.legacy_api_role
    return _permissions_response(role)


@router.get("/source-collections", response_model=DocumentSourceCollectionCatalogResponse)
def document_source_collections(
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> DocumentSourceCollectionCatalogResponse:
    user = resolve_authenticated_user(
        state,
        x_user_id=x_user_id,
        x_role=x_role,
        default_role=HospitalRole.MEMBER,
    )
    role = user.legacy_api_role
    return _source_collection_catalog_response(state=state, role=role)


@router.get("/search", response_model=DocumentSearchResponse)
def document_search(
    state: Annotated[ApiState, Depends(get_api_state)],
    q: Annotated[str, Query(min_length=1, max_length=500)],
    source_collection: Annotated[list[SourceCollection] | None, Query()] = None,
    title_only: bool = False,
    limit: Annotated[int, Query(ge=1, le=20)] = 10,
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> DocumentSearchResponse:
    user = resolve_authenticated_user(
        state,
        x_user_id=x_user_id,
        x_role=x_role,
        default_role=HospitalRole.MEMBER,
    )
    role = user.legacy_api_role
    if state.search_engine is None:
        raise HTTPException(status_code=409, detail="search engine is not initialized")

    effective_source_collections = _effective_document_search_collections(
        role=role,
        requested=tuple(source_collection or ()),
    )
    if not effective_source_collections:
        return DocumentSearchResponse(
            contract_version="document-search-v1",
            query=q,
            effective_source_collections=[],
            items=[],
            store={
                "ready": True,
                "backend": state.search_backend or state.search_engine.__class__.__name__,
            },
            boundaries=DocumentSearchBoundaries(
                production_write=False,
                provider_call=False,
                database_write=False,
                object_storage_write=False,
                query_history_write=False,
            ),
        )
    filters = RetrievalFilters(
        source_collections=effective_source_collections,
        title_only=title_only,
        title_query=q if title_only else "",
        personal_material_created_by=(
            user.user_identifier
            if SourceCollection.PERSONAL_MATERIALS in effective_source_collections
            else ""
        ),
        personal_material_include_all=(
            SourceCollection.PERSONAL_MATERIALS in effective_source_collections
            and can_read_all_personal_uploads(role)
        ),
    )
    results = state.search_engine.search(q, filters=filters, top_k=limit)
    items = [_document_search_item(state, result) for result in results]
    return DocumentSearchResponse(
        contract_version="document-search-v1",
        query=q,
        effective_source_collections=list(effective_source_collections),
        items=items,
        store={
            "ready": True,
            "backend": state.search_backend or state.search_engine.__class__.__name__,
        },
        boundaries=DocumentSearchBoundaries(
            production_write=False,
            provider_call=_document_search_provider_call(state),
            database_write=False,
            object_storage_write=False,
            query_history_write=False,
        ),
    )


@router.get("/governance/status", response_model=DocumentGovernanceReadonlyStatusResponse)
def document_governance_status(
    state: Annotated[ApiState, Depends(get_api_state)],
) -> DocumentGovernanceReadonlyStatusResponse:
    storage = state.settings.document_storage
    governance = state.settings.document_upload_governance
    cos_required = storage.provider == "tencent-cos"
    virus_job_required = governance.virus_scan_provider == "tencent-ci-virus"
    dlp_job_required = governance.dlp_review_provider == "external-dlp"

    storage_status = DocumentGovernanceStorageReadonlyStatus(
        provider=storage.provider,
        cos_bucket_status=_redacted_status(storage.cos_bucket, required=cos_required),
        cos_region_status=_redacted_status(storage.cos_region, required=cos_required),
        cos_prefix_status=_redacted_status(storage.cos_prefix, required=cos_required),
        cos_secret_id=_secret_env_status(storage.cos_secret_id_env, required=cos_required),
        cos_secret_key=_secret_env_status(storage.cos_secret_key_env, required=cos_required),
        cos_sdk_bootstrap_status=_feature_status(
            storage.cos_sdk_bootstrap_enabled,
            required=cos_required,
        ),
        record_storage_objects=storage.record_storage_objects,
        signed_url_ttl_seconds=storage.signed_url_ttl_seconds,
        object_retention_days=storage.object_retention_days,
        local_quarantine_retention_days=storage.local_quarantine_retention_days,
    )
    governance_status = DocumentGovernancePolicyReadonlyStatus(
        virus_scan=DocumentGovernanceProviderReadonlyStatus(
            provider=governance.virus_scan_provider,
            job_endpoint_env_status=_redacted_status(
                governance.virus_scan_job_endpoint_env,
                required=virus_job_required,
            ),
            job_secret=_secret_env_status(
                governance.virus_scan_job_secret_env,
                required=virus_job_required,
            ),
        ),
        dlp_review=DocumentGovernanceProviderReadonlyStatus(
            provider=governance.dlp_review_provider,
            job_endpoint_env_status=_redacted_status(
                governance.dlp_review_job_endpoint_env,
                required=dlp_job_required,
            ),
            job_secret=_secret_env_status(
                governance.dlp_review_job_secret_env,
                required=dlp_job_required,
            ),
        ),
        redaction_rewrite_enabled=governance.redaction_rewrite_enabled,
        redaction_policy_version_status=_redacted_status(
            governance.redaction_policy_version,
            required=governance.redaction_rewrite_enabled,
        ),
        redaction_manual_review_required=governance.redaction_manual_review_required,
        governance_audit_event_required=governance.governance_audit_event_required,
    )
    endpoints = DocumentGovernanceEndpointReadonlyStatus(
        governance_readonly_endpoint_status="available",
        document_storage_objects_schema_ready=document_storage_objects_schema_ready(
            state.settings.database_url
        ),
        document_upload_list_readonly_status="blocked_by_audit_log_side_effect",
        download_metadata_readonly_status="blocked_by_audit_log_side_effect",
        audit_log_readonly_status="available_no_event_written",
        audit_log_store_configured=state.audit_log_store is not None,
    )
    return DocumentGovernanceReadonlyStatusResponse(
        status="readonly_status_available",
        evidence_grade="L1-public-or-runtime",
        storage=storage_status,
        governance=governance_status,
        endpoints=endpoints,
        required_report_fields=_document_governance_required_report_fields(
            storage=storage_status,
            governance=governance_status,
            endpoints=endpoints,
        ),
        boundaries=DocumentGovernanceReadonlyBoundaries(
            production_write=False,
            document_upload_write=False,
            document_upload_list_api_called=False,
            download_metadata_api_called=False,
            audit_log_write_expected=False,
            provider_call=False,
            object_storage_write=False,
            secret_values_reported=False,
            allowed_http_methods=["GET"],
            non_get_http_methods_allowed=False,
        ),
        supported_claims=[
            "This endpoint exposes document-governance readiness fields as redacted statuses.",
            (
                "This endpoint does not list uploads, download metadata, write audit logs, "
                "call providers, or write object storage."
            ),
        ],
        forbidden_claims=[
            (
                "This response proves production was observed unless the endpoint was "
                "called on production."
            ),
            (
                "This response contains COS bucket, region, prefix, policy version, env names, "
                "or secret values."
            ),
            "Upload list and download endpoints are harmless read-only endpoints.",
        ],
    )


@router.get("/uploads", response_model=DocumentUploadListResponse)
def list_document_uploads(
    state: Annotated[ApiState, Depends(get_api_state)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> DocumentUploadListResponse:
    user = resolve_authenticated_user(
        state,
        x_user_id=x_user_id,
        x_role=x_role,
        default_role=HospitalRole.MEMBER,
    )
    role = user.legacy_api_role
    permissions = _upload_permissions(role)
    if state.document_upload_store is None:
        return DocumentUploadListResponse(
            items=[],
            store={"ready": False, "backend": "none"},
            permissions=permissions,
        )

    items = [
        DocumentUploadItem.model_validate(item)
        for item in state.document_upload_store.list_uploads(
            created_by=user.user_identifier,
            include_all=permissions.can_read_all_personal_uploads,
            limit=limit,
        )
    ]
    record_operation(
        state,
        "document-upload-list",
        {
            "count": len(items),
            "limit": limit,
            "user_identifier": user.user_identifier,
            "role": role,
            "effective_role": user.role.value,
            "auth_source": user.auth_source,
            "include_all": permissions.can_read_all_personal_uploads,
        },
    )
    return DocumentUploadListResponse(
        items=items,
        store={"ready": True, "backend": state.document_upload_store.__class__.__name__},
        permissions=permissions,
    )


@router.post("/uploads", response_model=DocumentUploadResponse)
async def upload_document(
    file: Annotated[UploadFile, File()],
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> DocumentUploadResponse:
    user = resolve_authenticated_user(
        state,
        x_user_id=x_user_id,
        x_role=x_role,
        default_role=HospitalRole.MEMBER,
    )
    role = user.legacy_api_role
    permissions = _upload_permissions(role)
    if not user_has_permission(user, Permission.UPLOAD_PERSONAL_DOCUMENT):
        raise HTTPException(status_code=403, detail="upload_personal_document is not allowed")
    if state.document_upload_store is None:
        raise HTTPException(status_code=409, detail="document upload store is not configured")

    file_name = file.filename or "uploaded-document"
    extension = _file_extension(file_name)
    if extension not in SUPPORTED_DOCUMENT_EXTENSIONS:
        raise HTTPException(status_code=422, detail="unsupported document file extension")

    content = await file.read()
    if len(content) > MAX_DOCUMENT_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="uploaded document file is too large")
    if not content:
        raise HTTPException(status_code=422, detail="uploaded document file is empty")

    item = DocumentUploadItem.model_validate(
        state.document_upload_store.add_upload(
            file_name=file_name,
            extension=extension,
            content=content,
            created_by=user.user_identifier,
        )
    )
    record_operation(
        state,
        "document-upload",
        {
            "upload_id": item.id,
            "file_name": item.name,
            "extension": item.extension,
            "size_bytes": item.size_bytes,
            "retention_status": item.retention_status,
            "index_status": item.index_status,
            "governance_status": item.governance_status,
            "security_scan_status": item.security_scan_status,
            "dlp_status": item.dlp_status,
            "security_finding_count": len(item.security_findings),
            "user_identifier": user.user_identifier,
            "role": role,
            "effective_role": user.role.value,
            "auth_source": user.auth_source,
        },
    )
    return DocumentUploadResponse(
        item=item,
        store={"ready": True, "backend": state.document_upload_store.__class__.__name__},
        permissions=permissions,
    )


@router.get("/uploads/{upload_id}/download")
def download_document_upload(
    upload_id: str,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> Response:
    user = resolve_authenticated_user(
        state,
        x_user_id=x_user_id,
        x_role=x_role,
        default_role=HospitalRole.MEMBER,
    )
    role = user.legacy_api_role
    permissions = _upload_permissions(role)
    if state.document_upload_store is None:
        raise HTTPException(status_code=409, detail="document upload store is not configured")

    retained = state.document_upload_store.read_upload_content(upload_id=upload_id)
    if retained is None:
        raise HTTPException(status_code=404, detail="document upload not found")
    item_payload, content = retained
    item = DocumentUploadItem.model_validate(item_payload)
    if not _can_download_upload(
        item=item,
        user_identifier=user.user_identifier,
        permissions=permissions,
    ):
        record_operation(
            state,
            "authorization-denied",
            {
                "attempted_action": "document-upload-download",
                "permission": "owner_or_read_all_personal_uploads",
                "user_identifier": user.user_identifier,
                "role": user.raw_role or role,
                "effective_role": user.role.value,
                "auth_source": user.auth_source,
                "profile_status": user.profile_status,
                "status_code": 404,
                "reason": "document upload download is not visible for this user",
            },
        )
        raise HTTPException(status_code=404, detail="document upload not found")

    record_operation(
        state,
        "document-upload-download",
        {
            "upload_id": item.id,
            "extension": item.extension,
            "size_bytes": item.size_bytes,
            "security_scan_status": item.security_scan_status,
            "dlp_status": item.dlp_status,
            "user_identifier": user.user_identifier,
            "role": role,
            "effective_role": user.role.value,
            "auth_source": user.auth_source,
            "owner": item.created_by,
        },
    )
    return Response(
        content=content,
        media_type=_download_media_type(item.extension),
        headers={
            "Content-Disposition": (
                f"attachment; filename*=UTF-8''{quote(_safe_download_filename(item.name))}"
            ),
            "X-Document-Upload-Id": item.id,
            "X-Document-Security-Scan": item.security_scan_status,
            "X-Document-DLP-Status": item.dlp_status,
        },
    )


@router.post("/uploads/{upload_id}/governance", response_model=DocumentUploadResponse)
def update_document_upload_governance(
    upload_id: str,
    payload: DocumentUploadGovernanceRequest,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> DocumentUploadResponse:
    user = resolve_authenticated_user(
        state,
        x_user_id=x_user_id,
        x_role=x_role,
        default_role=HospitalRole.MEMBER,
    )
    role = user.legacy_api_role
    permissions = _upload_permissions(role)
    if not permissions.can_govern_personal_uploads:
        record_operation(
            state,
            "authorization-denied",
            {
                "attempted_action": "document-upload-governance-update",
                "permission": "manage_index_or_read_all_personal_uploads",
                "user_identifier": user.user_identifier,
                "role": user.raw_role or role,
                "effective_role": user.role.value,
                "auth_source": user.auth_source,
                "profile_status": user.profile_status,
                "status_code": 403,
                "reason": "document upload governance requires admin, technician, or director role",
            },
        )
        raise HTTPException(status_code=403, detail="document upload governance is not allowed")
    if state.document_upload_store is None:
        raise HTTPException(status_code=409, detail="document upload store is not configured")

    current_payload = state.document_upload_store.get_upload(upload_id=upload_id)
    if current_payload is None:
        raise HTTPException(status_code=404, detail="document upload not found")
    current_item = DocumentUploadItem.model_validate(current_payload)
    if payload.governance_status == "approved-for-index" and not _is_security_cleared(current_item):
        record_operation(
            state,
            "document-upload-governance-blocked",
            {
                "upload_id": current_item.id,
                "requested_governance_status": payload.governance_status,
                "security_scan_status": current_item.security_scan_status,
                "dlp_status": current_item.dlp_status,
                "security_finding_count": len(current_item.security_findings),
                "user_identifier": user.user_identifier,
                "role": role,
                "effective_role": user.role.value,
                "auth_source": user.auth_source,
            },
        )
        raise HTTPException(
            status_code=409,
            detail="document upload security review is required before index approval",
        )

    item_payload = state.document_upload_store.update_governance(
        upload_id=upload_id,
        governance_status=payload.governance_status,
        index_status=_index_status_for_governance(payload.governance_status),
        governed_by=user.user_identifier,
        governance_note=payload.note.strip(),
    )
    if item_payload is None:
        raise HTTPException(status_code=404, detail="document upload not found")

    item = DocumentUploadItem.model_validate(item_payload)
    record_operation(
        state,
        "document-upload-governance-update",
        {
            "upload_id": item.id,
            "governance_status": item.governance_status,
            "index_status": item.index_status,
            "governed_by": user.user_identifier,
            "user_identifier": user.user_identifier,
            "role": role,
            "effective_role": user.role.value,
            "auth_source": user.auth_source,
        },
    )
    return DocumentUploadResponse(
        item=item,
        store={"ready": True, "backend": state.document_upload_store.__class__.__name__},
        permissions=permissions,
    )


@router.post(
    "/uploads/{upload_id}/index-readiness/governance-result",
    response_model=DocumentUploadResponse,
)
def update_document_upload_governance_result(
    upload_id: str,
    payload: DocumentGovernanceResultRequest,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> DocumentUploadResponse:
    user = resolve_authenticated_user(
        state,
        x_user_id=x_user_id,
        x_role=x_role,
        default_role=HospitalRole.MEMBER,
    )
    role = user.legacy_api_role
    permissions = _upload_permissions(role)
    if not _can_update_index_readiness(role):
        record_operation(
            state,
            "document-upload-governance-result-access-denied",
            {
                "upload_id": upload_id,
                "check_type": payload.check_type,
                "provider": payload.provider,
                "user_identifier": user.user_identifier,
                "role": user.raw_role or role,
                "effective_role": user.role.value,
                "auth_source": user.auth_source,
                "status_code": 403,
                "reason": (
                    "document upload governance result update requires "
                    "department-head or system-admin role"
                ),
            },
        )
        raise HTTPException(
            status_code=403,
            detail=(
                "document upload governance result update requires "
                "department-head or system-admin role"
            ),
        )
    if state.document_upload_store is None:
        raise HTTPException(status_code=409, detail="document upload store is not configured")

    current_payload = state.document_upload_store.get_upload(upload_id=upload_id)
    if current_payload is None:
        raise HTTPException(status_code=404, detail="document upload not found")
    current_item = DocumentUploadItem.model_validate(current_payload)
    readiness = apply_governance_check_result(
        current_item.index_readiness.model_dump(mode="json"),
        check_type=payload.check_type,
        provider=payload.provider,
        status=payload.status,
        detail=payload.detail,
        external_job_id=payload.external_job_id,
        risk_level=payload.risk_level,
        result_code=payload.result_code,
        finished_at=payload.finished_at,
    )
    updated_payload = state.document_upload_store.update_index_readiness(
        upload_id=upload_id,
        index_readiness=readiness,
    )
    if updated_payload is None:
        raise HTTPException(status_code=404, detail="document upload not found")

    item = DocumentUploadItem.model_validate(updated_payload)
    record_operation(
        state,
        "document-upload-governance-result-update",
        {
            "upload_id": item.id,
            "check_type": payload.check_type,
            "provider": payload.provider,
            "status": payload.status,
            "result_code": payload.result_code,
            "external_job_id": payload.external_job_id,
            "readiness_status": item.index_readiness.status,
            "blockers": item.index_readiness.blockers,
            "user_identifier": user.user_identifier,
            "role": role,
            "effective_role": user.role.value,
            "auth_source": user.auth_source,
        },
    )
    return DocumentUploadResponse(
        item=item,
        store={"ready": True, "backend": state.document_upload_store.__class__.__name__},
        permissions=permissions,
    )


@router.post(
    "/uploads/{upload_id}/index-readiness/manual-approval",
    response_model=DocumentUploadResponse,
)
def update_document_upload_manual_approval(
    upload_id: str,
    payload: DocumentManualApprovalRequest,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> DocumentUploadResponse:
    user = resolve_authenticated_user(
        state,
        x_user_id=x_user_id,
        x_role=x_role,
        default_role=HospitalRole.MEMBER,
    )
    role = user.legacy_api_role
    permissions = _upload_permissions(role)
    if not _can_update_index_readiness(role):
        record_operation(
            state,
            "document-upload-index-approval-access-denied",
            {
                "upload_id": upload_id,
                "decision": payload.decision,
                "user_identifier": user.user_identifier,
                "role": user.raw_role or role,
                "effective_role": user.role.value,
                "auth_source": user.auth_source,
                "status_code": 403,
                "reason": (
                    "document upload manual approval requires "
                    "department-head or system-admin role"
                ),
            },
        )
        raise HTTPException(
            status_code=403,
            detail="document upload manual approval requires department-head or system-admin role",
        )
    if state.document_upload_store is None:
        raise HTTPException(status_code=409, detail="document upload store is not configured")

    current_payload = state.document_upload_store.get_upload(upload_id=upload_id)
    if current_payload is None:
        raise HTTPException(status_code=404, detail="document upload not found")
    current_item = DocumentUploadItem.model_validate(current_payload)
    readiness = apply_manual_index_decision(
        current_item.index_readiness.model_dump(mode="json"),
        decision=payload.decision,
        actor=user.user_identifier,
        note=payload.note.strip(),
    )
    updated_payload = state.document_upload_store.update_index_readiness(
        upload_id=upload_id,
        index_readiness=readiness,
    )
    if updated_payload is None:
        raise HTTPException(status_code=404, detail="document upload not found")

    item = DocumentUploadItem.model_validate(updated_payload)
    record_operation(
        state,
        "document-upload-index-readiness-update",
        {
            "upload_id": item.id,
            "decision": payload.decision,
            "readiness_status": item.index_readiness.status,
            "next_action": item.index_readiness.next_action,
            "blockers": item.index_readiness.blockers,
            "index_status": item.index_status,
            "user_identifier": user.user_identifier,
            "role": role,
            "effective_role": user.role.value,
            "auth_source": user.auth_source,
        },
    )
    return DocumentUploadResponse(
        item=item,
        store={"ready": True, "backend": state.document_upload_store.__class__.__name__},
        permissions=permissions,
    )


@router.post(
    "/uploads/{upload_id}/index-ingestion",
    response_model=DocumentUploadIndexIngestionResponse,
)
def ingest_document_upload_index(
    upload_id: str,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> DocumentUploadIndexIngestionResponse:
    user = resolve_authenticated_user(
        state,
        x_user_id=x_user_id,
        x_role=x_role,
        default_role=HospitalRole.MEMBER,
    )
    role = user.legacy_api_role
    permissions = _upload_permissions(role)
    if state.document_upload_store is None:
        raise HTTPException(status_code=409, detail="document upload store is not configured")
    if not permissions.can_govern_personal_uploads:
        record_operation(
            state,
            "authorization-denied",
            {
                "attempted_action": "document-upload-index-ingestion",
                "permission": "govern_personal_uploads",
                "upload_id": upload_id,
                "user_identifier": user.user_identifier,
                "role": user.raw_role or role,
                "effective_role": user.role.value,
                "auth_source": user.auth_source,
                "profile_status": user.profile_status,
                "status_code": 403,
                "reason": "document upload index ingestion requires governance role",
            },
        )
        raise HTTPException(
            status_code=403,
            detail="document upload index ingestion requires governance role",
        )
    if state.document_upload_indexer is None:
        record_operation(
            state,
            "document-upload-index-ingestion-blocked",
            {
                "upload_id": upload_id,
                "user_identifier": user.user_identifier,
                "role": role,
                "effective_role": user.role.value,
                "auth_source": user.auth_source,
                "status_code": 409,
                "reason": "document-upload-indexing-disabled",
            },
        )
        raise HTTPException(status_code=409, detail="document upload indexing is not enabled")

    try:
        result = state.document_upload_indexer.ingest_upload(
            upload_id,
            actor=user.user_identifier,
        )
    except DocumentUploadIngestionError as exc:
        record_operation(
            state,
            "document-upload-index-ingestion-blocked",
            {
                "upload_id": upload_id,
                "user_identifier": user.user_identifier,
                "role": role,
                "effective_role": user.role.value,
                "auth_source": user.auth_source,
                "status_code": exc.status_code,
                "reason": exc.reason,
                **exc.payload,
            },
        )
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    updated = state.document_upload_store.get_upload(upload_id=upload_id)
    if updated is None:
        raise HTTPException(status_code=404, detail="document upload not found")
    item = DocumentUploadItem.model_validate(updated)
    ingestion = DocumentUploadIndexIngestionDetails.model_validate(result.to_dict())
    record_operation(
        state,
        "document-upload-index-ingestion",
        {
            "upload_id": item.id,
            "index_status": item.index_status,
            "user_identifier": user.user_identifier,
            "role": role,
            "effective_role": user.role.value,
            "auth_source": user.auth_source,
            **ingestion.model_dump(),
        },
    )
    return DocumentUploadIndexIngestionResponse(
        item=item,
        ingestion=ingestion,
        store={"ready": True, "backend": state.document_upload_store.__class__.__name__},
        permissions=permissions,
    )


@router.post("/uploads/{upload_id}/index", response_model=DocumentUploadResponse)
def index_document_upload(
    upload_id: str,
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> DocumentUploadResponse:
    user = resolve_authenticated_user(
        state,
        x_user_id=x_user_id,
        x_role=x_role,
        default_role=HospitalRole.MEMBER,
    )
    role = user.legacy_api_role
    permissions = _upload_permissions(role)
    if state.document_upload_store is None:
        raise HTTPException(status_code=409, detail="document upload store is not configured")

    current_payload = state.document_upload_store.get_upload(upload_id=upload_id)
    if current_payload is None:
        raise HTTPException(status_code=404, detail="document upload not found")
    current_item = DocumentUploadItem.model_validate(current_payload)
    if not _can_index_upload(
        item=current_item,
        user_identifier=user.user_identifier,
        permissions=permissions,
    ):
        record_operation(
            state,
            "authorization-denied",
            {
                "attempted_action": "document-upload-index",
                "permission": "owner_or_govern_personal_uploads",
                "user_identifier": user.user_identifier,
                "role": user.raw_role or role,
                "effective_role": user.role.value,
                "auth_source": user.auth_source,
                "profile_status": user.profile_status,
                "status_code": 403,
                "reason": "document upload index requires owner or governance role",
            },
        )
        raise HTTPException(status_code=403, detail="document upload index is not allowed")
    if current_item.governance_status != "approved-for-index":
        raise HTTPException(
            status_code=409,
            detail="document upload must be approved before personal index",
        )
    if current_item.index_status != "index-ready":
        raise HTTPException(
            status_code=409,
            detail="document upload is not ready for personal index",
        )
    if not _is_security_cleared(current_item):
        raise HTTPException(
            status_code=409,
            detail="document upload security review is required before personal index",
        )

    item_payload = state.document_upload_store.index_upload(
        upload_id=upload_id,
        indexed_by=user.user_identifier,
    )
    if item_payload is None:
        raise HTTPException(status_code=404, detail="document upload not found")

    item = DocumentUploadItem.model_validate(item_payload)
    record_operation(
        state,
        "document-upload-index",
        {
            "upload_id": item.id,
            "personal_index_status": item.personal_index_status,
            "personal_index_chunk_count": item.personal_index_chunk_count,
            "personal_index_error": item.personal_index_error,
            "indexed_by": user.user_identifier,
            "user_identifier": user.user_identifier,
            "role": role,
            "effective_role": user.role.value,
            "auth_source": user.auth_source,
        },
    )
    return DocumentUploadResponse(
        item=item,
        store={"ready": True, "backend": state.document_upload_store.__class__.__name__},
        permissions=permissions,
    )


def _permissions_response(role: str) -> DocumentPermissionsResponse:
    return DocumentPermissionsResponse(
        role=role,
        source_collections=[
            DocumentSourcePermissionItem.model_validate(permission.to_payload())
            for permission in document_permissions_for_role(role)
        ],
        upload_permissions=_upload_permissions(role),
    )


def _effective_document_search_collections(
    *,
    role: str,
    requested: tuple[SourceCollection, ...],
) -> tuple[SourceCollection, ...]:
    allowed = {
        permission.source_collection
        for permission in document_permissions_for_role(role)
    }
    if requested:
        return tuple(collection for collection in requested if collection in allowed)
    return tuple(sorted(allowed, key=lambda item: item.value))


def _document_search_item(
    state: ApiState,
    result: HybridSearchResult,
) -> DocumentSearchItem:
    collection = _source_collection_from_result(result)
    title = _document_result_title(result)
    snippet = _document_result_snippet(result.chunk.text)
    state.preview_references[result.chunk.chunk_id] = PreviewReference(
        locator=result.chunk.locator,
        citation_text=snippet,
    )
    return DocumentSearchItem(
        id=str(result.chunk.chunk_id),
        chunk_id=str(result.chunk.chunk_id),
        title=title,
        source_collection=collection,
        source_label=_source_collection_label(collection),
        snippet=snippet,
        locator=result.chunk.locator,
        score=round(result.score, 6),
        matched_by=list(result.matched_by),
        index_version_key=result.chunk.index_version_key,
        source_package_version_key=result.chunk.source_package_version_key,
        preview_url=f"/api/v1/preview/{result.chunk.chunk_id}",
    )


def _source_collection_from_result(result: HybridSearchResult) -> SourceCollection:
    value = result.chunk.metadata.get("source_collection")
    if isinstance(value, str):
        try:
            return SourceCollection(value)
        except ValueError:
            pass
    return SourceCollection.MEDICAL_INSURANCE_LAWS


def _source_collection_label(collection: SourceCollection) -> str:
    for definition in SOURCE_COLLECTION_DEFINITIONS:
        if definition.collection == collection:
            return definition.label
    return collection.value


def _document_result_title(result: HybridSearchResult) -> str:
    for key in ("title", "document_title", "file_name"):
        value = result.chunk.metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    title_path = result.chunk.metadata.get("title_path")
    if isinstance(title_path, list):
        for value in reversed(title_path):
            if isinstance(value, str) and value.strip():
                return value.strip()
    source_path = result.chunk.metadata.get("source_path")
    if isinstance(source_path, str) and source_path.strip():
        return source_path.rsplit("/", 1)[-1]
    return "未命名文档"


def _document_result_snippet(text: str) -> str:
    compact = " ".join(text.split())
    if len(compact) <= 180:
        return compact
    return f"{compact[:180]}..."


def _document_search_provider_call(state: ApiState) -> bool:
    provider = state.search_backend_details.get("embedding_provider")
    return isinstance(provider, str) and provider not in {"", "fake", "deterministic-fake"}


def _source_collection_catalog_response(
    *,
    state: ApiState,
    role: str,
) -> DocumentSourceCollectionCatalogResponse:
    permissions = {
        permission.source_collection: permission
        for permission in document_permissions_for_role(role)
    }
    items: list[DocumentSourceCollectionCatalogItem] = []
    for definition in SOURCE_COLLECTION_DEFINITIONS:
        permission = permissions.get(definition.collection)
        if permission is None:
            continue
        items.append(
            DocumentSourceCollectionCatalogItem(
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
                queryable=definition.product_queryable and state.search_engine is not None,
                metrics=_source_collection_metrics(definition.collection, state),
            )
        )
    return DocumentSourceCollectionCatalogResponse(
        contract_version="document-source-collections-v1",
        role=role,
        items=items,
        search_backend=DocumentSourceCollectionSearchBackend(
            ready=state.search_engine is not None,
            backend=state.search_backend,
            details=safe_search_backend_details(state.search_backend_details),
        ),
        upload_permissions=_upload_permissions(role),
        boundaries=DocumentSourceCollectionCatalogBoundaries(
            production_write=False,
            provider_call=False,
            database_write=False,
            object_storage_write=False,
            source="runtime_state_and_registry_only",
        ),
    )


def _source_collection_metrics(
    collection: SourceCollection,
    state: ApiState,
) -> DocumentSourceCollectionMetrics:
    details = state.search_backend_details
    detail_collection = details.get("source_collection")
    chunk_count = _int_or_none(details.get("matching_embedding_count"))
    if detail_collection != collection.value:
        chunk_count = None
    return DocumentSourceCollectionMetrics(
        chunk_count=chunk_count,
        linked_app_count=1,
    )


def _int_or_none(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def _upload_permissions(role: str) -> DocumentUploadPermissions:
    return DocumentUploadPermissions(
        can_upload_personal=True,
        can_read_all_personal_uploads=can_read_all_personal_uploads(role),
        can_govern_personal_uploads=_can_govern_personal_uploads(role),
    )


def _redacted_status(value: str | None, *, required: bool) -> RedactedConfigStatus:
    if not required:
        return "not_required"
    if value is None:
        return "missing"
    return "set" if value.strip() else "missing"


def _secret_env_status(
    env_name: str | None,
    *,
    required: bool,
) -> DocumentGovernanceSecretStatus:
    env_name_status = _redacted_status(env_name, required=required)
    if env_name_status != "set":
        referenced_secret_status: RedactedConfigStatus = env_name_status
    else:
        referenced_secret_status = "set" if os.getenv(env_name or "", "").strip() else "missing"
    return DocumentGovernanceSecretStatus(
        env_name_status=env_name_status,
        referenced_secret_status=referenced_secret_status,
    )


def _feature_status(value: bool, *, required: bool) -> ReadonlyFeatureStatus:
    if not required:
        return "not_required"
    return "enabled" if value else "disabled"


def _document_governance_required_report_fields(
    *,
    storage: DocumentGovernanceStorageReadonlyStatus,
    governance: DocumentGovernancePolicyReadonlyStatus,
    endpoints: DocumentGovernanceEndpointReadonlyStatus,
) -> dict[str, RequiredReportFieldValue]:
    return {
        "document_storage_provider": storage.provider,
        "cos_bucket_status": storage.cos_bucket_status,
        "cos_region_status": storage.cos_region_status,
        "cos_prefix_status": storage.cos_prefix_status,
        "cos_secret_id_env_name_status": storage.cos_secret_id.env_name_status,
        "cos_secret_key_env_name_status": storage.cos_secret_key.env_name_status,
        "cos_sdk_bootstrap_status": storage.cos_sdk_bootstrap_status,
        "record_storage_objects": storage.record_storage_objects,
        "signed_url_ttl_seconds": storage.signed_url_ttl_seconds,
        "object_retention_days": storage.object_retention_days,
        "local_quarantine_retention_days": storage.local_quarantine_retention_days,
        "virus_scan_provider": governance.virus_scan.provider,
        "virus_scan_job_endpoint_env_status": governance.virus_scan.job_endpoint_env_status,
        "virus_scan_job_secret_env_status": governance.virus_scan.job_secret.env_name_status,
        "dlp_review_provider": governance.dlp_review.provider,
        "dlp_review_job_endpoint_env_status": governance.dlp_review.job_endpoint_env_status,
        "dlp_review_job_secret_env_status": governance.dlp_review.job_secret.env_name_status,
        "redaction_rewrite_enabled": governance.redaction_rewrite_enabled,
        "redaction_policy_version_status": governance.redaction_policy_version_status,
        "redaction_manual_review_required": governance.redaction_manual_review_required,
        "governance_audit_event_required": governance.governance_audit_event_required,
        "document_storage_objects_schema_ready": endpoints.document_storage_objects_schema_ready,
        "document_upload_list_readonly_status": endpoints.document_upload_list_readonly_status,
        "governance_readonly_endpoint_status": endpoints.governance_readonly_endpoint_status,
        "download_metadata_readonly_status": endpoints.download_metadata_readonly_status,
        "audit_log_readonly_status": endpoints.audit_log_readonly_status,
    }


def _file_extension(file_name: str) -> str:
    if "." not in file_name:
        return ""
    return file_name.rsplit(".", maxsplit=1)[-1].lower()


def _can_govern_personal_uploads(role: str) -> bool:
    try:
        normalized = normalize_hospital_role(role, default=HospitalRole.MEMBER)
    except HTTPException:
        return False
    return normalized in {HospitalRole.ADMIN, HospitalRole.TECHNICIAN, HospitalRole.DIRECTOR}


def _can_update_index_readiness(role: str) -> bool:
    try:
        normalized = normalize_hospital_role(role, default=HospitalRole.MEMBER)
    except HTTPException:
        return False
    return normalized in {HospitalRole.ADMIN, HospitalRole.DIRECTOR}


def _index_status_for_governance(status: DocumentGovernanceStatus) -> DocumentIndexStatus:
    if status == "approved-for-index":
        return "index-ready"
    if status == "blocked":
        return "blocked"
    return "not-indexed"


def _can_download_upload(
    *,
    item: DocumentUploadItem,
    user_identifier: str,
    permissions: DocumentUploadPermissions,
) -> bool:
    return item.created_by == user_identifier or permissions.can_read_all_personal_uploads


def _can_index_upload(
    *,
    item: DocumentUploadItem,
    user_identifier: str,
    permissions: DocumentUploadPermissions,
) -> bool:
    return item.created_by == user_identifier or permissions.can_govern_personal_uploads


def _is_security_cleared(item: DocumentUploadItem) -> bool:
    return item.security_scan_status == "local-policy-passed" and item.dlp_status == "clear"


def _download_media_type(extension: str) -> str:
    return {
        "pdf": "application/pdf",
        "md": "text/markdown; charset=utf-8",
        "txt": "text/plain; charset=utf-8",
        "csv": "text/csv; charset=utf-8",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "xlsm": "application/vnd.ms-excel.sheet.macroEnabled.12",
    }.get(extension, "application/octet-stream")


def _safe_download_filename(file_name: str) -> str:
    cleaned = file_name.replace("/", "_").replace("\\", "_").strip()
    return cleaned or "document-upload"
