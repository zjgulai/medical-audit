---
title: 重构站上线前收敛门禁方案
doc_type: release-plan
module: frontend
created: 2026-07-05
updated: 2026-08-13
owner: self
source: human+ai
project: medical_audit
created_at: 2026-07-05
status: superseded
scope: frontend-ai-replica-release-convergence
branch: codex/frontend-ai-replica-20260703
evidence_level: L1-local-runtime
production_write: false
provider_call: false
database_write: false
deploy_execution: false
---

# 重构站上线前收敛门禁方案

## 第一性原理

当前产品要解决的不是“页面是否好看”，而是“审计人员能否在可信、稳定、可解释的系统里完成工作”。因此上线前的最小事实单元不是某个组件通过，而是五个闭环：

1. **入口可信**：登录、导航、页签、返回、关闭都可逆，不丢上下文。
2. **页面可信**：每个主页面都有清晰任务、状态和下一步动作，避免文字堆积和后台术语。
3. **数据可信**：本地样例、后端只读、真实写入、生产数据四种状态必须可区分。
4. **合同可信**：前端按钮背后的 API、错误态、权限态和副作用边界必须明确。
5. **发布可信**：合并、部署、生产只读检查、生产写入必须分层授权，不能用本地通过替代生产可用。

## 当前事实

- 当前分支：`codex/frontend-ai-replica-20260703`。
- 当前 HEAD：`716ccd22 feat(kb): expand source taxonomy retrieval boundary`。
- 已收敛的本地提交链：`4fcc0ba2` 前端 replica shell、`c9742ab0` API contract boundary、`716ccd22` KB source taxonomy/retrieval boundary。
- 当前工作区：业务代码主 lane 已提交，剩余 dirty tree 主要是计划、草稿和运行输出产物。
- 当前 dirty tree 快照：`273` 个 git status 条目，其中 tracked modified `4` 个、untracked entry `269` 个；`.kiro/plan` 文件 `39` 个，`drafts/analysis` 文件 `282` 个。
- 输出产物快照：`output` 约 `45M`、`web/output` 约 `231M`、`web/web` 约 `8.6M`，三类目录合计 `1082` 个文件；这些属于本地证据或误置产物，默认不进入发布提交。
- 已有本地交互证据：重构站曾完成 29 条显式交互和标准 Playwright E2E。
- 已有合同缺口证据：33 个前端 API contract 中仍有 response schema、字段差异、legacy route 和 product template ownership 待收敛。
- 本轮边界：只做本地计划、清单和验收；不 merge、不 deploy、不写生产、不调用 provider、不写数据库。

## 证据门禁

| 层级 | 允许结论 | 禁止越级结论 | 本轮动作 |
| --- | --- | --- | --- |
| L0-unverified | 仅能作为待查假设 | 不能说完成 | 不使用 |
| L1-local-runtime | 本地页面/脚本通过 | 不能说生产已更新 | 跑本地 prodlike smoke |
| L2-fixture-or-dry-run | fixture 或 dry-run 可用 | 不能说真实业务写入可用 | 仅记录待办 |
| L3-production-read-only | 生产只读可观察 | 不能说已发布新版本 | 需另行授权 |
| L4-authorized-live | 已授权且有 live side effect 日志 | 不能事后补授权 | 本轮不触发 |

## 完整解决方案

### A. 分支与文件治理

目标：避免重构站和旧页面、KB 后端、生产脚本互相污染。

- 生成当前变更清单，按 `frontend_replica`、`api_contract`、`kb_backend`、`tests`、`plans_docs`、`outputs`、`other` 分类。
- 标出混合风险文件，例如 `web/src/lib/api-client.ts`、`package.json`、`web/package.json`。
- 后续合并必须以清单为准做 patch-level staging，不使用 `git add .`。

### B. 全站本地 prodlike 验收

目标：先证明当前分支在本地生产式启动下可运行。

- 跑 `corepack pnpm --filter medical-audit-web smoke:prodlike`。
- 期望覆盖：`next build`、`next start`、29 条交互流程、Playwright E2E。
- 若有未通过项，按面向拆分：构建、路由、交互、视觉/溢出、测试断言漂移。

### C. UI/UX 收敛

目标：从“AI 味的功能堆叠”收敛到“政务审计工作台”。

- 默认页面只保留任务、关键状态、核心动作；解释性文案进入 hover、抽屉或详情。
- 左侧导航和页面标题保持一致的图标、字号、行高和视觉节奏。
- 文档检索、知识库、智能体、项目管理、底稿报告等页面补足官方质感：细线纹理、低饱和蓝灰底、业务图标、克制插图。
- 对每个页面保留一个主 CTA，次级操作降权，避免横向栏堆叠。

### D. 交互闭环

目标：所有按钮都要有可解释结果，不出现“点了没反应”。

- 每个主导航页面至少验证：进入、主按钮、搜索/筛选、弹层或详情、关闭/返回。
- 创建类动作在真实后端接入前保持本地门禁，不伪装成已写入。
- 历史对话、智能体详情、知识库详情、文档结果、报告生成、项目新增要有最小闭环。

### E. 前后端合同

目标：把 UI 演示闭环升级为真实产品闭环的可执行路线。

- P0 保持当前 fixture/read-only 清晰标识。
- P1 补齐 response schema、typed rejection、权限拒绝、空态和分页。
- P2 迁移 legacy review-task/report/rectification 到 `/api/v1` contract。
- P3 决定 product templates ownership：前端 fixture、后端 config、DB-backed catalog 三选一。

### F. 生产前发布门禁

目标：避免再出现“本地最新 UI 与生产 UI 不一致”的问题。

- 合并前：dirty tree 清单、patch-level staging、lint/typecheck/test/build/prodlike smoke。
- 部署前：deploy plan、rollback point、静态资源版本戳、生产只读 smoke 清单。
- 部署后：生产首页、登录页、AI 对话、侧栏导航、知识库数字、文档检索、智能体、项目管理、底稿报告只读验收。

## TODO List

### P0 本轮立即执行

- [x] 复核分支、规则和历史证据边界。
- [x] 生成当前 dirty tree 分类清单。
- [x] 复核已有本地 prodlike smoke 证据。
- [x] 明确输出目录治理边界：保留证据，不直接提交，不在无授权情况下删除。
- [ ] 形成 docs-only 发布收敛门禁提交。

### P1 下一批修复

- [ ] 修复全站 smoke 中暴露的 P0/P1 缺口。
- [ ] 对页面顶部横向信息栏做二次减负：只保留当前模块、项目状态、权限状态。
- [ ] 对每个主页面建立按钮交互矩阵：点击、跳转、关闭、返回、空态、错误态。
- [ ] 补齐登录安全提示、历史对话恢复、知识库详情、文档检索结果详情。

### P1 文件治理

- [ ] 对 `.kiro/plan` 做单独 review：只保留当前分支仍有决策价值的计划文件。
- [ ] 对 `drafts/analysis` 做批量索引：以 topic/date/status 归类，后续按“提交、归档、保留本地”三类处理。
- [ ] 对 `output/` 与 `web/output/` 建立证据留存规则：关键报告转入 draft 或 tmp，截图/trace 默认本地留存。
- [ ] 对 `web/web/` 做误置产物确认：先核对内容来源，再在获得清理授权后删除或归档。
- [ ] 评估 `.gitignore` 是否增加 `output/`、`web/output/`、`web/web/`；该配置变更应单独提交，不能混入产品代码。

### P2 合同与集成

- [ ] 为 25 个缺失 response schema 的 endpoint 补 compatibility schema 或正式 response model。
- [ ] 对 `TableAnalysisUploadResponse` 和 `AgentPromptVersionCreateRequest` required/optional 差异做合同决策。
- [ ] 为 legacy review-task/report/rectification 设计 `/api/v1` contract。
- [ ] 建立 fullstack E2E 与 production read-only smoke 的分层脚本入口。

### P3 发布准备

- [ ] 形成 patch-level merge manifest。
- [ ] 合并前跑全量本地验证。
- [ ] 获得明确 merge/deploy 授权后执行部署。
- [ ] 部署后执行 production read-only 验收，不把只读验收说成生产写入成功。

## 本轮停止线

本轮只到 `L1-local-runtime` 和 docs-only 收敛门禁。若本地 prodlike smoke 存在未通过项，先修复本地缺口；若通过，也只能声明“当前分支具备本地生产式验收基线”，不能声明“生产环境已更新”。
