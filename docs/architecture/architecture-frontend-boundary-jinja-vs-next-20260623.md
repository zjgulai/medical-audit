---
title: 前端边界：Next 门户与 FastAPI 兼容深页
doc_type: architecture
module: frontend
topic: jinja-next-boundary
status: stable
created: 2026-06-23
updated: 2026-08-22
owner: self
source: human+ai
---

# 前端边界：Next 门户与 FastAPI 兼容深页

## 1. 当前结论

Next.js 已经是产品门户和主要交互层，不再只是“读与轻交互”外壳。FastAPI Jinja 页面继续承担兼容深页、服务端表单和导出入口，但不得据此把候选写操作声称为已通过生产验收。

当前完整架构见 [系统架构总览](architecture-system-overview-stable.md)，逐功能入口见 [用户 Playbook](../playbooks/user-playbook-medical-audit-v1-stable.md)。

## 2. 路由归属

| 类型 | 当前归属 | 约束 |
| --- | --- | --- |
| 产品门户、导航和 21 个独立页面 | Next.js | 主用户入口；`/workspace` 是独立工作台 |
| `/findings`、`/knowledge-query` | Next.js 兼容跳转 | 保留旧书签和查询参数映射合同 |
| 疑点、整改、报告、项目和知识工作台 | Next.js 调用 `/api/v1/*` | 权限与状态机以服务端字段为准 |
| `/pages/*`、旧表单和下载入口 | FastAPI Jinja | 兼容深页；只维护必要回归 |
| 静态资源、健康和部署元数据 | Next.js/FastAPI | `public-shell-readonly` 下可公开 |
| 业务 API 和旧深页中的业务数据 | FastAPI | 生产公开壳层模式统一阻断 |

## 3. 访问模式边界

### 3.1 本地测试

`header-transition-test` 允许本地角色模拟，用于成员、主任、技术员和管理员的权限回归。页面必须显示“仅本地测试”，不能把浏览器角色值当作可信认证。

后端同时缺少 `MEDICAL_AUDIT_API_ACCESS_MODE` 和 `MEDICAL_AUDIT_KB_DEV_MODE` 时默认进入 `public-shell-readonly`。本地 Header 角色模拟必须显式设置 `MEDICAL_AUDIT_KB_DEV_MODE=1`，或显式选择 `header-transition-test`。测试夹具负责声明该本地模式，不能依赖缺失环境变量产生的隐式回退。

### 3.2 生产公开壳层

`public-shell-readonly` 仅允许产品壳层、静态资源、`/health`、部署元数据和 release manifest。受保护请求在认证、业务逻辑和审计写入前返回 503 `trusted_identity_required`。生产导航验收在该模式下会拦截并计数 `/api/*` 请求；只要壳层主动尝试一条受保护 API，请求门禁就记录 P1 并使验收失败。

因此，历史文档中的“Jinja 写入型业务已过生产验收”不再是当前候选的有效结论。可信 SSO/OIDC 完成前，Next 和 Jinja 两侧的业务读取与写入都保持关闭。

## 4. 演进规则

1. 新功能统一使用 Next.js 页面和 `/api/v1/*` 规范接口。
2. 权限、可见性、状态迁移和可写性由 FastAPI 返回，前端不自行推导。
3. Jinja 兼容深页只修复缺陷和维持导出，不扩大新的产品入口。
4. 删除旧路由前必须先更新 21 个独立页面、2 个兼容跳转合同与逐功能 Playbook。
5. 任何生产写入验收都必须在可信身份上线后重新授权，不能复用历史 Header 模拟结果。

## 5. 当前证据

- 本地：17 个 Playwright 场景，以及 21 个独立页面、2 个兼容跳转和 4 条持久化业务工作流已形成合同；功能记录总数为 27。
- 生产：仅引用 2026-08-12 L3 壳层导航与健康证据。
- 候选外部观察：截至 2026-08-22 00:59（Asia/Shanghai），Draft PR #275 的观测 head 为 `d1973206d4f9b01ad0b287fb252fccf760fdab5c`，exact-head CI run `32499803192` 成功；Python `1018 passed`、Web `419 passed`，普通构建、公开壳层构建和文档门禁通过。PR 当时仍为 Draft，review、review request 和 review thread 均为 0；CodeRabbit 因 Draft 跳过 review。该观察不证明 Ready、merge 或部署，业务功能保持 `not_production_verified`。
