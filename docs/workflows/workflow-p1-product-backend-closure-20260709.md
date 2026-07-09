---
title: medical_audit P1 产品功能后端闭环方案
doc_type: workflow
module: product-backend-contract
status: active
created: 2026-07-09
updated: 2026-07-09
owner: codex
source: frontend-backend-contract-review
---

# medical_audit P1 产品功能后端闭环方案

## 总目标

围绕 `/medical-audit`、`/knowledge-base`、`/documents`、`/graph`、`/chat` 五个核心页面，先冻结任务流和数据合同，再逐批接入真实后端能力。

## 本轮已完成

- 将 PR #186 中仍有价值的 `/medical-audit` 合同迁移到当前 `docs/api/frontend-backend-page-contract.json`。
- 新增 `docs/api/product-page-backend-closure-contract-20260709.json`，把五个页面的目标、API、实体和验收方式统一起来。
- 本轮未改 UI，未访问 provider，未写生产数据。

## 执行批次

### P1-A：/medical-audit read-only project and findings wiring

- verification:
  - `frontend tests`
  - `backend API smoke`
  - `browser route acceptance`

### P1-B：knowledge-base and documents metric/citation/upload governance

- verification:
  - `contract tests`
  - `production read-only smoke`

### P1-C：graph readonly relation view and chat contextual payload

- verification:
  - `API tests`
  - `Playwright interaction smoke`
