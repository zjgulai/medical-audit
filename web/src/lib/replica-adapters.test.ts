import { describe, expect, it, vi } from "vitest";

import type {
  AgentsResponse,
  AuditAgentApiItem,
  DocumentSourceCollectionCatalogResponse,
  GraphWorkbenchResponse,
  KnowledgeBaseCatalogItem,
  KnowledgeBaseCatalogResponse,
  QueryHistoryResponse
} from "./api-types";
import {
  loadReplicaAgentMarketData,
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
    current_search_embedding_count: 120,
    candidate_chunk_count: 0,
    domain_counts: { 医保: 1 }
  },
  items: [catalogItem],
  search_backend: { ready: true, backend: "postgres", details: {} },
  store: { ready: true, backend: "runtime_state_and_postgres_catalog" },
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
    total_chunk_count: 120,
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
        chunk_count: 120,
        character_count: 0,
        linked_app_count: 0,
        embedding_count: 0,
        active_embedding_count: 0,
        candidate_chunk_count: 0
      },
      index: {
        ...catalogItem.index,
        search_backend_ready: false
      }
    }
  ],
  search_backend: { ready: false, backend: "unavailable", details: {} },
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
  it("keeps the market catalog independent from personal agent API reads", async () => {
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
    expect(result.data.agents).toHaveLength(referenceMarketAgents.length);
    expect(result.data.categories).toEqual([
      "财务收支审计",
      "采购招标审计",
      "工程审计",
      "工具智能体",
      "固定资产审计",
      "审计科研"
    ]);
    expect(result.data.categories).not.toContain("业务类");
    expect(result.data.agents.some((agent) => agent.id === "seed-legacy-business")).toBe(false);
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

  it("returns an error with no reference history when the API history read fails", async () => {
    const result = await loadReplicaChatData({
      fetchAgents: vi.fn().mockResolvedValue(makeAgentsResponse(["first-id"])),
      fetchQueryHistory: vi.fn().mockRejectedValue(new Error("history unavailable"))
    });

    expect(result.source).toBe("api");
    expect(result.outcome).toBe("error");
    expect(result.data.historyItems).toEqual([]);
    expect(result.data.historyItems).not.toEqual(referenceHistoryItems);
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

  it("preserves registry data as degraded when metrics are unavailable", async () => {
    const result = await loadReplicaKnowledgeBaseData({
      fetchKnowledgeBaseCatalog: vi.fn().mockResolvedValue(registryOnlyKnowledgeCatalog)
    });

    expect(result.source).toBe("api");
    expect(result.outcome).toBe("degraded");
    expect(result.data.knowledgeBases).not.toEqual([]);
    expect(result.data.knowledgeBases[0]?.chunkCount).toBeNull();
    expect(result.data.knowledgeBases[0]?.tags.some((tag) => tag.includes("chunks"))).toBe(false);
    expect(result.data.currentSearchEmbeddingCount).toBeNull();
    expect(result.data.metricsSource).toBe("unavailable");
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
    const fetchDocumentPermissions = vi.fn(async () => ({
      role: "admin",
      source_collections: [
        {
          source_collection: "medical-insurance-laws" as const,
          label: "医保法规库",
          scope: "系统",
          access: "read" as const
        }
      ],
      upload_permissions: uploadPermissions
    }));
    const fetchKnowledgeBaseCatalog = vi.fn(async () => knowledgeBaseCatalog);
    const fetchDocumentSourceCollections = vi.fn(async () => sourceCollectionCatalog);

    const result = await loadReplicaKnowledgeBaseData({
      fetchDocumentPermissions,
      fetchKnowledgeBaseCatalog,
      fetchDocumentSourceCollections
    });

    expect(result.source).toBe("api");
    expect(result.outcome).toBe("ready");
    expect(result.data.knowledgeBases[0]?.name).toBe("医保法规库");
    expect(result.data.knowledgeBases[0]?.chunkCount).toBe(120);
    expect(result.data.currentSearchEmbeddingCount).toBe(120);
    expect(result.data.metricsSource).toBe("knowledge-base-catalog");
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
});
