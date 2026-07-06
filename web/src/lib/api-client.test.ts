import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { afterEach, describe, expect, it, vi } from "vitest";

import {
  createAuditAgent,
  createAuditAgentPromptVersion,
  createProjectMember,
  fetchAnalysisUploadHistory,
  fetchArchiveWorkbench,
  fetchAuthSession,
  fetchAuditFindings,
  fetchAuditAgent,
  fetchAuditAgentFeedback,
  fetchAuditAgentInvocations,
  fetchAgents,
  fetchAuditAgentPromptVersions,
  fetchBackendHealth,
  fetchDocumentPermissions,
  fetchDocumentSourceCollections,
  fetchDocumentUploads,
  fetchGraphWorkbench,
  fetchProjectMembers,
  fetchProjects,
  fetchQueryHistory,
  fetchRemediationWorkbench,
  fetchReportWorkbench,
  fetchRulesWorkbench,
  fetchSearchBackendStatus,
  rollbackAuditAgentPromptVersion,
  indexPersonalDocument,
  recordAuditAgentInvocation,
  reviewAuditAgentPromptVersion,
  runKnowledgeQuery,
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
        "/api/v1/query/logs?limit=8",
        "/api/v1/audit-findings",
        "/api/v1/reports/workbench",
        "/api/v1/graph/workbench",
        "/api/v1/rules/workbench",
        "/api/v1/remediation/workbench",
        "/api/v1/archive/workbench",
        "/api/v1/analytics/table-uploads",
        "/api/v1/documents/source-collections",
        "/api/v1/documents/permissions",
        "/api/v1/documents/uploads",
        "/api/v1/agents",
        "/api/v1/agents/{agentId}",
        "/api/v1/agents/{agentId}/prompt-versions",
        "/api/v1/agents/{agentId}/invocations",
        "/api/v1/agents/{agentId}/feedback",
        "/api/v1/projects",
        "/api/v1/projects/{projectId}/members"
      ])
    );

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
      agent: "agent-installed-catalog-001"
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
        agent: "agent-installed-catalog-001"
      }),
      cache: "no-store"
    });
    expect(result.answer).toBe("应核验证据链。");
    expect(result.agent_invocation_id).toBe("agent-invocation-chat-001");
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
          store: { ready: true, backend: "ReadonlyGraphWorkbenchSeed" }
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
              storage_path: "2026/06/15/analytics-upload-001.csv",
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
              created_at: "2026-06-07",
              status: "进行中",
              operation_label: "进入项目",
              source: "system-default"
            }
          ],
          roles: ["项目负责人", "审计员", "业务专家", "信息科", "只读观察员"],
          statuses: ["在项目中", "待确认"],
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

  it("creates project members through the versioned API proxy", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          item: {
            id: "member-custom-001",
            project_key: "CATALOG-LIMIT-202606",
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
        name: "赵审计",
        role: "审计员",
        department: "医保办"
      }),
      cache: "no-store"
    });
    expect(result.item.id).toBe("member-custom-001");
  });
});
