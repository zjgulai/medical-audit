import { describe, expect, it } from "vitest";

import {
  currentSelfCheckProject,
  getOpenProjectQueueItems,
  getProjectMetricByKey,
  getProjectStageProgress
} from "./projects";

describe("self-check project model", () => {
  it("anchors the workspace to a fund usage self-check project", () => {
    expect(currentSelfCheckProject.id).toBe("SELF-CHECK-FUND-20260607");
    expect(currentSelfCheckProject.name).toBe("医保基金使用合规专项自查");
    expect(currentSelfCheckProject.auditTopic).toBe("医保基金使用合规");
    expect(currentSelfCheckProject.status).toBe("active");
    expect(currentSelfCheckProject.stage).toBe("analyze");
  });

  it("calculates workflow progress from the current project stage", () => {
    expect(getProjectStageProgress(currentSelfCheckProject)).toEqual({
      currentIndex: 3,
      total: 7,
      percent: 43
    });
  });

  it("keeps actionable queue items separate from closed items", () => {
    const openItems = getOpenProjectQueueItems(currentSelfCheckProject);

    expect(openItems).toHaveLength(3);
    expect(openItems.map((item) => item.status)).not.toContain("closed");
  });

  it("returns metrics by stable key", () => {
    expect(getProjectMetricByKey(currentSelfCheckProject, "open_findings")?.value).toBe("12");
    expect(getProjectMetricByKey(currentSelfCheckProject, "missing_evidence")?.tone).toBe("warning");
  });
});
