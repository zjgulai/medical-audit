import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { StrictMode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AuditUserProvider } from "@/components/shell/audit-user-context";
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
  ReportWorkbenchResponse,
  WorkpaperTemplateRegistryItem
} from "@/lib/api-types";
import { AUDIT_ROLE_STORAGE_KEY, writeAuditClientRole } from "@/lib/audit-user";

import { ReplicaReportWorkbench } from "./replica-report-workbench";

vi.mock("@/lib/api-client", () => ({
  createReportDraft: vi.fn(),
  downloadAuditArtifact: vi.fn(),
  fetchProjects: vi.fn(),
  fetchReportWorkbench: vi.fn(),
  isBackendRequestError: (error: unknown) => (
    error instanceof Error && error.name === "BackendRequestError" && "status" in error
  )
}));

const createReportDraftMock = vi.mocked(createReportDraft);
const downloadAuditArtifactMock = vi.mocked(downloadAuditArtifact);
const fetchProjectsMock = vi.mocked(fetchProjects);
const fetchReportWorkbenchMock = vi.mocked(fetchReportWorkbench);

const templateCategories: readonly ReportTemplateCategory[] = [
  { id: "plan", label: "计划类", availability: "awaiting-business-template" },
  { id: "workpaper", label: "底稿类", availability: "active" },
  { id: "evidence", label: "取证类", availability: "awaiting-business-template" },
  { id: "confirmation", label: "函证类", availability: "awaiting-business-template" },
  { id: "report", label: "报告类", availability: "awaiting-business-template" },
  { id: "remediation", label: "整改类", availability: "awaiting-business-template" }
];

const templates: readonly WorkpaperTemplateRegistryItem[] = [
  reportTemplate(
    "workpaper-summary-risk",
    "费用汇总风险底稿",
    ["费用分类汇总", "支付分项合计", "人工复核意见"]
  ),
  reportTemplate(
    "workpaper-category-review",
    "分类费用复核清单",
    ["平均费用偏离", "基金支付结构"]
  ),
  reportTemplate(
    "workpaper-visit-detail",
    "就诊明细疑点摘要",
    ["就诊记录号", "隐私字段处理记录"]
  )
];

const alphaProject = project("ALPHA", "Alpha 医保专项");
const betaProject = project("BETA", "Beta 收费专项");

function reportTemplate(
  id: string,
  name: string,
  evidenceBindings: readonly string[]
): WorkpaperTemplateRegistryItem {
  return {
    id,
    category_id: "workpaper",
    name,
    source_template_id: `${id}-source`,
    source_table: `${name}来源表`,
    source_file_name: `${name}.xlsx`,
    sheet_name: "汇总表",
    output_type: "底稿草稿",
    registry_status: "active",
    expected_columns: evidenceBindings,
    key_checks: evidenceBindings.map((field) => `核对${field}`),
    evidence_bindings: evidenceBindings,
    prompt: `生成${name}`,
    chat_href: "/chat"
  };
}

function project(id: string, name: string): ProjectSummaryApiItem {
  return {
    id,
    name,
    audit_topic: `${name}审计主题`,
    organization_name: "测试医院",
    member_count: 2,
    creator: "审计办",
    creator_user_identifier: "next-admin",
    created_at: "2026-07-12T08:00:00Z",
    status: "进行中",
    operation_label: "进入项目",
    source: "system-default"
  };
}

function projectsResponse(
  items: readonly ProjectSummaryApiItem[] = [alphaProject, betaProject],
  ready = true
): ProjectsResponse {
  return {
    items,
    roles: ["项目负责人", "审计员", "业务专家", "信息科", "只读观察员"],
    statuses: ["在项目中", "待确认"],
    project_statuses: ["待开始", "进行中", "已完成", "已归档"],
    store: { ready, backend: ready ? "SqlAlchemyProjectMemberStore" : "unavailable" }
  };
}

function reportEntry(
  id: string,
  status: ReportWorkbenchEntry["status"],
  downloads: ReportWorkbenchEntry["download_links"]
): ReportWorkbenchEntry {
  return {
    id,
    title: id === "blocked-report" ? "医保费用补证底稿" : "医保基金专项报告",
    status,
    report_no: id === "blocked-report" ? "WP-001" : "RPT-001",
    owner: "审计办",
    source: "review-task",
    included_finding_count: status === "门禁阻断" ? 0 : 2,
    appendix_count: status === "门禁阻断" ? 0 : 1,
    gate_summary: status === "门禁阻断" ? "证据链待补齐" : "报告门禁已通过",
    updated_at: "2026-07-12T08:00:00Z",
    href: "/pages/review-tasks",
    download_links: downloads
  };
}

function reportResponse(options: {
  readonly entries?: readonly ReportWorkbenchEntry[];
  readonly ready?: boolean;
  readonly evidence?: ReportWorkbenchResponse["report_evidence_sources"];
  readonly backend?: string;
} = {}): ReportWorkbenchResponse {
  const entries = options.entries ?? [];
  return {
    format: "report-workbench-v1",
    generated_at: "2026-07-12T08:00:00Z",
    template_registry_status: "active",
    template_categories: templateCategories,
    workpaper_templates: templates,
    report_entries: entries,
    report_evidence_sources: options.evidence ?? [],
    metrics: {
      report_count: entries.length,
      signed_report_count: entries.filter((entry) => entry.status === "已签发").length,
      blocked_report_count: entries.filter((entry) => entry.status === "门禁阻断").length,
      included_finding_count: entries.reduce((total, entry) => total + entry.included_finding_count, 0),
      docx_download_count: entries.filter((entry) => entry.download_links.report_docx !== null).length
    },
    store: {
      ready: options.ready ?? true,
      backend: options.backend ?? (options.ready === false ? "unavailable" : "JsonFileReviewTaskStore")
    }
  };
}

function draftResponse(
  audit: ReportDraftCreateResponse["audit"] = {
    status: "ready",
    durability: "durable",
    local_only: false,
    intent_recorded: true,
    completion_recorded: true
  }
): ReportDraftCreateResponse {
  return {
    format: "report-template-draft-v1",
    task_id: "report-draft-001",
    template_id: "workpaper-summary-risk",
    category_id: "workpaper",
    project_key: "ALPHA",
    project_href: "/projects?project=ALPHA",
    status: "pending-review",
    store: { ready: true, backend: "JsonFileReviewTaskStore" },
    formal_report_created: false,
    provider_call: false,
    audit
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

function backendRequestError(status: number, detail: string | null = null): Error {
  return Object.assign(
    new Error(`Backend request failed: POST /api/v1/reports/drafts returned ${status}`),
    {
      name: "BackendRequestError",
      method: "POST",
      path: "/api/v1/reports/drafts",
      status,
      detail
    }
  );
}

function renderWorkbench() {
  return render(
    <AuditUserProvider>
      <ReplicaReportWorkbench />
    </AuditUserProvider>
  );
}

function renderStrictWorkbench() {
  return render(
    <StrictMode>
      <AuditUserProvider>
        <ReplicaReportWorkbench />
      </AuditUserProvider>
    </StrictMode>
  );
}

async function selectTemplateAndProject(
  templateName = "费用汇总风险底稿",
  projectKey = "ALPHA"
) {
  fireEvent.change(await screen.findByRole("combobox", { name: "所属项目" }), {
    target: { value: projectKey }
  });
  fireEvent.click(screen.getByRole("button", { name: `填写模板：${templateName}` }));
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.unstubAllGlobals();
  window.localStorage.clear();
  fetchReportWorkbenchMock.mockResolvedValue(reportResponse());
  fetchProjectsMock.mockResolvedValue(projectsResponse());
  createReportDraftMock.mockResolvedValue(draftResponse());
  downloadAuditArtifactMock.mockResolvedValue({
    blob: new Blob(["artifact"], { type: "application/octet-stream" }),
    filename: "review-task-001.docx"
  });
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("ReplicaReportWorkbench", () => {
  it("requires an explicit ready project before a template can be opened", async () => {
    renderWorkbench();

    expect(await screen.findByRole("heading", { name: "六类模板目录", level: 2 })).toBeInTheDocument();
    expect(screen.getByText("请先选择项目后填写模板")).toBeInTheDocument();
    const buttons = screen.getAllByRole("button", { name: /^填写模板：/ });
    expect(buttons).toHaveLength(3);
    for (const button of buttons) expect(button).toBeDisabled();

    fireEvent.change(screen.getByRole("combobox", { name: "所属项目" }), {
      target: { value: "ALPHA" }
    });
    for (const button of buttons) expect(button).toBeEnabled();
  });

  it("renders dynamic evidence fields and submits only non-empty allowed values exactly once", async () => {
    const draft = deferred<ReportDraftCreateResponse>();
    createReportDraftMock.mockReturnValue(draft.promise);
    renderWorkbench();
    await selectTemplateAndProject();

    expect(screen.getByRole("heading", { name: "创建草稿：费用汇总风险底稿" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "费用分类汇总" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "支付分项合计" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "人工复核意见" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "费用分类汇总" })).toHaveAttribute("maxLength", "4000");
    expect(screen.getAllByText("0 / 4000")).toHaveLength(3);

    fireEvent.change(screen.getByRole("textbox", { name: "费用分类汇总" }), {
      target: { value: "门诊费用 120 万元" }
    });
    expect(screen.getByText("11 / 4000")).toBeInTheDocument();
    fireEvent.change(screen.getByRole("textbox", { name: "人工复核意见" }), {
      target: { value: "   " }
    });
    const form = screen.getByRole("form", { name: "费用汇总风险底稿草稿" });
    fireEvent.submit(form);
    fireEvent.submit(form);

    expect(createReportDraftMock).toHaveBeenCalledTimes(1);
    expect(createReportDraftMock).toHaveBeenCalledWith({
      template_id: "workpaper-summary-risk",
      project_key: "ALPHA",
      field_values: { 费用分类汇总: "门诊费用 120 万元" }
    });

    await act(async () => draft.resolve(draftResponse()));
  });

  it("shows a truthful project handoff, generation boundaries and audit durability after success", async () => {
    createReportDraftMock.mockResolvedValue(
      draftResponse({
        status: "degraded",
        durability: "intent-only",
        local_only: false,
        intent_recorded: true,
        completion_recorded: false
      })
    );
    renderWorkbench();
    await selectTemplateAndProject();
    fireEvent.change(screen.getByRole("textbox", { name: "人工复核意见" }), {
      target: { value: "待主任复核" }
    });
    fireEvent.submit(screen.getByRole("form", { name: "费用汇总风险底稿草稿" }));

    const handoff = await screen.findByRole("link", { name: "转入项目管理" });
    expect(handoff).toHaveAttribute("href", "/projects?project=ALPHA");
    expect(screen.getByText("未生成正式报告")).toBeInTheDocument();
    expect(screen.getByText("未调用外部 provider")).toBeInTheDocument();
    expect(screen.getByText("formal_report_created=false")).toBeInTheDocument();
    expect(screen.getByText("provider_call=false")).toBeInTheDocument();
    expect(screen.getByText("审计记录：intent-only（降级）")).toBeInTheDocument();
    expect(screen.queryByText("正式报告已生成")).not.toBeInTheDocument();
  });

  it("surfaces runtime boundary anomalies instead of repeating false claims", async () => {
    const anomalousResponse = {
      ...draftResponse(),
      formal_report_created: true,
      provider_call: true
    } as unknown as ReportDraftCreateResponse;
    createReportDraftMock.mockResolvedValue(anomalousResponse);
    renderWorkbench();
    await selectTemplateAndProject();
    fireEvent.change(screen.getByRole("textbox", { name: "人工复核意见" }), {
      target: { value: "待主任复核" }
    });
    fireEvent.submit(screen.getByRole("form", { name: "费用汇总风险底稿草稿" }));

    expect(await screen.findByText("formal_report_created=true")).toBeInTheDocument();
    expect(screen.getByText("provider_call=true")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("草稿响应违反无副作用边界");
    expect(screen.queryByText("草稿已进入待复核队列")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "转入项目管理" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "前往项目核查异常" })).toHaveAttribute(
      "href",
      "/projects?project=ALPHA"
    );
    expect(screen.queryByText("未生成正式报告")).not.toBeInTheDocument();
    expect(screen.queryByText("未调用外部 provider")).not.toBeInTheDocument();
  });

  it("renders report metrics, evidence, gate status and only non-null controlled downloads", async () => {
    const blocked = reportEntry("blocked-report", "门禁阻断", {
      page: "/pages/review-tasks",
      task_docx: "/review-tasks/blocked-report/export?format=docx",
      report_docx: null,
      report_markdown: null,
      report_json: null
    });
    const signed = reportEntry("signed-report", "已签发", {
      page: "/pages/review-tasks",
      task_docx: "/review-tasks/signed-report/export?format=docx",
      report_docx: "/review-tasks/signed-report/signed-report?format=docx",
      report_markdown: "/review-tasks/signed-report/signed-report?format=markdown",
      report_json: "/review-tasks/signed-report/signed-report?format=json"
    });
    fetchReportWorkbenchMock.mockResolvedValue(reportResponse({
      entries: [blocked, signed],
      evidence: [
        {
          id: "evidence-blocked",
          title: "workpaper-001",
          kind: "底稿",
          reference: "blocked-report · 附件 0 条",
          status: "待补证",
          href: "/pages/review-tasks"
        }
      ]
    }));

    renderWorkbench();

    expect(await screen.findByText("报告总数")).toBeInTheDocument();
    expect(screen.getByText("已签发报告")).toBeInTheDocument();
    expect(screen.getByText("门禁阻断报告")).toBeInTheDocument();
    expect(screen.getByText("证据链待补齐")).toBeInTheDocument();
    expect(screen.getByText("workpaper-001")).toBeInTheDocument();

    const blockedRow = screen.getByRole("row", { name: /医保费用补证底稿/ });
    expect(within(blockedRow).queryByRole("link", { name: "查看任务" })).not.toBeInTheDocument();
    expect(within(blockedRow).getByText("详情请从项目管理进入")).toBeInTheDocument();
    expect(within(blockedRow).getByRole("button", { name: "下载任务 DOCX" })).toBeEnabled();
    expect(within(blockedRow).queryByRole("button", { name: "下载报告 DOCX" })).not.toBeInTheDocument();
    expect(within(blockedRow).queryByRole("button", { name: "下载报告 Markdown" })).not.toBeInTheDocument();
    expect(within(blockedRow).queryByRole("link", { name: /下载/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "查看证据" })).not.toBeInTheDocument();
    expect(screen.getByText("证据详情由项目任务承载")).toBeInTheDocument();
    expect(document.querySelector('a[href="/pages/review-tasks"]')).toBeNull();
    expect(screen.queryByRole("button", { name: /签发/ })).not.toBeInTheDocument();
  });

  it("keeps technicians read-only even when active templates are visible", async () => {
    window.localStorage.setItem(AUDIT_ROLE_STORAGE_KEY, "technician");
    renderWorkbench();

    expect(await screen.findByText("当前角色无权新建底稿草稿")).toBeInTheDocument();
    expect(screen.getByText("当前身份只读")).toBeInTheDocument();
    expect(screen.queryByText("草稿可创建")).not.toBeInTheDocument();
    const activeButtons = screen.getAllByRole("button", { name: /^填写模板：/ });
    expect(activeButtons).toHaveLength(3);
    for (const button of activeButtons) expect(button).toBeDisabled();
  });

  it("starts report and project reads together and ignores stale role responses", async () => {
    const firstReport = deferred<ReportWorkbenchResponse>();
    const firstProjects = deferred<ProjectsResponse>();
    fetchReportWorkbenchMock
      .mockReturnValueOnce(firstReport.promise)
      .mockResolvedValueOnce(reportResponse({ backend: "FreshReviewTaskStore" }));
    fetchProjectsMock
      .mockReturnValueOnce(firstProjects.promise)
      .mockResolvedValueOnce(projectsResponse([betaProject]));
    renderWorkbench();

    await waitFor(() => {
      expect(fetchReportWorkbenchMock).toHaveBeenCalledTimes(1);
      expect(fetchProjectsMock).toHaveBeenCalledTimes(1);
    });
    act(() => writeAuditClientRole("member"));
    expect(await screen.findByRole("option", { name: "Beta 收费专项" })).toBeInTheDocument();
    expect(screen.getByText("FreshReviewTaskStore")).toBeInTheDocument();

    await act(async () => {
      firstReport.resolve(reportResponse({ backend: "StaleReviewTaskStore" }));
      firstProjects.resolve(projectsResponse([alphaProject]));
    });
    expect(screen.queryByRole("option", { name: "Alpha 医保专项" })).not.toBeInTheDocument();
    expect(screen.queryByText("StaleReviewTaskStore")).not.toBeInTheDocument();
  });

  it("locks project, template and form controls until the POST settles", async () => {
    const pendingDraft = deferred<ReportDraftCreateResponse>();
    createReportDraftMock.mockReturnValue(pendingDraft.promise);
    renderWorkbench();
    await selectTemplateAndProject();
    const opinion = screen.getByRole("textbox", { name: "人工复核意见" });
    fireEvent.change(opinion, { target: { value: "待复核" } });
    fireEvent.submit(screen.getByRole("form", { name: "费用汇总风险底稿草稿" }));

    expect(screen.getByRole("combobox", { name: "所属项目" })).toBeDisabled();
    for (const button of screen.getAllByRole("button", { name: /^填写模板：/ })) {
      expect(button).toBeDisabled();
    }
    for (const textbox of screen.getAllByRole("textbox")) expect(textbox).toBeDisabled();
    expect(screen.getByRole("button", { name: "正在创建草稿…" })).toBeDisabled();
    fireEvent.change(screen.getByRole("combobox", { name: "所属项目" }), {
      target: { value: "BETA" }
    });
    fireEvent.click(screen.getByRole("button", { name: "填写模板：分类费用复核清单" }));
    expect(screen.getByRole("combobox", { name: "所属项目" })).toHaveValue("ALPHA");
    expect(screen.getByRole("heading", { name: "创建草稿：费用汇总风险底稿" })).toBeInTheDocument();
    expect(opinion).toHaveValue("待复核");

    await act(async () => pendingDraft.resolve(draftResponse()));
    expect(screen.getByRole("combobox", { name: "所属项目" })).toBeEnabled();
  });

  it("restores draft results and controls after a StrictMode lifecycle replay", async () => {
    const pendingDraft = deferred<ReportDraftCreateResponse>();
    createReportDraftMock.mockReturnValue(pendingDraft.promise);
    renderStrictWorkbench();
    await selectTemplateAndProject();
    fireEvent.change(screen.getByRole("textbox", { name: "人工复核意见" }), {
      target: { value: "StrictMode 待复核" }
    });
    fireEvent.submit(screen.getByRole("form", { name: "费用汇总风险底稿草稿" }));

    expect(screen.getByRole("combobox", { name: "所属项目" })).toBeDisabled();
    expect(screen.getByRole("textbox", { name: "人工复核意见" })).toBeDisabled();
    await act(async () => pendingDraft.resolve(draftResponse()));

    expect(await screen.findByText("草稿已进入待复核队列")).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "所属项目" })).toBeEnabled();
    expect(screen.getByRole("textbox", { name: "人工复核意见" })).toBeEnabled();
    for (const button of screen.getAllByRole("button", { name: /^填写模板：/ })) {
      expect(button).toBeEnabled();
    }
  });

  it("keeps the POST lock across a role change and releases it only after settle", async () => {
    const firstDraft = deferred<ReportDraftCreateResponse>();
    createReportDraftMock.mockReturnValue(firstDraft.promise);
    renderWorkbench();
    await selectTemplateAndProject();
    fireEvent.change(screen.getByRole("textbox", { name: "人工复核意见" }), {
      target: { value: "旧上下文请求" }
    });
    fireEvent.submit(screen.getByRole("form", { name: "费用汇总风险底稿草稿" }));

    act(() => writeAuditClientRole("member"));
    expect(await screen.findByText("上一身份的草稿请求仍在处理中")).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "所属项目" })).toBeDisabled();
    expect(createReportDraftMock).toHaveBeenCalledTimes(1);

    await act(async () => firstDraft.resolve(draftResponse()));
    await waitFor(() => expect(screen.getByRole("combobox", { name: "所属项目" })).toBeEnabled());
    expect(screen.queryByRole("link", { name: "转入项目管理" })).not.toBeInTheDocument();

    await selectTemplateAndProject();
    fireEvent.change(screen.getByRole("textbox", { name: "人工复核意见" }), {
      target: { value: "新上下文请求" }
    });
    fireEvent.submit(screen.getByRole("form", { name: "费用汇总风险底稿草稿" }));
    expect(createReportDraftMock).toHaveBeenCalledTimes(2);
  });

  it("preserves unsaved fields when a project change is cancelled and clears only after confirmation", async () => {
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    renderWorkbench();
    await selectTemplateAndProject();
    const opinion = screen.getByRole("textbox", { name: "人工复核意见" });
    fireEvent.change(opinion, { target: { value: "尚未保存的项目意见" } });

    fireEvent.change(screen.getByRole("combobox", { name: "所属项目" }), {
      target: { value: "BETA" }
    });
    expect(confirm).toHaveBeenCalledWith("切换项目将清空当前未保存字段，是否继续？");
    expect(screen.getByRole("combobox", { name: "所属项目" })).toHaveValue("ALPHA");
    expect(opinion).toHaveValue("尚未保存的项目意见");

    confirm.mockReturnValue(true);
    fireEvent.change(screen.getByRole("combobox", { name: "所属项目" }), {
      target: { value: "BETA" }
    });
    expect(screen.getByRole("combobox", { name: "所属项目" })).toHaveValue("BETA");
    expect(opinion).toHaveValue("");
  });

  it("preserves unsaved fields when a template change is cancelled and clears only after confirmation", async () => {
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    renderWorkbench();
    await selectTemplateAndProject();
    const opinion = screen.getByRole("textbox", { name: "人工复核意见" });
    fireEvent.change(opinion, { target: { value: "尚未保存的模板意见" } });

    fireEvent.click(screen.getByRole("button", { name: "填写模板：分类费用复核清单" }));
    expect(confirm).toHaveBeenCalledWith("切换模板将清空当前未保存字段，是否继续？");
    expect(screen.getByRole("heading", { name: "创建草稿：费用汇总风险底稿" })).toBeInTheDocument();
    expect(opinion).toHaveValue("尚未保存的模板意见");

    confirm.mockReturnValue(true);
    fireEvent.click(screen.getByRole("button", { name: "填写模板：分类费用复核清单" }));
    expect(screen.getByRole("heading", { name: "创建草稿：分类费用复核清单" })).toBeInTheDocument();
    expect(screen.queryByDisplayValue("尚未保存的模板意见")).not.toBeInTheDocument();
  });

  it.each([
    [backendRequestError(422, "字段不受支持"), "模板字段校验失败：字段不受支持"],
    [backendRequestError(403, "create_report_draft is not allowed"), "当前身份无权创建底稿草稿。"],
    [backendRequestError(404, "project not found"), "所属项目不可见或已不存在。"],
    [new Error("network offline"), "草稿创建失败，请稍后重试。"]
  ] as const)("maps draft failure %# to a specific safe message", async (error, expectedMessage) => {
    createReportDraftMock.mockRejectedValueOnce(error);
    renderWorkbench();
    await selectTemplateAndProject();
    fireEvent.change(screen.getByRole("textbox", { name: "人工复核意见" }), {
      target: { value: "待复核" }
    });
    fireEvent.submit(screen.getByRole("form", { name: "费用汇总风险底稿草稿" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(expectedMessage);
  });

  it("renders ready report data while the independent project lane is loading then fails", async () => {
    const projects = deferred<ProjectsResponse>();
    fetchReportWorkbenchMock.mockResolvedValueOnce(reportResponse());
    fetchProjectsMock.mockReturnValueOnce(projects.promise);
    renderWorkbench();

    expect(await screen.findByRole("heading", { name: "六类模板目录" })).toBeInTheDocument();
    expect(screen.getByText("报告总数")).toBeInTheDocument();
    expect(screen.getByText("正在读取可见项目…")).toBeInTheDocument();

    await act(async () => projects.reject(new Error("project api down")));
    expect(await screen.findByRole("alert")).toHaveTextContent("项目列表读取失败");
    expect(screen.getByText("报告总数")).toBeInTheDocument();
    for (const button of screen.getAllByRole("button", { name: /^填写模板：/ })) {
      expect(button).toBeDisabled();
    }
  });

  it("keeps report data visible when project storage is degraded", async () => {
    fetchReportWorkbenchMock.mockResolvedValueOnce(reportResponse());
    fetchProjectsMock.mockResolvedValueOnce(projectsResponse([alphaProject], false));
    renderWorkbench();

    expect(await screen.findByText("项目存储未就绪")).toBeInTheDocument();
    expect(screen.getByText("报告总数")).toBeInTheDocument();
    for (const button of screen.getAllByRole("button", { name: /^填写模板：/ })) {
      expect(button).toBeDisabled();
    }
  });

  it("keeps the ready project lane visible when reports fail and retries both lanes", async () => {
    fetchReportWorkbenchMock.mockRejectedValueOnce(new Error("report api down"));
    fetchProjectsMock.mockResolvedValueOnce(projectsResponse());
    renderWorkbench();

    expect(await screen.findByRole("alert")).toHaveTextContent("报表工作台读取失败");
    expect(screen.getByRole("option", { name: "Alpha 医保专项" })).toBeInTheDocument();
    expect(screen.queryByText("报告总数")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "重试工作台" }));

    expect(await screen.findByRole("heading", { name: "六类模板目录" })).toBeInTheDocument();
    expect(fetchReportWorkbenchMock).toHaveBeenCalledTimes(2);
    expect(fetchProjectsMock).toHaveBeenCalledTimes(2);
  });

  it("keeps project selection visible without pretending a degraded report lane is ready", async () => {
    fetchReportWorkbenchMock.mockResolvedValueOnce(reportResponse({ ready: false }));
    fetchProjectsMock.mockResolvedValueOnce(projectsResponse());
    renderWorkbench();

    expect(await screen.findByText("报表数据源未就绪")).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Alpha 医保专项" })).toBeInTheDocument();
    expect(screen.queryByText("报告总数")).not.toBeInTheDocument();
  });

  it("renders truthful empty lanes without fixture fallback", async () => {
    fetchReportWorkbenchMock.mockResolvedValueOnce(reportResponse({ entries: [] }));
    fetchProjectsMock.mockResolvedValueOnce(projectsResponse([]));
    renderWorkbench();

    expect(await screen.findByText("当前没有可见项目")).toBeInTheDocument();
    expect(screen.getByText("暂无报告台账")).toBeInTheDocument();
    expect(screen.queryByText("2026年医疗费用专项审计报告")).not.toBeInTheDocument();
  });

  it("downloads through a locked button without exposing the backend path as navigation", async () => {
    const blocked = reportEntry("blocked-report", "门禁阻断", {
      page: "/pages/review-tasks",
      task_docx: "/review-tasks/blocked-report/export?format=docx",
      report_docx: null,
      report_markdown: null,
      report_json: null
    });
    fetchReportWorkbenchMock.mockResolvedValue(reportResponse({ entries: [blocked] }));
    const artifact = deferred<{ readonly blob: Blob; readonly filename: string }>();
    downloadAuditArtifactMock.mockReturnValueOnce(artifact.promise);
    const createObjectURL = vi.fn(() => "blob:report-download");
    const revokeObjectURL = vi.fn();
    vi.stubGlobal("URL", {
      ...URL,
      createObjectURL,
      revokeObjectURL
    });
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    renderWorkbench();

    const download = await screen.findByRole("button", { name: "下载任务 DOCX" });
    expect(screen.queryByRole("link", { name: "下载任务 DOCX" })).not.toBeInTheDocument();
    expect(document.querySelector('a[href^="/review-tasks/"]')).toBeNull();
    fireEvent.contextMenu(download);
    fireEvent.mouseDown(download, { button: 1 });
    expect(downloadAuditArtifactMock).not.toHaveBeenCalled();
    fireEvent.click(download);
    fireEvent.click(download);

    expect(downloadAuditArtifactMock).toHaveBeenCalledTimes(1);
    expect(downloadAuditArtifactMock).toHaveBeenCalledWith(
      "/review-tasks/blocked-report/export?format=docx",
      { signal: expect.any(AbortSignal) }
    );
    expect(screen.getByRole("button", { name: "正在下载：下载任务 DOCX" })).toBeDisabled();

    await act(async () => artifact.resolve({
      blob: new Blob(["artifact"], { type: "application/octet-stream" }),
      filename: "review-task-001.docx"
    }));

    await waitFor(() => {
      expect(createObjectURL).toHaveBeenCalledTimes(1);
      expect(clickSpy).toHaveBeenCalledTimes(1);
      expect(revokeObjectURL).toHaveBeenCalledWith("blob:report-download");
    });
    expect(screen.getByRole("button", { name: "下载任务 DOCX" })).toBeEnabled();

    downloadAuditArtifactMock.mockRejectedValueOnce(new Error("download denied"));
    fireEvent.click(screen.getByRole("button", { name: "下载任务 DOCX" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("文件下载失败");
  });

  it("unlocks StrictMode downloads after success and reports a later failure", async () => {
    const blocked = reportEntry("strict-report", "门禁阻断", {
      page: "/pages/review-tasks",
      task_docx: "/review-tasks/strict-report/export?format=docx",
      report_docx: null,
      report_markdown: null,
      report_json: null
    });
    fetchReportWorkbenchMock.mockResolvedValue(reportResponse({ entries: [blocked] }));
    const artifact = deferred<{ readonly blob: Blob; readonly filename: string }>();
    downloadAuditArtifactMock.mockReturnValueOnce(artifact.promise);
    const createObjectURL = vi.fn(() => "blob:strict-report-download");
    const revokeObjectURL = vi.fn();
    vi.stubGlobal("URL", { ...URL, createObjectURL, revokeObjectURL });
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    renderStrictWorkbench();

    fireEvent.click(await screen.findByRole("button", { name: "下载任务 DOCX" }));
    await act(async () => artifact.resolve({
      blob: new Blob(["strict-artifact"], { type: "application/octet-stream" }),
      filename: "strict-report.docx"
    }));

    await waitFor(() => {
      expect(createObjectURL).toHaveBeenCalledTimes(1);
      expect(clickSpy).toHaveBeenCalledTimes(1);
      expect(revokeObjectURL).toHaveBeenCalledWith("blob:strict-report-download");
      expect(screen.getByRole("button", { name: "下载任务 DOCX" })).toBeEnabled();
    });

    downloadAuditArtifactMock.mockRejectedValueOnce(new Error("strict download denied"));
    fireEvent.click(screen.getByRole("button", { name: "下载任务 DOCX" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("文件下载失败");
    expect(screen.getByRole("button", { name: "下载任务 DOCX" })).toBeEnabled();
  });

  it.each(["role-change", "unmount"] as const)(
    "aborts a pending download on %s and prevents a stale browser save",
    async (mode) => {
      const blocked = reportEntry("blocked-report", "门禁阻断", {
        page: "/pages/review-tasks",
        task_docx: "/review-tasks/blocked-report/export?format=docx",
        report_docx: null,
        report_markdown: null,
        report_json: null
      });
      fetchReportWorkbenchMock.mockResolvedValue(reportResponse({ entries: [blocked] }));
      const artifact = deferred<{ readonly blob: Blob; readonly filename: string }>();
      let signal: AbortSignal | undefined;
      downloadAuditArtifactMock.mockImplementation((...rawArgs) => {
        const [, options] = rawArgs as unknown as [string, { readonly signal?: AbortSignal }];
        signal = options?.signal;
        return artifact.promise;
      });
      const createObjectURL = vi.fn(() => "blob:stale-download");
      const revokeObjectURL = vi.fn();
      vi.stubGlobal("URL", { ...URL, createObjectURL, revokeObjectURL });
      const view = renderWorkbench();
      fireEvent.click(await screen.findByRole("button", { name: "下载任务 DOCX" }));
      expect(signal).toBeInstanceOf(AbortSignal);

      if (mode === "role-change") {
        act(() => writeAuditClientRole("member"));
      } else {
        view.unmount();
      }
      expect(signal?.aborted).toBe(true);

      await act(async () => artifact.resolve({
        blob: new Blob(["stale"], { type: "application/octet-stream" }),
        filename: "stale.docx"
      }));
      expect(createObjectURL).not.toHaveBeenCalled();
      expect(revokeObjectURL).not.toHaveBeenCalled();
    }
  );
});
