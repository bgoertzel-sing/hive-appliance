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
  O-ownerless-hold, option (a); Ben 2026-10-08 "(a) is best for a first try").
  A registered plan with no owner that an open incident links to is reported
  by `Reducer.quarantine_reasons()` / `HiveReducer.quarantine_reasons()` with
  reason `ownerless_linked`, and a WARNING is logged when such a plan
  completes. `quarantined_plans()` is unchanged (owner_unproven rebind
  candidates only); `rebind_plan_owner()` still refuses these plans.
  **Repair:** send a later PLAN for the same plan id that declares
  `incident_id`; that sets the immutable owner, and the already-verified
  receipts then close that owner (only). Ownership is never inferred from
  linkage. Full hold/rebind (option (b)) is deferred unless (a) causes
  problems in practice.
- Tests: `tests/test_astra7542.py` (ownerless_linked visibility/repair),
  `tests/test_astra7519.py` (ownerless negative controls incl.
  restore) and `tests/test_astra7195.py::test_policy_*` (local/hive agreement,
  including health, after every event).
