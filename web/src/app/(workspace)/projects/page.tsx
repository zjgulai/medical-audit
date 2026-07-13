import { Suspense } from "react";

import { ReplicaProjectWorkbench } from "@/components/replica/replica-project-workbench";

export default function ProjectsPage() {
  return (
    <Suspense fallback={null}>
      <ReplicaProjectWorkbench />
    </Suspense>
  );
}
