import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import LoginPage from "./page";

describe("LoginPage", () => {
  it("renders the Kimi-style audit login surface", () => {
    render(<LoginPage />);

    expect(screen.getByText("医保智能审计平台")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "欢迎登录" })).toBeInTheDocument();
    expect(screen.getByText("请使用您的账号密码进入系统")).toBeInTheDocument();
    expect(screen.getByLabelText("账号 / 工号")).toBeRequired();
    expect(screen.getByLabelText("密码")).toHaveAttribute("type", "password");
    expect(screen.getByLabelText("账号 / 工号")).not.toHaveAttribute("name");
    expect(screen.getByLabelText("密码")).not.toHaveAttribute("name");
    expect(screen.getByRole("button", { name: "登 录" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "信息中心" })).toHaveAttribute("href", "#support");
    expect(screen.getByText("医保智能审计平台 · 基金合规审计")).toBeInTheDocument();
  });

  it("toggles password visibility locally", () => {
    render(<LoginPage />);

    const password = screen.getByLabelText("密码");
    const toggle = screen.getByRole("button", { name: "显示密码" });

    fireEvent.click(toggle);

    expect(password).toHaveAttribute("type", "text");
    expect(screen.getByRole("button", { name: "隐藏密码" })).toHaveAttribute("aria-pressed", "true");
  });

  it("opens the initial-password security prompt before entering the workspace", () => {
    render(<LoginPage />);

    fireEvent.change(screen.getByLabelText("账号 / 工号"), { target: { value: "demo_user" } });
    fireEvent.change(screen.getByLabelText("密码"), { target: { value: "demo_password" } });
    fireEvent.submit(screen.getByRole("form", { name: "登录系统" }));

    expect(screen.getByRole("dialog", { name: "初始密码安全提示" })).toBeInTheDocument();
    expect(screen.getByText("检测到当前账号仍可能使用初始密码。建议先修改密码，再进入审计工作台。")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "修改密码" }));

    expect(screen.getByRole("dialog", { name: "修改密码" })).toBeInTheDocument();
    expect(screen.getByLabelText("新密码")).not.toHaveAttribute("name");
    expect(screen.getByLabelText("确认密码")).not.toHaveAttribute("name");

    fireEvent.click(screen.getByRole("button", { name: "提交修改" }));

    expect(screen.getByText("密码修改已生成预览。请确认后进入正式保存流程。")).toBeInTheDocument();
  });
});
