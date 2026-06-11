import { describe, expect, it } from "vitest";

import { primaryNavigation } from "./navigation";
import { workflowStages } from "./workflow";

describe("primaryNavigation", () => {
  it("keeps the self-check workflow order stable", () => {
    expect(primaryNavigation.map((item) => item.href)).toEqual([
      "/workspace",
      "/pages/chat",
      "/pages/query",
      "/pages/audit-findings",
      "/pages/review-tasks",
      "/pages/audit-logs",
      "/pages/index-admin"
    ]);
  });

  it("marks evidence chat as the core live module", () => {
    const chat = primaryNavigation.find((item) => item.href === "/pages/chat");

    expect(chat).toMatchObject({
      label: "对话审证",
      emphasis: "primary",
      target: "backend"
    });
  });

  it("does not expose placeholder plan routes as primary navigation", () => {
    expect(primaryNavigation.map((item) => item.href)).not.toEqual(
      expect.arrayContaining(["/guided-check", "/rules", "/analytics", "/graph", "/archive"])
    );
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
