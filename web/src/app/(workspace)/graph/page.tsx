"use client";

import { useMemo, useState } from "react";

import {
  buildReplicaLocalGateNotice,
  ReplicaEmptyState,
  ReplicaFilterButton,
  ReplicaMetric,
  ReplicaNotice,
  ReplicaPageHeader
} from "@/components/replica/replica-page-kit";
import { useReplicaGraphData } from "@/components/replica/use-replica-runtime";
import type { ReferenceGraphNode } from "@/lib/reference-replica-data";

type GraphKind = "全部" | "项目" | "智能体" | "知识库" | "文档" | "银行" | "企业" | "政府机构" | "政策文件";

const graphKinds: readonly GraphKind[] = ["全部", "项目", "智能体", "知识库", "文档", "银行", "企业", "政府机构", "政策文件"];
const graphCards = [
  {
    id: "graph-card-village",
    title: "乡村振兴专项审计图谱",
    meta: "27 文档 / 110 实体 / 54 企业",
    status: "运行中",
    summary: "围绕资金拨付、建设运维、主管责任和项目材料形成审计关系链。"
  },
  {
    id: "graph-card-medical",
    title: "医保基金合规审计图谱",
    meta: "32 文档 / 86 实体 / 18 规则",
    status: "可扩展",
    summary: "面向医保基金支付、目录限制、智能监管规则和疑点整改的图谱模板。"
  }
] as const;
type GraphCardId = (typeof graphCards)[number]["id"];

export default function GraphPage() {
  const graphData = useReplicaGraphData();
  const graphNodes = graphData.data.nodes;
  const [query, setQuery] = useState("");
  const [activeKind, setActiveKind] = useState<GraphKind>("全部");
  const [notice, setNotice] = useState("");
  const [selectedGraphId, setSelectedGraphId] = useState<GraphCardId>(graphCards[0].id);
  const [selectedNodeId, setSelectedNodeId] = useState(graphNodes[0]?.id ?? "");
  const [detailOpen, setDetailOpen] = useState(true);
  const filteredNodes = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return graphNodes.filter((node) => {
      const kindMatched = activeKind === "全部" || node.kind === activeKind;
      const queryMatched =
        normalizedQuery.length === 0 ||
        `${node.label} ${node.kind} ${node.metric} ${node.status}`.toLowerCase().includes(normalizedQuery);
      return kindMatched && queryMatched;
    });
  }, [activeKind, graphNodes, query]);
  const selectedGraph = graphCards.find((card) => card.id === selectedGraphId) ?? graphCards[0];
  const selectedNode = graphNodes.find((node) => node.id === selectedNodeId) ?? graphNodes[0];

  function recordGraphAction(card: typeof graphCards[number], action: string) {
    setSelectedGraphId(card.id);
    setDetailOpen(true);
    setNotice(buildReplicaLocalGateNotice({
      action: `${action}「${card.title}」`,
      nextStep: "图谱详情 API"
    }));
  }

  function recordNodeAction(node: ReferenceGraphNode, action: string) {
    setSelectedNodeId(node.id);
    setDetailOpen(true);
    setNotice(buildReplicaLocalGateNotice({
      action: `${action}「${node.label}」`,
      nextStep: "图谱节点 API"
    }));
  }

  return (
    <main
      className="replica-page"
      data-replica-source={graphData.source}
      data-replica-status={graphData.status}
    >
      <ReplicaPageHeader
        kicker="AI知识图谱"
        title="知识图谱"
        description="围绕项目、智能体、知识库和审计材料展示节点关系，新增图谱保持本地门禁。"
        actions={
          <button type="button" className="replica-primary-button" onClick={() => setNotice(buildReplicaLocalGateNotice({
            action: "新建图谱",
            nextStep: "图谱创建 API"
          }))}>
            新建图谱
          </button>
        }
      />

      <section className="replica-metric-grid">
        <ReplicaMetric label="节点数" value={`${graphNodes.length}`} />
        <ReplicaMetric label="节点类型" value={`${graphKinds.length - 1}`} tone="green" />
        <ReplicaMetric label="关系链" value="11" tone="amber" />
        <ReplicaMetric label="状态" value="静态预览" tone="slate" />
      </section>

      <section className="replica-graph-card-row" aria-label="知识图谱列表">
        {graphCards.map((card) => (
          <button
            key={card.id}
            type="button"
            className={selectedGraph.id === card.id ? "is-selected" : ""}
            onClick={() => recordGraphAction(card, "打开")}
          >
            <span>{card.status}</span>
            <strong>{card.title}</strong>
            <em>{card.meta}</em>
          </button>
        ))}
      </section>

      {detailOpen ? (
        <section className="replica-graph-detail-strip" aria-label="图谱详情预览">
          <div>
            <span>{selectedGraph.status}</span>
            <h2>{selectedGraph.title}</h2>
            <p>{selectedGraph.summary}</p>
          </div>
          {selectedNode ? (
            <dl>
              <div>
                <dt>当前节点</dt>
                <dd>{selectedNode.label}</dd>
              </div>
              <div>
                <dt>节点类型</dt>
                <dd>{selectedNode.kind}</dd>
              </div>
              <div>
                <dt>状态</dt>
                <dd>{selectedNode.status}</dd>
              </div>
            </dl>
          ) : null}
          <div className="replica-graph-detail-actions">
            {selectedNode ? (
              <button type="button" onClick={() => recordNodeAction(selectedNode, "查看证据")}>查看证据</button>
            ) : null}
            <button type="button" onClick={() => setDetailOpen(false)} aria-label="关闭图谱详情">关闭</button>
          </div>
        </section>
      ) : null}

      <section className="replica-panel">
        {notice && <ReplicaNotice>{notice}</ReplicaNotice>}
        <div className="replica-toolbar">
          <label className="replica-search">
            <span aria-hidden="true">⌕</span>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="搜索知识图谱"
            />
          </label>
          <div className="replica-filter-group" aria-label="节点类型">
            {graphKinds.map((kind) => (
              <ReplicaFilterButton key={kind} value={kind} activeValue={activeKind} onSelect={setActiveKind}>
                {kind}
              </ReplicaFilterButton>
            ))}
          </div>
        </div>
        <div className="replica-statebar" aria-label="图谱筛选状态">
          <span>{activeKind === "全部" ? "全部节点" : activeKind}</span>
          <strong>{filteredNodes.length} / {graphNodes.length}</strong>
          <span>{query.trim() ? "关键词已应用" : "全量预览"}</span>
          <span>静态关系图</span>
        </div>
      </section>

      <section className="replica-graph-layout">
        <div className="replica-panel replica-graph-map" aria-label="知识图谱关系预览">
          <div className="replica-graph-map-summary">
            <strong>关系预览</strong>
            <span>节点位置为本地布局，不创建远端图谱。</span>
          </div>
          <div className="replica-graph-core" aria-hidden="true">
            <span>项目</span>
            <strong>乡村振兴专项审计</strong>
          </div>
          <div className="replica-graph-relation-label relation-a">引用</div>
          <div className="replica-graph-relation-label relation-b">关联</div>
          <div className="replica-graph-relation-label relation-c">资金链</div>
          <div className="replica-graph-line line-a" />
          <div className="replica-graph-line line-b" />
          <div className="replica-graph-line line-c" />
          {graphNodes.slice(0, 6).map((node, index) => (
            <button
              key={node.id}
              type="button"
              className={`replica-graph-node node-${index + 1} ${selectedNode?.id === node.id ? "is-selected" : ""}`}
              aria-label={`聚焦节点：${node.label}`}
              onClick={() => recordNodeAction(node, "聚焦节点")}
            >
              <span>{node.kind}</span>
              <strong>{node.label}</strong>
            </button>
          ))}
        </div>

        <div className="replica-panel">
          <div className="replica-results-head">
            <div>
              <p className="replica-kicker">节点类型</p>
              <h2>节点列表</h2>
            </div>
            <span>{filteredNodes.length} 个节点</span>
          </div>
          {filteredNodes.length === 0 ? (
            <ReplicaEmptyState title="暂无节点" description="调整图谱关键词或节点类型后重试。" />
          ) : (
            <div className="replica-node-list">
              {filteredNodes.map((node) => (
                <article key={node.id}>
                  <div>
                    <span>{node.kind}</span>
                    <h3>{node.label}</h3>
                  </div>
                  <p>{node.metric}</p>
                  <strong>{node.status}</strong>
                  <button type="button" onClick={() => recordNodeAction(node, "聚焦节点")}>聚焦</button>
                </article>
              ))}
            </div>
          )}
        </div>
      </section>
    </main>
  );
}
