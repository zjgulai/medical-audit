import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { createAuditAgent } from "@/lib/api-client";
import type { AgentCreateRequest } from "@/lib/api-types";

import { ReplicaAgentDirectory } from "./replica-agent-directory";

vi.mock("@/lib/api-client", () => ({
  createAuditAgent: vi.fn(async (payload: AgentCreateRequest) => ({
    item: {
      id: "agent-installed-001",
      name: payload.name,
      category: payload.category,
      topic: payload.topic,
      prompt: payload.prompt,
      knowledge_base: payload.knowledge_base,
      project_name: payload.project_name,
      status: "active",
      prompt_version: 1,
      prompt_version_key: "agent-installed-001@v1",
      visibility_scope: "project",
      allowed_roles: payload.allowed_roles,
      prompt_versions: [],
      created_by: "next-admin",
      updated_at: "2026-07-06T00:00:00Z",
      source: "custom",
      metadata: payload.metadata
    },
    store: { ready: true, backend: "SqlAlchemyAgentStore" }
  }))
}));

vi.mock("./use-replica-runtime", () => ({
  useReplicaAgentsData: () => ({
    apiReadsEnabled: false,
    source: "fixture",
    status: "ready",
    issues: [],
    data: {
      categories: ["业务类"],
      agents: [
        {
          id: "template-medical-fund",
          name: "医保核验",
          category: "业务类",
          summary: "核验医保目录限制、结算明细和疑点依据。",
          project: "智能体广场",
          topic: "医保基金使用合规",
          initial: "医",
          tone: "blue"
        }
      ]
    }
  })
}));

describe("ReplicaAgentDirectory", () => {
  it("installs a market template through the audit agent API", async () => {
    render(<ReplicaAgentDirectory mode="market" />);

    fireEvent.click(screen.getByRole("button", { name: "创建副本：医保核验" }));

    await waitFor(() => {
      expect(createAuditAgent).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "医保核验",
          category: "业务类",
          topic: "医保基金使用合规",
          knowledge_base: "医保基金合规知识库",
          project_name: "医保基金使用合规专项自查",
          visibility_scope: "project",
          metadata: expect.objectContaining({
            source: "agent-market",
            template_id: "template-medical-fund",
            template_project: "智能体广场",
            avatar_initial: "医"
          })
        })
      );
    });
    expect(await screen.findByText(/已安装「医保核验」/)).toBeInTheDocument();
  });
});
