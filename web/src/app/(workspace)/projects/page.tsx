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
import { fetchAuditFindings } from "@/lib/api-client";
import type { AuditFinding, AuditFindingsResponse } from "@/lib/api-types";
import type { ReferenceProject } from "@/lib/reference-replica-data";

type ProjectDialog = "新增项目" | "修改项目" | null;
type ProjectAction = "进入项目" | "成员管理" | "归档检查";
type FindingStoreStatus = "loading" | "ready" | "fallback";

export default function ProjectsPage() {
  const projectsData = useReplicaProjectsData();
  const projects = projectsData.data.projects;
  const [query, setQuery] = useState("");
  const [selectedProject, setSelectedProject] = useState<ReferenceProject | null>(projects[0] ?? null);
  const [dialog, setDialog] = useState<ProjectDialog>(null);
  const [activeProjectAction, setActiveProjectAction] = useState<ProjectAction | null>(null);
  const [notice, setNotice] = useState("");
  const [findingResponse, setFindingResponse] = useState<AuditFindingsResponse | null>(null);
  const [findingStoreStatus, setFindingStoreStatus] = useState<FindingStoreStatus>("loading");
  const filteredProjects = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return projects.filter((project) =>
      normalizedQuery.length === 0 ||
      `${project.name} ${project.type} ${project.owner} ${project.status}`.toLowerCase().includes(normalizedQuery)
    );
  }, [projects, query]);
  const totalMembers = projects.reduce((sum, project) => sum + project.members, 0);
  const auditCockpit = useMemo(() => buildProjectAuditCockpit(findingResponse, projects), [findingResponse, projects]);

  useEffect(() => {
    if (projects.length === 0) {
      setSelectedProject(null);
      return;
    }
    if (!selectedProject || !projects.some((project) => project.id === selectedProject.id)) {
      setSelectedProject(projects[0] ?? null);
    }
  }, [projects, selectedProject]);

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

      <AuditCockpitPanel
        cockpit={auditCockpit}
        storeStatus={findingStoreStatus}
        storeBackend={findingResponse?.store.backend ?? null}
      />

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

const unassignedOwner = "未分配";

type CockpitStatusRow = {
  readonly key: string;
  readonly label: string;
  readonly count: number;
};

type CockpitMemberRow = {
  readonly name: string;
  readonly total: number;
  readonly pending: number;
};

type ProjectAuditCockpit = {
  readonly source: "findings" | "project-fallback";
  readonly total: number;
  readonly pendingReview: number;
  readonly linkedReviewTask: number;
  readonly unassigned: number;
  readonly statusRows: readonly CockpitStatusRow[];
  readonly memberRows: readonly CockpitMemberRow[];
};

function buildProjectAuditCockpit(
  response: AuditFindingsResponse | null,
  projects: readonly ReferenceProject[]
): ProjectAuditCockpit {
  if (!response) {
    return buildProjectFallbackCockpit(projects);
  }

  const statusCounts = new Map<string, number>();
  const memberCounts = new Map<string, { total: number; pending: number }>();
  for (const project of projects) {
    if (project.owner.trim()) {
      memberCounts.set(project.owner, { total: 0, pending: 0 });
    }
  }
  memberCounts.set(unassignedOwner, memberCounts.get(unassignedOwner) ?? { total: 0, pending: 0 });

  for (const finding of response.items) {
    statusCounts.set(finding.review_status, (statusCounts.get(finding.review_status) ?? 0) + 1);
    const owner = findingOwner(finding);
    const current = memberCounts.get(owner) ?? { total: 0, pending: 0 };
    current.total += 1;
    if (isPendingReviewStatus(finding.review_status)) {
      current.pending += 1;
    }
    memberCounts.set(owner, current);
  }

  const total = response.stats.total ?? response.items.length;
  const statusRows = Array.from(statusCounts.entries())
    .map(([status, count]) => ({
      key: status,
      label: response.review_status_options[status] ?? status,
      count
    }))
    .sort((left, right) => right.count - left.count || left.label.localeCompare(right.label, "zh-CN"));

  return {
    source: "findings",
    total,
    pendingReview: response.stats.pending_review ?? countPendingFindings(response.items),
    linkedReviewTask: response.stats.linked_review_task ?? response.items.filter((item) => item.review_task_id).length,
    unassigned: memberCounts.get(unassignedOwner)?.total ?? 0,
    statusRows: statusRows.length > 0 ? statusRows : [{ key: "empty", label: "暂无疑点", count: 0 }],
    memberRows: buildMemberRows(memberCounts)
  };
}

function buildProjectFallbackCockpit(projects: readonly ReferenceProject[]): ProjectAuditCockpit {
  const statusCounts = new Map<string, number>();
  const memberCounts = new Map<string, { total: number; pending: number }>();
  let total = 0;
  let pendingReview = 0;
  let linkedReviewTask = 0;

  for (const project of projects) {
    const count = Math.max(project.members, 1);
    total += count;
    statusCounts.set(project.status, (statusCounts.get(project.status) ?? 0) + count);
    const pending = project.progress >= 100 ? 0 : Math.max(1, Math.round(count * (100 - project.progress) / 100));
    pendingReview += pending;
    linkedReviewTask += Math.max(0, count - pending);
    const owner = project.owner.trim() || unassignedOwner;
    const current = memberCounts.get(owner) ?? { total: 0, pending: 0 };
    current.total += count;
    current.pending += pending;
    memberCounts.set(owner, current);
  }

  return {
    source: "project-fallback",
    total,
    pendingReview,
    linkedReviewTask,
    unassigned: memberCounts.get(unassignedOwner)?.total ?? 0,
    statusRows: Array.from(statusCounts.entries())
      .map(([status, count]) => ({ key: status, label: status, count }))
      .sort((left, right) => right.count - left.count || left.label.localeCompare(right.label, "zh-CN")),
    memberRows: buildMemberRows(memberCounts)
  };
}

function buildMemberRows(memberCounts: Map<string, { total: number; pending: number }>): readonly CockpitMemberRow[] {
  const rows = Array.from(memberCounts.entries())
    .map(([name, count]) => ({ name, ...count }))
    .sort((left, right) => right.total - left.total || left.name.localeCompare(right.name, "zh-CN"))
    .slice(0, 8);
  return rows.length > 0 ? rows : [{ name: "暂无承接人", total: 0, pending: 0 }];
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

function isPendingReviewStatus(status: string) {
  return status === "pending-review" || status === "needs-evidence" || status === "open";
}

function countPendingFindings(findings: readonly AuditFinding[]) {
  return findings.filter((finding) => isPendingReviewStatus(finding.review_status)).length;
}

function AuditCockpitPanel({
  cockpit,
  storeStatus,
  storeBackend
}: {
  readonly cockpit: ProjectAuditCockpit;
  readonly storeStatus: FindingStoreStatus;
  readonly storeBackend: string | null;
}) {
  const statusLabel = buildCockpitStatusLabel(cockpit.source, storeStatus, storeBackend);
  return (
    <section className="replica-panel replica-project-cockpit" aria-label="审计驾驶舱">
      <div className="replica-results-head">
        <div>
          <p className="replica-kicker">审计驾驶舱</p>
          <h2>专题审计看板</h2>
          <p>汇总审计专题、复核状态和人员承接。</p>
        </div>
        <span>{statusLabel}</span>
      </div>

      <div className="replica-metric-grid">
        <ReplicaMetric label="总审计条数" value={`${cockpit.total}`} />
        <ReplicaMetric label="待复核" value={`${cockpit.pendingReview}`} tone="amber" />
        <ReplicaMetric label="已关联任务" value={`${cockpit.linkedReviewTask}`} tone="green" />
        <ReplicaMetric label="未分配" value={`${cockpit.unassigned}`} tone="slate" />
      </div>

      <div className="replica-cockpit-grid">
        <section aria-label="状态分布">
          <div className="replica-cockpit-section-head">
            <h3>状态分布</h3>
            <span>{cockpit.statusRows.length} 类状态</span>
          </div>
          <div className="replica-cockpit-list">
            {cockpit.statusRows.map((row) => (
              <StatusDistributionRow key={row.key} row={row} total={cockpit.total} />
            ))}
          </div>
        </section>

        <section aria-label="人员承接">
          <div className="replica-cockpit-section-head">
            <h3>人员承接</h3>
            <span>Top {cockpit.memberRows.length}</span>
          </div>
          <div className="replica-cockpit-list">
            {cockpit.memberRows.map((row) => (
              <MemberWorkloadRow key={row.name} row={row} />
            ))}
          </div>
        </section>
      </div>
    </section>
  );
}

function buildCockpitStatusLabel(source: ProjectAuditCockpit["source"], status: FindingStoreStatus, backend: string | null) {
  if (status === "loading") {
    return "同步中";
  }
  if (source === "findings") {
    return backend ? "疑点明细同步" : "审计数据同步";
  }
  return "项目列表兜底";
}

function StatusDistributionRow({
  row,
  total
}: {
  readonly row: CockpitStatusRow;
  readonly total: number;
}) {
  const ratio = total > 0 ? Math.min(100, Math.round((row.count / total) * 100)) : 0;
  return (
    <div className="replica-cockpit-row">
      <div>
        <strong>{row.label}</strong>
        <span>{row.count} 条</span>
      </div>
      <div className="replica-cockpit-bar" aria-hidden="true">
        <span style={{ width: `${ratio}%` }} />
      </div>
    </div>
  );
}

function MemberWorkloadRow({ row }: { readonly row: CockpitMemberRow }) {
  return (
    <div className="replica-cockpit-row">
      <div>
        <strong>{row.name}</strong>
        <span>{row.total} 条 / {row.pending} 待复核</span>
      </div>
      <div className="replica-cockpit-bar" aria-hidden="true">
        <span style={{ width: `${row.total > 0 ? Math.min(100, Math.round((row.pending / row.total) * 100)) : 0}%` }} />
      </div>
    </div>
  );
}
