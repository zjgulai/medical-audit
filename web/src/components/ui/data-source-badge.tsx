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
  static: { tone: "warning", label: "数据来源：示例·未接后端" }
};

/**
 * 明确标注页面数据来源，避免把"静态示例壳"误判为"已完成业务闭环"。
 * - api: 全部来自后端实时数据
 * - hybrid: 部分实时 + 部分静态示例兜底
 * - static: 纯静态示例，尚未接入后端
 */
export function DataSourceBadge({ source }: DataSourceBadgeProps) {
  const { tone, label } = sourceConfig[source];
  return <StatusPill tone={tone}>{label}</StatusPill>;
}
