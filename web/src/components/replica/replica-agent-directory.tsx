"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { useReplicaAgentsData } from "./use-replica-runtime";
import { createAuditAgent } from "@/lib/api-client";
import type { ApiAgentCategory } from "@/lib/api-types";
import { DEFAULT_AUDIT_PROJECT_NAME } from "@/lib/audit-user";
import type { ReferenceAgentCard, ReferenceAgentCategory } from "@/lib/reference-replica-data";

import {
  buildReplicaLocalGateNotice,
  ReplicaEmptyState,
  ReplicaFilterButton,
  ReplicaNotice,
  ReplicaPageHeader
} from "./replica-page-kit";

type ReplicaAgentDirectoryProps = {
  readonly mode: "mine" | "market";
};

type AgentFilter = "全部" | ReferenceAgentCategory;
type AgentAction = "查看详情" | "编辑" | "历史版本" | "删除" | "创建副本" | "立即使用" | "配置知识" | "查看调用" | "收藏";
type AgentActionPanel = {
  readonly title: string;
  readonly description: string;
  readonly items: readonly string[];
};

const allAgentsFilter = "全部";
const marketCategoryOrder = [
  "财务收支审计",
  "采购招标审计",
  "工程审计",
  "固定资产审计",
  "工具智能体",
  "审计科研"
] as const;
const mineActionPanels: Record<AgentAction, AgentActionPanel> = {
  查看详情: {
    title: "智能体概览",
    description: "展示该智能体适合处理的审计任务、材料范围和调用入口。",
    items: ["审计主题已识别", "知识库待确认", "可从 AI 对话调用"]
  },
  编辑: {
    title: "编辑智能体",
    description: "调整名称、说明、提示词和可见范围。",
    items: ["名称与说明", "审计提示词", "启用范围"]
  },
  历史版本: {
    title: "版本记录",
    description: "查看提示词版本、更新时间和适用范围。",
    items: ["v3 当前版本", "v2 已归档", "v1 初始版本"]
  },
  删除: {
    title: "停用确认",
    description: "停用前请确认该智能体不再被项目和对话调用。",
    items: ["先从项目解绑", "保留调用记录", "等待管理员确认"]
  },
  创建副本: {
    title: "创建副本",
    description: "从当前智能体生成一个个人可维护版本。",
    items: ["复制基础信息", "复用知识库", "重置调用统计"]
  },
  立即使用: {
    title: "使用路径",
    description: "进入 AI 对话或专题工作台后调用该智能体。",
    items: ["选择项目", "确认知识库", "开始审计对话"]
  },
  配置知识: {
    title: "知识配置",
    description: "绑定个人、系统或项目知识库，为回答提供依据。",
    items: ["医保基金合规知识库", "审计案例库", "项目材料库"]
  },
  查看调用: {
    title: "调用记录",
    description: "查看最近调用场景、产出类型和项目来源。",
    items: ["AI 对话 12 次", "底稿生成 3 次", "项目检索 7 次"]
  },
  收藏: {
    title: "收藏记录",
    description: "收藏后可更快找到常用智能体。",
    items: ["加入常用模板", "保留提示词", "等待后端收藏接口"]
  }
};

const marketActionPanels: Record<AgentAction, AgentActionPanel> = {
  查看详情: {
    title: "模板能力",
    description: "说明模板适合的审计任务、输入材料和输出形式。",
    items: ["支持政策依据提取", "支持风险线索归纳", "支持底稿片段生成"]
  },
  编辑: {
    title: "模板不可直接编辑",
    description: "广场模板需要先加入我的智能体，再维护个人版本。",
    items: ["先复制模板", "再绑定知识库", "再进入项目调用"]
  },
  历史版本: {
    title: "模板版本",
    description: "展示官方模板迭代记录，安装后由我的智能体维护版本。",
    items: ["官方模板", "审计场景适配", "安装后进入版本管理"]
  },
  删除: {
    title: "广场模板不可删除",
    description: "广场模板由系统维护，个人只管理已加入的智能体。",
    items: ["保留官方模板", "个人副本可停用", "操作需管理员"]
  },
  创建副本: {
    title: "加入我的智能体",
    description: "加入后可以在 AI 对话中通过 @ 或 / 调用。",
    items: ["生成个人副本", "保留模板能力", "写入智能体 store"]
  },
  立即使用: {
    title: "试用路径",
    description: "先加入我的智能体，再从 AI 对话选择调用。",
    items: ["创建副本", "选择项目", "进入 AI 对话"]
  },
  配置知识: {
    title: "接入知识",
    description: "安装后可绑定系统知识库和项目材料。",
    items: ["法律法规库", "医保基金合规知识库", "审计案例库"]
  },
  查看调用: {
    title: "广场统计",
    description: "当前只展示模板使用口径，不读取远端安装统计。",
    items: ["模板浏览", "副本创建", "项目接入"]
  },
  收藏: {
    title: "收藏模板",
    description: "收藏后可在广场中快速回访。",
    items: ["记录模板", "保留完整提示词", "后续同步个人收藏"]
  }
};

function matchesAgent(agent: ReferenceAgentCard, query: string, activeFilter: AgentFilter) {
  const normalizedQuery = query.trim().toLowerCase();
  const matchesFilter = activeFilter === "全部" || agent.category === activeFilter;
  const matchesQuery =
    normalizedQuery.length === 0 ||
    `${agent.name} ${agent.summary} ${agent.project} ${agent.topic}`.toLowerCase().includes(normalizedQuery);

  return matchesFilter && matchesQuery;
}

function getCategoryRank(category: string): number {
  const index = marketCategoryOrder.indexOf(category as (typeof marketCategoryOrder)[number]);
  return index === -1 ? Number.MAX_SAFE_INTEGER : index;
}

function getAgentCategoryOptions(
  agents: readonly ReferenceAgentCard[],
  categories: readonly ReferenceAgentCategory[]
): readonly AgentFilter[] {
  const uniqueCategories = new Set<string>();
  for (const category of categories) {
    if (category) {
      uniqueCategories.add(category);
    }
  }
  for (const agent of agents) {
    if (agent.category) {
      uniqueCategories.add(agent.category);
    }
  }

  return [
    allAgentsFilter,
    ...Array.from(uniqueCategories).sort((left, right) => {
      const rankDelta = getCategoryRank(left) - getCategoryRank(right);
      return rankDelta === 0 ? left.localeCompare(right, "zh-Hans-CN") : rankDelta;
    })
  ];
}

function getCategoryCounts(agents: readonly ReferenceAgentCard[]): ReadonlyMap<string, number> {
  const counts = new Map<string, number>();
  for (const agent of agents) {
    counts.set(agent.category, (counts.get(agent.category) ?? 0) + 1);
  }
  return counts;
}

function estimateAgentPageSize(width: number, height: number): number {
  const columns = width >= 1360 ? 5 : width >= 1120 ? 4 : width >= 860 ? 3 : width >= 640 ? 2 : 1;
  const rows = Math.max(2, Math.min(4, Math.floor((height - 360) / 204)));
  return columns * rows;
}

function toApiAgentCategory(category: ReferenceAgentCategory): ApiAgentCategory {
  if (category === "工具智能体") {
    return "效率类";
  }
  if (category === "审计科研") {
    return "研究类";
  }
  return "业务类";
}

function DigitalHumanAvatar({
  agent,
  size = "default"
}: {
  readonly agent: ReferenceAgentCard;
  readonly size?: "default" | "large";
}) {
  return (
    <span
      className={`replica-digital-avatar tone-${agent.tone} ${size === "large" ? "is-large" : ""}`}
      aria-label={`${agent.name}数字人头像`}
      role="img"
      title={agent.name}
    >
      <span className="replica-digital-avatar-halo" />
      <span className="replica-digital-avatar-head" />
      <span className="replica-digital-avatar-face">
        <i />
        <i />
      </span>
      <span className="replica-digital-avatar-body" />
      <span className="replica-digital-avatar-chip" />
    </span>
  );
}

export function ReplicaAgentDirectory({ mode }: ReplicaAgentDirectoryProps) {
  const [query, setQuery] = useState("");
  const [activeFilter, setActiveFilter] = useState<AgentFilter>("全部");
  const [notice, setNotice] = useState("");
  const [selectedAgentId, setSelectedAgentId] = useState("");
  const [detailOpen, setDetailOpen] = useState(() => mode === "mine");
  const [activeAction, setActiveAction] = useState<AgentAction>("查看详情");
  const [installingAgentId, setInstallingAgentId] = useState("");
  const [installedAgentId, setInstalledAgentId] = useState("");
  const [favoriteAgentIds, setFavoriteAgentIds] = useState<Set<string>>(() => new Set());
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(15);
  const agentData = useReplicaAgentsData(mode);
  const sourceAgents = agentData.data.agents;
  const agentFilters = useMemo(
    () => getAgentCategoryOptions(sourceAgents, agentData.data.categories),
    [agentData.data.categories, sourceAgents]
  );
  const categoryCounts = useMemo(() => getCategoryCounts(sourceAgents), [sourceAgents]);
  const filteredAgents = useMemo(
    () => sourceAgents.filter((agent) => matchesAgent(agent, query, activeFilter)),
    [activeFilter, query, sourceAgents]
  );

  const isMine = mode === "mine";
  const pageCount = Math.max(1, Math.ceil(filteredAgents.length / pageSize));
  const safePage = Math.min(currentPage, pageCount);
  const pageStartIndex = (safePage - 1) * pageSize;
  const pageEndIndex = Math.min(filteredAgents.length, pageStartIndex + pageSize);
  const visibleAgents = filteredAgents.slice(pageStartIndex, pageEndIndex);
  const selectedAgent =
    sourceAgents.find((agent) => agent.id === selectedAgentId) ??
    visibleAgents[0] ??
    filteredAgents[0] ??
    sourceAgents[0];
  const actionPanel = (isMine ? mineActionPanels : marketActionPanels)[activeAction];
  const isSelectedAgentFavorite = selectedAgent ? favoriteAgentIds.has(selectedAgent.id) : false;

  useEffect(() => {
    if (agentFilters.includes(activeFilter)) {
      return;
    }
    setActiveFilter(allAgentsFilter);
  }, [activeFilter, agentFilters]);

  useEffect(() => {
    setCurrentPage(1);
  }, [activeFilter, pageSize, query]);

  useEffect(() => {
    setCurrentPage((page) => Math.min(page, pageCount));
  }, [pageCount]);

  useEffect(() => {
    function updatePageSize() {
      setPageSize(estimateAgentPageSize(window.innerWidth, window.innerHeight));
    }

    updatePageSize();
    window.addEventListener("resize", updatePageSize);
    return () => window.removeEventListener("resize", updatePageSize);
  }, []);

  function recordAction(agent: ReferenceAgentCard, action: AgentAction) {
    setSelectedAgentId(agent.id);
    setDetailOpen(true);
    setActiveAction(action);
    setNotice(buildReplicaLocalGateNotice({
      action: `${action}「${agent.name}」`,
      nextStep: isMine ? "智能体生命周期 API" : "智能体 clone/install API"
    }));
  }

  function openAgentDetail(agent: ReferenceAgentCard) {
    setSelectedAgentId(agent.id);
    setDetailOpen(true);
    setActiveAction("查看详情");
  }

  function toggleFavorite(agent: ReferenceAgentCard) {
    setSelectedAgentId(agent.id);
    setFavoriteAgentIds((previous) => {
      const next = new Set(previous);
      if (next.has(agent.id)) {
        next.delete(agent.id);
      } else {
        next.add(agent.id);
      }
      return next;
    });
    setNotice(favoriteAgentIds.has(agent.id)
      ? `已取消收藏「${agent.name}」。`
      : `已收藏「${agent.name}」，后续可接入个人收藏接口同步。`
    );
  }

  async function installMarketAgent(agent: ReferenceAgentCard) {
    setSelectedAgentId(agent.id);
    setDetailOpen(true);
    setActiveAction("创建副本");
    setInstallingAgentId(agent.id);
    setInstalledAgentId("");
    setNotice("");

    try {
      const response = await createAuditAgent({
        name: agent.name,
        category: toApiAgentCategory(agent.category),
        topic: agent.topic,
        prompt: buildMarketAgentPrompt(agent),
        knowledge_base: "医保基金合规知识库",
        project_name: DEFAULT_AUDIT_PROJECT_NAME,
        visibility_scope: "project",
        allowed_roles: ["admin", "technician", "director", "member"],
        metadata: {
          source: "agent-market",
          template_id: agent.id,
          template_original_category: agent.category,
          template_summary: agent.summary,
          template_project: agent.project,
          avatar_initial: agent.initial,
          avatar_tone: agent.tone,
          avatar_kind: "digital-human",
          template_key: agent.templateKey,
          template_source_file: agent.sourceFile
        }
      });
      setInstalledAgentId(response.item.id);
      setNotice(`已安装「${response.item.name}」到我的智能体，可在 AI 对话中通过 @ 或 /chat?agent=${response.item.id} 调用。`);
    } catch {
      setNotice("安装未完成：智能体创建接口暂不可用，请稍后重试。");
    } finally {
      setInstallingAgentId("");
    }
  }

  const activeScopeLabel = activeFilter === "全部" ? "全部分类" : activeFilter;
  const pageRangeLabel = filteredAgents.length === 0 ? "0 / 0" : `${pageStartIndex + 1}-${pageEndIndex} / ${filteredAgents.length}`;
  const pageDescription = isMine
    ? "管理审计工作中常用的个人智能体，可在 AI 对话和专题工作台中调用。"
    : "浏览可复用的审计智能体模板，按场景分类查看并加入我的智能体。";
  const pageTitle = isMine ? "我的智能体" : "智能体广场";

  return (
    <main
      className="replica-page"
      data-replica-source={agentData.source}
      data-replica-status={agentData.status}
    >
      <ReplicaPageHeader
        kicker={isMine ? "我的智能体" : "智能体广场"}
        title={pageTitle}
        description={pageDescription}
        actions={
          <button
            type="button"
            className="replica-primary-button"
            disabled={!isMine && selectedAgent ? installingAgentId === selectedAgent.id : false}
            onClick={() => {
              if (isMine || !selectedAgent) {
                setNotice(buildReplicaLocalGateNotice({
                  action: isMine ? "创建智能体" : "加入我的智能体",
                  nextStep: isMine ? "智能体创建 API" : "智能体市场安装 API"
                }));
                return;
              }
              void installMarketAgent(selectedAgent);
            }}
          >
            {isMine ? "+ 创建智能体" : installingAgentId === selectedAgent?.id ? "加入中" : "加入我的智能体"}
          </button>
        }
      />

      <section className="replica-panel">
        <div className="replica-toolbar">
          <label className="replica-search">
            <span aria-hidden="true">⌕</span>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={isMine ? "搜索我的智能体" : "搜索 AI 智能体"}
            />
          </label>
          <div className="replica-filter-group" aria-label="智能体分类">
            {agentFilters.map((filter) => (
              <ReplicaFilterButton key={filter} value={filter} activeValue={activeFilter} onSelect={setActiveFilter}>
                <span>{filter}</span>
                <em>{filter === allAgentsFilter ? sourceAgents.length : categoryCounts.get(filter) ?? 0}</em>
              </ReplicaFilterButton>
            ))}
          </div>
        </div>

        <div className="replica-directory-statebar" aria-label="智能体列表状态">
          <span>{activeScopeLabel}</span>
          <strong>{pageRangeLabel}</strong>
          <span>第 {safePage} / {pageCount} 页</span>
          <span>{isMine ? "可在 AI 对话调用" : "可加入我的智能体"}</span>
        </div>

        {notice && (
          <ReplicaNotice>
            {notice}
            {!isMine && installedAgentId ? (
              <Link className="replica-card-detail-button mt-3 inline-flex" href={`/chat?agent=${encodeURIComponent(installedAgentId)}`}>
                进入 AI 对话
              </Link>
            ) : null}
          </ReplicaNotice>
        )}

        {filteredAgents.length === 0 ? (
          <ReplicaEmptyState title="未找到智能体" description="调整关键词或分类后重试。" />
        ) : (
          <div className={`replica-agent-workbench ${isMine ? "is-mine-list" : "is-market-grid"}`}>
            <div className="replica-directory-grid">
              {visibleAgents.map((agent) => (
                <article
                  key={agent.id}
                  className={`replica-directory-card ${isMine ? "" : "is-market-card"} ${selectedAgent?.id === agent.id ? "is-selected" : ""}`}
                >
                  <DigitalHumanAvatar agent={agent} />
                  <div className="replica-directory-body">
                    <div className="replica-directory-title">
                      <h2>{agent.name}</h2>
                      <span>{agent.category}</span>
                    </div>
                    <p>{agent.summary}</p>
                    <dl className="replica-directory-meta">
                      <div>
                        <dt>关联项目</dt>
                        <dd>{agent.project}</dd>
                      </div>
                      <div>
                        <dt>审计主题</dt>
                        <dd>{agent.topic}</dd>
                      </div>
                    </dl>
                    <div className="replica-card-actions">
                      {isMine ? (
                        <>
                          <button
                            type="button"
                            aria-label={`查看详情：${agent.name}`}
                            onClick={() => recordAction(agent, "查看详情")}
                          >
                            查看详情
                          </button>
                          <button
                            type="button"
                            aria-label={`编辑：${agent.name}`}
                            onClick={() => recordAction(agent, "编辑")}
                          >
                            编辑
                          </button>
                          <button
                            type="button"
                            aria-label={`历史版本：${agent.name}`}
                            onClick={() => recordAction(agent, "历史版本")}
                          >
                            历史版本
                          </button>
                          <button
                            type="button"
                            aria-label={`删除：${agent.name}`}
                            onClick={() => recordAction(agent, "删除")}
                          >
                            删除
                          </button>
                        </>
                      ) : (
                        <button
                          type="button"
                          className="replica-card-detail-button"
                          aria-label={`详情：${agent.name}`}
                          onClick={() => openAgentDetail(agent)}
                        >
                          详情
                        </button>
                      )}
                    </div>
                  </div>
                </article>
              ))}
            </div>

            {pageCount > 1 ? (
              <nav className="replica-pagination" aria-label="智能体分页">
                <button type="button" disabled={safePage === 1} onClick={() => setCurrentPage((page) => Math.max(1, page - 1))}>
                  上一页
                </button>
                <span>每页 {pageSize} 个</span>
                <strong>{safePage} / {pageCount}</strong>
                <button type="button" disabled={safePage === pageCount} onClick={() => setCurrentPage((page) => Math.min(pageCount, page + 1))}>
                  下一页
                </button>
              </nav>
            ) : null}

            {isMine && selectedAgent && detailOpen ? (
              <aside className="replica-agent-detail" aria-label={isMine ? "我的智能体详情" : "智能体模板详情"}>
                <div className="replica-detail-head">
                  <span>{activeAction}</span>
                  <button type="button" aria-label="关闭智能体详情" onClick={() => setDetailOpen(false)}>×</button>
                </div>
                <DigitalHumanAvatar agent={selectedAgent} size="large" />
                <h2>{selectedAgent.name}</h2>
                <p>{selectedAgent.summary}</p>
                <dl>
                  <div>
                    <dt>分类</dt>
                    <dd>{selectedAgent.category}</dd>
                  </div>
                  <div>
                    <dt>主题</dt>
                    <dd>{selectedAgent.topic}</dd>
                  </div>
                  <div>
                    <dt>项目</dt>
                    <dd>{selectedAgent.project}</dd>
                  </div>
                </dl>
                <section className="replica-agent-next-panel" aria-label={isMine ? "智能体后续操作预览" : "模板安装后续预览"}>
                  <h3>{actionPanel.title}</h3>
                  <p>{actionPanel.description}</p>
                  <ul>
                    {actionPanel.items.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </section>
                <div className="replica-agent-detail-actions">
                  <button
                    type="button"
                    disabled={!isMine && installingAgentId === selectedAgent.id}
                    onClick={() => {
                      if (isMine) {
                        recordAction(selectedAgent, "立即使用");
                        return;
                      }
                      void installMarketAgent(selectedAgent);
                    }}
                  >
                    {isMine ? "立即使用" : installingAgentId === selectedAgent.id ? "安装中" : "创建副本"}
                  </button>
                  <button type="button" onClick={() => recordAction(selectedAgent, "配置知识")}>配置知识</button>
                  <button type="button" onClick={() => recordAction(selectedAgent, "查看调用")}>调用记录</button>
                </div>
              </aside>
            ) : null}
          </div>
        )}
      </section>

      {!isMine && selectedAgent && detailOpen ? (
        <div
          className="replica-agent-dialog-backdrop"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              setDetailOpen(false);
            }
          }}
        >
          <aside
            className="replica-agent-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="replica-agent-dialog-title"
          >
            <div className="replica-detail-head">
              <span>智能体详情</span>
              <button type="button" aria-label="关闭智能体详情" onClick={() => setDetailOpen(false)}>×</button>
            </div>
            <div className="replica-agent-dialog-head">
              <DigitalHumanAvatar agent={selectedAgent} size="large" />
              <div>
                <h2 id="replica-agent-dialog-title">{selectedAgent.name}</h2>
                <p>{selectedAgent.summary}</p>
              </div>
            </div>
            <dl className="replica-agent-dialog-meta">
              <div>
                <dt>分类</dt>
                <dd>{selectedAgent.category}</dd>
              </div>
              <div>
                <dt>主题</dt>
                <dd>{selectedAgent.topic}</dd>
              </div>
              <div>
                <dt>来源</dt>
                <dd>{selectedAgent.sourceFile || "提示词分类0613"}</dd>
              </div>
            </dl>
            <section className="replica-agent-prompt-panel" aria-label={`${selectedAgent.name}提示词`}>
              <h3>提示词</h3>
              <pre>{buildMarketAgentPrompt(selectedAgent)}</pre>
            </section>
            <div className="replica-agent-detail-actions is-dialog-actions">
              <button
                type="button"
                disabled={installingAgentId === selectedAgent.id}
                aria-label={`加入我的智能体：${selectedAgent.name}`}
                onClick={() => void installMarketAgent(selectedAgent)}
              >
                {installingAgentId === selectedAgent.id ? "安装中" : "加入我的智能体"}
              </button>
              {installedAgentId ? (
                <Link className="replica-card-detail-button" href={`/chat?agent=${encodeURIComponent(installedAgentId)}`}>
                  进入 AI 对话
                </Link>
              ) : null}
              <button type="button" aria-label={`收藏：${selectedAgent.name}`} onClick={() => toggleFavorite(selectedAgent)}>
                {isSelectedAgentFavorite ? "取消收藏" : "收藏"}
              </button>
            </div>
          </aside>
        </div>
      ) : null}
    </main>
  );
}

function buildMarketAgentPrompt(agent: ReferenceAgentCard): string {
  if (agent.prompt?.trim()) {
    return agent.prompt;
  }

  return [
    `你是「${agent.name}」，服务于「${agent.project}」。`,
    `审计主题：${agent.topic}。`,
    `能力摘要：${agent.summary}。`,
    "回答时必须先说明依据范围，只引用已接入知识库、项目材料和审计记录；若证据不足，应列出需要补充的材料清单，不直接下结论。",
    "输出应包含：风险判断、证据依据、待补材料、下一步建议。"
  ].join("\n");
}
