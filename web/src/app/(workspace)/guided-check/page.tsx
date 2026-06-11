import { BackendFeatureBridge } from "@/components/shell/backend-feature-bridge";

export default function GuidedCheckPage() {
  return (
    <BackendFeatureBridge
      title="AI 引导自查"
      targetHref="/pages/chat"
      targetLabel="对话审证"
      reason="当前已上线的自查问答、引用证据和复核任务创建能力集中在对话审证页。"
    />
  );
}
