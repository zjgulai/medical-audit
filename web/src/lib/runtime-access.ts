export const MEDICAL_AUDIT_ACCESS_MODES = [
  "header-transition-test",
  "public-shell-readonly"
] as const;

export type MedicalAuditAccessMode = (typeof MEDICAL_AUDIT_ACCESS_MODES)[number];

export function medicalAuditAccessMode(): MedicalAuditAccessMode {
  const configured = process.env.NEXT_PUBLIC_MEDICAL_AUDIT_API_ACCESS_MODE?.trim();
  if (configured === "header-transition-test" || configured === "public-shell-readonly") {
    return configured;
  }
  return process.env.NODE_ENV === "production"
    ? "public-shell-readonly"
    : "header-transition-test";
}

export function isPublicShellReadonly(): boolean {
  return medicalAuditAccessMode() === "public-shell-readonly";
}

export function assertProtectedApiAvailable(): void {
  if (isPublicShellReadonly()) {
    throw new Error("生产业务数据访问已关闭，等待可信身份认证启用。");
  }
}
