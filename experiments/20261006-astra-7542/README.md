# Astra 7542 evidence

Reviewed pin: **85c505d1608680f1ac965ad5fad46a573c032b35**, equal to `origin/main` at initial clean clone. Model: **gpt-6-astra**, confirmed by runtime session metadata in `model-verification.json`. One reviewer, no delegation. Report: [ASTRA_REVIEW_7542.md](../../docs/ASTRA_REVIEW_7542.md).

## Findings and actual outcomes

- **P3-ownerless CLOSED:** exact prior witness + 180 ownerless schedules / 1,224 per-event states; six positive owned controls; retained 1,440 supersession schedules / 15,840 states.
- **O-ownerless-hold OPEN, Medium operability:** no actionable quarantine/owner diagnostic; preview/rebind refuse. Ordinary later PLAN with first nonempty owner repairs using existing progress, so this is not an irreparable condition. No pending buildup for registered linked ownerless plans (three 1,024-receipt controls); 1,024 late-plan pending receipts drain to zero.
- **H-oracle-resolved CLOSED:** UNKNOWN first-resolved arrival, HEALTHY same-event open/close, all five original health-only mutants detected.
- **L-F7-negative-fixtures OPEN, Low:** legitimate positive fixture adaptation, but neighboring ownerless negative fixtures do not test composite completion. All three old F7 tests miss removal of the cardinality guard; independent owned incomplete-plan control catches it.
- **Full suite once: 717 passed / 1 failed / 718 collected.** Offline wheel-build dependency provisioning fails (`No matching distribution found for wheel`). Not a passing packaging qualification.
- Retained N1–N10/H2/quarantine safety scopes pass. Unchanged `semantic_7133.py` exits 1 for three already-known obsolete automatic legacy-recovery expectations; manual repair controls pass. No failed outcome was discarded.

## Commands and evidence structure

`commands.sh` is an audit of exact child commands/cwds; `*-started.json` records each before launch and `*-exit.json`, `.stdout`, `.stderr` preserve its result. **Eleven primary test children**: one full pytest, the nine retained helper invocations, and `review7542.py`. Clone, branch creation and source audit also have start/exit records. Read-only interactive inspection commands are not represented as test children.

`prepare.py` prepared the clean clone's source export and copied prior helpers. It is workspace-specific, not a portable replayer. The full-suite child was launched through `runner.run('pytest', [...])`; `execute_regressions.py` launches retained helpers. `review7542.py` executes only the definition prefix of the unchanged `review7519.py`: quarantine, supersession, foreign-owner and health groups. It intentionally does NOT execute the old helper's final group asserting the defects still exist. `retained-extraction.json` identifies that exact selection and its hash.

Important artifacts:

- `review7542.json`, `ownerless-witness.json`, `ownerless-schedules.json`, `policy-schedules.json`: current witnesses, positive controls, repair/log state, independent literal expectations and mutations.
- `authentic-300-before.json`: authentic e6afe16 → ef18db3 quarantine migration fixture; current membership 300 → 151 → 0, historical sample 256, 20 round trips at each stage.
- `semantic-summary.json`, `review7173-summary.json`, `review7195-summary.json`, `new-cases-summary.json`, retained raw outputs/checkpoints: scoped regression evidence.
- `source/`, `source-sha256.json`, `production.diff`, `git-source-audit.json`: reviewed tracked source (excluding old experiment directories), complete requested six-file diff, Git history and original F7 test.
- `copy-provenance.json`: byte-identical retained 7519 helpers. `new_cases.py` already carries 7519's documented Ben-policy supersession adaptation; this review makes no further change. Original evidence is untouched.
- `prepush-validation.json`, `SHA256SUMS`, `final-integrity.json`: publication scope, pattern scan and integrity. Source snapshots, logs and checkpoints are included; disposable `tmp/`, `pytest-tmp/`, Python caches and untracked build products are excluded.

Local restart means real JSON snapshot/restore. **Hive has no snapshot API:** restart means serialized ordered event-prefix replay, never a claimed hive checkpoint restore.

## Environment and reproduction

Python 3.10.12; package versions/platform in `environment.json`. No dependency install or credential change. Test children set `PYTHONDONTWRITEBYTECODE=1`, `PIP_NO_INDEX=1`, `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, `ANONYMIZED_TELEMETRY=False`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, `TMPDIR=<output>/tmp`, `PYTHONPATH=<output>/guard`, `HIVE_SRC=<output>/source`. The inherited socket guard blocks external Python connects; it is not an OS sandbox. Retained controls exercise bounded temporary local shell/filesystem paths, not live repairs.

Verify the published copy:

```sh
python3 verify_evidence.py
```

Replay into a **new** directory, without overwriting evidence:

```sh
python3 replay.py /absolute/path/to/new-output
# Optional separate reproduction of the full suite:
python3 replay.py /absolute/path/to/another-new-output --include-pytest
```

The replayer is supplied but was not rerun during this review. All outcomes, including known obsolete legacy expectations and any offline packaging failure, remain in the new output. A helper exiting zero may mean it successfully reproduced a reported finding, not that the finding is closed.

`model-provider-verification.json` also confirms provider `openai` / API `openai-responses` from the reviewer's own transcript. `publication-checks.json` retains expected whitespace warnings in copied source, raw diff/logs and runner EOF; those evidence bytes were not normalized.
