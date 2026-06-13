"use client";

import { useState } from "react";

import { StatusPill } from "@/components/ui/status-pill";
import { AgentCategory, auditAgentTemplates } from "@/lib/portal-data";

type MarketFilter = "全部" | AgentCategory;

const marketFilters: readonly MarketFilter[] = ["全部", "业务类", "效率类", "研究类"];

export default function AgentMarketPage() {
  const [activeFilter, setActiveFilter] = useState<MarketFilter>("全部");
  const [query, setQuery] = useState("");
  const normalizedQuery = query.trim().toLowerCase();
  const filteredTemplates = auditAgentTemplates.filter((template) => {
    const matchesFilter = activeFilter === "全部" || template.category === activeFilter;
    const matchesQuery =
      !normalizedQuery ||
      [template.name, template.topic, template.prompt, template.knowledgeBase, template.projectName].some((value) =>
        value.toLowerCase().includes(normalizedQuery)
      );

    return matchesFilter && matchesQuery;
  });

  return (
    <main className="audit-panel p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="audit-kicker">智能体广场</p>
          <h1 className="audit-page-title">医疗审计场景模板</h1>
          <p className="mt-3 max-w-3xl audit-copy">
            模板仅覆盖医疗/医保审计首期场景，添加后仍按提示词型智能体使用，不执行多步自主编排。
          </p>
        </div>
        <StatusPill tone="info">模板</StatusPill>
      </div>

      <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2" role="group" aria-label="智能体分类筛选">
          {marketFilters.map((filter) => (
            <button
              key={filter}
              className={`audit-focus-ring audit-btn ${
                activeFilter === filter
                  ? "border-[var(--audit-primary)] bg-[var(--audit-primary)] text-white"
                  : "audit-btn-neutral"
              }`}
              type="button"
              onClick={() => setActiveFilter(filter)}
              aria-pressed={activeFilter === filter}
            >
              {filter}
            </button>
          ))}
        </div>
        <label className="block min-w-72">
          <span className="sr-only">搜索智能体模板</span>
          <input
            className="audit-focus-ring audit-input px-3 py-2"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索模板、专题、知识库"
            aria-label="搜索智能体模板"
          />
        </label>
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-3">
        {filteredTemplates.map((template) => (
          <article key={template.id} className="audit-panel-muted p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="audit-card-title">{template.name}</h2>
                <p className="mt-1 audit-meta">{template.topic}</p>
              </div>
              <StatusPill tone={template.category === "业务类" ? "success" : "neutral"}>{template.category}</StatusPill>
            </div>
            <p className="mt-4 audit-copy">{template.prompt}</p>
            <div className="mt-4 flex flex-wrap gap-2">
              <span className="audit-chip">{template.knowledgeBase}</span>
              <span className="audit-chip">{template.projectName}</span>
            </div>
            <a
              className="audit-focus-ring audit-btn audit-btn-primary mt-4"
              href={`/agents?template=${template.id}`}
            >
              添加到我的智能体
            </a>
          </article>
        ))}
      </div>
      {filteredTemplates.length === 0 && (
        <p className="audit-panel-muted mt-6 border-dashed px-4 py-6 text-center audit-copy">
          没有匹配的医疗审计智能体模板。
        </p>
      )}
    </main>
  );
}
