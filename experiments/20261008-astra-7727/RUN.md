# Astra 7727 execution ledger

Status: completed; production gate **NOT APPROVED** (one new Medium durability-status finding).

- Reviewer: `openai/gpt-6-astra`, verified provider/model metadata.
- Pin: `7ce5cd5c2c3289ee1ce9f50c2683854e038df0d0`; diff `30e3d39..7ce5cd5`.
- Source: exact Git-blob export `/tmp/hive-astra-7727-source`; 157 non-experiment files verified before/after, no source mutations. Historical evidence read-only link.
- Purpose: close 7718 reset interruption/live-error defects; qualify intent startup, recovery, retry, durability reporting and retained storage/semantic behavior.
- Execution: local CPU, Python socket guard, PIP_NO_INDEX, existing hashed wheels, no paid/remote compute. No environment dump.
- Commands: [commands.sh](commands.sh). Each row has matching started/exit JSON and stdout/stderr.
- UTC window: 2026-10-09T03:58:56.692942+00:00 → 2026-10-09T04:03:08.523170+00:00.

## Executions

| Run | Exit | Wall seconds |
|---|---:|---:|
| pytest | 0 | 52.1323 |
| review7694 | 0 | 11.0492 |
| followup7694 | 0 | 0.9720 |
| focused7701 | 0 | 0.4663 |
| startup7708 | 0 | 0.4663 |
| startup_recovery_final7708 | 0 | 0.4667 |
| clearance7701 | 0 | 1.4226 |
| review7195 | 0 | 1.8780 |
| marker7701 | 0 | 0.2150 |
| recovery7708 | 0 | 0.3170 |
| review7173 | 0 | 2.2264 |
| boundary-and-disk | 0 | 0.1646 |
| mechanism-probes | 0 | 0.2652 |
| probes | 0 | 0.6172 |
| older-regressions | 0 | 0.3156 |
| independent | 0 | 0.3156 |
| new-cases | 0 | 0.4666 |
| semantic-7133 | 1 | 7.0083 |
| reset7718 | 0 | 4.5881 |
| exact_restore_final7718 | 0 | 0.2685 |
| intent7727 | 1 | 0.8256 |
| intent-final7727 | 0 | 3.6324 |
| extra-io7727 | 0 | 1.2205 |
| static7727 | 0 | 0.4666 |

## Results and interpretation

Full suite exactly once: **817 passed in 51.57 s**. Retained schedules: 1,440 supersession / 15,840 prefix checks; 144 hold/rebind / 1,152 checks. Primary 16/16, focused 8/8.

Reset matrix: 24/28 storage operations, 96/112 injections = 208; 104 error recoveries carry zero rebinds. 188 fenced restarts, 12 new-pair held restarts, eight unchanged-old-pair restarts before intent helper completion. Additional: 42 intent controls, 48 same-process reset retries, 48 direct live-error replays, 72 intent-clearance interruptions, 48 stat/close/directory-open errors, four anchor open/read errors. All corrected invariant groups pass.

Two independent witnesses show `intent_durable` is actually namespace existence: never-fsync'd empty marker and fsync-error plus unlink-cleanup-error. A separately labeled model removes the unfsync'd entry to represent an allowed power-loss outcome. The live reducer remains safely fenced; the recovery message's durability promise is unsupported. This is a review finding, not an assertion that the ordinary-startup marker check fails.

Nonzero runs retained: semantic-7133 has three previously documented obsolete expectations. Initial intent7727 had review-harness inspection/wrapper defects; intent-final7727 corrects these in a separate script/diff and fresh fixture namespace. The initial unreadable fixture was chmod'd readable only after failure for hashing; successful final controls genuinely use mode 000. No full-suite rerun, production edit, raw-log overwrite, commit or push.

Reproduction requires fresh evidence and temporary directories. Source and previous manifests verified; adaptation diffs preserve retained-harness changes. Hardware power-loss, adversarial chain rewriting, concurrent writers, snapshot recovery and performance remeasurement are outside this evidence.
