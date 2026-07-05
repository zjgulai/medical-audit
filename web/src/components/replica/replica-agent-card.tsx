"use client";

import type { ReferenceAgentCard } from "@/lib/reference-replica-data";

type ReplicaAgentCardProps = {
  readonly agent: ReferenceAgentCard;
  readonly onStart?: (agent: ReferenceAgentCard) => void;
};

export function ReplicaAgentCard({ agent, onStart }: ReplicaAgentCardProps) {
  return (
    <article className="replica-agent-card">
      <button
        type="button"
        className="replica-agent-more"
        aria-label={`打开 ${agent.name} 操作`}
      >
        ▾
      </button>
      <div className={`replica-agent-initial tone-${agent.tone}`}>{agent.initial}</div>
      <div className="replica-agent-body">
        <div className="replica-agent-title-row">
          <h3>{agent.name}</h3>
          <span className="replica-agent-badge">{agent.category}</span>
        </div>
        <p>{agent.summary}</p>
        <div className="replica-agent-meta">
          <span>{agent.project}</span>
          <span># {agent.topic}</span>
        </div>
        <div className="replica-agent-readiness" aria-label={`${agent.name} 当前状态`}>
          <span>本地预演</span>
          <span>证据优先</span>
        </div>
      </div>
      <button
        type="button"
        className="replica-agent-start"
        onClick={() => onStart?.(agent)}
        aria-label={`使用 ${agent.name} 开始审计`}
      >
        开始审计
      </button>
    </article>
  );
}
