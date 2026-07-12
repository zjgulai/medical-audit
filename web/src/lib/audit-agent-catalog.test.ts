import { afterEach, describe, expect, it, vi } from "vitest";

import * as agentCatalog from "./audit-agent-catalog";
import { referenceMarketAgents } from "./reference-replica-data";

const catalogExports = agentCatalog as unknown as Record<string, unknown>;

const EXTENSION_VALIDATION_KEYS = [
  ["财务收支审计", "超标准举办会议"],
  ["采购招标审计", "违法订立与招投标文件不符的合同或协议"],
  ["工程审计", "未经批准，擅自改变工程建设项目招标方式"]
] as const;

describe("audit agent catalog scope", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("exports exactly the three backend-aligned medical audit agents", () => {
    expect(catalogExports).toHaveProperty("medicalAuditAgentCatalog");

    const medicalCatalog = catalogExports.medicalAuditAgentCatalog as readonly Record<string, unknown>[] | undefined;
    expect(medicalCatalog).toEqual([
      expect.objectContaining({
        id: "agent-citation-check",
        name: "引用依据核验助手",
        category: "业务类",
        topic: "医保基金使用合规",
        project: "医保基金使用合规专项自查",
        prompt: "只基于命中的法规、目录、规则和风险清单回答；没有引用时输出待补证据。"
      }),
      expect.objectContaining({
        id: "agent-duplicate-charge",
        name: "重复收费复核助手",
        category: "业务类",
        topic: "收费明细复核",
        project: "医保基金使用合规专项自查",
        prompt: "围绕同就诊、同项目、同日期的重复收费线索，列出应核验的执行记录、数量和例外情形。"
      }),
      expect.objectContaining({
        id: "agent-report-draft",
        name: "底稿摘要助手",
        category: "效率类",
        topic: "审计底稿",
        project: "医保基金使用合规专项自查",
        prompt: "把已复核的引用、疑点和附件清单整理为底稿摘要，保留待人工确认标记。"
      })
    ]);
  });

  it("deduplicates the exact three extension source rows and retains template provenance", () => {
    expect(catalogExports).toHaveProperty("auditExtensionValidationCatalog");

    const extensionCatalog = catalogExports.auditExtensionValidationCatalog as readonly Record<string, unknown>[] | undefined;
    expect(extensionCatalog?.map((agent) => [agent.category, agent.name])).toEqual(EXTENSION_VALIDATION_KEYS);
    expect(new Set(extensionCatalog?.map((agent) => `${agent.category}::${agent.name}`)).size).toBe(3);
    expect(extensionCatalog?.map((agent) => [agent.sourceFile, agent.templateKey])).toEqual([
      ["1，财务收支审计.ods", "audit-agent-prompts-0613-002"],
      ["2，采购招标审计.ods", "audit-agent-prompts-0613-064"],
      ["3，工程审计.ods", "audit-agent-prompts-0613-095"]
    ]);
    for (const agent of extensionCatalog ?? []) {
      expect(agent.sourceFile).toMatch(/\.ods$/);
      expect(agent.templateKey).toMatch(/^audit-agent-prompts-0613-\d{3}$/);
      expect(agent.prompt).toEqual(expect.any(String));
      expect((agent.prompt as string).length).toBeGreaterThan(0);
      expect(agent.catalogScope).toBe("extension-validation");
    }
  });

  it("keeps the default marketplace medical-only and reads the opt-in flag per call", () => {
    expect(referenceMarketAgents.map((agent) => agent.id)).toEqual([
      "agent-citation-check",
      "agent-duplicate-charge",
      "agent-report-draft"
    ]);
    expect(referenceMarketAgents.some((agent) =>
      EXTENSION_VALIDATION_KEYS.some(([category, title]) => agent.category === category && agent.name === title)
    )).toBe(false);

    expect(catalogExports).toHaveProperty("getAuditAgentMarketCatalog");
    const getMarketCatalog = catalogExports.getAuditAgentMarketCatalog as (() => readonly Record<string, unknown>[]) | undefined;

    vi.stubEnv("NEXT_PUBLIC_MEDICAL_AUDIT_AGENT_EXTENSION_PACK", "1");
    expect(getMarketCatalog?.().map((agent) => agent.id)).toHaveLength(6);
    expect(getMarketCatalog?.().slice(3).map((agent) => [agent.category, agent.name])).toEqual(
      EXTENSION_VALIDATION_KEYS
    );

    vi.stubEnv("NEXT_PUBLIC_MEDICAL_AUDIT_AGENT_EXTENSION_PACK", "0");
    expect(getMarketCatalog?.().map((agent) => agent.id)).toEqual([
      "agent-citation-check",
      "agent-duplicate-charge",
      "agent-report-draft"
    ]);
  });
});
