import { ReplicaShell } from "@/components/replica/replica-shell";
import { WorkspaceAuthGate } from "@/components/shell/workspace-auth-gate";

export default function WorkspaceLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <WorkspaceAuthGate>
      <ReplicaShell>{children}</ReplicaShell>
    </WorkspaceAuthGate>
  );
}
