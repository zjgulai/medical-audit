---
title: 知识库查询引擎运行手册
doc_type: workflow
module: knowledge-query-engine
topic: knowledge-query-engine-operations
status: stable
created: 2026-05-31
updated: 2026-05-31
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

启动 API：

```bash
uv run uvicorn medical_audit_kb.api.app:create_app --factory --reload
```

访问入口：

- 查询页：`http://127.0.0.1:8000/pages/query`
- 索引管理页：`http://127.0.0.1:8000/pages/index-admin`
- 健康检查：`http://127.0.0.1:8000/health`

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

## 9. 验收指标

- 可索引文件成功率不低于 `95%`。
- 失败队列和待处理队列覆盖率为 `100%`，不可静默丢失文件。
- 查询结果必须包含 `index_version_key` 和 `source_package_version_key`。
- 引用定位成功率必须覆盖 Markdown/txt 行、PDF 页码、xlsx 行。
- 评测集 `recall@5` 达到内部基线后，再进入答案生成质量评估。
- 查询、预览、导出、索引管理操作必须能在操作日志中追踪。
