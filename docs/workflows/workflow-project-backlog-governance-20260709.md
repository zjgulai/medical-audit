---
title: medical_audit 当前产品形态与项目治理待办收敛方案
doc_type: workflow
module: project-governance
status: active
created: 2026-07-09
updated: 2026-07-09
owner: codex
source: production-readonly+local-git-inventory
---

# medical_audit 当前产品形态与项目治理待办收敛方案

## 1. 当前已核验事实

- 生产环境已部署到 `main@d6ae4c191453b0e5619d451cb26b41e3aeb68bee`。
- 生产容器状态：`medical_audit_app`、`medical_audit_pg`、`medical_audit_clamav` 均为 healthy。
- 生产前端验收已覆盖 18 条路由、桌面/移动 36 项检查，`P0=0`、`P1=0`。
- 当前公网产品形态是 `AI审计一体化协作平台`，主要入口包括 `/login`、`/chat`、`/agent-market`、`/knowledge-base`、`/documents`、`/graph`、`/medical-audit`。
- 生产磁盘 `/` 使用率约 `95%`，剩余约 `15G`，主要风险来自多轮部署备份保守保留。
- 本地根目录 `/Users/pray/project/medical_audit` 不是可开发基线：本地 `main` 落后 `origin/main` 81 个提交，且存在 367 条未收敛变更。
- 当前本地 worktree 共 43 个，其中 4 个 prunable、15 个 detached、28 个 branch worktree。
- GitHub 当前开放 PR 仅 `#186 docs: add medical_audit governance manifests`，状态 `OPEN/CLEAN`，但内容基于 2026-07-06 的治理快照，已经落后于当前生产事实。

## 2. 当前未完成事项分层

### P0：生产与项目治理安全线

1. **生产备份与磁盘治理**
   - 状态：未完成。
   - 当前风险：磁盘 95%，继续部署会持续产生 DB/app/web/nginx/env 备份。
   - 下一步：先生成 `/opt/medical-audit/backups` manifest，按 stamp、大小、最近成功部署、最近 3 天保留窗口分组；删除需要单独授权。
   - 验收：磁盘空间恢复到可持续区间，且 `medical_audit_*` 容器保持 healthy。

2. **本地根目录脏树收敛**
   - 状态：未完成。
   - 当前事实：367 条变更，分组为 `.kiro=20`、`drafts=298`、`docs=4`、`repo-config=2`、`scripts=5`、`src=9`、`tests=7`、`web=19`、`output=1`、`other=2`。
   - 下一步：禁止在根目录继续开发；用 clean `origin/main` worktree 做开发，根目录只做 manifest 和归档决策。
   - 验收：每组都有 `keep / archive / migrate / discard-candidate` 结论，不混合提交。

3. **worktree 与历史分支治理**
   - 状态：未完成。
   - 当前事实：43 个 worktree，已明显超过可管理规模。
   - 下一步：先清理 4 个 prunable worktree 元数据；对 detached deploy worktree、已合并热修复分支、历史 UI 恢复 worktree 做保留/移除建议。
   - 验收：保留集只包含根目录、当前 clean main、活跃后端/知识库开发 worktree 和必要历史恢复点。

4. **PR #186 治理文档去重**
   - 状态：未完成。
   - 当前判断：不建议原样合并，因为它的事实基线落后于当前 `d6ae4c19` 生产状态。
   - 下一步：吸收其中有价值的 manifest 结构，更新为当前 SHA、当前 worktree 数、当前生产磁盘与当前合同状态后再决定合并或关闭。
   - 验收：GitHub 只保留一个最新治理 PR，不再同时维护过期治理 PR。

### P1：产品核心闭环

1. **医保审计 `/medical-audit` 生产流程闭环**
   - 状态：部分完成，仍需后端流程闭环。
   - 缺口：数据导入、规则选择、疑点生成、人工复核、底稿归档、报告导出、整改跟踪之间还需要统一状态机和 API 合同。
   - 下一步：优先冻结实体和流程：`audit_project -> import_batch -> rule_run -> finding -> review_task -> dossier/report -> remediation`。
   - 验收：用户能从专题入口完成一条最小审计样例的创建、复核、归档闭环。

2. **知识库 `/knowledge-base` 内容联通**
   - 状态：首批已接通，仍需产品化和指标口径冻结。
   - 缺口：后端 source collection、前端产品分类、文档数、片段数、embedding 数、最后同步时间之间还需要稳定映射。
   - 下一步：以 `docs/api/frontend-backend-page-contract.json` 为入口，补充每个分类的真实数据来源和空态/fallback 规则。
   - 验收：页面每个分类卡片都能说明“来自哪个 source_collection、多少文档、多少片段、何时同步”。

3. **文档检索 `/documents` 操作闭环**
   - 状态：首批已接通，仍需上传、治理、预览、引用闭环。
   - 缺口：搜索、上传历史、权限、治理结果、引用预览之间的用户路径还需要打通。
   - 下一步：优先做只读路径闭环，再做上传写入路径最小样例。
   - 验收：搜索结果可打开引用来源；上传后能进入治理/索引状态，而不是只显示入口。

4. **知识图谱 `/graph` 从只读工作台到真实关系图**
   - 状态：首批接通，但仍可能存在 seed/只读工作台成分。
   - 缺口：法规、规则、疑点、证据、报告之间的边类型和节点来源尚未冻结。
   - 下一步：不引入图数据库，先从现有 PostgreSQL/知识库/疑点数据生成只读关系视图。
   - 验收：任一节点能追溯到真实文档、规则或疑点记录。

5. **AI 对话 `/chat` 模型与附件能力**
   - 状态：页面能力已进入生产，但 provider 配置与附件分析链路仍需运营化。
   - 缺口：`kimi-2.7`、`deepseek-v4-pro` 的生产环境别名映射、不可用提示、query history 与附件分析成本边界。
   - 下一步：先做模型可用性只读检查和错误口径，再决定是否启用真实 provider。
   - 验收：模型不可用时不写入 query history；模型可用时能记录 model alias、引用和调用状态。

6. **智能体广场与我的智能体**
   - 状态：100+ 智能体与分类已上线，但仍需安装、收藏、调用一致性验证。
   - 缺口：安装后的“我的智能体”、`@` 调用、`/` 调用和聊天页上下文传递需要持续 E2E 覆盖。
   - 下一步：把智能体安装、收藏、进入 chat、携带 agent 参数作为生产前端验收扩展项。
   - 验收：安装任一智能体后，能在 `/chat` 中选择并发起带 agent 的知识库查询。

### P2：工程债务

1. **前后端合同冻结**
   - 当前文件：`docs/api/frontend-backend-page-contract.json`。
   - 缺口：所有页面标为 `connected_first_batch` 容易掩盖“真实 DB / persistent store / backend seed / frontend static / ui shell only”的差异。
   - 下一步：增加 `data_source_grade` 字段，并要求每个页面列出读接口、写接口、空态和生产验收方式。

2. **生产验收脚本扩展**
   - 当前状态：18 路由 36 检查通过。
   - 缺口：更多点击交互、弹窗关闭、分页、安装、上传、引用预览等动作仍未全部纳入脚本。
   - 下一步：扩展 `scripts/run-production-frontend-acceptance.mjs` 的 hardened profile，不把文本存在当作唯一验收。

3. **文档债务清理**
   - 当前风险：`drafts/analysis` 历史知识库和 UI 方案草稿过多，根目录仍有 298 条草稿变更。
   - 下一步：按 `obsolete / superseded / active / promote-to-docs` 四类标注，不直接删除。

4. **旧路由和兼容层退休**
   - 当前风险：`/pages/*` legacy compatibility、旧 Jinja 模板、Next 静态路由和后端模板同时存在。
   - 下一步：先观测访问日志和生产 acceptance，再分阶段关闭 legacy pages。

## 3. 推荐执行顺序

### 第一批：治理和安全收口

- [x] 建立当前项目未完成任务与治理方案文档。
- [ ] 生成生产备份 manifest 和磁盘占用报告。
- [ ] 生成根目录脏树 manifest。
- [ ] 生成 worktree 保留/移除建议。
- [ ] Review PR #186，给出合并、重写或关闭建议。

### 第二批：核心产品闭环

- [ ] `/medical-audit` 冻结实体状态机和 API 合同。
- [ ] `/medical-audit` 接通一条最小真实样例流程。
- [ ] `/documents` 完成检索、引用、上传治理、预览闭环。
- [ ] `/knowledge-base` 冻结分类和指标口径。
- [ ] `/graph` 以现有 DB 生成最小关系图。

### 第三批：AI 与智能体闭环

- [ ] `/chat` 模型别名生产可用性检查。
- [ ] 附件分析链路最小样例。
- [ ] 智能体安装、收藏、`@` 调用和 `/` 调用的 E2E 验收。

### 第四批：收敛和部署

- [ ] 扩展生产前端验收到关键点击动作。
- [ ] 清理 legacy route 的访问和退休计划。
- [ ] 合并阶段 PR。
- [ ] 从干净 `main` 部署生产。
- [ ] 执行生产 smoke、frontend acceptance、关键页浏览器截图验收。

## 4. 本批执行边界

- 本批只做项目治理方案和清单化，不改业务页面。
- 本批不删除备份、worktree、草稿或历史分支。
- 本批不写生产数据库。
- 本批不部署生产，因为本批新增的是治理文档，不影响运行时产品。
- 后续任何生产备份删除、Docker 清理、legacy route 退休、数据库写入，都需要单独授权。
