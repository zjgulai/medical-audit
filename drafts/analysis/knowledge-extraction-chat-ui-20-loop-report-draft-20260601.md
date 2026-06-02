---
title: 知识库萃取与对话网站 20 轮优化复盘
doc_type: analysis
module: knowledge-query
topic: extraction-chat-ui-20-loop
status: draft
created: 2026-06-01
updated: 2026-06-01
owner: self
source: human+ai
---

# 知识库萃取与对话网站 20 轮优化复盘

## 目标

深度检查当前知识库萃取链路的问题和脆弱点，完成一轮可落地修复，并把网站从“查询表单”升级为“对话式审证工作台”。

## 行业复盘基准

- OpenAI Deep Research 的有效模式是结构化报告加可验证引用，适合高准确性任务的复核链路：<https://help.openai.com/en/articles/10500283-research-faq>
- Claude Artifacts 的有效模式是把复杂内容放在主对话旁的独立工作区，降低长回答的认知负担：<https://support.anthropic.com/en/articles/9487310-what-are-artifacts-and-how-do-i-use-them>
- OpenAI 对生成链接的风险提示说明，证据链接必须让用户保持控制并明确知道将访问什么：<https://help.openai.com/en/articles/10984597>

本项目采用的产品原则：对话区负责问题与结论，右侧证据区负责引用、质量状态和原文预览，避免把长证据直接堆进聊天气泡。

## 萃取脆弱点

| 问题 | 证据 | 风险 | 本轮处理 |
| --- | --- | --- | --- |
| XLSX 表头行被当作 chunk | 表格首行会生成“规则编码: 规则编码”类内容 | 检索可能引用表头噪声，污染回答依据 | 已跳过表头行 |
| 空文本/空表格被视为 extracted | 空内容可能形成 0 chunk 文件 | 统计显示“已萃取”，实际不可检索 | 已进入 pending，且 0 chunk 不计 indexed |
| 13 个文件仍 pending | `zip/rar/png` 当前不处理 | 图片规则批次和压缩包未进入知识库 | 本轮只显性化，不伪处理 |
| 16753 个文件被 ignored | 大量全量法律不在医保关键词范围 | 范围控制正确但召回边界脆弱 | 保留为 v1 范围策略，后续需做法律范围扩展评估 |
| PDF parser 输出 warning | pypdf 对部分对象打印 warning | 日志噪声影响批处理可读性 | 记录为后续治理项 |

## 本轮修复

- `extract_file()` 对空 Markdown/TXT 返回 `LOW_QUALITY_TEXT` pending。
- `extract_file()` 对空 XLSX 返回 `LOW_QUALITY_TEXT` pending。
- `chunk_extraction_result()` 跳过 XLSX 表头行，减少表格噪声。
- `KnowledgeIndexPipeline` 对 0 chunk 结果进入 pending，不再计入 indexed。
- 新增 `/pages/chat` 对话审证工作台。
- `/` 根路径进入对话审证工作台。
- 查询页、索引页、预览页导航增加“对话审证”入口。
- 对话页新增证据质量卡、引用分组、原文预览、后续问题建议和最近对话。

## 20-loop 结果

输出文件：`tmp/outputs/knowledge-query-chat-extraction-20-loop-20260601.json`

| Loop | 覆盖点 | 结果 |
| --- | --- | --- |
| 1 | 真实资料清点可核对 | PASS |
| 2 | pending 队列可见 | PASS |
| 3 | 法律范围裁剪显式 | PASS |
| 4 | 重复文件组可见 | PASS |
| 5 | 空文本进入 pending | PASS |
| 6 | XLSX 表头跳过 | PASS |
| 7 | 0 chunk 文件不计 indexed | PASS |
| 8 | 根路径渲染对话工作台 | PASS |
| 9 | 对话空状态 | PASS |
| 10 | 对话回答 | PASS |
| 11 | 证据检查面板 | PASS |
| 12 | 原文预览链接 | PASS |
| 13 | 后续问题建议 | PASS |
| 14 | 旧查询页保留 | PASS |
| 15 | 索引页链接对话入口 | PASS |
| 16 | 预览页链接对话入口 | PASS |
| 17 | 对话 CSS 布局 | PASS |
| 18 | API 查询回归 | PASS |
| 19 | 操作日志导出回归 | PASS |
| 20 | 键盘焦点样式保留 | PASS |

总计：`20 passed / 0 failed`。

## 未完成事项

- `png` 规则批次需要 OCR 或人工结构化，不能继续伪装为已处理。
- `zip/rar` 需要受控解包策略，包括大小限制、路径穿越防护和重复内容去重。
- 全量法律范围需要从“文件名关键词”升级为“主题分类 + 白名单/黑名单 + 抽样评测”。
- 对话目前是单轮 GET 工作台，下一阶段需要引入会话 ID、POST API、可复制结论、导出审计记录。
- 当前未做浏览器截图级视觉回归，因为本会话没有可调用浏览器截图工具。
