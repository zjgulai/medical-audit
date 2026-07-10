import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchDocumentSourceCollections, runKnowledgeQuery } from "@/lib/api-client";

import { KnowledgeQueryWorkbench } from "./knowledge-query-workbench";

vi.mock("@/lib/api-client", () => ({
  fetchDocumentSourceCollections: vi.fn(async () => {
    throw new Error("catalog fixture intentionally unavailable");
  }),
  runKnowledgeQuery: vi.fn()
}));

const fetchDocumentSourceCollectionsMock = vi.mocked(fetchDocumentSourceCollections);
const runKnowledgeQueryMock = vi.mocked(runKnowledgeQuery);

describe("KnowledgeQueryWorkbench", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("exposes the contract-aligned source collection filters", async () => {
    render(<KnowledgeQueryWorkbench />);

    expect(screen.getAllByRole("checkbox")).toHaveLength(25);
    expect(screen.getByRole("checkbox", { name: /^法规政策/ })).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: /^综合政策/ })).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: /^城市市政/ })).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: /^农业水利/ })).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: /^个人上传材料/ })).toBeInTheDocument();
    expect(screen.queryByText("other-unclassified")).not.toBeInTheDocument();
    await waitFor(() => {
      expect(fetchDocumentSourceCollectionsMock).toHaveBeenCalled();
    });
  });

  it("runs a query through the API-first client and renders citations", async () => {
    runKnowledgeQueryMock.mockResolvedValue({
      contract_version: "knowledge-query-contract-v2",
      question: "医保基金审核依据",
      answer: "应核验诊疗记录、收费明细和政策依据。",
      confidence: "high",
      fallback_used: true,
      generation_status: "not_requested",
      generation_failure_code: null,
      effective_source_collections: ["medical-insurance-laws"],
      query_log_index: 7,
      basis_groups: [
        {
          evidence_type: "policy",
          title: "法规依据",
          items: [
            {
              citation_id: "C1",
              chunk_id: "11111111-1111-4111-8111-111111111111",
              source_collection: "medical-insurance-laws",
              snippet: "医疗机构应保留审核依据。",
              locator: { source_path: "全量法律/law.md", line_start: 1, line_end: 2 },
              index_version_key: "index-v1",
              source_package_version_key: "package-v1"
            }
          ]
        }
      ],
      citations: [
        {
          citation_id: "C1",
          marker: "[1]",
          chunk_id: "11111111-1111-4111-8111-111111111111",
          evidence_type: "policy",
          source_collection: "medical-insurance-laws",
          snippet: "医疗机构应保留审核依据。",
          locator: { source_path: "全量法律/law.md", line_start: 1, line_end: 2 },
          index_version_key: "index-v1",
          source_package_version_key: "package-v1"
        }
      ],
      personal_upload_matches: []
    });

    render(<KnowledgeQueryWorkbench />);

    fireEvent.change(screen.getByLabelText("审计问题"), {
      target: { value: "医保基金审核依据" }
    });
    fireEvent.click(screen.getByRole("checkbox", { name: /^法规政策/ }));
    fireEvent.click(screen.getByRole("button", { name: "执行查询" }));

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "医保基金审核依据" })).toBeInTheDocument();
    });

    expect(runKnowledgeQueryMock).toHaveBeenCalledWith({
      question: "医保基金审核依据",
      top_k: 5,
      source_collections: ["medical-insurance-laws"],
      topic: "medical-insurance-fund"
    });
    expect(screen.getByText("应核验诊疗记录、收费明细和政策依据。")).toBeInTheDocument();
    expect(screen.getByText("来源: medical-insurance-laws")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "核验原文" })).toHaveAttribute(
      "href",
      "/pages/preview/11111111-1111-4111-8111-111111111111"
    );
    expect(screen.getByRole("link", { name: "转入对话审证" })).toHaveAttribute(
      "href",
      "/chat?question=%E5%8C%BB%E4%BF%9D%E5%9F%BA%E9%87%91%E5%AE%A1%E6%A0%B8%E4%BE%9D%E6%8D%AE&source_collection=medical-insurance-laws"
    );
  });

  it("shows a conservative error state when the backend query fails", async () => {
    runKnowledgeQueryMock.mockRejectedValue(new Error("backend failed"));

    render(<KnowledgeQueryWorkbench />);

    fireEvent.click(screen.getByRole("button", { name: "执行查询" }));

    await waitFor(() => {
      expect(screen.getByText("查询失败。请确认后端检索已就绪后重试。")).toBeInTheDocument();
    });
  });
});
