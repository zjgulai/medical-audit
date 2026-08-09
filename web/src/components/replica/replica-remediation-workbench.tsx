"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  fetchRemediationWorkbench,
  updateRemediationItemStatus,
  uploadRemediationAttachment
} from "@/lib/api-client";
import type { RemediationWorkbenchResponse } from "@/lib/api-types";

// 状态流转表：status_key → [{label, nextStatus}]
const STATUS_TRANSITIONS: Record<string, ReadonlyArray<{ readonly label: string; readonly next: string }>> = {
  "pending-rectification": [{ label: "开始整改", next: "in-rectification" }],
  "in-rectification":      [{ label: "提交验收", next: "pending-acceptance" }],
  "pending-acceptance":    [
    { label: "验收通过", next: "accepted" },
    { label: "退回整改", next: "rejected" }
  ],
  "rejected":              [{ label: "重新整改", next: "in-rectification" }],
  "accepted":              [{ label: "关闭事项", next: "closed" }],
  "closed":                []
};

type ActionState =
  | { readonly phase: "idle" }
  | { readonly phase: "confirming"; readonly next: string; readonly label: string }
  | { readonly phase: "submitting" }
  | { readonly phase: "done" }
  | { readonly phase: "error"; readonly message: string };

function StatusActionButtons({
  itemId,
  statusKey,
  onSuccess
}: {
  readonly itemId: string;
  readonly statusKey: string;
  readonly onSuccess: () => void;
}) {
  const [actionState, setActionState] = useState<ActionState>({ phase: "idle" });
  const [note, setNote] = useState("");

  const transitions = STATUS_TRANSITIONS[statusKey] ?? [];

  const handlePick = (label: string, next: string) => {
    setNote("");
    setActionState({ phase: "confirming", next, label });
  };

  const handleCancel = () => {
    setActionState({ phase: "idle" });
    setNote("");
  };

  const handleConfirm = async () => {
    if (actionState.phase !== "confirming") return;
    const { next } = actionState;
    setActionState({ phase: "submitting" });
    try {
      await updateRemediationItemStatus(itemId, next, note.trim());
      setActionState({ phase: "done" });
      setTimeout(() => {
        setActionState({ phase: "idle" });
        onSuccess();
      }, 1200);
    } catch {
      setActionState({ phase: "error", message: "操作失败，请重试" });
      setTimeout(() => setActionState({ phase: "idle" }), 4000);
    }
  };

  if (transitions.length === 0) return null;

  if (actionState.phase === "done") {
    return <span className="remediation-status-done">✓ 已更新</span>;
  }

  if (actionState.phase === "error") {
    return <span className="remediation-upload-error">{actionState.message}</span>;
  }

  if (actionState.phase === "confirming" || actionState.phase === "submitting") {
    return (
      <span className="remediation-status-action-group">
        <input
          aria-label="备注（可选）"
          className="remediation-note-input"
          disabled={actionState.phase === "submitting"}
          placeholder="备注（可选）"
          type="text"
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
        <button
          className="replica-primary-button"
          disabled={actionState.phase === "submitting"}
          type="button"
          onClick={handleConfirm}
        >
          {actionState.phase === "submitting" ? "提交中..." : `确认${actionState.label}`}
        </button>
        <button
          className="replica-secondary-button"
          disabled={actionState.phase === "submitting"}
          type="button"
          onClick={handleCancel}
        >
          取消
        </button>
      </span>
    );
  }

  return (
    <span className="remediation-status-actions">
      {transitions.map(({ label, next }) => (
        <button
          key={next}
          className="replica-secondary-button"
          type="button"
          onClick={() => handlePick(label, next)}
        >
          {label}
        </button>
      ))}
    </span>
  );
}

import {
  ReplicaEmptyState,
  ReplicaMetric,
  ReplicaNotice,
  ReplicaPageHeader,
  ReplicaRuntimeBadge
} from "./replica-page-kit";

type RemediationState =
  | { readonly status: "loading"; readonly data: null }
  | { readonly status: "ready"; readonly data: RemediationWorkbenchResponse }
  | { readonly status: "empty"; readonly data: RemediationWorkbenchResponse }
  | { readonly status: "degraded"; readonly data: null }
  | { readonly status: "error"; readonly data: null };

type UploadState =
  | { readonly status: "idle" }
  | { readonly status: "uploading"; readonly itemId: string }
  | { readonly status: "success"; readonly itemId: string; readonly fileName: string }
  | { readonly status: "error"; readonly itemId: string; readonly message: string };

function RemediationMetrics({ metrics }: { readonly metrics: RemediationWorkbenchResponse["metrics"] }) {
  const items = [
    ["整改事项", metrics.case_count, "blue"],
    ["整改中", metrics.active_case_count, "green"],
    ["待补证", metrics.pending_evidence_count, "amber"],
    ["阻断门禁", metrics.blocked_gate_count, "rose"]
  ] as const;

  return (
    <section className="replica-metric-grid" aria-label="整改指标">
      {items.map(([label, value, tone]) => (
        <ReplicaMetric key={label} label={label} value={String(value)} tone={tone} />
      ))}
    </section>
  );
}

function AttachmentUploadButton({
  itemId,
  uploadState,
  onUpload
}: {
  readonly itemId: string;
  readonly uploadState: UploadState;
  readonly onUpload: (itemId: string, file: File) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const isUploading = uploadState.status === "uploading" && uploadState.itemId === itemId;
  const isSuccess = uploadState.status === "success" && uploadState.itemId === itemId;
  const isError = uploadState.status === "error" && uploadState.itemId === itemId;

  return (
    <span className="remediation-attachment-upload">
      <input
        ref={inputRef}
        accept=".pdf,.png,.jpg,.jpeg,.xlsx,.xls,.csv,.docx,.doc,.txt,.zip"
        aria-label="上传补证附件"
        disabled={isUploading}
        style={{ display: "none" }}
        type="file"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onUpload(itemId, file);
          if (inputRef.current) inputRef.current.value = "";
        }}
      />
      <button
        className="replica-secondary-button"
        disabled={isUploading}
        type="button"
        onClick={() => inputRef.current?.click()}
      >
        {isUploading ? "上传中..." : "上传附件"}
      </button>
      {isSuccess ? (
        <span className="remediation-upload-success">✓ {uploadState.fileName}</span>
      ) : null}
      {isError ? (
        <span className="remediation-upload-error">{uploadState.message}</span>
      ) : null}
    </span>
  );
}

function gateStatusClass(status: string): string {
  if (status === "阻断") return "is-blocked";
  if (status === "通过") return "is-passed";
  return "is-pending";
}

export function ReplicaRemediationWorkbench() {
  const [state, setState] = useState<RemediationState>({ status: "loading", data: null });
  const [uploadState, setUploadState] = useState<UploadState>({ status: "idle" });

  const fetchData = useCallback(() => {
    fetchRemediationWorkbench()
      .then((data) => {
        if (!data.store.ready) {
          setState({ status: "degraded", data: null });
          return;
        }
        const empty = data.remediation_cases.length === 0
          && data.evidence_requests.length === 0
          && data.closure_gates.length === 0
          && data.timeline.length === 0;
        setState({ status: empty ? "empty" : "ready", data });
      })
      .catch(() => {
        setState({ status: "error", data: null });
      });
  }, []);

  useEffect(() => {
    let active = true;
    fetchRemediationWorkbench()
      .then((data) => {
        if (!active) return;
        if (!data.store.ready) {
          setState({ status: "degraded", data: null });
          return;
        }
        const empty = data.remediation_cases.length === 0
          && data.evidence_requests.length === 0
          && data.closure_gates.length === 0
          && data.timeline.length === 0;
        setState({ status: empty ? "empty" : "ready", data });
      })
      .catch(() => {
        if (active) setState({ status: "error", data: null });
      });
    return () => {
      active = false;
    };
  }, []);

  const handleUpload = useCallback(async (itemId: string, file: File) => {
    setUploadState({ status: "uploading", itemId });
    try {
      const result = await uploadRemediationAttachment(itemId, file);
      setUploadState({ status: "success", itemId, fileName: result.file_name });
      setTimeout(() => setUploadState({ status: "idle" }), 4000);
    } catch {
      setUploadState({ status: "error", itemId, message: "上传失败，请重试" });
      setTimeout(() => setUploadState({ status: "idle" }), 5000);
    }
  }, []);

  const data = state.data;
  const hasSeedData = data?.store.backend === "ReadonlyRemediationWorkbenchSeed";

  return (
    <main className="replica-page replica-page-standard" data-replica-source="api" data-replica-status={state.status}>
      <ReplicaPageHeader
        kicker="整改闭环"
        title="整改工作台"
        description="跟踪整改事项、补证请求和关闭门禁。可在此更新整改状态、上传补证附件。"
        actions={<ReplicaRuntimeBadge source="api" status={state.status} hasSeedData={hasSeedData} />}
      />

      {state.status === "loading" ? (
        <ReplicaEmptyState title="整改数据加载中" description="正在读取整改工作台数据。" />
      ) : state.status === "degraded" ? (
        <ReplicaEmptyState title="整改数据受限" description="整改存储状态未就绪，已停止展示可能不完整的整改记录。" />
      ) : state.status === "error" ? (
        <ReplicaEmptyState title="整改工作台暂不可用" description="整改数据读取失败，请稍后重试。" />
      ) : data ? (
        <>
          <RemediationMetrics metrics={data.metrics} />

          {hasSeedData ? (
            <ReplicaNotice>
              当前展示样例数据，生产整改台账将在整改事项入库后同步显示。
            </ReplicaNotice>
          ) : null}

          {state.status === "empty" ? (
            <ReplicaEmptyState
              title="暂无整改记录"
              description="当前没有进行中的整改事项。整改记录将在报告签发并生成整改任务后自动出现。"
            />
          ) : (
            <>
              <section className="replica-panel" aria-labelledby="remediation-cases-title">
                <div className="replica-results-head">
                  <div>
                    <p className="replica-kicker">整改事项</p>
                    <h2 id="remediation-cases-title">整改台账</h2>
                  </div>
                  <span>{data.remediation_cases.length} 项</span>
                </div>
                <div className="replica-record-list">
                  {data.remediation_cases.map((item) => (
                    <article key={item.id} className="remediation-item-actions">
                      <div>
                        <h3>{item.title}</h3>
                        <p>{item.department} · {item.reportNo}</p>
                        <small>{item.nextAction} · 截止 {item.dueDate}</small>
                      </div>
                      <span>{item.progress}% · {item.evidenceStatus}</span>
                      <strong>{item.status}</strong>
                      <StatusActionButtons
                        itemId={item.id}
                        statusKey={item.status_key ?? ""}
                        onSuccess={fetchData}
                      />
                      <AttachmentUploadButton
                        itemId={item.id}
                        uploadState={uploadState}
                        onUpload={handleUpload}
                      />
                    </article>
                  ))}
                </div>
              </section>

              <section className="replica-panel" aria-labelledby="remediation-evidence-title">
                <div className="replica-results-head">
                  <div>
                    <p className="replica-kicker">补证请求</p>
                    <h2 id="remediation-evidence-title">待补充证据</h2>
                  </div>
                  <span>{data.evidence_requests.length} 项</span>
                </div>
                <div className="replica-record-list">
                  {data.evidence_requests.map((item) => (
                    <article key={item.id}>
                      <div>
                        <h3>{item.title}</h3>
                        <p>{item.detail}</p>
                        <small>截止 {item.dueDate}</small>
                      </div>
                      <span>{item.owner} · {item.kind}</span>
                      <strong>{item.status}</strong>
                      <AttachmentUploadButton
                        itemId={item.id}
                        uploadState={uploadState}
                        onUpload={handleUpload}
                      />
                    </article>
                  ))}
                </div>
              </section>

              <section className="replica-panel" aria-labelledby="remediation-gates-title">
                <div className="replica-results-head">
                  <div>
                    <p className="replica-kicker">关闭门禁</p>
                    <h2 id="remediation-gates-title">结案条件</h2>
                  </div>
                  <span>{data.closure_gates.length} 项</span>
                </div>
                <div className="replica-record-list">
                  {data.closure_gates.map((item) => (
                    <article key={item.id} className={`remediation-gate-item ${gateStatusClass(item.status)}`}>
                      <div>
                        <h3>{item.label}</h3>
                        <p>{item.detail}</p>
                      </div>
                      <span>{item.owner}</span>
                      <strong
                        className={
                          item.status === "阻断" ? "remediation-gate-blocked"
                          : item.status === "通过" ? "remediation-gate-passed"
                          : ""
                        }
                      >
                        {item.status}
                      </strong>
                    </article>
                  ))}
                </div>
              </section>

              <section className="replica-panel" aria-labelledby="remediation-timeline-title">
                <div className="replica-results-head">
                  <div>
                    <p className="replica-kicker">整改时间线</p>
                    <h2 id="remediation-timeline-title">最近跟踪记录</h2>
                  </div>
                  <span>{data.timeline.length} 项</span>
                </div>
                <div className="replica-record-list">
                  {data.timeline.map((item) => (
                    <article key={item.id}>
                      <div>
                        <h3>{item.title}</h3>
                        <p>{item.detail}</p>
                        <small>{item.time}</small>
                      </div>
                      <strong>{item.status}</strong>
                    </article>
                  ))}
                </div>
              </section>
            </>
          )}
        </>
      ) : null}
    </main>
  );
}
