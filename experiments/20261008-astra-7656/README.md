# Evidence index — Astra 7656

Reviewed pin: `647fac6fd46f950ab00301aba75dc10900baf1e9` (parent `ff692b9`). Sole reviewer `openai/gpt-6-astra`; production hold/rebind **NOT APPROVED**.

- `review7656.py` / `.json`: 20 independent assertion groups; reproduced defects are asserted, not hidden as conformance passes.
- `followup7656.py` / `.json`: exact old all-fsync-fail injection, rollback preserving a prior entry, startup fsync boundaries, bounded unapplied diagnostics. **Final F-journal-content severity is Medium**, superseding the initial High label in raw primary results because changed payloads violate the immutable-event convention.
- `pytest.stdout`, `pytest-exit.json`, `run_primary.py`: sole full suite, **764 passed in 48.31s**; retained historical helpers also run here. No second full suite.
- `RUN.md`, `environment.json`, `model-verification.json`, `commands.sh`: execution ledger, environment, confirmed reviewer and exact commands.
- `source/production.diff`, `source/`, `source-verification*.json`, `copy-provenance.json`: full reviewed diff, selected source archive, byte-identical source verification and copied-helper provenance.
- `static7656.py`, `static-review.json`, `production-wiring-search.json`: caller/documentation audit; 144 unchanged product files and prior 7638 manifest verification.
- `journal-cases/`, `journal-followup/`: actual normal/refused/corrupt/legacy journal fixtures. Invalid UTF-8 and truncated fragments are intentional. Diagnostic paths refer to original run locations.
- `semantic-summary.json`: three known obsolete legacy auto-closure expectations fail; current/prior/legacy fail-closed sweeps pass. Raw output/exit 1 is retained.
- `review7173*.json`, `review7195*.json`, `policy-schedules.json`, `ownerless-schedules.json`: retained semantic controls, including 1,440 owned and 144 hold/rebind schedules.
- `publication-checks.json`, `staging-checks.json`, `SHA256SUMS`, `verify_evidence.py`: delivered integrity/credential checks.

## Reproduction

Use a **fresh** evidence directory because runner logs are exclusive and journals deliberately append. Copy archived Python helpers and `guard/`; supply the three build wheels identified in `build-prerequisites.json`; set `HIVE_SRC` to a clean checkout of the pin. Use the sequence in `commands.sh`, replacing original absolute paths. `run_primary.py` runs the suite once plus historical probes; the three subsequent runner calls are independent/focused/static checks. `source/` is an input archive, not a complete checkout. Earlier `review*.py` files are retained definitions/inputs; do not independently run every historical script or mistake old defect expectations for current claims.

The 600-hold helper is extracted with three recorded candidate-cap substitutions. The 300-plan helper uses only the already-recorded recovery-text assertion update. No source/test edits. Python network guard permits only loopback/Unix sockets; no paid/remote compute. UUIDs/timestamps vary, schedule oracles are deterministic. Installed build is 1.5.0 rather than the declared 1.6.1.

Disposable test/build directories, bytecode, third-party wheels and five large journal padding fixtures are not published; generation recipes, exact sizes and hashes remain. Read-only delivered verification from repository root: `python3 experiments/20261008-astra-7656/verify_evidence.py`. Post-push commit/remote hashes are recorded outside the committed manifest.
