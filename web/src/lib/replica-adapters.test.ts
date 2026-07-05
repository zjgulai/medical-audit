import { describe, expect, it } from "vitest";

import type {
  AgentsResponse,
  AuditAgentApiItem,
  AuthSessionResponse,
  DocumentPermissionsResponse,
  GraphWorkbenchResponse,
  ProjectsResponse,
  QueryHistoryResponse,
  QueryResponse,
  ReportWorkbenchResponse,
  TableAnalysisUploadHistoryResponse
} from "./api-types";
import {
  loadReplicaAgentMarketData,
  loadReplicaAgentsData,
  loadReplicaAnalyticsData,
  loadReplicaDocumentsData,
  loadReplicaGraphData,
  loadReplicaKnowledgeBaseData,
  loadReplicaProjectsData,
  loadReplicaReportsData,
  loadReplicaShellData
} from "./replica-adapters";

const readyStore = { ready: true, backend: "unit-test" } as const;

const apiAgent = {
  id: "agent-healthcare-duplicates",
  name: "医保重复收费核验",
  category: "业务类",
  topic: "社会保障审计",
  prompt: "识别医保结算明细中的重复收费、超目录支付和限制条件不满足问题。",
  knowledge_base: "医保目录库",
  project_name: "医保基金审计",
  status: "active",
  prompt_version: 1,
  prompt_version_key: "prompt-version-1",
  visibility_scope: "project",
  allowed_roles: ["admin"],
  prompt_versions: [],
  created_by: "auditor",
  created_at: "2026-07-01T00:00:00Z",
  updated_at: "2026-07-03T08:30:00Z",
  source: "custom",
  metadata: { summary: "按医保结算明细识别重复收费风险。" }
} satisfies AuditAgentApiItem;

const agentsResponse = {
  items: [apiAgent],
  categories: ["业务类", "效率类", "研究类"],
  store: readyStore
} satisfies AgentsResponse;

describe("replica-adapters", () => {
  it("keeps shell on fixture data when no API client is injected", async () => {
    const result = await loadReplicaShellData();

    expect(result.source).toBe("fixture");
    expect(result.data.user.displayName).toBe("审计员");
    expect(result.data.navigation.map((item) => item.href)).toContain("/chat");
    expect(result.issues).toEqual([]);
  });

  it("maps auth session and query history into shell data without replacing navigation", async () => {
    const session = {
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
      store: readyStore
    } satisfies AuthSessionResponse;
    const history = {
      items: [
        {
          id: "query-history-001",
          user_identifier: "next-admin",
          question: "医保基金审核依据",
          filters: { top_k: 8, source_collections: ["medical-insurance-laws"] },
          answer_summary: "应核验证据链。",
          retrieved_chunk_ids: ["chunk-doc-001"],
          citation_count: 1,
          created_at: "2026-06-15T00:00:00Z"
        }
      ],
      store: readyStore
    } satisfies QueryHistoryResponse;

    const result = await loadReplicaShellData({
      fetchAuthSession: async () => session,
      fetchQueryHistory: async () => history
    });

    expect(result.source).toBe("hybrid");
    expect(result.data.user.displayName).toBe("系统管理员");
    expect(result.data.historyItems).toEqual([{ id: "query-history-001", title: "医保基金审核依据" }]);
    expect(result.data.navigation).toHaveLength(10);
  });

  it("maps API agents and falls back to fixture agents when the read fails", async () => {
    const result = await loadReplicaAgentsData({
      fetchAgents: async () => agentsResponse
    });

    expect(result.source).toBe("api");
    expect(result.data.agents[0]).toMatchObject({
      id: "agent-healthcare-duplicates",
      name: "医保重复收费核验",
      project: "医保基金审计",
      summary: "按医保结算明细识别重复收费风险。"
    });

    const fallback = await loadReplicaAgentsData({
      fetchAgents: async () => {
        throw new Error("backend unavailable");
      }
    });

    expect(fallback.source).toBe("fixture");
    expect(fallback.data.agents.length).toBeGreaterThan(1);
    expect(fallback.issues).toContainEqual({
      surface: "agents",
      code: "api-read-failed",
      message: "API read failed; reference fixture data remains active."
    });
  });

  it("keeps marketplace and knowledge-base catalog gaps explicit", async () => {
    const market = await loadReplicaAgentMarketData();
    const permissions = {
      role: "admin",
      source_collections: [
        {
          source_collection: "medical-insurance-laws",
          label: "医保法规库",
          scope: "public",
          access: "read"
        }
      ],
      upload_permissions: {
        can_upload_personal: true,
        can_read_all_personal_uploads: false,
        can_govern_personal_uploads: false
      }
    } satisfies DocumentPermissionsResponse;
    const knowledgeBase = await loadReplicaKnowledgeBaseData({
      fetchDocumentPermissions: async () => permissions
    });

    expect(market.source).toBe("fixture");
    expect(market.issues.map((item) => item.code)).toEqual(["catalog-api-needed", "mutation-gated"]);
    expect(knowledgeBase.source).toBe("hybrid");
    expect(knowledgeBase.data.readableSourceCollections).toEqual(["医保法规库"]);
    expect(knowledgeBase.issues[0].code).toBe("catalog-api-needed");
  });

  it("maps query citations and query history into document search data", async () => {
    const history = {
      items: [
        {
          id: "query-history-002",
          user_identifier: "next-admin",
          question: "招标人违法确定中标人的定性依据",
          filters: { top_k: 5 },
          answer_summary: null,
          retrieved_chunk_ids: ["chunk-law-001"],
          citation_count: 1,
          created_at: "2026-07-01T00:00:00Z"
        }
      ],
      store: readyStore
    } satisfies QueryHistoryResponse;
    const queryResponse = {
      question: "招标人违法确定中标人的定性依据",
      answer: "应引用招投标相关法规和案例。",
      confidence: "high",
      fallback_used: false,
      effective_source_collections: ["medical-insurance-laws"],
      basis_groups: [],
      citations: [
        {
          citation_id: "citation-law-001",
          marker: "[1]",
          chunk_id: "chunk-law-001",
          evidence_type: "法律法规库",
          source_collection: "medical-insurance-laws",
          snippet: "招标人应当按照评标委员会推荐的中标候选人确定中标人。",
          locator: { title: "中华人民共和国招标投标法实施条例", issued_at: "2026-06-18" },
          index_version_key: null,
          source_package_version_key: null
        }
      ],
      personal_upload_matches: [
        {
          id: "personal-001",
          upload_id: "upload-001",
          name: "项目访谈纪要.docx",
          extension: ".docx",
          created_by: "auditor",
          indexed_at: "2026-07-02T10:20:00Z",
          chunk_index: 0,
          snippet: "访谈材料显示定标流程需要进一步复核。",
          score: 0.82,
          locator: {}
        }
      ],
      query_log_index: 2
    } satisfies QueryResponse;

    const result = await loadReplicaDocumentsData({
      fetchQueryHistory: async () => history,
      runKnowledgeQuery: async () => queryResponse
    });

    expect(result.source).toBe("hybrid");
    expect(result.data.searchHistory).toEqual(["招标人违法确定中标人的定性依据"]);
    expect(result.data.results).toHaveLength(2);
    expect(result.data.results[0]).toMatchObject({
      id: "citation-law-001",
      title: "中华人民共和国招标投标法实施条例",
      category: "法律法规库",
      source: "医保法规库"
    });
  });

  it("maps analytics, graph, report, and project read models", async () => {
    const uploads = {
      items: [
        {
          id: "upload-001",
          name: "医保结算明细.csv",
          extension: ".csv",
          size_bytes: 1024,
          size_kb: 1,
          sha256: "hash",
          storage_path: "uploads/医保结算明细.csv",
          sheet_name: null,
          row_count: 128,
          column_count: 12,
          empty_cell_count: 3,
          duplicate_row_count: 1,
          status: "retained",
          created_by: "auditor",
          created_at: "2026-07-03T08:00:00Z",
          retention_status: "retained",
          audit_signals: ["识别到疑似重复收费字段组合。"]
        }
      ],
      store: readyStore
    } satisfies TableAnalysisUploadHistoryResponse;
    const graph = {
      format: "graph-workbench-v1",
      generated_at: "2026-07-03T08:00:00Z",
      graph_id: "graph-001",
      graph_title: "医保基金图谱",
      graph_scope: "read-only",
      nodes: [
        {
          id: "node-project",
          label: "医保基金审计",
          kind: "项目",
          status: "可引用",
          description: "项目节点",
          metric: "3 个主题",
          href: "/projects/project-001",
          x: 0,
          y: 0
        }
      ],
      relations: [],
      metrics: {
        node_count: 1,
        node_kind_count: 1,
        node_kind_counts: {
          项目: 1,
          知识库: 0,
          文档: 0,
          规则: 0,
          疑点: 0,
          复核: 0,
          报告: 0,
          整改: 0
        },
        relation_count: 0,
        strong_relation_count: 0,
        pending_relation_count: 0
      },
      evidence_grade: "local-read",
      production_side_effect: "none",
      store: readyStore
    } satisfies GraphWorkbenchResponse;
    const reports = {
      format: "report-workbench-v1",
      generated_at: "2026-07-03T08:00:00Z",
      template_registry_status: "active",
      workpaper_templates: [],
      report_entries: [
        {
          id: "report-001",
          title: "医保基金支付异常分析底稿",
          status: "草稿",
          report_no: "R-001",
          owner: "审计二组",
          source: "医保基金审计",
          included_finding_count: 4,
          appendix_count: 2,
          gate_summary: "待复核",
          updated_at: "2026-07-03T09:10:00Z",
          href: "/reports/report-001",
          download_links: {
            page: "/reports/report-001",
            task_docx: "/downloads/task.docx",
            report_docx: null,
            report_markdown: null,
            report_json: null
          }
        }
      ],
      report_evidence_sources: [],
      metrics: {
        report_count: 1,
        signed_report_count: 0,
        blocked_report_count: 0,
        included_finding_count: 4,
        docx_download_count: 1
      },
      store: readyStore
    } satisfies ReportWorkbenchResponse;
    const projects = {
      items: [
        {
          id: "project-001",
          name: "医保基金使用合规审计",
          audit_topic: "社会保障审计",
          organization_name: "审计二组",
          member_count: 6,
          creator: "auditor",
          created_at: "2026-07-02T00:00:00Z",
          status: "进行中",
          operation_label: "进入项目",
          source: "system-default"
        }
      ],
      roles: ["项目负责人", "审计员", "业务专家", "信息科", "只读观察员"],
      statuses: ["在项目中", "待确认"],
      store: readyStore
    } satisfies ProjectsResponse;

    await expect(
      loadReplicaAnalyticsData({ fetchAnalysisUploadHistory: async () => uploads })
    ).resolves.toMatchObject({
      source: "api",
      data: { datasets: [{ id: "upload-001", rows: 128, columns: 12 }] }
    });
    await expect(loadReplicaGraphData({ fetchGraphWorkbench: async () => graph })).resolves.toMatchObject({
      source: "api",
      data: { nodes: [{ id: "node-project", status: "可引用" }] }
    });
    await expect(loadReplicaReportsData({ fetchReportWorkbench: async () => reports })).resolves.toMatchObject({
      source: "api",
      data: { records: [{ id: "report-001", sourceCount: 6 }] }
    });
    await expect(loadReplicaProjectsData({ fetchProjects: async () => projects })).resolves.toMatchObject({
      source: "api",
      data: { projects: [{ id: "project-001", progress: 68 }] }
    });
  });
});
