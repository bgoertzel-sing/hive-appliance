# Astra re-review 7638

Status: completed; production ownerless hold/rebind gate remains rejected.

Pin: `f18bc2c7349f139707d1a9de9cf673d30bdea0fc`, verified against origin/main at clone and pre-publication fetch. Single `openai/gpt-6-astra` reviewer; no fallback/delegation. Repository-operations, experiment-ledger and GitHub procedures applied.

Full suite exactly once: **746 passed in 43.16s**, runner wall time 43.56s. Final independent harness: 15/15 assertion groups, including four groups reproducing defects (two High, two Medium). Exact named-foreign receipts and ordinary hold-expiry repairs pass; unregister bypass and journal ordering prevent production approval. Default no-journal persistence remains Medium; aggregate bounds remain Low.

Historical helper exception: semantic_7133 exits 1 for three already-obsolete expectations of legacy auto-closure without operator rebind. Independent initial run: one fixture setup error (constructor sees directory); final independent rerun corrects only fixture setup/evidence detachment. No second full suite. 300-plan helper extraction updates only the superseded recovery-text assertion; adaptation recorded in final JSON.

Deterministic permutations, no random seed; event UUIDs/timestamps vary but not the semantic oracles. Offline Python guard; no paid/remote compute. No source edits, prior-evidence edits or credential changes. Runtime/software versions, exact commands, stdout/stderr/exit codes and wall times recorded. No power-loss or concurrent-writer testing claimed; fsync was wrapped/fault-injected in process and restart used fresh reducers plus JSON-serialized events.

Complete report: `docs/ASTRA_REVIEW_7638.md`. Publication is evidence/report only to the authorized repository main branch, fast-forward-only. Final commit/remote hashes are recorded after publication outside the committed manifest.
