"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { navigationGroups, type NavigationItem } from "@/lib/navigation";

function isActivePath(pathname: string, href: string) {
  return pathname === href || pathname.startsWith(`${href}/`);
}

const recentConversations = [
  {
    title: "门诊超量开药依据核验",
    href: "/pages/chat?question=%E9%97%A8%E8%AF%8A%E8%B6%85%E9%87%8F%E5%BC%80%E8%8D%AF%E5%BA%94%E6%A0%B8%E5%AF%B9%E5%93%AA%E4%BA%9B%E5%8C%BB%E4%BF%9D%E5%AE%A1%E6%A0%B8%E4%BE%9D%E6%8D%AE"
  },
  {
    title: "重复收费疑点复核",
    href: "/pages/chat?question=%E9%87%8D%E5%A4%8D%E6%94%B6%E8%B4%B9%E7%96%91%E7%82%B9%E5%BA%94%E5%A6%82%E4%BD%95%E6%A0%B8%E9%AA%8C%E8%AF%81%E6%8D%AE"
  },
  {
    title: "目录限制交叉审核",
    href: "/pages/chat?question=%E8%AF%8A%E7%96%97%E9%A1%B9%E7%9B%AE%E6%94%B6%E8%B4%B9%E4%B8%8E%E7%9B%AE%E5%BD%95%E9%99%90%E5%88%B6%E5%A6%82%E4%BD%95%E4%BA%A4%E5%8F%89%E5%AE%A1%E6%A0%B8"
  }
] as const;

function NavigationLink({ item, pathname }: { readonly item: NavigationItem; readonly pathname: string }) {
  const isActive = isActivePath(pathname, item.href);
  const className = `audit-focus-ring audit-sidebar-link flex min-w-36 items-center gap-2 rounded-[var(--audit-radius-md)] px-2.5 py-2 text-sm transition md:min-w-0 ${
    isActive
      ? "bg-[var(--audit-primary)] text-white shadow-[0_8px_18px_rgb(29_117_201/0.18)]"
      : "text-[var(--audit-ink-muted)] hover:bg-white hover:text-[var(--audit-ink)]"
  }`;
  const content = (
    <>
      <span
        aria-hidden="true"
        className={`grid size-7 shrink-0 place-items-center rounded-[var(--audit-radius-sm)] text-[11px] font-semibold ${
          isActive ? "bg-white/18 text-white" : "bg-[var(--audit-surface-subtle)] text-[var(--audit-primary)]"
        }`}
      >
        {item.symbol}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate font-medium">{item.label}</span>
      </span>
      {item.target === "backend" && (
        <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-semibold ${isActive ? "bg-white/20 text-white" : "bg-white text-[var(--audit-ink-subtle)]"}`}>
          深页
        </span>
      )}
    </>
  );

  if (item.target === "backend") {
    return (
      <a
        href={item.href}
        title={item.description}
        aria-current={isActive ? "page" : undefined}
        className={className}
      >
        {content}
      </a>
    );
  }

  return (
    <Link
      href={item.href}
      title={item.description}
      aria-current={isActive ? "page" : undefined}
      className={className}
    >
      {content}
    </Link>
  );
}

export function AppSidebar() {
  const pathname = usePathname();

  return (
    <aside className="audit-sidebar-shell flex w-full flex-col border-b border-[var(--audit-line)] px-4 py-4 shadow-[0_10px_24px_rgb(23_62_105/0.05)] sm:px-5 md:min-h-screen md:w-[18rem] md:border-r md:border-b-0 md:py-5 md:shadow-[8px_0_24px_rgb(23_62_105/0.05)] xl:w-[19rem]">
      <Link href="/workspace" className="audit-focus-ring rounded-[var(--audit-radius-lg)]" aria-label="打开门户首页">
        <div className="flex items-center gap-3">
          <div className="grid size-11 shrink-0 place-items-center rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-white shadow-[0_8px_18px_rgb(35_45_84/0.08)]">
            <Image
              src="/brand/auditscope-logo.png"
              alt=""
              width={30}
              height={30}
              priority
            />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-[var(--audit-ink)]">AI智能审计管理系统</p>
            <p className="audit-meta">医保基金审计专题</p>
          </div>
        </div>
      </Link>

      <div className="mt-4 rounded-[var(--audit-radius-lg)] border border-[var(--audit-primary-line)] bg-white/78 p-3">
        <p className="text-xs font-semibold text-[var(--audit-primary)]">当前专题</p>
        <p className="mt-1 text-sm font-semibold text-[var(--audit-ink)]">医保基金使用合规</p>
        <p className="mt-1 audit-meta">费用汇总、分类汇总、就诊明细模板已纳入数据分析入口。</p>
      </div>

      <nav className="mt-4 flex gap-3 overflow-x-auto pb-1 md:flex-col md:gap-3 md:overflow-x-visible md:pb-0" aria-label="主导航">
        {navigationGroups.map((group) => (
          <section key={group.id} className="flex min-w-56 flex-col gap-1 md:min-w-0">
            <h2 className="px-2 text-[11px] font-semibold leading-5 text-[var(--audit-ink-subtle)]">{group.label}</h2>
            {group.items.map((item) => (
              <NavigationLink key={item.id} item={item} pathname={pathname} />
            ))}
          </section>
        ))}
      </nav>

      <div className="mt-5 border-t border-[var(--audit-line)] pt-4">
        <div className="flex items-center justify-between gap-3">
          <p className="audit-meta font-semibold">常用审证入口</p>
          <a className="audit-focus-ring rounded-[var(--audit-radius-sm)] px-2 py-1 text-xs font-semibold text-[var(--audit-primary)] hover:bg-[var(--audit-primary-soft)]" href="/chat">
            新建
          </a>
        </div>
        <div className="mt-2 space-y-1">
          {recentConversations.map((conversation) => (
            <a
              key={conversation.title}
              className="audit-focus-ring block truncate rounded-[var(--audit-radius-sm)] px-2 py-2 text-xs text-[var(--audit-ink-muted)] hover:bg-[var(--audit-surface-muted)] hover:text-[var(--audit-ink)]"
              href={conversation.href}
            >
              {conversation.title}
            </a>
          ))}
        </div>
      </div>
    </aside>
  );
}
