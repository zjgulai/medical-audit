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

    expect(screen.getByRole("heading", { name: "面向医院内审的医保审计工作台" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "登录工作台" })).toBeInTheDocument();
    expect(screen.getByText("医疗AI审计平台")).toBeInTheDocument();
    const loginHero = screen.getByLabelText("医疗AI审计平台入口介绍");
    expect(loginHero).toHaveClass("audit-login-hero");
    expect(loginHero.className).not.toContain("bg-white/10");
    expect(loginHero.className).not.toContain("text-white");
    expect(screen.queryByText("AuditScope Medical")).not.toBeInTheDocument();
    expect(screen.getByLabelText("账号 / 工号")).toBeRequired();
    expect(screen.getByLabelText("密码")).toHaveAttribute("type", "password");
    expect(screen.getByRole("button", { name: "进入系统" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "查看当前工作台" })).toHaveAttribute("href", "/workspace");

    for (const role of ["管理员", "技术人员", "主任", "普通成员"]) {
      expect(screen.getByText(role)).toBeInTheDocument();
    }
  });

  it("keeps the hero surface dark and legible without a grey-white overlay", () => {
    const heroRule = cssRuleFor(".audit-login-hero");
    expect(heroRule).toContain("#092a59");
    expect(heroRule).toContain("#0e5598");
    expect(heroRule).toContain("#0b6f88");
    expect(heroRule).toContain("color: #ffffff");

    const gridRule = cssRuleFor(".audit-login-hero::before");
    expect(gridRule).toContain("opacity: 0.22");
    expect(gridRule).not.toContain("opacity: 0.48");
    expect(gridRule).not.toContain("rgb(255 255 255 / 0.075)");

    const overlayRule = cssRuleFor(".audit-login-hero::after");
    expect(overlayRule).toContain("rgb(2 12 27 / 0.16)");
    expect(overlayRule).not.toContain("rgb(255 255 255 / 0.2)");
    expect(overlayRule).not.toContain("rgb(255 255 255 / 0.14)");
  });
});
