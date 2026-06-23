"use client";

import { FormEvent, useEffect, useState } from "react";

import { useAuditUser } from "@/components/shell/audit-user-context";
import { StatusPill } from "@/components/ui/status-pill";
import { createProjectMember, fetchProjectMembers, fetchProjects } from "@/lib/api-client";
import type { ProjectMemberApiItem, ProjectSummaryApiItem } from "@/lib/api-types";
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
    <main className="grid min-w-0 gap-4 xl:grid-cols-[17rem_minmax(0,1fr)_18rem]">
      <aside className="audit-panel-rail min-w-0 p-5">
        <h2 className="audit-section-title">项目空间</h2>
        <p className="audit-copy mt-2">按审计专题切换项目，成员表随当前项目上下文展示。</p>
        <div className="mt-5 grid grid-cols-2 gap-2">
          <SidebarMetric label="进行中" value={String(activeProjectCount)} />
          <SidebarMetric label="待启动" value={String(pendingProjectCount)} />
        </div>
        <div className="mt-5 space-y-3">
          {portalProjectSummaries.map((item) => (
            <ProjectNavigatorItem
              key={item.id}
              item={item}
              selected={item.id === selectedProject.id}
              onSelect={() => setSelectedProjectId(item.id)}
            />
          ))}
        </div>
      </aside>

      <section className="min-w-0 space-y-5">
        <div className="audit-panel min-w-0 p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="audit-kicker">项目管理</p>
              <h1 className="audit-page-title">审计项目管理</h1>
              <p className="audit-meta mt-2">{project.organizationName} / {project.dateRange}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <StatusPill tone="success">项目进行中</StatusPill>
              <StatusPill tone={projectStoreStatus === "ready" ? "success" : "neutral"}>
                {projectStoreStatusLabel(projectStoreStatus)}
              </StatusPill>
            </div>
          </div>

          <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
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

          <div className="audit-table-shell mt-4 max-w-full overflow-x-auto">
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

        <div className="audit-panel min-w-0 p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="audit-kicker">项目成员</p>
              <h2 className="audit-section-title mt-2">{selectedProject.name}</h2>
              <p className="audit-copy mt-2">角色展示和新增入口已接入当前医院角色权限。</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <StatusPill tone={projectStatusTone[selectedProject.status]}>{selectedProject.status}</StatusPill>
              <StatusPill tone={memberStoreStatus === "ready" ? "success" : "neutral"}>
                {memberStoreStatusLabel(memberStoreStatus)}
              </StatusPill>
            </div>
          </div>

          <div className="audit-table-shell mt-6 max-w-full overflow-x-auto">
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

        <div className="audit-panel min-w-0 p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="audit-kicker">权限角色</p>
              <h2 className="audit-section-title mt-2">医院权限角色矩阵</h2>
              <p className="audit-copy mt-2">按用户提出的四类角色组织操作边界；后端项目成员角色暂不变。</p>
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

      <aside className="min-w-0 space-y-4">
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
      </aside>
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
    return "项目后端已连接";
  }
  if (status === "loading") {
    return "项目连接中";
  }
  return "项目默认内容";
}

function memberStoreStatusLabel(status: StoreStatus): string {
  if (status === "ready") {
    return "成员后端已连接";
  }
  if (status === "saving") {
    return "成员保存中";
  }
  if (status === "loading") {
    return "成员连接中";
  }
  return "成员默认内容";
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
      <span className="audit-meta mt-1 block truncate">{item.creator} / {item.createdAt}</span>
      <span className="mt-2 inline-flex">
        <StatusPill tone={projectStatusTone[item.status]}>{item.status}</StatusPill>
      </span>
    </button>
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
        {permissionRole.allowedActions.map((action) => (
          <span className="audit-chip" key={action}>
            {action}
          </span>
        ))}
      </span>
      <span className="audit-meta mt-3 block">{permissionRole.boundary}</span>
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
