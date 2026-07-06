import { expect, test } from "@playwright/test";

test.describe("local acceptance fullstack proxy smoke", () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem("medical-audit-authenticated", "authenticated");
      window.localStorage.setItem("medical-audit-current-role", "admin");
    });
  });

  test("chat reaches local acceptance agents, source catalog, query and invocation APIs", async ({ page }) => {
    await page.goto("/chat");

    await expect(page.getByRole("heading", { name: "AI 问答" })).toBeVisible();
    await expect(page.getByText("已同步").first()).toBeVisible();
    const agentSelect = page.locator('select[name="agent"]');
    await expect(agentSelect).toBeVisible();
    await expect(agentSelect).toContainText("引用依据核验助手");
    await agentSelect.selectOption("agent-citation-check");
    await expect(page.getByRole("heading", { name: "引用依据核验助手" })).toBeVisible();

    await page.getByLabel("审计问题").fill("医保基金审核依据是什么？");
    await page.getByRole("button", { name: "提交问题" }).click();

    await expect(page.getByLabel("AI回答结果")).toBeVisible();
    await expect(page.getByText("本地验收回答")).toBeVisible();
    await expect(page.getByText("已记录调用")).toBeVisible();
    await expect(page.getByText("medical-insurance-laws").first()).toBeVisible();
  });

  test("documents reaches local acceptance catalog, permissions, uploads, history and query APIs", async ({ page }) => {
    await page.goto("/documents");

    await expect(page.getByRole("heading", { name: "文档依据检索" })).toBeVisible();
    await expect(page.getByText("法规政策").first()).toBeVisible();
    await expect(page.getByText("个人材料").first()).toBeVisible();

    await page.getByLabel("审计问题或文档关键词").fill("医保基金审核依据是什么？");
    await page.getByRole("button", { name: "执行检索" }).click();

    await expect(page.getByRole("heading", { name: "医保基金审核依据是什么？" })).toBeVisible();
    await expect(page.getByText("本地验收回答")).toBeVisible();
    await expect(page.getByText("1 条引用").first()).toBeVisible();
    await expect(page.getByText("医保基金审核依据").first()).toBeVisible();
  });

  test("knowledge query reaches local acceptance source catalog and query APIs", async ({ page }) => {
    await page.goto("/knowledge-query");

    await expect(page.getByRole("heading", { name: "引用优先的知识查询" })).toBeVisible();
    await expect(page.getByText("法规政策").first()).toBeVisible();

    await page.getByLabel("审计问题").fill("医保基金审核依据是什么？");
    await page.getByRole("button", { name: "执行查询" }).click();

    await expect(page.getByRole("heading", { name: "医保基金审核依据是什么？" })).toBeVisible();
    await expect(page.getByText("本地验收回答")).toBeVisible();
    await expect(page.getByText("1 条引用")).toBeVisible();
    await expect(page.getByText("query_log_index:").first()).toBeVisible();
  });

  test("agent marketplace installs a catalog agent and chat invokes it through local acceptance APIs", async ({ page }) => {
    await page.goto("/agent-market");

    await expect(page.getByRole("heading", { name: "审计助手库" })).toBeVisible();
    await page.getByLabel("搜索审计助手").fill("合同要素");
    await page.getByRole("button", { name: /合同风险核验/ }).first().click();

    await expect(page.getByRole("dialog", { name: "合同风险核验" })).toBeVisible();
    const installButton = page.getByRole("button", { name: "安装到我的智能体", exact: true });
    if ((await installButton.count()) > 0 && (await installButton.isEnabled())) {
      await installButton.click();
    }
    await expect(page.getByRole("button", { name: "已安装到我的智能体", exact: true })).toBeVisible();

    await page.getByRole("link", { name: "用此助手提问" }).click();
    await expect(page).toHaveURL(/\/chat\?agent=agent-custom-/);
    await expect(page.getByRole("heading", { name: "AI 问答" })).toBeVisible();
    await expect(page.getByText("合同风险核验").first()).toBeVisible();

    await page.getByLabel("审计问题").fill("医保基金审核依据是什么？");
    await page.getByRole("button", { name: "提交问题" }).click();

    await expect(page.getByLabel("AI回答结果")).toBeVisible();
    await expect(page.getByText("本地验收回答")).toBeVisible();
    await expect(page.getByText("已记录调用")).toBeVisible();
  });

  test("analytics uploads a CSV and renders local acceptance audit hints", async ({ page }) => {
    await page.goto("/analytics");

    await expect(page.getByRole("heading", { name: "等待上传表1数据文件" })).toBeVisible();
    await page.getByLabel("上传审计表格").setInputFiles({
      name: "charge-sample.csv",
      mimeType: "text/csv",
      buffer: Buffer.from(
        [
          "patient_id,visit_date,item_code,charge_amount,insurance_pay",
          "P001,2026-01-01,A100,120.00,80.00",
          "P001,2026-01-01,A100,120.00,80.00",
          "P002,2026-01-02,B200,,50.00"
        ].join("\n")
      )
    });

    await expect(page.getByRole("heading", { name: "charge-sample.csv" })).toBeVisible();
    await expect(page.getByText("数据质量提示")).toBeVisible();
    await expect(page.getByText("审计初步分析")).toBeVisible();
    await expect(page.getByText("金额/费用字段").first()).toBeVisible();
    await expect(page.getByText("发现 1 条完全重复行。")).toBeVisible();
    await expect(page.getByText("留存：已留存").first()).toBeVisible();
  });

  test("graph renders local acceptance relationship coverage and evidence nodes", async ({ page }) => {
    await page.goto("/graph");

    await expect(page.getByRole("heading", { name: "知识图谱入口" })).toBeVisible();
    await expect(page.getByText("后端已连接")).toBeVisible();
    await expect(page.getByRole("img", { name: "审计知识图谱静态关系预览" })).toBeVisible();
    await expect(page.getByText("医保基金使用合规专项图谱")).toBeVisible();
    await expect(page.getByText("节点覆盖")).toBeVisible();
    await expect(page.getByText("节点证据")).toBeVisible();

    const nodeCoverage = page.locator("section", { has: page.getByRole("heading", { name: "节点覆盖" }) });
    await expect(nodeCoverage.getByText("项目", { exact: true })).toBeVisible();
    await expect(nodeCoverage.getByText("知识库", { exact: true })).toBeVisible();
    await expect(nodeCoverage.getByText("文档", { exact: true })).toBeVisible();
    await expect(nodeCoverage.getByText("规则", { exact: true })).toBeVisible();
    await expect(nodeCoverage.getByText("疑点", { exact: true })).toBeVisible();
    await expect(nodeCoverage.getByText("复核", { exact: true })).toBeVisible();
    await expect(nodeCoverage.getByText("报告", { exact: true })).toBeVisible();
    await expect(nodeCoverage.getByText("整改", { exact: true })).toBeVisible();
    await expect(page.getByText("FINDING-F044EBD309B659DC").first()).toBeVisible();
    await expect(page.getByText("review-task-0007").first()).toBeVisible();
  });

  test("rules renders local acceptance sources, runs and release gates", async ({ page }) => {
    await page.goto("/rules");

    await expect(page.getByRole("heading", { name: "审计规则与依据总览" })).toBeVisible();
    await expect(page.getByText("后端已连接")).toBeVisible();
    await expect(page.getByText("可运行规则")).toBeVisible();
    await expect(page.getByText("待处理规则")).toBeVisible();
    await expect(page.getByRole("heading", { name: "规则清单" })).toBeVisible();
    await expect(page.getByText("CHARGE-RULE-001").first()).toBeVisible();
    await expect(page.getByText("CATALOG-RULE-014").first()).toBeVisible();
    await expect(page.getByRole("heading", { name: "最近运行" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "来源覆盖" })).toBeVisible();
    await expect(page.getByText("监管两库").first()).toBeVisible();
    await expect(page.getByRole("heading", { name: "发布门禁" })).toBeVisible();
    await expect(page.getByText("字段可运行")).toBeVisible();
    await expect(page.getByRole("link", { name: "查看依据库" })).toHaveAttribute("href", "/knowledge-base");
    await expect(
      page.locator("article").filter({ hasText: "CHARGE-RULE-001" }).getByRole("link", { name: "查看", exact: true })
    ).toHaveAttribute("href", "/findings?rule=CHARGE-RULE-001");
  });

  test("reports renders local acceptance gates, evidence and remediation", async ({ page }) => {
    await page.goto("/reports");

    await expect(page.getByRole("heading", { name: "底稿与报告" })).toBeVisible();
    await expect(page.getByText("后端驱动")).toBeVisible();
    await expect(page.getByText("已签发报告")).toBeVisible();
    await expect(page.getByText("门禁阻断").first()).toBeVisible();
    await expect(page.getByText("纳入疑点").first()).toBeVisible();
    await expect(page.getByRole("heading", { name: "报告记录" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "报告门禁预检" }).first()).toBeVisible();
    await expect(page.getByText("表1 医保费用汇总表").first()).toBeVisible();
    await expect(page.getByText("费用汇总风险底稿")).toBeVisible();
    await expect(page.getByText("底稿与负责人确认")).toBeVisible();
    await expect(page.getByText("附件登记与报告草稿")).toBeVisible();
    await expect(page.getByRole("heading", { name: "底稿证据来源" })).toBeVisible();
    await expect(page.getByText("workpaper-20260604-001")).toBeVisible();
    await expect(page.getByRole("heading", { name: "整改跟踪" })).toBeVisible();
    await expect(page.getByText("重复收费退费与流程复核")).toBeVisible();
    await expect(page.getByText("AUDIT-REPORT-20260611-001").first()).toBeVisible();
    await expect(page.getByRole("link", { name: "查看证据链" }).first()).toHaveAttribute("href", "/graph#graph-node-report");
  });

  test("projects reaches local acceptance project, member and finding APIs", async ({ page }) => {
    await page.goto("/projects");

    await expect(page.getByRole("heading", { name: "项目与成员" })).toBeVisible();
    await expect(page.getByText("项目已同步")).toBeVisible();
    await expect(page.getByText("成员已同步").first()).toBeVisible();
    await expect(page.getByRole("heading", { name: "专题审计看板" })).toBeVisible();
    await expect(page.getByText("默认统计")).toBeVisible();
    await expect(page.getByRole("heading", { name: "医保基金使用合规专项自查" }).first()).toBeVisible();
  });
});
