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

  test("documents reaches local source catalog and document search API", async ({ page }) => {
    await page.goto("/documents");

    await expect(page.getByRole("heading", { name: "文档检索" })).toBeVisible();
    await expect(page.getByText("法规政策").first()).toBeVisible();

    const searchRequestPromise = page.waitForRequest(
      (request) => request.url().includes("/api/v1/documents/search") && request.method() === "GET"
    );
    await page.getByLabel("检索关键词").fill("医保基金审核依据是什么？");
    await page.getByRole("button", { name: "搜索", exact: true }).click();
    await searchRequestPromise;

    await expect(page.getByText("1 条匹配").first()).toBeVisible();
    await expect(page.getByText("medical-insurance-laws").first()).toBeVisible();
  });

  test("agent directories expose mine and market pages with local backend data", async ({ page }) => {
    await page.goto("/agents");
    await expect(page.getByRole("heading", { name: "我的智能体" })).toBeVisible();
    await expect(page.getByText("引用依据核验助手").first()).toBeVisible();
    await page.getByRole("button", { name: "查看详情" }).first().click();
    await expect(page.getByLabel("我的智能体详情")).toBeVisible();

    await page.goto("/agent-market");
    await expect(page.getByRole("heading", { name: "智能体广场" })).toBeVisible();
    await expect(page.getByRole("button", { name: /详情/ }).first()).toBeVisible();
  });

  test("analytics workbench, preview modules and medical audit remain interactive", async ({ page }) => {
    await page.goto("/analytics");
    await expect(page.getByRole("heading", { name: "表格分析工作台", exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "上传表格", exact: true })).toBeVisible();
    await expect(page.getByText("provider_call=false", { exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "分析历史", exact: true })).toBeVisible();

    await page.goto("/graph");
    await expect(page.getByRole("heading", { name: "知识依据与项目证据链", exact: true })).toBeVisible();
    await expect(page.getByLabel("知识依据图谱工作台")).toBeVisible();
    await expect(page.getByRole("tab", { name: "知识依据" })).toHaveAttribute("aria-selected", "true");

    const reportWorkbenchResponsePromise = page.waitForResponse(
      (response) => response.url().includes("/api/v1/reports/workbench") && response.request().method() === "GET"
    );
    await page.goto("/reports");
    const reportWorkbenchResponse = await reportWorkbenchResponsePromise;
    expect(reportWorkbenchResponse.status()).toBe(200);
    expect(await reportWorkbenchResponse.json()).toMatchObject({
      store: { ready: true, backend: "InMemoryReviewTaskStore" }
    });
    await expect(page.getByRole("heading", { name: "审计底稿与报告台账", exact: true })).toBeVisible();
    await expect(page.getByRole("region", { name: "报表分类目录" })).toBeVisible();

    await page.goto("/projects");
    await expect(page.getByRole("heading", { name: "项目协作工作台", exact: true })).toBeVisible();
    await expect(page.getByRole("combobox", { name: "项目状态" })).toBeVisible();

    await page.goto("/medical-audit");
    await expect(page.getByRole("heading", { name: "医保审计", exact: true })).toBeVisible();
    await page.getByRole("tab", { name: "费用汇总表" }).click();
    await expect(page.getByLabel("医保费用汇总表")).toBeVisible();
  });

  test("compatibility routes land on the restored replica shell", async ({ page }) => {
    const redirects = [
      { from: "/workspace", to: /\/chat$/ },
      { from: "/findings", to: /\/medical-audit$/ }
    ] as const;

    for (const redirect of redirects) {
      await page.goto(redirect.from);
      await expect(page).toHaveURL(redirect.to);
      await expect(page.getByRole("link", { name: "AI审计一体化协作平台" })).toBeVisible();
    }

    await page.goto(
      "/knowledge-query?query=%E5%8C%BB%E4%BF%9D%E6%94%AF%E4%BB%98&source_collection=medical-insurance-laws&unknown=discard&source_collection=personal-materials"
    );
    await expect(page).toHaveURL(
      (url) =>
        url.pathname === "/documents" &&
        url.search ===
          "?query=%E5%8C%BB%E4%BF%9D%E6%94%AF%E4%BB%98&source_collection=medical-insurance-laws&source_collection=personal-materials"
    );
    await expect(page.getByRole("link", { name: "AI审计一体化协作平台" })).toBeVisible();

    const compatibilityPages = [
      { route: "/fund-compliance", heading: "医保基金使用合规", marker: "医保审计" },
      { route: "/fund-compliance/review", heading: "医保基金复核表单", marker: "费用汇总表" },
      { route: "/rules", heading: "规则运行工作台", marker: "规则法规库" },
      { route: "/archive", heading: "归档工作台", marker: "归档包" },
      { route: "/guided-check", heading: "引导式核查", marker: "核查步骤" },
      { route: "/remediation", heading: "整改工作台", marker: "整改事项、补证请求、关闭门禁" }
    ] as const;

    for (const compatibilityPage of compatibilityPages) {
      await page.goto(compatibilityPage.route);
      await expect(page).toHaveURL(new RegExp(`${compatibilityPage.route.replace(/\//g, "\\/")}$`));
      await expect(page.getByRole("heading", { name: compatibilityPage.heading })).toBeVisible();
      await expect(page.getByText(compatibilityPage.marker).first()).toBeVisible();
      await expect(page.getByRole("link", { name: "AI审计一体化协作平台" })).toBeVisible();
      await expect(page.getByRole("banner").getByText(compatibilityPage.heading, { exact: true })).toBeVisible();
      await expect(
        page
          .getByLabel("打开页面")
          .getByRole("button", { name: `关闭${compatibilityPage.heading}页签`, exact: true })
      ).toBeVisible();
    }
  });
});
