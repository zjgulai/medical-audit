"use client";

import Link from "next/link";
import { useState } from "react";

const QUICK_PROMPTS = [
  "门诊超量开药如何核验医保审核依据",
  "重复收费疑点应如何取证",
  "诊疗项目收费与目录限制如何交叉审核"
] as const;

export function AiChatFab() {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");

  const trimmed = text.trim();
  const chatHref = trimmed ? `/chat?question=${encodeURIComponent(trimmed)}` : "/chat";

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="打开 AI 对话"
        className="audit-focus-ring fixed bottom-4 right-4 z-30 grid size-11 place-items-center rounded-full bg-[var(--audit-primary)] text-white shadow-[0_14px_32px_rgb(29_117_201/0.42)] transition hover:scale-105 sm:bottom-6 sm:right-6 sm:size-14"
      >
        <span aria-hidden="true" className="text-sm font-bold tracking-tight sm:text-base">
          AI
        </span>
      </button>

      {open ? (
        <div className="fixed inset-0 z-40" role="dialog" aria-modal="true" aria-label="AI 审计助手对话">
          <div
            className="absolute inset-0 bg-[rgb(16_24_40/0.4)]"
            onClick={() => setOpen(false)}
            aria-hidden="true"
          />
          <div className="absolute inset-x-0 bottom-0 flex max-h-[88vh] flex-col rounded-t-[var(--audit-radius-lg)] bg-[var(--audit-bg-raised)] shadow-[var(--audit-shadow-lg)] sm:inset-x-auto sm:bottom-6 sm:right-6 sm:top-auto sm:h-[34rem] sm:w-[26rem] sm:rounded-[var(--audit-radius-lg)]">
            <div className="flex items-center justify-between border-b border-[var(--audit-line)] px-5 py-4">
              <div className="flex items-center gap-3">
                <span
                  aria-hidden="true"
                  className="grid size-9 place-items-center rounded-full bg-[var(--audit-primary)] text-sm font-bold text-white"
                >
                  AI
                </span>
                <div>
                  <p className="audit-kicker">AI 审计助手</p>
                  <h2 className="audit-card-title leading-tight">快速对话</h2>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="关闭对话"
                className="audit-focus-ring rounded-[var(--audit-radius-sm)] px-2 py-1 text-lg text-[var(--audit-ink-muted)] hover:bg-[var(--audit-surface-muted)]"
              >
                ✕
              </button>
            </div>

            <div className="flex-1 overflow-auto px-5 py-4">
              <p className="audit-copy">输入审计问题,或选一个常用场景,进入带引用依据的完整对话。</p>
              <p className="audit-kicker mt-4">常用场景</p>
              <div className="mt-2 flex flex-col gap-2">
                {QUICK_PROMPTS.map((prompt) => (
                  <Link
                    key={prompt}
                    href={`/chat?question=${encodeURIComponent(prompt)}`}
                    className="audit-focus-ring rounded-[var(--audit-radius-md)] border border-[var(--audit-line)] bg-[var(--audit-surface-subtle)] px-3 py-2 text-sm text-[var(--audit-ink-muted)] transition hover:border-[var(--audit-primary-line)] hover:text-[var(--audit-ink)]"
                  >
                    {prompt}
                  </Link>
                ))}
              </div>
            </div>

            <div className="border-t border-[var(--audit-line)] p-4">
              <textarea
                value={text}
                onChange={(event) => setText(event.target.value)}
                rows={2}
                placeholder="输入你的审计问题…"
                aria-label="AI 对话输入"
                className="audit-focus-ring audit-input w-full resize-none px-3 py-2 text-sm"
              />
              <Link href={chatHref} className="audit-focus-ring audit-btn audit-btn-primary mt-2 w-full justify-center">
                进入完整对话 ›
              </Link>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
