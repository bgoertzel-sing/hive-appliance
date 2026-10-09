# Astra 7694 run

Status: REVIEW COMPLETE — production ownerless hold/rebind gate NOT APPROVED.
Reviewed pin: cf6a0601ddc03dcd87daab7f982cb97361ac7ee8 (parent d1239f9).
Sole reviewer: openai/gpt-6-astra, verified at beginning and near completion.
Sessions: agent:main:subagent:ce379868-8734-49fc-b8b2-9b17659d49ef, continued by agent:main:subagent:58d4840d-3ff6-4ae5-afbe-193491620461.
Earlier session interruption: provider content-refusal on one large embedded script, NOT fallback/delegation. Completed suite/harnesses were not repeated.

## Results

- Full pytest suite EXACTLY ONCE: 785 passed in 47.86s; exit 0; runner wall 48.4249176979s.
- Primary review7694: 16/16 groups.
- Focused followup7694: initially 11/11, extended by clearance7694 to 12/12. Followup wall 0.8685853481s; clearance wall 0.3155791760s.
- Static first attempt exit 1: incomplete changed-source archive (not product/test failure). Archive completed from pinned source; static7694-final exit 0, wall 0.6694025993s. Both attempts retained.
- 149 tracked non-experiment files byte-identical before/after/pinned, clean detached source.
- 7669 and 7678 prior manifests: 315 and 351 artifact/report hashes verified.
- 1440 owned supersession and 144 hold/rebind schedules, retained semantic sweeps and exact witness groups pass.
- semantic_7133 retains its known exit 1 for three obsolete automatic-closure expectations; fail-closed sweeps pass. This is not counted as a pytest failure or relabeled a pass.
- CLOSED Medium: F-abort-tail, F-journal-refused-compound, F-abort-order-scope.
- OPEN Medium: F-applied-without-durable-commit; F-journal-rollback-anchor (qualified old-journal restore).
- OPEN Low: F-runtime-integrity-overclaim.

## Publication

Authorized scope: docs/ASTRA_REVIEW_7694.md and experiments/20261008-astra-7694/ only.
Remote: https://github.com/bgoertzel-sing/hive-appliance.git; branch main; fast-forward only.
No production/test edits, old-evidence edits, scratch changes, paid/remote compute or deployment.
Manifest covers published artifacts and report; verification is read-only.
Post-push local/fetched-origin equality is recorded in /tmp/hive-astra-7694/postpush-verification.json outside the published manifest, avoiding self-reference. This prepublication RUN record does not itself claim that the future push already succeeded.
