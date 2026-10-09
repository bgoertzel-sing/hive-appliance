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

## Hive rebind journal: recovery, fencing and migration (Astra 7638/7656/7678)

- **Configuration.** `HiveAppliance(rebind_journal=PATH)` or the
  `HIVE_REBIND_JOURNAL` environment variable (an explicit argument wins).
  Without a journal `HiveAppliance` REFUSES rebinds unless
  `volatile_rebinds=True` is passed. A bare `HiveReducer()` still allows
  volatile rebinds.
- **Replay model.** A restart must replay the FULL hive event stream from the
  beginning. Each rebind record (format v4) records the event-stream position (`seq`)
  and a SHA-256 hash chain over the canonical CONTENT of every reduced event
  (id, kind, ts, source, subject, payload, severity, schema version). An entry
  is re-applied only at exactly that position and only if the replayed stream
  hashes the same. Otherwise it is listed in
  `journal_status()["unapplied"]` and the operator must re-issue it. Rejected
  conflicting PLANs (7146 N6) do not advance the position. Snapshot or partial
  (suffix) restore is NOT supported: entries stay pending or are reported as
  unapplied.
- **Commit-record journal (Astra 7678).** Each rebind is written as a
  `rebind_pending` record, then, once that is durable, a `rebind_commit`
  record naming it (`op_id` plus the pending record's hash). Only rebinds
  with a valid commit record are replayed; a pending record without one (the
  rebind was refused, or the process stopped between the two writes) is
  listed in `unapplied` with "no commit record" and never replays. There are
  no cancel/abort records and no fence marker file.
- **Record integrity and chain.** Every record carries `prev` (the
  `rec_hash` of the record before it, `""` for the first) and its own
  `rec_hash` (SHA-256 of all its other fields). A reordered, removed,
  inserted or edited record therefore breaks the chain. These hashes detect
  accidental and naive edits; they are NOT a keyed MAC (someone with write
  access who recomputes every hash is not detected), so protect the journal
  with file permissions.
- **Fail closed on the whole journal.** At startup, if ANY record cannot be
  verified -- an unreadable line, a hash mismatch, a broken chain, a legacy
  or unknown format, a commit naming no earlier pending record or not
  matching it, a duplicate, or an unterminated (torn) last line, including a
  record missing only its final newline -- NO journaled rebind is replayed.
  The journal is reported unhealthy (`journal_status()["healthy"]` False,
  `fence` says why, `corrupt_records` gives the line) and every new rebind is
  refused. The journal is never trimmed or repaired, so it fences again after
  every restart until an operator clears it. A leftover legacy
  `<journal>.fence` file also fences everything.
- **Write failures.** Each record is appended and fsync'd; on failure the
  partial write is truncated away and that truncation fsync'd.
  - Pending write fails, rollback OK: clean refusal, journal stays healthy.
  - Pending write fails AND rollback fails: refused and fenced (unhealthy).
    The record may be on disk, possibly torn, but it has no commit, so it can
    never replay; a torn tail fences the journal at the next start.
  - Commit write fails, rollback OK: clean refusal; the pending record stays
    on disk without a commit and never replays. Journal stays healthy.
  - Commit write fails AND rollback fails: the commit may or may not be
    durable, so a refusal could be contradicted by a restart. The rebind is
    therefore APPLIED and reported as applied (`True`), and the journal is
    fenced (`fence.kind == "commit_uncertain"`, `applied: True`). After a
    restart it is either replayed (commit survived), held again (commit
    lost) or the whole journal is fenced (commit torn) -- never a refused
    rebind coming back.
  - Before every write the journal must still be exactly what this process
    last wrote (size and last record). Otherwise (changed, truncated,
    removed or torn from outside) nothing is written and the journal is
    fenced (`changed`).
  - A journal that cannot be created or read at startup is fenced
    (`unwritable`): the process reports unhealthy and refuses rebinds.
- **Clearing a fence.** Inspect the journal, then call
  `clear_journal_fence(actor=..., reason=...)`. It copies the old journal
  byte-for-byte to `<journal>.fenced-<ns>` (fsync'd, directory fsync'd),
  then atomically replaces the journal with a new one that starts with a
  `journal_reset` record (actor, reason, archive path) and re-journals, as
  pending + commit pairs, exactly the rebinds this process holds applied or
  still awaiting their event position, so a restart matches the running
  state. Rebinds in the old journal that were not applied are NOT carried
  over: re-issue them if still wanted. Any failure raises and the journal
  stays fenced. Clearances are listed in
  `journal_status()["fence_clearances"]`.
- **Upgrading (behaviour change).** v1-v3 journals are legacy format and
  fence the whole journal at the first start after upgrading: nothing in them
  is replayed. Review the journal, clear the fence, and re-issue each rebind
  that is still wanted with `rebind_plan_owner()`.
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
  `tests/test_astra7678.py`.

