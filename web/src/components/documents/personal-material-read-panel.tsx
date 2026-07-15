"use client";

import { useEffect, useRef, useState } from "react";

import { useAuditUser } from "@/components/shell/audit-user-context";
import { fetchDocumentPermissions, fetchDocumentUploads } from "@/lib/api-client";
import type {
  DocumentPermissionsResponse,
  DocumentUploadItem,
  DocumentUploadListResponse,
  DocumentUploadPermissions
} from "@/lib/api-types";

import { PersonalMaterialActions } from "./personal-material-actions";

type PersonalMaterialReadState =
  | { readonly status: "loading" }
  | {
      readonly status: "ready" | "empty";
      readonly generation: number;
      readonly loadedRole: string;
      readonly permissions: DocumentPermissionsResponse;
      readonly uploads: DocumentUploadListResponse;
    }
  | { readonly status: "degraded"; readonly reason: string }
  | { readonly status: "error" };

export function PersonalMaterialReadPanel() {
  const auditUser = useAuditUser();
  const [state, setState] = useState<PersonalMaterialReadState>({ status: "loading" });
  const mountedRef = useRef(false);
  const currentRoleRef = useRef(auditUser.role);
  const loadGenerationRef = useRef(0);
  currentRoleRef.current = auditUser.role;

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      loadGenerationRef.current += 1;
    };
  }, []);

  useEffect(() => {
    const loadedRole = auditUser.role;
    const generation = loadGenerationRef.current + 1;
    loadGenerationRef.current = generation;
    setState({ status: "loading" });

    Promise.all([fetchDocumentPermissions(), fetchDocumentUploads()])
      .then(([permissions, uploads]) => {
        if (!isCurrentIdentityLoad(
          mountedRef,
          currentRoleRef,
          loadGenerationRef,
          loadedRole,
          generation
        )) {
          return;
        }
        const invalidReason = documentUploadsInvalidReason(permissions, uploads);
        if (invalidReason) {
          setState({ status: "degraded", reason: invalidReason });
          return;
        }
        setState({
          status: uploads.items.length > 0 ? "ready" : "empty",
          generation,
          loadedRole,
          permissions,
          uploads
        });
      })
      .catch(() => {
        if (isCurrentIdentityLoad(
          mountedRef,
          currentRoleRef,
          loadGenerationRef,
          loadedRole,
          generation
        )) {
          setState({ status: "error" });
        }
      });
  }, [auditUser.role]);

  const staleRole = (state.status === "ready" || state.status === "empty")
    && state.loadedRole !== auditUser.role;
  const displayStatus = staleRole ? "loading" : state.status;

  return (
    <section className="replica-panel" aria-labelledby="personal-material-title" data-status={displayStatus}>
      <div className="replica-results-head">
        <div>
          <p className="replica-kicker">个人材料权限与状态</p>
          <h2 id="personal-material-title">个人材料</h2>
        </div>
        <span>写入仅由显式操作触发</span>
      </div>

      {displayStatus === "loading" ? (
        <p role="status">个人材料加载中</p>
      ) : null}

      {displayStatus === "error" ? (
        <p role="alert">个人材料读取失败</p>
      ) : null}

      {displayStatus === "degraded" && state.status === "degraded" ? (
        <div role="status">
          <strong>个人材料状态受限</strong>
          <p>{state.reason}</p>
        </div>
      ) : null}

      {!staleRole && (state.status === "ready" || state.status === "empty") ? (
        <>
          <div aria-label="个人材料角色能力">
            <p>当前角色：{state.permissions.role}</p>
            <ul>
              <li>上传个人材料：{permissionLabel(state.permissions.upload_permissions.can_upload_personal)}</li>
              <li>查看全部个人材料：{permissionLabel(state.permissions.upload_permissions.can_read_all_personal_uploads)}</li>
              <li>治理个人材料：{permissionLabel(state.permissions.upload_permissions.can_govern_personal_uploads)}</li>
            </ul>
          </div>

          {state.status === "empty" ? (
            <p role="status">当前身份暂无可见个人材料</p>
          ) : (
            <div aria-label="可见个人材料历史">
              {state.uploads.items.map((item) => (
                <PersonalMaterialHistoryItem key={item.id} item={item} />
              ))}
            </div>
          )}

          <PersonalMaterialActions
            permissions={state.permissions.upload_permissions}
            uploads={state.uploads.items}
            onChanged={async () => {
              assertCurrentIdentityLoad(
                mountedRef,
                currentRoleRef,
                loadGenerationRef,
                state.loadedRole,
                state.generation
              );
              const uploads = await fetchDocumentUploads();
              assertCurrentIdentityLoad(
                mountedRef,
                currentRoleRef,
                loadGenerationRef,
                state.loadedRole,
                state.generation
              );
              const invalidReason = documentUploadsInvalidReason(state.permissions, uploads);
              if (invalidReason) {
                throw new Error(invalidReason);
              }
              setState({
                status: uploads.items.length > 0 ? "ready" : "empty",
                generation: state.generation,
                loadedRole: state.loadedRole,
                permissions: state.permissions,
                uploads
              });
            }}
          />
        </>
      ) : null}
    </section>
  );
}

function isCurrentIdentityLoad(
  mountedRef: React.RefObject<boolean>,
  currentRoleRef: React.RefObject<string>,
  generationRef: React.RefObject<number>,
  loadedRole: string,
  generation: number
): boolean {
  return mountedRef.current
    && currentRoleRef.current === loadedRole
    && generationRef.current === generation;
}

function assertCurrentIdentityLoad(
  mountedRef: React.RefObject<boolean>,
  currentRoleRef: React.RefObject<string>,
  generationRef: React.RefObject<number>,
  loadedRole: string,
  generation: number
): void {
  if (!isCurrentIdentityLoad(
    mountedRef,
    currentRoleRef,
    generationRef,
    loadedRole,
    generation
  )) {
    throw new Error("个人材料身份已变化，已忽略旧列表刷新");
  }
}

function documentUploadsInvalidReason(
  permissions: DocumentPermissionsResponse,
  uploads: DocumentUploadListResponse
): string | null {
  if (!uploads.store.ready) {
    return "个人材料存储当前未就绪，已停止展示上传明细。";
  }
  if (!sameUploadPermissions(permissions.upload_permissions, uploads.permissions)) {
    return "个人材料权限响应不一致，已停止展示上传明细。";
  }
  if (!Array.isArray(uploads.items)) {
    return "个人材料响应格式无效，已停止展示上传明细。";
  }
  return null;
}

function PersonalMaterialHistoryItem({ item }: { readonly item: DocumentUploadItem }) {
  return (
    <article className="replica-result-card">
      <h3>{item.name}</h3>
      <time>{item.created_at}</time>
      <dl>
        <div>
          <dt className="sr-only">治理状态</dt>
          <dd>治理状态：{item.governance_status}</dd>
        </div>
        <div>
          <dt className="sr-only">安全扫描</dt>
          <dd>安全扫描：{item.security_scan_status}</dd>
        </div>
        <div>
          <dt className="sr-only">DLP</dt>
          <dd>DLP：{item.dlp_status}</dd>
        </div>
        <div>
          <dt className="sr-only">索引状态</dt>
          <dd>索引状态：{item.index_status}</dd>
        </div>
        <div>
          <dt className="sr-only">个人索引</dt>
          <dd>个人索引：{item.personal_index_status} / {item.personal_index_chunk_count} chunks</dd>
        </div>
      </dl>
    </article>
  );
}

function sameUploadPermissions(left: unknown, right: unknown): boolean {
  if (!isDocumentUploadPermissions(left) || !isDocumentUploadPermissions(right)) {
    return false;
  }
  return left.can_upload_personal === right.can_upload_personal
    && left.can_read_all_personal_uploads === right.can_read_all_personal_uploads
    && left.can_govern_personal_uploads === right.can_govern_personal_uploads;
}

function isDocumentUploadPermissions(value: unknown): value is DocumentUploadPermissions {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return false;
  }
  const candidate = value as Record<string, unknown>;
  return typeof candidate.can_upload_personal === "boolean"
    && typeof candidate.can_read_all_personal_uploads === "boolean"
    && typeof candidate.can_govern_personal_uploads === "boolean";
}

function permissionLabel(allowed: boolean): string {
  return allowed ? "允许" : "不允许";
}
