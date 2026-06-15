import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  createAuditAgent,
  createProjectMember,
  fetchAnalysisUploadHistory,
  fetchDocumentPermissions,
  fetchDocumentUploads,
  fetchQueryHistory,
  fetchSearchBackendStatus,
  runKnowledgeQuery,
  uploadAnalysisTable,
  uploadPersonalDocument
} from "@/lib/api-client";
import { primaryNavigation, secondaryNavigation, workspaceHomeNavigation } from "@/lib/navigation";

import AgentMarketPage from "./agent-market/page";
import AgentsPage from "./agents/page";
import AnalyticsPage from "./analytics/page";
import ArchivePage from "./archive/page";
import ChatPortalPage from "./chat/page";
import DocumentsPage from "./documents/page";
import FindingsPage from "./findings/page";
import GraphPage from "./graph/page";
import GuidedCheckPage from "./guided-check/page";
import KnowledgeBasePage from "./knowledge-base/page";
import KnowledgeQueryPage from "./knowledge-query/page";
import ProjectsPage from "./projects/page";
import RemediationPage from "./remediation/page";
import ReportsPage from "./reports/page";
import RulesPage from "./rules/page";
import WorkspacePage from "./workspace/page";

vi.mock("@/lib/api-client", () => ({
  createAuditAgent: vi.fn(
    async (payload: {
      readonly name: string;
      readonly category: string;
      readonly topic: string;
      readonly prompt: string;
      readonly knowledge_base?: string;
      readonly project_name?: string;
    }) => ({
    item: {
      id: "agent-custom-test",
      name: payload.name,
      category: payload.category,
      topic: payload.topic,
      prompt: payload.prompt,
      knowledge_base: payload.knowledge_base ?? "项目默认知识库",
      project_name: payload.project_name ?? "医保基金使用合规专项自查",
      status: "active",
      created_by: "next-knowledge-query",
      updated_at: "2026-06-14T00:00:00Z",
      source: "custom",
      metadata: {}
    },
    store: { ready: true, backend: "SqlAlchemyAgentStore" }
    })
  ),
  createProjectMember: vi.fn(
    async (
      projectId: string,
      payload: {
        readonly name: string;
        readonly role: string;
        readonly department: string;
      }
    ) => ({
      item: {
        id: "member-custom-test",
        project_key: projectId,
        name: payload.name,
        role: payload.role,
        department: payload.department,
        status: "待确认",
        created_by: "next-knowledge-query",
        updated_at: "2026-06-14T00:00:00Z",
        source: "custom",
        metadata: {}
      },
      store: { ready: true, backend: "SqlAlchemyProjectMemberStore" }
    })
  ),
  uploadAnalysisTable: vi.fn(async (file: File) => ({
    name: file.name,
    size_kb: Math.max(1, Math.round(file.size / 1024)),
    extension: "csv",
    status: "parsed",
    sheet_name: null,
    columns: [
      {
        name: "patient_id",
        type: "标识",
        empty_count: 0,
        unique_count: 2,
        sample_values: ["P001", "P002"],
        audit_hint: "对象字段，可用于同人同次就诊聚合"
      },
      {
        name: "visit_date",
        type: "日期",
        empty_count: 0,
        unique_count: 2,
        sample_values: ["2026-01-01", "2026-01-02"],
        audit_hint: "时间字段，可用于限定审计期间和同日重复核验"
      },
      {
        name: "item_code",
        type: "标识",
        empty_count: 0,
        unique_count: 2,
        sample_values: ["A100", "B200"],
        audit_hint: "项目字段，可用于目录限制和重复收费核验"
      },
      {
        name: "charge_amount",
        type: "数值",
        empty_count: 1,
        unique_count: 1,
        sample_values: ["120.00"],
        audit_hint: "金额字段，可用于收费合规和异常金额核验"
      },
      {
        name: "insurance_pay",
        type: "数值",
        empty_count: 0,
        unique_count: 2,
        sample_values: ["80.00", "50.00"],
        audit_hint: "医保字段，可用于支付范围和报销口径核验"
      }
    ],
    row_count: 3,
    empty_cell_count: 1,
    duplicate_row_count: 1,
    message: "后端已完成 CSV 文件的字段画像。",
    quality_findings: [
      "识别到 3 行数据和 5 个字段。",
      "发现 1 个空值单元，需要确认是否为业务允许缺失。",
      "发现 1 条完全重复行。",
      "字段名未发现重复。"
    ],
    audit_signals: ["金额/费用字段", "患者/就诊字段", "日期/时间字段", "项目/药品/目录字段", "医保支付字段"],
    recommendations: [
      "重复收费核验字段基础完整，可按患者/就诊、项目、日期和金额形成初筛分组。",
      "已识别医保支付字段，可进一步核对支付范围、报销口径和目录限制条件。",
      "优先核对高空值字段：charge_amount。"
    ],
    upload_id: "analytics-upload-test",
    sha256: "a".repeat(64),
    retention_status: "retained",
    created_at: "2026-06-15T00:00:00Z"
  })),
  fetchAnalysisUploadHistory: vi.fn(async () => ({
    items: [
      {
        id: "analytics-upload-history",
        name: "history-charge.csv",
        extension: "csv",
        size_bytes: 128,
        size_kb: 1,
        sha256: "b".repeat(64),
        storage_path: "2026/06/15/analytics-upload-history.csv",
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
  })),
  fetchDocumentPermissions: vi.fn(async () => ({
    role: "auditor",
    source_collections: [
      {
        source_collection: "medical-insurance-laws",
        label: "法规政策",
        scope: "公开知识库",
        access: "read"
      },
      {
        source_collection: "supervision-rules-knowledge",
        label: "监管两库",
        scope: "系统知识库",
        access: "read"
      },
      {
        source_collection: "medical-insurance-catalog",
        label: "医保目录",
        scope: "系统知识库",
        access: "read"
      },
      {
        source_collection: "risk-negative-list",
        label: "风险清单",
        scope: "系统知识库",
        access: "read"
      }
    ],
    upload_permissions: {
      can_upload_personal: true,
      can_read_all_personal_uploads: false
    }
  })),
  fetchDocumentUploads: vi.fn(async () => ({
    items: [
      {
        id: "document-upload-history",
        name: "policy-retained.pdf",
        extension: "pdf",
        size_bytes: 128,
        size_kb: 1,
        sha256: "c".repeat(64),
        storage_path: "2026/06/15/document-upload-history.pdf",
        visibility: "private",
        status: "retained",
        created_by: "next-knowledge-query",
        created_at: "2026-06-15T00:00:00Z",
        retention_status: "retained",
        index_status: "not-indexed"
      }
    ],
    store: { ready: true, backend: "SqlAlchemyDocumentUploadStore" },
    permissions: {
      can_upload_personal: true,
      can_read_all_personal_uploads: false
    }
  })),
  uploadPersonalDocument: vi.fn(async (file: File) => ({
    item: {
      id: "document-upload-test",
      name: file.name,
      extension: "pdf",
      size_bytes: file.size,
      size_kb: Math.max(1, Math.round(file.size / 1024)),
      sha256: "d".repeat(64),
      storage_path: "2026/06/15/document-upload-test.pdf",
      visibility: "private",
      status: "retained",
      created_by: "next-knowledge-query",
      created_at: "2026-06-15T00:00:00Z",
      retention_status: "retained",
      index_status: "not-indexed"
    },
    store: { ready: true, backend: "SqlAlchemyDocumentUploadStore" },
    permissions: {
      can_upload_personal: true,
      can_read_all_personal_uploads: false
    }
  })),
  fetchQueryHistory: vi.fn(async () => ({
    items: [
      {
        id: "query-history-001",
        user_identifier: "next-knowledge-query",
        question: "医保基金支付异常",
        filters: {
          top_k: 8,
          source_collections: ["medical-insurance-laws"]
        },
        answer_summary: "应核验医保基金支付异常的引用依据。",
        retrieved_chunk_ids: ["chunk-doc-001"],
        citation_count: 1,
        created_at: "2026-06-15T00:00:00Z"
      }
    ],
    store: { ready: true, backend: "SqlAlchemyQueryHistoryStore" }
  })),
  fetchAuditFindings: vi.fn(async () => ({
    items: [],
    stats: { total: 0, open: 0, pending_review: 0, linked_review_task: 0 },
    filters: { review_status: null, limit: 100 },
    review_status_options: { "pending-review": "待复核" },
    generation_readiness: {
      status: "blocked",
      ready: false,
      has_findings: false,
      table_counts: { audit_projects: 0, his_staging_rows: 0, audit_findings: 0 },
      prerequisites: [
        { key: "audit_projects", label: "审计项目", count: 0, ready: false, required: true }
      ],
      blocking_reasons: [
        { code: "missing-audit_projects", message: "审计项目为空，无法从规则运行生成疑点。" }
      ],
      next_actions: ["导入脱敏 HIS 样本。"]
    },
    store: { ready: true, backend: "SqlAlchemyAuditFindingStore" }
  })),
  fetchBackendHealth: vi.fn(async () => ({
    status: "ok",
    version: "0.1.0",
    data_root: "/tmp/data"
  })),
  fetchProjectMembers: vi.fn(async (projectId: string) => ({
    items:
      projectId === "CATALOG-LIMIT-202606"
        ? [
            {
              id: "member-catalog-owner",
              project_key: "CATALOG-LIMIT-202606",
              name: "业务专家",
              role: "业务专家",
              department: "医保办",
              status: "在项目中",
              created_by: "system",
              source: "system-default",
              metadata: {}
            },
            {
              id: "member-catalog-it",
              project_key: "CATALOG-LIMIT-202606",
              name: "信息科接口人",
              role: "信息科",
              department: "信息科",
              status: "待确认",
              created_by: "system",
              source: "system-default",
              metadata: {}
            }
          ]
        : [
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
            },
            {
              id: "member-owner",
              project_key: "SELF-CHECK-FUND-20260607",
              name: "项目负责人",
              role: "项目负责人",
              department: "内审部",
              status: "在项目中",
              created_by: "system",
              source: "system-default",
              metadata: {}
            },
            {
              id: "member-it",
              project_key: "SELF-CHECK-FUND-20260607",
              name: "信息科接口人",
              role: "信息科",
              department: "信息科",
              status: "待确认",
              created_by: "system",
              source: "system-default",
              metadata: {}
            }
          ],
    project_key: projectId,
    roles: ["项目负责人", "审计员", "业务专家", "信息科", "只读观察员"],
    statuses: ["在项目中", "待确认"],
    store: { ready: true, backend: "SqlAlchemyProjectMemberStore" }
  })),
  fetchProjects: vi.fn(async () => ({
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
      },
      {
        id: "CATALOG-LIMIT-202606",
        name: "医保目录限制条件核验",
        audit_topic: "目录限制",
        organization_name: "单院医保内审试运行",
        member_count: 4,
        creator: "业务专家",
        created_at: "2026-06-09",
        status: "待启动",
        operation_label: "查看成员",
        source: "system-default"
      }
    ],
    roles: ["项目负责人", "审计员", "业务专家", "信息科", "只读观察员"],
    statuses: ["在项目中", "待确认"],
    store: { ready: true, backend: "SqlAlchemyProjectMemberStore" }
  })),
  fetchAgents: vi.fn(async () => ({
    items: [
      {
        id: "agent-citation-check",
        name: "引用依据核验助手",
        category: "业务类",
        topic: "医保基金使用合规",
        prompt: "只基于命中的法规、目录、规则和风险清单回答；没有引用时输出待补证据。",
        knowledge_base: "系统医保审计知识库",
        project_name: "医保基金使用合规专项自查",
        status: "active",
        created_by: "system",
        updated_at: "2026-06-12",
        source: "system-default",
        metadata: {}
      },
      {
        id: "agent-duplicate-charge",
        name: "重复收费复核助手",
        category: "业务类",
        topic: "收费明细复核",
        prompt: "围绕同就诊、同项目、同日期的重复收费线索，列出应核验的执行记录、数量和例外情形。",
        knowledge_base: "规则库与风险清单",
        project_name: "医保基金使用合规专项自查",
        status: "active",
        created_by: "system",
        updated_at: "2026-06-11",
        source: "system-default",
        metadata: {}
      },
      {
        id: "agent-report-draft",
        name: "底稿摘要助手",
        category: "效率类",
        topic: "审计底稿",
        prompt: "把已复核的引用、疑点和附件清单整理为底稿摘要，保留待人工确认标记。",
        knowledge_base: "项目复核资料",
        project_name: "医保基金使用合规专项自查",
        status: "active",
        created_by: "system",
        updated_at: "2026-06-10",
        source: "system-default",
        metadata: {}
      }
    ],
    categories: ["业务类", "效率类", "研究类"],
    store: { ready: true, backend: "SqlAlchemyAgentStore" }
  })),
  fetchSearchBackendStatus: vi.fn(async () => ({
    backend: "postgres",
    ready: true,
    details: { matching_embedding_count: 48985 }
  })),
  runKnowledgeQuery: vi.fn(async (payload: { readonly question: string }) => ({
    question: payload.question,
    answer: "应核验诊疗记录、收费明细和政策依据。",
    confidence: "high",
    fallback_used: true,
    basis_groups: [
      {
        evidence_type: "law",
        title: "法规依据",
        items: [
          {
            citation_id: "C1",
            chunk_id: "chunk-doc-001",
            source_collection: "medical-insurance-laws",
            snippet: "医疗机构应当保留医保基金审核依据。",
            locator: {
              source_path: "全量法律/law.md",
              line_start: 1,
              line_end: 1
            },
            index_version_key: "index-v1",
            source_package_version_key: "package-v1"
          }
        ]
      }
    ],
    citations: [
      {
        citation_id: "C1",
        marker: "[C1]",
        chunk_id: "chunk-doc-001",
        evidence_type: "law",
        source_collection: "medical-insurance-laws",
        snippet: "医疗机构应当保留医保基金审核依据。",
        locator: {
          source_path: "全量法律/law.md",
          line_start: 1,
          line_end: 1
        },
        index_version_key: "index-v1",
        source_package_version_key: "package-v1"
      }
    ],
    query_log_index: 0
  }))
}));

const routePages = [
  ["/chat", ChatPortalPage],
  ["/agents", AgentsPage],
  ["/agent-market", AgentMarketPage],
  ["/knowledge-base", KnowledgeBasePage],
  ["/documents", DocumentsPage],
  ["/analytics", AnalyticsPage],
  ["/graph", GraphPage],
  ["/reports", ReportsPage],
  ["/projects", ProjectsPage]
] as const;

const allWorkspaceRoutePages = [
  [workspaceHomeNavigation.href, WorkspacePage],
  ...routePages,
  ["/guided-check", GuidedCheckPage],
  ["/rules", RulesPage],
  ["/remediation", RemediationPage],
  ["/archive", ArchivePage],
] as const;

describe("workspace foundation pages", () => {
  it("keeps Next-owned portal targets backed by a page with one h1", () => {
    expect(routePages.map(([href]) => href)).toEqual(
      primaryNavigation.filter((item) => item.target === "workspace").map((item) => item.href)
    );

    for (const [href, Page] of routePages) {
      const { unmount } = render(<Page />);

      expect(screen.getAllByRole("heading", { level: 1 }), href).toHaveLength(1);

      unmount();
    }
  });

  it("covers every workspace navigation target with an implemented page", () => {
    const configuredWorkspaceRoutes = [
      workspaceHomeNavigation,
      ...primaryNavigation,
      ...secondaryNavigation
    ].map((item) => item.href);

    expect(allWorkspaceRoutePages.map(([href]) => href).sort()).toEqual(configuredWorkspaceRoutes.sort());

    for (const [, Page] of allWorkspaceRoutePages) {
      const { unmount } = render(<Page />);
      expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
      unmount();
    }
  });

  it("exposes the dashboard sections owned by the workspace page", async () => {
    render(<WorkspacePage />);

    expect(screen.getByRole("region", { name: "项目关键指标" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "当前阶段：形成判断" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "需要人工处理" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "项目审计链动态" })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getAllByText("FastAPI 正常").length).toBeGreaterThan(0);
    });
  });

  it("renders the current self-check project dashboard", async () => {
    render(<WorkspacePage />);

    expect(screen.getByRole("heading", { name: "医保基金使用合规专项自查" })).toBeInTheDocument();
    expect(screen.getByText("待处理疑点")).toBeInTheDocument();
    expect(screen.getByText("待补证据")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getAllByText("FastAPI 正常").length).toBeGreaterThan(0);
    });
  });

  it("keeps legacy real routes outside the primary portal navigation", async () => {
    render(<KnowledgeQueryPage />);
    expect(screen.getByRole("heading", { name: "引用优先的知识查询" })).toBeInTheDocument();

    render(<FindingsPage />);
    expect(screen.getByRole("heading", { name: "规则命中疑点工作台" })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "疑点生成链路未就绪" })).toBeInTheDocument();
    });
  });

  it("renders the AI chat portal handoff to backend evidence chat", () => {
    render(<ChatPortalPage />);

    expect(screen.getByRole("heading", { name: "选择智能体后进入审证对话" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "进入审证对话" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "打开后端深页" })).toHaveAttribute("href", "/pages/chat");
  });

  it("renders the guided self-check workbench with steps, prompts and gates", () => {
    render(<GuidedCheckPage />);

    expect(screen.getByRole("heading", { name: "AI 引导自查工作台" })).toBeInTheDocument();
    expect(screen.getByText("已完成步骤")).toBeInTheDocument();
    expect(screen.getByText("可提问模板")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "自查路径" })).toBeInTheDocument();
    expect(screen.getByText("锁定自查范围")).toBeInTheDocument();
    expect(screen.getByText("上传并识别数据")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "AI 提问模板" })).toBeInTheDocument();
    expect(screen.getByText("重复收费复核助手")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "证据门禁" })).toBeInTheDocument();
    expect(screen.getByText("目录限制 HIS 字段截图")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "风险预检" })).toBeInTheDocument();
    expect(screen.getByText("重复收费线索")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "自查动态" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "进入 AI 审证对话" })).toHaveAttribute("href", "/chat");
    expect(screen.getAllByRole("link", { name: "进入对话" })[0]).toHaveAttribute(
      "href",
      expect.stringContaining("/chat?agent=agent-duplicate-charge")
    );
  });

  it("analyzes an uploaded CSV with audit-ready quality hints", async () => {
    render(<AnalyticsPage />);

    const input = screen.getByLabelText("上传审计表格");
    const file = new File(
      [
        [
          "patient_id,visit_date,item_code,charge_amount,insurance_pay",
          "P001,2026-01-01,A100,120.00,80.00",
          "P001,2026-01-01,A100,120.00,80.00",
          "P002,2026-01-02,B200,,50.00"
        ].join("\n")
      ],
      "charge-sample.csv",
      { type: "text/csv" }
    );

    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      expect(uploadAnalysisTable).toHaveBeenCalledWith(file);
    });
    await waitFor(() => {
      expect(fetchAnalysisUploadHistory).toHaveBeenCalled();
    });
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "charge-sample.csv" })).toBeInTheDocument();
    });
    expect(screen.getByText("数据质量提示")).toBeInTheDocument();
    expect(screen.getByText("审计初步分析")).toBeInTheDocument();
    expect(screen.getByText("金额/费用字段")).toBeInTheDocument();
    expect(screen.getByText("重复收费核验字段基础完整，可按患者/就诊、项目、日期和金额形成初筛分组。")).toBeInTheDocument();
    expect(screen.getByText("发现 1 条完全重复行。")).toBeInTheDocument();
    expect(screen.getByText("上传历史")).toBeInTheDocument();
    expect(screen.getByText("history-charge.csv")).toBeInTheDocument();
  });

  it("renders project list and creates project members through the backend API", async () => {
    render(<ProjectsPage />);

    expect(screen.getByRole("heading", { name: "审计项目管理" })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("项目后端已连接")).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText("成员后端已连接")).toBeInTheDocument();
    });
    expect(screen.getByRole("heading", { name: "项目列表" })).toBeInTheDocument();
    expect(screen.getByText("项目名称")).toBeInTheDocument();
    expect(screen.getByText("成员数")).toBeInTheDocument();
    expect(screen.getByText("创建人")).toBeInTheDocument();
    expect(screen.getByText("创建时间")).toBeInTheDocument();
    expect(screen.getByText("医保目录限制条件核验")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "查看成员" }));
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "医保目录限制条件核验" })).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText("姓名"), { target: { value: "赵审计" } });
    fireEvent.change(screen.getByLabelText("部门"), { target: { value: "医保办" } });
    fireEvent.click(screen.getByRole("button", { name: "添加成员" }));

    await waitFor(() => {
      expect(createProjectMember).toHaveBeenCalledWith("CATALOG-LIMIT-202606", {
        name: "赵审计",
        role: "审计员",
        department: "医保办"
      });
    });
    expect(screen.getByText("赵审计")).toBeInTheDocument();
    expect(screen.getAllByText("医保办").length).toBeGreaterThan(0);
    expect(screen.getAllByText("待确认").length).toBeGreaterThan(0);
  });

  it("filters agent marketplace templates and keeps agent chat handoff in the portal", async () => {
    render(<AgentMarketPage />);

    expect(screen.getByRole("heading", { name: "医疗审计场景模板" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "智能体分类筛选" })).toBeInTheDocument();
    expect(screen.getByText("医保目录限制审查")).toBeInTheDocument();
    expect(screen.getByText("审计底稿生成模板")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "效率类" }));
    expect(screen.getByText("审计底稿生成模板")).toBeInTheDocument();
    expect(screen.queryByText("医保目录限制审查")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "全部" }));
    fireEvent.change(screen.getByLabelText("搜索智能体模板"), { target: { value: "身份" } });
    expect(screen.getByText("参保身份异常核验")).toBeInTheDocument();
    expect(screen.queryByText("政策口径对比")).not.toBeInTheDocument();

    render(<AgentsPage />);
    await waitFor(() => {
      expect(screen.getByText("后端已连接")).toBeInTheDocument();
    });
    expect(screen.getAllByText("医保基金使用合规专项自查").length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "进入对话" })[0]).toHaveAttribute("href", "/chat?agent=agent-citation-check");
  });

  it("creates a custom audit agent through the backend API", async () => {
    render(<AgentsPage />);

    await waitFor(() => {
      expect(screen.getByText("后端已连接")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText("名称"), { target: { value: "目录限制核验助手" } });
    fireEvent.change(screen.getByLabelText("审计专题"), { target: { value: "医保目录限制条件核验" } });
    fireEvent.change(screen.getByLabelText("提示词"), {
      target: { value: "仅基于目录限制字段和引用依据输出待补证问题。" }
    });
    fireEvent.click(screen.getByRole("button", { name: "新增智能体" }));

    await waitFor(() => {
      expect(createAuditAgent).toHaveBeenCalledWith({
        name: "目录限制核验助手",
        category: "业务类",
        topic: "医保目录限制条件核验",
        prompt: "仅基于目录限制字段和引用依据输出待补证问题。",
        knowledge_base: "项目默认知识库",
        project_name: "医保基金使用合规专项自查"
      });
    });
    expect(screen.getAllByText("目录限制核验助手").length).toBeGreaterThan(0);
  });

  it("renders read-only knowledge base asset metrics", async () => {
    render(<KnowledgeBasePage />);

    expect(screen.getByRole("heading", { name: "个人、系统、公开知识库" })).toBeInTheDocument();
    expect(screen.getAllByText("个人知识库").length).toBeGreaterThan(0);
    expect(screen.getAllByText("系统知识库").length).toBeGreaterThan(0);
    expect(screen.getAllByText("公开知识库").length).toBeGreaterThan(0);
    expect(screen.getAllByText("文档数").length).toBeGreaterThan(0);
    expect(screen.getAllByText("字符数").length).toBeGreaterThan(0);
    expect(screen.getAllByText("关联应用数").length).toBeGreaterThan(0);
    expect(screen.getAllByText("系统医保审计知识库").length).toBeGreaterThan(0);
    expect(screen.getAllByText("法规政策、医保目录、监管规则和风险负面清单组成的系统检索底座。").length).toBeGreaterThan(0);
    await waitFor(() => {
      expect(screen.getByText("检索索引：就绪（postgres）")).toBeInTheDocument();
    });
  });

  it("falls back to sample knowledge base when search backend probe fails", async () => {
    vi.mocked(fetchSearchBackendStatus).mockRejectedValueOnce(new Error("search service down"));

    render(<KnowledgeBasePage />);

    await waitFor(() => {
      expect(screen.getByText("检索索引：异常")).toBeInTheDocument();
    });
    expect(screen.getByRole("heading", { name: "个人、系统、公开知识库" })).toBeInTheDocument();
  });

  it("runs document search through the backend query API and renders citations", async () => {
    render(<DocumentsPage />);

    expect(screen.getByRole("heading", { name: "材料与知识库统一检索" })).toBeInTheDocument();
    expect(screen.getByLabelText("审计问题或文档关键词")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "搜索历史" })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("医保基金支付异常")).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(fetchDocumentPermissions).toHaveBeenCalled();
    });
    await waitFor(() => {
      expect(fetchDocumentUploads).toHaveBeenCalled();
    });
    expect(screen.getByText("权限已连接")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "个人材料" })).toBeInTheDocument();
    expect(screen.getByText("policy-retained.pdf")).toBeInTheDocument();
    expect(screen.getAllByText("已连接").length).toBeGreaterThan(0);
    expect(screen.getByText("监管两库")).toBeInTheDocument();
    expect(screen.getByText("risk-negative-list")).toBeInTheDocument();
    expect(screen.getByText("等待检索")).toBeInTheDocument();

    const documentFile = new File(["policy"], "policy.pdf", { type: "application/pdf" });
    fireEvent.change(screen.getByLabelText("上传个人知识库材料"), {
      target: { files: [documentFile] }
    });
    fireEvent.click(screen.getByRole("button", { name: "上传材料" }));
    await waitFor(() => {
      expect(uploadPersonalDocument).toHaveBeenCalledWith(documentFile);
    });
    expect(screen.getByText("policy.pdf 已留存，索引状态：not-indexed")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /监管两库/ }));
    fireEvent.change(screen.getByLabelText("审计问题或文档关键词"), {
      target: { value: "医保基金审核依据" }
    });
    fireEvent.click(screen.getByRole("button", { name: "执行检索" }));

    await waitFor(() => {
      expect(runKnowledgeQuery).toHaveBeenCalledWith({
        question: "医保基金审核依据",
        top_k: 8,
        source_collections: ["supervision-rules-knowledge"]
      });
    });
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "医保基金审核依据" })).toBeInTheDocument();
    });
    expect(screen.getByText("应核验诊疗记录、收费明细和政策依据。")).toBeInTheDocument();
    expect(screen.getByText("医疗机构应当保留医保基金审核依据。")).toBeInTheDocument();
    expect(screen.getByText("来源: medical-insurance-laws")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "核验原文" })).toHaveAttribute("href", "/pages/preview/chunk-doc-001");
    expect(screen.getByRole("heading", { name: "对话文档" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "知识库文档" })).toBeInTheDocument();
    expect(screen.getByText("重复收费疑点复核对话")).toBeInTheDocument();
    expect(screen.getByText("医保目录限制条件资料包")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "转入 AI 对话" })[0]).toHaveAttribute(
      "href",
      expect.stringContaining("/chat?question=")
    );
    expect(fetchQueryHistory).toHaveBeenCalled();
  });

  it("renders the read-only knowledge graph coverage view", async () => {
    render(<GraphPage />);

    expect(screen.getByRole("heading", { name: "知识图谱入口" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "审计知识图谱静态关系预览" })).toBeInTheDocument();
    expect(screen.getByText("医保基金使用合规专项图谱")).toBeInTheDocument();
    expect(screen.getByText("节点覆盖")).toBeInTheDocument();
    expect(screen.getByText("节点证据")).toBeInTheDocument();
    expect(screen.getAllByText("项目").length).toBeGreaterThan(0);
    expect(screen.getAllByText("知识库").length).toBeGreaterThan(0);
    expect(screen.getAllByText("文档").length).toBeGreaterThan(0);
    expect(screen.getAllByText("规则").length).toBeGreaterThan(0);
    expect(screen.getAllByText("疑点").length).toBeGreaterThan(0);
    expect(screen.getAllByText("复核").length).toBeGreaterThan(0);
    expect(screen.getAllByText("报告").length).toBeGreaterThan(0);
    expect(screen.getAllByText("整改").length).toBeGreaterThan(0);
    expect(screen.getAllByText("FINDING-F044EBD309B659DC").length).toBeGreaterThan(0);
    expect(screen.getAllByText("review-task-0007").length).toBeGreaterThan(0);
    await waitFor(() => {
      expect(screen.getByText("检索索引：就绪（postgres）")).toBeInTheDocument();
    });
  });

  it("keeps graph sample topology when search backend probe fails", async () => {
    vi.mocked(fetchSearchBackendStatus).mockRejectedValueOnce(new Error("search service down"));

    render(<GraphPage />);

    await waitFor(() => {
      expect(screen.getByText("检索索引：异常")).toBeInTheDocument();
    });
    expect(screen.getByRole("heading", { name: "知识图谱入口" })).toBeInTheDocument();
  });

  it("renders the report homepage with gates, evidence and remediation", () => {
    render(<ReportsPage />);

    expect(screen.getByRole("heading", { name: "底稿生成与报告记录" })).toBeInTheDocument();
    expect(screen.getByText("已签发报告")).toBeInTheDocument();
    expect(screen.getAllByText("门禁阻断").length).toBeGreaterThan(0);
    expect(screen.getAllByText("纳入疑点").length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: "历史生成记录" })).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { name: "报告门禁预检" }).length).toBeGreaterThan(0);
    expect(screen.getByText("底稿与负责人确认")).toBeInTheDocument();
    expect(screen.getByText("附件登记与报告草稿")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "底稿证据来源" })).toBeInTheDocument();
    expect(screen.getByText("workpaper-20260604-001")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "整改跟踪" })).toBeInTheDocument();
    expect(screen.getByText("重复收费退费与流程复核")).toBeInTheDocument();
    expect(screen.getAllByText("AUDIT-REPORT-20260611-001").length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "查看详情" })[0]).toHaveAttribute("href", "/pages/review-tasks");
  });

  it("renders the remediation homepage with evidence requests and closure gates", () => {
    render(<RemediationPage />);

    expect(screen.getByRole("heading", { name: "整改事项与补证闭环" })).toBeInTheDocument();
    expect(screen.getByText("未关闭事项")).toBeInTheDocument();
    expect(screen.getByText("待补证材料")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "整改台账" })).toBeInTheDocument();
    expect(screen.getAllByText("重复收费退费与流程复核").length).toBeGreaterThan(0);
    expect(screen.getAllByText("FINDING-F044EBD309B659DC").length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: "补证请求" })).toBeInTheDocument();
    expect(screen.getByText("重复收费退费凭证")).toBeInTheDocument();
    expect(screen.getByText("目录限制 HIS 字段截图")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "关闭门禁" })).toBeInTheDocument();
    expect(screen.getByText("补证材料完整")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "整改动态" })).toBeInTheDocument();
    expect(screen.getByText("附件归档校验阻断")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "查看报告来源" })).toHaveAttribute("href", "/reports");
    expect(screen.getAllByRole("link", { name: "查看详情" })[0]).toHaveAttribute("href", "/pages/review-tasks");
  });

  it("renders the archive homepage with packages, audit runs and signature chain", async () => {
    render(<ArchivePage />);

    expect(screen.getByRole("heading", { name: "项目档案与审计日志归档" })).toBeInTheDocument();
    expect(screen.getByText("已归档项目")).toBeInTheDocument();
    expect(screen.getByText("待归档档案")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "项目档案包" })).toBeInTheDocument();
    expect(screen.getAllByText("医保基金使用合规专项自查").length).toBeGreaterThan(0);
    expect(screen.getAllByText("ARCHIVE-SELF-CHECK-FUND-202606").length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: "审计日志治理策略" })).toBeInTheDocument();
    expect(screen.getByText("180 days")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "归档巡检" })).toBeInTheDocument();
    expect(screen.getByText("archive root 巡检")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "签名链" })).toBeInTheDocument();
    expect(screen.getByText("retention-batch-0001.jsonl")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "入档动态" })).toBeInTheDocument();
    expect(screen.getByText("附件 hash 阻断归档")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "打开审计日志台" })).toHaveAttribute("href", "/pages/audit-logs");
    expect(screen.getAllByRole("link", { name: "查看档案" })[0]).toHaveAttribute("href", "/reports");
    expect(screen.getAllByRole("link", { name: "查看日志" })[0]).toHaveAttribute(
      "href",
      "/pages/audit-logs?entity_type=review-task&entity_id=review-task-0001"
    );
    await waitFor(() => {
      expect(screen.getByText("检索索引：就绪（postgres）")).toBeInTheDocument();
    });
  });

  it("keeps archive samples when search backend probe fails", async () => {
    vi.mocked(fetchSearchBackendStatus).mockRejectedValueOnce(new Error("search service down"));

    render(<ArchivePage />);

    await waitFor(() => {
      expect(screen.getByText("检索索引：异常")).toBeInTheDocument();
    });
    expect(screen.getByRole("heading", { name: "项目档案与审计日志归档" })).toBeInTheDocument();
    expect(screen.getByText("ARCHIVE-SELF-CHECK-FUND-202606")).toBeInTheDocument();
  });

  it("renders the rules homepage with sources, runs and release gates", async () => {
    render(<RulesPage />);

    expect(screen.getByRole("heading", { name: "审计规则与依据总览" })).toBeInTheDocument();
    expect(screen.getByText("可运行规则")).toBeInTheDocument();
    expect(screen.getByText("待处理规则")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "规则清单" })).toBeInTheDocument();
    expect(screen.getAllByText("CHARGE-RULE-001").length).toBeGreaterThan(0);
    expect(screen.getAllByText("CATALOG-RULE-014").length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: "最近运行" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "来源覆盖" })).toBeInTheDocument();
    expect(screen.getAllByText("监管两库").length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: "发布门禁" })).toBeInTheDocument();
    expect(screen.getByText("字段可运行")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "打开索引管理" })).toHaveAttribute("href", "/pages/index-admin");
    expect(screen.getAllByRole("link", { name: "查看" })[0]).toHaveAttribute("href", "/findings?rule=CHARGE-RULE-001");
    expect(screen.getAllByRole("link", { name: "审证" })[0]).toHaveAttribute("href", expect.stringContaining("/chat?question="));
    await waitFor(() => {
      expect(screen.getByText("检索索引：就绪（postgres）")).toBeInTheDocument();
    });
  });

  it("keeps rule samples when search backend probe fails", async () => {
    vi.mocked(fetchSearchBackendStatus).mockRejectedValueOnce(new Error("search service down"));

    render(<RulesPage />);

    await waitFor(() => {
      expect(screen.getByText("检索索引：异常")).toBeInTheDocument();
    });
    expect(screen.getByRole("heading", { name: "审计规则与依据总览" })).toBeInTheDocument();
    expect(screen.getAllByText("CHARGE-RULE-001").length).toBeGreaterThan(0);
  });
});
