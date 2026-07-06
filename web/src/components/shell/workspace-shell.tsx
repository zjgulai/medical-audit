"use client";

import { useState } from "react";

import { AuditUserProvider } from "./audit-user-context";
import { AppSidebar } from "./app-sidebar";
import { ProjectContextBar } from "./project-context-bar";
import { AiChatFab } from "./ai-chat-fab";

type WorkspaceShellProps = {
  readonly children: React.ReactNode;
};

export function WorkspaceShell({ children }: WorkspaceShellProps) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  return (
    <AuditUserProvider>
      <div className="audit-shell-grid min-h-screen bg-[var(--audit-bg)]">
        <div className="flex min-h-screen flex-col md:flex-row">
          <AppSidebar collapsed={sidebarCollapsed} />
          <div className="min-w-0 flex-1">
            <ProjectContextBar
              sidebarCollapsed={sidebarCollapsed}
              onToggleSidebar={() => setSidebarCollapsed((value) => !value)}
            />
            <div className="px-4 py-5 sm:px-6 md:px-8 md:py-6">{children}</div>
          </div>
        </div>
        <AiChatFab />
      </div>
    </AuditUserProvider>
  );
}
