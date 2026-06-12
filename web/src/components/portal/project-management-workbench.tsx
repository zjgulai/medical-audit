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
    <main className="grid min-w-0 gap-5 xl:grid-cols-[minmax(0,1fr)_22rem]">
      <section className="min-w-0 space-y-5">
        <div className="min-w-0 rounded-2xl border border-slate-200 bg-white p-6 shadow-[var(--audit-shadow-card)]">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="text-sm font-semibold text-blue-700">项目管理</p>
              <h1 className="mt-2 text-3xl font-semibold text-slate-950">审计项目管理</h1>
              <p className="mt-2 text-sm text-slate-500">
                {project.organizationName} · {project.dateRange}
              </p>
            </div>
            <StatusPill tone="success">项目进行中</StatusPill>
          </div>

          <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-lg font-semibold text-slate-950">项目列表</h2>
            <label className="block w-full min-w-0 sm:min-w-64 sm:max-w-80">
              <span className="sr-only">搜索项目</span>
              <input
                className="audit-focus-ring w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
                value={projectQuery}
                onChange={(event) => setProjectQuery(event.target.value)}
                placeholder="搜索项目、专题、创建人"
                aria-label="搜索项目"
              />
            </label>
          </div>

          <div className="mt-4 max-w-full overflow-x-auto rounded-2xl border border-slate-200">
            <table className="w-full min-w-[58rem] text-left text-sm">
              <thead className="bg-slate-50 text-slate-500">
                <tr>
                  <th className="px-4 py-3 font-semibold">序号</th>
                  <th className="px-4 py-3 font-semibold">项目名称</th>
                  <th className="px-4 py-3 font-semibold">成员数</th>
                  <th className="px-4 py-3 font-semibold">创建人</th>
                  <th className="px-4 py-3 font-semibold">创建时间</th>
                  <th className="px-4 py-3 font-semibold">状态</th>
                  <th className="px-4 py-3 font-semibold">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {filteredProjects.map((item, index) => (
                  <tr key={item.id} className={item.id === selectedProject.id ? "bg-blue-50/60" : undefined}>
                    <td className="px-4 py-3 text-slate-500">{index + 1}</td>
                    <td className="px-4 py-3">
                      <p className="font-semibold text-slate-950">{item.name}</p>
                      <p className="mt-1 text-xs text-slate-500">
                        {item.organizationName} · {item.auditTopic}
                      </p>
                    </td>
                    <td className="px-4 py-3 text-slate-700">{item.id === selectedProject.id ? members.length : item.memberCount}</td>
                    <td className="px-4 py-3 text-slate-700">{item.creator}</td>
                    <td className="px-4 py-3 text-slate-700">{item.createdAt}</td>
                    <td className="px-4 py-3">
                      <StatusPill tone={projectStatusTone[item.status]}>{item.status}</StatusPill>
                    </td>
                    <td className="px-4 py-3">
                      <button
                        className="audit-focus-ring rounded-xl border border-blue-200 bg-white px-3 py-2 text-sm font-semibold text-blue-700 hover:bg-blue-50"
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

        <div className="min-w-0 rounded-2xl border border-slate-200 bg-white p-6 shadow-[var(--audit-shadow-card)]">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="text-sm font-semibold text-blue-700">项目成员</p>
              <h2 className="mt-2 text-xl font-semibold text-slate-950">{selectedProject.name}</h2>
              <p className="mt-2 text-sm text-slate-500">角色展示和新增入口先用于首期项目空间组织，权限生效后置。</p>
            </div>
            <StatusPill tone={projectStatusTone[selectedProject.status]}>{selectedProject.status}</StatusPill>
          </div>

          <div className="mt-6 max-w-full overflow-x-auto rounded-2xl border border-slate-200">
            <table className="w-full min-w-[42rem] text-left text-sm">
              <thead className="bg-slate-50 text-slate-500">
                <tr>
                  <th className="px-4 py-3 font-semibold">成员</th>
                  <th className="px-4 py-3 font-semibold">角色</th>
                  <th className="px-4 py-3 font-semibold">部门</th>
                  <th className="px-4 py-3 font-semibold">状态</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {members.map((member) => (
                  <tr key={member.id}>
                    <td className="px-4 py-3 font-semibold text-slate-950">{member.name}</td>
                    <td className="px-4 py-3 text-slate-700">{member.role}</td>
                    <td className="px-4 py-3 text-slate-700">{member.department}</td>
                    <td className="px-4 py-3">
                      <StatusPill tone={member.status === "在项目中" ? "success" : "warning"}>{member.status}</StatusPill>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <aside className="min-w-0 rounded-2xl border border-slate-200 bg-white p-5 shadow-[var(--audit-shadow-card)]">
        <h2 className="text-lg font-semibold text-slate-950">新增成员</h2>
        <form className="mt-4 space-y-4" onSubmit={submitMember}>
          <label className="block">
            <span className="text-sm font-semibold text-slate-700">姓名</span>
            <input
              className="audit-focus-ring mt-2 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="成员姓名"
            />
          </label>
          <label className="block">
            <span className="text-sm font-semibold text-slate-700">角色</span>
            <select
              className="audit-focus-ring mt-2 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
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
            <span className="text-sm font-semibold text-slate-700">部门</span>
            <input
              className="audit-focus-ring mt-2 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
              value={department}
              onChange={(event) => setDepartment(event.target.value)}
            />
          </label>
          <button className="audit-focus-ring w-full rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-700" type="submit">
            添加成员
          </button>
        </form>
      </aside>
    </main>
  );
}
