import { expect, test } from "@playwright/test";

test("self-check OS foundation renders navigation and core modules", async ({ page }) => {
  await page.goto("/workspace");

  const primaryNavigation = page.getByRole("navigation", { name: "主导航" });
  const chatLink = primaryNavigation.getByRole("link", { name: /^对话审证/ });

  await expect(page.getByRole("heading", { name: "医保基金使用合规专项自查" })).toBeVisible();
  await expect(page.getByText("待处理疑点")).toBeVisible();
  await expect(page.getByText("待补证据")).toBeVisible();
  await expect(page.getByRole("heading", { name: "后端与索引联通" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "当前阶段：形成判断" })).toBeVisible();
  await expect(chatLink).toBeVisible();
  await expect(chatLink).toHaveAttribute("href", "/pages/chat");
  await expect(primaryNavigation.getByRole("link", { name: /^查询工作台/ })).toHaveAttribute("href", "/knowledge-query");
  await expect(primaryNavigation.getByRole("link", { name: /^疑点清单/ })).toHaveAttribute("href", "/findings");
  await expect(primaryNavigation.getByRole("link", { name: /^索引管理/ })).toHaveAttribute(
    "href",
    "/pages/index-admin"
  );
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
  await expect(page.getByRole("link", { name: "打开后端兼容页" })).toHaveAttribute(
    "href",
    "/pages/audit-findings"
  );
});

test("legacy guided check route no longer renders a plan placeholder", async ({ page }) => {
  await page.goto("/guided-check");

  await expect(page.getByRole("heading", { name: "AI 引导自查" })).toBeVisible();
  await expect(page.getByText(/Plan 03/)).toHaveCount(0);
  await expect(page.getByRole("link", { name: "打开对话审证" })).toHaveAttribute("href", "/pages/chat");
});
