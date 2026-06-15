---
title: 医疗审计项目仓库说明
doc_type: knowledge
module: repository
topic: project-overview
status: stable
created: 2026-05-31
updated: 2026-06-15
owner: self
source: human+ai
---

# 医疗审计项目

## 当前定位

当前项目不是通用 SaaS，也不是纯研究仓库，而是一个面向医院场景的私有化医疗审计产品项目。现有材料指向的最小可落地目标，是先在单院环境内跑通基于 HIS 数据的医疗/医保审计 MVP。

核心闭环为：

`法规与知识支撑 -> 合规判断与风险识别 -> 审计底稿与报告 -> 整改跟踪`

## 当前材料的权威层级

1. `docs/product/product-meeting-consensus-20260315-stable.md`
   当前 MVP 范围的最高优先级业务共识。
2. `docs/product/product-prd-medical-audit-v1-stable.md`
   当前 V1.0 产品执行基线，承接业务共识、架构边界和验收要求。
3. `docs/product/product-development-plan-medical-audit-stable.md`
   当前开发排期、交付物和里程碑基线。
4. `docs/product/product-scope-baseline-stable.md`
   基于现有材料整理出的统一产品范围基线。
5. `docs/knowledge/knowledge-query-evidence-register-stable.md`
   知识库查询引擎草稿证据登记表，说明哪些评测、迁移和 UI 复盘草稿可以作为历史证据保留。
6. `docs/knowledge/audit-agent-platform-reference-stable.pptx`
   上游平台能力参考材料，不直接作为当前医疗项目需求基线。
7. `data/医保审核前期资料/`
   当前项目的正式输入资料库。

## 目录说明

- `docs/product/`: 产品范围、会议共识、计划基线
- `docs/knowledge/`: 项目资料审计、参考材料、长期知识沉淀
- `docs/architecture/`: 后续系统架构、模块边界、数据流设计
- `docs/api/`: 后续接口设计
- `docs/workflows/`: 协作流程、操作规范
- `assets/images/`: 需要在文档中引用的正式图片资产
- `archive/docs/`: 原始源文件、历史版本和不再直接参与协作的材料
- `drafts/`: 未定稿分析、需求草稿、方案探索
- `tmp/`: 临时输出、截图、调试产物
- `data/`: 正式输入资料和知识源文件

## 当前已完成的初始化

- 已初始化 git 仓库
- 已建立标准目录骨架
- 已将根目录文档迁入正式区、知识区或归档区
- 已补充项目资料审计结论和产品范围基线
- 已落地 `docs/product/product-prd-medical-audit-v1-stable.md` 作为 V1.0 PRD 执行基线
- 已形成知识库查询引擎的架构、API 和运行手册
- 已建立 `docs/knowledge/knowledge-query-evidence-register-stable.md`，用于登记知识库评测、迁移、UI smoke 和 provider 预检草稿证据
- 已产出 `drafts/docs/architecture-his-data-ingestion-design-draft-20260602.md`，作为 HIS DDL、字段映射和任务级快照设计的评审草稿
- 已完成 `国家规章平台文档.zip` 增量资料补充、稳定增量索引激活和腾讯云生产 E2E 复核；当前生产 active index 为 `incremental-20260615-national-regulation-stable-20260615103344`，覆盖 `503` 个文档、`49051` 个 chunks 和 `49051` 条 embeddings

## 下一步

下一步围绕 V1.0 PRD 和当前生产基线继续收敛：

- 评审 HIS 数据接入设计草稿，并向院方/信息科索取 HIS DDL、字段字典、脱敏历史数据和验证集
- 补充首个专项审计场景 PRD、底稿报告模板设计
- 与院方确认 HIS DDL、脱敏测试集、报告模板和准确率口径
- 将 V1.0 的 0/1 合规判定、复核、报告和整改链路拆成可开发任务
- 继续补齐真实生成模型 provider、个人/系统/公开知识库治理、文档权限、真实医院数据验收和案件级审计闭环
