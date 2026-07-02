import { expect, test, type Page } from "@playwright/test";

async function mockJson(page: Page, url: string | RegExp, body: unknown, status = 200) {
  await page.route(url, (route) =>
    route.fulfill({
      status,
      contentType: "application/json; charset=utf-8",
      body: JSON.stringify(body)
    })
  );
}

async function mockCommonPortalBackend(page: Page) {
  await mockJson(page, "**/api/backend/index/search-backend", {
    backend: "playwright-fixture",
    ready: true,
    details: { matching_embedding_count: 12 }
  });
  await mockJson(page, "**/api/v1/auth/session", {
    user_identifier: "next-admin",
    role: "admin",
    role_label: "管理员",
    permissions: [
      "manage_project_members",
      "read_documents",
      "upload_personal_documents",
      "govern_personal_uploads"
    ],
    legacy_api_role: "admin",
    tenant_id: null,
    auth_source: "playwright-fixture",
    profile_status: "active",
    auth_scope_type: "project",
    auth_scope_key: "SELF-CHECK-FUND-20260607",
    auth_mode: "header_transition_layer",
    profile: null,
    store: { ready: true, backend: "playwright-fixture" }
  });
}

async function mockFindingsWorkbench(page: Page) {
  await mockJson(page, "**/api/v1/audit-findings**", {
    items: [],
    stats: { total: 0, open: 0, pending_review: 0, linked_review_task: 0 },
    filters: { review_status: null, limit: 100 },
    review_status_options: { "pending-review": "待复核", closed: "已关闭" },
    generation_readiness: {
      status: "blocked",
      ready: false,
      has_findings: false,
      table_counts: { audit_projects: 0, his_staging_rows: 0, audit_findings: 0 },
      prerequisites: [
        { key: "audit_projects", label: "审计项目", count: 0, ready: false, required: true }
      ],
      blocking_reasons: [
        { code: "store-not-ready", message: "疑点 store 未初始化，无法读取规则生成链路状态。" }
      ],
      next_actions: ["先完成业务数据底座同步。"]
    },
    store: { ready: true, backend: "playwright-fixture" }
  });
}

async function mockAnalyticsWorkbench(page: Page) {
  await mockJson(page, "**/api/v1/analytics/table-uploads", {
    items: [],
    store: { ready: true, backend: "playwright-fixture" }
  });
  await mockJson(page, "**/api/v1/analytics/table-upload", {
    name: "charge-sample.csv",
    size_kb: 1,
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
        audit_hint: "患者标识字段"
      },
      {
        name: "charge_amount",
        type: "数值",
        empty_count: 1,
        unique_count: 2,
        sample_values: ["120.00"],
        audit_hint: "金额/费用字段"
      }
    ],
    row_count: 3,
    empty_cell_count: 1,
    duplicate_row_count: 1,
    message: "已生成字段画像。",
    quality_findings: ["发现 1 条完全重复行。"],
    audit_signals: ["金额/费用字段"],
    recommendations: ["金额字段可用于识别重复收费。"],
    upload_id: "upload-e2e-001",
    sha256: "e2e-fixture-sha256",
    retention_status: "retained",
    created_at: "2026-06-30T00:00:00Z"
  });
}

async function mockProjectWorkbench(page: Page) {
  const roles = ["项目负责人", "审计员", "业务专家", "信息科", "只读观察员"];
  const statuses = ["在项目中", "待确认"];

  await mockJson(page, "**/api/v1/projects", {
    items: [
      {
        id: "CATALOG-LIMIT-202606",
        name: "医保目录限制条件核验",
        audit_topic: "医保目录限制条件核验",
        organization_name: "单院医保内审试运行",
        member_count: 3,
        creator: "项目负责人",
        created_at: "2026-06-09",
        status: "进行中",
        operation_label: "查看成员",
        source: "system-default"
      }
    ],
    roles,
    statuses,
    store: { ready: true, backend: "playwright-fixture" }
  });

  await page.route("**/api/v1/projects/*/members", (route) => {
    const body =
      route.request().method() === "POST"
        ? {
            item: {
              id: "member-zhao-audit",
              project_key: "CATALOG-LIMIT-202606",
              name: "赵审计",
              role: "审计员",
              department: "医保办",
              status: "在项目中",
              created_by: "next-admin",
              created_at: "2026-06-30T00:00:00Z",
              updated_at: "2026-06-30T00:00:00Z",
              source: "custom",
              metadata: {}
            },
            store: { ready: true, backend: "playwright-fixture" }
          }
        : {
            items: [
              {
                id: "member-owner",
                project_key: "CATALOG-LIMIT-202606",
                name: "周主任",
                role: "项目负责人",
                department: "医保办",
                status: "在项目中",
                created_by: "system",
                source: "system-default",
                metadata: {}
              }
            ],
            project_key: "CATALOG-LIMIT-202606",
            roles,
            statuses,
            store: { ready: true, backend: "playwright-fixture" }
          };

    return route.fulfill({
      status: 200,
      contentType: "application/json; charset=utf-8",
      body: JSON.stringify(body)
    });
  });
}

async function mockDocumentWorkbench(page: Page) {
  const uploadPermissions = {
    can_upload_personal: true,
    can_read_all_personal_uploads: true,
    can_govern_personal_uploads: true
  };

  await mockJson(page, "**/api/v1/documents/permissions", {
    role: "admin",
    source_collections: [
      {
        source_collection: "medical-insurance-laws",
        label: "监管两库",
        scope: "system",
        access: "read"
      },
      {
        source_collection: "risk-negative-list",
        label: "risk-negative-list",
        scope: "system",
        access: "read"
      }
    ],
    upload_permissions: uploadPermissions
  });
  await mockJson(page, "**/api/v1/documents/uploads", {
    items: [],
    store: { ready: true, backend: "playwright-fixture" },
    permissions: uploadPermissions
  });
  await mockJson(page, "**/api/v1/query/logs**", {
    items: [],
    store: { ready: true, backend: "playwright-fixture" }
  });
  await mockJson(page, "**/api/v1/query", {
    question: "医保基金审核依据是什么",
    answer: "医保基金审核依据应以监管两库、医保目录限制条件和风险负面清单共同核验。",
    confidence: "medium",
    fallback_used: false,
    basis_groups: [],
    citations: [
      {
        citation_id: "citation-e2e-001",
        marker: "[1]",
        chunk_id: "chunk-e2e-001",
        evidence_type: "法规依据",
        source_collection: "medical-insurance-laws",
        snippet: "医保基金使用应遵循目录限制条件、支付范围和监管规则。",
        locator: { title: "医保目录限制条件资料包" },
        index_version_key: "active",
        source_package_version_key: "fixture"
      }
    ],
    personal_upload_matches: [],
    query_log_index: 1,
    query_log_id: "query-e2e-001"
  });
}

test.beforeEach(async ({ page }) => {
  await mockCommonPortalBackend(page);
});

const portalAuditRoutes = [
  "/",
  "/workspace",
  "/fund-compliance",
  "/fund-compliance/review",
  "/chat",
  "/agents",
  "/agent-market",
  "/knowledge-base",
  "/documents",
  "/analytics",
  "/graph",
  "/reports",
  "/projects",
  "/guided-check",
  "/rules",
  "/remediation",
  "/archive",
  "/knowledge-query",
  "/findings"
] as const;

async function expectNoBrokenImages(page: Page) {
  const brokenImages = await page.locator("img").evaluateAll((images) =>
    images
      .filter((image) => image.naturalWidth === 0 || image.naturalHeight === 0)
      .map((image) => image.getAttribute("src") ?? "")
  );

  expect(brokenImages).toEqual([]);
}

test("AI audit portal foundation renders navigation and core modules", async ({ page }) => {
  await page.goto("/documents");

  const primaryNavigation = page.getByRole("navigation", { name: "主导航" });
  const chatLink = primaryNavigation.getByRole("link", { name: /审计助手/ });
  const topicLink = primaryNavigation.getByRole("link", { name: /基金合规/ });

  await expect(page.getByText("医保智能审计平台")).toBeVisible();
  await expect(page.getByTestId("auditscope-brand-logo")).toBeVisible();
  await expect(topicLink).toHaveAttribute("href", "/fund-compliance");
  const navigationBox = await primaryNavigation.boundingBox();

  expect(navigationBox).not.toBeNull();

  await expect(page.getByRole("heading", { name: "文档依据检索" })).toBeVisible();
  await expect(chatLink).toBeVisible();
  await expect(chatLink).toHaveAttribute("href", "/chat");
  await expect(primaryNavigation.getByRole("link", { name: /工作台/ })).toHaveAttribute("href", "/workspace");
  await expect(primaryNavigation.getByRole("link", { name: /文档依据/ })).toHaveAttribute("href", "/documents");
  await expect(primaryNavigation.getByRole("link", { name: /项目归档/ })).toHaveAttribute("href", "/archive");
  await expect(primaryNavigation.getByRole("link")).toHaveCount(5);
  await page.getByText("更多功能").click();
  await expect(page.getByRole("link", { name: /我的助手/ })).toHaveAttribute("href", "/agents");
  await expect(page.getByRole("link", { name: /助手库/ })).toHaveAttribute("href", "/agent-market");
  await expect(page.getByRole("link", { name: /依据库/ })).toHaveAttribute("href", "/knowledge-base");
  await expect(page.getByRole("link", { name: /数据分析/ })).toHaveAttribute("href", "/analytics");
  await page.getByText("全部功能").click();
  await expect(page.getByRole("link", { name: /关系图谱/ })).toHaveAttribute("href", "/graph");
  await expect(page.getByRole("link", { name: "底稿生成" })).toHaveAttribute("href", "/reports");
  await expect(page.getByRole("link", { name: /项目空间/ })).toHaveAttribute("href", "/projects");
  await expectNoBrokenImages(page);
});

test("fund compliance topic opens a separate review workbench", async ({ page }) => {
  await page.goto("/fund-compliance");

  await expect(page.getByRole("heading", { name: "医保基金使用合规专项自查" })).toBeVisible();
  await expect(page.getByRole("main").getByText("医保智能审计平台")).toBeVisible();
  await expect(page.getByText("2025 年 Q4 住院部专项审计")).toBeVisible();
  await expect(page.getByRole("heading", { name: "审计口径" })).toBeVisible();
  await expect(page.getByRole("link", { name: "进入专题工作台" })).toHaveAttribute(
    "href",
    "/fund-compliance/review"
  );

  await page.getByRole("link", { name: "进入专题工作台" }).click();
  await expect(page).toHaveURL(/\/fund-compliance\/review$/);
  await expect(page.getByRole("heading", { name: "专题审计工作台" })).toBeVisible();
  await page.getByRole("tab", { name: "费用表单" }).click();
  await expect(page.getByRole("heading", { name: "三份模板与自建表单" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "表1" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByText("表1_医保费用汇总表（空白）.xlsx / 汇总表")).toBeVisible();
  await expect(page.getByText("表样预览")).toBeVisible();
  await page.getByRole("tab", { name: "表2" }).click();
  await expect(page.getByRole("tab", { name: "表2" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByText("表2_医保费用分类汇总表（空白）.xlsx / 汇总表")).toBeVisible();
  await page.getByRole("tab", { name: "表3" }).click();
  await expect(page.getByRole("tab", { name: "表3" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByText("表3_就诊费用明细表（空白）.xlsx / 明细表")).toBeVisible();
  await page.getByText("新建表单").click();
  await expect(page.getByLabel("表单名称")).toBeVisible();
});

test("Next-native audit chat portal is reachable", async ({ page }) => {
  await page.goto("/chat");

  await expect(page.getByRole("heading", { name: "审计问答" })).toBeVisible();
  await expect(page.getByRole("button", { name: "进入对话" })).toBeVisible();
  await expect(page.getByRole("link", { name: "先检索文档" })).toHaveAttribute("href", "/documents");
});

test("Next-native query workbench is reachable", async ({ page }) => {
  await page.goto("/knowledge-query");

  await expect(page.getByRole("heading", { name: "引用优先的知识查询" })).toBeVisible();
  await expect(page.getByLabel("审计问题")).toBeVisible();
  await expect(page.getByRole("button", { name: "执行查询" })).toBeVisible();
  await expect(page.getByRole("link", { name: "回到文档依据" })).toHaveAttribute("href", "/documents");
});

test("Next-native findings workbench is reachable", async ({ page }) => {
  await mockFindingsWorkbench(page);
  await page.goto("/findings");

  await expect(page.getByRole("heading", { name: "规则命中疑点工作台" })).toBeVisible();
  await expect(page.getByLabel("复核状态")).toBeVisible();
  await expect(page.getByRole("heading", { name: "疑点生成链路未就绪" })).toBeVisible();
  await expect(page.getByText("疑点 store 未初始化，无法读取规则生成链路状态。")).toBeVisible();
});

test("AI data analysis accepts CSV uploads and shows audit hints", async ({ page }) => {
  await mockAnalyticsWorkbench(page);
  await page.goto("/analytics");

  await page.getByLabel("上传审计表格").setInputFiles({
    name: "charge-sample.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(
      [
        "patient_id,visit_date,item_code,charge_amount,insurance_pay",
        "P001,2026-01-01,A100,120.00,80.00",
        "P001,2026-01-01,A100,120.00,80.00",
        "P002,2026-01-02,B200,,50.00"
      ].join("\n")
    )
  });

  await expect(page.getByRole("heading", { name: "charge-sample.csv" })).toBeVisible();
  await expect(page.getByText("数据质量提示")).toBeVisible();
  await expect(page.getByText("审计初步分析")).toBeVisible();
  await expect(page.getByText("金额/费用字段").first()).toBeVisible();
  await expect(page.getByText("发现 1 条完全重复行。")).toBeVisible();
});

test("project management exposes project list and member workflow", async ({ page }) => {
  await mockProjectWorkbench(page);
  await page.goto("/projects");

  await expect(page.getByRole("heading", { name: "项目与成员" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "项目列表" })).toBeVisible();
  await expect(page.getByText("项目名称")).toBeVisible();
  await expect(page.getByText("成员数")).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "创建人" })).toBeVisible();
  await expect(page.getByText("创建时间")).toBeVisible();
  await expect(page.getByRole("row").filter({ hasText: "医保目录限制条件核验" }).first()).toBeVisible();

  await page.getByRole("button", { name: "查看成员" }).click();
  await expect(page.getByRole("heading", { name: "医保目录限制条件核验" })).toBeVisible();

  await page.getByLabel("姓名").fill("赵审计");
  await page.getByLabel("部门").fill("医保办");
  await page.getByRole("button", { name: "添加成员" }).click();

  const createdMemberRow = page.getByRole("row").filter({ hasText: "赵审计" }).last();
  await expect(createdMemberRow).toBeVisible();
  await expect(createdMemberRow.getByRole("cell", { name: "医保办" })).toBeVisible();
});

test("agent marketplace filters templates and agents enter portal chat", async ({ page }) => {
  await page.goto("/agent-market");

  await expect(page.getByRole("heading", { name: "审计助手库" })).toBeVisible();
  await expect(page.getByRole("tab", { name: /^全部132$/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /出国差旅核验/ }).first()).toBeVisible();

  await page.getByRole("tab", { name: /^工具智能体10$/ }).click();
  await expect(page.getByRole("button", { name: /质量检查核验/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /出国差旅核验/ })).toHaveCount(0);

  await page.getByRole("tab", { name: /^全部132$/ }).click();
  await page.getByLabel("搜索审计助手").fill("合同要素");
  await expect(page.getByRole("button", { name: /合同风险核验/ }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: /会议费用核验/ })).toHaveCount(0);

  await page.getByRole("button", { name: /合同风险核验/ }).first().click();
  await expect(page.getByRole("dialog", { name: "合同风险核验" })).toBeVisible();
  await expect(page.getByRole("link", { name: "用此助手提问" })).toHaveAttribute("href", /\/chat\?agent=/);

  await page.goto("/agents");
  await expect(page.locator("main").getByText("医保基金使用合规专项自查").first()).toBeVisible();
  await expect(page.getByRole("link", { name: "进入对话" }).first()).toHaveAttribute(
    "href",
    "/chat?agent=agent-citation-check"
  );
});

test("knowledge base page exposes read-only asset metrics", async ({ page }) => {
  await page.goto("/knowledge-base");

  await expect(page.getByRole("heading", { name: "知识库总览" })).toBeVisible();
  await expect(page.getByText("个人知识库").first()).toBeVisible();
  await expect(page.getByText("系统知识库").first()).toBeVisible();
  await expect(page.getByText("公开知识库").first()).toBeVisible();
  await expect(page.getByText("文档数").first()).toBeVisible();
  await expect(page.getByText("字符数").first()).toBeVisible();
  await expect(page.getByText("应用数").first()).toBeVisible();
  await expect(page.getByText("法规政策、医保目录、监管规则和风险负面清单组成的系统检索底座。").first()).toBeVisible();
});

test("document search homepage exposes history and document groups", async ({ page }) => {
  await mockDocumentWorkbench(page);
  await page.goto("/documents");

  await expect(page.getByRole("heading", { name: "文档依据检索" })).toBeVisible();
  await expect(page.getByLabel("审计问题或文档关键词")).toBeVisible();
  await expect(page.getByLabel("仅标题")).toBeVisible();
  await expect(page.getByRole("heading", { name: "搜索历史" })).toBeVisible();
  await expect(page.getByText("监管两库")).toBeVisible();
  await expect(page.getByText("风险清单")).toBeVisible();
  await page.getByLabel("审计问题或文档关键词").fill("医保基金审核依据是什么");
  await page.getByRole("button", { name: "执行检索" }).click();
  await expect(page.getByRole("heading", { name: "医保基金审核依据是什么" })).toBeVisible();
  await expect(page.getByText("1 条引用").first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "对话文档" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "知识库文档" })).toBeVisible();
  await expect(page.getByText("重复收费疑点复核对话")).toBeVisible();
  await expect(page.getByText("医保目录限制条件资料包")).toBeVisible();
  await expect(page.getByRole("link", { name: "转入对话" }).first()).toHaveAttribute("href", /\/chat/);
});

test("knowledge graph exposes read-only relationship coverage", async ({ page }) => {
  await page.goto("/graph");

  await expect(page.getByRole("heading", { name: "知识图谱入口" })).toBeVisible();
  await expect(page.getByRole("img", { name: "审计知识图谱静态关系预览" })).toBeVisible();
  await expect(page.getByText("医保基金使用合规专项图谱")).toBeVisible();
  await expect(page.getByText("节点覆盖")).toBeVisible();
  await expect(page.getByText("节点证据")).toBeVisible();
  const nodeCoverage = page.locator("section", { has: page.getByRole("heading", { name: "节点覆盖" }) });
  await expect(nodeCoverage.getByText("项目", { exact: true })).toBeVisible();
  await expect(nodeCoverage.getByText("知识库", { exact: true })).toBeVisible();
  await expect(nodeCoverage.getByText("文档", { exact: true })).toBeVisible();
  await expect(nodeCoverage.getByText("规则", { exact: true })).toBeVisible();
  await expect(nodeCoverage.getByText("疑点", { exact: true })).toBeVisible();
  await expect(nodeCoverage.getByText("复核", { exact: true })).toBeVisible();
  await expect(nodeCoverage.getByText("报告", { exact: true })).toBeVisible();
  await expect(nodeCoverage.getByText("整改", { exact: true })).toBeVisible();
  await expect(page.getByText("FINDING-F044EBD309B659DC").first()).toBeVisible();
  await expect(page.getByText("review-task-0007").first()).toBeVisible();
});

test("rules homepage exposes sources, runs and release gates", async ({ page }) => {
  await page.goto("/rules");

  await expect(page.getByRole("heading", { name: "审计规则与依据总览" })).toBeVisible();
  await expect(page.getByText("可运行规则")).toBeVisible();
  await expect(page.getByText("待处理规则")).toBeVisible();
  await expect(page.getByRole("heading", { name: "规则清单" })).toBeVisible();
  await expect(page.getByText("CHARGE-RULE-001").first()).toBeVisible();
  await expect(page.getByText("CATALOG-RULE-014").first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "最近运行" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "来源覆盖" })).toBeVisible();
  await expect(page.getByText("监管两库").first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "发布门禁" })).toBeVisible();
  await expect(page.getByText("字段可运行")).toBeVisible();
  await expect(page.getByRole("link", { name: "查看依据库" })).toHaveAttribute("href", "/knowledge-base");
  await expect(
    page.locator("article").filter({ hasText: "CHARGE-RULE-001" }).getByRole("link", { name: "查看", exact: true })
  ).toHaveAttribute("href", "/findings?rule=CHARGE-RULE-001");
});

test("report homepage exposes gates, evidence and remediation", async ({ page }) => {
  await page.goto("/reports");

  await expect(page.getByRole("heading", { name: "底稿与报告" })).toBeVisible();
  await expect(page.getByText("已签发报告")).toBeVisible();
  await expect(page.getByText("门禁阻断").first()).toBeVisible();
  await expect(page.getByText("纳入疑点").first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "报告记录" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "报告门禁预检" }).first()).toBeVisible();
  await expect(page.getByText("表1 医保费用汇总表").first()).toBeVisible();
  await expect(page.getByText("费用汇总风险底稿")).toBeVisible();
  await expect(page.getByText("底稿与负责人确认")).toBeVisible();
  await expect(page.getByText("附件登记与报告草稿")).toBeVisible();
  await expect(page.getByRole("heading", { name: "底稿证据来源" })).toBeVisible();
  await expect(page.getByText("workpaper-20260604-001")).toBeVisible();
  await expect(page.getByRole("heading", { name: "整改跟踪" })).toBeVisible();
  await expect(page.getByText("重复收费退费与流程复核")).toBeVisible();
  await expect(page.getByText("AUDIT-REPORT-20260611-001").first()).toBeVisible();
  await expect(page.getByRole("link", { name: "查看证据链" }).first()).toHaveAttribute("href", "/graph#graph-node-report");
});

test("remediation homepage exposes evidence requests and closure gates", async ({ page }) => {
  await page.goto("/remediation");

  await expect(page.getByRole("heading", { name: "整改事项与补证闭环" })).toBeVisible();
  await expect(page.getByText("未关闭事项", { exact: true })).toBeVisible();
  await expect(page.getByText("待补证材料", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "整改台账" })).toBeVisible();
  await expect(page.getByText("重复收费退费与流程复核").first()).toBeVisible();
  await expect(page.getByText("FINDING-F044EBD309B659DC").first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "补证请求" })).toBeVisible();
  await expect(page.getByText("重复收费退费凭证")).toBeVisible();
  await expect(page.getByText("目录限制 HIS 字段截图")).toBeVisible();
  await expect(page.getByRole("heading", { name: "关闭门禁" })).toBeVisible();
  await expect(page.getByText("补证材料完整")).toBeVisible();
  await expect(page.getByRole("heading", { name: "整改动态" })).toBeVisible();
  await expect(page.getByText("附件归档校验阻断")).toBeVisible();
  await expect(page.getByRole("link", { name: "查看报告来源" })).toHaveAttribute("href", "/reports");
  await expect(page.getByRole("link", { name: "查看证据链" }).first()).toHaveAttribute("href", "/graph#graph-node-remediation");
});

test("archive homepage exposes packages, audit runs and signature chain", async ({ page }) => {
  await page.goto("/archive");

  await expect(page.getByRole("heading", { name: "项目档案与审计日志归档" })).toBeVisible();
  await expect(page.getByText("已归档项目", { exact: true })).toBeVisible();
  await expect(page.getByText("待归档档案", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "项目档案包" })).toBeVisible();
  await expect(
    page
      .locator("section", { has: page.getByRole("heading", { name: "项目档案包" }) })
      .getByText("医保基金使用合规专项自查")
      .first()
  ).toBeVisible();
  await expect(page.getByText("ARCHIVE-SELF-CHECK-FUND-202606").first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "审计日志治理策略" })).toBeVisible();
  await expect(page.getByText("180 days")).toBeVisible();
  await expect(page.getByRole("heading", { name: "归档巡检", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "archive root 巡检", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "签名链" })).toBeVisible();
  await expect(page.getByText("retention-batch-0001.jsonl")).toBeVisible();
  await expect(page.getByRole("heading", { name: "入档动态" })).toBeVisible();
  await expect(page.getByText("附件 hash 阻断归档")).toBeVisible();
  await expect(page.getByRole("link", { name: "查看归档策略" })).toHaveAttribute("href", "#archive-policy-title");
  await expect(page.getByRole("link", { name: "查看档案" }).first()).toHaveAttribute("href", "/reports");
  await expect(page.getByRole("link", { name: "查看留痕" }).first()).toHaveAttribute(
    "href",
    "#archive-policy-title"
  );
});

test("guided check homepage exposes steps, prompts and evidence gates", async ({ page }) => {
  await page.goto("/guided-check");

  await expect(page.getByRole("heading", { name: "AI 引导自查工作台" })).toBeVisible();
  await expect(page.getByText("已完成步骤")).toBeVisible();
  await expect(page.getByText("可提问模板")).toBeVisible();
  await expect(page.getByRole("heading", { name: "自查路径" })).toBeVisible();
  await expect(page.getByText("锁定自查范围")).toBeVisible();
  await expect(page.getByText("上传并识别数据")).toBeVisible();
  await expect(page.getByRole("heading", { name: "AI 提问模板" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "重复收费复核助手" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "证据门禁" })).toBeVisible();
  await expect(page.getByText("目录限制 HIS 字段截图", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "风险预检" })).toBeVisible();
  await expect(page.getByText("重复收费线索")).toBeVisible();
  await expect(page.getByRole("heading", { name: "自查动态" })).toBeVisible();
  await expect(page.getByRole("link", { name: "进入 AI 审证对话", exact: true })).toHaveAttribute("href", "/chat");
  await expect(page.getByRole("link", { name: "进入对话" }).first()).toHaveAttribute(
    "href",
    /\/chat\?agent=agent-duplicate-charge/
  );
});

test("portal routes render without placeholders or mobile page overflow", async ({ page }) => {
  test.setTimeout(60_000);
  await page.setViewportSize({ width: 390, height: 1000 });

  for (const route of portalAuditRoutes) {
    await page.goto(route);

    await expect(page.locator("h1"), `${route} h1 count`).toHaveCount(1);

    const audit = await page.evaluate(() => ({
      clientWidth: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
      bodyScrollWidth: document.body.scrollWidth,
      bodyText: document.body.textContent ?? ""
    }));

    expect(audit.scrollWidth, `${route} document overflow`).toBeLessThanOrEqual(audit.clientWidth);
    expect(audit.bodyScrollWidth, `${route} body overflow`).toBeLessThanOrEqual(audit.clientWidth);
    expect(audit.bodyText, `${route} placeholder text`).not.toMatch(
      /BackendFeatureBridge|Plan \d+|Coming soon|敬请期待|占位/
    );
  }
});
