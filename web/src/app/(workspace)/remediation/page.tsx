import { BackendFeatureBridge } from "@/components/shell/backend-feature-bridge";

export default function RemediationPage() {
  return (
    <BackendFeatureBridge
      title="补证整改"
      targetHref="/pages/review-tasks"
      targetLabel="复核任务/底稿"
      reason="当前已上线的补证状态、整改记录和关闭判断能力依附在复核任务详情流中。"
    />
  );
}
