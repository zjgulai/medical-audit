import Link from "next/link";

import { ReplicaNotice, ReplicaPageHeader } from "./replica-page-kit";

type ReplicaPreviewPageProps = {
  readonly kicker: string;
  readonly title: string;
  readonly description: string;
  readonly checkpoints: readonly string[];
};

export function ReplicaPreviewPage({
  kicker,
  title,
  description,
  checkpoints
}: ReplicaPreviewPageProps) {
  return (
    <main className="replica-page replica-page-standard replica-preview-page">
      <ReplicaPageHeader
        kicker={kicker}
        title={title}
        description={description}
        actions={<span className="replica-preview-badge">内测中</span>}
      />

      <section className="replica-preview-panel" aria-label={`${title}开通说明`}>
        <div>
          <span className="replica-preview-mark" aria-hidden="true">…</span>
          <h2>{title}正在完善</h2>
          <p>该模块先保留入口，不再展示不能直接使用的指标、流程和结果卡片。等后端能力和验收链路完成后，再恢复完整工作台。</p>
        </div>
        <ul>
          {checkpoints.map((checkpoint) => (
            <li key={checkpoint}>{checkpoint}</li>
          ))}
        </ul>
      </section>

      <ReplicaNotice>
        当前可先使用 <Link href="/chat">AI 对话</Link>、<Link href="/documents">文档检索</Link> 和 <Link href="/knowledge-base">知识库</Link> 完成依据查询与材料核验。
      </ReplicaNotice>
    </main>
  );
}
