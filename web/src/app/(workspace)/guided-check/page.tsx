import { StatusPill } from "@/components/ui/status-pill";
import {
  guidedCheckEvidenceItems,
  guidedCheckQuestions,
  guidedCheckRiskSignals,
  guidedCheckSteps,
  guidedCheckTimeline
} from "@/lib/portal-data";
import type {
  GuidedCheckEvidenceItem,
  GuidedCheckQuestion,
  GuidedCheckRiskSignal,
  GuidedCheckStep,
  GuidedCheckTimelineItem
} from "@/lib/portal-data";

const completedStepCount = guidedCheckSteps.filter((step) => step.status === "已完成").length;
const pendingEvidenceCount = guidedCheckEvidenceItems.filter((item) => item.status !== "已就绪").length;
const readyQuestionCount = guidedCheckQuestions.filter((question) => question.status === "可提问").length;
const highRiskCount = guidedCheckRiskSignals.filter((signal) => signal.status === "高风险").length;

export default function GuidedCheckPage() {
  return (
    <main className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_22rem]">
      <section className="space-y-5">
        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-[var(--audit-shadow-card)]">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-sm font-semibold text-blue-700">AI 引导自查</p>
              <h1 className="mt-2 text-3xl font-semibold text-slate-950">AI 引导自查工作台</h1>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
                按项目范围、数据、规则、审证对话、底稿报告串联自查路径；AI 只给出带引用的审证问题和复核建议，不直接生成正式结论。
              </p>
            </div>
            <StatusPill tone="info">提示词型智能体</StatusPill>
          </div>

          <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4" aria-label="自查概览">
            <GuidedMetric label="已完成步骤" value={`${completedStepCount}/${guidedCheckSteps.length}`} />
            <GuidedMetric label="可提问模板" value={`${readyQuestionCount} 个`} />
            <GuidedMetric label="证据待处理" value={`${pendingEvidenceCount} 项`} />
            <GuidedMetric label="高风险线索" value={`${highRiskCount} 条`} />
          </div>

          <div className="mt-6 flex flex-wrap gap-3">
            <a className="audit-focus-ring inline-flex rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700" href="/chat">
              进入 AI 审证对话
            </a>
            <a className="audit-focus-ring inline-flex rounded-xl border border-blue-200 bg-white px-4 py-2.5 text-sm font-semibold text-blue-700 hover:bg-blue-50" href="/analytics">
              上传自查数据
            </a>
          </div>
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-[var(--audit-shadow-card)]" aria-labelledby="guided-steps-title">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 id="guided-steps-title" className="text-lg font-semibold text-slate-950">
                自查路径
              </h2>
              <p className="mt-1 text-sm text-slate-500">每一步只展示当前项目的真实去向，阻断项必须先补证。</p>
            </div>
            <a className="audit-focus-ring rounded-xl border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50" href="/projects">
              查看项目
            </a>
          </div>

          <ol className="mt-4 space-y-3">
            {guidedCheckSteps.map((step) => (
              <GuidedStepRow key={step.id} step={step} />
            ))}
          </ol>
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-[var(--audit-shadow-card)]" aria-labelledby="guided-questions-title">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 id="guided-questions-title" className="text-lg font-semibold text-slate-950">
                AI 提问模板
              </h2>
              <p className="mt-1 text-sm text-slate-500">一个智能体对应一个提示词，自查页只组织问题和证据边界。</p>
            </div>
            <a className="audit-focus-ring rounded-xl border border-blue-200 bg-white px-3 py-2 text-sm font-semibold text-blue-700 hover:bg-blue-50" href="/agents">
              管理智能体
            </a>
          </div>

          <div className="mt-4 hidden overflow-hidden rounded-2xl border border-slate-200 md:block">
            <table className="w-full table-fixed text-left text-sm">
              <thead className="bg-slate-50 text-slate-500">
                <tr>
                  <th scope="col" className="w-[16%] px-4 py-3 font-semibold">
                    场景
                  </th>
                  <th scope="col" className="w-[38%] px-4 py-3 font-semibold">
                    自查问题
                  </th>
                  <th scope="col" className="w-[18%] px-4 py-3 font-semibold">
                    智能体
                  </th>
                  <th scope="col" className="w-[14%] px-4 py-3 font-semibold">
                    状态
                  </th>
                  <th scope="col" className="w-[14%] px-4 py-3 font-semibold">
                    操作
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {guidedCheckQuestions.map((question) => (
                  <QuestionRow key={question.id} question={question} />
                ))}
              </tbody>
            </table>
          </div>

          <div className="mt-4 grid gap-3 md:hidden">
            {guidedCheckQuestions.map((question) => (
              <QuestionCard key={question.id} question={question} />
            ))}
          </div>
        </section>
      </section>

      <aside className="space-y-4">
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-[var(--audit-shadow-card)]" aria-labelledby="guided-evidence-title">
          <h2 id="guided-evidence-title" className="text-lg font-semibold text-slate-950">
            证据门禁
          </h2>
          <div className="mt-4 space-y-3">
            {guidedCheckEvidenceItems.map((item) => (
              <EvidenceCard key={item.id} item={item} />
            ))}
          </div>
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-[var(--audit-shadow-card)]" aria-labelledby="guided-risk-title">
          <h2 id="guided-risk-title" className="text-lg font-semibold text-slate-950">
            风险预检
          </h2>
          <div className="mt-4 space-y-3">
            {guidedCheckRiskSignals.map((signal) => (
              <RiskCard key={signal.id} signal={signal} />
            ))}
          </div>
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-[var(--audit-shadow-card)]" aria-labelledby="guided-timeline-title">
          <h2 id="guided-timeline-title" className="text-lg font-semibold text-slate-950">
            自查动态
          </h2>
          <div className="mt-4 space-y-4">
            {guidedCheckTimeline.map((item) => (
              <TimelineItem key={item.id} item={item} />
            ))}
          </div>
        </section>

        <a className="audit-focus-ring block rounded-2xl border border-blue-100 bg-blue-50 p-5" href="/findings">
          <p className="text-sm font-semibold text-blue-700">下一步</p>
          <h2 className="mt-2 text-lg font-semibold text-slate-950">查看规则命中疑点</h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">自查问题进入 AI 对话后，仍需回到疑点工作台做人工复核。</p>
        </a>
      </aside>
    </main>
  );
}

function GuidedMetric({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <p className="text-sm font-semibold text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-slate-950">{value}</p>
    </div>
  );
}

function GuidedStepRow({ step }: { readonly step: GuidedCheckStep }) {
  return (
    <li className="grid gap-3 rounded-2xl border border-slate-200 p-4 sm:grid-cols-[3.5rem_minmax(0,1fr)_7rem] sm:items-center">
      <div className="flex size-12 items-center justify-center rounded-2xl bg-slate-950 text-sm font-semibold text-white">{step.order}</div>
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-base font-semibold text-slate-950">{step.title}</h3>
          <StatusPill tone={getStepTone(step.status)}>{step.status}</StatusPill>
        </div>
        <p className="mt-1 text-sm leading-6 text-slate-600">{step.detail}</p>
        <p className="mt-1 text-xs font-semibold text-slate-500">责任人：{step.owner}</p>
      </div>
      <a className="audit-focus-ring inline-flex justify-center rounded-xl border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50" href={step.href}>
        打开
      </a>
    </li>
  );
}

function QuestionRow({ question }: { readonly question: GuidedCheckQuestion }) {
  return (
    <tr>
      <td className="px-4 py-3">
        <p className="font-semibold text-slate-950">{question.domain}</p>
        <p className="mt-1 break-words text-xs text-slate-500">{question.knowledgeScope}</p>
      </td>
      <td className="px-4 py-3 text-slate-700">{question.question}</td>
      <td className="px-4 py-3 text-slate-700">{question.agentName}</td>
      <td className="px-4 py-3">
        <StatusPill tone={getQuestionTone(question.status)}>{question.status}</StatusPill>
      </td>
      <td className="px-4 py-3">
        <a className="audit-focus-ring inline-flex whitespace-nowrap rounded-xl bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700" href={question.chatHref}>
          进入对话
        </a>
      </td>
    </tr>
  );
}

function QuestionCard({ question }: { readonly question: GuidedCheckQuestion }) {
  return (
    <article className="rounded-2xl border border-slate-200 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-semibold text-slate-950">{question.domain}</p>
        <StatusPill tone={getQuestionTone(question.status)}>{question.status}</StatusPill>
      </div>
      <p className="mt-3 text-sm leading-6 text-slate-700">{question.question}</p>
      <p className="mt-2 text-xs text-slate-500">
        {question.agentName} · {question.knowledgeScope}
      </p>
      <a className="audit-focus-ring mt-4 inline-flex rounded-xl bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700" href={question.chatHref}>
        进入对话
      </a>
    </article>
  );
}

function EvidenceCard({ item }: { readonly item: GuidedCheckEvidenceItem }) {
  return (
    <a className="audit-focus-ring block rounded-2xl border border-slate-200 p-4 hover:bg-slate-50" href={item.href}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-semibold text-slate-950">{item.title}</p>
        <StatusPill tone={getEvidenceTone(item.status)}>{item.status}</StatusPill>
      </div>
      <p className="mt-1 text-xs font-semibold text-slate-500">{item.source}</p>
      <p className="mt-2 text-sm leading-6 text-slate-600">{item.blocker}</p>
    </a>
  );
}

function RiskCard({ signal }: { readonly signal: GuidedCheckRiskSignal }) {
  return (
    <a className="audit-focus-ring block rounded-2xl border border-slate-200 p-4 hover:bg-slate-50" href={signal.href}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-slate-950">{signal.label}</p>
          <p className="mt-1 text-2xl font-semibold text-slate-950">{signal.value}</p>
        </div>
        <StatusPill tone={getRiskTone(signal.status)}>{signal.status}</StatusPill>
      </div>
      <p className="mt-2 text-sm leading-6 text-slate-600">{signal.detail}</p>
    </a>
  );
}

function TimelineItem({ item }: { readonly item: GuidedCheckTimelineItem }) {
  return (
    <article className="border-l-2 border-slate-200 pl-4">
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-xs font-semibold text-slate-500">{item.time}</p>
        <StatusPill tone={getTimelineTone(item.status)}>{item.status}</StatusPill>
      </div>
      <h3 className="mt-2 text-sm font-semibold text-slate-950">{item.title}</h3>
      <p className="mt-1 text-sm leading-6 text-slate-600">{item.detail}</p>
    </article>
  );
}

function getStepTone(status: GuidedCheckStep["status"]) {
  if (status === "已完成") {
    return "success";
  }
  if (status === "待补证") {
    return "danger";
  }
  if (status === "进行中") {
    return "info";
  }
  return "neutral";
}

function getQuestionTone(status: GuidedCheckQuestion["status"]) {
  if (status === "可提问") {
    return "success";
  }
  if (status === "需补数据") {
    return "warning";
  }
  return "info";
}

function getEvidenceTone(status: GuidedCheckEvidenceItem["status"]) {
  if (status === "已就绪") {
    return "success";
  }
  if (status === "待补证") {
    return "danger";
  }
  return "warning";
}

function getRiskTone(status: GuidedCheckRiskSignal["status"]) {
  if (status === "高风险") {
    return "danger";
  }
  if (status === "待确认") {
    return "warning";
  }
  return "success";
}

function getTimelineTone(status: GuidedCheckTimelineItem["status"]) {
  if (status === "已完成") {
    return "success";
  }
  if (status === "进行中") {
    return "info";
  }
  return "warning";
}
