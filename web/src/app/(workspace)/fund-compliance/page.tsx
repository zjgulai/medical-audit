"use client";

import { FormEvent, useMemo, useState } from "react";

import { StatusPill } from "@/components/ui/status-pill";
import { auditTableTemplates, type AuditTableTemplate } from "@/lib/portal-data";

type AuditCase = {
  readonly id: string;
  readonly patient: string;
  readonly department: string;
  readonly dimension: string;
  readonly rule: string;
  readonly amount: string;
  readonly risk: "高风险" | "中风险" | "低风险";
  readonly status: "待初审" | "待复核" | "已整改" | "已驳回";
  readonly time: string;
};

type RuleGroup = {
  readonly name: string;
  readonly count: number;
  readonly items: readonly string[];
};

const ruleGroups: readonly RuleGroup[] = [
  {
    name: "药品使用",
    count: 36,
    items: ["药品限适应症", "药品限工伤保险", "药品限生育保险"]
  },
  {
    name: "DIP/DRG",
    count: 18,
    items: ["DIP 分值高套", "DRG 分组错误", "重复结算"]
  },
  {
    name: "价格合规",
    count: 24,
    items: ["诊疗项目超标准收费", "耗材价格异常", "自费转基金支付"]
  },
  {
    name: "身份与待遇",
    count: 12,
    items: ["待遇资格异常", "异地结算异常", "重复参保"]
  }
];

const auditCases: readonly AuditCase[] = [
  {
    id: "20251203001",
    patient: "王**（男，52岁）",
    department: "骨科",
    dimension: "政策类-药品",
    rule: "药品区分性别使用",
    amount: "¥1,240.00",
    risk: "高风险",
    status: "待初审",
    time: "2025-12-03"
  },
  {
    id: "20251203005",
    patient: "李**（女，34岁）",
    department: "内科",
    dimension: "政策类-药品",
    rule: "药品限适应症",
    amount: "¥8,600.00",
    risk: "高风险",
    status: "待初审",
    time: "2025-12-03"
  },
  {
    id: "20251202018",
    patient: "张**（男，67岁）",
    department: "心内科",
    dimension: "政策类-药品",
    rule: "药品限工伤保险",
    amount: "¥320.00",
    risk: "中风险",
    status: "待复核",
    time: "2025-12-02"
  },
  {
    id: "20251201042",
    patient: "周**（男，72岁）",
    department: "内科",
    dimension: "DIP/DRG",
    rule: "DIP分值高套",
    amount: "¥12,500.00",
    risk: "高风险",
    status: "待复核",
    time: "2025-12-01"
  },
  {
    id: "20251129012",
    patient: "马**（女，61岁）",
    department: "外科",
    dimension: "价格合规",
    rule: "诊疗项目超标准收费",
    amount: "¥85.00",
    risk: "低风险",
    status: "已驳回",
    time: "2025-11-29"
  }
];

const workflowTabs = ["单据审查", "费用表单", "规则复核", "底稿输出"] as const;

function splitCustomFields(value: string): readonly string[] {
  return value
    .split(/[\n,，、]/)
    .map((field) => field.trim())
    .filter((field) => field.length > 0)
    .slice(0, 24);
}

function riskTone(risk: AuditCase["risk"]): "danger" | "warning" | "success" {
  if (risk === "高风险") {
    return "danger";
  }
  if (risk === "中风险") {
    return "warning";
  }
  return "success";
}

function statusTone(status: AuditCase["status"]): "info" | "warning" | "success" | "neutral" {
  if (status === "待初审") {
    return "info";
  }
  if (status === "待复核") {
    return "warning";
  }
  if (status === "已整改") {
    return "success";
  }
  return "neutral";
}

export default function FundCompliancePage() {
  const [selectedCaseId, setSelectedCaseId] = useState(auditCases[0]?.id ?? "");
  const [selectedTemplateId, setSelectedTemplateId] = useState<AuditTableTemplate["id"]>(
    auditTableTemplates[0]?.id ?? ""
  );
  const [customForms, setCustomForms] = useState<readonly AuditTableTemplate[]>([]);
  const [customName, setCustomName] = useState("门诊慢病费用复核表");
  const [customFields, setCustomFields] = useState("费用分类\n人次\n医疗总费用\n统筹支付\n疑点说明");

  const templates = useMemo(() => [...auditTableTemplates, ...customForms], [customForms]);
  const selectedCase = auditCases.find((item) => item.id === selectedCaseId) ?? auditCases[0];
  const selectedTemplate = templates.find((template) => template.id === selectedTemplateId) ?? templates[0];

  function createCustomForm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const fields = splitCustomFields(customFields);
    if (!customName.trim() || fields.length === 0) {
      return;
    }

    const template: AuditTableTemplate = {
      id: `custom-${Date.now()}`,
      name: customName.trim(),
      shortName: "自建",
      fileName: "新建表单",
      sheetName: "自定义",
      auditUse: "用于后续按项目需要扩展医保费用复核表单。",
      expectedColumns: fields,
      keyChecks: ["字段是否完整", "金额口径是否一致", "能否追溯到就诊明细"],
      analysisRequest: `按 ${fields.slice(0, 4).join("、")} 复核医保费用异常。`
    };
    setCustomForms((current) => [...current, template]);
    setSelectedTemplateId(template.id);
  }

  return (
    <main className="space-y-5">
      <section className="audit-panel p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="audit-kicker">医保基金使用合规</p>
            <h1 className="audit-page-title">专题审计工作台</h1>
            <p className="audit-copy mt-2 max-w-3xl">
              从疑点单据进入规则、表单和底稿，不影响今日工作台的项目概览。
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {workflowTabs.map((tab, index) => (
              <button
                key={tab}
                type="button"
                className={`audit-focus-ring rounded-full px-3 py-1.5 text-sm font-semibold ${
                  index === 0
                    ? "bg-[var(--audit-primary)] text-white"
                    : "border border-[var(--audit-line)] bg-white text-[var(--audit-ink-muted)]"
                }`}
              >
                {tab}
              </button>
            ))}
          </div>
        </div>

        <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <MetricCard label="待初审单据" value="3" />
          <MetricCard label="高风险疑点" value="4" />
          <MetricCard label="待复核金额" value="¥24,660" />
          <MetricCard label="可用表单" value={`${templates.length} 份`} />
        </div>
      </section>

      <section className="grid min-w-0 gap-4 xl:grid-cols-[17rem_minmax(0,1fr)_19rem]">
        <aside className="audit-panel-rail min-w-0 p-5">
          <h2 className="audit-section-title">专题规则</h2>
          <div className="mt-4 space-y-3">
            {ruleGroups.map((group) => (
              <section key={group.name} className="rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-white p-3">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="audit-card-title">{group.name}</h3>
                  <span className="audit-meta">{group.count} 条</span>
                </div>
                <div className="mt-3 space-y-2">
                  {group.items.map((item) => (
                    <button
                      key={item}
                      type="button"
                      className="audit-focus-ring block w-full rounded-[var(--audit-radius-sm)] px-2 py-1.5 text-left text-sm text-[var(--audit-ink-muted)] hover:bg-[var(--audit-primary-soft)] hover:text-[var(--audit-primary)]"
                    >
                      {item}
                    </button>
                  ))}
                </div>
              </section>
            ))}
          </div>
        </aside>

        <section className="audit-panel min-w-0 p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="audit-kicker">疑点单据</p>
              <h2 className="audit-section-title">待处理清单</h2>
            </div>
            <div className="flex flex-wrap gap-2">
              <button className="audit-focus-ring audit-btn audit-btn-secondary min-h-9 px-3 py-1.5" type="button">
                导出清单
              </button>
              <button className="audit-focus-ring audit-btn audit-btn-primary min-h-9 px-3 py-1.5" type="button">
                发起复核
              </button>
            </div>
          </div>

          <div className="audit-table-shell mt-4">
            <table className="audit-table min-w-[56rem]">
              <thead>
                <tr>
                  <th>单据号</th>
                  <th>患者</th>
                  <th>科室</th>
                  <th>审计维度</th>
                  <th>违规规则</th>
                  <th>涉及金额</th>
                  <th>风险</th>
                  <th>状态</th>
                  <th>时间</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--audit-line-soft)]">
                {auditCases.map((item) => (
                  <tr
                    key={item.id}
                    className={selectedCaseId === item.id ? "bg-[var(--audit-primary-soft)]" : ""}
                    onClick={() => setSelectedCaseId(item.id)}
                  >
                    <td className="font-mono font-semibold text-[var(--audit-ink)]">{item.id}</td>
                    <td>{item.patient}</td>
                    <td>{item.department}</td>
                    <td>
                      <span className="audit-chip audit-chip-info">{item.dimension}</span>
                    </td>
                    <td>{item.rule}</td>
                    <td className="font-mono font-semibold">{item.amount}</td>
                    <td>
                      <StatusPill tone={riskTone(item.risk)}>{item.risk}</StatusPill>
                    </td>
                    <td>
                      <StatusPill tone={statusTone(item.status)}>{item.status}</StatusPill>
                    </td>
                    <td>{item.time}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <section className="mt-5" aria-labelledby="template-preview-title">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="audit-kicker">费用表单</p>
                <h2 id="template-preview-title" className="audit-section-title">
                  三份模板与自建表单
                </h2>
              </div>
              <StatusPill tone="info">{selectedTemplate?.shortName ?? "模板"}</StatusPill>
            </div>

            <div className="mt-4 grid gap-3 lg:grid-cols-3">
              {templates.map((template) => (
                <button
                  key={template.id}
                  type="button"
                  onClick={() => setSelectedTemplateId(template.id)}
                  className={`audit-focus-ring rounded-[var(--audit-radius-md)] border p-3 text-left transition ${
                    selectedTemplateId === template.id
                      ? "border-[var(--audit-primary-line)] bg-[var(--audit-primary-soft)]"
                      : "border-[var(--audit-line)] bg-white hover:bg-[var(--audit-surface-muted)]"
                  }`}
                >
                  <span className="audit-meta">{template.shortName} · {template.sheetName}</span>
                  <span className="mt-1 block font-semibold text-[var(--audit-ink)]">{template.name}</span>
                  <span className="mt-2 line-clamp-2 block text-xs leading-5 text-[var(--audit-ink-muted)]">
                    {template.auditUse}
                  </span>
                </button>
              ))}
            </div>

            {selectedTemplate ? <TemplatePreview template={selectedTemplate} /> : null}
          </section>
        </section>

        <aside className="min-w-0 space-y-4">
          {selectedCase ? (
            <section className="audit-panel-rail p-5">
              <p className="audit-kicker">单据详情</p>
              <h2 className="audit-section-title mt-2">{selectedCase.id}</h2>
              <div className="mt-4 space-y-3 text-sm">
                <DetailRow label="患者" value={selectedCase.patient} />
                <DetailRow label="规则" value={selectedCase.rule} />
                <DetailRow label="金额" value={selectedCase.amount} />
                <DetailRow label="处理状态" value={selectedCase.status} />
              </div>
              <div className="mt-5 grid gap-2">
                <button className="audit-focus-ring audit-btn audit-btn-primary" type="button">
                  进入复核
                </button>
                <button className="audit-focus-ring audit-btn audit-btn-neutral" type="button">
                  加入底稿
                </button>
              </div>
            </section>
          ) : null}

          <form className="audit-panel-rail p-5" onSubmit={createCustomForm}>
            <p className="audit-kicker">创建表单</p>
            <h2 className="audit-section-title mt-2">扩展费用模板</h2>
            <label className="mt-4 block">
              <span className="audit-label">表单名称</span>
              <input
                className="audit-focus-ring audit-input mt-2 px-3 py-2"
                value={customName}
                onChange={(event) => setCustomName(event.target.value)}
              />
            </label>
            <label className="mt-4 block">
              <span className="audit-label">字段列表</span>
              <textarea
                className="audit-focus-ring audit-input mt-2 min-h-28 resize-y px-3 py-2"
                value={customFields}
                onChange={(event) => setCustomFields(event.target.value)}
              />
            </label>
            <button className="audit-focus-ring audit-btn audit-btn-secondary mt-4 w-full" type="submit">
              新建表单
            </button>
          </form>
        </aside>
      </section>
    </main>
  );
}

function MetricCard({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <div className="rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-white p-4">
      <p className="audit-meta">{label}</p>
      <p className="audit-metric-value-sm mt-1">{value}</p>
    </div>
  );
}

function DetailRow({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-[var(--audit-line-soft)] pb-2">
      <span className="audit-meta">{label}</span>
      <span className="max-w-[12rem] text-right font-semibold text-[var(--audit-ink)]">{value}</span>
    </div>
  );
}

function TemplatePreview({ template }: { readonly template: AuditTableTemplate }) {
  const isDetail = template.id === "visit-expense-detail";
  return (
    <div className="mt-4 rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-white p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="audit-card-title">{template.name}</h3>
          <p className="audit-meta mt-1">{template.fileName} / {template.sheetName}</p>
        </div>
        <StatusPill tone="success">{isDetail ? "明细表" : "汇总表"}</StatusPill>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        <label className="block">
          <span className="audit-meta">定点医疗机构</span>
          <input className="audit-input mt-1 px-3 py-2" readOnly value="待填写" />
        </label>
        <label className="block">
          <span className="audit-meta">统计日期</span>
          <input className="audit-input mt-1 px-3 py-2" readOnly value="____ 至 ____" />
        </label>
        <label className="block">
          <span className="audit-meta">单位</span>
          <input className="audit-input mt-1 px-3 py-2" readOnly value="元" />
        </label>
      </div>

      <div className={`mt-4 grid gap-2 ${isDetail ? "sm:grid-cols-2 xl:grid-cols-3" : "sm:grid-cols-3 xl:grid-cols-4"}`}>
        {template.expectedColumns.map((field) => (
          <label key={field} className="block rounded-[var(--audit-radius-sm)] border border-[var(--audit-line-soft)] bg-[var(--audit-surface-muted)] p-2">
            <span className="audit-meta">{field}</span>
            <input className="audit-input mt-1 px-2 py-1.5 text-sm" readOnly value="" />
          </label>
        ))}
      </div>

      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        <Checklist title="核验重点" items={template.keyChecks} />
        <Checklist title="分析要求" items={[template.analysisRequest]} />
      </div>
    </div>
  );
}

function Checklist({ title, items }: { readonly title: string; readonly items: readonly string[] }) {
  return (
    <div className="rounded-[var(--audit-radius-sm)] border border-[var(--audit-line-soft)] bg-[var(--audit-surface-muted)] p-3">
      <h4 className="audit-compact-title">{title}</h4>
      <ul className="mt-2 space-y-1.5">
        {items.map((item) => (
          <li key={item} className="audit-copy text-sm">
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}
