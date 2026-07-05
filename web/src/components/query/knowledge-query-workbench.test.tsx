import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiClientError, runKnowledgeQuery } from "@/lib/api-client";

import { KnowledgeQueryWorkbench } from "./knowledge-query-workbench";

vi.mock("@/lib/api-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api-client")>();
  return {
    ...actual,
    runKnowledgeQuery: vi.fn()
  };
});

const runKnowledgeQueryMock = vi.mocked(runKnowledgeQuery);

describe("KnowledgeQueryWorkbench", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("runs a query through the API-first client and renders citations", async () => {
    runKnowledgeQueryMock.mockResolvedValue({
      question: "医保基金审核依据",
      answer: "应核验诊疗记录、收费明细和政策依据。",
      confidence: "high",
      fallback_used: true,
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
    fireEvent.change(screen.getByLabelText("年份"), { target: { value: "2024, 2025" } });
    fireEvent.change(screen.getByLabelText("地区"), { target: { value: "国家, 广东" } });
    fireEvent.change(screen.getByLabelText("文档类型"), { target: { value: "law, regulation" } });
    fireEvent.change(screen.getByLabelText("业务主题"), {
      target: { value: "fund-supervision" }
    });
    fireEvent.click(screen.getByRole("button", { name: "执行查询" }));

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "医保基金审核依据" })).toBeInTheDocument();
    });

    expect(runKnowledgeQueryMock).toHaveBeenCalledWith({
      question: "医保基金审核依据",
      top_k: 5,
      source_collections: ["medical-insurance-laws"],
      years: [2024, 2025],
      regions: ["国家", "广东"],
      document_types: ["law", "regulation"],
      business_topics: ["fund-supervision"],
      topic: "medical-insurance-fund"
    });
    expect(screen.getByText("应核验诊疗记录、收费明细和政策依据。")).toBeInTheDocument();
    expect(screen.getByText("实际检索范围")).toBeInTheDocument();
    expect(screen.getByText("来源: medical-insurance-laws")).toBeInTheDocument();
    expect(screen.getByText("index-v1")).toBeInTheDocument();
    expect(screen.getByText("package-v1")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "核验原文" })).toHaveAttribute(
      "href",
      "/pages/preview/11111111-1111-4111-8111-111111111111"
    );
    expect(screen.getByRole("link", { name: "转入对话审证" })).toHaveAttribute(
      "href",
      "/chat?question=%E5%8C%BB%E4%BF%9D%E5%9F%BA%E9%87%91%E5%AE%A1%E6%A0%B8%E4%BE%9D%E6%8D%AE&source_collection=medical-insurance-laws&year=2024&year=2025&region=%E5%9B%BD%E5%AE%B6&region=%E5%B9%BF%E4%B8%9C&document_type=law&document_type=regulation&business_topic=fund-supervision"
    );
  });

  it("shows a local preview fallback when the search index is unavailable", async () => {
    runKnowledgeQueryMock.mockRejectedValue(
      new ApiClientError({
        code: "search-engine-not-initialized",
        detail: "search engine is not initialized",
        method: "POST",
        path: "/api/v1/query",
        status: 409
      })
    );

    render(<KnowledgeQueryWorkbench />);

    fireEvent.click(screen.getByRole("button", { name: "执行查询" }));

    await waitFor(() => {
      expect(screen.getByText("本地预览依据")).toBeInTheDocument();
    });
    expect(screen.getByText(/当前为本地重构站预览结果/)).toBeInTheDocument();
    expect(screen.getByText("fallback: yes")).toBeInTheDocument();
  });
});
