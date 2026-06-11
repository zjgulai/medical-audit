import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { primaryNavigation } from "@/lib/navigation";

import AnalyticsPage from "./analytics/page";
import ArchivePage from "./archive/page";
import DocumentsPage from "./documents/page";
import FindingsPage from "./findings/page";
import GraphPage from "./graph/page";
import GuidedCheckPage from "./guided-check/page";
import KnowledgeQueryPage from "./knowledge-query/page";
import RemediationPage from "./remediation/page";
import ReportsPage from "./reports/page";
import RulesPage from "./rules/page";
import WorkspacePage from "./workspace/page";

vi.mock("@/lib/api-client", () => ({
  fetchAuditFindings: vi.fn(async () => ({
    items: [],
    stats: { total: 0, open: 0, pending_review: 0, linked_review_task: 0 },
    filters: { review_status: null, limit: 100 },
    review_status_options: { "pending-review": "待复核" },
    store: { ready: true, backend: "SqlAlchemyAuditFindingStore" }
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
  })),
  runKnowledgeQuery: vi.fn()
}));

const routePages = [
  ["/workspace", WorkspacePage],
  ["/knowledge-query", KnowledgeQueryPage],
  ["/findings", FindingsPage],
] as const;

const legacyBridgePages = [
  ["/guided-check", GuidedCheckPage, "/pages/chat"],
  ["/rules", RulesPage, "/pages/index-admin"],
  ["/documents", DocumentsPage, "/knowledge-query"],
  ["/remediation", RemediationPage, "/pages/review-tasks"],
  ["/reports", ReportsPage, "/pages/review-tasks"],
  ["/analytics", AnalyticsPage, "/pages/index-admin"],
  ["/graph", GraphPage, "/workspace"],
  ["/archive", ArchivePage, "/pages/audit-logs"]
] as const;

describe("workspace foundation pages", () => {
  it("keeps Next-owned sidebar targets backed by a page with one h1", () => {
    expect(routePages.map(([href]) => href)).toEqual(
      primaryNavigation.filter((item) => item.target === "workspace").map((item) => item.href)
    );

    for (const [href, Page] of routePages) {
      const { unmount } = render(<Page />);

      expect(screen.getAllByRole("heading", { level: 1 }), href).toHaveLength(1);

      unmount();
    }
  });

  it("keeps legacy plan routes as bridges to real production pages", () => {
    for (const [href, Page, targetHref] of legacyBridgePages) {
      const { container, unmount } = render(<Page />);

      expect(container.textContent, href).not.toMatch(/Plan \d+/);
      expect(screen.getByRole("link"), href).toHaveAttribute("href", targetHref);

      unmount();
    }
  });

  it("exposes the dashboard sections owned by the workspace page", () => {
    render(<WorkspacePage />);

    expect(screen.getByRole("region", { name: "项目关键指标" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "当前阶段：形成判断" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "需要人工处理" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "项目审计链动态" })).toBeInTheDocument();
  });

  it("renders the current self-check project dashboard", () => {
    render(<WorkspacePage />);

    expect(screen.getByRole("heading", { name: "医保基金使用合规专项自查" })).toBeInTheDocument();
    expect(screen.getByText("待处理疑点")).toBeInTheDocument();
    expect(screen.getByText("待补证据")).toBeInTheDocument();
  });
});
