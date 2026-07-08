import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import ProjectsPage from "./page";

describe("ProjectsPage", () => {
  it("renders a clear preview state instead of unfinished cockpit metrics", () => {
    render(<ProjectsPage />);

    expect(screen.getByRole("heading", { name: "项目管理" })).toBeInTheDocument();
    expect(screen.getByText("内测中")).toBeInTheDocument();
    expect(screen.getByLabelText("项目管理开通说明")).toBeInTheDocument();
    expect(screen.getByText("审计专题列表")).toBeInTheDocument();
    expect(screen.getByText("成员权限")).toBeInTheDocument();
    expect(screen.getByText("任务状态")).toBeInTheDocument();
  });
});
