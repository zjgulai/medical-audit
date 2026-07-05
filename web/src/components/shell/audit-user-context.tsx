"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";

import {
  AuditClientRole,
  DEFAULT_AUDIT_ROLE,
  hasAuditClientPermission,
  readAuditClientRole,
  writeAuditClientRole
} from "@/lib/audit-user";

type AuditUserContextValue = {
  readonly role: AuditClientRole;
  readonly setRole: (role: AuditClientRole) => void;
  readonly can: (permission: Parameters<typeof hasAuditClientPermission>[1]) => boolean;
};

const AuditUserContext = createContext<AuditUserContextValue | null>(null);

type AuditUserProviderProps = {
  readonly children: React.ReactNode;
};

export function AuditUserProvider({ children }: AuditUserProviderProps) {
  const [role, setRoleState] = useState<AuditClientRole>("admin");

  useEffect(() => {
    setRoleState(readAuditClientRole());

    function handleStorage() {
      setRoleState(readAuditClientRole());
    }

    function handleRoleChange(event: Event) {
      const detail = (event as CustomEvent<{ role?: AuditClientRole }>).detail;
      if (detail?.role) {
        setRoleState(detail.role);
      }
    }

    window.addEventListener("storage", handleStorage);
    window.addEventListener("medical-audit-role-change", handleRoleChange);
    return () => {
      window.removeEventListener("storage", handleStorage);
      window.removeEventListener("medical-audit-role-change", handleRoleChange);
    };
  }, []);

  const value = useMemo<AuditUserContextValue>(
    () => ({
      role,
      setRole: (nextRole) => {
        writeAuditClientRole(nextRole);
        setRoleState(nextRole);
      },
      can: (permission) => hasAuditClientPermission(role, permission)
    }),
    [role]
  );

  return <AuditUserContext.Provider value={value}>{children}</AuditUserContext.Provider>;
}

export function useAuditUser(): AuditUserContextValue {
  const value = useContext(AuditUserContext);
  if (value === null) {
    return {
      role: DEFAULT_AUDIT_ROLE,
      setRole: writeAuditClientRole,
      can: (permission) => hasAuditClientPermission(DEFAULT_AUDIT_ROLE, permission)
    };
  }
  return value;
}
