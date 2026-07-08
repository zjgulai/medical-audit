"use client";

import Image from "next/image";
import Link from "next/link";
import type { FormEvent } from "react";

import { BrandLogo } from "@/components/shell/brand-logo";
import { writeAuditClientSession } from "@/lib/audit-user";
import {
  AUDIT_ORGANIZATION_LOGO,
  AUDIT_ORGANIZATION_NAME,
  AUDIT_PLATFORM_DESCRIPTION,
  AUDIT_PLATFORM_NAME,
  AUDIT_PLATFORM_SUBTITLE,
  HAS_CONFIGURED_ORGANIZATION
} from "@/lib/brand";

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
    <main className="audit-login-shell audit-login-shell-compact">
      <section className="audit-login-center-stack" aria-label={`${AUDIT_PLATFORM_NAME}登录入口`}>
        <form className="audit-login-card audit-login-card-compact" action={fallbackAction} method="get" onSubmit={handleSubmit}>
          <div className="audit-login-card-brand">
            <span className="audit-login-compact-logo">
              <BrandLogo priority height={30} width={30} />
            </span>
            <div>
              <p>{AUDIT_PLATFORM_NAME}</p>
              <span>{AUDIT_PLATFORM_SUBTITLE}</span>
            </div>
          </div>

          <div className="audit-login-heading-block">
            <p className="audit-kicker">欢迎登录</p>
            <h1>登录工作台</h1>
            <p>{AUDIT_PLATFORM_DESCRIPTION}</p>
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
            登录
          </button>

          <div className="audit-login-role-strip" aria-label="角色入口说明">
            {roleEntries.map((role) => (
              <span key={role.label} title={role.description}>{role.label}</span>
            ))}
          </div>

          <div id="support" className="audit-login-org-panel">
            {AUDIT_ORGANIZATION_LOGO ? (
              <Image
                alt={`${AUDIT_ORGANIZATION_NAME} Logo`}
                height={28}
                src={AUDIT_ORGANIZATION_LOGO}
                unoptimized
                width={28}
              />
            ) : (
              <span aria-hidden="true" />
            )}
            <div>
              <p>{HAS_CONFIGURED_ORGANIZATION ? AUDIT_ORGANIZATION_NAME : "医院名称与 Logo 可在部署时配置"}</p>
              <small>账号由医院信息科统一开通，权限范围以管理员配置为准。</small>
            </div>
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
