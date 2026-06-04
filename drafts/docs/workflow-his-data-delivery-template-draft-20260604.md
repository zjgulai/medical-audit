---
title: HIS 数据交付与验收模板草稿
doc_type: workflow
module: his-data-ingestion
topic: his-data-delivery-template
status: draft
created: 2026-06-04
updated: 2026-06-04
owner: self
source: human+ai
---

# HIS 数据交付与验收模板草稿

## 1. 目的

本模板用于向医院信息科和审计科收集 V1.0 首个专项审计场景所需的 HIS 输入，避免只拿到截图、口头字段说明或不可复跑样本。

当前候选场景为收费合规 / 重复收费与目录限制核验。模板字段在院方确认前均为交付要求，不是已确认事实。

## 2. 交付包结构

建议每次交付使用一个独立压缩包：

```text
his-delivery-[hospital-code]-[scenario]-[YYYYMMDD]/
|-- README.md
|-- ddl/
|   |-- his-ddl.sql
|   `-- table-list.csv
|-- dictionary/
|   |-- table-dictionary.csv
|   |-- field-dictionary.csv
|   `-- enum-dictionary.csv
|-- samples/
|   |-- visit.csv
|   |-- diagnosis.csv
|   |-- order_or_prescription.csv
|   |-- charge_detail.csv
|   |-- item_catalog.csv
|   `-- department_staff.csv
|-- validation/
|   |-- confirmed-positive-cases.csv
|   |-- confirmed-negative-cases.csv
|   `-- validation-guideline.md
`-- report-template/
    |-- audit-report-template.docx
    `-- signoff-flow.md
```

如果院方不能按该结构交付，必须至少保留同等信息量，并说明差异。

## 3. README 必填项

| 字段 | 示例 | 必填 | 说明 |
| --- | --- | --- | --- |
| hospital_code | `HOSP001` | 是 | 医院匿名编码 |
| scenario | `charging-compliance` | 是 | 审计场景 |
| export_time_range | `2025-01-01~2025-12-31` | 是 | 数据覆盖时间 |
| exported_at | `2026-06-04T10:00:00+08:00` | 是 | 数据导出时间 |
| source_type | `offline-export` | 是 | 中间库、离线导出或只读副本 |
| desensitization_method | `stable-hash-in-batch` | 是 | 脱敏方法 |
| row_counts | `{charge_detail: 100000}` | 是 | 表级行数 |
| owner_department | `信息科` | 是 | 交付责任部门 |
| audit_owner | `审计科` | 是 | 业务验收责任人 |

## 4. DDL 交付要求

`ddl/his-ddl.sql` 必须包含：

- 与收费合规场景相关的源表 DDL。
- 主键、唯一键、索引和字段类型。
- 字段注释或可关联字段字典。
- 表之间关联键说明。

不接受：

- 只提供截图。
- 只提供导出 CSV 而无表结构。
- 无法判断主键和时间字段含义的 DDL。

## 5. 表清单模板

`ddl/table-list.csv` 字段：

```csv
table_name,table_label,business_domain,primary_key,stable_unique_key,time_fields,row_count,owner,required_for_v1
visit,就诊记录,visit,visit_id,,visit_time,10000,信息科,true
diagnosis,诊断记录,diagnosis,diagnosis_id,,diagnosis_time,18000,信息科,true
charge_detail,收费明细,charge,charge_id,,charge_time,120000,信息科,true
```

## 6. 字段字典模板

`dictionary/field-dictionary.csv` 字段：

```csv
table_name,field_name,field_label,data_type,nullable,unit,enum_ref,meaning,desensitization_rule,example_value,quality_requirement
charge_detail,charge_id,收费明细ID,varchar,false,,,稳定唯一键,none,CD0001,not_null_unique
charge_detail,visit_id,就诊ID,varchar,false,,,关联就诊,stable_hash,V0001,not_null
charge_detail,item_code,院内项目编码,varchar,false,,,关联项目目录,none,ITEM001,not_null
charge_detail,charge_time,收费时间,timestamp,false,,,收费发生时间,none,2025-01-01 09:00:00,valid_datetime
charge_detail,amount,收费金额,decimal,false,CNY,,单价乘数量后金额,none,120.00,non_negative
```

## 7. 枚举字典模板

`dictionary/enum-dictionary.csv` 字段：

```csv
enum_ref,enum_value,enum_label,description
visit_type,OP,门诊,门诊就诊
visit_type,IP,住院,住院就诊
settlement_status,SETTLED,已结算,已进入结算
settlement_status,CANCELLED,已冲销,不能直接作为违规疑点
```

## 8. 脱敏样本要求

最低要求：

- 患者姓名、证件号、手机号、住址不得出现。
- 患者匿名 ID 在同一批次内稳定。
- 如需跨批次追踪，院方必须说明是否稳定映射。
- 医生姓名可改为医生匿名 ID；如果保留真实姓名，必须由院方确认权限和用途。
- 金额、数量、时间、项目编码原则上保留真实业务分布，不能全部随机打乱。

样本文件必须使用 UTF-8 编码，首行字段名，时间字段使用 ISO-like 格式或明确格式说明。

## 9. 验证集模板

`validation/confirmed-positive-cases.csv` 字段：

```csv
case_id,source_table,source_primary_key,expected_rule_key,expected_finding_type,reviewer,reviewed_at,review_note
P001,charge_detail,CD0001,CHARGE-RULE-001,duplicate-charge,审计员A,2026-06-04,同就诊同项目重复收费
```

`validation/confirmed-negative-cases.csv` 字段：

```csv
case_id,source_table,source_primary_key,expected_rule_key,negative_reason,reviewer,reviewed_at,review_note
N001,charge_detail,CD0100,CHARGE-RULE-001,quantity-explained-by-order,审计员A,2026-06-04,多条收费由不同执行记录解释
```

没有验证集时，系统只能输出工程 smoke 和规则命中样例，不能承诺准确率。

## 10. 数据质量验收

交付包进入开发前必须通过最低检查：

- 所有必需表存在。
- 每个必需表有主键或稳定唯一键。
- 关键字段空值率符合字段字典要求。
- 金额和数量字段不存在无法解释的负值。
- 时间字段可解析。
- 收费明细能关联就诊记录。
- 收费项目能关联项目目录。
- 重复收费正例和正常反例可定位到源记录。

失败处理：

- 不生成正式任务快照。
- 不运行规则。
- 输出问题清单给信息科和审计科确认。

## 11. 验收签收项

院方交付后需确认：

- 信息科确认 DDL 与样本来自指定系统和时间范围。
- 审计科确认验证集样本和判断口径。
- 双方确认脱敏规则满足开发和联调要求。
- 双方确认准确率统计口径。
- 双方确认报告模板和签字流程。

## 12. 后续开发入口

交付包通过后，进入以下工程任务：

1. 使用 `his-ddl-parse` 解析 HIS DDL，生成 DDL 解析 Markdown/JSON 报告。
2. 使用 `his-sample-quality` 校验脱敏样本字段、行数、必填空值和重复主键。
3. 建立 `his_source_batches`、`his_table_schemas`、`his_field_mappings`。
4. 运行收费合规字段映射校验，确认必需字段、脱敏规则、nullable 和重复映射门禁通过。
5. 使用 `his-staging-import` dry-run 校验样本质量报告、source batch、table schema 和重复 staging 行。
6. 复核 dry-run 报告后显式 `--execute` 写入 `his_staging_rows`。
7. 使用 `his-snapshot-plan` 生成快照计划、row_counts、checksum 和 `AuditDataSnapshotCreate` payload。
8. 使用 `his-snapshot-apply` dry-run 校验快照计划、项目存在性和 `snapshot_key` 唯一性。
9. 复核 dry-run 报告后显式 `--execute` 写入 `audit_data_snapshots`。
10. 建立 `audit_tasks`、`audit_runs`、`audit_rules` 和 `rule_versions`。
11. 使用 `charge-rule-001-staging-run` dry-run 校验 staging 转换、任务/快照/运行批次/规则版本一致性和预期疑点。
12. 复核 dry-run 报告后显式 `--execute` 写入 `audit_findings` 和 `finding_evidence_items`。
13. 如果生产 staging 验收失败，先使用 `his-snapshot-rollback-audit` dry-run 计算从当前快照回退到上一可用快照的影响面。
14. 复核回滚影响面后显式 `--execute` 写入 `audit_snapshot_rollbacks` 审计事件；该命令不删除历史快照、任务、run 或疑点。

示例命令：

```bash
medical-audit-kb his-ddl-parse \
  --ddl-file tmp/outputs/his-delivery/his-ddl.sql \
  --output tmp/outputs/his-delivery/his-ddl-parse-report.md \
  --json-output tmp/outputs/his-delivery/his-ddl-parse-report.json

medical-audit-kb his-sample-quality \
  --sample-root tmp/outputs/his-delivery/samples \
  --ddl-report-json tmp/outputs/his-delivery/his-ddl-parse-report.json \
  --output tmp/outputs/his-delivery/his-sample-quality-report.md \
  --json-output tmp/outputs/his-delivery/his-sample-quality-report.json

medical-audit-kb his-staging-import \
  --quality-report-json tmp/outputs/his-delivery/his-sample-quality-report.json \
  --source-batch-key his-batch-20260604-001 \
  --database-url-env MEDICAL_AUDIT_DATABASE_URL \
  --output tmp/outputs/his-delivery/his-staging-import-dry-run.md \
  --json-output tmp/outputs/his-delivery/his-staging-import-dry-run.json

medical-audit-kb his-staging-import \
  --quality-report-json tmp/outputs/his-delivery/his-sample-quality-report.json \
  --source-batch-key his-batch-20260604-001 \
  --database-url-env MEDICAL_AUDIT_DATABASE_URL \
  --output tmp/outputs/his-delivery/his-staging-import-execute.md \
  --json-output tmp/outputs/his-delivery/his-staging-import-execute.json \
  --execute

medical-audit-kb his-snapshot-plan \
  --quality-report-json tmp/outputs/his-delivery/his-sample-quality-report.json \
  --project-id 11111111-1111-4111-8111-111111111111 \
  --snapshot-key snapshot-his-20260604-001 \
  --source-batch-key his-batch-20260604-001 \
  --time-range-json '{"from":"2025-01-01","to":"2025-01-31"}' \
  --output tmp/outputs/his-delivery/his-snapshot-plan.md \
  --json-output tmp/outputs/his-delivery/his-snapshot-plan.json

medical-audit-kb his-snapshot-apply \
  --snapshot-plan-json tmp/outputs/his-delivery/his-snapshot-plan.json \
  --database-url-env MEDICAL_AUDIT_DATABASE_URL \
  --output tmp/outputs/his-delivery/his-snapshot-apply-dry-run.md \
  --json-output tmp/outputs/his-delivery/his-snapshot-apply-dry-run.json

medical-audit-kb his-snapshot-apply \
  --snapshot-plan-json tmp/outputs/his-delivery/his-snapshot-plan.json \
  --database-url-env MEDICAL_AUDIT_DATABASE_URL \
  --output tmp/outputs/his-delivery/his-snapshot-apply-execute.md \
  --json-output tmp/outputs/his-delivery/his-snapshot-apply-execute.json \
  --execute

medical-audit-kb charge-rule-001-staging-run \
  --source-batch-key his-batch-20260604-001 \
  --audit-task-key audit-task-charge-20260604-001 \
  --audit-run-key audit-run-charge-20260604-001 \
  --database-url-env MEDICAL_AUDIT_DATABASE_URL \
  --output tmp/outputs/his-delivery/charge-rule-001-staging-run-dry-run.md \
  --json-output tmp/outputs/his-delivery/charge-rule-001-staging-run-dry-run.json

medical-audit-kb charge-rule-001-staging-run \
  --source-batch-key his-batch-20260604-001 \
  --audit-task-key audit-task-charge-20260604-001 \
  --audit-run-key audit-run-charge-20260604-001 \
  --database-url-env MEDICAL_AUDIT_DATABASE_URL \
  --output tmp/outputs/his-delivery/charge-rule-001-staging-run-execute.md \
  --json-output tmp/outputs/his-delivery/charge-rule-001-staging-run-execute.json \
  --execute

medical-audit-kb his-snapshot-rollback-audit \
  --rollback-key rollback-his-20260604-001 \
  --project-key audit-project-charge-20260604 \
  --from-snapshot-key snapshot-his-20260604-001 \
  --to-snapshot-key snapshot-his-previous-stable \
  --reason "生产 staging 验收未通过，回退到上一可用快照" \
  --requested-by audit-admin \
  --database-url-env MEDICAL_AUDIT_DATABASE_URL \
  --output tmp/outputs/his-delivery/his-snapshot-rollback-audit-dry-run.md \
  --json-output tmp/outputs/his-delivery/his-snapshot-rollback-audit-dry-run.json

medical-audit-kb his-snapshot-rollback-audit \
  --rollback-key rollback-his-20260604-001 \
  --project-key audit-project-charge-20260604 \
  --from-snapshot-key snapshot-his-20260604-001 \
  --to-snapshot-key snapshot-his-previous-stable \
  --reason "生产 staging 验收未通过，回退到上一可用快照" \
  --requested-by audit-admin \
  --database-url-env MEDICAL_AUDIT_DATABASE_URL \
  --output tmp/outputs/his-delivery/his-snapshot-rollback-audit-execute.md \
  --json-output tmp/outputs/his-delivery/his-snapshot-rollback-audit-execute.json \
  --execute
```
