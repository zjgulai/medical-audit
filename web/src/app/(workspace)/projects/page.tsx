"use client";

import { useEffect, useMemo, useState } from "react";

import {
  buildReplicaLocalGateNotice,
  ReplicaEmptyState,
  ReplicaMetric,
  ReplicaNotice,
  ReplicaPageHeader
} from "@/components/replica/replica-page-kit";
import { useReplicaProjectsData } from "@/components/replica/use-replica-runtime";
import type { ReferenceProject } from "@/lib/reference-replica-data";

type ProjectDialog = "新增项目" | "修改项目" | null;
type ProjectAction = "进入项目" | "成员管理" | "归档检查";

export default function ProjectsPage() {
  const projectsData = useReplicaProjectsData();
  const projects = projectsData.data.projects;
  const [query, setQuery] = useState("");
  const [selectedProject, setSelectedProject] = useState<ReferenceProject | null>(projects[0] ?? null);
  const [dialog, setDialog] = useState<ProjectDialog>(null);
  const [activeProjectAction, setActiveProjectAction] = useState<ProjectAction | null>(null);
  const [notice, setNotice] = useState("");
  const filteredProjects = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return projects.filter((project) =>
      normalizedQuery.length === 0 ||
      `${project.name} ${project.type} ${project.owner} ${project.status}`.toLowerCase().includes(normalizedQuery)
    );
  }, [projects, query]);
  const totalMembers = projects.reduce((sum, project) => sum + project.members, 0);

  useEffect(() => {
    if (projects.length === 0) {
      setSelectedProject(null);
      return;
    }
    if (!selectedProject || !projects.some((project) => project.id === selectedProject.id)) {
      setSelectedProject(projects[0] ?? null);
    }
  }, [projects, selectedProject]);

  function confirmDialog() {
    setNotice(buildReplicaLocalGateNotice({
      action: dialog ?? "项目操作",
      nextStep: "项目管理写入 API"
    }));
    setDialog(null);
  }

  function runProjectAction(action: ProjectAction) {
    if (!selectedProject) {
      setNotice("请先选择项目。");
      return;
    }

    setActiveProjectAction(action);
    setNotice(buildReplicaLocalGateNotice({
      action: `${action}「${selectedProject.name}」`,
      nextStep: getProjectActionNextStep(action)
    }));
  }

  return (
    <main
      className="replica-page"
      data-replica-source={projectsData.source}
      data-replica-status={projectsData.status}
    >
      <ReplicaPageHeader
        kicker="项目管理"
        title="项目管理"
        description="管理审计项目的成员、状态和进度，新增/修改弹层保持本地预览态。"
        actions={<button type="button" className="replica-primary-button" onClick={() => setDialog("新增项目")}>创建新项目</button>}
      />

      <section className="replica-metric-grid">
        <ReplicaMetric label="项目数" value={`${projects.length}`} />
        <ReplicaMetric label="项目成员数" value={`${totalMembers}`} tone="green" />
        <ReplicaMetric label="进行中" value={`${projects.filter((project) => project.status !== "底稿编制").length}`} tone="amber" />
        <ReplicaMetric label="当前用户" value="审计员" tone="slate" />
      </section>

      <section className="replica-panel">
        <div className="replica-toolbar">
          <label className="replica-search">
            <span aria-hidden="true">⌕</span>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="搜索项目名称"
            />
          </label>
          <button type="button" className="replica-secondary-button" onClick={() => setDialog("修改项目")}>修改项目</button>
        </div>
        <div className="replica-statebar" aria-label="项目列表状态">
          <span>{query.trim() ? "筛选中" : "全部项目"}</span>
          <strong>{filteredProjects.length} / {projects.length}</strong>
          <span>{selectedProject?.status ?? "未选择项目"}</span>
          <span>本地管理门禁</span>
        </div>
        {notice && <ReplicaNotice>{notice}</ReplicaNotice>}
      </section>

      <section className="replica-project-layout">
        <div className="replica-panel replica-project-table">
          {filteredProjects.length === 0 ? (
            <ReplicaEmptyState title="暂无项目" description="调整项目名称或负责人关键词后重试。" />
          ) : (
            <table>
              <thead>
                <tr>
                  <th>项目名称</th>
                  <th>类型</th>
                  <th>负责人</th>
                  <th>项目成员数</th>
                  <th>状态</th>
                  <th>更新时间</th>
                </tr>
              </thead>
              <tbody>
                {filteredProjects.map((project) => (
                  <tr
                    key={project.id}
                    className={selectedProject?.id === project.id ? "is-active" : ""}
                    onClick={() => setSelectedProject(project)}
                  >
                    <td>{project.name}</td>
                    <td>{project.type}</td>
                    <td>{project.owner}</td>
                    <td>{project.members}</td>
                    <td>{project.status}</td>
                    <td>{project.updatedAt}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <aside className="replica-panel replica-project-detail" aria-label="项目详情预览">
          <p className="replica-kicker">项目详情</p>
          <h2>{selectedProject?.name ?? "未选择项目"}</h2>
          <div className="replica-project-detail-meta">
            <span>{selectedProject?.updatedAt ?? "未记录更新时间"}</span>
            <span>{selectedProject?.status ?? "未记录状态"}</span>
          </div>
          <dl>
            <div>
              <dt>项目类型</dt>
              <dd>{selectedProject?.type ?? "未记录"}</dd>
            </div>
            <div>
              <dt>负责人</dt>
              <dd>{selectedProject?.owner ?? "未记录"}</dd>
            </div>
            <div>
              <dt>成员数</dt>
              <dd>{selectedProject?.members ?? 0}</dd>
            </div>
            <div>
              <dt>状态</dt>
              <dd>{selectedProject?.status ?? "未记录"}</dd>
            </div>
          </dl>
          <div className="replica-progress">
            <span style={{ width: `${selectedProject?.progress ?? 0}%` }} />
          </div>
          <strong>{selectedProject?.progress ?? 0}%</strong>
          <div className="replica-project-detail-actions">
            <button type="button" onClick={() => runProjectAction("进入项目")} disabled={!selectedProject}>进入项目</button>
            <button type="button" onClick={() => runProjectAction("成员管理")} disabled={!selectedProject}>成员管理</button>
            <button type="button" onClick={() => runProjectAction("归档检查")} disabled={!selectedProject}>归档检查</button>
            <button type="button" onClick={() => setDialog("修改项目")} disabled={!selectedProject}>修改当前项目</button>
          </div>
          {activeProjectAction && selectedProject ? (
            <section className="replica-project-action-panel" aria-label="项目后续操作预览">
              <div className="replica-results-head">
                <div>
                  <p className="replica-kicker">后续操作</p>
                  <h3>{activeProjectAction}</h3>
                </div>
                <button
                  type="button"
                  aria-label="关闭项目操作预览"
                  onClick={() => setActiveProjectAction(null)}
                >
                  ×
                </button>
              </div>
              <p>{getProjectActionPreview(selectedProject, activeProjectAction)}</p>
            </section>
          ) : null}
        </aside>
      </section>

      {dialog && (
        <div className="replica-modal-backdrop" role="presentation">
          <div className="replica-modal" role="dialog" aria-modal="true" aria-label={dialog}>
            <div className="replica-results-head">
              <div>
                <p className="replica-kicker">项目管理</p>
                <h2>{dialog}</h2>
              </div>
              <button type="button" onClick={() => setDialog(null)}>×</button>
            </div>
            <label className="replica-field">
              <span>项目名称</span>
              <input defaultValue={dialog === "修改项目" ? selectedProject?.name ?? "" : ""} placeholder="请输入项目名称" />
            </label>
            <label className="replica-field">
              <span>负责人</span>
              <input defaultValue={dialog === "修改项目" ? selectedProject?.owner ?? "" : "审计员"} placeholder="请输入负责人" />
            </label>
            <div className="replica-modal-actions">
              <button type="button" className="replica-secondary-button" onClick={() => setDialog(null)}>取消</button>
              <button type="button" className="replica-primary-button" onClick={confirmDialog}>确定</button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}

function getProjectActionNextStep(action: ProjectAction) {
  if (action === "进入项目") {
    return "项目工作台 API";
  }

  if (action === "成员管理") {
    return "项目成员权限 API";
  }

  return "归档检查 API";
}

function getProjectActionPreview(project: ReferenceProject, action: ProjectAction) {
  if (action === "进入项目") {
    return `已定位「${project.name}」的工作台入口，正式环境需加载任务、证据和项目动态。`;
  }

  if (action === "成员管理") {
    return `已打开 ${project.members} 名成员的管理预览，正式环境需校验角色、组织和权限写入。`;
  }

  return `已生成「${project.name}」归档前检查预览，正式环境需核对报告、附件、签名链和留痕策略。`;
}
