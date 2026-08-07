import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { fetchProjectDashboard, fetchProjects } from "@/lib/api-client";
import type { ProjectDashboardResponse, ProjectsResponse } from "@/lib/api-types";

import { AuditCockpit } from "./audit-cockpit";

vi.mock("@/components/shell/audit-user-context", () => ({
  useAuditUser: () => ({ role: "member", can: () => true })
}));

vi.mock("@/lib/api-client", () => ({
  fetchProjectDashboard: vi.fn(),
  fetchProjects: vi.fn()
}));

const fetchProjectsMock = vi.mocked(fetchProjects);
const fetchProjectDashboardMock = vi.mocked(fetchProjectDashboard);

const projectsResponse: ProjectsResponse = {
  items: [
    {
      id: "AUDIT-2026",
      name: "医保基金专项审计",
      audit_topic: "医保基金使用合规",
      organization_name: "示例医院",
      member_count: 5,
      creator: "李主任",
      creator_user_identifier: "director-1",
      created_at: "2026-08-01T08:00:00Z",
      status: "进行中",
      operation_label: "进入项目",
      source: "custom"
    }
  ],
  roles: ["项目负责人", "审计员", "业务专家", "信息科", "只读观察员"],
  statuses: ["在项目中", "待确认"],
  project_statuses: ["待开始", "进行中", "已完成", "已归档"],
  store: { ready: true, backend: "postgres" }
};

const dashboardResponse: ProjectDashboardResponse = {
  format: "project-dashboard-v1",
  project: projectsResponse.items[0],
  metrics: [
    { key: "open_findings", label: "待处理疑点", value: "3", helper: "来自项目疑点", tone: "danger" },
    { key: "missing_evidence", label: "待补证据", value: "1", helper: "来自项目疑点", tone: "warning" },
    { key: "rule_cards", label: "已关联任务", value: "4", helper: "来自项目任务", tone: "info" },
    { key: "backend_status", label: "资料可检索", value: "已接入", helper: "项目证据已连接", tone: "success" }
  ],
  queue: [
    { id: "Q-1", title: "复核高额重复收费", owner: "王审计", dueLabel: "今天", status: "open", risk: "high" },
    { id: "Q-2", title: "补充采购合同", owner: "赵审计", dueLabel: "本周", status: "blocked", risk: "medium" }
  ],
  activities: [
    { id: "A-1", title: "新增审计疑点", description: "规则命中形成待复核事项。", timeLabel: "10 分钟前" }
  ],
  status_distribution: [],
  member_workloads: [],
  evidence_grade: "live-db-connected",
  production_side_effect: "none",
  store: {
    ready: true,
    project_members_ready: true,
    audit_findings_ready: true,
    status: "ready",
    backend: { project_members: "postgres", audit_findings: "postgres" }
  }
};

describe("AuditCockpit", () => {
  beforeEach(() => {
    fetchProjectsMock.mockReset();
    fetchProjectDashboardMock.mockReset();
    fetchProjectsMock.mockResolvedValue(projectsResponse);
    fetchProjectDashboardMock.mockResolvedValue(dashboardResponse);
  });

  it("loads a real visible project and renders progress, risk, queue and activity", async () => {
    render(<AuditCockpit />);

    expect(screen.getByRole("heading", { name: "审计驾驶舱" })).toBeInTheDocument();
    await waitFor(() => expect(fetchProjectDashboardMock).toHaveBeenCalledWith("AUDIT-2026"));
    expect(await screen.findByRole("heading", { name: "医保基金专项审计" })).toBeInTheDocument();
    expect(await screen.findByText("待处理疑点")).toBeInTheDocument();
    expect(screen.getByText("审计实施")).toBeInTheDocument();
    expect(screen.getByText("复核高额重复收费")).toBeInTheDocument();
    expect(screen.getByText("新增审计疑点")).toBeInTheDocument();
    expect(screen.getByText("证据状态：", { exact: false })).toHaveTextContent("项目证据已同步");
    fireEvent.click(screen.getByText("查看数据完整性"));
    expect(screen.getByText("项目数据").closest("div")).toHaveTextContent("项目证据已同步");
    expect(screen.queryByText("ready")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "项目管理" })).toHaveAttribute("href", "/projects");
  });

  it("retries a failed project-list request without rendering fixture data", async () => {
    fetchProjectsMock.mockRejectedValueOnce(new Error("projects unavailable"));

    render(<AuditCockpit />);

    expect(await screen.findByRole("alert")).toHaveTextContent("项目列表读取失败");
    expect(fetchProjectDashboardMock).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "重试" }));

    await waitFor(() => expect(fetchProjectsMock).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(fetchProjectDashboardMock).toHaveBeenCalledWith("AUDIT-2026"));
    expect(await screen.findByRole("heading", { name: "医保基金专项审计" })).toBeInTheDocument();
  });

  it("retries a failed dashboard request for the same selected project", async () => {
    fetchProjectDashboardMock.mockRejectedValueOnce(new Error("dashboard unavailable"));

    render(<AuditCockpit />);

    expect(await screen.findByRole("alert")).toHaveTextContent("项目驾驶舱读取失败");
    fireEvent.click(screen.getByRole("button", { name: "重新读取" }));

    await waitFor(() => expect(fetchProjectDashboardMock).toHaveBeenCalledTimes(2));
    expect(fetchProjectDashboardMock).toHaveBeenNthCalledWith(2, "AUDIT-2026");
    expect(await screen.findByText("复核高额重复收费")).toBeInTheDocument();
  });

  it("shows an honest empty state instead of fixture metrics", async () => {
    fetchProjectsMock.mockResolvedValue({ ...projectsResponse, items: [] });

    render(<AuditCockpit />);

    expect(await screen.findByText("当前没有可见项目。请先在项目管理中创建或加入项目。")).toBeInTheDocument();
    expect(fetchProjectDashboardMock).not.toHaveBeenCalled();
    expect(screen.queryByText("待处理疑点")).not.toBeInTheDocument();
  });
});
