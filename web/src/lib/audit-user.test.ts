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
