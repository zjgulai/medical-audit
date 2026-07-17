"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { fetchRemediationWorkbench } from "@/lib/api-client";
import type { RemediationWorkbenchResponse } from "@/lib/api-types";

import {
  ReplicaEmptyState,
  ReplicaMetric,
  ReplicaNotice,
  ReplicaPageHeader,
  ReplicaRuntimeBadge
} from "./replica-page-kit";

type RemediationState =
  | { readonly status: "loading"; readonly data: null }
  | { readonly status: "ready"; readonly data: RemediationWorkbenchResponse }
  | { readonly status: "empty"; readonly data: RemediationWorkbenchResponse }
  | { readonly status: "error"; readonly data: null };

function RemediationMetrics({ metrics }: { readonly metrics: RemediationWorkbenchResponse["metrics"] }) {
  const items = [
    ["整改事项", metrics.case_count, "blue"],
    ["整改中", metrics.active_case_count, "green"],
    ["待补证", metrics.pending_evidence_count, "amber"],
    ["阻断门禁", metrics.blocked_gate_count, "rose"]
  ] as const;

  return (
    <section className="replica-metric-grid" aria-label="整改指标">
      {items.map(([label, value, tone]) => (
        <ReplicaMetric key={label} label={label} value={String(value)} tone={tone} />
      ))}
    </section>
  );
}

export function ReplicaRemediationWorkbench() {
  const [state, setState] = useState<RemediationState>({ status: "loading", data: null });

  useEffect(() => {
    let active = true;
    fetchRemediationWorkbench()
      .then((data) => {
        if (!active) return;
        const empty = data.remediation_cases.length === 0
          && data.evidence_requests.length === 0
          && data.closure_gates.length === 0
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
  const hasSeedData = data?.store.backend === "ReadonlyRemediationWorkbenchSeed";

  return (
    <main className="replica-page replica-page-standard" data-replica-source="api" data-replica-status={state.status}>
      <ReplicaPageHeader
        kicker="整改闭环"
        title="整改工作台"
        description="只读展示整改事项、补证请求、关闭门禁和跟踪时间线，不在此页面执行更新或关闭动作。"
        actions={<ReplicaRuntimeBadge source="api" status={state.status} hasSeedData={hasSeedData} />}
      />

      {state.status === "loading" ? (
        <ReplicaEmptyState title="整改数据加载中" description="正在读取整改工作台的只读运行证据。" />
      ) : state.status === "error" ? (
        <ReplicaEmptyState title="整改工作台暂不可用" description="整改数据读取失败，页面不会注入本地样例或旧数据。" />
      ) : data ? (
        <>
          <RemediationMetrics metrics={data.metrics} />
          <ReplicaNotice>
            {data.workbench_title} · 数据后端：<strong>{data.store.backend}</strong> · store.ready={String(data.store.ready)} · evidence_grade=<strong>{data.evidence_grade}</strong> · production_side_effect=<strong>{data.production_side_effect}</strong>
          </ReplicaNotice>

          {state.status === "empty" ? (
            <ReplicaEmptyState title="暂无整改、补证、门禁或时间线记录" description="整改工作台返回的四类运行集合均为空，页面不会注入旧台账或本地样例。" />
          ) : (
            <>
          <section className="replica-panel" aria-labelledby="remediation-cases-title">
            <div className="replica-results-head">
              <div><p className="replica-kicker">整改事项</p><h2 id="remediation-cases-title">整改台账</h2></div>
              <span>{data.remediation_cases.length} 项</span>
            </div>
            <div className="replica-record-list">
              {data.remediation_cases.map((item) => (
                <article key={item.id}>
                  <div><h3>{item.title}</h3><p>{item.id} · {item.department} · {item.reportNo}</p><small>{item.nextAction} · 截止 {item.dueDate}</small></div>
                  <span>{item.progress}% · {item.evidenceStatus}</span>
                  <strong>{item.status}</strong>
                  <Link href={item.href}>查看只读详情</Link>
                </article>
              ))}
            </div>
          </section>

          <section className="replica-panel" aria-labelledby="remediation-evidence-title">
            <div className="replica-results-head">
              <div><p className="replica-kicker">补证请求</p><h2 id="remediation-evidence-title">待补充证据</h2></div>
              <span>{data.evidence_requests.length} 项</span>
            </div>
            <div className="replica-record-list">
              {data.evidence_requests.map((item) => (
                <article key={item.id}>
                  <div><h3>{item.title}</h3><p>{item.detail}</p><small>{item.linkedCaseId} · 截止 {item.dueDate}</small></div>
                  <span>{item.owner} · {item.kind}</span>
                  <strong>{item.status}</strong>
                  <Link href={item.href}>查看证据位置</Link>
                </article>
              ))}
            </div>
          </section>

          <section className="replica-panel" aria-labelledby="remediation-gates-title">
            <div className="replica-results-head">
              <div><p className="replica-kicker">关闭门禁</p><h2 id="remediation-gates-title">关闭条件</h2></div>
              <span>{data.closure_gates.length} 项</span>
            </div>
            <div className="replica-record-list">
              {data.closure_gates.map((item) => (
                <article key={item.id}>
                  <div><h3>{item.label}</h3><p>{item.detail}</p></div>
                  <span>{item.owner}</span>
                  <strong>{item.status}</strong>
                </article>
              ))}
            </div>
          </section>

          <section className="replica-panel" aria-labelledby="remediation-timeline-title">
            <div className="replica-results-head">
              <div><p className="replica-kicker">整改时间线</p><h2 id="remediation-timeline-title">最近跟踪记录</h2></div>
              <span>{data.timeline.length} 项</span>
            </div>
            <div className="replica-record-list">
              {data.timeline.map((item) => (
                <article key={item.id}>
                  <div><h3>{item.title}</h3><p>{item.detail}</p><small>{item.time}</small></div>
                  <strong>{item.status}</strong>
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
