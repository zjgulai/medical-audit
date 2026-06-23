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
    label: "选择智能体",
    detail: "按医保基金、收费明细、目录限制或底稿生成选择提示词模板。"
  },
  {
    label: "限定知识来源",
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
    <main className="grid min-w-0 items-start gap-4 xl:grid-cols-[18rem_minmax(0,1fr)_18rem]">
      <aside className="audit-panel-rail min-w-0 p-5">
        <h2 className="audit-section-title">问题构建</h2>
        <p className="audit-copy mt-2">把审计问题先限定在专题、智能体和知识来源内，再进入审证深页。</p>
        <ol className="mt-5 space-y-3">
          {questionBuilderSteps.map((step, index) => (
            <li key={step.label} className="rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-white p-3">
              <span className="grid size-7 place-items-center rounded-[var(--audit-radius-md)] bg-[var(--audit-primary)] text-xs font-semibold text-white">
                {index + 1}
              </span>
              <h3 className="mt-3 text-sm font-semibold text-[var(--audit-ink)]">{step.label}</h3>
              <p className="audit-copy mt-2">{step.detail}</p>
            </li>
          ))}
        </ol>

        <section className="mt-5" aria-labelledby="chat-source-title">
          <h2 id="chat-source-title" className="audit-section-title">知识来源</h2>
          <div className="mt-3 space-y-2">
            {documentCategoryStats.map((source) => (
              <div key={source.id} className="rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-white p-3">
                <div className="flex items-start justify-between gap-3">
                  <p className="text-sm font-semibold text-[var(--audit-ink)]">{source.name}</p>
                  <span className="audit-meta">{source.documentCount} 份</span>
                </div>
                <p className="audit-meta mt-1">{source.sourceCollection}</p>
              </div>
            ))}
          </div>
        </section>
      </aside>

      <section className="audit-panel min-w-0 p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="audit-kicker">AI 对话</p>
            <h1 className="audit-page-title">AI 审证对话工作台</h1>
            <p className="audit-copy mt-2 max-w-3xl">
              面向医保基金审计的问题入口。页面负责选择智能体、限定知识来源和组织问题，引用生成和原文预览仍由后端审证深页执行。
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <StatusPill tone="success">引用优先</StatusPill>
            <StatusPill tone={agentStatus === "ready" ? "success" : "neutral"}>
              {agentStatus === "ready" ? "智能体已同步" : agentStatus === "loading" ? "智能体同步中" : "默认智能体"}
            </StatusPill>
          </div>
        </div>

        <section className="mt-6 rounded-[var(--audit-radius-md)] border border-[var(--audit-primary-line)] bg-[var(--audit-primary-soft)] p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-[var(--audit-primary)]">当前智能体</p>
              <h2 className="audit-card-title mt-1">{activeAgent.name}</h2>
              <p className="audit-meta mt-1">{activeAgent.topic} / {activeAgent.knowledgeBase}</p>
            </div>
            <StatusPill tone="info">{activeAgent.category}</StatusPill>
          </div>
          <p className="audit-copy mt-3">{activeAgent.prompt}</p>
        </section>

        <form className="mt-5 grid gap-5" action="/pages/chat" method="get">
          <div className="grid gap-4 lg:grid-cols-[18rem_1fr]">
            <label className="block">
              <span className="audit-label">智能体</span>
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
                placeholder="例如：非医保目录自费项目发生基金支付，应核验哪些结算字段？"
                required
              />
            </label>
            <input type="hidden" name="project_name" value={activeAgent.projectName} />
          </div>

          <fieldset>
            <legend className="audit-label">限定知识来源</legend>
            <div className="mt-3 grid gap-3 md:grid-cols-2 2xl:grid-cols-4">
              {documentCategoryStats.map((source) => (
                <label
                  key={source.id}
                  className="flex items-start gap-3 rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-[var(--audit-surface-muted)] p-4 text-sm"
                >
                  <input
                    className="mt-1 size-4"
                    type="checkbox"
                    name="source_collection"
                    value={source.sourceCollection}
                    defaultChecked={source.id === "doc-cat-laws" || source.id === "doc-cat-catalog"}
                  />
                  <span>
                    <span className="block audit-compact-title">{source.name}</span>
                    <span className="mt-1 block audit-meta">{source.description}</span>
                  </span>
                </label>
              ))}
            </div>
          </fieldset>

          <div className="flex flex-wrap items-center gap-3">
            <button className="audit-focus-ring audit-btn audit-btn-primary" type="submit">
              进入审证对话
            </button>
            <a className="audit-focus-ring audit-btn audit-btn-neutral" href="/pages/chat">
              打开后端深页
            </a>
            <a className="audit-focus-ring audit-btn audit-btn-secondary" href="/documents">
              先检索文档
            </a>
          </div>
        </form>

        <section className="mt-6" aria-labelledby="chat-agent-title">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 id="chat-agent-title" className="audit-section-title">可用智能体</h2>
            <a className="audit-focus-ring audit-btn audit-btn-neutral min-h-8 px-3 py-1.5 text-xs" href="/agent-market">
              查看广场
            </a>
          </div>
          <div className="mt-4 grid gap-3 lg:grid-cols-3">
            {agents.map((agent) => (
              <AgentCard key={agent.id} agent={agent} />
            ))}
          </div>
        </section>
      </section>

      <aside className="min-w-0 space-y-4">
        <section className="audit-panel-rail p-5">
          <h2 className="audit-section-title">推荐问题</h2>
          <div className="mt-4 space-y-2">
            {guidedCheckQuestions.slice(0, 4).map((item) => (
              <a
                key={item.id}
                className="audit-focus-ring audit-action-card px-3 py-2"
                href={item.chatHref}
              >
                <span className="audit-meta font-semibold">{item.domain} / {item.agentName}</span>
                <span className="mt-1 block text-sm font-semibold text-[var(--audit-ink)]">{item.question}</span>
              </a>
            ))}
          </div>
        </section>

        <section className="audit-panel-rail p-5">
          <h2 className="audit-section-title">证据边界</h2>
          <ul className="mt-4 space-y-3">
            {evidenceRules.map((rule) => (
              <li key={rule} className="audit-panel-muted px-3 py-2 audit-copy">
                {rule}
              </li>
            ))}
          </ul>
        </section>

        <section className="audit-callout p-5">
          <p className="audit-kicker">输出去向</p>
          <h2 className="audit-section-title mt-2">回答先进入草稿态</h2>
          <p className="audit-copy mt-2">只有引用、原文和人工复核结论都齐备后，才进入底稿生成和报告链路。</p>
        </section>
      </aside>
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
        用此智能体提问
      </a>
    </article>
  );
}
