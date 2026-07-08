import { ReplicaPreviewPage } from "@/components/replica/replica-preview-page";

export default function GraphPage() {
  return (
    <ReplicaPreviewPage
      kicker="知识图谱"
      title="知识图谱"
      description="知识库、规则、疑点、复核任务之间的关系视图仍在做只读关系建模。"
      checkpoints={["知识库节点", "规则与依据关系", "疑点关联", "复核闭环"]}
    />
  );
}
