import { describe, expect, it } from "vitest";

import { classifyWorkbenchEvidence, isReadonlySeedBackend } from "./workbench-evidence";

describe("workbench evidence classification", () => {
  it("keeps loading transport separate from evidence persistence", () => {
    expect(classifyWorkbenchEvidence("loading", { ready: false, backend: "unknown" })).toMatchObject({
      label: "连接中",
      tone: "info",
      isPersistent: false
    });
  });

  it("does not treat readonly seed backends as persistent stores", () => {
    expect(isReadonlySeedBackend("ReadonlyGraphWorkbenchSeed")).toBe(true);
    expect(
      classifyWorkbenchEvidence("ready", { ready: true, backend: "ReadonlyGraphWorkbenchSeed" })
    ).toMatchObject({
      label: "后端种子数据",
      tone: "warning",
      isSeed: true,
      isPersistent: false
    });
  });

  it("marks static fallback data as local samples", () => {
    expect(
      classifyWorkbenchEvidence("ready", { ready: false, backend: "portal-data-static-fallback" })
    ).toMatchObject({
      label: "本地样例兜底",
      tone: "warning",
      isFallback: true,
      isPersistent: false
    });
  });

  it("marks non-seed ready stores as persistent backends", () => {
    expect(classifyWorkbenchEvidence("ready", { ready: true, backend: "PostgresWorkbenchStore" })).toMatchObject({
      label: "持久后端",
      tone: "success",
      isPersistent: true
    });
  });
});
