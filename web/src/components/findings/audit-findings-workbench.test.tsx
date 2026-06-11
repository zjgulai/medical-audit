import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchAuditFindings } from "@/lib/api-client";

import { AuditFindingsWorkbench } from "./audit-findings-workbench";

vi.mock("@/lib/api-client", () => ({
  fetchAuditFindings: vi.fn()
}));

const fetchAuditFindingsMock = vi.mocked(fetchAuditFindings);

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
});
