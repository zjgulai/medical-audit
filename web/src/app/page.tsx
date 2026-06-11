import { ProjectDashboard } from "@/components/dashboard/project-dashboard";
import { WorkspaceShell } from "@/components/shell/workspace-shell";
import { currentSelfCheckProject } from "@/lib/projects";

export default function HomePage() {
  return (
    <WorkspaceShell>
      <ProjectDashboard project={currentSelfCheckProject} />
    </WorkspaceShell>
  );
}
