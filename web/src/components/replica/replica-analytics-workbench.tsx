"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";

import { fetchAnalysisUploadHistory, uploadAnalysisTable } from "@/lib/api-client";
import type {
  TableAnalysisUploadHistoryResponse,
  TableAnalysisUploadResponse
} from "@/lib/api-types";

type HistoryPhase = "loading" | "ready" | "empty" | "degraded" | "error";

type HistoryState = {
  readonly phase: HistoryPhase;
  readonly response: TableAnalysisUploadHistoryResponse | null;
};

function errorMessage(error: unknown): string {
  return error instanceof Error && error.message.trim().length > 0
    ? error.message
    : "表格上传分析失败，请稍后重试。";
}

function truncatedSha256(value: string): string {
  return value.length > 18 ? `${value.slice(0, 12)}…${value.slice(-6)}` : value;
}

export function ReplicaAnalyticsWorkbench() {
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

  async function submitUpload() {
    if (!selectedFile || uploadInFlightRef.current) return;
    uploadInFlightRef.current = true;
    setUploading(true);
    setUploadError(null);
    setUploadResult(null);
    try {
      const response = await uploadAnalysisTable(selectedFile);
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
          <p className="replica-kicker">AI 数据分析</p>
          <h1>表格分析工作台</h1>
          <p>上传 CSV 或 XLSX 表格，读取后端字段画像、数据质量线索与审计建议。</p>
        </div>
      </header>

      <section className="replica-analytics-upload" aria-labelledby="analytics-upload-title">
        <div>
          <p className="replica-kicker">受控分析</p>
          <h2 id="analytics-upload-title">上传表格</h2>
        </div>
        <p className="replica-analytics-boundary">
          上传是受控写入；只有分析记录服务就绪时才保留历史。当前分析不调用外部模型，
          选择文件只记录待提交项，不代表已经上传。
        </p>
        <details className="replica-runtime-diagnostics">
          <summary>查看处理边界</summary>
          <code>provider_call=false</code>
        </details>
        <label className="replica-analytics-file-field">
          <span>选择分析表格</span>
          <input
            type="file"
            accept=".xlsx,.csv"
            aria-label="选择分析表格"
            disabled={uploading}
            onChange={(event) => chooseFile(event.target.files?.[0] ?? null)}
          />
        </label>
        <p className="replica-analytics-selection">
          {selectedFile ? `已选择：${selectedFile.name}（尚未上传）` : "尚未选择文件"}
        </p>
        <button
          type="button"
          className="replica-primary-button"
          disabled={!selectedFile || uploading}
          onClick={() => void submitUpload()}
        >
          {uploading ? "上传分析中…" : "上传并分析"}
        </button>
        {uploading ? (
          <p className="replica-analytics-status" role="status" aria-live="polite">
            正在上传并等待后端完成字段画像…
          </p>
        ) : null}
        {uploadError ? (
          <p className="replica-analytics-error" role="alert">
            上传分析失败：{uploadError}
          </p>
        ) : null}
      </section>

      {uploadResult ? <AnalysisResult response={uploadResult} /> : null}

      <HistoryPanel state={historyState} onReload={() => void loadHistory()} />

      <aside className="replica-analytics-followup" aria-label="后续处理范围">
        <div>
          <h2>需要形成文档总结？</h2>
          <p>复用现有文档检索或问答入口继续整理，不在本页重复建设文档分析流程。</p>
        </div>
        <nav aria-label="分析后续入口">
          <Link href="/documents">前往文档</Link>
          <Link href="/chat">前往问答</Link>
        </nav>
        <p>本批不含 OCR</p>
      </aside>
    </main>
  );
}

function AnalysisResult({ response }: { readonly response: TableAnalysisUploadResponse }) {
  return (
    <section
      className="replica-analytics-result"
      aria-label="本次分析结果"
    >
      <div className="replica-analytics-section-heading">
        <div>
          <p className="replica-kicker">后端返回</p>
          <h2>本次分析结果</h2>
        </div>
        <span className={`replica-analytics-retention is-${response.retention_status}`}>
          {response.retention_status}
        </span>
      </div>

      <dl className="replica-analytics-definitions replica-analytics-file-metrics">
        <Definition term="文件名" value={response.name} />
        <Definition term="文件大小" value={`${response.size_kb} KB`} />
        <Definition term="扩展名" value={response.extension} />
        <Definition term="解析状态" value={response.status} />
        <Definition term="工作表" value={response.sheet_name ?? "不适用"} />
        <Definition term="数据行" value={String(response.row_count)} />
        <Definition term="空单元格" value={String(response.empty_cell_count)} />
        <Definition term="重复行" value={String(response.duplicate_row_count)} />
      </dl>

      <p className="replica-analytics-message">{response.message}</p>

      <div className="replica-analytics-table-wrap">
        <table>
          <caption>字段画像</caption>
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
        <ResultList title="审计信号" items={response.audit_signals} />
        <ResultList title="后续建议" items={response.recommendations} />
      </div>

      <p className="replica-analytics-retention-note">
        {response.retention_status === "retained"
          ? "已保留分析文件和结果记录。"
          : "未配置 analytics store，本次分析未保留。"}
      </p>
      <dl className="replica-analytics-definitions replica-analytics-evidence">
        <Definition term="upload_id" value={response.upload_id ?? "未生成"} />
        <Definition term="sha256" value={response.sha256 ?? "未生成"} />
        <Definition term="retention_status" value={response.retention_status} />
        <Definition term="created_at" value={response.created_at ?? "未记录"} />
      </dl>
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
        <p>后端未返回该类结果</p>
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
    <section className="replica-analytics-history" aria-label="分析历史">
      <div className="replica-analytics-section-heading">
        <div>
          <p className="replica-kicker">真实记录</p>
          <h2>分析历史</h2>
        </div>
        <button type="button" className="replica-secondary-button" onClick={onReload}>
          刷新历史
        </button>
      </div>

      {state.phase === "loading" ? (
        <p className="replica-analytics-status" role="status" aria-live="polite">
          正在读取分析历史…
        </p>
      ) : null}
      {state.phase === "error" ? (
        <div className="replica-analytics-error" role="alert">
          <p>分析历史读取失败</p>
          <button type="button" className="replica-secondary-button" onClick={onReload}>
            重试读取历史
          </button>
        </div>
      ) : null}
      {state.phase === "empty" ? <p className="replica-analytics-empty">当前没有保留的分析记录</p> : null}
      {state.phase === "degraded" ? (
        <p className="replica-analytics-degraded" role="status">历史存储未就绪</p>
      ) : null}

      {response ? (
        <>
          <dl className="replica-analytics-definitions replica-analytics-store">
            <Definition term="store ready" value={String(response.store.ready)} />
            <Definition term="store backend" value={response.store.backend} />
          </dl>
          {response.items.length > 0 ? (
            <div className="replica-analytics-history-list">
              {response.items.map((item) => (
                <article key={item.id} aria-label={item.name}>
                  <div>
                    <h3>{item.name}</h3>
                    <p>{item.extension} · {item.size_kb} KB · {item.sheet_name ?? "无工作表"}</p>
                  </div>
                  <dl className="replica-analytics-definitions">
                    <Definition term="记录 ID" value={item.id} />
                    <Definition term="原始字节" value={String(item.size_bytes)} />
                    <Definition term="文件大小" value={`${item.size_kb} KB`} />
                    <Definition term="数据行" value={String(item.row_count)} />
                    <Definition term="字段数" value={String(item.column_count)} />
                    <Definition term="空单元格" value={String(item.empty_cell_count)} />
                    <Definition term="重复行" value={String(item.duplicate_row_count)} />
                    <Definition term="分析状态" value={item.status} />
                    <Definition term="保留状态" value={item.retention_status} />
                    <Definition term="created_at" value={item.created_at} />
                    <Definition term="sha256（截断）" value={truncatedSha256(item.sha256)} />
                  </dl>
                  {item.audit_signals.length > 0 ? (
                    <p>审计信号：{item.audit_signals.join("、")}</p>
                  ) : (
                    <p>审计信号：无</p>
                  )}
                </article>
              ))}
            </div>
          ) : state.phase === "degraded" ? (
            <p className="replica-analytics-empty">存储未就绪，未返回历史记录</p>
          ) : null}
        </>
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
