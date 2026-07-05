import { expect, test, type Page } from "@playwright/test";

const coreRoutes = [
  ["/chat", "AI，让审计更智能"],
  ["/agents", "我的助手"],
  ["/agent-market", "发现审计智能体"],
  ["/knowledge-base", "知识库"],
  ["/documents", "文档检索"],
  ["/analytics", "AI数据分析"],
  ["/graph", "知识图谱"],
  ["/reports", "底稿与报告"],
  ["/projects", "项目管理"],
  ["/medical-audit", "医保审计"]
] as const;

const legacyRedirects = [
  ["/", /\/chat$/],
  ["/workspace", /\/chat$/],
  ["/findings", /\/medical-audit$/],
  ["/fund-compliance", /\/medical-audit$/],
  ["/fund-compliance/review", /\/medical-audit$/],
  ["/guided-check", /\/chat$/],
  ["/knowledge-query", /\/documents$/],
  ["/rules", /\/knowledge-base$/],
  ["/remediation", /\/medical-audit$/],
  ["/archive", /\/reports$/]
] as const;

async function expectNoBrokenImages(page: Page) {
  const brokenImages = await page.locator("img").evaluateAll((images) =>
    images
      .filter((image) => image.naturalWidth === 0 || image.naturalHeight === 0)
      .map((image) => image.getAttribute("src") ?? "")
  );

  expect(brokenImages).toEqual([]);
}

async function expectRouteHeading(page: Page, heading: string) {
  const locator = page.getByRole("heading", { name: heading, exact: true });
  if (heading === "医保审计") {
    await expect(locator).toBeAttached();
    return;
  }
  await expect(locator).toBeVisible();
}

test("refactored shell renders navigation and product routes", async ({ page }) => {
  await page.goto("/documents");

  const primaryNavigation = page.getByRole("navigation", { name: "主导航" });
  await expect(page.getByRole("link", { name: "AI审计应用" })).toHaveAttribute("href", "/chat");
  await expect(primaryNavigation.getByRole("link")).toHaveCount(10);
  await expect(primaryNavigation.getByRole("link", { name: /AI 对话/ })).toHaveAttribute("href", "/chat");
  await expect(primaryNavigation.getByRole("link", { name: /我的智能体/ })).toHaveAttribute("href", "/agents");
  await expect(primaryNavigation.getByRole("link", { name: /智能体广场/ })).toHaveAttribute("href", "/agent-market");
  await expect(primaryNavigation.getByRole("link", { name: /知识库/ })).toHaveAttribute("href", "/knowledge-base");
  await expect(primaryNavigation.getByRole("link", { name: /文档检索/ })).toHaveAttribute("href", "/documents");
  await expect(primaryNavigation.getByRole("link", { name: /AI数据分析/ })).toHaveAttribute("href", "/analytics");
  await expect(primaryNavigation.getByRole("link", { name: /知识图谱/ })).toHaveAttribute("href", "/graph");
  await expect(primaryNavigation.getByRole("link", { name: /审计底稿\/报告/ })).toHaveAttribute("href", "/reports");
  await expect(primaryNavigation.getByRole("link", { name: /项目管理/ })).toHaveAttribute("href", "/projects");
  await expect(primaryNavigation.getByRole("link", { name: /医保审计/ })).toHaveAttribute("href", "/medical-audit");
  await expect(page.getByRole("heading", { name: "文档检索" })).toBeVisible();
  await expectNoBrokenImages(page);
});

test("core refactored pages are reachable", async ({ page }) => {
  for (const [route, heading] of coreRoutes) {
    await page.goto(route);
    await expectRouteHeading(page, heading);
    await expectNoBrokenImages(page);
  }
});

test("legacy frontend entries redirect to refactored surfaces", async ({ page }) => {
  for (const [route, target] of legacyRedirects) {
    await page.goto(route);
    await expect(page).toHaveURL(target);
    await expect(page.getByRole("navigation", { name: "主导航" })).toBeVisible();
  }
});

test("refactored pages avoid placeholder copy and mobile overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 1000 });

  for (const [route] of coreRoutes) {
    await page.goto(route);

    const audit = await page.evaluate(() => ({
      clientWidth: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
      bodyScrollWidth: document.body.scrollWidth,
      bodyText: document.body.textContent ?? ""
    }));

    expect(audit.scrollWidth, `${route} document overflow`).toBeLessThanOrEqual(audit.clientWidth);
    expect(audit.bodyScrollWidth, `${route} body overflow`).toBeLessThanOrEqual(audit.clientWidth);
    expect(audit.bodyText, `${route} placeholder copy`).not.toMatch(
      /BackendFeatureBridge|Plan \d+|Coming soon|敬请期待|占位/
    );
  }
});
