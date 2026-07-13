import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import ProjectsPage from "./page";

vi.mock("@/lib/api-client", () => ({
  createProjectMember: vi.fn(),
  fetchProjectDashboard: vi.fn(),
  fetchProjectMembers: vi.fn(),
  fetchProjects: vi.fn(() => new Promise(() => undefined))
}));

describe("ProjectsPage", () => {
  it("mounts the project collaboration workbench instead of the preview", () => {
    render(<ProjectsPage />);

    expect(screen.getByRole("heading", { name: "项目协作工作台" })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "项目状态" })).toBeInTheDocument();
    expect(screen.queryByText("内测中")).not.toBeInTheDocument();
  });
});
