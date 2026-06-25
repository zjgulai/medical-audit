---
name: product-audit-design-system
description: Use for AuditScope medical insurance audit interfaces, evidence review workflows, knowledge-base query pages, review-task desks, audit logs, and operational consoles that require serious, traceable, professional healthcare-audit UI.
---

# AuditScope Product Design System

Use this system for production-facing医保审计 and knowledge-base evidence workflows.

## Product Tone

- Serious, controlled, and evidence-led.
- Prefer restrained density over decorative storytelling.
- Make every conclusion look conditional until citations and original text are verified.
- Treat blue as operational focus, green as evidence-ready, amber as review-needed, red as blocked or violation risk.

## Visual Rules

- Use the tokens in `tokens/colors_and_type.css`.
- Avoid saturated gradients, floating decorative circles, emoji icons, and casual SaaS illustration patterns.
- Use tabular summaries, compact metadata blocks, and explicit gate labels.
- Keep primary actions short and auditable: 查询依据, 生成可追溯回答, 核验原文, 创建复核任务.
- Evidence cards must expose citation id, chunk id, index key, package key, and original preview entry.

## Interaction Rules

- Every submit action must show busy state and an `aria-live` status.
- Every copy action must provide success/failure feedback.
- Every page should preserve a clear human-review boundary.
- Review or export actions must never imply that the AI output is a final audit conclusion.
