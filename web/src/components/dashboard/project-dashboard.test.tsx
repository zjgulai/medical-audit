import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { currentSelfCheckProject } from "@/lib/projects";

import { ProjectDashboard } from "./project-dashboard";

describe("ProjectDashboard", () => {
  it("renders current project, metrics, queue, workflow progress and recent activity", () => {
    render(<ProjectDashboard project={currentSelfCheckProject} />);

    expect(screen.getByRole("heading", { name: "医保基金使用合规专项自查" })).toBeInTheDocument();
    expect(screen.getByText("单院医保内审试运行")).toBeInTheDocument();
    expect(screen.getByText("2026-01 至 2026-03")).toBeInTheDocument();
    expect(screen.getByText("待处理疑点")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("核对非目录项目发生基金支付的结算明细")).toBeInTheDocument();
    expect(screen.getByText("形成判断")).toBeInTheDocument();
    expect(screen.getByText("规则卡映射已激活")).toBeInTheDocument();
  });
});
