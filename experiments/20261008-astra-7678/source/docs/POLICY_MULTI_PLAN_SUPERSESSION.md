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
- **Entry integrity.** Each rebind entry and each `abort_rebind` record
  carries `entry_hash` (SHA-256 of its other fields). A rebind line that fails
  its hash is reported unapplied ("entry content hash mismatch"). Any record
  that cannot be verified -- an unreadable or invalid line, an abort record
  that fails its hash/format check, or an abort record that names no earlier
  journaled rebind -- might have been the cancellation of an earlier rebind,
  so EVERY rebind before it is not replayed (fail-closed; reported unapplied
  and listed in `journal_status()["corrupt_records"]`). Rebinds after it are
  unaffected. These checks detect accidental and naive edits. They are NOT a
  keyed MAC: someone with write access who recomputes the hashes is not
  detected, so protect the journal and marker with file permissions.
- **Write protocol and fence.** Before each append, a fence marker
  `<journal>.fence` is written to a temp file, fsync'd, renamed into place and
  its directory fsync'd. The marker (format v2) embeds the entry and its own
  `marker_hash`. The entry is then appended and fsync'd; on success the
  marker is unlinked and the directory fsync'd. Outcomes:
  - Append write/fsync fails and the truncate-rollback is fsync'd: clean
    refusal, the marker is removed. If that removal fails the journal stays
    fenced in memory; nothing can replay because the entry is not in the
    journal.
  - Rollback fails: indeterminate. The marker is left in place (it was made
    durable before the append) and the journal is fenced in memory.
  - Entry committed but the marker unlink fails, OR the unlink succeeds and
    the directory fsync fails (so the removal may or may not survive a
    crash): the rebind is reported NOT applied, the journal is fenced in
    memory, and a durable `abort_rebind` record for the entry is appended
    (the journal file's own fsync), so a restart does not apply it whatever
    happened to the marker. If that abort record also cannot be made
    durable, the marker is re-written; `journal_status()["indeterminate"]`
    reports `abort_durable` and `marker_present`. Only if BOTH fail can the
    entry replay after a restart, and the status says so explicitly.
  - `marker_present`/`persisted` report presence in the directory listing at
    that moment, not a durability guarantee.
  While fenced (live, or a marker found at startup), new rebinds are refused.
  At startup a marker is trusted only if it parses, has format v2, its
  `marker_hash` matches, it embeds a hash-valid entry with the same `op_id`,
  and that entry is the LAST journaled rebind; then only that entry is held
  back. Any other marker (unreadable, edited, legacy format, or naming a
  different entry) fences EVERY journaled rebind. A leftover
  `<journal>.fence.tmp` (never renamed into place) means the append never
  started; it is deleted.
- **Clearing a fence.** Inspect the journal and the marker, then call
  `clear_journal_fence(actor=..., reason=...)`. It FIRST appends durable
  `abort_rebind` records -- for the marker's entry if the marker is trusted,
  and, if the marker is untrusted or does not name the last journaled
  rebind, also for the last journaled rebind -- and only then removes the
  marker, so losing the removal cannot bring the entry back. If an abort
  record or the directory fsync after the removal fails, it raises and the
  journal stays fenced in memory. The clearance is recorded in
  `journal_status()["fence_clearances"]`. Aborted entries are never replayed;
  re-issue the rebind afterwards if it is still wanted.
- **Torn tail.** An unterminated last line is copied to
  `<journal>.torn-<ns>`. The copy is fully written, fsync'd, read back and
  compared, and its directory entry fsync'd, BEFORE the journal is truncated.
  This happens at startup and before every append. If a step fails BEFORE the
  truncate, the journal bytes are untouched and the rebind is refused (or
  startup raises). If the truncate succeeds but the journal's following fsync
  fails, the journal may already be truncated (on disk the old length may or
  may not survive a crash); the fragment is preserved in the verified,
  durable aside file and the rebind is refused.
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
- Tests: `tests/test_astra7638.py`, `tests/test_astra7656.py`,
  `tests/test_astra7669.py`.

