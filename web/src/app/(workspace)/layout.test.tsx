import { act, fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  fetchProjectDashboard,
  fetchProjectFiles,
  fetchProjectMembers,
  fetchProjects
} from "@/lib/api-client";
import type {
  ProjectDashboardResponse,
  ProjectMembersResponse,
  ProjectsResponse
} from "@/lib/api-types";
import { AUDIT_ROLE_STORAGE_KEY, writeAuditClientRole } from "@/lib/audit-user";

import WorkspaceLayout from "./layout";
import ProjectsPage from "./projects/page";

vi.mock("@/components/replica/replica-shell", () => ({
  ReplicaShell: ({ children }: { readonly children: ReactNode }) => <>{children}</>
}));

vi.mock("@/components/shell/workspace-auth-gate", () => ({
  WorkspaceAuthGate: ({ children }: { readonly children: ReactNode }) => <>{children}</>
}));

vi.mock("@/lib/api-client", () => ({
  createProjectMember: vi.fn(),
  fetchProjectDashboard: vi.fn(),
  fetchProjectFiles: vi.fn(),
  fetchProjectMembers: vi.fn(),
  fetchProjects: vi.fn()
}));

const fetchProjectsMock = vi.mocked(fetchProjects);
const fetchProjectMembersMock = vi.mocked(fetchProjectMembers);
const fetchProjectDashboardMock = vi.mocked(fetchProjectDashboard);
const fetchProjectFilesMock = vi.mocked(fetchProjectFiles);

const project = {
  id: "ROLE-PROJECT",
  name: "角色隔离项目",
  audit_topic: "医保基金监管",
  organization_name: "测试医院",
  member_count: 1,
  creator: "项目负责人",
  creator_user_identifier: "next-director",
  created_at: "2026-07-12T08:00:00Z",
  status: "进行中",
  operation_label: "进入项目",
  source: "system-default"
} as const;

const projectsResponse: ProjectsResponse = {
  items: [project],
  roles: ["项目负责人", "审计员", "业务专家", "信息科", "只读观察员"],
  statuses: ["在项目中", "待确认"],
  project_statuses: ["待开始", "进行中", "已完成", "已归档"],
  store: { ready: true, backend: "SqlAlchemyProjectMemberStore" }
};

const membersResponse: ProjectMembersResponse = {
  items: [],
  project_key: project.id,
  roles: projectsResponse.roles,
  statuses: projectsResponse.statuses,
  store: { ready: true, backend: "SqlAlchemyProjectMemberStore" }
};

const dashboardResponse: ProjectDashboardResponse = {
  format: "project-dashboard-v1",
  project,
  metrics: [],
  queue: [],
  activities: [],
  status_distribution: [],
  member_workloads: [],
  evidence_grade: "live-db-connected",
  production_side_effect: "none",
  store: {
    ready: true,
    project_members_ready: true,
    audit_findings_ready: true,
    status: "ready",
    backend: {
      project_members: "SqlAlchemyProjectMemberStore",
      audit_findings: "SqlAlchemyAuditFindingStore"
    }
  }
};

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
  window.localStorage.setItem(AUDIT_ROLE_STORAGE_KEY, "member");
  fetchProjectsMock.mockResolvedValue(projectsResponse);
  fetchProjectMembersMock.mockResolvedValue(membersResponse);
  fetchProjectDashboardMock.mockResolvedValue(dashboardResponse);
  fetchProjectFilesMock.mockResolvedValue({
    contract_version: "project-files-v2",
    project_key: project.id,
    items: [],
    store: { ready: true, backend: "InMemoryDocumentUploadStore" },
    permissions: {
      can_upload: true,
      can_review: false,
      can_withdraw_own: true,
      visibility_scope: "own"
    }
  });
});

describe("WorkspaceLayout role integration", () => {
  it("provides the stored non-admin role to a real workspace page and responds to role changes", async () => {
    render(
      <WorkspaceLayout>
        <ProjectsPage />
      </WorkspaceLayout>
    );

    expect(await screen.findByText("当前显示：我创建或参与的项目")).toBeInTheDocument();
    fireEvent.click(await screen.findByRole("button", { name: "查看：角色隔离项目" }));
    expect(await screen.findByRole("heading", { name: "项目详情：角色隔离项目" })).toBeInTheDocument();
    expect(screen.getByText("当前角色仅可查看项目成员")).toBeInTheDocument();
    expect(screen.queryByRole("form", { name: "新增项目成员" })).not.toBeInTheDocument();

    act(() => writeAuditClientRole("admin"));

    expect(await screen.findByText("当前显示：全部项目")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "项目详情：角色隔离项目" })).not.toBeInTheDocument();
    fireEvent.click(await screen.findByRole("button", { name: "查看：角色隔离项目" }));
    expect(await screen.findByRole("form", { name: "新增项目成员" })).toBeInTheDocument();
  });
});
