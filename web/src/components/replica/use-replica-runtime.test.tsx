import { act, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { fetchAgents, fetchGraphWorkbench } from "@/lib/api-client";
import type { AgentsResponse } from "@/lib/api-types";
import { writeAuditClientRole } from "@/lib/audit-user";
import { AuditUserProvider } from "@/components/shell/audit-user-context";

import {
  useReplicaAgentsData,
  useReplicaGraphData,
  useReplicaMarketInstallations
} from "./use-replica-runtime";

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

function agentsResponse(
  storeReady = true,
  name = "运行时只读助手",
  id = "agent-runtime-api",
  marketInstallations: AgentsResponse["market_installations"] = []
): AgentsResponse {
  return {
    items: [
      {
        id,
        name,
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
    market_installations: marketInstallations,
    store: { ready: storeReady, backend: "unit-test" }
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
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

function MarketInstallationsProbe() {
  const result = useReplicaMarketInstallations();

  return (
    <div data-testid="market-installations" data-status={result.status}>
      {Array.from(result.installedAgentIds).map(([templateId, agentId]) => (
        <span key={templateId}>{`${templateId}:${agentId}`}</span>
      ))}
    </div>
  );
}

describe("use-replica-runtime", () => {
  beforeEach(() => {
    window.localStorage.clear();
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
    vi.stubEnv("NEXT_PUBLIC_MEDICAL_AUDIT_AGENT_EXTENSION_PACK", "0");
    render(<AgentsRuntimeProbe mode="market" />);

    expect(screen.getByTestId("market-agents-runtime")).toHaveAttribute("data-source", "catalog");
    expect(screen.getByTestId("market-agents-runtime")).toHaveAttribute("data-status", "ready");
    expect(fetchAgents).not.toHaveBeenCalled();
  });

  it("restores the current identity market installations through a separate API read", async () => {
    vi.mocked(fetchAgents).mockResolvedValueOnce(agentsResponse(
      true,
      "运行时只读助手",
      "agent-runtime-api",
      [{ template_id: "template-medical-fund", agent_id: "agent-installed-fund" }]
    ));

    render(<MarketInstallationsProbe />);

    expect(screen.getByTestId("market-installations")).toHaveAttribute("data-status", "loading");
    expect(await screen.findByText("template-medical-fund:agent-installed-fund")).toBeInTheDocument();
    expect(screen.getByTestId("market-installations")).toHaveAttribute("data-status", "ready");
    expect(fetchAgents).toHaveBeenCalledTimes(1);
  });

  it("fails closed on ambiguous market installations and exposes degraded state", async () => {
    vi.mocked(fetchAgents).mockResolvedValueOnce({
      ...agentsResponse(),
      market_installations: [
        { template_id: "template-medical-fund", agent_id: "agent-legacy-1" }
      ],
      market_installation_issues: [
        {
          code: "ambiguous-market-installations",
          template_id: "template-medical-fund",
          agent_ids: ["agent-legacy-1", "agent-legacy-2"]
        }
      ]
    });

    render(<MarketInstallationsProbe />);

    await waitFor(() => {
      expect(screen.getByTestId("market-installations")).toHaveAttribute(
        "data-status",
        "degraded"
      );
    });
    expect(screen.queryByText(/template-medical-fund:/)).not.toBeInTheDocument();
  });

  it("does not expose a late installation response from the previous identity", async () => {
    const adminRead = deferred<AgentsResponse>();
    const memberRead = deferred<AgentsResponse>();
    vi.mocked(fetchAgents)
      .mockReturnValueOnce(adminRead.promise)
      .mockReturnValueOnce(memberRead.promise);

    render(
      <AuditUserProvider>
        <MarketInstallationsProbe />
      </AuditUserProvider>
    );
    act(() => writeAuditClientRole("member"));

    await act(async () => {
      memberRead.resolve(agentsResponse(
        true,
        "成员可见智能体",
        "member-agent",
        [{ template_id: "member-template", agent_id: "member-install" }]
      ));
      await memberRead.promise;
    });
    expect(await screen.findByText("member-template:member-install")).toBeInTheDocument();

    await act(async () => {
      adminRead.resolve(agentsResponse(
        true,
        "管理员智能体",
        "admin-agent",
        [{ template_id: "admin-template", agent_id: "admin-install" }]
      ));
      await adminRead.promise;
    });

    expect(screen.queryByText("admin-template:admin-install")).not.toBeInTheDocument();
    expect(screen.getByText("member-template:member-install")).toBeInTheDocument();
  });

  it("switches the opt-in extension pack on and off without leaking module-cached catalog state", () => {
    vi.stubEnv("NEXT_PUBLIC_MEDICAL_AUDIT_AGENT_EXTENSION_PACK", "0");
    const { rerender } = render(<AgentsRuntimeProbe mode="market" />);

    expect(screen.getByText("引用依据核验助手")).toBeInTheDocument();
    expect(screen.queryByText("超标准举办会议")).not.toBeInTheDocument();

    vi.stubEnv("NEXT_PUBLIC_MEDICAL_AUDIT_AGENT_EXTENSION_PACK", "1");
    rerender(<AgentsRuntimeProbe mode="market" />);

    expect(screen.getByText("超标准举办会议")).toBeInTheDocument();
    expect(screen.getByText("违法订立与招投标文件不符的合同或协议")).toBeInTheDocument();
    expect(screen.getByText("未经批准，擅自改变工程建设项目招标方式")).toBeInTheDocument();
    expect(fetchAgents).not.toHaveBeenCalled();

    vi.stubEnv("NEXT_PUBLIC_MEDICAL_AUDIT_AGENT_EXTENSION_PACK", "0");
    rerender(<AgentsRuntimeProbe mode="market" />);

    expect(screen.queryByText("超标准举办会议")).not.toBeInTheDocument();
    expect(screen.getByText("引用依据核验助手")).toBeInTheDocument();
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

  it("ignores a late personal API result after switching mine to market", async () => {
    const oldMineRead = deferred<AgentsResponse>();
    vi.mocked(fetchAgents).mockReturnValueOnce(oldMineRead.promise);
    const { rerender } = render(<AgentsRuntimeProbe mode="mine" />);

    expect(screen.getByTestId("mine-agents-runtime")).toHaveAttribute("data-status", "loading");

    rerender(<AgentsRuntimeProbe mode="market" />);
    expect(screen.getByTestId("market-agents-runtime")).toHaveAttribute("data-source", "catalog");
    expect(screen.getByTestId("market-agents-runtime")).toHaveAttribute("data-status", "ready");

    await act(async () => {
      oldMineRead.resolve(agentsResponse());
      await oldMineRead.promise;
      await Promise.resolve();
    });

    expect(screen.getByTestId("market-agents-runtime")).toHaveAttribute("data-source", "catalog");
    expect(screen.queryByText("运行时只读助手")).not.toBeInTheDocument();
  });

  it("clears old-role API data immediately and reloads for the new identity", async () => {
    const memberRead = deferred<AgentsResponse>();
    vi.mocked(fetchAgents)
      .mockResolvedValueOnce(agentsResponse(true, "管理员敏感智能体", "admin-agent"))
      .mockReturnValueOnce(memberRead.promise);

    render(
      <AuditUserProvider>
        <AgentsRuntimeProbe />
      </AuditUserProvider>
    );

    expect(await screen.findByText("管理员敏感智能体")).toBeInTheDocument();

    act(() => writeAuditClientRole("member"));

    expect(screen.getByTestId("mine-agents-runtime")).toHaveAttribute("data-status", "loading");
    expect(screen.queryByText("管理员敏感智能体")).not.toBeInTheDocument();

    await act(async () => {
      memberRead.resolve(agentsResponse(true, "成员可见智能体", "member-agent"));
      await memberRead.promise;
    });

    expect(await screen.findByText("成员可见智能体")).toBeInTheDocument();
    expect(fetchAgents).toHaveBeenCalledTimes(2);
  });

  it("ignores an old-role response that resolves after the new-role response", async () => {
    const adminRead = deferred<AgentsResponse>();
    const memberRead = deferred<AgentsResponse>();
    vi.mocked(fetchAgents)
      .mockReturnValueOnce(adminRead.promise)
      .mockReturnValueOnce(memberRead.promise);

    render(
      <AuditUserProvider>
        <AgentsRuntimeProbe />
      </AuditUserProvider>
    );
    act(() => writeAuditClientRole("member"));

    await act(async () => {
      memberRead.resolve(agentsResponse(true, "成员可见智能体", "member-agent"));
      await memberRead.promise;
    });
    expect(await screen.findByText("成员可见智能体")).toBeInTheDocument();

    await act(async () => {
      adminRead.resolve(agentsResponse(true, "迟到的管理员智能体", "late-admin-agent"));
      await adminRead.promise;
    });

    expect(screen.queryByText("迟到的管理员智能体")).not.toBeInTheDocument();
    expect(screen.getByText("成员可见智能体")).toBeInTheDocument();
  });

  it("keeps readonly graph workbench seed data visible as an adapter issue", async () => {
    vi.mocked(fetchGraphWorkbench).mockResolvedValueOnce({
      format: "graph-workbench-v1",
      generated_at: "2026-07-08T00:00:00Z",
      graph_id: "graph-seed-test",
      graph_title: "种子图谱",
      graph_scope: "只读种子拓扑",
      view: "knowledge",
      project_key: null,
      evidence_chain_status: "catalog",
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
