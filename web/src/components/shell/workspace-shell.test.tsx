import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { WorkspaceShell } from "./workspace-shell";

const { usePathnameMock } = vi.hoisted(() => ({
  usePathnameMock: vi.fn()
}));

vi.mock("next/navigation", () => ({
  usePathname: usePathnameMock
}));

describe("WorkspaceShell", () => {
  beforeEach(() => {
    usePathnameMock.mockReturnValue("/workspace");
  });

  it("renders route-aware navigation and project context without owning the page h1", () => {
    render(
      <WorkspaceShell>
        <main>页面内容</main>
      </WorkspaceShell>
    );

    expect(screen.getByRole("navigation", { name: "主导航" })).toHaveClass("overflow-x-auto");
    expect(screen.getByText("医保自查 OS")).toBeInTheDocument();
    expect(screen.getByText("对话审证")).toBeInTheDocument();
    expect(screen.getByText("医保基金使用合规专项自查")).toBeInTheDocument();
    expect(screen.getByText("单院医保内审试运行")).toBeInTheDocument();
    expect(screen.getByText("医保基金使用合规")).toBeInTheDocument();
    expect(screen.getByText("页面内容")).toBeInTheDocument();

    expect(screen.getByRole("link", { name: /今日工作台/ })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: /对话审证/ })).toHaveAttribute("href", "/pages/chat");
    expect(screen.getByRole("link", { name: /查询工作台/ })).toHaveAttribute("href", "/knowledge-query");
    expect(screen.getByRole("link", { name: /疑点清单/ })).toHaveAttribute("href", "/findings");
    expect(screen.getByRole("link", { name: /对话审证/ })).not.toHaveAttribute("aria-current");
    expect(screen.queryByRole("heading", { level: 1 })).not.toBeInTheDocument();
  });

  it("marks backend route active if the shell is rendered around it", () => {
    usePathnameMock.mockReturnValue("/pages/chat");

    render(
      <WorkspaceShell>
        <main>嵌套路由内容</main>
      </WorkspaceShell>
    );

    expect(screen.getByRole("link", { name: /对话审证/ })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: /今日工作台/ })).not.toHaveAttribute("aria-current");
  });

  it("marks the Next-native query route active", () => {
    usePathnameMock.mockReturnValue("/knowledge-query");

    render(
      <WorkspaceShell>
        <main>查询工作台内容</main>
      </WorkspaceShell>
    );

    expect(screen.getByRole("link", { name: /查询工作台/ })).toHaveAttribute("aria-current", "page");
  });

  it("marks the Next-native findings route active", () => {
    usePathnameMock.mockReturnValue("/findings");

    render(
      <WorkspaceShell>
        <main>疑点清单内容</main>
      </WorkspaceShell>
    );

    expect(screen.getByRole("link", { name: /疑点清单/ })).toHaveAttribute("aria-current", "page");
  });
});
