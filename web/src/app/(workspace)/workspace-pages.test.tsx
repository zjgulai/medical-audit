import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { primaryNavigation } from "@/lib/navigation";

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
  fetchSearchBackendStatus: vi.fn(async () => ({
    backend: "postgres",
    ready: true,
    details: { matching_embedding_count: 48985 }
  })),
  runKnowledgeQuery: vi.fn()
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
      expect(screen.getByRole("heading", { name: "charge-sample.csv" })).toBeInTheDocument();
    });
    expect(screen.getByText("数据质量提示")).toBeInTheDocument();
    expect(screen.getByText("审计初步分析")).toBeInTheDocument();
    expect(screen.getByText("金额/费用字段")).toBeInTheDocument();
    expect(screen.getByText("重复收费核验字段基础完整，可按患者/就诊、项目、日期和金额形成初筛分组。")).toBeInTheDocument();
    expect(screen.getByText("发现 1 条完全重复行。")).toBeInTheDocument();
  });

  it("renders project list and member management controls", () => {
    render(<ProjectsPage />);

    expect(screen.getByRole("heading", { name: "审计项目管理" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "项目列表" })).toBeInTheDocument();
    expect(screen.getByText("项目名称")).toBeInTheDocument();
    expect(screen.getByText("成员数")).toBeInTheDocument();
    expect(screen.getByText("创建人")).toBeInTheDocument();
    expect(screen.getByText("创建时间")).toBeInTheDocument();
    expect(screen.getByText("医保目录限制条件核验")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "查看成员" }));
    expect(screen.getByRole("heading", { name: "医保目录限制条件核验" })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("姓名"), { target: { value: "赵审计" } });
    fireEvent.change(screen.getByLabelText("部门"), { target: { value: "医保办" } });
    fireEvent.click(screen.getByRole("button", { name: "添加成员" }));

    expect(screen.getByText("赵审计")).toBeInTheDocument();
    expect(screen.getByText("医保办")).toBeInTheDocument();
    expect(screen.getAllByText("待确认").length).toBeGreaterThan(0);
  });

  it("filters agent marketplace templates and keeps agent chat handoff in the portal", () => {
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
    expect(screen.getAllByText("医保基金使用合规专项自查").length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "进入对话" })[0]).toHaveAttribute("href", "/chat?agent=agent-citation-check");
  });

  it("renders read-only knowledge base asset metrics", () => {
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
  });

  it("renders the document search homepage with history and document groups", () => {
    render(<DocumentsPage />);

    expect(screen.getByRole("heading", { name: "材料与知识库统一检索" })).toBeInTheDocument();
    expect(screen.getByLabelText("审计问题或文档关键词")).toBeInTheDocument();
    expect(screen.getByLabelText("仅标题")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "搜索历史" })).toBeInTheDocument();
    expect(screen.getByText("医保基金支付异常")).toBeInTheDocument();
    expect(screen.getByText("监管两库")).toBeInTheDocument();
    expect(screen.getByText("risk-negative-list")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "对话文档" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "知识库文档" })).toBeInTheDocument();
    expect(screen.getByText("重复收费疑点复核对话")).toBeInTheDocument();
    expect(screen.getByText("医保目录限制条件资料包")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "转入 AI 对话" })[0]).toHaveAttribute("href", "/chat");
  });

  it("renders the read-only knowledge graph coverage view", () => {
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

  it("renders the archive homepage with packages, audit runs and signature chain", () => {
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
  });

  it("renders the rules homepage with sources, runs and release gates", () => {
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
  });
});
