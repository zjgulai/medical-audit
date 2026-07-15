---
title: 前端页面沟通 0710 生产闭环验收矩阵
doc_type: analysis
module: product
status: draft
created: 2026-07-15
updated: 2026-07-15
owner: self
source: human+ai
source_artifact: /Users/pray/Desktop/audit/前端页面沟通0710.pptx
branch: codex/ppt-production-closure-20260715
evidence_level: mixed-L2-L4
draft_pr: 236
promotion_status: draft-pr-open
production_write: false
provider_call: false
database_write: local-test-only
deploy_execution: false
---

# 前端页面沟通 0710 生产闭环验收矩阵

## 判定原则

- `implemented`：最终代码中存在可追溯实现，且至少有针对性自动化测试。
- `partial`：只完成收敛后的部分语义、只存在目录/入口，或缺少原 PPT 要求的业务动作。
- `blocked`：需要医院业务输入、正式模板、生产写入或真实 provider 授权，当前不得伪造。
- “代码已进入部署 SHA”只证明产物随版本发布，不等于交互、业务写入或真实 provider 已完成生产验收。
- 当前生产 runtime 最近验证为 `2bba501c93eaf1f6f7485241ec15e0c21c209842`；PR `#232` 的 PPT 产品实现是该 SHA 的祖先。

## 15 页逐页矩阵

| PPT 页 | 原始反馈闭环 | 当前判定 | 已有代码 / 本地证据 | 当前生产证据 | 缺口与闭环标准 |
| ---: | --- | --- | --- | --- | --- |
| 1 | 删除副标题和红框冗余，只保留完整主品牌 | implemented | 登录与 shell 测试；R01/R03 本地 pass | `/login`、品牌文本和部署 SHA可达 | 补最终部署代码对应的登录截图，确认副标题不存在 |
| 2 | 采用简洁登录布局；医院名称后置 | implemented | R02 本地测试/截图；医院名明确为后续配置 | `/login` 200 | 补桌面/移动生产视觉截图；医院名不作为本轮缺口 |
| 3 | 9 个主模块、唯一专题入口、Logo/标题一致 | implemented | shell/navigation tests；9+1 合同 | 生产页面 body 显示 9+1 导航 | 补 active state、窄屏、Logo 一致性的生产交互截图 |
| 4 | Enter 换行、箭头发送；历史对话不自动成任务，需要时人工提交 | implemented（L2 本地候选） | 显式选择项目后人工提交；owner/project/permission 三重校验；读取 ready + project/review-task 持久化能力 fail-closed；JSON 文件解析、编码、格式和写入失败统一 503 且保留审计终态；稳定幂等任务；Markdown/DOCX 底稿导出；移动端抽屉可滚动 | 当前生产仍运行旧部署版本；未执行生产转任务写入 | 候选合入并部署后，单独授权一条生产业务写入 UAT；禁止自动建任务 |
| 5 | 我的智能体在 67% 等缩放下记录集合稳定 | implemented | 固定 12 条/页；67/100/125% 本地矩阵 | `/agents` 桌面/移动路由通过 | 用最终代码重跑 67/100/125% 并记录 agent id 集合 |
| 6 | 点击我的智能体可直接使用/进入详情，不只是放大卡片 | implemented | `/chat?agent=...` hydration 与直接使用测试 | `/agents`、`/chat` 可达 | 补生产点击链验证；不触发 provider |
| 7 | 我的智能体数据稳定，不因 API/fixture 混用变化 | implemented | ready/empty/degraded/error 与身份失效测试 | 生产当前验收身份显示真实空集合 | 补生产身份切换后的稳定性验收；不得注入 fixture |
| 8 | 知识库内容稳定且可点击进入 | implemented | catalog 单一来源、source-scoped 文档/对话/图谱链接测试 | `/knowledge-base` 路由和关键文案通过 | 补三类链接生产点击链；GET 可能写审计日志时按 L4 标注 |
| 9 | 文档检索首页信息准确稳定 | implemented | API-first 搜索、筛选和历史状态测试 | `/documents` 路由和检索入口通过 | 补真实检索业务动作需独立写入/provider 边界 |
| 10 | 切换布局/筛选后文档数量不能异常变 0 | implemented（L2 本地候选） | 文档数只读取 `document_count`，不再以 `chunk_count` 冒充；未知显示“待同步”，真实 `0` 保持 `0`；adapter/page 回归与本地浏览器证据已通过 | 当前生产仍运行旧部署版本；未验证候选生产计数切换 | 候选合入并部署后补生产只读/审计分层的筛选切换验收 |
| 11 | 真实数据按科室、金额、类型分析；讨论文档/OCR | partial | CSV/XLSX 表格画像、质量提示和审计信号已实现 | `/analytics` 路由、上传入口和历史可见 | 需要脱敏医院样本完成业务聚合 UAT；OCR 保持独立安全门 |
| 12 | 业务关系图 / 知识关系图产品定位 | partial / blocked | 知识依据与项目证据链双视图已实现 | `/graph` 路由和双视图文案可见 | 医院未提供流程、表单和角色输入，业务流程图不得伪造 |
| 13 | 六类底稿/报告分类，生成后进入项目 | partial / blocked | 六类目录；3 个底稿模板 active；草稿关联项目 | `/reports` 路由和六类目录可见 | 五类正式业务模板待提供；签发、电子签章、长期归档另立门 |
| 14 | 项目管理支持有权限的新建项目 | implemented（L2 本地候选） | admin-only `POST /projects` 与创建表单；项目和创建人成员同事务；持久化 project/audit store 缺失或仅内存时 fail-closed；`persistent_writes_ready` 独立门禁全部 mutation；创建后立即可见；审计降级显式呈现 | 当前生产仍运行旧部署版本；未执行生产项目创建写入 | 候选合入并部署后，单独授权一条生产项目创建 UAT，并预先确定测试项目保留/清理策略 |
| 15 | 接入模型并先运行三个指定跨行业智能体 | partial / blocked | 三个扩展模板、feature flag、安装链和 fake-provider 合同已有 | 生产默认 3 个医疗智能体；`provider_call_status=not_called` | readiness 通过后单独授权真实 provider smoke，并保存三场景结果 |

## 本轮代码闭环范围

1. 历史对话人工转任务。
2. 有权限的新建项目。
3. 文档统计未知值与真实 `0` 的区分。

上述三项已形成 L2 本地候选并通过自动化与浏览器验收；仍不能把它们表述为已部署，也不能把第 11、12、13、15 页的医院输入/provider 阻塞写成已完成。

## 生产验收分层

| 层级 | 本轮可执行 | 结论边界 |
| --- | --- | --- |
| L2 local | 单元、集成、full-stack、最终代码 Playwright | 证明实现与本地合同，不证明生产 |
| L3 production read-only | marker、容器、前门、无副作用 public probe | 证明生产状态，不证明业务动作 |
| L4 audit-log-only | 完整浏览器 GET 矩阵，需精确授权并记录日志 delta | 证明页面与权限读取，不证明项目创建/转任务/provider |
| L4 business write | 项目创建、历史转任务、上传、报告草稿 | 每类动作单独授权、留痕和回滚/清理方案 |
| L4 provider | 三个扩展智能体真实调用 | 独立 readiness、费用/模型/输出证据，不能与浏览器验收合并 |

## 本地发布准备证据

- Pytest：`645` 项通过；历史/项目 targeted：`28` 项通过。
- Vitest：`32 files / 295 tests`；Ruff、Mypy、ESLint、TypeScript、Next build `24/24`、冻结 JSON 语法与 `git diff --check` 均通过。
- 本地 full-stack Playwright：`13/13`；专项截图覆盖文档真实 `0`、项目创建和移动端历史转任务。
- 最终独立复审：accepted P0/P1/P2=`0`；当前推广状态为 `draft_pr_open`。
- 三个业务原子 commit 已 push，Draft PR `#236` 已创建；产品/验收与推广状态 docs-only commit 正在收尾。
- 尚未 Ready、merge 或 deploy。

## 当前边界

- `production unchanged`
- `provider_call=false`
- `database_write=local-test-only`
- `deploy_execution=false`
- 本文是动态验收矩阵；每个阶段只依据新鲜证据更新状态。
