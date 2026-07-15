import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ReplicaShell } from "./replica-shell";

const { usePathnameMock } = vi.hoisted(() => ({
  usePathnameMock: vi.fn()
}));

const apiMocks = vi.hoisted(() => ({
  createQueryHistoryReviewTask: vi.fn(),
  fetchAuthSession: vi.fn(),
  fetchProjects: vi.fn(),
  fetchQueryHistory: vi.fn()
}));

vi.mock("next/navigation", () => ({
  usePathname: usePathnameMock
}));

vi.mock("@/lib/api-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api-client")>();
  return { ...actual, ...apiMocks };
});

const globalsCss = readFileSync(resolve(process.cwd(), "src/app/globals.css"), "utf-8");

describe("ReplicaShell", () => {
  beforeEach(() => {
    usePathnameMock.mockReturnValue("/chat");
    apiMocks.createQueryHistoryReviewTask.mockReset();
    apiMocks.fetchAuthSession.mockReset();
    apiMocks.fetchProjects.mockReset();
    apiMocks.fetchQueryHistory.mockReset();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("renders the active page tag as a closable control", () => {
    vi.stubEnv("NEXT_PUBLIC_MEDICAL_AUDIT_REPLICA_API_READS", "0");
    usePathnameMock.mockReturnValue("/documents");

    render(
      <ReplicaShell>
        <main>复刻页面内容</main>
      </ReplicaShell>
    );

    const tagsbar = screen.getByLabelText("打开页面");
    expect(within(tagsbar).getByText("文档检索")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "关闭文档检索页签" }));

    expect(within(tagsbar).queryByText("文档检索")).not.toBeInTheDocument();
    expect(screen.getByText("复刻页面内容")).toBeInTheDocument();
  });

  it("renders nine main modules and one separate medical topic entry", () => {
    vi.stubEnv("NEXT_PUBLIC_MEDICAL_AUDIT_REPLICA_API_READS", "0");

    render(
      <ReplicaShell>
        <main>复刻页面内容</main>
      </ReplicaShell>
    );

    const mainNav = screen.getByRole("navigation", { name: "主导航" });
    expect(within(mainNav).getAllByRole("link")).toHaveLength(9);
    expect(within(mainNav).queryByText("医保审计专题")).not.toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "打开医保审计专题" })).toHaveLength(1);
    expect(screen.queryByText("医保基金合规审计")).not.toBeInTheDocument();
  });

  it("marks the medical topic active and uses its label in the page chrome", () => {
    vi.stubEnv("NEXT_PUBLIC_MEDICAL_AUDIT_REPLICA_API_READS", "0");
    usePathnameMock.mockReturnValue("/medical-audit");

    render(
      <ReplicaShell>
        <main>复刻页面内容</main>
      </ReplicaShell>
    );

    expect(screen.getByRole("link", { name: "打开医保审计专题" })).toHaveAttribute("aria-current", "page");
    expect(within(screen.getByRole("banner")).getByText("医保审计专题")).toBeInTheDocument();
    expect(within(screen.getByLabelText("打开页面")).getByText("医保审计专题")).toBeInTheDocument();
  });

  it("marks the project route so floating history stays clear of row actions", () => {
    vi.stubEnv("NEXT_PUBLIC_MEDICAL_AUDIT_REPLICA_API_READS", "0");
    usePathnameMock.mockReturnValue("/projects");

    const { container } = render(
      <ReplicaShell>
        <main>项目内容</main>
      </ReplicaShell>
    );

    expect(container.firstElementChild).toHaveClass("replica-project-shell");
  });

  it("keeps the fixed history drawer inside the viewport with internal scrolling", () => {
    expect(globalsCss).toMatch(
      /\.replica-history-drawer\s*\{[^}]*max-height:\s*calc\([^;]+\);[^}]*overflow-y:\s*auto;/s
    );
  });

  it("renders history items as deterministic chat links", () => {
    vi.stubEnv("NEXT_PUBLIC_MEDICAL_AUDIT_REPLICA_API_READS", "0");

    render(
      <ReplicaShell>
        <main>复刻页面内容</main>
      </ReplicaShell>
    );

    const historyTrigger = screen.getByRole("button", { name: "打开历史对话" });
    expect(historyTrigger).toHaveTextContent("历史对话");
    fireEvent.click(historyTrigger);

    expect(screen.getByRole("button", { name: "收起历史对话" })).toHaveAttribute("aria-expanded", "true");

    expect(screen.getByRole("link", { name: "打开历史对话：中标候选人名单表" })).toHaveAttribute(
      "href",
      "/chat?history=history-1"
    );
    expect(screen.queryByRole("button", { name: /转为任务/ })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "关闭历史对话" }));
    expect(screen.queryByRole("link", { name: "打开历史对话：中标候选人名单表" })).not.toBeInTheDocument();
  });

  it("requires an explicit visible project before converting one durable history item", async () => {
    vi.stubEnv("NEXT_PUBLIC_MEDICAL_AUDIT_REPLICA_API_READS", "1");
    apiMocks.fetchAuthSession.mockResolvedValue({
      user_identifier: "next-admin",
      role: "admin",
      role_label: "管理员",
      permissions: ["create_review_task"],
      legacy_api_role: "it-admin",
      tenant_id: "hospital-demo",
      auth_source: "header",
      profile_status: null,
      auth_scope_type: null,
      auth_scope_key: null,
      auth_mode: "header_transition_layer",
      profile: null,
      store: { ready: true, backend: "test" }
    });
    apiMocks.fetchQueryHistory.mockResolvedValue({
      items: [
        {
          id: "query-history-001",
          user_identifier: "next-admin",
          question: "医保基金审核依据",
          filters: { source_collections: ["medical-insurance-laws"] },
          answer_summary: "应核对证据链。",
          retrieved_chunk_ids: ["chunk-001"],
          citation_count: 1,
          created_at: "2026-07-15T00:00:00Z"
        }
      ],
      store: { ready: true, backend: "SqlAlchemyQueryHistoryStore" }
    });
    apiMocks.fetchProjects.mockResolvedValue({
      items: [
        {
          id: "SELF-CHECK-FUND-20260607",
          name: "医保基金使用合规专项自查",
          audit_topic: "医保基金使用合规",
          organization_name: "单院医保内审试运行",
          member_count: 3,
          creator: "项目负责人",
          creator_user_identifier: "next-director",
          created_at: "2026-06-07",
          status: "进行中",
          operation_label: "进入项目",
          source: "system-default"
        }
      ],
      roles: ["项目负责人"],
      statuses: ["在项目中"],
      project_statuses: ["进行中"],
      store: {
        ready: true,
        backend: "test",
        persistent_writes_ready: true,
        history_review_task_writes_ready: true
      }
    });
    apiMocks.createQueryHistoryReviewTask.mockResolvedValue({
      format: "query-history-review-task-v1",
      query_log_id: "query-history-001",
      task_id: "history-task-001",
      project_key: "SELF-CHECK-FUND-20260607",
      status: "pending-review",
      created: true,
      review_queue_href: "/reports",
      provider_call: false,
      audit: { status: "degraded", intent_recorded: true, completion_recorded: false }
    });

    render(
      <ReplicaShell>
        <main>复刻页面内容</main>
      </ReplicaShell>
    );

    fireEvent.click(screen.getByRole("button", { name: "打开历史对话" }));
    const convertButton = await screen.findByRole("button", { name: "转为任务：医保基金审核依据" });
    fireEvent.click(convertButton);

    expect(apiMocks.fetchProjects).toHaveBeenCalledTimes(1);
    expect(apiMocks.createQueryHistoryReviewTask).not.toHaveBeenCalled();
    const confirmButton = await screen.findByRole("button", { name: "确认转为任务" });
    expect(confirmButton).toBeDisabled();

    fireEvent.change(screen.getByLabelText("选择目标项目"), {
      target: { value: "SELF-CHECK-FUND-20260607" }
    });
    expect(confirmButton).toBeEnabled();
    fireEvent.click(confirmButton);

    await waitFor(() => {
      expect(apiMocks.createQueryHistoryReviewTask).toHaveBeenCalledWith(
        "query-history-001",
        { project_key: "SELF-CHECK-FUND-20260607" }
      );
    });
    expect(await screen.findByText("history-task-001")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "任务已创建，但完成审计记录未写入；请联系管理员核查。"
    );
    expect(screen.getByRole("link", { name: "前往复核任务" })).toHaveAttribute("href", "/reports");
  });

  it("blocks history conversion when projects are readable but persistent writes are unavailable", async () => {
    vi.stubEnv("NEXT_PUBLIC_MEDICAL_AUDIT_REPLICA_API_READS", "1");
    apiMocks.fetchAuthSession.mockResolvedValue({
      user_identifier: "next-admin",
      role: "admin",
      role_label: "管理员",
      permissions: ["create_review_task"],
      legacy_api_role: "it-admin",
      tenant_id: "hospital-demo",
      auth_source: "header",
      profile_status: null,
      auth_scope_type: null,
      auth_scope_key: null,
      auth_mode: "header_transition_layer",
      profile: null,
      store: { ready: true, backend: "test" }
    });
    apiMocks.fetchQueryHistory.mockResolvedValue({
      items: [{
        id: "query-history-001",
        user_identifier: "next-admin",
        question: "医保基金审核依据",
        filters: {},
        answer_summary: "应核对证据链。",
        retrieved_chunk_ids: [],
        citation_count: 0,
        created_at: "2026-07-15T00:00:00Z"
      }],
      store: { ready: true, backend: "SqlAlchemyQueryHistoryStore" }
    });
    const projectResponse = {
      items: [{
        id: "SELF-CHECK-FUND-20260607",
        name: "医保基金使用合规专项自查",
        audit_topic: "医保基金使用合规",
        organization_name: "单院医保内审试运行",
        member_count: 3,
        creator: "项目负责人",
        creator_user_identifier: "next-director",
        created_at: "2026-06-07",
        status: "进行中",
        operation_label: "进入项目",
        source: "system-default"
      }],
      roles: ["项目负责人"],
      statuses: ["在项目中"],
      project_statuses: ["进行中"],
      store: {
        ready: true,
        backend: "test",
        persistent_writes_ready: true,
        history_review_task_writes_ready: false
      }
    };
    apiMocks.fetchProjects.mockResolvedValue(projectResponse);

    render(<ReplicaShell><main>复刻页面内容</main></ReplicaShell>);
    fireEvent.click(screen.getByRole("button", { name: "打开历史对话" }));
    fireEvent.click(await screen.findByRole("button", { name: "转为任务：医保基金审核依据" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("复核任务持久化写入未就绪，暂不能创建复核任务");
    fireEvent.change(screen.getByLabelText("选择目标项目"), {
      target: { value: "SELF-CHECK-FUND-20260607" }
    });
    expect(screen.getByRole("button", { name: "确认转为任务" })).toBeDisabled();
    expect(apiMocks.createQueryHistoryReviewTask).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "关闭历史对话" }));
    apiMocks.fetchProjects.mockResolvedValueOnce({
      ...projectResponse,
      store: {
        ready: false,
        backend: "unavailable",
        persistent_writes_ready: true,
        history_review_task_writes_ready: true
      }
    });
    fireEvent.click(screen.getByRole("button", { name: "打开历史对话" }));
    fireEvent.click(await screen.findByRole("button", { name: "转为任务：医保基金审核依据" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("项目存储未就绪，暂不能创建复核任务");
    expect(screen.getByRole("button", { name: "确认转为任务" })).toBeDisabled();
    expect(apiMocks.createQueryHistoryReviewTask).not.toHaveBeenCalled();
  });
});
