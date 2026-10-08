# Policy: multi-plan supersession

Decided by Ben Goertzel, 2026-10-06, in answer to Astra review 7195 follow-up 3
(also raised in 7173 "Multi-plan supersession").

## Rule

An incident may own more than one repair plan. **Any one owned plan that
completes closes the incident**, even if a sibling plan for the same incident
failed:

- "Completes" means every step is verified, the plan has no failed step, its
  owner is proven (not in `owner_unproven`), and no pending evidence blocks it.
- There is no newest-plan selection and no explicit `supersedes` or
  cancellation relation. A sibling failure, before or after the closure, never
  blocks the closure and never reopens the incident.
- Only plans **owned** by the incident (immutable owner, see N6) can close it.
  A plan owned by another incident cannot.
- **Ownerless plans close nothing** (Astra 7519 P3-ownerless; Ben 2026-10-07
  "ok we can try it that way"). A plan with no proven owner, e.g. a PLAN with
  an empty `incident_id`, never closes an incident, even one whose `plan_id`
  links to it. Linkage alone is not ownership. Earlier code had a linked-plan
  fallback; it was removed from both reducers.

Both the local `controller/reducer.py` and the hive `hive/reducer.py` already
behave this way. The decision makes this the specified behavior, not an
accident.

## Consequences

- The historical expectation `two_plans_one_incident_failure` in Astra's
  `experiments/*/new_cases.py` (which wanted the failed plan q retried before
  closure) is superseded by this decision. Those Astra artifacts are left
  unchanged as a record.
- **Ownerless linked plans are visible, not silent** (Astra 7542
  O-ownerless-hold). **PROVENANCE CORRECTION (Astra 7562
  D-option-conformance):** the recorded decision (Ben, Telegram msg 7547,
  2026-10-07, "option (a)") is to HOLD such plans in quarantined_plans() and
  repair them through previewed, audited preview_rebind()/rebind_plan_owner(),
  with a re-sent PLAN recording only an ownership candidate. The re-send
  repair described below is the alternative that decision rejected; it was
  built under reversed (a)/(b) labels in the 7542 thread (Ben's 2026-10-08
  "(a) is best for a first try" was answered against those reversed labels).
  Which behaviour stands is PENDING Ben's choice; this entry describes the
  code as built at this commit, not an approved policy.
  A registered plan with no owner that an open incident links to is reported
  by `Reducer.quarantine_reasons()` / `HiveReducer.quarantine_reasons()` with
  reason `ownerless_linked`, and a WARNING is logged when such a plan
  completes. `quarantined_plans()` is unchanged (owner_unproven rebind
  candidates only); `rebind_plan_owner()` still refuses these plans.
  **Repair:** send a later PLAN for the same plan id that declares
  `incident_id`; that sets the immutable owner, and the already-verified
  receipts then close that owner (only). Ownership is never inferred from
  linkage.
  **Qualifications (Astra 7562):** the WARNING fires when the plan completes
  while linked, and also when a linking INCIDENT arrives after the plan is
  already complete. quarantine_reasons() also lists incomplete linked
  ownerless plans; it has no global size cap (one entry per held plan). The
  hive reducer never prunes OPEN incidents past MAX_AGENT_INCIDENTS (only
  resolved history is trimmed), so no hold silently disappears.
- Tests: `tests/test_astra7562.py` (retention, late-link warning),
  `tests/test_astra7542.py` (ownerless_linked visibility/repair),
  `tests/test_astra7519.py` (ownerless negative controls incl.
  restore) and `tests/test_astra7195.py::test_policy_*` (local/hive agreement,
  including health, after every event).
