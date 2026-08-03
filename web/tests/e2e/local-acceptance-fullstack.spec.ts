import { expect, test } from "@playwright/test";

test.describe("local fullstack acceptance for restored replica product", () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem("medical-audit-authenticated", "authenticated");
      window.localStorage.setItem("medical-audit-current-role", "admin");
    });
    await page.route("**/api/v1/documents/library**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json; charset=utf-8",
        body: JSON.stringify({
          contract_version: "document-library-v1",
          effective_source_collections: ["medical-insurance-laws"],
          items: [
            {
              id: "document-fullstack-001",
              title: "医保基金审核依据",
              source_collection: "medical-insurance-laws",
              source_label: "法规政策",
              file_ext: "md",
              size_bytes: 128,
              updated_at: "2026-08-01T00:00:00Z",
              chunk_count: 1,
              page_count: 1,
              preview_url: "/api/v1/preview/document-fullstack-001",
              download_url: "/api/v1/documents/source/document-fullstack-001/download",
              provenance: {
                relative_path: "全量法律/law.md",
                sha256: "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                source_package_version_key: "local-fullstack-fixture-v1"
              }
            }
          ],
          store: { ready: true, backend: "playwright-local-fullstack-fixture" },
          boundaries: {
            production_write: false,
            provider_call: false,
            database_write: false,
            object_storage_write: false,
            query_history_write: false
          }
        })
      })
    );
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
    await expect(page.getByText("法规政策").first()).toBeVisible();
    await expect(page.getByText("medical-insurance-laws")).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "关键词命中位置" })).toBeVisible();
    await expect(page.getByRole("link", { name: "预览原文" })).toBeVisible();
    await expect(page.getByRole("button", { name: "下载原文" })).toBeVisible();
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
    await expect(
      page.getByRole("heading", { name: "选择一个审计案例，上传数据即可得到可复核结果", exact: true })
    ).toBeVisible();
    await expect(page.getByRole("heading", { name: "上传数据并执行审计数据分析", exact: true })).toBeVisible();
    await expect(page.getByText("浏览本地文件", { exact: true })).toBeVisible();
    await expect(page.getByText("provider_call=false", { exact: true })).toBeHidden();
    await expect(page.getByRole("heading", { name: "分析记录", exact: true })).toBeVisible();

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
    await expect(page.getByRole("heading", { name: "报告与底稿", level: 1, exact: true })).toBeVisible();
    await expect(page.getByRole("region", { name: "报表分类目录" })).toBeVisible();

    await page.goto("/projects");
    await expect(page.getByRole("heading", { name: "项目协作工作台", exact: true })).toBeVisible();
    await expect(page.getByRole("combobox", { name: "项目状态" })).toBeVisible();

    await page.goto("/medical-audit");
    await expect(page.getByRole("heading", { name: "医保审计", exact: true })).toBeVisible();
    await page.getByRole("tab", { name: "费用汇总表" }).click();
    await expect(page.getByLabel("医保费用汇总表")).toBeVisible();
  });

  test("audit-only knowledge, OCR and the project cockpit stay reachable", async ({ page }) => {
    await page.goto("/knowledge-base");
    await expect(page.getByRole("heading", { name: "审计知识库", exact: true })).toBeVisible();
    await expect(page.getByText("审计核心知识", { exact: true })).toBeVisible();
    await expect(page.getByText("原文溯源", { exact: true })).toBeVisible();

    await page.goto("/ocr");
    await expect(page.getByRole("heading", { name: "扫描材料识别工作台", exact: true })).toBeVisible();
    await expect(page.getByText(/Unlimited-OCR/).first()).toBeVisible();

    await page.goto("/audit-cockpit");
    await expect(page.getByRole("heading", { name: "审计驾驶舱", exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: "进入项目管理", exact: true })).toHaveAttribute("href", "/projects");
    const navigationLabels = await page.getByRole("navigation", { name: "主导航" }).getByRole("link").allTextContents();
    expect(navigationLabels.slice(-2)).toEqual(["项目管理", "审计驾驶舱"]);
  });

  test("report download controls remain in the mobile viewport", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 900 });
    await page.route("**/api/v1/reports/workbench", async (route) => {
      const response = await route.fetch();
      const body = await response.json();
      body.report_entries = [
        {
          id: "mobile-report-001",
          title: "医保基金专项报告",
          status: "已签发",
          report_no: "RPT-MOBILE-001",
          owner: "审计办",
          source: "review-task",
          included_finding_count: 2,
          appendix_count: 1,
          gate_summary: "报告门禁已通过",
          updated_at: "2026-07-20T00:00:00Z",
          href: "/projects",
          download_links: {
            page: "/projects",
            task_docx: "/review-tasks/mobile-report-001/export?format=docx",
            report_docx: "/review-tasks/mobile-report-001/signed-report?format=docx",
            report_markdown: "/review-tasks/mobile-report-001/signed-report?format=markdown",
            report_json: "/review-tasks/mobile-report-001/signed-report?format=json"
          }
        }
      ];
      body.metrics = {
        report_count: 1,
        signed_report_count: 1,
        blocked_report_count: 0,
        included_finding_count: 2,
        docx_download_count: 1
      };
      await route.fulfill({ response, json: body });
    });
    await page.goto("/reports");
    await expect(page.getByRole("heading", { name: "报告与底稿", level: 1, exact: true })).toBeVisible();

    const downloadControls = page.locator(".replica-report-table-wrap button");
    await expect(downloadControls.first()).toBeVisible();
    const controlBounds = await downloadControls.evaluateAll((controls) =>
      controls.map((control) => {
        const rect = control.getBoundingClientRect();
        return { left: rect.left, right: rect.right, clientWidth: document.documentElement.clientWidth };
      })
    );

    expect(controlBounds.length).toBeGreaterThan(0);
    for (const bounds of controlBounds) {
      expect(bounds.left).toBeGreaterThanOrEqual(-2);
      expect(bounds.right).toBeLessThanOrEqual(bounds.clientWidth + 2);
    }
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
      "/knowledge-query?q=%E5%8C%BB%E4%BF%9D%E6%94%AF%E4%BB%98&source_collection=medical-insurance-laws&unknown=discard&source_collection=personal-materials"
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
