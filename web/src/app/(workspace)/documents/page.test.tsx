import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { runKnowledgeQuery, searchDocuments } from "@/lib/api-client";

import DocumentsPage from "./page";

vi.mock("@/components/replica/use-replica-runtime", () => ({
  useReplicaDocumentsData: () => ({
    source: "hybrid",
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
  })
}));

vi.mock("@/lib/api-client", () => ({
  runKnowledgeQuery: vi.fn(),
  searchDocuments: vi.fn()
}));

const runKnowledgeQueryMock = vi.mocked(runKnowledgeQuery);
const searchDocumentsMock = vi.mocked(searchDocuments);

describe("DocumentsPage", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("keeps the first render read-only for knowledge query side effects", () => {
    render(<DocumentsPage />);

    expect(screen.getByRole("heading", { name: "文档检索" })).toBeInTheDocument();
    expect(runKnowledgeQueryMock).not.toHaveBeenCalled();
    expect(searchDocumentsMock).not.toHaveBeenCalled();
  });

  it("runs read-only document search after an explicit search action", async () => {
    searchDocumentsMock.mockResolvedValue({
      contract_version: "document-search-v1",
      query: "劳动争议司法案件解释",
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

    await waitFor(() => {
      expect(searchDocumentsMock).toHaveBeenCalledWith({
        query: "劳动争议司法案件解释",
        limit: 10,
        titleOnly: false,
        sourceCollections: []
      });
    });
    expect(await screen.findAllByText("医保支付政策")).toHaveLength(2);
    expect(runKnowledgeQueryMock).not.toHaveBeenCalled();
  });
});
