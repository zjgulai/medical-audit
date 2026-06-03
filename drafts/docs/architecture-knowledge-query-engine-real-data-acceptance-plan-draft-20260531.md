---
title: 知识库真实资料索引验收实施计划草稿
doc_type: architecture
module: knowledge-query-engine
topic: real-data-index-acceptance
status: draft
created: 2026-05-31
updated: 2026-05-31
owner: self
source: human+ai
---

# Real Data Index Acceptance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 对本地 `data/医保审核前期资料/` 执行只读全量索引验收，输出可复现的成功率、失败队列、待处理队列和验收门禁报告。

**Architecture:** 在现有 `KnowledgeIndexPipeline` 之上增加独立验收报告层，不改变原始资料、不引入数据库副作用。CLI 负责触发全量重建 dry run，并将摘要、门禁指标、失败原因分布和样例写入 Markdown/JSON 报告。

**Tech Stack:** Python 3.12、uv、FastAPI 现有包结构、pytest、ruff、mypy。

---

### Task 1: 验收报告模型与格式化

**Files:**

- Create: `src/medical_audit_kb/acceptance/__init__.py`
- Create: `src/medical_audit_kb/acceptance/reports.py`
- Create: `tests/knowledge_query/test_acceptance_reports.py`

- [x] Step 1: 定义 `AcceptanceGateResult`、`AcceptanceReport` 和 `build_acceptance_report`。
- [x] Step 2: 指标包含 `index_success_rate`、`queue_explain_rate`、`no_silent_loss`。
- [x] Step 3: Markdown 输出包含摘要、门禁、失败原因分布、待处理原因分布、失败样例、待处理样例。
- [x] Step 4: 测试成功率计算、队列解释率和 Markdown 关键字段。

### Task 2: CLI 运行入口

**Files:**

- Create: `src/medical_audit_kb/cli.py`
- Modify: `pyproject.toml`
- Test: `tests/knowledge_query/test_cli.py`

- [x] Step 1: 增加 `medical-audit-kb acceptance-run` 命令。
- [x] Step 2: 参数包含 `--source-root`、`--output`、`--json-output`、`--package-version-key`。
- [x] Step 3: 命令只读扫描资料并运行 `KnowledgeIndexPipeline.run_full_rebuild`。
- [x] Step 4: 输出 Markdown，必要时同时输出 JSON。
- [x] Step 5: CLI 测试覆盖输出文件生成。

### Task 3: 真实资料验收运行

**Files:**

- Create: `drafts/analysis/knowledge-query-real-data-acceptance-report-draft-20260531.md`
- Optional create: `tmp/outputs/knowledge-query-real-data-acceptance-report-20260531.json`

- [x] Step 1: 对 `data/医保审核前期资料/` 执行 `acceptance-run`。
- [x] Step 2: 记录文件发现数量、可索引数量、成功索引数量、chunk 数、失败数量、待处理数量、忽略数量。
- [x] Step 3: 记录是否达到 `95%` 可索引成功率、队列解释率和无静默丢失门禁。
- [x] Step 4: 根据报告列出下一轮必须处理的资料问题。
