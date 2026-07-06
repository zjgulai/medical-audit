import { render, screen, within } from "@testing-library/react";
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

    const mainNavigation = screen.getByRole("navigation", { name: "主导航" });

    expect(mainNavigation).toHaveClass("grid");
    expect(screen.getByText("医疗AI审计平台")).toBeInTheDocument();
    for (const label of ["工作台", "基金合规", "审计助手", "文档依据", "项目归档"]) {
      expect(within(mainNavigation).getByText(label)).toBeInTheDocument();
    }
    for (const label of ["我的助手", "助手库", "依据库", "数据分析", "项目空间", "底稿生成"]) {
      expect(within(mainNavigation).queryByText(label)).not.toBeInTheDocument();
    }
    expect(screen.getByText("更多")).toBeInTheDocument();
    expect(screen.queryByRole("tablist", { name: "已打开模块" })).not.toBeInTheDocument();
    expect(screen.getByRole("searchbox", { name: "全局搜索" })).toHaveAttribute("placeholder", "搜索");
    expect(screen.getByLabelText("角色权限视图")).toBeInTheDocument();
    expect(screen.getByText(/医保基金使用合规专项自查/)).toBeInTheDocument();
    expect(screen.getAllByText("基金合规").length).toBeGreaterThan(0);
    expect(screen.getByTestId("auditscope-brand-logo")).toBeInTheDocument();
    expect(screen.getAllByText("管理员").length).toBeGreaterThan(0);
    const roleMenu = screen.getByLabelText("角色权限视图");
    for (const role of ["管理员", "技术人员", "主任", "普通成员"]) {
      expect(within(roleMenu).getByText(role)).toBeInTheDocument();
    }
    expect(screen.queryByText("连接检测中")).not.toBeInTheDocument();
    expect(screen.getByText("页面内容")).toBeInTheDocument();

    expect(screen.getByRole("link", { name: /文档依据/ })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: /审计助手/ })).toHaveAttribute("href", "/chat");
    expect(screen.getByRole("link", { name: /文档依据/ })).toHaveAttribute("href", "/documents");
    expect(screen.getByRole("link", { name: /基金合规/ })).toHaveAttribute("href", "/fund-compliance");
    expect(screen.getByRole("link", { name: /审计助手/ })).not.toHaveAttribute("aria-current");
    expect(screen.queryByRole("heading", { level: 1 })).not.toBeInTheDocument();
  });

  it("marks the Next-native AI chat route active", () => {
    usePathnameMock.mockReturnValue("/chat");

    render(
      <WorkspaceShell>
        <main>审计助手内容</main>
      </WorkspaceShell>
    );

    expect(screen.getByRole("link", { name: /审计助手/ })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: /文档依据/ })).not.toHaveAttribute("aria-current");
  });

  it("marks the Next-native data analysis route active", () => {
    usePathnameMock.mockReturnValue("/analytics");

    render(
      <WorkspaceShell>
        <main>数据分析内容</main>
      </WorkspaceShell>
    );

    expect(screen.getByRole("link", { name: /数据分析/ })).toHaveAttribute("aria-current", "page");
  });

  it("marks the Next-native project management route active", () => {
    usePathnameMock.mockReturnValue("/projects");

    render(
      <WorkspaceShell>
        <main>项目空间内容</main>
      </WorkspaceShell>
    );

    expect(screen.getByRole("link", { name: /项目空间/ })).toHaveAttribute("aria-current", "page");
  });

  it("keeps secondary workspace routes reachable from the sidebar", () => {
    usePathnameMock.mockReturnValue("/rules");

    render(
      <WorkspaceShell>
        <main>规则库内容</main>
      </WorkspaceShell>
    );

    expect(screen.getAllByText("规则库").length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: /规则库/ })).toHaveAttribute("aria-current", "page");
    expect(screen.queryByRole("tablist", { name: "已打开模块" })).not.toBeInTheDocument();
  });
});
