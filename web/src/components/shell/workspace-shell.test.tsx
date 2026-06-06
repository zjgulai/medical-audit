import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { WorkspaceShell } from "./workspace-shell";

describe("WorkspaceShell", () => {
  it("renders the self-check OS navigation and project context", () => {
    render(
      <WorkspaceShell>
        <main>页面内容</main>
      </WorkspaceShell>
    );

    expect(screen.getByText("医保自查 OS")).toBeInTheDocument();
    expect(screen.getByText("AI 引导自查")).toBeInTheDocument();
    expect(screen.getByText("默认自查项目")).toBeInTheDocument();
    expect(screen.getByText("页面内容")).toBeInTheDocument();
  });
});
