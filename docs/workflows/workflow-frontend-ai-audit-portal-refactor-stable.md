---
title: AI智能审计管理系统前端门户化改版实施计划
doc_type: workflow
module: frontend
topic: ai-audit-portal-refactor
status: stable
created: 2026-06-12
updated: 2026-06-21
owner: self
source: human+ai
---

# AI智能审计管理系统前端门户化改版实施计划

## 1. 目标

将当前 AuditScope 前端从“医保自查 OS / 审计证据控制台”调整为参考系统式 `AI智能审计管理系统` 门户。

改版目标：

- 左侧固定 9 模块导航。
- 顶部栏和顶部多标签工作区。
- 历史对话侧边入口。
- 提示词型智能体列表、广场和新增智能体。
- 知识库三类只读展示。
- 文档检索首页。
- 上传表格 AI 数据分析和审计数据分析入口。
- 知识图谱入口。
- 审计底稿/报告首页。
- 项目管理和成员管理。

本计划只定义前端改版实施路径。生产部署、数据库迁移和真实写入型 E2E 仍按腾讯云部署工作流执行。

## 2. 已确认需求

| 编号 | 已确认内容 | 执行要求 |
| --- | --- | --- |
| D1 | 产品名称改为 `AI智能审计管理系统` | 替换前端主品牌、页面标题和文档口径 |
| D2 | 智能体为提示词类型 | 一个智能体对应一个提示词，可新增智能体，不做复杂编排 |
| D3 | 跨行业专题只是 UI 参考 | 当前项目只交付医疗/医保审计专题 |
| D4 | AI 数据分析必须具备上传表格分析能力 | 同时保留审计数据分析入口 |
| D5 | 项目管理必须包含成员管理 | 至少有成员列表、角色展示和新增成员入口 |
| D6 | 知识库区分个人、系统、公开三类 | 首期只读展示 |
| D7 | 顶部多标签作为 UI 硬性要求 | 支持打开、切换、关闭标签 |

## 3. 实施原则

- 先改信息架构，再改视觉细节。
- 先接入已有真实能力，再补新增模块。
- 不把提示词型智能体写成 agent 编排能力。
- 不把上传表格分析输出写成正式审计结论。
- 不把跨行业专题纳入当前交付范围。
- 不在普通业务页面暴露 `API-first`、`store`、`backend`、`persistent` 等工程术语。
- 所有导航入口必须有真实页面，禁止只显示低信息量 `plan` 或空桥接页。

## 4. 目标路由

| 模块 | 目标路由 | 首期状态 |
| --- | --- | --- |
| AI 对话 | `/chat` | 迁移现有 `/pages/chat` 能力或建立 Next 包装页 |
| 我的智能体 | `/agents/my` | 新增 |
| 智能体广场 | `/agents/marketplace` | 新增 |
| 知识库 | `/knowledge-bases` | 新增 |
| 文档检索 | `/document-search` | 基于 `/knowledge-query` 重构 |
| AI 数据分析 | `/data-analysis` | 新增，含上传表格分析 |
| 知识图谱 | `/knowledge-graph` | 新增只读入口 |
| 审计底稿/报告 | `/workpapers` | 新增首页，深链到 `/pages/review-tasks` |
| 项目管理 | `/projects` | 新增，含成员管理入口 |
| 审计日志 | `/audit-logs` | 可保留管理员入口 |
| 索引管理 | `/index-admin` | 可保留管理员入口 |

兼容要求：

- 现有 `/pages/chat`、`/pages/review-tasks`、`/pages/index-admin`、`/findings` 和 `/knowledge-query` 在改版期间不得失效。
- 新路由稳定后再决定是否把旧路由降级为兼容入口。

## 5. 阶段计划

### Phase 0：现状冻结与视觉基线

目标：

- 固化当前生产能力和截图基线。
- 确认所有现有真实能力的回归入口。

任务：

- 记录当前 `/workspace`、`/knowledge-query`、`/findings`、`/pages/chat`、`/pages/review-tasks`、`/pages/index-admin` 截图。
- 梳理现有 API client、类型定义和后端兼容页。
- 列出当前桥接页和 plan 页，作为改造清单。

退出标准：

- 当前能力清单完整。
- 不再新增临时导航或空页面。

### Phase 1：门户壳和多标签工作区

目标：

- 完成 `AI智能审计管理系统` 品牌。
- 完成左侧 9 模块导航、顶部栏、顶部多标签。

任务：

- 重构 `WorkspaceShell`、`AppSidebar`、`ProjectContextBar`。
- 新增 tab state，支持打开、切换、关闭。
- 导航项改为图标 + 模块名，移除长描述。
- 保留历史对话区。

退出标准：

- 9 个模块均可打开真实页面。
- 标签打开、切换、关闭可用。
- Desktop 和 mobile 无横向溢出。

### Phase 2：提示词型智能体

目标：

- 实现“我的智能体”和“智能体广场”。
- 支持新增提示词型智能体。

任务：

- 定义 `AuditAgentTemplate` 类型：名称、分类、审计专题、提示词、关联知识库、关联项目、创建人、更新时间。
- 新增内置医疗/医保审计模板。
- 实现新增智能体表单；首期可先使用前端状态或后端轻量存储，正式持久化另行评审。
- 分类支持全部、效率类、业务类、研究类。

退出标准：

- 可查看我的智能体。
- 可查看智能体广场。
- 可新增一个提示词型智能体。
- 页面不出现“自动办案”“自主执行”类表述。

### Phase 3：知识库和文档检索首页

目标：

- 将现有知识查询能力产品化为参考系统式知识库和文档检索。

任务：

- 新增知识库列表页，区分个人、系统、公开三类。
- 重构文档检索首页：搜索框、仅标题开关、搜索历史、库分类统计、对话文档、知识库文档。
- 查询结果按文档和引用分组展示。
- 保留原文预览入口和转入 AI 对话入口。

退出标准：

- 文档检索仍能调用现有查询接口。
- 查询结果仍保留引用和原文预览。
- 无引用时不得生成无依据审计结论。

### Phase 4：AI 数据分析和项目成员管理

目标：

- 实现上传表格分析能力。
- 实现项目管理和成员管理 UI。

任务：

- 新增表格上传入口，首期支持 `.xlsx` 和 `.csv`。
- 上传后展示字段概览、行列统计、空值/重复/异常类型提示和初步审计分析。
- 明确输出为分析线索，不是正式审计结论。
- 新增项目列表、项目详情、成员列表、角色展示和新增成员入口。

退出标准：

- 上传一个测试表格后能看到结构化分析结果。
- 项目详情页能看到成员列表和角色。
- 新增成员入口存在；真实权限生效可后置，但不能伪装为已生效。

### Phase 5：底稿报告、图谱和回归收口

目标：

- 补齐审计底稿/报告首页和知识图谱入口。
- 完成全站回归。

任务：

- 新增底稿/报告首页：历史生成记录、可选历史对话或复核任务、一键生成底稿入口。
- 新增知识图谱列表或静态预览：项目、知识库、文档、规则、疑点、复核任务、报告、整改事项关系。
- 回归现有复核任务台、签发、整改、导出、审计日志和索引管理。

退出标准：

- 所有门户导航入口真实可用。
- 现有生产 E2E 能力不回归。
- 视觉检查无明显重叠、溢出和不可读文本。

## 6. 验证计划

每个实现 PR 至少执行：

```bash
pnpm --dir web lint
pnpm --dir web typecheck
pnpm --dir web test
```

涉及后端 API 或模板时追加：

```bash
uv run pytest tests/knowledge_query/test_pages.py -q
uv run ruff check src tests scripts
```

上线前执行：

```bash
uv run python scripts/run-production-e2e-smoke.py \
  --base-url https://audit.lute-tlz-dddd.top \
  --report tmp/outputs/production-e2e-smoke-after-ai-audit-portal.json

pnpm production:frontend-acceptance -- \
  --base-url https://audit.lute-tlz-dddd.top \
  --output tmp/outputs/production-frontend-acceptance-latest.json \
  --screenshot-dir tmp/screenshots/production-frontend-acceptance-latest \
  --admin-role it-admin
```

视觉检查必须覆盖：

- 桌面端 `1440x1000`
- 移动端 `390x844`
- 左侧导航折叠或横向滚动状态
- 顶部多标签溢出状态
- 上传表格分析结果页
- 项目成员管理页

## 7. 风险与约束

- 上传表格分析可能引入文件解析、大小限制、敏感数据处理和异步任务问题；首期必须限制文件类型和大小。
- 成员管理 UI 不等于权限系统；真实权限生效需要独立后端设计。
- 顶部多标签如果做服务端持久化会扩大范围；首期只做前端状态。
- 智能体新增如果直接写库，需要补 schema、权限和审计日志；首期可先评审持久化方案。
- 参考系统是 UI/IA 参考，不是跨行业审计范围授权。

## 8. 不允许事项

- 不把参考系统账号、密码或截图中的敏感信息写入正式代码。
- 不对参考系统执行新增、编辑、删除、修改密码等写入动作。
- 不新增只有 `plan` 文案的导航页。
- 不把提示词型智能体描述成自主 agent。
- 不把上传表格分析结果描述成正式审计结论。
- 不删除现有生产入口，直到新入口通过回归验证。

## 9. 2026-06-21 第一阶段执行记录

本轮执行范围：前端门户壳层、登录页、浅蓝视觉 token、左侧导航分组、顶部状态栏、角色视图和阶段测试。

已完成：

- 新增 `/login` 登录界面，复用 `ref/前端/LOGO.png` 生成的前端 public 品牌资产。
- 将左侧导航重组为 `核心功能 / 专题审计 / 知识底座 / 系统管理`，核心功能直接覆盖 `AI 对话`、`智能体广场`、`文档检索`、`AI 数据分析`、`审计底稿生成`。
- 顶部栏新增全局检索输入、项目专题、后端待检测提示、AI 草稿人工确认提示、主任视图和四类角色视图。
- 视觉 token 调整为浅蓝医院内审工作台风格，圆角和间距更接近工业软件工作台。
- 保留现有 `web/src/lib/api-client.ts` 和后端 `/api/v1/*`、`/pages/*` 契约；本阶段未删除后端能力。

本地验收：

- `pnpm --dir web lint`：通过。
- `pnpm --dir web typecheck`：通过。
- `pnpm --dir web test`：通过，`11` 个 test files、`70` 个 tests。
- `pnpm --dir web build`：通过，生成 `21/21` 个静态页面，新增 `/login`。
- Playwright 本地视觉检查：`/login` 和 `/workspace` 在 `1440x900` 下均为 `h1Count=1`、无横向溢出。
- 截图：
  - `tmp/screenshots/phase1-ui-login-20260621.png`
  - `tmp/screenshots/phase1-ui-workspace-20260621.png`

边界：

- 本轮为本地前端重构和本地验收，未执行生产部署。
- 本轮未启动后端联调；顶部 `后端待检测` 是当前界面状态提示，不代表生产或本地 API 状态。
- 审计底稿生成仍沿用现有底稿/报告入口；未新增 Word/docx 生成后端适配层。
- 登录页为 UI 重构入口，真实认证、单点登录和权限生效不在本阶段完成范围内。

## 10. 2026-06-21 Phase 2 模板工作流执行记录

本轮执行范围：医保费用模板驱动的 `AI 数据分析` 与 `审计底稿生成` 前端切片。

已完成：

- 在 `web/src/lib/portal-data.ts` 中新增三张医保费用模板元数据：`表1 医保费用汇总表`、`表2 医保费用分类汇总表`、`表3 就诊费用明细表`。
- 在 `/analytics` 数据分析工作台新增常用表模板选择、模板字段、核验重点和分析要求联动。
- 保持上传解析仍走现有 `uploadAnalysisTable` 后端 API；本轮只增加模板引导，不改解析后端。
- 在 `/reports` 底稿生成页新增三类提示词模板：费用汇总风险底稿、分类费用复核清单、就诊明细疑点摘要。
- 底稿模板只进入 AI 对话和复核任务绑定入口，不宣称已具备 Word/docx 导出。

本地验收：

- `pnpm --dir web test -- src/app/'(workspace)'/workspace-pages.test.tsx`：通过，`22` 个 tests。
- `pnpm --dir web lint`：通过。
- `pnpm --dir web typecheck`：通过。
- `pnpm --dir web test`：通过，`11` 个 test files、`70` 个 tests。
- `pnpm --dir web build`：通过，生成 `21/21` 个静态页面。
- Playwright 本地视觉检查：`/analytics` 和 `/reports` 在 `1440x900` 下均为 `h1Count=1`、无横向溢出。
- 截图：
  - `tmp/screenshots/phase2-template-workflow-analytics-20260621.png`
  - `tmp/screenshots/phase2-template-workflow-reports-20260621.png`

边界：

- 本轮仍为本地前端重构和本地验收，未执行生产部署。
- 本轮没有 provider call，也没有生产或本地业务数据写入。
- Excel 模板已转化为 UI 元数据和提示词入口；未把模板文件内容写入后端配置、种子数据或生产知识库。
- 真实权限、正式认证、Word/docx 导出、正式报告签发仍保持后续阶段任务。

## 11. 2026-06-21 Phase 2 AI 对话工作台执行记录

本轮执行范围：`AI 对话` 第一屏从跳转表单升级为审证入口工作台。

已完成：

- 将 `/chat` 重构为三栏工作台：问题构建、审证表单、推荐问题与证据边界。
- 左侧展示审证步骤和知识来源覆盖，保持来源集合与文档检索页面一致。
- 中间保留智能体选择、审计问题输入、来源限定和进入后端审证深页的表单。
- 右侧展示推荐问题、证据边界和回答进入草稿态的输出去向。
- 保持提交路径为 `/pages/chat`，未新增 provider 调用或后端写入。

本地验收：

- `pnpm --dir web test -- src/app/'(workspace)'/workspace-pages.test.tsx`：通过，`22` 个 tests。
- `pnpm --dir web lint`：通过。
- `pnpm --dir web typecheck`：通过。
- `pnpm --dir web test`：通过，`11` 个 test files、`70` 个 tests。
- `pnpm --dir web build`：通过，生成 `21/21` 个静态页面。
- Playwright 本地视觉检查：`/chat` 在 `1440x900` 下 `h1Count=1`、无横向溢出。
- 截图：`tmp/screenshots/phase2-chat-workbench-20260621.png`。

边界：

- 本轮仍为本地前端 UI 重构，未执行生产部署。
- 本轮未启动 FastAPI 做本地 API 联调；`/chat` 表单仍交接到既有后端深页。
- 本轮没有 provider call，也没有生产或本地业务数据写入。

## 12. 2026-06-21 Phase 2 智能体模板创建闭环执行记录

本轮执行范围：提示词型智能体的广场模板、我的智能体新增表单和保存前边界提示。

已完成：

- `/agent-market` 智能体广场保留分类筛选和搜索，模板卡片入口改为 `套用并新增智能体`，跳转到 `/agents?template={id}#new-agent`。
- `/agents` 新增表单支持从模板参数预填名称、分类、审计专题、关联知识库、关联项目和提示词。
- `/agents` 右侧模板推荐支持在当前页套用模板；页面明确提示点击保存前不会写入后端。
- 新增智能体仍通过既有 `createAuditAgent` 调用 `/api/v1/agents`；本轮未新增存储层，也未绕过后端持久化契约。
- 修复模板锚点滚动遮挡问题，避免 `#new-agent` 被顶部栏覆盖。

本地验收：

- `pnpm --dir web test -- src/app/'(workspace)'/workspace-pages.test.tsx`：通过，`23` 个 tests。
- `pnpm --dir web lint`：通过。
- `pnpm --dir web typecheck`：通过。
- `pnpm --dir web test`：通过，`11` 个 test files、`71` 个 tests。
- `pnpm --dir web build`：通过，生成 `21/21` 个静态页面。
- Playwright 本地视觉检查：`/agent-market` 和 `/agents?template=template-identity-risk#new-agent` 在 `1440x900` 下均为 `h1Count=1`、无横向溢出；模板入口、模板预填和保存前不写入提示均可见。
- 截图：
  - `tmp/screenshots/phase2-agent-template-market-20260621.png`
  - `tmp/screenshots/phase2-agent-template-prefill-20260621.png`

边界：

- 本轮仍为本地前端 UI 重构，未执行生产部署。
- 本轮没有 provider call，也没有生产业务数据写入。
- 模板预填不是新增成功；只有点击 `新增智能体` 并通过现有后端接口后才进入我的智能体列表。
- 智能体提示词版本治理、版本对比 UI、下架/停用、软归档、角色可见范围、调用记录和效果反馈已完成本地首切片；生产部署验收、真实对话自动调用挂接、逐行 diff/审批流、反馈统计看板和真实权限闭环仍保持后续任务。

## 13. 2026-06-21 Phase 3 文档检索首页执行记录

本轮执行范围：`文档检索` 首页的信息架构、仅标题模式、引用分组和知识库只读联动。

已完成：

- `/documents` 左侧来源区升级为 `知识库分类统计`，继续按法规政策、监管两库、医保目录和风险清单限定后端检索范围。
- `/documents` 检索框新增 `仅标题` 开关；该模式用于前端文档卡片筛选，后端仍按现有全文检索接口返回引用。
- `/documents` 顶部新增 `无引用不下结论` 门禁提示，检索结果无引用时只作为补证线索。
- `/documents` 检索结果按 `source_collection` 分组展示引用，并保留 `/pages/preview/{chunk_id}` 原文核验入口和转入 AI 对话入口。
- `/knowledge-base` 保持个人、系统、公开知识库只读展示，作为统一检索首页的索引覆盖入口。
- 本轮未修改 `web/src/lib/api-client.ts`、`web/src/lib/api-types.ts` 或 FastAPI router。

本地验收：

- `pnpm --dir web test -- src/app/'(workspace)'/workspace-pages.test.tsx`：通过，`23` 个 tests。
- `pnpm --dir web lint`：通过。
- `pnpm --dir web typecheck`：通过。
- `pnpm --dir web test`：通过，`11` 个 test files、`71` 个 tests。
- `pnpm --dir web build`：通过，生成 `21/21` 个静态页面。
- Playwright 本地视觉检查：`/documents` 和 `/knowledge-base` 在 `1440x900` 下均为 `h1Count=1`、无横向溢出；`/documents` 中仅标题、无引用门禁和知识库分类统计均可见。
- 截图：
  - `tmp/screenshots/phase3-document-search-home-20260621.png`
  - `tmp/screenshots/phase3-knowledge-base-readonly-20260621.png`

边界：

- 本轮仍为本地前端 UI 重构，未执行生产部署。
- 本轮没有 provider call，也没有生产业务数据写入。
- 本轮未启动本地 FastAPI 做 API 联调；知识库页的检索索引状态在本地后端未启动时可显示异常。
- `仅标题` 已接入后端 `title_only` 查询参数和标题/路径元数据过滤；本地页面仍保留前端文档卡片筛选用于降低用户扫描成本。

## 14. 2026-06-21 Phase 3 权限角色 UI 映射执行记录

本轮执行范围：`项目管理` 页的医院权限角色矩阵和新增成员表单映射。

已完成：

- 在 `web/src/lib/portal-data.ts` 中新增四类医院权限角色：`管理员`、`技术人员`、`主任`、`普通成员`。
- 四类医院权限角色当前映射到既有项目成员角色，后端项目成员角色枚举暂不变。
- `/projects` 主内容区新增 `医院权限角色矩阵`，展示职责、可执行操作和当前权限边界。
- `/projects` 新增成员表单增加 `权限角色视图`，选择 `技术人员` 时同步映射 `项目成员角色=信息科` 和 `部门=信息科`。
- 页面明确提示权限角色视图只做前端映射，真实账号开通、权限生效和禁用移除仍需后续后端认证体系验证。
- 本轮未修改 `web/src/lib/api-client.ts`、`web/src/lib/api-types.ts` 或 FastAPI router。

本地验收：

- `pnpm --dir web test -- src/app/'(workspace)'/workspace-pages.test.tsx`：通过，`23` 个 tests。
- `pnpm --dir web lint`：通过。
- `pnpm --dir web typecheck`：通过。
- `pnpm --dir web test`：通过，`11` 个 test files、`71` 个 tests。
- `pnpm --dir web build`：通过，生成 `21/21` 个静态页面。
- Playwright 本地视觉检查：`/projects` 在 `1440x1100` 下 `h1Count=1`、无横向溢出；`医院权限角色矩阵`、`权限角色视图` 和前端映射边界提示均可见；选择 `技术人员` 后项目成员角色和部门均映射为 `信息科`。
- 截图：`tmp/screenshots/phase3-role-permission-projects-20260621.png`。

边界：

- 本轮仍为本地前端 UI 重构，未执行生产部署。
- 本轮没有 provider call，也没有生产业务数据写入。
- 医院权限角色矩阵当前只做前端视图和新增成员表单映射，不代表真实权限、账号开通、SSO、禁用移除或审计日志权限闭环已经生效。
- 后端仍使用既有项目成员角色契约；真实用户、角色、科室、权限模型和角色枚举治理保持后续阶段任务。

## 15. 2026-06-21 Phase 5 知识图谱只读入口验收记录

本轮执行范围：`知识图谱` 入口的只读关系预览和本地验收。

已完成：

- `/graph` 已提供医保基金使用合规专项的只读图谱入口，覆盖项目、知识库、文档、规则、疑点、复核、报告和整改节点。
- 图谱主区展示静态 SVG 关系预览、节点类型统计、关系链路统计、强证据关系和待补关系。
- 页面下方展示证据链关系卡片，右侧展示节点证据入口，并保留转入 `/documents` 核验证据来源的入口。
- 图谱数据来自前端 `graphNodes` 和 `graphRelations`，本轮不引入动态图数据库或新增后端查询契约。
- 单测已覆盖正常检索索引状态和本地后端不可用时的图谱拓扑保留。

本地验收：

- `pnpm --dir web test -- src/app/'(workspace)'/workspace-pages.test.tsx`：通过，`23` 个 tests。
- `pnpm --dir web lint`：通过。
- `pnpm --dir web typecheck`：通过。
- `pnpm --dir web test`：通过，`11` 个 test files、`71` 个 tests。
- `pnpm --dir web build`：通过，生成 `21/21` 个静态页面。
- Playwright 本地视觉检查：`/graph` 在 `1440x1000` 和 `390x844` 下均为 `h1Count=1`、无横向溢出；`审计知识图谱静态关系预览`、`节点证据`、`证据链关系` 和 `首期只读` 均可见。
- 截图：
  - `tmp/screenshots/phase5-graph-readonly-desktop-20260621.png`
  - `tmp/screenshots/phase5-graph-readonly-mobile-20260621.png`

边界：

- 本轮仍为本地前端 UI 验收和状态同步，未执行生产部署。
- 本轮没有 provider call，也没有生产业务数据写入。
- 本地视觉验收未启动 FastAPI 后端；图谱页的索引状态提示不代表本轮完成前后端联调。
- 当前图谱是前端只读关系预览，不代表已经具备动态图数据库、图谱编辑、图谱查询 API 或自动证据链推理能力。

## 16. 2026-06-21 Phase 5 规则整改归档入口验收记录

本轮执行范围：`专题规则库`、`补证整改`、`项目档案` 三个回归收口入口的本地验收和状态同步。

已完成：

- `/rules` 已展示规则来源覆盖、规则清单、最近运行、发布门禁和规则输出边界。
- `/rules` 保留进入 `/pages/index-admin` 的索引管理入口，以及转入疑点和 AI 审证的工作流入口。
- `/remediation` 已展示整改台账、补证请求、关闭门禁、整改动态和图谱证据链入口。
- `/archive` 已展示项目档案包、审计日志治理策略、归档巡检、签名链和入档动态。
- `/archive` 保留受控审计日志台和日志导出入口，界面继续提示日志查询和导出必须经过权限校验。
- 本批次未修改 `web/src/lib/api-client.ts`、`web/src/lib/api-types.ts` 或 FastAPI router。

本地验收：

- `pnpm --dir web test -- src/app/'(workspace)'/workspace-pages.test.tsx`：通过，`23` 个 tests。
- `pnpm --dir web lint`：通过。
- `pnpm --dir web typecheck`：通过。
- `pnpm --dir web test`：通过，`11` 个 test files、`71` 个 tests。
- `pnpm --dir web build`：通过，生成 `21/21` 个静态页面。
- Playwright production server 本地视觉检查：`/rules`、`/remediation`、`/archive` 在 `1440x1000` 和 `390x844` 下均为 `h1Count=1`、无横向溢出。
- 截图：
  - `tmp/screenshots/phase5-rules-prod-desktop-20260621.png`
  - `tmp/screenshots/phase5-rules-prod-mobile-20260621.png`
  - `tmp/screenshots/phase5-remediation-prod-desktop-20260621.png`
  - `tmp/screenshots/phase5-remediation-prod-mobile-20260621.png`
  - `tmp/screenshots/phase5-archive-prod-desktop-20260621.png`
  - `tmp/screenshots/phase5-archive-prod-mobile-20260621.png`

边界：

- `validation_scope=local_ui`。
- `backend_loopback_status=not_started`。
- `production_side_effect=none`。
- `provider_call_status=not_called`。
- 当前三页使用前端静态关系和既有兼容入口；规则执行、整改写入、审计日志权限、归档签名和长期留存仍按后续后端/生产验收链路处理。
