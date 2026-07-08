import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import LoginPage from "./page";

const globalsCss = readFileSync(resolve(process.cwd(), "src/app/globals.css"), "utf-8");

function cssRuleFor(selector: string): string {
  const escapedSelector = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const match = globalsCss.match(new RegExp(`${escapedSelector}\\s*\\{(?<body>[^}]*)\\}`));
  expect(match).not.toBeNull();
  return match?.groups?.body ?? "";
}

describe("LoginPage", () => {
  it("renders the hospital audit login surface with role entry points", () => {
    render(<LoginPage />);

    expect(screen.getByRole("heading", { name: "登录工作台" })).toBeInTheDocument();
    expect(screen.getByText("AI审计一体化协作平台")).toBeInTheDocument();
    const loginSurface = screen.getByLabelText("AI审计一体化协作平台登录入口");
    expect(loginSurface).toHaveClass("audit-login-center-stack");
    expect(screen.queryByText("AuditScope Medical")).not.toBeInTheDocument();
    expect(screen.getByLabelText("账号 / 工号")).toBeRequired();
    expect(screen.getByLabelText("密码")).toHaveAttribute("type", "password");
    expect(screen.getByRole("button", { name: "登录" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "查看当前工作台" })).toHaveAttribute("href", "/workspace");
    expect(screen.getByText("医院名称与 Logo 可在部署时配置")).toBeInTheDocument();

    for (const role of ["管理员", "技术人员", "主任", "普通成员"]) {
      expect(screen.getByText(role)).toBeInTheDocument();
    }
  });

  it("uses the compact card layout requested by the PPT feedback", () => {
    const shellRule = cssRuleFor(".audit-login-shell-compact");
    expect(shellRule).toContain("#f7fafc");
    expect(shellRule).toContain("Inter");

    const cardRule = cssRuleFor(".audit-login-card-compact");
    expect(cardRule).toContain("420px");
    expect(cardRule).toContain("border-radius: 18px");

    const orgRule = cssRuleFor(".audit-login-org-panel");
    expect(orgRule).toContain("grid-template-columns: 32px minmax(0, 1fr)");
  });
});
