"use client";

import { FormEvent, Suspense, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { buildReplicaLocalGateNotice, ReplicaNotice } from "@/components/replica/replica-page-kit";
import { useReplicaChatData } from "@/components/replica/use-replica-runtime";
import type { ReferenceHistoryMessage } from "@/lib/reference-replica-data";

type LocalMessage = {
  readonly id: string;
  readonly role: "user" | "assistant";
  readonly text: string;
};

const chatShortcuts = [
  { label: "智能体广场", href: "/agent-market", icon: "◎" },
  { label: "我的智能体", href: "/agents", icon: "▣" },
  { label: "OCR 识别", href: "/documents", icon: "⌗" },
  { label: "数据分析", href: "/analytics", icon: "▥" },
  { label: "项目管理", href: "/projects", icon: "▤" }
] as const;

export default function ChatPortalPage() {
  return (
    <Suspense fallback={<ChatPortalLoading />}>
      <ChatPortalContent />
    </Suspense>
  );
}

function ChatPortalLoading() {
  return (
    <main className="replica-chat-page" data-replica-source="loading" data-replica-status="loading">
      <section className="replica-chat-hero" aria-labelledby="replica-chat-loading-title">
        <h1 id="replica-chat-loading-title"><span>AI，</span>让审计更智能</h1>
        <p className="replica-chat-subtitle">正在恢复当前会话。</p>
      </section>
    </main>
  );
}

function mapHistoryMessages(messages: readonly ReferenceHistoryMessage[] | undefined): readonly LocalMessage[] {
  return (messages ?? []).map((message) => ({
    id: message.id,
    role: message.role,
    text: message.text
  }));
}

function ChatPortalContent() {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<readonly LocalMessage[]>([]);
  const [notice, setNotice] = useState("");
  const searchParams = useSearchParams();
  const chatData = useReplicaChatData();
  const defaultAgent = chatData.data.agents[0];
  const activeHistoryId = searchParams.get("history");
  const activeHistory = useMemo(
    () => chatData.data.historyItems.find((item) => item.id === activeHistoryId) ?? null,
    [activeHistoryId, chatData.data.historyItems]
  );
  const restoredMessages = useMemo(() => mapHistoryMessages(activeHistory?.messages), [activeHistory?.messages]);
  const previewMessages = messages.length > 0 ? messages : restoredMessages;
  const activeAssistantName = activeHistory?.agentName ?? defaultAgent?.name ?? "AI审计助手";
  const hasConversation = previewMessages.length > 0;

  function submitQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = question.trim();
    if (!value) {
      return;
    }

    const userMessage: LocalMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      text: value
    };
    const assistantMessage: LocalMessage = {
      id: `assistant-${Date.now()}`,
      role: "assistant",
      text: buildReplicaLocalGateNotice({
        action: `提交给「${activeAssistantName}」的问题`,
        nextStep: "问答流式响应 API"
      })
    };

    setMessages((current) => [...current, userMessage, assistantMessage]);
    setQuestion("");
  }

  return (
    <main
      className="replica-chat-page"
      data-replica-source={chatData.source}
      data-replica-status={chatData.status}
    >
      <section className="replica-chat-hero" aria-labelledby="replica-chat-title">
        <h1 id="replica-chat-title"><span>AI，</span>让审计更智能</h1>
        <p className="replica-chat-subtitle">与 AI 审计助手进行自然语言对话，获取审计建议和数据分析</p>

        {activeHistory && (
          <section className="replica-history-context" aria-label="历史对话恢复">
            <span>已恢复历史对话</span>
            <h2>{activeHistory.title}</h2>
            <p>{activeHistory.summary ?? "当前已恢复历史标题，完整上下文将在正式会话中补齐。"}</p>
          </section>
        )}

        <form className="replica-chat-box" onSubmit={submitQuestion}>
          <textarea
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder={'输入 "/" 可快捷使用技能，或描述你的审计问题...'}
            aria-label="输入相关问题以对话"
            rows={3}
          />
          <div className="replica-chat-tools">
            <button
              type="button"
              className="replica-tool-button"
              aria-label="上传附件"
              onClick={() => setNotice(buildReplicaLocalGateNotice({
                action: "添加内容",
                nextStep: "附件上传 API"
              }))}
            >
              +
            </button>
            <button
              type="button"
              className="replica-chat-agent-chip"
              onClick={() => setQuestion(`请使用「${activeAssistantName}」帮助我分析：`)}
            >
              <span aria-hidden="true">▣</span>
              智能体
            </button>
            <span className="replica-chat-model-chip">↯ Kimi K2.5 快速</span>
            <button
              type="submit"
              className="replica-send-button"
              disabled={!question.trim()}
              aria-label="发送问题"
            >
              ↑
            </button>
          </div>
        </form>
        {notice && <ReplicaNotice>{notice}</ReplicaNotice>}
        <nav className="replica-chat-shortcuts" aria-label="AI 对话快捷入口">
          {chatShortcuts.map((shortcut) => (
            <Link key={shortcut.href} href={shortcut.href}>
              <span aria-hidden="true">{shortcut.icon}</span>
              {shortcut.label}
            </Link>
          ))}
        </nav>
      </section>

      {hasConversation ? (
        <section className="replica-message-preview" aria-label="对话记录">
          {previewMessages.map((message) => (
            <div key={message.id} className={`replica-message ${message.role}`}>
              <span>{message.role === "user" ? "我" : "AI"}</span>
              <p>{message.text}</p>
            </div>
          ))}
        </section>
      ) : null}
    </main>
  );
}
