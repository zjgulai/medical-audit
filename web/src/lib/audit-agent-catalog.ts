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

const agentTones: readonly ReferenceAgentCard["tone"][] = ["blue", "cyan", "rose", "amber", "slate"];

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

function makeAgentName(title: string, category: string): string {
  const candidates = [
    title,
    title.replace(/^违反/, "").replace(/^违规/, ""),
    title.replace(/相关规定/g, "").replace(/有关规定/g, ""),
    title
      .replace(/^违反/, "")
      .replace(/^违规/, "")
      .replace(/相关规定/g, "")
      .replace(/有关规定/g, "")
      .replace(/符合性审计/g, "符合")
      .replace(/审计程序/g, "")
      .replace(/审计/g, "")
  ];
  let fallback = "";

  for (const candidate of candidates) {
    const base = normalizeText(candidate)
      .replace(/[“”"《》【】（）()]/g, "")
      .replace(/^\d+[、.)．]\s*/g, "")
      .replace(/管理管理/g, "管理")
      .trim();
    const clipped = base.replace(/[，,、。；;：:].*$/g, "").trim();
    const normalized = Array.from(clipped).length >= 5
      ? clipped
      : base.replace(/[，,、。；;：:]/g, "").trim();
    const chars = Array.from(normalized);
    if (chars.length >= 5 && chars.length <= 10) {
      return normalized;
    }
    if (chars.length > 10 && !fallback) {
      fallback = chars.slice(0, 10).join("");
    }
  }

  const categoryFallback = `${category.replace(/审计/g, "")}核验`;
  return fallback || (Array.from(categoryFallback).length >= 5 ? categoryFallback : `${categoryFallback}助手`);
}

function makeInitial(name: string): string {
  const chars = Array.from(name.trim());
  if (chars.length === 0) {
    return "审";
  }
  return chars.slice(0, 1).join("");
}

function makeSummary(row: RawAuditAgentPrompt): string {
  const intro = normalizeText(row.intro);
  if (intro) {
    return compactText(intro.split("\n").filter(Boolean).slice(0, 3).join("；"), 84);
  }
  return compactText(row.prompt ?? `${row.category}审计助手`, 84);
}

function makeStableKey(row: RawAuditAgentPrompt): string {
  return `${normalizeText(row.category)}::${normalizeText(row.title)}`;
}

function makeUniqueAgentName(
  name: string,
  row: RawAuditAgentPrompt,
  usedNames: Map<string, number>
): string {
  const count = usedNames.get(name) ?? 0;
  if (count === 0) {
    usedNames.set(name, 1);
    return name;
  }

  const suffixSeed = Array.from(normalizeText(row.title).replace(/[^\p{Script=Han}A-Za-z0-9]/gu, "")).slice(-2).join("");
  let suffix = suffixSeed || String(count + 1);
  let candidate = "";
  let nextCount = count + 1;

  do {
    const baseLength = Math.max(5, 10 - Array.from(suffix).length);
    candidate = `${Array.from(name).slice(0, baseLength).join("")}${suffix}`;
    if (!usedNames.has(candidate)) {
      usedNames.set(name, nextCount);
      usedNames.set(candidate, 1);
      return candidate;
    }
    nextCount += 1;
    suffix = String(nextCount);
  } while (nextCount < 100);

  usedNames.set(name, nextCount);
  return `${Array.from(name).slice(0, 8).join("")}${nextCount}`;
}

export const auditAgentCatalog: readonly ReferenceAgentCard[] = (() => {
  const seen = new Set<string>();
  const usedNames = new Map<string, number>();
  return (rawAgentPrompts as readonly RawAuditAgentPrompt[]).flatMap((row, index) => {
    const key = makeStableKey(row);
    if (seen.has(key)) {
      return [];
    }
    seen.add(key);

    const name = makeUniqueAgentName(makeAgentName(row.title, row.category), row, usedNames);
    const templateKey = `audit-agent-prompts-0613-${String(index + 1).padStart(3, "0")}`;
    return [{
      id: templateKey,
      name,
      category: normalizeText(row.category) || "其他分类",
      summary: makeSummary(row),
      project: "智能体广场",
      topic: normalizeText(row.category),
      initial: makeInitial(name),
      tone: agentTones[index % agentTones.length],
      prompt: normalizeText(row.prompt),
      sourceFile: normalizeText(row.source),
      avatarSeed: `${row.category}-${row.title}`,
      templateKey
    }];
  });
})();
