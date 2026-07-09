import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import GraphPage from "./page";

vi.mock("@/components/replica/use-replica-runtime", () => ({
  useReplicaGraphData: () => ({
    apiReadsEnabled: true,
    source: "api",
    status: "ready",
    issues: [],
    data: {
      title: "医疗审计知识工程",
      scope: "知识库、规则、疑点和报告的只读关系图。",
      nodes: [
        {
          id: "graph-node-project",
          label: "医疗审计知识工程",
          kind: "项目",
          metric: "2 类知识库",
          status: "已归集",
          description: "当前知识底座。",
          href: "/projects"
        },
        {
          id: "graph-source-medical-insurance-laws",
          label: "医保法规库",
          kind: "知识库",
          metric: "128 文档 / 600 chunks",
          status: "可引用",
          description: "医保法规、政策解释和处罚依据。",
          href: "/documents?source_collection=medical-insurance-laws",
          sourceCollection: "medical-insurance-laws",
          domain: "medical"
        }
      ],
      relations: [
        {
          id: "graph-medical-laws",
          sourceId: "graph-node-project",
          targetId: "graph-source-medical-insurance-laws",
          source: "医疗审计知识工程",
          relation: "包含",
          target: "医保法规库",
          evidence: "600 active embeddings",
          strength: "强"
        }
      ],
      metrics: {
        nodeCount: 2,
        nodeKindCount: 2,
        relationCount: 1,
        strongRelationCount: 1,
        pendingRelationCount: 0
      }
    }
  })
}));

describe("GraphPage", () => {
  afterEach(() => {
    window.history.pushState({}, "", "/graph");
  });

  it("keeps source collection scope from the knowledge base route", async () => {
    window.history.pushState({}, "", "/graph?source_collection=medical-insurance-laws");

    render(<GraphPage />);

    await waitFor(() => {
      expect(screen.getByText("当前范围：法规政策")).toBeInTheDocument();
    });
    expect(screen.getAllByRole("link", { name: "进入文档检索" })[0]).toHaveAttribute(
      "href",
      "/documents?source_collection=medical-insurance-laws"
    );
  });

  it("opens node details and preserves node source context in downstream links", async () => {
    render(<GraphPage />);

    fireEvent.click(within(screen.getByLabelText("图谱节点")).getByRole("button", { name: /医保法规库/ }));

    expect(screen.getByRole("heading", { name: "医保法规库" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "打开来源" })).toHaveAttribute(
      "href",
      "/documents?source_collection=medical-insurance-laws"
    );
    expect(screen.getAllByRole("link", { name: "进入文档检索" })[1]).toHaveAttribute(
      "href",
      "/documents?source_collection=medical-insurance-laws"
    );
    expect(screen.getByRole("link", { name: "进入 AI 对话" })).toHaveAttribute(
      "href",
      "/chat?question=%E8%AF%B7%E5%9F%BA%E4%BA%8E%E3%80%8C%E5%8C%BB%E4%BF%9D%E6%B3%95%E8%A7%84%E5%BA%93%E3%80%8D%E6%A2%B3%E7%90%86%E5%85%B3%E7%B3%BB%E5%92%8C%E5%AE%A1%E8%AE%A1%E4%BE%9D%E6%8D%AE&source_collection=medical-insurance-laws"
    );
  });

  it("selects relation evidence and focuses the target node", () => {
    render(<GraphPage />);

    const relationPanel = screen.getByLabelText("关系证据");
    fireEvent.click(within(relationPanel).getByRole("button", { name: /600 active embeddings/ }));

    expect(screen.getByRole("heading", { name: "医保法规库" })).toBeInTheDocument();
    expect(within(relationPanel).getAllByText("600 active embeddings").length).toBeGreaterThan(0);
  });
});
