---
title: 知识库萃取与对话网站 20 轮优化复盘
doc_type: analysis
module: knowledge-query
topic: extraction-chat-ui-20-loop
status: draft
created: 2026-06-01
updated: 2026-06-03
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

## 2026-06-02 精细化迭代增量

本轮目标不是继续堆装饰，而是把页面从“能查询”推进到“审计员能按证据链复核”的工作台。视觉方向采用 Apple 系统字体栈、低饱和蓝灰、毛玻璃浅层次和高密度信息卡，避免娱乐化和营销化。

### 本轮 20 个精修点

| Loop | 精修点 | 落地结果 |
| --- | --- | --- |
| 1 | 审计安全边界前置 | 新增“本地证据优先、无引用不结论、人工复核门禁、患者数据边界”四卡片。 |
| 2 | 顶部审计策略显性化 | 在主标题下增加“证据优先、引用编号、原文预览、人工复核”策略标签。 |
| 3 | 检索能力状态说明 | 顶部 scoreboard 从英文状态改为“检索后端、回答规则、证据状态”。 |
| 4 | 左侧流程说明 | 审证流程增加“问题 - 依据 - 原文”提示，阻止直接跳结论。 |
| 5 | 复核门禁卡 | 根据引用数量和置信度显示“可进入人工复核 / 不可进入报告”。 |
| 6 | 追问指引 | 推荐追问增加适用条件、例外情形、原始凭证方向。 |
| 7 | 空状态问题模板 | 增加超量开药、目录限制、重复收费三类入口。 |
| 8 | 输入隐私提醒 | 明确不要输入患者姓名、证件号、手机号等敏感标识。 |
| 9 | 来源过滤卡片化 | 来源从枚举值升级为法规政策、监管两库、医保目录、风险清单四类说明卡。 |
| 10 | 来源使用目的说明 | 每个来源卡增加审计用途，例如监管边界、规则口径、目录限制。 |
| 11 | 回答质量徽标中文化 | 回答区展示“置信度 高/中/低、检索直出/模型生成、引用条数”。 |
| 12 | 回答复核摘要 | 增加结论性质、证据分组、生成方式、下一步四宫格。 |
| 13 | 审计底稿提示 | 回答进入底稿或报告前必须核验原文、适用对象、时间范围和本地规则版本。 |
| 14 | 人工复核清单 | 证据卷宗增加四项人工复核 checklist。 |
| 15 | 引用溯源元数据 | 引用项展示 `chunk`、`index`、`package`，便于定位 active index 和资料包。 |
| 16 | 原文核验动作 | 引用操作文案统一为“核验原文”，弱化普通跳转感。 |
| 17 | 复制引用动作 | 增加“复制引用”按钮，复制 `[C*]` 编号和片段。 |
| 18 | 查询页结果结构化 | 查询工作台增加查询结果摘要，替代粗糙 `<pre>` 展示。 |
| 19 | 原文预览复核链 | 原文页增加“原文复核优先级”和“查询结果 -> 引用编号 -> chunk -> 原文定位”。 |
| 20 | 输出与设备细节 | 增加 print 样式、移动端网格降级和截图级视觉验证。 |

### 验证结果

| 验证项 | 结果 |
| --- | --- |
| 页面回归 | `uv run pytest tests/knowledge_query/test_pages.py -q`，`9 passed` |
| 格式检查 | `uv run ruff format --check .`，`82 files already formatted` |
| Lint | `uv run ruff check .`，`All checks passed` |
| 全量测试 | `uv run pytest -q`，`141 passed` |
| 类型检查 | `uv run mypy src tests`，`Success: no issues found in 82 source files` |
| 真实后端加载 | PostgreSQL/Kimi 后端 ready，`matching_embedding_count=48985` |
| 真实回答态 smoke | “门诊超量开药”问题返回高置信、3 条引用，引用含 `chunk/index/package` |
| 桌面截图验证 | `tmp/screenshots/tmp-screenshot-chat-ui-refinement-20260602-answer.png` |
| 移动截图验证 | `tmp/screenshots/tmp-screenshot-chat-ui-refinement-20260602-mobile-cdp.png` |
| 可重复视觉基线 | `uv run python scripts/capture-chat-workbench-visual-baseline.py --base-url http://127.0.0.1:8021 --report tmp/outputs/knowledge-query-chat-visual-baseline-latest.json`，`status=pass` |

### 反面判断

“99% 接近大师级”不是可客观证明的工程指标。本轮能够确认的是：页面已经具备审计级信息架构、证据门禁、溯源元数据、人工复核指引、真实回答态、桌面/移动截图验证和自动化回归。下一阶段若要接近正式商用大师级，还需要做可用性访谈、真实审计员任务测试、暗色/高对比可访问性审计、像素级视觉 diff、任务级复核台和正式报告导出。

## 2026-06-02 视觉基线脚本闭环

本轮已将视觉验证从一次性截图升级为可重复脚本：

- 新增 `scripts/capture-chat-workbench-visual-baseline.py`。
- 脚本要求 `/index/search-backend` 已 ready，不接收 API key，不启动检索后端。
- 输出桌面/移动截图到 `tmp/screenshots/`，输出 JSON 报告到 `tmp/outputs/`。
- JSON 检查关键文案和 `scrollWidth <= clientWidth`，避免移动端横向溢出。
- 已更新正式运维文档，要求每次修改 `/pages/chat`、`app.css` 或证据展示模板后执行。

## 2026-06-03 审计底稿导出闭环

本轮已把当前单轮对话的回答与证据链导出为可复核底稿：

- 新增 `/pages/chat/export`。
- 支持 `format=json` 和 `format=markdown`。
- 导出内容包含问题、回答、置信度、生成方式、复核门禁、人工复核清单、证据分组和完整引用。
- 每条引用包含 `chunk_id`、`index_version_key`、`source_package_version_key`、`score`、`locator` 和 `preview_url`。
- 后端未 ready 或无引用依据时不生成底稿。
- 对话页已提供“导出 Markdown 底稿”和“导出 JSON 记录”入口。

## 2026-06-03 任务级复核台 v1

本轮已把“单轮回答底稿”进一步沉淀为本地复核任务：

- 新增 `/pages/review-tasks` 复核任务台。
- 对话页在形成引用型回答后可点击“创建复核任务”。
- 创建任务时重新执行引用查询，并保存当时的 `audit-dossier-v1` 快照。
- 复核任务支持状态、复核意见和复核结论维护。
- 状态集合覆盖待复核、确认违规、规则问题、数据问题、待补证据、未发现违规和已关闭。
- 新增任务级 JSON/Markdown 导出，格式为 `review-task-v1`。
- 当前实现为进程内本地任务台，服务重启后不保留，不等同于生产级案件系统。

## 未完成事项

- `png` 规则批次需要 OCR 或人工结构化，不能继续伪装为已处理。
- `zip/rar` 需要受控解包策略，包括大小限制、路径穿越防护和重复内容去重。
- 全量法律范围需要从“文件名关键词”升级为“主题分类 + 白名单/黑名单 + 抽样评测”。
- 对话目前仍是单轮 GET 工作台，下一阶段需要引入会话 ID、POST API、可编辑底稿和服务端持久化复核流。
- 当前已形成可重复视觉基线捕获、单轮底稿导出和本地复核任务台；下一步仍缺少像素级 diff、真实审计员任务测试、权限、数据库持久化和正式报告导出。
