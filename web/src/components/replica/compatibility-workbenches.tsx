"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

import {
  ReplicaMetric,
  ReplicaNotice,
  ReplicaPageHeader,
  ReplicaRuntimeBadge
} from "@/components/replica/replica-page-kit";
import {
  fetchAuditFindings,
  fetchReportWorkbench,
  fetchRulesWorkbench,
  fetchSearchBackendStatus
} from "@/lib/api-client";
import type {
  AuditFindingsResponse,
  ReportWorkbenchResponse,
  RulesWorkbenchResponse,
  SearchBackendStatusResponse
} from "@/lib/api-types";
import {
  archiveAuditRuns,
  archivePackages,
  archivePolicyItems,
  archiveSignatureItems,
  archiveTimeline,
  auditTableTemplates,
  guidedCheckEvidenceItems,
  guidedCheckQuestions,
  guidedCheckRiskSignals,
  guidedCheckSteps,
  guidedCheckTimeline
} from "@/lib/portal-data";

type RuntimeStatus = "loading" | "ready" | "fallback";

type CompatibilityRuntime = {
  readonly findings: AuditFindingsResponse | null;
  readonly rules: RulesWorkbenchResponse | null;
  readonly reports: ReportWorkbenchResponse | null;
  readonly search: SearchBackendStatusResponse | null;
  readonly statuses: {
    readonly findings: RuntimeStatus;
    readonly rules: RuntimeStatus;
    readonly reports: RuntimeStatus;
    readonly search: RuntimeStatus;
  };
};

type RuntimeSummary = {
  readonly source: "fixture" | "api" | "hybrid";
  readonly status: "loading" | "ready";
  readonly hasSeedData: boolean;
  readonly issueCount: number;
  readonly backendLabel: string;
};

type MetricTone = "blue" | "green" | "amber" | "rose" | "slate";

type DynamicMetric = {
  readonly label: string;
  readonly value: string;
  readonly tone?: MetricTone;
};

type DynamicCard = {
  readonly id: string;
  readonly eyebrow: string;
  readonly title: string;
  readonly detail: string;
  readonly value?: string;
  readonly href: string;
};

type ReviewStage = {
  readonly id: "records" | "forms" | "rules" | "workpaper";
  readonly label: string;
  readonly href: string;
  readonly status: string;
  readonly summary: string;
};

function useMedicalAuditCompatibilityRuntime(): CompatibilityRuntime {
  const [findings, setFindings] = useState<AuditFindingsResponse | null>(null);
  const [rules, setRules] = useState<RulesWorkbenchResponse | null>(null);
  const [reports, setReports] = useState<ReportWorkbenchResponse | null>(null);
  const [search, setSearch] = useState<SearchBackendStatusResponse | null>(null);
  const [statuses, setStatuses] = useState<CompatibilityRuntime["statuses"]>({
    findings: "loading",
    rules: "loading",
    reports: "loading",
    search: "loading"
  });

  useEffect(() => {
    let mounted = true;

    fetchAuditFindings("pending-review")
      .then((response) => {
        if (!mounted) return;
        setFindings(response);
        setStatuses((current) => ({ ...current, findings: "ready" }));
      })
      .catch(() => {
        if (mounted) setStatuses((current) => ({ ...current, findings: "fallback" }));
      });

    fetchRulesWorkbench()
      .then((response) => {
        if (!mounted) return;
        setRules(response);
        setStatuses((current) => ({ ...current, rules: "ready" }));
      })
      .catch(() => {
        if (mounted) setStatuses((current) => ({ ...current, rules: "fallback" }));
      });

    fetchReportWorkbench()
      .then((response) => {
        if (!mounted) return;
        setReports(response);
        setStatuses((current) => ({ ...current, reports: "ready" }));
      })
      .catch(() => {
        if (mounted) setStatuses((current) => ({ ...current, reports: "fallback" }));
      });

    fetchSearchBackendStatus()
      .then((response) => {
        if (!mounted) return;
        setSearch(response);
        setStatuses((current) => ({ ...current, search: "ready" }));
      })
      .catch(() => {
        if (mounted) setStatuses((current) => ({ ...current, search: "fallback" }));
      });

    return () => {
      mounted = false;
    };
  }, []);

  return { findings, rules, reports, search, statuses };
}

function buildRuntimeSummary(runtime: CompatibilityRuntime): RuntimeSummary {
  const statuses = Object.values(runtime.statuses);
  const readyCount = statuses.filter((status) => status === "ready").length;
  const fallbackCount = statuses.filter((status) => status === "fallback").length;
  const loadingCount = statuses.filter((status) => status === "loading").length;
  const backends = [
    runtime.findings?.store.backend,
    runtime.rules?.store.backend,
    runtime.reports?.store.backend,
    runtime.search?.backend
  ].filter(Boolean);
  const hasSeedData = backends.some((backend) => isSeedBackend(backend));

  return {
    source: readyCount > 0 ? (fallbackCount > 0 ? "hybrid" : "api") : "fixture",
    status: loadingCount > 0 && readyCount === 0 ? "loading" : "ready",
    hasSeedData,
    issueCount: fallbackCount + Number(hasSeedData),
    backendLabel: backends.length > 0 ? backends.join(" / ") : "本地样例"
  };
}

function isSeedBackend(backend: string | undefined): boolean {
  return Boolean(backend && (backend.startsWith("Readonly") || backend.endsWith("Seed")));
}

function formatNumber(value: number | undefined, fallback: number): string {
  return `${value ?? fallback}`;
}

function runtimeActions(summary: RuntimeSummary, primaryHref: string, primaryLabel: string) {
  return (
    <>
      <ReplicaRuntimeBadge
        source={summary.source}
        status={summary.status}
        hasSeedData={summary.hasSeedData}
        issueCount={summary.issueCount}
      />
      <Link className="replica-primary-button" href={primaryHref}>{primaryLabel}</Link>
    </>
  );
}

function buildComplianceMetrics(runtime: CompatibilityRuntime): readonly DynamicMetric[] {
  return [
    {
      label: "待复核疑点",
      value: formatNumber(runtime.findings?.stats.pending_review, guidedCheckRiskSignals.length),
      tone: "rose"
    },
    {
      label: "规则命中",
      value: formatNumber(runtime.rules?.metrics.total_finding_count, guidedCheckRiskSignals.length),
      tone: "amber"
    },
    {
      label: "已关联任务",
      value: formatNumber(runtime.findings?.stats.linked_review_task, archivePackages.length),
      tone: "green"
    },
    {
      label: "底稿条目",
      value: formatNumber(runtime.reports?.metrics.report_count, auditTableTemplates.length),
      tone: "slate"
    }
  ];
}

function buildComplianceRiskCards(runtime: CompatibilityRuntime): readonly DynamicCard[] {
  const findings = runtime.findings?.items.slice(0, 4).map((item) => ({
    id: item.finding_key,
    eyebrow: item.review_status,
    title: item.finding_key,
    detail: `${item.finding_type} · ${item.severity} · ${item.rule_key ?? "待绑定规则"}`,
    value: item.status,
    href: "/findings"
  }));

  if (findings && findings.length > 0) {
    return findings;
  }

  return guidedCheckRiskSignals.map((signal) => ({
    id: signal.id,
    eyebrow: signal.status,
    title: signal.label,
    detail: signal.detail,
    value: signal.value,
    href: signal.href
  }));
}

function buildReviewMetrics(runtime: CompatibilityRuntime): readonly DynamicMetric[] {
  return [
    {
      label: "表单样式",
      value: formatNumber(runtime.reports?.workpaper_templates.length, auditTableTemplates.length)
    },
    {
      label: "疑点总数",
      value: formatNumber(runtime.findings?.stats.total, 0),
      tone: "rose"
    },
    {
      label: "规则数量",
      value: formatNumber(runtime.rules?.metrics.enabled_rule_count, 0),
      tone: "green"
    },
    {
      label: "阻断底稿",
      value: formatNumber(runtime.reports?.metrics.blocked_report_count, 0),
      tone: "amber"
    }
  ];
}

function runtimeStageStatus(status: RuntimeStatus, blockerCount: number): string {
  if (status === "loading") return "加载中";
  if (status === "fallback") return "数据不可用";
  return blockerCount > 0 ? "需处理" : "已就绪";
}

function reportStageStatus(status: RuntimeStatus, reportCount: number, blockedReportCount: number): string {
  if (status === "loading") return "加载中";
  if (status === "fallback") return "数据不可用";
  return reportCount === 0 || blockedReportCount > 0 ? "需处理" : "已就绪";
}

function runtimeDataSummary(status: RuntimeStatus, label: string, readySummary: string): string {
  if (status === "loading") return `${label}加载中`;
  if (status === "fallback") return `${label}暂不可用`;
  return readySummary;
}

function runtimeCountValue(status: RuntimeStatus, value: number): string {
  return status === "ready" ? `${value}` : "待同步";
}

function reportStageSummary(
  status: RuntimeStatus,
  reportCount: number,
  blockedReportCount: number
): string {
  return runtimeDataSummary(
    status,
    "底稿数据",
    reportCount === 0 ? "暂无底稿" : `${reportCount} 项底稿 / ${blockedReportCount} 项阻断`
  );
}

function buildReviewStages(runtime: CompatibilityRuntime): readonly ReviewStage[] {
  const pendingFindingCount = runtime.findings?.stats.pending_review ?? 0;
  const templateCount = runtime.reports?.workpaper_templates.length ?? 0;
  const blockingGateCount = runtime.rules?.metrics.blocked_gate_count ?? 0;
  const controlGateCount = runtime.rules?.control_gates.length ?? 0;
  const reportCount = runtime.reports?.metrics.report_count ?? 0;
  const blockedReportCount = runtime.reports?.metrics.blocked_report_count ?? 0;

  return [
    {
      id: "records",
      label: "单据审查",
      href: "/medical-audit",
      status: runtimeStageStatus(runtime.statuses.findings, pendingFindingCount),
      summary: runtimeDataSummary(
        runtime.statuses.findings,
        "疑点数据",
        `${pendingFindingCount} 项待复核疑点`
      )
    },
    {
      id: "forms",
      label: "费用表单",
      href: "/analytics",
      status: runtimeStageStatus(runtime.statuses.reports, Number(templateCount === 0)),
      summary: runtimeDataSummary(
        runtime.statuses.reports,
        "底稿模板",
        `费用汇总、分类汇总、就诊明细 · ${templateCount} 个底稿模板`
      )
    },
    {
      id: "rules",
      label: "规则复核",
      href: "/rules",
      status: runtimeStageStatus(runtime.statuses.rules, blockingGateCount),
      summary: runtimeDataSummary(
        runtime.statuses.rules,
        "规则数据",
        `${blockingGateCount} 项阻断门禁 / ${controlGateCount} 项控制门禁`
      )
    },
    {
      id: "workpaper",
      label: "底稿输出",
      href: "/reports",
      status: reportStageStatus(runtime.statuses.reports, reportCount, blockedReportCount),
      summary: reportStageSummary(runtime.statuses.reports, reportCount, blockedReportCount)
    }
  ];
}

function buildComplianceReadinessCards(runtime: CompatibilityRuntime): readonly DynamicCard[] {
  const pendingFindingCount = runtime.findings?.stats.pending_review ?? 0;
  const visibleFindingCount = runtime.findings?.items.length ?? 0;
  const blockingGateCount = runtime.rules?.metrics.blocked_gate_count ?? 0;
  const controlGateCount = runtime.rules?.control_gates.length ?? 0;
  const reportCount = runtime.reports?.metrics.report_count ?? 0;
  const blockedReportCount = runtime.reports?.metrics.blocked_report_count ?? 0;

  return [
    {
      id: "pending-findings",
      eyebrow: runtimeStageStatus(runtime.statuses.findings, pendingFindingCount),
      title: "当前待复核疑点",
      detail: runtimeDataSummary(
        runtime.statuses.findings,
        "疑点数据",
        `${pendingFindingCount} 项待复核，当前返回 ${visibleFindingCount} 项。`
      ),
      value: runtimeCountValue(runtime.statuses.findings, pendingFindingCount),
      href: "/findings"
    },
    {
      id: "blocking-control-gates",
      eyebrow: runtimeStageStatus(runtime.statuses.rules, blockingGateCount),
      title: "阻断控制门禁",
      detail: runtimeDataSummary(
        runtime.statuses.rules,
        "规则数据",
        `${blockingGateCount} 项阻断门禁 / ${controlGateCount} 项控制门禁。`
      ),
      value: runtimeCountValue(runtime.statuses.rules, blockingGateCount),
      href: "/rules"
    },
    {
      id: "report-readiness",
      eyebrow: reportStageStatus(runtime.statuses.reports, reportCount, blockedReportCount),
      title: "底稿就绪状态",
      detail: runtimeDataSummary(
        runtime.statuses.reports,
        "底稿数据",
        reportCount === 0
          ? "当前没有可用底稿。"
          : `${reportCount} 项底稿 / ${blockedReportCount} 项阻断。`
      ),
      value: runtime.statuses.reports !== "ready"
        ? "待同步"
        : reportCount === 0
          ? "暂无底稿"
          : `${Math.max(reportCount - blockedReportCount, 0)}/${reportCount}`,
      href: "/reports"
    }
  ];
}

function buildGuidedRiskSummary(runtime: CompatibilityRuntime): string {
  const pendingFindingCount = runtime.findings?.stats.pending_review ?? 0;
  const blockingGateCount = runtime.rules?.metrics.blocked_gate_count ?? 0;
  const blockedReportCount = runtime.reports?.metrics.blocked_report_count ?? 0;

  return [
    runtimeDataSummary(runtime.statuses.findings, "疑点数据", `${pendingFindingCount} 项待复核`),
    runtimeDataSummary(runtime.statuses.rules, "规则数据", `${blockingGateCount} 项规则阻断`),
    runtimeDataSummary(runtime.statuses.reports, "底稿数据", `${blockedReportCount} 项底稿阻断`)
  ].join(" · ");
}

function buildGuidedMetrics(runtime: CompatibilityRuntime): readonly DynamicMetric[] {
  return [
    {
      label: "核查步骤",
      value: `${guidedCheckSteps.length}`
    },
    {
      label: "待补门禁",
      value: formatNumber(
        runtime.findings?.generation_readiness.blocking_reasons.length,
        guidedCheckEvidenceItems.filter((item) => item.status !== "已就绪").length
      ),
      tone: "amber"
    },
    {
      label: "规则阻断",
      value: formatNumber(runtime.rules?.metrics.blocked_gate_count, 0),
      tone: "rose"
    },
    {
      label: "检索状态",
      value: runtime.search?.ready ? "就绪" : "待接入",
      tone: runtime.search?.ready ? "green" : "slate"
    }
  ];
}

function buildGuidedEvidence(runtime: CompatibilityRuntime): readonly DynamicCard[] {
  const cards: DynamicCard[] = [];

  for (const prerequisite of runtime.findings?.generation_readiness.prerequisites ?? []) {
    cards.push({
      id: `prerequisite-${prerequisite.key}`,
      eyebrow: prerequisite.ready ? "已就绪" : "待补证",
      title: prerequisite.label,
      detail: `当前 ${prerequisite.count} 条，${prerequisite.required ? "必需" : "可选"}材料。`,
      value: prerequisite.ready ? "通过" : "待处理",
      href: "/findings"
    });
  }

  for (const gate of runtime.rules?.control_gates ?? []) {
    cards.push({
      id: `gate-${gate.id}`,
      eyebrow: gate.status,
      title: gate.label,
      detail: gate.detail,
      value: gate.owner,
      href: "/rules"
    });
  }

  for (const entry of runtime.reports?.report_entries.slice(0, 4) ?? []) {
    cards.push({
      id: `report-${entry.id}`,
      eyebrow: entry.status,
      title: entry.title,
      detail: entry.gate_summary,
      value: entry.report_no,
      href: "/reports"
    });
  }

  if (cards.length > 0) {
    return cards.slice(0, 8);
  }

  return guidedCheckEvidenceItems.map((item) => ({
    id: item.id,
    eyebrow: item.source,
    title: item.title,
    detail: item.blocker,
    value: item.status,
    href: item.href
  }));
}

export function FundComplianceWorkbench() {
  const runtime = useMedicalAuditCompatibilityRuntime();
  const summary = buildRuntimeSummary(runtime);
  const metrics = useMemo(() => buildComplianceMetrics(runtime), [runtime]);
  const readinessCards = useMemo(() => buildComplianceReadinessCards(runtime), [runtime]);
  const riskCards = useMemo(() => buildComplianceRiskCards(runtime), [runtime]);

  return (
    <main className="replica-page" data-replica-source="compatibility-route" data-replica-status="ready">
      <ReplicaPageHeader
        kicker="医保审计"
        title="医保基金使用合规"
        description="旧基金合规入口保留为专题首页，聚合医保审计、三张费用表单、引导核查和底稿归档入口。"
        actions={runtimeActions(summary, "/medical-audit", "进入医保审计")}
      />

      <section className="replica-metric-grid" aria-label="医保基金使用合规概览">
        {metrics.map((metric) => (
          <ReplicaMetric key={metric.label} label={metric.label} value={metric.value} tone={metric.tone} />
        ))}
      </section>

      <ReplicaNotice>数据来源：{summary.backendLabel}</ReplicaNotice>

      <section className="replica-panel" aria-label="医保基金合规运行状态">
        <div className="replica-results-head">
          <div>
            <p className="replica-kicker">运行状态</p>
            <h2>疑点、门禁与底稿</h2>
          </div>
          <span>只读汇总</span>
        </div>
        <div className="replica-kb-grid">
          {readinessCards.map((item) => (
            <article key={item.id} className="replica-kb-card">
              <div className="replica-kb-card-head">
                <div>
                  <span>{item.eyebrow}</span>
                  <h2>{item.title}</h2>
                </div>
                <strong>{item.value}</strong>
              </div>
              <p>{item.detail}</p>
              <div className="replica-card-actions">
                <Link className="replica-card-detail-button" href={item.href}>查看</Link>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="replica-report-layout">
        <div className="replica-panel">
          <div className="replica-results-head">
            <div>
              <p className="replica-kicker">专题路径</p>
              <h2>医保审计闭环</h2>
            </div>
            <span>规则、表单、底稿、归档</span>
          </div>
          <div className="replica-kb-grid">
            {[
              { title: "医保审计", detail: "进入专项工作台查看规则维度、疑点列表和三张表单。", href: "/medical-audit" },
              { title: "复核表单", detail: "按费用汇总、分类汇总、就诊明细三类模板组织复核。", href: "/fund-compliance/review" },
              { title: "引导式核查", detail: "按步骤梳理数据、规则、AI 对话和报告门禁。", href: "/guided-check" },
              { title: "项目档案", detail: "查看归档包、签名链、保留策略和阻断项。", href: "/archive" }
            ].map((item) => (
              <article key={item.href} className="replica-kb-card">
                <div className="replica-kb-card-head">
                  <div>
                    <span>专题入口</span>
                    <h2>{item.title}</h2>
                  </div>
                </div>
                <p>{item.detail}</p>
                <div className="replica-card-actions">
                  <Link className="replica-card-detail-button" href={item.href}>打开</Link>
                </div>
              </article>
            ))}
          </div>
        </div>

        <div className="replica-panel">
          <div className="replica-results-head">
            <div>
              <p className="replica-kicker">表单模板</p>
              <h2>医保费用复核表</h2>
            </div>
            <Link href="/fund-compliance/review">查看全部</Link>
          </div>
          <div className="replica-record-list">
            {auditTableTemplates.map((template) => (
              <article key={template.id}>
                <div>
                  <h3>{template.name}</h3>
                  <p>{template.auditUse}</p>
                </div>
                <span>{template.shortName}</span>
                <strong>{template.expectedColumns.length} 列</strong>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="replica-panel">
        <div className="replica-results-head">
          <div>
            <p className="replica-kicker">风险信号</p>
            <h2>当前核查重点</h2>
          </div>
          <span>{guidedCheckRiskSignals.length} 项</span>
        </div>
        <div className="replica-kb-grid">
          {riskCards.map((signal) => (
            <article key={signal.id} className="replica-kb-card">
              <div className="replica-kb-card-head">
                <div>
                  <span>{signal.eyebrow}</span>
                  <h2>{signal.title}</h2>
                </div>
                <strong>{signal.value}</strong>
              </div>
              <p>{signal.detail}</p>
              <div className="replica-card-actions">
                <Link className="replica-card-detail-button" href={signal.href}>查看</Link>
              </div>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}

export function FundComplianceReviewWorkbench() {
  const runtime = useMedicalAuditCompatibilityRuntime();
  const summary = buildRuntimeSummary(runtime);
  const metrics = useMemo(() => buildReviewMetrics(runtime), [runtime]);
  const reviewStages = useMemo(() => buildReviewStages(runtime), [runtime]);

  return (
    <main className="replica-page" data-replica-source="compatibility-route" data-replica-status="ready">
      <ReplicaPageHeader
        kicker="医保基金使用合规"
        title="医保基金复核表单"
        description="保留三类费用模板的产品入口，后续上传和分析继续在 AI 数据分析、医保审计工作台中完成。"
        actions={runtimeActions(summary, "/medical-audit", "返回医保审计")}
      />

      <section className="replica-metric-grid" aria-label="医保基金复核表单概览">
        {metrics.map((metric) => (
          <ReplicaMetric key={metric.label} label={metric.label} value={metric.value} tone={metric.tone} />
        ))}
      </section>

      <ReplicaNotice>数据来源：{summary.backendLabel}</ReplicaNotice>

      <section className="replica-panel" aria-label="医保基金复核四阶段">
        <div className="replica-results-head">
          <div>
            <p className="replica-kicker">复核工作流</p>
            <h2>从单据审查到底稿输出</h2>
          </div>
          <span>当前运行数据只读展示</span>
        </div>
        <div className="replica-kb-grid">
          {reviewStages.map((stage) => (
            <article key={stage.id} className="replica-kb-card">
              <div className="replica-kb-card-head">
                <div>
                  <span>{stage.status}</span>
                  <h2>{stage.label}</h2>
                </div>
              </div>
              <p>{stage.summary}</p>
              <div className="replica-card-actions">
                <Link className="replica-card-detail-button" href={stage.href}>打开{stage.label}</Link>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="replica-kb-grid" aria-label="医保基金复核表单列表">
        {auditTableTemplates.map((template) => (
          <article key={template.id} className="replica-kb-card" aria-label={template.name}>
            <div className="replica-kb-card-head">
              <div>
                <span>{template.shortName}</span>
                <h2>{template.name}</h2>
              </div>
              <strong>{template.sheetName}</strong>
            </div>
            <p>{template.auditUse}</p>
            <dl className="replica-kb-stats">
              <div>
                <dt>文件模板</dt>
                <dd>{template.fileName}</dd>
              </div>
              <div>
                <dt>字段数量</dt>
                <dd>{template.expectedColumns.length}</dd>
              </div>
            </dl>
            <div className="replica-kb-tags">
              {template.keyChecks.map((check) => (
                <span key={check}>{check}</span>
              ))}
            </div>
            <div className="replica-card-actions">
              <Link className="replica-card-detail-button" href={`/analytics?template=${template.id}`}>进入分析</Link>
              <Link className="replica-card-detail-button" href={`/chat?question=${encodeURIComponent(template.analysisRequest)}`}>生成问题</Link>
            </div>
          </article>
        ))}
      </section>

      <ReplicaNotice>复核表单页面仅提供模板与入口；上传、解析和底稿生成需按受控流程提交并完成人工复核。</ReplicaNotice>
    </main>
  );
}

export function GuidedCheckWorkbench() {
  const runtime = useMedicalAuditCompatibilityRuntime();
  const summary = buildRuntimeSummary(runtime);
  const metrics = useMemo(() => buildGuidedMetrics(runtime), [runtime]);
  const guidedEvidence = useMemo(() => buildGuidedEvidence(runtime), [runtime]);
  const riskSummary = useMemo(() => buildGuidedRiskSummary(runtime), [runtime]);

  return (
    <main className="replica-page" data-replica-source="compatibility-route" data-replica-status="ready">
      <ReplicaPageHeader
        kicker="引导自查"
        title="引导式核查"
        description="按医保基金使用合规专题的真实工作顺序，把数据、规则、AI 审证、底稿和归档串成可执行路径。"
        actions={runtimeActions(summary, "/chat", "进入 AI 对话")}
      />

      <section className="replica-metric-grid" aria-label="引导式核查概览">
        {metrics.map((metric) => (
          <ReplicaMetric key={metric.label} label={metric.label} value={metric.value} tone={metric.tone} />
        ))}
      </section>

      <ReplicaNotice>数据来源：{summary.backendLabel}</ReplicaNotice>

      <section className="replica-panel" aria-label="引导式核查风险摘要">
        <div className="replica-results-head">
          <div>
            <p className="replica-kicker">当前风险</p>
            <h2>风险摘要</h2>
          </div>
          <span>只读运行态</span>
        </div>
        <ReplicaNotice>{riskSummary}</ReplicaNotice>
      </section>

      <section className="replica-report-layout">
        <div className="replica-panel">
          <div className="replica-results-head">
            <div>
              <p className="replica-kicker">核查步骤</p>
              <h2>从项目到归档</h2>
            </div>
            <span>人工复核边界保留</span>
          </div>
          <div className="replica-record-list">
            {guidedCheckSteps.map((step) => (
              <article key={step.id}>
                <div>
                  <h3>{step.order} · {step.title}</h3>
                  <p>{step.detail}</p>
                </div>
                <span>{step.status}</span>
                <strong>{step.owner}</strong>
                <div className="replica-record-actions">
                  <Link href={step.href}>打开</Link>
                </div>
              </article>
            ))}
          </div>
        </div>

        <div className="replica-panel">
          <div className="replica-results-head">
            <div>
              <p className="replica-kicker">AI 审证问题</p>
              <h2>可直接带入对话</h2>
            </div>
            <span>{guidedCheckQuestions.length} 条</span>
          </div>
          <div className="replica-record-list">
            {guidedCheckQuestions.map((item) => (
              <article key={item.id}>
                <div>
                  <h3>{item.domain}</h3>
                  <p>{item.question}</p>
                </div>
                <span>{item.status}</span>
                <strong>{item.agentName}</strong>
                <div className="replica-record-actions">
                  <Link href={item.chatHref}>提问</Link>
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="replica-panel">
        <div className="replica-results-head">
          <div>
            <p className="replica-kicker">证据与风险</p>
            <h2>材料准备状态</h2>
          </div>
          <span>{guidedEvidence.length} 项材料</span>
        </div>
        <div className="replica-kb-grid">
          {guidedEvidence.map((item) => (
            <article key={item.id} className="replica-kb-card">
              <div className="replica-kb-card-head">
                <div>
                  <span>{item.eyebrow}</span>
                  <h2>{item.title}</h2>
                </div>
                <strong>{item.value}</strong>
              </div>
              <p>{item.detail}</p>
              <div className="replica-card-actions">
                <Link className="replica-card-detail-button" href={item.href}>查看</Link>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="replica-panel">
        <div className="replica-results-head">
          <div>
            <p className="replica-kicker">核查时间线</p>
            <h2>最近进展</h2>
          </div>
          <span>{guidedCheckTimeline.length} 条</span>
        </div>
        <div className="replica-record-list">
          {guidedCheckTimeline.map((item) => (
            <article key={item.id}>
              <div>
                <h3>{item.title}</h3>
                <p>{item.detail}</p>
              </div>
              <span>{item.status}</span>
              <strong>{item.time}</strong>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}

export function ArchiveWorkbench() {
  return (
    <main className="replica-page" data-replica-source="compatibility-route" data-replica-status="ready">
      <ReplicaPageHeader
        kicker="项目归档"
        title="项目档案归档"
        description="按项目档案包、签名链、巡检记录和归档策略组织生产只读证据，避免把报告、整改和日志混在一个页面里。"
        actions={<Link className="replica-primary-button" href="/reports">查看底稿报告</Link>}
      />

      <section className="replica-metric-grid" aria-label="项目档案归档概览">
        <ReplicaMetric label="归档包" value={`${archivePackages.length}`} />
        <ReplicaMetric label="巡检记录" value={`${archiveAuditRuns.length}`} tone="green" />
        <ReplicaMetric label="签名链" value={`${archiveSignatureItems.length}`} tone="amber" />
        <ReplicaMetric label="策略项" value={`${archivePolicyItems.length}`} tone="slate" />
      </section>

      <section className="replica-report-layout">
        <div className="replica-panel">
          <div className="replica-results-head">
            <div>
              <p className="replica-kicker">归档包</p>
              <h2>项目档案包</h2>
            </div>
            <span>{archivePackages.length} 个</span>
          </div>
          <div className="replica-record-list">
            {archivePackages.map((item) => (
              <article key={item.id}>
                <div>
                  <h3>{item.projectName}</h3>
                  <p>{item.archiveScope}</p>
                </div>
                <span>{item.status}</span>
                <strong>{item.archiveNo}</strong>
                <div className="replica-record-actions">
                  <Link href={item.href}>查看来源</Link>
                </div>
              </article>
            ))}
          </div>
        </div>

        <div className="replica-panel" id="archive-policy-title">
          <div className="replica-results-head">
            <div>
              <p className="replica-kicker">审计日志与策略</p>
              <h2>归档策略</h2>
            </div>
            <span>{archivePolicyItems.length} 项</span>
          </div>
          <div className="replica-kb-grid">
            {archivePolicyItems.map((item) => (
              <article key={item.id} className="replica-kb-card">
                <div className="replica-kb-card-head">
                  <div>
                    <span>{item.label}</span>
                    <h2>{item.value}</h2>
                  </div>
                </div>
                <p>{item.detail}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="replica-report-layout">
        <div className="replica-panel">
          <div className="replica-results-head">
            <div>
              <p className="replica-kicker">验签与巡检</p>
              <h2>签名链状态</h2>
            </div>
            <span>{archiveSignatureItems.length} 项</span>
          </div>
          <div className="replica-record-list">
            {archiveSignatureItems.map((item) => (
              <article key={item.id}>
                <div>
                  <h3>{item.label}</h3>
                  <p>{item.detail}</p>
                </div>
                <span>{item.status}</span>
                <strong>{item.sha256}</strong>
              </article>
            ))}
          </div>
        </div>

        <div className="replica-panel">
          <div className="replica-results-head">
            <div>
              <p className="replica-kicker">归档时间线</p>
              <h2>最近归档事件</h2>
            </div>
            <span>{archiveTimeline.length} 条</span>
          </div>
          <div className="replica-record-list">
            {archiveTimeline.map((item) => (
              <article key={item.id}>
                <div>
                  <h3>{item.title}</h3>
                  <p>{item.detail}</p>
                </div>
                <span>{item.status}</span>
                <strong>{item.time}</strong>
              </article>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}
