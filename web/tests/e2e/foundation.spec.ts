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
      { alias: "kimi-2.7", label: "Kimi K2.6（兼容别名）", available: true, model_status: "ready" },
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
  await mockJson(page, "**/api/v1/knowledge-base/catalog", {
    contract_version: "knowledge-base-catalog-v1",
    role: "admin",
    summary: {
      source_collection_count: 2,
      queryable_collection_count: 2,
      total_document_count: 13452,
      total_chunk_count: 49051,
      total_embedding_count: 49051,
      current_search_embedding_count: 49051,
      candidate_chunk_count: 0,
      domain_counts: { medical: 1, policy: 1 }
    },
    items: [
      {
        source_collection: "medical-insurance-laws",
        label: "法规政策",
        scope: "公开知识库",
        phase: "active",
        domain: "medical",
        evidence_group: "legal",
        description: "医保基金监管与支付依据。",
        audit_hint: "用于判断制度依据和监管边界。",
        access: "read",
        product_queryable: true,
        queryable: true,
        metrics: {
          document_count: 612,
          chunk_count: 49051,
          embedding_count: 49051,
          active_embedding_count: 49051,
          candidate_chunk_count: 0,
          character_count: 123456,
          linked_app_count: 1
        },
        index: {
          latest_version_key: "active-index",
          latest_status: "active",
          search_backend_ready: true,
          queryable: true
        },
        actions: {
          documents: "/documents?source_collection=medical-insurance-laws",
          chat: "/chat?source_collection=medical-insurance-laws",
          graph: "/graph?source_collection=medical-insurance-laws"
        }
      },
      {
        source_collection: "supervision-rules-knowledge",
        label: "监管两库",
        scope: "系统知识库",
        phase: "active",
        domain: "policy",
        evidence_group: "supervision",
        description: "监管规则、医保目录限制和审核口径。",
        audit_hint: "用于核验监管规则和审核边界。",
        access: "read",
        product_queryable: true,
        queryable: true,
        metrics: {
          document_count: 12840,
          chunk_count: 18000,
          embedding_count: 18000,
          active_embedding_count: 18000,
          candidate_chunk_count: 0,
          character_count: 65432,
          linked_app_count: 1
        },
        index: {
          latest_version_key: "active-index",
          latest_status: "active",
          search_backend_ready: true,
          queryable: true
        },
        actions: {
          documents: "/documents?source_collection=supervision-rules-knowledge",
          chat: "/chat?source_collection=supervision-rules-knowledge",
          graph: "/graph?source_collection=supervision-rules-knowledge"
        }
      }
    ],
    search_backend: { ready: true, backend: "playwright-fixture", details: {} },
    store: { ready: true, backend: "runtime_state_and_postgres_catalog" },
    boundaries: {
      production_write: false,
      provider_call: false,
      database_write: false,
      object_storage_write: false,
      query_history_write: false,
      source: "runtime_state_and_postgres_catalog"
    }
  });
  await mockJson(page, "**/api/v1/documents/search**", {
    contract_version: "document-search-v1",
    query: "医保基金审核依据是什么？",
    effective_source_collections: ["medical-insurance-laws"],
    items: [
      {
        id: "chunk-e2e-001",
        chunk_id: "chunk-e2e-001",
        title: "医保基金审核依据",
        source_collection: "medical-insurance-laws",
        source_label: "法规政策",
        snippet: "医保基金使用应遵循目录限制条件、支付范围和监管规则。",
        locator: { title: "医保基金审核依据" },
        score: 1,
        matched_by: ["vector"],
        index_version_key: "active",
        source_package_version_key: "fixture",
        preview_url: "/api/v1/preview/chunk-e2e-001"
      }
    ],
    store: { ready: true, backend: "playwright-fixture" },
    boundaries: {
      production_write: false,
      provider_call: false,
      database_write: false,
      object_storage_write: false,
      query_history_write: false
    }
  });
  await mockJson(page, "**/api/v1/graph/workbench", {
    format: "graph-workbench-v1",
    graph_id: "SELF-CHECK-FUND-20260607",
    graph_title: "医保基金使用合规专项图谱",
    graph_scope: "基于当前可查询知识库目录，将医疗医保和政策知识组织成可审证关系图。",
    view: "knowledge",
    project_key: null,
    evidence_chain_status: "catalog",
    nodes: [
      {
        id: "graph-node-project",
        label: "医疗审计知识工程",
        kind: "项目",
        status: "已归集",
        description: "当前生产知识库目录、文档检索和审计问答共同使用的知识底座。",
        metric: "2 类知识库",
        href: "/projects",
        x: 100,
        y: 250
      },
      {
        id: "graph-domain-medical",
        label: "医疗医保知识",
        kind: "一级分类",
        status: "可引用",
        description: "医疗医保知识下共有 1 个知识库。",
        metric: "49,051 chunks",
        href: "/knowledge-base?domain=medical",
        x: 280,
        y: 120
      },
      {
        id: "graph-source-medical-insurance-laws",
        label: "法规政策",
        kind: "知识库",
        status: "可引用",
        description: "医保基金监管与支付依据。",
        metric: "612 文档 / 49,051 chunks",
        href: "/documents?source_collection=medical-insurance-laws",
        x: 220,
        y: 520,
        sourceCollection: "medical-insurance-laws",
        domain: "medical"
      }
    ],
    relations: [
      {
        id: "graph-project-medical",
        sourceId: "graph-node-project",
        targetId: "graph-domain-medical",
        source: "医疗审计知识工程",
        relation: "组织",
        target: "医疗医保知识",
        evidence: "1 个一级知识库分类",
        strength: "强"
      },
      {
        id: "graph-medical-medical-insurance-laws",
        sourceId: "graph-domain-medical",
        targetId: "graph-source-medical-insurance-laws",
        source: "医疗医保知识",
        relation: "包含",
        target: "法规政策",
        evidence: "49,051 active embeddings",
        strength: "强"
      }
    ],
    metrics: {
      node_count: 3,
      node_kind_count: 3,
      node_kind_counts: { 项目: 1, 一级分类: 1, 知识库: 1 },
      relation_count: 2,
      strong_relation_count: 2,
      pending_relation_count: 0
    },
    evidence_grade: "local-readonly-api",
    production_side_effect: "none",
    store: { ready: true, backend: "KnowledgeCatalogGraphBuilder" }
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
  { href: "/agents", label: "我的智能体", heading: "我的智能体" },
  { href: "/agent-market", label: "智能体广场", heading: "智能体广场" },
  { href: "/knowledge-base", label: "知识库", heading: "知识库分类" },
  { href: "/documents", label: "文档检索", heading: "文档检索" },
  { href: "/analytics", label: "AI数据分析", heading: "表格分析工作台" },
  { href: "/graph", label: "知识图谱", heading: "知识依据与项目证据链" },
  { href: "/reports", label: "审计底稿/报告", heading: "审计底稿与报告台账" },
  { href: "/projects", label: "项目管理", heading: "项目协作工作台" }
] as const;

const topicRoute = { href: "/medical-audit", label: "医保审计专题", heading: "医保审计" } as const;
const portalRoutes = [...sidebarRoutes, topicRoute] as const;

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
  await expect(page.getByRole("link", { name: "AI审计一体化协作平台" })).toHaveAttribute("href", "/chat");
  await expect(page.getByTestId("auditscope-brand-logo")).toBeVisible();
  await expect(navigation.getByRole("link")).toHaveCount(sidebarRoutes.length);
  await expect(page.getByRole("link", { name: "打开医保审计专题", exact: true })).toHaveAttribute(
    "href",
    topicRoute.href
  );

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

  await page.goto(topicRoute.href);
  await expect(page.getByRole("heading", { name: topicRoute.heading, exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "打开医保审计专题", exact: true })).toHaveAttribute(
    "aria-current",
    "page"
  );
  await expectNoBrokenImages(page);
});

test("workspace keeps its redirect while compatibility routes render current product pages", async ({ page }) => {
  const redirects = [
    { from: "/workspace", to: /\/chat$/ },
    { from: "/findings", to: /\/medical-audit$/ }
  ] as const;

  for (const redirect of redirects) {
    await page.goto(redirect.from);
    await expect(page).toHaveURL(redirect.to);
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

  const compatibilityPages = [
    { href: "/fund-compliance", heading: "医保基金使用合规", text: "医保审计" },
    { href: "/fund-compliance/review", heading: "医保基金复核表单", text: "费用汇总表" },
    { href: "/archive", heading: "归档工作台", text: "归档包" },
    { href: "/guided-check", heading: "引导式核查", text: "核查步骤" },
    { href: "/remediation", heading: "整改工作台", text: "整改事项、补证请求、关闭门禁" }
  ] as const;

  for (const route of compatibilityPages) {
    await page.goto(route.href);
    await expect(page).toHaveURL(new RegExp(`${route.href.replace(/\//g, "\\/")}$`));
    await expect(page.getByRole("heading", { name: route.heading, exact: true })).toBeVisible();
    await expect(page.getByText(route.text).first()).toBeVisible();
  }
});

test("compatibility route CTAs keep the medical audit workflow reachable", async ({ page }) => {
  await page.goto("/fund-compliance");
  await page.getByRole("link", { name: "进入医保审计" }).click();
  await expect(page).toHaveURL(/\/medical-audit$/);
  await expect(page.getByRole("heading", { name: "医保审计", exact: true })).toBeVisible();

  await page.goto("/fund-compliance/review");
  await page.getByRole("link", { name: "进入分析" }).first().click();
  await expect(page).toHaveURL(/\/analytics\?template=medical-expense-summary$/);
  await expect(page.getByRole("heading", { name: "表格分析工作台", exact: true })).toBeVisible();

  await page.goto("/guided-check");
  await page.getByRole("link", { name: "进入 AI 对话" }).click();
  await expect(page).toHaveURL(/\/chat$/);
  await expect(page.getByRole("heading", { name: "AI，让审计更智能" })).toBeVisible();
});

test("document search, preview modules and medical audit keep core interactions reachable", async ({ page }) => {
  await page.goto("/documents");
  await page.getByLabel("检索关键词").fill("医保基金审核依据是什么？");
  await page.getByRole("button", { name: "搜索", exact: true }).click();
  await expect(page.getByText("1 条匹配").first()).toBeVisible();
  await expect(page.getByText("medical-insurance-laws").first()).toBeVisible();

  await page.goto("/analytics");
  await expect(page.getByRole("heading", { name: "表格分析工作台", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "上传表格", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "分析历史", exact: true })).toBeVisible();

  await page.goto("/graph");
  await expect(page.getByLabel("知识依据图谱工作台")).toBeVisible();
  await expect(page.getByRole("tab", { name: "知识依据" })).toHaveAttribute("aria-selected", "true");

  await page.goto("/reports");
  await expect(page.getByRole("heading", { name: "审计底稿与报告台账", exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "报表分类目录" })).toBeVisible();

  await page.goto("/projects");
  await expect(page.getByRole("heading", { name: "项目协作工作台", exact: true })).toBeVisible();
  await expect(page.getByRole("combobox", { name: "项目状态" })).toBeVisible();

  await page.goto("/medical-audit");
  await page.getByRole("tab", { name: "费用汇总表" }).click();
  await expect(page.getByLabel("医保费用汇总表")).toBeVisible();
});

test("portal pages render without placeholder text or mobile page overflow", async ({ page }) => {
  test.setTimeout(60_000);
  await page.setViewportSize({ width: 390, height: 1000 });

  for (const route of portalRoutes) {
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
