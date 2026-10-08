# Evidence index — Astra 7678

Reviewed pin: `2e63084dbdecd8f3ea0bb23472a8f57be24e57d4` (parent `7008f0a`). Sole verified reviewer `openai/gpt-6-astra`, no delegation/fallback. Production ownerless hold/rebind **NOT APPROVED**.

- `review7678.py` / `.json` / `-summary.json`: 27 primary assertion groups; exact 7669 witnesses with fixed-outcome assertions, retained semantics and real caps. `witness-adaptation.diff` exposes every adaptation.
- `followup7678.py` / `.json` / `-summary.json`: 9 focused groups, including whole-live-state comparison, compound failure, exact abort edit, temporal corruption scope, torn cancellation, two-entry fences and v1 migration. Assertions include reproduced defects, not just conformance passes.
- `pytest.stdout`, `pytest-exit.json`, `run_primary.py`: sole full suite, **782 passed in 47.93s**; historical probes also executed once.
- `RUN.md`, `commands.sh`, `environment.json`, `model-verification.json`: ledger, commands, environment and before/near-end own-session model/provider evidence.
- `source/production.diff`, `source/`, `source-verification*.json`, `copy-provenance.json`, `helper-adaptations.json`: complete four-file diff/selected inputs, 148 pinned byte-identical non-experiment files, copied/extracted helper provenance.
- `static7678.py`, `static-review.json`, `production-wiring-search.json`, `offline-verification.json`: source/docs/caller audit, guard and offline-wheel verification; prior 7669 manifest has 315 verified artifact/report hashes.
- `journal-7678/`, `journal-followup7678/`, `journal-cases/`: real probe journals, markers, cancels and aside fragments. Invalid UTF-8/torn bytes are intentional. Empty `journal-7669/`/`journal-followup7669/` created by retained definitions are not publication artifacts.
- `semantic-summary.json`: unchanged legacy semantic harness exits 1 for three obsolete automatic-close expectations; current/prior/legacy fail-closed sweeps pass. Raw failures retained.
- Retained `review7173`, `review7195` and nested primary controls include 1,440 owned supersession and 144 hold/rebind schedules.
- `publication-checks.json`, `staging-checks.json`, `SHA256SUMS`, `verify_evidence.py`: publication scope, high-confidence credential-pattern checks and complete artifact/report manifest.

## Reproduction

Use a **fresh** evidence directory: runner logs are exclusive and journals append. Copy the scripts/guard and provide the three wheels identified by `build-prerequisites.json`. Set `HIVE_SRC` to a clean detached checkout of the pin. Follow `commands.sh` with adjusted paths. `run_primary.py` runs the full suite exactly once; primary/followup/static are independent scripts. `source/` is a selected input archive, not a complete checkout.

Old review/followup/static scripts are retained definitions/inputs, **not extra mains to execute**; their historical mains intentionally expect old defects. The unchanged retained helper adaptations from 7669 remain recorded: sole 300-plan recovery-text assertion change, three 600-hold candidate-cap changes. No production/test edits.

Python socket guard permits only loopback/Unix, pip offline; not an OS-wide sandbox. Installed build 1.5.0 differs from declared 1.6.1. UUIDs/time vary; schedule oracles deterministic. Fault/crash probes are local injected syscalls/abrupt exceptions plus fresh reducers, not physical power loss. No paid/remote compute.

Exact 7669 OPEN witnesses are closed. New/residual Medium findings: cancellation final-newline loss revives cancelled entry (F-abort-tail); compound abort/marker failure revives refused entry (F-journal-refused-compound); authentic cancellation displaced before target revives it (F-abort-order-scope, explicitly stronger storage-order precondition). Honest compound-failure status and passing intact-order controls are recorded, not hidden.

Disposable build/test files, bytecode, third-party wheels and large padding fixtures excluded with recipe/hash evidence retained. From repository root: `python3 experiments/20261008-astra-7678/verify_evidence.py`. Post-push local/fetched-remote hashes recorded outside this manifest to avoid self-reference.
