import rawAgentPrompts from "@/data/audit-agent-prompts.json";

import type { ReferenceAgentCard } from "./reference-replica-data";

type RawAuditAgentPrompt = {
  readonly category: string;
  readonly title: string;
  readonly intro?: string;
  readonly scene?: string;
  readonly tags?: string;
  readonly prompt?: string;
  readonly source?: string;
};

const EXTENSION_VALIDATION_KEYS = [
  ["财务收支审计", "超标准举办会议"],
  ["采购招标审计", "违法订立与招投标文件不符的合同或协议"],
  ["工程审计", "未经批准，擅自改变工程建设项目招标方式"]
] as const;
const extensionAgentTones: readonly ReferenceAgentCard["tone"][] = ["amber", "rose", "slate"];

function normalizeText(value: string | null | undefined): string {
  return (value ?? "")
    .replace(/\\n/g, "\n")
    .replace(/\r/g, "\n")
    .replace(/[ \t]+/g, " ")
    .replace(/\n{2,}/g, "\n")
    .trim();
}

function compactText(value: string, maxLength: number): string {
  const normalized = normalizeText(value).replace(/\n/g, " ");
  const chars = Array.from(normalized);
  if (chars.length <= maxLength) {
    return normalized;
  }
  return `${chars.slice(0, Math.max(0, maxLength - 1)).join("")}…`;
}

function makeSummary(row: RawAuditAgentPrompt): string {
  const intro = normalizeText(row.intro);
  if (intro) {
    return compactText(intro.split("\n").filter(Boolean).slice(0, 3).join("；"), 84);
  }
  return compactText(row.prompt ?? `${row.category}审计助手`, 84);
}

function makeStableKey(category: string, title: string): string {
  return `${normalizeText(category)}::${normalizeText(title)}`;
}

export const medicalAuditAgentCatalog: readonly ReferenceAgentCard[] = [
  {
    id: "agent-citation-check",
    name: "引用依据核验助手",
    category: "业务类",
    summary: "只基于命中的法规、目录、规则和风险清单回答；没有引用时输出待补证据。",
    project: "医保基金使用合规专项自查",
    topic: "医保基金使用合规",
    initial: "引",
    tone: "blue",
    prompt: "只基于命中的法规、目录、规则和风险清单回答；没有引用时输出待补证据。",
    sourceFile: "src/medical_audit_kb/api/agent_store.py",
    avatarSeed: "agent-citation-check",
    templateKey: "agent-citation-check@v1",
    catalogScope: "medical-default"
  },
  {
    id: "agent-duplicate-charge",
    name: "重复收费复核助手",
    category: "业务类",
    summary: "围绕同就诊、同项目、同日期的重复收费线索，列出应核验的执行记录、数量和例外情形。",
    project: "医保基金使用合规专项自查",
    topic: "收费明细复核",
    initial: "重",
    tone: "cyan",
    prompt: "围绕同就诊、同项目、同日期的重复收费线索，列出应核验的执行记录、数量和例外情形。",
    sourceFile: "src/medical_audit_kb/api/agent_store.py",
    avatarSeed: "agent-duplicate-charge",
    templateKey: "agent-duplicate-charge@v1",
    catalogScope: "medical-default"
  },
  {
    id: "agent-report-draft",
    name: "底稿摘要助手",
    category: "效率类",
    summary: "把已复核的引用、疑点和附件清单整理为底稿摘要，保留待人工确认标记。",
    project: "医保基金使用合规专项自查",
    topic: "审计底稿",
    initial: "底",
    tone: "slate",
    prompt: "把已复核的引用、疑点和附件清单整理为底稿摘要，保留待人工确认标记。",
    sourceFile: "src/medical_audit_kb/api/agent_store.py",
    avatarSeed: "agent-report-draft",
    templateKey: "agent-report-draft@v1",
    catalogScope: "medical-default"
  }
];

export const auditExtensionValidationCatalog: readonly ReferenceAgentCard[] = (() => {
  const selectedRows = new Map<string, { readonly index: number; readonly row: RawAuditAgentPrompt }>();
  for (const [index, row] of (rawAgentPrompts as readonly RawAuditAgentPrompt[]).entries()) {
    const key = makeStableKey(row.category, row.title);
    if (!selectedRows.has(key)) {
      selectedRows.set(key, { index, row });
    }
  }

  return EXTENSION_VALIDATION_KEYS.flatMap(([category, title], keyIndex) => {
    const selected = selectedRows.get(makeStableKey(category, title));
    if (!selected) {
      return [];
    }
    const normalizedTitle = normalizeText(selected.row.title);
    const templateKey = `audit-agent-prompts-0613-${String(selected.index + 1).padStart(3, "0")}`;
    return [{
      id: templateKey,
      name: normalizedTitle,
      category: normalizeText(selected.row.category),
      summary: makeSummary(selected.row),
      project: "智能体广场",
      topic: normalizeText(selected.row.scene) || normalizeText(selected.row.category),
      initial: Array.from(normalizedTitle)[0] ?? "审",
      tone: extensionAgentTones[keyIndex],
      prompt: normalizeText(selected.row.prompt),
      sourceFile: normalizeText(selected.row.source),
      avatarSeed: `${selected.row.category}-${selected.row.title}`,
      templateKey,
      catalogScope: "extension-validation" as const
    }];
  });
})();

const agentMarketCatalogWithExtension: readonly ReferenceAgentCard[] = [
  ...medicalAuditAgentCatalog,
  ...auditExtensionValidationCatalog
];

export function isAuditExtensionValidationPackEnabled(): boolean {
  return process.env.NEXT_PUBLIC_MEDICAL_AUDIT_AGENT_EXTENSION_PACK === "1";
}

export function getAuditAgentMarketCatalog(): readonly ReferenceAgentCard[] {
  return isAuditExtensionValidationPackEnabled()
    ? agentMarketCatalogWithExtension
    : medicalAuditAgentCatalog;
}
