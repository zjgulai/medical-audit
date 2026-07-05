import { describe, expect, it } from "vitest";

import { backendApiEndpoints } from "./api-endpoints";

describe("backendApiEndpoints", () => {
  it("keeps stable top-level API paths centralized", () => {
    expect(backendApiEndpoints.backendHealth).toBe("/api/backend/health");
    expect(backendApiEndpoints.authSession).toBe("/api/v1/auth/session");
    expect(backendApiEndpoints.query).toBe("/api/v1/query");
    expect(backendApiEndpoints.documentUploads).toBe("/api/v1/documents/uploads");
    expect(backendApiEndpoints.agents).toBe("/api/v1/agents");
    expect(backendApiEndpoints.projects).toBe("/api/v1/projects");
  });

  it("encodes dynamic path segments before building endpoint paths", () => {
    expect(backendApiEndpoints.documentUploadGovernance("upload/a b")).toBe(
      "/api/v1/documents/uploads/upload%2Fa%20b/governance"
    );
    expect(backendApiEndpoints.agentPromptVersionReview("agent/a b")).toBe(
      "/api/v1/agents/agent%2Fa%20b/prompt-versions/review"
    );
    expect(backendApiEndpoints.projectMembers("project/a b")).toBe(
      "/api/v1/projects/project%2Fa%20b/members"
    );
  });

  it("builds optional query parameters without changing the base endpoint", () => {
    expect(backendApiEndpoints.queryLogs()).toBe("/api/v1/query/logs?limit=8");
    expect(backendApiEndpoints.auditFindings()).toBe("/api/v1/audit-findings");
    expect(backendApiEndpoints.auditFindings("pending review")).toBe(
      "/api/v1/audit-findings?review_status=pending+review"
    );
  });
});
