import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { primaryNavigation } from "@/lib/navigation";

import AnalyticsPage from "./analytics/page";
import ArchivePage from "./archive/page";
import DocumentsPage from "./documents/page";
import FindingsPage from "./findings/page";
import GraphPage from "./graph/page";
import GuidedCheckPage from "./guided-check/page";
import RemediationPage from "./remediation/page";
import ReportsPage from "./reports/page";
import RulesPage from "./rules/page";
import WorkspacePage from "./workspace/page";

const routePages = [
  ["/workspace", WorkspacePage],
  ["/guided-check", GuidedCheckPage],
  ["/rules", RulesPage],
  ["/documents", DocumentsPage],
  ["/findings", FindingsPage],
  ["/remediation", RemediationPage],
  ["/reports", ReportsPage],
  ["/analytics", AnalyticsPage],
  ["/graph", GraphPage],
  ["/archive", ArchivePage]
] as const;

describe("workspace foundation pages", () => {
  it("keeps every sidebar target backed by a page with one h1", () => {
    expect(routePages.map(([href]) => href)).toEqual(primaryNavigation.map((item) => item.href));

    for (const [href, Page] of routePages) {
      const { unmount } = render(<Page />);

      expect(screen.getAllByRole("heading", { level: 1 }), href).toHaveLength(1);

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
