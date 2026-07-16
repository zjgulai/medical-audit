---
title: Loop 59 生产就绪排查与最后冲刺执行方案
doc_type: analysis-draft
module: release
status: active
created: 2026-07-16
updated: 2026-07-17
owner: self
source: repository+production-readonly+playwright
---

# Loop 59 生产就绪排查与最后冲刺执行方案

## 1. 执行结论

当前部署决策为 **NO-GO**。生产现网仍可用，Batch A 本地 P1 已关闭；下一步是 Batch B clean exact-SHA 回归、manifest 与全页截图审阅，不应直接 Ready、merge 或 deploy。

| 问题 | 当前结论 | 证据层级 | 把握 |
|---|---|---|---|
| 是否可以继续部署 | 否；先完成 candidate exact-SHA 再冻结、首次迁移完整性、fresh S0、release manifest 和全页验收 | L2 candidate + fresh L3 read-only | 高 |
| 当前生产是否可用 | 是；当前运行 `main@1376baef0d8d47f1e1ef60b2cec130451af5af4f`，核心容器、Nginx、front door、PostgreSQL 和检索后端健康 | fresh L3 read-only | 高 |
| 所有知识库是否正常 | 否；核心医疗检索可用，但 25 个注册集合中只有 5 个有生产数据，真实问答/引用质量未做本轮 L4/provider 验收 | fresh L3 read-only + repository contract | 高 |
| 100+ 智能体是否正常 | 否；304 是历史持久化行，只有 13 active、7 个 distinct template、7 个曾被调用的 agent key，并存在 3 个重复 identity group | fresh L3 read-only SQL | 高 |
| 所有页面是否达到一致且专业 | 尚未证明；Batch A 已关闭已知移动端 P1 并通过本地 60/60 结构矩阵，但生产仍是旧 SHA，exact-SHA 全截图和真实数据/鉴权态验收尚未完成 | local L2 + fresh L3 production identity | 高 |

这不是当前生产故障结论。`NO-GO` 针对的是“把 Draft PR #239 候选继续推进到生产”的决策。

## 2. 证据边界

- Candidate：Batch A 从 base `846aa89187867339feb6d6c90c102ca1336e4105` 开始本地原子冻结；exact candidate SHA 必须在计划组 commit 后外部读取。Draft PR `#239` 尚未更新；未 push、未 merge、未 deploy。
- Production：marker `1376baef0d8d47f1e1ef60b2cec130451af5af4f`，仍为 legacy static topology，不是候选的 versioned-release topology。
- Fresh L3 deployment-state audit：审计日志 `56,347 → 56,347`，fingerprint 不变，unique auditor events `0 → 0`，GET-only，`database_write=false`。
- Fresh production SQL：`SERIALIZABLE READ ONLY DEFERRABLE`，`transaction_read_only=on`；未执行 SQL 写入。
- 本轮没有重新运行 authenticated production frontend acceptance；该流程会写 audit log，证据等级是 L4 `audit-log-only`，需要独立授权。
- 60 次新鲜 Playwright 页面执行使用真实生产静态页面，但本地拦截全部 `/api/v1/**`；它证明页面结构，不证明带真实数据的交互状态。
- 一次未带 tenant 的 catalog GET 返回 `401`。鉴权拒绝路径可能记录审计事件，因此该单次尝试只能标记 `database_write=unknown`，未重复执行。
- 全局 provider 遥测未观测：`provider_call_status=not_observed`；本次合格 L3 collector 自身为 `collector_provider_call_status=not_called`。

## 3. 生产排查结果

### 3.1 运行与发布完整性

当前运行面健康：

- `medical_audit_app`、`medical_audit_pg`、`medical_audit_clamav`、`ai_video_nginx` 均健康。
- Nginx 配置有效，公网 front door 正常，Web mount 为 read-only。
- PostgreSQL ready；检索后端报告 `49,051` 条匹配 embedding，模型 `kimi-for-coding`，维度 `1024`。

但首次迁移/部署门禁未通过：

- 先前 mandatory S0 collector 在生产 Python 3.10 上因 `from datetime import UTC` 失败；Batch A 已用真实 Python 3.10 fixture capture 关闭本地兼容性，但尚未获得 fresh L3 production S0 证据。
- `/release-manifest.json` 返回 `200 text/html`、`6947` bytes，是 HTML fallback，不是 JSON manifest。
- 生产不存在候选要求的 `current` release target、remote manifest/file set 和 versioned Nginx release route。
- HTML 仍使用旧 `public, max-age=300, must-revalidate` 策略，immutable asset path 未被证明。

结论：现网健康不等于下一次版本化发布已具备可验证的迁移与回滚条件。

### 3.2 知识库

生产有数据的集合仅 5 个：

| collection | documents | embeddings/chunks | active-index embeddings |
|---|---:|---:|---:|
| `medical-insurance-catalog` | 45 | 37,396 | 7,480 |
| `medical-insurance-laws` | 19,784 | 791,602 | 22,770 |
| `personal-materials` | 4 | 4 | 4 |
| `risk-negative-list` | 15 | 165 | 33 |
| `supervision-rules-knowledge` | 206 | 94,121 | 18,768 |
| 合计 | 20,054 | 923,288 | 49,055 |

代码 registry 定义 25 个 source collection；其余 20 个没有生产行。因此必须把两个目标分开：

1. 医保/监管核心检索运行面：当前健康。
2. 全量业务知识域覆盖：尚未完成。

本轮未发送真实问题、未生成引用、未调用 provider；端到端答案正确性、引用完整性和权限隔离仍需独立 L4/business UAT。

### 3.3 智能体

- 原始 prompt source 有 169 行、132 个 unique category-title pair；它不是已发布 catalog。
- 候选默认 catalog 只有 3 个后端对齐医疗智能体；opt-in extension 再增加 3 个，最大为 6。
- 生产 `audit_agents` 有 304 行：13 active、21 inactive、270 archived。
- 13 个 active row 只覆盖 7 个 distinct template ID。
- 1,707 次 invocation 只覆盖 7 个 agent key；最近一次记录是 `2026-07-09 03:11:54+00`。
- 13 个 active row 聚合后只有 7 个 actor/project/template identity group；其中 3 组重复，共 6 条 excess row，最大重复组为 4。

结论：不能用“304 行历史数据”宣传“100+ 智能体生产正常”。候选幂等修复可以阻止/报告新重复，但不会自动清理现有生产重复数据。

### 3.4 页面布局与专业度

机械基线：

- 历史同生产 SHA 的 L4 acceptance 覆盖 18 routes × desktop/mobile = 36/36；HTTP、导航、console、request、interaction 和 root horizontal overflow 均无 P0/P1。
- 新鲜安全矩阵覆盖 20 routes × 3 viewports = 60/60；无 navigation error、non-200、root horizontal overflow、missing heading 或 page error。
- 249 条 console error 均来自本地强制拦截 API 的 503，不计为生产 API 故障。

定性问题：

- mobile 全局导航占据约 350–420 px 顶部空间，主任务内容普遍被推到首屏以下。
- mobile `/medical-audit` 及 alias 到该页的路由存在内部 tab 横向裁切；按钮右边界达到 `394/490/586/682`，而 viewport 仅 `390`。现有 root overflow gate 捕捉不到这个缺陷。
- mobile `/archive` 卡片和技术字段严重压缩，页面约 5,240 px；`/guided-check` 约 4,745 px；`/knowledge-base` 约 3,338 px。
- “历史对话”浮动按钮在 agent-market、projects、reports、chat 等移动端页面遮挡筛选或内容。
- desktop `/medical-audit` 同时出现全局 sidebar、glyph rail、rule panel，1440 宽度下工作区只剩约 812 px，明显比其他页拥挤。
- archive、analytics、graph、reports 暴露内部/英文技术信息，如 `it-admin / department-head`、`provider_call=false`、API failure 文案和裸 `error`。
- 标准页面、rules、medical-audit、chat 的主内容 left/width 模式差异明显，削弱跨页一致性。
- 空态/错误态大面积留白；视觉语言一致，但尚未达到最终产品精修标准。

总体判断：desktop 可作为候选基线，mobile 仍为发布 NO-GO；带真实数据的 authenticated 视觉质量尚未获得本轮证据。

## 4. 阻断项分级

### P0 — 当前现网故障

- 当前未发现 P0 outage；不得把 legacy topology audit failure 误报为现网不可用。

### P1 — deploy 前必须关闭

- [ ] 修复 release-guard 的 Python 3.10 兼容性，并增加真实 Python 3.10 执行门禁。
- [ ] 在 legacy 生产上取得 fresh S0，确认 migration readiness 精确为 `legacy_ready`；任何 `partial_or_unknown` 停止部署。
- [ ] 设计并 dry-run 生产 active-agent duplicate cleanup；部署候选前明确重复 identity 的保留规则、备份、回滚和 post-check。
- [ ] 修复 mobile `/medical-audit` 内部 tab 裁切，并让视觉验收检测内部 scroll/clip container，而不只检查 root overflow。
- [ ] 修复移动端关键浮层遮挡、archive 可读性和首屏导航占用；关键任务页必须在 390 px 宽度下可完成阅读与操作定位。
- [ ] 冻结知识库发布口径：若本版本承诺 25 个集合全量覆盖，则 20 个空集合是数据发布阻断；若只承诺核心 5 个集合，则 UI、文档和验收必须明确 `partial coverage`。

### P2 — 最终验收前关闭

- [ ] 统一页面 content width、hero、toolbar、filter 和 card spacing token。
- [x] 将 archive/analytics/graph/reports 的内部技术字段改为用户可理解的中文状态，技术细节进入可展开诊断区。
- [ ] 压缩 guided-check/knowledge-base/archive 的移动端纵向密度，建立 section priority 和 progressive disclosure。
- [ ] 收敛空态、错误态、降级态，避免裸 `error`、大面积无解释留白或开发者错误文本。
- [ ] 为全 20 route × 3 viewport 保存 exact-SHA 截图并执行逐页人工 visual sign-off。

## 5. 最后冲刺批次与 TODO

### Batch A — P1 本地修复闭环（已完成，L2）

授权边界：local code/test/docs only；不 push、不改 PR 状态、不 merge、不 SSH、不 deploy、不写生产数据库、不调用 provider。

- [x] A1. 将 collector 的 UTC 处理改为 Python 3.10 compatible 写法；保持 timestamp canonicalization 不变。
- [x] A2. 新增 Python 3.10 container/interpreter compatibility test，证明 capture path 能进入 strict read-only collector。
- [x] A3. 修复 mobile medical-audit tabs、全局 mobile nav、floating history/medical-AI button、collapsed sidebar 和 archive card layout。
- [x] A4. 扩展 Playwright detector：检查关键 tab/button/overlay 的 bounding box、内部 scrollWidth 和遮挡，不只检查 document root。
- [x] A5. 收敛 archive/analytics/graph/reports 技术文案与 error/empty state。
- [x] A6. 编写 agent duplicate cleanup 的只读 inventory 与 dry-run manifest；不得在本 Batch 执行 UPDATE/DELETE。
- [x] A7. 已冻结知识库发布范围为 `core-5`，并用动态 `populated / registered` coverage label 区分 `core-ready / core-incomplete / unknown`；不宣称 `full-25`。

完成标准：focused tests、Ruff、targeted Mypy、Web Vitest/typecheck/lint/build、3-viewport matrix、`git diff --check` 全绿；accepted P0/P1=`0`。

Batch A closure：已满足上述本地标准；Python related `319`、Web `363`、non-regression `11`、24-page build 与最终 `20 routes × 3 viewports = 60/60` structural matrix 全绿。证据等级保持 `L2-fixture-or-dry-run`，不等于 production 验收。

### Batch B — exact-SHA release candidate 再冻结（L2）

- [ ] B1. 从 clean candidate exact SHA 重跑后端、前端、release-guard、non-regression 和 deployment tests。
- [ ] B2. 生成并校验 release manifest；所有文件 hash、candidate SHA、app metadata 和 static source identity 一致。
- [ ] B3. 运行 17 independent pages + 3 aliases × 3 viewports，全 60 execution 生成唯一 PNG。
- [ ] B4. 对每个 route 记录 desktop/tablet/mobile 的视觉结论，不以自动化零 overflow 替代人工专业度判断。
- [ ] B5. 独立审阅 accepted P0/P1=`0` 后，形成可审阅的 atomic commit manifest。

### Batch C — PR promotion（独立授权）

- [ ] C1. push local candidate，更新 Draft PR #239 的 exact head、证据摘要和回滚说明。
- [ ] C2. 等待/完成独立 review；确认 mergeability 与 checks，不能把“无 checks”写成 PASS。
- [ ] C3. 分别取得 Ready 与 merge 授权；不得用已有“自动授权”跨越这两个外部状态门。

### Batch D — production preflight / S0（L3，独立只读授权）

- [ ] D1. 在 current legacy production 运行修复后的 S0 collector；要求 SSH exit `0`、Python 3.10 compatible、`transaction_read_only=on`。
- [ ] D2. topology 必须分类为 `legacy_ready`，并证明无 `.deploy-sha.next`、partial release、symlink/file 异常或未知 residue。
- [ ] D3. 运行 deploy preflight；显式使用首次 legacy migration flag，验证磁盘、备份路径、Docker/Nginx、app rebuild 和 rollback target。
- [ ] D4. S0 保存 schema、business、audit、object-ledger 和 topology fingerprints；`provider_attempt_made=false`。

### Batch E — versioned deploy（L5，必须再次明确授权）

- [ ] E1. 仅从 clean `main == origin/main == approved_sha` 执行。
- [ ] E2. 先完成 app/env/db/nginx/web 备份并校验可读性；冻结 rollback stamp。
- [ ] E3. 执行 app rebuild、versioned static release、Nginx switch、manifest 与 marker 更新；禁止 `--skip-app-rebuild`。
- [ ] E4. 任一 build、health、manifest、Nginx 或 marker 不一致立即停止并按 frozen target 回滚。

deploy script exit `0` 只允许标记 `deployed_pending_l3`，不能标记生产验收完成。

### Batch F — post-deploy S1 / L3（部署授权内的只读验证）

- [ ] F1. 捕获 S1；证明 S0→S1 schema/business/object-ledger zero delta。
- [ ] F2. 证明 marker、`current`、manifest、app deploy SHA、public asset hash 和 Nginx target 全部等于 approved SHA。
- [ ] F3. 运行 conditional L3 deployment-state audit；audit count/fingerprint 和 unique auditor identity 必须不变。
- [ ] F4. 通过后仅升级为 `deployed_l3_verified`。

### Batch G — authenticated production acceptance（L4 `audit-log-only`，独立授权）

- [ ] G1. 为该 run 捕获 exact S1 zero baseline，使用唯一 run ID/user。
- [ ] G2. 执行完整 permission matrix 与 20 route × 3 viewport frontend acceptance；保存全部截图。
- [ ] G3. 捕获 S2；证明 S1→S2 只有该 run 可归因的 audit-log delta，无 schema/business/object/topology delta。
- [ ] G4. 逐页人工 visual sign-off，覆盖真实 populated/empty/error/permission states。
- [ ] G5. 通过后才可标记 `release_accepted_l4`。

### Batch H — 独立业务与数据激活 lane（不与 app deploy 合并）

- [ ] H1. Knowledge UAT：真实 query、citation、permission、provider quality；单独授权 query-history write 和 provider call。
- [ ] H2. Agent cleanup：生产 DB backup、dry-run identity manifest、显式 UPDATE/DELETE 授权、rollback/post-check。
- [ ] H3. Agent execution UAT：按 default/extension/custom 分层抽样，不用“100+ 全部正常”作无法验证的 blanket claim。
- [ ] H4. Missing collection activation：对 20 个空集合逐个确认来源、授权、导入、索引、质量评估和回滚；它是数据项目，不是普通应用部署步骤。
- [ ] H5. 若目标确实是 100+ approved agents，先建立 template registry、版本/权限/owner/测试/退役治理，再分批上线，不直接复活 304 条历史行。

## 6. 停止与回滚条件

- S0 不能在生产 Python 3.10 完整运行，立即停止。
- topology 为 `partial_or_unknown`、存在 residue、backup 不完整或 rollback target 不唯一，立即停止。
- candidate、PR head、merge SHA、build SHA、manifest、app SHA 或 public SHA 任一不一致，立即停止。
- 任何非预期 database/object/schema/business delta、provider attempt、live send 或 audit attribution 不唯一，立即停止并保留原始证据。
- 移动端关键路由仍有裁切、遮挡或不可读内容，不进入 PR Ready。
- agent duplicate cleanup 与 app deploy 不在同一事务/授权中执行；cleanup 失败不得通过 app rollback 伪装恢复。
- 20 个空知识集合未经来源与质量验收，不以创建空 catalog card 方式宣称已上线。

## 7. 最终完成定义

只有同时满足以下条件，才允许宣布“最后冲刺完成”：

- candidate exact SHA 的 L2 全量门禁和 60/60 all-screenshot matrix 通过；人工视觉 P0/P1=`0`。
- legacy→versioned migration 的 S0、备份、rollback 和 preflight 证据完整。
- 经独立授权完成 deploy，S1 L3 证明身份一致且 business/schema/object zero delta。
- 经独立 L4 `audit-log-only` 授权完成真实 authenticated 页面与权限验收，S2 delta 唯一可归因。
- 知识库只能按实际覆盖范围声明；真实问答/provider UAT 未执行时不得声称答案质量已验收。
- 智能体按 active/template/invoked 三层报告；重复数据已单独治理，未建设 100+ approved registry 前不得声称 100+ 正常上线。

## 8. 当前边界标签

- `production unchanged`
- `deploy_execution=false`
- fresh qualified L3 collector：`database_write=false`
- one unauthenticated catalog denial attempt：`database_write=unknown`
- `provider_attempt_made=false`
- `provider_call_status=not_observed`
- `collector_provider_call_status=not_called`
- `live_send=false`
