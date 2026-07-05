import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchAuditFindings } from "@/lib/api-client";
import type { AuditFindingGenerationReadiness } from "@/lib/api-types";

import { AuditFindingsWorkbench } from "./audit-findings-workbench";

vi.mock("@/lib/api-client", () => ({
  fetchAuditFindings: vi.fn()
}));

const fetchAuditFindingsMock = vi.mocked(fetchAuditFindings);

const generatedReadiness = {
  status: "generated",
  ready: true,
  has_findings: true,
  table_counts: { audit_findings: 1 },
  prerequisites: [],
  blocking_reasons: [],
  next_actions: ["从疑点清单创建人工复核任务，完成复核后再进入底稿或报告。"]
} satisfies AuditFindingGenerationReadiness;

const blockedReadiness = {
  status: "blocked",
  ready: false,
  has_findings: false,
  table_counts: { audit_projects: 0, his_staging_rows: 0, audit_findings: 0 },
  prerequisites: [
    { key: "audit_projects", label: "审计项目", count: 0, ready: false, required: true },
    { key: "his_staging_rows", label: "HIS staging 行", count: 0, ready: false, required: true }
  ],
  blocking_reasons: [
    { code: "missing-audit_projects", message: "审计项目为空，无法从规则运行生成疑点。" },
    {
      code: "missing-his_staging_rows",
      message: "HIS staging 行为空，无法从规则运行生成疑点。"
    }
  ],
  next_actions: [
    "导入脱敏 HIS 样本，生成 his_source_batches、his_table_schemas、his_field_mappings 和 his_staging_rows。"
  ]
} satisfies AuditFindingGenerationReadiness;

describe("AuditFindingsWorkbench", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("loads audit findings through the API-first client", async () => {
    fetchAuditFindingsMock.mockResolvedValue({
      items: [
        {
          finding_key: "finding-001",
          status: "open",
          finding_type: "duplicate-charge",
          severity: "high",
          review_status: "pending-review",
          review_task_id: null,
          source_record_locator: { source_table: "charge_detail", record_ids: ["CD0001"] },
          calculation_trace: { matched_charge_detail_ids: ["CD0001", "CD0002"] },
          metadata: {},
          created_at: "2026-06-11T00:00:00Z",
          updated_at: "2026-06-11T00:00:00Z",
          audit_run_key: "run-001",
          audit_task_key: "task-001",
          rule_key: "CHARGE-RULE-001",
          rule_version_key: "CHARGE-RULE-001@2026-06",
          evidence_items: [
            {
              evidence_type: "rule-rationale",
              chunk_id: "11111111-1111-4111-8111-111111111111",
              source_package_version_key: "package-v1",
              index_version_key: "index-v1",
              citation_id: "C1",
              locator: { source_path: "法规/law.md" },
              snippet: "重复收费需要核验。",
              metadata: {},
              created_at: "2026-06-11T00:00:00Z"
            }
          ]
        }
      ],
      stats: { total: 1, open: 1, pending_review: 1, linked_review_task: 0 },
      filters: { review_status: null, limit: 100 },
      review_status_options: { "pending-review": "待复核", closed: "已关闭" },
      generation_readiness: generatedReadiness,
      store: { ready: true, backend: "SqlAlchemyAuditFindingStore" }
    });

    render(<AuditFindingsWorkbench />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /duplicate-charge/ })).toBeInTheDocument();
    });

    expect(fetchAuditFindingsMock).toHaveBeenCalledWith(undefined);
    expect(screen.getByText("规则命中疑点工作台")).toBeInTheDocument();
    expect(screen.getByText("CHARGE-RULE-001@2026-06")).toBeInTheDocument();
    expect(screen.getByText("重复收费需要核验。")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "导出疑点 JSON" })).toHaveAttribute(
      "href",
      "/audit-findings/finding-001/export"
    );
    expect(screen.getByRole("button", { name: "创建复核任务" }).closest("form")).toHaveAttribute(
      "action",
      "/pages/audit-findings/finding-001/review-task"
    );

    fireEvent.change(screen.getByLabelText("复核状态"), { target: { value: "closed" } });

    await waitFor(() => {
      expect(fetchAuditFindingsMock).toHaveBeenLastCalledWith("closed");
    });
  });

  it("shows a conservative error state when the backend list fails", async () => {
    fetchAuditFindingsMock.mockRejectedValue(new Error("backend failed"));

    render(<AuditFindingsWorkbench />);

    await waitFor(() => {
      expect(
        screen.getByText("疑点清单加载失败。请确认后端数据库和审计疑点表已就绪。")
      ).toBeInTheDocument();
    });
  });

  it("explains why no generated findings are available", async () => {
    fetchAuditFindingsMock.mockResolvedValue({
      items: [],
      stats: { total: 0, open: 0, pending_review: 0, linked_review_task: 0 },
      filters: { review_status: null, limit: 100 },
      review_status_options: { "pending-review": "待复核" },
      generation_readiness: blockedReadiness,
      store: { ready: true, backend: "SqlAlchemyAuditFindingStore" }
    });

    render(<AuditFindingsWorkbench />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "疑点生成链路未就绪" })).toBeInTheDocument();
    });
    expect(screen.getByText("审计项目")).toBeInTheDocument();
    expect(screen.getByText("HIS staging 行")).toBeInTheDocument();
    expect(screen.getByText("blocked")).toBeInTheDocument();
  });
});
