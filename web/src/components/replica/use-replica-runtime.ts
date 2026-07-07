"use client";

import { useEffect, useState } from "react";

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
import type {
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
} from "@/lib/reference-replica-data";
import { FALLBACK_SOURCE_COLLECTION_GROUPS } from "@/lib/source-collection-catalog";

export type ReplicaRuntimeStatus = "loading" | "ready";

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
  status: ReplicaRuntimeStatus
): ReplicaRuntimeResult<TData> {
  return {
    ...result,
    apiReadsEnabled: replicaApiReadsEnabled(),
    status
  };
}

const shellFallback: ReplicaAdapterResult<ReplicaShellData> = {
  source: "fixture",
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
  data: {
    agents: referenceAgents.slice(0, 4),
    historyItems: referenceHistoryItems,
    documentResults: referenceDocumentResults
  },
  issues: []
};

const mineAgentsFallback: ReplicaAdapterResult<ReplicaAgentsData> = {
  source: "fixture",
  data: {
    agents: referenceAgents,
    categories: ["业务类", "效率类", "研究类"]
  },
  issues: []
};

const marketAgentCategories = Array.from(new Set(referenceMarketAgents.map((agent) => agent.category)));

const marketAgentsFallback: ReplicaAdapterResult<ReplicaAgentsData> = {
  source: "fixture",
  data: {
    agents: referenceMarketAgents,
    categories: marketAgentCategories
  },
  issues: [
    {
      surface: "agent-market",
      code: "catalog-api-needed",
      message: "Marketplace catalog contract is not available yet."
    },
    {
      surface: "agent-market",
      code: "mutation-gated",
      message: "Marketplace copy and install actions remain local."
    }
  ]
};

const knowledgeBaseFallback: ReplicaAdapterResult<ReplicaKnowledgeBaseData> = {
  source: "fixture",
  data: {
    knowledgeBases: referenceKnowledgeBases,
    sourceGroups: FALLBACK_SOURCE_COLLECTION_GROUPS,
    readableSourceCollections: referenceKnowledgeBases.map((item) => item.name),
    canUploadPersonal: true
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
  data: {
    categories: referenceDocumentCategories,
    searchHistory: referenceSearchHistory,
    results: referenceDocumentResults
  },
  issues: []
};

const analyticsFallback: ReplicaAdapterResult<ReplicaAnalyticsData> = {
  source: "fixture",
  data: {
    datasets: referenceAnalysisDatasets
  },
  issues: [
    {
      surface: "analytics",
      code: "mutation-gated",
      message: "Upload and generation actions remain local."
    }
  ]
};

const graphFallback: ReplicaAdapterResult<ReplicaGraphData> = {
  source: "fixture",
  data: {
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

function useReplicaLoader<TData>(
  fallback: ReplicaAdapterResult<TData>,
  load: (client: ReplicaClient) => Promise<ReplicaAdapterResult<TData>>
): ReplicaRuntimeResult<TData> {
  const [result, setResult] = useState<ReplicaAdapterResult<TData>>(fallback);
  const [status, setStatus] = useState<ReplicaRuntimeStatus>("loading");

  useEffect(() => {
    let mounted = true;
    setStatus("loading");

    void load(replicaReadClient())
      .then((nextResult) => {
        if (mounted) {
          setResult(nextResult);
        }
      })
      .catch(() => {
        if (mounted) {
          setResult(fallback);
        }
      })
      .finally(() => {
        if (mounted) {
          setStatus("ready");
        }
      });

    return () => {
      mounted = false;
    };
  }, [fallback, load]);

  return runtimeResult(result, status);
}

export function useReplicaShellData(): ReplicaRuntimeResult<ReplicaShellData> {
  return useReplicaLoader(shellFallback, loadReplicaShellData);
}

export function useReplicaChatData(): ReplicaRuntimeResult<ReplicaChatData> {
  return useReplicaLoader(chatFallback, loadReplicaChatData);
}

export function useReplicaAgentsData(mode: "mine" | "market"): ReplicaRuntimeResult<ReplicaAgentsData> {
  const fallback = mode === "mine" ? mineAgentsFallback : marketAgentsFallback;
  const loader = mode === "mine" ? loadReplicaAgentsData : loadReplicaAgentMarketData;
  return useReplicaLoader(fallback, loader);
}

export function useReplicaKnowledgeBaseData(): ReplicaRuntimeResult<ReplicaKnowledgeBaseData> {
  return useReplicaLoader(knowledgeBaseFallback, loadReplicaKnowledgeBaseData);
}

export function useReplicaDocumentsData(): ReplicaRuntimeResult<ReplicaDocumentsData> {
  return useReplicaLoader(documentsFallback, loadReplicaDocumentsData);
}

export function useReplicaAnalyticsData(): ReplicaRuntimeResult<ReplicaAnalyticsData> {
  return useReplicaLoader(analyticsFallback, loadReplicaAnalyticsData);
}

export function useReplicaGraphData(): ReplicaRuntimeResult<ReplicaGraphData> {
  return useReplicaLoader(graphFallback, loadReplicaGraphData);
}

export function useReplicaReportsData(): ReplicaRuntimeResult<ReplicaReportsData> {
  return useReplicaLoader(reportsFallback, loadReplicaReportsData);
}

export function useReplicaProjectsData(): ReplicaRuntimeResult<ReplicaProjectsData> {
  return useReplicaLoader(projectsFallback, loadReplicaProjectsData);
}
