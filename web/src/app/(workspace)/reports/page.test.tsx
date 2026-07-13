import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AuditUserProvider } from "@/components/shell/audit-user-context";
import {
  createReportDraft,
  downloadAuditArtifact,
  fetchProjects,
  fetchReportWorkbench
} from "@/lib/api-client";

import ReportsPage from "./page";

vi.mock("@/lib/api-client", () => ({
  createReportDraft: vi.fn(),
  downloadAuditArtifact: vi.fn(),
  fetchProjects: vi.fn(),
  fetchReportWorkbench: vi.fn()
}));

const fetchProjectsMock = vi.mocked(fetchProjects);
const fetchReportWorkbenchMock = vi.mocked(fetchReportWorkbench);
const createReportDraftMock = vi.mocked(createReportDraft);
const downloadAuditArtifactMock = vi.mocked(downloadAuditArtifact);

const templateCategories = [
  { id: "plan", label: "计划类", availability: "awaiting-business-template" },
  { id: "workpaper", label: "底稿类", availability: "active" },
  { id: "evidence", label: "取证类", availability: "awaiting-business-template" },
  { id: "confirmation", label: "函证类", availability: "awaiting-business-template" },
  { id: "report", label: "报告类", availability: "awaiting-business-template" },
  { id: "remediation", label: "整改类", availability: "awaiting-business-template" }
] as const;

const workpaperTemplates = [
  ["workpaper-summary-risk", "费用汇总风险底稿", "费用分类汇总"],
  ["workpaper-category-review", "分类费用复核清单", "平均费用偏离"],
  ["workpaper-visit-detail", "就诊明细疑点摘要", "就诊记录号"]
].map(([id, name, field]) => ({
  id,
  category_id: "workpaper" as const,
  name,
  source_template_id: `${id}-source`,
  source_table: `${name}来源表`,
  source_file_name: `${name}.xlsx`,
  sheet_name: "汇总表",
  output_type: "底稿草稿",
  registry_status: "active",
  expected_columns: [field],
  key_checks: [`核对${field}`],
  evidence_bindings: [field],
  prompt: `生成${name}`,
  chat_href: "/chat"
}));

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
  fetchReportWorkbenchMock.mockResolvedValue({
    format: "report-workbench-v1",
    generated_at: "2026-07-12T08:00:00Z",
    template_registry_status: "active",
    template_categories: templateCategories,
    workpaper_templates: workpaperTemplates,
    report_entries: [],
    report_evidence_sources: [],
    metrics: {
      report_count: 0,
      signed_report_count: 0,
      blocked_report_count: 0,
      included_finding_count: 0,
      docx_download_count: 0
    },
    store: { ready: true, backend: "JsonFileReviewTaskStore" }
  });
  fetchProjectsMock.mockResolvedValue({
    items: [
      {
        id: "SELF-CHECK-FUND-20260607",
        name: "医保基金使用合规专项自查",
        audit_topic: "医保基金使用合规",
        organization_name: "测试医院",
        member_count: 3,
        creator: "审计办",
        creator_user_identifier: "next-admin",
        created_at: "2026-07-12T08:00:00Z",
        status: "进行中",
        operation_label: "进入项目",
        source: "system-default"
      }
    ],
    roles: ["项目负责人", "审计员", "业务专家", "信息科", "只读观察员"],
    statuses: ["在项目中", "待确认"],
    project_statuses: ["待开始", "进行中", "已完成", "已归档"],
    store: { ready: true, backend: "SqlAlchemyProjectMemberStore" }
  });
  createReportDraftMock.mockRejectedValue(new Error("not configured"));
  downloadAuditArtifactMock.mockRejectedValue(new Error("not configured"));
});

describe("ReportsPage", () => {
  it("replaces the preview with the six-category report workbench", async () => {
    render(
      <AuditUserProvider>
        <ReportsPage />
      </AuditUserProvider>
    );

    expect(screen.queryByText("内测中")).not.toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "审计底稿与报告台账" })).toBeInTheDocument();

    const catalog = screen.getByRole("region", { name: "报表分类目录" });
    expect(within(catalog).getAllByRole("heading", { level: 3 }).map((heading) => heading.textContent)).toEqual(
      ["计划类", "底稿类", "取证类", "函证类", "报告类", "整改类"]
    );
    expect(within(catalog).getAllByRole("button", { name: /^填写模板：/ })).toHaveLength(3);
    expect(within(catalog).getAllByText("待业务模板确认")).toHaveLength(5);

    expect(screen.getByRole("combobox", { name: "所属项目" })).toHaveValue("");
    expect(createReportDraftMock).not.toHaveBeenCalled();
  });
});
