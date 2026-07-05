import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { chromium } from "@playwright/test";

const localUrl = process.env.PLAYWRIGHT_BASE_URL ?? process.env.LOCAL_URL ?? "http://localhost:3030";
const stamp = new Date().toISOString().replace(/[-:]/g, "").replace(/\..+/, "Z");
const outDir = path.resolve(
  process.env.OUT_DIR ?? path.join("output", "playwright", `replica-interaction-smoke-${stamp}`)
);

async function settle(page) {
  await page.waitForLoadState("domcontentloaded", { timeout: 8000 }).catch(() => {});
  await page.waitForTimeout(250);
}

function cleanText(text) {
  return String(text ?? "").replace(/\s+/g, " ").trim().slice(0, 160);
}

function slug(text) {
  return cleanText(text)
    .replace(/[^a-zA-Z0-9\u4e00-\u9fa5]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 50) || "step";
}

async function pageState(page) {
  return page.evaluate(() => {
    function visible(el) {
      const rect = el.getBoundingClientRect();
      const style = window.getComputedStyle(el);
      return rect.width > 1 && rect.height > 1 && style.visibility !== "hidden" && style.display !== "none";
    }

    const headings = [...document.querySelectorAll("h1,h2,h3")]
      .filter(visible)
      .slice(0, 16)
      .map((el) => ({
        tag: el.tagName.toLowerCase(),
        text: (el.textContent || "").replace(/\s+/g, " ").trim().slice(0, 120)
      }))
      .filter((item) => item.text);

    const controls = [...document.querySelectorAll("a,button,input,textarea,select,[role='tab'],[role='dialog']")]
      .filter(visible)
      .slice(0, 120)
      .map((el) => ({
        tag: el.tagName.toLowerCase(),
        role: el.getAttribute("role") || "",
        text: (el.getAttribute("aria-label") || el.getAttribute("placeholder") || el.textContent || "")
          .replace(/\s+/g, " ")
          .trim()
          .slice(0, 120),
        href: el.tagName.toLowerCase() === "a" ? el.getAttribute("href") || "" : ""
      }))
      .filter((item) => item.text || item.href);

    return {
      url: location.href,
      title: document.title,
      headings,
      controls,
      visibleText: (document.body?.innerText || "").replace(/\s+/g, " ").trim().slice(0, 1600)
    };
  });
}

async function screenshot(page, name) {
  const file = path.join(outDir, `script-${String(name).padStart(2, "0")}.png`);
  await page.screenshot({ path: file, fullPage: true });
  return file;
}

async function runStep(page, steps, label, fn) {
  const stepNumber = steps.length + 1;
  const id = `${String(stepNumber).padStart(2, "0")}-${slug(label)}`;
  try {
    await fn();
    await settle(page);
    const shot = await screenshot(page, id);
    steps.push({ step: stepNumber, label, status: "ok", screenshot: shot, state: await pageState(page) });
  } catch (error) {
    const shot = await screenshot(page, `${id}-error`).catch(() => "");
    steps.push({
      step: stepNumber,
      label,
      status: "error",
      screenshot: shot,
      error: String(error?.message ?? error).slice(0, 500),
      state: await pageState(page).catch(() => null)
    });
  }
}

async function goto(page, route) {
  const targetUrl = new URL(route, localUrl).toString();
  let lastStatus = "";
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const response = await page.goto(targetUrl, { waitUntil: "domcontentloaded", timeout: 10000 });
    await settle(page);
    const status = response?.status() ?? 200;
    const bodyHasText = await page
      .locator("body")
      .evaluate((body) => (body.textContent || "").trim().length > 0)
      .catch(() => false);
    if (status < 500 && bodyHasText) return;
    lastStatus = `status=${status} bodyHasText=${bodyHasText}`;
    await page.waitForTimeout(750 * (attempt + 1));
  }
  throw new Error(`route did not become usable: ${route} ${lastStatus}`);
}

async function launchBrowser() {
  if (process.env.PLAYWRIGHT_USE_SYSTEM_CHROME === "1") {
    return chromium.launch({ headless: true, channel: "chrome" });
  }
  try {
    return await chromium.launch({ headless: true, channel: "chrome" });
  } catch {
    return chromium.launch({ headless: true });
  }
}

async function main() {
  await mkdir(outDir, { recursive: true });
  const browser = await launchBrowser();
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, ignoreHTTPSErrors: true });
  const page = await context.newPage();
  page.setDefaultTimeout(4000);
  const consoleMessages = [];
  const pageErrors = [];
  page.on("console", (msg) => {
    if (["error", "warning"].includes(msg.type())) consoleMessages.push(`${msg.type()}: ${cleanText(msg.text())}`);
  });
  page.on("pageerror", (error) => pageErrors.push(cleanText(error.message)));
  const steps = [];

  await runStep(page, steps, "登录页初始状态", async () => goto(page, "/login"));
  await runStep(page, steps, "登录页显示密码切换", async () => {
    await page.getByLabel("显示密码").click();
  });
  await runStep(page, steps, "登录提交进入AI对话", async () => {
    await page.getByPlaceholder("请输入账号或工号").fill("demo_user");
    await page.getByPlaceholder("请输入密码").fill("demo_password");
    await page.getByRole("button", { name: "登 录" }).click();
    await page.getByRole("dialog", { name: "初始密码安全提示" }).waitFor();
    await page.getByRole("button", { name: "稍后处理" }).click();
    await page.waitForURL(/\/chat$/, { timeout: 6000 });
  });

  const navItems = [
    ["AI 对话", "/chat"],
    ["我的智能体", "/agents"],
    ["智能体广场", "/agent-market"],
    ["知识库", "/knowledge-base"],
    ["文档检索", "/documents"],
    ["AI数据分析", "/analytics"],
    ["知识图谱", "/graph"],
    ["审计底稿/报告", "/reports"],
    ["项目管理", "/projects"],
    ["医保审计", "/medical-audit"]
  ];

  for (const [label, route] of navItems) {
    await runStep(page, steps, `侧栏跳转：${label}`, async () => {
      await goto(page, "/workspace");
      await page.getByLabel("主导航").getByRole("link", { name: label, exact: true }).click();
      await page.waitForURL(new RegExp(`${route.replace("/", "\\/")}$`), { timeout: 6000 });
    });
  }

  await runStep(page, steps, "侧栏收起与展开", async () => {
    await goto(page, "/documents");
    await page.getByRole("button", { name: "收起侧栏" }).click();
    await page.getByRole("button", { name: "展开侧栏" }).click();
  });

  await runStep(page, steps, "关闭当前页签", async () => {
    await goto(page, "/documents");
    await page.getByRole("button", { name: /^关闭.+页签$/ }).click();
  });

  await runStep(page, steps, "历史对话跳转", async () => {
    await goto(page, "/chat");
    await page.getByRole("link", { name: /打开历史对话/ }).first().click();
    await page.waitForURL(/\/chat\?history=/, { timeout: 6000 });
    await page.getByRole("heading", { name: "中标候选人名单表" }).waitFor();
    await page.getByText(/本地历史记录：已标出候选人排序/).waitFor();
  });

  await runStep(page, steps, "AI 对话发送本地预览", async () => {
    await goto(page, "/chat");
    await page.getByLabel("输入相关问题以对话").fill("请核验医保目录限制条件是否满足");
    await page.getByRole("button", { name: "发送问题" }).click();
  });

  await runStep(page, steps, "AI 对话上传附件门禁", async () => {
    await goto(page, "/chat");
    await page.getByRole("button", { name: "上传附件" }).click();
  });

  await runStep(page, steps, "智能体广场搜索与创建副本门禁", async () => {
    await goto(page, "/agent-market");
    await page.getByPlaceholder("搜索AI智能体").fill("医保");
    await page.getByRole("button", { name: "创建副本" }).first().click();
  });

  await runStep(page, steps, "我的智能体创建入口门禁", async () => {
    await goto(page, "/agents");
    await page.getByRole("button", { name: "+ 创建我的助手" }).click();
  });

  await runStep(page, steps, "知识库搜索查看与新建门禁", async () => {
    await goto(page, "/knowledge-base");
    await page.getByPlaceholder("搜索知识库").fill("医保");
    await page.getByRole("button", { name: "查看" }).first().click();
    await page.getByRole("button", { name: "+ 创建知识库" }).click();
  });

  await runStep(page, steps, "文档检索搜索标题筛选与清空历史", async () => {
    await goto(page, "/documents");
    await page.getByPlaceholder("劳动争议司法案件解释").fill("医保基金重复收费怎么取证");
    await page.getByRole("button", { name: "搜索", exact: true }).click();
    await page.getByLabel("仅标题").click();
    await page.getByRole("button", { name: "清空搜索历史" }).click();
  });

  await runStep(page, steps, "AI 数据分析选择文件并开始分析", async () => {
    await goto(page, "/analytics");
    await page.locator("input[type='file']").setInputFiles({
      name: "charge-sample.csv",
      mimeType: "text/csv",
      buffer: Buffer.from("a,b\n1,2\n")
    });
    await page.getByRole("button", { name: "绘制图表" }).click();
    await page.getByRole("button", { name: "开始分析" }).click();
  });

  await runStep(page, steps, "知识图谱筛选与新建门禁", async () => {
    await goto(page, "/graph");
    await page.getByRole("button", { name: "银行" }).click();
    await page.getByRole("button", { name: "新建图谱" }).click();
  });

  await runStep(page, steps, "底稿报告生成无选择与有选择", async () => {
    await goto(page, "/reports");
    await page.getByRole("button", { name: "一键生成底稿" }).click();
    await page.getByRole("checkbox").first().check();
    await page.getByRole("button", { name: "一键生成底稿" }).click();
  });

  await runStep(page, steps, "项目管理新增弹层取消与确认", async () => {
    await goto(page, "/projects");
    await page.getByRole("button", { name: "创建新项目" }).click({ force: true });
    await page.getByRole("dialog", { name: "新增项目" }).waitFor();
    await page.getByRole("button", { name: "取消" }).click();
    await page.getByRole("button", { name: "创建新项目" }).click({ force: true });
    await page.getByRole("dialog", { name: "新增项目" }).waitFor();
    await page.getByPlaceholder("请输入项目名称").fill("医保基金演示项目");
    await page.getByRole("button", { name: "确定" }).click();
  });

  await runStep(page, steps, "医保审计筛选详情AI抽屉与表单页签", async () => {
    await goto(page, "/medical-audit");
    await page.getByRole("button", { name: "DIP/DRG审计" }).click();
    await page.getByLabel("风险").selectOption("中风险");
    await page.getByRole("button", { name: /2025/ }).first().click();
    await page.getByRole("button", { name: "打开AI审计助手" }).click();
    await page.getByPlaceholder("询问当前疑点、复核意见或整改建议...").fill("请生成复核意见");
    await page.getByRole("button", { name: "发送" }).click();
    await page.getByRole("tab", { name: "费用汇总表" }).click();
    await page.getByRole("tab", { name: "分类汇总表" }).click();
    await page.getByRole("tab", { name: "就诊明细表" }).click();
  });

  await runStep(page, steps, "旧基金合规入口转入医保审计表单", async () => {
    await goto(page, "/fund-compliance");
    await page.waitForURL(/\/medical-audit$/, { timeout: 6000 });
    await page.getByRole("tab", { name: "费用汇总表" }).click();
    await page.getByRole("tab", { name: "分类汇总表" }).click();
    await page.getByRole("tab", { name: "就诊明细表" }).click();
    await page.getByRole("button", { name: "新建表单" }).click();
  });

  await runStep(page, steps, "旧入口重定向到重构页面", async () => {
    const redirects = [
      ["/rules", /\/knowledge-base$/],
      ["/remediation", /\/medical-audit$/],
      ["/archive", /\/reports$/],
      ["/findings", /\/medical-audit$/],
      ["/knowledge-query", /\/documents$/],
      ["/guided-check", /\/chat$/],
      ["/fund-compliance/review", /\/medical-audit$/]
    ];
    for (const [route, expected] of redirects) {
      await goto(page, route);
      await page.waitForURL(expected, { timeout: 6000 });
    }
  });

  await context.close();
  await browser.close();

  const failedSteps = steps.filter((step) => step.status !== "ok");
  const result = {
    localUrl,
    capturedAt: new Date().toISOString(),
    steps,
    consoleMessages: [...new Set(consoleMessages)].slice(0, 50),
    pageErrors: [...new Set(pageErrors)].slice(0, 50)
  };
  const jsonPath = path.join(outDir, "local-interaction-script.json");
  await writeFile(jsonPath, JSON.stringify(result, null, 2), "utf8");
  console.log(JSON.stringify({ jsonPath, outDir, steps: steps.length, failed: failedSteps.length }, null, 2));
  if (failedSteps.length > 0) {
    process.exitCode = 1;
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
