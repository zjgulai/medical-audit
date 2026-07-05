"use client";

import { FormEvent, useEffect, useState } from "react";

import { useAuditUser } from "@/components/shell/audit-user-context";
import { StatusPill } from "@/components/ui/status-pill";
import { createProjectMember, fetchAuditFindings, fetchProjectMembers, fetchProjects } from "@/lib/api-client";
import type { AuditFinding, AuditFindingsResponse, ProjectMemberApiItem, ProjectSummaryApiItem } from "@/lib/api-types";
import {
  defaultProjectMembers,
  hospitalPermissionRoles,
  HospitalPermissionRole,
  portalProjectSummaries,
  PortalProjectMember,
  PortalProjectSummary
} from "@/lib/portal-data";
import { currentSelfCheckProject } from "@/lib/projects";

const memberRoles: readonly PortalProjectMember["role"][] = ["项目负责人", "审计员", "业务专家", "信息科", "只读观察员"];
const projectStatusTone: Record<PortalProjectSummary["status"], "neutral" | "warning" | "success"> = {
  进行中: "success",
  待启动: "warning",
  已归档: "neutral"
};
type StoreStatus = "loading" | "ready" | "fallback" | "saving";
type FindingStoreStatus = "loading" | "ready" | "fallback";

const unassignedOwner = "未分配";

export function ProjectManagementWorkbench() {
  const auditUser = useAuditUser();
  const project = currentSelfCheckProject;
  const [projects, setProjects] = useState<readonly PortalProjectSummary[]>(portalProjectSummaries);
  const [selectedProjectId, setSelectedProjectId] = useState(project.id);
  const [members, setMembers] = useState<readonly PortalProjectMember[]>(defaultMembersForProject(project.id));
  const [projectQuery, setProjectQuery] = useState("");
  const [name, setName] = useState("");
  const [permissionRoleId, setPermissionRoleId] = useState(hospitalPermissionRoles[3].id);
  const [role, setRole] = useState<PortalProjectMember["role"]>("审计员");
  const [department, setDepartment] = useState("内审部");
  const [projectStoreStatus, setProjectStoreStatus] = useState<StoreStatus>("loading");
  const [memberStoreStatus, setMemberStoreStatus] = useState<StoreStatus>("loading");
  const [findingStoreStatus, setFindingStoreStatus] = useState<FindingStoreStatus>("loading");
  const [findingResponse, setFindingResponse] = useState<AuditFindingsResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const normalizedProjectQuery = projectQuery.trim().toLowerCase();
  const filteredProjects = projects.filter((item) => {
    if (!normalizedProjectQuery) {
      return true;
    }

    return [item.name, item.auditTopic, item.creator, item.organizationName].some((value) =>
      value.toLowerCase().includes(normalizedProjectQuery)
    );
  });
  const selectedProject = projects.find((item) => item.id === selectedProjectId) ?? projects[0] ?? portalProjectSummaries[0];
  const selectedPermissionRole =
    hospitalPermissionRoles.find((item) => item.id === permissionRoleId) ?? hospitalPermissionRoles[3];
  const canManageProjectMembers = auditUser.can("manage_project_members");
  const activeProjectCount = projects.filter((item) => item.status === "进行中").length;
  const pendingProjectCount = projects.filter((item) => item.status === "待启动").length;
  const cockpit = buildAuditCockpit(findingResponse, members);

  useEffect(() => {
    let isMounted = true;

    fetchProjects()
      .then((response) => {
        if (!isMounted) {
          return;
        }
        const nextProjects = response.items.map(apiProjectToPortalProject);
        if (nextProjects.length > 0) {
          setProjects(nextProjects);
          setSelectedProjectId((current) =>
            nextProjects.some((item) => item.id === current) ? current : nextProjects[0].id
          );
        }
        setProjectStoreStatus(response.store.ready ? "ready" : "fallback");
      })
      .catch(() => {
        if (!isMounted) {
          return;
        }
        setProjectStoreStatus("fallback");
      });

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    let isMounted = true;
    setMemberStoreStatus("loading");

    fetchProjectMembers(selectedProjectId)
      .then((response) => {
        if (!isMounted) {
          return;
        }
        setMembers(response.items.map(apiMemberToPortalMember));
        setMemberStoreStatus(response.store.ready ? "ready" : "fallback");
      })
      .catch(() => {
        if (!isMounted) {
          return;
        }
        setMembers(defaultMembersForProject(selectedProjectId));
        setMemberStoreStatus("fallback");
      });

    return () => {
      isMounted = false;
    };
  }, [selectedProjectId]);

  useEffect(() => {
    let isMounted = true;
    setFindingStoreStatus("loading");

    fetchAuditFindings()
      .then((response) => {
        if (!isMounted) {
          return;
        }
        setFindingResponse(response);
        setFindingStoreStatus(response.store.ready ? "ready" : "fallback");
      })
      .catch(() => {
        if (!isMounted) {
          return;
        }
        setFindingResponse(null);
        setFindingStoreStatus("fallback");
      });

    return () => {
      isMounted = false;
    };
  }, []);

  async function submitMember(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canManageProjectMembers) {
      setErrorMessage("当前角色无成员分配权限。");
      return;
    }

    const normalizedName = name.trim();
    const normalizedDepartment = department.trim();

    if (!normalizedName || !normalizedDepartment) {
      return;
    }

    setMemberStoreStatus("saving");
    setErrorMessage(null);
    try {
      const response = await createProjectMember(selectedProject.id, {
        name: normalizedName,
        role,
        department: normalizedDepartment
      });
      const nextMember = apiMemberToPortalMember(response.item);
      setMembers((current) => [nextMember, ...current.filter((member) => member.id !== nextMember.id)]);
      setProjects((current) =>
        current.map((item) =>
          item.id === selectedProject.id ? { ...item, memberCount: item.memberCount + 1 } : item
        )
      );
      setName("");
      setMemberStoreStatus(response.store.ready ? "ready" : "fallback");
    } catch {
      setMemberStoreStatus("fallback");
      setErrorMessage("成员未保存，请检查后端连接和当前角色权限。");
    }
  }

  function applyPermissionRole(nextRoleId: string) {
    const nextRole = hospitalPermissionRoles.find((item) => item.id === nextRoleId);
    if (!nextRole) {
      return;
    }

    setPermissionRoleId(nextRole.id);
    setRole(nextRole.mapsToProjectRole);
    setDepartment(nextRole.departmentHint);
  }

  return (
    <main className="audit-workbench-main mx-auto grid gap-4">
      <section className="audit-panel-rail min-w-0 p-4 sm:p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="audit-kicker">项目空间</p>
            <h2 className="audit-section-title mt-1">切换审计项目</h2>
          </div>
          <StatusPill tone={projectStoreStatus === "ready" ? "success" : "neutral"}>
            {projectStoreStatusLabel(projectStoreStatus)}
          </StatusPill>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-2 sm:max-w-sm">
          <SidebarMetric label="进行中" value={String(activeProjectCount)} />
          <SidebarMetric label="待启动" value={String(pendingProjectCount)} />
        </div>
        <div className="mt-4 grid gap-2 md:grid-cols-3">
          {portalProjectSummaries.slice(0, 3).map((item) => (
            <ProjectNavigatorItem
              key={item.id}
              item={item}
              selected={item.id === selectedProject.id}
              onSelect={() => setSelectedProjectId(item.id)}
            />
          ))}
        </div>
      </section>

      <section className="min-w-0 space-y-4">
        <div className="audit-panel min-w-0 p-5 sm:p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="audit-kicker">项目管理</p>
              <h1 className="audit-page-title">项目与成员</h1>
              <p className="audit-copy mt-2 max-w-2xl">{project.organizationName}，{project.dateRange}。</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <StatusPill tone="success">进行中</StatusPill>
              <StatusPill tone={memberStoreStatus === "ready" ? "success" : "neutral"}>
                {memberStoreStatusLabel(memberStoreStatus)}
              </StatusPill>
            </div>
          </div>

          <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
            <h2 className="audit-section-title">项目列表</h2>
            <label className="block w-full min-w-0 sm:min-w-64 sm:max-w-80">
              <span className="sr-only">搜索项目</span>
              <input
                className="audit-focus-ring audit-input px-3 py-2"
                value={projectQuery}
                onChange={(event) => setProjectQuery(event.target.value)}
                placeholder="搜索项目、专题、创建人"
                aria-label="搜索项目"
              />
            </label>
          </div>

          <div className="mt-4 grid gap-3 md:hidden">
            {filteredProjects.map((item) => (
              <ProjectMobileCard
                item={item}
                key={item.id}
                memberCount={item.id === selectedProject.id ? members.length : item.memberCount}
                onSelect={() => setSelectedProjectId(item.id)}
                selected={item.id === selectedProject.id}
              />
            ))}
          </div>

          <div className="audit-table-shell mt-4 hidden max-w-full overflow-x-auto md:block">
            <table className="audit-table min-w-[58rem]">
              <thead>
                <tr>
                  <th>序号</th>
                  <th>项目名称</th>
                  <th>成员数</th>
                  <th>创建人</th>
                  <th>创建时间</th>
                  <th>状态</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--audit-line-soft)]">
                {filteredProjects.map((item, index) => (
                  <tr key={item.id} className={item.id === selectedProject.id ? "audit-row-selected" : undefined}>
                    <td className="text-[var(--audit-ink-subtle)]">{index + 1}</td>
                    <td>
                      <p className="font-semibold text-[var(--audit-ink)]">{item.name}</p>
                      <p className="audit-meta mt-1">
                        {item.organizationName} / {item.auditTopic}
                      </p>
                    </td>
                    <td className="text-[var(--audit-ink-muted)]">{item.id === selectedProject.id ? members.length : item.memberCount}</td>
                    <td className="text-[var(--audit-ink-muted)]">{item.creator}</td>
                    <td className="text-[var(--audit-ink-muted)]">{item.createdAt}</td>
                    <td>
                      <StatusPill tone={projectStatusTone[item.status]}>{item.status}</StatusPill>
                    </td>
                    <td>
                      <button
                        className="audit-focus-ring audit-btn audit-btn-secondary"
                        type="button"
                        onClick={() => setSelectedProjectId(item.id)}
                        aria-pressed={item.id === selectedProject.id}
                      >
                        {item.operationLabel}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="audit-panel min-w-0 p-5 sm:p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="audit-kicker">审计驾驶舱</p>
              <h2 className="audit-section-title mt-2">专题审计看板</h2>
              <p className="audit-copy mt-2">面向当前审计专题，汇总疑点总量、复核状态和人员承接情况。</p>
            </div>
            <StatusPill tone={findingStoreStatus === "ready" ? "success" : "neutral"}>
              {findingStoreStatus === "ready" ? "疑点已同步" : findingStoreStatus === "loading" ? "疑点同步中" : "默认统计"}
            </StatusPill>
          </div>

          <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <CockpitMetric icon="Σ" label="总审计条数" value={String(cockpit.total)} detail="疑点与审计记录" />
            <CockpitMetric icon="○" label="待复核" value={String(cockpit.pendingReview)} detail="需要人工判断" />
            <CockpitMetric icon="✓" label="已关联任务" value={String(cockpit.linkedReviewTask)} detail="进入复核闭环" />
            <CockpitMetric icon="!" label="未分配" value={String(cockpit.unassigned)} detail="待绑定负责人" />
          </div>

          <div className="mt-5 grid gap-4 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
            <section className="rounded-[var(--audit-radius-lg)] border border-[var(--audit-line-soft)] bg-[var(--audit-surface-muted)] p-4">
              <h3 className="audit-card-title">状态分布</h3>
              <div className="mt-3 grid gap-2">
                {cockpit.statusRows.map((row) => (
                  <StatusDistributionRow key={row.status} row={row} total={Math.max(cockpit.total, 1)} />
                ))}
              </div>
            </section>

            <section className="rounded-[var(--audit-radius-lg)] border border-[var(--audit-line-soft)] bg-[var(--audit-surface-muted)] p-4">
              <h3 className="audit-card-title">人员承接</h3>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                {cockpit.memberRows.map((row) => (
                  <MemberWorkloadCard key={row.name} row={row} />
                ))}
              </div>
            </section>
          </div>
        </div>

        <div className="audit-panel min-w-0 p-5 sm:p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="audit-kicker">项目成员</p>
              <h2 className="audit-section-title mt-2">{selectedProject.name}</h2>
              <p className="audit-copy mt-2">查看成员职责，按需要补充项目成员。</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <StatusPill tone={projectStatusTone[selectedProject.status]}>{selectedProject.status}</StatusPill>
              <StatusPill tone={memberStoreStatus === "ready" ? "success" : "neutral"}>
                {memberStoreStatusLabel(memberStoreStatus)}
              </StatusPill>
            </div>
          </div>

          <div className="mt-5 grid gap-3 md:hidden">
            {members.map((member) => (
              <MemberMobileCard key={member.id} member={member} />
            ))}
          </div>

          <div className="audit-table-shell mt-6 hidden max-w-full overflow-x-auto md:block">
            <table className="audit-table min-w-[42rem]">
              <thead>
                <tr>
                  <th>成员</th>
                  <th>角色</th>
                  <th>部门</th>
                  <th>状态</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--audit-line-soft)]">
                {members.map((member) => (
                  <tr key={member.id}>
                    <td className="font-semibold text-[var(--audit-ink)]">{member.name}</td>
                    <td className="text-[var(--audit-ink-muted)]">{member.role}</td>
                    <td className="text-[var(--audit-ink-muted)]">{member.department}</td>
                    <td>
                      <StatusPill tone={member.status === "在项目中" ? "success" : "warning"}>{member.status}</StatusPill>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="audit-panel min-w-0 p-5 sm:p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="audit-kicker">权限角色</p>
              <h2 className="audit-section-title mt-2">权限角色</h2>
              <p className="audit-copy mt-2">按管理员、技术人员、主任和普通成员分配可见范围。</p>
            </div>
            <StatusPill tone="success">权限已接入</StatusPill>
          </div>
          <div className="mt-5 grid gap-3 lg:grid-cols-2">
            {hospitalPermissionRoles.map((permissionRole) => (
              <PermissionRoleCard
                key={permissionRole.id}
                permissionRole={permissionRole}
                selected={permissionRole.id === permissionRoleId}
                onSelect={() => applyPermissionRole(permissionRole.id)}
              />
            ))}
          </div>
        </div>
      </section>

      <section className="grid min-w-0 gap-4 lg:grid-cols-2">
        <section className="audit-panel-rail p-5">
          <h2 className="audit-section-title">当前项目</h2>
          <p className="audit-card-title mt-4">{selectedProject.name}</p>
          <p className="audit-copy mt-2">{selectedProject.organizationName}</p>
          <div className="mt-4 space-y-2">
            <SummaryRow label="审计专题" value={selectedProject.auditTopic} />
            <SummaryRow label="当前成员" value={String(members.length)} />
            <SummaryRow label="项目创建人" value={selectedProject.creator} />
          </div>
        </section>

        <section className="audit-panel-rail p-5">
          <h2 className="audit-section-title">新增成员</h2>
          <form className="mt-4 space-y-4" onSubmit={submitMember}>
            <label className="block">
              <span className="audit-label">姓名</span>
              <input
                className="audit-focus-ring audit-input mt-2 px-3 py-2"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="成员姓名"
              />
            </label>
            <label className="block">
              <span className="audit-label">权限角色视图</span>
              <select
                aria-label="权限角色视图"
                className="audit-focus-ring audit-input mt-2 px-3 py-2"
                value={permissionRoleId}
                onChange={(event) => applyPermissionRole(event.target.value)}
              >
                {hospitalPermissionRoles.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
              <p className="audit-meta mt-2">{selectedPermissionRole.responsibility}</p>
            </label>
            <label className="block">
              <span className="audit-label">项目成员角色</span>
              <select
                aria-label="项目成员角色"
                className="audit-focus-ring audit-input mt-2 px-3 py-2"
                value={role}
                onChange={(event) => setRole(event.target.value as PortalProjectMember["role"])}
              >
                {memberRoles.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
              <p className="audit-meta mt-2">提交到现有后端角色：{selectedPermissionRole.mapsToProjectRole}</p>
            </label>
            <label className="block">
              <span className="audit-label">部门</span>
              <input
                className="audit-focus-ring audit-input mt-2 px-3 py-2"
                value={department}
                onChange={(event) => setDepartment(event.target.value)}
              />
            </label>
            {errorMessage ? (
              <p className="text-sm font-semibold text-[var(--audit-red)]" role="alert">
                {errorMessage}
              </p>
            ) : null}
            <button
              className="audit-focus-ring audit-btn audit-btn-primary w-full"
              type="submit"
              disabled={memberStoreStatus === "saving" || !canManageProjectMembers}
            >
              {memberStoreStatus === "saving" ? "保存中" : "添加成员"}
            </button>
            {!canManageProjectMembers ? (
              <p className="audit-meta">当前角色只能查看项目成员，不能分配账号或权限。</p>
            ) : null}
          </form>
        </section>
      </section>
    </main>
  );
}

function apiProjectToPortalProject(project: ProjectSummaryApiItem): PortalProjectSummary {
  return {
    id: project.id,
    name: project.name,
    auditTopic: project.audit_topic,
    organizationName: project.organization_name,
    memberCount: project.member_count,
    creator: project.creator,
    createdAt: project.created_at,
    status: project.status,
    operationLabel: project.operation_label
  };
}

function apiMemberToPortalMember(member: ProjectMemberApiItem): PortalProjectMember {
  return {
    id: member.id,
    name: member.name,
    role: member.role,
    department: member.department,
    status: member.status
  };
}

function defaultMembersForProject(projectId: string): readonly PortalProjectMember[] {
  if (projectId === currentSelfCheckProject.id) {
    return defaultProjectMembers;
  }
  return [];
}

function projectStoreStatusLabel(status: StoreStatus): string {
  if (status === "ready") {
    return "项目已同步";
  }
  if (status === "loading") {
    return "项目同步中";
  }
  return "默认项目";
}

function memberStoreStatusLabel(status: StoreStatus): string {
  if (status === "ready") {
    return "成员已同步";
  }
  if (status === "saving") {
    return "成员保存中";
  }
  if (status === "loading") {
    return "成员同步中";
  }
  return "默认成员";
}

function findingOwner(finding: AuditFinding): string {
  const candidateKeys = ["owner", "assignee", "auditor", "reviewer", "employee", "handler"];
  for (const key of candidateKeys) {
    const value = finding.metadata[key] ?? finding.calculation_trace[key] ?? finding.source_record_locator[key];
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
  }
  return unassignedOwner;
}

function statusLabel(response: AuditFindingsResponse | null, status: string): string {
  return response?.review_status_options[status] ?? status;
}

function buildAuditCockpit(response: AuditFindingsResponse | null, members: readonly PortalProjectMember[]) {
  const findings = response?.items ?? [];
  const statusCounts = new Map<string, number>();
  const memberCounts = new Map<string, { total: number; pending: number }>();
  for (const member of members) {
    memberCounts.set(member.name, { total: 0, pending: 0 });
  }
  for (const finding of findings) {
    statusCounts.set(finding.review_status, (statusCounts.get(finding.review_status) ?? 0) + 1);
    const owner = findingOwner(finding);
    const current = memberCounts.get(owner) ?? { total: 0, pending: 0 };
    current.total += 1;
    if (finding.review_status === "pending-review" || finding.review_status === "needs-evidence") {
      current.pending += 1;
    }
    memberCounts.set(owner, current);
  }
  const stats = response?.stats;
  const total = stats?.total ?? findings.length;
  const statusRows = Array.from(statusCounts.entries())
    .map(([status, count]) => ({ status, label: statusLabel(response, status), count }))
    .sort((a, b) => b.count - a.count);
  const memberRows = Array.from(memberCounts.entries())
    .map(([name, count]) => ({ name, ...count }))
    .filter((row) => row.total > 0 || row.name !== unassignedOwner)
    .sort((a, b) => b.total - a.total || a.name.localeCompare(b.name, "zh-CN"))
    .slice(0, 8);
  return {
    total,
    pendingReview: stats?.pending_review ?? (statusCounts.get("pending-review") ?? 0),
    linkedReviewTask: stats?.linked_review_task ?? findings.filter((item) => item.review_task_id).length,
    unassigned: memberCounts.get(unassignedOwner)?.total ?? 0,
    statusRows: statusRows.length > 0 ? statusRows : [{ status: "empty", label: "暂无疑点", count: 0 }],
    memberRows: memberRows.length > 0 ? memberRows : [{ name: "暂无承接人", total: 0, pending: 0 }]
  };
}

function CockpitMetric({
  icon,
  label,
  value,
  detail
}: {
  readonly icon: string;
  readonly label: string;
  readonly value: string;
  readonly detail: string;
}) {
  return (
    <article className="rounded-[var(--audit-radius-lg)] border border-[var(--audit-line)] bg-white p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="audit-meta font-semibold">{label}</p>
          <p className="audit-metric-value mt-1">{value}</p>
        </div>
        <span className="grid size-9 place-items-center rounded-full bg-[var(--audit-primary-soft)] text-sm font-semibold text-[var(--audit-primary)]">
          {icon}
        </span>
      </div>
      <p className="audit-meta mt-2">{detail}</p>
    </article>
  );
}

function StatusDistributionRow({
  row,
  total
}: {
  readonly row: { readonly status: string; readonly label: string; readonly count: number };
  readonly total: number;
}) {
  const ratio = Math.round((row.count / total) * 100);
  return (
    <div className="rounded-[var(--audit-radius-md)] bg-white px-3 py-2">
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm font-semibold text-[var(--audit-ink)]">{row.label}</span>
        <span className="audit-meta">{row.count} 条</span>
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-[var(--audit-surface-subtle)]">
        <span className="block h-full rounded-full bg-[var(--audit-primary)]" style={{ width: `${ratio}%` }} />
      </div>
    </div>
  );
}

function MemberWorkloadCard({
  row
}: {
  readonly row: { readonly name: string; readonly total: number; readonly pending: number };
}) {
  return (
    <article className="rounded-[var(--audit-radius-md)] border border-[var(--audit-line-soft)] bg-white p-3">
      <div className="flex items-center justify-between gap-3">
        <p className="truncate text-sm font-semibold text-[var(--audit-ink)]">{row.name}</p>
        <StatusPill tone={row.pending > 0 ? "warning" : "success"}>{row.pending > 0 ? "待处理" : "平稳"}</StatusPill>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2">
        <SidebarMetric label="审计条数" value={String(row.total)} />
        <SidebarMetric label="待处理" value={String(row.pending)} />
      </div>
    </article>
  );
}

function SidebarMetric({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <div className="rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-white p-3">
      <p className="audit-meta font-semibold">{label}</p>
      <p className="audit-metric-value-sm mt-1">{value}</p>
    </div>
  );
}

function ProjectNavigatorItem({
  item,
  selected,
  onSelect
}: {
  readonly item: PortalProjectSummary;
  readonly selected: boolean;
  readonly onSelect: () => void;
}) {
  return (
    <button
      className={`audit-focus-ring block w-full rounded-[var(--audit-radius-md)] border p-3 text-left ${
        selected
          ? "border-[var(--audit-primary-line)] bg-[var(--audit-primary-soft)]"
          : "border-[var(--audit-line)] bg-white hover:bg-[var(--audit-surface-muted)]"
      }`}
      type="button"
      aria-pressed={selected}
      onClick={onSelect}
    >
      <span className="block truncate text-sm font-semibold text-[var(--audit-ink)]">{item.auditTopic}</span>
      <span className="audit-meta mt-1 block truncate">{item.creator}，{item.createdAt}</span>
      <span className="mt-2 inline-flex">
        <StatusPill tone={projectStatusTone[item.status]}>{item.status}</StatusPill>
      </span>
    </button>
  );
}

function ProjectMobileCard({
  item,
  memberCount,
  selected,
  onSelect
}: {
  readonly item: PortalProjectSummary;
  readonly memberCount: number;
  readonly selected: boolean;
  readonly onSelect: () => void;
}) {
  return (
    <article
      className={`rounded-[var(--audit-radius-md)] border p-4 ${
        selected ? "border-[var(--audit-primary-line)] bg-[var(--audit-primary-soft)]" : "border-[var(--audit-line)] bg-white"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-sm font-semibold text-[var(--audit-ink)]">{item.name}</h3>
          <p className="audit-meta mt-1 truncate">{item.auditTopic}</p>
        </div>
        <StatusPill tone={projectStatusTone[item.status]}>{item.status}</StatusPill>
      </div>
      <dl className="mt-3 grid grid-cols-2 gap-2 text-xs">
        <div>
          <dt className="audit-meta">成员</dt>
          <dd className="mt-1 font-semibold text-[var(--audit-ink)]">{memberCount}</dd>
        </div>
        <div>
          <dt className="audit-meta">创建</dt>
          <dd className="mt-1 font-semibold text-[var(--audit-ink)]">{item.createdAt}</dd>
        </div>
      </dl>
      <button
        aria-label={`查看${item.name}成员`}
        aria-pressed={selected}
        className="audit-focus-ring audit-btn audit-btn-secondary mt-3 w-full justify-center"
        onClick={onSelect}
        type="button"
      >
        查看
      </button>
    </article>
  );
}

function MemberMobileCard({ member }: { readonly member: PortalProjectMember }) {
  return (
    <article className="rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-white p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-sm font-semibold text-[var(--audit-ink)]">{member.name}</h3>
          <p className="audit-meta mt-1 truncate">{member.role}</p>
        </div>
        <StatusPill tone={member.status === "在项目中" ? "success" : "warning"}>{member.status}</StatusPill>
      </div>
      <p className="audit-meta mt-3">部门：{member.department}</p>
    </article>
  );
}

function PermissionRoleCard({
  permissionRole,
  selected,
  onSelect
}: {
  readonly permissionRole: HospitalPermissionRole;
  readonly selected: boolean;
  readonly onSelect: () => void;
}) {
  return (
    <button
      aria-pressed={selected}
      className={`audit-focus-ring rounded-[var(--audit-radius-md)] border p-4 text-left ${
        selected
          ? "border-[var(--audit-primary-line)] bg-[var(--audit-primary-soft)]"
          : "border-[var(--audit-line)] bg-[var(--audit-surface-muted)] hover:bg-white"
      }`}
      onClick={onSelect}
      type="button"
    >
      <span className="flex flex-wrap items-start justify-between gap-3">
        <span>
          <span className="audit-card-title block">{permissionRole.name}</span>
          <span className="audit-meta mt-1 block">映射项目角色：{permissionRole.mapsToProjectRole}</span>
        </span>
        <StatusPill tone={selected ? "info" : "neutral"}>{permissionRole.departmentHint}</StatusPill>
      </span>
      <span className="audit-copy mt-3 block">{permissionRole.responsibility}</span>
      <span className="mt-3 flex flex-wrap gap-2">
        {permissionRole.allowedActions.slice(0, 2).map((action) => (
          <span className="audit-chip" key={action}>
            {action}
          </span>
        ))}
        {permissionRole.allowedActions.length > 2 ? (
          <span className="audit-chip">另 {permissionRole.allowedActions.length - 2} 项</span>
        ) : null}
      </span>
      <span className="audit-meta mt-3 line-clamp-2 block">{permissionRole.boundary}</span>
    </button>
  );
}

function SummaryRow({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-[var(--audit-radius-md)] bg-[var(--audit-surface-muted)] px-3 py-2">
      <span className="text-sm text-[var(--audit-ink-muted)]">{label}</span>
      <span className="truncate text-sm font-semibold text-[var(--audit-ink)]">{value}</span>
    </div>
  );
}
