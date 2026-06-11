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
