import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import AnalyticsPage from "./page";

vi.mock("@/lib/api-client", () => ({
  fetchAnalysisUploadHistory: vi.fn(() => new Promise(() => undefined)),
  uploadAnalysisTable: vi.fn()
}));

describe("AnalyticsPage", () => {
  it("mounts the simplified case-led analytics workbench instead of the preview", () => {
    render(<AnalyticsPage />);

    expect(screen.getByRole("heading", {
      name: "选择一个审计案例，上传数据即可得到可复核结果"
    })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /审计数据分析/ })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /财务杜邦分析/ })).toBeInTheDocument();
    expect(screen.getByLabelText("选择分析表格")).toHaveAttribute("accept", ".xlsx,.csv");
    expect(screen.queryByText("内测中")).not.toBeInTheDocument();
    expect(screen.queryByText("参考数据集")).not.toBeInTheDocument();
  });
});
