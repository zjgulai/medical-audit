import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { fetchAgents, fetchGraphWorkbench } from "@/lib/api-client";
import type { AgentsResponse } from "@/lib/api-types";

import { useReplicaAgentsData, useReplicaGraphData } from "./use-replica-runtime";

vi.mock("@/lib/api-client", () => ({
  fetchAgents: vi.fn(),
  fetchAnalysisUploadHistory: vi.fn(),
  fetchAuthSession: vi.fn(),
  fetchDocumentPermissions: vi.fn(),
  fetchDocumentSourceCollections: vi.fn(),
  fetchGraphWorkbench: vi.fn(),
  fetchKnowledgeBaseCatalog: vi.fn(),
  fetchProjects: vi.fn(),
  fetchQueryHistory: vi.fn(),
  fetchReportWorkbench: vi.fn(),
  runKnowledgeQuery: vi.fn()
}));

function agentsResponse(storeReady = true): AgentsResponse {
  return {
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
    store: { ready: storeReady, backend: "unit-test" }
  };
}

type AgentsRuntimeSnapshot = {
  readonly source: string;
  readonly status: string;
  readonly agentNames: readonly string[];
};

function AgentsRuntimeProbe({
  mode = "mine",
  onRender
}: {
  readonly mode?: "mine" | "market";
  readonly onRender?: (snapshot: AgentsRuntimeSnapshot) => void;
}) {
  const result = useReplicaAgentsData(mode);
  onRender?.({
    source: result.source,
    status: result.status,
    agentNames: result.data.agents.map((agent) => agent.name)
  });

  return (
    <div
      data-testid={`${mode}-agents-runtime`}
      data-source={result.source}
      data-status={result.status}
      data-outcome={result.outcome}
    >
      {result.data.agents.map((agent) => (
        <span key={agent.id}>{agent.name}</span>
      ))}
      {result.issues.map((issue) => (
        <em key={`${issue.surface}-${issue.code}`}>{issue.code}</em>
      ))}
    </div>
  );
}

function GraphRuntimeProbe() {
  const result = useReplicaGraphData();

  return (
    <div
      data-testid="graph-runtime"
      data-source={result.source}
      data-status={result.status}
      data-outcome={result.outcome}
    >
      <span>{result.data.title}</span>
      {result.issues.map((issue) => (
        <em key={`${issue.surface}-${issue.code}`}>{issue.code}</em>
      ))}
    </div>
  );
}

describe("use-replica-runtime", () => {
  beforeEach(() => {
    vi.mocked(fetchAgents).mockResolvedValue(agentsResponse());
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetAllMocks();
  });

  it("uses replica API reads by default", async () => {
    render(<AgentsRuntimeProbe />);

    await waitFor(() => {
      expect(screen.getByText("运行时只读助手")).toBeInTheDocument();
    });
    expect(screen.getByText("运行时只读助手").parentElement).toHaveAttribute("data-source", "api");
    expect(fetchAgents).toHaveBeenCalledTimes(1);
  });

  it("starts enabled API reads in a loading empty state without fixture records", () => {
    vi.mocked(fetchAgents).mockReturnValueOnce(new Promise(() => undefined));

    render(<AgentsRuntimeProbe />);

    expect(screen.getByTestId("mine-agents-runtime")).toHaveAttribute("data-source", "api");
    expect(screen.getByTestId("mine-agents-runtime")).toHaveAttribute("data-status", "loading");
    expect(screen.queryByText("模拟数据助手")).not.toBeInTheDocument();
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

  it("returns an API error without fixture substitution when an enabled read fails", async () => {
    vi.mocked(fetchAgents).mockRejectedValueOnce(new Error("read unavailable"));

    render(<AgentsRuntimeProbe />);

    await waitFor(() => {
      expect(screen.getByTestId("mine-agents-runtime")).toHaveAttribute("data-status", "error");
    });
    expect(screen.getByTestId("mine-agents-runtime")).toHaveAttribute("data-source", "api");
    expect(screen.queryByText("模拟数据助手")).not.toBeInTheDocument();
    expect(screen.getByText("api-read-failed")).toBeInTheDocument();
  });

  it("maps an unready API store to degraded while preserving API data", async () => {
    vi.mocked(fetchAgents).mockResolvedValueOnce(agentsResponse(false));

    render(<AgentsRuntimeProbe />);

    await waitFor(() => {
      expect(screen.getByTestId("mine-agents-runtime")).toHaveAttribute("data-status", "degraded");
    });
    expect(screen.getByTestId("mine-agents-runtime")).toHaveAttribute("data-source", "api");
    expect(screen.getByText("运行时只读助手")).toBeInTheDocument();
  });

  it("keeps the medical agent marketplace on the version-controlled catalog", () => {
    render(<AgentsRuntimeProbe mode="market" />);

    expect(screen.getByTestId("market-agents-runtime")).toHaveAttribute("data-source", "catalog");
    expect(screen.getByTestId("market-agents-runtime")).toHaveAttribute("data-status", "ready");
    expect(fetchAgents).not.toHaveBeenCalled();
  });

  it("switches from disabled fixtures to enabled loading data on the first mounted rerender", () => {
    vi.stubEnv("NEXT_PUBLIC_MEDICAL_AUDIT_REPLICA_API_READS", "0");
    const snapshots: AgentsRuntimeSnapshot[] = [];
    const recordSnapshot = (snapshot: AgentsRuntimeSnapshot) => snapshots.push(snapshot);
    const { rerender } = render(<AgentsRuntimeProbe onRender={recordSnapshot} />);

    expect(screen.getByTestId("mine-agents-runtime")).toHaveAttribute("data-source", "fixture");

    vi.mocked(fetchAgents).mockReturnValueOnce(new Promise(() => undefined));
    vi.stubEnv("NEXT_PUBLIC_MEDICAL_AUDIT_REPLICA_API_READS", "1");
    const firstEnabledRender = snapshots.length;
    rerender(<AgentsRuntimeProbe onRender={recordSnapshot} />);

    expect(snapshots[firstEnabledRender]).toEqual({
      source: "api",
      status: "loading",
      agentNames: []
    });
  });

  it("switches from enabled API data to disabled fixtures on the first mounted rerender", async () => {
    const snapshots: AgentsRuntimeSnapshot[] = [];
    const recordSnapshot = (snapshot: AgentsRuntimeSnapshot) => snapshots.push(snapshot);
    const { rerender } = render(<AgentsRuntimeProbe onRender={recordSnapshot} />);

    await waitFor(() => {
      expect(screen.getByTestId("mine-agents-runtime")).toHaveAttribute("data-status", "ready");
    });

    vi.stubEnv("NEXT_PUBLIC_MEDICAL_AUDIT_REPLICA_API_READS", "0");
    const firstDisabledRender = snapshots.length;
    rerender(<AgentsRuntimeProbe onRender={recordSnapshot} />);

    expect(snapshots[firstDisabledRender]).toEqual(expect.objectContaining({
      source: "fixture",
      status: "ready"
    }));
    expect(snapshots[firstDisabledRender]?.agentNames).toContain("模拟数据助手");
  });

  it("switches mine to market without exposing personal records on the first mounted rerender", async () => {
    const snapshots: AgentsRuntimeSnapshot[] = [];
    const recordSnapshot = (snapshot: AgentsRuntimeSnapshot) => snapshots.push(snapshot);
    const { rerender } = render(<AgentsRuntimeProbe mode="mine" onRender={recordSnapshot} />);

    await waitFor(() => {
      expect(screen.getByTestId("mine-agents-runtime")).toHaveAttribute("data-status", "ready");
    });

    const firstMarketRender = snapshots.length;
    rerender(<AgentsRuntimeProbe mode="market" onRender={recordSnapshot} />);

    expect(snapshots[firstMarketRender]).toEqual(expect.objectContaining({
      source: "catalog",
      status: "ready"
    }));
    expect(snapshots[firstMarketRender]?.agentNames).not.toContain("运行时只读助手");
    expect(snapshots[firstMarketRender]?.agentNames.length).toBeGreaterThan(0);
  });

  it("switches market to mine loading data on the first mounted rerender", () => {
    const snapshots: AgentsRuntimeSnapshot[] = [];
    const recordSnapshot = (snapshot: AgentsRuntimeSnapshot) => snapshots.push(snapshot);
    const { rerender } = render(<AgentsRuntimeProbe mode="market" onRender={recordSnapshot} />);

    vi.mocked(fetchAgents).mockReturnValueOnce(new Promise(() => undefined));
    const firstMineRender = snapshots.length;
    rerender(<AgentsRuntimeProbe mode="mine" onRender={recordSnapshot} />);

    expect(snapshots[firstMineRender]).toEqual({
      source: "api",
      status: "loading",
      agentNames: []
    });
  });

  it("keeps readonly graph workbench seed data visible as an adapter issue", async () => {
    vi.mocked(fetchGraphWorkbench).mockResolvedValueOnce({
      format: "graph-workbench-v1",
      generated_at: "2026-07-08T00:00:00Z",
      graph_id: "graph-seed-test",
      graph_title: "种子图谱",
      graph_scope: "只读种子拓扑",
      nodes: [
        {
          id: "node-project",
          label: "医保审计项目",
          kind: "项目",
          description: "用于测试后端种子图谱分类。",
          metric: "1 个专题",
          status: "待接入",
          href: "/projects",
          x: 50,
          y: 50
        }
      ],
      relations: [],
      metrics: {
        node_count: 1,
        node_kind_count: 1,
        node_kind_counts: {
          项目: 1,
          一级分类: 0,
          知识库: 0,
          文档: 0,
          规则: 0,
          疑点: 0,
          复核: 0,
          报告: 0,
          整改: 0
        },
        relation_count: 0,
        strong_relation_count: 0,
        pending_relation_count: 0
      },
      evidence_grade: "local-readonly-api",
      production_side_effect: "none",
      store: { ready: true, backend: "ReadonlyGraphWorkbenchSeed" }
    });

    render(<GraphRuntimeProbe />);

    await waitFor(() => {
      expect(screen.getByText("种子图谱")).toBeInTheDocument();
    });
    expect(screen.getByText("种子图谱").parentElement).toHaveAttribute("data-source", "api");
    expect(screen.getByText("种子图谱").parentElement).toHaveAttribute("data-status", "degraded");
    expect(screen.getByText("backend-seed-data")).toBeInTheDocument();
  });
});
