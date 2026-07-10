---
title: 真实生成模型 Provider 生产门禁（F2）
doc_type: workflow
module: knowledge-query-engine
topic: answer-provider-production-gate
status: stable
created: 2026-06-15
updated: 2026-07-10
owner: self
source: human+ai
---

# 真实生成模型 Provider 生产门禁（F2）

> 本文件由 `drafts/analysis/analysis-answer-provider-production-gate-plan-draft-20260615.md` 定稿。
> 工具链就绪：`audit-answer-provider-gate-readiness.py`、`run-production-chat-model-catalog-readonly-probe.py`、`answer-provider-smoke`、`evaluate-answers`、答案预检与生产 `--require-generated-answer` E2E 闸均已实现。

## 0. 2026-07-10 chat model catalog 只读门禁补充（最新）

`/chat` 现使用模型别名合同，生产判断需要分成两层：

1. **目录合同可观测**：`/api/v1/query/models` 可通过 GET 返回 `kimi-2.7` 与 `deepseek-v4-pro`，且响应显式声明 `production_write=false`、`provider_call=false`、`secret_values_reported=false`。这只证明前端可读取模型目录。
2. **模型启用门禁**：至少一个模型别名返回 `available=true`，才允许继续进入最小 provider smoke。若 `available_model_aliases=[]`，即使目录接口可达，也不能宣称 `/chat` 已具备真实模型回答能力。

标准命令：

```bash
pnpm production:chat-model-catalog-readonly
```

用于生产只读目录合同观测。该命令只发 GET，不写生产环境变量，不重启容器，不调用外部 provider。

```bash
pnpm production:chat-model-ready
```

用于生产模型启用门禁。该命令会在没有可用模型别名时返回非零退出码；这代表继续 provider smoke 的前置条件未满足，而非业务代码需要回滚。

2026-07-10 生产证据：

- `production:chat-model-catalog-readonly` 对当前生产返回 `status=pass`，`contract_version=chat-model-catalog-v1`，`model_aliases=["kimi-2.7","deepseek-v4-pro"]`。
- PR #226 已合入并部署为 `main@c29f5e37`；生产环境已配置独立的 `MOONSHOT_API_KEY` 与 `DEEPSEEK_API_KEY`，两个模型别名均返回 `available=true`。
- 经授权对两个模型各执行一次最小 `/api/v1/query`，请求均返回 `200` 和 3 条引用，但 `fallback_used=true`，只能证明检索、请求编排和查询历史链路可用，不能证明模型生成已生效。
- 后续修复分支必须先输出脱敏的 `generation_status` 与 `generation_failure_code`，再通过 provider-specific `thinking` 参数和输出预算修正做第二轮最小验收；修复分支未部署前，生产结论仍是“模型可选，生成链路未达标”。

2026-07-10 provider 合同修正：

- 历史产品别名 `kimi-2.7` 暂保留以兼容已发布请求；默认运行时映射到官方 Chat Completion 已发布的 `kimi-k2.6`、`https://api.moonshot.cn/v1`、`temperature=1.0`，界面标签必须明确显示实际模型。生产环境变量切换仍需单独授权。
- 产品别名 `deepseek-v4-pro` 映射到 `deepseek-v4-pro`、`https://api.deepseek.com`、`temperature=0.0`。
- Kimi K2.7 Code 必须使用 `thinking=enabled`；本项目默认输出预算为 4096，并按 Kimi API 合同发送 `max_completion_tokens`。DeepSeek V4 Pro 的短答案检索增强路径使用 `thinking=disabled` 和 `max_tokens=900`。
- 运行时默认值、生产 env 示例和只读 readiness 报告必须使用同一映射；未配置有效 key 时仍保持不可用，不得因默认值完整而升级为 provider 就绪。
- 合同依据：Kimi `https://platform.kimi.com/docs/api/chat`；DeepSeek `https://api-docs.deepseek.com/`。

边界：

- `KIMI_API_KEY=SET` 只说明 embedding runtime 已配置；它不能自动等同于 `kimi-2.7` 聊天模型可用。
- `MOONSHOT_API_KEY` 或 `DEEPSEEK_API_KEY` 写入生产 env、容器重启、provider smoke、真实 `/chat` 提问都必须作为后续单独授权动作执行。
- provider smoke 通过前，产品状态仍应表述为“模型目录可见，真实生成能力待启用”。

## 0. 2026-06-29 main@a78bf8e5 最新 UI/UX 生产基线后只读复核结论（最新）

本轮 Batch 0 已确认生产站点运行 `main@a78bf8e5a1303178df26d03c6a687bd68f4512c2` 的最新 UI/UX 基线；该复核没有写生产 `MEDICAL_AUDIT_KB_ANSWER_*`，也没有调用外部 answer provider。生产-only readiness 结论不变：

**F2 生产仍阻塞，不能写生产 `MEDICAL_AUDIT_KB_ANSWER_*`，也不能执行生产 no-fallback E2E。**

本轮证据：

- 生产部署状态审计：`tmp/outputs/tencent-cloud-deployment-state-batch0-latest-ui-20260629T2151.json` 返回 `status=pass`，远端 `.deploy-sha=a78bf8e5a1303178df26d03c6a687bd68f4512c2`，app/postgres/clamav healthy，`matching_embedding_count=49051`。
- 生产-only 只读 readiness：`tmp/outputs/answer-provider-gate-readiness-production-only-batch0-latest-ui-20260629T2151.json` 返回 `status=blocked`、`blockers=["no-provider-api-key-env-set"]`，`provider_call_status=not_called`，`production_env_write=false`。
- 生产前端验收：`tmp/outputs/production-frontend-acceptance-batch0-latest-ui-20260629T2151.json` 返回 `status=pass`、`route_count=21`、`check_count=42`、`p0=[]`、`p1=[]`。

边界：

- 当前生产 UI/UX 与 `main@a78bf8e5` 对齐；本轮没有重复执行部署。
- 生产-only readiness 是当前生产判定依据；普通前端验收或部署状态审计不能覆盖 `no-provider-api-key-env-set`。
- 如需继续 §4.2 provider smoke，必须明确授权一次外部 provider 调用；通过 smoke 前不得进入真实答案评测、生产 env 写入或 `--require-generated-answer` 生产 E2E。

## 0.1 2026-06-29 main@66b22d45 部署后只读复核结论

本轮已完成 `main@66b22d4549724a5065f396b94d6e1db15471983b` 的生产 UI/UX 部署，但该部署没有写生产 `MEDICAL_AUDIT_KB_ANSWER_*`，也没有调用外部 answer provider。部署后重跑生产-only readiness，结论不变：

**F2 生产仍阻塞，不能写生产 `MEDICAL_AUDIT_KB_ANSWER_*`，也不能执行生产 no-fallback E2E。**

本轮证据：

- 生产-only 只读 readiness：`tmp/outputs/answer-provider-gate-readiness-production-only-after-deploy-main-66b22d45-20260629T075824Z.json` 返回 `status=blocked`、`blockers=["no-provider-api-key-env-set"]`；生产 `answer_runtime.status=fallback_or_unset`，`DEEPSEEK_API_KEY`、`OPENAI_API_KEY`、`ANTHROPIC_API_KEY`、`MOONSHOT_API_KEY` 均为 `UNSET`。
- 部署后生产综合 E2E：`tmp/outputs/production-e2e-smoke-after-deploy-main-66b22d45-20260629T075824Z.json` 返回 `status=pass`，但 `query-api-with-citations.fallback_used=true`，该报告只证明 citation fallback 路径可用，不证明生成模型 no-fallback 可用。

边界：

- 本轮有授权生产部署，但没有 provider call、没有生产 env 写入、没有 schema migration。
- 生产-only readiness 是当前生产判定依据；综合 readiness 或普通 E2E smoke 不能覆盖 `no-provider-api-key-env-set`。
- 如需继续 §4.2 provider smoke，必须明确授权一次外部 provider 调用；通过 smoke 前不得进入真实答案评测、生产 env 写入或 `--require-generated-answer` 生产 E2E。

## 0.2 2026-06-29 Batch 2 部署前只读复核结论

本批先重跑 §4.1 只读 readiness，并把本地与生产 scope 分开判读。结论：

**F2 生产仍阻塞，不能写生产 `MEDICAL_AUDIT_KB_ANSWER_*`，也不能执行生产 no-fallback E2E。**

本批证据：

- 综合只读 readiness：`tmp/outputs/answer-provider-gate-readiness-local-and-production-20260629T024617Z.json` 返回 `status=ready_for_smoke`，但 `ready_scopes=["local-shell"]`，只说明本地 shell 有 `ANTHROPIC_API_KEY=SET`，不代表生产具备生成 provider 条件。
- 生产-only 只读 readiness：`tmp/outputs/answer-provider-gate-readiness-production-only-20260629T024658Z.json` 返回 `status=blocked`、`blockers=["no-provider-api-key-env-set"]`；生产 `answer_runtime.status=fallback_or_unset`，`DEEPSEEK_API_KEY`、`OPENAI_API_KEY`、`ANTHROPIC_API_KEY`、`MOONSHOT_API_KEY` 均为 `UNSET`，Kimi embedding 仍为 `SET` 且仅用于检索向量。

边界：

- 本批没有 provider call、没有生产 env 写入、没有 schema migration、没有生产部署。
- 生产-only readiness 是当前生产判定依据；综合 readiness 只能作为本地 smoke 前置条件观察，不能覆盖生产 blocker。
- 如需继续 §4.2 provider smoke，必须明确授权一次外部 provider 调用；通过 smoke 前不得进入真实答案评测、生产 env 写入或 `--require-generated-answer` 生产 E2E。

## 0.3 2026-06-28 Batch 1 执行结论

本批先执行 F2 的低风险门禁面：§4.1 脱敏只读条件检查 + 一次本地 Anthropic provider smoke。结论：

**F2 仍阻塞，不能写生产 `MEDICAL_AUDIT_KB_ANSWER_*`，也不能执行生产 no-fallback E2E。**

新增工具：

- `scripts/audit-answer-provider-gate-readiness.py`：只输出 env var 名称、`SET/UNSET` 状态和非密配置值；不读取或输出实际 key；可本地执行，也可通过 SSH 只读观察生产容器。
- 报告状态 `ready_for_smoke` 只代表具备运行 provider smoke 的前置 env 条件，不代表 provider 已可用。

本批证据：

- 本地只读 readiness：`tmp/outputs/answer-provider-gate-readiness-local-20260628T1235.json`，`status=ready_for_smoke`；本地仅 `ANTHROPIC_API_KEY` 具备 smoke 前置条件；`provider_call_status=not_called`、`secret_values_reported=false`。
- 本地 Anthropic smoke：`tmp/outputs/answer-provider-smoke-anthropic-20260628T1230.json`，`success=false`，错误为 `401 authentication_error: invalid x-api-key`；因此不进入 §4.3 真实答案评测。
- 生产容器只读 readiness：`tmp/outputs/answer-provider-gate-readiness-production-only-20260628T1235.json`，`status=blocked`、`blockers=["no-provider-api-key-env-set"]`；生产 `answer_runtime.status=fallback_or_unset`，`DEEPSEEK_API_KEY`、`OPENAI_API_KEY`、`ANTHROPIC_API_KEY`、`MOONSHOT_API_KEY` 均为 `UNSET`；Kimi embedding 仍为 `SET` 且仅用于检索向量。

边界：

- 本批唯一外部 provider 调用是本地 Anthropic smoke；没有生产 provider 调用、没有生产 env 写入、没有 schema migration、没有生产部署。
- 生产只读 readiness 是 `L3-production-read-only`；Anthropic smoke 是本地 provider preflight，不构成生产能力证明。
- 当前产品表达仍应保持 generate-or-safe-fallback / citation fallback 边界，不能宣称 no-fallback 真实生成已上线。

## 0.4 2026-06-24 验证结论（历史基线）

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

**不能启用 no-fallback 真实生成；产品表达暂为"基于证据检索的引用式回答"或"依据充分时生成、依据不足时安全回退",不得宣称 no-fallback 已上线。**

事实依据：

- 代码仅支持 `anthropic` 和 `openai` 兼容接口两类真实 provider，`fallback` 为默认。
- 2026-06-28 生产容器只读 readiness：`KIMI_API_KEY=SET`，其余答案生成 provider key 与全部 `MEDICAL_AUDIT_KB_ANSWER_*` 均 `UNSET`。
- 2026-06-28 本地 Anthropic smoke：`claude-sonnet-4-5-20250929` 返回 `401 invalid x-api-key`；Kimi 历史常规 chat `401`、Coding endpoint `403 access_terminated_error`。
- 结论：当前没有可迁移到生产的、已验证可用的 chat answer provider。**F2 上线前必须先拿到一个能通过 §4.2 smoke 的 key。**

## 2. Provider 候选与进入条件

| 候选 | 配置 | 现状 | 进入下一步条件 |
| --- | --- | --- | --- |
| Anthropic | `PROVIDER=anthropic` + `ANTHROPIC_API_KEY` | 2026-06-28 本地 smoke 401 | 用**新的有效 key** 跑通 smoke |
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

```bash
python3 scripts/audit-answer-provider-gate-readiness.py \
  --ssh-key /Users/pray/project/medical_audit/ai_video.pem \
  --json-output tmp/outputs/answer-provider-gate-readiness-<date>.json \
  --markdown-output tmp/outputs/answer-provider-gate-readiness-<date>.md
```

生产正式判断建议使用 `--skip-local` 单独观察生产容器，避免本地 key 状态掩盖生产缺口。

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

F2 阻塞在可用凭证。2026-06-28 已确认本地 Anthropic key 无效、生产容器无答案生成 key。需要决策并提供**一个**可用生成 provider key（写入服务端 env，不入 Git）：

1. 选定 provider（Anthropic / OpenAI / Moonshot chat / DeepSeek 等）。
2. 在本地或服务端配置对应 `*_API_KEY` env。
3. 跑 §4.2 smoke；通过再跑 §4.3 评测；全过再 §4.4 写生产 + §4.5 no-fallback E2E。
4. 任一闸不过即停、不写生产，保留 citation fallback 为产品边界。
