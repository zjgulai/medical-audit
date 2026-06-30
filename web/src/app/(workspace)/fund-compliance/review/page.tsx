"use client";

import { FormEvent, useMemo, useState } from "react";

import { StatusPill } from "@/components/ui/status-pill";
import { auditTableTemplates, type AuditTableTemplate } from "@/lib/portal-data";

type ReviewCase = {
  readonly id: string;
  readonly patient: string;
  readonly department: string;
  readonly rule: string;
  readonly amount: string;
  readonly risk: "高风险" | "中风险" | "低风险";
  readonly status: "待初审" | "待复核" | "已驳回";
};

const workflowTabs = ["单据审查", "费用表单", "规则复核", "底稿输出"] as const;

const reviewCases: readonly ReviewCase[] = [
  { id: "20251203001", patient: "王**（男，52岁）", department: "骨科", rule: "药品区分性别使用", amount: "¥1,240.00", risk: "高风险", status: "待初审" },
  { id: "20251203005", patient: "李**（女，34岁）", department: "内科", rule: "药品限适应症", amount: "¥8,600.00", risk: "高风险", status: "待初审" },
  { id: "20251202018", patient: "张**（男，67岁）", department: "心内科", rule: "药品限工伤保险", amount: "¥320.00", risk: "中风险", status: "待复核" },
  { id: "20251201042", patient: "周**（男，72岁）", department: "内科", rule: "DIP 分值高套", amount: "¥12,500.00", risk: "高风险", status: "待复核" },
  { id: "20251129012", patient: "马**（女，61岁）", department: "外科", rule: "诊疗项目超标准收费", amount: "¥85.00", risk: "低风险", status: "已驳回" }
];

const ruleGroups = [
  { name: "药品使用", count: 36, items: ["药品限适应症", "药品限工伤保险", "药品限生育保险"] },
  { name: "DIP/DRG", count: 18, items: ["DIP 分值高套", "DRG 分组错误", "重复结算"] },
  { name: "价格合规", count: 24, items: ["诊疗项目超标准收费", "耗材价格异常", "自费转基金支付"] },
  { name: "身份与待遇", count: 12, items: ["待遇资格异常", "异地结算异常", "重复参保"] }
] as const;

function riskTone(risk: ReviewCase["risk"]): "danger" | "warning" | "success" {
  if (risk === "高风险") return "danger";
  if (risk === "中风险") return "warning";
  return "success";
}

function splitCustomFields(value: string): readonly string[] {
  return value
    .split(/[\n,，、]/)
    .map((field) => field.trim())
    .filter(Boolean)
    .slice(0, 24);
}

export default function FundComplianceReviewPage() {
  const [activeWorkflow, setActiveWorkflow] = useState<(typeof workflowTabs)[number]>("单据审查");
  const [selectedTemplateId, setSelectedTemplateId] = useState<AuditTableTemplate["id"]>(
    auditTableTemplates[0]?.id ?? ""
  );
  const [customForms, setCustomForms] = useState<readonly AuditTableTemplate[]>([]);
  const [customName, setCustomName] = useState("门诊慢病费用复核表");
  const [customFields, setCustomFields] = useState("费用分类\n人次\n医疗总费用\n统筹支付\n疑点说明");

  const templates = useMemo(() => [...auditTableTemplates, ...customForms], [customForms]);
  const selectedTemplate = templates.find((template) => template.id === selectedTemplateId) ?? templates[0];

  function createCustomForm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const fields = splitCustomFields(customFields);
    if (!customName.trim() || fields.length === 0) return;
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
          </div>
          <div className="flex max-w-full flex-nowrap gap-1 overflow-x-auto rounded-full border border-[var(--audit-line)] bg-[var(--audit-surface-muted)] p-1" role="tablist" aria-label="专题流程">
            {workflowTabs.map((tab) => (
              <button
                key={tab}
                type="button"
                role="tab"
                aria-selected={activeWorkflow === tab}
                onClick={() => setActiveWorkflow(tab)}
                className={`audit-focus-ring shrink-0 rounded-full px-3 py-1.5 text-sm font-semibold ${
                  activeWorkflow === tab ? "bg-[var(--audit-primary)] text-white" : "text-[var(--audit-ink-muted)] hover:bg-white"
                }`}
              >
                {tab}
              </button>
            ))}
          </div>
        </div>
      </section>

      {activeWorkflow === "单据审查" ? (
        <section className="audit-panel min-w-0 p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="audit-kicker">疑点单据</p>
              <h2 className="audit-section-title">待处理清单</h2>
            </div>
            <button className="audit-focus-ring audit-btn audit-btn-primary min-h-9 px-3 py-1.5" type="button">
              发起复核
            </button>
          </div>
          <div className="audit-table-shell mt-4">
            <table className="audit-table min-w-[42rem]">
              <thead>
                <tr>
                  <th>单据号</th>
                  <th>患者</th>
                  <th>问题</th>
                  <th>金额</th>
                  <th>风险</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--audit-line-soft)]">
                {reviewCases.map((item) => (
                  <tr key={item.id}>
                    <td className="font-mono font-semibold">{item.id}</td>
                    <td>
                      <div className="font-semibold text-[var(--audit-ink)]">{item.patient}</div>
                      <div className="audit-meta mt-1">{item.department}</div>
                    </td>
                    <td className="font-semibold text-[var(--audit-ink)]">{item.rule}</td>
                    <td className="font-mono font-semibold">{item.amount}</td>
                    <td>
                      <StatusPill tone={riskTone(item.risk)}>{item.risk}</StatusPill>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      {activeWorkflow === "费用表单" ? (
        <section className="audit-panel min-w-0 p-5" aria-labelledby="template-preview-title">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="audit-kicker">费用表单</p>
              <h2 id="template-preview-title" className="audit-section-title">三份模板与自建表单</h2>
            </div>
            <details>
              <summary className="audit-focus-ring cursor-pointer list-none rounded-full border border-[var(--audit-line)] bg-white px-3 py-1.5 text-sm font-semibold text-[var(--audit-primary)] [&::-webkit-details-marker]:hidden">
                新建表单
              </summary>
              <form className="absolute z-10 mt-2 w-[min(22rem,calc(100vw-2rem))] rounded-[var(--audit-radius-lg)] border border-[var(--audit-line)] bg-white p-4 shadow-[0_16px_36px_rgb(23_62_105/0.16)]" onSubmit={createCustomForm}>
                <label className="block">
                  <span className="audit-label">表单名称</span>
                  <input className="audit-focus-ring audit-input mt-2 px-3 py-2" value={customName} onChange={(event) => setCustomName(event.target.value)} />
                </label>
                <label className="mt-4 block">
                  <span className="audit-label">字段列表</span>
                  <textarea className="audit-focus-ring audit-input mt-2 min-h-28 resize-y px-3 py-2" value={customFields} onChange={(event) => setCustomFields(event.target.value)} />
                </label>
                <button className="audit-focus-ring audit-btn audit-btn-secondary mt-4 w-full" type="submit">创建</button>
              </form>
            </details>
          </div>

          <div className="mt-4 flex gap-2 overflow-x-auto pb-1" role="tablist" aria-label="费用表单模板">
            {templates.map((template) => (
              <button
                key={template.id}
                type="button"
                role="tab"
                aria-selected={selectedTemplateId === template.id}
                onClick={() => setSelectedTemplateId(template.id)}
                className={`audit-focus-ring shrink-0 rounded-full border px-3 py-1.5 text-sm font-semibold ${
                  selectedTemplateId === template.id
                    ? "border-[var(--audit-primary-line)] bg-[var(--audit-primary-soft)] text-[var(--audit-primary)]"
                    : "border-[var(--audit-line)] bg-white text-[var(--audit-ink-muted)] hover:bg-[var(--audit-surface-muted)]"
                }`}
              >
                {template.shortName}
              </button>
            ))}
          </div>
          {selectedTemplate ? <TemplatePreview template={selectedTemplate} /> : null}
        </section>
      ) : null}

      {activeWorkflow === "规则复核" ? (
        <section className="audit-panel p-5">
          <p className="audit-kicker">专题规则</p>
          <h2 className="audit-section-title mt-1">规则分类</h2>
          <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            {ruleGroups.map((group) => (
              <section key={group.name} className="rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-white p-3">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="audit-card-title">{group.name}</h3>
                  <span className="audit-meta">{group.count} 条</span>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {group.items.map((item) => (
                    <span key={item} className="rounded-full border border-[var(--audit-line-soft)] px-2.5 py-1 text-xs font-semibold text-[var(--audit-ink-muted)]">{item}</span>
                  ))}
                </div>
              </section>
            ))}
          </div>
        </section>
      ) : null}

      {activeWorkflow === "底稿输出" ? (
        <section className="audit-panel p-5">
          <p className="audit-kicker">底稿输出</p>
          <h2 className="audit-section-title mt-1">待确认后生成底稿</h2>
          <p className="audit-copy mt-2 max-w-2xl">仅纳入已人工复核的疑点，未确认内容继续保留在草稿区。</p>
          <button className="audit-focus-ring audit-btn audit-btn-primary mt-4" type="button">生成草稿</button>
        </section>
      ) : null}
    </main>
  );
}

function TemplatePreview({ template }: { readonly template: AuditTableTemplate }) {
  const preview = templatePreviewRows(template);
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
      <p className="audit-label mt-4">表样预览</p>
      <div className="audit-table-shell mt-2">
        <table className="audit-table min-w-[38rem]">
          <thead>
            <tr>
              {preview.columns.map((field) => <th key={field}>{field}</th>)}
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--audit-line-soft)]">
            {preview.rows.map((row, index) => (
              <tr key={`${template.id}-${index}`}>
                {preview.columns.map((field) => <td key={field}>{row[field] ?? "待填"}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <details className="mt-4">
        <summary className="audit-focus-ring cursor-pointer list-none rounded-full border border-[var(--audit-line)] bg-[var(--audit-surface-muted)] px-3 py-1.5 text-sm font-semibold text-[var(--audit-ink-muted)] [&::-webkit-details-marker]:hidden">
          查看全部字段
        </summary>
        <div className="mt-3 flex flex-wrap gap-2">
          {template.expectedColumns.map((field) => (
            <span key={field} className="rounded-[var(--audit-radius-sm)] border border-[var(--audit-line-soft)] bg-[var(--audit-surface-muted)] px-2 py-1.5 text-sm text-[var(--audit-ink-muted)]">{field}</span>
          ))}
        </div>
      </details>
    </div>
  );
}

function templatePreviewRows(template: AuditTableTemplate): {
  readonly columns: readonly string[];
  readonly rows: readonly Record<string, string>[];
} {
  if (template.id === "visit-expense-detail") {
    const columns = ["就诊记录号", "姓名", "入院诊断", "医疗费用总额", "自费金额", "统筹支付"];
    return {
      columns,
      rows: [
        { 就诊记录号: "V20251203001", 姓名: "王**", 入院诊断: "骨折术后", 医疗费用总额: "¥1,240.00", 自费金额: "¥120.00", 统筹支付: "¥880.00" }
      ]
    };
  }
  if (template.id === "medical-expense-category-summary") {
    const columns = ["费用分类", "人次", "人数", "平均费用", "医疗总费用", "统筹支付"];
    return {
      columns,
      rows: [
        { 费用分类: "药品费", 人次: "126", 人数: "98", 平均费用: "¥312.40", 医疗总费用: "¥39,362.40", 统筹支付: "¥28,440.00" }
      ]
    };
  }
  const columns = ["费用分类", "人次", "人数", "医疗总费用", "现金支付", "记账合计"];
  return {
    columns,
    rows: [
      { 费用分类: "门诊", 人次: "420", 人数: "318", 医疗总费用: "¥82,430.00", 现金支付: "¥9,860.00", 记账合计: "¥72,570.00" }
    ]
  };
}
