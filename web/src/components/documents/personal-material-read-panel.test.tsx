import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  fetchDocumentPermissions,
  fetchDocumentUploads,
  indexPersonalDocument,
  updateDocumentUploadGovernance,
  uploadPersonalDocument
} from "@/lib/api-client";
import type {
  DocumentPermissionsResponse,
  DocumentUploadListResponse,
  DocumentUploadPermissions
} from "@/lib/api-types";

import { PersonalMaterialReadPanel } from "./personal-material-read-panel";

vi.mock("@/lib/api-client", () => ({
  fetchDocumentPermissions: vi.fn(),
  fetchDocumentUploads: vi.fn(),
  indexPersonalDocument: vi.fn(),
  updateDocumentUploadGovernance: vi.fn(),
  uploadPersonalDocument: vi.fn()
}));

const fetchDocumentPermissionsMock = vi.mocked(fetchDocumentPermissions);
const fetchDocumentUploadsMock = vi.mocked(fetchDocumentUploads);
const indexPersonalDocumentMock = vi.mocked(indexPersonalDocument);
const updateDocumentUploadGovernanceMock = vi.mocked(updateDocumentUploadGovernance);
const uploadPersonalDocumentMock = vi.mocked(uploadPersonalDocument);

const uploadPermissions: DocumentUploadPermissions = {
  can_upload_personal: true,
  can_read_all_personal_uploads: false,
  can_govern_personal_uploads: true
};

const permissionsResponse: DocumentPermissionsResponse = {
  role: "it-admin",
  source_collections: [],
  upload_permissions: uploadPermissions
};

const uploadListResponse: DocumentUploadListResponse = {
  store: { ready: true, backend: "local-private-store" },
  permissions: uploadPermissions,
  items: [
    {
      id: "document-upload-001",
      name: "document-upload-001.pdf",
      extension: ".pdf",
      size_bytes: 2048,
      size_kb: 2,
      sha256: "sensitive-sha256-value",
      storage_path: "/private/sensitive/storage/document-upload-001.pdf",
      visibility: "private",
      status: "retained",
      created_by: "admin",
      created_at: "2026-07-16T08:30:00Z",
      retention_status: "retained",
      index_status: "index-ready",
      governance_status: "approved-for-index",
      governance_note: "approved",
      governed_by: "admin",
      governed_at: "2026-07-16T08:40:00Z",
      security_scan_status: "local-policy-passed",
      security_scan_provider: "local-policy",
      dlp_status: "clear",
      security_findings: [],
      personal_index_status: "indexed",
      personal_indexed_at: "2026-07-16T08:45:00Z",
      personal_indexed_by: "admin",
      personal_index_chunk_count: 8,
      personal_index_error: "",
      download_url: "https://signed.example.test/sensitive-download-url"
    }
  ]
};

function assertGetOnlyContract() {
  expect(fetchDocumentPermissionsMock).toHaveBeenCalledTimes(1);
  expect(fetchDocumentUploadsMock).toHaveBeenCalledTimes(1);
  expect(uploadPersonalDocumentMock).not.toHaveBeenCalled();
  expect(updateDocumentUploadGovernanceMock).not.toHaveBeenCalled();
  expect(indexPersonalDocumentMock).not.toHaveBeenCalled();
  expect(document.querySelector('input[type="file"]')).not.toBeInTheDocument();
}

function assertUploadPayloadHidden() {
  expect(screen.queryByText("document-upload-001.pdf")).not.toBeInTheDocument();
  expect(screen.queryByText("sensitive-sha256-value")).not.toBeInTheDocument();
  expect(screen.queryByText("/private/sensitive/storage/document-upload-001.pdf")).not.toBeInTheDocument();
  expect(screen.queryByText("https://signed.example.test/sensitive-download-url")).not.toBeInTheDocument();
}

describe("PersonalMaterialReadPanel", () => {
  beforeEach(() => {
    fetchDocumentPermissionsMock.mockReset();
    fetchDocumentUploadsMock.mockReset();
    uploadPersonalDocumentMock.mockReset();
    updateDocumentUploadGovernanceMock.mockReset();
    indexPersonalDocumentMock.mockReset();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("loads document permissions and personal upload history without writing", async () => {
    fetchDocumentPermissionsMock.mockResolvedValue(permissionsResponse);
    fetchDocumentUploadsMock.mockResolvedValue(uploadListResponse);

    render(<PersonalMaterialReadPanel />);

    expect(await screen.findByText("document-upload-001.pdf")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "个人材料" })).toBeInTheDocument();
    expect(screen.getByText("当前角色：it-admin")).toBeInTheDocument();
    expect(screen.getByText("上传个人材料：允许")).toBeInTheDocument();
    expect(screen.getByText("查看全部个人材料：不允许")).toBeInTheDocument();
    expect(screen.getByText("治理个人材料：允许")).toBeInTheDocument();
    expect(screen.getByText("2026-07-16T08:30:00Z")).toBeInTheDocument();
    expect(screen.getByText("治理状态：approved-for-index")).toBeInTheDocument();
    expect(screen.getByText("安全扫描：local-policy-passed")).toBeInTheDocument();
    expect(screen.getByText("DLP：clear")).toBeInTheDocument();
    expect(screen.getByText("索引状态：index-ready")).toBeInTheDocument();
    expect(screen.getByText("个人索引：indexed / 8 chunks")).toBeInTheDocument();
    expect(screen.queryByText("sensitive-sha256-value")).not.toBeInTheDocument();
    expect(screen.queryByText("/private/sensitive/storage/document-upload-001.pdf")).not.toBeInTheDocument();
    expect(screen.queryByText("https://signed.example.test/sensitive-download-url")).not.toBeInTheDocument();
    assertGetOnlyContract();
  });

  it("shows a loading state while both GET requests are pending", () => {
    fetchDocumentPermissionsMock.mockReturnValue(new Promise(() => undefined));
    fetchDocumentUploadsMock.mockReturnValue(new Promise(() => undefined));

    render(<PersonalMaterialReadPanel />);

    expect(screen.getByText("个人材料加载中")).toBeInTheDocument();
    assertGetOnlyContract();
  });

  it("shows an explicit empty state for an identity with no visible uploads", async () => {
    fetchDocumentPermissionsMock.mockResolvedValue(permissionsResponse);
    fetchDocumentUploadsMock.mockResolvedValue({ ...uploadListResponse, items: [] });

    render(<PersonalMaterialReadPanel />);

    expect(await screen.findByText("当前身份暂无可见个人材料")).toBeInTheDocument();
    expect(screen.queryByText("document-upload-001.pdf")).not.toBeInTheDocument();
    assertGetOnlyContract();
  });

  it.each(["permissions", "uploads"] as const)(
    "fails closed when the %s GET request fails",
    async (failedRequest) => {
      fetchDocumentPermissionsMock.mockImplementation(() => failedRequest === "permissions"
        ? Promise.reject(new Error("permissions read failed"))
        : Promise.resolve(permissionsResponse));
      fetchDocumentUploadsMock.mockImplementation(() => failedRequest === "uploads"
        ? Promise.reject(new Error("uploads read failed"))
        : Promise.resolve(uploadListResponse));

      render(<PersonalMaterialReadPanel />);

      expect(await screen.findByText("个人材料读取失败")).toBeInTheDocument();
      expect(screen.queryByText("当前角色：it-admin")).not.toBeInTheDocument();
      expect(screen.queryByText("document-upload-001.pdf")).not.toBeInTheDocument();
      assertGetOnlyContract();
    }
  );

  it("fails closed as degraded when the personal material store is not ready", async () => {
    fetchDocumentPermissionsMock.mockResolvedValue(permissionsResponse);
    fetchDocumentUploadsMock.mockResolvedValue({
      ...uploadListResponse,
      store: { ready: false, backend: "unavailable" }
    });

    render(<PersonalMaterialReadPanel />);

    expect(await screen.findByText("个人材料状态受限")).toBeInTheDocument();
    expect(screen.queryByText("document-upload-001.pdf")).not.toBeInTheDocument();
    assertGetOnlyContract();
  });

  it("fails closed as degraded when the two permission responses disagree", async () => {
    fetchDocumentPermissionsMock.mockResolvedValue(permissionsResponse);
    fetchDocumentUploadsMock.mockResolvedValue({
      ...uploadListResponse,
      permissions: { ...uploadPermissions, can_govern_personal_uploads: false }
    });

    render(<PersonalMaterialReadPanel />);

    expect(await screen.findByText("个人材料状态受限")).toBeInTheDocument();
    expect(screen.queryByText("document-upload-001.pdf")).not.toBeInTheDocument();
    assertGetOnlyContract();
  });

  it("fails closed when the permission response belongs to another role", async () => {
    fetchDocumentPermissionsMock.mockResolvedValue({ ...permissionsResponse, role: "auditor" });
    fetchDocumentUploadsMock.mockResolvedValue(uploadListResponse);

    render(<PersonalMaterialReadPanel />);

    expect(await screen.findByText("个人材料状态受限")).toBeInTheDocument();
    expect(screen.getByText("个人材料权限身份不一致，已停止展示上传明细。")).toBeInTheDocument();
    assertUploadPayloadHidden();
    assertGetOnlyContract();
  });

  it("fails closed when both permission payloads omit the same capability", async () => {
    const malformedPermissions = {
      can_upload_personal: true,
      can_read_all_personal_uploads: false
    } as unknown as DocumentUploadPermissions;
    fetchDocumentPermissionsMock.mockResolvedValue({
      ...permissionsResponse,
      upload_permissions: malformedPermissions
    });
    fetchDocumentUploadsMock.mockResolvedValue({
      ...uploadListResponse,
      permissions: malformedPermissions
    });

    render(<PersonalMaterialReadPanel />);

    expect(await screen.findByText("个人材料状态受限")).toBeInTheDocument();
    assertUploadPayloadHidden();
    assertGetOnlyContract();
  });

  it("fails closed when both permission payloads contain the same non-boolean capability", async () => {
    const malformedPermissions = {
      ...uploadPermissions,
      can_govern_personal_uploads: "true"
    } as unknown as DocumentUploadPermissions;
    fetchDocumentPermissionsMock.mockResolvedValue({
      ...permissionsResponse,
      upload_permissions: malformedPermissions
    });
    fetchDocumentUploadsMock.mockResolvedValue({
      ...uploadListResponse,
      permissions: malformedPermissions
    });

    render(<PersonalMaterialReadPanel />);

    expect(await screen.findByText("个人材料状态受限")).toBeInTheDocument();
    assertUploadPayloadHidden();
    assertGetOnlyContract();
  });
});
