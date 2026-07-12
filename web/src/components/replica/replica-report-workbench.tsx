"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent, MouseEvent } from "react";

import { useAuditUser } from "@/components/shell/audit-user-context";
import {
  createReportDraft,
  downloadAuditArtifact,
  fetchProjects,
  fetchReportWorkbench
} from "@/lib/api-client";
import type {
  ProjectSummaryApiItem,
  ProjectsResponse,
  ReportDraftCreateResponse,
  ReportTemplateCategory,
  ReportWorkbenchEntry,
  ReportWorkbenchEvidenceSource,
  ReportWorkbenchResponse,
  WorkpaperTemplateRegistryItem
} from "@/lib/api-types";
import type { AuditClientRole } from "@/lib/audit-user";

type ReportLoadPhase = "loading" | "ready" | "degraded" | "error";

type ReportLoadState = {
  readonly report: ReportWorkbenchResponse | null;
  readonly projects: ProjectsResponse | null;
  readonly phase: ReportLoadPhase;
  readonly role: AuditClientRole | null;
};

type CategoryCatalogProps = {
  readonly categories: readonly ReportTemplateCategory[];
  readonly templates: readonly WorkpaperTemplateRegistryItem[];
  readonly canCreate: boolean;
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

type AuthenticatedDownloadLinkProps = {
  readonly href: string;
  readonly label: string;
  readonly onDownload: (href: string) => Promise<void>;
};

const initialLoadState: ReportLoadState = {
  report: null,
  projects: null,
  phase: "loading",
  role: null
};

function CategoryCatalog({
  categories,
  templates,
  canCreate,
  selectedTemplateId,
  onSelectTemplate
}: CategoryCatalogProps) {
  return (
    <section className="replica-report-catalog" aria-label="报表分类目录">
      {categories.map((category, index) => {
        const categoryTemplates = templates.filter((template) => template.category_id === category.id);
        const active = category.availability === "active";
        return (
          <article
            className={active ? "is-active" : "is-awaiting"}
            key={category.id}
          >
            <div className="replica-report-category-heading">
              <span aria-hidden="true">{String(index + 1).padStart(2, "0")}</span>
              <div>
                <h3>{category.label}</h3>
                <p>{active ? `${categoryTemplates.length} 项受控模板` : "模板尚未进入目录"}</p>
              </div>
            </div>
            {active ? (
              <div className="replica-report-template-list">
                {categoryTemplates.length > 0 ? categoryTemplates.map((template) => (
                  <div className="replica-report-template" key={template.id}>
                    <div>
                      <strong>{template.name}</strong>
                      <span>{template.output_type} · {template.source_table}</span>
                    </div>
                    <button
                      aria-label={`填写模板：${template.name}`}
                      aria-pressed={selectedTemplateId === template.id}
                      disabled={!canCreate}
                      type="button"
                      onClick={() => onSelectTemplate(template.id)}
                    >
                      填写模板
                    </button>
                  </div>
                )) : <p className="replica-report-empty-inline">当前无已启用模板</p>}
              </div>
            ) : (
              <span className="replica-report-awaiting-badge">待业务模板确认</span>
            )}
          </article>
        );
      })}
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
          <p>受控底稿草稿</p>
          <h2 id="report-draft-title">创建草稿：{template.name}</h2>
        </div>
        <span>{template.evidence_bindings.length} 个允许字段</span>
      </div>
      <p className="replica-report-draft-note">
        仅提交当前模板声明的 evidence_bindings；空白字段不会进入草稿。
      </p>
      <form aria-label={`${template.name}草稿`} onSubmit={onSubmit}>
        {template.evidence_bindings.map((field) => (
          <label key={field}>
            <span>{field}</span>
            <textarea
              name={field}
              rows={3}
              value={fieldValues[field] ?? ""}
              onChange={(event) => onFieldChange(field, event.target.value)}
            />
          </label>
        ))}
        <div className="replica-report-form-actions">
          <button
            disabled={!canCreate || !projectKey || nonEmptyFieldCount === 0 || saving}
            type="submit"
          >
            {saving ? "正在创建草稿…" : "创建受控草稿"}
          </button>
          <span>{projectKey ? `目标项目：${projectKey}` : "请先选择所属项目"}</span>
        </div>
      </form>
      {error ? <p className="replica-report-error" role="alert">{error}</p> : null}
      {result ? (
        <div className="replica-report-handoff" aria-live="polite">
          <div>
            <span>草稿已进入待复核队列</span>
            <strong>{result.task_id}</strong>
          </div>
          <ul>
            <li>
              <span>formal_report_created={String(result.formal_report_created)}</span>
              {result.formal_report_created === false ? <span>未生成正式报告</span> : null}
            </li>
            <li>
              <span>provider_call={String(result.provider_call)}</span>
              {result.provider_call === false ? <span>未调用外部 provider</span> : null}
            </li>
            <li>
              审计记录：{result.audit.durability}
              {result.audit.status === "degraded" ? "（降级）" : ""}
              {result.audit.status === "local-only" ? "（本地）" : ""}
            </li>
          </ul>
          {boundaryAnomaly ? (
            <p className="replica-report-error" role="alert">
              草稿响应违反无副作用边界，请勿将其视为安全草稿。
            </p>
          ) : null}
          <Link href={result.project_href}>转入项目管理</Link>
        </div>
      ) : null}
    </section>
  );
}

function ReportMetrics({ metrics }: { readonly metrics: ReportWorkbenchResponse["metrics"] }) {
  const items = [
    ["报告总数", metrics.report_count],
    ["已签发报告", metrics.signed_report_count],
    ["门禁阻断报告", metrics.blocked_report_count],
    ["已纳入疑点", metrics.included_finding_count],
    ["报告 DOCX", metrics.docx_download_count]
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

function AuthenticatedDownloadLink({ href, label, onDownload }: AuthenticatedDownloadLinkProps) {
  async function handleClick(event: MouseEvent<HTMLAnchorElement>) {
    event.preventDefault();
    await onDownload(href);
  }

  return <a href={href} onClick={handleClick}>{label}</a>;
}

function ReportLedger({
  entries,
  onDownload
}: {
  readonly entries: readonly ReportWorkbenchEntry[];
  readonly onDownload: (href: string) => Promise<void>;
}) {
  return (
    <section className="replica-report-ledger" aria-labelledby="report-ledger-title">
      <div className="replica-report-section-heading">
        <div>
          <p>复核与报告</p>
          <h2 id="report-ledger-title">报告台账</h2>
        </div>
        <span>{entries.length} 条</span>
      </div>
      {entries.length === 0 ? (
        <p className="replica-report-empty">暂无报告台账</p>
      ) : (
        <div className="replica-report-table-wrap">
          <table>
            <thead>
              <tr>
                <th>报告 / 底稿</th>
                <th>状态</th>
                <th>证据与门禁</th>
                <th>负责人</th>
                <th>受控操作</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => (
                <tr key={entry.id}>
                  <td>
                    <strong>{entry.title}</strong>
                    <span>{entry.report_no} · {entry.id}</span>
                  </td>
                  <td><span className={`replica-report-status status-${entry.status}`}>{entry.status}</span></td>
                  <td>
                    <strong>{entry.gate_summary}</strong>
                    <span>{entry.included_finding_count} 个疑点 · {entry.appendix_count} 个附件</span>
                  </td>
                  <td>{entry.owner}</td>
                  <td>
                    <nav aria-label={`${entry.title}操作`}>
                      <span>详情请从项目管理进入</span>
                      <AuthenticatedDownloadLink
                        href={entry.download_links.task_docx}
                        label="下载任务 DOCX"
                        onDownload={onDownload}
                      />
                      {entry.download_links.report_docx ? (
                        <AuthenticatedDownloadLink
                          href={entry.download_links.report_docx}
                          label="下载报告 DOCX"
                          onDownload={onDownload}
                        />
                      ) : null}
                      {entry.download_links.report_markdown ? (
                        <AuthenticatedDownloadLink
                          href={entry.download_links.report_markdown}
                          label="下载报告 Markdown"
                          onDownload={onDownload}
                        />
                      ) : null}
                      {entry.download_links.report_json ? (
                        <AuthenticatedDownloadLink
                          href={entry.download_links.report_json}
                          label="下载报告 JSON"
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
    <section className="replica-report-evidence" aria-labelledby="report-evidence-title">
      <div className="replica-report-section-heading">
        <div>
          <p>证据来源</p>
          <h2 id="report-evidence-title">底稿证据索引</h2>
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
    </section>
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

export function ReplicaReportWorkbench() {
  const auditUser = useAuditUser();
  const requestGenerationRef = useRef(0);
  const interactionGenerationRef = useRef(0);
  const submittingRef = useRef(false);
  const [loadState, setLoadState] = useState<ReportLoadState>(initialLoadState);
  const [selectedProjectKey, setSelectedProjectKey] = useState("");
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null);
  const [fieldValues, setFieldValues] = useState<Readonly<Record<string, string>>>({});
  const [submitting, setSubmitting] = useState(false);
  const [draftError, setDraftError] = useState<string | null>(null);
  const [draftResult, setDraftResult] = useState<ReportDraftCreateResponse | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const loadWorkbench = useCallback((role: AuditClientRole) => {
    const generation = ++requestGenerationRef.current;
    setLoadState({ ...initialLoadState, role });
    Promise.allSettled([fetchReportWorkbench(), fetchProjects()]).then(([reportResult, projectsResult]) => {
      if (generation !== requestGenerationRef.current) return;
      if (reportResult.status === "rejected" || projectsResult.status === "rejected") {
        setLoadState({ report: null, projects: null, phase: "error", role });
        return;
      }
      const degraded = !reportResult.value.store.ready || !projectsResult.value.store.ready;
      setLoadState({
        report: reportResult.value,
        projects: projectsResult.value,
        phase: degraded ? "degraded" : "ready",
        role
      });
    });
  }, []);

  useEffect(() => {
    ++interactionGenerationRef.current;
    submittingRef.current = false;
    setSelectedProjectKey("");
    setSelectedTemplateId(null);
    setFieldValues({});
    setSubmitting(false);
    setDraftError(null);
    setDraftResult(null);
    setDownloadError(null);
    loadWorkbench(auditUser.role);
  }, [auditUser.role, loadWorkbench]);

  const roleScopedLoadState = loadState.role === auditUser.role
    ? loadState
    : { ...initialLoadState, role: auditUser.role };
  const report = roleScopedLoadState.report;
  const projects = roleScopedLoadState.projects;
  const selectedTemplate = report?.workpaper_templates.find(
    (template) => template.id === selectedTemplateId
  ) ?? null;
  const canCreate = auditUser.can("create_report_draft");

  function resetDraftInteraction(): void {
    ++interactionGenerationRef.current;
    submittingRef.current = false;
    setSubmitting(false);
    setDraftError(null);
    setDraftResult(null);
  }

  function selectProject(projectKey: string): void {
    resetDraftInteraction();
    setSelectedProjectKey(projectKey);
    setFieldValues({});
  }

  function selectTemplate(templateId: string): void {
    resetDraftInteraction();
    setSelectedTemplateId(templateId);
    setFieldValues({});
  }

  function changeField(field: string, value: string): void {
    setFieldValues((current) => ({ ...current, [field]: value }));
    setDraftError(null);
    setDraftResult(null);
  }

  async function submitDraft(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!selectedTemplate || !selectedProjectKey || !canCreate || submittingRef.current) return;
    const allowedFields = new Set(selectedTemplate.evidence_bindings);
    const normalizedValues: Record<string, string> = {};
    for (const [field, value] of Object.entries(fieldValues)) {
      const normalizedValue = value.trim();
      if (allowedFields.has(field) && normalizedValue) normalizedValues[field] = normalizedValue;
    }
    if (Object.keys(normalizedValues).length === 0) return;

    const generation = interactionGenerationRef.current;
    submittingRef.current = true;
    setSubmitting(true);
    setDraftError(null);
    setDraftResult(null);
    try {
      const response = await createReportDraft({
        template_id: selectedTemplate.id,
        project_key: selectedProjectKey,
        field_values: normalizedValues
      });
      if (generation === interactionGenerationRef.current) setDraftResult(response);
    } catch {
      if (generation === interactionGenerationRef.current) {
        setDraftError("草稿创建失败，请核对项目权限或稍后重试。");
      }
    } finally {
      if (generation === interactionGenerationRef.current) {
        submittingRef.current = false;
        setSubmitting(false);
      }
    }
  }

  const handleDownload = useCallback(async (href: string) => {
    setDownloadError(null);
    try {
      const artifact = await downloadAuditArtifact(href);
      triggerBrowserDownload(artifact.blob, artifact.filename);
    } catch {
      setDownloadError("文件下载失败，请确认当前身份与任务访问权限。");
    }
  }, []);

  return (
    <main className="replica-page replica-page-standard replica-report-workbench">
      <header className="replica-page-header">
        <div>
          <p className="replica-kicker">受控报告工作台</p>
          <h1>审计底稿与报告台账</h1>
          <p>按业务模板形成可追溯草稿，正式报告生成与签发仍由后续门禁控制。</p>
        </div>
        <div className="replica-report-boundary" aria-label="报告边界">
          <span>草稿可创建</span>
          <span>签发不在本页</span>
        </div>
      </header>

      {roleScopedLoadState.phase === "loading" ? (
        <p className="replica-report-message" role="status">正在读取报表目录与可见项目…</p>
      ) : null}
      {roleScopedLoadState.phase === "error" ? (
        <p className="replica-report-message is-error" role="alert">报表工作台读取失败，请稍后重试。</p>
      ) : null}
      {roleScopedLoadState.phase === "degraded" ? (
        <div className="replica-report-message is-degraded" role="status">
          <strong>报表数据源未就绪</strong>
          <span>当前不展示草稿入口或历史 fixture。</span>
        </div>
      ) : null}
      {roleScopedLoadState.phase === "ready" && report && projects ? (
        <>
          <section className="replica-report-control-band" aria-label="草稿项目上下文">
            <div>
              <p>项目归属</p>
              <label>
                <span>所属项目</span>
                <select
                  aria-label="所属项目"
                  value={selectedProjectKey}
                  onChange={(event) => selectProject(event.target.value)}
                >
                  <option value="">请选择可见项目</option>
                  {projects.items.map((project: ProjectSummaryApiItem) => (
                    <option key={project.id} value={project.id}>{project.name}</option>
                  ))}
                </select>
              </label>
              {projects.items.length === 0 ? <span>当前没有可见项目</span> : null}
            </div>
            <div>
              <p>当前身份边界</p>
              <strong>{canCreate ? "可创建底稿草稿" : "当前角色无权新建底稿草稿"}</strong>
              <span>后端仍会独立执行项目可见性与角色鉴权。</span>
            </div>
            <div>
              <p>数据来源</p>
              <strong>{report.store.backend}</strong>
              <span>{report.template_registry_status} · {report.generated_at}</span>
            </div>
          </section>

          <CategoryCatalog
            canCreate={canCreate}
            categories={report.template_categories}
            selectedTemplateId={selectedTemplateId}
            templates={report.workpaper_templates}
            onSelectTemplate={selectTemplate}
          />

          {selectedTemplate ? (
            <DraftPanel
              canCreate={canCreate}
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
            <ReportLedger entries={report.report_entries} onDownload={handleDownload} />
            <EvidenceLedger sources={report.report_evidence_sources} />
          </div>
        </>
      ) : null}
    </main>
  );
}
