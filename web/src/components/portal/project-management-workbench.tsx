"use client";

import { FormEvent, useState } from "react";

import { StatusPill } from "@/components/ui/status-pill";
import {
  defaultProjectMembers,
  portalProjectSummaries,
  PortalProjectMember,
  PortalProjectSummary
} from "@/lib/portal-data";
import { currentSelfCheckProject } from "@/lib/projects";

const memberRoles: readonly PortalProjectMember["role"][] = ["审计员", "业务专家", "信息科", "只读观察员"];
const projectStatusTone: Record<PortalProjectSummary["status"], "neutral" | "warning" | "success"> = {
  进行中: "success",
  待启动: "warning",
  已归档: "neutral"
};

export function ProjectManagementWorkbench() {
  const project = currentSelfCheckProject;
  const [selectedProjectId, setSelectedProjectId] = useState(project.id);
  const [members, setMembers] = useState<readonly PortalProjectMember[]>(defaultProjectMembers);
  const [projectQuery, setProjectQuery] = useState("");
  const [name, setName] = useState("");
  const [role, setRole] = useState<PortalProjectMember["role"]>("审计员");
  const [department, setDepartment] = useState("内审部");
  const normalizedProjectQuery = projectQuery.trim().toLowerCase();
  const filteredProjects = portalProjectSummaries.filter((item) => {
    if (!normalizedProjectQuery) {
      return true;
    }

    return [item.name, item.auditTopic, item.creator, item.organizationName].some((value) =>
      value.toLowerCase().includes(normalizedProjectQuery)
    );
  });
  const selectedProject = portalProjectSummaries.find((item) => item.id === selectedProjectId) ?? portalProjectSummaries[0];

  function submitMember(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalizedName = name.trim();
    const normalizedDepartment = department.trim();

    if (!normalizedName || !normalizedDepartment) {
      return;
    }

    setMembers((current) => [
      ...current,
      {
        id: `member-${Date.now()}`,
        name: normalizedName,
        role,
        department: normalizedDepartment,
        status: "待确认"
      }
    ]);
    setName("");
  }

  return (
    <main className="audit-page-grid audit-page-grid--rail min-w-0">
      <section className="min-w-0 space-y-5">
        <div className="audit-panel min-w-0 p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="audit-kicker">项目管理</p>
              <h1 className="audit-page-title">审计项目管理</h1>
              <p className="audit-meta mt-2">
                {project.organizationName} · {project.dateRange}
              </p>
            </div>
            <StatusPill tone="success">项目进行中</StatusPill>
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
                        {item.organizationName} · {item.auditTopic}
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
              <p className="audit-copy mt-2">角色展示和新增入口先用于首期项目空间组织，权限生效后置。</p>
            </div>
            <StatusPill tone={projectStatusTone[selectedProject.status]}>{selectedProject.status}</StatusPill>
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
      </section>

      <aside className="audit-panel-rail min-w-0 p-5">
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
            <span className="audit-label">角色</span>
            <select
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
          </label>
          <label className="block">
            <span className="audit-label">部门</span>
            <input
              className="audit-focus-ring audit-input mt-2 px-3 py-2"
              value={department}
              onChange={(event) => setDepartment(event.target.value)}
            />
          </label>
          <button className="audit-focus-ring audit-btn audit-btn-primary w-full" type="submit">
            添加成员
          </button>
        </form>
      </aside>
    </main>
  );
}
