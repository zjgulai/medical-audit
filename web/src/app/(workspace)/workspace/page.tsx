import { ProjectDashboard } from "@/components/dashboard/project-dashboard";
import { currentSelfCheckProject } from "@/lib/projects";

export default function WorkspacePage() {
  return <ProjectDashboard project={currentSelfCheckProject} />;
}
