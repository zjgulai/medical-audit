---
title: medical_audit 文档入口
doc_type: documentation-index
module: documentation
status: active
created: 2026-08-13
updated: 2026-08-13
owner: self
source: human+ai
---

# medical_audit 文档入口

本目录是 `AI 审计一体化协作平台` 的权威文档入口。当前候选基于 Git 提交 `ccc73e95820e39559430e96c01d52c8dfb77a246` 开发；候选变更尚未合并、推送或部署。2026 年 8 月 12 日的 L3 只读证据显示，生产运行 `25e1654e0c44ca5cbb2bb42e82debdb40fa6f224`。

## 阅读顺序

1. [系统架构](architecture/architecture-system-overview-stable.md)：理解 Next.js、FastAPI、存储、访问门禁和部署边界。
2. [平台 API](api/api-medical-audit-platform-v1-stable.md)：查询规范路径、权限、错误码和接口族。
3. [用户 Playbook](playbooks/user-playbook-medical-audit-v1-stable.md)：按页面和角色执行具体功能。
4. [管理员运维 Playbook](playbooks/admin-operations-playbook-stable.md)：执行本地验收、生产只读检查、备份和恢复门禁。
5. [生产功能验收矩阵](testing/production-feature-acceptance-matrix-stable.md)：区分本地、生产壳层和未验证业务能力。
6. [中文技术写作规则](style/chinese-technical-writing-style.md)：维护项目文档和界面文案。
7. [项目状态与技术债台账](workflows/workflow-project-state-and-debt-register-stable.md)：查看当前状态、阻塞项和下一门禁。
8. [全量复盘与清理审计](../drafts/analysis/project-reanalysis-and-gap-audit-20260813.md)：查看本地/生产差异、待办和 exact-path 清理候选。

## 权威层级

| 层级 | 文档或证据 | 用途 |
|---|---|---|
| L0 | Git、测试收据、生产只读收据 | 当前工程与运行事实 |
| L1 | 会议共识、PRD、范围基线 | 产品目标和约束 |
| L2 | 架构、API、Playbook | 技术和操作合同 |
| L3 | 状态与技术债台账 | 唯一当前状态快照 |
| L4 | delivery、handoff、backlog、Sprint 计划 | 带日期的历史执行记录 |

当文档互相冲突时，以带 SHA、观测时间和证据等级的较新证据为准。历史文档不得单独证明当前生产状态。

## 当前证据边界

- `fact`：本地候选已使用临时 SQLite 和确定性 Fake Provider 完成 17 项 Playwright E2E；机器收据覆盖 20 个独立页面和 3 个兼容别名。
- `fact`：候选将生产访问模式设为 `public-shell-readonly`，保护业务读取、写入和 Provider 调用。
- `fact`：候选尚未部署，因此不能把本地访问门禁结果称为生产通过。
- `inference`：生产应用源码与候选基线的用户态差异很小，但运行配置、数据和业务行为仍需发布后只读验收。
- `uncertain`：可信身份、真实 HIS、真实 OCR/LLM Provider、现场 UAT 和隔离恢复演练尚未完成。

## 历史文档状态

- 名称含 `stable` 的产品共识、PRD 和范围基线继续作为规范性来源。
- 2026 年 8 月 13 日以前的 handoff、backlog 和 Sprint delivery 是历史快照；若状态字段为 `superseded`，不得用于当前完成声明。
- `.kiro/plan/` 是执行账本，不是生产完成证明。
- `drafts/analysis/` 中的调查材料只有在带观测时间、SHA 和证据等级时，才可作为对应时间点的证据。

## 文档校验

```bash
pnpm docs:lint
```

该命令运行固定版本的中文文案检查器，并验证 frontmatter、相对链接、标题层级、页面与 Playbook 覆盖、API 族覆盖和当前状态证据字段。
