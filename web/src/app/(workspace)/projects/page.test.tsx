import { render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchAuditFindings } from "@/lib/api-client";
import type { AuditFindingsResponse } from "@/lib/api-types";

import ProjectsPage from "./page";

vi.mock("@/components/replica/use-replica-runtime", () => ({
  useReplicaProjectsData: () => ({
    source: "api",
    status: "ready",
    issues: [],
    data: {
      projects: [
        {
          id: "project-001",
          name: "医保基金使用合规审计",
          type: "医保审计",
          owner: "张主任",
          members: 4,
          status: "进行中",
          updatedAt: "2026-07-06",
          progress: 68
        },
        {
          id: "project-002",
          name: "药品目录支付核查",
          type: "专项审计",
          owner: "李审计",
          members: 3,
          status: "底稿编制",
          updatedAt: "2026-07-05",
          progress: 100
        }
      ]
    }
  })
}));

vi.mock("@/lib/api-client", () => ({
  fetchAuditFindings: vi.fn()
}));

const fetchAuditFindingsMock = vi.mocked(fetchAuditFindings);

describe("ProjectsPage", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders the audit cockpit from backend finding statistics", async () => {
    fetchAuditFindingsMock.mockResolvedValue(buildFindingsResponse());

    render(<ProjectsPage />);

    const cockpit = screen.getByLabelText("审计驾驶舱");
    expect(within(cockpit).getByText("总审计条数")).toBeInTheDocument();
    expect(within(cockpit).getByText("待复核")).toBeInTheDocument();
    expect(within(cockpit).getByText("已关联任务")).toBeInTheDocument();
    expect(within(cockpit).getByText("未分配")).toBeInTheDocument();
    expect(within(cockpit).getByText("状态分布")).toBeInTheDocument();
    expect(within(cockpit).getByText("人员承接")).toBeInTheDocument();

    await screen.findByText("疑点明细同步");
    expect(within(cockpit).getByText("张主任")).toBeInTheDocument();
    expect(fetchAuditFindingsMock).toHaveBeenCalledTimes(1);
  });

  it("keeps the cockpit visible when findings are temporarily unavailable", async () => {
    fetchAuditFindingsMock.mockRejectedValue(new Error("findings unavailable"));

    render(<ProjectsPage />);

    await screen.findByText("项目列表兜底");
    const cockpit = screen.getByLabelText("审计驾驶舱");
    expect(within(cockpit).getByText("总审计条数")).toBeInTheDocument();
    expect(within(cockpit).getByText("张主任")).toBeInTheDocument();
  });
});

function buildFindingsResponse(): AuditFindingsResponse {
  return {
    items: [
      {
        finding_key: "finding-001",
        status: "open",
        finding_type: "医保费用异常",
        severity: "high",
        review_status: "pending-review",
        review_task_id: null,
        source_record_locator: {},
        calculation_trace: {},
        metadata: { owner: "张主任" },
        created_at: "2026-07-06T00:00:00Z",
        updated_at: "2026-07-06T00:00:00Z",
        audit_run_key: null,
        audit_task_key: null,
        rule_key: null,
        rule_version_key: null,
        evidence_items: []
      },
      {
        finding_key: "finding-002",
        status: "open",
        finding_type: "重复收费",
        severity: "medium",
        review_status: "closed",
        review_task_id: "task-001",
        source_record_locator: {},
        calculation_trace: {},
        metadata: { owner: "李审计" },
        created_at: "2026-07-06T00:00:00Z",
        updated_at: "2026-07-06T00:00:00Z",
        audit_run_key: null,
        audit_task_key: null,
        rule_key: null,
        rule_version_key: null,
        evidence_items: []
      }
    ],
    stats: {
      total: 2,
      open: 2,
      pending_review: 1,
      linked_review_task: 1
    },
    filters: {
      review_status: null,
      limit: 100
    },
    review_status_options: {
      "pending-review": "待复核",
      closed: "已关闭"
    },
    generation_readiness: {
      status: "generated",
      ready: true,
      has_findings: true,
      table_counts: { audit_findings: 2 },
      prerequisites: [],
      blocking_reasons: [],
      next_actions: []
    },
    store: {
      ready: true,
      backend: "SqlAlchemyAuditFindingStore"
    }
  };
}
