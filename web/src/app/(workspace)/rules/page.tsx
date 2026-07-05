"use client";

import { useEffect, useState } from "react";

import { SearchBackendStatusPill } from "@/components/portal/search-backend-status-pill";
import { StatusPill } from "@/components/ui/status-pill";
import { fetchRulesWorkbench } from "@/lib/api-client";
import type {
  RuleControlGateApiItem,
  RuleLibraryApiItem,
  RuleRunSnapshotApiItem,
  RuleSourceCoverageApiItem,
  RulesWorkbenchResponse
} from "@/lib/api-types";
import {
  ruleControlGates,
  ruleLibraryItems,
  ruleRunSnapshots,
  ruleSourceCoverages
} from "@/lib/portal-data";

const staticRulesWorkbench: RulesWorkbenchResponse = {
  format: "rules-workbench-v1",
  generated_at: "static-fallback",
  ruleset_id: "FUND-USAGE-COMPLIANCE-RULES",
  ruleset_title: "医保基金使用合规专题规则库",
  ruleset_scope: "汇总监管两库、医保目录、风险清单和对话审证沉淀，首期只读展示规则来源、运行状态和疑点去向。",
  rule_library_items: ruleLibraryItems,
  source_coverages: ruleSourceCoverages,
  run_snapshots: ruleRunSnapshots,
  control_gates: ruleControlGates,
  metrics: buildRulesMetrics(ruleLibraryItems, ruleControlGates, ruleSourceCoverages, ruleRunSnapshots),
  evidence_grade: "static-fallback",
  production_side_effect: "none",
  store: { ready: false, backend: "portal-data-static-fallback" }
};

export default function RulesPage() {
  const [workbench, setWorkbench] = useState<RulesWorkbenchResponse>(staticRulesWorkbench);
  const [backendStatus, setBackendStatus] = useState<"loading" | "ready" | "fallback">("loading");

  useEffect(() => {
    let active = true;

    fetchRulesWorkbench()
      .then((response) => {
        if (!active) {
          return;
        }
        setWorkbench(response);
        setBackendStatus("ready");
      })
      .catch(() => {
        if (!active) {
          return;
        }
        setWorkbench(staticRulesWorkbench);
        setBackendStatus("fallback");
      });

    return () => {
      active = false;
    };
  }, []);

  const statusTone = backendStatus === "ready" ? "success" : backendStatus === "loading" ? "info" : "warning";
  const statusLabel =
    backendStatus === "ready" ? "数据已同步" : backendStatus === "loading" ? "同步中" : "演示数据";

  return (
    <main className="space-y-5">
      <section className="audit-panel p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="audit-kicker">专题规则库</p>
            <h1 className="audit-page-title">审计规则与依据总览</h1>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <SearchBackendStatusPill />
            <StatusPill tone={statusTone}>{statusLabel}</StatusPill>
          </div>
        </div>
        {backendStatus === "fallback" ? (
          <p className="audit-meta mt-4">当前展示演示规则，用于核对规则分类、来源覆盖和疑点流转。</p>
        ) : null}

        <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <RulesMetric label="可运行规则" value={`${workbench.metrics.enabled_rule_count} 条`} />
          <RulesMetric label="待处理规则" value={`${workbench.metrics.pending_rule_count} 条`} />
          <RulesMetric label="已生成疑点" value={`${workbench.metrics.total_finding_count} 条`} />
          <RulesMetric label="阻断门禁" value={`${workbench.metrics.blocked_gate_count} 项`} />
        </div>
      </section>

      <section className="audit-panel p-6" aria-labelledby="rule-library-title">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 id="rule-library-title" className="audit-section-title">规则清单</h2>
          <a className="audit-focus-ring audit-btn audit-btn-secondary" href="/knowledge-base">
            查看依据库
          </a>
        </div>
        <div className="mt-4 grid gap-3 xl:grid-cols-2">
          {workbench.rule_library_items.map((rule) => (
            <RuleCard key={rule.id} rule={rule} />
          ))}
        </div>
      </section>

      <div className="grid gap-5 xl:grid-cols-2">
        <section className="audit-panel p-6">
          <h2 className="audit-section-title">最近运行</h2>
          <div className="mt-4 grid gap-3">
            {workbench.run_snapshots.map((snapshot) => (
              <RunSnapshotCard key={snapshot.id} snapshot={snapshot} />
            ))}
          </div>
        </section>
        <section className="audit-panel p-6">
          <h2 className="audit-section-title">来源覆盖</h2>
          <div className="mt-4 grid gap-3">
            {workbench.source_coverages.map((source) => (
              <SourceCoverageCard key={source.id} source={source} />
            ))}
          </div>
        </section>
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        <section className="audit-panel p-6">
          <h2 className="audit-section-title">发布门禁</h2>
          <div className="mt-4 grid gap-3">
            {workbench.control_gates.map((gate) => (
              <RuleGateCard key={gate.id} gate={gate} />
            ))}
          </div>
        </section>
        <a className="audit-focus-ring audit-action-card p-5" href="/graph">
          <p className="audit-kicker">知识图谱</p>
          <h2 className="audit-section-title mt-2">查看规则证据链</h2>
        </a>
      </div>
    </main>
  );
}

function buildRulesMetrics(
  rules: readonly RuleLibraryApiItem[],
  gates: readonly RuleControlGateApiItem[],
  sources: readonly RuleSourceCoverageApiItem[],
  runs: readonly RuleRunSnapshotApiItem[]
): RulesWorkbenchResponse["metrics"] {
  return {
    rule_count: rules.length,
    enabled_rule_count: rules.filter((rule) => rule.status === "已启用").length,
    pending_rule_count: rules.filter((rule) => rule.status !== "已启用").length,
    total_finding_count: rules.reduce((sum, rule) => sum + rule.findingCount, 0),
    blocked_gate_count: gates.filter((gate) => gate.status === "阻断").length,
    source_count: sources.length,
    run_count: runs.length
  };
}

function RulesMetric({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <div className="audit-panel-muted p-4">
      <p className="audit-label">{label}</p>
      <p className="audit-metric-value mt-2">{value}</p>
    </div>
  );
}

function RuleCard({ rule }: { readonly rule: RuleLibraryApiItem }) {
  return (
    <article className="audit-panel-muted p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="audit-compact-title">{rule.name}</h3>
          <p className="audit-meta mt-1">{rule.code}</p>
        </div>
        <StatusPill tone={getRuleStatusTone(rule.status)}>{rule.status}</StatusPill>
      </div>
      <p className="audit-copy mt-3">{rule.evidenceScope}</p>
      <dl className="audit-meta mt-4 grid grid-cols-2 gap-3">
        <div>
          <dt className="font-semibold">来源</dt>
          <dd className="mt-1 break-words text-[var(--audit-ink)]">{rule.sourceCollection}</dd>
        </div>
        <div>
          <dt className="font-semibold">责任方</dt>
          <dd className="mt-1 text-[var(--audit-ink)]">{rule.owner}</dd>
        </div>
        <div>
          <dt className="font-semibold">疑点</dt>
          <dd className="mt-1 text-[var(--audit-ink)]">{rule.findingCount} 条</dd>
        </div>
        <div>
          <dt className="font-semibold">更新时间</dt>
          <dd className="mt-1 text-[var(--audit-ink)]">{rule.updatedAt}</dd>
        </div>
      </dl>
      <div className="mt-4 grid grid-cols-2 gap-2">
        <a className="audit-focus-ring audit-btn audit-btn-primary" href={rule.href}>
          查看
        </a>
        <a className="audit-focus-ring audit-btn audit-btn-secondary" href={rule.chatHref}>
          审证
        </a>
      </div>
    </article>
  );
}

function RunSnapshotCard({ snapshot }: { readonly snapshot: RuleRunSnapshotApiItem }) {
  return (
    <article className="audit-panel-muted p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="audit-card-title">{snapshot.ruleCode}</h3>
          <p className="audit-meta mt-1">
            {snapshot.inputTable} · {snapshot.lastRunAt}
          </p>
        </div>
        <StatusPill tone={snapshot.hitCount > 0 ? "warning" : "success"}>{snapshot.hitCount} 命中</StatusPill>
      </div>
      <p className="audit-copy mt-3">{snapshot.linkedFinding}</p>
      <p className="mt-2 text-xs font-semibold text-[var(--audit-primary)]">{snapshot.nextAction}</p>
    </article>
  );
}

function SourceCoverageCard({ source }: { readonly source: RuleSourceCoverageApiItem }) {
  return (
    <a className="audit-focus-ring block rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-[var(--audit-surface-muted)] p-3 hover:bg-[var(--audit-primary-soft)]" href={source.href}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="audit-compact-title">{source.name}</p>
          <p className="audit-meta mt-1">{source.sourceCollection}</p>
        </div>
        <StatusPill tone={source.indexStatus === "可引用" ? "success" : source.indexStatus === "待同步" ? "warning" : "neutral"}>
          {source.indexStatus}
        </StatusPill>
      </div>
      <p className="audit-copy mt-3">{source.health}</p>
      <p className="audit-meta mt-2 font-semibold">{source.ruleCount.toLocaleString()} 条</p>
    </a>
  );
}

function RuleGateCard({ gate }: { readonly gate: RuleControlGateApiItem }) {
  return (
    <article className="rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-[var(--audit-surface-muted)] p-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="audit-compact-title">{gate.label}</h3>
          <p className="audit-meta mt-1">责任方：{gate.owner}</p>
        </div>
        <StatusPill tone={getRuleGateTone(gate.status)}>{gate.status}</StatusPill>
      </div>
      <p className="audit-copy mt-3">{gate.detail}</p>
    </article>
  );
}

function getRuleStatusTone(status: RuleLibraryApiItem["status"]) {
  if (status === "已启用") {
    return "success";
  }

  if (status === "待补字段" || status === "待复核") {
    return "warning";
  }

  return "neutral";
}

function getRuleGateTone(status: RuleControlGateApiItem["status"]) {
  if (status === "通过") {
    return "success";
  }

  if (status === "阻断") {
    return "danger";
  }

  return "warning";
}
