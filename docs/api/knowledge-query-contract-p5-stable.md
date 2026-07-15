---
title: "Knowledge Query Contract P5 Stable"
project: "medical_audit"
status: "stable"
created_at: "2026-07-04T13:45:00+08:00"
evidence_grade: "L1-local-contract-freeze"
provider_call: false
database_write: false
index_activation: false
production_probe: false
updated_at: "2026-07-15T14:33:00+08:00"
---

# Knowledge Query Contract P5 Stable

## Decision

Freeze `knowledge-query-contract-v1` as the frontend-backend boundary for the current frontend refactor.

The machine-readable contract is `docs/api/knowledge-query-contract-v1.json`. Frontend refactor work should treat that file as the source of record for `/query`, `/query/logs`, source-collection scoping, nullable history IDs, and typed query states.

## Contract Surface

| Surface | Frozen rule |
| --- | --- |
| Frontend query path | `POST /api/v1/query` |
| Backend query path | `POST /query` |
| Frontend logs path | `GET /api/v1/query/logs?limit=8` by default；必须发送 `X-User-Id` |
| Backend logs path | `GET /query/logs`, `limit=1..100`, backend default `20`；仅返回当前 owner 的记录 |
| History-to-task path | `POST /api/v1/query/logs/{query_log_id}/review-task` -> `POST /query/logs/{query_log_id}/review-task` |
| History-to-task gate | 当前 owner 的历史、显式可见项目、`create_review_task` 权限；外部记录按 `404` 隐藏 |
| Required request field | `question` |
| Optional request fields | `top_k`, `source_collections`, `years`, `regions`, `document_types`, `business_topics`, `topic`, `title_only`, `agent` |
| Required response fields | `question`, `answer`, `confidence`, `fallback_used`, `effective_source_collections`, `basis_groups`, `citations`, `personal_upload_matches`, `query_log_index`, `query_log_id`, `agent_invocation_id` |
| Nullable response fields | `query_log_id`, `agent_invocation_id` |
| Frontend source scope | Render `effective_source_collections`, not only requested `source_collections` |
| Evidence source of record | `citations[].source_collection` and `basis_groups[].items[].source_collection` |

## Source Collections

Medical second-level libraries:

- `medical-insurance-catalog`
- `medical-insurance-laws`
- `risk-negative-list`
- `supervision-rules-knowledge`

Explicit-only personal collection:

- `personal-materials`

Default member effective scope excludes `personal-materials`.

## Typed Query States

| HTTP status | Detail prefix | Frontend code |
| --- | --- | --- |
| `400` | `unknown topic` | `unknown-topic` |
| `403` | `source collection access denied` | `source-collection-denied` |
| `404` | `no cited evidence found` | `no-cited-evidence` |
| `409` | `search engine is not initialized` | `search-engine-not-initialized` |

## Frontend Refactor Rules

- Keep `query_log_id` nullable. A `null` value is valid in no-history mode or when history persistence is unavailable.
- Keep `agent_invocation_id` nullable. It should not be treated as required for ordinary knowledge queries.
- Do not infer actual retrieval scope from the user's requested filters. The UI should display `effective_source_collections`.
- Preview links should continue to derive from citation or basis `chunk_id`.
- Chat transfer should preserve selected source scope and user-entered filters.
- Fallback display should be derived from `fallback_used`, but this does not prove answer-provider execution.
- Query history reads must include the authenticated `X-User-Id`; anonymous reads return `401`, and records are owner-scoped.
- History-to-task must require an explicit visible project selection. Its deterministic ID derives from the canonical persisted `query_log_id`, so equivalent UUID representations cannot create duplicate tasks.
- The mutation requires persistent project-membership and review-task stores, writes one durable review task plus audit intent/terminal evidence, and never calls the answer provider. An in-memory store or missing persistent-write capability returns `503`. Frontend success must continue to display `audit.status=degraded|local-only` instead of claiming complete audit readiness.
- `GET /projects.store` reports read readiness separately from `persistent_writes_ready` (project/member mutations) and `history_review_task_writes_ready` (project membership plus review-task persistence). The history UI requires both `ready=true` and its operation-specific capability before enabling submit.
- The created task must remain exportable as JSON, Markdown, and DOCX through the existing review-task export surface.

## Evidence Boundary

This is a local contract freeze. It is supported by source review and local contract tests only.

It does not prove live backend write-path behavior, production behavior, answer-provider behavior, deployment readiness, or remote index state.
