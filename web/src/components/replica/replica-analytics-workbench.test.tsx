import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { fetchAnalysisUploadHistory, uploadAnalysisTable } from "@/lib/api-client";
import type {
  TableAnalysisUploadHistoryResponse,
  TableAnalysisUploadResponse
} from "@/lib/api-types";

import { ReplicaAnalyticsWorkbench } from "./replica-analytics-workbench";

vi.mock("@/lib/api-client", () => ({
  fetchAnalysisUploadHistory: vi.fn(),
  uploadAnalysisTable: vi.fn()
}));

const fetchHistoryMock = vi.mocked(fetchAnalysisUploadHistory);
const uploadMock = vi.mocked(uploadAnalysisTable);

const historyReady: TableAnalysisUploadHistoryResponse = {
  items: [
    {
      id: "upload-history-1",
      name: "历史收费.csv",
      analysis_case: "audit-data",
      analysis_case_label: "审计数据分析",
      extension: "csv",
      size_bytes: 0,
      size_kb: 0,
      sha256: "b".repeat(64),
      sheet_name: null,
      row_count: 0,
      column_count: 0,
      empty_cell_count: 0,
      duplicate_row_count: 0,
      status: "parsed",
      created_by: "next-admin",
      created_at: "2026-07-12T08:00:00Z",
      retention_status: "retained",
      audit_signals: []
    }
  ],
  store: { ready: true, backend: "SqlAlchemyAnalyticsUploadStore" }
};

const uploadResult: TableAnalysisUploadResponse = {
  name: "本次收费.xlsx",
  analysis_case: "audit-data",
  analysis_case_label: "审计数据分析",
  case_status: "completed",
  case_metrics: [
    {
      key: "row_count",
      label: "数据行数",
      value: 2,
      display_value: "2 行",
      formula: null,
      status: "available"
    },
    {
      key: "duplicate_row_count",
      label: "完全重复记录",
      value: 1,
      display_value: "1 条",
      formula: null,
      status: "available"
    }
  ],
  case_findings: ["发现 1 条完全重复记录，建议优先核对。"],
  size_kb: 0,
  extension: "xlsx",
  status: "parsed",
  sheet_name: "收费明细",
  columns: [
    {
      name: "金额",
      type: "数值",
      empty_count: 0,
      unique_count: 2,
      sample_values: ["0", "128.50"],
      audit_hint: "可用于费用异常核验。"
    }
  ],
  row_count: 2,
  empty_cell_count: 0,
  duplicate_row_count: 1,
  message: "已完成表格字段画像。",
  quality_findings: ["未发现空值单元。"],
  audit_signals: ["金额/费用字段"],
  recommendations: ["进入重复收费核验。"],
  upload_id: "upload-current-1",
  sha256: "a".repeat(64),
  retention_status: "retained",
  created_at: "2026-07-12T09:00:00Z"
};

const dupontResult: TableAnalysisUploadResponse = {
  ...uploadResult,
  name: "财务杜邦分析案例.csv",
  analysis_case: "dupont",
  analysis_case_label: "财务杜邦分析",
  case_metrics: [
    {
      key: "net_profit_margin",
      label: "销售净利率",
      value: 0.1,
      display_value: "10.00%",
      formula: "净利润 ÷ 营业收入",
      status: "available"
    },
    {
      key: "return_on_equity",
      label: "净资产收益率",
      value: 0.125,
      display_value: "12.50%",
      formula: "销售净利率 × 总资产周转率 × 权益乘数",
      status: "available"
    }
  ],
  case_findings: ["2025年的净资产收益率为 12.50%。"]
};

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

function chooseFile(name = "本次收费.xlsx") {
  const input = screen.getByLabelText("选择分析表格") as HTMLInputElement;
  const file = new File(["amount\n0"], name, {
    type: name.endsWith(".csv")
      ? "text/csv"
      : "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
  });
  fireEvent.change(input, { target: { files: [file] } });
  return { input, file };
}

describe("ReplicaAnalyticsWorkbench", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  beforeEach(() => {
    fetchHistoryMock.mockReset();
    uploadMock.mockReset();
    fetchHistoryMock.mockResolvedValue(historyReady);
    uploadMock.mockResolvedValue(uploadResult);
  });

  it("leads with two executable audit cases and keeps technical boundaries collapsed", async () => {
    render(<ReplicaAnalyticsWorkbench />);

    expect(screen.getByRole("heading", { name: /选择一个审计案例/ })).toBeInTheDocument();
    const cases = screen.getByRole("radiogroup", { name: "分析案例" });
    expect(within(cases).getByRole("radio", { name: /审计数据分析/ })).toHaveAttribute(
      "aria-checked",
      "true"
    );
    expect(within(cases).getByRole("radio", { name: /财务杜邦分析/ })).toHaveAttribute(
      "aria-checked",
      "false"
    );
    expect(screen.getAllByText(/建议包含患者\/对象/)).toHaveLength(2);
    expect(screen.getByText("provider_call=false").closest("details")).not.toBeNull();
    expect(screen.getByText("浏览本地文件")).toBeInTheDocument();
    expect(screen.getByLabelText("选择分析表格")).toHaveClass("replica-analytics-file-input");
    expect(screen.queryByText(/analytics store ready/)).not.toBeInTheDocument();
    expect(uploadMock).not.toHaveBeenCalled();
    await waitFor(() => expect(fetchHistoryMock).toHaveBeenCalledTimes(1));
  });

  it("removes upload and history controls from the production shell", async () => {
    vi.stubEnv("NEXT_PUBLIC_MEDICAL_AUDIT_API_ACCESS_MODE", "public-shell-readonly");

    render(<ReplicaAnalyticsWorkbench />);

    expect(await screen.findByText(/表格上传、分析记录读取和业务写入均不开放/)).toBeInTheDocument();
    expect(fetchHistoryMock).not.toHaveBeenCalled();
    expect(uploadMock).not.toHaveBeenCalled();
    expect(screen.queryByLabelText("选择分析表格")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /载入.*案例/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /开始.*分析/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "刷新" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "重试" })).not.toBeInTheDocument();
  });

  it("loads and executes the DuPont example exactly once", async () => {
    const pendingUpload = deferred<TableAnalysisUploadResponse>();
    uploadMock.mockReturnValue(pendingUpload.promise);
    render(<ReplicaAnalyticsWorkbench />);

    fireEvent.click(screen.getByRole("radio", { name: /财务杜邦分析/ }));
    expect(screen.getAllByText(/必需字段：净利润、营业收入/)).toHaveLength(2);
    fireEvent.click(screen.getByRole("button", { name: "载入财务杜邦分析案例" }));
    expect(screen.getByText("已选择：财务杜邦分析案例.csv（尚未提交）")).toBeInTheDocument();

    const submit = screen.getByRole("button", { name: "开始财务杜邦分析" });
    fireEvent.click(submit);
    fireEvent.click(submit);
    expect(uploadMock).toHaveBeenCalledTimes(1);
    expect(uploadMock.mock.calls[0][0].name).toBe("财务杜邦分析案例.csv");
    expect(uploadMock.mock.calls[0][1]).toBe("dupont");
    expect(screen.getByLabelText("选择分析表格")).toBeDisabled();

    await act(async () => pendingUpload.resolve(dupontResult));

    const result = await screen.findByRole("region", { name: "本次分析结果" });
    expect(within(result).getByRole("heading", { name: "财务杜邦分析结果" })).toBeInTheDocument();
    expect(within(result).getByText("10.00%")).toBeInTheDocument();
    expect(within(result).getByText("12.50%")).toBeInTheDocument();
    expect(within(result).getByText(/净利润 ÷ 营业收入/)).toBeInTheDocument();
    expect(within(result).getByText(/2025年的净资产收益率/)).toBeInTheDocument();
    await waitFor(() => expect(fetchHistoryMock).toHaveBeenCalledTimes(2));
  });

  it("renders audit conclusions first and keeps field and record internals in details", async () => {
    render(<ReplicaAnalyticsWorkbench />);
    const { file } = chooseFile();
    fireEvent.click(screen.getByRole("button", { name: "开始审计数据分析" }));

    expect(uploadMock).toHaveBeenCalledWith(file, "audit-data");
    const result = await screen.findByRole("region", { name: "本次分析结果" });
    expect(within(result).getByText("2 行")).toBeInTheDocument();
    expect(within(result).getByText("1 条")).toBeInTheDocument();
    expect(within(result).getByText(/发现 1 条完全重复记录/)).toBeInTheDocument();
    expect(within(result).getByText("查看字段识别与数据质量").closest("details")).not.toBeNull();
    expect(within(result).getByText("管理与审计详情").closest("details")).not.toBeNull();
    expect(within(result).getByText("upload-current-1")).toBeInTheDocument();
    expect(within(result).getByText("a".repeat(64))).toBeInTheDocument();
    expect(within(result).getByText("外部模型调用").nextElementSibling).toHaveTextContent("否");
  });

  it("clears evidence when the case or selected file changes", async () => {
    render(<ReplicaAnalyticsWorkbench />);
    chooseFile("文件A.xlsx");
    fireEvent.click(screen.getByRole("button", { name: "开始审计数据分析" }));
    expect(await screen.findByRole("region", { name: "本次分析结果" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("radio", { name: /财务杜邦分析/ }));
    expect(screen.queryByRole("region", { name: "本次分析结果" })).not.toBeInTheDocument();
    expect(screen.getByText("尚未选择文件")).toBeInTheDocument();

    chooseFile("文件B.csv");
    expect(screen.getByText("已选择：文件B.csv（尚未提交）")).toBeInTheDocument();
    expect(uploadMock).toHaveBeenCalledTimes(1);
  });

  it("keeps a successful result when the independent history refresh fails", async () => {
    fetchHistoryMock
      .mockResolvedValueOnce(historyReady)
      .mockRejectedValueOnce(new Error("history refresh failed"));
    render(<ReplicaAnalyticsWorkbench />);
    chooseFile();
    fireEvent.click(screen.getByRole("button", { name: "开始审计数据分析" }));

    expect(await screen.findByRole("region", { name: "本次分析结果" })).toHaveTextContent(
      "审计数据分析结果"
    );
    expect(await screen.findByText("分析记录读取失败")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "本次分析结果" })).toHaveTextContent("分析完成");
  });

  it("states when analysis was not retained and never invents results after failure", async () => {
    uploadMock
      .mockResolvedValueOnce({
        ...uploadResult,
        upload_id: null,
        sha256: null,
        retention_status: "not-configured",
        created_at: null
      })
      .mockRejectedValueOnce(new Error("uploaded table file is too large"));
    render(<ReplicaAnalyticsWorkbench />);
    chooseFile("临时.csv");
    fireEvent.click(screen.getByRole("button", { name: "开始审计数据分析" }));

    expect(await screen.findByText("分析记录存储未配置，本次结果未保留。")).toBeInTheDocument();

    chooseFile("超大.csv");
    fireEvent.click(screen.getByRole("button", { name: "开始审计数据分析" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("uploaded table file is too large");
    expect(screen.queryByRole("region", { name: "本次分析结果" })).not.toBeInTheDocument();
  });

  it("keeps history useful for auditors while placing implementation fields in details", async () => {
    fetchHistoryMock
      .mockResolvedValueOnce(historyReady)
      .mockResolvedValueOnce({ ...historyReady, store: { ready: false, backend: "none" } })
      .mockRejectedValueOnce(new Error("history unavailable"))
      .mockResolvedValueOnce({
        items: [],
        store: { ready: true, backend: "SqlAlchemyAnalyticsUploadStore" }
      });
    render(<ReplicaAnalyticsWorkbench />);

    const history = await screen.findByRole("region", { name: "分析记录" });
    const historyItem = within(history).getByRole("article", { name: "历史收费.csv" });
    expect(within(historyItem).getByText("审计数据分析")).toBeInTheDocument();
    expect(within(historyItem).getByText("2026-07-12 · 0 行数据")).toBeInTheDocument();
    expect(within(historyItem).getByText("管理信息").closest("details")).not.toBeNull();
    expect(within(historyItem).getByText("upload-history-1")).toBeInTheDocument();
    expect(within(historyItem).getByText("bbbbbbbbbbbb…bbbbbb")).toBeInTheDocument();
    expect(within(history).getByText("记录服务状态").closest("details")).not.toBeNull();

    fireEvent.click(within(history).getByRole("button", { name: "刷新" }));
    expect(await within(history).findByText("分析记录暂不可用")).toBeInTheDocument();

    fireEvent.click(within(history).getByRole("button", { name: "刷新" }));
    expect(await within(history).findByText("分析记录读取失败")).toBeInTheDocument();
    fireEvent.click(within(history).getByRole("button", { name: "重试" }));
    expect(await within(history).findByText("当前没有分析记录")).toBeInTheDocument();
  });

  it("ignores an older history request that settles after a retry", async () => {
    const first = deferred<TableAnalysisUploadHistoryResponse>();
    fetchHistoryMock.mockReturnValueOnce(first.promise).mockResolvedValueOnce(historyReady);
    render(<ReplicaAnalyticsWorkbench />);

    fireEvent.click(screen.getByRole("button", { name: "刷新" }));
    expect(await screen.findByText("历史收费.csv")).toBeInTheDocument();
    await act(async () => first.resolve({ items: [], store: { ready: true, backend: "old" } }));
    expect(screen.getByText("历史收费.csv")).toBeInTheDocument();
    expect(screen.queryByText("当前没有分析记录")).not.toBeInTheDocument();
  });

  it("routes results into source review and report delivery", async () => {
    render(<ReplicaAnalyticsWorkbench />);

    expect(screen.getByRole("link", { name: "核对原始文档" })).toHaveAttribute(
      "href",
      "/documents"
    );
    expect(screen.getByRole("link", { name: "形成报告与底稿" })).toHaveAttribute(
      "href",
      "/reports"
    );
    await waitFor(() => expect(fetchHistoryMock).toHaveBeenCalledTimes(1));
  });
});
