import type {
  AgentsResponse,
  AuditAgentApiItem,
  AuthSessionResponse,
  DocumentPermissionsResponse,
  DocumentSourceCollectionCatalogItem,
  DocumentSourceCollectionCatalogResponse,
  DocumentSearchResponse,
  GraphWorkbenchResponse,
  KnowledgeBaseCatalogResponse,
  ProjectsResponse,
  QueryHistoryResponse,
  ReportWorkbenchResponse,
  TableAnalysisUploadHistoryResponse
} from "./api-types";
import { getAuditAgentMarketCatalog } from "./audit-agent-catalog";
import {
  referenceAgents,
  referenceDocumentCategories,
  referenceDocumentResults,
  referenceGraphNodes,
  referenceGraphRelations,
  referenceHistoryItems,
  referenceKnowledgeBases,
  referenceNavigation,
  referenceProjects,
  referenceReportRecords,
  referenceSearchHistory
} from "./reference-replica-data";
import type {
  ReferenceAgentCard,
  ReferenceAgentCategory,
  ReferenceAnalysisDataset,
  ReferenceDocumentCategory,
  ReferenceDocumentResult,
  ReferenceGraphNode,
  ReferenceGraphRelation,
  ReferenceHistoryItem,
  ReferenceKnowledgeBase,
  ReferenceNavigationItem,
  ReferenceProject,
  ReferenceReportRecord
} from "./reference-replica-data";
import {
  FALLBACK_SOURCE_COLLECTION_GROUPS,
  sourceCollectionCatalogToGroups,
  type SourceCollectionGroup
} from "./source-collection-catalog";

type OptionalApiRead<T> =
  | { readonly kind: "disabled" }
  | { readonly kind: "success"; readonly value: T }
  | { readonly kind: "failure"; readonly message: string };

type ReplicaApiReadName =
  | "auth-session"
  | "query-history"
  | "agents"
  | "document-permissions"
  | "knowledge-base-catalog"
  | "document-source-collections"
  | "analysis-upload-history"
  | "graph-workbench"
  | "report-workbench"
  | "projects";

export type ReplicaDataSource = "fixture" | "catalog" | "api" | "hybrid";

export type ReplicaAdapterOutcome = "ready" | "empty" | "degraded" | "error";

export type ReplicaSurface =
  | "shell"
  | "chat"
  | "agents"
  | "agent-market"
  | "knowledge-base"
  | "documents"
  | "analytics"
  | "graph"
  | "reports"
  | "projects";

export type ReplicaAdapterIssueCode =
  | "api-read-failed"
  | "fixture-fallback"
  | "partial-schema-gap"
  | "backend-seed-data"
  | "catalog-api-needed"
  | "mutation-gated";

export type ReplicaAdapterIssue = {
  readonly surface: ReplicaSurface;
  readonly code: ReplicaAdapterIssueCode;
  readonly message: string;
  readonly status?: number;
};

export type ReplicaAdapterResult<TData> = {
  readonly source: ReplicaDataSource;
  readonly outcome: ReplicaAdapterOutcome;
  readonly data: TData;
  readonly issues: readonly ReplicaAdapterIssue[];
};

export type ReplicaShellUser = {
  readonly displayName: string;
  readonly avatarLabel: string;
  readonly roleLabel: string;
  readonly tenantLabel: string;
};

export type ReplicaShellData = {
  readonly navigation: readonly ReferenceNavigationItem[];
  readonly historyItems: readonly ReferenceHistoryItem[];
  readonly user: ReplicaShellUser;
};

export type ReplicaChatData = {
  readonly agents: readonly ReferenceAgentCard[];
  readonly historyItems: readonly ReferenceHistoryItem[];
  readonly documentResults: readonly ReferenceDocumentResult[];
};

export type ReplicaAgentsData = {
  readonly agents: readonly ReferenceAgentCard[];
  readonly categories: readonly ReferenceAgentCategory[];
};

export type ReplicaKnowledgeBaseItem = Omit<
  ReferenceKnowledgeBase,
  "documentCount" | "chunkCount" | "appCount"
> & {
  readonly documentCount: number | null;
  readonly chunkCount: number | null;
  readonly appCount: number | null;
};

export type ReplicaKnowledgeBaseSummary = {
  readonly sourceCollectionCount: number;
  readonly queryableCollectionCount: number;
  readonly totalDocumentCount: number | null;
  readonly totalChunkCount: number | null;
  readonly totalEmbeddingCount: number | null;
  readonly currentSearchEmbeddingCount: number | null;
  readonly candidateChunkCount: number | null;
  readonly domainCounts: Readonly<Record<string, number>>;
};

export type ReplicaKnowledgeBaseStore = {
  readonly ready: boolean;
  readonly catalogReady: boolean;
  readonly metricsReady: boolean;
  readonly backend: string;
};

export type ReplicaDocumentCategory = Omit<ReferenceDocumentCategory, "count"> & {
  readonly count: number | null;
};

export type ReplicaKnowledgeBaseBoundaries = {
  readonly productionWrite: false;
  readonly providerCall: false;
  readonly databaseWrite: false;
  readonly objectStorageWrite: false;
  readonly queryHistoryWrite: false;
  readonly source: KnowledgeBaseCatalogResponse["boundaries"]["source"];
};

export type ReplicaKnowledgeBaseData = {
  readonly knowledgeBases: readonly ReplicaKnowledgeBaseItem[];
  readonly sourceGroups: readonly SourceCollectionGroup[];
  readonly readableSourceCollections: readonly string[];
  readonly canUploadPersonal: boolean;
  readonly currentSearchEmbeddingCount: number | null;
  readonly metricsSource: "knowledge-base-catalog" | "unavailable";
  readonly summary: ReplicaKnowledgeBaseSummary | null;
  readonly store: ReplicaKnowledgeBaseStore | null;
  readonly boundaries: ReplicaKnowledgeBaseBoundaries | null;
};

export type ReplicaDocumentsData = {
  readonly categories: readonly ReplicaDocumentCategory[];
  readonly searchHistory: readonly string[];
  readonly results: readonly ReferenceDocumentResult[];
};

export type ReplicaAnalyticsData = {
  readonly datasets: readonly ReferenceAnalysisDataset[];
  readonly store: TableAnalysisUploadHistoryResponse["store"] | null;
};

export type ReplicaGraphData = {
  readonly view: "knowledge" | "project";
  readonly projectKey: string | null;
  readonly evidenceChainStatus: "catalog" | "ready" | "empty";
  readonly evidenceGrade: string;
  readonly productionSideEffect: "none";
  readonly store: GraphWorkbenchResponse["store"];
  readonly title: string;
  readonly scope: string;
  readonly nodes: readonly ReferenceGraphNode[];
  readonly relations: readonly ReferenceGraphRelation[];
  readonly metrics: {
    readonly nodeCount: number;
    readonly nodeKindCount: number;
    readonly relationCount: number;
    readonly strongRelationCount: number;
    readonly pendingRelationCount: number;
  };
};

export type ReplicaReportsData = {
  readonly records: readonly ReferenceReportRecord[];
};

export type ReplicaProjectsData = {
  readonly projects: readonly ReferenceProject[];
};

export type ReplicaShellClient = {
  readonly fetchAuthSession?: () => Promise<AuthSessionResponse>;
  readonly fetchQueryHistory?: () => Promise<QueryHistoryResponse>;
};

export type ReplicaAgentClient = {
  readonly fetchAgents?: () => Promise<AgentsResponse>;
};

export type ReplicaKnowledgeBaseClient = {
  readonly fetchDocumentPermissions?: () => Promise<DocumentPermissionsResponse>;
  readonly fetchDocumentSourceCollections?: () => Promise<DocumentSourceCollectionCatalogResponse>;
  readonly fetchKnowledgeBaseCatalog?: () => Promise<KnowledgeBaseCatalogResponse>;
};

export type ReplicaDocumentsClient = {
  readonly fetchDocumentSourceCollections?: () => Promise<DocumentSourceCollectionCatalogResponse>;
  readonly fetchKnowledgeBaseCatalog?: () => Promise<KnowledgeBaseCatalogResponse>;
  readonly searchDocuments?: (options: {
    readonly query: string;
    readonly sourceCollections?: readonly string[];
    readonly titleOnly?: boolean;
    readonly limit?: number;
  }) => Promise<DocumentSearchResponse>;
  readonly fetchQueryHistory?: () => Promise<QueryHistoryResponse>;
};

export type ReplicaAnalyticsClient = {
  readonly fetchAnalysisUploadHistory?: () => Promise<TableAnalysisUploadHistoryResponse>;
};

export type ReplicaGraphClient = {
  readonly fetchGraphWorkbench?: (options?: {
    readonly view?: "knowledge" | "project";
    readonly projectKey?: string;
  }) => Promise<GraphWorkbenchResponse>;
};

export type ReplicaReportsClient = {
  readonly fetchReportWorkbench?: () => Promise<ReportWorkbenchResponse>;
};

export type ReplicaProjectsClient = {
  readonly fetchProjects?: () => Promise<ProjectsResponse>;
};

export type ReplicaClient = ReplicaShellClient &
  ReplicaAgentClient &
  ReplicaKnowledgeBaseClient &
  ReplicaDocumentsClient &
  ReplicaAnalyticsClient &
  ReplicaGraphClient &
  ReplicaReportsClient &
  ReplicaProjectsClient;

const agentTones: readonly ReferenceAgentCard["tone"][] = ["rose", "blue", "cyan", "amber", "slate"];

function issue(
  surface: ReplicaSurface,
  code: ReplicaAdapterIssueCode,
  message: string
): ReplicaAdapterIssue {
  return { surface, code, message };
}

function isReadonlySeedBackend(backend: GraphWorkbenchResponse["store"]["backend"]): boolean {
  return typeof backend === "string" && backend.startsWith("Readonly") && backend.endsWith("Seed");
}

async function readOptionalApi<TResponse>(
  surface: ReplicaSurface,
  readName: ReplicaApiReadName,
  issues: ReplicaAdapterIssue[],
  read: (() => Promise<TResponse>) | undefined
): Promise<OptionalApiRead<TResponse>> {
  if (!read) {
    return { kind: "disabled" };
  }

  try {
    return { kind: "success", value: await read() };
  } catch (error) {
    const message = `API read ${readName} failed; no fixture data was substituted.`;
    const status = typeof error === "object" && error !== null && "status" in error &&
      typeof error.status === "number"
      ? error.status
      : undefined;
    issues.push({
      ...issue(surface, "api-read-failed", message),
      ...(status === undefined ? {} : { status })
    });
    return { kind: "failure", message };
  }
}

function hasApiFailure(reads: readonly OptionalApiRead<unknown>[]): boolean {
  return reads.some((read) => read.kind === "failure");
}

function allEnabledApiReadsFailed(reads: readonly OptionalApiRead<unknown>[]): boolean {
  return hasApiFailure(reads) && !reads.some((read) => read.kind === "success");
}

function allApiReadsDisabled(reads: readonly OptionalApiRead<unknown>[]): boolean {
  return reads.every((read) => read.kind === "disabled");
}

function normalizeText(value: string | null | undefined, fallback: string): string {
  const normalized = value?.replace(/\s+/g, " ").trim();
  return normalized && normalized.length > 0 ? normalized : fallback;
}

function compactText(value: string, maxLength: number): string {
  const normalized = value.replace(/\s+/g, " ").trim();
  if (normalized.length <= maxLength) {
    return normalized;
  }
  return `${normalized.slice(0, Math.max(0, maxLength - 3))}...`;
}

function formatDate(value: string | null | undefined, fallback = "未记录"): string {
  if (!value) {
    return fallback;
  }
  const datePrefix = value.match(/^\d{4}-\d{2}-\d{2}/)?.[0];
  return datePrefix ?? value;
}

export function formatReplicaDateTime(
  value: string | null | undefined,
  fallback = "未记录"
): string {
  if (!value) {
    return fallback;
  }
  const timestamp = Date.parse(value);
  if (Number.isNaN(timestamp)) {
    return value.replace("T", " ").replace(/Z$/, "").slice(0, 16);
  }
  const parts = new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23"
  }).formatToParts(new Date(timestamp));
  const part = (type: Intl.DateTimeFormatPartTypes) => (
    parts.find((item) => item.type === type)?.value ?? ""
  );
  return `${part("year")}-${part("month")}-${part("day")} ${part("hour")}:${part("minute")}`;
}

function metadataString(metadata: Record<string, unknown>, key: string): string | null {
  const value = metadata[key];
  return typeof value === "string" && value.trim().length > 0 ? value.trim() : null;
}

function makeInitial(name: string): string {
  const chars = Array.from(name.trim());
  if (chars.length === 0) {
    return "AI";
  }
  return chars.slice(0, Math.min(2, chars.length)).join("");
}

function toReferenceAgentCategory(category: string): ReferenceAgentCategory {
  return normalizeText(category, "业务类");
}

function mapQueryHistoryItems(history: QueryHistoryResponse): readonly ReferenceHistoryItem[] {
  return history.items.map((item, index) => ({
    id: item.id || `query-history-${index + 1}`,
    title: normalizeText(item.question, item.answer_summary ?? `查询记录 ${index + 1}`),
    summary: item.answer_summary ?? undefined,
    taskConvertible: history.store.ready && item.id.trim().length > 0
  }));
}

function mapSessionUser(session: AuthSessionResponse): ReplicaShellUser {
  const displayName = normalizeText(session.profile?.display_name, session.user_identifier || "审计员");
  return {
    displayName,
    avatarLabel: makeInitial(displayName),
    roleLabel: normalizeText(session.role_label, session.role),
    tenantLabel: normalizeText(session.tenant_id, "未绑定租户")
  };
}

function mapAgent(item: AuditAgentApiItem, index: number, projectFallback: string): ReferenceAgentCard {
  const summary =
    metadataString(item.metadata, "summary") ??
    metadataString(item.metadata, "description") ??
    compactText(item.prompt, 82);
  const project = normalizeText(item.project_name, projectFallback);

  return {
    id: item.id,
    name: item.name,
    category: toReferenceAgentCategory(item.category),
    summary,
    project,
    topic: normalizeText(item.topic, item.knowledge_base || "其他"),
    initial: makeInitial(item.name),
    tone: agentTones[index % agentTones.length]
  };
}

function mapDocumentCategoriesFromCatalog(
  items: readonly DocumentSourceCollectionCatalogItem[]
): readonly ReplicaDocumentCategory[] {
  return items
    .filter((item) => item.product_queryable || item.queryable)
    .map((item) => ({
      id: `source-${item.source_collection}`,
      name: item.label,
      description: item.description,
      count: item.metrics.document_count ?? null
    }));
}

function toKnowledgeBaseScope(scope: string): ReferenceKnowledgeBase["scope"] {
  if (scope === "个人知识库" || scope === "公开知识库" || scope === "系统知识库" || scope === "项目知识库") {
    return scope;
  }
  if (scope.includes("个人")) {
    return "个人知识库";
  }
  if (scope.includes("公开")) {
    return "公开知识库";
  }
  if (scope.includes("项目")) {
    return "项目知识库";
  }
  return "系统知识库";
}

function mapKnowledgeBasesFromSourceGroups(
  groups: readonly SourceCollectionGroup[],
  catalogItems: readonly DocumentSourceCollectionCatalogItem[] | null | undefined,
  metricsReady: boolean
): readonly ReplicaKnowledgeBaseItem[] {
  const itemBySource = new Map(
    (catalogItems ?? []).map((item) => [item.source_collection, item])
  );

  return groups.flatMap((group) =>
    group.options.map((option) => {
      const item = itemBySource.get(option.value);
      const documentCount = metricsReady ? item?.metrics.document_count ?? null : null;
      const chunkCount = metricsReady ? item?.metrics.chunk_count ?? null : null;
      const appCount = metricsReady ? item?.metrics.linked_app_count ?? null : null;
      return {
        id: `kb-${option.value}`,
        name: option.label,
        scope: toKnowledgeBaseScope(option.scope),
        owner: option.scope.includes("个人") ? "审计员" : "系统",
        documentCount,
        chunkCount,
        appCount,
        updatedAt: item?.phase ?? (option.queryable ? "可检索" : "待接入"),
        description: item?.audit_hint || option.description,
        tags: [
          group.title,
          option.queryable ? "可检索" : "待接入",
          item?.evidence_group || option.scope
        ].filter(Boolean)
      };
    })
  );
}

function mapKnowledgeBaseSummary(
  catalog: KnowledgeBaseCatalogResponse | null,
  metricsReady: boolean
): ReplicaKnowledgeBaseSummary | null {
  if (!catalog) {
    return null;
  }
  return {
    sourceCollectionCount: catalog.summary.source_collection_count,
    queryableCollectionCount: catalog.summary.queryable_collection_count,
    totalDocumentCount: metricsReady ? catalog.summary.total_document_count : null,
    totalChunkCount: metricsReady ? catalog.summary.total_chunk_count : null,
    totalEmbeddingCount: metricsReady ? catalog.summary.total_embedding_count : null,
    currentSearchEmbeddingCount: metricsReady
      ? catalog.summary.current_search_embedding_count
      : null,
    candidateChunkCount: metricsReady ? catalog.summary.candidate_chunk_count : null,
    domainCounts: catalog.summary.domain_counts
  };
}

function mapKnowledgeBaseStore(
  catalog: KnowledgeBaseCatalogResponse | null
): ReplicaKnowledgeBaseStore | null {
  if (!catalog) {
    return null;
  }
  return {
    ready: catalog.store.ready,
    catalogReady: catalog.store.catalog_ready,
    metricsReady: catalog.store.metrics_ready,
    backend: catalog.store.backend
  };
}

function mapKnowledgeBaseBoundaries(
  catalog: KnowledgeBaseCatalogResponse | null
): ReplicaKnowledgeBaseBoundaries | null {
  if (!catalog) {
    return null;
  }
  return {
    productionWrite: catalog.boundaries.production_write,
    providerCall: catalog.boundaries.provider_call,
    databaseWrite: catalog.boundaries.database_write,
    objectStorageWrite: catalog.boundaries.object_storage_write,
    queryHistoryWrite: catalog.boundaries.query_history_write,
    source: catalog.boundaries.source
  };
}

function mapAnalysisUploads(
  response: TableAnalysisUploadHistoryResponse
): readonly ReferenceAnalysisDataset[] {
  return response.items.map((item, index) => ({
    id: item.id || `analysis-upload-${index + 1}`,
    name: item.name,
    rows: item.row_count,
    columns: item.column_count,
    status: item.status === "parsed" ? "已解析" : item.status,
    insight:
      item.audit_signals[0] ??
      `已读取 ${item.row_count} 行、${item.column_count} 列，可进入本地字段画像。`
  }));
}

function graphDataFallback(): ReplicaGraphData {
  return {
    view: "knowledge",
    projectKey: null,
    evidenceChainStatus: "catalog",
    evidenceGrade: "fixture-catalog",
    productionSideEffect: "none",
    store: { ready: true, backend: "ReferenceGraphCatalog" },
    title: "审计知识图谱",
    scope: "项目、知识库、文档、规则与疑点的只读关系视图",
    nodes: referenceGraphNodes,
    relations: referenceGraphRelations,
    metrics: {
      nodeCount: referenceGraphNodes.length,
      nodeKindCount: new Set(referenceGraphNodes.map((node) => node.kind)).size,
      relationCount: referenceGraphRelations.length,
      strongRelationCount: referenceGraphRelations.filter((relation) => relation.strength === "强").length,
      pendingRelationCount: referenceGraphRelations.filter((relation) => relation.strength === "待补").length
    }
  };
}

function emptyGraphData(options: {
  readonly view?: "knowledge" | "project";
  readonly projectKey?: string;
} = {}): ReplicaGraphData {
  const view = options.view ?? "knowledge";
  return {
    view,
    projectKey: view === "project" ? options.projectKey?.trim() || null : null,
    evidenceChainStatus: view === "project" ? "empty" : "catalog",
    evidenceGrade: "unavailable",
    productionSideEffect: "none",
    store: view === "project"
      ? {
          ready: false,
          backend: { audit_findings: "unavailable", review_tasks: "unavailable" }
        }
      : { ready: false, backend: "unavailable" },
    title: "",
    scope: "",
    nodes: [],
    relations: [],
    metrics: {
      nodeCount: 0,
      nodeKindCount: 0,
      relationCount: 0,
      strongRelationCount: 0,
      pendingRelationCount: 0
    }
  };
}

function mapGraphWorkbench(response: GraphWorkbenchResponse): ReplicaGraphData {
  return {
    view: response.view,
    projectKey: response.project_key,
    evidenceChainStatus: response.evidence_chain_status,
    evidenceGrade: response.evidence_grade,
    productionSideEffect: response.production_side_effect,
    store: response.store,
    title: response.graph_title,
    scope: response.graph_scope,
    nodes: response.nodes.map((node) => ({
      id: node.id,
      label: node.label,
      kind: node.kind,
      metric: node.metric,
      status: node.status,
      description: node.description,
      href: node.href,
      sourceCollection: node.sourceCollection,
      domain: node.domain,
      x: node.x,
      y: node.y
    })),
    relations: response.relations.map((relation) => ({
      id: relation.id,
      sourceId: relation.sourceId,
      targetId: relation.targetId,
      source: relation.source,
      relation: relation.relation,
      target: relation.target,
      evidence: relation.evidence,
      strength: relation.strength
    })),
    metrics: {
      nodeCount: response.metrics.node_count,
      nodeKindCount: response.metrics.node_kind_count,
      relationCount: response.metrics.relation_count,
      strongRelationCount: response.metrics.strong_relation_count,
      pendingRelationCount: response.metrics.pending_relation_count
    }
  };
}

function mapReportWorkbench(response: ReportWorkbenchResponse): readonly ReferenceReportRecord[] {
  return response.report_entries.map((entry) => ({
    id: entry.id,
    title: entry.title,
    project: normalizeText(entry.source, entry.owner),
    status: entry.status,
    generatedAt: formatReplicaDateTime(entry.updated_at),
    sourceCount: entry.included_finding_count + entry.appendix_count
  }));
}

function projectProgress(status: string): number {
  if (status === "已归档" || status === "已完成") {
    return 100;
  }
  if (status === "待开始") {
    return 12;
  }
  return 68;
}

function mapProjects(response: ProjectsResponse): readonly ReferenceProject[] {
  return response.items.map((item) => ({
    id: item.id,
    name: item.name,
    type: normalizeText(item.audit_topic, item.organization_name),
    owner: normalizeText(item.creator, "项目组"),
    members: item.member_count,
    status: item.status,
    updatedAt: formatDate(item.created_at),
    progress: projectProgress(item.status)
  }));
}

export async function loadReplicaShellData(
  client: ReplicaShellClient = {}
): Promise<ReplicaAdapterResult<ReplicaShellData>> {
  const issues: ReplicaAdapterIssue[] = [];
  const fixtureUser: ReplicaShellUser = {
    displayName: "审计员",
    avatarLabel: "审",
    roleLabel: "演示身份",
    tenantLabel: "fixture"
  };
  const emptyUser: ReplicaShellUser = {
    displayName: "",
    avatarLabel: "",
    roleLabel: "",
    tenantLabel: ""
  };
  const [sessionRead, historyRead] = await Promise.all([
    readOptionalApi("shell", "auth-session", issues, client.fetchAuthSession),
    readOptionalApi("shell", "query-history", issues, client.fetchQueryHistory)
  ]);

  if (allApiReadsDisabled([sessionRead, historyRead])) {
    return {
      source: "fixture",
      outcome: "ready",
      data: { navigation: referenceNavigation, historyItems: referenceHistoryItems, user: fixtureUser },
      issues
    };
  }

  if (allEnabledApiReadsFailed([sessionRead, historyRead])) {
    return {
      source: "api",
      outcome: "error",
      data: { navigation: referenceNavigation, historyItems: [], user: emptyUser },
      issues
    };
  }

  const session = sessionRead.kind === "success" ? sessionRead.value : null;
  const history = historyRead.kind === "success" ? historyRead.value : null;
  const user = session ? mapSessionUser(session) : emptyUser;
  const historyItems = history ? mapQueryHistoryItems(history) : [];
  const degraded = Boolean(
    hasApiFailure([sessionRead, historyRead]) ||
    (session && !session.store.ready) ||
    (history && !history.store.ready)
  );

  if (degraded) {
    issues.push(issue("shell", "partial-schema-gap", "Session or query-history data is only partially available."));
  }

  return {
    source: session ? "hybrid" : "api",
    outcome: degraded
      ? "degraded"
      : session || historyItems.length > 0
        ? "ready"
        : "empty",
    data: { navigation: referenceNavigation, historyItems, user },
    issues
  };
}

export async function loadReplicaChatData(
  client: ReplicaShellClient & ReplicaAgentClient = {}
): Promise<ReplicaAdapterResult<ReplicaChatData>> {
  const issues: ReplicaAdapterIssue[] = [];
  const [agentRead, historyRead] = await Promise.all([
    readOptionalApi("chat", "agents", issues, client.fetchAgents),
    readOptionalApi("chat", "query-history", issues, client.fetchQueryHistory)
  ]);

  if (allApiReadsDisabled([agentRead, historyRead])) {
    return {
      source: "fixture",
      outcome: "ready",
      data: {
        agents: referenceAgents,
        historyItems: referenceHistoryItems,
        documentResults: referenceDocumentResults
      },
      issues
    };
  }

  if (allEnabledApiReadsFailed([agentRead, historyRead])) {
    return {
      source: "api",
      outcome: "error",
      data: { agents: [], historyItems: [], documentResults: [] },
      issues
    };
  }

  const agentResponse = agentRead.kind === "success" ? agentRead.value : null;
  const history = historyRead.kind === "success" ? historyRead.value : null;
  const agents = agentResponse
    ? agentResponse.items.map((item, index) => mapAgent(item, index, "未关联项目"))
    : [];
  const historyItems = history ? mapQueryHistoryItems(history) : [];
  const degraded = Boolean(
    hasApiFailure([agentRead, historyRead]) ||
    (agentResponse && !agentResponse.store.ready) ||
    (history && !history.store.ready)
  );

  if (degraded) {
    issues.push(issue("chat", "partial-schema-gap", "Agent or query-history data is only partially available."));
  }

  return {
    source: "api",
    outcome: degraded ? "degraded" : agents.length > 0 || historyItems.length > 0 ? "ready" : "empty",
    data: { agents, historyItems, documentResults: [] },
    issues
  };
}

export async function loadReplicaAgentsData(
  client: ReplicaAgentClient = {}
): Promise<ReplicaAdapterResult<ReplicaAgentsData>> {
  const issues: ReplicaAdapterIssue[] = [];
  const agentRead = await readOptionalApi("agents", "agents", issues, client.fetchAgents);

  if (agentRead.kind === "disabled") {
    return {
      source: "fixture",
      outcome: "ready",
      data: { agents: referenceAgents, categories: uniqueAgentCategories(referenceAgents) },
      issues
    };
  }

  if (agentRead.kind === "failure") {
    return { source: "api", outcome: "error", data: { agents: [], categories: [] }, issues };
  }

  const agentResponse = agentRead.value;
  const agents = agentResponse.items.map((item, index) => mapAgent(item, index, "未关联项目"));
  const degraded = !agentResponse.store.ready;
  if (degraded) {
    issues.push(issue("agents", "partial-schema-gap", "Agent storage is not ready."));
  }

  return {
    source: "api",
    outcome: degraded ? "degraded" : agents.length > 0 ? "ready" : "empty",
    data: {
      agents,
      categories: agents.length > 0
        ? agentResponse.categories.map(toReferenceAgentCategory)
        : []
    },
    issues
  };
}

export async function loadReplicaAgentMarketData(
  _client: ReplicaAgentClient = {}
): Promise<ReplicaAdapterResult<ReplicaAgentsData>> {
  void _client;
  const marketAgents = getAuditAgentMarketCatalog();

  const issues: ReplicaAdapterIssue[] = [
    issue(
      "agent-market",
      "mutation-gated",
      "Publish, rating, and lifecycle actions remain gated; install uses the agent create API."
    )
  ];

  return {
    source: "catalog",
    outcome: "ready",
    data: {
      agents: marketAgents,
      categories: uniqueAgentCategories(marketAgents)
    },
    issues
  };
}

function uniqueAgentCategories(agents: readonly ReferenceAgentCard[]): readonly ReferenceAgentCategory[] {
  return Array.from(new Set(agents.map((agent) => agent.category).filter(Boolean)));
}

export async function loadReplicaKnowledgeBaseData(
  client: ReplicaKnowledgeBaseClient = {}
): Promise<ReplicaAdapterResult<ReplicaKnowledgeBaseData>> {
  const issues: ReplicaAdapterIssue[] = [];
  const [permissionsRead, knowledgeCatalogRead, sourceCollectionCatalogRead] = await Promise.all([
    readOptionalApi("knowledge-base", "document-permissions", issues, client.fetchDocumentPermissions),
    readOptionalApi("knowledge-base", "knowledge-base-catalog", issues, client.fetchKnowledgeBaseCatalog),
    readOptionalApi(
      "knowledge-base",
      "document-source-collections",
      issues,
      client.fetchDocumentSourceCollections
    )
  ]);
  const reads = [permissionsRead, knowledgeCatalogRead, sourceCollectionCatalogRead];

  if (allApiReadsDisabled(reads)) {
    return {
      source: "fixture",
      outcome: "ready",
      data: {
        knowledgeBases: referenceKnowledgeBases.map((item) => ({
          ...item,
          chunkCount: item.chunkCount ?? null
        })),
        sourceGroups: FALLBACK_SOURCE_COLLECTION_GROUPS,
        readableSourceCollections: referenceKnowledgeBases.map((item) => item.name),
        canUploadPersonal: true,
        currentSearchEmbeddingCount: null,
        metricsSource: "unavailable",
        summary: null,
        store: null,
        boundaries: null
      },
      issues
    };
  }

  if (allEnabledApiReadsFailed(reads)) {
    return {
      source: "api",
      outcome: "error",
      data: {
        knowledgeBases: [],
        sourceGroups: [],
        readableSourceCollections: [],
        canUploadPersonal: false,
        currentSearchEmbeddingCount: null,
        metricsSource: "unavailable",
        summary: null,
        store: null,
        boundaries: null
      },
      issues
    };
  }

  const permissions = permissionsRead.kind === "success" ? permissionsRead.value : null;
  const knowledgeCatalog = knowledgeCatalogRead.kind === "success"
    ? knowledgeCatalogRead.value
    : null;
  const sourceCollectionCatalog = sourceCollectionCatalogRead.kind === "success"
    ? sourceCollectionCatalogRead.value
    : null;
  const catalog =
    knowledgeCatalog ??
    sourceCollectionCatalog;
  const selectableCatalogItems = catalog?.items.filter((item) =>
    item.product_queryable && (item.access === "read" || item.access.startsWith("explicit-"))
  ) ?? [];
  const sourceGroups = selectableCatalogItems.length > 0
    ? sourceCollectionCatalogToGroups(selectableCatalogItems)
    : [];
  const registryOnly = knowledgeCatalog?.boundaries.source === "runtime_state_and_registry_only";
  const knowledgeMetricsReady = Boolean(
    knowledgeCatalog?.store.metrics_ready && !registryOnly
  );
  const knowledgeBases = mapKnowledgeBasesFromSourceGroups(
    sourceGroups,
    catalog?.items,
    knowledgeMetricsReady
  );
  const documentCatalogUploadPermissions = sourceCollectionCatalog?.upload_permissions ?? null;
  const currentSearchEmbeddingCount = knowledgeMetricsReady
    ? knowledgeCatalog?.summary.current_search_embedding_count ?? null
    : null;
  const readinessGap = Boolean(
    hasApiFailure(reads) ||
    (knowledgeCatalog && (
      !knowledgeCatalog.store.ready ||
      !knowledgeCatalog.store.catalog_ready ||
      !knowledgeCatalog.store.metrics_ready ||
      !knowledgeCatalog.search_backend.ready ||
      registryOnly ||
      knowledgeCatalog.items.some((item) => !item.index.search_backend_ready)
    )) ||
    (!knowledgeCatalog && sourceCollectionCatalog)
  );

  if (readinessGap) {
    issues.push(issue(
      "knowledge-base",
      "partial-schema-gap",
      "Knowledge-base registry data is available, but search metrics or backend readiness is unavailable."
    ));
  }

  return {
    source: "api",
    outcome: readinessGap
      ? "degraded"
      : knowledgeBases.length > 0 || (permissions?.source_collections.length ?? 0) > 0
        ? "ready"
        : "empty",
    data: {
      knowledgeBases,
      sourceGroups,
      readableSourceCollections:
        catalog?.items.filter((item) => item.queryable || item.product_queryable).map((item) => item.label) ??
        permissions?.source_collections.map((item) => item.label) ??
        [],
      canUploadPersonal:
        documentCatalogUploadPermissions?.can_upload_personal ??
        permissions?.upload_permissions.can_upload_personal ??
        false,
      currentSearchEmbeddingCount,
      metricsSource: knowledgeMetricsReady ? "knowledge-base-catalog" : "unavailable",
      summary: mapKnowledgeBaseSummary(knowledgeCatalog, knowledgeMetricsReady),
      store: mapKnowledgeBaseStore(knowledgeCatalog),
      boundaries: mapKnowledgeBaseBoundaries(knowledgeCatalog)
    },
    issues
  };
}

export async function loadReplicaDocumentsData(
  client: ReplicaDocumentsClient = {}
): Promise<ReplicaAdapterResult<ReplicaDocumentsData>> {
  const issues: ReplicaAdapterIssue[] = [];
  const [knowledgeCatalogRead, sourceCollectionCatalogRead, historyRead] = await Promise.all([
    readOptionalApi("documents", "knowledge-base-catalog", issues, client.fetchKnowledgeBaseCatalog),
    readOptionalApi(
      "documents",
      "document-source-collections",
      issues,
      client.fetchDocumentSourceCollections
    ),
    readOptionalApi("documents", "query-history", issues, client.fetchQueryHistory)
  ]);
  const reads = [knowledgeCatalogRead, sourceCollectionCatalogRead, historyRead];

  if (allApiReadsDisabled(reads)) {
    return {
      source: "fixture",
      outcome: "ready",
      data: {
        categories: referenceDocumentCategories,
        searchHistory: referenceSearchHistory,
        results: referenceDocumentResults
      },
      issues
    };
  }

  if (allEnabledApiReadsFailed(reads)) {
    return {
      source: "api",
      outcome: "error",
      data: { categories: [], searchHistory: [], results: [] },
      issues
    };
  }

  const knowledgeCatalog = knowledgeCatalogRead.kind === "success"
    ? knowledgeCatalogRead.value
    : null;
  const sourceCollectionCatalog = sourceCollectionCatalogRead.kind === "success"
    ? sourceCollectionCatalogRead.value
    : null;
  const history = historyRead.kind === "success" ? historyRead.value : null;
  const catalog =
    knowledgeCatalog ??
    sourceCollectionCatalog;
  const categories = catalog ? mapDocumentCategoriesFromCatalog(catalog.items) : [];
  const documentMetricsUnavailable = categories.some((category) => category.count === null);
  const searchHistory = history
    ? history.items.map((item) => normalizeText(item.question, "未命名查询"))
    : [];
  const readinessGap = Boolean(
    hasApiFailure(reads) ||
    documentMetricsUnavailable ||
    (knowledgeCatalog && (
      !knowledgeCatalog.store.ready ||
      !knowledgeCatalog.search_backend.ready
    )) ||
    (sourceCollectionCatalog && !sourceCollectionCatalog.search_backend.ready) ||
    (history && !history.store.ready)
  );

  if (readinessGap) {
    issues.push(issue(
      "documents",
      "partial-schema-gap",
      "Document catalog, search backend, or query-history storage is not ready."
    ));
  }

  return {
    source: "api",
    outcome: readinessGap
      ? "degraded"
      : categories.length > 0 || searchHistory.length > 0
        ? "ready"
        : "empty",
    data: { categories, searchHistory, results: [] },
    issues
  };
}

export async function loadReplicaAnalyticsData(
  client: ReplicaAnalyticsClient = {}
): Promise<ReplicaAdapterResult<ReplicaAnalyticsData>> {
  const issues: ReplicaAdapterIssue[] = [];
  const uploadHistoryRead = await readOptionalApi(
    "analytics",
    "analysis-upload-history",
    issues,
    client.fetchAnalysisUploadHistory
  );

  if (uploadHistoryRead.kind === "disabled") {
    issues.push(issue(
      "analytics",
      "partial-schema-gap",
      "Analysis upload history API is not configured; no fixture data was substituted."
    ));
    return {
      source: "api",
      outcome: "empty",
      data: { datasets: [], store: null },
      issues
    };
  }

  if (uploadHistoryRead.kind === "failure") {
    return { source: "api", outcome: "error", data: { datasets: [], store: null }, issues };
  }

  const uploadHistory = uploadHistoryRead.value;
  const datasets = mapAnalysisUploads(uploadHistory);
  const degraded = !uploadHistory.store.ready;
  if (degraded) {
    issues.push(issue("analytics", "partial-schema-gap", "Analysis upload storage is not ready."));
  }

  return {
    source: "api",
    outcome: degraded ? "degraded" : datasets.length > 0 ? "ready" : "empty",
    data: { datasets, store: uploadHistory.store },
    issues
  };
}

export async function loadReplicaGraphData(
  client: ReplicaGraphClient = {},
  options: {
    readonly view?: "knowledge" | "project";
    readonly projectKey?: string;
  } = {}
): Promise<ReplicaAdapterResult<ReplicaGraphData>> {
  const issues: ReplicaAdapterIssue[] = [];
  const requestedView = options.view ?? "knowledge";
  const projectKey = requestedView === "project" ? options.projectKey?.trim() ?? "" : "";
  const requestOptions = requestedView === "project"
    ? { view: "project" as const, projectKey }
    : undefined;
  const fetchGraphWorkbench = client.fetchGraphWorkbench;
  const graphRead = await readOptionalApi(
    "graph",
    "graph-workbench",
    issues,
    fetchGraphWorkbench
      ? () => fetchGraphWorkbench(requestOptions)
      : undefined
  );

  if (graphRead.kind === "disabled") {
    if (requestedView === "project") {
      issues.push(issue(
        "graph",
        "partial-schema-gap",
        "Project evidence graph API read is disabled; no knowledge fixture was substituted."
      ));
      return {
        source: "api",
        outcome: "empty",
        data: emptyGraphData({ view: "project", projectKey }),
        issues
      };
    }
    return { source: "fixture", outcome: "ready", data: graphDataFallback(), issues };
  }

  if (graphRead.kind === "failure") {
    return {
      source: "api",
      outcome: "error",
      data: emptyGraphData({ view: requestedView, projectKey }),
      issues
    };
  }

  const graph = graphRead.value;
  const mismatchedResponse = requestedView === "project"
    ? graph.view !== "project" || graph.project_key !== projectKey
    : graph.view !== "knowledge" || graph.project_key !== null;
  if (mismatchedResponse) {
    issues.push(issue(
      "graph",
      "api-read-failed",
      "Graph workbench response did not match the requested view and project scope."
    ));
    return {
      source: "api",
      outcome: "error",
      data: emptyGraphData({ view: requestedView, projectKey }),
      issues
    };
  }
  const seedBackend = isReadonlySeedBackend(graph.store.backend);

  if (seedBackend) {
    issues.push(issue(
      "graph",
      "backend-seed-data",
      `Graph workbench is served by ${graph.store.backend}; treat it as seed data until persistent relations are available.`
    ));
  }

  if (!graph.store.ready) {
    issues.push(issue("graph", "partial-schema-gap", "Graph workbench storage is not ready."));
  }

  return {
    source: "api",
    outcome: seedBackend || !graph.store.ready
      ? "degraded"
      : graph.view === "project" && graph.evidence_chain_status === "empty"
        ? "empty"
        : graph.nodes.length > 0
        ? "ready"
        : "empty",
    data: mapGraphWorkbench(graph),
    issues
  };
}

export async function loadReplicaReportsData(
  client: ReplicaReportsClient = {}
): Promise<ReplicaAdapterResult<ReplicaReportsData>> {
  const issues: ReplicaAdapterIssue[] = [
    issue(
      "reports",
      "mutation-gated",
      "Report generation, signing, and download side effects remain gated until explicit approval."
    )
  ];
  const reportsRead = await readOptionalApi(
    "reports",
    "report-workbench",
    issues,
    client.fetchReportWorkbench
  );

  if (reportsRead.kind === "disabled") {
    return {
      source: "fixture",
      outcome: "ready",
      data: { records: referenceReportRecords },
      issues
    };
  }

  if (reportsRead.kind === "failure") {
    return { source: "api", outcome: "error", data: { records: [] }, issues };
  }

  const reports = reportsRead.value;
  const records = mapReportWorkbench(reports);
  const degraded = !reports.store.ready;
  if (degraded) {
    issues.push(issue("reports", "partial-schema-gap", "Report workbench storage is not ready."));
  }

  return {
    source: "api",
    outcome: degraded ? "degraded" : records.length > 0 ? "ready" : "empty",
    data: { records },
    issues
  };
}

export async function loadReplicaProjectsData(
  client: ReplicaProjectsClient = {}
): Promise<ReplicaAdapterResult<ReplicaProjectsData>> {
  const issues: ReplicaAdapterIssue[] = [
    issue(
      "projects",
      "mutation-gated",
      "Create project, member changes, archive, and role updates remain gated until write approval."
    )
  ];
  const projectsRead = await readOptionalApi("projects", "projects", issues, client.fetchProjects);

  if (projectsRead.kind === "disabled") {
    return {
      source: "fixture",
      outcome: "ready",
      data: { projects: referenceProjects },
      issues
    };
  }

  if (projectsRead.kind === "failure") {
    return { source: "api", outcome: "error", data: { projects: [] }, issues };
  }

  const projects = projectsRead.value;
  const mappedProjects = mapProjects(projects);
  const degraded = !projects.store.ready;
  if (degraded) {
    issues.push(issue("projects", "partial-schema-gap", "Project storage is not ready."));
  }

  return {
    source: "api",
    outcome: degraded ? "degraded" : mappedProjects.length > 0 ? "ready" : "empty",
    data: { projects: mappedProjects },
    issues
  };
}
