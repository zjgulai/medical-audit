from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Header

from medical_audit_kb.api.app import ApiState, get_api_state, record_operation
from medical_audit_kb.api.auth import HospitalRole, resolve_authenticated_user
from medical_audit_kb.api.routes_knowledge_base import build_knowledge_base_catalog_response

router = APIRouter()

DOMAIN_LABELS: dict[str, str] = {
    "medical": "医疗医保知识",
    "policy": "综合政策知识",
    "management": "管理治理知识",
    "other": "公共专题知识",
    "personal": "个人材料",
}

DOMAIN_ORDER: tuple[str, ...] = ("medical", "policy", "management", "other", "personal")


GRAPH_NODES: tuple[dict[str, object], ...] = (
    {
        "id": "graph-node-project",
        "label": "专项自查项目",
        "kind": "项目",
        "status": "已归集",
        "description": "医保基金使用合规专项自查，承载当前审计主题、成员和工作流。",
        "metric": "3 名成员",
        "href": "/projects",
        "x": 100,
        "y": 250,
    },
    {
        "id": "graph-node-kb",
        "label": "系统知识库",
        "kind": "知识库",
        "status": "可引用",
        "description": "法规政策、医保目录、监管两库和风险负面清单的统一知识底座。",
        "metric": "48,985 篇",
        "href": "/knowledge-base",
        "x": 260,
        "y": 130,
    },
    {
        "id": "graph-node-document",
        "label": "目录限制资料包",
        "kind": "文档",
        "status": "可引用",
        "description": "用于限定诊疗项目、药品编码、支付范围和限制条件的可审证材料。",
        "metric": "2 份引用",
        "href": "/documents",
        "x": 430,
        "y": 130,
    },
    {
        "id": "graph-node-rule",
        "label": "重复收费规则",
        "kind": "规则",
        "status": "已归集",
        "description": "围绕同就诊、同项目、同日期和同金额线索形成规则命中条件。",
        "metric": "CHARGE-RULE-001",
        "href": "/rules",
        "x": 600,
        "y": 130,
    },
    {
        "id": "graph-node-finding",
        "label": "疑点 F044",
        "kind": "疑点",
        "status": "待复核",
        "description": "由收费明细和规则运行生成的重复收费疑点，等待人工核验。",
        "metric": "2 条记录",
        "href": "/findings",
        "x": 790,
        "y": 250,
    },
    {
        "id": "graph-node-review",
        "label": "复核任务 0007",
        "kind": "复核",
        "status": "门禁中",
        "description": "沉淀负责人确认、附件和人工判断，决定是否进入报告。",
        "metric": "负责人确认",
        "href": "/pages/review-tasks",
        "x": 600,
        "y": 370,
    },
    {
        "id": "graph-node-report",
        "label": "报告草稿",
        "kind": "报告",
        "status": "门禁中",
        "description": "从已复核疑点和引用材料生成的底稿与报告记录。",
        "metric": "1 份草稿",
        "href": "/reports",
        "x": 430,
        "y": 370,
    },
    {
        "id": "graph-node-remediation",
        "label": "整改跟踪",
        "kind": "整改",
        "status": "跟踪中",
        "description": "报告签发后进入整改责任、状态跟踪和后续归档链路。",
        "metric": "1 项跟踪",
        "href": "/remediation",
        "x": 260,
        "y": 370,
    },
)


GRAPH_RELATIONS: tuple[dict[str, object], ...] = (
    {
        "id": "graph-project-kb",
        "sourceId": "graph-node-project",
        "targetId": "graph-node-kb",
        "source": "医保基金使用合规专项自查",
        "relation": "引用",
        "target": "系统医保审计知识库",
        "evidence": "项目知识库绑定 · system-kb",
        "strength": "强",
    },
    {
        "id": "graph-kb-document",
        "sourceId": "graph-node-kb",
        "targetId": "graph-node-document",
        "source": "系统医保审计知识库",
        "relation": "产出",
        "target": "医保目录限制条件资料包",
        "evidence": "medical-insurance-catalog · 2 refs",
        "strength": "强",
    },
    {
        "id": "graph-document-rule",
        "sourceId": "graph-node-document",
        "targetId": "graph-node-rule",
        "source": "医保目录限制条件资料包",
        "relation": "约束",
        "target": "重复收费规则",
        "evidence": "支付范围和限制条件交叉核验",
        "strength": "中",
    },
    {
        "id": "graph-rule-finding",
        "sourceId": "graph-node-rule",
        "targetId": "graph-node-finding",
        "source": "重复收费规则",
        "relation": "命中",
        "target": "FINDING-F044EBD309B659DC",
        "evidence": "charge_detail · 2 records",
        "strength": "强",
    },
    {
        "id": "graph-finding-task",
        "sourceId": "graph-node-finding",
        "targetId": "graph-node-review",
        "source": "FINDING-F044EBD309B659DC",
        "relation": "生成",
        "target": "review-task-0007",
        "evidence": "rule_version CHARGE-RULE-001@v1",
        "strength": "强",
    },
    {
        "id": "graph-task-report",
        "sourceId": "graph-node-review",
        "targetId": "graph-node-report",
        "source": "review-task-0007",
        "relation": "进入",
        "target": "报告草稿",
        "evidence": "负责人确认和附件门禁",
        "strength": "中",
    },
    {
        "id": "graph-report-remediation",
        "sourceId": "graph-node-report",
        "targetId": "graph-node-remediation",
        "source": "报告草稿",
        "relation": "形成",
        "target": "整改跟踪",
        "evidence": "底稿结论、责任科室和整改期限",
        "strength": "待补",
    },
    {
        "id": "graph-remediation-project",
        "sourceId": "graph-node-remediation",
        "targetId": "graph-node-project",
        "source": "整改跟踪",
        "relation": "回写",
        "target": "医保基金使用合规专项自查",
        "evidence": "整改状态进入项目归档前检查",
        "strength": "待补",
    },
)


RULE_LIBRARY_ITEMS: tuple[dict[str, object], ...] = (
    {
        "id": "rule-duplicate-charge",
        "code": "CHARGE-RULE-001",
        "name": "同就诊同项目重复收费",
        "domain": "收费明细",
        "status": "已启用",
        "sourceCollection": "supervision-rules-knowledge",
        "evidenceScope": "按患者、就诊、项目、日期和金额聚合，识别同源重复收费。",
        "evidenceCount": 4,
        "findingCount": 1,
        "owner": "内审部",
        "updatedAt": "2026-06-11",
        "href": "/findings?rule=CHARGE-RULE-001",
        "chatHref": (
            "/chat?question=%E5%90%8C%E5%B0%B1%E8%AF%8A%E5%90%8C%E9%A1%B9"
            "%E7%9B%AE%E9%87%8D%E5%A4%8D%E6%94%B6%E8%B4%B9%E8%A7%84"
            "%E5%88%99%E5%A6%82%E4%BD%95%E6%A0%B8%E9%AA%8C%E8%AF%81"
            "%E6%8D%AE%E9%93%BE%EF%BC%9F"
        ),
    },
    {
        "id": "rule-catalog-limit",
        "code": "CATALOG-RULE-014",
        "name": "目录限制条件交叉核验",
        "domain": "医保目录",
        "status": "待补字段",
        "sourceCollection": "medical-insurance-catalog",
        "evidenceScope": "核对诊疗项目编码、医保支付范围、限制条件和结算口径。",
        "evidenceCount": 3,
        "findingCount": 2,
        "owner": "业务专家",
        "updatedAt": "2026-06-10",
        "href": "/knowledge-query?q=%E7%9B%AE%E5%BD%95%E9%99%90%E5%88%B6%E6%9D%A1%E4%BB%B6",
        "chatHref": (
            "/chat?question=%E7%9B%AE%E5%BD%95%E9%99%90%E5%88%B6%E6%9D"
            "%A1%E4%BB%B6%E8%A7%84%E5%88%99%E9%9C%80%E8%A6%81%E5%93"
            "%AA%E4%BA%9B%20HIS%20%E5%AD%97%E6%AE%B5%EF%BC%9F"
        ),
    },
    {
        "id": "rule-dose-limit",
        "code": "DOSE-RULE-006",
        "name": "门诊超量开药提示",
        "domain": "处方用药",
        "status": "待复核",
        "sourceCollection": "risk-negative-list",
        "evidenceScope": "结合处方天数、药品用量、就诊频次和特殊病种标识形成提示。",
        "evidenceCount": 2,
        "findingCount": 0,
        "owner": "内审部",
        "updatedAt": "2026-06-09",
        "href": "/documents",
        "chatHref": (
            "/chat?question=%E9%97%A8%E8%AF%8A%E8%B6%85%E9%87%8F%E5%BC"
            "%80%E8%8D%AF%E5%BA%94%E6%A0%B8%E5%AF%B9%E5%93%AA%E4%BA"
            "%9B%E5%8C%BB%E4%BF%9D%E5%AE%A1%E6%A0%B8%E4%BE%9D%E6%8D"
            "%AE%EF%BC%9F"
        ),
    },
    {
        "id": "rule-identity-risk",
        "code": "IDENTITY-RULE-003",
        "name": "参保身份异常核验",
        "domain": "参保身份",
        "status": "只读",
        "sourceCollection": "risk-negative-list",
        "evidenceScope": "比对参保身份、就诊记录、结算记录和异常高频使用线索。",
        "evidenceCount": 2,
        "findingCount": 0,
        "owner": "信息科",
        "updatedAt": "2026-06-08",
        "href": "/agent-market",
        "chatHref": "/chat?agent=template-identity-risk",
    },
)


RULE_SOURCE_COVERAGES: tuple[dict[str, object], ...] = (
    {
        "id": "rule-source-supervision",
        "name": "监管两库",
        "sourceCollection": "supervision-rules-knowledge",
        "ruleCount": 12840,
        "indexStatus": "可引用",
        "health": "规则库、知识库和知识点明细已同步。",
        "href": "/documents",
    },
    {
        "id": "rule-source-catalog",
        "name": "医保目录",
        "sourceCollection": "medical-insurance-catalog",
        "ruleCount": 18266,
        "indexStatus": "可引用",
        "health": "支付范围和限制条件已进入统一检索。",
        "href": "/knowledge-query?q=%E5%8C%BB%E4%BF%9D%E7%9B%AE%E5%BD%95",
    },
    {
        "id": "rule-source-risk",
        "name": "风险清单",
        "sourceCollection": "risk-negative-list",
        "ruleCount": 731,
        "indexStatus": "可引用",
        "health": "负面清单和专项风险案例可用于审计提示。",
        "href": "/documents",
    },
    {
        "id": "rule-source-chat",
        "name": "对话审证沉淀",
        "sourceCollection": "conversation-documents",
        "ruleCount": 2,
        "indexStatus": "待同步",
        "health": "对话材料只能作为草稿来源，转规则前需人工确认。",
        "href": "/chat",
    },
)


RULE_RUN_SNAPSHOTS: tuple[dict[str, object], ...] = (
    {
        "id": "run-duplicate-charge",
        "ruleCode": "CHARGE-RULE-001",
        "inputTable": "charge_detail",
        "lastRunAt": "2026-06-11 10:24",
        "hitCount": 1,
        "linkedFinding": "FINDING-F044EBD309B659DC",
        "nextAction": "进入疑点工作台复核。",
    },
    {
        "id": "run-catalog-limit",
        "ruleCode": "CATALOG-RULE-014",
        "inputTable": "his_charge_detail",
        "lastRunAt": "2026-06-10 16:30",
        "hitCount": 2,
        "linkedFinding": "待生成复核任务",
        "nextAction": "补齐医保目录限制字段。",
    },
    {
        "id": "run-dose-limit",
        "ruleCode": "DOSE-RULE-006",
        "inputTable": "prescription_detail",
        "lastRunAt": "2026-06-09 09:10",
        "hitCount": 0,
        "linkedFinding": "无",
        "nextAction": "保留为专项提示规则。",
    },
)


RULE_CONTROL_GATES: tuple[dict[str, object], ...] = (
    {
        "id": "rule-gate-source",
        "label": "来源可追溯",
        "status": "通过",
        "detail": "每条规则必须绑定知识库来源、规则编码和适用审计主题。",
        "owner": "审计员",
    },
    {
        "id": "rule-gate-field",
        "label": "字段可运行",
        "status": "阻断",
        "detail": "目录限制规则缺少部分 HIS 字段，不能直接进入批量运行。",
        "owner": "信息科",
    },
    {
        "id": "rule-gate-business",
        "label": "业务口径确认",
        "status": "待人工确认",
        "detail": "处方用药和身份异常规则需要业务专家确认阈值口径。",
        "owner": "业务专家",
    },
    {
        "id": "rule-gate-output",
        "label": "输出去向明确",
        "status": "通过",
        "detail": "规则命中后只能进入疑点、复核或审证对话，不能直接写入报告。",
        "owner": "审计员",
    },
)


REMEDIATION_CASES: tuple[dict[str, object], ...] = (
    {
        "id": "remediation-duplicate-charge",
        "title": "重复收费退费与流程复核",
        "department": "医保办",
        "owner": "医保办",
        "status": "整改中",
        "dueDate": "2026-06-20",
        "reportNo": "AUDIT-REPORT-20260611-001",
        "sourceFinding": "FINDING-F044EBD309B659DC",
        "progress": 62,
        "evidenceStatus": "已提交",
        "nextAction": "核验退费凭证和流程复核记录。",
        "href": "/pages/review-tasks",
    },
    {
        "id": "remediation-catalog-limit",
        "title": "目录限制项目收费口径复查",
        "department": "财务科",
        "owner": "财务科",
        "status": "待整改",
        "dueDate": "2026-06-25",
        "reportNo": "WORKPAPER-20260610-003",
        "sourceFinding": "CATALOG-RULE-014",
        "progress": 18,
        "evidenceStatus": "待补证",
        "nextAction": "补齐收费口径说明和 HIS 字段截图。",
        "href": "/knowledge-query?q=%E7%9B%AE%E5%BD%95%E9%99%90%E5%88%B6",
    },
    {
        "id": "remediation-attachment-archive",
        "title": "复核附件归档校验",
        "department": "信息科",
        "owner": "信息科",
        "status": "待验收",
        "dueDate": "2026-06-18",
        "reportNo": "WORKPAPER-20260611-002",
        "sourceFinding": "review-task-0002",
        "progress": 82,
        "evidenceStatus": "需退回",
        "nextAction": "重新上传带校验值的归档文件。",
        "href": "/pages/review-tasks",
    },
    {
        "id": "remediation-dose-review",
        "title": "门诊超量开药口径确认",
        "department": "药剂科",
        "owner": "药剂科",
        "status": "已关闭",
        "dueDate": "2026-06-15",
        "reportNo": "INTERNAL-MEMO-20260609-001",
        "sourceFinding": "DOSE-RULE-006",
        "progress": 100,
        "evidenceStatus": "已验收",
        "nextAction": "已进入项目归档检查。",
        "href": "/documents",
    },
)


REMEDIATION_EVIDENCE_REQUESTS: tuple[dict[str, object], ...] = (
    {
        "id": "evidence-refund",
        "title": "重复收费退费凭证",
        "linkedCaseId": "remediation-duplicate-charge",
        "kind": "退费凭证",
        "status": "已提交",
        "owner": "医保办",
        "dueDate": "2026-06-18",
        "detail": "退费流水、患者确认和财务复核记录已提交，等待审计验收。",
        "href": "/pages/review-tasks",
    },
    {
        "id": "evidence-catalog-field",
        "title": "目录限制 HIS 字段截图",
        "linkedCaseId": "remediation-catalog-limit",
        "kind": "HIS 凭证",
        "status": "待上传",
        "owner": "财务科",
        "dueDate": "2026-06-21",
        "detail": "需补充项目编码、支付范围、限制条件和结算口径字段截图。",
        "href": "/knowledge-query?q=%E7%9B%AE%E5%BD%95%E9%99%90%E5%88%B6",
    },
    {
        "id": "evidence-archive-hash",
        "title": "附件归档文件校验值",
        "linkedCaseId": "remediation-attachment-archive",
        "kind": "附件归档",
        "status": "需退回",
        "owner": "信息科",
        "dueDate": "2026-06-18",
        "detail": "附件名称已登记，但缺少文件 hash 和归档位置校验。",
        "href": "/pages/review-tasks",
    },
    {
        "id": "evidence-owner-confirm",
        "title": "整改负责人确认记录",
        "linkedCaseId": "remediation-duplicate-charge",
        "kind": "负责人确认",
        "status": "待上传",
        "owner": "项目负责人",
        "dueDate": "2026-06-20",
        "detail": "报告签发后的整改责任确认需与验收意见一起留痕。",
        "href": "/reports",
    },
)


REMEDIATION_CLOSURE_GATES: tuple[dict[str, object], ...] = (
    {
        "id": "remediation-gate-evidence",
        "label": "补证材料完整",
        "status": "阻断",
        "detail": "附件归档缺少文件 hash，目录限制字段仍未上传。",
        "owner": "信息科",
    },
    {
        "id": "remediation-gate-owner",
        "label": "责任科室确认",
        "status": "待人工确认",
        "detail": "医保办已提交退费凭证，仍需项目负责人确认闭环意见。",
        "owner": "项目负责人",
    },
    {
        "id": "remediation-gate-review",
        "label": "审计验收结论",
        "status": "待人工确认",
        "detail": "整改说明不能自动关闭，必须由审计员记录验收结论。",
        "owner": "审计员",
    },
    {
        "id": "remediation-gate-archive",
        "label": "归档前检查",
        "status": "通过",
        "detail": "已关闭事项可进入项目档案，未关闭事项继续留在整改台账。",
        "owner": "信息科",
    },
)


REMEDIATION_TIMELINE: tuple[dict[str, object], ...] = (
    {
        "id": "timeline-report-issued",
        "time": "2026-06-11 15:40",
        "title": "报告签发后生成整改事项",
        "detail": "AUDIT-REPORT-20260611-001 形成重复收费退费与流程复核整改事项。",
        "status": "已记录",
    },
    {
        "id": "timeline-refund-evidence",
        "time": "2026-06-12 09:15",
        "title": "医保办提交退费凭证",
        "detail": "退费流水和财务复核记录已进入验收队列。",
        "status": "已记录",
    },
    {
        "id": "timeline-attachment-blocked",
        "time": "2026-06-12 11:20",
        "title": "附件归档校验阻断",
        "detail": "系统发现附件只有登记名称，缺少文件 hash 和归档位置。",
        "status": "已阻断",
    },
    {
        "id": "timeline-catalog-pending",
        "time": "2026-06-12 14:05",
        "title": "目录限制字段待补",
        "detail": "财务科需补充 HIS 字段截图和收费口径说明。",
        "status": "待处理",
    },
)


ARCHIVE_PACKAGES: tuple[dict[str, object], ...] = (
    {
        "id": "archive-package-fund-self-check",
        "projectName": "医保基金使用合规专项自查",
        "archiveNo": "ARCHIVE-SELF-CHECK-FUND-202606",
        "status": "归档前检查",
        "reportNo": "AUDIT-REPORT-20260611-001",
        "owner": "项目负责人",
        "archiveScope": "报告正文、整改事项、复核附件和审计日志索引。",
        "evidenceSummary": "1 项整改门禁仍阻断，等待附件 hash 和目录限制字段。",
        "signedAt": "2026-06-11",
        "retainedUntil": "2026-12-09",
        "href": "/reports",
        "logHref": "/pages/audit-logs?entity_type=review-task&entity_id=review-task-0001",
    },
    {
        "id": "archive-package-kb-governance",
        "projectName": "审计知识库治理项目",
        "archiveNo": "ARCHIVE-KB-GOV-202606",
        "status": "已归档",
        "reportNo": "INTERNAL-MEMO-20260609-001",
        "owner": "信息科接口人",
        "archiveScope": "知识库索引、文档入库、规则发布和巡检记录。",
        "evidenceSummary": "签名 manifest 可验，archive root 巡检通过。",
        "signedAt": "2026-06-10",
        "retainedUntil": "2026-12-07",
        "href": "/projects",
        "logHref": "/pages/audit-logs?entity_type=project&entity_id=KB-GOVERNANCE-202606",
    },
    {
        "id": "archive-package-dose-review",
        "projectName": "门诊超量开药专项复核",
        "archiveNo": "ARCHIVE-DOSE-202606",
        "status": "待归档",
        "reportNo": "WORKPAPER-20260610-003",
        "owner": "审计员",
        "archiveScope": "复核底稿、处方分析、人工确认记录。",
        "evidenceSummary": "底稿草稿可导出，负责人确认仍待补。",
        "signedAt": "未签发",
        "retainedUntil": "待签发后计算",
        "href": "/reports",
        "logHref": "/pages/audit-logs?entity_type=review-task&entity_id=review-task-0007",
    },
    {
        "id": "archive-package-catalog-limit",
        "projectName": "医保目录限制条件核验",
        "archiveNo": "ARCHIVE-CATALOG-LIMIT-202606",
        "status": "材料阻断",
        "reportNo": "WORKPAPER-20260611-002",
        "owner": "业务专家",
        "archiveScope": "规则命中、HIS 字段截图、整改验收和引用来源。",
        "evidenceSummary": "目录限制 HIS 字段截图缺失，不能进入长期归档。",
        "signedAt": "未签发",
        "retainedUntil": "待补证后计算",
        "href": "/remediation",
        "logHref": "/pages/audit-logs?entity_type=rule&entity_id=CATALOG-RULE-014",
    },
)


ARCHIVE_AUDIT_RUNS: tuple[dict[str, object], ...] = (
    {
        "id": "archive-run-root-audit",
        "title": "archive root 巡检",
        "status": "通过",
        "time": "2026-06-12 03:17",
        "archiveRoot": "/opt/medical-audit/audit-log-archive",
        "manifestCount": 0,
        "failedCount": 0,
        "detail": "latest JSON 报告 status=pass，当前没有失败 manifest。",
    },
    {
        "id": "archive-run-retention-plan",
        "title": "保留期归档计划",
        "status": "待人工确认",
        "time": "2026-06-12 02:40",
        "archiveRoot": "audit_log_events",
        "manifestCount": 1,
        "failedCount": 0,
        "detail": "180 天外事件必须先 dry-run，再显式执行归档清理。",
    },
    {
        "id": "archive-run-alert-webhook",
        "title": "外部告警端点",
        "status": "待配置",
        "time": "配置后启用",
        "archiveRoot": "MEDICAL_AUDIT_AUDIT_LOG_ALERT_WEBHOOK_URL",
        "manifestCount": 0,
        "failedCount": 0,
        "detail": "未配置 webhook 时只能依赖 cron 退出码和 latest 报告排查。",
    },
)


ARCHIVE_SIGNATURE_ITEMS: tuple[dict[str, object], ...] = (
    {
        "id": "archive-signature-retention-batch",
        "label": "retention-batch-0001.jsonl",
        "status": "验签通过",
        "sha256": "e7c4a6b2c41f0b1a9f7d2e3a6b8c9d01",
        "detail": "归档文件、archive_sha256 和 detached HMAC-SHA256 manifest 一致。",
    },
    {
        "id": "archive-signature-latest-report",
        "label": "audit-log-archive-audit-latest.json",
        "status": "已生成",
        "sha256": "latest-report-managed-by-cron",
        "detail": "巡检脚本维护 latest 报告，用于生产只读排查。",
    },
    {
        "id": "archive-signature-case-file",
        "label": "case-level-remediation-archive",
        "status": "待生成",
        "sha256": "等待整改验收后生成",
        "detail": "案件级整改归档流仍是后续范围，首期只读展示阻断原因。",
    },
)


ARCHIVE_POLICY_ITEMS: tuple[dict[str, object], ...] = (
    {
        "id": "archive-policy-roles",
        "label": "允许角色",
        "value": "it-admin / department-head",
        "detail": "审计日志查询和导出必须通过角色校验。",
    },
    {
        "id": "archive-policy-retention",
        "label": "保留周期",
        "value": "180 days",
        "detail": "保留期外事件归档后再清理数据库记录。",
    },
    {
        "id": "archive-policy-redaction",
        "label": "脱敏模式",
        "value": "response-only",
        "detail": "API 响应和导出结果对敏感字段脱敏，原始归档受控保存。",
    },
    {
        "id": "archive-policy-layout",
        "label": "受控目录",
        "value": "audit-log-events/YYYY/MM/DD/<batch-key>.jsonl",
        "detail": "归档输出和签名 manifest 不得逃出 archive root。",
    },
)


ARCHIVE_TIMELINE: tuple[dict[str, object], ...] = (
    {
        "id": "archive-timeline-cron",
        "time": "2026-06-05 03:17",
        "title": "归档巡检 cron 生效",
        "detail": "腾讯云生产环境每天执行只读 archive root 巡检。",
        "status": "已部署",
    },
    {
        "id": "archive-timeline-kb",
        "time": "2026-06-10 16:30",
        "title": "知识库治理项目入档",
        "detail": "索引治理、规则发布和巡检证据已进入项目档案。",
        "status": "已入档",
    },
    {
        "id": "archive-timeline-report",
        "time": "2026-06-11 15:40",
        "title": "报告签发生成档案包",
        "detail": "AUDIT-REPORT-20260611-001 进入归档前检查。",
        "status": "已记录",
    },
    {
        "id": "archive-timeline-blocked",
        "time": "2026-06-12 11:20",
        "title": "附件 hash 阻断归档",
        "detail": "缺少附件 hash 和归档位置，不能进入长期保存。",
        "status": "待补证",
    },
)


@router.get("/graph/workbench")
def graph_workbench(
    state: Annotated[ApiState, Depends(get_api_state)],
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_role: Annotated[str | None, Header(alias="X-Role")] = None,
) -> dict[str, object]:
    user = resolve_authenticated_user(
        state,
        x_user_id=x_user_id,
        x_role=x_role,
        default_role=HospitalRole.MEMBER,
    )
    graph = _knowledge_catalog_graph(state=state, role=user.legacy_api_role)
    metrics = _graph_metrics(graph["nodes"], graph["relations"])
    record_operation(
        state,
        "graph-workbench-view",
        {
            "node_count": metrics["node_count"],
            "relation_count": metrics["relation_count"],
            "strong_relation_count": metrics["strong_relation_count"],
            "pending_relation_count": metrics["pending_relation_count"],
        },
    )
    return {
        "format": "graph-workbench-v1",
        "generated_at": _utc_now_iso(),
        "graph_id": "SELF-CHECK-FUND-20260607",
        "graph_title": "医保基金使用合规专项图谱",
        "graph_scope": (
            "基于当前可查询知识库目录，将医疗医保、政策、管理和公共专题知识组织成可审证关系图。"
        ),
        "nodes": graph["nodes"],
        "relations": graph["relations"],
        "metrics": metrics,
        "evidence_grade": "local-readonly-api",
        "production_side_effect": "none",
        "store": {"ready": True, "backend": "KnowledgeCatalogGraphBuilder"},
    }


@router.get("/rules/workbench")
def rules_workbench(
    state: Annotated[ApiState, Depends(get_api_state)],
) -> dict[str, object]:
    metrics = _rules_metrics()
    record_operation(
        state,
        "rules-workbench-view",
        {
            "rule_count": metrics["rule_count"],
            "enabled_rule_count": metrics["enabled_rule_count"],
            "total_finding_count": metrics["total_finding_count"],
            "blocked_gate_count": metrics["blocked_gate_count"],
        },
    )
    return {
        "format": "rules-workbench-v1",
        "generated_at": _utc_now_iso(),
        "ruleset_id": "FUND-USAGE-COMPLIANCE-RULES",
        "ruleset_title": "医保基金使用合规专题规则库",
        "ruleset_scope": (
            "汇总监管两库、医保目录、风险清单和对话审证沉淀，"
            "只读展示规则来源、运行状态和疑点去向。"
        ),
        "rule_library_items": RULE_LIBRARY_ITEMS,
        "source_coverages": RULE_SOURCE_COVERAGES,
        "run_snapshots": RULE_RUN_SNAPSHOTS,
        "control_gates": RULE_CONTROL_GATES,
        "metrics": metrics,
        "evidence_grade": "local-readonly-api",
        "production_side_effect": "none",
        "store": {"ready": True, "backend": "ReadonlyRulesWorkbenchSeed"},
    }


@router.get("/remediation/workbench")
def remediation_workbench(
    state: Annotated[ApiState, Depends(get_api_state)],
) -> dict[str, object]:
    metrics = _remediation_metrics()
    record_operation(
        state,
        "remediation-workbench-view",
        {
            "case_count": metrics["case_count"],
            "active_case_count": metrics["active_case_count"],
            "pending_evidence_count": metrics["pending_evidence_count"],
            "blocked_gate_count": metrics["blocked_gate_count"],
        },
    )
    return {
        "format": "remediation-workbench-v1",
        "generated_at": _utc_now_iso(),
        "workbench_id": "FUND-USAGE-REMEDIATION",
        "workbench_title": "整改事项与补证闭环",
        "workbench_scope": "把报告整改事项、补证请求、责任科室和验收门禁组织成可追踪的整改工作台。",
        "remediation_cases": REMEDIATION_CASES,
        "evidence_requests": REMEDIATION_EVIDENCE_REQUESTS,
        "closure_gates": REMEDIATION_CLOSURE_GATES,
        "timeline": REMEDIATION_TIMELINE,
        "metrics": metrics,
        "evidence_grade": "local-readonly-api",
        "production_side_effect": "none",
        "store": {"ready": True, "backend": "ReadonlyRemediationWorkbenchSeed"},
    }


@router.get("/archive/workbench")
def archive_workbench(
    state: Annotated[ApiState, Depends(get_api_state)],
) -> dict[str, object]:
    metrics = _archive_metrics()
    record_operation(
        state,
        "archive-workbench-view",
        {
            "package_count": metrics["package_count"],
            "archived_package_count": metrics["archived_package_count"],
            "blocked_package_count": metrics["blocked_package_count"],
            "audit_run_count": metrics["audit_run_count"],
        },
    )
    return {
        "format": "archive-workbench-v1",
        "generated_at": _utc_now_iso(),
        "archive_id": "FUND-USAGE-ARCHIVE",
        "archive_title": "项目档案与审计日志归档",
        "archive_scope": (
            "汇总项目档案包、审计日志归档、签名链和归档前阻断原因，"
            "首期只读展示归档状态和受控导出入口。"
        ),
        "archive_packages": ARCHIVE_PACKAGES,
        "audit_runs": ARCHIVE_AUDIT_RUNS,
        "signature_items": ARCHIVE_SIGNATURE_ITEMS,
        "policy_items": ARCHIVE_POLICY_ITEMS,
        "timeline": ARCHIVE_TIMELINE,
        "metrics": metrics,
        "evidence_grade": "local-readonly-api",
        "production_side_effect": "none",
        "store": {"ready": True, "backend": "ReadonlyArchiveWorkbenchSeed"},
    }


def _knowledge_catalog_graph(*, state: ApiState, role: str) -> dict[str, list[dict[str, object]]]:
    catalog = build_knowledge_base_catalog_response(state=state, role=role)
    items = catalog.items
    nodes: list[dict[str, object]] = [
        {
            "id": "graph-node-project",
            "label": "医疗审计知识工程",
            "kind": "项目",
            "status": "已归集",
            "description": "当前生产知识库目录、文档检索和审计问答共同使用的知识底座。",
            "metric": f"{catalog.summary.source_collection_count} 类知识库",
            "href": "/projects",
            "x": 100,
            "y": 250,
        }
    ]
    relations: list[dict[str, object]] = []
    grouped_domains = [
        domain
        for domain in DOMAIN_ORDER
        if any(item.domain == domain for item in items)
    ]
    for domain_index, domain in enumerate(grouped_domains):
        domain_items = [item for item in items if item.domain == domain]
        domain_id = f"graph-domain-{domain}"
        domain_x = 280 + (domain_index * 180)
        domain_y = 120 + ((domain_index % 2) * 260)
        domain_chunk_count = sum(item.metrics.chunk_count for item in domain_items)
        nodes.append(
            {
                "id": domain_id,
                "label": DOMAIN_LABELS.get(domain, domain),
                "kind": "一级分类",
                "status": "可引用" if any(item.queryable for item in domain_items) else "待接入",
                "description": (
                    f"{DOMAIN_LABELS.get(domain, domain)}下共有 {len(domain_items)} 个知识库。"
                ),
                "metric": f"{domain_chunk_count:,} chunks",
                "href": f"/knowledge-base?domain={domain}",
                "x": domain_x,
                "y": domain_y,
            }
        )
        relations.append(
            {
                "id": f"graph-project-{domain}",
                "sourceId": "graph-node-project",
                "targetId": domain_id,
                "source": "医疗审计知识工程",
                "relation": "组织",
                "target": DOMAIN_LABELS.get(domain, domain),
                "evidence": f"{len(domain_items)} 个一级知识库分类",
                "strength": "强",
            }
        )
        for item_index, item in enumerate(domain_items):
            node_id = f"graph-source-{item.source_collection.value}"
            node_x = 220 + ((item_index % 5) * 170)
            node_y = 520 + (domain_index * 170) + ((item_index // 5) * 90)
            active_count = item.metrics.active_embedding_count or item.metrics.embedding_count
            nodes.append(
                {
                    "id": node_id,
                    "label": item.label,
                    "kind": "知识库",
                    "status": "可引用" if item.queryable else "待接入",
                    "description": item.audit_hint or item.description,
                    "metric": (
                        f"{item.metrics.document_count:,} 文档 / "
                        f"{item.metrics.chunk_count:,} chunks"
                    ),
                    "href": item.actions["documents"],
                    "x": node_x,
                    "y": node_y,
                    "sourceCollection": item.source_collection.value,
                    "domain": item.domain,
                }
            )
            relations.append(
                {
                    "id": f"graph-{domain}-{item.source_collection.value}",
                    "sourceId": domain_id,
                    "targetId": node_id,
                    "source": DOMAIN_LABELS.get(domain, domain),
                    "relation": "包含",
                    "target": item.label,
                    "evidence": f"{active_count:,} active embeddings",
                    "strength": "强" if active_count else "待补",
                }
            )
    return {"nodes": nodes, "relations": relations}


def _graph_metrics(
    nodes: list[dict[str, object]],
    relations: list[dict[str, object]],
) -> dict[str, object]:
    node_kind_counts = Counter(str(node["kind"]) for node in nodes)
    return {
        "node_count": len(nodes),
        "node_kind_count": len(node_kind_counts),
        "node_kind_counts": dict(node_kind_counts),
        "relation_count": len(relations),
        "strong_relation_count": sum(
            1 for relation in relations if relation["strength"] == "强"
        ),
        "pending_relation_count": sum(
            1 for relation in relations if relation["strength"] == "待补"
        ),
    }


def _rules_metrics() -> dict[str, object]:
    return {
        "rule_count": len(RULE_LIBRARY_ITEMS),
        "enabled_rule_count": sum(
            1 for rule in RULE_LIBRARY_ITEMS if rule["status"] == "已启用"
        ),
        "pending_rule_count": sum(
            1 for rule in RULE_LIBRARY_ITEMS if rule["status"] != "已启用"
        ),
        "total_finding_count": sum(
            cast(int, rule["findingCount"]) for rule in RULE_LIBRARY_ITEMS
        ),
        "blocked_gate_count": sum(
            1 for gate in RULE_CONTROL_GATES if gate["status"] == "阻断"
        ),
        "source_count": len(RULE_SOURCE_COVERAGES),
        "run_count": len(RULE_RUN_SNAPSHOTS),
    }


def _remediation_metrics() -> dict[str, object]:
    case_count = len(REMEDIATION_CASES)
    total_progress = sum(cast(int, item["progress"]) for item in REMEDIATION_CASES)
    return {
        "case_count": case_count,
        "active_case_count": sum(
            1 for item in REMEDIATION_CASES if item["status"] != "已关闭"
        ),
        "closed_case_count": sum(
            1 for item in REMEDIATION_CASES if item["status"] == "已关闭"
        ),
        "pending_evidence_count": sum(
            1
            for item in REMEDIATION_EVIDENCE_REQUESTS
            if item["status"] in {"待上传", "需退回"}
        ),
        "blocked_gate_count": sum(
            1 for gate in REMEDIATION_CLOSURE_GATES if gate["status"] == "阻断"
        ),
        "average_progress": round(total_progress / case_count) if case_count else 0,
        "timeline_count": len(REMEDIATION_TIMELINE),
    }


def _archive_metrics() -> dict[str, object]:
    latest_run_status = str(ARCHIVE_AUDIT_RUNS[0]["status"]) if ARCHIVE_AUDIT_RUNS else "无"
    return {
        "package_count": len(ARCHIVE_PACKAGES),
        "archived_package_count": sum(
            1 for item in ARCHIVE_PACKAGES if item["status"] == "已归档"
        ),
        "pending_package_count": sum(
            1 for item in ARCHIVE_PACKAGES if item["status"] != "已归档"
        ),
        "blocked_package_count": sum(
            1 for item in ARCHIVE_PACKAGES if item["status"] == "材料阻断"
        ),
        "audit_run_count": len(ARCHIVE_AUDIT_RUNS),
        "signature_count": len(ARCHIVE_SIGNATURE_ITEMS),
        "policy_count": len(ARCHIVE_POLICY_ITEMS),
        "timeline_count": len(ARCHIVE_TIMELINE),
        "latest_archive_run_status": latest_run_status,
    }


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
