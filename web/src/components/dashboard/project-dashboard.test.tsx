import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { currentSelfCheckProject } from "@/lib/projects";

import { ProjectDashboard } from "./project-dashboard";

vi.mock("@/lib/api-client", () => ({
  fetchBackendHealth: vi.fn(async () => ({
    status: "ok",
    version: "0.1.0",
    data_root: "/tmp/data"
  })),
  fetchSearchBackendStatus: vi.fn(async () => ({
    backend: "postgres",
    ready: true,
    details: { matching_embedding_count: 48985 }
  }))
}));

describe("ProjectDashboard", () => {
  it("renders current project, metrics, queue, workflow progress and recent activity", async () => {
    render(<ProjectDashboard project={currentSelfCheckProject} />);

    expect(screen.getByRole("heading", { name: "医保基金使用合规专项自查" })).toBeInTheDocument();
    expect(screen.getByText("单院医保内审试运行")).toBeInTheDocument();
    expect(screen.getByText("2026-01 至 2026-03")).toBeInTheDocument();
    expect(screen.getByText("待处理疑点")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("核对非目录项目发生基金支付的结算明细")).toBeInTheDocument();
    expect(screen.getByText("形成判断")).toBeInTheDocument();
    expect(screen.getByText("规则卡映射已激活")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("工作台可用")).toBeInTheDocument();
    });
  });
});
