import { BackendFeatureBridge } from "@/components/shell/backend-feature-bridge";

export default function ArchivePage() {
  return (
    <BackendFeatureBridge
      title="项目档案"
      targetHref="/pages/audit-logs"
      targetLabel="审计日志"
      reason="当前已上线的可追溯档案线索集中在审计日志页，覆盖查询、导出、复核和索引操作。"
    />
  );
}
