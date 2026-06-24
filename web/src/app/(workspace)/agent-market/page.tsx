"use client";

import { useEffect, useState } from "react";

import { fetchAgents } from "@/lib/api-client";
import { DataSourceBadge } from "@/components/ui/data-source-badge";
import { StatusPill } from "@/components/ui/status-pill";
import type { AuditAgentApiItem } from "@/lib/api-types";
import { AgentCategory, auditAgentTemplates } from "@/lib/portal-data";

type MarketFilter = "全部" | AgentCategory;
type LoadStatus = "loading" | "ready" | "error";

const marketFilters: readonly MarketFilter[] = ["全部", "业务类", "效率类", "研究类"];

export default function AgentMarketPage() {
  const [activeFilter, setActiveFilter] = useState<MarketFilter>("全部");
  const [query, setQuery] = useState("");
  const [agents, setAgents] = useState<readonly AuditAgentApiItem[]>([]);
  const [agentStatus, setAgentStatus] = useState<LoadStatus>("loading");
  const [storeReady, setStoreReady] = useState(false);

  useEffect(() => {
    let cancelled = false;

    fetchAgents()
      .then((result) => {
        if (cancelled) {
          return;
        }
        setAgents(result.items ?? []);
        setStoreReady(Boolean(result.store?.ready));
        setAgentStatus("ready");
      })
      .catch(() => {
        if (!cancelled) {
          setAgentStatus("error");
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const systemAgents = agents.filter((agent) => agent.source === "system-default");

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
            上方为后端已发布的系统智能体（实时），下方为可套用的示例模板；添加后仍按提示词型智能体使用，不执行多步自主编排。
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <StatusPill tone="info">提示词型</StatusPill>
          <StatusPill tone="neutral">保存后生效</StatusPill>
          <DataSourceBadge source="hybrid" />
        </div>
      </div>

      <section className="audit-panel-muted mt-6 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="audit-section-title">系统已发布智能体（实时）</h2>
          <StatusPill tone={agentStatus === "error" ? "warning" : "neutral"}>
            {agentStatus === "ready"
              ? `${systemAgents.length} 个系统智能体${storeReady ? "" : "（store 未就绪）"}`
              : agentStatus === "error"
                ? "加载失败"
                : "加载中"}
          </StatusPill>
        </div>
        <div className="mt-4 grid gap-4 lg:grid-cols-3">
          {agentStatus === "loading" && <p className="audit-copy">正在从后端读取系统智能体…</p>}
          {agentStatus === "error" && (
            <p className="audit-copy text-amber-700">系统智能体读取失败，可先使用下方示例模板，稍后刷新。</p>
          )}
          {agentStatus === "ready" && systemAgents.length === 0 && (
            <p className="audit-copy">后端暂无系统智能体，可从下方示例模板套用新增。</p>
          )}
          {systemAgents.map((agent) => (
            <article key={agent.id} className="audit-panel min-w-0 p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="audit-card-title">{agent.name}</h3>
                  <p className="mt-1 audit-meta">{agent.topic}</p>
                </div>
                <StatusPill tone="success">系统</StatusPill>
              </div>
              <p className="mt-4 audit-copy">{agent.prompt}</p>
              <div className="mt-4 flex flex-wrap gap-2">
                <span className="audit-chip">{agent.knowledge_base}</span>
                <span className="audit-chip">{agent.project_name}</span>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="audit-panel-muted mt-6 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="audit-section-title">示例模板（套用入口）</h2>
          <DataSourceBadge source="static" />
        </div>

        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
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
            <article key={template.id} className="audit-panel p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="audit-card-title">{template.name}</h3>
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
                href={`/agents?template=${template.id}#new-agent`}
              >
                套用并新增智能体
              </a>
            </article>
          ))}
        </div>
        {filteredTemplates.length === 0 && (
          <p className="audit-panel mt-6 border-dashed px-4 py-6 text-center audit-copy">
            没有匹配的医疗审计智能体模板。
          </p>
        )}
      </section>
    </main>
  );
}
