export type NavigationEmphasis = "primary" | "standard";
export type NavigationTarget = "workspace" | "backend";

export type NavigationItem = {
  readonly id: string;
  readonly label: string;
  readonly href: string;
  readonly symbol: string;
  readonly description: string;
  readonly emphasis: NavigationEmphasis;
  readonly target: NavigationTarget;
};

export const primaryNavigation: readonly NavigationItem[] = [
  {
    id: "ai-chat",
    label: "AI 对话",
    href: "/chat",
    symbol: "AI",
    description: "选择提示词型智能体，生成带引用依据的审计回答。",
    emphasis: "primary",
    target: "workspace"
  },
  {
    id: "my-agents",
    label: "我的智能体",
    href: "/agents",
    symbol: "智",
    description: "管理个人常用审计提示词和场景助手。",
    emphasis: "standard",
    target: "workspace"
  },
  {
    id: "agent-market",
    label: "智能体广场",
    href: "/agent-market",
    symbol: "广",
    description: "查看医疗和医保审计场景模板。",
    emphasis: "standard",
    target: "workspace"
  },
  {
    id: "knowledge-base",
    label: "知识库",
    href: "/knowledge-base",
    symbol: "库",
    description: "查看个人、系统、公开知识库和索引状态。",
    emphasis: "standard",
    target: "workspace"
  },
  {
    id: "documents",
    label: "文档检索",
    href: "/documents",
    symbol: "检",
    description: "检索材料、知识库文档、引用片段和原文入口。",
    emphasis: "standard",
    target: "workspace"
  },
  {
    id: "analytics",
    label: "AI 数据分析",
    href: "/analytics",
    symbol: "数",
    description: "上传表格并查看审计数据分析线索。",
    emphasis: "standard",
    target: "workspace"
  },
  {
    id: "graph",
    label: "知识图谱",
    href: "/graph",
    symbol: "图",
    description: "查看项目、文档、规则、疑点和复核关系。",
    emphasis: "standard",
    target: "workspace"
  },
  {
    id: "reports",
    label: "审计底稿/报告",
    href: "/reports",
    symbol: "稿",
    description: "进入底稿生成、报告签发和整改导出。",
    emphasis: "standard",
    target: "workspace"
  },
  {
    id: "projects",
    label: "项目管理",
    href: "/projects",
    symbol: "项",
    description: "管理审计项目、成员、角色和项目空间。",
    emphasis: "standard",
    target: "workspace"
  }
];

export const secondaryNavigation: readonly NavigationItem[] = [
  {
    id: "guided-check",
    label: "AI 引导自查",
    href: "/guided-check",
    symbol: "查",
    description: "从自查问题进入 AI 审证对话。",
    emphasis: "standard",
    target: "workspace"
  },
  {
    id: "rules",
    label: "专题规则库",
    href: "/rules",
    symbol: "规",
    description: "查看规则来源、运行状态、疑点去向和发布门禁。",
    emphasis: "standard",
    target: "workspace"
  },
  {
    id: "remediation",
    label: "补证整改",
    href: "/remediation",
    symbol: "整",
    description: "跟踪补证、整改状态和关闭判断。",
    emphasis: "standard",
    target: "workspace"
  },
  {
    id: "archive",
    label: "项目档案",
    href: "/archive",
    symbol: "档",
    description: "查看审计日志、归档线索和导出记录。",
    emphasis: "standard",
    target: "workspace"
  }
];

const workspaceNavigation = [...primaryNavigation, ...secondaryNavigation] as const;

export function findNavigationItemById(id: string): NavigationItem | undefined {
  return workspaceNavigation.find((item) => item.id === id);
}

export function findNavigationItemForPath(pathname: string): NavigationItem | undefined {
  return workspaceNavigation.find((item) => pathname === item.href || pathname.startsWith(`${item.href}/`));
}
