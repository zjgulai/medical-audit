"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useAuditUser } from "@/components/shell/audit-user-context";
import { fetchProjectDashboard, fetchProjects } from "@/lib/api-client";
import type {
  ProjectDashboardResponse,
  ProjectsResponse,
  ProjectSummaryApiItem
} from "@/lib/api-types";

type ProjectsState =
  | { readonly phase: "loading"; readonly response: null }
  | { readonly phase: "ready" | "degraded"; readonly response: ProjectsResponse }
  | { readonly phase: "error"; readonly response: null };

type DashboardState =
  | { readonly phase: "idle" | "loading"; readonly response: null }
  | { readonly phase: "ready" | "degraded"; readonly response: ProjectDashboardResponse }
  | { readonly phase: "error"; readonly response: null };

const auditStages = ["项目立项", "资料归集", "审计实施", "报告交付"] as const;

export function AuditCockpit() {
  const auditUser = useAuditUser();
  const projectsRequestRef = useRef(0);
  const dashboardRequestRef = useRef(0);
  const [projectsState, setProjectsState] = useState<ProjectsState>({ phase: "loading", response: null });
  const [dashboardState, setDashboardState] = useState<DashboardState>({ phase: "idle", response: null });
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [dashboardRetryNonce, setDashboardRetryNonce] = useState(0);

  const loadProjects = useCallback(() => {
    const requestId = ++projectsRequestRef.current;
    setProjectsState({ phase: "loading", response: null });
    fetchProjects()
      .then((response) => {
        if (requestId !== projectsRequestRef.current) return;
        setProjectsState({
          phase: response.store.ready ? "ready" : "degraded",
          response
        });
        setSelectedProjectId((current) => selectVisibleProject(current, response.items));
      })
      .catch(() => {
        if (requestId === projectsRequestRef.current) {
          setProjectsState({ phase: "error", response: null });
          setSelectedProjectId("");
        }
      });
  }, []);

  useEffect(() => {
    const projectsRequest = projectsRequestRef;
    const dashboardRequest = dashboardRequestRef;
    loadProjects();
    return () => {
      ++projectsRequest.current;
      ++dashboardRequest.current;
    };
  }, [auditUser.role, loadProjects]);

  useEffect(() => {
    if (!selectedProjectId) {
      setDashboardState({ phase: "idle", response: null });
      return;
    }
    const requestId = ++dashboardRequestRef.current;
    setDashboardState({ phase: "loading", response: null });
    fetchProjectDashboard(selectedProjectId)
      .then((response) => {
        if (requestId !== dashboardRequestRef.current) return;
        setDashboardState({
          phase: response.store.status === "ready" ? "ready" : "degraded",
          response
        });
      })
      .catch(() => {
        if (requestId === dashboardRequestRef.current) {
          setDashboardState({ phase: "error", response: null });
        }
      });
  }, [dashboardRetryNonce, selectedProjectId]);

  const projects = projectsState.response?.items ?? [];
  const selectedProject = projects.find((project) => project.id === selectedProjectId) ?? null;
  const dashboard = dashboardState.response;
  const riskCounts = useMemo(() => {
    const counts = { high: 0, medium: 0, low: 0 };
    for (const item of dashboard?.queue ?? []) counts[item.risk] += 1;
    return counts;
  }, [dashboard]);

  return (
    <main className="audit-cockpit-page">
      <header className="audit-cockpit-hero">
        <div>
          <p className="audit-cockpit-kicker">项目总览</p>
          <h1>审计驾驶舱</h1>
          <p>把项目进度、风险、待办和证据准备情况放在一个决策视图中。</p>
        </div>
        <div className="audit-cockpit-project-control">
          <label htmlFor="audit-cockpit-project">当前项目</label>
          <select
            id="audit-cockpit-project"
            disabled={projectsState.phase === "loading" || projects.length === 0}
            value={selectedProjectId}
            onChange={(event) => setSelectedProjectId(event.target.value)}
          >
            {projects.length === 0 ? <option value="">暂无可见项目</option> : null}
            {projects.map((project) => (
              <option key={project.id} value={project.id}>{project.name}</option>
            ))}
          </select>
          <Link href="/projects">进入项目管理</Link>
        </div>
      </header>

      {projectsState.phase === "loading" ? <CockpitMessage text="正在读取可见项目…" /> : null}
      {projectsState.phase === "error" ? (
        <CockpitMessage text="项目列表读取失败，请检查服务后重试。" action="重试" onAction={loadProjects} error />
      ) : null}
      {projectsState.response && projects.length === 0 ? (
        <CockpitMessage text="当前没有可见项目。请先在项目管理中创建或加入项目。" action="打开项目管理" href="/projects" />
      ) : null}
      {projectsState.phase === "degraded" ? (
        <CockpitMessage text="项目存储有限可用，驾驶舱只展示服务实际返回的数据。" />
      ) : null}

      {selectedProject ? (
        <section className="audit-cockpit-project-strip" aria-label="当前项目摘要">
          <div>
            <span>{selectedProject.status}</span>
            <h2>{selectedProject.name}</h2>
            <p>{selectedProject.organization_name} · {selectedProject.audit_topic}</p>
          </div>
          <dl>
            <div><dt>项目负责人</dt><dd>{selectedProject.creator}</dd></div>
            <div><dt>项目成员</dt><dd>{formatMemberCount(selectedProject.member_count)}</dd></div>
            <div><dt>创建日期</dt><dd>{selectedProject.created_at.slice(0, 10)}</dd></div>
          </dl>
        </section>
      ) : null}

      {dashboardState.phase === "loading" ? <CockpitMessage text="正在汇总项目驾驶舱…" /> : null}
      {dashboardState.phase === "error" ? (
        <CockpitMessage
          text="项目驾驶舱读取失败，未使用示例数据替代。"
          action="重新读取"
          onAction={() => setDashboardRetryNonce((value) => value + 1)}
          error
        />
      ) : null}

      {dashboard ? (
        <>
          <section className="audit-cockpit-metrics" aria-label="项目关键指标">
            {dashboard.metrics.length > 0 ? dashboard.metrics.map((metric) => (
              <article key={metric.key} data-tone={metric.tone}>
                <span>{metric.label}</span>
                <strong>{metric.value}</strong>
                <p>{metric.helper}</p>
              </article>
            )) : <p className="audit-cockpit-inline-empty">当前项目尚无可汇总指标。</p>}
          </section>

          <section className="audit-cockpit-grid">
            <article className="audit-cockpit-panel audit-cockpit-stage-panel">
              <div className="audit-cockpit-panel-heading">
                <div><span>项目阶段</span><h2>审计推进</h2></div>
                <small>依据项目状态展示</small>
              </div>
              <ol>
                {auditStages.map((stage, index) => {
                  const state = stageState(index, dashboard.project.status);
                  return (
                    <li key={stage} data-state={state}>
                      <span>{index + 1}</span>
                      <div><strong>{stage}</strong><small>{stageStateLabel(state)}</small></div>
                    </li>
                  );
                })}
              </ol>
            </article>

            <article className="audit-cockpit-panel">
              <div className="audit-cockpit-panel-heading">
                <div><span>风险分布</span><h2>当前待办风险</h2></div>
                <small>{dashboard.queue.length} 项</small>
              </div>
              <div className="audit-cockpit-risk-grid">
                <RiskCount label="高风险" value={riskCounts.high} tone="high" />
                <RiskCount label="中风险" value={riskCounts.medium} tone="medium" />
                <RiskCount label="低风险" value={riskCounts.low} tone="low" />
              </div>
              <p className="audit-cockpit-evidence-state">
                证据状态：{friendlyStoreStatus(dashboard.store.status)}
              </p>
            </article>
          </section>

          <section className="audit-cockpit-grid audit-cockpit-grid-wide">
            <article className="audit-cockpit-panel">
              <div className="audit-cockpit-panel-heading">
                <div><span>工作项</span><h2>优先处理</h2></div>
                <Link href={`/projects?project=${encodeURIComponent(dashboard.project.id)}`}>查看项目</Link>
              </div>
              {dashboard.queue.length > 0 ? (
                <ul className="audit-cockpit-queue">
                  {dashboard.queue.map((item) => (
                    <li key={item.id}>
                      <span data-risk={item.risk}>{riskLabel(item.risk)}</span>
                      <div><strong>{item.title}</strong><small>{item.owner} · {item.dueLabel}</small></div>
                      <em>{workItemStatus(item.status)}</em>
                    </li>
                  ))}
                </ul>
              ) : <p className="audit-cockpit-inline-empty">当前没有待处理工作项。</p>}
            </article>

            <article className="audit-cockpit-panel">
              <div className="audit-cockpit-panel-heading">
                <div><span>最近动态</span><h2>项目留痕</h2></div>
              </div>
              {dashboard.activities.length > 0 ? (
                <ul className="audit-cockpit-activities">
                  {dashboard.activities.slice(0, 5).map((activity) => (
                    <li key={activity.id}>
                      <span aria-hidden="true" />
                      <div><strong>{activity.title}</strong><p>{activity.description}</p><small>{activity.timeLabel}</small></div>
                    </li>
                  ))}
                </ul>
              ) : <p className="audit-cockpit-inline-empty">当前没有项目动态。</p>}
            </article>
          </section>

          <details className="audit-cockpit-details">
            <summary>查看数据完整性</summary>
            <dl>
              <div><dt>证据等级</dt><dd>{dashboard.evidence_grade}</dd></div>
              <div><dt>项目数据</dt><dd>{dashboard.store.status}</dd></div>
              <div><dt>成员数据</dt><dd>{dashboard.store.project_members_ready ? "就绪" : "未就绪"}</dd></div>
              <div><dt>疑点数据</dt><dd>{dashboard.store.audit_findings_ready ? "就绪" : "未就绪"}</dd></div>
            </dl>
          </details>
        </>
      ) : null}
    </main>
  );
}

function selectVisibleProject(current: string, projects: readonly ProjectSummaryApiItem[]): string {
  if (projects.some((project) => project.id === current)) return current;
  return projects.find((project) => project.status === "进行中")?.id ?? projects[0]?.id ?? "";
}

function formatMemberCount(value: number | null): string {
  return value === null ? "待同步" : `${value} 人`;
}

function stageState(index: number, status: ProjectSummaryApiItem["status"]): "done" | "current" | "pending" {
  const currentIndex = status === "待开始" ? 0 : status === "进行中" ? 2 : auditStages.length;
  if (index < currentIndex) return "done";
  if (index === currentIndex) return "current";
  return "pending";
}

function stageStateLabel(value: "done" | "current" | "pending"): string {
  if (value === "done") return "已完成";
  if (value === "current") return "当前阶段";
  return "待开始";
}

function friendlyStoreStatus(value: ProjectDashboardResponse["store"]["status"]): string {
  if (value === "ready") return "项目证据已同步";
  if (value === "partial") return "部分证据待同步";
  return "项目证据暂不可用";
}

function riskLabel(value: ProjectDashboardResponse["queue"][number]["risk"]): string {
  if (value === "high") return "高";
  if (value === "medium") return "中";
  return "低";
}

function workItemStatus(value: ProjectDashboardResponse["queue"][number]["status"]): string {
  if (value === "closed") return "已完成";
  if (value === "blocked") return "受阻";
  return "待处理";
}

function RiskCount({ label, value, tone }: { readonly label: string; readonly value: number; readonly tone: string }) {
  return <div data-tone={tone}><strong>{value}</strong><span>{label}</span></div>;
}

function CockpitMessage({
  text,
  action,
  href,
  onAction,
  error = false
}: {
  readonly text: string;
  readonly action?: string;
  readonly href?: string;
  readonly onAction?: () => void;
  readonly error?: boolean;
}) {
  return (
    <section className={`audit-cockpit-message ${error ? "is-error" : ""}`} role={error ? "alert" : "status"}>
      <p>{text}</p>
      {action && href ? <Link href={href}>{action}</Link> : null}
      {action && onAction ? <button type="button" onClick={onAction}>{action}</button> : null}
    </section>
  );
}
