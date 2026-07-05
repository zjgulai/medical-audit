"use client";

import { useMemo, useState } from "react";

import { useReplicaAgentsData } from "./use-replica-runtime";
import type { ReferenceAgentCard, ReferenceAgentCategory } from "@/lib/reference-replica-data";

import {
  buildReplicaLocalGateNotice,
  ReplicaEmptyState,
  ReplicaFilterButton,
  ReplicaMetric,
  ReplicaNotice,
  ReplicaPageHeader
} from "./replica-page-kit";

type ReplicaAgentDirectoryProps = {
  readonly mode: "mine" | "market";
};

type AgentFilter = "全部" | ReferenceAgentCategory;
type AgentAction = "查看详情" | "编辑" | "历史版本" | "删除" | "创建副本" | "立即使用" | "配置知识" | "查看调用";
type AgentActionPanel = {
  readonly title: string;
  readonly description: string;
  readonly items: readonly string[];
};

const agentFilters: readonly AgentFilter[] = ["全部", "业务类", "效率类", "研究类"];
const minePathway = [
  { label: "选择助手", detail: "按审计主题筛选" },
  { label: "配置知识", detail: "关联项目和知识库" },
  { label: "进入审计", detail: "在对话或工作台调用" }
] as const;
const marketPathway = [
  { label: "发现模板", detail: "查看官方模板能力" },
  { label: "复制副本", detail: "进入我的智能体管理" },
  { label: "接入项目", detail: "绑定审计主题和知识库" }
] as const;

const mineActionPanels: Record<AgentAction, AgentActionPanel> = {
  查看详情: {
    title: "助手概览",
    description: "展示该助手的审计主题、适用材料和当前接入状态。",
    items: ["审计主题已识别", "知识库待确认", "可从 AI 对话调用"]
  },
  编辑: {
    title: "编辑预览",
    description: "编辑入口停留在本地，正式保存需接入智能体生命周期 API。",
    items: ["名称与说明", "审计提示词", "启用范围"]
  },
  历史版本: {
    title: "版本记录",
    description: "展示提示词版本和审核状态，不执行回滚或发布动作。",
    items: ["v3 当前版本", "v2 已归档", "v1 初始版本"]
  },
  删除: {
    title: "停用确认",
    description: "删除只生成本地预览，避免误停用正在演示的助手。",
    items: ["先从项目解绑", "保留调用记录", "等待管理员确认"]
  },
  创建副本: {
    title: "副本预览",
    description: "从当前助手生成个人副本，正式创建仍需后端接口。",
    items: ["复制基础信息", "复用知识库", "重置调用统计"]
  },
  立即使用: {
    title: "使用路径",
    description: "进入 AI 对话或专题工作台后调用该助手。",
    items: ["选择项目", "确认知识库", "开始审计对话"]
  },
  配置知识: {
    title: "知识配置",
    description: "绑定个人、系统或项目知识库，为回答提供依据。",
    items: ["医保基金合规知识库", "审计案例库", "项目材料库"]
  },
  查看调用: {
    title: "调用记录",
    description: "查看最近调用场景和产出类型，当前为本地摘要。",
    items: ["AI 对话 12 次", "底稿生成 3 次", "项目检索 7 次"]
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
    description: "广场模板需要先创建副本，再进入我的智能体维护。",
    items: ["先复制模板", "再绑定知识库", "再进入项目调用"]
  },
  历史版本: {
    title: "模板版本",
    description: "展示官方模板迭代记录，当前不读取远端版本库。",
    items: ["官方模板", "审计场景适配", "等待安装接口"]
  },
  删除: {
    title: "广场模板不可删除",
    description: "市场模板由系统维护，本地只展示不可删除的提示。",
    items: ["保留官方模板", "个人副本可停用", "操作需管理员"]
  },
  创建副本: {
    title: "复制副本",
    description: "将模板复制到我的智能体后再绑定项目和知识库。",
    items: ["生成个人副本", "保留模板能力", "等待安装 API"]
  },
  立即使用: {
    title: "试用路径",
    description: "先创建副本，再从 AI 对话选择该助手。",
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

export function ReplicaAgentDirectory({ mode }: ReplicaAgentDirectoryProps) {
  const [query, setQuery] = useState("");
  const [activeFilter, setActiveFilter] = useState<AgentFilter>("全部");
  const [notice, setNotice] = useState("");
  const [selectedAgentId, setSelectedAgentId] = useState("");
  const [detailOpen, setDetailOpen] = useState(true);
  const [activeAction, setActiveAction] = useState<AgentAction>("查看详情");
  const agentData = useReplicaAgentsData(mode);
  const sourceAgents = agentData.data.agents;
  const filteredAgents = useMemo(
    () => sourceAgents.filter((agent) => matchesAgent(agent, query, activeFilter)),
    [activeFilter, query, sourceAgents]
  );

  const isMine = mode === "mine";
  const selectedAgent =
    sourceAgents.find((agent) => agent.id === selectedAgentId) ??
    filteredAgents[0] ??
    sourceAgents[0];
  const pathway = isMine ? minePathway : marketPathway;
  const actionPanel = (isMine ? mineActionPanels : marketActionPanels)[activeAction];

  function recordAction(agent: ReferenceAgentCard, action: AgentAction) {
    setSelectedAgentId(agent.id);
    setDetailOpen(true);
    setActiveAction(action);
    setNotice(buildReplicaLocalGateNotice({
      action: `${action}「${agent.name}」`,
      nextStep: isMine ? "智能体生命周期 API" : "智能体 clone/install API"
    }));
  }

  const activeScopeLabel = activeFilter === "全部" ? "全部分类" : activeFilter;
  const pageDescription = isMine
    ? "管理审计工作中常用的个人智能体，所有编辑、删除和版本入口保持本地门禁。"
    : "浏览可复用的审计智能体模板，复制和安装入口保持本地副本态。";
  const pageTitle = isMine ? "我的助手" : "发现审计智能体";

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
            onClick={() => setNotice(buildReplicaLocalGateNotice({
              action: isMine ? "创建我的助手" : "复制到我的空间",
              nextStep: isMine ? "智能体创建 API" : "智能体市场安装 API"
            }))}
          >
            {isMine ? "+ 创建我的助手" : "复制到我的空间"}
          </button>
        }
      />

      <section className="replica-metric-grid">
        <ReplicaMetric label={isMine ? "我的助手" : "广场助手"} value={`${sourceAgents.length}`} />
        <ReplicaMetric label="业务类" value={`${sourceAgents.filter((agent) => agent.category === "业务类").length}`} tone="green" />
        <ReplicaMetric label="效率类" value={`${sourceAgents.filter((agent) => agent.category === "效率类").length}`} tone="amber" />
        <ReplicaMetric label="研究类" value={`${sourceAgents.filter((agent) => agent.category === "研究类").length}`} tone="slate" />
      </section>

      <section className="replica-agent-pathway" aria-label={isMine ? "我的智能体使用路径" : "智能体广场复制路径"}>
        {pathway.map((item, index) => (
          <article key={item.label}>
            <span>{String(index + 1).padStart(2, "0")}</span>
            <strong>{item.label}</strong>
            <p>{item.detail}</p>
          </article>
        ))}
      </section>

      <section className="replica-panel">
        <div className="replica-toolbar">
          <label className="replica-search">
            <span aria-hidden="true">⌕</span>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={isMine ? "搜索我的助手" : "搜索AI智能体"}
            />
          </label>
          <div className="replica-filter-group" aria-label="智能体分类">
            {agentFilters.map((filter) => (
              <ReplicaFilterButton key={filter} value={filter} activeValue={activeFilter} onSelect={setActiveFilter}>
                {filter}
              </ReplicaFilterButton>
            ))}
          </div>
        </div>

        <div className="replica-directory-statebar" aria-label="智能体列表状态">
          <span>{activeScopeLabel}</span>
          <strong>{filteredAgents.length} / {sourceAgents.length}</strong>
          <span>{isMine ? "本地管理门禁" : "本地复制门禁"}</span>
        </div>

        {notice && <ReplicaNotice>{notice}</ReplicaNotice>}

        {filteredAgents.length === 0 ? (
          <ReplicaEmptyState title="未找到智能体" description="调整关键词或分类后重试。" />
        ) : (
          <div className="replica-agent-workbench">
            <div className="replica-directory-grid">
              {filteredAgents.map((agent) => (
                <article
                  key={agent.id}
                  className={`replica-directory-card ${selectedAgent?.id === agent.id ? "is-selected" : ""}`}
                >
                  <div className={`replica-agent-initial tone-${agent.tone}`}>{agent.initial}</div>
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
                      <button
                        type="button"
                        aria-label={`查看详情：${agent.name}`}
                        onClick={() => recordAction(agent, "查看详情")}
                      >
                        查看详情
                      </button>
                      {isMine ? (
                        <>
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
                          aria-label={`创建副本：${agent.name}`}
                          onClick={() => recordAction(agent, "创建副本")}
                        >
                          创建副本
                        </button>
                      )}
                    </div>
                  </div>
                </article>
              ))}
            </div>

            {selectedAgent && detailOpen ? (
              <aside className="replica-agent-detail" aria-label={isMine ? "我的智能体详情" : "智能体模板详情"}>
                <div className="replica-detail-head">
                  <span>{activeAction}</span>
                  <button type="button" aria-label="关闭智能体详情" onClick={() => setDetailOpen(false)}>×</button>
                </div>
                <div className={`replica-agent-detail-icon tone-${selectedAgent.tone}`}>{selectedAgent.initial}</div>
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
                  <button type="button" onClick={() => recordAction(selectedAgent, isMine ? "立即使用" : "创建副本")}>
                    {isMine ? "立即使用" : "创建副本"}
                  </button>
                  <button type="button" onClick={() => recordAction(selectedAgent, "配置知识")}>配置知识</button>
                  <button type="button" onClick={() => recordAction(selectedAgent, "查看调用")}>调用记录</button>
                </div>
              </aside>
            ) : null}
          </div>
        )}
      </section>
    </main>
  );
}
