import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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
      categories: ["财务收支审计", "采购招标审计", "工程审计"],
      agents: [
        makeAgent("template-medical-fund", "医保核验", "财务收支审计", "医保基金使用合规"),
        makeAgent("template-travel", "出国核验", "财务收支审计", "财务收支审计"),
        makeAgent("template-meeting", "会议核验", "财务收支审计", "会议费审计"),
        makeAgent("template-procurement", "招标核验", "采购招标审计", "采购招标审计"),
        makeAgent("template-bid", "定标核验", "采购招标审计", "定标复核"),
        makeAgent("template-engineering", "工程核验", "工程审计", "工程审计"),
        makeAgent("template-asset", "资产核验", "固定资产审计", "资产审计"),
        makeAgent("template-research", "科研核验", "审计科研", "审计科研")
      ]
    }
  })
}));

function makeAgent(id: string, name: string, category: string, topic: string) {
  return {
    id,
    name,
    category,
    summary: `${name}用于核验审计资料、证据链和风险描述。`,
    project: "智能体广场",
    topic,
    initial: name.slice(0, 1),
    tone: "blue",
    prompt: `## ${name}\n请围绕${topic}输出风险判断、证据依据和待补材料。`,
    sourceFile: `${category}.ods`
  };
}

describe("ReplicaAgentDirectory", () => {
  it("uses prompt source categories and paginates market cards", () => {
    render(<ReplicaAgentDirectory mode="market" />);

    expect(screen.getByRole("button", { name: /财务收支审计/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /采购招标审计/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^业务类/ })).not.toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /^详情：/ })).toHaveLength(6);

    fireEvent.click(screen.getByRole("button", { name: "下一页" }));
    expect(screen.getByRole("button", { name: "详情：资产核验" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /采购招标审计/ }));
    expect(screen.getByRole("button", { name: "详情：招标核验" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "详情：医保核验" })).not.toBeInTheDocument();
  });

  it("opens prompt details and installs a market template through the audit agent API", async () => {
    render(<ReplicaAgentDirectory mode="market" />);

    fireEvent.click(screen.getByRole("button", { name: "详情：医保核验" }));

    expect(screen.getByRole("dialog", { name: "医保核验" })).toBeInTheDocument();
    expect(screen.getByText("提示词")).toBeInTheDocument();
    expect(screen.getByText(/请围绕医保基金使用合规输出风险判断/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "收藏：医保核验" }));
    expect(screen.getByRole("button", { name: "收藏：医保核验" })).toHaveTextContent("取消收藏");

    fireEvent.click(screen.getByRole("button", { name: "加入我的智能体：医保核验" }));

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
            template_original_category: "财务收支审计",
            template_project: "智能体广场",
            avatar_initial: "医"
          })
        })
      );
    });
    expect(await screen.findByText(/已安装「医保核验」/)).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "进入 AI 对话" }).map((item) => item.getAttribute("href"))).toContain(
      "/chat?agent=agent-installed-001"
    );
    expect(within(screen.getByRole("dialog", { name: "医保核验" })).getByRole("link", { name: "进入 AI 对话" })).toHaveAttribute(
      "href",
      "/chat?agent=agent-installed-001"
    );
  });
});
