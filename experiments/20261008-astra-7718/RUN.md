# Astra 7718 execution ledger

- Date: 2026-10-08 America/Vancouver (UTC timestamps are next day).
- Question: does target reset safely discard restored operator decisions across success, process/storage failure and subsequent replay?
- Source: clean detached `0ec1a2dc9b56b8011903180f07f94cd1f3f3d39f`; origin unchanged after fetch.
- Reviewer: sole independently verified `openai/gpt-6-astra`; no delegation.
- Skills applied: repository-operations and experiment-ledger. Explicit user authorization covers publication on main; no unrelated project/memory edits.
- Verdict: **NOT APPROVED**. Successful reset and clean-prefix docs corrected; early interrupted reset and stale live pending after OSError revive old authorization.
- Full pytest: exactly once, **813 passed in 52.16s**, wall 52.6947s.
- Environment/offline controls: see environment.json, offline-verification.json, guard/, build-prerequisites.json.
- Historical harness controls deliberately include defect witnesses. Success of such a probe establishes reproduction, not safety.

## Execution records

| Run | Exit | Wall seconds |
|---|---:|---:|
| boundary-and-disk | 0 | 0.1653 |
| clearance7701 | 0 | 2.2346 |
| exact-restore-final7718 | 0 | 0.2658 |
| exact-restore7718 | 1 | 0.2654 |
| focused7701 | 0 | 0.7721 |
| followup7694 | 0 | 1.8839 |
| independent | 0 | 0.3157 |
| marker7701 | 0 | 0.3703 |
| mechanism-probes | 0 | 0.2654 |
| new-cases | 0 | 0.4666 |
| older-regressions | 0 | 0.2655 |
| probes | 0 | 0.6172 |
| pytest | 0 | 52.6947 |
| recovery7708 | 0 | 0.5702 |
| reset7718 | 0 | 3.3319 |
| review7173 | 0 | 2.7416 |
| review7195 | 0 | 1.9248 |
| review7694 | 0 | 12.5750 |
| semantic-7133 | 1 | 7.2006 |
| startup7708 | 0 | 0.9758 |
| startup_recovery_final7708 | 0 | 0.7252 |
| static7718 | 0 | 12.6963 |

## Nonzero accounting

- semantic-7133: three obsolete automatic-closure expectations; separate current/prior/legacy sweeps pass.
- exact-restore7718: inherited CRITICAL root threshold suppressed expected WARNING. Storage assertions before capture passed. exact-restore-final7718 explicitly sets reducer logger level and uses a new fixture; passes. Both logs and adaptation diff retained.
- No full-suite rerun.

## Measurements and limitations

- Supersession/hold-rebind: 1,440/144 schedules, 15,840/1,152 event-prefix checks.
- Primary/focused journal groups: 16/16 and 8/8.
- Reset faults: 176 injections; 50 healthy old authorization replays, 114 fenced restarts, 12 healthy held restarts. Healthy-input caught OSError: 40/40 live stale-pending replays.
- Exact successful restore: discarded p held on two restarts; reissued p persists on two restarts.
- Storage faults simulate syscall-visible exceptions, not physical power loss. No concurrency, hardware durability or performance benchmark claimed.
- Accepted architecture limits and precise production gate blockers are in the report.
- Source/prior manifests verified; only report/new evidence published. Post-push result kept outside manifest to avoid circular hash claims.
