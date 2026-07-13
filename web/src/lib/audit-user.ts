export type AuditClientRole = "admin" | "technician" | "director" | "member";

export type AuditClientPermission =
  | "create_report_draft"
  | "manage_agents"
  | "manage_project_members"
  | "manage_index"
  | "read_audit_logs"
  | "sign_reports";

export type AuditRoleOption = {
  readonly id: AuditClientRole;
  readonly label: string;
  readonly detail: string;
  readonly userId: string;
};

export const AUDIT_ROLE_STORAGE_KEY = "medical-audit-current-role";
export const AUDIT_AUTH_STORAGE_KEY = "medical-audit-authenticated";
export const DEFAULT_AUDIT_ROLE: AuditClientRole = "admin";
export const DEFAULT_AUDIT_TENANT_ID = "hospital-demo";
export const DEFAULT_AUDIT_PROJECT_KEY = "SELF-CHECK-FUND-20260607";
export const DEFAULT_AUDIT_PROJECT_NAME = "医保基金使用合规专项自查";

export const auditRoleOptions: readonly AuditRoleOption[] = [
  { id: "admin", label: "管理员", detail: "账号与权限", userId: "next-admin" },
  { id: "technician", label: "技术人员", detail: "数据与索引", userId: "next-technician" },
  { id: "director", label: "主任", detail: "复核与签发", userId: "next-director" },
  { id: "member", label: "普通成员", detail: "审证与底稿", userId: "next-member" }
] as const;

const rolePermissions: Record<AuditClientRole, readonly AuditClientPermission[]> = {
  admin: [
    "create_report_draft",
    "manage_agents",
    "manage_project_members",
    "manage_index",
    "read_audit_logs"
  ],
  technician: ["manage_agents", "manage_index"],
  director: ["create_report_draft", "manage_agents", "read_audit_logs", "sign_reports"],
  member: ["create_report_draft"]
};

export function normalizeAuditClientRole(value: string | null | undefined): AuditClientRole {
  if (value === "admin" || value === "technician" || value === "director" || value === "member") {
    return value;
  }
  return DEFAULT_AUDIT_ROLE;
}

export function readAuditClientRole(): AuditClientRole {
  if (typeof window === "undefined") {
    return DEFAULT_AUDIT_ROLE;
  }

  try {
    return normalizeAuditClientRole(window.localStorage.getItem(AUDIT_ROLE_STORAGE_KEY));
  } catch {
    return DEFAULT_AUDIT_ROLE;
  }
}

export function writeAuditClientRole(role: AuditClientRole): void {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(AUDIT_ROLE_STORAGE_KEY, role);
  window.dispatchEvent(new CustomEvent("medical-audit-role-change", { detail: { role } }));
}

export function isAuditClientAuthenticated(): boolean {
  if (typeof window === "undefined") {
    return false;
  }

  try {
    return window.localStorage.getItem(AUDIT_AUTH_STORAGE_KEY) === "authenticated";
  } catch {
    return false;
  }
}

export function writeAuditClientSession(role: AuditClientRole = DEFAULT_AUDIT_ROLE): void {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(AUDIT_AUTH_STORAGE_KEY, "authenticated");
  writeAuditClientRole(role);
}

export function clearAuditClientSession(): void {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.removeItem(AUDIT_AUTH_STORAGE_KEY);
}

export function auditClientUserId(role: AuditClientRole): string {
  return auditRoleOptions.find((item) => item.id === role)?.userId ?? "next-admin";
}

export function auditClientRoleLabel(role: AuditClientRole): string {
  return auditRoleOptions.find((item) => item.id === role)?.label ?? "管理员";
}

export function auditClientRoleDetail(role: AuditClientRole): string {
  return auditRoleOptions.find((item) => item.id === role)?.detail ?? "账号与权限";
}

export function hasAuditClientPermission(role: AuditClientRole, permission: AuditClientPermission): boolean {
  return rolePermissions[role].includes(permission);
}

export function auditClientHeaders(): Record<string, string> {
  const role = readAuditClientRole();
  return {
    "X-Role": role,
    "X-User-Id": auditClientUserId(role),
    "X-Tenant-Id": DEFAULT_AUDIT_TENANT_ID
  };
}

export function auditAgentClientHeaders(): Record<string, string> {
  return {
    ...auditClientHeaders(),
    "X-Project-Name": encodeURIComponent(DEFAULT_AUDIT_PROJECT_NAME)
  };
}

export function auditProjectClientHeaders(projectKey = DEFAULT_AUDIT_PROJECT_KEY): Record<string, string> {
  return {
    ...auditClientHeaders(),
    "X-Project-Key": projectKey
  };
}
