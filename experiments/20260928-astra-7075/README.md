# Astra review 7075 evidence

Task: independent review of N4/N5/H2 at 5de0d533a9070585c8c87129ba4c2598e3b7ac8b,
including production fix d6ab556. No production edits or publication.

Acceptance: original 7024 harnesses, independent semantic ordering/snapshot/
lifecycle probes, earlier regressions, one full pytest run, and findings-first
report at ../../docs/ASTRA_REVIEW_7075.md. Preserve actual child exit codes.
Next command: /usr/bin/python3 run_review.py.
Evidence: this directory; parent packaging smoke is in the separate sibling
20260928-astra-7075-packaging directory and must be labelled parent-verified.

Rules consulted: research rules 2 (explicit semantic invariants), 4 (independent
review), 5 (pinned reproducible results), 7 (local/hive and snapshot boundaries).
Requested/selected review model: gpt-6-astra; parent reports session_status
openai/gpt-6-astra. This is parent-provided routing provenance, not a new
runtime measurement by this reviewer.

Status: review complete. Report: ../../docs/ASTRA_REVIEW_7075.md.
All 402 original schedules pass; new-format snapshots 1920/1920 pass.
Authentic legacy restore violates ordered semantics in 96/384 cases, including
24 premature completions. Lifecycle identity limitations reproduce at baseline.
N4 named timing defect CLOSED; N5 and H2 PARTIAL; new N6 OPEN, pre-existing.
Full pytest invoked once: 655 passed, one offline packaging dependency failure,
actual exit 1. Parent packaging smoke passes separately. Read each *-exit.json:
launcher success is not child success. No production changes or push.
Next action: parent publication/integration; repair legacy migration and durable
plan ownership before lifting the gated live-repair/replay restriction.
