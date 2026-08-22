"use client";

import { useEffect, useState } from "react";

import { LoginSurface } from "@/components/login/login-surface";
import { isAuditClientAuthenticated } from "@/lib/audit-user";
import { isPublicShellReadonly } from "@/lib/runtime-access";

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
  const publicShellReadonly = isPublicShellReadonly();
  const [state, setState] = useState<AuthGateState>({
    authenticated: publicShellReadonly,
    redirectTo: "/workspace"
  });

  useEffect(() => {
    if (publicShellReadonly) {
      setState({ authenticated: true, redirectTo: currentWorkspacePath() });
      return;
    }
    setState({
      authenticated: isAuditClientAuthenticated(),
      redirectTo: currentWorkspacePath()
    });
  }, [publicShellReadonly]);

  if (!state.authenticated) {
    return <LoginSurface redirectTo={state.redirectTo} />;
  }

  return (
    <>
      {publicShellReadonly ? (
        <div className="audit-runtime-access-banner" role="status">
          生产只读导览：可信登录尚未启用，业务数据读取和写入均已关闭。
        </div>
      ) : null}
      {children}
    </>
  );
}
