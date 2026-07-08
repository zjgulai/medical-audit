import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import KnowledgeBasePage from "./page";

vi.mock("@/components/replica/use-replica-runtime", () => ({
  useReplicaKnowledgeBaseData: () => ({
    apiReadsEnabled: true,
    source: "api",
    status: "ready",
    issues: [],
    data: {
      knowledgeBases: [
        {
          id: "kb-medical-insurance-laws",
          name: "医保法规库",
          scope: "公开知识库",
          owner: "审计中心",
          documentCount: 128,
          appCount: 3,
          updatedAt: "2026-07-08",
          description: "医保法规、政策解释和处罚依据。",
          tags: ["医保", "法规"]
        }
      ],
      sourceGroups: [
        {
          id: "medical",
          title: "医疗医保",
          description: "医保审计相关知识库",
          options: [
            {
              value: "medical-insurance-laws",
              label: "医保法规库",
              description: "医保法规、政策解释和处罚依据。"
            }
          ]
        }
      ],
      readableSourceCollections: ["medical-insurance-laws"],
      canUploadPersonal: true
    }
  })
}));

describe("KnowledgeBasePage", () => {
  it("links a knowledge base into documents and chat with source context", () => {
    render(<KnowledgeBasePage />);

    expect(screen.getByRole("link", { name: "打开目录" })).toHaveAttribute(
      "href",
      "/documents?source_collection=medical-insurance-laws"
    );
    expect(screen.getByRole("link", { name: "进入 AI 对话" })).toHaveAttribute(
      "href",
      "/chat?question=%E8%AF%B7%E5%9F%BA%E4%BA%8E%E3%80%8C%E5%8C%BB%E4%BF%9D%E6%B3%95%E8%A7%84%E5%BA%93%E3%80%8D%E5%9B%9E%E7%AD%94%E5%AE%A1%E8%AE%A1%E9%97%AE%E9%A2%98&source_collection=medical-insurance-laws"
    );
  });
});
