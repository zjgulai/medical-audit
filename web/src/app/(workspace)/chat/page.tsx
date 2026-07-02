"use client";

import { useEffect, useState } from "react";

import { StatusPill } from "@/components/ui/status-pill";
import { fetchAgents } from "@/lib/api-client";
import type { AuditAgentApiItem } from "@/lib/api-types";
import {
  defaultAuditAgents,
  documentCategoryStats,
  guidedCheckQuestions,
  type AuditAgent
} from "@/lib/portal-data";

const assistantNotes = ["先查依据", "人工复核", "避免身份信息"] as const;

export default function ChatPortalPage() {
  const [agents, setAgents] = useState<readonly AuditAgent[]>(defaultAuditAgents);
  const [agentStatus, setAgentStatus] = useState<"loading" | "ready" | "fallback">("loading");
  const [selectedAgentId, setSelectedAgentId] = useState(defaultAuditAgents[0].id);
  const activeAgent =
    agents.find((agent) => agent.id === selectedAgentId) ?? agents[0] ?? defaultAuditAgents[0];

  useEffect(() => {
    let isMounted = true;
    const requestedAgentId =
      typeof window === "undefined" ? null : new URLSearchParams(window.location.search).get("agent");

    fetchAgents()
      .then((response) => {
        if (!isMounted) {
          return;
        }
        const activeAgents = response.items
          .filter((agent) => agent.status === "active")
          .map(apiAgentToPortalAgent);
        if (activeAgents.length > 0) {
          setAgents(activeAgents);
          setSelectedAgentId(
            activeAgents.some((agent) => agent.id === requestedAgentId)
              ? String(requestedAgentId)
              : activeAgents[0].id
          );
        } else if (requestedAgentId && defaultAuditAgents.some((agent) => agent.id === requestedAgentId)) {
          setSelectedAgentId(requestedAgentId);
        }
        setAgentStatus(response.store.ready ? "ready" : "fallback");
      })
      .catch(() => {
        if (!isMounted) {
          return;
        }
        if (requestedAgentId && defaultAuditAgents.some((agent) => agent.id === requestedAgentId)) {
          setSelectedAgentId(requestedAgentId);
        }
        setAgentStatus("fallback");
      });

    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <main className="audit-workbench-main mx-auto grid gap-4">
      <section className="audit-panel min-w-0 p-5 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="audit-kicker">审计助手</p>
            <h1 className="audit-page-title">AI 问答</h1>
            <p className="audit-copy mt-2 max-w-2xl">选择助手并提交问题，回答用于审计复核。</p>
          </div>
          <div className="flex flex-wrap gap-1.5">
            <StatusPill tone={agentStatus === "ready" ? "success" : "neutral"}>
              {agentStatus === "ready" ? "已同步" : agentStatus === "loading" ? "同步中" : "默认"}
            </StatusPill>
          </div>
        </div>

        <section className="mt-4 rounded-[var(--audit-radius-md)] border border-[var(--audit-primary-line)] bg-[var(--audit-primary-soft)] p-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="text-xs font-semibold text-[var(--audit-primary)]">当前助手</p>
              <h2 className="mt-1 truncate text-base font-semibold text-[var(--audit-ink)]">{activeAgent.name}</h2>
            </div>
            <details className="shrink-0">
              <summary className="audit-focus-ring cursor-pointer list-none rounded-full border border-[var(--audit-primary-line)] bg-white px-3 py-1 text-xs font-semibold text-[var(--audit-primary)] [&::-webkit-details-marker]:hidden">
                方法
              </summary>
              <p className="audit-copy mt-3 max-w-3xl">{activeAgent.prompt}</p>
            </details>
          </div>
        </section>

        <form className="mt-5 grid gap-4" action="/chat" method="get">
          <div className="grid gap-4 lg:grid-cols-[16rem_1fr]">
            <label className="block">
              <span className="audit-label">审计助手</span>
              <select
                className="audit-focus-ring audit-input mt-2 px-3 py-2.5"
                name="agent"
                value={activeAgent.id}
                onChange={(event) => setSelectedAgentId(event.target.value)}
              >
                {agents.map((agent) => (
                  <option key={agent.id} value={agent.id}>
                    {agent.name}
                  </option>
                ))}
              </select>
            </label>

            <label className="block">
              <span className="audit-label">审计问题</span>
              <input
                className="audit-focus-ring audit-input mt-2 px-3 py-2.5"
                name="question"
                autoComplete="off"
                placeholder="输入要核验的问题…"
                required
              />
            </label>
            <input type="hidden" name="project_name" value={activeAgent.projectName} />
          </div>

          <details className="rounded-[var(--audit-radius-md)] border border-[var(--audit-line-soft)] bg-[var(--audit-surface-muted)] p-3">
            <summary className="audit-focus-ring cursor-pointer list-none text-sm font-semibold text-[var(--audit-ink)] [&::-webkit-details-marker]:hidden">
              依据范围
              <span className="audit-meta ml-2">默认法规与目录</span>
            </summary>
            <fieldset className="mt-3">
              <legend className="sr-only">依据范围</legend>
              <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
                {documentCategoryStats.map((source) => (
                  <label
                    key={source.id}
                    className="flex items-center gap-2 rounded-[var(--audit-radius-sm)] border border-[var(--audit-line)] bg-white px-3 py-2 text-sm"
                  >
                    <input
                      className="size-4"
                      type="checkbox"
                      name="source_collection"
                      value={source.sourceCollection}
                      defaultChecked={source.id === "doc-cat-laws" || source.id === "doc-cat-catalog"}
                    />
                    <span className="min-w-0 flex-1 truncate font-semibold text-[var(--audit-ink)]">{source.name}</span>
                    <span className="audit-meta shrink-0">{source.documentCount}</span>
                  </label>
                ))}
              </div>
            </fieldset>
          </details>

          <div className="flex flex-wrap items-center gap-3">
            <button className="audit-focus-ring audit-btn audit-btn-primary" type="submit">
              进入对话
            </button>
            <a className="audit-focus-ring audit-btn audit-btn-neutral" href="/documents">
              先检索文档
            </a>
          </div>
        </form>

        <section className="mt-5" aria-labelledby="quick-question-title">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 id="quick-question-title" className="audit-section-title">常用问题</h2>
            <a className="audit-focus-ring rounded-[var(--audit-radius-sm)] px-2 py-1 text-xs font-semibold text-[var(--audit-primary)] hover:bg-[var(--audit-primary-soft)]" href="/agent-market">
              查看助手库
            </a>
          </div>
          <div className="mt-3 grid gap-2 lg:grid-cols-3">
            {guidedCheckQuestions.slice(0, 3).map((item) => (
              <a key={item.id} className="audit-focus-ring audit-action-card min-w-0 overflow-hidden px-3 py-2" href={item.chatHref}>
                <span className="block truncate text-sm font-semibold text-[var(--audit-ink)]">{item.question}</span>
              </a>
            ))}
          </div>
        </section>
      </section>

      <details className="audit-panel-rail p-4">
        <summary className="audit-focus-ring cursor-pointer list-none text-sm font-semibold text-[var(--audit-ink)] [&::-webkit-details-marker]:hidden">
          更多
        </summary>
        <div className="mt-3 flex flex-wrap gap-2">
          {assistantNotes.map((note) => (
            <span key={note} className="audit-chip">
              {note}
            </span>
          ))}
        </div>
        <div className="mt-4 grid gap-3 lg:grid-cols-3">
          {agents.slice(0, 6).map((agent) => (
            <AgentCard key={agent.id} agent={agent} />
          ))}
        </div>
      </details>
    </main>
  );
}

function apiAgentToPortalAgent(agent: AuditAgentApiItem): AuditAgent {
  return {
    id: agent.id,
    name: agent.name,
    category: agent.category,
    topic: agent.topic,
    prompt: agent.prompt,
    knowledgeBase: agent.knowledge_base,
    projectName: agent.project_name,
    updatedAt: formatAgentUpdatedAt(agent.updated_at),
    status: agent.status,
    promptVersion: agent.prompt_version,
    promptVersionKey: agent.prompt_version_key,
    visibilityScope: agent.visibility_scope,
    allowedRoles: agent.allowed_roles
  };
}

function formatAgentUpdatedAt(value: string): string {
  if (/^\d{4}-\d{2}-\d{2}T/.test(value)) {
    return value.slice(0, 10);
  }
  return value;
}

function AgentCard({ agent }: { readonly agent: AuditAgent }) {
  return (
    <article className="audit-panel-muted p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="audit-card-title">{agent.name}</h3>
        </div>
        <StatusPill tone={agent.category === "业务类" ? "success" : "neutral"}>{agent.category}</StatusPill>
      </div>
      <a
        className="audit-focus-ring audit-btn audit-btn-secondary mt-3 min-h-8 px-3 py-1.5 text-xs"
        href={`/chat?agent=${encodeURIComponent(agent.id)}&project_name=${encodeURIComponent(agent.projectName)}`}
      >
        提问
      </a>
    </article>
  );
}
