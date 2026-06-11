export type NavigationEmphasis = "primary" | "standard";
export type NavigationTarget = "workspace" | "backend";

export type NavigationItem = {
  readonly id: string;
  readonly label: string;
  readonly href: string;
  readonly description: string;
  readonly emphasis: NavigationEmphasis;
  readonly target: NavigationTarget;
};

export const primaryNavigation: readonly NavigationItem[] = [
  {
    id: "workspace",
    label: "今日工作台",
    href: "/workspace",
    description: "查看项目状态、待办疑点、补证任务和索引健康。",
    emphasis: "standard",
    target: "workspace"
  },
  {
    id: "chat",
    label: "对话审证",
    href: "/pages/chat",
    description: "围绕审核问题生成引用型回答，并进入人工复核。",
    emphasis: "primary",
    target: "backend"
  },
  {
    id: "query",
    label: "查询工作台",
    href: "/knowledge-query",
    description: "检索政策、规则、风险清单和引用原文。",
    emphasis: "standard",
    target: "workspace"
  },
  {
    id: "findings",
    label: "疑点清单",
    href: "/findings",
    description: "查看疑点状态、证据强度和复核入口。",
    emphasis: "standard",
    target: "workspace"
  },
  {
    id: "review-tasks",
    label: "复核任务/底稿",
    href: "/pages/review-tasks",
    description: "维护复核任务、附件、报告草稿、签发与整改跟踪。",
    emphasis: "standard",
    target: "backend"
  },
  {
    id: "audit-logs",
    label: "审计日志",
    href: "/pages/audit-logs",
    description: "追踪查询、导出、复核和索引操作记录。",
    emphasis: "standard",
    target: "backend"
  },
  {
    id: "index-admin",
    label: "索引管理",
    href: "/pages/index-admin",
    description: "查看索引版本、后端状态、失败文件和评测记录。",
    emphasis: "standard",
    target: "backend"
  }
];
