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
    .replace(/^【(.+)】$/, "$1")
    .replace(/^\[(.+)]$/, "$1")
    .replace(/^["'`]+|["'`]+$/g, "")
    .trim();
}

function firstLine(text: string): string {
  const line = normalizeVisibleText(text)
    .split(/\n|，|。/)
    .map((part) => part.trim())
    .find((part) => part.length > 0);
  return line ?? text.trim();
}

function tagList(tags: string): readonly string[] {
  return normalizeVisibleText(tags)
    .split(/[、,，\s]+/)
    .map((tag) => tag.trim())
    .filter((tag) => tag.length > 0)
    .slice(0, 3);
}

function compactAgentTitle(agent: AgentPrompt): string {
  const normalized = cleanLine(agent.title)
    .replace(/违反/g, "")
    .replace(/相关规定/g, "")
    .replace(/符合性/g, "合规")
    .replace(/管理制度/g, "制度")
    .replace(/管理/g, "")
    .replace(/审计/g, "")
    .replace(/\s+/g, "");
  const source = normalized || cleanLine(agent.title) || agent.category.replace("审计", "");
  const chars = Array.from(source);
  let title = chars.slice(0, 10).join("");
  while (Array.from(title).length < 5) {
    title += Array.from(title).length <= 3 ? "核验" : "助手";
  }
  return Array.from(title).slice(0, 10).join("");
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

function promptSections(prompt: string): readonly PromptSection[] {
  const sections: PromptSection[] = [];
  let current: { title: string; lines: string[] } = { title: "使用说明", lines: [] };

  for (const rawLine of normalizeVisibleText(prompt).split("\n")) {
    const line = cleanLine(rawLine);
    if (!line) {
      continue;
    }
    const heading = rawLine.match(/^#{1,6}\s*(.+)$/);
    const bracketHeading = line.match(/^【(.+)】$/) ?? line.match(/^\[(.+)]$/);
    if (heading || bracketHeading) {
      if (current.lines.length > 0 || sections.length === 0) {
        sections.push(current);
      }
      current = { title: cleanLine(heading?.[1] ?? bracketHeading?.[1] ?? line), lines: [] };
      continue;
    }
    current.lines.push(line);
  }

  if (current.lines.length > 0) {
    sections.push(current);
  }

  return sections
    .map((section) => ({
      title: section.title,
      lines: section.lines.slice(0, 7)
    }))
    .filter((section) => section.lines.length > 0)
    .slice(0, 5);
}

export default function AgentMarketPage() {
  const [category, setCategory] = useState<string>("全部");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<AgentPrompt | null>(null);

  const counts = useMemo(() => {
    const map: Record<string, number> = {};
    for (const agent of auditAgents) {
      map[agent.category] = (map[agent.category] ?? 0) + 1;
    }
    return map;
  }, []);

  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return auditAgents.filter((agent) => {
      const matchesCategory = category === "全部" || agent.category === category;
      const matchesQuery =
        !normalized ||
        `${agent.title}${agent.intro}${agent.tags}${agent.scene}`.toLowerCase().includes(normalized);
      return matchesCategory && matchesQuery;
    });
  }, [category, query]);

  return (
    <main className="space-y-5">
      <section className="audit-panel p-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="audit-kicker">智能体广场</p>
            <h1 className="audit-page-title">审计提示词智能体</h1>
            <p className="mt-2 audit-copy">{auditAgents.length} 个内置审计助手，选择后进入对话即用。</p>
          </div>
          <input
            className="audit-focus-ring audit-input w-full max-w-xs px-3 py-2.5"
            placeholder="搜索助手 / 场景 / 标签"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            aria-label="搜索智能体"
          />
        </div>

        <div className="mt-4 flex flex-wrap gap-2" role="tablist" aria-label="智能体分类">
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
        {filtered.map((agent) => (
          <button
            key={`${agent.category}-${agent.title}`}
            type="button"
            onClick={() => setSelected(agent)}
            className="audit-focus-ring audit-panel flex flex-col gap-3 p-4 text-left transition hover:border-[var(--audit-primary-line)]"
          >
            <div className="flex items-start gap-3">
              <AgentAvatar agent={agent} size="compact" />
              <h2 className="audit-card-title min-w-0 flex-1 leading-snug">{compactAgentTitle(agent)}</h2>
            </div>
            <p className="line-clamp-2 audit-copy text-[var(--audit-ink-muted)]">{firstLine(agent.intro)}</p>
            <div className="mt-auto flex items-center justify-between gap-2 pt-1">
              <div className="flex min-w-0 flex-wrap gap-1.5">
                {tagList(agent.tags).map((tag) => (
                  <span
                    key={tag}
                    className="rounded-full bg-[var(--audit-surface-subtle)] px-2 py-0.5 text-[11px] font-medium text-[var(--audit-primary)]"
                  >
                    {tag}
                  </span>
                ))}
              </div>
              <span className="shrink-0 text-xs font-semibold text-[var(--audit-primary)]">用 ›</span>
            </div>
          </button>
        ))}
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
      className={`audit-focus-ring rounded-full px-3 py-1.5 text-sm transition ${
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

function AgentDetailDialog({ agent, onClose }: { readonly agent: AgentPrompt; readonly onClose: () => void }) {
  const chatHref = `/chat?agent=${encodeURIComponent(agent.title)}`;
  const displayTitle = compactAgentTitle(agent);
  const sections = promptSections(agent.prompt);
  const normalizedPrompt = normalizeVisibleText(agent.prompt);
  return (
    <div
      className="fixed inset-0 z-40 flex items-end justify-center bg-[rgb(16_24_40/0.45)] p-0 sm:items-center sm:p-6"
      role="dialog"
      aria-modal="true"
      aria-label={displayTitle}
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
              <p className="audit-kicker">{agent.category.replace("审计", "")}</p>
              <h2 className="mt-1 audit-section-title">{displayTitle}</h2>
              <p className="audit-meta mt-1">原始名称：{cleanLine(agent.title)}</p>
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

        {agent.scene ? (
          <p className="mt-3 inline-block rounded-full bg-[var(--audit-surface-subtle)] px-3 py-1 text-xs text-[var(--audit-ink-muted)]">
            适用：{agent.scene}
          </p>
        ) : null}

        <p className="mt-3 audit-copy">{firstLine(agent.intro)}</p>

        <div className="mt-4">
          <h3 className="audit-card-title">提示词结构</h3>
          <div className="mt-2 grid max-h-80 gap-3 overflow-auto pr-1">
            {sections.map((section) => (
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
            复制提示词
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
  readonly agent: AgentPrompt;
  readonly size: "compact" | "detail";
}) {
  const displayTitle = compactAgentTitle(agent);
  const hue = agentHue(`${agent.category}-${agent.title}`);
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
      {agentInitials(displayTitle)}
    </span>
  );
}
