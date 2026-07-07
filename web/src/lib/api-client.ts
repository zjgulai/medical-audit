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
  ChatAttachmentAnalysisResponse,
  ChatAttachmentAnalyzeMode,
  ChatModelAlias,
  ChatModelCatalogResponse,
  DocumentSourceCollectionCatalogResponse,
  DocumentSearchResponse,
  DocumentUploadGovernanceRequest,
  DocumentPermissionsResponse,
  DocumentUploadListResponse,
  DocumentUploadResponse,
  GraphWorkbenchResponse,
  KnowledgeBaseCatalogResponse,
  ProjectMemberCreateRequest,
  ProjectMemberCreateResponse,
  ProjectDashboardResponse,
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
import { auditAgentClientHeaders, auditClientHeaders, auditProjectClientHeaders } from "./audit-user";

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
    throw new Error(`Backend request failed: GET ${path} returned ${response.status}`);
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
      ...auditClientHeaders()
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
  return getJsonWithAuditHeaders<SearchBackendStatusResponse>("/api/backend/index/search-backend");
}

export function fetchAuthSession(): Promise<AuthSessionResponse> {
  return getJsonWithAuditHeaders<AuthSessionResponse>(
    "/api/v1/auth/session",
    auditProjectClientHeaders()
  );
}

export function runKnowledgeQuery(payload: QueryRequest): Promise<QueryResponse> {
  return postJson<QueryResponse>("/api/v1/query", payload);
}

export function fetchQueryModels(): Promise<ChatModelCatalogResponse> {
  return getJsonWithAuditHeaders<ChatModelCatalogResponse>("/api/v1/query/models");
}

export function fetchQueryHistory(): Promise<QueryHistoryResponse> {
  return getJsonWithAuditHeaders<QueryHistoryResponse>("/api/v1/query/logs?limit=8");
}

export function analyzeChatAttachment(
  file: File,
  options: {
    readonly model?: ChatModelAlias | null;
    readonly mode?: ChatAttachmentAnalyzeMode;
  }
): Promise<ChatAttachmentAnalysisResponse> {
  const formData = new FormData();
  formData.append("file", file);
  if (options.model) {
    formData.append("model", options.model);
  }
  formData.append("mode", options.mode ?? "auto");
  return postForm<ChatAttachmentAnalysisResponse>("/api/v1/chat/attachments/analyze", formData);
}

export function fetchAuditFindings(reviewStatus?: string): Promise<AuditFindingsResponse> {
  const params = new URLSearchParams();
  if (reviewStatus) {
    params.set("review_status", reviewStatus);
  }
  const queryString = params.toString();
  return getJsonWithAuditHeaders<AuditFindingsResponse>(
    `/api/v1/audit-findings${queryString ? `?${queryString}` : ""}`
  );
}

export function fetchReportWorkbench(): Promise<ReportWorkbenchResponse> {
  return getJsonWithAuditHeaders<ReportWorkbenchResponse>("/api/v1/reports/workbench");
}

export function fetchGraphWorkbench(): Promise<GraphWorkbenchResponse> {
  return getJsonWithAuditHeaders<GraphWorkbenchResponse>("/api/v1/graph/workbench");
}

export function fetchRulesWorkbench(): Promise<RulesWorkbenchResponse> {
  return getJsonWithAuditHeaders<RulesWorkbenchResponse>("/api/v1/rules/workbench");
}

export function fetchRemediationWorkbench(): Promise<RemediationWorkbenchResponse> {
  return getJsonWithAuditHeaders<RemediationWorkbenchResponse>("/api/v1/remediation/workbench");
}

export function fetchArchiveWorkbench(): Promise<ArchiveWorkbenchResponse> {
  return getJsonWithAuditHeaders<ArchiveWorkbenchResponse>("/api/v1/archive/workbench");
}

export function uploadAnalysisTable(file: File): Promise<TableAnalysisUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  return postForm<TableAnalysisUploadResponse>("/api/v1/analytics/table-upload", formData);
}

export function fetchAnalysisUploadHistory(): Promise<TableAnalysisUploadHistoryResponse> {
  return getJsonWithAuditHeaders<TableAnalysisUploadHistoryResponse>("/api/v1/analytics/table-uploads");
}

export function fetchDocumentPermissions(): Promise<DocumentPermissionsResponse> {
  return getJsonWithAuditHeaders<DocumentPermissionsResponse>("/api/v1/documents/permissions");
}

export function fetchDocumentSourceCollections(): Promise<DocumentSourceCollectionCatalogResponse> {
  return getJsonWithAuditHeaders<DocumentSourceCollectionCatalogResponse>(
    "/api/v1/documents/source-collections"
  );
}

export function fetchKnowledgeBaseCatalog(): Promise<KnowledgeBaseCatalogResponse> {
  return getJsonWithAuditHeaders<KnowledgeBaseCatalogResponse>("/api/v1/knowledge-base/catalog");
}

export function searchDocuments(options: {
  readonly query: string;
  readonly sourceCollections?: readonly string[];
  readonly titleOnly?: boolean;
  readonly limit?: number;
}): Promise<DocumentSearchResponse> {
  const params = new URLSearchParams();
  params.set("q", options.query);
  for (const sourceCollection of options.sourceCollections ?? []) {
    params.append("source_collection", sourceCollection);
  }
  if (options.titleOnly) {
    params.set("title_only", "true");
  }
  if (options.limit) {
    params.set("limit", String(options.limit));
  }
  return getJsonWithAuditHeaders<DocumentSearchResponse>(
    `/api/v1/documents/search?${params.toString()}`
  );
}

export function fetchDocumentUploads(): Promise<DocumentUploadListResponse> {
  return getJsonWithAuditHeaders<DocumentUploadListResponse>("/api/v1/documents/uploads");
}

export function uploadPersonalDocument(file: File): Promise<DocumentUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  return postForm<DocumentUploadResponse>("/api/v1/documents/uploads", formData);
}

export function updateDocumentUploadGovernance(
  uploadId: string,
  payload: DocumentUploadGovernanceRequest
): Promise<DocumentUploadResponse> {
  return postJson<DocumentUploadResponse>(
    `/api/v1/documents/uploads/${encodeURIComponent(uploadId)}/governance`,
    payload
  );
}

export function indexPersonalDocument(uploadId: string): Promise<DocumentUploadResponse> {
  return postJson<DocumentUploadResponse>(
    `/api/v1/documents/uploads/${encodeURIComponent(uploadId)}/index`,
    {}
  );
}

export function fetchAgents(): Promise<AgentsResponse> {
  return getJsonWithAuditHeaders<AgentsResponse>("/api/v1/agents", auditAgentClientHeaders());
}

export function fetchAuditAgent(agentId: string): Promise<AgentDetailResponse> {
  return getJsonWithAuditHeaders<AgentDetailResponse>(
    `/api/v1/agents/${encodeURIComponent(agentId)}`,
    auditAgentClientHeaders()
  );
}

export function createAuditAgent(payload: AgentCreateRequest): Promise<AgentCreateResponse> {
  return postJson<AgentCreateResponse>("/api/v1/agents", payload, auditAgentClientHeaders());
}

export function fetchAuditAgentPromptVersions(
  agentId: string
): Promise<AgentPromptVersionsResponse> {
  return getJsonWithAuditHeaders<AgentPromptVersionsResponse>(
    `/api/v1/agents/${encodeURIComponent(agentId)}/prompt-versions`,
    auditAgentClientHeaders()
  );
}

export function createAuditAgentPromptVersion(
  agentId: string,
  payload: AgentPromptVersionCreateRequest
): Promise<AgentCreateResponse> {
  return postJson<AgentCreateResponse>(
    `/api/v1/agents/${encodeURIComponent(agentId)}/prompt-versions`,
    payload,
    auditAgentClientHeaders()
  );
}

export function rollbackAuditAgentPromptVersion(
  agentId: string,
  payload: AgentPromptVersionRollbackRequest
): Promise<AgentCreateResponse> {
  return postJson<AgentCreateResponse>(
    `/api/v1/agents/${encodeURIComponent(agentId)}/prompt-versions/rollback`,
    payload,
    auditAgentClientHeaders()
  );
}

export function reviewAuditAgentPromptVersion(
  agentId: string,
  payload: AgentPromptVersionReviewRequest
): Promise<AgentCreateResponse> {
  return postJson<AgentCreateResponse>(
    `/api/v1/agents/${encodeURIComponent(agentId)}/prompt-versions/review`,
    payload,
    auditAgentClientHeaders()
  );
}

export function updateAuditAgentLifecycle(
  agentId: string,
  payload: AgentLifecycleRequest
): Promise<AgentCreateResponse> {
  return postJson<AgentCreateResponse>(
    `/api/v1/agents/${encodeURIComponent(agentId)}/lifecycle`,
    payload,
    auditAgentClientHeaders()
  );
}

export function fetchAuditAgentInvocations(agentId: string): Promise<AgentInvocationsResponse> {
  return getJsonWithAuditHeaders<AgentInvocationsResponse>(
    `/api/v1/agents/${encodeURIComponent(agentId)}/invocations`,
    auditAgentClientHeaders()
  );
}

export function recordAuditAgentInvocation(
  agentId: string,
  payload: AgentInvocationCreateRequest
): Promise<AgentInvocationResponse> {
  return postJson<AgentInvocationResponse>(
    `/api/v1/agents/${encodeURIComponent(agentId)}/invocations`,
    payload,
    auditAgentClientHeaders()
  );
}

export function fetchAuditAgentFeedback(agentId: string): Promise<AgentFeedbackListResponse> {
  return getJsonWithAuditHeaders<AgentFeedbackListResponse>(
    `/api/v1/agents/${encodeURIComponent(agentId)}/feedback`,
    auditAgentClientHeaders()
  );
}

export function submitAuditAgentFeedback(
  agentId: string,
  payload: AgentFeedbackCreateRequest
): Promise<AgentFeedbackResponse> {
  return postJson<AgentFeedbackResponse>(
    `/api/v1/agents/${encodeURIComponent(agentId)}/feedback`,
    payload,
    auditAgentClientHeaders()
  );
}

export function fetchProjects(): Promise<ProjectsResponse> {
  return getJsonWithAuditHeaders<ProjectsResponse>("/api/v1/projects", auditProjectClientHeaders());
}

export function fetchProjectMembers(projectId: string): Promise<ProjectMembersResponse> {
  return getJsonWithAuditHeaders<ProjectMembersResponse>(
    `/api/v1/projects/${encodeURIComponent(projectId)}/members`,
    auditProjectClientHeaders(projectId)
  );
}

export function fetchProjectDashboard(projectId: string): Promise<ProjectDashboardResponse> {
  return getJsonWithAuditHeaders<ProjectDashboardResponse>(
    `/api/v1/projects/${encodeURIComponent(projectId)}/dashboard`,
    auditProjectClientHeaders(projectId)
  );
}

export function createProjectMember(
  projectId: string,
  payload: ProjectMemberCreateRequest
): Promise<ProjectMemberCreateResponse> {
  return postJson<ProjectMemberCreateResponse>(
    `/api/v1/projects/${encodeURIComponent(projectId)}/members`,
    payload,
    auditProjectClientHeaders(projectId)
  );
}
