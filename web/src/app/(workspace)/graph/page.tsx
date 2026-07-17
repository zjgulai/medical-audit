"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { KeyboardEvent as ReactKeyboardEvent } from "react";

import {
  ReplicaEmptyState,
  ReplicaMetric,
  ReplicaNotice,
  ReplicaPageHeader,
  ReplicaRuntimeBadge
} from "@/components/replica/replica-page-kit";
import { useAuditUser } from "@/components/shell/audit-user-context";
import { fetchGraphWorkbench, fetchProjects } from "@/lib/api-client";
import type { ProjectsResponse, SourceCollection } from "@/lib/api-types";
import type { AuditClientRole } from "@/lib/audit-user";
import {
  loadReplicaGraphData,
  type ReplicaAdapterResult,
  type ReplicaGraphData
} from "@/lib/replica-adapters";
import type { ReferenceGraphNode } from "@/lib/reference-replica-data";
import {
  FALLBACK_SOURCE_COLLECTION_GROUPS,
  isSourceCollectionValue
} from "@/lib/source-collection-catalog";

type GraphView = "knowledge" | "project";
type GraphLanePhase = "idle" | "loading" | "ready" | "empty" | "degraded" | "error";
type ProjectsLanePhase = "loading" | "ready" | "degraded" | "error";

type GraphLaneState = {
  readonly phase: GraphLanePhase;
  readonly result: ReplicaAdapterResult<ReplicaGraphData> | null;
  readonly role: AuditClientRole | null;
  readonly projectKey: string | null;
};

type ProjectsLaneState = {
  readonly phase: ProjectsLanePhase;
  readonly response: ProjectsResponse | null;
  readonly role: AuditClientRole | null;
};

type GraphSurfaceProps = {
  readonly view: GraphView;
  readonly lane: GraphLaneState;
  readonly selectedProjectKey: string;
  readonly sourceCollections: readonly SourceCollection[];
  readonly selectedNodeId: string;
  readonly selectedRelationId: string;
  readonly onSelectNode: (nodeId: string) => void;
  readonly onSelectRelation: (relationId: string, targetId: string) => void;
  readonly onRetry: () => void;
};

const countFormatter = new Intl.NumberFormat("zh-CN");
const sourceCollectionLabelByValue = new Map<SourceCollection, string>(
  FALLBACK_SOURCE_COLLECTION_GROUPS.flatMap((group) =>
    group.options.map((option) => [option.value, option.label] as const)
  )
);

function replicaApiReadsEnabled(): boolean {
  return process.env.NEXT_PUBLIC_MEDICAL_AUDIT_REPLICA_API_READS !== "0";
}

function idleGraphLane(role: AuditClientRole | null, projectKey: string | null = null): GraphLaneState {
  return { phase: "idle", result: null, role, projectKey };
}

function loadingGraphLane(role: AuditClientRole, projectKey: string | null): GraphLaneState {
  return { phase: "loading", result: null, role, projectKey };
}

function loadingProjectsLane(role: AuditClientRole | null): ProjectsLaneState {
  return { phase: "loading", response: null, role };
}

function graphLaneFromResult(
  role: AuditClientRole,
  projectKey: string | null,
  result: ReplicaAdapterResult<ReplicaGraphData>
): GraphLaneState {
  return { phase: result.outcome, result, role, projectKey };
}

function graphErrorMessage(lane: GraphLaneState, view: GraphView): string {
  const status = lane.result?.issues.find((issue) => issue.status !== undefined)?.status;
  if (view === "project" && status === 404) return "项目不可见或已不存在";
  if (view === "project" && status === 503) return "项目证据存储未就绪";
  return view === "project"
    ? "项目证据链读取失败，请稍后重试。"
    : "知识依据图谱读取失败，请稍后重试。";
}

function graphStoreLabel(store: ReplicaGraphData["store"]): string {
  const backend = store.backend;
  if (typeof backend === "string") return backend;
  return `${backend.audit_findings} / ${backend.review_tasks}`;
}

function GraphContextStrip({ graph }: { readonly graph: ReplicaGraphData }) {
  return (
    <section className="replica-graph-evidence-strip" aria-label="图谱证据边界">
      <div>
        <span>视图</span>
        <strong>{graph.view === "knowledge" ? "知识依据" : "项目证据链"}</strong>
      </div>
      <div>
        <span>项目范围</span>
        <strong translate="no">{graph.projectKey ?? "不适用"}</strong>
      </div>
      <div>
        <span>证据等级</span>
        <strong translate="no">{graph.evidenceGrade}</strong>
      </div>
      <div>
        <span>证据链状态</span>
        <strong translate="no">{graph.evidenceChainStatus}</strong>
      </div>
      <div>
        <span>存储后端</span>
        <strong translate="no">{graphStoreLabel(graph.store)}</strong>
      </div>
      <div>
        <span>生产副作用</span>
        <strong translate="no">{graph.productionSideEffect}</strong>
      </div>
    </section>
  );
}

function GraphSurface({
  view,
  lane,
  selectedProjectKey,
  sourceCollections,
  selectedNodeId,
  selectedRelationId,
  onSelectNode,
  onSelectRelation,
  onRetry
}: GraphSurfaceProps) {
  if (view === "project" && !selectedProjectKey) {
    return (
      <ReplicaEmptyState
        title="请先选择一个可见项目"
        description="项目证据链不会自动选取默认项目；请选择当前身份可见的项目后再读取。"
      />
    );
  }
  if (lane.phase === "idle" || lane.phase === "loading") {
    return <p className="replica-graph-state" role="status">正在读取图谱…</p>;
  }
  if (lane.phase === "error") {
    return (
      <section className="replica-graph-state is-error" role="alert">
        <strong>{graphErrorMessage(lane, view)}</strong>
        <span>未使用静态图谱替代当前请求。</span>
        <button type="button" onClick={onRetry}>重试当前视图</button>
      </section>
    );
  }

  const result = lane.result;
  if (result === null) {
    return null;
  }
  const graph = result.data;
  if (lane.phase === "degraded") {
    return (
      <>
        <GraphContextStrip graph={graph} />
        <section className="replica-graph-state is-degraded" role="status">
          <strong>{view === "project" ? "项目证据存储尚未就绪" : "知识图谱数据源处于降级状态"}</strong>
          <span>当前不展示旧 fixture 或把降级数据标记为已就绪。</span>
          <button type="button" onClick={onRetry}>重试当前视图</button>
        </section>
      </>
    );
  }
  if (lane.phase === "empty") {
    return (
      <>
        <GraphContextStrip graph={graph} />
        <ReplicaEmptyState
          title={view === "project" ? "当前项目暂无证据链" : "暂无图谱节点"}
          description={view === "project"
            ? "该项目尚未形成持久化疑点、复核、报告或整改关系。"
            : "当前后端未返回可展示的知识关系节点。"}
        />
      </>
    );
  }

  return (
    <GraphReadySurface
      graph={graph}
      sourceCollections={view === "knowledge" ? sourceCollections : []}
      selectedNodeId={selectedNodeId}
      selectedRelationId={selectedRelationId}
      onSelectNode={onSelectNode}
      onSelectRelation={onSelectRelation}
    />
  );
}

function GraphReadySurface({
  graph,
  sourceCollections,
  selectedNodeId,
  selectedRelationId,
  onSelectNode,
  onSelectRelation
}: {
  readonly graph: ReplicaGraphData;
  readonly sourceCollections: readonly SourceCollection[];
  readonly selectedNodeId: string;
  readonly selectedRelationId: string;
  readonly onSelectNode: (nodeId: string) => void;
  readonly onSelectRelation: (relationId: string, targetId: string) => void;
}) {
  const centerNode = graph.nodes[0];
  const displayNodes = graph.nodes.filter((node) => node.id !== centerNode?.id);
  const selectedNode = graph.nodes.find((node) => node.id === selectedNodeId) ?? centerNode;
  const selectedRelation = graph.relations.find((relation) => relation.id === selectedRelationId) ?? graph.relations[0];
  const selectedNodeSources = graph.view === "knowledge"
    ? sourceCollectionsForNode(selectedNode, sourceCollections)
    : [];
  const scopedLabel = graph.view === "knowledge"
    ? sourceCollections.length > 0
      ? sourceCollections.map(sourceCollectionLabel).join("、")
      : "全部知识库"
    : graph.projectKey ?? "未选择项目";

  return (
    <>
      <GraphContextStrip graph={graph} />
      <section className="replica-graph-summary-card" aria-label="图谱数据概览">
        <div>
          <p className="replica-kicker">当前范围：{scopedLabel}</p>
          <h2>{graph.title}</h2>
          <p>{graph.scope}</p>
        </div>
        <dl>
          <div><dt>节点</dt><dd>{countFormatter.format(graph.metrics.nodeCount)} 个</dd></div>
          <div><dt>关系</dt><dd>{countFormatter.format(graph.metrics.relationCount)} 条</dd></div>
          <div><dt>强关系</dt><dd>{countFormatter.format(graph.metrics.strongRelationCount)} 条</dd></div>
        </dl>
      </section>

      <section className="replica-metric-grid" aria-label="知识图谱指标">
        <ReplicaMetric label="节点类型" value={`${countFormatter.format(graph.metrics.nodeKindCount)} 类`} tone="blue" />
        <ReplicaMetric label="待补关系" value={`${countFormatter.format(graph.metrics.pendingRelationCount)} 条`} tone="amber" />
        <ReplicaMetric label="显示范围" value={scopedLabel} tone={graph.view === "project" || sourceCollections.length > 0 ? "green" : "slate"} />
      </section>

      <section className="replica-graph-workbench" aria-label={graph.view === "knowledge" ? "知识依据图谱工作台" : "项目证据链工作台"}>
        <div className="replica-graph-focus-card" aria-label="节点详情">
          <span className="replica-kicker">选中节点</span>
          <h2>{selectedNode?.label ?? "未选择节点"}</h2>
          <p>{selectedNode?.description ?? "点击图谱节点查看状态和下一步入口。"}</p>
          <strong>{selectedNode?.kind ?? "节点"} · {selectedNode?.status ?? "待查看"}</strong>
          <dl className="replica-graph-detail-list">
            <div><dt>指标</dt><dd>{selectedNode?.metric ?? "未记录"}</dd></div>
            <div><dt>范围</dt><dd>{selectedNodeSources.length > 0 ? selectedNodeSources.map(sourceCollectionLabel).join("、") : scopedLabel}</dd></div>
          </dl>
          <div className="replica-graph-detail-actions">
            {selectedNode ? (
              <Link href={safeFrontendHref(selectedNode.href ?? projectHref(graph.projectKey))}>打开来源</Link>
            ) : null}
            {graph.view === "knowledge" ? (
              <>
                <Link href={documentsHref(selectedNodeSources)}>进入文档检索</Link>
                <Link href={chatHref(selectedNode, selectedNodeSources)}>进入 AI 对话</Link>
              </>
            ) : (
              <Link href={projectHref(graph.projectKey)}>进入项目管理</Link>
            )}
          </div>
        </div>

        <div className="replica-graph-map" aria-label="图谱节点">
          <div className="replica-graph-map-summary">
            <strong>证据节点索引 · {graph.nodes.length} 个</strong>
            <span>完整展示响应节点；关系方向以右侧证据清单为准。</span>
          </div>
          {centerNode ? (
            <button
              type="button"
              className={`replica-graph-core ${selectedNode?.id === centerNode.id ? "is-selected" : ""}`}
              onClick={() => onSelectNode(centerNode.id)}
            >
              <span>{centerNode.kind}</span>
              <strong>{centerNode.label}</strong>
            </button>
          ) : null}
          {displayNodes.map((node) => (
            <button
              key={node.id}
              type="button"
              className={`replica-graph-node ${selectedNode?.id === node.id ? "is-selected" : ""}`}
              onClick={() => onSelectNode(node.id)}
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
            {graph.relations.map((relation) => (
              <button
                key={relation.id}
                type="button"
                className={selectedRelation?.id === relation.id ? "is-selected" : ""}
                onClick={() => onSelectRelation(relation.id, relation.targetId ?? "")}
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
    </>
  );
}

export default function GraphPage() {
  const auditUser = useAuditUser();
  const apiReadsEnabled = replicaApiReadsEnabled();
  const mountedRef = useRef(false);
  const roleGenerationRef = useRef(0);
  const projectGenerationRef = useRef(0);
  const selectedProjectKeyRef = useRef("");
  const knowledgeTabRef = useRef<HTMLButtonElement>(null);
  const projectTabRef = useRef<HTMLButtonElement>(null);
  const [activeView, setActiveView] = useState<GraphView>("knowledge");
  const [selectedProjectKey, setSelectedProjectKey] = useState("");
  const [selectedSourceCollections, setSelectedSourceCollections] = useState<readonly SourceCollection[]>([]);
  const [selectedNodeId, setSelectedNodeId] = useState("");
  const [selectedRelationId, setSelectedRelationId] = useState("");
  const [projectContextNotice, setProjectContextNotice] = useState<string | null>(null);
  const [knowledgeLane, setKnowledgeLane] = useState<GraphLaneState>(() => idleGraphLane(null));
  const [projectLane, setProjectLane] = useState<GraphLaneState>(() => idleGraphLane(null));
  const [projectsLane, setProjectsLane] = useState<ProjectsLaneState>(() => loadingProjectsLane(null));

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    setSelectedSourceCollections(readSourceCollectionsFromLocation());
  }, []);

  const loadRoleContext = useCallback((role: AuditClientRole, resetInteraction: boolean) => {
    const generation = ++roleGenerationRef.current;
    if (resetInteraction) {
      ++projectGenerationRef.current;
      selectedProjectKeyRef.current = "";
      setActiveView("knowledge");
      setSelectedProjectKey("");
      setProjectLane(idleGraphLane(role));
      setSelectedNodeId("");
      setSelectedRelationId("");
      setProjectContextNotice(null);
    }
    setKnowledgeLane(loadingGraphLane(role, null));
    setProjectsLane(loadingProjectsLane(role));

    const knowledgeRequest = loadReplicaGraphData(
      apiReadsEnabled ? { fetchGraphWorkbench } : {}
    );
    const projectsRequest = apiReadsEnabled ? fetchProjects() : null;

    void knowledgeRequest.then((result) => {
      if (!mountedRef.current || generation !== roleGenerationRef.current) return;
      setKnowledgeLane(graphLaneFromResult(role, null, result));
    });

    if (projectsRequest === null) {
      setProjectsLane({ phase: "error", response: null, role });
      return;
    }
    void projectsRequest
      .then((response) => {
        if (!mountedRef.current || generation !== roleGenerationRef.current) return;
        setProjectsLane({
          phase: response.store.ready ? "ready" : "degraded",
          response,
          role
        });
        const selectedKey = selectedProjectKeyRef.current;
        if (selectedKey && !response.items.some((project) => project.id === selectedKey)) {
          ++projectGenerationRef.current;
          selectedProjectKeyRef.current = "";
          setSelectedProjectKey("");
          setProjectLane(idleGraphLane(role));
          setSelectedNodeId("");
          setSelectedRelationId("");
          setProjectContextNotice("原项目已不可见，请重新选择");
        }
      })
      .catch(() => {
        if (mountedRef.current && generation === roleGenerationRef.current) {
          setProjectsLane({ phase: "error", response: null, role });
        }
      });
  }, [apiReadsEnabled]);

  const loadProjectGraph = useCallback((role: AuditClientRole, projectKey: string) => {
    const normalizedKey = projectKey.trim();
    if (!normalizedKey) return;
    const projectGeneration = ++projectGenerationRef.current;
    const roleGeneration = roleGenerationRef.current;
    setProjectLane(loadingGraphLane(role, normalizedKey));
    const request = loadReplicaGraphData(
      apiReadsEnabled ? { fetchGraphWorkbench } : {},
      { view: "project", projectKey: normalizedKey }
    );
    void request.then((result) => {
      if (
        !mountedRef.current ||
        projectGeneration !== projectGenerationRef.current ||
        roleGeneration !== roleGenerationRef.current ||
        selectedProjectKeyRef.current !== normalizedKey
      ) return;
      setProjectLane(graphLaneFromResult(role, normalizedKey, result));
    });
  }, [apiReadsEnabled]);

  useEffect(() => {
    loadRoleContext(auditUser.role, true);
  }, [auditUser.role, loadRoleContext]);

  const roleKnowledgeLane = knowledgeLane.role === auditUser.role
    ? knowledgeLane
    : loadingGraphLane(auditUser.role, null);
  const roleProjectsLane = projectsLane.role === auditUser.role
    ? projectsLane
    : loadingProjectsLane(auditUser.role);
  const roleProjectLane = projectLane.role === auditUser.role && projectLane.projectKey === selectedProjectKey
    ? projectLane
    : idleGraphLane(auditUser.role, selectedProjectKey || null);
  const projects = roleProjectsLane.phase === "ready" ? roleProjectsLane.response?.items ?? [] : [];
  const selectedProjectVisible = selectedProjectKey.length > 0 && projects.some((project) => project.id === selectedProjectKey);
  const currentLane = activeView === "knowledge" ? roleKnowledgeLane : roleProjectLane;
  const currentResult = currentLane.result;
  const runtimeStatus = currentLane.phase === "idle" ? "empty" : currentLane.phase;

  const sourceScopeLabel = useMemo(() => (
    selectedSourceCollections.length > 0
      ? selectedSourceCollections.map(sourceCollectionLabel).join("、")
      : "全部知识库"
  ), [selectedSourceCollections]);

  function changeView(nextView: GraphView): void {
    if (nextView === activeView) return;
    setActiveView(nextView);
    setSelectedNodeId("");
    setSelectedRelationId("");
    if (
      nextView === "project" &&
      selectedProjectVisible &&
      (roleProjectLane.phase === "idle" || roleProjectLane.phase === "error")
    ) {
      loadProjectGraph(auditUser.role, selectedProjectKey);
    }
  }

  function moveTabFocus(event: ReactKeyboardEvent<HTMLButtonElement>, currentView: GraphView): void {
    let nextView: GraphView | null = null;
    if (event.key === "ArrowRight" || event.key === "ArrowDown") {
      nextView = currentView === "knowledge" ? "project" : "knowledge";
    } else if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
      nextView = currentView === "knowledge" ? "project" : "knowledge";
    } else if (event.key === "Home") {
      nextView = "knowledge";
    } else if (event.key === "End") {
      nextView = "project";
    }
    if (nextView === null) return;
    event.preventDefault();
    changeView(nextView);
    (nextView === "knowledge" ? knowledgeTabRef : projectTabRef).current?.focus();
  }

  function changeProject(projectKey: string): void {
    if (projectKey === selectedProjectKey) return;
    ++projectGenerationRef.current;
    selectedProjectKeyRef.current = projectKey;
    setSelectedProjectKey(projectKey);
    setProjectLane(idleGraphLane(auditUser.role, projectKey || null));
    setSelectedNodeId("");
    setSelectedRelationId("");
    setProjectContextNotice(null);
    if (activeView === "project" && projectKey) {
      loadProjectGraph(auditUser.role, projectKey);
    }
  }

  function retryCurrentView(): void {
    if (activeView === "knowledge") {
      loadRoleContext(auditUser.role, false);
      return;
    }
    if (selectedProjectVisible) loadProjectGraph(auditUser.role, selectedProjectKey);
  }

  function selectRelation(relationId: string, targetId: string): void {
    setSelectedRelationId(relationId);
    setSelectedNodeId(targetId);
  }

  return (
    <main
      className="replica-page replica-page-standard replica-graph-dual-view"
      data-replica-source={currentResult?.source ?? "api"}
      data-replica-status={runtimeStatus}
    >
      <ReplicaPageHeader
        kicker="审计关系工作台"
        title="知识依据与项目证据链"
        description="知识依据保持来源范围，项目证据链只读取所选可见项目的持久化疑点、复核、报告与整改关系。"
        actions={
          <>
            <ReplicaRuntimeBadge
              source={currentResult?.source ?? "api"}
              status={runtimeStatus}
              hasSeedData={currentResult?.issues.some((issue) => issue.code === "backend-seed-data") ?? false}
              issueCount={currentResult?.issues.length ?? 0}
            />
            {activeView === "knowledge" ? (
              <Link href={documentsHref(selectedSourceCollections)} className="replica-secondary-button">
                进入文档检索
              </Link>
            ) : selectedProjectVisible ? (
              <Link href={projectHref(selectedProjectKey)} className="replica-secondary-button">
                进入项目管理
              </Link>
            ) : (
              <span className="replica-secondary-button is-disabled" aria-disabled="true">
                选择项目后进入
              </span>
            )}
          </>
        }
      />

      <section className="replica-graph-view-control" aria-label="图谱视图控制">
        <div className="replica-graph-tabs" role="tablist" aria-label="图谱视图">
          <button
            ref={knowledgeTabRef}
            id="graph-tab-knowledge"
            type="button"
            role="tab"
            aria-controls="graph-panel-knowledge"
            aria-selected={activeView === "knowledge"}
            tabIndex={activeView === "knowledge" ? 0 : -1}
            onClick={() => changeView("knowledge")}
            onKeyDown={(event) => moveTabFocus(event, "knowledge")}
          >
            <span aria-hidden="true">01</span>
            知识依据
          </button>
          <button
            ref={projectTabRef}
            id="graph-tab-project"
            type="button"
            role="tab"
            aria-controls="graph-panel-project"
            aria-selected={activeView === "project"}
            tabIndex={activeView === "project" ? 0 : -1}
            onClick={() => changeView("project")}
            onKeyDown={(event) => moveTabFocus(event, "project")}
          >
            <span aria-hidden="true">02</span>
            项目证据链
          </button>
        </div>
        <label className="replica-graph-project-select" htmlFor="graph-project-key">
          <span>证据链所属项目</span>
          <select
            id="graph-project-key"
            name="graph-project-key"
            aria-label="证据链所属项目"
            autoComplete="off"
            disabled={roleProjectsLane.phase !== "ready"}
            value={selectedProjectVisible ? selectedProjectKey : ""}
            onChange={(event) => changeProject(event.target.value)}
          >
            <option value="">请选择可见项目</option>
            {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
          </select>
        </label>
        <span className="replica-graph-flow-note" aria-disabled="true">
          业务流程图谱：等待医院流程输入
        </span>
      </section>

      <div className="replica-graph-context-status" aria-live="polite">
        <span>知识范围：{sourceScopeLabel}</span>
        {roleProjectsLane.phase === "loading" ? <span>正在读取可见项目…</span> : null}
        {roleProjectsLane.phase === "error" ? <span role="alert">项目列表读取失败，仅知识依据可用。</span> : null}
        {roleProjectsLane.phase === "degraded" ? <span role="status">项目目录存储未就绪。</span> : null}
        {roleProjectsLane.phase === "ready" && projects.length === 0 ? <span>当前没有可见项目。</span> : null}
        {projectContextNotice ? <span role="status">{projectContextNotice}</span> : null}
        <button type="button" onClick={() => loadRoleContext(auditUser.role, false)}>刷新知识与项目目录</button>
      </div>

      {currentResult && currentResult.issues.length > 0 ? (
        <ReplicaNotice>
          当前图谱数据未完全就绪，页面不会使用旧样例替代本次请求。
          <details className="replica-runtime-diagnostics">
            <summary>查看读取诊断</summary>
            <ul>
              {currentResult.issues.map((issue, index) => (
                <li key={`${issue.code}-${index}`}><code>{issue.message}</code></li>
              ))}
            </ul>
          </details>
        </ReplicaNotice>
      ) : null}

      <section
        id={`graph-panel-${activeView}`}
        role="tabpanel"
        aria-labelledby={`graph-tab-${activeView}`}
        tabIndex={0}
      >
        <GraphSurface
          view={activeView}
          lane={currentLane}
          selectedProjectKey={selectedProjectVisible ? selectedProjectKey : ""}
          sourceCollections={selectedSourceCollections}
          selectedNodeId={selectedNodeId}
          selectedRelationId={selectedRelationId}
          onSelectNode={setSelectedNodeId}
          onSelectRelation={selectRelation}
          onRetry={retryCurrentView}
        />
      </section>
    </main>
  );
}

function readSourceCollectionsFromLocation(): readonly SourceCollection[] {
  if (typeof window === "undefined") return [];
  const params = new URLSearchParams(window.location.search);
  return params.getAll("source_collection").filter(isSourceCollectionValue);
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
  if (sourceCollections.length === 0) return "/documents";
  const params = new URLSearchParams();
  for (const sourceCollection of sourceCollections) params.append("source_collection", sourceCollection);
  return `/documents?${params.toString()}`;
}

function chatHref(node: ReferenceGraphNode | undefined, sourceCollections: readonly SourceCollection[]): string {
  const params = new URLSearchParams();
  params.set("question", `请基于「${node?.label ?? "知识图谱"}」梳理关系和审计依据`);
  for (const sourceCollection of sourceCollections) params.append("source_collection", sourceCollection);
  return `/chat?${params.toString()}`;
}

function projectHref(projectKey: string | null): string {
  if (!projectKey) return "/projects";
  const params = new URLSearchParams();
  params.set("project", projectKey);
  return `/projects?${params.toString()}`;
}

function safeFrontendHref(href: string): string {
  if (!href.startsWith("/") || href.startsWith("//")) return "/projects";
  return href;
}
