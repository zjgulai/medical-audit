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
    <main className="audit-page-grid audit-page-grid--rail">
      <section className="audit-panel p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="audit-kicker">AI 对话</p>
            <h1 className="audit-page-title">选择智能体后进入审证对话</h1>
            <p className="mt-3 max-w-3xl audit-copy">
              门户页负责选择提示词型智能体、限定知识来源和组织审计问题；可追溯回答、引用和原文预览仍由后端审证深页执行。
            </p>
          </div>
          <StatusPill tone="success">引用约束</StatusPill>
        </div>

        <form className="audit-panel-muted mt-6 p-5" action="/pages/chat" method="get">
          <div className="grid gap-4 lg:grid-cols-[18rem_1fr]">
            <label className="block">
              <span className="audit-label">智能体</span>
              <select
                className="audit-focus-ring audit-input mt-2 bg-white px-3 py-2.5"
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
              <span className="audit-label">审计问题</span>
              <input
                className="audit-focus-ring audit-input mt-2 bg-white px-3 py-2.5"
                name="question"
                placeholder="例如：门诊超量开药应核对哪些医保审核依据？"
                required
              />
            </label>
          </div>

          <fieldset className="mt-5">
            <legend className="audit-label">知识来源</legend>
            <div className="mt-3 grid gap-3 lg:grid-cols-4">
              {sourceCollectionOptions.map((source) => (
                <label key={source.value} className="flex items-start gap-3 rounded-[var(--audit-radius-lg)] border border-[var(--audit-line)] bg-white p-4 text-sm">
                  <input className="mt-1 size-4" type="checkbox" name="source_collection" value={source.value} />
                  <span>
                    <span className="block audit-compact-title">{source.title}</span>
                    <span className="mt-1 block audit-meta">
                      {source.description}
                    </span>
                  </span>
                </label>
              ))}
            </div>
          </fieldset>

          <div className="mt-5 flex flex-wrap items-center gap-3">
            <button className="audit-focus-ring audit-btn audit-btn-primary" type="submit">
              进入审证对话
            </button>
            <a className="audit-focus-ring audit-btn audit-btn-neutral" href="/pages/chat">
              打开后端深页
            </a>
          </div>
        </form>

        <div className="mt-5 grid gap-4 lg:grid-cols-3">
          {defaultAuditAgents.map((agent) => (
            <article key={agent.id} className="audit-panel-muted p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="audit-card-title">{agent.name}</h2>
                  <p className="mt-1 audit-meta">{agent.topic}</p>
                </div>
                <StatusPill tone={agent.category === "业务类" ? "success" : "neutral"}>{agent.category}</StatusPill>
              </div>
              <p className="mt-4 audit-copy">{agent.prompt}</p>
              <a
                className="audit-focus-ring audit-btn audit-btn-secondary mt-4"
                href={`/pages/chat?agent=${agent.id}`}
              >
                用此智能体提问
              </a>
            </article>
          ))}
        </div>
      </section>

      <aside className="space-y-4">
        <section className="audit-panel-rail p-5">
          <h2 className="audit-section-title">推荐问题</h2>
          <div className="mt-4 space-y-2">
            {recommendedQuestions.map((question) => (
              <a
                key={question}
                className="audit-focus-ring audit-action-card px-3 py-2 audit-copy"
                href={`/pages/chat?question=${encodeURIComponent(question)}`}
              >
                {question}
              </a>
            ))}
          </div>
        </section>

        <section className="audit-panel-rail p-5">
          <h2 className="audit-section-title">证据边界</h2>
          <ul className="mt-4 space-y-3">
            {evidenceRules.map((rule) => (
              <li key={rule} className="audit-panel-muted px-3 py-2 audit-copy">
                {rule}
              </li>
            ))}
          </ul>
        </section>
      </aside>
    </main>
  );
}
