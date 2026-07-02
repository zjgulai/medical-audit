#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(new URL("../web/package.json", import.meta.url));
const { chromium } = require("@playwright/test");

const __filename = fileURLToPath(import.meta.url);
const repoRoot = path.resolve(path.dirname(__filename), "..");

const DEFAULT_BASE_URL = "https://audit.lute-tlz-dddd.top";
const DEFAULT_OUTPUT = "tmp/outputs/production-frontend-acceptance-latest.json";
const DEFAULT_SCREENSHOT_DIR = "tmp/screenshots/production-frontend-acceptance-latest";
const DEFAULT_TENANT_ID = "hospital-demo";
const DEFAULT_PROJECT_KEY = "SELF-CHECK-FUND-20260607";
const DEFAULT_ADMIN_USER_ID = "frontend-acceptance-admin";

const viewports = [
  { name: "desktop", width: 1440, height: 1100 },
  { name: "mobile", width: 390, height: 900 },
];

const routeChecks = [
  { route: "/workspace", requiredText: [/医保基金使用合规专项自查/, /今日工作台|项目审计链/] },
  {
    route: "/fund-compliance",
    requiredText: [/基金合规自查/, /进入审查/, /规则|审计口径|专题规则/],
  },
  {
    route: "/fund-compliance/review",
    interactions: [
      { role: "tab", name: "费用表单" },
      { text: "新建表单" },
    ],
    requiredText: [/专题审计工作台/, /三份模板与自建表单/, /表单名称/, /字段列表/],
    requiredControlText: [/创建/],
  },
  { route: "/chat", requiredText: [/AI 问答/, /依据范围/, /进入对话/] },
  {
    route: "/agents",
    requiredText: [/提示词型审计智能体/, /新增智能体/, /提示词|prompt/i],
    requiredControlText: [/如：目录限制核验助手/, /新增智能体/],
  },
  { route: "/agent-market", requiredText: [/审计助手库/, /搜索助手|财务收支|采购招标/] },
  {
    route: "/analytics",
    requiredText: [/费用表单分析/, /疑点清单|索引状态|上传/, /上传|表格|CSV|XLSX/i],
    requiredFileInputCount: 1,
  },
  {
    route: "/projects",
    requiredText: [/项目与成员/, /新增成员|添加成员/, /成员|member/i],
    requiredControlText: [/成员姓名/, /审计员业务专家信息科只读观察员/, /添加成员/],
  },
  { route: "/documents", requiredText: [/文档依据检索/, /法规政策|监管两库|医保目录|风险清单/, /检索|过滤|筛选/] },
  { route: "/knowledge-base", requiredText: [/知识库总览/, /个人审计材料库|系统医保审计知识库|公开法规政策库/] },
  { route: "/graph", requiredText: [/知识图谱入口/, /医保基金使用合规专项图谱|证据链关系/] },
  { route: "/rules", requiredText: [/审计规则与依据总览/, /CHARGE-RULE-001|规则清单|发布门禁/] },
  { route: "/reports", requiredText: [/底稿与报告/, /报告门禁预检|报告记录/] },
  { route: "/remediation", requiredText: [/整改事项与补证闭环/, /整改台账|补证请求/] },
  { route: "/archive", requiredText: [/项目档案与审计日志归档/, /项目档案包|审计日志治理策略/] },
  { route: "/guided-check", requiredText: [/AI 引导自查工作台/, /自查路径|AI 提问模板/] },
  { route: "/findings", requiredText: [/规则命中疑点工作台/, /源记录定位|计算过程|证据项/] },
  { route: "/knowledge-query", requiredText: [/引用优先的知识查询/, /等待查询|查询/, /引用|证据|检索/] },
  { route: "/pages/chat", requiredText: [/AI智能审计管理系统/, /AI 对话/, /检索后端/] },
  { route: "/pages/query", requiredText: [/医保审计知识查询|医保审核知识库查询/, /文档检索/] },
  { route: "/pages/review-tasks", requiredText: [/AI智能审计管理系统/, /审计底稿\/报告/] },
  { route: "/pages/index-admin", requiredText: [/索引管理/, /检索后端/] },
  { route: "/pages/audit-logs", requiredText: [/审计日志台/, /审计日志/] },
];

const placeholderPatterns = [
  /敬请期待/i,
  /coming soon/i,
  /\btodo\b/i,
  /开发中/i,
  /建设中/i,
  /计划中/i,
  /\bplanned\b/i,
  /\bplanning\b/i,
];

function parseArgs(argv) {
  const options = {
    baseUrl: DEFAULT_BASE_URL,
    output: DEFAULT_OUTPUT,
    screenshotDir: DEFAULT_SCREENSHOT_DIR,
    timeoutMs: 45_000,
    adminRole: "it-admin",
    adminApiKeyEnv: null,
  };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    const next = argv[index + 1];
    if (arg === "--base-url" && next) {
      options.baseUrl = next;
      index += 1;
    } else if (arg === "--output" && next) {
      options.output = next;
      index += 1;
    } else if (arg === "--screenshot-dir" && next) {
      options.screenshotDir = next;
      index += 1;
    } else if (arg === "--timeout-ms" && next) {
      options.timeoutMs = Number(next);
      index += 1;
    } else if (arg === "--admin-role" && next) {
      options.adminRole = next;
      index += 1;
    } else if (arg === "--admin-api-key-env" && next) {
      options.adminApiKeyEnv = next;
      index += 1;
    } else if (arg === "--help") {
      printHelp();
      process.exit(0);
    } else {
      throw new Error(`Unknown or incomplete argument: ${arg}`);
    }
  }
  return options;
}

function printHelp() {
  console.log(`Run read-only production frontend acceptance checks.

Usage:
  node scripts/run-production-frontend-acceptance.mjs [options]

Options:
  --base-url <url>          Default: ${DEFAULT_BASE_URL}
  --output <path>           Default: ${DEFAULT_OUTPUT}
  --screenshot-dir <path>   Default: ${DEFAULT_SCREENSHOT_DIR}
  --timeout-ms <number>     Default: 45000
  --admin-role <role>       Role for admin API checks (default: it-admin)
  --admin-api-key-env <name> Env var for admin API key (optional)
`);
}

function resolveRepoPath(value) {
  return path.isAbsolute(value) ? value : path.join(repoRoot, value);
}

function compactText(value) {
  return value.replace(/\s+/g, " ").trim();
}

function readOptionalEnv(name) {
  if (!name) {
    return null;
  }
  const value = process.env[name];
  if (!value) {
    return null;
  }
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function readBooleanEnv(name) {
  return ["1", "true", "yes"].includes((process.env[name] ?? "").trim().toLowerCase());
}

async function snapshot(page) {
  for (let attempt = 1; attempt <= 3; attempt += 1) {
    try {
      return await page.evaluate(() => {
        const isVisible = (element) => {
          const style = window.getComputedStyle(element);
          const rect = element.getBoundingClientRect();
          return style.visibility !== "hidden" && style.display !== "none" && rect.width > 0 && rect.height > 0;
        };
        const controlText = Array.from(document.querySelectorAll("input, textarea, select, button, a"))
          .filter(isVisible)
          .map((element) =>
            [
              element.textContent,
              element.getAttribute("aria-label"),
              element.getAttribute("placeholder"),
              element.getAttribute("name"),
            ]
              .filter(Boolean)
              .join(" ")
              .trim(),
          )
          .filter(Boolean);
        const root = document.documentElement;
        return {
          title: document.title,
          bodyText: document.body?.innerText ?? "",
          headings: Array.from(document.querySelectorAll("h1,h2,h3"))
            .filter(isVisible)
            .map((element) => element.textContent?.trim())
            .filter(Boolean),
          controlText,
          fileInputCount: document.querySelectorAll('input[type="file"]').length,
          scrollWidth: root.scrollWidth,
          clientWidth: root.clientWidth,
          horizontalOverflow: root.scrollWidth > root.clientWidth + 2,
        };
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      if (!message.includes("Execution context was destroyed") || attempt === 3) {
        throw error;
      }
      await page.waitForLoadState("domcontentloaded", { timeout: 5_000 }).catch(() => {});
      await page.waitForTimeout(500);
    }
  }
  throw new Error("snapshot failed");
}

async function applyInteractions(page, interactions = []) {
  for (const action of interactions) {
    const timeout = action.timeoutMs ?? 5_000;
    if (action.role) {
      await page.getByRole(action.role, { name: action.name, exact: action.exact ?? true }).click({ timeout });
    } else if (action.text) {
      await page.getByText(action.text, { exact: action.exact ?? true }).first().click({ timeout });
    } else if (action.selector) {
      await page.locator(action.selector).first().click({ timeout });
    } else {
      throw new Error(`Unsupported interaction: ${JSON.stringify(action)}`);
    }
    await page.waitForTimeout(action.waitMs ?? 500);
  }
}

function issue(severity, type, message) {
  return { severity, type, message };
}

function classify(check, routeCheck, data) {
  const issues = [];
  if (!check.status || check.status >= 400) {
    issues.push(issue("P0", "http-status", `HTTP ${check.status ?? "unknown"}`));
  }
  if (check.error) {
    issues.push(issue("P0", "navigation-error", check.error));
  }
  if (check.consoleErrors.length > 0) {
    issues.push(issue("P1", "console-error", check.consoleErrors.slice(0, 3).join(" | ")));
  }
  if (check.failedRequests.length > 0) {
    const sample = check.failedRequests
      .slice(0, 3)
      .map((failed) => `${failed.status ?? failed.error} ${failed.url}`)
      .join(" | ");
    issues.push(issue("P1", "failed-request", sample));
  }
  if (check.interactionErrors.length > 0) {
    issues.push(issue("P1", "interaction-error", check.interactionErrors.slice(0, 3).join(" | ")));
  }
  if (data.horizontalOverflow) {
    issues.push(issue("P1", "horizontal-overflow", `scrollWidth ${data.scrollWidth} > clientWidth ${data.clientWidth}`));
  }
  if (compactText(data.bodyText).length < 80) {
    issues.push(issue("P1", "thin-page", `body text length ${compactText(data.bodyText).length}`));
  }
  if (data.headings.length === 0) {
    issues.push(issue("P1", "missing-heading", "no visible heading found"));
  }
  for (const pattern of placeholderPatterns) {
    if (pattern.test(data.bodyText)) {
      issues.push(issue("P1", "placeholder-text", String(pattern)));
    }
  }
  for (const pattern of routeCheck.requiredText ?? []) {
    if (!pattern.test(data.bodyText)) {
      issues.push(issue("P1", "missing-required-text", String(pattern)));
    }
  }
  const combinedControlText = data.controlText.join(" ");
  for (const pattern of routeCheck.requiredControlText ?? []) {
    if (!pattern.test(combinedControlText)) {
      issues.push(issue("P1", "missing-control", String(pattern)));
    }
  }
  if (routeCheck.requiredFileInputCount && data.fileInputCount < routeCheck.requiredFileInputCount) {
    issues.push(issue("P1", "missing-file-input", `found ${data.fileInputCount}`));
  }
  return issues;
}

async function fetchWithTimeout(url, { headers = {}, timeoutMs }) {
  const controller = new AbortController();
  const timer = setTimeout(() => {
    controller.abort();
  }, timeoutMs);
  try {
    const response = await fetch(url, {
      method: "GET",
      headers,
      signal: controller.signal,
    });
    const bodyText = await response.text();
    let body = null;
    try {
      body = JSON.parse(bodyText);
    } catch {
      body = null;
    }
    return {
      status: response.status,
      body,
      bodyText,
      contentType: response.headers.get("content-type") ?? "unknown",
      location: response.headers.get("location") ?? null,
    };
  } finally {
    clearTimeout(timer);
  }
}

async function checkAuditLogApiPermissions({ baseUrl, adminRole, adminApiKey, timeoutMs }) {
  const checks = {};
  const endpoints = [
    { path: "/audit/logs", requireItems: true },
    { path: "/audit/logs/export", requireItems: false },
  ];

  for (const item of endpoints) {
    const denied = await fetchWithTimeout(`${baseUrl}${item.path}`, {
      timeoutMs,
      headers: { Accept: "application/json" },
    });
    const allowed = await fetchWithTimeout(`${baseUrl}${item.path}`, {
      timeoutMs,
      headers: {
        Accept: "application/json",
        "X-User-Id": DEFAULT_ADMIN_USER_ID,
        "X-Role": adminRole,
        "X-Project-Key": DEFAULT_PROJECT_KEY,
        "X-Tenant-Id": DEFAULT_TENANT_ID,
        ...(adminApiKey ? { "X-API-Key": adminApiKey } : {}),
      },
    });

    if (item.requireItems && !Array.isArray(allowed.body?.items)) {
      throw new Error(`${item.path} should return JSON with items`);
    }

    checks[item.path] = {
      denied_status: denied.status,
      denied_content_type: denied.contentType,
      allowed_status: allowed.status,
      allowed_content_type: allowed.contentType,
      denied_body_sample: denied.bodyText.slice(0, 220),
      allowed_body_sample: allowed.bodyText.slice(0, 220),
    };

    if (![401, 403].includes(denied.status)) {
      throw new Error(`${item.path} should return 401/403 without role`);
    }
    if (allowed.status !== 200) {
      throw new Error(`${item.path} should return 200 with role`);
    }
  }

  return checks;
}

async function run() {
  const options = parseArgs(process.argv.slice(2));
  const baseUrl = options.baseUrl.replace(/\/+$/, "");
  const outputPath = resolveRepoPath(options.output);
  const screenshotDir = resolveRepoPath(options.screenshotDir);
  const adminApiKey = readOptionalEnv(options.adminApiKeyEnv);
  const adminRole = options.adminRole || "it-admin";
  const acceptanceHeaders = {
    "X-User-Id": DEFAULT_ADMIN_USER_ID,
    "X-Role": adminRole,
    "X-Project-Key": DEFAULT_PROJECT_KEY,
    "X-Tenant-Id": DEFAULT_TENANT_ID,
  };
  const captureScreenshots = readBooleanEnv("MEDICAL_AUDIT_FRONTEND_ACCEPTANCE_SCREENSHOTS");
  let apiCheckResult = null;
  let apiCheckError = null;
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.mkdirSync(screenshotDir, { recursive: true });

  const browser = await chromium.launch({
    headless: true,
    args: ["--no-proxy-server", "--proxy-server=direct://", "--proxy-bypass-list=*"],
  });
  const checks = [];
  try {
    for (const viewport of viewports) {
      const context = await browser.newContext({
        viewport: { width: viewport.width, height: viewport.height },
        extraHTTPHeaders: acceptanceHeaders,
      });
      for (const routeCheck of routeChecks) {
        const page = await context.newPage();
        const consoleErrors = [];
        const failedRequests = [];
        const interactionErrors = [];
        page.on("console", (message) => {
          if (message.type() === "error") {
            consoleErrors.push(message.text());
          }
        });
        page.on("requestfailed", (request) => {
          failedRequests.push({ url: request.url(), error: request.failure()?.errorText ?? "requestfailed" });
        });
        page.on("response", (response) => {
          const url = response.url();
          if (response.status() >= 400 && url.startsWith(baseUrl)) {
            failedRequests.push({ url, status: response.status() });
          }
        });

        let status = null;
        let error = null;
        const url = `${baseUrl}${routeCheck.route}`;
        try {
          const response = await page.goto(url, { waitUntil: "domcontentloaded", timeout: options.timeoutMs });
          status = response?.status() ?? null;
          await page.waitForTimeout(1_200);
          await applyInteractions(page, routeCheck.interactions);
        } catch (caught) {
          const message = caught instanceof Error ? caught.message : String(caught);
          if (status === null) {
            error = message;
          } else {
            interactionErrors.push(message);
          }
        }
        const data = await snapshot(page);
        const check = {
          route: routeCheck.route,
          viewport: viewport.name,
          url,
          status,
          error,
          title: data.title,
          headings: data.headings.slice(0, 8),
          bodyTextLength: compactText(data.bodyText).length,
          bodySample: compactText(data.bodyText).slice(0, 320),
          fileInputCount: data.fileInputCount,
          scrollWidth: data.scrollWidth,
          clientWidth: data.clientWidth,
          horizontalOverflow: data.horizontalOverflow,
          consoleErrors,
          failedRequests,
          interactionErrors,
          issues: classify({ status, error, consoleErrors, failedRequests, interactionErrors }, routeCheck, data),
        };
        if (captureScreenshots && check.issues.length > 0) {
          const safeRoute = routeCheck.route.replaceAll("/", "_").replace(/^_/, "") || "root";
          const screenshotPath = path.join(screenshotDir, `${viewport.name}-${safeRoute}.png`);
          try {
            await page.screenshot({ path: screenshotPath, fullPage: false, timeout: 10_000 });
            check.screenshot = screenshotPath;
          } catch (caught) {
            check.screenshot_error = caught instanceof Error ? caught.message : String(caught);
          }
        }
        checks.push(check);
        console.error(
          JSON.stringify({
            route: routeCheck.route,
            viewport: viewport.name,
            status,
            issue_count: check.issues.length,
          }),
        );
        await page.close();
      }
      await context.close();
    }
    try {
      apiCheckResult = await checkAuditLogApiPermissions({
        baseUrl,
        adminRole,
        adminApiKey,
        timeoutMs: options.timeoutMs,
      });
    } catch (error) {
      apiCheckError = error instanceof Error ? error.message : String(error);
    }
  } finally {
    await browser.close();
  }

  const p0 = checks.flatMap((check) =>
    check.issues.filter((item) => item.severity === "P0").map((item) => ({ route: check.route, viewport: check.viewport, ...item })),
  );
  const p1 = checks.flatMap((check) =>
    check.issues.filter((item) => item.severity === "P1").map((item) => ({ route: check.route, viewport: check.viewport, ...item })),
  );
  const status = p0.length === 0 && p1.length === 0 && !apiCheckError ? "pass" : "fail";

  const report = {
    status,
    generated_at: new Date().toISOString(),
    base_url: baseUrl,
    summary: {
      route_count: routeChecks.length,
      check_count: checks.length,
      viewports: viewports.map((viewport) => viewport.name),
      api_checks: apiCheckResult || { error: apiCheckError },
      screenshot_capture: captureScreenshots,
      p0,
      p1,
    },
    checks,
  };
  fs.writeFileSync(outputPath, JSON.stringify(report, null, 2));
  console.log(JSON.stringify({ status: report.status, output: outputPath, p0_count: p0.length, p1_count: p1.length }, null, 2));
  return report.status === "pass" ? 0 : 2;
}

run()
  .then((code) => {
    process.exitCode = code;
  })
  .catch((error) => {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 2;
  });
