# Astra 7734 evidence index

Review: [ASTRA_REVIEW_7734.md](../../docs/ASTRA_REVIEW_7734.md) — **NOT APPROVED** on `8c54bdf2ee26675dcaa4362b2197d167cb3d0241`.

## Execution and provenance

- [RUN.md](RUN.md): scope, counts, timings and failed-run accounting.
- [commands.sh](commands.sh), [runner.py](runner.py), [setup7734.py](setup7734.py): commands, exclusive evidence recorder, pinned exporter. Run only in fresh evidence/source namespaces; runner refuses to overwrite logs.
- [model-verification.json](model-verification.json), [environment.json](environment.json), [offline-verification.json](offline-verification.json): model/provider, environment allowlist and local-wheel hashes/socket controls.
- [source-verification-before.json](source-verification-before.json), [source-verification.json](source-verification.json), [source/target.patch](source/target.patch): pin/export hashes, repository immutability and changed-file snapshots. Code comparison to 7ce5cd5 is also in source/.
- [copy-provenance.json](copy-provenance.json), [adaptation-7734.diff](adaptation-7734.diff), [tempdir-adaptation.diff](tempdir-adaptation.diff), [verifier-adaptation.diff](verifier-adaptation.diff): every inherited Python harness, original/adapted hashes and modifications. Some copied dependency/legacy scripts are not standalone executed; the command and exit ledgers are authoritative.
- [prior-evidence-verification.json](prior-evidence-verification.json): verified 7669/7678/7694/7701/7708/7718/7727 manifests.
- Every substantive run has `<name>-started.json`, `<name>-exit.json`, `<name>.stdout`, `<name>.stderr`. [setup-errors.json](setup-errors.json) records setup-only cwd error and three corrected temporary-path failures.

## Review results

- [pytest.stdout](pytest.stdout): **824 passed in 49.33 s**, exactly one full-suite run.
- [reset7727.json](reset7727.json): retained 208 reset interruption / 104 error cases.
- [intent-final7727.json](intent-final7727.json): 42 marker combinations, 72 clearance cases, 96 retry/live-feed cases and both original 7727 durability witnesses now corrected.
- [extra-io7727.json](extra-io7727.json): 48 supplemental I/O boundaries plus four anchor read/open cases.
- [intent7734.json](intent7734.json): 384 current intent/full-reset boundaries, four compound configurations, mode-000 behavior and remaining Medium classification defect.
- [metadata7734.json](metadata7734.json): new Low presence/error-text finding and nonregular marker wording controls.
- [exact-restore-final7718.json](exact-restore-final7718.json): byte-preserving archives, held restore and explicit durable reissue.
- [review7694.json](review7694.json), [followup7694.json](followup7694.json), [focused7701.json](focused7701.json), startup/clearance/marker/recovery JSON: retained journal regressions.
- [policy-schedules.json](policy-schedules.json): 1,440 supersession schedules; 144 hold/rebind schedules are in review7694.json.
- [semantic-summary.json](semantic-summary.json): current/prior/legacy sweeps and explicitly obsolete expectations.
- Corrected `probes-final`, `older-regressions-final`, `independent-final` logs/results preserve successful unrelated baseline regressions without overwriting initial harness failures.

## Integrity

[secret-scan.json](secret-scan.json) records report/evidence credential-pattern scan. `SHA256SUMS` includes every regular delivered evidence file and the report, excluding itself. Run `PYTHONDONTWRITEBYTECODE=1 python3 verify_evidence.py` for read-only hash, coverage, execution and invariant verification. Generated journal/checkpoint fixtures are deliberate evidence. Damaged/dangling/directory marker fixtures are intentional, not deployment files.
