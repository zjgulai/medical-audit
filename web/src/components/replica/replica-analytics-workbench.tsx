"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { fetchAnalysisUploadHistory, uploadAnalysisTable } from "@/lib/api-client";
import type {
  TableAnalysisCase,
  TableAnalysisUploadHistoryResponse,
  TableAnalysisUploadResponse
} from "@/lib/api-types";

type HistoryPhase = "loading" | "ready" | "empty" | "degraded" | "error";

type HistoryState = {
  readonly phase: HistoryPhase;
  readonly response: TableAnalysisUploadHistoryResponse | null;
};

type AnalysisCaseOption = {
  readonly id: TableAnalysisCase;
  readonly label: string;
  readonly description: string;
  readonly requiredColumns: string;
  readonly exampleFileName: string;
  readonly exampleCsv: string;
};

const ANALYSIS_CASES: readonly AnalysisCaseOption[] = [
  {
    id: "audit-data",
    label: "审计数据分析",
    description: "识别重复记录、空值和可用于金额、患者、项目、时间核验的字段。",
    requiredColumns: "建议包含患者/对象、日期、项目、金额和医保支付等字段",
    exampleFileName: "审计数据分析案例.csv",
    exampleCsv: [
      "患者编号,就诊日期,项目编码,收费金额,医保支付",
      "P001,2026-01-01,A100,120.00,80.00",
      "P001,2026-01-01,A100,120.00,80.00",
      "P002,2026-01-02,B200,,50.00"
    ].join("\n")
  },
  {
    id: "dupont",
    label: "财务杜邦分析",
    description: "用可复核公式拆解盈利能力、资产使用效率、财务杠杆和净资产收益率。",
    requiredColumns: "必需字段：净利润、营业收入、平均总资产、平均净资产",
    exampleFileName: "财务杜邦分析案例.csv",
    exampleCsv: [
      "年度,净利润,营业收入,平均总资产,平均净资产",
      "2024,80,900,1800,720",
      "2025,100,1000,2000,800"
    ].join("\n")
  }
];

function errorMessage(error: unknown): string {
  return error instanceof Error && error.message.trim().length > 0
    ? error.message
    : "表格分析失败，请稍后重试。";
}

function truncatedSha256(value: string): string {
  return value.length > 18 ? `${value.slice(0, 12)}…${value.slice(-6)}` : value;
}

function caseOption(caseId: TableAnalysisCase): AnalysisCaseOption {
  return ANALYSIS_CASES.find((item) => item.id === caseId) ?? ANALYSIS_CASES[0];
}

export function ReplicaAnalyticsWorkbench() {
  const [analysisCase, setAnalysisCase] = useState<TableAnalysisCase>("audit-data");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadResult, setUploadResult] = useState<TableAnalysisUploadResponse | null>(null);
  const [historyState, setHistoryState] = useState<HistoryState>({
    phase: "loading",
    response: null
  });
  const mountedRef = useRef(false);
  const uploadInFlightRef = useRef(false);
  const historyRequestRef = useRef(0);
  const activeCase = caseOption(analysisCase);

  const loadHistory = useCallback(async () => {
    const requestId = ++historyRequestRef.current;
    setHistoryState({ phase: "loading", response: null });
    try {
      const response = await fetchAnalysisUploadHistory();
      if (!mountedRef.current || requestId !== historyRequestRef.current) return;
      setHistoryState({
        phase: !response.store.ready
          ? "degraded"
          : response.items.length === 0
            ? "empty"
            : "ready",
        response
      });
    } catch {
      if (!mountedRef.current || requestId !== historyRequestRef.current) return;
      setHistoryState({ phase: "error", response: null });
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    void loadHistory();
    return () => {
      mountedRef.current = false;
    };
  }, [loadHistory]);

  function chooseFile(file: File | null) {
    setSelectedFile(file);
    setUploadError(null);
    setUploadResult(null);
  }

  function chooseCase(nextCase: TableAnalysisCase) {
    if (nextCase === analysisCase) return;
    setAnalysisCase(nextCase);
    chooseFile(null);
  }

  function loadExample() {
    chooseFile(
      new File([`\uFEFF${activeCase.exampleCsv}`], activeCase.exampleFileName, {
        type: "text/csv;charset=utf-8"
      })
    );
  }

  async function submitUpload() {
    if (!selectedFile || uploadInFlightRef.current) return;
    uploadInFlightRef.current = true;
    setUploading(true);
    setUploadError(null);
    setUploadResult(null);
    try {
      const response = await uploadAnalysisTable(selectedFile, analysisCase);
      if (!mountedRef.current) return;
      setUploadResult(response);
      void loadHistory();
    } catch (error) {
      if (mountedRef.current) setUploadError(errorMessage(error));
    } finally {
      uploadInFlightRef.current = false;
      if (mountedRef.current) setUploading(false);
    }
  }

  return (
    <main className="replica-page replica-page-standard replica-analytics-workbench">
      <header className="replica-page-header">
        <div>
          <p className="replica-kicker">表格分析</p>
          <h1>选择一个审计案例，上传数据即可得到可复核结果</h1>
          <p>先用内置案例了解所需字段，再替换为真实 CSV 或 XLSX 文件。</p>
        </div>
      </header>

      <section className="replica-analytics-cases" aria-labelledby="analysis-case-title">
        <div className="replica-analytics-section-heading">
          <div>
            <p className="replica-kicker">第 1 步</p>
            <h2 id="analysis-case-title">选择分析案例</h2>
          </div>
        </div>
        <div className="replica-analytics-case-grid" role="radiogroup" aria-label="分析案例">
          {ANALYSIS_CASES.map((item) => {
            const selected = item.id === analysisCase;
            return (
              <button
                type="button"
                role="radio"
                aria-checked={selected}
                className={`replica-analytics-case${selected ? " is-selected" : ""}`}
                key={item.id}
                onClick={() => chooseCase(item.id)}
              >
                <strong>{item.label}</strong>
                <span>{item.description}</span>
                <small>{item.requiredColumns}</small>
              </button>
            );
          })}
        </div>
      </section>

      <section className="replica-analytics-upload" aria-labelledby="analytics-upload-title">
        <div className="replica-analytics-section-heading">
          <div>
            <p className="replica-kicker">第 2 步</p>
            <h2 id="analytics-upload-title">上传数据并执行{activeCase.label}</h2>
          </div>
          <button type="button" className="replica-secondary-button" onClick={loadExample}>
            载入{activeCase.label}案例
          </button>
        </div>
        <p className="replica-analytics-case-requirement">{activeCase.requiredColumns}</p>
        <label className="replica-analytics-file-field">
          <span>选择 CSV 或 XLSX 文件</span>
          <span className="replica-analytics-file-picker">
            <span className="replica-analytics-file-button" aria-hidden="true">浏览本地文件</span>
            <small aria-hidden="true">CSV / XLSX，单文件</small>
            <input
              className="replica-analytics-file-input"
              type="file"
              accept=".xlsx,.csv"
              aria-label="选择分析表格"
              disabled={uploading}
              onChange={(event) => chooseFile(event.target.files?.[0] ?? null)}
            />
          </span>
        </label>
        <p className="replica-analytics-selection">
          {selectedFile ? `已选择：${selectedFile.name}（尚未提交）` : "尚未选择文件"}
        </p>
        <button
          type="button"
          className="replica-primary-button"
          disabled={!selectedFile || uploading}
          onClick={() => void submitUpload()}
        >
          {uploading ? "正在分析…" : `开始${activeCase.label}`}
        </button>
        {uploading ? (
          <p className="replica-analytics-status" role="status" aria-live="polite">
            正在读取表格并生成可复核结果…
          </p>
        ) : null}
        {uploadError ? (
          <p className="replica-analytics-error" role="alert">
            分析失败：{uploadError}
          </p>
        ) : null}
        <details className="replica-runtime-diagnostics">
          <summary>处理与留痕说明</summary>
          <p>
            提交文件会形成受权限控制的分析记录；本页当前使用确定性规则与公式，
            不调用外部大模型。
          </p>
          <code>provider_call=false</code>
        </details>
      </section>

      {uploadResult ? <AnalysisResult response={uploadResult} /> : null}

      <HistoryPanel state={historyState} onReload={() => void loadHistory()} />

      <aside className="replica-analytics-followup" aria-label="分析后续入口">
        <div>
          <h2>把分析结果带入审计交付</h2>
          <p>继续核对原始依据，或进入报告与底稿页面整理审计结论。</p>
        </div>
        <nav aria-label="分析后续入口">
          <Link href="/documents">核对原始文档</Link>
          <Link href="/reports">形成报告与底稿</Link>
        </nav>
      </aside>
    </main>
  );
}

function AnalysisResult({ response }: { readonly response: TableAnalysisUploadResponse }) {
  return (
    <section className="replica-analytics-result" aria-label="本次分析结果">
      <div className="replica-analytics-section-heading">
        <div>
          <p className="replica-kicker">第 3 步</p>
          <h2>{response.analysis_case_label}结果</h2>
        </div>
        <span className={`replica-analytics-retention is-${response.case_status}`}>
          {response.case_status === "completed" ? "分析完成" : "需要补充数据"}
        </span>
      </div>

      <div className="replica-analytics-metric-grid" aria-label="关键分析指标">
        {response.case_metrics.map((metric) => (
          <article className={`is-${metric.status}`} key={metric.key}>
            <span>{metric.label}</span>
            <strong>{metric.display_value}</strong>
            {metric.formula ? <small>{metric.formula}</small> : null}
          </article>
        ))}
      </div>

      <div className="replica-analytics-findings-grid">
        <ResultList title="分析结论" items={response.case_findings} />
        <ResultList title="复核建议" items={response.recommendations} />
      </div>

      <details className="replica-analytics-detail-panel">
        <summary>查看字段识别与数据质量</summary>
        <dl className="replica-analytics-definitions replica-analytics-file-metrics">
          <Definition term="文件" value={response.name} />
          <Definition term="工作表" value={response.sheet_name ?? "不适用"} />
          <Definition term="数据行" value={String(response.row_count)} />
          <Definition term="重复行" value={String(response.duplicate_row_count)} />
          <Definition term="空单元格" value={String(response.empty_cell_count)} />
        </dl>
        <p className="replica-analytics-message">{response.message}</p>
        <div className="replica-analytics-table-wrap">
          <table>
            <caption>字段识别结果</caption>
            <thead>
              <tr>
                <th scope="col">字段</th>
                <th scope="col">类型</th>
                <th scope="col">空值</th>
                <th scope="col">唯一值</th>
                <th scope="col">样例</th>
                <th scope="col">审计提示</th>
              </tr>
            </thead>
            <tbody>
              {response.columns.map((column, index) => (
                <tr key={`${column.name}-${index}`}>
                  <td>{column.name}</td>
                  <td>{column.type}</td>
                  <td>{column.empty_count}</td>
                  <td>{column.unique_count}</td>
                  <td>{column.sample_values.length > 0 ? column.sample_values.join("、") : "无样例"}</td>
                  <td>{column.audit_hint}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="replica-analytics-findings-grid">
          <ResultList title="数据质量" items={response.quality_findings} />
          <ResultList title="识别到的审计维度" items={response.audit_signals} />
        </div>
      </details>

      <details className="replica-analytics-detail-panel replica-analytics-admin-details">
        <summary>管理与审计详情</summary>
        <p className="replica-analytics-retention-note">
          {response.retention_status === "retained"
            ? "已保留分析文件和结果记录。"
            : "分析记录存储未配置，本次结果未保留。"}
        </p>
        <dl className="replica-analytics-definitions replica-analytics-evidence">
          <Definition term="记录 ID" value={response.upload_id ?? "未生成"} />
          <Definition term="文件指纹" value={response.sha256 ?? "未生成"} />
          <Definition term="留存状态" value={response.retention_status} />
          <Definition term="生成时间" value={response.created_at ?? "未记录"} />
          <Definition term="外部模型调用" value="否" />
        </dl>
      </details>
    </section>
  );
}

function ResultList({ title, items }: { readonly title: string; readonly items: readonly string[] }) {
  return (
    <article>
      <h3>{title}</h3>
      {items.length > 0 ? (
        <ul>
          {items.map((item, index) => <li key={`${title}-${index}`}>{item}</li>)}
        </ul>
      ) : (
        <p>当前没有该类结果</p>
      )}
    </article>
  );
}

function HistoryPanel({
  state,
  onReload
}: {
  readonly state: HistoryState;
  readonly onReload: () => void;
}) {
  const response = state.response;
  return (
    <section className="replica-analytics-history" aria-label="分析记录">
      <div className="replica-analytics-section-heading">
        <div>
          <p className="replica-kicker">最近工作</p>
          <h2>分析记录</h2>
        </div>
        <button type="button" className="replica-secondary-button" onClick={onReload}>
          刷新
        </button>
      </div>

      {state.phase === "loading" ? (
        <p className="replica-analytics-status" role="status" aria-live="polite">
          正在读取分析记录…
        </p>
      ) : null}
      {state.phase === "error" ? (
        <div className="replica-analytics-error" role="alert">
          <p>分析记录读取失败</p>
          <button type="button" className="replica-secondary-button" onClick={onReload}>
            重试
          </button>
        </div>
      ) : null}
      {state.phase === "empty" ? <p className="replica-analytics-empty">当前没有分析记录</p> : null}
      {state.phase === "degraded" ? (
        <p className="replica-analytics-degraded" role="status">分析记录暂不可用</p>
      ) : null}

      {response?.items.length ? (
        <div className="replica-analytics-history-list">
          {response.items.map((item) => (
            <article key={item.id} aria-label={item.name}>
              <div>
                <span className="replica-analytics-history-case">{item.analysis_case_label}</span>
                <h3>{item.name}</h3>
                <p>{item.created_at.slice(0, 10)} · {item.row_count} 行数据</p>
                <p>
                  {item.audit_signals.length > 0
                    ? `已识别：${item.audit_signals.join("、")}`
                    : "尚未识别常用审计字段"}
                </p>
              </div>
              <details className="replica-analytics-history-details">
                <summary>管理信息</summary>
                <dl className="replica-analytics-definitions">
                  <Definition term="记录 ID" value={item.id} />
                  <Definition term="文件大小" value={`${item.size_kb} KB`} />
                  <Definition term="字段数" value={String(item.column_count)} />
                  <Definition term="空单元格" value={String(item.empty_cell_count)} />
                  <Definition term="重复行" value={String(item.duplicate_row_count)} />
                  <Definition term="文件指纹" value={truncatedSha256(item.sha256)} />
                </dl>
              </details>
            </article>
          ))}
        </div>
      ) : null}

      {response ? (
        <details className="replica-analytics-admin-details">
          <summary>记录服务状态</summary>
          <dl className="replica-analytics-definitions replica-analytics-store">
            <Definition term="服务可用" value={response.store.ready ? "是" : "否"} />
            <Definition term="存储实现" value={response.store.backend} />
          </dl>
        </details>
      ) : null}
    </section>
  );
}

function Definition({ term, value }: { readonly term: string; readonly value: string }) {
  return (
    <div>
      <dt>{term}</dt>
      <dd>{value}</dd>
    </div>
  );
}
