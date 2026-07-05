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

async function mockReadOnlyBackend(page: Page) {
  await mockJson(page, "**/api/backend/health", {
    status: "ok",
    version: "playwright",
    data_root: "/tmp/playwright"
  });
  await mockJson(page, "**/api/backend/index/search-backend", {
    backend: "playwright-fixture",
    ready: true,
    details: { matching_embedding_count: 12 }
  });
}

async function mockOfflineWorkbenchReads(page: Page) {
  await mockJson(page, "**/api/backend/health", { detail: "backend offline" }, 503);
  await mockJson(page, "**/api/backend/index/search-backend", { detail: "backend offline" }, 503);
  await mockJson(page, "**/api/v1/rules/workbench", { detail: "backend offline" }, 503);
  await mockJson(page, "**/api/v1/remediation/workbench", { detail: "backend offline" }, 503);
  await mockJson(page, "**/api/v1/archive/workbench", { detail: "backend offline" }, 503);
}

test("login and replica shell interactions have deterministic results", async ({ page }) => {
  await mockReadOnlyBackend(page);

  await page.goto("/login");
  await page.getByLabel("账号 / 工号").fill("demo_user");
  await page.locator("#login-password").fill("demo_password");
  await page.getByRole("button", { name: "显示密码" }).click();
  await expect(page.locator("#login-password")).toHaveAttribute("type", "text");

  await page.getByRole("button", { name: /登\s*录/ }).click();
  await expect(page.getByRole("dialog", { name: "初始密码安全提示" })).toBeVisible();
  await page.getByRole("button", { name: "稍后处理" }).click();
  await expect(page).toHaveURL(/\/workspace$/);
  expect(page.url()).not.toContain("password=");
  expect(page.url()).not.toContain("account=");

  await page.goto("/chat");
  await page.getByRole("link", { name: "打开历史对话：中标候选人名单表" }).click();
  await expect(page).toHaveURL(/\/chat\?history=history-1$/);
  await expect(page.getByRole("heading", { name: "中标候选人名单表" })).toBeVisible();
  await expect(page.getByText("已恢复历史对话")).toBeVisible();
  await expect(page.getByText(/本地历史记录：已标出候选人排序/)).toBeVisible();

  await page.goto("/documents");
  await page.getByRole("button", { name: "收起侧栏" }).click();
  await expect(page.locator(".replica-app-shell")).toHaveClass(/replica-sidebar-collapsed/);

  await page.getByRole("button", { name: "展开侧栏" }).click();
  await page.getByRole("button", { name: "关闭文档检索页签" }).click();
  await expect(page.locator(".replica-page-tag", { hasText: "文档检索" })).toHaveCount(0);
});

test("fund compliance and medical audit local flows remain usable", async ({ page }) => {
  await mockReadOnlyBackend(page);

  await page.goto("/fund-compliance");
  await page.getByRole("link", { name: "进入审查" }).click();
  await expect(page).toHaveURL(/\/fund-compliance\/review$/);
  await page.getByRole("tab", { name: "费用表单" }).click();
  await page.getByRole("tab", { name: "表3" }).click();
  await expect(page.getByText("表3_就诊费用明细表（空白）.xlsx / 明细表")).toBeVisible();
  await page.getByText("新建表单").click();
  await expect(page.getByLabel("表单名称")).toBeVisible();

  await page.goto("/medical-audit");
  await expect(page.getByRole("heading", { name: "医保审计" })).toBeAttached();
  await page.getByRole("button", { name: "打开AI审计助手" }).click();
  await expect(page.getByText(/打开 AI 审计助手已生成预览/)).toBeVisible();
  await page.getByPlaceholder("询问当前疑点、复核意见或整改建议...").fill("请解释当前疑点");
  await page.getByRole("button", { name: "发送" }).click();
  await expect(page.getByText(/生成 AI 审计建议已生成预览/)).toBeVisible();
});

test("backend-offline read surfaces show local sample boundary", async ({ page }) => {
  await mockOfflineWorkbenchReads(page);

  await page.goto("/workspace");
  await expect(page.getByRole("heading", { name: "知识库暂未连接" })).toBeVisible();
  await expect(page.getByText("当前展示演示数据，可先体验检索、审证和底稿路径。")).toBeVisible();

  await page.goto("/rules");
  await expect(page.getByRole("heading", { name: "审计规则与依据总览" })).toBeVisible();
  await expect(page.getByText("演示数据").first()).toBeVisible();
  await expect(page.getByText("当前展示演示规则，用于核对规则分类、来源覆盖和疑点流转。")).toBeVisible();

  await page.goto("/remediation");
  await expect(page.getByRole("heading", { name: "整改事项与补证闭环" })).toBeVisible();
  await expect(page.getByText("当前展示演示整改台账，用于核对责任科室、补证材料和关闭门禁。")).toBeVisible();

  await page.goto("/archive");
  await expect(page.getByRole("heading", { name: "项目档案与审计日志归档" })).toBeVisible();
  await expect(page.getByText("当前展示演示归档包，用于核对材料完整性、签名链和归档策略。")).toBeVisible();
});
