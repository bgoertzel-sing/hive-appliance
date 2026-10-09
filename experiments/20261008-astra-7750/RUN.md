# Astra 7750 run ledger

## Scope and execution

- Required/runtime model: `openai/gpt-6-astra`, provider `openai`; verified with this session's runtime listing and assistant-history metadata. Sole reviewer, no delegation.
- Pin: `6b750ca53a695d70ba4fd44dd2961389f1690df9`; comparison `2c7e337..6b750ca`, excluding experiments in the patch; nine prior manifests verified separately. Initial/audit/pre-publication fetches confirm unchanged origin/main.
- Source: `/tmp/hive-astra-7750-source`; 163 non-experiment tracked files exported and hash-verified. Historical experiments link used read-only.
- Environment: uid 1001, Python 3.10.12, pytest 9.1.1, build 1.5.0; Linux 7.0.11 x86_64/glibc 2.35; eight reported CPUs. Existing local wheels, Python socket guard, pip no-index and third-party pytest plugin autoload disabled; not an OS network sandbox.
- Repo write/stage/commit scope: `docs/ASTRA_REVIEW_7750.md` and this evidence directory only. Scratch, production and tests untouched. Task explicitly authorizes fast-forward main publication and remote verification.
- Setup: `PYTHONDONTWRITEBYTECODE=1 python3 experiments/20261008-astra-7750/setup7750.py`. Setup only exports/copies and records initial metadata, not tests. commands.sh is the equivalent fresh-namespace execution sequence; runner prevents log overwrite.
- Full pytest suite exactly once: **855 passed in 49.93 s**, runner wall **50.49388527870178 s**, exit 0. No local thread-limit failure.

## Exclusive command records

All rows have separate started/exit JSON and stdout/stderr. Copied dependencies not listed were not separately executed. Never replay this populated directory.

| Run | Exit | Wall seconds | Command evidence |
|---|---:|---:|---|
| pytest | 0 | 50.4939 | [pytest-started.json](pytest-started.json) |
| review7694 | 0 | 11.0994 | [review7694-started.json](review7694-started.json) |
| reset7718 | 0 | 5.9671 | [reset7718-started.json](reset7718-started.json) |
| exact_restore_final7718 | 0 | 0.2180 | [exact_restore_final7718-started.json](exact_restore_final7718-started.json) |
| intent_final7727 | 0 | 4.6427 | [intent_final7727-started.json](intent_final7727-started.json) |
| review7195 | 0 | 1.9781 | [review7195-started.json](review7195-started.json) |
| review7173 | 0 | 2.4286 | [review7173-started.json](review7173-started.json) |
| followup7694 | 0 | 0.9706 | [followup7694-started.json](followup7694-started.json) |
| extra_io7727 | 0 | 1.8277 | [extra_io7727-started.json](extra_io7727-started.json) |
| boundary-and-disk | 0 | 0.1673 | [boundary-and-disk-started.json](boundary-and-disk-started.json) |
| focused7701 | 0 | 0.4691 | [focused7701-started.json](focused7701-started.json) |
| mechanism-probes | 0 | 0.2166 | [mechanism-probes-started.json](mechanism-probes-started.json) |
| probes-final | 0 | 0.7720 | [probes-final-started.json](probes-final-started.json) |
| startup7708 | 0 | 0.5175 | [startup7708-started.json](startup7708-started.json) |
| startup_recovery_final7708 | 0 | 0.4678 | [startup_recovery_final7708-started.json](startup_recovery_final7708-started.json) |
| older-regressions-final | 0 | 0.3180 | [older-regressions-final-started.json](older-regressions-final-started.json) |
| independent-final | 0 | 0.3669 | [independent-final-started.json](independent-final-started.json) |
| clearance7701 | 0 | 1.7754 | [clearance7701-started.json](clearance7701-started.json) |
| intent7734 | 0 | 8.0652 | [intent7734-started.json](intent7734-started.json) |
| new-cases | 0 | 0.3671 | [new-cases-started.json](new-cases-started.json) |
| semantic-7133 | 1 | 6.4067 | [semantic-7133-started.json](semantic-7133-started.json) |
| marker7701 | 0 | 0.3161 | [marker7701-started.json](marker7701-started.json) |
| recovery7708 | 1 | 0.3698 | [recovery7708-started.json](recovery7708-started.json) |
| metadata7734 | 0 | 0.2653 | [metadata7734-started.json](metadata7734-started.json) |
| focused7741 | 0 | 1.0693 | [focused7741-started.json](focused7741-started.json) |
| focused7750 | 0 | 2.3770 | [focused7750-started.json](focused7750-started.json) |
| recovery-final7750 | 0 | 0.2656 | [recovery-final7750-started.json](recovery-final7750-started.json) |
| audit7750 | 0 | 0.2153 | [audit7750-started.json](audit7750-started.json) |
| verify_sources7734 | 0 | 1.1245 | [verify_sources7734-started.json](verify_sources7734-started.json) |
| static7734 | 0 | 0.4665 | [static7734-started.json](static7734-started.json) |
| namespace-scope7750 | 1 | 0.2171 | [namespace-scope7750-started.json](namespace-scope7750-started.json) |
| audit7750-final | 0 | 0.1657 | [audit7750-final-started.json](audit7750-final-started.json) |
| namespace-scope7750-final | 0 | 0.2660 | [namespace-scope7750-final-started.json](namespace-scope7750-final-started.json) |
| finalize-special-files | 0 | 0.3166 | [finalize-special-files-started.json](finalize-special-files-started.json) |
| prepublish7750 | 0 required by final verifier | see exit JSON | [prepublish7750-started.json](prepublish7750-started.json) |
| secret-scan | 0 required by final verifier | see exit JSON | [secret-scan-started.json](secret-scan-started.json) |

Total after final fetch/scan: **36 execution ledgers**. Final scan follows final narrative/verifier/provenance. Read-only manifest verification does not create another ledger or write files.

## Outcomes

- Reset: 208 interruptions / 104 caught-error recoveries; 188 fenced, 12 healthy held-new-pair, eight old-pair pre-confirmation restarts; zero discarded live replay.
- Markers/recovery: 42 controls, 72 clearance interruptions, 96 retry/live-error cases. 52 supplementary I/O boundaries plus four anchor open/read faults.
- Current intent: 51/50-call fresh/existing traces, 404 syscall injections plus eight helper boundaries = 412; four compound failures, mode-000 repair and original classification probes pass.
- 7741: 12 classification controls, seven race/fstat/flag controls, 45/45 applicable strict-check cases, six audit presence_error boundaries; original dangling-anchor overwrite closed.
- New: 32 nonregular configurations with two starts and explicit clear/reset, 40 reader errors, eight read swaps, 15 runtime type controls, three FIFO-blocking process witnesses, five directory-symlink controls and zero archive reads during startup/replay/verify/reissue.
- OPEN Medium: runtime FIFO verify waits in open before fstat; regular-to-FIFO startup journal/anchor races likewise block. OPEN Low: directory journal append refuses but remains healthy.
- Three deliberate concurrent namespace races demonstrate excluded scope, not protected-single-writer approval.
- 1,440 supersession schedules / 15,840 prefixes; 144 hold/rebind schedules / 1,152 checks. Exact reset/reissue and earlier journal regressions pass after I/O hook adaptation.
- Nine prior manifests: 315 / 351 / 355 / 829 / 1,189 / 2,221 / 3,913 / 5,821 / 6,131 artifact hashes verified, 7669 through 7741.

## Nonzero results and corrections

`semantic-7133` exit 1 repeats three known obsolete automatic-closure expectations. Current format 3072/3072, prior format 3072/3072, legacy 384/384 and ownership lifecycle controls pass.

`recovery7708` exit 1 uses a stale builtin-open fault injection. Its unreadable subgroup fails because it no longer intercepts reducer I/O. `recovery-final7750` changes only that hook to os.open and fixture/output namespaces; all four groups pass. Original files/logs retained.

`namespace-scope7750` exit 1 retargets the directory at pending-open: the following commit correctly sees different bytes and fences, disproving the harness's initial assumed success. Final version retargets at commit-open after copying matching pending bytes; it records durable success to the detached directory and held replay through the new target. This requires a concurrent namespace writer and is outside accepted deployment scope. Original failed execution retained.

`audit7750-final` corrects the call-graph root from a nonexistent guessed replay name to `_replay_journal`; both audits retained. One preliminary repository-root invocation failed to import runner before any witness execution; rerun from the evidence cwd generated its first exclusive ledger. No full-suite rerun or output-log overwriting.

## Provenance and integrity

Inherited Python scripts, dependency scripts and final corrections have source/adapted hashes and complete diffs in copy-provenance.json/adaptation-7750.diff. New witnesses use the retained definition harnesses, whose copies are included. Model/provider verified for this exact child, not inferred from its parent.

14 FIFO fixture entries are serialized into special-fixtures.json then unlinked because Git cannot store FIFOs. 39 intentional symlinks remain and their literal targets are inventoried. SHA256SUMS covers all delivered regular evidence/report bytes and literal symlink-target bytes, excluding itself. verify_evidence.py is read-only and checks full inventory and semantic results. Secret scan is a high-signal credential-pattern scan, not a proof against arbitrary encoded secrets; it does not follow symlinks. Commit/remote hashes are delivered after publication, not embedded recursively in their own commit.
