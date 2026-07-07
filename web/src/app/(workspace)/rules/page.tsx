import { ReplicaMetric, ReplicaPageHeader } from "@/components/replica/replica-page-kit";

const ruleGroups = [
  {
    title: "医保目录规则",
    scope: "药品、诊疗项目、耗材和限定支付范围",
    count: "1,482",
    status: "已接入知识库"
  },
  {
    title: "基金合规法规",
    scope: "基金监管条例、经办规程和处罚依据",
    count: "936",
    status: "可用于问答引用"
  },
  {
    title: "审计疑点规则",
    scope: "超限定、重复收费、分解收费和异常组合",
    count: "128",
    status: "待人工复核"
  }
] as const;

const ruleTasks = [
  "按项目选择规则包，限定医保审计专题的知识库范围。",
  "将法规条款、目录限制和疑点规则统一映射到证据链。",
  "输出底稿前保留人工复核节点，避免规则命中直接替代审计判断。"
] as const;

export default function RulesPage() {
  return (
    <main className="space-y-6">
      <ReplicaPageHeader
        kicker="规则法规库"
        title="审计规则与知识库"
        description="围绕医保基金监管、目录支付限制和医院内审规则，统一维护法规依据、规则口径和复核边界。"
      />

      <section className="grid gap-4 md:grid-cols-3" aria-label="规则法规指标">
        <ReplicaMetric label="规则法规" value="2,546" />
        <ReplicaMetric label="知识库引用" value="49,051" tone="green" />
        <ReplicaMetric label="待复核规则" value="128" tone="amber" />
      </section>

      <section className="replica-panel">
        <div className="replica-doc-section-title">
          <div>
            <p className="replica-kicker">规则分类</p>
            <h2>医保审计规则包</h2>
          </div>
        </div>
        <div className="grid gap-4 lg:grid-cols-3">
          {ruleGroups.map((group) => (
            <article key={group.title} className="rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-white/80 p-5 shadow-[var(--audit-shadow-sm)]">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h3 className="text-base font-semibold text-[var(--audit-ink)]">{group.title}</h3>
                  <p className="mt-2 text-sm leading-6 text-[var(--audit-ink-muted)]">{group.scope}</p>
                </div>
                <strong className="text-lg text-[var(--audit-blue)]">{group.count}</strong>
              </div>
              <p className="mt-4 text-xs font-semibold text-[var(--audit-blue)]">{group.status}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="replica-panel">
        <div className="replica-doc-section-title">
          <div>
            <p className="replica-kicker">执行边界</p>
            <h2>法规、规则与人工复核</h2>
          </div>
        </div>
        <ol className="space-y-3 text-sm leading-7 text-[var(--audit-ink-muted)]">
          {ruleTasks.map((task) => (
            <li key={task} className="rounded-[var(--audit-radius-sm)] border border-[var(--audit-line)] bg-[var(--audit-soft)] px-4 py-3">
              {task}
            </li>
          ))}
        </ol>
      </section>
    </main>
  );
}
