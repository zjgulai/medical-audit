---
title: medical_audit 根目录脏树分组决策
doc_type: workflow
module: repository-governance
status: active
created: 2026-07-09
updated: 2026-07-09
owner: codex
source: local-git-inventory
---

# medical_audit 根目录脏树分组决策

## 结论

- 根目录仍不是开发基线。
- 本轮只做 manifest，不改根目录文件、不归档、不删除。
- 总变更条目：`367`。

## 分组决策

### .kiro-plan

- count: `20`
- modified: `3`
- untracked: `17`
- decision: `keep-active-plan-state`
- next_action: review and promote only active plan entries after product milestone
- sample_paths:
  - `.kiro/plan/findings.md`
  - `.kiro/plan/progress.md`
  - `.kiro/plan/task_plan.md`
  - `.kiro/plan/frontend_ai_replica_api_integration_plan_20260704.md`
  - `.kiro/plan/frontend_ai_replica_loop1_fidelity_freeze_20260704.md`
  - `.kiro/plan/frontend_ai_replica_loop2_route_contract_matrix_20260704.md`
  - `.kiro/plan/frontend_ai_replica_loop3_adapters_20260704.md`
  - `.kiro/plan/frontend_ai_replica_loop4_5_runtime_wiring_20260704.md`
  - `.kiro/plan/frontend_ai_replica_loop6_page_microtuning_acceptance_20260704.md`
  - `.kiro/plan/frontend_ai_replica_loop7_delivery_closure_20260704.md`

### docs

- count: `4`
- modified: `0`
- untracked: `4`
- decision: `review-for-promote`
- next_action: compare with current docs/workflows and docs/api before staging
- sample_paths:
  - `docs/api/frontend-backend-page-contract.json`
  - `docs/api/knowledge-query-contract-v2.json`
  - `docs/api/knowledge-query-contract-v2.md`
  - `docs/superpowers/`

### drafts-analysis

- count: `298`
- modified: `1`
- untracked: `297`
- decision: `archive-or-supersede-by-topic`
- next_action: batch by date/topic; promote only latest summary docs
- sample_paths:
  - `drafts/analysis/branch-consolidation-and-frontend-backend-separation-todo-draft-20260702.md`
  - `drafts/analysis/frontend-adversarial-uiux-audit-refinement-plan-draft-20260704.md`
  - `drafts/analysis/frontend-ai-replica-api-integration-loop-engineering-plan-draft-20260704.md`
  - `drafts/analysis/frontend-ai-replica-loop-engineering-todo-draft-20260703.md`
  - `drafts/analysis/frontend-ai-replica-loop1-fidelity-freeze-report-draft-20260704.md`
  - `drafts/analysis/frontend-ai-replica-loop3-adapter-implementation-draft-20260704.md`
  - `drafts/analysis/frontend-ai-replica-loop4-5-runtime-wiring-staging-manifest-draft-20260704.md`
  - `drafts/analysis/frontend-ai-replica-loop7-atomic-delivery-plan-draft-20260704.md`
  - `drafts/analysis/frontend-ai-replica-next-stage-solution-and-execution-plan-draft-20260705.md`
  - `drafts/analysis/frontend-ai-replica-page-microtuning-execution-plan-draft-20260704.md`

### other

- count: `1`
- modified: `0`
- untracked: `1`
- decision: `manual-review`
- next_action: inspect before any action
- sample_paths:
  - `.playwright-cli/`

### output-generated

- count: `1`
- modified: `0`
- untracked: `1`
- decision: `discard-candidate`
- next_action: ignore or archive generated output, do not commit raw output
- sample_paths:
  - `output/`

### repo-config

- count: `3`
- modified: `2`
- untracked: `1`
- decision: `manual-review-high-risk`
- next_action: inspect exact diff; do not bundle with feature work
- sample_paths:
  - `pnpm-lock.yaml`
  - `pnpm-workspace.yaml`
  - `AGENTS.md`

### scripts

- count: `5`
- modified: `1`
- untracked: `4`
- decision: `defer-code-review`
- next_action: separate PR with tests if still relevant
- sample_paths:
  - `scripts/deploy-tencent-cloud-production.py`
  - `scripts/build-p6d-confirmed-decision-manifest.py`
  - `scripts/build-p6d-deferred-review-pack.py`
  - `scripts/build-p6d-human-review-decision-manifest.py`
  - `scripts/build-p6d-residual-decision-manifest.py`

### src-backend

- count: `9`
- modified: `9`
- untracked: `0`
- decision: `defer-code-review`
- next_action: separate backend/KB PR with pytest gates
- sample_paths:
  - `src/medical_audit_kb/api/document_permissions.py`
  - `src/medical_audit_kb/api/routes_pages.py`
  - `src/medical_audit_kb/domain/constants.py`
  - `src/medical_audit_kb/generation/citations.py`
  - `src/medical_audit_kb/indexing/embeddings.py`
  - `src/medical_audit_kb/indexing/incremental_plan.py`
  - `src/medical_audit_kb/indexing/index_activation.py`
  - `src/medical_audit_kb/indexing/persistent_index.py`
  - `src/medical_audit_kb/ingestion/inventory.py`

### tests

- count: `7`
- modified: `7`
- untracked: `0`
- decision: `pair-with-source-change`
- next_action: stage only with corresponding src/web changes
- sample_paths:
  - `tests/knowledge_query/test_api.py`
  - `tests/knowledge_query/test_citations.py`
  - `tests/knowledge_query/test_incremental_plan.py`
  - `tests/knowledge_query/test_index_activation.py`
  - `tests/knowledge_query/test_index_backends.py`
  - `tests/knowledge_query/test_persistent_index.py`
  - `tests/knowledge_query/test_scripts.py`

### web-frontend

- count: `19`
- modified: `15`
- untracked: `4`
- decision: `defer-ui-review`
- next_action: compare against current production UI before deciding
- sample_paths:
  - `web/src/app/(workspace)/agent-market/page.tsx`
  - `web/src/app/(workspace)/archive/page.tsx`
  - `web/src/app/(workspace)/documents/page.tsx`
  - `web/src/app/(workspace)/fund-compliance/page.tsx`
  - `web/src/app/(workspace)/fund-compliance/review/page.tsx`
  - `web/src/app/(workspace)/graph/page.tsx`
  - `web/src/app/(workspace)/guided-check/page.tsx`
  - `web/src/app/(workspace)/knowledge-base/page.tsx`
  - `web/src/app/(workspace)/remediation/page.tsx`
  - `web/src/app/(workspace)/rules/page.tsx`
