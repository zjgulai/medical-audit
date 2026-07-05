import { expect, test } from "@playwright/test";

const redirects = [
  ["/workspace", /\/chat$/],
  ["/fund-compliance", /\/medical-audit$/],
  ["/fund-compliance/review", /\/medical-audit$/],
  ["/knowledge-query", /\/documents$/],
  ["/findings", /\/medical-audit$/],
  ["/rules", /\/knowledge-base$/],
  ["/remediation", /\/medical-audit$/],
  ["/archive", /\/reports$/],
  ["/guided-check", /\/chat$/]
] as const;

test("login and replica shell interactions have deterministic results", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("账号 / 工号").fill("demo_user");
  await page.locator("#login-password").fill("demo_password");
  await page.getByRole("button", { name: "显示密码" }).click();
  await expect(page.locator("#login-password")).toHaveAttribute("type", "text");

  await page.getByRole("button", { name: /登\s*录/ }).click();
  await expect(page.getByRole("dialog", { name: "初始密码安全提示" })).toBeVisible();
  await page.getByRole("button", { name: "稍后处理" }).click();
  await expect(page).toHaveURL(/\/chat$/);
  expect(page.url()).not.toContain("password=");
  expect(page.url()).not.toContain("account=");

  await page.getByRole("link", { name: "打开历史对话：中标候选人名单表" }).click();
  await expect(page).toHaveURL(/\/chat\?history=history-1$/);
  await expect(page.getByRole("heading", { name: "中标候选人名单表" })).toBeVisible();
  await expect(page.getByText(/本地历史记录：已标出候选人排序/)).toBeVisible();

  await page.goto("/documents");
  await page.getByRole("button", { name: "收起侧栏" }).click();
  await expect(page.locator(".replica-app-shell")).toHaveClass(/replica-sidebar-collapsed/);

  await page.getByRole("button", { name: "展开侧栏" }).click();
  await page.getByRole("button", { name: "关闭文档检索页签" }).click();
  await expect(page.locator(".replica-page-tag", { hasText: "文档检索" })).toHaveCount(0);
});

test("legacy entries and medical audit local flows remain usable", async ({ page }) => {
  for (const [route, target] of redirects) {
    await page.goto(route);
    await expect(page).toHaveURL(target);
  }

  await page.goto("/medical-audit");
  await expect(page.getByRole("heading", { name: "医保审计" })).toBeAttached();
  await page.getByRole("button", { name: "打开AI审计助手" }).click();
  await page.getByPlaceholder("询问当前疑点、复核意见或整改建议...").fill("请解释当前疑点");
  await page.getByRole("button", { name: "发送" }).click();
  await expect(page.getByText(/生成 AI 审计建议已生成预览/)).toBeVisible();

  await page.getByRole("tab", { name: "费用汇总表" }).click();
  await page.getByRole("button", { name: "新建表单" }).click();
  await expect(page.getByText(/新建表单已生成预览/)).toBeVisible();
  await page.getByRole("tab", { name: "分类汇总表" }).click();
  await page.getByRole("tab", { name: "就诊明细表" }).click();
});

test("refactored read surfaces keep local sample boundary when backend is unavailable", async ({ page }) => {
  await page.goto("/knowledge-base");
  await expect(page.getByRole("heading", { name: "知识库", exact: true })).toBeVisible();
  await expect(page.getByText("系统知识库").first()).toBeVisible();

  await page.goto("/documents");
  await expect(page.getByRole("heading", { name: "文档检索" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "搜索历史:" })).toBeVisible();

  await page.goto("/reports");
  await expect(page.getByRole("heading", { name: "底稿与报告" })).toBeVisible();
  await expect(page.getByText("历史记录")).toBeVisible();
});
