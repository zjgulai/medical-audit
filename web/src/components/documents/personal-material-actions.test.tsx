import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  BackendRequestError,
  fetchDocumentPermissions,
  fetchDocumentUploads,
  indexPersonalDocument,
  updateDocumentUploadGovernance,
  uploadPersonalDocument
} from "@/lib/api-client";
import type {
  DocumentPermissionsResponse,
  DocumentUploadItem,
  DocumentUploadListResponse,
  DocumentUploadPermissions,
  DocumentUploadResponse
} from "@/lib/api-types";

import { PersonalMaterialActions } from "./personal-material-actions";
import { PersonalMaterialReadPanel } from "./personal-material-read-panel";

const auditUserState = vi.hoisted(() => ({ role: "admin" }));

vi.mock("@/components/shell/audit-user-context", () => ({
  useAuditUser: () => ({ role: auditUserState.role, setRole: vi.fn(), can: vi.fn() })
}));

vi.mock("@/lib/api-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api-client")>();
  return {
    ...actual,
    fetchDocumentPermissions: vi.fn(),
    fetchDocumentUploads: vi.fn(),
    indexPersonalDocument: vi.fn(),
    updateDocumentUploadGovernance: vi.fn(),
    uploadPersonalDocument: vi.fn()
  };
});

const fetchDocumentPermissionsMock = vi.mocked(fetchDocumentPermissions);
const fetchDocumentUploadsMock = vi.mocked(fetchDocumentUploads);
const indexPersonalDocumentMock = vi.mocked(indexPersonalDocument);
const updateDocumentUploadGovernanceMock = vi.mocked(updateDocumentUploadGovernance);
const uploadPersonalDocumentMock = vi.mocked(uploadPersonalDocument);

const deniedPermissions: DocumentUploadPermissions = {
  can_upload_personal: false,
  can_read_all_personal_uploads: false,
  can_govern_personal_uploads: false
};

const uploadPermissions: DocumentUploadPermissions = {
  ...deniedPermissions,
  can_upload_personal: true
};

const governorPermissions: DocumentUploadPermissions = {
  can_upload_personal: true,
  can_read_all_personal_uploads: true,
  can_govern_personal_uploads: true
};

const readyUpload: DocumentUploadItem = {
  id: "document-upload-001",
  name: "audit-evidence.pdf",
  extension: ".pdf",
  size_bytes: 2048,
  size_kb: 2,
  sha256: "sha256-value",
  storage_path: "/private/audit-evidence.pdf",
  visibility: "private",
  status: "retained",
  created_by: "next-admin",
  created_at: "2026-07-16T08:30:00Z",
  retention_status: "retained",
  index_status: "index-ready",
  governance_status: "approved-for-index",
  governance_note: "approved",
  governed_by: "next-admin",
  governed_at: "2026-07-16T08:40:00Z",
  security_scan_status: "local-policy-passed",
  security_scan_provider: "local-policy",
  dlp_status: "clear",
  security_findings: [],
  personal_index_status: "not-indexed",
  personal_indexed_at: null,
  personal_indexed_by: null,
  personal_index_chunk_count: 0,
  personal_index_error: "",
  download_url: "https://signed.example.test/audit-evidence"
};

const uploadResponse: DocumentUploadResponse = {
  item: readyUpload,
  store: { ready: true, backend: "local-private-store" },
  permissions: governorPermissions
};

function permissionsResponse(
  role: string,
  upload_permissions: DocumentUploadPermissions
): DocumentPermissionsResponse {
  return { role, source_collections: [], upload_permissions };
}

function uploadsResponse(
  permissions: DocumentUploadPermissions,
  items: readonly DocumentUploadItem[] = [readyUpload]
): DocumentUploadListResponse {
  return {
    store: { ready: true, backend: "local-private-store" },
    permissions,
    items
  };
}

function chooseFile(file: File) {
  fireEvent.click(screen.getByRole("button", { name: "上传个人材料" }));
  fireEvent.change(screen.getByLabelText("选择个人材料文件"), {
    target: { files: [file] }
  });
}

function validFile(name = "audit-evidence.pdf") {
  return new File(["evidence"], name, { type: "application/pdf" });
}

function fileWithSize(name: string, size: number) {
  const file = validFile(name);
  Object.defineProperty(file, "size", { value: size });
  return file;
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

describe("PersonalMaterialActions", () => {
  beforeEach(() => {
    auditUserState.role = "admin";
    fetchDocumentPermissionsMock.mockReset();
    fetchDocumentUploadsMock.mockReset();
    indexPersonalDocumentMock.mockReset();
    updateDocumentUploadGovernanceMock.mockReset();
    uploadPersonalDocumentMock.mockReset();
  });

  it("hides all write controls when backend permissions are false", () => {
    render(
      <PersonalMaterialActions
        permissions={deniedPermissions}
        uploads={[]}
        onChanged={vi.fn()}
      />
    );

    expect(screen.queryByLabelText("上传个人材料")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "批准进入索引" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "执行个人索引" })).not.toBeInTheDocument();
  });

  it("performs zero writes during initial render and file selection", () => {
    render(
      <PersonalMaterialActions
        permissions={uploadPermissions}
        uploads={[]}
        onChanged={vi.fn()}
      />
    );

    chooseFile(validFile());

    expect(uploadPersonalDocumentMock).not.toHaveBeenCalled();
    expect(updateDocumentUploadGovernanceMock).not.toHaveBeenCalled();
    expect(indexPersonalDocumentMock).not.toHaveBeenCalled();
  });

  it("uploads exactly once after explicit submit, refreshes once, and does not auto-govern or index", async () => {
    const onChanged = vi.fn().mockResolvedValue(undefined);
    uploadPersonalDocumentMock.mockResolvedValue(uploadResponse);
    render(
      <PersonalMaterialActions
        permissions={uploadPermissions}
        uploads={[]}
        onChanged={onChanged}
      />
    );
    const file = validFile();
    chooseFile(file);

    fireEvent.click(screen.getByRole("button", { name: "提交上传" }));

    await waitFor(() => expect(uploadPersonalDocumentMock).toHaveBeenCalledTimes(1));
    expect(uploadPersonalDocumentMock).toHaveBeenCalledWith(file);
    expect(onChanged).toHaveBeenCalledTimes(1);
    expect(updateDocumentUploadGovernanceMock).not.toHaveBeenCalled();
    expect(indexPersonalDocumentMock).not.toHaveBeenCalled();
  });

  it.each([
    ["unsupported extension", validFile("audit-evidence.exe"), "仅支持 pdf、md、txt、csv、xlsx、xlsm 文件"],
    ["empty file", fileWithSize("audit-evidence.pdf", 0), "文件不能为空"],
    ["oversized file", fileWithSize("audit-evidence.pdf", 20 * 1024 * 1024 + 1), "文件不能超过 20 MiB"]
  ])("rejects an %s before upload", (_case, file, message) => {
    render(
      <PersonalMaterialActions
        permissions={uploadPermissions}
        uploads={[]}
        onChanged={vi.fn()}
      />
    );

    chooseFile(file);

    expect(screen.getByRole("alert")).toHaveTextContent(message);
    expect(screen.queryByRole("button", { name: "提交上传" })).not.toBeInTheDocument();
    expect(uploadPersonalDocumentMock).not.toHaveBeenCalled();
  });

  it("blocks a deferred upload double click synchronously", async () => {
    const upload = deferred<DocumentUploadResponse>();
    const onChanged = vi.fn().mockResolvedValue(undefined);
    uploadPersonalDocumentMock.mockReturnValue(upload.promise);
    render(
      <PersonalMaterialActions
        permissions={uploadPermissions}
        uploads={[]}
        onChanged={onChanged}
      />
    );
    chooseFile(validFile());
    const submit = screen.getByRole("button", { name: "提交上传" });

    await act(async () => {
      submit.click();
      submit.click();
    });

    expect(uploadPersonalDocumentMock).toHaveBeenCalledTimes(1);
    expect(onChanged).not.toHaveBeenCalled();

    upload.resolve(uploadResponse);
    await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(1));
  });

  it("sends the exact governance id and approved payload then refreshes once", async () => {
    const onChanged = vi.fn().mockResolvedValue(undefined);
    updateDocumentUploadGovernanceMock.mockResolvedValue(uploadResponse);
    render(
      <PersonalMaterialActions
        permissions={governorPermissions}
        uploads={[readyUpload]}
        onChanged={onChanged}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "批准进入索引" }));

    await waitFor(() => expect(updateDocumentUploadGovernanceMock).toHaveBeenCalledTimes(1));
    expect(updateDocumentUploadGovernanceMock).toHaveBeenCalledWith(
      "document-upload-001",
      { governance_status: "approved-for-index" }
    );
    expect(onChanged).toHaveBeenCalledTimes(1);
  });

  it("does not refresh after a rejected governance write and prefers backend detail", async () => {
    const onChanged = vi.fn().mockResolvedValue(undefined);
    updateDocumentUploadGovernanceMock.mockRejectedValue(new BackendRequestError({
      path: "/api/v1/documents/uploads/document-upload-001/governance",
      status: 403,
      detail: "仅治理角色可执行"
    }));
    render(
      <PersonalMaterialActions
        permissions={governorPermissions}
        uploads={[readyUpload]}
        onChanged={onChanged}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "阻断" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("仅治理角色可执行");
    expect(updateDocumentUploadGovernanceMock).toHaveBeenCalledWith(
      "document-upload-001",
      { governance_status: "blocked" }
    );
    expect(onChanged).not.toHaveBeenCalled();
  });

  it("keeps an ineligible index action disabled and never calls the API", () => {
    render(
      <PersonalMaterialActions
        permissions={governorPermissions}
        uploads={[{ ...readyUpload, governance_status: "blocked" }]}
        onChanged={vi.fn()}
      />
    );

    const indexButton = screen.getByRole("button", { name: "执行个人索引" });
    expect(indexButton).toBeDisabled();
    fireEvent.click(indexButton);
    expect(indexPersonalDocumentMock).not.toHaveBeenCalled();
  });

  it("indexes an eligible upload by exact id and refreshes once", async () => {
    const onChanged = vi.fn().mockResolvedValue(undefined);
    indexPersonalDocumentMock.mockResolvedValue(uploadResponse);
    render(
      <PersonalMaterialActions
        permissions={governorPermissions}
        uploads={[readyUpload]}
        onChanged={onChanged}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "执行个人索引" }));

    await waitFor(() => expect(indexPersonalDocumentMock).toHaveBeenCalledTimes(1));
    expect(indexPersonalDocumentMock).toHaveBeenCalledWith("document-upload-001");
    expect(onChanged).toHaveBeenCalledTimes(1);
  });

  it("lets a member index their own eligible upload while hiding governance", () => {
    auditUserState.role = "member";
    render(
      <PersonalMaterialActions
        permissions={deniedPermissions}
        uploads={[{ ...readyUpload, created_by: "next-member" }]}
        onChanged={vi.fn()}
      />
    );

    expect(screen.getByRole("button", { name: "执行个人索引" })).toBeEnabled();
    expect(screen.queryByRole("button", { name: "批准进入索引" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "阻断" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "退回复核" })).not.toBeInTheDocument();
  });

  it("reports a completed write separately when the one refresh fails", async () => {
    const onChanged = vi.fn().mockRejectedValue(new Error("refresh unavailable"));
    indexPersonalDocumentMock.mockResolvedValue(uploadResponse);
    render(
      <PersonalMaterialActions
        permissions={governorPermissions}
        uploads={[readyUpload]}
        onChanged={onChanged}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "执行个人索引" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "操作已完成，但列表刷新失败：refresh unavailable"
    );
    expect(indexPersonalDocumentMock).toHaveBeenCalledTimes(1);
    expect(onChanged).toHaveBeenCalledTimes(1);
  });
});

describe("PersonalMaterialReadPanel action integration", () => {
  beforeEach(() => {
    auditUserState.role = "admin";
    fetchDocumentPermissionsMock.mockReset();
    fetchDocumentUploadsMock.mockReset();
    indexPersonalDocumentMock.mockReset();
    updateDocumentUploadGovernanceMock.mockReset();
    uploadPersonalDocumentMock.mockReset();
  });

  it("fetches uploads exactly once after a write and rejects an invalid refresh", async () => {
    fetchDocumentPermissionsMock.mockResolvedValue(
      permissionsResponse("admin", uploadPermissions)
    );
    fetchDocumentUploadsMock
      .mockResolvedValueOnce(uploadsResponse(uploadPermissions, []))
      .mockResolvedValueOnce({
        ...uploadsResponse(uploadPermissions, []),
        store: { ready: false, backend: "unavailable" }
      });
    uploadPersonalDocumentMock.mockResolvedValue(uploadResponse);
    render(<PersonalMaterialReadPanel />);
    await screen.findByText("当前身份暂无可见个人材料");
    chooseFile(validFile());

    fireEvent.click(screen.getByRole("button", { name: "提交上传" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "操作已完成，但列表刷新失败"
    );
    expect(fetchDocumentUploadsMock).toHaveBeenCalledTimes(2);
    expect(uploadPersonalDocumentMock).toHaveBeenCalledTimes(1);
  });

  it("removes stale role controls immediately and reloads for the new role", async () => {
    fetchDocumentPermissionsMock
      .mockResolvedValueOnce(permissionsResponse("admin", governorPermissions))
      .mockResolvedValueOnce(permissionsResponse("member", deniedPermissions));
    fetchDocumentUploadsMock
      .mockResolvedValueOnce(uploadsResponse(governorPermissions))
      .mockResolvedValueOnce(uploadsResponse(deniedPermissions, [
        { ...readyUpload, created_by: "next-member" }
      ]));
    const view = render(<PersonalMaterialReadPanel />);
    expect(await screen.findByRole("button", { name: "批准进入索引" })).toBeInTheDocument();

    auditUserState.role = "member";
    view.rerender(<PersonalMaterialReadPanel />);

    expect(screen.queryByRole("button", { name: "批准进入索引" })).not.toBeInTheDocument();
    expect(screen.getByText("个人材料加载中")).toBeInTheDocument();
    expect(await screen.findByText("当前角色：member")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "执行个人索引" })).toBeEnabled();
    expect(fetchDocumentPermissionsMock).toHaveBeenCalledTimes(2);
    expect(fetchDocumentUploadsMock).toHaveBeenCalledTimes(2);
  });
});
