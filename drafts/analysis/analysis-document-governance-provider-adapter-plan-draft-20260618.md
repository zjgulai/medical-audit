---
title: 文档上传治理真实 Provider Adapter 实施草案
doc_type: analysis
module: medical-audit
topic: document-governance-provider-adapter
status: draft
created: 2026-06-18
updated: 2026-06-19
owner: self
source: human+ai
scope: docs-only
---

# 文档上传治理真实 Provider Adapter 实施草案

## 当前事实

- 已具备个人材料上传、COS 对象存储、下载授权、治理结果回写、人工审批和 ready 状态生产 E2E。
- 已具备 provider pending 语义：`tencent-ci-virus` 和 `external-dlp` 表达等待外部结果，不自动消除 blocker。
- 已具备 provider preflight：默认只读检查，不调用病毒扫描、DLP、对象存储或生产 API。
- 已具备 governance job contract：`local-recording` 可在本地或预生产记录 `virus-scan`、`dlp-review` pending job，且明确 `external_provider_call_performed=false`。
- 已具备生产 `clamav-sidecar` clean 扫描链路：干净文本上传可由真实 ClamAV sidecar 返回 `virus-scan=passed/result_code=clean`。
- 已具备生产 `ruleset-v1` 应用级本地 DLP 链路：clean 样本返回 `dlp-review=passed/result_code=no-sensitive-marker`，sensitive 样本返回 `dlp-review=blocked/result_code=sensitive-marker-detected`。

## 不能越界的结论

- 现阶段只能宣称 `clamav-sidecar` 本地 sidecar clean 扫描生产复验通过，不能宣称腾讯云 CI 或其它外部病毒扫描 provider 已接入。
- 现阶段只能宣称 `ruleset-v1` 应用级本地 DLP 规则生产复验通过，不能宣称企业级 DLP、脱敏改写或完整敏感数据分级完成。
- 现阶段仍不能把个人材料实际写入检索索引。
- 现阶段不能在没有明确 provider 选择、密钥治理、超时重试和生产验收前打开真实 provider call。

## 推荐实施顺序

### P1：`ruleset-v1` 应用级 DLP adapter（已完成生产复验）

目标：先实现可审计、可解释、无外部依赖的 DLP 检测能力。

原因：

- 不依赖外部厂商密钥或网络。
- 可以用固定样本覆盖身份证、手机号、医保号、住院号、患者姓名、诊断、地址、费用明细等模式。
- 对生产风险最低；失败时保持 `dlp-review-required` blocker。

验收：

- 正常样本：`dlp-review=passed`，`risk_level=low`。
- 命中高风险样本：`dlp-review=blocked`，保留 `findings`、`risk_level`、`result_code`。
- 所有结果只更新治理状态和 job result，不改写原始文件。
- 生产证据：`tmp/outputs/production-documents-ruleset-dlp-write-e2e-after-activation-20260619.json` 为 `status=pass`；clean 样本 `document-upload-c3bd6dcf9917` 通过，sensitive 样本 `document-upload-2d7265f12e5d` 被 DLP 阻断。

### P2：`clamav-sidecar` 本地病毒扫描 adapter（已完成生产复验）

目标：先用可控 sidecar 建立真实扫描的 fail-closed 链路。

原因：

- 相比云查毒，sidecar 更适合本地和预生产复现。
- 可以在 Docker 环境中用固定测试样本验证 timeout、unavailable、malware detected、clean 四类路径。
- 不需要在首个真实扫描 PR 中处理 COS 云服务 job 生命周期差异。

验收：

- sidecar 不可用：job `failed` 或 `timeout`，`virus-scan-required` blocker 保持。
- clean：`virus-scan=passed`。
- malware/test marker：`virus-scan=blocked`。
- 所有调用必须有 timeout、重试上限和审计日志。
- 生产证据：`tmp/outputs/production-documents-clamav-sidecar-write-e2e-after-pr147-personal-material-retrieval-isolation-20260619.json` 为 `status=pass`，干净文本上传由真实 ClamAV sidecar 返回 clean。

### P3：`tencent-ci-virus` 云查毒 adapter

目标：在 COS 已稳定的基础上接入腾讯云对象级病毒扫描。

前置条件：

- 使用官方文档确认当前 API、权限、回调或轮询方式。
- 使用最小权限 CAM policy。
- 生产密钥必须只通过服务器环境变量或 secret 文件加载，不进入前端、日志、job result 或 DB 明文字段。
- 先在 staging bucket 验证，再进入生产 bucket。

验收：

- 提交 job 后记录 `external_job_id`。
- 轮询或回调结果写回 `document_upload_governance_jobs`。
- clean 才能写回 `virus-scan=passed`。
- suspicious、infected、timeout、provider error 均保持 blocked。

### P4：`external-dlp` 企业 DLP HTTP adapter

目标：对接院方或第三方 DLP 服务。

前置条件：

- 明确请求字段、响应 schema、错误码、超时和重试策略。
- 明确是否允许上传文件正文；如不允许，只传 COS signed URL 或对象引用。
- 明确 DLP 结果是否包含原文片段；默认不写入原文片段，只保存 finding 类型和定位摘要。

验收：

- 低风险：`dlp-review=passed`。
- 中高风险：`dlp-review=blocked`，需人工复核。
- provider 失败：保持 blocked，不允许降级为 passed。

## 通用 adapter contract

所有真实 provider adapter 必须满足：

- fail-closed：调用失败、超时、响应无法解析、签名失败、权限不足均不能清除 blocker。
- bounded timeout：每次提交和查询有明确超时。
- no secret persistence：secret value 不写入 DB、日志、API 响应或前端。
- result normalization：不同 provider 结果统一归一到 `passed` 或 `blocked`，并保留 `result_code`、`risk_level`、`external_job_id`、`finished_at`。
- auditability：提交、失败、重试、写回都写审计日志。
- idempotency：同一 upload/check_type/provider 重试不能制造无限重复 job。

## 推荐下一个 PR

本草案内 P1/P2 已完成到生产复验层。下一步分两条线，不能混在同一个 PR：

1. Provider 线：继续 P3/P4 前，先明确腾讯云 CI 或院方企业 DLP 的接口、权限、回调/轮询、secret 管理和错误语义；没有这些材料时，不建议直接打开真实外部 provider call。
2. 产品闭环线：在 `clamav-sidecar` 和 `ruleset-v1` 均可消除对应 blocker 的基础上，单独推进个人材料实际入索引和 active personal-material 检索命中验收。

下一步仍不做事项：

- 不把 `ruleset-v1` 称为企业级 DLP。
- 不把本地 sidecar 扫描称为腾讯云 CI。
- 不在无单独审批和回滚计划时触发个人材料批量入索引。
- 不把生产写入型 E2E 的受控样本说成真实医院业务数据验收。
