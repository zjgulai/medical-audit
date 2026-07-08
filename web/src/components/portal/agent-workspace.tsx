"use client";

import { FormEvent, useEffect, useState } from "react";

import { useAuditUser } from "@/components/shell/audit-user-context";
import { StatusPill } from "@/components/ui/status-pill";
import {
  createAuditAgent,
  createAuditAgentPromptVersion,
  fetchAgents,
  fetchAuditAgent,
  fetchAuditAgentFeedback,
  fetchAuditAgentInvocations,
  recordAuditAgentInvocation,
  reviewAuditAgentPromptVersion,
  rollbackAuditAgentPromptVersion,
  submitAuditAgentFeedback,
  updateAuditAgentLifecycle
} from "@/lib/api-client";
import type {
  AgentFeedbackApiItem,
  AgentFeedbackRating,
  AgentFeedbackSummary,
  AgentInvocationApiItem,
  AuditAgentApiItem
} from "@/lib/api-types";
import { AgentCategory, AuditAgent, auditAgentTemplates, defaultAuditAgents } from "@/lib/portal-data";
import type { AuditAgentPromptReviewStatus } from "@/lib/portal-data";

const agentCategories: readonly AgentCategory[] = ["业务类", "效率类", "研究类"];
type AgentCategoryFilter = "全部" | AgentCategory;
type AgentStoreStatus = "loading" | "ready" | "fallback" | "saving" | "updating";
type AgentVisibilityScope = "project" | "system";
type PromptLineDiffKind = "unchanged" | "added" | "removed" | "changed";

type PromptLineDiffRow = {
  readonly id: string;
  readonly kind: PromptLineDiffKind;
  readonly previousLine: number | null;
  readonly currentLine: number | null;
  readonly previousText: string;
  readonly currentText: string;
};

const emptyFeedbackSummary: AgentFeedbackSummary = {
  total: 0,
  effective: 0,
  needs_review: 0,
  unsafe: 0,
  latest_rating: null
};

export function AgentWorkspace() {
  const auditUser = useAuditUser();
  const [agents, setAgents] = useState<readonly AuditAgent[]>(defaultAuditAgents);
  const [selectedAgentId, setSelectedAgentId] = useState(defaultAuditAgents[0].id);
  const [categoryFilter, setCategoryFilter] = useState<AgentCategoryFilter>("全部");
  const [name, setName] = useState("");
  const [category, setCategory] = useState<AgentCategory>("业务类");
  const [topic, setTopic] = useState("医保基金使用合规");
  const [knowledgeBase, setKnowledgeBase] = useState("项目默认知识库");
  const [projectName, setProjectName] = useState("医保基金使用合规专项自查");
  const [visibilityScope, setVisibilityScope] = useState<AgentVisibilityScope>("project");
  const [prompt, setPrompt] = useState("");
  const [versionPrompt, setVersionPrompt] = useState("");
  const [versionChangeSummary, setVersionChangeSummary] = useState("人工优化提示词约束。");
  const [reviewNote, setReviewNote] = useState("");
  const [invocations, setInvocations] = useState<readonly AgentInvocationApiItem[]>([]);
  const [feedbackEntries, setFeedbackEntries] = useState<readonly AgentFeedbackApiItem[]>([]);
  const [feedbackSummary, setFeedbackSummary] = useState<AgentFeedbackSummary>(emptyFeedbackSummary);
  const [feedbackRating, setFeedbackRating] = useState<AgentFeedbackRating>("effective");
  const [feedbackComment, setFeedbackComment] = useState("");
  const [governanceNotice, setGovernanceNotice] = useState<string | null>(null);
  const [activeTemplateId, setActiveTemplateId] = useState<string | null>(null);
  const [templateNotice, setTemplateNotice] = useState<string | null>(null);
  const [storeStatus, setStoreStatus] = useState<AgentStoreStatus>("loading");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const roleVisibleAgents = agents.filter(
    (agent) => !agent.allowedRoles || agent.allowedRoles.includes(auditUser.role)
  );
  const filteredAgents =
    categoryFilter === "全部"
      ? roleVisibleAgents
      : roleVisibleAgents.filter((agent) => agent.category === categoryFilter);
  const selectedAgent = agents.find((agent) => agent.id === selectedAgentId) ?? agents[0] ?? defaultAuditAgents[0];
  const activeTemplate = auditAgentTemplates.find((template) => template.id === activeTemplateId);
  const canManageAgents = auditUser.can("manage_agents");
  const canReviewAgentPrompts = auditUser.role === "admin" || auditUser.role === "director";
  const selectedPromptVersions = selectedAgent.promptVersions ?? [];
  const activePromptVersion = selectedPromptVersions.find(
    (version) => version.isActive
  ) ?? selectedPromptVersions.find(
    (version) => version.version === (selectedAgent.promptVersion ?? 1)
  );
  const latestPromptVersion = latestPromptVersionForAgent(selectedAgent);
  const hasPendingActivation = Boolean(
    latestPromptVersion && latestPromptVersion.version !== (selectedAgent.promptVersion ?? 1)
  );
  const reviewTargetPromptVersion = hasPendingActivation
    ? latestPromptVersion
    : activePromptVersion;
  const currentReviewStatus = activePromptVersion?.reviewStatus ?? "approved";
  const reviewTargetVersion = reviewTargetPromptVersion?.version ?? selectedAgent.promptVersion ?? 1;
  const reviewTargetStatus = reviewTargetPromptVersion?.reviewStatus ?? currentReviewStatus;
  const previousPromptVersion = previousVersionForDiff(
    selectedPromptVersions,
    selectedAgent.promptVersion ?? 1
  );
  const comparisonBaseVersion = hasPendingActivation ? activePromptVersion : previousPromptVersion;
  const comparisonTargetVersion = hasPendingActivation ? latestPromptVersion : activePromptVersion;
  const comparisonTargetPrompt = comparisonTargetVersion?.prompt ?? selectedAgent.prompt;
  const diffSummary = promptDiffSummary(comparisonBaseVersion?.prompt, comparisonTargetPrompt);
  const promptLineDiffRows = promptLineDiff(comparisonBaseVersion?.prompt, comparisonTargetPrompt);

  useEffect(() => {
    let isMounted = true;

    fetchAgents()
      .then((response) => {
        if (!isMounted) {
          return;
        }
        const nextAgents = response.items
          .filter((agent) => agent.status === "active")
          .map(apiAgentToPortalAgent);
        if (nextAgents.length > 0) {
          setAgents(nextAgents);
          setSelectedAgentId((current) =>
            nextAgents.some((agent) => agent.id === current) ? current : nextAgents[0].id
          );
        }
        setStoreStatus(response.store.ready ? "ready" : "fallback");
      })
      .catch(() => {
        if (!isMounted) {
          return;
        }
        setStoreStatus("fallback");
      });

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    setVersionPrompt(latestPromptVersion?.prompt ?? selectedAgent.prompt);
    setVersionChangeSummary("人工优化提示词约束。");
    setFeedbackComment("");
    setReviewNote(reviewTargetPromptVersion?.reviewNote ?? "");
  }, [
    latestPromptVersion?.prompt,
    reviewTargetPromptVersion?.reviewNote,
    reviewTargetPromptVersion?.version,
    selectedAgent.id,
    selectedAgent.prompt
  ]);

  useEffect(() => {
    setGovernanceNotice(null);
  }, [selectedAgent.id]);

  useEffect(() => {
    let isMounted = true;

    fetchAuditAgent(selectedAgentId)
      .then((response) => {
        if (!isMounted) {
          return;
        }
        const nextAgent = apiAgentToPortalAgent(response.item);
        setAgents((current) => [
          nextAgent,
          ...current.filter((agent) => agent.id !== nextAgent.id)
        ]);
      })
      .catch(() => {
        // Detail sync is additive; the list response remains the fallback source.
      });

    Promise.all([
      fetchAuditAgentInvocations(selectedAgentId),
      fetchAuditAgentFeedback(selectedAgentId)
    ])
      .then(([invocationResponse, feedbackResponse]) => {
        if (!isMounted) {
          return;
        }
        setInvocations(invocationResponse.items);
        setFeedbackEntries(feedbackResponse.items);
        setFeedbackSummary(feedbackResponse.summary);
      })
      .catch(() => {
        if (!isMounted) {
          return;
        }
        setInvocations([]);
        setFeedbackEntries([]);
        setFeedbackSummary(emptyFeedbackSummary);
      });

    return () => {
      isMounted = false;
    };
  }, [selectedAgentId]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const templateId = new URLSearchParams(window.location.search).get("template");
    const template = auditAgentTemplates.find((item) => item.id === templateId);
    if (!template) {
      return;
    }

    setName(template.name);
    setCategory(template.category);
    setTopic(template.topic);
    setKnowledgeBase(template.knowledgeBase);
    setProjectName(template.projectName);
    setVisibilityScope("project");
    setPrompt(template.prompt);
    setActiveTemplateId(template.id);
    setTemplateNotice(`${template.name} 已填入新增表单，保存后才会写入我的智能体。`);
  }, []);

  async function submitAgent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canManageAgents) {
      setErrorMessage("当前角色无智能体保存权限。");
      return;
    }

    const normalizedName = name.trim();
    const normalizedPrompt = prompt.trim();
    const normalizedTopic = topic.trim();
    const normalizedKnowledgeBase = knowledgeBase.trim();
    const normalizedProjectName = projectName.trim();

    if (!normalizedName || !normalizedPrompt || !normalizedTopic || !normalizedKnowledgeBase || !normalizedProjectName) {
      return;
    }

    setStoreStatus("saving");
    setErrorMessage(null);
    try {
      const response = await createAuditAgent({
        name: normalizedName,
        category,
        topic: normalizedTopic,
        prompt: normalizedPrompt,
        knowledge_base: normalizedKnowledgeBase,
        project_name: normalizedProjectName,
        visibility_scope: visibilityScope,
        allowed_roles: ["admin", "technician", "director", "member"]
      });
      const nextAgent = apiAgentToPortalAgent(response.item);
      setAgents((current) => [nextAgent, ...current.filter((agent) => agent.id !== nextAgent.id)]);
      setSelectedAgentId(nextAgent.id);
      setName("");
      setPrompt("");
      setActiveTemplateId(null);
      setTemplateNotice(null);
      setStoreStatus(response.store.ready ? "ready" : "fallback");
    } catch {
      setStoreStatus("fallback");
      setErrorMessage("智能体未保存，请检查后端连接和当前角色权限。");
    }
  }

  function applyTemplate(template: AuditAgent) {
    setName(template.name);
    setCategory(template.category);
    setTopic(template.topic);
    setKnowledgeBase(template.knowledgeBase);
    setProjectName(template.projectName);
    setVisibilityScope("project");
    setPrompt(template.prompt);
    setActiveTemplateId(template.id);
    setTemplateNotice(`${template.name} 已填入新增表单，保存后才会写入我的智能体。`);
  }

  function updateAgentFromApi(agent: AuditAgentApiItem) {
    const nextAgent = apiAgentToPortalAgent(agent);
    setAgents((current) => [nextAgent, ...current.filter((item) => item.id !== nextAgent.id)]);
    setSelectedAgentId(nextAgent.id);
    setVersionPrompt(latestPromptVersionForAgent(nextAgent)?.prompt ?? nextAgent.prompt);
    return nextAgent;
  }

  async function saveSelectedAgentVersion() {
    if (!canManageAgents || !selectedAgent.id.startsWith("agent-custom-")) {
      return;
    }
    const normalizedPrompt = versionPrompt.trim();
    const normalizedSummary = versionChangeSummary.trim();
    if (!normalizedPrompt || !normalizedSummary) {
      return;
    }

    setStoreStatus("updating");
    setErrorMessage(null);
    setGovernanceNotice(null);
    try {
      const response = await createAuditAgentPromptVersion(selectedAgent.id, {
        prompt: normalizedPrompt,
        change_summary: normalizedSummary,
        review_note: normalizedSummary
      });
      const nextAgent = updateAgentFromApi(response.item);
      const savedVersion = latestPromptVersionForAgent(nextAgent)?.version ?? nextAgent.promptVersion ?? 1;
      setStoreStatus(response.store.ready ? "ready" : "fallback");
      setGovernanceNotice(`已保存 ${nextAgent.name} v${savedVersion}，待审批通过后激活。`);
    } catch {
      setStoreStatus("fallback");
      setErrorMessage("提示词版本未保存，请检查后端连接和当前角色权限。");
    }
  }

  async function rollbackSelectedAgentVersion(version: number) {
    if (!canReviewAgentPrompts || !selectedAgent.id.startsWith("agent-custom-")) {
      return;
    }

    setStoreStatus("updating");
    setErrorMessage(null);
    setGovernanceNotice(null);
    try {
      const response = await rollbackAuditAgentPromptVersion(selectedAgent.id, { version });
      const nextAgent = updateAgentFromApi(response.item);
      setStoreStatus(response.store.ready ? "ready" : "fallback");
      setGovernanceNotice(`已回滚生成 ${nextAgent.name} v${nextAgent.promptVersion ?? 1}。`);
    } catch {
      setStoreStatus("fallback");
      setErrorMessage("提示词版本未回滚，请检查后端连接和当前角色权限。");
    }
  }

  async function reviewSelectedAgentPromptVersion(reviewStatus: AuditAgentPromptReviewStatus) {
    if (!canReviewAgentPrompts || !selectedAgent.id.startsWith("agent-custom-")) {
      return;
    }
    const version = reviewTargetVersion;

    setStoreStatus("updating");
    setErrorMessage(null);
    setGovernanceNotice(null);
    try {
      const response = await reviewAuditAgentPromptVersion(selectedAgent.id, {
        version,
        review_status: reviewStatus,
        review_note: reviewNote.trim()
      });
      const nextAgent = updateAgentFromApi(response.item);
      setStoreStatus(response.store.ready ? "ready" : "fallback");
      const wasActivated = reviewStatus === "approved" && nextAgent.promptVersion === version;
      setGovernanceNotice(
        wasActivated
          ? `已批准并激活 ${nextAgent.name} v${version}。`
          : `已更新 ${nextAgent.name} v${version} 审核状态：${promptReviewStatusLabel(reviewStatus)}。`
      );
    } catch {
      setStoreStatus("fallback");
      setErrorMessage("提示词版本审核状态未更新，请检查后端连接和当前角色权限。");
    }
  }

  async function updateSelectedAgentLifecycle(status: "inactive" | "archived", reason: string) {
    if (!canManageAgents || !selectedAgent.id.startsWith("agent-custom-")) {
      return;
    }

    setStoreStatus("updating");
    setErrorMessage(null);
    setGovernanceNotice(null);
    try {
      const response = await updateAuditAgentLifecycle(selectedAgent.id, {
        status,
        reason
      });
      setAgents((current) => current.filter((agent) => agent.id !== response.item.id));
      setSelectedAgentId((current) => {
        if (current !== response.item.id) {
          return current;
        }
        const nextAgent = agents.find((agent) => agent.id !== response.item.id) ?? defaultAuditAgents[0];
        return nextAgent.id;
      });
      setStoreStatus(response.store.ready ? "ready" : "fallback");
      setGovernanceNotice(status === "archived" ? "智能体已进入软归档。" : "智能体已下架。");
    } catch {
      setStoreStatus("fallback");
      setErrorMessage("智能体状态未更新，请检查后端连接和当前角色权限。");
    }
  }

  async function deactivateSelectedAgent() {
    await updateSelectedAgentLifecycle("inactive", "工作台下架，保留历史追溯。");
  }

  async function archiveSelectedAgent() {
    await updateSelectedAgentLifecycle("archived", "工作台软归档，不做物理删除。");
  }

  async function recordSelectedInvocation() {
    setStoreStatus("updating");
    setErrorMessage(null);
    setGovernanceNotice(null);
    try {
      const response = await recordAuditAgentInvocation(selectedAgent.id, {
        invocation_source: "agent-workspace",
        question: `${selectedAgent.name} 工作台试用登记`,
        metadata: { prompt_version_key: selectedAgent.promptVersionKey ?? `${selectedAgent.id}@v1` }
      });
      setInvocations((current) => [response.item, ...current]);
      setStoreStatus(response.store.ready ? "ready" : "fallback");
      setGovernanceNotice("已登记一次智能体使用记录。");
    } catch {
      setStoreStatus("fallback");
      setErrorMessage("智能体使用记录未登记，请检查后端连接和当前角色权限。");
    }
  }

  async function submitSelectedFeedback() {
    const normalizedComment = feedbackComment.trim();
    setStoreStatus("updating");
    setErrorMessage(null);
    setGovernanceNotice(null);
    try {
      const response = await submitAuditAgentFeedback(selectedAgent.id, {
        invocation_id: invocations[0]?.id ?? null,
        rating: feedbackRating,
        comment: normalizedComment,
        metadata: { prompt_version_key: selectedAgent.promptVersionKey ?? `${selectedAgent.id}@v1` }
      });
      setFeedbackEntries((current) => [response.item, ...current]);
      setFeedbackSummary(response.summary);
      setFeedbackComment("");
      setStoreStatus(response.store.ready ? "ready" : "fallback");
      setGovernanceNotice("已提交智能体效果反馈。");
    } catch {
      setStoreStatus("fallback");
      setErrorMessage("智能体反馈未提交，请检查后端连接和当前角色权限。");
    }
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
          <div className="flex flex-wrap gap-2">
            <StatusPill tone="info">一体一提示词</StatusPill>
            <StatusPill tone={storeStatus === "ready" ? "success" : "neutral"}>
              {agentStoreStatusLabel(storeStatus)}
            </StatusPill>
          </div>
        </div>

        <section className="audit-panel-muted mt-6 p-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <h2 className="audit-section-title">{selectedAgent.name}</h2>
              <p className="audit-meta mt-1">{selectedAgent.topic}</p>
            </div>
            <StatusPill tone={selectedAgent.category === "业务类" ? "success" : "neutral"}>{selectedAgent.category}</StatusPill>
          </div>
          <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <PromptMetric label="知识库" value={selectedAgent.knowledgeBase} />
            <PromptMetric label="关联项目" value={selectedAgent.projectName} />
            <PromptMetric label="提示词版本" value={`v${selectedAgent.promptVersion ?? 1}`} />
            <PromptMetric
              label="待审版本"
              value={hasPendingActivation && latestPromptVersion ? `v${latestPromptVersion.version}` : "无"}
            />
            <PromptMetric label="审核状态" value={promptReviewStatusLabel(currentReviewStatus)} />
            <PromptMetric label="可见范围" value={agentVisibilityLabel(selectedAgent.visibilityScope)} />
            <PromptMetric label="更新时间" value={selectedAgent.updatedAt} />
          </div>
          <div className="mt-5 rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-white p-4">
            <h3 className="audit-compact-title">提示词</h3>
            <p className="audit-copy mt-3 whitespace-pre-wrap leading-7">{selectedAgent.prompt}</p>
          </div>
          {governanceNotice ? (
            <p className="mt-4 text-sm font-semibold text-[var(--audit-primary)]" role="status">
              {governanceNotice}
            </p>
          ) : null}
          <div className="mt-5 grid gap-4 xl:grid-cols-2">
            <section className="rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-white p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h3 className="audit-compact-title">版本对比</h3>
                  <p className="audit-meta mt-1">
                    {hasPendingActivation && activePromptVersion && latestPromptVersion
                      ? `对比当前激活 v${activePromptVersion.version} 与待审 v${latestPromptVersion.version}`
                      : previousPromptVersion
                        ? `对比 v${previousPromptVersion.version} 与 v${selectedAgent.promptVersion ?? 1}`
                        : "当前为初始提示词版本"}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <StatusPill tone={promptReviewStatusTone(reviewTargetStatus)}>
                    {promptReviewStatusLabel(reviewTargetStatus)}
                  </StatusPill>
                  <StatusPill tone="info">{diffSummary}</StatusPill>
                </div>
              </div>
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                <PromptVersionPreview
                  title={comparisonBaseVersion ? `基准版 v${comparisonBaseVersion.version}` : "基准版"}
                  prompt={comparisonBaseVersion?.prompt ?? "暂无基准版"}
                />
                <PromptVersionPreview
                  title={
                    hasPendingActivation && comparisonTargetVersion
                      ? `待审版 v${comparisonTargetVersion.version}`
                      : `当前版 v${selectedAgent.promptVersion ?? 1}`
                  }
                  prompt={comparisonTargetPrompt}
                />
              </div>
              <PromptLineDiffTable rows={promptLineDiffRows} />
              <div className="mt-4 space-y-2">
                {selectedPromptVersions.slice(-4).map((version) => (
                  <div
                    key={`${selectedAgent.id}-${version.version}`}
                    className="flex flex-wrap items-center justify-between gap-3 rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-[var(--audit-surface-muted)] px-3 py-2"
                  >
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-sm font-semibold text-[var(--audit-ink)]">v{version.version}</p>
                        {version.isActive ? <StatusPill tone="success">当前激活</StatusPill> : null}
                      </div>
                      <p className="audit-meta truncate">{version.changeSummary}</p>
                    </div>
                    <div className="flex flex-wrap items-center justify-end gap-2">
                      <StatusPill tone={promptReviewStatusTone(version.reviewStatus)}>
                        {promptReviewStatusLabel(version.reviewStatus)}
                      </StatusPill>
                      {canReviewAgentPrompts &&
                      selectedAgent.id.startsWith("agent-custom-") &&
                      version.version !== selectedAgent.promptVersion ? (
                        <button
                          className="audit-focus-ring audit-btn audit-btn-neutral min-h-8 px-3 py-1.5 text-xs"
                          type="button"
                          disabled={storeStatus === "updating"}
                          onClick={() => rollbackSelectedAgentVersion(version.version)}
                        >
                          回滚到此版
                        </button>
                      ) : null}
                    </div>
                  </div>
                ))}
              </div>
              {canManageAgents && selectedAgent.id.startsWith("agent-custom-") ? (
                <div className="mt-4 space-y-3">
                  <label className="block">
                    <span className="audit-label">新版本提示词</span>
                    <textarea
                      className="audit-focus-ring audit-input mt-2 min-h-28 resize-y px-3 py-2 leading-6"
                      value={versionPrompt}
                      onChange={(event) => setVersionPrompt(event.target.value)}
                    />
                  </label>
                  <label className="block">
                    <span className="audit-label">变更说明</span>
                    <input
                      className="audit-focus-ring audit-input mt-2 px-3 py-2"
                      value={versionChangeSummary}
                      onChange={(event) => setVersionChangeSummary(event.target.value)}
                    />
                  </label>
                  <label className="block">
                    <span className="audit-label">审核意见</span>
                    <textarea
                      className="audit-focus-ring audit-input mt-2 min-h-20 resize-y px-3 py-2 leading-6"
                      value={reviewNote}
                      onChange={(event) => setReviewNote(event.target.value)}
                    />
                  </label>
                  <p className="audit-meta">审核对象：v{reviewTargetVersion}</p>
                  <button
                    className="audit-focus-ring audit-btn audit-btn-primary"
                    type="button"
                    disabled={storeStatus === "updating"}
                    onClick={saveSelectedAgentVersion}
                  >
                    保存新版本
                  </button>
                  <div className="flex flex-wrap gap-2">
                    <button
                      className="audit-focus-ring audit-btn audit-btn-secondary"
                      type="button"
                      disabled={storeStatus === "updating" || !canReviewAgentPrompts}
                      title={!canReviewAgentPrompts ? "仅管理员或主任可审核激活" : undefined}
                      onClick={() => reviewSelectedAgentPromptVersion("approved")}
                    >
                      审批通过
                    </button>
                    <button
                      className="audit-focus-ring audit-btn audit-btn-neutral"
                      type="button"
                      disabled={storeStatus === "updating" || !canReviewAgentPrompts}
                      title={!canReviewAgentPrompts ? "仅管理员或主任可审核激活" : undefined}
                      onClick={() => reviewSelectedAgentPromptVersion("changes-requested")}
                    >
                      要求修改
                    </button>
                  </div>
                </div>
              ) : null}
            </section>

            <section className="rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-white p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h3 className="audit-compact-title">调用与反馈</h3>
                  <p className="audit-meta mt-1">
                    {invocations.length} 次登记 / {feedbackSummary.total} 条反馈
                  </p>
                </div>
                <button
                  className="audit-focus-ring audit-btn audit-btn-secondary min-h-8 px-3 py-1.5 text-xs"
                  type="button"
                  disabled={storeStatus === "updating"}
                  onClick={recordSelectedInvocation}
                >
                  登记试用
                </button>
              </div>
              <div className="mt-4 grid gap-3 sm:grid-cols-3">
                <PromptMetric label="可继续使用" value={`${feedbackSummary.effective} 条`} />
                <PromptMetric label="需要复核" value={`${feedbackSummary.needs_review} 条`} />
                <PromptMetric label="暂不建议" value={`${feedbackSummary.unsafe} 条`} />
              </div>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <label className="block">
                  <span className="audit-label">效果评级</span>
                  <select
                    className="audit-focus-ring audit-input mt-2 px-3 py-2"
                    value={feedbackRating}
                    onChange={(event) => setFeedbackRating(event.target.value as AgentFeedbackRating)}
                  >
                    <option value="effective">可继续使用</option>
                    <option value="needs_review">需要复核</option>
                    <option value="unsafe">暂不建议使用</option>
                  </select>
                </label>
                <label className="block sm:col-span-2">
                  <span className="audit-label">反馈说明</span>
                  <textarea
                    className="audit-focus-ring audit-input mt-2 min-h-24 resize-y px-3 py-2 leading-6"
                    value={feedbackComment}
                    onChange={(event) => setFeedbackComment(event.target.value)}
                    placeholder="记录引用质量、口径偏差或适用场景。"
                  />
                </label>
              </div>
              <button
                className="audit-focus-ring audit-btn audit-btn-primary mt-3"
                type="button"
                disabled={storeStatus === "updating"}
                onClick={submitSelectedFeedback}
              >
                提交反馈
              </button>
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                <RecentTraceList
                  title="最近调用"
                  emptyLabel="暂无调用记录"
                  items={invocations.map((item) => ({
                    id: item.id,
                    title: `v${item.prompt_version} / ${item.invocation_source}`,
                    detail: item.question ?? "未登记问题",
                    meta: formatAgentUpdatedAt(item.created_at)
                  }))}
                />
                <RecentTraceList
                  title="最近反馈"
                  emptyLabel="暂无反馈记录"
                  items={feedbackEntries.map((item) => ({
                    id: item.id,
                    title: feedbackRatingLabel(item.rating),
                    detail: item.comment || "未填写说明",
                    meta: `v${item.prompt_version} / ${formatAgentUpdatedAt(item.created_at)}`
                  }))}
                />
              </div>
            </section>
          </div>
          <div className="mt-5 flex flex-wrap gap-3">
            <a className="audit-focus-ring audit-btn audit-btn-primary" href={`/chat?agent=${selectedAgent.id}`}>
              进入对话
            </a>
            <a className="audit-focus-ring audit-btn audit-btn-secondary" href="/agent-market">
              查看模板
            </a>
            {canManageAgents && selectedAgent.id.startsWith("agent-custom-") ? (
              <button
                className="audit-focus-ring audit-btn audit-btn-secondary"
                type="button"
                disabled={storeStatus === "updating"}
                onClick={deactivateSelectedAgent}
              >
                {storeStatus === "updating" ? "状态更新中" : "下架智能体"}
              </button>
            ) : null}
            {canManageAgents && selectedAgent.id.startsWith("agent-custom-") ? (
              <button
                className="audit-focus-ring audit-btn audit-btn-secondary"
                type="button"
                disabled={storeStatus === "updating"}
                onClick={archiveSelectedAgent}
              >
                软归档智能体
              </button>
            ) : null}
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
        <section className="audit-panel-rail scroll-mt-40 p-5" id="new-agent">
          <h2 className="audit-section-title">新增智能体</h2>
          <p className="audit-copy mt-2">可从广场套用提示词模板；点击保存前不会写入后端。</p>
          {templateNotice ? (
            <div
              className="mt-4 rounded-[var(--audit-radius-md)] border border-[var(--audit-primary-line)] bg-[var(--audit-primary-soft)] p-3"
              role="status"
              aria-label="模板已预填"
            >
              <p className="text-sm font-semibold text-[var(--audit-ink)]">模板已预填</p>
              <p className="audit-copy mt-1">{templateNotice}</p>
              {activeTemplate ? <p className="audit-meta mt-2">来源模板：{activeTemplate.name}</p> : null}
            </div>
          ) : null}
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
              <span className="audit-label">关联知识库</span>
              <input
                className="audit-focus-ring audit-input mt-2 px-3 py-2"
                value={knowledgeBase}
                onChange={(event) => setKnowledgeBase(event.target.value)}
              />
            </label>
            <label className="block">
              <span className="audit-label">关联项目</span>
              <input
                className="audit-focus-ring audit-input mt-2 px-3 py-2"
                value={projectName}
                onChange={(event) => setProjectName(event.target.value)}
              />
            </label>
            <label className="block">
              <span className="audit-label">可见范围</span>
              <select
                className="audit-focus-ring audit-input mt-2 px-3 py-2"
                value={visibilityScope}
                onChange={(event) => setVisibilityScope(event.target.value as AgentVisibilityScope)}
              >
                <option value="project">项目内</option>
                <option value="system">系统级</option>
              </select>
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
            {errorMessage ? (
              <p className="text-sm font-semibold text-[var(--audit-red)]" role="alert">
                {errorMessage}
              </p>
            ) : null}
            <button
              className="audit-focus-ring audit-btn audit-btn-primary w-full"
              type="submit"
              disabled={storeStatus === "saving" || !canManageAgents}
            >
              {storeStatus === "saving" ? "保存中" : "新增智能体"}
            </button>
            {!canManageAgents ? (
              <p className="audit-meta">当前角色只能查看和使用智能体，不能保存新的系统智能体。</p>
            ) : null}
          </form>
        </section>

        <section className="audit-panel-rail p-5">
          <h2 className="audit-section-title">模板推荐</h2>
          <div className="mt-4 space-y-3">
            {auditAgentTemplates.slice(0, 3).map((agent) => (
              <TemplatePreview
                key={agent.id}
                agent={agent}
                isActive={agent.id === activeTemplateId}
                onApply={() => applyTemplate(agent)}
              />
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
    promptVersions: agent.prompt_versions.map((version) => ({
      version: version.version,
      prompt: version.prompt,
      changeSummary: version.change_summary,
      isActive: version.is_active ?? version.version === agent.prompt_version,
      createdBy: version.created_by,
      createdAt: version.created_at,
      reviewStatus: version.review_status ?? "approved",
      reviewNote: version.review_note ?? "",
      requestedBy: version.requested_by ?? null,
      reviewedBy: version.reviewed_by ?? null,
      reviewedAt: version.reviewed_at ?? null,
      reviewUpdatedAt: version.review_updated_at ?? null
    })),
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

function agentStoreStatusLabel(status: AgentStoreStatus): string {
  if (status === "ready") {
    return "后端已连接";
  }
  if (status === "saving") {
    return "保存中";
  }
  if (status === "updating") {
    return "更新中";
  }
  if (status === "loading") {
    return "连接中";
  }
  return "默认内容";
}

function agentVisibilityLabel(scope: AuditAgent["visibilityScope"]): string {
  if (scope === "system") {
    return "系统级";
  }
  return "项目内";
}

function previousVersionForDiff(
  versions: readonly NonNullable<AuditAgent["promptVersions"]>[number][],
  currentVersion: number
) {
  return [...versions].reverse().find((version) => version.version < currentVersion);
}

function latestPromptVersionForAgent(agent: AuditAgent) {
  const sortedVersions = [...(agent.promptVersions ?? [])].sort((left, right) => left.version - right.version);
  return sortedVersions[sortedVersions.length - 1];
}

function promptDiffSummary(previousPrompt: string | undefined, currentPrompt: string): string {
  if (!previousPrompt) {
    return "初始版本";
  }
  const delta = currentPrompt.length - previousPrompt.length;
  if (delta > 0) {
    return `新增 ${delta} 字`;
  }
  if (delta < 0) {
    return `减少 ${Math.abs(delta)} 字`;
  }
  return "字数不变";
}

function promptLineDiff(
  previousPrompt: string | undefined,
  currentPrompt: string
): readonly PromptLineDiffRow[] {
  if (!previousPrompt) {
    return [];
  }

  const previousLines = splitPromptLines(previousPrompt);
  const currentLines = splitPromptLines(currentPrompt);
  const maxLineCount = Math.max(previousLines.length, currentLines.length);
  return Array.from({ length: maxLineCount }, (_, index) => {
    const previousText = previousLines[index] ?? "";
    const currentText = currentLines[index] ?? "";
    return {
      id: `line-${index + 1}`,
      kind: promptLineDiffKind(previousLines[index], currentLines[index]),
      previousLine: previousLines[index] === undefined ? null : index + 1,
      currentLine: currentLines[index] === undefined ? null : index + 1,
      previousText,
      currentText
    };
  });
}

function splitPromptLines(prompt: string): readonly string[] {
  const lines = prompt.split(/\r?\n/);
  return lines.length === 1 && lines[0] === "" ? [] : lines;
}

function promptLineDiffKind(
  previousLine: string | undefined,
  currentLine: string | undefined
): PromptLineDiffKind {
  if (previousLine === undefined) {
    return "added";
  }
  if (currentLine === undefined) {
    return "removed";
  }
  if (previousLine === currentLine) {
    return "unchanged";
  }
  return "changed";
}

function promptLineDiffLabel(kind: PromptLineDiffKind): string {
  if (kind === "added") {
    return "新增";
  }
  if (kind === "removed") {
    return "删除";
  }
  if (kind === "changed") {
    return "变更";
  }
  return "未变";
}

function promptReviewStatusLabel(status: AuditAgentPromptReviewStatus): string {
  if (status === "pending-review") {
    return "待审批";
  }
  if (status === "changes-requested") {
    return "要求修改";
  }
  return "已通过";
}

function promptReviewStatusTone(status: AuditAgentPromptReviewStatus): "neutral" | "info" | "success" | "warning" {
  if (status === "approved") {
    return "success";
  }
  if (status === "changes-requested") {
    return "warning";
  }
  return "info";
}

function feedbackRatingLabel(rating: AgentFeedbackRating): string {
  if (rating === "effective") {
    return "可继续使用";
  }
  if (rating === "needs_review") {
    return "需要复核";
  }
  return "暂不建议使用";
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

function PromptLineDiffTable({ rows }: { readonly rows: readonly PromptLineDiffRow[] }) {
  if (rows.length === 0) {
    return null;
  }

  return (
    <div className="mt-4 overflow-hidden rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-white">
      <div className="grid grid-cols-[4.5rem_minmax(0,1fr)_minmax(0,1fr)] border-b border-[var(--audit-line)] bg-[var(--audit-surface-muted)] px-3 py-2 text-xs font-semibold text-[var(--audit-ink-muted)]">
        <span>行状态</span>
        <span>上一版</span>
        <span>当前版</span>
      </div>
      <div className="max-h-72 overflow-auto">
        {rows.map((row) => (
          <div
            key={row.id}
            className="grid grid-cols-[4.5rem_minmax(0,1fr)_minmax(0,1fr)] gap-3 border-b border-[var(--audit-line)] px-3 py-2 last:border-b-0"
          >
            <span className="audit-meta font-semibold">{promptLineDiffLabel(row.kind)}</span>
            <p className="min-w-0 whitespace-pre-wrap break-words text-xs leading-5 text-[var(--audit-ink-muted)]">
              <span className="mr-2 font-semibold text-[var(--audit-ink-subtle)]">
                {row.previousLine ?? "-"}
              </span>
              {row.previousText || "-"}
            </p>
            <p className="min-w-0 whitespace-pre-wrap break-words text-xs leading-5 text-[var(--audit-ink)]">
              <span className="mr-2 font-semibold text-[var(--audit-ink-subtle)]">
                {row.currentLine ?? "-"}
              </span>
              {row.currentText || "-"}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

function PromptVersionPreview({
  title,
  prompt
}: {
  readonly title: string;
  readonly prompt: string;
}) {
  return (
    <div className="rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-[var(--audit-surface-muted)] p-3">
      <p className="audit-meta font-semibold">{title}</p>
      <p className="audit-copy mt-2 line-clamp-5 whitespace-pre-wrap">{prompt}</p>
    </div>
  );
}

function RecentTraceList({
  title,
  emptyLabel,
  items
}: {
  readonly title: string;
  readonly emptyLabel: string;
  readonly items: readonly {
    readonly id: string;
    readonly title: string;
    readonly detail: string;
    readonly meta: string;
  }[];
}) {
  return (
    <div className="rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-[var(--audit-surface-muted)] p-3">
      <p className="audit-meta font-semibold">{title}</p>
      <div className="mt-2 space-y-2">
        {items.length === 0 ? <p className="audit-copy">{emptyLabel}</p> : null}
        {items.slice(0, 3).map((item) => (
          <div key={item.id} className="rounded-[var(--audit-radius-md)] bg-white px-3 py-2">
            <p className="text-sm font-semibold text-[var(--audit-ink)]">{item.title}</p>
            <p className="audit-copy mt-1 line-clamp-2">{item.detail}</p>
            <p className="audit-meta mt-1">{item.meta}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function TemplatePreview({
  agent,
  isActive,
  onApply
}: {
  readonly agent: AuditAgent;
  readonly isActive: boolean;
  readonly onApply: () => void;
}) {
  return (
    <article className="rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-white p-3">
      <div className="flex items-start justify-between gap-3">
        <h3 className="text-sm font-semibold text-[var(--audit-ink)]">{agent.name}</h3>
        <StatusPill tone={agent.category === "业务类" ? "success" : "neutral"}>{agent.category}</StatusPill>
      </div>
      <p className="audit-copy mt-2 line-clamp-2">{agent.prompt}</p>
      <button
        className="audit-focus-ring audit-btn audit-btn-secondary mt-3 w-full"
        type="button"
        onClick={onApply}
        aria-pressed={isActive}
      >
        {isActive ? "已填入表单" : "套用此模板"}
      </button>
    </article>
  );
}
