---
title: 知识库查询引擎 Kimi 评测会话压缩交接
doc_type: analysis
module: knowledge-query-engine
topic: kimi-evaluation-session-summary
status: draft
created: 2026-06-01
updated: 2026-06-01
owner: self
source: human+ai
---

# 知识库查询引擎 Kimi 评测会话压缩交接

## 当前目标

将 `data/` 下医保审核资料建设为本地知识库查询引擎，并形成可持续迭代的评测、索引、运维和产品文档体系。

## 已确认事实

- `data/` 是本地知识库原始资料目录，不进入 Git。
- `tmp/knowledge-query-indexes/real-data-kimi-20260531/` 是当前主索引目录。
- 当前主索引包含 `48985` 个 chunks、`48985` 条 embeddings、`48985` 条 BM25 文档。
- 当前 Kimi embedding 使用 OpenAI 兼容接口，模型参数传入 `kimi-for-coding`，返回向量维度为 `1024`。
- API key 只通过环境变量临时使用，未写入项目文件；由于 key 曾在会话中明文出现，后续应轮换。

## 已完成资产

- 已完成真实资料索引构建和 Kimi embedding 接入。
- 已完成自动评测报告，自动生成 case 的结果为 `100` 条 case 全部通过。
- 已建立固定人工评测集 `configs/evaluation/knowledge-query-human-evaluation-cases-v1.yaml`。
- 已完成 `52` 条固定人工评测，当前结果为 recall、citation、preview 全部 `100%`。
- 已修复医学目录编码检索问题：tokenizer 保留 `A00.0` 这类编码，BM25 对精确编码命中加权。
- 已建立答案级评测集 `configs/evaluation/knowledge-query-answer-evaluation-cases-v1.yaml`。
- 已完成 `8` 条答案级评测，当前结果为 pass、citation marker、answer term、citation term、refusal accuracy、unsupported claim free 全部 `100%`。
- 已修复答案级评测链路问题：空禁用词不再误判；fallback answer 按问题焦点词筛选引用，并优先聚焦 `A00.0`、`0000` 等领域编码。
- 已接入 OpenAI-compatible answer generation provider，并扩展 `evaluate-answers` 支持真实生成评测。
- 已确认 Kimi Code 当前不能通过 OpenAI-compatible chat completion 用于答案生成：6 个应回答 case 返回 `403 access_terminated_error`，真实生成评测 `pass_rate=25%`、`generation_success_rate=0%`、`fallback_rate=100%`。
- 已新增 `answer-provider-smoke` 预检命令，后续更换 chat model 或 key 时先跑单条引用预检，再跑完整答案评测。
- 已新增 Anthropic Messages API answer provider 适配器；当前环境中 `ANTHROPIC_API_KEY` 存在但预检返回 `401 authentication_error: invalid x-api-key`。
- 已将 `sql/knowledge-query-schema.sql` 的 pgvector 向量列对齐当前 Kimi 主索引：`vector(1024)`，并新增 Kimi cosine HNSW 索引草案。
- 已新增 pgvector 迁移计划草稿，明确当前 schema 不兼容 1536 维 embedding 混写。
- 已新增 `pgvector-import-plan` 导入前校验 CLI，并对当前 Kimi 主索引完成校验：`ready_for_import=true`，`chunks=48985`，`embeddings=48985`，`failed=0`，`pending=13`，无缺失 embedding、孤儿 embedding、重复 ID 或维度错误。
- 已新增 `pgvector-import` 受控写入 CLI，默认 dry-run；当前 Kimi 主索引 dry-run 通过：`ready_for_write=true`，`source_documents=486`，`document_chunks=48985`，`chunk_embeddings=48985`，`pending_files=13`，无缺失源文件或源元数据错误。
- 已确认执行 `pgvector-import --execute`，当前 PostgreSQL 已写入 Kimi 主索引：`source_documents=486`，`document_chunks=48985`，`chunk_embeddings=48985`，`failed_files=0`，`pending_files=13`。写入后校验显示 `orphan_embedding_count=0`、`missing_embedding_count=0`、`invalid_dimension_count=0`，HNSW 向量检索 smoke query 通过。
- 已新增 `evaluate-postgres-index` 和 PostgreSQL-backed `PostgresVectorIndex`。当前 pgvector self-query smoke 通过；PostgreSQL 数据源 BM25 固定 52 case 评测为 `recall@5=100%`、`citation_hit_rate=100%`、`preview_location_success_rate=100%`。由于当前 shell 未设置 `KIMI_API_KEY`，固定 52 case 的真实 pgvector+Kimi 查询向量评测尚未执行。

## 关键文件

- `configs/evaluation/knowledge-query-human-evaluation-cases-v1.yaml`
- `configs/evaluation/knowledge-query-answer-evaluation-cases-v1.yaml`
- `drafts/analysis/knowledge-query-human-evaluation-kimi-v1-draft-20260601.md`
- `drafts/analysis/knowledge-query-answer-evaluation-kimi-v1-draft-20260601.md`
- `drafts/analysis/knowledge-query-answer-generation-kimi-v1-draft-20260601.md`
- `drafts/analysis/knowledge-query-answer-provider-smoke-kimi-draft-20260601.md`
- `drafts/analysis/knowledge-query-answer-provider-smoke-anthropic-draft-20260601.md`
- `drafts/analysis/knowledge-query-pgvector-import-plan-kimi-draft-20260601.md`
- `drafts/analysis/knowledge-query-pgvector-import-dry-run-kimi-draft-20260601.md`
- `drafts/analysis/knowledge-query-pgvector-import-execute-kimi-draft-20260601.md`
- `drafts/analysis/knowledge-query-postgres-bm25-evaluation-v1-draft-20260601.md`
- `tmp/outputs/knowledge-query-human-evaluation-kimi-v1-20260601.json`
- `tmp/outputs/knowledge-query-answer-evaluation-kimi-v1-20260601.json`
- `tmp/outputs/knowledge-query-answer-generation-kimi-v1-20260601.json`
- `tmp/outputs/knowledge-query-answer-provider-smoke-kimi-20260601.json`
- `tmp/outputs/knowledge-query-answer-provider-smoke-anthropic-20260601.json`
- `tmp/outputs/knowledge-query-pgvector-import-plan-kimi-20260601.json`
- `tmp/outputs/knowledge-query-pgvector-import-dry-run-kimi-20260601.json`
- `tmp/outputs/knowledge-query-pgvector-import-execute-kimi-20260601.json`
- `tmp/outputs/knowledge-query-postgres-vector-self-query-smoke-20260601.json`
- `tmp/outputs/knowledge-query-postgres-bm25-evaluation-v1-20260601.json`
- `tmp/knowledge-query-indexes/real-data-kimi-20260531/summary.json`
- `sql/knowledge-query-schema.sql`
- `drafts/docs/architecture-knowledge-query-engine-pgvector-migration-plan-draft-20260601.md`
- `docs/architecture/architecture-knowledge-query-engine-stable.md`
- `docs/api/api-knowledge-query-engine-stable.md`
- `docs/workflows/workflow-knowledge-query-engine-operations-stable.md`

## 当前未完成工作

1. 引入真实审计专家人工标注问题，替换或补充当前 AI 从资料中抽取的 review case。
2. 将当前 `review` 状态 case 交给医保审核专家复核，确认后再转为 `stable`。
3. 更换可用 chat model 或有效 API key 后，先跑 `answer-provider-smoke`，再复跑真实生成评测。
4. 将 API 查询路径中的答案门控与当前答案级评测指标保持一致，避免评测链路和线上查询链路分叉。
5. 设置有效 `KIMI_API_KEY` 后，运行固定 52 case 的真实 pgvector+Kimi 查询向量评测。

## 最近校验结果

- `uv run ruff check .`：通过。
- `uv run mypy src`：通过。
- 待本轮代码和文档更新后重新执行完整校验。

## 下一步执行顺序

1. 提供一个有效 chat provider key，优先使用 OpenAI-compatible chat 或有效 Anthropic key。
2. 对新模型先跑 `answer-provider-smoke`，要求 `success=true` 后再跑完整真实生成评测。
3. 复跑 `knowledge-query-answer-generation-kimi-v1` 或新 provider 对应评测，要求 `generation_success_rate=100%` 后再接入 API 查询路径。
4. 扩充答案级评测集到专家问题和真实审计场景，保留当前 8 条作为 smoke gate。
5. 设置有效 `KIMI_API_KEY`，运行 `evaluate-postgres-index --embedding-provider openai --embedding-model kimi-for-coding --embedding-dimension 1024`，验证真实 pgvector+Kimi `recall@5=100%` 后再把 API 查询切到数据库。
