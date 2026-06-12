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
    <main className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_24rem]">
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-[var(--audit-shadow-card)]">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-sm font-semibold text-blue-700">我的智能体</p>
            <h1 className="mt-2 text-3xl font-semibold text-slate-950">提示词型审计智能体</h1>
          </div>
          <StatusPill tone="info">一体一提示词</StatusPill>
        </div>

        <div className="mt-6 grid gap-4 lg:grid-cols-3">
          {agents.map((agent) => (
            <article key={agent.id} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-base font-semibold text-slate-950">{agent.name}</h2>
                  <p className="mt-1 text-xs text-slate-500">{agent.topic}</p>
                </div>
                <StatusPill tone={agent.category === "业务类" ? "success" : "neutral"}>{agent.category}</StatusPill>
              </div>
              <p className="mt-4 line-clamp-4 text-sm leading-6 text-slate-700">{agent.prompt}</p>
              <div className="mt-4 flex flex-wrap gap-2 text-xs text-slate-500">
                <span>{agent.knowledgeBase}</span>
                <span>{agent.projectName}</span>
                <span>{agent.updatedAt}</span>
              </div>
              <a
                className="audit-focus-ring mt-4 inline-flex rounded-xl bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700"
                href={`/chat?agent=${agent.id}`}
              >
                进入对话
              </a>
            </article>
          ))}
        </div>
      </section>

      <aside className="rounded-2xl border border-slate-200 bg-white p-5 shadow-[var(--audit-shadow-card)]">
        <h2 className="text-lg font-semibold text-slate-950">新增智能体</h2>
        <form className="mt-4 space-y-4" onSubmit={submitAgent}>
          <label className="block">
            <span className="text-sm font-semibold text-slate-700">名称</span>
            <input
              className="audit-focus-ring mt-2 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="如：目录限制核验助手"
            />
          </label>
          <label className="block">
            <span className="text-sm font-semibold text-slate-700">分类</span>
            <select
              className="audit-focus-ring mt-2 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
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
            <span className="text-sm font-semibold text-slate-700">审计专题</span>
            <input
              className="audit-focus-ring mt-2 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
              value={topic}
              onChange={(event) => setTopic(event.target.value)}
            />
          </label>
          <label className="block">
            <span className="text-sm font-semibold text-slate-700">提示词</span>
            <textarea
              className="audit-focus-ring mt-2 min-h-32 w-full resize-y rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm leading-6"
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              placeholder="写清审计对象、证据约束、输出格式和人工复核边界。"
            />
          </label>
          <button className="audit-focus-ring w-full rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-700" type="submit">
            新增智能体
          </button>
        </form>
      </aside>
    </main>
  );
}
