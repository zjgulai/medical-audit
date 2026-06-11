import { BackendFeatureBridge } from "@/components/shell/backend-feature-bridge";

export default function RulesPage() {
  return (
    <BackendFeatureBridge
      title="专题规则库"
      targetHref="/pages/index-admin"
      targetLabel="索引管理"
      reason="当前规则与资料状态通过知识库索引、失败文件、待处理文件和评测记录进行运维核验。"
    />
  );
}
