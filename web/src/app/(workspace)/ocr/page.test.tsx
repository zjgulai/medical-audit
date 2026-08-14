import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import OcrWorkbenchPage from "./page";

const apiMocks = vi.hoisted(() => ({
  extractOcrText: vi.fn(),
  fetchOcrCapabilities: vi.fn()
}));

vi.mock("@/lib/api-client", () => apiMocks);

describe("OcrWorkbenchPage", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  beforeEach(() => {
    vi.clearAllMocks();
    apiMocks.fetchOcrCapabilities.mockResolvedValue({
      contract_version: "unlimited-ocr-capability-v1",
      enabled: true,
      engine: "baidu/Unlimited-OCR",
      source_commit: "d49ff64afffc1f47ab563dc1c589bc2f78808fa4",
      supported_extensions: ["pdf", "png", "jpg"],
      max_upload_bytes: 40 * 1024 * 1024,
      max_pages: 100,
      pdf_dpi: 200,
      boundaries: {
        database_write: false,
        audit_log_write: false,
        source_storage_write: false,
        provider_call: false
      }
    });
    apiMocks.extractOcrText.mockResolvedValue({
      contract_version: "unlimited-ocr-extraction-v1",
      file_name: "扫描合同.png",
      extension: "png",
      source_sha256: "a".repeat(64),
      size_bytes: 10,
      text: "第一条 付款条件需要复核。",
      page_count: 1,
      engine: "baidu/Unlimited-OCR",
      source_commit: "d49ff64afffc1f47ab563dc1c589bc2f78808fa4",
      mapping_status: "resolved",
      pages: [{
        page_number: 1,
        text: "第一条 付款条件需要复核。",
        image_sha256: "b".repeat(64),
        text_sha256: "c".repeat(64),
        mapping_status: "resolved"
      }],
      boundaries: {
        database_write: false,
        audit_log_write: true,
        source_storage_write: false,
        index_write: false,
        provider_call: true,
        ocr_call: true,
        answer_provider_call: false
      }
    });
  });

  it("exposes the bounded OCR workflow and renders page evidence", async () => {
    const { container } = render(<OcrWorkbenchPage />);

    expect(await screen.findByText("Unlimited-OCR 已就绪")).toBeInTheDocument();
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["image-data"], "扫描合同.png", { type: "image/png" });
    fireEvent.change(input, { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: "开始文本识别" }));

    await waitFor(() => expect(apiMocks.extractOcrText).toHaveBeenCalledWith(file));
    expect(await screen.findByDisplayValue("第一条 付款条件需要复核。")).toBeInTheDocument();
    expect(screen.getByText("第 1 页")).toBeInTheDocument();
    expect(screen.getByText("文本 cccccccc…cccccccc")).toBeInTheDocument();
    expect(screen.getByText("成功后仅写安全元数据与哈希")).toBeInTheDocument();
  });

  it("fails closed when the OCR runtime is not enabled", async () => {
    apiMocks.fetchOcrCapabilities.mockResolvedValueOnce({
      contract_version: "unlimited-ocr-capability-v1",
      enabled: false,
      engine: "baidu/Unlimited-OCR",
      source_commit: "d49ff64afffc1f47ab563dc1c589bc2f78808fa4",
      supported_extensions: ["pdf", "png"],
      max_upload_bytes: 40 * 1024 * 1024,
      max_pages: 100,
      pdf_dpi: 200,
      boundaries: {
        database_write: false,
        audit_log_write: false,
        source_storage_write: false,
        provider_call: false
      }
    });

    const { container } = render(<OcrWorkbenchPage />);

    expect(await screen.findByText("Unlimited-OCR 未启用")).toBeInTheDocument();
    expect(screen.getByText(/不会自动拉取模型或修改运行配置/)).toBeInTheDocument();
    expect(container.querySelector('input[type="file"]')).toBeDisabled();
    expect(screen.getByRole("button", { name: "开始文本识别" })).toBeDisabled();
    expect(apiMocks.extractOcrText).not.toHaveBeenCalled();
  });

  it("removes OCR upload controls and capability reads from the production shell", async () => {
    vi.stubEnv("NEXT_PUBLIC_MEDICAL_AUDIT_API_ACCESS_MODE", "public-shell-readonly");

    const { container } = render(<OcrWorkbenchPage />);

    expect(await screen.findByText(/OCR 文件上传、文本识别和 Provider 调用均不开放/)).toBeInTheDocument();
    expect(apiMocks.fetchOcrCapabilities).not.toHaveBeenCalled();
    expect(apiMocks.extractOcrText).not.toHaveBeenCalled();
    expect(container.querySelector('input[type="file"]')).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "开始文本识别" })).not.toBeInTheDocument();
  });
});
