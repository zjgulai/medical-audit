import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ChatPortalPage from "./page";

const { useSearchParamsMock } = vi.hoisted(() => ({
  useSearchParamsMock: vi.fn(() => new URLSearchParams())
}));

const apiMocks = vi.hoisted(() => ({
  analyzeChatAttachment: vi.fn(),
  fetchDocumentSourceCollections: vi.fn(),
  fetchQueryModels: vi.fn(),
  runKnowledgeQuery: vi.fn()
}));

vi.mock("next/navigation", () => ({
  useSearchParams: useSearchParamsMock
}));

vi.mock("@/components/replica/use-replica-runtime", () => ({
  useReplicaChatData: () => ({
    source: "api",
    status: "ready",
    data: {
      agents: [
        {
          id: "agent-fund-helper",
          name: "基金问答助手",
          category: "业务类",
          summary: "围绕医保基金审核依据回答。",
          project: "医保基金使用合规专项自查",
          topic: "医保基金",
          initial: "基金",
          tone: "blue"
        },
        {
          id: "agent-data-helper",
          name: "数据分析助手",
          category: "效率类",
          summary: "分析表格字段。",
          project: "医保基金使用合规专项自查",
          topic: "数据分析",
          initial: "数",
          tone: "cyan"
        }
      ],
      historyItems: [],
      documentResults: []
    }
  })
}));

vi.mock("@/lib/api-client", () => apiMocks);

describe("ChatPortalPage", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.clearAllMocks();
    useSearchParamsMock.mockReturnValue(new URLSearchParams());
    apiMocks.fetchQueryModels.mockResolvedValue({
      contract_version: "chat-model-catalog-v1",
      default_model: "kimi-2.7",
      items: [
        {
          alias: "kimi-2.7",
          label: "Kimi 2.7",
          provider: "kimi",
          available: true,
          default: true,
          unavailable_reason: null
        },
        {
          alias: "deepseek-v4-pro",
          label: "DeepSeek V4 Pro",
          provider: "deepseek",
          available: true,
          default: false,
          unavailable_reason: null
        }
      ],
      boundaries: {
        production_write: false,
        provider_call: false,
        secret_values_reported: false,
        source: "environment_capability_probe_only"
      }
    });
    apiMocks.fetchDocumentSourceCollections.mockResolvedValue({
      contract_version: "document-source-collections-v1",
      role: "auditor",
      items: [
        {
          source_collection: "medical-insurance-laws",
          label: "法规政策",
          scope: "公开知识库",
          phase: "P6A",
          domain: "medical",
          evidence_group: "legal",
          description: "医保法规政策。",
          audit_hint: "用于制度依据核验。",
          access: "read",
          product_queryable: true,
          queryable: true,
          metrics: {
            document_count: 1,
            chunk_count: 8,
            character_count: null,
            linked_app_count: 1
          }
        }
      ],
      search_backend: {
        ready: true,
        backend: "local",
        details: {}
      },
      upload_permissions: {
        can_upload_personal: true,
        can_read_all_personal_uploads: false,
        can_govern_personal_uploads: false
      },
      boundaries: {
        production_write: false,
        provider_call: false,
        database_write: false,
        object_storage_write: false,
        source: "runtime_state_and_registry_only"
      }
    });
    apiMocks.runKnowledgeQuery.mockResolvedValue({
      contract_version: "knowledge-query-contract-v2",
      question: "医保基金审核依据",
      answer: "应核验医保基金审核依据 [C1]。",
      confidence: "high",
      fallback_used: false,
      model_alias: "deepseek-v4-pro",
      model_status: "selected_provider",
      effective_source_collections: ["medical-insurance-laws"],
      basis_groups: [],
      citations: [
        {
          citation_id: "C1",
          marker: "[C1]",
          chunk_id: "chunk-1",
          evidence_type: "legal_basis",
          source_collection: "medical-insurance-laws",
          snippet: "医疗机构应保留审核依据。",
          locator: {},
          index_version_key: "index-v1",
          source_package_version_key: "package-v1"
        }
      ],
      personal_upload_matches: [],
      query_log_index: 0,
      query_log_id: "query-history-1",
      agent_invocation_id: "agent-invocation-1"
    });
    apiMocks.analyzeChatAttachment.mockResolvedValue({
      contract_version: "chat-attachment-analysis-v1",
      file_name: "charges.csv",
      extension: "csv",
      mode: "table-analysis",
      model_alias: "kimi-2.7",
      model_status: "selected_provider",
      answer: "表格存在高频收费线索 [C1]。",
      extracted_preview: "charge_amount",
      summary_items: ["行数：2", "字段数：1"],
      boundaries: {
        database_write: false,
        object_storage_write: false,
        index_write: false,
        provider_call: true
      }
    });
  });

  it("submits selected model, knowledge base, and agent to the query API", async () => {
    render(<ChatPortalPage />);

    await screen.findByRole("option", { name: "DeepSeek V4 Pro" });
    fireEvent.change(screen.getByLabelText("选择模型"), {
      target: { value: "deepseek-v4-pro" }
    });
    fireEvent.click(screen.getByRole("button", { name: /全部知识库/ }));
    fireEvent.click(await screen.findByText("法规政策"));
    fireEvent.change(screen.getByLabelText("输入相关问题以对话"), {
      target: { value: "@基" }
    });
    fireEvent.click(await screen.findByText("基金问答助手"));
    fireEvent.change(screen.getByLabelText("输入相关问题以对话"), {
      target: { value: "医保基金审核依据" }
    });
    fireEvent.click(screen.getByRole("button", { name: "发送问题" }));

    await waitFor(() => {
      expect(apiMocks.runKnowledgeQuery).toHaveBeenCalledWith({
        question: "医保基金审核依据",
        top_k: 5,
        model: "deepseek-v4-pro",
        source_collections: ["medical-insurance-laws"],
        agent: "agent-fund-helper"
      });
    });
    expect(await screen.findByText(/应核验医保基金审核依据/)).toBeInTheDocument();
    expect(screen.getByText(/智能体调用已记录/)).toBeInTheDocument();
    expect(apiMocks.fetchQueryModels).toHaveBeenCalledTimes(1);
  });

  it("falls back to the default knowledge query path when chat model aliases are unavailable", async () => {
    apiMocks.fetchQueryModels.mockResolvedValue({
      contract_version: "chat-model-catalog-v1",
      default_model: "kimi-2.7",
      items: [
        {
          alias: "kimi-2.7",
          label: "Kimi 2.7",
          provider: null,
          available: false,
          default: true,
          unavailable_reason: "missing_api_key_env"
        },
        {
          alias: "deepseek-v4-pro",
          label: "DeepSeek V4 Pro",
          provider: null,
          available: false,
          default: false,
          unavailable_reason: "missing_api_key_env"
        }
      ],
      boundaries: {
        production_write: false,
        provider_call: false,
        secret_values_reported: false,
        source: "environment_capability_probe_only"
      }
    });
    apiMocks.runKnowledgeQuery.mockResolvedValue({
      contract_version: "knowledge-query-contract-v2",
      question: "医保基金审核依据",
      answer: "默认知识库回答。",
      confidence: "medium",
      fallback_used: true,
      model_alias: null,
      model_status: "default_fallback",
      effective_source_collections: ["medical-insurance-laws"],
      basis_groups: [],
      citations: [],
      personal_upload_matches: [],
      query_log_index: 0,
      query_log_id: "query-history-default",
      agent_invocation_id: null
    });
    render(<ChatPortalPage />);

    await screen.findByRole("option", { name: "Kimi 2.7（未配置）" });
    fireEvent.change(screen.getByLabelText("输入相关问题以对话"), {
      target: { value: "医保基金审核依据" }
    });
    fireEvent.click(screen.getByRole("button", { name: "发送问题" }));

    await waitFor(() => {
      expect(apiMocks.runKnowledgeQuery).toHaveBeenCalledWith(
        expect.objectContaining({
          question: "医保基金审核依据",
          model: null,
          agent: null
        })
      );
    });
    expect(await screen.findByText("默认知识库回答。")).toBeInTheDocument();
    expect(screen.getByText(/模型：默认知识库问答/)).toBeInTheDocument();
  });

  it("uploads an attachment through the chat analysis endpoint", async () => {
    const { container } = render(<ChatPortalPage />);

    await screen.findByRole("option", { name: "Kimi 2.7" });
    fireEvent.click(screen.getByRole("button", { name: "上传附件" }));
    const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["charge_amount\n100"], "charges.csv", { type: "text/csv" });
    fireEvent.change(fileInput, { target: { files: [file] } });

    await waitFor(() => {
      expect(apiMocks.analyzeChatAttachment).toHaveBeenCalledWith(file, { model: "kimi-2.7" });
    });
    expect(await screen.findByText(/表格存在高频收费线索/)).toBeInTheDocument();
  });

  it("uploads an attachment through the default parser when model aliases are unavailable", async () => {
    apiMocks.fetchQueryModels.mockResolvedValue({
      contract_version: "chat-model-catalog-v1",
      default_model: "kimi-2.7",
      items: [
        {
          alias: "kimi-2.7",
          label: "Kimi 2.7",
          provider: null,
          available: false,
          default: true,
          unavailable_reason: "missing_api_key_env"
        },
        {
          alias: "deepseek-v4-pro",
          label: "DeepSeek V4 Pro",
          provider: null,
          available: false,
          default: false,
          unavailable_reason: "missing_api_key_env"
        }
      ],
      boundaries: {
        production_write: false,
        provider_call: false,
        secret_values_reported: false,
        source: "environment_capability_probe_only"
      }
    });
    apiMocks.analyzeChatAttachment.mockResolvedValue({
      contract_version: "chat-attachment-analysis-v1",
      file_name: "charges.csv",
      extension: "csv",
      mode: "table-analysis",
      model_alias: null,
      model_status: "default_fallback",
      answer: "已用默认附件解析完成。",
      extracted_preview: "charge_amount",
      summary_items: ["行数：2", "字段数：1"],
      boundaries: {
        database_write: false,
        object_storage_write: false,
        index_write: false,
        provider_call: false
      }
    });
    const { container } = render(<ChatPortalPage />);

    await screen.findByRole("option", { name: "Kimi 2.7（未配置）" });
    fireEvent.click(screen.getByRole("button", { name: "上传附件" }));
    const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["charge_amount\n100"], "charges.csv", { type: "text/csv" });
    fireEvent.change(fileInput, { target: { files: [file] } });

    await waitFor(() => {
      expect(apiMocks.analyzeChatAttachment).toHaveBeenCalledWith(file, { model: null });
    });
    expect(await screen.findByText(/已用默认附件解析完成/)).toBeInTheDocument();
    expect(screen.getByText(/模型：默认附件解析/)).toBeInTheDocument();
    expect(screen.getByText(/未调用外部模型/)).toBeInTheDocument();
  });
});
