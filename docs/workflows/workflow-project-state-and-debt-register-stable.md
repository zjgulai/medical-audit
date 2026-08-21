---
title: AI智能审计管理系统项目状态与债务台账
doc_type: workflow
module: project-governance
topic: project-state-and-debt-register
status: stable
created: 2026-06-14
updated: 2026-08-21
owner: self
source: human+ai
---

# AI智能审计管理系统项目状态与债务台账

## 1. 目的

本台账用于冻结当前项目真实状态，统一识别技术债务、工程债务、产品集成债务、项目管理债务、文档管理债务和脆弱点债务。

任何后续计划、开发、部署和验收，都必须先对齐本台账的事实边界：

- `fixture` 只证明链路，不代表真实医院数据验收。
- `fallback` 只证明引用型答案兜底，不代表生成式模型能力可用。
- 静态 UI 和浏览器本地 state 不代表后端持久化能力完成。
- 只读 smoke 不代表写入型业务流验收。
- 生产健康不代表 V1.0 产品闭环完成。

## 2. 当前状态冻结

### 2.6 2026-08-14 exact-head 交付观察（当前）

本节采用带时间的外部观察。tracked 文档不声明自身 commit SHA，也不保存瞬时 push 状态。

| 维度 | 观察事实 | 证据边界 |
| --- | --- | --- |
| 外部观察时间 | 2026-08-14 22:46（Asia/Shanghai） | GitHub 与仓库外只读审计收据 |
| Draft PR | [#275](https://github.com/zjgulai/medical-audit/pull/275)，base `ccc73e95`，观测 head `4b42b3eab6972d8ce7d870346f13d16f8ef04f79` | `OPEN/DRAFT`、merge state `CLEAN`；review 数量为 0 |
| exact-head CI | Python `1003 passed`；Web `417 passed`；Ruff、Mypy、typecheck、lint、普通/公开壳层构建和文档检查通过 | [Actions run 31778904386](https://github.com/zjgulai/medical-audit/actions/runs/31778904386)；只覆盖观测 head |
| 当前本地修复 | fail-closed 默认、manifest 访问模式、21+2 路由分类、只读导航零增量 gate、深链 apply-once、整改异常状态和签发 actor 缓存 | 工作树变更；尚未提交、推送或取得新的 exact-head CI |
| 本地完整回归 | Python `1016 passed, 1 skipped, 5 warnings`；Web `418 passed`；Playwright `17/17`；其余门禁通过 | L2 未提交工作树；唯一 skip 需要本地 PostgreSQL 测试 URL，5 条 warning 来自第三方 SWIG 类型；最近 exact-head CI 不覆盖本轮变更 |
| API 文档 | 112 个规范路径、123 个方法/路径操作逐项列出 | `docs:lint` 从 FastAPI OpenAPI 对账 |
| 生产身份 | `25e1654e0c44ca5cbb2bb42e82debdb40fa6f224` | 2026-08-12 L3 历史只读收据；本门禁未刷新 |
| 生产业务能力 | `not_production_verified` | 候选未部署；业务读取、写入和 Provider 调用保持关闭 |

门禁结论：`4b42b3ea…` 的 exact-head CI 为 `PASS`；仓库外 CodeRabbit CLI review 的 9 项发现触发本地修复门禁。当前工作树不能继承该 CI；Ready、merge、部署和生产验收仍是独立门禁。

状态合同：当前状态段只写带时间的外部观察；后续 commit、push 或 CI 变化不会反向使该观察失真。最新身份必须从 PR、Actions run 和仓库外收据重新解析。

### 2.5 2026-08-14 Draft PR 与文档收口快照（历史：push 前）

以下内容保留本地提交完成、外部 push 发生前的历史快照。当前状态以 2.6 节为准；2.4 及更早章节同样只用于追溯。

| 维度 | 当前事实 | 证据边界 |
| --- | --- | --- |
| 主分支基线 | `main == origin/main == ccc73e95820e39559430e96c01d52c8dfb77a246` | 本地 Git 只读核验 |
| Draft PR | [#275](https://github.com/zjgulai/medical-audit/pull/275)，base `ccc73e95`，head `cc711fdb4dc2b36d2b5de705939a7726917960f1` | `OPEN`、`DRAFT`、`MERGEABLE/CLEAN`；尚无 code review |
| exact-head CI | Python `1001 passed`；Web `417 passed`；Ruff、Mypy、typecheck、lint、普通/公开壳层构建和文档检查通过 | GitHub Actions run `31768924010`；只覆盖 `cc711fdb` |
| 当前本地提交 | OpenAPI 覆盖门禁、只读导航 API 请求门禁、整改可见性分页和状态文档同步 | 1 个原子提交，尚未推送；Python `1002 passed, 1 skipped`、Web `417 passed`、Playwright `17/17`，其余本地门禁通过 |
| API 文档 | 112 个规范路径、123 个方法/路径操作逐项列出 | `docs:lint` 从 FastAPI OpenAPI 对账，缺失或陈旧操作均阻断 |
| 生产身份 | `25e1654e0c44ca5cbb2bb42e82debdb40fa6f224` | 2026-08-12 L3 历史只读收据；本门禁未刷新 |
| 生产业务能力 | `not_production_verified` | 未部署候选；业务读取、写入和 Provider 调用保持关闭 |

本门禁处理结果：

- `P1-current-state-document-drift`：本地权威文档已改为区分主分支、PR exact head、本地未推送提交和历史生产观测；PR 正文本身仍需在后续独立 GitHub 写入门禁更新。
- `P1-openapi-documentation-coverage-gap`：本地已补齐逐操作清单，并把方法/路径集合与 FastAPI OpenAPI 纳入 `docs:lint`。
- `P2-readonly-navigation-contract`：已修复。`public-shell-readonly` 导航中只要出现受保护 API 尝试，就记录 P1 并使验收失败。
- `P2-remediation-limit-before-visibility`：已修复。项目可见性进入 SQL 查询后再排序和 `LIMIT`，避免隐藏项目挤占结果窗口。
- `P2-generic-backend-default`：显式接受为受控兼容风险，不将其标记为已修复。现有测试和本地直接启动继续允许 Header 回退；生产 Compose、生产 env 示例和部署脚本必须显式指定 `public-shell-readonly`。责任人为后端/运维维护者；统一 runtime profile 或可信身份上线时重新评估。在新增启动器、编排或部署路径时，如果缺少显式访问模式，发布门禁直接 NO-GO。

当前下一步边界：本地原子提交已经完成；push 与 PR 正文更新仍需独立授权，Ready、review、merge、部署和生产验收继续分别授权。

本地完整回归已经完成。唯一 skip 是本机没有配置 `MEDICAL_AUDIT_TEST_POSTGRES_URL` 的知识统计 PostgreSQL 回归；它不是仓库失败，对应测试已在 PR exact-head CI 的 PostgreSQL service 中通过。5 条 warning 仍来自 `pymupdf==1.27.2.2` 的 SWIG 类型导入。

### 2.4 2026-08-13 全量复盘候选快照（历史）

以下内容保留候选创建日的历史快照。当前状态以 2.5 节为准；2.3 及更早章节同样只用于追溯。

| 维度 | 当前事实 | 证据边界 |
| --- | --- | --- |
| 候选起点 | `main == origin/main == ccc73e95820e39559430e96c01d52c8dfb77a246` | 分支创建时的本地 Git 证据 |
| 候选分支 | `codex/medical-audit-reanalysis-playbook-20260813` | 尚未合并、推送或部署 |
| 生产身份 | `25e1654e0c44ca5cbb2bb42e82debdb40fa6f224` | 2026-08-12 L3 只读收据；不是本次候选部署证据 |
| 源码差异 | `25e1654e..ccc73e95` 没有 `src/`、`web/` 业务源码差异 | 不等于配置、数据和行为完全一致 |
| 本地全栈 | 17 个 Playwright 场景通过；当前合同覆盖 21 个独立页面、2 个兼容跳转和 4 条持久化业务工作流 | 共 27 条功能记录；临时 SQLite、Fake Provider、`provider_call=false` |
| 候选质量 | Python `995 passed`；Web `412 passed`；Ruff、Mypy、typecheck、lint、build 和本地全栈通过 | L2 本地证据；5 条 warning 来自第三方 SWIG 类型 |
| 生产业务能力 | `not_production_verified` | 生产仅允许公开壳层；业务读取和写入关闭 |

本轮候选已经实现生产公开壳层门禁、疑点深链、整改可见性和状态机、报告签发权限、知识统计聚合修复，以及逐功能 Playbook。完整测试仍以候选最终收据为准。

候选收口复审补充修复了两项整改附件鉴权顺序缺陷：父整改项不可见时必须在文件扩展名、文件体或附件存储状态处理前返回 `404`。新增回归先复现 `422/200`，修复后定向测试 `6/6` 通过。

当前阻塞与下一门禁：

- 可信 SSO/OIDC 延期；没有可信身份前，不开放生产业务读取、写入或 Provider 调用。
- merge、push、部署和生产写入均未授权。
- 首批 4 个低风险路径已按用户确认于 14:45 移动到系统 Trash，约 40 MiB；但 16:02 新鲜复核发现 Finder 在 15:10 清空了 Trash，源和 Trash 目标均不存在，因此当前不可恢复。系统日志不能证明触发者。
- 旧工作区的 416 个选定证据文件已归并并通过隔离解包哈希校验；第二批 5 个相互独立目录、约 2.50 GiB 已按确认移动到受管同卷隔离目录。
- Loop 128 及其父仓库约 1.218 GiB 已按确认完成第三批成对隔离：三处 Git 关联元数据已转为相对 worktree 路径，保持同级布局的两个目录已同卷移动到受管隔离目录。
- 两个目录移动前后 inode 和非指针载荷哈希一致；worktree 注册、clean 状态、`fsck`、全部 ref tip 祖先关系、alternates 和候选 Git 状态均通过。父仓库仍通过 alternates 依赖当前候选仓库，并非自包含副本。
- 第二批没有使用系统 Trash；移动前后 inode、全量树哈希和候选 Git 状态一致，精确恢复映射已写入收据。隔离不释放磁盘空间，永久删除仍未授权。
- 第三批同样未使用系统 Trash；原绝对 Git 关联元数据已有 `0700` 本地备份，移动收据记录了成对恢复顺序。隔离不释放磁盘空间，永久删除仍未授权。
- 生产备份没有新鲜隔离恢复证明，删除门禁为 `blocked`。

当前权威入口：

- [文档索引](../README.md)
- [系统架构](../architecture/architecture-system-overview-stable.md)
- [平台 API](../api/api-medical-audit-platform-v1-stable.md)
- [用户 Playbook](../playbooks/user-playbook-medical-audit-v1-stable.md)
- [生产验收矩阵](../testing/production-feature-acceptance-matrix-stable.md)

### 2.3 2026-08-09 Sprint-5 完整基线（历史）

状态口径：本节记录 Sprint-5 在 2026-08-08/09 执行后的完整基线。本地 main 领先 origin/main 1 个 commit（`226d3d0d`），尚未 push；生产仍停留在 Sprint-4 deploy_sha = `484c348f`，尚未部署 sprint-5 内容。

#### 本轮已完成事项（Sprint-5，2026-08-08/09）

**Sprint-5 Batch-A — 整改工作台可操作化**

- `routes_workbench.py`：`remediation_workbench` 返回的 `db_items` 补齐前端字段（`department`/`nextAction`/`evidenceStatus`/`reportNo`/`dueDate`），英文 `status` 映射为中文标签，保留 `status_key` 供门禁和 metrics 计算。
- 新增 `_remediation_status_label` / `_remediation_next_action` 辅助函数和 `_REMEDIATION_STATUS_LABELS` / `_REMEDIATION_NEXT_ACTIONS` 映射字典。
- `api-client.ts`：新增 `updateRemediationItemStatus` + `fetchRemediationItems`。
- `replica-remediation-workbench.tsx`：加入 `StatusActionButtons` 组件，根据 `status_key` 展示下一步操作（开始整改/提交验收/验收通过/退回/关闭），点击展开 note 输入框，确认后调用状态更新 API，成功自动刷新。

**Sprint-5 Batch-B — 报告签发持久化与 UI**

- `routes_pages.py`：`_review_task_report_entry` 暴露 `signed`/`signed_by`/`signed_at`/`signoff_note`/`report_id` 五个签发字段，直接从 `dossier.signed_report` 读取（已持久化在 `review_tasks`）。
- 新增 `POST /api/v1/reports/drafts/{task_id}/signoff` JSON 接口，复用 `_build_review_task_signed_report` + `_update_review_task`；已签发返回 409；权限 `CREATE_REVIEW_TASK`（member 及以上）；`ReportSignoffRequest.signoff_note` max_length=2000。
- `replica-report-workbench.tsx`：新增 `SignoffButton` 组件（草稿→展开说明输入→成功显示绿色 ✓ 标签）；门禁阻断时不显示签发按钮；成功后刷新工作台。
- `api-client.ts`：新增 `signReportDraft(taskId, note)`。
- `api-types.ts`：`ReportWorkbenchEntry` 加可选 signoff 字段。

**Sprint-5 Batch-C — workspace 今日待复核预览**

- `workspace/page.tsx`：加载 pending-review 疑点列表（最多 5 条），每条展示风险等级 badge + 疑点名称 + 「进入复核」快捷链接；无待复核时显示绿色「审计进度良好 ✓」。

**Sprint-5 — 知识库来源标签本地化**

- `replica-rules-workbench.tsx`：新增 `SOURCE_COLLECTION_LABELS` 映射（26 个 collection key → 中文标签），`RuleCard` 和 `SourceCard` 来源字段改为本地化显示，修复 `SourceCard` 重复展示 raw key 的 bug。

**Sprint-5 — 验收文本合同对齐**

- `scripts/run-production-frontend-acceptance.mjs`：更新 `/workspace`（`工作台/待复核疑点`）和 `/remediation`（`整改工作台/整改事项`）路由的验收文本合同，对齐 Sprint-5 页面副本。

#### 本地/生产差异（截至 2026-08-09）

| 项目 | 本地 main HEAD | 生产 deploy_sha |
|---|---|---|
| commit | `226d3d0d` | `484c348f`（Sprint-4） |
| origin/main | `d31a1b1d`（Sprint-5 Batch-B） | 未部署 Sprint-5 |
| 报告签发 UI | ✅ SignoffButton 已实现 | ❌ 旧 UI |
| 整改状态操作 | ✅ StatusActionButtons | ❌ 旧只读展示 |
| workspace 待复核预览 | ✅ 已实现 | ❌ 旧 redirect |
| 知识库来源标签 | ✅ 中文化 | ❌ raw key |

**待 push 的本地 commit**：`226d3d0d fix(replica): localize collection labels and update acceptance text contracts`（1 commit ahead of origin/main）

#### 生产能力现状（2026-08-09 验收值，仍基于 Sprint-4 deploy）

| 指标 | 值 |
|---|---|
| deploy_sha | `484c348f`（Sprint-4，Sprint-5 尚未部署） |
| 本地 main | `226d3d0d`（领先 origin/main 1 commit） |
| 容器状态 | healthy（最后 L3 验收值） |
| 前端路由 | 23/23 |
| 知识库 collections | 25/25 |
| KB chunks | 923,288 |
| 疑点数据 | 5 条（脱敏样本） |
| review_tasks | 13 条 |
| remediation_items | 4 条 |
| report_entries | 13 条 |
| 测试套件 | vitest 406/406，ruff/mypy 全绿 |
| auth_mode | header_transition_layer |

#### 已知 debt（截至 2026-08-09）

**阻塞单院试运行（外部依赖）**

1. **真实 HIS 数据接入**：生产 5 条疑点均为手工脱敏样本，非来自 HIS 规则引擎；需院方提供 DDL + 字段字典 + 脱敏数据集。
2. **SSO 认证**：`auth_mode=header_transition_layer`，X-Role header 可自行构造；需确认院方 SSO 协议。

**产品功能债（可自主推进）**

3. **Sprint-5 代码尚未 push/部署**：本地 main `226d3d0d` 领先 origin/main 1 commit；origin/main `d31a1b1d` 领先生产 3 commits（Sprint-5 全部内容）；需 push 本地 commit 后再走部署流程。
4. **整改附件映射真实 case ID**：前端上传时用的是 workbench 返回的静态 case id，需映射到 `remediation_items.id` 真实 UUID。
5. **整改状态 UI 后端 PATCH 路由**：前端 `StatusActionButtons` 调用 `PATCH /api/v1/remediation/items/{id}/status`，需确认后端路由已对应（`POST .../status` 已有，需核实 HTTP 方法一致性）。
6. **告警 webhook**：`MEDICAL_AUDIT_AUDIT_LOG_ALERT_WEBHOOK_URL=` 为空，cron 已启用但无外部通知。

**长期架构债**

7. **supervision-rules-knowledge re-chunk**：定义类内容与字段模板混在同一 chunk；auto-retry 缓解，根本修复需重新 chunking + 重建 embedding。
8. **数据备份 pg_restore 完整验证**：gzip 完整性通过，未做完整 pg_restore 演练。
9. **压测覆盖**：查询 QPS/任务运行/报告导出关键路径未做压测。
10. **UAT 脚本和培训材料**：面向院方的验收脚本和操作手册未完成。

---

### 2.2 2026-08-07 Sprint 1-4 完整基线（最新）

状态口径：本节记录 2026-08-07 多轮 sprint 执行、对抗性 UI 审计、Bug 修复和生产部署后的完整基线。生产与本地 main 完全同步，deploy_sha = `484c348fe9aadc2771a5d4683cc2822b9ea815af`。

#### 本轮已完成事项（2026-08-07）

**工程治理**

- 84 条 `origin/codex/*` 历史分支全部清理，远端仅保留 `main`。
- 预先存在的 Dockerfile `UV_HTTP_TIMEOUT` 测试不一致（120 vs 180）已修复。
- 测试套件：pytest 核心 API 套件通过，vitest 406/406 通过，ruff/mypy 全绿。

**后端新增能力（Sprint 3）**

- **`visible_project_keys_for_findings` bug 修复**：私有化单院场景下，无自定义成员配置时认证用户默认可见所有 default 项目；疑点查询不再对非 admin 用户返回空集。
- **知识库 catalog SQL 性能优化**：4 个串行 SQL → 3 个，去掉 `COUNT(DISTINCT chunk_embeddings) FILTER (WHERE status='active')` 全表聚合（923K 行），加 `statement_timeout=8s` 防线程池阻塞，知识库页加载速度显著提升。
- **`remediation closure_gates` 动态化**：`_dynamic_closure_gates()` 从 DB items 实时计算门禁状态（`pending-acceptance`→阻断，`rejected`→阻断，全部 closed/accepted→通过），不再硬编码。
- **整改附件上传路由（S1）**：`POST /api/v1/remediation/items/{id}/attachments`（multipart, 20MiB 限制，白名单扩展名），`GET /api/v1/remediation/items/{id}/attachments`，`attachment_count` 字段同步递增。

**前端 UI/UX 优化（Sprint 1-4）**

- **导航重构**：侧边栏从 4 分组重构为「审计工作流」+「工具支撑」两层；知识库从 utility 升入 workflow 主区；文档检索降级到 utility。
- **医保专题 filter bar 合并**：3 层 tab（14 按钮）→ 3 个 select + count pill + 3 action buttons。
- **Finding cards 升级**：11 列表格 → 信息卡片（严重度 badge + 标题 + 状态 + meta 行 + action 行）。
- **知识库骨架屏**：loading 状态从文字提示改为 6 格 shimmer 骨架屏。
- **mobile filter bar 适配**：max-width 600px 操作按钮组换行左对齐。
- **workspace 工作台**：原 redirect /chat → 真实仪表板（4 个实时 KPI + 6 个快捷入口）。
- **FindingDrawer 去技术字段**：屏蔽 chunk_id/待映射/JSON 原始输出，改为患者/金额/违规摘要等可读语言。
- **WorkflowGateDialog 复核意见输入**：review 类型加必填 textarea，按钮 disabled 直到填写，不再写入硬编码机器文本。
- **整改工作台可操作化**：移除死链接，加入附件上传入口（复用 S1 路由），门禁状态三色视觉化（阻断/通过/待确认）。
- **RuleNavigator 默认折叠**：左侧规则栏从常驻 260px → 默认 40px 折叠，toggle 展开，首屏可见目标从 28 降至约 18。
- **TemplateWorkbookView 空状态引导**：空表格占位行 → 3 步操作引导 + 字段预览 + 「立即导入」CTA。
- **驾驶舱⇄医保专题联动**：驾驶舱加「进入医保审计」链接携带 `?project=id`，医保专题页读 URL 参数优先选择对应项目。
- **ProjectFlowPanel 紧凑化**：三区大面板（项目头/4步流程/队列/人员）→ 单行紧凑状态条（项目名 + 4 步计数），消除与驾驶舱的重叠。
- **CSS 体系对齐**：`audit-cockpit-page` 宽度合同对齐 `replica-page-standard`（`min(1440px, calc(100% - 72px))`）。

#### 生产能力现状（2026-08-07 验收值）

| 指标 | 值 |
|---|---|
| deploy_sha | `484c348f` (= main HEAD) |
| 容器状态 | healthy，Up ~30 min |
| 前端路由 | 23/23 全部 200 |
| 知识库 collections | 25/25 可查询 |
| KB chunks | 923,288 |
| 疑点数据 | 5 条（脱敏样本） |
| review_tasks | 13 条 |
| remediation_items | 4 条 |
| report_entries | 13 条 |
| report_templates | 3 个 active |
| OCR | deepseek+tesseract enabled |
| 知识查询 | generated ✅（law + rules） |
| auth_mode | header_transition_layer |
| 测试套件 | vitest 406/406，pytest 核心套件通过 |
| 远端分支 | main 唯一（84 条 codex/* 已清理） |

#### 已知 debt（截至 2026-08-07）

**阻塞单院试运行（外部依赖）**

1. **真实 HIS 数据接入**：生产 5 条疑点均为手工脱敏样本，非来自 HIS 规则引擎；需院方提供 DDL + 字段字典 + 脱敏数据集。
2. **SSO 认证**：`auth_mode=header_transition_layer`，X-Role header 可自行构造；需确认院方 SSO 协议（选 A：nginx 可信代理 / 选 B：SAML/OAuth2）。

**产品功能债（可自主推进）**

3. **整改附件附到真实 case ID**：前端上传时用的是 workbench 返回的静态 case id，需映射到 `remediation_items.id` 真实 UUID。
4. **整改状态更新 UI**：工作台可读取和上传附件，但无法在页面直接更新整改状态（需要独立操作流）。
5. **报告签发持久化**：`POST /reports/drafts` 已有，但 `is_signed_off/signed_at/signer` 未持久化到 DB。
6. **告警 webhook**：`MEDICAL_AUDIT_AUDIT_LOG_ALERT_WEBHOOK_URL=` 为空，cron 已启用但无外部通知；需院方/团队提供钉钉/企业微信 webhook URL。

**长期架构债**

7. **supervision-rules-knowledge re-chunk**：定义类内容与字段模板混在同一 chunk；auto-retry 缓解，根本修复需重新 chunking + 重建 embedding（需 embedding quota）。
8. **数据备份 pg_restore 完整验证**：gzip 完整性通过，DDL 可解析，但未在真实 PostgreSQL 实例做完整 pg_restore 演练。
9. **压测覆盖**：知识查询 QPS/合同审计并发/报告导出未做压测。
10. **UAT 脚本和培训材料**：面向院方的验收脚本和操作手册未完成。

---

### 2.1 2026-08-06 生产+本地对齐基线

状态口径：本节记录 2026-08-05 至 2026-08-06 多轮深度测试、Bug 修复、功能补齐和生产部署后的完整基线。生产与本地 main 完全同步，deploy_sha = `aa623e204a4c22d0e7577a32311fc701bbee6b24`。

#### 已完成事项

**生产部署与版本管理**

- 本地 main 追赶了 origin/main 的 326 个 commit（`git pull --ff-only`），所有本地历史 codex/* 分支（60+ 条）已清理，仅保留 main 一条分支、一个 worktree。
- 生产历次通过 deploy 脚本正式构建镜像部署，当前镜像 `3cb505f1ba6d`，deploy_sha = `aa623e20`，与 main HEAD 一致。
- 所有过去的手动 `docker cp` 补丁已被正式镜像取代，生产代码状态干净。
- `AGENTS.md`、`.gitignore`（排除本地草稿目录）等工程规范文件已提交并同步。

**后端新增能力（2026-08-05/06）**

- **整改独立 DB 表**：新增 `remediation_items` 表（SQL: `sql/remediation-items-schema-v1.sql`），生产已执行 migration。实现 `GET/POST /api/v1/remediation/items` 及 `POST .../status` 状态流转，6 个状态（待整改→整改中→待验收→验收通过/退回→已关闭）。
- **整改 workbench 数据源统一**：`/remediation/workbench` 优先读取 `remediation_items` DB，不再用静态种子数据。当前 `evidence_grade=backend-db`，`backend=SqlAlchemyRemediationStore`。
- **review-tasks 列表 API**：新增 `GET /api/v1/review-tasks`，返回 `review-tasks-list-v1` 格式，当前 13 条。
- **知识查询 deepseek dialect 修复**：`MEDICAL_AUDIT_KB_ANSWER_PROVIDER=openai` + `MEDICAL_AUDIT_KB_ANSWER_PROVIDER_DIALECT=deepseek`，确保 DeepSeek JSON 模式 prompt 和引用标记验证正常工作。
- **supervision-rules 单查自动 retry**：当规则类 collection 单查 citation marker 失败时，自动补充 `medical-insurance-laws` 重新检索，4/4 规则类查询现已 `generated`（含"分解住院""虚假住院"等典型场景）。
- **question 输入大小限制**：`QueryRequest.question` 新增 `max_length=2000`，防止超大 payload。
- **OCR workbench 全链路验收**：`/api/v1/ocr/extract` POST 端到端通过，`engine=deepseek-v4-pro+tesseract-chi_sim+eng`，`mapping_status=resolved`，Tesseract `chi_sim+eng+osd` 全部安装可用。
- **合同审计 PDF 报告**：loop129 已合入，DeepSeek-assisted OCR + PDF 导出端到端通过（`generation_status=pass`，`evidence_grade=L4-authorized-live`）。
- **httpx2 替换**：dev 依赖切换为 `httpx2`，消除 `StarletteDeprecationWarning`，981/981 测试通过。

**前端页面合同状态**

- 所有 19 个页面已更新为 `connected_first_batch`，无 `static_shell` 页面。
- `/medical-audit`、`/fund-compliance`、`/guided-check`、`/ocr` 等之前为 static_shell 的页面全部关联了真实后端 API。

**审计数据导入**

- 生产 DB 已写入 5 条脱敏样本疑点（分解住院/过度诊疗/目录限制/虚假住院/重复收费），关联到演示项目 `MEDICAL-AUDIT-DEMO-2026`。
- `/api/v1/audit-findings` 现返回 `total=5`，`generation_readiness.status=generated`。
- `audit_tasks` 的 `project_id` 已正确关联到 `MEDICAL-AUDIT-DEMO-2026`。

#### 生产能力现状（2026-08-06 验收值）

| 指标 | 值 |
|---|---|
| deploy_sha | `aa623e20` (= main HEAD) |
| 前端路由 | 23/23 全部 200 |
| 知识库 collections | 25/25 可查询 |
| KB chunks | 923,288 |
| 疑点数据 | 5 条 |
| review_tasks | 13 条 |
| remediation_items | 4 条 |
| report_entries | 13 条 |
| report_templates | 3 个 active |
| OCR | enabled, deepseek+tesseract |
| 知识查询 (law) | generated ✅ |
| 知识查询 (rules) | generated ✅ (retry) |
| auth_mode | header_transition_layer |
| 测试套件 | pytest 981/981, vitest 409/409 |

#### 已知 debt（截至 2026-08-06）

**Sprint 5 未完成（产品功能债）**

1. **整改附件存储**：`attachment_count` 字段存在但无上传/下载路由；需对象存储（COS）支撑。
2. **责任科室权限隔离**：`responsible_dept` 字段存在，但整改事项的科室可见性没有 RBAC 过滤。
3. **结案门禁绑定真实 DB**：`closure_gates` 仍是静态种子数据，未从 `remediation_items.status` 动态计算。
4. **报告签发冻结与电子签章**：`/reports/drafts` 已有草稿创建，但签发冻结（`POST /reports/drafts/{id}/signoff`）状态在 DB 中未持久化到 `review_tasks`。
5. **独立整改 DB 表完整化**：缺少整改验收退回记录、案件级整改归档。

**Sprint 6 未完成（上线加固债）**

6. **SSO 可信代理接入**：`auth_mode=header_transition_layer`，Legacy header 仍可构造，生产写入型权限 E2E 不得开始。
7. **数据备份恢复演练**：脚本存在（`scripts/deploy-tencent-cloud-production.py` 含备份逻辑），但未做完整 `pg_restore` 验证。
8. **生产告警 webhook**：`MEDICAL_AUDIT_AUDIT_LOG_ALERT_WEBHOOK_URL=` 为空，audit log 巡检 cron 已启用但无外部通知。
9. **压测覆盖**：查询/任务运行/报告导出关键路径未做压测。
10. **UAT 脚本和培训材料**：面向医院方的验收脚本和操作手册未完成。

**长期架构债**

11. **supervision-rules-knowledge 索引质量**：chunking 粒度过粗，"分解住院"等定义 chunk 被通用字段模板淹没；当前通过 auto-retry 补充 medical-insurance-laws 缓解，根本修复需要 re-chunk + 重建 embedding。
12. **审计数据为样本数据**：生产 5 条疑点均为脱敏手工插入，非来自真实 HIS 规则引擎运行；需接入真实 HIS 数据后重新运行规则评审。
13. **部署机制**：`deploy-tencent-cloud-production.py` Docker build 因网络限速（~3KB/s pypi 下载）每次耗时 60-90 分钟；建议引入私有 pypi 镜像或 BuildKit 缓存层。
14. **`visible_project_keys` 项目可见性 bug**：`list_findings` 用 project_key（字符串）过滤，但 `visible_project_keys` 返回项目 UUID；当前通过 admin 角色全可见绕过，非 admin 用户在只属于单个项目时仍能看到所有疑点，需对齐。

冻结日期：`2026-08-06`

---

### 2.0 2026-06-21 本地版本状态

状态口径：本节只同步当前本地工作区在第一阶段 UI 重构、Phase 2 对话工作台/智能体模板闭环/医保费用模板工作流、Phase 3 文档检索首页/权限角色 UI 映射、Batch 2 权限底座过渡层、Batch 3 后端 docx 导出切片和 Batch 4 报告页 API-first 下载切片后的事实；未执行生产部署、生产只读 smoke 或生产写入型 E2E。

本地版本变更：

- 前端新增 `/login` 登录界面，使用 `web/public/brand/auditscope-logo.png` 作为品牌资产。
- 前端门户壳层完成浅蓝医院内审工作台风格调整，左侧导航重组为 `核心功能 / 专题审计 / 知识底座 / 系统管理`。
- 核心功能导航覆盖 `AI 对话`、`智能体广场`、`文档检索`、`AI 数据分析`、`审计底稿生成`。
- 顶部状态栏新增全局检索输入、项目专题、后端待检测、AI 草稿人工确认、主任视图和四类角色视图。
- `AI 对话` 已从跳转表单升级为审证入口工作台，包含问题构建、知识来源、智能体选择、推荐问题和证据边界。
- `智能体广场` 和 `我的智能体` 已形成提示词型智能体创建闭环：广场模板可跳转到新增表单，模板可预填名称、分类、专题、关联知识库、关联项目和提示词；保存动作已接入权限检查和 `/agents` API。
- `文档检索` 首页已补齐知识库分类统计、仅标题前端筛选、无引用不下结论门禁、引用来源分组、原文核验入口和转入 AI 对话入口。
- `AI 数据分析` 已新增三张医保费用模板入口：`表1 医保费用汇总表`、`表2 医保费用分类汇总表`、`表3 就诊费用明细表`，并展示模板字段、核验重点和分析要求。
- `审计底稿生成` 已新增与三张模板对应的提示词模板：费用汇总风险底稿、分类费用复核清单、就诊明细疑点摘要。
- 后端导出链路已支持 Word/docx：`/pages/chat/export`、`/review-tasks/{task_id}/export`、`/review-tasks/{task_id}/report-draft`、`/review-tasks/{task_id}/signed-report` 均支持 `format=docx`；docx 由已有 Markdown 底稿/报告即时转换，已签发报告的 `content_sha256` 仍以冻结 Markdown 正文为准。
- 报告页已完成本地 API-first 下载切片：`/reports/workpaper-templates` 暴露三张医保费用模板 registry，`/reports/workbench` 聚合复核任务报告记录、证据来源、统计和 Word 下载链接；Next `/reports` 优先读取该接口并在无任务或后端异常时保留样例兜底。
- `项目管理` 已新增医院权限角色矩阵，覆盖 `管理员`、`技术人员`、`主任`、`普通成员`，并在新增成员表单中映射到既有项目成员角色。
- 权限底座已新增 `auth_departments`、`auth_users`、`auth_user_role_assignments`，并通过 `/auth/session`、`/auth/roles`、`/auth/users`、`/auth/users/{user_key}`、`/auth/users/{user_key}/role-assignments` 和 `/auth/users/{user_key}/role-assignments/{assignment_key}` 提供 header 过渡层 API；受控写入口的 `require_permission` 已优先使用持久化 `active/global` 角色授权，并拒绝 `disabled/pending` 用户。
- `/query`、`/documents/permissions`、`/documents/uploads`、`/audit/logs`、`/audit/logs/export` 和 `/pages/audit-logs` 已完成本地持久化用户优先解析；持久化角色可覆盖 header，停用用户会被拦截，审计日志页面保持无权限可打开但隐藏事件。
- `知识图谱` 已完成医保基金使用合规专项的只读关系预览，覆盖项目、知识库、文档、规则、疑点、复核、报告和整改节点。
- `专题规则库`、`补证整改`、`项目档案` 已完成本地只读入口验收，覆盖规则来源、发布门禁、整改台账、补证请求、归档巡检、签名链和审计日志受控入口。
- 本轮扩展了 `web/src/lib/api-client.ts`、`web/src/lib/api-types.ts` 和 FastAPI router，以接入本地权限底座；未删除现有后端能力。
- 当前工作区仍存在既有未跟踪资料和草稿目录；本轮未清理、迁移或归档这些目录。

本地验收证据：

- `uv run ruff check .`：通过。
- `uv run mypy src`：通过，`88` 个 source files。
- `uv run pytest tests/knowledge_query`：通过，`288 passed`，`1` 个既有 `StarletteDeprecationWarning`。
- `pnpm --filter medical-audit-web lint`：通过。
- `pnpm --filter medical-audit-web typecheck`：通过。
- `pnpm --filter medical-audit-web test`：通过，`11` 个 test files、`91` 个 tests。
- `pnpm --filter medical-audit-web build`：通过，静态页面 `21/21`。
- `uv run pytest tests/knowledge_query/test_api.py -k "auth_api or permission_resolver or agents_api_enforces or projects_api_enforces"`：通过，`6 passed`，覆盖持久化角色优先和 disabled 用户拒绝。
- `uv run pytest tests/knowledge_query/test_api.py -k "auth_api or permission_resolver"`：通过，`5 passed`，覆盖软禁用/恢复用户、撤销/恢复角色授权和撤销后的降权。
- `uv run pytest tests/knowledge_query/test_api.py -k "documents or query_endpoint"`：通过，`8 passed`，覆盖文档权限、文档上传列表和查询入口的持久化用户状态门禁。
- `uv run pytest tests/knowledge_query/test_pages.py -k "audit_logs"`：通过，`5 passed`，覆盖审计日志 API、导出和后端页面的持久化角色覆盖。
- `uv run pytest tests/knowledge_query/test_pages.py -k "docx or review_task_create_update_and_export_flow or chat_dossier_export"`：通过，`5 passed`，覆盖对话底稿、复核任务记录、报告草稿和已签发报告 docx 导出。
- `uv run pytest tests/knowledge_query/test_pages.py -k "report_workpaper_template_registry or review_task_create_update_and_export_flow"`：通过，`2 passed`，覆盖模板 registry、报告 workbench 和 Word 下载链接聚合。
- `pnpm --filter medical-audit-web test -- src/lib/api-client.test.ts src/app/'(workspace)'/workspace-pages.test.tsx`：通过，`41 passed`，覆盖 `/api/v1/reports/workbench` client 和 Next `/reports` API-first 下载入口。
- `pnpm local:fullstack:e2e`：通过，`16 passed`，覆盖 `/reports` 模板源文件和 registry 状态可见。
- `pnpm --dir web test -- src/app/'(workspace)'/workspace-pages.test.tsx`：通过，`23` 个 tests。
- Playwright 本地检查 `/login`、`/workspace`、`/chat`、`/agent-market`、`/agents?template=template-identity-risk#new-agent`、`/documents`、`/knowledge-base`、`/analytics`、`/reports`、`/projects`、`/graph`、`/rules`、`/remediation`、`/archive`：检查页面均 `h1Count=1`，`horizontalOverflow=false`。
- 截图：`tmp/screenshots/phase1-ui-login-20260621.png`、`tmp/screenshots/phase1-ui-workspace-20260621.png`、`tmp/screenshots/phase2-chat-workbench-20260621.png`、`tmp/screenshots/phase2-template-workflow-analytics-20260621.png`、`tmp/screenshots/phase2-template-workflow-reports-20260621.png`。
- 智能体模板截图：`tmp/screenshots/phase2-agent-template-market-20260621.png`、`tmp/screenshots/phase2-agent-template-prefill-20260621.png`。
- 文档检索截图：`tmp/screenshots/phase3-document-search-home-20260621.png`、`tmp/screenshots/phase3-knowledge-base-readonly-20260621.png`。
- 权限角色截图：`tmp/screenshots/phase3-role-permission-projects-20260621.png`。
- 知识图谱截图：`tmp/screenshots/phase5-graph-readonly-desktop-20260621.png`、`tmp/screenshots/phase5-graph-readonly-mobile-20260621.png`。
- 规则/整改/归档截图：`tmp/screenshots/phase5-rules-prod-desktop-20260621.png`、`tmp/screenshots/phase5-rules-prod-mobile-20260621.png`、`tmp/screenshots/phase5-remediation-prod-desktop-20260621.png`、`tmp/screenshots/phase5-remediation-prod-mobile-20260621.png`、`tmp/screenshots/phase5-archive-prod-desktop-20260621.png`、`tmp/screenshots/phase5-archive-prod-mobile-20260621.png`。

当前边界：

- `production unchanged`：本轮没有生产部署或生产变更操作。
- `no provider call`：本轮没有调用生成模型或外部 AI provider。
- `local fullstack smoke only`：本轮启动一次性内存态 FastAPI 做本地联调；不代表真实 PostgreSQL、真实医院数据或生产索引验收。
- `auth_status=header_transition_layer_with_controlled_api_auth_and_local_tenant_header`：账号、科室和角色授权已有本地 schema/store/API，受控写入口和核心查询/文档/审计日志路由已优先使用持久化角色并拒绝 disabled/pending profile，已支持软禁用/恢复用户、撤销/恢复角色授权、项目级角色 scope 和本地 `X-Tenant-Id` 请求头契约；受控 API 鉴权中间件已在本地强制模式要求租户头并通过 E2E，但仍未完成真实医院 SSO、登录会话签发、正式租户身份来源或生产权限验收。
- `docx_status=local_backend_export_ready`：docx 当前由标准库从既有 Markdown 内容生成，已通过本地 API 测试打开 `.docx` 包校验主文档 XML；不代表生产验收、电子签章或证书级正式报告。
- `report_workbench_status=local_api_first_next_ready`：Next `/reports` 已读取 `/reports/workbench` 并展示任务 Word、报告 Word 和模板 registry；无任务或后端异常时保留样例兜底，不代表生产验收或正式签章。
- `manual review required`：智能体生产部署验收、生产智能体调用统计、正式租户 scope、个人材料真实入向量索引、外部杀毒/DLP 服务、对象存储、动态图谱查询 API、规则执行写入、整改验收写入、审计日志生产权限专项验收、归档签名、生产报告验收、电子签章和正式底稿签发仍需后续阶段实现或验证；医保表模板元数据和图谱关系预览当前仍以本地 UI/静态关系或本地模板 registry 为主。
- `document_search_status=local_title_only_governance_security_download_ready`：`/query` 已支持 `title_only` 标题/路径元数据过滤；`/documents/uploads/{upload_id}/governance` 已支持本地个人材料治理状态机；上传记录已带 `local-policy` 安全扫描/DLP 标记；`/documents/uploads/{upload_id}/download` 已按本人或读全部权限隔离下载；`approved-for-index` 仅标记 `index-ready`，不代表上传文件已写入真实检索索引。

冻结日期：`2026-06-21`

### 2.0.1 2026-06-22 Batch 7.3 本地版本状态

状态口径：本节只同步本地智能体真实对话挂接、反馈统计和项目范围校验增量；未执行生产部署、生产只读 smoke、生产写入型 E2E 或外部 AI provider 调用。

本地版本变更：

- `/query` 已接受可选 `agent` 参数；当用户选择智能体且回答生成成功时，后端会写入 `audit_agent_invocations`，返回 `agent_invocation_id`，并在操作日志中关联 `query_log_id`、引用数量和筛选条件。
- `/pages/chat` 已接受 `agent` 和 `project_name` 查询参数；从 Next `/chat` 提交到后端深页时会登记一次 `/pages/chat` 来源的智能体调用记录，`/pages/chat/export` 只导出底稿，不重复登记新调用。
- Next `/chat?agent=...` 已按 URL 参数选中对应智能体，并随表单提交当前项目空间，避免从“我的智能体”进入对话后丢失智能体选择。
- `/agents`、智能体详情、版本、生命周期、调用和反馈接口已支持 URL encoded `X-Project-Name` 项目范围校验；`visibility_scope=project` 的智能体会按当前项目过滤或阻断跨项目操作，`visibility_scope=system` 仍全局可见。
- `/agents/{agent_key}/feedback` 已返回 `summary`，包含 `total`、`effective`、`needs_review`、`unsafe` 和 `latest_rating`；Next `/agents` 已展示可继续使用、需要复核、暂不建议三类反馈统计。
- 本批未新增数据库表或迁移，复用 Batch 7.2 已落地的 `audit_agent_invocations` 和 `audit_agent_feedback`。

本地验收证据：

- `uv run pytest tests/knowledge_query/test_api.py::test_agents_api_tracks_prompt_versions_lifecycle_and_history tests/knowledge_query/test_api.py::test_agents_api_filters_project_scope_and_blocks_cross_project_invocation tests/knowledge_query/test_api.py::test_query_endpoint_returns_citation_answer_and_records_query_log tests/knowledge_query/test_api.py::test_query_endpoint_records_selected_agent_invocation tests/knowledge_query/test_pages.py::test_chat_page_renders_conversation_evidence_and_followups tests/knowledge_query/test_pages.py::test_chat_page_records_selected_agent_invocation_without_export_duplication tests/knowledge_query/test_pages.py::test_chat_dossier_export_returns_json_download_and_records_log`：通过，`7 passed`，`1` 个既有 `StarletteDeprecationWarning`。
- `uv run ruff check src/medical_audit_kb/api/routes_agents.py src/medical_audit_kb/api/routes_query.py src/medical_audit_kb/api/routes_pages.py tests/knowledge_query/test_api.py tests/knowledge_query/test_pages.py`：通过。
- `uv run mypy src/medical_audit_kb/api/agent_store.py src/medical_audit_kb/api/routes_agents.py src/medical_audit_kb/api/routes_query.py src/medical_audit_kb/api/routes_pages.py`：通过。
- `uv run pytest tests/knowledge_query/test_api.py tests/knowledge_query/test_pages.py`：通过，`79 passed`，`1` 个既有 `StarletteDeprecationWarning`。
- `pnpm --filter medical-audit-web test -- src/lib/api-client.test.ts 'src/app/(workspace)/workspace-pages.test.tsx'`：通过，`2` 个 test files、`57` 个 tests。
- `pnpm --filter medical-audit-web typecheck`：通过。
- `pnpm --filter medical-audit-web lint`：通过。
- `pnpm --filter medical-audit-web build`：通过，静态页面 `21/21`。
- `git diff --check`：通过。

当前边界：

- `production unchanged`：本批没有生产部署或生产变更操作。
- `no provider call`：本批没有调用生成模型或外部 AI provider。
- `local verification only`：本批验收为本地 API、模板、Next 单测、typecheck 和 lint；不代表生产对话、生产项目范围或真实医院 SSO 验收。
- `project_scope_header=percent_encoded`：项目范围请求头使用 URL encoded `X-Project-Name`，后端 decode 后与智能体 `project_name` 比对；这是本地过渡方案，不等同于正式租户身份来源或医院 SSO scope。
- `manual review required`：逐行 prompt diff 审批流、生产智能体调用统计、真实会话权限、生产权限验收和生产部署验收仍需后续阶段完成。

冻结日期：`2026-06-22`

### 2.0.2 2026-06-22 Batch 7.4 本地版本状态

状态口径：本节只同步本地智能体提示词逐行对照、版本审核状态和审核操作首切片；未执行生产部署、生产只读 smoke、生产写入型 E2E、真实医院 SSO 或外部 AI provider 调用。

本地版本变更：

- `/agents/{agent_key}/prompt-versions` 新增 `review_note` 入参；新建提示词版本默认写入 `review_status=pending-review`。
- `/agents/{agent_key}/prompt-versions/review` 已新增本地审核状态接口，支持 `pending-review`、`approved`、`changes-requested`，复用 `manage_agents` 权限和项目范围校验，并记录 `agent-prompt-version-review` 操作日志。
- `prompt_versions` 响应已补充 `review_status`、`review_note`、`requested_by`、`reviewed_by`、`reviewed_at` 和 `review_updated_at` 字段。
- 回滚生成的新当前版本会标记为 `approved`，保留历史版本审核信息。
- Next `/agents` 已展示当前提示词审核状态、版本列表审核标签、审核意见、`审批通过` / `要求修改` 操作，以及上一版与当前版的逐行对照表。
- 本批未新增数据库表或迁移；审核状态首切片暂存于 `AuditAgent.extra_metadata["prompt_version_reviews"]`，不改变当前提示词激活语义。

本地验收证据：

- `uv run ruff check src/medical_audit_kb/api/agent_store.py src/medical_audit_kb/api/routes_agents.py tests/knowledge_query/test_api.py`：通过。
- `uv run mypy src/medical_audit_kb/api/agent_store.py src/medical_audit_kb/api/routes_agents.py`：通过。
- `uv run pytest tests/knowledge_query/test_api.py -k "agents_api"`：通过，`5 passed`，`40 deselected`，`1` 个既有 `StarletteDeprecationWarning`。
- `pnpm --filter medical-audit-web test -- src/lib/api-client.test.ts 'src/app/(workspace)/workspace-pages.test.tsx'`：通过，`2` 个 test files、`58` 个 tests。
- `pnpm --filter medical-audit-web typecheck`：通过。
- `pnpm --filter medical-audit-web lint`：通过。
- `pnpm --filter medical-audit-web build`：通过，静态页面 `21/21`。
- `uv run python scripts/run-local-fullstack-e2e.py`：通过，`16 passed`，使用临时 in-memory FastAPI 后端和 fake provider。
- `git diff --check`：通过。

当前边界：

- `production unchanged`：本批没有生产部署或生产变更操作。
- `no provider call`：本批没有调用生成模型或外部 AI provider。
- `local verification only`：本批验收为本地 API、Next 单测、typecheck、lint、build 和本地 fullstack E2E；不代表生产智能体治理验收。
- `review_status_tracking_only`：审核状态已可记录、展示和追溯，但当前没有强制阻断未通过版本被激活或被对话使用；正式激活门禁仍需后续阶段实现。
- `project_scope_header=percent_encoded`：项目范围请求头仍是 URL encoded `X-Project-Name` 过渡方案，不等同于正式租户身份来源或医院 SSO scope。
- `manual review required`：生产智能体调用统计、真实会话权限、生产权限验收、生产部署验收、审核强制激活门禁和正式租户 scope 仍需后续阶段完成。

冻结日期：`2026-06-22`

### 2.0.3 2026-06-22 Batch 7.5 本地版本状态

状态口径：本节只同步本地智能体提示词审核激活门禁；未执行生产部署、生产只读 smoke、生产写入型 E2E、真实医院 SSO 或外部 AI provider 调用。

本地版本变更：

- `/agents/{agent_key}/prompt-versions` 新建提示词版本后只生成候选版本，`review_status=pending-review`，不再覆盖 `agent.prompt`、`prompt_version` 或 `prompt_version_key`。
- `/agents/{agent_key}/prompt-versions/review` 在 `review_status=approved` 时才激活对应版本；`changes-requested` 只记录审核意见，不改变当前 active prompt。
- `prompt_versions` 响应新增 `is_active`，用于前端明确区分当前激活版本和待审候选版本。
- Next `/agents` 已展示 `待审版本`、`当前激活` 标记、`审核对象：vN`，版本对比改为“当前激活 vs 待审版本”；保存候选后提示“待审批通过后激活”。
- 智能体调用登记继续使用当前 active `prompt_version_key`；审批通过后才切换到新版本 key。
- 回滚仍生成新的 approved active 版本，作为人工治理下的显式激活动作。
- `/agents` 在持久化 agent store 不可用时的默认智能体 fallback 也会返回 `prompt_versions` 和 `is_active`，避免前端版本治理视图在默认数据下缺字段。
- 本批未新增数据库表或迁移；仍复用 `AuditAgent.extra_metadata["prompt_version_reviews"]` 和现有 prompt version 表。

本地验收证据：

- `uv run ruff check src/medical_audit_kb/api/agent_store.py src/medical_audit_kb/api/routes_agents.py tests/knowledge_query/test_api.py`：通过。
- `uv run pytest tests/knowledge_query/test_api.py -k "agents_api_tracks_prompt_versions_lifecycle_and_history"`：通过，`1 passed`，`44 deselected`，`1` 个既有 `StarletteDeprecationWarning`。
- `uv run pytest tests/knowledge_query`：通过，`285 passed`，`1` 个既有 `StarletteDeprecationWarning`。
- `uv run mypy src`：通过，`88` 个 source files。
- `pnpm --filter medical-audit-web typecheck`：通过。
- `pnpm --filter medical-audit-web lint`：通过。
- `pnpm --filter medical-audit-web test`：通过，`11` 个 test files、`90` 个 tests。
- `pnpm --filter medical-audit-web build`：通过，静态页面 `21/21`。
- `uv run python scripts/run-local-fullstack-e2e.py`：通过，`16 passed`，使用临时 in-memory FastAPI 后端和 fake provider。

当前边界：

- `production unchanged`：本批没有生产部署或生产变更操作。
- `no provider call`：本批没有调用生成模型或外部 AI provider。
- `local verification only`：本批验收为本地 API、Next 单测、typecheck、lint、build 和本地 fullstack E2E；不代表生产智能体治理验收。
- `review_activation_gate=local_ready`：本地保存候选、退回修改、审批激活和回滚激活已闭合；生产部署验收、正式租户 scope 和生产权限验收仍需后续阶段完成。
- `e2e_harness_required`：需要 FastAPI 数据的本地 Playwright 验收必须使用 `uv run python scripts/run-local-fullstack-e2e.py` 或等价全栈 harness；单独运行 web e2e 只启动 Next，不能作为完整验收结论。

冻结日期：`2026-06-22`

### 2.0.4 2026-06-22 Batch 7.6 本地版本状态

状态口径：本节只同步本地智能体提示词审核/激活的角色分离门禁；未执行生产部署、生产只读 smoke、生产写入型 E2E、真实医院 SSO 或外部 AI provider 调用。

本地版本变更：

- `/agents/{agent_key}/prompt-versions/review` 和 `/agents/{agent_key}/prompt-versions/rollback` 已增加二次角色门禁：只有 `admin` 和 `director` 可审核激活或回滚激活提示词版本。
- `technician` 仍可使用 `manage_agents` 创建智能体和保存候选提示词版本，但不能把候选版本变成 active prompt，也不能通过回滚生成新的 active version。
- 被拒绝的提示词审核/回滚激活请求会记录 `authorization-denied` 操作日志，payload 标记 `permission=review_agent_prompts` 和原始 `attempted_action`。
- Next `/agents` 已把“保存新版本”和“审批/回滚激活”拆开：技术人员可保存候选版本，但 `审批通过`、`要求修改` 和 `回滚到此版` 不会触发激活 API。

本地验收证据：

- `uv run ruff check src/medical_audit_kb/api/routes_agents.py tests/knowledge_query/test_api.py`：通过。
- `uv run pytest tests/knowledge_query/test_api.py -k 'agents_api_restricts_prompt_activation_to_admin_and_director or agents_api_tracks_prompt_versions_lifecycle_and_history'`：通过，`2 passed`，`45 deselected`，`1` 个既有 `StarletteDeprecationWarning`。
- `pnpm --filter medical-audit-web test -- workspace-pages.test.tsx -t 'prompt activation controls'`：通过，`1 passed`，`27 skipped`。
- `uv run ruff check .`：通过。
- `uv run mypy src`：通过，`88` 个 source files。
- `uv run pytest tests/knowledge_query`：通过，`286 passed`，`1` 个既有 `StarletteDeprecationWarning`。
- `pnpm --filter medical-audit-web typecheck`：通过。
- `pnpm --filter medical-audit-web lint`：通过。
- `pnpm --filter medical-audit-web test`：通过，`11` 个 test files、`91` 个 tests。
- `pnpm --filter medical-audit-web build`：通过，静态页面 `21/21`。
- `uv run python scripts/run-local-fullstack-e2e.py`：通过，`16 passed`，使用临时 in-memory FastAPI 后端和 fake provider。
- `git diff --check`：通过。

当前边界：

- `production unchanged`：本批没有生产部署或生产变更操作。
- `no provider call`：本批没有调用生成模型或外部 AI provider。
- `local verification only`：本批验收为本地 API、Next 单测、静态质量闸、build 和本地 fullstack E2E；不代表生产智能体治理验收。
- `agent_prompt_activation_roles=admin_or_director_only`：本地提示词审核/回滚激活已收口到管理员和主任；正式租户 scope、真实登录会话、医院 SSO 和生产权限验收仍需后续阶段完成。

冻结日期：`2026-06-22`

### 2.0.5 2026-06-22 Batch 7.7 本地版本状态

状态口径：本节只同步本地项目级角色 scope 生效切片；未执行生产部署、生产只读 smoke、生产写入型 E2E、真实医院 SSO 或外部 AI provider 调用。

本地版本变更：

- 持久化用户角色解析已支持 `scope_type=project` + `scope_key=<project_key>`；当请求带 `X-Project-Key` 时，匹配项目的 active role assignment 会作为生效角色返回。
- `/auth/session` 已接受 `X-Project-Key`，返回 `auth_scope_type` 和 `auth_scope_key`，用于区分 `persistent_role` 与 `persistent_project_role`。
- `/projects/{project_key}/members` 新增成员写入口已按路径 `project_key` 传入权限解析；项目 scoped `admin` 只在对应项目获得 `manage_project_members`，跨项目仍返回 `403`。
- Next API client 已让 `/auth/session` 携带当前项目 key，并让 `createProjectMember(projectId, ...)` 携带对应 `X-Project-Key`。
- 顶部栏已展示后端 session 的生效角色，便于区分本地角色视图和后端实际授权角色。

本地验收证据：

- `uv run ruff check src/medical_audit_kb/api/auth.py src/medical_audit_kb/api/routes_auth.py src/medical_audit_kb/api/routes_projects.py tests/knowledge_query/test_api.py`：通过。
- `uv run pytest tests/knowledge_query/test_api.py -k 'permission_resolver_uses_project_scoped_role or permission_resolver_prefers_persisted_global_role or auth_api_updates_user_status'`：通过，`3 passed`，`45 deselected`，`1` 个既有 `StarletteDeprecationWarning`。
- `uv run mypy src/medical_audit_kb/api/auth.py src/medical_audit_kb/api/routes_auth.py src/medical_audit_kb/api/routes_projects.py`：通过。
- `pnpm --filter medical-audit-web test -- src/lib/api-client.test.ts src/components/shell/workspace-shell.test.tsx`：通过，`2` 个 test files、`36` 个 tests。
- `pnpm --filter medical-audit-web typecheck`：通过。
- `uv run ruff check .`：通过。
- `uv run mypy src`：通过，`88` 个 source files。
- `uv run pytest tests/knowledge_query`：通过，`287 passed`，`1` 个既有 `StarletteDeprecationWarning`。
- `pnpm --filter medical-audit-web lint`：通过。
- `pnpm --filter medical-audit-web typecheck`：通过。
- `pnpm --filter medical-audit-web test`：通过，`11` 个 test files、`91` 个 tests。
- `pnpm --filter medical-audit-web build`：通过，静态页面 `21/21`。
- `uv run python scripts/run-local-fullstack-e2e.py`：通过，`16 passed`，使用临时 in-memory FastAPI 后端和 fake provider。

当前边界：

- `production unchanged`：本批没有生产部署或生产变更操作。
- `no provider call`：本批没有调用生成模型或外部 AI provider。
- `local verification only`：本批验收为本地 API、前端单测、静态质量闸、build 和本地 fullstack E2E；不代表生产权限体系验收。
- `project_scope_role=local_ready`：项目级 role assignment 已能在本地 session 和项目成员写入口生效；正式租户身份来源、医院 SSO、真实登录会话签发和生产权限验收仍需后续阶段完成。

冻结日期：`2026-06-22`

### 2.0.6 2026-06-22 Batch 7.8 本地版本状态

状态口径：本节只同步受控 API 鉴权中间件本地强制模式切片；未执行生产部署、生产只读 smoke、生产写入型 E2E、真实医院 SSO、真实会话签发或外部 AI provider 调用。

本地版本变更：

- FastAPI `create_app(..., enforce_controlled_api_auth=True)` 已支持受控 API 鉴权中间件；默认保持兼容，生产或本地验收可通过 `MEDICAL_AUDIT_CONTROLLED_API_AUTH=enforce` 或显式参数开启。
- 中间件对 `/query`、`/agents`、`/analytics`、`/documents`、`/projects`、`/auth/session`、图谱/规则/整改/归档 workbench、报告、审计日志、索引等受控 API 做基础用户解析；`/health`、`/auth/roles`、`/index/postgres-status`、`/static/*` 和 `/preview/*` 保持公开或只读探测路径。
- 未带角色头的受控 API 访问会返回 `401/403` 并写入 `authorization-denied`，停用持久化用户即使带 `admin` header 也会被中间件拒绝。
- 本地 `pnpm local:fullstack:e2e` 的内存态 FastAPI 后端已改为强制鉴权模式，作为前端工作区 API 是否漏带审计角色头的回归门禁。
- Next API client 已让查询历史、疑点、报告、图谱、规则、整改、归档、分析历史、项目列表和项目成员读取接口统一携带 `X-Role` / `X-User-Id`；项目读取接口还携带 `X-Project-Key`。

本地验收证据：

- `uv run ruff check src/medical_audit_kb/api/app.py tests/knowledge_query/test_api.py scripts/run-local-fullstack-e2e.py`：通过。
- `uv run pytest tests/knowledge_query/test_api.py -k 'controlled_api_auth_middleware or permission_resolver_uses_project_scoped_role or auth_api_rejects_member_user_management'`：通过，`3 passed`，`46 deselected`，`1` 个既有 `StarletteDeprecationWarning`。
- `pnpm --filter medical-audit-web test -- src/lib/api-client.test.ts`：通过，`31` 个 tests。
- `uv run mypy src/medical_audit_kb/api/app.py src/medical_audit_kb/api/auth.py`：通过。
- `pnpm --filter medical-audit-web typecheck`：通过。
- `pnpm local:fullstack:e2e`：通过，`16 passed`，后端以强制受控 API 鉴权模式启动。
- `uv run ruff check .`：通过。
- `uv run mypy src`：通过，`88` 个 source files。
- `uv run pytest tests/knowledge_query`：通过，`288 passed`，`1` 个既有 `StarletteDeprecationWarning`。
- `pnpm --filter medical-audit-web lint`：通过。
- `pnpm --filter medical-audit-web test`：通过，`11` 个 test files、`91` 个 tests。
- `pnpm --filter medical-audit-web build`：通过，静态页面 `21/21`。

当前边界：

- `production unchanged`：本批没有生产部署或生产变更操作。
- `no provider call`：本批没有调用生成模型或外部 AI provider。
- `local verification only`：本批验收为本地 API、前端单测、静态质量闸、build 和本地 fullstack E2E；不代表生产权限体系验收。
- `controlled_api_auth_gate=local_enforce_ready`：受控 API 中间件本地强制模式已通过；真实医院 SSO、正式登录会话、租户 ID、网关/Nginx 注入策略、生产只读和生产写入型权限验收仍未完成。

冻结日期：`2026-06-22`

### 2.0.7 2026-06-22 Batch 7.9 本地版本状态

状态口径：本节只同步本地租户 ID 请求头契约切片；未执行生产部署、生产只读 smoke、生产写入型 E2E、真实医院 SSO、真实会话签发或外部 AI provider 调用。

本地版本变更：

- FastAPI 受控 API 鉴权中间件在强制模式下已要求 `X-Tenant-Id`；受控 API 未带租户头会返回 `401`，并写入 `authorization-denied`，payload 保留 `tenant_id=None` 和拒绝原因。
- `/auth/session` 已接受 `X-Tenant-Id` 并在响应中返回 `tenant_id`，用于让前端和测试链路核对当前本地租户上下文。
- Next API client 已在 `auditClientHeaders()` 默认发送 `X-Tenant-Id: hospital-demo`；查询历史、疑点、报告、图谱、规则、整改、归档、分析历史、项目列表、项目成员和 `/auth/session` 等工作区 API 继承该请求头。
- 本地 fullstack E2E 仍以强制受控 API 鉴权模式运行，当前可同时验证审计角色头、项目 key 和本地租户头没有遗漏。

本地验收证据：

- `uv run ruff check src/medical_audit_kb/api/app.py src/medical_audit_kb/api/auth.py src/medical_audit_kb/api/routes_auth.py tests/knowledge_query/test_api.py scripts/run-local-fullstack-e2e.py`：通过。
- `uv run pytest tests/knowledge_query/test_api.py -k 'controlled_api_auth_middleware or auth_api_lists_roles_and_manages_users or permission_resolver_uses_project_scoped_role'`：通过，`3 passed`，`46 deselected`，`1` 个既有 `StarletteDeprecationWarning`。
- `pnpm --filter medical-audit-web test -- src/lib/api-client.test.ts`：通过，`31` 个 tests。
- `uv run ruff check .`：通过。
- `uv run mypy src`：通过，`88` 个 source files。
- `uv run pytest tests/knowledge_query`：通过，`288 passed`，`1` 个既有 `StarletteDeprecationWarning`。
- `pnpm --filter medical-audit-web lint`：通过。
- `pnpm --filter medical-audit-web typecheck`：通过。
- `pnpm --filter medical-audit-web test`：通过，`11` 个 test files、`91` 个 tests。
- `pnpm --filter medical-audit-web build`：通过，静态页面 `21/21`。
- `pnpm local:fullstack:e2e`：通过，`16 passed`，后端以强制受控 API 鉴权模式启动。

当前边界：

- `production unchanged`：本批没有生产部署或生产变更操作。
- `no provider call`：本批没有调用生成模型或外部 AI provider。
- `local verification only`：本批验收为本地 API、前端单测、静态质量闸、build 和本地 fullstack E2E；不代表生产权限体系验收。
- `tenant_header_contract=local_ready`：`X-Tenant-Id` 只是本地过渡请求头契约和 E2E 漏头门禁，不等同于真实医院租户 ID、SSO claims、网关注入策略或生产多租户隔离。

冻结日期：`2026-06-22`

### 2.0.8 2026-06-22 Batch 8.1 本地版本状态

状态口径：本节只同步生产权限只读验收脚本 dry-run 准备；未执行生产只读 smoke、生产写入型 E2E、生产部署、真实医院 SSO、真实会话签发或外部 AI provider 调用。

本地版本变更：

- 新增 `scripts/run-controlled-api-readonly-permission-smoke.py`，只发 `GET` 请求，用于检查受控 API 在只读路径上的角色头、项目 key 和 `X-Tenant-Id` 门禁表现。
- 新增 `pnpm local:permission:readonly`，默认针对本地 `http://127.0.0.1:8021` 执行 `enforce` 模式；该模式会把受控 API 裸请求、缺租户头请求和管理员带齐请求按预期状态严格断言。
- 新增 `pnpm production:permission-readonly`，默认针对 `https://audit.lute-tlz-dddd.top/api/v1` 执行 `observe` 模式并写入 `tmp/outputs/production-permission-readonly-smoke-latest.json`；该命令只读观测，不做生产写入，不调用 provider，不把观测结果自动判定为生产权限验收通过。
- 脚本支持可选 `--api-key-env`，只记录环境变量名和是否配置，不把 secret 写入报告。

本地验收证据：

- `uv run ruff check scripts/run-controlled-api-readonly-permission-smoke.py tests/knowledge_query/test_scripts.py`：通过。
- `uv run pytest tests/knowledge_query/test_scripts.py -k 'controlled_api_readonly_permission'`：通过，`4 passed`，`23 deselected`。
- `python3 -m py_compile scripts/run-controlled-api-readonly-permission-smoke.py`：通过。
- `uv run pytest tests/knowledge_query/test_scripts.py`：通过，`27 passed`。
- `uv run pytest tests/knowledge_query`：通过，`292 passed`，`1` 个既有 `StarletteDeprecationWarning`。
- `uv run mypy src`：通过，`88` 个 source files。
- `git diff --check`：通过。

当前边界：

- `production unchanged`：本批没有生产部署或生产变更操作。
- `production_readonly_status=not_run`：本批没有实际访问生产权限接口；只完成只读验收脚本和本地契约测试。
- `no provider call`：本批没有调用生成模型或外部 AI provider。
- `readonly_permission_smoke_status=script_ready`：脚本可作为下一步生产只读观测入口，但生产通过结论必须等真实报告生成后再写。

冻结日期：`2026-06-22`

### 2.0.9 2026-06-23 Batch 8.2 生产只读权限观测状态

状态口径：本节只同步一次授权后的生产只读权限 smoke 观测；本批未执行生产部署、生产写入型 E2E、数据库写入、真实医院 SSO、真实会话签发或外部 AI provider 调用。

生产只读命令：

- `pnpm production:permission-readonly`
- 报告路径：`tmp/outputs/production-permission-readonly-smoke-latest.json`
- 报告时间：`2026-06-23T03:15:52Z` 至 `2026-06-23T03:17:37Z`

生产只读观测结论：

- 报告 `status=fail`，`probe_count=35`，`issue_count=1`，`observation_count=28`。
- `production_side_effect=none`，`provider_call_status=not_called`，`http_methods=["GET"]`。
- `/api/v1/health` 返回 `200`，说明生产 API 基础健康探测可读。
- `/api/v1/auth/roles` 返回 `404`；`/api/v1/auth/session` 三类探针均返回 `404`，说明本地 `/auth/*` 过渡层尚未部署到当前生产。
- `/api/v1/projects`、`/api/v1/agents`、`/api/v1/query/logs?limit=1`、`/api/v1/audit-findings`、`/api/v1/analytics/table-uploads` 等已存在读接口对缺少 `X-Tenant-Id` 的请求返回 `200`；当前生产未执行 Batch 7.9 的租户头强制门禁。
- `/api/v1/graph/workbench`、`/api/v1/rules/workbench`、`/api/v1/remediation/workbench`、`/api/v1/archive/workbench`、`/api/v1/reports/workbench` 返回 `404`，说明本地 API-first workbench 切片尚未部署到当前生产。

当前边界：

- `production_readonly_status=fail`：本批已执行生产只读权限 smoke，但结论是不通过。
- `production unchanged`：本批没有生产部署或生产变更操作。
- `no provider call`：本批没有调用生成模型或外部 AI provider。
- `auth_production_gap=confirmed`：生产当前仍是旧权限/路由状态，不能宣称真实会话、租户门禁或 API-first workbench 已在生产闭合。

冻结日期：`2026-06-23`

### 2.0.10 2026-06-23 Batch 8.3 生产部署差异只读复核状态

状态口径：本节只同步一次生产部署状态只读巡检和本地发布候选风险复核；本批未执行生产部署、生产写入型 E2E、数据库写入、schema 迁移、真实医院 SSO、真实会话签发或外部 AI provider 调用。

只读审计命令与报告：

- 首次命令使用旧预期值 `f864e370abd7309f6222376074b45ef2bc6c0ff4` 和默认 `expected_matching_embeddings=48985`，报告 `tmp/outputs/tencent-cloud-deployment-state-20260623-readonly.json` 返回 `status=fail`，阻断项为 `deploy-sha-mismatch` 和 `search-backend-not-ready`。
- 复核命令使用生产实际值 `expected_deploy_sha=550a445012267ba1211f5881b1d441264f3a3056` 和 `expected_matching_embeddings=49051`，报告 `tmp/outputs/tencent-cloud-deployment-state-20260623-readonly-current.json` 返回 `status=pass`。
- 复核报告显示 `app_health=healthy`、`postgres_health=healthy`、`nginx_config_test=True`、`audit_mount_present=True`、`search_backend_ready=True`、`latest_local_smoke_status=pass`。

2026-06-23 生产状态快照：

- 当时生产部署 SHA：`550a445012267ba1211f5881b1d441264f3a3056`。
- `medical_audit_app`：running，healthy，启动时间 `2026-06-19T07:30:29Z`。
- `medical_audit_pg`：running，healthy，启动时间 `2026-06-19T07:30:18Z`。
- `ai_video_nginx`：running，作为共享公网入口。
- PostgreSQL 检索后端：`backend=postgres`，`ready=true`，`matching_embedding_count=49051`。
- 最新可见备份包含 `pre-deploy-pr153-pgvector-hotfix-20260619` 相关 app/env/db/nginx/web 备份。

本地发布候选风险：

- 当前本地 `HEAD=b298c6c8b416b4863c948ff5c7d0cbfc5881ebab`，分支为 `codex/answer-provider-gate-plan`，对应远端分支已显示 `[gone]`。
- 当前工作树存在大量 tracked 修改和 untracked 文件，范围覆盖文档、脚本、认证路由、workbench API、前端壳层、登录页、智能体、文档、报告、规则、图谱、整改、归档等。
- `git diff 550a445012267ba1211f5881b1d441264f3a3056..HEAD` 不能作为准确发布清单，因为当前本地分支不是相对生产 SHA 的干净线性发布候选。
- 当前不能从本工作树直接生产部署；需要先在干净 release 分支或 worktree 中按 manifest 精确移植 Batch 7.9、8.1 和相关依赖，再重新跑完整质量闸。

当前边界：

- `production_current_state=healthy_at_550a445012267ba1211f5881b1d441264f3a3056`。
- `local_release_candidate_status=not_ready_dirty_untracked`。
- `production_permission_smoke_status=fail`：生产权限只读 smoke 仍以 Batch 8.2 报告为准，不因部署状态巡检通过而改变。
- `deploy_status=not_deployed`：本批没有生产发布动作。
- `no provider call`：本批没有调用生成模型或外部 AI provider。

冻结日期：`2026-06-23`

### 2.1 生产状态

> 2026-06-29 更新：已按生产部署授权把干净 `main@66b22d4549724a5065f396b94d6e1db15471983b` 部署到 `https://audit.lute-tlz-dddd.top`，部署戳为 `deploy-main-66b22d45-20260629T075824Z`。本次存在授权生产 live side effect（app rebuild/restart、Next static 同步、共享 Nginx 静态资产更新），但没有 schema migration、没有生产 env 写入、没有外部 answer provider call；`/Users/pray/project/medical_audit` 的 dirty frontend WIP 未纳入部署。2026-06-23 以前的报告仅作为历史证据，不再代表最新生产部署 SHA。
> 2026-06-30 更新：最新生产只读审计为 `tmp/outputs/tencent-cloud-deployment-state-doc-sync-20260630T035605.json`，当前生产 `.deploy-sha=a78bf8e5a1303178df26d03c6a687bd68f4512c2`。

- 生产域名：`https://audit.lute-tlz-dddd.top`
- 服务器：`101.34.52.232`
- 主机名：`VM-0-16-ubuntu`
- 用户：`ubuntu`
- SSH key：`ai_video.pem`，必须保留在本项目本地，不能删除。
- 当前生产部署 SHA：`a78bf8e5a1303178df26d03c6a687bd68f4512c2`
- `medical_audit_app`：running，healthy。
- `medical_audit_pg`：running，healthy。
- `ai_video_nginx`：running，作为共享公网入口。
- PostgreSQL 检索后端：`backend=postgres`，`ready=true`。
- Kimi embedding：`embedding_model=kimi-for-coding`，`embedding_dimension=1024`。
- 当前匹配 embeddings：`49051`。
- 当前 active index：主知识库仍为 `incremental-20260615-national-regulation-stable-20260615103344`，覆盖 `503` 个 source documents、`49051` 个 chunks 和 `49051` 条 embeddings；个人材料 active 版本为 `personal-materials-cos-staging-pr152-20260619`，覆盖 `4` 个 personal-material documents/chunks，使用 `fake/deterministic-token-hashing` staging embedding，不增加当前 `openai/kimi-for-coding` `matching_embedding_count=49051`。
- 最新项目成员生产写入 smoke 报告：`tmp/outputs/production-project-member-write-smoke-20260614.json`，状态 `pass`。
- 最新智能体生产写入 smoke 报告：`tmp/outputs/production-agent-write-smoke-20260614.json`，状态 `pass`。
- 最新 AI 数据分析生产上传解析 smoke 报告：`tmp/outputs/production-analytics-upload-smoke-20260614.json`，状态 `pass`。
- 最新 AI 数据分析上传留存 API 写入报告：`tmp/outputs/production-analytics-retention-write-e2e-20260615.json`，状态 `pass`。
- 最新 AI 数据分析上传留存 UI 联调报告：`tmp/outputs/production-analytics-ui-upload-retention-e2e-20260615.json`，状态 `pass`。
- 最新文档检索生产查询 smoke 报告：`tmp/outputs/production-documents-query-smoke-20260614.json`，状态 `pass`。
- 最新文档检索边界能力生产写入型 E2E 报告：`tmp/outputs/production-documents-write-e2e-20260615T122620+0800-verified.json`，状态 `pass`。
- 最新生产前端语义验收报告：`tmp/outputs/production-frontend-acceptance-batch0-latest-ui-20260629T2151.json`，状态 `pass`，覆盖 `21` 个路由、`42` 个检查，desktop/mobile 均通过，`p0=[]`、`p1=[]`；该报告为最新 UI/UX 生产基线只读验收。
- 最新生产部署状态审计报告：`tmp/outputs/tencent-cloud-deployment-state-doc-sync-20260630T035605.json`，状态 `pass`，`issues=[]`，`warnings=[]`，确认现网 `.deploy-sha=a78bf8e5a1303178df26d03c6a687bd68f4512c2`、app/postgres/clamav healthy、`audit_frontdoor_healthy=true`、`audit_next_static_healthy=true`、`audit_mount_present=true`、`search_backend_ready=true`、`matching_embedding_count=49051`，并校验部署戳 `20260629T183500-latest-ui` 的 app/env/db/nginx/web 备份存在。
- PR #175 目标 SHA 部署前差异审计：`tmp/outputs/tencent-cloud-deployment-state-target-pr175-readonly-20260629T034239Z.json` 为 `status=fail`，唯一 `issues=["deploy-sha-mismatch"]`；这是部署前只读历史证据，不再代表当前生产状态。
- 最新生产综合 E2E 报告：`tmp/outputs/production-e2e-smoke-after-deploy-20260629T183500-latest-ui.json`，状态 `pass`；TLS、health、PostgreSQL search backend、页面渲染、审计日志权限、query API citations、citation preview、chat dossier export 和边缘域名回归均通过。该 smoke 的 `query-api-with-citations` 仍为 `fallback_used=true`，不能解释为 no-fallback 真实生成能力。
- 最新 `/documents` 只读 probe 报告：`tmp/outputs/production-documents-readonly-probe-batch0-latest-ui-20260629T2151.json`，状态 `pass`，只调用 GET，不调用上传列表或下载元信息写审计日志的端点；`documents_role=auditor`、`source_collection_count=5`、`can_upload_personal=true`、`can_read_all_personal_uploads=false`、`search_backend_ready=true`、`matching_embedding_count=49051`、`production_write=false`、`provider_call=false`。
- 最新生产只读权限观测报告：`tmp/outputs/production-permission-readonly-smoke-after-frontend-2-main-20260628T1142.json`，`status=observed`、`probe_count=35`、`issue_count=0`、`production_side_effect=none`、`provider_call_status=not_called`。
- 最新个人材料索引 readiness 历史只读报告：`tmp/outputs/production-personal-material-indexing-readiness-after-staging-20260628T072621Z.json`，状态 `pass`，目标版本 `personal-materials-cos-staging-pr152-20260619`，当时 `ready_not_indexed_uploads=0`、`staged_uploads=4`、`personal_material_candidate_versions=1`、`personal_material_chunks=4`、`personal_material_active_versions=0`、`personal_material_active_chunks=0`；ready/not-indexed 队列已清零。
- 最新个人材料 live retrieval metadata gate 历史记录：dry-run 报告 `tmp/outputs/production-personal-material-live-retrieval-gate-dry-run-20260628T160140Z.json` 为 `ready_for_write`；正式执行报告 `tmp/outputs/production-personal-material-live-retrieval-gate-execute-20260628T160140Z.json` 为 `pass`，`production_write=true`、`db_write=true`，已将目标 candidate metadata 标记为 `live_retrieval_activated=true`。该记录为 2026-06-29 `index-activate` 的前置条件，不再代表当前目标版本状态。
- 最新个人材料 active retrieval 激活记录：激活前 DB 备份 `tmp/outputs/production-pre-index-activate-db-backup-personal-material-index-activate-20260628T165539Z.json` 对应远端 `/opt/medical-audit/backups/db/pre-index-activate-personal-material-index-activate-20260628T165539Z.sql.gz`，大小 `4832935545` bytes；`tmp/outputs/production-personal-material-index-activate-personal-material-index-activate-20260628T165539Z.json` 返回 `success=true`、`previous_status=candidate`、`deactivated_index_version_keys=[]`；reload 报告 `tmp/outputs/production-personal-material-search-backend-reload-personal-material-index-activate-20260628T165539Z-with-tenant.json` 返回 `backend=postgres`、`ready=true`、`matching_embedding_count=49051`。
- 最新个人材料激活后只读验收：`tmp/outputs/production-personal-material-post-activation-db-readonly-personal-material-index-activate-20260628T165539Z-retry1.json` 确认目标版本 `status=active`、`personal_material_active_versions=1`、`personal_material_active_chunks=4`，主 `openai/kimi-for-coding` active 版本仍存在；`tmp/outputs/production-personal-material-runtime-isolation-readonly-personal-material-index-activate-20260628T165539Z.json` 确认默认查询不包含 `personal-materials` 且 `personal_material_explicit_query_allowed_roles=[]`；公网权限 API 和 search-backend 状态分别见 `tmp/outputs/production-personal-material-permissions-api-readonly-personal-material-index-activate-20260628T165539Z.json`、`tmp/outputs/production-personal-material-public-search-backend-readonly-personal-material-index-activate-20260628T165539Z.json`。
- 最新 F2 answer provider gate：部署后生产-only 只读报告 `tmp/outputs/answer-provider-gate-readiness-production-only-after-deploy-main-66b22d45-20260629T075824Z.json` 仍为 `blocked`，blocker 为 `no-provider-api-key-env-set`。生产 `MEDICAL_AUDIT_KB_ANSWER_*` 与 `DEEPSEEK_API_KEY`、`OPENAI_API_KEY`、`ANTHROPIC_API_KEY`、`MOONSHOT_API_KEY` 均为 `UNSET`；本轮没有 provider call、没有写生产 env，不能进入 no-fallback 生产 E2E。
- 最新个人材料 active gate 复核：`tmp/outputs/production-personal-material-active-gate-doc-sync-20260630T035605.json` 为 `blocked`，issue 为 `target-index-version-not-candidate`；只读确认目标版本已是 `active`、`target_live_retrieval_activated=true`、`runtime_activation_guard_enforced=true`、`personal_material_active_chunks=4`，因此保持 `production unchanged`，不得重复执行 `index-activate` 或 search backend reload。
- 最新个人材料显式查询生产验收：`tmp/outputs/production-personal-material-explicit-query-scope-batch1-20260629T220732.json` 为 `pass`；默认 `/api/v1/query` 不返回 `personal-materials`，owner 显式查询命中 active 个人材料，非 owner 显式查询返回 `404`，`it-admin` 显式查询可 read-all。该验收会写 query history，不涉及上传、索引写入、`index-activate`、search backend reload 或 provider call。
- 最新个人材料 staging API 状态：PR #168 已将 `/documents/uploads/{upload_id}/index-ingestion` 路由、`document_upload_indexer` state wiring、权限门禁和显式生产写入脚本部署到生产；写入型 staging E2E `tmp/outputs/production-personal-material-index-staging-e2e-20260628T072621Z.json` 为 `pass`，已将 `document-upload-b15035ddbb79` 与 `document-upload-5fe687e5a5d0` 写入 candidate staging。旧 `/documents/uploads/{upload_id}/index` 仍不得被解释为 pgvector candidate staging。
- 最新 AI 数据分析留存历史本地联调截图：`tmp/screenshots/tmp-screenshot-analytics-retention-history-20260615.png`。
- 项目成员写入前 DB 备份：`/opt/medical-audit/backups/db/pre-project-member-write-smoke-20260614T212850+0800.sql.gz`，`gzip -t` 通过，权限 `600`，大小 `512950686` bytes，`sha256=2f0c119410ad58690934f555cf6d807a91c70cf6588a8189dcc4d058f0c4b8a0`。
- 项目成员生产写入结果：`CATALOG-LIMIT-202606` 新增 `member-custom-e152673f93f9`，成员数从 `4` 增至 `5`，数据库 `audit_project_members` 当前自定义记录数为 `1`。
- 智能体写入前 DB 备份：`/opt/medical-audit/backups/db/pre-agent-write-smoke-20260614T215017+0800.sql.gz`，`gzip -t` 通过，权限 `600`，大小 `512951265` bytes，`sha256=5d06dd8919f71f7d73446203424e8907dd1fc7677fc2a3d40e819bf6109026db`。
- 智能体生产写入结果：新增 `agent-custom-ec210547464a`，智能体列表从 `3` 增至 `4`，数据库 `audit_agents` 当前自定义记录数为 `1`。
- AI 数据分析生产上传结果：CSV 和 XLSX 上传均返回 `200`、`status=parsed`、`row_count=4`、`column_count=7`、`duplicate_row_count=1`，并识别金额/费用、患者/就诊、医保支付等审计信号；不支持的 `.txt` 扩展返回 `422 unsupported table file extension`。
- AI 数据分析留存历史生产结果：生产已应用 `analytics_upload_records` 表和索引；API 上传记录 `analytics-upload-b3a1898e38d1` 和 UI 上传记录 `analytics-upload-f39d652d3f81` 均完成历史查询、DB 行和宿主机留存文件 `sha256` 校验。
- 文档检索生产查询结果：全库重复收费、法规政策过滤和医保目录过滤 `POST /api/v1/query` 均返回 `200`，每个用例返回 `3` 条引用、证据分组和 `query_log_index`；首个引用 `chunk_id` 对应 `/pages/preview/{chunk_id}` 均返回 `200`。
- 文档检索边界能力生产结果：生产已应用 `document_upload_records` 表和索引；个人上传记录 `document-upload-1ba9d6e00cb7` 的 DB 行、宿主机文件 `/opt/medical-audit/document-uploads/2026/06/15/document-upload-1ba9d6e00cb7.txt` 和 `sha256=88fe90530c937d6ea6b534dafff636d5b7dec15b7c1131d786e5f00b007b466e` 均校验通过；普通审计员只能读取本人上传，其他普通审计员不可见，管理员可读全部个人上传；`/api/v1/query` 已验证 `source_collection=medical-insurance-laws` 在 citation 和 basis item 中直接回显。

生产结论：当前生产 runtime/source、Next static 门户 2.0、共享 Nginx 静态路由、检索、引用、预览、审计日志权限、文档检索查询、文档来源回显、个人材料留存/下载治理、个人材料 candidate staging、个人材料 active retrieval 激活与默认查询隔离、任务级复核写入链路、项目成员持久化写入链路、提示词型智能体持久化写入链路、AI 数据分析上传解析链路和 AI 数据分析上传留存/历史记录链路可用；不能据此宣称真实医院审计、真实生成模型 no-fallback、真实登录会话/医院 SSO、外部企业级 DLP/脱敏改写、个人材料对普通查询默认可见、证书级签章归档或案件级合规闭环已完成。

### 2.2 本地仓库状态

> 2026-06-28 更新：本节以下内容保留为 2026-06-23 历史工作区快照，不代表当前工作区状态；最新分支、部署和验收边界见 `2.0.14`。

- 当前工作区：`/Users/pray/project/medical_audit`
- 当前本地工作分支：`codex/answer-provider-gate-plan`，对应远端分支已显示 `[gone]`。
- 当前本地 `HEAD`：`b298c6c8b416b4863c948ff5c7d0cbfc5881ebab`。
- 当时生产运行代码 SHA：`550a445012267ba1211f5881b1d441264f3a3056`，以 `tmp/outputs/tencent-cloud-deployment-state-20260623-readonly-current.json` 为当时只读证据。
- 当前工作树存在大量 tracked 修改，覆盖文档、脚本、认证、文档、智能体、项目、查询、workbench、前端壳层和 E2E 等文件。
- 当前存在未跟踪资料、草稿、脚本和新代码文件：
  - `.codex/`
  - `.kiro/`
  - `.playwright-mcp/`
  - `docs/workflows/workflow-fullstack-completeness-audit-and-batch-execution-plan-stable.md`
  - `drafts/analysis/analysis-production-acceptance-p0-p1-*.md`
  - `drafts/analysis/analysis-reference-material-*.md`
  - `opendesign/`
  - `ref/`
  - `scripts/run-controlled-api-readonly-permission-smoke.py`
  - `scripts/run-local-fullstack-e2e.py`
  - `src/medical_audit_kb/api/auth.py`
  - `src/medical_audit_kb/api/auth_user_store.py`
  - `src/medical_audit_kb/api/docx_export.py`
  - `src/medical_audit_kb/api/routes_auth.py`
  - `src/medical_audit_kb/api/routes_workbench.py`
  - `web/public/`
  - `web/src/app/login/`
  - `web/src/components/shell/audit-user-context.tsx`
  - `web/src/lib/audit-user.ts`

仓库结论：当前本地状态适合继续做只读复核、文档同步和发布 manifest 梳理；不适合直接生产部署。进入发布准备前，必须从生产匹配基线或已确认主线创建干净 release 分支/worktree，按 manifest 精确移植目标能力，避免把历史 worktree、参考材料、草稿和本地工具目录混入交付分支。

### 2.3 产品状态

已完成：

- `AI智能审计管理系统` 门户壳层已部署。
- 生产静态页面已覆盖工作台、对话、智能体、智能体广场、知识库、文档、数据分析、图谱、规则、报告、整改、归档、项目、引导自查、知识查询和疑点入口。
- 知识库查询引擎已具备检索、引用型回答、原文预览、索引管理、评测和回滚治理。
- 复核任务台已具备任务级持久化、报告准备度预检、附件归档、正式报告签发冻结、整改跟踪和结案只读锁。
- HIS 数据底座、staging、snapshot、字段映射校验、`CHARGE-RULE-001` fixture 与 staging 执行路径已具备工程基础。
- 智能体持久化已完成生产写入型 E2E；生产 `/api/v1/agents` 返回 `SqlAlchemyAgentStore`，新增智能体刷新后仍可读，数据库 `audit_agents` 已落表。
- 项目成员持久化已完成生产写入型 E2E；`/api/v1/projects` 和 `/api/v1/projects/{project_key}/members` 均返回 `SqlAlchemyProjectMemberStore`，新增成员刷新后仍可读，数据库 `audit_project_members` 已落表。
- AI 数据分析表格上传解析已完成生产上传 E2E；CSV 和 XLSX 由 FastAPI 后端解析并返回字段画像、质量提示、重复行和审计信号。
- AI 数据分析上传留存和历史记录已完成生产部署与写入型 E2E；上传后写入 `analytics_upload_records`，原始文件按 `sha256` 可追溯留存在受控目录，前端 `/analytics` 可展示最近上传历史。
- 文档检索页已完成生产查询 E2E；`/api/v1/query` 可按来源过滤返回引用、证据分组和原文入口，`/pages/preview/{chunk_id}` 生产预览可打开。
- 文档检索搜索历史持久化已完成本地实现和联调；`/api/v1/query` 返回 `query_log_id`，`GET /api/v1/query/logs` 可从 `query_logs` 读取历史，`/documents` 可展示、刷新和回填历史。
- 文档检索剩余边界已完成生产部署和写入型 E2E；`/api/v1/query` 的 `citations` 与 `basis_groups.items` 直接回显 `source_collection`，`/api/v1/documents/permissions` 返回来源集合读权限，`/api/v1/documents/uploads` 支持个人材料留存、刷新后读取和普通审计员/管理员角色隔离，`/documents` 页面可展示权限状态和 `not-indexed` 上传历史；个人材料已有生产 candidate staging、live metadata 标记、active retrieval 激活和 search backend reload 证据，默认查询仍隔离 `personal-materials`。

未完成：

- 智能体提示词版本治理、版本对比 UI、逐行 diff、审核状态记录、审批通过才激活、上下架/停用、软归档、角色可见范围、调用记录和效果反馈已完成本地首切片；生产部署验收、正式租户 scope 和完整权限闭环仍未完成。
- 项目成员真实权限、邀请审批、成员禁用/移除和权限生效仍未完成；本轮只验证成员新增持久化。
- AI 数据分析病毒扫描、脱敏改写、对象存储、下载权限隔离、正式工作簿治理和长期存储生命周期策略仍未完成。
- 文档检索个人材料当前完成留存、角色读取隔离、本地策略扫描/DLP 标记、本地治理状态机、受控下载、生产 candidate staging、live metadata gate、active retrieval 激活和默认查询隔离；真实认证、外部杀毒/DLP 服务、脱敏改写、对象存储治理、个人材料显式查询授权策略和生产搜索历史列表/回填专项验收仍未完成。
- 多数门户模块仍由 `web/src/lib/portal-data.ts` 静态数据驱动。
- 生产数据仍以受控脱敏 fixture 为主要业务写入验收样本。
- Kimi 当前只验证为 embedding provider；线上答案生成模型未验证通过。
- 用户、角色、科室、全站权限、证书级电子签章、长期留存介质和真实外部告警端点未闭合。

### 2.4 Phase 1 基线验收状态

验收日期：`2026-06-14`

本轮 Phase 1 已完成，结论为 `pass`。

本地后端基线：

- `uv run ruff check src tests scripts`：通过。
- `uv run mypy src`：通过，`73` 个源码文件无类型错误。
- `uv run pytest`：通过，`241 passed`，`1` 个 `StarletteDeprecationWarning`，当前不阻断。

本地前端基线：

- `pnpm --dir web lint`：通过。
- `pnpm --dir web typecheck`：通过。
- `pnpm --dir web test`：通过，`10` 个 test files、`51` 个 tests。
- `pnpm --dir web build:static`：通过，静态构建生成 `20/20` 页面。
- 本轮修复了测试门禁债务：ESLint 忽略 `coverage/**`，Vitest 设置 `testTimeout=30000`，并补齐异步组件测试等待，避免 `act(...)` warning 污染验收信号。

生产只读验收：

- 报告：`tmp/outputs/production-e2e-smoke-phase1-readonly-20260614.json`
- 状态：`pass`
- 覆盖：TLS、health、PostgreSQL 检索、页面渲染、查询引用、原文预览、底稿导出和边缘域名回归。
- 边界：`query-api-with-citations.fallback_used=true`，只证明引用型 fallback 链路健康。

生产前端语义验收：

- 报告：`tmp/outputs/production-frontend-acceptance-phase1-20260614.json`
- 状态：`pass`
- 覆盖：`20` 个路由，桌面和移动共 `40` 次检查。
- 结果：`p0=[]`，`p1=[]`。
- 当时最新一次语义验收：`tmp/outputs/production-frontend-acceptance-latest.json`，状态 `pass`；`check_count=42`（21 个路由×2 viewport），`summary.api_checks` 中 `/audit/logs` 与 `/audit/logs/export` 均满足当时口径 `denied_status=403`、`allowed_status=200`，`p0=[]`、`p1=[]`。

生产写入型验收：

- 写入前 DB 备份：`/opt/medical-audit/backups/db/pre-review-write-smoke-phase1-20260614T105417+0800.sql.gz`
- 备份状态：`gzip -t` 通过，权限 `600`，大小约 `490M`，`sha256=169eeec6a99ff09e1a0a277d75f2f70620d01ff6b71dd03ea4c68a7b98cbb777`。
- 报告：`tmp/outputs/production-e2e-smoke-phase1-review-write-20260614.json`
- 状态：`pass`
- 覆盖：只读 smoke 全部步骤 + 复核任务创建/更新/导出。
- 写入结果：创建并更新 `review-task-0011`，`create_status=200`，`update_status=200`。
- 写入后状态审计：`pass`，`medical_audit_app` 和 `medical_audit_pg` 保持 healthy，检索后端仍 `ready=true`。

Phase 1 结论：工程基线、生产只读链路、门户语义验收和任务级写入型 smoke 均已通过；下一阶段应进入 Phase 2 产品集成债务治理。

### 2.5 Phase 2.1 本地验收状态

验收日期：`2026-06-14`

本轮 Phase 2.1 已完成，结论为 `pass`，范围限定为本地开发和联调环境。

后端集成：

- 新增 `audit_agents` SQLAlchemy 模型和正式 SQL schema。
- 新增 `SqlAlchemyAgentStore`、`InMemoryAgentStore` 和 `/agents` GET/POST API。
- `/agents` 返回系统默认智能体和自定义智能体；默认项标记为 `source=system-default`，自定义项标记为 `source=custom`。
- 新增自定义智能体写入持久化 store，刷新或重新创建 store 后仍可读取。

前端集成：

- `AgentWorkspace` 启动时读取 `/api/v1/agents`。
- 新增智能体必须通过 `createAuditAgent` POST 后端成功后才进入页面列表。
- 后端不可用时只显示默认内容和错误状态，不再伪造本地新增成功。

本地验收：

- `uv run ruff check src tests scripts`：通过。
- `uv run mypy src`：通过，`75` 个源码文件无类型错误。
- `uv run pytest`：通过，`244 passed`，`1` 个既有 `StarletteDeprecationWarning`。
- `pnpm --dir web lint`：通过。
- `pnpm --dir web typecheck`：通过。
- `pnpm --dir web test`：通过，`10` 个 test files、`54` 个 tests。
- `pnpm --dir web build:static`：通过，静态构建生成 `20/20` 页面。
- 本地浏览器联调：Next `127.0.0.1:3030` + FastAPI `127.0.0.1:8021`，`/agents` 页面显示默认智能体、后端连接状态和新增自定义智能体；刷新级 API 校验返回 `store.ready=true`。
- 浏览器截图：`tmp/screenshots/tmp-screenshot-agents-phase2-agent-persistence-20260614.png`。

边界：

- 本轮未执行生产部署。
- 本轮未对生产 PostgreSQL 应用 `audit_agents` schema。
- 本轮 FastAPI 联调使用本地临时 SQLite agent store，仅证明前后端协议和持久化行为。

### 2.6 Phase 2.2 本地验收状态

验收日期：`2026-06-14`

本轮 Phase 2.2 已完成，结论为 `pass`，范围限定为本地开发和联调环境。

后端集成：

- 新增 `audit_project_members` SQLAlchemy 模型和正式 SQL schema。
- 新增 `SqlAlchemyProjectMemberStore`、`InMemoryProjectMemberStore` 和项目成员 API。
- `/projects` 返回系统默认项目，并按自定义成员数量更新 `member_count`。
- `/projects/{project_key}/members` 返回系统默认成员和自定义成员；默认项标记为 `source=system-default`，自定义项标记为 `source=custom`。
- 新增自定义成员写入持久化 store，刷新或重新创建 store 后仍可读取。

前端集成：

- `ProjectManagementWorkbench` 启动时读取 `/api/v1/projects`。
- 切换项目时读取 `/api/v1/projects/{project_key}/members`。
- 新增成员必须通过 `createProjectMember` POST 后端成功后才进入页面列表。
- 后端不可用时只显示默认内容和错误状态，不再伪造本地新增成功。

本地验收：

- `uv run ruff check src tests scripts`：通过。
- `uv run mypy src`：通过，`77` 个源码文件无类型错误。
- `uv run pytest`：通过，`247 passed`，`1` 个既有 `StarletteDeprecationWarning`。
- `pnpm --dir web lint`：通过。
- `pnpm --dir web typecheck`：通过。
- `pnpm --dir web test`：通过，`10` 个 test files、`57` 个 tests。
- `pnpm --dir web build:static`：通过，静态构建生成 `20/20` 页面。
- 本地浏览器联调：Next `127.0.0.1:3030` + FastAPI `127.0.0.1:8021`，`/projects` 页面显示项目后端连接、成员后端连接和新增自定义成员。
- 刷新级 API 校验：FastAPI 与 Next 代理均返回 `store.ready=true`；`CATALOG-LIMIT-202606` 自定义成员排在默认成员前，项目成员数从 `4` 增至 `5`。
- 浏览器截图：`tmp/screenshots/tmp-screenshot-projects-phase2-member-persistence-20260614.png`。

边界：

- 本轮未执行生产部署。
- 本轮未对生产 PostgreSQL 应用 `audit_project_members` schema。
- 本轮 FastAPI 联调使用本地临时 SQLite project member store，仅证明前后端协议和持久化行为。

### 2.7 Phase 2.3 本地验收状态

验收日期：`2026-06-14`

本轮 Phase 2.3 已完成，结论为 `pass`，范围限定为本地开发和联调环境。

后端集成：

- 新增 `/analytics/table-upload` API，统一接收 multipart 表格上传。
- CSV 由 Python `csv` 解析，XLSX 和 XLSM 由 `openpyxl` 解析。
- 后端返回字段画像、字段类型、空值、去重值、样例值、重复行、质量提示、审计线索和建议。
- 不支持的扩展名返回 `422`，空文件、超大文件和无法解析的工作簿不返回伪成功状态。
- API 操作写入 `analytics-table-upload` operation log。

前端集成：

- `DataAnalysisWorkbench` 已移除浏览器本地 CSV parser。
- 上传 CSV、XLSX 或 XLSM 时统一调用 `uploadAnalysisTable` 走 `/api/v1/analytics/table-upload`。
- 页面展示后端返回的字段画像；后端失败时显示失败状态，不再伪造本地解析成功或排队成功。
- 右侧上传入口、终端状态和报告状态已改为后端解析口径。

本地验收：

- `uv run ruff check src tests scripts`：通过。
- `uv run mypy src`：通过，`78` 个源码文件无类型错误。
- `uv run pytest`：通过，`250 passed`，`1` 个既有 `StarletteDeprecationWarning`。
- `pnpm --dir web lint`：通过。
- `pnpm --dir web typecheck`：通过。
- `pnpm --dir web test`：通过，`10` 个 test files、`58` 个 tests。
- `pnpm --dir web build:static`：通过，静态构建生成 `20/20` 页面。
- 本地浏览器联调：Next `127.0.0.1:3030` + FastAPI `127.0.0.1:8021`，`/analytics` 页面上传 CSV 和 XLSX 均通过后端解析并渲染结果。
- 浏览器截图：
  - `tmp/screenshots/tmp-screenshot-analytics-phase23-csv-upload-20260614.png`
  - `tmp/screenshots/tmp-screenshot-analytics-phase23-xlsx-upload-20260614.png`

边界：

- 本轮未执行生产部署。
- 本轮未建立上传文件持久化、历史分析记录、病毒扫描、脱敏留存或对象存储。
- 本轮表格解析为本地瞬时分析能力，仅证明前后端上传解析协议和字段画像展示。

### 2.8 Phase 2.4 本地验收状态

验收日期：`2026-06-14`

本轮 Phase 2.4 已完成，结论为 `pass`，范围限定为本地开发和联调环境。

前端集成：

- `/documents` 已从静态跳转页调整为客户端 API-first 文档检索工作台。
- 文档源卡片可作为 `source_collections` 过滤条件传给后端 `/query`。
- 执行检索后展示后端返回的答案、引用数、引用片段、证据分组和 `/pages/preview/{chunk_id}` 原文入口。
- 搜索历史保留为本页快捷填充，不再伪装为后端历史记录。
- 对话文档和知识库文档示例列表保留为只读入口，继续作为静态示例资产。

本地验收：

- `uv run ruff check src tests scripts`：通过。
- `uv run mypy src`：通过，`78` 个源码文件无类型错误。
- `uv run pytest`：通过，`250 passed`，`1` 个既有 `StarletteDeprecationWarning`。
- `pnpm --dir web lint`：通过。
- `pnpm --dir web typecheck`：通过。
- `pnpm --dir web test`：通过，`10` 个 test files、`58` 个 tests。
- `pnpm --dir web build:static`：通过，静态构建生成 `20/20` 页面。
- 本地浏览器联调：Next `127.0.0.1:3030` + FastAPI `127.0.0.1:8021`，使用本地 fake search engine 验证 `/documents` 选择来源、提交检索、渲染引用和原文入口。
- 浏览器截图：`tmp/screenshots/tmp-screenshot-documents-phase24-api-search-20260614.png`。

边界：

- 本轮未执行生产部署。
- 本轮未新增文档持久化、搜索历史持久化、文档权限模型或个人知识库上传能力。
- 本轮浏览器联调使用本地 fake search engine，仅证明前端页面、Next 代理和 `/query` 协议闭环。

### 2.9 Phase 2.5 AI 数据分析留存历史本地验收状态

验收日期：`2026-06-15`

本轮 Phase 2.5 已完成本地实现和联调，结论为 `pass`，范围限定为本地开发和联调环境。

后端集成：

- 新增 `analytics_upload_records` 数据表和 SQLAlchemy model。
- 新增 `SqlAlchemyAnalyticsUploadStore` 和 `InMemoryAnalyticsUploadStore`。
- `/analytics/table-upload` 上传成功后写入原始文件、`sha256`、相对留存路径、字段画像摘要和上传历史记录。
- 新增 `GET /analytics/table-uploads`，返回最近上传记录和 store 状态。
- 新增 `MEDICAL_AUDIT_ANALYTICS_UPLOAD_ROOT`，未配置时使用 `index_root/analytics-uploads`。

前端集成：

- `/analytics` 页面加载最近上传历史。
- 上传成功后刷新历史列表，并展示 `upload_id`、`sha256` 和“已留存”状态。
- 历史读取失败不阻断文件上传，只显示历史不可用状态。

部署配置：

- 腾讯云 Compose 新增 `/app/analytics-uploads` 挂载。
- `medical-audit.env.example` 新增 `MEDICAL_AUDIT_ANALYTICS_UPLOAD_ROOT_HOST=/opt/medical-audit/analytics-uploads`。
- 部署脚本会创建 `/opt/medical-audit/analytics-uploads`，避免首次挂载目录权限漂移。

本地验收：

- `uv run pytest tests/knowledge_query/test_api.py tests/knowledge_query/test_sql_assets.py`：通过，`34 passed`，`1` 个既有 `StarletteDeprecationWarning`。
- `uv run ruff check src tests scripts`：通过。
- `uv run mypy src`：通过，`79` 个源码文件无类型错误。
- `pnpm --dir web lint`：通过。
- `pnpm --dir web typecheck`：通过。
- `pnpm --dir web test`：通过，`10` 个 test files、`65` 个 tests。
- `pnpm web:build:static`：通过，静态构建生成 `20/20` 页面。
- 本地浏览器联调：Next `127.0.0.1:3030` + FastAPI `127.0.0.1:8021`，`/analytics` 上传 `charge-retention-final.csv` 后页面显示“留存：已留存”，历史接口最新记录为 `analytics-upload-28a10ca6ac89`，`row_count=3`，`column_count=5`，`retention_status=retained`，无失败网络响应。
- 浏览器截图：`tmp/screenshots/tmp-screenshot-analytics-retention-history-20260615.png`。

边界：

- 本节只记录本地实现验收；生产部署与写入验收见 2.10。
- 本轮未实现病毒扫描、脱敏改写、对象存储、下载权限隔离或正式工作簿治理。

### 2.10 Phase 2.5 AI 数据分析留存历史生产验收状态

验收日期：`2026-06-15`

本轮 Phase 2.5 已完成生产部署和写入型验收，结论为 `pass`。

生产部署：

- 部署提交：`cbd93324119b28a7097712ea7b50b2d96b72de31`。
- 部署戳：`analytics-retention-20260615`。
- 生产已应用 `analytics_upload_records` 表和索引。
- 宿主机上传留存目录：`/opt/medical-audit/analytics-uploads`，目录权限 `ubuntu:ubuntu 775`。
- 写入前 DB 备份：`/opt/medical-audit/backups/db/pre-deploy-analytics-retention-20260615.sql.gz`，`gzip -t` 通过，`sha256=876bb9ecc1a0a39aa23085688c613000ca44dc4133b428ab2fdb3cb26d66f68d`。

生产验收：

- 部署后基础 smoke：`tmp/outputs/production-e2e-smoke-after-analytics-retention-deploy-20260615.json`，状态 `pass`。
- 部署状态审计：`tmp/outputs/tencent-cloud-deployment-state-after-analytics-retention-deploy-20260615.json`，状态 `pass`，`issues=[]`。
- 生产前端验收：`tmp/outputs/production-frontend-acceptance-after-analytics-retention-deploy-20260615.json`，状态 `pass`，`p0_count=0`、`p1_count=0`。
- API 上传留存写入验收：`tmp/outputs/production-analytics-retention-write-e2e-20260615.json`，状态 `pass`；记录 `analytics-upload-b3a1898e38d1` 的历史、DB 行和宿主机文件 `sha256` 均校验通过。
- UI 上传留存联调：`tmp/outputs/production-analytics-ui-upload-retention-e2e-20260615.json`，状态 `pass`；记录 `analytics-upload-f39d652d3f81` 由 `/analytics` 页面上传产生，历史、DB 行和宿主机文件 `sha256` 均校验通过。
- UI 截图：`tmp/screenshots/production-analytics-ui-upload-retention-20260615.png`。

边界：

- 上传留存文件当前由容器写出，宿主机文件权限为 `root:root 644`；功能可用，但人工清理需要 sudo 或后续补容器用户/文件权限治理。
- 本轮未实现病毒扫描、脱敏改写、对象存储、下载权限隔离、正式工作簿治理或长期存储生命周期策略。

### 2.11 Phase 2.6 文档检索搜索历史本地验收状态

验收日期：`2026-06-15`

本轮 Phase 2.6 已完成本地实现和联调，结论为 `pass`，范围限定为本地开发和联调环境。

后端集成：

- 新增 `QueryHistoryStore` 抽象、`SqlAlchemyQueryHistoryStore` 和 `InMemoryQueryHistoryStore`。
- 复用既有 `query_logs` 表持久化搜索历史，不新增平行表。
- `/query` 写入查询问题、过滤条件、答案摘要和引用 chunk，并在响应中返回 `query_log_id`。
- `GET /query/logs?limit=` 返回最近搜索历史和 store 状态；持久化 store 不可用或读取失败时回退进程内历史并显式标记 `store.ready=false`。
- 历史写入失败不阻断主检索结果，只在 operation payload 中记录结构化 `query_history_error`。

前端集成：

- `/documents` 页面加载 `GET /api/v1/query/logs?limit=8`。
- 查询成功后刷新历史列表。
- 点击历史项可回填问题和来源集合过滤条件。
- 历史读取失败不阻断文档检索，只显示历史不可用状态。

本地验收：

- `uv run pytest`：通过，`255 passed`，`1` 个既有 `StarletteDeprecationWarning`。
- `uv run ruff check src tests scripts`：通过。
- `uv run mypy src`：通过，`80` 个源码文件无类型错误。
- `pnpm --dir web lint`：通过。
- `pnpm --dir web typecheck`：通过。
- `pnpm --dir web test`：通过，`10` 个 test files、`66` 个 tests。
- `pnpm web:build:static`：通过，静态构建生成 `20/20` 页面。
- 本地浏览器联调：Next `127.0.0.1:3030` + FastAPI `127.0.0.1:8021`，使用本地 fixture search engine 和 `tmp/debug` SQLite 验证 `/documents` 初始历史为空、提交检索后历史刷新、刷新页面后历史仍从 `SqlAlchemyQueryHistoryStore` 回读。
- 浏览器截图：`tmp/screenshots/tmp-screenshot-documents-history-persistence-20260615.png`。

边界：

- 本节只记录 PR #81 搜索历史本地实现验收；PR #83 合并后的生产部署和写入型 E2E 见 2.12。
- 本轮未实现个人知识库上传、文档权限模型或响应中的 `source_collection` 直接回显。

### 2.12 Phase 2.6/2.7 文档检索边界能力生产验收状态

验收日期：`2026-06-15`

本轮已完成 PR #83 生产部署和 `/documents` 写入型验收，结论为 `pass`。

生产部署：

- 部署提交：`f864e370abd7309f6222376074b45ef2bc6c0ff4`。
- 部署戳：`20260615T121812+0800`。
- 生产已应用 `document_upload_records` 表和索引。
- 宿主机个人文档留存目录：`/opt/medical-audit/document-uploads`。
- 写入前 DB 备份：`/opt/medical-audit/backups/db/pre-deploy-20260615T121812+0800.sql.gz`，大小 `512967344` bytes。

生产验收：

- 部署后基础 smoke：`tmp/outputs/production-e2e-smoke-after-deploy-20260615T121812+0800.json`，状态 `pass`。
- 部署状态审计：`tmp/outputs/tencent-cloud-deployment-state-after-documents-boundary-deploy-20260615.json`，状态 `pass`，`issues=[]`。
- 生产前端验收：`tmp/outputs/production-frontend-acceptance-after-documents-boundary-deploy-20260615.json`，状态 `pass`，覆盖 `21` 个路由、`42` 个检查，`p0_count=0`、`p1_count=0`。
- `/documents` 写入型 E2E：`tmp/outputs/production-documents-write-e2e-20260615T122620+0800-verified.json`，状态 `pass`。
- 上传记录：`document-upload-1ba9d6e00cb7`，文件名 `production-documents-write-e2e-20260615T122620+0800.txt`，上传人 `documents-e2e-owner-20260615T122620+0800`。
- DB 行验证：`retention_status=retained`、`index_status=not-indexed`、相对路径 `2026/06/15/document-upload-1ba9d6e00cb7.txt`。
- 宿主机文件验证：`/opt/medical-audit/document-uploads/2026/06/15/document-upload-1ba9d6e00cb7.txt`，`sha256=88fe90530c937d6ea6b534dafff636d5b7dec15b7c1131d786e5f00b007b466e`。
- 角色读取隔离：本人列表包含该上传；其他普通审计员列表不包含该上传；管理员列表包含该上传并返回 `can_read_all_personal_uploads=true`。
- 来源集合回显：`/api/v1/query` 使用 `source_collections=["medical-insurance-laws"]` 返回 `citation_count=1`、`basis_item_count=1`，citation 和 basis item 均回显 `medical-insurance-laws`，同时返回 `query_log_id=9d6ec14e-1406-4e15-88b1-5978f6588891`。

边界：

- 上传材料当前为 `not-indexed`，只完成留存和读取隔离，不进入知识库检索。
- 查询响应仍为 `fallback_used=true`，只证明引用型 fallback 和来源过滤链路健康，不证明真实生成模型能力。
- 本轮不覆盖真实登录会话、组织级权限、病毒扫描、DLP/脱敏改写、对象存储、下载权限隔离、个人材料入索引或长期存储生命周期策略。
- 早先三份 `production-documents-write-e2e-*.json` 失败报告属于检查脚本 SQL quoting 问题，已被 `production-documents-write-e2e-20260615T122620+0800-verified.json` 以显式 DB 行和宿主机文件校验覆盖。

### 2.13 国家规章平台文档增量入库与生产激活状态

验收日期：`2026-06-15`

本轮国家规章平台资料补充已完成生产激活，结论为 `pass`。

数据与索引：

- 资料来源：`data/国家规章平台文档.zip`。
- 生产资料路径：`/opt/medical-audit/app/data/医保审核前期资料/全量法律/国家规章平台文档`。
- active index：`incremental-20260615-national-regulation-stable-20260615103344`。
- source package：`source-package-national-regulation-stable-incremental-20260615103344`。
- active 计数：`503` 个 source documents、`49051` 个 chunks、`49051` 条 embeddings。
- 本轮新增国家规章平台入库文档：`17` 个；新增 chunks：`66`。

验收证据：

- 固定 52 case 检索评测：`52/52` 通过。
- 新增文档检索评测：`6/6` 通过。
- 新增文档答案评测：`4/4` 通过；仍为 citation fallback answer，不代表真实生成模型能力可用。
- 生产 E2E：`tmp/outputs/production-e2e-smoke-after-national-regulation-app-restart-20260615.json`，状态 `pass`。

异常与处置：

- 第一次全量重建候选 `full-rebuild-20260615093424` 因固定 52 case 回归为 `51/52` 未激活，并已置为 `inactive`。
- 激活后 `/pages/chat` 曾返回 `500`，日志为 `TemplateNotFound: chat.html`；复核确认不是本地缺模板或 wheel 缺模板，而是运行中 `uvicorn` 子进程持有旧导入路径。
- 已仅重启 `medical_audit_app` 修复；未修改 `medical_audit_pg`、`medical_audit_pgdata` 或共享 `ai_video_nginx`。重启后 `/pages/chat` 内外网均返回 `200`，重启后日志未再出现 `TemplateNotFound`。

## 3. 债务分级

| 等级 | 定义 | 处理原则 |
| --- | --- | --- |
| P0 | 会导致产品能力被误判、生产交付边界不清、真实业务验收不可执行或安全合规风险扩大的债务 | 先处理，不进入新功能扩张 |
| P1 | 不阻断当前生产运行，但阻断 V1.0 闭环、UAT 或持续开发效率的债务 | 进入最近两个开发批次 |
| P2 | 影响维护成本、认知清晰度、目录卫生和长期扩展性的债务 | 纳入持续治理 |

## 4. P0 债务台账

| 编号 | 类型 | 债务 | 当前证据 | 影响 | 处置计划 | 完成门禁 |
| --- | --- | --- | --- | --- | --- | --- |
| P0-01 | 产品集成债务 | 门户核心模块仍以静态数据和本地 state 为主 | `/agents` 和 `/projects` 已完成生产写入验收；`/analytics` 已完成生产上传解析、上传留存和历史记录验收；`/documents` 已完成生产查询、来源集合回显、文档权限接口和个人材料留存写入型验收；个人材料 candidate staging、live retrieval metadata gate、`index-activate`、search backend reload、激活后只读/API 验收和显式查询 owner/read-all 生产验收均已完成，且默认查询仍隔离 `personal-materials`；本地已补 `title_only`、材料治理状态机、本地策略扫描/DLP 标记和受控下载；其余模块仍多依赖 `portal-data` | 页面存在但业务闭环不完整，容易误判为功能已完成 | 下一步补外部杀毒/DLP 服务、脱敏改写、对象存储治理、真实认证权限、知识库/图谱/报告/整改页面 API、生产搜索历史专项验收和审计策略验收 | 新增/查询/刷新后数据仍存在；上传文件可追溯留存并通过治理门禁；前端测试、API 测试和生产写入验收通过；active retrieval 已完成 runtime 激活、默认隔离和显式查询 owner/read-all 生产验收，后续需补 DLP/脱敏、外部扫描、对象治理和审计策略验收 |
| P0-02 | 真实数据债务 | 生产验收主要基于受控脱敏 fixture | 生产文档明确 fixture 只证明链路 | 不能进入真实医院 UAT | 获取院方 DDL、字段字典、脱敏样本，执行 staging 验收 | `his-staging-acceptance` 对真实样本 PASS |
| P0-03 | AI 生成债务 | 线上答案生成 provider 未验证通过 | 2026-06-29 生产-only readiness：生产仅 `KIMI_API_KEY=SET`，`DEEPSEEK_API_KEY`、`OPENAI_API_KEY`、`ANTHROPIC_API_KEY`、`MOONSHOT_API_KEY` 与全部 `MEDICAL_AUDIT_KB_ANSWER_*` 均为 `UNSET`；综合 readiness 仅说明本地 shell 有 Anthropic smoke 前置条件；生产 query smoke 仍为 fallback | 不能宣称 no-fallback AI 生成审计结论能力 | 先取得明确授权的一次 provider smoke；provider smoke 和真实答案评测通过前不得写生产 env，未通过前保持 generate-or-safe-fallback / citation fallback 为产品边界 | `answer-provider-smoke`、真实生成评测和生产 `--require-generated-answer` E2E 全部 PASS |
| P0-04 | 权限安全债务 | 真实 SSO、登录会话签发和写入型生产权限验收未完成 | 已新增本地 `auth_departments`、`auth_users`、`auth_user_role_assignments` 和 `/auth/*` 过渡层 API；`require_permission` 已优先使用持久化 `active/global/project` 角色并拒绝 `disabled/pending` profile；受控 API 鉴权中间件要求 `X-Tenant-Id` 并写 `authorization-denied`；2026-06-30 生产只读权限 smoke 已在最新 UI/UX 基线上返回 `status=observed`、`probe_count=35`、`issue_count=0`；新增 `scripts/audit-auth-sso-contract-readiness.py` 与 `pnpm auth:sso-contract-readiness`，当前 P0-04 合同 readiness 报告 `status=blocked`，阻塞项为可信代理/签名密钥/CIDR/关闭 legacy header 均未配置 | 仍无法满足生产级审计系统完整权限边界；只读 GET 权限通过不等于真实 SSO 或写入型验收完成 | 在现有本地权限底座上继续补真实会话认证或可信 SSO 代理、正式租户身份来源、网关注入策略和生产写入型权限复验 | 未授权路径 401/403；审计日志记录访问拒绝；禁用用户无法继续访问受控入口；`production:permission-readonly` 持续通过；`auth:sso-contract-readiness` 不再 blocked；真实会话/SSO smoke 通过；授权写入型权限 E2E 通过 |
| P0-05 | 合规闭环债务 | 证书级电子签章、长期留存介质、对象存储、脱敏改写和外部治理服务未形成可验收闭环 | 当前生产只读曾观测到 `virus_scan_provider=clamav-sidecar`、`dlp_review_provider=ruleset-v1`；新增 `scripts/audit-document-governance-contract-readiness.py`、`pnpm document:governance-contract-readiness`、非生产 `configs/knowledge-query-engine-document-governance-ready-profile.yaml`、`pnpm document:governance-ready-profile`、`scripts/prepare-document-governance-production-readonly-plan.py`、`pnpm document:governance-production-readonly-plan`、`scripts/run-document-governance-production-readonly-precheck.py`、`pnpm document:governance-production-readonly-precheck`、`scripts/prepare-document-governance-production-readonly-observation-coverage.py`、`pnpm document:governance-production-readonly-coverage`、GET-only `/api/v1/documents/governance/status`、GET-only `/api/v1/deployment/metadata` 和生产只读 probe 的治理状态/部署 SHA 检查；coverage gate 返回 `status=ready`，26 个治理字段已有 redacted status 契约，`expected_deploy_sha` 已有本地 deployment metadata 只读契约 | 报告、归档和个人材料治理不能作为完整合规交付；非生产 ready-profile、生产只读准备包、precheck、coverage gate、governance status endpoint 和 deployment metadata endpoint 只证明合同/计划/授权清单/本地只读契约，不能替代生产部署后 L3 只读、授权写入型治理 E2E 或证书级签章恢复演练 | 将包含 deployment metadata 与 governance status endpoint 的主线按批准路径部署；部署后在明确只读授权下执行更新后的 production documents readonly probe；生产 env 变更、外部 provider smoke、对象存储写入和写入型 E2E 必须单独授权 | 默认 `document:governance-contract-readiness` 不再 blocked；生产只读复核通过且覆盖 deploy SHA 与 governance status；有备份/授权/回滚路径的写入型治理 E2E、归档包、签章、验签和恢复演练通过 |
| P0-06 | 状态源债务 | 本地分支、生产 SHA、远端主线、多个 worktree 容易产生认知漂移 | 2026-06-28 已将 runtime/source reconciliation 通过 PR #161 合入并部署到生产；随后补齐共享 Nginx 静态路由源配置和部署状态 gate（medical-audit PR #162、AI_vedio PR #56），再将 Frontend 2.0 通过 PR #163 部署到生产。PR #168 已将个人材料 pgvector 候选入库 API 部署到生产；PR #170/#171 已将默认查询隔离、live retrieval metadata gate 和 SQL 修复部署到生产；2026-06-29 已授权执行 runtime DB `index-activate` 和 search backend reload。2026-06-30 只读复核确认最新生产 `.deploy-sha=a78bf8e5a1303178df26d03c6a687bd68f4512c2`，app/postgres/clamav healthy，`audit_next_static_healthy=true`，`matching_embedding_count=49051`；后续 docs-only 远端主线领先生产 `.deploy-sha` 时，不代表生产代码部署改变。 | 后续若只看 `origin/main` 或旧 worktree，仍可能误判生产正在运行的代码 SHA；docs-only/test-only merge 仍需明确 `production unchanged`，runtime DB 状态变更也必须单独记录 | 将 P0-06 从发布阻断项降级为持续监控项：每次部署前先核对 `origin/main`、干净 release worktree、生产 `.deploy-sha`、共享 Nginx 源配置、runtime DB 状态和验收脚本口径；docs-only/test-only 合并不得自动声称生产已同步 | 生产状态审计、生产 smoke、生产前端验收、权限只读观测和 runtime DB 状态复核均通过；文档记录 `main/prod SHA` 与 runtime 状态边界；后续部署继续执行 static asset gate |

## 5. P1 债务台账

| 编号 | 类型 | 债务 | 当前证据 | 影响 | 处置计划 | 完成门禁 |
| --- | --- | --- | --- | --- | --- | --- |
| P1-01 | 本地/生产一致性债务 | 本地 Kimi 运行态缺少同生产一致的安全加载流程 | 本地缺少 `KIMI_API_KEY` 时 PostgreSQL backend load 返回 409 | 本地复现生产问题困难 | 建立本地 Kimi profile 文档和安全 env 加载脚本 | 本地只读 UI smoke 可复现生产检索 |
| P1-02 | 知识库资料债务 | `pending_files=13` 未闭合 | 图片需 OCR 或替换，压缩包需解包去重 | 新资料增量发布质量受限 | 执行 pending 文件分类处理和候选索引流程 | pending 队列归零或有明确豁免记录 |
| P1-03 | HIS 产品化债务 | HIS 字段映射、确认、版本发布缺少页面化流程 | CLI 已有，UI 未闭合 | 院方业务人员难以参与字段确认 | 补字段映射 UI、确认记录和版本发布门禁 | 字段映射可由页面提交并进入审计日志 |
| P1-04 | 规则治理债务 | 结构化规则、医院本地覆盖和规则评审发布流程未产品化 | `CHARGE-RULE-001` 已有工程路径，规则库 UI 只读 | 规则变更不可治理 | 建立规则版本、评审、发布、回滚 UI/API | 规则发布和回滚有审计日志 |
| P1-05 | UAT 债务 | 缺少院方 UAT 用例、验收记录和签收材料 | 现有 smoke 主要为工程验收 | 无法形成客户验收证据 | 建立 UAT case matrix、验收脚本和问题闭环 | P0/P1 UAT 问题为 0 |
| P1-06 | 文档同步债务 | 正式文档存在阶段性漂移风险 | 本轮已同步开发计划、部署工作流和本台账，后续仍需随功能落地持续校准 | 新成员和部署决策容易误读 | 持续同步 PRD、开发计划、部署工作流和本台账 | 正式文档状态一致 |

## 6. P2 债务台账

| 编号 | 类型 | 债务 | 当前证据 | 影响 | 处置计划 | 完成门禁 |
| --- | --- | --- | --- | --- | --- | --- |
| P2-01 | 目录治理债务 | 本地存在 `.DS_Store`、缓存、参考材料和多个草稿目录 | 根目录和子目录有本地系统文件及未跟踪目录 | 降低可导航性，增加误提交风险 | 保留必要参考资料，清理或归档无效本地文件 | `git status` 只显示本轮目标资产 |
| P2-02 | 仓库体积债务 | 当前工作区约 `3.7G` | `du -sh .` | clone、索引和扫描成本升高 | 复核 `data/`、`node_modules/`、缓存和历史输出 | 大文件有明确归属和忽略规则 |
| P2-03 | 测试资产债务 | 生产验收脚本已具备，但产品模块联调用例不足 | 前端 acceptance 偏语义可达性 | 难捕捉持久化和权限回归 | 为 agents/projects/analytics 增加 API+UI E2E | 新模块每次 PR 自动跑关键路径 |

## 7. 执行路线

### Phase 0：状态冻结与台账同步

目标：完成当前事实冻结、债务台账、正式文档同步和后续分支边界。

任务：

- 新增本台账。
- 同步开发计划中的当前状态。
- 同步腾讯云部署工作流中的 2026-06-14 生产状态。
- 明确后续功能开发必须从干净 `codex/` 分支开始。

完成门禁：

- `git status --short --branch` 可解释。
- 生产状态审计通过。
- 正式文档不再把已完成门户壳层写成未完成，也不把静态 UI 写成后端闭环。

### Phase 1：基线复核

状态：已完成，完成日期 `2026-06-14`。

目标：确保本地、生产、测试和部署边界一致。

任务：

- 执行 Python `pytest`、`ruff`、`mypy`。
- 执行前端 `lint`、`typecheck`、`test`、`build:static`。
- 执行生产只读 smoke。
- 在备份后执行写入型 smoke。
- 输出基线验收报告。

完成门禁：

- 代码测试已通过，剩余 `StarletteDeprecationWarning` 记录为 P2 依赖观察项。
- 生产只读 smoke 已通过。
- 生产前端语义验收已通过，`p0=[]`，`p1=[]`。
- 写入前 DB 备份已通过完整性校验。
- 生产写入型 smoke 已通过，创建并更新 `review-task-0011`。
- 本地与生产的 Kimi 配置差异仍保持文档化边界：生产 Kimi embedding 可用，本地缺少 `KIMI_API_KEY` 时不能加载 PostgreSQL 检索后端。

### Phase 2：产品集成债务治理

目标：把门户核心页面从 UI 壳层推进到可持久化业务模块。

优先顺序：

1. 智能体 CRUD 和提示词版本：生产写入型 E2E 已完成；提示词版本治理、版本对比 UI、逐行 diff、审核状态记录、审批通过才激活、上下架/停用、软归档、角色可见范围、调用记录、效果反馈、项目范围校验和本地租户头契约已完成本地首切片；生产部署验收、生产智能体调用统计、正式租户 scope 和完整权限闭环待后续阶段。
2. 项目成员管理 API 和页面持久化：生产写入型 E2E 已完成；真实权限、邀请审批、禁用/移除和成员权限生效待后续阶段。
3. 表格上传分析后端和工作簿解析任务：生产上传解析、上传留存和历史记录写入型 E2E 已完成；病毒扫描、脱敏改写、对象存储、下载权限隔离和正式工作簿治理待后续阶段。
4. 文档检索 API-first 接入：生产查询、搜索历史写入信号、来源集合回显、文档权限接口和个人材料留存写入型 E2E 已完成；本地已补 `title_only`、材料治理状态机、本地策略扫描/DLP 标记和受控下载隔离；真实认证、外部杀毒/DLP 服务、脱敏改写、对象存储、个人材料真实入索引和生产搜索历史列表/回填专项验收待后续阶段。
5. 知识库、图谱、报告、整改页面逐步接真实 API。

完成门禁：

- 刷新页面后新增数据仍存在。
- API 测试、前端测试和最小 E2E 均通过。
- 生产前端变更必须执行 `pnpm production:frontend-acceptance -- --base-url https://audit.lute-tlz-dddd.top --admin-role it-admin`，且 `p0=[]`、`p1=[]`、审计日志查询和导出 API 均满足无角色 `401/403`、管理员角色 `200`。
- 页面文案不再暗示未完成能力已经完成。

### Phase 3：真实 HIS 审计 MVP

目标：完成单院真实样本的 HIS 审计闭环。

任务：

- 获取院方 DDL、字段字典、脱敏样本和验收口径。
- 完成字段映射确认和版本发布。
- 执行 staging 导入、snapshot、规则运行、疑点入库。
- 形成复核任务、证据链、底稿和报告草稿。

完成门禁：

- 真实样本 `his-staging-acceptance` PASS。
- `CHARGE-RULE-001` 对真实样本可复核运行。
- 疑点证据链可追溯到原始行、规则版本和知识依据。

### Phase 4：安全与合规闭环

目标：补齐生产审计系统所需的权限和归档能力。

任务：

- 在已建立的本地用户、角色、部门、项目授权和租户头过渡层基础上，补真实登录会话、医院 SSO claims、正式租户身份来源、账号移除/停用治理和生产权限验收。
- 迁移 API secret、Kimi key、HMAC secret 到服务器级 secret 或 Docker secret。
- 接入对象存储、病毒扫描、证书级电子签章和长期留存介质方案。
- 完成未授权访问、签章验签、归档恢复演练。

完成门禁：

- 权限绕过测试失败即阻断。
- 签章和归档验签可独立复现。
- 备份恢复演练通过。

### Phase 5：UAT 与生产硬化

目标：形成可交付给院方的验收包。

任务：

- 建立 UAT case matrix。
- 建立问题登记、修复、复测和签收流程。
- 执行性能、备份恢复、回滚、监控告警和共享 Nginx 回归。

完成门禁：

- UAT P0/P1 为 0。
- 回滚方案可执行。
- 生产监控、告警、备份、恢复均有证据。

## 8. 后续执行规则

- 新功能开发必须从干净 `codex/` 分支开始。
- 不在生产部署同步中包含 `drafts/`、`ref/`、`opendesign/`、`tmp/`、密钥或 env 文件。
- `ai_video.pem` 保留在本地，不进入 Git，不删除。
- 每次声称完成前必须同时给出代码证据、页面证据、测试证据和生产边界。
- 每次生产写入前必须先有备份和回滚路径。
- 每次文档同步必须明确 `fixture`、`fallback`、`dry-run`、`read-only` 和 `production` 的边界。

### 2.0.11 2026-06-23 Batch 8.4 发布候选合入 main 与生产部署
- 发布候选 `codex/medical-audit-release-auth-workbench-20260623`(main+5) 已推远端并合入 main，main tip `c10b3d3b`。
- 生产已部署 `c10b3d3b` 并 `--apply-schema`；app/pg/clamav 均 healthy，`matching_embedding_count=49051`。
- 受控 API 鉴权已在生产 enforce 生效：`production:frontend-acceptance` 通过，`p0=0 p1=0`，`/audit/logs` 与 `/audit/logs/export` 满足无角色 401、管理员 200。
- 写入前已备份：`pre-deploy-20260623T171314`（app/env/db 1.0G/nginx/web 全套）。
- 边界：部署后 e2e smoke 因重启窗口瞬时 reset 记为 fail，已由 frontend-acceptance 与状态审计(app_health=healthy)覆盖；P0-04 生产鉴权侧实质推进，真实 SSO/会话签发仍待后续。

### 2.0.12 2026-06-24 Batch 8.5 F2 检索/拒答调优工具链与召回杠杆（本地切片）

状态口径：本节同步 F2 调优一批本地代码切片与 bench 工具链；未 push、未跑生产 bench、未改生产默认 reranker/来源权重、未写 answer provider env、未部署。E3/E4（`785a2bc0`）生产部署缺口仍独立待办（见文末）。

交付切片（均从 `origin/main = d3ca0a1a` 拉干净分支，沙箱四证绿，以 patch 交付，待本机全量门禁 + push）：

- B2 引用标记鲁棒性（分支 `codex/answer-marker-robustness`）：`generation/answer_builder.py:_contains_citation_marker` 改为容忍 `[C1]`/`【C1】`/`(C1)` 等变体并带字母数字边界保护，消除真实生成激活后的“假回退”；红线守住（无任何 `C<编号>` 仍判 fallback）。
- C1 调优测试台 `scripts/run-answer-provider-tuning-bench.py`（分支 `codex/answer-tuning-bench-and-cases`，下同）：进程内 pgvector + provider 只读复刻，输出每问题 fallback/refusal/recall 及强/弱召回分组的 generate-or-safe-fallback 指标。
- C2 弱召回评测集：`configs/evaluation/knowledge-query-answer-evaluation-cases-v1.yaml` 8→10 用例；目录类（ICD `A00.0`/DRG `0000`/药品）打 `weak-recall` 标签；新增 `I10`/`E11` ICD 用例（标 `needs-corpus-verification`，required 术语待对照真实语料确认）。
- A1 域码感知 reranker：`retrieval/rerank.py` 新增 `DomainAwareRerankProvider`（精确域码命中强加权，确定性、零外部依赖，非 cross-encoder）+ `rerank_provider_from_name` 工厂；bench `--rerank {fake,domain}` 做 A/B；生产默认仍 `Fake`。
- A2 来源加权杠杆：`retrieval/postgres_search.py:load_postgres_hybrid_search_engine` 加 `source_collection_weights` 透传 + bench `--source-weights-file`；`DEFAULT_SOURCE_WEIGHTS` 未改。

本地验收证据（沙箱子集，py3.14 临时 venv + 最小依赖）：

- B2：`test_citations.py` + `test_answer_providers.py` `16 passed`；`ruff`/`mypy` 绿。
- C1/C2/A1/A2：`test_rerank.py` + `test_hybrid_search.py` + `test_answer_datasets.py` `15 passed`；bench `--help` 导入冒烟 `exit 0`；`ruff`/`mypy` 绿。
- 汇总器 `f2-bench-summary.py`：合成数据验证，正确显示弱召回逐题 `refuse→gen` 翻转。
- 一条龙脚本 `f2-bench-and-ship.sh`：`bash -n` 通过、全 dry-run `exit 0`、密钥不回显（`leak=0`）。

生产 embedding 参数（已从架构稳定文档 + 仓库 13 处确认，bench 须同源）：`openai` 兼容 / `kimi-for-coding` / dim `1024` / base_url `https://api.kimi.com/coding/v1` / `KIMI_API_KEY`；`kimi-for-coding` 仅作 embedding（`/chat/completions` 返回 403），答案生成用 DeepSeek。

当前边界：

- `local verification (subset) only`：沙箱只跑相关子集门禁；本机须补全量 `uv run ruff check . && uv run mypy src && uv run pytest`。
- `not pushed / not benched`：切片未 push，未在生产 pgvector + DeepSeek 上跑 bench。
- `production defaults unchanged`：生产 reranker 仍 `Fake`、来源权重仍默认、未写 answer provider env、未部署。
- `manual review required`：A1/A2 真实增益须 bench 量化；`I10`/`E11` 用例 required 术语待对照语料；是否切默认 reranker / 是否上 cross-encoder 待 bench 数据后定。

并行未闭：E3/E4（`785a2bc0`）仍待部署生产（缺口 `c10b3d3b..d3ca0a1a`，纯前端 + 文档，部署不带 `--apply-schema`；详见 E3/E4 生产落地 handoff）。

冻结日期：`2026-06-24`

### 2.0.13 2026-06-28 P0-06 runtime/source reconciliation 本地候选状态

状态口径：本节同步 P0-06 状态源债务的本地候选分支处理结果。候选分支从 `origin/main@cd8e2849fd4cdd4196a5a4055293a094d18cdfa6` 创建，精确移植当前生产运行态 `3dd20fe63c5d32c3dd665392a6892dd0b9304aa9` 中与 runtime/source 相关的代码和脚本差异；未执行生产部署、生产写入、生产 provider 调用或生产权限变更。主工作区 `codex/frontend-2.0` 的前端 WIP 保持隔离，未混入本候选。

本地候选变更：

- 部署镜像和 Compose 已显式携带 `web/out`，并通过 `MEDICAL_AUDIT_WEB_STATIC_ROOT=/app/web/out` 让 FastAPI 运行态可服务 Next static export。
- 腾讯云部署脚本已停止排除 `web/out`，部署前只清理可再生成的远端 `web/out`，部署后补查 `/api/v1/health` 和受控 `/documents`。
- FastAPI app 已补齐 `/api/v1`、`/api/backend` 兼容挂载、受控 API 鉴权路径规范化、门户 static export fallback 和 API 404 边界。
- RBAC 兼容保留 `system-admin` alias；文档治理接口补齐 `governance-result`、`manual-approval` 和 `index_readiness` 更新路径。
- 生产部署状态审计脚本已接受 app-proxy topology，在前门健康且 app 可服务静态页时，不再要求 Nginx 静态 bind mount。
- 生产文档治理 E2E 脚本保留 `--confirm-production-write` 显式门禁，并带租户、项目和角色请求头。
- `tests/knowledge_query/test_api.py` 手工合并保留 `origin/main` 上的 F2 topic/query 测试和 index candidate 断言，同时新增 runtime/source reconciliation 覆盖用例。

本地验收证据：

- `git diff --check`：通过。
- `uv run ruff check configs/deploy/tencent-cloud scripts/audit-tencent-cloud-deployment-state.py scripts/deploy-tencent-cloud-production.py scripts/run-production-documents-governance-result-e2e.py src/medical_audit_kb/api/app.py src/medical_audit_kb/api/auth.py src/medical_audit_kb/api/routes_auth.py src/medical_audit_kb/api/document_upload_store.py src/medical_audit_kb/api/routes_documents.py tests/knowledge_query/test_api.py tests/knowledge_query/test_scripts.py`：通过。
- `uv run pytest tests/knowledge_query/test_api.py -k "versioned_api_prefix or static_export_serves_portal or auth_api_lists_roles or documents_index_readiness_governance_result"`：通过，`4 passed`、`49 deselected`。
- `uv run pytest tests/knowledge_query/test_scripts.py -k "production_documents_governance or deployment_state_accepts_proxy_frontdoor or deployment_state_authenticates_documents_frontdoor or deploy_tencent_cloud_preflight_uses_app_proxy_topology or deploy_tencent_cloud_post_checks_auth_protected_documents or deploy_tencent_cloud_package_carries_static_export or cleans_only_regenerable"`：通过，`9 passed`、`30 deselected`。
- `uv run mypy src`：通过，`96` 个 source files。
- `uv run pytest tests/knowledge_query`：通过，`372 passed`，`1` 个既有 `StarletteDeprecationWarning`。
- `pnpm web:lint`：通过。
- `pnpm web:typecheck`：通过。
- `pnpm web:test`：通过，`11` 个 test files、`91` 个 tests。
- `pnpm web:build`：通过，静态页面 `21/21`。
- `pnpm local:fullstack:e2e`：通过，`16 passed`，使用临时 in-memory FastAPI backend 和 fake provider。
- `uv run python scripts/run-controlled-api-readonly-permission-smoke.py --json-output tmp/outputs/local-permission-readonly-smoke-runtime-reconcile-20260628T0035Z.json`：通过，`35` 个只读 GET probe，`issue_count=0`。
- `uv run python scripts/audit-tencent-cloud-deployment-state.py --ssh-key /Users/pray/project/medical_audit/ai_video.pem --expected-deploy-sha 3dd20fe63c5d32c3dd665392a6892dd0b9304aa9 --required-backup-stamp 20260627T2318-manual-approval-endpoints --min-matching-embeddings 49000 --require-clamav-sidecar --json-output tmp/outputs/tencent-cloud-deployment-state-runtime-reconcile-20260628T0035Z.json --markdown-output tmp/outputs/tencent-cloud-deployment-state-runtime-reconcile-20260628T0035Z.md`：生产只读巡检通过，`status=pass`、`issues=[]`、`warnings=[]`、`deploy_sha=3dd20fe63c5d32c3dd665392a6892dd0b9304aa9`、`matching_embedding_count=49051`、app/postgres/clamav healthy。

当前边界：

- `production_readonly_only`：本轮只做生产只读部署状态审计；没有生产部署、生产写入或生产配置变更。
- `no provider call`：本轮没有调用生成模型或外部 AI provider；本地 fullstack E2E 使用 fake provider。
- `local_candidate_not_release`：`codex/runtime-reconcile-20260628` 是 P0-06 源码对齐候选；合入、部署和生产写入型验收仍需后续独立门禁。
- `e2e_execution_order`：Next build 和 Playwright/Next dev 需要串行执行或先清理生成目录；并发运行会争用 `.next` 生成物，不能作为验收证据。
- `permission_smoke_prerequisite`：`local:permission:readonly` 依赖本地 backend 已监听 `127.0.0.1:8021`；直接在无服务时运行只会得到连接拒绝，不能作为产品权限结论。
- `answer_provider_status=blocked`：真实线上答案生成 provider 仍未通过 no-fallback 评测，本轮未推进该边界。

冻结日期：`2026-06-28`

### 2.0.15 2026-06-29 main@66b22d45 生产 UI/UX 部署与部署后验收

状态口径：本节同步 2026-06-29 已授权并执行的生产部署。部署对象为干净 `main@66b22d4549724a5065f396b94d6e1db15471983b`，部署戳 `deploy-main-66b22d45-20260629T075824Z`；该部署包含已合入 main 的当前 UI/UX、知识库/个人材料查询边界和文档状态同步，不包含 `/Users/pray/project/medical_audit` dirty WIP。

已完成：

- 预部署本地门禁：`uv run ruff check .`、`uv run pytest tests/knowledge_query`、`pnpm --filter medical-audit-web lint`、`typecheck`、`test`、`build` 均通过。
- 生产部署 preflight：`scripts/deploy-tencent-cloud-production.py` 使用同一部署戳完成 preflight；预期的目标 SHA 只读差异在部署前存在，生产部署后已由状态审计对齐。
- 生产部署执行：使用 `--execute --confirm-production audit.lute-tlz-dddd.top` 完成 app rebuild/restart、Next static 同步和共享 Nginx 静态资产更新；未带 `--apply-schema`。
- 远端备份：已生成 `pre-deploy-deploy-main-66b22d45-20260629T075824Z` app/env/db/nginx/web 备份；DB 备份路径为 `/opt/medical-audit/backups/db/pre-deploy-deploy-main-66b22d45-20260629T075824Z.sql.gz`，大小 `4832943186` bytes。

部署后验收证据：

- 生产综合 E2E：`tmp/outputs/production-e2e-smoke-after-deploy-main-66b22d45-20260629T075824Z.json`，`status=pass`；TLS、health、PostgreSQL search backend、页面渲染、审计日志权限、query API citations、citation preview、chat dossier export 和边缘域名回归均通过。`query-api-with-citations` 仍为 `fallback_used=true`，所以不构成 no-fallback 生成模型验收。
- 生产部署状态审计：`tmp/outputs/tencent-cloud-deployment-state-after-deploy-main-66b22d45-20260629T075824Z.json`，`status=pass`、`issues=[]`、`warnings=[]`、`deploy_sha=66b22d4549724a5065f396b94d6e1db15471983b`、app/postgres/clamav healthy、`audit_frontdoor_healthy=true`、`audit_next_static_healthy=true`、`audit_mount_present=true`、`matching_embedding_count=49051`。
- 生产前端语义验收：`tmp/outputs/production-frontend-acceptance-after-deploy-main-66b22d45-20260629T075824Z.json`，`status=pass`、`route_count=21`、`check_count=42`、`viewports=["desktop","mobile"]`、`p0=[]`、`p1=[]`。
- `/documents` 只读 probe：`tmp/outputs/production-documents-readonly-probe-after-deploy-main-66b22d45-20260629T075824Z.json`，`status=pass`，`documents_role=auditor`、`source_collection_count=5`、`can_upload_personal=true`、`can_read_all_personal_uploads=false`、`production_write=false`、`provider_call=false`。

当前边界：

- `production_live_side_effect=app_static_nginx_deploy`：本轮是授权生产部署，不是只读巡检。
- `schema_migration=not_applied`：未执行 `--apply-schema`。
- `production_env_write=false`：未写生产 env，未配置 chat answer provider key。
- `provider_call_status=not_called`：生产 answer provider readiness 仍 blocked，未运行 no-fallback 生产 E2E。
- `personal_material_active_gate=blocked_readonly`：目标版本已是 `active`，本轮只读复核不得重复 `index-activate` 或 reload。
- `original_frontend_wip_preserved`：`/Users/pray/project/medical_audit` dirty WIP 未回滚、未纳入本次生产包。

冻结日期：`2026-06-29`

### 2.0.17 2026-06-29 Batch 1 个人材料 active retrieval 与显式查询生产验收

状态口径：本节同步 2026-06-29 Batch 1 的执行结果。用户已同意继续下一批；本批先按 read-only 门禁判断是否仍需个人材料入索引写入或 `index-activate`，发现生产目标版本已是 active，因此没有重复执行 staging 写入、`index-activate` 或 search backend reload，转为验证当前 active personal-material 显式查询与默认隔离。

只读门禁：

- 部署状态审计：`tmp/outputs/tencent-cloud-deployment-state-batch1-personal-material-20260629T220732.json` 返回 `status=pass`、`issues=[]`、`warnings=[]`，远端 `.deploy-sha=a78bf8e5a1303178df26d03c6a687bd68f4512c2`，app/postgres/clamav healthy，`audit_next_static_healthy=true`，`search_backend_ready=true`，`matching_embedding_count=49051`。
- 个人材料 indexing readiness：`tmp/outputs/production-personal-material-indexing-readiness-batch1-20260629T220732.json` 返回 `status=blocked`，唯一 issue 为 `no-ready-upload-for-indexing`；摘要为 `ready_not_indexed_uploads=0`、`staged_uploads=4`、`personal_material_active_versions=1`、`personal_material_active_chunks=4`、`active_retrieval_activated=true`。
- 个人材料 active gate：`tmp/outputs/production-personal-material-active-gate-batch1-20260629T220732.json` 返回 `status=blocked`，唯一 issue 为 `target-index-version-not-candidate`；只读确认目标版本 `personal-materials-cos-staging-pr152-20260619` 已是 `active` 且 `target_live_retrieval_activated=true`，`safe_to_execute_index_activate=false`。
- 只读样本抽取确认 active personal-material chunk 存在，示例 owner 为 `cos-index-owner-20260619T071401Z`，目标 chunk 来自 `document-upload-d95888cd28ae`。

生产 API 验收：

- 显式查询验收报告：`tmp/outputs/production-personal-material-explicit-query-scope-batch1-20260629T220732.json` 返回 `status=pass`。
- `permissions-owner`：`GET /api/v1/documents/permissions` 返回 `200`，`source_collection_count=5`，包含 `personal-materials`。
- `default-query-excludes-personal-materials`：默认 `POST /api/v1/query` 返回 `200`，引用来源为 `medical-insurance-catalog` 与 `supervision-rules-knowledge`，不包含 `personal-materials`。
- `owner-explicit-personal-materials-query`：owner 显式传入 `source_collections=["personal-materials"]` 返回 `200`，`citation_count=1`，引用来源为 `personal-materials`，`first_index_version_key=personal-materials-cos-staging-pr152-20260619`。
- `non-owner-explicit-personal-materials-query-denied`：非 owner 普通审计员显式查询返回 `404`，符合 owner 隔离预期。
- `admin-explicit-personal-materials-query`：`it-admin` 显式查询返回 `200`，`citation_count=1`，引用来源为 `personal-materials`。

当前边界：

- `production_index_write=false`：本批没有执行个人材料 staging 写入、`index-activate` 或 search backend reload。
- `production_api_live_side_effect=query_history_write`：生产 query API 验收会写查询历史，属于本批已授权的轻量 L4 live side effect。
- `provider_call_status=not_called`：响应均为 `fallback_used=true`，本批没有调用外部 answer provider，也没有写生产 `MEDICAL_AUDIT_KB_ANSWER_*`。
- `personal_material_default_query_isolated=true`：默认查询仍不包含 `personal-materials`。
- `personal_material_explicit_query_status=pass`：owner/read-all 显式查询链路已在生产验证。

冻结日期：`2026-06-29`

### 2.0.18 2026-06-30 Batch 2 最新 UI/UX 基线后的认证/权限生产只读复核

状态口径：本节同步用户继续下一批后的生产只读复核。复核对象是当前生产最新 UI/UX 基线 `main@a78bf8e5a1303178df26d03c6a687bd68f4512c2`，目标是确认 docs-only 后续提交未被误判为已部署，并验证当前生产的 header transition layer、`X-Tenant-Id` 和受控 API 只读权限门禁。本批没有生产部署、没有生产写入、没有 provider call、没有授权写入型 E2E。

生产只读证据：

- 部署状态审计：`tmp/outputs/tencent-cloud-deployment-state-auth-permission-20260630T041340+0800.json` 返回 `status=pass`、`issues=[]`、`warnings=[]`，远端 `.deploy-sha=a78bf8e5a1303178df26d03c6a687bd68f4512c2`；app/postgres/clamav 均 healthy，`virus_scan_provider=clamav-sidecar`，`dlp_review_provider=ruleset-v1`，`audit_frontdoor_healthy=true`，`audit_next_static_healthy=true`，`audit_mount_present=true`，`search_backend_ready=true`，`matching_embedding_count=49051`。
- 权限只读 smoke：`tmp/outputs/production-permission-readonly-smoke-auth-permission-20260630T041340+0800.json` 返回 `status=observed`、`probe_count=35`、`issue_count=0`、`observation_count=0`，全程 `http_methods=["GET"]`，`production_side_effect=none`，`provider_call_status=not_called`。
- 公开路径：`/api/v1/health` 与 `/api/v1/auth/roles` 返回 `200`。
- 受控路径：`/api/v1/auth/session`、`/api/v1/query/logs?limit=1`、`/api/v1/audit-findings`、`/api/v1/graph/workbench`、`/api/v1/rules/workbench`、`/api/v1/remediation/workbench`、`/api/v1/archive/workbench`、`/api/v1/reports/workbench` 等路径在匿名或缺 `X-Tenant-Id` 时返回 `401`，在带 `X-User-Id`、`X-Role=admin`、`X-Project-Key` 和 `X-Tenant-Id=hospital-demo` 时返回 `200`。

当前边界：

- `production_deploy_status=unchanged_after_docs_only_main`：当前生产仍运行 `a78bf8e5`；`origin/main` 后续 docs-only 提交不等于生产代码/静态资产已再次部署。
- `auth_permission_readonly_status=observed_pass_on_probed_gets`：生产已在本批探测的只读 GET 受控路径上执行租户头和角色头门禁。
- `real_sso_status=not_implemented_or_not_verified`：本批不证明真实医院 SSO、正式登录会话签发、正式租户身份来源或网关 claims 注入策略已完成。
- `authorized_write_e2e_status=not_run`：本批不进入生产写入型权限验收；后续必须先有备份、显式授权和回滚路径。
- `provider_call_status=not_called`：本批没有调用外部 answer provider，也没有写生产 `MEDICAL_AUDIT_KB_ANSWER_*`。

下一步执行建议：

1. P0-04 继续从 header transition layer 推进到医院 SSO/session claims 合同、网关注入策略和正式租户身份来源；先做方案和只读验证，不直接写生产配置。
2. 写入型权限 E2E 仅在明确授权、备份和回滚路径齐备后执行；执行前复跑 `production:permission-readonly`。
3. F2 no-fallback 真实生成仍受 `no-provider-api-key-env-set` 阻塞；除非单独授权 provider smoke，否则继续保持 fallback 边界。

冻结日期：`2026-06-30`

### 2.0.27 2026-06-30 Batch 8.11C P0-05 deployment metadata GET-only 契约

状态口径：本节同步 P0-05 deployment metadata GET-only 契约。目标是在不触达生产的前提下，补齐一个只报告当前 deploy SHA 状态的只读面，让未来 production documents readonly probe 能把 `expected_deploy_sha` 与当前部署 SHA 做同源比较。本批没有执行生产只读 probe，没有生产部署、没有生产 env 写入、没有对象存储写入、没有外部治理 provider 调用、没有授权写入型 E2E。

本地变更：

- 新增 GET-only `GET /deployment/metadata`，并暴露 `/api/v1/deployment/metadata` 与 `/api/backend/deployment/metadata`。
- endpoint 按顺序读取 `MEDICAL_AUDIT_DEPLOY_SHA`、`MEDICAL_AUDIT_DEPLOY_SHA_FILE` 指向文件和默认 `.deploy-sha`，只接受 7-64 位 hex commit SHA；无有效值时返回 `deploy_sha_status=missing|invalid`，不输出 env name、secret value 或文件内容。
- endpoint 返回 `required_report_fields.expected_deploy_sha/current_deploy_sha/deploy_sha_status` 与只读边界；不写生产 env，不调用 provider，不写对象存储，不写 audit log。
- `scripts/run-production-documents-readonly-probe.py` 新增 `deployment-metadata` 步骤和 `--expected-deploy-sha` 参数；只有未来部署并获得显式只读授权后才可用于 L3 生产只读。
- `scripts/prepare-document-governance-production-readonly-observation-coverage.py` 更新为 `status=ready`，覆盖摘要为 `total=30`、`observable_by_existing_probe=1`、`observable_by_deployment_metadata_endpoint=1`、`observable_by_new_governance_status_endpoint=26`、`observable_by_boundary=2`。

验收证据：

- `python3 -m py_compile src/medical_audit_kb/api/app.py scripts/prepare-document-governance-production-readonly-observation-coverage.py scripts/run-production-documents-readonly-probe.py tests/knowledge_query/test_api.py tests/knowledge_query/test_scripts.py`：通过。
- `uv run ruff check src/medical_audit_kb/api/app.py scripts/prepare-document-governance-production-readonly-observation-coverage.py scripts/run-production-documents-readonly-probe.py tests/knowledge_query/test_api.py tests/knowledge_query/test_scripts.py`：通过。
- `uv run mypy src/medical_audit_kb/api/app.py`：通过。
- `uv run pytest tests/knowledge_query/test_api.py -k "deployment_metadata"`：通过，`3 passed`。
- `uv run pytest tests/knowledge_query/test_scripts.py -k "production_readonly_coverage or production_documents_readonly_probe"`：通过，`6 passed`。
- `uv run pytest tests/knowledge_query`：通过，`412 passed`。
- `pnpm document:governance-production-readonly-coverage`：返回 `status=ready`、`evidence_grade=L2-fixture-or-dry-run`、`coverage_summary.total=30`、`observable_by_existing_probe=1`、`observable_by_deployment_metadata_endpoint=1`、`observable_by_new_governance_status_endpoint=26`、`observable_by_boundary=2`。
- `git diff --check`：通过；diff 关键字扫描只命中文档和边界字段名，未发现真实 secret literal。

当前边界：

- `deployment_metadata_endpoint_status=local_get_only_contract_ready`：本地 API 契约和脚本门禁已具备，但尚未部署到生产。
- `production_readonly_probe=not_run`：本批没有访问生产 URL；不能声称生产 deploy SHA 或生产治理配置已观测。
- `production_current_state=unchanged`：本批没有部署生产，也没有生产 env 写入。
- `next_evidence_required`：按批准 release 路径部署主线后，使用明确批准的 GET-only production documents probe 和 `--expected-deploy-sha` 升级到 `L3-production-read-only`。

冻结日期：`2026-06-30`

### 2.0.26 2026-06-30 Batch 8.11B P0-05 governance status GET-only 契约

状态口径：本节同步 P0-05 文档治理 governance status GET-only 契约。目标是在不触达生产的前提下，补齐一个无 upload-list、无 download、无 audit-log write、无 provider call、无 object storage write 的 redacted status endpoint，并让未来 production documents readonly probe 能观测治理配置字段。本批没有执行生产只读 probe，没有生产部署、没有生产 env 写入、没有对象存储写入、没有外部治理 provider 调用、没有授权写入型 E2E。

本地变更：

- 新增 GET-only `GET /documents/governance/status`，并通过既有 router 前缀暴露 `/api/v1/documents/governance/status` 与 `/api/backend/documents/governance/status`。
- endpoint 返回 storage、COS、governance provider、redaction、audit event contract、`document_storage_objects_schema_ready`、upload-list/download 副作用状态和 audit-log 只读状态的 redacted status。
- endpoint 不输出 COS bucket、region、prefix、redaction policy version、env name 或 secret value；测试使用 sentinel secret 值确认响应正文不泄露。
- `scripts/run-production-documents-readonly-probe.py` 新增未来 GET-only `documents-governance-status` 步骤，并继续校验 `/api/v1/documents/uploads` 与 download route 是 audit-log side-effect blocked。
- `scripts/prepare-document-governance-production-readonly-observation-coverage.py` 更新为识别 `/api/v1/documents/governance/status` 覆盖 26 个治理字段。

验收证据：

- `python3 -m py_compile src/medical_audit_kb/api/routes_documents.py scripts/prepare-document-governance-production-readonly-observation-coverage.py scripts/run-production-documents-readonly-probe.py`：通过。
- `uv run ruff check src/medical_audit_kb/api/routes_documents.py scripts/prepare-document-governance-production-readonly-observation-coverage.py scripts/run-production-documents-readonly-probe.py tests/knowledge_query/test_api.py tests/knowledge_query/test_scripts.py`：通过。
- `uv run pytest tests/knowledge_query/test_api.py -k "documents_governance_status"`：通过，`1 passed`。
- `uv run pytest tests/knowledge_query/test_scripts.py -k "production_readonly_coverage or production_documents_readonly_probe"`：通过，`5 passed`。
- `pnpm document:governance-production-readonly-coverage`：返回 `status=ready_for_governance_config_readonly_probe_with_deploy_metadata_gap`、`evidence_grade=L2-fixture-or-dry-run`、`coverage_summary.total=30`、`observable_by_existing_probe=1`、`observable_by_new_governance_status_endpoint=26`、`observable_by_boundary=2`、`not_observable_without_deploy_metadata_endpoint=1`。

当前边界：

- `governance_status_endpoint_status=local_get_only_contract_ready`：本地 API 契约和脚本门禁已具备，但尚未部署到生产。
- `production_readonly_probe=not_run`：本批没有访问生产 URL；不能声称生产治理配置已观测。
- `production_current_state=unchanged`：本批没有部署生产，也没有生产 env 写入。
- `expected_deploy_sha_status=not_observable_without_deploy_metadata_endpoint`：完整 P0-05 L3 仍需 deployment metadata endpoint 或 static manifest。
- `side_effect_blocked_endpoints=preserved`：upload-list 和 download route 仍被记录为会写 audit log，不能作为无副作用只读观测端点。
- `next_evidence_required`：补 GET-only deployment metadata 后，随主线部署并获得显式只读授权，再执行更新后的 production documents readonly probe。

冻结日期：`2026-06-30`

### 2.0.25 2026-06-30 Batch 8.11A P0-05 生产只读观测覆盖缺口门禁

状态口径：本节同步 P0-05 文档治理生产只读观测覆盖缺口门禁。目标是在不触达生产的前提下，逐项盘点现有 documents GET-only probe 是否覆盖生产只读 required fields，并明确普通 `/documents` smoke 不能替代治理配置只读验收。本批没有执行生产只读 probe，没有生产部署、没有生产 env 写入、没有对象存储写入、没有外部治理 provider 调用、没有授权写入型 E2E。

本地变更：

- 新增 `scripts/prepare-document-governance-production-readonly-observation-coverage.py`，输出 P0-05 production-readonly required fields 覆盖矩阵。
- 新增 `pnpm document:governance-production-readonly-coverage`，默认输出 `tmp/outputs/document-governance-production-readonly-observation-coverage-latest.json` 与 `.md`。
- coverage gate 明确现有 safe GET endpoints、side-effect blocked GET endpoints 和 out-of-scope write endpoints。
- 新增测试，覆盖 `not_observable_without_new_readonly_endpoint`、`blocked_by_audit_log_side_effect`、禁止非 GET、secret value 不输出和本批无生产副作用边界。

验收证据：

- `python3 -m json.tool package.json`：通过。
- `python3 -m py_compile scripts/prepare-document-governance-production-readonly-observation-coverage.py`：通过。
- `uv run ruff check scripts/prepare-document-governance-production-readonly-observation-coverage.py tests/knowledge_query/test_scripts.py`：通过。
- `uv run pytest tests/knowledge_query/test_scripts.py -k "production_readonly_coverage"`：通过。
- `pnpm document:governance-production-readonly-coverage`：返回 `status=blocked_missing_governance_readonly_surface`、`evidence_grade=L2-fixture-or-dry-run`、`coverage_summary.total=30`、`observable_by_existing_probe=1`、`observable_by_boundary=2`、`not_observable_without_new_readonly_endpoint=23`、`blocked_by_audit_log_side_effect=2`。

当前边界：

- `production_readonly_coverage_status=blocked_missing_governance_readonly_surface`：只代表当前观测覆盖不足，不代表生产治理配置失败。
- `production_readonly_probe=not_run`：本批没有执行生产 GET-only probe。
- `production_current_state=unchanged`：本批未验证或变更生产配置。
- `upload_list_get_status=blocked_by_audit_log_side_effect`：`GET /api/v1/documents/uploads` 会记录 `document-upload-list` 审计操作，不能当作无副作用只读端点。
- `download_metadata_get_status=blocked_by_audit_log_side_effect`：`GET /api/v1/documents/uploads/{upload_id}/download` 会记录下载或拒绝审计操作，不能当作无副作用只读端点。
- `next_evidence_required`：下一批先补 GET-only governance config/status 只读面和无副作用 metadata/status 观测；覆盖门禁不再 blocked 后，才申请 L3 production read-only probe。

冻结日期：`2026-06-30`

### 2.0.24 2026-06-30 Batch 8 P0-05 生产只读执行前检查

状态口径：本节同步 P0-05 文档治理生产只读执行前检查。目标是在不触达生产的前提下，复跑非生产 ready-profile 和生产只读准备包，汇总人工授权 todo，并明确下一步只能申请显式 GET-only 生产只读授权。本批没有执行生产只读 probe，没有生产部署、没有生产 env 写入、没有对象存储写入、没有外部治理 provider 调用、没有授权写入型 E2E。

本地变更：

- 新增 `scripts/run-document-governance-production-readonly-precheck.py`，自动执行本地 ready-profile dry-run 与生产只读准备包 refresh，并合并生成 precheck 报告。
- 新增 `pnpm document:governance-production-readonly-precheck`，默认输出 `tmp/outputs/document-governance-production-readonly-precheck-latest.json` 与 `.md`。
- precheck 子报告默认输出 `tmp/outputs/document-governance-production-readonly-precheck-ready-profile-latest.json` 和 `tmp/outputs/document-governance-production-readonly-precheck-plan-latest.json`。
- 新增 precheck 测试，覆盖脚本边界字段、子报告状态、manual authorization todo、next allowed step、仍禁止的生产副作用和 ready-profile sentinel value 不泄露。

验收证据：

- `python3 -m json.tool package.json`：通过。
- `python3 -m py_compile scripts/run-document-governance-production-readonly-precheck.py`：通过。
- `uv run ruff check scripts/run-document-governance-production-readonly-precheck.py tests/knowledge_query/test_scripts.py`：通过。
- `uv run pytest tests/knowledge_query/test_scripts.py -k "production_readonly_precheck"`：通过。
- `pnpm document:governance-production-readonly-precheck`：返回 `status=ready_for_manual_authorization_review`、`blockers=[]`、`evidence_grade=L2-fixture-or-dry-run`，并确认 `production_readonly_probe=not_run`、`production_env_write=false`、`object_storage_write=false`、`network_call_status=not_called`、`provider_call_status=not_called`、`external_governance_provider_call=not_called`、`authorized_write_e2e=not_run`、`secret_values_reported=false`。

当前边界：

- `production_readonly_precheck_status=ready_for_manual_authorization_review`：只代表人工授权复核材料已准备好。
- `production_readonly_probe=not_run`：本批没有执行生产 GET-only probe。
- `production_current_state=unchanged`：本批未验证或变更生产配置。
- `production_env_write=false`：本批未写生产 env。
- `authorized_write_e2e_status=not_run`：对象存储写入、文档治理结果写入、归档签章和恢复演练仍需备份、显式授权和回滚路径后执行。
- `next_evidence_required`：下一批必须先取得显式生产只读授权；获得授权后只执行 GET-only production read-only probe，并继续禁止生产 env write、对象存储写入、外部 provider call 和写入型治理 E2E。

冻结日期：`2026-06-30`

### 2.0.23 2026-06-30 Batch 7 P0-05 生产只读准备包

状态口径：本节同步 P0-05 文档治理合同的生产只读准备包。目标是把生产当前配置观测、非生产 ready-profile dry-run 和授权写入型治理 E2E 拆成三层证据，并把生产只读报告字段、生产配置授权输入和 rollback 要求固化为机器可读本地报告。本批没有执行生产只读 probe，没有生产部署、没有生产 env 写入、没有对象存储写入、没有外部治理 provider 调用、没有授权写入型 E2E。

本地变更：

- 新增 `scripts/prepare-document-governance-production-readonly-plan.py`，输出 P0-05 生产只读准备包。
- 新增 `pnpm document:governance-production-readonly-plan`，默认输出 `tmp/outputs/document-governance-production-readonly-plan-latest.json` 与 `.md`。
- 准备包将 `local-ready-profile-dry-run`、`production-readonly-observation` 和 `authorized-write-governance-e2e` 分开记录，避免把 L2 dry-run、L3 production read-only 和 L4 authorized-live 混为同一状态。
- 准备包列明生产只读必备字段、人工授权 env 名称、rollback 要求和后续证据升级路径；报告只允许 env 名称和 SET/UNSET 状态，不承载 credential values。

验收证据：

- `python3 -m json.tool package.json`：通过。
- `python3 -m py_compile scripts/prepare-document-governance-production-readonly-plan.py`：通过。
- `uv run ruff check scripts/prepare-document-governance-production-readonly-plan.py tests/knowledge_query/test_scripts.py`：通过。
- `uv run pytest tests/knowledge_query/test_scripts.py -k "prepare_document_governance_production_readonly_plan"`：通过。
- `pnpm document:governance-production-readonly-plan`：返回 `status=ready_for_production_readonly_plan_review`、`evidence_grade=L2-fixture-or-dry-run`、`production_readonly_probe=not_run`、`production_env_write=false`、`object_storage_write=false`、`network_call_status=not_called`、`provider_call_status=not_called`、`external_governance_provider_call=not_called`、`authorized_write_e2e=not_run`、`secret_values_reported=false`。

当前边界：

- `production_readonly_plan_status=ready_for_production_readonly_plan_review`：只代表本地准备包可审查。
- `production_readonly_probe=not_run`：本批没有执行生产 GET-only probe。
- `production_current_state=unchanged`：本批未验证或变更生产配置。
- `production_env_write=false`：本批未写生产 env。
- `authorized_write_e2e_status=not_run`：对象存储写入、文档治理结果写入、归档签章和恢复演练仍需备份、显式授权和回滚路径后执行。
- `next_evidence_required`：下一批先人工复核生产配置授权包和只读执行前检查；只有获得只读授权后，才执行生产只读 probe 并升级到 `L3-production-read-only`。

冻结日期：`2026-06-30`

### 2.0.22 2026-06-30 Batch 6 P0-05 非生产 ready-profile 验证

状态口径：本节同步 P0-05 文档治理合同的非生产 ready-profile 验证。目标是证明当前 readiness 门禁不仅能 fail-closed，也能在显式非生产配置和 sentinel env value 下进入 `ready_for_readonly_governance_probe`。本批没有生产部署、没有生产 env 写入、没有对象存储写入、没有外部治理 provider 调用、没有授权写入型 E2E。

本地变更：

- 新增 `configs/knowledge-query-engine-document-governance-ready-profile.yaml`，显式使用 `medical-audit-ready-profile-nonprod` bucket 与 `non-production/ready-profile` prefix。
- 新增 `scripts/run-document-governance-ready-profile.py`，内部注入非生产 sentinel env value 并调用 readiness 脚本；package 命令不回显 sentinel value。
- 新增 `pnpm document:governance-ready-profile`，输出 `tmp/outputs/document-governance-contract-readiness-ready-profile-latest.json` 与 `.md`。
- 新增 ready-profile 测试，覆盖 report `ready_for_readonly_governance_probe`、`blockers=[]`、边界字段和 sentinel value 不出现在 stdout/JSON/Markdown。

验收证据：

- `python3 -m json.tool package.json`：通过。
- `python3 -m py_compile scripts/audit-document-governance-contract-readiness.py scripts/run-document-governance-ready-profile.py`：通过。
- `uv run ruff check scripts/audit-document-governance-contract-readiness.py scripts/run-document-governance-ready-profile.py tests/knowledge_query/test_scripts.py`：通过。
- `uv run pytest tests/knowledge_query/test_scripts.py -k "audit_document_governance or run_document_governance_ready_profile"`：通过，`5 passed`。
- `pnpm document:governance-ready-profile`：返回 `status=ready_for_readonly_governance_probe`、`blockers=[]`、`evidence_grade=L2-fixture-or-dry-run`、`production_side_effect=none`、`object_storage_write=false`、`external_governance_provider_call=not_called`、`secret_values_reported=false`。

当前边界：

- `ready_profile_status=ready_for_readonly_governance_probe`：只代表非生产配置合同可达。
- `production_current_state=unchanged`：本批未验证或变更生产配置。
- `external_governance_provider_call=not_called`：本批没有外部 DLP/virus provider 调用。
- `authorized_write_e2e_status=not_run`：对象存储写入、治理结果写入、归档签章和恢复演练仍需备份、显式授权和回滚路径后执行。
- `next_evidence_required`：下一批应设计生产只读复核和人工授权包，继续把 production read-only 与 authorized live side effect 分开。

冻结日期：`2026-06-30`

### 2.0.21 2026-06-30 Batch 5 P0-05 脱敏与审计合同 settings 固化

状态口径：本节同步 P0-05 文档治理合同的下一批本地配置收口。目标是把脱敏改写、策略版本、人工复核要求和治理审计事件要求从 readiness 脚本内的裸 env 检查提升到正式 `DocumentUploadGovernanceSettings` 与 env override 层。本批没有生产部署、没有生产 env 写入、没有对象存储写入、没有外部治理 provider 调用、没有授权写入型 E2E。

本地变更：

- `DocumentUploadGovernanceSettings` 新增 `redaction_rewrite_enabled`、`redaction_policy_version`、`redaction_manual_review_required` 和 `governance_audit_event_required`。
- 新增 env override：`MEDICAL_AUDIT_DOCUMENT_REDACTION_REWRITE_ENABLED`、`MEDICAL_AUDIT_DOCUMENT_REDACTION_POLICY_VERSION`、`MEDICAL_AUDIT_DOCUMENT_REDACTION_REVIEW_REQUIRED`、`MEDICAL_AUDIT_DOCUMENT_GOVERNANCE_AUDIT_EVENT_REQUIRED`。
- `scripts/audit-document-governance-contract-readiness.py` 改为读取 typed settings 判定脱敏/审计合同，不再在脚本内部直接读取这些 env 值；报告仍只输出合同状态和 COS secret env 的 `SET/UNSET`。
- 新增配置测试，覆盖默认 fail-closed、env override 生效和非法布尔值 fail-closed。

验收证据：

- `python3 -m py_compile src/medical_audit_kb/core/config.py scripts/audit-document-governance-contract-readiness.py`：通过。
- `uv run ruff check src/medical_audit_kb/core/config.py scripts/audit-document-governance-contract-readiness.py tests/knowledge_query/test_config.py tests/knowledge_query/test_scripts.py`：通过。
- `uv run pytest tests/knowledge_query/test_config.py tests/knowledge_query/test_scripts.py -k "document_governance or document_upload_governance or audit_document_governance"`：通过，`6 passed`。
- `pnpm document:governance-contract-readiness`：仍按预期返回 `status=blocked`，报告只包含 `production_side_effect=none`、`production_env_write=false`、`object_storage_write=false`、`external_governance_provider_call=not_called` 和 `secret_values_reported=false`。

当前边界：

- `document_governance_settings_contract_status=local_typed_settings_ready`：合同已进入本地配置模型，但默认配置仍不足以支撑生产级文档治理闭环。
- `document_governance_contract_readiness_status=blocked`：默认运行仍缺 COS/object recording、企业级病毒/DLP provider、脱敏启用、策略版本、人工复核和审计事件要求。
- `production_current_state=unchanged`：本批未部署生产，也未写生产 env。
- `next_evidence_required`：下一批应先补非生产 ready-profile 或等价配置验证，证明 readiness 可进入 `ready_for_readonly_governance_probe`；生产配置与写入型治理 E2E 仍需单独授权。

冻结日期：`2026-06-30`

### 2.0.20 2026-06-30 Batch 4 P0-05 文档治理合同 readiness 固化

状态口径：本节同步 P0-05 文档治理安全闭环的下一批本地收口。目标是把对象存储、企业级病毒/DLP provider、脱敏改写、留存策略和审计事件合同从计划文字固化为可执行 readiness 门禁。本批没有生产部署、没有生产 env 写入、没有对象存储写入、没有外部治理 provider 调用、没有授权写入型 E2E。

本地变更：

- 新增 `scripts/audit-document-governance-contract-readiness.py`，聚合文档上传治理 provider preflight、Tencent COS bootstrap preflight、对象记录、签名 URL TTL、retention、脱敏改写和审计事件合同检查。
- 新增 `pnpm document:governance-contract-readiness`，作为 P0-05 文档治理合同门禁入口。
- 新增脚本测试，覆盖默认 fail-closed、企业级配置齐备时进入 `ready_for_readonly_governance_probe`、COS secret 值不泄露。
- 输出报告默认写入 `tmp/outputs/document-governance-contract-readiness-latest.json` 与 `tmp/outputs/document-governance-contract-readiness-latest.md`。

验收证据：

- `python3 -m py_compile scripts/audit-document-governance-contract-readiness.py`：通过。
- `uv run pytest tests/knowledge_query/test_scripts.py -k "audit_document_governance_contract_readiness"`：通过，`3 passed`。
- `uv run ruff check scripts/audit-document-governance-contract-readiness.py tests/knowledge_query/test_scripts.py`：通过。
- `pnpm document:governance-contract-readiness`：返回 `status=blocked`、`evidence_grade=L2-fixture-or-dry-run`，并记录 `production_side_effect=none`、`production_env_write=false`、`object_storage_write=false`、`external_governance_provider_call=not_called`、`secret_values_reported=false`。

当前阻塞项：

- `cos:document-storage-provider-not-tencent-cos`
- `cos:cos-sdk-bootstrap-disabled`
- `cos:cos-bucket-missing`
- `cos:cos-region-missing`
- `cos:cos-secret-id-env-name-missing`
- `cos:cos-secret-key-env-name-missing`
- `cos:cos-secret-id-env-value-missing`
- `cos:cos-secret-key-env-value-missing`
- `document-storage-object-recording-disabled`
- `enterprise-virus-scan-provider-not-configured`
- `enterprise-dlp-provider-not-configured`
- `redaction-rewrite-not-enabled`
- `redaction-policy-version-missing`
- `redaction-manual-review-not-required`
- `document-governance-audit-event-contract-missing`

当前边界：

- `document_governance_contract_readiness_status=blocked`：本地合同门禁已存在，但默认配置仍不足以支撑生产级文档治理闭环。
- `production_current_state=unchanged`：本批未部署生产，也未修改生产文档治理配置；既有生产只读证据只能说明被观测配置和只读路径状态。
- `external_governance_provider_call=not_called`：本批没有调用外部病毒扫描、外部 DLP 或 answer provider。
- `authorized_write_e2e_status=not_run`：对象存储写入、文档治理结果写入、归档签章和恢复演练仍需备份、显式授权和回滚路径后再执行。
- `next_evidence_required`：补齐 COS/object recording、脱敏改写策略、审计事件合同和企业级治理 provider 配置后，先跑 readiness，再跑生产只读，最后申请授权写入型治理 E2E。

冻结日期：`2026-06-30`

### 2.0.19 2026-06-30 Batch 3 P0-04 SSO/session 合同 readiness 固化

状态口径：本节同步 P0-04 真实认证与租户边界的下一批本地收口。目标是把医院 SSO/session claims、可信代理、正式租户身份来源和 legacy header 关闭要求从计划文字固化为可执行 readiness 门禁。本批没有生产部署、没有生产配置写入、没有生产写入型 E2E、没有 provider call。

本地变更：

- 新增 `scripts/audit-auth-sso-contract-readiness.py`，默认目标为 `trusted-sso-proxy`，只读取本地环境变量名称和 `SET/UNSET` 状态，输出 SSO/session 合同 readiness JSON/Markdown。
- 新增 `pnpm auth:sso-contract-readiness`，作为 P0-04 合同门禁入口。
- 新增脚本测试，覆盖默认 fail-closed、可信代理配置齐备时进入 `ready_for_readonly_gateway_probe`、签名密钥值不泄露。
- 同步 `docs/architecture/architecture-auth-rbac-stable.md`，补充 2026-06-30 生产只读权限事实、可信代理 claims 合同和当前阻塞项。

验收证据：

- `python3 -m py_compile scripts/audit-auth-sso-contract-readiness.py`：通过。
- `uv run pytest tests/knowledge_query/test_scripts.py -k "audit_auth_sso_contract_readiness"`：通过，`3 passed`。
- `uv run ruff check scripts/audit-auth-sso-contract-readiness.py tests/knowledge_query/test_scripts.py`：通过。
- `uv run python scripts/audit-auth-sso-contract-readiness.py --json-output tmp/outputs/auth-sso-contract-readiness-p0-04-20260630T042500+0800.json --markdown-output tmp/outputs/auth-sso-contract-readiness-p0-04-20260630T042500+0800.md`：返回 `status=blocked`、`evidence_grade=L2-fixture-or-dry-run`、`production_side_effect=none`、`provider_call_status=not_called`、`secret_values_reported=false`。

当前阻塞项：

- `auth-mode-not-trusted-sso-proxy`
- `trusted-proxy-not-enabled`
- `trusted-proxy-signature-key-env-missing`
- `trusted-proxy-allowed-source-cidrs-missing`
- `legacy-header-auth-still-enabled`

当前边界：

- `sso_contract_readiness_status=blocked`：真实 SSO/可信代理或 server-session 尚未配置，不能宣称真实会话完成。
- `legacy_header_auth_status=still_enabled`：浏览器可构造的过渡 header 仍参与授权解析，生产写入型权限验收不得开始。
- `production_side_effect=none`：本批只做本地脚本、测试和文档同步。
- `next_evidence_required`：选择可信代理或 server-session 路径，配置签名/会话/legacy header 关闭策略后，先跑 readiness，再跑生产只读权限 smoke，最后才申请授权写入型权限 E2E。

冻结日期：`2026-06-30`

### 2.0.16 2026-06-29 Batch 0 最新 UI/UX 生产基线与顺序合并复核

状态口径：本节同步 2026-06-29 按推荐执行顺序完成的 Batch 0 复核。目标是确认最新网站 UI/UX 是否已经按顺序合并并部署到生产，同时避免把历史 UI 实验分支误合回当前主线。本节为状态同步，不包含业务代码修改、schema migration、生产 env 改写或 provider 调用。

分支合并结论：

- 当前生产主线：`/Users/pray/project/medical_audit_minimal_pr` 的 `main@a78bf8e5a1303178df26d03c6a687bd68f4512c2`，且 `main...origin/main` 干净。
- 最新 UI/UX 合并顺序已在 `main` 历史中闭合：`560758ea fix(ui): stabilize sidebar brand and topic entry` -> `20bec8d2 merge main into frontend 2 latest design` -> `85330508 fix(ui): keep topic entry visible on mobile` -> `a78bf8e5 merge frontend 2 latest website design`。
- `codex/frontend-2.0` 和 `codex/frontend-2-release-20260628` 均已是 `main` 的祖先；不需要再次合并。
- `codex/frontend-plan-02-projects-dashboard`、`codex/frontend-visual-system-polish`、`codex/opendesign-ui-polish` 等历史分支未纳入本批合并；对比 `main` 的 diff 会删除当前已落地的大量 API、脚本、状态文档和前端数据契约，属于被后续 `frontend-2.0` 主线取代的旧实验分支，不是最新 UI/UX 待合并分支。
- `/Users/pray/project/medical_audit` 仍保留 `codex/frontend-2.0` 本地 evidence 产物 `output/`，该工作树状态不等同于生产 `main` 真相。

本地质量闸：

- `web`: `./node_modules/.bin/eslint .` 通过。
- `web`: `./node_modules/.bin/tsc --noEmit` 通过。
- `web`: `./node_modules/.bin/vitest run` 通过，`11` 个 test files、`91` 个 tests。
- `web`: `MEDICAL_AUDIT_NEXT_EXPORT=1 ./node_modules/.bin/next build` 通过，静态页面 `21/21`。
- repo: `uv run ruff check .` 通过。
- repo: `uv run pytest tests/knowledge_query` 通过，`392 passed`，`1` 个既有 `StarletteDeprecationWarning`。
- repo: `git diff --check` 通过。

生产复核证据：

- 部署状态审计：`tmp/outputs/tencent-cloud-deployment-state-batch0-latest-ui-20260629T2151.json`，`status=pass`、`issues=[]`、`warnings=[]`、`deploy_sha=a78bf8e5a1303178df26d03c6a687bd68f4512c2`、app/postgres/clamav healthy、`audit_frontdoor_healthy=true`、`audit_next_static_healthy=true`、`matching_embedding_count=49051`。
- 生产前端语义验收：`tmp/outputs/production-frontend-acceptance-batch0-latest-ui-20260629T2151.json`，`status=pass`、`route_count=21`、`check_count=42`、desktop/mobile 均通过，`p0=[]`、`p1=[]`。
- `/documents` 只读 probe：`tmp/outputs/production-documents-readonly-probe-batch0-latest-ui-20260629T2151.json`，`status=pass`、`production_write=false`、`provider_call=false`、`source_collection_count=5`、`matching_embedding_count=49051`。
- 浏览器 DOM 检查：`tmp/outputs/playwright/batch0-latest-ui-20260629T2151/summary.json`，`failedCount=0`；desktop/mobile 均确认 Logo `src` 为 `/brand/auditscope-logo.png`、无 broken image、`医保基金使用合规` 入口可见并指向 `/workspace`、专题入口到导航间距 `20px`、无横向溢出。
- Answer provider 只读门禁：`tmp/outputs/answer-provider-gate-readiness-production-only-batch0-latest-ui-20260629T2151.json`，`status=blocked`、`blockers=["no-provider-api-key-env-set"]`、`provider_call_status=not_called`、`production_env_write=false`。

当前边界：

- `current_ui_deploy_status=aligned`：当前生产站点已经运行最新合并的 UI/UX 版本 `a78bf8e5`。
- `deployment_execute_status=not_needed_for_batch0`：本批复核发现生产 SHA 已对齐，因此没有重复执行生产部署。
- `stale_ui_branches=not_merged_by_design`：历史 UI 实验分支未合入，是为了保护当前生产主线能力。
- `next_batch_requires_authorization`：Batch 1 若进入个人材料真实入向量索引或生产写入型 E2E，需要单独确认生产写入边界。

冻结日期：`2026-06-29`

### 2.0.14 2026-06-28 runtime/source reconciliation 与 Frontend 2.0 生产基线

状态口径：本节同步 2026-06-28 PR #163 Frontend 2.0 已合并、已部署、已验收的生产基线。该轮生产部署对象为 `main@0984aad93505cb8eedb36aa8379031c4396b1939`；PR #164 合入点 `de648cccd855336d850c837fcaf0b5750ba0ede3` 额外包含验收脚本文案同步。后续 PR #168 已更新生产 `.deploy-sha`，最新生产状态见 `2.1`。

已完成：

- PR #161 `runtime-reconcile` 已合入并部署到生产，消除 runtime/source 漂移，生产检索后端继续为 PostgreSQL，`matching_embedding_count=49051`。
- PR #162 已将部署状态审计收紧为必须验证共享 Nginx 静态 bind mount 和 Next static chunk，防止只看 API health 误判静态门户可用。
- AI_vedio PR #56 已同步共享 `ai_video_nginx` 源配置，`audit.lute-tlz-dddd.top` 由 `/var/www/audit` 服务 Next static export，并保留 API/Jinja 路由反代到 `medical_audit_app`。
- PR #163 已将 Frontend 2.0 release candidate 合入并部署到生产，覆盖对话工作台、智能体广场、知识库查询、疑点工作台、文档检索、知识图谱、规则、整改、归档和项目门户形态。
- PR #164 已同步 `scripts/run-production-frontend-acceptance.mjs` 的 2.0 文案断言；该 PR 是验收脚本口径同步，不代表新增生产业务部署。

本地和生产验收证据：

- Frontend 2.0 release worktree：`pnpm --filter medical-audit-web lint`、`typecheck`、`test`、`build` 均通过；前端单测 `11` 个 test files、`91` 个 tests；静态页面 `21/21`；`uv run python scripts/run-local-fullstack-e2e.py` 通过，`16 passed`。
- 生产部署戳：`frontend-2-main-20260628T1142`；部署前 preflight 通过，部署执行使用 `--execute --confirm-production audit.lute-tlz-dddd.top`，未带 `--apply-schema`。
- 生产综合 E2E：`tmp/outputs/production-e2e-smoke-after-frontend-2-main-20260628T1142.json`，`status=pass`；TLS、health、PostgreSQL search backend、Jinja pages、审计日志权限、query API citations、citation preview、chat dossier export 和边缘域名回归均通过。
- 该轮生产部署状态审计：`tmp/outputs/tencent-cloud-deployment-state-after-frontend-2-main-20260628T1142.json`，`status=pass`、`issues=[]`、`warnings=[]`、`deploy_sha=0984aad93505cb8eedb36aa8379031c4396b1939`、`audit_frontdoor_healthy=true`、`audit_next_static_healthy=true`、`audit_mount_present=true`、app/postgres/clamav healthy。
- 生产前端语义验收：`tmp/outputs/production-frontend-acceptance-after-frontend-2-main-rerun-20260628T1204.json`，`status=pass`、`route_count=21`、`check_count=42`、`p0=[]`、`p1=[]`；`/audit/logs` 与 `/audit/logs/export` 均满足无租户头 `401`、管理员 `200`。
- 生产只读权限观测：`tmp/outputs/production-permission-readonly-smoke-after-frontend-2-main-20260628T1142.json`，`status=observed`、`probe_count=35`、`issue_count=0`、`production_side_effect=none`、`provider_call_status=not_called`、`http_methods=["GET"]`。
- 远端备份：`pre-deploy-frontend-2-main-20260628T1142` 已生成 app/env/db/nginx/web 备份；DB 备份路径为 `/opt/medical-audit/backups/db/pre-deploy-frontend-2-main-20260628T1142.sql.gz`。

当前边界：

- `production_live_side_effect=app_static_nginx_deploy`：本轮存在授权生产部署和共享 Nginx 配置/挂载修复；已备份、`nginx -t`、重建 `ai_video_nginx` 并做边缘域名回归。
- `personal_material_live_gate_metadata_write=executed`：已授权执行 production DB metadata write，将目标 candidate 标记为 `live_retrieval_activated=true`；该动作是后续 `index-activate` 前置条件。
- `personal_material_index_activate_and_reload=executed`：2026-06-29 已授权执行 production DB `index-activate` 和 search backend reload；目标版本 `personal-materials-cos-staging-pr152-20260619` 当前为 `active`，`personal_material_active_chunks=4`，默认查询仍隔离 `personal-materials`。
- `schema_migration=not_applied`：本轮 SQL diff 为空，生产部署未执行 `--apply-schema`。
- `no_provider_call`：本轮没有调用生成模型或外部 AI provider；answer provider 生产-only readiness 仍 blocked，完整 production smoke 因可能触发 query/chat provider 行为未运行，no-fallback 生成能力仍未验收。
- `no_dedicated_production_write_e2e`：本轮未执行新的写入型业务 E2E；生产 smoke 和权限观测不等价于真实医院写入验收。
- `main_prod_sha_boundary=documented`：本节记录 PR #170/#171 当时已单独部署并更新生产 `.deploy-sha=30df45269ba38e3d3d56e0599162950b6389f3eb` 的历史边界；最新生产 `.deploy-sha` 以 2026-06-30 只读审计确认的 `a78bf8e5a1303178df26d03c6a687bd68f4512c2` 为准。后续 docs-only/test-only 合并仍不得自动声称生产已同步。
- `original_frontend_wip_preserved`：`/Users/pray/project/medical_audit` 的 `codex/frontend-2.0` 工作区仍保留原 7 个 dirty WIP 文件；本轮通过干净 release worktree 移植并发布，不回滚用户工作区。

下一阶段计划：

1. 真实生成模型 no-fallback 门禁：生产-only readiness 仍缺生成 provider key；下一步必须先明确授权 provider smoke，provider smoke 与真实问题评测通过前保持 fallback 边界。
2. 个人材料 active retrieval 后续产品化：`ready_not_indexed_uploads=0`、candidate staging、live retrieval metadata gate、`index-activate`、search backend reload、激活后只读验收和显式查询 owner/read-all 生产验收均已完成；下一步是 DLP/脱敏改写、外部杀毒/对象存储治理、查询历史/审计事件专项验收，以及移动端/前端状态呈现。
3. 真实认证和租户边界：从 header transition layer 推进到医院 SSO/session claims、正式租户身份来源和生产权限复验。
4. 前端 2.0 API 化：优先把疑点工作台、知识图谱、规则、整改、归档从静态/只读状态推进到受控 API 首切片，保持 `production:frontend-acceptance` 与 local fullstack E2E 双门禁。
5. UAT 包与运维硬化：沉淀 UAT case matrix、回滚演练、共享 Nginx 回归、备份恢复和告警配置证据。

冻结日期：`2026-06-29`
