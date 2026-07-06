import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { currentSelfCheckProject } from "@/lib/projects";

import { ProjectDashboard } from "./project-dashboard";

vi.mock("@/lib/api-client", () => ({
  fetchProjectDashboard: vi.fn(async () => ({
    format: "project-dashboard-v1",
    project: {
      id: "SELF-CHECK-FUND-20260607",
      name: "医保基金使用合规专项自查",
      audit_topic: "医保基金使用合规",
      organization_name: "单院医保内审试运行",
      member_count: 3,
      creator: "项目负责人",
      created_at: "2026-06-07",
      status: "进行中",
      operation_label: "进入项目",
      source: "system-default"
    },
    metrics: [
      {
        key: "open_findings",
        label: "待处理疑点",
        value: "2",
        helper: "来自审计疑点库",
        tone: "danger"
      },
      {
        key: "missing_evidence",
        label: "待补证据",
        value: "1",
        helper: "来自审计疑点库",
        tone: "warning"
      },
      {
        key: "rule_cards",
        label: "已关联任务",
        value: "1",
        helper: "来自审计疑点库",
        tone: "info"
      },
      {
        key: "backend_status",
        label: "资料可检索",
        value: "已接入",
        helper: "读取后端 store",
        tone: "success"
      }
    ],
    queue: [
      {
        id: "FINDING-001",
        title: "后端疑点复核队列",
        owner: "审计员",
        dueLabel: "待复核",
        status: "open",
        risk: "high"
      }
    ],
    activities: [
      {
        id: "ACT-BACKEND-001",
        title: "审计疑点已同步",
        description: "当前读取 2 条疑点。",
        timeLabel: "刚刚"
      }
    ],
    status_distribution: [],
    member_workloads: [],
    evidence_grade: "live-db-connected",
    production_side_effect: "none",
    store: {
      ready: true,
      backend: {
        project_members: "SqlAlchemyProjectMemberStore",
        audit_findings: "SqlAlchemyAuditFindingStore"
      }
    }
  })),
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
    await waitFor(() => {
      expect(screen.getByText("后端疑点复核队列")).toBeInTheDocument();
    });
    expect(screen.getByText("审计疑点已同步")).toBeInTheDocument();
  });
});
