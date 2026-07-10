import { expect, test } from "@playwright/test";

test.describe("login surface contrast", () => {
  test("renders the configured compact login card without a dimming overlay", async ({ page }) => {
    await page.goto("/");

    const shell = page.locator(".audit-login-shell-compact");
    const card = page.locator(".audit-login-card-compact");
    await expect(shell).toBeVisible();
    await expect(card).toBeVisible();
    await expect(card.getByRole("heading", { name: "登录工作台" })).toBeVisible();
    await expect(card.getByText("AI审计一体化协作平台")).toBeVisible();
    await expect(card.getByRole("button", { name: "登录" })).toBeVisible();

    const styles = await shell.evaluate((element) => {
      const computed = getComputedStyle(element);
      return {
        background: computed.backgroundImage,
        backgroundColor: computed.backgroundColor,
        opacity: computed.opacity
      };
    });

    expect(styles.background).toContain("rgb(247, 250, 252)");
    expect(styles.opacity).toBe("1");
    await expect(card).toHaveCSS("background-color", "rgb(255, 255, 255)");
  });
});
