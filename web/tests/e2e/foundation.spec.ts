import { expect, test } from "@playwright/test";

test("self-check OS foundation renders navigation and core modules", async ({ page }) => {
  await page.goto("/workspace");

  const primaryNavigation = page.getByRole("navigation", { name: "主导航" });
  const guidedCheckLink = primaryNavigation.getByRole("link", { name: /^AI 引导自查/ });

  await expect(page.getByRole("heading", { name: "医保基金使用合规专项自查" })).toBeVisible();
  await expect(page.getByText("待处理疑点")).toBeVisible();
  await expect(page.getByText("待补证据")).toBeVisible();
  await expect(page.getByRole("heading", { name: "后端与索引联通" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "当前阶段：形成判断" })).toBeVisible();
  await expect(guidedCheckLink).toBeVisible();
  await expect(guidedCheckLink).toHaveAttribute("href", "/guided-check");
  await expect(primaryNavigation.getByRole("link", { name: /^专题规则库/ })).toBeVisible();
});

test("guided check route is reachable", async ({ page }) => {
  await page.goto("/guided-check");

  await expect(page.getByRole("heading", { name: "AI 引导自查" })).toBeVisible();
  await expect(page.getByText("自查向导 + 多轮对话 + 证据侧栏")).toBeVisible();
});
