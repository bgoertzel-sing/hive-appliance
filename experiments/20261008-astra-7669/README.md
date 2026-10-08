# Evidence index — Astra 7669

Reviewed pin: `d0fc184d6cbbd6381243d55901219b6b1ba41721` (parent `7a372c3`). Sole verified reviewer `openai/gpt-6-astra`. Production ownerless hold/rebind **NOT APPROVED**.

- `review7669.py` / `.json` / `-summary.json`: 27 independent assertion groups, including explicitly reproduced defects. Not 27 safety approvals.
- `followup7669.py` / `.json`: four focused groups: prior-record rollback, startup fsync, corrupt abort ID, complete matching marker clearance.
- `pytest.stdout`, `pytest-exit.json`, `run_primary.py`: sole full suite, **774 passed in 47.23s**; retained historical probes also executed.
- `RUN.md`, `environment.json`, `commands.sh`, `model-verification.json`: ledger, environment, exact execution sequence and own-session model/provider evidence.
- `source/production.diff`, `source/`, `source-verification*.json`, `copy-provenance.json`, `helper-adaptations.json`: complete diff/selected input archive, 146 pinned byte-identical non-experiment files, copied-input and extracted-helper provenance.
- `static7669.py`, `static-review.json`, `production-wiring-search.json`, `offline-verification.json`: source/docs/caller audit, guard and build-wheel verification. Prior 7656 manifest: 243 hashes verified.
- `journal-7669/`, `journal-followup7669/`, `journal-cases/`: actual normal/fault/migration/corrupt journals and marker fixtures. Invalid UTF-8 and torn fragments are intentional. Paths refer to original run locations.
- `semantic-summary.json`: three unchanged obsolete legacy auto-closure expectations fail (raw exit 1 retained); current/prior/legacy fail-closed sweeps pass.
- Retained `review7173`, `review7195` and primary nested controls include 1,440 owned supersession and 144 hold/rebind schedules.
- `publication-checks.json`, `staging-checks.json`, `SHA256SUMS`, `verify_evidence.py`: delivered integrity and credential-pattern checks.

## Reproduction

Use a **fresh** evidence directory: runner logs are exclusive and journals append. Copy Python helpers and `guard/`, provide the three wheels identified by `build-prerequisites.json`, and set `HIVE_SRC` to a clean detached checkout of the pin. Follow `commands.sh` with adjusted paths. `run_primary.py` runs pytest exactly once; primary/followup/static scripts are separate independent checks. `source/` is an input archive, not a complete checkout. Old `review*.py`/`followup*.py` files are retained definitions/inputs, **not additional scripts to execute**: their historical main blocks intentionally expect old defects. Copied `static7656.py` is historical input, not a current audit.

The 600-hold helper uses the same three recorded candidate-cap substitutions as 7656; the 300-plan helper uses only its recorded recovery-text assertion adaptation. No production/test edits. Network guard permits Python loopback/Unix connections only, pip offline; no paid/remote compute. Installed build 1.5.0 differs from requirements-dev 1.6.1. UUIDs/timestamps vary, schedule oracles are deterministic. Crash probes are abrupt exception/control-flow escape plus fresh reducers, not physical power-loss tests.

Known OPEN Medium witnesses: fence unlink succeeds but parent fsync fails; parseable fence operation-ID corruption; one-character abort operation-ID corruption. OPEN Low: recovery docs overstate unchanged-original/persistent-marker failure behavior. Other exact prior OPEN witnesses are repaired/scoped in the report.

Disposable test/build directories, bytecode, third-party wheels and large padding fixtures are excluded with hashes/recipes retained. Read-only verification from repository root: `python3 experiments/20261008-astra-7669/verify_evidence.py`. Post-push commit/remote hashes are recorded outside the manifest.
