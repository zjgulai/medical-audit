import { describe, expect, it, vi } from "vitest";

import type {
  AgentsResponse,
  DocumentSourceCollectionCatalogResponse,
  GraphWorkbenchResponse,
  KnowledgeBaseCatalogItem,
  KnowledgeBaseCatalogResponse
} from "./api-types";
import {
  loadReplicaAgentMarketData,
  loadReplicaDocumentsData,
  loadReplicaGraphData,
  loadReplicaKnowledgeBaseData
} from "./replica-adapters";
import { referenceMarketAgents } from "./reference-replica-data";

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
    source: "runtime_state_and_registry_only"
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
  it("keeps the market catalog on prompt-source categories when the API returns old seed agents", async () => {
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

    expect(fetchAgents).toHaveBeenCalledTimes(1);
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

describe("replica backend read adapters", () => {
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

    expect(result.source).toBe("hybrid");
    expect(result.data.categories[0]?.name).toBe("医保法规库");
    expect(result.data.searchHistory).toContain("医保法规查询");
    expect(fetchKnowledgeBaseCatalog).toHaveBeenCalledTimes(1);
    expect(fetchDocumentSourceCollections).toHaveBeenCalledTimes(1);
    expect(fetchQueryHistory).toHaveBeenCalledTimes(1);
  });

  it("maps graph workbench API nodes instead of falling back to the old fixture graph", async () => {
    const fetchGraphWorkbench = vi.fn(async () => graphWorkbench);

    const result = await loadReplicaGraphData({ fetchGraphWorkbench });

    expect(result.source).toBe("api");
    expect(result.data.title).toBe("医疗审计知识工程");
    expect(result.data.nodes).toHaveLength(2);
    expect(result.data.nodes[0]?.label).toBe("医疗审计知识工程");
    expect(result.data.relations[0]?.target).toBe("医疗医保知识");
    expect(result.issues).toEqual([]);
    expect(fetchGraphWorkbench).toHaveBeenCalledTimes(1);
  });
});
