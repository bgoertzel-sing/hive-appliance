# Astra 7734 execution ledger

Status: completed; production gate **NOT APPROVED** (one remaining Medium durability-status finding and one new Low diagnostic finding).

- Reviewer: `openai/gpt-6-astra`, provider openai, independently verified runtime metadata; no delegation.
- Pin: `8c54bdf2ee26675dcaa4362b2197d167cb3d0241`; diff `1a33645..8c54bdf`, code also compared to `7ce5cd5`. Fetch rechecked after review: origin/main unchanged.
- Source: exact Git-blob export `/tmp/hive-astra-7734-source`; 159 non-experiment files verified before/after against export, Git and repository. Historical evidence linked read-only-use.
- Purpose: requalify intent presence/durability diagnostics, reset interruption and recovery invariants; retained journal and semantic regressions.
- Execution: local CPU, Python socket guard, PIP_NO_INDEX, existing hashed wheels; no dependency downloads or paid/remote compute. Environment allowlist only.
- Commands: [commands.sh](commands.sh); setup exporter: [setup7734.py](setup7734.py). Exclusive started/exit JSON + stdout/stderr per substantive run; command ledger requires a fresh evidence namespace to reproduce.
- Temporary files: `/tmp/hive-astra-7734-runtime` and pytest basetemp under `/tmp`. Journal/checkpoint files retained under evidence are deliberate result fixtures, not temporary build files.

## Executions

| Run | Exit | Wall seconds |
|---|---:|---:|
| pytest | 0 | 49.8351 |
| review7195 | 0 | 1.7729 |
| review7173 | 0 | 2.4853 |
| boundary-and-disk | 0 | 0.1650 |
| mechanism-probes | 0 | 0.2653 |
| probes | 1 | 0.2656 |
| older-regressions | 1 | 0.2152 |
| independent | 1 | 0.1649 |
| new-cases | 0 | 0.4162 |
| semantic-7133 | 1 | 6.2502 |
| intent7734 | 0 | 6.8055 |
| review7694 | 0 | 6.7564 |
| followup7694 | 0 | 0.7679 |
| focused7701 | 0 | 0.4162 |
| startup7708 | 0 | 0.4666 |
| startup_recovery_final7708 | 0 | 0.3660 |
| clearance7701 | 0 | 1.1711 |
| marker7701 | 0 | 0.2655 |
| recovery7708 | 0 | 0.3661 |
| reset7718 | 0 | 4.5425 |
| source-and-prior-verification | 0 | 0.7174 |
| exact_restore_final7718 | 0 | 0.2653 |
| intent-final7727 | 0 | 4.6907 |
| extra-io7727 | 0 | 1.3206 |
| probes-final | 0 | 0.6174 |
| older-regressions-final | 0 | 0.2650 |
| independent-final | 0 | 0.3162 |
| metadata7734 | 0 | 0.3158 |
| static7734 | 0 | 0.4197 |
| secret-scan | See secret-scan-exit.json | See secret-scan-exit.json |

## Results and interpretation

Full suite exactly once: **824 passed in 49.33 s**, runner wall **49.8351 s**, exit 0. Retained schedules: 1,440 supersession / 15,840 event-prefix checks; 144 hold/rebind / 1,152 checks. Primary 16/16 and focused 8/8.

Retained reset evidence: 208 interruptions, 104 error recoveries, 42 intent combinations, 72 intent-clearance interruptions, 48 same-process retries and 48 direct live-feed errors; 48 extra I/O failures plus four anchor read/open failures. Unchanged 24/28 mutation traces explain unchanged retained counts.

Current intent trace: new 48 calls / existing 46 calls; 376 syscall interruptions plus eight helper boundaries = 384. Four additional fsync/cleanup-denial configurations; genuine mode-000 failure and permission-repair retry. Two stat EIO/EACCES witnesses retain the Medium durability-status defect: directory-only fsync produces a positive file-and-directory assurance. Two regular-file lstat controls still fsync both. Two metadata-error witnesses expose false presence/unchanged-pair/unlinked text (Low); two nonregular controls document directory-only confirmation wording.

Prior manifests: 315 / 351 / 355 / 829 / 1,189 / 2,221 / 3,913 artifact hashes verified for 7669–7727 selected rounds. Source pin unchanged after a final fetch.

Nonzero runs: semantic-7133 retains three obsolete automatic-closure expectations (all current/prior 3,072-case sweeps, 384 legacy cases and lifecycle checks pass). Initial probes, older-regressions and independent fail solely on an absent evidence-local temporary directory; separate final copies use /tmp, preserve original result files and pass. Original failures, corrected harness copies and tempdir adaptation diff retained. Initial shell command from wrong cwd failed to locate scripts before any test execution; setup-errors.json records it. No full-suite rerun.

Secret scan: [secret-scan.json](secret-scan.json), with exclusive execution logs. Manifest/verifier are generated after all content; read-only verifier checks hashes, complete coverage, 30 execution ledgers and semantic evidence. Injected syscall boundaries and persistence models are not hardware power-cut proof. No source/test/scratch modifications, staging, commit or push.
