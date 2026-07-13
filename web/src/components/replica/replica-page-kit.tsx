import type { ReactNode } from "react";

import type { ReplicaDataSource } from "@/lib/replica-adapters";

import type { ReplicaRuntimeStatus } from "./use-replica-runtime";

type ReplicaPageHeaderProps = {
  readonly kicker: string;
  readonly title: string;
  readonly description: string;
  readonly actions?: ReactNode;
};

type ReplicaMetricProps = {
  readonly label: string;
  readonly value: string;
  readonly tone?: "blue" | "green" | "amber" | "rose" | "slate";
};

type ReplicaRuntimeBadgeProps = {
  readonly source: ReplicaDataSource;
  readonly status: ReplicaRuntimeStatus;
  readonly hasSeedData?: boolean;
  readonly issueCount?: number;
};

type ReplicaFilterButtonProps<T extends string> = {
  readonly value: T;
  readonly activeValue: T;
  readonly onSelect: (value: T) => void;
  readonly children: ReactNode;
};

type ReplicaLocalGateNoticeOptions = {
  readonly action: string;
  readonly nextStep: string;
};

export function buildReplicaLocalGateNotice({ action }: ReplicaLocalGateNoticeOptions) {
  return `${action}已生成预览。请复核内容后再进入正式处理。`;
}

export function ReplicaPageHeader({ kicker, title, description, actions }: ReplicaPageHeaderProps) {
  return (
    <section className="replica-page-header">
      <div>
        <p className="replica-kicker">{kicker}</p>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {actions && <div className="replica-header-actions">{actions}</div>}
    </section>
  );
}

export function ReplicaMetric({ label, value, tone = "blue" }: ReplicaMetricProps) {
  return (
    <article className={`replica-metric tone-${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

export function ReplicaRuntimeBadge({
  source,
  status,
  hasSeedData = false,
  issueCount = 0
}: ReplicaRuntimeBadgeProps) {
  const label = runtimeBadgeLabel(source, status, hasSeedData);
  const sourceLabel = runtimeSourceLabel(source, hasSeedData);
  const statusLabel = runtimeStatusLabel(status);
  const detail = runtimeBadgeDetail(source, status, issueCount);

  return (
    <span
      className={`replica-runtime-badge source-${hasSeedData ? "seed" : source}`}
      aria-label={`数据来源：${sourceLabel}；状态：${statusLabel}`}
    >
      <strong>{label}</strong>
      <em>{detail}</em>
    </span>
  );
}

function runtimeBadgeLabel(source: ReplicaRuntimeBadgeProps["source"], status: ReplicaRuntimeBadgeProps["status"], hasSeedData: boolean) {
  if (status === "loading") {
    return "数据加载中";
  }
  if (status === "empty") {
    return "暂无数据";
  }
  if (status === "degraded") {
    return "数据受限";
  }
  if (status === "error") {
    return "读取失败";
  }
  return runtimeSourceLabel(source, hasSeedData);
}

function runtimeSourceLabel(source: ReplicaRuntimeBadgeProps["source"], hasSeedData: boolean) {
  if (hasSeedData) {
    return "后端种子数据";
  }
  if (source === "catalog") {
    return "产品目录";
  }
  if (source === "api") {
    return "后端数据";
  }
  if (source === "hybrid") {
    return "后端+本地";
  }
  return "本地样例";
}

function runtimeStatusLabel(status: ReplicaRuntimeBadgeProps["status"]) {
  if (status === "loading") {
    return "数据加载中";
  }
  if (status === "empty") {
    return "暂无数据";
  }
  if (status === "degraded") {
    return "数据受限";
  }
  if (status === "error") {
    return "读取失败";
  }
  return "已就绪";
}

function runtimeBadgeDetail(
  source: ReplicaRuntimeBadgeProps["source"],
  status: ReplicaRuntimeBadgeProps["status"],
  issueCount: number
) {
  if (status === "loading") {
    return "正在读取";
  }
  if (status === "empty") {
    return "当前无记录";
  }
  if (status === "degraded") {
    return issueCount > 0 ? `${issueCount} 项受限` : "部分能力受限";
  }
  if (status === "error") {
    return "请检查读取服务";
  }
  if (issueCount > 0) {
    return `${issueCount} 项待接入`;
  }
  if (source === "catalog") {
    return "目录已就绪";
  }
  return source === "fixture" ? "样例数据已启用" : "接口已校验";
}

export function ReplicaFilterButton<T extends string>({
  value,
  activeValue,
  onSelect,
  children
}: ReplicaFilterButtonProps<T>) {
  return (
    <button
      type="button"
      className={`replica-filter-button ${activeValue === value ? "is-active" : ""}`}
      onClick={() => onSelect(value)}
    >
      {children}
    </button>
  );
}

export function ReplicaNotice({ children }: { readonly children: ReactNode }) {
  return <div className="replica-notice">{children}</div>;
}

export function ReplicaEmptyState({ title, description }: { readonly title: string; readonly description: string }) {
  return (
    <div className="replica-empty">
      <span aria-hidden="true">∅</span>
      <strong>{title}</strong>
      <p>{description}</p>
    </div>
  );
}
