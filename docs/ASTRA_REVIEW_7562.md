# Astra re-review 7562 — 57a6298

**Reviewer:** `openai/gpt-6-astra`, one reviewer, no delegation or fallback. Own session `agent:main:subagent:a4016835-c331-4718-8c63-39d23d0921e2` was confirmed by runtime session metadata; own transcript also reports provider `openai`, API `openai-responses`, model `gpt-6-astra`. See `model-verification.json` in the evidence.

**Requested:** Protomega2, Telegram 7562; approval: glicerico, 7560. **Date:** 2026-10-07. **Reviewed pin:** `57a62987a8e46fe2fdf45d63c1a9c148d3e12fbd`, equal to `origin/main` at clean clone and pre-publication fetch. Read the complete five-file `0258413..57a6298` delta, commits `c6a5543` and `57a6298`. Clone: `projects/hive-appliance/repos/hive-astra-7562`; branch: `review/astra-7562`. Repository-operations, experiment-ledger and GitHub procedures applied. No product/test source edits, credential changes, live repairs or changes to prior evidence.

**Evidence:** [run README](../experiments/20261007-astra-7562/README.md). Artifact names below are relative to that directory. A passing witness assertion confirms its described behavior, not necessarily satisfaction of the product requirement.

## Verdicts and gate

| Item | Verdict | Finding |
|---|---|---|
| P3-ownerless / owned completion safety | **CLOSED — prior Medium** | No ownership inferred from links; ownerless plans close nothing. Exact witness, 180 ownerless schedules, six positive controls and 1,440 owned supersession schedules pass. Scoped to retained incident state. |
| New visibility and documented re-send behavior, as built | **CLOSED within retention limits** | Both reason maps, expected WARNING, local restore, serialized hive replay, repair and clearing work. This is a diagnostic plus ordinary first-owner assignment, not an operator hold. |
| O-ownerless-hold / operator recovery | **OPEN — Medium** | Current ownerless plans remain absent from `quarantined_plans()`; preview/rebind refuse; re-send immediately establishes ownership and uses old progress without operator-rebind audit. |
| D-option-conformance, separate policy gate | **OPEN — Medium; human decision required** | The recorded option (a) was previewed/audited hold/rebind; implemented behavior is recorded option (b) plus visibility. The implementation's option labels reverse the decision record. |
| O-retention: missing hive holds at capacity | **OPEN — Medium, newly tested inherited limitation** | 600 open linked ownerless plans yield 600 local reasons but only 500 hive reasons. The pre-existing incident cap silently drops the first 100 open incidents. |
| O-bound: global diagnostic bound | **OPEN — Low resource/operability limitation** | No explicit/global cap: local returns 600, hive returns 1,000 across two agents. No new accumulating diagnostic buffer or measured OOM; these are derived views. |
| L-F7-negative-fixtures | **CLOSED — prior Low** | Both repaired negatives fail the identical 7542 completeness-gate mutant; unmutated F7 trio passes. |
| Documentation | **CLOSED for core described code behavior; OPEN for decision provenance (Medium)** | Correctly documents re-send and rebind refusal; incorrectly attributes that choice as accepted option (a). Retention and late-link logging qualifications below. |
| Seven authored 7542 tests | **CLOSED as legitimate behavior tests** | All seven pass; not evidence of decision conformance. Synthetic legacy-set test has limited migration coverage. |
| Full suite / scoped N1–N10, H2, H-oracle, quarantine regressions | **CLOSED as execution and scoped regression review** | Sole full suite: **725 passed, 0 failed, 0 skipped**. Retained safety groups pass; three known obsolete legacy-auto-recovery expectations remain explicitly failed. |

**Gate recommendation:** retain the previously bounded current-format repair/replay gate for **explicitly owned plans**. Do **not** close O-ownerless-hold or authorize unattended ownerless ownership recovery on the strength of this patch. Obtain a human reconciliation of the two incompatible option definitions: implement the recorded previewed/audited workflow, or explicitly change the policy to accept ordinary event-authorized re-send. This review does not make that policy choice. Do not claim complete hive hold visibility above the existing incident-retention limit. No deployment/gate state was changed.

## 1. Decision conformance is distinct from implementation correctness

The preserved project decision input, [DECISIONS-input.md](../experiments/20261007-astra-7562/DECISIONS-input.md), records under **2026-10-07 — Linked-but-ownerless plans are held for operator rebind (Ben, Telegram msg 7547)**:

> Decision: option (a). Such plans enter the same visible hold list as owner_unproven, with the same previewed, audited operator rebind. Provisional: "first try; reconsider if it causes problems in practice".

> Rejected for now: option (b), relying on re-sending the PLAN with incident_id plus a warning log.

The reviewed [policy document](POLICY_MULTI_PLAN_SUPERSESSION.md#L35) instead says:

> `quarantined_plans()` is unchanged (owner_unproven rebind candidates only); `rebind_plan_owner()` still refuses these plans.

> **Repair:** send a later PLAN for the same plan id that declares `incident_id`; that sets the immutable owner, and the already-verified receipts then close that owner (only).

> Full hold/rebind (option (b)) is deferred unless (a) causes problems in practice.

These are **not the same option (a)**. The code follows its new document, but that document reverses the recorded alternatives. It also dates Ben's quoted choice **2026-10-08**, while the provided decision is recorded on 2026-10-07. The supplied 7544 handoff additionally requires re-send to record only an ownership candidate; it still assigns the owner directly here. The quotation from the decision file is direct documentary evidence; the 7544 handoff context is supplied by the requester, not independently recovered from Telegram in this review.

The new behavior is coherent under a trusted ordinary-PLAN authority model and preserves the narrower no-owner/no-closure invariant. That does not constitute approval to replace an operator-authorized recovery policy. **Human decision required; policy not silently reinterpreted.**

## 2. Implementation behavior and authority

### Witness, orderings and cleanup

Independent witness:

```text
INCIDENT(i, plan_id=p)
INCIDENT(j, plan_id=p)
PLAN(p, incident_id="", one step)
RECEIPT(x, plan_id=p, step_index=0, verified=True)
```

Both reducers retain open `[i,j]` and empty owner maps. Local reasons are `{"p":"ownerless_linked"}`; hive reasons are `{"a1:p":"ownerless_linked"}`. WARNINGs from both reducers name p and **both i and j**. Local state survives real JSON snapshot/restore after every event; hive state survives replay of serialized event prefixes into a new instance. **Hive has no snapshot API**; replay is not a checkpoint-restore claim.

`PLAN(p, incident_id=i, one step)` then closes **i only**, leaves j open, and removes the reason from both maps. It needs no new receipt. Existing verified progress is consumed for closure, not held pending an operator decision. Local preview and rebind both refuse before that repair, including `allow_non_candidate=True`, without state mutation.

Evidence includes:

- **180 ownerless schedules / 1,224 per-event states**, all PLAN/receipt/one-or-two-INCIDENT permutations for plan-only, incident-only and dual addressing, with duplicate suffixes and restart variants.
- **60 additional visibility schedules / 408 per-event states / 60 repairs**, explicitly asserting reason membership and literal open IDs at every prefix, including late PLAN/INCIDENT and multiply linked cases.
- Unlinked ownerless and owned complete/incomplete controls have no ownerless reason. Detached returned maps cannot mutate reducer state.
- A separate owned q closes i while j still links ownerless p: p remains visible. A separate owned s then closes j: p disappears although p still has no owner. Cleanup therefore is not limited to repairing p itself.
- Retained six owned-positive controls, four foreign-owner controls and **1,440 owned supersession schedules / 15,840 states** pass. The retained owned matrix uses ordered event replay for hive restart; the additional ownerless matrix explicitly serializes replay events.

See `review7562.json`, `ownerless-witness.json`, `ownerless-schedules.json`, `visibility-schedules.json`, `policy-schedules.json`.

**Logging qualification:** if p completes while unlinked and i/j arrive later, the reason appears but no WARNING is emitted on those late INCIDENTs. Completion is rechecked only for owned plans on that path. The documented normal witness logs correctly; do not claim all arrival orders produce an alert. The accessor reports incomplete linked ownerless plans too. No production CLI/status caller of `quarantine_reasons()` exists at this pin; the delivered visibility is a programmatic accessor plus warnings, not a newly integrated operator screen.

### Re-send authority versus legacy rebind

[Local `_handle_plan`](../controller/reducer.py#L364) and [hive `_handle_plan`](../hive/reducer.py#L337) establish the first nonempty owner using `setdefault`. They do not authenticate `Event.source`, validate operator actor/reason, require preview, or create `owner_rebinds`. A PLAN with `source=""` or `source="untrusted-other-agent"`, admitted to the same local/hive agent stream, repairs the witness and closes i. Thus **any producer already able to submit PLANs in that namespace can make this ownership claim**, with no additional operator authorization.

This is not evidence that an arbitrary external network user can inject events. In the normal [HiveEventBus](../hive/event_bus.py#L69), the registered adapter determines `source_agent`; an a2 adapter claiming `Event.source="a1"` still receives the a2 envelope. Independent control: a2's PLAN creates `a2:p`, leaves `a1:p` ownerless, and does not close a1's incident. The reducers themselves are trusted in-process consumers, not authenticated endpoints. Legacy rebind also relies on a trusted caller; nonempty actor/reason strings are audit requirements, not cryptographic authentication. Its docstring explicitly warns against unauthenticated exposure.

The legacy contrast is stronger in workflow terms: using authentic historical serializers, ordinary PLAN re-send records a **candidate only**, receipts remain held, blank actor/reason are rejected, preview predicts closure, and deliberate rebind creates the actor/reason/candidate/receipt-effect/closed-incident audit. Current ownerless re-send does none of that.

**Is re-send audited anywhere?** Ordinary event persistence does exist. An actual `Appliance.record_plan()` probe stores a PLAN with source `planner`, target incident and payload in the SQLite event store. Generic hive closure INFO logging can also occur. It would be inaccurate to say there is no event trace anywhere. However, no operator ownership-recovery audit, preview result, actor/reason, or receipt-effect record is produced; direct reducer calls do not persist an event themselves. See `authority-followup.json` and `review7562.json.warning_and_repair`.

One original independent authority fixture failed because it supplied a historical incident link from which ownership could genuinely be reconstructed. Its original source, exit 1 and traceback are retained. `authority_followup.py` corrects **only that fixture** to authentic PLAN-before-unlinked-INCIDENT history, matching the retained 300-plan fixture; the authority group then passes. No product/test edit or second full-suite run occurred.

## 3. Bounds and retention — additional findings

`quarantine_reasons()` is computed afresh, not persisted as an accumulating list. That avoids a new stale diagnostic cache, but **does not provide a global cap**:

| Independent load | Local reasons | Hive reasons |
|---|---:|---:|
| 600 distinct open linked ownerless plans, one agent | 600, also after restore | 500 |
| Same load on two hive agents | n/a | 1,000 |

Local `MAX_DIAG_ENTRIES=256` bounds historical migration diagnostics, **not current quarantine membership or the new reason map**. Treating that historical bound as a universal current-hold cap would repeat the earlier truncated-quarantine problem. A resource-bound claim needs a complete enumerable/paginated or explicit overflow design, not silent omission. Local unbounded result size is a **Low** resource/operability limitation here; no resource-exhaustion measurement is asserted.

More seriously, hive derives reasons solely from `_agent_incidents`, whose existing pruning code falls back to `kept[-MAX_AGENT_INCIDENTS:]` even when all 600 are open. The first 100 holds therefore disappear: `a1:p0` is missing, while p0's plan metadata remains registered and ownerless. The comment says “never open ones,” but the fallback contradicts it. This pruning is byte-identical in **0258413**: **not a newly introduced pruning regression**, but a newly tested **Medium** completeness limitation of the new visibility claim. It can hide an unresolved ownership hold, not merely shorten a historical sample.

All retained reasons clear after legitimate incident closure; unregistering the second hive agent removes its remaining reasons. Those lifecycle tests pass. See `review7562.json.caps`; the first agent's observed counts are 600 local / 500 hive, and the two-agent hive count is 1,000. These findings do not reopen the independently checked N10 historical-diagnostic caps.

## 4. Test legitimacy and docs

**F7 negatives — CLOSED.** Both now declare owner `inc_1`, the partial-failure fixture gives indices 0 and 1, and both explicitly assert that ownership exists. The original composite-completeness intent is preserved. The exact 7542 in-memory mutant removes only:

```python
if len(self._plan_verified.get(plan_id, ())) != n:
    return
```

Both `test_single_receipt_does_not_resolve` and `test_partial_failure_does_not_resolve` fail under that mutant; the complete-positive fixture survives as expected. All three pass unmutated. This is genuine detection, not a test-source edit made for review. Although the failed-step fixture's final state includes a failure guard, under the mutant its first successful step has already closed the incident, which the final assertion detects. `review7562.json.F7_mutant` preserves the result.

**Seven authored 7542 tests:** literal reason maps/open IDs and explicit log checks make them legitimate, non-tautological tests of the implemented behavior. They cover normal witness, repeated local restore, both warning names, unlinked negative, owned negative, re-send/clearing and legacy reason coexistence. The restore coverage is local only; independent probes add serialized hive replay and per-prefix reason checks. The last test directly inserts `legacy` into `_owner_unproven`, so it checks accessor composition, not authentic migration or durable recovery; retained authentic migration probes supply that coverage. These tests do not validate cap behavior, operator authorization or the recorded decision. Passing the re-send test demonstrates exactly the disputed behavior, not policy acceptance.

**Docs:** accurately describe the reason, unchanged quarantine list, rebind refusal and re-send repair. Their option attribution is nonconforming as quoted above. “Every plan that cannot currently close an incident” in the local accessor docstring is overbroad: owned-but-incomplete plans intentionally return no reason. Capacity and late-link logging qualifications should be explicit. Neither wording nor a green suite closes the separate policy gate.

## 5. Sole full suite and retained regressions

```text
/usr/bin/python3 -m pytest tests/ -v -p no:cacheprovider \
  --basetemp=.../20261007-astra-7562/pytest-tmp
cwd: .../20261007-astra-7562/source
725 collected; 725 passed; 0 failed; 0 skipped
47.73 seconds pytest; 48.2496 seconds runner wall time; exit 0
```

This matches the claimed **725/0**. There was **exactly one** full-suite invocation. Before it, three build-prerequisite wheels (setuptools 82.0.1, wheel 0.46.3, packaging 26.0) were downloaded into an isolated directory without changing installed packages. The suite remained offline with `PIP_NO_INDEX=1` and `PIP_FIND_LINKS` pointing there; `test_wheel_build` passed. This fixes the *review environment's* previous missing-build-prerequisite issue, not product code. It is the authored wheel-build smoke, not a new clean-installed runtime qualification.

| Retained scope | Actual result |
|---|---|
| N1–N4 and mixed-receipt cases | **398/398** |
| N5 current / authentic prior ordered formats | **3,072/3,072 each** |
| Legacy fail-closed / opposite histories | **384/384; 2/2** |
| Ownership lifecycle / authentic old ownership / namespace | **48/48; 6/6; 1/1** |
| Explicit manual-rebind stale-progress disk recovery | **6/6** |
| N8 boundaries | **14/14** |
| H2/N9/N10 7173 groups | **10/10**, including **51 H2 schedules** |
| N9/N10 7195 groups | **7/7**, including **64 receipt schedules** |
| Authentic 300-plan quarantine follow-up | **300 → 151 → 0**, historical sample 256, **20 restores at each stage** |
| H-oracle | All **five health mutants** detected; four boundary cases and hive-health-poisoning independence pass |
| Earlier A/H/U/L/S/P and independent controls | Retained assertions pass |

Counts overlap and must not be summed into a unique test total. Unchanged `semantic_7133.py` exits **1** for **three previously known obsolete automatic legacy-PLAN recovery expectations (0/3)**; its safety families pass and the explicit manual repair controls pass separately. That failure is retained, not relabeled green. Historical helpers were copied byte-for-byte; the prior supersession-policy adaptation was retained, not weakened again.

## Publication and reproducibility

The evidence includes pinned tracked source, complete requested diff, decision input, exact child commands/start/exit/logs, unchanged historical helpers, successful and failed independent attempts, schedule traces and hashes. Source and copied-helper hashes were verified after testing. Only this report and `experiments/20261007-astra-7562/` are publication changes. A fetch, focused staged-scope review, credential-pattern scan and integrity verification precede the explicitly authorized fast-forward main push. If main moves, only the review commit may be rebased; the reviewed product pin remains 57a6298.

`README.md` documents environment, excluded disposable outputs/dependency binaries, exact reproduction and verification. New report prose is whitespace-clean; copied source/raw diffs/logs retain their original formatting. No discarded outcome, future-source qualification, external-injection claim, policy override or deployment approval is implied.
