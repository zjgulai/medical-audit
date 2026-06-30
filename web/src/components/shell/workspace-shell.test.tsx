import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { WorkspaceShell } from "./workspace-shell";

const { usePathnameMock, useRouterMock } = vi.hoisted(() => ({
  usePathnameMock: vi.fn(),
  useRouterMock: vi.fn(() => ({ push: vi.fn() }))
}));

vi.mock("next/navigation", () => ({
  usePathname: usePathnameMock,
  useRouter: useRouterMock
}));

describe("WorkspaceShell", () => {
  beforeEach(() => {
    usePathnameMock.mockReturnValue("/documents");
  });

  it("renders route-aware navigation and project context without owning the page h1", () => {
    render(
      <WorkspaceShell>
        <main>页面内容</main>
      </WorkspaceShell>
    );

    expect(screen.getByRole("navigation", { name: "主导航" })).toHaveClass("overflow-x-auto");
    expect(screen.getByText("AI智能审计管理系统")).toBeInTheDocument();
    expect(screen.getByText("AI 对话")).toBeInTheDocument();
    expect(screen.getByText("我的智能体")).toBeInTheDocument();
    expect(screen.getByText("智能体广场")).toBeInTheDocument();
    expect(screen.getByText("知识库")).toBeInTheDocument();
    expect(screen.getByText("AI 数据分析")).toBeInTheDocument();
    expect(screen.getByText("项目管理")).toBeInTheDocument();
    expect(screen.getByText("审计底稿生成")).toBeInTheDocument();
    expect(screen.getByRole("tablist", { name: "已打开模块" })).toBeInTheDocument();
    expect(screen.getByLabelText("角色权限视图")).toBeInTheDocument();
    expect(screen.getByText(/医保基金使用合规专项自查/)).toBeInTheDocument();
    expect(screen.getByText(/单院医保内审试运行/)).toBeInTheDocument();
    expect(screen.getAllByText("医保基金使用合规").length).toBeGreaterThan(0);
    expect(screen.getByTestId("auditscope-brand-logo")).toBeInTheDocument();
    expect(screen.getByText("管理员视图")).toBeInTheDocument();
    for (const role of ["管理员", "技术人员", "主任", "普通成员"]) {
      expect(screen.getByRole("button", { name: new RegExp(role) })).toBeInTheDocument();
    }
    expect(screen.getByText("连接检测中")).toBeInTheDocument();
    expect(screen.getByText("页面内容")).toBeInTheDocument();

    expect(screen.getByRole("link", { name: /文档检索/ })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: /AI 对话/ })).toHaveAttribute("href", "/chat");
    expect(screen.getByRole("link", { name: /文档检索/ })).toHaveAttribute("href", "/documents");
    expect(screen.getByRole("link", { name: /项目管理/ })).toHaveAttribute("href", "/projects");
    expect(screen.getByRole("link", { name: /打开当前审计专题/ })).toHaveAttribute("href", "/fund-compliance");
    expect(screen.getByRole("link", { name: /AI 对话/ })).not.toHaveAttribute("aria-current");
    expect(screen.queryByRole("heading", { level: 1 })).not.toBeInTheDocument();
  });

  it("marks the Next-native AI chat route active", () => {
    usePathnameMock.mockReturnValue("/chat");

    render(
      <WorkspaceShell>
        <main>AI 对话内容</main>
      </WorkspaceShell>
    );

    expect(screen.getByRole("link", { name: /AI 对话/ })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: /文档检索/ })).not.toHaveAttribute("aria-current");
  });

  it("marks the Next-native data analysis route active", () => {
    usePathnameMock.mockReturnValue("/analytics");

    render(
      <WorkspaceShell>
        <main>数据分析内容</main>
      </WorkspaceShell>
    );

    expect(screen.getByRole("link", { name: /AI 数据分析/ })).toHaveAttribute("aria-current", "page");
  });

  it("marks the Next-native project management route active", () => {
    usePathnameMock.mockReturnValue("/projects");

    render(
      <WorkspaceShell>
        <main>项目管理内容</main>
      </WorkspaceShell>
    );

    expect(screen.getByRole("link", { name: /项目管理/ })).toHaveAttribute("aria-current", "page");
  });

  it("keeps secondary workspace routes reachable from the sidebar and active tabs", () => {
    usePathnameMock.mockReturnValue("/rules");

    render(
      <WorkspaceShell>
        <main>规则库内容</main>
      </WorkspaceShell>
    );

    expect(screen.getAllByText("专题规则库").length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: /专题规则库/ })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("tab", { name: /专题规则库/ })).toHaveAttribute("href", "/rules");
  });
});
