import { WorkspaceShell } from "@/components/shell/workspace-shell";
import { WorkspaceAuthGate } from "@/components/shell/workspace-auth-gate";

export default function WorkspaceLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <WorkspaceAuthGate>
      <WorkspaceShell>{children}</WorkspaceShell>
    </WorkspaceAuthGate>
  );
}
