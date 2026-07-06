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

async function mockReplicaBackend(page: Page) {
  await mockJson(page, "**/api/backend/index/search-backend", {
    backend: "playwright-fixture",
    ready: true,
    details: { provider_call: false, database_write: false, matching_embedding_count: 12 }
  });
  await mockJson(page, "**/api/v1/auth/session", {
    user_identifier: "next-admin",
    role: "admin",
    role_label: "管理员",
    legacy_api_role: "admin",
    auth_source: "playwright-fixture",
    profile_status: "active",
    auth_scope_type: "project",
    auth_scope_key: "SELF-CHECK-FUND-20260607",
    auth_mode: "header_transition_layer",
    store: { ready: true, backend: "playwright-fixture" }
  });
  await mockJson(page, "**/api/v1/query/models", {
    default_model: "kimi-2.7",
    items: [
      { alias: "kimi-2.7", label: "Kimi 2.7", available: true, model_status: "ready" },
      { alias: "deepseek-v4-pro", label: "DeepSeek V4 Pro", available: true, model_status: "ready" }
    ]
  });
  await mockJson(page, "**/api/v1/documents/source-collections", {
    contract_version: "document-source-collections-v1",
    role: "admin",
    items: [
      {
        source_collection: "medical-insurance-laws",
        label: "法规政策",
        scope: "公开知识库",
        queryable: true,
        product_queryable: true,
        metrics: { document_count: 612, chunk_count: null, character_count: null, linked_app_count: 1 }
      },
      {
        source_collection: "supervision-rules-knowledge",
        label: "监管两库",
        scope: "系统知识库",
        queryable: true,
        product_queryable: true,
        metrics: { document_count: 12840, chunk_count: null, character_count: null, linked_app_count: 1 }
      }
    ],
    search_backend: { ready: true, backend: "playwright-fixture" },
    upload_permissions: {
      can_upload_personal: true,
      can_read_all_personal_uploads: true,
      can_govern_personal_uploads: true
    }
  });
  await mockJson(page, "**/api/v1/agents", {
    items: [
      {
        id: "agent-citation-check",
        name: "引用依据核验助手",
        category: "业务类",
        topic: "医保基金合规",
        prompt: "核验引用依据和政策口径。",
        project_name: "医保基金使用合规专项自查",
        knowledge_base: "法规政策",
        status: "active",
        visibility_scope: "project",
        allowed_roles: ["admin"],
        metadata: { avatar_initial: "引", avatar_tone: "blue" }
      }
    ],
    store: { ready: true, backend: "playwright-fixture" }
  });
  await mockJson(page, "**/api/v1/query/logs**", {
    items: [],
    store: { ready: true, backend: "playwright-fixture" }
  });
  await mockJson(page, "**/api/v1/query", {
    question: "医保基金审核依据是什么？",
    answer: "本地验收模型回答：应结合法规政策、监管两库和医保目录限制条件核验。",
    confidence: "medium",
    fallback_used: false,
    model_alias: "kimi-2.7",
    model_status: "ready",
    agent_invocation_id: "invocation-e2e-001",
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
    basis_groups: [],
    personal_upload_matches: [],
    query_log_index: 1,
    query_log_id: "query-e2e-001"
  });
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("medical-audit-authenticated", "authenticated");
    window.localStorage.setItem("medical-audit-current-role", "admin");
  });
  await mockReplicaBackend(page);
});

const sidebarRoutes = [
  { href: "/chat", label: "AI 对话", heading: "AI，让审计更智能" },
  { href: "/agents", label: "我的智能体", heading: "我的助手" },
  { href: "/agent-market", label: "智能体广场", heading: "发现审计智能体" },
  { href: "/knowledge-base", label: "知识库", heading: "知识库" },
  { href: "/documents", label: "文档检索", heading: "文档检索" },
  { href: "/analytics", label: "AI数据分析", heading: "AI数据分析" },
  { href: "/graph", label: "知识图谱", heading: "知识图谱" },
  { href: "/reports", label: "审计底稿/报告", heading: "底稿与报告" },
  { href: "/projects", label: "项目管理", heading: "项目管理" },
  { href: "/medical-audit", label: "医保审计", heading: "医保审计" }
] as const;

async function expectNoBrokenImages(page: Page) {
  await page.waitForFunction(() =>
    Array.from(document.images).every((image) => image.complete)
  );
  const brokenImages = await page.locator("img").evaluateAll((images) =>
    images
      .filter((image) => image.naturalWidth === 0 || image.naturalHeight === 0)
      .map((image) => image.getAttribute("src") ?? "")
  );

  expect(brokenImages).toEqual([]);
}

test("replica shell renders the restored sidebar navigation", async ({ page }) => {
  await page.goto("/chat");

  const navigation = page.getByRole("navigation", { name: "主导航" });
  await expect(page.getByRole("link", { name: "医疗AI审计平台" })).toHaveAttribute("href", "/chat");
  await expect(page.getByTestId("auditscope-brand-logo")).toBeVisible();
  await expect(navigation.getByRole("link")).toHaveCount(sidebarRoutes.length);

  for (const route of sidebarRoutes) {
    await expect(navigation.getByRole("link", { name: route.label })).toHaveAttribute("href", route.href);
  }
});

test("all restored sidebar pages expose their current product skeleton", async ({ page }) => {
  for (const route of sidebarRoutes) {
    await page.goto(route.href);
    await expect(page.getByRole("heading", { name: route.heading, exact: true })).toBeVisible();
    await expect(page.getByRole("navigation", { name: "主导航" }).getByRole("link", { name: route.label, exact: true })).toHaveAttribute(
      "aria-current",
      "page"
    );
    await expectNoBrokenImages(page);
  }
});

test("workspace and legacy routes redirect to the restored replica destinations", async ({ page }) => {
  const redirects = [
    { from: "/workspace", to: /\/chat$/ },
    { from: "/knowledge-query", to: /\/documents$/ },
    { from: "/fund-compliance", to: /\/medical-audit$/ },
    { from: "/fund-compliance/review", to: /\/medical-audit$/ },
    { from: "/findings", to: /\/medical-audit$/ },
    { from: "/remediation", to: /\/medical-audit$/ },
    { from: "/archive", to: /\/reports$/ },
    { from: "/guided-check", to: /\/chat$/ }
  ] as const;

  for (const redirect of redirects) {
    await page.goto(redirect.from);
    await expect(page).toHaveURL(redirect.to);
  }
});

test("document search, analytics, graph, reports, projects and medical audit keep core interactions reachable", async ({ page }) => {
  await page.goto("/documents");
  await page.getByLabel("检索关键词").fill("医保基金审核依据是什么？");
  await page.getByRole("button", { name: "搜索", exact: true }).click();
  await expect(page.getByText("1 条匹配").first()).toBeVisible();
  await expect(page.getByText("medical-insurance-laws").first()).toBeVisible();

  await page.goto("/analytics");
  await page.locator('input[type="file"]').setInputFiles({
    name: "charge-sample.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("patient_id,charge_amount\nP001,120\n")
  });
  await expect(page.getByText("charge-sample.csv", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "开始分析" }).click();
  await expect(page.getByText(/结果预览已生成预览/)).toBeVisible();

  await page.goto("/graph");
  await page.getByRole("button", { name: /乡村振兴专项审计图谱/ }).click();
  await expect(page.getByLabel("图谱详情预览")).toBeVisible();
  await page.getByRole("button", { name: "关闭图谱详情" }).click();

  await page.goto("/reports");
  await page.getByRole("button", { name: "查看底稿" }).first().click();
  await expect(page.getByLabel("报告详情预览")).toBeVisible();
  await page.getByRole("button", { name: "关闭报告详情" }).click();

  await page.goto("/projects");
  await expect(page.getByLabel("审计驾驶舱")).toBeVisible();
  await expect(page.getByText("总审计条数")).toBeVisible();

  await page.goto("/medical-audit");
  await page.getByRole("tab", { name: "费用汇总表" }).click();
  await expect(page.getByLabel("医保费用汇总表")).toBeVisible();
});

test("portal pages render without placeholder text or mobile page overflow", async ({ page }) => {
  test.setTimeout(60_000);
  await page.setViewportSize({ width: 390, height: 1000 });

  for (const route of sidebarRoutes) {
    await page.goto(route.href);
    await expect(page.locator("h1"), `${route.href} h1 count`).toHaveCount(1);

    const audit = await page.evaluate(() => ({
      clientWidth: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
      bodyScrollWidth: document.body.scrollWidth,
      bodyText: document.body.textContent ?? ""
    }));

    expect(audit.scrollWidth, `${route.href} document overflow`).toBeLessThanOrEqual(audit.clientWidth);
    expect(audit.bodyScrollWidth, `${route.href} body overflow`).toBeLessThanOrEqual(audit.clientWidth);
    expect(audit.bodyText, `${route.href} placeholder text`).not.toMatch(
      /BackendFeatureBridge|Plan \d+|Coming soon|敬请期待|占位/
    );
  }
});
