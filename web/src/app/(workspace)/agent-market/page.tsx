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

function firstLine(text: string): string {
  const line = text
    .split(/\n|，|。/)
    .map((part) => part.trim())
    .find((part) => part.length > 0);
  return line ?? text.trim();
}

function tagList(tags: string): readonly string[] {
  return tags
    .split(/[、,，\s]+/)
    .map((tag) => tag.trim())
    .filter((tag) => tag.length > 0)
    .slice(0, 3);
}

function avatarUrl(seed: string): string {
  return `https://api.dicebear.com/9.x/notionists/svg?seed=${encodeURIComponent(seed)}&radius=14&backgroundColor=eef2f5,e1f5ee,faeeda,fcebeb`;
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
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={avatarUrl(agent.title)}
                alt=""
                width={40}
                height={40}
                loading="lazy"
                className="size-10 shrink-0 rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-[var(--audit-surface-subtle)]"
              />
              <h2 className="audit-card-title min-w-0 flex-1 leading-snug">{agent.title}</h2>
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
  return (
    <div
      className="fixed inset-0 z-40 flex items-end justify-center bg-[rgb(16_24_40/0.45)] p-0 sm:items-center sm:p-6"
      role="dialog"
      aria-modal="true"
      aria-label={agent.title}
      onClick={onClose}
    >
      <div
        className="audit-panel max-h-[86vh] w-full max-w-2xl overflow-auto rounded-b-none p-6 sm:rounded-[var(--audit-radius-lg)]"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={avatarUrl(agent.title)}
              alt=""
              width={44}
              height={44}
              className="size-11 shrink-0 rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-[var(--audit-surface-subtle)]"
            />
            <div>
              <p className="audit-kicker">{agent.category.replace("审计", "")}</p>
              <h2 className="mt-1 audit-section-title">{agent.title}</h2>
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

        <p className="mt-3 whitespace-pre-line audit-copy">{agent.intro}</p>

        <div className="mt-4">
          <h3 className="audit-card-title">提示词</h3>
          <pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap break-words rounded-[var(--audit-radius-md)] bg-[var(--audit-surface-muted)] p-3 font-mono text-xs leading-5 text-[var(--audit-ink-muted)]">
            {agent.prompt}
          </pre>
        </div>

        <div className="mt-5 flex flex-wrap gap-3">
          <a className="audit-focus-ring audit-btn audit-btn-primary" href={chatHref}>
            用此智能体对话
          </a>
          <button
            type="button"
            className="audit-focus-ring audit-btn audit-btn-neutral"
            onClick={() => {
              void navigator.clipboard?.writeText(agent.prompt);
            }}
          >
            复制提示词
          </button>
        </div>
      </div>
    </div>
  );
}
