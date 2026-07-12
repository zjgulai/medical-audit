import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ReplicaRuntimeResult } from "@/components/replica/use-replica-runtime";
import type { ReplicaKnowledgeBaseData } from "@/lib/replica-adapters";

import KnowledgeBasePage from "./page";

const runtimeMock = vi.hoisted(() => ({
  current: null as unknown as ReplicaRuntimeResult<ReplicaKnowledgeBaseData>
}));

vi.mock("@/components/replica/use-replica-runtime", () => ({
  useReplicaKnowledgeBaseData: () => runtimeMock.current
}));

function makeMetricsReadyRuntime(): ReplicaRuntimeResult<ReplicaKnowledgeBaseData> {
  return {
    apiReadsEnabled: true,
    source: "api",
    outcome: "ready",
    status: "ready",
    issues: [],
    data: {
      knowledgeBases: [
        {
          id: "kb-medical-insurance-laws",
          name: "医保法规库",
          scope: "公开知识库",
          owner: "审计中心",
          documentCount: 12,
          chunkCount: 120,
          appCount: 2,
          updatedAt: "active",
          description: "医保法规、政策解释和处罚依据。",
          tags: ["医保", "法规"]
        }
      ],
      sourceGroups: [
        {
          title: "医疗医保",
          options: [
            {
              value: "medical-insurance-laws",
              label: "医保法规库",
              description: "医保法规、政策解释和处罚依据。",
              scope: "系统",
              queryable: true
            }
          ]
        }
      ],
      readableSourceCollections: ["医保法规库"],
      canUploadPersonal: true,
      currentSearchEmbeddingCount: 49051,
      metricsSource: "knowledge-base-catalog",
      summary: {
        sourceCollectionCount: 1,
        queryableCollectionCount: 1,
        totalDocumentCount: 12,
        totalChunkCount: 120,
        totalEmbeddingCount: 120,
        currentSearchEmbeddingCount: 49051,
        candidateChunkCount: 0,
        domainCounts: { 医保: 1 }
      },
      store: {
        ready: true,
        catalogReady: true,
        metricsReady: true,
        backend: "runtime_state_and_postgres_catalog"
      },
      boundaries: {
        productionWrite: false,
        providerCall: false,
        databaseWrite: false,
        objectStorageWrite: false,
        queryHistoryWrite: false,
        source: "runtime_state_and_postgres_catalog"
      }
    }
  };
}

function makeUnavailableRuntime(
  status: "empty" | "error"
): ReplicaRuntimeResult<ReplicaKnowledgeBaseData> {
  return {
    apiReadsEnabled: true,
    source: "api",
    outcome: status,
    status,
    issues: [],
    data: {
      knowledgeBases: [],
      sourceGroups: [],
      readableSourceCollections: [],
      canUploadPersonal: false,
      currentSearchEmbeddingCount: null,
      metricsSource: "unavailable",
      summary: null,
      store: null,
      boundaries: null
    }
  };
}

beforeEach(() => {
  runtimeMock.current = makeMetricsReadyRuntime();
});

describe("KnowledgeBasePage", () => {
  it("renders metrics-ready totals and preserves source-scoped links", () => {
    render(<KnowledgeBasePage />);

    expect(screen.getByRole("link", { name: "打开目录" })).toHaveAttribute(
      "href",
      "/documents?source_collection=medical-insurance-laws"
    );
    expect(screen.getByRole("link", { name: "进入 AI 对话" })).toHaveAttribute(
      "href",
      "/chat?question=%E8%AF%B7%E5%9F%BA%E4%BA%8E%E3%80%8C%E5%8C%BB%E4%BF%9D%E6%B3%95%E8%A7%84%E5%BA%93%E3%80%8D%E5%9B%9E%E7%AD%94%E5%AE%A1%E8%AE%A1%E9%97%AE%E9%A2%98&source_collection=medical-insurance-laws"
    );
    expect(screen.getByRole("link", { name: "查看图谱" })).toHaveAttribute(
      "href",
      "/graph?source_collection=medical-insurance-laws"
    );
    expect(screen.getByRole("link", { name: "检索全部目录" })).toHaveAttribute(
      "href",
      "/documents?source_collection=medical-insurance-laws"
    );
    expect(screen.getByRole("link", { name: "查看全部图谱" })).toHaveAttribute(
      "href",
      "/graph?source_collection=medical-insurance-laws"
    );
    expect(screen.getAllByText("49,051").length).toBeGreaterThan(0);
    expect(screen.getAllByText("120").length).toBeGreaterThan(0);
    expect(screen.queryByText("样例")).not.toBeInTheDocument();
  });

  it("keeps registry cards while marking every unavailable metric as pending sync", () => {
    const ready = makeMetricsReadyRuntime();
    runtimeMock.current = {
      ...ready,
      outcome: "degraded",
      status: "degraded",
      data: {
        ...ready.data,
        knowledgeBases: ready.data.knowledgeBases.map((item) => ({
          ...item,
          documentCount: null,
          chunkCount: null,
          appCount: null
        })),
        currentSearchEmbeddingCount: null,
        metricsSource: "unavailable",
        summary: {
          ...ready.data.summary!,
          totalDocumentCount: null,
          totalChunkCount: null,
          totalEmbeddingCount: null,
          currentSearchEmbeddingCount: null,
          candidateChunkCount: null
        },
        store: {
          ready: false,
          catalogReady: true,
          metricsReady: false,
          backend: "runtime_state_and_registry_only"
        },
        boundaries: {
          ...ready.data.boundaries!,
          source: "runtime_state_and_registry_only"
        }
      }
    };

    render(<KnowledgeBasePage />);

    expect(screen.getByRole("main")).toHaveAttribute("data-replica-status", "degraded");
    const cardHeading = screen.getAllByRole("heading", { name: "医保法规库", level: 2 })[0];
    const card = cardHeading.closest("article");
    expect(card).not.toBeNull();
    expect(within(card as HTMLElement).getAllByText("待同步").length).toBeGreaterThanOrEqual(2);
    expect(within(card as HTMLElement).queryByText(/^0$/)).not.toBeInTheDocument();
    expect(within(card as HTMLElement).queryByText("0 个片段")).not.toBeInTheDocument();
    expect(within(screen.getByLabelText("知识库数据口径")).getAllByText("待同步").length).toBeGreaterThanOrEqual(2);
  });

  it("uses a catalog-empty message instead of search-no-result copy", () => {
    runtimeMock.current = makeUnavailableRuntime("empty");

    render(<KnowledgeBasePage />);

    expect(screen.getByText("暂无可用知识库")).toBeInTheDocument();
    expect(screen.queryByText("未找到知识库")).not.toBeInTheDocument();
    expect(screen.queryByText("知识库读取失败")).not.toBeInTheDocument();
  });

  it("uses a distinct API failure message", () => {
    runtimeMock.current = makeUnavailableRuntime("error");

    render(<KnowledgeBasePage />);

    expect(screen.getByText("知识库读取失败")).toBeInTheDocument();
    expect(screen.queryByText("暂无可用知识库")).not.toBeInTheDocument();
    expect(screen.queryByText("未找到知识库")).not.toBeInTheDocument();
  });
});
