"use client";

import { useMemo, useState } from "react";

import { buildReplicaLocalGateNotice } from "@/components/replica/replica-page-kit";

type AuditView = "audit" | "table1" | "table2" | "table3";
type ToolId = "audit" | "dip" | "code" | "price" | "rule" | "setting";
type RuleFilter = "all" | "policy" | "manage" | "medical" | "dip" | "code" | "price";
type RiskLevel = "高风险" | "中风险" | "低风险";
type RiskFilter = "全部风险" | RiskLevel;
type DeptFilter = "全部科室" | "内科" | "外科" | "骨科" | "儿科" | "妇产科" | "心内科";
type StatusFilter = "全部状态" | "待初审" | "待复核" | "已确认违规" | "已整改" | "已驳回";
type AssistantRole = "assistant" | "user";

type AuditFinding = {
  readonly id: string;
  readonly patient: string;
  readonly gender: string;
  readonly age: number;
  readonly department: Exclude<DeptFilter, "全部科室">;
  readonly doctor: string;
  readonly dimension: string;
  readonly rule: string;
  readonly amount: number;
  readonly risk: RiskLevel;
  readonly status: Exclude<StatusFilter, "全部状态">;
  readonly date: string;
  readonly diagnosis: string;
  readonly subject: string;
  readonly evidence: string;
  readonly knowledge: string;
  readonly code: string;
  readonly toolIds: readonly ToolId[];
};

type AssistantMessage = {
  readonly id: string;
  readonly role: AssistantRole;
  readonly text: string;
};

type AssistantContext = {
  readonly finding: AuditFinding | null;
  readonly activeView: AuditView;
  readonly activeRule: RuleFilter;
  readonly riskFilter: RiskFilter;
  readonly deptFilter: DeptFilter;
  readonly statusFilter: StatusFilter;
  readonly filteredCount: number;
  readonly selectedCount: number;
};

type FeeCategoryRow = {
  readonly category: string;
  readonly visits: string;
  readonly people: string;
  readonly validVisits: string;
  readonly validPeople: string;
  readonly averageFee: string;
  readonly totalFee: string;
  readonly cashPay: string;
  readonly accountPay: string;
  readonly poolPay: string;
  readonly largePay: string;
  readonly civilPay: string;
  readonly medicalAid: string;
  readonly totalLedger: string;
  readonly ratio: number;
};

type VisitDetailRow = {
  readonly seq: number;
  readonly staffType: "在职职工" | "退休人员" | "灵活就业";
  readonly recordNo: string;
  readonly name: string;
  readonly idNo: string;
  readonly diagnosis: string;
  readonly totalFee: string;
  readonly selfPay: string;
  readonly poolPay: string;
  readonly civilPay: string;
  readonly largePay: string;
  readonly accountPay: string;
};

const toolModules: readonly { id: ToolId; label: string; badge?: string; symbol: string }[] = [
  { id: "audit", label: "智能审计", badge: "89", symbol: "审" },
  { id: "dip", label: "DIP/DRG审计", badge: "34", symbol: "分" },
  { id: "code", label: "编码质量", badge: "12", symbol: "码" },
  { id: "price", label: "价格合规", badge: "45", symbol: "费" },
  { id: "rule", label: "两库规则", symbol: "库" },
  { id: "setting", label: "系统配置", symbol: "设" }
];

const viewTabs: readonly { id: AuditView; label: string }[] = [
  { id: "audit", label: "智能审计" },
  { id: "table1", label: "费用汇总表" },
  { id: "table2", label: "分类汇总表" },
  { id: "table3", label: "就诊明细表" }
];

const ruleTabs: readonly { id: RuleFilter; label: string }[] = [
  { id: "all", label: "全部疑点" },
  { id: "policy", label: "政策类" },
  { id: "manage", label: "管理类" },
  { id: "medical", label: "医疗类" },
  { id: "dip", label: "DIP/DRG" },
  { id: "code", label: "编码质量" },
  { id: "price", label: "价格合规" }
];

const riskOptions: readonly RiskFilter[] = ["全部风险", "高风险", "中风险", "低风险"];
const deptOptions: readonly DeptFilter[] = ["全部科室", "内科", "外科", "骨科", "儿科", "妇产科", "心内科"];
const statusOptions: readonly StatusFilter[] = ["全部状态", "待初审", "待复核", "已确认违规", "已整改", "已驳回"];

const assistantQuickActions = [
  "分析当前疑点",
  "生成复核意见",
  "汇总高风险原因",
  "起草整改通知"
] as const;

const initialAssistantMessages: readonly AssistantMessage[] = [
  {
    id: "assistant-welcome",
    role: "assistant",
    text: "我已进入医保审计工作台，可基于当前疑点、规则维度、筛选条件和费用表格生成本地分析建议。"
  }
] as const;

const metricCards = [
  {
    label: "本月疑点总数",
    value: "207",
    tone: "blue",
    change: "▲ 12.5% 较上月",
    changeTone: "up",
    sub: "高风险 89 | 中风险 68 | 低风险 50"
  },
  {
    label: "涉及金额（元）",
    value: "¥128,450",
    tone: "blue",
    change: "▲ 8.3% 较上月",
    changeTone: "up",
    sub: "药品类 ¥68,200 | 项目类 ¥34,150 | 其他 ¥26,100"
  },
  {
    label: "DIP分值异常",
    value: "34",
    tone: "blue",
    change: "▲ 5.7% 较上月",
    changeTone: "up",
    sub: "高套嫌疑 12 | 低套嫌疑 8 | 分值偏差 14"
  },
  {
    label: "已整改 / 整改率",
    value: "28 / 13.5%",
    tone: "green",
    change: "▼ 2.1% 较上月",
    changeTone: "down",
    sub: "待复核 34 | 逾期 6"
  }
] as const;

const auditFindings: readonly AuditFinding[] = [
  {
    id: "20251203001",
    patient: "王**",
    gender: "男",
    age: 52,
    department: "骨科",
    doctor: "赵医生",
    amount: 1240,
    rule: "药品区分性别使用",
    dimension: "政策类-药品",
    knowledge: "枸橼酸他莫昔芬片限女性使用",
    code: "XB01AAT012A001010203485",
    diagnosis: "骨质疏松",
    subject: "枸橼酸他莫昔芬片 10mg*60片",
    evidence: "患者性别为男，药品限定性别为女。无乳腺癌相关诊断。",
    risk: "高风险",
    status: "待初审",
    date: "2025-12-03",
    toolIds: ["audit", "rule"]
  },
  {
    id: "20251203005",
    patient: "李**",
    gender: "女",
    age: 34,
    department: "内科",
    doctor: "钱医生",
    amount: 8600,
    rule: "药品限适应症",
    dimension: "政策类-药品",
    knowledge: "注射用阿替普酶限急性缺血性脑卒中发病 4.5 小时内",
    code: "XB01AAD021A001010203491",
    diagnosis: "高血压",
    subject: "注射用阿替普酶 20mg",
    evidence: "患者诊断仅为高血压，无急性缺血性脑卒中相关诊断及发病时间记录。",
    risk: "高风险",
    status: "待初审",
    date: "2025-12-03",
    toolIds: ["audit", "rule"]
  },
  {
    id: "20251202018",
    patient: "张**",
    gender: "男",
    age: 67,
    department: "心内科",
    doctor: "孙医生",
    amount: 320,
    rule: "药品限工伤保险",
    dimension: "政策类-药品",
    knowledge: "工伤保险药品目录范围外使用",
    code: "XB01AAG034A001010203512",
    diagnosis: "冠心病",
    subject: "丹参酮IIA磺酸钠注射液",
    evidence: "患者参保类型为职工医保，非工伤保险。该药品限定支付范围为限工伤保险。",
    risk: "中风险",
    status: "待复核",
    date: "2025-12-02",
    toolIds: ["audit", "rule"]
  },
  {
    id: "20251201015",
    patient: "刘**",
    gender: "女",
    age: 56,
    department: "骨科",
    doctor: "吴医生",
    amount: 2340,
    rule: "药品限适应症",
    dimension: "政策类-药品",
    knowledge: "利伐沙班限髋关节或膝关节置换术后",
    code: "XB01AAD067A001010203556",
    diagnosis: "腰椎间盘突出",
    subject: "利伐沙班片 15mg*7片",
    evidence: "患者诊断为腰椎间盘突出，未行髋关节或膝关节置换手术。",
    risk: "高风险",
    status: "待初审",
    date: "2025-12-01",
    toolIds: ["audit", "rule"]
  },
  {
    id: "20251201042",
    patient: "周**",
    gender: "男",
    age: 72,
    department: "内科",
    doctor: "周医生",
    amount: 12500,
    rule: "DIP分值高套",
    dimension: "DIP/DRG",
    knowledge: "DIP 病种分值与主要诊断、费用结构应保持一致",
    code: "DIP-A02.0",
    diagnosis: "沙门菌肠炎",
    subject: "医保申报分值 480.50",
    evidence: "病案首页主要诊断应得分值 351.94，医保申报分值偏差 36.5%。",
    risk: "高风险",
    status: "待复核",
    date: "2025-12-01",
    toolIds: ["audit", "dip"]
  },
  {
    id: "20251201058",
    patient: "吴**",
    gender: "女",
    age: 45,
    department: "妇产科",
    doctor: "冯医生",
    amount: 2800,
    rule: "DRG分组错误",
    dimension: "DIP/DRG",
    knowledge: "DRG 分组需与主要诊断、手术编码和并发症保持一致",
    code: "DRG-O01",
    diagnosis: "子宫肌瘤",
    subject: "DRG 组别异常",
    evidence: "主要诊断与手术编码组合无法支持当前分组，需复核病案首页。",
    risk: "高风险",
    status: "待初审",
    date: "2025-12-01",
    toolIds: ["audit", "dip", "code"]
  },
  {
    id: "20251130031",
    patient: "孙**",
    gender: "男",
    age: 38,
    department: "内科",
    doctor: "郑医生",
    amount: 5200,
    rule: "信息数据篡改",
    dimension: "管理类",
    knowledge: "入院、结算、收费时间应可追溯且一致",
    code: "MGMT-TIME-078",
    diagnosis: "肺炎",
    subject: "HIS 入院时间与医保结算时间不一致",
    evidence: "HIS 显示入院时间为 2025-11-28 09:30，医保结算接口记录为 2025-11-27 22:00。",
    risk: "高风险",
    status: "待复核",
    date: "2025-11-30",
    toolIds: ["audit", "code"]
  },
  {
    id: "20251129012",
    patient: "马**",
    gender: "女",
    age: 61,
    department: "外科",
    doctor: "陈医生",
    amount: 85,
    rule: "诊疗项目超标准收费",
    dimension: "价格合规",
    knowledge: "河南省医疗服务价格项目规范",
    code: "PRICE-DRESSING-056",
    diagnosis: "术后伤口护理",
    subject: "小换药收费",
    evidence: "服务目录标准为小换药 15 元/次，实际收取 25 元/次。",
    risk: "低风险",
    status: "已驳回",
    date: "2025-11-29",
    toolIds: ["audit", "price"]
  },
  {
    id: "20251128045",
    patient: "郑**",
    gender: "男",
    age: 55,
    department: "骨科",
    doctor: "刘医生",
    amount: 3400,
    rule: "ICD-10编码不完整",
    dimension: "编码质量",
    knowledge: "病案首页主要诊断需编码到规则要求粒度",
    code: "ICD10-S72.0",
    diagnosis: "股骨颈骨折",
    subject: "主要诊断编码 S72.0",
    evidence: "主要诊断未编码到细目，影响 DIP 分组准确性。",
    risk: "中风险",
    status: "待初审",
    date: "2025-11-28",
    toolIds: ["audit", "code", "dip"]
  },
  {
    id: "20251127019",
    patient: "赵**",
    gender: "女",
    age: 29,
    department: "儿科",
    doctor: "韩医生",
    amount: 1260,
    rule: "药品儿童专用",
    dimension: "政策类-药品",
    knowledge: "儿童专用药品不得用于成人医保结算",
    code: "XB01AAP044A001010203577",
    diagnosis: "急性支气管炎",
    subject: "儿童复方制剂",
    evidence: "参保人年龄 29 岁，药品限定儿童适用，未见特殊说明。",
    risk: "中风险",
    status: "已确认违规",
    date: "2025-11-27",
    toolIds: ["audit", "rule"]
  }
];

const ruleGroups = [
  {
    title: "政策类规则",
    filter: "policy" as const,
    children: ["药品区分性别使用", "药品儿童专用", "药品限工伤保险", "药品限生育保险", "药品限适应症", "药品限疗程", "药品限就医方式"]
  },
  {
    title: "管理类规则",
    filter: "manage" as const,
    children: ["信息数据篡改", "虚假病历", "超量开药", "分解收费", "串换项目"]
  },
  {
    title: "医疗类规则",
    filter: "medical" as const,
    children: ["诊疗项目重复收费", "诊疗项目超标准收费", "耗材超量使用", "诊疗项目与诊断不符"]
  },
  {
    title: "审计状态",
    filter: "all" as const,
    children: ["待初审", "待复核", "已确认违规", "已整改"]
  }
];

const feeCategoryRows: readonly FeeCategoryRow[] = [
  { category: "普通门诊", visits: "3,256", people: "1,890", validVisits: "3,120", validPeople: "1,820", averageFee: "¥286", totalFee: "¥931,216", cashPay: "¥186,243", accountPay: "¥279,365", poolPay: "¥372,486", largePay: "¥0", civilPay: "¥46,561", medicalAid: "¥0", totalLedger: "¥744,973", ratio: 2.3 },
  { category: "门诊慢性病", visits: "1,286", people: "456", validVisits: "1,250", validPeople: "440", averageFee: "¥1,568", totalFee: "¥2,016,448", cashPay: "¥403,289", accountPay: "¥604,934", poolPay: "¥806,579", largePay: "¥40,329", civilPay: "¥50,412", medicalAid: "¥40,329", totalLedger: "¥1,613,159", ratio: 4.9 },
  { category: "重特大疾病门诊", visits: "234", people: "89", validVisits: "228", validPeople: "86", averageFee: "¥8,520", totalFee: "¥1,993,680", cashPay: "¥598,104", accountPay: "¥498,420", poolPay: "¥598,104", largePay: "¥199,368", civilPay: "¥49,842", medicalAid: "¥49,842", totalLedger: "¥1,395,576", ratio: 4.8 },
  { category: "特药门诊", visits: "156", people: "67", validVisits: "150", validPeople: "65", averageFee: "¥12,860", totalFee: "¥2,006,160", cashPay: "¥601,848", accountPay: "¥501,540", poolPay: "¥601,848", largePay: "¥200,616", civilPay: "¥50,154", medicalAid: "¥50,154", totalLedger: "¥1,404,312", ratio: 4.9 },
  { category: "普通住院", visits: "892", people: "823", validVisits: "870", validPeople: "810", averageFee: "¥12,568", totalFee: "¥11,214,656", cashPay: "¥3,364,397", accountPay: "¥2,242,931", poolPay: "¥3,364,397", largePay: "¥1,121,466", civilPay: "¥280,866", medicalAid: "¥224,293", totalLedger: "¥7,850,262", ratio: 27.3 },
  { category: "重大疾病住院", visits: "123", people: "118", validVisits: "120", validPeople: "116", averageFee: "¥42,580", totalFee: "¥5,237,340", cashPay: "¥1,571,202", accountPay: "¥1,047,468", poolPay: "¥1,571,202", largePay: "¥523,734", civilPay: "¥130,933", medicalAid: "¥261,867", totalLedger: "¥3,666,138", ratio: 12.7 },
  { category: "单病种住院", visits: "345", people: "340", validVisits: "340", validPeople: "338", averageFee: "¥9,850", totalFee: "¥3,398,250", cashPay: "¥1,019,475", accountPay: "¥679,650", poolPay: "¥1,019,475", largePay: "¥339,825", civilPay: "¥84,956", medicalAid: "¥169,912", totalLedger: "¥2,378,775", ratio: 8.3 },
  { category: "生育住院", visits: "89", people: "89", validVisits: "89", validPeople: "89", averageFee: "¥6,520", totalFee: "¥580,280", cashPay: "¥174,084", accountPay: "¥116,056", poolPay: "¥174,084", largePay: "¥0", civilPay: "¥0", medicalAid: "¥0", totalLedger: "¥406,196", ratio: 1.4 },
  { category: "计划生育手术", visits: "45", people: "45", validVisits: "45", validPeople: "45", averageFee: "¥1,860", totalFee: "¥83,700", cashPay: "¥25,110", accountPay: "¥16,740", poolPay: "¥25,110", largePay: "¥0", civilPay: "¥0", medicalAid: "¥0", totalLedger: "¥58,590", ratio: 0.2 },
  { category: "辅助生殖门诊", visits: "67", people: "34", validVisits: "64", validPeople: "33", averageFee: "¥15,680", totalFee: "¥1,050,560", cashPay: "¥315,168", accountPay: "¥210,112", poolPay: "¥315,168", largePay: "¥0", civilPay: "¥52,528", medicalAid: "¥0", totalLedger: "¥735,392", ratio: 2.6 },
  { category: "日间手术", visits: "234", people: "231", validVisits: "230", validPeople: "229", averageFee: "¥6,850", totalFee: "¥1,602,900", cashPay: "¥480,870", accountPay: "¥320,580", poolPay: "¥480,870", largePay: "¥80,145", civilPay: "¥80,145", medicalAid: "¥0", totalLedger: "¥1,122,030", ratio: 3.9 },
  { category: "透析治疗", visits: "890", people: "156", validVisits: "880", validPeople: "154", averageFee: "¥5,680", totalFee: "¥5,056,320", cashPay: "¥1,516,896", accountPay: "¥1,011,264", poolPay: "¥1,516,896", largePay: "¥505,632", civilPay: "¥50,563", medicalAid: "¥101,126", totalLedger: "¥3,539,424", ratio: 12.3 },
  { category: "体检", visits: "2,560", people: "2,450", validVisits: "2,500", validPeople: "2,400", averageFee: "¥860", totalFee: "¥2,201,600", cashPay: "¥1,320,960", accountPay: "¥440,320", poolPay: "¥0", largePay: "¥0", civilPay: "¥0", medicalAid: "¥0", totalLedger: "¥0", ratio: 5.3 }
];

const visitRows: readonly VisitDetailRow[] = [
  { seq: 1, staffType: "在职职工", recordNo: "MZ20251203001", name: "王建国", idNo: "41010519780512****", diagnosis: "腰椎间盘突出", totalFee: "¥3,260", selfPay: "¥978", poolPay: "¥1,304", civilPay: "¥326", largePay: "¥0", accountPay: "¥652" },
  { seq: 2, staffType: "在职职工", recordNo: "MZ20251203002", name: "李秀芳", idNo: "41010519820324****", diagnosis: "2型糖尿病", totalFee: "¥1,856", selfPay: "¥557", poolPay: "¥742", civilPay: "¥186", largePay: "¥0", accountPay: "¥371" },
  { seq: 3, staffType: "退休人员", recordNo: "MZ20251203003", name: "张德明", idNo: "41010519560918****", diagnosis: "高血压病III级", totalFee: "¥2,450", selfPay: "¥735", poolPay: "¥980", civilPay: "¥245", largePay: "¥0", accountPay: "¥490" },
  { seq: 4, staffType: "在职职工", recordNo: "MZ20251203004", name: "刘美华", idNo: "41010519900506****", diagnosis: "急性上呼吸道感染", totalFee: "¥580", selfPay: "¥174", poolPay: "¥232", civilPay: "¥58", largePay: "¥0", accountPay: "¥116" },
  { seq: 5, staffType: "在职职工", recordNo: "ZY20251203005", name: "陈志强", idNo: "41010519871123****", diagnosis: "冠心病-心绞痛", totalFee: "¥28,650", selfPay: "¥8,595", poolPay: "¥11,460", civilPay: "¥2,865", largePay: "¥2,865", accountPay: "¥2,865" },
  { seq: 6, staffType: "退休人员", recordNo: "ZY20251203006", name: "赵秀英", idNo: "41010519530214****", diagnosis: "脑梗死恢复期", totalFee: "¥35,680", selfPay: "¥10,704", poolPay: "¥14,272", civilPay: "¥3,568", largePay: "¥3,568", accountPay: "¥3,568" },
  { seq: 7, staffType: "在职职工", recordNo: "MZ20251203007", name: "孙伟强", idNo: "41010519920815****", diagnosis: "慢性胃炎", totalFee: "¥1,280", selfPay: "¥384", poolPay: "¥512", civilPay: "¥128", largePay: "¥0", accountPay: "¥256" },
  { seq: 8, staffType: "在职职工", recordNo: "MZ20251203008", name: "周晓燕", idNo: "41010519891007****", diagnosis: "甲状腺结节", totalFee: "¥2,680", selfPay: "¥804", poolPay: "¥1,072", civilPay: "¥268", largePay: "¥0", accountPay: "¥536" },
  { seq: 9, staffType: "灵活就业", recordNo: "MZ20251203009", name: "吴国强", idNo: "41010519741203****", diagnosis: "慢性支气管炎", totalFee: "¥1,850", selfPay: "¥555", poolPay: "¥740", civilPay: "¥185", largePay: "¥0", accountPay: "¥370" },
  { seq: 10, staffType: "在职职工", recordNo: "ZY20251203010", name: "郑小玲", idNo: "41010519960318****", diagnosis: "剖宫产术后", totalFee: "¥9,850", selfPay: "¥2,955", poolPay: "¥3,940", civilPay: "¥0", largePay: "¥0", accountPay: "¥2,955" },
  { seq: 11, staffType: "退休人员", recordNo: "MZ20251203011", name: "黄志华", idNo: "41010519580522****", diagnosis: "骨质疏松症", totalFee: "¥1,560", selfPay: "¥468", poolPay: "¥624", civilPay: "¥156", largePay: "¥0", accountPay: "¥312" },
  { seq: 12, staffType: "在职职工", recordNo: "MZ20251203012", name: "马丽娟", idNo: "41010519840109****", diagnosis: "乳腺纤维瘤", totalFee: "¥3,280", selfPay: "¥984", poolPay: "¥1,312", civilPay: "¥328", largePay: "¥0", accountPay: "¥656" },
  { seq: 13, staffType: "在职职工", recordNo: "ZY20251203013", name: "林建华", idNo: "41010519720328****", diagnosis: "肺恶性肿瘤化疗", totalFee: "¥45,680", selfPay: "¥13,704", poolPay: "¥18,272", civilPay: "¥4,568", largePay: "¥4,568", accountPay: "¥4,568" },
  { seq: 14, staffType: "退休人员", recordNo: "MZ20251203014", name: "谢淑芬", idNo: "41010519541106****", diagnosis: "类风湿关节炎", totalFee: "¥2,180", selfPay: "¥654", poolPay: "¥872", civilPay: "¥218", largePay: "¥0", accountPay: "¥436" },
  { seq: 15, staffType: "在职职工", recordNo: "MZ20251203015", name: "高明辉", idNo: "41010519860814****", diagnosis: "急性阑尾炎术后", totalFee: "¥8,650", selfPay: "¥2,595", poolPay: "¥3,460", civilPay: "¥865", largePay: "¥0", accountPay: "¥1,730" },
  { seq: 16, staffType: "在职职工", recordNo: "MZ20251203016", name: "何晓峰", idNo: "41010519910520****", diagnosis: "痛风性关节炎", totalFee: "¥1,420", selfPay: "¥426", poolPay: "¥568", civilPay: "¥142", largePay: "¥0", accountPay: "¥284" },
  { seq: 17, staffType: "退休人员", recordNo: "ZY20251203017", name: "罗秀兰", idNo: "41010519490730****", diagnosis: "股骨颈骨折术后", totalFee: "¥42,360", selfPay: "¥12,708", poolPay: "¥16,944", civilPay: "¥4,236", largePay: "¥4,236", accountPay: "¥4,236" },
  { seq: 18, staffType: "在职职工", recordNo: "MZ20251203018", name: "梁志强", idNo: "41010519831217****", diagnosis: "青光眼", totalFee: "¥2,560", selfPay: "¥768", poolPay: "¥1,024", civilPay: "¥256", largePay: "¥0", accountPay: "¥512" },
  { seq: 19, staffType: "灵活就业", recordNo: "MZ20251203019", name: "宋美琳", idNo: "41010519760908****", diagnosis: "宫颈上皮内瘤变", totalFee: "¥4,860", selfPay: "¥1,458", poolPay: "¥1,944", civilPay: "¥486", largePay: "¥0", accountPay: "¥972" },
  { seq: 20, staffType: "在职职工", recordNo: "ZY20251203020", name: "曹建军", idNo: "41010519940211****", diagnosis: "胫骨平台骨折", totalFee: "¥32,560", selfPay: "¥9,768", poolPay: "¥13,024", civilPay: "¥3,256", largePay: "¥3,256", accountPay: "¥3,256" },
  { seq: 21, staffType: "在职职工", recordNo: "MZ20251203021", name: "彭小雪", idNo: "41010519850725****", diagnosis: "妊娠期糖尿病", totalFee: "¥3,680", selfPay: "¥1,104", poolPay: "¥1,472", civilPay: "¥0", largePay: "¥0", accountPay: "¥1,104" },
  { seq: 22, staffType: "退休人员", recordNo: "MZ20251203022", name: "杜国安", idNo: "41010519520102****", diagnosis: "慢性阻塞性肺疾病", totalFee: "¥6,240", selfPay: "¥1,872", poolPay: "¥2,496", civilPay: "¥624", largePay: "¥0", accountPay: "¥1,248" },
  { seq: 23, staffType: "在职职工", recordNo: "MZ20251203023", name: "邵丽", idNo: "41010519930823****", diagnosis: "胆囊结石", totalFee: "¥7,930", selfPay: "¥2,379", poolPay: "¥3,172", civilPay: "¥793", largePay: "¥0", accountPay: "¥1,586" },
  { seq: 24, staffType: "灵活就业", recordNo: "MZ20251203024", name: "孟繁强", idNo: "41010519770519****", diagnosis: "椎间盘突出", totalFee: "¥2,740", selfPay: "¥822", poolPay: "¥1,096", civilPay: "¥274", largePay: "¥0", accountPay: "¥548" },
  { seq: 25, staffType: "在职职工", recordNo: "ZY20251203025", name: "丁晓敏", idNo: "41010519891029****", diagnosis: "甲状腺癌术后", totalFee: "¥29,860", selfPay: "¥8,958", poolPay: "¥11,944", civilPay: "¥2,986", largePay: "¥2,986", accountPay: "¥2,986" }
];

function formatCurrency(amount: number) {
  return `¥${amount.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function riskClass(risk: RiskLevel) {
  if (risk === "高风险") return "is-high";
  if (risk === "中风险") return "is-medium";
  return "is-low";
}

function statusClass(status: Exclude<StatusFilter, "全部状态">) {
  if (status === "待初审") return "is-blue";
  if (status === "待复核") return "is-medium";
  if (status === "已确认违规") return "is-danger";
  if (status === "已整改") return "is-low";
  return "is-muted";
}

function ruleMatchesFilter(item: AuditFinding, activeRule: RuleFilter) {
  if (activeRule === "all") return true;
  if (activeRule === "policy") return item.dimension.startsWith("政策");
  if (activeRule === "manage") return item.dimension.startsWith("管理");
  if (activeRule === "medical") return item.dimension.startsWith("医疗");
  if (activeRule === "dip") return item.dimension.includes("DIP") || item.dimension.includes("DRG");
  if (activeRule === "code") return item.dimension.includes("编码");
  return item.dimension.includes("价格");
}

function buildAssistantReply(prompt: string, context: AssistantContext) {
  const filterText = [
    context.riskFilter,
    context.deptFilter,
    context.statusFilter,
    ruleTabs.find((tab) => tab.id === context.activeRule)?.label ?? "全部疑点"
  ].join(" / ");

  if (context.finding) {
    const finding = context.finding;
    if (prompt.includes("整改")) {
      return `整改建议：围绕 ${finding.id} 的「${finding.rule}」先补齐诊断、医嘱、医保目录限制和收费明细四类证据；责任科室为${finding.department}，建议整改时限 3 个工作日，整改后由医保办复核 ${formatCurrency(finding.amount)} 涉及金额。`;
    }
    if (prompt.includes("复核")) {
      return `复核意见草稿：${finding.patient} ${finding.diagnosis} 与「${finding.knowledge}」存在不一致，当前证据显示 ${finding.evidence} 建议维持${finding.risk}，进入${finding.status}队列并要求科室补证。`;
    }
    return `已基于当前疑点生成分析：单据 ${finding.id} 命中「${finding.rule}」，涉及 ${formatCurrency(finding.amount)}，风险等级为${finding.risk}。优先核对医保编码 ${finding.code}、诊断 ${finding.diagnosis}、项目 ${finding.subject} 与知识点依据的一致性。`;
  }

  if (prompt.includes("高风险")) {
    return `当前筛选条件为 ${filterText}，命中 ${context.filteredCount} 条疑点。高风险排查建议按金额、规则类别、科室集中度排序，优先处理药品限制、DIP/DRG 分值偏差和信息数据篡改三类。`;
  }

  return `当前处于「${viewTabs.find((view) => view.id === context.activeView)?.label ?? "智能审计"}」视图，筛选条件为 ${filterText}，表内共有 ${context.filteredCount} 条疑点，已勾选 ${context.selectedCount} 条。建议先核对高风险规则、金额异常和证据链完整性，再形成复核意见。`;
}

function MedicalStatusRail({
  activeTool,
  onToolChange
}: {
  readonly activeTool: ToolId;
  readonly onToolChange: (tool: ToolId) => void;
}) {
  return (
    <aside className="replica-medical-iconrail" aria-label="医保审计工具栏">
      {toolModules.map((tool) => (
        <button
          key={tool.id}
          type="button"
          aria-label={tool.label}
          aria-pressed={activeTool === tool.id}
          className={activeTool === tool.id ? "is-active" : ""}
          onClick={() => onToolChange(tool.id)}
        >
          {tool.badge ? <em>{tool.badge}</em> : null}
          <span aria-hidden="true">{tool.symbol}</span>
        </button>
      ))}
    </aside>
  );
}

function RuleNavigator({
  activeRule,
  ruleSearch,
  onRuleChange,
  onRuleSearch
}: {
  readonly activeRule: RuleFilter;
  readonly ruleSearch: string;
  readonly onRuleChange: (filter: RuleFilter) => void;
  readonly onRuleSearch: (value: string) => void;
}) {
  const normalized = ruleSearch.trim().toLowerCase();

  return (
    <aside className="replica-medical-rules" aria-label="智能审计规则导航">
      <h2>智能审计 - 规则导航</h2>
      <label className="replica-medical-search">
        <span aria-hidden="true">⌕</span>
        <input
          value={ruleSearch}
          onChange={(event) => onRuleSearch(event.target.value)}
          placeholder="搜索规则/知识点/编码..."
        />
      </label>
      <nav>
        {ruleGroups.map((group) => {
          const visibleChildren = group.children.filter((child) => child.toLowerCase().includes(normalized));
          if (normalized && visibleChildren.length === 0) return null;
          return (
            <section key={group.title}>
              <button
                type="button"
                className={activeRule === group.filter ? "is-active" : ""}
                onClick={() => onRuleChange(group.filter)}
              >
                {group.title}
              </button>
              <div>
                {visibleChildren.map((child) => (
                  <button key={child} type="button" onClick={() => onRuleSearch(child)}>
                    {child}
                  </button>
                ))}
              </div>
            </section>
          );
        })}
      </nav>
    </aside>
  );
}

function MedicalMetricCards() {
  return (
    <section className="replica-medical-metrics" aria-label="医保审计指标">
      {metricCards.map((metric) => (
        <article key={metric.label} className={`tone-${metric.tone}`}>
          <span>{metric.label}</span>
          <strong>{metric.value}</strong>
          <em className={metric.changeTone === "up" ? "is-up" : "is-down"}>{metric.change}</em>
          <p>{metric.sub}</p>
        </article>
      ))}
    </section>
  );
}

function LocalActionNotice({ text }: { readonly text: string }) {
  return (
    <div className="replica-medical-notice" role="status">
      {text}
    </div>
  );
}

function MedicalAuditPageTabs({
  activeView,
  onViewChange
}: {
  readonly activeView: AuditView;
  readonly onViewChange: (view: AuditView) => void;
}) {
  return (
    <div className="replica-medical-tabs" role="tablist" aria-label="医保审计子页面">
      {viewTabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          role="tab"
          aria-selected={activeView === tab.id}
          className={activeView === tab.id ? "is-active" : ""}
          onClick={() => onViewChange(tab.id)}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}

function SelectFilter<T extends string>({
  label,
  value,
  options,
  onChange
}: {
  readonly label: string;
  readonly value: T;
  readonly options: readonly T[];
  readonly onChange: (value: T) => void;
}) {
  return (
    <label className="replica-medical-select">
      <span>{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value as T)}>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

function AuditTable({
  rows,
  selectedIds,
  page,
  totalPages,
  selectedFindingId,
  onToggleRow,
  onTogglePage,
  onOpenFinding,
  onPageChange
}: {
  readonly rows: readonly AuditFinding[];
  readonly selectedIds: ReadonlySet<string>;
  readonly page: number;
  readonly totalPages: number;
  readonly selectedFindingId: string | null;
  readonly onToggleRow: (id: string) => void;
  readonly onTogglePage: () => void;
  readonly onOpenFinding: (id: string) => void;
  readonly onPageChange: (page: number) => void;
}) {
  const isPageSelected = rows.length > 0 && rows.every((row) => selectedIds.has(row.id));

  return (
    <>
      <div className="replica-medical-data-table is-audit-list">
        <table>
          <thead>
            <tr>
              <th>
                <input
                  type="checkbox"
                  aria-label="选择当前页"
                  checked={isPageSelected}
                  onChange={onTogglePage}
                />
              </th>
              <th>单据号</th>
              <th>患者</th>
              <th>科室</th>
              <th>维度</th>
              <th>命中规则</th>
              <th>涉及金额</th>
              <th>风险</th>
              <th>状态</th>
              <th>日期</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} className={selectedFindingId === row.id ? "is-active" : ""}>
                <td data-label="选择">
                  <input
                    type="checkbox"
                    aria-label={`选择${row.id}`}
                    checked={selectedIds.has(row.id)}
                    onChange={() => onToggleRow(row.id)}
                  />
                </td>
                <td data-label="单据号">
                  <button type="button" onClick={() => onOpenFinding(row.id)}>
                    {row.id}
                  </button>
                </td>
                <td data-label="患者">{row.patient}（{row.gender}，{row.age}岁）</td>
                <td data-label="科室">{row.department}</td>
                <td data-label="维度">
                  <span className="replica-medical-dimension">{row.dimension}</span>
                </td>
                <td data-label="命中规则">{row.rule}</td>
                <td data-label="涉及金额" className="is-number">{formatCurrency(row.amount)}</td>
                <td data-label="风险">
                  <span className={`replica-medical-tag ${riskClass(row.risk)}`}>{row.risk}</span>
                </td>
                <td data-label="状态">
                  <span className={`replica-medical-tag ${statusClass(row.status)}`}>{row.status}</span>
                </td>
                <td data-label="日期">{row.date}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="replica-medical-pagination">
        <button type="button" disabled={page === 1} onClick={() => onPageChange(page - 1)}>
          上一页
        </button>
        {Array.from({ length: totalPages }, (_, index) => index + 1).map((pageNumber) => (
          <button
            key={pageNumber}
            type="button"
            className={pageNumber === page ? "is-active" : ""}
            onClick={() => onPageChange(pageNumber)}
          >
            {pageNumber}
          </button>
        ))}
        <button type="button" disabled={page === totalPages} onClick={() => onPageChange(page + 1)}>
          下一页
        </button>
        <span>共 {auditFindings.length} 条</span>
      </div>
    </>
  );
}

function FindingDrawer({
  finding,
  onClose,
  onLocalAction
}: {
  readonly finding: AuditFinding | null;
  readonly onClose: () => void;
  readonly onLocalAction: (action: string) => void;
}) {
  if (!finding) return null;

  return (
    <aside className="replica-medical-drawer" aria-label="疑点详情">
      <div className="replica-medical-drawer-head">
        <button type="button" onClick={onClose}>
          收起
        </button>
        <button type="button" aria-label="关闭疑点详情" onClick={onClose}>
          ×
        </button>
      </div>
      <section>
        <h2>疑点详情</h2>
        <h3>基本信息</h3>
        <dl>
          <div><dt>单据号</dt><dd>{finding.id}</dd></div>
          <div><dt>患者</dt><dd>{finding.patient}（{finding.gender}，{finding.age}岁）</dd></div>
          <div><dt>科室</dt><dd>{finding.department}</dd></div>
          <div><dt>医师</dt><dd>{finding.doctor}</dd></div>
          <div><dt>诊断</dt><dd>{finding.diagnosis}</dd></div>
          <div><dt>涉及药品/项目</dt><dd>{finding.subject}</dd></div>
          <div><dt>涉及金额</dt><dd>{formatCurrency(finding.amount)}</dd></div>
          <div><dt>发生时间</dt><dd>{finding.date}</dd></div>
          <div><dt>风险等级</dt><dd><span className={`replica-medical-tag ${riskClass(finding.risk)}`}>{finding.risk}</span></dd></div>
          <div><dt>当前状态</dt><dd>{finding.status}</dd></div>
        </dl>
      </section>
      <section>
        <h3>规则命中</h3>
        <article className="replica-medical-evidence is-danger">
          <strong>{finding.rule}</strong>
          <p>医保编码 <code>{finding.code}</code></p>
        </article>
        <article className="replica-medical-evidence is-blue">
          <strong>知识点依据</strong>
          <p>{finding.knowledge}</p>
          <a href="/knowledge-query">查看原文</a>
        </article>
      </section>
      <section>
        <h3>审计证据</h3>
        <article className="replica-medical-evidence">
          <p>{finding.evidence}</p>
        </article>
      </section>
      <section>
        <h3>关联单据</h3>
        <ul className="replica-medical-related">
          <li><span>同患者近30天其他单据</span><strong>3 条</strong></li>
          <li><span>同科室同规则其他单据</span><strong>7 条</strong></li>
          <li><span>同医师其他违规</span><strong>1 条</strong></li>
        </ul>
      </section>
      <section>
        <h3>法规原文</h3>
        <p className="replica-medical-source">医疗保障基金智能监管规则库、知识库（2025年版）· 第三部分</p>
        <p className="replica-medical-source">国家基本医疗保险药品目录（2025年）· 西药部分</p>
        <p className="replica-medical-source">河南省医疗服务价格项目规范（20260201版）</p>
      </section>
      <div className="replica-medical-drawer-actions">
        <button type="button" onClick={() => onLocalAction("通过")}>通过</button>
        <button type="button" className="is-primary" onClick={() => onLocalAction("确认违规")}>确认违规</button>
        <button type="button" onClick={() => onLocalAction("转整改")}>转整改</button>
        <button type="button" onClick={() => onLocalAction("更多")}>更多</button>
      </div>
    </aside>
  );
}

function MedicalAiAssistantButton({
  isOpen,
  isShifted,
  onClick
}: {
  readonly isOpen: boolean;
  readonly isShifted: boolean;
  readonly onClick: () => void;
}) {
  return (
    <button
      type="button"
      className={`replica-medical-ai-fab ${isOpen ? "is-open" : ""} ${isShifted ? "is-shifted" : ""}`}
      aria-label={isOpen ? "收起AI审计助手" : "打开AI审计助手"}
      onClick={onClick}
    >
      <span>AI</span>
      <strong>审计助手</strong>
    </button>
  );
}

function MedicalAiDrawer({
  context,
  messages,
  draft,
  onDraftChange,
  onQuickAction,
  onSubmit,
  onClose,
  onLocalAction
}: {
  readonly context: AssistantContext;
  readonly messages: readonly AssistantMessage[];
  readonly draft: string;
  readonly onDraftChange: (value: string) => void;
  readonly onQuickAction: (prompt: string) => void;
  readonly onSubmit: () => void;
  readonly onClose: () => void;
  readonly onLocalAction: (action: string) => void;
}) {
  const activeViewLabel = viewTabs.find((view) => view.id === context.activeView)?.label ?? "智能审计";
  const activeRuleLabel = ruleTabs.find((tab) => tab.id === context.activeRule)?.label ?? "全部疑点";

  return (
    <aside className="replica-medical-ai-drawer" aria-label="AI审计助手抽屉">
      <header className="replica-medical-ai-head">
        <div>
          <span>AI 审计助手</span>
          <h2>医保疑点联审</h2>
        </div>
        <button type="button" aria-label="关闭AI审计助手" onClick={onClose}>
          ×
        </button>
      </header>
      <section className="replica-medical-ai-context" aria-label="当前上下文">
        <div>
          <span>当前上下文</span>
          <strong>{context.finding ? context.finding.id : activeViewLabel}</strong>
        </div>
        {context.finding ? (
          <p>
            {context.finding.patient} · {context.finding.department} · {context.finding.rule} · {formatCurrency(context.finding.amount)}
          </p>
        ) : (
          <p>
            {activeRuleLabel} / {context.riskFilter} / {context.deptFilter} / {context.statusFilter}，共 {context.filteredCount} 条疑点。
          </p>
        )}
        <dl>
          <div><dt>审计模式</dt><dd>安全预览</dd></div>
          <div><dt>已选疑点</dt><dd>{context.selectedCount} 条</dd></div>
          <div><dt>筛选结果</dt><dd>{context.filteredCount} 条</dd></div>
        </dl>
      </section>
      <section className="replica-medical-ai-shortcuts" aria-label="AI快捷指令">
        {assistantQuickActions.map((action) => (
          <button key={action} type="button" onClick={() => onQuickAction(action)}>
            {action}
          </button>
        ))}
      </section>
      <section className="replica-medical-ai-thread" aria-label="AI对话记录">
        {messages.map((message) => (
          <article key={message.id} className={`replica-medical-ai-message is-${message.role}`}>
            <span>{message.role === "assistant" ? "AI" : "我"}</span>
            <p>{message.text}</p>
          </article>
        ))}
      </section>
      <form
        className="replica-medical-ai-compose"
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit();
        }}
      >
        <label>
          <span>输入 AI 指令</span>
          <textarea
            value={draft}
            onChange={(event) => onDraftChange(event.target.value)}
            placeholder="询问当前疑点、复核意见或整改建议..."
          />
        </label>
        <div>
          <button type="button" onClick={() => onLocalAction("引用知识库依据")}>
            引用依据
          </button>
          <button type="submit" className="is-primary">
            发送
          </button>
        </div>
      </form>
    </aside>
  );
}

function SmartAuditView({
  activeRule,
  riskFilter,
  deptFilter,
  statusFilter,
  rows,
  pagedRows,
  page,
  totalPages,
  selectedIds,
  selectedFindingId,
  onRuleTabChange,
  onRiskChange,
  onDeptChange,
  onStatusChange,
  onToggleRow,
  onTogglePage,
  onOpenFinding,
  onPageChange,
  onLocalAction
}: {
  readonly activeRule: RuleFilter;
  readonly riskFilter: RiskFilter;
  readonly deptFilter: DeptFilter;
  readonly statusFilter: StatusFilter;
  readonly rows: readonly AuditFinding[];
  readonly pagedRows: readonly AuditFinding[];
  readonly page: number;
  readonly totalPages: number;
  readonly selectedIds: ReadonlySet<string>;
  readonly selectedFindingId: string | null;
  readonly onRuleTabChange: (tab: RuleFilter) => void;
  readonly onRiskChange: (value: RiskFilter) => void;
  readonly onDeptChange: (value: DeptFilter) => void;
  readonly onStatusChange: (value: StatusFilter) => void;
  readonly onToggleRow: (id: string) => void;
  readonly onTogglePage: () => void;
  readonly onOpenFinding: (id: string) => void;
  readonly onPageChange: (page: number) => void;
  readonly onLocalAction: (action: string) => void;
}) {
  return (
    <>
      <MedicalMetricCards />
      <div className="replica-medical-rule-tabs" role="tablist" aria-label="疑点分类">
        {ruleTabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={activeRule === tab.id}
            className={activeRule === tab.id ? "is-active" : ""}
            onClick={() => onRuleTabChange(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div className="replica-medical-toolbar">
        <div>
          <button type="button" className="replica-primary-button" onClick={() => onLocalAction("新建审计任务")}>
            新建审计任务
          </button>
          <button type="button" className="replica-secondary-button" onClick={() => onLocalAction("批量导入")}>
            批量导入
          </button>
          <button type="button" className="replica-secondary-button" onClick={() => onLocalAction("导出报告")}>
            导出报告
          </button>
          <button type="button" className="replica-danger-button" onClick={() => onLocalAction("确认违规")}>
            确认违规
          </button>
        </div>
        <div>
          <SelectFilter label="风险" value={riskFilter} options={riskOptions} onChange={onRiskChange} />
          <SelectFilter label="科室" value={deptFilter} options={deptOptions} onChange={onDeptChange} />
          <SelectFilter label="状态" value={statusFilter} options={statusOptions} onChange={onStatusChange} />
        </div>
      </div>
      <AuditTable
        rows={pagedRows}
        selectedIds={selectedIds}
        page={page}
        totalPages={totalPages}
        selectedFindingId={selectedFindingId}
        onToggleRow={onToggleRow}
        onTogglePage={onTogglePage}
        onOpenFinding={onOpenFinding}
        onPageChange={onPageChange}
      />
      {rows.length === 0 ? <div className="replica-medical-empty">当前筛选条件下暂无疑点。</div> : null}
    </>
  );
}

function TablePageHeader({
  title,
  badge,
  extra,
  onLocalAction
}: {
  readonly title: string;
  readonly badge: string;
  readonly extra?: string;
  readonly onLocalAction: (action: string) => void;
}) {
  return (
    <header className="replica-medical-table-head">
      <div>
        <h2>{title}</h2>
        <span>{badge}</span>
        {extra ? <em>{extra}</em> : null}
      </div>
      <div>
        <button type="button" className="replica-secondary-button" onClick={() => onLocalAction("新建表单")}>
          新建表单
        </button>
        <button type="button" className="replica-secondary-button" onClick={() => onLocalAction("打印")}>
          打印
        </button>
        <button type="button" className="replica-primary-button" onClick={() => onLocalAction("导出Excel")}>
          导出Excel
        </button>
      </div>
    </header>
  );
}

function MedicalTableMeta({ mode }: { readonly mode: "summary" | "detail" }) {
  return (
    <div className="replica-medical-table-meta">
      <span>定点医疗机构：<strong>河南省人民医院</strong></span>
      {mode === "summary" ? (
        <span>统计日期：2025年12月01日 至 2025年12月31日</span>
      ) : (
        <span>统计日期：2025年12月01日 00:00:00 至 2025年12月31日 23:59:59</span>
      )}
      <span>单位：元</span>
    </div>
  );
}

function FeeSummaryTable({ onLocalAction }: { readonly onLocalAction: (action: string) => void }) {
  return (
    <section className="replica-medical-table-page" aria-label="医保费用汇总表">
      <TablePageHeader title="医保费用汇总表" badge="表1" onLocalAction={onLocalAction} />
      <MedicalTableMeta mode="summary" />
      <div className="replica-medical-data-table is-wide">
        <table>
          <thead>
            <tr>
              <th>费用分类</th>
              <th>人次</th>
              <th>人数</th>
              <th>有效人次</th>
              <th>有效人数</th>
              <th>平均费用</th>
              <th>医疗总费用</th>
              <th>现金支付</th>
              <th>账户支付</th>
              <th>统筹支付</th>
              <th>大额记账</th>
              <th>公务员补助</th>
              <th>医疗救助</th>
              <th>记账合计</th>
            </tr>
          </thead>
          <tbody>
            {feeCategoryRows.map((row) => (
              <tr key={row.category}>
                <td>{row.category}</td>
                <td>{row.visits}</td>
                <td>{row.people}</td>
                <td>{row.validVisits}</td>
                <td>{row.validPeople}</td>
                <td>{row.averageFee}</td>
                <td className="is-link-number">{row.totalFee}</td>
                <td>{row.cashPay}</td>
                <td>{row.accountPay}</td>
                <td>{row.poolPay}</td>
                <td>{row.largePay}</td>
                <td>{row.civilPay}</td>
                <td>{row.medicalAid}</td>
                <td>{row.totalLedger}</td>
              </tr>
            ))}
            <tr className="is-total">
              <td>合计</td>
              <td>13,448</td>
              <td>9,325</td>
              <td>13,057</td>
              <td>9,093</td>
              <td>¥3,152</td>
              <td>¥41,153,790</td>
              <td>¥12,557,945</td>
              <td>¥8,879,421</td>
              <td>¥12,134,328</td>
              <td>¥3,011,115</td>
              <td>¥1,058,585</td>
              <td>¥912,343</td>
              <td>¥27,714,083</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div className="replica-medical-signatures">
        <span>主管领导：__________</span>
        <span>医保办负责人：__________</span>
        <span>制表人：__________</span>
      </div>
    </section>
  );
}

function FeeCategoryTable({ onLocalAction }: { readonly onLocalAction: (action: string) => void }) {
  return (
    <section className="replica-medical-table-page" aria-label="医保费用分类汇总表">
      <TablePageHeader title="医保费用分类汇总表" badge="表2" onLocalAction={onLocalAction} />
      <MedicalTableMeta mode="summary" />
      <div className="replica-medical-summary-cards">
        <article><span>医疗总费用</span><strong>¥41,153,790</strong></article>
        <article className="is-green"><span>统筹支付</span><strong>¥12,134,328</strong></article>
        <article className="is-amber"><span>现金支付</span><strong>¥12,557,945</strong></article>
        <article className="is-cyan"><span>账户支付</span><strong>¥8,879,421</strong></article>
      </div>
      <div className="replica-medical-data-table">
        <table>
          <thead>
            <tr>
              <th>费用分类</th>
              <th>人次</th>
              <th>医疗总费用</th>
              <th>统筹支付</th>
              <th>现金支付</th>
              <th>占比</th>
              <th>趋势</th>
            </tr>
          </thead>
          <tbody>
            {feeCategoryRows.map((row) => (
              <tr key={row.category}>
                <td>{row.category}</td>
                <td>{row.visits}</td>
                <td className="is-link-number">{row.totalFee}</td>
                <td>{row.poolPay}</td>
                <td>{row.cashPay}</td>
                <td>{row.ratio.toFixed(1)}%</td>
                <td>
                  <span className="replica-medical-bar">
                    <span style={{ width: `${Math.max(row.ratio, 1.2)}%` }} />
                  </span>
                </td>
              </tr>
            ))}
            <tr className="is-total">
              <td>合计</td>
              <td>13,448</td>
              <td>¥41,153,790</td>
              <td>¥12,134,328</td>
              <td>¥12,557,945</td>
              <td>100%</td>
              <td><span className="replica-medical-bar"><span style={{ width: "100%" }} /></span></td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  );
}

function VisitDetailTable({
  search,
  onSearch,
  onLocalAction
}: {
  readonly search: string;
  readonly onSearch: (value: string) => void;
  readonly onLocalAction: (action: string) => void;
}) {
  const filteredRows = useMemo(() => {
    const normalized = search.trim().toLowerCase();
    if (!normalized) return visitRows;
    return visitRows.filter((row) =>
      [row.name, row.diagnosis, row.recordNo, row.staffType].join(" ").toLowerCase().includes(normalized)
    );
  }, [search]);

  return (
    <section className="replica-medical-table-page" aria-label="就诊费用明细表">
      <TablePageHeader title="就诊费用明细表" badge="表3" extra={`共 ${visitRows.length} 条记录`} onLocalAction={onLocalAction} />
      <div className="replica-medical-detail-toolbar">
        <MedicalTableMeta mode="detail" />
        <label className="replica-medical-search">
          <span aria-hidden="true">⌕</span>
          <input value={search} onChange={(event) => onSearch(event.target.value)} placeholder="搜索姓名/诊断..." />
        </label>
      </div>
      <div className="replica-medical-total-strip">
        <span>合计：25 人次</span>
        <span>医疗费用总额：<strong>¥299,556</strong></span>
        <span>自费金额：¥89,867</span>
        <span>统筹支付：¥119,822</span>
        <span>公务员补助：¥28,603</span>
        <span>大额支付：¥22,358</span>
        <span>账户支付：¥38,906</span>
      </div>
      <div className="replica-medical-data-table is-wide">
        <table>
          <thead>
            <tr>
              <th>序号</th>
              <th>职工类型</th>
              <th>就诊记录号</th>
              <th>姓名</th>
              <th>身份证号码</th>
              <th>入院诊断</th>
              <th>医疗费用总额</th>
              <th>自费金额</th>
              <th>统筹支付</th>
              <th>公务员补助</th>
              <th>大额支付</th>
              <th>账户支付</th>
            </tr>
          </thead>
          <tbody>
            {filteredRows.map((row) => (
              <tr key={row.seq}>
                <td>{row.seq}</td>
                <td><span className="replica-medical-tag is-blue">{row.staffType}</span></td>
                <td className="is-link-number">{row.recordNo}</td>
                <td>{row.name}</td>
                <td>{row.idNo}</td>
                <td>{row.diagnosis}</td>
                <td className="is-link-number">{row.totalFee}</td>
                <td>{row.selfPay}</td>
                <td>{row.poolPay}</td>
                <td>{row.civilPay}</td>
                <td>{row.largePay}</td>
                <td>{row.accountPay}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="replica-medical-signatures">
        <span>主管领导：__________</span>
        <span>医保办负责人：__________</span>
        <span>制表人：__________</span>
      </div>
    </section>
  );
}

export default function MedicalAuditPage() {
  const [activeView, setActiveView] = useState<AuditView>("audit");
  const [activeTool, setActiveTool] = useState<ToolId>("audit");
  const [activeRule, setActiveRule] = useState<RuleFilter>("all");
  const [ruleSearch, setRuleSearch] = useState("");
  const [riskFilter, setRiskFilter] = useState<RiskFilter>("全部风险");
  const [deptFilter, setDeptFilter] = useState<DeptFilter>("全部科室");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("全部状态");
  const [page, setPage] = useState(1);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [drawerFindingId, setDrawerFindingId] = useState<string | null>(null);
  const [assistantDrawerOpen, setAssistantDrawerOpen] = useState(false);
  const [assistantContextFindingId, setAssistantContextFindingId] = useState<string | null>(null);
  const [assistantDraft, setAssistantDraft] = useState("");
  const [assistantMessages, setAssistantMessages] = useState<readonly AssistantMessage[]>(initialAssistantMessages);
  const [visitSearch, setVisitSearch] = useState("");
  const [notice, setNotice] = useState(buildReplicaLocalGateNotice({
    action: "打开医保审计页面",
    nextStep: "医保审计后端 API"
  }));

  const filteredFindings = useMemo(() => {
    return auditFindings.filter((finding) => {
      const toolMatched = activeTool === "audit" || activeTool === "rule" || finding.toolIds.includes(activeTool);
      const ruleMatched = ruleMatchesFilter(finding, activeRule);
      const riskMatched = riskFilter === "全部风险" || finding.risk === riskFilter;
      const deptMatched = deptFilter === "全部科室" || finding.department === deptFilter;
      const statusMatched = statusFilter === "全部状态" || finding.status === statusFilter;
      const searchText = ruleSearch.trim().toLowerCase();
      const searchMatched =
        !searchText ||
        [finding.id, finding.patient, finding.department, finding.rule, finding.dimension, finding.code, finding.knowledge]
          .join(" ")
          .toLowerCase()
          .includes(searchText);
      return toolMatched && ruleMatched && riskMatched && deptMatched && statusMatched && searchMatched;
    });
  }, [activeRule, activeTool, deptFilter, riskFilter, ruleSearch, statusFilter]);

  const totalPages = Math.max(1, Math.ceil(filteredFindings.length / 8));
  const currentPage = Math.min(page, totalPages);
  const pagedFindings = filteredFindings.slice((currentPage - 1) * 8, currentPage * 8);
  const drawerFinding = auditFindings.find((finding) => finding.id === drawerFindingId) ?? null;
  const assistantContextFinding =
    auditFindings.find((finding) => finding.id === assistantContextFindingId) ?? drawerFinding ?? null;
  const assistantContext = useMemo<AssistantContext>(() => ({
    finding: assistantContextFinding,
    activeView,
    activeRule,
    riskFilter,
    deptFilter,
    statusFilter,
    filteredCount: filteredFindings.length,
    selectedCount: selectedIds.size
  }), [
    activeRule,
    activeView,
    assistantContextFinding,
    deptFilter,
    filteredFindings.length,
    riskFilter,
    selectedIds.size,
    statusFilter
  ]);

  function recordLocalAction(action: string) {
    setNotice(buildReplicaLocalGateNotice({
      action,
      nextStep: "医保审计后端 API"
    }));
  }

  function resetAuditPage() {
    setDrawerFindingId(null);
    setAssistantContextFindingId(null);
    setSelectedIds(new Set());
    setPage(1);
  }

  function handleToolChange(tool: ToolId) {
    setActiveTool(tool);
    setActiveView("audit");
    setAssistantDrawerOpen(false);
    resetAuditPage();
    setNotice(`${toolModules.find((item) => item.id === tool)?.label ?? "工具"}已切换为当前本地筛选视图。`);
  }

  function handleRuleChange(rule: RuleFilter) {
    setActiveRule(rule);
    resetAuditPage();
  }

  function handleOpenAssistant() {
    if (assistantDrawerOpen) {
      setAssistantDrawerOpen(false);
      return;
    }
    const selectedId = selectedIds.size === 1 ? Array.from(selectedIds)[0] : null;
    setAssistantContextFindingId(drawerFindingId ?? selectedId);
    setDrawerFindingId(null);
    setAssistantDrawerOpen(true);
    setNotice(buildReplicaLocalGateNotice({
      action: "打开 AI 审计助手",
      nextStep: "医保审计后端与 AI provider 授权"
    }));
  }

  function submitAssistantPrompt(prompt: string) {
    const text = prompt.trim();
    if (!text) return;
    const reply = buildAssistantReply(text, assistantContext);
    setAssistantMessages((current) => [
      ...current,
      { id: `user-${current.length + 1}`, role: "user", text },
      { id: `assistant-${current.length + 2}`, role: "assistant", text: reply }
    ]);
    setAssistantDraft("");
    setNotice(buildReplicaLocalGateNotice({
      action: "生成 AI 审计建议",
      nextStep: "医保审计后端与 AI provider 授权"
    }));
  }

  function handleToggleRow(id: string) {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function handleTogglePage() {
    setSelectedIds((current) => {
      const ids = pagedFindings.map((finding) => finding.id);
      const allSelected = ids.length > 0 && ids.every((id) => current.has(id));
      const next = new Set(current);
      if (allSelected) ids.forEach((id) => next.delete(id));
      else ids.forEach((id) => next.add(id));
      return next;
    });
  }

  return (
    <main className="replica-medical-page" aria-label="医保审计工作台">
      <h1 className="replica-medical-sr-title">医保审计</h1>
      <MedicalStatusRail activeTool={activeTool} onToolChange={handleToolChange} />
      <RuleNavigator
        activeRule={activeRule}
        ruleSearch={ruleSearch}
        onRuleChange={handleRuleChange}
        onRuleSearch={(value) => {
          setRuleSearch(value);
          setPage(1);
        }}
      />
      <section className={`replica-medical-content ${drawerFinding || assistantDrawerOpen ? "has-drawer" : ""}`}>
        <div className="replica-medical-main">
          <MedicalAuditPageTabs
            activeView={activeView}
            onViewChange={(view) => {
              setActiveView(view);
              setDrawerFindingId(null);
              setAssistantDrawerOpen(false);
      setNotice(`${viewTabs.find((item) => item.id === view)?.label ?? "子页面"}已切换。`);
            }}
          />
          <LocalActionNotice text={notice} />
          {activeView === "audit" ? (
            <SmartAuditView
              activeRule={activeRule}
              riskFilter={riskFilter}
              deptFilter={deptFilter}
              statusFilter={statusFilter}
              rows={filteredFindings}
              pagedRows={pagedFindings}
              page={currentPage}
              totalPages={totalPages}
              selectedIds={selectedIds}
              selectedFindingId={drawerFindingId}
              onRuleTabChange={handleRuleChange}
              onRiskChange={(value) => {
                setRiskFilter(value);
                resetAuditPage();
              }}
              onDeptChange={(value) => {
                setDeptFilter(value);
                resetAuditPage();
              }}
              onStatusChange={(value) => {
                setStatusFilter(value);
                resetAuditPage();
              }}
              onToggleRow={handleToggleRow}
              onTogglePage={handleTogglePage}
              onOpenFinding={(id) => {
                setDrawerFindingId(id);
                setAssistantContextFindingId(id);
                setAssistantDrawerOpen(false);
              }}
              onPageChange={setPage}
              onLocalAction={recordLocalAction}
            />
          ) : null}
          {activeView === "table1" ? <FeeSummaryTable onLocalAction={recordLocalAction} /> : null}
          {activeView === "table2" ? <FeeCategoryTable onLocalAction={recordLocalAction} /> : null}
          {activeView === "table3" ? (
            <VisitDetailTable search={visitSearch} onSearch={setVisitSearch} onLocalAction={recordLocalAction} />
          ) : null}
        </div>
        {drawerFinding ? (
          <FindingDrawer finding={drawerFinding} onClose={() => setDrawerFindingId(null)} onLocalAction={recordLocalAction} />
        ) : null}
        {assistantDrawerOpen ? (
          <MedicalAiDrawer
            context={assistantContext}
            messages={assistantMessages}
            draft={assistantDraft}
            onDraftChange={setAssistantDraft}
            onQuickAction={submitAssistantPrompt}
            onSubmit={() => submitAssistantPrompt(assistantDraft)}
            onClose={() => setAssistantDrawerOpen(false)}
            onLocalAction={recordLocalAction}
          />
        ) : null}
        <MedicalAiAssistantButton
          isOpen={assistantDrawerOpen}
          isShifted={Boolean(drawerFinding || assistantDrawerOpen)}
          onClick={handleOpenAssistant}
        />
      </section>
    </main>
  );
}
