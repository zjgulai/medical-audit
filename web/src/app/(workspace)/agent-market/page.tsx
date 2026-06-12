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
    <main className="rounded-2xl border border-slate-200 bg-white p-6 shadow-[var(--audit-shadow-card)]">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-blue-700">智能体广场</p>
          <h1 className="mt-2 text-3xl font-semibold text-slate-950">医疗审计场景模板</h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">
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
              className={`audit-focus-ring rounded-xl border px-3 py-2 text-sm font-semibold ${
                activeFilter === filter
                  ? "border-blue-200 bg-blue-600 text-white"
                  : "border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100"
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
            className="audit-focus-ring w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索模板、专题、知识库"
            aria-label="搜索智能体模板"
          />
        </label>
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-3">
        {filteredTemplates.map((template) => (
          <article key={template.id} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-base font-semibold text-slate-950">{template.name}</h2>
                <p className="mt-1 text-xs text-slate-500">{template.topic}</p>
              </div>
              <StatusPill tone={template.category === "业务类" ? "success" : "neutral"}>{template.category}</StatusPill>
            </div>
            <p className="mt-4 text-sm leading-6 text-slate-700">{template.prompt}</p>
            <div className="mt-4 flex flex-wrap gap-2 text-xs text-slate-500">
              <span>{template.knowledgeBase}</span>
              <span>{template.projectName}</span>
            </div>
            <a
              className="audit-focus-ring mt-4 inline-flex rounded-xl bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700"
              href={`/agents?template=${template.id}`}
            >
              添加到我的智能体
            </a>
          </article>
        ))}
      </div>
      {filteredTemplates.length === 0 && (
        <p className="mt-6 rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-center text-sm text-slate-500">
          没有匹配的医疗审计智能体模板。
        </p>
      )}
    </main>
  );
}
