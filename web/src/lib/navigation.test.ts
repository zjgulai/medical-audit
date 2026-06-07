import { describe, expect, it } from "vitest";

import { primaryNavigation } from "./navigation";
import { workflowStages } from "./workflow";

describe("primaryNavigation", () => {
  it("keeps the self-check workflow order stable", () => {
    expect(primaryNavigation.map((item) => item.href)).toEqual([
      "/workspace",
      "/guided-check",
      "/rules",
      "/documents",
      "/findings",
      "/remediation",
      "/reports",
      "/analytics",
      "/graph",
      "/archive"
    ]);
  });

  it("marks AI guided self-check as the core module", () => {
    const guidedCheck = primaryNavigation.find((item) => item.href === "/guided-check");

    expect(guidedCheck).toMatchObject({
      label: "AI 引导自查",
      emphasis: "primary"
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
