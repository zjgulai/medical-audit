---
title: 知识库查询引擎实施计划草稿
doc_type: architecture
module: knowledge-query-engine
topic: implementation-plan
status: draft
created: 2026-05-31
updated: 2026-05-31
owner: self
source: human+ai
---

# 知识库查询引擎实施计划草稿

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 基于 `data/` 下现有医保审核资料，构建首版 `检索 + 引用型问答 + 原文定位` 的知识库查询引擎。

**Architecture:** 后端采用 `FastAPI`，以 `PostgreSQL + pgvector` 存储文档、chunk、向量和引用链，以 `Tantivy/BM25` 提供关键词检索，以混合检索、rerank 和元数据过滤形成可追溯结果。首版前端提供最小查询页面和索引管理页面，重点支持审计科查询、信息科索引管理和来源追溯。

**Tech Stack:** Python 3.12、uv、FastAPI、Pydantic V2、SQLAlchemy 2.0、PostgreSQL、pgvector、Tantivy/BM25、pytest、ruff、mypy。开发期优先使用 `OpenAI API` 验证 embedding、rerank 和答案生成，模型调用层必须通过 provider 抽象预留国产和本地私有化模型替换接口。

---

## 1. 范围基线

首版只做以下能力：

- `医保目录`、`智能监管“两库”规则和知识点`、`风险负面清单`、`医保相关法律` 的优先索引
- 文档资料包版本化管理
- 可抽文本文件的抽取、结构化切分、chunk 入库
- 关键词检索、向量检索、rerank、元数据过滤
- 引用型答案生成，包含答案、分条依据、引用片段、原文定位、置信提示
- 系统内原文预览和命中高亮
- 数据源状态、索引版本、重建任务、失败队列、待处理队列、评测结果管理

首版不做以下能力：

- 不做患者数据问答
- 不直接输出合规判定结论
- 不做扫描件和图片 OCR
- 不把 `全量法律` 无差别全部索引
- 不做复杂多轮智能体编排

## 2. 目标文件结构

```text
project-root/
├─ pyproject.toml
├─ docker-compose.dev.yaml
├─ configs/
│  └─ knowledge-query-engine-dev.yaml
├─ sql/
│  └─ knowledge-query-schema.sql
├─ src/
│  └─ medical_audit_kb/
│     ├─ __init__.py
│     ├─ api/
│     │  ├─ app.py
│     │  ├─ routes_query.py
│     │  ├─ routes_index.py
│     │  └─ routes_preview.py
│     ├─ core/
│     │  ├─ config.py
│     │  ├─ errors.py
│     │  └─ logging.py
│     ├─ db/
│     │  ├─ engine.py
│     │  ├─ models.py
│     │  └─ repositories.py
│     ├─ domain/
│     │  ├─ schemas.py
│     │  └─ constants.py
│     ├─ ingestion/
│     │  ├─ inventory.py
│     │  ├─ extractors.py
│     │  ├─ chunkers.py
│     │  └─ pipeline.py
│     ├─ indexing/
│     │  ├─ embeddings.py
│     │  ├─ vector_index.py
│     │  ├─ bm25_index.py
│     │  └─ index_jobs.py
│     ├─ retrieval/
│     │  ├─ hybrid_search.py
│     │  ├─ rerank.py
│     │  └─ filters.py
│     ├─ generation/
│     │  ├─ answer_builder.py
│     │  └─ citations.py
│     ├─ preview/
│     │  └─ resolver.py
│     └─ evaluation/
│        ├─ datasets.py
│        └─ runner.py
└─ tests/
   └─ knowledge_query/
      ├─ test_inventory.py
      ├─ test_extractors.py
      ├─ test_chunkers.py
      ├─ test_hybrid_search.py
      └─ test_citations.py
```

## 3. 实施任务

### Task 1: 项目工程骨架

**Files:**

- Create: `pyproject.toml`
- Create: `docker-compose.dev.yaml`
- Create: `configs/knowledge-query-engine-dev.yaml`
- Create: `src/medical_audit_kb/__init__.py`
- Create: `src/medical_audit_kb/core/config.py`
- Create: `tests/knowledge_query/test_config.py`

- [x] Step 1: 初始化 Python 包和依赖声明。
- [x] Step 2: 配置 `ruff`、`mypy`、`pytest` 基线。
- [x] Step 3: 用 `Docker Compose` 定义本地 `PostgreSQL + pgvector` 服务。
- [x] Step 4: 定义配置项：数据根目录、索引目录、数据库连接、模型 provider、资料集合权重。
- [x] Step 5: 运行 `uv run pytest tests/knowledge_query/test_config.py -v`。
- [x] Step 6: 运行 `uv run ruff check .` 和 `uv run mypy src`。

### Task 2: 数据库与核心数据模型

**Files:**

- Create: `sql/knowledge-query-schema.sql`
- Create: `src/medical_audit_kb/db/engine.py`
- Create: `src/medical_audit_kb/db/models.py`
- Create: `src/medical_audit_kb/db/repositories.py`
- Create: `src/medical_audit_kb/domain/schemas.py`
- Create: `src/medical_audit_kb/domain/constants.py`

- [x] Step 1: 定义 `source_package_versions`，记录资料包版本和导入时间。
- [x] Step 2: 定义 `source_documents`，记录文件路径、集合、类型、hash、版本。
- [x] Step 3: 定义 `document_chunks`，记录 chunk 文本、定位信息、标题层级、条款号、页码、行号。
- [x] Step 4: 定义 `chunk_embeddings`，保存向量和 embedding provider 版本。
- [x] Step 5: 定义 `index_versions`、`index_jobs`、`failed_files`、`pending_files`、`query_logs`。
- [x] Step 6: 为来源集合、资料包版本、索引版本、文件 hash 建索引。
- [x] Step 7: 写 repository 单元测试，覆盖资料包版本创建、文档 upsert、chunk 写入、失败队列写入。

### Task 3: 数据源盘点与资料包版本化

**Files:**

- Create: `src/medical_audit_kb/ingestion/inventory.py`
- Create: `tests/knowledge_query/test_inventory.py`

- [x] Step 1: 扫描 `data/医保审核前期资料/` 下的文件。
- [x] Step 2: 将文件映射到四个首版集合：`medical-insurance-catalog`、`supervision-rules-knowledge`、`risk-negative-list`、`medical-insurance-laws`。
- [x] Step 3: 对全量法律只纳入医保相关文件，先用文件名和关键词做首版筛选。
- [x] Step 4: 为每个文件计算 `sha256`。
- [x] Step 5: 生成 `source_package_version` 和文件清单。
- [x] Step 6: 测试文件分类、hash 稳定性、重复文件识别、未知类型进入待处理队列。

### Task 4: 文本抽取器

**Files:**

- Create: `src/medical_audit_kb/ingestion/extractors.py`
- Create: `tests/knowledge_query/test_extractors.py`

- [x] Step 1: 支持 Markdown 和 txt 的直接文本抽取。
- [x] Step 2: 支持可抽文本 PDF 的文本抽取。
- [x] Step 3: 支持 xlsx 按 sheet 和行抽取为结构化记录。
- [x] Step 4: 扫描件 PDF、png、rar、zip 进入待处理队列。
- [x] Step 5: 失败文件写入失败队列，记录错误类型和摘要。
- [x] Step 6: 测试 Markdown、txt、xlsx、可抽文本 PDF、不可处理文件五类路径。

### Task 5: 结构化切分与引用定位

**Files:**

- Create: `src/medical_audit_kb/ingestion/chunkers.py`
- Create: `tests/knowledge_query/test_chunkers.py`

- [x] Step 1: 法规政策按章、节、条款切分。
- [x] Step 2: 普通文档按标题层级和段落切分。
- [x] Step 3: xlsx 按行或规则项切分。
- [x] Step 4: 每个 chunk 保留原文件路径、来源集合、标题层级、条款号、页码或行号。
- [x] Step 5: 对过长条款做窗口切分，并保留父条款定位。
- [x] Step 6: 测试条款识别、标题层级、表格行定位和长文本切分。

### Task 6: 索引流水线

**Files:**

- Create: `src/medical_audit_kb/ingestion/pipeline.py`
- Create: `src/medical_audit_kb/indexing/index_jobs.py`
- Create: `tests/knowledge_query/test_index_jobs.py`

- [x] Step 1: 实现增量索引，按文件 hash 判断新增、修改、删除。
- [x] Step 2: 实现手动全量重建，生成新的 `index_version`。
- [x] Step 3: 每次索引输出文件数、chunk 数、失败文件数、待处理文件数。
- [x] Step 4: 支持失败文件修复后的单文件重试。
- [x] Step 5: 保存重建前后对比摘要。
- [x] Step 6: 测试增量索引、全量重建、单文件重试和失败队列统计。

### Task 7: 向量与关键词索引

**Files:**

- Create: `src/medical_audit_kb/indexing/embeddings.py`
- Create: `src/medical_audit_kb/indexing/vector_index.py`
- Create: `src/medical_audit_kb/indexing/bm25_index.py`
- Create: `tests/knowledge_query/test_index_backends.py`

- [x] Step 1: 定义 embedding provider 接口，开发期接云端 API，测试使用 deterministic fake provider。
- [x] Step 2: 将 chunk embedding 写入 pgvector。
- [x] Step 3: 用 Tantivy/BM25 建本地关键词索引。
- [x] Step 4: 记录 embedding provider、模型名、维度、版本。
- [x] Step 5: 测试 fake embedding 可稳定召回，BM25 可按政策号、条款号、术语召回。

### Task 8: 混合检索、rerank 与元数据过滤

**Files:**

- Create: `src/medical_audit_kb/retrieval/hybrid_search.py`
- Create: `src/medical_audit_kb/retrieval/rerank.py`
- Create: `src/medical_audit_kb/retrieval/filters.py`
- Create: `tests/knowledge_query/test_hybrid_search.py`

- [x] Step 1: 合并 BM25 和向量召回结果。
- [x] Step 2: 支持来源集合、年份、地区、资料类型、业务主题过滤。
- [x] Step 3: 按来源集合做业务加权排序。
- [x] Step 4: 定义 rerank provider 接口，测试使用 fake reranker。
- [x] Step 5: 返回结果必须包含 chunk、定位信息、索引版本、资料包版本。
- [x] Step 6: 测试精确术语、自然语言问题、来源过滤和跨集合召回。

### Task 9: 引用型答案生成

**Files:**

- Create: `src/medical_audit_kb/generation/answer_builder.py`
- Create: `src/medical_audit_kb/generation/citations.py`
- Create: `tests/knowledge_query/test_citations.py`

- [x] Step 1: 定义答案结构：答案正文、分条依据、引用片段、原文定位、置信提示。
- [x] Step 2: 答案按法规依据、规则依据、目录依据、风险案例依据分组。
- [x] Step 3: 禁止无引用结论进入最终答案。
- [x] Step 4: 支持模型生成失败时返回检索结果和引用列表。
- [x] Step 5: 测试答案必须含引用、引用必须能回到 chunk 定位、跨集合答案必须分组。

### Task 10: 原文预览与高亮

**Files:**

- Create: `src/medical_audit_kb/preview/resolver.py`
- Create: `tests/knowledge_query/test_preview_resolver.py`

- [x] Step 1: 根据 chunk 定位解析原文片段。
- [x] Step 2: Markdown/txt 支持条款或行号定位。
- [x] Step 3: PDF 支持页码定位和引用文本高亮数据。
- [x] Step 4: xlsx 支持 sheet 和行号定位。
- [x] Step 5: 保留本地源文件路径。
- [x] Step 6: 测试不同文件类型的定位结果。

### Task 11: 后端 API

**Files:**

- Create: `src/medical_audit_kb/api/app.py`
- Create: `src/medical_audit_kb/api/routes_query.py`
- Create: `src/medical_audit_kb/api/routes_index.py`
- Create: `src/medical_audit_kb/api/routes_preview.py`
- Create: `tests/knowledge_query/test_api.py`

- [x] Step 1: 实现 `GET /health`。
- [x] Step 2: 实现 `POST /query`，返回引用型答案。
- [x] Step 3: 实现 `POST /index/incremental`。
- [x] Step 4: 实现 `POST /index/rebuild`。
- [x] Step 5: 实现 `GET /index/versions`、`GET /index/jobs`、`GET /index/failures`、`GET /index/pending`。
- [x] Step 6: 实现 `GET /preview/{chunk_id}`。
- [x] Step 7: API 测试覆盖权限占位、查询日志、索引任务状态和预览定位。

### Task 12: 最小查询页面与索引管理页面

**Files:**

- Create: `src/medical_audit_kb/api/templates/query.html`
- Create: `src/medical_audit_kb/api/templates/index_admin.html`
- Create: `src/medical_audit_kb/api/static/app.css`
- Create: `tests/knowledge_query/test_pages.py`

- [x] Step 1: 查询页支持自然语言输入、来源过滤、答案展示、引用分组、原文预览入口。
- [x] Step 2: 索引管理页展示数据源状态、索引版本、重建任务、失败队列、待处理队列、评测结果。
- [x] Step 3: 查询、预览、导出、索引管理操作写入日志。
- [x] Step 4: 使用 `FastAPI` 服务端模板实现首版页面，后续产品化 UI 再迁移到 `React/Next.js`。
- [x] Step 5: 页面测试覆盖基本渲染和关键数据字段。

### Task 13: 检索评测集与评测报告

**Files:**

- Create: `src/medical_audit_kb/evaluation/datasets.py`
- Create: `src/medical_audit_kb/evaluation/runner.py`
- Create: `drafts/analysis/knowledge-query-evaluation-seed-draft-20260531.md`
- Create: `tests/knowledge_query/test_evaluation.py`

- [x] Step 1: 定义评测集格式，包含问题、期望来源、期望文件、期望条款或规则项、答案接受标准。
- [x] Step 2: 从 PRD 场景构造第一批问题。
- [x] Step 3: 从资料标题和条款自动生成候选问题。
- [x] Step 4: 预留审计员真实问题导入字段。
- [x] Step 5: 输出 recall@k、引用命中率、原文定位成功率。
- [x] Step 6: 测试评测集加载和评测指标计算。

### Task 14: 验收与运行手册

**Files:**

- Create: `docs/workflows/workflow-knowledge-query-engine-operations-stable.md`
- Create: `docs/api/api-knowledge-query-engine-stable.md`
- Create: `docs/architecture/architecture-knowledge-query-engine-stable.md`

- [x] Step 1: 方案验证通过后，将草稿沉淀为正式架构文档。
- [x] Step 2: 编写 API 文档，覆盖查询、索引、预览和管理接口。
- [x] Step 3: 编写运维流程，覆盖资料包导入、增量索引、全量重建、失败文件重试、评测报告查看。
- [x] Step 4: 明确首版验收指标：可索引文件成功率、失败队列可解释率、引用定位成功率、评测集召回指标。

## 4. 开发顺序

1. 工程骨架与数据库模型
2. 文件盘点、版本化和抽取
3. 结构化切分与引用定位
4. 索引流水线和失败队列
5. BM25 与向量索引
6. 混合检索与 rerank
7. 引用答案生成
8. 原文预览
9. API 与最小页面
10. 评测集与运维文档

## 5. 首版验收指标

- 可处理文件进入索引成功率不低于 `95%`
- 不可处理文件必须进入失败队列或待处理队列，不能静默丢失
- 查询结果必须返回索引版本、资料包版本和引用定位
- 评测集 top5 召回率达到内部基线后再进入问答评估
- 引用答案不得出现无来源结论
- 原文预览必须能定位到 Markdown/txt 条款、PDF 页码、xlsx 行号

## 6. 风险与控制

- `PDF 和 xlsx 抽取质量不稳定`：先把失败文件透明化，OCR 放 V1.1。
- `全量法律噪声过大`：首版只筛医保相关法律进入索引。
- `云端 API 与交付私有化不一致`：模型调用层从第一天抽象 provider。
- `答案幻觉`：禁止无引用答案，生成失败时返回检索结果。
- `索引不可复现`：资料包版本、索引版本、chunk、答案引用必须全链路关联。

## 7. 下一步确认

在进入代码实现前，需要先完成：

- 全量扫描 `data/` 资料，生成资料质量审计报告。
- 根据报告确认首版可索引范围、待处理队列和失败队列初始策略。
