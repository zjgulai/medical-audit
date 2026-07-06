import { expect, test } from "@playwright/test";

test.describe("login surface contrast", () => {
  test("renders the hospital login hero with a dark readable surface", async ({ page }) => {
    await page.goto("/");

    const hero = page.locator(".audit-login-hero");
    await expect(hero).toBeVisible();
    await expect(hero.getByRole("heading", { name: "面向医院内审的医保审计工作台" })).toHaveCSS("color", "rgb(255, 255, 255)");

    const styles = await hero.evaluate((element) => {
      const computed = getComputedStyle(element);
      const before = getComputedStyle(element, "::before");
      const after = getComputedStyle(element, "::after");
      return {
        background: computed.backgroundImage,
        backgroundColor: computed.backgroundColor,
        beforeOpacity: before.opacity,
        afterBackground: after.backgroundImage
      };
    });

    expect(styles.background).toContain("rgb(9, 42, 89)");
    expect(styles.background).toContain("rgb(14, 85, 152)");
    expect(styles.backgroundColor).toBe("rgb(9, 42, 89)");
    expect(Number(styles.beforeOpacity)).toBeLessThanOrEqual(0.25);
    expect(styles.afterBackground).not.toContain("rgba(255, 255, 255, 0.2)");
  });
});
