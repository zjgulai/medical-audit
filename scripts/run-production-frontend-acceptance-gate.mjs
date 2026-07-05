#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const repoRoot = path.resolve(path.dirname(__filename), "..");

const DEFAULT_BASE_URL = "https://audit.lute-tlz-dddd.top";
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
`);
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

function assertGate(report) {
  const summary = report.summary ?? {};
  const apiChecks = summary.api_checks ?? {};
  const auditLogs = apiChecks["/audit/logs"] ?? {};
  const auditLogExports = apiChecks["/audit/logs/export"] ?? {};
  const p0 = Array.isArray(summary.p0) ? summary.p0 : [];
  const p1 = Array.isArray(summary.p1) ? summary.p1 : [];

  requireStatus(report.status === "pass", "frontend acceptance report is not pass", {
    status: report.status,
  });
  requireStatus(p0.length === 0 && p1.length === 0, "frontend acceptance found P0/P1 issues", {
    p0_count: p0.length,
    p1_count: p1.length,
  });
  requireStatus(
    [401, 403].includes(auditLogs.denied_status) && auditLogs.allowed_status === 200,
    "audit logs API permission gate failed",
    auditLogs,
  );
  requireStatus(
    [401, 403].includes(auditLogExports.denied_status) && auditLogExports.allowed_status === 200,
    "audit logs export API permission gate failed",
    auditLogExports,
  );

  console.log(
    JSON.stringify(
      {
        status: "pass",
        contract_profile: report.contract_profile,
        route_count: summary.route_count,
        check_count: summary.check_count,
        p0_count: p0.length,
        p1_count: p1.length,
        api_checks: {
          "/audit/logs": {
            denied_status: auditLogs.denied_status,
            allowed_status: auditLogs.allowed_status,
          },
          "/audit/logs/export": {
            denied_status: auditLogExports.denied_status,
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
  runAcceptance(options);
  assertGate(readReport(options.output));
}

main();
