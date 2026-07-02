import { StatusPill } from "@/components/ui/status-pill";

export type DataSource = "api" | "hybrid" | "static";

type DataSourceBadgeProps = {
  readonly source: DataSource;
};

const sourceConfig: Record<
  DataSource,
  { readonly tone: "success" | "info" | "warning"; readonly label: string }
> = {
  api: { tone: "success", label: "数据来源：实时" },
  hybrid: { tone: "info", label: "数据来源：部分实时·含示例" },
  static: { tone: "warning", label: "数据来源：演示样例" }
};

/**
 * 明确标注页面数据来源，避免把演示样例误判为已完成业务闭环。
 * - api: 全部来自后端实时数据
 * - hybrid: 部分实时 + 部分静态示例兜底
 * - static: 面向演示的静态样例
 */
export function DataSourceBadge({ source }: DataSourceBadgeProps) {
  const { tone, label } = sourceConfig[source];
  return <StatusPill tone={tone}>{label}</StatusPill>;
}
