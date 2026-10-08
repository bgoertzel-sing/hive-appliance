# Opus 5.5 review 6979 — re-review of H2 / U2 / P2-store fixes at 1ab8e5f

> **This is an Opus 5.5 review, not an Astra review.** The filename keeps the `ASTRA_REVIEW_<n>` series for continuity only. Ben approved running it on Claude Opus 5.5 because Astra was unavailable.

**Model that actually ran this review:** `anthropic/claude-opus-5-5`, OpenClaw subagent session `agent:main:subagent:de0c6b2a-d321-49d0-83c3-1d9bb60118ec`. No Astra model was used at any point.
**Date:** 2026-09-26. **Repository:** `bgoertzel-sing/hive-appliance`.
**Commit reviewed:** `1ab8e5fc80de98f7d7ab4448f084be2af76143ab` (main). Clean detached worktree `repos/hive-astra-6979`. Its `git status --porcelain` output was empty before and after the review, and all 111 tracked files match `source-sha256.json`.
**Delta reviewed:** `8c373da..1ab8e5f`, a single commit (`latest.diff`: 8 files, +320/−18).
**Prior baseline:** [ASTRA_REVIEW_6949](ASTRA_REVIEW_6949.md) at `bc8e5e0`: 8 CLOSED, with H2, U2 and P2-store PARTIAL. The authoritative prior probes are `experiments/20260926-astra-6949/primary-029ec2d2/`.
**Evidence:** [`experiments/20260926-astra-6979/`](../experiments/20260926-astra-6979/)

## Verdict

**9 CLOSED, 2 PARTIAL (H2, P2-store), 0 OPEN. No regressions found among the 8 previously closed findings.**

- **U2 → CLOSED.** In real ShellExecutor runs I checked the files on disk after each upgrade: rollback commands run newest-first, and the resulting file contents match the flags. `rolled_back` is True only when metadata was restored **and** every needed `rollback_command` succeeded.
- **H2 → PARTIAL, but much narrower than before (High → Medium).** Both 6949 counterexamples are closed: an untargeted receipt no longer resolves an incident, and a single receipt no longer resolves a two-step plan. Every claim in the commit held for in-order event streams. However, the reducer still **resolves on a single receipt when it has not seen the PLAN event** for that plan. So if a PLAN event arrives after its receipts, or never arrives, an incident already linked to that plan resolves after its first step.
- **P2-store → PARTIAL.** A rooted store correctly rejects external paths, including symlink escapes and `..` traversal. But the only production constructor, `ConversationStoreClient` (`conversation/client.py:95`), creates an **unrooted** `AttachmentStore`. The new admission check is therefore not active in production wiring. The effect boundary does hold in production: in my probe, nothing outside the root was written or deleted.
- **Full suite:** 623 passed, 1 failed, 624 collected. **True pytest exit code: 1**, 27.44 s. The one failure is `tests/test_packaging.py::test_wheel_build`: the isolated build cannot fetch `wheel` under the deliberate offline controls. The same thing happened at 6949. This is an environment limitation, not a packaging pass, and not a source regression. The commit's claim of "624 passed" was **not reproduced** in this offline environment; 623 of 624 is consistent with it apart from that environment-caused failure.
- **Adapted probes:** 23 observation groups, 23 assertions held, exit 0, 0.66 s. Some assertions deliberately record residual defects, so this is not "23 safety gates passed".

Not certified: that incident state in the hive is authoritative under reordered or lossy event delivery; that upgrades are safe against real services; or that shared ingestion is ready for production.

## Findings table (all 11)

| ID | 6949 | **6979 (Opus 5.5)** | What was checked at 1ab8e5f |
|---|---|---|---|
| A1 | CLOSED | **CLOSED** | Reran the prior probe: a stale worker is blocked mid-download while an independent SQLite store reclaims and completes. The winner's row and `new` bytes survive, and the stale worker reports failure. |
| A2 | CLOSED | **CLOSED** | Reran: the active attempt's `.part` file is kept and the orphan is deleted (`active_partials_kept=1`, `orphan_partials=1`). The row stays `downloading`. |
| H1 | CLOSED | **CLOSED** | Reran: a critical incident plus a HEALTHY, DEGRADED, FAILED or UNKNOWN poll always gives FAILED/1. **New H1/H2 interaction probe:** with partial composite progress (one step verified, one failed), all four poll states still give FAILED/1. After a completed plan, a HEALTHY poll gives HEALTHY/0. No regression. |
| H2 | PARTIAL | **PARTIAL (narrowed; Medium)** | The prior residual probe now behaves as desired. The claimed behaviours hold, plus the out-of-order and duplicate-index cases. **Residual:** a receipt for a plan the reducer has not registered resolves on its own (see H2 section). |
| U1 | CLOSED | **CLOSED** | Reran all 5 fault modes: `blocked_no_checkpoint` with 0 executor calls; `rollback_failed` with a durable error; exact snapshot equality on restore. |
| U2 | PARTIAL | **CLOSED** | Real ShellExecutor with temp files: a successful rollback restores the file; a failing rollback leaves the file in its failed state and sets `rolled_back=False`. Multi-step order and a missing `rollback_command` were also checked on disk. |
| U3 | CLOSED | **CLOSED** | Reran: the checkpoint roundtrip keeps the open incident and composite progress; the final receipt then resolves it. |
| L1 | CLOSED | **CLOSED** | Reran both probes: after a stop timeout the live worker is retained and restart is refused; normal lifecycle and restart work. |
| S1 | CLOSED | **CLOSED** | Reran: `finish_attempt` rejects INVALID, pending and downloading; the DB trigger rejects a raw INVALID status; a valid completion succeeds. |
| P1-symlink | CLOSED | **CLOSED** | Reran: a pre-planted `root/tg → outside` is rejected for both main and thumbnail paths, with no directories created outside. |
| P2-store | PARTIAL | **PARTIAL** | A rooted store rejects external paths in append, `update_status` and `finish_attempt`. **Production `ConversationStoreClient` is unrooted**, so production admission is unchanged. A lexical outside→root symlink path is also accepted and persisted. |

CLOSED means the specific defect named in the finding no longer reproduces. It does not certify the whole subsystem.

## H2 — hive reducer composite completion (`hive/reducer.py:294–371`)

**Observed (probes `H2_prior_residual_now`, `H2_edges`, `H2_original_identity_replay`, `H2_local_resolution`, `H1_H2_interaction`):**

- The 6949 counterexamples are closed:
  - An untargeted verified receipt `{id, verified:true}` leaves FAILED/1.
  - In a real Appliance with a two-step plan, step 0 gives hive DEGRADED/1 and local open=1. Step 1 gives HEALTHY/0 with local open=0. They stay consistent after a poll.
- **Out-of-order receipts** (steps 2, 0, then 1 of a 3-step plan): still open after two steps, resolved after the third.
- **Duplicate step index:** receipts `r0` replayed, `r0b` with the same index 0, index 5 (out of range) and index −1 all leave the incident open.
- **Mismatched plan and cross-agent receipts:**
  - An incident linked to `p1` with a receipt naming `pX` is rejected.
  - A receipt from agent `b` naming agent `a`'s incident is ignored.
  - A receipt for an unknown plan against an incident already linked to a known composite plan is rejected.
- **Failed step:** a failed step 0 followed by a verified retry of step 0 on the same plan leaves the incident open. A new plan `p2` linked to the same incident resolves it. This matches the local F7 rule (`all(received)`).

**Residual counterexamples (observed):**

1. **Unknown or late PLAN fails open.**
   - *Case d1:* the incident is recorded with payload `plan_id='p'`, which happens whenever `IncidentReport.plan_id` is set before `record_incident`. Then a verified receipt `{plan_id:'p', step_index:0}` arrives **before** the 2-step PLAN event. Result: the incident resolves immediately (`open_after_step0_of_2 = []`). The PLAN event arriving later does not reopen it.
   - *Case c:* a receipt `{incident_id:'i', plan_id:'ghost'}` against an unlinked incident also resolves it on one receipt.
   - *Cause:* line 362–366 applies the step-count gate only when the plan key is already in `_plan_steps`. Otherwise the reducer falls back to single-receipt resolution. The local `controller/reducer.py:137` "legacy path" does the same, so this is consistent with the local reducer, but it is still fail-open.
2. **Receipts that arrive before their PLAN event are never counted (stuck incident).**
   - *Case d2:* the incident is unlinked, receipts for both steps arrive, then the PLAN event links the plan. The incident stays open permanently.
   - Replaying the same receipt ids does not help, because deduplication has already consumed them.
   - This fails closed, so it is safe, but it is a liveness defect under reordering.
3. **Minor:** `step_index` values of `False`/`True` count as steps 0 and 1, because `isinstance(True, int)` is true in Python. Two boolean receipts resolved a two-step plan.

**Inference:**

- In the paths I exercised, a single Appliance emits INCIDENT → PLAN → RECEIPT in append order through the store cursor. So residual 1 needs reordered, lost or filtered events, or a receipt whose payload names an incident. It did not occur in the real-repair probe.
- That is why the severity drops to Medium rather than the finding closing. The 6949 acceptance criterion ("preserve per-plan completion semantics") is not met under reordering.
- **To close:**
  - Buffer receipts for plans the reducer has not seen instead of resolving on them (fail closed).
  - Count buffered receipts once the PLAN event arrives.
  - Accept only a real `int` (not `bool`) for `step_index`.
  - Add tests for PLAN-after-receipt in both the linked and unlinked cases.

## U2 — upgrade rollback (`recovery/upgrade.py:191–229`, `cli.py:290–298`)

**Observed (probes `U2_shell_on_disk`, `U2_actual_metadata_restoration_now`, `U2_cli_output`).** All shell actions are bounded `printf` writes to evidence temp files, with `false` / `exit 3` as controls.

| Case | Flags | On disk |
|---|---|---|
| a. step `printf changed; false`, rollback `printf before` | `rolled_back=T`, `metadata_restored=T`, `actions_rolled_back=T` | `before` ✔ (in 6949 the file stayed `changed` with `rolled_back=True`) |
| b. same step, rollback `printf partial; exit 3` | `rolled_back=F`, `metadata_restored=T`, `actions_rolled_back=F`, `rollback_error` set | `partial` — the flags match the file |
| c. 4 steps, step 2 fails | `rolled_back=T`, rollback indices [2, 1, 0] | log `s0,s1,s2,r2,r1,r0,` — newest-first; step 3 was never executed and never rolled back ✔ |
| d. step 1 has no `rollback_command`, step 2 fails | `rolled_back=F`, error "step 1 (inspect) has no rollback_command"; steps 2 and 0 still rolled back | log `s0,s1,s2,r2,r0,` |
| e. success path | no rollback results | `new` |
| Missing checkpoint | `metadata_restored=F`, `rolled_back=F`, both errors joined | — |

CLI output:

- When rollback succeeds it prints `Rolled back: YES (rollback commands succeeded; …)`.
- When rollback fails it prints `Rolled back: NO (external actions NOT rolled back: …)` followed by `metadata restored: yes; external actions rolled back: no`.

**Remaining notes (inference, not defects in the named finding):**

- Rollback success is judged only by the rollback command's exit code (`ExitCodeVerifier`). Nothing checks the resulting external state.
- The failed step's rollback always runs, even if that step failed before doing anything. Manifest authors must therefore write idempotent rollback commands; document this.
- For ShellExecutor failures, `rollback_error` detail is the generic "rollback command failed" because the receipt `stderr` was empty. The main step error still reads "failed: unknown", which is pre-existing.

## P2-store — path admission (`conversation/attachments.py:304–313, 326, 380, 441`)

**Observed (probes `P2_rooted_store_edges`, `P2_prior_probe_adapted`, `P2_production_wiring`, `P2_static_constructors`).**

A rooted store rejects all of the following:

- an absolute external path in `append` (returns 0), in `update_status` (returns False) and in `finish_attempt` (returns False, and the row stays `downloading` with its old path);
- `root/tg/../../outside/y.bin`;
- relative `../outside/rel.bin`;
- a symlink inside the root pointing to an outside directory;
- a dangling symlink inside the root pointing to an outside file.

Paths inside the root are accepted. Unrooted stores behave as before.

Residuals:

1. **Production wiring is unrooted (main reason for PARTIAL).**
   - `P2_static_constructors`: the only non-test constructor is `conversation/client.py:95`, `AttachmentStore(str(self.store.db_path))`, called with no `attachments_root`.
   - `P2_production_wiring`: a real `ConversationStoreClient` (real `MessageStore`, stub index) had `attachment_store._root_folder = None`. `append` persisted an external `local_path`.
   - The effect boundary still held: `process_pending` wrote the attachment inside `…/attachments` and left the outside file untouched, and `delete` did not unlink the outside file.
   - *Inference:* the new admission check does not protect production metadata unless callers pass a root. `client.py` already knows the folder root (`folder_manager`), so passing `attachments_root=str(folder_manager.base_dir)` is the obvious fix.
2. **A lexical path through an outside symlink pointing into the root is accepted.** `outside/in_link → root`, so `outside/in_link/tg/w.bin` resolves inside the root and is stored verbatim. After the symlink was retargeted to point outside, the stored path resolved to `outside/tg/w.bin`, and the store's own `contains()` returned False. Delete stays safe because `is_safe_file` requires a lexical prefix. *Recommendation:* store the resolved path, or require a lexical prefix at admission too.
3. **Relative paths depend on the working directory.** `tg/rel.bin` is accepted when the process runs inside the root, is persisted as relative, and is rejected when it runs elsewhere. Recommendation: require absolute paths.
4. **Minor:** `update_status(…, 'INVALID', local_path=external)` returns False instead of raising ValueError, because the path check runs before status validation.

## New observations outside the 11 IDs (pre-existing, not regressions)

- **N1 — the local controller reducer never resolves incidents repaired through `Appliance.repair()`.**
  - Observed in `H2_real_repair_flow` and `debug_repair_flow.out`, reproduced identically at `bc8e5e0`.
  - `repair()` records the INCIDENT with `plan_id=''` and only sets `incident.plan_id` in memory (`controller/appliance.py:297`). `controller/reducer.py:_handle_plan` does not link plan→incident, and `_handle_receipt` matches on `inc.plan_id`.
  - After a fully verified 2-step repair: `outcome='resolved'` and the in-memory object is resolved, but `app.open_incidents()` still returns 1.
  - The **hive** reducer now resolves it correctly (its incident record shows `resolved: True`, thanks to the new `_handle_plan` linkage). The hive still displays FAILED/1, because `update_agent_health` takes max(polled local count, reducer count).
  - Earlier probes masked this by setting `inc.plan_id` before `record_incident`. It matters for the 6949 criterion "keep local and hive state consistent". Recommend a separate finding.
- **N2 — the local F7 rule counts duplicate step indices.** Two verified step-0 receipts resolve a 2-step plan locally (`b2_local_controller_open_after_two_step0_receipts = 0`), while the hive correctly keeps it open. The hive is now stricter than the local reducer.

## Modified older tests (3)

| Test | Change (`latest.diff`) | Assessment |
|---|---|---|
| `tests/test_hive_reducer.py` helper `_make_receipt_event` | payload `{"verified": v}` → `{"verified": v, "incident_id": "inc_1"}` | **Legitimate contract update.** The helper's incident default id is `inc_1`, so the receipt now targets the incident it is meant to resolve. `test_reduce_receipt_resolves_incident` still asserts resolution, and `test_reduce_unverified_receipt_no_change` still asserts nothing changes; neither assertion was edited. The old test relied on the untargeted fallback, which H2 required removing. The opposite case (untargeted resolves nothing) is now covered by `test_h2_untargeted_receipt_resolves_nothing`. |
| `tests/test_a1_a2_p_astra6882.py::test_p2_delete_refuses_uncontained_path` | `assert store.append([item]) == 1` → `== 0`, plus an unrooted store writing a legacy row | **Legitimate, and slightly stronger.** It now also asserts the new rejection, and the original delete-safety assertions (`delete is True`, victim still reads `precious`, row gone) are unchanged. |
| `tests/test_u1_u3_astra6882.py::test_u2_appliance_upgrade_actually_restores` | `rolled_back is True and rollback_error == ""` → `metadata_restored is True`, `rolled_back is False`, and `"no rollback_command" in rollback_error` | **Legitimate contract update.** `_failing_manifest()` defines a step with no `rollback_command`, so `rolled_back=False` is the correct answer under the new contract. The substantive checks (executor called, state not mutated, incident list restored) are unchanged. It is not a weakening: it still asserts metadata restoration through the new, more specific flag. |

All three pass in the full run, and all 10 tests in `tests/test_astra6949.py` pass.

## Test results

- **Command:** `experiments/20260926-astra-6979/command.sh` → `run_suite.py`. The suite runs `python3 -m pytest tests/ -v -p no:cacheprovider` against an exported tracked-source copy (`source/`, 111 files, hashes match the worktree). Environment: offline socket guard (`guard/sitecustomize.py`), `PIP_NO_INDEX=1`, `HF_HUB_OFFLINE=1`, 600 s timeout. It was run **once**.
- **Result (`pytest-result.json`, `pytest.stdout`, `pytest.stderr`):** exit_code **1**, no timeout, 27.77 s launcher / 27.44 s pytest. 623 passed, 1 failed (`test_wheel_build`, `No matching distribution found for wheel`, offline).
- **Probes (`probe-command.sh`, `probes.py`, `probes-result.json`, `probes.stdout`, `probes.stderr`, `probes-exit.json`):** 23/23 held, exit 0.
  - Earlier probe iterations in this session failed only because of harness bugs, all fixed: an enum severity; a parent message the attachment needed; and an unrooted-store P2 probe that needed the new legacy-row setup.
  - Final files overwrite those iterations; the harness failures are described here rather than retained.
- **Environment (`environment.json`):** Python 3.10.12, pytest 9.1.1, SQLite 3.37.2.

## Recommendations

1. **H2:** buffer receipts for plans the reducer has not seen instead of resolving on them, count them once the PLAN event arrives, reject `bool` step indices, and add PLAN-after-receipt tests.
2. **P2:** make `ConversationStoreClient` pass `attachments_root=folder_manager.base_dir`. Require absolute paths and a lexical prefix (or store resolved paths) at admission.
3. **N1:** fix the local controller linkage by recording the incident's plan link or handling `incident_id` in `_handle_plan`. Add an end-to-end `repair()` test that asserts `open_incidents()==0` both locally and in the hive, without pre-setting `inc.plan_id`.
4. **U2:** document that rollback commands must be idempotent and that success is judged by exit code only. Propagate stderr into `rollback_error`.
5. Keep live upgrade/repair and "authoritative hive incident state" gated until H2 and N1 are closed.

## Scope and limits

- No production source edits, pushes, dependency installs, remote compute, service mutations or credential handling.
- Shell actions touched only evidence temp files.
- This was a single reviewer; there was no concurrent-writer collision like the one at 6949.
- Nothing was tested for concurrent symlink swaps, multiprocess crashes, or real transports.

**Model at completion: `anthropic/claude-opus-5-5` (Opus 5.5 review, not Astra).**
