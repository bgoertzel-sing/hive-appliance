# Astra 7708 run

Status: REVIEW COMPLETE — production ownerless hold/rebind recovery gate NOT APPROVED.
Reviewed pin: 8945bdcb06415a11a5647fbb0e4decc59e021784; parent 1a87ae9bcdbb8140ff853f32291e17c9582e09d7; previous code pin 865fd633bc53561aea140dc3f43fee72b8fd61ee.
Reviewer: sole openai/gpt-6-astra; own sessions_list/history verified at start and near completion.
Session: agent:main:subagent:a24f66ce-f5bc-41a4-ae99-568384ca947f.
No delegation, fallback, provider interruption or reviewer continuation.

## Results

- Full suite EXACTLY ONCE: 808 passed in 49.96 s; wall 50.5086772442 s, exit 0.
- Retained primary 16/16; journal 7/8 initially, diagnostic-only legacy/default retry passes.
- Focused 5/5; new recovery 4/4, including a passing assertion of unsafe restore guidance.
- 48 corrected creation injections; 24 fenced cases all recover through explicit clearance/reissue/restart.
- 80 clearance injections include both marker rename/fsync transitions; eight marker startup variants; 12 legacy version/op cases.
- 1,440 owned supersession schedules/15,840 states; 144 hold/rebind schedules/1,152 event-prefix checks.
- Current/prior sweeps 3,072 each; legacy 384; original witnesses 2. semantic_7133 exits 1 on three retained obsolete automatic-closure expectations.
- Startup inherited matrix recreated event timestamps per restart. Supplemental assertion exposed this (exit 1). Corrected matrix retains original stream, uses new fixture paths, reruns affected cases and passes. All initial outputs/failure remain; no suite rerun.
- Permission/EIO on journal/anchor fail closed; leftover nonactive temp/cleared files do not authorize replay.
- Static: all 153 tracked non-experiment files unchanged/pinned, detached source clean. Prior manifests: 315/351/355/829 hashes.
- Author's full-suite run on exact target pin UNVERIFIED: no tied artifact found. Independent run directly covers target.

## Findings

CLOSED prior Medium: F-startup-identity-adoption; F-legacy-marker-startup-bypass.
OPEN Low: F-joint-rollback-doc-scope (warning now correct; suggested clearance no-op on healthy restored pair).
OPEN Low: F-clean-suffix-doc-overclaim (complete-prefix rollback not detected at restart).
Other prior High/Medium/Low scopes retained closed as detailed in report.

## Publication

Only docs/ASTRA_REVIEW_7708.md and experiments/20261008-astra-7708/.
Fetched local/main and origin/main equal reviewed pin before publication. Authorized fast-forward push only.
No source/test/old-evidence/scratch modifications; no paid/remote compute or deployment.
Staged index bytes scope/credential-pattern checked; manifest includes report and every delivered evidence file except SHA256SUMS itself.
Post-push verification lives outside manifest at /tmp/hive-astra-7708/postpush-verification.json; this ledger does not pre-claim a future push.
