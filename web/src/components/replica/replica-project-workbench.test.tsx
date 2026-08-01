import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AuditUserProvider } from "@/components/shell/audit-user-context";
import {
  createProject,
  createProjectMember,
  fetchProjectDashboard,
  fetchProjectFileBlob,
  fetchProjectFiles,
  fetchProjectMembers,
  fetchProjects,
  reviewProjectFile,
  uploadProjectFile
} from "@/lib/api-client";
import type {
  ApiProjectStatus,
  ProjectDashboardResponse,
  ProjectFileApiItem,
  ProjectFilesResponse,
  ProjectMemberApiItem,
  ProjectMembersResponse,
  ProjectsResponse,
  ProjectSummaryApiItem
} from "@/lib/api-types";
import { AUDIT_ROLE_STORAGE_KEY, writeAuditClientRole } from "@/lib/audit-user";

import { ReplicaProjectWorkbench } from "./replica-project-workbench";

const { useSearchParamsMock } = vi.hoisted(() => ({
  useSearchParamsMock: vi.fn(() => new URLSearchParams())
}));

vi.mock("next/navigation", () => ({
  useSearchParams: useSearchParamsMock
}));

vi.mock("@/lib/api-client", () => ({
  createProject: vi.fn(),
  createProjectMember: vi.fn(),
  fetchProjectDashboard: vi.fn(),
  fetchProjectFileBlob: vi.fn(),
  fetchProjectFiles: vi.fn(),
  fetchProjectMembers: vi.fn(),
  fetchProjects: vi.fn(),
  reviewProjectFile: vi.fn(),
  uploadProjectFile: vi.fn()
}));

const fetchProjectsMock = vi.mocked(fetchProjects);
const fetchProjectMembersMock = vi.mocked(fetchProjectMembers);
const fetchProjectDashboardMock = vi.mocked(fetchProjectDashboard);
const fetchProjectFilesMock = vi.mocked(fetchProjectFiles);
const fetchProjectFileBlobMock = vi.mocked(fetchProjectFileBlob);
const createProjectMock = vi.mocked(createProject);
const createProjectMemberMock = vi.mocked(createProjectMember);
const uploadProjectFileMock = vi.mocked(uploadProjectFile);
const reviewProjectFileMock = vi.mocked(reviewProjectFile);
const globalsCss = readFileSync(resolve(process.cwd(), "src/app/globals.css"), "utf-8");

const projectStatuses: readonly ApiProjectStatus[] = ["待开始", "进行中", "已完成", "已归档"];

function project(
  id: string,
  name: string,
  status: ApiProjectStatus = "进行中",
  memberCount: number | null = 1
): ProjectSummaryApiItem {
  return {
    id,
    name,
    audit_topic: `${name}专题`,
    organization_name: "测试医院",
    member_count: memberCount,
    creator: `${name}创建人`,
    creator_user_identifier: `${id.toLowerCase()}-creator`,
    created_at: "2026-07-12T08:00:00Z",
    status,
    operation_label: "进入项目",
    source: "system-default"
  };
}

function projectsResponse(
  items: readonly ProjectSummaryApiItem[],
  ready = true,
  persistentWritesReady = ready
): ProjectsResponse {
  return {
    items,
    roles: ["项目负责人", "审计员", "业务专家", "信息科", "只读观察员"],
    statuses: ["在项目中", "待确认"],
    project_statuses: projectStatuses,
    store: {
      ready,
      backend: ready ? "SqlAlchemyProjectMemberStore" : "unavailable",
      persistent_writes_ready: persistentWritesReady,
      history_review_task_writes_ready: persistentWritesReady
    }
  };
}

function member(
  id: string,
  projectKey: string,
  name: string,
  userIdentifier: string | null = `${id}-account`
): ProjectMemberApiItem {
  return {
    id,
    project_key: projectKey,
    user_identifier: userIdentifier,
    name,
    role: "审计员",
    department: "内审部",
    status: "在项目中",
    created_by: "next-admin",
    source: "custom",
    metadata: {}
  };
}

function membersResponse(
  projectKey: string,
  items: readonly ProjectMemberApiItem[],
  ready = true
): ProjectMembersResponse {
  return {
    items,
    project_key: projectKey,
    roles: ["项目负责人", "审计员", "业务专家", "信息科", "只读观察员"],
    statuses: ["在项目中", "待确认"],
    store: { ready, backend: ready ? "SqlAlchemyProjectMemberStore" : "unavailable" }
  };
}

function filesResponse(projectKey: string): ProjectFilesResponse {
  return {
    contract_version: "project-files-v2",
    project_key: projectKey,
    items: [],
    store: { ready: true, backend: "InMemoryDocumentUploadStore" },
    permissions: {
      can_upload: true,
      can_review: true,
      can_withdraw_own: true,
      visibility_scope: "project"
    }
  };
}

function projectFile(overrides: Partial<ProjectFileApiItem> = {}): ProjectFileApiItem {
  return {
    id: "document-upload-project-file",
    name: "audit-evidence.pdf",
    extension: "pdf",
    size_bytes: 2048,
    sha256: "a".repeat(64),
    created_by: "next-admin",
    created_at: "2026-07-29T12:00:00Z",
    project_name: "Alpha项目",
    department: "财务科",
    document_type: "财务资料",
    description: "月度结算资料",
    replaces_upload_id: null,
    review_status: "pending-review",
    review_note: "",
    reviewed_by: null,
    reviewed_at: null,
    review_history: [],
    security_scan_status: "local-policy-passed",
    dlp_status: "clear",
    preview_url: "/api/v1/projects/ALPHA/files/document-upload-project-file/preview",
    download_url: "/api/v1/projects/ALPHA/files/document-upload-project-file/download",
    ...overrides
  };
}

function dashboardResponse(
  item: ProjectSummaryApiItem,
  status: ProjectDashboardResponse["store"]["status"] = "ready"
): ProjectDashboardResponse {
  const membersReady = status !== "unavailable";
  const findingsReady = status === "ready";
  return {
    format: "project-dashboard-v1",
    project: item,
    metrics: [
      {
        key: "open_findings",
        label: "待处理疑点",
        value: "0",
        helper: "来自当前项目审计疑点库",
        tone: "warning"
      }
    ],
    queue: [
      {
        id: `${item.id}-queue`,
        title: `${item.name}复核任务`,
        owner: "审计员",
        dueLabel: "今日",
        status: "open",
        risk: "medium"
      }
    ],
    activities: [
      {
        id: `${item.id}-activity`,
        title: `${item.name}同步完成`,
        description: "项目范围内数据已刷新。",
        timeLabel: "刚刚"
      }
    ],
    status_distribution: [{ status: "open", label: "待处理", count: 0 }],
    member_workloads: [
      { name: "审计员", role: "审计员", department: "内审部", total: 0, pending: 0, closed: 0 }
    ],
    evidence_grade: status === "ready" ? "live-db-connected" : "partial-live-db-connected",
    production_side_effect: "none",
    store: {
      ready: status === "ready",
      project_members_ready: membersReady,
      audit_findings_ready: findingsReady,
      status,
      backend: {
        project_members: membersReady ? "SqlAlchemyProjectMemberStore" : "unavailable",
        audit_findings: findingsReady ? "SqlAlchemyAuditFindingStore" : "unavailable"
      }
    }
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

function renderWithUser() {
  return render(
    <AuditUserProvider>
      <ReplicaProjectWorkbench />
    </AuditUserProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
  useSearchParamsMock.mockReturnValue(new URLSearchParams());
  const alpha = project("ALPHA", "Alpha项目", "进行中", 1);
  fetchProjectsMock.mockResolvedValue(projectsResponse([alpha]));
  fetchProjectMembersMock.mockResolvedValue(membersResponse(alpha.id, [member("ALPHA-M1", alpha.id, "张审计")]));
  fetchProjectDashboardMock.mockResolvedValue(dashboardResponse(alpha));
  fetchProjectFilesMock.mockResolvedValue(filesResponse(alpha.id));
  fetchProjectFileBlobMock.mockResolvedValue(new Blob(["file"]));
  createProjectMock.mockRejectedValue(new Error("not configured"));
  createProjectMemberMock.mockRejectedValue(new Error("not configured"));
  uploadProjectFileMock.mockRejectedValue(new Error("not configured"));
  reviewProjectFileMock.mockRejectedValue(new Error("not configured"));
});

describe("ReplicaProjectWorkbench", () => {
  it("keeps project row actions visible in horizontally constrained tables", () => {
    expect(globalsCss).toMatch(
      /\.replica-project-workbench \.replica-project-table th:last-child,\s*\.replica-project-workbench \.replica-project-table td:last-child\s*\{[^}]*position:\s*sticky;[^}]*right:\s*0;/s
    );
  });

  it("lays out the create form as a readable full-width semantic section", () => {
    expect(globalsCss).toMatch(
      /\.replica-project-workbench \.replica-project-member-form h3,[^}]*\[role="status"\][^{]*\{[^}]*grid-column:\s*1\s*\/\s*-1;/s
    );
    expect(globalsCss).toMatch(
      /\.replica-project-workbench select,[^}]*\.replica-project-workbench input,[^}]*\.replica-project-workbench textarea\s*\{/s
    );
  });

  it("renders the API project list, canonical status filter and truthful zero", async () => {
    const alpha = project("ALPHA", "Alpha项目", "进行中", 2);
    const done = project("DONE", "已完成项目", "已完成", 0);
    const unknown = project("UNKNOWN", "成员待同步项目", "进行中", null);
    fetchProjectsMock.mockResolvedValue(projectsResponse([alpha, done, unknown]));

    render(<ReplicaProjectWorkbench />);

    expect(await screen.findByText("当前显示：全部项目")).toBeInTheDocument();
    const statusFilter = screen.getByRole("combobox", { name: "项目状态" });
    expect(within(statusFilter).getAllByRole("option").map((option) => option.textContent)).toEqual([
      "全部",
      "待开始",
      "进行中",
      "已完成",
      "已归档"
    ]);
    const doneRow = screen.getByRole("row", { name: /已完成项目/ });
    expect(within(doneRow).getByText("0")).toBeInTheDocument();
    const unknownRow = screen.getByRole("row", { name: /成员待同步项目/ });
    expect(within(unknownRow).getByText("待同步")).toBeInTheDocument();

    fireEvent.change(statusFilter, { target: { value: "已完成" } });
    expect(screen.getByRole("row", { name: /已完成项目/ })).toBeInTheDocument();
    expect(screen.queryByRole("row", { name: /Alpha项目/ })).not.toBeInTheDocument();
    expect(fetchProjectMembersMock).not.toHaveBeenCalled();
    expect(fetchProjectDashboardMock).not.toHaveBeenCalled();
  });

  it("separates empty, error with retry, and degraded project-list states", async () => {
    fetchProjectsMock.mockResolvedValueOnce(projectsResponse([]));
    const { unmount } = render(<ReplicaProjectWorkbench />);
    expect(await screen.findByText("当前没有可见项目")).toBeInTheDocument();
    unmount();

    fetchProjectsMock.mockRejectedValueOnce(new Error("offline"));
    fetchProjectsMock.mockResolvedValueOnce(projectsResponse([project("RETRY", "重试项目")]));
    const second = render(<ReplicaProjectWorkbench />);
    const projectListError = await screen.findByText("项目列表读取失败");
    expect(projectListError).toHaveAttribute("role", "alert");
    fireEvent.click(screen.getByRole("button", { name: "重试项目列表" }));
    expect(await screen.findByText("重试项目")).toBeInTheDocument();
    second.unmount();

    fetchProjectsMock.mockResolvedValueOnce(projectsResponse([project("DEGRADED", "降级项目")], false));
    render(<ReplicaProjectWorkbench />);
    expect(await screen.findByText("项目列表存储未就绪")).toBeInTheDocument();
    expect(screen.getByText("降级项目")).toBeInTheDocument();
  });

  it("loads members and dashboard only after an explicit project selection", async () => {
    render(<ReplicaProjectWorkbench />);

    const selectButton = await screen.findByRole("button", { name: "查看：Alpha项目" });
    expect(fetchProjectMembersMock).not.toHaveBeenCalled();
    expect(fetchProjectDashboardMock).not.toHaveBeenCalled();
    fireEvent.click(selectButton);

    await waitFor(() => {
      expect(fetchProjectMembersMock).toHaveBeenCalledWith("ALPHA");
      expect(fetchProjectDashboardMock).toHaveBeenCalledWith("ALPHA");
      expect(fetchProjectFilesMock).toHaveBeenCalledWith("ALPHA");
    });
    expect(await screen.findByRole("heading", { name: "项目详情：Alpha项目" })).toBeInTheDocument();
    expect(screen.getByText("ALPHA-M1-account")).toBeInTheDocument();
    expect(screen.getByText("待处理疑点")).toBeInTheDocument();
    expect(screen.getByText("Alpha项目复核任务")).toBeInTheDocument();
    expect(screen.getByText("Alpha项目同步完成")).toBeInTheDocument();
    expect(screen.getByText("live-db-connected")).toBeInTheDocument();
    expect(screen.getByText("SqlAlchemyProjectMemberStore / SqlAlchemyAuditFindingStore")).toBeInTheDocument();
  });

  it("lets an admin upload a file into the selected project", async () => {
    uploadProjectFileMock.mockResolvedValue({
      contract_version: "project-files-v2",
      project_key: "ALPHA",
      item: projectFile(),
      store: { ready: true, backend: "InMemoryDocumentUploadStore" }
    });
    const { container } = render(<ReplicaProjectWorkbench />);
    fireEvent.click(await screen.findByRole("button", { name: "查看：Alpha项目" }));
    await waitFor(() => expect(fetchProjectFilesMock).toHaveBeenCalledWith("ALPHA"));
    fireEvent.click(screen.getByRole("tab", { name: "资料上传" }));

    const fileInput = container.querySelector(
      '.replica-project-file-picker input[type="file"]'
    ) as HTMLInputElement;
    const file = new File(["%PDF"], "audit-evidence.pdf", {
      type: "application/pdf"
    });
    fireEvent.change(fileInput, { target: { files: [file] } });
    fireEvent.change(screen.getByRole("combobox", { name: "资料类型" }), {
      target: { value: "财务资料" }
    });
    fireEvent.change(screen.getByRole("textbox", { name: "所属部门" }), {
      target: { value: "财务科" }
    });
    fireEvent.change(screen.getByRole("textbox", { name: "资料说明" }), {
      target: { value: "月度结算资料" }
    });
    fireEvent.click(screen.getByRole("button", { name: "提交 1 份资料" }));

    await waitFor(() => {
      expect(uploadProjectFileMock).toHaveBeenCalledWith("ALPHA", {
        file,
        department: "财务科",
        document_type: "财务资料",
        description: "月度结算资料",
        replaces_upload_id: undefined
      });
    });
    expect(await screen.findByText("已提交 1 份项目资料，等待审核。")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "项目文件 1" }));
    expect(screen.getByText("audit-evidence.pdf")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "预览" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "下载" })).toBeInTheDocument();
  });

  it("records a review decision and routes a returned file into replacement upload", async () => {
    const pendingFile = projectFile();
    fetchProjectFilesMock.mockResolvedValue({
      ...filesResponse("ALPHA"),
      items: [pendingFile]
    });
    reviewProjectFileMock.mockResolvedValue({
      contract_version: "project-files-v2",
      project_key: "ALPHA",
      item: projectFile({
        review_status: "changes-requested",
        review_note: "请补充签章页",
        reviewed_by: "next-admin",
        reviewed_at: "2026-08-01T06:00:00Z",
        review_history: [{
          status: "changes-requested",
          note: "请补充签章页",
          reviewed_by: "next-admin",
          reviewed_at: "2026-08-01T06:00:00Z"
        }]
      })
    });

    render(<ReplicaProjectWorkbench />);
    fireEvent.click(await screen.findByRole("button", { name: "查看：Alpha项目" }));
    fireEvent.click(await screen.findByRole("tab", { name: "审核状态 1" }));
    fireEvent.change(screen.getByRole("textbox", { name: "处理说明：audit-evidence.pdf" }), {
      target: { value: "请补充签章页" }
    });
    fireEvent.click(screen.getByRole("button", { name: "退回补正" }));

    await waitFor(() => {
      expect(reviewProjectFileMock).toHaveBeenCalledWith(
        "ALPHA",
        pendingFile.id,
        { status: "changes-requested", note: "请补充签章页" }
      );
    });
    expect(await screen.findByText("审核意见：请补充签章页")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "上传补正版" }));
    expect(screen.getByRole("heading", { name: "上传项目资料" })).toBeInTheDocument();
    expect(screen.getByText("正在补正：")).toHaveTextContent("audit-evidence.pdf");
    expect(screen.getByRole("textbox", { name: "资料说明" })).toHaveValue(
      "补正：audit-evidence.pdf；审核意见：请补充签章页"
    );
  });

  it("creates a project exactly once from the admin-only form", async () => {
    const pendingCreate = deferred<Awaited<ReturnType<typeof createProject>>>();
    const createdProject = {
      ...project("FUND-CHECK-202607", "医保基金专项检查", "待开始", 1),
      audit_topic: "医保基金使用合规",
      organization_name: "测试医院",
      creator: "next-admin",
      creator_user_identifier: "next-admin",
      source: "collaboration-v1"
    };
    createProjectMock.mockReturnValue(pendingCreate.promise);

    render(<ReplicaProjectWorkbench />);

    const form = await screen.findByRole("form", { name: "新建项目" });
    fireEvent.change(screen.getByRole("textbox", { name: "项目编码" }), {
      target: { value: "  FUND-CHECK-202607  " }
    });
    fireEvent.change(screen.getByRole("textbox", { name: "项目名称" }), {
      target: { value: " 医保基金专项检查 " }
    });
    fireEvent.change(screen.getByRole("textbox", { name: "机构名称" }), {
      target: { value: " 测试医院 " }
    });
    fireEvent.change(screen.getByRole("textbox", { name: "负责部门" }), {
      target: { value: " 内审部 " }
    });
    fireEvent.change(screen.getByRole("textbox", { name: "项目说明" }), {
      target: { value: " 本地合同测试 " }
    });
    fireEvent.submit(form);
    fireEvent.submit(form);

    expect(createProjectMock).toHaveBeenCalledTimes(1);
    expect(createProjectMock).toHaveBeenCalledWith({
      project_key: "FUND-CHECK-202607",
      name: "医保基金专项检查",
      scenario_key: "charging-compliance",
      audit_topic: "医保基金使用合规",
      organization_name: "测试医院",
      owner_department: "内审部",
      description: "本地合同测试"
    });
    expect(screen.getByRole("button", { name: "创建中" })).toBeDisabled();

    await act(async () => {
      pendingCreate.resolve({
        item: createdProject,
        creator_member: {
          ...member("CREATOR-MEMBER", createdProject.id, "next-admin", "next-admin"),
          role: "项目负责人"
        },
        store: { ready: true, backend: "SqlAlchemyProjectMemberStore" },
        audit: { status: "degraded" }
      });
      await Promise.resolve();
    });

    expect(await screen.findByText("项目已创建：医保基金专项检查")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "项目已创建，但完成审计记录未写入；请联系管理员核查。"
    );
    expect(screen.getByRole("button", { name: "查看：医保基金专项检查" })).toBeInTheDocument();
  });

  it("keeps a 409 conflict out of the project list", async () => {
    createProjectMock.mockRejectedValue(Object.assign(new Error("conflict"), { status: 409 }));
    render(<ReplicaProjectWorkbench />);
    const form = await screen.findByRole("form", { name: "新建项目" });
    fireEvent.change(screen.getByRole("textbox", { name: "项目编码" }), {
      target: { value: "DUPLICATE" }
    });
    fireEvent.change(screen.getByRole("textbox", { name: "项目名称" }), {
      target: { value: "重复项目" }
    });
    fireEvent.change(screen.getByRole("textbox", { name: "机构名称" }), {
      target: { value: "测试医院" }
    });
    fireEvent.submit(form);

    expect(await screen.findByRole("alert")).toHaveTextContent("项目编码已存在");
    expect(screen.queryByRole("button", { name: "查看：重复项目" })).not.toBeInTheDocument();
  });

  it("opens a visible project from the project URL parameter", async () => {
    const alpha = project("ALPHA", "Alpha项目");
    const beta = project("BETA", "Beta项目");
    useSearchParamsMock.mockReturnValue(new URLSearchParams("project=BETA"));
    fetchProjectsMock.mockResolvedValue(projectsResponse([alpha, beta]));
    fetchProjectMembersMock.mockImplementation((projectId) => Promise.resolve(
      membersResponse(projectId, [member(`${projectId}-M1`, projectId, `${projectId}成员`)])
    ));
    fetchProjectDashboardMock.mockImplementation((projectId) => Promise.resolve(
      dashboardResponse(projectId === alpha.id ? alpha : beta)
    ));

    render(<ReplicaProjectWorkbench />);

    expect(await screen.findByRole("heading", { name: "项目详情：Beta项目" })).toBeInTheDocument();
    expect(await screen.findByText("BETA-M1-account")).toBeInTheDocument();
    expect(fetchProjectMembersMock).toHaveBeenCalledWith("BETA");
    expect(fetchProjectDashboardMock).toHaveBeenCalledWith("BETA");
  });

  it("rejects an invisible project URL and clears previously selected details", async () => {
    const alpha = project("ALPHA", "Alpha项目");
    useSearchParamsMock.mockReturnValue(new URLSearchParams("project=ALPHA"));
    fetchProjectsMock.mockResolvedValue(projectsResponse([alpha]));
    const { rerender } = render(<ReplicaProjectWorkbench />);

    expect(await screen.findByRole("heading", { name: "项目详情：Alpha项目" })).toBeInTheDocument();

    useSearchParamsMock.mockReturnValue(new URLSearchParams("project=HIDDEN"));
    rerender(<ReplicaProjectWorkbench />);

    expect(await screen.findByRole("alert")).toHaveTextContent("链接中的项目不可见或已不存在");
    expect(screen.queryByRole("heading", { name: "项目详情：Alpha项目" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "查看：Alpha项目" }));
    expect(await screen.findByRole("heading", { name: "项目详情：Alpha项目" })).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("does not reapply a project deep link after a member update changes list state", async () => {
    const alpha = project("ALPHA", "Alpha项目");
    const beta = project("BETA", "Beta项目");
    useSearchParamsMock.mockReturnValue(new URLSearchParams("project=ALPHA"));
    fetchProjectsMock.mockResolvedValue(projectsResponse([alpha, beta]));
    fetchProjectMembersMock.mockImplementation((projectId) => Promise.resolve(
      membersResponse(projectId, [member(`${projectId}-M1`, projectId, `${projectId}成员`)])
    ));
    fetchProjectDashboardMock.mockImplementation((projectId) => Promise.resolve(
      dashboardResponse(projectId === alpha.id ? alpha : beta)
    ));
    createProjectMemberMock.mockResolvedValue({
      item: member("BETA-M2", "BETA", "Beta新增成员", "beta-new"),
      store: { ready: true, backend: "SqlAlchemyProjectMemberStore" }
    });

    render(<ReplicaProjectWorkbench />);
    expect(await screen.findByRole("heading", { name: "项目详情：Alpha项目" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "查看：Beta项目" }));
    expect(await screen.findByRole("heading", { name: "项目详情：Beta项目" })).toBeInTheDocument();
    await screen.findByText("BETA-M1-account");

    fireEvent.change(screen.getByRole("textbox", { name: "账号" }), { target: { value: "beta-new" } });
    fireEvent.change(screen.getByRole("textbox", { name: "姓名" }), { target: { value: "Beta新增成员" } });
    fireEvent.change(screen.getByRole("textbox", { name: "部门" }), { target: { value: "内审部" } });
    fireEvent.click(screen.getByRole("button", { name: "新增成员" }));

    expect(await screen.findByText("beta-new")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "项目详情：Beta项目" })).toBeInTheDocument();
    expect(fetchProjectMembersMock.mock.calls.filter(([projectId]) => projectId === "ALPHA")).toHaveLength(1);
    expect(fetchProjectMembersMock.mock.calls.filter(([projectId]) => projectId === "BETA")).toHaveLength(1);
  });

  it("renders member degradation and partial dashboard data without claiming full readiness", async () => {
    const alpha = project("ALPHA", "Alpha项目");
    fetchProjectMembersMock.mockResolvedValue(membersResponse(alpha.id, [member("NO-ID", alpha.id, "未绑定成员", null)], false));
    fetchProjectDashboardMock.mockResolvedValue(dashboardResponse(alpha, "partial"));

    render(<ReplicaProjectWorkbench />);
    fireEvent.click(await screen.findByRole("button", { name: "查看：Alpha项目" }));

    expect(await screen.findByText("项目成员存储未就绪")).toBeInTheDocument();
    expect(screen.getByText("未绑定账号")).toBeInTheDocument();
    expect(screen.getByText("项目数据部分可用")).toBeInTheDocument();
    expect(screen.getByText("待处理疑点")).toBeInTheDocument();
    expect(screen.getByText("提示等级：warning")).toBeInTheDocument();
    expect(screen.getByText("状态：open · 风险：medium")).toBeInTheDocument();
    expect(screen.getByText("原始状态：open · 数量：0")).toBeInTheDocument();
    expect(screen.getByText("部门：内审部 · 总计 0 / 待处理 0 / 已关闭 0")).toBeInTheDocument();
    expect(screen.getByText("partial")).toBeInTheDocument();
    expect(screen.getByText("否（false）")).toBeInTheDocument();
    expect(screen.getByText("可用（true） · SqlAlchemyProjectMemberStore")).toBeInTheDocument();
    expect(screen.getByText("不可用（false） · unavailable")).toBeInTheDocument();
    expect(screen.queryByText("项目数据已完整同步")).not.toBeInTheDocument();
  });

  it("labels unavailable dashboard data without also claiming an empty ready state", async () => {
    const alpha = project("ALPHA", "Alpha项目");
    fetchProjectDashboardMock.mockResolvedValue(dashboardResponse(alpha, "unavailable"));

    render(<ReplicaProjectWorkbench />);
    fireEvent.click(await screen.findByRole("button", { name: "查看：Alpha项目" }));

    expect(await screen.findByText("项目数据当前不可用")).toBeInTheDocument();
    expect(screen.getByText("待处理疑点")).toBeInTheDocument();
    expect(screen.queryByText("当前项目暂无驾驶舱数据")).not.toBeInTheDocument();
    expect(screen.queryByText("项目数据已完整同步")).not.toBeInTheDocument();
  });

  it("separates empty and error states for members and dashboard", async () => {
    const alpha = project("ALPHA", "Alpha项目");
    fetchProjectMembersMock.mockResolvedValueOnce(membersResponse(alpha.id, []));
    fetchProjectDashboardMock.mockResolvedValueOnce({
      ...dashboardResponse(alpha),
      metrics: [],
      queue: [],
      activities: [],
      status_distribution: [],
      member_workloads: []
    });
    const { unmount } = render(<ReplicaProjectWorkbench />);
    fireEvent.click(await screen.findByRole("button", { name: "查看：Alpha项目" }));
    expect(await screen.findByText("当前项目没有成员")).toBeInTheDocument();
    expect(screen.getByText("当前项目暂无驾驶舱数据")).toBeInTheDocument();
    unmount();

    fetchProjectMembersMock.mockRejectedValueOnce(new Error("members down"));
    fetchProjectDashboardMock.mockRejectedValueOnce(new Error("dashboard down"));
    render(<ReplicaProjectWorkbench />);
    fireEvent.click(await screen.findByRole("button", { name: "查看：Alpha项目" }));
    const memberError = await screen.findByText("项目成员读取失败");
    expect(memberError).toHaveAttribute("role", "alert");
    expect(screen.getByText("项目驾驶舱读取失败")).toHaveAttribute("role", "alert");
    expect(screen.getByRole("button", { name: "重试项目成员" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "重试项目驾驶舱" })).toBeInTheDocument();
  });

  it("announces asynchronous loading states politely without treating them as errors", () => {
    fetchProjectsMock.mockReturnValue(new Promise(() => undefined));

    render(<ReplicaProjectWorkbench />);

    const loading = screen.getByText("项目列表读取中");
    expect(loading).toHaveAttribute("role", "status");
    expect(loading).toHaveAttribute("aria-live", "polite");
  });

  it("ignores stale detail responses after rapid project switching", async () => {
    const alpha = project("ALPHA", "Alpha项目");
    const beta = project("BETA", "Beta项目");
    const alphaMembers = deferred<ProjectMembersResponse>();
    const alphaDashboard = deferred<ProjectDashboardResponse>();
    fetchProjectsMock.mockResolvedValue(projectsResponse([alpha, beta]));
    fetchProjectMembersMock.mockImplementation((projectId) =>
      projectId === alpha.id
        ? alphaMembers.promise
        : Promise.resolve(membersResponse(beta.id, [member("BETA-M1", beta.id, "Beta成员")]))
    );
    fetchProjectDashboardMock.mockImplementation((projectId) =>
      projectId === alpha.id ? alphaDashboard.promise : Promise.resolve(dashboardResponse(beta))
    );

    render(<ReplicaProjectWorkbench />);
    fireEvent.click(await screen.findByRole("button", { name: "查看：Alpha项目" }));
    fireEvent.click(screen.getByRole("button", { name: "查看：Beta项目" }));

    expect(await screen.findByRole("heading", { name: "项目详情：Beta项目" })).toBeInTheDocument();
    expect(await screen.findByText("BETA-M1-account")).toBeInTheDocument();
    await act(async () => {
      alphaMembers.resolve(membersResponse(alpha.id, [member("ALPHA-LATE", alpha.id, "迟到成员")]));
      alphaDashboard.resolve(dashboardResponse(alpha));
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(screen.queryByText("ALPHA-LATE-account")).not.toBeInTheDocument();
      expect(screen.queryByText("Alpha项目复核任务")).not.toBeInTheDocument();
    });
    expect(screen.getByText("Beta项目复核任务")).toBeInTheDocument();
  });

  it("adds an admin-created member exactly once and does not lie after a 409", async () => {
    const alpha = project("ALPHA", "Alpha项目", "进行中", 1);
    const created = member("NEW-MEMBER", alpha.id, "赵审计", "auditor-zhao");
    fetchProjectsMock.mockResolvedValue(projectsResponse([alpha]));
    createProjectMemberMock
      .mockResolvedValueOnce({ item: created, store: { ready: true, backend: "SqlAlchemyProjectMemberStore" } })
      .mockRejectedValueOnce(new Error("409 conflict"));

    render(<ReplicaProjectWorkbench />);
    fireEvent.click(await screen.findByRole("button", { name: "查看：Alpha项目" }));
    await screen.findByText("ALPHA-M1-account");

    fireEvent.change(screen.getByRole("textbox", { name: "账号" }), { target: { value: "auditor-zhao" } });
    fireEvent.change(screen.getByRole("textbox", { name: "姓名" }), { target: { value: "赵审计" } });
    fireEvent.change(screen.getByRole("textbox", { name: "部门" }), { target: { value: "医保办" } });
    fireEvent.click(screen.getByRole("button", { name: "新增成员" }));

    await waitFor(() => {
      expect(createProjectMemberMock).toHaveBeenCalledTimes(1);
      expect(createProjectMemberMock).toHaveBeenCalledWith("ALPHA", {
        user_identifier: "auditor-zhao",
        name: "赵审计",
        role: "审计员",
        department: "医保办",
        status: "在项目中"
      });
    });
    expect(await screen.findByText("auditor-zhao")).toBeInTheDocument();
    expect(within(screen.getByRole("row", { name: /Alpha项目/ })).getByText("2")).toBeInTheDocument();

    fireEvent.change(screen.getByRole("textbox", { name: "账号" }), { target: { value: "auditor-zhao" } });
    fireEvent.change(screen.getByRole("textbox", { name: "姓名" }), { target: { value: "重复成员" } });
    fireEvent.click(screen.getByRole("button", { name: "新增成员" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("成员新增失败");
    expect(createProjectMemberMock).toHaveBeenCalledTimes(2);
    expect(screen.queryByText("重复成员")).not.toBeInTheDocument();
    expect(within(screen.getByRole("row", { name: /Alpha项目/ })).getByText("2")).toBeInTheDocument();
  });

  it("keeps an unknown member count unknown and blocks writes while reads are degraded", async () => {
    const alpha = project("ALPHA", "Alpha项目", "进行中", null);
    fetchProjectsMock.mockResolvedValue(projectsResponse([alpha], false, true));

    render(<ReplicaProjectWorkbench />);
    fireEvent.click(await screen.findByRole("button", { name: "查看：Alpha项目" }));
    await screen.findByText("ALPHA-M1-account");

    expect(within(screen.getByRole("row", { name: /Alpha项目/ })).getByText("待同步")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "新增成员" })).toBeDisabled();
    expect(createProjectMemberMock).not.toHaveBeenCalled();
  });

  it("disables member creation when project reads work but persistent writes are unavailable", async () => {
    const alpha = project("ALPHA", "Alpha项目");
    const response = projectsResponse([alpha]);
    fetchProjectsMock.mockResolvedValue({
      ...response,
      store: {
        ...response.store,
        persistent_writes_ready: false
      }
    } as ProjectsResponse);

    render(<ReplicaProjectWorkbench />);
    fireEvent.click(await screen.findByRole("button", { name: "查看：Alpha项目" }));
    await screen.findByText("ALPHA-M1-account");

    expect(screen.getByText("项目持久化写入未就绪，暂不能新增成员")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "新增成员" })).toBeDisabled();
  });

  it("submits the semantic member form exactly once during synchronous duplicate submits", async () => {
    const alpha = project("ALPHA", "Alpha项目");
    const pendingCreate = deferred<Awaited<ReturnType<typeof createProjectMember>>>();
    createProjectMemberMock.mockReturnValue(pendingCreate.promise);

    render(<ReplicaProjectWorkbench />);
    fireEvent.click(await screen.findByRole("button", { name: "查看：Alpha项目" }));
    await screen.findByText("ALPHA-M1-account");
    fireEvent.change(screen.getByRole("textbox", { name: "账号" }), { target: { value: "auditor-li" } });
    fireEvent.change(screen.getByRole("textbox", { name: "姓名" }), { target: { value: "李审计" } });
    fireEvent.change(screen.getByRole("textbox", { name: "部门" }), { target: { value: "医保办" } });

    const form = screen.getByRole("form", { name: "新增项目成员" });
    expect(screen.getByRole("button", { name: "新增成员" })).toHaveAttribute("type", "submit");
    fireEvent.submit(form);
    fireEvent.submit(form);

    expect(createProjectMemberMock).toHaveBeenCalledTimes(1);
    await act(async () => {
      pendingCreate.resolve({
        item: member("NEW-LI", alpha.id, "李审计", "auditor-li"),
        store: { ready: true, backend: "SqlAlchemyProjectMemberStore" }
      });
      await Promise.resolve();
    });
  });

  it("clears pending member-save state when switching projects and ignores the stale POST", async () => {
    const alpha = project("ALPHA", "Alpha项目", "进行中", 1);
    const beta = project("BETA", "Beta项目", "进行中", 1);
    const pendingCreate = deferred<Awaited<ReturnType<typeof createProjectMember>>>();
    fetchProjectsMock.mockResolvedValue(projectsResponse([alpha, beta]));
    fetchProjectMembersMock.mockImplementation((projectId) => Promise.resolve(
      membersResponse(projectId, [member(`${projectId}-M1`, projectId, `${projectId}成员`)])
    ));
    fetchProjectDashboardMock.mockImplementation((projectId) => Promise.resolve(
      dashboardResponse(projectId === alpha.id ? alpha : beta)
    ));
    createProjectMemberMock.mockReturnValue(pendingCreate.promise);

    render(<ReplicaProjectWorkbench />);
    fireEvent.click(await screen.findByRole("button", { name: "查看：Alpha项目" }));
    await screen.findByText("ALPHA-M1-account");
    fireEvent.change(screen.getByRole("textbox", { name: "账号" }), { target: { value: "late-account" } });
    fireEvent.change(screen.getByRole("textbox", { name: "姓名" }), { target: { value: "迟到成员" } });
    fireEvent.change(screen.getByRole("textbox", { name: "部门" }), { target: { value: "内审部" } });
    fireEvent.click(screen.getByRole("button", { name: "新增成员" }));
    expect(await screen.findByRole("button", { name: "新增中" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "查看：Beta项目" }));
    expect(await screen.findByRole("heading", { name: "项目详情：Beta项目" })).toBeInTheDocument();
    expect(await screen.findByText("BETA-M1-account")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "新增成员" })).toBeEnabled();

    await act(async () => {
      pendingCreate.resolve({
        item: member("ALPHA-LATE", alpha.id, "迟到成员", "late-account"),
        store: { ready: true, backend: "SqlAlchemyProjectMemberStore" }
      });
      await Promise.resolve();
    });

    expect(screen.queryByText("late-account")).not.toBeInTheDocument();
    expect(within(screen.getByRole("row", { name: /Alpha项目/ })).getByText("1")).toBeInTheDocument();
    expect(within(screen.getByRole("row", { name: /Beta项目/ })).getByText("1")).toBeInTheDocument();
  });

  it("keeps project details readable but hides enabled member creation for a read-only member", async () => {
    window.localStorage.setItem(AUDIT_ROLE_STORAGE_KEY, "member");
    renderWithUser();

    expect(await screen.findByText("当前显示：我创建或参与的项目")).toBeInTheDocument();
    fireEvent.click(await screen.findByRole("button", { name: "查看：Alpha项目" }));
    expect(await screen.findByText("ALPHA-M1-account")).toBeInTheDocument();
    expect(screen.getByText("当前角色仅可查看项目成员")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "新增成员" })).not.toBeInTheDocument();
    expect(screen.queryByRole("form", { name: "新建项目" })).not.toBeInTheDocument();
  });

  it("reloads role-scoped projects and clears the previous role selection", async () => {
    const alpha = project("ALPHA", "Alpha项目");
    const beta = project("BETA", "Beta项目");
    fetchProjectsMock
      .mockResolvedValueOnce(projectsResponse([alpha]))
      .mockResolvedValueOnce(projectsResponse([beta]));
    renderWithUser();

    fireEvent.click(await screen.findByRole("button", { name: "查看：Alpha项目" }));
    expect(await screen.findByRole("heading", { name: "项目详情：Alpha项目" })).toBeInTheDocument();

    act(() => writeAuditClientRole("member"));

    expect(await screen.findByText("当前显示：我创建或参与的项目")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "项目详情：Alpha项目" })).not.toBeInTheDocument();
    expect(await screen.findByText("Beta项目")).toBeInTheDocument();
    expect(screen.queryByText("Alpha项目")).not.toBeInTheDocument();
    expect(fetchProjectsMock).toHaveBeenCalledTimes(2);
  });
});
