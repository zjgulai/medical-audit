---
title: 知识库检索评测种子集草稿
doc_type: analysis
module: knowledge-query-engine
topic: retrieval-evaluation-seed
status: draft
created: 2026-05-31
updated: 2026-05-31
owner: self
source: human+ai
---

# 知识库检索评测种子集草稿

## 1. 评测目标

首批评测只验证知识库查询引擎的三件事：

- 检索结果是否命中预期资料、文件和条款/规则项。
- 回答引用是否能覆盖预期证据。
- 引用定位是否能打开原文预览。

不在本阶段评估生成语言质量、审计结论正确性和复杂多轮推理。

## 2. 数据格式

```json
{
  "cases": [
    {
      "case_id": "prd-prescription-over-quantity-001",
      "question": "肿瘤门特慢病门诊处方出现超量开药时，应引用哪些规则来源？",
      "expected_evidence": [
        {
          "source_collection": "supervision-rules-knowledge",
          "source_path": "智能监管两库规则和知识点/处方规则.xlsx",
          "article_or_rule": "超量开药",
          "locator": {
            "type": "xlsx-row",
            "sheet_name": "规则",
            "row_number": 2
          },
          "required_terms": ["超量", "处方"]
        }
      ],
      "acceptance_criteria": {
        "required_terms": ["超量开药", "规则来源"],
        "min_citations": 1,
        "require_preview": true
      },
      "tags": ["prd", "prescription-audit", "over-quantity"],
      "filters": {
        "source_collections": ["supervision-rules-knowledge"],
        "business_topics": ["prescription-audit"]
      },
      "auditor_import": {
        "raw_question": null,
        "source_channel": null,
        "auditor_question_id": null,
        "auditor_role": null,
        "asked_at": null,
        "reviewer_notes": null
      }
    }
  ]
}
```

## 3. PRD 场景种子问题

- `prd-prescription-over-quantity-001`：肿瘤门特慢病门诊处方出现超量开药时，应引用哪些规则来源？
- `prd-prescription-over-course-001`：肿瘤门特慢病长处方如何判断是否超疗程？
- `prd-rule-version-trace-001`：审计结果中的命中规则需要怎样追溯到规则版本？
- `prd-evidence-package-001`：每条疑似问题的最小证据包应包含哪些内容？
- `prd-report-export-001`：正式审计报告和底稿导出的引用依据如何保留？

## 4. 自动候选问题生成规则

- 资料文本包含 `第X条` 时，生成问题：`{资料标题}中{条款号}的审核要求是什么？`
- 资料文本包含 `规则名称: xxx` 时，生成问题：`{规则名称}规则的判定依据是什么？`
- 无条款和规则名称时，生成问题：`{资料标题}的核心审核依据是什么？`

自动生成的问题只进入候选池，必须由审计专家或产品负责人确认后才能进入正式评测集。

## 5. 指标口径

- `recall@k`：每个问题的 Top K 检索结果中是否至少命中一个预期证据。
- `citation_hit_rate`：回答引用中是否至少包含一个预期证据。
- `preview_location_success_rate`：已命中引用能否成功解析到原文预览。

当前评测是 case-level 指标，不直接替代最终准确率口径。
