"use client";

import { useEffect, useState } from "react";

import { fetchRulesWorkbench } from "@/lib/api-client";
import type {
  RuleControlGateApiItem,
  RuleLibraryApiItem,
  RuleRunSnapshotApiItem,
  RuleSourceCoverageApiItem,
  RulesWorkbenchResponse
} from "@/lib/api-types";

import {
  ReplicaEmptyState,
  ReplicaMetric,
  ReplicaNotice,
  ReplicaPageHeader,
  ReplicaRuntimeBadge
} from "./replica-page-kit";

type RulesState =
  | { readonly status: "loading"; readonly data: null }
  | { readonly status: "ready"; readonly data: RulesWorkbenchResponse }
  | { readonly status: "empty"; readonly data: RulesWorkbenchResponse }
  | { readonly status: "error"; readonly data: null };

function RulesMetrics({ metrics }: { readonly metrics: RulesWorkbenchResponse["metrics"] }) {
  const items = [
    ["规则总数", metrics.rule_count, "blue"],
    ["已启用", metrics.enabled_rule_count, "green"],
    ["待处理", metrics.pending_rule_count, "amber"],
    ["关联疑点", metrics.total_finding_count, "rose"],
    ["阻断门禁", metrics.blocked_gate_count, "rose"],
    ["数据来源", metrics.source_count, "slate"],
    ["运行记录", metrics.run_count, "blue"]
  ] as const;

  return (
    <section className="replica-metric-grid" aria-label="规则运行指标">
      {items.map(([label, value, tone]) => (
        <ReplicaMetric key={label} label={label} value={String(value)} tone={tone} />
      ))}
    </section>
  );
}

function RuleLibrary({ items }: { readonly items: readonly RuleLibraryApiItem[] }) {
  return (
    <section className="replica-panel" aria-labelledby="rules-library-title">
      <div className="replica-results-head">
        <div>
          <p className="replica-kicker">规则库</p>
          <h2 id="rules-library-title">当前可用规则</h2>
        </div>
        <span>{items.length} 项</span>
      </div>
      {items.length === 0 ? (
        <ReplicaEmptyState title="暂无规则库记录" description="后端当前未返回可展示的规则。" />
      ) : (
        <div className="replica-kb-grid">
          {items.map((item) => <RuleCard key={item.id} item={item} />)}
        </div>
      )}
    </section>
  );
}

function RuleCard({ item }: { readonly item: RuleLibraryApiItem }) {
  return (
    <article className="replica-kb-card">
      <div className="replica-kb-card-head">
        <div>
          <span>{item.domain}</span>
          <h2>{item.name}</h2>
        </div>
        <strong>{item.status}</strong>
      </div>
      <p className="font-mono text-xs text-[var(--audit-blue)]">{item.code}</p>
      <p>{item.evidenceScope}</p>
      <dl className="replica-kb-stats">
        <div><dt>来源</dt><dd>{item.sourceCollection}</dd></div>
        <div><dt>证据</dt><dd>{item.evidenceCount}</dd></div>
        <div><dt>疑点</dt><dd>{item.findingCount}</dd></div>
        <div><dt>责任人</dt><dd>{item.owner}</dd></div>
      </dl>
      <small>更新于 {item.updatedAt}</small>
    </article>
  );
}

function SourceCoverage({ items }: { readonly items: readonly RuleSourceCoverageApiItem[] }) {
  return (
    <section className="replica-panel" aria-labelledby="rules-source-title">
      <div className="replica-results-head">
        <div>
          <p className="replica-kicker">来源覆盖</p>
          <h2 id="rules-source-title">规则证据来源</h2>
        </div>
        <span>{items.length} 项</span>
      </div>
      {items.length === 0 ? (
        <ReplicaEmptyState title="暂无来源覆盖" description="后端当前未返回规则来源覆盖信息。" />
      ) : (
        <div className="replica-kb-grid">
          {items.map((item) => <SourceCard key={item.id} item={item} />)}
        </div>
      )}
    </section>
  );
}

function SourceCard({ item }: { readonly item: RuleSourceCoverageApiItem }) {
  return (
    <article className="replica-kb-card">
      <div className="replica-kb-card-head">
        <div>
          <span>{item.sourceCollection}</span>
          <h3>{item.name}</h3>
        </div>
        <strong>{item.indexStatus}</strong>
      </div>
      <p>{item.health}</p>
      <dl className="replica-kb-stats">
        <div><dt>覆盖规则</dt><dd>{item.ruleCount}</dd></div>
      </dl>
    </article>
  );
}

function RunSnapshots({ items }: { readonly items: readonly RuleRunSnapshotApiItem[] }) {
  return (
    <section className="replica-panel" aria-labelledby="rules-runs-title">
      <div className="replica-results-head">
        <div>
          <p className="replica-kicker">运行记录</p>
          <h2 id="rules-runs-title">最近规则运行</h2>
        </div>
        <span>{items.length} 项</span>
      </div>
      {items.length === 0 ? (
        <ReplicaEmptyState title="暂无运行记录" description="当前规则库尚无可展示的只读运行快照。" />
      ) : (
        <div className="replica-record-list">
          {items.map((item) => <RunRow key={item.id} item={item} />)}
        </div>
      )}
    </section>
  );
}

function RunRow({ item }: { readonly item: RuleRunSnapshotApiItem }) {
  return (
    <article>
      <div>
        <h3>{item.id}</h3>
        <p>{item.ruleCode} · {item.inputTable}</p>
        <small>{item.lastRunAt} · {item.nextAction}</small>
      </div>
      <span>{item.linkedFinding}</span>
      <strong>{item.hitCount} 命中</strong>
    </article>
  );
}

function ControlGates({ items }: { readonly items: readonly RuleControlGateApiItem[] }) {
  return (
    <section className="replica-panel" aria-labelledby="rules-gates-title">
      <div className="replica-results-head">
        <div>
          <p className="replica-kicker">控制门禁</p>
          <h2 id="rules-gates-title">规则运行边界</h2>
        </div>
        <span>{items.length} 项</span>
      </div>
      {items.length === 0 ? (
        <ReplicaEmptyState title="暂无控制门禁" description="后端当前未返回规则控制门禁。" />
      ) : (
        <div className="replica-record-list">
          {items.map((item) => (
            <article key={item.id}>
              <div>
                <h3>{item.label}</h3>
                <p>{item.detail}</p>
              </div>
              <span>{item.owner}</span>
              <strong>{item.status}</strong>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

export function ReplicaRulesWorkbench() {
  const [state, setState] = useState<RulesState>({ status: "loading", data: null });

  useEffect(() => {
    let active = true;
    fetchRulesWorkbench()
      .then((data) => {
        if (!active) return;
        const empty = data.rule_library_items.length === 0 && data.run_snapshots.length === 0;
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
  const hasSeedData = data?.store.backend === "ReadonlyRulesWorkbenchSeed";

  return (
    <main
      className="replica-page replica-page-standard"
      data-replica-source="api"
      data-replica-status={state.status}
    >
      <ReplicaPageHeader
        kicker="规则法规库"
        title="规则运行工作台"
        description="只读展示规则库、证据来源、运行快照和执行门禁，不在此页面触发规则运行或生产写入。"
        actions={
          <ReplicaRuntimeBadge
            source="api"
            status={state.status}
            hasSeedData={hasSeedData}
          />
        }
      />

      {state.status === "loading" ? (
        <ReplicaEmptyState title="规则数据加载中" description="正在读取规则工作台的只读运行证据。" />
      ) : state.status === "error" ? (
        <ReplicaEmptyState title="规则工作台暂不可用" description="规则 API 读取失败，页面不会注入本地样例或旧统计值。" />
      ) : data ? (
        <>
          <RulesMetrics metrics={data.metrics} />
          <ReplicaNotice>
            数据后端：<strong>{data.store.backend}</strong> · store.ready={String(data.store.ready)} · evidence_grade=<strong>{data.evidence_grade}</strong> · production_side_effect=<strong>{data.production_side_effect}</strong>
          </ReplicaNotice>
          {state.status === "empty" ? (
            <ReplicaEmptyState title="暂无规则与运行记录" description="规则库和运行快照均为空；来源覆盖与控制门禁仍按后端返回结果展示。" />
          ) : null}
          <RuleLibrary items={data.rule_library_items} />
          <SourceCoverage items={data.source_coverages} />
          <RunSnapshots items={data.run_snapshots} />
          <ControlGates items={data.control_gates} />
        </>
      ) : null}
    </main>
  );
}
