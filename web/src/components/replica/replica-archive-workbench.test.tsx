import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchArchiveWorkbench } from "@/lib/api-client";
import type { ArchiveWorkbenchResponse } from "@/lib/api-types";

import { ReplicaArchiveWorkbench } from "./replica-archive-workbench";

vi.mock("@/lib/api-client", () => ({
  fetchArchiveWorkbench: vi.fn()
}));

const fetchArchiveWorkbenchMock = vi.mocked(fetchArchiveWorkbench);

const archiveResponse: ArchiveWorkbenchResponse = {
  format: "archive-workbench-v1",
  generated_at: "2026-07-16T09:00:00Z",
  archive_id: "archive-runtime-001",
  archive_title: "审计归档",
  archive_scope: "报告、证据与运行清单",
  archive_packages: [
    {
      id: "archive-package-001",
      projectName: "医保基金专项审计",
      archiveNo: "ARCHIVE-001",
      status: "已归档",
      reportNo: "REPORT-001",
      owner: "内审部",
      archiveScope: "审计报告与整改证据",
      evidenceSummary: "证据清单 12 项",
      signedAt: "2026-07-16T08:00:00Z",
      retainedUntil: "2036-07-16",
      href: "/archive/archive-package-001",
      logHref: "/archive#archive-runs-title"
    }
  ],
  audit_runs: [
    {
      id: "archive-run-001",
      title: "归档完整性检查",
      status: "通过",
      time: "2026-07-16T08:30:00Z",
      archiveRoot: "/archives/ARCHIVE-001",
      manifestCount: 12,
      failedCount: 0,
      detail: "归档清单完整。"
    }
  ],
  signature_items: [
    {
      id: "signature-001",
      label: "报告签名",
      status: "验签通过",
      sha256: "sha256-runtime-001",
      detail: "签名与归档报告一致。"
    }
  ],
  policy_items: [
    {
      id: "policy-001",
      label: "保留期限",
      value: "10 年",
      detail: "按审计档案制度保留。"
    }
  ],
  timeline: [
    {
      id: "archive-timeline-001",
      time: "2026-07-16T08:45:00Z",
      title: "归档完成",
      detail: "归档包已登记。",
      status: "已入档"
    }
  ],
  metrics: {
    package_count: 1,
    archived_package_count: 1,
    pending_package_count: 0,
    blocked_package_count: 0,
    audit_run_count: 1,
    signature_count: 1,
    policy_count: 1,
    timeline_count: 1,
    latest_archive_run_status: "通过"
  },
  evidence_grade: "production-readonly-api",
  production_side_effect: "audit-log-only",
  store: { ready: true, backend: "SqlAlchemyArchiveWorkbenchStore" }
};

describe("ReplicaArchiveWorkbench", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders archive packages, signatures, policies and audit runs from the API", async () => {
    fetchArchiveWorkbenchMock.mockResolvedValue(archiveResponse);

    render(<ReplicaArchiveWorkbench />);

    expect(await screen.findByRole("heading", { name: "医保基金专项审计" })).toBeInTheDocument();
    expect(screen.getByText("验签通过")).toBeInTheDocument();
    expect(screen.getByText("SqlAlchemyArchiveWorkbenchStore")).toBeInTheDocument();
    expect(screen.getByText("archive-package-001").closest("details")).not.toBeNull();
    expect(screen.getByRole("link", { name: "查看归档检查" })).toHaveAttribute(
      "href",
      "/archive#archive-runs-title"
    );
  });

  it("keeps technical production values in diagnostics and presents readable labels", async () => {
    fetchArchiveWorkbenchMock.mockResolvedValue({
      ...archiveResponse,
      archive_packages: [{
        ...archiveResponse.archive_packages[0]!,
        owner: "it-admin / department-head"
      }],
      audit_runs: [{
        ...archiveResponse.audit_runs[0]!,
        archiveRoot: "audit-log-events/YYYY/MM/DD/<batch-key>.jsonl"
      }],
      policy_items: [{
        ...archiveResponse.policy_items[0]!,
        value: "180 days",
        detail: "response-only"
      }]
    });

    render(<ReplicaArchiveWorkbench />);

    expect(await screen.findByText("系统管理员、部门负责人")).toBeInTheDocument();
    expect(screen.getByText("180 天")).toBeInTheDocument();
    expect(screen.getByText("audit-log-events/YYYY/MM/DD/<batch-key>.jsonl").closest("details")).not.toBeNull();
    expect(screen.getByText(/当前为生产只读证据/)).toBeInTheDocument();
    expect(screen.getByText("production-readonly-api").closest("details")).not.toBeNull();
  });

  it("does not expose zero metrics or retired fixtures while the initial read is pending", () => {
    fetchArchiveWorkbenchMock.mockReturnValue(new Promise(() => undefined));

    render(<ReplicaArchiveWorkbench />);

    expect(screen.getByText("归档数据加载中")).toBeInTheDocument();
    expect(screen.queryByText("归档包")).not.toBeInTheDocument();
    expect(screen.queryByText("archive-package-fund-self-check")).not.toBeInTheDocument();
  });

  it("uses the strict empty contract when every archive collection is empty", async () => {
    fetchArchiveWorkbenchMock.mockResolvedValue({
      ...archiveResponse,
      archive_packages: [],
      audit_runs: [],
      signature_items: [],
      policy_items: [],
      timeline: [],
      metrics: {
        ...archiveResponse.metrics,
        package_count: 0,
        archived_package_count: 0,
        pending_package_count: 0,
        blocked_package_count: 0,
        audit_run_count: 0,
        signature_count: 0,
        policy_count: 0,
        timeline_count: 0,
        latest_archive_run_status: "暂无运行"
      }
    });

    render(<ReplicaArchiveWorkbench />);

    expect(await screen.findByText("暂无归档包、运行、签名、策略或时间线记录")).toBeInTheDocument();
    expect(screen.getByText("SqlAlchemyArchiveWorkbenchStore")).toBeInTheDocument();
    expect(screen.queryByText("archive-package-fund-self-check")).not.toBeInTheDocument();
  });

  it("fails closed when the archive API rejects", async () => {
    fetchArchiveWorkbenchMock.mockRejectedValue(new Error("archive unavailable"));

    render(<ReplicaArchiveWorkbench />);

    expect(await screen.findByText("归档工作台暂不可用")).toBeInTheDocument();
    expect(screen.getByText("归档数据读取失败，页面不会注入本地样例或旧数据。")).toBeInTheDocument();
    expect(screen.queryByText(/归档 API/)).not.toBeInTheDocument();
    expect(screen.queryByText("archive-package-001")).not.toBeInTheDocument();
    expect(screen.queryByText("archive-package-fund-self-check")).not.toBeInTheDocument();
  });

  it("fails closed when the archive store is not ready", async () => {
    fetchArchiveWorkbenchMock.mockResolvedValue({
      ...archiveResponse,
      store: { ready: false, backend: "unavailable" }
    });

    render(<ReplicaArchiveWorkbench />);

    expect(await screen.findByText("归档数据受限")).toBeInTheDocument();
    expect(screen.getByText("归档存储状态未就绪，已停止展示可能不完整的归档记录。")).toBeInTheDocument();
    expect(screen.queryByText("archive-package-001")).not.toBeInTheDocument();
  });
});
