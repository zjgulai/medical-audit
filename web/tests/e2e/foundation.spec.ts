import { expect, test, type Page } from "@playwright/test";

const portalAuditRoutes = [
  "/",
  "/workspace",
  "/fund-compliance",
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
  const chatLink = primaryNavigation.getByRole("link", { name: /AI 对话/ });
  const topicLink = page.getByRole("link", { name: /打开当前审计专题/ });

  await expect(page.getByText("AI智能审计管理系统")).toBeVisible();
  await expect(page.getByTestId("auditscope-brand-logo")).toBeVisible();
  await expect(topicLink).toHaveAttribute("href", "/fund-compliance");
  const topicBox = await topicLink.boundingBox();
  const navigationBox = await primaryNavigation.boundingBox();

  expect(topicBox).not.toBeNull();
  expect(navigationBox).not.toBeNull();
  if (topicBox && navigationBox) {
    expect(navigationBox.y - (topicBox.y + topicBox.height)).toBeLessThanOrEqual(32);
  }

  await expect(page.getByRole("heading", { name: "材料与知识库统一检索" })).toBeVisible();
  await expect(chatLink).toBeVisible();
  await expect(chatLink).toHaveAttribute("href", "/chat");
  await expect(primaryNavigation.getByRole("link", { name: /我的智能体/ })).toHaveAttribute("href", "/agents");
  await expect(primaryNavigation.getByRole("link", { name: /智能体广场/ })).toHaveAttribute("href", "/agent-market");
  await expect(primaryNavigation.getByRole("link", { name: /^知识库/ })).toHaveAttribute("href", "/knowledge-base");
  await expect(primaryNavigation.getByRole("link", { name: /文档检索/ })).toHaveAttribute("href", "/documents");
  await expect(primaryNavigation.getByRole("link", { name: /AI 数据分析/ })).toHaveAttribute("href", "/analytics");
  await expect(primaryNavigation.getByRole("link", { name: /知识图谱/ })).toHaveAttribute("href", "/graph");
  await expect(primaryNavigation.getByRole("link", { name: "审计底稿生成" })).toHaveAttribute("href", "/reports");
  await expect(primaryNavigation.getByRole("link", { name: /项目管理/ })).toHaveAttribute("href", "/projects");
  await expectNoBrokenImages(page);
});

test("Next-native AI chat portal is reachable", async ({ page }) => {
  await page.goto("/chat");

  await expect(page.getByRole("heading", { name: "AI 审证对话工作台" })).toBeVisible();
  await expect(page.getByRole("button", { name: "进入审证对话" })).toBeVisible();
  await expect(page.getByRole("link", { name: "打开后端深页" })).toHaveAttribute("href", "/pages/chat");
});

test("Next-native query workbench is reachable", async ({ page }) => {
  await page.goto("/knowledge-query");

  await expect(page.getByRole("heading", { name: "引用优先的知识查询" })).toBeVisible();
  await expect(page.getByLabel("审计问题")).toBeVisible();
  await expect(page.getByRole("button", { name: "执行查询" })).toBeVisible();
  await expect(page.getByRole("link", { name: "打开后端兼容页" })).toHaveAttribute("href", "/pages/query");
});

test("Next-native findings workbench is reachable", async ({ page }) => {
  await page.goto("/findings");

  await expect(page.getByRole("heading", { name: "规则命中疑点工作台" })).toBeVisible();
  await expect(page.getByLabel("复核状态")).toBeVisible();
  await expect(page.getByRole("heading", { name: "疑点生成链路未就绪" })).toBeVisible();
  await expect(page.getByText("疑点 store 未初始化，无法读取规则生成链路状态。")).toBeVisible();
});

test("AI data analysis accepts CSV uploads and shows audit hints", async ({ page }) => {
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
  await expect(page.getByText("金额/费用字段")).toBeVisible();
  await expect(page.getByText("发现 1 条完全重复行。")).toBeVisible();
});

test("project management exposes project list and member workflow", async ({ page }) => {
  await page.goto("/projects");

  await expect(page.getByRole("heading", { name: "审计项目管理" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "项目列表" })).toBeVisible();
  await expect(page.getByText("项目名称")).toBeVisible();
  await expect(page.getByText("成员数")).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "创建人" })).toBeVisible();
  await expect(page.getByText("创建时间")).toBeVisible();
  await expect(page.getByText("医保目录限制条件核验")).toBeVisible();

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

  await expect(page.getByRole("heading", { name: "审计提示词智能体" })).toBeVisible();
  await expect(page.getByRole("tab", { name: /^全部132$/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /出国团组助手/ })).toBeVisible();

  await page.getByRole("tab", { name: /^工具智能体10$/ }).click();
  await expect(page.getByRole("button", { name: /质量检查助手/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /出国团组助手/ })).toHaveCount(0);

  await page.getByRole("tab", { name: /^全部132$/ }).click();
  await page.getByLabel("搜索智能体").fill("合同要素");
  await expect(page.getByRole("button", { name: /合同要素提取/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /会议费审计/ })).toHaveCount(0);

  await page.getByRole("button", { name: /合同要素提取/ }).click();
  await expect(page.getByRole("dialog", { name: "合同要素提取" })).toBeVisible();
  await expect(page.getByRole("link", { name: "用此智能体对话" })).toHaveAttribute("href", /\/chat\?agent=/);

  await page.goto("/agents");
  await expect(page.getByText("医保基金使用合规专项自查").first()).toBeVisible();
  await expect(page.getByRole("link", { name: "进入对话" }).first()).toHaveAttribute(
    "href",
    "/chat?agent=agent-citation-check"
  );
});

test("knowledge base page exposes read-only asset metrics", async ({ page }) => {
  await page.goto("/knowledge-base");

  await expect(page.getByRole("heading", { name: "个人、系统、公开知识库" })).toBeVisible();
  await expect(page.getByText("个人知识库").first()).toBeVisible();
  await expect(page.getByText("系统知识库").first()).toBeVisible();
  await expect(page.getByText("公开知识库").first()).toBeVisible();
  await expect(page.getByText("文档数").first()).toBeVisible();
  await expect(page.getByText("字符数").first()).toBeVisible();
  await expect(page.getByText("关联应用数").first()).toBeVisible();
  await expect(page.getByText("法规政策、医保目录、监管规则和风险负面清单组成的系统检索底座。").first()).toBeVisible();
});

test("document search homepage exposes history and document groups", async ({ page }) => {
  await page.goto("/documents");

  await expect(page.getByRole("heading", { name: "材料与知识库统一检索" })).toBeVisible();
  await expect(page.getByLabel("审计问题或文档关键词")).toBeVisible();
  await expect(page.getByLabel("仅标题")).toBeVisible();
  await expect(page.getByRole("heading", { name: "搜索历史" })).toBeVisible();
  await expect(page.getByText("监管两库")).toBeVisible();
  await expect(page.getByText("risk-negative-list")).toBeVisible();
  await page.getByLabel("审计问题或文档关键词").fill("医保基金审核依据是什么");
  await page.getByRole("button", { name: "执行检索" }).click();
  await expect(page.getByRole("heading", { name: "医保基金审核依据是什么" })).toBeVisible();
  await expect(page.getByText("1 条引用").first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "对话文档" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "知识库文档" })).toBeVisible();
  await expect(page.getByText("重复收费疑点复核对话")).toBeVisible();
  await expect(page.getByText("医保目录限制条件资料包")).toBeVisible();
  await expect(page.getByRole("link", { name: "转入 AI 对话" }).first()).toHaveAttribute("href", /\/chat/);
});

test("knowledge graph exposes read-only relationship coverage", async ({ page }) => {
  await page.goto("/graph");

  await expect(page.getByRole("heading", { name: "知识图谱入口" })).toBeVisible();
  await expect(page.getByRole("img", { name: "审计知识图谱静态关系预览" })).toBeVisible();
  await expect(page.getByText("医保基金使用合规专项图谱")).toBeVisible();
  await expect(page.getByText("节点覆盖")).toBeVisible();
  await expect(page.getByText("节点证据")).toBeVisible();
  await expect(page.getByText("项目").first()).toBeVisible();
  await expect(page.getByText("知识库").first()).toBeVisible();
  await expect(page.getByText("文档").first()).toBeVisible();
  await expect(page.getByText("规则").first()).toBeVisible();
  await expect(page.getByText("疑点").first()).toBeVisible();
  await expect(page.getByText("复核").first()).toBeVisible();
  await expect(page.getByText("报告").first()).toBeVisible();
  await expect(page.getByText("整改").first()).toBeVisible();
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
  await expect(page.getByRole("link", { name: "打开索引管理" })).toHaveAttribute("href", "/pages/index-admin");
  await expect(
    page.locator("article").filter({ hasText: "CHARGE-RULE-001" }).getByRole("link", { name: "查看", exact: true })
  ).toHaveAttribute("href", "/findings?rule=CHARGE-RULE-001");
});

test("report homepage exposes gates, evidence and remediation", async ({ page }) => {
  await page.goto("/reports");

  await expect(page.getByRole("heading", { name: "底稿生成与报告记录" })).toBeVisible();
  await expect(page.getByText("已签发报告")).toBeVisible();
  await expect(page.getByText("门禁阻断").first()).toBeVisible();
  await expect(page.getByText("纳入疑点").first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "历史生成记录" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "报告门禁预检" }).first()).toBeVisible();
  await expect(page.getByText("表1_医保费用汇总表（空白）.xlsx")).toBeVisible();
  await expect(page.getByText("模板字段已注册").first()).toBeVisible();
  await expect(page.getByText("底稿与负责人确认")).toBeVisible();
  await expect(page.getByText("附件登记与报告草稿")).toBeVisible();
  await expect(page.getByRole("heading", { name: "底稿证据来源" })).toBeVisible();
  await expect(page.getByText("workpaper-20260604-001")).toBeVisible();
  await expect(page.getByRole("heading", { name: "整改跟踪" })).toBeVisible();
  await expect(page.getByText("重复收费退费与流程复核")).toBeVisible();
  await expect(page.getByText("AUDIT-REPORT-20260611-001").first()).toBeVisible();
  await expect(page.getByRole("link", { name: "查看详情" }).first()).toHaveAttribute("href", "/pages/review-tasks");
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
  await expect(page.getByRole("link", { name: "查看详情" }).first()).toHaveAttribute("href", "/pages/review-tasks");
});

test("archive homepage exposes packages, audit runs and signature chain", async ({ page }) => {
  await page.goto("/archive");

  await expect(page.getByRole("heading", { name: "项目档案与审计日志归档" })).toBeVisible();
  await expect(page.getByText("已归档项目", { exact: true })).toBeVisible();
  await expect(page.getByText("待归档档案", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "项目档案包" })).toBeVisible();
  await expect(page.getByText("医保基金使用合规专项自查").first()).toBeVisible();
  await expect(page.getByText("ARCHIVE-SELF-CHECK-FUND-202606").first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "审计日志治理策略" })).toBeVisible();
  await expect(page.getByText("180 days")).toBeVisible();
  await expect(page.getByRole("heading", { name: "归档巡检", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "archive root 巡检", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "签名链" })).toBeVisible();
  await expect(page.getByText("retention-batch-0001.jsonl")).toBeVisible();
  await expect(page.getByRole("heading", { name: "入档动态" })).toBeVisible();
  await expect(page.getByText("附件 hash 阻断归档")).toBeVisible();
  await expect(page.getByRole("link", { name: "打开审计日志台" })).toHaveAttribute("href", "/pages/audit-logs");
  await expect(page.getByRole("link", { name: "查看档案" }).first()).toHaveAttribute("href", "/reports");
  await expect(page.getByRole("link", { name: "查看日志" }).first()).toHaveAttribute(
    "href",
    "/pages/audit-logs?entity_type=review-task&entity_id=review-task-0001"
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
