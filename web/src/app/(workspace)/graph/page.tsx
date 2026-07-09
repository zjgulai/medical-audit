"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

import {
  ReplicaEmptyState,
  ReplicaMetric,
  ReplicaNotice,
  ReplicaPageHeader,
  ReplicaRuntimeBadge
} from "@/components/replica/replica-page-kit";
import { useReplicaGraphData } from "@/components/replica/use-replica-runtime";
import type { SourceCollection } from "@/lib/api-types";
import type { ReferenceGraphNode } from "@/lib/reference-replica-data";
import {
  FALLBACK_SOURCE_COLLECTION_GROUPS,
  isSourceCollectionValue
} from "@/lib/source-collection-catalog";

const sourceCollectionLabelByValue = new Map<SourceCollection, string>(
  FALLBACK_SOURCE_COLLECTION_GROUPS.flatMap((group) =>
    group.options.map((option) => [option.value, option.label] as const)
  )
);

export default function GraphPage() {
  const graphData = useReplicaGraphData();
  const graph = graphData.data;
  const [selectedSourceCollections, setSelectedSourceCollections] = useState<readonly SourceCollection[]>([]);
  const [selectedNodeId, setSelectedNodeId] = useState("");
  const [selectedRelationId, setSelectedRelationId] = useState("");

  useEffect(() => {
    setSelectedSourceCollections(readSourceCollectionsFromLocation());
  }, []);

  const centerNode = graph.nodes[0];
  const displayNodes = useMemo(() => graph.nodes.filter((node) => node.id !== centerNode?.id).slice(0, 6), [centerNode?.id, graph.nodes]);
  const selectedNode = graph.nodes.find((node) => node.id === selectedNodeId) ?? centerNode ?? graph.nodes[0];
  const selectedRelation = graph.relations.find((relation) => relation.id === selectedRelationId) ?? graph.relations[0];
  const selectedNodeSources = sourceCollectionsForNode(selectedNode, selectedSourceCollections);
  const scopedLabel = selectedSourceCollections.length > 0
    ? selectedSourceCollections.map(sourceCollectionLabel).join("、")
    : "全部知识库";

  return (
    <main
      className="replica-page replica-page-standard"
      data-replica-source={graphData.source}
      data-replica-status={graphData.status}
    >
      <ReplicaPageHeader
        kicker="知识图谱"
        title="知识图谱"
        description="复用当前知识库目录、规则、疑点和报告工作台生成只读关系视图；先帮助审计人员看清来源、关系和下一步入口。"
        actions={
          <>
            <ReplicaRuntimeBadge
              source={graphData.source}
              status={graphData.status}
              hasSeedData={graphData.issues.some((issue) => issue.code === "backend-seed-data")}
              issueCount={graphData.issues.length}
            />
            <Link href={documentsHref(selectedSourceCollections)} className="replica-secondary-button">
              进入文档检索
            </Link>
          </>
        }
      />

      {graphData.issues.length > 0 ? (
        <ReplicaNotice>
          {graphData.issues.map((issue) => issue.message).join("；")}
        </ReplicaNotice>
      ) : null}

      <section className="replica-graph-summary-card" aria-label="图谱数据概览">
        <div>
          <p className="replica-kicker">当前范围：{scopedLabel}</p>
          <h2>{graph.title}</h2>
          <p>{graph.scope}</p>
        </div>
        <dl>
          <div>
            <dt>节点</dt>
            <dd>{graph.metrics.nodeCount.toLocaleString()} 个</dd>
          </div>
          <div>
            <dt>关系</dt>
            <dd>{graph.metrics.relationCount.toLocaleString()} 条</dd>
          </div>
          <div>
            <dt>强关系</dt>
            <dd>{graph.metrics.strongRelationCount.toLocaleString()} 条</dd>
          </div>
        </dl>
      </section>

      <section className="replica-metric-grid" aria-label="知识图谱指标">
        <ReplicaMetric label="节点类型" value={`${graph.metrics.nodeKindCount.toLocaleString()} 类`} tone="blue" />
        <ReplicaMetric label="待补关系" value={`${graph.metrics.pendingRelationCount.toLocaleString()} 条`} tone="amber" />
        <ReplicaMetric label="显示范围" value={scopedLabel} tone={selectedSourceCollections.length > 0 ? "green" : "slate"} />
      </section>

      {graph.nodes.length === 0 ? (
        <ReplicaEmptyState title="暂无图谱节点" description="当前后端未返回可展示的关系节点，请先完成知识库或规则工作台同步。" />
      ) : (
        <section className="replica-graph-workbench" aria-label="知识图谱工作台">
          <div className="replica-graph-focus-card" aria-label="节点详情">
            <span className="replica-kicker">选中节点</span>
            <h2>{selectedNode?.label ?? "未选择节点"}</h2>
            <p>{selectedNode?.description ?? "点击图谱节点查看来源、状态和可继续处理的入口。"}</p>
            <strong>{selectedNode?.kind ?? "节点"} · {selectedNode?.status ?? "待查看"}</strong>
            <dl className="replica-graph-detail-list">
              <div>
                <dt>指标</dt>
                <dd>{selectedNode?.metric ?? "未记录"}</dd>
              </div>
              <div>
                <dt>范围</dt>
                <dd>{selectedNodeSources.length > 0 ? selectedNodeSources.map(sourceCollectionLabel).join("、") : scopedLabel}</dd>
              </div>
            </dl>
            <div className="replica-graph-detail-actions">
              <Link href={selectedNode?.href ?? "/knowledge-base"}>打开来源</Link>
              <Link href={documentsHref(selectedNodeSources)}>进入文档检索</Link>
              <Link href={chatHref(selectedNode, selectedNodeSources)}>进入 AI 对话</Link>
            </div>
          </div>

          <div className="replica-graph-map" aria-label="图谱节点">
            <div className="replica-graph-map-summary">
              <strong>只读关系视图</strong>
              <span>点击节点后，右侧展示来源和下一步入口。</span>
            </div>
            {centerNode ? (
              <button
                type="button"
                className={`replica-graph-core ${selectedNode?.id === centerNode.id ? "is-selected" : ""}`}
                onClick={() => setSelectedNodeId(centerNode.id)}
              >
                <span>{centerNode.kind}</span>
                <strong>{centerNode.label}</strong>
              </button>
            ) : null}
            <div className="replica-graph-line line-a" />
            <div className="replica-graph-line line-b" />
            <div className="replica-graph-line line-c" />
            <span className="replica-graph-relation-label relation-a">组织</span>
            <span className="replica-graph-relation-label relation-b">包含</span>
            <span className="replica-graph-relation-label relation-c">引用</span>
            {displayNodes.map((node, index) => (
              <button
                key={node.id}
                type="button"
                className={`replica-graph-node node-${(index % 6) + 1} ${selectedNode?.id === node.id ? "is-selected" : ""}`}
                onClick={() => setSelectedNodeId(node.id)}
              >
                <span>{node.kind}</span>
                <strong>{node.label}</strong>
              </button>
            ))}
          </div>

          <aside className="replica-graph-relation-panel replica-graph-focus-card" aria-label="关系证据">
            <span className="replica-kicker">关系证据</span>
            <h2>{selectedRelation ? `${selectedRelation.source} ${selectedRelation.relation}` : "暂无关系"}</h2>
            <p>{selectedRelation?.evidence ?? "当前节点尚未形成可展示的关系证据。"}</p>
            <div className="replica-graph-relation-list">
              {graph.relations.slice(0, 8).map((relation) => (
                <button
                  key={relation.id}
                  type="button"
                  className={selectedRelation?.id === relation.id ? "is-selected" : ""}
                  onClick={() => {
                    setSelectedRelationId(relation.id);
                    const targetNode = graph.nodes.find((node) => node.id === relation.targetId);
                    if (targetNode) {
                      setSelectedNodeId(targetNode.id);
                    }
                  }}
                >
                  <span>{relation.strength}</span>
                  <strong>{relation.source} → {relation.target}</strong>
                  <em>{relation.relation}</em>
                  <p>{relation.evidence}</p>
                </button>
              ))}
            </div>
          </aside>
        </section>
      )}
    </main>
  );
}

function readSourceCollectionsFromLocation(): readonly SourceCollection[] {
  if (typeof window === "undefined") {
    return [];
  }
  const params = new URLSearchParams(window.location.search);
  return params
    .getAll("source_collection")
    .filter(isSourceCollectionValue);
}

function sourceCollectionLabel(sourceCollection: SourceCollection): string {
  return sourceCollectionLabelByValue.get(sourceCollection) ?? sourceCollection;
}

function sourceCollectionsForNode(
  node: ReferenceGraphNode | undefined,
  fallbackSources: readonly SourceCollection[]
): readonly SourceCollection[] {
  if (node?.sourceCollection && isSourceCollectionValue(node.sourceCollection)) {
    return [node.sourceCollection];
  }
  return fallbackSources;
}

function documentsHref(sourceCollections: readonly SourceCollection[]): string {
  if (sourceCollections.length === 0) {
    return "/documents";
  }
  const params = new URLSearchParams();
  for (const sourceCollection of sourceCollections) {
    params.append("source_collection", sourceCollection);
  }
  return `/documents?${params.toString()}`;
}

function chatHref(node: ReferenceGraphNode | undefined, sourceCollections: readonly SourceCollection[]): string {
  const params = new URLSearchParams();
  params.set("question", `请基于「${node?.label ?? "知识图谱"}」梳理关系和审计依据`);
  for (const sourceCollection of sourceCollections) {
    params.append("source_collection", sourceCollection);
  }
  return `/chat?${params.toString()}`;
}
