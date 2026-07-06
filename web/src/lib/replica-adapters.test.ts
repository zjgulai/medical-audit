import { describe, expect, it, vi } from "vitest";

import type { AgentsResponse } from "./api-types";
import { loadReplicaAgentMarketData } from "./replica-adapters";
import { referenceMarketAgents } from "./reference-replica-data";

describe("loadReplicaAgentMarketData", () => {
  it("keeps the market catalog on prompt-source categories when the API returns old seed agents", async () => {
    const fetchAgents = vi.fn(async (): Promise<AgentsResponse> => ({
      items: [
        {
          id: "seed-legacy-business",
          name: "旧业务助手",
          category: "业务类",
          topic: "旧专题",
          prompt: "旧系统默认提示词",
          knowledge_base: "旧知识库",
          project_name: "旧项目",
          status: "active",
          prompt_version: 1,
          prompt_version_key: "seed-legacy-business@v1",
          visibility_scope: "system",
          allowed_roles: ["admin"],
          prompt_versions: [],
          created_by: "system",
          updated_at: "2026-07-06T00:00:00Z",
          source: "system-default",
          metadata: {}
        }
      ],
      categories: ["业务类", "效率类", "研究类"],
      store: { ready: true, backend: "SqlAlchemyAgentStore" }
    }));

    const result = await loadReplicaAgentMarketData({ fetchAgents });

    expect(fetchAgents).toHaveBeenCalledTimes(1);
    expect(result.data.agents).toHaveLength(referenceMarketAgents.length);
    expect(result.data.categories).toEqual([
      "财务收支审计",
      "采购招标审计",
      "工程审计",
      "工具智能体",
      "固定资产审计",
      "审计科研"
    ]);
    expect(result.data.categories).not.toContain("业务类");
    expect(result.data.agents.some((agent) => agent.id === "seed-legacy-business")).toBe(false);
  });
});
