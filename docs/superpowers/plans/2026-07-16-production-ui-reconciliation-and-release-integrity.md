---
title: Production UI Reconciliation and Release Integrity Implementation Plan
doc_type: implementation-plan
module: deployment
status: superseded
superseded_by: drafts/analysis/project-reanalysis-and-gap-audit-20260813.md
created: 2026-07-16
updated: 2026-08-22
owner: self
source: human+ai
---

# Production UI Reconciliation and Release Integrity Implementation Plan

> 本计划已停用，不再作为可执行指引。当前权威状态与后续门禁见 [项目全量复盘与差异审计](../../../drafts/analysis/project-reanalysis-and-gap-audit-20260813.md)。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将生产前端、干净 `main` 与旧本地 dirty workspace 收敛为一个可审阅、可复现、可证明的新发布版本，补齐真正缺失的页面能力，并消除“SHA 正确但页面版本无法证明”的验收漏洞。

**Architecture:** 以干净 `origin/main` 为唯一发布源，不复制旧 dirty workspace，也不整支合并宽分叉；仅按路由语义移植仍有产品价值的实现。前端页面修复、验收合同、构建 manifest、静态发布原子性分成独立可拒绝批次，每批都保持可构建、可测试、可回滚。生产发布绑定 `Git SHA → frozen build manifest → remote manifest → public manifest`，生产浏览器验收同时校验最终 URL、关键结构、禁止旧文案和全页截图。

**Tech Stack:** Next.js static export、React、TypeScript、Vitest、Playwright、Python 3、pytest、Nginx、Docker Compose、rsync、SHA-256 manifest。

## Global Constraints

- 发布源只能是 fresh clean worktree 中的 `main == origin/main == approved SHA`；禁止从 `/Users/pray/project/medical_audit` dirty root 直接构建或部署。
- 当前生产基线是 `1376baef0d8d47f1e1ef60b2cec130451af5af4f`；重复部署该 SHA 不会改变页面。
- `/knowledge-base`、`/graph`、`/agent-market`、`/knowledge-query` 的 clean-main 实现优于旧本地实现；禁止用旧文件覆盖，只允许窄范围视觉提取并保留权限、项目范围和 runtime 状态合同。
- 不新增 dependency；复用现有 `ReplicaPageHeader`、`ReplicaMetric`、`ReplicaNotice`、`ReplicaRuntimeBadge`、API client 和 API types。
- UI 读取失败必须显示 `loading / empty / degraded / error`；不得把 fixture 或 seed 数据伪装成生产真实数据。
- 页面 GET 可能产生 audit log；生产浏览器验收只允许经单独授权的 `audit-log-only` 写入。
- schema、provider/query、review、项目创建、文档上传、对象存储、治理和索引写入必须分别授权；不得由前端视觉验收隐式触发。
- merge、生产部署、Nginx reload、production write UAT、远端分支删除均需单独明确授权。
- 所有生产报告必须保留 `production_side_effect`、`database_write`、`provider_call_status`、目标 SHA、最终 URL 和 manifest hash。

---

## Verified Current State

- Google Chrome 已直接检查生产 `/chat`、`/fund-compliance`、`/knowledge-base`、`/documents`、`/graph`、`/rules`、`/remediation`、`/fund-compliance/review`。
- `/rules` 仍显示硬编码的 `2,546 / 49,051 / 128`，没有规则清单、运行快照、来源覆盖和发布门禁 runtime。
- `/remediation` 最终跳转到 `/medical-audit`，没有独立整改台账；导航和页面合同不一致。
- `/fund-compliance/review` 只有三张模板卡和跳转入口，没有本地旧实现中的四阶段复核工作流。
- `/documents` 有检索和分类，但没有个人材料权限、上传历史、治理和索引区。
- `/knowledge-base` 与 `/graph` 已是 clean-main 的较新实现，不能被旧本地页面替换。
- clean release worktree 的 `web/out` 与公网静态文件 `87/87` SHA-256 一致；当前不是 rsync 漏文件。
- dirty root 位于 `main@6429b34278cf6d35e3477edc6bc3e5032df652f2`，比生产源码祖先基线落后约 191 commits；包含 15 个 tracked Web 修改和 2 个未跟踪源码，补丁不能直接应用到 clean main。
- 现有 hardened acceptance 把四个兼容重定向当成独立页面 PASS：`/workspace → /chat`、`/remediation → /medical-audit`、`/findings → /medical-audit`、`/knowledge-query → /documents`。
- 公网 HTML 当前为 `Cache-Control: public, max-age=300, must-revalidate`，仓库 Nginx fragment 要求 `no-store, no-cache, must-revalidate`，存在配置漂移。

## Target Route Decision

| Route | Decision | Release batch |
|---|---|---|
| `/rules` | 在现有 Replica 视觉中接入真实 `fetchRulesWorkbench()`，删除硬编码指标 | Batch A |
| `/remediation` | 恢复独立只读整改工作台；不再跳转 `/medical-audit` | Batch A |
| `/archive` | 接入 `fetchArchiveWorkbench()`，保留归档、验签和保留策略 runtime | Batch A |
| `/fund-compliance` | 保留 clean-main shared workbench，增强当前疑点、规则、报告和闭环信息 | Batch B |
| `/fund-compliance/review` | 增加单据审查、费用表单、规则复核、底稿输出四阶段信息架构 | Batch B |
| `/guided-check` | 增强证据、风险、时间线和 AI 问题，不复制旧整页 | Batch B |
| `/documents` | 先交付只读 permissions/uploads/history；写动作单独门禁 | Batch C/D |
| `/knowledge-base` | 保留 clean-main 实现，增加防回退测试 | Preservation |
| `/graph` | 保留双视图、项目选择、权限和 degraded/error 状态 | Preservation |
| `/agent-market` | 保留权限、项目范围、并发和重复安装保护 | Preservation |
| `/workspace` | 明确为 `/chat` alias，不计作独立页面 | Alias contract |
| `/findings` | 明确为 `/medical-audit` alias，直至产品决定恢复独立疑点页 | Alias contract |
| `/knowledge-query` | 明确为 `/documents` alias，不计作独立页面 | Alias contract |
| `/login` | 纳入独立 anonymous acceptance | Acceptance |
| `/medical-audit` | 纳入独立 workspace acceptance | Acceptance |

## File Structure Map

### New focused files

- `web/src/components/replica/replica-rules-workbench.tsx`: rules runtime state and rendering only.
- `web/src/components/replica/replica-rules-workbench.test.tsx`: rules loading/ready/empty/error/seed tests.
- `web/src/components/replica/replica-remediation-workbench.tsx`: remediation read-only runtime and rendering only.
- `web/src/components/replica/replica-remediation-workbench.test.tsx`: remediation route and state tests.
- `web/src/components/replica/replica-archive-workbench.tsx`: archive runtime, signatures and policy rendering.
- `web/src/components/replica/replica-archive-workbench.test.tsx`: archive state tests.
- `web/src/components/documents/personal-material-read-panel.tsx`: GET-only permissions and upload history panel.
- `web/src/components/documents/personal-material-read-panel.test.tsx`: read-only document panel contract.
- `web/src/components/documents/personal-material-actions.tsx`: explicitly user-triggered upload/govern/index actions.
- `web/src/components/documents/personal-material-actions.test.tsx`: permission and no-implicit-write tests.
- `scripts/build-web-release-manifest.py`: deterministic Web release manifest generator.
- `tests/fixtures/web-release-manifest/`: small manifest fixture tree.
- `drafts/analysis/production-ui-route-reconciliation-draft-20260716.md`: route-by-route source/production/decision/evidence matrix.

### Existing files to modify

- `web/src/app/(workspace)/rules/page.tsx`
- `web/src/app/(workspace)/remediation/page.tsx`
- `web/src/app/(workspace)/archive/page.tsx`
- `web/src/app/(workspace)/documents/page.tsx`
- `web/src/components/replica/compatibility-workbenches.tsx`
- `web/src/components/replica/compatibility-workbenches.test.tsx`
- `web/src/app/(workspace)/documents/page.test.tsx`
- `web/src/app/(workspace)/graph/page.test.tsx`
- `web/src/app/(workspace)/knowledge-base/page.test.tsx`
- `web/src/components/replica/replica-agent-directory.test.tsx`
- `scripts/run-production-frontend-acceptance.mjs`
- `scripts/run-production-frontend-acceptance-gate.mjs`
- `scripts/deploy-tencent-cloud-production.py`
- `scripts/audit-tencent-cloud-deployment-state.py`
- `configs/deploy/tencent-cloud/nginx-audit-server.conf`
- `tests/knowledge_query/test_scripts.py`
- `package.json`
- `docs/workflows/workflow-tencent-cloud-audit-deployment-stable.md`

---

### Task 1: Establish the clean reconciliation branch and evidence matrix

**Files:**
- Create: `drafts/analysis/production-ui-route-reconciliation-draft-20260716.md`
- Read only: `/Users/pray/project/medical_audit/web/src/**`
- Read only: `/Users/pray/project/medical_audit_release_reconciliation_20260714/web/src/**`

**Interfaces:**
- Consumes: production baseline `1376baef0d8d47f1e1ef60b2cec130451af5af4f`, PPT closure matrix, Chrome evidence.
- Produces: one row per route with `clean_main_source`, `dirty_source`, `production_observation`, `decision`, `write_boundary`, `acceptance_contract`.

- [ ] **Step 1: Create a fresh branch from remote main**

```bash
git fetch origin main
git switch -c codex/production-ui-reconciliation-20260716 origin/main
git status --short --branch
```

Expected: branch starts clean; `HEAD == origin/main`; no dirty-root files are copied.

- [ ] **Step 2: Record the dirty Web delta without applying it**

```bash
git -C /Users/pray/project/medical_audit diff --stat -- web/src
git -C /Users/pray/project/medical_audit diff --name-status -- web/src
git diff --no-index --stat \
  /Users/pray/project/medical_audit_release_reconciliation_20260714/web/src \
  /Users/pray/project/medical_audit/web/src
```

Expected: evidence records 15 tracked changes, 2 untracked source files and broad file-level divergence; no patch is applied.

- [ ] **Step 3: Create the reconciliation matrix with frontmatter**

The document must start with:

```yaml
---
title: 生产前端逐路由收敛矩阵
doc_type: analysis-draft
module: web-release
status: active
created: 2026-07-16
updated: 2026-07-16
owner: self
source: chrome+repository+production-readonly
---
```

Each route row must use exactly one decision: `port-semantically`, `preserve-clean-main`, `explicit-alias`, `blocked-by-write-authorization`.

- [ ] **Step 4: Verify the matrix has no undecided routes**

```bash
python3 - <<'PY'
from pathlib import Path

text = Path("drafts/analysis/production-ui-route-reconciliation-draft-20260716.md").read_text(encoding="utf-8")
blocked_tokens = ["TB" + "D", "TO" + "DO", "待" + "决定", "unknown" + "-decision"]
matches = [token for token in blocked_tokens if token in text]
raise SystemExit(f"unresolved markers: {matches}" if matches else 0)
PY
```

Expected: no matches.

- [ ] **Step 5: Commit the evidence-only baseline**

```bash
git add drafts/analysis/production-ui-route-reconciliation-draft-20260716.md
git commit -m "docs: freeze production UI reconciliation matrix"
```

---

### Task 2: Make frontend acceptance prove route identity and visual evidence

**Files:**
- Modify: `scripts/run-production-frontend-acceptance.mjs`
- Modify: `scripts/run-production-frontend-acceptance-gate.mjs`
- Modify: `tests/knowledge_query/test_scripts.py`

**Interfaces:**
- Consumes: route entries with `route`, `expectedPath`, `session`, required and forbidden text.
- Produces: `17` independent page contracts, `3` explicit alias contracts, every successful page screenshot, exact final-path verification.

- [ ] **Step 1: Write a failing route-identity test**

Add to `tests/knowledge_query/test_scripts.py`:

```python
def test_production_frontend_acceptance_rejects_unexpected_final_path() -> None:
    runner_path = Path("scripts/run-production-frontend-acceptance.mjs").resolve()
    program = (
        "import { classify } from " + json.dumps(runner_path.as_uri()) + "; "
        "const issues = classify("
        "{ status: 200, error: null, consoleErrors: [], failedRequests: [], "
        "interactionErrors: [], finalUrl: 'https://audit.example.test/medical-audit' }, "
        "{ route: '/remediation', expectedPath: '/remediation' }, "
        "{ bodyText: 'x'.repeat(120), headings: ['整改台账'], controlText: [], "
        "fileInputCount: 0, horizontalOverflow: false, scrollWidth: 100, "
        "clientWidth: 100, overflowOffenders: [] }); "
        "console.log(JSON.stringify(issues));"
    )
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", program],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert '"type":"unexpected-final-path"' in result.stdout
```

- [ ] **Step 2: Run the focused test and verify RED**

```bash
uv run pytest tests/knowledge_query/test_scripts.py::test_production_frontend_acceptance_rejects_unexpected_final_path -q
```

Expected: FAIL because `classify()` does not inspect `finalUrl`.

- [ ] **Step 3: Add exact path classification**

Change the check passed to `classify()` so it contains `finalUrl`, then add:

```javascript
function finalPath(url) {
  try {
    return new URL(url).pathname.replace(/\/+$/, "") || "/";
  } catch {
    return null;
  }
}

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
```

- [ ] **Step 4: Split independent pages from aliases**

Use independent entries for `/login`, `/medical-audit`, `/rules`, `/remediation` and the other real pages. Represent aliases separately:

```javascript
const aliasRouteChecks = [
  { route: "/workspace", expectedPath: "/chat" },
  { route: "/findings", expectedPath: "/medical-audit" },
  { route: "/knowledge-query", expectedPath: "/documents" },
];
```

The report must expose `independent_page_count`, `alias_check_count`, and `alias_checks`; aliases must not inflate `route_count`.

- [ ] **Step 5: Add anonymous login coverage and exact remediation coverage**

Add route properties:

```javascript
{ route: "/login", expectedPath: "/login", session: "anonymous", requiredText: [/登录工作台/], requiredControlText: [/(^|\s)登录($|\s)/] }
{ route: "/medical-audit", expectedPath: "/medical-audit", session: "workspace", requiredText: [/医保审计/, /智能审计/] }
{ route: "/remediation", expectedPath: "/remediation", session: "workspace", requiredText: [/整改/, /补证/, /关闭门禁/] }
```

Only call `seedWorkspaceSession()` when `session !== "anonymous"`.

- [ ] **Step 6: Capture every passing screenshot when enabled**

Replace issue-only capture with:

```javascript
const screenshotPolicy = readOptionalEnv("MEDICAL_AUDIT_FRONTEND_ACCEPTANCE_SCREENSHOT_POLICY") ?? "all";
const shouldCaptureScreenshot =
  captureScreenshots &&
  (screenshotPolicy === "all" || check.issues.length > 0 || check.horizontalOverflow);
```

Allowed values are `all` and `issues`; any other value must fail before browser launch.

- [ ] **Step 7: Make the gate reject missing screenshots and path evidence**

For a report with `screenshot_capture=true` and policy `all`, require every independent route/viewport check to have a non-empty `screenshot` and exact `finalPath` evidence.

- [ ] **Step 8: Run tests**

```bash
uv run pytest tests/knowledge_query/test_scripts.py -k 'production_frontend_acceptance' -q
node --check scripts/run-production-frontend-acceptance.mjs
node --check scripts/run-production-frontend-acceptance-gate.mjs
```

Expected: all focused tests PASS.

- [ ] **Step 9: Commit the acceptance contract**

```bash
git add scripts/run-production-frontend-acceptance.mjs scripts/run-production-frontend-acceptance-gate.mjs tests/knowledge_query/test_scripts.py
git commit -m "test: require exact production UI route identity"
```

---

### Task 3: Replace the hard-coded rules page with the real read-only workbench

**Files:**
- Create: `web/src/components/replica/replica-rules-workbench.tsx`
- Create: `web/src/components/replica/replica-rules-workbench.test.tsx`
- Modify: `web/src/app/(workspace)/rules/page.tsx`

**Interfaces:**
- Consumes: `fetchRulesWorkbench(): Promise<RulesWorkbenchResponse>`.
- Produces: runtime metrics, rule library, source coverage, run snapshots and control gates; never performs POST.

- [ ] **Step 1: Write the failing component test**

```tsx
it("renders runtime rules instead of the retired hard-coded totals", async () => {
  fetchRulesWorkbenchMock.mockResolvedValue(rulesResponse);
  render(<ReplicaRulesWorkbench />);
  expect(await screen.findByText("runtime-rule-001")).toBeInTheDocument();
  expect(screen.getByText("字段可运行")).toBeInTheDocument();
  expect(screen.getByText("SqlAlchemyRulesWorkbenchStore")).toBeInTheDocument();
  expect(screen.queryByText("2,546")).not.toBeInTheDocument();
});

it("shows a degraded state when the rules API fails", async () => {
  fetchRulesWorkbenchMock.mockRejectedValue(new Error("rules unavailable"));
  render(<ReplicaRulesWorkbench />);
  expect(await screen.findByText("规则工作台暂不可用")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run the component test and verify RED**

```bash
pnpm --filter medical-audit-web test -- replica-rules-workbench.test.tsx
```

Expected: FAIL because the component does not exist.

- [ ] **Step 3: Implement the runtime state**

Use exactly this state contract:

```tsx
type RulesState =
  | { readonly status: "loading"; readonly data: null }
  | { readonly status: "ready"; readonly data: RulesWorkbenchResponse }
  | { readonly status: "empty"; readonly data: RulesWorkbenchResponse }
  | { readonly status: "error"; readonly data: null };

const [state, setState] = useState<RulesState>({ status: "loading", data: null });

useEffect(() => {
  let active = true;
  fetchRulesWorkbench()
    .then((data) => {
      if (!active) return;
      const empty = data.rule_library_items.length === 0 && data.run_snapshots.length === 0;
      setState({ status: empty ? "empty" : "ready", data });
    })
    .catch(() => {
      if (active) setState({ status: "error", data: null });
    });
  return () => {
    active = false;
  };
}, []);
```

Render `metrics.rule_count`, `enabled_rule_count`, `pending_rule_count`, `rule_library_items`, `source_coverages`, `run_snapshots`, and `control_gates`. Display `store.backend`, `evidence_grade`, and `production_side_effect` through the existing Replica status components.

- [ ] **Step 4: Make the route a thin wrapper**

```tsx
import { ReplicaRulesWorkbench } from "@/components/replica/replica-rules-workbench";

export default function RulesPage() {
  return <ReplicaRulesWorkbench />;
}
```

- [ ] **Step 5: Run validation**

```bash
pnpm --filter medical-audit-web test -- replica-rules-workbench.test.tsx
pnpm web:typecheck
pnpm web:lint
```

Expected: PASS; no hard-coded `2,546`, `49,051`, or `128` remains in the route source.

- [ ] **Step 6: Commit**

```bash
git add 'web/src/app/(workspace)/rules/page.tsx' web/src/components/replica/replica-rules-workbench.tsx web/src/components/replica/replica-rules-workbench.test.tsx
git commit -m "feat: connect rules page to runtime evidence"
```

---

### Task 4: Restore independent remediation and runtime archive pages

**Files:**
- Create: `web/src/components/replica/replica-remediation-workbench.tsx`
- Create: `web/src/components/replica/replica-remediation-workbench.test.tsx`
- Create: `web/src/components/replica/replica-archive-workbench.tsx`
- Create: `web/src/components/replica/replica-archive-workbench.test.tsx`
- Modify: `web/src/app/(workspace)/remediation/page.tsx`
- Modify: `web/src/app/(workspace)/archive/page.tsx`

**Interfaces:**
- Consumes: `fetchRemediationWorkbench()` and `fetchArchiveWorkbench()`; both are GET-only.
- Produces: exact `/remediation` page identity and archive runtime evidence.

- [ ] **Step 1: Write the failing remediation route test**

```tsx
it("keeps remediation on its own route and renders closure gates", async () => {
  fetchRemediationWorkbenchMock.mockResolvedValue(remediationResponse);
  render(<ReplicaRemediationWorkbench />);
  expect(await screen.findByText("整改台账")).toBeInTheDocument();
  expect(screen.getByText("补证请求")).toBeInTheDocument();
  expect(screen.getByText("关闭门禁")).toBeInTheDocument();
  expect(screen.getByText("SqlAlchemyRemediationWorkbenchStore")).toBeInTheDocument();
});
```

- [ ] **Step 2: Write the failing archive runtime test**

```tsx
it("renders archive packages, signatures, policies and audit runs from the API", async () => {
  fetchArchiveWorkbenchMock.mockResolvedValue(archiveResponse);
  render(<ReplicaArchiveWorkbench />);
  expect(await screen.findByText("archive-package-001")).toBeInTheDocument();
  expect(screen.getByText("验签通过")).toBeInTheDocument();
  expect(screen.getByText("SqlAlchemyArchiveWorkbenchStore")).toBeInTheDocument();
});
```

- [ ] **Step 3: Run tests and verify RED**

```bash
pnpm --filter medical-audit-web test -- replica-remediation-workbench.test.tsx replica-archive-workbench.test.tsx
```

Expected: FAIL because the components do not exist.

- [ ] **Step 4: Implement remediation state and rendering**

Use the same four-state pattern as Task 3. Render:

```tsx
const metrics = [
  ["整改事项", data.metrics.case_count],
  ["整改中", data.metrics.active_case_count],
  ["待补证", data.metrics.pending_evidence_count],
  ["阻断门禁", data.metrics.blocked_gate_count],
] as const;
```

The page must display `remediation_cases`, `evidence_requests`, `closure_gates`, and `timeline`. Links may navigate to existing read-only destinations only; no update, review or closure POST is added in this task.

- [ ] **Step 5: Implement archive state and rendering**

Render `archive_packages`, `audit_runs`, `signature_items`, `policy_items`, and `timeline`; show the backend and latest archive-run status. Empty API arrays must produce a real empty state, not `portal-data` fallback.

- [ ] **Step 6: Replace the redirect and static archive wrapper**

```tsx
// remediation/page.tsx
import { ReplicaRemediationWorkbench } from "@/components/replica/replica-remediation-workbench";
export default function RemediationPage() {
  return <ReplicaRemediationWorkbench />;
}

// archive/page.tsx
import { ReplicaArchiveWorkbench } from "@/components/replica/replica-archive-workbench";
export default function ArchivePage() {
  return <ReplicaArchiveWorkbench />;
}
```

- [ ] **Step 7: Validate**

```bash
pnpm --filter medical-audit-web test -- replica-remediation-workbench.test.tsx replica-archive-workbench.test.tsx
pnpm web:typecheck
pnpm web:lint
```

Expected: PASS; `redirect("/medical-audit")` no longer exists in `remediation/page.tsx`.

- [ ] **Step 8: Commit**

```bash
git add 'web/src/app/(workspace)/remediation/page.tsx' 'web/src/app/(workspace)/archive/page.tsx' web/src/components/replica/replica-remediation-workbench.tsx web/src/components/replica/replica-remediation-workbench.test.tsx web/src/components/replica/replica-archive-workbench.tsx web/src/components/replica/replica-archive-workbench.test.tsx
git commit -m "feat: restore remediation and archive workbenches"
```

---

### Task 5: Enrich the fund-compliance and guided workflow without replacing clean-main architecture

**Files:**
- Modify: `web/src/components/replica/compatibility-workbenches.tsx`
- Modify: `web/src/components/replica/compatibility-workbenches.test.tsx`

**Interfaces:**
- Consumes: existing `CompatibilityRuntime` from findings, rules, reports and search GET APIs.
- Produces: four-stage review workflow plus evidence/risk/timeline summaries; no new POST.

- [ ] **Step 1: Add failing workflow tests**

```tsx
it("renders the four review stages from the shared runtime", async () => {
  mockBackendReads();
  render(<FundComplianceReviewWorkbench />);
  expect(await screen.findByText("单据审查")).toBeInTheDocument();
  expect(screen.getByText("费用表单")).toBeInTheDocument();
  expect(screen.getByText("规则复核")).toBeInTheDocument();
  expect(screen.getByText("底稿输出")).toBeInTheDocument();
  expect(screen.getByText("字段可运行")).toBeInTheDocument();
});

it("does not create a project, review task or report while rendering", async () => {
  mockBackendReads();
  render(<FundComplianceReviewWorkbench />);
  await screen.findByText("单据审查");
  expect(createAuditProjectMock).not.toHaveBeenCalled();
  expect(createReviewTaskMock).not.toHaveBeenCalled();
  expect(createReportDraftMock).not.toHaveBeenCalled();
});
```

- [ ] **Step 2: Run RED**

```bash
pnpm --filter medical-audit-web test -- compatibility-workbenches.test.tsx
```

- [ ] **Step 3: Add a deterministic stage model**

```tsx
const reviewStages = [
  { id: "records", label: "单据审查", href: "/medical-audit", status: findingsStatus },
  { id: "forms", label: "费用表单", href: "/analytics", status: reportsStatus },
  { id: "rules", label: "规则复核", href: "/rules", status: rulesStatus },
  { id: "workpaper", label: "底稿输出", href: "/reports", status: reportsStatus },
] as const;
```

Status values must derive from API readiness and counts; they must not be hard-coded to complete.

- [ ] **Step 4: Enrich fund compliance and guided check**

Add sections for current pending findings, blocking control gates, report readiness and the existing guided timeline. Preserve the existing `runtimeActions`, `ReplicaRuntimeBadge`, route links and fallback/error behavior.

- [ ] **Step 5: Validate**

```bash
pnpm --filter medical-audit-web test -- compatibility-workbenches.test.tsx
pnpm web:typecheck
pnpm web:lint
```

- [ ] **Step 6: Commit**

```bash
git add web/src/components/replica/compatibility-workbenches.tsx web/src/components/replica/compatibility-workbenches.test.tsx
git commit -m "feat: enrich medical audit review workflow"
```

---

### Task 6: Add the GET-only personal-material surface to documents

**Files:**
- Create: `web/src/components/documents/personal-material-read-panel.tsx`
- Create: `web/src/components/documents/personal-material-read-panel.test.tsx`
- Modify: `web/src/app/(workspace)/documents/page.tsx`
- Modify: `web/src/app/(workspace)/documents/page.test.tsx`

**Interfaces:**
- Consumes: `fetchDocumentPermissions()` and `fetchDocumentUploads()` only.
- Produces: role capability summary and visible upload history; no file chooser and no POST.

- [ ] **Step 1: Write failing GET-only tests**

```tsx
it("loads document permissions and personal upload history without writing", async () => {
  fetchDocumentPermissionsMock.mockResolvedValue(permissionsResponse);
  fetchDocumentUploadsMock.mockResolvedValue(uploadListResponse);
  render(<PersonalMaterialReadPanel />);
  expect(await screen.findByText("个人材料")).toBeInTheDocument();
  expect(screen.getByText("document-upload-001.pdf")).toBeInTheDocument();
  expect(fetchDocumentPermissionsMock).toHaveBeenCalledTimes(1);
  expect(fetchDocumentUploadsMock).toHaveBeenCalledTimes(1);
  expect(uploadPersonalDocumentMock).not.toHaveBeenCalled();
  expect(updateDocumentUploadGovernanceMock).not.toHaveBeenCalled();
  expect(indexPersonalDocumentMock).not.toHaveBeenCalled();
});
```

- [ ] **Step 2: Run RED**

```bash
pnpm --filter medical-audit-web test -- personal-material-read-panel.test.tsx
```

- [ ] **Step 3: Implement GET-only state**

```tsx
useEffect(() => {
  let active = true;
  Promise.all([fetchDocumentPermissions(), fetchDocumentUploads()])
    .then(([permissions, uploads]) => {
      if (active) setState({ status: "ready", permissions, uploads });
    })
    .catch(() => {
      if (active) setState({ status: "error", permissions: null, uploads: null });
    });
  return () => {
    active = false;
  };
}, []);
```

Render `can_upload_personal`, `can_read_all_personal_uploads`, `can_govern_personal_uploads`, file name, created time, governance status, security status, index status and chunk count. Do not expose `storage_path`, raw SHA in normal UI, or any signed URL.

- [ ] **Step 4: Mount the panel under the existing search experience**

Keep the clean-main search, source catalog, search history and AI search UI unchanged. Add a dedicated `个人材料` section after the source-collection summary.

- [ ] **Step 5: Validate**

```bash
pnpm --filter medical-audit-web test -- personal-material-read-panel.test.tsx documents/page.test.tsx
pnpm web:typecheck
pnpm web:lint
```

- [ ] **Step 6: Commit**

```bash
git add 'web/src/app/(workspace)/documents/page.tsx' 'web/src/app/(workspace)/documents/page.test.tsx' web/src/components/documents/personal-material-read-panel.tsx web/src/components/documents/personal-material-read-panel.test.tsx
git commit -m "feat: expose read-only personal material status"
```

---

### Task 7: Add explicitly triggered document write controls behind backend permissions

**Files:**
- Create: `web/src/components/documents/personal-material-actions.tsx`
- Create: `web/src/components/documents/personal-material-actions.test.tsx`
- Modify: `web/src/components/documents/personal-material-read-panel.tsx`

**Interfaces:**
- Consumes: `uploadPersonalDocument`, `updateDocumentUploadGovernance`, `indexPersonalDocument` after a unique user action.
- Produces: permission-scoped buttons; rendering and page navigation perform zero writes.

- [ ] **Step 1: Write failing permission tests**

```tsx
it("hides all write controls when backend permissions are false", () => {
  render(<PersonalMaterialActions permissions={deniedPermissions} uploads={[]} onChanged={vi.fn()} />);
  expect(screen.queryByLabelText("上传个人材料")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "批准入索引" })).not.toBeInTheDocument();
});

it("does not write until the user chooses a file", () => {
  render(<PersonalMaterialActions permissions={uploadPermissions} uploads={[]} onChanged={vi.fn()} />);
  expect(uploadPersonalDocumentMock).not.toHaveBeenCalled();
  expect(updateDocumentUploadGovernanceMock).not.toHaveBeenCalled();
  expect(indexPersonalDocumentMock).not.toHaveBeenCalled();
});
```

- [ ] **Step 2: Run RED**

```bash
pnpm --filter medical-audit-web test -- personal-material-actions.test.tsx
```

- [ ] **Step 3: Implement permission-gated controls**

```tsx
const canUpload = permissions.can_upload_personal;
const canGovern = permissions.can_govern_personal_uploads;

async function handleUpload(file: File) {
  setPendingAction("upload");
  try {
    await uploadPersonalDocument(file);
    await onChanged();
  } finally {
    setPendingAction(null);
  }
}
```

Governance and indexing handlers must require one unique button click, disable while pending, surface the exact API error, and refresh through `fetchDocumentUploads()` after success. Do not auto-index after upload and do not swallow errors.

- [ ] **Step 4: Add write-boundary tests**

Test unauthorized role, double click while pending, rejected governance, blocked index, and successful refresh. Assert every API call receives the exact upload ID and governance payload.

- [ ] **Step 5: Validate locally only**

```bash
pnpm --filter medical-audit-web test -- personal-material-actions.test.tsx personal-material-read-panel.test.tsx documents/page.test.tsx
pnpm web:typecheck
pnpm web:lint
```

Expected: PASS; no production API is called.

- [ ] **Step 6: Commit code without running production write UAT**

```bash
git add web/src/components/documents/personal-material-actions.tsx web/src/components/documents/personal-material-actions.test.tsx web/src/components/documents/personal-material-read-panel.tsx
git commit -m "feat: add permission-gated personal material actions"
```

---

### Task 8: Add preservation tests for pages that must not regress

**Files:**
- Modify: `web/src/app/(workspace)/graph/page.test.tsx`
- Modify: `web/src/app/(workspace)/knowledge-base/page.test.tsx`
- Modify: `web/src/components/replica/replica-agent-directory.test.tsx`
- Modify: `web/src/lib/replica-adapters.test.ts`

**Interfaces:**
- Consumes: current clean-main graph, knowledge catalog and agent permission behavior.
- Produces: explicit rejection of old dirty-root regressions.

- [ ] **Step 1: Lock graph behavior**

Add assertions for exact tabs `知识依据` and `项目证据链`, project selection before project view, role/project invalidation, empty/error/degraded/retry, and `fetchGraphWorkbench({ view: "project", projectKey })`.

- [ ] **Step 2: Lock knowledge-base behavior**

Assert catalog comes from `fetchKnowledgeBaseCatalog()`, internal `source_collection` and access codes are not rendered as primary labels, and document/chat/graph links retain the selected source collection.

- [ ] **Step 3: Lock agent-market behavior**

Assert manage permission, project scope, duplicate install protection and concurrent pending-state protection remain. No test may accept direct unguarded `createAuditAgent()` from a catalog card.

- [ ] **Step 4: Run preservation tests**

```bash
pnpm --filter medical-audit-web test -- graph/page.test.tsx knowledge-base/page.test.tsx replica-agent-directory.test.tsx replica-adapters.test.ts
```

Expected: PASS on clean-main behavior.

- [ ] **Step 5: Commit**

```bash
git add 'web/src/app/(workspace)/graph/page.test.tsx' 'web/src/app/(workspace)/knowledge-base/page.test.tsx' web/src/components/replica/replica-agent-directory.test.tsx web/src/lib/replica-adapters.test.ts
git commit -m "test: protect current graph knowledge and agent contracts"
```

---

### Task 9: Bind every static build to a deterministic release manifest

**Files:**
- Create: `scripts/build-web-release-manifest.py`
- Create: `tests/fixtures/web-release-manifest/index.html`
- Create: `tests/fixtures/web-release-manifest/_next/static/app.js`
- Modify: `tests/knowledge_query/test_scripts.py`
- Modify: `package.json`

**Interfaces:**
- Consumes: clean Git SHA, `pnpm-lock.yaml`, `web/out`, allowlisted `NEXT_PUBLIC_*` values.
- Produces: `web/out/release-manifest.json` with hashes for every other public file.

- [ ] **Step 1: Write failing manifest tests**

```python
def test_web_release_manifest_is_deterministic_and_secret_safe(tmp_path: Path) -> None:
    source = Path("tests/fixtures/web-release-manifest")
    web_out = tmp_path / "out"
    shutil.copytree(source, web_out)
    output = web_out / "release-manifest.json"
    command = [
        "python3",
        "scripts/build-web-release-manifest.py",
        "--web-out",
        str(web_out),
        "--source-sha",
        "a" * 40,
        "--output",
        str(output),
    ]
    first = subprocess.run(command, check=False, capture_output=True, text=True)
    assert first.returncode == 0, first.stderr
    first_bytes = output.read_bytes()
    second = subprocess.run(command, check=False, capture_output=True, text=True)
    assert second.returncode == 0, second.stderr
    assert output.read_bytes() == first_bytes
    payload = json.loads(first_bytes)
    assert payload["source_sha"] == "a" * 40
    assert [item["path"] for item in payload["files"]] == ["_next/static/app.js", "index.html"]
    assert "release-manifest.json" not in first_bytes.decode("utf-8")
```

- [ ] **Step 2: Run RED**

```bash
uv run pytest tests/knowledge_query/test_scripts.py::test_web_release_manifest_is_deterministic_and_secret_safe -q
```

- [ ] **Step 3: Implement the generator**

The manifest must use this shape:

```python
payload = {
    "format": "medical-audit-web-release-manifest-v1",
    "source_sha": source_sha,
    "lockfile_sha256": sha256_file(repo_root / "pnpm-lock.yaml"),
    "node_version": node_version,
    "pnpm_version": pnpm_version,
    "public_build_variables": {
        key: value for key, value in sorted(os.environ.items()) if key.startswith("NEXT_PUBLIC_")
    },
    "files": [
        {"path": path.as_posix(), "size_bytes": file_path.stat().st_size, "sha256": sha256_file(file_path)}
        for path, file_path in sorted(public_files)
    ],
}
```

Exclude the output manifest itself, reject a dirty source SHA, sort paths bytewise, serialize with `sort_keys=True`, and never include environment keys outside `NEXT_PUBLIC_*`.

- [ ] **Step 4: Add a frozen build script**

Add to root `package.json`:

```json
"web:build:release": "pnpm web:build:static && uv run python scripts/build-web-release-manifest.py --web-out web/out --source-sha-env MEDICAL_AUDIT_DEPLOY_SHA --output web/out/release-manifest.json"
```

- [ ] **Step 5: Run tests and a real clean build**

```bash
uv run pytest tests/knowledge_query/test_scripts.py -k 'web_release_manifest' -q
MEDICAL_AUDIT_DEPLOY_SHA="$(git rev-parse HEAD)" pnpm web:build:release
jq -e --arg sha "$(git rev-parse HEAD)" '.source_sha == $sha and (.files | length > 80)' web/out/release-manifest.json
```

Expected: build PASS; manifest source SHA matches HEAD; no file hash mismatch.

- [ ] **Step 6: Commit**

```bash
git add scripts/build-web-release-manifest.py tests/fixtures/web-release-manifest tests/knowledge_query/test_scripts.py package.json
git commit -m "build: bind static output to a release manifest"
```

---

### Task 10: Make static deployment versioned, verified and cache-correct

**Files:**
- Modify: `scripts/deploy-tencent-cloud-production.py`
- Modify: `scripts/audit-tencent-cloud-deployment-state.py`
- Modify: `configs/deploy/tencent-cloud/nginx-audit-server.conf`
- Modify: `tests/knowledge_query/test_scripts.py`
- Modify: `docs/workflows/workflow-tencent-cloud-audit-deployment-stable.md`

**Interfaces:**
- Consumes: `web/out/release-manifest.json` bound to the approved SHA.
- Produces: remote versioned release, atomic `current` link, public manifest proof, cache-header proof and rollback target.

- [ ] **Step 1: Write failing deployment tests**

Add tests asserting:

```python
assert "release-manifest.json" in deploy_script
assert "web/releases" in deploy_script
assert "current.next" in deploy_script
assert "mv -Tf" in deploy_script
assert "public_manifest_sha256" in audit_script
assert "html_cache_control" in audit_script
```

Also execute `_validate_local_state()` against a fixture where manifest SHA differs from `approved_sha`; expect `DeployError("web release manifest source SHA does not match approved SHA")`.

- [ ] **Step 2: Run RED**

```bash
uv run pytest tests/knowledge_query/test_scripts.py -k 'release_manifest or versioned_static or cache_control' -q
```

- [ ] **Step 3: Reject stale `--skip-web-build` output**

Before any SSH command, parse `web/out/release-manifest.json` and require:

```python
manifest["format"] == "medical-audit-web-release-manifest-v1"
manifest["source_sha"] == config.approved_sha
verify_manifest_files(config.repo_root / "web/out", manifest) == []
```

- [ ] **Step 4: Sync into a versioned directory and switch atomically**

Use remote paths under the existing bind mount:

```bash
release_root="$remote_web_dir/releases"
incoming="$release_root/$approved_sha.incoming"
release="$release_root/$approved_sha"
mkdir -p "$release_root"
rm -rf "$incoming"
mkdir -p "$incoming"
```

Rsync to `incoming`, run a remote Python manifest verifier, rename `incoming` to the immutable SHA directory, create `current.next -> releases/$approved_sha`, then `mv -Tf current.next current`. Nginx root must be `/var/www/audit/current`; hashed assets and HTML remain inside the same mounted parent.

- [ ] **Step 5: Reconcile Nginx cache policy without printing secrets**

Update the controlled server fragment so:

```nginx
location /_next/static/ {
    root /var/www/audit/current;
    try_files $uri =404;
    add_header Cache-Control "public, max-age=31536000, immutable" always;
}

location / {
    root /var/www/audit/current;
    try_files $uri $uri.html /index.html;
    add_header Cache-Control "no-store, no-cache, must-revalidate" always;
}
```

The deployment code must preserve the existing remote secret injection and must never print the rendered Nginx file. Apply `nginx -t` before reload; on failure keep the previous config and current link.

- [ ] **Step 6: Move `.deploy-sha` to the final atomic commit point**

Write `.deploy-sha` only after all of these are true:

```text
app container healthy
remote manifest source_sha == approved SHA
remote files match manifest
public /release-manifest.json matches remote manifest
public HTML cache header is no-store/no-cache
hashed asset cache header contains immutable
Nginx config test passes
```

- [ ] **Step 7: Extend read-only production audit**

Report `remote_manifest_sha256`, `public_manifest_sha256`, `manifest_file_count`, `manifest_mismatch_count`, `html_cache_control`, `static_cache_control`, `current_release_target`, and `deploy_sha`. Status is PASS only when all refer to the same SHA.

- [ ] **Step 8: Run tests**

```bash
uv run pytest tests/knowledge_query/test_scripts.py -k 'deploy or audit_tencent_cloud or release_manifest' -q
uv run ruff check scripts/deploy-tencent-cloud-production.py scripts/audit-tencent-cloud-deployment-state.py scripts/build-web-release-manifest.py
uv run mypy scripts/deploy-tencent-cloud-production.py scripts/audit-tencent-cloud-deployment-state.py scripts/build-web-release-manifest.py
```

- [ ] **Step 9: Commit**

```bash
git add scripts/deploy-tencent-cloud-production.py scripts/audit-tencent-cloud-deployment-state.py configs/deploy/tencent-cloud/nginx-audit-server.conf tests/knowledge_query/test_scripts.py docs/workflows/workflow-tencent-cloud-audit-deployment-stable.md
git commit -m "deploy: verify and atomically switch static releases"
```

---

### Task 11: Run the complete local and production-like release gate

**Files:**
- Output only: `tmp/outputs/**`
- Output only: `tmp/screenshots/**`

**Interfaces:**
- Consumes: all implementation commits and clean branch.
- Produces: reviewable local evidence; no production write.

- [ ] **Step 1: Verify branch integrity**

```bash
git status --short --branch
git merge-base --is-ancestor origin/main HEAD
git diff --check origin/main...HEAD
```

Expected: clean branch; no whitespace errors; branch descends from current origin/main.

- [ ] **Step 2: Run Web gates**

```bash
pnpm web:lint
pnpm web:typecheck
pnpm web:test
MEDICAL_AUDIT_DEPLOY_SHA="$(git rev-parse HEAD)" pnpm web:build:release
```

Expected: all PASS.

- [ ] **Step 3: Run backend/script gates**

```bash
uv run ruff check .
uv run mypy src scripts
uv run pytest
```

Expected: all PASS; existing unrelated failures must be reported, never skipped or deleted.

- [ ] **Step 4: Run local browser acceptance**

Use `1280×800`, `1440×1100`, and `390×900`. Capture all independent pages and alias checks. Required independent-page screenshots include `/login`, `/medical-audit`, `/rules`, `/remediation`, `/archive`, `/fund-compliance/review`, `/documents`, `/knowledge-base`, `/graph`, and `/agent-market`.

- [ ] **Step 5: Review screenshot matrix**

For every page record `expected final path`, `observed final path`, required headings, forbidden legacy text, primary CTA, runtime source badge, empty/error state, horizontal overflow and screenshot path.

- [ ] **Step 6: Create a draft PR after review authorization**

```bash
git push -u origin codex/production-ui-reconciliation-20260716
gh pr create --draft --base main --head codex/production-ui-reconciliation-20260716 --title "feat: reconcile production UI and release integrity" --body-file tmp/outputs/production-ui-reconciliation-pr-body.md
```

- [ ] **Step 7: Require independent review**

Review must explicitly approve:

```text
route decisions
no dirty-root whole-file overwrite
no regression on graph/knowledge-base/agent-market
no implicit production write
manifest determinism
atomic static rollback
Nginx secret safety
acceptance exact final paths
```

#### 2026-07-16 Task 11 local checkpoint

- Branch remains `codex/production-ui-reconciliation-20260716`, descending from `origin/main`; current `HEAD=489ff70185c70b008d1d30b41ce239386e9debd9` is `29` commits ahead and the current candidate is intentionally uncommitted.
- The earlier `task11-local-browser-matrix-current.json` reported `17` independent routes plus `3` aliases across `1280x800`, `1440x1100`, and `390x900`, but it predates the current route-chrome fix and has `source_sha=null`; it is retained as pre-fix evidence, not current acceptance.
- Fresh Playwright CLI snapshots now show exact topbar and open-tab identity for `/fund-compliance`, `/fund-compliance/review`, `/rules`, `/remediation`, `/archive`, and `/guided-check`. Focused browser regression passed explicit alias/route identity plus the initial mobile history-control placement check (`2 passed`).
- Screenshot review exposed the fixed mobile history control covering page content. A RED browser test reproduced it at `390x900`; the mobile control is now icon-only in the brand-header safe area, and the test turned GREEN. Independent review then widened the regression to `/remediation` and `/projects` at widths `390` and `900`, with viewport/header containment assertions, plus a `901` desktop invariance case; both widened tests passed (`2 passed`). Fresh screenshot: `output/playwright/task11-route-identity-20260716/mobile-390x900-remediation-safe-history.png`.
- Fresh local gates passed: Web lint, Web typecheck, Web Vitest `38` files / `352` tests, static export `24/24`, full `test_scripts.py` `267` tests, full pytest exit `0`, Ruff, `mypy src` (`104` source files), Node syntax, and `git diff --check`.
- `uv run mypy src scripts` remains blocked by `195` errors in `10` pre-existing files. None of those files has a commit in `origin/main..HEAD`, and none belongs to the current candidate diff; the errors were not skipped, deleted, or widened into an unrelated refactor.
- Exact-SHA release proof is still pending because the candidate worktree is dirty. `web:build:release`, commit, push, draft PR, merge, deploy, production acceptance, and production-write UAT were not executed.
- Boundary: `local_only` · `production unchanged` · `provider_call=false` · `database_write=local-test-only` · `live_send=false` · `external_call=false`.

---

### Task 12: Merge and deploy one new exact SHA

**Files:**
- Production outputs: remote backup, release directory, manifest, `.deploy-sha`, acceptance reports.

**Interfaces:**
- Consumes: reviewed Ready PR, green CI, explicit merge authorization, then explicit exact-SHA deployment authorization.
- Produces: production release with verifiable UI identity.

- [ ] **Step 1: Turn the PR Ready only after every local gate is green**

```bash
gh pr ready <PR_NUMBER>
gh pr checks <PR_NUMBER>
```

Expected: required checks PASS; no unresolved P0/P1 review comment.

- [ ] **Step 2: Merge only after explicit merge authorization**

```bash
gh pr merge <PR_NUMBER> --merge
git fetch origin main
git rev-parse origin/main
```

Record the full 40-character merge SHA. Do not deploy a symbolic `main` target.

- [ ] **Step 3: Obtain exact-SHA deployment authorization**

Authorization must name the SHA and separately list permission for backups, frozen build, static sync, app rebuild, Nginx config/reload, `.deploy-sha`, audit-log-only browser acceptance and read-only before/after snapshots.

- [ ] **Step 4: Run production preflight and before snapshot**

Require production deploy SHA, container health, current manifest, business-table counts and schema fingerprint. Preflight must make no production writes.

- [ ] **Step 5: Deploy through the hardened script**

Build from clean main, generate manifest, back up app/Web/Nginx/DB as authorized, sync to versioned release, verify, atomically switch, rebuild app only if the approved change requires it, test Nginx, then update `.deploy-sha`.

- [ ] **Step 6: Verify all public files against the manifest**

Expected:

```text
source_sha == approved merge SHA
remote manifest hash == public manifest hash
manifest mismatch count == 0
HTML Cache-Control contains no-store or no-cache
/_next/static Cache-Control contains immutable
```

- [ ] **Step 7: Run full production Chrome acceptance**

Capture every independent page in desktop/mobile and execute explicit alias checks. Require exact final URL, all screenshots present, `P0=0`, `P1=0`, provider not called and HTTP methods limited to GET.

- [ ] **Step 8: Compare before and after read-only snapshots**

Allowed delta: audit log entries attributable to acceptance. Required zero deltas: schema, query logs, review tables, projects and members, analytics uploads, document uploads, object storage records, governance jobs and agent invocations.

- [ ] **Step 9: Publish the deployment acceptance report**

The report must state the exact SHA, manifest hash, route/screenshot counts, alias checks, audit-log delta, prohibited-write deltas, container start times, cache headers and rollback release target.

---

### Task 13: Run separately authorized business-write UAT

**Files:**
- Production outputs only; no code changes in this task.

**Interfaces:**
- Consumes: already deployed and browser-accepted UI.
- Produces: isolated evidence for each real write flow.

- [ ] **Step 1: Keep each write lane separate**

Use independent authorization and evidence for:

```text
project creation
history-to-task conversion
review task creation/update
report draft creation
document upload
document governance
document personal indexing
provider-backed query
```

- [ ] **Step 2: Take a lane-specific backup and before snapshot**

Snapshot only the tables and object roots touched by that lane; do not reuse browser acceptance evidence as write approval.

- [ ] **Step 3: Execute one deterministic fixture**

Use a uniquely named fixture and record its audit identity. Do not batch several business effects into one test.

- [ ] **Step 4: Verify database, object, audit and UI evidence**

Require exact created IDs, expected table delta, object SHA when applicable, permission isolation, UI visibility and audit record attribution.

- [ ] **Step 5: Clean up only when cleanup was included in the lane authorization**

If cleanup was not authorized, preserve the fixture and report it explicitly.

---

## Release Go/No-Go Checklist

The release is `GO` only when every line is true:

- [ ] New UI changes exist on a clean branch descending from current `origin/main`.
- [ ] No whole-file copy or whole-branch merge from dirty root/continuation occurred.
- [ ] `/rules` is runtime-backed; retired hard-coded totals are absent.
- [ ] `/remediation` remains on `/remediation` and renders an independent workbench.
- [ ] `/archive` is runtime-backed.
- [ ] Fund review displays the four-stage workflow without implicit writes.
- [ ] Documents exposes GET-only personal-material status; write controls obey backend permissions and never auto-run.
- [ ] Knowledge-base, graph and agent-market preservation tests pass.
- [ ] Acceptance reports independent pages and aliases separately.
- [ ] `/login` and `/medical-audit` are covered.
- [ ] Every passing independent page has a screenshot and exact final-path proof.
- [ ] Static build manifest matches the exact Git SHA and every public file.
- [ ] Public manifest equals remote manifest; mismatch count is zero.
- [ ] HTML cache is no-store/no-cache; hashed assets are immutable.
- [ ] Nginx config test passes and secret material was never printed or committed.
- [ ] Before/after snapshots show audit-log-only acceptance writes and zero prohibited deltas.
- [ ] Exact-SHA merge and deployment approvals are recorded.

Current decision: `NO-GO` for production deployment. Tasks 1-10 are already represented in the current `29`-commit branch, but Task 11 still lacks a clean exact SHA, a current SHA-bound browser matrix, a resolved `mypy src scripts` policy, migration-readiness evidence and executable S0/S1/S2 production snapshot tooling. The next executable batch is the local-only Loop 58 evidence-contract closure below; it is not merge or deploy authorization.

---

## 2026-07-16 Next-Batch Deployment Plan (Loop 58)

### Recommended scheme

| Scheme | Description | Decision |
|---|---|---|
| A — evidence-first gated promotion | Close the missing release evidence contracts locally, freeze an exact SHA, review through Draft PR, merge separately, then split deployment, L3 verification and L4 acceptance | **Recommended** |
| B — direct commit and deploy | Commit the current delta and move directly to production | Rejected: no broad snapshot harness, no migration-readiness proof, stale browser matrix |
| C — fix all repository Mypy debt in this release | Expand this branch to repair `195` historical errors in `10` unrelated files | Not recommended: separate quality-debt lane unless the owner explicitly chooses it |

The evidence-first path uses these terminal states and never collapses them:

```text
planned
  -> local_candidate
  -> reviewed_draft_pr
  -> merged_exact_sha
  -> preflight_observed
  -> deployed_pending_l3
  -> deployed_l3_verified
  -> release_accepted_l4
```

### Verified input state

- Worktree: `/Users/pray/project/medical_audit_release_reconciliation_20260714`.
- Branch: `codex/production-ui-reconciliation-20260716`.
- Current committed head: `489ff70185c70b008d1d30b41ce239386e9debd9`; base `origin/main@1376baef0d8d47f1e1ef60b2cec130451af5af4f`; branch is `29` commits ahead.
- `origin/main..HEAD` touches `41` files before the current checkpoint. The original Task 11 checkpoint has `12` modified tracked files; Loop 58 also updates the three `.kiro/plan` ledgers as plan-only state.
- Current branch delta contains Web runtime, Nginx/release policy and operator tooling, but no `src/` application runtime or schema/migration file. Final deploy classification must be recomputed from the fresh production marker to the final merge SHA.
- The latest local browser matrix with all routes is pre-fix, has `source_sha=null` and is not current acceptance.
- `uv run mypy src scripts` currently reports `195` errors in `10` pre-existing files outside both the candidate diff and `origin/main..HEAD`; this remains a named gate conflict.
- No current-turn production topology observation exists. Any previous production SHA or legacy/versioned assumption is historical until refreshed read-only.

### Batch map

| Batch | Scope | Evidence produced | Authorization boundary |
|---|---|---|---|
| D0 | Release evidence-contract closure | L2 tests for migration readiness, S0/S1/S2 snapshots and exact-SHA frontend acceptance | Local-only implementation |
| D1 | Candidate freeze and atomic local commits | Clean candidate SHA and explicit manifests | Explicit local commit authorization |
| D2 | Exact-SHA local release gate | Manifest-bound build and fresh route matrix | Local-only verification |
| D3 | Draft PR and independent review | Remote review candidate | Explicit push/Draft PR authorization |
| D4 | Ready and merge | Full 40-character merge SHA | Separate Ready and merge authorizations |
| D5 | Clean-main preflight and S0 | Fresh production topology and before snapshot | Explicit production read-only authorization |
| D6 | Exact-SHA deployment | Backups, versioned release, app identity, Nginx and marker | Exact-SHA deployment plus rollback pre-authorization |
| D7 | S1 and conditional L3 closure | Deployment-state audit and zero business/schema deploy delta | Post-deploy read-only authorization named in D6 |
| D8 | L4 permission/browser acceptance and S2 | Attributable audit-log-only delta, all-page screenshots | Separate L4 `audit-log-only` authorization |
| D9 | Business-write/provider UAT | Per-lane production evidence | Separate authorization for every lane |

### D0 — Close release evidence contracts locally

- [x] **D0.1: Add one fail-closed release guard snapshot tool**

Implemented file: `scripts/audit-production-release-guard-snapshot.py`, with tested `capture` and `compare` modes. It:

- forces PostgreSQL `SERIALIZABLE READ ONLY DEFERRABLE`, checks `transaction_read_only=on`, and fails closed on WAL/double-capture ambiguity;
- binds L3 evidence to the configured production SSH host/user, fixed app/Web/PostgreSQL scope, strict transport settings, generated time, current collector source SHA-256 and a snapshot+provenance envelope; hidden `capture-live` returns only a stdout fixture, rejects `--output` and lacks a valid outer-SSH receipt;
- classifies release topology as exactly one of `legacy_ready`, `versioned_ready`, or `partial_or_unknown`;
- captures release identity plus schema columns, constraints, indexes, ACL, RLS policies, triggers and trigger-function definitions;
- captures row count, primary-key fingerprint, full row-content fingerprint and max relevant timestamp for the allowlisted business tables below, with exact audit event IDs/row hashes;
- records the database object ledger fingerprint; COS object enumeration remains explicitly outside this guard's observation scope;
- fails closed on missing tables, duplicate/unknown/malformed collector records, unreadable values, concurrent ambiguity or partial topology;
- never opens or prints `.env`, secret values, credentials or full container environments.

Allowlisted database scope:

```text
query_logs
review_tasks
review_actions
review_comments
audit_projects
audit_project_members
analytics_upload_records
document_upload_records
document_storage_objects
document_upload_governance_jobs
audit_agent_invocations
audit_log_events
```

- [x] **D0.2: Implement three-phase comparison**

```text
S0 = pre-deploy
S1 = post-deploy, before L4 acceptance
S2 = post-L4 acceptance
```

Required comparisons:

- `S0 -> S1`: schema and every business table unchanged; release/container/manifest identity may change only as authorized by deploy.
- `S1 -> S2`: only exact event IDs attributable to the supplied `acceptance_run_id` may increase; the run user must have a zero S1 baseline, old audit rows may not change, and all other tables, schema, release topology and object ledger must remain unchanged.
- Unknown or concurrent deltas produce `status=blocked`, not a guessed attribution.
- Each compare revalidates both input capture contracts and recomputes their snapshot IDs. The release guard proves only `collector_provider_call_status=not_called`; whole-runtime provider status is `not_observed` unless a separate telemetry source is supplied.
- The fixed deploy transition profile permits only `legacy_ready|versioned_ready -> versioned_ready`; rollback to legacy is a separate production-write workflow and cannot pass as S0→S1 deploy evidence.

- [x] **D0.3: Add first versioned-release migration readiness**

`legacy_ready` requires all of the following: no `current`, no migration sentinel, valid legacy flat-root `index.html`, valid existing marker, no `.incoming`/`.next`/`.deploy-sha.next` residue, and `releases/` either absent or a real non-symlink directory. `versioned_ready` requires `releases/` to be a real directory, marker, `current -> releases/<sha>`, release directory and manifest identity to agree, plus a valid non-symlink migration sentinel and no residue. The sentinel is durable migration-lineage evidence and may retain the first successful migration SHA; it is not a rotating current-release marker. The collector also verifies app container status/health/deploy SHA, Nginx config and the read-only Web mount. Any mixed state is `partial_or_unknown` and blocks deploy/rollback.

The rollback tests must cover first migration back to legacy. A rollback exit code alone is not acceptance; the migration-aware guard must verify the restored marker, flat-root content, Nginx and container identity.

- [x] **D0.4: Harden full frontend acceptance**

Modify the runner/gate and tests so the hardened production profile requires:

- `17` independent routes and `3` aliases across desktop/mobile (`34 + 6` executions);
- `screenshot_capture=true` and `screenshot_policy=all`;
- valid, unique and run-bound PNG evidence for all `40` executions, including aliases, with exact viewport dimensions, CRC and decompressed scanline validation;
- exact `expected_deploy_sha`, public manifest/source SHA and current release target;
- unique `acceptance_run_id` and run-specific audit user identity;
- the S1 guard attribution must carry the same run/user, zero attributable events and an empty exact-ID baseline;
- same-origin GET-only browser/API requests;
- exact production HTTP origin only (`https://audit.lute-tlz-dddd.top`, with explicit `:443` normalized); reject other scheme/host/port, userinfo, path, query or fragment and bind `report.base_url` to it;
- `P0=0`, `P1=0` and exact final-path/chrome-title proof;
- release-guard collector proof separated from whole-runtime provider telemetry; the latter remains `not_observed` unless a separate source is supplied;
- anonymous/missing-role probes retain the run-specific user ID so every audit-log write remains attributable.

- [x] **D0.5: Add RED-to-GREEN tests and update stable workflow**

At minimum cover partial migration, legacy/versioned identity drift, schema/table delta, balanced delete+insert, concurrent ambiguity, missing screenshot, fixed-identity rejection, expected-SHA mismatch, public-manifest mismatch and provider evidence missing.

Boundary for D0: `local_only`, `production unchanged`, `database_write=local-test-only`, `provider_attempt_made=false`, `provider_call_status=not_observed`, `collector_provider_call_status=not_called`.

Trust boundary: the SSH provenance/envelope detects wrong-target, direct hidden-capture, stale-collector and ordinary artifact drift under the controlled operator-workspace model. It is not an external signed attestation against a malicious local operator who can replace both code and report; that stronger threat model requires a separately designed signing service or hardware-backed key.

Final D0 evidence: `40` release-guard tests, `22` focused frontend-acceptance tests and `311` combined related tests pass; Ruff, changed-script Mypy, both Node syntax checks and diff checks pass. Two independent final read-only reviews report `accepted P0/P1=0`, confidence high. This closes only L2 D0; no L3 SSH capture or L4 browser execution occurred.

### D1 — Freeze the local candidate

- [x] **D1.1: Resolve the Mypy policy before claiming Task 11 complete**

Owner selected policy 2 on `2026-07-16`: an exact, fail-closed non-regression exception. The rejected alternative remains a separate quality-debt lane:

1. Repair the `195` historical errors in a separate quality-debt lane and rebase/reconcile afterward; or
2. Explicitly approve a non-regression exception proving all `10` failing files are outside the candidate, every candidate-changed Python script passes targeted Mypy and the exact diagnostic set is unchanged.

Implemented contract:

```bash
uv run python scripts/check-mypy-non-regression.py \
  --output tmp/outputs/mypy-non-regression-loop58-phase3.json
```

- Baseline: `configs/mypy-non-regression-baseline-v1.json`, bound to exact base `1376baef0d8d47f1e1ef60b2cec130451af5af4f`, Mypy `2.1.0`, the full command, exit `1`, all `195` diagnostics, all `10` files, per-file fingerprints and base/current source hashes.
- Fresh isolated base and current-candidate runs have identical canonical diagnostic SHA-256 `fd5876c18cd71cd2e316a2c9c9206a59fc5dc1654143fcfb0242d8d5b566e97f`.
- Fresh candidate gate result is `status=pass`, `decision=allowed-with-label`, `mypy_full_pass=false`, `issues=[]`; all six candidate-changed Python scripts pass targeted Mypy.
- Diagnostic exchange at the same count, improvement/removal, Mypy version drift, base ancestry failure, stderr, debt-file modification or base/current source-hash drift all fail closed and require an explicit baseline refresh.
- No `ignore_errors`, looser `strict`, skipped target or new `type: ignore` is introduced. This exception must never be reported as `mypy src scripts PASS` or repository-wide Mypy clean.

- [x] **D1.2: Create atomic local commits after the owner authorization received on `2026-07-16`**

Suggested manifests:

1. Release evidence closure: snapshot/migration tool, Mypy non-regression gate/baseline, acceptance runner/gate, focused tests and stable workflow.
2. Route/chrome/mobile checkpoint: alias pages, replica shell/data, mobile safe-area CSS and browser/component/fullstack tests.
3. Planning ledger: this implementation plan plus `.kiro/plan/task_plan.md`, `findings.md`, and `progress.md`.

For every commit: explicit `git add -- <paths>`, inspect `git diff --cached --name-status`, run `git diff --cached --check`, verify no `output/`, `tmp/`, screenshots, SQLite, secrets or generated build output is staged.

Execution evidence:

- `0d34a94` — release evidence closure, exact `10`-file manifest, `5,755` insertions / `116` deletions.
- `85859a6` — route/chrome/mobile checkpoint, exact `8`-file manifest, `158` insertions / `11` deletions.
- The third and final manifest is this planning-ledger commit. Its SHA and final clean-worktree equality are external Git facts verified after commit; this file does not invent its own future SHA.
- Every group used explicit paths, exact manifest comparison, cached diff check and a refined added-content high-risk secret scan with `secret_candidates=0`. No ignored output, `tmp/`, screenshot, SQLite, build output or cache entered the index.
- Pre-staging gates: `322` evidence tests passed, full Ruff PASS, both Node syntax checks PASS, real Mypy gate `allowed-with-label`; Web `38` files / `352` tests passed, typecheck PASS and lint PASS. These runs cover the full working tree; atomic independence is additionally supported by exact staged manifests and concern-specific tests.

### D2 — Produce exact-SHA L2 evidence

- [ ] **D2.1: Require a clean candidate descending from current origin/main**

```bash
git status --short --branch
git fetch origin main
git merge-base --is-ancestor origin/main HEAD
git diff --check origin/main...HEAD
CANDIDATE_SHA="$(git rev-parse HEAD)"
```

- [ ] **D2.2: Run the complete local gate**

```bash
pnpm web:lint
pnpm web:typecheck
pnpm web:test
uv run ruff check .
uv run mypy src
uv run pytest
pnpm local:fullstack:e2e
MEDICAL_AUDIT_DEPLOY_SHA="$CANDIDATE_SHA" pnpm web:build:release
```

Run `uv run mypy src scripts` separately and apply the selected D1.1 policy. Also run targeted Mypy for every changed Python script and Node syntax/tests for both frontend acceptance files.

The canonical D1.1 invocation is `uv run python scripts/check-mypy-non-regression.py`; it intentionally retains the full command exit `1` as historical-debt evidence and returns success only as `allowed-with-label` after exact fingerprint and targeted-script checks pass.

- [ ] **D2.3: Regenerate the full local browser matrix from the exact SHA**

Required viewports: `1280x800`, `1440x1100`, `390x900`; required `source_sha=$CANDIDATE_SHA`, `source_worktree_dirty=false`; `17` independent routes, `3` aliases, exact chrome/final path, screenshots, runtime/error state and horizontal-overflow evidence. Do not overwrite the pre-fix matrix; save a SHA-named artifact.

### D3/D4 — Review, Ready and merge

- [ ] **D3.1:** After explicit authorization, push the feature branch and create a Draft PR. Record remote head, base, commit/file manifest and checks without claiming CI passed when none are reported.
- [ ] **D3.2:** Require independent review of route decisions, migration/snapshot failure modes, manifest determinism, Nginx secret safety, app deployment identity, rollback and L4 attribution. Accepted P0/P1 must be zero.
- [ ] **D4.1:** Move Draft to Ready only after local policy, review and required checks are resolved; this needs separate authorization.
- [ ] **D4.2:** Merge only after separate merge authorization. Fetch `origin/main` and record the full merge SHA as `APPROVED_SHA`; symbolic `main` is not a deploy identity.

### D5 — Clean-main preflight and S0

- [ ] **D5.1: Establish clean release source**

Use only the release reconciliation clone after it is clean on `main`; require `HEAD == origin/main == APPROVED_SHA`. Never deploy from `/Users/pray/project/medical_audit` dirty root.

- [ ] **D5.2: Capture S0 and topology under production read-only authorization**

Capture current marker, release topology, schema/business/object guard, audit baseline, container IDs/health/start times, disk/backup capacity, Nginx test, front door and current embedding lower bound.

- `legacy_ready`: deployment authorization must explicitly include `--allow-first-legacy-migration` and migration-sentinel creation.
- `versioned_ready`: omit the migration flag.
- `partial_or_unknown`: STOP; no deploy command may run.

- [ ] **D5.3: Run default deploy preflight without `--execute`**

```bash
uv run python scripts/deploy-tencent-cloud-production.py \
  --ssh-key <SSH_KEY_PATH> \
  --stamp "preflight-<APPROVED_SHA_SHORT>-<TIMESTAMP>"
```

This preflight checks locked dependencies and basic remote health. It does not create the execute report and does not replace S0 topology/schema/business snapshots.

### D6 — Exact-SHA production deployment

- [ ] **D6.1: Obtain one exact authorization package**

It must name `APPROVED_SHA`, `CURRENT_PRODUCTION_SHA`, deploy stamp, SSH target, app/Web/Nginx/DB/env backups, frozen build, app sync and rebuild, versioned static release, optional first migration, Nginx test/reload, smoke, marker commit, and pre-authorized rollback conditions.

Do not authorize or pass:

```text
--allow-dirty
--skip-web-build
--skip-smoke
--skip-app-rebuild
--apply-schema
--include-query-provider-smoke
--include-review-write
--confirm-production-write
```

`--skip-app-rebuild` is forbidden for this release because app deployment metadata is bound to `MEDICAL_AUDIT_DEPLOY_SHA` at container start; skipping rebuild would split app identity from `.deploy-sha` and the public manifest.

- [ ] **D6.2: Execute only from clean main**

```bash
uv run python scripts/deploy-tencent-cloud-production.py \
  --execute \
  --confirm-production audit.lute-tlz-dddd.top \
  --approved-sha <APPROVED_SHA> \
  <OPTIONAL_ALLOW_FIRST_LEGACY_MIGRATION> \
  --stamp <DEPLOY_STAMP> \
  --ssh-key <SSH_KEY_PATH> \
  --report tmp/outputs/production-e2e-smoke-after-<DEPLOY_STAMP>.json
```

Successful script exit establishes only `deployed_pending_l3`. It does not establish full release acceptance.

### D7 — S1 and conditional L3 closure

- [ ] **D7.1: Run strict deployment-state audit**

```bash
uv run python scripts/audit-tencent-cloud-deployment-state.py \
  --ssh-key <SSH_KEY_PATH> \
  --expected-deploy-sha <APPROVED_SHA> \
  --required-backup-stamp <DEPLOY_STAMP> \
  --min-matching-embeddings <S0_LOWER_BOUND> \
  --require-clamav-sidecar \
  --expected-dlp-review-provider ruleset-v1 \
  --json-output tmp/outputs/tencent-cloud-deployment-state-after-<DEPLOY_STAMP>.json \
  --markdown-output tmp/outputs/tencent-cloud-deployment-state-after-<DEPLOY_STAMP>.md
```

- [ ] **D7.2: Capture S1 and compare S0→S1**

Require marker/current/manifest/public hash/cache/container/backup checks to pass, schema fingerprint unchanged, all business-table/object-ledger metadata unchanged, and no unexplained audit delta. The release guard may establish only that its collector made no provider attempt; a whole-runtime no-provider-call claim requires separate telemetry and otherwise remains `provider_call_status=not_observed`. The default permission observation remains limited to `2/35` public GET probes and must not be called a full permission matrix.

Only then may status become `deployed_l3_verified`.

### D8 — Separately authorized L4 acceptance and S2

- [ ] **D8.1: Capture the S1 baseline immediately before each L4 lane**
- [ ] **D8.2: Run the full permission matrix under its own `audit-log-only` authorization**
- [ ] **D8.3: Run full frontend acceptance under a different `audit-log-only` authorization**

```bash
MEDICAL_AUDIT_FRONTEND_ACCEPTANCE_SCREENSHOTS=1 \
MEDICAL_AUDIT_FRONTEND_ACCEPTANCE_SCREENSHOT_POLICY=all \
pnpm production:frontend-acceptance -- \
  --base-url https://audit.lute-tlz-dddd.top \
  --expected-deploy-sha <APPROVED_SHA> \
  --acceptance-run-id <UNIQUE_RUN_ID> \
  --release-guard-report tmp/outputs/release-guard-s1-<DEPLOY_STAMP>.json \
  --allow-audit-log-writes \
  --confirm-production-write audit.lute-tlz-dddd.top \
  --output tmp/outputs/production-frontend-acceptance-<DEPLOY_STAMP>.json \
  --screenshot-dir tmp/screenshots/production-frontend-acceptance-<DEPLOY_STAMP> \
  --admin-role it-admin
```

The three evidence-binding CLI options are D0 deliverables and are now implemented and locally tested.

- [ ] **D8.4: Capture S2 and compare S1→S2**

Only the run-specific audit identity may have attributable `audit_log_events` deltas. Schema, query history, review, projects/members, analytics, documents/object metadata, governance and agent invocation deltas must all be zero. Provider evidence must be runtime-derived. Any ambiguity blocks acceptance.

- [ ] **D8.5: Publish one closeout report**

Required fields: merge/approved/deploy SHA equality, deploy flags/exit, backup stamp, release/manifest hashes, file count/mismatches, cache headers, rollback target, route/alias/viewport exact sets, screenshot paths/hashes/dimensions, P0/P1, S0→S1 and S1→S2 deltas, attributable audit delta, prohibited-table deltas, schema fingerprint, provider evidence source, unverified items and concurrent-write ambiguity.

Only this state may be called `release_accepted_l4`.

### D9 — Business-write and provider UAT

Continue Task 13 unchanged: project creation, history-to-task, review/report, uploads/governance/indexing and provider-backed query remain independent lanes. Each requires its own authorization, backup, before snapshot, deterministic fixture, exact delta, audit identity, optional cleanup authorization and report. L4 frontend acceptance does not authorize any D9 lane.

### Rollback contract

Rollback must use the original deployment stamp and observed identities:

```bash
uv run python scripts/deploy-tencent-cloud-production.py \
  --rollback \
  --confirm-production audit.lute-tlz-dddd.top \
  --stamp <DEPLOY_STAMP> \
  --expected-current-sha <OBSERVED_CURRENT_MARKER_SHA> \
  --restore-sha <VERIFIED_SHA_INSIDE_APP_BACKUP> \
  --ssh-key <SSH_KEY_PATH>
```

Do not guess `restore-sha`; read it through the reviewed rollback-precheck path. If the deploy/rollback outcome is unknown, SSH returns `255`, timeout/rsync uncertainty occurs, marker commit is uncertain, or activation restore fails, retain the production lock and enter manual reconciliation. Do not rerun blindly.

### Hard stop conditions

- dirty release source, non-main execute source, `HEAD != origin/main != APPROVED_SHA`;
- unresolved D1.1 policy, failing required test or unresolved P0/P1;
- `partial_or_unknown` migration topology;
- stale/mismatched manifest, missing full backup category, insufficient disk, existing deploy lock or `.incoming/.next/.deploy-sha.next` residue;
- marker/current/manifest/transaction identity mismatch;
- Nginx candidate or formal `nginx -t` failure, public hash/cache mismatch, unhealthy app/PostgreSQL/ClamAV or changed protected container identity;
- any provider attempt, schema drift, prohibited business/object delta or un-attributable audit delta;
- any unknown remote outcome or incomplete rollback verification.

### Authorization matrix

| Action | Required authorization |
|---|---|
| D0 local implementation/tests | Authorized and completed at L2; no production authority inherited |
| Local commits | Owner authorization received on `2026-07-16` for D1.2 only; no external authority inherited |
| Push and Draft PR | Explicit GitHub push/PR authorization |
| Ready | Separate Ready authorization |
| Merge | Separate merge authorization |
| D5 production read-only observation | Explicit production read-only authorization |
| D6 exact-SHA deploy and rollback pre-authorization | Exact SHA plus named side effects |
| D8 full permission matrix | Separate L4 `audit-log-only` authorization |
| D8 full frontend acceptance | Separate L4 `audit-log-only` authorization |
| D9 each business/provider lane | Independent lane-specific authorization |

Loop 58 D0 closure boundary: `L2-fixture-or-dry-run` · `local_only` · `production unchanged` · `provider_attempt_made=false` · `provider_call_status=not_observed` · `collector_provider_call_status=not_called` · `database_write=local-test-only` · `live_send=false` · `deploy_execution=false`.

Loop 58 D1.1 closure boundary: `L2-fixture-or-dry-run` · `allowed-with-label` · `mypy_full_pass=false` · `195 inherited diagnostics` · `10 untouched debt files` · `6 changed scripts targeted PASS` · `production unchanged` · `provider_attempt_made=false` · `database_write=false` · `deploy_execution=false`.
