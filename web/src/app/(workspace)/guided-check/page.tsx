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
    <main className="audit-page-grid audit-page-grid--rail">
      <section className="space-y-5">
        <section className="audit-panel p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="audit-kicker">AI 引导自查</p>
              <h1 className="audit-page-title">AI 引导自查工作台</h1>
              <p className="audit-copy mt-2 max-w-3xl">
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
            <a className="audit-focus-ring audit-btn audit-btn-primary" href="/chat">
              进入 AI 审证对话
            </a>
            <a className="audit-focus-ring audit-btn audit-btn-secondary" href="/analytics">
              上传自查数据
            </a>
          </div>
        </section>

        <section className="audit-panel p-6" aria-labelledby="guided-steps-title">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 id="guided-steps-title" className="audit-section-title">
                自查路径
              </h2>
              <p className="audit-copy mt-1">每一步只展示当前项目的真实去向，阻断项必须先补证。</p>
            </div>
            <a className="audit-focus-ring audit-btn audit-btn-neutral" href="/projects">
              查看项目
            </a>
          </div>

          <ol className="mt-4 space-y-3">
            {guidedCheckSteps.map((step) => (
              <GuidedStepRow key={step.id} step={step} />
            ))}
          </ol>
        </section>

        <section className="audit-panel p-6" aria-labelledby="guided-questions-title">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 id="guided-questions-title" className="audit-section-title">
                AI 提问模板
              </h2>
              <p className="audit-copy mt-1">一个智能体对应一个提示词，自查页只组织问题和证据边界。</p>
            </div>
            <a className="audit-focus-ring audit-btn audit-btn-secondary" href="/agents">
              管理智能体
            </a>
          </div>

          <div className="audit-table-shell mt-4 hidden md:block">
            <table className="audit-table table-fixed">
              <thead>
                <tr>
                  <th scope="col" className="w-[16%]">
                    场景
                  </th>
                  <th scope="col" className="w-[38%]">
                    自查问题
                  </th>
                  <th scope="col" className="w-[18%]">
                    智能体
                  </th>
                  <th scope="col" className="w-[14%]">
                    状态
                  </th>
                  <th scope="col" className="w-[14%]">
                    操作
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--audit-line-soft)]">
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
        <section className="audit-panel-rail p-5" aria-labelledby="guided-evidence-title">
          <h2 id="guided-evidence-title" className="audit-section-title">
            证据门禁
          </h2>
          <div className="mt-4 space-y-3">
            {guidedCheckEvidenceItems.map((item) => (
              <EvidenceCard key={item.id} item={item} />
            ))}
          </div>
        </section>

        <section className="audit-panel-rail p-5" aria-labelledby="guided-risk-title">
          <h2 id="guided-risk-title" className="audit-section-title">
            风险预检
          </h2>
          <div className="mt-4 space-y-3">
            {guidedCheckRiskSignals.map((signal) => (
              <RiskCard key={signal.id} signal={signal} />
            ))}
          </div>
        </section>

        <section className="audit-panel-rail p-5" aria-labelledby="guided-timeline-title">
          <h2 id="guided-timeline-title" className="audit-section-title">
            自查动态
          </h2>
          <div className="mt-4 space-y-4">
            {guidedCheckTimeline.map((item) => (
              <TimelineItem key={item.id} item={item} />
            ))}
          </div>
        </section>

        <a className="audit-focus-ring audit-callout block p-5" href="/findings">
          <p className="audit-kicker">下一步</p>
          <h2 className="audit-section-title mt-2">查看规则命中疑点</h2>
          <p className="audit-copy mt-2">自查问题进入 AI 对话后，仍需回到疑点工作台做人工复核。</p>
        </a>
      </aside>
    </main>
  );
}

function GuidedMetric({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <div className="audit-panel-muted p-4">
      <p className="audit-label">{label}</p>
      <p className="audit-metric-value mt-2">{value}</p>
    </div>
  );
}

function GuidedStepRow({ step }: { readonly step: GuidedCheckStep }) {
  return (
    <li className="grid gap-3 rounded-[var(--audit-radius-lg)] border border-[var(--audit-line)] bg-[var(--audit-surface-muted)] p-4 sm:grid-cols-[3.5rem_minmax(0,1fr)_7rem] sm:items-center">
      <div className="flex size-12 items-center justify-center rounded-[var(--audit-radius-md)] bg-[var(--audit-ink)] text-sm font-semibold text-white">{step.order}</div>
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="audit-card-title">{step.title}</h3>
          <StatusPill tone={getStepTone(step.status)}>{step.status}</StatusPill>
        </div>
        <p className="audit-copy mt-1">{step.detail}</p>
        <p className="audit-meta mt-1 font-semibold">责任人：{step.owner}</p>
      </div>
      <a className="audit-focus-ring audit-btn audit-btn-neutral" href={step.href}>
        打开
      </a>
    </li>
  );
}

function QuestionRow({ question }: { readonly question: GuidedCheckQuestion }) {
  return (
    <tr>
      <td>
        <p className="font-semibold text-[var(--audit-ink)]">{question.domain}</p>
        <p className="audit-meta mt-1 break-words">{question.knowledgeScope}</p>
      </td>
      <td className="text-[var(--audit-ink-muted)]">{question.question}</td>
      <td className="text-[var(--audit-ink-muted)]">{question.agentName}</td>
      <td>
        <StatusPill tone={getQuestionTone(question.status)}>{question.status}</StatusPill>
      </td>
      <td>
        <a className="audit-focus-ring audit-btn audit-btn-primary whitespace-nowrap" href={question.chatHref}>
          进入对话
        </a>
      </td>
    </tr>
  );
}

function QuestionCard({ question }: { readonly question: GuidedCheckQuestion }) {
  return (
    <article className="audit-panel-muted p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="audit-compact-title">{question.domain}</p>
        <StatusPill tone={getQuestionTone(question.status)}>{question.status}</StatusPill>
      </div>
      <p className="audit-copy mt-3">{question.question}</p>
      <p className="audit-meta mt-2">
        {question.agentName} · {question.knowledgeScope}
      </p>
      <a className="audit-focus-ring audit-btn audit-btn-primary mt-4" href={question.chatHref}>
        进入对话
      </a>
    </article>
  );
}

function EvidenceCard({ item }: { readonly item: GuidedCheckEvidenceItem }) {
  return (
    <a className="audit-focus-ring block rounded-[var(--audit-radius-lg)] border border-[var(--audit-line)] bg-[var(--audit-surface-muted)] p-4 hover:bg-[var(--audit-primary-soft)]" href={item.href}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="audit-compact-title">{item.title}</p>
        <StatusPill tone={getEvidenceTone(item.status)}>{item.status}</StatusPill>
      </div>
      <p className="audit-meta mt-1 font-semibold">{item.source}</p>
      <p className="audit-copy mt-2">{item.blocker}</p>
    </a>
  );
}

function RiskCard({ signal }: { readonly signal: GuidedCheckRiskSignal }) {
  return (
    <a className="audit-focus-ring block rounded-[var(--audit-radius-lg)] border border-[var(--audit-line)] bg-[var(--audit-surface-muted)] p-4 hover:bg-[var(--audit-primary-soft)]" href={signal.href}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="audit-compact-title">{signal.label}</p>
          <p className="audit-metric-value mt-1">{signal.value}</p>
        </div>
        <StatusPill tone={getRiskTone(signal.status)}>{signal.status}</StatusPill>
      </div>
      <p className="audit-copy mt-2">{signal.detail}</p>
    </a>
  );
}

function TimelineItem({ item }: { readonly item: GuidedCheckTimelineItem }) {
  return (
    <article className="border-l-2 border-[var(--audit-line)] pl-4">
      <div className="flex flex-wrap items-center gap-2">
        <p className="audit-meta font-semibold">{item.time}</p>
        <StatusPill tone={getTimelineTone(item.status)}>{item.status}</StatusPill>
      </div>
      <h3 className="audit-compact-title mt-2">{item.title}</h3>
      <p className="audit-copy mt-1">{item.detail}</p>
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
