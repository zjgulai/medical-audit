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
  { label: "本月疑点总数", value: "207", tone: "text-red-600", detail: "高风险 89 | 中风险 68" },
  { label: "涉及金额", value: "¥128,450", tone: "text-blue-600", detail: "药品类 ¥68,200" },
  { label: "DIP 分值异常", value: "34", tone: "text-amber-600", detail: "高套嫌疑 12" },
  { label: "整改率", value: "13.5%", tone: "text-emerald-600", detail: "待复核 34" }
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
  },
  {
    title: "底稿输出",
    description: "把已确认疑点整理为待签发底稿草稿。",
    href: "/fund-compliance/review",
    action: "生成底稿"
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
      <section className="audit-panel overflow-hidden p-0">
        <div className="flex flex-col border-b border-[var(--audit-line)] bg-white lg:flex-row">
          <div className="border-b border-[var(--audit-line-soft)] p-5 lg:w-72 lg:border-b-0 lg:border-r">
            <div className="flex items-center gap-2">
              <span className="rounded-md bg-[var(--audit-primary)] px-2 py-1 text-xs font-bold text-white">B2B</span>
              <span className="audit-kicker">医保智能审计平台</span>
            </div>
            <h1 className="audit-page-title mt-3">医保基金使用合规专项自查</h1>
            <p className="audit-copy mt-2">医院审计科用于统筹规则、表单、疑点和底稿的专题入口。</p>
            <div className="mt-4 rounded-[var(--audit-radius-md)] border border-[var(--audit-line-soft)] bg-[var(--audit-surface-muted)] p-3">
              <p className="audit-meta">当前任务</p>
              <p className="mt-1 font-semibold text-[var(--audit-ink)]">2025 年 Q4 住院部专项审计</p>
              <p className="audit-meta mt-2">数据源：HIS + 医保结算 + 病案</p>
            </div>
          </div>

          <div className="min-w-0 flex-1 p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="audit-kicker">智能审计</p>
                <h2 className="audit-section-title mt-1">专题总览</h2>
              </div>
              <Link className="audit-focus-ring audit-btn audit-btn-primary" href="/fund-compliance/review">
                进入专题工作台
              </Link>
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              {topicMetrics.map((metric) => (
                <div key={metric.label} className="rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-white p-4">
                  <p className="audit-meta">{metric.label}</p>
                  <p className={`mt-1 text-2xl font-bold ${metric.tone}`}>{metric.value}</p>
                  <p className="audit-meta mt-1">{metric.detail}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-[18rem_minmax(0,1fr)]">
        <aside className="audit-panel p-4">
          <div className="flex items-center justify-between gap-2">
            <div>
              <p className="audit-kicker">规则导航</p>
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
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {topicModules.map((module) => (
              <Link
                key={module.title}
                href={module.href}
                className="audit-focus-ring audit-panel flex min-h-36 flex-col justify-between p-4 transition hover:border-[var(--audit-primary-line)]"
              >
                <div>
                  <h3 className="audit-card-title">{module.title}</h3>
                  <p className="audit-copy mt-2 text-sm">{module.description}</p>
                </div>
                <span className="mt-4 text-sm font-semibold text-[var(--audit-primary)]">{module.action}</span>
              </Link>
            ))}
          </div>

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
