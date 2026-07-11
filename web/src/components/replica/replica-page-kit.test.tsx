import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ReplicaRuntimeBadge } from "./replica-page-kit";

describe("ReplicaRuntimeBadge", () => {
  it("identifies a ready version-controlled catalog", () => {
    render(<ReplicaRuntimeBadge source="catalog" status="ready" />);

    const badge = screen.getByLabelText("数据来源：产品目录；状态：已就绪");
    expect(badge).toHaveTextContent("产品目录");
    expect(badge).toHaveTextContent("目录已就绪");
  });

  it("identifies a successful empty API result", () => {
    render(<ReplicaRuntimeBadge source="api" status="empty" />);

    const badge = screen.getByLabelText("数据来源：后端数据；状态：暂无数据");
    expect(badge).toHaveTextContent("暂无数据");
    expect(badge).toHaveTextContent("当前无记录");
  });

  it("identifies a degraded API result and its limitations", () => {
    render(<ReplicaRuntimeBadge source="api" status="degraded" issueCount={2} />);

    const badge = screen.getByLabelText("数据来源：后端数据；状态：数据受限");
    expect(badge).toHaveTextContent("数据受限");
    expect(badge).toHaveTextContent("2 项受限");
  });

  it("identifies an API read error without claiming the interface was verified", () => {
    render(<ReplicaRuntimeBadge source="api" status="error" />);

    const badge = screen.getByLabelText("数据来源：后端数据；状态：读取失败");
    expect(badge).toHaveTextContent("读取失败");
    expect(badge).toHaveTextContent("请检查读取服务");
    expect(badge).not.toHaveTextContent("接口已校验");
  });
});
