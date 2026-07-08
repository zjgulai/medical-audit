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
import {
  referenceAgents,
  referenceAnalysisDatasets,
  referenceDocumentCategories,
  referenceDocumentResults,
  referenceGraphNodes,
  referenceGraphRelations,
  referenceHistoryItems,
  referenceKnowledgeBases,
  referenceMarketAgents,
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

export type ReplicaDataSource = "fixture" | "api" | "hybrid";

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
};

export type ReplicaAdapterResult<TData> = {
  readonly source: ReplicaDataSource;
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

export type ReplicaKnowledgeBaseData = {
  readonly knowledgeBases: readonly ReferenceKnowledgeBase[];
  readonly sourceGroups: readonly SourceCollectionGroup[];
  readonly readableSourceCollections: readonly string[];
  readonly canUploadPersonal: boolean;
};

export type ReplicaDocumentsData = {
  readonly categories: readonly ReferenceDocumentCategory[];
  readonly searchHistory: readonly string[];
  readonly results: readonly ReferenceDocumentResult[];
};

export type ReplicaAnalyticsData = {
  readonly datasets: readonly ReferenceAnalysisDataset[];
};

export type ReplicaGraphData = {
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
  readonly fetchGraphWorkbench?: () => Promise<GraphWorkbenchResponse>;
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

function sourceFrom(apiUsed: boolean, fixtureUsed: boolean): ReplicaDataSource {
  if (!apiUsed) {
    return "fixture";
  }
  return fixtureUsed ? "hybrid" : "api";
}

function isReadonlySeedBackend(backend: string): boolean {
  return backend.startsWith("Readonly") && backend.endsWith("Seed");
}

async function readOptionalApi<TResponse>(
  surface: ReplicaSurface,
  issues: ReplicaAdapterIssue[],
  read: (() => Promise<TResponse>) | undefined
): Promise<TResponse | null> {
  if (!read) {
    return null;
  }

  try {
    return await read();
  } catch {
    issues.push(
      issue(surface, "api-read-failed", "API read failed; reference fixture data remains active.")
    );
    return null;
  }
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

function formatDateTime(value: string | null | undefined, fallback = "未记录"): string {
  if (!value) {
    return fallback;
  }
  const withoutTimezone = value.replace("T", " ").replace(/Z$/, "");
  return withoutTimezone.slice(0, 16);
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
    title: normalizeText(item.question, item.answer_summary ?? `查询记录 ${index + 1}`)
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
): readonly ReferenceDocumentCategory[] {
  const categories = items
    .filter((item) => item.product_queryable || item.queryable)
    .map((item) => ({
      id: `source-${item.source_collection}`,
      name: item.label,
      description: item.description,
      count: item.metrics.document_count ?? item.metrics.chunk_count ?? 0
    }));
  return categories.length > 0 ? categories : referenceDocumentCategories;
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
  catalogItems: readonly DocumentSourceCollectionCatalogItem[] | null | undefined
): readonly ReferenceKnowledgeBase[] {
  const itemBySource = new Map(
    (catalogItems ?? []).map((item) => [item.source_collection, item])
  );

  return groups.flatMap((group) =>
    group.options.map((option) => {
      const item = itemBySource.get(option.value);
      const documentCount = item?.metrics.document_count ?? item?.metrics.chunk_count ?? 0;
      const chunkCount = item?.metrics.chunk_count ?? 0;
      const appCount = item?.metrics.linked_app_count ?? 0;
      return {
        id: `kb-${option.value}`,
        name: option.label,
        scope: toKnowledgeBaseScope(option.scope),
        owner: option.scope.includes("个人") ? "审计员" : "系统",
        documentCount,
        appCount,
        updatedAt: item?.phase ?? (option.queryable ? "可检索" : "待接入"),
        description: item?.audit_hint || option.description,
        tags: [
          group.title,
          option.queryable ? "可检索" : "待接入",
          item?.evidence_group || option.scope,
          chunkCount > 0 ? `${chunkCount.toLocaleString("zh-CN")} chunks` : ""
        ].filter(Boolean)
      };
    })
  );
}

function mapAnalysisUploads(
  response: TableAnalysisUploadHistoryResponse
): readonly ReferenceAnalysisDataset[] {
  return response.items.map((item, index) => ({
    id: item.id || `analysis-upload-${index + 1}`,
    name: item.name,
    rows: item.row_count,
    columns: item.column_count,
    status: item.status === "retained" ? "已解析" : item.status,
    insight:
      item.audit_signals[0] ??
      `已读取 ${item.row_count} 行、${item.column_count} 列，可进入本地字段画像。`
  }));
}

function graphDataFallback(): ReplicaGraphData {
  return {
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

function mapGraphWorkbench(response: GraphWorkbenchResponse): ReplicaGraphData {
  return {
    title: response.graph_title,
    scope: response.graph_scope,
    nodes: response.nodes.map((node) => ({
      id: node.id,
      label: node.label,
      kind: node.kind,
      metric: node.metric,
      status: node.status
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
    generatedAt: formatDateTime(entry.updated_at),
    sourceCount: entry.included_finding_count + entry.appendix_count
  }));
}

function projectProgress(status: string): number {
  if (status === "已归档") {
    return 100;
  }
  if (status === "待启动") {
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
  let user: ReplicaShellUser = {
    displayName: "审计员",
    avatarLabel: "审",
    roleLabel: "演示身份",
    tenantLabel: "fixture"
  };
  let historyItems = referenceHistoryItems;
  let apiUsed = false;

  const session = await readOptionalApi("shell", issues, client.fetchAuthSession);
  if (session) {
    user = mapSessionUser(session);
    apiUsed = true;
  }

  const history = await readOptionalApi("shell", issues, client.fetchQueryHistory);
  if (history && history.items.length > 0) {
    historyItems = mapQueryHistoryItems(history);
    apiUsed = true;
  }

  return {
    source: sourceFrom(apiUsed, true),
    data: { navigation: referenceNavigation, historyItems, user },
    issues
  };
}

export async function loadReplicaChatData(
  client: ReplicaShellClient & ReplicaAgentClient = {}
): Promise<ReplicaAdapterResult<ReplicaChatData>> {
  const issues: ReplicaAdapterIssue[] = [];
  let agents = referenceAgents.slice(0, 4);
  let historyItems = referenceHistoryItems;
  let apiUsed = false;

  const agentResponse = await readOptionalApi("chat", issues, client.fetchAgents);
  if (agentResponse && agentResponse.items.length > 0) {
    agents = agentResponse.items.slice(0, 4).map((item, index) => mapAgent(item, index, "未关联项目"));
    apiUsed = true;
  }

  const history = await readOptionalApi("chat", issues, client.fetchQueryHistory);
  if (history && history.items.length > 0) {
    historyItems = mapQueryHistoryItems(history);
    apiUsed = true;
  }

  return {
    source: sourceFrom(apiUsed, true),
    data: { agents, historyItems, documentResults: referenceDocumentResults },
    issues
  };
}

export async function loadReplicaAgentsData(
  client: ReplicaAgentClient = {}
): Promise<ReplicaAdapterResult<ReplicaAgentsData>> {
  const issues: ReplicaAdapterIssue[] = [];
  const agentResponse = await readOptionalApi("agents", issues, client.fetchAgents);

  if (!agentResponse || agentResponse.items.length === 0) {
    return {
      source: "fixture",
      data: { agents: referenceAgents, categories: uniqueAgentCategories(referenceAgents) },
      issues
    };
  }

  return {
    source: "api",
    data: {
      agents: agentResponse.items.map((item, index) => mapAgent(item, index, "未关联项目")),
      categories: agentResponse.categories.map(toReferenceAgentCategory)
    },
    issues
  };
}

export async function loadReplicaAgentMarketData(
  client: ReplicaAgentClient = {}
): Promise<ReplicaAdapterResult<ReplicaAgentsData>> {
  const issues: ReplicaAdapterIssue[] = [
    issue(
      "agent-market",
      "catalog-api-needed",
      "Dedicated marketplace rating and ownership contract is not available yet."
    ),
    issue(
      "agent-market",
      "mutation-gated",
      "Publish, rating, and lifecycle actions remain gated; install uses the agent create API."
    )
  ];
  await readOptionalApi("agent-market", issues, client.fetchAgents);

  return {
    source: "fixture",
    data: {
      agents: referenceMarketAgents,
      categories: uniqueAgentCategories(referenceMarketAgents)
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
  const [permissions, knowledgeCatalog, sourceCollectionCatalog] = await Promise.all([
    readOptionalApi("knowledge-base", issues, client.fetchDocumentPermissions),
    readOptionalApi("knowledge-base", issues, client.fetchKnowledgeBaseCatalog),
    readOptionalApi("knowledge-base", issues, client.fetchDocumentSourceCollections)
  ]);
  const catalog =
    knowledgeCatalog ??
    sourceCollectionCatalog;
  const sourceGroups = sourceCollectionCatalogToGroups(catalog?.items);
  const knowledgeBases = mapKnowledgeBasesFromSourceGroups(sourceGroups, catalog?.items);
  const documentCatalogUploadPermissions = catalog && "upload_permissions" in catalog
    ? catalog.upload_permissions
    : null;

  return {
    source: sourceFrom(Boolean(permissions || catalog), true),
    data: {
      knowledgeBases: knowledgeBases.length > 0 ? knowledgeBases : referenceKnowledgeBases,
      sourceGroups,
      readableSourceCollections:
        catalog?.items.filter((item) => item.queryable || item.product_queryable).map((item) => item.label) ??
        permissions?.source_collections.map((item) => item.label) ??
        FALLBACK_SOURCE_COLLECTION_GROUPS.flatMap((group) => group.options.map((item) => item.label)),
      canUploadPersonal:
        documentCatalogUploadPermissions?.can_upload_personal ??
        permissions?.upload_permissions.can_upload_personal ??
        true
    },
    issues
  };
}

export async function loadReplicaDocumentsData(
  client: ReplicaDocumentsClient = {}
): Promise<ReplicaAdapterResult<ReplicaDocumentsData>> {
  const issues: ReplicaAdapterIssue[] = [];
  let searchHistory = referenceSearchHistory;
  let categories = referenceDocumentCategories;
  const results = referenceDocumentResults;
  let apiUsed = false;

  const [knowledgeCatalog, sourceCollectionCatalog, history] = await Promise.all([
    readOptionalApi("documents", issues, client.fetchKnowledgeBaseCatalog),
    readOptionalApi("documents", issues, client.fetchDocumentSourceCollections),
    readOptionalApi("documents", issues, client.fetchQueryHistory)
  ]);
  const catalog =
    knowledgeCatalog ??
    sourceCollectionCatalog;
  if (catalog && catalog.items.length > 0) {
    categories = mapDocumentCategoriesFromCatalog(catalog.items);
    apiUsed = true;
  }

  if (history && history.items.length > 0) {
    searchHistory = history.items.map((item) => normalizeText(item.question, "未命名查询"));
    apiUsed = true;
  }

  return {
    source: sourceFrom(apiUsed, true),
    data: { categories, searchHistory, results },
    issues
  };
}

export async function loadReplicaAnalyticsData(
  client: ReplicaAnalyticsClient = {}
): Promise<ReplicaAdapterResult<ReplicaAnalyticsData>> {
  const issues: ReplicaAdapterIssue[] = [
    issue(
      "analytics",
      "mutation-gated",
      "Upload, chart generation, and provider analysis actions remain disabled until write gates are approved."
    )
  ];
  const uploadHistory = await readOptionalApi("analytics", issues, client.fetchAnalysisUploadHistory);

  if (!uploadHistory || uploadHistory.items.length === 0) {
    return { source: "fixture", data: { datasets: referenceAnalysisDatasets }, issues };
  }

  return {
    source: "api",
    data: { datasets: mapAnalysisUploads(uploadHistory) },
    issues
  };
}

export async function loadReplicaGraphData(
  client: ReplicaGraphClient = {}
): Promise<ReplicaAdapterResult<ReplicaGraphData>> {
  const issues: ReplicaAdapterIssue[] = [];
  const graph = await readOptionalApi("graph", issues, client.fetchGraphWorkbench);

  if (!graph || graph.nodes.length === 0) {
    return { source: "fixture", data: graphDataFallback(), issues };
  }

  if (isReadonlySeedBackend(graph.store.backend)) {
    issues.push(issue(
      "graph",
      "backend-seed-data",
      `Graph workbench is served by ${graph.store.backend}; treat it as seed data until persistent relations are available.`
    ));
  }

  return { source: "api", data: mapGraphWorkbench(graph), issues };
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
  const reports = await readOptionalApi("reports", issues, client.fetchReportWorkbench);

  if (!reports || reports.report_entries.length === 0) {
    return { source: "fixture", data: { records: referenceReportRecords }, issues };
  }

  return {
    source: "api",
    data: { records: mapReportWorkbench(reports) },
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
  const projects = await readOptionalApi("projects", issues, client.fetchProjects);

  if (!projects || projects.items.length === 0) {
    return { source: "fixture", data: { projects: referenceProjects }, issues };
  }

  return { source: "api", data: { projects: mapProjects(projects) }, issues };
}
