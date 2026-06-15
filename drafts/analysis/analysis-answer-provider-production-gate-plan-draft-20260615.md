---
title: 真实生成模型 Provider 生产门禁计划
doc_type: analysis
module: knowledge-query-engine
topic: answer-provider-production-gate
status: draft
created: 2026-06-15
updated: 2026-06-15
owner: self
source: human+ai
---

# 真实生成模型 Provider 生产门禁计划

## 1. 当前结论

当前不能启用 no-fallback 真实生成门禁。

事实依据：

- 代码层只支持两类真实答案生成 provider：`anthropic` 和 `openai` 兼容接口；`fallback` 仍是默认路径。
- 本地环境只读检查结果：`ANTHROPIC_API_KEY=SET`，`KIMI_API_KEY`、`MOONSHOT_API_KEY`、`OPENAI_API_KEY`、`DEEPSEEK_API_KEY` 和全部 `MEDICAL_AUDIT_KB_ANSWER_*` 均为 `UNSET`。
- 生产容器只读检查结果：`KIMI_API_KEY=SET`，`MOONSHOT_API_KEY`、`OPENAI_API_KEY`、`ANTHROPIC_API_KEY`、`DEEPSEEK_API_KEY` 和全部 `MEDICAL_AUDIT_KB_ANSWER_*` 均为 `UNSET`。
- 既有记录显示：生产 `KIMI_API_KEY` 对常规 Moonshot chat endpoint 返回 `401 Invalid Authentication`，对 Kimi Coding endpoint 返回 `403 access_terminated_error`；本地 `ANTHROPIC_API_KEY` 历史 smoke 返回 `401 invalid x-api-key`。
- 因此，目前没有一个已验证可用、可迁移到生产的真实 chat answer provider。

## 2. Provider 候选

| 候选 | 配置形态 | 当前状态 | 进入下一步条件 |
| --- | --- | --- | --- |
| Anthropic | `MEDICAL_AUDIT_KB_ANSWER_PROVIDER=anthropic` | 代码原生支持；本地存在 key，但历史 smoke 为 `401` | 使用当前或新 key 跑通 `answer-provider-smoke` |
| OpenAI | `MEDICAL_AUDIT_KB_ANSWER_PROVIDER=openai` + OpenAI base URL | 代码原生支持；当前本地和生产均无 `OPENAI_API_KEY` | 提供服务端 key，并跑通 smoke |
| Moonshot/Kimi Chat | `openai` 兼容接口 + Moonshot base URL | 生产只有 `KIMI_API_KEY`；历史常规 chat endpoint 认证失败 | 提供可用于普通 chat completion 的 key，不能复用已失败的 Coding key 作为通过依据 |
| DeepSeek 或其他兼容接口 | `openai` 兼容接口 + 对应 base URL | 当前无 key，无验证记录 | 提供 key、base URL、model 后跑通 smoke |

反面论点：也可以继续保留 citation-backed fallback 作为产品能力边界，不启用真实生成模型。这条路径更稳，但产品表达必须降级为“基于证据检索的引用式回答”，不能宣称“AI 生成审计结论”。

## 3. 密钥边界

硬性边界：

- 不把真实 key 写入 Git、PR、Markdown、日志、前端代码、浏览器存储、`tmp/outputs` 报告或 shell 历史。
- 文档、命令和配置示例只允许出现 env var 名称，不允许出现 key 值。
- `MEDICAL_AUDIT_KB_ANSWER_API_KEY_ENV` 的值必须是环境变量名，例如 `ANTHROPIC_API_KEY`，不能是密钥本身。
- 生产 key 只允许进入远端服务端 env 文件或未来 secret 管理设施。
- 嵌入模型 key 和答案生成 key 分开管理；除非对应 key 通过普通 chat smoke，否则不得把生产 `KIMI_API_KEY` 当作答案生成 key。

## 4. 验证顺序

### 4.1 只读环境检查

目标：确认本地和生产是否存在候选 key，不读取、不打印 key 值。

输出要求：

- 只输出 `SET/UNSET`。
- 检查项包括候选 provider key 和全部 `MEDICAL_AUDIT_KB_ANSWER_*`。
- 检查结果只能作为“是否具备测试条件”的依据，不能作为 provider 可用依据。

### 4.2 单 provider 预检

每个候选 provider 必须先跑：

```bash
uv run medical-audit-kb answer-provider-smoke \
  --answer-provider anthropic \
  --answer-model replace-with-verified-model \
  --answer-api-key-env ANTHROPIC_API_KEY \
  --answer-max-output-tokens 300 \
  --answer-temperature 0 \
  --output drafts/analysis/knowledge-query-answer-provider-smoke-anthropic-draft-20260615.md \
  --json-output tmp/outputs/knowledge-query-answer-provider-smoke-anthropic-20260615.json
```

OpenAI 兼容 provider 只替换 provider、model、base URL 和 key env：

```bash
uv run medical-audit-kb answer-provider-smoke \
  --answer-provider openai \
  --answer-model replace-with-verified-model \
  --answer-api-key-env PROVIDER_API_KEY_ENV \
  --answer-base-url https://replace-with-provider-base-url/v1 \
  --answer-max-output-tokens 300 \
  --answer-temperature 0 \
  --output drafts/analysis/knowledge-query-answer-provider-smoke-openai-compatible-draft-20260615.md \
  --json-output tmp/outputs/knowledge-query-answer-provider-smoke-openai-compatible-20260615.json
```

通过标准：

- CLI exit code 为 `0`。
- JSON 中 `success=true`。
- `citation_marker_present=true`。
- `required_term_present=true`。

### 4.3 真实答案评测

只有首个通过 smoke 的 provider 才进入完整评测：

```bash
uv run medical-audit-kb evaluate-answers \
  --answer-provider replace-with-provider \
  --answer-model replace-with-verified-model \
  --answer-api-key-env PROVIDER_API_KEY_ENV \
  --answer-base-url https://replace-with-provider-base-url/v1 \
  --answer-max-output-tokens 600 \
  --answer-temperature 0 \
  --output drafts/analysis/knowledge-query-answer-evaluation-provider-draft-20260615.md \
  --json-output tmp/outputs/knowledge-query-answer-evaluation-provider-20260615.json
```

通过标准：

- 不使用 `--allow-answer-fallback`。
- `generation_success_rate=100%`。
- `fallback_rate=0%`。
- `pass_rate=100%`。
- `citation_marker_rate=100%`。
- `unsupported_claim_free_rate=100%`。

### 4.4 生产 env 写入与回滚

只有 smoke 和真实答案评测均通过后，才允许写入生产：

1. 备份远端 `configs/deploy/tencent-cloud/medical-audit.env`。
2. 写入 `MEDICAL_AUDIT_KB_ANSWER_PROVIDER`、`MEDICAL_AUDIT_KB_ANSWER_API_KEY_ENV`、`MEDICAL_AUDIT_KB_ANSWER_MODEL`、`MEDICAL_AUDIT_KB_ANSWER_BASE_URL`、`MEDICAL_AUDIT_KB_ANSWER_MAX_OUTPUT_TOKENS` 和 `MEDICAL_AUDIT_KB_ANSWER_TEMPERATURE`。
3. 只重启 `medical_audit_app`。
4. 不修改 `medical_audit_pg`、`medical_audit_pgdata` 或共享 `ai_video_nginx`。

回滚条件：

- app 启动失败。
- 生产 smoke 出现 `fallback_used=true`。
- provider 请求失败、超时或生成质量不达标。

回滚动作：

- 恢复备份 env 或设置 `MEDICAL_AUDIT_KB_ANSWER_PROVIDER=fallback`。
- 只重启 `medical_audit_app`。
- 保留失败报告到 `tmp/outputs/`，并在正式台账中标记未通过。

### 4.5 生产 no-fallback E2E

生产写入 provider env 后必须运行：

```bash
python3 scripts/run-production-e2e-smoke.py \
  --base-url https://audit.lute-tlz-dddd.top \
  --expected-matching-embeddings 49051 \
  --require-generated-answer \
  --report tmp/outputs/production-e2e-smoke-require-generated-answer-20260615.json
```

通过标准：

- `status=pass`。
- `/query` 不返回 fallback answer。
- 引用标记存在。
- 检索 embedding 数量与当前生产激活索引一致。
- TLS、health、search backend、page rendering 和 audit logs permission 均通过。

## 5. 当前执行建议

下一步只做本地 `ANTHROPIC_API_KEY` 的 `answer-provider-smoke`，前提是允许一次外部 provider 调用和可能产生的小额费用。

若 Anthropic 仍为 `401`，立即停止，不进入生产 env 写入；随后要求提供新的可用服务端 chat provider key。

若 Anthropic smoke 通过，再执行完整 `evaluate-answers`。完整评测通过后，才进入生产 env 备份、写入、应用重启和 no-fallback 生产 E2E。
