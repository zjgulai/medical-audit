---
title: "PR 182 conflict strategy loop45"
project: "medical_audit"
created_at: "2026-07-02T08:54:00+08:00"
status: "reviewed"
evidence_grade: "github-pr-plus-local-merge-tree-readonly"
pr: 182
branch: "codex/frontend-2.0"
base: "main"
---

# PR 182 Conflict Strategy Loop45

## Scope

This loop reviews Draft PR `#182` conflict and CI state only.

It does not resolve conflicts, mark the PR ready for review, merge, deploy, probe production, call providers, touch Docker, or run write-path smoke.

## Facts

- Current branch: `codex/frontend-2.0`.
- Current HEAD and `origin/codex/frontend-2.0`: `ed36b1459b8ae1083b7c6906d715463a2f1db9c9`.
- Current `origin/main`: `b1c9a6c229a7880afcbfed35c1903d514914bb15`.
- Merge base: `818b42b7c1045308d0e7e191a97c81e015cacc2f`.
- PR `#182`: `OPEN`, `isDraft=true`, `mergeable=CONFLICTING`.
- `gh pr checks 182 --watch=false`: no checks reported.
- Worktree before this docs update: clean tracked state, with only untracked `output/` evidence artifacts.

## Conflict Surface

`git merge-tree $(git merge-base HEAD origin/main) HEAD origin/main` reports semantic conflicts in these files:

- `scripts/run-production-frontend-acceptance.mjs`
- `web/src/app/(workspace)/agent-market/page.tsx`
- `web/src/app/(workspace)/chat/page.tsx`
- `web/src/app/(workspace)/fund-compliance/page.tsx`
- `web/src/app/(workspace)/fund-compliance/review/page.tsx`
- `web/src/app/(workspace)/workspace-pages.test.tsx`
- `web/src/components/shell/app-sidebar.tsx`
- `web/src/components/shell/project-context-bar.tsx`
- `web/src/components/shell/workspace-shell.test.tsx`
- `web/tests/e2e/foundation.spec.ts`

Main also changed dashboard copy files, but those are auto-mergeable and should be preserved because they remove backend-style wording such as raw FastAPI/postgres language.

## First-Principles Strategy

The product contract is not "keep whichever side is newer". The merge must preserve three user-visible outcomes:

- the latest government-style UI density reduction from `codex/frontend-2.0`;
- the current production/main workbench semantics for the B2B medical-audit topic where they better match the user-provided HTML/table workflow;
- tests and acceptance probes that assert user-facing text, not old implementation wording.

## File-Level Resolution Plan

| File | Recommended Resolution |
| --- | --- |
| `scripts/run-production-frontend-acceptance.mjs` | Hybrid. Keep the PR's low-density route expectations for `chat` and `agent-market`; update `/fund-compliance` expectations to the B2B topic entry copy if the page keeps `进入专题工作台`. |
| `agent-market/page.tsx` | Prefer PR branch. Keep `审计助手库`, compact cards, `DEFAULT_AGENT_LIMIT=8`, cleaned prompt sections, and avoid returning to AI/prompt-heavy card descriptions. Remove duplicate `打开` if conflict hunks introduce it. |
| `chat/page.tsx` | Prefer PR branch. Keep `审计问答`, `依据范围`, `当前助手`, and `查看核验方法` to reduce AI-flavored/internal wording. |
| `fund-compliance/page.tsx` | Hybrid leaning `main` for product skeleton. Keep the B2B专题总览 structure, four metrics, `进入专题工作台`, and `底稿输出`; retain PR/global government typography and avoid adding extra explanatory copy. |
| `fund-compliance/review/page.tsx` | Hybrid. Preserve the three-template plus self-created-form workbench behavior; keep the header compact and ensure tab styling matches the government UI token system. |
| `workspace-pages.test.tsx` | Hybrid. Update assertions to final visible user-facing copy, not either side's temporary wording. Keep dashboard copy assertions from `main` where they reflect deployed P2 copy polish. |
| `app-sidebar.tsx` | Prefer PR branch. Keep the simplified sidebar width and do not re-add a separate current-topic CTA that competes with navigation. |
| `project-context-bar.tsx` | Prefer PR density. Do not re-add the topic chip in the top bar; keep a clear `工作台` return label instead of broad status/chip clutter. |
| `workspace-shell.test.tsx` | Prefer PR branch. Tests should enforce simplified navigation, not the earlier all-module horizontal list. |
| `foundation.spec.ts` | Hybrid. Assert the final business path: B2B topic entry, separate review workbench, three form templates, compact assistant library, and non-AI chat wording. |

## Next Loop

Loop46 should perform local conflict resolution on `codex/frontend-2.0` only after confirming the intended strategy above. It should stop before ready-for-review, merge, deploy, production probe, provider call, Docker change, or write-path smoke.

Required Loop46 verification:

- `git diff --check`
- frontend typecheck
- frontend lint
- full frontend unit tests
- frontend build
- Foundation Playwright E2E
- local browser density checks for `/workspace`, `/fund-compliance`, `/fund-compliance/review`, `/chat`, and `/agent-market` on desktop and mobile

## Boundary

This loop is PR conflict triage and strategy only.

No business-code edit, conflict resolution, ready-for-review transition, merge, deployment, production probe, provider call, env write, object storage write, schema migration, Docker change, or write-path smoke is part of this loop.
