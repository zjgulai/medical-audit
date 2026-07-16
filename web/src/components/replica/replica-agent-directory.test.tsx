import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { BackendRequestError, createAuditAgent } from "@/lib/api-client";
import type { AgentCreateRequest } from "@/lib/api-types";
import { auditExtensionValidationCatalog } from "@/lib/audit-agent-catalog";
import { AUDIT_ROLE_STORAGE_KEY, writeAuditClientRole } from "@/lib/audit-user";
import type { ReferenceAgentCard } from "@/lib/reference-replica-data";
import { AuditUserProvider } from "@/components/shell/audit-user-context";

import {
  getMarketAgentInstallBlockReason,
  ReplicaAgentDirectory
} from "./replica-agent-directory";

const installedMarketAgentIds = new Map<string, string>();
let marketInstallationsStatus: "loading" | "ready" | "degraded" | "error" = "ready";

vi.mock("@/lib/api-client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api-client")>()),
  createAuditAgent: vi.fn(async (payload: AgentCreateRequest) => {
    const templateId = String(payload.metadata?.template_id ?? "unknown-template");
    const installedId = `installed-${templateId}`;
    return {
      item: {
        id: installedId,
        name: payload.name,
        category: payload.category,
        topic: payload.topic,
        prompt: payload.prompt,
        knowledge_base: payload.knowledge_base,
        project_name: payload.project_name,
        status: "active",
        prompt_version: 1,
        prompt_version_key: `${installedId}@v1`,
        visibility_scope: "project",
        allowed_roles: payload.allowed_roles,
        prompt_versions: [],
        created_by: "next-admin",
        updated_at: "2026-07-06T00:00:00Z",
        source: "custom",
        metadata: payload.metadata
      },
      store: { ready: true, backend: "SqlAlchemyAgentStore" }
    };
  })
}));

vi.mock("./use-replica-runtime", async () => {
  const { auditExtensionValidationCatalog: extensionCatalog } = await import("@/lib/audit-agent-catalog");
  return {
    useReplicaMarketInstallations: () => ({
      apiReadsEnabled: true,
      installedAgentIds: installedMarketAgentIds,
      status: marketInstallationsStatus
    }),
    useReplicaAgentsData: () => ({
      apiReadsEnabled: false,
      source: "fixture",
      status: "ready",
      issues: [],
      data: {
        categories: ["财务收支审计", "采购招标审计", "工程审计"],
        agents: [
          makeAgent("template-medical-fund", "医保核验", "财务收支审计", "医保基金使用合规"),
          makeAgent("template-travel", "出国核验", "财务收支审计", "财务收支审计"),
          makeAgent("template meeting/2026", "会议核验", "财务收支审计", "会议费审计"),
          makeAgent("template-procurement", "招标核验", "采购招标审计", "采购招标审计"),
          makeAgent("template-bid", "定标核验", "采购招标审计", "定标复核"),
          makeAgent("template-engineering", "工程核验", "工程审计", "工程审计"),
          makeAgent("template-asset", "资产核验", "固定资产审计", "资产审计"),
          makeAgent("template-research", "科研核验", "审计科研", "审计科研"),
          makeAgent("template-contract", "合同核验", "采购招标审计", "合同审计"),
          makeAgent("template-invoice", "发票核验", "财务收支审计", "票据审计"),
          makeAgent("template-budget", "预算核验", "财务收支审计", "预算执行审计"),
          makeAgent("template-data", "数据核验", "工具智能体", "数据质量审计"),
          makeAgent("template-archive", "档案核验", "工具智能体", "档案完整性审计"),
          ...extensionCatalog
        ]
      }
    })
  };
});

function makeAgent(
  id: string,
  name: string,
  category: string,
  topic: string
): ReferenceAgentCard {
  return {
    id,
    name,
    category,
    summary: `${name}用于核验审计资料、证据链和风险描述。`,
    project: "智能体广场",
    topic,
    initial: name.slice(0, 1),
    tone: "blue",
    prompt: `## ${name}\n请围绕${topic}输出风险判断、证据依据和待补材料。`,
    sourceFile: `${category}.ods`,
    avatarSeed: `${id}-avatar`,
    templateKey: `${id}-template`
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

function installedAgentResponse(id: string, name: string): Awaited<ReturnType<typeof createAuditAgent>> {
  return {
    item: {
      id,
      name,
      category: "业务类",
      topic: "医保基金使用合规",
      prompt: "请输出风险判断、证据依据和待补材料。",
      knowledge_base: "医保基金合规知识库",
      project_name: "医保基金使用合规专项自查",
      status: "active",
      prompt_version: 1,
      prompt_version_key: `${id}@v1`,
      visibility_scope: "project",
      allowed_roles: ["admin", "technician", "director", "member"],
      prompt_versions: [],
      created_by: "next-admin",
      updated_at: "2026-07-13T00:00:00Z",
      source: "custom",
      metadata: {}
    },
    store: { ready: true, backend: "SqlAlchemyAgentStore" }
  };
}

describe("ReplicaAgentDirectory", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    installedMarketAgentIds.clear();
    marketInstallationsStatus = "ready";
  });

  it("shows exactly twelve agents on page one and the thirteenth on page two", () => {
    render(<ReplicaAgentDirectory mode="market" />);

    expect(screen.getByRole("button", { name: /财务收支审计/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /采购招标审计/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^业务类/ })).not.toBeInTheDocument();

    const firstPageNames = screen.getAllByRole("button", { name: /^详情：/ }).map((button) => button.getAttribute("aria-label"));
    expect(firstPageNames).toEqual([
      "详情：医保核验",
      "详情：出国核验",
      "详情：会议核验",
      "详情：招标核验",
      "详情：定标核验",
      "详情：工程核验",
      "详情：资产核验",
      "详情：科研核验",
      "详情：合同核验",
      "详情：发票核验",
      "详情：预算核验",
      "详情：数据核验"
    ]);
    expect(screen.queryByRole("button", { name: "详情：档案核验" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "下一页" }));
    expect(screen.getAllByRole("button", { name: /^详情：/ })).toHaveLength(4);
    expect(screen.getByRole("button", { name: "详情：档案核验" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /采购招标审计/ }));
    expect(screen.getByRole("button", { name: "详情：招标核验" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "详情：医保核验" })).not.toBeInTheDocument();
  });

  it("keeps page size and membership stable when the window resizes", () => {
    render(<ReplicaAgentDirectory mode="market" />);

    const firstPageNames = screen.getAllByRole("button", { name: /^详情：/ }).map((button) => button.getAttribute("aria-label"));
    const originalWidthDescriptor = Object.getOwnPropertyDescriptor(window, "innerWidth");
    const originalHeightDescriptor = Object.getOwnPropertyDescriptor(window, "innerHeight");
    try {
      Object.defineProperty(window, "innerWidth", { configurable: true, value: 360 });
      Object.defineProperty(window, "innerHeight", { configurable: true, value: 520 });
      fireEvent(window, new Event("resize"));

      expect(screen.getAllByRole("button", { name: /^详情：/ }).map((button) => button.getAttribute("aria-label"))).toEqual(
        firstPageNames
      );
      expect(screen.getByText("每页 12 个")).toBeInTheDocument();
    } finally {
      if (originalWidthDescriptor) {
        Object.defineProperty(window, "innerWidth", originalWidthDescriptor);
      } else {
        Reflect.deleteProperty(window, "innerWidth");
      }
      if (originalHeightDescriptor) {
        Object.defineProperty(window, "innerHeight", originalHeightDescriptor);
      } else {
        Reflect.deleteProperty(window, "innerHeight");
      }
    }
  });

  it("links every visible personal agent directly to chat", () => {
    render(<ReplicaAgentDirectory mode="mine" />);

    const expectedIdsByName = new Map<string, string>([
      ["医保核验", "template-medical-fund"],
      ["出国核验", "template-travel"],
      ["会议核验", "template meeting/2026"],
      ["招标核验", "template-procurement"],
      ["定标核验", "template-bid"],
      ["工程核验", "template-engineering"],
      ["资产核验", "template-asset"],
      ["科研核验", "template-research"],
      ["合同核验", "template-contract"],
      ["发票核验", "template-invoice"],
      ["预算核验", "template-budget"],
      ["数据核验", "template-data"]
    ]);

    const cards = screen.getAllByRole("article");
    expect(cards).toHaveLength(12);
    for (const card of cards) {
      const name = within(card).getByRole("heading", { level: 2 }).textContent ?? "";
      const id = expectedIdsByName.get(name);
      expect(id).toBeDefined();
      expect(within(card).getByRole("link", { name: `立即使用：${name}` })).toHaveAttribute(
        "href",
        `/chat?agent=${encodeURIComponent(id ?? "")}`
      );
    }
  });

  it("links the personal agent detail primary action directly to chat", () => {
    render(<ReplicaAgentDirectory mode="mine" />);

    expect(
      within(screen.getByRole("complementary", { name: "我的智能体详情" })).getByRole("link", {
        name: "立即使用：医保核验"
      })
    ).toHaveAttribute("href", "/chat?agent=template-medical-fund");
  });

  it("moves the personal agent detail to the first visible agent on the next page", () => {
    render(<ReplicaAgentDirectory mode="mine" />);

    fireEvent.click(screen.getByRole("button", { name: "查看详情：数据核验" }));
    expect(
      within(screen.getByRole("complementary", { name: "我的智能体详情" })).getByRole("link", {
        name: "立即使用：数据核验"
      })
    ).toHaveAttribute("href", "/chat?agent=template-data");

    fireEvent.click(screen.getByRole("button", { name: "下一页" }));

    const detail = screen.getByRole("complementary", { name: "我的智能体详情" });
    expect(within(detail).getByRole("heading", { name: "档案核验" })).toBeInTheDocument();
    expect(within(detail).getByRole("link", { name: "立即使用：档案核验" })).toHaveAttribute(
      "href",
      "/chat?agent=template-archive"
    );
    expect(within(detail).queryByRole("link", { name: "立即使用：数据核验" })).not.toBeInTheDocument();
  });

  it("opens prompt details and installs a market template through the audit agent API", async () => {
    render(<ReplicaAgentDirectory mode="market" />);

    expect(screen.queryByRole("link", { name: /^立即使用：/ })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "详情：医保核验" }));

    expect(screen.getByRole("dialog", { name: "医保核验" })).toBeInTheDocument();
    expect(screen.getByText("提示词")).toBeInTheDocument();
    expect(screen.getByText(/请围绕医保基金使用合规输出风险判断/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "收藏：医保核验" }));
    expect(screen.getByRole("button", { name: "收藏：医保核验" })).toHaveTextContent("取消收藏");

    fireEvent.click(screen.getByRole("button", { name: "加入我的智能体：医保核验" }));

    await waitFor(() => {
      expect(createAuditAgent).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "医保核验",
          category: "业务类",
          topic: "医保基金使用合规",
          knowledge_base: "医保基金合规知识库",
          project_name: "医保基金使用合规专项自查",
          visibility_scope: "project",
          metadata: expect.objectContaining({
            source: "agent-market",
            template_id: "template-medical-fund",
            template_original_category: "财务收支审计",
            template_project: "智能体广场",
            avatar_initial: "医"
          })
        })
      );
    });
    expect(await screen.findByText(/已安装「医保核验」/)).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "进入 AI 对话" }).map((item) => item.getAttribute("href"))).toContain(
      "/chat?agent=installed-template-medical-fund"
    );
    expect(within(screen.getByRole("dialog", { name: "医保核验" })).getByRole("link", { name: "进入 AI 对话" })).toHaveAttribute(
      "href",
      "/chat?agent=installed-template-medical-fund"
    );
  });

  it("renders completed market-template install actions as disabled", async () => {
    render(<ReplicaAgentDirectory mode="market" />);

    fireEvent.click(screen.getByRole("button", { name: "详情：医保核验" }));
    const dialog = screen.getByRole("dialog", { name: "医保核验" });
    const installButton = within(dialog).getByRole("button", { name: "加入我的智能体：医保核验" });

    fireEvent.click(installButton);

    await waitFor(() => {
      expect(createAuditAgent).toHaveBeenCalledTimes(1);
      expect(installButton).toBeDisabled();
      expect(installButton).toHaveTextContent("已安装");
    });
    expect(screen.getByRole("button", { name: "已安装" })).toBeDisabled();
  });

  it("labels an archived market-template reinstall as restored", async () => {
    vi.mocked(createAuditAgent).mockResolvedValueOnce({
      ...installedAgentResponse("installed-template-medical-fund", "医保核验"),
      created: false,
      reactivated: true
    });
    render(<ReplicaAgentDirectory mode="market" />);

    fireEvent.click(screen.getByRole("button", { name: "详情：医保核验" }));
    fireEvent.click(screen.getByRole("button", { name: "加入我的智能体：医保核验" }));

    expect(await screen.findByText(/已恢复「医保核验」/)).toBeInTheDocument();
  });

  it("restores a completed market-template install after remount", async () => {
    installedMarketAgentIds.set("template-medical-fund", "installed-template-medical-fund");

    render(<ReplicaAgentDirectory mode="market" />);

    fireEvent.click(screen.getByRole("button", { name: "详情：医保核验" }));
    const dialog = screen.getByRole("dialog", { name: "医保核验" });
    expect(within(dialog).getByRole("button", { name: "已安装：医保核验" })).toBeDisabled();
    expect(within(dialog).getByRole("link", { name: "进入 AI 对话" })).toHaveAttribute(
      "href",
      "/chat?agent=installed-template-medical-fund"
    );
    expect(createAuditAgent).not.toHaveBeenCalled();
  });

  it("rejects a completed market-template install before the handler can call the API again", () => {
    expect(getMarketAgentInstallBlockReason({
      canManageAgents: true,
      installStateLoading: false,
      isInstalled: true,
      inFlightIdentityKey: null,
      identityKey: "admin:next-admin"
    })).toBe("already-installed");

    expect(getMarketAgentInstallBlockReason({
      canManageAgents: true,
      installStateLoading: false,
      isInstalled: false,
      inFlightIdentityKey: null,
      identityKey: "admin:next-admin"
    })).toBeNull();
  });

  it("blocks install while the current identity installation state is loading", () => {
    expect(getMarketAgentInstallBlockReason({
      canManageAgents: true,
      installStateLoading: true,
      isInstalled: false,
      inFlightIdentityKey: null,
      identityKey: "admin:next-admin"
    })).toBe("install-state-loading");

    marketInstallationsStatus = "loading";
    render(<ReplicaAgentDirectory mode="market" />);

    expect(screen.getByRole("button", { name: "安装状态读取中" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "详情：医保核验" }));
    expect(
      within(screen.getByRole("dialog", { name: "医保核验" })).getByRole("button", {
        name: "加入我的智能体：医保核验"
      })
    ).toHaveTextContent("安装状态读取中");
    expect(createAuditAgent).not.toHaveBeenCalled();
  });

  it("surfaces installation-state read failures while keeping server-idempotent retry available", () => {
    marketInstallationsStatus = "error";
    render(<ReplicaAgentDirectory mode="market" />);

    expect(screen.getByText("已安装状态读取失败；再次安装仍由服务端幂等保护。")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "加入我的智能体" })).toBeEnabled();
  });

  it.each(auditExtensionValidationCatalog.map(({ id, name }) => ({ id, name })))(
    "labels, opens, installs and links extension template $name",
    async ({ id, name }) => {
      render(<ReplicaAgentDirectory mode="market" />);

      fireEvent.change(screen.getByPlaceholderText("搜索 AI 智能体"), { target: { value: name } });
      const card = screen.getByRole("article");
      expect(within(card).getByLabelText(`扩展验证包：${name}`)).toHaveTextContent("扩展验证包");

      fireEvent.click(within(card).getByRole("button", { name: `详情：${name}` }));
      const dialog = screen.getByRole("dialog", { name });
      expect(within(dialog).getByText("扩展验证包")).toBeInTheDocument();

      fireEvent.click(within(dialog).getByRole("button", { name: `加入我的智能体：${name}` }));

      await waitFor(() => {
        expect(createAuditAgent).toHaveBeenLastCalledWith(
          expect.objectContaining({
            name,
            knowledge_base: "未绑定知识库",
            project_name: "医保基金使用合规专项自查",
            visibility_scope: "project",
            metadata: expect.objectContaining({
              template_id: id,
              template_scope: "extension-validation"
            })
          })
        );
      });
      expect(within(dialog).getByRole("link", { name: "进入 AI 对话" })).toHaveAttribute(
        "href",
        `/chat?agent=installed-${id}`
      );
    }
  );

  it("does not reuse an installed chat link across extension templates", async () => {
    const [firstAgent, secondAgent] = auditExtensionValidationCatalog;
    render(<ReplicaAgentDirectory mode="market" />);

    fireEvent.change(screen.getByPlaceholderText("搜索 AI 智能体"), {
      target: { value: firstAgent.name }
    });
    fireEvent.click(screen.getByRole("button", { name: `详情：${firstAgent.name}` }));
    let dialog = screen.getByRole("dialog", { name: firstAgent.name });
    fireEvent.click(within(dialog).getByRole("button", { name: `加入我的智能体：${firstAgent.name}` }));
    expect(await within(dialog).findByRole("link", { name: "进入 AI 对话" })).toHaveAttribute(
      "href",
      `/chat?agent=installed-${firstAgent.id}`
    );

    fireEvent.click(within(dialog).getByRole("button", { name: "关闭智能体详情" }));
    fireEvent.change(screen.getByPlaceholderText("搜索 AI 智能体"), {
      target: { value: secondAgent.name }
    });
    fireEvent.click(screen.getByRole("button", { name: `详情：${secondAgent.name}` }));
    dialog = screen.getByRole("dialog", { name: secondAgent.name });
    expect(within(dialog).queryByRole("link", { name: "进入 AI 对话" })).not.toBeInTheDocument();

    fireEvent.click(within(dialog).getByRole("button", { name: `加入我的智能体：${secondAgent.name}` }));
    expect(await within(dialog).findByRole("link", { name: "进入 AI 对话" })).toHaveAttribute(
      "href",
      `/chat?agent=installed-${secondAgent.id}`
    );

    fireEvent.click(within(dialog).getByRole("button", { name: "关闭智能体详情" }));
    fireEvent.change(screen.getByPlaceholderText("搜索 AI 智能体"), {
      target: { value: firstAgent.name }
    });
    fireEvent.click(screen.getByRole("button", { name: `详情：${firstAgent.name}` }));
    expect(
      within(screen.getByRole("dialog", { name: firstAgent.name })).getByRole("link", { name: "进入 AI 对话" })
    ).toHaveAttribute("href", `/chat?agent=installed-${firstAgent.id}`);
  });

  it("blocks a second template install while another install is pending", () => {
    const [firstAgent, secondAgent] = auditExtensionValidationCatalog;
    vi.mocked(createAuditAgent).mockReturnValueOnce(
      new Promise<Awaited<ReturnType<typeof createAuditAgent>>>(() => undefined)
    );
    render(<ReplicaAgentDirectory mode="market" />);

    fireEvent.change(screen.getByPlaceholderText("搜索 AI 智能体"), {
      target: { value: firstAgent.name }
    });
    fireEvent.click(screen.getByRole("button", { name: `详情：${firstAgent.name}` }));
    let dialog = screen.getByRole("dialog", { name: firstAgent.name });
    fireEvent.click(within(dialog).getByRole("button", { name: `加入我的智能体：${firstAgent.name}` }));
    expect(createAuditAgent).toHaveBeenCalledTimes(1);

    fireEvent.click(within(dialog).getByRole("button", { name: "关闭智能体详情" }));
    fireEvent.change(screen.getByPlaceholderText("搜索 AI 智能体"), {
      target: { value: secondAgent.name }
    });
    fireEvent.click(screen.getByRole("button", { name: `详情：${secondAgent.name}` }));
    dialog = screen.getByRole("dialog", { name: secondAgent.name });

    expect(within(dialog).getByRole("button", { name: `加入我的智能体：${secondAgent.name}` })).toBeDisabled();
    fireEvent.click(within(dialog).getByRole("button", { name: `加入我的智能体：${secondAgent.name}` }));
    expect(createAuditAgent).toHaveBeenCalledTimes(1);
  });

  it("disables market installation when the current role lacks manage_agents", async () => {
    window.localStorage.setItem(AUDIT_ROLE_STORAGE_KEY, "member");
    render(
      <AuditUserProvider>
        <ReplicaAgentDirectory mode="market" />
      </AuditUserProvider>
    );

    const headerInstall = await screen.findByRole("button", { name: "加入我的智能体" });
    expect(headerInstall).toBeDisabled();
    expect(screen.getByText("当前角色无智能体安装权限")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "详情：医保核验" }));
    expect(screen.getByRole("button", { name: "加入我的智能体：医保核验" })).toBeDisabled();
    expect(createAuditAgent).not.toHaveBeenCalled();
  });

  it("presents a permission-specific message when installation returns 403", async () => {
    vi.mocked(createAuditAgent).mockRejectedValueOnce(new BackendRequestError({
      path: "/agents",
      status: 403,
      detail: "manage_agents is not allowed"
    }));
    render(<ReplicaAgentDirectory mode="market" />);

    fireEvent.click(screen.getByRole("button", { name: "详情：医保核验" }));
    fireEvent.click(screen.getByRole("button", { name: "加入我的智能体：医保核验" }));

    expect(await screen.findByText("安装未完成：当前身份无权安装智能体。")).toBeInTheDocument();
  });

  it("presents a fail-closed message for ambiguous historical installs", async () => {
    vi.mocked(createAuditAgent).mockRejectedValueOnce(new BackendRequestError({
      path: "/agents",
      status: 409,
      detail: "multiple market agent installations already exist"
    }));
    render(<ReplicaAgentDirectory mode="market" />);

    fireEvent.click(screen.getByRole("button", { name: "详情：医保核验" }));
    fireEvent.click(screen.getByRole("button", { name: "加入我的智能体：医保核验" }));

    expect(
      await screen.findByText("安装未完成：检测到多个历史安装记录，请联系管理员处理。")
    ).toBeInTheDocument();
  });

  it("clears installed links and notices when the active identity changes", async () => {
    render(
      <AuditUserProvider>
        <ReplicaAgentDirectory mode="market" />
      </AuditUserProvider>
    );

    fireEvent.click(screen.getByRole("button", { name: "详情：医保核验" }));
    fireEvent.click(screen.getByRole("button", { name: "加入我的智能体：医保核验" }));
    expect(await screen.findByText(/已安装「医保核验」/)).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "进入 AI 对话" }).length).toBeGreaterThan(0);

    act(() => writeAuditClientRole("member"));

    await waitFor(() => {
      expect(screen.queryByText(/已安装「医保核验」/)).not.toBeInTheDocument();
      expect(screen.queryByRole("link", { name: "进入 AI 对话" })).not.toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: "加入我的智能体" })).toBeDisabled();
  });

  it("ignores an install response from the previous identity", async () => {
    const pendingInstall = deferred<Awaited<ReturnType<typeof createAuditAgent>>>();
    vi.mocked(createAuditAgent).mockReturnValueOnce(pendingInstall.promise);
    render(
      <AuditUserProvider>
        <ReplicaAgentDirectory mode="market" />
      </AuditUserProvider>
    );

    fireEvent.click(screen.getByRole("button", { name: "详情：医保核验" }));
    fireEvent.click(screen.getByRole("button", { name: "加入我的智能体：医保核验" }));
    expect(screen.getByRole("button", { name: "加入我的智能体：医保核验" })).toBeDisabled();

    act(() => writeAuditClientRole("member"));
    await act(async () => {
      pendingInstall.resolve(installedAgentResponse("stale-admin-agent", "医保核验"));
      await pendingInstall.promise;
    });

    expect(screen.queryByText(/已安装「医保核验」/)).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "进入 AI 对话" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "加入我的智能体" })).toBeDisabled();
  });
});
