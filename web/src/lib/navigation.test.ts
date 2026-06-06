import { describe, expect, it } from "vitest";

import { primaryNavigation } from "./navigation";

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
