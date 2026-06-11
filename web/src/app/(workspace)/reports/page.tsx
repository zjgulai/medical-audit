import { BackendFeatureBridge } from "@/components/shell/backend-feature-bridge";

export default function ReportsPage() {
  return (
    <BackendFeatureBridge
      title="底稿/报告"
      targetHref="/pages/review-tasks"
      targetLabel="复核任务/底稿"
      reason="当前已上线的底稿导出、报告草稿、签发报告和整改导出能力集中在复核任务台。"
    />
  );
}
