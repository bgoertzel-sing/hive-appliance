# Astra 7741 run ledger

## Scope and execution

- Required and runtime model: `openai/gpt-6-astra`, provider `openai`; verified via sessions_list and sessions_history before review. No delegation.
- Pin: `2c7e337202cbfa19569b344992326a1603d867cd`; requested comparison `48c10cc..2c7e337`. Initial and final fetch confirmed origin/main unchanged.
- Source: `/tmp/hive-astra-7741-source`; 161 non-experiment Git-tracked files exported and hash-verified. Historical experiments link used read-only.
- Environment uid 1001; Python socket guard and local existing wheel inputs; no dependency downloads. Not an OS network sandbox.
- Repo write scope: `docs/ASTRA_REVIEW_7741.md` and this evidence directory only. Scratch, production and tests untouched; no stage/commit/push.
- Setup: `PYTHONDONTWRITEBYTECODE=1 python3 experiments/20261008-astra-7741/setup7741.py`; setup exports/copies only. Then commands.sh primary/journal/retained runs; focused/audit runs separately while reviewing. The final commands.sh is the equivalent full sequence for a fresh namespace.
- Full pytest suite exactly once: **840 passed in 50.37 s**, runner wall **50.90446186065674 s**, exit 0.

## Exclusive command records

All rows have separate started/exit JSON and stdout/stderr. Never replay commands in this populated directory: the runner uses exclusive creation. Copied dependency/legacy harnesses not listed below were not separately executed. Their relevant functions may be exercised by composite harnesses.

| Run | Exit | Wall seconds | Command evidence |
|---|---:|---:|---|
| pytest | 0 | 50.9045 | [pytest-started.json](pytest-started.json) |
| review7195 | 0 | 1.7752 | [review7195-started.json](review7195-started.json) |
| review7173 | 0 | 2.4803 | [review7173-started.json](review7173-started.json) |
| boundary-and-disk | 0 | 0.1657 | [boundary-and-disk-started.json](boundary-and-disk-started.json) |
| mechanism-probes | 0 | 0.2200 | [mechanism-probes-started.json](mechanism-probes-started.json) |
| probes-final | 0 | 0.6194 | [probes-final-started.json](probes-final-started.json) |
| older-regressions-final | 0 | 0.2653 | [older-regressions-final-started.json](older-regressions-final-started.json) |
| independent-final | 0 | 0.3157 | [independent-final-started.json](independent-final-started.json) |
| new-cases | 0 | 0.4160 | [new-cases-started.json](new-cases-started.json) |
| semantic-7133 | 1 | 6.7549 | [semantic-7133-started.json](semantic-7133-started.json) |
| review7694 | 0 | 10.2250 | [review7694-started.json](review7694-started.json) |
| followup7694 | 0 | 0.8682 | [followup7694-started.json](followup7694-started.json) |
| focused7701 | 0 | 0.3657 | [focused7701-started.json](focused7701-started.json) |
| startup7708 | 0 | 0.4666 | [startup7708-started.json](startup7708-started.json) |
| startup_recovery_final7708 | 0 | 0.3667 | [startup_recovery_final7708-started.json](startup_recovery_final7708-started.json) |
| clearance7701 | 0 | 1.1698 | [clearance7701-started.json](clearance7701-started.json) |
| marker7701 | 0 | 0.2651 | [marker7701-started.json](marker7701-started.json) |
| recovery7708 | 0 | 0.3660 | [recovery7708-started.json](recovery7708-started.json) |
| reset7718 | 0 | 4.3363 | [reset7718-started.json](reset7718-started.json) |
| exact_restore_final7718 | 0 | 0.2651 | [exact_restore_final7718-started.json](exact_restore_final7718-started.json) |
| intent_final7727 | 0 | 3.4858 | [intent_final7727-started.json](intent_final7727-started.json) |
| extra_io7727 | 0 | 1.2198 | [extra_io7727-started.json](extra_io7727-started.json) |
| intent7734 | 0 | 7.3104 | [intent7734-started.json](intent7734-started.json) |
| focused7741 | 0 | 1.3225 | [focused7741-started.json](focused7741-started.json) |
| metadata7734 | 0 | 0.2150 | [metadata7734-started.json](metadata7734-started.json) |
| verify_sources7734 | 0 | 0.7739 | [verify_sources7734-started.json](verify_sources7734-started.json) |
| static7734 | 0 | 0.4164 | [static7734-started.json](static7734-started.json) |
| audit7741 | 0 | 0.2152 | [audit7741-started.json](audit7741-started.json) |
| audit7741-final | 0 | 0.2150 | [audit7741-final-started.json](audit7741-final-started.json) |
| secret-scan | 0 required by final verifier | see exit JSON | [secret-scan-started.json](secret-scan-started.json) |

Total after final scan: **30** execution ledgers. Scan is run after this ledger and all narrative files are final; its timing is in its exclusive exit record. Read-only final manifest verification prints to the requester and does not generate another file.

## Outcomes

- Reset: 208 interruptions, 104 caught-error recoveries; 188 fenced restarts, 12 healthy held new-pair restarts, eight unchanged-old-pair pre-confirmation restarts.
- Marker/recovery: 42 marker combinations, 72 clearance interruptions, 96 retry/live-error cases, 48 supplementary I/O boundaries plus four anchor reads.
- Current intent: 48/47-call fresh/existing traces, 380 syscall injections plus eight helper boundaries = 388; four compound failures, non-root mode-000 and original classification witnesses pass. Added fstat accounts for increase from 384.
- Focused 7741: 12 first/confirm/every-call EIO/EACCES classification controls; seven race/fstat/flag-availability probes; 45 strict-check combinations (42 applicable, three clearance anchor-read controls inapplicable by design); six metadata after-return boundaries.
- New real-filesystem dangling-anchor witness: missing journal + dangling .id becomes healthy fresh pair; symlink entry overwritten. No authorization resurrection asserted.
- Metadata: original two false presence/text cases corrected; fence presence_error still missing from audit in all six new compound cases.
- Existing-marker nonregular type rejected; O_NOFOLLOW enforced on Linux. Forced unavailable flag allows same-inode symlink follow, documented portability exclusion.
- 1,440 supersession schedules / 15,840 prefixes and 144 hold/rebind schedules / 1,152 checks pass.
- Exact restore archives byte-for-byte, holds through two restarts, explicit reissue durable through two more.
- Eight prior manifests: 315 / 351 / 355 / 829 / 1,189 / 2,221 / 3,913 / 5,821 artifacts verified (7669 through 7734).

## Nonzero results and corrections

`semantic-7133` exit 1 repeats three known obsolete automatic-closure expectations. Current format 3072/3072, prior ordered format 3072/3072, legacy 384/384 and ownership lifecycle controls pass. These are not new regressions. All other substantive commands pass.

`audit7741-final` corrects only erroneous line numbers in one narrative audit note (failure audit is at 1208–1212, fence presence_error at 1207). Both original and corrected scripts/output remain. Preliminary shell inspection asked for suite-exit records before completion and returned missing-file errors; no test rerun or evidence overwrite resulted. No harness-failure recovery was needed.

## Provenance and integrity

59 inherited Python scripts (including dependencies and guard) have original/adapted SHA-256 hashes and complete unified diffs. setup7741.py and focused7741.py are new; legacy setup scripts were not copied. The final verifier is adapted from 7734 and included in provenance. The model JSON preserves the earlier shape with this verified runtime session identity.

SHA256SUMS inventories all regular evidence files plus the report except itself, including generated journal fixtures, command outputs, source snapshots, prose and scripts. verify_evidence.py reads only. The secret scan is a high-signal pattern scan, not proof against arbitrary encoded credentials. All report/evidence content present before the final scan is included; generated scan result and manifest are excluded by its explicit scope.
