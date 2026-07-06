import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { runKnowledgeQuery } from "@/lib/api-client";

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
  runKnowledgeQuery: vi.fn()
}));

const runKnowledgeQueryMock = vi.mocked(runKnowledgeQuery);

describe("DocumentsPage", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("keeps the first render read-only for knowledge query side effects", () => {
    render(<DocumentsPage />);

    expect(screen.getByRole("heading", { name: "文档检索" })).toBeInTheDocument();
    expect(runKnowledgeQueryMock).not.toHaveBeenCalled();
  });

  it("runs knowledge query after an explicit search action", async () => {
    runKnowledgeQueryMock.mockResolvedValue({
      contract_version: "knowledge-query-contract-v2",
      question: "医保支付",
      answer: "命中医保支付政策。",
      confidence: "medium",
      fallback_used: false,
      effective_source_collections: ["medical-insurance-laws"],
      basis_groups: [],
      citations: [
        {
          citation_id: "citation-1",
          marker: "[1]",
          chunk_id: "chunk-1",
          evidence_type: "医保法规库",
          source_collection: "medical-insurance-laws",
          snippet: "医保支付政策引用片段。",
          locator: { title: "医保支付政策", date: "2026-07-06" },
          index_version_key: null,
          source_package_version_key: null
        }
      ],
      personal_upload_matches: [],
      query_log_index: 1,
      query_log_id: "query-log-1",
      agent_invocation_id: null
    });

    render(<DocumentsPage />);

    fireEvent.click(screen.getByRole("button", { name: "搜索" }));

    await waitFor(() => {
      expect(runKnowledgeQueryMock).toHaveBeenCalledWith({
        question: "劳动争议司法案件解释",
        top_k: 5,
        title_only: false
      });
    });
    expect(await screen.findAllByText("医保支付政策")).toHaveLength(2);
  });
});
