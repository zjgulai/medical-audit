---
title: 生产证据工具副作用合同设计
doc_type: design
module: release-evidence
status: implemented_local_review_passed
created: 2026-07-15
updated: 2026-07-15
owner: self
source: human+ai
baseline: origin-main@2d790375621bafa3dd564b1a1464f3e229a053a2
production_runtime_sha: b88ecdff7f773c8990454009d4a2b33ea8fdc2d4
design_option: A-approved
production_side_effect: audit-log-only-observed-before-fix
provider_call: false
database_write: audit-log-only-observed-before-fix
implementation_status: local_validation_and_review_passed_pr_pending
---

# 生产证据工具副作用合同设计

## 1. 目标

修正两个生产验收工具的副作用合同，使默认命令不再隐式写入生产，同时保留经显式授权后执行完整权限与前端验收的能力。工具输出必须如实区分有限只读证据、因无法保证只读而失败关闭的门禁，以及已授权的 `audit-log-only` 写入证据。

本设计不改变产品 API、权限模型或审计日志记录规则；只调整验收脚本、门禁和对应测试。

## 2. 已确认问题与证据边界

当前脚本把部分请求描述为 `production_side_effect=none`，但实际生产行为会持久化审计日志：

- `scripts/run-controlled-api-readonly-permission-smoke.py` 的匿名和缺失租户负向请求会写入 `authorization-denied` 事件。
- `scripts/run-production-frontend-acceptance.mjs` 调用 `/audit/logs/export`，该路由会写入 `audit-logs-export` 事件。
- 后续代码追踪确认，问题不只存在于负向请求和 export：部分成功 GET（例如 `/agents`）也会通过 `record_operation` 持久化读取事件；完整浏览器验收会加载这些 API，因此不能诚实标记为数据库零写入。
- 本次部署准备阶段通过只读查询至少归因出 69 条新增审计事件：68 条 `authorization-denied`、1 条 `audit-logs-export`。
- 这些事件保留，不执行清理或删除；生产运行版本仍为 `b88ecdff7f773c8990454009d4a2b33ea8fdc2d4`，尚未执行本轮部署。

因此，旧报告的“无生产副作用”结论失效；脚本 HTTP 方法为 GET 也不能作为数据库只读的充分证据。实现阶段据此收紧已批准方案 A：权限 smoke 默认只执行经代码追踪确认的安全子集；完整前端浏览器验收在未授权审计日志写入时直接失败关闭，不伪造有限覆盖。

## 3. 已批准方案：双模式、默认真只读

采用方案 A：同一工具保留两种显式模式。

### 3.1 默认只读模式

默认运行不接受任何隐式数据库写入：

- 权限 smoke 的 35 个候选探针中，只运行 2 个不进入受控鉴权中间件的公共 GET；其余 33 个候选明确标记 skipped。`/auth/session` handler 本身不调用 `record_operation`，但请求仍可能因持久用户被禁用等鉴权失败而由 middleware 写入 `authorization-denied`，因此不能列入通用只读 allowlist。
- 完整前端验收会执行 JavaScript 并加载可能记录读取事件的业务 API，因此未提供写入授权时必须在创建目录、启动 Chromium 或发出网络请求前失败关闭。
- 报告列出跳过的负向检查，不能把“未执行”写成“通过”。
- 报告合同包含：
  - `side_effect_mode=readonly`
  - `production_side_effect=none`
  - `database_write=false`
  - `audit_log_write_expected=false`
  - 已执行和已跳过的 probe 清单及数量

默认 package scripts 不嵌入生产写入授权。权限命令返回有限 L3 只读证据；前端验收命令在缺少显式写入授权时阻断，并说明必须使用 L4 `audit-log-only` 模式取得完整验收证据。

### 3.2 显式审计日志写入模式

新增 `--allow-audit-log-writes`。启用后恢复全部 35 个权限探针，并允许完整前端页面、业务 API、权限负向检查和审计日志导出检查，按真实副作用报告：

- `side_effect_mode=audit-log-write-enabled`
- `production_side_effect=audit-log-only`
- `database_write=audit-log-only`
- `audit_log_write_expected=true`
- 报告记录执行的负向 probe 和导出 probe，不承诺精确写入条数，实际数量由只读审计查询核验。

所有目标启用写入模式时都必须同时提供固定确认值 `--confirm-production-write audit.lute-tlz-dddd.top`。缺少或拼写错误时，在发出任何可能写入审计日志的请求前失败；Python transport 禁止跟随 redirect，frontend API fetch 使用 manual redirect，浏览器上下文阻断跨 origin 请求。这样本地地址、IP、别名或重定向均不能绕过同一确认门禁。

`--allow-audit-log-writes` 只授权既有 API 行为产生的审计日志，不授权 schema 变更、SQL 写入、回填、provider call、review/query 写入、live send 或远端分支删除。

## 4. 工具改动

### 4.1 权限 smoke

文件：`scripts/run-controlled-api-readonly-permission-smoke.py`

- 依据模式构建 probe 集合，而不是运行后再修改结果标签。
- 默认集合只保留 2 个公共 GET。
- 默认跳过 22 个匿名/缺失租户负向 GET，以及 11 个可能经过 middleware 或 handler 记录事件的管理员成功 GET；报告分别给出 `audit-log-writes-not-authorized` 和 `endpoint-may-write-audit-log` 原因。
- 写入模式恢复完整 35 个候选探针。
- 在网络请求前完成参数组合与生产确认校验。
- JSON 输出同时记录模式、预期副作用、执行项、跳过项和失败项。
- 退出码继续由实际执行的 probe 决定；跳过项不计为成功，也不导致默认只读模式失败。

### 4.2 前端生产验收

文件：`scripts/run-production-frontend-acceptance.mjs`

- 默认模式在任何文件系统、浏览器或网络动作前失败关闭，因为现有完整页面/资源验收本身可能记录成功 GET 事件。
- 写入模式执行现有完整页面/资源验收、负向权限矩阵和 export 检查。
- 报告把页面/API 验收整体标为 `audit-log-write-enabled` 和 `database_write=audit-log-only`，不再根据 GET 方法推断零写入。
- 与权限 smoke 使用相同的模式名称、生产确认语义和报告字段。
- 浏览器上下文仅允许同 origin GET；非 GET 或跨 origin 请求在发送前阻断，避免页面行为超出 `audit-log-only` 合同。
- 报告不保存 DOM 正文、heading 文本、console/interaction 原文、URL query/fragment 或失败响应正文；默认关闭截图，避免把医疗信息或 token 写入本地产物。

### 4.3 前端验收门禁

文件：`scripts/run-production-frontend-acceptance-gate.mjs`

- 默认门禁不启动 runner，并在缺少写入授权时失败关闭；阻断发生在任何生产网络动作前。
- 写入模式门禁要求完整负向矩阵及 export 结果存在，并要求 `database_write=audit-log-only`。
- route 覆盖按 runner 导出的 profile 精确校验 `route × viewport` 集合，不接受只满足数量的替代路由；每项还必须包含成功 HTTP status、无 navigation/console/request/interaction 错误、可读正文/heading 度量和空 issues，gate 从 checks 重新确认 P0/P1 为零。
- 模式和报告内容不一致时失败关闭。

## 5. 测试与验证

在 `tests/knowledge_query/test_scripts.py` 及现有相邻脚本测试中覆盖：

1. 权限 smoke 默认模式仅执行 2 个公共 probe，并逐项报告其余 33 个 skipped 候选。
2. `--allow-audit-log-writes` 恢复匿名、缺失租户和管理员 probe，并输出真实副作用标签。
3. 任意目标写入模式缺少正确确认值时，在网络访问前失败；redirect 不得被跟随。
4. 前端验收和 gate 缺少写入授权时在任何浏览器/网络动作前失败关闭。
5. 前端写入模式包含完整页面和 API 检查并使用 `audit-log-only` 标签。
6. 门禁拒绝模式与报告字段不一致、缺少 skipped 明细或把未执行项标成通过的结果。
7. 参数、报告和日志不包含 secret。
8. 前端 gate 拒绝伪造 route 集合，报告 sanitizer 不持久化 sentinel PII/token。

实现完成后执行聚焦测试、相关脚本测试、Ruff、Mypy、Node 语法检查和差异检查；代码审查必须确认没有通过改标签掩盖真实请求。

## 6. 发布与部署顺序

1. 从 `origin/main@2d790375621bafa3dd564b1a1464f3e229a053a2` 的干净分支实施并验证。
2. commit、push、创建 PR、转为 Ready，完成 merge 审查后 merge；不删除远端分支。
3. 在全新同步的 clean `main` 上确认部署 SHA 与 merge SHA 一致。
4. 运行严格零执行 preflight；部署时不启用 schema、回填、provider、review/query 写入参数。
5. 执行备份、同步、构建、重启，并以脚本最终退出状态作为部署执行证据。
6. 部署后先运行严格状态检查和有限真只读权限 smoke；任何 GET-only 工具只有在代码路径确认不调用 `record_operation` 后才能标 L3。
7. 完整前端验收与完整权限矩阵使用已授权的审计日志写入模式；其结果单列为 L4 `audit-log-only` 生产副作用，不与只读证据混写。

证据等级保持分离：本地测试/preflight 为 L2，生产只读检查为 L3，已授权部署及审计日志写入验收为 L4。

## 7. 回滚与失败处理

- 脚本改动回滚：回退本 PR，不触碰已经产生的生产审计日志。
- 部署失败：停止后续验收，保留备份、部署日志、目标 SHA 和运行时 SHA；按现有部署脚本的回滚流程恢复上一运行版本。
- 部署成功但只读验收失败：不得宣称生产验收完成；保持运行事实与验收事实分开，先定位失败原因。
- 写入模式确认门禁失败：不降级绕过，不发送相关请求。

## 8. 非目标

- 不修改业务 API、权限策略、审计日志持久化或数据库 schema。
- 不删除、回填或改写既有审计日志。
- 不执行 provider call、live send、review/query 写入或 SQL 写入。
- 不删除远端分支。

## 9. 验收标准

- 默认权限 smoke 只执行 2 个已确认安全的公共 GET，明确列出 33 个 skipped 项，并且 `database_write=false`。
- 默认前端验收在任何浏览器/网络动作前失败关闭，不产生虚假的“只读前端验收通过”报告。
- 写入模式必须双重显式授权，且报告为 `database_write=audit-log-only`。
- 自动化测试能够在请求发出前验证生产确认门禁，并能检测报告标签与实际 probe 集合不一致。
- 合并后仅从 clean `main` 部署精确 merge SHA；部署和生产验收分别提供新鲜证据。
