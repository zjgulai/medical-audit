import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { afterEach, describe, expect, it, vi } from "vitest";

import {
  analyzeChatAttachment,
  createContractAuditJob,
  createAuditAgent,
  createAuditAgentPromptVersion,
  createProject,
  createProjectMember,
  createQueryHistoryReviewTask,
  fetchAnalysisUploadHistory,
  fetchArchiveWorkbench,
  fetchAuthSession,
  fetchAuditFindings,
  fetchAuditAgent,
  fetchAuditAgentFeedback,
  fetchAuditAgentInvocations,
  fetchAgents,
  fetchAgentMarketCatalog,
  fetchAuditAgentPromptVersions,
  fetchBackendHealth,
  fetchDocumentPermissions,
  fetchDocumentSourceCollections,
  fetchDocumentUploads,
  fetchGraphWorkbench,
  fetchKnowledgeBaseCatalog,
  fetchOcrCapabilities,
  fetchProjectDashboard,
  fetchProjectMembers,
  fetchProjects,
  fetchQueryModels,
  fetchQueryHistory,
  fetchRemediationWorkbench,
  fetchReportWorkbench,
  fetchRulesWorkbench,
  fetchSearchBackendStatus,
  installAuditAgentMarketTemplate,
  extractOcrText,
  rollbackAuditAgentPromptVersion,
  indexPersonalDocument,
  recordAuditAgentInvocation,
  reviewAuditAgentPromptVersion,
  runKnowledgeQuery,
  searchDocuments,
  submitAuditAgentFeedback,
  updateAuditAgentLifecycle,
  updateDocumentUploadGovernance,
  uploadAnalysisTable,
  uploadPersonalDocument
} from "./api-client";

type PageBackendEndpointContract = {
  readonly name: string;
  readonly method: "GET" | "POST";
  readonly path: string;
  readonly sample_body?: Record<string, unknown>;
};

type PageBackendContract = {
  readonly contract_version: "frontend-backend-page-contract-v1";
  readonly boundaries: {
    readonly ui_style_change: false;
    readonly production_write: false;
    readonly provider_call: false;
    readonly database_write: false;
    readonly scope: "local_acceptance_and_frontend_contract_only";
  };
  readonly pages: readonly {
    readonly page_id: string;
    readonly route: string;
    readonly connection_status: "connected_first_batch" | "static_shell_first_batch";
    readonly endpoints: readonly PageBackendEndpointContract[];
  }[];
};

const pageBackendContract = JSON.parse(
  readFileSync(
    resolve(process.cwd(), "../docs/api/frontend-backend-page-contract.json"),
    "utf-8"
  )
) as PageBackendContract;

describe("api-client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    window.localStorage.removeItem("medical-audit-current-role");
  });

  it("keeps the page backend contract aligned with proxy-local API paths", () => {
    const expectedRoutes = new Set([
      "/workspace",
      "/chat",
      "/knowledge-query",
      "/agents",
      "/agent-market",
      "/knowledge-base",
      "/documents",
      "/analytics",
      "/graph",
      "/rules",
      "/reports",
      "/projects",
      "/findings",
      "/remediation",
      "/archive",
      "/fund-compliance",
      "/fund-compliance/review",
      "/guided-check"
    ]);
    const contractRoutes = new Set(pageBackendContract.pages.map((page) => page.route));
    for (const route of expectedRoutes) {
      expect(contractRoutes.has(route)).toBe(true);
    }

    const endpointPaths = new Set(
      pageBackendContract.pages.flatMap((page) => page.endpoints.map((endpoint) => endpoint.path))
    );
    expect([...endpointPaths]).toEqual(
      expect.arrayContaining([
        "/api/backend/health",
        "/api/backend/index/search-backend",
        "/api/v1/auth/session",
        "/api/v1/query",
        "/api/v1/query/models",
        "/api/v1/query/logs?limit=8",
        "/api/v1/chat/attachments/analyze",
        "/api/v1/audit-findings",
        "/api/v1/reports/workbench",
        "/api/v1/graph/workbench",
        "/api/v1/rules/workbench",
        "/api/v1/remediation/workbench",
        "/api/v1/archive/workbench",
        "/api/v1/analytics/table-uploads",
        "/api/v1/knowledge-base/catalog",
        "/api/v1/documents/source-collections",
        "/api/v1/documents/permissions",
        "/api/v1/documents/uploads",
        "/api/v1/agents",
        "/api/v1/agents/{agentId}",
        "/api/v1/agents/{agentId}/prompt-versions",
        "/api/v1/agents/{agentId}/invocations",
        "/api/v1/agents/{agentId}/feedback",
        "/api/v1/projects",
        "/api/v1/projects/{projectId}/dashboard",
        "/api/v1/projects/{projectId}/members"
      ])
    );
    expect([...endpointPaths].some((path) => (
      path.startsWith("/api/v1/documents/search?") && path.includes("q=")
    ))).toBe(true);

    for (const page of pageBackendContract.pages) {
      for (const endpoint of page.endpoints) {
        expect(endpoint.path.startsWith("/api/")).toBe(true);
        expect(endpoint.path.startsWith("http://")).toBe(false);
        expect(endpoint.path.startsWith("https://")).toBe(false);
        if (endpoint.method === "POST") {
          expect(endpoint.sample_body).toBeDefined();
        }
      }
    }
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
          contract_version: "knowledge-query-contract-v2",
          question: "医保基金审核依据",
          answer: "应核验证据链。",
          confidence: "high",
          fallback_used: true,
          generation_status: "not_requested",
          generation_failure_code: null,
          generation_http_status: null,
          effective_source_collections: ["medical-insurance-laws"],
          basis_groups: [],
          citations: [],
          personal_upload_matches: [],
          query_log_index: 0,
          query_log_id: "query-history-chat-001",
          agent_invocation_id: "agent-invocation-chat-001"
        })
      }))
    );

    const result = await runKnowledgeQuery({
      question: "医保基金审核依据",
      top_k: 5,
      source_collections: ["medical-insurance-laws", "medical-insurance-catalog"],
      topic: "medical-insurance-fund",
      agent: "agent-installed-catalog-001",
      model: "kimi-2.7"
    });

    expect(fetch).toHaveBeenCalledWith("/api/v1/query", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "X-Role": "admin",
        "X-Tenant-Id": "hospital-demo",
        "X-User-Id": "next-admin"
      },
      body: JSON.stringify({
        question: "医保基金审核依据",
        top_k: 5,
        source_collections: ["medical-insurance-laws", "medical-insurance-catalog"],
        topic: "medical-insurance-fund",
        agent: "agent-installed-catalog-001",
        model: "kimi-2.7"
      }),
      cache: "no-store"
    });
    expect(result.answer).toBe("应核验证据链。");
    expect(result.agent_invocation_id).toBe("agent-invocation-chat-001");
  });

  it("fetches chat model catalog through the versioned API proxy", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          contract_version: "chat-model-catalog-v1",
          default_model: "kimi-2.7",
          items: [
            {
              alias: "kimi-2.7",
              label: "Kimi K2.6（兼容别名）",
              provider: "kimi",
              available: true,
              default: true,
              unavailable_reason: null
            },
            {
              alias: "deepseek-v4-pro",
              label: "DeepSeek V4 Pro",
              provider: null,
              available: false,
              default: false,
              unavailable_reason: "missing_api_key_env"
            }
          ],
          boundaries: {
            production_write: false,
            provider_call: false,
            secret_values_reported: false,
            source: "environment_capability_probe_only"
          }
        })
      }))
    );

    const result = await fetchQueryModels();

    expect(fetch).toHaveBeenCalledWith("/api/v1/query/models", {
      headers: {
        Accept: "application/json",
        "X-Role": "admin",
        "X-Tenant-Id": "hospital-demo",
        "X-User-Id": "next-admin"
      },
      cache: "no-store"
    });
    expect(result.default_model).toBe("kimi-2.7");
    expect(result.items[0].available).toBe(true);
  });

  it("posts chat attachment analysis through the versioned API proxy", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          contract_version: "chat-attachment-analysis-v1",
          file_name: "charges.csv",
          extension: "csv",
          mode: "table-analysis",
          model_alias: "kimi-2.7",
          model_status: "selected_provider",
          answer: "已完成分析 [C1]。",
          extracted_preview: "字段：charge_amount",
          summary_items: ["行数：2"],
          boundaries: {
            database_write: false,
            object_storage_write: false,
            index_write: false,
            provider_call: true
          }
        })
      }))
    );
    const file = new File(["charge_amount\n100"], "charges.csv", { type: "text/csv" });

    const result = await analyzeChatAttachment(file, { model: "kimi-2.7", mode: "auto" });

    expect(fetch).toHaveBeenCalledWith("/api/v1/chat/attachments/analyze", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "X-Role": "admin",
        "X-Tenant-Id": "hospital-demo",
        "X-User-Id": "next-admin"
      },
      body: expect.any(FormData),
      cache: "no-store"
    });
    const formData = vi.mocked(fetch).mock.calls[0]?.[1]?.body as FormData;
    expect(formData.get("file")).toBe(file);
    expect(formData.get("model")).toBe("kimi-2.7");
    expect(formData.get("mode")).toBe("auto");
    expect(result.mode).toBe("table-analysis");
  });

  it("omits the chat attachment model when the selected alias is unavailable", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          contract_version: "chat-attachment-analysis-v1",
          file_name: "charges.csv",
          extension: "csv",
          mode: "table-analysis",
          model_alias: null,
          model_status: "default_fallback",
          answer: "已用默认附件解析完成。",
          extracted_preview: "字段：charge_amount",
          summary_items: ["行数：2"],
          boundaries: {
            database_write: false,
            object_storage_write: false,
            index_write: false,
            provider_call: false
          }
        })
      }))
    );
    const file = new File(["charge_amount\n100"], "charges.csv", { type: "text/csv" });

    const result = await analyzeChatAttachment(file, { model: null, mode: "auto" });

    const formData = vi.mocked(fetch).mock.calls[0]?.[1]?.body as FormData;
    expect(formData.get("file")).toBe(file);
    expect(formData.has("model")).toBe(false);
    expect(formData.get("mode")).toBe("auto");
    expect(result.model_alias).toBeNull();
    expect(result.boundaries.provider_call).toBe(false);
  });

  it("creates a persistent contract audit job with the selected model", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          contract_version: "contract-audit-job-v2",
          job_id: "contract-audit-0123456789abcdef0123456789abcdef",
          status: "completed",
          downloads: { json: "/j", markdown: "/m", docx: "/d" }
        })
      }))
    );
    const file = new File(["%PDF-1.4"], "采购合同.pdf", { type: "application/pdf" });

    const result = await createContractAuditJob(file, {
      projectName: "采购合同专项",
      model: "deepseek-v4-pro"
    });

    expect(fetch).toHaveBeenCalledWith("/api/v1/contract-audits", expect.objectContaining({
      method: "POST",
      body: expect.any(FormData)
    }));
    const formData = vi.mocked(fetch).mock.calls[0]?.[1]?.body as FormData;
    expect(formData.get("file")).toBe(file);
    expect(formData.get("project_name")).toBe("采购合同专项");
    expect(formData.get("model")).toBe("deepseek-v4-pro");
    expect(result.status).toBe("completed");
  });

  it("reads OCR capability without a write and extracts a page-mapped file", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          contract_version: "unlimited-ocr-capability-v1",
          enabled: true,
          engine: "baidu/Unlimited-OCR",
          source_commit: "d49ff64afffc1f47ab563dc1c589bc2f78808fa4",
          supported_extensions: ["pdf", "png"],
          max_upload_bytes: 40 * 1024 * 1024,
          max_pages: 40,
          pdf_dpi: 300,
          boundaries: {
            database_write: false,
            audit_log_write: false,
            source_storage_write: false,
            provider_call: false
          }
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          contract_version: "unlimited-ocr-extraction-v1",
          file_name: "扫描合同.png",
          extension: "png",
          source_sha256: "a".repeat(64),
          size_bytes: 11,
          text: "付款条款待复核。",
          page_count: 1,
          engine: "baidu/Unlimited-OCR",
          source_commit: "d49ff64afffc1f47ab563dc1c589bc2f78808fa4",
          mapping_status: "resolved",
          pages: [{
            page_number: 1,
            text: "付款条款待复核。",
            image_sha256: "b".repeat(64),
            text_sha256: "c".repeat(64),
            mapping_status: "resolved"
          }],
          boundaries: {
            database_write: false,
            audit_log_write: true,
            source_storage_write: false,
            index_write: false,
            provider_call: true,
            ocr_call: true,
            answer_provider_call: false
          }
        })
      });
    vi.stubGlobal("fetch", fetchMock);
    const file = new File(["image-bytes"], "扫描合同.png", { type: "image/png" });

    const capability = await fetchOcrCapabilities();
    const result = await extractOcrText(file);

    expect(capability.enabled).toBe(true);
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/v1/ocr/capabilities",
      expect.objectContaining({ cache: "no-store" })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/v1/ocr/extract",
      expect.objectContaining({ method: "POST", body: expect.any(FormData) })
    );
    const formData = fetchMock.mock.calls[1]?.[1]?.body as FormData;
    expect(formData.get("file")).toBe(file);
    expect(result.pages[0]?.mapping_status).toBe("resolved");
  });

  it("surfaces the OCR runtime gate message from a structured 409 detail", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: false,
        status: 409,
        json: async () => ({
          detail: {
            code: "unlimited_ocr_unavailable",
            message: "Unlimited-OCR 服务尚未启用，请联系管理员完成运行时门禁。"
          }
        })
      }))
    );

    await expect(
      extractOcrText(new File(["image"], "scan.png", { type: "image/png" }))
    ).rejects.toThrow("Unlimited-OCR 服务尚未启用，请联系管理员完成运行时门禁。");
  });

  it("surfaces actionable validation detail for an image-only PDF attachment", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: false,
        status: 422,
        json: async () => ({
          detail:
            "PDF 未检测到可读取文字，可能是扫描件或图片型 PDF。请先进行 OCR 识别，或上传可搜索文字版 PDF。"
        })
      }))
    );
    const file = new File(["%PDF-1.4"], "scanned.pdf", { type: "application/pdf" });

    await expect(
      analyzeChatAttachment(file, { model: "deepseek-v4-pro", mode: "auto" })
    ).rejects.toThrow(
      "PDF 未检测到可读取文字，可能是扫描件或图片型 PDF。请先进行 OCR 识别，或上传可搜索文字版 PDF。"
    );
  });

  it("fetches auth session through the versioned API proxy with current audit headers", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          user_identifier: "next-admin",
          role: "admin",
          role_label: "管理员",
          permissions: ["manage_project_members"],
          legacy_api_role: "it-admin",
          tenant_id: "hospital-demo",
          auth_source: "persistent_role",
          profile_status: "active",
          auth_scope_type: "global",
          auth_scope_key: null,
          auth_mode: "header_transition_layer",
          profile: {
            user_key: "next-admin",
            display_name: "系统管理员",
            department_key: "it-department",
            department_name: "信息科",
            status: "active",
            created_by: "system",
            metadata: {},
            role_assignments: [],
            source: "system-default"
          },
          store: { ready: true, backend: "SqlAlchemyAuthUserStore" }
        })
      }))
    );

    const session = await fetchAuthSession();

    expect(fetch).toHaveBeenCalledWith("/api/v1/auth/session", {
      headers: {
        Accept: "application/json",
        "X-Role": "admin",
        "X-Tenant-Id": "hospital-demo",
        "X-User-Id": "next-admin",
        "X-Project-Key": "SELF-CHECK-FUND-20260607"
      },
      cache: "no-store"
    });
    expect(session.role).toBe("admin");
    expect(session.tenant_id).toBe("hospital-demo");
    expect(session.profile?.display_name).toBe("系统管理员");
  });

  it("fetches persisted query history through the versioned API proxy", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          items: [
            {
              id: "query-history-001",
              user_identifier: "next-knowledge-query",
              question: "医保基金审核依据",
              filters: { top_k: 8, source_collections: ["medical-insurance-laws"] },
              answer_summary: "应核验证据链。",
              retrieved_chunk_ids: ["chunk-doc-001"],
              citation_count: 1,
              created_at: "2026-06-15T00:00:00Z"
            }
          ],
          store: { ready: true, backend: "SqlAlchemyQueryHistoryStore" }
        })
      }))
    );

    const result = await fetchQueryHistory();

    expect(fetch).toHaveBeenCalledWith("/api/v1/query/logs?limit=8", {
      headers: {
        Accept: "application/json",
        "X-Role": "admin",
        "X-Tenant-Id": "hospital-demo",
        "X-User-Id": "next-admin"
      },
      cache: "no-store"
    });
    expect(result.items[0].question).toBe("医保基金审核依据");
  });

  it("creates a project-scoped review task from an owned query history item", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          format: "query-history-review-task-v1",
          query_log_id: "query/history 001",
          task_id: "history-task-001",
          project_key: "SELF-CHECK-FUND-20260607",
          status: "pending-review",
          created: true,
          review_queue_href: "/reports",
          provider_call: false,
          audit: { status: "ready", intent_recorded: true, completion_recorded: true }
        })
      }))
    );

    const result = await createQueryHistoryReviewTask("query/history 001", {
      project_key: "SELF-CHECK-FUND-20260607",
      note: "请人工复核"
    });

    expect(fetch).toHaveBeenCalledWith(
      "/api/v1/query/logs/query%2Fhistory%20001/review-task",
      {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          "X-Project-Key": "SELF-CHECK-FUND-20260607",
          "X-Role": "admin",
          "X-Tenant-Id": "hospital-demo",
          "X-User-Id": "next-admin"
        },
        body: JSON.stringify({
          project_key: "SELF-CHECK-FUND-20260607",
          note: "请人工复核"
        }),
        cache: "no-store"
      }
    );
    expect(result.task_id).toBe("history-task-001");
    expect(result.provider_call).toBe(false);
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
      headers: {
        Accept: "application/json",
        "X-Role": "admin",
        "X-Tenant-Id": "hospital-demo",
        "X-User-Id": "next-admin"
      },
      cache: "no-store"
    });
    expect(result.filters.review_status).toBe("pending-review");
  });

  it("fetches report workbench through the versioned API proxy", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          format: "report-workbench-v1",
          generated_at: "2026-06-21T00:00:00Z",
          template_registry_status: "active",
          template_categories: [
            { id: "plan", label: "计划类", availability: "awaiting-business-template" },
            { id: "workpaper", label: "底稿类", availability: "active" },
            { id: "evidence", label: "取证类", availability: "awaiting-business-template" },
            { id: "confirmation", label: "函证类", availability: "awaiting-business-template" },
            { id: "report", label: "报告类", availability: "awaiting-business-template" },
            { id: "remediation", label: "整改类", availability: "awaiting-business-template" }
          ],
          workpaper_templates: [],
          report_entries: [],
          report_evidence_sources: [],
          metrics: {
            report_count: 0,
            signed_report_count: 0,
            blocked_report_count: 0,
            included_finding_count: 0,
            docx_download_count: 0
          },
          store: { ready: true, backend: "InMemoryReviewTaskStore" }
        })
      }))
    );

    const result = await fetchReportWorkbench();

    expect(fetch).toHaveBeenCalledWith("/api/v1/reports/workbench", {
      headers: {
        Accept: "application/json",
        "X-Role": "admin",
        "X-Tenant-Id": "hospital-demo",
        "X-User-Id": "next-admin"
      },
      cache: "no-store"
    });
    expect(result.format).toBe("report-workbench-v1");
  });

  it("creates a controlled report draft with project-scoped identity headers", async () => {
    const client = await import("./api-client") as unknown as {
      readonly createReportDraft?: (payload: {
        readonly template_id: string;
        readonly project_key: string;
        readonly field_values: Readonly<Record<string, string>>;
      }) => Promise<{ readonly task_id: string }>;
    };
    expect(client.createReportDraft).toBeTypeOf("function");
    if (!client.createReportDraft) return;

    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          format: "report-template-draft-v1",
          task_id: "report-draft-123",
          template_id: "workpaper-summary-risk",
          category_id: "workpaper",
          project_key: "PROJECT-A",
          project_href: "/projects?project=PROJECT-A",
          status: "pending-review",
          store: { ready: true, backend: "JsonFileReviewTaskStore" },
          formal_report_created: false,
          provider_call: false,
          audit: {
            status: "ready",
            durability: "durable",
            local_only: false,
            intent_recorded: true,
            completion_recorded: true
          }
        })
      }))
    );
    const payload = {
      template_id: "workpaper-summary-risk",
      project_key: "PROJECT-A",
      field_values: { 人工复核意见: "待主任复核" }
    } as const;

    const result = await client.createReportDraft(payload);

    expect(fetch).toHaveBeenCalledWith("/api/v1/reports/drafts", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "X-Project-Key": "PROJECT-A",
        "X-Role": "admin",
        "X-Tenant-Id": "hospital-demo",
        "X-User-Id": "next-admin"
      },
      body: JSON.stringify(payload),
      cache: "no-store"
    });
    expect(result.task_id).toBe("report-draft-123");
  });

  it.each([
    [422, "field_values contains unsupported evidence binding", "field_values contains unsupported evidence binding"],
    [403, "create_report_draft is not allowed", "create_report_draft is not allowed"],
    [404, "project not found", "project not found"]
  ] as const)(
    "exposes structured POST status %s with a safe string detail",
    async (status, responseDetail, expectedDetail) => {
      const client = await import("./api-client") as unknown as {
        readonly createReportDraft: (payload: {
          readonly template_id: string;
          readonly project_key: string;
          readonly field_values: Readonly<Record<string, string>>;
        }) => Promise<unknown>;
        readonly isBackendRequestError?: (error: unknown) => boolean;
      };
      vi.stubGlobal(
        "fetch",
        vi.fn(async () => ({
          ok: false,
          status,
          json: async () => ({ detail: responseDetail })
        }))
      );

      const error = await client.createReportDraft({
        template_id: "workpaper-summary-risk",
        project_key: "PROJECT-A",
        field_values: { 人工复核意见: "待复核" }
      }).catch((caught: unknown) => caught);

      expect(client.isBackendRequestError).toBeTypeOf("function");
      expect(client.isBackendRequestError?.(error)).toBe(true);
      expect(error).toMatchObject({
        name: "BackendRequestError",
        method: "POST",
        path: "/api/v1/reports/drafts",
        status,
        detail: expectedDetail,
        message: `Backend request failed: POST /api/v1/reports/drafts returned ${status}`
      });
    }
  );

  it("does not expose structured error-detail objects through the shared POST client", async () => {
    const client = await import("./api-client") as unknown as {
      readonly createReportDraft: (payload: {
        readonly template_id: string;
        readonly project_key: string;
        readonly field_values: Readonly<Record<string, string>>;
      }) => Promise<unknown>;
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: false,
        status: 422,
        json: async () => ({ detail: { field: "SENSITIVE-OBJECT-DETAIL" } })
      }))
    );

    const error = await client.createReportDraft({
      template_id: "workpaper-summary-risk",
      project_key: "PROJECT-A",
      field_values: { 人工复核意见: "待复核" }
    }).catch((caught: unknown) => caught);

    expect(error).toMatchObject({
      name: "BackendRequestError",
      status: 422,
      detail: null
    });
    expect(JSON.stringify(error)).not.toContain("SENSITIVE-OBJECT-DETAIL");
  });

  it("downloads only internal review-task artifacts with authenticated headers and a response filename", async () => {
    const client = await import("./api-client") as unknown as {
      readonly downloadAuditArtifact?: (
        path: string
      ) => Promise<{ readonly blob: Blob; readonly filename: string }>;
    };
    expect(client.downloadAuditArtifact).toBeTypeOf("function");
    if (!client.downloadAuditArtifact) return;

    const fetchMock = vi.fn(async () => ({
      ok: true,
      headers: new Headers({
        "Content-Disposition": 'attachment; filename="review-task-001.docx"',
        "Content-Type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
      }),
      blob: async () => new Blob(["document"], { type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" })
    }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(client.downloadAuditArtifact("https://attacker.invalid/steal")).rejects.toThrow(
      "Audit artifact path must be an internal /review-tasks/ path"
    );
    await expect(client.downloadAuditArtifact("/api/v1/documents/secret")).rejects.toThrow(
      "Audit artifact path must be an internal /review-tasks/ path"
    );
    expect(fetchMock).not.toHaveBeenCalled();

    const result = await client.downloadAuditArtifact(
      "/review-tasks/review-task-001/export?format=docx"
    );

    expect(fetchMock).toHaveBeenCalledWith(
      "/review-tasks/review-task-001/export?format=docx",
      {
        headers: {
          Accept: "application/octet-stream",
          "X-Role": "admin",
          "X-Tenant-Id": "hospital-demo",
          "X-User-Id": "next-admin"
        },
        cache: "no-store"
      }
    );
    expect(result.filename).toBe("review-task-001.docx");
    expect(result.blob).toBeInstanceOf(Blob);
  });

  it("surfaces authenticated artifact download failures with method, path and status", async () => {
    const client = await import("./api-client") as unknown as {
      readonly downloadAuditArtifact?: (path: string) => Promise<unknown>;
    };
    expect(client.downloadAuditArtifact).toBeTypeOf("function");
    if (!client.downloadAuditArtifact) return;
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({ ok: false, status: 403 }))
    );

    await expect(
      client.downloadAuditArtifact("/review-tasks/review-task-001/export?format=docx")
    ).rejects.toThrow(
      "Backend request failed: GET /review-tasks/review-task-001/export?format=docx returned 403"
    );
  });

  it("passes an AbortSignal to the authenticated artifact request", async () => {
    const client = await import("./api-client") as unknown as {
      readonly downloadAuditArtifact: (
        path: string,
        options?: { readonly signal?: AbortSignal }
      ) => Promise<unknown>;
    };
    const fetchMock = vi.fn(async () => ({
      ok: true,
      headers: new Headers({ "Content-Type": "application/json" }),
      blob: async () => new Blob(["artifact"], { type: "application/json" })
    }));
    vi.stubGlobal("fetch", fetchMock);
    const controller = new AbortController();

    await client.downloadAuditArtifact(
      "/review-tasks/review-task-001/export?format=json",
      { signal: controller.signal }
    );

    expect(fetchMock).toHaveBeenCalledWith(
      "/review-tasks/review-task-001/export?format=json",
      expect.objectContaining({ signal: controller.signal })
    );
  });

  it("decodes RFC 5987 artifact filenames and uses path-safe format fallbacks", async () => {
    const client = await import("./api-client") as unknown as {
      readonly downloadAuditArtifact: (
        path: string
      ) => Promise<{ readonly blob: Blob; readonly filename: string }>;
    };
    const response = (disposition: string | null, contentType: string) => ({
      ok: true,
      headers: new Headers({
        ...(disposition ? { "Content-Disposition": disposition } : {}),
        "Content-Type": contentType
      }),
      blob: async () => new Blob(["artifact"], { type: contentType })
    });
    vi.stubGlobal(
      "fetch",
      vi.fn()
        .mockResolvedValueOnce(response(
          "attachment; filename*=UTF-8''%E5%8C%BB%E4%BF%9D%E5%BA%95%E7%A8%BF.docx",
          "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ))
        .mockResolvedValueOnce(response(
          'attachment; filename="../../secret.docx"',
          "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ))
        .mockResolvedValueOnce(response(null, "text/markdown"))
        .mockResolvedValueOnce(response(
          'attachment; filename="audit;report\\"final.docx"',
          "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ))
    );

    await expect(
      client.downloadAuditArtifact("/review-tasks/task-1/export?format=docx")
    ).resolves.toMatchObject({ filename: "医保底稿.docx" });
    await expect(
      client.downloadAuditArtifact("/review-tasks/task-2/export?format=docx")
    ).resolves.toMatchObject({ filename: "secret.docx" });
    await expect(
      client.downloadAuditArtifact("/review-tasks/task-3/export?format=markdown")
    ).resolves.toMatchObject({ filename: "audit-artifact.md" });
    await expect(
      client.downloadAuditArtifact("/review-tasks/task-4/export?format=docx")
    ).resolves.toMatchObject({ filename: "audit;report-final.docx" });
  });

  it("fetches graph workbench through the versioned API proxy", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          format: "graph-workbench-v1",
          generated_at: "2026-06-22T00:00:00Z",
          graph_id: "SELF-CHECK-FUND-20260607",
          graph_title: "医保基金使用合规专项图谱",
          graph_scope: "医保基金使用合规专项自查。",
          nodes: [],
          relations: [],
          metrics: {
            node_count: 0,
            node_kind_count: 0,
            node_kind_counts: {},
            relation_count: 0,
            strong_relation_count: 0,
            pending_relation_count: 0
          },
          evidence_grade: "local-readonly-api",
          production_side_effect: "none",
          store: { ready: true, backend: "KnowledgeCatalogGraphBuilder" }
        })
      }))
    );

    const result = await fetchGraphWorkbench();

    expect(fetch).toHaveBeenCalledWith("/api/v1/graph/workbench", {
      headers: {
        Accept: "application/json",
        "X-Role": "admin",
        "X-Tenant-Id": "hospital-demo",
        "X-User-Id": "next-admin"
      },
      cache: "no-store"
    });
    expect(result.format).toBe("graph-workbench-v1");
  });

  it("fetches a project evidence graph with exact encoded scope headers", async () => {
    window.localStorage.setItem("medical-audit-current-role", "member");
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          format: "graph-workbench-v1",
          view: "project",
          project_key: "PROJECT / A&B",
          evidence_chain_status: "empty"
        })
      }))
    );

    const result = await fetchGraphWorkbench({
      view: "project",
      projectKey: "PROJECT / A&B"
    });

    expect(fetch).toHaveBeenCalledWith(
      "/api/v1/graph/workbench?view=project&project_key=PROJECT+%2F+A%26B",
      {
        headers: {
          Accept: "application/json",
          "X-Project-Key": "PROJECT / A&B",
          "X-Role": "member",
          "X-Tenant-Id": "hospital-demo",
          "X-User-Id": "next-member"
        },
        cache: "no-store"
      }
    );
    expect(result.view).toBe("project");
  });

  it("preserves project graph GET status and backend detail for view-specific errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: false,
        status: 404,
        json: async () => ({ detail: "project not found" })
      }))
    );

    await expect(fetchGraphWorkbench({ view: "project", projectKey: "PROJECT-A" })).rejects.toMatchObject({
      name: "BackendRequestError",
      method: "GET",
      path: "/api/v1/graph/workbench?view=project&project_key=PROJECT-A",
      status: 404,
      detail: "project not found"
    });
  });

  it("fetches rules workbench through the versioned API proxy", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          format: "rules-workbench-v1",
          generated_at: "2026-06-22T00:00:00Z",
          ruleset_id: "FUND-USAGE-COMPLIANCE-RULES",
          ruleset_title: "医保基金使用合规专题规则库",
          ruleset_scope: "汇总监管两库、医保目录、风险清单和对话审证沉淀。",
          rule_library_items: [],
          source_coverages: [],
          run_snapshots: [],
          control_gates: [],
          metrics: {
            rule_count: 0,
            enabled_rule_count: 0,
            pending_rule_count: 0,
            total_finding_count: 0,
            blocked_gate_count: 0,
            source_count: 0,
            run_count: 0
          },
          evidence_grade: "local-readonly-api",
          production_side_effect: "none",
          store: { ready: true, backend: "ReadonlyRulesWorkbenchSeed" }
        })
      }))
    );

    const result = await fetchRulesWorkbench();

    expect(fetch).toHaveBeenCalledWith("/api/v1/rules/workbench", {
      headers: {
        Accept: "application/json",
        "X-Role": "admin",
        "X-Tenant-Id": "hospital-demo",
        "X-User-Id": "next-admin"
      },
      cache: "no-store"
    });
    expect(result.format).toBe("rules-workbench-v1");
  });

  it("fetches remediation workbench through the versioned API proxy", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          format: "remediation-workbench-v1",
          generated_at: "2026-06-22T00:00:00Z",
          workbench_id: "FUND-USAGE-REMEDIATION",
          workbench_title: "整改事项与补证闭环",
          workbench_scope: "把报告整改事项、补证请求、责任科室和验收门禁组织成可追踪的整改工作台。",
          remediation_cases: [],
          evidence_requests: [],
          closure_gates: [],
          timeline: [],
          metrics: {
            case_count: 0,
            active_case_count: 0,
            closed_case_count: 0,
            pending_evidence_count: 0,
            blocked_gate_count: 0,
            average_progress: 0,
            timeline_count: 0
          },
          evidence_grade: "local-readonly-api",
          production_side_effect: "none",
          store: { ready: true, backend: "ReadonlyRemediationWorkbenchSeed" }
        })
      }))
    );

    const result = await fetchRemediationWorkbench();

    expect(fetch).toHaveBeenCalledWith("/api/v1/remediation/workbench", {
      headers: {
        Accept: "application/json",
        "X-Role": "admin",
        "X-Tenant-Id": "hospital-demo",
        "X-User-Id": "next-admin"
      },
      cache: "no-store"
    });
    expect(result.format).toBe("remediation-workbench-v1");
  });

  it("fetches archive workbench through the versioned API proxy", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          format: "archive-workbench-v1",
          generated_at: "2026-06-22T00:00:00Z",
          archive_id: "FUND-USAGE-ARCHIVE",
          archive_title: "项目档案与审计日志归档",
          archive_scope: "汇总项目档案包、审计日志归档、签名链和归档前阻断原因。",
          archive_packages: [],
          audit_runs: [],
          signature_items: [],
          policy_items: [],
          timeline: [],
          metrics: {
            package_count: 0,
            archived_package_count: 0,
            pending_package_count: 0,
            blocked_package_count: 0,
            audit_run_count: 0,
            signature_count: 0,
            policy_count: 0,
            timeline_count: 0,
            latest_archive_run_status: "无"
          },
          evidence_grade: "local-readonly-api",
          production_side_effect: "none",
          store: { ready: true, backend: "ReadonlyArchiveWorkbenchSeed" }
        })
      }))
    );

    const result = await fetchArchiveWorkbench();

    expect(fetch).toHaveBeenCalledWith("/api/v1/archive/workbench", {
      headers: {
        Accept: "application/json",
        "X-Role": "admin",
        "X-Tenant-Id": "hospital-demo",
        "X-User-Id": "next-admin"
      },
      cache: "no-store"
    });
    expect(result.format).toBe("archive-workbench-v1");
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
      headers: {
        Accept: "application/json",
        "X-Project-Name": "%E5%8C%BB%E4%BF%9D%E5%9F%BA%E9%87%91%E4%BD%BF%E7%94%A8%E5%90%88%E8%A7%84%E4%B8%93%E9%A1%B9%E8%87%AA%E6%9F%A5",
        "X-Role": "admin",
        "X-Tenant-Id": "hospital-demo",
        "X-User-Id": "next-admin"
      },
      cache: "no-store"
    });
    expect(result.items[0].id).toBe("agent-citation-check");
  });

  it("uploads analysis tables through the versioned API proxy", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          name: "charge-sample.csv",
          size_kb: 1,
          extension: "csv",
          status: "parsed",
          sheet_name: null,
          columns: [],
          row_count: 0,
          empty_cell_count: 0,
          duplicate_row_count: 0,
          message: "后端已完成 CSV 文件的字段画像。",
          quality_findings: [],
          audit_signals: [],
          recommendations: [],
          upload_id: "analytics-upload-test",
          sha256: "a".repeat(64),
          retention_status: "retained",
          created_at: "2026-06-15T00:00:00Z"
        })
      }))
    );

    const file = new File(["patient_id"], "charge-sample.csv", { type: "text/csv" });
    const result = await uploadAnalysisTable(file);
    const fetchCall = vi.mocked(fetch).mock.calls[0];

    expect(fetchCall[0]).toBe("/api/v1/analytics/table-upload");
    expect(fetchCall[1]).toMatchObject({
      method: "POST",
      headers: {
        Accept: "application/json",
        "X-Role": "admin",
        "X-Tenant-Id": "hospital-demo",
        "X-User-Id": "next-admin"
      },
      cache: "no-store"
    });
    expect(fetchCall[1]?.body).toBeInstanceOf(FormData);
    expect(result.name).toBe("charge-sample.csv");
    expect(result.retention_status).toBe("retained");
  });

  it.each([
    [413, "uploaded table file is too large"],
    [422, "unsupported table file extension"]
  ])("surfaces FastAPI string detail for analytics upload status %s", async (status, detail) => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: false,
        status,
        json: async () => ({ detail })
      }))
    );

    await expect(uploadAnalysisTable(new File(["x"], "bad.csv"))).rejects.toThrow(detail);
  });

  it("keeps generic method, path and status context for non-validation upload failures", async () => {
    const json = vi.fn(async () => ({ detail: "do not expose this body" }));
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: false, status: 500, json })));

    await expect(uploadAnalysisTable(new File(["x"], "bad.csv"))).rejects.toThrow(
      "Backend request failed: POST /api/v1/analytics/table-upload returned 500"
    );
    expect(json).not.toHaveBeenCalled();
  });

  it("falls back safely when a validation error body cannot be parsed", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: false,
        status: 422,
        json: async () => {
          throw new SyntaxError("invalid json");
        }
      }))
    );

    await expect(uploadAnalysisTable(new File(["x"], "bad.csv"))).rejects.toThrow(
      "Backend request failed: POST /api/v1/analytics/table-upload returned 422"
    );
  });

  it("keeps non-analytics form validation errors generic without reading backend detail", async () => {
    const json = vi.fn(async () => ({ detail: "internal document validation detail" }));
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: false, status: 422, json })));

    await expect(uploadPersonalDocument(new File(["x"], "document.pdf"))).rejects.toThrow(
      "Backend request failed: POST /api/v1/documents/uploads returned 422"
    );
    expect(json).not.toHaveBeenCalled();
  });

  it("fetches analysis upload history through the versioned API proxy", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          items: [
            {
              id: "analytics-upload-001",
              name: "charge-sample.csv",
              extension: "csv",
              size_bytes: 128,
              size_kb: 1,
              sha256: "b".repeat(64),
              sheet_name: null,
              row_count: 3,
              column_count: 5,
              empty_cell_count: 1,
              duplicate_row_count: 1,
              status: "parsed",
              created_by: "next-knowledge-query",
              created_at: "2026-06-15T00:00:00Z",
              retention_status: "retained",
              audit_signals: ["金额/费用字段"]
            }
          ],
          store: { ready: true, backend: "SqlAlchemyAnalyticsUploadStore" }
        })
      }))
    );

    const result = await fetchAnalysisUploadHistory();

    expect(fetch).toHaveBeenCalledWith("/api/v1/analytics/table-uploads", {
      headers: {
        Accept: "application/json",
        "X-Role": "admin",
        "X-Tenant-Id": "hospital-demo",
        "X-User-Id": "next-admin"
      },
      cache: "no-store"
    });
    expect(result.items[0].id).toBe("analytics-upload-001");
    expect(result.items[0]).not.toHaveProperty("storage_path");
  });

  it("fetches document permissions through the versioned API proxy", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          role: "auditor",
          source_collections: [
            {
              source_collection: "medical-insurance-laws",
              label: "法规政策",
              scope: "公开知识库",
              access: "read"
            }
          ],
          upload_permissions: {
            can_upload_personal: true,
            can_read_all_personal_uploads: false,
            can_govern_personal_uploads: false
          }
        })
      }))
    );

    const result = await fetchDocumentPermissions();

    expect(fetch).toHaveBeenCalledWith("/api/v1/documents/permissions", {
      headers: {
        Accept: "application/json",
        "X-Role": "admin",
        "X-Tenant-Id": "hospital-demo",
        "X-User-Id": "next-admin"
      },
      cache: "no-store"
    });
    expect(result.source_collections[0].source_collection).toBe("medical-insurance-laws");
  });

  it("fetches document source collection catalog through the versioned API proxy", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          contract_version: "document-source-collections-v1",
          role: "auditor",
          items: [
            {
              source_collection: "medical-insurance-laws",
              label: "法规政策",
              scope: "公开知识库",
              phase: "P6A-medical-current-library-completion",
              domain: "medical",
              evidence_group: "legal",
              description: "医保、医疗、药品、基金监管相关法律政策。",
              audit_hint: "用于判断制度依据和监管边界。",
              access: "read",
              product_queryable: true,
              queryable: true,
              metrics: {
                document_count: null,
                chunk_count: 1,
                character_count: null,
                linked_app_count: 1
              }
            }
          ],
          search_backend: {
            ready: true,
            backend: "local-acceptance",
            details: {
              provider_call: false,
              database_write: false,
              source_collection: "medical-insurance-laws"
            }
          },
          upload_permissions: {
            can_upload_personal: true,
            can_read_all_personal_uploads: false,
            can_govern_personal_uploads: false
          },
          boundaries: {
            production_write: false,
            provider_call: false,
            database_write: false,
            object_storage_write: false,
            source: "runtime_state_and_registry_only"
          }
        })
      }))
    );

    const result = await fetchDocumentSourceCollections();

    expect(fetch).toHaveBeenCalledWith("/api/v1/documents/source-collections", {
      headers: {
        Accept: "application/json",
        "X-Role": "admin",
        "X-Tenant-Id": "hospital-demo",
        "X-User-Id": "next-admin"
      },
      cache: "no-store"
    });
    expect(result.items[0].source_collection).toBe("medical-insurance-laws");
    expect(result.boundaries.provider_call).toBe(false);
  });

  it("fetches knowledge base catalog through the versioned API proxy", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          contract_version: "knowledge-base-catalog-v1",
          role: "auditor",
          summary: {
            source_collection_count: 25,
            queryable_collection_count: 25,
            total_document_count: 20054,
            total_chunk_count: 923288,
            total_embedding_count: 923288,
            current_search_embedding_count: 49051,
            candidate_chunk_count: 727214,
            domain_counts: { medical: 4, policy: 6 }
          },
          items: [
            {
              source_collection: "medical-insurance-laws",
              label: "法规政策",
              scope: "公开知识库",
              phase: "P6A-medical-current-library-completion",
              domain: "medical",
              evidence_group: "legal",
              description: "医保、医疗、药品、基金监管相关法律政策。",
              audit_hint: "用于判断制度依据和监管边界。",
              access: "read",
              product_queryable: true,
              queryable: true,
              metrics: {
                document_count: 503,
                chunk_count: 49051,
                embedding_count: 49051,
                active_embedding_count: 49051,
                candidate_chunk_count: 727214,
                character_count: 123456,
                linked_app_count: 1
              },
              index: {
                latest_version_key: "incremental-20260615",
                latest_status: "active",
                search_backend_ready: true,
                queryable: true
              },
              actions: {
                documents: "/documents?source_collection=medical-insurance-laws",
                chat: "/chat?source_collection=medical-insurance-laws",
                graph: "/graph?source_collection=medical-insurance-laws"
              }
            }
          ],
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
        })
      }))
    );

    const result = await fetchKnowledgeBaseCatalog();

    expect(fetch).toHaveBeenCalledWith("/api/v1/knowledge-base/catalog", {
      headers: {
        Accept: "application/json",
        "X-Role": "admin",
        "X-Tenant-Id": "hospital-demo",
        "X-User-Id": "next-admin"
      },
      cache: "no-store"
    });
    expect(result.summary.total_document_count).toBe(20054);
    expect(result.items[0].metrics.active_embedding_count).toBe(49051);
  });

  it("searches documents through the read-only document search endpoint", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          contract_version: "document-search-v1",
          query: "医保基金审核依据",
          effective_source_collections: ["medical-insurance-laws"],
          items: [
            {
              id: "chunk-001",
              chunk_id: "chunk-001",
              title: "医保基金审核依据",
              source_collection: "medical-insurance-laws",
              source_label: "法规政策",
              snippet: "医疗机构应当保留医保基金审核依据。",
              locator: { source_path: "全量法律/law.md" },
              score: 1,
              matched_by: ["bm25"],
              index_version_key: "index-v1",
              source_package_version_key: "package-v1",
              preview_url: "/api/v1/preview/chunk-001"
            }
          ],
          store: { ready: true, backend: "postgres" },
          boundaries: {
            production_write: false,
            provider_call: true,
            database_write: false,
            object_storage_write: false,
            query_history_write: false
          }
        })
      }))
    );

    const result = await searchDocuments({
      query: "医保基金审核依据",
      sourceCollections: ["medical-insurance-laws"],
      titleOnly: true,
      limit: 3
    });

    expect(fetch).toHaveBeenCalledWith(
      "/api/v1/documents/search?q=%E5%8C%BB%E4%BF%9D%E5%9F%BA%E9%87%91%E5%AE%A1%E6%A0%B8%E4%BE%9D%E6%8D%AE&source_collection=medical-insurance-laws&title_only=true&limit=3",
      {
        headers: {
          Accept: "application/json",
          "X-Role": "admin",
          "X-Tenant-Id": "hospital-demo",
          "X-User-Id": "next-admin"
        },
        cache: "no-store"
      }
    );
    expect(result.boundaries.query_history_write).toBe(false);
    expect(result.items[0].preview_url).toBe("/api/v1/preview/chunk-001");
  });

  it("fetches personal document uploads through the versioned API proxy", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          items: [
            {
              id: "document-upload-001",
              name: "policy.pdf",
              extension: "pdf",
              size_bytes: 128,
              size_kb: 1,
              sha256: "c".repeat(64),
              storage_path: "2026/06/15/document-upload-001.pdf",
              visibility: "private",
              status: "retained",
              created_by: "next-knowledge-query",
              created_at: "2026-06-15T00:00:00Z",
              retention_status: "retained",
              index_status: "not-indexed",
              governance_status: "pending-review",
              governance_note: "",
              governed_by: null,
              governed_at: null,
              security_scan_status: "local-policy-passed",
              security_scan_provider: "local-policy",
              dlp_status: "clear",
              security_findings: [],
              personal_index_status: "not-indexed",
              personal_indexed_at: null,
              personal_indexed_by: null,
              personal_index_chunk_count: 0,
              personal_index_error: "",
              download_url: "/api/v1/documents/uploads/document-upload-001/download"
            }
          ],
          store: { ready: true, backend: "SqlAlchemyDocumentUploadStore" },
          permissions: {
            can_upload_personal: true,
            can_read_all_personal_uploads: false,
            can_govern_personal_uploads: false
          }
        })
      }))
    );

    const result = await fetchDocumentUploads();

    expect(fetch).toHaveBeenCalledWith("/api/v1/documents/uploads", {
      headers: {
        Accept: "application/json",
        "X-Role": "admin",
        "X-Tenant-Id": "hospital-demo",
        "X-User-Id": "next-admin"
      },
      cache: "no-store"
    });
    expect(result.items[0].id).toBe("document-upload-001");
  });

  it("uploads personal documents through the versioned API proxy", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          item: {
            id: "document-upload-001",
            name: "policy.pdf",
            extension: "pdf",
            size_bytes: 128,
            size_kb: 1,
            sha256: "c".repeat(64),
            storage_path: "2026/06/15/document-upload-001.pdf",
            visibility: "private",
            status: "retained",
            created_by: "next-knowledge-query",
            created_at: "2026-06-15T00:00:00Z",
            retention_status: "retained",
            index_status: "not-indexed",
            governance_status: "pending-review",
            governance_note: "",
            governed_by: null,
            governed_at: null,
            security_scan_status: "local-policy-passed",
            security_scan_provider: "local-policy",
            dlp_status: "clear",
            security_findings: [],
            personal_index_status: "not-indexed",
            personal_indexed_at: null,
            personal_indexed_by: null,
            personal_index_chunk_count: 0,
            personal_index_error: "",
            download_url: "/api/v1/documents/uploads/document-upload-001/download"
          },
          store: { ready: true, backend: "SqlAlchemyDocumentUploadStore" },
          permissions: {
            can_upload_personal: true,
            can_read_all_personal_uploads: false,
            can_govern_personal_uploads: false
          }
        })
      }))
    );

    const file = new File(["policy"], "policy.pdf", { type: "application/pdf" });
    const result = await uploadPersonalDocument(file);
    const fetchCall = vi.mocked(fetch).mock.calls[0];

    expect(fetchCall[0]).toBe("/api/v1/documents/uploads");
    expect(fetchCall[1]).toMatchObject({
      method: "POST",
      headers: {
        Accept: "application/json",
        "X-Role": "admin",
        "X-Tenant-Id": "hospital-demo",
        "X-User-Id": "next-admin"
      },
      cache: "no-store"
    });
    expect(fetchCall[1]?.body).toBeInstanceOf(FormData);
    expect(result.item.index_status).toBe("not-indexed");
  });

  it("updates personal document governance through the versioned API proxy", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          item: {
            id: "document-upload-001",
            name: "policy.pdf",
            extension: "pdf",
            size_bytes: 128,
            size_kb: 1,
            sha256: "c".repeat(64),
            storage_path: "2026/06/15/document-upload-001.pdf",
            visibility: "private",
            status: "retained",
            created_by: "next-knowledge-query",
            created_at: "2026-06-15T00:00:00Z",
            retention_status: "retained",
            index_status: "index-ready",
            governance_status: "approved-for-index",
            governance_note: "已完成材料治理。",
            governed_by: "next-admin",
            governed_at: "2026-06-21T00:00:00Z",
            security_scan_status: "local-policy-passed",
            security_scan_provider: "local-policy",
            dlp_status: "clear",
            security_findings: [],
            personal_index_status: "not-indexed",
            personal_indexed_at: null,
            personal_indexed_by: null,
            personal_index_chunk_count: 0,
            personal_index_error: "",
            download_url: "/api/v1/documents/uploads/document-upload-001/download"
          },
          store: { ready: true, backend: "SqlAlchemyDocumentUploadStore" },
          permissions: {
            can_upload_personal: true,
            can_read_all_personal_uploads: true,
            can_govern_personal_uploads: true
          }
        })
      }))
    );

    const result = await updateDocumentUploadGovernance("document-upload-001", {
      governance_status: "approved-for-index",
      note: "已完成材料治理。"
    });

    expect(fetch).toHaveBeenCalledWith("/api/v1/documents/uploads/document-upload-001/governance", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "X-Role": "admin",
        "X-Tenant-Id": "hospital-demo",
        "X-User-Id": "next-admin"
      },
      body: JSON.stringify({
        governance_status: "approved-for-index",
        note: "已完成材料治理。"
      }),
      cache: "no-store"
    });
    expect(result.item.index_status).toBe("index-ready");
  });

  it("starts personal document local indexing through the versioned API proxy", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          item: {
            id: "document-upload-001",
            name: "policy.pdf",
            extension: "pdf",
            size_bytes: 128,
            size_kb: 1,
            sha256: "c".repeat(64),
            storage_path: "2026/06/15/document-upload-001.pdf",
            visibility: "private",
            status: "retained",
            created_by: "next-knowledge-query",
            created_at: "2026-06-15T00:00:00Z",
            retention_status: "retained",
            index_status: "index-ready",
            governance_status: "approved-for-index",
            governance_note: "已完成材料治理。",
            governed_by: "next-admin",
            governed_at: "2026-06-21T00:00:00Z",
            security_scan_status: "local-policy-passed",
            security_scan_provider: "local-policy",
            dlp_status: "clear",
            security_findings: [],
            personal_index_status: "indexed",
            personal_indexed_at: "2026-06-21T00:00:00Z",
            personal_indexed_by: "next-admin",
            personal_index_chunk_count: 1,
            personal_index_error: "",
            download_url: "/api/v1/documents/uploads/document-upload-001/download"
          },
          store: { ready: true, backend: "SqlAlchemyDocumentUploadStore" },
          permissions: {
            can_upload_personal: true,
            can_read_all_personal_uploads: true,
            can_govern_personal_uploads: true
          }
        })
      }))
    );

    const result = await indexPersonalDocument("document-upload-001");

    expect(fetch).toHaveBeenCalledWith("/api/v1/documents/uploads/document-upload-001/index", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "X-Role": "admin",
        "X-Tenant-Id": "hospital-demo",
        "X-User-Id": "next-admin"
      },
      body: JSON.stringify({}),
      cache: "no-store"
    });
    expect(result.item.personal_index_status).toBe("indexed");
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
        "X-Project-Name": "%E5%8C%BB%E4%BF%9D%E5%9F%BA%E9%87%91%E4%BD%BF%E7%94%A8%E5%90%88%E8%A7%84%E4%B8%93%E9%A1%B9%E8%87%AA%E6%9F%A5",
        "X-Role": "admin",
        "X-Tenant-Id": "hospital-demo",
        "X-User-Id": "next-admin"
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

  it("reads and installs server-side agent market templates without exposing prompts", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          contract_version: "agent-market-catalog-v2",
          count: 133,
          featured_count: 1,
          prompt_materialization: "server-only",
          items: [{
            id: "agent-contract-audit-v2",
            name: "合同审计智能体",
            category: "工具智能体",
            summary: "合同审计",
            topic: "合同审计",
            project: "全院审计项目",
            featured: true,
            featured_rank: 1,
            prompt_sha256: "a".repeat(64),
            source: "contract-audit-v2",
            template_key: "agent-contract-audit-v2"
          }]
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          item: { id: "agent-custom-installed", name: "合同审计智能体" },
          created: true,
          store: { ready: true, backend: "SqlAlchemyAgentStore" }
        })
      });
    vi.stubGlobal("fetch", fetchMock);

    const catalog = await fetchAgentMarketCatalog();
    const installed = await installAuditAgentMarketTemplate("agent-contract-audit-v2", {
      project_name: "医保基金使用合规专项自查"
    });

    expect(catalog.count).toBe(133);
    expect(catalog.items[0]).not.toHaveProperty("prompt");
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/v1/agent-market/templates/agent-contract-audit-v2/install",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ project_name: "医保基金使用合规专项自查" })
      })
    );
    expect(installed.item.id).toBe("agent-custom-installed");
  });

  it("updates audit agent prompt versions through the versioned API proxy", async () => {
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
            prompt: "补充原文引用约束。",
            knowledge_base: "医保目录库",
            project_name: "医保目录限制条件核验",
            status: "active",
            prompt_version: 2,
            prompt_version_key: "agent-custom-001@v2",
            visibility_scope: "project",
            allowed_roles: ["admin", "technician", "director", "member"],
            created_by: "next-admin",
            updated_at: "2026-06-22T00:00:00Z",
            source: "custom",
            metadata: {}
          },
          store: { ready: true, backend: "SqlAlchemyAgentStore" }
        })
      }))
    );

    const result = await createAuditAgentPromptVersion("agent-custom-001", {
      prompt: "补充原文引用约束。",
      change_summary: "补充原文引用约束。"
    });

    expect(fetch).toHaveBeenCalledWith("/api/v1/agents/agent-custom-001/prompt-versions", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "X-Project-Name": "%E5%8C%BB%E4%BF%9D%E5%9F%BA%E9%87%91%E4%BD%BF%E7%94%A8%E5%90%88%E8%A7%84%E4%B8%93%E9%A1%B9%E8%87%AA%E6%9F%A5",
        "X-Role": "admin",
        "X-Tenant-Id": "hospital-demo",
        "X-User-Id": "next-admin"
      },
      body: JSON.stringify({
        prompt: "补充原文引用约束。",
        change_summary: "补充原文引用约束。"
      }),
      cache: "no-store"
    });
    expect(result.item.prompt_version).toBe(2);
  });

  it("rolls back audit agent prompt versions through the versioned API proxy", async () => {
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
            prompt: "初始提示词。",
            knowledge_base: "医保目录库",
            project_name: "医保目录限制条件核验",
            status: "active",
            prompt_version: 3,
            prompt_version_key: "agent-custom-001@v3",
            visibility_scope: "project",
            allowed_roles: ["admin", "technician", "director", "member"],
            created_by: "next-admin",
            updated_at: "2026-06-22T00:00:00Z",
            source: "custom",
            metadata: {}
          },
          store: { ready: true, backend: "SqlAlchemyAgentStore" }
        })
      }))
    );

    const result = await rollbackAuditAgentPromptVersion("agent-custom-001", { version: 1 });

    expect(fetch).toHaveBeenCalledWith("/api/v1/agents/agent-custom-001/prompt-versions/rollback", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "X-Project-Name": "%E5%8C%BB%E4%BF%9D%E5%9F%BA%E9%87%91%E4%BD%BF%E7%94%A8%E5%90%88%E8%A7%84%E4%B8%93%E9%A1%B9%E8%87%AA%E6%9F%A5",
        "X-Role": "admin",
        "X-Tenant-Id": "hospital-demo",
        "X-User-Id": "next-admin"
      },
      body: JSON.stringify({ version: 1 }),
      cache: "no-store"
    });
    expect(result.item.prompt_version).toBe(3);
  });

  it("reviews audit agent prompt versions through the versioned API proxy", async () => {
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
            prompt: "补充原文引用约束。",
            knowledge_base: "医保目录库",
            project_name: "医保目录限制条件核验",
            status: "active",
            prompt_version: 2,
            prompt_version_key: "agent-custom-001@v2",
            visibility_scope: "project",
            allowed_roles: ["admin", "technician", "director", "member"],
            created_by: "next-admin",
            updated_at: "2026-06-22T00:00:00Z",
            source: "custom",
            metadata: {}
          },
          store: { ready: true, backend: "SqlAlchemyAgentStore" }
        })
      }))
    );

    const result = await reviewAuditAgentPromptVersion("agent-custom-001", {
      version: 2,
      review_status: "approved",
      review_note: "主任已复核引用边界。"
    });

    expect(fetch).toHaveBeenCalledWith("/api/v1/agents/agent-custom-001/prompt-versions/review", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "X-Project-Name": "%E5%8C%BB%E4%BF%9D%E5%9F%BA%E9%87%91%E4%BD%BF%E7%94%A8%E5%90%88%E8%A7%84%E4%B8%93%E9%A1%B9%E8%87%AA%E6%9F%A5",
        "X-Role": "admin",
        "X-Tenant-Id": "hospital-demo",
        "X-User-Id": "next-admin"
      },
      body: JSON.stringify({
        version: 2,
        review_status: "approved",
        review_note: "主任已复核引用边界。"
      }),
      cache: "no-store"
    });
    expect(result.item.prompt_version).toBe(2);
  });

  it("updates audit agent lifecycle through the versioned API proxy", async () => {
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
            prompt: "初始提示词。",
            knowledge_base: "医保目录库",
            project_name: "医保目录限制条件核验",
            status: "inactive",
            prompt_version: 1,
            prompt_version_key: "agent-custom-001@v1",
            visibility_scope: "project",
            allowed_roles: ["admin", "technician", "director", "member"],
            created_by: "next-admin",
            updated_at: "2026-06-22T00:00:00Z",
            source: "custom",
            metadata: { lifecycle_reason: "工作台下架，保留历史追溯。" }
          },
          store: { ready: true, backend: "SqlAlchemyAgentStore" }
        })
      }))
    );

    const result = await updateAuditAgentLifecycle("agent-custom-001", {
      status: "inactive",
      reason: "工作台下架，保留历史追溯。"
    });

    expect(fetch).toHaveBeenCalledWith("/api/v1/agents/agent-custom-001/lifecycle", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "X-Project-Name": "%E5%8C%BB%E4%BF%9D%E5%9F%BA%E9%87%91%E4%BD%BF%E7%94%A8%E5%90%88%E8%A7%84%E4%B8%93%E9%A1%B9%E8%87%AA%E6%9F%A5",
        "X-Role": "admin",
        "X-Tenant-Id": "hospital-demo",
        "X-User-Id": "next-admin"
      },
      body: JSON.stringify({
        status: "inactive",
        reason: "工作台下架，保留历史追溯。"
      }),
      cache: "no-store"
    });
    expect(result.item.status).toBe("inactive");
  });

  it("fetches audit agent detail and prompt versions through the versioned API proxy", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (path: string) => ({
        ok: true,
        json: async () =>
          path.endsWith("/prompt-versions")
            ? {
                items: [
                  {
                    version: 1,
                    prompt: "初始提示词。",
                    change_summary: "initial prompt",
                    created_by: "next-admin",
                    created_at: "2026-06-22T00:00:00Z"
                  }
                ],
                store: { ready: true, backend: "SqlAlchemyAgentStore" }
              }
            : {
                item: {
                  id: "agent-custom-001",
                  name: "目录限制核验助手",
                  category: "业务类",
                  topic: "医保目录限制条件核验",
                  prompt: "初始提示词。",
                  knowledge_base: "医保目录库",
                  project_name: "医保目录限制条件核验",
                  status: "active",
                  prompt_version: 1,
                  prompt_version_key: "agent-custom-001@v1",
                  prompt_versions: [
                    {
                      version: 1,
                      prompt: "初始提示词。",
                      change_summary: "initial prompt",
                      created_by: "next-admin",
                      created_at: "2026-06-22T00:00:00Z"
                    }
                  ],
                  visibility_scope: "project",
                  allowed_roles: ["admin", "technician", "director", "member"],
                  created_by: "next-admin",
                  updated_at: "2026-06-22T00:00:00Z",
                  source: "custom",
                  metadata: {}
                },
                store: { ready: true, backend: "SqlAlchemyAgentStore" }
              }
      }))
    );

    const detail = await fetchAuditAgent("agent-custom-001");
    const versions = await fetchAuditAgentPromptVersions("agent-custom-001");

    expect(fetch).toHaveBeenNthCalledWith(1, "/api/v1/agents/agent-custom-001", {
      headers: {
        Accept: "application/json",
        "X-Project-Name": "%E5%8C%BB%E4%BF%9D%E5%9F%BA%E9%87%91%E4%BD%BF%E7%94%A8%E5%90%88%E8%A7%84%E4%B8%93%E9%A1%B9%E8%87%AA%E6%9F%A5",
        "X-Role": "admin",
        "X-Tenant-Id": "hospital-demo",
        "X-User-Id": "next-admin"
      },
      cache: "no-store"
    });
    expect(fetch).toHaveBeenNthCalledWith(2, "/api/v1/agents/agent-custom-001/prompt-versions", {
      headers: {
        Accept: "application/json",
        "X-Project-Name": "%E5%8C%BB%E4%BF%9D%E5%9F%BA%E9%87%91%E4%BD%BF%E7%94%A8%E5%90%88%E8%A7%84%E4%B8%93%E9%A1%B9%E8%87%AA%E6%9F%A5",
        "X-Role": "admin",
        "X-Tenant-Id": "hospital-demo",
        "X-User-Id": "next-admin"
      },
      cache: "no-store"
    });
    expect(detail.item.prompt_versions).toHaveLength(1);
    expect(versions.items[0].version).toBe(1);
  });

  it("records and fetches audit agent invocations through the versioned API proxy", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (path: string) => ({
        ok: true,
        json: async () =>
          path.endsWith("/invocations")
            ? {
                items: [
                  {
                    id: "agent-invocation-001",
                    agent_key: "agent-custom-001",
                    prompt_version: 2,
                    prompt_version_key: "agent-custom-001@v2",
                    invocation_source: "agent-workspace",
                    question: "目录限制核验试用",
                    conversation_ref: null,
                    created_by: "next-admin",
                    created_at: "2026-06-22T00:00:00Z",
                    metadata: {}
                  }
                ],
                store: { ready: true, backend: "SqlAlchemyAgentStore" }
              }
            : {}
      }))
    );

    const list = await fetchAuditAgentInvocations("agent-custom-001");
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        item: list.items[0],
        store: { ready: true, backend: "SqlAlchemyAgentStore" }
      })
    } as Response);
    const created = await recordAuditAgentInvocation("agent-custom-001", {
      invocation_source: "agent-workspace",
      question: "目录限制核验试用"
    });

    expect(fetch).toHaveBeenNthCalledWith(1, "/api/v1/agents/agent-custom-001/invocations", {
      headers: {
        Accept: "application/json",
        "X-Project-Name": "%E5%8C%BB%E4%BF%9D%E5%9F%BA%E9%87%91%E4%BD%BF%E7%94%A8%E5%90%88%E8%A7%84%E4%B8%93%E9%A1%B9%E8%87%AA%E6%9F%A5",
        "X-Role": "admin",
        "X-Tenant-Id": "hospital-demo",
        "X-User-Id": "next-admin"
      },
      cache: "no-store"
    });
    expect(fetch).toHaveBeenNthCalledWith(2, "/api/v1/agents/agent-custom-001/invocations", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "X-Project-Name": "%E5%8C%BB%E4%BF%9D%E5%9F%BA%E9%87%91%E4%BD%BF%E7%94%A8%E5%90%88%E8%A7%84%E4%B8%93%E9%A1%B9%E8%87%AA%E6%9F%A5",
        "X-Role": "admin",
        "X-Tenant-Id": "hospital-demo",
        "X-User-Id": "next-admin"
      },
      body: JSON.stringify({
        invocation_source: "agent-workspace",
        question: "目录限制核验试用"
      }),
      cache: "no-store"
    });
    expect(created.item.id).toBe("agent-invocation-001");
  });

  it("submits and fetches audit agent feedback through the versioned API proxy", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (path: string) => ({
        ok: true,
        json: async () =>
          path.endsWith("/feedback")
            ? {
                items: [
                  {
                    id: "agent-feedback-001",
                    agent_key: "agent-custom-001",
                    invocation_id: "agent-invocation-001",
                    prompt_version: 2,
                    rating: "needs_review",
                    comment: "需要补充目录限制原文适用条件。",
                    created_by: "next-admin",
                    created_at: "2026-06-22T00:00:00Z",
                    metadata: {}
                  }
                ],
                ratings: ["effective", "needs_review", "unsafe"],
                summary: {
                  total: 1,
                  effective: 0,
                  needs_review: 1,
                  unsafe: 0,
                  latest_rating: "needs_review"
                },
                store: { ready: true, backend: "SqlAlchemyAgentStore" }
              }
            : {}
      }))
    );

    const list = await fetchAuditAgentFeedback("agent-custom-001");
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        item: list.items[0],
        ratings: ["effective", "needs_review", "unsafe"],
        summary: {
          total: 1,
          effective: 0,
          needs_review: 1,
          unsafe: 0,
          latest_rating: "needs_review"
        },
        store: { ready: true, backend: "SqlAlchemyAgentStore" }
      })
    } as Response);
    const created = await submitAuditAgentFeedback("agent-custom-001", {
      invocation_id: "agent-invocation-001",
      rating: "needs_review",
      comment: "需要补充目录限制原文适用条件。"
    });

    expect(fetch).toHaveBeenNthCalledWith(1, "/api/v1/agents/agent-custom-001/feedback", {
      headers: {
        Accept: "application/json",
        "X-Project-Name": "%E5%8C%BB%E4%BF%9D%E5%9F%BA%E9%87%91%E4%BD%BF%E7%94%A8%E5%90%88%E8%A7%84%E4%B8%93%E9%A1%B9%E8%87%AA%E6%9F%A5",
        "X-Role": "admin",
        "X-Tenant-Id": "hospital-demo",
        "X-User-Id": "next-admin"
      },
      cache: "no-store"
    });
    expect(fetch).toHaveBeenNthCalledWith(2, "/api/v1/agents/agent-custom-001/feedback", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "X-Project-Name": "%E5%8C%BB%E4%BF%9D%E5%9F%BA%E9%87%91%E4%BD%BF%E7%94%A8%E5%90%88%E8%A7%84%E4%B8%93%E9%A1%B9%E8%87%AA%E6%9F%A5",
        "X-Role": "admin",
        "X-Tenant-Id": "hospital-demo",
        "X-User-Id": "next-admin"
      },
      body: JSON.stringify({
        invocation_id: "agent-invocation-001",
        rating: "needs_review",
        comment: "需要补充目录限制原文适用条件。"
      }),
      cache: "no-store"
    });
    expect(created.item.rating).toBe("needs_review");
  });

  it("fetches projects through the versioned API proxy", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          items: [
            {
              id: "SELF-CHECK-FUND-20260607",
              name: "医保基金使用合规专项自查",
              audit_topic: "医保基金使用合规",
              organization_name: "单院医保内审试运行",
              member_count: 3,
              creator: "项目负责人",
              creator_user_identifier: "next-director",
              created_at: "2026-06-07",
              status: "进行中",
              operation_label: "进入项目",
              source: "system-default"
            }
          ],
          roles: ["项目负责人", "审计员", "业务专家", "信息科", "只读观察员"],
          statuses: ["在项目中", "待确认"],
          project_statuses: ["待开始", "进行中", "已完成", "已归档"],
          store: { ready: true, backend: "SqlAlchemyProjectMemberStore" }
        })
      }))
    );

    const result = await fetchProjects();

    expect(fetch).toHaveBeenCalledWith("/api/v1/projects", {
      headers: {
        Accept: "application/json",
        "X-Project-Key": "SELF-CHECK-FUND-20260607",
        "X-Role": "admin",
        "X-Tenant-Id": "hospital-demo",
        "X-User-Id": "next-admin"
      },
      cache: "no-store"
    });
    expect(result.items[0].id).toBe("SELF-CHECK-FUND-20260607");
  });

  it("creates a project without sending a default project scope header", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          item: {
            id: "FUND-CHECK-202607",
            name: "医保基金专项检查",
            audit_topic: "医保基金使用合规",
            organization_name: "某医院",
            member_count: 1,
            creator: "next-admin",
            creator_user_identifier: "next-admin",
            created_at: "2026-07-15T04:00:00Z",
            status: "待开始",
            operation_label: "进入项目",
            source: "collaboration-v1"
          },
          creator_member: {
            id: "member-custom-001",
            project_key: "FUND-CHECK-202607",
            user_identifier: "next-admin",
            name: "next-admin",
            role: "项目负责人",
            department: "内审部",
            status: "在项目中",
            created_by: "next-admin",
            source: "custom",
            metadata: {}
          },
          store: { ready: true, backend: "SqlAlchemyProjectMemberStore" },
          audit: { status: "recorded" }
        })
      }))
    );

    const payload = {
      project_key: "FUND-CHECK-202607",
      name: "医保基金专项检查",
      scenario_key: "charging-compliance",
      audit_topic: "医保基金使用合规",
      organization_name: "某医院",
      owner_department: "内审部",
      description: "专项检查"
    } as const;
    const result = await createProject(payload);

    expect(fetch).toHaveBeenCalledWith("/api/v1/projects", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "X-Role": "admin",
        "X-Tenant-Id": "hospital-demo",
        "X-User-Id": "next-admin"
      },
      body: JSON.stringify(payload),
      cache: "no-store"
    });
    expect(result.item.id).toBe("FUND-CHECK-202607");
    expect(result.creator_member.role).toBe("项目负责人");
    expect(result.audit.status).toBe("recorded");
  });

  it("fetches project members through the versioned API proxy", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          items: [
            {
              id: "member-auditor",
              project_key: "SELF-CHECK-FUND-20260607",
              user_identifier: "next-member",
              name: "审计员",
              role: "审计员",
              department: "内审部",
              status: "在项目中",
              created_by: "system",
              source: "system-default",
              metadata: {}
            }
          ],
          project_key: "SELF-CHECK-FUND-20260607",
          roles: ["项目负责人", "审计员", "业务专家", "信息科", "只读观察员"],
          statuses: ["在项目中", "待确认"],
          store: { ready: true, backend: "SqlAlchemyProjectMemberStore" }
        })
      }))
    );

    const result = await fetchProjectMembers("SELF-CHECK-FUND-20260607");

    expect(fetch).toHaveBeenCalledWith("/api/v1/projects/SELF-CHECK-FUND-20260607/members", {
      headers: {
        Accept: "application/json",
        "X-Project-Key": "SELF-CHECK-FUND-20260607",
        "X-Role": "admin",
        "X-Tenant-Id": "hospital-demo",
        "X-User-Id": "next-admin"
      },
      cache: "no-store"
    });
    expect(result.items[0].id).toBe("member-auditor");
  });

  it("fetches project dashboard through the versioned API proxy", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          format: "project-dashboard-v1",
          project: {
            id: "SELF-CHECK-FUND-20260607",
            name: "医保基金使用合规专项自查",
            audit_topic: "医保基金使用合规",
            organization_name: "单院医保内审试运行",
            member_count: 3,
            creator: "项目负责人",
            creator_user_identifier: "next-director",
            created_at: "2026-06-07",
            status: "进行中",
            operation_label: "进入项目",
            source: "system-default"
          },
          metrics: [
            {
              key: "open_findings",
              label: "待处理疑点",
              value: "2",
              helper: "来自审计疑点库",
              tone: "danger"
            }
          ],
          queue: [],
          activities: [],
          status_distribution: [],
          member_workloads: [],
          evidence_grade: "live-db-connected",
          production_side_effect: "none",
          store: {
            ready: true,
            project_members_ready: true,
            audit_findings_ready: true,
            status: "ready",
            backend: {
              project_members: "SqlAlchemyProjectMemberStore",
              audit_findings: "SqlAlchemyAuditFindingStore"
            }
          }
        })
      }))
    );

    const result = await fetchProjectDashboard("SELF-CHECK-FUND-20260607");

    expect(fetch).toHaveBeenCalledWith("/api/v1/projects/SELF-CHECK-FUND-20260607/dashboard", {
      headers: {
        Accept: "application/json",
        "X-Project-Key": "SELF-CHECK-FUND-20260607",
        "X-Role": "admin",
        "X-Tenant-Id": "hospital-demo",
        "X-User-Id": "next-admin"
      },
      cache: "no-store"
    });
    expect(result.metrics[0].value).toBe("2");
  });

  it("creates project members through the versioned API proxy", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          item: {
            id: "member-custom-001",
            project_key: "CATALOG-LIMIT-202606",
            user_identifier: "auditor-zhao",
            name: "赵审计",
            role: "审计员",
            department: "医保办",
            status: "待确认",
            created_by: "next-knowledge-query",
            updated_at: "2026-06-14T00:00:00Z",
            source: "custom",
            metadata: {}
          },
          store: { ready: true, backend: "SqlAlchemyProjectMemberStore" }
        })
      }))
    );

    const result = await createProjectMember("CATALOG-LIMIT-202606", {
      user_identifier: "auditor-zhao",
      name: "赵审计",
      role: "审计员",
      department: "医保办"
    });

    expect(fetch).toHaveBeenCalledWith("/api/v1/projects/CATALOG-LIMIT-202606/members", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "X-Role": "admin",
        "X-Tenant-Id": "hospital-demo",
        "X-User-Id": "next-admin",
        "X-Project-Key": "CATALOG-LIMIT-202606"
      },
      body: JSON.stringify({
        user_identifier: "auditor-zhao",
        name: "赵审计",
        role: "审计员",
        department: "医保办"
      }),
      cache: "no-store"
    });
    expect(result.item.id).toBe("member-custom-001");
  });
});
