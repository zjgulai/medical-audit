"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { primaryNavigation } from "@/lib/navigation";

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

export function AppSidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex w-full flex-col border-b border-slate-200 bg-white px-4 py-4 shadow-[0_12px_32px_rgb(16_24_40/0.04)] sm:px-5 md:min-h-screen md:w-60 md:border-r md:border-b-0 md:py-5 md:shadow-[10px_0_32px_rgb(16_24_40/0.04)] lg:w-64">
      <Link href="/workspace" className="audit-focus-ring rounded-xl" aria-label="打开门户首页">
        <div className="flex items-center gap-3">
          <div className="grid size-10 shrink-0 place-items-center rounded-xl bg-blue-600 text-sm font-semibold text-white shadow-lg shadow-blue-600/20">
            AI
          </div>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-slate-950">AI智能审计管理系统</p>
            <p className="text-xs text-slate-500">AuditScope Portal</p>
          </div>
        </div>
      </Link>

      <nav
        className="mt-5 flex gap-2 overflow-x-auto pb-1 md:flex-col md:gap-1 md:overflow-x-visible md:pb-0"
        aria-label="主导航"
      >
        {primaryNavigation.map((item) => {
          const isActive = isActivePath(pathname, item.href);
          const className = `audit-focus-ring flex min-w-36 items-center gap-2 rounded-xl px-2.5 py-2.5 text-sm transition md:min-w-0 ${
            isActive
              ? "bg-blue-50 text-blue-700 ring-1 ring-blue-100"
              : "text-slate-700 hover:bg-slate-50 hover:text-slate-950"
          }`;
          const content = (
            <>
              <span
                aria-hidden="true"
                className={`grid size-7 shrink-0 place-items-center rounded-lg text-[11px] font-semibold ${
                  isActive ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-500"
                }`}
              >
                {item.symbol}
              </span>
              <span className="truncate font-medium">{item.label}</span>
            </>
          );

          if (item.target === "backend") {
            return (
              <a
                key={item.id}
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
              key={item.id}
              href={item.href}
              title={item.description}
              aria-current={isActive ? "page" : undefined}
              className={className}
            >
              {content}
            </Link>
          );
        })}
      </nav>

      <div className="mt-5 border-t border-slate-200 pt-4 md:mt-auto">
        <div className="flex items-center justify-between gap-3">
          <p className="text-xs font-semibold text-slate-500">历史对话</p>
          <a className="audit-focus-ring rounded-lg px-2 py-1 text-xs font-semibold text-blue-700 hover:bg-blue-50" href="/chat">
            新建
          </a>
        </div>
        <div className="mt-2 space-y-1">
          {recentConversations.map((conversation) => (
            <a
              key={conversation.title}
              className="audit-focus-ring block truncate rounded-lg px-2 py-2 text-xs text-slate-600 hover:bg-slate-50 hover:text-slate-950"
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
