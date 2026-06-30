"use client";

import { ChangeEvent, useCallback, useEffect, useState } from "react";

import { StatusPill } from "@/components/ui/status-pill";
import { fetchAnalysisUploadHistory, uploadAnalysisTable } from "@/lib/api-client";
import type {
  TableAnalysisColumnType,
  TableAnalysisUploadHistoryItem,
  TableAnalysisUploadResponse
} from "@/lib/api-types";
import { auditTableTemplates, type AuditTableTemplate } from "@/lib/portal-data";

type UploadProfile = {
  readonly name: string;
  readonly sizeKb: number;
  readonly extension: string;
  readonly status: "parsed" | "error";
  readonly sheetName: string | null;
  readonly columns: readonly ColumnProfile[];
  readonly rowCount: number;
  readonly emptyCellCount: number;
  readonly duplicateRowCount: number;
  readonly message: string;
  readonly qualityFindings: readonly string[];
  readonly auditSignals: readonly string[];
  readonly recommendations: readonly string[];
  readonly uploadId: string | null;
  readonly sha256: string | null;
  readonly retentionStatus: "retained" | "not-configured";
  readonly createdAt: string | null;
};

type ColumnProfile = {
  readonly name: string;
  readonly type: TableAnalysisColumnType;
  readonly emptyCount: number;
  readonly uniqueCount: number;
  readonly sampleValues: readonly string[];
  readonly auditHint: string;
};

type AnalysisTab = "code" | "terminal" | "chart" | "data" | "report";
type HistoryStatus = "loading" | "ready" | "unavailable";

const analysisTabs: readonly { readonly id: AnalysisTab; readonly label: string }[] = [
  { id: "code", label: "代码" },
  { id: "terminal", label: "终端" },
  { id: "chart", label: "图表" },
  { id: "data", label: "数据" },
  { id: "report", label: "分析报告" }
];

function fileExtension(fileName: string) {
  return fileName.split(".").pop()?.toLowerCase() ?? "";
}

function mapUploadProfile(response: TableAnalysisUploadResponse): UploadProfile {
  return {
    name: response.name,
    sizeKb: response.size_kb,
    extension: response.extension,
    status: response.status,
    sheetName: response.sheet_name,
    columns: response.columns.map((column) => ({
      name: column.name,
      type: column.type,
      emptyCount: column.empty_count,
      uniqueCount: column.unique_count,
      sampleValues: column.sample_values,
      auditHint: column.audit_hint
    })),
    rowCount: response.row_count,
    emptyCellCount: response.empty_cell_count,
    duplicateRowCount: response.duplicate_row_count,
    message: response.message,
    qualityFindings: response.quality_findings,
    auditSignals: response.audit_signals,
    recommendations: response.recommendations,
    uploadId: response.upload_id,
    sha256: response.sha256,
    retentionStatus: response.retention_status,
    createdAt: response.created_at
  };
}

function buildErrorProfile(file: File, message: string): UploadProfile {
  return {
    name: file.name,
    sizeKb: Math.max(1, Math.round(file.size / 1024)),
    extension: fileExtension(file.name),
    status: "error",
    sheetName: null,
    columns: [],
    rowCount: 0,
    emptyCellCount: 0,
    duplicateRowCount: 0,
    message,
    qualityFindings: ["后端未返回字段画像，当前文件不能进入审计判断。"],
    auditSignals: [],
    recommendations: ["检查文件格式、大小和后端分析服务状态后重新上传。"],
    uploadId: null,
    sha256: null,
    retentionStatus: "not-configured",
    createdAt: null
  };
}

export function DataAnalysisWorkbench() {
  const [selectedTemplateId, setSelectedTemplateId] = useState<AuditTableTemplate["id"]>(auditTableTemplates[0]?.id ?? "");
  const selectedTemplate = auditTableTemplates.find((template) => template.id === selectedTemplateId) ?? auditTableTemplates[0];
  const [analysisRequirement, setAnalysisRequirement] = useState(selectedTemplate?.analysisRequest ?? "");
  const [profile, setProfile] = useState<UploadProfile | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [activeTab, setActiveTab] = useState<AnalysisTab>("data");
  const [history, setHistory] = useState<readonly TableAnalysisUploadHistoryItem[]>([]);
  const [historyStatus, setHistoryStatus] = useState<HistoryStatus>("loading");

  const refreshHistory = useCallback(async () => {
    setHistoryStatus("loading");
    try {
      const result = await fetchAnalysisUploadHistory();
      setHistory(result.items);
      setHistoryStatus(result.store.ready ? "ready" : "unavailable");
    } catch {
      setHistory([]);
      setHistoryStatus("unavailable");
    }
  }, []);

  useEffect(() => {
    void refreshHistory();
  }, [refreshHistory]);

  function selectTemplate(template: AuditTableTemplate) {
    setSelectedTemplateId(template.id);
    setAnalysisRequirement(template.analysisRequest);
  }

  async function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) {
      setProfile(null);
      return;
    }

    setIsUploading(true);
    setProfile(null);
    try {
      const result = await uploadAnalysisTable(file);
      setProfile(mapUploadProfile(result));
      await refreshHistory();
    } catch {
      setProfile(buildErrorProfile(file, "后端表格分析失败，请检查文件格式或稍后重试。"));
    } finally {
      setIsUploading(false);
    }
  }

  function renderTabContent() {
    if (isUploading) {
      return (
        <div className="audit-panel-muted p-6 text-center">
          <h2 className="audit-section-title">正在上传并分析数据文件</h2>
          <p className="audit-copy mx-auto mt-2 max-w-xl">
            后端正在读取工作簿、生成字段画像、质量提示和审计初步分析。
          </p>
        </div>
      );
    }

    if (!profile) {
      return (
        <div className="audit-panel-muted p-6 text-center">
          <h2 className="audit-section-title">等待上传{selectedTemplate?.shortName ?? "审计"}数据文件</h2>
          <p className="audit-copy mx-auto mt-2 max-w-xl">
            选择 CSV 或 XLSX 文件后，后端会生成字段画像、质量提示和审计初步分析。
          </p>
          {selectedTemplate && (
            <div className="mt-5 grid gap-4 text-left lg:grid-cols-2">
              <AnalysisList title="模板字段" items={selectedTemplate.expectedColumns.slice(0, 12)} />
              <AnalysisList title="核验重点" items={selectedTemplate.keyChecks} />
            </div>
          )}
        </div>
      );
    }

    if (activeTab === "code") {
      return (
        <section className="audit-panel-muted p-5">
          <h2 className="audit-section-title">{profile.name}</h2>
          <p className="audit-copy mt-2">首期展示可复核的分析步骤，不自动执行生产级代码。</p>
          <pre className="mt-4 overflow-x-auto rounded-[var(--audit-radius-md)] bg-[#101828] p-4 text-xs leading-6 text-white">
{`load_file("${profile.name}")
profile_columns()
check_empty_cells()
detect_duplicate_rows()
map_audit_signals()`}</pre>
        </section>
      );
    }

    if (activeTab === "terminal") {
      return (
        <section className="audit-panel-muted p-5">
          <h2 className="audit-section-title">{profile.name}</h2>
          <div className="mt-4 space-y-2 font-mono text-xs text-[var(--audit-ink-muted)]">
            <p>[ok] 文件入口校验通过</p>
            <p>[ok] 字段数: {profile.columns.length}</p>
            <p>[ok] 数据行: {profile.rowCount}</p>
            <p>{profile.status === "parsed" ? "[ok] 后端表格解析完成" : "[error] 后端表格解析失败"}</p>
            <p>{profile.retentionStatus === "retained" ? "[ok] 上传文件已留存" : "[warn] 上传文件未留存"}</p>
          </div>
        </section>
      );
    }

    if (activeTab === "chart") {
      const maxValue = Math.max(profile.rowCount, profile.emptyCellCount, profile.duplicateRowCount, 1);
      const chartRows = [
        { label: "数据行", value: profile.rowCount },
        { label: "空值单元", value: profile.emptyCellCount },
        { label: "重复行", value: profile.duplicateRowCount }
      ];

      return (
        <section className="audit-panel-muted p-5">
          <h2 className="audit-section-title">{profile.name}</h2>
          <div className="mt-5 space-y-4">
            {chartRows.map((row) => (
              <div key={row.label}>
                <div className="flex items-center justify-between gap-4 text-sm">
                  <span className="font-semibold text-[var(--audit-ink)]">{row.label}</span>
                  <span className="font-mono text-[var(--audit-ink-muted)]">{row.value}</span>
                </div>
                <div className="mt-2 h-2 overflow-hidden rounded-full bg-white">
                  <div
                    className="h-full rounded-full bg-[var(--audit-primary)]"
                    style={{ width: `${Math.max(6, Math.round((row.value / maxValue) * 100))}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </section>
      );
    }

    if (activeTab === "report") {
      return (
        <section className="audit-panel-muted p-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h2 className="audit-section-title">{profile.name}</h2>
            <p className="audit-copy mt-2">{profile.message}</p>
            {profile.sha256 && (
              <p className="audit-meta mt-2 break-all">sha256: {profile.sha256}</p>
            )}
          </div>
            <StatusPill tone={profile.status === "parsed" ? "success" : "danger"}>
              {profile.status === "parsed" ? "已生成" : "失败"}
            </StatusPill>
          </div>
          <div className="mt-5 grid gap-4 lg:grid-cols-2">
            <AnalysisList title="数据质量提示" items={profile.qualityFindings} />
            <AnalysisList title="审计初步分析" items={profile.recommendations} />
          </div>
        </section>
      );
    }

    return (
      <section aria-live="polite" className="audit-panel-muted p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="audit-section-title">{profile.name}</h2>
            <p className="audit-meta mt-1">
              {profile.extension.toUpperCase()} / {profile.sizeKb} KB
              {profile.sheetName ? ` / ${profile.sheetName}` : ""}
            </p>
          </div>
          <StatusPill tone={profile.status === "parsed" ? "success" : "danger"}>
            {profile.status === "parsed" ? "已分析" : "失败"}
          </StatusPill>
        </div>
        <p className="audit-copy mt-4">{profile.message}</p>
        <div className="mt-3 flex flex-wrap gap-2">
          <span className="audit-chip">
            留存：{profile.retentionStatus === "retained" ? "已留存" : "未配置"}
          </span>
          {profile.uploadId && <span className="audit-chip">记录：{profile.uploadId}</span>}
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          <Metric label="字段数" value={String(profile.columns.length)} />
          <Metric label="数据行" value={String(profile.rowCount)} />
          <Metric label="重复行" value={String(profile.duplicateRowCount)} />
        </div>
        {profile.columns.length > 0 && (
          <div className="audit-table-shell mt-4">
            <table className="audit-table table-fixed">
              <thead>
                <tr>
                  <th className="w-[23%]">字段</th>
                  <th className="w-[14%]">类型</th>
                  <th className="w-[13%]">空值</th>
                  <th className="w-[13%]">去重值</th>
                  <th className="w-[37%]">审计提示</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--audit-line-soft)]">
                {profile.columns.map((column) => (
                  <tr key={column.name}>
                    <td className="break-words font-semibold text-[var(--audit-ink)]">{column.name}</td>
                    <td className="break-words text-[var(--audit-ink-muted)]">{column.type}</td>
                    <td className="text-[var(--audit-ink-muted)]">{column.emptyCount}</td>
                    <td className="text-[var(--audit-ink-muted)]">{column.uniqueCount}</td>
                    <td className="break-words text-[var(--audit-ink-muted)]">{column.auditHint}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {profile.auditSignals.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-2">
            {profile.auditSignals.map((signal) => (
              <span key={signal} className="audit-chip audit-chip-info">
                {signal}
              </span>
            ))}
          </div>
        )}
        {profile.columns.some((column) => column.sampleValues.length > 0) && (
          <div className="mt-5">
            <h3 className="audit-compact-title">样例值</h3>
            <div className="mt-3 flex flex-wrap gap-2">
              {profile.columns.slice(0, 6).map((column) => (
                <span key={column.name} className="audit-chip">
                  {column.name}: {column.sampleValues.join(" / ") || "空"}
                </span>
              ))}
            </div>
          </div>
        )}
        <div className="mt-5 grid gap-4 lg:grid-cols-2">
          <AnalysisList title="数据质量提示" items={profile.qualityFindings} />
          <AnalysisList title="审计初步分析" items={profile.recommendations} />
        </div>
      </section>
    );
  }

  return (
    <main className="grid min-w-0 gap-4 xl:grid-cols-[18rem_minmax(0,1fr)_17rem]">
      <aside className="audit-panel-rail min-w-0 p-5">
        <h2 className="audit-section-title">数据分析助手</h2>
        <p className="audit-copy mt-2">按医保费用模板组织上传、预检、产物和报告。首期不执行生产级自动审计。</p>
        <section className="mt-5" aria-labelledby="table-template-title">
          <h3 id="table-template-title" className="audit-compact-title">常用表模板</h3>
          <div className="mt-3 space-y-2">
            {auditTableTemplates.map((template) => {
              const isSelected = selectedTemplateId === template.id;
              return (
                <button
                  key={template.id}
                  className={`audit-focus-ring w-full rounded-[var(--audit-radius-md)] border p-3 text-left transition ${
                    isSelected
                      ? "border-[var(--audit-primary-line)] bg-[var(--audit-primary-soft)]"
                      : "border-[var(--audit-line)] bg-white hover:bg-[var(--audit-surface-muted)]"
                  }`}
                  type="button"
                  aria-pressed={isSelected}
                  onClick={() => selectTemplate(template)}
                >
                  <span className="flex items-center justify-between gap-2">
                    <span className="text-sm font-semibold text-[var(--audit-ink)]">{template.shortName} · {template.name}</span>
                    <span className="audit-meta">{template.sheetName}</span>
                  </span>
                  <span className="mt-2 block audit-meta">{template.auditUse}</span>
                </button>
              );
            })}
          </div>
        </section>
        <div className="mt-5 space-y-3">
          {[
            ["da_list_files", isUploading ? "处理中" : profile ? "完成" : "等待"],
            [
              "da_preview_data",
              isUploading ? "处理中" : profile?.status === "parsed" ? "完成" : profile ? "失败" : "等待"
            ],
            [
              "da_profile_columns",
              isUploading ? "处理中" : profile?.columns.length ? "完成" : profile ? "失败" : "等待"
            ],
            ["da_write_report", isUploading ? "处理中" : profile?.status === "parsed" ? "草稿" : profile ? "失败" : "等待"]
          ].map(([tool, status]) => (
            <div key={tool} className="rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-white p-3">
              <p className="font-mono text-xs font-semibold text-[var(--audit-primary)]">{tool}</p>
              <p className="audit-meta mt-1">状态：{status}</p>
            </div>
          ))}
        </div>
        <label className="mt-5 block">
          <span className="audit-label">分析要求</span>
          <textarea
            className="audit-focus-ring audit-input mt-2 min-h-28 resize-y px-3 py-2"
            value={analysisRequirement}
            onChange={(event) => setAnalysisRequirement(event.target.value)}
          />
        </label>
      </aside>

      <section className="audit-panel min-w-0 p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="audit-kicker">AI 数据分析</p>
            <h1 className="audit-page-title">上传表格分析工作台</h1>
            <p className="audit-copy mt-2 max-w-3xl">
              左侧选择医保费用模板，中间展示代码、终端、图表、数据和报告，右侧管理上传文件。
            </p>
          </div>
          <StatusPill tone={isUploading ? "info" : profile?.status === "parsed" ? "success" : profile?.status === "error" ? "danger" : "warning"}>
            {isUploading ? "分析中" : profile?.status === "parsed" ? "已分析" : profile?.status === "error" ? "失败" : "分析线索"}
          </StatusPill>
        </div>

        <div className="mt-6 flex flex-wrap gap-2 border-b border-[var(--audit-line)] pb-3" role="tablist" aria-label="分析产物">
          {analysisTabs.map((tab) => (
            <button
              key={tab.id}
              className={`audit-focus-ring rounded-[var(--audit-radius-md)] px-3 py-2 text-sm font-semibold ${
                activeTab === tab.id
                  ? "bg-[var(--audit-primary)] text-white"
                  : "bg-[var(--audit-surface-muted)] text-[var(--audit-ink-muted)] hover:text-[var(--audit-ink)]"
              }`}
              type="button"
              role="tab"
              aria-selected={activeTab === tab.id}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {selectedTemplate && (
          <section className="mt-5 rounded-[var(--audit-radius-md)] border border-[var(--audit-primary-line)] bg-[var(--audit-primary-soft)] p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-[var(--audit-primary)]">当前模板：{selectedTemplate.shortName}</p>
                <h2 className="audit-card-title mt-1">{selectedTemplate.name}</h2>
                <p className="audit-meta mt-1">{selectedTemplate.fileName} / {selectedTemplate.sheetName}</p>
              </div>
              <StatusPill tone="info">模板引导</StatusPill>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {selectedTemplate.expectedColumns.slice(0, 10).map((column) => (
                <span key={column} className="audit-chip bg-white">
                  {column}
                </span>
              ))}
            </div>
          </section>
        )}

        <div className="mt-5">{renderTabContent()}</div>
      </section>

      <aside className="min-w-0 space-y-4">
        <label className="audit-focus-ring audit-upload-drop p-5">
          <span className="audit-card-title block">上传{selectedTemplate?.shortName ?? ""}填报文件</span>
          <span className="audit-copy mt-2 block">
            支持 `.csv`、`.xlsx`、`.xlsm`；表格会交由后端解析，生成字段、行数、空值、重复行和审计线索概览。
          </span>
          <input
            aria-label="上传审计表格"
            className="mt-4 block w-full text-sm text-[var(--audit-ink-muted)]"
            accept=".csv,.xlsx,.xlsm"
            type="file"
            onChange={handleFileChange}
          />
        </label>

        <section className="audit-panel-rail p-5">
          <h2 className="audit-section-title">数据文件</h2>
          <div className="mt-4 space-y-2">
            <FileRow
              name={profile?.name ?? "尚未上传文件"}
              status={isUploading ? "分析中" : profile?.status === "parsed" ? "已分析" : profile ? "失败" : "等待上传"}
            />
            <FileRow name="HIS staging 明细" status="审计数据入口" />
          </div>
        </section>
        <section className="audit-panel-rail p-5">
          <div className="flex items-start justify-between gap-3">
            <h2 className="audit-section-title">上传历史</h2>
            <StatusPill tone={historyStatus === "ready" ? "success" : historyStatus === "loading" ? "info" : "warning"}>
              {historyStatus === "ready" ? "已连接" : historyStatus === "loading" ? "读取中" : "不可用"}
            </StatusPill>
          </div>
          <div className="mt-4 space-y-2">
            {history.length > 0 ? (
              history.slice(0, 4).map((item) => <HistoryRow key={item.id} item={item} />)
            ) : (
              <p className="audit-copy">暂无上传记录。</p>
            )}
          </div>
        </section>
        <a className="audit-focus-ring audit-action-card p-5" href="/findings">
          <p className="audit-kicker">审计数据分析入口</p>
          <h2 className="audit-section-title mt-2">查看规则命中疑点</h2>
          <p className="audit-copy mt-2">进入已上线的疑点清单、源记录定位和计算过程。</p>
        </a>
        <a className="audit-focus-ring audit-action-card p-5" href="/pages/index-admin">
          <p className="audit-kicker">索引与数据状态</p>
          <h2 className="audit-section-title mt-2">查看知识库运行态</h2>
          <p className="audit-copy mt-2">运维发布、回滚和验收仍保留在索引管理后台。</p>
        </a>
      </aside>
    </main>
  );
}

function HistoryRow({ item }: { readonly item: TableAnalysisUploadHistoryItem }) {
  return (
    <div className="rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-[var(--audit-surface-muted)] px-3 py-2">
      <p className="truncate text-sm font-semibold text-[var(--audit-ink)]">{item.name}</p>
      <p className="audit-meta mt-1">
        {item.extension.toUpperCase()} / {item.row_count} 行 / {formatDateTime(item.created_at)}
      </p>
      <p className="audit-meta mt-1 break-all">sha256: {shortSha(item.sha256)}</p>
    </div>
  );
}

function FileRow({ name, status }: { readonly name: string; readonly status: string }) {
  return (
    <div className="rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-[var(--audit-surface-muted)] px-3 py-2">
      <p className="truncate text-sm font-semibold text-[var(--audit-ink)]">{name}</p>
      <p className="audit-meta mt-1">{status}</p>
    </div>
  );
}

function Metric({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <div className="rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-white p-3">
      <p className="audit-meta font-semibold">{label}</p>
      <p className="audit-metric-value-sm mt-1">{value}</p>
    </div>
  );
}

function AnalysisList({ title, items }: { readonly title: string; readonly items: readonly string[] }) {
  return (
    <section className="rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-white p-4">
      <h3 className="audit-compact-title">{title}</h3>
      <ul className="audit-copy mt-3 space-y-2">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </section>
  );
}

function shortSha(value: string): string {
  return value.length > 16 ? `${value.slice(0, 12)}...${value.slice(-6)}` : value;
}

function formatDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
}
