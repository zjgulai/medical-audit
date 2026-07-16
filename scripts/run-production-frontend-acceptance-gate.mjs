#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import {
  aliasRouteChecks,
  deriveAcceptanceUserId,
  finalPath,
  loadReleaseGuardEvidence,
  normalizeProductionBaseUrl,
  readPngEvidence,
  routeCheckProfiles,
  screenshotFileName,
  validateAcceptanceEvidenceOptions,
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
    expectedDeploySha: null,
    acceptanceRunId: null,
    releaseGuardReport: null,
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
    } else if (arg === "--expected-deploy-sha" && next) {
      options.expectedDeploySha = next;
      index += 1;
    } else if (arg.startsWith("--expected-deploy-sha=")) {
      options.expectedDeploySha = arg.split("=", 2)[1];
    } else if (arg === "--acceptance-run-id" && next) {
      options.acceptanceRunId = next;
      index += 1;
    } else if (arg.startsWith("--acceptance-run-id=")) {
      options.acceptanceRunId = arg.split("=", 2)[1];
    } else if (arg === "--release-guard-report" && next) {
      options.releaseGuardReport = next;
      index += 1;
    } else if (arg.startsWith("--release-guard-report=")) {
      options.releaseGuardReport = arg.split("=", 2)[1];
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
  --expected-deploy-sha <sha> Exact 40-character lowercase release commit SHA.
  --acceptance-run-id <id>   Unique run id: fa-YYYYMMDDtHHMMSSz-<8..32 lowercase hex>.
  --release-guard-report <path>
                            Passing S1 medical-audit-production-release-guard-v1 report.
`);
}

function validateSideEffectAuthorization(options) {
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
  return normalizeProductionBaseUrl(options.baseUrl);
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
    "--expected-deploy-sha",
    options.expectedDeploySha,
    "--acceptance-run-id",
    options.acceptanceRunId,
    "--release-guard-report",
    options.releaseGuardReport,
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
    env: {
      ...process.env,
      MEDICAL_AUDIT_FRONTEND_ACCEPTANCE_SCREENSHOTS: "1",
      MEDICAL_AUDIT_FRONTEND_ACCEPTANCE_SCREENSHOT_POLICY: "all",
    },
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

function hasValidPngScreenshot(value, reportedEvidence) {
  const freshEvidence = readPngEvidence(value);
  return (
    freshEvidence !== null &&
    reportedEvidence !== null &&
    typeof reportedEvidence === "object" &&
    reportedEvidence.path === freshEvidence.path &&
    reportedEvidence.sha256 === freshEvidence.sha256 &&
    reportedEvidence.size_bytes === freshEvidence.size_bytes &&
    reportedEvidence.width === freshEvidence.width &&
    reportedEvidence.height === freshEvidence.height &&
    reportedEvidence.format === "png"
  );
}

function hasCompleteRouteEvidence(
  check,
  {
    expectedPath = null,
    expectedInputSearch = null,
    expectedSearch = null,
    expectedChromeTitle = null,
    requirePathIdentity = false,
    requireSearchIdentity = false,
    requireChromeIdentity = false,
    requireScreenshot = false,
    expectedScreenshotName = null,
    expectedScreenshotWidth = null,
    expectedScreenshotHeight = null,
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
    (!requireChromeIdentity ||
      (typeof check.expectedChromeTitle === "string" &&
        check.expectedChromeTitle === expectedChromeTitle &&
        typeof check.chromeTitle === "string" &&
        check.chromeTitle === expectedChromeTitle)) &&
    (!requireScreenshot ||
      (hasValidPngScreenshot(check.screenshot, check.screenshot_evidence) &&
        typeof check.screenshot === "string" &&
        path.basename(check.screenshot) === expectedScreenshotName &&
        check.screenshot_evidence?.width === expectedScreenshotWidth &&
        check.screenshot_evidence?.height === expectedScreenshotHeight)) &&
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

function assertGate(report, expected = {}) {
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
  const expectedRouteChromeTitles = new Map(
    Array.isArray(expectedRouteChecks)
      ? expectedRouteChecks
          .filter((check) => typeof check.expectedChromeTitle === "string")
          .map((check) => [check.route, check.expectedChromeTitle])
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
  const expectedViewportDimensions = new Map(
    acceptanceViewports.map((viewport) => [viewport.name, viewport]),
  );
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
  const requireIndependentScreenshot = true;
  const acceptanceRunId = expected.acceptanceRunId ?? report.acceptance_run_id;
  const incompleteRouteChecks = routeChecks
    .filter(
      (check) =>
        !hasCompleteRouteEvidence(check, {
          expectedPath: expectedRoutePaths.get(check?.route),
          expectedChromeTitle: expectedRouteChromeTitles.get(check?.route),
          requirePathIdentity: requirePathIdentity && expectedRoutePaths.has(check?.route),
          requireChromeIdentity: expectedRouteChromeTitles.has(check?.route),
          requireScreenshot: requireIndependentScreenshot,
          expectedScreenshotName: screenshotFileName({
            acceptanceRunId,
            contractKind: "independent",
            viewport: check?.viewport,
            route: check?.route,
            inputSearch: check?.inputSearch,
          }),
          expectedScreenshotWidth: expectedViewportDimensions.get(check?.viewport)?.width,
          expectedScreenshotHeight: expectedViewportDimensions.get(check?.viewport)?.height,
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
          requireScreenshot: true,
          expectedScreenshotName: screenshotFileName({
            acceptanceRunId,
            contractKind: "alias",
            viewport: check?.viewport,
            route: check?.route,
            inputSearch: check?.inputSearch,
          }),
          expectedScreenshotWidth: expectedViewportDimensions.get(check?.viewport)?.width,
          expectedScreenshotHeight: expectedViewportDimensions.get(check?.viewport)?.height,
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
  const releaseGuard = report.release_guard ?? {};
  const releaseIdentity = report.release_identity ?? {};
  const publicManifest = releaseIdentity.public_manifest ?? {};
  const deploymentMetadata = releaseIdentity.deployment_metadata ?? {};
  const expectedDeploySha = expected.expectedDeploySha ?? report.expected_deploy_sha;
  const expectedBaseUrl = expected.baseUrl ?? `${DEFAULT_BASE_URL}/`;
  let expectedAcceptanceUserId = null;
  try {
    expectedAcceptanceUserId = deriveAcceptanceUserId(acceptanceRunId);
  } catch {
    expectedAcceptanceUserId = null;
  }

  requireStatus(
    report.contract_profile === "hardened",
    "frontend acceptance gate requires the hardened contract profile",
    { contract_profile: report.contract_profile },
  );
  requireStatus(report.status === "pass", "frontend acceptance report is not pass", {
    status: report.status,
  });
  requireStatus(
    report.base_url === expectedBaseUrl,
    "frontend acceptance report base URL is not the exact production origin",
    { base_url: report.base_url, expected_base_url: expectedBaseUrl },
  );
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
    summary.screenshot_capture === true && summary.screenshot_policy === "all",
    "frontend acceptance screenshot contract is inconsistent",
    {
      screenshot_capture: summary.screenshot_capture,
      screenshot_policy: summary.screenshot_policy,
    },
  );
  requireStatus(
    typeof expectedDeploySha === "string" &&
      /^[0-9a-f]{40}$/.test(expectedDeploySha) &&
      report.expected_deploy_sha === expectedDeploySha &&
      report.acceptance_run_id === acceptanceRunId &&
      report.acceptance_user_id === expectedAcceptanceUserId,
    "frontend acceptance run identity is inconsistent",
    {
      expected_deploy_sha: report.expected_deploy_sha,
      acceptance_run_id: report.acceptance_run_id,
      acceptance_user_id: report.acceptance_user_id,
    },
  );
  requireStatus(
    releaseGuard.format === "medical-audit-production-release-guard-v1" &&
      releaseGuard.mode === "capture" &&
      releaseGuard.phase === "S1" &&
      releaseGuard.status === "pass" &&
      releaseGuard.evidence_grade === "L3-production-read-only" &&
      releaseGuard.source === "ssh-live-readonly" &&
      releaseGuard.observation_target?.format ===
        "medical-audit-release-guard-observation-target-v1" &&
      releaseGuard.observation_target?.kind === "production-ssh" &&
      releaseGuard.observation_target?.ssh_host === "101.34.52.232" &&
      releaseGuard.observation_target?.remote_app_dir === "/opt/medical-audit/app" &&
      releaseGuard.observation_target?.remote_web_dir === "/var/www/audit" &&
      releaseGuard.observation_target?.postgres_container === "medical_audit_pg" &&
      releaseGuard.capture_provenance?.format ===
        "medical-audit-release-guard-capture-provenance-v1" &&
      releaseGuard.capture_provenance?.transport === "ssh-stdin" &&
      releaseGuard.capture_provenance?.ssh_host === "101.34.52.232" &&
      releaseGuard.capture_provenance?.ssh_user === "ubuntu" &&
      releaseGuard.capture_provenance?.batch_mode === true &&
      releaseGuard.capture_provenance?.strict_host_key_checking === true &&
      releaseGuard.capture_provenance?.identities_only === true &&
      releaseGuard.capture_provenance?.ssh_exit_code === 0 &&
      releaseGuard.capture_provenance?.remote_app_dir === "/opt/medical-audit/app" &&
      releaseGuard.capture_provenance?.remote_web_dir === "/var/www/audit" &&
      releaseGuard.capture_provenance?.postgres_container === "medical_audit_pg" &&
      /^[0-9a-f]{64}$/.test(
        releaseGuard.capture_provenance?.collector_source_sha256 ?? "",
      ) &&
      /^[0-9a-f]{64}$/.test(releaseGuard.capture_envelope_id ?? "") &&
      releaseGuard.expected_deploy_sha === expectedDeploySha &&
      releaseGuard.observed_deploy_sha === expectedDeploySha &&
      releaseGuard.provider_call_status === "not_observed" &&
      releaseGuard.provider_evidence_source === "outside-release-guard-scope" &&
      releaseGuard.collector_provider_call_status === "not_called" &&
      releaseGuard.collector_provider_attempt_count === 0 &&
      releaseGuard.collector_execution_boundary?.format ===
        "medical-audit-release-guard-execution-boundary-v1" &&
      releaseGuard.collector_execution_boundary?.collector_protocol ===
        "ssh-stdin-release-topology-postgresql-readonly-v2" &&
      JSON.stringify(releaseGuard.collector_execution_boundary?.allowed_operations) ===
        JSON.stringify([
          "filesystem-read",
          "docker-exec-psql-readonly",
          "docker-inspect-readonly",
          "docker-exec-app-deploy-sha-readonly",
          "docker-exec-nginx-config-test",
        ]) &&
      releaseGuard.collector_execution_boundary?.executed_postgresql_readonly_commands === 2 &&
      releaseGuard.collector_execution_boundary?.executed_runtime_readonly_commands === 8 &&
      releaseGuard.collector_execution_boundary?.rejected_command_count === 0 &&
      releaseGuard.collector_execution_boundary?.collector_provider_endpoint_attempt_count === 0 &&
      releaseGuard.collector_execution_boundary?.provider_environment_read === false &&
      releaseGuard.collector_execution_boundary?.secret_values_reported === false &&
      releaseGuard.database_write === false &&
      releaseGuard.transaction_read_only === true &&
      releaseGuard.transaction_read_only_observed === "on" &&
      releaseGuard.transaction_isolation_observed === "serializable" &&
      releaseGuard.transaction_deferrable_observed === "on" &&
      releaseGuard.release_topology === "versioned_ready" &&
      releaseGuard.release_topology_evidence?.releases_root?.kind === "directory" &&
      releaseGuard.release_topology_evidence?.current?.target ===
        `releases/${expectedDeploySha}` &&
      releaseGuard.release_topology_evidence?.deploy_marker?.sha === expectedDeploySha &&
      releaseGuard.release_topology_evidence?.release?.sha === expectedDeploySha &&
      releaseGuard.current_release_target === `releases/${expectedDeploySha}` &&
      releaseGuard.object_storage?.status === "observed" &&
      releaseGuard.object_storage?.observation_scope === "database-ledger" &&
      releaseGuard.audit_attribution?.acceptance_run_id === acceptanceRunId &&
      releaseGuard.audit_attribution?.audit_user_identifier ===
        expectedAcceptanceUserId &&
      releaseGuard.audit_attribution?.attributable_event_count === 0 &&
      releaseGuard.audit_attribution?.event_id_fingerprint ===
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855" &&
      Array.isArray(releaseGuard.audit_attribution?.event_ids) &&
      releaseGuard.audit_attribution.event_ids.length === 0 &&
      releaseGuard.evidence_source === "release-guard-report:S1" &&
      typeof releaseGuard.report_path === "string" &&
      releaseGuard.report_path.length > 0 &&
      /^[0-9a-f]{64}$/.test(releaseGuard.report_sha256 ?? "") &&
      /^[0-9a-f]{64}$/.test(releaseGuard.snapshot_id ?? "") &&
      Array.isArray(releaseGuard.blocking_reasons) &&
      releaseGuard.blocking_reasons.length === 0 &&
      releaseGuard.guard_execution_write === false &&
      releaseGuard.capture_side_effect === "none" &&
      report.provider_call_status === releaseGuard.provider_call_status &&
      report.provider_evidence_source === "outside-frontend-acceptance-scope" &&
      report.collector_provider_call_status === releaseGuard.collector_provider_call_status &&
      (!expected.releaseGuardEvidence ||
        (releaseGuard.report_path === expected.releaseGuardEvidence.report_path &&
          releaseGuard.report_sha256 === expected.releaseGuardEvidence.report_sha256 &&
          releaseGuard.snapshot_id === expected.releaseGuardEvidence.snapshot_id)),
    "frontend acceptance release guard evidence is inconsistent",
    {
      release_guard: releaseGuard,
      provider_call_status: report.provider_call_status,
    },
  );
  requireStatus(
    releaseIdentity.stable === true &&
      releaseIdentity.expected_deploy_sha === expectedDeploySha &&
      releaseIdentity.current_release_target === `releases/${expectedDeploySha}` &&
      releaseIdentity.current_release_target_source === "release-guard-report:S1" &&
      publicManifest.path === "/release-manifest.json" &&
      publicManifest.format === "medical-audit-web-release-manifest-v1" &&
      publicManifest.source_sha === expectedDeploySha &&
      /^[0-9a-f]{64}$/.test(publicManifest.body_sha256 ?? "") &&
      publicManifest.initial_body_sha256 === publicManifest.body_sha256 &&
      publicManifest.final_body_sha256 === publicManifest.body_sha256 &&
      deploymentMetadata.path === "/api/v1/deployment/metadata" &&
      deploymentMetadata.status === "deployment_metadata_available" &&
      deploymentMetadata.deploy_sha_status === "set" &&
      deploymentMetadata.observed_deploy_sha === expectedDeploySha &&
      typeof deploymentMetadata.deploy_sha_source === "string" &&
      deploymentMetadata.deploy_sha_source.length > 0 &&
      /^[0-9a-f]{64}$/.test(deploymentMetadata.initial_body_sha256 ?? "") &&
      deploymentMetadata.final_body_sha256 === deploymentMetadata.initial_body_sha256 &&
      deploymentMetadata.current_release_target === null &&
      deploymentMetadata.current_release_target_status === "not_exposed_by_endpoint",
    "frontend acceptance release identity evidence is inconsistent",
    { release_identity: releaseIdentity },
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
  const screenshotPaths = allRouteChecks.map((check) => check?.screenshot);
  requireStatus(
    screenshotPaths.every((value) => typeof value === "string" && path.isAbsolute(value)) &&
      new Set(screenshotPaths).size === allRouteChecks.length,
    "frontend acceptance screenshot executions are not uniquely bound",
    {
      screenshot_count: screenshotPaths.length,
      unique_screenshot_count: new Set(screenshotPaths).size,
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
      auditLogs.anonymous_attribution_user_id === expectedAcceptanceUserId &&
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
      auditLogExports.anonymous_attribution_user_id === expectedAcceptanceUserId &&
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
        expected_deploy_sha: report.expected_deploy_sha,
        acceptance_run_id: report.acceptance_run_id,
        acceptance_user_id: report.acceptance_user_id,
        current_release_target: releaseIdentity.current_release_target,
        public_manifest_sha256: publicManifest.body_sha256,
        release_guard_report_sha256: releaseGuard.report_sha256,
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
  const normalizedBaseUrl = validateSideEffectAuthorization(options);
  options.baseUrl = normalizedBaseUrl;
  validateAcceptanceEvidenceOptions(options);
  if (options.contractProfile !== "hardened") {
    throw new Error("Frontend acceptance gate requires --contract-profile hardened");
  }
  const releaseGuardEvidence = loadReleaseGuardEvidence(
    options.releaseGuardReport,
    options.expectedDeploySha,
    options.acceptanceRunId,
  );
  runAcceptance(options);
  const finalReleaseGuardEvidence = loadReleaseGuardEvidence(
    options.releaseGuardReport,
    options.expectedDeploySha,
    options.acceptanceRunId,
  );
  if (
    finalReleaseGuardEvidence.report_sha256 !== releaseGuardEvidence.report_sha256 ||
    finalReleaseGuardEvidence.snapshot_id !== releaseGuardEvidence.snapshot_id
  ) {
    throw new Error("release guard report changed during frontend acceptance");
  }
  assertGate(readReport(options.output), {
    expectedDeploySha: options.expectedDeploySha,
    acceptanceRunId: options.acceptanceRunId,
    baseUrl: `${normalizedBaseUrl}/`,
    releaseGuardEvidence: finalReleaseGuardEvidence,
  });
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
