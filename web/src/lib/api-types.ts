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
