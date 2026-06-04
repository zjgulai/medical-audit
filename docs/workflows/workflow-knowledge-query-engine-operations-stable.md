---
title: 知识库查询引擎运行手册
doc_type: workflow
module: knowledge-query-engine
topic: knowledge-query-engine-operations
status: stable
created: 2026-05-31
updated: 2026-06-04
owner: self
source: human+ai
---

# 知识库查询引擎运行手册

## 1. 本地启动

安装依赖：

```bash
uv sync
```

启动本地数据库：

```bash
docker compose -f docker-compose.dev.yaml up -d
```

推荐启动对话审证台：

```bash
export KIMI_API_KEY='实际 key'
scripts/serve-chat-workbench.sh
```

该脚本会执行：

- 启动 `uvicorn` 到 `http://127.0.0.1:8010`。
- 等待 `/health` 可用。
- 使用 Kimi 主索引参数加载 PostgreSQL 检索后端。
- 校验 `details.matching_embedding_count > 0`。
- 保持 API 进程在前台运行，按 `Ctrl-C` 停止。

约束：

- 不要把 key 写入仓库文件。
- `KIMI_API_KEY` 必须在启动脚本的同一个 shell 中存在。
- 如果 `8010` 已经有 API 进程但检索后端未加载，先停止旧进程再运行脚本。环境变量无法注入到已经运行的 API 进程。

仅启动 API、不加载检索后端时使用：

```bash
uv run uvicorn medical_audit_kb.api.app:create_app --factory --reload
```

访问入口：

- 对话审证页：`http://127.0.0.1:8010/pages/chat`
- 查询页：`http://127.0.0.1:8010/pages/query`
- 复核任务台：`http://127.0.0.1:8010/pages/review-tasks`
- 索引管理页：`http://127.0.0.1:8010/pages/index-admin`
- 健康检查：`http://127.0.0.1:8010/health`

## 2. 资料包导入

首版约束：

- `data/` 作为原始资料目录，只读使用。
- 新资料以资料包方式进入 `data/` 对应来源目录。
- 不直接覆盖旧资料包；需要保留可追溯版本。
- 每次索引时传入 `package_version_key`。

推荐资料来源目录：

- `医保目录`
- `三大目录知识库`
- `智能监管“两库”规则和知识点`
- `风险负面清单`
- `全量法律`

## 3. 全量重建

触发：

```bash
curl -X POST http://127.0.0.1:8000/index/rebuild \
  -H "Content-Type: application/json" \
  -H "X-Role: it-admin" \
  -d '{"package_version_key":"source-package-20260531"}'
```

全量重建用于：

- 首次初始化索引。
- 资料包发生大范围变化。
- 索引策略、chunk 策略或模型 provider 发生变化。

检查项：

- `summary.index_candidate_file_count`
- `summary.indexed_file_count`
- `summary.failed_file_count`
- `summary.pending_file_count`
- `summary.chunk_count`

## 4. 增量索引

触发：

```bash
curl -X POST http://127.0.0.1:8000/index/incremental \
  -H "Content-Type: application/json" \
  -H "X-Role: it-admin" \
  -d '{"package_version_key":"source-package-20260601"}'
```

前提：

- 已存在一次全量重建快照。
- 仅新增、修改、删除少量资料。

如果返回 `409`，先执行全量重建。

## 5. 失败文件重试

查看失败队列：

```bash
curl http://127.0.0.1:8000/index/failures
```

修复源文件或抽取策略后，重试单文件：

```bash
curl -X POST http://127.0.0.1:8000/index/retry-file \
  -H "Content-Type: application/json" \
  -H "X-Role: it-admin" \
  -d '{"package_version_key":"source-package-20260601","relative_path":"全量法律/example.md"}'
```

失败文件不进入可查询索引。失败原因必须可解释，不能静默丢失。

## 6. 待处理队列

查看待处理队列：

```bash
curl http://127.0.0.1:8000/index/pending
```

首版进入待处理队列的典型情况：

- 扫描件 PDF。
- 图片。
- 压缩包。
- 需要 OCR 或人工整理的低质量文本。

待处理队列不阻塞可索引文件上线，但必须纳入验收统计。

## 7. 查询与预览

浏览器对话入口：

```text
http://127.0.0.1:8000/pages/chat
```

查询：

```bash
curl -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -H "X-Role: auditor" \
  -H "X-User-Id: auditor-1" \
  -d '{"question":"超量开药的审核依据是什么？","top_k":5}'
```

预览：

```bash
curl http://127.0.0.1:8000/preview/{chunk_id}
```

预览必须在查询之后执行，因为运行态需要先记录该 `chunk_id` 的 locator。

单轮对话底稿导出：

```bash
curl 'http://127.0.0.1:8000/pages/chat/export?question=超量开药的审核依据是什么&format=markdown'
curl 'http://127.0.0.1:8000/pages/chat/export?question=超量开药的审核依据是什么&format=json'
```

从对话结果创建数据库复核任务：

```bash
curl -i -X POST http://127.0.0.1:8000/pages/review-tasks/create \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "question=超量开药的审核依据是什么"
```

更新复核状态：

```bash
curl -i -X POST http://127.0.0.1:8000/pages/review-tasks/review-task-0001/status \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "status=needs-evidence" \
  --data-urlencode "reviewer_note=引用已覆盖规则依据，仍需补 HIS 原始凭证。" \
  --data-urlencode "conclusion=暂不进入正式报告。"
```

导出任务级复核记录：

```bash
curl 'http://127.0.0.1:8000/review-tasks/review-task-0001/export?format=markdown'
curl 'http://127.0.0.1:8000/review-tasks/review-task-0001/export?format=json'
```

当前复核任务台默认写入 PostgreSQL，用于验证“对话回答 -> 底稿快照 -> 人工复核 -> 任务导出”闭环。服务重启后任务保留；多实例强一致编号、权限、负责人审核、附件、正式报告门禁和整改闭环仍未完成。

## 8. 评测报告查看

首版评测使用 `evaluation` 模块计算：

- `recall@k`
- `citation_hit_rate`
- `preview_location_success_rate`

评测集来源：

- PRD 场景种子问题。
- 资料标题、条款、规则项自动生成候选问题。
- 审计员真实问题导入字段。

评测草稿位置：

- `drafts/analysis/knowledge-query-evaluation-seed-draft-20260531.md`
- `drafts/analysis/knowledge-query-real-data-retrieval-evaluation-draft-20260531.md`

草稿证据登记表：

- `docs/knowledge/knowledge-query-evidence-register-stable.md`

使用规则：

- 草稿报告只作为历史运行证据，不作为当前状态最高优先级来源。
- 发布、回滚、上线验收前必须重新运行当前门禁，不能直接复用历史草稿指标。
- 新增评测、迁移或 provider 预检草稿后，必须更新证据登记表再进入提交。

## 9. 本地持久化索引

构建默认 fake embedding 索引：

```bash
uv run medical-audit-kb index-build \
  --source-root 'data/医保审核前期资料' \
  --index-root tmp/knowledge-query-indexes/real-data-20260531 \
  --json-output tmp/outputs/knowledge-query-real-data-persistent-index-summary-20260531.json \
  --package-version-key source-package-real-data-20260531
```

基于医保审核主题评测：

```bash
uv run medical-audit-kb evaluate-index \
  --source-root 'data/医保审核前期资料' \
  --index-root tmp/knowledge-query-indexes/real-data-20260531 \
  --output drafts/analysis/knowledge-query-real-data-retrieval-evaluation-draft-20260531.md \
  --json-output tmp/outputs/knowledge-query-real-data-retrieval-evaluation-20260531.json \
  --max-cases 25 \
  --top-k 5 \
  --query-terms 医保 医疗保障 医保基金 超量 规则 处方 药品 基金
```

当前本地 fake embedding 主题评测基线：

- `case_count`: `25`
- `recall@5`: `100%`
- `citation_hit_rate`: `100%`
- `preview_location_success_rate`: `100%`

该基线只证明工程闭环有效，不代表真实模型质量。

## 10. 第三方 Embedding 接入

第三方 provider 必须兼容 OpenAI `/v1/embeddings` 协议。推荐使用独立环境变量，不把 key 写入仓库。

smoke test 前置变量：

```bash
export KIMI_API_KEY='实际 key'
export KIMI_EMBEDDING_BASE_URL='https://api.kimi.com/coding/v1'
export KIMI_EMBEDDING_MODEL='kimi-for-coding'
export KIMI_EMBEDDING_DIMENSION='1024'
```

小批量 smoke 构建命令格式：

```bash
uv run medical-audit-kb index-build \
  --source-root 'data/医保审核前期资料' \
  --index-root tmp/knowledge-query-indexes/real-data-kimi-smoke-20260531 \
  --json-output tmp/outputs/knowledge-query-real-data-kimi-smoke-index-summary-20260531.json \
  --package-version-key source-package-real-data-kimi-smoke-20260531 \
  --embedding-provider openai \
  --embedding-model "$KIMI_EMBEDDING_MODEL" \
  --embedding-dimension "$KIMI_EMBEDDING_DIMENSION" \
  --api-key-env KIMI_API_KEY \
  --embedding-base-url "$KIMI_EMBEDDING_BASE_URL" \
  --embedding-batch-size 16 \
  --max-chunks 100
```

当前 Kimi smoke 结果：

- `persistent_chunk_count`: `100`
- `embedding_count`: `100`
- `bm25_document_count`: `100`
- `embedding_dimension`: `1024`
- 小批量评测：`case_count=10`，`recall@5=90%`，`citation_hit_rate=90%`，`preview_location_success_rate=100%`

当前 Kimi 全量构建结果：

- `index_root`: `tmp/knowledge-query-indexes/real-data-kimi-20260531`
- `persistent_chunk_count`: `48985`
- `embedding_count`: `48985`
- `bm25_document_count`: `48985`
- `embedding_dimension`: `1024`
- `failed_file_count`: `0`
- `pending_file_count`: `13`
- artifact size：约 `917M`

当前 Kimi 全量索引评测结果：

- `case_count`: `100`
- `recall@5`: `100%`
- `citation_hit_rate`: `100%`
- `preview_location_success_rate`: `100%`

`InMemoryVectorIndex` 已启用 NumPy 加速路径，无过滤条件的向量检索使用归一化矩阵和向量化 dot product。后续执行更大规模评测时，优先复用该路径；生产持久化仍建议迁移到 pgvector。

固定人工评测集 V1：

```bash
KIMI_API_KEY='实际 key' uv run medical-audit-kb evaluate-index \
  --source-root 'data/医保审核前期资料' \
  --index-root tmp/knowledge-query-indexes/real-data-kimi-20260531 \
  --cases-file configs/evaluation/knowledge-query-human-evaluation-cases-v1.yaml \
  --output drafts/analysis/knowledge-query-human-evaluation-kimi-v1-draft-20260601.md \
  --json-output tmp/outputs/knowledge-query-human-evaluation-kimi-v1-20260601.json \
  --max-cases 52 \
  --top-k 5 \
  --embedding-provider openai \
  --embedding-model kimi-for-coding \
  --embedding-dimension 1024 \
  --api-key-env KIMI_API_KEY \
  --embedding-base-url https://api.kimi.com/coding/v1 \
  --embedding-batch-size 16
```

固定集 V1 结果：

- `case_count`: `52`
- `recall@5`: `100%`
- `citation_hit_rate`: `100%`
- `preview_location_success_rate`: `100%`

注意：固定集运行已暴露三类问题。`A00.0` ICD 编码未命中时，修复方式不是放宽评测集，而是增强编码 tokenization 和 BM25 精确编码命中权重；`医疗服务项目重复收费` 首次未命中时，根因是 expected source 过窄，已调整到实际命中的第七批 Excel 知识点明细；`诊断编码与手术操作编码不符` 首次未命中时，根因是 expected rule 使用了规范化转述，已调整为源文真实表述。

答案级评测集 V1：

```bash
KIMI_API_KEY='实际 key' uv run medical-audit-kb evaluate-answers \
  --index-root tmp/knowledge-query-indexes/real-data-kimi-20260531 \
  --cases-file configs/evaluation/knowledge-query-answer-evaluation-cases-v1.yaml \
  --output drafts/analysis/knowledge-query-answer-evaluation-kimi-v1-draft-20260601.md \
  --json-output tmp/outputs/knowledge-query-answer-evaluation-kimi-v1-20260601.json \
  --max-cases 8 \
  --top-k 5 \
  --embedding-provider openai \
  --embedding-model kimi-for-coding \
  --embedding-dimension 1024 \
  --api-key-env KIMI_API_KEY \
  --embedding-base-url https://api.kimi.com/coding/v1 \
  --embedding-batch-size 16
```

答案级 V1 结果：

- `case_count`: `8`
- `pass_rate`: `100%`
- `citation_marker_rate`: `100%`
- `answer_term_coverage_rate`: `100%`
- `citation_term_coverage_rate`: `100%`
- `refusal_accuracy_rate`: `100%`
- `unsupported_claim_free_rate`: `100%`

注意：答案级评测已暴露两类问题。空 `forbidden_answer_terms` 不能按 `all([])` 判定为命中；fallback answer 不能机械输出全部 Top-K 引用，必须按问题焦点词筛选引用，并优先聚焦 `A00.0`、`0000` 等领域编码。

答案生成 provider 预检命令：

```bash
KIMI_API_KEY='实际 key' uv run medical-audit-kb answer-provider-smoke \
  --answer-provider openai \
  --answer-model kimi-for-coding \
  --answer-api-key-env KIMI_API_KEY \
  --answer-base-url https://api.kimi.com/coding/v1 \
  --answer-max-output-tokens 300 \
  --answer-temperature 0 \
  --output drafts/analysis/knowledge-query-answer-provider-smoke-kimi-draft-20260601.md \
  --json-output tmp/outputs/knowledge-query-answer-provider-smoke-kimi-20260601.json
```

Kimi Code provider 预检结果：

- `success`: `false`
- `citation_marker_present`: `false`
- `required_term_present`: `false`
- `error`: `403 access_terminated_error`

Anthropic provider 预检命令：

```bash
uv run medical-audit-kb answer-provider-smoke \
  --answer-provider anthropic \
  --answer-model claude-sonnet-4-5-20250929 \
  --answer-api-key-env ANTHROPIC_API_KEY \
  --answer-max-output-tokens 300 \
  --answer-temperature 0 \
  --output drafts/analysis/knowledge-query-answer-provider-smoke-anthropic-draft-20260601.md \
  --json-output tmp/outputs/knowledge-query-answer-provider-smoke-anthropic-20260601.json
```

Anthropic provider 预检结果：

- `success`: `false`
- `citation_marker_present`: `false`
- `required_term_present`: `false`
- `error`: `401 authentication_error: invalid x-api-key`

结论：以后更换 chat model 或 key 时，必须先跑 `answer-provider-smoke`。只有预检通过，才继续运行完整 `evaluate-answers` 真实生成评测。当前没有已验证可用的真实 chat answer provider。

真实生成评测命令格式：

```bash
KIMI_API_KEY='实际 key' uv run medical-audit-kb evaluate-answers \
  --index-root tmp/knowledge-query-indexes/real-data-kimi-20260531 \
  --cases-file configs/evaluation/knowledge-query-answer-evaluation-cases-v1.yaml \
  --output drafts/analysis/knowledge-query-answer-generation-kimi-v1-draft-20260601.md \
  --json-output tmp/outputs/knowledge-query-answer-generation-kimi-v1-20260601.json \
  --max-cases 8 \
  --top-k 5 \
  --embedding-provider openai \
  --embedding-model kimi-for-coding \
  --embedding-dimension 1024 \
  --api-key-env KIMI_API_KEY \
  --embedding-base-url https://api.kimi.com/coding/v1 \
  --embedding-batch-size 16 \
  --answer-provider openai \
  --answer-model kimi-for-coding \
  --answer-api-key-env KIMI_API_KEY \
  --answer-base-url https://api.kimi.com/coding/v1 \
  --answer-max-output-tokens 600 \
  --answer-temperature 0
```

真实生成评测结果：

- `case_count`: `8`
- `pass_rate`: `25%`
- `generation_success_rate`: `0%`
- `fallback_rate`: `100%`
- `refusal_accuracy_rate`: `100%`

结论：Kimi Code 当前不能作为 OpenAI-compatible chat answer provider 通过本项目评测。6 个应回答 case 均返回 `403 access_terminated_error`，提示该模型仅可用于 Kimi CLI、Claude Code、Roo Code、Kilo Code 等 Coding Agents。未显式传入 `--allow-answer-fallback` 时，provider 失败必须计入 `generation_provider_failed`。

全量构建命令格式：

```bash
uv run medical-audit-kb index-build \
  --source-root 'data/医保审核前期资料' \
  --index-root tmp/knowledge-query-indexes/real-data-kimi-20260531 \
  --json-output tmp/outputs/knowledge-query-real-data-kimi-index-summary-20260531.json \
  --package-version-key source-package-real-data-kimi-20260531 \
  --embedding-provider openai \
  --embedding-model "$KIMI_EMBEDDING_MODEL" \
  --embedding-dimension "$KIMI_EMBEDDING_DIMENSION" \
  --api-key-env KIMI_API_KEY \
  --embedding-base-url "$KIMI_EMBEDDING_BASE_URL" \
  --embedding-batch-size 64 \
  --resume
```

说明：全量外部 embedding 必须使用 `--resume`。如果中途遇到限流、网络错误或服务端错误，修复后重复执行同一命令即可复用已写入的 `embeddings.jsonl`，只继续缺失部分。

全量评测必须使用同一个 embedding provider 生成查询向量：

```bash
uv run medical-audit-kb evaluate-index \
  --source-root 'data/医保审核前期资料' \
  --index-root tmp/knowledge-query-indexes/real-data-kimi-20260531 \
  --output drafts/analysis/knowledge-query-real-data-kimi-evaluation-draft-20260531.md \
  --json-output tmp/outputs/knowledge-query-real-data-kimi-evaluation-20260531.json \
  --max-cases 50 \
  --top-k 5 \
  --query-terms 医保 医疗保障 医保基金 超量 规则 处方 药品 基金 \
  --embedding-provider openai \
  --embedding-model "$KIMI_EMBEDDING_MODEL" \
  --embedding-dimension "$KIMI_EMBEDDING_DIMENSION" \
  --api-key-env KIMI_API_KEY \
  --embedding-base-url "$KIMI_EMBEDDING_BASE_URL" \
  --embedding-batch-size 16
```

执行原则：

- 未通过 smoke test 不跑全量。
- 未确认成本和限流不跑全量。
- key 只放环境变量，不落盘。
- 失败后先读错误码，不重试制造额外成本。

## 11. PostgreSQL + pgvector 迁移预备

当前生产迁移目标：

- 将 `tmp/knowledge-query-indexes/real-data-kimi-20260531` 导入 PostgreSQL + pgvector。
- 保留当前 Kimi `1024` 维 embedding，不重新生成全量 embedding。
- 用数据库向量检索替代 API 运行时加载 917M 本地 artifact。

初始化 schema：

```bash
docker compose -f docker-compose.dev.yaml up -d
psql "postgresql://medical_audit_kb:medical_audit_kb_dev@localhost:5433/medical_audit_kb" \
  -f sql/knowledge-query-schema.sql
```

当前 schema 约束：

- `chunk_embeddings.embedding` 为 `vector(1024)`。
- `chunk_embeddings.dimension` 必须等于 `1024`。
- Kimi 专用 HNSW cosine 索引为 `idx_chunk_embeddings_kimi_cosine_hnsw`。
- `document_chunks.metadata`、`document_chunks.locator`、`query_logs.filters` 使用 GIN 索引支撑过滤和定位。

一致性校验目标：

- `document_chunks`: `48985`
- `chunk_embeddings`: `48985`
- `failed_files`: `0`
- `pending_files`: `13`
- 所有 `chunk_embeddings.dimension` 均为 `1024`

写入数据库前，先执行 JSONL artifact 导入前校验：

```bash
uv run medical-audit-kb pgvector-import-plan \
  --index-root tmp/knowledge-query-indexes/real-data-kimi-20260531 \
  --schema-dimension 1024 \
  --output drafts/analysis/knowledge-query-pgvector-import-plan-kimi-draft-20260601.md \
  --json-output tmp/outputs/knowledge-query-pgvector-import-plan-kimi-20260601.json
```

当前导入前校验结果：

- `ready_for_import`: `true`
- `chunks.jsonl`: `48985`
- `embeddings.jsonl`: `48985`
- `failed_files.jsonl`: `0`
- `pending_files.jsonl`: `13`
- `duplicate_chunk_id_count`: `0`
- `duplicate_embedding_chunk_id_count`: `0`
- `missing_embedding_count`: `0`
- `orphan_embedding_count`: `0`
- `invalid_embedding_metadata_count`: `0`
- `invalid_embedding_dimension_count`: `0`

执行数据库写入前，先执行受控导入 dry-run：

```bash
uv run medical-audit-kb pgvector-import \
  --index-root tmp/knowledge-query-indexes/real-data-kimi-20260531 \
  --source-root 'data/医保审核前期资料' \
  --schema-dimension 1024 \
  --output drafts/analysis/knowledge-query-pgvector-import-dry-run-kimi-draft-20260601.md \
  --json-output tmp/outputs/knowledge-query-pgvector-import-dry-run-kimi-20260601.json
```

当前 dry-run 结果：

- `ready_for_write`: `true`
- `source_document_count`: `486`
- `document_chunk_count`: `48985`
- `chunk_embedding_count`: `48985`
- `failed_file_count`: `0`
- `pending_file_count`: `13`
- `source_file_missing_count`: `0`
- `invalid_source_metadata_count`: `0`

确认数据库连接、schema 和备份后，才允许添加 `--execute`。当前默认写入 `candidate` 版本，不直接切换线上 active 检索版本：

```bash
MEDICAL_AUDIT_KB_DATABASE_URL='postgresql://medical_audit_kb:medical_audit_kb_dev@localhost:5433/medical_audit_kb' \
uv run medical-audit-kb pgvector-import \
  --index-root tmp/knowledge-query-indexes/real-data-kimi-20260531 \
  --source-root 'data/医保审核前期资料' \
  --schema-dimension 1024 \
  --output drafts/analysis/knowledge-query-pgvector-import-execute-kimi-draft-20260601.md \
  --json-output tmp/outputs/knowledge-query-pgvector-import-execute-kimi-20260601.json \
  --index-version-status candidate \
  --execute
```

历史 Kimi 主索引执行结果：

- `executed`: `true`
- `success`: `true`
- `source_documents`: `486`
- `document_chunks`: `48985`
- `chunk_embeddings`: `48985`
- `failed_files`: `0`
- `pending_files`: `13`
- `orphan_embedding_count`: `0`
- `missing_embedding_count`: `0`
- `invalid_dimension_count`: `0`
- `database_size`: `764 MB`
- `chunk_embeddings_total_size`: `654 MB`
- `hnsw_index_size`: `382 MB`
- `index_version_status`: 历史导入发生在 candidate/activate 流程落地之前，当前数据库中该版本已是 `active`

导入前快照：

- `archive/snapshots/postgres-pre-pgvector-import-20260601160814.sql`
- `archive/snapshots/postgres-schema-before-pgvector-import-20260601160829.sql`

迁移计划草稿：

- `drafts/docs/architecture-knowledge-query-engine-pgvector-migration-plan-draft-20260601.md`

注意：后续新资料包导入必须先写 `candidate`。该 schema 不支持混写 `1536` 维或其他维度 embedding。切换 embedding model 时，先新增 migration 或新向量表，再重新评测。

## 12. 增量计划、版本激活与回滚

新增源文件或准备发布新索引前，先生成只读增量计划：

```bash
MEDICAL_AUDIT_KB_DATABASE_URL='postgresql://medical_audit_kb:medical_audit_kb_dev@localhost:5433/medical_audit_kb' \
uv run medical-audit-kb index-incremental-plan \
  --source-root 'data/医保审核前期资料' \
  --package-version-key source-package-real-data-20260602-plan \
  --database-url-env MEDICAL_AUDIT_KB_DATABASE_URL \
  --output drafts/analysis/knowledge-query-incremental-plan-current-draft-20260602.md \
  --json-output tmp/outputs/knowledge-query-incremental-plan-current-20260602.json
```

当前增量计划结果：

- `ready_for_incremental_build`: `true`
- `added_files`: `0`
- `modified_files`: `0`
- `deleted_files`: `0`
- `unchanged_files`: `486`
- `pending_files`: `13`
- `estimated_new_embeddings`: `0`
- `db_rows_to_deactivate`: `0`

发布新 candidate 版本前必须完成：

1. `pgvector-import-plan` 通过。
2. `pgvector-import` dry-run 通过。
3. `scripts/audit-index-candidate-release-readiness.py` 通过，确认 candidate key 不存在、不等于 active，provider/model 与当前 active 兼容，且不同 source package 下的 candidate chunk id 与 active 无碰撞。
4. `pgvector-import --execute --index-version-status candidate` 写入候选版本。
5. `evaluate-postgres-index` 固定评测通过。
6. `evaluate-answers` fallback 答案评测通过。
7. `ui-smoke` 在候选版本切换前后按需执行。

当前生产门禁结果：

- `knowledge-query-index-candidate-release-readiness-20260603` 返回 `blocked`，原因是 `candidate-index-version-key-already-exists` 和 `candidate-index-version-key-matches-active`。
- 旧 candidate `full-rebuild-20260603081846` 的 `pgvector-import` dry-run 为 `success=true`，但 `chunk_collision_check.collision_count=48985`，因此继续阻断写库。
- package-aware chunk id 修复已部署到腾讯云生产镜像，fixed candidate `full-rebuild-20260603085815` 已重新构建。
- fixed candidate 构建结果：`persistent_chunk_count=48985`、`embedding_reused_count=48985`、`embedding_created_count=0`、`pending_file_count=0`、`failed_file_count=0`。
- fixed candidate 的 `pgvector-import-plan` 和 `pgvector-import` dry-run 通过；发布就绪审计返回 `status=pass`、`safe_to_execute_candidate_write=true`、`chunk_collision_check.collision_count=0`、`evidence_grade=L3-production-read-only + L2-dry-run`。
- 受控 `pgvector-import --execute --index-version-status candidate` 已执行；随后受控 `index-activate --index-version-key full-rebuild-20260603085815` 已执行。
- 生产库当前包含 active `full-rebuild-20260603085815` 和 inactive `full-rebuild-20260531142344`，总计 `source_documents=972`、`document_chunks=97970`、`chunk_embeddings=97970`。
- 线上 PostgreSQL search backend 已重载，`/index/search-backend` 报告新 active 的 `matching_embedding_count=48985`。
- candidate DB vector self-query 通过：candidate 范围内 top1 命中同一 chunk，`score=1`。
- candidate PostgreSQL 固定 52 case 检索评测通过：`recall@5=100%`、`citation_hit_rate=100%`、`preview_location_success_rate=100%`。
- candidate PostgreSQL fallback 答案评测通过：8 case `pass_rate=100%`、`citation_marker_rate=100%`、`unsupported_claim_free_rate=100%`、`fallback_rate=100%`。
- 本地 artifact 评测在腾讯云轻量服务器被 OOM killer 终止，退出码 `137`；后续 candidate 评测应使用 PostgreSQL candidate-only 路径，不再在该服务器加载 733MB embedding artifact。
- 生产只读 E2E smoke `production-e2e-smoke-readonly-after-candidate-fix-20260603` 通过；复核任务写入流已跳过，不能把该结果解释为复核工作流写入验收。
- 生产只读 E2E smoke `production-e2e-smoke-readonly-after-candidate-write-20260603` 通过；复核任务写入流已跳过，不能把该结果解释为复核工作流写入验收。
- 激活后线上综合评测 run `45f56a84-c4a8-4ad3-8450-e2b1cce1b786` 通过：`retrieval.case_count=52`、`retrieval.recall_at_k=1.0`、`answer.case_count=8`、`answer.pass_rate=1.0`、`ui_smoke.success=true`。
- 生产只读 E2E smoke `production-e2e-smoke-readonly-after-activation-20260603` 通过；复核任务写入流已跳过，不能把该结果解释为复核工作流写入验收。
- rollback readiness `knowledge-query-index-rollback-readiness-after-activation-20260603` 通过：`active_count=1`、`inactive_count=1`、`rollback_target_count=1`、`safe_to_execute_rollback_rehearsal=true`。
- 真实 rollback rehearsal 已执行到旧 active：`knowledge-query-index-rollback-rehearsal-to-20260531-20260603` 成功，旧版本 `full-rebuild-20260531142344` 临时恢复为 active，查询引用版本、生产只读 E2E 和线上综合评测 run `5bf5a0d0-57e6-4105-ad98-37d9dc70f6bd` 均通过。
- rehearsal 已切回新 active：`knowledge-query-index-rollback-rehearsal-return-to-20260603-20260603` 成功，`full-rebuild-20260603085815` 恢复为 active，查询引用版本、生产只读 E2E 和线上综合评测 run `18b97df2-c75b-4aa3-95b7-f5e001e9c3a1` 均通过。
- rollback readiness `knowledge-query-index-rollback-readiness-after-return-20260603` 通过：`active_count=1`、`inactive_count=1`、`rollback_target_count=1`。
- 结论：索引 candidate 写入、激活、回滚演练、切回和 smoke 闭环已完成；后续新资料包发布必须复用同一门禁链路。

日常发布优先使用索引管理页：

1. 打开 `http://127.0.0.1:8010/pages/index-admin`。
2. 在 `Release Console` 的 `发布 candidate` 输入候选 `index_version_key`。
3. 点击 `发布 candidate`，接口会调用 `POST /index/versions/activate`。
4. 点击 `重载 PostgreSQL 后端`，接口会调用 `POST /index/search-backend/postgres`。
5. 在 `Acceptance Panel` 点击 `运行发布后验收`，接口会调用 `POST /index/evaluation/run`。
6. 用 `Smoke Question` 打开 `/pages/chat`，人工确认引用型回答和原文预览链路正常。
7. 在 `验收历史` 打开 `历史报告列表`，确认本次报告已进入 `/index/evaluation/history`。

`Acceptance Panel` 默认执行三类门禁：

- 固定 52 case 检索评测，要求 `recall@k` 达到阈值。
- 固定 8 case fallback 答案评测，要求 `pass_rate` 达到阈值。
- 单条 UI smoke 预览解析，要求第一条引用可打开原文。

限制：该面板验证当前 API 进程已加载的检索后端，不会重建索引。每次运行会把 JSON 报告写入 `index_root/evaluation-runs/`，并在 PostgreSQL 后端运行时写入 `index_evaluation_runs` 历史表；管理页可通过 `下载最新验收报告 JSON` 获取完整报告，也可通过 `历史报告列表` 复盘最近运行。需要 Markdown 审计材料时仍使用 CLI 的 `--output` 和 `--json-output`。

候选版本通过门禁后，执行显式激活：

```bash
MEDICAL_AUDIT_KB_DATABASE_URL='postgresql://medical_audit_kb:medical_audit_kb_dev@localhost:5433/medical_audit_kb' \
uv run medical-audit-kb index-activate \
  --index-version-key full-rebuild-YYYYMMDDHHMMSS \
  --database-url-env MEDICAL_AUDIT_KB_DATABASE_URL \
  --output drafts/analysis/knowledge-query-index-activation-draft-YYYYMMDD.md \
  --json-output tmp/outputs/knowledge-query-index-activation-YYYYMMDD.json
```

激活语义：

- 目标版本必须存在，状态必须是 `candidate` 或 `active`。
- 同一 `vector_provider` + `vector_model` 下旧 active version 会被置为 `inactive`。
- 激活后必须重启或重新加载 PostgreSQL 检索后端，因为 API 进程内 BM25 索引是在加载后端时构建的。
- 当前已对真实 PostgreSQL 执行过事务内 rollback 激活验证，SQL 可执行且未改变库状态。

如果激活后的固定评测或 UI smoke 失败，回滚到最近一个已验收的历史版本：

UI 路径：

1. 在 `Release Console` 的 `回滚到历史版本` 输入最近一个已验收的历史 `index_version_key`。
2. 点击 `回滚到历史版本`，接口会调用 `POST /index/versions/rollback`。
3. 点击 `重载 PostgreSQL 后端`。
4. 在 `Acceptance Panel` 重新运行发布后固定验收。
5. 再执行 `Smoke Question` 人工确认。

CLI 兜底路径：

```bash
MEDICAL_AUDIT_KB_DATABASE_URL='postgresql://medical_audit_kb:medical_audit_kb_dev@localhost:5433/medical_audit_kb' \
uv run medical-audit-kb index-rollback \
  --index-version-key previous-active-version-key \
  --database-url-env MEDICAL_AUDIT_KB_DATABASE_URL \
  --output drafts/analysis/knowledge-query-index-rollback-draft-YYYYMMDD.md \
  --json-output tmp/outputs/knowledge-query-index-rollback-YYYYMMDD.json
```

回滚语义：

- 目标版本必须存在，状态必须是 `inactive` 或 `active`。
- `candidate` 不能作为 rollback 目标；candidate 必须先走发布门禁和 `index-activate`。
- 同一 `vector_provider` + `vector_model` 下当前 active version 会被置为 `inactive`。
- 回滚后必须重新加载 PostgreSQL 检索后端，并重新运行 `evaluate-postgres-index`、`evaluate-answers` 和 `ui-smoke`。
- 当前已对真实 PostgreSQL 执行过事务内 rollback 验证，SQL 可执行且未改变库状态。

## 13. PostgreSQL 检索评测

pgvector self-query smoke：

```bash
uv run python - <<'PY'
import json
import psycopg
from medical_audit_kb.retrieval.postgres_search import PostgresVectorIndex

dsn = 'postgresql://medical_audit_kb:medical_audit_kb_dev@localhost:5433/medical_audit_kb'
with psycopg.connect(dsn) as conn, conn.cursor() as cur:
    cur.execute('select chunk_id, embedding::text from chunk_embeddings order by chunk_id limit 1')
    expected_id, vector_text = cur.fetchone()
query_embedding = tuple(float(item) for item in vector_text.strip('[]').split(','))
index = PostgresVectorIndex(
    database_url=dsn,
    provider='openai',
    model_name='kimi-for-coding',
    provider_version='v1',
    dimension=1024,
)
results = index.search(query_embedding, top_k=3)
print(json.dumps({
    'expected_id': str(expected_id),
    'top_id': str(results[0].record.chunk_id),
    'top_score': results[0].score,
    'passed': str(results[0].record.chunk_id) == str(expected_id) and results[0].score == 1.0,
}, ensure_ascii=False, indent=2))
PY
```

当前 self-query smoke 结果：

- JSON：`tmp/outputs/knowledge-query-postgres-vector-self-query-smoke-20260601.json`
- `passed`: `true`
- `top_score`: `1.0`

PostgreSQL 数据源 BM25 固定 52 case 评测：

```bash
MEDICAL_AUDIT_KB_DATABASE_URL='postgresql://medical_audit_kb:medical_audit_kb_dev@localhost:5433/medical_audit_kb' \
uv run medical-audit-kb evaluate-postgres-index \
  --source-root 'data/医保审核前期资料' \
  --cases-file configs/evaluation/knowledge-query-human-evaluation-cases-v1.yaml \
  --output drafts/analysis/knowledge-query-postgres-bm25-evaluation-v1-draft-20260601.md \
  --json-output tmp/outputs/knowledge-query-postgres-bm25-evaluation-v1-20260601.json \
  --max-cases 52 \
  --top-k 5 \
  --embedding-provider fake \
  --embedding-dimension 1024
```

当前 BM25 评测结果：

- `case_count`: `52`
- `recall@5`: `100%`
- `citation_hit_rate`: `100%`
- `preview_location_success_rate`: `100%`

限制：当前 shell 未设置 `KIMI_API_KEY`，尚未运行固定 52 case 的真实 pgvector+Kimi 查询向量评测。

## 14. API 运行态切换 PostgreSQL 检索

默认 API 启动后不自动加载 PostgreSQL 检索后端。当前推荐使用脚本完成“启动 API + 加载 PostgreSQL 检索后端”：

```bash
export KIMI_API_KEY='实际 key'
scripts/serve-chat-workbench.sh
```

脚本默认参数：

- `MEDICAL_AUDIT_KB_HOST=127.0.0.1`
- `MEDICAL_AUDIT_KB_PORT=8010`
- `KIMI_EMBEDDING_MODEL=kimi-for-coding`
- `KIMI_EMBEDDING_DIMENSION=1024`
- `KIMI_EMBEDDING_BASE_URL=https://api.kimi.com/coding/v1`
- `KIMI_EMBEDDING_BATCH_SIZE=16`
- `KIMI_API_KEY_ENV=KIMI_API_KEY`

查看当前检索后端：

```bash
curl http://127.0.0.1:8010/index/search-backend
```

查看 PostgreSQL 已导入索引状态：

```bash
curl http://127.0.0.1:8010/index/postgres-status
```

该接口必须显示：

- `row_counts.document_chunks = 48985`
- `row_counts.chunk_embeddings = 48985`
- `row_counts.failed_files = 0`
- `row_counts.pending_files = 13`
- `embedding_sets[0] = openai/kimi-for-coding/v1/1024`

备用手动加载 Kimi 主索引对应的 PostgreSQL 检索后端：

终端 A 启动 API：

```bash
export KIMI_API_KEY='实际 key'
uv run uvicorn medical_audit_kb.api.app:create_app --factory --host 127.0.0.1 --port 8010
```

终端 B 加载后端：

```bash
curl -X POST http://127.0.0.1:8010/index/search-backend/postgres \
  -H "Content-Type: application/json" \
  -H "X-Role: it-admin" \
  -d '{
    "embedding_provider":"openai",
    "embedding_model":"kimi-for-coding",
    "embedding_dimension":1024,
    "api_key_env":"KIMI_API_KEY",
    "embedding_base_url":"https://api.kimi.com/coding/v1",
    "embedding_batch_size":16
  }'
```

加载成功后再执行 `/pages/chat` 或 `/query`。如果返回 `409`，先检查 `KIMI_API_KEY` 是否在启动 API 的同一 shell 环境中存在；如果返回 `503`，先检查 PostgreSQL 容器、schema 和导入数据。

加载成功响应中的 `details.matching_embedding_count` 必须大于 `0`。当前 Kimi 主索引期望为 `48985`，如果为 `0` 或返回 `409 no postgres embeddings match requested provider metadata`，说明请求参数与数据库中的 `openai/kimi-for-coding/v1/1024` 主索引不一致。

注意：不要使用默认配置中的 `text-embedding-3-small` 参数加载当前数据库。当前数据库向量是 `openai/kimi-for-coding/v1/1024`，查询 embedding provider 必须一致。

## 15. UI 查询闭环 Smoke

设置有效 `KIMI_API_KEY` 后，执行 UI 查询闭环 smoke：

```bash
export KIMI_API_KEY='实际 key'

uv run medical-audit-kb ui-smoke \
  --question '医保基金审核依据' \
  --json-output tmp/outputs/knowledge-query-ui-smoke-kimi-20260601.json
```

该命令会按顺序验证：

- `/index/postgres-status`
- `/index/search-backend/postgres`
- `/pages/query`
- `/pages/preview/{chunk_id}`

管理页替代路径：进入 `http://127.0.0.1:8010/pages/index-admin`，先确认 `Release Console` 中 PostgreSQL 后端为就绪状态，再用 `Acceptance Panel` 执行 `/index/evaluation/run`。该路径覆盖固定检索评测、答案评测和预览 smoke，并生成 `index_root/evaluation-runs/` JSON 报告；可通过 `/index/evaluation/latest/export` 下载完整报告，通过 `/index/evaluation/history` 查看最近验收历史。

如果当前 shell 未设置 `KIMI_API_KEY`，命令返回 `2`，JSON 中 `backend_load_status_code` 为 `409`。不要把 key 写入命令参数或仓库文件，只通过环境变量传入。

## 16. 审计底稿导出闭环

对话页返回引用型回答后，可通过页面按钮或接口导出单轮审计底稿。导出内容用于人工复核和底稿草案，不替代正式审计结论。

Markdown 导出：

```bash
curl -fsS \
  'http://127.0.0.1:8021/pages/chat/export?question=医保基金审核依据&format=markdown' \
  -o tmp/outputs/auditscope-dossier.md
```

JSON 导出：

```bash
curl -fsS \
  'http://127.0.0.1:8021/pages/chat/export?question=医保基金审核依据&format=json' \
  -o tmp/outputs/auditscope-dossier.json
```

导出验收点：

- 文件包含问题、回答、置信度、生成方式和复核门禁。
- 文件包含人工复核清单。
- 每条引用包含 `chunk_id`、`index_version_key`、`source_package_version_key`、`score`、`locator` 和原文预览链接。
- 后端未 ready 或无引用依据时，接口必须失败，不允许生成空底稿。

## 17. 视觉回归基线

`ui-smoke` 只证明查询页和原文预览链路可用，不证明页面布局、关键文案和移动端无横向溢出。每次改 `/pages/chat`、`app.css` 或证据展示模板后，在后端 ready 的本地服务上执行视觉基线捕获：

```bash
uv run python scripts/capture-chat-workbench-visual-baseline.py \
  --base-url http://127.0.0.1:8021 \
  --report tmp/outputs/knowledge-query-chat-visual-baseline-latest.json
```

该脚本不接收 API key，也不启动检索后端；它要求当前服务的 `/index/search-backend` 已经返回 `ready=true`。默认输出：

- 桌面截图：`tmp/screenshots/knowledge-query-chat-visual-baseline-desktop.png`
- 移动截图：`tmp/screenshots/knowledge-query-chat-visual-baseline-mobile.png`
- JSON 报告：`tmp/outputs/knowledge-query-chat-visual-baseline-latest.json`

JSON 报告必须满足：

- `status=pass`
- `captures[].metrics.scrollWidth <= captures[].metrics.clientWidth`
- 桌面和移动截图均包含“可追溯回答、证据卷宗、人工复核清单、核验原文、复制引用、导出 Markdown 底稿、导出 JSON 记录”

如果脚本返回 `2`，先处理后端未 ready、关键文案缺失或横向溢出，再继续提交 UI 变更。

## 18. 验收指标

- 可索引文件成功率不低于 `95%`。
- 失败队列和待处理队列覆盖率为 `100%`，不可静默丢失文件。
- 查询结果必须包含 `index_version_key` 和 `source_package_version_key`。
- 引用定位成功率必须覆盖 Markdown/txt 行、PDF 页码、xlsx 行。
- 评测集 `recall@5` 达到内部基线后，再进入答案生成质量评估。
- 查询、预览、导出、索引管理操作必须能在操作日志中追踪。
