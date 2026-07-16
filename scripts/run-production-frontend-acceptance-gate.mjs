#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import {
  aliasRouteChecks,
  finalPath,
  routeCheckProfiles,
  viewports as acceptanceViewports,
} from "./run-production-frontend-acceptance.mjs";

const __filename = fileURLToPath(import.meta.url);
const repoRoot = path.resolve(path.dirname(__filename), "..");

const DEFAULT_BASE_URL = "https://audit.lute-tlz-dddd.top";
const PRODUCTION_HOST = "audit.lute-tlz-dddd.top";
const DEFAULT_OUTPUT = "tmp/outputs/production-frontend-acceptance-latest.json";
const DEFAULT_SCREENSHOT_DIR = "tmp/screenshots/production-frontend-acceptance-latest";

function parseArgs(argv) {
  const options = {
    baseUrl: DEFAULT_BASE_URL,
    output: DEFAULT_OUTPUT,
    screenshotDir: DEFAULT_SCREENSHOT_DIR,
    timeoutMs: null,
    adminRole: "it-admin",
    adminApiKeyEnv: null,
    contractProfile: "hardened",
    allowAuditLogWrites: false,
    confirmProductionWrite: null,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    const next = argv[index + 1];
    if (arg === "--") {
      continue;
    } else if (arg === "--base-url" && next) {
      options.baseUrl = next;
      index += 1;
    } else if (arg === "--output" && next) {
      options.output = next;
      index += 1;
    } else if (arg === "--screenshot-dir" && next) {
      options.screenshotDir = next;
      index += 1;
    } else if (arg === "--timeout-ms" && next) {
      options.timeoutMs = next;
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
    } else if (arg === "--allow-audit-log-writes") {
      options.allowAuditLogWrites = true;
    } else if (arg === "--confirm-production-write" && next) {
      options.confirmProductionWrite = next;
      index += 1;
    } else if (arg.startsWith("--confirm-production-write=")) {
      options.confirmProductionWrite = arg.split("=", 2)[1];
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
  console.log(`Run the production frontend acceptance gate.

Usage:
  node scripts/run-production-frontend-acceptance-gate.mjs [options]

Options:
  --base-url <url>          Default: ${DEFAULT_BASE_URL}
  --output <path>           Default: ${DEFAULT_OUTPUT}
  --screenshot-dir <path>   Default: ${DEFAULT_SCREENSHOT_DIR}
  --timeout-ms <number>     Passed through to the acceptance runner.
  --admin-role <role>       Default: it-admin
  --admin-api-key-env <name> Optional env var containing admin API key.
  --contract-profile <name> Passed through to the acceptance runner (default: hardened).
  --allow-audit-log-writes Authorize audit-log-only writes made by the acceptance flow.
  --confirm-production-write <host>
                            Required with --allow-audit-log-writes for every target;
                            must equal ${PRODUCTION_HOST}.
`);
}

function validateSideEffectAuthorization(options) {
  try {
    new URL(options.baseUrl);
  } catch {
    throw new Error(`Invalid --base-url: ${options.baseUrl}`);
  }

  if (!options.allowAuditLogWrites) {
    throw new Error(
      "Frontend acceptance gate fails closed by default because the full flow can write audit-log records. " +
        "Use --allow-audit-log-writes and " +
        `--confirm-production-write ${PRODUCTION_HOST}.`,
    );
  }
  if (options.confirmProductionWrite !== PRODUCTION_HOST) {
    throw new Error(
      `Audit-log writes require --confirm-production-write ${PRODUCTION_HOST} for every target.`,
    );
  }
}

function resolveRepoPath(value) {
  return path.isAbsolute(value) ? value : path.join(repoRoot, value);
}

function runAcceptance(options) {
  const runner = path.join(repoRoot, "scripts/run-production-frontend-acceptance.mjs");
  const args = [
    runner,
    "--base-url",
    options.baseUrl,
    "--output",
    options.output,
    "--screenshot-dir",
    options.screenshotDir,
    "--admin-role",
    options.adminRole,
    "--contract-profile",
    options.contractProfile,
  ];
  if (options.timeoutMs) {
    args.push("--timeout-ms", options.timeoutMs);
  }
  if (options.adminApiKeyEnv) {
    args.push("--admin-api-key-env", options.adminApiKeyEnv);
  }
  if (options.allowAuditLogWrites) {
    args.push("--allow-audit-log-writes");
  }
  if (options.confirmProductionWrite) {
    args.push("--confirm-production-write", options.confirmProductionWrite);
  }

  const result = spawnSync(process.execPath, args, {
    cwd: repoRoot,
    env: process.env,
    stdio: "inherit",
  });

  if (result.status !== 0) {
    process.exit(result.status ?? 2);
  }
}

function readReport(output) {
  const outputPath = resolveRepoPath(output);
  return JSON.parse(fs.readFileSync(outputPath, "utf8"));
}

function requireStatus(condition, message, details = {}) {
  if (!condition) {
    console.error(
      JSON.stringify(
        {
          status: "fail",
          message,
          details,
        },
        null,
        2,
      ),
    );
    process.exit(2);
  }
}

function isNonNegativeInteger(value) {
  return Number.isInteger(value) && value >= 0;
}

const PNG_SIGNATURE = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);

function hasValidPngScreenshot(value) {
  if (typeof value !== "string" || value.trim().length === 0 || path.extname(value).toLowerCase() !== ".png") {
    return false;
  }
  let descriptor = null;
  try {
    const stats = fs.statSync(value);
    if (!stats.isFile() || stats.size < PNG_SIGNATURE.length) {
      return false;
    }
    descriptor = fs.openSync(value, "r");
    const signature = Buffer.alloc(PNG_SIGNATURE.length);
    const bytesRead = fs.readSync(descriptor, signature, 0, signature.length, 0);
    return bytesRead === PNG_SIGNATURE.length && signature.equals(PNG_SIGNATURE);
  } catch {
    return false;
  } finally {
    if (descriptor !== null) {
      fs.closeSync(descriptor);
    }
  }
}

function hasCompleteRouteEvidence(
  check,
  {
    expectedPath = null,
    expectedInputSearch = null,
    expectedSearch = null,
    requirePathIdentity = false,
    requireSearchIdentity = false,
    requireScreenshot = false,
  } = {},
) {
  const observedPath = typeof check?.finalUrl === "string" ? finalPath(check.finalUrl) : null;
  return (
    typeof check?.route === "string" &&
    typeof check?.viewport === "string" &&
    (!requirePathIdentity ||
      (typeof check.expectedPath === "string" &&
        check.expectedPath === expectedPath &&
        typeof check.finalPath === "string" &&
        check.finalPath === expectedPath &&
        observedPath === expectedPath)) &&
    (!requireSearchIdentity ||
      (typeof check.inputSearch === "string" &&
        check.inputSearch === expectedInputSearch &&
        typeof check.expectedSearch === "string" &&
        check.expectedSearch === expectedSearch &&
        typeof check.finalSearch === "string" &&
        check.finalSearch === expectedSearch)) &&
    (!requireScreenshot || hasValidPngScreenshot(check.screenshot)) &&
    Number.isInteger(check.status) &&
    check.status >= 200 &&
    check.status < 400 &&
    check.navigationError === false &&
    Number.isInteger(check.headingCount) &&
    check.headingCount > 0 &&
    Number.isInteger(check.bodyTextLength) &&
    check.bodyTextLength >= 80 &&
    isNonNegativeInteger(check.fileInputCount) &&
    isNonNegativeInteger(check.scrollWidth) &&
    isNonNegativeInteger(check.clientWidth) &&
    check.horizontalOverflow === false &&
    Array.isArray(check.overflowOffenders) &&
    check.consoleErrorCount === 0 &&
    check.failedRequestCount === 0 &&
    Array.isArray(check.failedRequests) &&
    check.failedRequests.length === 0 &&
    check.interactionErrorCount === 0 &&
    Array.isArray(check.issues) &&
    check.issues.length === 0
  );
}

function assertGate(report) {
  const summary = report.summary ?? {};
  const apiChecks = summary.api_checks ?? {};
  const auditLogs = apiChecks["/audit/logs"] ?? {};
  const auditLogExports = apiChecks["/audit/logs/export"] ?? {};
  const executedApiProbes = Array.isArray(summary.executed_api_probes) ? summary.executed_api_probes : [];
  const skippedApiProbes = Array.isArray(summary.skipped_api_probes) ? summary.skipped_api_probes : [];
  const skippedRoutes = Array.isArray(summary.skipped_routes) ? summary.skipped_routes : [];
  const reportViewports = Array.isArray(summary.viewports) ? summary.viewports : [];
  const routeChecks = Array.isArray(report.checks) ? report.checks : [];
  const reportAliasChecks = Array.isArray(report.alias_checks) ? report.alias_checks : [];
  const routeViewportKeys = new Set(
    routeChecks
      .filter((check) => typeof check?.route === "string" && typeof check?.viewport === "string")
      .map((check) => `${check.route}:${check.viewport}`),
  );
  const aliasRouteViewportKeys = new Set(
    reportAliasChecks
      .filter((check) => typeof check?.route === "string" && typeof check?.viewport === "string")
      .map((check) => `${check.route}:${check.viewport}`),
  );
  const expectedRouteChecks = routeCheckProfiles[report.contract_profile];
  const expectedRoutes = Array.isArray(expectedRouteChecks)
    ? expectedRouteChecks.map((check) => check.route)
    : [];
  const expectedRoutePaths = new Map(
    Array.isArray(expectedRouteChecks)
      ? expectedRouteChecks.map((check) => [check.route, check.expectedPath ?? null])
      : [],
  );
  const expectedAliasRouteChecks = report.contract_profile === "hardened" ? aliasRouteChecks : [];
  const expectedAliasRoutes = expectedAliasRouteChecks.map((check) => check.route);
  const expectedAliasPaths = new Map(
    expectedAliasRouteChecks.map((check) => [check.route, check.expectedPath]),
  );
  const expectedAliasInputSearches = new Map(
    expectedAliasRouteChecks.map((check) => [check.route, check.inputSearch]),
  );
  const expectedAliasSearches = new Map(
    expectedAliasRouteChecks.map((check) => [check.route, check.expectedSearch]),
  );
  const expectedViewports = acceptanceViewports.map((viewport) => viewport.name);
  const expectedRouteViewportKeys = new Set(
    expectedRoutes.flatMap((route) =>
      expectedViewports.map((viewport) => `${route}:${viewport}`),
    ),
  );
  const expectedAliasRouteViewportKeys = new Set(
    expectedAliasRoutes.flatMap((route) =>
      expectedViewports.map((viewport) => `${route}:${viewport}`),
    ),
  );
  const requirePathIdentity = report.contract_profile === "hardened";
  const requireIndependentScreenshot =
    summary.screenshot_capture === true && summary.screenshot_policy === "all";
  const incompleteRouteChecks = routeChecks
    .filter(
      (check) =>
        !hasCompleteRouteEvidence(check, {
          expectedPath: expectedRoutePaths.get(check?.route),
          requirePathIdentity: requirePathIdentity && expectedRoutePaths.has(check?.route),
          requireScreenshot: requireIndependentScreenshot,
        }),
    )
    .map((check) => ({ route: check?.route ?? null, viewport: check?.viewport ?? null }));
  const incompleteAliasChecks = reportAliasChecks
    .filter(
      (check) =>
        !hasCompleteRouteEvidence(check, {
          expectedPath: expectedAliasPaths.get(check?.route),
          expectedInputSearch: expectedAliasInputSearches.get(check?.route),
          expectedSearch: expectedAliasSearches.get(check?.route),
          requirePathIdentity: expectedAliasPaths.has(check?.route),
          requireSearchIdentity: expectedAliasSearches.has(check?.route),
          requireScreenshot: false,
        }),
    )
    .map((check) => ({ route: check?.route ?? null, viewport: check?.viewport ?? null }));
  const allRouteChecks = [...routeChecks, ...reportAliasChecks];
  const routeP0 = allRouteChecks.flatMap((check) =>
    Array.isArray(check?.issues)
      ? check.issues.filter((item) => item?.severity === "P0")
      : [],
  );
  const routeP1 = allRouteChecks.flatMap((check) =>
    Array.isArray(check?.issues)
      ? check.issues.filter((item) => item?.severity === "P1")
      : [],
  );
  const p0 = Array.isArray(summary.p0) ? summary.p0 : [];
  const p1 = Array.isArray(summary.p1) ? summary.p1 : [];
  const expectedApiProbes = [
    "/audit/logs:anonymous",
    "/audit/logs:missing-tenant",
    "/audit/logs:allowed",
    "/audit/logs/export:anonymous",
    "/audit/logs/export:missing-tenant",
    "/audit/logs/export:allowed",
  ];

  requireStatus(report.status === "pass", "frontend acceptance report is not pass", {
    status: report.status,
  });
  requireStatus(p0.length === 0 && p1.length === 0, "frontend acceptance found P0/P1 issues", {
    p0_count: p0.length,
    p1_count: p1.length,
  });
  requireStatus(
    report.side_effect_mode === "audit-log-write-enabled" &&
      report.production_side_effect === "audit-log-only" &&
      report.database_write === "audit-log-only" &&
      report.audit_log_write_expected === true,
    "frontend acceptance side-effect contract is inconsistent",
    {
      side_effect_mode: report.side_effect_mode,
      production_side_effect: report.production_side_effect,
      database_write: report.database_write,
      audit_log_write_expected: report.audit_log_write_expected,
    },
  );
  requireStatus(
    (summary.screenshot_capture === false && summary.screenshot_policy === "disabled") ||
      (summary.screenshot_capture === true && ["all", "issues"].includes(summary.screenshot_policy)),
    "frontend acceptance screenshot contract is inconsistent",
    {
      screenshot_capture: summary.screenshot_capture,
      screenshot_policy: summary.screenshot_policy,
    },
  );
  requireStatus(
    incompleteRouteChecks.length === 0 && routeP0.length === 0 && routeP1.length === 0,
    "frontend acceptance route check evidence is incomplete",
    {
      incomplete_route_checks: incompleteRouteChecks,
      recomputed_p0_count: routeP0.length,
      recomputed_p1_count: routeP1.length,
    },
  );
  requireStatus(
    incompleteAliasChecks.length === 0,
    "frontend acceptance alias check evidence is incomplete",
    {
      incomplete_alias_checks: incompleteAliasChecks,
    },
  );
  requireStatus(
    executedApiProbes.length === expectedApiProbes.length &&
      expectedApiProbes.every((probe) => executedApiProbes.includes(probe)) &&
      summary.executed_api_probe_count === expectedApiProbes.length &&
      skippedApiProbes.length === 0 &&
      summary.skipped_api_probe_count === 0,
    "frontend acceptance API probe coverage is incomplete",
    {
      executed_api_probes: executedApiProbes,
      executed_api_probe_count: summary.executed_api_probe_count,
      skipped_api_probes: skippedApiProbes,
      skipped_api_probe_count: summary.skipped_api_probe_count,
    },
  );
  requireStatus(
    expectedRoutes.length > 0 &&
      new Set(expectedRoutes).size === expectedRoutes.length &&
      summary.route_count === expectedRoutes.length &&
      summary.independent_page_count === expectedRoutes.length &&
      reportViewports.length === expectedViewports.length &&
      new Set(reportViewports).size === expectedViewports.length &&
      expectedViewports.every((viewport) => reportViewports.includes(viewport)) &&
      skippedRoutes.length === 0 &&
      summary.skipped_route_count === 0 &&
      routeChecks.length === summary.check_count &&
      routeViewportKeys.size === summary.check_count &&
      summary.check_count === expectedRouteViewportKeys.size &&
      routeViewportKeys.size === expectedRouteViewportKeys.size &&
      [...expectedRouteViewportKeys].every((key) => routeViewportKeys.has(key)),
    "frontend acceptance route coverage is incomplete",
    {
      contract_profile: report.contract_profile,
      expected_route_count: expectedRoutes.length,
      route_count: summary.route_count,
      independent_page_count: summary.independent_page_count,
      check_count: summary.check_count,
      viewport_count: reportViewports.length,
      skipped_routes: skippedRoutes,
      skipped_route_count: summary.skipped_route_count,
    },
  );
  requireStatus(
    new Set(expectedAliasRoutes).size === expectedAliasRoutes.length &&
      summary.alias_check_count === expectedAliasRoutes.length &&
      reportAliasChecks.length === summary.alias_execution_check_count &&
      aliasRouteViewportKeys.size === summary.alias_execution_check_count &&
      summary.alias_execution_check_count === expectedAliasRouteViewportKeys.size &&
      aliasRouteViewportKeys.size === expectedAliasRouteViewportKeys.size &&
      [...expectedAliasRouteViewportKeys].every((key) => aliasRouteViewportKeys.has(key)) &&
      summary.total_execution_check_count === routeChecks.length + reportAliasChecks.length,
    "frontend acceptance alias coverage is incomplete",
    {
      contract_profile: report.contract_profile,
      expected_alias_check_count: expectedAliasRoutes.length,
      alias_check_count: summary.alias_check_count,
      alias_execution_check_count: summary.alias_execution_check_count,
      total_execution_check_count: summary.total_execution_check_count,
    },
  );
  requireStatus(
    auditLogs.execution_status === "executed" &&
      auditLogs.anonymous_check === "executed" &&
      auditLogs.missing_tenant_check === "executed" &&
      auditLogs.allowed_check === "executed" &&
      [401, 403].includes(auditLogs.anonymous_status) &&
      [401, 403].includes(auditLogs.missing_tenant_status) &&
      auditLogs.allowed_status === 200,
    "audit logs API permission gate failed",
    auditLogs,
  );
  requireStatus(
    auditLogExports.execution_status === "executed" &&
      auditLogExports.anonymous_check === "executed" &&
      auditLogExports.missing_tenant_check === "executed" &&
      auditLogExports.allowed_check === "executed" &&
      [401, 403].includes(auditLogExports.anonymous_status) &&
      [401, 403].includes(auditLogExports.missing_tenant_status) &&
      auditLogExports.allowed_status === 200,
    "audit logs export API permission gate failed",
    auditLogExports,
  );
  console.log(
    JSON.stringify(
      {
        status: "pass",
        contract_profile: report.contract_profile,
        side_effect_mode: report.side_effect_mode,
        production_side_effect: report.production_side_effect,
        database_write: report.database_write,
        audit_log_write_expected: report.audit_log_write_expected,
        route_count: summary.route_count,
        independent_page_count: summary.independent_page_count,
        alias_check_count: summary.alias_check_count,
        check_count: summary.check_count,
        alias_execution_check_count: summary.alias_execution_check_count,
        total_execution_check_count: summary.total_execution_check_count,
        p0_count: p0.length,
        p1_count: p1.length,
        api_checks: {
          "/audit/logs": {
            anonymous_status: auditLogs.anonymous_status,
            missing_tenant_status: auditLogs.missing_tenant_status,
            allowed_status: auditLogs.allowed_status,
          },
          "/audit/logs/export": {
            anonymous_status: auditLogExports.anonymous_status,
            missing_tenant_status: auditLogExports.missing_tenant_status,
            allowed_status: auditLogExports.allowed_status,
          },
        },
      },
      null,
      2,
    ),
  );
}

function main() {
  const options = parseArgs(process.argv.slice(2));
  validateSideEffectAuthorization(options);
  runAcceptance(options);
  assertGate(readReport(options.output));
}

if (process.argv[1] && path.resolve(process.argv[1]) === __filename) {
  try {
    main();
  } catch (error) {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 2;
  }
}

export { assertGate, validateSideEffectAuthorization };
