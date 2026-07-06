import type {
  AgentsResponse,
  AuditAgentApiItem,
  AuthSessionResponse,
  DocumentPermissionsResponse,
  GraphWorkbenchResponse,
  ProjectsResponse,
  QueryHistoryResponse,
  QueryRequest,
  QueryResponse,
  ReportWorkbenchResponse,
  SourceCollection,
  TableAnalysisUploadHistoryResponse
} from "./api-types";
import {
  referenceAgents,
  referenceAnalysisDatasets,
  referenceDocumentCategories,
  referenceDocumentResults,
  referenceGraphNodes,
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
  ReferenceHistoryItem,
  ReferenceKnowledgeBase,
  ReferenceNavigationItem,
  ReferenceProject,
  ReferenceReportRecord
} from "./reference-replica-data";

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
  readonly nodes: readonly ReferenceGraphNode[];
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
};

export type ReplicaDocumentsClient = {
  readonly fetchQueryHistory?: () => Promise<QueryHistoryResponse>;
  readonly runKnowledgeQuery?: (request: QueryRequest) => Promise<QueryResponse>;
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

const sourceCollectionLabels: Partial<Record<SourceCollection, string>> = {
  "medical-insurance-laws": "医保法规库",
  "supervision-rules-knowledge": "监督规则库",
  "medical-insurance-catalog": "医保目录库",
  "risk-negative-list": "风险负面清单",
  "personal-materials": "个人材料库"
};

const defaultDocumentQuery: QueryRequest = {
  question: "招标人违法确定中标人的定性依据",
  top_k: 5,
  title_only: true
};

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

function locatorString(locator: Record<string, unknown>, keys: readonly string[]): string | null {
  for (const key of keys) {
    const value = locator[key];
    if (typeof value === "string" && value.trim().length > 0) {
      return value.trim();
    }
    if (typeof value === "number") {
      return String(value);
    }
  }
  return null;
}

function makeInitial(name: string): string {
  const chars = Array.from(name.trim());
  if (chars.length === 0) {
    return "AI";
  }
  return chars.slice(0, Math.min(2, chars.length)).join("");
}

function toReferenceAgentCategory(category: string): ReferenceAgentCategory {
  if (category === "效率类" || category === "业务类" || category === "研究类") {
    return category;
  }
  return "业务类";
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

function mapDocumentResults(response: QueryResponse): readonly ReferenceDocumentResult[] {
  const citationResults = response.citations.map((citation, index) => {
    const locatorTitle = locatorString(citation.locator, [
      "title",
      "document_title",
      "file_name",
      "source_title",
      "name"
    ]);
    const locatorDate = locatorString(citation.locator, ["date", "published_at", "issued_at", "year"]);
    const source = sourceCollectionLabels[citation.source_collection] ?? citation.source_collection;

    return {
      id: citation.citation_id || `query-citation-${index + 1}`,
      title: locatorTitle ?? `${source}引用 ${index + 1}`,
      category: normalizeText(citation.evidence_type, source),
      excerpt: compactText(citation.snippet, 96),
      source,
      updatedAt: locatorDate ?? "检索命中"
    };
  });

  const personalResults = response.personal_upload_matches.map((match, index) => ({
    id: match.id || `personal-match-${index + 1}`,
    title: match.name,
    category: "个人材料",
    excerpt: compactText(match.snippet, 96),
    source: normalizeText(match.created_by, "个人上传"),
    updatedAt: formatDate(match.indexed_at, "未索引")
  }));

  return [...citationResults, ...personalResults];
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

function mapGraphWorkbench(response: GraphWorkbenchResponse): readonly ReferenceGraphNode[] {
  return response.nodes.map((node) => ({
    id: node.id,
    label: node.label,
    kind: node.kind,
    metric: node.metric,
    status: node.status
  }));
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
      data: { agents: referenceAgents, categories: ["业务类", "效率类", "研究类"] },
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
      "Marketplace ownership, install, rating, and visibility contract is not available yet."
    ),
    issue(
      "agent-market",
      "mutation-gated",
      "Install, copy, publish, and lifecycle actions remain UI-only until write gates are approved."
    )
  ];
  const agentResponse = await readOptionalApi("agent-market", issues, client.fetchAgents);

  if (!agentResponse || agentResponse.items.length === 0) {
    return {
      source: "fixture",
      data: { agents: referenceMarketAgents, categories: ["业务类", "效率类", "研究类"] },
      issues
    };
  }

  const marketAgents = agentResponse.items
    .filter((item) => item.visibility_scope === "system" || item.source === "system-default")
    .map((item, index) => mapAgent(item, index, "智能体广场"));

  return {
    source: sourceFrom(marketAgents.length > 0, marketAgents.length === 0),
    data: {
      agents: marketAgents.length > 0 ? marketAgents : referenceMarketAgents,
      categories: agentResponse.categories.map(toReferenceAgentCategory)
    },
    issues
  };
}

export async function loadReplicaKnowledgeBaseData(
  client: ReplicaKnowledgeBaseClient = {}
): Promise<ReplicaAdapterResult<ReplicaKnowledgeBaseData>> {
  const issues: ReplicaAdapterIssue[] = [
    issue(
      "knowledge-base",
      "catalog-api-needed",
      "Knowledge-base card catalog, document counts, app counts, and ownership contract is not available yet."
    )
  ];
  const permissions = await readOptionalApi("knowledge-base", issues, client.fetchDocumentPermissions);

  return {
    source: sourceFrom(Boolean(permissions), true),
    data: {
      knowledgeBases: referenceKnowledgeBases,
      readableSourceCollections:
        permissions?.source_collections.map((item) => item.label) ??
        referenceKnowledgeBases.map((item) => item.name),
      canUploadPersonal: permissions?.upload_permissions.can_upload_personal ?? true
    },
    issues
  };
}

export async function loadReplicaDocumentsData(
  client: ReplicaDocumentsClient = {}
): Promise<ReplicaAdapterResult<ReplicaDocumentsData>> {
  const issues: ReplicaAdapterIssue[] = [];
  let searchHistory = referenceSearchHistory;
  let results = referenceDocumentResults;
  let apiUsed = false;

  const history = await readOptionalApi("documents", issues, client.fetchQueryHistory);
  if (history && history.items.length > 0) {
    searchHistory = history.items.map((item) => normalizeText(item.question, "未命名查询"));
    apiUsed = true;
  }

  const runKnowledgeQuery = client.runKnowledgeQuery;
  const queryResponse = await readOptionalApi(
    "documents",
    issues,
    runKnowledgeQuery ? () => runKnowledgeQuery(defaultDocumentQuery) : undefined
  );
  if (queryResponse) {
    const mappedResults = mapDocumentResults(queryResponse);
    if (mappedResults.length > 0) {
      results = mappedResults;
      apiUsed = true;
    } else {
      issues.push(
        issue(
          "documents",
          "partial-schema-gap",
          "Knowledge query returned no citations or personal upload matches for document result cards."
        )
      );
    }
  }

  return {
    source: sourceFrom(apiUsed, true),
    data: { categories: referenceDocumentCategories, searchHistory, results },
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
    return { source: "fixture", data: { nodes: referenceGraphNodes }, issues };
  }

  return { source: "api", data: { nodes: mapGraphWorkbench(graph) }, issues };
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
