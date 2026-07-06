import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchAgents } from "@/lib/api-client";

import { useReplicaAgentsData } from "./use-replica-runtime";

vi.mock("@/lib/api-client", () => ({
  fetchAgents: vi.fn(async () => ({
    items: [
      {
        id: "agent-runtime-api",
        name: "运行时只读助手",
        category: "业务类",
        topic: "医保基金审计",
        prompt: "用于测试运行时只读 adapter。",
        knowledge_base: "医保法规库",
        project_name: "医保基金审计",
        status: "active",
        prompt_version: 1,
        prompt_version_key: "agent-runtime-api@v1",
        visibility_scope: "project",
        allowed_roles: ["admin"],
        prompt_versions: [],
        created_by: "system",
        updated_at: "2026-07-04T00:00:00Z",
        source: "system-default",
        metadata: { summary: "运行时 adapter 测试数据。" }
      }
    ],
    categories: ["业务类"],
    store: { ready: true, backend: "unit-test" }
  })),
  fetchAnalysisUploadHistory: vi.fn(),
  fetchAuthSession: vi.fn(),
  fetchDocumentPermissions: vi.fn(),
  fetchDocumentSourceCollections: vi.fn(),
  fetchGraphWorkbench: vi.fn(),
  fetchProjects: vi.fn(),
  fetchQueryHistory: vi.fn(),
  fetchReportWorkbench: vi.fn(),
  runKnowledgeQuery: vi.fn()
}));

function AgentsRuntimeProbe() {
  const result = useReplicaAgentsData("mine");

  return (
    <div data-source={result.source} data-status={result.status}>
      {result.data.agents.map((agent) => (
        <span key={agent.id}>{agent.name}</span>
      ))}
      {result.issues.map((issue) => (
        <em key={`${issue.surface}-${issue.code}`}>{issue.code}</em>
      ))}
    </div>
  );
}

describe("use-replica-runtime", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.clearAllMocks();
  });

  it("uses replica API reads by default", async () => {
    render(<AgentsRuntimeProbe />);

    await waitFor(() => {
      expect(screen.getByText("运行时只读助手")).toBeInTheDocument();
    });
    expect(screen.getByText("运行时只读助手").parentElement).toHaveAttribute("data-source", "api");
    expect(fetchAgents).toHaveBeenCalledTimes(1);
  });

  it("can explicitly disable replica API reads", async () => {
    vi.stubEnv("NEXT_PUBLIC_MEDICAL_AUDIT_REPLICA_API_READS", "0");

    render(<AgentsRuntimeProbe />);

    expect(screen.getByText("模拟数据助手")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("模拟数据助手").parentElement).toHaveAttribute("data-status", "ready");
    });
    expect(screen.getByText("模拟数据助手").parentElement).toHaveAttribute("data-source", "fixture");
    expect(fetchAgents).not.toHaveBeenCalled();
  });

  it("falls back to fixture data when an enabled read API fails", async () => {
    vi.mocked(fetchAgents).mockRejectedValueOnce(new Error("read unavailable"));

    render(<AgentsRuntimeProbe />);

    await waitFor(() => {
      expect(screen.getByText("模拟数据助手")).toBeInTheDocument();
    });
    expect(screen.getByText("模拟数据助手").parentElement).toHaveAttribute("data-source", "fixture");
    expect(screen.getByText("api-read-failed")).toBeInTheDocument();
  });
});
