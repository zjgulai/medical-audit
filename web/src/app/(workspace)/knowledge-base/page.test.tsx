import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ReplicaRuntimeResult } from "@/components/replica/use-replica-runtime";
import type { ReplicaKnowledgeBaseData } from "@/lib/replica-adapters";

import KnowledgeBasePage from "./page";

const runtimeMock = vi.hoisted(() => ({
  current: null as unknown as ReplicaRuntimeResult<ReplicaKnowledgeBaseData>
}));

const HUMAN_KNOWLEDGE_LABEL = "医院医保审计依据库";
const INTERNAL_SOURCE_SENTINEL = "medical-insurance-laws";
const INTERNAL_ACCESS_SENTINEL = "explicit-read-all";
const INTERNAL_METADATA_SENTINELS = {
  sourceCollection: INTERNAL_SOURCE_SENTINEL,
  access: INTERNAL_ACCESS_SENTINEL
} as const;

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
          ...INTERNAL_METADATA_SENTINELS,
          id: `kb-${INTERNAL_SOURCE_SENTINEL}`,
          name: HUMAN_KNOWLEDGE_LABEL,
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
              label: HUMAN_KNOWLEDGE_LABEL,
              description: "医保法规、政策解释和处罚依据。",
              scope: "系统",
              queryable: true
            }
          ]
        }
      ],
      readableSourceCollections: [HUMAN_KNOWLEDGE_LABEL],
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

    expect(screen.getAllByRole("heading", { name: HUMAN_KNOWLEDGE_LABEL, level: 2 }).length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: "打开目录" })).toHaveAttribute(
      "href",
      `/documents?source_collection=${INTERNAL_SOURCE_SENTINEL}`
    );
    expect(screen.getByRole("link", { name: "进入 AI 对话" })).toHaveAttribute(
      "href",
      `/chat?question=${encodeURIComponent(`请基于「${HUMAN_KNOWLEDGE_LABEL}」回答审计问题`)}&source_collection=${INTERNAL_SOURCE_SENTINEL}`
    );
    expect(screen.getByRole("link", { name: "查看图谱" })).toHaveAttribute(
      "href",
      `/graph?source_collection=${INTERNAL_SOURCE_SENTINEL}`
    );
    expect(screen.getByRole("link", { name: "检索全部目录" })).toHaveAttribute(
      "href",
      `/documents?source_collection=${INTERNAL_SOURCE_SENTINEL}`
    );
    expect(screen.getByRole("link", { name: "查看全部图谱" })).toHaveAttribute(
      "href",
      `/graph?source_collection=${INTERNAL_SOURCE_SENTINEL}`
    );
    expect(screen.queryByText(INTERNAL_SOURCE_SENTINEL)).not.toBeInTheDocument();
    expect(screen.queryByText(INTERNAL_ACCESS_SENTINEL)).not.toBeInTheDocument();
    expect(screen.getAllByText("49,051").length).toBeGreaterThan(0);
    expect(screen.getAllByText("120").length).toBeGreaterThan(0);
    expect(screen.getByText("来自当前知识目录")).toBeInTheDocument();
    expect(screen.getByText("知识目录")).toBeInTheDocument();
    expect(screen.getByText("当前可用于检索的知识片段数量")).toBeInTheDocument();
    expect(screen.queryByText(/后端目录/)).not.toBeInTheDocument();
    expect(screen.queryByText("样例")).not.toBeInTheDocument();
    expect(screen.getByLabelText("知识库发布覆盖")).toHaveAttribute(
      "data-knowledge-release-scope",
      "core-5"
    );
    expect(screen.getByLabelText("知识库发布覆盖")).toHaveAttribute(
      "data-coverage-status",
      "core-incomplete"
    );
    expect(screen.getByText(/已装载 1 \/ 1 个注册集合/)).toBeInTheDocument();
  });

  it("labels five populated collections as core-ready without claiming full registry coverage", () => {
    const ready = makeMetricsReadyRuntime();
    const sourceIds = [
      "medical-insurance-laws",
      "supervision-rules-knowledge",
      "medical-insurance-catalog",
      "risk-negative-list",
      "personal-materials"
    ] as const;
    runtimeMock.current = {
      ...ready,
      data: {
        ...ready.data,
        knowledgeBases: sourceIds.map((sourceId, index) => ({
          ...ready.data.knowledgeBases[0]!,
          id: `kb-${sourceId}`,
          name: `核心知识集合 ${index + 1}`,
          documentCount: index + 1,
          chunkCount: (index + 1) * 10
        })),
        summary: {
          ...ready.data.summary!,
          sourceCollectionCount: 25,
          queryableCollectionCount: 5
        }
      }
    };

    render(<KnowledgeBasePage />);

    const coverage = screen.getByLabelText("知识库发布覆盖");
    expect(coverage).toHaveAttribute("data-coverage-status", "core-ready");
    expect(within(coverage).getByText(/已装载 5 \/ 25 个注册集合/)).toBeInTheDocument();
    expect(within(coverage).getByText(/本次仅承诺核心范围/)).toBeInTheDocument();
    expect(within(coverage).queryByText(/全量可用/)).not.toBeInTheDocument();
  });

  it("keeps coverage incomplete when five populated collections omit a required core source", () => {
    const ready = makeMetricsReadyRuntime();
    const sourceIds = [
      "medical-insurance-laws",
      "supervision-rules-knowledge",
      "medical-insurance-catalog",
      "risk-negative-list",
      "other-agriculture-water"
    ] as const;
    runtimeMock.current = {
      ...ready,
      data: {
        ...ready.data,
        knowledgeBases: sourceIds.map((sourceId, index) => ({
          ...ready.data.knowledgeBases[0]!,
          id: `kb-${sourceId}`,
          name: `知识集合 ${index + 1}`,
          documentCount: index + 1,
          chunkCount: (index + 1) * 10
        })),
        summary: {
          ...ready.data.summary!,
          sourceCollectionCount: 25,
          queryableCollectionCount: 5
        }
      }
    };

    render(<KnowledgeBasePage />);

    const coverage = screen.getByLabelText("知识库发布覆盖");
    expect(coverage).toHaveAttribute("data-coverage-status", "core-incomplete");
    expect(within(coverage).getByText(/尚未达到核心 5 个知识集合的发布门槛/)).toBeInTheDocument();
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
    const cardHeading = screen.getAllByRole("heading", { name: HUMAN_KNOWLEDGE_LABEL, level: 2 })[0];
    const card = cardHeading.closest("article");
    expect(card).not.toBeNull();
    expect(within(card as HTMLElement).getAllByText("待同步").length).toBeGreaterThanOrEqual(2);
    expect(within(card as HTMLElement).queryByText(/^0$/)).not.toBeInTheDocument();
    expect(within(card as HTMLElement).queryByText("0 个片段")).not.toBeInTheDocument();
    expect(within(screen.getByLabelText("知识库数据口径")).getAllByText("待同步").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByLabelText("知识库发布覆盖")).toHaveAttribute(
      "data-coverage-status",
      "unknown"
    );
  });

  it("does not present a partial category sum when any item metric is unavailable", () => {
    const ready = makeMetricsReadyRuntime();
    runtimeMock.current = {
      ...ready,
      apiReadsEnabled: false,
      source: "fixture",
      data: {
        ...ready.data,
        knowledgeBases: [
          ready.data.knowledgeBases[0]!,
          {
            ...ready.data.knowledgeBases[0]!,
            id: "kb-review-partial-medical-policy",
            name: "医保政策补充库",
            documentCount: null,
            chunkCount: null,
            appCount: null
          }
        ],
        currentSearchEmbeddingCount: null,
        metricsSource: "unavailable",
        summary: null,
        store: null,
        boundaries: null
      }
    };

    render(<KnowledgeBasePage />);

    const categoryTitle = within(screen.getByLabelText("知识库分类卡片")).getByText("医疗领域法律法规");
    const categoryCard = categoryTitle.closest("button");
    expect(categoryCard).not.toBeNull();
    expect(categoryCard as HTMLButtonElement).toHaveTextContent("待同步 · 待同步");
    expect(categoryCard as HTMLButtonElement).not.toHaveTextContent("12 份文档");
    expect(categoryCard as HTMLButtonElement).not.toHaveTextContent("120 个片段");
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
