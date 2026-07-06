"use client";

import Link from "next/link";
import type { FormEvent } from "react";

import { BrandLogo } from "@/components/shell/brand-logo";
import { writeAuditClientSession } from "@/lib/audit-user";

const roleEntries = [
  { label: "管理员", description: "账号、权限、日志" },
  { label: "技术人员", description: "数据、索引、模板" },
  { label: "主任", description: "复核、签发、闭环" },
  { label: "普通成员", description: "审证、分析、底稿" }
] as const;

type LoginSurfaceProps = {
  readonly redirectTo?: string;
};

function safeRedirectPath(value: string | null | undefined): string | null {
  if (!value || !value.startsWith("/") || value.startsWith("//")) {
    return null;
  }
  return value;
}

function resolveRedirectPath(redirectTo: string | undefined): string {
  const explicitRedirect = safeRedirectPath(redirectTo);
  if (explicitRedirect) {
    return explicitRedirect;
  }
  if (typeof window === "undefined") {
    return "/workspace";
  }
  return safeRedirectPath(new URLSearchParams(window.location.search).get("redirect")) ?? "/workspace";
}

export function LoginSurface({ redirectTo }: LoginSurfaceProps) {
  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    writeAuditClientSession();
    window.location.assign(resolveRedirectPath(redirectTo));
  }

  const fallbackAction = safeRedirectPath(redirectTo) ?? "/workspace";

  return (
    <main className="audit-login-shell flex items-center justify-center px-4 py-8 sm:px-6">
      <section className="grid w-full max-w-6xl gap-6 lg:grid-cols-[1fr_26rem]">
        <div className="audit-login-hero flex min-h-[34rem] flex-col justify-between p-6 lg:p-8" aria-label="医疗AI审计平台入口介绍">
          <div className="audit-login-hero-content">
            <div className="audit-login-hero-brand">
              <span className="audit-login-hero-logo">
                <BrandLogo priority />
              </span>
              <span>
                <span className="block text-sm font-semibold">医疗AI审计平台</span>
                <span className="block text-xs">医保基金合规审计</span>
              </span>
            </div>

            <div className="mt-14 max-w-2xl">
              <p className="audit-login-hero-kicker">医保基金审计专题</p>
              <h1 className="mt-3 text-4xl font-semibold leading-tight tracking-[0] sm:text-5xl">
                面向医院内审的医保审计工作台
              </h1>
              <p className="audit-login-hero-copy mt-5 max-w-xl text-base leading-7">
                围绕依据检索、审计助手、表格分析和底稿生成组织日常工作，系统建议保持人工复核边界。
              </p>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-4">
            {roleEntries.map((role) => (
              <div key={role.label} className="audit-login-role-card p-3">
                <p className="text-sm font-semibold">{role.label}</p>
                <p className="mt-1 text-xs leading-5">{role.description}</p>
              </div>
            ))}
          </div>
        </div>

        <form className="audit-login-card p-6 sm:p-7" action={fallbackAction} method="get" onSubmit={handleSubmit}>
          <div>
            <p className="audit-kicker">医院统一入口</p>
            <h2 className="mt-2 text-2xl font-semibold leading-8 text-[var(--audit-ink)]">登录工作台</h2>
            <p className="mt-2 audit-copy">使用信息科分配的账号进入对应角色视图。</p>
          </div>

          <div className="mt-7 space-y-5">
            <label className="block">
              <span className="audit-label">账号 / 工号</span>
              <input
                className="audit-focus-ring audit-input mt-2 px-3 py-3"
                name="account"
                autoComplete="username"
                placeholder="请输入账号或工号"
                required
              />
            </label>

            <label className="block">
              <span className="audit-label">密码</span>
              <input
                className="audit-focus-ring audit-input mt-2 px-3 py-3"
                name="password"
                type="password"
                autoComplete="current-password"
                placeholder="请输入密码"
                required
              />
            </label>

            <div className="flex flex-wrap items-center justify-between gap-3">
              <label className="flex items-center gap-2 text-sm text-[var(--audit-ink-muted)]">
                <input className="size-4 rounded border-[var(--audit-line)]" type="checkbox" name="remember" />
                保持本机登录
              </label>
              <a className="audit-focus-ring rounded-[var(--audit-radius-sm)] px-2 py-1 text-sm font-semibold text-[var(--audit-primary)]" href="#support">
                联系信息中心
              </a>
            </div>
          </div>

          <button className="audit-focus-ring audit-btn audit-btn-primary mt-7 w-full" type="submit">
            进入系统
          </button>

          <div id="support" className="mt-6 rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-[var(--audit-surface-muted)] p-4">
            <p className="text-sm font-semibold text-[var(--audit-ink)]">访问边界</p>
            <p className="mt-1 audit-meta">
              账号由医院信息科统一开通；权限范围以管理员配置为准。
            </p>
          </div>

          <div className="mt-5 text-center">
            <Link className="audit-focus-ring rounded-[var(--audit-radius-sm)] px-2 py-1 text-sm font-semibold text-[var(--audit-ink-muted)]" href="/workspace">
              查看当前工作台
            </Link>
          </div>
        </form>
      </section>
    </main>
  );
}
