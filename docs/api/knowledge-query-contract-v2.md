---
title: "Knowledge Query Contract V2"
project: "medical_audit"
created_at: "2026-07-05T15:21:56+08:00"
status: "draft"
evidence_grade: "L1-local-contract"
provider_call: false
database_write: false
index_activation: false
production_probe: false
frontend_business_change: false
---

# Knowledge Query Contract V2

`knowledge-query-contract-v2` is the local API contract for P6 source collection expansion. It lets the backend and frontend type system name the P6A/P6B/P6C/P6E product collections plus `personal-materials`.

This file does not claim that every collection has active DB rows or an activated index. Runtime availability still depends on the later candidate write, evaluation, activation, and read-only verification gates.

## Included Collections

- P6A medical current libraries: 4 collections.
- P6B policy libraries: 6 collections.
- P6C management libraries: 8 collections.
- P6E other libraries: 6 collections.
- Personal materials: explicit user-scoped collection.

## Excluded Collections

`other-unclassified` remains a P6D manual classification pool. It must be reclassified into an included collection, excluded, or deferred before product query exposure.

## Response Additions

The `/query` response must include:

- `contract_version`
- `effective_source_collections`
- `generation_status`: `not_requested`, `generated`, or `retrieval_fallback`
- `generation_failure_code`: a sanitized reason code or `null`; never a provider response body

These fields make effective backend filtering and generation fallback state visible to the frontend
and test suite without exposing provider credentials or raw provider responses.
