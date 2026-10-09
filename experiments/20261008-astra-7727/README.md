# Astra 7727 evidence index

Pin: `7ce5cd5c2c3289ee1ce9f50c2683854e038df0d0`. Sole reviewer: verified **openai/gpt-6-astra**. [Report](../../docs/ASTRA_REVIEW_7727.md). **NOT APPROVED**: the two 7718 defects are fixed within the established-intent/failed-live-reset scopes; new **F-reset-intent-durability-status — OPEN Medium** incorrectly equates visible marker presence with durable intent.

## Execution and provenance

- [RUN.md](RUN.md), [commands.sh](commands.sh), [runner.py](runner.py): exact execution ledger and exclusive started/exit JSON plus stdout/stderr for 24 runs.
- [model-verification.json](model-verification.json), [environment.json](environment.json), [offline-verification.json](offline-verification.json).
- [pytest.stdout](pytest.stdout), [pytest-exit.json](pytest-exit.json): suite once, **817 passed**.
- [source-verification-before.json](source-verification-before.json), [source-verification.json](source-verification.json): all 157 tracked non-experiment files match Git blobs and original hashes.
- [copy-provenance.json](copy-provenance.json), [adaptation-7727.diff](adaptation-7727.diff): copied 7718 scripts and all adaptations. Copied scripts not listed in the ledger are dependencies/retained provenance, not claims of independent execution.
- [prior-evidence-verification.json](prior-evidence-verification.json): prior 7669–7718 manifests unchanged.
- `source/`: exact `30e3d39..7ce5cd5` patch and changed source/doc/test snapshots.

## Reset and intent evidence

- [reset7727.json](reset7727.json), adapted [reset7718.py](reset7718.py): 208 storage injections (96 healthy, 112 with legacy markers), 104 zero-carry verify/clear recoveries, six success cases, seven refusal guards and two late-failure witnesses. Eight ordinary restarts revive the old pair only within uncompleted intent establishment, the accepted stop/retry boundary.
- [intent-final7727.json](intent-final7727.json): 42 marker/pair controls, 48 reset retries, 48 direct live-error replays, 72 intent-clearance injections; two witnesses of the new inaccurate durability status. The power-loss example is explicitly a model, not a hardware test.
- [extra-io7727.json](extra-io7727.json): 48 additional stat/close/directory-open injections plus four anchor open/read failures.
- [exact-restore-final7718.json](exact-restore-final7718.json): successful exact restored-pair reset; p held through two restarts; explicit reissue durable through two more.
- [intent7727.json](intent7727.json), [intent-final-adaptation.diff](intent-final-adaptation.diff): original failed supplemental harness retained; targeted corrected run has distinct fixtures, no raw evidence overwritten.
- `reset-cases/`, `intent-final-cases/`, `extra-io-cases/`: forensic journal pairs, archives and markers. Empty directory-in-place fixtures are represented by the captured JSON and are not relied on as Git-trackable artifacts.

## Retained regression evidence

- [policy-schedules.json](policy-schedules.json), [review7195.json](review7195.json): 1,440 supersession schedules.
- [review7694.json](review7694.json): 16 groups including 144 hold/rebind schedules.
- [followup7694.json](followup7694.json): eight journal groups, 24 rebind fault modes and eight abrupt boundaries.
- [focused7701.json](focused7701.json), [marker7701.json](marker7701.json): identity/runtime/rollback/prefix/legacy groups and eight active-marker startup variants.
- [startup7708.json](startup7708.json), [startup-recovery7708.json](startup-recovery7708.json): 48 creation interruptions, 24 explicit recoveries using identical Event objects.
- [clearance7701.json](clearance7701.json), [recovery7708.json](recovery7708.json): 80 retained clearance injections; unreadable files and artifact/version/op controls. Old clearance-only restore witness is intentionally historical.
- [semantic-summary.json](semantic-summary.json): known three obsolete automatic-closure expectations; current/prior 3,072-case and legacy 384-case sweeps pass.

## Integrity and reproduction

`python3 verify_evidence.py` validates complete SHA256SUMS coverage, source provenance and expected run outcomes. The manifest includes the report, itself excluded. No commit or push was performed.

Use a **fresh** evidence directory: scripts deliberately use exclusive run logs and named forensic fixtures. Export non-experiment tracked blobs from the pin into `/tmp/hive-astra-7727-source`, preserving historical experiments read-only (the original run used a symlink). Copy the 7718 Python harnesses and guard according to `copy-provenance.json`, apply `adaptation-7727.diff`, and use the delivered supplemental scripts. Follow `commands.sh` in order. The suite requires pytest/build and the local setuptools/wheel/packaging wheels identified by SHA-256 in `environment.json`; adjust the recorded cache path to a local equivalent. Runtime/pytest temporary files are under `/tmp`, not evidence. No dependency downloads, remote compute, deployment or author full-suite provenance claims.
