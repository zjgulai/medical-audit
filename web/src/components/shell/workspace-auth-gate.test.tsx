import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { AUDIT_AUTH_STORAGE_KEY } from "@/lib/audit-user";

import { WorkspaceAuthGate } from "./workspace-auth-gate";

describe("WorkspaceAuthGate", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.history.replaceState(null, "", "/chat");
  });

  it("shows the login surface before a local audit session is established", () => {
    render(
      <WorkspaceAuthGate>
        <main>审计助手内容</main>
      </WorkspaceAuthGate>
    );

    expect(screen.getByRole("heading", { name: "欢迎登录" })).toBeInTheDocument();
    expect(screen.queryByText("审计助手内容")).not.toBeInTheDocument();
  });

  it("renders protected workspace content when a local audit session exists", async () => {
    window.localStorage.setItem(AUDIT_AUTH_STORAGE_KEY, "authenticated");

    render(
      <WorkspaceAuthGate>
        <main>审计助手内容</main>
      </WorkspaceAuthGate>
    );

    await waitFor(() => {
      expect(screen.getByText("审计助手内容")).toBeInTheDocument();
    });
    expect(screen.queryByRole("heading", { name: "欢迎登录" })).not.toBeInTheDocument();
  });
});
