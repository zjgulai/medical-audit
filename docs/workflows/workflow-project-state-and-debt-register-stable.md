---
title: AI智能审计管理系统项目状态与债务台账
doc_type: workflow
module: project-governance
topic: project-state-and-debt-register
status: stable
created: 2026-06-14
updated: 2026-06-14
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

冻结日期：`2026-06-14`

### 2.1 生产状态

- 生产域名：`https://audit.lute-tlz-dddd.top`
- 服务器：`101.34.52.232`
- 主机名：`VM-0-16-ubuntu`
- 用户：`ubuntu`
- SSH key：`ai_video.pem`，必须保留在本项目本地，不能删除。
- 当前生产部署 SHA：`32027049eb7fa2b9d336af217a228b0f21dca990`
- `medical_audit_app`：running，healthy。
- `medical_audit_pg`：running，healthy。
- `ai_video_nginx`：running，作为共享公网入口。
- PostgreSQL 检索后端：`backend=postgres`，`ready=true`。
- Kimi embedding：`embedding_model=kimi-for-coding`，`embedding_dimension=1024`。
- 当前匹配 embeddings：`48985`。
- 最新本地生产 smoke 报告：`tmp/outputs/production-e2e-smoke-phase1-review-write-20260614.json`，状态 `pass`。
- 最新生产前端语义验收报告：`tmp/outputs/production-frontend-acceptance-phase1-20260614.json`，状态 `pass`。

生产结论：当前生产检索、引用、预览、静态门户和任务级复核写入链路可用；不能据此宣称真实医院审计、真实生成模型、真实权限体系或案件级合规闭环已完成。

### 2.2 本地仓库状态

- 当前工作区：`/Users/pray/project/medical_audit`
- 当前分支：`codex/product-integration-debt-phase2`
- 本地 HEAD：Phase 2.1 至 Phase 2.3 本地集成提交链，尚未部署到生产。
- 本地 `origin/main`：`596d6967 合并审计门户核心工作台`
- 当前分支相对 `origin/main`：包含产品集成债务 Phase 2 本地改造；生产仍运行 `32027049eb7fa2b9d336af217a228b0f21dca990`。
- 当前生产部署 SHA 位于 `codex/reference-workspace-shell-p0`，并作为当前主线历史的祖先保留。
- 当前存在额外 worktree：
  - `/Users/pray/.config/superpowers/worktrees/medical_audit/frontend-plan-02-projects-dashboard`
  - `/Users/pray/project/medical_audit_minimal_pr`
- 当前存在未跟踪资料和草稿目录：
  - `.kiro/`
  - `.playwright-mcp/`
  - `drafts/analysis/analysis-production-acceptance-p0-p1-*.md`
  - `drafts/analysis/analysis-reference-material-*.md`
  - `opendesign/`
  - `ref/`

仓库结论：当前本地状态适合继续做文档和计划同步；进入功能开发前，必须从明确的主线或新 `codex/` 分支开始，避免把历史 worktree、参考材料和草稿混入交付分支。

### 2.3 产品状态

已完成：

- `AI智能审计管理系统` 门户壳层已部署。
- 生产静态页面已覆盖工作台、对话、智能体、智能体广场、知识库、文档、数据分析、图谱、规则、报告、整改、归档、项目、引导自查、知识查询和疑点入口。
- 知识库查询引擎已具备检索、引用型回答、原文预览、索引管理、评测和回滚治理。
- 复核任务台已具备任务级持久化、报告准备度预检、附件归档、正式报告签发冻结、整改跟踪和结案只读锁。
- HIS 数据底座、staging、snapshot、字段映射校验、`CHARGE-RULE-001` fixture 与 staging 执行路径已具备工程基础。
- 智能体持久化已在本地 Phase 2.1 完成并通过 API、前端和浏览器联调验收；尚未部署到生产。
- 项目成员持久化已在本地 Phase 2.2 完成并通过 API、前端和浏览器联调验收；尚未部署到生产。
- AI 数据分析表格上传解析已在本地 Phase 2.3 完成，CSV、XLSX 和 XLSM 由 FastAPI 后端解析并返回字段画像；尚未部署到生产。

未完成：

- 智能体持久化尚未执行生产部署和生产库 `audit_agents` schema 应用。
- 项目成员持久化尚未执行生产部署和生产库 `audit_project_members` schema 应用。
- AI 数据分析上传文件尚未进入正式存储、病毒扫描、脱敏留存或历史分析记录。
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

## 3. 债务分级

| 等级 | 定义 | 处理原则 |
| --- | --- | --- |
| P0 | 会导致产品能力被误判、生产交付边界不清、真实业务验收不可执行或安全合规风险扩大的债务 | 先处理，不进入新功能扩张 |
| P1 | 不阻断当前生产运行，但阻断 V1.0 闭环、UAT 或持续开发效率的债务 | 进入最近两个开发批次 |
| P2 | 影响维护成本、认知清晰度、目录卫生和长期扩展性的债务 | 纳入持续治理 |

## 4. P0 债务台账

| 编号 | 类型 | 债务 | 当前证据 | 影响 | 处置计划 | 完成门禁 |
| --- | --- | --- | --- | --- | --- | --- |
| P0-01 | 产品集成债务 | 门户核心模块仍以静态数据和本地 state 为主 | `/agents`、`/projects` 已完成本地持久化；`/analytics` 已完成本地后端上传解析；其余模块仍多依赖 `portal-data` | 页面存在但业务闭环不完整，容易误判为功能已完成 | 继续补文档、知识库、图谱、报告、整改页面 API，生产部署 Phase 2.1-2.3 | 新增/查询/刷新后数据仍存在；上传解析走后端；前端测试和 API 测试通过 |
| P0-02 | 真实数据债务 | 生产验收主要基于受控脱敏 fixture | 生产文档明确 fixture 只证明链路 | 不能进入真实医院 UAT | 获取院方 DDL、字段字典、脱敏样本，执行 staging 验收 | `his-staging-acceptance` 对真实样本 PASS |
| P0-03 | AI 生成债务 | 线上答案生成 provider 未验证通过 | Kimi chat 403，Anthropic 401，fallback rate 100% | 不能宣称 AI 生成审计结论能力 | 决定可用 chat provider 或保持引用 fallback 为产品边界 | `answer-provider-smoke` 和真实生成评测 PASS |
| P0-04 | 权限安全债务 | 真实用户、角色、科室、全站权限未完成 | 当前 API 主要依赖 `X-Role`、`X-User-Id`、Nginx 注入 `X-API-Key` | 无法满足生产级审计系统权限边界 | 建立用户/角色/部门模型和会话认证，替换静态 header 口径 | 未授权路径 403；审计日志记录访问拒绝 |
| P0-05 | 合规闭环债务 | 证书级电子签章、长期留存介质、对象存储和病毒扫描未完成 | 当前仅 HMAC 归档签名和本地附件归档 | 报告与归档不能作为完整合规交付 | 设计签章、对象存储、扫描、留存介质方案 | 归档包、签章、验签和恢复演练通过 |
| P0-06 | 状态源债务 | 本地分支、生产 SHA、远端主线、多个 worktree 容易产生认知漂移 | 当前分支 ahead 1，生产 SHA 不等于本地 HEAD | 后续部署可能混入非目标状态 | 固定主线基线，后续功能从干净 `codex/` 分支切出 | `git status` 清晰；PR、部署 SHA、文档一致 |

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

1. 智能体 CRUD 和提示词版本：本地 Phase 2.1 已完成；生产部署和 schema 应用待执行。
2. 项目成员管理 API 和页面持久化：本地 Phase 2.2 已完成；生产部署和 schema 应用待执行。
3. 表格上传分析后端和工作簿解析任务：本地 Phase 2.3 已完成；生产部署、上传留存和历史记录待后续阶段。
4. 文档、知识库、图谱、报告、整改页面逐步接真实 API。

完成门禁：

- 刷新页面后新增数据仍存在。
- API 测试、前端测试和最小 E2E 均通过。
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

- 建立用户、角色、部门和权限模型。
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
