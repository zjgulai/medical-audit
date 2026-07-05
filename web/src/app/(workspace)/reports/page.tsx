"use client";

import { useEffect, useState } from "react";

import { referenceHistoryItems } from "@/lib/reference-replica-data";
import type { ReferenceReportRecord } from "@/lib/reference-replica-data";
import {
  buildReplicaLocalGateNotice,
  ReplicaMetric,
  ReplicaNotice,
  ReplicaPageHeader
} from "@/components/replica/replica-page-kit";
import { useReplicaProjectsData, useReplicaReportsData } from "@/components/replica/use-replica-runtime";

type ReportAction = "查看底稿" | "导出报告" | "提交签发";

export default function ReportsPage() {
  const reportsData = useReplicaReportsData();
  const projectsData = useReplicaProjectsData();
  const reportRecords = reportsData.data.records;
  const projects = projectsData.data.projects;
  const [selectedProject, setSelectedProject] = useState(projects[0]?.id ?? "");
  const [selectedHistory, setSelectedHistory] = useState<readonly string[]>([]);
  const [selectedReportId, setSelectedReportId] = useState(reportRecords[0]?.id ?? "");
  const [reportDetailOpen, setReportDetailOpen] = useState(false);
  const [activeReportAction, setActiveReportAction] = useState<ReportAction | null>(null);
  const [notice, setNotice] = useState("");
  const selectedReport = reportRecords.find((record) => record.id === selectedReportId) ?? reportRecords[0];

  useEffect(() => {
    if (projects.length === 0) {
      setSelectedProject("");
      return;
    }
    if (!projects.some((project) => project.id === selectedProject)) {
      setSelectedProject(projects[0]?.id ?? "");
    }
  }, [projects, selectedProject]);

  useEffect(() => {
    if (reportRecords.length === 0) {
      setSelectedReportId("");
      setReportDetailOpen(false);
      return;
    }

    if (!reportRecords.some((record) => record.id === selectedReportId)) {
      setSelectedReportId(reportRecords[0]?.id ?? "");
    }
  }, [reportRecords, selectedReportId]);

  function toggleHistory(id: string) {
    setSelectedHistory((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id]
    );
  }

  function generateWorkpaper() {
    if (selectedHistory.length === 0) {
      setNotice("请先选择要纳入底稿的历史会话。");
      return;
    }
    setNotice(buildReplicaLocalGateNotice({
      action: `生成 ${selectedHistory.length} 条历史会话的底稿预览`,
      nextStep: "报告生成任务 API"
    }));
  }

  function runReportAction(record: ReferenceReportRecord, action: ReportAction) {
    setSelectedReportId(record.id);
    setReportDetailOpen(true);
    setActiveReportAction(action);
    setNotice(buildReplicaLocalGateNotice({
      action: `${action}「${record.title}」`,
      nextStep: getReportActionNextStep(action)
    }));
  }

  return (
    <main
      className="replica-page"
      data-replica-source={reportsData.source}
      data-replica-status={reportsData.status}
    >
      <ReplicaPageHeader
        kicker="审计底稿/报告"
        title="底稿与报告"
        description="选择项目和会话范围，先生成可复核底稿，再进入正式签发。"
        actions={<button type="button" className="replica-primary-button" onClick={generateWorkpaper}>一键生成底稿</button>}
      />

      <section className="replica-metric-grid">
        <ReplicaMetric label="历史记录" value={`${reportRecords.length}`} />
        <ReplicaMetric label="可选会话" value={`${referenceHistoryItems.length}`} tone="green" />
        <ReplicaMetric label="已选择" value={`${selectedHistory.length}`} tone="amber" />
        <ReplicaMetric label="模式" value="草稿预览" tone="slate" />
      </section>

      <section className="replica-report-layout">
        <div className="replica-panel">
          <label className="replica-field">
            <span>项目</span>
            <select value={selectedProject} onChange={(event) => setSelectedProject(event.target.value)}>
              {projects.map((project) => (
                <option key={project.id} value={project.id}>{project.name}</option>
              ))}
            </select>
          </label>

          <div className="replica-statebar" aria-label="底稿生成状态">
            <span>{projects.find((project) => project.id === selectedProject)?.type ?? "未选择项目"}</span>
            <strong>{selectedHistory.length} 条已选</strong>
            <span>本地草稿</span>
          </div>

          <div className="replica-history-select">
            <div className="replica-results-head">
              <div>
                <p className="replica-kicker">历史对话</p>
                <h2>选择生成范围</h2>
              </div>
              <span>选择要纳入底稿的会话</span>
            </div>
            {referenceHistoryItems.slice(0, 8).map((item) => (
              <label key={item.id}>
                <input
                  type="checkbox"
                  aria-label={item.title}
                  className="replica-large-checkbox"
                  checked={selectedHistory.includes(item.id)}
                  onChange={() => toggleHistory(item.id)}
                />
                <span>{item.title}</span>
              </label>
            ))}
          </div>

          {notice && <ReplicaNotice>{notice}</ReplicaNotice>}
        </div>

        <div className="replica-panel">
          <div className="replica-results-head">
            <div>
              <p className="replica-kicker">历史生成记录</p>
              <h2>历史生成记录</h2>
            </div>
            <span>{reportRecords.length} 条</span>
          </div>
          <div className="replica-record-list">
            {reportRecords.map((record) => (
              <article key={record.id} className={selectedReportId === record.id ? "is-active" : ""}>
                <div>
                  <h3>{record.title}</h3>
                  <p>{record.project} / {record.generatedAt}</p>
                </div>
                <span>{record.status}</span>
                <strong>{record.sourceCount} 条来源</strong>
                <div className="replica-record-actions">
                  <button type="button" onClick={() => runReportAction(record, "查看底稿")}>
                    查看底稿
                  </button>
                  <button type="button" onClick={() => runReportAction(record, "导出报告")}>
                    导出报告
                  </button>
                </div>
              </article>
            ))}
          </div>
          {reportDetailOpen && selectedReport ? (
            <section className="replica-report-detail" aria-label="报告详情预览">
              <div className="replica-results-head">
                <div>
                  <p className="replica-kicker">报告详情</p>
                  <h2>{selectedReport.title}</h2>
                </div>
                <button type="button" aria-label="关闭报告详情" onClick={() => setReportDetailOpen(false)}>×</button>
              </div>
              <dl>
                <div>
                  <dt>所属项目</dt>
                  <dd>{selectedReport.project}</dd>
                </div>
                <div>
                  <dt>当前状态</dt>
                  <dd>{selectedReport.status}</dd>
                </div>
                <div>
                  <dt>生成时间</dt>
                  <dd>{selectedReport.generatedAt}</dd>
                </div>
                <div>
                  <dt>来源证据</dt>
                  <dd>{selectedReport.sourceCount} 条</dd>
                </div>
              </dl>
              <div className="replica-card-actions">
                <button type="button" onClick={() => runReportAction(selectedReport, "查看底稿")}>查看底稿</button>
                <button type="button" onClick={() => runReportAction(selectedReport, "导出报告")}>导出报告</button>
                <button type="button" onClick={() => runReportAction(selectedReport, "提交签发")}>提交签发</button>
              </div>
              {activeReportAction ? (
                <div className="replica-report-next-panel" aria-label="报告后续操作预览">
                  <strong>{activeReportAction}</strong>
                  <p>{getReportActionPreview(selectedReport, activeReportAction)}</p>
                </div>
              ) : null}
            </section>
          ) : null}
        </div>
      </section>
    </main>
  );
}

function getReportActionNextStep(action: ReportAction) {
  if (action === "查看底稿") {
    return "报告详情 API";
  }

  if (action === "导出报告") {
    return "报告导出 API";
  }

  return "报告签发流程 API";
}

function getReportActionPreview(record: ReferenceReportRecord, action: ReportAction) {
  if (action === "查看底稿") {
    return `已打开 ${record.sourceCount} 条来源证据的底稿预览，正式环境需拉取报告详情与证据链。`;
  }

  if (action === "导出报告") {
    return `已生成「${record.title}」导出确认态，正式环境需进入受控下载与水印审计。`;
  }

  return `已进入「${record.title}」签发前确认态，正式环境需按角色流转到复核与签发。`;
}
