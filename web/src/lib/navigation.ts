export type NavigationEmphasis = "primary" | "standard";

export type NavigationItem = {
  readonly label: string;
  readonly href: string;
  readonly description: string;
  readonly emphasis: NavigationEmphasis;
};

export const primaryNavigation: readonly NavigationItem[] = [
  {
    label: "今日工作台",
    href: "/workspace",
    description: "查看项目状态、待办疑点、补证任务和索引健康。",
    emphasis: "standard"
  },
  {
    label: "AI 引导自查",
    href: "/guided-check",
    description: "通过自查向导、多轮对话和证据侧栏完成政策问答与材料自查。",
    emphasis: "primary"
  },
  {
    label: "专题规则库",
    href: "/rules",
    description: "查看医保基金使用合规、身份骗保等专题规则卡。",
    emphasis: "standard"
  },
  {
    label: "材料与文档检索",
    href: "/documents",
    description: "检索源文档、上传材料、定位引用原文。",
    emphasis: "standard"
  },
  {
    label: "疑点清单",
    href: "/findings",
    description: "管理风险等级、证据强度、待补条件和人工确认状态。",
    emphasis: "standard"
  },
  {
    label: "补证整改",
    href: "/remediation",
    description: "跟踪补证任务、整改建议、处理记录和关闭原因。",
    emphasis: "standard"
  },
  {
    label: "底稿/报告",
    href: "/reports",
    description: "生成自查底稿、整改记录和专题报告。",
    emphasis: "standard"
  },
  {
    label: "AI 数据分析",
    href: "/analytics",
    description: "查看风险分布、规则命中热区和整改进度。",
    emphasis: "standard"
  },
  {
    label: "知识图谱",
    href: "/graph",
    description: "展示项目内人员、材料、规则、疑点和整改关系。",
    emphasis: "standard"
  },
  {
    label: "项目档案",
    href: "/archive",
    description: "归档项目画像、会话、材料、疑点、报告和操作日志。",
    emphasis: "standard"
  }
];
