"use client";

import { useEffect, useState } from "react";

import { LoginSurface } from "@/components/login/login-surface";
import { isAuditClientAuthenticated } from "@/lib/audit-user";

type WorkspaceAuthGateProps = {
  readonly children: React.ReactNode;
};

type AuthGateState = {
  readonly authenticated: boolean;
  readonly redirectTo: string;
};

function currentWorkspacePath(): string {
  if (typeof window === "undefined") {
    return "/workspace";
  }
  return `${window.location.pathname}${window.location.search}${window.location.hash}`;
}

export function WorkspaceAuthGate({ children }: WorkspaceAuthGateProps) {
  const [state, setState] = useState<AuthGateState>({
    authenticated: false,
    redirectTo: "/workspace"
  });

  useEffect(() => {
    setState({
      authenticated: isAuditClientAuthenticated(),
      redirectTo: currentWorkspacePath()
    });
  }, []);

  if (!state.authenticated) {
    return <LoginSurface redirectTo={state.redirectTo} />;
  }

  return <>{children}</>;
}
