"use client";

import { useMemo, useState } from "react";
import Link from "next/link";

import {
  buildReplicaLocalGateNotice,
  ReplicaEmptyState,
  ReplicaFilterButton,
  ReplicaMetric,
  ReplicaNotice,
  ReplicaPageHeader,
  ReplicaRuntimeBadge
} from "@/components/replica/replica-page-kit";
import { useReplicaKnowledgeBaseData } from "@/components/replica/use-replica-runtime";
import type { ReferenceKnowledgeBase } from "@/lib/reference-replica-data";

type KnowledgeGroup = "全部分类" | string;
type KnowledgeAction = "查看" | "创建知识库" | "打开目录" | "关联智能体" | "权限设置";
type KnowledgeActionPanel = {
  readonly title: string;
  readonly description: string;
  readonly rows: readonly {
    readonly label: string;
    readonly value: string;
  }[];
};

const knowledgeWorkflow = [
  { label: "归集材料", detail: "按来源和主题入库" },
  { label: "配置权限", detail: "区分个人、系统、项目" },
  { label: "服务智能体", detail: "为问答和审计提供依据" }
] as const;

const knowledgeActionPanels: Record<KnowledgeAction, KnowledgeActionPanel> = {
  查看: {
    title: "知识库概览",
    description: "展示当前知识库的材料范围、责任人和可调用状态。",
    rows: [
      { label: "目录", value: "按主题分层" },
      { label: "权限", value: "按角色读取" },
      { label: "状态", value: "本地预览" }
    ]
  },
  创建知识库: {
    title: "创建预览",
    description: "创建动作仅生成本地预览，正式写入需目录管理 API。",
    rows: [
      { label: "命名", value: "待填写" },
      { label: "来源", value: "待选择" },
      { label: "审批", value: "管理员确认" }
    ]
  },
  打开目录: {
    title: "目录预览",
    description: "按材料类型展示目录结构，不读取远端文档明细。",
    rows: [
      { label: "法规政策", value: "条款与政策" },
      { label: "项目材料", value: "台账与底稿" },
      { label: "风险线索", value: "疑点与清单" }
    ]
  },
  关联智能体: {
    title: "关联智能体",
    description: "将知识库绑定到审计助手，用于问答、检索和底稿生成。",
    rows: [
      { label: "推荐", value: "医保政策核验" },
      { label: "推荐", value: "政策依据速查" },
      { label: "推荐", value: "定标合规核验" }
    ]
  },
  权限设置: {
    title: "权限设置",
    description: "按角色控制可见范围，当前只显示本地权限草案。",
    rows: [
      { label: "管理员", value: "管理与授权" },
      { label: "主任", value: "复核与签发" },
      { label: "成员", value: "检索与引用" }
    ]
  }
};

function matchesKnowledgeBase(item: ReferenceKnowledgeBase, scope: KnowledgeGroup, query: string) {
  const normalizedQuery = query.trim().toLowerCase();
  const scopeMatched = scope === "全部分类" || item.tags.includes(scope) || item.scope === scope;
  const queryMatched =
    normalizedQuery.length === 0 ||
    `${item.name} ${item.scope} ${item.owner} ${item.description} ${item.tags.join(" ")}`.toLowerCase().includes(normalizedQuery);

  return scopeMatched && queryMatched;
}

export default function KnowledgeBasePage() {
  const [query, setQuery] = useState("");
  const [activeScope, setActiveScope] = useState<KnowledgeGroup>("全部分类");
  const [notice, setNotice] = useState("");
  const [selectedKnowledgeBaseId, setSelectedKnowledgeBaseId] = useState("");
  const [detailOpen, setDetailOpen] = useState(true);
  const [activeAction, setActiveAction] = useState<KnowledgeAction>("查看");
  const knowledgeBaseData = useReplicaKnowledgeBaseData();
  const knowledgeBases = knowledgeBaseData.data.knowledgeBases;
  const sourceGroups = knowledgeBaseData.data.sourceGroups;
  const knowledgeScopes: readonly KnowledgeGroup[] = useMemo(
    () => ["全部分类", ...sourceGroups.map((group) => group.title)],
    [sourceGroups]
  );
  const knowledgeHighlights = useMemo(
    () => sourceGroups.map((group) => ({
      label: group.title,
      value: `${group.options.length}`,
      detail: group.options.slice(0, 3).map((item) => item.label).join(" / ")
    })),
    [sourceGroups]
  );
  const filteredKnowledgeBases = useMemo(
    () => knowledgeBases.filter((item) => matchesKnowledgeBase(item, activeScope, query)),
    [activeScope, knowledgeBases, query]
  );
  const totalDocuments = knowledgeBases.reduce((sum, item) => sum + item.documentCount, 0);
  const totalApps = knowledgeBases.reduce((sum, item) => sum + item.appCount, 0);
  const selectedKnowledgeBase =
    knowledgeBases.find((item) => item.id === selectedKnowledgeBaseId) ??
    filteredKnowledgeBases[0] ??
    knowledgeBases[0];
  const actionPanel = knowledgeActionPanels[activeAction];

  function recordKnowledgeBaseAction(item: ReferenceKnowledgeBase, action: KnowledgeAction) {
    setSelectedKnowledgeBaseId(item.id);
    setDetailOpen(true);
    setActiveAction(action);
    setNotice(buildReplicaLocalGateNotice({
      action: `${action}「${item.name}」`,
      nextStep: "知识库目录读取 API"
    }));
  }

  return (
    <main
      className="replica-page"
      data-replica-source={knowledgeBaseData.source}
      data-replica-status={knowledgeBaseData.status}
    >
      <ReplicaPageHeader
        kicker="知识库"
        title="知识库分类"
        description="按一级专题和二级知识库组织当前项目材料，优先展示可被问答、检索和智能体调用的来源。"
        actions={
          <>
            <ReplicaRuntimeBadge
              source={knowledgeBaseData.source}
              status={knowledgeBaseData.status}
              issueCount={knowledgeBaseData.issues.length}
            />
            <button
              type="button"
              className="replica-secondary-button"
              onClick={() => setActiveScope("全部分类")}
            >
              全部分类
            </button>
            <button
              type="button"
	              className="replica-primary-button"
	              onClick={() => {
	                setActiveAction("创建知识库");
	                setDetailOpen(true);
	                setNotice(buildReplicaLocalGateNotice({
	                  action: "创建知识库",
	                  nextStep: "知识库目录写入 API"
	                }));
	              }}
	            >
              + 创建知识库
            </button>
          </>
        }
      />

      <section className="replica-metric-grid">
        <ReplicaMetric label="知识库" value={`${knowledgeBases.length}`} />
        <ReplicaMetric label="文档数" value={totalDocuments.toLocaleString()} tone="green" />
        <ReplicaMetric label="应用数" value={`${totalApps}`} tone="amber" />
        <ReplicaMetric label="一级分类" value={`${sourceGroups.length}`} tone="slate" />
      </section>

      <section className="replica-kb-overview-band" aria-label="知识来源概览">
        {knowledgeHighlights.map((item) => (
          <article key={item.label}>
            <span>{item.label}</span>
            <strong>{item.value}</strong>
            <p>{item.detail}</p>
          </article>
        ))}
      </section>

      <section className="replica-kb-workflow" aria-label="知识库工作流">
        {knowledgeWorkflow.map((item, index) => (
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
              placeholder="搜索知识库"
            />
          </label>
          <div className="replica-filter-group" aria-label="知识库一级分类">
            {knowledgeScopes.map((scope) => (
              <ReplicaFilterButton key={scope} value={scope} activeValue={activeScope} onSelect={setActiveScope}>
                {scope}
              </ReplicaFilterButton>
            ))}
          </div>
        </div>

        <div className="replica-statebar" aria-label="知识库列表状态">
          <span>{activeScope}</span>
          <strong>{filteredKnowledgeBases.length} / {knowledgeBases.length}</strong>
          <span>{query.trim() ? `关键词：${query.trim()}` : "全量目录"}</span>
          <span>{knowledgeBaseData.source === "fixture" ? "本地目录" : "生产目录"}</span>
        </div>

        {notice && <ReplicaNotice>{notice}</ReplicaNotice>}

        {filteredKnowledgeBases.length === 0 ? (
          <ReplicaEmptyState title="未找到知识库" description="调整关键词或知识库范围后重试。" />
        ) : (
          <div className="replica-kb-workbench">
            <div className="replica-kb-grid">
              {filteredKnowledgeBases.map((item) => (
                <article
                  key={item.id}
                  className={`replica-kb-card ${selectedKnowledgeBase?.id === item.id ? "is-selected" : ""}`}
                >
                  <div className="replica-kb-card-head">
                    <span>{item.scope}</span>
                    <button
                      type="button"
                      aria-label={`查看知识库：${item.name}`}
                      onClick={() => recordKnowledgeBaseAction(item, "查看")}
                    >
                      查看
                    </button>
                  </div>
                  <h2>{item.name}</h2>
                  <div className="replica-kb-owner">负责人：{item.owner}</div>
                  <p>{item.description}</p>
                  <div className="replica-kb-tags">
                    {item.tags.map((tag) => (
                      <span key={tag}>{tag}</span>
                    ))}
                  </div>
                  <dl className="replica-kb-stats">
                    <div>
                      <dt>文档数</dt>
                      <dd>{item.documentCount.toLocaleString()}</dd>
                    </div>
                    <div>
                      <dt>应用数</dt>
                      <dd>{item.appCount}</dd>
                    </div>
                    <div>
                      <dt>更新</dt>
                      <dd>{item.updatedAt}</dd>
                    </div>
                  </dl>
                </article>
              ))}
            </div>

            {selectedKnowledgeBase && detailOpen ? (
	              <aside className="replica-kb-detail" aria-label="知识库详情预览">
	                <div className="replica-detail-head">
	                  <span>{activeAction}</span>
	                  <button type="button" aria-label="关闭知识库详情" onClick={() => setDetailOpen(false)}>×</button>
	                </div>
	                <div className="replica-kb-scope-pill">{selectedKnowledgeBase.scope}</div>
	                <h2>{selectedKnowledgeBase.name}</h2>
	                <p>{selectedKnowledgeBase.description}</p>
                <dl>
                  <div>
                    <dt>负责人</dt>
                    <dd>{selectedKnowledgeBase.owner}</dd>
                  </div>
                  <div>
                    <dt>文档数</dt>
                    <dd>{selectedKnowledgeBase.documentCount.toLocaleString()}</dd>
                  </div>
                  <div>
                    <dt>应用数</dt>
                    <dd>{selectedKnowledgeBase.appCount}</dd>
                  </div>
                  <div>
                    <dt>更新日期</dt>
                    <dd>{selectedKnowledgeBase.updatedAt}</dd>
                  </div>
                </dl>
	                <div className="replica-kb-tags">
                  {selectedKnowledgeBase.tags.map((tag) => (
                    <span key={tag}>{tag}</span>
                  ))}
                </div>
	                <section className="replica-kb-next-panel" aria-label="知识库后续操作预览">
	                  <h3>{actionPanel.title}</h3>
	                  <p>{actionPanel.description}</p>
	                  <div>
	                    {actionPanel.rows.map((row) => (
	                      <article key={`${row.label}-${row.value}`}>
	                        <span>{row.label}</span>
	                        <strong>{row.value}</strong>
	                      </article>
	                    ))}
	                  </div>
	                </section>
	                <div className="replica-kb-detail-actions">
	                  {sourceCollectionFromKnowledgeBaseId(selectedKnowledgeBase.id) ? (
	                    <Link href={knowledgeBaseDocumentsHref(selectedKnowledgeBase)}>打开目录</Link>
	                  ) : (
	                    <button type="button" onClick={() => recordKnowledgeBaseAction(selectedKnowledgeBase, "打开目录")}>打开目录</button>
	                  )}
                  {sourceCollectionFromKnowledgeBaseId(selectedKnowledgeBase.id) ? (
                    <Link href={knowledgeBaseChatHref(selectedKnowledgeBase)}>关联智能体</Link>
                  ) : (
                    <button type="button" onClick={() => recordKnowledgeBaseAction(selectedKnowledgeBase, "关联智能体")}>关联智能体</button>
                  )}
                  <button type="button" onClick={() => recordKnowledgeBaseAction(selectedKnowledgeBase, "权限设置")}>权限设置</button>
                </div>
              </aside>
            ) : null}
          </div>
        )}
      </section>
    </main>
  );
}

function sourceCollectionFromKnowledgeBaseId(id: string): string | null {
  if (!id.startsWith("kb-")) {
    return null;
  }
  return id.slice("kb-".length);
}

function knowledgeBaseDocumentsHref(item: ReferenceKnowledgeBase): string {
  const sourceCollection = sourceCollectionFromKnowledgeBaseId(item.id);
  return sourceCollection ? `/documents?source_collection=${encodeURIComponent(sourceCollection)}` : "/documents";
}

function knowledgeBaseChatHref(item: ReferenceKnowledgeBase): string {
  const params = new URLSearchParams();
  params.set("question", `请基于「${item.name}」回答审计问题`);
  const sourceCollection = sourceCollectionFromKnowledgeBaseId(item.id);
  if (sourceCollection) {
    params.set("source_collection", sourceCollection);
  }
  return `/chat?${params.toString()}`;
}
