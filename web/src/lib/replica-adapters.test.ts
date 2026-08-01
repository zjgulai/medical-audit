import { afterEach, describe, expect, it, vi } from "vitest";

import type {
  AgentsResponse,
  AuditAgentApiItem,
  DocumentSourceCollectionCatalogResponse,
  GraphWorkbenchResponse,
  KnowledgeBaseCatalogItem,
  KnowledgeBaseCatalogResponse,
  QueryHistoryResponse,
  TableAnalysisUploadHistoryResponse
} from "./api-types";
import {
  formatReplicaDateTime,
  loadReplicaAgentMarketData,
  loadReplicaAnalyticsData,
  loadReplicaChatData,
  loadReplicaDocumentsData,
  loadReplicaGraphData,
  loadReplicaKnowledgeBaseData,
  loadReplicaProjectsData
} from "./replica-adapters";
import { referenceHistoryItems, referenceMarketAgents } from "./reference-replica-data";

function makeApiAgent(id: string, index: number): AuditAgentApiItem {
  return {
    id,
    name: `API 智能体 ${index}`,
    category: index % 2 === 0 ? "效率类" : "业务类",
    topic: `审计主题 ${index}`,
    prompt: `请围绕审计主题 ${index} 输出风险判断、证据依据和待补材料。`,
    knowledge_base: "医保基金合规知识库",
    project_name: "医保基金使用合规专项自查",
    status: "active",
    prompt_version: 1,
    prompt_version_key: `${id}@v1`,
    visibility_scope: "project",
    allowed_roles: ["admin", "technician", "director", "member"],
    prompt_versions: [
      {
        version: 1,
        prompt: `请围绕审计主题 ${index} 输出风险判断、证据依据和待补材料。`,
        change_summary: "initial version",
        is_active: true,
        created_by: "next-admin",
        created_at: "2026-07-06T00:00:00Z",
        review_status: "approved",
        review_note: "reviewed",
        requested_by: "next-admin",
        reviewed_by: "next-admin",
        reviewed_at: "2026-07-06T00:00:00Z",
        review_updated_at: "2026-07-06T00:00:00Z"
      }
    ],
    created_by: "next-admin",
    created_at: "2026-07-06T00:00:00Z",
    updated_at: "2026-07-06T00:00:00Z",
    source: "custom",
    metadata: {
      summary: `API 智能体 ${index} 的完整摘要。`,
      description: `API 智能体 ${index} 的完整描述。`,
      contract_version: "audit-agent-v1"
    }
  };
}

function makeAgentsResponse(ids: readonly string[]): AgentsResponse {
  return {
    items: ids.map((id, index) => makeApiAgent(id, index + 1)),
    categories: ["业务类", "效率类", "研究类"],
    store: { ready: true, backend: "SqlAlchemyAgentStore" }
  };
}

const emptyQueryHistory: QueryHistoryResponse = {
  items: [],
  store: { ready: true, backend: "SqlAlchemyQueryHistoryStore" }
};

describe("formatReplicaDateTime", () => {
  it("converts UTC review timestamps to the audit display timezone", () => {
    expect(formatReplicaDateTime("2026-08-01T06:00:00Z")).toBe("2026-08-01 14:00");
    expect(formatReplicaDateTime(null)).toBe("未记录");
    expect(formatReplicaDateTime("not-a-date")).toBe("not-a-date");
  });
});

const catalogItem: KnowledgeBaseCatalogItem = {
  source_collection: "medical-insurance-laws",
  label: "医保法规库",
  scope: "系统",
  phase: "active",
  domain: "医保",
  evidence_group: "法规政策",
  description: "医保法规政策。",
  audit_hint: "用于医保审计依据核验。",
  access: "read",
  product_queryable: true,
  queryable: true,
  metrics: {
    document_count: 12,
    chunk_count: 120,
    character_count: 24000,
    linked_app_count: 2,
    embedding_count: 120,
    active_embedding_count: 120,
    candidate_chunk_count: 0
  },
  index: {
    latest_version_key: "medical-legal@v1",
    latest_status: "active",
    search_backend_ready: true,
    queryable: true
  },
  actions: {
    documents: "/documents",
    chat: "/chat",
    graph: "/graph"
  }
};

const sourceCollectionCatalogItem: DocumentSourceCollectionCatalogResponse["items"][number] = {
  ...catalogItem,
  metrics: {
    document_count: catalogItem.metrics.document_count,
    chunk_count: catalogItem.metrics.chunk_count,
    character_count: catalogItem.metrics.character_count,
    linked_app_count: catalogItem.metrics.linked_app_count
  }
};

const uploadPermissions = {
  can_upload_personal: true,
  can_read_all_personal_uploads: true,
  can_govern_personal_uploads: true
} as const;

const knowledgeBaseCatalog: KnowledgeBaseCatalogResponse = {
  contract_version: "knowledge-base-catalog-v1",
  role: "admin",
  summary: {
    source_collection_count: 1,
    queryable_collection_count: 1,
    total_document_count: 12,
    total_chunk_count: 120,
    total_embedding_count: 120,
    current_search_embedding_count: 49051,
    candidate_chunk_count: 0,
    domain_counts: { 医保: 1 }
  },
  items: [catalogItem],
  search_backend: { ready: true, backend: "postgres", details: {} },
  store: {
    ready: true,
    catalog_ready: true,
    metrics_ready: true,
    backend: "runtime_state_and_postgres_catalog"
  },
  boundaries: {
    production_write: false,
    provider_call: false,
    database_write: false,
    object_storage_write: false,
    query_history_write: false,
    source: "runtime_state_and_postgres_catalog"
  }
};

const sourceCollectionCatalog: DocumentSourceCollectionCatalogResponse = {
  contract_version: "document-source-collections-v1",
  role: "admin",
  items: [sourceCollectionCatalogItem],
  search_backend: { ready: true, backend: "postgres", details: {} },
  upload_permissions: uploadPermissions,
  boundaries: {
    production_write: false,
    provider_call: false,
    database_write: false,
    object_storage_write: false,
    source: "runtime_state_and_registry_only"
  }
};

const emptyKnowledgeCatalog: KnowledgeBaseCatalogResponse = {
  ...knowledgeBaseCatalog,
  summary: {
    source_collection_count: 0,
    queryable_collection_count: 0,
    total_document_count: 0,
    total_chunk_count: 0,
    total_embedding_count: 0,
    current_search_embedding_count: 0,
    candidate_chunk_count: 0,
    domain_counts: {}
  },
  items: []
};

const emptySourceCatalog: DocumentSourceCollectionCatalogResponse = {
  ...sourceCollectionCatalog,
  items: []
};

const metricBearingSourceCatalog: DocumentSourceCollectionCatalogResponse = {
  ...sourceCollectionCatalog,
  search_backend: {
    ready: true,
    backend: "postgres",
    details: { matching_embedding_count: 456 }
  }
};

const registryOnlyKnowledgeCatalog: KnowledgeBaseCatalogResponse = {
  ...knowledgeBaseCatalog,
  summary: {
    source_collection_count: 1,
    queryable_collection_count: 1,
    total_document_count: 0,
    total_chunk_count: 0,
    total_embedding_count: 0,
    current_search_embedding_count: 0,
    candidate_chunk_count: 0,
    domain_counts: { 医保: 1 }
  },
  items: [
    {
      ...catalogItem,
      metrics: {
        document_count: 0,
        chunk_count: 0,
        character_count: 0,
        linked_app_count: 0,
        embedding_count: 0,
        active_embedding_count: 0,
        candidate_chunk_count: 0
      },
      index: {
        ...catalogItem.index,
        search_backend_ready: true
      }
    }
  ],
  search_backend: { ready: true, backend: "postgres", details: {} },
  store: {
    ready: false,
    catalog_ready: true,
    metrics_ready: false,
    backend: "runtime_state_and_registry_only"
  },
  boundaries: {
    ...knowledgeBaseCatalog.boundaries,
    source: "runtime_state_and_registry_only"
  }
};

const readyZeroMetricKnowledgeCatalog: KnowledgeBaseCatalogResponse = {
  ...registryOnlyKnowledgeCatalog,
  summary: {
    ...registryOnlyKnowledgeCatalog.summary,
    total_chunk_count: 0
  },
  search_backend: { ready: true, backend: "postgres", details: {} },
  store: {
    ready: true,
    catalog_ready: true,
    metrics_ready: true,
    backend: "runtime_state_and_postgres_catalog"
  },
  items: registryOnlyKnowledgeCatalog.items.map((item) => ({
    ...item,
    metrics: { ...item.metrics, chunk_count: 0 },
    index: { ...item.index, search_backend_ready: true }
  })),
  boundaries: {
    ...knowledgeBaseCatalog.boundaries,
    source: "runtime_state_and_postgres_catalog"
  }
};

const registryProvenanceOnlyKnowledgeCatalog: KnowledgeBaseCatalogResponse = {
  ...registryOnlyKnowledgeCatalog,
  search_backend: { ready: true, backend: "postgres", details: {} },
  items: registryOnlyKnowledgeCatalog.items.map((item) => ({
    ...item,
    index: { ...item.index, search_backend_ready: true }
  })),
  boundaries: {
    ...registryOnlyKnowledgeCatalog.boundaries,
    source: "runtime_state_and_registry_only"
  }
};

const unavailableKnowledgeCatalog: KnowledgeBaseCatalogResponse = {
  ...knowledgeBaseCatalog,
  summary: {
    ...knowledgeBaseCatalog.summary,
    queryable_collection_count: 0
  },
  items: [
    {
      ...catalogItem,
      product_queryable: false,
      queryable: false,
      index: { ...catalogItem.index, queryable: false }
    }
  ]
};

const graphWorkbench: GraphWorkbenchResponse = {
  format: "graph-workbench-v1",
  generated_at: "2026-07-08T08:00:00Z",
  graph_id: "medical-audit-knowledge-catalog",
  graph_title: "医疗审计知识工程",
  graph_scope: "生产知识库目录、文档检索和审计问答共同使用的知识底座。",
  view: "knowledge",
  project_key: null,
  evidence_chain_status: "catalog",
  nodes: [
    {
      id: "graph-node-project",
      label: "医疗审计知识工程",
      kind: "项目",
      status: "已归集",
      description: "当前生产知识库目录、文档检索和审计问答共同使用的知识底座。",
      metric: "25 类知识库",
      href: "/projects",
      x: 100,
      y: 250
    },
    {
      id: "graph-domain-medical",
      label: "医疗医保知识",
      kind: "一级分类",
      status: "已归集",
      description: "医保基金、监管规则、医保目录和风险清单。",
      metric: "4 个知识库",
      href: "/knowledge-base",
      x: 320,
      y: 120
    }
  ],
  relations: [
    {
      id: "graph-project-medical",
      sourceId: "graph-node-project",
      targetId: "graph-domain-medical",
      source: "医疗审计知识工程",
      relation: "组织",
      target: "医疗医保知识",
      evidence: "4 个一级知识库分类",
      strength: "强"
    }
  ],
  metrics: {
    node_count: 2,
    node_kind_count: 2,
    node_kind_counts: {
      项目: 1,
      一级分类: 1,
      知识库: 0,
      文档: 0,
      规则: 0,
      疑点: 0,
      复核: 0,
      报告: 0,
      整改: 0
    },
    relation_count: 1,
    strong_relation_count: 1,
    pending_relation_count: 0
  },
  evidence_grade: "production-readonly",
  production_side_effect: "none",
  store: { ready: true, backend: "KnowledgeCatalogGraphBuilder" }
};

describe("loadReplicaAgentMarketData", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("keeps the market catalog independent from personal agent API reads", async () => {
    vi.stubEnv("NEXT_PUBLIC_MEDICAL_AUDIT_AGENT_EXTENSION_PACK", "0");
    const fetchAgents = vi.fn(async (): Promise<AgentsResponse> => ({
      items: [
        {
          id: "seed-legacy-business",
          name: "旧业务助手",
          category: "业务类",
          topic: "旧专题",
          prompt: "旧系统默认提示词",
          knowledge_base: "旧知识库",
          project_name: "旧项目",
          status: "active",
          prompt_version: 1,
          prompt_version_key: "seed-legacy-business@v1",
          visibility_scope: "system",
          allowed_roles: ["admin"],
          prompt_versions: [],
          created_by: "system",
          updated_at: "2026-07-06T00:00:00Z",
          source: "system-default",
          metadata: {}
        }
      ],
      categories: ["业务类", "效率类", "研究类"],
      store: { ready: true, backend: "SqlAlchemyAgentStore" }
    }));

    const result = await loadReplicaAgentMarketData({ fetchAgents });

    expect(fetchAgents).not.toHaveBeenCalled();
    expect(result.source).toBe("catalog");
    expect(result.outcome).toBe("ready");
    expect(result.data.agents).toEqual(referenceMarketAgents);
    expect(result.data.agents.map((agent) => agent.id)).toEqual([
      "agent-citation-check",
      "agent-duplicate-charge",
      "agent-report-draft"
    ]);
    expect(result.data.categories).toEqual(["业务类", "效率类"]);
    expect(result.data.agents.some((agent) => agent.id === "seed-legacy-business")).toBe(false);
  });

  it("appends exactly three extension validation agents only under the opt-in flag", async () => {
    vi.stubEnv("NEXT_PUBLIC_MEDICAL_AUDIT_AGENT_EXTENSION_PACK", "1");

    const result = await loadReplicaAgentMarketData();

    expect(result.source).toBe("catalog");
    expect(result.outcome).toBe("ready");
    expect(result.data.agents).toHaveLength(6);
    expect(result.data.agents.slice(3).map((agent) => [agent.category, agent.name])).toEqual([
      ["财务收支审计", "超标准举办会议"],
      ["采购招标审计", "违法订立与招投标文件不符的合同或协议"],
      ["工程审计", "未经批准，擅自改变工程建设项目招标方式"]
    ]);
    expect(result.data.agents.slice(3).every((agent) => agent.catalogScope === "extension-validation")).toBe(true);
  });
});

describe("loadReplicaChatData", () => {
  it("maps every API agent without applying the chat presentation limit", async () => {
    const result = await loadReplicaChatData({
      fetchAgents: vi.fn().mockResolvedValue(
        makeAgentsResponse(["first-id", "second-id", "third-id", "fourth-id", "fifth-id"])
      ),
      fetchQueryHistory: vi.fn().mockResolvedValue(emptyQueryHistory)
    });

    expect(result.outcome).toBe("ready");
    expect(result.data.agents).toHaveLength(5);
    expect(result.data.agents[4]).toEqual(expect.objectContaining({ id: "fifth-id", name: "API 智能体 5" }));
  });

  it("keeps successful empty API history empty", async () => {
    const result = await loadReplicaChatData({
      fetchQueryHistory: vi.fn().mockResolvedValue(emptyQueryHistory)
    });

    expect(result.source).toBe("api");
    expect(result.outcome).toBe("empty");
    expect(result.data.historyItems).toEqual([]);
  });

  it("marks only durable API history as eligible for manual task creation", async () => {
    const historyItem = {
      id: "query-history-001",
      user_identifier: "next-member",
      question: "医保基金审核依据",
      filters: { source_collections: ["medical-insurance-laws" as const] },
      answer_summary: "应核对证据链。",
      retrieved_chunk_ids: ["chunk-001"],
      citation_count: 1,
      created_at: "2026-07-15T00:00:00Z"
    };
    const ready = await loadReplicaChatData({
      fetchQueryHistory: vi.fn().mockResolvedValue({
        items: [historyItem],
        store: { ready: true, backend: "SqlAlchemyQueryHistoryStore" }
      })
    });
    const degraded = await loadReplicaChatData({
      fetchQueryHistory: vi.fn().mockResolvedValue({
        items: [historyItem],
        store: { ready: false, backend: "memory" }
      })
    });

    expect(ready.data.historyItems[0]).toEqual(expect.objectContaining({
      id: "query-history-001",
      title: "医保基金审核依据",
      summary: "应核对证据链。",
      taskConvertible: true
    }));
    expect(degraded.outcome).toBe("degraded");
    expect(degraded.data.historyItems[0]?.taskConvertible).toBe(false);
  });

  it("preserves the successful agent lane as degraded when history fails", async () => {
    const result = await loadReplicaChatData({
      fetchAgents: vi.fn().mockResolvedValue(makeAgentsResponse(["first-id"])),
      fetchQueryHistory: vi.fn().mockRejectedValue(new Error("history unavailable"))
    });

    expect(result.source).toBe("api");
    expect(result.outcome).toBe("degraded");
    expect(result.data.agents).toHaveLength(1);
    expect(result.data.historyItems).toEqual([]);
    expect(result.data.historyItems).not.toEqual(referenceHistoryItems);
    expect(result.issues).toContainEqual(expect.objectContaining({ code: "api-read-failed" }));
  });

  it("retains reference history only when API reads are disabled", async () => {
    const result = await loadReplicaChatData();

    expect(result.source).toBe("fixture");
    expect(result.outcome).toBe("ready");
    expect(result.data.historyItems).toEqual(referenceHistoryItems);
  });
});

describe("replica backend read adapters", () => {
  it("uses fixture data only when API reads are disabled", async () => {
    const result = await loadReplicaProjectsData();

    expect(result.source).toBe("fixture");
    expect(result.outcome).toBe("ready");
    expect(result.data.projects).not.toEqual([]);
  });

  it("keeps a successful empty API collection empty", async () => {
    const result = await loadReplicaDocumentsData({
      fetchKnowledgeBaseCatalog: vi.fn().mockResolvedValue(emptyKnowledgeCatalog),
      fetchDocumentSourceCollections: vi.fn().mockResolvedValue(emptySourceCatalog),
      fetchQueryHistory: vi.fn().mockResolvedValue({
        items: [],
        store: { ready: true, backend: "test" }
      })
    });

    expect(result.outcome).toBe("empty");
    expect(result.source).toBe("api");
    expect(result.data.results).toEqual([]);
    expect(result.data.searchHistory).toEqual([]);
  });

  it("returns error without fixture substitution when an enabled API read fails", async () => {
    const result = await loadReplicaProjectsData({
      fetchProjects: vi.fn().mockRejectedValue(new Error("offline"))
    });

    expect(result.outcome).toBe("error");
    expect(result.source).toBe("api");
    expect(result.data.projects).toEqual([]);
    expect(result.issues).toContainEqual(expect.objectContaining({ code: "api-read-failed" }));
  });

  it("identifies failed reads by safe names without exposing raw exceptions", async () => {
    const secretError = "https://private.invalid/read?password=do-not-expose body=confidential";
    const result = await loadReplicaDocumentsData({
      fetchKnowledgeBaseCatalog: vi.fn().mockRejectedValue(new Error(secretError)),
      fetchDocumentSourceCollections: vi.fn().mockRejectedValue(new Error(secretError)),
      fetchQueryHistory: vi.fn().mockRejectedValue(new Error(secretError))
    });

    const failureMessages = result.issues
      .filter((item) => item.code === "api-read-failed")
      .map((item) => item.message);

    expect(failureMessages).toHaveLength(3);
    expect(failureMessages).toEqual(expect.arrayContaining([
      expect.stringContaining("knowledge-base-catalog"),
      expect.stringContaining("document-source-collections"),
      expect.stringContaining("query-history")
    ]));
    expect(failureMessages.join(" ")).not.toContain("password=do-not-expose");
    expect(failureMessages.join(" ")).not.toContain("body=confidential");
  });

  it("preserves a successful document catalog as degraded when history fails", async () => {
    const result = await loadReplicaDocumentsData({
      fetchDocumentSourceCollections: vi.fn().mockResolvedValue(metricBearingSourceCatalog),
      fetchQueryHistory: vi.fn().mockRejectedValue(new Error("history unavailable"))
    });

    expect(result.outcome).toBe("degraded");
    expect(result.data.categories).not.toEqual([]);
    expect(result.data.searchHistory).toEqual([]);
    expect(result.issues).toContainEqual(expect.objectContaining({ code: "api-read-failed" }));
  });

  it("keeps unknown document metrics distinct from a real zero", async () => {
    const unknownMetricCatalog: DocumentSourceCollectionCatalogResponse = {
      ...sourceCollectionCatalog,
      items: [
        {
          ...sourceCollectionCatalogItem,
          metrics: {
            ...sourceCollectionCatalogItem.metrics,
            document_count: null,
            chunk_count: null
          }
        }
      ]
    };
    const zeroMetricCatalog: DocumentSourceCollectionCatalogResponse = {
      ...sourceCollectionCatalog,
      items: [
        {
          ...sourceCollectionCatalogItem,
          metrics: {
            ...sourceCollectionCatalogItem.metrics,
            document_count: 0,
            chunk_count: 0
          }
        }
      ]
    };
    const chunkOnlyMetricCatalog: DocumentSourceCollectionCatalogResponse = {
      ...sourceCollectionCatalog,
      items: [
        {
          ...sourceCollectionCatalogItem,
          metrics: {
            ...sourceCollectionCatalogItem.metrics,
            document_count: null,
            chunk_count: 128
          }
        }
      ]
    };

    const unknown = await loadReplicaDocumentsData({
      fetchDocumentSourceCollections: vi.fn().mockResolvedValue(unknownMetricCatalog),
      fetchQueryHistory: vi.fn().mockResolvedValue(emptyQueryHistory)
    });
    const zero = await loadReplicaDocumentsData({
      fetchDocumentSourceCollections: vi.fn().mockResolvedValue(zeroMetricCatalog),
      fetchQueryHistory: vi.fn().mockResolvedValue(emptyQueryHistory)
    });
    const chunkOnly = await loadReplicaDocumentsData({
      fetchDocumentSourceCollections: vi.fn().mockResolvedValue(chunkOnlyMetricCatalog),
      fetchQueryHistory: vi.fn().mockResolvedValue(emptyQueryHistory)
    });

    expect(unknown.outcome).toBe("degraded");
    expect(unknown.data.categories[0]?.count).toBeNull();
    expect(unknown.issues).toContainEqual(expect.objectContaining({ code: "partial-schema-gap" }));
    expect(zero.outcome).toBe("ready");
    expect(zero.data.categories[0]?.count).toBe(0);
    expect(chunkOnly.outcome).toBe("degraded");
    expect(chunkOnly.data.categories[0]?.count).toBeNull();
    expect(chunkOnly.issues).toContainEqual(expect.objectContaining({ code: "partial-schema-gap" }));
  });

  it("preserves a successful knowledge catalog lane when another catalog read fails", async () => {
    const result = await loadReplicaKnowledgeBaseData({
      fetchKnowledgeBaseCatalog: vi.fn().mockRejectedValue(new Error("metrics unavailable")),
      fetchDocumentSourceCollections: vi.fn().mockResolvedValue(metricBearingSourceCatalog)
    });

    expect(result.outcome).toBe("degraded");
    expect(result.data.knowledgeBases).not.toEqual([]);
    expect(result.issues).toContainEqual(expect.objectContaining({ code: "api-read-failed" }));
  });

  it("preserves registry data as degraded when metrics are unavailable", async () => {
    const result = await loadReplicaKnowledgeBaseData({
      fetchKnowledgeBaseCatalog: vi.fn().mockResolvedValue(registryOnlyKnowledgeCatalog)
    });

    expect(result.source).toBe("api");
    expect(result.outcome).toBe("degraded");
    expect(result.data.knowledgeBases).not.toEqual([]);
    expect(result.data.knowledgeBases[0]?.documentCount).toBeNull();
    expect(result.data.knowledgeBases[0]?.chunkCount).toBeNull();
    expect(result.data.knowledgeBases[0]?.appCount).toBeNull();
    expect(result.data.knowledgeBases[0]?.tags.some((tag) => tag.includes("chunks"))).toBe(false);
    expect(result.data.currentSearchEmbeddingCount).toBeNull();
    expect(result.data.summary).toEqual({
      sourceCollectionCount: 1,
      queryableCollectionCount: 1,
      totalDocumentCount: null,
      totalChunkCount: null,
      totalEmbeddingCount: null,
      currentSearchEmbeddingCount: null,
      candidateChunkCount: null,
      domainCounts: { 医保: 1 }
    });
    expect(result.data.metricsSource).toBe("unavailable");
    expect(result.data.store).toEqual({
      ready: false,
      catalogReady: true,
      metricsReady: false,
      backend: "runtime_state_and_registry_only"
    });
    expect(result.data.boundaries).toEqual({
      productionWrite: false,
      providerCall: false,
      databaseWrite: false,
      objectStorageWrite: false,
      queryHistoryWrite: false,
      source: "runtime_state_and_registry_only"
    });
  });

  it("treats registry-only provenance as degraded even when readiness flags are true", async () => {
    const result = await loadReplicaKnowledgeBaseData({
      fetchKnowledgeBaseCatalog: vi.fn().mockResolvedValue(registryProvenanceOnlyKnowledgeCatalog),
      fetchDocumentSourceCollections: vi.fn().mockResolvedValue(metricBearingSourceCatalog)
    });

    expect(result.source).toBe("api");
    expect(result.outcome).toBe("degraded");
    expect(result.data.knowledgeBases).not.toEqual([]);
    expect(result.data.knowledgeBases[0]?.chunkCount).toBeNull();
    expect(result.data.knowledgeBases[0]?.tags.some((tag) => tag.includes("chunks"))).toBe(false);
    expect(result.data.currentSearchEmbeddingCount).toBeNull();
    expect(result.data.metricsSource).toBe("unavailable");
  });

  it("does not expose partial search metrics without the knowledge catalog", async () => {
    const result = await loadReplicaKnowledgeBaseData({
      fetchDocumentSourceCollections: vi.fn().mockResolvedValue(metricBearingSourceCatalog)
    });

    expect(result.source).toBe("api");
    expect(result.outcome).toBe("degraded");
    expect(result.data.knowledgeBases).not.toEqual([]);
    expect(result.data.knowledgeBases[0]?.documentCount).toBeNull();
    expect(result.data.knowledgeBases[0]?.chunkCount).toBeNull();
    expect(result.data.knowledgeBases[0]?.appCount).toBeNull();
    expect(result.data.currentSearchEmbeddingCount).toBeNull();
    expect(result.data.metricsSource).toBe("unavailable");
    expect(result.data.summary).toBeNull();
    expect(result.data.store).toBeNull();
    expect(result.data.boundaries).toBeNull();
  });

  it("marks an empty source-only catalog degraded when the knowledge catalog is absent", async () => {
    const result = await loadReplicaKnowledgeBaseData({
      fetchDocumentSourceCollections: vi.fn().mockResolvedValue(emptySourceCatalog)
    });

    expect(result.source).toBe("api");
    expect(result.outcome).toBe("degraded");
    expect(result.data.knowledgeBases).toEqual([]);
    expect(result.data.currentSearchEmbeddingCount).toBeNull();
    expect(result.data.metricsSource).toBe("unavailable");
    expect(result.data.summary).toBeNull();
    expect(result.data.store).toBeNull();
    expect(result.data.boundaries).toBeNull();
  });

  it("keeps zero metrics ready when the catalog and search backend are ready", async () => {
    const result = await loadReplicaKnowledgeBaseData({
      fetchKnowledgeBaseCatalog: vi.fn().mockResolvedValue(readyZeroMetricKnowledgeCatalog)
    });

    expect(result.outcome).toBe("ready");
    expect(result.data.knowledgeBases[0]?.chunkCount).toBe(0);
    expect(result.data.currentSearchEmbeddingCount).toBe(0);
    expect(result.data.metricsSource).toBe("knowledge-base-catalog");
  });

  it("does not substitute fixture groups for an API catalog without selectable items", async () => {
    const result = await loadReplicaKnowledgeBaseData({
      fetchKnowledgeBaseCatalog: vi.fn().mockResolvedValue(unavailableKnowledgeCatalog)
    });

    expect(result.outcome).toBe("empty");
    expect(result.data.knowledgeBases).toEqual([]);
    expect(result.data.sourceGroups).toEqual([]);
  });

  it("starts knowledge-base permissions and both catalog reads in the same load pass", async () => {
    const humanLabel = "医院医保审计依据库";
    const permissionsFallbackLabel = "权限目录回退标签-不得采用";
    const sourceCatalogFallbackLabel = "来源目录回退标签-不得采用";
    const internalSource = "medical-insurance-laws" as const;
    const internalAccess = "explicit-read-all" as const;
    const fetchDocumentPermissions = vi.fn(async () => ({
      role: "admin",
      source_collections: [
        {
          source_collection: internalSource,
          label: permissionsFallbackLabel,
          scope: "系统",
          access: internalAccess
        }
      ],
      upload_permissions: uploadPermissions
    }));
    const fetchKnowledgeBaseCatalog = vi.fn(async (): Promise<KnowledgeBaseCatalogResponse> => ({
      ...knowledgeBaseCatalog,
      items: [{
        ...catalogItem,
        source_collection: internalSource,
        label: humanLabel,
        access: internalAccess
      }]
    }));
    const fetchDocumentSourceCollections = vi.fn(async (): Promise<DocumentSourceCollectionCatalogResponse> => ({
      ...sourceCollectionCatalog,
      items: [{
        ...sourceCollectionCatalogItem,
        source_collection: internalSource,
        label: sourceCatalogFallbackLabel,
        access: internalAccess
      }]
    }));

    const result = await loadReplicaKnowledgeBaseData({
      fetchDocumentPermissions,
      fetchKnowledgeBaseCatalog,
      fetchDocumentSourceCollections
    });

    expect(result.source).toBe("api");
    expect(result.outcome).toBe("ready");
    expect(result.data.knowledgeBases[0]).toMatchObject({
      id: `kb-${internalSource}`,
      name: humanLabel
    });
    expect(result.data.knowledgeBases[0]).not.toHaveProperty("source_collection");
    expect(result.data.knowledgeBases[0]).not.toHaveProperty("access");
    expect(result.data.knowledgeBases[0]?.name).not.toBe(permissionsFallbackLabel);
    expect(result.data.knowledgeBases[0]?.name).not.toBe(sourceCatalogFallbackLabel);
    expect(result.data.sourceGroups[0]?.options[0]).toMatchObject({
      value: internalSource,
      label: humanLabel
    });
    expect(result.data.knowledgeBases[0]?.documentCount).toBe(12);
    expect(result.data.knowledgeBases[0]?.chunkCount).toBe(120);
    expect(result.data.knowledgeBases[0]?.appCount).toBe(2);
    expect(result.data.currentSearchEmbeddingCount).toBe(49051);
    expect(result.data.summary).toEqual({
      sourceCollectionCount: 1,
      queryableCollectionCount: 1,
      totalDocumentCount: 12,
      totalChunkCount: 120,
      totalEmbeddingCount: 120,
      currentSearchEmbeddingCount: 49051,
      candidateChunkCount: 0,
      domainCounts: { 医保: 1 }
    });
    expect(result.data.metricsSource).toBe("knowledge-base-catalog");
    expect(result.data.store).toEqual({
      ready: true,
      catalogReady: true,
      metricsReady: true,
      backend: "runtime_state_and_postgres_catalog"
    });
    expect(result.data.boundaries).toEqual({
      productionWrite: false,
      providerCall: false,
      databaseWrite: false,
      objectStorageWrite: false,
      queryHistoryWrite: false,
      source: "runtime_state_and_postgres_catalog"
    });
    expect(fetchDocumentPermissions).toHaveBeenCalledTimes(1);
    expect(fetchKnowledgeBaseCatalog).toHaveBeenCalledTimes(1);
    expect(fetchDocumentSourceCollections).toHaveBeenCalledTimes(1);
  });

  it("starts document catalog and query history reads in the same load pass", async () => {
    const fetchKnowledgeBaseCatalog = vi.fn(async () => knowledgeBaseCatalog);
    const fetchDocumentSourceCollections = vi.fn(async () => sourceCollectionCatalog);
    const fetchQueryHistory = vi.fn(async () => ({
      items: [
        {
          id: "query-1",
          user_identifier: "auditor",
          question: "医保法规查询",
          filters: {},
          answer_summary: null,
          retrieved_chunk_ids: [],
          citation_count: 0,
          created_at: "2026-07-08T00:00:00Z"
        }
      ],
      store: { ready: true, backend: "SqlAlchemyQueryHistoryStore" }
    }));

    const result = await loadReplicaDocumentsData({
      fetchKnowledgeBaseCatalog,
      fetchDocumentSourceCollections,
      fetchQueryHistory
    });

    expect(result.source).toBe("api");
    expect(result.outcome).toBe("ready");
    expect(result.data.categories[0]?.name).toBe("医保法规库");
    expect(result.data.searchHistory).toContain("医保法规查询");
    expect(result.data.results).toEqual([]);
    expect(fetchKnowledgeBaseCatalog).toHaveBeenCalledTimes(1);
    expect(fetchDocumentSourceCollections).toHaveBeenCalledTimes(1);
    expect(fetchQueryHistory).toHaveBeenCalledTimes(1);
  });

  it("maps graph workbench API nodes instead of falling back to the old fixture graph", async () => {
    const fetchGraphWorkbench = vi.fn(async () => graphWorkbench);

    const result = await loadReplicaGraphData({ fetchGraphWorkbench });

    expect(result.source).toBe("api");
    expect(result.outcome).toBe("ready");
    expect(result.data.title).toBe("医疗审计知识工程");
    expect(result.data.nodes).toHaveLength(2);
    expect(result.data.nodes[0]?.label).toBe("医疗审计知识工程");
    expect(result.data.relations[0]?.target).toBe("医疗医保知识");
    expect(result.issues).toEqual([]);
    expect(fetchGraphWorkbench).toHaveBeenCalledTimes(1);
  });

  it("preserves project evidence-chain metadata and treats a root-only chain as empty", async () => {
    const projectGraph = {
      ...graphWorkbench,
      graph_id: "PROJECT-A",
      graph_title: "项目 A 项目证据链",
      graph_scope: "仅组织当前项目已持久化的疑点、复核、报告和整改证据。",
      view: "project",
      project_key: "PROJECT-A",
      evidence_chain_status: "empty",
      evidence_grade: "live-store-readonly",
      nodes: [
        {
          ...graphWorkbench.nodes[0],
          id: "project:PROJECT-A",
          label: "项目 A",
          href: "/projects?project=PROJECT-A",
          metric: "0 条项目证据"
        }
      ],
      relations: [],
      metrics: {
        ...graphWorkbench.metrics,
        node_count: 1,
        node_kind_count: 1,
        relation_count: 0,
        strong_relation_count: 0,
        pending_relation_count: 0
      },
      store: {
        ready: true,
        backend: {
          audit_findings: "SqlAlchemyAuditFindingStore",
          review_tasks: "JsonReviewTaskStore"
        }
      }
    } as unknown as GraphWorkbenchResponse;
    const fetchGraphWorkbench = vi.fn(async () => projectGraph);

    const result = await loadReplicaGraphData(
      { fetchGraphWorkbench },
      { view: "project", projectKey: "PROJECT-A" }
    );

    expect(fetchGraphWorkbench).toHaveBeenCalledWith({ view: "project", projectKey: "PROJECT-A" });
    expect(result.source).toBe("api");
    expect(result.outcome).toBe("empty");
    expect(result.data).toMatchObject({
      view: "project",
      projectKey: "PROJECT-A",
      evidenceChainStatus: "empty",
      evidenceGrade: "live-store-readonly",
      productionSideEffect: "none",
      store: projectGraph.store
    });
    expect(result.data.nodes).toHaveLength(1);
    expect(result.data.nodes[0]?.label).toBe("项目 A");
  });

  it("never substitutes the knowledge fixture when a project graph read is disabled or fails", async () => {
    const disabled = await loadReplicaGraphData({}, { view: "project", projectKey: "PROJECT-A" });
    const failed = await loadReplicaGraphData(
      {
        fetchGraphWorkbench: vi.fn(async () => {
          throw Object.assign(new Error("not visible"), { status: 404 });
        })
      },
      { view: "project", projectKey: "PROJECT-A" }
    );

    expect(disabled.source).toBe("api");
    expect(disabled.outcome).toBe("empty");
    expect(disabled.data.nodes).toEqual([]);
    expect(failed.source).toBe("api");
    expect(failed.outcome).toBe("error");
    expect(failed.data.nodes).toEqual([]);
    expect(failed.issues[0]).toMatchObject({ code: "api-read-failed", status: 404 });
  });

  it("fails closed when a project graph response belongs to another project", async () => {
    const mismatched = {
      ...graphWorkbench,
      view: "project",
      project_key: "PROJECT-B",
      evidence_chain_status: "ready",
      evidence_grade: "live-store-readonly",
      store: {
        ready: true,
        backend: { audit_findings: "SqlFindingStore", review_tasks: "JsonReviewStore" }
      }
    } as unknown as GraphWorkbenchResponse;

    const result = await loadReplicaGraphData(
      { fetchGraphWorkbench: vi.fn(async () => mismatched) },
      { view: "project", projectKey: "PROJECT-A" }
    );

    expect(result.outcome).toBe("error");
    expect(result.data.projectKey).toBe("PROJECT-A");
    expect(result.data.nodes).toEqual([]);
    expect(result.issues[0]?.message).toContain("did not match");
  });

  it("keeps a not-ready project store degraded without fixture substitution", async () => {
    const degraded = {
      ...graphWorkbench,
      view: "project",
      project_key: "PROJECT-A",
      evidence_chain_status: "ready",
      evidence_grade: "live-store-readonly",
      store: {
        ready: false,
        backend: { audit_findings: "SqlFindingStore", review_tasks: "JsonReviewStore" }
      }
    } as unknown as GraphWorkbenchResponse;

    const result = await loadReplicaGraphData(
      { fetchGraphWorkbench: vi.fn(async () => degraded) },
      { view: "project", projectKey: "PROJECT-A" }
    );

    expect(result.source).toBe("api");
    expect(result.outcome).toBe("degraded");
    expect(result.data.nodes[0]?.label).toBe("医疗审计知识工程");
    expect(result.data.nodes.some((node) => node.label.includes("乡村振兴"))).toBe(false);
  });

  it("does not substitute reference analytics datasets when the API read is disabled or fails", async () => {
    const disabled = await loadReplicaAnalyticsData();
    const failed = await loadReplicaAnalyticsData({
      fetchAnalysisUploadHistory: vi.fn(async () => {
        throw new Error("history unavailable");
      })
    });

    expect(disabled.source).toBe("api");
    expect(disabled.outcome).toBe("empty");
    expect(disabled.data).toEqual({ datasets: [], store: null });
    expect(disabled.issues.some((item) => item.code === "mutation-gated")).toBe(false);
    expect(failed.source).toBe("api");
    expect(failed.outcome).toBe("error");
    expect(failed.data).toEqual({ datasets: [], store: null });
  });

  it("maps real analytics history status and store readiness without fixture fallback", async () => {
    const response: TableAnalysisUploadHistoryResponse = {
      items: [
        {
          id: "analytics-real-1",
          name: "真实收费.csv",
          extension: "csv",
          size_bytes: 0,
          size_kb: 0,
          sha256: "c".repeat(64),
          sheet_name: null,
          row_count: 0,
          column_count: 0,
          empty_cell_count: 0,
          duplicate_row_count: 0,
          status: "parsed",
          created_by: null,
          created_at: "2026-07-12T10:00:00Z",
          retention_status: "retained",
          audit_signals: []
        }
      ],
      store: { ready: false, backend: "none" }
    };

    const result = await loadReplicaAnalyticsData({
      fetchAnalysisUploadHistory: vi.fn(async () => response)
    });

    expect(result.source).toBe("api");
    expect(result.outcome).toBe("degraded");
    expect(result.data.store).toEqual(response.store);
    expect(result.data.datasets).toEqual([
      expect.objectContaining({ id: "analytics-real-1", rows: 0, columns: 0, status: "已解析" })
    ]);
    expect(result.data.datasets.some((item) => item.name.includes("参考"))).toBe(false);
  });
});
