---
title: 个人材料生产级扫描、DLP 与对象存储治理方案
doc_type: analysis
module: documents
topic: personal-material-scan-dlp-object-storage
status: draft
created: 2026-06-16
updated: 2026-06-16
owner: self
source: human+ai
---

# 个人材料生产级扫描、DLP 与对象存储治理方案

## 1. 当前基线

已验证事实：

- 生产 `/api/v1/documents/uploads` 已支持个人材料留存、本人/他人/管理员读取隔离和 `document_upload_records` 持久化。
- 生产 `/api/v1/documents/uploads/{upload_id}/index-readiness/manual-approval` 已支持 `department-head` 人工审批通过或驳回。
- 生产当前病毒扫描 provider 和 DLP provider 仍为 `unconfigured`，因此人工审批通过后只清除人工审批 blocker，整体仍因 `virus-scan-required` 和 `dlp-review-required` 保持 `blocked`。
- 当前文件留存在 CVM 本地目录 `/opt/medical-audit/document-uploads`，由 Docker bind mount 暴露给 `medical_audit_app`。
- 当前没有对象存储、下载权限隔离、真实病毒扫描、真实 DLP、文件生命周期清理或实际入索引 worker。

边界判断：

- 现有 `local-test` adapter 只能用于测试，不允许配置为生产能力。
- 现有人工审批状态机不能替代病毒扫描、DLP 或对象存储治理。
- 个人材料实际入索引必须等待病毒扫描、DLP、人工审批三类门禁全部 passed。

## 2. 目标

本方案目标是把个人材料从“本地留存 + 门禁表达”升级为“生产级受控材料链路”：

1. 原始文件进入隔离区，不直接进入知识库索引。
2. 文件保存到私有对象存储，记录可追溯对象元数据。
3. 病毒扫描异步执行，结果写回 `index_readiness.checks`。
4. DLP 检测异步执行，识别敏感字段和泄露风险。
5. 人工审批保留为最终业务确认门禁。
6. 下载只能通过服务端授权和短期签名 URL 或受控流式代理。
7. 留存、下载、审批、扫描、DLP、入索引全部写审计日志。
8. 生命周期规则能归档、转冷、删除或冻结材料。

非目标：

- 不在本阶段直接实现真实登录会话。
- 不把 WAF 响应脱敏能力误写成上传文件 DLP。
- 不让个人材料绕过门禁进入现有知识库检索索引。
- 不在未确认院方数据合规边界前启用公网可访问对象 URL。

## 3. 推荐架构

### 3.1 状态机

个人材料状态应拆成四层，避免继续把所有状态塞进一个 `index_readiness.status`：

| 层级 | 建议字段 | 说明 |
| --- | --- | --- |
| 留存状态 | `retention_status` | `retained`、`archived`、`expired`、`deleted` |
| 存储状态 | `storage_status` | `local-quarantine`、`object-stored`、`object-missing` |
| 治理状态 | `index_readiness` | 继续承载 `virus-scan`、`dlp-review`、`manual-index-approval` |
| 入索引状态 | `index_status` | `not-indexed`、`queued`、`indexed`、`index-failed` |

推荐流转：

```text
uploaded
  -> local-quarantine
  -> object-stored
  -> virus-scan-pending
  -> virus-scan-passed | virus-scan-blocked
  -> dlp-review-pending
  -> dlp-review-passed | dlp-review-blocked
  -> manual-index-approval-required
  -> ready | rejected
  -> ingest-queued
  -> indexed | index-failed
```

当前 PR #103 已完成 `manual-index-approval-required -> ready/rejected` 的人工审批状态机，但前置 `virus-scan` 和 `dlp-review` 仍未接生产 provider。

### 3.2 对象存储层

首选方案：腾讯云 COS 私有 Bucket。

设计约束：

- Bucket 必须私有，禁止公开读。
- 对象 key 不包含原始文件名，使用稳定路径：
  `personal-materials/{environment}/{yyyy}/{mm}/{dd}/{upload_id}/{sha256}.{extension}`。
- DB 只保存 `bucket`、`region`、`object_key`、`etag`、`version_id`、`sha256`、`size_bytes`、`storage_class`、`encryption_mode`，不保存永久下载 URL。
- 上传后本地隔离文件可保留短周期，作为扫描失败排查和重试材料。
- COS 开启服务端加密，优先 SSE-KMS；若 KMS 未开通，至少 SSE-COS。
- Bucket 配置生命周期规则，按合规要求转低频、归档或删除。
- 下载走后端授权，短期预签名 URL TTL 建议 60-300 秒。

官方能力依据：

- Tencent Cloud COS 是对象存储服务，支持通过 API、SDK 和工具进行上传、下载和管理。
- COS 支持 SSE-COS 和 SSE-KMS 服务端加密。
- COS 生命周期规则可自动转换存储类型或删除对象。
- COS 支持 bucket policy、CAM/user policy 和 ACL 等访问控制。
- COS 支持预签名 URL，并建议使用临时密钥和最小权限。

### 3.3 病毒扫描层

推荐两级策略：

| 场景 | 推荐 provider | 说明 |
| --- | --- | --- |
| 腾讯云生产 | `tencent-ci-virus` | 基于 COS + 数据万象云查毒，异步提交任务并轮询结果 |
| 私有化/无云查毒 | `clamav-sidecar` | 在同 Docker network 内部署 ClamAV 或同类扫描服务 |
| 本地测试 | `local-test` | 仅用于测试 marker，不作为生产能力 |

`tencent-ci-virus` 处理流程：

1. 文件先进入 COS quarantine 前缀。
2. 服务端提交云查毒任务。
3. 记录外部 job id、provider、object key、提交时间。
4. worker 轮询查询检测结果。
5. `normal` 写回 `virus-scan` passed。
6. `block` 写回 `virus-scan` blocked，并保持材料不可下载、不可入索引。
7. 超时、失败或未知结果保持 blocked，不默认放行。

当前 `DocumentUploadVirusScanner.scan()` 是同步接口，不适合生产异步扫描。需要新增异步 job 表和 worker，不应把异步外部任务伪装成同步 passed。

### 3.4 DLP 层

推荐先做应用级 DLP，再预留企业 DLP/DSGC 集成：

第一阶段应用级 DLP：

- 针对 `txt`、`md`、`csv`、`xlsx` 做结构化文本抽取。
- 针对 `pdf` 先支持文本型 PDF；扫描件进入 `ocr-required` 或 `dlp-review-required`。
- 建立规则集：身份证号、手机号、银行卡号、医保号、住院号、患者姓名列、地址、诊断文本、费用明细等。
- DLP 结果不直接改写原文件，只生成 `findings`、`risk_level`、`recommended_action`。
- 高风险默认 blocked；中风险进入人工 DLP 复核；低风险可 passed。

第二阶段企业 DLP/DSGC：

- 若院方要求云侧资产分类分级，可接入腾讯云数据安全治理中心 DSGC 做云数据资产识别、分类分级和风险评估。
- 不能把 WAF 的响应泄露防护当作上传文件 DLP。WAF DLP 适合响应内容脱敏/阻断，不解决个人材料上传文件的入库前检测。

### 3.5 下载权限隔离

新增下载能力前必须满足：

- 只有上传人、`department-head`、`system-admin` 可申请下载。
- 被病毒扫描 blocked 的文件默认不可下载，只允许 `system-admin` 在隔离流程内取证。
- DLP blocked 的文件默认不可下载，只允许治理角色处理。
- 下载不返回永久 COS URL。
- 预签名 URL 由后端生成，TTL 60-300 秒，绑定 object key。
- 每次下载申请写入 `audit_log_events`，至少包含 `upload_id`、`object_key_hash`、`user_identifier`、`role`、`decision`、`reason`、`expires_at`。

## 4. 数据模型建议

保守方案：保持 `document_upload_records` 为主表，新增两张治理表，降低对既有 API 的破坏。

### 4.1 `document_storage_objects`

建议字段：

- `upload_key`
- `provider`: `local`、`tencent-cos`
- `bucket`
- `region`
- `object_key`
- `object_version`
- `etag`
- `sha256`
- `size_bytes`
- `storage_class`
- `encryption_mode`
- `storage_status`
- `retention_until`
- `created_at`
- `updated_at`

### 4.2 `document_upload_governance_jobs`

建议字段：

- `job_key`
- `upload_key`
- `job_type`: `virus-scan`、`dlp-review`、`object-sync`
- `provider`
- `external_job_id`
- `status`: `pending`、`running`、`passed`、`blocked`、`failed`、`timeout`
- `result_payload`
- `error_message`
- `attempt_count`
- `next_retry_at`
- `created_at`
- `updated_at`
- `finished_at`

### 4.3 `metadata.index_readiness`

继续保留当前结构，但每个 check 增加可选字段：

- `job_key`
- `external_job_id`
- `risk_level`
- `result_code`
- `finished_at`

旧客户端仍只读取 `check_type`、`provider`、`status`、`blocker`、`detail`。

## 5. API 规划

### 5.1 上传

`POST /api/v1/documents/uploads`

新增行为：

- 写本地 quarantine 文件。
- 生成 `document_upload_records`。
- 如配置 COS，上传到 COS quarantine 前缀。
- 创建 `virus-scan` 和 `dlp-review` jobs。
- 返回 `index_readiness.status=blocked`、`next_action=complete-upload-governance`。

### 5.2 状态读取

`GET /api/v1/documents/uploads/{upload_id}`

新增单条详情接口，避免列表承载过多治理细节。

### 5.3 下载

`POST /api/v1/documents/uploads/{upload_id}/download-url`

返回：

- `download_url`
- `expires_at`
- `method`
- `audit_event_id`

不直接暴露永久对象 URL。

### 5.4 扫描和 DLP 重试

治理角色接口：

- `POST /api/v1/documents/uploads/{upload_id}/virus-scan/retry`
- `POST /api/v1/documents/uploads/{upload_id}/dlp-review/retry`

限制：

- 只允许 `system-admin` 或指定治理角色。
- 必须写审计日志。
- 不允许普通审计员触发重试。

### 5.5 入索引

后续新增：

- `POST /api/v1/documents/uploads/{upload_id}/ingest`

门禁：

- `virus-scan=passed`
- `dlp-review=passed`
- `manual-index-approval=passed`
- `index_status=not-indexed`

本阶段只规划，不建议和扫描/DLP/对象存储同 PR 实现。

## 6. 配置规划

新增配置建议：

```text
MEDICAL_AUDIT_DOCUMENT_STORAGE_PROVIDER=local|tencent-cos
MEDICAL_AUDIT_DOCUMENT_STORAGE_COS_BUCKET=
MEDICAL_AUDIT_DOCUMENT_STORAGE_COS_REGION=
MEDICAL_AUDIT_DOCUMENT_STORAGE_COS_PREFIX=personal-materials/prod
MEDICAL_AUDIT_DOCUMENT_STORAGE_COS_SECRET_ID_ENV=
MEDICAL_AUDIT_DOCUMENT_STORAGE_COS_SECRET_KEY_ENV=
MEDICAL_AUDIT_DOCUMENT_STORAGE_COS_ENCRYPTION=sse-cos|sse-kms
MEDICAL_AUDIT_DOCUMENT_STORAGE_COS_KMS_KEY_ID=

MEDICAL_AUDIT_DOCUMENT_UPLOAD_VIRUS_SCANNER_PROVIDER=unconfigured|local-test|tencent-ci-virus|clamav-sidecar
MEDICAL_AUDIT_DOCUMENT_UPLOAD_DLP_REVIEWER_PROVIDER=unconfigured|local-test|ruleset-v1|external-dlp

MEDICAL_AUDIT_DOCUMENT_DOWNLOAD_SIGNED_URL_TTL_SECONDS=120
MEDICAL_AUDIT_DOCUMENT_LOCAL_QUARANTINE_RETENTION_DAYS=7
MEDICAL_AUDIT_DOCUMENT_OBJECT_RETENTION_DAYS=180
```

密钥只进入生产 env 或密钥管理，不进入 Git。

## 7. 实施顺序

### Phase A：无行为变更的架构准备

- 新增 storage/governance job 模型与 repository。
- 新增配置模型，但默认仍为 `local` + `unconfigured`。
- 新增 provider interface：`DocumentObjectStorage`、`DocumentVirusScanJobProvider`、`DocumentDlpJobProvider`。
- 新增单元测试和 schema 幂等测试。
- 不部署生产行为变化。

验收：

- `uv run pytest -q`
- `uv run mypy src/medical_audit_kb`
- `uv run ruff check .`
- 默认生产配置仍 blocked，不误报 ready。

### Phase B：本地 quarantine 与对象存储抽象

- 将本地文件留存迁到 `DocumentObjectStorage` adapter。
- 保持现有 `/opt/medical-audit/document-uploads` 行为兼容。
- 增加 object metadata 写入。
- 新增下载接口骨架，但默认不开放 COS。

验收：

- 既有 `/documents` 生产写入型 E2E 不回归。
- 本地文件 `sha256` 与 DB 一致。
- 下载接口无授权返回 403。

### Phase C：腾讯云 COS 受控存储

- 新增 `tencent-cos` storage adapter。
- 使用私有 bucket、短期签名 URL、服务端加密。
- 上传成功后写 `document_storage_objects`。
- 本地 quarantine 文件保留短周期。

验收：

- COS object key 不含原始文件名。
- DB 不保存永久 URL。
- 预签名 URL TTL 生效。
- 生产 smoke 验证 app/pg/nginx 不受影响。

### Phase D：病毒扫描异步 job

- 新增 `tencent-ci-virus` provider。
- 提交 COS 云查毒任务。
- worker 轮询查询结果。
- 写回 `index_readiness.checks`。
- blocked 文件禁止下载和入索引。

验收：

- 正常样本进入 `virus-scan=passed`。
- 测试病毒样本进入 `virus-scan=blocked`。
- provider 超时或异常保持 blocked。
- 审计日志记录 scan job 创建、结果和失败。

### Phase E：DLP ruleset-v1

- 新增文本抽取管道。
- 建立敏感字段规则集。
- DLP findings 写入治理 job result。
- 高风险 blocked，中风险人工复核，低风险 passed。

验收：

- 身份证号、手机号、银行卡号、患者姓名列等测试样本可识别。
- DLP blocked 时人工审批不能让整体 ready。
- DLP passed + virus passed + manual passed 后才进入 `ready`。

### Phase F：下载隔离和生命周期

- 下载接口返回短期签名 URL 或受控代理流。
- 角色、状态和风险共同决定下载权限。
- COS lifecycle 与本地 quarantine 清理策略落地。
- 下载、拒绝下载、清理任务全部写审计日志。

验收：

- 普通审计员只能下载本人且未 blocked 文件。
- 其他审计员下载返回 403。
- `department-head`、`system-admin` 权限按规则生效。
- blocked 文件默认不可下载。
- 生命周期 dry-run 报告先通过，再启用执行。

### Phase G：个人材料实际入索引

- 新增入索引队列。
- `ready` 材料由 worker 转入个人知识库索引。
- 索引记录绑定上传记录、治理状态和来源权限。
- 支持撤回、失效和重建。

验收：

- 未 ready 材料不能入索引。
- 入索引后仅授权用户/角色可检索。
- 撤回后不再被检索召回。

## 8. 关键风险

| 风险 | 判断 | 处理 |
| --- | --- | --- |
| 云存储合规 | 个人材料可能包含患者敏感信息 | 先由甲方确认 COS 地域、合同、数据处理协议和院内制度 |
| 异步扫描误报/漏报 | 不能把提交成功当扫描成功 | 必须等待结果，未知状态保持 blocked |
| DLP 范围过宽 | 容易把所有医疗文本都判高风险 | 规则分级，先用识别和阻断，不直接脱敏改写原件 |
| 下载 URL 泄露 | 预签名 URL 可被转发 | TTL 缩短、最小权限、审计日志、必要时走后端代理 |
| 本地与 COS 双份材料 | 生命周期不清会造成数据蔓延 | 本地 quarantine 默认短保留，COS 承担长期留存 |
| 生产 env 泄露 | COS secret 不能进 Git | 只允许生产 env 或密钥管理，部署脚本继续排除 `.env`、`*.key`、`*.pem` |

## 9. 甲方需确认事项

1. 是否允许个人材料进入腾讯云 COS；若不允许，改走私有化对象存储或 CVM 本地加密盘。
2. COS 地域、Bucket 命名、SSE-COS 还是 SSE-KMS。
3. 是否开通数据万象云查毒，以及费用预算。
4. DLP 首期规则范围：身份证、手机号、银行卡、医保号、住院号、患者姓名、诊断、地址、费用明细。
5. 下载权限：审计员本人、科室负责人、系统管理员的边界。
6. 留存周期：本地 quarantine、COS 热存储、归档、删除或法律保留。
7. 是否允许个人材料在通过治理门禁后进入检索索引。

## 10. 下一步建议

下一步不要直接实现 COS 和 DLP 全链路。推荐先执行 Phase A：

- 新增 schema/repository/provider interface。
- 默认配置保持 `unconfigured`。
- 不改变生产行为。
- 用测试证明：只有三类 check 全 passed 时，`index_readiness` 才能进入 `ready`。

Phase A 合并后，再用单独 PR 做 Phase B 本地 storage adapter 重构。COS、云查毒、DLP、下载隔离和实际入索引分别独立 PR，降低生产风险。

## 11. 参考资料

- Tencent Cloud COS 概览：<https://www.tencentcloud.com/document/product/436/6222>
- Tencent Cloud COS 服务端加密：<https://intl.cloud.tencent.com/document/product/436/18145>
- Tencent Cloud COS 生命周期：<https://www.tencentcloud.com/document/product/436/17028>
- Tencent Cloud COS 访问控制：<https://www.tencentcloud.com/document/product/436/30581>
- Tencent Cloud COS 预签名 URL：<https://www.tencentcloud.com/document/product/436/45243>
- Tencent Cloud COS 云查毒任务：<https://cloud.tencent.com/document/product/436/63961>
- Tencent Cloud COS 云查毒结果查询：<https://cloud.tencent.com/document/product/436/63962>
- Tencent Cloud DSGC 数据安全治理中心：<https://intl.cloud.tencent.com/product/dsgc>
