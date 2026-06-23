import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  createAuditAgent,
  createAuditAgentPromptVersion,
  createProjectMember,
  fetchAnalysisUploadHistory,
  fetchArchiveWorkbench,
  fetchAuditAgent,
  fetchDocumentPermissions,
  fetchDocumentUploads,
  fetchGraphWorkbench,
  fetchQueryHistory,
  fetchRemediationWorkbench,
  fetchReportWorkbench,
  fetchRulesWorkbench,
  fetchSearchBackendStatus,
  recordAuditAgentInvocation,
  reviewAuditAgentPromptVersion,
  rollbackAuditAgentPromptVersion,
  runKnowledgeQuery,
  submitAuditAgentFeedback,
  uploadAnalysisTable,
  uploadPersonalDocument,
  updateAuditAgentLifecycle
} from "@/lib/api-client";
import { AuditUserProvider } from "@/components/shell/audit-user-context";
import { AUDIT_ROLE_STORAGE_KEY } from "@/lib/audit-user";
import { primaryNavigation, secondaryNavigation, workspaceHomeNavigation } from "@/lib/navigation";

import AgentMarketPage from "./agent-market/page";
import AgentsPage from "./agents/page";
import AnalyticsPage from "./analytics/page";
import ArchivePage from "./archive/page";
import ChatPortalPage from "./chat/page";
import DocumentsPage from "./documents/page";
import FindingsPage from "./findings/page";
import GraphPage from "./graph/page";
import GuidedCheckPage from "./guided-check/page";
import KnowledgeBasePage from "./knowledge-base/page";
import KnowledgeQueryPage from "./knowledge-query/page";
import ProjectsPage from "./projects/page";
import RemediationPage from "./remediation/page";
import ReportsPage from "./reports/page";
import RulesPage from "./rules/page";
import WorkspacePage from "./workspace/page";

vi.mock("@/lib/api-client", () => ({
  createAuditAgent: vi.fn(
    async (payload: {
      readonly name: string;
      readonly category: string;
      readonly topic: string;
      readonly prompt: string;
      readonly knowledge_base?: string;
      readonly project_name?: string;
    }) => ({
    item: {
      id: "agent-custom-test",
      name: payload.name,
      category: payload.category,
      topic: payload.topic,
      prompt: payload.prompt,
      knowledge_base: payload.knowledge_base ?? "项目默认知识库",
      project_name: payload.project_name ?? "医保基金使用合规专项自查",
      status: "active",
      created_by: "next-knowledge-query",
      updated_at: "2026-06-14T00:00:00Z",
      prompt_version: 1,
      prompt_version_key: "agent-custom-test@v1",
      prompt_versions: [
        {
          version: 1,
          prompt: payload.prompt,
          change_summary: "initial prompt",
          is_active: true,
          created_by: "next-knowledge-query",
          created_at: "2026-06-14T00:00:00Z"
        }
      ],
      visibility_scope: "project",
      allowed_roles: ["admin", "technician", "director", "member"],
      source: "custom",
      metadata: {}
    },
    store: { ready: true, backend: "SqlAlchemyAgentStore" }
    })
  ),
  createAuditAgentPromptVersion: vi.fn(async (
    agentId: string,
    payload: { readonly prompt: string; readonly change_summary: string; readonly review_note?: string }
  ) => ({
    item: {
      id: agentId,
      name: "目录限制核验助手",
      category: "业务类",
      topic: "医保目录限制条件核验",
      prompt: "仅基于目录限制字段和引用依据输出待补证问题。",
      knowledge_base: "项目默认知识库",
      project_name: "医保基金使用合规专项自查",
      status: "active",
      created_by: "next-admin",
      updated_at: "2026-06-22T00:00:00Z",
      prompt_version: 1,
      prompt_version_key: `${agentId}@v1`,
      prompt_versions: [
        {
          version: 1,
          prompt: "仅基于目录限制字段和引用依据输出待补证问题。",
          change_summary: "initial prompt",
          is_active: true,
          created_by: "next-admin",
          created_at: "2026-06-14T00:00:00Z",
          review_status: "approved",
          review_note: "initial prompt",
          requested_by: "next-admin",
          reviewed_by: "next-admin",
          reviewed_at: "2026-06-14T00:00:00Z",
          review_updated_at: "2026-06-14T00:00:00Z"
        },
        {
          version: 2,
          prompt: payload.prompt,
          change_summary: payload.change_summary,
          is_active: false,
          created_by: "next-admin",
          created_at: "2026-06-22T00:00:00Z",
          review_status: "pending-review",
          review_note: payload.review_note ?? "",
          requested_by: "next-admin",
          reviewed_by: null,
          reviewed_at: null,
          review_updated_at: "2026-06-22T00:00:00Z"
        }
      ],
      visibility_scope: "project",
      allowed_roles: ["admin", "technician", "director", "member"],
      source: "custom",
      metadata: {}
    },
    store: { ready: true, backend: "SqlAlchemyAgentStore" }
  })),
  reviewAuditAgentPromptVersion: vi.fn(async (
    agentId: string,
    payload: {
      readonly version: number;
      readonly review_status: "pending-review" | "approved" | "changes-requested";
      readonly review_note?: string;
    }
  ) => {
    const isApproved = payload.review_status === "approved";
    return {
      item: {
        id: agentId,
        name: "目录限制核验助手",
        category: "业务类",
        topic: "医保目录限制条件核验",
        prompt: isApproved
          ? "仅基于目录限制字段、引用依据和原文截图输出待补证问题。"
          : "仅基于目录限制字段和引用依据输出待补证问题。",
        knowledge_base: "项目默认知识库",
        project_name: "医保基金使用合规专项自查",
        status: "active",
        created_by: "next-admin",
        updated_at: "2026-06-22T00:00:00Z",
        prompt_version: isApproved ? 2 : 1,
        prompt_version_key: `${agentId}@v${isApproved ? 2 : 1}`,
        prompt_versions: [
          {
            version: 1,
            prompt: "仅基于目录限制字段和引用依据输出待补证问题。",
            change_summary: "initial prompt",
            is_active: !isApproved,
            created_by: "next-admin",
            created_at: "2026-06-14T00:00:00Z",
            review_status: "approved",
            review_note: "initial prompt",
            requested_by: "next-admin",
            reviewed_by: "next-admin",
            reviewed_at: "2026-06-14T00:00:00Z",
            review_updated_at: "2026-06-14T00:00:00Z"
          },
          {
            version: 2,
            prompt: "仅基于目录限制字段、引用依据和原文截图输出待补证问题。",
            change_summary: "补充原文截图约束。",
            is_active: isApproved,
            created_by: "next-admin",
            created_at: "2026-06-22T00:00:00Z",
            review_status: payload.review_status,
            review_note: payload.review_note ?? "",
            requested_by: "next-admin",
            reviewed_by: "next-admin",
            reviewed_at: "2026-06-22T00:00:00Z",
            review_updated_at: "2026-06-22T00:00:00Z"
          }
        ],
        visibility_scope: "project",
        allowed_roles: ["admin", "technician", "director", "member"],
        source: "custom",
        metadata: {}
      },
      store: { ready: true, backend: "SqlAlchemyAgentStore" }
    };
  }),
  rollbackAuditAgentPromptVersion: vi.fn(async (
    agentId: string,
    payload: { readonly version: number }
  ) => ({
    item: {
      id: agentId,
      name: "目录限制核验助手",
      category: "业务类",
      topic: "医保目录限制条件核验",
      prompt: "仅基于目录限制字段和引用依据输出待补证问题。",
      knowledge_base: "项目默认知识库",
      project_name: "医保基金使用合规专项自查",
      status: "active",
      created_by: "next-admin",
      updated_at: "2026-06-22T00:00:00Z",
      prompt_version: 3,
      prompt_version_key: `${agentId}@v3`,
      prompt_versions: [
        {
          version: payload.version,
          prompt: "仅基于目录限制字段和引用依据输出待补证问题。",
          change_summary: "initial prompt",
          created_by: "next-admin",
          created_at: "2026-06-14T00:00:00Z"
        },
        {
          version: 3,
          prompt: "仅基于目录限制字段和引用依据输出待补证问题。",
          change_summary: `rollback to v${payload.version}`,
          created_by: "next-admin",
          created_at: "2026-06-22T00:00:00Z"
        }
      ],
      visibility_scope: "project",
      allowed_roles: ["admin", "technician", "director", "member"],
      source: "custom",
      metadata: {}
    },
    store: { ready: true, backend: "SqlAlchemyAgentStore" }
  })),
  updateAuditAgentLifecycle: vi.fn(async (
    agentId: string,
    payload?: { readonly status?: string; readonly reason?: string }
  ) => ({
    item: {
      id: agentId,
      name: "目录限制核验助手",
      category: "业务类",
      topic: "医保目录限制条件核验",
      prompt: "仅基于目录限制字段和引用依据输出待补证问题。",
      knowledge_base: "项目默认知识库",
      project_name: "医保基金使用合规专项自查",
      created_by: "next-admin",
      updated_at: "2026-06-22T00:00:00Z",
      prompt_version: 1,
      prompt_version_key: `${agentId}@v1`,
      prompt_versions: [
        {
          version: 1,
          prompt: "仅基于目录限制字段和引用依据输出待补证问题。",
          change_summary: "initial prompt",
          created_by: "next-admin",
          created_at: "2026-06-22T00:00:00Z"
        }
      ],
      visibility_scope: "project",
      allowed_roles: ["admin", "technician", "director", "member"],
      source: "custom",
      status: payload?.status ?? "inactive",
      metadata: { lifecycle_reason: payload?.reason ?? "工作台下架，保留历史追溯。" }
    },
    store: { ready: true, backend: "SqlAlchemyAgentStore" }
  })),
  fetchAuditAgent: vi.fn(async (agentId: string) => ({
    item: {
      id: agentId,
      name: agentId === "agent-custom-test" ? "目录限制核验助手" : "引用依据核验助手",
      category: "业务类",
      topic: agentId === "agent-custom-test" ? "医保目录限制条件核验" : "医保基金使用合规",
      prompt:
        agentId === "agent-custom-test"
          ? "仅基于目录限制字段和引用依据输出待补证问题。"
          : "只基于命中的法规、目录、规则和风险清单回答；没有引用时输出待补证据。",
      knowledge_base: agentId === "agent-custom-test" ? "项目默认知识库" : "系统医保审计知识库",
      project_name: "医保基金使用合规专项自查",
      status: "active",
      created_by: agentId === "agent-custom-test" ? "next-admin" : "system",
      updated_at: "2026-06-22T00:00:00Z",
      prompt_version: 1,
      prompt_version_key: `${agentId}@v1`,
      prompt_versions: [
        {
          version: 1,
          prompt:
            agentId === "agent-custom-test"
              ? "仅基于目录限制字段和引用依据输出待补证问题。"
              : "只基于命中的法规、目录、规则和风险清单回答；没有引用时输出待补证据。",
          change_summary: "initial prompt",
          created_by: agentId === "agent-custom-test" ? "next-admin" : "system",
          created_at: "2026-06-14T00:00:00Z"
        }
      ],
      visibility_scope: agentId === "agent-custom-test" ? "project" : "system",
      allowed_roles: ["admin", "technician", "director", "member"],
      source: agentId === "agent-custom-test" ? "custom" : "system-default",
      metadata: {}
    },
    store: { ready: true, backend: "SqlAlchemyAgentStore" }
  })),
  fetchAuditAgentInvocations: vi.fn(async () => ({
    items: [],
    store: { ready: true, backend: "SqlAlchemyAgentStore" }
  })),
  recordAuditAgentInvocation: vi.fn(async (agentId: string) => ({
    item: {
      id: "agent-invocation-test",
      agent_key: agentId,
      prompt_version: 2,
      prompt_version_key: `${agentId}@v2`,
      invocation_source: "agent-workspace",
      question: "目录限制核验助手 工作台试用登记",
      conversation_ref: null,
      created_by: "next-admin",
      created_at: "2026-06-22T00:00:00Z",
      metadata: {}
    },
    store: { ready: true, backend: "SqlAlchemyAgentStore" }
  })),
  fetchAuditAgentFeedback: vi.fn(async () => ({
    items: [],
    ratings: ["effective", "needs_review", "unsafe"],
    summary: {
      total: 0,
      effective: 0,
      needs_review: 0,
      unsafe: 0,
      latest_rating: null
    },
    store: { ready: true, backend: "SqlAlchemyAgentStore" }
  })),
  submitAuditAgentFeedback: vi.fn(async (
    agentId: string,
    payload: {
      readonly invocation_id?: string | null;
      readonly rating: "effective" | "needs_review" | "unsafe";
      readonly comment?: string;
    }
  ) => ({
    item: {
      id: "agent-feedback-test",
      agent_key: agentId,
      invocation_id: payload.invocation_id ?? null,
      prompt_version: 2,
      rating: payload.rating,
      comment: payload.comment ?? "",
      created_by: "next-admin",
      created_at: "2026-06-22T00:00:00Z",
      metadata: {}
    },
    ratings: ["effective", "needs_review", "unsafe"],
    summary: {
      total: 1,
      effective: payload.rating === "effective" ? 1 : 0,
      needs_review: payload.rating === "needs_review" ? 1 : 0,
      unsafe: payload.rating === "unsafe" ? 1 : 0,
      latest_rating: payload.rating
    },
    store: { ready: true, backend: "SqlAlchemyAgentStore" }
  })),
  createProjectMember: vi.fn(
    async (
      projectId: string,
      payload: {
        readonly name: string;
        readonly role: string;
        readonly department: string;
      }
    ) => ({
      item: {
        id: "member-custom-test",
        project_key: projectId,
        name: payload.name,
        role: payload.role,
        department: payload.department,
        status: "待确认",
        created_by: "next-knowledge-query",
        updated_at: "2026-06-14T00:00:00Z",
        source: "custom",
        metadata: {}
      },
      store: { ready: true, backend: "SqlAlchemyProjectMemberStore" }
    })
  ),
  uploadAnalysisTable: vi.fn(async (file: File) => ({
    name: file.name,
    size_kb: Math.max(1, Math.round(file.size / 1024)),
    extension: "csv",
    status: "parsed",
    sheet_name: null,
    columns: [
      {
        name: "patient_id",
        type: "标识",
        empty_count: 0,
        unique_count: 2,
        sample_values: ["P001", "P002"],
        audit_hint: "对象字段，可用于同人同次就诊聚合"
      },
      {
        name: "visit_date",
        type: "日期",
        empty_count: 0,
        unique_count: 2,
        sample_values: ["2026-01-01", "2026-01-02"],
        audit_hint: "时间字段，可用于限定审计期间和同日重复核验"
      },
      {
        name: "item_code",
        type: "标识",
        empty_count: 0,
        unique_count: 2,
        sample_values: ["A100", "B200"],
        audit_hint: "项目字段，可用于目录限制和重复收费核验"
      },
      {
        name: "charge_amount",
        type: "数值",
        empty_count: 1,
        unique_count: 1,
        sample_values: ["120.00"],
        audit_hint: "金额字段，可用于收费合规和异常金额核验"
      },
      {
        name: "insurance_pay",
        type: "数值",
        empty_count: 0,
        unique_count: 2,
        sample_values: ["80.00", "50.00"],
        audit_hint: "医保字段，可用于支付范围和报销口径核验"
      }
    ],
    row_count: 3,
    empty_cell_count: 1,
    duplicate_row_count: 1,
    message: "后端已完成 CSV 文件的字段画像。",
    quality_findings: [
      "识别到 3 行数据和 5 个字段。",
      "发现 1 个空值单元，需要确认是否为业务允许缺失。",
      "发现 1 条完全重复行。",
      "字段名未发现重复。"
    ],
    audit_signals: ["金额/费用字段", "患者/就诊字段", "日期/时间字段", "项目/药品/目录字段", "医保支付字段"],
    recommendations: [
      "重复收费核验字段基础完整，可按患者/就诊、项目、日期和金额形成初筛分组。",
      "已识别医保支付字段，可进一步核对支付范围、报销口径和目录限制条件。",
      "优先核对高空值字段：charge_amount。"
    ],
    upload_id: "analytics-upload-test",
    sha256: "a".repeat(64),
    retention_status: "retained",
    created_at: "2026-06-15T00:00:00Z"
  })),
  fetchAnalysisUploadHistory: vi.fn(async () => ({
    items: [
      {
        id: "analytics-upload-history",
        name: "history-charge.csv",
        extension: "csv",
        size_bytes: 128,
        size_kb: 1,
        sha256: "b".repeat(64),
        storage_path: "2026/06/15/analytics-upload-history.csv",
        sheet_name: null,
        row_count: 3,
        column_count: 5,
        empty_cell_count: 1,
        duplicate_row_count: 1,
        status: "parsed",
        created_by: "next-knowledge-query",
        created_at: "2026-06-15T00:00:00Z",
        retention_status: "retained",
        audit_signals: ["金额/费用字段"]
      }
    ],
    store: { ready: true, backend: "SqlAlchemyAnalyticsUploadStore" }
  })),
  fetchDocumentPermissions: vi.fn(async () => ({
    role: "auditor",
    source_collections: [
      {
        source_collection: "medical-insurance-laws",
        label: "法规政策",
        scope: "公开知识库",
        access: "read"
      },
      {
        source_collection: "supervision-rules-knowledge",
        label: "监管两库",
        scope: "系统知识库",
        access: "read"
      },
      {
        source_collection: "medical-insurance-catalog",
        label: "医保目录",
        scope: "系统知识库",
        access: "read"
      },
      {
        source_collection: "risk-negative-list",
        label: "风险清单",
        scope: "系统知识库",
        access: "read"
      }
    ],
    upload_permissions: {
      can_upload_personal: true,
      can_read_all_personal_uploads: false,
      can_govern_personal_uploads: false
    }
  })),
  fetchDocumentUploads: vi.fn(async () => ({
    items: [
      {
        id: "document-upload-history",
        name: "policy-retained.pdf",
        extension: "pdf",
        size_bytes: 128,
        size_kb: 1,
        sha256: "c".repeat(64),
        storage_path: "2026/06/15/document-upload-history.pdf",
        visibility: "private",
        status: "retained",
        created_by: "next-knowledge-query",
        created_at: "2026-06-15T00:00:00Z",
        retention_status: "retained",
        index_status: "not-indexed",
        governance_status: "pending-review",
        governance_note: "",
        governed_by: null,
        governed_at: null,
        security_scan_status: "local-policy-passed",
        security_scan_provider: "local-policy",
        dlp_status: "clear",
        security_findings: [],
        personal_index_status: "not-indexed",
        personal_indexed_at: null,
        personal_indexed_by: null,
        personal_index_chunk_count: 0,
        personal_index_error: "",
        download_url: "/api/v1/documents/uploads/document-upload-history/download"
      }
    ],
    store: { ready: true, backend: "SqlAlchemyDocumentUploadStore" },
    permissions: {
      can_upload_personal: true,
      can_read_all_personal_uploads: false,
      can_govern_personal_uploads: false
    }
  })),
  uploadPersonalDocument: vi.fn(async (file: File) => ({
    item: {
      id: "document-upload-test",
      name: file.name,
      extension: "pdf",
      size_bytes: file.size,
      size_kb: Math.max(1, Math.round(file.size / 1024)),
      sha256: "d".repeat(64),
      storage_path: "2026/06/15/document-upload-test.pdf",
      visibility: "private",
      status: "retained",
      created_by: "next-knowledge-query",
      created_at: "2026-06-15T00:00:00Z",
      retention_status: "retained",
      index_status: "not-indexed",
      governance_status: "pending-review",
      governance_note: "",
      governed_by: null,
      governed_at: null,
      security_scan_status: "local-policy-passed",
      security_scan_provider: "local-policy",
      dlp_status: "clear",
      security_findings: [],
      personal_index_status: "not-indexed",
      personal_indexed_at: null,
      personal_indexed_by: null,
      personal_index_chunk_count: 0,
      personal_index_error: "",
      download_url: "/api/v1/documents/uploads/document-upload-test/download"
    },
    store: { ready: true, backend: "SqlAlchemyDocumentUploadStore" },
    permissions: {
      can_upload_personal: true,
      can_read_all_personal_uploads: false,
      can_govern_personal_uploads: false
    }
  })),
  indexPersonalDocument: vi.fn(async (uploadId: string) => ({
    item: {
      id: uploadId,
      name: "policy-retained.pdf",
      extension: "pdf",
      size_bytes: 128,
      size_kb: 1,
      sha256: "c".repeat(64),
      storage_path: "2026/06/15/document-upload-history.pdf",
      visibility: "private",
      status: "retained",
      created_by: "next-knowledge-query",
      created_at: "2026-06-15T00:00:00Z",
      retention_status: "retained",
      index_status: "index-ready",
      governance_status: "approved-for-index",
      governance_note: "",
      governed_by: "next-admin",
      governed_at: "2026-06-21T00:00:00Z",
      security_scan_status: "local-policy-passed",
      security_scan_provider: "local-policy",
      dlp_status: "clear",
      security_findings: [],
      personal_index_status: "indexed",
      personal_indexed_at: "2026-06-21T00:00:00Z",
      personal_indexed_by: "next-admin",
      personal_index_chunk_count: 1,
      personal_index_error: "",
      download_url: `/api/v1/documents/uploads/${uploadId}/download`
    },
    store: { ready: true, backend: "SqlAlchemyDocumentUploadStore" },
    permissions: {
      can_upload_personal: true,
      can_read_all_personal_uploads: false,
      can_govern_personal_uploads: false
    }
  })),
  updateDocumentUploadGovernance: vi.fn(
    async (
      uploadId: string,
      payload: { readonly governance_status: "pending-review" | "approved-for-index" | "blocked" }
    ) => ({
      item: {
        id: uploadId,
        name: "policy-retained.pdf",
        extension: "pdf",
        size_bytes: 128,
        size_kb: 1,
        sha256: "c".repeat(64),
        storage_path: "2026/06/15/document-upload-history.pdf",
        visibility: "private",
        status: "retained",
        created_by: "next-knowledge-query",
        created_at: "2026-06-15T00:00:00Z",
        retention_status: "retained",
        index_status: payload.governance_status === "approved-for-index" ? "index-ready" : "not-indexed",
        governance_status: payload.governance_status,
        governance_note: "",
        governed_by: "next-admin",
        governed_at: "2026-06-21T00:00:00Z",
        security_scan_status: "local-policy-passed",
        security_scan_provider: "local-policy",
        dlp_status: "clear",
        security_findings: [],
        personal_index_status: "not-indexed",
        personal_indexed_at: null,
        personal_indexed_by: null,
        personal_index_chunk_count: 0,
        personal_index_error: "",
        download_url: `/api/v1/documents/uploads/${uploadId}/download`
      },
      store: { ready: true, backend: "SqlAlchemyDocumentUploadStore" },
      permissions: {
        can_upload_personal: true,
        can_read_all_personal_uploads: false,
        can_govern_personal_uploads: false
      }
    })
  ),
  fetchQueryHistory: vi.fn(async () => ({
    items: [
      {
        id: "query-history-001",
        user_identifier: "next-knowledge-query",
        question: "医保基金支付异常",
        filters: {
          top_k: 8,
          source_collections: ["medical-insurance-laws"]
        },
        answer_summary: "应核验医保基金支付异常的引用依据。",
        retrieved_chunk_ids: ["chunk-doc-001"],
        citation_count: 1,
        created_at: "2026-06-15T00:00:00Z"
      }
    ],
    store: { ready: true, backend: "SqlAlchemyQueryHistoryStore" }
  })),
  fetchAuditFindings: vi.fn(async () => ({
    items: [],
    stats: { total: 0, open: 0, pending_review: 0, linked_review_task: 0 },
    filters: { review_status: null, limit: 100 },
    review_status_options: { "pending-review": "待复核" },
    generation_readiness: {
      status: "blocked",
      ready: false,
      has_findings: false,
      table_counts: { audit_projects: 0, his_staging_rows: 0, audit_findings: 0 },
      prerequisites: [
        { key: "audit_projects", label: "审计项目", count: 0, ready: false, required: true }
      ],
      blocking_reasons: [
        { code: "missing-audit_projects", message: "审计项目为空，无法从规则运行生成疑点。" }
      ],
      next_actions: ["导入脱敏 HIS 样本。"]
    },
    store: { ready: true, backend: "SqlAlchemyAuditFindingStore" }
  })),
  fetchReportWorkbench: vi.fn(async () => ({
    format: "report-workbench-v1",
    generated_at: "2026-06-21T00:00:00Z",
    template_registry_status: "active",
    workpaper_templates: [
      {
        id: "workpaper-summary-risk",
        name: "费用汇总风险底稿",
        source_template_id: "medical-expense-summary",
        source_table: "表1 医保费用汇总表",
        source_file_name: "表1_医保费用汇总表-模版.xlsx",
        sheet_name: "汇总表",
        output_type: "底稿草稿",
        registry_status: "active",
        expected_columns: ["费用分类", "医疗总费用", "统筹支付"],
        key_checks: ["支付分项是否能回溯到明细"],
        evidence_bindings: ["费用分类汇总", "支付分项合计"],
        prompt: "基于医保费用汇总表生成底稿草稿。",
        chat_href: "/chat?agent=agent-report-draft&question=费用汇总底稿"
      },
      {
        id: "workpaper-category-review",
        name: "分类费用复核清单",
        source_template_id: "medical-expense-category-summary",
        source_table: "表2 医保费用分类汇总表",
        source_file_name: "表2_医保费用分类汇总表-模版.xlsx",
        sheet_name: "汇总表",
        output_type: "问题清单",
        registry_status: "active",
        expected_columns: ["费用分类", "平均费用", "统筹支付"],
        key_checks: ["平均费用是否存在明显偏离"],
        evidence_bindings: ["平均费用偏离", "需下钻明细"],
        prompt: "基于医保费用分类汇总表形成复核问题清单。",
        chat_href: "/chat?agent=agent-citation-check&question=分类费用复核清单"
      },
      {
        id: "workpaper-visit-detail",
        name: "就诊明细疑点摘要",
        source_template_id: "visit-expense-detail",
        source_table: "表3 就诊费用明细表",
        source_file_name: "表3_就诊费用明细表-模版.xlsx",
        sheet_name: "明细表",
        output_type: "复核摘要",
        registry_status: "active",
        expected_columns: ["就诊记录号", "身份证号码", "统筹支付"],
        key_checks: ["身份证号、就诊记录号等直接身份字段需按权限处理"],
        evidence_bindings: ["就诊记录号", "隐私字段处理记录"],
        prompt: "基于就诊费用明细表整理疑点摘要。",
        chat_href: "/chat?agent=agent-report-draft&question=就诊明细疑点摘要"
      }
    ],
    report_entries: [
      {
        id: "review-task-0001",
        title: "同就诊同项目重复收费复核报告草稿",
        status: "已签发",
        report_no: "signed-report-abc123",
        owner: "审计员",
        source: "chat-dossier",
        included_finding_count: 1,
        appendix_count: 2,
        gate_summary: "可进入报告草稿",
        updated_at: "2026-06-21T00:00:00Z",
        href: "/pages/review-tasks",
        download_links: {
          page: "/pages/review-tasks",
          task_docx: "/review-tasks/review-task-0001/export?format=docx",
          report_docx: "/review-tasks/review-task-0001/signed-report?format=docx",
          report_markdown: "/review-tasks/review-task-0001/signed-report?format=markdown",
          report_json: "/review-tasks/review-task-0001/signed-report?format=json"
        }
      }
    ],
    report_evidence_sources: [
      {
        id: "evidence-review-task-0001",
        title: "workpaper-20260604-001",
        kind: "底稿",
        reference: "review-task-0001 · 附件 2 条",
        status: "已纳入",
        href: "/pages/review-tasks"
      }
    ],
    metrics: {
      report_count: 1,
      signed_report_count: 1,
      blocked_report_count: 0,
      included_finding_count: 1,
      docx_download_count: 1
    },
    store: { ready: true, backend: "InMemoryReviewTaskStore" }
  })),
  fetchGraphWorkbench: vi.fn(async () => ({
    format: "graph-workbench-v1",
    generated_at: "2026-06-22T00:00:00Z",
    graph_id: "SELF-CHECK-FUND-20260607",
    graph_title: "医保基金使用合规专项图谱",
    graph_scope: "医保基金使用合规专项自查的项目、知识、规则、疑点、复核、报告和整改关系预览。",
    nodes: [
      {
        id: "graph-node-project",
        label: "专项自查项目",
        kind: "项目",
        status: "已归集",
        description: "医保基金使用合规专项自查，承载当前审计主题、成员和工作流。",
        metric: "3 名成员",
        href: "/projects",
        x: 100,
        y: 250
      },
      {
        id: "graph-node-kb",
        label: "系统知识库",
        kind: "知识库",
        status: "可引用",
        description: "法规政策、医保目录、监管两库和风险负面清单的统一知识底座。",
        metric: "48,985 篇",
        href: "/knowledge-base",
        x: 260,
        y: 130
      },
      {
        id: "graph-node-document",
        label: "目录限制资料包",
        kind: "文档",
        status: "可引用",
        description: "用于限定诊疗项目、药品编码、支付范围和限制条件的可审证材料。",
        metric: "2 份引用",
        href: "/documents",
        x: 430,
        y: 130
      },
      {
        id: "graph-node-rule",
        label: "重复收费规则",
        kind: "规则",
        status: "已归集",
        description: "围绕同就诊、同项目、同日期和同金额线索形成规则命中条件。",
        metric: "CHARGE-RULE-001",
        href: "/rules",
        x: 600,
        y: 130
      },
      {
        id: "graph-node-finding",
        label: "疑点 F044",
        kind: "疑点",
        status: "待复核",
        description: "由收费明细和规则运行生成的重复收费疑点，等待人工核验。",
        metric: "2 条记录",
        href: "/findings",
        x: 790,
        y: 250
      },
      {
        id: "graph-node-review",
        label: "复核任务 0007",
        kind: "复核",
        status: "门禁中",
        description: "沉淀负责人确认、附件和人工判断，决定是否进入报告。",
        metric: "负责人确认",
        href: "/pages/review-tasks",
        x: 600,
        y: 370
      },
      {
        id: "graph-node-report",
        label: "报告草稿",
        kind: "报告",
        status: "门禁中",
        description: "从已复核疑点和引用材料生成的底稿与报告记录。",
        metric: "1 份草稿",
        href: "/reports",
        x: 430,
        y: 370
      },
      {
        id: "graph-node-remediation",
        label: "整改跟踪",
        kind: "整改",
        status: "跟踪中",
        description: "报告签发后进入整改责任、状态跟踪和后续归档链路。",
        metric: "1 项跟踪",
        href: "/remediation",
        x: 260,
        y: 370
      }
    ],
    relations: [
      {
        id: "graph-rule-finding",
        sourceId: "graph-node-rule",
        targetId: "graph-node-finding",
        source: "重复收费规则",
        relation: "命中",
        target: "FINDING-F044EBD309B659DC",
        evidence: "charge_detail · 2 records",
        strength: "强"
      },
      {
        id: "graph-finding-task",
        sourceId: "graph-node-finding",
        targetId: "graph-node-review",
        source: "FINDING-F044EBD309B659DC",
        relation: "生成",
        target: "review-task-0007",
        evidence: "rule_version CHARGE-RULE-001@v1",
        strength: "强"
      }
    ],
    metrics: {
      node_count: 8,
      node_kind_count: 8,
      node_kind_counts: { 项目: 1, 知识库: 1, 文档: 1, 规则: 1, 疑点: 1, 复核: 1, 报告: 1, 整改: 1 },
      relation_count: 2,
      strong_relation_count: 2,
      pending_relation_count: 0
    },
    evidence_grade: "local-readonly-api",
    production_side_effect: "none",
    store: { ready: true, backend: "ReadonlyGraphWorkbenchSeed" }
  })),
  fetchRulesWorkbench: vi.fn(async () => ({
    format: "rules-workbench-v1",
    generated_at: "2026-06-22T00:00:00Z",
    ruleset_id: "FUND-USAGE-COMPLIANCE-RULES",
    ruleset_title: "医保基金使用合规专题规则库",
    ruleset_scope: "汇总监管两库、医保目录、风险清单和对话审证沉淀，首期只读展示规则来源、运行状态和疑点去向。",
    rule_library_items: [
      {
        id: "rule-duplicate-charge",
        code: "CHARGE-RULE-001",
        name: "同就诊同项目重复收费",
        domain: "收费明细",
        status: "已启用",
        sourceCollection: "supervision-rules-knowledge",
        evidenceScope: "按患者、就诊、项目、日期和金额聚合，识别同源重复收费。",
        evidenceCount: 4,
        findingCount: 1,
        owner: "内审部",
        updatedAt: "2026-06-11",
        href: "/findings?rule=CHARGE-RULE-001",
        chatHref: "/chat?question=duplicate-charge"
      },
      {
        id: "rule-catalog-limit",
        code: "CATALOG-RULE-014",
        name: "目录限制条件交叉核验",
        domain: "医保目录",
        status: "待补字段",
        sourceCollection: "medical-insurance-catalog",
        evidenceScope: "核对诊疗项目编码、医保支付范围、限制条件和结算口径。",
        evidenceCount: 3,
        findingCount: 2,
        owner: "业务专家",
        updatedAt: "2026-06-10",
        href: "/knowledge-query?q=%E7%9B%AE%E5%BD%95%E9%99%90%E5%88%B6%E6%9D%A1%E4%BB%B6",
        chatHref: "/chat?question=catalog-limit"
      }
    ],
    source_coverages: [
      {
        id: "rule-source-supervision",
        name: "监管两库",
        sourceCollection: "supervision-rules-knowledge",
        ruleCount: 12840,
        indexStatus: "可引用",
        health: "规则库、知识库和知识点明细已同步。",
        href: "/documents"
      }
    ],
    run_snapshots: [
      {
        id: "run-duplicate-charge",
        ruleCode: "CHARGE-RULE-001",
        inputTable: "charge_detail",
        lastRunAt: "2026-06-11 10:24",
        hitCount: 1,
        linkedFinding: "FINDING-F044EBD309B659DC",
        nextAction: "进入疑点工作台复核。"
      }
    ],
    control_gates: [
      {
        id: "rule-gate-field",
        label: "字段可运行",
        status: "阻断",
        detail: "目录限制规则缺少部分 HIS 字段，不能直接进入批量运行。",
        owner: "信息科"
      }
    ],
    metrics: {
      rule_count: 2,
      enabled_rule_count: 1,
      pending_rule_count: 1,
      total_finding_count: 3,
      blocked_gate_count: 1,
      source_count: 1,
      run_count: 1
    },
    evidence_grade: "local-readonly-api",
    production_side_effect: "none",
    store: { ready: true, backend: "ReadonlyRulesWorkbenchSeed" }
  })),
  fetchRemediationWorkbench: vi.fn(async () => ({
    format: "remediation-workbench-v1",
    generated_at: "2026-06-22T00:00:00Z",
    workbench_id: "FUND-USAGE-REMEDIATION",
    workbench_title: "整改事项与补证闭环",
    workbench_scope: "把报告整改事项、补证请求、责任科室和验收门禁组织成可追踪的整改工作台。",
    remediation_cases: [
      {
        id: "remediation-duplicate-charge",
        title: "重复收费退费与流程复核",
        department: "医保办",
        owner: "医保办",
        status: "整改中",
        dueDate: "2026-06-20",
        reportNo: "AUDIT-REPORT-20260611-001",
        sourceFinding: "FINDING-F044EBD309B659DC",
        progress: 62,
        evidenceStatus: "已提交",
        nextAction: "核验退费凭证和流程复核记录。",
        href: "/pages/review-tasks"
      }
    ],
    evidence_requests: [
      {
        id: "evidence-refund",
        title: "重复收费退费凭证",
        linkedCaseId: "remediation-duplicate-charge",
        kind: "退费凭证",
        status: "已提交",
        owner: "医保办",
        dueDate: "2026-06-18",
        detail: "退费流水、患者确认和财务复核记录已提交，等待审计验收。",
        href: "/pages/review-tasks"
      },
      {
        id: "evidence-catalog-field",
        title: "目录限制 HIS 字段截图",
        linkedCaseId: "remediation-catalog-limit",
        kind: "HIS 凭证",
        status: "待上传",
        owner: "财务科",
        dueDate: "2026-06-21",
        detail: "需补充项目编码、支付范围、限制条件和结算口径字段截图。",
        href: "/knowledge-query?q=%E7%9B%AE%E5%BD%95%E9%99%90%E5%88%B6"
      }
    ],
    closure_gates: [
      {
        id: "remediation-gate-evidence",
        label: "补证材料完整",
        status: "阻断",
        detail: "附件归档缺少文件 hash，目录限制字段仍未上传。",
        owner: "信息科"
      }
    ],
    timeline: [
      {
        id: "timeline-attachment-blocked",
        time: "2026-06-12 11:20",
        title: "附件归档校验阻断",
        detail: "系统发现附件只有登记名称，缺少文件 hash 和归档位置。",
        status: "已阻断"
      }
    ],
    metrics: {
      case_count: 1,
      active_case_count: 1,
      closed_case_count: 0,
      pending_evidence_count: 1,
      blocked_gate_count: 1,
      average_progress: 62,
      timeline_count: 1
    },
    evidence_grade: "local-readonly-api",
    production_side_effect: "none",
    store: { ready: true, backend: "ReadonlyRemediationWorkbenchSeed" }
  })),
  fetchArchiveWorkbench: vi.fn(async () => ({
    format: "archive-workbench-v1",
    generated_at: "2026-06-22T00:00:00Z",
    archive_id: "FUND-USAGE-ARCHIVE",
    archive_title: "项目档案与审计日志归档",
    archive_scope: "汇总项目档案包、审计日志归档、签名链和归档前阻断原因，首期只读展示归档状态和受控导出入口。",
    archive_packages: [
      {
        id: "archive-package-fund-self-check",
        projectName: "医保基金使用合规专项自查",
        archiveNo: "ARCHIVE-SELF-CHECK-FUND-202606",
        status: "归档前检查",
        reportNo: "AUDIT-REPORT-20260611-001",
        owner: "项目负责人",
        archiveScope: "报告正文、整改事项、复核附件和审计日志索引。",
        evidenceSummary: "1 项整改门禁仍阻断，等待附件 hash 和目录限制字段。",
        signedAt: "2026-06-11",
        retainedUntil: "2026-12-09",
        href: "/reports",
        logHref: "/pages/audit-logs?entity_type=review-task&entity_id=review-task-0001"
      },
      {
        id: "archive-package-kb-governance",
        projectName: "审计知识库治理项目",
        archiveNo: "ARCHIVE-KB-GOV-202606",
        status: "已归档",
        reportNo: "INTERNAL-MEMO-20260609-001",
        owner: "信息科接口人",
        archiveScope: "知识库索引、文档入库、规则发布和巡检记录。",
        evidenceSummary: "签名 manifest 可验，archive root 巡检通过。",
        signedAt: "2026-06-10",
        retainedUntil: "2026-12-07",
        href: "/projects",
        logHref: "/pages/audit-logs?entity_type=project&entity_id=KB-GOVERNANCE-202606"
      },
      {
        id: "archive-package-catalog-limit",
        projectName: "医保目录限制条件核验",
        archiveNo: "ARCHIVE-CATALOG-LIMIT-202606",
        status: "材料阻断",
        reportNo: "WORKPAPER-20260611-002",
        owner: "业务专家",
        archiveScope: "规则命中、HIS 字段截图、整改验收和引用来源。",
        evidenceSummary: "目录限制 HIS 字段截图缺失，不能进入长期归档。",
        signedAt: "未签发",
        retainedUntil: "待补证后计算",
        href: "/remediation",
        logHref: "/pages/audit-logs?entity_type=rule&entity_id=CATALOG-RULE-014"
      }
    ],
    audit_runs: [
      {
        id: "archive-run-root-audit",
        title: "archive root 巡检",
        status: "通过",
        time: "2026-06-12 03:17",
        archiveRoot: "/opt/medical-audit/audit-log-archive",
        manifestCount: 0,
        failedCount: 0,
        detail: "latest JSON 报告 status=pass，当前没有失败 manifest。"
      }
    ],
    signature_items: [
      {
        id: "archive-signature-retention-batch",
        label: "retention-batch-0001.jsonl",
        status: "验签通过",
        sha256: "e7c4a6b2c41f0b1a9f7d2e3a6b8c9d01",
        detail: "归档文件、archive_sha256 和 detached HMAC-SHA256 manifest 一致。"
      }
    ],
    policy_items: [
      {
        id: "archive-policy-retention",
        label: "保留周期",
        value: "180 days",
        detail: "保留期外事件归档后再清理数据库记录。"
      }
    ],
    timeline: [
      {
        id: "archive-timeline-blocked",
        time: "2026-06-12 11:20",
        title: "附件 hash 阻断归档",
        detail: "缺少附件 hash 和归档位置，不能进入长期保存。",
        status: "待补证"
      }
    ],
    metrics: {
      package_count: 3,
      archived_package_count: 1,
      pending_package_count: 2,
      blocked_package_count: 1,
      audit_run_count: 1,
      signature_count: 1,
      policy_count: 1,
      timeline_count: 1,
      latest_archive_run_status: "通过"
    },
    evidence_grade: "local-readonly-api",
    production_side_effect: "none",
    store: { ready: true, backend: "ReadonlyArchiveWorkbenchSeed" }
  })),
  fetchBackendHealth: vi.fn(async () => ({
    status: "ok",
    version: "0.1.0",
    data_root: "/tmp/data"
  })),
  fetchProjectMembers: vi.fn(async (projectId: string) => ({
    items:
      projectId === "CATALOG-LIMIT-202606"
        ? [
            {
              id: "member-catalog-owner",
              project_key: "CATALOG-LIMIT-202606",
              name: "业务专家",
              role: "业务专家",
              department: "医保办",
              status: "在项目中",
              created_by: "system",
              source: "system-default",
              metadata: {}
            },
            {
              id: "member-catalog-it",
              project_key: "CATALOG-LIMIT-202606",
              name: "信息科接口人",
              role: "信息科",
              department: "信息科",
              status: "待确认",
              created_by: "system",
              source: "system-default",
              metadata: {}
            }
          ]
        : [
            {
              id: "member-auditor",
              project_key: "SELF-CHECK-FUND-20260607",
              name: "审计员",
              role: "审计员",
              department: "内审部",
              status: "在项目中",
              created_by: "system",
              source: "system-default",
              metadata: {}
            },
            {
              id: "member-owner",
              project_key: "SELF-CHECK-FUND-20260607",
              name: "项目负责人",
              role: "项目负责人",
              department: "内审部",
              status: "在项目中",
              created_by: "system",
              source: "system-default",
              metadata: {}
            },
            {
              id: "member-it",
              project_key: "SELF-CHECK-FUND-20260607",
              name: "信息科接口人",
              role: "信息科",
              department: "信息科",
              status: "待确认",
              created_by: "system",
              source: "system-default",
              metadata: {}
            }
          ],
    project_key: projectId,
    roles: ["项目负责人", "审计员", "业务专家", "信息科", "只读观察员"],
    statuses: ["在项目中", "待确认"],
    store: { ready: true, backend: "SqlAlchemyProjectMemberStore" }
  })),
  fetchProjects: vi.fn(async () => ({
    items: [
      {
        id: "SELF-CHECK-FUND-20260607",
        name: "医保基金使用合规专项自查",
        audit_topic: "医保基金使用合规",
        organization_name: "单院医保内审试运行",
        member_count: 3,
        creator: "项目负责人",
        created_at: "2026-06-07",
        status: "进行中",
        operation_label: "进入项目",
        source: "system-default"
      },
      {
        id: "CATALOG-LIMIT-202606",
        name: "医保目录限制条件核验",
        audit_topic: "目录限制",
        organization_name: "单院医保内审试运行",
        member_count: 4,
        creator: "业务专家",
        created_at: "2026-06-09",
        status: "待启动",
        operation_label: "查看成员",
        source: "system-default"
      }
    ],
    roles: ["项目负责人", "审计员", "业务专家", "信息科", "只读观察员"],
    statuses: ["在项目中", "待确认"],
    store: { ready: true, backend: "SqlAlchemyProjectMemberStore" }
  })),
  fetchAgents: vi.fn(async () => ({
    items: [
      {
        id: "agent-citation-check",
        name: "引用依据核验助手",
        category: "业务类",
        topic: "医保基金使用合规",
        prompt: "只基于命中的法规、目录、规则和风险清单回答；没有引用时输出待补证据。",
        knowledge_base: "系统医保审计知识库",
        project_name: "医保基金使用合规专项自查",
        status: "active",
        created_by: "system",
        updated_at: "2026-06-12",
        prompt_version: 1,
        prompt_version_key: "agent-citation-check@v1",
        prompt_versions: [
          {
            version: 1,
            prompt: "只基于命中的法规、目录、规则和风险清单回答；没有引用时输出待补证据。",
            change_summary: "initial prompt",
            created_by: "system",
            created_at: "2026-06-12"
          }
        ],
        visibility_scope: "system",
        allowed_roles: ["admin", "technician", "director", "member"],
        source: "system-default",
        metadata: {}
      },
      {
        id: "agent-duplicate-charge",
        name: "重复收费复核助手",
        category: "业务类",
        topic: "收费明细复核",
        prompt: "围绕同就诊、同项目、同日期的重复收费线索，列出应核验的执行记录、数量和例外情形。",
        knowledge_base: "规则库与风险清单",
        project_name: "医保基金使用合规专项自查",
        status: "active",
        created_by: "system",
        updated_at: "2026-06-11",
        prompt_version: 1,
        prompt_version_key: "agent-duplicate-charge@v1",
        prompt_versions: [
          {
            version: 1,
            prompt: "围绕同就诊、同项目、同日期的重复收费线索，列出应核验的执行记录、数量和例外情形。",
            change_summary: "initial prompt",
            created_by: "system",
            created_at: "2026-06-11"
          }
        ],
        visibility_scope: "system",
        allowed_roles: ["admin", "technician", "director", "member"],
        source: "system-default",
        metadata: {}
      },
      {
        id: "agent-report-draft",
        name: "底稿摘要助手",
        category: "效率类",
        topic: "审计底稿",
        prompt: "把已复核的引用、疑点和附件清单整理为底稿摘要，保留待人工确认标记。",
        knowledge_base: "项目复核资料",
        project_name: "医保基金使用合规专项自查",
        status: "active",
        created_by: "system",
        updated_at: "2026-06-10",
        prompt_version: 1,
        prompt_version_key: "agent-report-draft@v1",
        prompt_versions: [
          {
            version: 1,
            prompt: "把已复核的引用、疑点和附件清单整理为底稿摘要，保留待人工确认标记。",
            change_summary: "initial prompt",
            created_by: "system",
            created_at: "2026-06-10"
          }
        ],
        visibility_scope: "system",
        allowed_roles: ["admin", "technician", "director", "member"],
        source: "system-default",
        metadata: {}
      },
      {
        id: "agent-custom-inactive",
        name: "已下架测试智能体",
        category: "业务类",
        topic: "状态治理",
        prompt: "这个智能体用于验证非 active 状态不会进入新对话选择。",
        knowledge_base: "项目默认知识库",
        project_name: "医保基金使用合规专项自查",
        status: "inactive",
        created_by: "next-admin",
        updated_at: "2026-06-22T00:00:00Z",
        prompt_version: 1,
        prompt_version_key: "agent-custom-inactive@v1",
        prompt_versions: [
          {
            version: 1,
            prompt: "这个智能体用于验证非 active 状态不会进入新对话选择。",
            change_summary: "initial prompt",
            created_by: "next-admin",
            created_at: "2026-06-22T00:00:00Z"
          }
        ],
        visibility_scope: "project",
        allowed_roles: ["admin", "technician", "director", "member"],
        source: "custom",
        metadata: {}
      }
    ],
    categories: ["业务类", "效率类", "研究类"],
    store: { ready: true, backend: "SqlAlchemyAgentStore" }
  })),
  fetchSearchBackendStatus: vi.fn(async () => ({
    backend: "postgres",
    ready: true,
    details: { matching_embedding_count: 48985 }
  })),
  runKnowledgeQuery: vi.fn(async (payload: { readonly question: string }) => ({
    question: payload.question,
    answer: "应核验诊疗记录、收费明细和政策依据。",
    confidence: "high",
    fallback_used: true,
    basis_groups: [
      {
        evidence_type: "law",
        title: "法规依据",
        items: [
          {
            citation_id: "C1",
            chunk_id: "chunk-doc-001",
            source_collection: "medical-insurance-laws",
            snippet: "医疗机构应当保留医保基金审核依据。",
            locator: {
              source_path: "全量法律/law.md",
              line_start: 1,
              line_end: 1
            },
            index_version_key: "index-v1",
            source_package_version_key: "package-v1"
          }
        ]
      }
    ],
    citations: [
      {
        citation_id: "C1",
        marker: "[C1]",
        chunk_id: "chunk-doc-001",
        evidence_type: "law",
        source_collection: "medical-insurance-laws",
        snippet: "医疗机构应当保留医保基金审核依据。",
        locator: {
          source_path: "全量法律/law.md",
          line_start: 1,
          line_end: 1
        },
        index_version_key: "index-v1",
        source_package_version_key: "package-v1"
      }
    ],
    personal_upload_matches: [
      {
        id: "document-upload-history#chunk-1",
        upload_id: "document-upload-history",
        name: "policy-retained.pdf",
        extension: "pdf",
        created_by: "next-knowledge-query",
        indexed_at: "2026-06-21T00:00:00Z",
        chunk_index: 0,
        snippet: "个人材料提示：医保基金审核依据需核对院内报销清单。",
        score: 6,
        locator: {
          type: "personal-upload",
          upload_id: "document-upload-history",
          file_name: "policy-retained.pdf",
          chunk_index: 0
        }
      }
    ],
    query_log_index: 0
  }))
}));

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
  window.history.replaceState(null, "", "/");
});

const routePages = [
  ["/chat", ChatPortalPage],
  ["/agents", AgentsPage],
  ["/agent-market", AgentMarketPage],
  ["/knowledge-base", KnowledgeBasePage],
  ["/documents", DocumentsPage],
  ["/analytics", AnalyticsPage],
  ["/graph", GraphPage],
  ["/reports", ReportsPage],
  ["/projects", ProjectsPage]
] as const;

const allWorkspaceRoutePages = [
  [workspaceHomeNavigation.href, WorkspacePage],
  ...routePages,
  ["/guided-check", GuidedCheckPage],
  ["/rules", RulesPage],
  ["/remediation", RemediationPage],
  ["/archive", ArchivePage],
] as const;

describe("workspace foundation pages", () => {
  it("keeps Next-owned portal targets backed by a page with one h1", () => {
    expect(routePages.map(([href]) => href)).toEqual(
      primaryNavigation.filter((item) => item.target === "workspace").map((item) => item.href)
    );

    for (const [href, Page] of routePages) {
      const { unmount } = render(<Page />);

      expect(screen.getAllByRole("heading", { level: 1 }), href).toHaveLength(1);

      unmount();
    }
  });

  it("covers every workspace navigation target with an implemented page", () => {
    const configuredWorkspaceRoutes = [
      workspaceHomeNavigation,
      ...primaryNavigation,
      ...secondaryNavigation
    ].map((item) => item.href);

    expect(allWorkspaceRoutePages.map(([href]) => href).sort()).toEqual(configuredWorkspaceRoutes.sort());

    for (const [, Page] of allWorkspaceRoutePages) {
      const { unmount } = render(<Page />);
      expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
      unmount();
    }
  });

  it("exposes the dashboard sections owned by the workspace page", async () => {
    render(<WorkspacePage />);

    expect(screen.getByRole("region", { name: "项目关键指标" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "当前阶段：形成判断" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "需要人工处理" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "项目审计链动态" })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getAllByText("FastAPI 正常").length).toBeGreaterThan(0);
    });
  });

  it("renders the current self-check project dashboard", async () => {
    render(<WorkspacePage />);

    expect(screen.getByRole("heading", { name: "医保基金使用合规专项自查" })).toBeInTheDocument();
    expect(screen.getByText("待处理疑点")).toBeInTheDocument();
    expect(screen.getByText("待补证据")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getAllByText("FastAPI 正常").length).toBeGreaterThan(0);
    });
  });

  it("keeps legacy real routes outside the primary portal navigation", async () => {
    render(<KnowledgeQueryPage />);
    expect(screen.getByRole("heading", { name: "引用优先的知识查询" })).toBeInTheDocument();

    render(<FindingsPage />);
    expect(screen.getByRole("heading", { name: "规则命中疑点工作台" })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "疑点生成链路未就绪" })).toBeInTheDocument();
    });
  });

  it("renders the AI chat portal handoff to backend evidence chat", async () => {
    const { container } = render(<ChatPortalPage />);

    expect(screen.getByRole("heading", { name: "AI 审证对话工作台" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "问题构建" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "知识来源" })).toBeInTheDocument();
    expect(screen.getByText("当前智能体")).toBeInTheDocument();
    expect(screen.getAllByText("法规政策").length).toBeGreaterThan(0);
    expect(screen.getAllByText("医保目录").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "进入审证对话" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "打开后端深页" })).toHaveAttribute("href", "/pages/chat");
    expect(screen.getByRole("link", { name: "先检索文档" })).toHaveAttribute("href", "/documents");
    expect(container.querySelector('input[name="project_name"]')).toHaveAttribute(
      "value",
      "医保基金使用合规专项自查"
    );
    expect(screen.getByRole("heading", { name: "可用智能体" })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("智能体已同步")).toBeInTheDocument();
    });
    expect(screen.queryByText("已下架测试智能体")).not.toBeInTheDocument();
    expect(screen.getByText("参保身份、就诊记录和结算记录不一致时，应先做哪三类交叉核验？")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "证据边界" })).toBeInTheDocument();
  });

  it("renders the guided self-check workbench with steps, prompts and gates", () => {
    render(<GuidedCheckPage />);

    expect(screen.getByRole("heading", { name: "AI 引导自查工作台" })).toBeInTheDocument();
    expect(screen.getByText("已完成步骤")).toBeInTheDocument();
    expect(screen.getByText("可提问模板")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "自查路径" })).toBeInTheDocument();
    expect(screen.getByText("锁定自查范围")).toBeInTheDocument();
    expect(screen.getByText("上传并识别数据")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "AI 提问模板" })).toBeInTheDocument();
    expect(screen.getByText("重复收费复核助手")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "证据门禁" })).toBeInTheDocument();
    expect(screen.getByText("目录限制 HIS 字段截图")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "风险预检" })).toBeInTheDocument();
    expect(screen.getByText("重复收费线索")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "自查动态" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "进入 AI 审证对话" })).toHaveAttribute("href", "/chat");
    expect(screen.getAllByRole("link", { name: "进入对话" })[0]).toHaveAttribute(
      "href",
      expect.stringContaining("/chat?agent=agent-duplicate-charge")
    );
  });

  it("analyzes an uploaded CSV with audit-ready quality hints", async () => {
    render(<AnalyticsPage />);

    expect(screen.getByRole("heading", { name: "常用表模板" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /表1 · 医保费用汇总表/ })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: /表2 · 医保费用分类汇总表/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /表3 · 就诊费用明细表/ })).toBeInTheDocument();
    expect(screen.getByText("当前模板：表1")).toBeInTheDocument();
    expect(screen.getByText("表1_医保费用汇总表-模版.xlsx / 汇总表")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "模板字段" })).toBeInTheDocument();
    expect(screen.getByText("统筹支付")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /表3 · 就诊费用明细表/ }));
    expect(screen.getByText("当前模板：表3")).toBeInTheDocument();
    expect(screen.getByDisplayValue(/按就诊记录号、诊断、医疗费用/)).toBeInTheDocument();

    const input = screen.getByLabelText("上传审计表格");
    const file = new File(
      [
        [
          "patient_id,visit_date,item_code,charge_amount,insurance_pay",
          "P001,2026-01-01,A100,120.00,80.00",
          "P001,2026-01-01,A100,120.00,80.00",
          "P002,2026-01-02,B200,,50.00"
        ].join("\n")
      ],
      "charge-sample.csv",
      { type: "text/csv" }
    );

    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      expect(uploadAnalysisTable).toHaveBeenCalledWith(file);
    });
    await waitFor(() => {
      expect(fetchAnalysisUploadHistory).toHaveBeenCalled();
    });
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "charge-sample.csv" })).toBeInTheDocument();
    });
    expect(screen.getByText("数据质量提示")).toBeInTheDocument();
    expect(screen.getByText("审计初步分析")).toBeInTheDocument();
    expect(screen.getByText("金额/费用字段")).toBeInTheDocument();
    expect(screen.getByText("重复收费核验字段基础完整，可按患者/就诊、项目、日期和金额形成初筛分组。")).toBeInTheDocument();
    expect(screen.getByText("发现 1 条完全重复行。")).toBeInTheDocument();
    expect(screen.getByText("上传历史")).toBeInTheDocument();
    expect(screen.getByText("history-charge.csv")).toBeInTheDocument();
  });

  it("renders project list and creates project members through the backend API", async () => {
    render(<ProjectsPage />);

    expect(screen.getByRole("heading", { name: "审计项目管理" })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("项目后端已连接")).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText("成员后端已连接")).toBeInTheDocument();
    });
    expect(screen.getByRole("heading", { name: "项目列表" })).toBeInTheDocument();
    expect(screen.getByText("项目名称")).toBeInTheDocument();
    expect(screen.getByText("成员数")).toBeInTheDocument();
    expect(screen.getByText("创建人")).toBeInTheDocument();
    expect(screen.getByText("创建时间")).toBeInTheDocument();
    expect(screen.getByText("医保目录限制条件核验")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "医院权限角色矩阵" })).toBeInTheDocument();
    expect(screen.getAllByText("管理员").length).toBeGreaterThan(0);
    expect(screen.getAllByText("技术人员").length).toBeGreaterThan(0);
    expect(screen.getAllByText("主任").length).toBeGreaterThan(0);
    expect(screen.getAllByText("普通成员").length).toBeGreaterThan(0);
    expect(screen.getByText("权限已接入")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "查看成员" }));
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "医保目录限制条件核验" })).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText("权限角色视图"), { target: { value: "hospital-technician" } });
    expect(screen.getByLabelText("项目成员角色")).toHaveValue("信息科");
    expect(screen.getByLabelText("部门")).toHaveValue("信息科");
    expect(screen.getByText("提交到现有后端角色：信息科")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("姓名"), { target: { value: "赵审计" } });
    fireEvent.click(screen.getByRole("button", { name: "添加成员" }));

    await waitFor(() => {
      expect(createProjectMember).toHaveBeenCalledWith("CATALOG-LIMIT-202606", {
        name: "赵审计",
        role: "信息科",
        department: "信息科"
      });
    });
    expect(screen.getByText("赵审计")).toBeInTheDocument();
    expect(screen.getAllByText("信息科").length).toBeGreaterThan(0);
    expect(screen.getAllByText("待确认").length).toBeGreaterThan(0);
  });

  it("filters agent marketplace templates and keeps agent chat handoff in the portal", async () => {
    render(<AgentMarketPage />);

    expect(screen.getByRole("heading", { name: "医疗审计场景模板" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "智能体分类筛选" })).toBeInTheDocument();
    expect(screen.getByText("医保目录限制审查")).toBeInTheDocument();
    expect(screen.getByText("审计底稿生成模板")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "套用并新增智能体" })[0]).toHaveAttribute(
      "href",
      "/agents?template=template-catalog-limit#new-agent"
    );

    fireEvent.click(screen.getByRole("button", { name: "效率类" }));
    expect(screen.getByText("审计底稿生成模板")).toBeInTheDocument();
    expect(screen.queryByText("医保目录限制审查")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "全部" }));
    fireEvent.change(screen.getByLabelText("搜索智能体模板"), { target: { value: "身份" } });
    expect(screen.getByText("参保身份异常核验")).toBeInTheDocument();
    expect(screen.queryByText("政策口径对比")).not.toBeInTheDocument();

    render(<AgentsPage />);
    await waitFor(() => {
      expect(screen.getByText("后端已连接")).toBeInTheDocument();
    });
    expect(screen.getAllByText("医保基金使用合规专项自查").length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "进入对话" })[0]).toHaveAttribute("href", "/chat?agent=agent-citation-check");
  });

  it("prefills a custom audit agent from a marketplace template before backend save", async () => {
    window.history.replaceState(null, "", "/agents?template=template-identity-risk#new-agent");
    render(<AgentsPage />);

    await waitFor(() => {
      expect(screen.getByRole("status", { name: "模板已预填" })).toBeInTheDocument();
    });
    expect(screen.getByDisplayValue("参保身份异常核验")).toBeInTheDocument();
    expect(screen.getByDisplayValue("身份骗保")).toBeInTheDocument();
    expect(screen.getByDisplayValue("风险负面清单")).toBeInTheDocument();
    expect(screen.getByDisplayValue("医保基金使用合规专项自查")).toBeInTheDocument();
    expect(screen.getByDisplayValue(/围绕参保身份、就诊记录和结算记录/)).toBeInTheDocument();
    expect(createAuditAgent).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "新增智能体" }));

    await waitFor(() => {
      expect(createAuditAgent).toHaveBeenCalledWith({
        name: "参保身份异常核验",
        category: "业务类",
        topic: "身份骗保",
        prompt: "围绕参保身份、就诊记录和结算记录查找不一致线索，只输出可追溯问题清单。",
        knowledge_base: "风险负面清单",
        project_name: "医保基金使用合规专项自查",
        visibility_scope: "project",
        allowed_roles: ["admin", "technician", "director", "member"]
      });
    });
  });

  it("creates a custom audit agent through the backend API", async () => {
    render(<AgentsPage />);

    await waitFor(() => {
      expect(screen.getByText("后端已连接")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText("名称"), { target: { value: "目录限制核验助手" } });
    fireEvent.change(screen.getByLabelText("审计专题"), { target: { value: "医保目录限制条件核验" } });
    fireEvent.change(screen.getByLabelText("提示词"), {
      target: { value: "仅基于目录限制字段和引用依据输出待补证问题。" }
    });
    fireEvent.click(screen.getByRole("button", { name: "新增智能体" }));

    await waitFor(() => {
      expect(createAuditAgent).toHaveBeenCalledWith({
        name: "目录限制核验助手",
        category: "业务类",
        topic: "医保目录限制条件核验",
        prompt: "仅基于目录限制字段和引用依据输出待补证问题。",
        knowledge_base: "项目默认知识库",
        project_name: "医保基金使用合规专项自查",
        visibility_scope: "project",
        allowed_roles: ["admin", "technician", "director", "member"]
      });
    });
    expect(screen.getAllByText("目录限制核验助手").length).toBeGreaterThan(0);
    expect(screen.getAllByText("v1").length).toBeGreaterThan(0);
    expect(screen.getAllByText("项目内").length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: "版本对比" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "调用与反馈" })).toBeInTheDocument();
    await waitFor(() => {
      expect(fetchAuditAgent).toHaveBeenCalledWith("agent-custom-test");
    });
    await waitFor(() => {
      expect(screen.getByLabelText("新版本提示词")).toHaveValue(
        "仅基于目录限制字段和引用依据输出待补证问题。"
      );
    });

    fireEvent.change(screen.getByLabelText("新版本提示词"), {
      target: { value: "仅基于目录限制字段、引用依据和原文截图输出待补证问题。" }
    });
    fireEvent.change(screen.getByLabelText("变更说明"), {
      target: { value: "补充原文截图约束。" }
    });
    fireEvent.click(screen.getByRole("button", { name: "保存新版本" }));

    await waitFor(() => {
      expect(createAuditAgentPromptVersion).toHaveBeenCalledWith("agent-custom-test", {
        prompt: "仅基于目录限制字段、引用依据和原文截图输出待补证问题。",
        change_summary: "补充原文截图约束。",
        review_note: "补充原文截图约束。"
      });
    });
    expect(await screen.findByText("已保存 目录限制核验助手 v2，待审批通过后激活。")).toBeInTheDocument();
    expect(screen.getAllByText("待审批").length).toBeGreaterThan(0);
    expect(screen.getByText("审核对象：v2")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("审核意见"), {
      target: { value: "主任已复核提示词引用边界。" }
    });
    fireEvent.click(screen.getByRole("button", { name: "审批通过" }));

    await waitFor(() => {
      expect(reviewAuditAgentPromptVersion).toHaveBeenCalledWith("agent-custom-test", {
        version: 2,
        review_status: "approved",
        review_note: "主任已复核提示词引用边界。"
      });
    });
    expect(await screen.findByText("已批准并激活 目录限制核验助手 v2。")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "登记试用" }));

    await waitFor(() => {
      expect(recordAuditAgentInvocation).toHaveBeenCalledWith("agent-custom-test", {
        invocation_source: "agent-workspace",
        question: "目录限制核验助手 工作台试用登记",
        metadata: { prompt_version_key: "agent-custom-test@v2" }
      });
    });
    expect(await screen.findByText(/agent-workspace/)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("效果评级"), { target: { value: "needs_review" } });
    fireEvent.change(screen.getByLabelText("反馈说明"), {
      target: { value: "需要补充目录限制原文适用条件。" }
    });
    fireEvent.click(screen.getByRole("button", { name: "提交反馈" }));

    await waitFor(() => {
      expect(submitAuditAgentFeedback).toHaveBeenCalledWith("agent-custom-test", {
        invocation_id: "agent-invocation-test",
        rating: "needs_review",
        comment: "需要补充目录限制原文适用条件。",
        metadata: { prompt_version_key: "agent-custom-test@v2" }
      });
    });
    expect(await screen.findByText("需要补充目录限制原文适用条件。")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "下架智能体" }));

    await waitFor(() => {
      expect(updateAuditAgentLifecycle).toHaveBeenCalledWith("agent-custom-test", {
        status: "inactive",
        reason: "工作台下架，保留历史追溯。"
      });
    });
  });

  it("keeps prompt activation controls disabled for technician role", async () => {
    window.localStorage.setItem(AUDIT_ROLE_STORAGE_KEY, "technician");
    render(
      <AuditUserProvider>
        <AgentsPage />
      </AuditUserProvider>
    );

    await waitFor(() => {
      expect(screen.getByText("后端已连接")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText("名称"), { target: { value: "目录限制核验助手" } });
    fireEvent.change(screen.getByLabelText("审计专题"), { target: { value: "医保目录限制条件核验" } });
    fireEvent.change(screen.getByLabelText("提示词"), {
      target: { value: "仅基于目录限制字段和引用依据输出待补证问题。" }
    });
    fireEvent.click(screen.getByRole("button", { name: "新增智能体" }));

    await waitFor(() => {
      expect(createAuditAgent).toHaveBeenCalled();
    });
    await waitFor(() => {
      expect(screen.getByLabelText("新版本提示词")).toHaveValue(
        "仅基于目录限制字段和引用依据输出待补证问题。"
      );
    });

    fireEvent.change(screen.getByLabelText("新版本提示词"), {
      target: { value: "仅基于目录限制字段、引用依据和原文截图输出待补证问题。" }
    });
    fireEvent.change(screen.getByLabelText("变更说明"), {
      target: { value: "补充原文截图约束。" }
    });
    fireEvent.click(screen.getByRole("button", { name: "保存新版本" }));

    await waitFor(() => {
      expect(createAuditAgentPromptVersion).toHaveBeenCalledWith("agent-custom-test", {
        prompt: "仅基于目录限制字段、引用依据和原文截图输出待补证问题。",
        change_summary: "补充原文截图约束。",
        review_note: "补充原文截图约束。"
      });
    });

    const approveButton = await screen.findByRole("button", { name: "审批通过" });
    const changesButton = screen.getByRole("button", { name: "要求修改" });
    await waitFor(() => {
      expect(approveButton).toBeDisabled();
      expect(changesButton).toBeDisabled();
    });

    fireEvent.click(approveButton);
    fireEvent.click(changesButton);
    expect(reviewAuditAgentPromptVersion).not.toHaveBeenCalled();
    expect(rollbackAuditAgentPromptVersion).not.toHaveBeenCalled();
  });

  it("soft archives a custom audit agent without hard deletion", async () => {
    render(<AgentsPage />);

    await waitFor(() => {
      expect(screen.getByText("后端已连接")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText("名称"), { target: { value: "目录限制核验助手" } });
    fireEvent.change(screen.getByLabelText("审计专题"), { target: { value: "医保目录限制条件核验" } });
    fireEvent.change(screen.getByLabelText("提示词"), {
      target: { value: "仅基于目录限制字段和引用依据输出待补证问题。" }
    });
    fireEvent.click(screen.getByRole("button", { name: "新增智能体" }));

    await waitFor(() => {
      expect(screen.getAllByText("目录限制核验助手").length).toBeGreaterThan(0);
    });

    fireEvent.click(screen.getByRole("button", { name: "软归档智能体" }));

    await waitFor(() => {
      expect(updateAuditAgentLifecycle).toHaveBeenCalledWith("agent-custom-test", {
        status: "archived",
        reason: "工作台软归档，不做物理删除。"
      });
    });
  });

  it("renders read-only knowledge base asset metrics", async () => {
    render(<KnowledgeBasePage />);

    expect(screen.getByRole("heading", { name: "个人、系统、公开知识库" })).toBeInTheDocument();
    expect(screen.getAllByText("个人知识库").length).toBeGreaterThan(0);
    expect(screen.getAllByText("系统知识库").length).toBeGreaterThan(0);
    expect(screen.getAllByText("公开知识库").length).toBeGreaterThan(0);
    expect(screen.getAllByText("文档数").length).toBeGreaterThan(0);
    expect(screen.getAllByText("字符数").length).toBeGreaterThan(0);
    expect(screen.getAllByText("关联应用数").length).toBeGreaterThan(0);
    expect(screen.getAllByText("系统医保审计知识库").length).toBeGreaterThan(0);
    expect(screen.getAllByText("法规政策、医保目录、监管规则和风险负面清单组成的系统检索底座。").length).toBeGreaterThan(0);
    await waitFor(() => {
      expect(screen.getByText("检索索引：就绪（postgres）")).toBeInTheDocument();
    });
  });

  it("falls back to sample knowledge base when search backend probe fails", async () => {
    vi.mocked(fetchSearchBackendStatus).mockRejectedValueOnce(new Error("search service down"));

    render(<KnowledgeBasePage />);

    await waitFor(() => {
      expect(screen.getByText("检索索引：异常")).toBeInTheDocument();
    });
    expect(screen.getByRole("heading", { name: "个人、系统、公开知识库" })).toBeInTheDocument();
  });

  it("runs document search through the backend query API and renders citations", async () => {
    render(<DocumentsPage />);

    expect(screen.getByRole("heading", { name: "材料与知识库统一检索" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "知识库分类统计" })).toBeInTheDocument();
    expect(screen.getByLabelText("审计问题或文档关键词")).toBeInTheDocument();
    expect(screen.getByLabelText("仅标题")).toBeInTheDocument();
    expect(screen.getByText("无引用不下结论")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "搜索历史" })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("医保基金支付异常")).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(fetchDocumentPermissions).toHaveBeenCalled();
    });
    await waitFor(() => {
      expect(fetchDocumentUploads).toHaveBeenCalled();
    });
    expect(screen.getByText("权限已连接")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "个人材料" })).toBeInTheDocument();
    expect(screen.getByText("policy-retained.pdf")).toBeInTheDocument();
    expect(screen.getByText("待治理")).toBeInTheDocument();
    expect(screen.getByText("安全：本地策略通过 / DLP：未提示")).toBeInTheDocument();
    expect(screen.getByText("本地索引：未入本地索引")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "下载留存文件" })).toHaveAttribute(
      "href",
      "/api/v1/documents/uploads/document-upload-history/download"
    );
    expect(screen.getAllByText("已连接").length).toBeGreaterThan(0);
    expect(screen.getByText("监管两库")).toBeInTheDocument();
    expect(screen.getByText("risk-negative-list")).toBeInTheDocument();
    expect(screen.getByText("等待检索")).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText("仅标题"));
    fireEvent.change(screen.getByLabelText("审计问题或文档关键词"), {
      target: { value: "医保目录限制" }
    });
    expect(screen.getByText("医保目录限制条件资料包")).toBeInTheDocument();
    expect(screen.getByText("当前关键词没有匹配的标题文档，可切换为全文模式或直接执行后端检索。")).toBeInTheDocument();
    expect(screen.getByText("仅标题模式会同步传入后端 title_only=true，并只在标题和路径元数据上匹配引用。")).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("仅标题"));

    const documentFile = new File(["policy"], "policy.pdf", { type: "application/pdf" });
    fireEvent.change(screen.getByLabelText("上传个人知识库材料"), {
      target: { files: [documentFile] }
    });
    fireEvent.click(screen.getByRole("button", { name: "上传材料" }));
    await waitFor(() => {
      expect(uploadPersonalDocument).toHaveBeenCalledWith(documentFile);
    });
    expect(screen.getByText("policy.pdf 已留存，治理状态：待治理")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /监管两库/ }));
    fireEvent.change(screen.getByLabelText("审计问题或文档关键词"), {
      target: { value: "医保基金审核依据" }
    });
    fireEvent.click(screen.getByRole("button", { name: "执行检索" }));

    await waitFor(() => {
      expect(runKnowledgeQuery).toHaveBeenCalledWith({
        question: "医保基金审核依据",
        top_k: 8,
        source_collections: ["supervision-rules-knowledge"],
        title_only: false
      });
    });
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "医保基金审核依据" })).toBeInTheDocument();
    });
    expect(screen.getByText("应核验诊疗记录、收费明细和政策依据。")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "引用分组：法规政策" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "个人材料命中" })).toBeInTheDocument();
    expect(screen.getByText("个人材料提示：医保基金审核依据需核对院内报销清单。")).toBeInTheDocument();
    expect(screen.getByText("医疗机构应当保留医保基金审核依据。")).toBeInTheDocument();
    expect(screen.getByText("来源: medical-insurance-laws")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "核验原文" })).toHaveAttribute("href", "/pages/preview/chunk-doc-001");
    expect(screen.getByRole("heading", { name: "对话文档" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "知识库文档" })).toBeInTheDocument();
    expect(screen.getByText("重复收费疑点复核对话")).toBeInTheDocument();
    expect(screen.getByText("医保目录限制条件资料包")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "转入 AI 对话" })[0]).toHaveAttribute(
      "href",
      expect.stringContaining("/chat?question=")
    );
    expect(fetchQueryHistory).toHaveBeenCalled();
  });

  it("renders the read-only knowledge graph coverage view", async () => {
    render(<GraphPage />);

    expect(screen.getByRole("heading", { name: "知识图谱入口" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "审计知识图谱静态关系预览" })).toBeInTheDocument();
    expect(screen.getByText("医保基金使用合规专项图谱")).toBeInTheDocument();
    expect(screen.getByText("节点覆盖")).toBeInTheDocument();
    expect(screen.getByText("节点证据")).toBeInTheDocument();
    expect(screen.getAllByText("项目").length).toBeGreaterThan(0);
    expect(screen.getAllByText("知识库").length).toBeGreaterThan(0);
    expect(screen.getAllByText("文档").length).toBeGreaterThan(0);
    expect(screen.getAllByText("规则").length).toBeGreaterThan(0);
    expect(screen.getAllByText("疑点").length).toBeGreaterThan(0);
    expect(screen.getAllByText("复核").length).toBeGreaterThan(0);
    expect(screen.getAllByText("报告").length).toBeGreaterThan(0);
    expect(screen.getAllByText("整改").length).toBeGreaterThan(0);
    expect(screen.getAllByText("FINDING-F044EBD309B659DC").length).toBeGreaterThan(0);
    expect(screen.getAllByText("review-task-0007").length).toBeGreaterThan(0);
    await waitFor(() => {
      expect(fetchGraphWorkbench).toHaveBeenCalledTimes(1);
    });
    expect(screen.getByText("后端已连接")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("检索索引：就绪（postgres）")).toBeInTheDocument();
    });
  });

  it("keeps graph sample topology when search backend probe fails", async () => {
    vi.mocked(fetchSearchBackendStatus).mockRejectedValueOnce(new Error("search service down"));

    render(<GraphPage />);

    await waitFor(() => {
      expect(screen.getByText("检索索引：异常")).toBeInTheDocument();
    });
    expect(screen.getByRole("heading", { name: "知识图谱入口" })).toBeInTheDocument();
  });

  it("renders the report homepage with API-first templates, downloads and gates", async () => {
    render(<ReportsPage />);

    expect(screen.getByRole("heading", { name: "底稿生成与报告记录" })).toBeInTheDocument();
    await waitFor(() => {
      expect(fetchReportWorkbench).toHaveBeenCalledTimes(1);
    });
    expect(screen.getByText("已签发报告")).toBeInTheDocument();
    expect(screen.getAllByText("门禁阻断").length).toBeGreaterThan(0);
    expect(screen.getAllByText("纳入疑点").length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: "提示词模板生成" })).toBeInTheDocument();
    expect(screen.getByText("费用汇总风险底稿")).toBeInTheDocument();
    expect(screen.getByText("分类费用复核清单")).toBeInTheDocument();
    expect(screen.getByText("就诊明细疑点摘要")).toBeInTheDocument();
    expect(screen.getByText("表1_医保费用汇总表-模版.xlsx")).toBeInTheDocument();
    expect(screen.getAllByText("模板字段已注册").length).toBeGreaterThan(0);
    expect(screen.getByText("隐私字段处理记录")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "套用模板" })[0]).toHaveAttribute("href", expect.stringContaining("/chat?agent="));
    expect(screen.getByRole("heading", { name: "历史生成记录" })).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { name: "报告门禁预检" }).length).toBeGreaterThan(0);
    expect(screen.getByText("底稿与负责人确认")).toBeInTheDocument();
    expect(screen.getByText("附件登记与报告草稿")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "底稿证据来源" })).toBeInTheDocument();
    expect(screen.getByText("workpaper-20260604-001")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "整改跟踪" })).toBeInTheDocument();
    expect(screen.getByText("重复收费退费与流程复核")).toBeInTheDocument();
    expect(screen.getByText("signed-report-abc123")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "查看详情" })[0]).toHaveAttribute("href", "/pages/review-tasks");
    expect(screen.getByRole("link", { name: "任务 Word" })).toHaveAttribute(
      "href",
      "/review-tasks/review-task-0001/export?format=docx"
    );
    expect(screen.getByRole("link", { name: "报告 Word" })).toHaveAttribute(
      "href",
      "/review-tasks/review-task-0001/signed-report?format=docx"
    );
  });

  it("renders the remediation homepage with evidence requests and closure gates", async () => {
    render(<RemediationPage />);

    expect(screen.getByRole("heading", { name: "整改事项与补证闭环" })).toBeInTheDocument();
    expect(screen.getByText("未关闭事项")).toBeInTheDocument();
    expect(screen.getByText("待补证材料")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "整改台账" })).toBeInTheDocument();
    expect(screen.getAllByText("重复收费退费与流程复核").length).toBeGreaterThan(0);
    expect(screen.getAllByText("FINDING-F044EBD309B659DC").length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: "补证请求" })).toBeInTheDocument();
    expect(screen.getByText("重复收费退费凭证")).toBeInTheDocument();
    expect(screen.getByText("目录限制 HIS 字段截图")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "关闭门禁" })).toBeInTheDocument();
    expect(screen.getByText("补证材料完整")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "整改动态" })).toBeInTheDocument();
    expect(screen.getByText("附件归档校验阻断")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "查看报告来源" })).toHaveAttribute("href", "/reports");
    expect(screen.getAllByRole("link", { name: "查看详情" })[0]).toHaveAttribute("href", "/pages/review-tasks");
    await waitFor(() => {
      expect(fetchRemediationWorkbench).toHaveBeenCalledTimes(1);
    });
    expect(screen.getByText("后端已连接")).toBeInTheDocument();
  });

  it("keeps remediation samples when the remediation workbench API fails", async () => {
    vi.mocked(fetchRemediationWorkbench).mockRejectedValueOnce(new Error("remediation api down"));

    render(<RemediationPage />);

    await waitFor(() => {
      expect(screen.getByText("本地样例兜底")).toBeInTheDocument();
    });
    expect(screen.getByRole("heading", { name: "整改事项与补证闭环" })).toBeInTheDocument();
    expect(screen.getAllByText("重复收费退费与流程复核").length).toBeGreaterThan(0);
  });

  it("renders the archive homepage with packages, audit runs and signature chain", async () => {
    render(<ArchivePage />);

    expect(screen.getByRole("heading", { name: "项目档案与审计日志归档" })).toBeInTheDocument();
    expect(screen.getByText("已归档项目")).toBeInTheDocument();
    expect(screen.getByText("待归档档案")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "项目档案包" })).toBeInTheDocument();
    expect(screen.getAllByText("医保基金使用合规专项自查").length).toBeGreaterThan(0);
    expect(screen.getAllByText("ARCHIVE-SELF-CHECK-FUND-202606").length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: "审计日志治理策略" })).toBeInTheDocument();
    expect(screen.getByText("180 days")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "归档巡检" })).toBeInTheDocument();
    expect(screen.getByText("archive root 巡检")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "签名链" })).toBeInTheDocument();
    expect(screen.getByText("retention-batch-0001.jsonl")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "入档动态" })).toBeInTheDocument();
    expect(screen.getByText("附件 hash 阻断归档")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "打开审计日志台" })).toHaveAttribute("href", "/pages/audit-logs");
    expect(screen.getAllByRole("link", { name: "查看档案" })[0]).toHaveAttribute("href", "/reports");
    expect(screen.getAllByRole("link", { name: "查看日志" })[0]).toHaveAttribute(
      "href",
      "/pages/audit-logs?entity_type=review-task&entity_id=review-task-0001"
    );
    await waitFor(() => {
      expect(fetchArchiveWorkbench).toHaveBeenCalledTimes(1);
    });
    expect(screen.getByText("后端已连接")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("检索索引：就绪（postgres）")).toBeInTheDocument();
    });
  });

  it("keeps archive samples when the archive workbench API fails", async () => {
    vi.mocked(fetchArchiveWorkbench).mockRejectedValueOnce(new Error("archive api down"));

    render(<ArchivePage />);

    await waitFor(() => {
      expect(screen.getByText("本地样例兜底")).toBeInTheDocument();
    });
    expect(screen.getByRole("heading", { name: "项目档案与审计日志归档" })).toBeInTheDocument();
    expect(screen.getAllByText("ARCHIVE-SELF-CHECK-FUND-202606").length).toBeGreaterThan(0);
  });

  it("keeps archive samples when search backend probe fails", async () => {
    vi.mocked(fetchSearchBackendStatus).mockRejectedValueOnce(new Error("search service down"));

    render(<ArchivePage />);

    await waitFor(() => {
      expect(screen.getByText("检索索引：异常")).toBeInTheDocument();
    });
    expect(screen.getByRole("heading", { name: "项目档案与审计日志归档" })).toBeInTheDocument();
    expect(screen.getByText("ARCHIVE-SELF-CHECK-FUND-202606")).toBeInTheDocument();
  });

  it("renders the rules homepage with sources, runs and release gates", async () => {
    render(<RulesPage />);

    expect(screen.getByRole("heading", { name: "审计规则与依据总览" })).toBeInTheDocument();
    expect(screen.getByText("可运行规则")).toBeInTheDocument();
    expect(screen.getByText("待处理规则")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "规则清单" })).toBeInTheDocument();
    expect(screen.getAllByText("CHARGE-RULE-001").length).toBeGreaterThan(0);
    expect(screen.getAllByText("CATALOG-RULE-014").length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: "最近运行" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "来源覆盖" })).toBeInTheDocument();
    expect(screen.getAllByText("监管两库").length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: "发布门禁" })).toBeInTheDocument();
    expect(screen.getByText("字段可运行")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "打开索引管理" })).toHaveAttribute("href", "/pages/index-admin");
    expect(screen.getAllByRole("link", { name: "查看" })[0]).toHaveAttribute("href", "/findings?rule=CHARGE-RULE-001");
    expect(screen.getAllByRole("link", { name: "审证" })[0]).toHaveAttribute("href", expect.stringContaining("/chat?question="));
    await waitFor(() => {
      expect(fetchRulesWorkbench).toHaveBeenCalledTimes(1);
    });
    expect(screen.getByText("后端已连接")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("检索索引：就绪（postgres）")).toBeInTheDocument();
    });
  });

  it("keeps rule samples when the rules workbench API fails", async () => {
    vi.mocked(fetchRulesWorkbench).mockRejectedValueOnce(new Error("rules api down"));

    render(<RulesPage />);

    await waitFor(() => {
      expect(screen.getByText("本地样例兜底")).toBeInTheDocument();
    });
    expect(screen.getByRole("heading", { name: "审计规则与依据总览" })).toBeInTheDocument();
    expect(screen.getAllByText("CHARGE-RULE-001").length).toBeGreaterThan(0);
  });

  it("keeps rule samples when search backend probe fails", async () => {
    vi.mocked(fetchSearchBackendStatus).mockRejectedValueOnce(new Error("search service down"));

    render(<RulesPage />);

    await waitFor(() => {
      expect(screen.getByText("检索索引：异常")).toBeInTheDocument();
    });
    expect(screen.getByRole("heading", { name: "审计规则与依据总览" })).toBeInTheDocument();
    expect(screen.getAllByText("CHARGE-RULE-001").length).toBeGreaterThan(0);
  });
});
