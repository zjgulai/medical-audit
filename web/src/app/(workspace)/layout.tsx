import { ReplicaShell } from "@/components/replica/replica-shell";
import { AuditUserProvider } from "@/components/shell/audit-user-context";
import { WorkspaceAuthGate } from "@/components/shell/workspace-auth-gate";

export default function WorkspaceLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <WorkspaceAuthGate>
      <AuditUserProvider>
        <ReplicaShell>{children}</ReplicaShell>
      </AuditUserProvider>
    </WorkspaceAuthGate>
  );
}
