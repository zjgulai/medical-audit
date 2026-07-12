---
title: PPT Feedback Product Optimization Implementation Plan
created_at: 2026-07-11
project: medical_audit
scope: product-alignment-and-implementation
baseline: origin-main@51dfcb816a0c71928c206683f0fa7fef796e895a
production_side_effect: none
provider_call: false
database_write: local-test-only
status: local-accepted
updated_at: 2026-07-13
---

# PPT Feedback Product Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` for task-by-task execution, or `superpowers:executing-plans` when running the batches in a separate execution session. Use `superpowers:test-driven-development` for every behavior change and `superpowers:verification-before-completion` before any completion claim. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the 19 approved PPT feedback requirements without weakening the medical-audit V1 scope, data truthfulness, permission boundaries, or provider gates.

**Architecture:** Keep the existing FastAPI + Next.js API-first boundary. First remove silent fixture substitution and freeze runtime states, then fix the shared shell and direct-use paths, then restore the three hidden workbenches, and finally add project-scoped graph/report contracts. Reuse current stores and APIs; do not add a graph database, OCR pipeline, or multi-agent orchestrator.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, SQLAlchemy, PostgreSQL/SQLite test stores, Next.js, React, TypeScript, Vitest/Testing Library, Playwright, pnpm, pytest.

**Approved design:** `docs/superpowers/specs/2026-07-11-ppt-feedback-product-alignment-design.md`

## Execution status

- Feature branch: `codex/ppt-feedback-product-optimization-20260711` based on `origin-main@51dfcb816a0c71928c206683f0fa7fef796e895a`.
- Tasks 0-10 are implemented and locally accepted with local task commits.
- Current verified gates: backend `281 passed`; frontend `32 files / 267 tests`; typecheck and lint exit `0`; Next build `24/24` pages; local full-stack E2E `13 passed`.
- Task-scoped Ruff and mypy pass. Repository-wide Ruff/mypy still report four pre-existing findings in untouched `routes_chat.py`, `ingestion/inventory.py` and `indexing/bm25_index.py`; they are recorded in the local acceptance JSON and excluded from this product-alignment diff.
- `production_side_effect=none`, `provider_call=false`, `database_write=local-test-only`; merge, push, deploy, production checks and real provider smoke were not executed.
- `docs/workflows/workflow-project-state-and-debt-register-stable.md` contains protected user edits and is excluded from this batch's writes and staging.

---

## Global execution constraints

- Implementation uses the dedicated feature worktree recorded above; do not switch, stash, reset, format or reuse the dirty root checkout.
- Keep the three protected pre-existing document changes untouched and unstaged.
- Do not read or print `.env`, secret values, tokens, passwords, private keys, or personal data.
- Do not add dependencies. Use current React, FastAPI, Pydantic and test utilities.
- Product labels are exact: `AI审计一体化协作平台`, 9 main navigation entries, and one separate `医保审计专题` entry.
- Enter in chat remains newline; only the arrow button submits.
- API success with an empty collection is a real empty state. API failure is an error state. Neither may silently display fixture data.
- Medical/医保 agents remain the default V1 catalog. The three requested finance/procurement/engineering agents are an opt-in validation pack.
- Production deploy, merge, production/database writes, environment changes, real provider calls, report signing and live sends require separate explicit authorization.
- Commit commands below are conditional instructions only. Execute them only after the owner explicitly authorizes commits.

## Dependency order

| Order | Task | Depends on |
| ---: | --- | --- |
| 0 | Clean baseline and contract freeze | none |
| 1 | Runtime truth-state foundation | 0 |
| 2 | Login, brand, 9+1 shell and history button | 1 |
| 3 | Chat and agent direct-use path | 1-2 |
| 4 | Knowledge base and document truthfulness | 1 |
| 5 | Project status, identity and visibility | 1 |
| 6 | Analytics workbench | 1, 5 read contract |
| 7 | Report categories, draft handoff and workbench | 1, 5 |
| 8 | Dual-view graph | 4, 5, 7 |
| 9 | Medical default agents and extension validation pack | 3 |
| 10 | Full acceptance and stable-document sync | 2-9 |

---

### Task 0: Create a clean execution baseline

**Files:**

- Read: `AGENTS.md`
- Read: `docs/superpowers/specs/2026-07-11-ppt-feedback-product-alignment-design.md`
- Read: `docs/product/product-prd-medical-audit-v1-stable.md`
- Read: `docs/product/product-development-plan-medical-audit-stable.md`
- Read: `docs/workflows/workflow-answer-provider-production-gate-stable.md`
- Track: `docs/superpowers/plans/2026-07-11-ppt-feedback-product-optimization.md`

- [ ] **Step 0.1: Verify the execution checkout is clean**

Run:

```bash
git status --short --branch
git rev-parse HEAD
git rev-parse origin/main
```

Expected: no status entries below the branch header. If any modified or untracked file exists, stop; do not stash or discard it.

- [ ] **Step 0.2: Refresh and review the remote baseline**

Run only in the clean checkout:

```bash
git fetch --prune origin
git log -1 --oneline origin/main
git diff --stat c29f5e37dafae931f5df1dbfbe7b851fbc0bc638..origin/main
```

Expected: the latest remote SHA and a reviewable diff summary. Re-run the file mapping for any changed file named in this plan before editing.

- [ ] **Step 0.3: Create the feature branch**

Run:

```bash
git switch -c codex/ppt-feedback-product-optimization-20260711 origin/main
git status --short --branch
```

Expected: branch `codex/ppt-feedback-product-optimization-20260711`, clean status.

- [ ] **Step 0.4: Record the actual SHA in both design and plan frontmatter**

Replace `local-cached-origin-main@...` only if the refreshed SHA differs. Do not change approved decisions.

- [ ] **Step 0.5: Conditional checkpoint commit**

Only with explicit commit authorization:

```bash
git add docs/superpowers/specs/2026-07-11-ppt-feedback-product-alignment-design.md docs/superpowers/plans/2026-07-11-ppt-feedback-product-optimization.md
git commit -m "docs: freeze ppt feedback product alignment"
```

---

### Task 1: Establish explicit runtime truth states

**Files:**

- Modify: `web/src/lib/replica-adapters.ts`
- Modify: `web/src/lib/replica-adapters.test.ts`
- Modify: `web/src/components/replica/use-replica-runtime.ts`
- Modify: `web/src/components/replica/use-replica-runtime.test.tsx`
- Modify: `web/src/components/replica/replica-page-kit.tsx`
- Create: `web/src/components/replica/replica-page-kit.test.tsx`
- Modify: `web/src/components/replica/replica-shell.test.tsx`

- [ ] **Step 1.1: Write failing adapter tests for disabled, success-empty and failure**

Add tests proving all three paths are different:

```ts
it("keeps a successful empty API collection empty", async () => {
  const result = await loadReplicaDocumentsData({
    fetchKnowledgeBaseCatalog: vi.fn().mockResolvedValue(emptyKnowledgeCatalog),
    fetchDocumentSourceCollections: vi.fn().mockResolvedValue(emptySourceCatalog),
    fetchQueryHistory: vi.fn().mockResolvedValue({ items: [], store: { ready: true, backend: "test" } })
  });

  expect(result.outcome).toBe("empty");
  expect(result.source).toBe("api");
  expect(result.data.results).toEqual([]);
  expect(result.data.searchHistory).toEqual([]);
});

it("returns error without fixture substitution when an enabled API read fails", async () => {
  const result = await loadReplicaProjectsData({
    fetchProjects: vi.fn().mockRejectedValue(new Error("offline"))
  });

  expect(result.outcome).toBe("error");
  expect(result.data.projects).toEqual([]);
  expect(result.issues).toContainEqual(expect.objectContaining({ code: "api-read-failed" }));
});

it("preserves registry data as degraded when metrics are unavailable", async () => {
  const result = await loadReplicaKnowledgeBaseData({
    fetchKnowledgeBaseCatalog: vi.fn().mockResolvedValue(registryOnlyKnowledgeCatalog)
  });

  expect(result.source).toBe("api");
  expect(result.outcome).toBe("degraded");
  expect(result.data.knowledgeBases).not.toEqual([]);
});
```

The registry-only case must remain degraded even when `store.ready=true`, `search_backend.ready=true` and every item index reports ready, because `boundaries.source="runtime_state_and_registry_only"` means persisted metrics are unavailable. Preserve the registry cards, but map their unverified `chunkCount` to `null` and omit any numeric chunk tag. Set aggregate metrics provenance truthfully, and prove a real numeric zero remains ready and remains `chunkCount=0` only for `runtime_state_and_postgres_catalog`.

Run:

```bash
pnpm --filter medical-audit-web exec vitest run src/lib/replica-adapters.test.ts
```

Expected: FAIL because `outcome` does not exist and current loaders return fixtures for empty/failure.

- [ ] **Step 1.2: Add a discriminated API-read result**

In `replica-adapters.ts`, replace the nullable read result with:

```ts
type OptionalApiRead<T> =
  | { readonly kind: "disabled" }
  | { readonly kind: "success"; readonly value: T }
  | { readonly kind: "failure"; readonly message: string };

export type ReplicaDataSource = "fixture" | "catalog" | "api" | "hybrid";
export type ReplicaAdapterOutcome = "ready" | "empty" | "degraded" | "error";

export type ReplicaAdapterResult<TData> = {
  readonly source: ReplicaDataSource;
  readonly outcome: ReplicaAdapterOutcome;
  readonly data: TData;
  readonly issues: readonly ReplicaAdapterIssue[];
};
```

Rules for runtime API loaders:

- `disabled`: fixture is allowed and `source="fixture"`;
- `success` with items: `outcome="ready"`, `source="api"` or explicit `hybrid` for static navigation plus API identity;
- `success` with no items: `outcome="empty"`, empty collections, no fixture;
- `success` with `store.ready=false` or an explicit metrics/backend readiness gap: `outcome="degraded"`, preserve returned data and expose its limitation;
- `failure`: `outcome="error"`, empty collections, issue `api-read-failed`, no fixture.

Each read failure issue must include a version-controlled, non-sensitive read name so concurrent failures on one surface remain distinguishable. Never expose the raw exception message, URL query, credentials or response body.

Version-controlled navigation, report-category definitions and the medical marketplace are product catalogs, not runtime API reads. They return `source="catalog"` and must never call a personal-data API merely to appear live.

- [ ] **Step 1.3: Write failing hook tests**

Cover:

```ts
expect(screen.queryByText("本地样例记录")).not.toBeInTheDocument();
expect(result.current.status).toBe("loading");
// after an API rejection
expect(result.current.status).toBe("error");
expect(result.current.source).toBe("api");
```

Also resolve a response with `store.ready=false` and assert `status="degraded"`. Set `NEXT_PUBLIC_MEDICAL_AUDIT_REPLICA_API_READS=0` and prove fixture data appears only then.

Add a focused `ReplicaRuntimeBadge` test proving the shared consumer accepts `source="catalog"` and renders distinct accessible labels for `empty`, `degraded` and `error`; it must not describe an error as `接口已校验`.

Rerender the same mounted runtime harness across API-read enabled/disabled states and across agent `mine`/`market` modes. Prove the first render after each switch immediately exposes the current empty/loading, fixture/ready or catalog/ready state and never leaks the previous surface's records. Add a fixture-ready badge assertion proving it does not claim `接口已校验`.

Use a controlled deferred API promise to prove that resolving an old request after a runtime-key switch cannot overwrite the new fixture/catalog/current-API state. Update fixture-specific shell tests to explicitly stub `NEXT_PUBLIC_MEDICAL_AUDIT_REPLICA_API_READS=0` and restore the environment after each test; do not rely on the former implicit first-render fixture.

Run:

```bash
pnpm --filter medical-audit-web exec vitest run src/components/replica/use-replica-runtime.test.tsx
pnpm --filter medical-audit-web exec vitest run src/components/replica/replica-page-kit.test.tsx
```

Expected: FAIL because the current hook initializes with fixture and collapses failure into `ready`.

- [ ] **Step 1.4: Implement runtime states**

Use:

```ts
export type ReplicaRuntimeStatus = "loading" | "ready" | "empty" | "degraded" | "error";
```

When API reads are enabled, initialize each hook with its empty data shape, not the fixture. On resolution, map `nextResult.outcome` to status, including `degraded`. On an unexpected thrown error, return `status="error"` and an `api-read-failed` issue. Preserve fixture initialization only when reads are explicitly disabled. Catalog-only surfaces initialize from catalog with `status="ready"` and do not use the API-read toggle. Preserve the refreshed-baseline KB fields `chunkCount`, `currentSearchEmbeddingCount` and `metricsSource` in every empty/fallback shape; determine KB degraded state from catalog/store readiness rather than from a missing number alone.

Key mounted async state by the current surface/catalog mode/API-read toggle. When the key changes, synchronously expose that key's initial state before its effect resolves, include the toggle/key in effect dependencies, and ignore late results from the previous key.

Widen `ReplicaRuntimeBadgeProps` to the exported source/status contract and map `loading`, `empty`, `degraded` and `error` to truthful visible labels. Ready details must also distinguish `fixture`, `catalog`, `api` and `hybrid`; a fixture must never say `接口已校验`. Keep compatibility-workbench callers valid; do not change those workbenches in this task.

- [ ] **Step 1.5: Run focused and type checks**

```bash
pnpm --filter medical-audit-web exec vitest run src/lib/replica-adapters.test.ts src/components/replica/use-replica-runtime.test.tsx src/components/replica/replica-page-kit.test.tsx
pnpm web:typecheck
pnpm web:test
```

Expected: focused tests pass; typecheck exits 0.

- [ ] **Step 1.6: Conditional commit**

Only with explicit authorization:

```bash
git add web/src/lib/replica-adapters.ts web/src/lib/replica-adapters.test.ts web/src/components/replica/use-replica-runtime.ts web/src/components/replica/use-replica-runtime.test.tsx web/src/components/replica/replica-page-kit.tsx web/src/components/replica/replica-page-kit.test.tsx web/src/components/replica/replica-shell.test.tsx
git commit -m "fix: make replica runtime states truthful"
```

---

### Task 2: Finalize login, brand, 9+1 navigation and history entry

**Files:**

- Modify: `web/src/components/login/login-surface.tsx`
- Modify: `web/src/app/login/page.test.tsx`
- Modify: `web/src/lib/reference-replica-data.ts`
- Modify: `web/src/components/replica/replica-shell.tsx`
- Modify: `web/src/components/replica/replica-shell.test.tsx`
- Modify: `web/src/app/globals.css`

- [ ] **Step 2.1: Write the failing login contract**

Add or update assertions:

```ts
expect(screen.getByText("AI审计一体化协作平台")).toBeInTheDocument();
expect(screen.queryByText("医保基金合规审计")).not.toBeInTheDocument();
expect(screen.queryByLabelText("角色入口说明")).not.toBeInTheDocument();
expect(screen.queryByText("医院名称与 Logo 可在部署时配置")).not.toBeInTheDocument();
expect(screen.queryByRole("link", { name: "查看当前工作台" })).not.toBeInTheDocument();
```

Keep the account, password, remember-login, information-center and login assertions.

The retained `联系信息中心` entry must target an existing compact support note; do not leave a dead `#support` anchor and do not recreate the removed organization deployment panel.

Run:

```bash
pnpm --filter medical-audit-web exec vitest run src/app/login/page.test.tsx
```

Expected: FAIL on the elements that still render.

- [ ] **Step 2.2: Reduce the login component to the approved surface**

Delete `roleEntries`, the role strip, organization deployment panel and workspace preview link. Remove now-unused `Image`, `Link`, organization and subtitle imports. Keep `BrandLogo`, `AUDIT_PLATFORM_NAME`, `AUDIT_PLATFORM_DESCRIPTION`, account/password form behavior and safe redirect logic.

Keep a minimal `id="support"` note for account activation/password-reset guidance so the information-center link remains functional without restoring organization configuration content.

Delete only CSS selectors no longer referenced by this component, including `.audit-login-role-strip` and `.audit-login-org-panel`; do not format unrelated CSS.

- [ ] **Step 2.3: Write the failing 9+1 navigation tests**

```ts
const mainNav = screen.getByRole("navigation", { name: "主导航" });
expect(within(mainNav).getAllByRole("link")).toHaveLength(9);
expect(within(mainNav).queryByText("医保审计专题")).not.toBeInTheDocument();
expect(screen.getAllByRole("link", { name: "打开医保审计专题" })).toHaveLength(1);
expect(screen.queryByText("医保基金合规审计")).not.toBeInTheDocument();
```

For pathname `/medical-audit`, assert the topic link has `aria-current="page"` and the topbar/page tag say `医保审计专题`. Assert the history trigger has visible text `历史对话` and still opens/closes its drawer.

Assert the history disclosure reports `aria-expanded=false` with accessible name `打开历史对话`, then `true` with `收起历史对话`, and returns to `false` when toggled closed.

Run:

```bash
pnpm --filter medical-audit-web exec vitest run src/components/replica/replica-shell.test.tsx
```

Expected: FAIL because the main navigation contains 10 entries, subtitle renders, and history trigger is icon-only.

- [ ] **Step 2.4: Implement a separate topic navigation constant**

In `reference-replica-data.ts`:

```ts
export const referenceNavigation: readonly ReferenceNavigationItem[] = [
  // exactly the nine approved main modules
];

export const referenceTopicNavigation: ReferenceNavigationItem = {
  id: "medical-topic",
  label: "医保审计专题",
  href: "/medical-audit",
  icon: "shield"
};
```

In `replica-shell.tsx`, use the separate constant for the bottom entry and active title. Remove `AUDIT_PLATFORM_SUBTITLE` import/render. Render history trigger as icon plus visible label. Add only the topic active/collapsed styles and a responsive history pill to `globals.css`.

- [ ] **Step 2.5: Verify focused UI**

```bash
pnpm --filter medical-audit-web exec vitest run src/app/login/page.test.tsx src/components/replica/replica-shell.test.tsx
pnpm web:typecheck
pnpm web:lint
```

Expected: all commands exit 0.

- [ ] **Step 2.6: Conditional commit**

Only with explicit authorization:

```bash
git add web/src/components/login/login-surface.tsx web/src/app/login/page.test.tsx web/src/lib/reference-replica-data.ts web/src/components/replica/replica-shell.tsx web/src/components/replica/replica-shell.test.tsx web/src/app/globals.css
git commit -m "fix: align login and shell with approved navigation"
```

---

### Task 3: Preserve chat newline behavior and make agents directly usable

**Files:**

- Modify: `web/src/app/(workspace)/chat/page.test.tsx`
- Modify: `web/src/components/replica/replica-agent-directory.tsx`
- Modify: `web/src/components/replica/replica-agent-directory.test.tsx`
- Modify: `web/src/lib/replica-adapters.ts`
- Modify: `web/src/lib/replica-adapters.test.ts`
- Modify: `web/src/components/replica/use-replica-runtime.ts`
- Modify: `web/src/app/globals.css`

- [ ] **Step 3.1: Freeze the chat keyboard contract with a failing regression test**

Do not add `onKeyDown` to the textarea. Test native multiline input and button-only submission:

```ts
await user.type(textbox, "第一行{enter}第二行");
expect(textbox).toHaveValue("第一行\n第二行");
expect(runKnowledgeQuery).not.toHaveBeenCalled();

await user.click(screen.getByRole("button", { name: "发送问题" }));
expect(runKnowledgeQuery).toHaveBeenCalledWith(
  expect.objectContaining({ question: "第一行\n第二行" })
);
```

If the existing test dependencies do not include `@testing-library/user-event`, do not add it. Use the current `fireEvent` stack to dispatch `keyDown` with `key/code="Enter"`, then apply the multiline value via `change`/`input`; assert no query call occurred before clicking the send button. Name this fallback test for what it proves: Enter does not submit and a multiline value submits only after button click. Do not claim jsdom inserted the newline natively. A plain value assignment without an Enter key event is insufficient characterization evidence.

Run:

```bash
pnpm --filter medical-audit-web exec vitest run 'src/app/(workspace)/chat/page.test.tsx'
```

Expected: the new regression test passes against current behavior. Treat this as a characterization test, not a reason to change the page.

- [ ] **Step 3.2: Write failing direct-use and stable-pagination tests**

For mine mode, assert every visible card has an accessible link `立即使用：{name}` with `/chat?agent={encoded id}`. With 13 fixtures, assert page 1 shows 12 and page 2 shows the 13th. Dispatch a resize event and prove the page membership and page size do not change.

Also test a fifth API agent passed in `/chat?agent=fifth-id` is resolved, which currently fails because the adapter slices to four.

With API reads disabled, route a fifth fixture agent through the real `useReplicaChatData -> ChatPortalPage` chain and prove the URL selects it. The hook-level `chatFallback` must expose the same full fixture set as the disabled adapter path.

Select a mine agent, then change page or filter so it is no longer visible. Prove the open detail panel and its direct-use href immediately fall back to an agent on the current visible page rather than retaining the stale hidden selection. When a resize test overrides `innerWidth`/`innerHeight`, restore the complete original property descriptors so later tests are not polluted.

The fifth-agent URL test must exercise the real `loadReplicaChatData -> useReplicaChatData -> ChatPortalPage` chain. Do not mock `useReplicaChatData` with a prebuilt fifth card. Partially mock the API client so `fetchAgents` returns five complete API items and `fetchQueryHistory` returns an empty ready store while unrelated exports remain real. If the production slice was already removed before this integration test is written, perform a temporary mutation check that restores `slice(0, 4)`, observe the test fail, then restore the implementation before committing.

- [ ] **Step 3.3: Implement fixed product pagination and direct links**

Use:

```ts
const AGENT_PAGE_SIZE = 12;
```

Delete `estimateAgentPageSize`, `pageSize` state and the window resize effect. Make mine-card and detail-panel primary actions links:

```tsx
<Link
  aria-label={`立即使用：${agent.name}`}
  href={`/chat?agent=${encodeURIComponent(agent.id)}`}
>
  立即使用
</Link>
```

Keep lifecycle management buttons secondary. Keep market install behavior unchanged.

Give the new personal-agent direct-use anchors a dedicated class and scope their sizing/layout CSS to that class. Do not add a global `.replica-card-actions a` rule because the same action container is used by compatibility workbenches.

In `loadReplicaChatData`, map all returned agents; limit command-menu presentation inside the page rather than truncating adapter data.

In `use-replica-runtime.ts`, keep the API-disabled `chatFallback` aligned with the adapter by exposing all `referenceAgents`; do not retain a hook-only four-agent slice.

- [ ] **Step 3.4: Remove history/API empty contamination in shell/chat loaders**

When `fetchQueryHistory()` succeeds with `items=[]`, return `historyItems=[]`. When it fails, return `outcome="error"`; do not retain `referenceHistoryItems`. Preserve fixture history only when API reads are explicitly disabled.

- [ ] **Step 3.5: Run focused checks**

```bash
pnpm --filter medical-audit-web exec vitest run 'src/app/(workspace)/chat/page.test.tsx' src/components/replica/replica-agent-directory.test.tsx src/lib/replica-adapters.test.ts
pnpm web:typecheck
```

Expected: all tests pass; the mine direct-use link and fifth agent URL path are covered.

- [ ] **Step 3.6: Conditional commit**

Only with explicit authorization:

```bash
git add 'web/src/app/(workspace)/chat/page.test.tsx' web/src/components/replica/replica-agent-directory.tsx web/src/components/replica/replica-agent-directory.test.tsx web/src/lib/replica-adapters.ts web/src/lib/replica-adapters.test.ts web/src/components/replica/use-replica-runtime.ts web/src/app/globals.css
git commit -m "fix: make personal agents directly usable"
```

---

### Task 4: Make knowledge-base and document data truthful and source-scoped

**Files:**

- Create: `src/medical_audit_kb/api/search_backend_details.py`
- Modify: `src/medical_audit_kb/api/routes_knowledge_base.py`
- Modify: `src/medical_audit_kb/api/routes_documents.py`
- Modify: `tests/knowledge_query/test_api.py`
- Modify: `web/src/lib/api-types.ts`
- Modify: `web/src/lib/replica-adapters.ts`
- Modify: `web/src/lib/replica-adapters.test.ts`
- Modify: `web/src/components/replica/use-replica-runtime.ts`
- Modify: `web/src/app/(workspace)/knowledge-base/page.tsx`
- Modify: `web/src/app/(workspace)/knowledge-base/page.test.tsx`
- Modify: `web/src/app/(workspace)/documents/page.tsx`
- Modify: `web/src/app/(workspace)/documents/page.test.tsx`

- [ ] **Step 4.1: Write backend tests for unavailable metrics and safe details**

Add assertions that a registry-only catalog is not reported as real zero metrics:

```py
assert payload["boundaries"]["source"] == "runtime_state_and_registry_only"
assert payload["store"]["catalog_ready"] is True
assert payload["store"]["metrics_ready"] is False
```

For `/documents/source-collections`, inject nested backend details containing keys such as `token`, `password`, `api_key`, and `private_key` inside mappings and lists; assert neither the keys nor values appear in the response JSON. Include a URL-like string with credential query parameters and assert its userinfo/query secrets are removed.

Run:

```bash
uv run pytest tests/knowledge_query/test_api.py -k 'knowledge_base_catalog or document_source' -q
```

Expected: FAIL because metrics readiness is absent and documents returns raw backend details.

- [ ] **Step 4.2: Centralize safe backend details**

In the new module, implement a recursive allowlist/scrubber used by both routes:

```py
SENSITIVE_KEY_FRAGMENTS = ("secret", "token", "password", "private_key", "api_key", "credential")

def safe_search_backend_details(details: Mapping[str, object]) -> dict[str, object]:
    return {
        key: safe_search_backend_value(value)
        for key, value in details.items()
        if not any(fragment in key.lower() for fragment in SENSITIVE_KEY_FRAGMENTS)
    }

def safe_search_backend_value(value: object) -> object:
    if isinstance(value, Mapping):
        return safe_search_backend_details(value)
    if isinstance(value, (list, tuple)):
        return [safe_search_backend_value(item) for item in value]
    if isinstance(value, str):
        return redact_url_credentials_and_sensitive_query(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return "<unsupported-diagnostic-value>"

def redact_url_credentials_and_sensitive_query(value: str) -> str:
    parsed = urlsplit(value)
    if not parsed.scheme or not parsed.netloc:
        return value
    hostname = parsed.hostname or ""
    netloc = f"{hostname}:{parsed.port}" if parsed.port is not None else hostname
    safe_query = urlencode(
        (key, item)
        for key, item in parse_qsl(parsed.query, keep_blank_values=True)
        if not any(fragment in key.lower() for fragment in SENSITIVE_KEY_FRAGMENTS)
    )
    return urlunsplit((parsed.scheme, netloc, parsed.path, safe_query, parsed.fragment))
```

Import `parse_qsl`, `urlencode`, `urlsplit` and `urlunsplit` from Python's standard `urllib.parse`. Retain only JSON-safe diagnostic values, strip URL userinfo and sensitive query parameters, and do not log rejected values. Import this helper from both routes. The nested mapping/list test is required; a top-level-only filter is insufficient.

Treat diagnostic strings as untrusted. Catch `ValueError` from `urlsplit()` and `parsed.port`; never return the original string after a URL parse failure that might contain credentials. Rebuild IPv6 hosts with brackets, preserve only a valid non-sensitive port/query/fragment, and return a fixed redacted sentinel for malformed URL diagnostics. Add malformed-port and credentialed-IPv6 cases to the scrubber test.

Sanitize protocol-relative URLs (`//user:pass@host/...`) whenever `netloc` is present. A `scheme://` or `//` candidate with no valid hostname returns the invalid-URL sentinel rather than the original text. Canonicalize query keys and fragments through bounded, repeated percent-decoding before sensitive-fragment matching so double-encoded names cannot bypass the contract. Preserve only finite floats; map NaN and positive/negative infinity to the unsupported-value sentinel so JSON serialization cannot fail. Cover all of these cases through both catalog endpoints while retaining a plain non-URL diagnostic unchanged.

Use one normalized candidate for both URL parsing and URL-candidate detection; do not compare parser output with an unnormalized raw prefix. Match the active `urllib.parse` preprocessing semantics explicitly: strip leading ASCII C0 controls plus space (`0x00` through `0x20`) and remove TAB, CR and LF at every position before both operations. If percent canonicalization reaches its round limit and one more decode would still change the value, fail closed by treating that key/fragment as sensitive instead of returning the unstable representation. Add leading-whitespace/C0, embedded TAB/CR/LF empty-host and over-limit encoding regressions for both endpoints.

Set catalog store semantics explicitly:

```py
metrics_ready = store_backend == "runtime_state_and_postgres_catalog"
store={
    "ready": metrics_ready,
    "catalog_ready": True,
    "metrics_ready": metrics_ready,
    "backend": store_backend,
}
```

- [ ] **Step 4.3: Write frontend tests for real counts, unavailable counts, empty and error**

Knowledge base assertions:

- preserve the refreshed-baseline tests that already render PostgreSQL catalog numbers (`49,051` current-search embeddings and per-card `120` chunks) exactly;
- registry-only renders `待同步`, never `0` as a substitute;
- documents/chat/graph links retain the selected `source_collection`;
- empty and error states are distinct.

Document assertions:

- initial live page does not render hard-coded `referenceDocumentResults`, cross-industry project documents or reference search history;
- successful empty search displays `未找到匹配文档`;
- 409/backend failure displays error and retry, not zero/empty;
- real result opens preview and passes the same source scope to AI conversation;
- `AI+` runs only after an explicit click and reports its `provider_call` boundary separately from pure document search.

- [ ] **Step 4.4: Implement catalog and document page states**

Extend `ReplicaKnowledgeBaseData` with catalog summary, store and boundaries while preserving its existing `chunkCount`, `currentSearchEmbeddingCount` and `metricsSource` fields. Use a replica-specific knowledge-base item type when necessary so API-derived `documentCount`, `chunkCount` and `appCount` can be `null` without weakening version-controlled fixture types. When `metrics_ready=false`, map unavailable summary/item counts to `null`, set runtime outcome to `degraded`, and do not fall back to tag parsing. Update every knowledge-base empty/fixture shape in `use-replica-runtime.ts` so the extended result contract remains explicit and type-safe. Remove `referenceDocumentResults`, `referenceSearchHistory` and hard-coded category numbers from live document flow. Use an explicit page search state:

```ts
type DocumentSearchState =
  | { readonly kind: "idle" }
  | { readonly kind: "searching" }
  | { readonly kind: "results"; readonly response: DocumentSearchResponse }
  | { readonly kind: "empty"; readonly response: DocumentSearchResponse }
  | { readonly kind: "error"; readonly message: string };
```

Do not collapse a thrown error into `items=[]`. Keep the existing preview and source-scoped links.

- [ ] **Step 4.5: Verify backend and frontend contracts**

```bash
uv run pytest tests/knowledge_query/test_api.py -k 'knowledge_base_catalog or documents_search or document_source' -q
pnpm --filter medical-audit-web exec vitest run src/lib/replica-adapters.test.ts 'src/app/(workspace)/knowledge-base/page.test.tsx' 'src/app/(workspace)/documents/page.test.tsx'
pnpm web:typecheck
pnpm web:lint
```

Expected: all commands exit 0; live-mode tests contain no fixture documents or numbers.

- [ ] **Step 4.6: Conditional commit**

Only with explicit authorization:

```bash
git add src/medical_audit_kb/api/search_backend_details.py src/medical_audit_kb/api/routes_knowledge_base.py src/medical_audit_kb/api/routes_documents.py tests/knowledge_query/test_api.py web/src/lib/api-types.ts web/src/lib/replica-adapters.ts web/src/lib/replica-adapters.test.ts web/src/components/replica/use-replica-runtime.ts 'web/src/app/(workspace)/knowledge-base/page.tsx' 'web/src/app/(workspace)/knowledge-base/page.test.tsx' 'web/src/app/(workspace)/documents/page.tsx' 'web/src/app/(workspace)/documents/page.test.tsx'
git commit -m "fix: make knowledge and document states source truthful"
```

---

### Task 5: Add canonical project states and collaboration visibility

**Files:**

- Modify: `src/medical_audit_kb/api/project_member_store.py`
- Modify: `src/medical_audit_kb/api/routes_projects.py`
- Modify: `tests/knowledge_query/test_api.py`
- Modify: `web/src/lib/api-types.ts`
- Modify: `web/src/lib/api-client.ts`
- Modify: `web/src/lib/api-client.test.ts`
- Create: `web/src/components/replica/replica-project-workbench.tsx`
- Create: `web/src/components/replica/replica-project-workbench.test.tsx`
- Modify: `web/src/app/(workspace)/projects/page.tsx`
- Modify: `web/src/app/(workspace)/projects/page.test.tsx`
- Modify: `web/src/app/globals.css`

- [ ] **Step 5.1: Write backend visibility and status tests**

Cover:

1. admin sees all projects;
2. creator sees their project;
3. active member sees their project;
4. unrelated member does not see it in list and receives 404 for members/dashboard;
5. unrelated member receives 404 from the refreshed-baseline detail route `GET /projects/{project_key}`;
6. adding a member requires `user_identifier` and persists it without a schema change;
7. response publishes `project_statuses=["待开始","进行中","已完成","已归档"]`;
8. member without `MANAGE_PROJECT_MEMBERS` cannot POST.

Run:

```bash
uv run pytest tests/knowledge_query/test_api.py -k 'projects_api' -q
```

Expected: FAIL because GET list is unfiltered, member identity is not present, and canonical project statuses are absent.

- [ ] **Step 5.2: Implement identity without a database migration**

Add:

```py
PROJECT_STATUSES = ("待开始", "进行中", "已完成", "已归档")
```

Normalize legacy `待启动` to `待开始` in payload mapping. Add `creator_user_identifier` to default project definitions and `user_identifier` to default members. For custom members, persist `user_identifier` inside the existing JSON `metadata` column and expose it as a top-level response field.

Add a shared helper in `project_member_store.py`:

```py
def visible_project_keys(
    *, user_identifier: str, is_admin: bool, store: ProjectMemberStore
) -> frozenset[str]:
    if is_admin:
        return frozenset(str(item["id"]) for item in DEFAULT_PROJECT_PAYLOADS)
    # include creator ids and active member metadata identities only
```

Use `resolve_authenticated_user()` in all GET project routes, including the refreshed-baseline `GET /projects/{project_key}` detail route. Filter the collection response and return 404 for unauthorized detail, members and dashboard reads. Add `project_statuses` while retaining existing member `statuses` for backward compatibility.

- [ ] **Step 5.3: Write failing project workbench tests**

Assert the route no longer renders `内测中`. Test list -> select -> members/dashboard; four status filters; current visibility label; store empty/error states; and role-gated add-member form. A read-only member can inspect a visible project but cannot see an enabled “新增成员” submit button.

- [ ] **Step 5.4: Implement the replica project workbench**

Use existing clients:

```ts
fetchProjects()
fetchProjectMembers(projectId)
fetchProjectDashboard(projectId)
createProjectMember(projectId, payload)
```

Extend `ProjectMemberCreateRequest` with `user_identifier`. Update `ApiProjectStatus` to:

```ts
export type ApiProjectStatus = "待开始" | "进行中" | "已完成" | "已归档";
```

Render table fields required by the PRD, explicit loading/empty/error, members and dashboard. Keep all write buttons gated by current client permission and backend enforcement.

- [ ] **Step 5.5: Verify project slice**

```bash
uv run pytest tests/knowledge_query/test_api.py -k 'projects_api' -q
pnpm --filter medical-audit-web exec vitest run src/lib/api-client.test.ts src/components/replica/replica-project-workbench.test.tsx 'src/app/(workspace)/projects/page.test.tsx'
pnpm web:typecheck
pnpm web:lint
```

Expected: all commands pass; project tests prove owner/member/admin visibility rather than creator-only visibility.

- [ ] **Step 5.6: Conditional commit**

Only with explicit authorization:

```bash
git add src/medical_audit_kb/api/project_member_store.py src/medical_audit_kb/api/routes_projects.py tests/knowledge_query/test_api.py web/src/lib/api-types.ts web/src/lib/api-client.ts web/src/lib/api-client.test.ts web/src/components/replica/replica-project-workbench.tsx web/src/components/replica/replica-project-workbench.test.tsx 'web/src/app/(workspace)/projects/page.tsx' 'web/src/app/(workspace)/projects/page.test.tsx' web/src/app/globals.css
git commit -m "feat: restore project collaboration workbench"
```

---

### Task 6: Restore the table-first analytics workbench

**Files:**

- Create: `web/src/components/replica/replica-analytics-workbench.tsx`
- Create: `web/src/components/replica/replica-analytics-workbench.test.tsx`
- Modify: `web/src/app/(workspace)/analytics/page.tsx`
- Create: `web/src/app/(workspace)/analytics/page.test.tsx`
- Modify: `web/src/lib/replica-adapters.ts`
- Modify: `web/src/lib/replica-adapters.test.ts`
- Modify: `web/src/app/globals.css`
- Verify only: `src/medical_audit_kb/api/routes_analytics.py`
- Verify only: `tests/knowledge_query/test_api.py`

- [ ] **Step 6.1: Write the failing page/component tests**

Assert:

- `内测中` is absent;
- `.xlsx` and `.csv` can be selected;
- clicking upload calls `uploadAnalysisTable(file)` exactly once;
- row count, columns, empty cells, duplicates, quality findings, audit signals and recommendations render from the response;
- history ready/empty/error states do not display reference datasets;
- the page contains no OCR button, upload control or clickable OCR entry; a non-interactive scope note may state that OCR is outside this batch.

Run:

```bash
pnpm --filter medical-audit-web exec vitest run src/components/replica/replica-analytics-workbench.test.tsx 'src/app/(workspace)/analytics/page.test.tsx'
```

Expected: FAIL because the route is still `ReplicaPreviewPage`.

- [ ] **Step 6.2: Implement the workbench by reusing current APIs**

Use `uploadAnalysisTable` and `fetchAnalysisUploadHistory`; do not duplicate parsing in the browser. Render the backend `TableAnalysisUploadResponse` fields. Use `accept=".xlsx,.csv"`, while retaining backend extension and size validation as the authority.

The page must describe document summarization as a link to `/documents` or `/chat`, not as a second document-analysis engine. Do not add OCR code, an OCR provider, or a disabled OCR control that looks like a future product entry.

- [ ] **Step 6.3: Keep upload side effects explicit**

Before submit, show that upload persists a controlled analysis record when the backend store is ready. On 413/422, display the backend message. On store failure, do not claim retention. Never auto-upload on file selection.

- [ ] **Step 6.4: Verify frontend and existing backend contracts**

```bash
uv run pytest tests/knowledge_query/test_api.py -k 'analytics_table_upload' -q
pnpm --filter medical-audit-web exec vitest run src/components/replica/replica-analytics-workbench.test.tsx 'src/app/(workspace)/analytics/page.test.tsx' src/lib/replica-adapters.test.ts
pnpm web:typecheck
pnpm web:lint
```

Expected: existing CSV/XLSX/unsupported-extension backend tests and new UI tests pass.

- [ ] **Step 6.5: Conditional commit**

Only with explicit authorization:

```bash
git add web/src/components/replica/replica-analytics-workbench.tsx web/src/components/replica/replica-analytics-workbench.test.tsx 'web/src/app/(workspace)/analytics/page.tsx' 'web/src/app/(workspace)/analytics/page.test.tsx' web/src/lib/replica-adapters.ts web/src/lib/replica-adapters.test.ts web/src/app/globals.css
git commit -m "feat: restore table analytics workbench"
```

---

### Task 7: Add six report categories, controlled draft handoff and the report workbench

**Files:**

- Modify: `src/medical_audit_kb/api/auth.py`
- Modify: `src/medical_audit_kb/api/routes_pages.py`
- Modify: `tests/knowledge_query/test_api.py`
- Modify: `tests/knowledge_query/test_pages.py`
- Modify: `web/src/lib/api-types.ts`
- Modify: `web/src/lib/api-client.ts`
- Modify: `web/src/lib/api-client.test.ts`
- Create: `web/src/components/replica/replica-report-workbench.tsx`
- Create: `web/src/components/replica/replica-report-workbench.test.tsx`
- Modify: `web/src/app/(workspace)/reports/page.tsx`
- Create: `web/src/app/(workspace)/reports/page.test.tsx`
- Modify: `web/src/app/globals.css`

- [ ] **Step 7.1: Write failing backend category and draft tests**

Freeze the six category directory:

```py
assert [item["label"] for item in payload["template_categories"]] == [
    "计划类", "底稿类", "取证类", "函证类", "报告类", "整改类"
]
assert {item["id"] for item in payload["workpaper_templates"]} == {
    "workpaper-summary-risk",
    "workpaper-category-review",
    "workpaper-visit-detail",
}
```

All three current templates must have `category_id="workpaper"` and remain the only active templates until business templates arrive. Other categories use `availability="awaiting-business-template"`.

Add a POST draft test with `template_id`, visible `project_key`, and `field_values` restricted to the template's `evidence_bindings`. Assert a review-task draft is persisted in the test store with dossier metadata containing template id/category/project/user and the response returns `/projects?project={project_key}`. Assert unknown template and unknown field are rejected.

Add authorization cases: missing identity -> 401; visible project plus a role without `CREATE_REPORT_DRAFT` -> 403; authenticated non-member project -> 404; active project member/director/admin with permission -> success. Assert each denial writes an authorization audit event without template field values or sensitive data.

- [ ] **Step 7.2: Implement category metadata and narrow draft endpoint**

Add:

```py
REPORT_TEMPLATE_CATEGORIES = (
    {"id": "plan", "label": "计划类", "availability": "awaiting-business-template"},
    {"id": "workpaper", "label": "底稿类", "availability": "active"},
    {"id": "evidence", "label": "取证类", "availability": "awaiting-business-template"},
    {"id": "confirmation", "label": "函证类", "availability": "awaiting-business-template"},
    {"id": "report", "label": "报告类", "availability": "awaiting-business-template"},
    {"id": "remediation", "label": "整改类", "availability": "awaiting-business-template"},
)
```

Add `category_id="workpaper"` to each registry item and return categories from both report endpoints.

Add `Permission.CREATE_REPORT_DRAFT` in `auth.py`. Grant it to `admin`, `director` and `member`; do not grant it to `technician`. Project membership/creator visibility remains an additional resource check, so permission alone does not expose another project.

Implement `POST /reports/drafts` using the existing `ReviewTaskStore`; do not create a new table. Resolve identity, conceal unauthorized project existence with 404, then enforce `CREATE_REPORT_DRAFT` with 403 and audit all denials. Validate field keys against `evidence_bindings`, write the template/project metadata into `dossier`, call `record_operation`, and return the new task id plus project href. This endpoint creates a draft only; it does not sign, export or call a provider.

- [ ] **Step 7.3: Add typed client contract**

Add:

```ts
export type ReportTemplateCategory = {
  readonly id: "plan" | "workpaper" | "evidence" | "confirmation" | "report" | "remediation";
  readonly label: string;
  readonly availability: "active" | "awaiting-business-template";
};
```

Extend `WorkpaperTemplateRegistryItem` with `category_id`. Add `createReportDraft(payload)` and request/response types. Test exact POST path/body and typed response.

- [ ] **Step 7.4: Write failing report workbench tests**

Assert:

- route no longer shows `内测中`;
- all six categories render in fixed order;
- only bottom-paper active templates have “填写模板”; blocked categories say `待业务模板确认` and have no enabled create button;
- template form fields come from `evidence_bindings`;
- successful draft response exposes a “转入项目管理” link;
- report entries, evidence sources, gate status and non-null download links render from API;
- blocked reports cannot display an enabled sign action;
- empty/error does not fall back to `referenceReportRecords`.

- [ ] **Step 7.5: Implement the report workbench**

Build `ReplicaReportWorkbench` around `fetchReportWorkbench()` and `createReportDraft()`. Keep signing and formal report generation out of this page. Render download anchors only for non-null URLs already returned by the backend.

- [ ] **Step 7.6: Verify report slice**

```bash
uv run pytest tests/knowledge_query/test_pages.py -k 'report_workpaper_template_registry or report_workbench or report_template_draft' -q
pnpm --filter medical-audit-web exec vitest run src/lib/api-client.test.ts src/components/replica/replica-report-workbench.test.tsx 'src/app/(workspace)/reports/page.test.tsx'
pnpm web:typecheck
pnpm web:lint
```

Expected: six categories, three active real templates, draft-to-project metadata and gate-safe UI all pass.

- [ ] **Step 7.7: Conditional commit**

Only with explicit authorization:

```bash
git add src/medical_audit_kb/api/auth.py src/medical_audit_kb/api/routes_pages.py tests/knowledge_query/test_api.py tests/knowledge_query/test_pages.py web/src/lib/api-types.ts web/src/lib/api-client.ts web/src/lib/api-client.test.ts web/src/components/replica/replica-report-workbench.tsx web/src/components/replica/replica-report-workbench.test.tsx 'web/src/app/(workspace)/reports/page.tsx' 'web/src/app/(workspace)/reports/page.test.tsx' web/src/app/globals.css
git commit -m "feat: add report catalog and project draft handoff"
```

---

### Task 8: Split graph into knowledge-basis and project-evidence views

**Files:**

- Modify: `src/medical_audit_kb/api/audit_finding_store.py`
- Modify: `src/medical_audit_kb/api/routes_workbench.py`
- Modify: `tests/knowledge_query/test_api.py`
- Modify: `web/src/lib/api-types.ts`
- Modify: `web/src/lib/api-client.ts`
- Modify: `web/src/lib/api-client.test.ts`
- Modify: `web/src/lib/replica-adapters.ts`
- Modify: `web/src/lib/replica-adapters.test.ts`
- Modify: `web/src/app/(workspace)/graph/page.tsx`
- Modify: `web/src/app/(workspace)/graph/page.test.tsx`
- Modify: `web/src/app/globals.css`

- [ ] **Step 8.1: Write failing backend dual-view tests**

Default request must remain knowledge view. Add:

```py
knowledge = client.get("/api/v1/graph/workbench", headers=member_headers)
assert knowledge.json()["view"] == "knowledge"
assert knowledge.json()["project_key"] is None

project = client.get(
    "/api/v1/graph/workbench?view=project&project_key=SELF-CHECK-FUND-20260607",
    headers=member_headers,
)
assert project.json()["view"] == "project"
assert project.json()["project_key"] == "SELF-CHECK-FUND-20260607"
```

Add parameter-validation tests: `view=project` without a non-blank `project_key` returns 422; `view=knowledge` with any `project_key` also returns 422. No store query or audit-data read may run after either invalid request.

Create two projects with independent tasks, runs, findings and linked review tasks. Assert each project graph contains only its own finding/review/report ids and never the other project's ids. Assert a standalone report draft is included only when `dossier.project_key` matches. Unauthorized users receive 404. No project data produces a project node plus an explicit empty evidence-chain status, not static fake findings.

First add a store/API contract test for `list_findings(project_key=...)` and payload `project_key`; this must fail before the graph builder is changed.

- [ ] **Step 8.2: Extend the existing endpoint, not the infrastructure**

Add query parameters:

```py
view: Annotated[Literal["knowledge", "project"], Query()] = "knowledge"
project_key: Annotated[str | None, Query(max_length=128)] = None
```

Validate the pair before resolving project data:

```py
normalized_project_key = (project_key or "").strip()
if view == "project" and not normalized_project_key:
    raise HTTPException(status_code=422, detail="project_key is required for project graph view")
if view == "knowledge" and normalized_project_key:
    raise HTTPException(status_code=422, detail="project_key is not allowed for knowledge graph view")
```

In `audit_finding_store.py`, add optional `project_key` to `list_findings()`. Filter through `AuditFinding.audit_task_id -> AuditTask.project_id -> AuditProject.project_key`, eager-load `AuditFinding.audit_task -> AuditTask.project`, and expose `project_key` in each finding payload. Do not infer a project from a finding title or metadata string.

Keep `_knowledge_catalog_graph()` for knowledge view. Add `_project_evidence_graph()` that calls `list_findings(project_key=...)`. Collect review task ids only from those findings; additionally include template drafts only when their dossier has the exact same `project_key`. Build report/remediation nodes only from that filtered review-task set. Do not add a graph database and do not import the static `GRAPH_NODES`/`GRAPH_RELATIONS` as project evidence.

Return `view`, `project_key`, `evidence_grade`, `production_side_effect="none"`, nodes, relations, metrics and store state.

- [ ] **Step 8.3: Add typed client parameters and tests**

Change to:

```ts
fetchGraphWorkbench(options?: {
  readonly view?: "knowledge" | "project";
  readonly projectKey?: string;
}): Promise<GraphWorkbenchResponse>
```

Assert project requests encode both query parameters and default calls preserve the existing path.

- [ ] **Step 8.4: Write and implement frontend tab tests**

Assert the default tab is `知识依据`, the second is `项目证据链`, switching requests a selected visible project, nodes preserve source/evidence-grade details, and an empty project chain shows an empty state. Keep documents/chat links scoped. Add a disabled note `业务流程图谱：等待医院流程输入`; do not render it as a third working tab.

- [ ] **Step 8.5: Verify graph slice**

```bash
uv run pytest tests/knowledge_query/test_api.py -k 'graph_workbench' -q
pnpm --filter medical-audit-web exec vitest run src/lib/api-client.test.ts src/lib/replica-adapters.test.ts 'src/app/(workspace)/graph/page.test.tsx'
pnpm web:typecheck
pnpm web:lint
```

Expected: both views pass; project view contains no hard-coded evidence records.

- [ ] **Step 8.6: Conditional commit**

Only with explicit authorization:

```bash
git add src/medical_audit_kb/api/audit_finding_store.py src/medical_audit_kb/api/routes_workbench.py tests/knowledge_query/test_api.py web/src/lib/api-types.ts web/src/lib/api-client.ts web/src/lib/api-client.test.ts web/src/lib/replica-adapters.ts web/src/lib/replica-adapters.test.ts 'web/src/app/(workspace)/graph/page.tsx' 'web/src/app/(workspace)/graph/page.test.tsx' web/src/app/globals.css
git commit -m "feat: add project evidence graph view"
```

---

### Task 9: Keep medical agents default and add an opt-in three-agent validation pack

**Files:**

- Modify: `web/src/lib/audit-agent-catalog.ts`
- Create: `web/src/lib/audit-agent-catalog.test.ts`
- Modify: `web/src/lib/reference-replica-data.ts`
- Modify: `web/src/lib/replica-adapters.ts`
- Modify: `web/src/lib/replica-adapters.test.ts`
- Modify: `web/src/components/replica/replica-agent-directory.tsx`
- Modify: `web/src/components/replica/replica-agent-directory.test.tsx`
- Verify only: `web/src/data/audit-agent-prompts.json`
- Verify only: `src/medical_audit_kb/api/agent_store.py`
- Verify only: `src/medical_audit_kb/api/chat_models.py`
- Modify if regression coverage is missing: `tests/knowledge_query/test_api.py`
- Modify if regression coverage is missing: `tests/knowledge_query/test_scripts.py`

- [ ] **Step 9.1: Write failing catalog scope tests**

The default catalog must contain only the three backend-aligned medical/HIS templates: citation check, duplicate-charge review and report draft. The extension validation pack must contain exactly these source rows:

```ts
const EXTENSION_VALIDATION_KEYS = [
  ["财务收支审计", "超标准举办会议"],
  ["采购招标审计", "违法订立与招投标文件不符的合同或协议"],
  ["工程审计", "未经批准，擅自改变工程建设项目招标方式"]
] as const;
```

Deduplicate repeated source rows by category/title and retain source-file metadata. Assert the default marketplace excludes all three extension agents.

- [ ] **Step 9.2: Implement explicit exports and feature gate**

Export:

```ts
export const medicalAuditAgentCatalog: readonly ReferenceAgentCard[] = /* 3 medical templates */;
export const auditExtensionValidationCatalog: readonly ReferenceAgentCard[] = /* exact 3 filtered rows */;
```

Set `referenceMarketAgents` to the medical catalog. Add extension agents only when `NEXT_PUBLIC_MEDICAL_AUDIT_AGENT_EXTENSION_PACK === "1"`, and show an `扩展验证包` badge. Do not delete or rewrite the source JSON.

`loadReplicaAgentMarketData` must return `source="catalog"`, `outcome="ready"` and must not call `fetchAgents()`: the installed/personal agent API is not a marketplace catalog. Mine-mode agents continue to use the API and the Task 1 empty/error rules. Add an adapter test proving the market loader does not invoke the supplied personal-agent client.

- [ ] **Step 9.3: Prove installation and direct use locally**

For each extension agent under the enabled flag, test template detail -> install via `createAuditAgent` -> returned id -> `/chat?agent={id}` link. This proves application wiring only; it does not call a provider.

- [ ] **Step 9.4: Re-run model catalog and readiness contracts**

The model directory contract must continue to report aliases and boundaries without a provider call. Preserve the refreshed-baseline mapping: alias `kimi-2.7` labels `Kimi K2.6（兼容别名）`, uses model `kimi-k2.6`, `https://api.moonshot.cn/v1`, default/minimum 4096 output tokens and thinking enabled; DeepSeek requires thinking disabled. Do not revert these values while editing shared tests or mocks. A model with `available=false` must remain disabled in chat. Use the existing fake provider only inside tests:

```bash
MEDICAL_AUDIT_KB_CHAT_MODEL_KIMI_2_7_API_KEY_ENV=TEST_CHAT_MODEL_KEY \
TEST_CHAT_MODEL_KEY=dummy \
MEDICAL_AUDIT_KB_CHAT_MODEL_KIMI_2_7_PROVIDER=fake \
MEDICAL_AUDIT_KB_ALLOW_FAKE_CHAT_MODELS=1 \
uv run pytest tests/knowledge_query/test_api.py -k 'chat_model' -q
```

Expected: local fake-provider contract passes; no external network call occurs.

- [ ] **Step 9.5: Run catalog/UI tests**

```bash
pnpm --filter medical-audit-web exec vitest run src/lib/audit-agent-catalog.test.ts src/lib/replica-adapters.test.ts src/components/replica/replica-agent-directory.test.tsx 'src/app/(workspace)/chat/page.test.tsx'
uv run pytest tests/knowledge_query/test_api.py tests/knowledge_query/test_scripts.py -k 'chat_model or provider_gate' -q
pnpm web:typecheck
```

Expected: default catalog is medical-only; extension flag exposes exactly three validation agents; provider boundaries remain false outside the fake test.

- [ ] **Step 9.6: Conditional commit**

Only with explicit authorization:

```bash
git add web/src/lib/audit-agent-catalog.ts web/src/lib/audit-agent-catalog.test.ts web/src/lib/reference-replica-data.ts web/src/lib/replica-adapters.ts web/src/lib/replica-adapters.test.ts web/src/components/replica/replica-agent-directory.tsx web/src/components/replica/replica-agent-directory.test.tsx tests/knowledge_query/test_api.py tests/knowledge_query/test_scripts.py
git commit -m "feat: separate medical agents from extension validation"
```

---

### Task 10: Run full acceptance and synchronize stable documentation

**Files:**

- Modify: `docs/product/product-prd-medical-audit-v1-stable.md`
- Modify: `docs/product/product-development-plan-medical-audit-stable.md`
- Verify only: `docs/workflows/workflow-project-state-and-debt-register-stable.md` (protected pre-existing user changes; do not overwrite or stage)
- Modify: `docs/superpowers/specs/2026-07-11-ppt-feedback-product-alignment-design.md`
- Modify: `docs/superpowers/plans/2026-07-11-ppt-feedback-product-optimization.md`
- Create: `tmp/outputs/ppt-feedback-product-optimization-local-acceptance-20260711.json`
- Create: `tmp/screenshots/ppt-feedback-product-optimization/` screenshots during Playwright verification

- [x] **Step 10.1: Run all focused backend tests together**

```bash
uv run pytest tests/knowledge_query/test_api.py tests/knowledge_query/test_pages.py tests/knowledge_query/test_scripts.py -q
```

Expected: exit 0. Record exact pass count and duration; do not copy an earlier count into the report.

Actual: exit `0`, `281 passed` in `55.48s`; the original pre-review run was `275 passed`, and the fresh post-review suite includes six added regression tests.

- [x] **Step 10.2: Run all frontend gates**

```bash
pnpm web:test
pnpm web:typecheck
pnpm web:lint
pnpm web:build
```

Expected: all commands exit 0. If output is truncated, rerun the failing or final summary command narrowly before concluding.

Actual: `32 files / 267 tests`, typecheck exit `0`, lint exit `0`, build exit `0` with `24/24` static pages; only the existing multiple-lockfile workspace-root warning remained.

- [x] **Step 10.3: Run local full-stack E2E**

```bash
pnpm local:fullstack:e2e
```

Expected: exit 0 with the fresh pass count. Local writes must use test/local stores only.

Actual: final exclusive post-visual run exit `0`, `13 passed` in `46.5s`. Earlier attempts exposed port ownership, concurrent `.next` mutation and stale E2E contracts; those failures were diagnosed and retained as non-product evidence instead of being hidden.

- [x] **Step 10.4: Run visual and interaction acceptance**

Capture login, chat, agents, knowledge base, documents, analytics, graph, reports and projects at:

- 1440×900 at 100%;
- 1280×800 at 67%, 100% and 125%;
- 390×844 at 100%.

For agent zoom checks, record the first-page agent ids and assert the set is identical at 67%, 100% and 125%. Verify no horizontal overflow, the history pill does not cover chat controls, and the topic entry remains unique.

Actual: local production `next start` runtime, `45/45` screenshots passed. Filename-sorted screenshot checksum-list aggregate SHA256 is `ab60b945d4f6327d37d1939e1d5fed3c3ad31e13fdd38bf6161fc722c9c8ed09`; agent ids were invariant (`agent-citation-check`, `agent-duplicate-charge`, `agent-report-draft`). The project action-column clipping and history-button overlap found during visual QA were fixed and recaptured before the pass verdict.

- [x] **Step 10.5: Write a machine-readable local acceptance report**

The JSON must include:

```json
{
  "baseline_sha": "actual-sha",
  "production_side_effect": "none",
  "provider_call": false,
  "database_write": "local-test-only",
  "requirements": {
    "R01": "pass",
    "R19": "pass"
  },
  "commands": [],
  "screenshots": [],
  "known_blockers": [
    "hospital_process_graph_input_missing",
    "non-workpaper_business_templates_missing",
    "real_provider_smoke_requires_authorization"
  ]
}
```

Include all R01-R19 keys, exact commands, exit codes and paths. Do not include secrets or raw PII.

Actual: `tmp/outputs/ppt-feedback-product-optimization-local-acceptance-20260711.json`, `361` lines, SHA256 `865effa25cb7b905db056af7034707ceaf8eb8bea33d57aecb338e74acbc44d5`; all R01-R19 are `pass`, all 45 screenshot paths exist.

- [x] **Step 10.6: Synchronize stable docs from verified facts only**

Update the PRD brand requirement to `AI审计一体化协作平台`, record the 9+1 navigation decision, table-first analytics, six-category report directory, collaboration project visibility, dual graph views and extension-agent scope. Update development/state docs with actual test results and remaining blockers. Do not write `已生产验收` unless production was separately verified in this execution.

- [x] **Step 10.7: Run documentation integrity checks**

```bash
rg -n 'T[B]D|TODO l[a]ter|implement l[a]ter|fill in d[e]tails|production c[o]mplete' docs/superpowers/specs/2026-07-11-ppt-feedback-product-alignment-design.md docs/superpowers/plans/2026-07-11-ppt-feedback-product-optimization.md docs/product/product-prd-medical-audit-v1-stable.md docs/product/product-development-plan-medical-audit-stable.md docs/workflows/workflow-project-state-and-debt-register-stable.md
git diff --check
git status --short
```

Expected: placeholder search returns no matches; `git diff --check` exits 0; status contains only scoped files and generated local acceptance artifacts.

Actual: placeholder search returned no matches and `git diff --check` exited `0`. Status contains the four scoped stable/design/plan docs plus the three explicitly protected pre-existing user document changes; the ignored `tmp/` acceptance artifacts are present but intentionally not staged.

- [ ] **Step 10.8: Optional production read-only gate after explicit authorization**

Only after the owner explicitly authorizes production read-only checks:

```bash
pnpm production:chat-model-catalog-readonly
pnpm production:chat-model-ready
pnpm production:permission-readonly
pnpm production:frontend-acceptance
```

Interpret separately:

- catalog pass proves aliases are observable, not callable;
- ready failure with `available_model_aliases=[]` is an expected blocker;
- permission/frontend pass is read-only evidence, not deploy or provider proof.

Actual: not executed because no separate production read-only authorization was given. `production unchanged` and `provider_call=false` remain the final boundary.

- [x] **Step 10.9: Request code review**

Use `superpowers:requesting-code-review`. Review must inspect data-source truthfulness, project authorization, report draft write boundaries, graph scope filtering and the default medical agent catalog.

Actual: initial review found six Important and two Minor issues; all eight were fixed with regression tests. Final re-review: Critical `0`, Important `0`, Minor `0`, Ready `YES`.

- [x] **Step 10.10: Conditional final commit**

Only with explicit authorization and only after review findings are resolved:

```bash
git add docs/product/product-prd-medical-audit-v1-stable.md docs/product/product-development-plan-medical-audit-stable.md docs/superpowers/specs/2026-07-11-ppt-feedback-product-alignment-design.md docs/superpowers/plans/2026-07-11-ppt-feedback-product-optimization.md
git commit -m "docs: record ppt feedback implementation evidence"
```

Do not commit `tmp/` artifacts unless the repository policy and owner explicitly require them.

Actual: owner authorized local task commits. Code hardening commit `078adcc5` and local full-stack contract commit `52724231` were created; this final documentation-only commit records the verified acceptance state. No push, merge or deploy was performed.

---

## Final definition of done

- [x] R01-R19 each have a passing automated or visual acceptance item.
- [x] Login contains no subtitle, role strip, deployment hint or workspace preview link.
- [x] Main navigation has exactly 9 entries and the topic appears exactly once.
- [x] Enter never submits chat; arrow submit works with multiline text.
- [x] Agent first-page membership is invariant across requested zoom levels.
- [x] API empty/error states never render live fixture records or numbers.
- [x] Knowledge and document links preserve source scope.
- [x] Analytics, reports and projects are no longer preview pages.
- [x] Project visibility is enforced by backend identity, not frontend hiding.
- [x] Graph has knowledge and project views without a graph database or fake project evidence.
- [x] Default agent market is medical-only; extension pack contains exactly three approved agents.
- [x] No real provider call, production write, deploy or merge occurred without separate authorization.
- [x] Fresh backend, frontend, build and local E2E evidence is recorded.
- [x] Stable documentation matches verified code and remaining blockers.
