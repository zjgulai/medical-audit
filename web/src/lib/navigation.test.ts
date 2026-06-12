import { describe, expect, it } from "vitest";

import { findNavigationItemForPath, primaryNavigation, secondaryNavigation } from "./navigation";
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
      label: "文档检索",
      href: "/documents",
      target: "workspace"
    });
  });

  it("keeps data analysis and project management as first-class modules", () => {
    const analytics = primaryNavigation.find((item) => item.id === "analytics");
    const projects = primaryNavigation.find((item) => item.id === "projects");

    expect(analytics).toMatchObject({
      label: "AI 数据分析",
      href: "/analytics",
      target: "workspace"
    });
    expect(projects).toMatchObject({
      label: "项目管理",
      href: "/projects",
      target: "workspace"
    });
  });

  it("marks evidence chat as the core live module", () => {
    const chat = primaryNavigation.find((item) => item.href === "/chat");

    expect(chat).toMatchObject({
      label: "AI 对话",
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
      label: "专题规则库",
      target: "workspace"
    });
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
