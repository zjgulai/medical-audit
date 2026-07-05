import type {
  AgentCreateRequest,
  AgentCreateResponse,
  AgentDetailResponse,
  AgentFeedbackCreateRequest,
  AgentFeedbackListResponse,
  AgentFeedbackResponse,
  AgentInvocationCreateRequest,
  AgentInvocationResponse,
  AgentInvocationsResponse,
  AgentLifecycleRequest,
  AgentPromptVersionCreateRequest,
  AgentPromptVersionRollbackRequest,
  AgentPromptVersionReviewRequest,
  AgentPromptVersionsResponse,
  AgentsResponse,
  ArchiveWorkbenchResponse,
  AuthSessionResponse,
  AuditFindingsResponse,
  BackendHealthResponse,
  DocumentUploadGovernanceRequest,
  DocumentPermissionsResponse,
  DocumentUploadListResponse,
  DocumentUploadResponse,
  GraphWorkbenchResponse,
  ProjectMemberCreateRequest,
  ProjectMemberCreateResponse,
  ProjectMembersResponse,
  ProjectsResponse,
  QueryHistoryResponse,
  QueryRequest,
  QueryResponse,
  RemediationWorkbenchResponse,
  ReportWorkbenchResponse,
  RulesWorkbenchResponse,
  SearchBackendStatusResponse,
  TableAnalysisUploadHistoryResponse,
  TableAnalysisUploadResponse
} from "./api-types";
import { backendApiEndpoints } from "./api-endpoints";
import { auditAgentClientHeaders, auditClientHeaders, auditProjectClientHeaders } from "./audit-user";

export type ApiClientErrorCode =
  | "backend-request-failed"
  | "no-cited-evidence"
  | "search-engine-not-initialized"
  | "source-collection-denied"
  | "unknown-topic";

export class ApiClientError extends Error {
  readonly code: ApiClientErrorCode;
  readonly detail: unknown;
  readonly method: "GET" | "POST";
  readonly path: string;
  readonly status: number;

  constructor({
    code,
    detail,
    method,
    path,
    status
  }: {
    readonly code: ApiClientErrorCode;
    readonly detail: unknown;
    readonly method: "GET" | "POST";
    readonly path: string;
    readonly status: number;
  }) {
    super(`Backend request failed: ${method} ${path} returned ${status}`);
    this.name = "ApiClientError";
    this.code = code;
    this.detail = detail;
    this.method = method;
    this.path = path;
    this.status = status;
  }
}

export function isApiClientError(error: unknown): error is ApiClientError {
  return error instanceof ApiClientError;
}

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
    throw await apiError("GET", path, response);
  }

  return (await response.json()) as T;
}

async function getJsonWithAuditHeaders<T>(
  path: string,
  headers: Record<string, string> = auditClientHeaders()
): Promise<T> {
  assertBackendProxyClientRuntime();

  const response = await fetch(path, {
    headers: {
      Accept: "application/json",
      ...headers
    },
    cache: "no-store"
  });

  if (!response.ok) {
    throw await apiError("GET", path, response);
  }

  return (await response.json()) as T;
}

async function postJson<T>(
  path: string,
  payload: unknown,
  headers: Record<string, string> = auditClientHeaders()
): Promise<T> {
  assertBackendProxyClientRuntime();

  const response = await fetch(path, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...headers
    },
    body: JSON.stringify(payload),
    cache: "no-store"
  });

  if (!response.ok) {
    throw await apiError("POST", path, response);
  }

  return (await response.json()) as T;
}

async function postForm<T>(path: string, formData: FormData): Promise<T> {
  assertBackendProxyClientRuntime();

  const response = await fetch(path, {
    method: "POST",
    headers: {
      Accept: "application/json",
      ...auditClientHeaders()
    },
    body: formData,
    cache: "no-store"
  });

  if (!response.ok) {
    throw await apiError("POST", path, response);
  }

  return (await response.json()) as T;
}

export function fetchBackendHealth(): Promise<BackendHealthResponse> {
  return getJson<BackendHealthResponse>(backendApiEndpoints.backendHealth);
}

async function apiError(
  method: "GET" | "POST",
  path: string,
  response: Response
): Promise<ApiClientError> {
  const detail = await readErrorDetail(response);
  return new ApiClientError({
    code: classifyApiError(response.status, detail),
    detail,
    method,
    path,
    status: response.status
  });
}

async function readErrorDetail(response: Response): Promise<unknown> {
  const maybeJson = response as Response & { readonly json?: () => Promise<unknown> };
  if (typeof maybeJson.json === "function") {
    try {
      const body = await maybeJson.json();
      if (body && typeof body === "object" && "detail" in body) {
        return (body as { readonly detail: unknown }).detail;
      }
      return body;
    } catch {
      // Fall through to text for non-JSON responses or lightweight test doubles.
    }
  }

  const maybeText = response as Response & { readonly text?: () => Promise<string> };
  if (typeof maybeText.text === "function") {
    try {
      return await maybeText.text();
    } catch {
      return "";
    }
  }
  return "";
}

function classifyApiError(status: number, detail: unknown): ApiClientErrorCode {
  const text = typeof detail === "string" ? detail : JSON.stringify(detail ?? "");
  if (status === 409 && text.includes("search engine is not initialized")) {
    return "search-engine-not-initialized";
  }
  if (status === 404 && text.includes("no cited evidence found")) {
    return "no-cited-evidence";
  }
  if (status === 400 && text.includes("unknown topic")) {
    return "unknown-topic";
  }
  if (status === 403) {
    return "source-collection-denied";
  }
  return "backend-request-failed";
}

export function fetchSearchBackendStatus(): Promise<SearchBackendStatusResponse> {
  return getJsonWithAuditHeaders<SearchBackendStatusResponse>(
    backendApiEndpoints.searchBackendStatus
  );
}

export function fetchAuthSession(): Promise<AuthSessionResponse> {
  return getJsonWithAuditHeaders<AuthSessionResponse>(
    backendApiEndpoints.authSession,
    auditProjectClientHeaders()
  );
}

export function runKnowledgeQuery(payload: QueryRequest): Promise<QueryResponse> {
  return postJson<QueryResponse>(backendApiEndpoints.query, payload);
}

export function fetchQueryHistory(): Promise<QueryHistoryResponse> {
  return getJsonWithAuditHeaders<QueryHistoryResponse>(backendApiEndpoints.queryLogs());
}

export function fetchAuditFindings(reviewStatus?: string): Promise<AuditFindingsResponse> {
  return getJsonWithAuditHeaders<AuditFindingsResponse>(
    backendApiEndpoints.auditFindings(reviewStatus)
  );
}

export function fetchReportWorkbench(): Promise<ReportWorkbenchResponse> {
  return getJsonWithAuditHeaders<ReportWorkbenchResponse>(backendApiEndpoints.reportWorkbench);
}

export function fetchGraphWorkbench(): Promise<GraphWorkbenchResponse> {
  return getJsonWithAuditHeaders<GraphWorkbenchResponse>(backendApiEndpoints.graphWorkbench);
}

export function fetchRulesWorkbench(): Promise<RulesWorkbenchResponse> {
  return getJsonWithAuditHeaders<RulesWorkbenchResponse>(backendApiEndpoints.rulesWorkbench);
}

export function fetchRemediationWorkbench(): Promise<RemediationWorkbenchResponse> {
  return getJsonWithAuditHeaders<RemediationWorkbenchResponse>(
    backendApiEndpoints.remediationWorkbench
  );
}

export function fetchArchiveWorkbench(): Promise<ArchiveWorkbenchResponse> {
  return getJsonWithAuditHeaders<ArchiveWorkbenchResponse>(backendApiEndpoints.archiveWorkbench);
}

export function uploadAnalysisTable(file: File): Promise<TableAnalysisUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  return postForm<TableAnalysisUploadResponse>(backendApiEndpoints.analyticsTableUpload, formData);
}

export function fetchAnalysisUploadHistory(): Promise<TableAnalysisUploadHistoryResponse> {
  return getJsonWithAuditHeaders<TableAnalysisUploadHistoryResponse>(
    backendApiEndpoints.analyticsTableUploads
  );
}

export function fetchDocumentPermissions(): Promise<DocumentPermissionsResponse> {
  return getJsonWithAuditHeaders<DocumentPermissionsResponse>(
    backendApiEndpoints.documentPermissions
  );
}

export function fetchDocumentUploads(): Promise<DocumentUploadListResponse> {
  return getJsonWithAuditHeaders<DocumentUploadListResponse>(backendApiEndpoints.documentUploads);
}

export function uploadPersonalDocument(file: File): Promise<DocumentUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  return postForm<DocumentUploadResponse>(backendApiEndpoints.documentUploads, formData);
}

export function updateDocumentUploadGovernance(
  uploadId: string,
  payload: DocumentUploadGovernanceRequest
): Promise<DocumentUploadResponse> {
  return postJson<DocumentUploadResponse>(
    backendApiEndpoints.documentUploadGovernance(uploadId),
    payload
  );
}

export function indexPersonalDocument(uploadId: string): Promise<DocumentUploadResponse> {
  return postJson<DocumentUploadResponse>(
    backendApiEndpoints.documentUploadIndex(uploadId),
    {}
  );
}

export function fetchAgents(): Promise<AgentsResponse> {
  return getJsonWithAuditHeaders<AgentsResponse>(
    backendApiEndpoints.agents,
    auditAgentClientHeaders()
  );
}

export function fetchAuditAgent(agentId: string): Promise<AgentDetailResponse> {
  return getJsonWithAuditHeaders<AgentDetailResponse>(
    backendApiEndpoints.agent(agentId),
    auditAgentClientHeaders()
  );
}

export function createAuditAgent(payload: AgentCreateRequest): Promise<AgentCreateResponse> {
  return postJson<AgentCreateResponse>(
    backendApiEndpoints.agents,
    payload,
    auditAgentClientHeaders()
  );
}

export function fetchAuditAgentPromptVersions(
  agentId: string
): Promise<AgentPromptVersionsResponse> {
  return getJsonWithAuditHeaders<AgentPromptVersionsResponse>(
    backendApiEndpoints.agentPromptVersions(agentId),
    auditAgentClientHeaders()
  );
}

export function createAuditAgentPromptVersion(
  agentId: string,
  payload: AgentPromptVersionCreateRequest
): Promise<AgentCreateResponse> {
  return postJson<AgentCreateResponse>(
    backendApiEndpoints.agentPromptVersions(agentId),
    payload,
    auditAgentClientHeaders()
  );
}

export function rollbackAuditAgentPromptVersion(
  agentId: string,
  payload: AgentPromptVersionRollbackRequest
): Promise<AgentCreateResponse> {
  return postJson<AgentCreateResponse>(
    backendApiEndpoints.agentPromptVersionRollback(agentId),
    payload,
    auditAgentClientHeaders()
  );
}

export function reviewAuditAgentPromptVersion(
  agentId: string,
  payload: AgentPromptVersionReviewRequest
): Promise<AgentCreateResponse> {
  return postJson<AgentCreateResponse>(
    backendApiEndpoints.agentPromptVersionReview(agentId),
    payload,
    auditAgentClientHeaders()
  );
}

export function updateAuditAgentLifecycle(
  agentId: string,
  payload: AgentLifecycleRequest
): Promise<AgentCreateResponse> {
  return postJson<AgentCreateResponse>(
    backendApiEndpoints.agentLifecycle(agentId),
    payload,
    auditAgentClientHeaders()
  );
}

export function fetchAuditAgentInvocations(agentId: string): Promise<AgentInvocationsResponse> {
  return getJsonWithAuditHeaders<AgentInvocationsResponse>(
    backendApiEndpoints.agentInvocations(agentId),
    auditAgentClientHeaders()
  );
}

export function recordAuditAgentInvocation(
  agentId: string,
  payload: AgentInvocationCreateRequest
): Promise<AgentInvocationResponse> {
  return postJson<AgentInvocationResponse>(
    backendApiEndpoints.agentInvocations(agentId),
    payload,
    auditAgentClientHeaders()
  );
}

export function fetchAuditAgentFeedback(agentId: string): Promise<AgentFeedbackListResponse> {
  return getJsonWithAuditHeaders<AgentFeedbackListResponse>(
    backendApiEndpoints.agentFeedback(agentId),
    auditAgentClientHeaders()
  );
}

export function submitAuditAgentFeedback(
  agentId: string,
  payload: AgentFeedbackCreateRequest
): Promise<AgentFeedbackResponse> {
  return postJson<AgentFeedbackResponse>(
    backendApiEndpoints.agentFeedback(agentId),
    payload,
    auditAgentClientHeaders()
  );
}

export function fetchProjects(): Promise<ProjectsResponse> {
  return getJsonWithAuditHeaders<ProjectsResponse>(
    backendApiEndpoints.projects,
    auditProjectClientHeaders()
  );
}

export function fetchProjectMembers(projectId: string): Promise<ProjectMembersResponse> {
  return getJsonWithAuditHeaders<ProjectMembersResponse>(
    backendApiEndpoints.projectMembers(projectId),
    auditProjectClientHeaders(projectId)
  );
}

export function createProjectMember(
  projectId: string,
  payload: ProjectMemberCreateRequest
): Promise<ProjectMemberCreateResponse> {
  return postJson<ProjectMemberCreateResponse>(
    backendApiEndpoints.projectMembers(projectId),
    payload,
    auditProjectClientHeaders(projectId)
  );
}
