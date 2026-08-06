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

export type NavigationGroup = {
  readonly id: string;
  readonly label: string;
  readonly items: readonly NavigationItem[];
};

export const workspaceHomeNavigation: NavigationItem = {
  id: "workspace",
  label: "工作台",
  href: "/workspace",
  symbol: "工作",
  description: "查看当前项目、待办事项、风险线索和工作进展。",
  emphasis: "standard",
  target: "workspace"
};

export const fundComplianceNavigation: NavigationItem = {
  id: "fund-compliance",
  label: "医保审计专题",
  href: "/medical-audit",
  symbol: "医保",
  description: "打开医保审计专题工作台，查看规则、表单和待复核单据。",
  emphasis: "primary",
  target: "workspace"
};

export const primaryNavigation: readonly NavigationItem[] = [
  {
    id: "ai-chat",
    label: "审计助手",
    href: "/chat",
    symbol: "对话",
    description: "选择审计助手，生成带引用依据的审计回答。",
    emphasis: "primary",
    target: "workspace"
  },
  {
    id: "my-agents",
    label: "我的智能体",
    href: "/agents",
    symbol: "智能",
    description: "管理个人常用审计提示词和场景助手。",
    emphasis: "standard",
    target: "workspace"
  },
  {
    id: "agent-market",
    label: "智能体广场",
    href: "/agent-market",
    symbol: "广场",
    description: "查看医疗和医保审计场景模板。",
    emphasis: "standard",
    target: "workspace"
  },
  {
    id: "knowledge-base",
    label: "知识库",
    href: "/knowledge-base",
    symbol: "知识",
    description: "查看个人、系统、公开知识库和索引状态。",
    emphasis: "standard",
    target: "workspace"
  },
  {
    id: "documents",
    label: "文档检索",
    href: "/documents",
    symbol: "文档",
    description: "检索材料、知识库文档、引用片段和原文入口。",
    emphasis: "standard",
    target: "workspace"
  },
  {
    id: "text-ocr",
    label: "文本 OCR",
    href: "/ocr",
    symbol: "识别",
    description: "识别扫描 PDF 和图片，核验逐页文本与证据哈希。",
    emphasis: "standard",
    target: "workspace"
  },
  {
    id: "analytics",
    label: "AI数据分析",
    href: "/analytics",
    symbol: "分析",
    description: "上传表格并查看审计数据分析线索。",
    emphasis: "standard",
    target: "workspace"
  },
  {
    id: "graph",
    label: "知识图谱",
    href: "/graph",
    symbol: "图谱",
    description: "查看项目、文档、规则、疑点和复核关系。",
    emphasis: "standard",
    target: "workspace"
  },
  {
    id: "reports",
    label: "审计底稿/报告",
    href: "/reports",
    symbol: "报告",
    description: "按提示词模板生成底稿草稿，并衔接报告签发和整改导出。",
    emphasis: "standard",
    target: "workspace"
  },
  {
    id: "projects",
    label: "项目管理",
    href: "/projects",
    symbol: "项目",
    description: "管理审计项目、成员、角色和任务流转。",
    emphasis: "standard",
    target: "workspace"
  },
  {
    id: "audit-cockpit",
    label: "审计驾驶舱",
    href: "/audit-cockpit",
    symbol: "驾驶",
    description: "查看项目进度、风险分布、待办事项和证据准备情况。",
    emphasis: "primary",
    target: "workspace"
  }
];

export const secondaryNavigation: readonly NavigationItem[] = [
  {
    id: "guided-check",
    label: "引导自查",
    href: "/guided-check",
    symbol: "自查",
    description: "从自查问题进入 AI 审证对话。",
    emphasis: "standard",
    target: "workspace"
  },
  {
    id: "rules",
    label: "规则库",
    href: "/rules",
    symbol: "规则",
    description: "查看规则来源、运行状态、疑点去向和发布门禁。",
    emphasis: "standard",
    target: "workspace"
  },
  {
    id: "remediation",
    label: "补证整改",
    href: "/remediation",
    symbol: "整改",
    description: "跟踪补证、整改状态和关闭判断。",
    emphasis: "standard",
    target: "workspace"
  },
  {
    id: "archive",
    label: "项目归档",
    href: "/archive",
    symbol: "归档",
    description: "查看审计日志、归档线索和导出记录。",
    emphasis: "standard",
    target: "workspace"
  }
];

export const systemNavigation: readonly NavigationItem[] = [
  {
    id: "index-admin",
    label: "索引管理",
    href: "/pages/index-admin",
    symbol: "索引",
    description: "进入后端索引发布、回滚、重载和验收控制台。",
    emphasis: "standard",
    target: "backend"
  },
  {
    id: "audit-logs",
    label: "审计日志",
    href: "/pages/audit-logs",
    symbol: "日志",
    description: "查看查询、导出、复核和索引操作留痕。",
    emphasis: "standard",
    target: "backend"
  }
];

const workspaceNavigation = [
  workspaceHomeNavigation,
  fundComplianceNavigation,
  ...primaryNavigation,
  ...secondaryNavigation,
  ...systemNavigation
] as const;

function requireNavigationItemById(id: string): NavigationItem {
  const item = workspaceNavigation.find((navigationItem) => navigationItem.id === id);
  if (!item) {
    throw new Error(`Missing navigation item: ${id}`);
  }
  return item;
}

export const visiblePrimaryNavigation: readonly NavigationItem[] = [
  requireNavigationItemById("audit-cockpit"),
  requireNavigationItemById("fund-compliance"),
  requireNavigationItemById("ai-chat"),
  requireNavigationItemById("remediation"),
  requireNavigationItemById("reports"),
  requireNavigationItemById("documents"),
  requireNavigationItemById("text-ocr"),
  requireNavigationItemById("archive")
];

export const sidebarUtilityNavigation: readonly NavigationItem[] = [
  requireNavigationItemById("agent-market"),
  requireNavigationItemById("my-agents"),
  requireNavigationItemById("knowledge-base"),
  requireNavigationItemById("analytics"),
  requireNavigationItemById("projects"),
  requireNavigationItemById("rules"),
  requireNavigationItemById("guided-check"),
  requireNavigationItemById("graph"),
  requireNavigationItemById("workspace")
];

export const navigationGroups: readonly NavigationGroup[] = [
  {
    id: "primary",
    label: "常用入口",
    items: visiblePrimaryNavigation
  },
  {
    id: "audit-tools",
    label: "审计工具",
    items: [
      requireNavigationItemById("agent-market"),
      requireNavigationItemById("my-agents"),
      requireNavigationItemById("analytics"),
      requireNavigationItemById("projects"),
      requireNavigationItemById("guided-check")
    ]
  },
  {
    id: "evidence",
    label: "依据与规则",
    items: [
      requireNavigationItemById("knowledge-base"),
      requireNavigationItemById("graph"),
      requireNavigationItemById("rules")
    ]
  },
  {
    id: "system",
    label: "系统管理",
    items: systemNavigation
  }
];

export function findNavigationItemById(id: string): NavigationItem | undefined {
  return workspaceNavigation.find((item) => item.id === id);
}

export function findNavigationItemForPath(pathname: string): NavigationItem | undefined {
  return workspaceNavigation.find((item) => pathname === item.href || pathname.startsWith(`${item.href}/`));
}
