#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(new URL("../web/package.json", import.meta.url));
const { chromium } = require("@playwright/test");

const __filename = fileURLToPath(import.meta.url);
const repoRoot = path.resolve(path.dirname(__filename), "..");

const DEFAULT_PRODUCTION_BASE_URL = "https://audit.lute-tlz-dddd.top";
const DEFAULT_LOCAL_BASE_URL = "http://localhost:3032";
const stamp = new Date().toISOString().replace(/[-:]/g, "").replace(/\..+/, "Z");

const coreRoutes = [
  { route: "/login", title: "登录页", compare: false },
  { route: "/chat", title: "AI 对话", compare: false },
  { route: "/agents", title: "我的智能体", expectedHeading: "我的助手" },
  { route: "/agent-market", title: "智能体广场", expectedHeading: "发现审计智能体" },
  { route: "/knowledge-base", title: "知识库", expectedHeading: "知识库" },
  { route: "/documents", title: "文档检索", expectedHeading: "文档检索" },
  { route: "/analytics", title: "AI数据分析", expectedHeading: "AI数据分析" },
  { route: "/graph", title: "知识图谱", expectedHeading: "知识图谱" },
  { route: "/reports", title: "审计底稿/报告", expectedHeading: "底稿与报告" },
  { route: "/projects", title: "项目管理", expectedHeading: "项目管理" },
  { route: "/medical-audit", title: "医保审计", compare: false },
];

const legacyRoutes = [
  { route: "/", expectedLocalPath: "/chat", title: "旧首页入口" },
  { route: "/workspace", expectedLocalPath: "/chat", title: "旧工作台入口" },
  { route: "/findings", expectedLocalPath: "/medical-audit", title: "旧疑点入口" },
  { route: "/fund-compliance", expectedLocalPath: "/medical-audit", title: "旧基金合规入口" },
  { route: "/fund-compliance/review", expectedLocalPath: "/medical-audit", title: "旧基金合规复核入口" },
  { route: "/guided-check", expectedLocalPath: "/chat", title: "旧引导自查入口" },
  { route: "/knowledge-query", expectedLocalPath: "/documents", title: "旧知识查询入口" },
  { route: "/rules", expectedLocalPath: "/knowledge-base", title: "旧规则入口" },
  { route: "/remediation", expectedLocalPath: "/medical-audit", title: "旧整改入口" },
  { route: "/archive", expectedLocalPath: "/reports", title: "旧归档入口" },
];

const viewports = [
  { name: "desktop", width: 1440, height: 1000 },
  { name: "mobile", width: 390, height: 900 },
];

function parseArgs(argv) {
  const options = {
    productionBaseUrl: DEFAULT_PRODUCTION_BASE_URL,
    localBaseUrl: DEFAULT_LOCAL_BASE_URL,
    output: path.join("tmp", "outputs", `frontend-cutover-readonly-compare-${stamp}.json`),
    markdown: path.join("tmp", "outputs", `frontend-cutover-readonly-compare-${stamp}.md`),
    screenshotDir: path.join("tmp", "screenshots", `frontend-cutover-readonly-compare-${stamp}`),
    timeoutMs: 20_000,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    const next = argv[index + 1];
    if (arg === "--production-base-url" && next) {
      options.productionBaseUrl = next;
      index += 1;
    } else if (arg === "--local-base-url" && next) {
      options.localBaseUrl = next;
      index += 1;
    } else if (arg === "--output" && next) {
      options.output = next;
      index += 1;
    } else if (arg === "--markdown" && next) {
      options.markdown = next;
      index += 1;
    } else if (arg === "--screenshot-dir" && next) {
      options.screenshotDir = next;
      index += 1;
    } else if (arg === "--timeout-ms" && next) {
      options.timeoutMs = Number(next);
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
  console.log(`Run read-only browser comparison between production and the local refactored frontend.

Usage:
  node scripts/audit-frontend-cutover-readonly-compare.mjs [options]

Options:
  --production-base-url <url>  Default: ${DEFAULT_PRODUCTION_BASE_URL}
  --local-base-url <url>       Default: ${DEFAULT_LOCAL_BASE_URL}
  --output <path>              JSON report path
  --markdown <path>            Markdown report path
  --screenshot-dir <path>      Screenshot artifact directory
  --timeout-ms <number>        Default: 20000
`);
}

function repoPath(value) {
  return path.isAbsolute(value) ? value : path.join(repoRoot, value);
}

function normalizeUrl(baseUrl, route) {
  return new URL(route, baseUrl.endsWith("/") ? baseUrl : `${baseUrl}/`).toString();
}

function finalPath(url) {
  try {
    const parsed = new URL(url);
    return `${parsed.pathname}${parsed.search}`;
  } catch {
    return "";
  }
}

function compact(value, max = 160) {
  return String(value ?? "").replace(/\s+/g, " ").trim().slice(0, max);
}

function slug(value) {
  return compact(value)
    .replace(/[^a-zA-Z0-9\u4e00-\u9fa5]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 72) || "route";
}

async function launchBrowser() {
  try {
    return await chromium.launch({ headless: true, channel: "chrome" });
  } catch {
    return chromium.launch({ headless: true });
  }
}

async function collectSnapshot(page) {
  return page.evaluate(() => {
    const visible = (element) => {
      const rect = element.getBoundingClientRect();
      const style = window.getComputedStyle(element);
      return rect.width > 1 && rect.height > 1 && style.visibility !== "hidden" && style.display !== "none";
    };
    const textOf = (element) =>
      (element.getAttribute("aria-label") || element.getAttribute("placeholder") || element.textContent || "")
        .replace(/\s+/g, " ")
        .trim();
    const root = document.documentElement;
    const bodyText = (document.body?.innerText || "").replace(/\s+/g, " ").trim();
    const brokenImages = Array.from(document.querySelectorAll("img"))
      .filter((image) => image.naturalWidth === 0 || image.naturalHeight === 0)
      .map((image) => image.getAttribute("src") || "")
      .slice(0, 10);

    return {
      title: document.title,
      bodyTextSample: bodyText.slice(0, 1400),
      bodyTextLength: bodyText.length,
      headings: Array.from(document.querySelectorAll("h1,h2,h3"))
        .filter(visible)
        .map((element) => compactForBrowser(element.textContent, 120))
        .filter(Boolean)
        .slice(0, 24),
      navLinks: Array.from(document.querySelectorAll("nav a, aside a"))
        .filter(visible)
        .map((element) => ({
          text: compactForBrowser(textOf(element), 100),
          href: element.getAttribute("href") || "",
        }))
        .filter((item) => item.text || item.href)
        .slice(0, 40),
      controls: Array.from(document.querySelectorAll("button,input,textarea,select,[role='tab']"))
        .filter(visible)
        .map((element) => compactForBrowser(textOf(element), 100))
        .filter(Boolean)
        .slice(0, 80),
      brokenImages,
      scrollWidth: root.scrollWidth,
      clientWidth: root.clientWidth,
      horizontalOverflow: root.scrollWidth > root.clientWidth + 2,
    };

    function compactForBrowser(value, max) {
      return String(value || "").replace(/\s+/g, " ").trim().slice(0, max);
    }
  });
}

async function auditRoute({ browser, source, sourceBaseUrl, routeSpec, viewport, screenshotDir, timeoutMs }) {
  const context = await browser.newContext({
    viewport: { width: viewport.width, height: viewport.height },
    ignoreHTTPSErrors: true,
  });
  const page = await context.newPage();
  const consoleIssues = [];
  const requestIssues = [];
  page.setDefaultTimeout(timeoutMs);
  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type())) {
      consoleIssues.push(`${message.type()}: ${compact(message.text(), 240)}`);
    }
  });
  page.on("requestfailed", (request) => {
    requestIssues.push(`${request.failure()?.errorText || "request"} ${request.url()}`);
  });
  page.on("response", (response) => {
    const status = response.status();
    if (status >= 400) {
      requestIssues.push(`${status} ${response.url()}`);
    }
  });

  const target = normalizeUrl(sourceBaseUrl, routeSpec.route);
  const result = {
    source,
    viewport: viewport.name,
    route: routeSpec.route,
    title: routeSpec.title,
    targetUrl: target,
    finalUrl: "",
    finalPath: "",
    status: null,
    ok: false,
    navigationIssue: null,
    screenshot: "",
    consoleIssues: [],
    requestIssues: [],
    snapshot: null,
  };

  try {
    const response = await page.goto(target, { waitUntil: "domcontentloaded", timeout: timeoutMs });
    await page.waitForTimeout(750);
    result.status = response?.status() ?? null;
    result.finalUrl = page.url();
    result.finalPath = finalPath(page.url());
    result.snapshot = await collectSnapshot(page);
    result.ok = Boolean(result.status === null || result.status < 400);
  } catch (error) {
    result.navigationIssue = compact(error instanceof Error ? error.message : String(error), 400);
    result.finalUrl = page.url();
    result.finalPath = finalPath(page.url());
  }

  result.consoleIssues = consoleIssues.slice(0, 8);
  result.requestIssues = requestIssues.slice(0, 8);
  const screenshotPath = path.join(
    screenshotDir,
    source,
    viewport.name,
    `${slug(routeSpec.route === "/" ? "root" : routeSpec.route)}.png`,
  );
  await fs.mkdir(path.dirname(screenshotPath), { recursive: true });
  await page.screenshot({ path: screenshotPath, fullPage: true }).catch(() => {});
  result.screenshot = screenshotPath;
  await context.close();
  return result;
}

function buildFindings({ productionResults, localResults }) {
  const findings = [];
  const localByKey = new Map(localResults.map((item) => [`${item.viewport} ${item.route}`, item]));
  const productionByKey = new Map(productionResults.map((item) => [`${item.viewport} ${item.route}`, item]));
  const allRoutes = [...coreRoutes, ...legacyRoutes];

  for (const routeSpec of allRoutes) {
    for (const viewport of viewports) {
      const key = `${viewport.name} ${routeSpec.route}`;
      const local = localByKey.get(key);
      const production = productionByKey.get(key);
      if (!local) continue;

      if (!local.ok || local.navigationIssue) {
        findings.push({
          severity: "P0",
          route: routeSpec.route,
          viewport: viewport.name,
          type: "local-route-not-usable",
          detail: local.navigationIssue || `HTTP ${local.status}`,
        });
      }

      const localSnapshot = local.snapshot;
      if (localSnapshot?.horizontalOverflow) {
        findings.push({
          severity: "P1",
          route: routeSpec.route,
          viewport: viewport.name,
          type: "local-horizontal-overflow",
          detail: `scrollWidth ${localSnapshot.scrollWidth} > clientWidth ${localSnapshot.clientWidth}`,
        });
      }

      if (localSnapshot?.brokenImages?.length) {
        findings.push({
          severity: "P1",
          route: routeSpec.route,
          viewport: viewport.name,
          type: "local-broken-image",
          detail: localSnapshot.brokenImages.join(" | "),
        });
      }

      if (routeSpec.expectedHeading) {
        const hasHeading = localSnapshot?.headings?.some((heading) => heading === routeSpec.expectedHeading);
        if (!hasHeading) {
          findings.push({
            severity: "P1",
            route: routeSpec.route,
            viewport: viewport.name,
            type: "local-heading-contract-drift",
            detail: `Expected heading: ${routeSpec.expectedHeading}`,
          });
        }
      }

      if (routeSpec.expectedLocalPath && !local.finalPath.startsWith(routeSpec.expectedLocalPath)) {
        findings.push({
          severity: "P0",
          route: routeSpec.route,
          viewport: viewport.name,
          type: "local-legacy-redirect-drift",
          detail: `Expected ${routeSpec.expectedLocalPath}, got ${local.finalPath}`,
        });
      }

      if (!production) continue;
      if (!production.ok || production.navigationIssue) {
        findings.push({
          severity: "OBS",
          route: routeSpec.route,
          viewport: viewport.name,
          type: "production-route-observation",
          detail: production.navigationIssue || `HTTP ${production.status}`,
        });
      }

      if (routeSpec.expectedLocalPath && production.finalPath !== local.finalPath) {
        findings.push({
          severity: "OBS",
          route: routeSpec.route,
          viewport: viewport.name,
          type: "production-legacy-behavior-differs-from-cutover",
          detail: `Production ${production.finalPath}, local ${local.finalPath}`,
        });
      }

      const localHeadings = (local.snapshot?.headings || []).join(" / ");
      const productionHeadings = (production.snapshot?.headings || []).join(" / ");
      if (routeSpec.compare !== false && localHeadings && productionHeadings && localHeadings !== productionHeadings) {
        findings.push({
          severity: "OBS",
          route: routeSpec.route,
          viewport: viewport.name,
          type: "production-content-differs-from-cutover",
          detail: `Production headings: ${productionHeadings}; local headings: ${localHeadings}`,
        });
      }
    }
  }
  return findings;
}

async function auditSource({ browser, source, baseUrl, screenshotDir, timeoutMs }) {
  const results = [];
  for (const routeSpec of [...coreRoutes, ...legacyRoutes]) {
    for (const viewport of viewports) {
      results.push(
        await auditRoute({
          browser,
          source,
          sourceBaseUrl: baseUrl,
          routeSpec,
          viewport,
          screenshotDir,
          timeoutMs,
        }),
      );
    }
  }
  return results;
}

function summarize(results) {
  return {
    routes: results.length,
    navigationIssues: results.filter((item) => item.navigationIssue).length,
    httpIssues: results.filter((item) => item.status && item.status >= 400).length,
    horizontalOverflow: results.filter((item) => item.snapshot?.horizontalOverflow).length,
    brokenImageRoutes: results.filter((item) => item.snapshot?.brokenImages?.length).length,
  };
}

function toMarkdown(report) {
  const lines = [
    "---",
    "title: Frontend Cutover Readonly Compare",
    `date: ${report.created_at.slice(0, 10)}`,
    "project: medical_audit",
    "status: observed",
    "production_write: false",
    "provider_call: false",
    "backend_write: false",
    "---",
    "",
    "# Frontend Cutover Readonly Compare",
    "",
    "## Boundaries",
    "",
    "- production_write: `false`",
    "- provider_call: `false`",
    "- backend_write: `false`",
    "- deploy: `false`",
    "- interaction mode: navigation, screenshots, DOM/resource inspection only",
    "",
    "## Summary",
    "",
    `- Production base URL: ${report.production_base_url}`,
    `- Local base URL: ${report.local_base_url}`,
    `- Production routes checked: ${report.summary.production.routes}`,
    `- Local routes checked: ${report.summary.local.routes}`,
    `- Findings: ${report.findings.length}`,
    "",
    "## Findings",
    "",
  ];

  if (report.findings.length === 0) {
    lines.push("No findings recorded.");
  } else {
    lines.push("| Severity | Route | Viewport | Type | Detail |");
    lines.push("| --- | --- | --- | --- | --- |");
    for (const finding of report.findings.slice(0, 120)) {
      lines.push(
        `| ${finding.severity} | \`${finding.route}\` | ${finding.viewport} | ${finding.type} | ${compact(
          finding.detail,
          240,
        ).replaceAll("|", "\\|")} |`,
      );
    }
  }

  lines.push("", "## Source Summaries", "");
  lines.push("```json");
  lines.push(JSON.stringify(report.summary, null, 2));
  lines.push("```");
  return `${lines.join("\n")}\n`;
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const screenshotDir = repoPath(options.screenshotDir);
  await fs.mkdir(path.dirname(repoPath(options.output)), { recursive: true });
  await fs.mkdir(path.dirname(repoPath(options.markdown)), { recursive: true });
  await fs.mkdir(screenshotDir, { recursive: true });

  const browser = await launchBrowser();
  const productionResults = await auditSource({
    browser,
    source: "production",
    baseUrl: options.productionBaseUrl,
    screenshotDir,
    timeoutMs: options.timeoutMs,
  });
  const localResults = await auditSource({
    browser,
    source: "local",
    baseUrl: options.localBaseUrl,
    screenshotDir,
    timeoutMs: options.timeoutMs,
  });
  await browser.close();

  const report = {
    task: "frontend-cutover-readonly-compare",
    created_at: new Date().toISOString(),
    production_base_url: options.productionBaseUrl,
    local_base_url: options.localBaseUrl,
    boundaries: {
      production_write: false,
      provider_call: false,
      backend_write: false,
      deploy: false,
      interaction_mode: "navigation_screenshot_dom_resource_inspection_only",
    },
    summary: {
      production: summarize(productionResults),
      local: summarize(localResults),
    },
    findings: buildFindings({ productionResults, localResults }),
    production_results: productionResults,
    local_results: localResults,
  };

  const jsonPath = repoPath(options.output);
  const markdownPath = repoPath(options.markdown);
  await fs.writeFile(jsonPath, JSON.stringify(report, null, 2), "utf8");
  await fs.writeFile(markdownPath, toMarkdown(report), "utf8");
  console.log(
    JSON.stringify(
      {
        task: report.task,
        jsonPath,
        markdownPath,
        screenshotDir,
        summary: report.summary,
        findingCount: report.findings.length,
        boundaries: report.boundaries,
      },
      null,
      2,
    ),
  );
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
