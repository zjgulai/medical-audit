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
  AuditArtifactDownload,
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
  MedicalAuditImportPreflightRequest,
  MedicalAuditReportEntryRequest,
  MedicalAuditReviewStatusRequest,
  MedicalAuditReviewTaskRequest,
  MedicalAuditSupplementRequest,
  MedicalAuditWorkflowActionResponse,
  ProjectMemberCreateRequest,
  ProjectMemberCreateResponse,
  ProjectDashboardResponse,
  ProjectMembersResponse,
  ProjectsResponse,
  QueryHistoryResponse,
  QueryRequest,
  QueryResponse,
  RemediationWorkbenchResponse,
  ReportDraftCreateRequest,
  ReportDraftCreateResponse,
  ReportWorkbenchResponse,
  RulesWorkbenchResponse,
  SearchBackendStatusResponse,
  TableAnalysisUploadHistoryResponse,
  TableAnalysisUploadResponse
} from "./api-types";
import { auditAgentClientHeaders, auditClientHeaders, auditProjectClientHeaders } from "./audit-user";

export class BackendRequestError extends Error {
  readonly method: "POST";
  readonly path: string;
  readonly status: number;
  readonly detail: string | null;

  constructor(options: {
    readonly path: string;
    readonly status: number;
    readonly detail: string | null;
  }) {
    super(`Backend request failed: POST ${options.path} returned ${options.status}`);
    this.name = "BackendRequestError";
    this.method = "POST";
    this.path = options.path;
    this.status = options.status;
    this.detail = options.detail;
  }
}

export function isBackendRequestError(error: unknown): error is BackendRequestError {
  return error instanceof BackendRequestError;
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
    let detail: string | null = null;
    try {
      const errorPayload = await response.json() as unknown;
      if (
        typeof errorPayload === "object" &&
        errorPayload !== null &&
        "detail" in errorPayload &&
        typeof errorPayload.detail === "string"
      ) {
        detail = errorPayload.detail.trim() || null;
      }
    } catch {
      // Preserve the stable generic error contract when the body is absent or invalid JSON.
    }
    throw new BackendRequestError({ path, status: response.status, detail });
  }

  return (await response.json()) as T;
}

async function postForm<T>(
  path: string,
  formData: FormData,
  options: { readonly exposeValidationDetail?: boolean } = {}
): Promise<T> {
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
    if (options.exposeValidationDetail && (response.status === 413 || response.status === 422)) {
      let detail: string | null = null;
      try {
        const payload = await response.json() as unknown;
        if (
          typeof payload === "object" &&
          payload !== null &&
          "detail" in payload &&
          typeof payload.detail === "string" &&
          payload.detail.trim().length > 0
        ) {
          detail = payload.detail.trim();
        }
      } catch {
        // The generic error below preserves method, path, and status when the body is not JSON.
      }
      if (detail) {
        throw new Error(detail);
      }
    }
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

export function recordMedicalAuditImportPreflight(
  payload: MedicalAuditImportPreflightRequest
): Promise<MedicalAuditWorkflowActionResponse> {
  return postJson<MedicalAuditWorkflowActionResponse>(
    "/api/v1/audit-findings/import-preflight",
    payload
  );
}

export function createMedicalAuditReviewTask(
  findingKey: string,
  payload: MedicalAuditReviewTaskRequest = {}
): Promise<MedicalAuditWorkflowActionResponse> {
  return postJson<MedicalAuditWorkflowActionResponse>(
    `/api/v1/audit-findings/${encodeURIComponent(findingKey)}/review-task`,
    payload
  );
}

export function updateMedicalAuditReviewStatus(
  findingKey: string,
  payload: MedicalAuditReviewStatusRequest
): Promise<MedicalAuditWorkflowActionResponse> {
  return postJson<MedicalAuditWorkflowActionResponse>(
    `/api/v1/audit-findings/${encodeURIComponent(findingKey)}/review-status`,
    payload
  );
}

export function registerMedicalAuditSupplement(
  findingKey: string,
  payload: MedicalAuditSupplementRequest
): Promise<MedicalAuditWorkflowActionResponse> {
  return postJson<MedicalAuditWorkflowActionResponse>(
    `/api/v1/audit-findings/${encodeURIComponent(findingKey)}/supplemental-material`,
    payload
  );
}

export function addMedicalAuditFindingToReport(
  findingKey: string,
  payload: MedicalAuditReportEntryRequest = {}
): Promise<MedicalAuditWorkflowActionResponse> {
  return postJson<MedicalAuditWorkflowActionResponse>(
    `/api/v1/audit-findings/${encodeURIComponent(findingKey)}/report-entry`,
    payload
  );
}

export function fetchReportWorkbench(): Promise<ReportWorkbenchResponse> {
  return getJsonWithAuditHeaders<ReportWorkbenchResponse>("/api/v1/reports/workbench");
}

export function createReportDraft(
  payload: ReportDraftCreateRequest
): Promise<ReportDraftCreateResponse> {
  return postJson<ReportDraftCreateResponse>(
    "/api/v1/reports/drafts",
    payload,
    auditProjectClientHeaders(payload.project_key)
  );
}

function safeArtifactFilename(value: string): string | null {
  const basename = value.replaceAll("\\", "/").split("/").at(-1) ?? "";
  const sanitized = basename
    .replace(/[\u0000-\u001f\u007f]/g, "")
    .replace(/[:*?"<>|]/g, "-")
    .replace(/^[.\s]+/, "")
    .trim();
  return sanitized && sanitized !== "." && sanitized !== ".." ? sanitized.slice(0, 180) : null;
}

function contentDispositionFilename(disposition: string): string | null {
  const encodedMatch = /filename\*\s*=\s*(?:UTF-8'[^']*')?([^;]+)/i.exec(disposition);
  if (encodedMatch?.[1]) {
    const encoded = encodedMatch[1].trim().replace(/^"|"$/g, "");
    try {
      const decoded = safeArtifactFilename(decodeURIComponent(encoded));
      if (decoded) return decoded;
    } catch {
      // Fall through to the plain filename or a deterministic format fallback.
    }
  }
  const quotedMatch = /filename\s*=\s*"((?:\\.|[^"])*)"/i.exec(disposition);
  if (quotedMatch?.[1]) {
    return safeArtifactFilename(quotedMatch[1].replace(/\\(.)/g, "$1"));
  }
  const plainMatch = /filename\s*=\s*([^;]+)/i.exec(disposition);
  return plainMatch?.[1] ? safeArtifactFilename(plainMatch[1]) : null;
}

function artifactFallbackFilename(path: URL, contentType: string): string {
  const format = path.searchParams.get("format")?.toLowerCase();
  if (format === "docx" || contentType.includes("wordprocessingml")) return "audit-artifact.docx";
  if (format === "markdown" || contentType.includes("markdown")) return "audit-artifact.md";
  if (format === "json" || contentType.includes("json")) return "audit-artifact.json";
  return "audit-artifact.bin";
}

export async function downloadAuditArtifact(
  path: string,
  options: { readonly signal?: AbortSignal } = {}
): Promise<AuditArtifactDownload> {
  assertBackendProxyClientRuntime();
  const parsed = new URL(path, window.location.origin);
  if (
    !path.startsWith("/review-tasks/") ||
    parsed.origin !== window.location.origin ||
    !parsed.pathname.startsWith("/review-tasks/")
  ) {
    throw new Error("Audit artifact path must be an internal /review-tasks/ path");
  }

  const response = await fetch(path, {
    headers: {
      Accept: "application/octet-stream",
      ...auditClientHeaders()
    },
    cache: "no-store",
    ...(options.signal ? { signal: options.signal } : {})
  });
  if (!response.ok) {
    throw new Error(`Backend request failed: GET ${path} returned ${response.status}`);
  }

  const disposition = response.headers.get("Content-Disposition") ?? "";
  const contentType = response.headers.get("Content-Type") ?? "";
  return {
    blob: await response.blob(),
    filename: contentDispositionFilename(disposition) ?? artifactFallbackFilename(parsed, contentType)
  };
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
  return postForm<TableAnalysisUploadResponse>("/api/v1/analytics/table-upload", formData, {
    exposeValidationDetail: true
  });
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
