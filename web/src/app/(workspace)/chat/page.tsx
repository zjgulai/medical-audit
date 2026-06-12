import { StatusPill } from "@/components/ui/status-pill";
import { defaultAuditAgents } from "@/lib/portal-data";

const recommendedQuestions = [
  "门诊超量开药应核对哪些医保审核依据？",
  "重复收费疑点应如何核验证据链？",
  "诊疗项目收费与目录限制如何交叉审核？"
] as const;

const evidenceRules = [
  "没有引用依据时，只输出待补证据状态。",
  "回答进入底稿前，必须打开原文核验适用条件。",
  "不要输入患者姓名、证件号、手机号等直接身份标识。"
] as const;

const sourceCollectionOptions = [
  {
    value: "medical-insurance-laws",
    title: "法规政策",
    description: "医保、医疗、药品、基金监管相关法律政策。"
  },
  {
    value: "supervision-rules-knowledge",
    title: "监管两库",
    description: "智能监管规则库、知识库和知识点明细。"
  },
  {
    value: "medical-insurance-catalog",
    title: "医保目录",
    description: "药品、诊疗项目、编码、支付范围和限制条件。"
  },
  {
    value: "risk-negative-list",
    title: "风险清单",
    description: "高风险负面清单、案例和风险线索。"
  }
] as const;

export default function ChatPortalPage() {
  return (
    <main className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_23rem]">
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-[var(--audit-shadow-card)]">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-sm font-semibold text-blue-700">AI 对话</p>
            <h1 className="mt-2 text-3xl font-semibold text-slate-950">选择智能体后进入审证对话</h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">
              门户页负责选择提示词型智能体、限定知识来源和组织审计问题；可追溯回答、引用和原文预览仍由后端审证深页执行。
            </p>
          </div>
          <StatusPill tone="success">引用约束</StatusPill>
        </div>

        <form className="mt-6 rounded-2xl border border-slate-200 bg-slate-50 p-5" action="/pages/chat" method="get">
          <div className="grid gap-4 lg:grid-cols-[18rem_1fr]">
            <label className="block">
              <span className="text-sm font-semibold text-slate-700">智能体</span>
              <select
                className="audit-focus-ring mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm"
                name="agent"
                defaultValue={defaultAuditAgents[0]?.id}
              >
                {defaultAuditAgents.map((agent) => (
                  <option key={agent.id} value={agent.id}>
                    {agent.name}
                  </option>
                ))}
              </select>
            </label>

            <label className="block">
              <span className="text-sm font-semibold text-slate-700">审计问题</span>
              <input
                className="audit-focus-ring mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm"
                name="question"
                placeholder="例如：门诊超量开药应核对哪些医保审核依据？"
                required
              />
            </label>
          </div>

          <fieldset className="mt-5">
            <legend className="text-sm font-semibold text-slate-700">知识来源</legend>
            <div className="mt-3 grid gap-3 lg:grid-cols-4">
              {sourceCollectionOptions.map((source) => (
                <label key={source.value} className="flex items-start gap-3 rounded-2xl border border-slate-200 bg-white p-4 text-sm">
                  <input className="mt-1 size-4" type="checkbox" name="source_collection" value={source.value} />
                  <span>
                    <span className="block font-semibold text-slate-950">{source.title}</span>
                    <span className="mt-1 block text-xs leading-5 text-slate-500">
                      {source.description}
                    </span>
                  </span>
                </label>
              ))}
            </div>
          </fieldset>

          <div className="mt-5 flex flex-wrap items-center gap-3">
            <button className="audit-focus-ring rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700" type="submit">
              进入审证对话
            </button>
            <a className="audit-focus-ring rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50" href="/pages/chat">
              打开后端深页
            </a>
          </div>
        </form>

        <div className="mt-5 grid gap-4 lg:grid-cols-3">
          {defaultAuditAgents.map((agent) => (
            <article key={agent.id} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-base font-semibold text-slate-950">{agent.name}</h2>
                  <p className="mt-1 text-xs text-slate-500">{agent.topic}</p>
                </div>
                <StatusPill tone={agent.category === "业务类" ? "success" : "neutral"}>{agent.category}</StatusPill>
              </div>
              <p className="mt-4 text-sm leading-6 text-slate-700">{agent.prompt}</p>
              <a
                className="audit-focus-ring mt-4 inline-flex rounded-xl bg-white px-3 py-2 text-sm font-semibold text-blue-700 ring-1 ring-blue-100 hover:bg-blue-50"
                href={`/pages/chat?agent=${agent.id}`}
              >
                用此智能体提问
              </a>
            </article>
          ))}
        </div>
      </section>

      <aside className="space-y-4">
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-[var(--audit-shadow-card)]">
          <h2 className="text-lg font-semibold text-slate-950">推荐问题</h2>
          <div className="mt-4 space-y-2">
            {recommendedQuestions.map((question) => (
              <a
                key={question}
                className="audit-focus-ring block rounded-xl bg-slate-50 px-3 py-2 text-sm text-slate-700 hover:bg-slate-100"
                href={`/pages/chat?question=${encodeURIComponent(question)}`}
              >
                {question}
              </a>
            ))}
          </div>
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-[var(--audit-shadow-card)]">
          <h2 className="text-lg font-semibold text-slate-950">证据边界</h2>
          <ul className="mt-4 space-y-3 text-sm leading-6 text-slate-600">
            {evidenceRules.map((rule) => (
              <li key={rule} className="rounded-xl bg-slate-50 px-3 py-2">
                {rule}
              </li>
            ))}
          </ul>
        </section>
      </aside>
    </main>
  );
}
