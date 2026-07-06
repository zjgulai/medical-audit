import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ReplicaShell } from "./replica-shell";

const { usePathnameMock } = vi.hoisted(() => ({
  usePathnameMock: vi.fn()
}));

vi.mock("next/navigation", () => ({
  usePathname: usePathnameMock
}));

describe("ReplicaShell", () => {
  beforeEach(() => {
    usePathnameMock.mockReturnValue("/chat");
  });

  it("renders the active page tag as a closable control", () => {
    usePathnameMock.mockReturnValue("/documents");

    render(
      <ReplicaShell>
        <main>复刻页面内容</main>
      </ReplicaShell>
    );

    const tagsbar = screen.getByLabelText("打开页面");
    expect(within(tagsbar).getByText("文档检索")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "关闭文档检索页签" }));

    expect(within(tagsbar).queryByText("文档检索")).not.toBeInTheDocument();
    expect(screen.getByText("复刻页面内容")).toBeInTheDocument();
  });

  it("renders history items as deterministic chat links", () => {
    render(
      <ReplicaShell>
        <main>复刻页面内容</main>
      </ReplicaShell>
    );

    expect(screen.getByRole("link", { name: "打开历史对话：中标候选人名单表" })).toHaveAttribute(
      "href",
      "/chat?history=history-1"
    );
  });
});
