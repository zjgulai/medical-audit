export type ProjectStatus = "active" | "paused" | "closed";
export type ProjectStage = "intake" | "retrieve" | "analyze" | "clarify" | "finding" | "remediation" | "report";
export type ProjectTone = "neutral" | "info" | "warning" | "danger" | "success";
export type QueueItemStatus = "open" | "blocked" | "closed";

export type ProjectMetric = {
  readonly key: "open_findings" | "missing_evidence" | "rule_cards" | "backend_status";
  readonly label: string;
  readonly value: string;
  readonly helper: string;
  readonly tone: ProjectTone;
};

export type ProjectQueueItem = {
  readonly id: string;
  readonly title: string;
  readonly owner: string;
  readonly dueLabel: string;
  readonly status: QueueItemStatus;
  readonly risk: "high" | "medium" | "low";
};

export type ProjectActivity = {
  readonly id: string;
  readonly title: string;
  readonly description: string;
  readonly timeLabel: string;
};

export type SelfCheckProject = {
  readonly id: string;
  readonly name: string;
  readonly organizationName: string;
  readonly auditTopic: string;
  readonly status: ProjectStatus;
  readonly stage: ProjectStage;
  readonly dateRange: string;
  readonly evidencePolicy: string;
  readonly metrics: readonly ProjectMetric[];
  readonly queue: readonly ProjectQueueItem[];
  readonly activities: readonly ProjectActivity[];
};

export const projectStageLabels: Record<ProjectStage, string> = {
  intake: "收集条件",
  retrieve: "检索证据",
  analyze: "形成判断",
  clarify: "缺证追问",
  finding: "生成疑点",
  remediation: "补证整改",
  report: "汇总输出"
};

const projectStageOrder: readonly ProjectStage[] = [
  "intake",
  "retrieve",
  "analyze",
  "clarify",
  "finding",
  "remediation",
  "report"
];

export const currentSelfCheckProject: SelfCheckProject = {
  id: "SELF-CHECK-FUND-20260607",
  name: "医保基金使用合规专项自查",
  organizationName: "单院医保内审试运行",
  auditTopic: "医保基金使用合规",
  status: "active",
  stage: "analyze",
  dateRange: "2026-01 至 2026-03",
  evidencePolicy: "仅展示资料内明确国家/地区政策，不做外推结论。",
  metrics: [
    {
      key: "open_findings",
      label: "待处理疑点",
      value: "12",
      helper: "均需人工确认后进入底稿",
      tone: "danger"
    },
    {
      key: "missing_evidence",
      label: "待补证据",
      value: "5",
      helper: "缺结算明细或目录限制字段",
      tone: "warning"
    },
    {
      key: "rule_cards",
      label: "专题规则卡",
      value: "18",
      helper: "Markdown / JSON 双形态",
      tone: "info"
    },
    {
      key: "backend_status",
      label: "索引联通",
      value: "待检测",
      helper: "由前端只读健康检查刷新",
      tone: "neutral"
    }
  ],
  queue: [
    {
      id: "QUEUE-001",
      title: "核对非目录项目发生基金支付的结算明细",
      owner: "审计员",
      dueLabel: "今日",
      status: "open",
      risk: "high"
    },
    {
      id: "QUEUE-002",
      title: "补充身份骗保相关就诊和参保身份字段",
      owner: "信息科",
      dueLabel: "2 天内",
      status: "blocked",
      risk: "medium"
    },
    {
      id: "QUEUE-003",
      title: "复核限定科室规则卡跨专题归类",
      owner: "业务专家",
      dueLabel: "本周",
      status: "open",
      risk: "medium"
    },
    {
      id: "QUEUE-004",
      title: "归档已确认规则卡评审记录",
      owner: "系统",
      dueLabel: "已完成",
      status: "closed",
      risk: "low"
    }
  ],
  activities: [
    {
      id: "ACT-001",
      title: "规则卡映射已激活",
      description: "医保基金使用合规专题已进入独立逻辑专题入口。",
      timeLabel: "今天 09:20"
    },
    {
      id: "ACT-002",
      title: "候选疑点等待人工确认",
      description: "高风险疑点仍保持 AI 草稿，不进入正式底稿。",
      timeLabel: "今天 08:45"
    },
    {
      id: "ACT-003",
      title: "索引健康等待前端联通检测",
      description: "Plan 02 只做只读健康展示，不执行索引变更。",
      timeLabel: "昨天 18:10"
    }
  ]
};

export function getProjectStageProgress(project: SelfCheckProject) {
  const currentIndex = projectStageOrder.indexOf(project.stage) + 1;

  return {
    currentIndex,
    total: projectStageOrder.length,
    percent: Math.round((currentIndex / projectStageOrder.length) * 100)
  };
}

export function getOpenProjectQueueItems(project: SelfCheckProject): readonly ProjectQueueItem[] {
  return project.queue.filter((item) => item.status !== "closed");
}

export function getProjectMetricByKey(project: SelfCheckProject, key: ProjectMetric["key"]): ProjectMetric | undefined {
  return project.metrics.find((metric) => metric.key === key);
}
