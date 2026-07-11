import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

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

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("renders the active page tag as a closable control", () => {
    vi.stubEnv("NEXT_PUBLIC_MEDICAL_AUDIT_REPLICA_API_READS", "0");
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

  it("renders nine main modules and one separate medical topic entry", () => {
    vi.stubEnv("NEXT_PUBLIC_MEDICAL_AUDIT_REPLICA_API_READS", "0");

    render(
      <ReplicaShell>
        <main>复刻页面内容</main>
      </ReplicaShell>
    );

    const mainNav = screen.getByRole("navigation", { name: "主导航" });
    expect(within(mainNav).getAllByRole("link")).toHaveLength(9);
    expect(within(mainNav).queryByText("医保审计专题")).not.toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "打开医保审计专题" })).toHaveLength(1);
    expect(screen.queryByText("医保基金合规审计")).not.toBeInTheDocument();
  });

  it("marks the medical topic active and uses its label in the page chrome", () => {
    vi.stubEnv("NEXT_PUBLIC_MEDICAL_AUDIT_REPLICA_API_READS", "0");
    usePathnameMock.mockReturnValue("/medical-audit");

    render(
      <ReplicaShell>
        <main>复刻页面内容</main>
      </ReplicaShell>
    );

    expect(screen.getByRole("link", { name: "打开医保审计专题" })).toHaveAttribute("aria-current", "page");
    expect(within(screen.getByRole("banner")).getByText("医保审计专题")).toBeInTheDocument();
    expect(within(screen.getByLabelText("打开页面")).getByText("医保审计专题")).toBeInTheDocument();
  });

  it("renders history items as deterministic chat links", () => {
    vi.stubEnv("NEXT_PUBLIC_MEDICAL_AUDIT_REPLICA_API_READS", "0");

    render(
      <ReplicaShell>
        <main>复刻页面内容</main>
      </ReplicaShell>
    );

    const historyTrigger = screen.getByRole("button", { name: "打开历史对话" });
    expect(historyTrigger).toHaveTextContent("历史对话");
    fireEvent.click(historyTrigger);

    expect(screen.getByRole("link", { name: "打开历史对话：中标候选人名单表" })).toHaveAttribute(
      "href",
      "/chat?history=history-1"
    );

    fireEvent.click(screen.getByRole("button", { name: "关闭历史对话" }));
    expect(screen.queryByRole("link", { name: "打开历史对话：中标候选人名单表" })).not.toBeInTheDocument();
  });
});
