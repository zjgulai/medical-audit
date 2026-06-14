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
};

export type SourceCollection =
  | "medical-insurance-laws"
  | "supervision-rules-knowledge"
  | "medical-insurance-catalog"
  | "risk-negative-list";

export type QueryRequest = {
  readonly question: string;
  readonly top_k?: number;
  readonly source_collections?: readonly SourceCollection[];
};

export type QueryBasisItem = {
  readonly citation_id: string;
  readonly chunk_id: string;
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
  readonly snippet: string;
  readonly locator: Record<string, unknown>;
  readonly index_version_key: string | null;
  readonly source_package_version_key: string | null;
};

export type QueryResponse = {
  readonly question: string;
  readonly answer: string;
  readonly confidence: string;
  readonly fallback_used: boolean;
  readonly basis_groups: readonly QueryBasisGroup[];
  readonly citations: readonly QueryCitation[];
  readonly query_log_index: number;
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
  readonly created_by: string | null;
  readonly created_at?: string;
  readonly updated_at: string;
  readonly source: "custom" | "system-default" | string;
  readonly metadata: Record<string, unknown>;
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
  readonly metadata?: Record<string, unknown>;
};

export type AgentCreateResponse = {
  readonly item: AuditAgentApiItem;
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
