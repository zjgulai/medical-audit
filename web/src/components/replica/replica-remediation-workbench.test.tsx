import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  fetchRemediationWorkbench,
  updateRemediationItemStatus,
  uploadRemediationAttachment
} from "@/lib/api-client";
import type { RemediationWorkbenchResponse } from "@/lib/api-types";

import { ReplicaRemediationWorkbench } from "./replica-remediation-workbench";

vi.mock("@/lib/api-client", () => ({
  fetchRemediationWorkbench: vi.fn(),
  updateRemediationItemStatus: vi.fn(),
  uploadRemediationAttachment: vi.fn()
}));

const fetchRemediationWorkbenchMock = vi.mocked(fetchRemediationWorkbench);
const updateRemediationItemStatusMock = vi.mocked(updateRemediationItemStatus);
const uploadRemediationAttachmentMock = vi.mocked(uploadRemediationAttachment);
const REMEDIATION_ITEM_UUID = "11111111-1111-4111-8111-111111111111";

const remediationResponse: RemediationWorkbenchResponse = {
  format: "remediation-workbench-v1",
  generated_at: "2026-07-16T09:00:00Z",
  workbench_id: "remediation-runtime-001",
  workbench_title: "整改台账",
  workbench_scope: "整改闭环",
  remediation_cases: [
    {
      id: REMEDIATION_ITEM_UUID,
      title: "重复收费整改",
      department: "医保办",
      owner: "医保办",
      status: "整改中",
      status_key: "in-rectification",
      dueDate: "2026-07-20",
      reportNo: "REPORT-001",
      sourceFinding: "finding-runtime-001",
      progress: 60,
      evidenceStatus: "待补证",
      nextAction: "补齐退费凭证",
      href: `/remediation/${REMEDIATION_ITEM_UUID}`,
      project_key: "SELF-CHECK-FUND-20260607",
      legacy_unscoped: false,
      writable: true,
      allowed_transitions: [{ status: "pending-acceptance", label: "提交验收" }],
      can_upload_attachment: true
    }
  ],
  evidence_requests: [
    {
      id: "evidence-request-001",
      title: "退费凭证",
      linkedCaseId: REMEDIATION_ITEM_UUID,
      kind: "退费凭证",
      status: "待上传",
      owner: "医保办",
      dueDate: "2026-07-18",
      detail: "上传只读验收所需的退费凭证。",
      href: "/documents",
      remediation_item_id: REMEDIATION_ITEM_UUID,
      writable: true
    }
  ],
  closure_gates: [
    {
      id: "closure-gate-001",
      label: "补证完整性",
      status: "阻断",
      detail: "退费凭证尚未验收。",
      owner: "审计员"
    }
  ],
  timeline: [
    {
      id: "timeline-001",
      time: "2026-07-16T08:30:00Z",
      title: "整改任务创建",
      detail: "整改事项已进入跟踪。",
      status: "已记录"
    }
  ],
  metrics: {
    case_count: 1,
    active_case_count: 1,
    closed_case_count: 0,
    pending_evidence_count: 1,
    blocked_gate_count: 1,
    average_progress: 60,
    timeline_count: 1
  },
  evidence_grade: "production-readonly-api",
  data_mode: "persistent",
  capabilities: { writable: true },
  production_side_effect: "audit-log-only",
  store: { ready: true, backend: "SqlAlchemyRemediationWorkbenchStore" }
};

describe("ReplicaRemediationWorkbench", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("keeps remediation on its own route and renders closure gates", async () => {
    fetchRemediationWorkbenchMock.mockResolvedValue(remediationResponse);

    render(<ReplicaRemediationWorkbench />);

    expect(await screen.findByText("整改台账")).toBeInTheDocument();
    expect(screen.getByText("补证请求")).toBeInTheDocument();
    expect(screen.getByText("关闭门禁")).toBeInTheDocument();
    expect(screen.queryByText("SqlAlchemyRemediationWorkbenchStore")).not.toBeInTheDocument();
    expect(screen.queryByText(/当前为只读整改数据，页面不会直接更新或关闭整改事项。/)).not.toBeInTheDocument();
  });

  it("does not expose zero metrics or retired fixtures while the initial read is pending", () => {
    fetchRemediationWorkbenchMock.mockReturnValue(new Promise(() => undefined));

    render(<ReplicaRemediationWorkbench />);

    expect(screen.getByText("整改数据加载中")).toBeInTheDocument();
    expect(screen.queryByText("整改事项")).not.toBeInTheDocument();
    expect(screen.queryByText("重复收费退费与流程复核")).not.toBeInTheDocument();
  });

  it("uses the strict empty contract when every remediation collection is empty", async () => {
    fetchRemediationWorkbenchMock.mockResolvedValue({
      ...remediationResponse,
      remediation_cases: [],
      evidence_requests: [],
      closure_gates: [],
      timeline: [],
      metrics: {
        ...remediationResponse.metrics,
        case_count: 0,
        active_case_count: 0,
        pending_evidence_count: 0,
        blocked_gate_count: 0,
        average_progress: 0,
        timeline_count: 0
      }
    });

    render(<ReplicaRemediationWorkbench />);

    expect(await screen.findByText("暂无整改记录")).toBeInTheDocument();
    expect(screen.queryByText("SqlAlchemyRemediationWorkbenchStore")).not.toBeInTheDocument();
    expect(screen.queryByText("重复收费退费与流程复核")).not.toBeInTheDocument();
  });

  it("fails closed when the remediation API rejects", async () => {
    fetchRemediationWorkbenchMock.mockRejectedValue(new Error("remediation unavailable"));

    render(<ReplicaRemediationWorkbench />);

    expect(await screen.findByText("整改工作台暂不可用")).toBeInTheDocument();
    expect(screen.getByText("整改数据读取失败，请稍后重试。")).toBeInTheDocument();
    expect(screen.queryByText(/整改 API/)).not.toBeInTheDocument();
    expect(screen.queryByText("remediation-case-001")).not.toBeInTheDocument();
    expect(screen.queryByText("重复收费退费与流程复核")).not.toBeInTheDocument();
  });

  it("fails closed when the remediation store is not ready", async () => {
    fetchRemediationWorkbenchMock.mockResolvedValue({
      ...remediationResponse,
      store: { ready: false, backend: "unavailable" }
    });

    render(<ReplicaRemediationWorkbench />);

    expect(await screen.findByText("整改数据受限")).toBeInTheDocument();
    expect(screen.getByText("整改存储状态未就绪，已停止展示可能不完整的整改记录。")).toBeInTheDocument();
    expect(screen.queryByText("remediation-case-001")).not.toBeInTheDocument();
  });

  it("shows status action buttons for items with known status_key", async () => {
    fetchRemediationWorkbenchMock.mockResolvedValue(remediationResponse);

    render(<ReplicaRemediationWorkbench />);

    expect(await screen.findByText("整改台账")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "提交验收" })).toBeInTheDocument();
  });

  it("calls updateRemediationItemStatus on action confirm", async () => {
    fetchRemediationWorkbenchMock.mockResolvedValue(remediationResponse);
    updateRemediationItemStatusMock.mockResolvedValue({ format: "ok", item: {} });

    render(<ReplicaRemediationWorkbench />);

    expect(await screen.findByRole("button", { name: "提交验收" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "提交验收" }));

    expect(await screen.findByRole("button", { name: "确认提交验收" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "确认提交验收" }));

    await waitFor(() => {
      expect(updateRemediationItemStatusMock).toHaveBeenCalledWith(
        REMEDIATION_ITEM_UUID,
        "pending-acceptance",
        ""
      );
    });
  });

  it("does not show action buttons for closed items", async () => {
    fetchRemediationWorkbenchMock.mockResolvedValue({
      ...remediationResponse,
      remediation_cases: [{
        ...remediationResponse.remediation_cases[0],
        status: "已关闭",
        status_key: "closed",
        writable: false,
        allowed_transitions: [],
        can_upload_attachment: false
      }]
    });

    render(<ReplicaRemediationWorkbench />);

    expect(await screen.findByText("整改台账")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /整改|验收|关闭/ })).not.toBeInTheDocument();
  });

  it("hides upload for active items when the API capability is false", async () => {
    fetchRemediationWorkbenchMock.mockResolvedValue({
      ...remediationResponse,
      remediation_cases: [{
        ...remediationResponse.remediation_cases[0],
        can_upload_attachment: false
      }],
      evidence_requests: []
    });

    render(<ReplicaRemediationWorkbench />);

    expect(await screen.findByRole("button", { name: "提交验收" })).toBeInTheDocument();
    expect(screen.queryByLabelText("上传补证附件")).not.toBeInTheDocument();
  });

  it("uses the real remediation UUID for evidence request upload", async () => {
    fetchRemediationWorkbenchMock.mockResolvedValue(remediationResponse);
    uploadRemediationAttachmentMock.mockResolvedValue({
      upload_id: "upload-001",
      file_name: "receipt.pdf",
      size_bytes: 7,
      item_id: REMEDIATION_ITEM_UUID
    });

    render(<ReplicaRemediationWorkbench />);

    expect(await screen.findByText("待补充证据")).toBeInTheDocument();
    const file = new File(["receipt"], "receipt.pdf", { type: "application/pdf" });
    const uploadInputs = screen.getAllByLabelText("上传补证附件");
    fireEvent.change(uploadInputs[uploadInputs.length - 1], {
      target: { files: [file] }
    });

    await waitFor(() => {
      expect(uploadRemediationAttachmentMock).toHaveBeenCalledWith(
        REMEDIATION_ITEM_UUID,
        file
      );
    });
    expect(await screen.findAllByText("✓ receipt.pdf")).toHaveLength(2);
  });
});
