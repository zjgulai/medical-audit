"use client";

import { useRef, useState } from "react";

import { useAuditUser } from "@/components/shell/audit-user-context";
import {
  indexPersonalDocument,
  updateDocumentUploadGovernance,
  uploadPersonalDocument
} from "@/lib/api-client";
import type { DocumentUploadItem, DocumentUploadPermissions } from "@/lib/api-types";
import { auditClientUserId } from "@/lib/audit-user";

const MAX_PERSONAL_FILE_SIZE = 20 * 1024 * 1024;
const SUPPORTED_EXTENSIONS = new Set(["pdf", "md", "txt", "csv", "xlsx", "xlsm"]);

type PendingAction = `upload` | `govern:${string}` | `index:${string}`;

type PersonalMaterialActionsProps = {
  readonly permissions: DocumentUploadPermissions;
  readonly uploads: readonly DocumentUploadItem[];
  readonly onChanged: () => Promise<void>;
};

export function PersonalMaterialActions({
  permissions,
  uploads,
  onChanged
}: PersonalMaterialActionsProps) {
  const auditUser = useAuditUser();
  const currentUserId = auditClientUserId(auditUser.role);
  const [chooserOpen, setChooserOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null);
  const [message, setMessage] = useState<{ readonly kind: "error" | "success"; readonly text: string } | null>(null);
  const pendingActionRef = useRef<PendingAction | null>(null);

  const canUpload = permissions.can_upload_personal;
  const canGovern = permissions.can_govern_personal_uploads;
  const canIndexAny = uploads.some((item) => canGovern || item.created_by === currentUserId);

  if (!canUpload && !canGovern && !canIndexAny) {
    return null;
  }

  function selectFile(file: File | undefined) {
    setMessage(null);
    if (!file) {
      setSelectedFile(null);
      return;
    }
    const validationError = validatePersonalFile(file);
    if (validationError) {
      setSelectedFile(null);
      setMessage({ kind: "error", text: validationError });
      return;
    }
    setSelectedFile(file);
  }

  async function executeWrite(
    action: PendingAction,
    write: () => Promise<unknown>,
    afterWrite?: () => void
  ) {
    if (pendingActionRef.current !== null) {
      return;
    }
    pendingActionRef.current = action;
    setPendingAction(action);
    setMessage(null);

    try {
      await write();
      afterWrite?.();
      try {
        await onChanged();
        setMessage({ kind: "success", text: "操作成功" });
      } catch (error) {
        setMessage({
          kind: "error",
          text: `操作已完成，但列表刷新失败：${requestErrorMessage(error)}`
        });
      }
    } catch (error) {
      setMessage({ kind: "error", text: requestErrorMessage(error) });
    } finally {
      pendingActionRef.current = null;
      setPendingAction(null);
    }
  }

  function handleUpload() {
    if (!canUpload || selectedFile === null) {
      return;
    }
    const file = selectedFile;
    void executeWrite(
      "upload",
      () => uploadPersonalDocument(file),
      () => {
        setSelectedFile(null);
        setChooserOpen(false);
      }
    );
  }

  function handleGovernance(
    uploadId: string,
    governanceStatus: DocumentUploadItem["governance_status"]
  ) {
    if (!canGovern) {
      return;
    }
    void executeWrite(
      `govern:${uploadId}`,
      () => updateDocumentUploadGovernance(uploadId, { governance_status: governanceStatus })
    );
  }

  function handleIndex(item: DocumentUploadItem) {
    const canIndexActor = canGovern || item.created_by === currentUserId;
    if (!canIndexActor || !isIndexEligible(item)) {
      return;
    }
    void executeWrite(`index:${item.id}`, () => indexPersonalDocument(item.id));
  }

  const anyPending = pendingAction !== null;

  return (
    <div className="replica-form" aria-label="个人材料写入操作">
      {canUpload ? (
        <div className="replica-action-bar">
          <button
            type="button"
            aria-label="上传个人材料"
            disabled={anyPending}
            onClick={() => setChooserOpen(true)}
          >
            上传个人材料
          </button>
          {chooserOpen ? (
            <label>
              <span>选择个人材料文件</span>
              <input
                type="file"
                aria-label="选择个人材料文件"
                accept=".pdf,.md,.txt,.csv,.xlsx,.xlsm"
                disabled={anyPending}
                onChange={(event) => selectFile(event.currentTarget.files?.[0])}
              />
            </label>
          ) : null}
          {selectedFile ? (
            <>
              <span>{selectedFile.name}</span>
              <button type="button" disabled={anyPending} onClick={handleUpload}>
                提交上传
              </button>
            </>
          ) : null}
        </div>
      ) : null}

      {uploads.map((item) => {
        const canIndexActor = canGovern || item.created_by === currentUserId;
        return canGovern || canIndexActor ? (
          <div key={item.id} className="replica-action-bar" aria-label={`${item.name} 写入操作`}>
            {canGovern ? (
              <>
                <button
                  type="button"
                  disabled={anyPending}
                  onClick={() => handleGovernance(item.id, "approved-for-index")}
                >
                  批准进入索引
                </button>
                <button
                  type="button"
                  disabled={anyPending}
                  onClick={() => handleGovernance(item.id, "blocked")}
                >
                  阻断
                </button>
                <button
                  type="button"
                  disabled={anyPending}
                  onClick={() => handleGovernance(item.id, "pending-review")}
                >
                  退回复核
                </button>
              </>
            ) : null}
            {canIndexActor ? (
              <button
                type="button"
                disabled={anyPending || !isIndexEligible(item)}
                onClick={() => handleIndex(item)}
              >
                执行个人索引
              </button>
            ) : null}
          </div>
        ) : null;
      })}

      {message?.kind === "error" ? <p role="alert">{message.text}</p> : null}
      {message?.kind === "success" ? <p role="status">{message.text}</p> : null}
    </div>
  );
}

function validatePersonalFile(file: File): string | null {
  const extension = file.name.includes(".")
    ? file.name.slice(file.name.lastIndexOf(".") + 1).toLowerCase()
    : "";
  if (!SUPPORTED_EXTENSIONS.has(extension)) {
    return "仅支持 pdf、md、txt、csv、xlsx、xlsm 文件";
  }
  if (file.size === 0) {
    return "文件不能为空";
  }
  if (file.size > MAX_PERSONAL_FILE_SIZE) {
    return "文件不能超过 20 MiB";
  }
  return null;
}

function isIndexEligible(item: DocumentUploadItem): boolean {
  return item.governance_status === "approved-for-index"
    && item.index_status === "index-ready"
    && item.security_scan_status === "local-policy-passed"
    && item.dlp_status === "clear";
}

function requestErrorMessage(error: unknown): string {
  if (typeof error === "object" && error !== null && "detail" in error) {
    const detail = (error as { readonly detail?: unknown }).detail;
    if (typeof detail === "string" && detail.trim().length > 0) {
      return detail;
    }
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "未知错误";
}
