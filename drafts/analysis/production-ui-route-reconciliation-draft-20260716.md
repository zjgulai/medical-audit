---
title: 生产前端逐路由收敛矩阵
doc_type: analysis-draft
module: web-release
status: active
created: 2026-07-16
updated: 2026-07-16
owner: self
source: chrome+repository+production-readonly
---

# 生产前端逐路由收敛矩阵

## 结论与证据边界

- 生产基线固定为 `main@1376baef0d8d47f1e1ef60b2cec130451af5af4f`；本矩阵只冻结逐路由收敛决策，不证明后续实现、合并或部署已完成。
- 2026-07-16 重新读取 dirty workspace 差异：`web/src` 有 15 个 tracked 修改、2 个 untracked 源文件；tracked diff 为 `1857 insertions(+), 686 deletions(-)`。
- clean release `web/src` 与 dirty workspace `web/src` 的 `git diff --no-index --stat` 为 85 files changed、`8349 insertions(+), 31446 deletions(-)`。这证明两棵源码存在广泛历史分叉，不支持整文件覆盖，只允许按矩阵语义移植。
- 2026-07-16 命令新鲜取证确认：公网产物与 clean release `web/out` 共 87 个文件逐项匹配，结果为 `87/87 hash match`；该证据只确认已发布静态产物对应 clean baseline，不替代逐路由语义验收。
- dirty workspace 仅用于只读取证；未应用 patch、未复制整文件、未改动旧 workspace。
- 生产只读页面证据来自同日 Chrome 复核与 `tmp/outputs/production-frontend-acceptance-main-1376bae-20260716T022942CST.json`。现有 hardened gate 对 18 个路由在 desktop/mobile 均返回 200，但 `/workspace`、`/findings`、`/knowledge-query` 发生重定向仍被计为通过，因此 200 不能替代最终路径与页面语义验收。
- 本轮目标合同为 17 个独立页面与 3 个显式别名；写动作始终与页面读取验收分层。

## 逐路由收敛矩阵

| route / layer | clean_main_source | dirty_source | production_observation | decision | write_boundary | acceptance_contract |
|---|---|---|---|---|---|---|
| `/login` | `web/src/app/login/page.tsx` → `LoginSurface`，属于 clean-main 登录入口 | dirty 同路径为旧登录实现；不在 15 个 tracked Web delta 内，但整体仓库落后 | 未纳入现有 hardened acceptance；必须作为未登录入口单独验证 | `preserve-clean-main` | 页面加载不得触发业务写入 | 未认证访问展示登录界面；desktop/mobile 无溢出、无 console error；登录后的 local/session 状态不视为业务数据验收 |
| `/workspace` | `web/src/app/(workspace)/workspace/page.tsx` 明确 `redirect("/chat")` | dirty 同路径仍为旧入口，整体源码历史落后 | desktop/mobile 均 200，但 `finalUrl=/chat`；旧 gate 将其误计为独立页通过 | `explicit-alias` | 仅导航；不得触发 provider、项目或 review 写入 | 请求 `/workspace` 必须最终到 `/chat`，alias 报告必须记录 requested path 与 final path，不得按独立页重复计数 |
| `/medical-audit` | `web/src/app/(workspace)/medical-audit/page.tsx` 为 clean-main 医保审计专题工作台 | dirty workspace 缺少该 clean-main 页面，整文件回迁会删除现有专题工作台 | 现有 hardened route 列表未直接覆盖；`/findings`、`/remediation` 可重定向至此并正常渲染 | `preserve-clean-main` | 页面读取可验收；新建任务、导入、复核、补证、报告等动作均不在本页只读验收授权内 | 必须作为独立页直接验收，最终路径保持 `/medical-audit`；检查专题标题、规则/疑点/三张表单可见，写控件只做权限与禁用态检查 |
| `/chat` | clean-main 为 `web/src/app/(workspace)/chat/page.tsx`，包含检索来源、模型与附件分析合同 | dirty 同路径为较旧 `fetchAgents` 门面；不属于本轮 tracked patch，整体历史落后 | hardened acceptance desktop/mobile 200，最终路径保持 `/chat` | `preserve-clean-main` | 页面加载只读；发送问题、provider call、附件分析需独立授权 | 标题与核心输入控件可见；最终路径精确；验收不得发送问题或调用 provider |
| `/agents` | `web/src/app/(workspace)/agents/page.tsx` → `ReplicaAgentDirectory mode="mine"` | dirty 同路径为旧 `AgentWorkspace`，不属于本轮 tracked patch | hardened acceptance desktop/mobile 200，最终路径保持 `/agents` | `preserve-clean-main` | 页面读取可验收；创建/修改智能体禁止 | 展示“我的助手/我的智能体”与详情入口；最终路径精确；不得执行 create/update |
| `/agent-market` | `web/src/app/(workspace)/agent-market/page.tsx` → `ReplicaAgentDirectory mode="market"` | tracked dirty 改为 `fetchAgents` 并带 `createAuditAgent` 相关交互，语义和写边界均更旧 | Chrome/acceptance 显示当前 clean-main 广场；desktop/mobile 200 且最终路径精确 | `preserve-clean-main` | 浏览详情只读；创建智能体禁止 | 保留 clean-main 分类、卡片和详情合同；不得以 dirty 整页覆盖，不得触发创建写入 |
| `/analytics` | `web/src/app/(workspace)/analytics/page.tsx` → `ReplicaAnalyticsWorkbench` | dirty 为旧 `DataAnalysisWorkbench`；不属于本轮 tracked patch | hardened acceptance desktop/mobile 200，最终路径保持 `/analytics` | `preserve-clean-main` | 页面读取可验收；表格上传禁止 | 表格分析工作台与历史入口可见；不选择文件、不上传对象 |
| `/projects` | `web/src/app/(workspace)/projects/page.tsx` → `ReplicaProjectWorkbench` | dirty 为旧 `ProjectManagementWorkbench`；不属于本轮 tracked patch | hardened acceptance desktop/mobile 200，最终路径保持 `/projects` | `preserve-clean-main` | 页面读取可验收；项目创建、成员与项目修改禁止 | 项目协作工作台与可见项目合同保持；不得创建或修改项目 |
| `/documents` — GET-only surface | clean-main `web/src/app/(workspace)/documents/page.tsx` 已有文档分类、检索和引用预览；`api-client.ts` 已具备 permissions/uploads/history GET 接口 | tracked dirty 页面展示 `fetchDocumentPermissions`、`fetchDocumentUploads`、`fetchQueryHistory` 形成的个人材料权限、上传台账与历史视图 | Chrome 显示检索与分类，但无个人上传/治理/索引状态面板；acceptance desktop/mobile 200，最终路径精确 | `port-semantically` | 只允许 GET 与本地筛选；不得借 GET 面板触发写请求 | 在保留 clean-main 搜索体验前提下增加权限、个人材料台账、治理状态、索引状态的只读面板；空态/无权限/错误态可区分 |
| `/documents` — write controls | clean-main API client 已定义 upload、governance、index 写接口，但当前页面未建立完整权限门禁 | dirty 页面包含 `uploadPersonalDocument`、`updateDocumentUploadGovernance`、`indexPersonalDocument` 按钮与状态 | 生产页面无对应写面板；本轮没有上传、治理或索引写入证据 | `blocked-by-write-authorization` | 禁止对象存储写入、governance 写入与 index 写入；不得靠隐藏按钮代替服务端权限 | 控件可按权限显示为 disabled/locked 并解释原因；任何 production acceptance 不得调用 POST/PATCH/DELETE，真实写验收另开授权 lane |
| `/knowledge-base` | clean-main 页面使用 `useReplicaKnowledgeBaseData`、来源集合映射与分类交互 | tracked dirty 为较窄 permissions/backend 状态页，移植整页会丢失 clean-main 分类与交互 | Chrome 显示新版知识库实现；acceptance desktop/mobile 200，最终路径精确 | `preserve-clean-main` | GET-only；不执行上传、索引或治理写入 | 保留一级专题、来源筛选、空态与 runtime badge；新增批次不得回退为 dirty 旧页 |
| `/graph` | clean-main 页面包含 knowledge/project 双视图、项目选择、节点与关系交互及 runtime/fallback 状态 | tracked dirty 为单一 `fetchGraphWorkbench` 图谱页，能力面较窄 | Chrome 显示新版知识图谱；acceptance desktop/mobile 200，最终路径精确 | `preserve-clean-main` | GET-only；不执行项目或图谱写入 | 保留双视图、节点/关系详情、键盘与失败态合同；新增批次不得回退 clean-main 图谱 |
| `/rules` | clean-main `web/src/app/(workspace)/rules/page.tsx` 以硬编码常量展示 `2,546 / 49,051 / 128` | tracked dirty 页面通过 `fetchRulesWorkbench` 读取规则库、覆盖率、运行快照与发布门禁，并显式区分持久后端/seed/fallback | Chrome 确认生产仍显示硬编码指标；acceptance 200 但只验证宽泛“知识库/规则/法规”文本 | `port-semantically` | GET-only；不得发布规则、切换 provider 或执行规则写入 | 独立页最终路径 `/rules`；展示 runtime/fallback badge、规则来源覆盖、运行状态与发布门禁；禁止静态数值冒充运行数据 |
| `/reports` | clean-main `web/src/app/(workspace)/reports/page.tsx` → `ReplicaReportWorkbench`，保留模板与台账合同 | dirty 为另一套 `fetchReportWorkbench` 页面；不属于 15 个 tracked patch，但整体版本落后 | hardened acceptance desktop/mobile 200，最终路径保持 `/reports` | `preserve-clean-main` | 目录与台账读取可验收；草稿创建、签发、导出写入禁止 | 保留六类模板目录与报告台账；只检查只读可见性与下载入口权限态，不生成报告 |
| `/remediation` | clean-main 当前 `redirect("/medical-audit")`，没有独立整改工作台 | tracked dirty 页面以 `fetchRemediationWorkbench` 展示整改事项、补证请求、关闭门禁和时间线，并区分 runtime/seed/fallback | Chrome 与 acceptance 均确认 `finalUrl=/medical-audit`；旧 gate 将其误计为整改页通过 | `port-semantically` | GET-only；整改状态、补证登记、关闭判断写入禁止 | 恢复为最终路径 `/remediation` 的独立页；展示待处理、补证、责任、关闭门禁和时间线；不得接受重定向后的医保审计文本作为通过 |
| `/archive` | clean-main `ArchiveWorkbench` 来自 compatibility workbench，主要依赖 clean-main replica/static 适配 | tracked dirty 页面通过 `fetchArchiveWorkbench` 获取归档包、策略、签名链、审计运行和时间线，并区分 runtime/seed/fallback | hardened acceptance desktop/mobile 200，最终路径精确；当前文本合同不足以证明数据来自 runtime | `port-semantically` | GET-only；不得创建归档包、签名或删除归档 | 保留 clean-main 视觉结构，接入 runtime read surface；必须显示 evidence badge、归档包、策略、签名链、审计日志入口与失败态 |
| `/guided-check` | clean-main `GuidedCheckWorkbench` 为 compatibility workbench | tracked dirty 页面组合 rules/findings/report/search-backend GET 数据，形成步骤、材料、风险与问答证据状态 | hardened acceptance desktop/mobile 200，最终路径精确 | `port-semantically` | GET-only；不得发起 provider 问答、创建 finding/review/report | 独立页展示核查步骤、材料准备、风险信号与 AI 审证问题；明确静态 fallback 与 runtime 状态，不实际发送问题 |
| `/fund-compliance` | clean-main `FundComplianceWorkbench` 为 compatibility workbench | tracked dirty 页面读取 rules/findings/report，提供专题概览、疑点与报告衔接 | hardened acceptance desktop/mobile 200，最终路径精确；现有宽泛文本合同不足以证明运行数据闭环 | `port-semantically` | GET-only；不得导入、创建复核、修改 finding 或生成报告 | 在 clean-main 视觉基线上移植 runtime 专题摘要、规则、疑点、三张表单与归档衔接；runtime/seed/fallback 必须可辨 |
| `/fund-compliance/review` | clean-main `FundComplianceReviewWorkbench` 为 compatibility workbench | tracked dirty 页面具备“单据审查→费用表单→规则复核→底稿输出”四阶段、三张表及 rules/findings/report GET 数据 | Chrome 显示当前主要为三张表模板卡，缺少四阶段工作流；acceptance 200 且最终路径精确 | `port-semantically` | GET-only；不得提交复核、更新 review、创建底稿或报告 | 展示四阶段进度、费用汇总表/分类汇总表/就诊明细表、规则依据与底稿出口；交互仅限标签切换与只读查看 |
| `/findings` | clean-main `web/src/app/(workspace)/findings/page.tsx` 明确 `redirect("/medical-audit")` | dirty 同路径也为旧桥接入口，整体仓库历史落后 | desktop/mobile 200，但 `finalUrl=/medical-audit`；旧 gate 将其误计为独立页通过 | `explicit-alias` | 仅导航；不得修改 finding | 请求 `/findings` 必须最终到 `/medical-audit`；alias 单独计数并标注目标，不再宣称存在独立 findings 页面 |
| `/knowledge-query` — clean implementation | clean-main `web/src/app/(workspace)/knowledge-query/page.tsx` 是单一职责 redirect，查询体验由 `/documents` 承载 | tracked dirty 修改 `KnowledgeQueryWorkbench`，但 dirty workspace 的 route 仍指向旧页面；整套回迁会回退 clean-main `/documents` | Chrome/acceptance 确认重定向到 `/documents`，目标页为新版检索页面 | `preserve-clean-main` | 页面加载/导航只读；不得发送 provider query | 保留 clean-main 单一职责实现与 `/documents` 查询能力，不恢复 dirty 独立 workbench |
| `/knowledge-query` — public route contract | clean-main 明确 alias 到 `/documents` | dirty 组件差异仅作语义证据，不改变冻结 alias | desktop/mobile 200，但 `finalUrl=/documents`；旧 gate 将其误计为独立页通过 | `explicit-alias` | 仅导航；真实 query/provider 调用禁止 | 请求 `/knowledge-query` 必须最终到 `/documents`；保留 query string；alias 与独立页验收分开统计 |

## 冻结后的执行顺序

1. 先修正 acceptance：17 个独立页面要求最终路径精确，3 个 alias 要求最终路径等于冻结目标，并为全部目标保留 desktop/tablet/mobile 截图证据。
2. 第一实现批次只处理 `/rules`、`/remediation`、`/archive` 的只读 runtime 语义移植。
3. 第二实现批次处理 `/fund-compliance`、`/fund-compliance/review`、`/guided-check`，保持所有业务动作关闭。
4. 第三实现批次只给 `/documents` 增加 GET-only 个人材料面板；写控件保持授权锁定，真实写验收不与 UI 发布合并。
5. 每个批次都以 clean-main 为基线，并为 `/knowledge-base`、`/graph`、`/agent-market`、`/knowledge-query` 建立防回退测试。

## 当前边界

- `production unchanged`
- `provider_call=false`
- `database_write=false`
- `object_storage_write=false`
- `project_write=false`
- `review_write=false`
- `dirty_patch_applied=false`
