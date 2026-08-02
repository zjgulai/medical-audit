import type { SourceCollection } from "@/lib/api-types";

export const AUDIT_PRODUCT_SOURCE_COLLECTIONS = [
  "management-judicial-audit-procedure",
  "medical-insurance-laws",
  "supervision-rules-knowledge",
  "medical-insurance-catalog",
  "risk-negative-list",
  "personal-materials"
] as const satisfies readonly SourceCollection[];

const auditProductSourceCollectionSet = new Set<SourceCollection>(
  AUDIT_PRODUCT_SOURCE_COLLECTIONS
);

export function isAuditProductSourceCollection(value: SourceCollection): boolean {
  return auditProductSourceCollectionSet.has(value);
}
