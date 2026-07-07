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

const DEFAULT_CONTRACT_PROFILE = "hardened";
const routeCheckProfiles = {
  legacy: [
    { route: "/workspace", requiredText: [/AI，让审计更智能/] },
    {
      route: "/fund-compliance",
      postLoadWaitMs: 5_000,
      requiredText: [/医保审计/, /智能审计 - 规则导航/],
    },
    {
      route: "/fund-compliance/review",
      interactions: [
        { role: "tab", name: "费用汇总表" },
      ],
      requiredText: [/智能审计 - 规则导航/, /费用汇总表/, /分类汇总表/, /就诊明细表/],
    },
    { route: "/chat", requiredText: [/AI，让审计更智能/, /AI 对话/], requiredControlText: [/输入相关问题以对话/] },
    {
      route: "/agents",
      requiredText: [/我的助手/, /模拟数据助手|厕所管护核验|定标合规核验/],
      requiredControlText: [/\+ 创建我的助手/, /查看详情/],
    },
    { route: "/agent-market", requiredText: [/发现审计智能体/, /招标流程核验|政策依据速查|凭证异常识别|纪要结构提取/] },
    {
      route: "/analytics",
      requiredText: [/AI数据分析/, /分析结果预览/, /开始分析|数据处理|生成底稿/i],
      requiredFileInputCount: 1,
    },
    {
      route: "/projects",
      requiredText: [/项目管理/, /创建新项目/],
      requiredControlText: [/创建新项目/, /成员管理/, /修改项目/],
    },
    { route: "/documents", requiredText: [/文档检索/, /AI检索AI\\+|检索结果/] },
    { route: "/knowledge-base", requiredText: [/知识库/, /知识库概览|法律法规库|审计员个人知识库/] },
    { route: "/graph", requiredText: [/知识图谱/, /新建图谱/] },
    { route: "/rules", requiredText: [/知识库/, /法规/, /审计规则|规则|发布门禁/] },
    { route: "/reports", requiredText: [/底稿与报告/, /历史生成记录/, /一键生成底稿/] },
    { route: "/remediation", postLoadWaitMs: 5_000, requiredText: [/医保审计/, /智能审计 - 规则导航/] },
    { route: "/archive", requiredText: [/底稿与报告/, /历史生成记录/, /历史记录/] },
    { route: "/guided-check", requiredText: [/AI，让审计更智能/] },
    { route: "/findings", postLoadWaitMs: 5_000, requiredText: [/医保审计/, /智能审计 - 规则导航/] },
    { route: "/knowledge-query", requiredText: [/文档检索/, /查询问题|检索结果/, /搜索历史/] },
    { route: "/pages/chat", requiredText: [/AI智能审计管理系统/, /AI 对话/, /检索后端/] },
    { route: "/pages/query", requiredText: [/医保审计知识查询|医保审核知识库查询/, /文档检索/] },
    { route: "/pages/review-tasks", requiredText: [/AI智能审计管理系统/, /审计底稿\/报告/] },
    { route: "/pages/index-admin", requiredText: [/索引管理/, /检索后端/] },
    { route: "/pages/audit-logs", requiredText: [/审计日志台/, /审计日志/] },
  ],
  hardened: [
    { route: "/workspace", requiredText: [/AI，让审计更智能/] },
    {
      route: "/fund-compliance",
      requiredText: [/医保基金使用合规/, /医保审计/],
      requiredTextAny: [[/复核表单/, /费用表单/, /归档包/]],
    },
    {
      route: "/fund-compliance/review",
      requiredText: [/医保基金复核表单/, /费用汇总表/, /分类汇总表|医保费用分类汇总表/, /就诊明细表|就诊费用明细表/],
    },
    { route: "/chat", requiredText: [/AI，让审计更智能/, /全部知识库|选择模型|发送问题|AI 对话/] },
    {
      route: "/agents",
      requiredText: [/我的助手|我的智能体/, /智能体/],
      requiredControlText: [/查看详情|创建/],
    },
    {
      route: "/agent-market",
      requiredText: [/发现审计智能体/, /详情/],
      requiredTextAny: [[/全部/, /财务收支审计/, /采购招标审计/, /工程审计/]],
    },
    {
      route: "/analytics",
      requiredText: [/AI数据分析/, /分析结果预览|数据质量|开始分析/],
      requiredFileInputCount: 1,
    },
    {
      route: "/projects",
      requiredText: [/项目管理/, /审计驾驶舱|总审计条数|医保基金使用合规专项自查/],
    },
    { route: "/documents", requiredText: [/文档检索/, /对话文档|检索结果|法律法规库|法规政策/] },
    { route: "/knowledge-base", requiredText: [/知识库分类|知识库/, /一级专题|可查询|知识库/] },
    { route: "/graph", requiredText: [/知识图谱/, /最小知识图谱方案|医疗审计知识工程|图谱/] },
    { route: "/rules", requiredText: [/知识库|规则|法规/] },
    { route: "/reports", requiredText: [/底稿与报告/, /历史生成记录/, /一键生成底稿/] },
    {
      route: "/remediation",
      postLoadWaitMs: 2_000,
      requiredText: [/医保审计/],
      requiredTextAny: [[/待处理/, /异常/, /疑点/, /规则/]],
    },
    { route: "/archive", requiredText: [/项目档案归档/, /归档包/, /签名链|归档策略|审计日志/] },
    { route: "/guided-check", requiredText: [/引导式核查/, /核查步骤/, /AI 审证问题|材料准备状态/] },
    {
      route: "/findings",
      postLoadWaitMs: 2_000,
      requiredText: [/医保审计/],
      requiredTextAny: [[/待处理/, /异常/, /疑点/, /规则/]],
    },
    { route: "/knowledge-query", requiredText: [/文档检索/, /对话文档|检索结果|搜索历史/] },
  ],
};
const contractProfiles = Object.keys(routeCheckProfiles);

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
    contractProfile: DEFAULT_CONTRACT_PROFILE,
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
    } else if (arg === "--contract-profile" && next) {
      options.contractProfile = next;
      index += 1;
    } else if (arg.startsWith("--contract-profile=")) {
      options.contractProfile = arg.split("=", 2)[1];
    } else if (arg === "--help") {
      printHelp();
      process.exit(0);
    } else {
      throw new Error(`Unknown or incomplete argument: ${arg}`);
    }
  }
  if (!contractProfiles.includes(options.contractProfile)) {
    throw new Error(`Unknown contract profile: ${options.contractProfile}. Expected one of: ${contractProfiles.join(", ")}`);
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
  --contract-profile <name> Acceptance contract profile: ${contractProfiles.join("|")} (default: ${DEFAULT_CONTRACT_PROFILE})
`);
}

function resolveRepoPath(value) {
  return path.isAbsolute(value) ? value : path.join(repoRoot, value);
}

function compactText(value) {
  return value.replace(/\s+/g, " ").trim();
}

function resetRegExp(pattern) {
  return new RegExp(pattern.source, pattern.flags.replace(/g|y/gi, ""));
}

function normalizeForMatch(value) {
  return compactText(value)
    .normalize("NFKC")
    .replace(/[\u200b\u00a0]/g, "")
    .replace(/[\-–—_]/g, "")
    .replace(/\s+/g, "")
    .trim();
}

function matchText(pattern, rawText) {
  const normalized = normalizeForMatch(rawText);
  const compacted = compactText(rawText);
  const normalizedPattern = resetRegExp(pattern);
  return normalizedPattern.test(compacted) || normalizedPattern.test(normalized);
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
        const compact = (value) => value.replace(/\s+/g, " ").trim();
        const elementClassName = (element) => {
          if (typeof element.className === "string") {
            return element.className;
          }
          return element.getAttribute("class") ?? "";
        };
        const selectorPart = (element) => {
          const tag = element.tagName.toLowerCase();
          const id = element.getAttribute("id");
          if (id) {
            return `${tag}#${id}`;
          }
          const className = elementClassName(element)
            .split(/\s+/)
            .filter(Boolean)
            .slice(0, 3)
            .join(".");
          const classPart = className ? `.${className}` : "";
          if (!element.parentElement) {
            return `${tag}${classPart}`;
          }
          const sameTagSiblings = Array.from(element.parentElement.children).filter((item) => item.tagName === element.tagName);
          const indexPart = sameTagSiblings.length > 1 ? `:nth-of-type(${sameTagSiblings.indexOf(element) + 1})` : "";
          return `${tag}${classPart}${indexPart}`;
        };
        const selectorPath = (element) => {
          const parts = [];
          let current = element;
          while (current && current !== document.body && current !== document.documentElement && parts.length < 5) {
            parts.unshift(selectorPart(current));
            current = current.parentElement;
          }
          return parts.join(" > ");
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
        const clientWidth = root.clientWidth;
        const overflowOffenders = Array.from(document.querySelectorAll("body *"))
          .filter((element) => element !== document.body && element !== document.documentElement && isVisible(element))
          .map((element) => {
            const rect = element.getBoundingClientRect();
            const overflowsRight = rect.right > clientWidth + 2;
            const overflowsLeft = rect.left < -2;
            const widerThanViewport = rect.width > clientWidth + 2;
            if (!overflowsRight && !overflowsLeft && !widerThanViewport) {
              return null;
            }
            return {
              tag: element.tagName.toLowerCase(),
              id: element.getAttribute("id") ?? "",
              className: elementClassName(element).slice(0, 160),
              role: element.getAttribute("role") ?? "",
              ariaLabel: element.getAttribute("aria-label") ?? "",
              selector: selectorPath(element),
              text: compact(element.textContent ?? "").slice(0, 160),
              rect: {
                left: Math.round(rect.left),
                right: Math.round(rect.right),
                width: Math.round(rect.width),
              },
            };
          })
          .filter(Boolean)
          .sort((left, right) => right.rect.right - left.rect.right || right.rect.width - left.rect.width)
          .slice(0, 10);
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
          clientWidth,
          horizontalOverflow: root.scrollWidth > clientWidth + 2,
          overflowOffenders,
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

async function waitForReadableBody(page, timeoutMs = 5_000) {
  await page
    .waitForFunction(
      () => {
        const text = document.body?.innerText?.replace(/\s+/g, " ").trim() ?? "";
        return text.length >= 80;
      },
      undefined,
      { timeout: timeoutMs },
    )
    .catch(() => {});
}

function serializePattern(pattern) {
  return {
    source: pattern.source,
    flags: pattern.flags.replace(/[gy]/g, ""),
  };
}

function serializeRouteContract(routeCheck) {
  return {
    requiredText: (routeCheck.requiredText ?? []).map(serializePattern),
    requiredControlText: (routeCheck.requiredControlText ?? []).map(serializePattern),
    requiredTextAny: (routeCheck.requiredTextAny ?? []).map((group) => group.map(serializePattern)),
  };
}

async function waitForRouteSemantics(page, routeCheck, timeoutMs = 6_000) {
  const contract = serializeRouteContract(routeCheck);
  const hasContract =
    contract.requiredText.length > 0 || contract.requiredControlText.length > 0 || contract.requiredTextAny.length > 0;
  if (!hasContract) {
    return;
  }
  await page
    .waitForFunction(
      ({ requiredText, requiredControlText, requiredTextAny }) => {
        const compactText = (value) => value.replace(/\s+/g, " ").trim();
        const normalizeForMatch = (value) =>
          compactText(value)
            .normalize("NFKC")
            .replace(/[\u200b\u00a0]/g, "")
            .replace(/[\-–—_]/g, "")
            .replace(/\s+/g, "")
            .trim();
        const matchText = (pattern, rawText) => {
          const compacted = compactText(rawText);
          const normalized = normalizeForMatch(rawText);
          const regexp = new RegExp(pattern.source, pattern.flags);
          return regexp.test(compacted) || regexp.test(normalized);
        };
        const isVisible = (element) => {
          const style = window.getComputedStyle(element);
          const rect = element.getBoundingClientRect();
          return style.visibility !== "hidden" && style.display !== "none" && rect.width > 0 && rect.height > 0;
        };
        const bodyText = document.body?.innerText ?? "";
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
          .filter(Boolean)
          .join(" ");
        return (
          requiredText.every((pattern) => matchText(pattern, bodyText)) &&
          requiredControlText.every((pattern) => matchText(pattern, controlText)) &&
          requiredTextAny.every((group) => group.some((pattern) => matchText(pattern, bodyText)))
        );
      },
      contract,
      { timeout: timeoutMs },
    )
    .catch(() => {});
}

async function waitForRouteReady(page, routeCheck) {
  if (routeCheck.postLoadWaitMs) {
    await page.waitForTimeout(routeCheck.postLoadWaitMs);
  } else {
    await waitForReadableBody(page, routeCheck.readyTimeoutMs ?? 5_000);
    await page.waitForTimeout(routeCheck.settleMs ?? 300);
  }
  await waitForRouteSemantics(page, routeCheck, routeCheck.semanticTimeoutMs ?? 6_000);
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
    issues.push(
      issue(
        "P1",
        "horizontal-overflow",
        `scrollWidth ${data.scrollWidth} > clientWidth ${data.clientWidth}; offenders ${data.overflowOffenders.length}`,
      ),
    );
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
    if (!matchText(pattern, data.bodyText)) {
      issues.push(issue("P1", "missing-required-text", String(pattern)));
    }
  }
  const combinedControlText = data.controlText.join(" ");
  for (const pattern of routeCheck.requiredControlText ?? []) {
    if (!matchText(pattern, combinedControlText)) {
      issues.push(issue("P1", "missing-control", String(pattern)));
    }
  }
  for (const patternGroup of routeCheck.requiredTextAny ?? []) {
    const matched = Array.isArray(patternGroup)
      ? patternGroup.some((pattern) => matchText(pattern, data.bodyText))
      : false;
    if (!matched) {
      const patterns = Array.isArray(patternGroup) ? patternGroup.map((pattern) => String(pattern)).join(" OR ") : String(patternGroup);
      issues.push(issue("P1", "missing-required-text-any", patterns));
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
  const routeChecks = routeCheckProfiles[options.contractProfile];
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
      for (const routeCheck of routeChecks) {
        const context = await browser.newContext({
          viewport: { width: viewport.width, height: viewport.height },
          extraHTTPHeaders: acceptanceHeaders,
        });
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
          await waitForRouteReady(page, routeCheck);
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
          finalUrl: page.url(),
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
          overflowOffenders: data.overflowOffenders,
          consoleErrors,
          failedRequests,
          interactionErrors,
          issues: classify({ status, error, consoleErrors, failedRequests, interactionErrors }, routeCheck, data),
        };
        const shouldCaptureScreenshot = (captureScreenshots && check.issues.length > 0) || check.horizontalOverflow;
        if (shouldCaptureScreenshot) {
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
        await context.close();
      }
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
    check.issues.filter((item) => item.severity === "P1").map((item) => ({
      route: check.route,
      viewport: check.viewport,
      ...item,
      ...(item.type === "horizontal-overflow"
        ? {
            finalUrl: check.finalUrl,
            screenshot: check.screenshot,
            overflowOffenders: check.overflowOffenders.slice(0, 3),
          }
        : {}),
    })),
  );
  const status = p0.length === 0 && p1.length === 0 && !apiCheckError ? "pass" : "fail";

  const report = {
    status,
    generated_at: new Date().toISOString(),
    base_url: baseUrl,
    contract_profile: options.contractProfile,
    summary: {
      route_count: routeChecks.length,
      check_count: checks.length,
      viewports: viewports.map((viewport) => viewport.name),
      api_checks: apiCheckResult || { error: apiCheckError },
      screenshot_capture: captureScreenshots,
      screenshot_policy: captureScreenshots ? "all_issues" : "horizontal_overflow_only",
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
