import { SearchBackendStatusPill } from "@/components/portal/search-backend-status-pill";
import { StatusPill } from "@/components/ui/status-pill";
import { graphNodes, graphRelations, GraphNode, GraphNodeKind, GraphRelation } from "@/lib/portal-data";

const graphNodeKindOrder: readonly GraphNodeKind[] = ["项目", "知识库", "文档", "规则", "疑点", "复核", "报告", "整改"];

const nodeById = new Map(graphNodes.map((node) => [node.id, node]));
const graphEdges = graphRelations.map((relation) => ({
  relation,
  source: getGraphNode(relation.sourceId),
  target: getGraphNode(relation.targetId)
}));

const kindStats = graphNodeKindOrder.map((kind) => ({
  kind,
  count: graphNodes.filter((node) => node.kind === kind).length
}));

const strongRelationCount = graphRelations.filter((relation) => relation.strength === "强").length;
const pendingRelationCount = graphRelations.filter((relation) => relation.strength === "待补").length;

export default function GraphPage() {
  return (
    <main className="grid min-w-0 items-start gap-4 xl:grid-cols-[17rem_minmax(0,1fr)_18rem]">
      <aside className="audit-panel-rail min-w-0 p-5">
        <h2 className="audit-section-title">节点覆盖</h2>
        <p className="audit-copy mt-2">按审计链路查看项目、知识、规则、疑点、复核和整改覆盖。</p>
        <div className="mt-3">
          <SearchBackendStatusPill />
        </div>
        <div className="mt-5 grid grid-cols-2 gap-2">
          {kindStats.map((item) => (
            <div key={item.kind} className="rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-white px-3 py-2">
              <p className="audit-meta font-semibold">{item.kind}</p>
              <p className="audit-metric-value-sm mt-1">{item.count}</p>
            </div>
          ))}
        </div>
      </aside>

      <section className="audit-panel min-w-0 p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="audit-kicker">知识图谱</p>
            <h1 className="audit-page-title">知识图谱入口</h1>
            <p className="audit-copy mt-2 max-w-3xl">
              医保基金使用合规专项自查的项目、知识、规则、疑点、复核、报告和整改关系预览。
            </p>
          </div>
          <StatusPill tone="info">首期只读</StatusPill>
        </div>

        <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <GraphMetric label="节点类型" value={`${kindStats.length} 类`} />
          <GraphMetric label="关系链路" value={`${graphRelations.length} 条`} />
          <GraphMetric label="强证据关系" value={`${strongRelationCount} 条`} />
          <GraphMetric label="待补关系" value={`${pendingRelationCount} 条`} />
        </div>

        <section className="audit-panel-muted mt-6 p-4" aria-labelledby="graph-preview-title">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 id="graph-preview-title" className="audit-section-title">
                医保基金使用合规专项图谱
              </h2>
              <p className="audit-meta mt-1">SELF-CHECK-FUND-20260607 · 证据链静态预览</p>
            </div>
            <StatusPill tone="success">证据链覆盖</StatusPill>
          </div>

          <div className="audit-table-shell mt-4 bg-white">
            <svg
              className="h-[32rem] w-full text-slate-700"
              role="img"
              aria-label="审计知识图谱静态关系预览"
              viewBox="0 0 920 500"
            >
              <defs>
                <marker id="graph-arrow" markerHeight="10" markerWidth="10" orient="auto" refX="8" refY="5">
                  <path d="M 0 0 L 10 5 L 0 10 z" className="fill-blue-400" />
                </marker>
              </defs>

              {graphEdges.map(({ relation, source, target }) => (
                <line
                  key={relation.id}
                  x1={source.x}
                  y1={source.y}
                  x2={target.x}
                  y2={target.y}
                  className={relation.strength === "待补" ? "stroke-amber-300" : "stroke-blue-300"}
                  markerEnd="url(#graph-arrow)"
                  strokeDasharray={relation.strength === "待补" ? "7 6" : undefined}
                  strokeLinecap="round"
                  strokeWidth="2"
                />
              ))}

              {graphNodes.map((node) => (
                <GraphSvgNode key={node.id} node={node} />
              ))}
            </svg>
          </div>
        </section>

        <section className="mt-6" aria-labelledby="graph-relations-title">
          <h2 id="graph-relations-title" className="audit-section-title">
            证据链关系
          </h2>
          <div className="mt-4 grid gap-3 lg:grid-cols-2">
            {graphRelations.map((relation) => (
              <RelationCard key={relation.id} relation={relation} />
            ))}
          </div>
        </section>
      </section>

      <aside className="min-w-0 space-y-4">
        <section className="audit-panel-rail p-5">
          <h2 className="audit-section-title">节点证据</h2>
          <div className="mt-4 space-y-3">
            {graphNodes.map((node) => (
              <a key={node.id} className="audit-focus-ring block rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-[var(--audit-surface-muted)] p-3 hover:bg-[var(--audit-primary-soft)]" href={node.href}>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="audit-compact-title">{node.label}</p>
                    <p className="audit-meta mt-1">
                      {node.kind} / {node.metric}
                    </p>
                  </div>
                  <StatusPill tone={getNodeStatusTone(node.status)}>{node.status}</StatusPill>
                </div>
              </a>
            ))}
          </div>
        </section>

        <a className="audit-focus-ring audit-callout block p-5" href="/documents">
          <p className="audit-kicker">文档检索</p>
          <h2 className="audit-section-title mt-2">核验证据来源</h2>
          <p className="audit-copy mt-2">图谱中的文档、知识库和引用材料继续由统一检索页承载。</p>
        </a>
      </aside>
    </main>
  );
}

function GraphMetric({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <div className="audit-panel-muted p-4">
      <p className="audit-label">{label}</p>
      <p className="audit-metric-value mt-2">{value}</p>
    </div>
  );
}

function GraphSvgNode({ node }: { readonly node: GraphNode }) {
  const style = graphNodeStyleByKind[node.kind];

  return (
    <g transform={`translate(${node.x} ${node.y})`}>
      <title>{`${node.kind}：${node.label}，${node.description}`}</title>
      <rect x="-68" y="-30" width="136" height="60" rx="15" className={`stroke-[1.5] ${style.rect}`} />
      <circle cx="-44" cy="-9" r="8" className={style.dot} />
      <text x="-28" y="-5" className="fill-slate-500 text-[11px] font-semibold">
        {node.kind}
      </text>
      <text x="0" y="16" textAnchor="middle" className="fill-slate-950 text-[13px] font-semibold">
        {node.label}
      </text>
    </g>
  );
}

function RelationCard({ relation }: { readonly relation: GraphRelation }) {
  return (
    <article className="audit-panel-muted p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="audit-compact-title">{relation.source}</p>
          <p className="audit-meta mt-1">{relation.evidence}</p>
        </div>
        <StatusPill tone={getRelationTone(relation.strength)}>{relation.strength}</StatusPill>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
        <span className="audit-chip audit-chip-info">{relation.relation}</span>
        <span className="font-semibold text-[var(--audit-ink)]">{relation.target}</span>
      </div>
    </article>
  );
}

function getGraphNode(id: string): GraphNode {
  const node = nodeById.get(id);

  if (!node) {
    throw new Error(`Missing graph node: ${id}`);
  }

  return node;
}

function getNodeStatusTone(status: GraphNode["status"]) {
  if (status === "可引用" || status === "已归集") {
    return "success";
  }

  if (status === "待复核" || status === "门禁中") {
    return "warning";
  }

  return "info";
}

function getRelationTone(strength: GraphRelation["strength"]) {
  if (strength === "强") {
    return "success";
  }

  if (strength === "中") {
    return "info";
  }

  return "warning";
}

const graphNodeStyleByKind: Record<GraphNodeKind, { readonly rect: string; readonly dot: string }> = {
  项目: {
    rect: "fill-blue-50 stroke-blue-200",
    dot: "fill-blue-600"
  },
  知识库: {
    rect: "fill-emerald-50 stroke-emerald-200",
    dot: "fill-emerald-600"
  },
  文档: {
    rect: "fill-cyan-50 stroke-cyan-200",
    dot: "fill-cyan-600"
  },
  规则: {
    rect: "fill-indigo-50 stroke-indigo-200",
    dot: "fill-indigo-600"
  },
  疑点: {
    rect: "fill-amber-50 stroke-amber-200",
    dot: "fill-amber-600"
  },
  复核: {
    rect: "fill-orange-50 stroke-orange-200",
    dot: "fill-orange-600"
  },
  报告: {
    rect: "fill-slate-50 stroke-slate-300",
    dot: "fill-slate-600"
  },
  整改: {
    rect: "fill-rose-50 stroke-rose-200",
    dot: "fill-rose-600"
  }
};
