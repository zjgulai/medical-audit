import { afterEach, describe, expect, it, vi } from "vitest";

import {
  fetchAuditFindings,
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
});
