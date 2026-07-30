import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { LoginSurface } from "@/components/login/login-surface";
import { AUDIT_AUTH_STORAGE_KEY } from "@/lib/audit-user";
import LoginPage from "./page";

const globalsCss = readFileSync(resolve(process.cwd(), "src/app/globals.css"), "utf-8");

function cssRuleFor(selector: string): string {
  const escapedSelector = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const match = globalsCss.match(new RegExp(`${escapedSelector}\\s*\\{(?<body>[^}]*)\\}`));
  expect(match).not.toBeNull();
  return match?.groups?.body ?? "";
}

describe("LoginPage", () => {
  afterEach(() => {
    window.localStorage.clear();
    window.history.replaceState(null, "", "/");
  });

  it("renders the focused hospital audit login surface", () => {
    render(<LoginPage />);

    expect(screen.getByRole("heading", { name: "登录工作台" })).toBeInTheDocument();
    expect(screen.getByText("AI审计一体化协作平台")).toBeInTheDocument();
    expect(screen.queryByText("医保基金合规审计")).not.toBeInTheDocument();
    expect(
      screen.queryByText("面向医院内审人员的医保基金审计、依据检索、表格分析和底稿工作区")
    ).not.toBeInTheDocument();
    expect(screen.queryByLabelText("角色入口说明")).not.toBeInTheDocument();
    expect(screen.queryByText("医院名称与 Logo 可在部署时配置")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "查看当前工作台" })).not.toBeInTheDocument();
    const loginSurface = screen.getByLabelText("AI审计一体化协作平台登录入口");
    expect(loginSurface).toHaveClass("audit-login-center-stack");
    expect(screen.queryByText("AuditScope Medical")).not.toBeInTheDocument();
    expect(screen.getByLabelText("账号 / 工号")).toBeRequired();
    expect(screen.getByLabelText("密码")).toHaveAttribute("type", "password");
    expect(screen.getByRole("checkbox", { name: "保持本机登录" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "联系信息中心" })).toHaveAttribute("href", "#support");
    expect(screen.getByRole("button", { name: "登录" })).toBeInTheDocument();
  });

  it("keeps the information-center link connected to visible support guidance", () => {
    render(<LoginPage />);

    const supportLink = screen.getByRole("link", { name: "联系信息中心" });
    if (!(supportLink instanceof HTMLAnchorElement)) {
      throw new TypeError("Expected the information-center link to be an anchor");
    }
    const supportHash = new URL(supportLink.href).hash;
    const supportTarget = document.querySelector(supportHash);

    expect(supportHash).toBe("#support");
    expect(supportTarget).not.toBeNull();
    expect(supportTarget).toBeVisible();
  });

  it("uses the compact card layout requested by the PPT feedback", () => {
    const shellRule = cssRuleFor(".audit-login-shell-compact");
    expect(shellRule).toContain("#f7fafc");
    expect(shellRule).toContain("Inter");

    const cardRule = cssRuleFor(".audit-login-card-compact");
    expect(cardRule).toContain("420px");
    expect(cardRule).toContain("border-radius: 18px");
  });

  it("preserves login submission and rejects unsafe redirect targets", () => {
    window.history.replaceState(null, "", "/login");
    const { rerender } = render(<LoginSurface redirectTo="/login#signed-in" />);

    const loginForm = screen.getByRole("button", { name: "登录" }).closest("form");
    expect(loginForm).toHaveAttribute("action", "/login#signed-in");
    fireEvent.submit(loginForm!);

    expect(window.localStorage.getItem(AUDIT_AUTH_STORAGE_KEY)).toBe("authenticated");
    expect(window.location.pathname).toBe("/login");
    expect(window.location.hash).toBe("#signed-in");

    rerender(<LoginSurface redirectTo="//outside.example" />);
    expect(screen.getByRole("button", { name: "登录" }).closest("form")).toHaveAttribute("action", "/workspace");

    rerender(<LoginSurface redirectTo="/\\outside.example/path" />);
    expect(screen.getByRole("button", { name: "登录" }).closest("form")).toHaveAttribute("action", "/workspace");
  });
});
