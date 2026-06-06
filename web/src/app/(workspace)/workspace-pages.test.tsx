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
});
