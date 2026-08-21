import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { GraphWorkbenchResponse, ProjectsResponse } from "@/lib/api-types";
import type { AuditClientRole } from "@/lib/audit-user";

import GraphPage from "./page";

const apiMocks = vi.hoisted(() => ({
  fetchGraphWorkbench: vi.fn(),
  fetchProjects: vi.fn()
}));

let currentRole: AuditClientRole = "admin";

vi.mock("@/lib/api-client", () => ({
  fetchGraphWorkbench: apiMocks.fetchGraphWorkbench,
  fetchProjects: apiMocks.fetchProjects
}));

vi.mock("@/components/shell/audit-user-context", () => ({
  useAuditUser: () => ({
    role: currentRole,
    setRole: vi.fn(),
    can: vi.fn(() => true)
  })
}));

// Keeps the pre-Task-8 implementation renderable while the new direct loader tests stay RED.
vi.mock("@/components/replica/use-replica-runtime", () => ({
  useReplicaGraphData: () => ({
    apiReadsEnabled: true,
    source: "api",
    status: "ready",
    issues: [],
    data: {
      title: "医疗审计知识工程",
      scope: "知识库、规则、疑点和报告的只读关系图。",
      nodes: [
        {
          id: "graph-node-project",
          label: "医疗审计知识工程",
          kind: "项目",
          metric: "2 类知识库",
          status: "已归集",
          description: "当前知识底座。",
          href: "/projects"
        },
        {
          id: "graph-source-medical-insurance-laws",
          label: "医保法规库",
          kind: "知识库",
          metric: "128 文档 / 600 chunks",
          status: "可引用",
          description: "医保法规、政策解释和处罚依据。",
          href: "/documents?source_collection=medical-insurance-laws",
          sourceCollection: "medical-insurance-laws",
          domain: "medical"
        }
      ],
      relations: [
        {
          id: "graph-medical-laws",
          sourceId: "graph-node-project",
          targetId: "graph-source-medical-insurance-laws",
          source: "医疗审计知识工程",
          relation: "包含",
          target: "医保法规库",
          evidence: "600 active embeddings",
          strength: "强"
        }
      ],
      metrics: {
        nodeCount: 2,
        nodeKindCount: 2,
        relationCount: 1,
        strongRelationCount: 1,
        pendingRelationCount: 0
      }
    }
  })
}));

function graphMetrics(nodeCount: number, relationCount: number) {
  return {
    node_count: nodeCount,
    node_kind_count: nodeCount > 0 ? 1 : 0,
    node_kind_counts: {
      项目: nodeCount > 0 ? 1 : 0,
      一级分类: 0,
      知识库: 0,
      文档: 0,
      规则: 0,
      疑点: 0,
      复核: 0,
      报告: 0,
      整改: 0
    },
    relation_count: relationCount,
    strong_relation_count: relationCount,
    pending_relation_count: 0
  };
}

function knowledgeGraph(): GraphWorkbenchResponse {
  return {
    format: "graph-workbench-v1",
    generated_at: "2026-07-13T00:00:00Z",
    graph_id: "SELF-CHECK-FUND-20260607",
    graph_title: "医疗审计知识工程",
    graph_scope: "生产知识库目录、文档检索和审计问答共同使用的知识底座。",
    view: "knowledge",
    project_key: null,
    evidence_chain_status: "catalog",
    nodes: [
      {
        id: "graph-source-medical-insurance-laws",
        label: "医保法规库",
        kind: "知识库",
        metric: "128 文档 / 600 chunks",
        status: "可引用",
        description: "医保法规、政策解释和处罚依据。",
        href: "/documents?source_collection=medical-insurance-laws",
        sourceCollection: "medical-insurance-laws",
        domain: "medical",
        x: 100,
        y: 250
      }
    ],
    relations: [],
    metrics: graphMetrics(1, 0),
    evidence_grade: "local-readonly-api",
    production_side_effect: "none",
    store: { ready: true, backend: "KnowledgeCatalogGraphBuilder" }
  } as GraphWorkbenchResponse;
}

function projectGraph(projectKey: string, options: { empty?: boolean; ready?: boolean } = {}): GraphWorkbenchResponse {
  const root = {
    id: `project:${projectKey}`,
    label: `${projectKey} 项目`,
    kind: "项目" as const,
    metric: options.empty ? "0 条项目证据" : "1 条项目证据",
    status: "已归集" as const,
    description: options.empty ? "当前项目暂无证据。" : "当前项目已有真实证据。",
    href: `/projects?project=${projectKey}`,
    x: 100,
    y: 250
  };
  const finding = {
    id: `finding:${projectKey}-F1`,
    label: `疑点 ${projectKey}-F1`,
    kind: "疑点" as const,
    metric: "2 项证据",
    status: "待复核" as const,
    description: "项目疑点已持久化。",
    href: "/findings",
    x: 320,
    y: 120
  };
  const empty = options.empty === true;
  return {
    format: "graph-workbench-v1",
    generated_at: "2026-07-13T00:00:00Z",
    graph_id: projectKey,
    graph_title: `${projectKey} 项目证据链`,
    graph_scope: "仅组织当前项目已持久化的疑点、复核、报告和整改证据。",
    view: "project",
    project_key: projectKey,
    evidence_chain_status: empty ? "empty" : "ready",
    nodes: empty ? [root] : [root, finding],
    relations: empty ? [] : [
      {
        id: `project-finding:${projectKey}`,
        sourceId: root.id,
        targetId: finding.id,
        source: projectKey,
        relation: "发现",
        target: `${projectKey}-F1`,
        evidence: "真实项目疑点",
        strength: "强"
      }
    ],
    metrics: graphMetrics(empty ? 1 : 2, empty ? 0 : 1),
    evidence_grade: "live-store-readonly",
    production_side_effect: "none",
    store: {
      ready: options.ready !== false,
      backend: {
        audit_findings: "SqlAlchemyAuditFindingStore",
        review_tasks: "JsonReviewTaskStore"
      }
    }
  } as unknown as GraphWorkbenchResponse;
}

function projects(...keys: string[]): ProjectsResponse {
  return {
    items: keys.map((key) => ({
      id: key,
      name: `${key} 项目`,
      audit_topic: "医保基金审计",
      organization_name: "示例医院",
      member_count: 2,
      creator: "审计部",
      creator_user_identifier: "next-admin",
      created_at: "2026-07-13T00:00:00Z",
      status: "进行中" as const,
      operation_label: "进入项目",
      source: "system-default" as const
    })),
    roles: [],
    statuses: [],
    project_statuses: [],
    store: { ready: true, backend: "SqlAlchemyProjectMemberStore" }
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

describe("GraphPage", () => {
  beforeEach(() => {
    currentRole = "admin";
    apiMocks.fetchGraphWorkbench.mockImplementation(async (options?: { view?: string; projectKey?: string }) => (
      options?.view === "project" ? projectGraph(options.projectKey ?? "") : knowledgeGraph()
    ));
    apiMocks.fetchProjects.mockResolvedValue(projects("PROJECT-A", "PROJECT-B"));
  });

  afterEach(() => {
    window.history.pushState({}, "", "/graph");
    vi.clearAllMocks();
    vi.unstubAllEnvs();
  });

  it("starts knowledge and visible-project reads together and keeps exactly two working tabs", async () => {
    const knowledgeRead = deferred<GraphWorkbenchResponse>();
    const projectListRead = deferred<ProjectsResponse>();
    apiMocks.fetchGraphWorkbench.mockReturnValueOnce(knowledgeRead.promise);
    apiMocks.fetchProjects.mockReturnValueOnce(projectListRead.promise);

    render(<GraphPage />);

    expect(apiMocks.fetchGraphWorkbench).toHaveBeenCalledWith(undefined);
    expect(apiMocks.fetchProjects).toHaveBeenCalledTimes(1);

    await act(async () => {
      knowledgeRead.resolve(knowledgeGraph());
      projectListRead.resolve(projects("PROJECT-A"));
      await Promise.all([knowledgeRead.promise, projectListRead.promise]);
    });

    const tablist = screen.getByRole("tablist", { name: "图谱视图" });
    expect(within(tablist).getAllByRole("tab")).toHaveLength(2);
    expect(within(tablist).getByRole("tab", { name: "知识依据" })).toHaveAttribute("aria-selected", "true");
    expect(within(tablist).getByRole("tab", { name: "项目证据链" })).toHaveAttribute("aria-selected", "false");
    expect(screen.getByText("业务流程图谱：等待医院流程输入")).toHaveAttribute("aria-disabled", "true");
  });

  it("supports arrow-key navigation between graph tabs", async () => {
    render(<GraphPage />);
    const knowledgeTab = await screen.findByRole("tab", { name: "知识依据" });
    const projectTab = screen.getByRole("tab", { name: "项目证据链" });

    knowledgeTab.focus();
    fireEvent.keyDown(knowledgeTab, { key: "ArrowRight" });
    expect(projectTab).toHaveFocus();
    expect(projectTab).toHaveAttribute("aria-selected", "true");

    fireEvent.keyDown(projectTab, { key: "ArrowLeft" });
    expect(knowledgeTab).toHaveFocus();
    expect(knowledgeTab).toHaveAttribute("aria-selected", "true");
  });

  it("keeps knowledge source scope in documents and chat links", async () => {
    window.history.pushState({}, "", "/graph?source_collection=medical-insurance-laws");
    render(<GraphPage />);

    await screen.findByText("当前范围：法规政策");
    fireEvent.click(within(screen.getByLabelText("图谱节点")).getByRole("button", { name: /医保法规库/ }));

    expect(screen.getAllByRole("link", { name: "进入文档检索" })[0]).toHaveAttribute(
      "href",
      "/documents?source_collection=medical-insurance-laws"
    );
    expect(screen.getByRole("link", { name: "进入 AI 对话" })).toHaveAttribute(
      "href",
      expect.stringContaining("source_collection=medical-insurance-laws")
    );
  });

  it("requires an explicit project selection before requesting the project graph", async () => {
    render(<GraphPage />);
    await screen.findByRole("option", { name: "PROJECT-A 项目" });

    expect(apiMocks.fetchGraphWorkbench).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("tab", { name: "项目证据链" }));
    expect(screen.getByText("请先选择一个可见项目")).toBeInTheDocument();
    expect(apiMocks.fetchGraphWorkbench).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("link", { name: "进入项目管理" })).not.toBeInTheDocument();

    fireEvent.change(screen.getByRole("combobox", { name: "证据链所属项目" }), {
      target: { value: "PROJECT-A" }
    });

    await waitFor(() => {
      expect(apiMocks.fetchGraphWorkbench).toHaveBeenLastCalledWith({
        view: "project",
        projectKey: "PROJECT-A"
      });
    });
    expect(await screen.findByText("PROJECT-A 项目证据链")).toBeInTheDocument();
    for (const link of screen.getAllByRole("link", { name: "进入项目管理" })) {
      expect(link).toHaveAttribute("href", "/projects?project=PROJECT-A");
    }
    expect(screen.queryByRole("link", { name: "进入 AI 对话" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "进入文档检索" })).not.toBeInTheDocument();
  });

  it("shows a root-only project response as an explicit empty evidence chain", async () => {
    apiMocks.fetchGraphWorkbench.mockImplementation(async (options?: { view?: string; projectKey?: string }) => (
      options?.view === "project" ? projectGraph(options.projectKey ?? "", { empty: true }) : knowledgeGraph()
    ));
    render(<GraphPage />);
    await screen.findByRole("option", { name: "PROJECT-A 项目" });

    fireEvent.change(screen.getByRole("combobox", { name: "证据链所属项目" }), {
      target: { value: "PROJECT-A" }
    });
    fireEvent.click(screen.getByRole("tab", { name: "项目证据链" }));

    expect(await screen.findByText("当前项目暂无证据链")).toBeInTheDocument();
    expect(screen.queryByText(/乡村振兴|县级财政专户|建设运维单位/)).not.toBeInTheDocument();
  });

  it("retries a degraded project store with the current view and project key", async () => {
    apiMocks.fetchGraphWorkbench.mockImplementation(async (options?: { view?: string; projectKey?: string }) => (
      options?.view === "project"
        ? projectGraph(options.projectKey ?? "", { ready: false })
        : knowledgeGraph()
    ));
    render(<GraphPage />);
    await screen.findByRole("option", { name: "PROJECT-A 项目" });

    fireEvent.change(screen.getByRole("combobox", { name: "证据链所属项目" }), {
      target: { value: "PROJECT-A" }
    });
    fireEvent.click(screen.getByRole("tab", { name: "项目证据链" }));

    expect(await screen.findByText("项目证据存储尚未就绪")).toBeInTheDocument();
    const requestCountBeforeRetry = apiMocks.fetchGraphWorkbench.mock.calls.length;
    fireEvent.click(screen.getByRole("button", { name: "重试当前视图" }));

    await waitFor(() => {
      expect(apiMocks.fetchGraphWorkbench).toHaveBeenCalledTimes(requestCountBeforeRetry + 1);
    });
    expect(apiMocks.fetchGraphWorkbench).toHaveBeenLastCalledWith({
      view: "project",
      projectKey: "PROJECT-A"
    });
    expect(screen.getByRole("tab", { name: "项目证据链" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("combobox", { name: "证据链所属项目" })).toHaveValue("PROJECT-A");
  });

  it("does not invent topology lines for response relations", async () => {
    const { container } = render(<GraphPage />);

    await screen.findByText("local-readonly-api");
    expect(container.querySelectorAll(".replica-graph-line")).toHaveLength(0);

    await screen.findByRole("option", { name: "PROJECT-A 项目" });
    fireEvent.change(screen.getByRole("combobox", { name: "证据链所属项目" }), {
      target: { value: "PROJECT-A" }
    });
    fireEvent.click(screen.getByRole("tab", { name: "项目证据链" }));

    expect(await screen.findByText("PROJECT-A 项目证据链")).toBeInTheDocument();
    expect(container.querySelectorAll(".replica-graph-line")).toHaveLength(0);
    expect(within(screen.getByLabelText("关系证据")).getAllByRole("button")).toHaveLength(1);
  });

  it("keeps every returned project node and relation accessible", async () => {
    apiMocks.fetchGraphWorkbench.mockImplementation(async (options?: { view?: string; projectKey?: string }) => {
      if (options?.view !== "project") return knowledgeGraph();
      const projectKey = options.projectKey ?? "";
      const base = projectGraph(projectKey);
      const root = base.nodes[0];
      const evidenceNodes = Array.from({ length: 9 }, (_, index) => ({
        id: `finding:${projectKey}-F${index + 1}`,
        label: `疑点 ${projectKey}-F${index + 1}`,
        kind: "疑点" as const,
        metric: `${index + 1} 项证据`,
        status: "待复核" as const,
        description: `项目证据节点 ${index + 1}`,
        href: "/findings",
        x: 320,
        y: 120
      }));
      const relations = evidenceNodes.map((node, index) => ({
        id: `project-finding:${projectKey}-${index + 1}`,
        sourceId: root.id,
        targetId: node.id,
        source: projectKey,
        relation: "发现",
        target: node.label,
        evidence: `项目证据 ${index + 1}`,
        strength: "强" as const
      }));
      return {
        ...base,
        nodes: [root, ...evidenceNodes],
        relations,
        metrics: graphMetrics(10, 9)
      };
    });
    render(<GraphPage />);
    await screen.findByRole("option", { name: "PROJECT-A 项目" });
    fireEvent.change(screen.getByRole("combobox", { name: "证据链所属项目" }), {
      target: { value: "PROJECT-A" }
    });
    fireEvent.click(screen.getByRole("tab", { name: "项目证据链" }));

    const graphMap = await screen.findByLabelText("图谱节点");
    expect(within(graphMap).getByRole("button", { name: /疑点 PROJECT-A-F9/ })).toBeInTheDocument();
    expect(within(screen.getByLabelText("关系证据")).getByRole("button", { name: /项目证据 9/ })).toBeInTheDocument();
  });

  it("isolates stale project responses across project and role changes", async () => {
    const projectARead = deferred<GraphWorkbenchResponse>();
    const projectBRead = deferred<GraphWorkbenchResponse>();
    const directorKnowledgeRead = deferred<GraphWorkbenchResponse>();
    const directorProjectsRead = deferred<ProjectsResponse>();
    apiMocks.fetchGraphWorkbench.mockImplementation((options?: { view?: string; projectKey?: string }) => {
      if (options?.projectKey === "PROJECT-A") return projectARead.promise;
      if (options?.projectKey === "PROJECT-B") return projectBRead.promise;
      return Promise.resolve(knowledgeGraph());
    });
    const view = render(<GraphPage />);
    await screen.findByRole("option", { name: "PROJECT-A 项目" });
    fireEvent.click(screen.getByRole("tab", { name: "项目证据链" }));
    fireEvent.change(screen.getByRole("combobox", { name: "证据链所属项目" }), {
      target: { value: "PROJECT-A" }
    });
    fireEvent.change(screen.getByRole("combobox", { name: "证据链所属项目" }), {
      target: { value: "PROJECT-B" }
    });

    await act(async () => {
      projectBRead.resolve(projectGraph("PROJECT-B"));
      await projectBRead.promise;
    });
    expect(screen.getByText("PROJECT-B 项目证据链")).toBeInTheDocument();

    await act(async () => {
      projectARead.resolve(projectGraph("PROJECT-A"));
      await projectARead.promise;
    });
    expect(screen.getByText("PROJECT-B 项目证据链")).toBeInTheDocument();
    expect(screen.queryByText("PROJECT-A 项目证据链")).not.toBeInTheDocument();

    apiMocks.fetchGraphWorkbench.mockReturnValueOnce(directorKnowledgeRead.promise);
    apiMocks.fetchProjects.mockReturnValueOnce(directorProjectsRead.promise);
    currentRole = "director";
    view.rerender(<GraphPage />);
    expect(screen.getByRole("tab", { name: "知识依据" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("combobox", { name: "证据链所属项目" })).toHaveValue("");

    await act(async () => {
      directorKnowledgeRead.resolve({
        ...knowledgeGraph(),
        graph_title: "主任知识依据"
      });
      directorProjectsRead.resolve(projects("DIRECTOR-A"));
      await Promise.all([directorKnowledgeRead.promise, directorProjectsRead.promise]);
    });
    expect(await screen.findByText("主任知识依据")).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "DIRECTOR-A 项目" })).toBeInTheDocument();
  });

  it("keeps knowledge ready when the independent project list lane fails", async () => {
    apiMocks.fetchProjects.mockRejectedValueOnce(new Error("projects offline"));

    render(<GraphPage />);

    expect(await screen.findByText("医疗审计知识工程")).toBeInTheDocument();
    expect(screen.getByText("项目列表读取失败，仅知识依据可用。")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "知识依据" })).toHaveAttribute("aria-selected", "true");
  });

  it("clears a selected project when a refreshed visible-project list no longer contains it", async () => {
    render(<GraphPage />);
    await screen.findByRole("option", { name: "PROJECT-A 项目" });
    fireEvent.change(screen.getByRole("combobox", { name: "证据链所属项目" }), {
      target: { value: "PROJECT-A" }
    });
    fireEvent.click(screen.getByRole("tab", { name: "项目证据链" }));
    expect(await screen.findByText("PROJECT-A 项目证据链")).toBeInTheDocument();

    apiMocks.fetchProjects.mockResolvedValueOnce(projects("PROJECT-B"));
    fireEvent.click(screen.getByRole("button", { name: "刷新知识与项目目录" }));

    expect(await screen.findByText("原项目已不可见，请重新选择")).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "证据链所属项目" })).toHaveValue("");
    expect(screen.getByText("请先选择一个可见项目")).toBeInTheDocument();
    expect(screen.queryByText("PROJECT-A 项目证据链")).not.toBeInTheDocument();
  });

  it.each([
    [404, "项目不可见或已不存在"],
    [503, "项目证据存储未就绪"]
  ])("maps project graph HTTP %s without showing fixture data", async (status, message) => {
    apiMocks.fetchGraphWorkbench.mockImplementation(async (options?: { view?: string }) => {
      if (options?.view === "project") {
        throw Object.assign(new Error(`Backend request failed: GET graph returned ${status}`), { status });
      }
      return knowledgeGraph();
    });
    render(<GraphPage />);
    await screen.findByRole("option", { name: "PROJECT-A 项目" });
    fireEvent.change(screen.getByRole("combobox", { name: "证据链所属项目" }), {
      target: { value: "PROJECT-A" }
    });
    fireEvent.click(screen.getByRole("tab", { name: "项目证据链" }));

    expect(await screen.findByText(message)).toBeInTheDocument();
    expect(screen.queryByText(/乡村振兴|县级财政专户|建设运维单位/)).not.toBeInTheDocument();
  });
});
