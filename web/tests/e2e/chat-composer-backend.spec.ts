import { expect, test } from "@playwright/test";

test.describe("chat composer backend orchestration", () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem("medical-audit-authenticated", "authenticated");
      window.localStorage.setItem("medical-audit-current-role", "admin");
    });
  });

  test("selects model, source collection, agent, and attachment analysis", async ({ page }) => {
    await page.goto("/chat");

    await expect(page.getByRole("heading", { name: "AI，让审计更智能" })).toBeVisible();
    await expect(page.getByRole("combobox", { name: "选择模型" })).toBeVisible();
    await page.getByRole("combobox", { name: "选择模型" }).selectOption("deepseek-v4-pro");

    await page.getByRole("button", { name: /全部知识库/ }).click();
    await expect(page.getByRole("dialog", { name: "选择知识库" })).toBeVisible();
    await page.getByLabel(/法规政策/).check();
    await expect(page.getByRole("button", { name: /1 个知识库/ })).toBeVisible();

    const questionInput = page.getByLabel("输入相关问题以对话");
    await questionInput.fill("/");
    await expect(page.getByRole("dialog", { name: "选择智能体" })).toBeVisible();
    await page.getByRole("button", { name: /引用依据核验助手/ }).click();
    await expect(page.getByRole("button", { name: /引用依据核验助手/ })).toBeVisible();

    const attachmentRequestPromise = page.waitForRequest(
      (request) =>
        request.url().includes("/api/v1/chat/attachments/analyze") &&
        request.method() === "POST"
    );
    await page.locator('input[type="file"]').setInputFiles({
      name: "charges.csv",
      mimeType: "text/csv",
      buffer: Buffer.from("patient_id,charge_amount\nP001,120\nP002,80\n")
    });
    await attachmentRequestPromise;
    await expect(page.getByText(/模型：deepseek-v4-pro/)).toBeVisible();
    await expect(page.getByText(/本地验收模型回答/).first()).toBeVisible();

    const queryRequestPromise = page.waitForRequest(
      (request) => request.url().includes("/api/v1/query") && request.method() === "POST"
    );
    await questionInput.fill("医保基金审核依据是什么？");
    await page.getByRole("button", { name: "发送问题" }).click();
    const queryRequest = await queryRequestPromise;

    expect(queryRequest.postDataJSON()).toMatchObject({
      question: "医保基金审核依据是什么？",
      model: "deepseek-v4-pro",
      source_collections: ["medical-insurance-laws"],
      agent: "agent-citation-check"
    });
    await expect(page.getByText(/智能体调用已记录/)).toBeVisible();
    await expect(page.getByText(/本地验收模型回答/).last()).toBeVisible();
  });
});
