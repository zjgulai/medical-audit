import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
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
  FundComplianceWorkbench,
  GuidedCheckWorkbench
} from "./compatibility-workbenches";

vi.mock("@/lib/api-client", () => ({
  fetchAuditFindings: vi.fn(),
  fetchReportWorkbench: vi.fn(),
  fetchRulesWorkbench: vi.fn(),
  fetchSearchBackendStatus: vi.fn()
}));

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

function mockBackendReads() {
  fetchAuditFindingsMock.mockResolvedValue(findingsResponse);
  fetchRulesWorkbenchMock.mockResolvedValue(rulesResponse);
  fetchReportWorkbenchMock.mockResolvedValue(reportsResponse);
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
