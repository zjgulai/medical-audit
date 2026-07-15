import { describe, expect, it } from "vitest";

import { hasAuditClientPermission } from "./audit-user";

describe("report draft client permissions", () => {
  it.each(["admin", "director", "member"] as const)(
    "allows %s to create a controlled report draft",
    (role) => {
      expect(hasAuditClientPermission(role, "create_report_draft")).toBe(true);
    }
  );

  it("keeps report draft creation unavailable to technicians", () => {
    expect(hasAuditClientPermission("technician", "create_report_draft")).toBe(false);
  });
});

describe("PPT closure client permissions", () => {
  it("allows review-task creation for audit roles but not technicians", () => {
    expect(hasAuditClientPermission("admin", "create_review_task")).toBe(true);
    expect(hasAuditClientPermission("director", "create_review_task")).toBe(true);
    expect(hasAuditClientPermission("member", "create_review_task")).toBe(true);
    expect(hasAuditClientPermission("technician", "create_review_task")).toBe(false);
  });

  it("allows project creation only for administrators", () => {
    expect(hasAuditClientPermission("admin", "create_project")).toBe(true);
    expect(hasAuditClientPermission("director", "create_project")).toBe(false);
    expect(hasAuditClientPermission("member", "create_project")).toBe(false);
    expect(hasAuditClientPermission("technician", "create_project")).toBe(false);
  });
});
