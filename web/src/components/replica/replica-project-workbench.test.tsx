import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AuditUserProvider } from "@/components/shell/audit-user-context";
import {
  createProjectMember,
  fetchProjectDashboard,
  fetchProjectMembers,
  fetchProjects
} from "@/lib/api-client";
import type {
  ApiProjectStatus,
  ProjectDashboardResponse,
  ProjectMemberApiItem,
  ProjectMembersResponse,
  ProjectsResponse,
  ProjectSummaryApiItem
} from "@/lib/api-types";
import { AUDIT_ROLE_STORAGE_KEY, writeAuditClientRole } from "@/lib/audit-user";

import { ReplicaProjectWorkbench } from "./replica-project-workbench";

vi.mock("@/lib/api-client", () => ({
  createProjectMember: vi.fn(),
  fetchProjectDashboard: vi.fn(),
  fetchProjectMembers: vi.fn(),
  fetchProjects: vi.fn()
}));

const fetchProjectsMock = vi.mocked(fetchProjects);
const fetchProjectMembersMock = vi.mocked(fetchProjectMembers);
const fetchProjectDashboardMock = vi.mocked(fetchProjectDashboard);
const createProjectMemberMock = vi.mocked(createProjectMember);

const projectStatuses: readonly ApiProjectStatus[] = ["待开始", "进行中", "已完成", "已归档"];

function project(
  id: string,
  name: string,
  status: ApiProjectStatus = "进行中",
  memberCount = 1
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
  ready = true
): ProjectsResponse {
  return {
    items,
    roles: ["项目负责人", "审计员", "业务专家", "信息科", "只读观察员"],
    statuses: ["在项目中", "待确认"],
    project_statuses: projectStatuses,
    store: { ready, backend: ready ? "SqlAlchemyProjectMemberStore" : "unavailable" }
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
  const alpha = project("ALPHA", "Alpha项目", "进行中", 1);
  fetchProjectsMock.mockResolvedValue(projectsResponse([alpha]));
  fetchProjectMembersMock.mockResolvedValue(membersResponse(alpha.id, [member("ALPHA-M1", alpha.id, "张审计")]));
  fetchProjectDashboardMock.mockResolvedValue(dashboardResponse(alpha));
  createProjectMemberMock.mockRejectedValue(new Error("not configured"));
});

describe("ReplicaProjectWorkbench", () => {
  it("renders the API project list, canonical status filter and truthful zero", async () => {
    const alpha = project("ALPHA", "Alpha项目", "进行中", 2);
    const done = project("DONE", "已完成项目", "已完成", 0);
    fetchProjectsMock.mockResolvedValue(projectsResponse([alpha, done]));

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
    expect(await screen.findByText("项目列表读取失败")).toBeInTheDocument();
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
    });
    expect(await screen.findByRole("heading", { name: "项目详情：Alpha项目" })).toBeInTheDocument();
    expect(screen.getByText("ALPHA-M1-account")).toBeInTheDocument();
    expect(screen.getByText("待处理疑点")).toBeInTheDocument();
    expect(screen.getByText("Alpha项目复核任务")).toBeInTheDocument();
    expect(screen.getByText("Alpha项目同步完成")).toBeInTheDocument();
    expect(screen.getByText("live-db-connected")).toBeInTheDocument();
    expect(screen.getByText("SqlAlchemyProjectMemberStore / SqlAlchemyAuditFindingStore")).toBeInTheDocument();
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
    expect(await screen.findByText("项目成员读取失败")).toBeInTheDocument();
    expect(screen.getByText("项目驾驶舱读取失败")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "重试项目成员" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "重试项目驾驶舱" })).toBeInTheDocument();
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
