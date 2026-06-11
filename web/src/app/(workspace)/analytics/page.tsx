import { BackendFeatureBridge } from "@/components/shell/backend-feature-bridge";

export default function AnalyticsPage() {
  return (
    <BackendFeatureBridge
      title="AI 数据分析"
      targetHref="/pages/index-admin"
      targetLabel="索引管理"
      reason="当前已上线的数据状态、检索后端、评测历史和索引健康指标集中在索引管理页。"
    />
  );
}
