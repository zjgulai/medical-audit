"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useAuditUser } from "@/components/shell/audit-user-context";
import {
  createProjectMember,
  fetchProjectDashboard,
  fetchProjectMembers,
  fetchProjects
} from "@/lib/api-client";
import type {
  ApiProjectMemberRole,
  ApiProjectMemberStatus,
  ApiProjectStatus,
  ProjectDashboardResponse,
  ProjectMembersResponse,
  ProjectsResponse,
  ProjectSummaryApiItem
} from "@/lib/api-types";
import type { AuditClientRole } from "@/lib/audit-user";

type ListPhase = "loading" | "ready" | "empty" | "degraded" | "error";
type DetailPhase = "idle" | "loading" | "ready" | "empty" | "degraded" | "error";

type ProjectsState = {
  readonly phase: ListPhase;
  readonly response: ProjectsResponse | null;
  readonly role: AuditClientRole | null;
};

type MembersState = {
  readonly phase: DetailPhase;
  readonly response: ProjectMembersResponse | null;
};

type DashboardPhase = "idle" | "loading" | "ready" | "empty" | "partial" | "unavailable" | "error";

type DashboardState = {
  readonly phase: DashboardPhase;
  readonly response: ProjectDashboardResponse | null;
};

const initialProjectsState: ProjectsState = { phase: "loading", response: null, role: null };
const initialMembersState: MembersState = { phase: "idle", response: null };
const initialDashboardState: DashboardState = { phase: "idle", response: null };
const emptyProjects: readonly ProjectSummaryApiItem[] = [];

export function ReplicaProjectWorkbench() {
  const auditUser = useAuditUser();
  const [projectsState, setProjectsState] = useState<ProjectsState>(initialProjectsState);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<ApiProjectStatus | "全部">("全部");
  const [membersState, setMembersState] = useState<MembersState>(initialMembersState);
  const [dashboardState, setDashboardState] = useState<DashboardState>(initialDashboardState);
  const [userIdentifier, setUserIdentifier] = useState("");
  const [memberName, setMemberName] = useState("");
  const [memberRole, setMemberRole] = useState<ApiProjectMemberRole>("审计员");
  const [memberDepartment, setMemberDepartment] = useState("");
  const [memberStatus, setMemberStatus] = useState<ApiProjectMemberStatus>("在项目中");
  const [memberSaving, setMemberSaving] = useState(false);
  const [memberCreateError, setMemberCreateError] = useState<string | null>(null);
  const projectsRequestRef = useRef(0);
  const membersRequestRef = useRef(0);
  const dashboardRequestRef = useRef(0);
  const selectionGenerationRef = useRef(0);

  const loadProjects = useCallback((role: AuditClientRole) => {
    const requestId = ++projectsRequestRef.current;
    setProjectsState({ phase: "loading", response: null, role });
    fetchProjects()
      .then((response) => {
        if (requestId !== projectsRequestRef.current) return;
        if (!response.store.ready) {
          setProjectsState({ phase: "degraded", response, role });
          return;
        }
        setProjectsState({
          phase: response.items.length === 0 ? "empty" : "ready",
          response,
          role
        });
      })
      .catch(() => {
        if (requestId === projectsRequestRef.current) {
          setProjectsState({ phase: "error", response: null, role });
        }
      });
  }, []);

  useEffect(() => {
    ++selectionGenerationRef.current;
    ++membersRequestRef.current;
    ++dashboardRequestRef.current;
    setSelectedProjectId(null);
    setStatusFilter("全部");
    setMembersState(initialMembersState);
    setDashboardState(initialDashboardState);
    setMemberSaving(false);
    setMemberCreateError(null);
    loadProjects(auditUser.role);
  }, [auditUser.role, loadProjects]);

  const loadMembers = useCallback((projectId: string) => {
    const requestId = ++membersRequestRef.current;
    setMembersState({ phase: "loading", response: null });
    fetchProjectMembers(projectId)
      .then((response) => {
        if (requestId !== membersRequestRef.current) return;
        if (!response.store.ready) {
          setMembersState({ phase: "degraded", response });
          return;
        }
        setMembersState({ phase: response.items.length === 0 ? "empty" : "ready", response });
      })
      .catch(() => {
        if (requestId === membersRequestRef.current) {
          setMembersState({ phase: "error", response: null });
        }
      });
  }, []);

  const loadDashboard = useCallback((projectId: string) => {
    const requestId = ++dashboardRequestRef.current;
    setDashboardState({ phase: "loading", response: null });
    fetchProjectDashboard(projectId)
      .then((response) => {
        if (requestId !== dashboardRequestRef.current) return;
        if (response.store.status === "unavailable") {
          setDashboardState({ phase: "unavailable", response });
          return;
        }
        if (response.store.status === "partial") {
          setDashboardState({ phase: "partial", response });
          return;
        }
        setDashboardState({
          phase: dashboardIsEmpty(response) ? "empty" : "ready",
          response
        });
      })
      .catch(() => {
        if (requestId === dashboardRequestRef.current) {
          setDashboardState({ phase: "error", response: null });
        }
      });
  }, []);

  const roleScopedProjectsState = projectsState.role === auditUser.role
    ? projectsState
    : { phase: "loading", response: null, role: auditUser.role } satisfies ProjectsState;
  const projects = roleScopedProjectsState.response?.items ?? emptyProjects;
  const selectedProject = projects.find((item) => item.id === selectedProjectId) ?? null;
  const filteredProjects = useMemo(
    () => projects.filter((item) => statusFilter === "全部" || item.status === statusFilter),
    [projects, statusFilter]
  );
  const projectStatuses = roleScopedProjectsState.response?.project_statuses ?? [];
  const canManageMembers = auditUser.can("manage_project_members");

  function selectProject(project: ProjectSummaryApiItem) {
    ++selectionGenerationRef.current;
    setSelectedProjectId(project.id);
    setMemberSaving(false);
    setMemberCreateError(null);
    loadMembers(project.id);
    loadDashboard(project.id);
  }

  async function submitMember() {
    if (!selectedProject || !canManageMembers || memberSaving) return;
    const normalizedIdentifier = userIdentifier.trim();
    const normalizedName = memberName.trim();
    const normalizedDepartment = memberDepartment.trim();
    if (!normalizedIdentifier || !normalizedName || !normalizedDepartment) return;

    const generation = selectionGenerationRef.current;
    setMemberSaving(true);
    setMemberCreateError(null);
    try {
      const response = await createProjectMember(selectedProject.id, {
        user_identifier: normalizedIdentifier,
        name: normalizedName,
        role: memberRole,
        department: normalizedDepartment,
        status: memberStatus
      });
      if (generation !== selectionGenerationRef.current) return;
      setMembersState((current) => {
        const currentItems = current.response?.items ?? [];
        const nextResponse: ProjectMembersResponse = {
          items: [response.item, ...currentItems.filter((item) => item.id !== response.item.id)],
          project_key: selectedProject.id,
          roles: current.response?.roles ?? roleScopedProjectsState.response?.roles ?? [],
          statuses: current.response?.statuses ?? roleScopedProjectsState.response?.statuses ?? [],
          store: response.store
        };
        return { phase: response.store.ready ? "ready" : "degraded", response: nextResponse };
      });
      setProjectsState((current) => {
        if (!current.response) return current;
        return {
          ...current,
          response: {
            ...current.response,
            items: current.response.items.map((item) =>
              item.id === selectedProject.id ? { ...item, member_count: item.member_count + 1 } : item
            )
          }
        };
      });
      setUserIdentifier("");
      setMemberName("");
    } catch {
      if (generation === selectionGenerationRef.current) {
        setMemberCreateError("成员新增失败，请核对账号是否重复或稍后重试。");
      }
    } finally {
      if (generation === selectionGenerationRef.current) setMemberSaving(false);
    }
  }

  return (
    <main className="replica-page replica-page-standard replica-project-workbench">
      <header className="replica-page-header">
        <div>
          <p className="replica-kicker">项目管理</p>
          <h1>项目协作工作台</h1>
          <p>按当前账号查看可见项目，并进入成员与审计进展协作。</p>
        </div>
        <p className="replica-project-visibility">
          {auditUser.role === "admin" ? "当前显示：全部项目" : "当前显示：我创建或参与的项目"}
        </p>
      </header>

      <section className="replica-project-section" aria-labelledby="project-list-title">
        <div className="replica-project-toolbar">
          <div>
            <p className="replica-kicker">项目清单</p>
            <h2 id="project-list-title">可见项目</h2>
          </div>
          <label className="replica-project-filter">
            <span>项目状态</span>
            <select
              aria-label="项目状态"
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value as ApiProjectStatus | "全部")}
            >
              <option value="全部">全部</option>
              {projectStatuses.map((item) => (
                <option key={item} value={item}>{item}</option>
              ))}
            </select>
          </label>
        </div>

        {roleScopedProjectsState.phase === "loading" ? <ProjectMessage>项目列表读取中</ProjectMessage> : null}
        {roleScopedProjectsState.phase === "error" ? (
          <ProjectMessage>
            项目列表读取失败
            <button type="button" onClick={() => loadProjects(auditUser.role)}>重试项目列表</button>
          </ProjectMessage>
        ) : null}
        {roleScopedProjectsState.phase === "empty" ? <ProjectMessage>当前没有可见项目</ProjectMessage> : null}
        {roleScopedProjectsState.phase === "degraded" ? <ProjectMessage>项目列表存储未就绪</ProjectMessage> : null}

        {roleScopedProjectsState.response && projects.length > 0 ? (
          filteredProjects.length > 0 ? (
            <div className="replica-project-table-shell">
              <table className="replica-project-table">
                <thead>
                  <tr>
                    <th>名称</th>
                    <th>专题</th>
                    <th>成员数</th>
                    <th>创建人</th>
                    <th>创建时间</th>
                    <th>状态</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredProjects.map((project) => (
                    <tr key={project.id} data-selected={project.id === selectedProjectId ? "true" : undefined}>
                      <td>{project.name}</td>
                      <td>{project.audit_topic}</td>
                      <td>{project.member_count}</td>
                      <td>{project.creator}</td>
                      <td>{formatDate(project.created_at)}</td>
                      <td>{project.status}</td>
                      <td>
                        <button type="button" onClick={() => selectProject(project)} aria-label={`查看：${project.name}`}>
                          {project.operation_label}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <ProjectMessage>当前筛选条件下没有项目</ProjectMessage>
        ) : null}
      </section>

      {selectedProject ? (
        <section className="replica-project-detail" aria-label={`项目详情：${selectedProject.name}`}>
          <div className="replica-project-detail-header">
            <div>
              <p className="replica-kicker">已选择项目</p>
              <h2>项目详情：{selectedProject.name}</h2>
            </div>
            <p>{selectedProject.audit_topic} · {selectedProject.status}</p>
          </div>

          <div className="replica-project-detail-grid">
            <MembersPanel
              canManage={canManageMembers}
              createError={memberCreateError}
              department={memberDepartment}
              membersState={membersState}
              name={memberName}
              onDepartmentChange={setMemberDepartment}
              onNameChange={setMemberName}
              onRetry={() => loadMembers(selectedProject.id)}
              onRoleChange={setMemberRole}
              onStatusChange={setMemberStatus}
              onSubmit={submitMember}
              onUserIdentifierChange={setUserIdentifier}
              projectResponse={roleScopedProjectsState.response}
              role={memberRole}
              saving={memberSaving}
              status={memberStatus}
              userIdentifier={userIdentifier}
            />
            <DashboardPanel
              dashboardState={dashboardState}
              onRetry={() => loadDashboard(selectedProject.id)}
            />
          </div>
        </section>
      ) : (
        roleScopedProjectsState.response && projects.length > 0
          ? <ProjectMessage>请选择一个项目查看成员与驾驶舱</ProjectMessage>
          : null
      )}
    </main>
  );
}

function MembersPanel({
  canManage,
  createError,
  department,
  membersState,
  name,
  onDepartmentChange,
  onNameChange,
  onRetry,
  onRoleChange,
  onStatusChange,
  onSubmit,
  onUserIdentifierChange,
  projectResponse,
  role,
  saving,
  status,
  userIdentifier
}: {
  readonly canManage: boolean;
  readonly createError: string | null;
  readonly department: string;
  readonly membersState: MembersState;
  readonly name: string;
  readonly onDepartmentChange: (value: string) => void;
  readonly onNameChange: (value: string) => void;
  readonly onRetry: () => void;
  readonly onRoleChange: (value: ApiProjectMemberRole) => void;
  readonly onStatusChange: (value: ApiProjectMemberStatus) => void;
  readonly onSubmit: () => void;
  readonly onUserIdentifierChange: (value: string) => void;
  readonly projectResponse: ProjectsResponse | null;
  readonly role: ApiProjectMemberRole;
  readonly saving: boolean;
  readonly status: ApiProjectMemberStatus;
  readonly userIdentifier: string;
}) {
  const members = membersState.response?.items ?? [];
  return (
    <section className="replica-project-panel" aria-labelledby="project-members-title">
      <h3 id="project-members-title">项目成员</h3>
      {membersState.phase === "loading" ? <ProjectMessage>项目成员读取中</ProjectMessage> : null}
      {membersState.phase === "error" ? (
        <ProjectMessage>
          项目成员读取失败
          <button type="button" onClick={onRetry}>重试项目成员</button>
        </ProjectMessage>
      ) : null}
      {membersState.phase === "empty" ? <ProjectMessage>当前项目没有成员</ProjectMessage> : null}
      {membersState.phase === "degraded" ? <ProjectMessage>项目成员存储未就绪</ProjectMessage> : null}
      {members.length > 0 ? (
        <div className="replica-project-table-shell">
          <table className="replica-project-table replica-project-table-compact">
            <thead>
              <tr><th>账号</th><th>姓名</th><th>角色</th><th>部门</th><th>状态</th></tr>
            </thead>
            <tbody>
              {members.map((member) => (
                <tr key={member.id}>
                  <td>{member.user_identifier ?? "未绑定账号"}</td>
                  <td>{member.name}</td>
                  <td>{member.role}</td>
                  <td>{member.department}</td>
                  <td>{member.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {canManage ? (
        <div className="replica-project-member-form" aria-label="新增项目成员">
          <h4>新增成员</h4>
          <label>账号<input aria-label="账号" required value={userIdentifier} onChange={(event) => onUserIdentifierChange(event.target.value)} /></label>
          <label>姓名<input aria-label="姓名" required value={name} onChange={(event) => onNameChange(event.target.value)} /></label>
          <label>
            角色
            <select aria-label="角色" value={role} onChange={(event) => onRoleChange(event.target.value as ApiProjectMemberRole)}>
              {(membersState.response?.roles ?? projectResponse?.roles ?? []).map((item) => <option key={item}>{item}</option>)}
            </select>
          </label>
          <label>部门<input aria-label="部门" required value={department} onChange={(event) => onDepartmentChange(event.target.value)} /></label>
          <label>
            状态
            <select aria-label="成员状态" value={status} onChange={(event) => onStatusChange(event.target.value as ApiProjectMemberStatus)}>
              {(membersState.response?.statuses ?? projectResponse?.statuses ?? []).map((item) => <option key={item}>{item}</option>)}
            </select>
          </label>
          {createError ? <p role="alert">{createError}</p> : null}
          <button type="button" disabled={saving} onClick={onSubmit}>{saving ? "新增中" : "新增成员"}</button>
        </div>
      ) : <p className="replica-project-readonly">当前角色仅可查看项目成员</p>}
    </section>
  );
}

function DashboardPanel({
  dashboardState,
  onRetry
}: {
  readonly dashboardState: DashboardState;
  readonly onRetry: () => void;
}) {
  const dashboard = dashboardState.response;
  return (
    <section className="replica-project-panel" aria-labelledby="project-dashboard-title">
      <h3 id="project-dashboard-title">项目驾驶舱</h3>
      {dashboardState.phase === "loading" ? <ProjectMessage>项目驾驶舱读取中</ProjectMessage> : null}
      {dashboardState.phase === "error" ? (
        <ProjectMessage>
          项目驾驶舱读取失败
          <button type="button" onClick={onRetry}>重试项目驾驶舱</button>
        </ProjectMessage>
      ) : null}
      {dashboard ? (
        <>
          <ProjectMessage>{dashboardStoreLabel(dashboard)}</ProjectMessage>
          {dashboardState.phase === "empty" ? <ProjectMessage>当前项目暂无驾驶舱数据</ProjectMessage> : null}
          {dashboard.metrics.length > 0 ? (
            <div className="replica-project-metrics">
              {dashboard.metrics.map((metric) => (
                <article key={metric.key}>
                  <span>{metric.label}</span><strong>{metric.value}</strong><small>{metric.helper}</small>
                </article>
              ))}
            </div>
          ) : null}
          {dashboard.queue.length > 0 ? (
            <DashboardList
              title="任务队列"
              items={dashboard.queue.map((item) => ({
                id: item.id,
                primary: item.title,
                details: `${item.owner} · ${item.dueLabel}`
              }))}
            />
          ) : null}
          {dashboard.activities.length > 0 ? (
            <DashboardList
              title="最近活动"
              items={dashboard.activities.map((item) => ({
                id: item.id,
                primary: item.title,
                details: `${item.description} · ${item.timeLabel}`
              }))}
            />
          ) : null}
          {dashboard.status_distribution.length > 0 ? (
            <DashboardList
              title="状态分布"
              items={dashboard.status_distribution.map((item) => ({
                id: item.status,
                primary: item.label,
                details: `${item.count}`
              }))}
            />
          ) : null}
          {dashboard.member_workloads.length > 0 ? (
            <DashboardList
              title="成员工作量"
              items={dashboard.member_workloads.map((item) => ({
                id: `${item.name}-${item.role}-${item.department}`,
                primary: `${item.name} · ${item.role}`,
                details: `总计 ${item.total} / 待处理 ${item.pending} / 已关闭 ${item.closed}`
              }))}
            />
          ) : null}
          <dl className="replica-project-evidence">
            <div><dt>证据等级</dt><dd>{dashboard.evidence_grade}</dd></div>
            <div><dt>数据存储</dt><dd>{dashboard.store.backend.project_members} / {dashboard.store.backend.audit_findings}</dd></div>
            <div><dt>生产副作用</dt><dd>{dashboard.production_side_effect}</dd></div>
          </dl>
        </>
      ) : null}
    </section>
  );
}

type DashboardListItem = {
  readonly id: string;
  readonly primary: string;
  readonly details: string;
};

function DashboardList({ title, items }: { readonly title: string; readonly items: readonly DashboardListItem[] }) {
  return (
    <section className="replica-project-dashboard-list">
      <h4>{title}</h4>
      <ul>
        {items.map((item) => (
          <li key={item.id}>
            <strong>{item.primary}</strong>
            <span>{item.details}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function ProjectMessage({ children }: { readonly children: React.ReactNode }) {
  return <div className="replica-project-message">{children}</div>;
}

function dashboardIsEmpty(response: ProjectDashboardResponse): boolean {
  return response.metrics.length === 0
    && response.queue.length === 0
    && response.activities.length === 0
    && response.status_distribution.length === 0
    && response.member_workloads.length === 0;
}

function dashboardStoreLabel(response: ProjectDashboardResponse): string {
  if (response.store.status === "ready") return "项目数据已完整同步";
  if (response.store.status === "partial") return "项目数据部分可用";
  return "项目数据当前不可用";
}

function formatDate(value: string): string {
  return value.slice(0, 10);
}
