"use client";

import { useState, type FormEvent } from "react";

import { BrandLogo } from "@/components/shell/brand-logo";
import { writeAuditClientSession } from "@/lib/audit-user";

type LoginSecurityStep = "closed" | "notice" | "password";

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
  const [showPassword, setShowPassword] = useState(false);
  const [securityStep, setSecurityStep] = useState<LoginSecurityStep>("closed");
  const [passwordChangeStatus, setPasswordChangeStatus] = useState("");
  const fallbackAction = resolveRedirectPath(redirectTo);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    writeAuditClientSession();
    setPasswordChangeStatus("");
    setSecurityStep("notice");
  }

  function enterWorkspace() {
    writeAuditClientSession();
    window.location.assign(resolveRedirectPath(redirectTo));
  }

  return (
    <main className="audit-login-shell">
      <div className="audit-login-glow audit-login-glow-top" aria-hidden="true" />
      <div className="audit-login-glow audit-login-glow-bottom" aria-hidden="true" />

      <form className="audit-login-card" action={fallbackAction} method="get" aria-label="登录系统" onSubmit={handleSubmit}>
        <div className="audit-login-brand">
          <span className="audit-login-mark" aria-hidden="true">
            <BrandLogo height={20} priority width={20} />
          </span>
          <span className="audit-login-brand-name">医保智能审计平台</span>
        </div>

        <div className="audit-login-heading">
          <h1>欢迎登录</h1>
          <p>请使用您的账号密码进入系统</p>
        </div>

        <div className="audit-login-fields">
          <div className="audit-login-field">
            <label htmlFor="login-account">账号 / 工号</label>
            <input
              id="login-account"
              autoComplete="username"
              placeholder="请输入账号或工号"
              required
              type="text"
            />
          </div>

          <div className="audit-login-field">
            <label htmlFor="login-password">密码</label>
            <span className="audit-login-password-wrap">
              <input
                id="login-password"
                autoComplete="current-password"
                placeholder="请输入密码"
                required
                type={showPassword ? "text" : "password"}
              />
              <button
                className="audit-login-visibility"
                type="button"
                aria-label={showPassword ? "隐藏密码" : "显示密码"}
                aria-pressed={showPassword}
                onClick={() => setShowPassword((current) => !current)}
              >
                {showPassword ? "◐" : "◎"}
              </button>
            </span>
          </div>
        </div>

        <button className="audit-login-submit" type="submit">
          登 录
        </button>

        <p className="audit-login-support">
          忘记密码或账号？请联系
          <a href="#support">信息中心</a>
        </p>
      </form>

      {securityStep !== "closed" && (
        <div className="audit-login-dialog-layer">
          <section
            className="audit-login-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="audit-login-security-title"
          >
            {securityStep === "notice" ? (
              <>
                <div className="audit-login-dialog-header">
                  <span aria-hidden="true">!</span>
                  <div>
                    <h2 id="audit-login-security-title">初始密码安全提示</h2>
                    <p>检测到当前账号仍可能使用初始密码。建议先修改密码，再进入审计工作台。</p>
                  </div>
                </div>

                <div className="audit-login-dialog-actions">
                  <button type="button" className="audit-login-dialog-secondary" onClick={enterWorkspace}>
                    稍后处理
                  </button>
                  <button type="button" className="audit-login-dialog-primary" onClick={() => setSecurityStep("password")}>
                    修改密码
                  </button>
                </div>
              </>
            ) : (
              <>
                <div className="audit-login-dialog-header">
                  <span aria-hidden="true">锁</span>
                  <div>
                    <h2 id="audit-login-security-title">修改密码</h2>
                    <p>请输入新密码并再次确认。正式保存前请确保密码符合机构安全要求。</p>
                  </div>
                </div>

                <div className="audit-login-dialog-fields">
                  <label htmlFor="login-new-password">新密码</label>
                  <input id="login-new-password" type="password" autoComplete="new-password" placeholder="请输入新密码" />
                  <label htmlFor="login-confirm-password">确认密码</label>
                  <input
                    id="login-confirm-password"
                    type="password"
                    autoComplete="new-password"
                    placeholder="请再次输入新密码"
                  />
                </div>

                {passwordChangeStatus && (
                  <p className="audit-login-dialog-status" role="status">
                    {passwordChangeStatus}
                  </p>
                )}

                <div className="audit-login-dialog-actions">
                  <button type="button" className="audit-login-dialog-secondary" onClick={() => setSecurityStep("notice")}>
                    返回提示
                  </button>
                  <button
                    type="button"
                    className="audit-login-dialog-secondary"
                    onClick={() => setPasswordChangeStatus("密码修改已生成预览。请确认后进入正式保存流程。")}
                  >
                    提交修改
                  </button>
                  <button type="button" className="audit-login-dialog-primary" onClick={enterWorkspace}>
                    进入系统
                  </button>
                </div>
              </>
            )}
          </section>
        </div>
      )}

      <p id="support" className="audit-login-footer">
        医保智能审计平台 · 基金合规审计
      </p>
    </main>
  );
}
