import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import LoginPage from "./page";

describe("LoginPage", () => {
  it("renders the hospital audit login surface with role entry points", () => {
    render(<LoginPage />);

    expect(screen.getByRole("heading", { name: "面向医院内审的 AI 审证工作台" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "登录工作台" })).toBeInTheDocument();
    expect(screen.getByLabelText("账号 / 工号")).toBeRequired();
    expect(screen.getByLabelText("密码")).toHaveAttribute("type", "password");
    expect(screen.getByRole("button", { name: "进入系统" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "查看当前工作台" })).toHaveAttribute("href", "/workspace");

    for (const role of ["管理员", "技术人员", "主任", "普通成员"]) {
      expect(screen.getByText(role)).toBeInTheDocument();
    }
  });
});
