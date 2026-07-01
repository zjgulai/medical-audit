"use client";

import { useMemo, useState } from "react";

import promptsData from "@/data/audit-agent-prompts.json";

type AgentPrompt = {
  readonly category: string;
  readonly title: string;
  readonly intro: string;
  readonly scene: string;
  readonly tags: string;
  readonly prompt: string;
  readonly source: string;
};

type PromptSection = {
  readonly title: string;
  readonly lines: readonly string[];
};

type AgentCard = {
  readonly source: AgentPrompt;
  readonly displayName: string;
  readonly summary: string;
  readonly sections: readonly PromptSection[];
  readonly tags: readonly string[];
};

const auditAgents: readonly AgentPrompt[] = (() => {
  const seen = new Set<string>();
  return (promptsData as readonly AgentPrompt[]).filter((agent) => {
    const key = `${agent.category}|${agent.title}`;
    if (seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
})();

const CATEGORY_ORDER = [
  "财务收支审计",
  "工程审计",
  "采购招标审计",
  "审计科研",
  "固定资产审计",
  "工具智能体"
] as const;

const DISPLAY_NAME_RULES: readonly [RegExp, string][] = [
  [/出国|境外|因公出国/, "出国差旅核验"],
  [/会议.*(超标准|超预算|超人数|超天数)|超标准举办会议/, "会议超标核验"],
  [/未按规定举办会议|计划外举办会议|非定点场所|驻地外/, "会议合规核验"],
  [/会议费|会议/, "会议费用核验"],
  [/内控.*制度|管理制度/, "制度合规核验"],
  [/超编制|职数|领导干部配备/, "编制职数核验"],
  [/离职|退休|接受聘任|营利性活动/, "离退休从业核验"],
  [/经商|办企业|入股/, "违规经商核验"],
  [/三公/, "三公经费核验"],
  [/公务用车.*预算|公车.*预算/, "公车预算核验"],
  [/公务用车|公车/, "公务用车核验"],
  [/预算/, "预算执行核验"],
  [/采购|招标/, "采购招标核验"],
  [/固定资产|资产/, "资产盘点核验"],
  [/合同/, "合同风险核验"],
  [/工程/, "工程合规核验"],
  [/科研/, "科研经费核验"],
  [/政策|法规/, "政策口径核验"],
  [/票据|发票/, "票据凭证核验"],
  [/资金|收支/, "资金收支核验"]
];

const SECTION_LABELS = {
  focus: "关注问题",
  material: "需要材料",
  method: "核验步骤"
} as const;
const DEFAULT_AGENT_LIMIT = 12;

function normalizeVisibleText(text: string): string {
  return text
    .replace(/\\n/g, "\n")
    .replace(/\r/g, "")
    .replace(/```(?:json)?/g, "")
    .replace(/\*\*/g, "")
    .trim();
}

function cleanLine(text: string): string {
  return normalizeVisibleText(text)
    .replace(/^#{1,6}\s*/, "")
    .replace(/^[-*]\s*/, "")
    .replace(/^[\d一二三四五六七八九十]+[、.．]\s*/, "")
    .replace(/^[{[\]},]+|[{[\]},]+$/g, "")
    .replace(/^"?(filename|tablename|name|title)"?\s*[:：]\s*/i, "")
    .replace(/^"?(files|tables|num)"?\s*[:：]?\s*/i, "")
    .replace(/^【(.+)】$/, "$1")
    .replace(/^\[(.+)]$/, "$1")
    .replace(/^【[^】]+】\s*/, "")
    .replace(/^\[[^\]]+]\s*/, "")
    .replace(/\*\*/g, "")
    .replace(/\\"/g, "\"")
    .replace(/^["'`]+|["'`,]+$/g, "")
    .replace(/[，,]\s*$/g, "")
    .trim();
}

function isUsefulLine(text: string): boolean {
  return (
    text.length > 1 &&
    !/^[\d.]+$/.test(text) &&
    !/^[{}[\],:："'`]+$/.test(text) &&
    !/^(files|tables|num|filename|tablename)$/i.test(text)
  );
}

function firstLine(text: string): string {
  const line = normalizeVisibleText(text)
    .split(/\n|，|。/)
    .map((part) => cleanLine(part))
    .find((part) => isUsefulLine(part) && !sectionKindFromTitle(part));
  return line ?? cleanLine(text);
}

function enforceCardTitleLength(value: string): string {
  const base = value.replace(/[^\p{L}\p{N}]/gu, "");
  let chars = Array.from(base);
  while (chars.length < 5) {
    chars = Array.from(`${chars.join("")}核验`);
  }
  if (chars.length > 10) {
    chars = [...chars.slice(0, 8), "核", "验"];
  }
  return chars.slice(0, 10).join("");
}

function tagList(tags: string): readonly string[] {
  return normalizeVisibleText(tags)
    .split(/[、,，\s]+/)
    .map((tag) => tag.trim())
    .filter((tag) => tag.length > 0)
    .slice(0, 3);
}

function compactAgentTitle(agent: AgentPrompt): string {
  const rawTitle = cleanLine(agent.title);
  const matchedRule = DISPLAY_NAME_RULES.find(([pattern]) => pattern.test(rawTitle));
  if (matchedRule) {
    return enforceCardTitleLength(matchedRule[1]);
  }

  const normalized = cleanLine(agent.title)
    .replace(/违反/g, "")
    .replace(/相关规定/g, "")
    .replace(/符合性/g, "合规")
    .replace(/管理制度/g, "制度")
    .replace(/管理/g, "")
    .replace(/审计/g, "")
    .replace(/\s+/g, "");
  const source = normalized || cleanLine(agent.title) || agent.category.replace("审计", "");
  return enforceCardTitleLength(source);
}

function agentInitials(title: string): string {
  const compact = Array.from(title.replace(/[^\p{L}\p{N}]/gu, ""));
  return compact.slice(0, 2).join("") || "审计";
}

function agentHue(seed: string): number {
  let hash = 0;
  for (const char of seed) {
    hash = (hash * 31 + char.charCodeAt(0)) % 360;
  }
  return hash;
}

function sectionKindFromTitle(title: string): keyof typeof SECTION_LABELS | null {
  if (/表现形式|关注问题|风险表现|常见问题/.test(title)) {
    return "focus";
  }
  if (/所需数据|需要数据|材料|资料|文件|表格/.test(title)) {
    return "material";
  }
  if (/实施方法|审计方法|审计程序|分析步骤|核验步骤|工作建议/.test(title)) {
    return "method";
  }
  return null;
}

function promptHeadingKind(rawLine: string): keyof typeof SECTION_LABELS | null {
  const raw = normalizeVisibleText(rawLine).trim();
  const heading = raw.match(/^#{1,6}\s*(.+)$/);
  const bracketHeading = raw.match(/^【(.+)】$/) ?? raw.match(/^\[(.+)]$/);
  const cleaned = cleanLine(heading?.[1] ?? bracketHeading?.[1] ?? raw.replace(/[:：]\s*$/, ""));
  return sectionKindFromTitle(cleaned);
}

function promptSections(agent: AgentPrompt): readonly PromptSection[] {
  const grouped: Record<keyof typeof SECTION_LABELS, string[]> = {
    focus: [],
    material: [],
    method: []
  };
  let current: keyof typeof SECTION_LABELS = "focus";

  const intro = cleanLine(firstLine(agent.intro));
  if (isUsefulLine(intro)) {
    grouped.focus.push(intro);
  }

  for (const rawLine of normalizeVisibleText(agent.prompt).split("\n")) {
    const headingKind = promptHeadingKind(rawLine);
    if (headingKind) {
      current = headingKind;
      continue;
    }
    const line = cleanLine(rawLine);
    if (!isUsefulLine(line)) {
      continue;
    }
    grouped[current].push(line);
  }

  return (Object.keys(SECTION_LABELS) as Array<keyof typeof SECTION_LABELS>)
    .map((key) => ({
      title: SECTION_LABELS[key],
      lines: Array.from(new Set(grouped[key])).slice(0, 4)
    }))
    .filter((section) => section.lines.length > 0)
    .slice(0, 3);
}

function buildAgentCard(agent: AgentPrompt): AgentCard {
  return {
    source: agent,
    displayName: compactAgentTitle(agent),
    summary: cleanLine(firstLine(agent.intro)),
    sections: promptSections(agent),
    tags: tagList(agent.tags)
  };
}

export default function AgentMarketPage() {
  const [category, setCategory] = useState<string>("全部");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<AgentCard | null>(null);
  const agentCards = useMemo(() => auditAgents.map(buildAgentCard), []);

  const counts = useMemo(() => {
    const map: Record<string, number> = {};
    for (const agent of auditAgents) {
      map[agent.category] = (map[agent.category] ?? 0) + 1;
    }
    return map;
  }, []);

  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return agentCards.filter((agent) => {
      const matchesCategory = category === "全部" || agent.source.category === category;
      const matchesQuery =
        !normalized ||
        `${agent.displayName}${agent.source.title}${agent.summary}${agent.source.tags}${agent.source.scene}`
          .toLowerCase()
          .includes(normalized);
      return matchesCategory && matchesQuery;
    });
  }, [agentCards, category, query]);

  const visibleAgents = filtered.slice(0, DEFAULT_AGENT_LIMIT);

  return (
    <main className="space-y-4 sm:space-y-5">
      <section className="audit-panel p-4 sm:p-6">
        <div className="grid gap-3 sm:grid-cols-[1fr_minmax(16rem,20rem)] sm:items-end">
          <div>
            <p className="audit-kicker">智能体广场</p>
            <h1 className="audit-page-title">审计提示词智能体</h1>
            <p className="mt-1 audit-copy">默认展示常用助手，可搜索完整模板库。</p>
          </div>
          <input
            className="audit-focus-ring audit-input w-full px-3 py-2.5"
            placeholder="搜索助手 / 场景 / 标签"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            aria-label="搜索智能体"
          />
        </div>

        <div className="-mx-1 mt-3 flex gap-1.5 overflow-x-auto px-1 pb-1 sm:mx-0 sm:mt-4 sm:flex-wrap sm:gap-2 sm:overflow-visible sm:px-0 sm:pb-0" role="tablist" aria-label="智能体分类">
          <CategoryChip
            label="全部"
            count={auditAgents.length}
            active={category === "全部"}
            onClick={() => setCategory("全部")}
          />
          {CATEGORY_ORDER.map((name) => (
            <CategoryChip
              key={name}
              label={name.replace("审计", "")}
              count={counts[name] ?? 0}
              active={category === name}
              onClick={() => setCategory(name)}
            />
          ))}
        </div>
      </section>

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3" aria-label="智能体列表">
        {visibleAgents.map((agent) => (
          <button
            key={`${agent.source.category}-${agent.source.title}`}
            type="button"
            onClick={() => setSelected(agent)}
            className="audit-focus-ring audit-panel flex flex-col gap-2.5 p-4 text-left transition hover:border-[var(--audit-primary-line)]"
          >
            <div className="flex items-start gap-3">
              <AgentAvatar agent={agent} size="compact" />
              <h2 className="audit-card-title min-w-0 flex-1 leading-snug">{agent.displayName}</h2>
            </div>
            <p className="line-clamp-2 audit-copy text-[var(--audit-ink-muted)]">{agent.summary}</p>
            <div className="mt-auto flex items-center justify-between gap-2 pt-1">
              <span className="min-w-0 truncate rounded-full bg-[var(--audit-surface-subtle)] px-2 py-0.5 text-[11px] font-medium text-[var(--audit-primary)]">
                {agent.tags[0] ?? agent.source.category.replace("审计", "")}
              </span>
              <span className="shrink-0 text-xs font-semibold text-[var(--audit-primary)]">打开</span>
            </div>
          </button>
        ))}
        {filtered.length > visibleAgents.length ? (
          <p className="audit-panel-muted p-4 audit-copy sm:col-span-2 xl:col-span-3">
            已显示前 {visibleAgents.length} 个。输入关键词可继续缩小范围。
          </p>
        ) : null}
        {filtered.length === 0 ? (
          <p className="audit-panel-muted p-6 audit-copy sm:col-span-2 xl:col-span-3">
            没有匹配的智能体，换个关键词或分类试试。
          </p>
        ) : null}
      </section>

      {selected ? <AgentDetailDialog agent={selected} onClose={() => setSelected(null)} /> : null}
    </main>
  );
}

function CategoryChip({
  label,
  count,
  active,
  onClick
}: {
  readonly label: string;
  readonly count: number;
  readonly active: boolean;
  readonly onClick: () => void;
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={`audit-focus-ring shrink-0 rounded-full px-2.5 py-1.5 text-xs transition sm:px-3 sm:text-sm ${
        active
          ? "bg-[var(--audit-primary)] font-semibold text-white"
          : "border border-[var(--audit-line)] text-[var(--audit-ink-muted)] hover:bg-[var(--audit-surface-muted)]"
      }`}
    >
      {label}
      <span className={`ml-1.5 text-xs ${active ? "text-white/80" : "text-[var(--audit-ink-subtle)]"}`}>{count}</span>
    </button>
  );
}

function AgentDetailDialog({ agent, onClose }: { readonly agent: AgentCard; readonly onClose: () => void }) {
  const chatHref = `/chat?agent=${encodeURIComponent(agent.source.title)}`;
  const normalizedPrompt = normalizeVisibleText(agent.source.prompt);
  return (
    <div
      className="fixed inset-0 z-40 flex items-end justify-center bg-[rgb(16_24_40/0.45)] p-0 sm:items-center sm:p-6"
      role="dialog"
      aria-modal="true"
      aria-label={agent.displayName}
      onClick={onClose}
    >
      <div
        className="audit-panel max-h-[86vh] w-full max-w-2xl overflow-auto rounded-b-none p-6 sm:rounded-[var(--audit-radius-lg)]"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <AgentAvatar agent={agent} size="detail" />
            <div>
              <p className="audit-kicker">{agent.source.category.replace("审计", "")}</p>
              <h2 className="mt-1 audit-section-title">{agent.displayName}</h2>
              <p className="audit-meta mt-1">{cleanLine(agent.source.title)}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="audit-focus-ring rounded-[var(--audit-radius-sm)] px-2 py-1 text-lg text-[var(--audit-ink-muted)] hover:bg-[var(--audit-surface-muted)]"
            aria-label="关闭"
          >
            ✕
          </button>
        </div>

        {agent.source.scene ? (
          <p className="mt-3 inline-block rounded-full bg-[var(--audit-surface-subtle)] px-3 py-1 text-xs text-[var(--audit-ink-muted)]">
            适用：{agent.source.scene}
          </p>
        ) : null}

        <p className="mt-3 audit-copy">{agent.summary}</p>

        <div className="mt-4">
          <h3 className="audit-card-title">怎么使用</h3>
          <div className="mt-2 grid max-h-80 gap-3 overflow-auto pr-1">
            {agent.sections.map((section) => (
              <section
                key={section.title}
                className="rounded-[var(--audit-radius-md)] border border-[var(--audit-line-soft)] bg-[var(--audit-surface-muted)] p-3"
              >
                <h4 className="audit-compact-title">{section.title}</h4>
                <ul className="mt-2 space-y-1.5">
                  {section.lines.map((line) => (
                    <li key={line} className="audit-copy text-sm">
                      {line}
                    </li>
                  ))}
                </ul>
              </section>
            ))}
          </div>
        </div>

        <div className="mt-5 flex flex-wrap gap-3">
          <a className="audit-focus-ring audit-btn audit-btn-primary" href={chatHref}>
            用此智能体对话
          </a>
          <button
            type="button"
            className="audit-focus-ring audit-btn audit-btn-neutral"
            onClick={() => {
              void navigator.clipboard?.writeText(normalizedPrompt);
            }}
          >
            复制原始提示词
          </button>
        </div>
      </div>
    </div>
  );
}

function AgentAvatar({
  agent,
  size
}: {
  readonly agent: AgentCard;
  readonly size: "compact" | "detail";
}) {
  const hue = agentHue(`${agent.source.category}-${agent.source.title}`);
  const sizeClass = size === "detail" ? "size-11 text-sm" : "size-10 text-xs";
  return (
    <span
      aria-hidden="true"
      className={`grid shrink-0 place-items-center rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] font-semibold shadow-[0_8px_18px_rgb(35_45_84/0.06)] ${sizeClass}`}
      style={{
        background: `linear-gradient(135deg, hsl(${hue} 76% 95%), hsl(${(hue + 28) % 360} 68% 88%))`,
        color: `hsl(${hue} 70% 30%)`
      }}
    >
      {agentInitials(agent.displayName)}
    </span>
  );
}
