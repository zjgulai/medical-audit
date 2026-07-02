import { describe, expect, it } from "vitest";
import nextConfig from "../../next.config";

import {
  findNavigationItemForPath,
  navigationGroups,
  primaryNavigation,
  sidebarUtilityNavigation,
  secondaryNavigation,
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
      "/analytics",
      "/graph",
      "/reports",
      "/projects"
    ]);
  });

  it("keeps the portal at nine primary modules", () => {
    expect(primaryNavigation).toHaveLength(9);
  });

  it("promotes document search to a Next-native module", () => {
    const documents = primaryNavigation.find((item) => item.id === "documents");

    expect(documents).toMatchObject({
      label: "文档依据",
      href: "/documents",
      target: "workspace"
    });
  });

  it("keeps data analysis and project management as first-class modules", () => {
    const analytics = primaryNavigation.find((item) => item.id === "analytics");
    const projects = primaryNavigation.find((item) => item.id === "projects");

    expect(analytics).toMatchObject({
      label: "数据分析",
      href: "/analytics",
      target: "workspace"
    });
    expect(projects).toMatchObject({
      label: "项目空间",
      href: "/projects",
      target: "workspace"
    });
  });

  it("marks evidence chat as the core live module", () => {
    const chat = primaryNavigation.find((item) => item.href === "/chat");

    expect(chat).toMatchObject({
      label: "审计助手",
      emphasis: "primary",
      target: "workspace"
    });
  });

  it("does not expose legacy bridge routes as primary navigation", () => {
    expect(primaryNavigation.map((item) => item.href)).not.toEqual(
      expect.arrayContaining(["/guided-check", "/rules", "/remediation", "/archive"])
    );
  });

  it("keeps secondary workspace routes addressable outside the primary sidebar", () => {
    expect(secondaryNavigation.map((item) => item.href)).toEqual(["/guided-check", "/rules", "/remediation", "/archive"]);
    expect(findNavigationItemForPath("/rules")).toMatchObject({
      label: "规则库",
      target: "workspace"
    });
  });

  it("keeps the sidebar visible layer to five common entries", () => {
    expect(visiblePrimaryNavigation.map((item) => item.href)).toEqual([
      "/workspace",
      "/fund-compliance",
      "/chat",
      "/documents",
      "/archive"
    ]);
    expect(sidebarUtilityNavigation.map((item) => item.href)).toEqual(
      expect.arrayContaining(["/agent-market", "/agents", "/analytics", "/projects", "/rules", "/pages/index-admin"])
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
      "/workspace",
      "/fund-compliance",
      "/chat",
      "/documents",
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
