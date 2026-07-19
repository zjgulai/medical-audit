#!/usr/bin/env node

import fs from "node:fs";
import { createHash } from "node:crypto";
import { inflateSync } from "node:zlib";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(new URL("../web/package.json", import.meta.url));
const { chromium } = require("@playwright/test");

const __filename = fileURLToPath(import.meta.url);
const repoRoot = path.resolve(path.dirname(__filename), "..");

const DEFAULT_BASE_URL = "https://audit.lute-tlz-dddd.top";
const PRODUCTION_HOST = "audit.lute-tlz-dddd.top";
const DEFAULT_OUTPUT = "tmp/outputs/production-frontend-acceptance-latest.json";
const DEFAULT_SCREENSHOT_DIR = "tmp/screenshots/production-frontend-acceptance-latest";
const DEFAULT_TENANT_ID = "hospital-demo";
const DEFAULT_PROJECT_KEY = "SELF-CHECK-FUND-20260607";
const AUDIT_AUTH_STORAGE_KEY = "medical-audit-authenticated";
const AUDIT_ROLE_STORAGE_KEY = "medical-audit-current-role";
const FLOATING_LAYOUT_POSITIONS = Object.freeze(["fixed", "absolute", "sticky"]);
const DEFAULT_AUDIT_ROLE = "admin";
const RELEASE_MANIFEST_FORMAT = "medical-audit-web-release-manifest-v1";
const RELEASE_GUARD_FORMAT = "medical-audit-production-release-guard-v1";
const DEPLOYMENT_METADATA_PATH = "/api/v1/deployment/metadata";
const PUBLIC_RELEASE_MANIFEST_PATH = "/release-manifest.json";
const DEPLOY_SHA_PATTERN = /^[0-9a-f]{40}$/;
const SHA256_PATTERN = /^[0-9a-f]{64}$/;
const ABORTABLE_STATIC_ASSET_PATH_PATTERN = /\.(?:avif|gif|ico|jpe?g|png|svg|webp)$/i;
const ACCEPTANCE_RUN_ID_PATTERN = /^fa-[0-9]{8}t[0-9]{6}z-[0-9a-f]{8,32}$/;
const RELEASE_GUARD_EXECUTION_BOUNDARY_FORMAT =
  "medical-audit-release-guard-execution-boundary-v1";
const RELEASE_GUARD_OBSERVATION_TARGET_FORMAT =
  "medical-audit-release-guard-observation-target-v1";
const RELEASE_GUARD_CAPTURE_PROVENANCE_FORMAT =
  "medical-audit-release-guard-capture-provenance-v1";
const RELEASE_GUARD_COLLECTOR_PROTOCOL =
  "ssh-stdin-release-topology-postgresql-readonly-v2";
const RELEASE_GUARD_PRODUCTION_SSH_HOST = "101.34.52.232";
const RELEASE_GUARD_PRODUCTION_SSH_USER = "ubuntu";
const RELEASE_GUARD_SCRIPT_PATH = path.join(
  repoRoot,
  "scripts/audit-production-release-guard-snapshot.py",
);
const RELEASE_GUARD_ALLOWED_OPERATIONS = [
  "filesystem-read",
  "docker-exec-psql-readonly",
  "docker-inspect-readonly",
  "docker-exec-app-deploy-sha-readonly",
  "docker-exec-nginx-config-test",
];

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
    { route: "/agent-market", requiredText: [/智能体广场/, /招标流程核验|政策依据速查|凭证异常识别|纪要结构提取/] },
    {
      route: "/analytics",
      requiredText: [/AI数据分析/, /表格分析工作台/, /上传表格|分析历史/],
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
    { route: "/reports", requiredText: [/审计底稿与报告台账/, /六类模板目录/, /报告台账/] },
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
    {
      route: "/login",
      expectedPath: "/login",
      session: "anonymous",
      requiredText: [/登录工作台/],
      requiredControlText: [/(^|\s)登录($|\s)/],
    },
    {
      route: "/medical-audit",
      expectedPath: "/medical-audit",
      session: "workspace",
      requiredText: [/医保审计/, /智能审计/],
    },
    {
      route: "/fund-compliance",
      expectedPath: "/fund-compliance",
      expectedChromeTitle: "医保基金使用合规",
      session: "workspace",
      requiredText: [/医保基金使用合规/, /医保审计/],
      requiredTextAny: [[/复核表单/, /费用表单/, /归档包/]],
    },
    {
      route: "/fund-compliance/review",
      expectedPath: "/fund-compliance/review",
      expectedChromeTitle: "医保基金复核表单",
      session: "workspace",
      requiredText: [/医保基金复核表单/, /费用汇总表/, /分类汇总表|医保费用分类汇总表/, /就诊明细表|就诊费用明细表/],
    },
    {
      route: "/chat",
      expectedPath: "/chat",
      session: "workspace",
      requiredText: [/AI，让审计更智能/, /全部知识库|选择模型|发送问题|AI 对话/],
    },
    {
      route: "/agents",
      expectedPath: "/agents",
      session: "workspace",
      requiredText: [/我的助手|我的智能体/, /智能体/],
      requiredControlText: [/查看详情|创建/],
    },
    {
      route: "/agent-market",
      expectedPath: "/agent-market",
      session: "workspace",
      requiredText: [/智能体广场/, /详情/],
      requiredTextAny: [[/全部/, /财务收支审计/, /采购招标审计/, /工程审计/]],
    },
    {
      route: "/analytics",
      expectedPath: "/analytics",
      session: "workspace",
      requiredText: [/AI数据分析/, /表格分析工作台/, /上传表格|分析历史/],
    },
    {
      route: "/projects",
      expectedPath: "/projects",
      session: "workspace",
      requiredText: [/项目管理/, /项目协作工作台/, /可见项目/],
    },
    {
      route: "/documents",
      expectedPath: "/documents",
      session: "workspace",
      requiredText: [/文档检索/, /对话文档|检索结果|法律法规库|法规政策/],
    },
    {
      route: "/knowledge-base",
      expectedPath: "/knowledge-base",
      session: "workspace",
      requiredText: [/知识库分类|知识库/, /一级专题|可查询|知识库/],
    },
    {
      route: "/graph",
      expectedPath: "/graph",
      session: "workspace",
      requiredText: [/知识图谱/, /最小知识图谱方案|医疗审计知识工程|图谱/],
    },
    {
      route: "/rules",
      expectedPath: "/rules",
      expectedChromeTitle: "规则运行工作台",
      session: "workspace",
      requiredText: [/知识库|规则|法规/],
    },
    {
      route: "/reports",
      expectedPath: "/reports",
      session: "workspace",
      requiredText: [/审计底稿与报告台账/, /六类模板目录/, /报告台账/],
    },
    {
      route: "/remediation",
      expectedPath: "/remediation",
      expectedChromeTitle: "整改工作台",
      session: "workspace",
      requiredText: [/整改/, /补证/, /关闭门禁/],
    },
    {
      route: "/archive",
      expectedPath: "/archive",
      expectedChromeTitle: "归档工作台",
      session: "workspace",
      requiredText: [/归档工作台/, /归档包/, /签名链|归档策略|审计日志/],
    },
    {
      route: "/guided-check",
      expectedPath: "/guided-check",
      expectedChromeTitle: "引导式核查",
      session: "workspace",
      requiredText: [/引导式核查/, /核查步骤/, /AI 审证问题|材料准备状态/],
    },
  ],
};
const aliasRouteChecks = [
  {
    route: "/workspace",
    inputSearch: "",
    expectedPath: "/chat",
    expectedSearch: "",
    session: "workspace",
    requiredText: [/AI，让审计更智能/],
  },
  {
    route: "/findings",
    inputSearch: "",
    expectedPath: "/medical-audit",
    expectedSearch: "",
    session: "workspace",
    requiredText: [/医保审计/, /智能审计/],
  },
  {
    route: "/knowledge-query",
    inputSearch:
      "?q=%E5%8C%BB%E4%BF%9D%E6%94%AF%E4%BB%98&source_collection=medical-insurance-laws&unknown=discard&source_collection=personal-materials",
    expectedPath: "/documents",
    expectedSearch:
      "?query=%E5%8C%BB%E4%BF%9D%E6%94%AF%E4%BB%98&source_collection=medical-insurance-laws&source_collection=personal-materials",
    session: "workspace",
    requiredText: [/文档检索/, /对话文档|检索结果|搜索历史/],
  },
];
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
    allowAuditLogWrites: false,
    confirmProductionWrite: null,
    expectedDeploySha: null,
    acceptanceRunId: null,
    releaseGuardReport: null,
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
  if (!contractProfiles.includes(options.contractProfile)) {
    throw new Error(`Unknown contract profile: ${options.contractProfile}. Expected one of: ${contractProfiles.join(", ")}`);
  }
  return options;
}

function printHelp() {
  console.log(`Run production frontend acceptance checks.

The full browser acceptance flow can write audit-log records and therefore
fails closed unless audit-log writes are explicitly authorized.

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
  --allow-audit-log-writes Authorize audit-log-only writes made by the acceptance flow
  --confirm-production-write <host>
                            Required with --allow-audit-log-writes for every target;
                            must equal ${PRODUCTION_HOST}
  --expected-deploy-sha <sha> Exact 40-character lowercase release commit SHA
  --acceptance-run-id <id>   Unique run id: fa-YYYYMMDDtHHMMSSz-<8..32 lowercase hex>
  --release-guard-report <path>
                            Passing S1 medical-audit-production-release-guard-v1 report
`);
}

function validateSideEffectAuthorization(options) {
  if (!options.allowAuditLogWrites) {
    throw new Error(
      "Frontend acceptance fails closed by default: browser routes and API permission checks can write audit-log records. " +
        "Re-run with --allow-audit-log-writes and " +
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

function normalizeProductionBaseUrl(value) {
  let parsed;
  try {
    parsed = new URL(value);
  } catch {
    throw new Error(`Invalid --base-url: ${value}`);
  }
  if (
    parsed.protocol !== "https:" ||
    parsed.hostname !== PRODUCTION_HOST ||
    (parsed.port !== "" && parsed.port !== "443") ||
    parsed.username !== "" ||
    parsed.password !== "" ||
    parsed.pathname !== "/" ||
    parsed.search !== "" ||
    parsed.hash !== ""
  ) {
    throw new Error(
      `--base-url must be the exact production origin https://${PRODUCTION_HOST}`,
    );
  }
  return DEFAULT_BASE_URL;
}

function validateAcceptanceEvidenceOptions(options) {
  if (!DEPLOY_SHA_PATTERN.test(options.expectedDeploySha ?? "")) {
    throw new Error("--expected-deploy-sha must be exactly 40 lowercase hexadecimal characters");
  }
  if (!ACCEPTANCE_RUN_ID_PATTERN.test(options.acceptanceRunId ?? "")) {
    throw new Error(
      "--acceptance-run-id must match fa-YYYYMMDDtHHMMSSz-<8..32 lowercase hex>",
    );
  }
  if (typeof options.releaseGuardReport !== "string" || options.releaseGuardReport.trim() === "") {
    throw new Error("--release-guard-report is required");
  }
}

function deriveAcceptanceUserId(acceptanceRunId) {
  if (!ACCEPTANCE_RUN_ID_PATTERN.test(acceptanceRunId ?? "")) {
    throw new Error(
      "--acceptance-run-id must match fa-YYYYMMDDtHHMMSSz-<8..32 lowercase hex>",
    );
  }
  return `frontend-acceptance-${acceptanceRunId}`;
}

function sha256(value) {
  return createHash("sha256").update(value).digest("hex");
}

function canonicalJson(value) {
  if (value === null || typeof value !== "object") {
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    return `[${value.map((item) => canonicalJson(item)).join(",")}]`;
  }
  return `{${Object.keys(value)
    .sort()
    .map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`)
    .join(",")}}`;
}

const RELEASE_GUARD_SNAPSHOT_CORE_FIELDS = [
  "phase",
  "generated_at",
  "observation_target",
  "expected_deploy_sha",
  "observed_deploy_sha",
  "transaction_read_only",
  "transaction_read_only_observed",
  "transaction_isolation_observed",
  "transaction_deferrable_observed",
  "release_topology",
  "release_topology_evidence",
  "current_release_target",
  "manifest_source_sha",
  "manifest_sha256",
  "schema_fingerprint",
  "schema_tables",
  "schema_fingerprint_scope",
  "tables",
  "object_storage",
  "provider_call_status",
  "provider_evidence_source",
  "collector_provider_call_status",
  "collector_provider_attempt_count",
  "collector_execution_boundary",
  "capture_consistency",
  "audit_attribution",
];

function recomputeReleaseGuardSnapshotId(payload) {
  if (
    payload === null ||
    typeof payload !== "object" ||
    Array.isArray(payload) ||
    RELEASE_GUARD_SNAPSHOT_CORE_FIELDS.some(
      (field) => !Object.prototype.hasOwnProperty.call(payload, field),
    )
  ) {
    return null;
  }
  const core = Object.fromEntries(
    RELEASE_GUARD_SNAPSHOT_CORE_FIELDS.map((field) => [field, payload[field]]),
  );
  return sha256(canonicalJson(core));
}

function loadReleaseGuardEvidence(value, expectedDeploySha, acceptanceRunId) {
  if (!DEPLOY_SHA_PATTERN.test(expectedDeploySha ?? "")) {
    throw new Error("expected deploy SHA must be exactly 40 lowercase hexadecimal characters");
  }
  if (!ACCEPTANCE_RUN_ID_PATTERN.test(acceptanceRunId ?? "")) {
    throw new Error("acceptance run id is invalid for release guard binding");
  }
  if (typeof value !== "string" || value.trim() === "") {
    throw new Error("release guard report path is required");
  }
  const reportPath = resolveRepoPath(value);
  let raw;
  try {
    raw = fs.readFileSync(reportPath);
  } catch {
    throw new Error(`release guard report is not readable: ${reportPath}`);
  }
  let payload;
  try {
    payload = JSON.parse(raw.toString("utf8"));
  } catch {
    throw new Error(`release guard report is not valid JSON: ${reportPath}`);
  }
  const snapshotId = payload?.snapshot_id;
  const recomputedSnapshotId = recomputeReleaseGuardSnapshotId(payload);
  const collectorBoundary = payload?.collector_execution_boundary;
  const observationTarget = payload?.observation_target;
  const topology = payload?.release_topology_evidence;
  const auditAttribution = payload?.audit_attribution;
  const captureProvenance = payload?.capture_provenance;
  let currentCollectorSourceSha256 = null;
  try {
    currentCollectorSourceSha256 = sha256(fs.readFileSync(RELEASE_GUARD_SCRIPT_PATH));
  } catch {
    throw new Error(`release guard collector source is not readable: ${RELEASE_GUARD_SCRIPT_PATH}`);
  }
  const recomputedEnvelopeId = sha256(
    canonicalJson({
      snapshot_id: snapshotId,
      capture_provenance: captureProvenance,
    }),
  );
  const valid =
    payload !== null &&
    typeof payload === "object" &&
    !Array.isArray(payload) &&
    payload.format === RELEASE_GUARD_FORMAT &&
    payload.mode === "capture" &&
    payload.phase === "S1" &&
    payload.status === "pass" &&
    payload.evidence_grade === "L3-production-read-only" &&
    payload.source === "ssh-live-readonly" &&
    /^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$/.test(
      payload.generated_at ?? "",
    ) &&
    observationTarget?.format === RELEASE_GUARD_OBSERVATION_TARGET_FORMAT &&
    observationTarget?.kind === "production-ssh" &&
    observationTarget?.ssh_host === RELEASE_GUARD_PRODUCTION_SSH_HOST &&
    observationTarget?.remote_app_dir === "/opt/medical-audit/app" &&
    observationTarget?.remote_web_dir === "/var/www/audit" &&
    observationTarget?.postgres_container === "medical_audit_pg" &&
    payload.expected_deploy_sha === expectedDeploySha &&
    payload.observed_deploy_sha === expectedDeploySha &&
    payload.provider_call_status === "not_observed" &&
    payload.provider_evidence_source === "outside-release-guard-scope" &&
    payload.collector_provider_call_status === "not_called" &&
    payload.collector_provider_attempt_count === 0 &&
    collectorBoundary?.format === RELEASE_GUARD_EXECUTION_BOUNDARY_FORMAT &&
    collectorBoundary?.collector_protocol === RELEASE_GUARD_COLLECTOR_PROTOCOL &&
    JSON.stringify(collectorBoundary?.allowed_operations) ===
      JSON.stringify(RELEASE_GUARD_ALLOWED_OPERATIONS) &&
    collectorBoundary?.executed_postgresql_readonly_commands === 2 &&
    collectorBoundary?.executed_runtime_readonly_commands === 8 &&
    collectorBoundary?.rejected_command_count === 0 &&
    collectorBoundary?.collector_provider_endpoint_attempt_count === 0 &&
    collectorBoundary?.provider_environment_read === false &&
    collectorBoundary?.secret_values_reported === false &&
    payload.database_write === false &&
    payload.transaction_read_only === true &&
    payload.transaction_read_only_observed === "on" &&
    payload.transaction_isolation_observed === "serializable" &&
    payload.transaction_deferrable_observed === "on" &&
    payload.release_topology === "versioned_ready" &&
    topology?.releases_root?.kind === "directory" &&
    topology?.current?.kind === "symlink" &&
    topology?.current?.target === `releases/${expectedDeploySha}` &&
    topology?.deploy_marker?.kind === "regular_file" &&
    topology?.deploy_marker?.sha === expectedDeploySha &&
    topology?.release?.kind === "directory" &&
    topology?.release?.sha === expectedDeploySha &&
    topology?.release?.manifest_source_sha === expectedDeploySha &&
    payload.current_release_target === `releases/${expectedDeploySha}` &&
    payload.object_storage?.status === "observed" &&
    payload.object_storage?.observation_scope === "database-ledger" &&
    auditAttribution?.acceptance_run_id === acceptanceRunId &&
    auditAttribution?.audit_user_identifier === `frontend-acceptance-${acceptanceRunId}` &&
    auditAttribution?.attributable_event_count === 0 &&
    auditAttribution?.event_id_fingerprint === sha256("") &&
    Array.isArray(auditAttribution?.event_ids) &&
    auditAttribution.event_ids.length === 0 &&
    captureProvenance?.format === RELEASE_GUARD_CAPTURE_PROVENANCE_FORMAT &&
    captureProvenance?.transport === "ssh-stdin" &&
    captureProvenance?.ssh_host === RELEASE_GUARD_PRODUCTION_SSH_HOST &&
    captureProvenance?.ssh_user === RELEASE_GUARD_PRODUCTION_SSH_USER &&
    captureProvenance?.batch_mode === true &&
    captureProvenance?.strict_host_key_checking === true &&
    captureProvenance?.identities_only === true &&
    captureProvenance?.ssh_exit_code === 0 &&
    captureProvenance?.remote_app_dir === "/opt/medical-audit/app" &&
    captureProvenance?.remote_web_dir === "/var/www/audit" &&
    captureProvenance?.postgres_container === "medical_audit_pg" &&
    captureProvenance?.collector_source_sha256 === currentCollectorSourceSha256 &&
    payload.capture_envelope_id === recomputedEnvelopeId &&
    Array.isArray(payload.blocking_reasons) &&
    payload.blocking_reasons.length === 0 &&
    payload.guard_execution_write === false &&
    payload.capture_side_effect === "none" &&
    typeof snapshotId === "string" &&
    SHA256_PATTERN.test(snapshotId) &&
    recomputedSnapshotId === snapshotId;
  if (!valid) {
    throw new Error(
      "release guard report must be a complete L3 ssh-live-readonly S1 capture bound to the " +
        "expected deploy SHA, current_release_target=releases/<expected SHA>, a validated " +
        "collector-only execution boundary, database_write=false, and a serializable " +
        "read-only deferrable transaction",
    );
  }
  return {
    report_path: reportPath,
    report_sha256: sha256(raw),
    evidence_source: "release-guard-report:S1",
    snapshot_id: snapshotId,
    format: payload.format,
    mode: payload.mode,
    phase: payload.phase,
    status: payload.status,
    evidence_grade: payload.evidence_grade,
    source: payload.source,
    generated_at: payload.generated_at,
    observation_target: payload.observation_target,
    capture_provenance: payload.capture_provenance,
    capture_envelope_id: payload.capture_envelope_id,
    expected_deploy_sha: payload.expected_deploy_sha,
    observed_deploy_sha: payload.observed_deploy_sha,
    provider_call_status: payload.provider_call_status,
    provider_evidence_source: payload.provider_evidence_source,
    collector_provider_call_status: payload.collector_provider_call_status,
    collector_provider_attempt_count: payload.collector_provider_attempt_count,
    collector_execution_boundary: payload.collector_execution_boundary,
    database_write: payload.database_write,
    transaction_read_only: payload.transaction_read_only,
    transaction_read_only_observed: payload.transaction_read_only_observed,
    transaction_isolation_observed: payload.transaction_isolation_observed,
    transaction_deferrable_observed: payload.transaction_deferrable_observed,
    release_topology: payload.release_topology,
    release_topology_evidence: payload.release_topology_evidence,
    current_release_target: payload.current_release_target,
    object_storage: payload.object_storage,
    audit_attribution: payload.audit_attribution,
    blocking_reasons: payload.blocking_reasons,
    guard_execution_write: payload.guard_execution_write,
    capture_side_effect: payload.capture_side_effect,
  };
}

const PNG_SIGNATURE = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);

function crc32(content) {
  let crc = 0xffffffff;
  for (const byte of content) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit += 1) {
      crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0);
    }
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function readPngEvidence(value) {
  if (typeof value !== "string" || path.extname(value).toLowerCase() !== ".png") {
    return null;
  }
  let content;
  try {
    content = fs.readFileSync(value);
  } catch {
    return null;
  }
  if (
    content.length < 45 ||
    !content.subarray(0, PNG_SIGNATURE.length).equals(PNG_SIGNATURE) ||
    content.readUInt32BE(8) !== 13 ||
    content.subarray(12, 16).toString("ascii") !== "IHDR"
  ) {
    return null;
  }
  const width = content.readUInt32BE(16);
  const height = content.readUInt32BE(20);
  const bitDepth = content[24];
  const colorType = content[25];
  const compressionMethod = content[26];
  const filterMethod = content[27];
  const interlaceMethod = content[28];
  const channels = { 2: 3, 6: 4 }[colorType];
  if (
    width <= 0 ||
    height <= 0 ||
    bitDepth !== 8 ||
    channels === undefined ||
    compressionMethod !== 0 ||
    filterMethod !== 0 ||
    interlaceMethod !== 0
  ) {
    return null;
  }
  let offset = PNG_SIGNATURE.length;
  let sawIend = false;
  const idatChunks = [];
  while (offset + 12 <= content.length) {
    const chunkLength = content.readUInt32BE(offset);
    const chunkEnd = offset + 12 + chunkLength;
    if (chunkEnd > content.length) {
      return null;
    }
    const chunkType = content.subarray(offset + 4, offset + 8).toString("ascii");
    const recordedCrc = content.readUInt32BE(offset + 8 + chunkLength);
    const computedCrc = crc32(content.subarray(offset + 4, offset + 8 + chunkLength));
    if (recordedCrc !== computedCrc) {
      return null;
    }
    if (chunkType === "IEND") {
      if (chunkLength !== 0 || chunkEnd !== content.length) {
        return null;
      }
      sawIend = true;
      break;
    }
    if (chunkType === "IDAT") {
      idatChunks.push(content.subarray(offset + 8, offset + 8 + chunkLength));
    }
    offset = chunkEnd;
  }
  const rowBytes = width * channels;
  const expectedInflatedSize = (rowBytes + 1) * height;
  if (!sawIend || idatChunks.length === 0 || expectedInflatedSize > 20 * 1024 * 1024) {
    return null;
  }
  let inflated;
  try {
    inflated = inflateSync(Buffer.concat(idatChunks), {
      maxOutputLength: expectedInflatedSize,
    });
  } catch {
    return null;
  }
  if (inflated.length !== expectedInflatedSize) {
    return null;
  }
  for (let row = 0; row < height; row += 1) {
    if (inflated[row * (rowBytes + 1)] > 4) {
      return null;
    }
  }
  return {
    path: value,
    sha256: sha256(content),
    size_bytes: content.length,
    width,
    height,
    format: "png",
  };
}

function screenshotFileName({ acceptanceRunId, contractKind, viewport, route, inputSearch }) {
  if (
    !ACCEPTANCE_RUN_ID_PATTERN.test(acceptanceRunId ?? "") ||
    typeof contractKind !== "string" ||
    typeof viewport !== "string" ||
    typeof route !== "string"
  ) {
    return null;
  }
  const safeRoute = route.replaceAll("/", "_").replace(/^_/, "") || "root";
  const executionHash = sha256(
    JSON.stringify({ contractKind, viewport, route, inputSearch: inputSearch ?? "" }),
  ).slice(0, 12);
  return `${acceptanceRunId}-${contractKind}-${viewport}-${safeRoute}-${executionHash}.png`;
}

function sanitizeUrl(value) {
  try {
    const parsed = new URL(value);
    return `${parsed.origin}${parsed.pathname}`;
  } catch {
    return "invalid-url";
  }
}

function finalPath(url) {
  try {
    return new URL(url).pathname.replace(/\/+$/, "") || "/";
  } catch {
    return null;
  }
}

function finalSearch(url) {
  try {
    return new URL(url).search;
  } catch {
    return null;
  }
}

function buildBrowserContextOptions(viewport, session, acceptanceHeaders) {
  const options = {
    viewport: { width: viewport.width, height: viewport.height },
  };
  if (session !== "anonymous") {
    options.extraHTTPHeaders = acceptanceHeaders;
  }
  return options;
}

function sanitizeFailedRequest(failed) {
  const sanitized = { url: sanitizeUrl(failed.url) };
  if (Number.isInteger(failed.status)) {
    sanitized.status = failed.status;
  } else if (typeof failed.error === "string" && /^net::[A-Z_]+$/.test(failed.error)) {
    sanitized.error = failed.error;
  } else {
    sanitized.error = "request-failed";
  }
  return sanitized;
}

function sanitizeOverflowOffenders(items) {
  return items.map((item) => ({
    tag: item.tag,
    rect: item.rect,
  }));
}

function sanitizeFloatingControlOcclusions(items) {
  return items.map((item) => ({
    floating: {
      tag: item.floating.tag,
      rect: item.floating.rect,
    },
    covered: {
      tag: item.covered.tag,
      rect: item.covered.rect,
    },
  }));
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

function isIgnorableFailedRequest({ url, error }, baseUrl) {
  if (error !== "net::ERR_ABORTED") {
    return false;
  }
  try {
    const parsed = new URL(url);
    if (parsed.origin !== new URL(baseUrl).origin) {
      return false;
    }
    return (
      parsed.pathname.startsWith("/_next/static/")
      || parsed.searchParams.has("_rsc")
      || parsed.pathname.endsWith(".txt")
      || ABORTABLE_STATIC_ASSET_PATH_PATTERN.test(parsed.pathname)
    );
  } catch {
    return false;
  }
}

function isRecoveredAbortedRequest(failed, successfulResponseUrls) {
  return (
    failed.method === "GET"
    && failed.error === "net::ERR_ABORTED"
    && successfulResponseUrls.has(failed.url)
  );
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

function isFloatingLayoutPosition(position) {
  return FLOATING_LAYOUT_POSITIONS.includes(position);
}

async function snapshot(page) {
  for (let attempt = 1; attempt <= 3; attempt += 1) {
    try {
      return await page.evaluate((floatingLayoutPositions) => {
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
        const interactiveElements = Array.from(
          document.querySelectorAll("input, textarea, select, button, a, [role='button'], [role='tab']"),
        ).filter(isVisible);
        const controlText = interactiveElements
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
        const layoutDescriptor = (element) => {
          const rect = element.getBoundingClientRect();
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
              top: Math.round(rect.top),
              bottom: Math.round(rect.bottom),
              width: Math.round(rect.width),
              height: Math.round(rect.height),
            },
          };
        };
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
            return layoutDescriptor(element);
          })
          .filter(Boolean)
          .sort((left, right) => right.rect.right - left.rect.right || right.rect.width - left.rect.width)
          .slice(0, 10);
        const interactiveOverflowOffenders = interactiveElements
          .map((element) => {
            const rect = element.getBoundingClientRect();
            if (rect.right <= clientWidth + 2 && rect.left >= -2) {
              return null;
            }
            return layoutDescriptor(element);
          })
          .filter(Boolean)
          .sort((left, right) => right.rect.right - left.rect.right)
          .slice(0, 10);
        const intersects = (left, right) => (
          Math.min(left.right, right.right) - Math.max(left.left, right.left) > 4
          && Math.min(left.bottom, right.bottom) - Math.max(left.top, right.top) > 4
        );
        const routeInteractiveElements = interactiveElements.filter((element) =>
          element.closest(".replica-page-scroll") !== null
        );
        const floatingControlOcclusions = Array.from(
          document.querySelectorAll("[data-layout-floating-control]"),
        )
          .filter(isVisible)
          .filter((floating) => floatingLayoutPositions.includes(window.getComputedStyle(floating).position))
          .flatMap((floating) => {
            const floatingRect = floating.getBoundingClientRect();
            return routeInteractiveElements
              .filter((covered) => covered !== floating && !floating.contains(covered))
              .filter((covered) => intersects(floatingRect, covered.getBoundingClientRect()))
              .map((covered) => ({
                floating: layoutDescriptor(floating),
                covered: layoutDescriptor(covered),
              }));
          })
          .slice(0, 10);
        const chromeTitleElement = Array.from(document.querySelectorAll(".replica-topbar-title")).find(isVisible);
        return {
          title: document.title,
          chromeTitle: chromeTitleElement ? compact(chromeTitleElement.textContent ?? "") : null,
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
          interactiveOverflowOffenders,
          floatingControlOcclusions,
        };
      }, FLOATING_LAYOUT_POSITIONS);
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

async function seedWorkspaceSession(context) {
  await context.addInitScript(
    ({ authStorageKey, roleStorageKey, role }) => {
      window.localStorage.setItem(authStorageKey, "authenticated");
      window.localStorage.setItem(roleStorageKey, role);
    },
    {
      authStorageKey: AUDIT_AUTH_STORAGE_KEY,
      roleStorageKey: AUDIT_ROLE_STORAGE_KEY,
      role: DEFAULT_AUDIT_ROLE,
    },
  );
}

function isLoginGateSnapshot(snapshot) {
  const headings = Array.isArray(snapshot?.headings) ? snapshot.headings : [];
  const submitControls = Array.isArray(snapshot?.submitControls) ? snapshot.submitControls : [];
  return (
    headings.some((value) => compactText(String(value)) === "登录工作台") &&
    submitControls.some((value) => compactText(String(value)) === "登录")
  );
}

async function ensureWorkspaceSession(page, timeoutMs) {
  await page
    .evaluate(
      ({ authStorageKey, roleStorageKey, role }) => {
        window.localStorage.setItem(authStorageKey, "authenticated");
        window.localStorage.setItem(roleStorageKey, role);
      },
      {
        authStorageKey: AUDIT_AUTH_STORAGE_KEY,
        roleStorageKey: AUDIT_ROLE_STORAGE_KEY,
        role: DEFAULT_AUDIT_ROLE,
      },
    )
    .catch(() => {});

  const loginGateSnapshot = await page
    .evaluate(() => {
      const textOf = (element) => element.textContent || element.getAttribute("value") || "";
      return {
        headings: Array.from(document.querySelectorAll("h1,h2,h3")).map(textOf),
        submitControls: Array.from(
          document.querySelectorAll('form button[type="submit"], form input[type="submit"]'),
        ).map(textOf),
      };
    })
    .catch(() => null);

  if (isLoginGateSnapshot(loginGateSnapshot)) {
    await page.reload({ waitUntil: "domcontentloaded", timeout: timeoutMs });
  }
}

function issue(severity, type, message) {
  return { severity, type, message };
}

function classify(check, routeCheck, data) {
  const issues = [];
  if (routeCheck.expectedPath) {
    const observedPath = finalPath(check.finalUrl);
    if (observedPath !== routeCheck.expectedPath) {
      issues.push(
        issue(
          "P0",
          "unexpected-final-path",
          `expected ${routeCheck.expectedPath}; observed ${observedPath ?? "invalid-url"}`,
        ),
      );
    }
  }
  if (typeof routeCheck.expectedSearch === "string") {
    const observedSearch =
      typeof check.finalSearch === "string" ? check.finalSearch : finalSearch(check.finalUrl);
    if (observedSearch !== routeCheck.expectedSearch) {
      issues.push(
        issue(
          "P0",
          "unexpected-final-search",
          `expected ${routeCheck.expectedSearch || "<empty>"}; observed ${observedSearch || "<empty>"}`,
        ),
      );
    }
  }
  if (
    typeof routeCheck.expectedChromeTitle === "string" &&
    data.chromeTitle !== routeCheck.expectedChromeTitle
  ) {
    issues.push(
      issue(
        "P0",
        "unexpected-chrome-title",
        `expected ${routeCheck.expectedChromeTitle}; observed ${data.chromeTitle ?? "missing"}`,
      ),
    );
  }
  if (!check.status || check.status >= 400) {
    issues.push(issue("P0", "http-status", `HTTP ${check.status ?? "unknown"}`));
  }
  if (check.error) {
    issues.push(issue("P0", "navigation-error", "navigation failed"));
  }
  if (check.consoleErrors.length > 0) {
    issues.push(issue("P1", "console-error", `${check.consoleErrors.length} console error(s)`));
  }
  if (check.failedRequests.length > 0) {
    const sample = check.failedRequests
      .slice(0, 3)
      .map(sanitizeFailedRequest)
      .map((failed) => `${failed.status ?? failed.error} ${failed.url}`)
      .join(" | ");
    issues.push(issue("P1", "failed-request", sample));
  }
  if (check.interactionErrors.length > 0) {
    issues.push(issue("P1", "interaction-error", `${check.interactionErrors.length} interaction error(s)`));
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
  if ((data.interactiveOverflowOffenders?.length ?? 0) > 0) {
    issues.push(
      issue(
        "P1",
        "interactive-control-overflow",
        `${data.interactiveOverflowOffenders.length} interactive control(s) outside the viewport`,
      ),
    );
  }
  if ((data.floatingControlOcclusions?.length ?? 0) > 0) {
    issues.push(
      issue(
        "P1",
        "floating-control-occlusion",
        `${data.floatingControlOcclusions.length} route control(s) covered by a floating control`,
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
      redirect: "manual",
      signal: controller.signal,
    });
    const bodyBytes = Buffer.from(await response.arrayBuffer());
    const bodyText = bodyBytes.toString("utf8");
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
      bodySha256: sha256(bodyBytes),
      contentType: response.headers.get("content-type") ?? "unknown",
      location: response.headers.get("location") ?? null,
    };
  } finally {
    clearTimeout(timer);
  }
}

async function observeReleaseIdentity({ baseUrl, acceptanceHeaders, timeoutMs }) {
  const publicManifest = await fetchWithTimeout(`${baseUrl}${PUBLIC_RELEASE_MANIFEST_PATH}`, {
    timeoutMs,
    headers: { Accept: "application/json" },
  });
  const deploymentMetadata = await fetchWithTimeout(`${baseUrl}${DEPLOYMENT_METADATA_PATH}`, {
    timeoutMs,
    headers: {
      Accept: "application/json",
      ...acceptanceHeaders,
    },
  });
  return {
    public_manifest: {
      path: PUBLIC_RELEASE_MANIFEST_PATH,
      http_status: publicManifest.status,
      content_type: publicManifest.contentType,
      format: publicManifest.body?.format ?? null,
      source_sha: publicManifest.body?.source_sha ?? null,
      body_sha256: publicManifest.bodySha256,
    },
    deployment_metadata: {
      path: DEPLOYMENT_METADATA_PATH,
      http_status: deploymentMetadata.status,
      content_type: deploymentMetadata.contentType,
      status: deploymentMetadata.body?.status ?? null,
      deploy_sha_status: deploymentMetadata.body?.deploy_sha_status ?? null,
      observed_deploy_sha: deploymentMetadata.body?.deploy_sha ?? null,
      deploy_sha_source: deploymentMetadata.body?.deploy_sha_source ?? null,
      body_sha256: deploymentMetadata.bodySha256,
    },
  };
}

function validateReleaseIdentityObservation(observation, expectedDeploySha, label) {
  const publicManifest = observation?.public_manifest ?? {};
  const deploymentMetadata = observation?.deployment_metadata ?? {};
  if (
    publicManifest.http_status !== 200 ||
    publicManifest.format !== RELEASE_MANIFEST_FORMAT ||
    publicManifest.source_sha !== expectedDeploySha ||
    !SHA256_PATTERN.test(publicManifest.body_sha256 ?? "")
  ) {
    throw new Error(
      `${label} public release manifest is not a valid ${RELEASE_MANIFEST_FORMAT} artifact bound to ${expectedDeploySha}`,
    );
  }
  if (
    deploymentMetadata.http_status !== 200 ||
    deploymentMetadata.status !== "deployment_metadata_available" ||
    deploymentMetadata.deploy_sha_status !== "set" ||
    deploymentMetadata.observed_deploy_sha !== expectedDeploySha ||
    typeof deploymentMetadata.deploy_sha_source !== "string" ||
    deploymentMetadata.deploy_sha_source.length === 0 ||
    !SHA256_PATTERN.test(deploymentMetadata.body_sha256 ?? "")
  ) {
    throw new Error(
      `${label} deployment metadata is not bound to expected deploy SHA ${expectedDeploySha}`,
    );
  }
}

function validateReleaseIdentityPair(
  initial,
  final,
  expectedDeploySha,
  currentReleaseTarget = null,
) {
  if (!DEPLOY_SHA_PATTERN.test(expectedDeploySha ?? "")) {
    throw new Error("expected deploy SHA must be exactly 40 lowercase hexadecimal characters");
  }
  validateReleaseIdentityObservation(initial, expectedDeploySha, "initial");
  validateReleaseIdentityObservation(final, expectedDeploySha, "final");
  const initialManifest = initial.public_manifest;
  const finalManifest = final.public_manifest;
  const initialMetadata = initial.deployment_metadata;
  const finalMetadata = final.deployment_metadata;
  const stable =
    initialManifest.body_sha256 === finalManifest.body_sha256 &&
    initialManifest.source_sha === finalManifest.source_sha &&
    initialMetadata.body_sha256 === finalMetadata.body_sha256 &&
    initialMetadata.observed_deploy_sha === finalMetadata.observed_deploy_sha &&
    initialMetadata.deploy_sha_source === finalMetadata.deploy_sha_source;
  if (!stable) {
    throw new Error("release identity changed during frontend acceptance");
  }
  if (currentReleaseTarget !== null && currentReleaseTarget !== `releases/${expectedDeploySha}`) {
    throw new Error("current release target is not bound to the expected deploy SHA");
  }
  return {
    stable: true,
    expected_deploy_sha: expectedDeploySha,
    current_release_target: currentReleaseTarget,
    current_release_target_source:
      currentReleaseTarget === null ? "not_observed" : "release-guard-report:S1",
    public_manifest: {
      path: PUBLIC_RELEASE_MANIFEST_PATH,
      format: RELEASE_MANIFEST_FORMAT,
      source_sha: initialManifest.source_sha,
      body_sha256: initialManifest.body_sha256,
      initial_body_sha256: initialManifest.body_sha256,
      final_body_sha256: finalManifest.body_sha256,
    },
    deployment_metadata: {
      path: DEPLOYMENT_METADATA_PATH,
      status: "deployment_metadata_available",
      deploy_sha_status: "set",
      observed_deploy_sha: initialMetadata.observed_deploy_sha,
      deploy_sha_source: initialMetadata.deploy_sha_source,
      initial_body_sha256: initialMetadata.body_sha256,
      final_body_sha256: finalMetadata.body_sha256,
      current_release_target: null,
      current_release_target_status: "not_exposed_by_endpoint",
    },
  };
}

async function checkAuditLogApiPermissions({
  baseUrl,
  adminRole,
  adminApiKey,
  adminUserId,
  timeoutMs,
}) {
  const checks = {};
  const executedProbes = [];
  const endpoints = [
    { path: "/audit/logs", requireItems: true },
    { path: "/audit/logs/export", requireItems: false },
  ];

  const probeHeaders = buildAuditPermissionProbeHeaders({
    adminRole,
    adminApiKey,
    adminUserId,
  });

  for (const item of endpoints) {
    const anonymous = await fetchWithTimeout(`${baseUrl}${item.path}`, {
      timeoutMs,
      headers: probeHeaders.anonymous,
    });
    executedProbes.push(`${item.path}:anonymous`);
    const missingTenant = await fetchWithTimeout(`${baseUrl}${item.path}`, {
      timeoutMs,
      headers: probeHeaders.missingTenant,
    });
    executedProbes.push(`${item.path}:missing-tenant`);
    const allowed = await fetchWithTimeout(`${baseUrl}${item.path}`, {
      timeoutMs,
      headers: probeHeaders.allowed,
    });
    executedProbes.push(`${item.path}:allowed`);

    if (item.requireItems && !Array.isArray(allowed.body?.items)) {
      throw new Error(`${item.path} should return JSON with items`);
    }

    checks[item.path] = {
      execution_status: "executed",
      anonymous_check: "executed",
      missing_tenant_check: "executed",
      allowed_check: "executed",
      anonymous_attribution_user_id: adminUserId,
      denied_status: anonymous.status,
      anonymous_status: anonymous.status,
      anonymous_content_type: anonymous.contentType,
      missing_tenant_status: missingTenant.status,
      missing_tenant_content_type: missingTenant.contentType,
      allowed_status: allowed.status,
      allowed_content_type: allowed.contentType,
      anonymous_body_length: anonymous.bodyText.length,
      missing_tenant_body_length: missingTenant.bodyText.length,
      allowed_body_length: allowed.bodyText.length,
    };

    if (![401, 403].includes(anonymous.status)) {
      throw new Error(`${item.path} should return 401/403 without role`);
    }
    if (![401, 403].includes(missingTenant.status)) {
      throw new Error(`${item.path} should return 401/403 without tenant`);
    }
    if (allowed.status !== 200) {
      throw new Error(`${item.path} should return 200 with role`);
    }
  }

  return { checks, executedProbes };
}

function buildAuditPermissionProbeHeaders({ adminRole, adminApiKey, adminUserId }) {
  const apiKeyHeader = adminApiKey ? { "X-API-Key": adminApiKey } : {};
  return {
    anonymous: {
      Accept: "application/json",
      "X-User-Id": adminUserId,
    },
    missingTenant: {
      Accept: "application/json",
      "X-User-Id": adminUserId,
      "X-Role": adminRole,
      "X-Project-Key": DEFAULT_PROJECT_KEY,
      ...apiKeyHeader,
    },
    allowed: {
      Accept: "application/json",
      "X-User-Id": adminUserId,
      "X-Role": adminRole,
      "X-Project-Key": DEFAULT_PROJECT_KEY,
      "X-Tenant-Id": DEFAULT_TENANT_ID,
      ...apiKeyHeader,
    },
  };
}

async function run() {
  const options = parseArgs(process.argv.slice(2));
  const baseUrl = validateSideEffectAuthorization(options);
  const baseOrigin = new URL(baseUrl).origin;
  const outputPath = resolveRepoPath(options.output);
  const screenshotDir = resolveRepoPath(options.screenshotDir);
  const routeChecks = routeCheckProfiles[options.contractProfile];
  const selectedAliasRouteChecks = options.contractProfile === DEFAULT_CONTRACT_PROFILE ? aliasRouteChecks : [];
  const adminApiKey = readOptionalEnv(options.adminApiKeyEnv);
  const adminRole = options.adminRole || "it-admin";
  const captureScreenshots = readBooleanEnv("MEDICAL_AUDIT_FRONTEND_ACCEPTANCE_SCREENSHOTS");
  const requestedScreenshotPolicy = readOptionalEnv("MEDICAL_AUDIT_FRONTEND_ACCEPTANCE_SCREENSHOT_POLICY");
  if (requestedScreenshotPolicy !== null && !["all", "issues"].includes(requestedScreenshotPolicy)) {
    throw new Error(
      "MEDICAL_AUDIT_FRONTEND_ACCEPTANCE_SCREENSHOT_POLICY must be one of: all, issues",
    );
  }
  validateAcceptanceEvidenceOptions(options);
  const acceptanceUserId = deriveAcceptanceUserId(options.acceptanceRunId);
  const releaseGuard = loadReleaseGuardEvidence(
    options.releaseGuardReport,
    options.expectedDeploySha,
    options.acceptanceRunId,
  );
  const acceptanceHeaders = {
    "X-User-Id": acceptanceUserId,
    "X-Role": adminRole,
    "X-Project-Key": DEFAULT_PROJECT_KEY,
    "X-Tenant-Id": DEFAULT_TENANT_ID,
  };
  const screenshotPolicy = captureScreenshots ? (requestedScreenshotPolicy ?? "all") : "disabled";
  let apiCheckResult = null;
  let apiCheckError = null;
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  if (captureScreenshots) {
    fs.mkdirSync(screenshotDir, { recursive: true });
  }
  const initialReleaseIdentity = await observeReleaseIdentity({
    baseUrl,
    acceptanceHeaders,
    timeoutMs: options.timeoutMs,
  });

  const executablePath =
    readOptionalEnv("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH") ?? readOptionalEnv("CHROME_EXECUTABLE_PATH");
  const browser = await chromium.launch({
    headless: true,
    ...(executablePath ? { executablePath } : {}),
    args: ["--no-proxy-server", "--proxy-server=direct://", "--proxy-bypass-list=*"],
  });
  const checks = [];
  const aliasChecks = [];
  try {
    for (const viewport of viewports) {
      const checkGroups = [
        { contractKind: "independent", routeChecks, target: checks },
        { contractKind: "alias", routeChecks: selectedAliasRouteChecks, target: aliasChecks },
      ];
      for (const group of checkGroups) {
        for (const routeCheck of group.routeChecks) {
          const session = routeCheck.session ?? "workspace";
          const context = await browser.newContext(
            buildBrowserContextOptions(viewport, session, acceptanceHeaders),
          );
          await context.route("**/*", async (route) => {
            if (route.request().method() !== "GET") {
              await route.abort("blockedbyclient");
              return;
            }
            let requestOrigin;
            try {
              requestOrigin = new URL(route.request().url()).origin;
            } catch {
              await route.abort("blockedbyclient");
              return;
            }
            if (requestOrigin !== baseOrigin) {
              await route.abort("blockedbyclient");
              return;
            }
            await route.continue();
          });
          if (session !== "anonymous") {
            await seedWorkspaceSession(context);
          }
          const page = await context.newPage();
          const consoleErrors = [];
          const failedRequests = [];
          const successfulResponseRequests = new WeakSet();
          const successfulResponseUrls = new Set();
          const interactionErrors = [];
          page.on("console", (message) => {
            if (message.type() === "error") {
              consoleErrors.push(message.text());
            }
          });
          page.on("requestfailed", (request) => {
            const failed = {
              url: request.url(),
              method: request.method(),
              error: request.failure()?.errorText ?? "requestfailed",
            };
            if (!isIgnorableFailedRequest(failed, baseUrl)) {
              failedRequests.push(failed);
            }
          });
          page.on("response", (response) => {
            const url = response.url();
            if (
              response.request().method() === "GET"
              && response.status() >= 200
              && response.status() < 300
              && new URL(url).origin === baseOrigin
            ) {
              successfulResponseRequests.add(response.request());
            }
            if (response.status() >= 400 && url.startsWith(baseUrl)) {
              failedRequests.push({ url, status: response.status() });
            }
          });
          page.on("requestfinished", (request) => {
            if (successfulResponseRequests.has(request)) {
              successfulResponseUrls.add(request.url());
            }
          });

          let status = null;
          let error = null;
          const inputSearch = routeCheck.inputSearch ?? "";
          const url = `${baseUrl}${routeCheck.route}${inputSearch}`;
          try {
            const response = await page.goto(url, { waitUntil: "domcontentloaded", timeout: options.timeoutMs });
            status = response?.status() ?? null;
            if (session !== "anonymous") {
              await ensureWorkspaceSession(page, options.timeoutMs);
            }
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
          const rawFinalUrl = page.url();
          const observedFinalUrl = sanitizeUrl(rawFinalUrl);
          const observedFinalSearch = finalSearch(rawFinalUrl);
          const recoveredAbortedRequests = failedRequests.filter((failed) =>
            isRecoveredAbortedRequest(failed, successfulResponseUrls)
          );
          const actionableFailedRequests = failedRequests.filter((failed) =>
            !isRecoveredAbortedRequest(failed, successfulResponseUrls)
          );
          const check = {
            route: routeCheck.route,
            inputSearch,
            expectedPath: routeCheck.expectedPath ?? null,
            expectedSearch: routeCheck.expectedSearch ?? null,
            expectedChromeTitle: routeCheck.expectedChromeTitle ?? null,
            finalPath: finalPath(observedFinalUrl),
            finalSearch: observedFinalSearch,
            chromeTitle: data.chromeTitle,
            contractKind: group.contractKind,
            session,
            viewport: viewport.name,
            url: sanitizeUrl(url),
            finalUrl: observedFinalUrl,
            status,
            navigationError: error !== null,
            headingCount: data.headings.length,
            bodyTextLength: compactText(data.bodyText).length,
            fileInputCount: data.fileInputCount,
            scrollWidth: data.scrollWidth,
            clientWidth: data.clientWidth,
            horizontalOverflow: data.horizontalOverflow,
            overflowOffenders: sanitizeOverflowOffenders(data.overflowOffenders),
            interactiveOverflowOffenders: sanitizeOverflowOffenders(
              data.interactiveOverflowOffenders,
            ),
            floatingControlOcclusions: sanitizeFloatingControlOcclusions(
              data.floatingControlOcclusions,
            ),
            consoleErrorCount: consoleErrors.length,
            failedRequestCount: actionableFailedRequests.length,
            failedRequests: actionableFailedRequests.map(sanitizeFailedRequest),
            recoveredAbortedRequestCount: recoveredAbortedRequests.length,
            recoveredAbortedRequests: recoveredAbortedRequests.map(sanitizeFailedRequest),
            interactionErrorCount: interactionErrors.length,
            issues: classify(
              {
                status,
                error,
                consoleErrors,
                failedRequests: actionableFailedRequests,
                interactionErrors,
                finalUrl: observedFinalUrl,
                finalSearch: observedFinalSearch,
              },
              routeCheck,
              data,
            ),
          };
          const shouldCaptureScreenshot =
            captureScreenshots &&
            (screenshotPolicy === "all" || check.issues.length > 0 || check.horizontalOverflow);
          if (shouldCaptureScreenshot) {
            const screenshotPath = path.join(
              screenshotDir,
              screenshotFileName({
                acceptanceRunId: options.acceptanceRunId,
                contractKind: group.contractKind,
                viewport: viewport.name,
                route: routeCheck.route,
                inputSearch,
              }),
            );
            try {
              await page.screenshot({ path: screenshotPath, fullPage: false, timeout: 10_000 });
              check.screenshot = screenshotPath;
              check.screenshot_evidence = readPngEvidence(screenshotPath);
              if (check.screenshot_evidence === null) {
                check.screenshot_error = true;
              }
            } catch (caught) {
              check.screenshot_error = true;
            }
          }
          group.target.push(check);
          console.error(
            JSON.stringify({
              route: routeCheck.route,
              contract_kind: group.contractKind,
              viewport: viewport.name,
              status,
              issue_count: check.issues.length,
            }),
          );
          await page.close();
          await context.close();
        }
      }
    }
    try {
      apiCheckResult = await checkAuditLogApiPermissions({
        baseUrl,
        adminRole,
        adminApiKey,
        adminUserId: acceptanceUserId,
        timeoutMs: options.timeoutMs,
      });
    } catch (error) {
      apiCheckError = error instanceof Error ? error.message : String(error);
    }
  } finally {
    await browser.close();
  }

  const allChecks = [...checks, ...aliasChecks];
  const p0 = allChecks.flatMap((check) =>
    check.issues.filter((item) => item.severity === "P0").map((item) => ({ route: check.route, viewport: check.viewport, ...item })),
  );
  const p1 = allChecks.flatMap((check) =>
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
  const finalReleaseIdentity = await observeReleaseIdentity({
    baseUrl,
    acceptanceHeaders,
    timeoutMs: options.timeoutMs,
  });
  const releaseIdentity = validateReleaseIdentityPair(
    initialReleaseIdentity,
    finalReleaseIdentity,
    options.expectedDeploySha,
    releaseGuard.current_release_target,
  );

  const report = {
    status,
    generated_at: new Date().toISOString(),
    base_url: sanitizeUrl(baseUrl),
    contract_profile: options.contractProfile,
    side_effect_mode: "audit-log-write-enabled",
    production_side_effect: "audit-log-only",
    database_write: "audit-log-only",
    audit_log_write_expected: true,
    provider_call_status: "not_observed",
    provider_evidence_source: "outside-frontend-acceptance-scope",
    collector_provider_call_status: releaseGuard.collector_provider_call_status,
    http_methods: ["GET"],
    expected_deploy_sha: options.expectedDeploySha,
    acceptance_run_id: options.acceptanceRunId,
    acceptance_user_id: acceptanceUserId,
    release_guard: releaseGuard,
    release_identity: releaseIdentity,
    summary: {
      route_count: routeChecks.length,
      independent_page_count: routeChecks.length,
      alias_check_count: selectedAliasRouteChecks.length,
      check_count: checks.length,
      alias_execution_check_count: aliasChecks.length,
      total_execution_check_count: allChecks.length,
      viewports: viewports.map((viewport) => viewport.name),
      api_checks: apiCheckResult?.checks || { error: apiCheckError !== null },
      executed_api_probes: apiCheckResult?.executedProbes || [],
      executed_api_probe_count: apiCheckResult?.executedProbes.length || 0,
      skipped_api_probes: [],
      skipped_api_probe_count: 0,
      skipped_routes: [],
      skipped_route_count: 0,
      screenshot_capture: captureScreenshots,
      screenshot_policy: screenshotPolicy,
      p0,
      p1,
    },
    checks,
    alias_checks: aliasChecks,
  };
  fs.writeFileSync(outputPath, JSON.stringify(report, null, 2));
  console.log(JSON.stringify({ status: report.status, output: outputPath, p0_count: p0.length, p1_count: p1.length }, null, 2));
  return report.status === "pass" ? 0 : 2;
}

if (process.argv[1] && path.resolve(process.argv[1]) === __filename) {
  run()
    .then((code) => {
      process.exitCode = code;
    })
    .catch((error) => {
      console.error(error instanceof Error ? error.message : String(error));
      process.exitCode = 2;
    });
}

export {
  aliasRouteChecks,
  buildAuditPermissionProbeHeaders,
  buildBrowserContextOptions,
  classify,
  deriveAcceptanceUserId,
  finalPath,
  finalSearch,
  isFloatingLayoutPosition,
  isIgnorableFailedRequest,
  isLoginGateSnapshot,
  loadReleaseGuardEvidence,
  normalizeProductionBaseUrl,
  readPngEvidence,
  routeCheckProfiles,
  sanitizeFailedRequest,
  sanitizeUrl,
  screenshotFileName,
  validateAcceptanceEvidenceOptions,
  validateReleaseIdentityPair,
  validateSideEffectAuthorization,
  viewports,
};
