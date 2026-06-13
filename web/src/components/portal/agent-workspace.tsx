"use client";

import { FormEvent, useState } from "react";

import { StatusPill } from "@/components/ui/status-pill";
import { AgentCategory, AuditAgent, defaultAuditAgents } from "@/lib/portal-data";

const agentCategories: readonly AgentCategory[] = ["业务类", "效率类", "研究类"];

export function AgentWorkspace() {
  const [agents, setAgents] = useState<readonly AuditAgent[]>(defaultAuditAgents);
  const [name, setName] = useState("");
  const [category, setCategory] = useState<AgentCategory>("业务类");
  const [topic, setTopic] = useState("医保基金使用合规");
  const [prompt, setPrompt] = useState("");

  function submitAgent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalizedName = name.trim();
    const normalizedPrompt = prompt.trim();
    const normalizedTopic = topic.trim();

    if (!normalizedName || !normalizedPrompt || !normalizedTopic) {
      return;
    }

    setAgents((current) => [
      {
        id: `agent-${Date.now()}`,
        name: normalizedName,
        category,
        topic: normalizedTopic,
        prompt: normalizedPrompt,
        knowledgeBase: "项目默认知识库",
        projectName: "医保基金使用合规专项自查",
        updatedAt: "刚刚"
      },
      ...current
    ]);
    setName("");
    setPrompt("");
  }

  return (
    <main className="audit-page-grid audit-page-grid--rail">
      <section className="audit-panel p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="audit-kicker">我的智能体</p>
            <h1 className="audit-page-title">提示词型审计智能体</h1>
          </div>
          <StatusPill tone="info">一体一提示词</StatusPill>
        </div>

        <div className="mt-6 grid gap-4 lg:grid-cols-3">
          {agents.map((agent) => (
            <article key={agent.id} className="audit-panel-muted p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="audit-card-title">{agent.name}</h2>
                  <p className="mt-1 audit-meta">{agent.topic}</p>
                </div>
                <StatusPill tone={agent.category === "业务类" ? "success" : "neutral"}>{agent.category}</StatusPill>
              </div>
              <p className="mt-4 line-clamp-4 audit-copy">{agent.prompt}</p>
              <div className="mt-4 flex flex-wrap gap-2">
                <span className="audit-chip">{agent.knowledgeBase}</span>
                <span className="audit-chip">{agent.projectName}</span>
                <span className="audit-chip">{agent.updatedAt}</span>
              </div>
              <a
                className="audit-focus-ring audit-btn audit-btn-primary mt-4"
                href={`/chat?agent=${agent.id}`}
              >
                进入对话
              </a>
            </article>
          ))}
        </div>
      </section>

      <aside className="audit-panel-rail p-5">
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
      </aside>
    </main>
  );
}
