import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ReplicaRuntimeResult } from "@/components/replica/use-replica-runtime";
import { runKnowledgeQuery, searchDocuments } from "@/lib/api-client";
import type { ReplicaDocumentsData } from "@/lib/replica-adapters";

import DocumentsPage from "./page";

const runtimeMock = vi.hoisted(() => ({
  current: null as unknown as ReplicaRuntimeResult<ReplicaDocumentsData>
}));

vi.mock("@/components/replica/use-replica-runtime", () => ({
  useReplicaDocumentsData: () => runtimeMock.current
}));

vi.mock("@/components/documents/personal-material-read-panel", () => ({
  PersonalMaterialReadPanel: () => (
    <section aria-label="个人材料只读面板">
      <h2>个人材料</h2>
    </section>
  )
}));

function makeApiRuntime(): ReplicaRuntimeResult<ReplicaDocumentsData> {
  return {
    apiReadsEnabled: true,
    source: "api",
    outcome: "ready",
    status: "ready",
    issues: [],
    data: {
      categories: [
        {
          id: "source-medical-insurance-laws",
          name: "医保法规库",
          description: "医保法规、政策解释和处罚依据。",
          count: 12
        }
      ],
      searchHistory: ["医保支付"],
      results: [
        {
          id: "fixture-doc",
          title: "医保基金监管条例",
          category: "医保法规库",
          excerpt: "医保基金使用监管依据。",
          source: "医保法规库",
          updatedAt: "2026-07-01"
        }
      ]
    }
  };
}

vi.mock("@/lib/api-client", () => ({
  fetchDocumentFileBlob: vi.fn(),
  runKnowledgeQuery: vi.fn(),
  searchDocuments: vi.fn()
}));

const runKnowledgeQueryMock = vi.mocked(runKnowledgeQuery);
const searchDocumentsMock = vi.mocked(searchDocuments);

function makeAiResponse(
  overrides: Partial<Awaited<ReturnType<typeof runKnowledgeQuery>>> = {}
): Awaited<ReturnType<typeof runKnowledgeQuery>> {
  return {
    contract_version: "knowledge-query-contract-v2",
    question: "医保基金监管",
    answer: "",
    confidence: "low",
    fallback_used: false,
    generation_status: "generated",
    generation_failure_code: null,
    generation_http_status: null,
    model_alias: "kimi-2.7",
    model_status: "selected_provider",
    effective_source_collections: [],
    basis_groups: [],
    citations: [],
    personal_upload_matches: [],
    query_log_index: 1,
    query_log_id: "query-log-mode-test",
    agent_invocation_id: null,
    ...overrides
  };
}

describe("DocumentsPage", () => {
  beforeEach(() => {
    runtimeMock.current = makeApiRuntime();
  });

  afterEach(() => {
    vi.clearAllMocks();
    window.history.pushState({}, "", "/documents");
  });

  it("keeps the first render read-only for knowledge query side effects", () => {
    render(<DocumentsPage />);

    expect(screen.getByRole("heading", { name: "文档检索" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "检索关键词" })).toHaveValue("医保基金监管");
    expect(screen.getByRole("textbox", { name: "检索关键词" })).toHaveAttribute(
      "placeholder",
      "医保基金监管"
    );
    expect(screen.queryByDisplayValue("劳动争议司法案件解释")).not.toBeInTheDocument();
    expect(runKnowledgeQueryMock).not.toHaveBeenCalled();
    expect(searchDocumentsMock).not.toHaveBeenCalled();
  });

  it("mounts the personal material panel without regressing search, catalog, history, or AI controls", () => {
    render(<DocumentsPage />);

    expect(screen.getByRole("region", { name: "个人材料只读面板" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "检索关键词" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "搜索历史" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "医保法规库 (12)" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /检索AI\+/ })).toBeInTheDocument();
  });

  it("uses the medical-audit default when either search mode receives a blank draft", async () => {
    searchDocumentsMock.mockResolvedValue({
      contract_version: "document-search-v2",
      query: "医保基金监管",
      effective_source_collections: [],
      items: [],
      store: { ready: true, backend: "unit-test" },
      boundaries: {
        production_write: false,
        provider_call: false,
        database_write: false,
        object_storage_write: false,
        query_history_write: false
      }
    });
    runKnowledgeQueryMock.mockResolvedValue(makeAiResponse());

    render(<DocumentsPage />);
    fireEvent.change(screen.getByRole("textbox", { name: "检索关键词" }), {
      target: { value: "   " }
    });
    fireEvent.click(screen.getByRole("button", { name: "搜索" }));

    await waitFor(() => {
      expect(searchDocumentsMock).toHaveBeenCalledWith(expect.objectContaining({ query: "医保基金监管" }));
    });
    fireEvent.click(screen.getByRole("button", { name: /检索AI\+/ }));

    await waitFor(() => {
      expect(runKnowledgeQueryMock).toHaveBeenCalledWith(expect.objectContaining({ question: "医保基金监管" }));
    });
    expect(screen.queryByText("劳动争议司法案件解释")).not.toBeInTheDocument();
  });

  it("does not substitute hard-coded or fixture documents into the initial live page", () => {
    render(<DocumentsPage />);

    expect(screen.getAllByText("医保法规库").length).toBeGreaterThan(0);
    expect(screen.getByText("医保支付")).toBeInTheDocument();
    expect(screen.queryByText("医保基金监管条例")).not.toBeInTheDocument();
    expect(screen.queryByText("雨丰民生25年流水.xlsx")).not.toBeInTheDocument();
    expect(screen.queryByText("18_投标被否决原因统计表.pdf")).not.toBeInTheDocument();
    expect(screen.queryByText("智能科技的CEO是谁")).not.toBeInTheDocument();
  });

  it("renders runtime catalog and history empty states without fabricated zero totals", () => {
    runtimeMock.current = {
      ...makeApiRuntime(),
      outcome: "empty",
      status: "empty",
      data: { categories: [], searchHistory: [], results: [] }
    };

    render(<DocumentsPage />);

    expect(screen.getByText("暂无可用文档目录")).toBeInTheDocument();
    expect(screen.getByText("暂无搜索历史")).toBeInTheDocument();
    expect(screen.queryByText("文档目录读取失败")).not.toBeInTheDocument();
    expect(screen.queryByText("文档库：0 类 / 0 份")).not.toBeInTheDocument();
    expect(screen.queryByText("0 条匹配")).not.toBeInTheDocument();
  });

  it("renders runtime catalog errors without leaking stale catalog, history, or fixture data", () => {
    runtimeMock.current = {
      ...makeApiRuntime(),
      outcome: "error",
      status: "error"
    };

    render(<DocumentsPage />);

    expect(screen.getByText("文档目录读取失败")).toBeInTheDocument();
    expect(screen.getByText("搜索历史读取失败")).toBeInTheDocument();
    expect(screen.queryByText("暂无搜索历史")).not.toBeInTheDocument();
    expect(screen.queryByText("暂无可用文档目录")).not.toBeInTheDocument();
    expect(screen.queryByText("医保支付")).not.toBeInTheDocument();
    expect(screen.queryByText("医保基金监管条例")).not.toBeInTheDocument();
    expect(screen.queryByText("医保法规库 文档目录")).not.toBeInTheDocument();
    expect(screen.queryByText("文档库：1 类 / 12 份")).not.toBeInTheDocument();
  });

  it("shows unknown catalog counts without fabricating zero values", () => {
    runtimeMock.current = {
      ...makeApiRuntime(),
      outcome: "degraded",
      status: "degraded",
      data: {
        ...makeApiRuntime().data,
        categories: [
          {
            id: "source-medical-insurance-laws",
            name: "医保法规库",
            description: "医保法规、政策解释和处罚依据。",
            count: null
          }
        ]
      }
    };

    render(<DocumentsPage />);

    expect(screen.getByRole("main")).toHaveAttribute("data-replica-status", "degraded");
    expect(screen.getByRole("button", { name: "全部文档 (待同步)" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "医保法规库 (待同步)" })).toBeInTheDocument();
    expect(screen.getByText("文档库：1 类 / 待同步")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "全部文档 (0)" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "医保法规库 (0)" })).not.toBeInTheDocument();
    expect(screen.queryByText("文档目录读取失败")).not.toBeInTheDocument();
  });

  it("keeps a real zero catalog count visible as zero", () => {
    runtimeMock.current = {
      ...makeApiRuntime(),
      data: {
        ...makeApiRuntime().data,
        categories: [
          {
            id: "source-medical-insurance-laws",
            name: "医保法规库",
            description: "医保法规、政策解释和处罚依据。",
            count: 0
          }
        ]
      }
    };

    render(<DocumentsPage />);

    expect(screen.getByRole("main")).toHaveAttribute("data-replica-status", "ready");
    expect(screen.getByRole("button", { name: "全部文档 (0)" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "医保法规库 (0)" })).toBeInTheDocument();
    expect(screen.getByText("文档库：1 类 / 0 份")).toBeInTheDocument();
  });

  it("renders runtime fixture history and documents only when the source is fixture", () => {
    runtimeMock.current = {
      ...makeApiRuntime(),
      apiReadsEnabled: false,
      source: "fixture",
      data: {
        categories: [
          {
            id: "fixture-law",
            name: "fixture 法规库",
            description: "本地 fixture 目录。",
            count: 1
          }
        ],
        searchHistory: ["fixture 历史词"],
        results: [
          {
            id: "fixture-visible-doc",
            title: "医保基金监管 fixture 文档",
            category: "fixture 法规库",
            excerpt: "本地 fixture 检索片段。",
            source: "fixture",
            updatedAt: "2026-07-01"
          }
        ]
      }
    };

    render(<DocumentsPage />);

    expect(screen.getByText("fixture 历史词")).toBeInTheDocument();
    expect(screen.getAllByText("医保基金监管 fixture 文档").length).toBeGreaterThan(0);
    expect(searchDocumentsMock).not.toHaveBeenCalled();
    expect(runKnowledgeQueryMock).not.toHaveBeenCalled();
  });

  it("runs read-only document search after an explicit search action", async () => {
    searchDocumentsMock.mockResolvedValue({
      contract_version: "document-search-v1",
      query: "医保基金监管",
      effective_source_collections: ["medical-insurance-laws"],
      items: [
        {
          id: "chunk-1",
          chunk_id: "chunk-1",
          title: "医保支付政策",
          source_collection: "medical-insurance-laws",
          source_label: "医保法规库",
          snippet: "医保支付政策引用片段。",
          locator: { title: "医保支付政策", date: "2026-07-06" },
          score: 1,
          matched_by: ["bm25"],
          index_version_key: "index-v1",
          source_package_version_key: "package-v1",
          preview_url: "/api/v1/preview/chunk-1",
          download_url: "/api/v1/documents/source/chunk-1/download",
          match_count: 2,
          matched_snippets: ["医保支付政策引用片段。"]
        }
      ],
      store: { ready: true, backend: "unit-test" },
      boundaries: {
        production_write: false,
        provider_call: false,
        database_write: false,
        object_storage_write: false,
        query_history_write: false
      }
    });

    render(<DocumentsPage />);

    fireEvent.click(screen.getByRole("button", { name: "搜索" }));

    await waitFor(() => {
      expect(searchDocumentsMock).toHaveBeenCalledWith({
        query: "医保基金监管",
        limit: 10,
        titleOnly: false,
        sourceCollections: []
      });
    });
    expect((await screen.findAllByText("医保支付政策")).length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("医保支付政策引用片段。").length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: "预览原文" })).toHaveAttribute(
      "href",
      "/api/v1/preview/chunk-1"
    );
    expect(screen.getByRole("button", { name: "下载原文" })).toBeInTheDocument();
    expect(screen.getByText("2 处")).toBeInTheDocument();
    expect(screen.getByText("文档检索 provider_call：否")).toBeInTheDocument();
    expect(runKnowledgeQueryMock).not.toHaveBeenCalled();
  });

  it("links the selected live document result into chat with query and source context", async () => {
    searchDocumentsMock.mockResolvedValue({
      contract_version: "document-search-v1",
      query: "医保基金监管",
      effective_source_collections: ["medical-insurance-laws"],
      items: [
        {
          id: "chunk-1",
          chunk_id: "chunk-1",
          title: "医保支付政策",
          source_collection: "medical-insurance-laws",
          source_label: "医保法规库",
          snippet: "医保支付政策引用片段。",
          locator: { title: "医保支付政策", date: "2026-07-06" },
          score: 1,
          matched_by: ["bm25"],
          index_version_key: "index-v1",
          source_package_version_key: "package-v1",
          preview_url: "/api/v1/preview/chunk-1"
        }
      ],
      store: { ready: true, backend: "unit-test" },
      boundaries: {
        production_write: false,
        provider_call: false,
        database_write: false,
        object_storage_write: false,
        query_history_write: false
      }
    });

    render(<DocumentsPage />);

    fireEvent.click(screen.getByRole("button", { name: "搜索" }));

    const chatLink = await screen.findByRole("link", { name: "加入对话" });
    expect(chatLink).toHaveAttribute(
      "href",
      "/chat?question=%E5%8C%BB%E4%BF%9D%E5%9F%BA%E9%87%91%E7%9B%91%E7%AE%A1&source_collection=medical-insurance-laws"
    );
    expect(runKnowledgeQueryMock).not.toHaveBeenCalled();
  });

  it("shows the exact empty state without substituting directory or fixture documents", async () => {
    searchDocumentsMock.mockResolvedValue({
      contract_version: "document-search-v1",
      query: "医保基金监管",
      effective_source_collections: [],
      items: [],
      store: { ready: true, backend: "unit-test" },
      boundaries: {
        production_write: false,
        provider_call: false,
        database_write: false,
        object_storage_write: false,
        query_history_write: false
      }
    });

    render(<DocumentsPage />);
    fireEvent.click(screen.getByRole("button", { name: "搜索" }));

    expect(await screen.findByText("未找到匹配文档")).toBeInTheDocument();
    expect(screen.getByRole("status", { name: "文档检索空状态" })).toHaveAttribute("aria-live", "polite");
    expect(screen.getByRole("status", { name: "文档检索完成状态" })).toHaveAttribute("aria-live", "polite");
    expect(screen.queryByText("医保法规库 文档目录")).not.toBeInTheDocument();
    expect(screen.queryByText("医保基金监管条例")).not.toBeInTheDocument();
    expect(screen.queryByText("推荐文档")).not.toBeInTheDocument();
  });

  it("disables both search actions while a document search is running", async () => {
    let resolveSearch!: (response: Awaited<ReturnType<typeof searchDocuments>>) => void;
    searchDocumentsMock.mockImplementation(() => new Promise((resolve) => {
      resolveSearch = resolve;
    }));

    render(<DocumentsPage />);
    fireEvent.click(screen.getByRole("button", { name: "搜索" }));

    const searchButton = await screen.findByRole("button", { name: "搜索中" });
    const aiButton = screen.getByRole("button", { name: /检索AI\+/ });
    expect(searchButton).toBeDisabled();
    expect(aiButton).toBeDisabled();

    fireEvent.click(searchButton);
    fireEvent.click(aiButton);
    expect(searchDocumentsMock).toHaveBeenCalledTimes(1);
    expect(runKnowledgeQueryMock).not.toHaveBeenCalled();

    resolveSearch({
      contract_version: "document-search-v1",
      query: "医保基金监管",
      effective_source_collections: [],
      items: [],
      store: { ready: true, backend: "unit-test" },
      boundaries: {
        production_write: false,
        provider_call: false,
        database_write: false,
        object_storage_write: false,
        query_history_write: false
      }
    });
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "搜索" })).not.toBeDisabled();
    });
  });

  it("keeps pure-search metadata and chat context bound to the completed request snapshot", async () => {
    let resolveSearch!: (response: Awaited<ReturnType<typeof searchDocuments>>) => void;
    searchDocumentsMock.mockImplementation(() => new Promise((resolve) => {
      resolveSearch = resolve;
    }));

    render(<DocumentsPage />);
    fireEvent.click(screen.getByRole("button", { name: "医保法规库 (12)" }));
    fireEvent.click(screen.getByRole("button", { name: "搜索" }));

    await waitFor(() => {
      expect(searchDocumentsMock).toHaveBeenCalledWith({
        query: "医保基金监管",
        limit: 10,
        titleOnly: false,
        sourceCollections: ["medical-insurance-laws"]
      });
    });

    fireEvent.change(screen.getByRole("textbox", { name: "检索关键词" }), {
      target: { value: "运行中修改的草稿" }
    });
    fireEvent.click(screen.getByRole("checkbox", { name: "仅标题" }));
    fireEvent.click(screen.getByRole("button", { name: "医保支付" }));
    fireEvent.click(screen.getByRole("button", { name: "全部文档 (12)" }));

    resolveSearch({
      contract_version: "document-search-v1",
      query: "医保基金监管",
      effective_source_collections: ["personal-materials"],
      items: [
        {
          id: "snapshot-result",
          chunk_id: "snapshot-result",
          title: "快照绑定结果",
          source_collection: "personal-materials",
          source_label: "个人材料",
          snippet: "结果上下文应保持原请求。",
          locator: { title: "快照绑定结果" },
          score: 1,
          matched_by: ["bm25"],
          index_version_key: "index-v1",
          source_package_version_key: "package-v1",
          preview_url: "/api/v1/preview/snapshot-result"
        }
      ],
      store: { ready: true, backend: "unit-test" },
      boundaries: {
        production_write: false,
        provider_call: false,
        database_write: false,
        object_storage_write: false,
        query_history_write: false
      }
    });

    expect((await screen.findAllByText("快照绑定结果")).length).toBeGreaterThan(0);
    const completedStatus = screen.getByLabelText("当前检索状态");
    expect(completedStatus).toHaveTextContent("医保法规库");
    expect(completedStatus).toHaveTextContent("全文检索");
    expect(completedStatus).toHaveTextContent("关键词：医保基金监管");
    expect(completedStatus).toHaveTextContent("范围：个人上传材料");
    expect(completedStatus).not.toHaveTextContent("医保支付");
    expect(completedStatus).not.toHaveTextContent("仅标题");
    expect(screen.getByRole("link", { name: "加入对话" })).toHaveAttribute(
      "href",
      "/chat?question=%E5%8C%BB%E4%BF%9D%E5%9F%BA%E9%87%91%E7%9B%91%E7%AE%A1&source_collection=personal-materials"
    );

    fireEvent.change(screen.getByRole("textbox", { name: "检索关键词" }), {
      target: { value: "完成后再次修改" }
    });
    fireEvent.click(screen.getByRole("checkbox", { name: "仅标题" }));
    fireEvent.click(screen.getByRole("button", { name: "医保法规库 (12)" }));
    fireEvent.click(screen.getByRole("button", { name: "全部文档 (12)" }));

    expect(screen.getByLabelText("当前检索状态")).toHaveTextContent("关键词：医保基金监管");
    expect(screen.getByLabelText("当前检索状态")).toHaveTextContent("范围：个人上传材料");
    expect(screen.getByRole("link", { name: "加入对话" })).toHaveAttribute(
      "href",
      "/chat?question=%E5%8C%BB%E4%BF%9D%E5%9F%BA%E9%87%91%E7%9B%91%E7%AE%A1&source_collection=personal-materials"
    );
  });

  it("keeps AI+ context immutable and gives a following pure search its own draft snapshot", async () => {
    let resolveAi!: (response: Awaited<ReturnType<typeof runKnowledgeQuery>>) => void;
    runKnowledgeQueryMock.mockImplementation(() => new Promise((resolve) => {
      resolveAi = resolve;
    }));

    render(<DocumentsPage />);
    fireEvent.click(screen.getByRole("button", { name: "医保法规库 (12)" }));
    fireEvent.click(screen.getByRole("button", { name: /检索AI\+/ }));

    await waitFor(() => {
      expect(runKnowledgeQueryMock).toHaveBeenCalledWith({
        question: "医保基金监管",
        top_k: 5,
        title_only: false,
        source_collections: ["medical-insurance-laws"]
      });
    });

    fireEvent.change(screen.getByRole("textbox", { name: "检索关键词" }), {
      target: { value: "AI运行中草稿" }
    });
    fireEvent.click(screen.getByRole("checkbox", { name: "仅标题" }));
    fireEvent.click(screen.getByRole("button", { name: "医保支付" }));
    fireEvent.click(screen.getByRole("button", { name: "全部文档 (12)" }));

    resolveAi(makeAiResponse({
      question: "医保基金监管",
      effective_source_collections: ["medical-insurance-laws"],
      citations: [
        {
          citation_id: "ai-snapshot-result",
          marker: "[1]",
          chunk_id: "ai-snapshot-result",
          evidence_type: "法规依据",
          source_collection: "medical-insurance-laws",
          snippet: "AI+ 快照结果。",
          locator: { title: "AI+ 快照结果" },
          index_version_key: "index-v1",
          source_package_version_key: "package-v1"
        }
      ]
    }));

    expect((await screen.findAllByText("AI+ 快照结果")).length).toBeGreaterThan(0);
    const aiStatus = screen.getByLabelText("当前检索状态");
    expect(aiStatus).toHaveTextContent("医保法规库");
    expect(aiStatus).toHaveTextContent("全文检索");
    expect(aiStatus).toHaveTextContent("关键词：医保基金监管");
    expect(aiStatus).toHaveTextContent("范围：医保法规库");
    expect(screen.getByRole("link", { name: "加入对话" })).toHaveAttribute(
      "href",
      "/chat?question=%E5%8C%BB%E4%BF%9D%E5%9F%BA%E9%87%91%E7%9B%91%E7%AE%A1&source_collection=medical-insurance-laws"
    );

    searchDocumentsMock.mockResolvedValue({
      contract_version: "document-search-v1",
      query: "医保支付",
      effective_source_collections: [],
      items: [
        {
          id: "pure-after-ai",
          chunk_id: "pure-after-ai",
          title: "AI+ 后的纯检索结果",
          source_collection: "medical-insurance-laws",
          source_label: "医保法规库",
          snippet: "使用新的纯检索草稿。",
          locator: { title: "AI+ 后的纯检索结果" },
          score: 1,
          matched_by: ["bm25"],
          index_version_key: "index-v2",
          source_package_version_key: "package-v2",
          preview_url: "/api/v1/preview/pure-after-ai"
        }
      ],
      store: { ready: true, backend: "unit-test" },
      boundaries: {
        production_write: false,
        provider_call: false,
        database_write: false,
        object_storage_write: false,
        query_history_write: false
      }
    });
    fireEvent.click(screen.getByRole("button", { name: "搜索" }));

    await waitFor(() => {
      expect(searchDocumentsMock).toHaveBeenCalledWith({
        query: "医保支付",
        limit: 10,
        titleOnly: true,
        sourceCollections: []
      });
    });
    expect((await screen.findAllByText("AI+ 后的纯检索结果")).length).toBeGreaterThan(0);
    expect(screen.queryByText("AI+ 快照结果")).not.toBeInTheDocument();
    expect(screen.queryByText(/AI\+ provider_call：/)).not.toBeInTheDocument();
    const pureStatus = screen.getByLabelText("当前检索状态");
    expect(pureStatus).toHaveTextContent("全部文档");
    expect(pureStatus).toHaveTextContent("仅标题");
    expect(pureStatus).toHaveTextContent("关键词：医保支付");
    expect(pureStatus).toHaveTextContent("范围：全部可检索知识库");
    expect(screen.getByRole("link", { name: "加入对话" })).toHaveAttribute(
      "href",
      "/chat?question=%E5%8C%BB%E4%BF%9D%E6%94%AF%E4%BB%98&source_collection=medical-insurance-laws"
    );
  });

  it("keeps a failed search distinct and retries the same query and source scope", async () => {
    window.history.pushState({}, "", "/documents?source_collection=medical-insurance-laws&query=医保支付");
    searchDocumentsMock
      .mockRejectedValueOnce(new Error("409 search backend unavailable"))
      .mockResolvedValueOnce({
        contract_version: "document-search-v1",
        query: "医保支付",
        effective_source_collections: ["medical-insurance-laws"],
        items: [
          {
            id: "chunk-retry",
            chunk_id: "chunk-retry",
            title: "重试后的医保依据",
            source_collection: "medical-insurance-laws",
            source_label: "医保法规库",
            snippet: "重试成功返回的真实检索片段。",
            locator: { title: "重试后的医保依据" },
            score: 1,
            matched_by: ["bm25"],
            index_version_key: "index-v1",
            source_package_version_key: "package-v1",
            preview_url: "/api/v1/preview/chunk-retry"
          }
        ],
        store: { ready: true, backend: "unit-test" },
        boundaries: {
          production_write: false,
          provider_call: false,
          database_write: false,
          object_storage_write: false,
          query_history_write: false
        }
      });

    render(<DocumentsPage />);
    await waitFor(() => {
      expect(screen.getByText("范围：医保法规库")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole("button", { name: "搜索" }));

    expect(await screen.findByText("文档检索失败：请确认知识库检索服务可用后重试。")).toBeInTheDocument();
    expect(screen.queryByText("未找到匹配文档")).not.toBeInTheDocument();

    fireEvent.change(screen.getByRole("textbox", { name: "检索关键词" }), {
      target: { value: "修改后的关键词" }
    });
    fireEvent.click(screen.getByRole("button", { name: "重试检索" }));

    await waitFor(() => {
      expect(searchDocumentsMock).toHaveBeenCalledTimes(2);
    });
    expect(searchDocumentsMock).toHaveBeenLastCalledWith({
      query: "医保支付",
      limit: 10,
      titleOnly: false,
      sourceCollections: ["medical-insurance-laws"]
    });
    expect((await screen.findAllByText("重试后的医保依据")).length).toBeGreaterThan(0);
  });

  it("replaces pure search results and boundaries when AI+ finishes empty", async () => {
    searchDocumentsMock.mockResolvedValue({
      contract_version: "document-search-v1",
      query: "医保基金监管",
      effective_source_collections: [],
      items: [
        {
          id: "pure-search-old",
          chunk_id: "pure-search-old",
          title: "纯检索旧结果",
          source_collection: "medical-insurance-laws",
          source_label: "医保法规库",
          snippet: "这条结果不应残留到 AI+ 状态。",
          locator: { title: "纯检索旧结果" },
          score: 1,
          matched_by: ["bm25"],
          index_version_key: "index-v1",
          source_package_version_key: "package-v1",
          preview_url: "/api/v1/preview/pure-search-old"
        }
      ],
      store: { ready: true, backend: "unit-test" },
      boundaries: {
        production_write: false,
        provider_call: true,
        database_write: false,
        object_storage_write: false,
        query_history_write: false
      }
    });
    runKnowledgeQueryMock.mockResolvedValue(makeAiResponse());

    render(<DocumentsPage />);
    fireEvent.click(screen.getByRole("button", { name: "搜索" }));

    expect((await screen.findAllByText("纯检索旧结果")).length).toBeGreaterThan(0);
    expect(screen.getByText("文档检索 provider_call：是")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /检索AI\+/ }));

    expect(await screen.findByText("AI+ 已完成审证，但未返回可展示的引用文档。")).toBeInTheDocument();
    expect(screen.getByRole("status", { name: "AI+ 空状态" })).toHaveAttribute("aria-live", "polite");
    expect(screen.getByRole("status", { name: "AI+ 完成状态" })).toHaveAttribute("aria-live", "polite");
    expect(screen.queryByText("纯检索旧结果")).not.toBeInTheDocument();
    expect(screen.queryByText(/文档检索 provider_call：/)).not.toBeInTheDocument();
    expect(screen.getByText("AI+ provider_call：当前查询契约未独立提供")).toBeInTheDocument();
    expect(screen.getByText("AI+ generation_status：generated")).toBeInTheDocument();
    expect(screen.getByLabelText("当前检索状态")).toHaveTextContent("0 条匹配");
  });

  it("replaces a pure search error and retry when AI+ returns results", async () => {
    searchDocumentsMock.mockRejectedValue(new Error("409 search backend unavailable"));
    runKnowledgeQueryMock.mockResolvedValue(makeAiResponse({
      citations: [
        {
          citation_id: "ai-current-result",
          marker: "[1]",
          chunk_id: "ai-current-result",
          evidence_type: "法规依据",
          source_collection: "medical-insurance-laws",
          snippet: "AI+ 当前模式返回的结果。",
          locator: { title: "AI+ 当前结果" },
          index_version_key: "index-v1",
          source_package_version_key: "package-v1"
        }
      ]
    }));

    render(<DocumentsPage />);
    fireEvent.click(screen.getByRole("button", { name: "搜索" }));

    expect(await screen.findByText("文档检索失败：请确认知识库检索服务可用后重试。")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "重试检索" })).toBeInTheDocument();
    expect(screen.getByLabelText("当前检索状态")).toHaveTextContent("检索失败");

    fireEvent.click(screen.getByRole("button", { name: /检索AI\+/ }));

    expect((await screen.findAllByText("AI+ 当前结果")).length).toBeGreaterThan(0);
    expect(screen.queryByText("文档检索失败：请确认知识库检索服务可用后重试。")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "重试检索" })).not.toBeInTheDocument();
    expect(screen.queryByText(/文档检索 provider_call：/)).not.toBeInTheDocument();
    expect(screen.getByText("AI+ provider_call：当前查询契约未独立提供")).toBeInTheDocument();
    expect(screen.getByLabelText("当前检索状态")).not.toHaveTextContent("检索失败");
    expect(screen.getByLabelText("当前检索状态")).toHaveTextContent("1 条匹配");
  });

  it("announces AI+ errors as alerts", async () => {
    runKnowledgeQueryMock.mockRejectedValue(new Error("AI backend unavailable"));

    render(<DocumentsPage />);
    fireEvent.click(screen.getByRole("button", { name: /检索AI\+/ }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("AI+ 审证未完成：请确认问答服务可用后重试。");
    expect(screen.queryByText("未找到匹配文档")).not.toBeInTheDocument();
  });

  it("keeps source collection scope from the knowledge base entry through search and AI+ query", async () => {
    window.history.pushState({}, "", "/documents?source_collection=medical-insurance-laws&query=医保支付");
    searchDocumentsMock.mockResolvedValue({
      contract_version: "document-search-v1",
      query: "医保支付",
      effective_source_collections: ["medical-insurance-laws"],
      items: [],
      store: { ready: true, backend: "unit-test" },
      boundaries: {
        production_write: false,
        provider_call: false,
        database_write: false,
        object_storage_write: false,
        query_history_write: false
      }
    });
    runKnowledgeQueryMock.mockResolvedValue({
      contract_version: "knowledge-query-contract-v2",
      question: "医保支付",
      answer: "应核验医保基金支付依据。",
      confidence: "medium",
      fallback_used: false,
      generation_status: "generated",
      generation_failure_code: null,
      generation_http_status: null,
      model_alias: "kimi-2.7",
      model_status: "selected_provider",
      effective_source_collections: ["medical-insurance-laws"],
      basis_groups: [],
      citations: [
        {
          citation_id: "citation-1",
          marker: "[1]",
          chunk_id: "ai-chunk-1",
          evidence_type: "法规依据",
          source_collection: "medical-insurance-laws",
          snippet: "AI+ 返回的医保法规引用。",
          locator: { title: "AI+ 医保法规依据", date: "2026-07-08" },
          index_version_key: "index-v1",
          source_package_version_key: "package-v1"
        }
      ],
      personal_upload_matches: [
        {
          id: "upload-match-1",
          upload_id: "upload-1",
          name: "个人医保核验材料.pdf",
          extension: ".pdf",
          created_by: "auditor",
          indexed_at: "2026-07-08T00:00:00Z",
          chunk_index: 0,
          snippet: "个人材料中的医保支付核验片段。",
          score: 0.8,
          locator: { page: 2 }
        }
      ],
      query_log_index: 1,
      query_log_id: "query-log-1",
      agent_invocation_id: null
    });

    render(<DocumentsPage />);

    await waitFor(() => {
      expect(screen.getByText("范围：医保法规库")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole("button", { name: "搜索" }));

    await waitFor(() => {
      expect(searchDocumentsMock).toHaveBeenCalledWith({
        query: "医保支付",
        limit: 10,
        titleOnly: false,
        sourceCollections: ["medical-insurance-laws"]
      });
    });

    fireEvent.click(screen.getByRole("button", { name: /检索AI\+/ }));

    await waitFor(() => {
      expect(runKnowledgeQueryMock).toHaveBeenCalledWith({
        question: "医保支付",
        top_k: 5,
        title_only: false,
        source_collections: ["medical-insurance-laws"]
      });
    });
    expect((await screen.findAllByText("AI+ 医保法规依据")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("个人医保核验材料.pdf").length).toBeGreaterThan(0);
    expect(screen.getByText(/AI\+ provider_call：当前查询契约未独立提供/)).toBeInTheDocument();
    expect(screen.getByText(/AI\+ generation_status：generated/)).toBeInTheDocument();
    expect(screen.getByRole("status", { name: "AI+ 完成状态" })).toHaveAttribute("aria-live", "polite");
  });
});
