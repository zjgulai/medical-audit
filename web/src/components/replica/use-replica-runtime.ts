"use client";

import { useEffect, useState } from "react";

import { useAuditUser } from "@/components/shell/audit-user-context";
import {
  fetchAgents,
  fetchAnalysisUploadHistory,
  fetchAuthSession,
  fetchDocumentPermissions,
  fetchDocumentSourceCollections,
  fetchGraphWorkbench,
  fetchKnowledgeBaseCatalog,
  fetchProjects,
  fetchQueryHistory,
  fetchReportWorkbench
} from "@/lib/api-client";
import {
  auditExtensionValidationCatalog,
  isAuditExtensionValidationPackEnabled,
  medicalAuditAgentCatalog
} from "@/lib/audit-agent-catalog";
import {
  loadReplicaAgentMarketData,
  loadReplicaAgentsData,
  loadReplicaAnalyticsData,
  loadReplicaChatData,
  loadReplicaDocumentsData,
  loadReplicaGraphData,
  loadReplicaKnowledgeBaseData,
  loadReplicaProjectsData,
  loadReplicaReportsData,
  loadReplicaShellData
} from "@/lib/replica-adapters";
import { auditClientUserId } from "@/lib/audit-user";
import type {
  ReplicaAdapterIssue,
  ReplicaAdapterResult,
  ReplicaAgentsData,
  ReplicaAnalyticsData,
  ReplicaChatData,
  ReplicaClient,
  ReplicaDocumentsData,
  ReplicaGraphData,
  ReplicaKnowledgeBaseData,
  ReplicaProjectsData,
  ReplicaReportsData,
  ReplicaShellData
} from "@/lib/replica-adapters";
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
} from "@/lib/reference-replica-data";
import { FALLBACK_SOURCE_COLLECTION_GROUPS } from "@/lib/source-collection-catalog";

export type ReplicaRuntimeStatus = "loading" | "ready" | "empty" | "degraded" | "error";

export type ReplicaRuntimeResult<TData> = ReplicaAdapterResult<TData> & {
  readonly apiReadsEnabled: boolean;
  readonly status: ReplicaRuntimeStatus;
};

function replicaApiReadsEnabled(): boolean {
  return process.env.NEXT_PUBLIC_MEDICAL_AUDIT_REPLICA_API_READS !== "0";
}

function replicaReadClient(): ReplicaClient {
  if (!replicaApiReadsEnabled()) {
    return {};
  }

  return {
    fetchAgents,
    fetchAnalysisUploadHistory,
    fetchAuthSession,
    fetchDocumentPermissions,
    fetchDocumentSourceCollections,
    fetchGraphWorkbench,
    fetchKnowledgeBaseCatalog,
    fetchProjects,
    fetchQueryHistory,
    fetchReportWorkbench
  };
}

function runtimeResult<TData>(
  result: ReplicaAdapterResult<TData>,
  status: ReplicaRuntimeStatus,
  apiReadsEnabled: boolean
): ReplicaRuntimeResult<TData> {
  return {
    ...result,
    apiReadsEnabled,
    status
  };
}

function apiReadFailure<TData>(
  surface: ReplicaAdapterIssue["surface"],
  emptyResult: ReplicaAdapterResult<TData>
): ReplicaAdapterResult<TData> {
  return {
    ...emptyResult,
    source: "api",
    outcome: "error",
    issues: [
      ...emptyResult.issues,
      {
        surface,
        code: "api-read-failed",
        message: "API read failed unexpectedly; no fixture data was substituted."
      }
    ]
  };
}

const shellFallback: ReplicaAdapterResult<ReplicaShellData> = {
  source: "fixture",
  outcome: "ready",
  data: {
    navigation: referenceNavigation,
    historyItems: referenceHistoryItems,
    user: {
      displayName: "审计员",
      avatarLabel: "审",
      roleLabel: "演示身份",
      tenantLabel: "fixture"
    }
  },
  issues: []
};

const chatFallback: ReplicaAdapterResult<ReplicaChatData> = {
  source: "fixture",
  outcome: "ready",
  data: {
    agents: referenceAgents,
    historyItems: referenceHistoryItems,
    documentResults: referenceDocumentResults
  },
  issues: []
};

const mineAgentsFallback: ReplicaAdapterResult<ReplicaAgentsData> = {
  source: "fixture",
  outcome: "ready",
  data: {
    agents: referenceAgents,
    categories: ["业务类", "效率类", "研究类"]
  },
  issues: []
};

function makeMarketAgentsCatalogResult(
  agents: readonly ReplicaAgentsData["agents"][number][]
): ReplicaAdapterResult<ReplicaAgentsData> {
  return {
    source: "catalog",
    outcome: "ready",
    data: {
      agents,
      categories: Array.from(new Set(agents.map((agent) => agent.category)))
    },
    issues: [
      {
        surface: "agent-market",
        code: "mutation-gated",
        message: "Marketplace copy and install actions remain local."
      }
    ]
  };
}

const medicalMarketAgentsFallback = makeMarketAgentsCatalogResult(medicalAuditAgentCatalog);
const extensionMarketAgentsFallback = makeMarketAgentsCatalogResult([
  ...medicalAuditAgentCatalog,
  ...auditExtensionValidationCatalog
]);

const knowledgeBaseFallback: ReplicaAdapterResult<ReplicaKnowledgeBaseData> = {
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
  issues: [
    {
      surface: "knowledge-base",
      code: "catalog-api-needed",
      message: "Knowledge-base card catalog contract is not available yet."
    }
  ]
};

const documentsFallback: ReplicaAdapterResult<ReplicaDocumentsData> = {
  source: "fixture",
  outcome: "ready",
  data: {
    categories: referenceDocumentCategories,
    searchHistory: referenceSearchHistory,
    results: referenceDocumentResults
  },
  issues: []
};

const analyticsFallback: ReplicaAdapterResult<ReplicaAnalyticsData> = {
  source: "api",
  outcome: "empty",
  data: {
    datasets: [],
    store: null
  },
  issues: [
    {
      surface: "analytics",
      code: "partial-schema-gap",
      message: "Analysis upload history API is not configured; no fixture data was substituted."
    }
  ]
};

const graphFallback: ReplicaAdapterResult<ReplicaGraphData> = {
  source: "fixture",
  outcome: "ready",
  data: {
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
  },
  issues: []
};

const reportsFallback: ReplicaAdapterResult<ReplicaReportsData> = {
  source: "fixture",
  outcome: "ready",
  data: {
    records: referenceReportRecords
  },
  issues: [
    {
      surface: "reports",
      code: "mutation-gated",
      message: "Report generation and export actions remain local."
    }
  ]
};

const projectsFallback: ReplicaAdapterResult<ReplicaProjectsData> = {
  source: "fixture",
  outcome: "ready",
  data: {
    projects: referenceProjects
  },
  issues: [
    {
      surface: "projects",
      code: "mutation-gated",
      message: "Project mutations remain local."
    }
  ]
};

const shellEmpty: ReplicaAdapterResult<ReplicaShellData> = {
  source: "api",
  outcome: "empty",
  data: {
    navigation: referenceNavigation,
    historyItems: [],
    user: { displayName: "", avatarLabel: "", roleLabel: "", tenantLabel: "" }
  },
  issues: []
};

const chatEmpty: ReplicaAdapterResult<ReplicaChatData> = {
  source: "api",
  outcome: "empty",
  data: { agents: [], historyItems: [], documentResults: [] },
  issues: []
};

const mineAgentsEmpty: ReplicaAdapterResult<ReplicaAgentsData> = {
  source: "api",
  outcome: "empty",
  data: { agents: [], categories: [] },
  issues: []
};

const knowledgeBaseEmpty: ReplicaAdapterResult<ReplicaKnowledgeBaseData> = {
  source: "api",
  outcome: "empty",
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
  issues: []
};

const documentsEmpty: ReplicaAdapterResult<ReplicaDocumentsData> = {
  source: "api",
  outcome: "empty",
  data: { categories: [], searchHistory: [], results: [] },
  issues: []
};

const analyticsEmpty: ReplicaAdapterResult<ReplicaAnalyticsData> = {
  source: "api",
  outcome: "empty",
  data: { datasets: [], store: null },
  issues: analyticsFallback.issues
};

const graphEmpty: ReplicaAdapterResult<ReplicaGraphData> = {
  source: "api",
  outcome: "empty",
  data: {
    view: "knowledge",
    projectKey: null,
    evidenceChainStatus: "catalog",
    evidenceGrade: "unavailable",
    productionSideEffect: "none",
    store: { ready: false, backend: "unavailable" },
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
  },
  issues: []
};

const reportsEmpty: ReplicaAdapterResult<ReplicaReportsData> = {
  source: "api",
  outcome: "empty",
  data: { records: [] },
  issues: reportsFallback.issues
};

const projectsEmpty: ReplicaAdapterResult<ReplicaProjectsData> = {
  source: "api",
  outcome: "empty",
  data: { projects: [] },
  issues: projectsFallback.issues
};

function useReplicaLoader<TData>(
  fallback: ReplicaAdapterResult<TData>,
  emptyResult: ReplicaAdapterResult<TData>,
  load: (client: ReplicaClient) => Promise<ReplicaAdapterResult<TData>>,
  surface: ReplicaAdapterIssue["surface"],
  catalogResult?: ReplicaAdapterResult<TData>
): ReplicaRuntimeResult<TData> {
  const auditUser = useAuditUser();
  const apiReadsEnabled = replicaApiReadsEnabled();
  const identityKey = `${auditUser.role}:${auditClientUserId(auditUser.role)}`;
  const runtimeKey = catalogResult
    ? `${surface}:catalog:${identityKey}`
    : `${surface}:${apiReadsEnabled ? "api" : "fixture"}:${identityKey}`;
  const initialResult = catalogResult ?? (apiReadsEnabled ? emptyResult : fallback);
  const initialStatus: ReplicaRuntimeStatus = catalogResult
    ? "ready"
    : apiReadsEnabled
      ? "loading"
      : fallback.outcome;
  const [state, setState] = useState<{
    readonly key: string;
    readonly result: ReplicaAdapterResult<TData>;
    readonly status: ReplicaRuntimeStatus;
  }>(() => ({ key: runtimeKey, result: initialResult, status: initialStatus }));
  const visibleState = state.key === runtimeKey
    ? state
    : { key: runtimeKey, result: initialResult, status: initialStatus };

  useEffect(() => {
    let mounted = true;

    if (catalogResult) {
      setState({ key: runtimeKey, result: catalogResult, status: "ready" });
      return () => {
        mounted = false;
      };
    }

    if (!apiReadsEnabled) {
      setState({ key: runtimeKey, result: fallback, status: fallback.outcome });
      return () => {
        mounted = false;
      };
    }

    setState({ key: runtimeKey, result: emptyResult, status: "loading" });

    void load(replicaReadClient())
      .then((nextResult) => {
        if (mounted) {
          setState((currentState) => currentState.key === runtimeKey
            ? { key: runtimeKey, result: nextResult, status: nextResult.outcome }
            : currentState);
        }
      })
      .catch(() => {
        if (mounted) {
          setState((currentState) => currentState.key === runtimeKey
            ? {
                key: runtimeKey,
                result: apiReadFailure(surface, emptyResult),
                status: "error"
              }
            : currentState);
        }
      });

    return () => {
      mounted = false;
    };
  }, [apiReadsEnabled, catalogResult, emptyResult, fallback, load, runtimeKey, surface]);

  return runtimeResult(visibleState.result, visibleState.status, apiReadsEnabled);
}

export function useReplicaShellData(): ReplicaRuntimeResult<ReplicaShellData> {
  return useReplicaLoader(shellFallback, shellEmpty, loadReplicaShellData, "shell");
}

export function useReplicaChatData(): ReplicaRuntimeResult<ReplicaChatData> {
  return useReplicaLoader(chatFallback, chatEmpty, loadReplicaChatData, "chat");
}

export function useReplicaAgentsData(mode: "mine" | "market"): ReplicaRuntimeResult<ReplicaAgentsData> {
  const marketAgentsFallback = isAuditExtensionValidationPackEnabled()
    ? extensionMarketAgentsFallback
    : medicalMarketAgentsFallback;
  const fallback = mode === "mine" ? mineAgentsFallback : marketAgentsFallback;
  const emptyResult = mode === "mine" ? mineAgentsEmpty : marketAgentsFallback;
  const loader = mode === "mine" ? loadReplicaAgentsData : loadReplicaAgentMarketData;
  return useReplicaLoader(
    fallback,
    emptyResult,
    loader,
    mode === "mine" ? "agents" : "agent-market",
    mode === "market" ? marketAgentsFallback : undefined
  );
}

export function useReplicaKnowledgeBaseData(): ReplicaRuntimeResult<ReplicaKnowledgeBaseData> {
  return useReplicaLoader(
    knowledgeBaseFallback,
    knowledgeBaseEmpty,
    loadReplicaKnowledgeBaseData,
    "knowledge-base"
  );
}

export function useReplicaDocumentsData(): ReplicaRuntimeResult<ReplicaDocumentsData> {
  return useReplicaLoader(documentsFallback, documentsEmpty, loadReplicaDocumentsData, "documents");
}

export function useReplicaAnalyticsData(): ReplicaRuntimeResult<ReplicaAnalyticsData> {
  return useReplicaLoader(analyticsFallback, analyticsEmpty, loadReplicaAnalyticsData, "analytics");
}

export function useReplicaGraphData(): ReplicaRuntimeResult<ReplicaGraphData> {
  return useReplicaLoader(graphFallback, graphEmpty, loadReplicaGraphData, "graph");
}

export function useReplicaReportsData(): ReplicaRuntimeResult<ReplicaReportsData> {
  return useReplicaLoader(reportsFallback, reportsEmpty, loadReplicaReportsData, "reports");
}

export function useReplicaProjectsData(): ReplicaRuntimeResult<ReplicaProjectsData> {
  return useReplicaLoader(projectsFallback, projectsEmpty, loadReplicaProjectsData, "projects");
}
