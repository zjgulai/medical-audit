"use client";

import { useState } from "react";

import {
  buildReplicaLocalGateNotice,
  ReplicaMetric,
  ReplicaNotice,
  ReplicaPageHeader
} from "@/components/replica/replica-page-kit";
import { useReplicaAnalyticsData } from "@/components/replica/use-replica-runtime";
import type { ReferenceAnalysisDataset } from "@/lib/reference-replica-data";

type AnalysisTab = "数据处理" | "绘制图表" | "生成底稿";

const analysisTabs: readonly AnalysisTab[] = ["数据处理", "绘制图表", "生成底稿"];
const analysisSteps = [
  { label: "上传数据", detail: "导入台账或明细" },
  { label: "选择目标", detail: "确定核验口径" },
  { label: "生成洞察", detail: "识别金额与字段异常" },
  { label: "沉淀底稿", detail: "输出可复核材料" }
] as const;
const analysisSignals = [
  { label: "异常金额", value: "17", detail: "预算金额与中标金额异常接近", tone: "blue" },
  { label: "重复收费", value: "9", detail: "同患者同项目疑似重复计费", tone: "amber" },
  { label: "字段缺失", value: "6", detail: "目录限制和诊疗记录待补证", tone: "slate" }
] as const;
const analysisTracks = [
  { label: "数据准备", value: "2 个数据集", detail: "合同台账、医保结算明细" },
  { label: "规则识别", value: "32 条规则", detail: "金额接近、重复收费、字段缺失" },
  { label: "图表研判", value: "4 张图表", detail: "金额分布、科室分布、异常趋势" },
  { label: "底稿输出", value: "3 份草稿", detail: "问题清单、取证建议、复核路径" }
] as const;
const workpaperSteps = ["校验字段", "生成图表", "形成结论", "导出底稿"] as const;

export default function AnalyticsPage() {
  const analyticsData = useReplicaAnalyticsData();
  const datasets = analyticsData.data.datasets;
  const [activeTab, setActiveTab] = useState<AnalysisTab>("数据处理");
  const [task, setTask] = useState("请识别台账中的异常金额、重复收费和字段缺失问题。");
  const [fileName, setFileName] = useState("");
  const [notice, setNotice] = useState("");
  const [selectedDatasetId, setSelectedDatasetId] = useState(datasets[0]?.id ?? "");
  const selectedDataset = datasets.find((dataset) => dataset.id === selectedDatasetId) ?? datasets[0];

  function runLocalAnalysis() {
    setNotice(buildReplicaLocalGateNotice({
      action: `${activeTab}结果预览`,
      nextStep: "文件上传与分析任务 API"
    }));
  }

  function recordDatasetAction(dataset: ReferenceAnalysisDataset, action: string) {
    setSelectedDatasetId(dataset.id);
    setNotice(buildReplicaLocalGateNotice({
      action: `${action}「${dataset.name}」`,
      nextStep: "数据分析任务 API"
    }));
  }

  return (
    <main
      className="replica-page"
      data-replica-source={analyticsData.source}
      data-replica-status={analyticsData.status}
    >
      <ReplicaPageHeader
        kicker="AI数据分析"
        title="AI数据分析"
        description="对审计台账执行数据处理、绘图和底稿生成预演，上传与分析保持本地门禁。"
        actions={<button type="button" className="replica-primary-button" onClick={runLocalAnalysis}>开始分析</button>}
      />

      <section className="replica-metric-grid">
        <ReplicaMetric label="数据集" value={`${datasets.length}`} />
        <ReplicaMetric label="总行数" value={datasets.reduce((sum, item) => sum + item.rows, 0).toLocaleString()} tone="green" />
        <ReplicaMetric label="字段数" value={datasets.reduce((sum, item) => sum + item.columns, 0).toLocaleString()} tone="amber" />
        <ReplicaMetric label="审计阶段" value="预分析" tone="slate" />
      </section>

      <section className="replica-analysis-process" aria-label="分析流程">
        {analysisSteps.map((step, index) => (
          <article key={step.label} className="replica-analysis-step">
            <span>{String(index + 1).padStart(2, "0")}</span>
            <strong>{step.label}</strong>
            <p>{step.detail}</p>
          </article>
        ))}
      </section>

      <section className="replica-analysis-track" aria-label="审计分析轨道">
        {analysisTracks.map((track) => (
          <article key={track.label}>
            <span>{track.label}</span>
            <strong>{track.value}</strong>
            <p>{track.detail}</p>
          </article>
        ))}
      </section>

      <section className="replica-analysis-grid">
        <div className="replica-panel">
          <div className="replica-upload-box">
            <span aria-hidden="true">⇧</span>
            <strong>上传数据文件</strong>
            <p>支持表格、CSV、审计台账等材料。当前仅记录文件名。</p>
            <label className="replica-secondary-button">
              选择文件
              <input
                type="file"
                onChange={(event) => {
                  const nextFileName = event.target.files?.[0]?.name ?? "";
                  setFileName(nextFileName);
                  if (nextFileName) {
                    setNotice(buildReplicaLocalGateNotice({
                      action: `选择文件「${nextFileName}」`,
                      nextStep: "文件上传 API"
                    }));
                  }
                }}
              />
            </label>
            {fileName && <em>{fileName}</em>}
          </div>

          <div className="replica-statebar" aria-label="数据分析状态">
            <span>{activeTab}</span>
            <strong>{fileName ? "已选择文件" : "未选择文件"}</strong>
            <span>本地预览</span>
          </div>

          <label className="replica-field">
            <span>分析需求</span>
            <textarea value={task} onChange={(event) => setTask(event.target.value)} />
          </label>

          <div className="replica-tab-row" aria-label="分析模式">
            {analysisTabs.map((tab) => (
              <button
                key={tab}
                type="button"
                className={activeTab === tab ? "is-active" : ""}
                onClick={() => setActiveTab(tab)}
              >
                {tab}
              </button>
            ))}
          </div>

          {notice && <ReplicaNotice>{notice}</ReplicaNotice>}
        </div>

        <div className="replica-panel replica-analysis-preview-panel">
          <div className="replica-results-head">
            <div>
              <p className="replica-kicker">{activeTab}</p>
              <h2>分析结果预览</h2>
            </div>
            <span>{datasets.length} 个数据集</span>
          </div>

          <div className="replica-analysis-signal-grid" aria-label="审计分析信号">
            {analysisSignals.map((signal) => (
              <article key={signal.label} className={`replica-analysis-signal-card tone-${signal.tone}`}>
                <div>
                  <span>{signal.label}</span>
                  <strong>{signal.value}</strong>
                </div>
                <p>{signal.detail}</p>
                <div className="replica-spark-bars" aria-hidden="true">
                  <i />
                  <i />
                  <i />
                  <i />
                </div>
              </article>
            ))}
          </div>

          <div className="replica-analysis-chart" aria-label="异常分布图表预览">
            <div>
              <span>异常分布</span>
              <strong>{selectedDataset?.name ?? "未选择数据集"}</strong>
            </div>
            <div className="replica-analysis-bars" aria-hidden="true">
              <i style={{ height: "42%" }} />
              <i style={{ height: "68%" }} />
              <i style={{ height: "55%" }} />
              <i style={{ height: "84%" }} />
              <i style={{ height: "37%" }} />
              <i style={{ height: "73%" }} />
            </div>
          </div>

          {selectedDataset ? (
            <aside className="replica-analysis-dataset-detail" aria-label="数据集详情预览">
              <div>
                <span>{selectedDataset.status}</span>
                <strong>{selectedDataset.name}</strong>
              </div>
              <p>{selectedDataset.insight}</p>
              <ol>
                {workpaperSteps.map((step) => (
                  <li key={step}>{step}</li>
                ))}
              </ol>
            </aside>
          ) : null}

          <div className="replica-dataset-list">
            {datasets.map((dataset) => (
              <article key={dataset.id} className={`replica-dataset-card ${selectedDataset?.id === dataset.id ? "is-selected" : ""}`}>
                <div>
                  <h3>{dataset.name}</h3>
                  <p>{dataset.insight}</p>
                </div>
                <dl>
                  <div>
                    <dt>行数</dt>
                    <dd>{dataset.rows.toLocaleString()}</dd>
                  </div>
                  <div>
                    <dt>字段</dt>
                    <dd>{dataset.columns}</dd>
                  </div>
                  <div>
                    <dt>状态</dt>
                    <dd>{dataset.status}</dd>
                  </div>
                </dl>
                <div className="replica-dataset-actions">
                  <button type="button" onClick={() => recordDatasetAction(dataset, "查看字段")}>查看字段</button>
                  <button type="button" onClick={() => recordDatasetAction(dataset, "生成图表")}>生成图表</button>
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}
