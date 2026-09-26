# Astra re-review 6949 — structural fixes at bc8e5e0

**Actual model:** `openai-api/gpt-6-astra`, original reviewer session `029ec2d2-6c66-4848-9b94-23b77b68cfb5`; no fallback used.  
**Date:** 2026-09-26. **Repository:** `bgoertzel-sing/hive-appliance`.  
**Commit:** `bc8e5e0699b5977020ea9cc75664282c44ebc3bc`, clean detached worktree `repos/hive-astra-6949`.  
**Prior baseline:** `635fa3d142961caa44555783dc7933914fc95463`; prior reports [6748](ASTRA_REVIEW_6748.md) and [6882](ASTRA_REVIEW_6882.md).  
**Evidence:** [20260926-astra-6949](../experiments/20260926-astra-6949/), especially the preserved original-reviewer `primary-029ec2d2/probes-result.json`.

## Verdict

**Substantial real repairs, not blanket closure: 8 CLOSED, 3 PARTIAL, 0 wholly OPEN.** The remaining partial IDs are **H2, U2, and P2-store**. P2's demonstrated external write/delete exploit is closed in the tested paths, but metadata admission remains permissive; see the explicit distinction below. **Do not enable live upgrade/repair or declare hive incident state authoritative on the basis of all-findings-fixed claims.** This bounded review also does not certify shared-ingestion production readiness against all historical gates.

The original stale-publication, live-partial deletion, nonhealthy count loss, checkpoint fail-open, incident-loss, stop-timeout, invalid finish status, and pre-existing symlink-directory counterexamples no longer reproduce. Identity-aware receipt handling and actual reducer restoration improved materially, but incomplete incident completion checks and missing external rollback remain executable counterexamples.

**Full pytest saved result: 613 passed, 1 failed, 614 collected, exit 1**, 28.53 seconds in the retained output. Failure: `tests/test_packaging.py::test_wheel_build`, isolated build cannot obtain `wheel` under deliberately offline dependency controls. This does **not** demonstrate a production source regression, and is **not** a packaging pass. All newly authored fix/CLI tests passed in this suite.

**Independent adapted probes: 16 observation groups, 16 assertions held, exit 0, no harness failures.** Some assertions deliberately demonstrate residual defects; this is not 16 safety gates passed.

### Execution/provenance caveat

This original reviewer launched the full suite once (`vivid-nexus`; process receipt exit 1, launcher wall 29.5559 seconds). The parent independently started a retry reviewer while this reviewer remained active. That reviewer wrote the same evidence paths: retained suite output/result now reports a second launcher wall time of 28.8173 seconds. Therefore **globally exactly one suite invocation cannot honestly be claimed**; duplicate orchestration occurred. No further suite invocation was made here. Independent probe files were copied into `primary-029ec2d2/` when this overlap was detected, before completing this report. `PRIMARY_REVIEW_COORDINATION.md` records the collision. Use the immutable named probe snapshot for this report's finding evidence, not any subsequently overwritten top-level probe file.

## Per-finding dispositions

Line references refer to exact bc8e5e0 source. CLOSED means the named bounded defect is closed, not an entire subsystem certification.

| ID | Status | Verified result |
|---|---|---|
| A1 | **CLOSED** | Expired worker A remains blocked inside its downloader while independent SQLite store B reclaims and completes. A resumes, loses CAS, and removes only its own artifact. B's completed pointer and `new` bytes survive. |
| A2 | **CLOSED** | Reconcile preserves the current unexpired attempt's real `.part` path; deletes a separate orphan. `active_partials_kept=1`, `orphan_partials=1`, row remains downloading. |
| H1 | **CLOSED** | Critical incident plus HEALTHY, DEGRADED, FAILED, or UNKNOWN/0 poll always preserves count 1 and FAILED severity. |
| H2 | **PARTIAL** | Explicit unrelated target is ignored; same receipt replay no longer clears a second incident; resolved history no longer poisons polls. But an untargeted unrelated verified receipt still clears oldest incident, and one receipt prematurely resolves a two-step plan. |
| U1 | **CLOSED** | Checkpoint-create exception and unreadable readback both cause 0 executor calls and durable `blocked_no_checkpoint`. Missing/raising rollback load after dispatch produces durable `rollback_failed`, not a hidden exception or NameError. Successful metadata restore verified. |
| U2 | **PARTIAL** | Actual checkpoint load and reducer restoration now occur; missing checkpoint reports `rolled_back=False`. But `rollback_command` is still unused and a real temp-file side effect survives a failed upgrade despite `rolled_back=True`. |
| U3 | **CLOSED** | Public checkpoint/restore preserves full incident records, one open incident, dedup and partial composite-plan progress; subsequent final receipt resolves correctly. |
| L1 | **CLOSED** | Stop timeout returns False, retains live worker and set stop event; start raises until termination. Later restart and normal lifecycle work. |
| S1 | **CLOSED** | `finish_attempt` rejects INVALID, pending and downloading; raw SQL invalid status is rejected; valid completed transition succeeds. |
| P1-symlink | **CLOSED** | Pre-existing `root/tg → outside` rejected by both normal and thumbnail resolution with **zero outside directories created**. |
| P2-store | **PARTIAL** | Append/update still accept external `local_path`, including a store with configured root. Publication now derives a safe attempt path; deletion no longer trusts external persisted paths, even with unknown root. Original filesystem exploit closed, admission policy not. |

## Evidence and residual details

### A1 — winner publication survives a genuinely overlapping stale worker

**Source:** `conversation/attachments.py:180–187,702–755`. **Probe:** `A1_concurrent_stale_publication`.

Unlike merely checking authored tests, the adapted old probe uses two real SQLite connections, an already-expired lease, and an actual blocking worker thread. A writes its partial, B reclaims/completes while A is still alive, then A resumes. Winner DB row remains completed and points to its own immutable attempt-specific file with bytes `new`. A reports failure and cannot unlink B's path. The old diagnostic “lease was lost before publication” remains temporally imprecise, but no longer denotes destruction of the winner.

### A2 — bounded old counterexample closed, concurrency breadth not certified

**Source:** `conversation/attachments.py:819–846`. **Probe:** `A2_active_partial`.

The current naming scheme adds attempt identity to both final artifact and partial; probe derives the actual current path rather than assuming the old filename. Existing live partial survives; independent orphan is deleted. Active lease membership is still captured once before the filesystem scan, so exhaustive claim-during-scan races are outside this evidence. Do not equate this result to a process-crash/multiprocess campaign.

### H1 and H2 — genuine count/identity fixes, but completion still unsafe

**Source:** `hive/reducer.py:103–139,191–224,288–316`. **Probes:** `H1_all_poll_states`, `H2_original_identity_replay`, `H2_local_resolution`, `H2_remaining_identity_composite_defects`.

The original explicitly mismatched receipt no longer clears an incident. A repeated receipt for A leaves B open. Resolving B then polling HEALTHY yields count 0, without the old resolved-history poisoning. A real one-step local Appliance/LocalAgentAdapter resolution also converges to HEALTHY/0.

However:

1. **Untargeted fallback remains identity-free.** Inject an unrelated `RECEIPT` event with `{id: 'unrelated-untargeted', verified: true}` and no incident/plan identity. Lines 309–310 intentionally select the oldest open incident. Observed FAILED/1 becomes HEALTHY/0. Receipt dedup does not make this identity match legitimate.
2. **Individual receipt is mistaken for whole-plan completion.** Record a real incident linked to a two-step Plan in an actual Appliance; record only step 0's verified Receipt. Local reducer correctly keeps one open incident. Hive reducer immediately marks it resolved. Suppress polling for that tick to observe Hive HEALTHY/0 versus local open=1; next normal poll restores DEGRADED/1. No private incident-list fabrication. A receipt must not resolve a composite repair until completion is authoritative.

**H2 acceptance remaining:** reject untargeted/contradictory resolution evidence; preserve per-plan/per-attempt completion semantics, not merely receipt identity; keep local and Hive active state consistent. Severity remains High for trusted operational state.

### U1 — intentional fail-closed gate and explicit failure audit now present

**Source:** `controller/appliance.py:216–236,271–299,330–359`. **Probe:** `U1_checkpoint_and_rollback_failures`.

Five fault scenarios independently exercised: create raises; load-after-create returns None; later rollback load returns None; later rollback load raises; ordinary failed execution with successful restore. First two dispatch no steps and return no receipts, record `blocked_no_checkpoint`, leave incident unresolved. Later failures dispatch one failed step, preserve an error in a durable RECOVERY event, record `rollback_failed`. Successful reducer rollback produces exact pre-repair snapshot equality. Undefined logger regression is gone.

This closes the named checkpoint/failure-reporting defect, **not external action reversibility**. Repair outcome `rolled_back` describes reducer restoration; host mutation still requires its own recovery contract.

### U2 — reducer restoration is real; external upgrade rollback is not

**Source:** `recovery/upgrade.py:188–213`; `controller/appliance.py:412–418`. **Probes:** `U2_actual_metadata_restoration`, `U2_external_rollback_missing`.

Original executor-double scenario now calls checkpoint load once and exactly restores reducer state including incident records. Missing checkpoint gives `rolled_back=False` plus rollback_error. This is a substantive closure of the old “flag only, no load” counterexample.

But the UpgradeStep still advertises `rollback_command`, and it is not executed. A bounded **real ShellExecutor** probe starts an evidence-temp file at `before`, runs `printf changed > <temp-file>; false`, with rollback command `printf before > <temp-file>`. Result: `success=False`, **`rolled_back=True`**, file still **`changed`**. Only reducer state was restored. No real host/service command or deployment was involved.

The CLI now explicitly says “state restored from pre-upgrade checkpoint”, an improvement over an unqualified presentation, but the broad automatic-rollback promise and unused rollback command remain. **Keep U2 PARTIAL** until actual external rollback is executed/verified, or the API explicitly separates `metadata_restored` from action rollback, rejects unsupported rollback promises, and prevents callers from treating it as recovery-ready external upgrade support.

### U3 — incident-safe snapshot roundtrip

**Source:** `controller/reducer.py:147–187`. **Probe:** `U3_checkpoint_incidents`.

Roundtrip includes one open incident, its identity/plan linkage, expected step count and already-received first step. Restore equals the entire earlier JSON snapshot. Re-emitting the incident does not duplicate it; second step resolves it. This closes the prior unconditional `incidents=[]` loss. It does not establish durable rollback of the whole event store or every event-replay ordering.

### L1 and S1 — tested boundary repairs hold

**Source:** `conversation/attachments.py:849–882` and `254–258,289–300,413–435`. **Probes:** `L1_timeout_restart`, `L1_normal_worker`, `S1_terminal_validation`.

Blocked downloader survives stop timeout but is retained; start refuses a new generation, stop event is not cleared; release permits clean stop and later fresh restart. No leaked test threads. This does not certify arbitrary simultaneous callers of start/stop.

Invalid finish states now raise before updating the row. DB invalid-status update raises IntegrityError. Source also installs triggers on legacy schemas; authored tests pass. A valid terminal completed call still succeeds.

### P1 and P2 — effect boundary repaired, metadata admission remains permissive

**Source:** `conversation/attachments.py:154–201,303–370,372–388,521–551,707–745`. **Probes:** `P1_existing_symlink`, `P2_store_paths`.

Both original pre-planted symlink cases reject before external mkdir. This is **not** a dirfd/no-follow implementation, so concurrent directory-swap resistance is not certified by these static-symlink probes.

Direct store append and update still persist external paths. Nevertheless `_download_one` ignores those paths and derives a contained attempt artifact; the outside sentinel is unchanged. `delete()` with no root refuses file removal, and with a configured root refuses external removal; metadata deletion still succeeds. Tested append, update, unknown-root delete and configured-root delete.

**Classification nuance:** if P2 is defined solely as the original external-publication/unlink exploit, that narrowly scoped defect is CLOSED. This report uses **PARTIAL** for the original multi-part request (“does store append still accept external paths?” plus final effect containment), because answer to admission is still **yes**. Do not describe unchanged admission as proof external writing/deletion still occurs. Define store-path trust policy and validate append/update/finish if they are intended to reject unsafe metadata; review other persisted-path consumers separately.

## CLI fix

**Source:** `cli.py:51–98,270–295`; `recovery/upgrade.py:215–241`. **Probe:** `CLI_manifest_and_plan`.

Both legacy JSON `{name, steps:[{name:'inspect', command:'true'}]}` and canonical UpgradeManifest JSON execute the actual CLI function successfully, report Steps 1/1 and a checkpoint. ShellExecutor receives a real Plan, so the prior `plan=None` provenance crash does not occur. The only shell action is `true`.

Direct **`UpgradeStep(name=...)` still raises TypeError** because the dataclass API still uses `verb`; that is expected. The CLI repair translates legacy names to `verb` instead of calling the unsupported constructor. Thus **the CLI defect is CLOSED**, not the dataclass made backward-compatible.

## Reproduction, tests and limits

- `command.sh`, `run_suite.py`, `pytest.stdout/stderr`, `pytest-result.json`: retained full suite execution record; orchestration collision caveat above. No suite exclusion, weakening or dependency installation used to obtain a green result.
- `source/`, `source-sha256.json`, `commits.txt`, `latest.diff`: exact tracked-source export and five-commit delta. Source export isolates packaging test writes from review worktree.
- Original probe source retained as `original-probes.py`. `adapt_probes.py` preserves original helpers/setups and replaces old defect assertions with current invariants plus residual boundary tests. `adapted_cases.txt` documents all adaptations. The standalone generated probe imports bc8e5e0 directly.
- `primary-029ec2d2/probes.py`, `probes-result.json`, `probes.stdout/stderr`, `probes-exit.json`: this report's independent 16-group output. These saved scripts contain the same probe code used at the evidence-root location; to rerun a saved standalone copy, place it at the evidence-root level (its R/E path derivation assumes that layout), or run root `probe-command.sh` after checking it has not been changed by concurrent review. Avoid overwriting retained outputs.
- Python 3.10.12; pytest 9.1.1; SQLite 3.37.2; build 1.5.0 versus dev pin 1.6.1; setuptools 59.6.0; wheel 0.37.1; Chroma 1.5.9; ONNX Runtime 1.23.2. Existing dependencies/cache used. Offline Python socket guard and HF/pip flags; this guard is not an OS sandbox.
- No production code edits, deployment, gateway/VM changes, remote compute, credential handling, real transport downloads or actual service rollback. Bounded shell commands affect only evidence temp file and use `true`/`false` controls. No installed-wheel qualification; full historical M5/Conversation Store gates not rerun.

**Overall:** recognize the eight bounded closures and narrower component successes; retain H2/U2 safety blockers, clarify P2 metadata policy, and do not equate green authored regression tests with all prior safety guarantees restored.

**Actual model at completion: `openai-api/gpt-6-astra`.**
