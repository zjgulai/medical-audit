import type {
  AgentCreateRequest,
  AgentCreateResponse,
  AgentsResponse,
  AuditFindingsResponse,
  BackendHealthResponse,
  DocumentPermissionsResponse,
  DocumentUploadDownloadResponse,
  DocumentUploadListResponse,
  DocumentUploadResponse,
  ProjectMemberCreateRequest,
  ProjectMemberCreateResponse,
  ProjectMembersResponse,
  ProjectsResponse,
  QueryHistoryResponse,
  QueryRequest,
  QueryResponse,
  SearchBackendStatusResponse,
  TableAnalysisUploadHistoryResponse,
  TableAnalysisUploadResponse
} from "./api-types";

function assertBackendProxyClientRuntime(): void {
  if (typeof window === "undefined") {
    throw new Error(
      "Backend proxy client must be called from browser/client code; server code needs an absolute backend URL."
    );
  }
}

async function getJson<T>(path: string): Promise<T> {
  assertBackendProxyClientRuntime();

  const response = await fetch(path, {
    headers: { Accept: "application/json" },
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error(`Backend request failed: GET ${path} returned ${response.status}`);
  }

  return (await response.json()) as T;
}

async function getJsonWithAuditHeaders<T>(path: string): Promise<T> {
  assertBackendProxyClientRuntime();

  const response = await fetch(path, {
    headers: {
      Accept: "application/json",
      "X-Role": "auditor",
      "X-User-Id": "next-knowledge-query"
    },
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error(`Backend request failed: GET ${path} returned ${response.status}`);
  }

  return (await response.json()) as T;
}

async function postJson<T>(path: string, payload: unknown): Promise<T> {
  assertBackendProxyClientRuntime();

  const response = await fetch(path, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "X-Role": "auditor",
      "X-User-Id": "next-knowledge-query"
    },
    body: JSON.stringify(payload),
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error(`Backend request failed: POST ${path} returned ${response.status}`);
  }

  return (await response.json()) as T;
}

async function postForm<T>(path: string, formData: FormData): Promise<T> {
  assertBackendProxyClientRuntime();

  const response = await fetch(path, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "X-Role": "auditor",
      "X-User-Id": "next-knowledge-query"
    },
    body: formData,
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error(`Backend request failed: POST ${path} returned ${response.status}`);
  }

  return (await response.json()) as T;
}

export function fetchBackendHealth(): Promise<BackendHealthResponse> {
  return getJson<BackendHealthResponse>("/api/backend/health");
}

export function fetchSearchBackendStatus(): Promise<SearchBackendStatusResponse> {
  return getJson<SearchBackendStatusResponse>("/api/backend/index/search-backend");
}

export function runKnowledgeQuery(payload: QueryRequest): Promise<QueryResponse> {
  return postJson<QueryResponse>("/api/v1/query", payload);
}

export function fetchQueryHistory(): Promise<QueryHistoryResponse> {
  return getJson<QueryHistoryResponse>("/api/v1/query/logs?limit=8");
}

export function fetchAuditFindings(reviewStatus?: string): Promise<AuditFindingsResponse> {
  const params = new URLSearchParams();
  if (reviewStatus) {
    params.set("review_status", reviewStatus);
  }
  const queryString = params.toString();
  return getJson<AuditFindingsResponse>(
    `/api/v1/audit-findings${queryString ? `?${queryString}` : ""}`
  );
}

export function uploadAnalysisTable(file: File): Promise<TableAnalysisUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  return postForm<TableAnalysisUploadResponse>("/api/v1/analytics/table-upload", formData);
}

export function fetchAnalysisUploadHistory(): Promise<TableAnalysisUploadHistoryResponse> {
  return getJson<TableAnalysisUploadHistoryResponse>("/api/v1/analytics/table-uploads");
}

export function fetchDocumentPermissions(): Promise<DocumentPermissionsResponse> {
  return getJsonWithAuditHeaders<DocumentPermissionsResponse>("/api/v1/documents/permissions");
}

export function fetchDocumentUploads(): Promise<DocumentUploadListResponse> {
  return getJsonWithAuditHeaders<DocumentUploadListResponse>("/api/v1/documents/uploads");
}

export function uploadPersonalDocument(file: File): Promise<DocumentUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  return postForm<DocumentUploadResponse>("/api/v1/documents/uploads", formData);
}

export function fetchDocumentUploadDownload(uploadId: string): Promise<DocumentUploadDownloadResponse> {
  return getJsonWithAuditHeaders<DocumentUploadDownloadResponse>(
    `/api/v1/documents/uploads/${encodeURIComponent(uploadId)}/download`
  );
}

export function fetchAgents(): Promise<AgentsResponse> {
  return getJson<AgentsResponse>("/api/v1/agents");
}

export function createAuditAgent(payload: AgentCreateRequest): Promise<AgentCreateResponse> {
  return postJson<AgentCreateResponse>("/api/v1/agents", payload);
}

export function fetchProjects(): Promise<ProjectsResponse> {
  return getJson<ProjectsResponse>("/api/v1/projects");
}

export function fetchProjectMembers(projectId: string): Promise<ProjectMembersResponse> {
  return getJson<ProjectMembersResponse>(`/api/v1/projects/${encodeURIComponent(projectId)}/members`);
}

export function createProjectMember(
  projectId: string,
  payload: ProjectMemberCreateRequest
): Promise<ProjectMemberCreateResponse> {
  return postJson<ProjectMemberCreateResponse>(
    `/api/v1/projects/${encodeURIComponent(projectId)}/members`,
    payload
  );
}
