import { describe, expect, it } from "vitest";
import nextConfig from "../../next.config";

import {
  findNavigationItemForPath,
  navigationGroups,
  primaryNavigation,
  sidebarUtilityNavigation,
  systemNavigation,
  visiblePrimaryNavigation
} from "./navigation";
import { workflowStages } from "./workflow";

describe("primaryNavigation", () => {
  it("keeps the AI audit portal module order stable", () => {
    expect(primaryNavigation.map((item) => item.href)).toEqual([
      "/chat",
      "/agents",
      "/agent-market",
      "/knowledge-base",
      "/documents",
      "/ocr",
      "/analytics",
      "/graph",
      "/reports",
      "/projects",
      "/audit-cockpit"
    ]);
  });

  it("keeps the portal at eleven primary modules", () => {
    expect(primaryNavigation).toHaveLength(11);
  });

  it("promotes document search to a Next-native module", () => {
    const documents = primaryNavigation.find((item) => item.id === "documents");

    expect(documents).toMatchObject({
      label: "文档检索",
      href: "/documents",
      target: "workspace"
    });
  });

  it("keeps data analysis and project management as first-class modules", () => {
    const analytics = primaryNavigation.find((item) => item.id === "analytics");
    const projects = primaryNavigation.find((item) => item.id === "projects");

    expect(analytics).toMatchObject({
      label: "AI数据分析",
      href: "/analytics",
      target: "workspace"
    });
    expect(projects).toMatchObject({
      label: "项目管理",
      href: "/projects",
      target: "workspace"
    });
  });

  it("places the audit cockpit first in the primary navigation", () => {
    expect(visiblePrimaryNavigation[0]).toMatchObject({
      id: "audit-cockpit",
      label: "审计驾驶舱",
      href: "/audit-cockpit",
      target: "workspace"
    });
  });

  it("keeps the sidebar visible layer to eight workbench entries", () => {
    expect(visiblePrimaryNavigation.map((item) => item.href)).toEqual([
      "/audit-cockpit",
      "/medical-audit",
      "/chat",
      "/remediation",
      "/reports",
      "/documents",
      "/ocr",
      "/archive"
    ]);
    expect(sidebarUtilityNavigation.map((item) => item.href)).toEqual(
      expect.arrayContaining(["/agent-market", "/agents", "/analytics", "/projects", "/rules", "/graph"])
    );
    expect(sidebarUtilityNavigation.map((item) => item.href)).not.toEqual(
      expect.arrayContaining(systemNavigation.map((item) => item.href))
    );
  });

  it("groups the sidebar around audit workbench concepts", () => {
    expect(navigationGroups.map((group) => group.label)).toEqual([
      "常用入口",
      "审计工具",
      "依据与规则",
      "系统管理"
    ]);
    expect(navigationGroups[0].items.map((item) => item.href)).toEqual([
      "/audit-cockpit",
      "/medical-audit",
      "/chat",
      "/remediation",
      "/reports",
      "/documents",
      "/ocr",
      "/archive"
    ]);
    expect(navigationGroups[3].items).toEqual(systemNavigation);
  });

  it("keeps workbench home and backend system routes addressable for tabs", () => {
    expect(findNavigationItemForPath("/workspace")).toMatchObject({
      label: "工作台",
      target: "workspace"
    });
    expect(findNavigationItemForPath("/pages/index-admin")).toMatchObject({
      label: "索引管理",
      target: "backend"
    });
  });

  it("keeps backend system routes as /pages proxied routes", async () => {
    if (typeof nextConfig.rewrites !== "function") {
      throw new Error("nextConfig.rewrites must be a function in test env.");
    }

    const rules = (await nextConfig.rewrites()) as readonly { readonly source: string; readonly destination: string }[];
    const pagesRewrite = rules.find((rule) => rule.source === "/pages/:path*");

    expect(pagesRewrite).toMatchObject({
      source: "/pages/:path*",
      destination: "http://127.0.0.1:8021/pages/:path*"
    });
    for (const item of systemNavigation) {
      expect(item.target).toBe("backend");
      expect(item.href).toMatch(/^\/pages\//);
    }
  });
});

describe("workflowStages", () => {
  it("keeps the self-check stage order stable", () => {
    expect(workflowStages.map((stage) => stage.stage)).toEqual([
      "intake",
      "retrieve",
      "analyze",
      "clarify",
      "finding",
      "remediation",
      "report"
    ]);
  });

  it("keeps every workflow stage readable", () => {
    for (const stage of workflowStages) {
      expect(stage.label.trim()).not.toBe("");
      expect(stage.description.trim()).not.toBe("");
    }
  });
});
