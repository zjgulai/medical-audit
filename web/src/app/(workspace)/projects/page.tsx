import { ReplicaPreviewPage } from "@/components/replica/replica-preview-page";

export default function ProjectsPage() {
  return (
    <ReplicaPreviewPage
      kicker="项目管理"
      title="项目管理"
      description="审计专题、成员分工、状态看板和任务流转还在与后端项目模型对齐。"
      checkpoints={["审计专题列表", "成员权限", "任务状态", "驾驶舱统计"]}
    />
  );
}
