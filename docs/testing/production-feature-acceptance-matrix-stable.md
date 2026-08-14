---
title: medical_audit 本地与生产功能验收矩阵
doc_type: acceptance-matrix
module: testing
status: stable
created: 2026-08-13
updated: 2026-08-14
owner: self
source: human+ai+local-acceptance
---

# medical_audit 本地与生产功能验收矩阵

矩阵区分本地活体验收、PR exact-head CI、生产壳层历史只读验收和受保护业务能力。Draft PR #275 的远端 head 为 `cc711fdb4dc2b36d2b5de705939a7726917960f1`；本地候选分支在其上有 1 个尚未推送的原子提交。候选尚未部署，生产列不得继承本地或 CI 结果。

## 页面与功能

| ID | 页面或别名 | 本地证据 | 生产证据 | 说明 |
|---|---|---|---|---|
| R01 | `/` | Playwright pass | `production_evidence=L3 shell pass` | 首页和只读入口 |
| R02 | `/login` | Playwright pass | `production_evidence=blocked_by_access_mode` | 登录占位，不建立可信会话 |
| R03 | `/medical-audit` | 深链、页面和只读壳层负向控件 pass | `production_evidence=blocked_by_access_mode` | 疑点业务不可读，无写控件 |
| R04 | `/fund-compliance` | 页面和 CTA pass | `production_evidence=L3 shell pass` | 产品导览 |
| R05 | `/fund-compliance/review` | 表单和 CTA pass | `production_evidence=blocked_by_access_mode` | 数据提交未验证 |
| R06 | `/chat` | Fake 查询和只读壳层负向控件 pass | `production_evidence=blocked_by_access_mode` | 无输入、上传、选择或发送控件 |
| R07 | `/agents` | 目录和详情 pass | `production_evidence=not_production_verified` | 写入能力未验证 |
| R08 | `/agent-market` | 目录 pass | `production_evidence=L3 shell pass` | 安装未验证 |
| R09 | `/analytics` | 页面和只读壳层负向控件 pass | `production_evidence=blocked_by_access_mode` | 无上传、重试或刷新控件 |
| R10 | `/projects` | 项目和可见性 pass | `production_evidence=blocked_by_access_mode` | 生产业务数据关闭 |
| R11 | `/audit-cockpit` | 页面和项目入口 pass | `production_evidence=L3 shell pass` | 壳层通过，指标不可读 |
| R12 | `/documents` | 检索、预览、下载控件 pass | `production_evidence=blocked_by_access_mode` | 真实文档不可读 |
| R13 | `/ocr` | 页面、能力合同和只读壳层负向控件 pass | `production_evidence=blocked_by_access_mode` | 无文件选择或识别控件 |
| R14 | `/knowledge-base` | 聚合和页面 pass | `production_evidence=L3 shell pass` | 壳层通过，catalog 受保护 |
| R15 | `/graph` | 页面和关系视图 pass | `production_evidence=L3 shell pass` | 动态项目数据未验证 |
| R16 | `/rules` | Seed 合同 pass | `production_evidence=sample_only` | 只读 Sample |
| R17 | `/reports` | 权限和签发合同 pass | `production_evidence=not_production_verified` | 无生产签发 |
| R18 | `/remediation` | UUID、状态机、附件 pass | `production_evidence=not_production_verified` | 无生产整改写入 |
| R19 | `/archive` | Seed 合同 pass | `production_evidence=sample_only` | 只读 Sample |
| R20 | `/guided-check` | 页面和 CTA pass | `production_evidence=L3 shell pass` | Provider 未运行 |
| A01 | `/workspace` | 独立工作台 pass | `production_evidence=L3 shell pass` | 不再跳转 `/chat` |
| A02 | `/findings` | 跳转 `/medical-audit` pass | `production_evidence=L3 shell pass` | 兼容别名 |
| A03 | `/knowledge-query` | 参数映射 pass | `production_evidence=L3 shell pass` | 未知参数丢弃 |

## 关键业务门禁

| 功能 | 本地合同 | 生产状态 |
|---|---|---|
| public shell 保护业务 GET、POST、OPTIONS | `503`、`no-store`、无审计增量 | `production_evidence=not_production_verified` |
| public shell 不请求业务 API、不显示写控件 | React 回归；导航验收发现任一受保护 API 尝试即记 P1 并失败 | `production_evidence=not_production_verified` |
| 疑点 `?finding=` 定位与不可见统一提示 | pass | `production_evidence=blocked_by_access_mode` |
| 整改真实 UUID 附件 | pass | `production_evidence=not_production_verified` |
| 整改空库真实空状态 | pass | `production_evidence=not_production_verified` |
| 整改 Sample `writable=false` | pass | `production_evidence=sample_only` |
| 整改项目可见性和 `404` | pass | `production_evidence=not_production_verified` |
| 整改可见性先于排序与 `LIMIT` | 多项目窗口回归 pass | `production_evidence=not_production_verified` |
| 成员和主任完整状态机 | pass | `production_evidence=not_production_verified` |
| 整改并发过期状态更新 | 一个提交成功、一个 `409` | `production_evidence=not_production_verified` |
| 报告仅主任签发 | pass | `production_evidence=not_production_verified` |
| 重复签发、关闭态和不可见任务 | pass | `production_evidence=not_production_verified` |
| 报告并发重复签发 | 一个 `200`、一个 `409`、一条操作日志 | `production_evidence=not_production_verified` |
| 知识库等长 chunk 和多 index 聚合 | SQLite 和真实 PostgreSQL pass | `production_evidence=blocked_by_access_mode` |
| OpenAPI 文档逐操作覆盖 | 112 个路径、123 个方法/路径操作由 `docs:lint` 对账 | `production_evidence=not_run` |
| 确定性 Fake OCR、页映射和审计记录 | pass | `production_evidence=not_production_verified` |
| 真实 OCR/LLM Provider | not_run | `production_evidence=not_run` |
| 真实 HIS 与医院现场 UAT | not_run | `production_evidence=not_run` |

## 本地收据

机器收据：`tmp/outputs/local-fullstack-feature-acceptance-latest.json`。

收据事实：

- `status=pass`。
- `data_store=temporary-sqlite`。
- `provider_call=false`。
- `external_provider_smoke=not_run`。
- `independent_route_count=20`。
- `alias_count=3`。
- `workflow_count=4`。
- `feature_count=27`。
- 四条活体业务工作流分别覆盖整改状态与附件、报告签发权限、项目/成员/文件持久化，以及确定性 Fake OCR 页映射。
- `candidate_identity.changed_files` 和 `candidate_identity.manifest_sha256` 绑定收据运行时的预提交候选文件；最终值直接读取机器收据，避免文档修改使静态抄录失效。

收据中的 `git_sha` 是预提交运行时基线 SHA；当时的候选差异由 `candidate_identity.changed_files` 和 manifest SHA-256 另行绑定。当前本地分支已经形成 1 个原子提交；最终提交身份和文件哈希由 Git 对象与仓库外提交收据绑定。远端 exact-head CI 仍只覆盖 `cc711fdb4dc2b36d2b5de705939a7726917960f1`，推送后的 CI 需要重新取得新提交证据。

## 生产证据说明

2026 年 8 月 12 日 L3 证据显示生产 SHA 为 `25e1654e0c44ca5cbb2bb42e82debdb40fa6f224`，核心容器、前门、搜索和页面壳层健康。该证据早于本候选访问门禁，不能证明候选 `public-shell-readonly` 已部署。

发布后只允许执行：

1. L3 容器、前门、release manifest 和部署 SHA 检查。
2. 20 个独立页面和 3 个别名的桌面、移动只读导航。
3. 一个受保护 GET 的 `503` 负向检查。
4. 业务数据和审计日志无增量检查。

不执行生产 POST、上传、签发、状态变更、Provider 调用或真实业务数据读取。
