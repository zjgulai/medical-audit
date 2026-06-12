import { StatusPill } from "@/components/ui/status-pill";
import {
  ruleControlGates,
  ruleLibraryItems,
  ruleRunSnapshots,
  ruleSourceCoverages
} from "@/lib/portal-data";
import type { RuleControlGate, RuleLibraryItem, RuleRunSnapshot, RuleSourceCoverage } from "@/lib/portal-data";

const enabledRuleCount = ruleLibraryItems.filter((rule) => rule.status === "已启用").length;
const pendingRuleCount = ruleLibraryItems.filter((rule) => rule.status !== "已启用").length;
const totalRuleFindingCount = ruleLibraryItems.reduce((sum, rule) => sum + rule.findingCount, 0);
const blockedGateCount = ruleControlGates.filter((gate) => gate.status === "阻断").length;

export default function RulesPage() {
  return (
    <main className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_22rem]">
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-[var(--audit-shadow-card)]">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-sm font-semibold text-blue-700">专题规则库</p>
            <h1 className="mt-2 text-3xl font-semibold text-slate-950">审计规则与依据总览</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
              汇总监管两库、医保目录、风险清单和对话审证沉淀，首期只读展示规则来源、运行状态和疑点去向。
            </p>
          </div>
          <StatusPill tone="info">首期只读</StatusPill>
        </div>

        <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <RulesMetric label="可运行规则" value={`${enabledRuleCount} 条`} />
          <RulesMetric label="待处理规则" value={`${pendingRuleCount} 条`} />
          <RulesMetric label="已生成疑点" value={`${totalRuleFindingCount} 条`} />
          <RulesMetric label="阻断门禁" value={`${blockedGateCount} 项`} />
        </div>

        <section className="mt-6" aria-labelledby="rule-library-title">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 id="rule-library-title" className="text-lg font-semibold text-slate-950">
              规则清单
            </h2>
            <a className="audit-focus-ring rounded-xl border border-blue-200 bg-white px-3 py-2 text-sm font-semibold text-blue-700 hover:bg-blue-50" href="/pages/index-admin">
              打开索引管理
            </a>
          </div>

          <div className="mt-4 hidden overflow-hidden rounded-2xl border border-slate-200 md:block">
            <table className="w-full table-fixed text-left text-sm">
              <thead className="bg-slate-50 text-slate-500">
                <tr>
                  <th scope="col" className="w-[24%] px-4 py-3 font-semibold">
                    规则
                  </th>
                  <th scope="col" className="w-[12%] px-4 py-3 font-semibold">
                    状态
                  </th>
                  <th scope="col" className="w-[18%] px-4 py-3 font-semibold">
                    来源
                  </th>
                  <th scope="col" className="w-[24%] px-4 py-3 font-semibold">
                    适用范围
                  </th>
                  <th scope="col" className="w-[10%] px-4 py-3 font-semibold">
                    疑点
                  </th>
                  <th scope="col" className="w-[12%] px-4 py-3 font-semibold">
                    操作
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {ruleLibraryItems.map((rule) => (
                  <RuleRow key={rule.id} rule={rule} />
                ))}
              </tbody>
            </table>
          </div>

          <div className="mt-4 grid gap-3 md:hidden">
            {ruleLibraryItems.map((rule) => (
              <RuleCard key={rule.id} rule={rule} />
            ))}
          </div>
        </section>

        <section className="mt-6 grid gap-5 xl:grid-cols-[minmax(0,1fr)_20rem]" aria-labelledby="rule-runs-title">
          <div>
            <h2 id="rule-runs-title" className="text-lg font-semibold text-slate-950">
              最近运行
            </h2>
            <div className="mt-4 grid gap-3 lg:grid-cols-3">
              {ruleRunSnapshots.map((snapshot) => (
                <RunSnapshotCard key={snapshot.id} snapshot={snapshot} />
              ))}
            </div>
          </div>

          <aside className="rounded-2xl border border-blue-100 bg-blue-50 p-5">
            <p className="text-sm font-semibold text-blue-700">输出边界</p>
            <h3 className="mt-2 text-lg font-semibold text-slate-950">规则命中不直接成结论</h3>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              规则只生成疑点或审证问题；是否进入底稿、报告和整改，仍由人工复核门禁决定。
            </p>
          </aside>
        </section>
      </section>

      <aside className="space-y-4">
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-[var(--audit-shadow-card)]">
          <h2 className="text-lg font-semibold text-slate-950">来源覆盖</h2>
          <div className="mt-4 space-y-3">
            {ruleSourceCoverages.map((source) => (
              <SourceCoverageCard key={source.id} source={source} />
            ))}
          </div>
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-[var(--audit-shadow-card)]">
          <h2 className="text-lg font-semibold text-slate-950">发布门禁</h2>
          <div className="mt-4 space-y-3">
            {ruleControlGates.map((gate) => (
              <RuleGateCard key={gate.id} gate={gate} />
            ))}
          </div>
        </section>

        <a className="audit-focus-ring block rounded-2xl border border-slate-200 bg-white p-5 shadow-[var(--audit-shadow-card)]" href="/graph">
          <p className="text-sm font-semibold text-blue-700">知识图谱</p>
          <h2 className="mt-2 text-lg font-semibold text-slate-950">查看规则证据链</h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">规则和文档、疑点、复核、报告的关系已进入图谱只读链路。</p>
        </a>
      </aside>
    </main>
  );
}

function RulesMetric({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <p className="text-sm font-semibold text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-slate-950">{value}</p>
    </div>
  );
}

function RuleRow({ rule }: { readonly rule: RuleLibraryItem }) {
  return (
    <tr>
      <td className="px-4 py-3">
        <p className="font-semibold text-slate-950">{rule.name}</p>
        <p className="mt-1 text-xs text-slate-500">{rule.code}</p>
      </td>
      <td className="px-4 py-3">
        <StatusPill tone={getRuleStatusTone(rule.status)}>{rule.status}</StatusPill>
      </td>
      <td className="px-4 py-3 text-slate-700">
        <p className="font-medium text-slate-900">{rule.domain}</p>
        <p className="mt-1 break-words text-xs text-slate-500">{rule.sourceCollection}</p>
      </td>
      <td className="px-4 py-3 text-slate-600">{rule.evidenceScope}</td>
      <td className="px-4 py-3 text-slate-700">
        <p>{rule.findingCount} 条</p>
        <p className="mt-1 text-xs text-slate-500">{rule.evidenceCount} 个依据</p>
      </td>
      <td className="px-4 py-3">
        <div className="flex flex-col gap-2">
          <a className="audit-focus-ring inline-flex min-w-20 items-center justify-center rounded-xl bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700" href={rule.href}>
            查看
          </a>
          <a className="audit-focus-ring inline-flex min-w-20 items-center justify-center rounded-xl border border-blue-200 bg-white px-3 py-2 text-sm font-semibold text-blue-700 hover:bg-blue-50" href={rule.chatHref}>
            审证
          </a>
        </div>
      </td>
    </tr>
  );
}

function RuleCard({ rule }: { readonly rule: RuleLibraryItem }) {
  return (
    <article className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold leading-6 text-slate-950">{rule.name}</h3>
          <p className="mt-1 text-xs text-slate-500">{rule.code}</p>
        </div>
        <StatusPill tone={getRuleStatusTone(rule.status)}>{rule.status}</StatusPill>
      </div>
      <p className="mt-3 text-sm leading-6 text-slate-600">{rule.evidenceScope}</p>
      <dl className="mt-4 grid grid-cols-2 gap-3 text-xs">
        <div>
          <dt className="font-semibold text-slate-500">来源</dt>
          <dd className="mt-1 break-words text-slate-900">{rule.sourceCollection}</dd>
        </div>
        <div>
          <dt className="font-semibold text-slate-500">责任方</dt>
          <dd className="mt-1 text-slate-900">{rule.owner}</dd>
        </div>
        <div>
          <dt className="font-semibold text-slate-500">疑点</dt>
          <dd className="mt-1 text-slate-900">{rule.findingCount} 条</dd>
        </div>
        <div>
          <dt className="font-semibold text-slate-500">更新时间</dt>
          <dd className="mt-1 text-slate-900">{rule.updatedAt}</dd>
        </div>
      </dl>
      <div className="mt-4 grid grid-cols-2 gap-2">
        <a className="audit-focus-ring inline-flex items-center justify-center rounded-xl bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700" href={rule.href}>
          查看
        </a>
        <a className="audit-focus-ring inline-flex items-center justify-center rounded-xl border border-blue-200 bg-white px-3 py-2 text-sm font-semibold text-blue-700 hover:bg-blue-50" href={rule.chatHref}>
          审证
        </a>
      </div>
    </article>
  );
}

function RunSnapshotCard({ snapshot }: { readonly snapshot: RuleRunSnapshot }) {
  return (
    <article className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-slate-950">{snapshot.ruleCode}</h3>
          <p className="mt-1 text-xs text-slate-500">
            {snapshot.inputTable} · {snapshot.lastRunAt}
          </p>
        </div>
        <StatusPill tone={snapshot.hitCount > 0 ? "warning" : "success"}>{snapshot.hitCount} 命中</StatusPill>
      </div>
      <p className="mt-3 text-sm leading-6 text-slate-600">{snapshot.linkedFinding}</p>
      <p className="mt-2 text-xs font-semibold text-blue-700">{snapshot.nextAction}</p>
    </article>
  );
}

function SourceCoverageCard({ source }: { readonly source: RuleSourceCoverage }) {
  return (
    <a className="audit-focus-ring block rounded-xl border border-slate-200 bg-slate-50 p-3 hover:bg-blue-50/70" href={source.href}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-slate-950">{source.name}</p>
          <p className="mt-1 text-xs text-slate-500">{source.sourceCollection}</p>
        </div>
        <StatusPill tone={source.indexStatus === "可引用" ? "success" : source.indexStatus === "待同步" ? "warning" : "neutral"}>
          {source.indexStatus}
        </StatusPill>
      </div>
      <p className="mt-3 text-sm leading-6 text-slate-600">{source.health}</p>
      <p className="mt-2 text-xs font-semibold text-slate-500">{source.ruleCount.toLocaleString()} 条</p>
    </a>
  );
}

function RuleGateCard({ gate }: { readonly gate: RuleControlGate }) {
  return (
    <article className="rounded-xl border border-slate-200 bg-slate-50 p-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-slate-950">{gate.label}</h3>
          <p className="mt-1 text-xs text-slate-500">责任方：{gate.owner}</p>
        </div>
        <StatusPill tone={getRuleGateTone(gate.status)}>{gate.status}</StatusPill>
      </div>
      <p className="mt-3 text-sm leading-6 text-slate-600">{gate.detail}</p>
    </article>
  );
}

function getRuleStatusTone(status: RuleLibraryItem["status"]) {
  if (status === "已启用") {
    return "success";
  }

  if (status === "待补字段" || status === "待复核") {
    return "warning";
  }

  return "neutral";
}

function getRuleGateTone(status: RuleControlGate["status"]) {
  if (status === "通过") {
    return "success";
  }

  if (status === "阻断") {
    return "danger";
  }

  return "warning";
}
