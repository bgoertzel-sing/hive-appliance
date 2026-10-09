# Astra 7701 run

Status: REVIEW COMPLETE — production ownerless hold/rebind gate NOT APPROVED.
Reviewed pin: 865fd633bc53561aea140dc3f43fee72b8fd61ee; parent 5535545368e1577a5eaed0b681b9cb6334915fff.
Reviewer: sole openai/gpt-6-astra, verified at start and near completion.
Session: agent:main:subagent:f4330ac2-ada4-43a1-983e-1682d71d5cd1.
No reviewer delegation, fallback, continuation or provider interruption.

## Results

- Full suite EXACTLY ONCE: 795 passed in 48.55 s; runner wall 49.0328907967 s.
- Primary initial 10/16; six API-shape adaptation failures later completed in retained-retry7701.json.
- Focused retained initial 7/8; final legacy/default group passed in legacy-final7701.json.
- First retry stopped with definition-loader KeyError; next completed all six primary groups but legacy result serialization failed; final legacy-only run corrected serialization. Raw nonzero exits/logs retained. No suite or completed primary group rerun.
- New focused groups 5/5; creation 48 injections/12 operations, clearance 64 injections/16 operations plus successes; three legacy-marker bypass witnesses and one valid control.
- Near 63 MiB: 81.1 ms median verify; 179.4/164.6 ms two-record rebinds. Warm-cache bounded measurements, no universal latency guarantee.
- 1,440 owned supersession schedules/15,840 states; 144 hold/rebind schedules/1,152 event-prefix checks.
- Current/prior sweeps 3,072 each; legacy fail-closed 384; original witnesses 2; retained lifecycle controls pass.
- semantic_7133 exits 1 for its three retained obsolete automatic-closure expectations. Not a pytest failure; not relabeled success.
- Static verification: exit 0. All 151 tracked non-experiment files unchanged/pinned; clean detached source.
- Prior manifests: 7669=315, 7678=351, 7694=355 artifact/report hashes verified.
- Author's claimed docs-only post-test edit: pre-doc tested tree unavailable; cannot confirm an empty non-doc diff against an unidentified tree. Final reviewed tree independently tested once.

## Findings

CLOSED prior Medium: F-applied-without-durable-commit; F-journal-rollback-anchor (single-file restore).
CLOSED prior Low: F-runtime-integrity-overclaim.
OPEN Medium: F-startup-identity-adoption (explicit required crash-fencing contract; no stale rebind demonstrated in header-only adoption).
OPEN Medium: F-legacy-marker-startup-bypass (durable applied live, ordinary restart fences/holds).
OPEN Low: F-joint-rollback-doc-scope (paired rollback limitation needs explicit documentation).

## Publication

Authorized scope: docs/ASTRA_REVIEW_7701.md and experiments/20261008-astra-7701/ only.
Remote: https://github.com/bgoertzel-sing/hive-appliance.git; branch main; fast-forward-only.
Fetches before publication found origin/main unchanged at 865fd63.
No source/test/old-evidence/scratch edits, remote/paid compute or deployment.
Manifest includes report; staged index bytes credential-pattern/scope checked.
Post-push verification is written outside the manifest to /tmp/hive-astra-7701/postpush-verification.json. This prepublication record does not claim a future push already succeeded.
