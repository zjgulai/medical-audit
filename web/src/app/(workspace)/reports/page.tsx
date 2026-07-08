import { ReplicaPreviewPage } from "@/components/replica/replica-preview-page";

export default function ReportsPage() {
  return (
    <ReplicaPreviewPage
      kicker="审计底稿/报告"
      title="审计底稿/报告"
      description="底稿草稿、报告目录、签发和导出链路仍在与审计证据闭环对齐。"
      checkpoints={["底稿模板", "证据引用", "主任复核", "报告导出"]}
    />
  );
}
