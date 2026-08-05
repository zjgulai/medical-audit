---
title: 前后端对抗式审查与执行计划
doc_type: audit-plan
module: frontend-backend
status: draft
created: 2026-07-08
updated: 2026-07-08
owner: codex
source: local-audit
---

# 前后端对抗式审查与执行计划

## 事实基线

- 本地 `main` 落后 `origin/main` 47 个提交，且工作区存在大量历史变更；不能作为直接生产发布基线。
- 前端已存在生产构建能力，`web:build` 可生成静态页面。
- 知识库、文档、智能体、项目、疑点等页面已经有部分 API 调用；图谱、规则、整改、归档页面仍以只读工作台接口和种子数据为主。
- `docs/api/frontend-backend-page-contract.json` 曾保留 `/api/v1/documents/source-collections`，当前前端与后端实际可用接口以 `/api/v1/documents/permissions`、`/api/v1/documents/uploads` 和检索接口为准。

## 对抗式审查结论

### P0：证据语义不一致

问题：图谱、规则、整改、归档页面把 `Readonly*Seed` 后端工作台显示为“后端已连接”，容易让用户误以为数据来自持久业务库。

本轮处理：

- 增加 `workbench-evidence` 分类函数。
- 将 `Readonly*Seed` 标识为“后端种子数据”。
- 将 `portal-data-static-fallback` 标识为“本地样例兜底”。
- 仅把非种子且 ready 的 store 标识为“持久后端”。

### P0：合同文档滞后

问题：合同文档残留不存在的 `document-source-collections` 接口，会误导下一阶段知识库接入。

本轮处理：

- 从知识库页和文档检索页合同中移除该接口。
- 保留当前真实入口：`documents/permissions`、`documents/uploads`、`query/logs` 和 `search-backend`。

### P1：页面交互与数据闭环不完整

仍需处理：

- `/workspace`：指标仍需要从项目、疑点、文档和查询历史聚合。
- `/agent-market`：需要确认安装、收藏、详情是否全部持久化。
- `/fund-compliance`、`/guided-check`：专题表单和交互仍需后端任务、表单模板、复核记录支撑。
- `/graph`：需要从知识库文档、引用、疑点、整改记录生成真实关系图，而不是只读种子拓扑。

### P1：工程治理债务

仍需处理：

- 当前工作区脏变更过多，需要按前端、KB 后端、文档草稿、输出产物分组收敛。
- 新增或变更文件必须进入干净分支后再 PR，避免再次把旧页面与重构页面混合。
- 生产发布必须从干净 `main` 或 release branch 执行，禁止从脏根目录直接发布。

### P2：文档债务

仍需处理：

- 页面到 API 的合同需要补充 `store.backend`、`evidence_grade`、`write_path` 和验收方式。
- 生产验收记录需要区分本地构建、生产只读、浏览器验收和授权写入。

## 执行 TODO

### 已执行

- [x] 抽出工作台证据分类函数。
- [x] 图谱、规则、整改、归档页面区分种子数据、兜底数据和持久后端。
- [x] 图谱页增加数据来源证据面板。
- [x] 更新页面测试断言，避免把种子数据当作持久联通。
- [x] 增加 `workbench-evidence` 单测。
- [x] 更新前后端合同文档，移除不存在接口。
- [x] 通过前端单测、类型检查、lint 和构建。

### 下一批 P0

- [ ] 从干净 `origin/main` 新建治理分支，按 manifest 只带入本轮前端证据修复和必要文档。
- [ ] 对 `/workspace` 建立真实数据聚合合同，明确指标来源和 fallback。
- [ ] 对 `/graph` 设计最小真实关系 API：知识库文档 -> 引用片段 -> 疑点 -> 整改 -> 报告。
- [ ] 对 `/agent-market` 安装与收藏动作增加后端验收用例。

### 下一批 P1

- [ ] 给 `/fund-compliance` 接入专题项目、表单模板、复核状态和附件记录。
- [ ] 给 `/guided-check` 接入规则运行、材料核验和证据引用。
- [ ] 将 `frontend-backend-page-contract.json` 扩展为每页一条验收矩阵。

## 部署门禁

- 当前本地工作区不满足生产发布门禁：`main` 落后远端且包含大量未分组变更。
- 本轮只完成本地开发、测试和构建闭环；生产部署需要先完成干净分支、PR、merge 和 release preflight。

## 验收记录

- `pnpm web:test`：12 个测试文件，98 个测试通过。
- `pnpm web:typecheck`：通过。
- `pnpm web:lint`：通过。
- `pnpm web:build`：通过，生成 23 个静态页面。
