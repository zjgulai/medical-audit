import { BackendFeatureBridge } from "@/components/shell/backend-feature-bridge";

export default function GraphPage() {
  return (
    <BackendFeatureBridge
      title="知识图谱"
      targetHref="/workspace"
      targetLabel="今日工作台"
      reason="当前尚未上线独立图谱视图，项目状态与审计链动态先回到今日工作台查看。"
    />
  );
}
