---
title: 真实生成模型 Provider 生产门禁（F2）
doc_type: workflow
module: knowledge-query-engine
topic: answer-provider-production-gate
status: stable
created: 2026-06-15
updated: 2026-06-24
owner: self
source: human+ai
---

# 真实生成模型 Provider 生产门禁（F2）

> 本文件由 `drafts/analysis/analysis-answer-provider-production-gate-plan-draft-20260615.md` 定稿。
> 工具链就绪：`answer-provider-smoke`、`evaluate-answers`、答案预检与生产 `--require-generated-answer` E2E 闸均已实现。

## 0. 2026-06-24 验证结论（最新，权威）

本轮用 **DeepSeek（`openai` 兼容，`deepseek-chat`）** 完整跑通了门禁的 §4.2/§4.3 并做了生产路径深挖，结论如下：

**F2 状态：能力已验证；生产激活暂缓，待检索质量/拒答阈值调优。生产保持安全回退（引用式答案，零幻觉）。**

已确凿验证：

- §4.2 provider smoke：DeepSeek 鉴权通过，生成带 `[Cn]` 引用的答案，`success=true`、`citation_marker_present=true`、`required_term_present=true`。
- §4.3 答案评测（文件索引）：`pass_rate=87.5%`(7/8)、`citation_marker_rate=100%`、`unsupported_claim_free_rate=100%`(**零幻觉**)、`refusal_accuracy_rate=100%`；deepseek-chat 与 deepseek-reasoner、600/900 token 结果一致（不是模型/截断问题）。
- DeepSeek 余额需充值（首次 smoke 报 `402 Insufficient Balance`，充值后通过）。

定位到的真因（非 bug，属正确安全行为）：

- 评测用的是**文件索引**，生产在线检索是 **pgvector**，两者对同一问题召回内容不同。
- 进程内复刻真实路径（pgvector + DeepSeek）发现：弱召回问题（如 `ICD-10医保2.0版 A00.0`，pgvector 召回到 ICD-9-CM3 手术编码表等弱相关 OCR 片段）会让 DeepSeek **主动拒答**（原文："依据不足，当前知识库未检索到足够可引用依据，拒绝生成结论。"）→ 无引用标记 → 系统**安全回退**到引用式答案。
- 即 **端到端"真实生成率"取决于 pgvector 检索质量**；证据充分时生成带引用答案，证据不足时模型拒答并回退，全程零幻觉。文件索引评测（7/8）**高估**了生产生成率。

激活姿态修正：

- 不应以"对任意问题强制 §4.5 no-fallback"为激活门禁——弱召回问题拒答/回退是**设计内的安全行为**。
- 正确激活姿态为 **generate-or-safe-fallback**：证据充分→生成带引用答案；不足→拒答回退。产品表达应为"AI 生成带引用审计答案；依据不足时回退到引用式答案"。

激活前仍需处理：

- 真正提升生产生成率 = 调优 pgvector 检索召回质量 + DeepSeek 提示词/拒答阈值（用"进程内 pgvector+DeepSeek 复刻"作测试台，见 §6）。
- 一个待复核的服务态现象：本轮密集重启期间，服务进程曾出现 `state.answer_generation_provider=None`（`/query` 返回 `fallback_used=True, generation_error=None`），而同容器 `create_app()` 单独构造却能得到 provider；疑为多次重启的瞬时态。**正式激活时须用一次干净部署 + 验证服务态 provider 已生效（`generation_error` 反映真实生成尝试，而非 None）。**

## 6. 调优测试台（进程内 pgvector + DeepSeek 复刻）

不污染生产、不依赖服务进程,直接在容器内复刻真实服务路径验证提示词/检索调优效果：

```bash
docker exec \
  -e MEDICAL_AUDIT_KB_ANSWER_PROVIDER=openai -e MEDICAL_AUDIT_KB_ANSWER_MODEL=deepseek-chat \
  -e MEDICAL_AUDIT_KB_ANSWER_API_KEY_ENV=DEEPSEEK_API_KEY -e MEDICAL_AUDIT_KB_ANSWER_BASE_URL=https://api.deepseek.com/v1 \
  -e MEDICAL_AUDIT_KB_ANSWER_MAX_OUTPUT_TOKENS=900 -e MEDICAL_AUDIT_KB_ANSWER_TEMPERATURE=0 \
  -e DEEPSEEK_API_KEY="$DEEPSEEK_API_KEY" \
  medical_audit_app python -c '...load_settings + answer_generation_provider_from_settings + OpenAICompatibleEmbeddingProvider.from_env(KIMI) + load_postgres_hybrid_search_engine + build_citation_backed_answer...'
```

判读 `fallback_used` / `generation_error`：`no citation markers` 常因 DeepSeek 拒答（弱召回），应从检索召回与提示词两端改进，而非放宽引用校验。

## 1. 当前结论（阻塞点）

**不能启用 no-fallback 真实生成；产品表达暂为"基于证据检索的引用式回答",不得宣称"AI 生成审计结论"。**

事实依据：

- 代码仅支持 `anthropic` 和 `openai` 兼容接口两类真实 provider，`fallback` 为默认。
- 生产容器：`KIMI_API_KEY=SET`，其余 provider key 与全部 `MEDICAL_AUDIT_KB_ANSWER_*` 均 `UNSET`。
- 历史 smoke：Anthropic `401 invalid x-api-key`（Sonnet 4.6 / Haiku 4.5，2026-06-14）；Kimi 常规 chat `401`、Coding endpoint `403 access_terminated_error`。
- 结论：当前没有可迁移到生产的、已验证可用的 chat answer provider。**F2 上线前必须先拿到一个能通过 §4.2 smoke 的 key。**

## 2. Provider 候选与进入条件

| 候选 | 配置 | 现状 | 进入下一步条件 |
| --- | --- | --- | --- |
| Anthropic | `PROVIDER=anthropic` + `ANTHROPIC_API_KEY` | 历史 401 | 用**新的有效 key** 跑通 smoke |
| OpenAI | `PROVIDER=openai` + OpenAI base URL + `OPENAI_API_KEY` | 无 key | 提供服务端 key + 跑通 smoke |
| Moonshot/Kimi Chat | `openai` 兼容 + Moonshot base URL | 仅有 Coding key（已失败） | 提供可用于普通 chat completion 的 key（不得复用 Coding key） |
| DeepSeek / 其他兼容 | `openai` 兼容 + 对应 base URL | 无验证 | 提供 key + base URL + model 跑通 smoke |

替代路径：保留 citation 引用式 fallback 作为产品边界（更稳，但不能宣称生成式审计结论）。

## 3. 密钥硬边界

- 真实 key 不进 Git/PR/Markdown/日志/前端/浏览器存储/`tmp/outputs`/shell 历史。
- 文档与命令只出现 env var **名称**，不出现 key 值。
- `MEDICAL_AUDIT_KB_ANSWER_API_KEY_ENV` 的值是环境变量名（如 `ANTHROPIC_API_KEY`），不是密钥。
- 生产 key 仅进远端服务端 env 或 secret 设施；embedding key 与答案生成 key 分开管理。

## 4. 验证顺序（逐闸，任一不过即停）

### 4.1 只读环境检查
只输出候选 key 与 `MEDICAL_AUDIT_KB_ANSWER_*` 的 `SET/UNSET`，不读/不打印 key 值。结果只代表"是否具备测试条件"。

### 4.2 单 provider 预检 smoke

```bash
uv run medical-audit-kb answer-provider-smoke \
  --answer-provider <anthropic|openai> \
  --answer-model <verified-model> \
  --answer-api-key-env <ENV_NAME> \
  [--answer-base-url <https://.../v1>] \
  --answer-max-output-tokens 300 --answer-temperature 0 \
  --json-output tmp/outputs/answer-provider-smoke-<provider>-<date>.json
```

通过：exit 0；`success=true`；`citation_marker_present=true`；`required_term_present=true`。

### 4.3 真实答案评测（仅首个通过 smoke 的 provider）

```bash
uv run medical-audit-kb evaluate-answers \
  --answer-provider <provider> --answer-model <verified-model> \
  --answer-api-key-env <ENV_NAME> [--answer-base-url <...>] \
  --answer-max-output-tokens 600 --answer-temperature 0 \
  --json-output tmp/outputs/answer-evaluation-<provider>-<date>.json
```

通过（**不加 `--allow-answer-fallback`**）：`generation_success_rate=100%`、`fallback_rate=0%`、`pass_rate=100%`、`citation_marker_rate=100%`、`unsupported_claim_free_rate=100%`。

### 4.4 生产 env 写入与回滚

smoke + 评测均通过后：
1. 备份远端 `configs/deploy/tencent-cloud/medical-audit.env`。
2. 写入 `MEDICAL_AUDIT_KB_ANSWER_PROVIDER / _API_KEY_ENV / _MODEL / _BASE_URL / _MAX_OUTPUT_TOKENS / _TEMPERATURE`。
3. 仅重启 `medical_audit_app`；不动 pg/pgdata/共享 nginx。

回滚（app 起不来 / 生产 `fallback_used=true` / provider 失败或质量不达标）：恢复备份 env 或设 `PROVIDER=fallback`，仅重启 app，失败报告留档并在台账标未通过。

### 4.5 生产 no-fallback E2E（写 env 后必跑）

```bash
python3 scripts/run-production-e2e-smoke.py \
  --base-url https://audit.lute-tlz-dddd.top \
  --expected-matching-embeddings 49051 \
  --require-generated-answer \
  --report tmp/outputs/production-e2e-smoke-require-generated-answer-<date>.json
```

通过：`status=pass`；`/query` 不返回 fallback；引用标记存在；embedding 数与生产激活索引一致；TLS/health/search/page/audit-logs 均过。

## 5. 立即下一步

F2 阻塞在凭证。需要决策并提供**一个**可用生成 provider key（写入服务端 env，不入 Git）：

1. 选定 provider（Anthropic / OpenAI / Moonshot chat / DeepSeek 等）。
2. 在本地或服务端配置对应 `*_API_KEY` env。
3. 跑 §4.2 smoke；通过再跑 §4.3 评测；全过再 §4.4 写生产 + §4.5 no-fallback E2E。
4. 任一闸不过即停、不写生产，保留 citation fallback 为产品边界。
