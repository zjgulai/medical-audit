import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  addMedicalAuditFindingToReport,
  createMedicalAuditReviewTask,
  fetchAuditFindings,
  fetchDocumentSourceCollections,
  fetchProjectDashboard,
  fetchProjects,
  fetchReportWorkbench,
  recordMedicalAuditImportPreflight,
  registerMedicalAuditSupplement,
  updateMedicalAuditReviewStatus
} from "@/lib/api-client";
import type {
  AuditFindingsResponse,
  DocumentSourceCollectionCatalogResponse,
  MedicalAuditWorkflowActionResponse,
  ProjectDashboardResponse,
  ProjectsResponse,
  ReportWorkbenchResponse
} from "@/lib/api-types";

import MedicalAuditPage from "./page";

vi.mock("@/lib/api-client", () => ({
  addMedicalAuditFindingToReport: vi.fn(),
  createMedicalAuditReviewTask: vi.fn(),
  fetchAuditFindings: vi.fn(),
  fetchDocumentSourceCollections: vi.fn(),
  fetchProjectDashboard: vi.fn(),
  fetchProjects: vi.fn(),
  fetchReportWorkbench: vi.fn(),
  recordMedicalAuditImportPreflight: vi.fn(),
  registerMedicalAuditSupplement: vi.fn(),
  updateMedicalAuditReviewStatus: vi.fn()
}));

const addMedicalAuditFindingToReportMock = vi.mocked(addMedicalAuditFindingToReport);
const createMedicalAuditReviewTaskMock = vi.mocked(createMedicalAuditReviewTask);
const fetchAuditFindingsMock = vi.mocked(fetchAuditFindings);
const fetchDocumentSourceCollectionsMock = vi.mocked(fetchDocumentSourceCollections);
const fetchProjectDashboardMock = vi.mocked(fetchProjectDashboard);
const fetchProjectsMock = vi.mocked(fetchProjects);
const fetchReportWorkbenchMock = vi.mocked(fetchReportWorkbench);
const recordMedicalAuditImportPreflightMock = vi.mocked(recordMedicalAuditImportPreflight);
const registerMedicalAuditSupplementMock = vi.mocked(registerMedicalAuditSupplement);
const updateMedicalAuditReviewStatusMock = vi.mocked(updateMedicalAuditReviewStatus);

const auditFindingsResponse: AuditFindingsResponse = {
  items: [
    {
      finding_key: "finding-f044ebd309b659dc",
      status: "open",
      finding_type: "medical-insurance-policy",
      severity: "medium",
      review_status: "confirmed-violation",
      review_task_id: "review-task-0007",
      source_record_locator: { source_table: "visit_charge_detail", visit_id: "VISIT-0001" },
      calculation_trace: { total_amount: 1280.5, matched_rule: "policy-drug-scope" },
      metadata: {
        department: "骨科",
        subject: "医保目录限制药品"
      },
      created_at: "2026-07-07T01:00:00Z",
      updated_at: "2026-07-07T02:00:00Z",
      audit_run_key: "run-20260707",
      audit_task_key: "task-medical-audit",
      rule_key: "policy-drug-scope",
      rule_version_key: "policy-drug-scope@2026-07",
      evidence_items: [
        {
          evidence_type: "knowledge-citation",
          chunk_id: "chunk-001",
          source_package_version_key: "package-v1",
          index_version_key: "index-v1",
          citation_id: "CIT-001",
          locator: { title: "医保基金监管政策" },
          snippet: "限定支付范围应结合诊断和医保目录核验。",
          metadata: {},
          created_at: "2026-07-07T02:00:00Z"
        }
      ]
    }
  ],
  stats: { total: 1, open: 1, pending_review: 0, linked_review_task: 1 },
  filters: { review_status: null, limit: 20 },
  review_status_options: { "confirmed-violation": "确认违规", "pending-review": "待复核" },
  generation_readiness: {
    status: "generated",
    ready: true,
    has_findings: true,
    table_counts: { audit_findings: 1 },
    prerequisites: [],
    blocking_reasons: [],
    next_actions: ["从疑点清单创建人工复核任务。"]
  },
  store: { ready: true, backend: "SqlAlchemyAuditFindingStore" }
};

const sourceCollectionsResponse: DocumentSourceCollectionCatalogResponse = {
  contract_version: "document-source-collections-v1",
  role: "auditor",
  items: [
    {
      source_collection: "medical-insurance-laws",
      label: "医保法规库",
      scope: "tenant",
      phase: "active",
      domain: "medical-audit",
      evidence_group: "policy",
      description: "医保基金监管政策、目录与处罚依据。",
      audit_hint: "用于医保审计规则解释。",
      access: "read",
      product_queryable: true,
      queryable: true,
      metrics: {
        document_count: 300,
        chunk_count: 1200,
        character_count: 900000,
        linked_app_count: 4
      }
    }
  ],
  search_backend: { ready: true, backend: "postgres-bm25", details: {} },
  upload_permissions: {
    can_upload_personal: true,
    can_read_all_personal_uploads: true,
    can_govern_personal_uploads: true
  },
  boundaries: {
    production_write: false,
    provider_call: false,
    database_write: false,
    object_storage_write: false,
    source: "runtime_state_and_registry_only"
  }
};

const reportWorkbenchResponse: ReportWorkbenchResponse = {
  format: "report-workbench-v1",
  generated_at: "2026-07-07T02:30:00Z",
  template_registry_status: "active",
  template_categories: [
    { id: "plan", label: "计划类", availability: "awaiting-business-template" },
    { id: "workpaper", label: "底稿类", availability: "active" },
    { id: "evidence", label: "取证类", availability: "awaiting-business-template" },
    { id: "confirmation", label: "函证类", availability: "awaiting-business-template" },
    { id: "report", label: "报告类", availability: "awaiting-business-template" },
    { id: "remediation", label: "整改类", availability: "awaiting-business-template" }
  ],
  workpaper_templates: [
    {
      id: "template-fee-summary",
      category_id: "workpaper",
      name: "医保费用汇总表",
      source_template_id: "table1",
      source_table: "fee_summary",
      source_file_name: "表1_医保费用汇总表.xlsx",
      sheet_name: "费用汇总",
      output_type: "底稿草稿",
      registry_status: "active",
      expected_columns: ["机构编码", "机构名称", "就诊人次", "总费用", "基金支付"],
      key_checks: [],
      evidence_bindings: [],
      prompt: "生成医保费用汇总表底稿。",
      chat_href: "/chat?question=医保费用汇总表"
    }
  ],
  report_entries: [],
  report_evidence_sources: [],
  metrics: {
    report_count: 2,
    signed_report_count: 0,
    blocked_report_count: 1,
    included_finding_count: 1,
    docx_download_count: 0
  },
  store: { ready: true, backend: "SqlAlchemyReviewTaskStore" }
};

const projectSummary = {
  id: "SELF-CHECK-FUND-20260607",
  name: "医保基金使用合规专项自查",
  audit_topic: "医保基金使用合规",
  organization_name: "单院医保内审试运行",
  member_count: 3,
  creator: "审计办",
  creator_user_identifier: "next-director",
  created_at: "2026-06-07T00:00:00Z",
  status: "进行中",
  operation_label: "进入专题",
  source: "system-default"
} as const;

const projectsResponse: ProjectsResponse = {
  items: [projectSummary],
  roles: ["项目负责人", "审计员", "业务专家", "信息科", "只读观察员"],
  statuses: ["在项目中", "待确认"],
  project_statuses: ["待开始", "进行中", "已完成", "已归档"],
  store: { ready: true, backend: "SqlAlchemyProjectMemberStore" }
};

const projectDashboardResponse: ProjectDashboardResponse = {
  format: "project-dashboard-v1",
  project: projectSummary,
  metrics: [
    {
      key: "open_findings",
      label: "未闭环疑点",
      value: "1",
      helper: "来自审计疑点库",
      tone: "warning"
    }
  ],
  queue: [
    {
      id: "queue-1",
      title: "核对非目录项目发生基金支付的结算明细",
      owner: "医保办",
      dueLabel: "今日",
      status: "open",
      risk: "medium"
    }
  ],
  activities: [],
  status_distribution: [{ status: "confirmed-violation", label: "确认违规", count: 1 }],
  member_workloads: [
    {
      name: "张主任",
      role: "项目负责人",
      department: "审计办",
      total: 1,
      pending: 1,
      closed: 0
    }
  ],
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
};

const workflowResponse: MedicalAuditWorkflowActionResponse = {
  format: "medical-audit-workflow-action-v1",
  action: "review-task-create",
  status: "created",
  processed_at: "2026-07-08T09:00:00Z",
  actor: {
    user_identifier: "next-admin",
    role: "it-admin",
    auth_source: "header"
  },
  task: {
    task_id: "review-task-0010",
    status: "pending-review",
    status_label: "待复核",
    question: "复核疑点 finding-f044ebd309b659dc",
    citation_count: 1,
    review_gate: "疑点已绑定规则版本、计算过程和证据链，进入人工复核。",
    confidence_label: "中",
    fallback_label: "规则命中",
    reviewer_note: "",
    conclusion: "",
    assigned_to: "",
    source: "medical-audit-workflow",
    dossier: {}
  }
};

function mockApis() {
  fetchAuditFindingsMock.mockResolvedValue(auditFindingsResponse);
  fetchDocumentSourceCollectionsMock.mockResolvedValue(sourceCollectionsResponse);
  fetchProjectsMock.mockResolvedValue(projectsResponse);
  fetchProjectDashboardMock.mockResolvedValue(projectDashboardResponse);
  fetchReportWorkbenchMock.mockResolvedValue(reportWorkbenchResponse);
  addMedicalAuditFindingToReportMock.mockResolvedValue({
    ...workflowResponse,
    action: "report-entry-add",
    status: "added"
  });
  createMedicalAuditReviewTaskMock.mockResolvedValue(workflowResponse);
  recordMedicalAuditImportPreflightMock.mockResolvedValue({
    ...workflowResponse,
    action: "import-preflight",
    status: "preflight_recorded",
    task: undefined
  });
  registerMedicalAuditSupplementMock.mockResolvedValue({
    ...workflowResponse,
    action: "supplemental-material-register",
    status: "registered"
  });
  updateMedicalAuditReviewStatusMock.mockResolvedValue({
    ...workflowResponse,
    action: "review-status-update",
    status: "updated"
  });
}

describe("MedicalAuditPage", () => {
  afterEach(() => {
    vi.clearAllMocks();
    vi.restoreAllMocks();
  });

  it("renders production audit findings and removes the old static metric baseline", async () => {
    mockApis();

    render(<MedicalAuditPage />);

    await waitFor(() => {
      expect(screen.getAllByText("finding-f044ebd309b659dc").length).toBeGreaterThanOrEqual(1);
    });

    expect(fetchAuditFindingsMock).toHaveBeenCalledWith(undefined);
    expect(fetchDocumentSourceCollectionsMock).toHaveBeenCalled();
    expect(fetchProjectsMock).toHaveBeenCalled();
    expect(fetchProjectDashboardMock).toHaveBeenCalledWith("SELF-CHECK-FUND-20260607");
    expect(fetchReportWorkbenchMock).toHaveBeenCalled();
    expect(screen.getByText("疑点数据已同步")).toBeInTheDocument();
    expect(screen.getByText("知识库分类已同步")).toBeInTheDocument();
    expect(screen.getByText("底稿与报告数据已同步")).toBeInTheDocument();
    expect(screen.getByText("知识检索可用")).toBeInTheDocument();
    expect(screen.queryByText(/检索后端/)).not.toBeInTheDocument();
    expect(screen.queryByText(/SqlAlchemyAuditFindingStore/)).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "医保基金使用合规专项自查" })).toBeInTheDocument();
    expect(screen.getByText("核对非目录项目发生基金支付的结算明细")).toBeInTheDocument();
    expect(screen.getByText("张主任")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "打开医保审计助手" })).toHaveAttribute(
      "data-layout-floating-control",
      "medical-ai"
    );
    expect(screen.getByRole("button", { name: "DIP/DRG审计" })).toHaveTextContent("DIP/DRG审计");
    expect(screen.getByText("查看数据与权限说明").closest("details")).not.toHaveAttribute("open");
    expect(screen.getByText(/页面初始加载读取生产数据/)).toBeInTheDocument();
    expect(screen.queryByText("当前页面只读取生产数据；写入类动作仍需经过独立确认门禁。")).not.toBeInTheDocument();
    expect(screen.queryByText("207")).not.toBeInTheDocument();
    expect(screen.queryByText("20251203001")).not.toBeInTheDocument();
  });

  it("keeps backend failure detail behind a diagnostic disclosure", async () => {
    mockApis();
    fetchAuditFindingsMock.mockRejectedValueOnce(
      new Error("Backend request failed: GET /api/v1/audit-findings returned 503")
    );

    render(<MedicalAuditPage />);

    expect(await screen.findByText("疑点数据读取异常")).toBeInTheDocument();
    expect(screen.queryByText("疑点接口读取异常")).not.toBeInTheDocument();
    expect(screen.getByText("请检查审计数据服务后重试；当前不会注入本地样例数据。")).toBeInTheDocument();
    expect(screen.getByText("疑点数据暂未同步")).toBeInTheDocument();
    expect(screen.queryByText("读取 /api/v1/audit-findings")).not.toBeInTheDocument();
    const diagnostics = screen.getByText("查看技术诊断").closest("details");
    expect(diagnostics).not.toBeNull();
    expect(diagnostics).toHaveTextContent(
      "Backend request failed: GET /api/v1/audit-findings returned 503"
    );
  });

  it("keeps audit findings visible when the project dashboard is unavailable", async () => {
    mockApis();
    fetchProjectsMock.mockRejectedValueOnce(new Error("project api down"));

    render(<MedicalAuditPage />);

    await waitFor(() => {
      expect(screen.getAllByText("finding-f044ebd309b659dc").length).toBeGreaterThanOrEqual(1);
    });

    expect(screen.getByRole("heading", { name: "专题项目待恢复" })).toBeInTheDocument();
    expect(screen.getByText("专题驾驶舱等待项目数据恢复")).toBeInTheDocument();
    expect(screen.getByText("专题数据暂不可用")).toBeInTheDocument();
    expect(screen.queryByText("专题驾驶舱等待项目接口恢复")).not.toBeInTheDocument();
    expect(fetchProjectDashboardMock).not.toHaveBeenCalled();
  });

  it("opens a backend-backed finding drawer and links context into chat", async () => {
    mockApis();

    render(<MedicalAuditPage />);

    const findingButton = await screen.findByRole("button", { name: "policy drug scope" });
    fireEvent.click(findingButton);

    const drawer = screen.getByLabelText("疑点详情");
    expect(within(drawer).getByText("policy-drug-scope@2026-07")).toBeInTheDocument();
    expect(within(drawer).getByText("限定支付范围应结合诊断和医保目录核验。")).toBeInTheDocument();
    expect(within(drawer).getByRole("link", { name: "AI 分析" })).toHaveAttribute(
      "href",
      expect.stringContaining("/chat?question=")
    );
  });

  it("submits create and import actions through backend workflow contracts", async () => {
    mockApis();

    render(<MedicalAuditPage />);

    fireEvent.click(await screen.findByRole("button", { name: "新建任务" }));
    expect(screen.getByRole("dialog")).toHaveTextContent("创建审计任务草稿");
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "创建复核任务" }));

    await waitFor(() => {
      expect(createMedicalAuditReviewTaskMock).toHaveBeenCalledWith("finding-f044ebd309b659dc", {
        note: "从医保审计工作台创建复核任务"
      });
    });
    expect(screen.getByRole("dialog")).toHaveTextContent("复核任务已关联：review-task-0010");

    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "关闭" }));
    fireEvent.click(screen.getByRole("button", { name: "批量导入" }));
    expect(screen.getByRole("dialog")).toHaveTextContent("批量导入预检");
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "记录导入预检" }));

    await waitFor(() => {
      expect(recordMedicalAuditImportPreflightMock).toHaveBeenCalledWith({
        template_id: "table1",
        template_name: "医保费用汇总表",
        file_name: null,
        row_count: null,
        note: "医保审计页面触发导入预检，等待上传与字段映射。"
      });
    });
  });

  it("uses report workbench templates for the fee summary tab instead of fake rows", async () => {
    mockApis();

    render(<MedicalAuditPage />);

    fireEvent.click(await screen.findByRole("tab", { name: "费用汇总表" }));

    await waitFor(() => {
      expect(screen.getByText("模板已就绪")).toBeInTheDocument();
    });
    expect(screen.getAllByText("医保费用汇总表").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/机构编码/)).toBeInTheDocument();
    expect(screen.getByText(/立即导入/)).toBeInTheDocument();
  });
});
