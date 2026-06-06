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
