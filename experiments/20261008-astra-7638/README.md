# Evidence index — Astra 7638

Reviewed source: `f18bc2c7349f139707d1a9de9cf673d30bdea0fc`.

- `review7638-final.json` / `.py`: final independent controls and reproduced findings, 15 groups. Assertions on defect groups establish reproduction, not safety.
- `review7638.json` / `.py`: initial run, retained with its directory-at-construction fixture error. Final version fixes that setup and detached owner-map capture; no product edits.
- `journal-cases-final/`: actual normal/fault/corrupt JSONL fixtures. Invalid UTF-8 is intentional.
- `pytest.stdout`, `pytest-exit.json`, `run_primary.py`: sole full-suite execution, 746 passed; unchanged historical regression helpers and raw outputs follow.
- `RUN.md`, `environment.json`, `model-verification.json`, `commands.sh`: execution context, genuine Astra confirmation, commands and limitations.
- `source/`, `production.diff`, `source-verification.json`, `copy-provenance.json`: reviewed inputs and hashes. Full source is recoverable from the public Git pin; archived source is the five changed files plus policy/setup inputs, not a standalone checkout.
- `semantic-summary.json`: three explicitly retained obsolete legacy-auto-close expectations fail; current/prior/legacy semantic sweeps pass.
- `review7173.json`, `review7195.json`, `policy-schedules.json`, `ownerless-schedules.json`: retained safety evidence. Shared generated helper outputs reflect the final independent run where rerun.
- `SHA256SUMS`, `verify_evidence.py`, `publication-checks.json`: delivered integrity and credential-pattern checks.

## Reproduction

Use a fresh evidence directory (runner logs use exclusive creation). Copy the helper `.py` files and `guard/`, provide the build dependencies listed in `build-prerequisites.json`, and set `HIVE_SRC` to a clean checkout of the pin. `run_primary.py` executes the full suite once plus historical probes; `review7638-final.py` executes the scoped re-review. Original absolute argv/cwd appear in each `*-started.json`. Network is blocked for Python except loopback/Unix sockets. Do not rerun into this archived directory: journal fixtures deliberately append.

Test/build scratch, bytecode, and third-party wheels were not published. Build-wheel hashes remain; build 1.5.0 was actually used. Verification is read-only: `python3 experiments/20261008-astra-7638/verify_evidence.py` from the repository root.
