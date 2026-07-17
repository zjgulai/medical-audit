import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchRulesWorkbench } from "@/lib/api-client";
import type { RulesWorkbenchResponse } from "@/lib/api-types";

import { ReplicaRulesWorkbench } from "./replica-rules-workbench";

vi.mock("@/lib/api-client", () => ({
  fetchRulesWorkbench: vi.fn()
}));

const fetchRulesWorkbenchMock = vi.mocked(fetchRulesWorkbench);

const rulesResponse: RulesWorkbenchResponse = {
  format: "rules-workbench-v1",
  generated_at: "2026-07-16T09:00:00Z",
  ruleset_id: "runtime-ruleset-001",
  ruleset_title: "医保审计规则库",
  ruleset_scope: "医保基金使用合规",
  rule_library_items: [
    {
      id: "rule-item-001",
      code: "runtime-rule-001",
      name: "重复收费识别",
      domain: "收费明细",
      status: "已启用",
      sourceCollection: "医保政策库",
      evidenceScope: "收费明细与结算记录",
      evidenceCount: 12,
      findingCount: 3,
      owner: "内审部",
      updatedAt: "2026-07-16T08:30:00Z",
      href: "/rules/runtime-rule-001",
      chatHref: "/chat?rule=runtime-rule-001"
    }
  ],
  source_coverages: [
    {
      id: "source-001",
      name: "医保政策库",
      sourceCollection: "医保政策",
      ruleCount: 1,
      indexStatus: "可引用",
      health: "正常",
      href: "/documents"
    }
  ],
  run_snapshots: [
    {
      id: "run-001",
      ruleCode: "runtime-rule-001",
      inputTable: "settlement_detail",
      lastRunAt: "2026-07-16T08:00:00Z",
      hitCount: 3,
      linkedFinding: "finding-runtime-001",
      nextAction: "进入疑点复核"
    }
  ],
  control_gates: [
    {
      id: "gate-fields",
      label: "字段可运行",
      status: "通过",
      detail: "运行字段已完成只读校验。",
      owner: "信息科"
    }
  ],
  metrics: {
    rule_count: 1,
    enabled_rule_count: 1,
    pending_rule_count: 0,
    total_finding_count: 3,
    blocked_gate_count: 0,
    source_count: 1,
    run_count: 1
  },
  evidence_grade: "production-readonly-api",
  production_side_effect: "none",
  store: { ready: true, backend: "SqlAlchemyRulesWorkbenchStore" }
};

describe("ReplicaRulesWorkbench", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders runtime rules instead of the retired hard-coded totals", async () => {
    fetchRulesWorkbenchMock.mockResolvedValue(rulesResponse);

    render(<ReplicaRulesWorkbench />);

    expect(await screen.findByText("runtime-rule-001")).toBeInTheDocument();
    expect(screen.getByText("字段可运行")).toBeInTheDocument();
    expect(screen.getByText("当前为只读规则数据，页面不会触发规则运行或生产写入。")).toBeInTheDocument();
    const diagnostics = screen.getByText("SqlAlchemyRulesWorkbenchStore").closest("details");
    expect(diagnostics).not.toBeNull();
    expect(diagnostics).not.toHaveAttribute("open");
    expect(screen.getByText("production-readonly-api").closest("details")).toBe(diagnostics);
    expect(screen.getByText("none").closest("details")).toBe(diagnostics);
    expect(screen.getByText("医保政策库", { selector: "h3" })).toBeInTheDocument();
    expect(screen.getByText("run-001")).toBeInTheDocument();
    expect(screen.queryByText("2,546")).not.toBeInTheDocument();
    expect(screen.queryByText("49,051")).not.toBeInTheDocument();
    expect(screen.queryByText("128")).not.toBeInTheDocument();
  });

  it("does not render zero metrics while the initial read is pending", () => {
    fetchRulesWorkbenchMock.mockReturnValue(new Promise(() => undefined));

    render(<ReplicaRulesWorkbench />);

    expect(screen.getByText("规则数据加载中")).toBeInTheDocument();
    expect(screen.queryByText("规则总数")).not.toBeInTheDocument();
  });

  it("uses the strict empty contract for an empty rule library and run history", async () => {
    fetchRulesWorkbenchMock.mockResolvedValue({
      ...rulesResponse,
      rule_library_items: [],
      run_snapshots: [],
      metrics: {
        ...rulesResponse.metrics,
        rule_count: 0,
        enabled_rule_count: 0,
        run_count: 0
      }
    });

    render(<ReplicaRulesWorkbench />);

    expect(await screen.findByText("暂无规则与运行记录")).toBeInTheDocument();
    expect(screen.getByText("字段可运行")).toBeInTheDocument();
  });

  it("shows a degraded state when the rules API fails without injecting fixtures", async () => {
    fetchRulesWorkbenchMock.mockRejectedValue(new Error("rules unavailable"));

    render(<ReplicaRulesWorkbench />);

    expect(await screen.findByText("规则工作台暂不可用")).toBeInTheDocument();
    expect(screen.getByText("规则数据读取失败，页面不会注入本地样例或旧统计值。")).toBeInTheDocument();
    expect(screen.queryByText(/规则 API/)).not.toBeInTheDocument();
    expect(screen.queryByText("runtime-rule-001")).not.toBeInTheDocument();
  });
});
