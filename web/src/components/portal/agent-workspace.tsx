"use client";

import { FormEvent, useState } from "react";

import { StatusPill } from "@/components/ui/status-pill";
import { AgentCategory, AuditAgent, auditAgentTemplates, defaultAuditAgents } from "@/lib/portal-data";

const agentCategories: readonly AgentCategory[] = ["业务类", "效率类", "研究类"];
type AgentCategoryFilter = "全部" | AgentCategory;

export function AgentWorkspace() {
  const [agents, setAgents] = useState<readonly AuditAgent[]>(defaultAuditAgents);
  const [selectedAgentId, setSelectedAgentId] = useState(defaultAuditAgents[0].id);
  const [categoryFilter, setCategoryFilter] = useState<AgentCategoryFilter>("全部");
  const [name, setName] = useState("");
  const [category, setCategory] = useState<AgentCategory>("业务类");
  const [topic, setTopic] = useState("医保基金使用合规");
  const [prompt, setPrompt] = useState("");
  const filteredAgents = categoryFilter === "全部" ? agents : agents.filter((agent) => agent.category === categoryFilter);
  const selectedAgent = agents.find((agent) => agent.id === selectedAgentId) ?? agents[0];

  function submitAgent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalizedName = name.trim();
    const normalizedPrompt = prompt.trim();
    const normalizedTopic = topic.trim();

    if (!normalizedName || !normalizedPrompt || !normalizedTopic) {
      return;
    }

    const nextAgent: AuditAgent = {
      id: `agent-${Date.now()}`,
      name: normalizedName,
      category,
      topic: normalizedTopic,
      prompt: normalizedPrompt,
      knowledgeBase: "项目默认知识库",
      projectName: "医保基金使用合规专项自查",
      updatedAt: "刚刚"
    };

    setAgents((current) => [nextAgent, ...current]);
    setSelectedAgentId(nextAgent.id);
    setName("");
    setPrompt("");
  }

  return (
    <main className="grid min-w-0 gap-4 xl:grid-cols-[18rem_minmax(0,1fr)_19rem]">
      <aside className="audit-panel-rail min-w-0 p-5">
        <h2 className="audit-section-title">智能体列表</h2>
        <p className="audit-copy mt-2">每个智能体只绑定一个提示词，便于审计人员复核口径。</p>
        <div className="mt-5 flex flex-wrap gap-2" role="group" aria-label="我的智能体分类筛选">
          {(["全部", ...agentCategories] as const).map((item) => (
            <button
              key={item}
              className={`audit-focus-ring rounded-[var(--audit-radius-md)] px-3 py-2 text-sm font-semibold ${
                categoryFilter === item
                  ? "bg-[var(--audit-primary)] text-white"
                  : "bg-white text-[var(--audit-ink-muted)] hover:bg-[var(--audit-surface-muted)] hover:text-[var(--audit-ink)]"
              }`}
              type="button"
              aria-pressed={categoryFilter === item}
              onClick={() => setCategoryFilter(item)}
            >
              {item}
            </button>
          ))}
        </div>
        <div className="mt-5 space-y-3">
          {filteredAgents.map((agent) => (
            <AgentListItem
              key={agent.id}
              agent={agent}
              selected={agent.id === selectedAgent.id}
              onSelect={() => setSelectedAgentId(agent.id)}
            />
          ))}
        </div>
      </aside>

      <section className="audit-panel min-w-0 p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="audit-kicker">我的智能体</p>
            <h1 className="audit-page-title">提示词型审计智能体</h1>
            <p className="audit-copy mt-2 max-w-3xl">按参考工作台组织智能体、提示词、知识库绑定和审证入口。</p>
          </div>
          <StatusPill tone="info">一体一提示词</StatusPill>
        </div>

        <section className="audit-panel-muted mt-6 p-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <h2 className="audit-section-title">{selectedAgent.name}</h2>
              <p className="audit-meta mt-1">{selectedAgent.topic}</p>
            </div>
            <StatusPill tone={selectedAgent.category === "业务类" ? "success" : "neutral"}>{selectedAgent.category}</StatusPill>
          </div>
          <div className="mt-5 grid gap-3 sm:grid-cols-3">
            <PromptMetric label="知识库" value={selectedAgent.knowledgeBase} />
            <PromptMetric label="项目空间" value={selectedAgent.projectName} />
            <PromptMetric label="更新时间" value={selectedAgent.updatedAt} />
          </div>
          <div className="mt-5 rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-white p-4">
            <h3 className="audit-compact-title">提示词</h3>
            <p className="audit-copy mt-3 whitespace-pre-wrap leading-7">{selectedAgent.prompt}</p>
          </div>
          <div className="mt-5 flex flex-wrap gap-3">
            <a className="audit-focus-ring audit-btn audit-btn-primary" href={`/chat?agent=${selectedAgent.id}`}>
              进入对话
            </a>
            <a className="audit-focus-ring audit-btn audit-btn-secondary" href="/agent-market">
              查看模板
            </a>
          </div>
        </section>

        <section className="mt-5 grid gap-4">
          {agents.map((agent) => (
            <article key={agent.id} className="audit-panel-muted min-w-0 p-4">
              <div className="flex items-start justify-between gap-3">
                <h3 className="audit-card-title">{agent.name}</h3>
                <StatusPill tone={agent.category === "业务类" ? "success" : "neutral"}>{agent.category}</StatusPill>
              </div>
              <p className="audit-copy mt-3 line-clamp-3">{agent.prompt}</p>
              <button
                className="audit-focus-ring audit-btn audit-btn-secondary mt-4"
                type="button"
                onClick={() => setSelectedAgentId(agent.id)}
              >
                查看提示词
              </button>
            </article>
          ))}
        </section>
      </section>

      <aside className="min-w-0 space-y-4">
        <section className="audit-panel-rail p-5">
          <h2 className="audit-section-title">新增智能体</h2>
          <form className="mt-4 space-y-4" onSubmit={submitAgent}>
            <label className="block">
              <span className="audit-label">名称</span>
              <input
                className="audit-focus-ring audit-input mt-2 px-3 py-2"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="如：目录限制核验助手"
              />
            </label>
            <label className="block">
              <span className="audit-label">分类</span>
              <select
                className="audit-focus-ring audit-input mt-2 px-3 py-2"
                value={category}
                onChange={(event) => setCategory(event.target.value as AgentCategory)}
              >
                {agentCategories.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="audit-label">审计专题</span>
              <input
                className="audit-focus-ring audit-input mt-2 px-3 py-2"
                value={topic}
                onChange={(event) => setTopic(event.target.value)}
              />
            </label>
            <label className="block">
              <span className="audit-label">提示词</span>
              <textarea
                className="audit-focus-ring audit-input mt-2 min-h-32 resize-y px-3 py-2 leading-6"
                value={prompt}
                onChange={(event) => setPrompt(event.target.value)}
                placeholder="写清审计对象、证据约束、输出格式和人工复核边界。"
              />
            </label>
            <button className="audit-focus-ring audit-btn audit-btn-primary w-full" type="submit">
              新增智能体
            </button>
          </form>
        </section>

        <section className="audit-panel-rail p-5">
          <h2 className="audit-section-title">模板推荐</h2>
          <div className="mt-4 space-y-3">
            {auditAgentTemplates.slice(0, 3).map((agent) => (
              <TemplatePreview key={agent.id} agent={agent} />
            ))}
          </div>
          <a className="audit-focus-ring audit-btn audit-btn-secondary mt-4 w-full" href="/agent-market">
            打开智能体广场
          </a>
        </section>
      </aside>
    </main>
  );
}

function AgentListItem({
  agent,
  selected,
  onSelect
}: {
  readonly agent: AuditAgent;
  readonly selected: boolean;
  readonly onSelect: () => void;
}) {
  return (
    <button
      className={`audit-focus-ring block w-full rounded-[var(--audit-radius-md)] border p-3 text-left ${
        selected
          ? "border-[var(--audit-primary-line)] bg-[var(--audit-primary-soft)]"
          : "border-[var(--audit-line)] bg-white hover:bg-[var(--audit-surface-muted)]"
      }`}
      type="button"
      aria-pressed={selected}
      onClick={onSelect}
    >
      <span className="flex items-start justify-between gap-3">
        <span className="min-w-0">
          <span className="block truncate text-sm font-semibold text-[var(--audit-ink)]">{agent.name}</span>
          <span className="audit-meta mt-1 block truncate">{agent.topic}</span>
        </span>
        <span className="audit-meta shrink-0">{agent.category}</span>
      </span>
    </button>
  );
}

function PromptMetric({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <div className="rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-white p-3">
      <p className="audit-meta font-semibold">{label}</p>
      <p className="mt-1 truncate text-sm font-semibold text-[var(--audit-ink)]">{value}</p>
    </div>
  );
}

function TemplatePreview({ agent }: { readonly agent: AuditAgent }) {
  return (
    <article className="rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-white p-3">
      <div className="flex items-start justify-between gap-3">
        <h3 className="text-sm font-semibold text-[var(--audit-ink)]">{agent.name}</h3>
        <StatusPill tone={agent.category === "业务类" ? "success" : "neutral"}>{agent.category}</StatusPill>
      </div>
      <p className="audit-copy mt-2 line-clamp-2">{agent.prompt}</p>
    </article>
  );
}
