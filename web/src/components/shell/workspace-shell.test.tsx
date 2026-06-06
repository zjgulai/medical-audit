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

    expect(screen.getByRole("navigation", { name: "主导航" })).toBeInTheDocument();
    expect(screen.getByText("医保自查 OS")).toBeInTheDocument();
    expect(screen.getByText("AI 引导自查")).toBeInTheDocument();
    expect(screen.getByText("默认自查项目")).toBeInTheDocument();
    expect(screen.getByText("索引状态待接入")).toBeInTheDocument();
    expect(screen.getByText("页面内容")).toBeInTheDocument();

    expect(screen.getByRole("link", { name: /今日工作台/ })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: /AI 引导自查/ })).not.toHaveAttribute("aria-current");
    expect(screen.queryByRole("heading", { level: 1 })).not.toBeInTheDocument();
  });
});
