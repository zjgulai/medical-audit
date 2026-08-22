"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";

import {
  AuditClientRole,
  DEFAULT_AUDIT_ROLE,
  hasAuditClientPermission,
  readAuditClientRole,
  writeAuditClientRole
} from "@/lib/audit-user";
import { isPublicShellReadonly } from "@/lib/runtime-access";

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
  const publicShellReadonly = isPublicShellReadonly();
  const [role, setRoleState] = useState<AuditClientRole>("admin");

  useEffect(() => {
    if (publicShellReadonly) {
      return;
    }
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
  }, [publicShellReadonly]);

  const value = useMemo<AuditUserContextValue>(
    () => ({
      role,
      setRole: (nextRole) => {
        if (publicShellReadonly) return;
        writeAuditClientRole(nextRole);
        setRoleState(nextRole);
      },
      can: (permission) => !publicShellReadonly && hasAuditClientPermission(role, permission)
    }),
    [publicShellReadonly, role]
  );

  return <AuditUserContext.Provider value={value}>{children}</AuditUserContext.Provider>;
}

export function useAuditUser(): AuditUserContextValue {
  const value = useContext(AuditUserContext);
  if (value === null) {
    const publicShellReadonly = isPublicShellReadonly();
    return {
      role: DEFAULT_AUDIT_ROLE,
      setRole: (role) => {
        if (!publicShellReadonly) writeAuditClientRole(role);
      },
      can: (permission) => (
        !publicShellReadonly && hasAuditClientPermission(DEFAULT_AUDIT_ROLE, permission)
      )
    };
  }
  return value;
}
