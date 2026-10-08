# Decision Log

## D-20260922-reject-251662b-latest-requalification: Keep attachment readiness rejected

- Date: `2026-09-22`
- Status: `accepted`
- Decision owner: delegated independent review gate
- Related task/run/commit: `experiments/20260922T224941Z-astra-latest-fixes-requalification/`, commit `251662bc6a230eaa3896119d504d8c1248c44e46`

### Decision

Keep hive-wide attachment readiness rejected and shared ingestion disabled.

### Rationale and evidence

The full suite produced 475 passes, 56 failures, and 23 errors. Independent
current-API testing reproduced 21 defects with five repair controls and zero
harness errors. PF01 is closed, but AF01-AF13 and GF01 remain open; missing
lease schema, duplicate process ownership, crash-stranded work, unsafe paths,
broken semantic outbox draining, and Gate-4 regressions remain executable.

### Revisit trigger

A pinned repair restores the complete baseline and closes every reproduced
counterexample, with particular priority on typed Hive health, queue fencing,
crash recovery, filesystem containment, and canonical semantic indexing.

## D-20260922-repair-implemented-await-requalification: Keep readiness disabled pending review

- Date: `2026-09-22`
- Status: `accepted`
- Decision owner: implementation/review boundary
- Related task/run/commit: repair branch `agent/astra-findings-repair`; full-suite and installed-smoke runs

### Decision

Treat the Astra findings as implemented locally, but retain the readiness
rejection and keep shared ingestion/live mutation disabled until an independent
commit-pinned Astra requalification passes.

### Rationale and evidence

The full suite improved from 471 passed/60 failed/23 errors to 561 passed with
new adversarial attachment gates, and the installed transitive imports pass.
These results were produced by the implementing agent and are not an
independent review.

### Revisit trigger

Astra re-runs all finding probes and cross-process/crash/package gates against
the exact repair commit.

## D-20260922-reject-22e0d57-attachment-requalification: Keep attachment readiness rejected

- Date: `2026-09-22`
- Status: `accepted`
- Decision owner: delegated independent review gate
- Related task/run/commit: `experiments/20260922T152243Z-astra-attachment-rereview/`, commit `22e0d5724217313037e964b5784fba0476c14a50`

### Context

Protomega2 published code-quality maintenance and 37 attachment tests after the
shared-attachment rejection at `1ae2b78`.

### Decision

Keep hive-wide attachment readiness rejected.

### Rationale and evidence

The full suite produced 471 passes, 60 failures, and 23 errors. Preserved and
adapted probes show all 15 findings remain open and all eight requalification
gates fail. The installed attachment-only smoke passes, but Hive/CLI imports
still fail because `recovery` is omitted from the wheel.

### Revisit trigger

A pinned repair closes the eight gates and passes the complete source and
installed-wheel suites for legitimate reasons.


## D-20260921-reject-e0f2f1d-requalification: Reject repaired M5 and Conversation Store completion

- Date: `2026-09-21`
- Status: `accepted`
- Decision owner: delegated independent review gate
- Related task/run/commit: `experiments/20260921T233949Z-astra-requalification/`, commit `e0f2f1d`

### Context

Protomega2 published a repair claiming all CS01–CS14 findings addressed.

### Decision

Keep M5 completion and Conversation Store readiness rejected; keep live mutation and real conversation ingestion disabled.

### Rationale and evidence

The full 517-test suite passes and packaging/local behaviors improved, but M5 has 1 closed and 16 open findings. Conversation Store has 5 closed, 5 partial, and 4 open. Actual Chroma reproduces duplicate contradiction, post-SQL-commit batch failure, and schedule-dependent vector truth; failed indexing is skipped on bootstrap retry. The exact wheel passes a clean installed ingest/query/reopen smoke.

### Revisit trigger

A pinned repair implements a durable canonical outbox/reconciliation watermark and closes the remaining source, retrieval, provenance, and M5 gates.

### Supersedes or superseded by

Updates but does not erase `D-20260921-reject-current-m5-and-conversation-store`.

## D-20260921-reject-current-m5-and-conversation-store: Reject current M5 and Conversation Store completion

- Date: `2026-09-21`
- Status: `accepted`
- Decision owner: delegated independent review gate
- Related task/run/commit: `experiments/20260921T115036Z-astra-current-review/`, commit `5de2919`

### Context

Ben requested an Astra review of Protomega2's current public Hive Appliance and
Conversation Store work. Contrary to a prior status implication, `023303a`
predates M5 and is not a post-M5 repair commit.

### Decision

Reject M5 completion and Conversation Store P1-P6 production/shared-service
readiness. Keep live hive mutation and real conversation ingestion disabled
until the High findings are repaired and the exact repair commit passes
independent requalification.

### Alternatives considered

Accepting the green authored suite and milestone commit labels as sufficient,
or deploying the Conversation Store as an experimental shared service while
repairing consistency and identity defects incrementally.

### Rationale and evidence

All 517 authored tests pass, but all 29 prior M5 defect probes reproduce, so
0/17 M5 findings are closed. Independent Conversation Store testing reproduced
17 deterministic defect scenarios and three real-Chroma corroborating/extended
cases, consolidated into 14 findings (10 High, 4 Medium). These include lost
identity/provenance, SQL/vector divergence and post-commit failures, unsafe
bootstrap completion/retry behavior, deterministic input loss, partial-tail
cursor loss, venue-scope collapse, and missing installed-package contracts.

### Consequences

Repair canonical identity and atomic/recoverable indexing first, then
bootstrap/cursor and scope semantics, packaging, retrieval, and threading.
Requalification must include a clean installed-wheel smoke test and positive
assertions for every reproduced counterexample.

### Revisit trigger

A scoped repair commit is published with tests addressing the reproduced M5
and Conversation Store failures.

### Supersedes or superseded by

Extends `D-20260918-reject-m5`; does not supersede its evidence.

## D-<YYYYMMDD>-<short-slug>: <Decision title>

- Date: `<YYYY-MM-DD>`
- Status: `proposed | accepted | superseded | rejected`
- Decision owner: Benjamin Goertzel or delegated role
- Related task/run/commit: `<pointer>`

### Context

### Decision

### Alternatives considered

### Rationale and evidence

### Consequences

### Revisit trigger

### Supersedes or superseded by

## D-20260918-reject-m5: Reject M5 completion and keep live hive mutation disabled

- Date: `2026-09-18`
- Status: `accepted`
- Decision owner: delegated independent review gate
- Related task/run/commit: `experiments/20260918T2130Z-astra-m5-review/`, commit `6efb35b`

### Context

Protomega2 claimed completion of the M5 Hive-Level Appliance implementation.
Astra reviewed the exact `85ee066..6efb35b` delta and independently tested it.

### Decision

Reject M5 completion and keep live hive-level mutation disabled until the High
findings are repaired and the exact repair commit passes independent
requalification.

### Alternatives considered

Accepting the passing authored suite as sufficient, or allowing limited live
mutation while addressing defects incrementally.

### Rationale and evidence

All 371 authored tests passed, but 29 independent defect scenarios reproduced.
The review consolidated 17 findings (13 High, 4 Medium), including broken
real-adapter/recovery integration, false healthy reporting, missing coordinated
operations, unsafe event/retry/replay behavior, and a wheel missing `hive/`.
See `experiments/20260918T2130Z-astra-m5-review/REVIEW.md` and the validated PDF.

### Consequences

Repair the adapter/health and packaging contracts first, then event semantics
and coordinated-operation safety. Re-review must be pinned to the repair commit.

### Revisit trigger

Protomega2 publishes a scoped repair commit with tests for the reproduced
failure modes and requests independent requalification.

### Supersedes or superseded by

None.


## 2026-10-06 — Only proven-owned plans can close an incident (Ben, Telegram msg 7525)
- Context: Astra review 7519 (`c876525`) Medium finding P3-ownerless: a current-format plan with no owner but linked via `IncidentReport.plan_id` could close incidents (one plan closed two).
- Decision: closure requires `plan_owner[plan_id] == incident_id` in both local (`controller/reducer.py`) and hive (`hive/reducer.py`) reducers. Linked-but-unowned plans are held via the same hold/rebind path as `owner_unproven`.
- Rejected alternative: linkage alone may close (contradicts the "only owned plans" clause of docs/POLICY_MULTI_PLAN_SUPERSESSION.md).
- Implementer: Protomega2; then one more single-reviewer Astra round. Also fix the Low health-oracle test defect (already-resolved first incident should expect UNKNOWN).


## 2026-10-07 — Linked-but-ownerless plans are held for operator rebind (Ben, Telegram msg 7547)
- Context: Astra review 7542 (`0258413`) Medium O-ownerless-hold: after 85c505d, a current-format plan linked to an incident but with no owner closes nothing, but is invisible (not in quarantined_plans()/owner_unproven, no log) and preview/rebind refuse it.
- Decision: option (a). Such plans enter the same visible hold list as owner_unproven, with the same previewed, audited operator rebind. Provisional: "first try; reconsider if it causes problems in practice".
- Rejected for now: option (b), relying on re-sending the PLAN with incident_id plus a warning log.
- Implementer: Protomega2, plus the 7542 Low test gap (F7 negative fixtures need explicit owners and valid indices). Then another single-reviewer Astra round.
