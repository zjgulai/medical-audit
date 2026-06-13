"use client";

import { ChangeEvent, useState } from "react";

import { StatusPill } from "@/components/ui/status-pill";

type UploadProfile = {
  readonly name: string;
  readonly sizeKb: number;
  readonly extension: string;
  readonly status: "parsed" | "queued" | "error";
  readonly columns: readonly ColumnProfile[];
  readonly rowCount: number;
  readonly emptyCellCount: number;
  readonly duplicateRowCount: number;
  readonly message: string;
  readonly qualityFindings: readonly string[];
  readonly auditSignals: readonly string[];
  readonly recommendations: readonly string[];
};

type ColumnProfile = {
  readonly name: string;
  readonly type: "数值" | "日期" | "标识" | "文本" | "空列";
  readonly emptyCount: number;
  readonly uniqueCount: number;
  readonly sampleValues: readonly string[];
  readonly auditHint: string;
};

function parseCsvRows(text: string) {
  const rows: string[][] = [];
  let field = "";
  let row: string[] = [];
  let inQuotes = false;
  const normalizedText = text.replace(/^\uFEFF/, "");

  for (let index = 0; index < normalizedText.length; index += 1) {
    const char = normalizedText[index];
    const nextChar = normalizedText[index + 1];

    if (char === '"' && inQuotes && nextChar === '"') {
      field += '"';
      index += 1;
      continue;
    }

    if (char === '"') {
      inQuotes = !inQuotes;
      continue;
    }

    if (char === "," && !inQuotes) {
      row.push(field);
      field = "";
      continue;
    }

    if ((char === "\n" || char === "\r") && !inQuotes) {
      if (char === "\r" && nextChar === "\n") {
        index += 1;
      }
      row.push(field);
      rows.push(row);
      field = "";
      row = [];
      continue;
    }

    field += char;
  }

  row.push(field);
  rows.push(row);

  return rows
    .map((cells) => cells.map((cell) => cell.trim()))
    .filter((cells) => cells.some((cell) => cell !== ""));
}

function normalizeRow(row: readonly string[], columnCount: number) {
  return Array.from({ length: columnCount }, (_, index) => row[index]?.trim() ?? "");
}

function inferColumnType(name: string, values: readonly string[]): ColumnProfile["type"] {
  const nonEmptyValues = values.filter(Boolean);
  const normalizedName = name.toLowerCase();

  if (nonEmptyValues.length === 0) {
    return "空列";
  }

  if (/id|编号|编码|身份证|患者|就诊|病历|patient|visit|code/.test(normalizedName)) {
    return "标识";
  }

  const numericCount = nonEmptyValues.filter((value) => /^-?\d+(\.\d+)?$/.test(value.replace(/,/g, ""))).length;
  if (numericCount / nonEmptyValues.length >= 0.8) {
    return "数值";
  }

  const dateCount = nonEmptyValues.filter((value) => !Number.isNaN(Date.parse(value.replace(/\./g, "-")))).length;
  if (dateCount / nonEmptyValues.length >= 0.8) {
    return "日期";
  }

  return "文本";
}

function inferAuditHint(name: string) {
  if (/金额|费用|price|amount|cost|fee|charge|total/i.test(name)) {
    return "金额字段，可用于收费合规和异常金额核验";
  }
  if (/患者|病人|patient|姓名|身份证|就诊|visit/i.test(name)) {
    return "对象字段，可用于同人同次就诊聚合";
  }
  if (/日期|时间|date|time|结算|发生/i.test(name)) {
    return "时间字段，可用于限定审计期间和同日重复核验";
  }
  if (/项目|药品|目录|item|drug|catalog|编码|code/i.test(name)) {
    return "项目字段，可用于目录限制和重复收费核验";
  }
  if (/科室|department|dept/i.test(name)) {
    return "组织字段，可用于科室维度分布分析";
  }
  if (/医保|结算|支付|报销|insurance|fund/i.test(name)) {
    return "医保字段，可用于支付范围和报销口径核验";
  }
  if (/数量|qty|quantity|num/i.test(name)) {
    return "数量字段，可用于数量异常和金额复算";
  }
  return "通用字段";
}

function buildAuditSignals(columnNames: readonly string[]) {
  const signalRules = [
    { label: "金额/费用字段", pattern: /金额|费用|price|amount|cost|fee|charge|total/i },
    { label: "患者/就诊字段", pattern: /患者|病人|patient|姓名|身份证|就诊|visit/i },
    { label: "日期/时间字段", pattern: /日期|时间|date|time|结算|发生/i },
    { label: "项目/药品/目录字段", pattern: /项目|药品|目录|item|drug|catalog|编码|code/i },
    { label: "医保支付字段", pattern: /医保|结算|支付|报销|insurance|fund/i },
    { label: "数量字段", pattern: /数量|qty|quantity|num/i }
  ] as const;

  return signalRules.filter((rule) => columnNames.some((name) => rule.pattern.test(name))).map((rule) => rule.label);
}

function parseCsv(text: string) {
  const parsedRows = parseCsvRows(text);
  const rawColumns = parsedRows[0] ?? [];
  const columns = rawColumns.map((cell, index) => cell || `field_${index + 1}`);
  const normalizedRows = parsedRows.slice(1).map((row) => normalizeRow(row, columns.length));
  const duplicateRowCount = normalizedRows.length - new Set(normalizedRows.map((row) => JSON.stringify(row))).size;

  const columnProfiles = columns.map((column, index): ColumnProfile => {
    const values = normalizedRows.map((row) => row[index] ?? "");
    const nonEmptyValues = values.filter(Boolean);

    return {
      name: column,
      type: inferColumnType(column, values),
      emptyCount: values.length - nonEmptyValues.length,
      uniqueCount: new Set(nonEmptyValues).size,
      sampleValues: Array.from(new Set(nonEmptyValues)).slice(0, 3),
      auditHint: inferAuditHint(column)
    };
  });

  const emptyCellCount = normalizedRows.reduce((count, row) => {
    return count + row.filter((cell) => cell.trim() === "").length;
  }, 0);
  const highEmptyColumns = columnProfiles.filter((column) => normalizedRows.length > 0 && column.emptyCount / normalizedRows.length >= 0.3);
  const duplicateColumnNames = columns.filter((column, index) => columns.indexOf(column) !== index);
  const auditSignals = buildAuditSignals(columns);
  const duplicateChargeSignals = ["金额/费用字段", "患者/就诊字段", "日期/时间字段", "项目/药品/目录字段"] as const;
  const hasDuplicateChargeBase = duplicateChargeSignals.every((signal) =>
    auditSignals.includes(signal)
  );
  const qualityFindings = [
    normalizedRows.length > 0 ? `识别到 ${normalizedRows.length} 行数据和 ${columns.length} 个字段。` : "仅识别到表头，未发现可分析数据行。",
    emptyCellCount > 0 ? `发现 ${emptyCellCount} 个空值单元，需要确认是否为业务允许缺失。` : "未发现空值单元。",
    duplicateRowCount > 0 ? `发现 ${duplicateRowCount} 条完全重复行。` : "未发现完全重复行。",
    duplicateColumnNames.length > 0 ? `存在重复字段名：${Array.from(new Set(duplicateColumnNames)).join("、")}。` : "字段名未发现重复。"
  ];
  const recommendations = [
    hasDuplicateChargeBase
      ? "重复收费核验字段基础完整，可按患者/就诊、项目、日期和金额形成初筛分组。"
      : "重复收费核验字段不完整，需补齐患者/就诊、项目、日期和金额字段后再进入正式审计判断。",
    auditSignals.includes("医保支付字段")
      ? "已识别医保支付字段，可进一步核对支付范围、报销口径和目录限制条件。"
      : "未识别医保支付字段，当前更适合做文件质量预检和通用异常线索整理。",
    highEmptyColumns.length > 0
      ? `优先核对高空值字段：${highEmptyColumns.map((column) => column.name).join("、")}。`
      : "字段完整度未触发高空值预警。"
  ];

  return {
    columns: columnProfiles,
    rowCount: normalizedRows.length,
    emptyCellCount,
    duplicateRowCount,
    qualityFindings,
    auditSignals,
    recommendations
  };
}

function buildQueuedProfile(name: string, sizeKb: number, extension: string): UploadProfile {
  return {
    name,
    sizeKb,
    extension,
    status: "queued",
    columns: [],
    rowCount: 0,
    emptyCellCount: 0,
    duplicateRowCount: 0,
    message: "已接收文件。当前前端先完成文件级预检，工作簿 sheet 解析需由后端分析服务接管。",
    qualityFindings: ["文件格式已通过上传入口校验。", "尚未读取 sheet 表头和数据行，不能生成字段级审计判断。"],
    auditSignals: ["待后端解析"],
    recommendations: ["确认工作簿中审计明细所在 sheet、表头行和字段字典，再进入正式分析。"]
  };
}

function readFileText(file: File) {
  if (typeof file.text === "function") {
    return file.text();
  }

  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? ""));
    reader.onerror = () => reject(reader.error ?? new Error("Failed to read file"));
    reader.readAsText(file);
  });
}

export function DataAnalysisWorkbench() {
  const [profile, setProfile] = useState<UploadProfile | null>(null);

  async function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) {
      setProfile(null);
      return;
    }

    const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
    const baseProfile = {
      name: file.name,
      sizeKb: Math.max(1, Math.round(file.size / 1024)),
      extension,
      columns: [],
      rowCount: 0,
      emptyCellCount: 0,
      duplicateRowCount: 0,
      qualityFindings: [],
      auditSignals: [],
      recommendations: []
    };

    if (extension === "csv") {
      try {
        const parsed = parseCsv(await readFileText(file));
        setProfile({
          ...baseProfile,
          ...parsed,
          status: "parsed",
          message: "已完成本地字段概览。"
        });
      } catch {
        setProfile({
          ...baseProfile,
          status: "error",
          message: "CSV 读取失败，请检查文件编码或重新上传。"
        });
      }
      return;
    }

    setProfile({
      ...baseProfile,
      ...buildQueuedProfile(file.name, Math.max(1, Math.round(file.size / 1024)), extension)
    });
  }

  return (
    <main className="audit-page-grid audit-page-grid--rail">
      <section className="audit-panel p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="audit-kicker">AI 数据分析</p>
            <h1 className="audit-page-title">上传表格分析</h1>
          </div>
          <StatusPill tone="warning">分析线索</StatusPill>
        </div>

        <label className="audit-focus-ring audit-upload-drop mt-6 p-6">
          <span className="audit-card-title block">选择 `.csv` 或 `.xlsx` 文件</span>
          <span className="audit-copy mt-2 block">
            CSV 会即时展示字段、行数和空值概览；XLSX 先进入上传接收状态。
          </span>
          <input
            aria-label="上传审计表格"
            className="mt-4 block w-full text-sm text-[var(--audit-ink-muted)]"
            accept=".csv,.xlsx"
            type="file"
            onChange={handleFileChange}
          />
        </label>

        <div className="mt-5 grid gap-4 lg:grid-cols-3">
          <div className="audit-panel-muted p-4">
            <p className="audit-label">HIS staging</p>
            <p className="audit-metric-value mt-2">可接入</p>
          </div>
          <div className="audit-panel-muted p-4">
            <p className="audit-label">规则疑点</p>
            <p className="audit-metric-value mt-2">1</p>
          </div>
          <div className="audit-panel-muted p-4">
            <p className="audit-label">待复核线索</p>
            <p className="audit-metric-value mt-2">开放</p>
          </div>
        </div>

        {profile && (
          <section aria-live="polite" className="audit-panel-muted mt-5 p-5">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <h2 className="audit-section-title">{profile.name}</h2>
                <p className="audit-meta mt-1">
                  {profile.extension.toUpperCase()} · {profile.sizeKb} KB
                </p>
              </div>
              <StatusPill tone={profile.status === "parsed" ? "success" : profile.status === "error" ? "danger" : "info"}>
                {profile.status === "parsed" ? "已分析" : profile.status === "error" ? "失败" : "已接收"}
              </StatusPill>
            </div>
            <p className="audit-copy mt-4">{profile.message}</p>
            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              <Metric label="字段数" value={String(profile.columns.length)} />
              <Metric label="数据行" value={String(profile.rowCount)} />
              <Metric label="重复行" value={String(profile.duplicateRowCount)} />
            </div>
            {profile.columns.length > 0 && (
              <div className="audit-table-shell mt-4 overflow-x-auto">
                <table className="audit-table min-w-[42rem]">
                  <thead>
                    <tr>
                      <th>字段</th>
                      <th>类型</th>
                      <th>空值</th>
                      <th>去重值</th>
                      <th>审计提示</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--audit-line-soft)]">
                    {profile.columns.map((column) => (
                      <tr key={column.name}>
                        <td className="font-semibold text-[var(--audit-ink)]">{column.name}</td>
                        <td className="text-[var(--audit-ink-muted)]">{column.type}</td>
                        <td className="text-[var(--audit-ink-muted)]">{column.emptyCount}</td>
                        <td className="text-[var(--audit-ink-muted)]">{column.uniqueCount}</td>
                        <td className="text-[var(--audit-ink-muted)]">{column.auditHint}</td>
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
            <div className="mt-5 grid gap-4 lg:grid-cols-2">
              <AnalysisList title="数据质量提示" items={profile.qualityFindings} />
              <AnalysisList title="审计初步分析" items={profile.recommendations} />
            </div>
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
            {profile.columns.length > 0 && (
              <div className="mt-4 flex flex-wrap gap-2">
                {profile.columns.map((column) => (
                  <span key={column.name} className="audit-chip">
                    {column.name}
                  </span>
                ))}
              </div>
            )}
          </section>
        )}
      </section>

      <aside className="space-y-4">
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
