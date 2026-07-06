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
import type { ReferenceGraphNode, ReferenceGraphRelation } from "@/lib/reference-replica-data";

type GraphKind = "全部" | string;

function matchesNode(node: ReferenceGraphNode, activeKind: GraphKind, query: string) {
  const normalizedQuery = query.trim().toLowerCase();
  const kindMatched = activeKind === "全部" || node.kind === activeKind;
  const queryMatched =
    normalizedQuery.length === 0 ||
    `${node.label} ${node.kind} ${node.metric} ${node.status}`.toLowerCase().includes(normalizedQuery);
  return kindMatched && queryMatched;
}

function matchesRelation(relation: ReferenceGraphRelation, query: string) {
  const normalizedQuery = query.trim().toLowerCase();
  if (!normalizedQuery) {
    return true;
  }
  return `${relation.source} ${relation.relation} ${relation.target} ${relation.evidence} ${relation.strength}`
    .toLowerCase()
    .includes(normalizedQuery);
}

export default function GraphPage() {
  const graphData = useReplicaGraphData();
  const { nodes, relations, metrics, title, scope } = graphData.data;
  const [query, setQuery] = useState("");
  const [activeKind, setActiveKind] = useState<GraphKind>("全部");
  const [notice, setNotice] = useState("");
  const [selectedNodeId, setSelectedNodeId] = useState(nodes[0]?.id ?? "");
  const [selectedRelationId, setSelectedRelationId] = useState(relations[0]?.id ?? "");
  const [detailOpen, setDetailOpen] = useState(true);

  const graphKinds = useMemo<readonly GraphKind[]>(
    () => ["全部", ...Array.from(new Set(nodes.map((node) => node.kind)))],
    [nodes]
  );
  const filteredNodes = useMemo(
    () => nodes.filter((node) => matchesNode(node, activeKind, query)),
    [activeKind, nodes, query]
  );
  const filteredRelations = useMemo(
    () => relations.filter((relation) => matchesRelation(relation, query)),
    [query, relations]
  );
  const selectedNode = nodes.find((node) => node.id === selectedNodeId) ?? filteredNodes[0] ?? nodes[0];
  const selectedRelation =
    relations.find((relation) => relation.id === selectedRelationId) ??
    filteredRelations[0] ??
    relations[0];

  function recordNodeAction(node: ReferenceGraphNode, action: string) {
    setSelectedNodeId(node.id);
    setDetailOpen(true);
    setNotice(buildReplicaLocalGateNotice({
      action: `${action}「${node.label}」`,
      nextStep: "图谱节点证据 API"
    }));
  }

  function recordRelationAction(relation: ReferenceGraphRelation, action: string) {
    setSelectedRelationId(relation.id);
    setDetailOpen(true);
    setNotice(buildReplicaLocalGateNotice({
      action: `${action}「${relation.source} -> ${relation.target}」`,
      nextStep: "图谱关系证据 API"
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
        description="以知识库、文档、规则、疑点和复核记录为基础，先做最小只读关系视图，不引入额外图数据库。"
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
        <ReplicaMetric label="节点数" value={`${metrics.nodeCount}`} />
        <ReplicaMetric label="节点类型" value={`${metrics.nodeKindCount}`} tone="green" />
        <ReplicaMetric label="关系链" value={`${metrics.relationCount}`} tone="amber" />
        <ReplicaMetric label="待补关系" value={`${metrics.pendingRelationCount}`} tone="slate" />
      </section>

      <section className="replica-graph-summary-card" aria-label="知识图谱方案概览">
        <div>
          <p className="replica-kicker">最小知识图谱方案</p>
          <h2>{title}</h2>
          <p>{scope}</p>
        </div>
        <dl>
          <div>
            <dt>数据来源</dt>
            <dd>{graphData.source === "api" ? "后端工作台" : "本地完整方案"}</dd>
          </div>
          <div>
            <dt>强关系</dt>
            <dd>{metrics.strongRelationCount}</dd>
          </div>
          <div>
            <dt>接入策略</dt>
            <dd>复用现有库表</dd>
          </div>
        </dl>
      </section>

      {detailOpen ? (
        <section className="replica-graph-detail-strip" aria-label="图谱详情预览">
          <div>
            <span>{selectedRelation?.strength ?? selectedNode?.status ?? "只读"}</span>
            <h2>{selectedRelation ? `${selectedRelation.source} -> ${selectedRelation.target}` : selectedNode?.label}</h2>
            <p>{selectedRelation?.evidence ?? selectedNode?.metric ?? "选择节点或关系后查看证据范围。"}</p>
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
              placeholder="搜索节点、关系或证据"
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
          <strong>{filteredNodes.length} / {nodes.length}</strong>
          <span>{filteredRelations.length} 条关系</span>
          <span>{query.trim() ? `关键词：${query.trim()}` : "全量关系视图"}</span>
        </div>
      </section>

      <section className="replica-graph-workbench">
        <article className="replica-graph-focus-card" aria-label="当前图谱焦点">
          <p className="replica-kicker">当前焦点</p>
          <h2>{selectedNode?.label ?? "暂无节点"}</h2>
          <p>{selectedNode ? `${selectedNode.kind}｜${selectedNode.metric}` : "等待后端返回图谱节点。"}</p>
          {selectedNode ? <strong>{selectedNode.status}</strong> : null}
        </article>

        <div className="replica-panel replica-graph-relation-panel">
          <div className="replica-results-head">
            <div>
              <p className="replica-kicker">关系链</p>
              <h2>证据关系</h2>
            </div>
            <span>{filteredRelations.length} 条</span>
          </div>
          {filteredRelations.length === 0 ? (
            <ReplicaEmptyState title="暂无关系" description="调整关键词后重试。" />
          ) : (
            <div className="replica-graph-relation-list">
              {filteredRelations.map((relation) => (
                <button
                  key={relation.id}
                  type="button"
                  className={selectedRelation?.id === relation.id ? "is-selected" : ""}
                  onClick={() => recordRelationAction(relation, "聚焦关系")}
                >
                  <span>{relation.strength}</span>
                  <strong>{relation.source}</strong>
                  <em>{relation.relation}</em>
                  <strong>{relation.target}</strong>
                  <p>{relation.evidence}</p>
                </button>
              ))}
            </div>
          )}
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
