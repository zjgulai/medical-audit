import Image from "next/image";
import Link from "next/link";

const roleEntries = [
  { label: "管理员", description: "账号、权限、日志" },
  { label: "技术人员", description: "数据、索引、模板" },
  { label: "主任", description: "复核、签发、闭环" },
  { label: "普通成员", description: "审证、分析、底稿" }
] as const;

export default function LoginPage() {
  return (
    <main className="audit-login-shell flex items-center justify-center px-4 py-8 sm:px-6">
      <section className="grid w-full max-w-6xl gap-6 lg:grid-cols-[1fr_26rem]">
        <div className="flex min-h-[34rem] flex-col justify-between rounded-[14px] border border-white/20 bg-white/10 p-6 text-white shadow-[0_24px_70px_rgb(10_31_68/0.18)] backdrop-blur lg:p-8">
          <div>
            <div className="inline-flex items-center gap-3 rounded-[var(--audit-radius-lg)] border border-white/20 bg-white/12 px-3 py-2">
              <span className="grid size-10 place-items-center rounded-[var(--audit-radius-md)] bg-white">
                <Image src="/brand/auditscope-logo.png" alt="" width={28} height={28} priority />
              </span>
              <span>
                <span className="block text-sm font-semibold">AI智能审计管理系统</span>
                <span className="block text-xs text-white/72">AuditScope Medical</span>
              </span>
            </div>

            <div className="mt-14 max-w-2xl">
              <p className="text-sm font-semibold text-sky-100">医保基金审计专题</p>
              <h1 className="mt-3 text-4xl font-semibold leading-tight tracking-[0] sm:text-5xl">
                面向医院内审的 AI 审证工作台
              </h1>
              <p className="mt-5 max-w-xl text-base leading-7 text-sky-50/84">
                围绕知识库问答、智能体模板、文档检索、表格分析和审计底稿生成组织日常审计工作，AI 输出保持人工复核边界。
              </p>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-4">
            {roleEntries.map((role) => (
              <div key={role.label} className="rounded-[var(--audit-radius-md)] border border-white/18 bg-white/10 p-3">
                <p className="text-sm font-semibold">{role.label}</p>
                <p className="mt-1 text-xs leading-5 text-sky-50/76">{role.description}</p>
              </div>
            ))}
          </div>
        </div>

        <form className="audit-login-card p-6 sm:p-7" action="/workspace" method="get">
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
