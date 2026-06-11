import { BackendFeatureBridge } from "@/components/shell/backend-feature-bridge";

export default function DocumentsPage() {
  return (
    <BackendFeatureBridge
      title="材料与文档检索"
      targetHref="/pages/query"
      targetLabel="查询工作台"
      reason="当前已上线的材料检索、来源过滤、引用定位和原文预览能力集中在查询工作台。"
    />
  );
}
