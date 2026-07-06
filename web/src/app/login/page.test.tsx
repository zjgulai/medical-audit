import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import LoginPage from "./page";

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
});
