import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

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
  duplicate_row_count: 0,
  message: "后端已完成表格字段画像。",
  quality_findings: ["未发现空值单元。"],
  audit_signals: ["金额/费用字段"],
  recommendations: ["进入重复收费核验。"],
  upload_id: "upload-current-1",
  sha256: "a".repeat(64),
  retention_status: "retained",
  created_at: "2026-07-12T09:00:00Z"
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

function expectDefinition(
  scope: HTMLElement,
  term: string,
  value: string
) {
  const definitionTerm = within(scope).getByText(term, { selector: "dt" });
  expect(definitionTerm.nextElementSibling).toHaveTextContent(value);
}

describe("ReplicaAnalyticsWorkbench", () => {
  beforeEach(() => {
    fetchHistoryMock.mockReset();
    uploadMock.mockReset();
    fetchHistoryMock.mockResolvedValue(historyReady);
    uploadMock.mockResolvedValue(uploadResult);
  });

  it("records an accepted file without uploading and explains the controlled-write boundary", async () => {
    render(<ReplicaAnalyticsWorkbench />);

    const { input, file } = chooseFile();

    expect(input).toHaveAttribute("accept", ".xlsx,.csv");
    expect(screen.getByText(`已选择：${file.name}（尚未上传）`)).toBeInTheDocument();
    expect(uploadMock).not.toHaveBeenCalled();
    expect(screen.getByText(/上传是受控写入/)).toBeInTheDocument();
    expect(screen.getByText(/analytics store ready/)).toBeInTheDocument();
    expect(screen.getByText(/当前分析不调用外部模型/)).toBeInTheDocument();
    expect(screen.getByText("provider_call=false").closest("details")).not.toBeNull();
    expect(screen.queryByRole("button", { name: /OCR/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /OCR/i })).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/OCR/i)).not.toBeInTheDocument();
    expect(document.querySelector('input[id*="ocr" i], input[name*="ocr" i]')).toBeNull();
    await waitFor(() => expect(fetchHistoryMock).toHaveBeenCalledTimes(1));
  });

  it("submits exactly once and renders the complete backend profile before refreshing history", async () => {
    const pendingUpload = deferred<TableAnalysisUploadResponse>();
    uploadMock.mockReturnValue(pendingUpload.promise);
    render(<ReplicaAnalyticsWorkbench />);
    const { file } = chooseFile();

    const submit = screen.getByRole("button", { name: "上传并分析" });
    fireEvent.click(submit);
    fireEvent.click(submit);
    expect(uploadMock).toHaveBeenCalledTimes(1);
    expect(uploadMock).toHaveBeenCalledWith(file);
    expect(screen.getByLabelText("选择分析表格")).toBeDisabled();

    await act(async () => pendingUpload.resolve(uploadResult));

    const result = await screen.findByRole("region", { name: "本次分析结果" });
    for (const text of [
      "本次收费.xlsx",
      "收费明细",
      "金额",
      "数值",
      "可用于费用异常核验。",
      "后端已完成表格字段画像。",
      "未发现空值单元。",
      "金额/费用字段",
      "进入重复收费核验。",
      "upload-current-1",
      "a".repeat(64),
      "2026-07-12T09:00:00Z"
    ]) {
      expect(within(result).getByText(text)).toBeInTheDocument();
    }
    expectDefinition(result, "文件大小", "0 KB");
    expectDefinition(result, "扩展名", "xlsx");
    expectDefinition(result, "解析状态", "parsed");
    expectDefinition(result, "数据行", "2");
    expectDefinition(result, "空单元格", "0");
    expectDefinition(result, "重复行", "0");
    const columnRow = within(result).getByRole("row", { name: /金额/ });
    const columnCells = within(columnRow).getAllByRole("cell");
    expect(columnCells[2]).toHaveTextContent("0");
    expect(columnCells[3]).toHaveTextContent("2");
    expect(columnCells[4]).toHaveTextContent("128.50");
    expectDefinition(result, "retention_status", "retained");
    expect(within(result).getByText("已保留分析文件和结果记录。")).toBeInTheDocument();
    await waitFor(() => expect(fetchHistoryMock).toHaveBeenCalledTimes(2));
  });

  it("keeps a successful upload result when the independent history refresh fails", async () => {
    fetchHistoryMock
      .mockResolvedValueOnce(historyReady)
      .mockRejectedValueOnce(new Error("history refresh failed"));
    render(<ReplicaAnalyticsWorkbench />);
    chooseFile();
    fireEvent.click(screen.getByRole("button", { name: "上传并分析" }));

    expect(await screen.findByRole("region", { name: "本次分析结果" })).toHaveTextContent(
      "本次收费.xlsx"
    );
    expect(await screen.findByText("分析历史读取失败")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "本次分析结果" })).toHaveTextContent(
      "已保留分析文件和结果记录。"
    );
  });

  it("clears evidence from file A as soon as file B is selected without uploading B", async () => {
    render(<ReplicaAnalyticsWorkbench />);
    chooseFile("文件A.xlsx");
    fireEvent.click(screen.getByRole("button", { name: "上传并分析" }));
    expect(await screen.findByRole("region", { name: "本次分析结果" })).toHaveTextContent(
      "本次收费.xlsx"
    );

    chooseFile("文件B.csv");

    expect(screen.getByText("已选择：文件B.csv（尚未上传）")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "本次分析结果" })).not.toBeInTheDocument();
    expect(uploadMock).toHaveBeenCalledTimes(1);
  });

  it("states when an analysis was not retained and never invents a profile after upload failure", async () => {
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
    fireEvent.click(screen.getByRole("button", { name: "上传并分析" }));

    expect(await screen.findByText("未配置 analytics store，本次分析未保留。")).toBeInTheDocument();

    chooseFile("超大.csv");
    fireEvent.click(screen.getByRole("button", { name: "上传并分析" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("uploaded table file is too large");
    expect(screen.queryByRole("region", { name: "本次分析结果" })).not.toBeInTheDocument();
  });

  it("separates history ready, zero values, degraded, empty, error and retry states", async () => {
    fetchHistoryMock
      .mockResolvedValueOnce(historyReady)
      .mockResolvedValueOnce({ ...historyReady, store: { ready: false, backend: "none" } })
      .mockRejectedValueOnce(new Error("history unavailable"))
      .mockResolvedValueOnce({
        items: [],
        store: { ready: true, backend: "SqlAlchemyAnalyticsUploadStore" }
      });
    render(<ReplicaAnalyticsWorkbench />);

    const history = await screen.findByRole("region", { name: "分析历史" });
    expect(within(history).getByText("历史收费.csv")).toBeInTheDocument();
    expect(within(history).getByText("SqlAlchemyAnalyticsUploadStore")).toBeInTheDocument();
    const historyItem = within(history).getByRole("article", { name: "历史收费.csv" });
    expectDefinition(historyItem, "记录 ID", "upload-history-1");
    expectDefinition(historyItem, "原始字节", "0");
    expectDefinition(historyItem, "文件大小", "0 KB");
    expectDefinition(historyItem, "数据行", "0");
    expectDefinition(historyItem, "字段数", "0");
    expectDefinition(historyItem, "空单元格", "0");
    expectDefinition(historyItem, "重复行", "0");
    expectDefinition(historyItem, "分析状态", "parsed");
    expectDefinition(historyItem, "保留状态", "retained");
    expect(within(historyItem).queryByText("next-admin")).not.toBeInTheDocument();
    expect(within(historyItem).queryByText("b".repeat(64))).not.toBeInTheDocument();
    expectDefinition(historyItem, "sha256（截断）", "bbbbbbbbbbbb…bbbbbb");

    fireEvent.click(within(history).getByRole("button", { name: "刷新历史" }));
    expect(await within(history).findByText("历史存储未就绪")).toBeInTheDocument();
    expect(within(history).getByText("历史收费.csv")).toBeInTheDocument();
    expect(within(history).getByText("none")).toBeInTheDocument();

    fireEvent.click(within(history).getByRole("button", { name: "刷新历史" }));
    expect(await within(history).findByText("分析历史读取失败")).toBeInTheDocument();
    expect(within(history).queryByText("历史收费.csv")).not.toBeInTheDocument();
    fireEvent.click(within(history).getByRole("button", { name: "重试读取历史" }));
    expect(await within(history).findByText("当前没有保留的分析记录")).toBeInTheDocument();
  });

  it("ignores an older history request that settles after a retry", async () => {
    const first = deferred<TableAnalysisUploadHistoryResponse>();
    fetchHistoryMock.mockReturnValueOnce(first.promise).mockResolvedValueOnce(historyReady);
    render(<ReplicaAnalyticsWorkbench />);

    fireEvent.click(screen.getByRole("button", { name: "刷新历史" }));
    expect(await screen.findByText("历史收费.csv")).toBeInTheDocument();
    await act(async () => first.resolve({ items: [], store: { ready: true, backend: "old" } }));
    expect(screen.getByText("历史收费.csv")).toBeInTheDocument();
    expect(screen.queryByText("当前没有保留的分析记录")).not.toBeInTheDocument();
  });

  it("links document follow-up only to the existing document and chat surfaces", async () => {
    render(<ReplicaAnalyticsWorkbench />);

    expect(screen.getByRole("link", { name: "前往文档" })).toHaveAttribute("href", "/documents");
    expect(screen.getByRole("link", { name: "前往问答" })).toHaveAttribute("href", "/chat");
    expect(screen.getByText("本批不含 OCR")).toBeInTheDocument();
    expect(screen.queryByLabelText(/OCR/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /OCR/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /OCR/i })).not.toBeInTheDocument();
    expect(document.querySelector('input[id*="ocr" i], input[name*="ocr" i]')).toBeNull();
    await waitFor(() => expect(fetchHistoryMock).toHaveBeenCalledTimes(1));
  });
});
