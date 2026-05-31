---
title: 知识库查询引擎架构说明
doc_type: architecture
module: knowledge-query-engine
topic: medical-audit-knowledge-query-engine
status: stable
created: 2026-05-31
updated: 2026-05-31
owner: self
source: human+ai
---

# 知识库查询引擎架构说明

## 1. 定位

知识库查询引擎首版定位为 `检索 + 引用型问答 + 原文定位`。

它服务审计员查法规、政策、规则、医保目录依据，不直接替代规则引擎输出合规判定。合规判断后续由结构化规则和审计数据链路承担，知识库负责提供可追溯依据。

## 2. 核心边界

- 知识库、索引、文档元数据、chunk 和引用链本地保存。
- 模型调用通过 provider 抽象，开发期可用云端 API，交付版可替换为私有化模型。
- 开发期禁止上传患者数据到外部模型服务。
- `data/` 原始资料只读，索引产物写入 `index_root`。
- OCR 不进入首版，扫描件和图片进入待处理队列。

## 3. 知识集合

首版固定四类来源集合：

- `medical-insurance-catalog`：医保目录、DRG/DIP 目录、药品目录等。
- `supervision-rules-knowledge`：智能监管“两库”规则和知识点。
- `risk-negative-list`：风险负面清单、违规风险案例。
- `medical-insurance-laws`：医保、医疗、药品、基金监管、处方、门特相关法律政策。

`全量法律` 不做无差别索引，只抽取与医保审核和医疗审计相关的文本进入首版索引。

## 4. 数据流

```mermaid
flowchart LR
  A["data/ 原始资料"] --> B["Inventory 扫描"]
  B --> C["Extractor 抽取文本"]
  C --> D["Chunker 结构化切分"]
  D --> E["Embedding + BM25 索引"]
  E --> F["Hybrid Search"]
  F --> G["Citation Answer"]
  G --> H["Preview Resolver 原文定位"]
```

## 5. 切分与定位

- 法规政策按条款、章节和标题层级切分。
- Markdown/txt 保留 `line_start`、`line_end` 和标题上下文。
- PDF 保留 `page_number`。
- xlsx 保留 `sheet_name` 和 `row_number`。
- 每个 chunk 必须保留 `source_collection`、`source_path`、`index_version_key`、`source_package_version_key`。

## 6. 检索链路

检索采用 `BM25 + vector + source weight + optional rerank`。

- BM25 负责精确术语、政策号、条款号和规则名称召回。
- 向量检索负责自然语言语义召回。
- 来源权重提升业务上更可信的规则来源。
- rerank 用于对混合召回结果重新排序。
- 元数据过滤支持来源集合、年份、地区、文档类型、业务主题。

## 7. 引用型回答

回答生成必须满足：

- 无引用结果时不得生成答案。
- 每条引用必须绑定 chunk、locator、索引版本和资料包版本。
- 依据按法规、规则、目录、风险案例分组。
- 生成模型失败或不可用时返回检索依据型 fallback 答案。
- 原文预览必须从引用 locator 回到源文件位置。

## 8. 索引版本

每次全量重建、增量索引或单文件重试都生成运行摘要。查询结果和引用必须可追溯到：

- `source_package_version_key`
- `index_version_key`
- `chunk_id`
- 原始文件路径与 locator

## 9. 验收指标

- 可索引文件成功率不低于 `95%`。
- 不可处理文件必须进入失败队列或待处理队列，不能静默丢失。
- 查询结果必须返回索引版本、资料包版本和引用定位。
- 评测集 `recall@5` 达到内部基线后再进入生成质量评估。
- 引用答案不得出现无来源结论。
- 原文预览必须能定位 Markdown/txt 行、PDF 页码、xlsx 行。
