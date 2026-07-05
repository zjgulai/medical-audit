import { ReplicaShell } from "@/components/replica/replica-shell";

export default function WorkspaceLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return <ReplicaShell>{children}</ReplicaShell>;
}
