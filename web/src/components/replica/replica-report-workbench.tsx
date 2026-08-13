"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";

import { useAuditUser } from "@/components/shell/audit-user-context";
import {
  createReportDraft,
  downloadAuditArtifact,
  fetchProjects,
  fetchReportWorkbench,
  isBackendRequestError,
  signReportDraft
} from "@/lib/api-client";
import type {
  ProjectsResponse,
  ReportDraftCreateResponse,
  ReportTemplateCategory,
  ReportWorkbenchEntry,
  ReportWorkbenchEvidenceSource,
  ReportWorkbenchResponse,
  WorkpaperTemplateRegistryItem
} from "@/lib/api-types";
import type { AuditClientRole } from "@/lib/audit-user";

type LanePhase = "loading" | "ready" | "degraded" | "error";

const lanePhaseLabels: Readonly<Record<LanePhase, string>> = {
  loading: "读取中",
  ready: "已连接",
  degraded: "有限可用",
  error: "读取异常"
};

type LaneState<T> = {
  readonly phase: LanePhase;
  readonly response: T | null;
  readonly role: AuditClientRole | null;
};

type CategoryCatalogProps = {
  readonly categories: readonly ReportTemplateCategory[];
  readonly templates: readonly WorkpaperTemplateRegistryItem[];
  readonly canSelect: boolean;
  readonly selectionHint: string;
  readonly selectedTemplateId: string | null;
  readonly onSelectTemplate: (templateId: string) => void;
};

type DraftPanelProps = {
  readonly template: WorkpaperTemplateRegistryItem;
  readonly projectKey: string;
  readonly canCreate: boolean;
  readonly fieldValues: Readonly<Record<string, string>>;
  readonly saving: boolean;
  readonly error: string | null;
  readonly result: ReportDraftCreateResponse | null;
  readonly onFieldChange: (field: string, value: string) => void;
  readonly onSubmit: (event: FormEvent<HTMLFormElement>) => void;
};

type AuthenticatedDownloadButtonProps = {
  readonly href: string;
  readonly label: string;
  readonly disabled: boolean;
  readonly pending: boolean;
  readonly onDownload: (href: string) => Promise<void>;
};

function loadingLane<T>(role: AuditClientRole | null): LaneState<T> {
  return { phase: "loading", response: null, role };
}

function isActiveTemplate(
  template: WorkpaperTemplateRegistryItem,
  categories: readonly ReportTemplateCategory[]
): boolean {
  return categories.some(
    (category) => category.id === template.category_id && category.availability === "active"
  );
}

function CategoryCatalog({
  categories,
  templates,
  canSelect,
  selectionHint,
  selectedTemplateId,
  onSelectTemplate
}: CategoryCatalogProps) {
  const activeTemplates = templates.filter((template) => isActiveTemplate(template, categories));
  const awaitingCategories = categories.filter(
    (category) => category.availability !== "active"
  );
  return (
    <section className="replica-report-catalog-section" aria-label="报表分类目录">
      <div className="replica-report-section-heading">
        <div>
          <p>第 2 步</p>
          <h2>选择报告或底稿</h2>
        </div>
        <span>{selectionHint}</span>
      </div>
      <div className="replica-report-deliverable-grid">
        {activeTemplates.length > 0 ? activeTemplates.map((template) => {
          const category = categories.find((item) => item.id === template.category_id);
          return (
            <article
              className={selectedTemplateId === template.id ? "is-selected" : ""}
              key={template.id}
            >
              <div>
                <span>{category?.label ?? "审计交付物"}</span>
                <h3>{template.name}</h3>
                <p>{template.output_type} · 支持人工复核后下载</p>
              </div>
              <button
                aria-label={`填写模板：${template.name}`}
                aria-pressed={selectedTemplateId === template.id}
                disabled={!canSelect}
                type="button"
                onClick={() => onSelectTemplate(template.id)}
              >
                {selectedTemplateId === template.id ? "已选择" : "选择"}
              </button>
            </article>
          );
        }) : <p className="replica-report-empty-inline">当前没有可用的报告或底稿</p>}
      </div>
      {awaitingCategories.length > 0 ? (
        <details className="replica-report-admin-details">
          <summary>查看暂未启用的模板分类</summary>
          <p>{awaitingCategories.map((category) => category.label).join("、")}</p>
        </details>
      ) : null}
    </section>
  );
}

function DraftPanel({
  template,
  projectKey,
  canCreate,
  fieldValues,
  saving,
  error,
  result,
  onFieldChange,
  onSubmit
}: DraftPanelProps) {
  const nonEmptyFieldCount = template.evidence_bindings.reduce(
    (count, field) => count + ((fieldValues[field] ?? "").trim() ? 1 : 0),
    0
  );
  const boundaryAnomaly = result !== null && (
    result.formal_report_created !== false || result.provider_call !== false
  );
  return (
    <section className="replica-report-draft-panel" aria-labelledby="report-draft-title">
      <div className="replica-report-section-heading">
        <div>
          <p>第 3 步 · 汇入分析结论</p>
          <h2 id="report-draft-title">创建草稿：{template.name}</h2>
        </div>
        <span>{nonEmptyFieldCount} 项已填写</span>
      </div>
      <p className="replica-report-draft-note">
        将已有的大模型分析结果粘贴到对应内容区，补充关键证据并人工修订后保存草稿。
        空白项不会写入。
      </p>
      <form aria-label={`${template.name}草稿`} onSubmit={onSubmit}>
        {template.evidence_bindings.map((field, index) => {
          const value = fieldValues[field] ?? "";
          const countId = `replica-report-field-${index}-count`;
          return (
            <label key={field}>
              <span>{index === 0 ? "大模型分析结果" : field}</span>
              {index === 0 ? <em>将写入：{field}</em> : null}
              <textarea
                aria-describedby={countId}
                aria-label={field}
                disabled={saving}
                maxLength={4000}
                name={field}
                placeholder={index === 0 ? "粘贴大模型分析结论，并保留关键依据和不确定项" : `补充${field}`}
                rows={3}
                value={value}
                onChange={(event) => onFieldChange(field, event.target.value)}
              />
              <small id={countId}>{value.length} / 4000</small>
            </label>
          );
        })}
        <div className="replica-report-form-actions">
          <button
            disabled={!canCreate || !projectKey || nonEmptyFieldCount === 0 || saving}
            type="submit"
          >
            {saving ? "正在保存草稿…" : "保存并进入人工复核"}
          </button>
          <span>{projectKey ? "草稿将归入已选项目" : "请先选择所属项目"}</span>
        </div>
      </form>
      {error ? <p className="replica-report-error" role="alert">{error}</p> : null}
      {result ? (
        <div className="replica-report-handoff" aria-live="polite">
          <div>
            <span>{boundaryAnomaly ? "草稿响应边界异常" : "草稿已进入待复核队列"}</span>
            <strong>{boundaryAnomaly ? "请停止后续操作" : "等待人工确认后再作为正式结论"}</strong>
          </div>
          <details className="replica-report-admin-details">
            <summary>管理与审计详情</summary>
            <ul>
              <li>任务编号：{result.task_id}</li>
              <li>
                {result.formal_report_created === false ? "未生成正式报告" : "正式报告状态异常"}
              </li>
              <li>
                {result.provider_call === false ? "未调用外部服务" : "检测到外部服务调用"}
              </li>
              <li>
                审计记录：{result.audit.durability}
                {result.audit.status === "degraded" ? "（降级）" : ""}
                {result.audit.status === "local-only" ? "（本地）" : ""}
              </li>
              <li><code>formal_report_created={String(result.formal_report_created)}</code></li>
              <li><code>provider_call={String(result.provider_call)}</code></li>
            </ul>
          </details>
          {boundaryAnomaly ? (
            <p className="replica-report-error" role="alert">
              草稿响应违反无副作用边界，请勿将其视为安全草稿。
            </p>
          ) : null}
          <Link href={result.project_href}>
            {boundaryAnomaly ? "前往项目核查异常" : "转入项目管理"}
          </Link>
        </div>
      ) : null}
    </section>
  );
}

function ReportMetrics({ metrics }: { readonly metrics: ReportWorkbenchResponse["metrics"] }) {
  const items = [
    ["报告总数", metrics.report_count],
    ["已签发报告", metrics.signed_report_count],
    ["待补充证据", metrics.blocked_report_count],
    ["已纳入审计疑点", metrics.included_finding_count]
  ] as const;
  return (
    <section className="replica-report-metrics" aria-label="报告指标">
      {items.map(([label, value]) => (
        <article key={label}>
          <span>{label}</span>
          <strong>{value}</strong>
        </article>
      ))}
    </section>
  );
}

function AuthenticatedDownloadButton({
  href,
  label,
  disabled,
  pending,
  onDownload
}: AuthenticatedDownloadButtonProps) {
  return (
    <button
      disabled={disabled}
      type="button"
      onClick={() => void onDownload(href)}
    >
      {pending ? `正在下载：${label}` : label}
    </button>
  );
}

function SignoffButton({
  entry,
  signoffState,
  onSignoff
}: {
  readonly entry: ReportWorkbenchEntry;
  readonly signoffState: { readonly status: string; readonly taskId?: string; readonly message?: string; readonly signedBy?: string };
  readonly onSignoff: (taskId: string, note: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [note, setNote] = useState("");
  const isSigning = signoffState.status === "signing" && signoffState.taskId === entry.id;
  const isSuccess = signoffState.status === "success" && signoffState.taskId === entry.id;
  const isError = signoffState.status === "error" && signoffState.taskId === entry.id;

  if (entry.signoff?.signed) {
    return (
      <span className="report-signoff-done">
        ✓ 已签发 · {entry.signoff.signed_by || "已签发"} · {entry.signoff.signed_at.slice(0, 10)}
      </span>
    );
  }

  if (
    !entry.signoff?.can_sign
    || !entry.signoff.gate_ready
    || !entry.signoff.writes_allowed
  ) return null;

  return (
    <span className="report-signoff-group">
      {expanded ? (
        <>
          <input
            className="report-signoff-note"
            disabled={isSigning}
            maxLength={500}
            placeholder="签发说明（可选）"
            type="text"
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
          <button
            className="replica-primary-button"
            disabled={isSigning}
            type="button"
            onClick={() => { onSignoff(entry.id, note); setExpanded(false); setNote(""); }}
          >
            {isSigning ? "签发中..." : "确认签发"}
          </button>
          <button
            className="replica-secondary-button"
            disabled={isSigning}
            type="button"
            onClick={() => { setExpanded(false); setNote(""); }}
          >
            取消
          </button>
        </>
      ) : (
        <button
          className="replica-primary-button"
          disabled={isSigning}
          type="button"
          onClick={() => setExpanded(true)}
        >
          {isSigning ? "签发中..." : "签发报告"}
        </button>
      )}
      {isSuccess ? <span className="report-signoff-success">✓ 签发成功</span> : null}
      {isError ? <span className="report-signoff-error">{signoffState.message}</span> : null}
    </span>
  );
}

function ReportLedger({
  entries,
  downloadingPath,
  signoffState,
  onDownload,
  onSignoff
}: {
  readonly entries: readonly ReportWorkbenchEntry[];
  readonly downloadingPath: string | null;
  readonly signoffState: { readonly status: string; readonly taskId?: string; readonly message?: string; readonly signedBy?: string };
  readonly onDownload: (href: string) => Promise<void>;
  readonly onSignoff: (taskId: string, note: string) => void;
}) {
  const downloadLocked = downloadingPath !== null;
  return (
    <section className="replica-report-ledger" aria-labelledby="report-ledger-title">
      <div className="replica-report-section-heading">
        <div>
          <p>最近交付物</p>
          <h2 id="report-ledger-title">报告与底稿</h2>
        </div>
        <span>{entries.length} 条</span>
      </div>
      {entries.length === 0 ? (
        <p className="replica-report-empty">暂无报告或底稿</p>
      ) : (
        <div className="replica-report-table-wrap">
          <table>
            <thead>
              <tr>
                <th>报告 / 底稿</th>
                <th>状态</th>
                <th>关键情况</th>
                <th>下载</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => (
                <tr key={entry.id}>
                  <td>
                    <strong>{entry.title}</strong>
                    <span>{entry.report_no} · 更新于 {entry.updated_at.slice(0, 10)}</span>
                  </td>
                  <td><span className={`replica-report-status status-${entry.status}`}>{entry.status}</span></td>
                  <td>
                    <strong>{entry.gate_summary}</strong>
                    <span>{entry.included_finding_count} 个疑点 · {entry.appendix_count} 个附件</span>
                  </td>
                  <td>
                    <nav aria-label={`${entry.title}操作`}>
                      <span>负责人：{entry.owner}</span>
                      <SignoffButton
                        entry={entry}
                        signoffState={signoffState}
                        onSignoff={onSignoff}
                      />
                      <AuthenticatedDownloadButton
                        disabled={downloadLocked}
                        href={entry.download_links.task_docx}
                        label="下载任务 DOCX"
                        pending={downloadingPath === entry.download_links.task_docx}
                        onDownload={onDownload}
                      />
                      {entry.download_links.report_docx ? (
                        <AuthenticatedDownloadButton
                          disabled={downloadLocked}
                          href={entry.download_links.report_docx}
                          label="下载报告 DOCX"
                          pending={downloadingPath === entry.download_links.report_docx}
                          onDownload={onDownload}
                        />
                      ) : null}
                      {entry.download_links.report_markdown ? (
                        <AuthenticatedDownloadButton
                          disabled={downloadLocked}
                          href={entry.download_links.report_markdown}
                          label="下载报告 Markdown"
                          pending={downloadingPath === entry.download_links.report_markdown}
                          onDownload={onDownload}
                        />
                      ) : null}
                      {entry.download_links.report_json ? (
                        <AuthenticatedDownloadButton
                          disabled={downloadLocked}
                          href={entry.download_links.report_json}
                          label="下载报告 JSON"
                          pending={downloadingPath === entry.download_links.report_json}
                          onDownload={onDownload}
                        />
                      ) : null}
                    </nav>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function EvidenceLedger({ sources }: { readonly sources: readonly ReportWorkbenchEvidenceSource[] }) {
  return (
    <details className="replica-report-evidence" aria-labelledby="report-evidence-title">
      <summary>查看已纳入的证据（{sources.length}）</summary>
      <div className="replica-report-section-heading">
        <div>
          <p>证据来源</p>
          <h2 id="report-evidence-title">证据清单</h2>
        </div>
        <span>{sources.length} 条</span>
      </div>
      {sources.length === 0 ? (
        <p className="replica-report-empty">暂无已纳入的底稿证据</p>
      ) : (
        <ul>
          {sources.map((source) => (
            <li key={source.id}>
              <div>
                <strong>{source.title}</strong>
                <span>{source.kind} · {source.reference}</span>
              </div>
              <span>{source.status}</span>
              <span>证据详情由项目任务承载</span>
            </li>
          ))}
        </ul>
      )}
    </details>
  );
}

function triggerBrowserDownload(blob: Blob, filename: string): void {
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  anchor.hidden = true;
  document.body.append(anchor);
  try {
    anchor.click();
  } finally {
    anchor.remove();
    URL.revokeObjectURL(objectUrl);
  }
}

function draftFailureMessage(error: unknown): string {
  if (!isBackendRequestError(error)) return "草稿创建失败，请稍后重试。";
  if (error.status === 422) {
    return error.detail ? `模板字段校验失败：${error.detail}` : "模板字段校验失败，请核对填写内容。";
  }
  if (error.status === 403) return "当前身份无权创建底稿草稿。";
  if (error.status === 404) return "所属项目不可见或已不存在。";
  return "草稿创建失败，请稍后重试。";
}

function hasNonEmptyValues(fieldValues: Readonly<Record<string, string>>): boolean {
  return Object.values(fieldValues).some((value) => value.trim().length > 0);
}

export function ReplicaReportWorkbench() {
  const auditUser = useAuditUser();
  const requestGenerationRef = useRef(0);
  const interactionGenerationRef = useRef(0);
  const submittingRef = useRef(false);
  const submitRoleRef = useRef<AuditClientRole | null>(null);
  const mountedRef = useRef(true);
  const downloadGenerationRef = useRef(0);
  const downloadPendingRef = useRef(false);
  const downloadAbortRef = useRef<AbortController | null>(null);
  const [reportState, setReportState] = useState<LaneState<ReportWorkbenchResponse>>(loadingLane(null));
  const [projectsState, setProjectsState] = useState<LaneState<ProjectsResponse>>(loadingLane(null));
  const [selectedProjectKey, setSelectedProjectKey] = useState("");
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null);
  const [fieldValues, setFieldValues] = useState<Readonly<Record<string, string>>>({});
  const [submitting, setSubmitting] = useState(false);
  const [draftError, setDraftError] = useState<string | null>(null);
  const [draftResult, setDraftResult] = useState<ReportDraftCreateResponse | null>(null);
  const [projectContextNotice, setProjectContextNotice] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [downloadingPath, setDownloadingPath] = useState<string | null>(null);
  const [signoffState, setSignoffState] = useState<
    | { readonly status: "idle" }
    | { readonly status: "signing"; readonly taskId: string }
    | { readonly status: "success"; readonly taskId: string; readonly signedBy: string }
    | { readonly status: "error"; readonly taskId: string; readonly message: string }
  >({ status: "idle" });

  const abortPendingDownload = useCallback((updateState: boolean) => {
    ++downloadGenerationRef.current;
    downloadAbortRef.current?.abort();
    downloadAbortRef.current = null;
    downloadPendingRef.current = false;
    if (updateState) setDownloadingPath(null);
  }, []);

  const loadWorkbench = useCallback((role: AuditClientRole) => {
    const generation = ++requestGenerationRef.current;
    setReportState(loadingLane(role));
    setProjectsState(loadingLane(role));

    const reportRequest = fetchReportWorkbench();
    const projectsRequest = fetchProjects();
    reportRequest
      .then((response) => {
        if (generation !== requestGenerationRef.current) return;
        setReportState({
          phase: response.store.ready ? "ready" : "degraded",
          response,
          role
        });
      })
      .catch(() => {
        if (generation === requestGenerationRef.current) {
          setReportState({ phase: "error", response: null, role });
        }
      });
    projectsRequest
      .then((response) => {
        if (generation !== requestGenerationRef.current) return;
        setProjectsState({
          phase: response.store.ready ? "ready" : "degraded",
          response,
          role
        });
      })
      .catch(() => {
        if (generation === requestGenerationRef.current) {
          setProjectsState({ phase: "error", response: null, role });
        }
      });
  }, []);

  useEffect(() => {
    abortPendingDownload(true);
    ++interactionGenerationRef.current;
    setSelectedProjectKey("");
    setSelectedTemplateId(null);
    setFieldValues({});
    setDraftError(null);
    setDraftResult(null);
    setProjectContextNotice(null);
    setDownloadError(null);
    loadWorkbench(auditUser.role);
  }, [abortPendingDownload, auditUser.role, loadWorkbench]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      abortPendingDownload(false);
    };
  }, [abortPendingDownload]);

  const roleReportState = reportState.role === auditUser.role
    ? reportState
    : loadingLane<ReportWorkbenchResponse>(auditUser.role);
  const roleProjectsState = projectsState.role === auditUser.role
    ? projectsState
    : loadingLane<ProjectsResponse>(auditUser.role);
  const report = roleReportState.phase === "ready" ? roleReportState.response : null;
  const projects = roleProjectsState.response?.items ?? [];
  const projectReady = roleProjectsState.phase === "ready" && roleProjectsState.response !== null;
  const selectedProjectVisible = projectReady && selectedProjectKey !== "" && projects.some(
    (project) => project.id === selectedProjectKey
  );
  const selectedTemplate = report?.workpaper_templates.find(
    (template) => (
      template.id === selectedTemplateId
      && isActiveTemplate(template, report.template_categories)
    )
  ) ?? null;
  const canCreate = auditUser.can("create_report_draft");
  const unsavedFields = hasNonEmptyValues(fieldValues);
  const canSelectTemplate = canCreate && selectedProjectVisible && !submitting;
  const submittingFromAnotherRole = submitting && submitRoleRef.current !== auditUser.role;
  const templateSelectionHint = !canCreate
    ? "无草稿创建权限"
    : submitting
      ? "草稿请求处理中，暂不可切换"
      : !projectReady
        ? "项目上下文未就绪"
        : !selectedProjectVisible
          ? "请先选择项目后填写模板"
          : "已选择项目，可填写模板";
  const retryVisible = (
    roleReportState.phase === "error" ||
    roleReportState.phase === "degraded" ||
    roleProjectsState.phase === "error" ||
    roleProjectsState.phase === "degraded"
  );

  useEffect(() => {
    if (!projectReady || selectedProjectKey === "" || selectedProjectVisible) return;
    ++interactionGenerationRef.current;
    setSelectedProjectKey("");
    setSelectedTemplateId(null);
    setFieldValues({});
    setDraftError(null);
    setDraftResult(null);
    setProjectContextNotice("原项目已不可见，请重新选择");
  }, [projectReady, selectedProjectKey, selectedProjectVisible]);

  useEffect(() => {
    if (
      roleReportState.phase !== "ready"
      || selectedTemplateId === null
      || selectedTemplate !== null
    ) return;
    ++interactionGenerationRef.current;
    setSelectedTemplateId(null);
    setFieldValues({});
    setDraftError(null);
    setDraftResult(null);
  }, [roleReportState.phase, selectedTemplate, selectedTemplateId]);

  function clearDraftDisplay(): void {
    ++interactionGenerationRef.current;
    setDraftError(null);
    setDraftResult(null);
  }

  function selectProject(projectKey: string): void {
    if (submittingRef.current || projectKey === selectedProjectKey) return;
    if (unsavedFields && !window.confirm("切换项目将清空当前未保存字段，是否继续？")) return;
    clearDraftDisplay();
    setSelectedProjectKey(projectKey);
    setFieldValues({});
    setProjectContextNotice(null);
  }

  function selectTemplate(templateId: string): void {
    if (submittingRef.current || templateId === selectedTemplateId) return;
    if (unsavedFields && !window.confirm("切换模板将清空当前未保存字段，是否继续？")) return;
    clearDraftDisplay();
    setSelectedTemplateId(templateId);
    setFieldValues({});
  }

  function changeField(field: string, value: string): void {
    if (submittingRef.current) return;
    setFieldValues((current) => ({ ...current, [field]: value }));
    setDraftError(null);
    setDraftResult(null);
  }

  async function submitDraft(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!selectedTemplate || !selectedProjectVisible || !canCreate || submittingRef.current) return;
    const allowedFields = new Set(selectedTemplate.evidence_bindings);
    const normalizedValues: Record<string, string> = {};
    for (const [field, value] of Object.entries(fieldValues)) {
      const normalizedValue = value.trim();
      if (allowedFields.has(field) && normalizedValue) normalizedValues[field] = normalizedValue;
    }
    if (Object.keys(normalizedValues).length === 0) return;

    const generation = interactionGenerationRef.current;
    submittingRef.current = true;
    submitRoleRef.current = auditUser.role;
    setSubmitting(true);
    setDraftError(null);
    setDraftResult(null);
    try {
      const response = await createReportDraft({
        template_id: selectedTemplate.id,
        project_key: selectedProjectKey,
        field_values: normalizedValues
      });
      if (generation === interactionGenerationRef.current && mountedRef.current) {
        setDraftResult(response);
      }
    } catch (error) {
      if (generation === interactionGenerationRef.current && mountedRef.current) {
        setDraftError(draftFailureMessage(error));
      }
    } finally {
      submittingRef.current = false;
      submitRoleRef.current = null;
      if (mountedRef.current) setSubmitting(false);
    }
  }

  const handleDownload = useCallback(async (href: string) => {
    if (downloadPendingRef.current) return;
    const generation = ++downloadGenerationRef.current;
    const controller = new AbortController();
    downloadPendingRef.current = true;
    downloadAbortRef.current = controller;
    setDownloadError(null);
    setDownloadingPath(href);
    try {
      const artifact = await downloadAuditArtifact(href, { signal: controller.signal });
      if (generation !== downloadGenerationRef.current || controller.signal.aborted) return;
      triggerBrowserDownload(artifact.blob, artifact.filename);
    } catch {
      if (generation === downloadGenerationRef.current && !controller.signal.aborted && mountedRef.current) {
        setDownloadError("文件下载失败，请确认当前身份与任务访问权限。");
      }
    } finally {
      if (generation === downloadGenerationRef.current) {
        downloadPendingRef.current = false;
        downloadAbortRef.current = null;
        if (mountedRef.current) setDownloadingPath(null);
      }
    }
  }, []);

  const handleSignoff = useCallback(async (taskId: string, note: string) => {
    setSignoffState({ status: "signing", taskId });
    try {
      const result = await signReportDraft(taskId, note);
      setSignoffState({ status: "success", taskId, signedBy: result.signed_by });
      if (mountedRef.current) {
        loadWorkbench(reportState.role ?? auditUser.role);
      }
    } catch {
      setSignoffState({ status: "error", taskId, message: "签发失败，请确认权限后重试。" });
    }
  }, [auditUser.role, loadWorkbench, reportState.role]);

  return (
    <main className="replica-page replica-page-standard replica-report-workbench">
      <header className="replica-page-header">
        <div>
          <p className="replica-kicker">审计交付</p>
          <h1>报告与底稿</h1>
          <p>选择项目和交付物，汇入大模型分析结果，人工复核后预览或下载。</p>
        </div>
        <div className="replica-report-boundary" aria-label="报告边界">
          <span>{canCreate ? "草稿可创建" : "当前身份只读"}</span>
          <span>签发按服务端门禁</span>
        </div>
      </header>

      <section className="replica-report-control-band" aria-label="草稿项目上下文">
        <div>
          <p>第 1 步 · 选择项目</p>
          <label>
            <span>所属项目</span>
            <select
              aria-label="所属项目"
              disabled={!projectReady || submitting}
              value={selectedProjectVisible ? selectedProjectKey : ""}
              onChange={(event) => selectProject(event.target.value)}
            >
              <option value="">请选择可见项目</option>
              {projects.map((project) => (
                <option key={project.id} value={project.id}>{project.name}</option>
              ))}
            </select>
          </label>
          {roleProjectsState.phase === "loading" ? <span>正在读取可见项目…</span> : null}
          {roleProjectsState.phase === "error" ? (
            <span className="replica-report-inline-error" role="alert">项目列表读取失败，草稿创建暂不可用。</span>
          ) : null}
          {roleProjectsState.phase === "degraded" ? <span>项目存储未就绪</span> : null}
          {projectReady && projects.length === 0 ? <span>当前没有可见项目</span> : null}
          {projectContextNotice ? <span role="status">{projectContextNotice}</span> : null}
        </div>
        <div>
          <p>权限状态</p>
          <strong>{canCreate ? "可创建并保存草稿" : "当前角色无权新建底稿草稿"}</strong>
          <span>项目范围和下载权限会在每次操作时重新校验。</span>
          {submittingFromAnotherRole ? <span>上一身份的草稿请求仍在处理中</span> : null}
        </div>
        <details className="replica-report-admin-details">
          <summary>管理与服务详情</summary>
          <p>服务状态：{lanePhaseLabels[roleReportState.phase]}</p>
          <p>存储实现：{roleReportState.response?.store.backend ?? "尚未就绪"}</p>
        </details>
      </section>

      {roleReportState.phase === "loading" ? (
        <p className="replica-report-message" role="status">正在读取报表目录…</p>
      ) : null}
      {roleReportState.phase === "error" ? (
        <p className="replica-report-message is-error" role="alert">报表工作台读取失败，请稍后重试。</p>
      ) : null}
      {roleReportState.phase === "degraded" ? (
        <div className="replica-report-message is-degraded" role="status">
          <strong>报表数据源未就绪</strong>
          <span>当前不展示草稿入口或历史 fixture。</span>
        </div>
      ) : null}
      <button disabled={submitting} type="button" onClick={() => loadWorkbench(auditUser.role)}>
        {retryVisible ? "重试工作台" : "刷新工作台"}
      </button>

      {report ? (
        <>
          <CategoryCatalog
            canSelect={canSelectTemplate}
            categories={report.template_categories}
            selectionHint={templateSelectionHint}
            selectedTemplateId={selectedTemplateId}
            templates={report.workpaper_templates}
            onSelectTemplate={selectTemplate}
          />

          {selectedTemplate && selectedProjectVisible ? (
            <DraftPanel
              canCreate={canCreate && selectedProjectVisible}
              error={draftError}
              fieldValues={fieldValues}
              projectKey={selectedProjectKey}
              result={draftResult}
              saving={submitting}
              template={selectedTemplate}
              onFieldChange={changeField}
              onSubmit={submitDraft}
            />
          ) : null}

          <ReportMetrics metrics={report.metrics} />
          {downloadError ? <p className="replica-report-error" role="alert">{downloadError}</p> : null}
          <div className="replica-report-ledger-grid">
            <ReportLedger
              downloadingPath={downloadingPath}
              entries={report.report_entries}
              signoffState={signoffState}
              onDownload={handleDownload}
              onSignoff={handleSignoff}
            />
            <EvidenceLedger sources={report.report_evidence_sources} />
          </div>
        </>
      ) : null}
    </main>
  );
}
