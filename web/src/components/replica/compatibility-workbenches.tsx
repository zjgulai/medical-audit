"use client";

import Link from "next/link";

import {
  ReplicaMetric,
  ReplicaNotice,
  ReplicaPageHeader
} from "@/components/replica/replica-page-kit";
import {
  archiveAuditRuns,
  archivePackages,
  archivePolicyItems,
  archiveSignatureItems,
  archiveTimeline,
  auditTableTemplates,
  guidedCheckEvidenceItems,
  guidedCheckQuestions,
  guidedCheckRiskSignals,
  guidedCheckSteps,
  guidedCheckTimeline
} from "@/lib/portal-data";

export function FundComplianceWorkbench() {
  return (
    <main className="replica-page" data-replica-source="compatibility-route" data-replica-status="ready">
      <ReplicaPageHeader
        kicker="医保审计"
        title="医保基金使用合规"
        description="旧基金合规入口保留为专题首页，聚合医保审计、三张费用表单、引导核查和底稿归档入口。"
        actions={<Link className="replica-primary-button" href="/medical-audit">进入医保审计</Link>}
      />

      <section className="replica-metric-grid" aria-label="医保基金使用合规概览">
        <ReplicaMetric label="费用表单" value={`${auditTableTemplates.length}`} />
        <ReplicaMetric label="核查步骤" value={`${guidedCheckSteps.length}`} tone="green" />
        <ReplicaMetric label="风险信号" value={`${guidedCheckRiskSignals.length}`} tone="amber" />
        <ReplicaMetric label="归档包" value={`${archivePackages.length}`} tone="slate" />
      </section>

      <section className="replica-report-layout">
        <div className="replica-panel">
          <div className="replica-results-head">
            <div>
              <p className="replica-kicker">专题路径</p>
              <h2>医保审计闭环</h2>
            </div>
            <span>规则、表单、底稿、归档</span>
          </div>
          <div className="replica-kb-grid">
            {[
              { title: "医保审计", detail: "进入专项工作台查看规则维度、疑点列表和三张表单。", href: "/medical-audit" },
              { title: "复核表单", detail: "按费用汇总、分类汇总、就诊明细三类模板组织复核。", href: "/fund-compliance/review" },
              { title: "引导式核查", detail: "按步骤梳理数据、规则、AI 对话和报告门禁。", href: "/guided-check" },
              { title: "项目档案", detail: "查看归档包、签名链、保留策略和阻断项。", href: "/archive" }
            ].map((item) => (
              <article key={item.href} className="replica-kb-card">
                <div className="replica-kb-card-head">
                  <div>
                    <span>专题入口</span>
                    <h2>{item.title}</h2>
                  </div>
                </div>
                <p>{item.detail}</p>
                <div className="replica-card-actions">
                  <Link className="replica-card-detail-button" href={item.href}>打开</Link>
                </div>
              </article>
            ))}
          </div>
        </div>

        <div className="replica-panel">
          <div className="replica-results-head">
            <div>
              <p className="replica-kicker">表单模板</p>
              <h2>医保费用复核表</h2>
            </div>
            <Link href="/fund-compliance/review">查看全部</Link>
          </div>
          <div className="replica-record-list">
            {auditTableTemplates.map((template) => (
              <article key={template.id}>
                <div>
                  <h3>{template.name}</h3>
                  <p>{template.auditUse}</p>
                </div>
                <span>{template.shortName}</span>
                <strong>{template.expectedColumns.length} 列</strong>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="replica-panel">
        <div className="replica-results-head">
          <div>
            <p className="replica-kicker">风险信号</p>
            <h2>当前核查重点</h2>
          </div>
          <span>{guidedCheckRiskSignals.length} 项</span>
        </div>
        <div className="replica-kb-grid">
          {guidedCheckRiskSignals.map((signal) => (
            <article key={signal.id} className="replica-kb-card">
              <div className="replica-kb-card-head">
                <div>
                  <span>{signal.status}</span>
                  <h2>{signal.label}</h2>
                </div>
                <strong>{signal.value}</strong>
              </div>
              <p>{signal.detail}</p>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}

export function FundComplianceReviewWorkbench() {
  return (
    <main className="replica-page" data-replica-source="compatibility-route" data-replica-status="ready">
      <ReplicaPageHeader
        kicker="医保基金使用合规"
        title="医保基金复核表单"
        description="保留三类费用模板的产品入口，后续上传和分析继续在 AI 数据分析、医保审计工作台中完成。"
        actions={<Link className="replica-primary-button" href="/medical-audit">返回医保审计</Link>}
      />

      <section className="replica-metric-grid" aria-label="医保基金复核表单概览">
        <ReplicaMetric label="表单样式" value={`${auditTableTemplates.length}`} />
        <ReplicaMetric label="明细列数" value={`${auditTableTemplates.reduce((sum, item) => sum + item.expectedColumns.length, 0)}`} tone="green" />
        <ReplicaMetric label="分析入口" value="AI数据分析" tone="amber" />
        <ReplicaMetric label="底稿入口" value="报告" tone="slate" />
      </section>

      <section className="replica-kb-grid" aria-label="医保基金复核表单列表">
        {auditTableTemplates.map((template) => (
          <article key={template.id} className="replica-kb-card" aria-label={template.name}>
            <div className="replica-kb-card-head">
              <div>
                <span>{template.shortName}</span>
                <h2>{template.name}</h2>
              </div>
              <strong>{template.sheetName}</strong>
            </div>
            <p>{template.auditUse}</p>
            <dl className="replica-kb-stats">
              <div>
                <dt>文件模板</dt>
                <dd>{template.fileName}</dd>
              </div>
              <div>
                <dt>字段数量</dt>
                <dd>{template.expectedColumns.length}</dd>
              </div>
            </dl>
            <div className="replica-kb-tags">
              {template.keyChecks.map((check) => (
                <span key={check}>{check}</span>
              ))}
            </div>
            <div className="replica-card-actions">
              <Link className="replica-card-detail-button" href={`/analytics?template=${template.id}`}>进入分析</Link>
              <Link className="replica-card-detail-button" href={`/chat?question=${encodeURIComponent(template.analysisRequest)}`}>生成问题</Link>
            </div>
          </article>
        ))}
      </section>

      <ReplicaNotice>复核表单页面只组织模板与入口，真实上传、解析和底稿生成仍走受控 API 与人工复核流程。</ReplicaNotice>
    </main>
  );
}

export function GuidedCheckWorkbench() {
  return (
    <main className="replica-page" data-replica-source="compatibility-route" data-replica-status="ready">
      <ReplicaPageHeader
        kicker="引导自查"
        title="引导式核查"
        description="按医保基金使用合规专题的真实工作顺序，把数据、规则、AI 审证、底稿和归档串成可执行路径。"
        actions={<Link className="replica-primary-button" href="/chat">进入 AI 对话</Link>}
      />

      <section className="replica-metric-grid" aria-label="引导式核查概览">
        <ReplicaMetric label="核查步骤" value={`${guidedCheckSteps.length}`} />
        <ReplicaMetric label="审证问题" value={`${guidedCheckQuestions.length}`} tone="green" />
        <ReplicaMetric label="证据材料" value={`${guidedCheckEvidenceItems.length}`} tone="amber" />
        <ReplicaMetric label="风险信号" value={`${guidedCheckRiskSignals.length}`} tone="rose" />
      </section>

      <section className="replica-report-layout">
        <div className="replica-panel">
          <div className="replica-results-head">
            <div>
              <p className="replica-kicker">核查步骤</p>
              <h2>从项目到归档</h2>
            </div>
            <span>人工复核边界保留</span>
          </div>
          <div className="replica-record-list">
            {guidedCheckSteps.map((step) => (
              <article key={step.id}>
                <div>
                  <h3>{step.order} · {step.title}</h3>
                  <p>{step.detail}</p>
                </div>
                <span>{step.status}</span>
                <strong>{step.owner}</strong>
                <div className="replica-record-actions">
                  <Link href={step.href}>打开</Link>
                </div>
              </article>
            ))}
          </div>
        </div>

        <div className="replica-panel">
          <div className="replica-results-head">
            <div>
              <p className="replica-kicker">AI 审证问题</p>
              <h2>可直接带入对话</h2>
            </div>
            <span>{guidedCheckQuestions.length} 条</span>
          </div>
          <div className="replica-record-list">
            {guidedCheckQuestions.map((item) => (
              <article key={item.id}>
                <div>
                  <h3>{item.domain}</h3>
                  <p>{item.question}</p>
                </div>
                <span>{item.status}</span>
                <strong>{item.agentName}</strong>
                <div className="replica-record-actions">
                  <Link href={item.chatHref}>提问</Link>
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="replica-panel">
        <div className="replica-results-head">
          <div>
            <p className="replica-kicker">证据与风险</p>
            <h2>材料准备状态</h2>
          </div>
          <span>{guidedCheckEvidenceItems.length} 项材料</span>
        </div>
        <div className="replica-kb-grid">
          {guidedCheckEvidenceItems.map((item) => (
            <article key={item.id} className="replica-kb-card">
              <div className="replica-kb-card-head">
                <div>
                  <span>{item.source}</span>
                  <h2>{item.title}</h2>
                </div>
                <strong>{item.status}</strong>
              </div>
              <p>{item.blocker}</p>
              <div className="replica-card-actions">
                <Link className="replica-card-detail-button" href={item.href}>查看</Link>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="replica-panel">
        <div className="replica-results-head">
          <div>
            <p className="replica-kicker">核查时间线</p>
            <h2>最近进展</h2>
          </div>
          <span>{guidedCheckTimeline.length} 条</span>
        </div>
        <div className="replica-record-list">
          {guidedCheckTimeline.map((item) => (
            <article key={item.id}>
              <div>
                <h3>{item.title}</h3>
                <p>{item.detail}</p>
              </div>
              <span>{item.status}</span>
              <strong>{item.time}</strong>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}

export function ArchiveWorkbench() {
  return (
    <main className="replica-page" data-replica-source="compatibility-route" data-replica-status="ready">
      <ReplicaPageHeader
        kicker="项目归档"
        title="项目档案归档"
        description="按项目档案包、签名链、巡检记录和归档策略组织生产只读证据，避免把报告、整改和日志混在一个页面里。"
        actions={<Link className="replica-primary-button" href="/reports">查看底稿报告</Link>}
      />

      <section className="replica-metric-grid" aria-label="项目档案归档概览">
        <ReplicaMetric label="归档包" value={`${archivePackages.length}`} />
        <ReplicaMetric label="巡检记录" value={`${archiveAuditRuns.length}`} tone="green" />
        <ReplicaMetric label="签名链" value={`${archiveSignatureItems.length}`} tone="amber" />
        <ReplicaMetric label="策略项" value={`${archivePolicyItems.length}`} tone="slate" />
      </section>

      <section className="replica-report-layout">
        <div className="replica-panel">
          <div className="replica-results-head">
            <div>
              <p className="replica-kicker">归档包</p>
              <h2>项目档案包</h2>
            </div>
            <span>{archivePackages.length} 个</span>
          </div>
          <div className="replica-record-list">
            {archivePackages.map((item) => (
              <article key={item.id}>
                <div>
                  <h3>{item.projectName}</h3>
                  <p>{item.archiveScope}</p>
                </div>
                <span>{item.status}</span>
                <strong>{item.archiveNo}</strong>
                <div className="replica-record-actions">
                  <Link href={item.href}>查看来源</Link>
                </div>
              </article>
            ))}
          </div>
        </div>

        <div className="replica-panel" id="archive-policy-title">
          <div className="replica-results-head">
            <div>
              <p className="replica-kicker">审计日志与策略</p>
              <h2>归档策略</h2>
            </div>
            <span>{archivePolicyItems.length} 项</span>
          </div>
          <div className="replica-kb-grid">
            {archivePolicyItems.map((item) => (
              <article key={item.id} className="replica-kb-card">
                <div className="replica-kb-card-head">
                  <div>
                    <span>{item.label}</span>
                    <h2>{item.value}</h2>
                  </div>
                </div>
                <p>{item.detail}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="replica-report-layout">
        <div className="replica-panel">
          <div className="replica-results-head">
            <div>
              <p className="replica-kicker">验签与巡检</p>
              <h2>签名链状态</h2>
            </div>
            <span>{archiveSignatureItems.length} 项</span>
          </div>
          <div className="replica-record-list">
            {archiveSignatureItems.map((item) => (
              <article key={item.id}>
                <div>
                  <h3>{item.label}</h3>
                  <p>{item.detail}</p>
                </div>
                <span>{item.status}</span>
                <strong>{item.sha256}</strong>
              </article>
            ))}
          </div>
        </div>

        <div className="replica-panel">
          <div className="replica-results-head">
            <div>
              <p className="replica-kicker">归档时间线</p>
              <h2>最近归档事件</h2>
            </div>
            <span>{archiveTimeline.length} 条</span>
          </div>
          <div className="replica-record-list">
            {archiveTimeline.map((item) => (
              <article key={item.id}>
                <div>
                  <h3>{item.title}</h3>
                  <p>{item.detail}</p>
                </div>
                <span>{item.status}</span>
                <strong>{item.time}</strong>
              </article>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}
