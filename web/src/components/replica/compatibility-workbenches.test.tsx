import { render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  addMedicalAuditFindingToReport,
  createMedicalAuditReviewTask,
  createProject,
  createReportDraft,
  fetchAuditFindings,
  fetchReportWorkbench,
  fetchRulesWorkbench,
  fetchSearchBackendStatus
} from "@/lib/api-client";
import type {
  AuditFindingsResponse,
  ReportWorkbenchResponse,
  RulesWorkbenchResponse,
  SearchBackendStatusResponse
} from "@/lib/api-types";

import {
  FundComplianceReviewWorkbench,
  FundComplianceWorkbench,
  GuidedCheckWorkbench
} from "./compatibility-workbenches";

vi.mock("@/lib/api-client", () => ({
  addMedicalAuditFindingToReport: vi.fn(),
  createMedicalAuditReviewTask: vi.fn(),
  createProject: vi.fn(),
  createReportDraft: vi.fn(),
  fetchAuditFindings: vi.fn(),
  fetchReportWorkbench: vi.fn(),
  fetchRulesWorkbench: vi.fn(),
  fetchSearchBackendStatus: vi.fn()
}));

const addMedicalAuditFindingToReportMock = vi.mocked(addMedicalAuditFindingToReport);
const createMedicalAuditReviewTaskMock = vi.mocked(createMedicalAuditReviewTask);
const createProjectMock = vi.mocked(createProject);
const createReportDraftMock = vi.mocked(createReportDraft);
const fetchAuditFindingsMock = vi.mocked(fetchAuditFindings);
const fetchReportWorkbenchMock = vi.mocked(fetchReportWorkbench);
const fetchRulesWorkbenchMock = vi.mocked(fetchRulesWorkbench);
const fetchSearchBackendStatusMock = vi.mocked(fetchSearchBackendStatus);

const findingsResponse: AuditFindingsResponse = {
  items: [
    {
      finding_key: "finding-guided-001",
      status: "open",
      finding_type: "medical-insurance-policy",
      severity: "high",
      review_status: "pending-review",
      review_task_id: null,
      source_record_locator: { visit_id: "VISIT-001" },
      calculation_trace: { amount: 1280 },
      metadata: {},
      created_at: "2026-07-08T08:00:00Z",
      updated_at: "2026-07-08T09:00:00Z",
      audit_run_key: "run-guided",
      audit_task_key: "task-guided",
      rule_key: "rule-guided",
      rule_version_key: "rule-guided@2026-07",
      evidence_items: []
    }
  ],
  stats: { total: 8, open: 5, pending_review: 3, linked_review_task: 2 },
  filters: { review_status: "pending-review", limit: 20 },
  review_status_options: { "pending-review": "待复核" },
  generation_readiness: {
    status: "blocked",
    ready: false,
    has_findings: true,
    table_counts: { audit_projects: 0 },
    prerequisites: [
      { key: "audit_projects", label: "审计项目", count: 0, ready: false, required: true }
    ],
    blocking_reasons: [
      { code: "missing-audit_projects", message: "审计项目为空，无法从规则运行生成疑点。" }
    ],
    next_actions: ["补齐审计项目。"]
  },
  store: { ready: true, backend: "SqlAlchemyAuditFindingStore" }
};

const rulesResponse: RulesWorkbenchResponse = {
  format: "rules-workbench-v1",
  generated_at: "2026-07-08T09:00:00Z",
  ruleset_id: "rules-guided",
  ruleset_title: "医保审计规则",
  ruleset_scope: "医保基金使用合规",
  rule_library_items: [],
  source_coverages: [],
  run_snapshots: [],
  control_gates: [
    {
      id: "gate-fields",
      label: "字段可运行",
      status: "阻断",
      detail: "缺少结算金额字段，规则运行需人工确认。",
      owner: "信息科"
    }
  ],
  metrics: {
    rule_count: 9,
    enabled_rule_count: 7,
    pending_rule_count: 2,
    total_finding_count: 6,
    blocked_gate_count: 1,
    source_count: 3,
    run_count: 2
  },
  evidence_grade: "local-readonly-api",
  production_side_effect: "none",
  store: { ready: true, backend: "ReadonlyRulesWorkbenchSeed" }
};

const reportsResponse: ReportWorkbenchResponse = {
  format: "report-workbench-v1",
  generated_at: "2026-07-08T09:00:00Z",
  template_registry_status: "active",
  template_categories: [
    { id: "plan", label: "计划类", availability: "awaiting-business-template" },
    { id: "workpaper", label: "底稿类", availability: "active" },
    { id: "evidence", label: "取证类", availability: "awaiting-business-template" },
    { id: "confirmation", label: "函证类", availability: "awaiting-business-template" },
    { id: "report", label: "报告类", availability: "awaiting-business-template" },
    { id: "remediation", label: "整改类", availability: "awaiting-business-template" }
  ],
  workpaper_templates: [],
  report_entries: [
    {
      id: "report-guided",
      title: "医保基金复核底稿",
      status: "门禁阻断",
      report_no: "RPT-20260708-001",
      owner: "医保办",
      source: "review-task",
      included_finding_count: 1,
      appendix_count: 0,
      gate_summary: "证据链仍需补齐后生成正式底稿。",
      updated_at: "2026-07-08T09:00:00Z",
      href: "/reports",
      download_links: {
        page: "/reports",
        task_docx: "/api/v1/reports/report-guided/task.docx",
        report_docx: null,
        report_markdown: null,
        report_json: null
      }
    }
  ],
  report_evidence_sources: [],
  metrics: {
    report_count: 1,
    signed_report_count: 0,
    blocked_report_count: 1,
    included_finding_count: 1,
    docx_download_count: 0
  },
  store: { ready: true, backend: "SqlAlchemyReviewTaskStore" }
};

const searchResponse: SearchBackendStatusResponse = {
  backend: "postgres-bm25",
  ready: true,
  details: { matching_embedding_count: 49051 }
};

function reportsWithMetrics(reportCount: number, blockedReportCount: number): ReportWorkbenchResponse {
  return {
    ...reportsResponse,
    report_entries: reportCount === 0 ? [] : reportsResponse.report_entries,
    metrics: {
      ...reportsResponse.metrics,
      report_count: reportCount,
      blocked_report_count: blockedReportCount
    }
  };
}

function mockBackendReads(options: { reports?: ReportWorkbenchResponse; reportsError?: Error } = {}) {
  fetchAuditFindingsMock.mockResolvedValue(findingsResponse);
  fetchRulesWorkbenchMock.mockResolvedValue(rulesResponse);
  if (options.reportsError) {
    fetchReportWorkbenchMock.mockRejectedValue(options.reportsError);
  } else {
    fetchReportWorkbenchMock.mockResolvedValue(options.reports ?? reportsResponse);
  }
  fetchSearchBackendStatusMock.mockResolvedValue(searchResponse);
}

describe("compatibility workbenches", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("connects the fund compliance compatibility page to backend evidence", async () => {
    mockBackendReads();

    render(<FundComplianceWorkbench />);

    await waitFor(() => {
      expect(screen.getByText(/SqlAlchemyAuditFindingStore/)).toBeInTheDocument();
    });
    expect(fetchAuditFindingsMock).toHaveBeenCalledWith("pending-review");
    expect(fetchRulesWorkbenchMock).toHaveBeenCalled();
    expect(fetchReportWorkbenchMock).toHaveBeenCalled();
    expect(fetchSearchBackendStatusMock).toHaveBeenCalled();
    expect(screen.getByText("后端种子数据")).toBeInTheDocument();
    expect(screen.getByText("finding-guided-001")).toBeInTheDocument();
    expect(screen.getByText("待复核疑点")).toBeInTheDocument();
  });

  it("renders four review stages with runtime-derived summaries", async () => {
    mockBackendReads();

    render(<FundComplianceReviewWorkbench />);

    const workflow = await screen.findByRole("region", { name: "医保基金复核四阶段" });
    const stages = within(workflow);
    expect(stages.getByText("单据审查")).toBeInTheDocument();
    expect(stages.getByText("费用表单")).toBeInTheDocument();
    expect(stages.getByText("规则复核")).toBeInTheDocument();
    expect(stages.getByText("底稿输出")).toBeInTheDocument();
    expect(await stages.findByText("3 项待复核疑点")).toBeInTheDocument();
    expect(await stages.findByText("费用汇总、分类汇总、就诊明细 · 0 个底稿模板")).toBeInTheDocument();
    expect(await stages.findByText("1 项阻断门禁 / 1 项控制门禁")).toBeInTheDocument();
    expect(await stages.findByText("1 项底稿 / 1 项阻断")).toBeInTheDocument();
    expect(stages.getByRole("link", { name: "打开单据审查" })).toHaveAttribute("href", "/medical-audit");
    expect(stages.getByRole("link", { name: "打开费用表单" })).toHaveAttribute("href", "/analytics");
    expect(stages.getByRole("link", { name: "打开规则复核" })).toHaveAttribute("href", "/rules");
    expect(stages.getByRole("link", { name: "打开底稿输出" })).toHaveAttribute("href", "/reports");
  });

  it.each([
    {
      name: "reports fallback",
      options: { reportsError: new Error("reports unavailable") },
      expectedStatus: "本地样例",
      expectedSummary: "暂无底稿"
    },
    {
      name: "ready with no reports",
      options: { reports: reportsWithMetrics(0, 0) },
      expectedStatus: "需处理",
      expectedSummary: "暂无底稿"
    },
    {
      name: "ready with blocked reports",
      options: { reports: reportsWithMetrics(1, 1) },
      expectedStatus: "需处理",
      expectedSummary: "1 项底稿 / 1 项阻断"
    },
    {
      name: "ready with unblocked reports",
      options: { reports: reportsWithMetrics(1, 0) },
      expectedStatus: "已就绪",
      expectedSummary: "1 项底稿 / 0 项阻断"
    }
  ])("derives the workpaper stage for $name", async ({ options, expectedStatus, expectedSummary }) => {
    mockBackendReads(options);

    render(<FundComplianceReviewWorkbench />);

    const workflow = await screen.findByRole("region", { name: "医保基金复核四阶段" });
    const stageHeading = within(workflow).getByRole("heading", { name: "底稿输出" });
    const stage = stageHeading.closest("article");
    expect(stage).not.toBeNull();
    expect(await within(stage!).findByText(expectedStatus)).toBeInTheDocument();
    expect(within(stage!).getByText(expectedSummary)).toBeInTheDocument();
  });

  it("shows an actionable empty state instead of 0/0 for report readiness", async () => {
    mockBackendReads({ reports: reportsWithMetrics(0, 0) });

    render(<FundComplianceWorkbench />);

    const heading = await screen.findByRole("heading", { name: "底稿就绪状态" });
    const card = heading.closest("article");
    expect(card).not.toBeNull();
    expect(await within(card!).findByText("需处理")).toBeInTheDocument();
    expect(within(card!).getByText("暂无底稿")).toBeInTheDocument();
    expect(within(card!).getByText("当前没有可用底稿。")).toBeInTheDocument();
    expect(within(card!).queryByText("0/0")).not.toBeInTheDocument();
  });

  it("does not execute workflow writes while rendering the review stages", async () => {
    mockBackendReads();

    render(<FundComplianceReviewWorkbench />);

    const workflow = await screen.findByRole("region", { name: "医保基金复核四阶段" });
    await within(workflow).findByText("3 项待复核疑点");
    expect(createProjectMock).not.toHaveBeenCalled();
    expect(createMedicalAuditReviewTaskMock).not.toHaveBeenCalled();
    expect(createReportDraftMock).not.toHaveBeenCalled();
    expect(addMedicalAuditFindingToReportMock).not.toHaveBeenCalled();
  });

  it("summarizes pending findings, blocking gates, report readiness and guided risk", async () => {
    mockBackendReads();

    const { unmount } = render(<FundComplianceWorkbench />);

    expect(await screen.findByRole("heading", { name: "当前待复核疑点" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "阻断控制门禁" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "底稿就绪状态" })).toBeInTheDocument();

    unmount();
    mockBackendReads();
    render(<GuidedCheckWorkbench />);

    expect(await screen.findByRole("heading", { name: "风险摘要" })).toBeInTheDocument();
    expect(screen.getByText("3 项待复核 · 1 项规则阻断 · 1 项底稿阻断")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "最近进展" })).toBeInTheDocument();
  });

  it("connects guided check evidence gates to findings, rules, reports, and search state", async () => {
    mockBackendReads();

    render(<GuidedCheckWorkbench />);

    await waitFor(() => {
      expect(screen.getByText("审计项目")).toBeInTheDocument();
    });
    expect(screen.getByText("字段可运行")).toBeInTheDocument();
    expect(screen.getByText("医保基金复核底稿")).toBeInTheDocument();
    expect(screen.getByText("检索状态")).toBeInTheDocument();
    expect(screen.getByText("就绪")).toBeInTheDocument();
  });

  it("keeps the compatibility pages usable when backend reads are unavailable", async () => {
    fetchAuditFindingsMock.mockRejectedValue(new Error("findings unavailable"));
    fetchRulesWorkbenchMock.mockRejectedValue(new Error("rules unavailable"));
    fetchReportWorkbenchMock.mockRejectedValue(new Error("reports unavailable"));
    fetchSearchBackendStatusMock.mockRejectedValue(new Error("search unavailable"));

    render(<GuidedCheckWorkbench />);

    await waitFor(() => {
      expect(screen.getByText("本地样例")).toBeInTheDocument();
    });
    expect(screen.getByText("目录限制 HIS 字段截图")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "进入 AI 对话" })).toHaveAttribute("href", "/chat");
  });
});
