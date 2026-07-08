import { ReplicaPreviewPage } from "@/components/replica/replica-preview-page";

export default function AnalyticsPage() {
  return (
    <ReplicaPreviewPage
      kicker="AI数据分析"
      title="AI数据分析"
      description="表格上传、数据清洗、图表分析和底稿沉淀仍在接入后端流程。"
      checkpoints={["上传文件解析", "分析任务记录", "图表结果复核", "底稿输出闭环"]}
    />
  );
}
