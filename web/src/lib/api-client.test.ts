import { afterEach, describe, expect, it, vi } from "vitest";

import {
  createAuditAgent,
  fetchAuditFindings,
  fetchAgents,
  fetchBackendHealth,
  fetchSearchBackendStatus,
  runKnowledgeQuery
} from "./api-client";

describe("api-client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("fetches backend health through the Next proxy", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          status: "ok",
          version: "0.1.0",
          data_root: "/tmp/data"
        })
      }))
    );

    const health = await fetchBackendHealth();

    expect(fetch).toHaveBeenCalledWith("/api/backend/health", {
      headers: { Accept: "application/json" },
      cache: "no-store"
    });
    expect(health.status).toBe("ok");
  });

  it("raises a clear error when the search backend check fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: false,
        status: 409,
        text: async () => "search engine is not initialized"
      }))
    );

    await expect(fetchSearchBackendStatus()).rejects.toThrow(
      "Backend request failed: GET /api/backend/index/search-backend returned 409"
    );
  });

  it("raises a boundary error when called outside the browser proxy runtime", async () => {
    vi.stubGlobal("window", undefined);

    await expect(fetchBackendHealth()).rejects.toThrow(
      "Backend proxy client must be called from browser/client code; server code needs an absolute backend URL."
    );
  });

  it("posts knowledge query requests through the versioned API proxy", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          question: "医保基金审核依据",
          answer: "应核验证据链。",
          confidence: "high",
          fallback_used: true,
          basis_groups: [],
          citations: [],
          query_log_index: 0
        })
      }))
    );

    const result = await runKnowledgeQuery({
      question: "医保基金审核依据",
      top_k: 5,
      source_collections: ["medical-insurance-laws"]
    });

    expect(fetch).toHaveBeenCalledWith("/api/v1/query", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "X-Role": "auditor",
        "X-User-Id": "next-knowledge-query"
      },
      body: JSON.stringify({
        question: "医保基金审核依据",
        top_k: 5,
        source_collections: ["medical-insurance-laws"]
      }),
      cache: "no-store"
    });
    expect(result.answer).toBe("应核验证据链。");
  });

  it("fetches audit findings with an optional review status filter", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          items: [],
          stats: { total: 0, open: 0, pending_review: 0, linked_review_task: 0 },
          filters: { review_status: "pending-review", limit: 100 },
          review_status_options: { "pending-review": "待复核" },
          generation_readiness: {
            status: "blocked",
            ready: false,
            has_findings: false,
            table_counts: { audit_findings: 0 },
            prerequisites: [],
            blocking_reasons: [],
            next_actions: []
          },
          store: { ready: true, backend: "SqlAlchemyAuditFindingStore" }
        })
      }))
    );

    const result = await fetchAuditFindings("pending-review");

    expect(fetch).toHaveBeenCalledWith("/api/v1/audit-findings?review_status=pending-review", {
      headers: { Accept: "application/json" },
      cache: "no-store"
    });
    expect(result.filters.review_status).toBe("pending-review");
  });

  it("fetches audit agents through the versioned API proxy", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          items: [
            {
              id: "agent-citation-check",
              name: "引用依据核验助手",
              category: "业务类",
              topic: "医保基金使用合规",
              prompt: "只基于引用回答。",
              knowledge_base: "系统医保审计知识库",
              project_name: "医保基金使用合规专项自查",
              status: "active",
              created_by: "system",
              updated_at: "2026-06-12",
              source: "system-default",
              metadata: {}
            }
          ],
          categories: ["业务类", "效率类", "研究类"],
          store: { ready: true, backend: "SqlAlchemyAgentStore" }
        })
      }))
    );

    const result = await fetchAgents();

    expect(fetch).toHaveBeenCalledWith("/api/v1/agents", {
      headers: { Accept: "application/json" },
      cache: "no-store"
    });
    expect(result.items[0].id).toBe("agent-citation-check");
  });

  it("creates audit agents through the versioned API proxy", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          item: {
            id: "agent-custom-001",
            name: "目录限制核验助手",
            category: "业务类",
            topic: "医保目录限制条件核验",
            prompt: "仅基于目录限制字段输出待补证问题。",
            knowledge_base: "医保目录库",
            project_name: "医保目录限制条件核验",
            status: "active",
            created_by: "next-knowledge-query",
            updated_at: "2026-06-14T00:00:00Z",
            source: "custom",
            metadata: {}
          },
          store: { ready: true, backend: "SqlAlchemyAgentStore" }
        })
      }))
    );

    const result = await createAuditAgent({
      name: "目录限制核验助手",
      category: "业务类",
      topic: "医保目录限制条件核验",
      prompt: "仅基于目录限制字段输出待补证问题。",
      knowledge_base: "医保目录库",
      project_name: "医保目录限制条件核验"
    });

    expect(fetch).toHaveBeenCalledWith("/api/v1/agents", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "X-Role": "auditor",
        "X-User-Id": "next-knowledge-query"
      },
      body: JSON.stringify({
        name: "目录限制核验助手",
        category: "业务类",
        topic: "医保目录限制条件核验",
        prompt: "仅基于目录限制字段输出待补证问题。",
        knowledge_base: "医保目录库",
        project_name: "医保目录限制条件核验"
      }),
      cache: "no-store"
    });
    expect(result.item.id).toBe("agent-custom-001");
  });
});
