"use client";

import type { FormEvent } from "react";

import { BrandLogo } from "@/components/shell/brand-logo";
import { writeAuditClientSession } from "@/lib/audit-user";
import { AUDIT_PLATFORM_DESCRIPTION, AUDIT_PLATFORM_NAME } from "@/lib/brand";

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

          <p id="support" className="audit-login-support">
            账号由医院信息中心统一开通，如需协助，请联系院内管理员。
          </p>
        </form>
      </section>
    </main>
  );
}
