---
title: 医疗审计项目仓库说明
doc_type: knowledge
module: repository
topic: project-overview
status: stable
created: 2026-05-31
updated: 2026-05-31
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
2. `docs/product/product-development-plan-medical-audit-stable.md`
   当前开发排期、交付物和里程碑基线。
3. `docs/product/product-scope-baseline-stable.md`
   基于现有材料整理出的统一产品范围基线。
4. `docs/knowledge/audit-agent-platform-reference-stable.pptx`
   上游平台能力参考材料，不直接作为当前医疗项目需求基线。
5. `data/医保审核前期资料/`
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

## 下一步

下一步不直接写功能清单，先完成产品调研，确认：

- 这个产品最终卖给谁、由谁主导采购
- 第一阶段到底是医院内审工具，还是医保监管协同工具
- MVP 首个细分场景具体落在哪一条审计链路
- “两库四审”里哪些属于 V1，哪些属于 V1.1 以后
