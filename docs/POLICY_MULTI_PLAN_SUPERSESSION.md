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
  disappears. Hive owner_candidates are in-memory (the hive reducer has no
  snapshot/restore); owner_rebinds are made durable by the rebind journal
  (see "Hive rebind journal" below).
- Tests: `tests/test_astra7562_hold.py` (hold/candidate/preview/audited
  rebind, both reducers), `tests/test_astra7562.py` (retention, late-link
  warning), `tests/test_astra7542.py` (ownerless_linked visibility; re-send
  is candidate-only),
  `tests/test_astra7519.py` (ownerless negative controls incl.
  restore) and `tests/test_astra7195.py::test_policy_*` (local/hive agreement,
  including health, after every event).

## Hive rebind journal: recovery, fencing and migration (Astra 7638/7656)

- **Configuration.** `HiveAppliance(rebind_journal=PATH)` or the
  `HIVE_REBIND_JOURNAL` environment variable (an explicit argument wins).
  Without a journal `HiveAppliance` REFUSES rebinds unless
  `volatile_rebinds=True` is passed. A bare `HiveReducer()` still allows
  volatile rebinds.
- **Replay model.** A restart must replay the FULL hive event stream from the
  beginning. Each entry (format v3) records the event-stream position (`seq`)
  and a SHA-256 hash chain over the canonical CONTENT of every reduced event
  (id, kind, ts, source, subject, payload, severity, schema version). An entry
  is re-applied only at exactly that position and only if the replayed stream
  hashes the same. Otherwise it is listed in
  `journal_status()["unapplied"]` and the operator must re-issue it. Rejected
  conflicting PLANs (7146 N6) do not advance the position. Snapshot or partial
  (suffix) restore is NOT supported: entries stay pending or are reported as
  unapplied.
- **Entry integrity.** Each entry carries `entry_hash` (SHA-256 of its other
  fields). An edited or corrupted line is reported unapplied ("entry content
  hash mismatch") and is not replayed. This detects accidental and naive
  edits. It is NOT a keyed MAC: someone with write access who recomputes the
  hash is not detected, so protect the journal with file permissions.
- **Write protocol and fence.** Before each append, a fence marker
  `<journal>.fence` (containing the entry) is written, fsync'd and renamed into
  place. The entry is then appended and fsync'd. On success the marker is
  removed. If the write or fsync fails, the entry is truncated away (clean
  refusal) and the marker removed. If the rollback or the marker removal
  fails, the outcome is indeterminate: the marker STAYS on disk. While a
  marker exists (live or found at startup), that entry is not replayed and all
  new rebinds are refused (`journal_status()["indeterminate"]`). An unreadable
  marker fences every journaled rebind. A leftover `<journal>.fence.tmp` (never
  renamed into place) means the append never started; it is deleted.
- **Clearing a fence.** Inspect the journal and the marker, then call
  `clear_journal_fence(actor=..., reason=...)`. It appends a durable
  `abort_rebind` record for the uncertain entry (or, for an unreadable marker,
  the last journaled rebind), removes the marker, and records the clearance in
  `journal_status()["fence_clearances"]`. The aborted entry is never replayed.
  Re-issue the rebind afterwards if it is still wanted.
- **Torn tail.** An unterminated last line is copied to
  `<journal>.torn-<ns>`. The copy is fully written, fsync'd, read back and
  compared, and its directory entry fsync'd, BEFORE the journal is truncated.
  This happens at startup and before every append. If any step fails, the
  journal is left untouched and the rebind is refused.
- **Legacy entries.** v1 (no position) and v2 (id-only stream hash, no
  entry hash) entries are NOT replayed after upgrading. They appear in
  `unapplied` with "legacy entry (format vN)". Migration: review them, then
  re-issue each rebind that is still wanted with `rebind_plan_owner()`. The new
  v3 entry replays normally, and the legacy diagnostic stays visible.
- **Caps and observability.** `MAX_HIVE_JOURNAL_BYTES` (64 MiB, append
  admission; rotate or compact offline when it is reached),
  `MAX_HIVE_CANDIDATE_KEYS` (256; the hold itself is never dropped), and
  `MAX_HIVE_PLANS` (10,000 tracked plans; above it a new PLAN is refused and
  its incident stays OPEN, counted in `plans_refused_cap`). `journal_status()`
  lists the newest 200 unapplied records plus `unapplied_total` and
  `unapplied_omitted`. `journal_unapplied()` returns all retained dispositions
  (up to `MAX_HIVE_UNAPPLIED_RECORDS`). Holds, open incidents and plan
  provenance below these caps are deliberately never dropped.
- Tests: `tests/test_astra7638.py`, `tests/test_astra7656.py`.

