import { expect, test } from "@playwright/test";

test.describe("local fullstack acceptance for restored replica product", () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem("medical-audit-authenticated", "authenticated");
      window.localStorage.setItem("medical-audit-current-role", "admin");
    });
  });

  test("chat reaches local models, knowledge sources, agents, attachment analysis and query APIs", async ({ page }) => {
    await page.goto("/chat");

    await expect(page.getByRole("heading", { name: "AI，让审计更智能" })).toBeVisible();
    await page.getByRole("combobox", { name: "选择模型" }).selectOption("deepseek-v4-pro");

    await page.getByRole("button", { name: /全部知识库/ }).click();
    await expect(page.getByRole("dialog", { name: "选择知识库" })).toBeVisible();
    await page.getByLabel(/法规政策/).check();

    const questionInput = page.getByLabel("输入相关问题以对话");
    await questionInput.fill("@");
    await expect(page.getByRole("dialog", { name: "选择智能体" })).toBeVisible();
    await page.getByRole("button", { name: /引用依据核验助手/ }).click();

    const attachmentRequestPromise = page.waitForRequest(
      (request) => request.url().includes("/api/v1/chat/attachments/analyze") && request.method() === "POST"
    );
    await page.locator('input[type="file"]').setInputFiles({
      name: "charges.csv",
      mimeType: "text/csv",
      buffer: Buffer.from("patient_id,charge_amount\nP001,120\nP002,80\n")
    });
    await attachmentRequestPromise;
    await expect(page.getByText(/模型：deepseek-v4-pro/)).toBeVisible();
    await expect(page.getByText(/本地验收模型回答/).first()).toBeVisible();

    const queryRequestPromise = page.waitForRequest(
      (request) => request.url().includes("/api/v1/query") && request.method() === "POST"
    );
    await questionInput.fill("医保基金审核依据是什么？");
    await page.getByRole("button", { name: "发送问题" }).click();
    const queryRequest = await queryRequestPromise;

    expect(queryRequest.postDataJSON()).toMatchObject({
      question: "医保基金审核依据是什么？",
      model: "deepseek-v4-pro",
      source_collections: ["medical-insurance-laws"],
      agent: "agent-citation-check"
    });
    await expect(page.getByText(/智能体调用已记录/)).toBeVisible();
    await expect(page.getByText(/本地验收模型回答/).last()).toBeVisible();
  });

  test("documents reaches local source catalog and query API", async ({ page }) => {
    await page.goto("/documents");

    await expect(page.getByRole("heading", { name: "文档检索" })).toBeVisible();
    await expect(page.getByText("法律法规库").first()).toBeVisible();

    const queryRequestPromise = page.waitForRequest(
      (request) => request.url().includes("/api/v1/query") && request.method() === "POST"
    );
    await page.getByLabel("检索关键词").fill("医保基金审核依据是什么？");
    await page.getByRole("button", { name: "搜索", exact: true }).click();
    await queryRequestPromise;

    await expect(page.getByText("1 条匹配").first()).toBeVisible();
    await expect(page.getByText("medical-insurance-laws").first()).toBeVisible();
  });

  test("agent directories expose mine and market pages with local backend data", async ({ page }) => {
    await page.goto("/agents");
    await expect(page.getByRole("heading", { name: "我的助手" })).toBeVisible();
    await expect(page.getByText("引用依据核验助手").first()).toBeVisible();
    await page.getByRole("button", { name: "查看详情" }).first().click();
    await expect(page.getByLabel("我的智能体详情")).toBeVisible();

    await page.goto("/agent-market");
    await expect(page.getByRole("heading", { name: "发现审计智能体" })).toBeVisible();
    await expect(page.getByText("广场助手")).toBeVisible();
    await expect(page.getByRole("button", { name: "查看详情" }).first()).toBeVisible();
  });

  test("analytics, graph, reports, projects and medical audit remain interactive", async ({ page }) => {
    await page.goto("/analytics");
    await expect(page.getByRole("heading", { name: "AI数据分析" })).toBeVisible();
    await page.locator('input[type="file"]').setInputFiles({
      name: "charge-sample.csv",
      mimeType: "text/csv",
      buffer: Buffer.from("patient_id,charge_amount\nP001,120\n")
    });
    await expect(page.getByText("charge-sample.csv", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "开始分析" }).click();
    await expect(page.getByText(/结果预览已生成预览/)).toBeVisible();

    await page.goto("/graph");
    await expect(page.getByRole("heading", { name: "知识图谱" })).toBeVisible();
    await page.getByRole("button", { name: /乡村振兴专项审计图谱/ }).click();
    await expect(page.getByLabel("图谱详情预览")).toBeVisible();
    await page.getByRole("button", { name: "关闭图谱详情" }).click();

    await page.goto("/reports");
    await expect(page.getByRole("heading", { name: "底稿与报告" })).toBeVisible();
    await page.getByRole("button", { name: "查看底稿" }).first().click();
    await expect(page.getByLabel("报告详情预览")).toBeVisible();
    await page.getByRole("button", { name: "关闭报告详情" }).click();

    await page.goto("/projects");
    await expect(page.getByRole("heading", { name: "项目管理" })).toBeVisible();
    await expect(page.getByLabel("审计驾驶舱")).toBeVisible();
    await expect(page.getByText("总审计条数")).toBeVisible();

    await page.goto("/medical-audit");
    await expect(page.getByRole("heading", { name: "医保审计" })).toBeVisible();
    await page.getByRole("tab", { name: "费用汇总表" }).click();
    await expect(page.getByLabel("医保费用汇总表")).toBeVisible();
  });

  test("compatibility routes land on the restored replica shell", async ({ page }) => {
    const redirects = [
      { from: "/workspace", to: /\/chat$/ },
      { from: "/knowledge-query", to: /\/documents$/ },
      { from: "/fund-compliance", to: /\/medical-audit$/ },
      { from: "/findings", to: /\/medical-audit$/ },
      { from: "/archive", to: /\/reports$/ }
    ] as const;

    for (const redirect of redirects) {
      await page.goto(redirect.from);
      await expect(page).toHaveURL(redirect.to);
      await expect(page.getByRole("link", { name: "医疗AI审计平台" })).toBeVisible();
    }
  });
});
