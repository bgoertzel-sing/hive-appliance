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
- **Ownerless linked plans are HELD and repaired by audited rebind** (Ben,
  Telegram msg 7547, 2026-10-07, "option (a)"; implemented after Astra 7562
  D-option-conformance on Ben's 2026-10-08 instruction "implement the hold
  and rebind workflow"). History: the 7542 thread used reversed (a)/(b)
  labels and first shipped a re-send repair (57a6298/1a4f740); that path is
  REMOVED.
  A registered plan with no owner that an open incident links to via
  plan_id is HELD: it is listed by `quarantined_plans()` and by
  `quarantine_reasons()` with reason `ownerless_linked` (local `Reducer` and
  `HiveReducer`, keys `plan_id` / `agent:plan_id`), and a WARNING is logged
  when such a plan completes or when a linking INCIDENT arrives after it is
  complete. Linkage is never treated as ownership; the plan closes nothing.
  **Re-sent PLAN:** a later PLAN declaring `incident_id` for a held plan does
  NOT set the owner; it only records an owner CANDIDATE (local:
  `migration_diagnostics["owner_candidates"]`; hive: `owner_candidates`).
  **Repair:** `preview_rebind()` (side-effect free; reports hold_reason,
  candidates, held receipts, would_close) then the trusted-operator
  `rebind_plan_owner(..., actor=, reason=)`, which requires a non-empty actor
  and reason, an existing OPEN target not linked to another plan, and a
  recorded candidate unless `allow_non_candidate=True`. Each rebind appends an
  audit record (actor, reason, candidate, hold_reason, held receipts, closed)
  and then closes the new owner only. The same workflow already applied to
  `owner_unproven` (legacy migration) plans.
  **Qualifications (Astra 7562):** quarantine_reasons() also lists incomplete
  linked ownerless plans; it has no global size cap (one entry per held
  plan). The hive reducer never prunes OPEN incidents past
  MAX_AGENT_INCIDENTS (only resolved history is trimmed), so no hold silently
  disappears. Hive owner_candidates/owner_rebinds are in-memory (the hive
  reducer has no snapshot/restore).
- Tests: `tests/test_astra7562_hold.py` (hold/candidate/preview/audited
  rebind, both reducers), `tests/test_astra7562.py` (retention, late-link
  warning), `tests/test_astra7542.py` (ownerless_linked visibility; re-send
  is candidate-only),
  `tests/test_astra7519.py` (ownerless negative controls incl.
  restore) and `tests/test_astra7195.py::test_policy_*` (local/hive agreement,
  including health, after every event).
