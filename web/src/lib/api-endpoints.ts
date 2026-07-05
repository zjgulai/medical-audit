const encodePathSegment = (value: string): string => encodeURIComponent(value);

export const backendApiEndpoints = {
  backendHealth: "/api/backend/health",
  searchBackendStatus: "/api/backend/index/search-backend",
  authSession: "/api/v1/auth/session",
  query: "/api/v1/query",
  queryLogs: (limit = 8): string => `/api/v1/query/logs?limit=${limit}`,
  auditFindings: (reviewStatus?: string): string => {
    const params = new URLSearchParams();
    if (reviewStatus) {
      params.set("review_status", reviewStatus);
    }
    const queryString = params.toString();
    return `/api/v1/audit-findings${queryString ? `?${queryString}` : ""}`;
  },
  reportWorkbench: "/api/v1/reports/workbench",
  graphWorkbench: "/api/v1/graph/workbench",
  rulesWorkbench: "/api/v1/rules/workbench",
  remediationWorkbench: "/api/v1/remediation/workbench",
  archiveWorkbench: "/api/v1/archive/workbench",
  analyticsTableUpload: "/api/v1/analytics/table-upload",
  analyticsTableUploads: "/api/v1/analytics/table-uploads",
  documentPermissions: "/api/v1/documents/permissions",
  documentUploads: "/api/v1/documents/uploads",
  documentUploadGovernance: (uploadId: string): string =>
    `/api/v1/documents/uploads/${encodePathSegment(uploadId)}/governance`,
  documentUploadIndex: (uploadId: string): string =>
    `/api/v1/documents/uploads/${encodePathSegment(uploadId)}/index`,
  agents: "/api/v1/agents",
  agent: (agentId: string): string => `/api/v1/agents/${encodePathSegment(agentId)}`,
  agentPromptVersions: (agentId: string): string =>
    `/api/v1/agents/${encodePathSegment(agentId)}/prompt-versions`,
  agentPromptVersionRollback: (agentId: string): string =>
    `/api/v1/agents/${encodePathSegment(agentId)}/prompt-versions/rollback`,
  agentPromptVersionReview: (agentId: string): string =>
    `/api/v1/agents/${encodePathSegment(agentId)}/prompt-versions/review`,
  agentLifecycle: (agentId: string): string =>
    `/api/v1/agents/${encodePathSegment(agentId)}/lifecycle`,
  agentInvocations: (agentId: string): string =>
    `/api/v1/agents/${encodePathSegment(agentId)}/invocations`,
  agentFeedback: (agentId: string): string =>
    `/api/v1/agents/${encodePathSegment(agentId)}/feedback`,
  projects: "/api/v1/projects",
  projectMembers: (projectId: string): string =>
    `/api/v1/projects/${encodePathSegment(projectId)}/members`
} as const;
