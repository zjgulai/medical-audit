import { BackendFeatureBridge } from "@/components/shell/backend-feature-bridge";

export default function FindingsPage() {
  return (
    <BackendFeatureBridge
      title="疑点清单"
      targetHref="/pages/audit-findings"
      targetLabel="疑点清单"
      reason="当前已上线的疑点状态、证据强度、复核状态和任务创建能力集中在后端疑点页。"
    />
  );
}
