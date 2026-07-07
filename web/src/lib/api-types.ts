export type SearchBackendDetails = Record<string, unknown> & {
  readonly matching_embedding_count?: number;
};

export type BackendHealthResponse = {
  readonly status: "ok";
  readonly version: string;
  readonly data_root: string;
};

export type SearchBackendStatusResponse = {
  readonly backend: string;
  readonly ready: boolean;
  readonly details?: SearchBackendDetails;
};

export type GraphWorkbenchNodeKind = "项目" | "一级分类" | "知识库" | "文档" | "规则" | "疑点" | "复核" | "报告" | "整改";

export type GraphWorkbenchNode = {
  readonly id: string;
  readonly label: string;
  readonly kind: GraphWorkbenchNodeKind;
  readonly status: "已归集" | "可引用" | "待复核" | "门禁中" | "跟踪中" | "待接入";
  readonly description: string;
  readonly metric: string;
  readonly href: string;
  readonly x: number;
  readonly y: number;
};

export type GraphWorkbenchRelation = {
  readonly id: string;
  readonly sourceId: string;
  readonly targetId: string;
  readonly source: string;
  readonly relation: string;
  readonly target: string;
  readonly evidence: string;
  readonly strength: "强" | "中" | "待补";
};

export type GraphWorkbenchResponse = {
  readonly format: "graph-workbench-v1";
  readonly generated_at: string;
  readonly graph_id: string;
  readonly graph_title: string;
  readonly graph_scope: string;
  readonly nodes: readonly GraphWorkbenchNode[];
  readonly relations: readonly GraphWorkbenchRelation[];
  readonly metrics: {
    readonly node_count: number;
    readonly node_kind_count: number;
    readonly node_kind_counts: Record<GraphWorkbenchNodeKind, number>;
    readonly relation_count: number;
    readonly strong_relation_count: number;
    readonly pending_relation_count: number;
  };
  readonly evidence_grade: string;
  readonly production_side_effect: "none" | string;
  readonly store: {
    readonly ready: boolean;
    readonly backend: string;
  };
};

export type RuleLibraryApiItem = {
  readonly id: string;
  readonly code: string;
  readonly name: string;
  readonly domain: "收费明细" | "医保目录" | "处方用药" | "参保身份";
  readonly status: "已启用" | "待补字段" | "待复核" | "只读";
  readonly sourceCollection: string;
  readonly evidenceScope: string;
  readonly evidenceCount: number;
  readonly findingCount: number;
  readonly owner: "内审部" | "业务专家" | "信息科";
  readonly updatedAt: string;
  readonly href: string;
  readonly chatHref: string;
};

export type RuleSourceCoverageApiItem = {
  readonly id: string;
  readonly name: string;
  readonly sourceCollection: string;
  readonly ruleCount: number;
  readonly indexStatus: "可引用" | "待同步" | "只读";
  readonly health: string;
  readonly href: string;
};

export type RuleRunSnapshotApiItem = {
  readonly id: string;
  readonly ruleCode: string;
  readonly inputTable: string;
  readonly lastRunAt: string;
  readonly hitCount: number;
  readonly linkedFinding: string;
  readonly nextAction: string;
};

export type RuleControlGateApiItem = {
  readonly id: string;
  readonly label: string;
  readonly status: "通过" | "阻断" | "待人工确认";
  readonly detail: string;
  readonly owner: "审计员" | "业务专家" | "信息科";
};

export type RulesWorkbenchResponse = {
  readonly format: "rules-workbench-v1";
  readonly generated_at: string;
  readonly ruleset_id: string;
  readonly ruleset_title: string;
  readonly ruleset_scope: string;
  readonly rule_library_items: readonly RuleLibraryApiItem[];
  readonly source_coverages: readonly RuleSourceCoverageApiItem[];
  readonly run_snapshots: readonly RuleRunSnapshotApiItem[];
  readonly control_gates: readonly RuleControlGateApiItem[];
  readonly metrics: {
    readonly rule_count: number;
    readonly enabled_rule_count: number;
    readonly pending_rule_count: number;
    readonly total_finding_count: number;
    readonly blocked_gate_count: number;
    readonly source_count: number;
    readonly run_count: number;
  };
  readonly evidence_grade: string;
  readonly production_side_effect: "none" | string;
  readonly store: {
    readonly ready: boolean;
    readonly backend: string;
  };
};

export type RemediationCaseApiItem = {
  readonly id: string;
  readonly title: string;
  readonly department: string;
  readonly owner: "医保办" | "财务科" | "信息科" | "药剂科";
  readonly status: "待整改" | "整改中" | "待验收" | "已关闭";
  readonly dueDate: string;
  readonly reportNo: string;
  readonly sourceFinding: string;
  readonly progress: number;
  readonly evidenceStatus: "待补证" | "已提交" | "需退回" | "已验收";
  readonly nextAction: string;
  readonly href: string;
};

export type RemediationEvidenceRequestApiItem = {
  readonly id: string;
  readonly title: string;
  readonly linkedCaseId: string;
  readonly kind: "HIS 凭证" | "附件归档" | "负责人确认" | "退费凭证";
  readonly status: "待上传" | "已提交" | "需退回" | "已验收";
  readonly owner: "医保办" | "财务科" | "信息科" | "项目负责人";
  readonly dueDate: string;
  readonly detail: string;
  readonly href: string;
};

export type RemediationClosureGateApiItem = {
  readonly id: string;
  readonly label: string;
  readonly status: "通过" | "阻断" | "待人工确认";
  readonly detail: string;
  readonly owner: "审计员" | "项目负责人" | "信息科";
};

export type RemediationTimelineApiItem = {
  readonly id: string;
  readonly time: string;
  readonly title: string;
  readonly detail: string;
  readonly status: "已记录" | "待处理" | "已阻断";
};

export type RemediationWorkbenchResponse = {
  readonly format: "remediation-workbench-v1";
  readonly generated_at: string;
  readonly workbench_id: string;
  readonly workbench_title: string;
  readonly workbench_scope: string;
  readonly remediation_cases: readonly RemediationCaseApiItem[];
  readonly evidence_requests: readonly RemediationEvidenceRequestApiItem[];
  readonly closure_gates: readonly RemediationClosureGateApiItem[];
  readonly timeline: readonly RemediationTimelineApiItem[];
  readonly metrics: {
    readonly case_count: number;
    readonly active_case_count: number;
    readonly closed_case_count: number;
    readonly pending_evidence_count: number;
    readonly blocked_gate_count: number;
    readonly average_progress: number;
    readonly timeline_count: number;
  };
  readonly evidence_grade: string;
  readonly production_side_effect: "none" | string;
  readonly store: {
    readonly ready: boolean;
    readonly backend: string;
  };
};

export type ArchivePackageApiItem = {
  readonly id: string;
  readonly projectName: string;
  readonly archiveNo: string;
  readonly status: "已归档" | "归档前检查" | "待归档" | "材料阻断";
  readonly reportNo: string;
  readonly owner: string;
  readonly archiveScope: string;
  readonly evidenceSummary: string;
  readonly signedAt: string;
  readonly retainedUntil: string;
  readonly href: string;
  readonly logHref: string;
};

export type ArchiveAuditRunApiItem = {
  readonly id: string;
  readonly title: string;
  readonly status: "通过" | "阻断" | "待人工确认" | "待配置";
  readonly time: string;
  readonly archiveRoot: string;
  readonly manifestCount: number;
  readonly failedCount: number;
  readonly detail: string;
};

export type ArchiveSignatureItemApiItem = {
  readonly id: string;
  readonly label: string;
  readonly status: "验签通过" | "已生成" | "待生成";
  readonly sha256: string;
  readonly detail: string;
};

export type ArchivePolicyItemApiItem = {
  readonly id: string;
  readonly label: string;
  readonly value: string;
  readonly detail: string;
};

export type ArchiveTimelineApiItem = {
  readonly id: string;
  readonly time: string;
  readonly title: string;
  readonly detail: string;
  readonly status: "已部署" | "已入档" | "待补证" | "已记录";
};

export type ArchiveWorkbenchResponse = {
  readonly format: "archive-workbench-v1";
  readonly generated_at: string;
  readonly archive_id: string;
  readonly archive_title: string;
  readonly archive_scope: string;
  readonly archive_packages: readonly ArchivePackageApiItem[];
  readonly audit_runs: readonly ArchiveAuditRunApiItem[];
  readonly signature_items: readonly ArchiveSignatureItemApiItem[];
  readonly policy_items: readonly ArchivePolicyItemApiItem[];
  readonly timeline: readonly ArchiveTimelineApiItem[];
  readonly metrics: {
    readonly package_count: number;
    readonly archived_package_count: number;
    readonly pending_package_count: number;
    readonly blocked_package_count: number;
    readonly audit_run_count: number;
    readonly signature_count: number;
    readonly policy_count: number;
    readonly timeline_count: number;
    readonly latest_archive_run_status: string;
  };
  readonly evidence_grade: string;
  readonly production_side_effect: "none" | string;
  readonly store: {
    readonly ready: boolean;
    readonly backend: string;
  };
};

export type AuthRole =
  | "admin"
  | "technician"
  | "director"
  | "member"
  | "it-admin"
  | "department-head"
  | "auditor";

export type AuthUserRoleAssignmentItem = {
  readonly assignment_key: string;
  readonly role: string;
  readonly scope_type: string;
  readonly scope_key: string | null;
  readonly status: string;
  readonly assigned_by: string | null;
  readonly metadata: Record<string, unknown>;
  readonly source: string;
};

export type AuthUserProfile = {
  readonly user_key: string;
  readonly display_name: string;
  readonly department_key: string | null;
  readonly department_name: string | null;
  readonly status: string;
  readonly created_by: string | null;
  readonly metadata: Record<string, unknown>;
  readonly role_assignments: readonly AuthUserRoleAssignmentItem[];
  readonly source: string;
};

export type AuthSessionResponse = {
  readonly user_identifier: string;
  readonly role: string;
  readonly role_label: string;
  readonly permissions: readonly string[];
  readonly legacy_api_role: string;
  readonly tenant_id: string | null;
  readonly auth_source: string;
  readonly profile_status: string | null;
  readonly auth_scope_type: string | null;
  readonly auth_scope_key: string | null;
  readonly auth_mode: "header_transition_layer";
  readonly profile: AuthUserProfile | null;
  readonly store: {
    readonly ready: boolean;
    readonly backend: string;
  };
};

export type TableAnalysisColumnType = "数值" | "日期" | "标识" | "文本" | "空列";

export type TableAnalysisColumnProfile = {
  readonly name: string;
  readonly type: TableAnalysisColumnType;
  readonly empty_count: number;
  readonly unique_count: number;
  readonly sample_values: readonly string[];
  readonly audit_hint: string;
};

export type TableAnalysisUploadResponse = {
  readonly name: string;
  readonly size_kb: number;
  readonly extension: string;
  readonly status: "parsed";
  readonly sheet_name: string | null;
  readonly columns: readonly TableAnalysisColumnProfile[];
  readonly row_count: number;
  readonly empty_cell_count: number;
  readonly duplicate_row_count: number;
  readonly message: string;
  readonly quality_findings: readonly string[];
  readonly audit_signals: readonly string[];
  readonly recommendations: readonly string[];
  readonly upload_id: string | null;
  readonly sha256: string | null;
  readonly retention_status: "retained" | "not-configured";
  readonly created_at: string | null;
};

export type TableAnalysisUploadHistoryItem = {
  readonly id: string;
  readonly name: string;
  readonly extension: string;
  readonly size_bytes: number;
  readonly size_kb: number;
  readonly sha256: string;
  readonly storage_path: string;
  readonly sheet_name: string | null;
  readonly row_count: number;
  readonly column_count: number;
  readonly empty_cell_count: number;
  readonly duplicate_row_count: number;
  readonly status: string;
  readonly created_by: string | null;
  readonly created_at: string;
  readonly retention_status: "retained";
  readonly audit_signals: readonly string[];
};

export type TableAnalysisUploadHistoryResponse = {
  readonly items: readonly TableAnalysisUploadHistoryItem[];
  readonly store: {
    readonly ready: boolean;
    readonly backend: string;
  };
};

export const KNOWLEDGE_QUERY_CONTRACT_VERSION = "knowledge-query-contract-v2" as const;

export type KnowledgeQueryContractVersion = typeof KNOWLEDGE_QUERY_CONTRACT_VERSION;

export type SourceCollection =
  | "medical-insurance-laws"
  | "supervision-rules-knowledge"
  | "medical-insurance-catalog"
  | "risk-negative-list"
  | "policy-general-policy"
  | "policy-finance-price-procurement"
  | "policy-data-statistics-disclosure"
  | "policy-reform-pilot"
  | "policy-social-security-livelihood"
  | "policy-industry-business-environment"
  | "management-org-personnel-qualification"
  | "management-market-quality"
  | "management-license-enforcement"
  | "management-safety-emergency"
  | "management-judicial-audit-procedure"
  | "management-ecology-resources"
  | "management-urban-municipal"
  | "management-general-admin"
  | "other-agriculture-water"
  | "other-culture-tourism-sports"
  | "other-defense-confidentiality"
  | "other-education-research"
  | "other-ethnic-religious-foreign"
  | "other-transport-maritime"
  | "personal-materials";

export type ChatModelAlias = "kimi-2.7" | "deepseek-v4-pro";

export type ChatModelCatalogItem = {
  readonly alias: ChatModelAlias;
  readonly label: string;
  readonly provider: string | null;
  readonly available: boolean;
  readonly default: boolean;
  readonly unavailable_reason?: string | null;
};

export type ChatModelCatalogResponse = {
  readonly contract_version: "chat-model-catalog-v1";
  readonly default_model: ChatModelAlias;
  readonly items: readonly ChatModelCatalogItem[];
  readonly boundaries: {
    readonly production_write: false;
    readonly provider_call: false;
    readonly secret_values_reported: false;
    readonly source: "environment_capability_probe_only";
  };
};

export type DocumentSourcePermissionItem = {
  readonly source_collection: SourceCollection;
  readonly label: string;
  readonly scope: string;
  readonly access: "read" | "explicit-owner-read" | "explicit-read-all";
};

export type DocumentUploadPermissions = {
  readonly can_upload_personal: boolean;
  readonly can_read_all_personal_uploads: boolean;
  readonly can_govern_personal_uploads: boolean;
};

export type DocumentPermissionsResponse = {
  readonly role: string;
  readonly source_collections: readonly DocumentSourcePermissionItem[];
  readonly upload_permissions: DocumentUploadPermissions;
};

export type DocumentSourceCollectionMetrics = {
  readonly document_count: number | null;
  readonly chunk_count: number | null;
  readonly character_count: number | null;
  readonly linked_app_count: number | null;
};

export type DocumentSourceCollectionCatalogItem = {
  readonly source_collection: SourceCollection;
  readonly label: string;
  readonly scope: string;
  readonly phase: string;
  readonly domain: string;
  readonly evidence_group: string;
  readonly description: string;
  readonly audit_hint: string;
  readonly access: DocumentSourcePermissionItem["access"];
  readonly product_queryable: boolean;
  readonly queryable: boolean;
  readonly metrics: DocumentSourceCollectionMetrics;
};

export type DocumentSourceCollectionCatalogResponse = {
  readonly contract_version: "document-source-collections-v1";
  readonly role: string;
  readonly items: readonly DocumentSourceCollectionCatalogItem[];
  readonly search_backend: {
    readonly ready: boolean;
    readonly backend: string;
    readonly details: Record<string, unknown>;
  };
  readonly upload_permissions: DocumentUploadPermissions;
  readonly boundaries: {
    readonly production_write: false;
    readonly provider_call: false;
    readonly database_write: false;
    readonly object_storage_write: false;
    readonly source: "runtime_state_and_registry_only";
  };
};

export type KnowledgeBaseCatalogMetrics = {
  readonly document_count: number;
  readonly chunk_count: number;
  readonly embedding_count: number;
  readonly active_embedding_count: number;
  readonly candidate_chunk_count: number;
  readonly character_count: number;
  readonly linked_app_count: number;
};

export type KnowledgeBaseCatalogItem = Omit<DocumentSourceCollectionCatalogItem, "metrics"> & {
  readonly metrics: KnowledgeBaseCatalogMetrics;
  readonly index: {
    readonly latest_version_key: string | null;
    readonly latest_status: string | null;
    readonly search_backend_ready: boolean;
    readonly queryable: boolean;
  };
  readonly actions: {
    readonly documents: string;
    readonly chat: string;
    readonly graph: string;
  };
};

export type KnowledgeBaseCatalogResponse = {
  readonly contract_version: "knowledge-base-catalog-v1";
  readonly role: string;
  readonly summary: {
    readonly source_collection_count: number;
    readonly queryable_collection_count: number;
    readonly total_document_count: number;
    readonly total_chunk_count: number;
    readonly total_embedding_count: number;
    readonly current_search_embedding_count: number;
    readonly candidate_chunk_count: number;
    readonly domain_counts: Record<string, number>;
  };
  readonly items: readonly KnowledgeBaseCatalogItem[];
  readonly search_backend: {
    readonly ready: boolean;
    readonly backend: string;
    readonly details: Record<string, unknown>;
  };
  readonly store: {
    readonly ready: boolean;
    readonly backend: string;
  };
  readonly boundaries: {
    readonly production_write: false;
    readonly provider_call: false;
    readonly database_write: false;
    readonly object_storage_write: false;
    readonly query_history_write: false;
    readonly source: "runtime_state_and_postgres_catalog" | "runtime_state_and_registry_only";
  };
};

export type DocumentSearchItem = {
  readonly id: string;
  readonly chunk_id: string;
  readonly title: string;
  readonly source_collection: SourceCollection;
  readonly source_label: string;
  readonly snippet: string;
  readonly locator: Record<string, unknown>;
  readonly score: number;
  readonly matched_by: readonly string[];
  readonly index_version_key: string;
  readonly source_package_version_key: string;
  readonly preview_url: string;
};

export type DocumentSearchResponse = {
  readonly contract_version: "document-search-v1";
  readonly query: string;
  readonly effective_source_collections: readonly SourceCollection[];
  readonly items: readonly DocumentSearchItem[];
  readonly store: {
    readonly ready: boolean;
    readonly backend: string;
  };
  readonly boundaries: {
    readonly production_write: false;
    readonly provider_call: boolean;
    readonly database_write: false;
    readonly object_storage_write: false;
    readonly query_history_write: false;
  };
};

export type DocumentUploadItem = {
  readonly id: string;
  readonly name: string;
  readonly extension: string;
  readonly size_bytes: number;
  readonly size_kb: number;
  readonly sha256: string;
  readonly storage_path: string;
  readonly visibility: "private";
  readonly status: "retained";
  readonly created_by: string | null;
  readonly created_at: string;
  readonly retention_status: "retained";
  readonly index_status: "not-indexed" | "index-ready" | "staged-for-index" | "blocked";
  readonly governance_status: "pending-review" | "approved-for-index" | "blocked";
  readonly governance_note: string;
  readonly governed_by: string | null;
  readonly governed_at: string | null;
  readonly security_scan_status: "local-policy-passed" | "local-policy-review";
  readonly security_scan_provider: "local-policy";
  readonly dlp_status: "clear" | "needs-review";
  readonly security_findings: readonly string[];
  readonly personal_index_status: "not-indexed" | "indexed" | "failed";
  readonly personal_indexed_at: string | null;
  readonly personal_indexed_by: string | null;
  readonly personal_index_chunk_count: number;
  readonly personal_index_error: string;
  readonly download_url: string;
};

export type DocumentUploadListResponse = {
  readonly items: readonly DocumentUploadItem[];
  readonly store: {
    readonly ready: boolean;
    readonly backend: string;
  };
  readonly permissions: DocumentUploadPermissions;
};

export type DocumentUploadResponse = {
  readonly item: DocumentUploadItem;
  readonly store: {
    readonly ready: boolean;
    readonly backend: string;
  };
  readonly permissions: DocumentUploadPermissions;
};

export type DocumentUploadGovernanceRequest = {
  readonly governance_status: DocumentUploadItem["governance_status"];
  readonly note?: string;
};

export type QueryRequest = {
  readonly question: string;
  readonly top_k?: number;
  readonly source_collections?: readonly SourceCollection[];
  readonly title_only?: boolean;
  readonly agent?: string | null;
  readonly topic?: string;
  readonly model?: ChatModelAlias | null;
};

export type QueryBasisItem = {
  readonly citation_id: string;
  readonly chunk_id: string;
  readonly source_collection: SourceCollection;
  readonly snippet: string;
  readonly locator: Record<string, unknown>;
  readonly index_version_key: string | null;
  readonly source_package_version_key: string | null;
};

export type QueryBasisGroup = {
  readonly evidence_type: string;
  readonly title: string;
  readonly items: readonly QueryBasisItem[];
};

export type QueryCitation = {
  readonly citation_id: string;
  readonly marker: string;
  readonly chunk_id: string;
  readonly evidence_type: string;
  readonly source_collection: SourceCollection;
  readonly snippet: string;
  readonly locator: Record<string, unknown>;
  readonly index_version_key: string | null;
  readonly source_package_version_key: string | null;
};

export type PersonalUploadMatch = {
  readonly id: string;
  readonly upload_id: string;
  readonly name: string;
  readonly extension: string;
  readonly created_by: string | null;
  readonly indexed_at: string | null;
  readonly chunk_index: number;
  readonly snippet: string;
  readonly score: number;
  readonly locator: Record<string, unknown>;
};

export type QueryResponse = {
  readonly contract_version: KnowledgeQueryContractVersion;
  readonly question: string;
  readonly answer: string;
  readonly confidence: string;
  readonly fallback_used: boolean;
  readonly model_alias?: ChatModelAlias | null;
  readonly model_status?: string | null;
  readonly effective_source_collections: readonly SourceCollection[];
  readonly basis_groups: readonly QueryBasisGroup[];
  readonly citations: readonly QueryCitation[];
  readonly personal_upload_matches: readonly PersonalUploadMatch[];
  readonly query_log_index: number;
  readonly query_log_id?: string | null;
  readonly agent_invocation_id?: string | null;
};

export type ChatAttachmentAnalyzeMode = "auto" | "table-analysis" | "document-summary";

export type ChatAttachmentAnalysisResponse = {
  readonly contract_version: "chat-attachment-analysis-v1";
  readonly file_name: string;
  readonly extension: string;
  readonly mode: "table-analysis" | "document-summary";
  readonly model_alias: ChatModelAlias | null;
  readonly model_status: "selected_provider" | "default_fallback";
  readonly answer: string;
  readonly extracted_preview: string;
  readonly summary_items: readonly string[];
  readonly boundaries: {
    readonly database_write: false;
    readonly object_storage_write: false;
    readonly index_write: false;
    readonly provider_call: boolean;
  };
};

export type QueryHistoryItem = {
  readonly id: string;
  readonly user_identifier: string | null;
  readonly question: string;
  readonly filters: {
    readonly top_k?: number;
    readonly source_collections?: readonly SourceCollection[];
    readonly [key: string]: unknown;
  };
  readonly answer_summary: string | null;
  readonly retrieved_chunk_ids: readonly string[];
  readonly citation_count: number;
  readonly created_at: string;
};

export type QueryHistoryResponse = {
  readonly items: readonly QueryHistoryItem[];
  readonly store: {
    readonly ready: boolean;
    readonly backend: string;
  };
};

export type AuditFindingEvidenceItem = {
  readonly evidence_type: string;
  readonly chunk_id: string | null;
  readonly source_package_version_key: string | null;
  readonly index_version_key: string | null;
  readonly citation_id: string | null;
  readonly locator: Record<string, unknown>;
  readonly snippet: string | null;
  readonly metadata: Record<string, unknown>;
  readonly created_at: string;
};

export type AuditFinding = {
  readonly finding_key: string;
  readonly status: string;
  readonly finding_type: string;
  readonly severity: string;
  readonly review_status: string;
  readonly review_task_id: string | null;
  readonly source_record_locator: Record<string, unknown>;
  readonly calculation_trace: Record<string, unknown>;
  readonly metadata: Record<string, unknown>;
  readonly created_at: string;
  readonly updated_at: string;
  readonly audit_run_key: string | null;
  readonly audit_task_key: string | null;
  readonly rule_key: string | null;
  readonly rule_version_key: string | null;
  readonly evidence_items: readonly AuditFindingEvidenceItem[];
};

export type AuditFindingStats = {
  readonly total: number;
  readonly open: number;
  readonly pending_review: number;
  readonly linked_review_task: number;
};

export type AuditFindingGenerationPrerequisite = {
  readonly key: string;
  readonly label: string;
  readonly count: number;
  readonly ready: boolean;
  readonly required: boolean;
};

export type AuditFindingGenerationBlockingReason = {
  readonly code: string;
  readonly message: string;
};

export type AuditFindingGenerationReadiness = {
  readonly status: "generated" | "ready-to-run" | "blocked" | string;
  readonly ready: boolean;
  readonly has_findings: boolean;
  readonly table_counts: Record<string, number>;
  readonly prerequisites: readonly AuditFindingGenerationPrerequisite[];
  readonly blocking_reasons: readonly AuditFindingGenerationBlockingReason[];
  readonly next_actions: readonly string[];
};

export type AuditFindingsResponse = {
  readonly items: readonly AuditFinding[];
  readonly stats: AuditFindingStats;
  readonly filters: {
    readonly review_status: string | null;
    readonly limit: number;
  };
  readonly review_status_options: Record<string, string>;
  readonly generation_readiness: AuditFindingGenerationReadiness;
  readonly store: {
    readonly ready: boolean;
    readonly backend: string;
  };
};

export type WorkpaperTemplateRegistryItem = {
  readonly id: string;
  readonly name: string;
  readonly source_template_id: string;
  readonly source_table: string;
  readonly source_file_name: string;
  readonly sheet_name: string;
  readonly output_type: "底稿草稿" | "问题清单" | "复核摘要" | string;
  readonly registry_status: "active" | string;
  readonly expected_columns: readonly string[];
  readonly key_checks: readonly string[];
  readonly evidence_bindings: readonly string[];
  readonly prompt: string;
  readonly chat_href: string;
};

export type ReportDownloadLinks = {
  readonly page: string;
  readonly task_docx: string;
  readonly report_docx: string | null;
  readonly report_markdown: string | null;
  readonly report_json: string | null;
};

export type ReportWorkbenchEntry = {
  readonly id: string;
  readonly title: string;
  readonly status: "草稿" | "门禁阻断" | "已签发" | string;
  readonly report_no: string;
  readonly owner: string;
  readonly source: string;
  readonly included_finding_count: number;
  readonly appendix_count: number;
  readonly gate_summary: string;
  readonly updated_at: string;
  readonly href: string;
  readonly download_links: ReportDownloadLinks;
};

export type ReportWorkbenchEvidenceSource = {
  readonly id: string;
  readonly title: string;
  readonly kind: "疑点" | "底稿" | "附件" | "负责人确认" | string;
  readonly reference: string;
  readonly status: "已纳入" | "待补证" | "只读" | string;
  readonly href: string;
};

export type ReportWorkbenchResponse = {
  readonly format: "report-workbench-v1";
  readonly generated_at: string;
  readonly template_registry_status: string;
  readonly workpaper_templates: readonly WorkpaperTemplateRegistryItem[];
  readonly report_entries: readonly ReportWorkbenchEntry[];
  readonly report_evidence_sources: readonly ReportWorkbenchEvidenceSource[];
  readonly metrics: {
    readonly report_count: number;
    readonly signed_report_count: number;
    readonly blocked_report_count: number;
    readonly included_finding_count: number;
    readonly docx_download_count: number;
  };
  readonly store: {
    readonly ready: boolean;
    readonly backend: string;
  };
};

export type ApiAgentCategory = "效率类" | "业务类" | "研究类";

export type AuditAgentApiItem = {
  readonly id: string;
  readonly name: string;
  readonly category: ApiAgentCategory;
  readonly topic: string;
  readonly prompt: string;
  readonly knowledge_base: string;
  readonly project_name: string;
  readonly status: string;
  readonly prompt_version: number;
  readonly prompt_version_key: string;
  readonly visibility_scope: "project" | "system";
  readonly allowed_roles: readonly string[];
  readonly prompt_versions: readonly AgentPromptVersionApiItem[];
  readonly created_by: string | null;
  readonly created_at?: string;
  readonly updated_at: string;
  readonly source: "custom" | "system-default" | string;
  readonly metadata: Record<string, unknown>;
};

export type AgentPromptVersionApiItem = {
  readonly version: number;
  readonly prompt: string;
  readonly change_summary: string;
  readonly is_active: boolean;
  readonly created_by: string | null;
  readonly created_at: string;
  readonly review_status: "pending-review" | "approved" | "changes-requested";
  readonly review_note: string;
  readonly requested_by: string | null;
  readonly reviewed_by: string | null;
  readonly reviewed_at: string | null;
  readonly review_updated_at: string | null;
};

export type AgentsResponse = {
  readonly items: readonly AuditAgentApiItem[];
  readonly categories: readonly ApiAgentCategory[];
  readonly store: {
    readonly ready: boolean;
    readonly backend: string;
  };
};

export type AgentCreateRequest = {
  readonly name: string;
  readonly category: ApiAgentCategory;
  readonly topic: string;
  readonly prompt: string;
  readonly knowledge_base?: string;
  readonly project_name?: string;
  readonly visibility_scope?: "project" | "system";
  readonly allowed_roles?: readonly string[];
  readonly metadata?: Record<string, unknown>;
};

export type AgentCreateResponse = {
  readonly item: AuditAgentApiItem;
  readonly store: {
    readonly ready: boolean;
    readonly backend: string;
  };
};

export type AgentDetailResponse = AgentCreateResponse;

export type AgentPromptVersionsResponse = {
  readonly items: readonly AgentPromptVersionApiItem[];
  readonly store: {
    readonly ready: boolean;
    readonly backend: string;
  };
};

export type AgentPromptVersionCreateRequest = {
  readonly prompt: string;
  readonly change_summary: string;
  readonly review_note?: string;
};

export type AgentPromptVersionReviewRequest = {
  readonly version: number;
  readonly review_status: "pending-review" | "approved" | "changes-requested";
  readonly review_note?: string;
};

export type AgentPromptVersionRollbackRequest = {
  readonly version: number;
};

export type AgentLifecycleRequest = {
  readonly status: "active" | "inactive" | "archived";
  readonly reason?: string;
};

export type AgentInvocationApiItem = {
  readonly id: string;
  readonly agent_key: string;
  readonly prompt_version: number;
  readonly prompt_version_key: string;
  readonly invocation_source: string;
  readonly question: string | null;
  readonly conversation_ref: string | null;
  readonly created_by: string | null;
  readonly created_at: string;
  readonly metadata: Record<string, unknown>;
};

export type AgentInvocationCreateRequest = {
  readonly invocation_source?: string;
  readonly question?: string | null;
  readonly conversation_ref?: string | null;
  readonly metadata?: Record<string, unknown>;
};

export type AgentInvocationResponse = {
  readonly item: AgentInvocationApiItem;
  readonly store: {
    readonly ready: boolean;
    readonly backend: string;
  };
};

export type AgentInvocationsResponse = {
  readonly items: readonly AgentInvocationApiItem[];
  readonly store: {
    readonly ready: boolean;
    readonly backend: string;
  };
};

export type AgentFeedbackRating = "effective" | "needs_review" | "unsafe";

export type AgentFeedbackSummary = {
  readonly total: number;
  readonly effective: number;
  readonly needs_review: number;
  readonly unsafe: number;
  readonly latest_rating: AgentFeedbackRating | null;
};

export type AgentFeedbackApiItem = {
  readonly id: string;
  readonly agent_key: string;
  readonly invocation_id: string | null;
  readonly prompt_version: number;
  readonly rating: AgentFeedbackRating;
  readonly comment: string;
  readonly created_by: string | null;
  readonly created_at: string;
  readonly metadata: Record<string, unknown>;
};

export type AgentFeedbackCreateRequest = {
  readonly invocation_id?: string | null;
  readonly rating: AgentFeedbackRating;
  readonly comment?: string;
  readonly metadata?: Record<string, unknown>;
};

export type AgentFeedbackResponse = {
  readonly item: AgentFeedbackApiItem;
  readonly ratings: readonly AgentFeedbackRating[];
  readonly summary: AgentFeedbackSummary;
  readonly store: {
    readonly ready: boolean;
    readonly backend: string;
  };
};

export type AgentFeedbackListResponse = {
  readonly items: readonly AgentFeedbackApiItem[];
  readonly ratings: readonly AgentFeedbackRating[];
  readonly summary: AgentFeedbackSummary;
  readonly store: {
    readonly ready: boolean;
    readonly backend: string;
  };
};

export type ApiProjectStatus = "进行中" | "待启动" | "已归档";
export type ApiProjectMemberRole = "项目负责人" | "审计员" | "业务专家" | "信息科" | "只读观察员";
export type ApiProjectMemberStatus = "在项目中" | "待确认";

export type ProjectSummaryApiItem = {
  readonly id: string;
  readonly name: string;
  readonly audit_topic: string;
  readonly organization_name: string;
  readonly member_count: number;
  readonly creator: string;
  readonly created_at: string;
  readonly status: ApiProjectStatus;
  readonly operation_label: string;
  readonly source: "system-default" | string;
};

export type ProjectMemberApiItem = {
  readonly id: string;
  readonly project_key: string;
  readonly name: string;
  readonly role: ApiProjectMemberRole;
  readonly department: string;
  readonly status: ApiProjectMemberStatus;
  readonly created_by: string | null;
  readonly created_at?: string;
  readonly updated_at?: string;
  readonly source: "custom" | "system-default" | string;
  readonly metadata: Record<string, unknown>;
};

export type ProjectsResponse = {
  readonly items: readonly ProjectSummaryApiItem[];
  readonly roles: readonly ApiProjectMemberRole[];
  readonly statuses: readonly ApiProjectMemberStatus[];
  readonly store: {
    readonly ready: boolean;
    readonly backend: string;
  };
};

export type ProjectDashboardMetricApiItem = {
  readonly key: "open_findings" | "missing_evidence" | "rule_cards" | "backend_status";
  readonly label: string;
  readonly value: string;
  readonly helper: string;
  readonly tone: "neutral" | "info" | "warning" | "danger" | "success";
};

export type ProjectDashboardQueueApiItem = {
  readonly id: string;
  readonly title: string;
  readonly owner: string;
  readonly dueLabel: string;
  readonly status: "open" | "blocked" | "closed";
  readonly risk: "high" | "medium" | "low";
};

export type ProjectDashboardActivityApiItem = {
  readonly id: string;
  readonly title: string;
  readonly description: string;
  readonly timeLabel: string;
};

export type ProjectDashboardStatusDistributionApiItem = {
  readonly status: string;
  readonly label: string;
  readonly count: number;
};

export type ProjectDashboardMemberWorkloadApiItem = {
  readonly name: string;
  readonly role: string;
  readonly department: string;
  readonly total: number;
  readonly pending: number;
  readonly closed: number;
};

export type ProjectDashboardResponse = {
  readonly format: "project-dashboard-v1";
  readonly project: ProjectSummaryApiItem;
  readonly metrics: readonly ProjectDashboardMetricApiItem[];
  readonly queue: readonly ProjectDashboardQueueApiItem[];
  readonly activities: readonly ProjectDashboardActivityApiItem[];
  readonly status_distribution: readonly ProjectDashboardStatusDistributionApiItem[];
  readonly member_workloads: readonly ProjectDashboardMemberWorkloadApiItem[];
  readonly evidence_grade: string;
  readonly production_side_effect: "none" | string;
  readonly store: {
    readonly ready: boolean;
    readonly backend: {
      readonly project_members: string;
      readonly audit_findings: string;
    };
  };
};

export type ProjectMembersResponse = {
  readonly items: readonly ProjectMemberApiItem[];
  readonly project_key: string;
  readonly roles: readonly ApiProjectMemberRole[];
  readonly statuses: readonly ApiProjectMemberStatus[];
  readonly store: {
    readonly ready: boolean;
    readonly backend: string;
  };
};

export type ProjectMemberCreateRequest = {
  readonly name: string;
  readonly role: ApiProjectMemberRole;
  readonly department: string;
  readonly status?: ApiProjectMemberStatus;
  readonly metadata?: Record<string, unknown>;
};

export type ProjectMemberCreateResponse = {
  readonly item: ProjectMemberApiItem;
  readonly store: {
    readonly ready: boolean;
    readonly backend: string;
  };
};
