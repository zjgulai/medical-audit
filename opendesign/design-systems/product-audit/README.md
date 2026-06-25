---
title: AuditScope Product Design System
doc_type: other
module: opendesign
topic: product-audit-design-system
status: stable
created: 2026-06-05
updated: 2026-06-05
owner: self
source: human+ai
---

# AuditScope Product Design System

This design system is extracted from the current `medical_audit` codebase and refined for a serious medical-insurance audit product. It is the canonical OpenDesign anchor for future UI work in this repository.

## Sources Consulted

- `src/medical_audit_kb/api/static/app.css`
- `src/medical_audit_kb/api/templates/chat.html`
- `src/medical_audit_kb/api/templates/query.html`
- `src/medical_audit_kb/api/templates/index_admin.html`
- `tests/knowledge_query/test_pages.py`

## Direction

AuditScope should feel like a regulated evidence-control surface, not a generic chat demo. The interface uses quiet Apple-grade typography, low-saturation medical audit colors, precise borders, tabular metadata, and explicit review gates.

## Core Product Principles

- Evidence precedes conclusion.
- Original-source preview is a first-class action.
- AI output is always framed as audit clue and review draft, never final finding.
- Operational pages must show version, backend, evaluation, and reload state without decorative noise.

## Files

- `tokens/colors_and_type.css`: canonical color and typography tokens.
- `brand/voice-and-tone.md`: copywriting and interaction language rules.
- `ui-kit-auditscope/index.html`: high-fidelity static reference of the intended surface.
