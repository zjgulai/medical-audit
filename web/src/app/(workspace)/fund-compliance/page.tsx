"use client";

import Link from "next/link";

import { StatusPill } from "@/components/ui/status-pill";

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

const topicMetrics = [
  { label: "待复核疑点", value: "207", tone: "text-red-600", detail: "高风险 89 条" },
  { label: "涉及金额", value: "¥128,450", tone: "text-blue-600", detail: "药品类占比最高" },
  { label: "待补材料", value: "34", tone: "text-amber-600", detail: "需科室补证" }
] as const;

const topicModules = [
  {
    title: "单据审查",
    description: "查看待处理疑点、证据链和复核动作。",
    href: "/fund-compliance/review",
    action: "进入审查"
  },
  {
    title: "费用表单",
    description: "按三张医保费用模板创建、预览和扩展表单。",
    href: "/fund-compliance/review",
    action: "查看表单"
  },
  {
    title: "规则复核",
    description: "核对药品、DIP/DRG、价格和身份待遇规则。",
    href: "/fund-compliance/review",
    action: "复核规则"
  }
] as const;

const topicRuleGroups = [
  { title: "政策类", count: 58, items: ["药品限适应症", "药品限工伤保险", "目录限制条件"] },
  { title: "管理类", count: 23, items: ["信息数据篡改", "结算时间异常", "审批材料缺失"] },
  { title: "医疗类", count: 31, items: ["诊疗项目超标准", "重复收费", "自费转基金"] },
  { title: "DIP/DRG", count: 34, items: ["DIP 分值高套", "DRG 分组错误", "病案首页偏差"] }
] as const;

function riskTone(risk: AuditCase["risk"]): "danger" | "warning" | "success" {
  if (risk === "高风险") {
    return "danger";
  }
  if (risk === "中风险") {
    return "warning";
  }
  return "success";
}

export default function FundCompliancePage() {
  const topCases = auditCases.slice(0, 4);

  return (
    <main className="space-y-5">
      <section className="audit-panel p-5 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-3xl">
            <p className="audit-kicker">医保基金审计专题</p>
            <h1 className="audit-page-title">医保基金使用合规专项自查</h1>
            <p className="audit-copy mt-2 max-w-2xl">用于查看住院部专项审计的疑点、表单和规则复核进度。</p>
            <p className="audit-meta mt-3">2025 年 Q4 住院部专项审计 · HIS、医保结算、病案材料</p>
          </div>
          <Link className="audit-focus-ring audit-btn audit-btn-primary" href="/fund-compliance/review">
            进入审查
          </Link>
        </div>
        <div className="mt-5 grid gap-3 md:grid-cols-3">
          {topicMetrics.map((metric) => (
            <div key={metric.label} className="rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-[var(--audit-surface-muted)] p-4">
              <p className="audit-meta">{metric.label}</p>
              <p className={`mt-1 audit-metric-value ${metric.tone}`}>{metric.value}</p>
              <p className="audit-meta mt-1">{metric.detail}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="audit-panel p-4 sm:p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="audit-kicker">工作入口</p>
            <h2 className="audit-section-title mt-1">从审查开始</h2>
          </div>
          <Link className="audit-focus-ring audit-btn audit-btn-secondary min-h-9 px-3 py-1.5" href="/fund-compliance/review">
            查看全部疑点
          </Link>
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          {topicModules.map((module) => (
            <Link
              key={module.title}
              href={module.href}
              className="audit-focus-ring rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-white p-4 transition hover:border-[var(--audit-primary-line)]"
            >
              <h3 className="audit-card-title">{module.title}</h3>
              <p className="audit-copy mt-2">{module.description}</p>
              <span className="mt-3 inline-flex text-sm font-semibold text-[var(--audit-primary)]">{module.action}</span>
            </Link>
          ))}
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-[18rem_minmax(0,1fr)]">
        <aside className="audit-panel p-4">
          <div className="flex items-center justify-between gap-2">
            <div>
              <p className="audit-kicker">规则分类</p>
              <h2 className="audit-card-title mt-1">审计口径</h2>
            </div>
            <StatusPill tone="info">146 条</StatusPill>
          </div>
          <div className="mt-4 space-y-3">
            {topicRuleGroups.map((group) => (
              <section key={group.title} className="rounded-[var(--audit-radius-md)] border border-[var(--audit-line-soft)] bg-[var(--audit-surface-muted)] p-3">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="audit-compact-title">{group.title}</h3>
                  <span className="audit-meta">{group.count}</span>
                </div>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {group.items.map((item) => (
                    <span key={item} className="rounded-full bg-white px-2 py-1 text-xs font-medium text-[var(--audit-ink-muted)]">
                      {item}
                    </span>
                  ))}
                </div>
              </section>
            ))}
          </div>
        </aside>

        <section className="min-w-0 space-y-4">
          <section className="audit-panel min-w-0 p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="audit-kicker">今日重点</p>
                <h2 className="audit-section-title">待复核疑点</h2>
              </div>
              <Link className="audit-focus-ring audit-btn audit-btn-secondary min-h-9 px-3 py-1.5" href="/fund-compliance/review">
                查看全部
              </Link>
            </div>
            <div className="audit-table-shell mt-4">
              <table className="audit-table min-w-[38rem]">
                <thead>
                  <tr>
                    <th>单据号</th>
                    <th>问题</th>
                    <th>金额</th>
                    <th>风险</th>
                    <th>状态</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--audit-line-soft)]">
                  {topCases.map((item) => (
                    <tr key={item.id}>
                      <td className="font-mono font-semibold">{item.id}</td>
                      <td>
                        <div className="font-semibold text-[var(--audit-ink)]">{item.rule}</div>
                        <div className="audit-meta mt-1">
                          {item.patient} · {item.department}
                        </div>
                      </td>
                      <td className="font-mono font-semibold">{item.amount}</td>
                      <td>
                        <StatusPill tone={riskTone(item.risk)}>{item.risk}</StatusPill>
                      </td>
                      <td>{item.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </section>
      </section>
    </main>
  );
}
