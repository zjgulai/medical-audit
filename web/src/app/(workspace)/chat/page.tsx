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

const questionBuilderSteps = [
  {
    label: "选择助手",
    detail: "按医保基金、收费明细、目录限制或底稿生成选择核验方法。"
  },
  {
    label: "限定依据范围",
    detail: "只在法规政策、监管两库、医保目录和风险清单内组织引用。"
  },
  {
    label: "提交审计问题",
    detail: "进入后端审证深页，输出带引用和原文入口的回答。"
  }
] as const;

const evidenceRules = [
  "没有引用依据时，只输出待补证据状态。",
  "回答进入底稿前，必须打开原文核验适用条件。",
  "不要输入患者姓名、证件号、手机号等直接身份标识。"
] as const;

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
            <h1 className="audit-page-title">审计问答</h1>
            <p className="audit-copy mt-2 max-w-2xl">围绕医保基金审计问题发起核验，回答进入底稿前仍需人工复核。</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <StatusPill tone="success">依据优先</StatusPill>
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
              <p className="audit-meta mt-1 truncate">{activeAgent.topic}</p>
            </div>
            <details className="shrink-0">
              <summary className="audit-focus-ring cursor-pointer list-none rounded-full border border-[var(--audit-primary-line)] bg-white px-3 py-1 text-xs font-semibold text-[var(--audit-primary)] [&::-webkit-details-marker]:hidden">
                查看核验方法
              </summary>
              <p className="audit-copy mt-3 max-w-3xl">{activeAgent.prompt}</p>
            </details>
          </div>
        </section>

        <form className="mt-5 grid gap-4" action="/pages/chat" method="get">
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

          <fieldset>
            <legend className="audit-label">依据范围</legend>
            <div className="mt-2 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
              {documentCategoryStats.map((source) => (
                <label
                  key={source.id}
                  className="flex items-center gap-2 rounded-[var(--audit-radius-sm)] border border-[var(--audit-line)] bg-[var(--audit-surface-muted)] px-3 py-2 text-sm"
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
            <h2 id="quick-question-title" className="audit-section-title">快速问题</h2>
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
          使用说明与证据边界
        </summary>
        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          <ol className="space-y-2">
            {questionBuilderSteps.map((step, index) => (
              <li key={step.label} className="rounded-[var(--audit-radius-sm)] border border-[var(--audit-line-soft)] bg-white p-3">
                <span className="audit-meta">步骤 {index + 1}</span>
                <h3 className="mt-1 text-sm font-semibold text-[var(--audit-ink)]">{step.label}</h3>
                <p className="audit-copy mt-1">{step.detail}</p>
              </li>
            ))}
          </ol>
          <ul className="space-y-2">
            {evidenceRules.map((rule) => (
              <li key={rule} className="audit-panel-muted px-3 py-2 audit-copy">
                {rule}
              </li>
            ))}
          </ul>
        </div>
      </details>

      <details className="audit-panel-rail p-4">
        <summary className="audit-focus-ring cursor-pointer list-none text-sm font-semibold text-[var(--audit-ink)] [&::-webkit-details-marker]:hidden">
          可用助手
        </summary>
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
    <article className="audit-panel-muted p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="audit-card-title">{agent.name}</h3>
          <p className="mt-1 audit-meta">{agent.topic}</p>
        </div>
        <StatusPill tone={agent.category === "业务类" ? "success" : "neutral"}>{agent.category}</StatusPill>
      </div>
      <p className="mt-4 audit-copy">{agent.prompt}</p>
      <a
        className="audit-focus-ring audit-btn audit-btn-secondary mt-4 min-h-8 px-3 py-1.5 text-xs"
        href={`/pages/chat?agent=${encodeURIComponent(agent.id)}&project_name=${encodeURIComponent(agent.projectName)}`}
      >
        用此助手提问
      </a>
    </article>
  );
}
