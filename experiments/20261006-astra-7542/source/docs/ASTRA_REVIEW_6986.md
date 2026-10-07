**Actual model: `openai/gpt-6-astra` — subscription / Codex app-server route.**

# Independent Astra review 6986 — 1ab8e5f

**Date:** 2026-09-26. **Repository:** `bgoertzel-sing/hive-appliance`.  
**Reviewed code:** `1ab8e5fc80de98f7d7ab4448f084be2af76143ab`, detached worktree `repos/hive-astra-6979`. `cfd446a` adds only the Opus review document; it does not change this code.  
**Reviewer session:** `agent:main:subagent:afe9eca5-987e-4614-ac45-33dccfb4e8ac`. Before executing source, session metadata identified `gpt-6-astra`; own transcript metadata identified provider `openai`, API `openai-responses`, and mirror origin `codex-app-server`. No fallback was used.  
**Exclusive evidence:** [20260926-astra-6986](../experiments/20260926-astra-6986/). No writes into the Opus evidence directory.  
**Claims reviewed:** [Opus 6979](ASTRA_REVIEW_6979.md), with [Astra 6949](ASTRA_REVIEW_6949.md) as the earlier baseline.

## Verdict

**9 CLOSED, 2 PARTIAL (H2 and P2-store), 0 OPEN among the original 11.** I agree with Opus's original-finding dispositions. All eight previously closed bounded counterexamples remained closed in my rerun. **U2 is genuinely repaired for its documented rollback-command contract.**

**N1 and N2 are independently confirmed**, including separate execution against `bc8e5e0` proving that the underlying local-controller defects predate this commit. N1 is **Medium** (verified repairs remain locally open and display FAILED/1); N2 is **High for trusted local repair-completion state** (duplicate step-0 evidence can declare a two-step repair complete). Those severity labels are reviewer assessments, not measured likelihoods.

**Do not yet treat local/hive completion state as authoritative for Protomega2 live repair.** H2 still fails open with missing/late PLAN metadata, while N1/N2 independently break local/hive agreement. P2's original external write/delete effect was not reproduced; its metadata-admission policy is still incomplete and not wired into the default client.

**Full pytest, exactly one invocation by this reviewer:** **623 passed, 1 failed, 624 collected, true pytest exit 1**; 27.35 s pytest / 27.73 s launcher. The isolated wheel-build test failed because offline pip could not obtain **`setuptools>=61`**. This is the same category of environment limitation as Opus's missing-`wheel` result, but the exact missing dependency in my run differed. It is not a packaging pass or evidence of a source regression.

## Method and evidence

- Inspected the pinned source and the three edited older-test diffs; checked `cfd446a` is doc-only.
- Copied the Opus harness (which incorporates the prior Astra probes) into my own evidence directory, audited its active assertions, and reran **23 observation groups**, all assertions holding. The copied harness contains unused historical functions; only its final `CASES` list executes. Reused code is disclosed, not presented as independently authored.
- Authored and ran **`independent.py`**, a separate harness for the H2 event schedules, same-stream local/hive N2 divergence, normal public `Appliance.repair()` N1 flow, and P2 mutable-path admission. These are fresh executions and assertions, not conclusions copied from Opus output.
- Exported `bc8e5e0` under my evidence directory and ran only the new N1/N2 probes against it. **No second pytest invocation**, including on the baseline.
- Full suite ran on a tracked-file export of the pinned worktree so packaging artifacts stayed in evidence. All **111 tracked worktree files** still match the before-run SHA-256 manifest, and the worktree remains clean (`verification.json`).
- Source snapshots, probes, stdout/stderr, subprocess return codes, environment versions, test diff and checksums are retained in the evidence directory. Temporary probe databases/files were deliberately removed by `TemporaryDirectory`; their observed content and flags are recorded in JSON.

A probe marked PASS means its observation/assertion held; several intentionally assert residual defects. It does **not** mean 23 safety gates passed.

## All original findings

| ID | Status | Independently observed evidence at 1ab8e5f |
|---|---|---|
| A1 | **CLOSED** | `A1_concurrent_stale_publication`: blocked stale worker A overlaps independent SQLite claimant B; B's completed row and `new` bytes survive A's failed publication. |
| A2 | **CLOSED** | `A2_active_partial`: live attempt `.part` survives reconciliation; separate orphan deleted; `active_partials_kept=1`, `orphan_partials=1`; row stays downloading. |
| H1 | **CLOSED** | `H1_all_poll_states` and `H1_H2_interaction`: HEALTHY/DEGRADED/FAILED/UNKNOWN polls preserve a critical active incident as FAILED/1, including partial composite progress; completed-plan healthy polling gives HEALTHY/0. |
| H2 | **PARTIAL** | `H2_prior_residual_now`, `H2_edges`, and new `independent.json:H2`: untargeted receipts rejected and in-order two-step completion correct, but unknown/late plans bypass the gate; early receipts are discarded from completion tracking; boolean indices count as steps. |
| U1 | **CLOSED** | `U1_checkpoint_and_rollback_failures`: create/readback faults cause zero executor calls and durable `blocked_no_checkpoint`; missing/raising rollback load gives durable `rollback_failed`; successful metadata restoration equals pre-repair snapshot. |
| U2 | **CLOSED** | `U2_shell_on_disk`: real shell mutations undo correctly; failing rollback leaves `partial` bytes and `rolled_back=False`; newest-first order `s0,s1,s2,r2,r1,r0,`; missing rollback command keeps overall flag false while other rollback commands run. Metadata and CLI probes also pass. |
| U3 | **CLOSED** | `U3_checkpoint_incidents`: full snapshot roundtrip preserves incident, incident dedup and partial composite progress; final receipt resolves after restore. |
| L1 | **CLOSED** | `L1_timeout_restart`, `L1_normal_worker`: stop timeout returns false and retains live thread/stop event, start refuses replacement, later termination and restart work. |
| S1 | **CLOSED** | `S1_terminal_validation`: finish rejects INVALID/pending/downloading; raw SQL INVALID rejected; valid completed transition succeeds. |
| P1-symlink | **CLOSED** | `P1_existing_symlink`: both main and thumbnail paths reject planted root/tg → outside before creating outside directories. |
| P2-store | **PARTIAL** | `P2_rooted_store_edges`, `P2_production_wiring`, `P2_prior_probe_adapted`, new `P2_symlink`/`P2_relative`: configured-root append/update/finish reject external paths, but default production client is unrooted and accepts one; mutable lexical/relative paths persist. Download/delete leave outside sentinel untouched. |

CLOSED is bounded to the named defect and exercised schedules, not certification of an entire subsystem.

## Agreement/disagreement register versus Opus 5.5

| Opus conclusion | Astra determination and reason |
|---|---|
| U2 CLOSED; real external rollback now runs and flags are honest | **Agree.** Independently reran real ShellExecutor scenarios and read `recovery/upgrade.py:191–229`; disk bytes, order and flags match. Command success is exit-code verification, not a semantic guarantee of arbitrary service recovery. |
| H2 PARTIAL: one early receipt resolves a linked two-step incident | **Agree.** Fresh schedule INCIDENT(linked) → receipt 0 → PLAN(2) → receipt 1 has open counts **1,0,0,0**. Late PLAN does not reopen it. |
| H2: incident+unknown-plan receipt resolves | **Agree.** Fresh INCIDENT(unlinked) → receipt(incident_id, unknown plan) gives **1,0**. Plan-only unknown receipt against an unlinked incident does not resolve it; explicit identity is material. |
| H2: all early receipts never counted, replay does not recover | **Agree for the tested unlinked-incident schedule.** INCIDENT → receipt 0 → receipt 1 → PLAN → same receipt 0 → same receipt 1 stays **1,1,1,1,1,1**. This is lost progress under reordering, not proof that no later fresh receipts can ever resolve it. |
| H2: bool step_index is accepted | **Agree.** Fresh PLAN(2) followed by False and True indices closes the incident. Python `isinstance(bool, int)` explains the source behavior. |
| P2: default production store is unrooted | **Agree.** Real ConversationStoreClient with real MessageStore and a stub semantic index has `_root_folder=None`, persists outside path, then safely downloads under its folder root and leaves outside bytes untouched on delete. Source `conversation/client.py:95` omits the root argument. |
| P2: outside→inside symlink and cwd-relative admission gaps | **Agree.** Fresh rooted-store probe persists outside/link/tg/x verbatim, then loses containment after retargeting. Relative tg/x is admitted in root cwd, rejected outside, and the saved path loses containment after chdir. |
| No regression in the eight previously closed IDs | **Agree within tested scope.** All eight adapted counterexamples held; this does not imply arbitrary event-order/concurrency correctness. |
| Three modified older tests legitimately updated | **Agree**, after inspecting the actual diff and full-suite results; details below. |
| N1 and N2 are pre-existing | **Agree about the local defects**, proven by baseline execution. **Qualification:** N2's local-versus-hive divergence is new with the stricter hive fix; at bc8e5e0 both reducers prematurely resolved. This is a newly visible mismatch caused by improving one reducer, not a regression of the closed hive safety behavior. N1's hive internal record also improved from unresolved at bc8e5e0 to resolved here, while displayed FAILED/1 persists. |
| 623 passed / 1 offline packaging failure | **Agree on counts, exit and cause category.** Exact diagnostic differs: my missing dependency is setuptools>=61, not wheel. No claim that Opus's recorded diagnostic was wrong. |

**No original-finding status disagreement.** The baseline behavior and exact packaging diagnostic are the two important qualifications to a simple “same results” summary.

## H2: observation versus inference

**Observed:** with the PLAN already registered, receipts for steps 2,0,1 complete a three-step plan only after all three; duplicate indices, receipt replay, negative/out-of-range indices do not prematurely complete the hive plan. Mismatched-plan and cross-agent examples are rejected. A failed step keeps the same plan open despite a later verified retry; a fresh plan can resolve it. The earlier untargeted-receipt and normal in-order one-of-two-receipts defects are closed.

**Observed residual:** the new independent schedules above reproduce both fail-open and lost-progress cases. The code records receipt dedup before plan registration; it only records step progress for a known plan. At `hive/reducer.py:362–366`, it only enforces completion for a plan present in `_plan_steps`. If absent, a matching incident can be marked resolved immediately.

**Inference/severity:** **Medium under the observed ordered LocalAgentAdapter path**, which emits PLAN before its receipts. Missing/reordered/filtered events or imported receipts expose the residual; if arbitrary event delivery is trusted operational evidence, impact can be high. I did not demonstrate a production transport reordering this stream. Boolean acceptance is a schema-validation defect, not itself evidence that ordinary receipts are boolean-valued.

## N1 and N2: independently confirmed, not additional original IDs

### N1 — successful public repair leaves local incident open (Medium)

**Observed at 1ab8e5f:** new harness creates a normal critical `file_missing` incident with no preassigned plan id, records it, then calls real `Appliance.repair()` using SimplePlanner, a successful executor double and ExitCodeVerifier. Both receipts verify; returned outcome is `resolved` and caller's incident object is resolved. Yet local persisted/reduced incident still has `plan_id=''` and open count **1**. Hive incident record is resolved, but health polling displays **FAILED/1**.

**Observed at bc8e5e0:** same local result and display; hive internal incident was still unresolved there. No source changes to `controller/appliance.py` or `controller/reducer.py` between baseline and target explain a newly introduced local bug.

**Cause (source-backed inference):** `repair()` assigns `incident.plan_id` after the INCIDENT payload has been recorded; local `_handle_plan` records step count but does not apply its incident linkage. Later local receipts match `inc.plan_id`, so cannot close the stored incident. Severity is Medium for persistent false alarms / impaired operational liveness. These probes establish the ordinary recorded-unlinked flow; “never clears” should not be read as a universal claim about manually prelinked incident setups.

### N2 — duplicate indices are mistaken for distinct completed steps (High for local authority)

**Observed at 1ab8e5f:** in the new harness, one Appliance event stream feeds both local reducer and LocalAgentAdapter. A linked two-step plan plus two distinct receipt IDs, both verified and both `step_index=0`, gives local open counts **1 then 0**, while hive remains **1**. There was no step-1 receipt.

**Observed at bc8e5e0:** local still resolves after the two step-0 receipts; hive also incorrectly resolves (open **0**). Thus the root local defect is pre-existing, while the current hive is correctly stricter.

**Cause (source-backed inference):** `controller/reducer.py:117–136` appends verification booleans and compares list length to expected count. It does not require a distinct valid index per step. Severity is High when downstream automation trusts local completion, because missing work is reported complete. No real downstream service failure was induced.

## U2 and P2 limits

**U2:** real shell test writes only bounded evidence-temp files. Rollback success restored `before`; failure left `partial` and correctly reported false. Steps rolled back newest first, including failed step, excluding unexecuted steps. Missing rollback commands are explicit errors and do not prevent other available rollback commands from running. The success path never runs rollback. CLI prints YES/NO consistently. `metadata_restored` and `actions_rolled_back` are distinct. This closes the earlier unused-command / dishonest-flag defect, but does not prove that a command exiting zero restored a real external service. Keep rollback commands idempotent and add semantic postchecks where service recovery requires them.

**P2:** `_path_admissible()` validates the resolved path but persists the original string. It does not require an absolute lexical root prefix, and it is bypassed with no configured root. A rooted store rejects absolute external paths, traversal, inside→outside symlinks and dangling external targets at append/update/finish. Default client wiring bypasses that admission policy. The effect layer remains protective in the probes: manager publication chooses its own safe path and deletion does not unlink outside sentinel bytes. Mutable-path evidence is a metadata trust defect; it is **not** a demonstrated new outside write/delete exploit. Concurrent symlink swapping and every other persisted-path consumer were not audited.

## Three modified older tests

Actual diff: [`modified-tests.diff`](../experiments/20260926-astra-6986/modified-tests.diff).

1. **`tests/test_hive_reducer.py` receipt helper:** adds incident_id=inc_1. This correctly makes intended resolution targeted; the resolution/nonresolution assertions remain. Untargeted rejection is separately tested. Legitimate contract correction, not assertion deletion.
2. **`test_p2_delete_refuses_uncontained_path`:** rooted append now must return 0, then unrooted legacy insertion recreates the unsafe row for deletion testing. Original outside sentinel and row-removal checks remain. The new assertion increases coverage while preserving the old effect-boundary test.
3. **`test_u2_appliance_upgrade_actually_restores`:** metadata restoration is asserted explicitly; a manifest with no rollback command must report overall rollback false with an explanatory error. State/incident restoration assertions remain. Correct under the separated metadata/action contract, not weakening the required restoration.

All affected tests and all ten `tests/test_astra6949.py` cases passed in the single full suite.

## Test execution and provenance

Exact pytest argv is in [`pytest-result.json`](../experiments/20260926-astra-6986/pytest-result.json):

```text
/usr/bin/python3 -m pytest tests/ -v -p no:cacheprovider --basetemp=<evidence>/pytest-tmp
cwd: <evidence>/source
```

- **One invocation only.** Launcher `run_suite.py` captured pytest's actual `Popen.wait()` return value **1**, no timeout. The launcher itself exits 0 after saving the result; do not mistake its shell status for pytest's status.
- [`pytest.stdout`](../experiments/20260926-astra-6986/pytest.stdout), [`pytest.stderr`](../experiments/20260926-astra-6986/pytest.stderr): 623 passed, 1 failed, 624 collected. Only `tests/test_packaging.py::test_wheel_build` failed, at isolated build dependency provisioning with `No matching distribution found for setuptools>=61`.
- Existing dependencies only; `PIP_NO_INDEX=1`, HF/Transformers offline flags and copied Python socket guard. Packaging attempted its normal isolated dependency provisioning but could not install its build requirements. No manual dependency installation or retry was performed. The Python guard is not an OS sandbox.
- [`probes-result.json`](../experiments/20260926-astra-6986/probes-result.json): 23/23 observation groups hold, subprocess exit 0, 0.73 s. Supplementary current and baseline probes both exit 0; see `independent.json`, `baseline-independent.json` and corresponding exit/stderr files.
- `environment.json`, `source-sha256.json`, `verification.json`, `runtime.json`, `SHA256SUMS` preserve versions, pin, cleanliness and runtime provenance. No production source edits, pushes, deployments or live service mutations. No evidence files were written to the 6979 directory.

## Prioritized fixes for Protomega2

1. **P0 — unify authoritative completion in both reducers (N2 + H2).** Require known plan metadata and a verified receipt for each distinct valid integer index; reject bool, negative and out-of-range indices. Buffer early receipts until plan registration; do not consume them irrecoverably in dedup. Preserve agent/incident/plan identity. Specify failed-step retry/attempt semantics rather than deriving completion from raw receipt count. Add late-plan, duplicate-index and same-stream local/hive tests.
2. **P1 — fix ordinary repair linkage (N1).** Apply PLAN.incident_id → incident.plan_id in local reduction, or durably record an equivalent link before receipts. Test public repair without pre-setting plan_id and assert both local open count and hive displayed count become zero after verified completion. Preserve unresolved state on failure.
3. **P1 — wire and harden P2 admission.** Initialize/reuse the actual folder manager before creating the default AttachmentStore; pass its configured root. Require stable absolute contained storage paths, with lexical and resolved containment or an explicit canonicalization policy. Cover externally supplied folder managers, legacy rows, chdir and outside→inside symlink retargeting while retaining safe download/delete behavior.
4. **P2 — retain U2 guarantees, improve operations contract.** Document idempotent rollback requirements and exit-code-only verification, surface useful rollback stderr, and add service-specific postconditions before live upgrade qualification.
5. **P2 — qualify packaging separately with pre-provisioned approved build dependencies.** Current offline result is not a wheel-build pass; do not install dependencies merely to make this review green.

**Actual model at completion: `openai/gpt-6-astra` (subscription / Codex app-server route).**
