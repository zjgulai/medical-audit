---
title: 前端边界：Next 门户与 FastAPI 兼容深页
doc_type: architecture
module: frontend
topic: jinja-next-boundary
status: stable
created: 2026-06-23
updated: 2026-08-14
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
| 产品门户、导航和 20 个独立页面 | Next.js | 主用户入口 |
| `/workspace`、`/findings`、`/knowledge-query` | Next.js 兼容别名 | 保留兼容合同，不再作为孤儿路由 |
| 疑点、整改、报告、项目和知识工作台 | Next.js 调用 `/api/v1/*` | 权限与状态机以服务端字段为准 |
| `/pages/*`、旧表单和下载入口 | FastAPI Jinja | 兼容深页；只维护必要回归 |
| 静态资源、健康和部署元数据 | Next.js/FastAPI | `public-shell-readonly` 下可公开 |
| 业务 API 和旧深页中的业务数据 | FastAPI | 生产公开壳层模式统一阻断 |

## 3. 访问模式边界

### 3.1 本地测试

`header-transition-test` 允许本地角色模拟，用于成员、主任、技术员和管理员的权限回归。页面必须显示“仅本地测试”，不能把浏览器角色值当作可信认证。

当前显式接受一项受控兼容风险：后端同时缺少 `MEDICAL_AUDIT_API_ACCESS_MODE` 和 `MEDICAL_AUDIT_KB_DEV_MODE` 时，仍回退到 `header-transition-test`，以兼容现有测试和本地直接启动方式。生产 Compose 和生产 env 示例均固定 `MEDICAL_AUDIT_KB_DEV_MODE=0`、`MEDICAL_AUDIT_API_ACCESS_MODE=public-shell-readonly`，部署脚本也强制公开壳层构建，因此已配置的生产路径保持 fail-closed。任何新增启动器、容器编排或非 Compose 部署必须先显式设置访问模式；若无法证明设置存在，不得归类为生产候选。该风险在可信身份或统一 runtime profile 建成时重新评估。

### 3.2 生产公开壳层

`public-shell-readonly` 仅允许产品壳层、静态资源、`/health`、部署元数据和 release manifest。受保护请求在认证、业务逻辑和审计写入前返回 503 `trusted_identity_required`。生产导航验收在该模式下会拦截并计数 `/api/*` 请求；只要壳层主动尝试一条受保护 API，请求门禁就记录 P1 并使验收失败。

因此，历史文档中的“Jinja 写入型业务已过生产验收”不再是当前候选的有效结论。可信 SSO/OIDC 完成前，Next 和 Jinja 两侧的业务读取与写入都保持关闭。

## 4. 演进规则

1. 新功能统一使用 Next.js 页面和 `/api/v1/*` 规范接口。
2. 权限、可见性、状态迁移和可写性由 FastAPI 返回，前端不自行推导。
3. Jinja 兼容深页只修复缺陷和维持导出，不扩大新的产品入口。
4. 删除旧路由前必须先更新 20 页面、3 别名合同与逐功能 Playbook。
5. 任何生产写入验收都必须在可信身份上线后重新授权，不能复用历史 Header 模拟结果。

## 5. 当前证据

- 本地：17 个 Playwright 场景，以及 20 个独立页面、3 个兼容别名和 4 条持久化业务工作流已形成机器收据；功能记录总数为 27。
- 生产：仅引用 2026-08-12 L3 壳层导航与健康证据。
- 候选：分支此前已推送为 Draft PR #275；当前远端 head 为 `cc711fdb4dc2b36d2b5de705939a7726917960f1`，本地在其上有 1 个尚未推送的原子提交。候选尚未合并或部署，业务功能保持 `not_production_verified`。
