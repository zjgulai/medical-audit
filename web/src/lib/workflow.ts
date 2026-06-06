export type SelfCheckWorkflowStage =
  | "intake"
  | "retrieve"
  | "analyze"
  | "clarify"
  | "finding"
  | "remediation"
  | "report";

export type WorkflowStageMeta = {
  readonly stage: SelfCheckWorkflowStage;
  readonly label: string;
  readonly description: string;
};

export const workflowStages: readonly WorkflowStageMeta[] = [
  {
    stage: "intake",
    label: "收集条件",
    description: "确认地区、机构类型、时间范围、材料类型和基金支付事实。"
  },
  {
    stage: "retrieve",
    label: "检索证据",
    description: "按专题规则卡筛选并排序证据。"
  },
  {
    stage: "analyze",
    label: "形成判断",
    description: "基于引用和规则卡输出政策解释或风险提示。"
  },
  {
    stage: "clarify",
    label: "缺证追问",
    description: "当证据不足时，要求用户补充材料或事实。"
  },
  {
    stage: "finding",
    label: "生成疑点",
    description: "把高风险结果转为待人工确认疑点。"
  },
  {
    stage: "remediation",
    label: "补证整改",
    description: "生成补证任务、整改建议和处理记录。"
  },
  {
    stage: "report",
    label: "汇总输出",
    description: "生成自查底稿、整改记录和专题报告。"
  }
];
