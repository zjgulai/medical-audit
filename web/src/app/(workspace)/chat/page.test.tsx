import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { AgentsResponse, AuditAgentApiItem, QueryHistoryResponse } from "@/lib/api-types";

import ChatPortalPage from "./page";

const { useSearchParamsMock } = vi.hoisted(() => ({
  useSearchParamsMock: vi.fn(() => new URLSearchParams())
}));

const apiMocks = vi.hoisted(() => ({
  analyzeChatAttachment: vi.fn(),
  fetchAgents: vi.fn(),
  fetchDocumentSourceCollections: vi.fn(),
  fetchQueryHistory: vi.fn(),
  fetchQueryModels: vi.fn(),
  runKnowledgeQuery: vi.fn()
}));

vi.mock("next/navigation", () => ({
  useSearchParams: useSearchParamsMock
}));

vi.mock("@/lib/api-client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api-client")>()),
  ...apiMocks
}));

function makeChatApiAgent(
  id: string,
  name: string,
  category: AuditAgentApiItem["category"],
  topic: string
): AuditAgentApiItem {
  const prompt = `请使用${name}围绕${topic}输出风险判断、证据依据和待补材料。`;
  return {
    id,
    name,
    category,
    topic,
    prompt,
    knowledge_base: "医保基金合规知识库",
    project_name: "医保基金使用合规专项自查",
    status: "active",
    prompt_version: 1,
    prompt_version_key: `${id}@v1`,
    visibility_scope: "project",
    allowed_roles: ["admin", "technician", "director", "member"],
    prompt_versions: [
      {
        version: 1,
        prompt,
        change_summary: "initial version",
        is_active: true,
        created_by: "next-admin",
        created_at: "2026-07-06T00:00:00Z",
        review_status: "approved",
        review_note: "reviewed",
        requested_by: "next-admin",
        reviewed_by: "next-admin",
        reviewed_at: "2026-07-06T00:00:00Z",
        review_updated_at: "2026-07-06T00:00:00Z"
      }
    ],
    created_by: "next-admin",
    created_at: "2026-07-06T00:00:00Z",
    updated_at: "2026-07-06T00:00:00Z",
    source: "custom",
    metadata: {
      summary: `${name}用于${topic}。`,
      description: `${name}的完整 API 测试数据。`,
      contract_version: "audit-agent-v1"
    }
  };
}

function chatAgentsResponse(): AgentsResponse {
  return {
    items: [
      makeChatApiAgent("agent-fund-helper", "基金问答助手", "业务类", "医保基金"),
      makeChatApiAgent("agent-data-helper", "数据分析助手", "效率类", "数据分析"),
      makeChatApiAgent("third-id", "第三智能体", "研究类", "科研复核"),
      makeChatApiAgent("fourth-id", "第四智能体", "业务类", "采购复核"),
      makeChatApiAgent("fifth-id", "第五智能体", "效率类", "档案复核")
    ],
    categories: ["业务类", "效率类", "研究类"],
    store: { ready: true, backend: "SqlAlchemyAgentStore" }
  };
}

const emptyQueryHistory: QueryHistoryResponse = {
  items: [],
  store: { ready: true, backend: "SqlAlchemyQueryHistoryStore" }
};

describe("ChatPortalPage", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.clearAllMocks();
    useSearchParamsMock.mockReturnValue(new URLSearchParams());
    apiMocks.fetchAgents.mockResolvedValue(chatAgentsResponse());
    apiMocks.fetchQueryHistory.mockResolvedValue(emptyQueryHistory);
    apiMocks.fetchQueryModels.mockResolvedValue({
      contract_version: "chat-model-catalog-v1",
      default_model: "kimi-2.7",
      items: [
        {
          alias: "kimi-2.7",
          label: "Kimi K2.6（兼容别名）",
          model: "kimi-k2.6",
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
      generation_status: "generated",
      generation_failure_code: null,
      generation_http_status: null,
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
    expect(screen.getByText(/模型状态：选定模型/)).toBeInTheDocument();
    expect(screen.getByText(/知识库：法规政策/)).toBeInTheDocument();
    expect(screen.getByText(/检索：已命中/)).toBeInTheDocument();
    expect(screen.getByText(/智能体调用已记录/)).toBeInTheDocument();
    expect(apiMocks.fetchQueryModels).toHaveBeenCalledTimes(1);
  });

  it("selects an agent from slash command and submits it to the query API", async () => {
    render(<ChatPortalPage />);

    await screen.findByRole("option", { name: "Kimi K2.6（兼容别名）" });
    fireEvent.change(screen.getByLabelText("输入相关问题以对话"), {
      target: { value: "/数" }
    });
    fireEvent.click(await screen.findByText("数据分析助手"));
    fireEvent.change(screen.getByLabelText("输入相关问题以对话"), {
      target: { value: "请分析收费明细" }
    });
    fireEvent.click(screen.getByRole("button", { name: "发送问题" }));

    await waitFor(() => {
      expect(apiMocks.runKnowledgeQuery).toHaveBeenCalledWith(
        expect.objectContaining({
          question: "请分析收费明细",
          model: "kimi-2.7",
          agent: "agent-data-helper"
        })
      );
    });
  });

  it("does not submit on an Enter key event and submits an assigned multiline value only after clicking send", async () => {
    render(<ChatPortalPage />);

    await screen.findByRole("option", { name: "Kimi K2.6（兼容别名）" });
    const textbox = screen.getByRole("textbox", { name: "输入相关问题以对话" });

    fireEvent.keyDown(textbox, { key: "Enter", code: "Enter" });
    fireEvent.change(textbox, { target: { value: "第一行\n第二行" } });

    expect(textbox).toHaveValue("第一行\n第二行");
    expect(apiMocks.runKnowledgeQuery).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "发送问题" }));

    await waitFor(() => {
      expect(apiMocks.runKnowledgeQuery).toHaveBeenCalledWith(
        expect.objectContaining({ question: "第一行\n第二行" })
      );
    });
  });

  it("hydrates question, knowledge base, and agent from chat URL params", async () => {
    useSearchParamsMock.mockReturnValue(
      new URLSearchParams(
        "question=%E5%8C%BB%E4%BF%9D%E5%9F%BA%E9%87%91%E5%AE%A1%E6%A0%B8%E4%BE%9D%E6%8D%AE&source_collection=medical-insurance-laws&agent=agent-fund-helper"
      )
    );

    render(<ChatPortalPage />);

    await waitFor(() => {
      expect(screen.getByLabelText("输入相关问题以对话")).toHaveValue("医保基金审核依据");
    });
    expect(await screen.findByRole("button", { name: /1 个知识库/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /基金问答助手/ })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "发送问题" }));

    await waitFor(() => {
      expect(apiMocks.runKnowledgeQuery).toHaveBeenCalledWith({
        question: "医保基金审核依据",
        top_k: 5,
        model: "kimi-2.7",
        source_collections: ["medical-insurance-laws"],
        agent: "agent-fund-helper"
      });
    });
  });

  it("selects the fifth API agent from the chat URL through the runtime loader", async () => {
    useSearchParamsMock.mockReturnValue(new URLSearchParams("agent=fifth-id"));

    render(<ChatPortalPage />);

    expect(await screen.findByRole("button", { name: /第五智能体/ })).toBeInTheDocument();
    expect(apiMocks.fetchAgents).toHaveBeenCalledTimes(1);
    expect(apiMocks.fetchQueryHistory).toHaveBeenCalledTimes(1);

    fireEvent.change(screen.getByLabelText("输入相关问题以对话"), {
      target: { value: "请执行档案复核" }
    });
    fireEvent.click(screen.getByRole("button", { name: "发送问题" }));

    await waitFor(() => {
      expect(apiMocks.runKnowledgeQuery).toHaveBeenCalledWith(
        expect.objectContaining({
          question: "请执行档案复核",
          agent: "fifth-id"
        })
      );
    });
  });

  it("falls back to the default knowledge query path when chat model aliases are unavailable", async () => {
    apiMocks.fetchQueryModels.mockResolvedValue({
      contract_version: "chat-model-catalog-v1",
      default_model: "kimi-2.7",
      items: [
        {
          alias: "kimi-2.7",
          label: "Kimi K2.6（兼容别名）",
          model: "kimi-k2.6",
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
      generation_status: "not_requested",
      generation_failure_code: null,
      generation_http_status: null,
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

    await screen.findByRole("option", { name: "Kimi K2.6（兼容别名）（未配置）" });
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
    expect(screen.getByText(/模型状态：默认通道/)).toBeInTheDocument();
    expect(screen.getByText(/检索：使用兜底/)).toBeInTheDocument();
  });

  it("uploads an attachment through the chat analysis endpoint", async () => {
    const { container } = render(<ChatPortalPage />);

    await screen.findByRole("option", { name: "Kimi K2.6（兼容别名）" });
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
          label: "Kimi K2.6（兼容别名）",
          model: "kimi-k2.6",
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

    await screen.findByRole("option", { name: "Kimi K2.6（兼容别名）（未配置）" });
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
