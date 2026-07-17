"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { fetchArchiveWorkbench } from "@/lib/api-client";
import type { ArchiveWorkbenchResponse } from "@/lib/api-types";

import {
  ReplicaEmptyState,
  ReplicaMetric,
  ReplicaNotice,
  ReplicaPageHeader,
  ReplicaRuntimeBadge
} from "./replica-page-kit";

type ArchiveState =
  | { readonly status: "loading"; readonly data: null }
  | { readonly status: "ready"; readonly data: ArchiveWorkbenchResponse }
  | { readonly status: "empty"; readonly data: ArchiveWorkbenchResponse }
  | { readonly status: "degraded"; readonly data: null }
  | { readonly status: "error"; readonly data: null };

const archiveStatusLabels: Readonly<Record<string, string>> = {
  active: "使用中",
  archived: "已归档",
  blocked: "存在阻断",
  complete: "已完成",
  completed: "已完成",
  failed: "未通过",
  pass: "通过",
  passed: "通过",
  pending: "待处理",
  ready: "已就绪",
  success: "成功",
  "audit-log-only": "仅记录审计日志",
  "production-readonly-api": "生产只读证据"
};

const archiveOwnerLabels: Readonly<Record<string, string>> = {
  "department-head": "部门负责人",
  "it-admin": "系统管理员",
  admin: "管理员",
  auditor: "审计人员"
};

function archiveStatusLabel(value: string): string {
  return archiveStatusLabels[value.trim().toLowerCase()] ?? value;
}

function archiveOwnerLabel(value: string): string {
  return value
    .split(/\s*[/,]\s*/)
    .filter(Boolean)
    .map((item) => archiveOwnerLabels[item.toLowerCase()] ?? item)
    .join("、");
}

function archivePolicyValue(value: string): string {
  const days = /^(\d+)\s*days?$/i.exec(value.trim());
  if (days) return `${days[1]} 天`;
  if (value.trim().toLowerCase() === "response-only") return "仅保留响应记录";
  return archiveStatusLabel(value);
}

function ArchiveMetrics({ metrics }: { readonly metrics: ArchiveWorkbenchResponse["metrics"] }) {
  const items = [
    ["归档包", metrics.package_count, "blue"],
    ["已归档", metrics.archived_package_count, "green"],
    ["待归档", metrics.pending_package_count, "amber"],
    ["材料阻断", metrics.blocked_package_count, "rose"]
  ] as const;

  return (
    <section className="replica-metric-grid" aria-label="归档指标">
      {items.map(([label, value, tone]) => (
        <ReplicaMetric key={label} label={label} value={String(value)} tone={tone} />
      ))}
    </section>
  );
}

export function ReplicaArchiveWorkbench() {
  const [state, setState] = useState<ArchiveState>({ status: "loading", data: null });

  useEffect(() => {
    let active = true;
    fetchArchiveWorkbench()
      .then((data) => {
        if (!active) return;
        if (!data.store.ready) {
          setState({ status: "degraded", data: null });
          return;
        }
        const empty = data.archive_packages.length === 0
          && data.audit_runs.length === 0
          && data.signature_items.length === 0
          && data.policy_items.length === 0
          && data.timeline.length === 0;
        setState({ status: empty ? "empty" : "ready", data });
      })
      .catch(() => {
        if (active) setState({ status: "error", data: null });
      });
    return () => {
      active = false;
    };
  }, []);

  const data = state.data;
  const hasSeedData = data?.store.backend === "ReadonlyArchiveWorkbenchSeed";

  return (
    <main className="replica-page replica-page-standard replica-archive-workbench" data-replica-source="api" data-replica-status={state.status}>
      <ReplicaPageHeader
        kicker="审计归档"
        title="归档工作台"
        description="只读展示归档包、审计运行、签名、策略和归档时间线，不在此页面触发导出或归档写入。"
        actions={<ReplicaRuntimeBadge source="api" status={state.status} hasSeedData={hasSeedData} />}
      />

      {state.status === "loading" ? (
        <ReplicaEmptyState title="归档数据加载中" description="正在读取归档工作台的只读运行证据。" />
      ) : state.status === "degraded" ? (
        <ReplicaEmptyState title="归档数据受限" description="归档存储状态未就绪，已停止展示可能不完整的归档记录。" />
      ) : state.status === "error" ? (
        <ReplicaEmptyState title="归档工作台暂不可用" description="归档数据读取失败，页面不会注入本地样例或旧数据。" />
      ) : data ? (
        <>
          <ArchiveMetrics metrics={data.metrics} />
          <ReplicaNotice>
            {data.archive_title} · 当前为{archiveStatusLabel(data.evidence_grade)}，最近一次完整性检查
            <strong>{archiveStatusLabel(data.metrics.latest_archive_run_status)}</strong>。本页只读展示，不执行归档或导出写入。
            <details className="replica-runtime-diagnostics">
              <summary>查看运行诊断</summary>
              <ul>
                <li>数据后端：<code>{data.store.backend}</code></li>
                <li>存储状态：<code>store.ready={String(data.store.ready)}</code></li>
                <li>证据等级：<code>{data.evidence_grade}</code></li>
                <li>生产副作用：<code>{data.production_side_effect}</code></li>
              </ul>
            </details>
          </ReplicaNotice>

          {state.status === "empty" ? (
            <ReplicaEmptyState title="暂无归档包、运行、签名、策略或时间线记录" description="归档工作台返回的五类运行集合均为空，页面不会注入旧归档包或本地样例。" />
          ) : (
            <>
          <section className="replica-panel" aria-labelledby="archive-packages-title">
            <div className="replica-results-head">
              <div><p className="replica-kicker">归档包</p><h2 id="archive-packages-title">审计归档包</h2></div>
              <span>{data.archive_packages.length} 项</span>
            </div>
            <div className="replica-record-list">
              {data.archive_packages.map((item) => (
                <article key={item.id}>
                  <div><h3>{item.projectName}</h3><p>归档编号：{item.archiveNo} · 报告编号：{item.reportNo}</p><small>{item.archiveScope} · 保留至 {item.retainedUntil}</small></div>
                  <span>{archiveOwnerLabel(item.owner)}</span>
                  <strong>{archiveStatusLabel(item.status)}</strong>
                  <div className="replica-record-actions">
                    <Link href={item.href}>查看只读归档</Link>
                    <Link href={item.logHref}>查看审计日志</Link>
                  </div>
                  <details className="replica-runtime-diagnostics">
                    <summary>查看归档标识</summary>
                    <code>{item.id}</code>
                  </details>
                </article>
              ))}
            </div>
          </section>

          <section className="replica-panel" aria-labelledby="archive-runs-title">
            <div className="replica-results-head">
              <div><p className="replica-kicker">审计运行</p><h2 id="archive-runs-title">归档完整性检查</h2></div>
              <span>{data.audit_runs.length} 项</span>
            </div>
            <div className="replica-record-list">
              {data.audit_runs.map((item) => (
                <article key={item.id}>
                  <div><h3>{item.title}</h3><p>{item.detail}</p><small>{item.time}</small></div>
                  <span>{item.manifestCount} 清单 · {item.failedCount} 失败</span>
                  <strong>{archiveStatusLabel(item.status)}</strong>
                  <details className="replica-runtime-diagnostics">
                    <summary>查看存储诊断</summary>
                    <code>{item.archiveRoot}</code>
                  </details>
                </article>
              ))}
            </div>
          </section>

          <section className="replica-panel" aria-labelledby="archive-signatures-title">
            <div className="replica-results-head">
              <div><p className="replica-kicker">签名与验签</p><h2 id="archive-signatures-title">签名证据</h2></div>
              <span>{data.signature_items.length} 项</span>
            </div>
            <div className="replica-record-list">
              {data.signature_items.map((item) => (
                <article key={item.id}>
                  <div><h3>{item.label}</h3><p>{item.detail}</p></div>
                  <strong>{archiveStatusLabel(item.status)}</strong>
                  <details className="replica-runtime-diagnostics">
                    <summary>查看签名摘要</summary>
                    <code>{item.sha256}</code>
                  </details>
                </article>
              ))}
            </div>
          </section>

          <section className="replica-panel" aria-labelledby="archive-policies-title">
            <div className="replica-results-head">
              <div><p className="replica-kicker">归档策略</p><h2 id="archive-policies-title">保留与治理策略</h2></div>
              <span>{data.policy_items.length} 项</span>
            </div>
            <div className="replica-record-list">
              {data.policy_items.map((item) => (
                <article key={item.id}>
                  <div><h3>{item.label}</h3><p>{item.detail}</p></div>
                  <strong>{archivePolicyValue(item.value)}</strong>
                </article>
              ))}
            </div>
          </section>

          <section className="replica-panel" aria-labelledby="archive-timeline-title">
            <div className="replica-results-head">
              <div><p className="replica-kicker">归档时间线</p><h2 id="archive-timeline-title">最近归档记录</h2></div>
              <span>{data.timeline.length} 项</span>
            </div>
            <div className="replica-record-list">
              {data.timeline.map((item) => (
                <article key={item.id}>
                  <div><h3>{item.title}</h3><p>{item.detail}</p><small>{item.time}</small></div>
                  <strong>{archiveStatusLabel(item.status)}</strong>
                </article>
              ))}
            </div>
          </section>
            </>
          )}
        </>
      ) : null}
    </main>
  );
}
