import { expect, test } from "@playwright/test";

test("self-check OS foundation renders navigation and core modules", async ({ page }) => {
  await page.goto("/workspace");

  const primaryNavigation = page.getByRole("navigation", { name: "主导航" });

  await expect(page.getByRole("heading", { name: "机构自查闭环总览" })).toBeVisible();
  await expect(primaryNavigation.getByRole("link", { name: /^AI 引导自查/ })).toBeVisible();
  await expect(primaryNavigation.getByRole("link", { name: /^专题规则库/ })).toBeVisible();
  await expect(page.getByText("AI 自查状态机")).toBeVisible();
});

test("guided check route is reachable", async ({ page }) => {
  await page.goto("/guided-check");

  await expect(page.getByRole("heading", { name: "AI 引导自查" })).toBeVisible();
  await expect(page.getByText("自查向导 + 多轮对话 + 证据侧栏")).toBeVisible();
});
