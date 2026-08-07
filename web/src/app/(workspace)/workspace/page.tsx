"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { fetchAuditFindings, fetchRemediationWorkbench } from "@/lib/api-client";
import type { AuditFinding, AuditFindingsResponse, RemediationWorkbenchResponse } from "@/lib/api-types";
import { useAuditUser } from "@/components/shell/audit-user-context";

const QUICK_LINKS = [
  { href: "/medical-audit", label: "医保审计", desc: "查看疑点、复核和批量操作", tone: "blue" },
  { href: "/audit-cockpit", label: "审计驾驶舱", desc: "项目进度、风险分布和待办", tone: "slate" },
  { href: "/remediation", label: "补证整改", desc: "整改台账、补证请求和门禁", tone: "amber" },
  { href: "/reports", label: "审计底稿", desc: "生成报告草稿和签发流程", tone: "green" },
  { href: "/chat", label: "审计助手", desc: "知识库问答和规则查询", tone: "cyan" },
  { href: "/knowledge-base", label: "知识库", desc: "法规、规则和政策文件", tone: "rose" }
] as const;

const SEVERITY_LABEL: Record<string, string> = {
  high: "高风险",
  medium: "中风险",
  low: "低风险"
};

const SEVERITY_CLASS: Record<string, string> = {
  high: "audit-finding-severity--high",
  medium: "audit-finding-severity--medium",
  low: "audit-finding-severity--low"
};

type WorkspaceData = {
  readonly pendingReview: number;
  readonly blockedGates: number;
  readonly totalFindings: number;
  readonly activeRemediation: number;
  readonly pendingFindings: readonly AuditFinding[];
};

function findingDisplayTitle(finding: AuditFinding): string {
  const meta = finding.metadata as Record<string, unknown> | null;
  if (meta?.title && typeof meta.title === "string") return meta.title;
  if (meta?.display_name && typeof meta.display_name === "string") return meta.display_name;
  return finding.finding_type.replace(/_/g, " ");
}

export default function WorkspacePage() {
  const auditUser = useAuditUser();
  const [data, setData] = useState<WorkspaceData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      fetchAuditFindings("pending-review").catch((): AuditFindingsResponse | null => null),
      fetchAuditFindings().catch((): AuditFindingsResponse | null => null),
      fetchRemediationWorkbench().catch((): RemediationWorkbenchResponse | null => null)
    ]).then(([pendingFindings, allFindings, remediation]) => {
      if (cancelled) return;
      setData({
        pendingReview: allFindings?.stats.pending_review ?? 0,
        totalFindings: allFindings?.stats.total ?? 0,
        blockedGates: remediation?.metrics.blocked_gate_count ?? 0,
        activeRemediation: remediation?.metrics.active_case_count ?? 0,
        pendingFindings: pendingFindings?.items.slice(0, 5) ?? []
      });
      setLoading(false);
    });
    return () => { cancelled = true; };
  }, []);

  const roleLabel =
    auditUser.role === "admin" ? "管理员"
    : auditUser.role === "director" ? "主任"
    : "审计员";

  return (
    <main className="workspace-home-page">
      <header className="workspace-home-hero">
        <div>
          <p className="workspace-home-kicker">工作台</p>
          <h1>你好</h1>
          <p className="workspace-home-subtitle">当前角色：{roleLabel} · 今日审计工作台概览</p>
        </div>
      </header>

      <section className="workspace-home-stats" aria-label="今日关键指标">
        <article>
          <span>待复核疑点</span>
          <strong>{loading ? "—" : data?.pendingReview ?? 0}</strong>
          <Link href="/medical-audit">前往处理</Link>
        </article>
        <article>
          <span>生产疑点总数</span>
          <strong>{loading ? "—" : data?.totalFindings ?? 0}</strong>
          <Link href="/medical-audit">查看全部</Link>
        </article>
        <article>
          <span>整改阻断门禁</span>
          <strong className={!loading && (data?.blockedGates ?? 0) > 0 ? "is-alert" : ""}>
            {loading ? "—" : data?.blockedGates ?? 0}
          </strong>
          <Link href="/remediation">查看整改</Link>
        </article>
        <article>
          <span>进行中整改</span>
          <strong>{loading ? "—" : data?.activeRemediation ?? 0}</strong>
          <Link href="/remediation">跟踪进度</Link>
        </article>
      </section>

      {!loading ? (
        <section className="workspace-pending-review" aria-label="今日待复核">
          <div className="workspace-pending-review-head">
            <h2>待复核疑点</h2>
            <Link href="/medical-audit">查看全部</Link>
          </div>
          {data && data.pendingFindings.length > 0 ? (
            <div className="workspace-pending-list">
              {data.pendingFindings.map((finding) => (
                <article key={finding.finding_key} className="workspace-pending-item">
                  <span className={`audit-finding-severity ${SEVERITY_CLASS[finding.severity] ?? ""}`}>
                    {SEVERITY_LABEL[finding.severity] ?? finding.severity}
                  </span>
                  <div className="workspace-pending-info">
                    <strong>{findingDisplayTitle(finding)}</strong>
                    <small>{finding.finding_key}</small>
                  </div>
                  <Link
                    className="workspace-pending-action"
                    href={`/medical-audit?finding=${encodeURIComponent(finding.finding_key)}`}
                  >
                    进入复核 →
                  </Link>
                </article>
              ))}
            </div>
          ) : (
            <p className="workspace-pending-empty">暂无待复核疑点，审计进度良好 ✓</p>
          )}
        </section>
      ) : null}

      <section className="workspace-home-links" aria-label="常用功能入口">
        <h2>常用功能</h2>
        <div className="workspace-home-grid">
          {QUICK_LINKS.map((link) => (
            <Link
              key={link.href}
              className={`workspace-home-card tone-${link.tone}`}
              href={link.href}
            >
              <strong>{link.label}</strong>
              <p>{link.desc}</p>
            </Link>
          ))}
        </div>
      </section>
    </main>
  );
}
