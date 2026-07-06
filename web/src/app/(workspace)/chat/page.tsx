"use client";

import { FormEvent, Suspense, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { ReplicaNotice } from "@/components/replica/replica-page-kit";
import { useReplicaChatData } from "@/components/replica/use-replica-runtime";
import {
  analyzeChatAttachment,
  fetchDocumentSourceCollections,
  fetchQueryModels,
  runKnowledgeQuery
} from "@/lib/api-client";
import type {
  ChatAttachmentAnalysisResponse,
  ChatModelCatalogItem,
  ChatModelAlias,
  DocumentSourceCollectionCatalogItem,
  QueryCitation,
  SourceCollection
} from "@/lib/api-types";
import type { ReferenceAgentCard, ReferenceHistoryMessage } from "@/lib/reference-replica-data";

type LocalMessage = {
  readonly id: string;
  readonly role: "user" | "assistant";
  readonly text: string;
  readonly meta?: string;
  readonly citations?: readonly QueryCitation[];
};

type CommandFragment = {
  readonly index: number;
  readonly fragment: string;
};

const DEFAULT_MODEL_OPTIONS: readonly ChatModelCatalogItem[] = [
  {
    alias: "kimi-2.7",
    label: "Kimi 2.7",
    provider: null,
    available: false,
    default: true,
    unavailable_reason: "模型目录读取中"
  },
  {
    alias: "deepseek-v4-pro",
    label: "DeepSeek V4 Pro",
    provider: null,
    available: false,
    default: false,
    unavailable_reason: "模型目录读取中"
  }
];

const DEFAULT_MODEL: ChatModelAlias = "kimi-2.7";
const MODEL_STORAGE_KEY = "medical-audit-chat-model";

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
  const [modelOptions, setModelOptions] = useState<readonly ChatModelCatalogItem[]>(DEFAULT_MODEL_OPTIONS);
  const [selectedModel, setSelectedModel] = useState<ChatModelAlias>(DEFAULT_MODEL);
  const [sourceCollections, setSourceCollections] = useState<
    readonly DocumentSourceCollectionCatalogItem[]
  >([]);
  const [selectedSources, setSelectedSources] = useState<readonly SourceCollection[]>([]);
  const [sourceMenuOpen, setSourceMenuOpen] = useState(false);
  const [commandMenuOpen, setCommandMenuOpen] = useState(false);
  const [commandQuery, setCommandQuery] = useState("");
  const [selectedAgent, setSelectedAgent] = useState<ReferenceAgentCard | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const searchParams = useSearchParams();
  const chatData = useReplicaChatData();
  const activeHistoryId = searchParams.get("history");
  const requestedAgentId = searchParams.get("agent");
  const activeHistory = useMemo(
    () => chatData.data.historyItems.find((item) => item.id === activeHistoryId) ?? null,
    [activeHistoryId, chatData.data.historyItems]
  );
  const restoredMessages = useMemo(() => mapHistoryMessages(activeHistory?.messages), [activeHistory?.messages]);
  const previewMessages = messages.length > 0 ? messages : restoredMessages;
  const hasConversation = previewMessages.length > 0;
  const selectedModelOption = modelOptions.find((item) => item.alias === selectedModel) ?? modelOptions[0];
  const queryableSources = useMemo(
    () => sourceCollections.filter((item) => item.queryable || item.product_queryable),
    [sourceCollections]
  );
  const selectedSourceLabel = selectedSources.length === 0 ? "全部知识库" : `${selectedSources.length} 个知识库`;
  const filteredAgents = useMemo(() => {
    const normalized = commandQuery.trim().toLowerCase();
    if (!normalized) {
      return chatData.data.agents.slice(0, 8);
    }
    return chatData.data.agents
      .filter((agent) => {
        const haystack = `${agent.name} ${agent.topic} ${agent.summary}`.toLowerCase();
        return haystack.includes(normalized);
      })
      .slice(0, 8);
  }, [chatData.data.agents, commandQuery]);

  useEffect(() => {
    let mounted = true;
    const stored = window.localStorage.getItem(MODEL_STORAGE_KEY);
    const preferredModel: ChatModelAlias =
      stored === "kimi-2.7" || stored === "deepseek-v4-pro" ? stored : DEFAULT_MODEL;
    if (preferredModel !== DEFAULT_MODEL) {
      setSelectedModel(preferredModel);
    }
    void fetchQueryModels()
      .then((catalog) => {
        if (!mounted) {
          return;
        }
        const options = catalog.items.length > 0 ? catalog.items : DEFAULT_MODEL_OPTIONS;
        setModelOptions(options);
        const hasPreferredModel = options.some((item) => item.alias === preferredModel);
        const defaultOption = options.find((item) => item.default) ?? options[0];
        if (!hasPreferredModel && defaultOption) {
          setSelectedModel(defaultOption.alias);
        }
      })
      .catch(() => {
        if (mounted) {
          setNotice("模型目录暂时不可用，请稍后重试。");
        }
      });
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    let mounted = true;
    void fetchDocumentSourceCollections()
      .then((catalog) => {
        if (mounted) {
          setSourceCollections(catalog.items);
        }
      })
      .catch(() => {
        if (mounted) {
          setNotice("知识库目录暂时不可用，当前将按默认全部范围提问。");
        }
      });
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    if (!requestedAgentId || selectedAgent) {
      return;
    }
    const matched = chatData.data.agents.find((agent) => agent.id === requestedAgentId);
    if (matched) {
      setSelectedAgent(matched);
    }
  }, [chatData.data.agents, requestedAgentId, selectedAgent]);

  function updateQuestion(value: string) {
    setQuestion(value);
    const fragment = commandFragment(value);
    if (fragment) {
      setCommandMenuOpen(true);
      setCommandQuery(fragment.fragment);
      return;
    }
    setCommandQuery("");
  }

  function selectModel(model: ChatModelAlias) {
    setSelectedModel(model);
    window.localStorage.setItem(MODEL_STORAGE_KEY, model);
  }

  function toggleSource(source: SourceCollection) {
    setSelectedSources((current) =>
      current.includes(source)
        ? current.filter((item) => item !== source)
        : [...current, source]
    );
  }

  function selectAgent(agent: ReferenceAgentCard) {
    const fragment = commandFragment(question);
    const nextQuestion = fragment
      ? `${question.slice(0, fragment.index)}@${agent.name} ${question.slice(fragment.index + fragment.fragment.length + 1)}`
      : `${question}${question.trim() ? " " : ""}@${agent.name} `;
    setSelectedAgent(agent);
    setQuestion(nextQuestion);
    setCommandMenuOpen(false);
    setCommandQuery("");
  }

  async function submitQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = question.trim();
    if (!value || submitting) {
      return;
    }
    if (!selectedModelOption?.available) {
      setNotice(`当前模型「${selectedModel}」未完成后端配置，暂不能发起模型问答。`);
      return;
    }

    const userMessage: LocalMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      text: value,
      meta: selectedAgent ? `调用智能体：${selectedAgent.name}` : undefined
    };
    setMessages((current) => [...current, userMessage]);
    setQuestion("");
    setSubmitting(true);
    setNotice("");
    try {
      const response = await runKnowledgeQuery({
        question: value,
        top_k: 5,
        model: selectedModel,
        source_collections: selectedSources.length > 0 ? selectedSources : undefined,
        agent: selectedAgent?.id ?? null
      });
      const assistantMessage: LocalMessage = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        text: response.answer,
        meta: [
          `模型：${response.model_alias ?? selectedModel}`,
          `知识库：${selectedSourceLabel}`,
          response.agent_invocation_id ? `智能体调用已记录` : null,
          response.query_log_id ? `查询记录：${response.query_log_id}` : null
        ].filter(Boolean).join(" · "),
        citations: response.citations
      };
      setMessages((current) => [...current, assistantMessage]);
    } catch (error) {
      setMessages((current) => [
        ...current,
        {
          id: `assistant-error-${Date.now()}`,
          role: "assistant",
          text: error instanceof Error ? error.message : "问答请求未完成，请稍后重试。"
        }
      ]);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleAttachment(file: File | null) {
    if (!file || uploading) {
      return;
    }
    if (!selectedModelOption?.available) {
      setNotice(`当前模型「${selectedModel}」未完成后端配置，暂不能分析附件。`);
      return;
    }
    setUploading(true);
    setNotice("");
    setMessages((current) => [
      ...current,
      {
        id: `upload-${Date.now()}`,
        role: "user",
        text: `上传附件：${file.name}`
      }
    ]);
    try {
      const response = await analyzeChatAttachment(file, { model: selectedModel });
      setMessages((current) => [...current, attachmentMessage(response)]);
    } catch (error) {
      setMessages((current) => [
        ...current,
        {
          id: `upload-error-${Date.now()}`,
          role: "assistant",
          text: error instanceof Error ? error.message : "附件分析未完成，请确认文件格式后重试。"
        }
      ]);
    } finally {
      setUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
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
            onChange={(event) => updateQuestion(event.target.value)}
            placeholder={'输入 "@" 或 "/" 调用智能体，或描述你的审计问题...'}
            aria-label="输入相关问题以对话"
            rows={3}
          />
          <div className="replica-chat-tools">
            <div className="replica-chat-tools-left">
              <button
                type="button"
                className="replica-tool-button"
                aria-label="上传附件"
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
              >
                +
              </button>
              <input
                ref={fileInputRef}
                className="replica-hidden-file"
                type="file"
                accept=".csv,.xlsx,.xlsm,.pdf,.md,.txt"
                onChange={(event) => void handleAttachment(event.target.files?.[0] ?? null)}
              />
              <div className="replica-chat-menu-wrap">
                <button
                  type="button"
                  className="replica-chat-agent-chip"
                  onClick={() => setSourceMenuOpen((open) => !open)}
                >
                  <span aria-hidden="true">▥</span>
                  {selectedSourceLabel}
                </button>
                {sourceMenuOpen && (
                  <div className="replica-chat-popover" role="dialog" aria-label="选择知识库">
                    <button
                      type="button"
                      className={`replica-chat-option ${selectedSources.length === 0 ? "is-active" : ""}`}
                      onClick={() => setSelectedSources([])}
                    >
                      全部可用知识库
                    </button>
                    {queryableSources.map((source) => (
                      <label key={source.source_collection} className="replica-chat-check-option">
                        <input
                          type="checkbox"
                          checked={selectedSources.includes(source.source_collection)}
                          onChange={() => toggleSource(source.source_collection)}
                        />
                        <span>
                          <strong>{source.label}</strong>
                          <small>{source.scope} · {source.domain}</small>
                        </span>
                      </label>
                    ))}
                  </div>
                )}
              </div>
              <div className="replica-chat-menu-wrap">
                <button
                  type="button"
                  className="replica-chat-agent-chip"
                  onClick={() => setCommandMenuOpen((open) => !open)}
                >
                  <span aria-hidden="true">▣</span>
                  {selectedAgent?.name ?? "智能体"}
                </button>
                {commandMenuOpen && (
                  <div className="replica-chat-popover replica-chat-agent-popover" role="dialog" aria-label="选择智能体">
                    {filteredAgents.map((agent) => (
                      <button
                        key={agent.id}
                        type="button"
                        className="replica-chat-agent-option"
                        onClick={() => selectAgent(agent)}
                      >
                        <span>{agent.initial}</span>
                        <strong>{agent.name}</strong>
                        <small>{agent.topic}</small>
                      </button>
                    ))}
                    {filteredAgents.length === 0 && <p className="replica-chat-popover-empty">没有匹配的智能体</p>}
                  </div>
                )}
              </div>
            </div>
            <div className="replica-chat-tools-right">
              <label className="replica-chat-model-select">
                <span className="sr-only">选择模型</span>
                <select
                  value={selectedModel}
                  onChange={(event) => selectModel(event.target.value as ChatModelAlias)}
                  aria-label="选择模型"
                >
                  {modelOptions.map((option) => (
                    <option key={option.alias} value={option.alias} disabled={!option.available}>
                      {option.label}{option.available ? "" : "（未配置）"}
                    </option>
                  ))}
                </select>
              </label>
              <button
                type="submit"
                className="replica-send-button"
                disabled={!question.trim() || submitting}
                aria-label="发送问题"
              >
                {submitting ? "…" : "↑"}
              </button>
            </div>
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
              <div className="replica-message-body">
                {message.meta && <small>{message.meta}</small>}
                <p>{message.text}</p>
                {message.citations && message.citations.length > 0 && (
                  <ul className="replica-message-citations" aria-label="引用依据">
                    {message.citations.slice(0, 3).map((citation) => (
                      <li key={citation.citation_id}>
                        <strong>{citation.marker}</strong>
                        {citation.snippet}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          ))}
        </section>
      ) : null}
    </main>
  );
}

function commandFragment(value: string): CommandFragment | null {
  const atIndex = value.lastIndexOf("@");
  const slashIndex = value.lastIndexOf("/");
  const index = Math.max(atIndex, slashIndex);
  if (index < 0) {
    return null;
  }
  const fragment = value.slice(index + 1);
  if (/\s/.test(fragment)) {
    return null;
  }
  return { index, fragment };
}

function attachmentMessage(response: ChatAttachmentAnalysisResponse): LocalMessage {
  return {
    id: `attachment-${Date.now()}`,
    role: "assistant",
    text: response.answer,
    meta: [
      `附件：${response.file_name}`,
      response.mode === "table-analysis" ? "数据分析" : "文档总结",
      `模型：${response.model_alias}`,
      ...response.summary_items.slice(0, 2)
    ].join(" · ")
  };
}
