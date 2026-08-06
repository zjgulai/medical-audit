---
title: UI精细化优化方案与执行TODO
doc_type: analysis
module: ui-ux
status: active
created: 2026-08-06
updated: 2026-08-06
owner: self
source: human+ai
---

# 医疗审计产品 UI 精细化优化方案

> 基于：PPT反馈19条需求（2026-07-11）、生产UI reconciliation计划（2026-07-16）、
> 当前生产代码（aa623e20）、行业最佳实践（飞书/钉钉/ServiceNow/Wolters Kluwer）
> 
> 原则：**不改变整体配色风格（#155fa8蓝/白/浅蓝灰）**，在此基础上做精细化提升

---

## 第一部分：深度问题分析

### 1.1 信息架构问题

**问题**：当前导航把 17 个入口压成"主导航 6 + 更多折叠 11"的结构。
用户要找"规则库""补证整改""知识图谱"都需要先展开"更多"，
而这三个恰恰是医院审计员最常用的工作入口。

**行业参考**：飞书工作台把高频功能固定在侧栏前 8 位，
低频管理功能收在底部；ServiceNow 按用户角色动态显示导航项。

**核心矛盾**：当前 `visiblePrimaryNavigation` 是产品设计者认为重要的入口，
而审计员实际工作流是：疑点 → 复核 → 知识查询 → 整改 → 报告，
这个路径在当前导航里需要在多个折叠层里寻找。

### 1.2 视觉密度问题

**问题1**：medical-audit 页顶部有 3 层 tab（工具栏 7 项 + 视图 tab 4 项 + 规则 tab 7 项），
用户一进页面看到 18 个 tab，不知道从哪里开始。

**问题2**：符号导航（"专"/"问"/"检"/"智"/"库"/"检"/"识"/"数"/"图"/"稿"/"项"/"舱"/"查"/"规"/"整"/"档"/"索"/"志"）
纯汉字方块无法形成视觉差异，用户需要逐字阅读才能找到入口。

**问题3**：replica 体系的 `.replica-page` 最大宽度 1180px，
而 audit 体系页面有 `.audit-workbench-main` 限制 72rem，
两套体系混用导致页面在同一屏幕宽度下呈现不同布局。

### 1.3 交互效率问题

**问题1**：疑点卡片（audit-finding）当前是紧凑列表行，
医院审计员核心操作是"看疑点 → 判断性质 → 创建复核任务"，
列表行隐藏了关键的"金额""违规类型""规则依据"信息，
需要展开才能操作，增加了决策成本。

**问题2**：工作流弹框（对话框）没有步骤进度指示。
创建复核任务弹框一次性呈现所有字段，
而审计员实际需要的是"选择疑点 → 填写复核意见 → 指定负责人 → 确认提交"的步骤化流程。

**问题3**：OCR页、合同审计页的上传结果呈现方式过于技术化（JSON字段直接展示），
缺少对审计员友好的结论摘要层。

---

## 第二部分：优化原则

1. **不改配色**：保持 `--audit-primary: #155fa8` 蓝色体系
2. **不拆体系**：replica 和 audit 两套 CSS 共存，但优先在 replica 页面中统一规范
3. **最小改动**：每个 TODO 对应1-3个文件，有测试覆盖
4. **医院场景优先**：优化决策以"住院医保审计员"为第一用户，而非开发者或演示用途
5. **数据真实性保持**：不改变任何 API 调用逻辑，只改视觉呈现层

---

## 第三部分：执行 TODO

### 模块 A：导航重构（优先级：P0）

#### A1 — 导航分组可见性改造
**问题**：核心工作入口（审计/复核/整改）藏在折叠区
**方案**：将 `visiblePrimaryNavigation` 扩展为按用户角色动态的两区结构：
- **上区"审计工作流"（6项固定）**：审计驾驶舱、医保专题、审计助手、疑点复核、补证整改、审计底稿
- **下区"工具支撑"（4项固定）**：知识库、文档检索、AI数据分析、智能体
- **折叠区（仅后台功能）**：索引管理、审计日志

**文件**：`web/src/lib/navigation.ts`（改 visiblePrimaryNavigation 顺序和分组）
**测试**：`web/src/lib/navigation.test.ts`（验证分组和顺序）

#### A2 — 导航符号改用 emoji/图标
**问题**：纯汉字方块无视觉区分
**方案**：用 Unicode 符号替代汉字（保持不引入图标库约束）：
- 审计驾驶舱：🔍 → `"🔍"` 
- 医保专题：`"🏥"`
- 审计助手：`"💬"`
- 疑点列表：`"⚠"`
- 补证整改：`"✓"`
- 知识库：`"📚"`
- 文档检索：`"🔎"`
- AI数据分析：`"📊"`
- 规则库：`"📋"`
- 图谱：`"🕸"`

**方案备选**：用2字汉字替代1字（"审计""医保""对话""疑点""整改"），
既有语义清晰度又无 emoji 兼容风险（**推荐此方案**）

**文件**：`web/src/lib/navigation.ts`（改 symbol 字段）
**文件**：`web/src/components/shell/app-sidebar.tsx`（图标区 size 从 7 改为 8，字号 text-[11px] 改 text-[10px]）

#### A3 — 移动端导航底栏固定4项
**问题**：移动端 grid-cols-5 展示 5 项导航，但 5 项是主导航排列而非移动端高频入口
**方案**：移动端固定底栏仅展示4项（审计助手/医保专题/疑点/项目）+溢出按钮

**文件**：`web/src/components/shell/app-sidebar.tsx`（改移动端 grid 为 4+1）

---

### 模块 B：登录页精化（优先级：P0）

**已完成**：PPT R01/R02 已实现（删除了副标题和角色说明）
**仍存在的问题**：
1. 登录卡背景右侧空白区域没有视觉信息（对于宽屏展示浪费了 50% 空间）
2. 登录按钮 `py-3` + `text-sm` 偏紧，不符合表单主按钮的视觉重量期望
3. "联系信息中心" href="#support" 是锚点，不是真实跳转，但视觉上像链接

#### B1 — 登录页右侧装饰区
**方案**：宽屏时（md及以上）右侧增加一个简洁的产品特性介绍区：
- 3 个功能亮点卡（各一行标题 + 一行描述）
- 配色用 audit-primary-soft 背景
- 不需要任何图片资源（用 CSS 渐变）

**文件**：`web/src/components/login/login-surface.tsx`
**文件**：`web/src/app/globals.css`（新增 `.audit-login-feature-rail` 样式）

#### B2 — 登录表单微调
**方案**：
- 登录按钮高度增加到 `py-3.5`（从 py-3），字号 `text-base`（从 text-sm继承）
- "联系信息中心"改为 `<span>` 样式的文字提示（不可点击的提示文字）
- 表单 gap 从 `space-y-5` 改 `space-y-4`，整体更紧凑

**文件**：`web/src/components/login/login-surface.tsx`

---

### 模块 C：医保审计工作台（medical-audit）精化（优先级：P0）

这是产品核心页面（1707行），当前问题最多。

#### C1 — 三层Tab合并为两层
**当前**：工具栏（7项）+ 视图Tab（4项）+ 规则筛选Tab（7项）= 三层18个Tab
**方案**：
- 工具栏 → 改为左侧竖向图标栏（类Figma左工具栏），宽 48px，只显示图标+tooltip
- 视图Tab → 保留横向，但限制在 4 项内（当前已经是4项 ✅）
- 规则筛选 → 改为下拉选择器（`<select>`），不再是横向Tab
这样三层18个Tab变成：1条视图Tab + 1个筛选下拉

**文件**：`web/src/app/(workspace)/medical-audit/page.tsx`（改 toolModules 渲染和 ruleFilter 渲染）

#### C2 — 疑点卡片从列表行升级为信息卡
**当前**：疑点渲染为表格行，只显示：finding_key | 类型 | 严重度 | 状态
**方案**：每条疑点改为卡片，包含：
```
┌──────────────────────────────────────────────┐
│ [高风险] 分解住院疑点                    [待复核] │
│ 患者 P001 · 急性阑尾炎 · 间隔10天              │
│ 涉及金额：¥12,800   规则：split-hosp-r001      │
│ [创建复核任务]  [查询知识库]  [加入报告]         │
└──────────────────────────────────────────────┘
```
每卡片 3 行信息 + 操作按钮行，替代当前的单行表格

**文件**：`web/src/app/(workspace)/medical-audit/page.tsx`（改 `_renderFinding` 或对应渲染函数）
**文件**：`web/src/app/globals.css`（新增 `.audit-finding-card` 样式）

#### C3 — 项目选择器下移至内容区
**当前**：项目选择器在页面头部独立一行，占用过多垂直空间
**方案**：将项目选择器移入视图Tab旁边的右侧区域，内联展示
从：
```
[页面标题行]
[项目选择器独立行]
[工具栏Tab]
[视图Tab]
```
改为：
```
[页面标题行 ←→ 项目选择器]
[工具栏（竖向）| 视图Tab + 规则筛选]
```

**文件**：`web/src/app/(workspace)/medical-audit/page.tsx`（调整 JSX 结构）

#### C4 — 工作流弹框步骤化
**当前**：创建复核任务弹框一次性呈现所有字段
**方案**：改为3步进度弹框：
- 步骤1：选择疑点范围（已选 N 条）+ 复核类型
- 步骤2：填写初步意见 + 关联规则依据
- 步骤3：指定负责人 + 确认提交

步骤进度用 `[1] → [2] → [3]` 简单数字步骤条显示

**文件**：`web/src/app/(workspace)/medical-audit/page.tsx`（改 WorkflowDialog 渲染）
**文件**：`web/src/app/globals.css`（新增 `.audit-stepper` 样式）

---

### 模块 D：全局 replica 页面样式统一（优先级：P1）

当前 replica 页面（agents/agent-market/reports/findings/remediation等）
使用独立的 `.replica-*` CSS 体系，与 audit 体系存在视觉割裂。

#### D1 — 统一页面最大宽度
**当前**：replica-page 最大宽 1180px，audit workbench 最大宽 72rem（1152px）
**方案**：全局统一为 `min(1200px, calc(100% - 48px))`

**文件**：`web/src/app/globals.css`（修改 `.replica-page` width 值）

#### D2 — replica 卡片阴影与 audit 卡片对齐
**当前**：replica-kb-card 用 `box-shadow: 0 2px 8px rgba(0,0,0,0.06)`
audit 卡片用 `--audit-shadow-card: 0 8px 20px rgb(23 62 105 / 0.055)`
**方案**：replica-kb-card 改用 `var(--audit-shadow-card)`

**文件**：`web/src/app/globals.css`（4行修改）

#### D3 — 页面头部（replica-page-header）与 audit-page-header 对齐
**当前**：replica-page-header 的 h1 是 font-weight: 750，颜色 #1f1f1f
audit 体系用 `--audit-ink: #17233b`
**方案**：replica 变量颜色全部引用 audit 变量（避免颜色分叉）

**文件**：`web/src/app/globals.css`（改 `.replica-page` 作用域内的颜色为 var(--audit-*) 引用）

---

### 模块 E：审计助手（chat）页面精化（优先级：P1）

#### E1 — 历史对话按钮优化（PPT R07 遗留）
**当前**：PPT R07 要求改为"图标+历史对话"胶囊按钮，检查当前实现状态

**文件**：`web/src/app/(workspace)/chat/page.tsx`（验证并修复）

#### E2 — 知识来源选择器显示优化  
**当前**：source_collections 以文字列表展示，选中后无明显视觉反馈
**方案**：选中的 collection 用 audit-primary 色的 badge 样式，未选中用 outline badge
同时在 badge 内加上该库的文档数（从 KB catalog API 读取）

**文件**：`web/src/app/(workspace)/chat/page.tsx`（改 collection 选择渲染）

---

### 模块 F：OCR 工作台精化（优先级：P1）

#### F1 — OCR 结果从技术视图改为审计员视图
**当前**：OCR 结果展示原始 pages[].text，页面映射状态等技术字段
**方案**：增加结论摘要层：
```
┌─ OCR 提取完成 ──────────────────────────┐
│  📄 test-ocr-real.png                     │
│  共 1 页 · 识别引擎：DeepSeek+Tesseract   │
│                                           │
│  提取文本摘要（前200字）：                │
│  "Medical Audit Report 2026..."           │
│                                           │
│  [复制全文] [用于审计对话] [下载文本]      │
└───────────────────────────────────────────┘
```

**文件**：`web/src/app/(workspace)/ocr/page.tsx`

---

### 模块 G：数据状态一致性优化（优先级：P1）

所有页面的 loading/empty/error 状态需统一设计语言。

#### G1 — 统一 empty state 组件
**当前**：各页面空态自行实现（有的是灰色文字、有的是空列表、有的什么都不显示）
**方案**：新增 `EmptyState` 共享组件：
```
[图标]
[主文字]：暂无数据
[副文字]：系统尚未接收到相关数据，您可以...
[CTA按钮]（可选）
```

**文件**：`web/src/components/ui/empty-state.tsx`（新建）
**文件**：`web/src/app/globals.css`（新增 `.audit-empty-state` 样式）

#### G2 — 数据来源 badge 统一
**当前**：DataSourceBadge 组件存在但部分页面没有使用
**方案**：在 replica-page 系列的每个主内容区顶部强制展示数据来源 badge
（SqlAlchemy/静态/演示数据 三种状态，不同颜色）

**文件**：`web/src/components/ui/data-source-badge.tsx`（改样式）
**文件**：各页面（确保每个工作台都渲染 badge）

---

## 第四部分：执行顺序 TODO

### Sprint UI-1（本周，纯视觉/不改逻辑）

| # | 任务 | 文件 | 预计行数 |
|---|---|---|---|
| UI-1.1 | A2: 导航符号改为2字汉字 | navigation.ts, app-sidebar.tsx | ~30行 |
| UI-1.2 | A1: 重排 visiblePrimaryNavigation 顺序 | navigation.ts | ~15行 |
| UI-1.3 | B2: 登录按钮微调 | login-surface.tsx | ~5行 |
| UI-1.4 | D1: 统一页面最大宽度 | globals.css | ~3行 |
| UI-1.5 | D2: replica卡片阴影对齐 | globals.css | ~8行 |
| UI-1.6 | G1: 新建 EmptyState 组件 | empty-state.tsx, globals.css | ~60行 |

### Sprint UI-2（下周，中等复杂度）

| # | 任务 | 文件 | 预计行数 |
|---|---|---|---|
| UI-2.1 | C1: medical-audit 三层Tab合并 | medical-audit/page.tsx, globals.css | ~80行 |
| UI-2.2 | C2: 疑点卡片升级 | medical-audit/page.tsx, globals.css | ~100行 |
| UI-2.3 | E1: chat历史按钮验证/修复 | chat/page.tsx | ~20行 |
| UI-2.4 | F1: OCR结果审计员视图 | ocr/page.tsx | ~60行 |
| UI-2.5 | D3: replica变量引用audit变量 | globals.css | ~30行 |

### Sprint UI-3（第三周，复杂交互）

| # | 任务 | 文件 | 预计行数 |
|---|---|---|---|
| UI-3.1 | C3: 项目选择器位置调整 | medical-audit/page.tsx | ~40行 |
| UI-3.2 | C4: 工作流弹框步骤化 | medical-audit/page.tsx, globals.css | ~150行 |
| UI-3.3 | B1: 登录页右侧装饰区 | login-surface.tsx, globals.css | ~80行 |
| UI-3.4 | A3: 移动端导航4+1 | app-sidebar.tsx | ~30行 |
| UI-3.5 | E2: 知识来源badge优化 | chat/page.tsx | ~50行 |

---

## 第五部分：关键设计决策

### 为什么用2字汉字而不是emoji
emoji 在不同操作系统渲染差异大（Windows vs macOS vs Linux），
医院的信息中心电脑多为 Windows，emoji 兼容性风险高。
2字汉字（"审计"/"医保"/"对话"/"疑点"/"整改"/"知识"/"文档"）
在所有环境下渲染一致，且语义比1字更清晰。

### 为什么不引入图标库
PPT 反馈约束、当前代码无图标库依赖、医院内网环境可能无法加载 CDN 字体。
保持纯 CSS + Unicode 方案，无额外依赖。

### 为什么疑点卡片比列表行好
医院审计员的核心任务是"看疑点 → 判断性质 → 操作"，
卡片能在一个视觉单元内展示决策所需的全部信息（金额/类型/规则/状态），
而列表行只能展示2-3个字段，需要点击展开才能操作。
行业参考：Workday 的 Alert card、ServiceNow 的 Incident card 均采用卡片式。

### 为什么工作流要步骤化
当前弹框一次性呈现 8+ 个字段，认知负担大。
步骤化的好处：
1. 每步只问1-2个问题，降低决策疲劳
2. 用户可以随时看到"我在第几步"，不担心操作流程
3. 可以在步骤间验证必填项，减少提交失败
行业参考：飞书审批流、钉钉工作流均采用步骤化弹框。
