---
title: "H1 citation observability next-UAT architecture decision"
doc_type: "analysis-draft"
module: "knowledge-query"
status: superseded
created: "2026-07-22"
updated: 2026-08-13
owner: "self"
source: "repo+official-docs+prior-authorized-live-evidence"
evidence_grade: "L1-L2-local-design-with-historical-L3-L4-inputs"
---

# H1 citation observability next-UAT architecture decision

> 从 `/Users/pray/project/medical_audit_h1_fix_20260721` 原样归并的历史独有草稿；2026-08-13 标记为 `superseded`。当前状态以 [文档索引](../../docs/README.md) 为准。

## Decision

The separately authorized live UAT is complete and failed-stopped on `deepseek_citation_markers_missing_without_claimed_ids`. The exact packet is consumed. This routes the problem to provider/structured-output reliability, not marker parsing or deterministic insertion from global IDs.

The current top-level `citation_ids` list is insufficient for deterministic marker insertion because it does not bind individual claims to individual citations. Automatic insertion is rejected.

Loop 67 implements a local, constructor-only `strict_tool_call` candidate using a claim-level response contract:

```json
{
  "claim_blocks": [
    {
      "text": "医疗机构应核验相关收费依据。",
      "citation_ids": ["C1"]
    }
  ]
}
```

The application validates every block and ID against the current retrieval candidates, rejects empty/uncited/duplicate/unavailable/marker-bearing blocks, and renders markers immediately after each block. This is an L2 local candidate only: production alias/env/catalog/deploy wiring remains unchanged and promotion is not authorized.

## Current verified facts

- Production deployment baseline from Loop 63 is `18d3ff86170558b0ea20eafc1dbd6e4a32c33a28`; it must be reverified at authorization time.
- Current runtime uses ordinary DeepSeek JSON Output through `/chat/completions`, with `response_format={"type":"json_object"}`, an exact example, `max_output_tokens=900`, temperature `0` and thinking disabled.
- JSON Output guarantees JSON syntax, not the custom relation between `answer`, visible markers and `citation_ids`.
- The deployed diagnostics distinguish valid available claimed IDs present versus absent without retaining the rejected answer or the claimed-ID list.
- Run `fa-20260722t063614z-18d3ff86` is consumed and failed-stopped after two calls with zero retry; its authorization cannot be reused.
- Loop 67 local candidate defaults to existing `json` mode. Strict mode requires provider `deepseek`, exact Beta base URL, one forced `submit_cited_answer` tool and local argument validation.

## Architecture matrix

| Lane | Current decision | Reason |
|---|---|---|
| Keep fail-closed and observe the new discriminator | Completed | Live result selected the without-claimed-IDs branch |
| Add more accepted marker punctuation | Rejected | No retained evidence identifies an equivalent rejected form |
| Append global `citation_ids` to provider text | Rejected | Creates unsupported statement-level citation placement |
| Prompt-only wording change | Not sufficient alone | Existing prompt already specifies exact JSON and marker examples |
| Claim-level blocks plus deterministic rendering | Local candidate implemented | Provides explicit claim-to-source mapping and deterministic formatting; still not semantic proof |
| DeepSeek Beta strict tool calls | Local spike complete; promotion blocked | Requires `/beta`, tools/schema, forced tool choice and a different response parser |

## Loop 67 local candidate

- Adds `deepseek_output_mode="strict_tool_call"` only to the provider constructor/from-env API; default remains `json`.
- Rejects strict mode unless provider is `deepseek` and base URL is exactly `https://api.deepseek.com/beta`.
- Sends one strict `submit_cited_answer` function schema with required nested `claim_blocks`, forces that named tool and omits `response_format`.
- Requires exactly one matching tool call and locally validates its JSON arguments even though strict mode validates schema server-side.
- Renders validated marker-free claim text as `text [C1] [C2]`, block by block; it never appends a global citation list to free prose.
- Preserves sanitized strict failure categories through the existing retrieval-fallback/query-audit path.
- Validation: focused RED→GREEN, related `31/31`, full repository Pytest exit `0`, repository Ruff pass and Mypy `104` source files pass.

Official contract references: [DeepSeek Tool Calls](https://api-docs.deepseek.com/guides/tool_calls/), [Chat Completion API](https://api-docs.deepseek.com/api/create-chat-completion/), and [JSON Output](https://api-docs.deepseek.com/guides/json_mode/).

## Future result routing

### Generated result

- Continue the bounded test cases until the four-call ceiling or first failure.
- A full pass may be labeled `L4-authorized-live` only after protected-state comparison also passes.

### `deepseek_citation_markers_missing_without_claimed_ids`

- Keep retrieval fallback.
- Classify as provider/structured-output reliability.
- Consider a local strict-tool-call compatibility spike; do not change production env or provider settings without a new release plan.

### `deepseek_citation_markers_missing_with_claimed_ids`

- Keep retrieval fallback.
- Do not insert markers into the current free text.
- Open a separate claim-level contract design/TDD batch before implementation.

### Any other failure

- Stop at the first failed case.
- Preserve query/audit history and compare the protected-state allowlist.
- Do not automatically retry or widen accepted syntax.

## Exact authorization packet — executed and consumed

Candidate identity was generated and validated locally on 2026-07-22, then explicitly authorized by the owner and executed once. The packet is consumed and must never be reused. The retained text below is historical authorization evidence, not a reusable authorization.

> 明确授权执行 H1 Knowledge live UAT：生产 SHA `18d3ff86170558b0ea20eafc1dbd6e4a32c33a28`，run ID `fa-20260722t063614z-18d3ff86`，使用 `deepseek-v4-pro`，最多 4 次 provider call，每次 `max_output_tokens=900`，禁止重试；允许执行调用前后的只读 readiness、catalog、health、baseline snapshot 和 allowlist comparison；仅允许新增最多 4 条 `query_logs` 及对应 query audit logs；禁止其他 DB、schema、env、runtime、agent、review、document、index 和 deploy 写入；失败立即停止，禁止 DELETE，保留 query/audit history。生产 SHA、模型配置、key SET 状态或 baseline 若发生漂移，必须在 provider call 前失败关闭；本授权不得更换 SHA、run ID、模型或自动重试。

## Pre-call fail-closed checklist

- Exact production deploy SHA equals the authorized 40-hex SHA.
- Run ID matches the established 8-to-32 lowercase hexadecimal suffix contract and has zero pre-existing attributable events.
- `deepseek-v4-pro` catalog configuration is available; model name, output limit, temperature and thinking mode equal the authorized values.
- Key state is reported only as `SET`/not set; no secret value is read or printed.
- App, PostgreSQL, ClamAV, front door and search backend are healthy; matching embedding count does not drift from the accepted baseline.
- Serializable read-only baseline snapshot passes with no concurrent ambiguity.
- Runner is bound to the exact SHA/run/model and enforces four calls maximum, zero retry and stop on first failure.
- Comparator allows only query rows and their matching query audit events; all other protected tables, schema, object ledger and release topology must remain unchanged.

## Evidence labels

- This document: `L1-L2 local design/readiness`.
- Loop 67 strict candidate: `L2 fixture/automated`, not configured, not deployed and not provider-validated.
- Loop 63 deployment: historical `L3 production read-only` evidence.
- Previous provider result: consumed `L4 authorized live`, outcome `failed-stopped`.
- Run ID `fa-20260722t063614z-18d3ff86`: `authorized`, `executed once`, `consumed`.
- Live UAT: `failed-stopped` after two calls with zero retry; failure reason `deepseek_citation_markers_missing_without_claimed_ids`.
- Allowlist comparison: `uat-failed-boundary-pass`; only `query_logs +2` and matching query audit events `+2`, with protected state otherwise unchanged.
