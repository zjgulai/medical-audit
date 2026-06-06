import { AppSidebar } from "./app-sidebar";
import { ProjectContextBar } from "./project-context-bar";

type WorkspaceShellProps = {
  readonly children: React.ReactNode;
};

export function WorkspaceShell({ children }: WorkspaceShellProps) {
  return (
    <div className="min-h-screen bg-[var(--audit-bg)]">
      <div className="flex min-h-screen">
        <AppSidebar />
        <div className="min-w-0 flex-1">
          <ProjectContextBar />
          <div className="px-8 py-8">{children}</div>
        </div>
      </div>
    </div>
  );
}
